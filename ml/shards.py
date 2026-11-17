"""Faz 4 v3 Bolum 5.4: shard bicimi (v1) Python okuyucu/yazici.

Bicim belgesi: SHARD_FORMAT.md. C# yazici: Backgammon.SelfPlay.ShardWriter.

Vektorler ham IEEE-754 float32 olarak saklanir; numpy.float32 ile bit duzeyinde korunur.
"""

from __future__ import annotations

import gzip
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Sequence

import numpy as np

MAGIC = b"BGSP"
FORMAT_VERSION = 1
VECTOR_SIZE = 221
HEADER_SIZE = 32

GAME_FLAG_ABORTED = 1

DEC_IS_PASS = 1
DEC_IS_LEARNER = 2
DEC_CHOSEN_IS_TERMINAL = 4
#: Faz 6 Bolum 7.5: karar `dup_cap` nedeniyle egitimden cikarildi.
DEC_DUP_CAPPED = 8
#: Faz 7 Bolum 5.4 / Test 100: karar bir damitma ogretmeninden geldi.
#: v1 okuyucusu bu biti **bilinmeyen bayrak** olarak yok sayar; bicim degismez.
DEC_DISTILLED = 16

_HEADER = struct.Struct("<4sIIIIIII")
_GAME_PREFIX = struct.Struct("<QbBiI")
_GAME_SUFFIX = struct.Struct("<bBB")
_DEC_PREFIX = struct.Struct("<bBHHf")


class ShardFormatError(ValueError):
    """Shard basligi veya kaydi gecersiz."""


@dataclass
class ShardHeader:
    format_version: int = FORMAT_VERSION
    feature_version: int = 1
    vector_size: int = VECTOR_SIZE
    model_version: int = 0
    log_top_candidates: int = 0
    flags: int = 0
    reserved: int = 0

    def pack(self) -> bytes:
        return _HEADER.pack(
            MAGIC,
            self.format_version,
            self.feature_version,
            self.vector_size,
            self.model_version,
            self.log_top_candidates,
            self.flags,
            self.reserved,
        )

    @staticmethod
    def unpack(raw: bytes) -> "ShardHeader":
        if len(raw) != HEADER_SIZE:
            raise ShardFormatError(f"baslik {HEADER_SIZE} bayt olmali, {len(raw)} geldi")
        (magic, fmt, feat, vec, model, top, flags, reserved) = _HEADER.unpack(raw)
        if magic != MAGIC:
            raise ShardFormatError(f"magic 'BGSP' degil: {magic!r}")
        if fmt != FORMAT_VERSION:
            raise ShardFormatError(f"formatVersion desteklenmiyor: {fmt}")
        if vec != VECTOR_SIZE:
            raise ShardFormatError(f"vectorSize uyumsuz: {vec}")
        return ShardHeader(fmt, feat, vec, model, top, flags, reserved)


@dataclass
class DecisionRecord:
    mover: int
    flags: int
    candidate_total: int
    search_value: float
    chosen_vector: np.ndarray | None = None
    q: np.ndarray | None = None
    policy_target_cs: np.ndarray | None = None
    cand_vectors: np.ndarray | None = None

    @property
    def logged_count(self) -> int:
        return 0 if self.q is None else int(self.q.shape[0])

    @property
    def is_pass(self) -> bool:
        return bool(self.flags & DEC_IS_PASS)

    @property
    def is_learner(self) -> bool:
        return bool(self.flags & DEC_IS_LEARNER)

    @property
    def chosen_is_terminal(self) -> bool:
        return bool(self.flags & DEC_CHOSEN_IS_TERMINAL)

    @property
    def is_distilled(self) -> bool:
        """Faz 7 Bolum 5.4: karar damitma ogretmeninden mi geldi?"""
        return bool(self.flags & DEC_DISTILLED)

    def is_dup_capped(self) -> bool:
        """Faz 6 Bolum 7.5: karar tekrar siniri nedeniyle egitimden cikarildi mi?"""
        return bool(self.flags & DEC_DUP_CAPPED)


@dataclass
class GameRecord:
    game_id: int
    learner_side: int
    flags: int
    cube_value: int
    decisions: list[DecisionRecord] = field(default_factory=list)
    winner: int = 0
    result_type: int = 0
    result_points: int = 0

    @property
    def is_aborted(self) -> bool:
        return bool(self.flags & GAME_FLAG_ABORTED)


class _Reader:
    __slots__ = ("_buf", "_pos")

    def __init__(self, buf: bytes) -> None:
        self._buf = buf
        self._pos = 0

    @property
    def eof(self) -> bool:
        return self._pos >= len(self._buf)

    def take(self, n: int) -> bytes:
        end = self._pos + n
        if end > len(self._buf):
            raise ShardFormatError("shard beklenmedik sekilde bitti")
        chunk = self._buf[self._pos:end]
        self._pos = end
        return chunk

    def unpack(self, st: struct.Struct):
        return st.unpack(self.take(st.size))

    def floats(self, n: int) -> np.ndarray:
        if n == 0:
            return np.zeros(0, dtype=np.float32)
        return np.frombuffer(self.take(n * 4), dtype="<f4").astype(np.float32, copy=True)


