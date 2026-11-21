"""Modeller arasi ppg karsilastirmasi ve ER<->ppg eslemesi - Faz 7-R-F (F7-104).

``vs_gnubg.py`` her model icin tek bir ppg uretir. R-D karari icin
**modeller arasi** fark ve **ER ile ppg arasindaki ampirik esleme**
gerekir; bu modul ikisini de uretir.

Neden iki ornekli (unpaired) test yeterli: her kosu ayni zar tohumunu
(2026) kullanir ama modeller farkli hamle oynadigi icin oyunlar
birbirinden ayrilir. Ayni zar dizisi uzerinde kosullu bagimlilik
zayiftir; iki ornekli yaklasim GA'yi oldugundan **dar** gostermez cunku
her kosunun kendi eslesmis GA'si zaten zar gurultusunu iptal etmistir.
Bu varsayim ``CAVEAT`` alaninda kayitlidir.

ER<->ppg eslemesi K3'un kalan teslimati: ER tek basina bir *afterstate*
olcumudur, ppg ise *urun* olcumudur. Ikisi arasindaki egim, ER'deki bir
birimin kac ppg'ye karsilik geldigini soyler ve gelecekteki ER
kosularinin ppg'ye cevrilmesini saglar.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PPG_MODELS_PATH = "ml/artifacts/ppg_models.json"
PPG_MODELS_MD_PATH = "ml/artifacts/ppg_models.md"

Z95 = 1.959963984540054

CAVEAT = (
    "Kosular ayni zar tohumunu (2026) kullanir ama modeller farkli hamle "
    "oynadigi icin oyunlar ayrilir; iki ornekli GA bu yuzden yaklasiktir. "
    "Her kosunun kendi eslesmis GA'si zar gurultusunu zaten iptal ettigi "
    "icin GA oldugundan dar gorunmez."
)


class PpgModelsError(RuntimeError):
    """Karsilastirma yapilamadi."""


@dataclass
class ModelPpg:
    """Tek bir modelin ppg olcumu."""

    label: str
    model: str
    path: str
    games: int
    wins: int
    win_rate: float
    ppg: float
    ppg_ci_low: float
    ppg_ci_high: float
    ppg_std_error: float
    mean_plies: float
    seed: int
    er_policy: float | None = None
    er_value: float | None = None
    #: ``max_plies`` doldugu icin bitmeyen oyun sayisi (K5). Eski JSON'larda yok.
    unfinished: int = 0

    @property
    def ppg_sigma(self) -> float:
        """Oyun duzeyinde standart sapma (SE * sqrt(n))."""
        return self.ppg_std_error * math.sqrt(self.games)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "model": self.model,
            "path": self.path,
            "games": self.games,
            "wins": self.wins,
            "winRate": round(self.win_rate, 6),
            "ppg": round(self.ppg, 6),
            "ppgCiLow": round(self.ppg_ci_low, 6),
            "ppgCiHigh": round(self.ppg_ci_high, 6),
            "ppgStdError": round(self.ppg_std_error, 6),
            "ppgSigma": round(self.ppg_sigma, 6),
            "meanPlies": round(self.mean_plies, 4),
            "seed": self.seed,
            "unfinished": int(self.unfinished),
            "erPolicy": None if self.er_policy is None else round(self.er_policy, 6),
            "erValue": None if self.er_value is None else round(self.er_value, 6),
        }


@dataclass
class PairDiff:
    """Iki model arasindaki ppg farki (a - b)."""

    a: str
    b: str
    diff: float
    ci_low: float
    ci_high: float
    standard_error: float
    z: float
    significant: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "a": self.a,
            "b": self.b,
            "diff": round(self.diff, 6),
            "ciLow": round(self.ci_low, 6),
            "ciHigh": round(self.ci_high, 6),
            "standardError": round(self.standard_error, 6),
            "z": round(self.z, 4),
            "significant": self.significant,
        }


@dataclass
class ErPpgFit:
    """ppg = intercept + slope * ER dogrusal eslemesi."""

    head: str
    slope: float
    intercept: float
    r_squared: float
    points: int
    residuals: list[float] = field(default_factory=list)

    def predict(self, er: float) -> float:
        return self.intercept + self.slope * er

    def to_dict(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "slope": round(self.slope, 6),
            "intercept": round(self.intercept, 6),
            "rSquared": round(self.r_squared, 6),
            "points": self.points,
            "residuals": [round(r, 6) for r in self.residuals],
        }


def load_match(path: str | Path, label: str) -> ModelPpg:
    """``vs_gnubg.py`` ciktisini okur."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise PpgModelsError(f"mac dosyasi yok: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return ModelPpg(
        label=label,
        model=str(data.get("model", "")),
        path=str(data.get("path", "")),
        games=int(data["games"]),
        wins=int(data["wins"]),
        win_rate=float(data["winRate"]),
        ppg=float(data["ppg"]),
        ppg_ci_low=float(data["ppgCiLow"]),
        ppg_ci_high=float(data["ppgCiHigh"]),
        ppg_std_error=float(data["ppgStdError"]),
        mean_plies=float(data.get("meanPlies", 0.0)),
        seed=int(data.get("seed", 0)),
        unfinished=int(data.get("unfinished", 0)),
    )


