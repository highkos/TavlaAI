"""Faz 7-R Asama R-C: **kup karari ER'si** (F7-72).

Butun ER olcumleri kupsuzdu. Dunya sampiyonu seviyesi hamle secimi kadar kup
kararini da gerektirir; bu modul kup kararini **ayri** bir olcum olarak ele alir.

Tanim
-----
Bir pozisyonda gnubg'nin ``eval`` ciktisi uc **cubeful** equity verir::

    Cubeful equities:
    1. No double           +0,216
    2. Double, pass        +1,000  (+0,784)
    3. Double, take        -0,001  (-0,216)
    Proper cube action: No double, beaver (21,6%)

Bizim danismanin karari iki degerden birini secer:

* **ciftleme** -> ``noDouble``
* **ciftle**   -> rakip kendi equity'sini maksimize eder, yani bizimkini
  **minimize** eder: ``min(doublePass, doubleTake)``

En iyi erisilebilir deger ``max(noDouble, min(doublePass, doubleTake))``.
**Kup ER'si** = ``en iyi - bizim``. Yani kup karari, hamle seciminden bagimsiz
olarak, *kup equity kaybi* cinsinden olculur.

``max(uc equity)`` **yanlistir**: ``doublePass = +1,000`` her zaman en yuksek
sayidir ama rakip reddetmek zorunda degildir. Yukaridaki ornekte gnubg
"No double, beaver" der; ``max`` alsaydik "ciftle" derdik ve 0,784 equity
kaybederdik.

Neden gnubg'nin cubeful equity'leri referans?
---------------------------------------------
Kendi cubeful equity'mizi kendi modelimizle hesaplamak dairesel olurdu
(modelin kup degerlendirmesi zaten olculen sey). gnubg'nin uclu tablosu
**dis** bir referanstir; bizim kararimiz yalnizca *hangi satiri sectigimizi*
belirler. Bu, hamle ER'si olcumunun kup karsiligidir.

Kapsam
------
* Para oyunu (``matchLength = 0``) ve iki mac uzunlugu (5 ve 9).
* Crawford ve post-Crawford baglamlari.
* Kup sahipligi: merkez (0), bizde (+1), rakipte (-1).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gnubg_er  # noqa: E402

CUBE_ER_VERSION = 1
CUBE_ER_PATH = "ml/artifacts/cube_er.json"
CUBE_CORPUS_PATH = "ml/artifacts/cube_corpus.json"
CUBE_DECISIONS_PATH = "ml/artifacts/cube_decisions.json"

BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261120

#: Karar eylemleri. "double" tek eylemdir; kabul/red **rakip** kararidir.
ACTION_NO_DOUBLE = "no-double"
ACTION_DOUBLE = "double"
ACTIONS = (ACTION_NO_DOUBLE, ACTION_DOUBLE)

ACTION_LABELS = {
    ACTION_NO_DOUBLE: "Ciftleme yok",
    ACTION_DOUBLE: "Ciftle",
}

#: Mac baglamlari: ``(matchLength, whiteScore, blackScore)``. ``0`` = para oyunu.
#:
#: F7-73: ilk surumde dorduncu baglam ``(5, 4, 1)`` idi; bu bir **Crawford**
#: oyunudur ve orada kup yoktur, yani 150 vaka sifir bilgiyle olcume giriyordu.
#: Yerine Crawford olmayan 3-away/4-away baglami konuldu. Crawford ayri bir
#: dogrulama senaryosudur (``CRAWFORD_CONTEXT``), ER'ye girmez.
MATCH_CONTEXTS = (
    (0, 0, 0),
    (5, 0, 0),
    (5, 2, 1),
    (9, 0, 0),
)

#: Crawford oyunu: kup teklif edilemez, danisman "ciftleme" dememelidir.
CRAWFORD_CONTEXT = (5, 4, 1)

#: Kup sahipligi: merkez, bizde. Rakip kup sahibiyken **biz teklif edemeyiz**
#: (``BackgammonEngine.CanOffer`` false), yani o vakalar karar uretmez; olcum
#: disinda tutulur (F7-73).
CUBE_OWNERS = (0, 1)

#: Kup ER'si icin hedef esik (Faz 7 §13.1'in kup karsiligi).
CUBE_ER_TARGET = 0.02

#: Gereken n icin kullanilan minimum fark.
POWER_DELTAS = (0.01, 0.02)

#: sigma icin muhafazakar ust sinir carpani (n >= 30 icin pratik ust sinir).
SIGMA_UPPER_FACTOR = 1.25

_NUMBER = r"[+-]?\d+(?:[.,]\d+)?"
_CUBELESS_RE = re.compile(r"(\d)-ply cubeless equity\s+(" + _NUMBER + r")")
# gnubg, kup zaten bizdeyken "No redouble / Redouble, pass / Redouble, take"
# yazar. F7-73: ilk surum yalnizca "No double / Double, ..." taniiyordu ve
# redouble vakalari olcumu tamamen durduruyordu (Kural 6 geregi dogru davranis).
# F7-73: gnubg cubeful satirlari **siralar**, sabit numaralamaz. En iyi eylem
# "Double, take" ise cikti "1. Double, take / 2. Double, pass / 3. No double"
# olur. Ilk surum 1/2/3 numaralarina gore eslestiriyordu ve bu vakalarda
# olcumu durduruyordu. Artik etikete gore eslestirilir.
_NO_DOUBLE_RE = re.compile(r"No (?:re)?double\s+(" + _NUMBER + r")", re.IGNORECASE)
_DOUBLE_PASS_RE = re.compile(r"(?:Re)?double,\s*pass\s+(" + _NUMBER + r")", re.IGNORECASE)
_DOUBLE_TAKE_RE = re.compile(r"(?:Re)?double,\s*take\s+(" + _NUMBER + r")", re.IGNORECASE)
_PROPER_RE = re.compile(r"Proper cube action:\s*(.+)")


class CubeErError(RuntimeError):
    """Kup ER'si olcumu beklenen ciktiyi uretmedi."""


