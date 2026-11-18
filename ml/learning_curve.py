"""Faz 7-R Asama R-C: ogrenme egrisi ("olcek mi pipeline mi?").

Faz 7'nin en pahali sorusu su: ER hedefin uzerindeyse, **daha cok veri** mi
gerekiyor, yoksa **hat** mi bozuk? Bu modul soruyu bir egriyle yanitlar.

Tasarim karari: ayni hat, ayni tohum, yalnizca **veri hacmi** degisir
(N, 2N, 4N, 8N). Her noktada ER uc oynanis yolu icin ayri olculur; ayrica
kalibrasyon egimi/MAE ve **in-sample** ile **held-out** kayip raporlanir.
Karar, ER'nin ``log2(veri)`` basina egiminden verilir.

Neden ``log2``? Cunku ogrenme egrisi literaturde ER ~ a - b*log(N) biciminde
modellenir; ``log2`` katsayisi "veri ikiye katlandiginda ER ne kadar duser"
diye dogrudan okunur. Egim **negatifse** veri artisi ER'yi dusuruyor demektir.

Neden bootstrap? Dort nokta ile egim tahmini cok gurultuludur. Guven araligi
**pozisyon duzeyinde** yeniden orneklenir (nokta duzeyinde degil): her
noktanin kayiplari kendi icinde yeniden orneklenir, egim yeniden hesaplanir.
Bu, "ayni dagilimdan yeni bir korpus gelseydi egim ne olurdu" sorusunu
yanitlar.

Kullanim (gercek egitim hatti ile)::

    python ml/learning_curve.py --base-positions 2000 --out ml/artifacts/learning_curve.json

Kullanim (enjekte edilebilir, testler icin)::

    report = run_curve(sizes=(100, 200, 400, 800), train_fn=..., measure_fn=...)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

#: Veri hacmi carpanlari (Faz 7-R Asama R-C, madde 4).
CURVE_MULTIPLIERS = (1, 2, 4, 8)

#: Bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261120

#: Olcekleme esigi: ER'nin log2(veri) basina dusus egimi.
#: ``pipeline_health.SCALING_SLOPE_EPSILON`` ile ayni olmali.
SCALING_SLOPE_EPSILON = 0.005

#: Raporlanan oynanis yollari (``er_paths.PLAY_PATHS`` ile ayni).
CURVE_PATHS = ("policy", "value", "search1")

#: Karar etiketleri.
DECISION_SCALES = "olcek"
DECISION_PIPELINE = "pipeline"
DECISION_UNDETERMINED = "belirsiz"
DECISION_NO_DATA = "veri-yok"


# ----------------------------------------------------------------------
# Veri yapilari
# ----------------------------------------------------------------------


@dataclass
class CurvePoint:
    """Ogrenme egrisinin tek bir noktasi.

    ``losses`` **pozisyon duzeyinde** ER kayiplaridir; bootstrap bunlari
    yeniden ornekler. ``in_sample_loss`` ve ``held_out_loss`` ayri alanlardir:
    in-sample metrikler basari sayilmaz (Kural 5).
    """

    multiplier: int
    positions: int
    losses: dict[str, list[float]] = field(default_factory=dict)
    slope: float | None = None
    mae: float | None = None
    in_sample_loss: float | None = None
    held_out_loss: float | None = None
    note: str = ""

    @property
    def means(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path, values in self.losses.items():
            if values:
                out[path] = float(np.mean(np.asarray(values, dtype=np.float64)))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "multiplier": self.multiplier,
            "positions": self.positions,
            "means": self.means,
            "counts": {p: len(v) for p, v in self.losses.items()},
            "calibrationSlope": self.slope,
            "calibrationMae": self.mae,
            "inSampleLoss": self.in_sample_loss,
            "heldOutLoss": self.held_out_loss,
            "note": self.note,
        }


@dataclass
class CurveReport:
    """Ogrenme egrisinin tamami."""

    points: list[CurvePoint] = field(default_factory=list)
    slopes: dict[str, dict[str, float]] = field(default_factory=dict)
    seed: int = 0
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    bootstrap_seed: int = BOOTSTRAP_SEED
    notes: list[str] = field(default_factory=list)

    def slope_for(self, path: str) -> float | None:
        entry = self.slopes.get(path)
        return None if entry is None else entry.get("slope")

    @property
    def decision(self) -> str:
        """``olcek`` / ``pipeline`` / ``belirsiz`` / ``veri-yok``.

        Kural 3: nokta tahmini kanit degildir. ``olcek`` demek icin egimin
        **GA alt siniri** esigin uzerinde olmalidir; ``pipeline`` demek icin
        **GA ust siniri** esigin altinda olmalidir. Aksi halde ``belirsiz``.
        """
        if not self.points or not self.slopes:
            return DECISION_NO_DATA
        entry = self.slopes.get("policy") or next(iter(self.slopes.values()))
        low = entry.get("gainCiLow")
        high = entry.get("gainCiHigh")
        if low is None or high is None:
            return DECISION_UNDETERMINED
        if float(low) >= SCALING_SLOPE_EPSILON:
            return DECISION_SCALES
        if float(high) < SCALING_SLOPE_EPSILON:
            return DECISION_PIPELINE
        return DECISION_UNDETERMINED

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [p.to_dict() for p in self.points],
            "slopes": self.slopes,
            "decision": self.decision,
            "seed": self.seed,
            "bootstrapResamples": self.bootstrap_resamples,
            "bootstrapSeed": self.bootstrap_seed,
            "scalingSlopeEpsilon": SCALING_SLOPE_EPSILON,
            "notes": self.notes,
        }

    def scaling_summary(self) -> dict[str, Any]:
        """``pipeline_health.diagnose(scaling=...)`` icin ozet."""
        entry = self.slopes.get("policy") or (next(iter(self.slopes.values())) if self.slopes else {})
        return {
            # ``slope`` burada **kazanc**tir: ER'nin log2(veri) basina DUSUSU.
            # Pozitif = veri arttikca ER iyilesiyor. Ham OLS egimi ``rawSlope``.
            "slope": entry.get("gain"),
            "ciLow": entry.get("gainCiLow"),
            "ciHigh": entry.get("gainCiHigh"),
            "rawSlope": entry.get("slope"),
            "path": entry.get("path", "policy"),
            "points": [p.positions for p in self.points],
            "decision": self.decision,
        }


# ----------------------------------------------------------------------
# Egim
# ----------------------------------------------------------------------


def _ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Tek degiskenli en kucuk kareler egimi."""
    if x.shape[0] < 2:
        return float("nan")
    xm = float(np.mean(x))
    ym = float(np.mean(y))
    denom = float(np.sum((x - xm) ** 2))
    if denom <= 0.0:
        return float("nan")
    return float(np.sum((x - xm) * (y - ym)) / denom)


