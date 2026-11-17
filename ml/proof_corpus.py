"""Faz 7 Bolum 4.5: kanit korpusu (``er_proof_corpus_v1.json``, 2 000 pozisyon).

**Neden ayri korpus.** Dondurulmus 200 pozisyonluk korpus
(``ml/artifacts/reference_corpus_v1.json``) **iterasyon** olcumleri icindir; ayni
veriyle hem ayar hem kanit yapmak sizintidir (Kural 10). Sampiyon iddiasinin
orneklemi ayri olmalidir.

**Tabakalama.** ``faz x pip farki kovasi``. Zorunlu tabaka (``faz 7.md`` 4.5):
temas / yaris / bearoff x 5 pip kovasi = 15 kova, her kovada **>= 100**.
Buna ek olarak ``bar`` ve ``closed`` fazlari da kova olarak eklenir (gercek
oyunda sik gorulur; disarida birakmak kanit orneginde sistematik bosluk yaratir).
Toplam 17 kova, 2 000 pozisyon -> kova basina ~117.

**Dosya bicimi.** Pozisyonlar **afterstate listesi olmadan** yazilir: afterstate'ler
deterministik olarak :func:`materialize_afterstates` ile (veya ``er_harness``
tarafindan) yeniden uretilir. Boylece dosya ~0,5 MB kalir; 2 000 vaka afterstate
listesiyle ~18 MB olurdu ve depoya islenemezdi.

**Dondurma.** Dosyanin SHA-256 ozeti ``ml/artifacts/stage_a_measurement.md``
icine yazilir; korpus degisirse ozet tutmaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
ML_DIR = REPO_ROOT / "ml"
for _path in (str(ML_DIR), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gnubg_er  # noqa: E402  (yol kurulumundan sonra)
import tools.reference_gen as refgen  # noqa: E402

#: Kanit korpusunun yazildigi yer (``faz 7.md`` 4.5).
PROOF_CORPUS_PATH = REPO_ROOT / "Backgammon.Tests" / "ReferenceData" / "er_proof_corpus_v1.json"

#: Sema surumu.
SCHEMA_VERSION = 1

#: Uretici kimligi (``generatedBy`` alanina yazilir).
GENERATOR = "ml/proof_corpus.py"

#: Sabit tohum. Degisirse korpus degisir ve SHA-256 tutmaz - **bilincli**.
PROOF_SEED = 20260717

#: Hedef pozisyon sayisi (``faz 7.md`` 4.5: 1 829'a %9 pay).
TARGET_POSITIONS = 2000

#: Kova basina en az pozisyon (``faz 7.md`` 4.5).
MIN_PER_BUCKET = 100

#: Pip farki kovalari (mutlak deger, alt sinir dahil, ust sinir haric).
PIP_BUCKETS: tuple[tuple[int, int | None], ...] = (
    (0, 10),
    (10, 25),
    (25, 50),
    (50, None),
)

#: ``faz 7.md`` 4.5'in zorunlu tuttugu fazlar.
REQUIRED_PHASES = ("contact", "race", "bearoff")

#: Kanit orneginde ek olarak kapsanan fazlar.
EXTRA_PHASES = ("bar", "closed")

#: Butun fazlar (kova sirasi).
PROOF_PHASES = REQUIRED_PHASES + EXTRA_PHASES

#: Aday havuzunun hedefin kac kati oldugu.
POOL_FACTOR = 8


class ProofCorpusError(RuntimeError):
    """Kanit korpusu uretilemedi (kova dolmadi vb.)."""


# ----------------------------------------------------------------------
# Pip farki ve kova
# ----------------------------------------------------------------------


def pip_difference(board: Sequence[int], turn: int) -> int:
    """Siranin oyuncusunun pip avantaji (pozitif = sirada olan onde)."""
    return int(gnubg_er.pip_count(board, turn) - gnubg_er.pip_count(board, -turn))


def pip_bucket_label(difference: int) -> str:
    """Mutlak pip farkini kova etiketine cevirir (``"0-10"``, ``"100+"``)."""
    value = abs(int(difference))
    for low, high in PIP_BUCKETS:
        if high is None:
            if value >= low:
                return "%d+" % low
        elif low <= value < high:
            return "%d-%d" % (low, high)
    raise ProofCorpusError("pip farki hicbir kovaya girmedi: %d" % value)


def bucket_key(phase: str, difference: int) -> str:
    """``"<faz>|<kova>"`` anahtari."""
    return "%s|%s" % (phase, pip_bucket_label(difference))


def all_bucket_keys() -> list[str]:
    """Butun (faz x pip kovasi) anahtarlari, deterministik sirada."""
    keys: list[str] = []
    for phase in PROOF_PHASES:
        for low, high in PIP_BUCKETS:
            keys.append("%s|%s" % (phase, "%d+" % low if high is None else "%d-%d" % (low, high)))
    return keys


def bucket_quotas(total: int = TARGET_POSITIONS) -> dict[str, int]:
    """Kova basina kota: esit dagitim, kalan ilk kovalara.

    Her kota **en az** :data:`MIN_PER_BUCKET` olmali; aksi halde
    :class:`ProofCorpusError`.
    """
    keys = all_bucket_keys()
    base = total // len(keys)
    remainder = total - base * len(keys)
    quotas = {key: base + (1 if index < remainder else 0) for index, key in enumerate(keys)}
    for key, quota in quotas.items():
        if quota < MIN_PER_BUCKET:
            raise ProofCorpusError(
                "kova kotasi %d < %d (%s); toplam %d cok kucuk"
                % (quota, MIN_PER_BUCKET, key, total)
            )
    return quotas


# ----------------------------------------------------------------------
# Aday uretimi
# ----------------------------------------------------------------------


def _random_dice(rng: random.Random) -> list[int]:
    """Rastgele zar; cift zarda dort ayni deger (Faz 1 sozlesmesi)."""
    d1 = rng.randint(1, 6)
    d2 = rng.randint(1, 6)
    return [d1, d1, d1, d1] if d1 == d2 else sorted([d1, d2])


def _spread(
    rng: random.Random,
    board: list[int],
    points: Sequence[int],
    sign: int,
    total: int,
) -> None:
    """``total`` tasi ``points`` uzerine 1..5'lik gruplar halinde dagitir."""
    order = list(points)
    rng.shuffle(order)
    remaining = total
    for index, point in enumerate(order):
        if remaining == 0:
            break
        left = len(order) - index - 1
        low = max(1, remaining - 5 * left)
        high = min(5, remaining)
        if low > high:
            low = high
        take = rng.randint(low, high)
        board[point] = sign * take
        remaining -= take
    if remaining:
        board[order[0]] += sign * remaining