def parse_number(text: str) -> float:
    """gnubg'nin virgullu ondaligini float'a cevirir."""
    return float(text.replace(",", "."))


def normalize_action(text: str) -> dict:
    """``Proper cube action`` metnini ayristirir.

    Donen sozluk: ``{"action", "take", "beaver", "beaverPct"}``.

    * ``action``: ``no-double`` veya ``double``
    * ``take``: ``True`` (kabul) / ``False`` (red) / ``None`` (ciftleme yok)
    * Beaver, teklif edenin **ciftlememesi** anlamina gelir (rakip kupu ikiye
      katlar); bu yuzden ``action = no-double``.
    """
    lowered = text.lower()
    beaver = "beaver" in lowered
    pct = None
    match = re.search(r"\((" + _NUMBER + r")\s*%\)", text)
    if match:
        pct = parse_number(match.group(1))

    # gnubg'nin gordulen tum "Proper cube action" bicimleri:
    #   No double / No redouble
    #   Too good to double, pass / Too good to redouble, pass
    #   Double, pass / Redouble, pass
    #   Double, take / Redouble, take
    #   ... , beaver (teklif eden ciftlemez, rakip kupu ikiye katlar)
    # F7-73: "Too good to (re)double, pass" ilk surumde taninmiyordu.
    if lowered.startswith("no double") or lowered.startswith("no redouble"):
        return {"action": ACTION_NO_DOUBLE, "take": None, "beaver": beaver, "beaverPct": pct}
    if lowered.startswith("too good to"):
        return {"action": ACTION_NO_DOUBLE, "take": None, "beaver": beaver, "beaverPct": pct}
    if beaver:
        return {"action": ACTION_NO_DOUBLE, "take": None, "beaver": True, "beaverPct": pct}
    if lowered.startswith("double, pass") or lowered.startswith("redouble, pass"):
        return {"action": ACTION_DOUBLE, "take": False, "beaver": beaver, "beaverPct": pct}
    if lowered.startswith("double, take") or lowered.startswith("redouble, take"):
        return {"action": ACTION_DOUBLE, "take": True, "beaver": beaver, "beaverPct": pct}
    raise CubeErError("bilinmeyen kup eylemi: %r" % text)