def read_shard(path: str | Path, *, gzip_auto: bool = True) -> tuple[ShardHeader, list[GameRecord]]:
    """Shard dosyasini okur. `.gz` uzantisi otomatik acilir."""
    p = Path(path)
    use_gzip = gzip_auto and p.suffix.lower() == ".gz"
    raw = gzip.decompress(p.read_bytes()) if use_gzip else p.read_bytes()
    return read_shard_bytes(raw)


def read_shard_bytes(raw: bytes) -> tuple[ShardHeader, list[GameRecord]]:
    reader = _Reader(raw)
    header = ShardHeader.unpack(reader.take(HEADER_SIZE))
    games: list[GameRecord] = []
    while not reader.eof:
        games.append(_read_game(reader))
    return header, games


def _read_game(reader: _Reader) -> GameRecord:
    game_id, learner_side, flags, cube_value, decision_count = reader.unpack(_GAME_PREFIX)
    game = GameRecord(game_id, learner_side, flags, cube_value)
    for _ in range(decision_count):
        game.decisions.append(_read_decision(reader))
    winner, result_type, result_points = reader.unpack(_GAME_SUFFIX)
    game.winner = winner
    game.result_type = result_type
    game.result_points = result_points
    return game


def _read_decision(reader: _Reader) -> DecisionRecord:
    mover, flags, candidate_total, logged, search_value = reader.unpack(_DEC_PREFIX)
    dec = DecisionRecord(mover, flags, candidate_total, search_value)
    if not dec.chosen_is_terminal:
        dec.chosen_vector = reader.floats(VECTOR_SIZE)
    if logged > 0:
        dec.q = reader.floats(logged)
        dec.policy_target_cs = reader.floats(logged)
        dec.cand_vectors = reader.floats(logged * VECTOR_SIZE).reshape(logged, VECTOR_SIZE)
    return dec


def write_shard(
    path: str | Path,
    header: ShardHeader,
    games: Iterable[GameRecord],
    *,
    gzip_out: bool = False,
) -> int:
    """Shard yazar (test/arac amacli). Yazilan ham bayt sayisini dondurur."""
    chunks: list[bytes] = [header.pack()]
    for game in games:
        chunks.append(_pack_game(game))
    raw = b"".join(chunks)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if gzip_out:
        p.write_bytes(gzip.compress(raw))
    else:
        p.write_bytes(raw)
    return len(raw)


def _pack_game(game: GameRecord) -> bytes:
    out: list[bytes] = [
        _GAME_PREFIX.pack(
            game.game_id,
            game.learner_side,
            game.flags,
            game.cube_value,
            len(game.decisions),
        )
    ]
    for dec in game.decisions:
        out.append(_pack_decision(dec))
    out.append(_GAME_SUFFIX.pack(game.winner, game.result_type, game.result_points))
    return b"".join(out)


def _pack_decision(dec: DecisionRecord) -> bytes:
    logged = dec.logged_count
    out: list[bytes] = [
        _DEC_PREFIX.pack(dec.mover, dec.flags, dec.candidate_total, logged, dec.search_value)
    ]
    if not dec.chosen_is_terminal:
        if dec.chosen_vector is None or dec.chosen_vector.shape[0] != VECTOR_SIZE:
            raise ShardFormatError("chosen_vector 221 elemanli olmali")
        out.append(np.asarray(dec.chosen_vector, dtype="<f4").tobytes())
    if logged > 0:
        if dec.policy_target_cs is None or dec.policy_target_cs.shape[0] != logged:
            raise ShardFormatError("policy_target_cs uzunlugu q ile ayni olmali")
        if dec.cand_vectors is None or dec.cand_vectors.shape != (logged, VECTOR_SIZE):
            raise ShardFormatError("cand_vectors sekli (logged, 221) olmali")
        out.append(np.asarray(dec.q, dtype="<f4").tobytes())
        out.append(np.asarray(dec.policy_target_cs, dtype="<f4").tobytes())
        out.append(np.asarray(dec.cand_vectors, dtype="<f4").tobytes())
    return b"".join(out)


def iter_learner_decisions(games: Sequence[GameRecord]) -> Iterator[tuple[GameRecord, DecisionRecord]]:
    """Egitimde kullanilabilir (aborted olmayan) oyunlarin ogrenen kararlarini gezer."""
    for game in games:
        if game.is_aborted:
            continue
        for dec in game.decisions:
            if dec.is_learner:
                yield game, dec