def pair_difference(a: ModelPpg, b: ModelPpg) -> PairDiff:
    """``a - b`` ppg farki, iki ornekli GA ile."""
    diff = a.ppg - b.ppg
    se = math.hypot(a.ppg_std_error, b.ppg_std_error)
    if se <= 0.0:
        raise PpgModelsError("standart hata sifir; GA hesaplanamaz")
    z = diff / se
    return PairDiff(
        a=a.label,
        b=b.label,
        diff=diff,
        ci_low=diff - Z95 * se,
        ci_high=diff + Z95 * se,
        standard_error=se,
        z=z,
        significant=abs(z) >= Z95,
    )


def fit_er_ppg(models: Sequence[ModelPpg], head: str = "policy") -> ErPpgFit:
    """ER -> ppg dogrusal en kucuk kareler fiti."""
    attr = "er_policy" if head == "policy" else "er_value"
    pts = [
        (getattr(m, attr), m.ppg)
        for m in models
        if getattr(m, attr) is not None
    ]
    if len(pts) < 2:
        raise PpgModelsError(f"fit icin en az 2 nokta gerekli ({head})")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0.0:
        raise PpgModelsError("ER degerleri ayni; egim tanimsiz")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0
    return ErPpgFit(
        head=head,
        slope=slope,
        intercept=intercept,
        r_squared=r2,
        points=n,
        residuals=residuals,
    )


