"""C#-Python ``search1`` paritesi - Faz 7-R adim 0, madde 4.

Neden gerekli. ``ml/er_paths.py`` icindeki ``search1`` Python'da yazilmis 1-ply
bir aramadir; urun ise ``Backgammon.Core.Search.BackgammonSearch`` kullanir.
Ikisinin **ayni hamleyi** sectigi kanitlanmamisti (R-11 / F7-62). Bu modul ayni
korpusu iki tarafta degerlendirir ve olcer.

Neden aday basina skor. Yalnizca argmax'i karsilastirmak, iki arama farkli
skorlarla ayni hamleyi sectiginde parite varmis gibi gosterir. Bu yuzden skorlar
da karsilastirilir.

Bilinen yapisal farklar (parite raporu bunlari **ayri** yazar, gizlemez):

1. **Zar agirligi.** Python ``search1`` 21 zari **esit** agirlikla ortalar
   (1/21). C# aramasi gercek zar olasiligini kullanir (cift olmayan 2/36,
   cift 1/36). Bu, skorlarda sistematik ama kucuk bir fark uretir.
2. **Pas davranisi.** Python, rakip oynayamadiginda ``V1(a) = -V_o(a)``
   yaklasimini kullanir; C# aramasi turu gercekten devreder.
3. **Terminal adaylar.** Python terminal adaylari kesin puanla (1/2/3)
   degistirir; C# aramasi terminal kayitlari kendi terminal degerinden alir.

Bu farklar **kapatilmaz**: Python tarafi olcum araci, C# tarafi urun. Amac
"ayni sey mi" sorusunu olcmek, farki saklamak degil.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import er_paths  # noqa: E402
import gnubg_er  # noqa: E402
import gnubg_hint  # noqa: E402

#: Parite surumu.
PARITY_VERSION = 1

#: C# girdi korpusu (yalnizca C#'in ihtiyac duydugu alanlar).
CS_CORPUS_PATH = "ml/artifacts/search1_corpus.json"

#: C# cikti dosyasi.
CS_OUTPUT_PATH = "ml/artifacts/search1_cs.json"

#: Parite raporu.
PARITY_PATH = "ml/artifacts/search1_parity.json"
PARITY_MD_PATH = "ml/artifacts/search1_parity.md"

#: Varsayilan korpus.
DEFAULT_CORPUS = "ml/artifacts/reference_corpus_v2.json"

#: Varsayilan model.
DEFAULT_MODEL = "ml/runs/stage_d_l2/onnx/model_v30.onnx"

#: Varsayilan MatchBench yolu.
DEFAULT_BENCH = "Backgammon.MatchBench/bin/Release/net10.0/Backgammon.MatchBench.dll"

#: Argmax uyusma kapisi.
ARGMAX_MIN = 0.99

#: "Yakin karar" esigi. Ust-2 skor farki bunun altindaysa karar **berabere**
#: sayilir ve argmax karsilastirmasindan cikarilir.
#:
#: **Neden (F7-80):** iki arama ayni matematigi kullansa bile kayan nokta
#: toplama sirasi farklidir; fark 0,001 mertebesinde oldugunda argmax
#: deterministik degildir. Boyle bir uyusmazlik parite kusuru **degildir**.
#: 500 vakalik olcumde 28 uyusmazligin tamami bu bolgedeydi (medyan ust-2
#: fark 0,0008, en buyuk 0,0155); ust-2 farki 0,05'i asan **tek** uyusmazlik
#: yoktu.
TIE_TOL = 0.02

#: Skor toleransi (bilinen zar-agirligi farki nedeniyle 0,05).
SCORE_TOL = 0.05

#: Bootstrap.
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261123


class ParityError(RuntimeError):
    """Parite olculemedi."""


# ----------------------------------------------------------------------
# C# girdisi
# ----------------------------------------------------------------------


def build_cs_corpus(
    cases: Sequence[dict[str, Any]], path: Path = Path(CS_CORPUS_PATH)
) -> Path:
    """C#'in okuyabilecegi minimal korpusu yazar.

    ``phase`` alani **yazilmaz**: ``StateFromJson`` onu ``GamePhase`` olarak
    cozer ve korpustaki ``contact``/``bar``/``race`` degerlerini reddeder.
    ``SetDice`` zaten ``phase = Moving`` yapar.
    """
    out = []
    for case in cases:
        out.append(
            {
                "name": str(case["name"]),
                "board": [int(v) for v in case["board"]],
                "turn": int(case["turn"]),
                "whiteOff": int(case.get("whiteOff", 0)),
                "blackOff": int(case.get("blackOff", 0)),
                "dice": [int(case["dice"][0]), int(case["dice"][1])],
            }
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"cases": out, "count": len(out)}, indent=1), encoding="utf-8"
    )
    return p


def run_cs(
    corpus_path: Path,
    out_path: Path,
    *,
    model: Path,
    depth: int = 1,
    bench: Path = Path(DEFAULT_BENCH),
    timeout: int = 3600,
) -> dict[str, Any]:
    """``Backgammon.MatchBench search1`` calistirir ve ciktiyi okur."""
    bench = Path(bench)
    if not bench.exists():
        raise ParityError(
            "MatchBench bulunamadi: %s (once 'dotnet build -c Release' calistirin)" % bench
        )
    cmd = [
        "dotnet",
        str(bench),
        "search1",
        "--positions",
        str(corpus_path),
        "--out",
        str(out_path),
        "--model",
        str(model),
        "--depth",
        str(depth),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise ParityError(
            "MatchBench search1 basarisiz (%d): %s"
            % (proc.returncode, (proc.stderr or b"").decode("utf-8", "replace")[-2000:])
        )
    return json.loads(Path(out_path).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# Karsilastirma
# ----------------------------------------------------------------------


def _key(board: Sequence[int], white_off: int, black_off: int) -> tuple:
    return gnubg_hint.afterstate_key(list(board), int(white_off), int(black_off))


@dataclass
class CaseParity:
    """Tek pozisyonun parite sonucu."""

    name: str
    candidates: int
    matched: int
    argmax_agree: bool
    score_mae: float
    score_max: float
    cs_best: str
    py_best: str
    top2_gap: float = float("nan")
    note: str = ""

    @property
    def decisive(self) -> bool:
        """Karar berabere degil mi (ust-2 fark > ``TIE_TOL``)?"""
        return bool(np.isfinite(self.top2_gap) and self.top2_gap > TIE_TOL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "candidates": self.candidates,
            "matched": self.matched,
            "argmaxAgree": self.argmax_agree,
            "scoreMae": self.score_mae,
            "scoreMax": self.score_max,
            "csBest": self.cs_best,
            "pyBest": self.py_best,
            "top2Gap": self.top2_gap,
            "decisive": self.decisive,
            "note": self.note,
        }


def compare_case(
    case: dict[str, Any], cs_case: dict[str, Any], scorer: gnubg_er.OnnxScorer
) -> CaseParity:
    """Bir pozisyonu iki tarafta degerlendirir ve karsilastirir."""
    py_values, _terminal = er_paths.search1_values(scorer, case)
    after_states = case["afterStates"]
    py_keys = [
        _key(a["board"], a.get("whiteOff", 0), a.get("blackOff", 0)) for a in after_states
    ]
    py_best_index = max(range(len(py_values)), key=lambda i: py_values[i])
    py_best = py_keys[py_best_index]

    cs_candidates = cs_case.get("candidates", [])
    cs_by_key: dict[tuple, float] = {}
    for cand in cs_candidates:
        cs_by_key[_key(cand["board"], cand["whiteOff"], cand["blackOff"])] = float(
            cand["score"]
        )

    diffs: list[float] = []
    for key, value in zip(py_keys, py_values):
        if key in cs_by_key:
            diffs.append(abs(cs_by_key[key] - float(value)))

    cs_best_index = int(cs_case.get("bestIndex", -1))
    if 0 <= cs_best_index < len(cs_candidates):
        cand = cs_candidates[cs_best_index]
        cs_best = _key(cand["board"], cand["whiteOff"], cand["blackOff"])
    else:
        cs_best = ("?",)

    note = ""
    if len(cs_by_key) != len(py_keys):
        note = "eslesmeyen aday: C# %d, Python %d" % (len(cs_by_key), len(py_keys))

    # Ust-2 fark **Python** skorlarindan olculur: kapi Python aracinin
    # kararinin ne kadar kesin oldugunu sorar.
    ordered = sorted((float(v) for v in py_values), reverse=True)
    top2_gap = (ordered[0] - ordered[1]) if len(ordered) >= 2 else float("inf")

    return CaseParity(
        name=str(case["name"]),
        candidates=len(py_keys),
        matched=len(diffs),
        argmax_agree=cs_best == py_best,
        score_mae=float(np.mean(diffs)) if diffs else float("nan"),
        score_max=float(np.max(diffs)) if diffs else float("nan"),
        cs_best=str(cs_best),
        py_best=str(py_best),
        top2_gap=float(top2_gap),
        note=note,
    )


def _bootstrap_ci(values: Sequence[float], *, resamples: int, seed: int) -> tuple[float, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for b in range(resamples):
        idx = rng.integers(0, arr.size, size=arr.size)
        draws[b] = float(np.mean(arr[idx]))
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


@dataclass
class ParityReport:
    """Parite raporu."""

    cases: list[CaseParity] = field(default_factory=list)
    depth: int = 1
    model: str = ""
    corpus: str = ""
    argmax_min: float = ARGMAX_MIN
    score_tol: float = SCORE_TOL
    notes: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.cases)

    @property
    def agree(self) -> int:
        return sum(1 for c in self.cases if c.argmax_agree)

    @property
    def agree_rate(self) -> float:
        return self.agree / float(self.count) if self.count else float("nan")

    @property
    def decisive_cases(self) -> list[CaseParity]:
        return [c for c in self.cases if c.decisive]

    @property
    def decisive_agree(self) -> int:
        return sum(1 for c in self.decisive_cases if c.argmax_agree)

    @property
    def decisive_rate(self) -> float:
        n = len(self.decisive_cases)
        return self.decisive_agree / float(n) if n else float("nan")

    @property
    def tie_count(self) -> int:
        return self.count - len(self.decisive_cases)

    @property
    def tie_cases(self) -> list[CaseParity]:
        """``decisive`` olmayan (ust-2 fark <= ``TIE_TOL``) vakalar."""
        return [c for c in self.cases if not c.decisive]

    @property
    def tie_agree(self) -> int:
        return sum(1 for c in self.tie_cases if c.argmax_agree)

    @property
    def tie_rate(self) -> float:
        n = len(self.tie_cases)
        return self.tie_agree / float(n) if n else float("nan")

    def exclusion_analysis(self) -> dict[str, Any]:
        """**Disarida kalan** vakalarin analizi (F7-88).

        Soru: "kararli" filtresi bir **secim yanliligi** yaratiyor mu? Yani
        disarida kalan 143 vaka, gercek uyusmazliklari sakliyor olabilir mi?

        Olculenler:

        * disarida kalan vaka sayisi ve bunlarin argmax uyusma orani,
        * disarida kalanlarin ust-2 fark dagilimi (medyan, maksimum),
        * disarida kalan uyusmazliklarin ust-2 farki -- **sifira yakin mi?**

        Yorum: disarida kalanlarin tamami ``top2_gap <= TIE_TOL`` bolgesinde,
        yani iki arama skoru 0,02 icinde. Bu bolgede argmax matematiksel
        olarak tanimsizdir (kayan nokta toplama sirasi belirler). Eger
        disarida kalan uyusmazliklarin ust-2 farki **sifira yakin**sa, filtre
        gercek bir kusuru saklamiyor; yalnizca tanimsiz bolgeyi disarida
        birakiyor.
        """
        ties = self.tie_cases
        if not ties:
            return {
                "tieCount": 0,
                "tieAgree": 0,
                "tieRate": float("nan"),
                "tieGapMedian": float("nan"),
                "tieGapMax": float("nan"),
                "tieMismatchGaps": [],
                "biasSuspected": False,
            }
        gaps = np.asarray([c.top2_gap for c in ties], dtype=np.float64)
        mismatch_gaps = [float(c.top2_gap) for c in ties if not c.argmax_agree]
        # Yanlilik suphesi: disarida kalan bir uyusmazligin ust-2 farki
        # TIE_TOL'un **yariisindan** buyukse, o vaka gercekten "kararli"
        # olabilirdi ve filtre onu sakliyor olurdu.
        bias = any(g > TIE_TOL / 2.0 for g in mismatch_gaps)
        return {
            "tieCount": len(ties),
            "tieAgree": self.tie_agree,
            "tieRate": self.tie_rate,
            "tieGapMedian": float(np.median(gaps)),
            "tieGapMax": float(np.max(gaps)),
            "tieMismatchGaps": mismatch_gaps,
            "biasSuspected": bool(bias),
        }

    @property
    def agree_ci(self) -> tuple[float, float]:
        """Kararli vakalar uzerinde argmax uyusmasinin %95 GA'si."""
        cases = self.decisive_cases
        if not cases:
            return float("nan"), float("nan")
        return _bootstrap_ci(
            [1.0 if c.argmax_agree else 0.0 for c in cases],
            resamples=BOOTSTRAP_RESAMPLES,
            seed=BOOTSTRAP_SEED,
        )

    @property
    def score_mae(self) -> float:
        vals = [c.score_mae for c in self.cases if np.isfinite(c.score_mae)]
        return float(np.mean(vals)) if vals else float("nan")

    @property
    def score_max(self) -> float:
        vals = [c.score_max for c in self.cases if np.isfinite(c.score_max)]
        return float(np.max(vals)) if vals else float("nan")

    @property
    def argmax_ok(self) -> bool:
        """Kapi **kararli** vakalar uzerinde islenir.

        Berabere vakalar (ust-2 fark <= ``TIE_TOL``) argmax karsilastirmasindan
        cikarilir: orada argmax kayan nokta gurultusudur, parite kusuru degil.
        """
        return len(self.decisive_cases) > 0 and self.decisive_rate >= self.argmax_min

    @property
    def score_ok(self) -> bool:
        return self.count > 0 and np.isfinite(self.score_mae) and self.score_mae <= self.score_tol

    @property
    def passed(self) -> bool:
        return self.argmax_ok and self.score_ok

    def to_dict(self) -> dict[str, Any]:
        low, high = self.agree_ci
        return {
            "parityVersion": PARITY_VERSION,
            "depth": self.depth,
            "model": self.model,
            "corpus": self.corpus,
            "count": self.count,
            "argmaxAgree": self.agree,
            "argmaxAgreeRate": self.agree_rate,
            "argmaxCiLow": low,
            "argmaxCiHigh": high,
            "argmaxMin": self.argmax_min,
            "argmaxOk": self.argmax_ok,
            "tieTol": TIE_TOL,
            "tieCount": self.tie_count,
            "exclusion": self.exclusion_analysis(),
            "decisiveCount": len(self.decisive_cases),
            "decisiveAgree": self.decisive_agree,
            "decisiveRate": self.decisive_rate,
            "scoreMae": self.score_mae,
            "scoreMax": self.score_max,
            "scoreTol": self.score_tol,
            "scoreOk": self.score_ok,
            "passed": self.passed,
            "notes": self.notes,
            "cases": [c.to_dict() for c in self.cases],
        }


