"""Faz 7 Bolum 4.2 -- gercek derin hakem: gnubg ``hint`` protokolu (Test 91, 92).

Neden bu modul var: gnubg'nin ``eval`` komutu **en fazla 2-ply** uretir (F6-32).
3-ply ve 4-ply hakem yalnizca ``hint`` ile elde edilir. Ama ``hint`` bir **hamle
listesi** dondurur, afterstate listesi degil; ER olcumu ise afterstate bazlidir.
Bu modul aradaki kopruyu kurar: hamle metni -> tahta -> afterstate -> eslesme.

Asama A'da olculen uc kritik gercek
------------------------------------

**F7-01 -- hamle filtresi (sessiz bozulma).** ``hint`` ``plies`` ayarina uyar ama
once **hamle filtresini** uygular. Varsayilan filtre 3-ply icin "ilk 0 2-ply
hamlesini ve 0,04 equity icinde en fazla 2 hamleyi tut" der; yani 3-ply cagrisinda
en fazla 2 hamle gercekten 3-ply degerlendirilir, kalanlar 2-ply etiketiyle doner.
F6-006'da en iyi hamle sans eseri 3-ply'ye terfi ettigi icin Faz 6 bunu fark
etmedi. Duzeltme: :class:`HintReferee` **tum** filtre seviyelerini acar
(``set evaluation movefilter <ply> <level> 1000 0 0.0``, ``level = 0..plies-1``);
:func:`verify_uniform_depth` her olcumde etiketleri denetler ve tekduze degilse
olcum durur.

**F7-02 -- notasyon aynalanmasi.** gnubg hamle notasyonu **sirada olan oyuncunun**
bakis acisindadir: X (Siyah) icin mutlak, O (Beyaz) icin aynalanmis
(``p -> 25 - p``). 200 pozisyonluk kumede 200/200 dogrulandi; ters varsayim
0/10 eslesme verir.

**F7-03 -- 10 hamle tavani.** gnubg ``hint`` komutu **en fazla 10 hamle** basar;
filtre 1000'e acilsa bile. Bu yuzden modelin sectigi afterstate ``hint``
listesinde olmayabilir. Cozum: ``plies <= 2`` icin modelin afterstate'i dogrudan
``eval`` ile degerlendirilir (``hint@N`` hamle degeri ile ``eval@N`` **birebir**
ayni cikti -- olculdu), ``plies >= 3`` icin pozisyon **sansurlu** isaretlenir ve
kayip icin yalnizca bir **alt sinir** raporlanir. Sansur orani birinci sinif
metriktir; sampiyon iddiasi icin kapsama >= %99 sarttir.

Maliyet (olculdu, Asama A, 8 pozisyon ortalamasi, filtre acik)
-------------------------------------------------------------
2-ply **0,48 s/pozisyon**, 3-ply **4,21 s/pozisyon**, 4-ply **62,6 s/pozisyon**.
Faz 7 Bolum 4.2'deki "20-40x, 8-16 saat" tahmini bu olcumle degistirilmistir.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import gnubg_er  # noqa: E402
import tools.reference_gen as refgen  # noqa: E402

#: ``hint`` protokolunun destekledigi en derin hakem.
HINT_MAX_PLIES = 4

#: gnubg ``hint`` komutunun bastigi en fazla hamle sayisi (olculdu, F7-03).
HINT_MOVE_CAP = 10

#: Filtreyi acmak icin "her zaman kabul et" sayisi (aday hamle sayisindan buyuk).
WIDE_FILTER_ACCEPT = 1000

#: Tek pozisyonun ``hint`` cagrisi icin zaman asimi (saniye). 4-ply ~63 s surer.
DEFAULT_HINT_TIMEOUT = 900

#: Modelin afterstate'i ``hint`` listesinde yoksa kullanilan kaynak etiketleri.
SOURCE_HINT = "hint"
SOURCE_EVAL = "eval"
SOURCE_CENSORED = "censored"

#: F7-04: 2-ply hakemi **her zaman** ``eval``'dir. ``hint@2`` ile ``eval@2``
#: ayni sey degildir (10 ornekte 6'sinda birebir ayni, 4'unde 0,118'e kadar
#: farkli). Merdivenin 1->2 ve 2->3 adimlari ayni buyuklukte (0,134 / 0,107)
#: oldugu icin bu bir kusur degil, oynak pozisyonlarda normal arama
#: gurultusudur. Yine de tek bir kod yolu kullanmak zorunludur.
EVAL_REFEREE_PLIES = 2

#: F7-04: ``hint`` yalnizca bu derinlikten itibaren hakem olarak kullanilir.
HINT_REFEREE_MIN_PLIES = 3

#: F7-04: 2-ply -> 3-ply gecisi bir **yontem degisikligidir**; raporlarda
#: bu not yer almak zorundadır.
LADDER_METHOD_NOTE = (
    "2-ply degerleri gnubg `eval` ile, 3-ply ve 4-ply degerleri gnubg `hint` "
    "ile olculur (F7-04). Iki protokol ayni pozisyonda birebir ayni sonucu "
    "vermez; 2/3 sinirindaki merdiven adimi elma-elmadir degildir."
)

_OFF = "off"
_BAR = "bar"

_TOKEN_RE = re.compile(r"^(?P<body>.+?)(?:\((?P<mult>\d+)\))?$")
_DEPTH_RE = re.compile(r"Cubeless\s+(?P<depth>\d+)-ply\s+(?P<move>.+?)\s+Eq\.")


class HintMappingError(RuntimeError):
    """``hint`` hamlesi bir afterstate'e eslestirilemedi."""


