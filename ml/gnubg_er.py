"""Faz 4 v3 Bölüm 9 (Aşama D) — GNU Backgammon ile pozisyon başına equity kaybı (ER).

Spec (Bölüm 9, Aşama D): "GNU Backgammon kuruluysa ve komut satirindan calistirilabiliyorsa
referans pozisyonlarda pozisyon başına equity kaybı (ER) ölçümü için bir yontem dokumante
edilir. Uretilemezse bunu acikca belirt ve uydurma değer yazma."

Bu modul ölçümü **gercekten** yapar: her referans pozisyon için

1. modelin afterstate'leri 221 elemanlı vektöre çevrilip ONNX modeline verilir,
   ``argmax`` ile modelin seçtiği hamle belirlenir,
2. **tüm** afterstate'ler tek bir ``gnubg-cli`` surecinde, sıra rakibe verilerek ve
   N-ply cubeless ``eval`` ile değerlendirilir; işaret çevrilerek hamleyi yapanın
   equity'si bulunur,
3. ``E_best = max(afterstate equity'leri)``, ``E_model = modelin seçtiği afterstate``,
4. ``ER = E_best - E_model`` hesaplanir.

``E_best`` ve ``E_model`` aynı değerlendiriciyle (aynı ply, aynı cubeless mod) üretildiği
için ER tutarlıdır. gnubg'nin kendi ``hint`` sıralaması yalnızca bilgi amaçlı kaydedilir:
``gnubg-cli``'de ``hint`` her zaman 0-ply çalışır.

gnubg yoksa modul **uydurma değer uretmez**; acik bir mesajla sıfır olmayan cikis kodu dondurur.

Kullanim::

    python ml/gnubg_er.py --model ml/runs/stage_d/onnx/model_v10.onnx \
        --out ml/artifacts/stage_d_er.md --json ml/artifacts/stage_d_er.json

    python ml/gnubg_er.py --model A.onnx --limit 5 --plies 2
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------

DEFAULT_CASES = Path("Backgammon.Tests/ReferenceData/reference_positions.json")
DEFAULT_PLIES = 2
#: gnubg'nin ``eval`` komutunun basabildigi en derin sutun (F6-32).
MAX_EVAL_PLIES = 2
DEFAULT_TIMEOUT = 180
PIECES_PER_PLAYER = 15

GNUBG_ENV = "GNUBG_CLI"

GNUBG_CANDIDATES: tuple[str, ...] = (
    r"F:\Program Files (x86)\gnubg\gnubg-cli.exe",
    r"F:\Program Files\gnubg\gnubg-cli.exe",
    r"C:\Program Files (x86)\gnubg\gnubg-cli.exe",
    r"C:\Program Files\gnubg\gnubg-cli.exe",
    "/usr/bin/gnubg-cli",
    "/usr/games/gnubg-cli",
    "/usr/local/bin/gnubg-cli",
    "/opt/homebrew/bin/gnubg-cli",
)

# Vektor semasi (Faz 2 v4) — Backgammon.Core/VectorLayout.cs ile birebir.
PIP_DIVISOR = 167.0
ACTIVE_OFFSET = 0
OPP_OFFSET = 96
ACTIVE_BAR = 192
OPP_BAR = 193
ACTIVE_OFF = 194
OPP_OFF = 195
CUBE_OWNER = 196
CUBE_VALUE = 197
IS_MONEY = 198
IS_CRAWFORD = 199
ACTIVE_PIP = 200
OPP_PIP = 201
ACTIVE_ESC = 202
OPP_ESC = 203
IS_CONTACT = 204
ACTIVE_AWAY = 205
OPP_AWAY = 213
AWAY_BUCKETS = 8
VECTOR_SIZE = 221

_INF = 1 << 30


# ----------------------------------------------------------------------
# gnubg kesfi
# ----------------------------------------------------------------------


def find_gnubg(explicit: str | Path | None = None) -> Path | None:
    """``gnubg-cli`` yolunu bulur; bulunamazsa ``None`` doner.

    Sirasi: acik parametre -> ``GNUBG_CLI`` ortam degiskeni -> ``PATH`` -> bilinen kurulum
    dizinleri.
    """
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        return None

    import os

    env = os.environ.get(GNUBG_ENV)
    if env:
        candidate = Path(env)
        if candidate.is_file():
            return candidate

    for name in ("gnubg-cli", "gnubg-cli.exe", "gnubg"):
        found = shutil.which(name)
        if found:
            return Path(found)

    for raw in GNUBG_CANDIDATES:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate

    return None


def gnubg_version(exe: Path, timeout: int = 60) -> str:
    """``gnubg --version`` ciktisinin ilk satirini dondurur (bossa boş dize)."""
    try:
        proc = subprocess.run(
            [str(exe), "--version"], capture_output=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""

    text = (proc.stdout or b"").decode("utf-8", "replace")
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


# ----------------------------------------------------------------------
# Tahta donusumu
# ----------------------------------------------------------------------


def board_to_simple(board: Sequence[int]) -> list[int]:
    """Proje tahtasini gnubg ``set board simple`` dizisine cevirir.

    Proje duzeni: ``board[0]`` = Beyaz bar, ``board[1..24]`` = 1..24 haneleri,
    ``board[25]`` = Siyah bar. Pozitif = Beyaz, negatif = Siyah.

    gnubg duzeni aynı hane numaralarini kullanır ama **X = Siyah** (X 24->1 oynar,
    evi 1-6) ve **O = Beyaz**. Bu yüzden isaretler terstir ve barlar yer degistirir::

        simple[0]  = -board[25]   # X bari = Siyah bari
        simple[i]  = -board[i]    # i = 1..24
        simple[25] =  board[0]    # O bari = Beyaz bari

    Dogrulama: baslangic pozisyonu ``4HPwATDgc/ABMA`` position ID'sini verir ve
    ``show pipcount`` iki oyuncu için de 167 bildirir.
    """
    if len(board) < 26:
        raise ValueError("board en az 26 eleman olmali: %d" % len(board))

    simple = [0] * 26
    simple[0] = -int(board[25])
    for i in range(1, 25):
        simple[i] = -int(board[i])
    simple[25] = int(board[0])
    return simple


def gnubg_turn(turn: int) -> int:
    """Proje sirasini gnubg ``set turn`` degerine cevirir.

    gnubg: 0 = O (Beyaz), 1 = X (Siyah). Proje: +1 = Beyaz, -1 = Siyah.
    """
    if turn == 1:
        return 0
    if turn == -1:
        return 1
    raise ValueError("turn +1 veya -1 olmali: %r" % (turn,))


# ----------------------------------------------------------------------
# Vektorlestirme (BackgammonVectorizer'in Python portu, 500/500 altin kayitla dogrulandi)
# ----------------------------------------------------------------------


def _distance_to_off(point: int, turn: int) -> int:
    return 25 - point if turn == 1 else point


def _bar_index(turn: int) -> int:
    return 0 if turn == 1 else 25


def _count_of(value: int, player: int) -> int:
    if player > 0:
        return value if value > 0 else 0
    return -value if value < 0 else 0


def pip_count(board: Sequence[int], player: int) -> int:
    """Oyuncunun pip sayisi; bar tasi 25 sayilir."""
    total = 0
    for point in range(1, 25):
        n = _count_of(board[point], player)
        if n:
            total += n * _distance_to_off(point, player)
    bar = _count_of(board[_bar_index(player)], player)
    if bar:
        total += bar * 25
    return total


def _active_max_j(board: Sequence[int], player: int) -> int:
    if _count_of(board[_bar_index(player)], player) > 0:
        return 25
    best = 0
    for point in range(1, 25):
        if _count_of(board[point], player) > 0:
            j = _distance_to_off(point, player)
            if j > best:
                best = j
    return best


def _opp_min_j(board: Sequence[int], player: int) -> int:
    opponent = -player
    if _count_of(board[_bar_index(opponent)], opponent) > 0:
        return 0
    best = _INF
    for point in range(1, 25):
        if _count_of(board[point], opponent) > 0:
            j = _distance_to_off(point, player)
            if j < best:
                best = j
    return best


def escaped_count(board: Sequence[int], player: int) -> int:
    """Kacak tas sayisi (Faz 2 v4 Bölüm 3.3)."""
    j_opp_min = _opp_min_j(board, player)
    if j_opp_min <= 0:
        return 0
    count = 0
    for point in range(1, 25):
        n = _count_of(board[point], player)
        if n and _distance_to_off(point, player) < j_opp_min:
            count += n
    return count


def is_contact(board: Sequence[int]) -> bool:
    """Temas var mi (Faz 2 v4 Bölüm 3.4)."""
    return _active_max_j(board, 1) > _opp_min_j(board, 1)


def _cube_value_neuron(cube_value: int) -> float:
    if cube_value <= 1:
        return 0.0
    log2 = 0
    power = 1
    while power < cube_value:
        power <<= 1
        log2 += 1
    value = log2 / 6.0
    return 1.0 if value > 1.0 else value


def _away_bucket(away: int) -> int:
    return (away if away < AWAY_BUCKETS else AWAY_BUCKETS) - 1


def _write_point_block(out: list[float], offset: int, n: int) -> None:
    out[offset + 0] = 1.0 if n == 1 else 0.0
    out[offset + 1] = 1.0 if n >= 2 else 0.0
    out[offset + 2] = 1.0 if n >= 3 else 0.0
    out[offset + 3] = (n - 3) / 2.0 if n > 3 else 0.0


def vectorize(
    board: Sequence[int],
    white_borne_off: int,
    black_borne_off: int,
    *,
    cube_value: int = 1,
    cube_owner: int = 0,
    match_length: int = 0,
    white_score: int = 0,
    black_score: int = 0,
    is_crawford: bool = False,
    perspective: int = 1,
) -> list[float]:
    """221 elemanlı giris vektorunu uretir (``BackgammonVectorizer`` portu)."""
    if perspective not in (1, -1):
        raise ValueError("perspective +1 veya -1 olmali: %r" % (perspective,))

    out = [0.0] * VECTOR_SIZE

    for point in range(1, 25):
        value = board[point]
        if perspective > 0:
            active_n = value if value > 0 else 0
            opp_n = -value if value < 0 else 0
        else:
            active_n = -value if value < 0 else 0
            opp_n = value if value > 0 else 0
        j = _distance_to_off(point, perspective)
        _write_point_block(out, ACTIVE_OFFSET + 4 * (j - 1), active_n)
        _write_point_block(out, OPP_OFFSET + 4 * (j - 1), opp_n)

    out[ACTIVE_BAR] = _count_of(board[_bar_index(perspective)], perspective) / 2.0
    out[OPP_BAR] = _count_of(board[_bar_index(-perspective)], -perspective) / 2.0
    out[ACTIVE_OFF] = (white_borne_off if perspective > 0 else black_borne_off) / 15.0
    out[OPP_OFF] = (black_borne_off if perspective > 0 else white_borne_off) / 15.0
    out[CUBE_OWNER] = cube_owner * perspective
    out[CUBE_VALUE] = _cube_value_neuron(cube_value)
    out[IS_MONEY] = 1.0 if match_length == 0 else 0.0
    out[IS_CRAWFORD] = 1.0 if is_crawford else 0.0
    out[ACTIVE_PIP] = pip_count(board, perspective) / PIP_DIVISOR
    out[OPP_PIP] = pip_count(board, -perspective) / PIP_DIVISOR
    out[ACTIVE_ESC] = escaped_count(board, perspective) / 15.0
    out[OPP_ESC] = escaped_count(board, -perspective) / 15.0
    out[IS_CONTACT] = 1.0 if is_contact(board) else 0.0

    if match_length > 0:
        active_away = match_length - (white_score if perspective > 0 else black_score)
        opp_away = match_length - (black_score if perspective > 0 else white_score)
        out[ACTIVE_AWAY + _away_bucket(active_away)] = 1.0
        out[OPP_AWAY + _away_bucket(opp_away)] = 1.0

    return out


# ----------------------------------------------------------------------
# gnubg cikti ayristirma
# ----------------------------------------------------------------------

_NUMBER = r"[+\-]?\d+(?:[.,]\d+)?"

_HINT_RE = re.compile(
    r"^\s*(\d+)\.\s+(?P<body>.*?)\s+Eq\.:\s*(?P<eq>" + _NUMBER + r")"
    r"(?:\s*\(\s*(?P<loss>" + _NUMBER + r")\s*\))?\s*$",
    re.MULTILINE,
)

_HINT_PREFIX_RE = re.compile(r"^(?:Cubeful|Cubeless)\s+\d+-ply\s+")

_EVAL_RE = re.compile(r"^\s*(?P<label>static|\d+\s*ply):\s*(?P<rest>.+)$", re.MULTILINE)

_PIP_RE = re.compile(
    r"The pip counts are:\s*(?P<xname>\S+)\s+(?P<xpips>\d+),\s*(?P<oname>\S+)\s+(?P<opips>\d+)\."
)


def parse_number(text: str) -> float:
    """gnubg'nin ondalik virgullu sayilarini (``+0,160``) float'a cevirir."""
    return float(text.replace(",", "."))


@dataclass(frozen=True)
class HintMove:
    """gnubg ``hint`` listesindeki tek bir hamle."""

    rank: int
    move: str
    equity: float
    loss: float | None


def parse_hint(text: str) -> list[HintMove]:
    """``hint`` ciktisindaki siralanmis hamleleri ayristirir.

    Ondalik virgul, ``(-0,168)`` kayıp eki ve ``(2)`` katlama eki desteklenir.
    """
    moves: list[HintMove] = []
    for match in _HINT_RE.finditer(text):
        body = match.group("body").strip()
        body = _HINT_PREFIX_RE.sub("", body).strip()
        loss_text = match.group("loss")
        moves.append(
            HintMove(
                rank=int(match.group(1)),
                move=body,
                equity=parse_number(match.group("eq")),
                loss=parse_number(loss_text) if loss_text else None,
            )
        )
    return moves


def parse_eval(text: str) -> dict[str, float]:
    """``eval`` tablosundaki cubeless equity'leri ``{"static": .., "1": .., "2": ..}`` olarak doner."""
    result: dict[str, float] = {}
    for match in _EVAL_RE.finditer(text):
        label = match.group("label").replace(" ", "")
        if label == "static":
            key = "static"
        else:
            key = label.replace("ply", "")
        numbers = re.findall(_NUMBER, match.group("rest"))
        if len(numbers) < 6:
            continue
        result[key] = parse_number(numbers[5])
    return result