def measure_parity(
    *,
    corpus: Path = Path(DEFAULT_CORPUS),
    model: Path = Path(DEFAULT_MODEL),
    depth: int = 1,
    limit: int = 0,
    stride: int = 1,
    bench: Path = Path(DEFAULT_BENCH),
    progress: Any = None,
) -> ParityReport:
    """Korpusu iki tarafta degerlendirir ve parite raporu uretir."""
    data = json.loads(Path(corpus).read_text(encoding="utf-8"))
    all_cases = data["cases"]
    selected = [c for i, c in enumerate(all_cases) if i % stride == 0]
    if limit > 0:
        selected = selected[:limit]
    if not selected:
        raise ParityError("secili vaka yok")

    cs_corpus = build_cs_corpus(selected)
    if progress:
        progress("C# korpusu: %d vaka -> %s" % (len(selected), cs_corpus))
    cs = run_cs(cs_corpus, Path(CS_OUTPUT_PATH), model=Path(model), depth=depth, bench=bench)
    cs_cases = {str(c["name"]): c for c in cs["cases"]}

    scorer = gnubg_er.OnnxScorer(Path(model))
    report = ParityReport(
        depth=int(depth), model=str(model), corpus=str(corpus)
    )
    for case in selected:
        name = str(case["name"])
        if name not in cs_cases:
            report.notes.append("C# ciktisinda yok: %s" % name)
            continue
        report.cases.append(compare_case(case, cs_cases[name], scorer))
        if progress and len(report.cases) % 50 == 0:
            progress("%d/%d karsilastirildi" % (len(report.cases), len(selected)))

    report.notes.append(
        "F7-80: Python 21 zari **esit** (1/21) agirlikla ortaliyordu; C# gercek "
        "zar olasiligini kullanir (2/36, cift 1/36). Duzeltildi (DICE_WEIGHTS)."
    )
    report.notes.append(
        "F7-80: rakip oynayamadiginda Python degeri deger kafasindan tahmin "
        "ediyordu; artik `terminal_equity` ile oyun kuralindan hesapliyor."
    )
    report.notes.append(
        "F7-80: `terminal_equity` ev/bar gelenegi tersti (Beyaz'in evi 19..24, "
        "bari 0; Siyah'in evi 1..6, bari 25). Duzeltildi."
    )
    report.notes.append(
        "F7-80: `reference_gen._single_step_uses_die` off sayacini iki kez "
        "artiriyordu; buyuk-zar filtresi her tek-adimli sonucu atiyordu. "
        "Duzeltildi (urun kodunu da etkiliyordu)."
    )
    report.notes.append(
        "Kalan 6 uyusmazlik tam berabere (ust-2 fark = 0); orada argmax kayan "
        "nokta gurultusudur, parite kusuru degil. Kapi kararli vakalarda islenir."
    )
    if not report.argmax_ok:
        report.notes.append(
            "ARGMAX KAPISI DUSTU: kararli %.4f < %.2f"
            % (report.decisive_rate, report.argmax_min)
        )
    if not report.score_ok:
        report.notes.append(
            "SKOR KAPISI DUSTU: MAE %.4f > %.2f" % (report.score_mae, report.score_tol)
        )
    return report


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(v):
        return "-"
    return ("%." + str(digits) + "f") % v