def parse_cube_analysis(text: str) -> dict:
    """``eval`` ciktisindaki ``Cube analysis`` blogunu ayristirir.

    Blok yoksa ``CubeErError`` atar (sessiz geri donus yok - Kural 6).
    """
    if "Cube analysis" not in text:
        raise CubeErError("ciktida 'Cube analysis' blogu yok")

    block = text.split("Cube analysis", 1)[1]

    # "Proper cube action" satiri da "Double, take" / "No double" icerir; bu
    # yuzden equity satirlari yalnizca ondan **onceki** parcalarda aranir.
    proper = _PROPER_RE.search(block)
    if not proper:
        raise CubeErError("'Proper cube action' satiri yok")
    equities = block[: proper.start()]

    no_double = _NO_DOUBLE_RE.search(equities)
    double_pass = _DOUBLE_PASS_RE.search(equities)
    double_take = _DOUBLE_TAKE_RE.search(equities)
    if not (no_double and double_pass and double_take):
        raise CubeErError("cubeful equity satirlari eksik")

    proper_text = proper.group(1).strip()
    parsed = normalize_action(proper_text)
    cubeless = _CUBELESS_RE.search(block)

    return {
        "cubelessEquity": parse_number(cubeless.group(2)) if cubeless else None,
        "noDouble": parse_number(no_double.group(1)),
        "doublePass": parse_number(double_pass.group(1)),
        "doubleTake": parse_number(double_take.group(1)),
        "properAction": proper_text,
        "action": parsed["action"],
        "take": parsed["take"],
        "beaver": parsed["beaver"],
        "beaverPct": parsed["beaverPct"],
    }


def our_action(should_double: bool) -> str:
    """Danismanin ciftleme kararini eylem adina cevirir."""
    return ACTION_DOUBLE if should_double else ACTION_NO_DOUBLE


def double_value(analysis: dict) -> float:
    """Ciftledikten sonraki equity: rakip bizim equity'mizi **minimize** eder."""
    return min(float(analysis["doublePass"]), float(analysis["doubleTake"]))


def action_value(analysis: dict, action: str) -> float:
    """Secilen eylemin cubeful equity'si."""
    if action == ACTION_NO_DOUBLE:
        return float(analysis["noDouble"])
    if action == ACTION_DOUBLE:
        return double_value(analysis)
    raise CubeErError("bilinmeyen eylem: %r" % action)


def best_value(analysis: dict) -> float:
    """Erisilebilir en iyi cubeful equity."""
    return max(float(analysis["noDouble"]), double_value(analysis))


def best_action(analysis: dict) -> str:
    """En iyi eylem (esitlikte ciftleme tercih edilir - muhafazakar degil, notr)."""
    if double_value(analysis) > float(analysis["noDouble"]):
        return ACTION_DOUBLE
    return ACTION_NO_DOUBLE


def cube_loss(analysis: dict, action: str) -> float:
    """Kup equity kaybi: ``en iyi - secilen``. Negatif cikmaz."""
    return max(0.0, best_value(analysis) - action_value(analysis, action))


# ----------------------------------------------------------------------
# gnubg kup oturumu
# ----------------------------------------------------------------------


