"""Faz 7 Bolum 5.4 / Test 102: damitilmis model ile kontrol modelinin VAL-ER karsilastirmasi.

Kapi: damitilmis model, damitilmamis **ayni** modelden VAL-ER'de **>= %25** daha iyi
olmali. Aksi halde damitma **basarisiz** sayilir ve sapma raporlanir.

Kazanc orani ``g = (ER_kontrol - ER_damitilmis) / ER_kontrol`` olarak tanimlidir.
Belirsizlik delta yontemiyle tasinir::

    Var(g) = Var(d) / c^2 + d^2 * Var(c) / c^4

Burada ``c`` kontrol, ``d`` damitilmis ER'dir. Iki olcum **bagimsiz** kabul edilir
(farkli modeller, ayni pozisyon kumesi; kovaryans ihmal edilir - muhafazakar
degildir, bu yuzden ``strict`` kapi alt siniri da ister).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

DISTILL_GAIN_MIN = 0.25
DISTILL_Z = 1.96
DISTILL_ALPHA = 0.05

# Kayan nokta sinir durumlari icin tolerans (or. (0.0740-0.0555)/0.0740 = 0.24999999999999994).
GAIN_EPS = 1e-9


class DistillCompareError(ValueError):
    """Karsilastirma girdileri gecersiz."""


def relative_gain(er_control: float, er_distill: float) -> float:
    """``(kontrol - damitilmis) / kontrol``. Pozitif = damitma daha iyi."""
    if not (er_control > 0.0):
        raise DistillCompareError("kontrol ER > 0 olmali: %r" % (er_control,))
    if er_distill < 0.0:
        raise DistillCompareError("damitilmis ER negatif olamaz: %r" % (er_distill,))
    return (er_control - er_distill) / er_control


def gain_standard_error(
    er_control: float,
    se_control: float,
    er_distill: float,
    se_distill: float,
) -> float:
    """Delta yontemiyle ``g``'nin standart hatasi."""
    if not (er_control > 0.0):
        raise DistillCompareError("kontrol ER > 0 olmali: %r" % (er_control,))
    if se_control < 0.0 or se_distill < 0.0:
        raise DistillCompareError("standart hatalar negatif olamaz")
    var = (se_distill ** 2) / (er_control ** 2)
    var += (er_distill ** 2) * (se_control ** 2) / (er_control ** 4)
    return math.sqrt(var)


def gain_interval(
    er_control: float,
    se_control: float,
    er_distill: float,
    se_distill: float,
    *,
    z: float = DISTILL_Z,
) -> tuple[float, float]:
    """Kazanc orani icin iki tarafli guven araligi."""
    if not (z > 0.0):
        raise DistillCompareError("z > 0 olmali: %r" % (z,))
    g = relative_gain(er_control, er_distill)
    se = gain_standard_error(er_control, se_control, er_distill, se_distill)
    return (g - z * se, g + z * se)


@dataclass
class CompareResult:
    """Test 102 kapi sonucu."""

    er_control: float
    se_control: float
    er_distill: float
    se_distill: float
    gain: float
    se: float
    low: float
    high: float
    gain_min: float
    passed: bool
    strict_passed: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "erControl": self.er_control,
            "seControl": self.se_control,
            "erDistill": self.er_distill,
            "seDistill": self.se_distill,
            "gain": self.gain,
            "se": self.se,
            "low": self.low,
            "high": self.high,
            "gainMin": self.gain_min,
            "passed": self.passed,
            "strictPassed": self.strict_passed,
            "reason": self.reason,
        }


def compare(
    er_control: float,
    se_control: float,
    er_distill: float,
    se_distill: float,
    *,
    gain_min: float = DISTILL_GAIN_MIN,
    z: float = DISTILL_Z,
) -> CompareResult:
    """Test 102 kapi karari.

    ``passed``: nokta tahmini esigi asar **ve** alt sinir 0'dan buyuktur
    (iyilesme istatistiksel olarak sifirdan ayrilir).

    ``strict_passed``: alt sinir da esigi asar (daha sert, daha az yanlis pozitif).
    """
    if not (0.0 < gain_min < 1.0):
        raise DistillCompareError("gain_min 0..1 araliginda olmali: %r" % (gain_min,))

    g = relative_gain(er_control, er_distill)
    se = gain_standard_error(er_control, se_control, er_distill, se_distill)
    low, high = gain_interval(er_control, se_control, er_distill, se_distill, z=z)

    passed = bool(g >= gain_min - GAIN_EPS and low > 0.0)
    strict_passed = bool(low >= gain_min - GAIN_EPS)

    if strict_passed:
        reason = "gecti: alt sinir %.4f >= esik %.2f" % (low, gain_min)
    elif passed:
        reason = (
            "gecti (nokta tahmini): kazanc %.4f >= esik %.2f, alt sinir %.4f > 0; "
            "sert kapi (alt sinir >= esik) saglanmadi" % (g, gain_min, low)
        )
    elif g >= gain_min - GAIN_EPS:
        reason = (
            "basarisiz: kazanc %.4f >= esik %.2f ama alt sinir %.4f <= 0 "
            "(iyilesme sifirdan ayrilmiyor)" % (g, gain_min, low)
        )
    else:
        reason = "basarisiz: kazanc %.4f < esik %.2f" % (g, gain_min)

    return CompareResult(
        er_control=er_control,
        se_control=se_control,
        er_distill=er_distill,
        se_distill=se_distill,
        gain=g,
        se=se,
        low=low,
        high=high,
        gain_min=gain_min,
        passed=passed,
        strict_passed=strict_passed,
        reason=reason,
    )