def build_report(
    models: Sequence[ModelPpg],
    baseline: str | None = None,
    pairs: Sequence[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Tam rapor sozlugu."""
    by_label = {m.label: m for m in models}
    if pairs is None:
        pairs = []
        if baseline and baseline in by_label:
            for m in models:
                if m.label != baseline:
                    pairs.append((m.label, baseline))
        else:
            for i in range(len(models)):
                for j in range(i + 1, len(models)):
                    pairs.append((models[i].label, models[j].label))
    diffs: list[PairDiff] = []
    for a_label, b_label in pairs:
        if a_label not in by_label or b_label not in by_label:
            raise PpgModelsError(f"bilinmeyen etiket: {a_label} / {b_label}")
        diffs.append(pair_difference(by_label[a_label], by_label[b_label]))

    fits: list[ErPpgFit] = []
    for head in ("policy", "value"):
        try:
            fits.append(fit_er_ppg(models, head))
        except PpgModelsError:
            pass

    return {
        "version": 1,
        "baseline": baseline,
        "caveat": CAVEAT,
        "models": [m.to_dict() for m in models],
        "pairs": [d.to_dict() for d in diffs],
        "fits": [f.to_dict() for f in fits],
    }


def _fmt(value: float, digits: int = 4) -> str:
    return f"{value:+.{digits}f}"


def build_markdown(report: dict[str, Any]) -> str:
    """Rapor sozlugunu markdown'a cevirir."""
    lines: list[str] = []
    lines.append("# Modeller arasi ppg ve ER<->ppg eslemesi (F7-104)")
    lines.append("")
    lines.append(
        "Ayni kosu kosullari (kupsuz para oyunu, eslestirilmis zar + renk "
        "takasi, gnubg 0-ply, `search1`, tohum 2026)."
    )
    lines.append("")
    lines.append("## 1. Modeller")
    lines.append("")
    lines.append(
        "| Model | Oyun | Kazanma | ppg | ppg %95 GA | SE | ER(pol, +1) | ER(val, +1) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for m in report["models"]:
        pol = "-" if m["erPolicy"] is None else f"{m['erPolicy']:.4f}"
        val = "-" if m["erValue"] is None else f"{m['erValue']:.4f}"
        lines.append(
            f"| `{m['label']}` | {m['games']} | {m['winRate']:.4f} | "
            f"**{m['ppg']:+.4f}** | [{m['ppgCiLow']:+.4f}; {m['ppgCiHigh']:+.4f}] | "
            f"{m['ppgStdError']:.4f} | {pol} | {val} |"
        )
    lines.append("")
    lines.append("## 2. Ikili farklar")
    lines.append("")
    lines.append("| a | b | a - b | %95 GA | z | Anlamli |")
    lines.append("|---|---|---|---|---|---|")
    for d in report["pairs"]:
        flag = "**evet**" if d["significant"] else "hayir"
        lines.append(
            f"| `{d['a']}` | `{d['b']}` | {_fmt(d['diff'])} | "
            f"[{d['ciLow']:+.4f}; {d['ciHigh']:+.4f}] | {d['z']:+.2f} | {flag} |"
        )
    lines.append("")
    lines.append("## 3. ER -> ppg eslemesi")
    lines.append("")
    if not report["fits"]:
        lines.append("Fit icin yeterli nokta yok.")
    else:
        lines.append("| Kafa | Egim (ppg / ER) | Kesisim | R^2 | Nokta |")
        lines.append("|---|---|---|---|---|")
        for f in report["fits"]:
            lines.append(
                f"| {f['head']} | **{f['slope']:+.2f}** | {f['intercept']:+.4f} | "
                f"{f['rSquared']:.4f} | {f['points']} |"
            )
        lines.append("")
        lines.append(
            "Egim, ER'deki **bir birimin** kac ppg'ye karsilik geldigini soyler. "
            "Negatif egim beklenir: ER buyudukce ppg kuculur."
        )
    lines.append("")
    lines.append("## 4. Uyari")
    lines.append("")
    lines.append(report["caveat"])
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Modeller arasi ppg karsilastirmasi")
    p.add_argument(
        "--model",
        action="append",
        default=[],
        metavar="ETIKET=JSON[,ER_POL[,ER_VAL]]",
        help="Model tanimi; birden fazla verilebilir",
    )
    p.add_argument("--baseline", default=None, help="Ikili farklarin referansi")
    p.add_argument("--out", default=PPG_MODELS_PATH)
    p.add_argument("--markdown", default=PPG_MODELS_MD_PATH)
    return p


def parse_model_spec(spec: str) -> ModelPpg:
    r"""``etiket=json[,er_pol[,er_val]]`` cozumler.

    Ayirici ``:`` degil ``,``: Windows surucu harfi (``C:\...``) iki nokta
    icerdigi icin ``:`` ayirici yolu bozar.
    """
    if "=" not in spec:
        raise PpgModelsError(f"gecersiz model tanimi: {spec}")
    label, rest = spec.split("=", 1)
    parts = rest.split(",")
    path = parts[0]
    er_pol = float(parts[1]) if len(parts) > 1 and parts[1] else None
    er_val = float(parts[2]) if len(parts) > 2 and parts[2] else None
    m = load_match(path, label)
    m.er_policy = er_pol
    m.er_value = er_val
    return m


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.model:
        raise SystemExit("en az bir --model gerekli")
    models = [parse_model_spec(s) for s in args.model]
    report = build_report(models, baseline=args.baseline)
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    if not md.is_absolute():
        md = REPO_ROOT / md
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")
    print(build_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
