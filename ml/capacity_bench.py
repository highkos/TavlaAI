#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.2 - kapasite olcumu (Test 95, 96).

Iki soruyu **olcer**, tahmin etmez:

1. **Test 95** - ``large`` profili ONNX'e ihrac edilebiliyor mu, PyTorch <-> ORT
   paritesi **1e-6**'nin altinda mi, ve CPU kova 128'de kac pozisyon/sn uretiyor?
2. **Test 96** - ``large``, ``medium``'a gore VAL-ER'de **>= %15** kazandiriyor mu
   **ve** depth 2 p95 **<= 2 s/karar** kapisini koruyor mu? Ikisi birlikte
   saglanmazsa ``medium`` uretim modeli kalir (Bolum 5.2 karar kurali).

**Durustluk kurali.** Karar kuralinin iki bacagi da **olculur**; biri eksikse
``selected = "undecided"`` yazilir ve gerekce raporlanir. Uydurma sayi yok.

Kullanim::

    python ml/capacity_bench.py --json ml/artifacts/stage_b_capacity.json \
        --markdown ml/artifacts/stage_g_capacity.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
for _path in (str(ML_DIR), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import export_onnx  # noqa: E402  (yol kurulumundan sonra)
from model import (  # noqa: E402
    CAPACITY_PROFILES,
    PROB_COUNT,
    VECTOR_SIZE,
    build_model,
    parameter_count,
)

#: Faz 7 Bolum 5.2: karsilastirilan iki profil.
PROFILES = ("medium", "large")

#: Faz 7 Bolum 5.2 / F-B3: ihrac paritesi esigi (``export_onnx`` 1e-5'ten **siki**).
PARITY_TOLERANCE = 1e-6

#: Faz 7 Bolum 5.2: CPU kova boyu.
CPU_BUCKET = 128

#: Faz 7 Bolum 5.2: ``large`` icin gereken **goreli** VAL-ER kazanci.
CAPACITY_GAIN_THRESHOLD = 0.15

#: Faz 7 Bolum 5.2 / Test 79: depth 2 p95 karar suresi tavani (saniye).
DEPTH2_P95_LIMIT = 2.0

#: Parite icin kullanilan toplu boylar (dinamik eksen de dogrulanir).
PARITY_BATCHES = (1, 2, 13, 64, 128)

#: Varsayilan olcum tekrari (isinma + olcum).
DEFAULT_REPEATS = 5

#: Varsayilan is parcacigi sayisi (0 = ORT varsayilani).
DEFAULT_THREADS = 0

#: Rapor sema surumu.
SCHEMA_VERSION = 1


class CapacityError(RuntimeError):
    """Kapasite olcumu yapilamadi."""


# ----------------------------------------------------------------------
# Test 95 - ihrac + parite + CPU kova
# ----------------------------------------------------------------------


def export_profile(
    profile: str,
    out_path: Path,
    *,
    seed: int = 20260717,
    model_version: int = 0,
    trained_by: str = "faz7-stage-b",
) -> dict[str, Any]:
    """Profili ONNX'e ihrac eder ve mimari/parametre bilgisini doner."""
    if profile not in CAPACITY_PROFILES:
        raise CapacityError("bilinmeyen profil: %r" % (profile,))
    model = build_model(output_version=2, profile=profile, seed=seed)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_onnx.export(model, str(out_path), model_version, trained_by, output_version=2)
    return {
        "profile": profile,
        "arch": model.arch,
        "parameters": parameter_count(model),
        "hidden": list(CAPACITY_PROFILES[profile]),
        "onnx": str(out_path),
        "onnxBytes": out_path.stat().st_size,
    }


def parity(
    profile: str,
    onnx_path: Path,
    *,
    seed: int = 0x4F4E4E58,
    tolerance: float = PARITY_TOLERANCE,
) -> dict[str, Any]:
    """PyTorch <-> ORT paritesi; ``tolerance`` asilirsa **hata** firlatir."""
    import onnxruntime as ort
    import torch

    model = build_model(output_version=2, profile=profile, seed=20260717)
    model.eval()
    rng = np.random.default_rng(seed)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    max_dp = 0.0
    max_dg = 0.0
    per_batch: list[dict[str, Any]] = []
    for batch in PARITY_BATCHES:
        x = rng.standard_normal((batch, VECTOR_SIZE)).astype(np.float32)
        with torch.no_grad():
            tp, tg = model(torch.from_numpy(x))
        tp = tp.detach().cpu().numpy().reshape(batch, PROB_COUNT)
        tg = tg.detach().cpu().numpy().reshape(-1)
        op, og = sess.run(["probs", "policy_logit"], {"features": x})
        op = op.reshape(batch, PROB_COUNT)
        og = og.reshape(-1)
        dp = float(np.max(np.abs(tp - op)))
        dg = float(np.max(np.abs(tg - og)))
        max_dp = max(max_dp, dp)
        max_dg = max(max_dg, dg)
        per_batch.append({"batch": batch, "maxAbsDeltaProbs": dp, "maxAbsDeltaPolicy": dg})

    worst = max(max_dp, max_dg)
    if not math.isfinite(worst) or worst > tolerance:
        raise CapacityError(
            "%s parite basarisiz: |dprobs|=%.3e |dpolicy|=%.3e tolerans=%.0e"
            % (profile, max_dp, max_dg, tolerance)
        )
    return {
        "profile": profile,
        "tolerance": tolerance,
        "maxAbsDeltaProbs": max_dp,
        "maxAbsDeltaPolicy": max_dg,
        "ok": True,
        "perBatch": per_batch,
    }


def throughput(
    onnx_path: Path,
    *,
    batch: int = CPU_BUCKET,
    repeats: int = DEFAULT_REPEATS,
    threads: int = DEFAULT_THREADS,
    seed: int = 7,
) -> dict[str, Any]:
    """CPU kova ``batch`` icin pozisyon/sn olcer (isinma + ``repeats`` olcum)."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    if threads > 0:
        options.intra_op_num_threads = int(threads)
        options.inter_op_num_threads = 1
    sess = ort.InferenceSession(
        str(onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((batch, VECTOR_SIZE)).astype(np.float32)

    sess.run(["probs", "policy_logit"], {"features": x})  # isinma

    samples: list[float] = []
    for _ in range(max(1, repeats)):
        started = time.perf_counter()
        sess.run(["probs", "policy_logit"], {"features": x})
        samples.append(time.perf_counter() - started)

    seconds = float(np.median(samples))
    return {
        "batch": batch,
        "repeats": len(samples),
        "threads": threads,
        "medianSeconds": seconds,
        "positionsPerSecond": (batch / seconds) if seconds > 0 else float("inf"),
        "minSeconds": float(np.min(samples)),
        "maxSeconds": float(np.max(samples)),
    }


# ----------------------------------------------------------------------
# Test 96 - karar kurali
# ----------------------------------------------------------------------


def decide_capacity(
    er_medium: float,
    se_medium: float,
    er_large: float,
    se_large: float,
    p95_large: float | None,
    *,
    gain_threshold: float = CAPACITY_GAIN_THRESHOLD,
    p95_limit: float = DEPTH2_P95_LIMIT,
) -> dict[str, Any]:
    """Bolum 5.2 karar kurali: **iki bacak birlikte** saglanmali.

    (a) ``large`` VAL-ER'de ``medium``'a gore **goreli** >= %15 iyi, **ve**
    (b) ``large`` depth 2 p95 <= 2 s/karar.

    ``p95_large`` verilmezse karar **verilemez** (``undecided``); uydurma yok.
    """
    values = (er_medium, se_medium, er_large, se_large)
    if not all(math.isfinite(float(v)) for v in values):
        raise CapacityError("ER/SE degerleri sonlu olmali: %r" % (values,))
    if float(er_medium) <= 0.0:
        raise CapacityError("medium ER pozitif olmali (goreli kazanc tanimsiz): %r" % (er_medium,))

    difference = float(er_medium) - float(er_large)
    relative_gain = difference / float(er_medium)
    threshold = float(gain_threshold) * math.hypot(float(se_medium), float(se_large))
    gain_ok = difference > threshold and relative_gain >= float(gain_threshold)

    if p95_large is None or not math.isfinite(float(p95_large)):
        latency_ok: bool | None = None
    else:
        latency_ok = float(p95_large) <= float(p95_limit)

    if latency_ok is None:
        selected = "undecided"
        reason = "depth 2 p95 olculmedi; karar kuralinin (b) bacagi eksik"
    elif gain_ok and latency_ok:
        selected = "large"
        reason = "iki bacak da saglandi: goreli kazanc %.1f%%, p95 %.2f s" % (
            100.0 * relative_gain,
            float(p95_large),
        )
    elif not gain_ok and latency_ok:
        selected = "medium"
        reason = "goreli kazanc %.1f%% < %.0f%%; medium kalir" % (
            100.0 * relative_gain,
            100.0 * float(gain_threshold),
        )
    elif gain_ok and not latency_ok:
        selected = "medium"
        reason = "p95 %.2f s > %.2f s; large uretimde kullanilamaz (F-B2)" % (
            float(p95_large),
            float(p95_limit),
        )
    else:
        selected = "medium"
        reason = "iki bacak da saglanmadi; medium kalir"

    return {
        "erMedium": float(er_medium),
        "seMedium": float(se_medium),
        "erLarge": float(er_large),
        "seLarge": float(se_large),
        "difference": difference,
        "relativeGain": relative_gain,
        "gainThreshold": float(gain_threshold),
        "noiseThreshold": threshold,
        "gainOk": gain_ok,
        "p95Large": None if p95_large is None else float(p95_large),
        "p95Limit": float(p95_limit),
        "latencyOk": latency_ok,
        "selected": selected,
        "reason": reason,
    }


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def build_markdown(report: dict[str, Any]) -> str:
    """Rapor sozlugunu Markdown'a cevirir."""
    lines = [
        "# Asama B - kapasite ve veri (Test 95-98)",
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| Parite esigi | %.0e (F-B3) |" % report["parityTolerance"],
        "| CPU kova | %d |" % report["cpuBucket"],
        "| Karar kurali | goreli kazanc >= %.0f%% **ve** depth 2 p95 <= %.1f s |"
        % (100.0 * report["gainThreshold"], report["p95Limit"]),
        "",
        "## 1. Profiller (Test 95)",
        "",
        "| Profil | Mimari | Parametre | ONNX | Parite max abs | CPU kova %d (poz/sn) |"
        % report["cpuBucket"],
        "|---|---|---|---|---|---|",
    ]
    for row in report["profiles"]:
        lines.append(
            "| `%s` | %s | %s | %.1f KB | %.2e | %s |"
            % (
                row["profile"],
                row["arch"],
                "{:,}".format(row["parameters"]).replace(",", " "),
                row["onnxBytes"] / 1024.0,
                max(row["parity"]["maxAbsDeltaProbs"], row["parity"]["maxAbsDeltaPolicy"]),
                "{:,.0f}".format(row["throughput"]["positionsPerSecond"]).replace(",", " "),
            )
        )
    decision = report["decision"]
    lines.extend(
        [
            "",
            "## 2. Karar (Test 96)",
            "",
            "| Alan | Deger |",
            "|---|---|",
            "| medium VAL-ER | %.4f (SE %.4f) |" % (decision["erMedium"], decision["seMedium"]),
            "| large VAL-ER | %.4f (SE %.4f) |" % (decision["erLarge"], decision["seLarge"]),
            "| Fark | %.4f |" % decision["difference"],
            "| Goreli kazanc | %.1f%% (esik %.0f%%) |"
            % (100.0 * decision["relativeGain"], 100.0 * decision["gainThreshold"]),
            "| Gurultu esigi | %.4f |" % decision["noiseThreshold"],
            "| depth 2 p95 | %s |"
            % ("olculmedi" if decision["p95Large"] is None else "%.2f s" % decision["p95Large"]),
            "| **Secim** | **%s** |" % decision["selected"],
            "",
            "**Gerekce.** %s" % decision["reason"],
            "",
            "## 3. Veri kalitesi (Test 97, 98)",
            "",
            "| Test | Ne dogrular | Durum |",
            "|---|---|---|",
            "| 97 | Ilk 10 ply'de `dup_cap` muafiyeti korunur | %s |" % report["dataQuality"]["test97"],
            "| 98 | Kritik karar agirligi 2x uygulanir, dagilim raporlanir | %s |"
            % report["dataQuality"]["test98"],
            "",
        ]
    )
    if report["dataQuality"].get("criticalDistribution"):
        dist = report["dataQuality"]["criticalDistribution"]
        lines.extend(
            [
                "### Kritik karar dagilimi (Test 98)",
                "",
                "| Alan | Deger |",
                "|---|---|",
                "| Karar sayisi | %d |" % dist["count"],
                "| Kritik karar | %d (%.1f%%) |" % (dist["critical"], 100.0 * dist["criticalShare"]),
                "| Agirlik | %.1fx |" % dist["boost"],
                "| Etkin orneklem | %.1f |" % dist["effectiveCount"],
                "| Equity esigi | %.2f |" % dist["equityThreshold"],
                "| Marj esigi | %.3f |" % dist["marginThreshold"],
                "",
            ]
        )
    lines.extend(
        [
            "## 4. B1 / B2 / B3 yolu",
            "",
            report["pathNote"],
            "",
        ]
    )
    return "\n".join(lines)


def write_json(report: dict[str, Any], path: Path) -> None:
    """Raporu JSON olarak yazar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def load_critical_distribution(path: Path) -> dict[str, Any] | None:
    """``train_report.json`` icinden Test 98 politika dagilimini okur."""
    path = Path(path)
    if not path.is_file():
        raise CapacityError("train_report bulunamadi: %s" % path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    # F7-11: `iterations` bir SAYIDIR; iterasyon kayitlari `history` listesindedir.
    history = payload.get("history")
    if not isinstance(history, list):
        history = []
    for record in reversed(history):
        if not isinstance(record, dict):
            continue
        critical = record.get("critical")
        if isinstance(critical, dict) and critical.get("policy"):
            return critical["policy"]
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Faz 7 Bolum 5.2 - kapasite olcumu (Test 95, 96)."
    )
    parser.add_argument("--out-dir", type=Path, default=ML_DIR / "artifacts" / "capacity")
    parser.add_argument("--profiles", nargs="+", default=list(PROFILES))
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--er-medium", type=float, default=None)
    parser.add_argument("--se-medium", type=float, default=0.0)
    parser.add_argument("--er-large", type=float, default=None)
    parser.add_argument("--se-large", type=float, default=0.0)
    parser.add_argument("--p95-large", type=float, default=None)
    parser.add_argument(
        "--critical-json",
        type=Path,
        default=None,
        help="Test 98: kritik karar dagilimini okumak icin train_report.json",
    )
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    rows: list[dict[str, Any]] = []
    for profile in args.profiles:
        onnx_path = Path(args.out_dir) / ("model_%s.onnx" % profile)
        info = export_profile(profile, onnx_path)
        info["parity"] = parity(profile, onnx_path)
        info["throughput"] = throughput(
            onnx_path, repeats=args.repeats, threads=args.threads
        )
        rows.append(info)
        if not args.quiet:
            print(
                "%-8s %-22s %8d param  parite %.2e  %8.0f poz/sn (kova %d)"
                % (
                    profile,
                    info["arch"],
                    info["parameters"],
                    max(
                        info["parity"]["maxAbsDeltaProbs"],
                        info["parity"]["maxAbsDeltaPolicy"],
                    ),
                    info["throughput"]["positionsPerSecond"],
                    info["throughput"]["batch"],
                )
            )

    if args.er_medium is None or args.er_large is None:
        decision = {
            "erMedium": float("nan"),
            "seMedium": float(args.se_medium),
            "erLarge": float("nan"),
            "seLarge": float(args.se_large),
            "difference": float("nan"),
            "relativeGain": float("nan"),
            "gainThreshold": CAPACITY_GAIN_THRESHOLD,
            "noiseThreshold": float("nan"),
            "gainOk": False,
            "p95Large": args.p95_large,
            "p95Limit": DEPTH2_P95_LIMIT,
            "latencyOk": None,
            "selected": "undecided",
            "reason": "VAL-ER olculmedi (--er-medium/--er-large verilmedi); karar verilemez",
        }
    else:
        decision = decide_capacity(
            args.er_medium,
            args.se_medium,
            args.er_large,
            args.se_large,
            args.p95_large,
        )

    critical_distribution = None
    if args.critical_json:
        critical_distribution = load_critical_distribution(Path(args.critical_json))

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "parityTolerance": PARITY_TOLERANCE,
        "cpuBucket": CPU_BUCKET,
        "gainThreshold": CAPACITY_GAIN_THRESHOLD,
        "p95Limit": DEPTH2_P95_LIMIT,
        "profiles": rows,
        "decision": decision,
        "dataQuality": {
            "test97": "bkz. Backgammon.Inference.Tests/StageBDataQualityTests.cs",
            "test98": "bkz. ml/critical.py + ml/tests/test_critical.py",
            "criticalDistribution": critical_distribution,
        },
        "pathNote": (
            "B1/B2/B3 yol secimi **kullanici onayi** gerektirir (Bolum 5.1.6). "
            "Bu rapor yolu secmez; yalnizca `large`'in teknik olarak uygun olup "
            "olmadigini olcer. Yol secilmeden `large` ile egitim kosusu baslatilmaz."
        ),
    }

    if args.json:
        write_json(report, args.json)
        if not args.quiet:
            print("JSON: %s" % args.json)
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(build_markdown(report), encoding="utf-8")
        if not args.quiet:
            print("Markdown: %s" % args.markdown)
    if not args.quiet:
        print("karar: %s - %s" % (decision["selected"], decision["reason"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