def fit_log_slope(
    points: Sequence[CurvePoint],
    *,
    path: str = "policy",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float]:
    """ER'nin ``log2(veri)`` basina egimi + bootstrap %95 GA.

    Nokta tahmini OLS'tir. GA **pozisyon duzeyinde** yeniden ornekleme ile
    hesaplanir: her noktanin kayip listesi kendi icinde (yerine koyarak)
    yeniden orneklenir, ortalama alinir, egim yeniden fit edilir. Bu, nokta
    sayisinin azligindan gelen belirsizligi **degil**, korpus orneklemesinden
    gelen belirsizligi olcer - dogru olan da budur.
    """
    usable = [p for p in points if p.losses.get(path)]
    if len(usable) < 2:
        return {
            "path": path,
            "slope": float("nan"),
            "ciLow": float("nan"),
            "ciHigh": float("nan"),
            "gain": float("nan"),
            "gainCiLow": float("nan"),
            "gainCiHigh": float("nan"),
            "n": 0,
            "resamples": 0,
        }
    x = np.log2(np.asarray([p.positions for p in usable], dtype=np.float64))
    y = np.asarray([float(np.mean(p.losses[path])) for p in usable], dtype=np.float64)
    slope = _ols_slope(x, y)

    rng = np.random.default_rng(seed)
    arrays = [np.asarray(p.losses[path], dtype=np.float64) for p in usable]
    draws = np.empty(resamples, dtype=np.float64)
    for b in range(resamples):
        means = np.empty(len(arrays), dtype=np.float64)
        for k, arr in enumerate(arrays):
            idx = rng.integers(0, arr.shape[0], size=arr.shape[0])
            means[k] = float(np.mean(arr[idx]))
        draws[b] = _ols_slope(x, means)
    finite = draws[np.isfinite(draws)]
    if finite.size == 0:
        low = high = float("nan")
    else:
        low = float(np.percentile(finite, 2.5))
        high = float(np.percentile(finite, 97.5))
    return {
        "path": path,
        "slope": slope,
        "ciLow": low,
        "ciHigh": high,
        # ``gain = -slope``: ER'nin log2(veri) basina **dususu**. Karar bu
        # isaretle verilir; ham egim negatiftir (ER dusuyor).
        "gain": -slope,
        "gainCiLow": -high,
        "gainCiHigh": -low,
        "n": len(usable),
        "resamples": int(resamples),
    }


