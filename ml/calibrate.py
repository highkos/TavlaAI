#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 7 Asama D - kalibrasyon onarimi ve kapisi (oncelikli).

**Neden oncelikli?** Olculen durum (`ml/artifacts/stage_h_calibration.json`,
400 afterstate, gnubg 0-ply):

    egim       0,6601   (kapi 0,85 .. 1,15)   **KALDI**
    korelasyon +0,8989  (kapi >= 0,75)        gecti
    MAE        0,2755   (kapi <= 0,15)        **KALDI**
    std orani  1,3617   (kapi 0,7 .. 1,4)     gecti

Yani ag equity'nin **yonunu** biliyor (korelasyon 0,90) ama **olcegini**
kaciriyor: tahminler hedefin ~0,66'si kadar, sistematik sapma -0,155. Bu, ER'yi
dogrudan bozar; bu yuzden kalibrasyon, diger kaldiraclardan **once** onarilir.

**Iki yol, ikisi de olculur.**

1. **Post-hoc affine** (`a * pred + b`). Kalibrasyonun "son care" adimi
   (Bolum 6.2 adim 4'ün dogrusal karsiligi). **Yalnizca CAL** kumesinde
   ogrenilir, **VAL** kumesinde raporlanir. Modeli yeniden egitmez; egri
   duzeltir. Egim ve MAE'yi duzeltir, ama **korelasyonu artirmaz** (dogrusal
   donusum korelasyonu degistirmez) - bunu rapor acikca yazar.
2. **Yeniden egitim** (`L_cal` terimi, `c_cal = 0.1`). Asil cozum; Asama D'nin
   egitim kosusudur. Bu modul onu **olcer**, yerine gecmez.

**Kural 10 (Faz 6 Bolum 6.4).** Sicaklik/egri **yalnizca CAL**'dan ogrenilir.
VAL ve TEST kumeleri duzeltmeyi gormez; aksi halde raporlanan kalibrasyon
iyimser olur. Bu modul, bolmeyi **deterministik** yapar (sabit tohum) ve
onarim oncesi/sonrasi metrikleri **VAL uzerinde** verir.

Kullanim::

    python ml/calibrate.py --source ml/artifacts/stage_h_afterstates.json
    python ml/calibrate.py --json ml/artifacts/stage_d_calibration.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from calibration import (  # noqa: E402
    CORRELATION_MIN,
    MAE_MAX,
    SLOPE_MAX,
    SLOPE_MIN,
    STD_RATIO_MAX,
    STD_RATIO_MIN,
    calibration_metrics,
    is_calibrated,
)

ARTIFACTS = os.path.join(HERE, "artifacts")
DEFAULT_SOURCE = os.path.join(ARTIFACTS, "stage_h_afterstates.json")
DEFAULT_JSON = os.path.join(ARTIFACTS, "stage_d_calibration.json")
DEFAULT_REPORT = os.path.join(ARTIFACTS, "stage_d_calibration.md")

#: CAL kumesinin orani (kalan VAL). Kural 10: onarim yalnizca CAL'da ogrenilir.
CAL_FRACTION = 0.5

#: Bolme tohumu (deterministik).
SPLIT_SEED = 20261117

#: Egim kirpilma araligi: asiri egim (or. 5,0) egriyi bozar.
SLOPE_CLAMP = (0.05, 20.0)


class CalibrationError(ValueError):
    """Kalibrasyon onarimi yapilamadi."""


# ----------------------------------------------------------------------
# Bolme
# ----------------------------------------------------------------------


