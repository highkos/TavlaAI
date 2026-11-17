# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.2 / Test 95-96 - kapasite olcumu testleri."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import capacity_bench  # noqa: E402
from capacity_bench import (  # noqa: E402
    CAPACITY_GAIN_THRESHOLD,
    CPU_BUCKET,
    DEPTH2_P95_LIMIT,
    PARITY_TOLERANCE,
    PROFILES,
    CapacityError,
    build_markdown,
    build_parser,
    decide_capacity,
    export_profile,
    load_critical_distribution,
    parity,
    throughput,
    write_json,
)


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_95_profiles_are_medium_and_large():
    assert PROFILES == ("medium", "large")


def test_95_parity_tolerance_is_one_e_minus_six():
    assert PARITY_TOLERANCE == pytest.approx(1e-6)


def test_95_cpu_bucket_is_128():
    assert CPU_BUCKET == 128


def test_95_gain_threshold_is_fifteen_percent():
    assert CAPACITY_GAIN_THRESHOLD == pytest.approx(0.15)


def test_95_p95_limit_is_two_seconds():
    assert DEPTH2_P95_LIMIT == pytest.approx(2.0)


# ----------------------------------------------------------------------
# decide_capacity - dogruluk tablosu
# ----------------------------------------------------------------------


def test_96_both_legs_pass_selects_large():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, 1.0)
    assert decision["gainOk"] is True
    assert decision["latencyOk"] is True
    assert decision["selected"] == "large"


def test_96_gain_fails_latency_passes_selects_medium():
    decision = decide_capacity(0.060, 0.005, 0.058, 0.005, 1.0)
    assert decision["gainOk"] is False
    assert decision["latencyOk"] is True
    assert decision["selected"] == "medium"


def test_96_gain_passes_latency_fails_selects_medium():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, 3.0)
    assert decision["gainOk"] is True
    assert decision["latencyOk"] is False
    assert decision["selected"] == "medium"


def test_96_both_legs_fail_selects_medium():
    decision = decide_capacity(0.060, 0.005, 0.059, 0.005, 3.0)
    assert decision["gainOk"] is False
    assert decision["latencyOk"] is False
    assert decision["selected"] == "medium"


def test_96_missing_p95_is_undecided():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, None)
    assert decision["latencyOk"] is None
    assert decision["selected"] == "undecided"


def test_96_nan_p95_is_undecided():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, float("nan"))
    assert decision["selected"] == "undecided"


def test_96_relative_gain_arithmetic():
    decision = decide_capacity(0.060, 0.005, 0.045, 0.004, 1.0)
    assert decision["difference"] == pytest.approx(0.015)
    assert decision["relativeGain"] == pytest.approx(0.25)


def test_96_noise_threshold_uses_hypot():
    decision = decide_capacity(0.060, 0.003, 0.040, 0.004, 1.0)
    assert decision["noiseThreshold"] == pytest.approx(0.15 * 0.005)


def test_96_gain_must_beat_noise_threshold():
    # Goreli kazanc %15'i gecer ama fark gurultu esiginin altinda kalir.
    decision = decide_capacity(0.060, 0.200, 0.050, 0.200, 1.0)
    assert decision["relativeGain"] == pytest.approx(1.0 / 6.0)
    assert decision["gainOk"] is False


def test_96_rejects_zero_medium_er():
    with pytest.raises(CapacityError):
        decide_capacity(0.0, 0.005, 0.040, 0.004, 1.0)


def test_96_rejects_negative_medium_er():
    with pytest.raises(CapacityError):
        decide_capacity(-0.01, 0.005, 0.040, 0.004, 1.0)


def test_96_rejects_non_finite_er():
    with pytest.raises(CapacityError):
        decide_capacity(0.060, 0.005, float("inf"), 0.004, 1.0)


def test_96_rejects_non_finite_se():
    with pytest.raises(CapacityError):
        decide_capacity(0.060, float("nan"), 0.040, 0.004, 1.0)


def test_96_custom_thresholds():
    decision = decide_capacity(
        0.060, 0.001, 0.050, 0.001, 1.0, gain_threshold=0.10, p95_limit=0.5
    )
    assert decision["gainOk"] is True
    assert decision["latencyOk"] is False
    assert decision["selected"] == "medium"


def test_96_reason_mentions_fb2_when_latency_fails():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, 3.0)
    assert "F-B2" in decision["reason"]


def test_96_reason_mentions_undecided_when_p95_missing():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, None)
    assert "p95" in decision["reason"]


def test_96_decision_has_all_fields():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, 1.0)
    expected = {
        "erMedium", "seMedium", "erLarge", "seLarge", "difference", "relativeGain",
        "gainThreshold", "noiseThreshold", "gainOk", "p95Large", "p95Limit",
        "latencyOk", "selected", "reason",
    }
    assert expected <= set(decision)