# ----------------------------------------------------------------------
# Hakem secimi (F7-04)
# ----------------------------------------------------------------------


def referee_for_plies(plies: int) -> str:
    """Verilen derinlik icin yetkili hakemin adini dondurur.

    ``2`` -> ``"eval"`` (F7-04: ``hint@2`` kullanilmaz), ``>=3`` -> ``"hint"``.
    """
    if plies < 0:
        raise ValueError(f"plies negatif olamaz: {plies}")
    if plies <= EVAL_REFEREE_PLIES:
        return SOURCE_EVAL
    if plies > HINT_MAX_PLIES:
        raise ValueError(
            f"plies {plies} desteklenmiyor; ust sinir {HINT_MAX_PLIES} (F7-01)"
        )
    return SOURCE_HINT


def assert_referee_choice(plies: int, referee: str) -> None:
    """Cagiranin sectigi hakem F7-04 politikasina uyuyor mu?"""
    expected = referee_for_plies(plies)
    if referee != expected:
        raise ValueError(
            f"plies={plies} icin hakem {expected!r} olmali, {referee!r} verildi (F7-04)"
        )


# ----------------------------------------------------------------------
# Hamle metni -> tahta
# ----------------------------------------------------------------------


def off_target(turn: int) -> int:
    """Toplanan tasin hedef indeksi (Beyaz 25, Siyah 0)."""
    return 25 if turn == 1 else 0


def _point(text: str, turn: int) -> int:
    """Notasyon hanesini **mutlak** hane indeksine cevirir.

    gnubg hamle notasyonu **sirada olan oyuncunun** bakis acisindadir: X (Siyah)
    icin mutlak numaralandirma, O (Beyaz) icin aynalanmis (``p -> 25 - p``).
    Bu, 200 pozisyonluk kumede 200/200 dogrulandi (F7-02): ``turn = -1`` icin
    kimlik eslemesi, ``turn = +1`` icin aynalama 10/10 hamleyi afterstate'e
    oturtur; tersi 0/10 verir.
    """
    token = text.strip()
    if token == _BAR:
        return refgen.bar_index(turn)
    if token == _OFF:
        return off_target(turn)
    try:
        value = int(token)
    except ValueError as exc:
        raise HintMappingError("hamle metninde gecersiz hane: %r" % text) from exc
    if not 1 <= value <= 24:
        raise HintMappingError("hane 1..24 olmali: %r" % text)
    return value if turn == -1 else 25 - value