def split_pairs(
    pairs: Sequence[tuple[float, float]],
    *,
    cal_fraction: float = CAL_FRACTION,
    seed: int = SPLIT_SEED,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Ciftleri deterministik olarak CAL / VAL kumelerine boler."""
    if not 0.0 < cal_fraction < 1.0:
        raise CalibrationError("cal_fraction 0 ile 1 arasinda olmali")
    n = len(pairs)
    if n < 4:
        raise CalibrationError("en az 4 cift gerekli")
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    cut = int(round(n * cal_fraction))
    cut = max(1, min(n - 1, cut))
    cal = [pairs[int(i)] for i in order[:cut]]
    val = [pairs[int(i)] for i in order[cut:]]
    return cal, val


# ----------------------------------------------------------------------
# Affine onarim
# ----------------------------------------------------------------------


def fit_affine(pred: Sequence[float], target: Sequence[float]) -> tuple[float, float]:
    """``target ~ a * pred + b`` en kucuk kareler fiti (yalnizca CAL)."""
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    t = np.asarray(target, dtype=np.float64).reshape(-1)
    if p.shape != t.shape:
        raise CalibrationError("sekil uyusmuyor: %s vs %s" % (p.shape, t.shape))
    if p.size < 2:
        raise CalibrationError("en az 2 ornek gerekli")
    if not (np.all(np.isfinite(p)) and np.all(np.isfinite(t))):
        raise CalibrationError("sonlu olmayan deger")

    p_var = float(np.var(p))
    if p_var <= 0.0:
        raise CalibrationError("pred varyansi sifir; egim tanimsiz")

    cov = float(np.mean((p - float(np.mean(p))) * (t - float(np.mean(t)))))
    slope = cov / p_var
    slope = float(np.clip(slope, SLOPE_CLAMP[0], SLOPE_CLAMP[1]))
    intercept = float(np.mean(t)) - slope * float(np.mean(p))
    return slope, intercept


def apply_affine(pred: Sequence[float], slope: float, intercept: float) -> np.ndarray:
    """``a * pred + b``."""
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    return slope * p + intercept


# ----------------------------------------------------------------------
# Kapi
# ----------------------------------------------------------------------


def gate_verdict(metrics: dict[str, float]) -> dict[str, Any]:
    """Dort kapiyi tek tek raporlar (Faz 6 Bolum 6.3)."""
    slope = float(metrics["slope"])
    corr = float(metrics["correlation"])
    mae = float(metrics["mae"])
    std_ratio = float(metrics["std_ratio"])
    gates = {
        "slope": SLOPE_MIN <= slope <= SLOPE_MAX,
        "correlation": corr >= CORRELATION_MIN,
        "mae": mae <= MAE_MAX,
        "std_ratio": STD_RATIO_MIN <= std_ratio <= STD_RATIO_MAX,
    }
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "failed": sorted(name for name, ok in gates.items() if not ok),
    }


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


@dataclass
class RepairResult:
    """Onarim oncesi/sonrasi kalibrasyon (VAL uzerinde)."""

    count: int
    cal_count: int
    val_count: int
    slope: float
    intercept: float
    before: dict[str, float]
    after: dict[str, float]
    before_gate: dict[str, Any]
    after_gate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "calCount": self.cal_count,
            "valCount": self.val_count,
            "affine": {"slope": self.slope, "intercept": self.intercept},
            "before": self.before,
            "after": self.after,
            "beforeGate": self.before_gate,
            "afterGate": self.after_gate,
        }


def repair(
    pairs: Sequence[tuple[float, float]],
    *,
    cal_fraction: float = CAL_FRACTION,
    seed: int = SPLIT_SEED,
) -> RepairResult:
    """CAL'da affine onarim ogrenir, VAL'de oncesi/sonrasi metrikleri verir."""
    cal, val = split_pairs(pairs, cal_fraction=cal_fraction, seed=seed)
    cal_pred = [a for a, _ in cal]
    cal_tgt = [b for _, b in cal]
    slope, intercept = fit_affine(cal_pred, cal_tgt)

    val_pred = np.asarray([a for a, _ in val], dtype=np.float64)
    val_tgt = np.asarray([b for _, b in val], dtype=np.float64)

    before = calibration_metrics(val_pred, val_tgt)
    after = calibration_metrics(apply_affine(val_pred, slope, intercept), val_tgt)

    return RepairResult(
        count=len(pairs),
        cal_count=len(cal),
        val_count=len(val),
        slope=slope,
        intercept=intercept,
        before=before,
        after=after,
        before_gate=gate_verdict(before),
        after_gate=gate_verdict(after),
    )


def _f(value: float, digits: int = 4, sign: bool = False) -> str:
    text = ("%+.*f" if sign else "%.*f") % (digits, value)
    return text.replace(".", ",")


def build_markdown(result: RepairResult, source_name: str) -> str:
    """Insan-okur onarim raporu."""
    lines = [
        "# Asama D - kalibrasyon onarimi (oncelikli)",
        "",
        "Kaynak: `%s`." % source_name,
        "Bolme: CAL %d / VAL %d (tohum %d, Kural 10: onarim **yalnizca CAL**'da ogrenilir)."
        % (result.cal_count, result.val_count, SPLIT_SEED),
        "",
        "## Onarim oncesi / sonrasi (VAL)",
        "",
        "| Metrik | Onarim oncesi | Onarim sonrasi | Kapi | Once | Sonra |",
        "|---|---|---|---|---|---|",
    ]
    rows = [
        ("Egim", "slope", "%s - %s" % (_f(SLOPE_MIN, 2), _f(SLOPE_MAX, 2)), False),
        ("Korelasyon", "correlation", ">= %s" % _f(CORRELATION_MIN, 2), True),
        ("MAE", "mae", "<= %s" % _f(MAE_MAX, 2), False),
        ("Std orani", "std_ratio", "%s - %s" % (_f(STD_RATIO_MIN, 1), _f(STD_RATIO_MAX, 1)), False),
    ]
    for label, key, gate, sign in rows:
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                label,
                _f(result.before[key], sign=sign),
                _f(result.after[key], sign=sign),
                gate,
                "gecti" if result.before_gate["gates"][key] else "**KALDI**",
                "gecti" if result.after_gate["gates"][key] else "**KALDI**",
            )
        )
    lines.append("")
    lines.append(
        "Affine onarim: `hedef ~ %s * tahmin %s %s`."
        % (_f(result.slope), "+" if result.intercept >= 0 else "-", _f(abs(result.intercept)))
    )
    lines.append("")
    lines.append("## Yorum")
    lines.append("")
    if result.after_gate["passed"]:
        lines.append("Affine onarim **dort kapiyi da** VAL'de geciyor.")
    else:
        lines.append(
            "Affine onarim sonrasi kapi disinda kalan metrikler: **%s**."
            % ", ".join(result.after_gate["failed"])
        )
    lines.append("")
    lines.append(
        "**Korelasyon degismez.** Dogrusal bir donusum Pearson korelasyonunu "
        "degistirmez; bu yuzden affine onarim korelasyonu **artirmaz**. Korelasyon "
        "kapi disindaysa tek cozum **yeniden egitimdir** (`L_cal`, `c_cal = 0.1`)."
    )
    lines.append("")
    lines.append(
        "**Bu rapor modeli kalibre demiyor.** Affine onarim, dagitimli urunde "
        "uygulanacak bir **cikti duzeltmesidir**; agin kendisi hala olcek kaciriyor "
        "olabilir. Asil cozum Asama D'nin `L_cal` egitimidir."
    )
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def load_pairs(path: str) -> list[tuple[float, float]]:
    """`dump-afterstates` ciktisindan ``(bizim, gnubg)`` ciftleri.

    ``gnubg`` degeri kaynakta **yoktur**; bu yuzden kaynak ya
    ``stage_h_calibration_pairs.json`` biciminde (``pairs``) ya da
    ``stage_h_afterstates.json`` + ``--gnubg-pairs`` ile verilir.
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if "pairs" in payload:
        return [(float(a), float(b)) for a, b in payload["pairs"]]
    raise CalibrationError(
        "kaynakta 'pairs' yok; once ml/calibration_bench.py ile gnubg ciftleri uretin"
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Faz 7 Asama D kalibrasyon onarimi")
    ap.add_argument("--source", default=os.path.join(ARTIFACTS, "stage_h_calibration_pairs.json"))
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--markdown", default=DEFAULT_REPORT)
    ap.add_argument("--cal-fraction", type=float, default=CAL_FRACTION)
    ap.add_argument("--seed", type=int, default=SPLIT_SEED)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pairs = load_pairs(args.source)
    result = repair(pairs, cal_fraction=args.cal_fraction, seed=args.seed)

    if args.json:
        directory = os.path.dirname(os.path.abspath(args.json))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
    if args.markdown:
        directory = os.path.dirname(os.path.abspath(args.markdown))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(build_markdown(result, os.path.basename(args.source)))

    print(
        "kalibrasyon: %d cift (CAL %d / VAL %d) | egim %s -> %s | MAE %s -> %s | kapi %s"
        % (
            result.count,
            result.cal_count,
            result.val_count,
            _f(result.before["slope"]),
            _f(result.after["slope"]),
            _f(result.before["mae"]),
            _f(result.after["mae"]),
            "gecti" if result.after_gate["passed"] else "KALDI",
        )
    )
    return 0 if result.after_gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