# ----------------------------------------------------------------------
# export_profile
# ----------------------------------------------------------------------


def test_95_export_rejects_unknown_profile(tmp_path):
    with pytest.raises(CapacityError):
        export_profile("gigantic", tmp_path / "x.onnx")


@pytest.mark.slow
def test_95_export_small_profile(tmp_path):
    info = export_profile("small", tmp_path / "small.onnx")
    assert info["profile"] == "small"
    assert info["parameters"] > 0
    assert info["onnxBytes"] > 0
    assert info["hidden"] == [128, 64]
    assert (tmp_path / "small.onnx").is_file()


@pytest.mark.slow
def test_95_export_medium_has_more_parameters_than_small(tmp_path):
    small = export_profile("small", tmp_path / "small.onnx")
    medium = export_profile("medium", tmp_path / "medium.onnx")
    assert medium["parameters"] > small["parameters"]


# ----------------------------------------------------------------------
# parity
# ----------------------------------------------------------------------


@pytest.mark.slow
def test_95_parity_small_passes(tmp_path):
    export_profile("small", tmp_path / "small.onnx")
    result = parity("small", tmp_path / "small.onnx")
    assert result["ok"] is True
    assert result["maxAbsDeltaProbs"] <= PARITY_TOLERANCE
    assert result["maxAbsDeltaPolicy"] <= PARITY_TOLERANCE


@pytest.mark.slow
def test_95_parity_reports_every_batch(tmp_path):
    export_profile("small", tmp_path / "small.onnx")
    result = parity("small", tmp_path / "small.onnx")
    assert [row["batch"] for row in result["perBatch"]] == list(capacity_bench.PARITY_BATCHES)


@pytest.mark.slow
def test_95_parity_rejects_impossible_tolerance(tmp_path):
    export_profile("small", tmp_path / "small.onnx")
    with pytest.raises(CapacityError):
        parity("small", tmp_path / "small.onnx", tolerance=1e-12)


# ----------------------------------------------------------------------
# throughput
# ----------------------------------------------------------------------


@pytest.mark.slow
def test_95_throughput_positive(tmp_path):
    export_profile("small", tmp_path / "small.onnx")
    result = throughput(tmp_path / "small.onnx", repeats=2)
    assert result["positionsPerSecond"] > 0.0
    assert result["medianSeconds"] > 0.0
    assert result["batch"] == CPU_BUCKET


@pytest.mark.slow
def test_95_throughput_repeats_recorded(tmp_path):
    export_profile("small", tmp_path / "small.onnx")
    result = throughput(tmp_path / "small.onnx", repeats=3)
    assert result["repeats"] == 3


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _report(decision=None, critical=None):
    decision = decision or decide_capacity(0.060, 0.005, 0.040, 0.004, 1.0)
    return {
        "schemaVersion": 1,
        "parityTolerance": PARITY_TOLERANCE,
        "cpuBucket": CPU_BUCKET,
        "gainThreshold": CAPACITY_GAIN_THRESHOLD,
        "p95Limit": DEPTH2_P95_LIMIT,
        "profiles": [
            {
                "profile": "medium",
                "arch": "221-256-256-128",
                "parameters": 156423,
                "onnxBytes": 700000,
                "parity": {"maxAbsDeltaProbs": 5.96e-08, "maxAbsDeltaPolicy": 1e-07},
                "throughput": {"positionsPerSecond": 392397.0},
            },
            {
                "profile": "large",
                "arch": "221-512-512-512",
                "parameters": 642567,
                "onnxBytes": 2600000,
                "parity": {"maxAbsDeltaProbs": 5.96e-08, "maxAbsDeltaPolicy": 1e-07},
                "throughput": {"positionsPerSecond": 143594.0},
            },
        ],
        "decision": decision,
        "dataQuality": {
            "test97": "bkz. StageBDataQualityTests.cs",
            "test98": "bkz. ml/critical.py",
            "criticalDistribution": critical,
        },
        "pathNote": "B1/B2/B3 yol secimi kullanici onayi gerektirir.",
    }


def test_95_markdown_has_both_profile_rows():
    text = build_markdown(_report())
    assert "`medium`" in text
    assert "`large`" in text


def test_95_markdown_has_decision_section():
    text = build_markdown(_report())
    assert "## 2. Karar (Test 96)" in text
    assert "**large**" in text


def test_95_markdown_has_data_quality_section():
    text = build_markdown(_report())
    assert "## 3. Veri kalitesi (Test 97, 98)" in text