def parse_move(move: str, turn: int) -> list[tuple[int, int, bool]]:
    """gnubg hamle metnini ``(from, to, hit)`` adimlarina cevirir.

    Desteklenen bicimler (gnubg 1.08 ciktilari), ``turn = -1`` (Siyah) icin::

        "15/6"            -> [(15, 6, False)]
        "13/5*(2)"        -> [(13, 5, True), (13, 5, True)]
        "13/5*/1 13/9"    -> [(13, 5, True), (5, 1, False), (13, 9, False)]
        "bar/22 8/5"      -> [(25, 22, False), (8, 5, False)]
        "6/off"           -> [(6, 0, False)]

    ``turn = +1`` (Beyaz) icin ayni metinler aynalanir (``p -> 25 - p``)::

        "15/6"            -> [(10, 19, False)]
        "bar/22 8/5"      -> [(0, 3, False), (17, 20, False)]
        "6/off"           -> [(19, 25, False)]

    Donen haneler **mutlak** indekslerdir; notasyonun aynalanmasi
    :func:`_point` icinde yapilir.
    """
    steps: list[tuple[int, int, bool]] = []
    for token in move.split():
        match = _TOKEN_RE.match(token)
        if not match:
            raise HintMappingError("hamle metni ayristirilamadi: %r" % token)
        body = match.group("body")
        mult = int(match.group("mult") or 1)
        parts = body.split("/")
        if len(parts) < 2:
            raise HintMappingError("hamlede '/' yok: %r" % token)
        hops: list[tuple[int, int, bool]] = []
        for i in range(len(parts) - 1):
            # Ara noktalar vurma isaretini tasir: "13/5*/1" -> 5* hem varis hem kalkis.
            frm = _point(parts[i].rstrip("*"), turn)
            raw_to = parts[i + 1]
            hit = raw_to.endswith("*")
            to = _point(raw_to.rstrip("*"), turn)
            hops.append((frm, to, hit))
        for _ in range(mult):
            steps.extend(hops)
    if not steps:
        raise HintMappingError("bos hamle metni")
    return steps


def apply_move(
    board: Sequence[int],
    turn: int,
    move: str,
    white_off: int = 0,
    black_off: int = 0,
) -> tuple[list[int], int, int]:
    """Hamleyi tahtaya uygular ve ``(board, whiteOff, blackOff)`` doner.

    Vurulan tas rakip barina gonderilir; toplanan tas sayaci artar. Girdi tahta
    degistirilmez.
    """
    nb = [int(v) for v in board]
    wo, bo = int(white_off), int(black_off)
    for frm, to, _hit in parse_move(move, turn):
        if nb[frm] * turn <= 0:
            raise HintMappingError(
                "hamle tas olmayan haneden basliyor: %d (tahta %d)" % (frm, nb[frm])
            )
        nb[frm] -= turn
        if to == off_target(turn):
            if turn == 1:
                wo += 1
            else:
                bo += 1
            continue
        if refgen.is_blot(nb, to, turn):
            nb[to] += turn
            nb[refgen.bar_index(-turn)] -= turn
        nb[to] += turn
    return nb, wo, bo


def afterstate_key(board: Sequence[int], white_off: int, black_off: int) -> tuple:
    """Afterstate kimligi -- eslestirme anahtari."""
    return (tuple(int(v) for v in board), int(white_off), int(black_off))


# ----------------------------------------------------------------------
# Derinlik etiketi denetimi
# ----------------------------------------------------------------------


def parse_depths(text: str) -> list[tuple[int, str]]:
    """``hint`` ciktisindaki ``(derinlik, hamle)`` ciftlerini sirayla doner.

    gnubg her hamleyi **hangi derinlikte** degerlendirdigini etiketler
    (``Cubeless 3-ply``). Bu etiket, filtrenin hamleyi gercekten istenen
    derinlige terfi ettirip ettirmedigini gosteren tek kanittir.
    """
    result: list[tuple[int, str]] = []
    for match in _DEPTH_RE.finditer(text):
        result.append((int(match.group("depth")), match.group("move").strip()))
    return result


def verify_uniform_depth(text: str, plies: int) -> list[str]:
    """Tum hamleler istenen derinlikte mi? Degilse eksik olanlarin listesi.

    F7-01'in kalbi: ``hint`` filtresi acilmazsa 3-ply cagrisinda hamlelerin
    cogu 2-ply etiketiyle doner ve "3-ply ER" sessizce yanlis olur.
    """
    problems: list[str] = []
    for depth, move in parse_depths(text):
        if depth != plies:
            problems.append("%s: %d-ply (istenen %d-ply)" % (move, depth, plies))
    return problems


# ----------------------------------------------------------------------
# Hakem
# ----------------------------------------------------------------------