def _pipcount_from_match(match: re.Match[str]) -> tuple[int, int] | None:
    entries = {
        match.group("xname").strip("`'\""): int(match.group("xpips")),
        match.group("oname").strip("`'\""): int(match.group("opips")),
    }
    monster = entries.get("MONSTER")
    gnubg = entries.get("gnubg")
    if monster is None or gnubg is None:
        return None
    return monster, gnubg


def parse_pipcount(text: str) -> tuple[int, int] | None:
    """``show pipcount`` ciktisindan ``(MONSTER_pips, gnubg_pips)`` doner.

    gnubg satiri **sirada olan oyuncuyu önce** yazdigi için (``set turn`` degerine göre
    sira degisir) oyuncular adlarina göre eslestirilir. ``MONSTER`` = X = Siyah,
    ``gnubg`` = O = Beyaz.
    """
    match = _PIP_RE.search(text)
    if not match:
        return None
    return _pipcount_from_match(match)


def parse_pipcounts(text: str) -> list[tuple[int, int]]:
    """Coklu ``show pipcount`` blogundaki tüm pip ciftlerini sirayla doner."""
    result: list[tuple[int, int]] = []
    for match in _PIP_RE.finditer(text):
        pips = _pipcount_from_match(match)
        if pips is not None:
            result.append(pips)
    return result