def _selfplay_candidates(seed: int, count: int, max_plies: int = 80) -> list[tuple]:
    """Tohumlu rastgele oyunlardan aday pozisyonlar (temas agirlikli)."""
    rng = random.Random(seed)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        board = list(refgen.START_BOARD)
        white_off = black_off = 0
        turn = 1 if rng.random() < 0.5 else -1

        for _ in range(max_plies):
            dice = _random_dice(rng)
            max_steps, states = refgen.legal_after_states(
                board, turn, dice, white_off, black_off
            )
            if max_steps == 0 or not states:
                turn = -turn
                continue

            if len(states) >= 2 and rng.random() < 0.30:
                out.append((list(board), turn, list(dice), white_off, black_off))
                if len(out) >= count:
                    return out

            nb, white_off, black_off = rng.choice(sorted(states))
            board = list(nb)
            if white_off == refgen.PIECES or black_off == refgen.PIECES:
                break
            turn = -turn

    return out


def _race_candidates(seed: int, count: int) -> list[tuple]:
    """Temassiz ama bearoff olmayan pozisyonlar, **ayarlanabilir pip farki**.

    Siyah ``1..split``, beyaz ``split+1..24`` araligina dagitilir. Beklenen pip
    farki ``15 * (split - 12)`` civarindadir; ``split`` 8..16 arasinda gezdirilerek
    butun pip kovalari kapsanir. ``_spread`` rastgele oldugu icin fark sureklidir.
    """
    rng = random.Random(seed ^ 0x7ACE01)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        split = rng.randint(8, 16)
        board = [0] * 26
        _spread(rng, board, range(1, split + 1), -1, 15)
        _spread(rng, board, range(split + 1, 25), 1, 15)
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _bearoff_candidates(seed: int, count: int) -> list[tuple]:
    """Beyazin tum taslari evinde olan pozisyonlar."""
    rng = random.Random(seed ^ 0xBEAF0F)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        _spread(rng, board, range(19, 25), 1, 15)
        _spread(rng, board, range(1, 13), -1, 15)
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _closed_candidates(seed: int, count: int) -> list[tuple]:
    """Rakibin evi tamamen kapali pozisyonlar."""
    rng = random.Random(seed ^ 0xC105ED)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        for point in range(1, 7):
            board[point] = -2
        spot = rng.randint(8, 18)
        board[spot] = -3

        free = [p for p in range(7, 25) if p != spot]
        rng.shuffle(free)
        remaining = 14
        for point in free:
            if remaining == 0:
                break
            take = rng.randint(1, min(5, remaining))
            board[point] = take
            remaining -= take
        if remaining:
            board[free[0]] += remaining
        board[7] = board[7] + 1 if board[7] else 1
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _bar_candidates(seed: int, count: int) -> list[tuple]:
    """Bar'da tas olan pozisyonlar (beyaz veya siyah)."""
    rng = random.Random(seed ^ 0xBA2017)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        on_bar = rng.randint(1, 2)
        if rng.random() < 0.5:
            board[0] = on_bar
            _spread(rng, board, range(1, 25), 1, 15 - on_bar)
            _spread(rng, board, range(1, 25), -1, 15)
        else:
            board[25] = -on_bar
            _spread(rng, board, range(1, 25), -1, 15 - on_bar)
            _spread(rng, board, range(1, 25), 1, 15)
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