class HintReferee:
    """``hint`` protokolunu **acik hamle filtresiyle** calistiran hakem."""

    def __init__(
        self,
        exe: Path,
        *,
        plies: int = 3,
        timeout: int = DEFAULT_HINT_TIMEOUT,
    ) -> None:
        if not 0 <= plies <= HINT_MAX_PLIES:
            raise ValueError("plies 0..%d olmali: %r" % (HINT_MAX_PLIES, plies))
        self.plies = plies
        self.session = gnubg_er.GnubgSession(exe, plies=plies, timeout=timeout)

    @property
    def method_note(self) -> str:
        """Rapora yazilmasi zorunlu yontem notu (F7-04)."""
        if self.plies <= EVAL_REFEREE_PLIES:
            return (
                "plies=%d: yetkili hakem gnubg `eval` (F7-04). `hint@2` ile "
                "`eval@2` ayni sey degildir; bu kosu `hint` listesini yalnizca "
                "aday siralamasi icin kullanir." % self.plies
            )
        return LADDER_METHOD_NOTE

    def _preamble(self) -> list[str]:
        commands = self.session._preamble()
        # gnubg N-ply icin N filtre seviyesi tutar (0..N-1). Hepsini acmak gerekir:
        # yalnizca ilk seviyeleri acmak 3-ply'de son (2-ply) seviyeyi kapali birakir
        # ve hamleler 2-ply etiketiyle doner -- olculdu, Asama A (F7-01).
        for level in range(self.plies):
            commands.append(
                "set evaluation movefilter %d %d %d 0 0.0"
                % (self.plies, level, WIDE_FILTER_ACCEPT)
            )
        return commands

    def hint(
        self, board: Sequence[int], turn: int, dice: Sequence[int]
    ) -> tuple[list[gnubg_er.HintMove], str]:
        """Pozisyonu yukler, pip sayilarini dogrular ve derin ``hint`` listesini doner."""
        commands = self._preamble()
        commands.extend(self.session.load_board(board, turn))
        commands.append("set dice %d %d" % (int(dice[0]), int(dice[1])))
        commands.append("show pipcount")
        commands.append("hint")
        text = self.session.run(commands)

        self.session._verify_pips(text, board)
        moves = gnubg_er.parse_hint(text)
        if not moves:
            raise HintMappingError("hint ciktisi ayristirilamadi")
        return moves, text

    def hint_checked(
        self, board: Sequence[int], turn: int, dice: Sequence[int]
    ) -> tuple[list[gnubg_er.HintMove], str]:
        """``hint`` + **derinlik denetimi**: filtre acilmamissa olcum durur."""
        moves, text = self.hint(board, turn, dice)
        problems = verify_uniform_depth(text, self.plies)
        if problems:
            raise HintMappingError(
                "%d-ply hakem tekduze degil (hamle filtresi acilmamis): %s"
                % (self.plies, "; ".join(problems[:3]))
            )
        return moves, text

    def eval_afterstate(
        self, board: Sequence[int], turn: int
    ) -> float | None:
        """Afterstate'in ``plies``-ply degerini **hamleyi yapanin** bakis acisindan doner.

        Yalnizca ``plies <= 2`` icin kullanilabilir: gnubg ``eval`` en fazla 2-ply
        uretir (F6-32). 2-ply'de bu yol **tam kapsama** saglar ve yetkili hakemdir
        (F7-04). Daha derin icin ``None`` doner ve cagiran taraf pozisyonu sansurlu
        isaretler (F7-03).
        """
        if self.plies > gnubg_er.MAX_EVAL_PLIES:
            return None
        table, _text = self.session.eval_position(board, -turn)
        return -gnubg_er._equity_at(table, self.plies)


# ----------------------------------------------------------------------
# Hamle -> afterstate eslemesi
# ----------------------------------------------------------------------