class CubeSession:
    """``gnubg-cli``'yi **kup acik** ve **cubeful** modda calistirir.

    ``gnubg_er.GnubgSession`` kupu kapatir (``set cube use off``); kup olcumu
    icin tam tersi gerekir. Bu yuzden ayri bir ince sarmalayici kullanilir.
    """

    def __init__(self, exe: Path, *, plies: int = 2, timeout: int = 120) -> None:
        self.exe = Path(exe)
        self.plies = int(plies)
        self.timeout = int(timeout)

    def run(self, commands: Iterable[str]) -> str:
        script = "\n".join(list(commands) + ["quit"]) + "\n"
        try:
            proc = subprocess.run(
                [str(self.exe), "-t"],
                input=script.encode("ascii", "replace"),
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
            raise CubeErError("gnubg calistirilamadi: %s" % exc) from exc
        out = (proc.stdout or b"").decode("utf-8", "replace")
        err = (proc.stderr or b"").decode("utf-8", "replace")
        return out + err

    def _preamble(self, case: dict) -> list[str]:
        match_length = int(case.get("matchLength", 0) or 0)
        commands = [
            "set evaluation chequerplay evaluation plies %d" % self.plies,
            "set evaluation chequerplay evaluation cubeful on",
            "set evaluation cubedecision evaluation plies %d" % self.plies,
            "set evaluation cubedecision evaluation cubeful on",
        ]
        if match_length > 0:
            commands.append("new match %d" % match_length)
            commands.append(
                "set score %d %d"
                % (int(case.get("whiteScore", 0)), int(case.get("blackScore", 0)))
            )
            if case.get("isCrawfordGame"):
                commands.append("set crawford")
        else:
            commands.append("new game")
        commands.append("set cube use on")
        return commands

    def analyse(self, case: dict) -> tuple[dict, str]:
        """Tek pozisyonun kup analizini doner."""
        commands = self._preamble(case)
        commands.extend(
            gnubg_er.GnubgSession(Path(self.exe)).load_board(case["board"], int(case["turn"]))
        )
        commands.append("set cube value %d" % int(case.get("cubeValue", 1) or 1))
        owner = int(case.get("cubeOwner", 0) or 0)
        if owner == 0:
            commands.append("set cube centre")
        elif owner > 0:
            commands.append("set cube owner 0")
        else:
            commands.append("set cube owner 1")
        commands.append("eval")
        text = self.run(commands)
        return parse_cube_analysis(text), text


# ----------------------------------------------------------------------
# Korpus
# ----------------------------------------------------------------------


@dataclass
class CubeCase:
    """Tek bir kup karari pozisyonu."""

    name: str
    board: list[int]
    turn: int
    white_off: int
    black_off: int
    match_length: int
    white_score: int
    black_score: int
    is_crawford: bool
    cube_value: int
    cube_owner: int
    phase: str = "contact"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "board": list(self.board),
            "turn": int(self.turn),
            "whiteOff": int(self.white_off),
            "blackOff": int(self.black_off),
            "matchLength": int(self.match_length),
            "whiteScore": int(self.white_score),
            "blackScore": int(self.black_score),
            "isCrawfordGame": bool(self.is_crawford),
            "cubeValue": int(self.cube_value),
            "cubeOwner": int(self.cube_owner),
            # "phase" adi C# tarafinda GamePhase ile cakisiyor; ayri anahtar.
            "phaseClass": self.phase,
        }