def parse_evals(text: str) -> list[dict[str, float]]:
    """Coklu ``eval`` blogunu sirayla ayristirir.

    Bloklar ``show pipcount`` ciktisiyla ayrilir: her blokta önce pip satiri, sonra
    ``eval`` tablosu bulunur. ``Position ID:`` ile bolmek yaniltir cunku ``set board``
    komutu da tahtayi position ID'siyle birlikte echo'lar.
    """
    blocks = text.split("The pip counts are:")[1:]
    return [parse_eval(block) for block in blocks]


# ----------------------------------------------------------------------
# gnubg oturumu
# ----------------------------------------------------------------------


class GnubgError(RuntimeError):
    """gnubg cagrisi beklenen ciktiyi uretmedi."""


class GnubgSession:
    """``gnubg-cli``'yi metin modunda calistiran ince sarmalayici."""

    def __init__(self, exe: Path, *, plies: int = DEFAULT_PLIES, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.exe = Path(exe)
        self.plies = plies
        self.timeout = timeout

    def run(self, commands: Iterable[str]) -> str:
        """Komutlari tek bir gnubg surecine besler ve stdout'u doner."""
        script = "\n".join(list(commands) + ["quit"]) + "\n"
        try:
            proc = subprocess.run(
                [str(self.exe), "-t"],
                input=script.encode("ascii", "replace"),
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - ortam bagimli
            raise GnubgError("gnubg calistirilamadi: %s" % exc) from exc

        out = (proc.stdout or b"").decode("utf-8", "replace")
        err = (proc.stderr or b"").decode("utf-8", "replace")
        return out + err

    def _preamble(self) -> list[str]:
        return [
            "set cube use off",
            "new game",
            "set evaluation chequerplay evaluation plies %d" % self.plies,
            "set evaluation chequerplay evaluation cubeful off",
        ]

    def load_board(self, board: Sequence[int], turn: int) -> list[str]:
        """Tahtayi yukleyen komut dizisini doner (sira ve pip dogrulamasi dahil değil)."""
        simple = board_to_simple(board)
        return [
            "set board simple " + " ".join(str(v) for v in simple),
            "set turn %d" % gnubg_turn(turn),
        ]

    def hint(self, board: Sequence[int], turn: int, dice: Sequence[int]) -> tuple[list[HintMove], str]:
        """Pozisyonu yukler, pip sayilarini dogrular ve ``hint`` listesini doner."""
        commands = self._preamble()
        commands.extend(self.load_board(board, turn))
        commands.append("set dice %d %d" % (int(dice[0]), int(dice[1])))
        commands.append("show pipcount")
        commands.append("hint")
        text = self.run(commands)

        self._verify_pips(text, board)
        moves = parse_hint(text)
        if not moves:
            raise GnubgError("hint çıktısı ayristirilamadi")
        return moves, text

    def eval_position(self, board: Sequence[int], turn: int) -> tuple[dict[str, float], str]:
        """Pozisyonu yukler, pip sayilarini dogrular ve ``eval`` tablosunu doner."""
        commands = self._preamble()
        commands.extend(self.load_board(board, turn))
        commands.append("show pipcount")
        commands.append("eval")
        text = self.run(commands)

        self._verify_pips(text, board)
        table = parse_eval(text)
        if not table:
            raise GnubgError("eval çıktısı ayristirilamadi")
        return table, text

    def eval_afterstates(
        self, boards: Sequence[Sequence[int]], turn: int
    ) -> list[dict[str, float]]:
        """Birden çok tahtayi **tek** gnubg surecinde degerlendirir.

        Her tahta için pip sayilari dogrulanir. Tek surec kullanmak, afterstate sayisi
        onlarca olan pozisyonlarda ölçümü dakikalar yerine saniyelere indirir.
        """
        if not boards:
            return []

        commands = self._preamble()
        for board in boards:
            # ``set board`` yalnizca oyun basindayken kabul edilir; ilk tahtadan sonra
            # gnubg zar atmaya gectigi icin sonraki tahtalar sessizce reddedilir.
            commands.append("new game")
            commands.extend(self.load_board(board, turn))
            commands.append("show pipcount")
            commands.append("eval")
        text = self.run(commands)

        pips = parse_pipcounts(text)
        tables = parse_evals(text)
        if len(pips) != len(boards) or len(tables) != len(boards):
            raise GnubgError(
                "toplu eval çıktısı eksik (pip %d, tablo %d, tahta %d)"
                % (len(pips), len(tables), len(boards))
            )

        for board, (monster_pips, gnubg_pips), table in zip(boards, pips, tables):
            expected_monster = pip_count(board, -1)
            expected_gnubg = pip_count(board, 1)
            if monster_pips != expected_monster or gnubg_pips != expected_gnubg:
                raise GnubgError(
                    "tahta yuklenmedi (pip MONSTER %d/%d, gnubg %d/%d)"
                    % (monster_pips, expected_monster, gnubg_pips, expected_gnubg)
                )
            if not table:
                raise GnubgError("eval çıktısı ayristirilamadi")
        return tables

    @staticmethod
    def _verify_pips(text: str, board: Sequence[int]) -> None:
        """``set board simple`` sessizce reddedilebildigi için pip sayilarini karsilastirir."""
        pips = parse_pipcount(text)
        if pips is None:
            raise GnubgError("pip sayilari okunamadi")
        monster_pips, gnubg_pips = pips
        expected_monster = pip_count(board, -1)
        expected_gnubg = pip_count(board, 1)
        if monster_pips != expected_monster or gnubg_pips != expected_gnubg:
            raise GnubgError(
                "tahta yuklenmedi (pip MONSTER %d/%d, gnubg %d/%d)"
                % (monster_pips, expected_monster, gnubg_pips, expected_gnubg)
            )


# ----------------------------------------------------------------------
# Referans veri
# ----------------------------------------------------------------------


def load_cases(path: Path) -> list[dict[str, Any]]:
    """``reference_positions.json`` dosyasini okur."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases listesi bulunamadi: %s" % path)
    return cases


def case_piece_counts(case: dict[str, Any]) -> tuple[int, int]:
    """Pozisyondaki beyaz/siyah tas sayilari (bar ve toplananlar dahil)."""
    board = case["board"]
    white = int(case.get("whiteOff", 0)) + max(int(board[0]), 0)
    black = int(case.get("blackOff", 0)) + max(-int(board[25]), 0)
    for point in range(1, 25):
        value = int(board[point])
        if value > 0:
            white += value
        elif value < 0:
            black -= value
    return white, black


def is_usable(case: dict[str, Any]) -> bool:
    """ER ölçümü için kullanılabilir mi (15/15 tas ve boş olmayan afterstate listesi)."""
    white, black = case_piece_counts(case)
    if white != PIECES_PER_PLAYER or black != PIECES_PER_PLAYER:
        return False
    return bool(case.get("afterStates"))


def split_cases(cases: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Kullanilabilir vakaları ve disarida kalanlarin adlarini doner."""
    usable: list[dict[str, Any]] = []
    skipped: list[str] = []
    for case in cases:
        if is_usable(case):
            usable.append(case)
        else:
            skipped.append(str(case.get("name", "?")))
    return usable, skipped


# ----------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------


class OnnxScorer:
    """ONNX modelini yukleyip afterstate'leri degerlendirir.

    Iki cikti sozlesmesini de destekler:

    ``output_version = 1``
        ``value`` [B, 1] dogrudan skaler deger.
    ``output_version = 2`` (Faz 6)
        ``probs`` [B, 6] dislayici olasiliklar; skaler deger
        ``ml.equity.equity_from_exclusive`` ile turetilir. Bu, C#
        ``OutcomeDistribution.Equity`` ile ayni ifadedir (Test 53).
    """

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort  # yerel import: gnubg yoksa bile modul import edilebilsin

        self.model_path = Path(model_path)
        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        outputs = [o.name for o in self.session.get_outputs()]
        self.probs_name = "probs" if "probs" in outputs else None
        self.value_name = "value" if "value" in outputs else outputs[0]
        self.policy_name = "policy_logit" if "policy_logit" in outputs else None
        self.output_version = 2 if self.probs_name is not None else 1

    def _run(self, name: str, vectors: Sequence[Sequence[float]]) -> list[float]:
        import numpy as np

        if not vectors:
            return []
        batch = np.asarray(vectors, dtype=np.float32)
        result = self.session.run([name], {self.input_name: batch})[0]
        return [float(v) for v in np.asarray(result).reshape(-1)]

    def probs(self, vectors: Sequence[Sequence[float]]) -> list[list[float]]:
        """Her vektör için 6 sinifli dislayici olasilik vektorunu doner."""
        import numpy as np

        if self.probs_name is None:
            raise GnubgError("modelde 'probs' ciktisi yok (output_version = 1)")
        if not vectors:
            return []
        batch = np.asarray(vectors, dtype=np.float32)
        result = self.session.run([self.probs_name], {self.input_name: batch})[0]
        return np.asarray(result, dtype=np.float64).reshape(-1, 6).tolist()

    def values(self, vectors: Sequence[Sequence[float]]) -> list[float]:
        """Her vektör için değer başı ciktisini doner (v2'de equity'ye turetilir)."""
        if self.output_version == 2:
            from equity import equity_from_exclusive

            probs = self.probs(vectors)
            if not probs:
                return []
            return [float(v) for v in equity_from_exclusive(probs)]
        return self._run(self.value_name, vectors)

    def logits(self, vectors: Sequence[Sequence[float]]) -> list[float]:
        """Her vektör için politika logit'ini doner (softmax tekduze olduğu için argmax aynı)."""
        if self.policy_name is None:
            raise GnubgError("modelde policy_logit çıktısı yok")
        return self._run(self.policy_name, vectors)


CRITERIA = ("policy", "value", "pip")

CRITERION_LABELS = {
    "policy": "politika başı argmax (C# `ArgMaxCandidate` ile aynı)",
    "value": "değer başı argmax",
    "pip": "pip farkı argmax (PipBot referans tabani)",
}


def score_afterstates(
    scorer: OnnxScorer, case: dict[str, Any], criterion: str = "policy"
) -> tuple[int, list[float]]:
    """Hamle secim kriterine göre ``argmax`` afterstate indeksini ve skorlari doner.

    - ``policy``: politika başı logit'i (C#'taki ``ArgMaxCandidate`` ile aynı; varsayılan)
    - ``value``: değer başı çıktısı
    - ``pip``: ``rakipPip - kendiPip`` (PipBot referans tabani)
    """
    if criterion not in CRITERIA:
        raise ValueError("criterion %s olmali: %r" % (CRITERIA, criterion))

    turn = int(case["turn"])
    after_states = case["afterStates"]
    if not after_states:
        raise ValueError("afterstate yok: %s" % case.get("name"))

    if criterion == "pip":
        scores = [
            float(pip_count(a["board"], -turn) - pip_count(a["board"], turn))
            for a in after_states
        ]
    else:
        vectors = [
            vectorize(
                a["board"],
                int(a.get("whiteOff", 0)),
                int(a.get("blackOff", 0)),
                perspective=turn,
            )
            for a in after_states
        ]
        scores = scorer.logits(vectors) if criterion == "policy" else scorer.values(vectors)

    best = max(range(len(scores)), key=lambda i: scores[i])
    return best, scores


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


@dataclass
class PositionResult:
    """Tek bir pozisyonun ER ölçümü."""

    name: str
    turn: int
    dice: list[int]
    afterstate_count: int
    gnubg_best_index: int
    gnubg_best_equity: float
    gnubg_hint_move: str
    gnubg_hint_equity: float
    model_afterstate_index: int
    model_equity: float
    equity_loss: float
    model_value: float
    exact_match: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "turn": self.turn,
            "dice": list(self.dice),
            "afterstateCount": self.afterstate_count,
            "gnubgBestIndex": self.gnubg_best_index,
            "gnubgBestEquity": round(self.gnubg_best_equity, 6),
            "gnubgHintMove": self.gnubg_hint_move,
            "gnubgHintEquity": round(self.gnubg_hint_equity, 6),
            "modelAfterstateIndex": self.model_afterstate_index,
            "modelEquity": round(self.model_equity, 6),
            "equityLoss": round(self.equity_loss, 6),
            "modelValue": round(self.model_value, 6),
            "exactMatch": self.exact_match,
            "notes": list(self.notes),
        }


def _equity_at(table: dict[str, float], plies: int) -> float:
    """``eval`` tablosundan istenen derinlikteki cubeless equity'yi secer.

    gnubg'nin ``eval`` komutu **her zaman** yalnizca ``static`` (0-ply), ``1 ply`` ve
    ``2 ply`` satirlarini basar; ``set evaluation chequerplay evaluation plies N``
    ayari bu tablonun derinligini degistirmez (F6-32). Bu yuzden istenen derinlik
    tabloda yoksa sessizce baska bir sutuna dusmek yerine hata verilir: aksi halde
    "3-ply" olcumu farkinda olmadan 0-ply (``static``) degerini okur.
    """
    key = "static" if plies == 0 else str(plies)
    if key not in table:
        raise ValueError(
            "gnubg 'eval' tablosunda %d-ply sutunu yok (mevcut: %s). "
            "gnubg 'eval' en fazla 2-ply uretir; daha derin hakem icin 'hint' "
            "protokolu gerekir (bkz. ASSUMPTIONS.md F6-32)."
            % (plies, ", ".join(sorted(table)))
        )
    return table[key]


def measure_position(
    session: GnubgSession,
    scorer: OnnxScorer,
    case: dict[str, Any],
    *,
    plies: int = DEFAULT_PLIES,
    criterion: str = "policy",
) -> PositionResult:
    """Tek bir referans pozisyonu için ER olcumunu yapar.

    Referans equity **tüm afterstate'lerin aynı derinlikteki gnubg değerlendirmesinin
    maksimumu** olarak alinir. Boylece ``E_best`` ve ``E_model`` aynı değerlendiriciyle
    (aynı ply, aynı cubeless mod) uretilir ve ER elmayla armut karşılaştırması olmaz.
    """
    board = case["board"]
    turn = int(case["turn"])
    dice = [int(d) for d in case["dice"]]
    after_states = case["afterStates"]

    index, values = score_afterstates(scorer, case, criterion)

    # Afterstate'ler hamleyi yapanin bakis acisindan degerlendirilir: sira rakibe verilir
    # ve isaret cevrilir.
    tables = session.eval_afterstates([a["board"] for a in after_states], -turn)
    equities = [-_equity_at(table, plies) for table in tables]

    best_index = max(range(len(equities)), key=lambda i: equities[i])
    best_equity = equities[best_index]
    model_equity = equities[index]

    # gnubg'nin kendi 0-ply siralamasi yalnizca bilgi amacli kaydedilir (gnubg-cli'de
    # ``hint`` her zaman 0-ply calisir; ``set evaluation ... plies`` sadece ``eval``'i etkiler).
    hint_move = ""
    hint_equity = 0.0
    try:
        hints, _ = session.hint(board, turn, dice)
        if hints:
            hint_move = hints[0].move
            hint_equity = hints[0].equity
    except GnubgError:
        pass

    notes: list[str] = []
    if len(after_states) == 1:
        notes.append("tek yasal hamle")
    if hint_move and abs(hint_equity - best_equity) > 0.02:
        notes.append("0-ply hint ile %d-ply eval farkli" % plies)

    return PositionResult(
        name=str(case.get("name", "?")),
        turn=turn,
        dice=dice,
        afterstate_count=len(after_states),
        gnubg_best_index=best_index,
        gnubg_best_equity=best_equity,
        gnubg_hint_move=hint_move,
        gnubg_hint_equity=hint_equity,
        model_afterstate_index=index,
        model_equity=model_equity,
        equity_loss=best_equity - model_equity,
        model_value=values[index],
        exact_match=index == best_index,
        notes=notes,
    )


def measure(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    plies: int = DEFAULT_PLIES,
    limit: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    progress: bool = True,
    criterion: str = "policy",
) -> tuple[list[PositionResult], list[str]]:
    """Kullanilabilir tüm vakalar için ER olcumunu calistirir."""
    usable, skipped = split_cases(cases)
    if limit is not None:
        usable = usable[:max(limit, 0)]

    session = GnubgSession(gnubg, plies=plies, timeout=timeout)
    scorer = OnnxScorer(model_path)

    results: list[PositionResult] = []
    for i, case in enumerate(usable, start=1):
        if progress:
            print("[%d/%d] %s" % (i, len(usable), case.get("name", "?")), file=sys.stderr)
        results.append(measure_position(session, scorer, case, plies=plies, criterion=criterion))
    return results, skipped


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def summarize(results: Sequence[PositionResult]) -> dict[str, float]:
    """Ortalama/medyan/maksimum ER ve eslesme oranı."""
    if not results:
        return {
            "count": 0,
            "mean": 0.0,
            "median": 0.0,
            "max": 0.0,
            "exactMatchRate": 0.0,
            "meanAbs": 0.0,
        }

    losses = sorted(r.equity_loss for r in results)
    count = len(losses)
    mean = sum(losses) / count
    if count % 2 == 1:
        median = losses[count // 2]
    else:
        median = (losses[count // 2 - 1] + losses[count // 2]) / 2.0
    exact = sum(1 for r in results if r.exact_match)
    return {
        "count": float(count),
        "mean": mean,
        "median": median,
        "max": losses[-1],
        "exactMatchRate": exact / count,
        "meanAbs": sum(abs(x) for x in losses) / count,
    }


def build_markdown(
    results: Sequence[PositionResult],
    skipped: Sequence[str],
    *,
    model_path: Path,
    gnubg_path: Path,
    gnubg_ver: str,
    plies: int,
    total_cases: int,
    criterion: str = "policy",
) -> str:
    """Ölçüm sonucunu Markdown raporuna cevirir."""
    stats = summarize(results)
    lines: list[str] = []

    lines.append("# GNU Backgammon equity kaybı (ER) ölçümü")
    lines.append("")
    lines.append("Faz 4 v3 Bölüm 9 (Aşama D) kabul kriteri: referans pozisyonlarda pozisyon")
    lines.append("başına equity kaybı ölçümü. Değerler **gerçek gnubg çağrılarından** üretilmiştir;")
    lines.append("hiçbir sayı elle yazılmamıştır.")
    lines.append("")
    lines.append("| Alan | Değer |")
    lines.append("| --- | --- |")
    lines.append("| Model | `%s` |" % model_path.as_posix())
    lines.append("| gnubg | `%s` |" % gnubg_path.as_posix())
    lines.append("| gnubg sürümü | %s |" % (gnubg_ver or "bilinmiyor"))
    lines.append("| gnubg değerlendirme | %d-ply, cubeless, money game |" % plies)
    lines.append("| Hamle seçimi | %s |" % CRITERION_LABELS.get(criterion, criterion))
    lines.append("| Referans vaka | %d (kullanılabilir %d) |" % (total_cases, len(results)))
    lines.append("| Dışarıda kalan | %s |" % (", ".join("`%s`" % s for s in skipped) if skipped else "yok"))
    lines.append("")

    lines.append("## Yöntem")
    lines.append("")
    lines.append("1. Pozisyon `set board simple` ile gnubg'ye yüklenir. gnubg geçersiz tahtayı")
    lines.append("   sessizce reddettiği için `show pipcount` çıktısı Python'da hesaplanan pip")
    lines.append("   sayılarıyla karşılaştırılır; uyuşmazsa vaka atılır.")
    lines.append("2. Modelin `afterStates` listesi 221 elemanlı vektöre çevrilip ONNX modeline")
    lines.append("   verilir; `argmax` modelin hamlesini verir (`--criterion %s`)." % criterion)
    lines.append("3. **Tüm** afterstate'ler tek bir gnubg sürecinde, sıra rakibe verilerek ve")
    lines.append("   %d-ply cubeless `eval` ile değerlendirilir; işaret çevrilerek hamleyi yapanın" % plies)
    lines.append("   equity'si bulunur.")
    lines.append("4. `E_best = max(afterstate equity'leri)`, `E_model = modelin seçtiği afterstate`.")
    lines.append("5. `ER = E_best - E_model` (pozitif = model kaybı).")
    lines.append("")
    lines.append("`E_best` ve `E_model` **aynı değerlendiriciyle** (aynı ply, aynı cubeless mod)")
    lines.append("üretildiği için ER tutarlıdır. gnubg'nin kendi `hint` sıralaması yalnızca")
    lines.append("bilgi amaçlı kaydedilir: gnubg-cli'de `hint` her zaman 0-ply çalışır")
    lines.append("(`set evaluation chequerplay evaluation plies` sadece `eval`'i etkiler).")
    lines.append("")
    lines.append("Tahta dönüşümü: gnubg'de **X = Siyah** (24->1 oynar, evi 1-6) ve **O = Beyaz**")
    lines.append("olduğu için `simple[0] = -board[25]`, `simple[i] = -board[i]`, `simple[25] = board[0]`.")
    lines.append("Başlangıç pozisyonu `4HPwATDgc/ABMA` position ID'sini ve 167/167 pip verir.")
    lines.append("")

    lines.append("## Özet")
    lines.append("")
    lines.append("| Metrik | Değer |")
    lines.append("| --- | --- |")
    lines.append("| Pozisyon | %d |" % int(stats["count"]))
    lines.append("| Ortalama ER | %.4f |" % stats["mean"])
    lines.append("| Medyan ER | %.4f |" % stats["median"])
    lines.append("| Maksimum ER | %.4f |" % stats["max"])
    lines.append("| gnubg ile aynı hamle | %.1f%% |" % (100.0 * stats["exactMatchRate"]))
    lines.append("")

    lines.append("## Pozisyon bazında")
    lines.append("")
    lines.append("| # | Pozisyon | Zar | Aday | gnubg en iyi # | E_best | E_model | ER | Aynı |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(results, start=1):
        dice = "%d-%d" % (r.dice[0], r.dice[1])
        lines.append(
            "| %d | `%s` | %s | %d | %d | %+.4f | %+.4f | %+.4f | %s |"
            % (
                i,
                r.name,
                dice,
                r.afterstate_count,
                r.gnubg_best_index,
                r.gnubg_best_equity,
                r.model_equity,
                r.equity_loss,
                "evet" if r.exact_match else "hayır",
            )
        )
    lines.append("")

    lines.append("## Notlar ve sınırlamalar")
    lines.append("")
    lines.append("- gnubg değerlendirmesi **cubeless money game** ve %d-ply'dir; küp kararları" % plies)
    lines.append("  ölçüme dahil değildir.")
    lines.append("- Hamle seçimi **0-ply**'dir (arama yok). C#'taki `BackgammonSearch` 1-ply")
    lines.append("  arama yaptığı için gerçek oyun gücü bu ölçümden daha iyi olabilir; yani ER")
    lines.append("  bir **üst sınır** olarak okunmalıdır.")
    lines.append("- gnubg `hint` listesi budanır (varsayılan 10 hamle) ve **0-ply**'dir; bu yüzden")
    lines.append("  ER referansı için kullanılmaz, yalnızca `gnubgHintMove` alanında saklanır.")
    lines.append("- 15/15 taş içermeyen veya `afterStates` listesi boş olan el yapımı referans")
    lines.append("  vakaları ölçüm dışıdır; adları yukarıda listelenmiştir.")
    lines.append("")
    return "\n".join(lines)


def write_json(
    path: Path,
    results: Sequence[PositionResult],
    skipped: Sequence[str],
    *,
    model_path: Path,
    gnubg_path: Path,
    gnubg_ver: str,
    plies: int,
    total_cases: int,
    criterion: str = "policy",
) -> None:
    """Olcumu JSON olarak yazar."""
    stats = summarize(results)
    payload = {
        "generator": "ml/gnubg_er.py",
        "model": model_path.as_posix(),
        "gnubg": gnubg_path.as_posix(),
        "gnubgVersion": gnubg_ver,
        "plies": plies,
        "criterion": criterion,
        "cubeful": False,
        "totalCases": total_cases,
        "measuredCases": len(results),
        "skippedCases": list(skipped),
        "summary": {
            "count": int(stats["count"]),
            "meanEquityLoss": round(stats["mean"], 6),
            "medianEquityLoss": round(stats["median"], 6),
            "maxEquityLoss": round(stats["max"], 6),
            "exactMatchRate": round(stats["exactMatchRate"], 6),
        },
        "positions": [r.to_dict() for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GNU Backgammon ile referans pozisyonlarda equity kaybı (ER) ölçümü."
    )
    parser.add_argument("--model", required=True, type=Path, help="ONNX model yolu")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="referans pozisyon dosyasi")
    parser.add_argument("--gnubg", type=Path, default=None, help="gnubg-cli yolu (otomatik kesif için boş)")
    parser.add_argument("--plies", type=int, default=DEFAULT_PLIES, help="gnubg değerlendirme derinligi")
    parser.add_argument("--limit", type=int, default=None, help="ilk N kullanılabilir vaka")
    parser.add_argument(
        "--criterion",
        choices=CRITERIA,
        default="policy",
        help="hamle seçimi: policy (C# ile aynı), value veya pip (referans tabani)",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="gnubg cagrisi zaman aşımı (sn)")
    parser.add_argument("--out", type=Path, default=None, help="Markdown rapor yolu")
    parser.add_argument("--json", type=Path, default=None, help="JSON cikti yolu")
    parser.add_argument("--quiet", action="store_true", help="ilerleme ciktisini kapat")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    gnubg = find_gnubg(args.gnubg)
    if gnubg is None:
        print(
            "HATA: gnubg-cli bulunamadi. Kurun veya --gnubg / GNUBG_CLI ile yol verin.\n"
            "      Uydurma değer uretilmedi.",
            file=sys.stderr,
        )
        return 2

    if not args.model.is_file():
        print("HATA: model bulunamadi: %s" % args.model, file=sys.stderr)
        return 2

    cases = load_cases(args.cases)
    version = gnubg_version(gnubg)

    results, skipped = measure(
        args.model,
        cases,
        gnubg=gnubg,
        plies=args.plies,
        limit=args.limit,
        timeout=args.timeout,
        progress=not args.quiet,
        criterion=args.criterion,
    )

    stats = summarize(results)
    print(
        "gnubg %s | %s | %d pozisyon | ortalama ER %.4f | medyan %.4f | maksimum %.4f | eslesme %.1f%%"
        % (
            version or "(surum okunamadi)",
            args.criterion,
            int(stats["count"]),
            stats["mean"],
            stats["median"],
            stats["max"],
            100.0 * stats["exactMatchRate"],
        )
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        markdown = build_markdown(
            results,
            skipped,
            model_path=args.model,
            gnubg_path=gnubg,
            gnubg_ver=version,
            plies=args.plies,
            total_cases=len(cases),
            criterion=args.criterion,
        )
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
        print("Markdown: %s" % args.out)

    if args.json:
        write_json(
            args.json,
            results,
            skipped,
            model_path=args.model,
            gnubg_path=gnubg,
            gnubg_ver=version,
            plies=args.plies,
            total_cases=len(cases),
            criterion=args.criterion,
        )
        print("JSON: %s" % args.json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