# ----------------------------------------------------------------------
# Kova doldurma
# ----------------------------------------------------------------------


def _phase_of(board: Sequence[int], turn: int) -> str:
    """``er_harness.classify_phase`` ile ayni siniflandirma (dongusel import yok)."""
    if int(board[0]) > 0 or int(board[25]) < 0:
        return "bar"
    if refgen.is_bear_off_mode(board, turn):
        return "bearoff"
    home = range(19, 25) if -turn > 0 else range(1, 7)
    if all(int(board[p]) * (-turn) >= 2 for p in home):
        return "closed"
    if not gnubg_er.is_contact(board):
        return "race"
    return "contact"


def _board_key(board: Sequence[int], turn: int, white_off: int, black_off: int) -> tuple:
    """Sizinti korumasi: ayni tahta + ayni kapanmis tas sayisi tekrar sayilmaz."""
    return (tuple(int(v) for v in board), int(white_off), int(black_off))


def _afterstate_count(
    board: Sequence[int], turn: int, dice: Sequence[int], white_off: int, black_off: int
) -> int:
    """Yasal afterstate sayisi (``>= 2`` olmali; tek aday ER'ye guc katmaz)."""
    max_steps, states = refgen.legal_after_states(
        list(board), int(turn), list(dice), int(white_off), int(black_off)
    )
    if max_steps == 0:
        return 0
    return len(states)