# ----------------------------------------------------------------------
# Kosum
# ----------------------------------------------------------------------

#: ``train_fn(positions, seed) -> dict`` sozlesmesi:
#:   ``{"losses": {path: [float, ...]}, "slope": float, "mae": float,
#:     "inSampleLoss": float, "heldOutLoss": float, "note": str}``
TrainFn = Callable[[int, int], dict[str, Any]]

#: ``measure_fn(model, positions) -> dict`` alternatifi; ``train_fn`` zaten
#: kayiplari donduruyorsa kullanilmaz.
MeasureFn = Callable[[Any, int], dict[str, list[float]]]


def run_curve(
    *,
    sizes: Sequence[int],
    train_fn: TrainFn,
    seed: int = 0,
    multipliers: Sequence[int] | None = None,
    resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    progress: Callable[[str], None] | None = None,
) -> CurveReport:
    """Ayni hat, ayni tohum, degisen **yalnizca** veri hacmi.

    ``sizes`` artan sirali olmalidir; her eleman bir nokta uretir. ``train_fn``
    verilen pozisyon sayisiyla egitir ve **pozisyon duzeyinde** ER kayiplarini
    dondurur. Kural 7: bu fonksiyon disinda hicbir parametre degismemelidir;
    degisiyorsa cagiran taraf bunu ``notes``a yazmalidir.
    """
    ordered = sorted(int(s) for s in sizes)
    if len(ordered) < 2:
        raise ValueError("en az iki nokta gerekli")
    if len(set(ordered)) != len(ordered):
        raise ValueError("veri hacimleri tekrar etmemeli")
    if multipliers is not None:
        mults = [int(m) for m in multipliers]
        if len(mults) != len(ordered):
            raise ValueError("multipliers ile sizes ayni uzunlukta olmali")
    else:
        base = ordered[0]
        mults = [max(1, int(round(p / base))) for p in ordered]

    report = CurveReport(
        seed=int(seed),
        bootstrap_resamples=int(resamples),
        bootstrap_seed=int(bootstrap_seed),
    )
    for k, positions in enumerate(ordered):
        if progress is not None:
            progress("nokta %d/%d: %d pozisyon" % (k + 1, len(ordered), positions))
        raw = train_fn(positions, int(seed))
        losses = {
            path: [float(v) for v in raw.get("losses", {}).get(path, [])]
            for path in CURVE_PATHS
        }
        point = CurvePoint(
            multiplier=int(mults[k]) if k < len(mults) else k + 1,
            positions=int(positions),
            losses=losses,
            slope=None if raw.get("slope") is None else float(raw["slope"]),
            mae=None if raw.get("mae") is None else float(raw["mae"]),
            in_sample_loss=(
                None if raw.get("inSampleLoss") is None else float(raw["inSampleLoss"])
            ),
            held_out_loss=(
                None if raw.get("heldOutLoss") is None else float(raw["heldOutLoss"])
            ),
            note=str(raw.get("note", "")),
        )
        report.points.append(point)

    for path in CURVE_PATHS:
        if any(p.losses.get(path) for p in report.points):
            report.slopes[path] = fit_log_slope(
                report.points, path=path, resamples=resamples, seed=bootstrap_seed
            )
    if not report.slopes:
        report.notes.append("hicbir noktada kayip yok: egim hesaplanamadi")
    return report


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and not math.isfinite(value):
        return "-"
    return ("%." + str(digits) + "f") % value


DECISION_TEXT = {
    DECISION_SCALES: (
        "Egim esigin uzerinde: veri ikiye katlandiginda ER olculebilir bicimde "
        "dusuyor. **Olcek buyutmek dogru kaldiractir.**"
    ),
    DECISION_PIPELINE: (
        "Egim esigin altinda: veri ikiye katlandiginda ER olculebilir bicimde "
        "dusmuyor. **Olcek buyutmek dogru kaldirac degildir**; once pipeline "
        "onarilmalidir."
    ),
    DECISION_UNDETERMINED: (
        "Egim guven araligi esigi kesiyor: **karar verilemez**. Daha fazla "
        "nokta ya da daha buyuk korpus gerekir."
    ),
    DECISION_NO_DATA: "Ogrenme egrisi olculmedi.",
}