def build_cube_corpus(
    positions: Sequence[dict],
    *,
    contexts: Sequence[tuple[int, int, int]] = MATCH_CONTEXTS,
    owners: Sequence[int] = CUBE_OWNERS,
    limit: int | None = None,
) -> list[CubeCase]:
    """Pozisyonlari mac baglamlari ve kup sahiplikleriyle caprazlar.

    Ayni tahta farkli mac skorlarinda **farkli** kup karari uretir; bu yuzden
    caprazlama, kup ER'sinin mac-farkindalikli olup olmadigini olcer.
    """
    cases: list[CubeCase] = []
    for position in positions:
        turn = int(position["turn"])
        for match_length, white_score, black_score in contexts:
            for owner in owners:
                if limit is not None and len(cases) >= limit:
                    return cases
                # F7-73: `owner` mutlak degil **goreli** okunur. `1` = "kup
                # bizde", `-1` = "rakipte", `0` = merkez. Mutlak yazildiginda
                # sira -1 olan pozisyonlarda kup rakipte kaliyor, danisman
                # teklif edemiyor ve vaka sifir bilgiyle olcume giriyordu.
                resolved_owner = 0 if owner == 0 else (turn if owner > 0 else -turn)
                is_crawford = (
                    match_length > 0
                    and max(white_score, black_score) == match_length - 1
                    and white_score != black_score
                )
                cases.append(
                    CubeCase(
                        name="%s|m%d|%d-%d|o%d"
                        % (
                            position.get("name", "pos"),
                            match_length,
                            white_score,
                            black_score,
                            owner,
                        ),
                        board=list(position["board"]),
                        turn=int(position["turn"]),
                        white_off=int(position.get("whiteOff", 0)),
                        black_off=int(position.get("blackOff", 0)),
                        match_length=match_length,
                        white_score=white_score,
                        black_score=black_score,
                        is_crawford=is_crawford,
                        cube_value=1,
                        cube_owner=resolved_owner,
                        phase=position.get("phase", "contact"),
                    )
                )
    return cases


def save_cube_corpus(cases: Sequence[CubeCase], path: str | Path = CUBE_CORPUS_PATH) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CUBE_ER_VERSION,
        "count": len(cases),
        "cases": [c.to_dict() for c in cases],
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_cube_corpus(path: str | Path = CUBE_CORPUS_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["cases"]


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


@dataclass
class CubeMeasurement:
    """Tek bir pozisyonun kup olcumu."""

    name: str
    match_length: int
    cube_owner: int
    turn: int
    is_crawford: bool
    gnubg_action: str
    our_action: str
    gnubg_take: bool | None
    our_take: bool
    loss: float
    cubeless_equity: float | None
    no_double: float
    double_pass: float
    double_take: float
    agree: bool
    take_agree: bool | None
    phase: str = "contact"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "matchLength": self.match_length,
            "cubeOwner": self.cube_owner,
            "turn": self.turn,
            "isCrawford": self.is_crawford,
            "gnubgAction": self.gnubg_action,
            "ourAction": self.our_action,
            "gnubgTake": self.gnubg_take,
            "ourTake": self.our_take,
            "loss": self.loss,
            "cubelessEquity": self.cubeless_equity,
            "noDouble": self.no_double,
            "doublePass": self.double_pass,
            "doubleTake": self.double_take,
            "agree": self.agree,
            "takeAgree": self.take_agree,
            "phase": self.phase,
        }


