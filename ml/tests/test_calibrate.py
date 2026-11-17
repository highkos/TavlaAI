# -*- coding: utf-8 -*-
"""Faz 7 Asama D - kalibrasyon onarimi testleri."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import calibrate  # noqa: E402
from calibrate import (  # noqa: E402
    CAL_FRACTION,
    SPLIT_SEED,
    CalibrationError,
    apply_affine,
    build_markdown,
    fit_affine,
    gate_verdict,
    load_pairs,
    repair,
    split_pairs,
)


def _synthetic(n=400, slope=0.66, intercept=0.14, noise=0.05, seed=3):
    rng = np.random.default_rng(seed)
    pred = rng.normal(scale=0.7, size=n)
    target = slope * pred + intercept + rng.normal(scale=noise, size=n)
    return [(float(a), float(b)) for a, b in zip(pred, target)]


# ----------------------------------------------------------------------
# Bolme
# ----------------------------------------------------------------------


def test_split_is_deterministic():
    pairs = _synthetic(100)
    a = split_pairs(pairs)
    b = split_pairs(pairs)
    assert a == b


def test_split_sizes():
    cal, val = split_pairs(_synthetic(100), cal_fraction=0.5)
    assert len(cal) == 50
    assert len(val) == 50


def test_split_respects_fraction():
    cal, val = split_pairs(_synthetic(100), cal_fraction=0.25)
    assert len(cal) == 25
    assert len(val) == 75


def test_split_has_no_overlap():
    pairs = _synthetic(60)
    cal, val = split_pairs(pairs)
    assert set(cal).isdisjoint(set(val))
    assert len(cal) + len(val) == len(pairs)


def test_split_rejects_bad_fraction():
    with pytest.raises(CalibrationError):
        split_pairs(_synthetic(20), cal_fraction=0.0)
    with pytest.raises(CalibrationError):
        split_pairs(_synthetic(20), cal_fraction=1.0)


def test_split_rejects_too_few_pairs():
    with pytest.raises(CalibrationError):
        split_pairs([(0.0, 0.0), (1.0, 1.0)])


def test_split_keeps_at_least_one_each():
    cal, val = split_pairs(_synthetic(4), cal_fraction=0.9)
    assert len(cal) >= 1
    assert len(val) >= 1


# ----------------------------------------------------------------------
# Affine
# ----------------------------------------------------------------------


def test_fit_affine_recovers_exact_line():
    pred = np.linspace(-2.0, 2.0, 50)
    target = 0.5 * pred + 0.25
    slope, intercept = fit_affine(pred, target)
    assert slope == pytest.approx(0.5, abs=1e-9)
    assert intercept == pytest.approx(0.25, abs=1e-9)


def test_fit_affine_clamps_extreme_slope():
    pred = np.array([0.0, 1e-6, 2e-6, 3e-6])
    target = np.array([0.0, 1.0, 2.0, 3.0])
    slope, _ = fit_affine(pred, target)
    assert slope <= calibrate.SLOPE_CLAMP[1]


def test_fit_affine_rejects_zero_variance():
    with pytest.raises(CalibrationError):
        fit_affine([1.0, 1.0, 1.0], [0.0, 1.0, 2.0])


def test_fit_affine_rejects_shape_mismatch():
    with pytest.raises(CalibrationError):
        fit_affine([0.0, 1.0], [0.0])


def test_fit_affine_rejects_nan():
    with pytest.raises(CalibrationError):
        fit_affine([0.0, float("nan")], [0.0, 1.0])


def test_apply_affine_is_linear():
    out = apply_affine([0.0, 1.0, 2.0], 2.0, 1.0)
    assert out.tolist() == [1.0, 3.0, 5.0]


# ----------------------------------------------------------------------
# Kapi
# ----------------------------------------------------------------------


def test_gate_verdict_all_pass():
    metrics = {"slope": 1.0, "correlation": 0.9, "mae": 0.1, "std_ratio": 1.0}
    verdict = gate_verdict(metrics)
    assert verdict["passed"] is True
    assert verdict["failed"] == []


def test_gate_verdict_reports_failed_names():
    metrics = {"slope": 0.5, "correlation": 0.9, "mae": 0.3, "std_ratio": 1.0}
    verdict = gate_verdict(metrics)
    assert verdict["passed"] is False
    assert verdict["failed"] == ["mae", "slope"]


def test_gate_verdict_boundaries_are_inclusive():
    metrics = {"slope": 0.85, "correlation": 0.75, "mae": 0.15, "std_ratio": 0.7}
    assert gate_verdict(metrics)["passed"] is True


# ----------------------------------------------------------------------
# Onarim
# ----------------------------------------------------------------------


def test_repair_improves_slope_on_held_out():
    result = repair(_synthetic(400, slope=0.66, intercept=0.14, noise=0.02))
    assert abs(result.after["slope"] - 1.0) < abs(result.before["slope"] - 1.0)


def test_repair_does_not_change_correlation():
    """Dogrusal donusum Pearson korelasyonunu degistirmez."""
    result = repair(_synthetic(400))
    assert result.after["correlation"] == pytest.approx(result.before["correlation"], abs=1e-9)


def test_repair_reduces_mae():
    result = repair(_synthetic(400, slope=0.66, intercept=0.14, noise=0.02))
    assert result.after["mae"] < result.before["mae"]


def test_repair_counts_add_up():
    result = repair(_synthetic(400))
    assert result.count == 400
    assert result.cal_count + result.val_count == 400


def test_repair_uses_only_cal_for_fitting():
    """Kural 10: egim yalnizca CAL kumesinden gelir."""
    pairs = _synthetic(200, seed=11)
    cal, _ = split_pairs(pairs)
    expected_slope, expected_intercept = fit_affine(
        [a for a, _ in cal], [b for _, b in cal]
    )

    result = repair(pairs)

    assert result.slope == pytest.approx(expected_slope, abs=1e-12)
    assert result.intercept == pytest.approx(expected_intercept, abs=1e-12)


def test_repair_metrics_are_computed_on_val_only():
    """Kural 10: raporlanan metrikler VAL'den gelir, CAL'den degil."""
    pairs = _synthetic(200, seed=11)
    _, val = split_pairs(pairs)
    expected = calibrate.calibration_metrics(
        [a for a, _ in val], [b for _, b in val]
    )

    result = repair(pairs)

    assert result.before["slope"] == pytest.approx(expected["slope"], abs=1e-12)
    assert result.before["mae"] == pytest.approx(expected["mae"], abs=1e-12)


def test_repair_to_dict_has_expected_keys():
    payload = repair(_synthetic(100)).to_dict()
    for key in ("count", "calCount", "valCount", "affine", "before", "after", "beforeGate", "afterGate"):
        assert key in payload


def test_repair_is_deterministic():
    pairs = _synthetic(120)
    assert repair(pairs).to_dict() == repair(pairs).to_dict()


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def test_markdown_has_before_after_table():
    text = build_markdown(repair(_synthetic(200)), "pairs.json")
    assert "Onarim oncesi / sonrasi" in text
    assert "Korelasyon degismez" in text
    assert "pairs.json" in text


def test_markdown_uses_turkish_decimal_comma():
    text = build_markdown(repair(_synthetic(200)), "p.json")
    assert "0,85 - 1,15" in text


def test_markdown_states_model_is_not_declared_calibrated():
    text = build_markdown(repair(_synthetic(200)), "p.json")
    assert "modeli kalibre demiyor" in text


# ----------------------------------------------------------------------
# Yukleme / CLI
# ----------------------------------------------------------------------


def test_load_pairs_reads_pairs_key(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"pairs": [[0.1, 0.2], [0.3, 0.4]]}), encoding="utf-8")
    assert load_pairs(str(path)) == [(0.1, 0.2), (0.3, 0.4)]


def test_load_pairs_rejects_missing_pairs(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"cases": []}), encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_pairs(str(path))


def test_cli_writes_outputs(tmp_path):
    src = tmp_path / "pairs.json"
    src.write_text(json.dumps({"pairs": _synthetic(200)}), encoding="utf-8")
    json_path = tmp_path / "out.json"
    md_path = tmp_path / "out.md"
    code = calibrate.main(
        ["--source", str(src), "--json", str(json_path), "--markdown", str(md_path)]
    )
    assert code in (0, 1)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["count"] == 200
    assert md_path.read_text(encoding="utf-8").startswith("# Asama D")


def test_cli_returns_zero_when_gates_pass(tmp_path):
    src = tmp_path / "pairs.json"
    src.write_text(json.dumps({"pairs": _synthetic(400, slope=1.0, intercept=0.0, noise=0.01)}), encoding="utf-8")
    code = calibrate.main(["--source", str(src), "--json", str(tmp_path / "o.json")])
    assert code == 0


def test_default_constants():
    assert CAL_FRACTION == 0.5
    assert SPLIT_SEED == 20261117