def build_proof_corpus(
    seed: int = PROOF_SEED,
    total: int = TARGET_POSITIONS,
) -> dict[str, Any]:
    """Tabakali kanit korpusunu deterministik olarak uretir."""
    quotas = bucket_quotas(total)
    pool_size = total * POOL_FACTOR

    pool: list[tuple] = []
    pool.extend(_selfplay_candidates(seed, pool_size))
    pool.extend(_bar_candidates(seed, pool_size // 4))
    pool.extend(_closed_candidates(seed, pool_size // 4))
    pool.extend(_race_candidates(seed, pool_size // 4))
    pool.extend(_bearoff_candidates(seed, pool_size // 4))

    buckets: dict[str, list[tuple]] = {key: [] for key in quotas}
    seen: set[tuple] = set()

    for position in pool:
        board, turn, dice, white_off, black_off = position
        phase = _phase_of(board, turn)
        if phase not in PROOF_PHASES:
            continue
        key = bucket_key(phase, pip_difference(board, turn))
        if key not in buckets:
            continue
        if len(buckets[key]) >= quotas[key]:
            continue
        identity = _board_key(board, turn, white_off, black_off)
        if identity in seen:
            continue
        # Tek adayli pozisyonda ER tanim geregi 0'dir ve olcume guc katmaz.
        if _afterstate_count(board, turn, dice, white_off, black_off) < 2:
            continue
        seen.add(identity)
        buckets[key].append(position)

    short = {key: quotas[key] - len(buckets[key]) for key in quotas if len(buckets[key]) < quotas[key]}
    if short:
        raise ProofCorpusError(
            "kova dolmadi (aday havuzu %d): %s" % (len(pool), short)
        )

    cases: list[dict[str, Any]] = []
    for key in all_bucket_keys():
        for position in buckets[key]:
            board, turn, dice, white_off, black_off = position
            difference = pip_difference(board, turn)
            cases.append(
                {
                    "name": "p-%04d" % len(cases),
                    "phase": key.split("|")[0],
                    "pipBucket": key.split("|")[1],
                    "pipDiff": int(difference),
                    "board": [int(v) for v in board],
                    "turn": int(turn),
                    "dice": [int(d) for d in dice],
                    "whiteOff": int(white_off),
                    "blackOff": int(black_off),
                }
            )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "seed": int(seed),
        "targetPositions": int(total),
        "minPerBucket": MIN_PER_BUCKET,
        "pipBuckets": [[low, high] for low, high in PIP_BUCKETS],
        "requiredPhases": list(REQUIRED_PHASES),
        "extraPhases": list(EXTRA_PHASES),
        "stratification": {key: len(buckets[key]) for key in all_bucket_keys()},
        "count": len(cases),
        "cases": cases,
    }


# ----------------------------------------------------------------------
# Afterstate uretimi (dosyada saklanmaz)
# ----------------------------------------------------------------------


def materialize_afterstates(case: dict[str, Any]) -> dict[str, Any]:
    """Pozisyondan afterstate listesini uretir (``er_harness`` bicimi).

    Kanit korpusu afterstate saklamaz; ``er_harness`` bu fonksiyonla
    ``afterStates`` alanini doldurur. Sonuc **deterministiktir**.
    """
    if case.get("afterStates"):
        return case
    board = [int(v) for v in case["board"]]
    turn = int(case["turn"])
    dice = [int(d) for d in case["dice"]]
    white_off = int(case.get("whiteOff", 0))
    black_off = int(case.get("blackOff", 0))
    max_steps, states = refgen.legal_after_states(board, turn, dice, white_off, black_off)
    out = dict(case)
    out["maxSteps"] = int(max_steps)
    out["afterStates"] = [
        {"board": list(b), "whiteOff": int(w), "blackOff": int(k)} for (b, w, k) in sorted(states)
    ]
    return out


# ----------------------------------------------------------------------
# Dosya islemleri
# ----------------------------------------------------------------------


def write_corpus(corpus: dict[str, Any], path: Path = PROOF_CORPUS_PATH) -> str:
    """Korpusu yazar ve SHA-256 ozetini doner."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(corpus, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return sha256_of(path)


def sha256_of(path: Path) -> str:
    """Dosyanin SHA-256 ozeti (kucuk harf onaltilik)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_corpus(path: Path = PROOF_CORPUS_PATH) -> dict[str, Any]:
    """Korpusu okur ve sema surumunu dogrular."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise ProofCorpusError(
            "sema surumu %r, beklenen %d" % (data.get("schemaVersion"), SCHEMA_VERSION)
        )
    if not isinstance(data.get("cases"), list):
        raise ProofCorpusError("cases listesi yok: %s" % path)
    return data


def load_cases(path: Path = PROOF_CORPUS_PATH) -> list[dict[str, Any]]:
    """Afterstate'leri doldurulmus vaka listesi (``er_harness`` icin)."""
    return [materialize_afterstates(case) for case in load_corpus(path)["cases"]]


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proof_corpus",
        description="Faz 7 kanit korpusunu uretir (2 000 pozisyon, tabakali).",
    )
    parser.add_argument("--out", default=str(PROOF_CORPUS_PATH), help="cikti dosyasi")
    parser.add_argument("--seed", type=int, default=PROOF_SEED, help="tohum")
    parser.add_argument("--count", type=int, default=TARGET_POSITIONS, help="pozisyon sayisi")
    parser.add_argument("--verify", action="store_true", help="yalnizca ozeti dogrula")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.out)

    if args.verify:
        if not path.exists():
            print("kanit korpusu yok: %s" % path)
            return 2
        corpus = load_corpus(path)
        print("count=%d sha256=%s" % (corpus["count"], sha256_of(path)))
        return 0

    corpus = build_proof_corpus(seed=args.seed, total=args.count)
    digest = write_corpus(corpus, path)
    print("count=%d sha256=%s -> %s" % (corpus["count"], digest, path))
    for key, value in corpus["stratification"].items():
        print("  %-16s %d" % (key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