def test_95_markdown_has_path_section():
    text = build_markdown(_report())
    assert "## 4. B1 / B2 / B3 yolu" in text


def test_95_markdown_omits_critical_table_when_absent():
    text = build_markdown(_report())
    assert "### Kritik karar dagilimi" not in text


def test_95_markdown_includes_critical_table_when_present():
    critical = {
        "count": 1000,
        "critical": 120,
        "criticalShare": 0.12,
        "boost": 2.0,
        "effectiveCount": 900.0,
        "equityThreshold": 0.5,
        "marginThreshold": 0.05,
    }
    text = build_markdown(_report(critical=critical))
    assert "### Kritik karar dagilimi (Test 98)" in text
    assert "120 (12.0%)" in text


def test_95_markdown_shows_unmeasured_p95():
    decision = decide_capacity(0.060, 0.005, 0.040, 0.004, None)
    text = build_markdown(_report(decision=decision))
    assert "olculmedi" in text


def test_95_write_json_round_trip(tmp_path):
    report = _report()
    path = tmp_path / "out.json"
    write_json(report, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["decision"]["selected"] == "large"
    assert len(loaded["profiles"]) == 2


def test_95_write_json_creates_parent(tmp_path):
    path = tmp_path / "nested" / "deep" / "out.json"
    write_json(_report(), path)
    assert path.is_file()


# ----------------------------------------------------------------------
# load_critical_distribution
# ----------------------------------------------------------------------


def test_98_load_critical_distribution(tmp_path):
    # F7-11: gercek semada `iterations` bir SAYIDIR; kayitlar `history` listesindedir.
    payload = {
        "iterations": 2,
        "history": [
            {"iteration": 1, "critical": None},
            {
                "iteration": 2,
                "critical": {
                    "value": {"count": 10},
                    "policy": {"count": 20, "critical": 3, "criticalShare": 0.15},
                },
            },
        ],
    }
    path = tmp_path / "train_report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    dist = load_critical_distribution(path)
    assert dist["count"] == 20
    assert dist["critical"] == 3


def test_98_load_critical_distribution_missing_file(tmp_path):
    with pytest.raises(CapacityError):
        load_critical_distribution(tmp_path / "nope.json")


def test_98_load_critical_distribution_absent_returns_none(tmp_path):
    path = tmp_path / "train_report.json"
    path.write_text(json.dumps({"iterations": 1, "history": [{"iteration": 1}]}), encoding="utf-8")
    assert load_critical_distribution(path) is None


def test_98_load_critical_distribution_tolerates_int_iterations(tmp_path):
    """F7-11 regresyonu: `iterations` int iken `reversed()` cokmemeli."""
    path = tmp_path / "train_report.json"
    path.write_text(json.dumps({"iterations": 1}), encoding="utf-8")
    assert load_critical_distribution(path) is None


def test_98_load_critical_distribution_skips_non_dict_records(tmp_path):
    payload = {
        "iterations": 2,
        "history": [
            "bozuk",
            {"critical": {"policy": {"count": 5, "critical": 1}}},
        ],
    }
    path = tmp_path / "train_report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_critical_distribution(path)["count"] == 5


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_95_parser_defaults():
    args = build_parser().parse_args([])
    assert args.profiles == list(PROFILES)
    assert args.er_medium is None
    assert args.er_large is None
    assert args.p95_large is None
    assert args.critical_json is None


def test_95_parser_accepts_er_values():
    args = build_parser().parse_args(
        ["--er-medium", "0.06", "--er-large", "0.04", "--p95-large", "1.2"]
    )
    assert args.er_medium == pytest.approx(0.06)
    assert args.er_large == pytest.approx(0.04)
    assert args.p95_large == pytest.approx(1.2)


@pytest.mark.slow
def test_95_main_without_er_is_undecided(tmp_path):
    code = capacity_bench.main(
        [
            "--profiles", "small",
            "--out-dir", str(tmp_path / "onnx"),
            "--repeats", "1",
            "--json", str(tmp_path / "out.json"),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["decision"]["selected"] == "undecided"
    assert len(payload["profiles"]) == 1


@pytest.mark.slow
def test_95_main_with_er_decides(tmp_path):
    code = capacity_bench.main(
        [
            "--profiles", "small",
            "--out-dir", str(tmp_path / "onnx"),
            "--repeats", "1",
            "--er-medium", "0.060",
            "--se-medium", "0.005",
            "--er-large", "0.040",
            "--se-large", "0.004",
            "--p95-large", "1.0",
            "--json", str(tmp_path / "out.json"),
            "--markdown", str(tmp_path / "out.md"),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["decision"]["selected"] == "large"
    assert (tmp_path / "out.md").is_file()