def load_summary(path: str | Path) -> dict:
    """``er_harness measure`` JSON'undan ozet okur."""
    p = Path(path)
    if not p.is_file():
        raise DistillCompareError("dosya yok: %s" % p)
    data = json.loads(p.read_text(encoding="utf-8"))
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise DistillCompareError("%s icinde 'summary' yok" % p)
    for key in ("mean", "standardError"):
        if key not in summary:
            raise DistillCompareError("%s icinde summary.%s yok" % (p, key))
    return {
        "model": data.get("model"),
        "split": data.get("split"),
        "plies": data.get("plies"),
        "count": summary.get("count"),
        "mean": float(summary["mean"]),
        "standardError": float(summary["standardError"]),
    }


def _f(value: float, digits: int = 4) -> str:
    return ("%." + str(digits) + "f") % value


def build_markdown(
    result: CompareResult,
    *,
    control_model: str | None = None,
    distill_model: str | None = None,
    control_count: int | None = None,
    distill_count: int | None = None,
) -> str:
    """Test 102 raporu (Turkce, ondalik virgul)."""
    def tr(value: float, digits: int = 4) -> str:
        return _f(value, digits).replace(".", ",")

    lines: list[str] = []
    lines.append("# Faz 7 Asama C - Test 102: damitma kazanci")
    lines.append("")
    lines.append("Kapi: damitilmis model, kontrol modelinden VAL-ER'de **>= %25** daha iyi.")
    lines.append("")
    lines.append("| Olcum | Kontrol | Damitilmis |")
    lines.append("|---|---|---|")
    lines.append("| Model | `%s` | `%s` |" % (control_model or "-", distill_model or "-"))
    lines.append("| Pozisyon | %s | %s |" % (control_count if control_count is not None else "-",
                                             distill_count if distill_count is not None else "-"))
    lines.append("| VAL-ER | %s | %s |" % (tr(result.er_control), tr(result.er_distill)))
    lines.append("| SE | %s | %s |" % (tr(result.se_control), tr(result.se_distill)))
    lines.append("")
    lines.append("| Kazanc | Deger |")
    lines.append("|---|---|")
    lines.append("| Nokta tahmini | %s |" % tr(result.gain))
    lines.append("| Standart hata | %s |" % tr(result.se))
    lines.append("| %%95 GA | [%s; %s] |" % (tr(result.low), tr(result.high)))
    lines.append("| Esik | %s |" % tr(result.gain_min, 2))
    lines.append("| Kapi | %s |" % ("GECTI" if result.passed else "BASARISIZ"))
    lines.append("| Sert kapi (alt sinir >= esik) | %s |" % ("GECTI" if result.strict_passed else "BASARISIZ"))
    lines.append("")
    lines.append("**Karar:** " + result.reason)
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="distill_compare",
        description="Faz 7 Test 102: damitilmis model vs kontrol modeli VAL-ER karsilastirmasi.",
    )
    parser.add_argument("--control", required=True, help="Kontrol modelinin er_harness JSON'u")
    parser.add_argument("--distill", required=True, help="Damitilmis modelin er_harness JSON'u")
    parser.add_argument("--gain-min", type=float, default=DISTILL_GAIN_MIN, help="Kapi esigi (varsayilan 0.25)")
    parser.add_argument("--z", type=float, default=DISTILL_Z, help="Guven araligi z (varsayilan 1.96)")
    parser.add_argument("--json", help="Sonucu JSON olarak yaz")
    parser.add_argument("--markdown", help="Sonucu Markdown olarak yaz")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        control = load_summary(args.control)
        distill = load_summary(args.distill)
        result = compare(
            control["mean"],
            control["standardError"],
            distill["mean"],
            distill["standardError"],
            gain_min=args.gain_min,
            z=args.z,
        )
    except DistillCompareError as exc:
        print("Hata: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        Path(args.json).write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.markdown:
        Path(args.markdown).write_text(
            build_markdown(
                result,
                control_model=control.get("model"),
                distill_model=distill.get("model"),
                control_count=control.get("count"),
                distill_count=distill.get("count"),
            ),
            encoding="utf-8",
        )

    print(
        "Test 102: kontrol ER=%.4f (SE %.4f), damitilmis ER=%.4f (SE %.4f)"
        % (result.er_control, result.se_control, result.er_distill, result.se_distill)
    )
    print(
        "kazanc=%.4f  SE=%.4f  %%95 GA=[%.4f; %.4f]  esik=%.2f  kapi=%s"
        % (result.gain, result.se, result.low, result.high, result.gain_min,
           "GECTI" if result.passed else "BASARISIZ")
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