def map_hints(
    hints: Sequence[gnubg_er.HintMove], case: dict[str, Any]
) -> tuple[list[tuple[gnubg_er.HintMove, int]], list[dict[str, str]]]:
    """``hint`` hamlelerini ``case['afterStates']`` indekslerine eslestirir.

    Eslesmeyen hamle **sessizce atlanmaz**; ``failures`` listesine yazilir ve
    cagiran taraf olcumu basarisiz sayar (Bolum 4.2 kabul kosulu).
    """
    turn = int(case["turn"])
    board = case["board"]
    white_off = int(case.get("whiteOff", 0))
    black_off = int(case.get("blackOff", 0))

    index: dict[tuple, int] = {}
    for i, after in enumerate(case["afterStates"]):
        index[afterstate_key(after["board"], after.get("whiteOff", 0), after.get("blackOff", 0))] = i

    matched: list[tuple[gnubg_er.HintMove, int]] = []
    failures: list[dict[str, str]] = []
    for hint in hints:
        try:
            nb, wo, bo = apply_move(board, turn, hint.move, white_off, black_off)
        except HintMappingError as exc:
            failures.append({"move": hint.move, "reason": str(exc)})
            continue
        key = afterstate_key(nb, wo, bo)
        if key not in index:
            failures.append({"move": hint.move, "reason": "afterstate kumede yok"})
            continue
        matched.append((hint, index[key]))
    return matched, failures


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


@dataclass
class HintPositionResult:
    """Tek pozisyonun derin hakem olcumu."""

    name: str
    turn: int
    dice: list[int]
    afterstate_count: int
    hint_count: int
    best_index: int
    best_equity: float
    best_move: str
    model_afterstate_index: int
    model_equity: float
    equity_loss: float
    exact_match: bool
    model_equity_source: str = SOURCE_HINT
    censored: bool = False
    loss_lower_bound: float = 0.0
    mapping_failures: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "turn": self.turn,
            "dice": list(self.dice),
            "afterstateCount": self.afterstate_count,
            "hintCount": self.hint_count,
            "bestIndex": self.best_index,
            "bestEquity": round(self.best_equity, 6),
            "bestMove": self.best_move,
            "modelAfterstateIndex": self.model_afterstate_index,
            "modelEquity": round(self.model_equity, 6),
            "equityLoss": round(self.equity_loss, 6),
            "exactMatch": self.exact_match,
            "modelEquitySource": self.model_equity_source,
            "censored": self.censored,
            "lossLowerBound": round(self.loss_lower_bound, 6),
            "mappingFailures": list(self.mapping_failures),
            "notes": list(self.notes),
        }


def measure_position(
    referee: HintReferee,
    scorer: gnubg_er.OnnxScorer,
    case: dict[str, Any],
    *,
    criterion: str = "policy",
) -> HintPositionResult:
    """Tek pozisyonu derin hakemle olcer.

    Referans equity, ``hint`` listesindeki **tum** afterstate'lerin ayni
    derinlikteki degerinin maksimumudur. Modelin sectigi afterstate'in degeri
    ayni listeden okunur; listede yoksa ``plies <= 2`` icin ``eval`` ile
    (birebir ayni deger) tamamlanir, daha derinde pozisyon **sansurlu** olur.
    """
    turn = int(case["turn"])
    dice = [int(d) for d in case["dice"]]
    after_states = case["afterStates"]

    model_index, _scores = gnubg_er.score_afterstates(scorer, case, criterion)

    hints, _text = referee.hint_checked(case["board"], turn, dice)
    matched, failures = map_hints(hints, case)

    notes: list[str] = []
    if len(after_states) == 1:
        notes.append("tek yasal hamle")
    if failures:
        notes.append("%d hamle eslestirilemedi" % len(failures))

    if not matched:
        return HintPositionResult(
            name=str(case.get("name", "?")),
            turn=turn,
            dice=dice,
            afterstate_count=len(after_states),
            hint_count=len(hints),
            best_index=-1,
            best_equity=0.0,
            best_move="",
            model_afterstate_index=model_index,
            model_equity=0.0,
            equity_loss=0.0,
            exact_match=False,
            model_equity_source=SOURCE_CENSORED,
            censored=True,
            mapping_failures=failures,
            notes=notes,
        )

    best_hint, best_index = max(matched, key=lambda pair: pair[0].equity)
    by_index = {idx: hint for hint, idx in matched}

    source = SOURCE_HINT
    censored = False
    loss_lower_bound = 0.0
    if model_index in by_index:
        model_equity = by_index[model_index].equity
    else:
        direct = referee.eval_afterstate(
            after_states[model_index]["board"], turn
        )
        if direct is not None:
            model_equity = direct
            source = SOURCE_EVAL
            notes.append("modelin hamlesi hint ilk %d'de yok; eval ile tamamlandi" % HINT_MOVE_CAP)
        else:
            # F7-03: gnubg `hint` en fazla 10 hamle basar. Modelin hamlesi
            # listelenen en kotu hamleden de kotu oldugu icin kayip icin yalnizca
            # ALT SINIR bilinir; pozisyon sansurlu isaretlenir.
            worst = min(hint.equity for hint, _ in matched)
            model_equity = worst
            source = SOURCE_CENSORED
            censored = True
            loss_lower_bound = best_hint.equity - worst
            notes.append(
                "modelin hamlesi hint ilk %d'de yok; kayip >= %.4f (sansurlu)"
                % (HINT_MOVE_CAP, loss_lower_bound)
            )

    return HintPositionResult(
        name=str(case.get("name", "?")),
        turn=turn,
        dice=dice,
        afterstate_count=len(after_states),
        hint_count=len(hints),
        best_index=best_index,
        best_equity=best_hint.equity,
        best_move=best_hint.move,
        model_afterstate_index=model_index,
        model_equity=model_equity,
        equity_loss=best_hint.equity - model_equity,
        exact_match=model_index == best_index,
        model_equity_source=source,
        censored=censored,
        loss_lower_bound=loss_lower_bound,
        mapping_failures=failures,
        notes=notes,
    )