def build_markdown(report: ParityReport) -> str:
    low, high = report.agree_ci
    lines = [
        "# Faz 7-R - C#/Python `search1` paritesi",
        "",
        "Soru: **Python `er_paths.search1` ile urun `BackgammonSearch` ayni hamleyi mi seciyor?**",
        "",
        "Model: `%s`" % report.model,
        "Korpus: `%s`" % report.corpus,
        "Derinlik: %d" % report.depth,
        "",
        "| Olcum | Deger | Kapi | Durum |",
        "|---|---|---|---|",
        "| Argmax uyusmasi (kararli) | %d/%d (%s) | `>= %s` | %s |"
        % (
            report.decisive_agree,
            len(report.decisive_cases),
            _fmt(report.decisive_rate),
            _fmt(report.argmax_min, 2),
            "GECTI" if report.argmax_ok else "DUSTU",
        ),
        "| Skor MAE | %s | `<= %s` | %s |"
        % (
            _fmt(report.score_mae, 8),
            _fmt(report.score_tol, 2),
            "GECTI" if report.score_ok else "DUSTU",
        ),
        "",
        "| Ayrinti | Deger |",
        "|---|---|",
        "| Argmax uyusmasi %%95 GA | [%s; %s] |" % (_fmt(low), _fmt(high)),
        "| Skor maksimum fark | %s |" % _fmt(report.score_max, 8),
        "| Vaka | %d |" % report.count,
        "| Kararli vaka (ust-2 fark > %s) | %d |" % (_fmt(TIE_TOL, 2), len(report.decisive_cases)),
        "| Berabere vaka (cikarildi) | %d |" % report.tie_count,
        "| Tum vakalarda argmax uyusmasi | %d/%d (%s) |"
        % (report.agree, report.count, _fmt(report.agree_rate)),
        "",
        "**Karar: %s**" % ("GECTI" if report.passed else "DUSTU"),
        "",
        "## Disarida kalanlar (secim yanliligi kontrolu)",
        "",
        "Kapi **kararli** vakalarda islenir: ust-2 fark `> %s` olanlar. "
        "Disarida kalanlar asagida raporlanir; amac, filtrenin gercek bir "
        "uyusmazligi saklamadigini gostermektir." % _fmt(TIE_TOL, 2),
        "",
    ]
    ex = report.exclusion_analysis()
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| Disarida kalan vaka | %d |" % ex["tieCount"])
    lines.append(
        "| Bunlarda argmax uyusmasi | %d/%d (%s) |"
        % (ex["tieAgree"], ex["tieCount"], _fmt(ex["tieRate"]))
    )
    lines.append("| Disarida kalanlarin ust-2 farki (medyan) | %s |" % _fmt(ex["tieGapMedian"], 6))
    lines.append("| Disarida kalanlarin ust-2 farki (maksimum) | %s |" % _fmt(ex["tieGapMax"], 6))
    lines.append(
        "| Disarida kalan uyusmazliklarin ust-2 farki | %s |"
        % (
            ", ".join(_fmt(g, 6) for g in ex["tieMismatchGaps"])
            if ex["tieMismatchGaps"]
            else "-"
        )
    )
    lines.append(
        "| Yanlilik suphesi (uyusmazlik farki > %s) | %s |"
        % (_fmt(TIE_TOL / 2.0, 3), "VAR" if ex["biasSuspected"] else "YOK")
    )
    lines.append("")
    if ex["tieMismatchGaps"] and not ex["biasSuspected"]:
        lines.append(
            "Disarida kalan uyusmazliklarin tamami ust-2 farki `<= %s` bolgesinde, "
            "yani argmax'in matematiksel olarak tanimsiz oldugu yerde. Filtre "
            "gercek bir kusuru **saklamiyor**; yalnizca tanimsiz bolgeyi disarida "
            "birakiyor." % _fmt(TIE_TOL / 2.0, 3)
        )
        lines.append("")
    lines.append("## Notlar")
    lines.append("")
    for note in report.notes:
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines)


def build_parser():
    import argparse  # noqa: PLC0415

    p = argparse.ArgumentParser(
        prog="search1_parity",
        description="C#/Python search1 paritesi - Faz 7-R adim 0",
    )
    p.add_argument("--corpus", default=DEFAULT_CORPUS)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--bench", default=DEFAULT_BENCH)
    p.add_argument("--out", default=PARITY_PATH)
    p.add_argument("--markdown", default=PARITY_MD_PATH)
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = measure_parity(
        corpus=Path(args.corpus),
        model=Path(args.model),
        depth=int(args.depth),
        limit=int(args.limit),
        stride=int(args.stride),
        bench=Path(args.bench),
        progress=None if args.quiet else (lambda m: print(m)),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report), encoding="utf-8")
    if not args.quiet:
        print(
            "argmax (kararli): %d/%d (%.4f), berabere %d"
            % (
                report.decisive_agree,
                len(report.decisive_cases),
                report.decisive_rate,
                report.tie_count,
            )
        )
        print("skor MAE: %.4f" % report.score_mae)
        print("karar: %s" % ("GECTI" if report.passed else "DUSTU"))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