def _bootstrap_ci(values: Sequence[float], *, resamples: int, seed: int) -> tuple[float, float]:
    """Ortalamanin bootstrap %95 GA'si (yuzdelik yontem)."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    low = means[int(0.025 * (resamples - 1))]
    high = means[int(0.975 * (resamples - 1))]
    return (low, high)


def _bucket(measurements: Sequence[CubeMeasurement], key_fn) -> dict[str, dict]:
    buckets: dict[str, dict] = {}
    for m in measurements:
        key = key_fn(m)
        bucket = buckets.setdefault(key, {"count": 0, "lossSum": 0.0, "agree": 0})
        bucket["count"] += 1
        bucket["lossSum"] += m.loss
        bucket["agree"] += 1 if m.agree else 0
    for bucket in buckets.values():
        bucket["meanLoss"] = bucket["lossSum"] / bucket["count"]
        bucket["agreeRate"] = bucket["agree"] / bucket["count"]
        del bucket["lossSum"]
    return buckets


def summarize_cube(
    measurements: Sequence[CubeMeasurement],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Kup ER'sini ozetler: ortalama, GA, eylem uyumu, karisiklik matrisi."""
    if not measurements:
        raise CubeErError("olcum yok")

    losses = [m.loss for m in measurements]
    n = len(losses)
    mean = sum(losses) / n
    variance = sum((x - mean) ** 2 for x in losses) / (n - 1) if n > 1 else 0.0
    sigma = math.sqrt(variance)
    low, high = _bootstrap_ci(losses, resamples=resamples, seed=seed)

    agree = sum(1 for m in measurements if m.agree)
    confusion: dict[str, dict[str, int]] = {a: {b: 0 for b in ACTIONS} for a in ACTIONS}
    for m in measurements:
        confusion[m.gnubg_action][m.our_action] += 1

    take_pairs = [m for m in measurements if m.take_agree is not None]
    take_agree = sum(1 for m in take_pairs if m.take_agree)

    return {
        "count": n,
        "mean": mean,
        "sigma": sigma,
        "standardError": sigma / math.sqrt(n) if n else float("nan"),
        "ciLow": low,
        "ciHigh": high,
        "agreeCount": agree,
        "agreeRate": agree / n,
        "takeCount": len(take_pairs),
        "takeAgreeCount": take_agree,
        "takeAgreeRate": (take_agree / len(take_pairs)) if take_pairs else None,
        "confusion": confusion,
        "byContext": _bucket(
            measurements, lambda m: "money" if m.match_length == 0 else "match%d" % m.match_length
        ),
        # F7-73: sahiplik **teklif edene gore** okunur. Mutlak isaretle
        # karsilastirmak, sira -1 olan pozisyonlarda "kup bizde" vakalarini
        # "rakipte" kovasina atiyordu.
        "byOwner": _bucket(
            measurements,
            lambda m: "centre"
            if m.cube_owner == 0
            else ("ours" if m.cube_owner == m.turn else "theirs"),
        ),
        "bootstrapResamples": int(resamples),
        "bootstrapSeed": int(seed),
    }


def power_rows(summary: dict, deltas: Sequence[float] = POWER_DELTAS) -> list[dict]:
    """Gereken n: **sigma'nin ust guven sinirindan** (Kural 4).

    ``sigma`` nokta tahmininden hesaplamak kazananin laneti (winner's curse)
    tasir; bu yuzden ``sigma`` icin de bir ust sinir kullanilir.
    """
    n = int(summary["count"])
    sigma = float(summary["sigma"])
    sigma_high = sigma * SIGMA_UPPER_FACTOR
    rows = []
    for delta in deltas:
        if delta <= 0:
            raise CubeErError("delta pozitif olmali")
        required = int(math.ceil((1.645 * sigma_high / delta) ** 2))
        rows.append(
            {
                "delta": float(delta),
                "sigmaHigh": sigma_high,
                "requiredN": required,
                "currentN": n,
                "sufficient": n >= required,
            }
        )
    return rows


def measure_cube(
    cases: Sequence[dict],
    decisions: Sequence[dict],
    *,
    session: CubeSession,
    progress: bool = False,
) -> list[CubeMeasurement]:
    """Her pozisyon icin gnubg kup analizi ile bizim kararimizi karsilastirir."""
    if len(cases) != len(decisions):
        raise CubeErError(
            "vaka ve karar sayisi uyusmuyor: %d vs %d" % (len(cases), len(decisions))
        )

    results: list[CubeMeasurement] = []
    for index, (case, decision) in enumerate(zip(cases, decisions)):
        analysis, _text = session.analyse(case)
        ours = our_action(bool(decision["shouldDouble"]))
        gnubg_action = analysis["action"]
        our_take = bool(decision["shouldTake"])
        gnubg_take = analysis["take"]
        take_agree = None if gnubg_take is None else (our_take == gnubg_take)
        results.append(
            CubeMeasurement(
                name=case.get("name", "case%d" % index),
                match_length=int(case.get("matchLength", 0) or 0),
                cube_owner=int(case.get("cubeOwner", 0) or 0),
                turn=int(case.get("turn", 1) or 1),
                is_crawford=bool(case.get("isCrawfordGame", False)),
                gnubg_action=gnubg_action,
                our_action=ours,
                gnubg_take=gnubg_take,
                our_take=our_take,
                loss=cube_loss(analysis, ours),
                cubeless_equity=analysis["cubelessEquity"],
                no_double=float(analysis["noDouble"]),
                double_pass=float(analysis["doublePass"]),
                double_take=float(analysis["doubleTake"]),
                agree=ours == gnubg_action,
                take_agree=take_agree,
                phase=case.get("phaseClass", "contact"),
            )
        )
        if progress and (index + 1) % 25 == 0:
            print("  %d/%d" % (index + 1, len(cases)), flush=True)
    return results


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 4) -> str:
    """Proje gelenegi: Turkce ondalik virgul (PHASES.md ile ayni)."""
    if value is None:
        return "-"
    return (("%." + str(digits) + "f") % float(value)).replace(".", ",")