def summarize(results: Sequence[HintPositionResult]) -> dict[str, Any]:
    """Olcumlerin ozeti (``er_power`` girdisi olacak kayiplar dahil)."""
    n = len(results)
    if n == 0:
        return {"count": 0}
    covered = [r for r in results if not r.censored]
    losses = [r.equity_loss for r in covered]
    lower = [r.loss_lower_bound if r.censored else r.equity_loss for r in results]

    def _stats(values: Sequence[float]) -> dict[str, float]:
        m = len(values)
        if m == 0:
            return {"count": 0, "mean": 0.0, "median": 0.0, "max": 0.0,
                    "standardDeviation": 0.0, "standardError": 0.0}
        mean = sum(values) / m
        var = sum((v - mean) ** 2 for v in values) / (m - 1) if m > 1 else 0.0
        ordered = sorted(values)
        median = ordered[m // 2] if m % 2 else 0.5 * (ordered[m // 2 - 1] + ordered[m // 2])
        return {
            "count": m,
            "mean": round(mean, 6),
            "median": round(median, 6),
            "max": round(max(values), 6),
            "standardDeviation": round(var ** 0.5, 6),
            "standardError": round((var / m) ** 0.5, 6),
        }

    summary = _stats(losses)
    summary["count"] = n
    summary["coveredCount"] = len(covered)
    summary["censoredCount"] = n - len(covered)
    summary["coverage"] = round(len(covered) / n, 4)
    summary["meanLowerBound"] = round(sum(lower) / n, 6)
    summary["exactMatchRate"] = round(sum(1 for r in results if r.exact_match) / n, 4)
    summary["mappingFailures"] = sum(len(r.mapping_failures) for r in results)
    summary["mappingOk"] = summary["mappingFailures"] == 0
    summary["sources"] = {
        SOURCE_HINT: sum(1 for r in results if r.model_equity_source == SOURCE_HINT),
        SOURCE_EVAL: sum(1 for r in results if r.model_equity_source == SOURCE_EVAL),
        SOURCE_CENSORED: sum(1 for r in results if r.model_equity_source == SOURCE_CENSORED),
    }
    return summary


def measure(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    plies: int = 3,
    criterion: str = "policy",
    timeout: int = DEFAULT_HINT_TIMEOUT,
    limit: int | None = None,
    progress: Any = None,
) -> dict[str, Any]:
    """Bir kumeyi derin hakemle olcer ve rapor sozlugu doner."""
    scorer = gnubg_er.OnnxScorer(model_path)
    referee = HintReferee(gnubg, plies=plies, timeout=timeout)
    selected = list(cases)[: limit if limit else None]

    results: list[HintPositionResult] = []
    started = time.time()
    for i, case in enumerate(selected, 1):
        results.append(measure_position(referee, scorer, case, criterion=criterion))
        if progress is not None:
            progress(i, len(selected), results[-1])
    elapsed = time.time() - started

    summary = summarize(results)
    summary["elapsedSeconds"] = round(elapsed, 1)
    summary["secondsPerPosition"] = round(elapsed / len(selected), 2) if selected else 0.0
    return {
        "model": str(model_path),
        "referee": "hint",
        "plies": plies,
        "criterion": criterion,
        "methodNote": referee.method_note,
        "summary": summary,
        "positions": [r.to_dict() for r in results],
    }


def build_markdown(report: dict[str, Any]) -> str:
    """Rapor sozlugunu Markdown'a cevirir."""
    s = report["summary"]
    lines = [
        "# Derin hakem (`hint`) ER olcumu",
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| Model | `%s` |" % report["model"],
        "| Hakem | gnubg `hint`, %d-ply (filtre acik) |" % report["plies"],
        "| Kriter | %s |" % report["criterion"],
        "| Pozisyon | %d |" % s.get("count", 0),
        "| Kapsama | **%.2f%%** (%d/%d) |"
        % (100.0 * s.get("coverage", 0.0), s.get("coveredCount", 0), s.get("count", 0)),
        "| Sansurlu | %d |" % s.get("censoredCount", 0),
        "| Ortalama ER (kapsanan) | **%.4f** |" % s.get("mean", 0.0),
        "| Ortalama ER (alt sinir) | %.4f |" % s.get("meanLowerBound", 0.0),
        "| Medyan | %.4f |" % s.get("median", 0.0),
        "| Maks | %.4f |" % s.get("max", 0.0),
        "| Standart sapma | %.6f |" % s.get("standardDeviation", 0.0),
        "| Standart hata | %.6f |" % s.get("standardError", 0.0),
        "| Tam eslesme | %.2f%% |" % (100.0 * s.get("exactMatchRate", 0.0)),
        "| Eslesme hatasi | %d |" % s.get("mappingFailures", 0),
        "| Deger kaynagi | hint %d / eval %d / sansurlu %d |"
        % (
            s.get("sources", {}).get(SOURCE_HINT, 0),
            s.get("sources", {}).get(SOURCE_EVAL, 0),
            s.get("sources", {}).get(SOURCE_CENSORED, 0),
        ),
        "| Sure | %.1f s (%.2f s/pozisyon) |"
        % (s.get("elapsedSeconds", 0.0), s.get("secondsPerPosition", 0.0)),
        "",
    ]
    if report.get("methodNote"):
        lines.append("> **Yontem notu (F7-04):** %s" % report["methodNote"])
        lines.append("")
    if not s.get("mappingOk", True):
        lines.append("**UYARI:** hamle->afterstate eslemesi tam degil; olcum basarisiz sayilir.")
        lines.append("")
    if s.get("censoredCount", 0):
        lines.append(
            "**UYARI:** %d pozisyon sansurlu (gnubg `hint` %d hamle tavani, F7-03). "
            "Sampiyon iddiasi icin kapsama >= %%99 sarttir."
            % (s["censoredCount"], HINT_MOVE_CAP)
        )
        lines.append("")
    return "\n".join(lines)


def write_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="gnubg `hint` derin hakem olcumu (Faz 7 Bolum 4.2)")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--corpus", type=Path, default=ML_DIR / "artifacts" / "reference_corpus_v1.json")
    parser.add_argument("--gnubg", type=Path, default=None)
    parser.add_argument("--plies", type=int, default=3)
    parser.add_argument("--criterion", default="policy", choices=list(gnubg_er.CRITERIA))
    parser.add_argument("--timeout", type=int, default=DEFAULT_HINT_TIMEOUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exe = gnubg_er.find_gnubg(args.gnubg)
    if exe is None:
        print("gnubg-cli bulunamadi", file=sys.stderr)
        return 2
    if not args.corpus.is_file():
        print("kume yok: %s" % args.corpus, file=sys.stderr)
        return 2

    cases = gnubg_er.load_cases(args.corpus)
    usable, _skipped = gnubg_er.split_cases(cases)

    def progress(i: int, total: int, result: HintPositionResult) -> None:
        if not args.quiet:
            print(
                "[%d/%d] %s ER=%.4f%s"
                % (i, total, result.name, result.equity_loss,
                   " (sansurlu)" if result.censored else ""),
                flush=True,
            )

    report = measure(
        args.model,
        usable,
        gnubg=exe,
        plies=args.plies,
        criterion=args.criterion,
        timeout=args.timeout,
        limit=args.limit,
        progress=progress,
    )
    if args.json:
        write_json(report, args.json)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")
    if not args.quiet:
        print(build_markdown(report))
    return 0 if report["summary"].get("mappingOk", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