def build_markdown(report: CurveReport, *, title: str = "Faz 7-R - Ogrenme egrisi") -> str:
    """Insan-okur Markdown rapor."""
    lines: list[str] = ["# " + title, ""]
    lines.append("Soru: **ER hedefin uzerindeyse, daha cok veri mi yoksa onarilmis")
    lines.append("bir hat mi gerekiyor?** Ayni hat, ayni tohum, yalnizca veri hacmi")
    lines.append("degisir. Karar, ER'nin `log2(veri)` basina egiminden verilir.")
    lines.append("")
    lines.append("## 1. Noktalar")
    lines.append("")
    header = "| Carpan | Pozisyon |"
    sep = "|---|---|"
    for path in CURVE_PATHS:
        header += " ER `%s` |" % path
        sep += "---|"
    header += " Kal. egimi | Kal. MAE | In-sample | Held-out |"
    sep += "---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for p in report.points:
        means = p.means
        row = "| %d× | %d |" % (p.multiplier, p.positions)
        for path in CURVE_PATHS:
            row += " %s |" % _fmt(means.get(path))
        row += " %s | %s | %s | %s |" % (
            _fmt(p.slope),
            _fmt(p.mae),
            _fmt(p.in_sample_loss),
            _fmt(p.held_out_loss),
        )
        lines.append(row)
    lines.append("")
    lines.append("> **In-sample metrikler basari sayilmaz** (Kural 5). Held-out")
    lines.append("> kolonu tek basina okunmalidir.")
    lines.append("")
    lines.append("## 2. Egim (ER / log2 veri)")
    lines.append("")
    lines.append("| Yol | Kazanc | %95 GA | Ham egim | Nokta | Yeniden ornekleme |")
    lines.append("|---|---|---|---|---|---|")
    for path in CURVE_PATHS:
        entry = report.slopes.get(path)
        if entry is None:
            continue
        lines.append(
            "| `%s` | %s | [%s; %s] | %s | %d | %d |"
            % (
                path,
                _fmt(entry.get("gain")),
                _fmt(entry.get("gainCiLow")),
                _fmt(entry.get("gainCiHigh")),
                _fmt(entry.get("slope")),
                int(entry.get("n", 0)),
                int(entry.get("resamples", 0)),
            )
        )
    lines.append("")
    lines.append(
        "**Kazanc** = ER'nin `log2(veri)` basina **dususu** (pozitif = veri "
        "arttkca ER iyilesiyor). Ham egim ayni buyuklugun isaretli hali."
    )
    lines.append("")
    lines.append("Esik: **%s** (ER kazanci / log2 veri)." % _fmt(SCALING_SLOPE_EPSILON))
    lines.append("")
    lines.append("## 3. Karar")
    lines.append("")
    lines.append("**`%s`**" % report.decision)
    lines.append("")
    lines.append(DECISION_TEXT.get(report.decision, ""))
    lines.append("")
    if report.notes:
        lines.append("## 4. Notlar")
        lines.append("")
        for note in report.notes:
            lines.append("- " + note)
        lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="learning_curve",
        description="Ogrenme egrisi: olcek mi pipeline mi?",
    )
    p.add_argument(
        "--base-positions",
        type=int,
        default=2000,
        help="1x noktasinin pozisyon sayisi (varsayilan 2000)",
    )
    p.add_argument(
        "--multipliers",
        type=int,
        nargs="+",
        default=list(CURVE_MULTIPLIERS),
        help="veri hacmi carpanlari",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    p.add_argument("--out", type=Path, default=None, help="cikti JSON")
    p.add_argument("--markdown", type=Path, default=None, help="cikti Markdown")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sizes = [int(args.base_positions) * int(m) for m in args.multipliers]

    def _train(positions: int, seed: int) -> dict[str, Any]:
        raise SystemExit(
            "learning_curve: gercek egitim hatti baglanmadi. "
            "run_curve(train_fn=...) ile cagirin (bkz. ml/gnubg_distill.py)."
        )

    report = run_curve(
        sizes=sizes,
        train_fn=_train,
        seed=args.seed,
        multipliers=args.multipliers,
        resamples=args.resamples,
        progress=None if args.quiet else (lambda m: print(m)),
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")
    if not args.quiet:
        print("karar: %s" % report.decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