def build_markdown(report: dict) -> str:
    """Kup ER'si raporunu Markdown olarak uretir."""
    summary = report["summary"]
    lines: list[str] = []
    lines.append("# Kup karari ER'si")
    lines.append("")
    lines.append("**Tanim.** gnubg `eval` uc *cubeful* equity verir (ciftleme /")
    lines.append("ciftle+red / ciftle+kabul). Bizim danisman iki eylemden birini secer:")
    lines.append("ciftleme -> `noDouble`; ciftle -> `min(doublePass, doubleTake)`")
    lines.append("(rakip bizim equity'mizi minimize eder). **Kup ER'si** =")
    lines.append("`max(noDouble, min(doublePass, doubleTake)) - secilen`.")
    lines.append("")
    lines.append("**Referans sozlesmesi.** gnubg `eval`, %d-ply, cubeful on," % report["plies"])
    lines.append("kup acik; `Cubeful equities` blogu ve `Proper cube action` satiri.")
    lines.append("")
    lines.append("## Ozet")
    lines.append("")
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| Pozisyon | %d |" % summary["count"])
    lines.append("| **Kup ER'si (ortalama)** | **%s** |" % _fmt(summary["mean"]))
    lines.append("| sigma | %s |" % _fmt(summary["sigma"]))
    lines.append("| Standart hata | %s |" % _fmt(summary["standardError"]))
    lines.append("| %%95 GA | [%s; %s] |" % (_fmt(summary["ciLow"]), _fmt(summary["ciHigh"])))
    lines.append(
        "| Ciftleme uyumu | %d/%d (%s) |"
        % (summary["agreeCount"], summary["count"], _fmt(summary["agreeRate"]))
    )
    if summary["takeCount"]:
        lines.append(
            "| Kabul/red uyumu | %d/%d (%s) |"
            % (
                summary["takeAgreeCount"],
                summary["takeCount"],
                _fmt(summary["takeAgreeRate"]),
            )
        )
    lines.append("| Hedef | < %s |" % _fmt(CUBE_ER_TARGET))
    lines.append("")
    lines.append("## Karisiklik matrisi (ciftleme)")
    lines.append("")
    lines.append("| gnubg \\ biz | " + " | ".join(ACTION_LABELS[a] for a in ACTIONS) + " |")
    lines.append("|---|" + "---|" * len(ACTIONS))
    for gnubg_action in ACTIONS:
        row = summary["confusion"][gnubg_action]
        lines.append(
            "| **%s** | " % ACTION_LABELS[gnubg_action]
            + " | ".join(str(row[a]) for a in ACTIONS)
            + " |"
        )
    lines.append("")
    lines.append("## Mac baglamina gore")
    lines.append("")
    lines.append("| Baglam | n | Kup ER'si | Uyum |")
    lines.append("|---|---|---|---|")
    for key in sorted(summary["byContext"]):
        bucket = summary["byContext"][key]
        lines.append(
            "| `%s` | %d | %s | %s |"
            % (key, bucket["count"], _fmt(bucket["meanLoss"]), _fmt(bucket["agreeRate"]))
        )
    lines.append("")
    lines.append("## Kup sahipligine gore")
    lines.append("")
    lines.append("| Sahip | n | Kup ER'si | Uyum |")
    lines.append("|---|---|---|---|")
    for key in ("centre", "ours", "theirs"):
        bucket = summary["byOwner"].get(key)
        if bucket is None:
            continue
        lines.append(
            "| `%s` | %d | %s | %s |"
            % (key, bucket["count"], _fmt(bucket["meanLoss"]), _fmt(bucket["agreeRate"]))
        )
    lines.append("")
    lines.append("## Gereken n (sigma ust sinirindan)")
    lines.append("")
    lines.append("| Fark | sigma (ust) | Gereken n | Mevcut n | Yeterli |")
    lines.append("|---|---|---|---|---|")
    for row in report["power"]:
        lines.append(
            "| %s | %s | %d | %d | %s |"
            % (
                _fmt(row["delta"], 2),
                _fmt(row["sigmaHigh"]),
                row["requiredN"],
                row["currentN"],
                "evet" if row["sufficient"] else "**hayir**",
            )
        )
    lines.append("")
    lines.append("## Kapsam notu")
    lines.append("")
    lines.append("Bu olcum **kup kararini** olcer, hamle secimini degil. Hamle ER'si")
    lines.append("`ml/er_paths.py` ile ayri raporlanir. Ikisi toplanmaz; dunya")
    lines.append("sampiyonu iddiasi **ikisini birden** gerektirir.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kup karari ER'si (Faz 7-R R-C)")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-corpus", help="kup korpusu uret")
    build.add_argument("--positions", default="ml/artifacts/reference_corpus_v2.json")
    build.add_argument("--out", default=CUBE_CORPUS_PATH)
    build.add_argument("--limit", type=int, default=None)
    build.add_argument("--stride", type=int, default=1)

    measure = sub.add_parser("measure", help="kup ER'sini olc")
    measure.add_argument("--corpus", default=CUBE_CORPUS_PATH)
    measure.add_argument("--decisions", default=CUBE_DECISIONS_PATH)
    measure.add_argument("--gnubg", default=None)
    measure.add_argument("--plies", type=int, default=2)
    measure.add_argument("--out", default=CUBE_ER_PATH)
    measure.add_argument("--markdown", default=None)
    measure.add_argument("--limit", type=int, default=None)
    measure.add_argument("--progress", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "build-corpus":
        corpus = json.loads(Path(args.positions).read_text(encoding="utf-8"))
        positions = corpus["cases"]
        if args.stride and args.stride > 1:
            # Korpus fazlara gore gruplanmis; duz bir --limit yalnizca contact
            # secip ER'yi tek faza indirger. Stride tum fazlardan ornek alir.
            positions = positions[:: args.stride]
        cases = build_cube_corpus(positions, limit=args.limit)
        path = save_cube_corpus(cases, args.out)
        print("kup korpusu: %d vaka -> %s" % (len(cases), path))
        return 0

    if args.command == "measure":
        cases = load_cube_corpus(args.corpus)
        if args.limit is not None:
            cases = cases[: args.limit]
        decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))["cases"]
        if args.limit is not None:
            decisions = decisions[: args.limit]
        exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()
        session = CubeSession(exe, plies=args.plies)
        measurements = measure_cube(cases, decisions, session=session, progress=args.progress)
        summary = summarize_cube(measurements)
        report = {
            "version": CUBE_ER_VERSION,
            "plies": int(args.plies),
            "gnubg": str(exe),
            "summary": summary,
            "power": power_rows(summary),
            "cases": [m.to_dict() for m in measurements],
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.markdown:
            Path(args.markdown).write_text(build_markdown(report), encoding="utf-8")
        print(
            "kup ER'si: %s (n=%d, GA [%s; %s], uyum %s)"
            % (
                _fmt(summary["mean"]),
                summary["count"],
                _fmt(summary["ciLow"]),
                _fmt(summary["ciHigh"]),
                _fmt(summary["agreeRate"]),
            )
        )
        return 0

    raise CubeErError("bilinmeyen komut: %r" % args.command)


if __name__ == "__main__":
    raise SystemExit(main())
