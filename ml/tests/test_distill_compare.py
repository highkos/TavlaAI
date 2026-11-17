"""Faz 7 Bolum 5.4 / Test 102: ``ml/distill_compare.py`` testleri."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import distill_compare as dc  # noqa: E402


# ----------------------------------------------------------------------
# relative_gain
# ----------------------------------------------------------------------


def test_relative_gain_positive_when_distill_better():
    assert dc.relative_gain(0.10, 0.05) == pytest.approx(0.5)


def test_relative_gain_zero_when_equal():
    assert dc.relative_gain(0.08, 0.08) == pytest.approx(0.0)


def test_relative_gain_negative_when_distill_worse():
    assert dc.relative_gain(0.05, 0.10) == pytest.approx(-1.0)


def test_relative_gain_rejects_zero_control():
    with pytest.raises(dc.DistillCompareError):
        dc.relative_gain(0.0, 0.01)


def test_relative_gain_rejects_negative_control():
    with pytest.raises(dc.DistillCompareError):
        dc.relative_gain(-0.01, 0.01)


def test_relative_gain_rejects_negative_distill():
    with pytest.raises(dc.DistillCompareError):
        dc.relative_gain(0.10, -0.01)


# ----------------------------------------------------------------------
# gain_standard_error
# ----------------------------------------------------------------------


def test_gain_se_matches_closed_form():
    c, sc, d, sd = 0.10, 0.01, 0.05, 0.008
    expected = math.sqrt((sd ** 2) / (c ** 2) + (d ** 2) * (sc ** 2) / (c ** 4))
    assert dc.gain_standard_error(c, sc, d, sd) == pytest.approx(expected)


def test_gain_se_is_zero_for_zero_errors():
    assert dc.gain_standard_error(0.10, 0.0, 0.05, 0.0) == pytest.approx(0.0)


def test_gain_se_grows_with_distill_error():
    small = dc.gain_standard_error(0.10, 0.01, 0.05, 0.001)
    large = dc.gain_standard_error(0.10, 0.01, 0.05, 0.02)
    assert large > small


def test_gain_se_rejects_negative_errors():
    with pytest.raises(dc.DistillCompareError):
        dc.gain_standard_error(0.10, -0.01, 0.05, 0.01)


# ----------------------------------------------------------------------
# gain_interval
# ----------------------------------------------------------------------


def test_gain_interval_is_symmetric_around_gain():
    c, sc, d, sd = 0.10, 0.01, 0.05, 0.008
    low, high = dc.gain_interval(c, sc, d, sd)
    g = dc.relative_gain(c, d)
    assert (low + high) / 2 == pytest.approx(g)


def test_gain_interval_widens_with_z():
    c, sc, d, sd = 0.10, 0.01, 0.05, 0.008
    low1, high1 = dc.gain_interval(c, sc, d, sd, z=1.0)
    low2, high2 = dc.gain_interval(c, sc, d, sd, z=2.0)
    assert (high2 - low2) > (high1 - low1)


def test_gain_interval_rejects_non_positive_z():
    with pytest.raises(dc.DistillCompareError):
        dc.gain_interval(0.10, 0.01, 0.05, 0.008, z=0.0)


# ----------------------------------------------------------------------
# compare / kapi
# ----------------------------------------------------------------------


def test_compare_passes_when_gain_clearly_above_threshold():
    result = dc.compare(0.10, 0.005, 0.05, 0.004)
    assert result.gain == pytest.approx(0.5)
    assert result.passed is True
    assert result.strict_passed is True


def test_compare_fails_when_gain_below_threshold():
    result = dc.compare(0.10, 0.005, 0.09, 0.005)
    assert result.gain == pytest.approx(0.1)
    assert result.passed is False
    assert result.strict_passed is False
    assert "basarisiz" in result.reason


def test_compare_fails_when_interval_crosses_zero():
    # Nokta tahmini esigi asar ama belirsizlik cok buyuk.
    result = dc.compare(0.10, 0.05, 0.05, 0.05)
    assert result.gain == pytest.approx(0.5)
    assert result.low < 0.0
    assert result.passed is False
    assert "alt sinir" in result.reason


def test_compare_boundary_gain_is_accepted():
    # (0.0740 - 0.0555) / 0.0740 = 0.24999999999999994 -> tolerans ile gecer.
    result = dc.compare(0.0740, 0.0001, 0.0555, 0.0001)
    assert result.gain == pytest.approx(0.25, abs=1e-9)
    assert result.passed is True


def test_compare_strict_requires_lower_bound_above_threshold():
    result = dc.compare(0.10, 0.02, 0.05, 0.02)
    assert result.passed is True
    assert result.strict_passed is False


def test_compare_rejects_bad_gain_min():
    with pytest.raises(dc.DistillCompareError):
        dc.compare(0.10, 0.01, 0.05, 0.01, gain_min=0.0)
    with pytest.raises(dc.DistillCompareError):
        dc.compare(0.10, 0.01, 0.05, 0.01, gain_min=1.0)


def test_compare_result_to_dict_has_all_keys():
    result = dc.compare(0.10, 0.01, 0.05, 0.01)
    payload = result.to_dict()
    for key in (
        "erControl",
        "seControl",
        "erDistill",
        "seDistill",
        "gain",
        "se",
        "low",
        "high",
        "gainMin",
        "passed",
        "strictPassed",
        "reason",
    ):
        assert key in payload


def test_compare_is_deterministic():
    a = dc.compare(0.10, 0.01, 0.05, 0.01)
    b = dc.compare(0.10, 0.01, 0.05, 0.01)
    assert a.to_dict() == b.to_dict()


# ----------------------------------------------------------------------
# load_summary
# ----------------------------------------------------------------------


def _write_er(path: Path, mean: float, se: float, count: int = 200) -> Path:
    payload = {
        "model": "ml/runs/x/onnx/model.onnx",
        "split": "all",
        "plies": 2,
        "summary": {
            "split": "all",
            "count": count,
            "mean": mean,
            "median": mean,
            "max": mean * 3,
            "exactMatchRate": 0.3,
            "standardError": se,
            "standardDeviation": se * math.sqrt(count),
        },
        "positions": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_summary_reads_mean_and_se(tmp_path):
    path = _write_er(tmp_path / "er.json", 0.074, 0.0077)
    summary = dc.load_summary(path)
    assert summary["mean"] == pytest.approx(0.074)
    assert summary["standardError"] == pytest.approx(0.0077)
    assert summary["count"] == 200
    assert summary["plies"] == 2


def test_load_summary_rejects_missing_file(tmp_path):
    with pytest.raises(dc.DistillCompareError):
        dc.load_summary(tmp_path / "yok.json")


def test_load_summary_rejects_missing_summary(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"model": "x"}), encoding="utf-8")
    with pytest.raises(dc.DistillCompareError):
        dc.load_summary(path)


def test_load_summary_rejects_missing_mean(tmp_path):
    path = tmp_path / "bad2.json"
    path.write_text(json.dumps({"summary": {"standardError": 0.1}}), encoding="utf-8")
    with pytest.raises(dc.DistillCompareError):
        dc.load_summary(path)


# ----------------------------------------------------------------------
# build_markdown
# ----------------------------------------------------------------------


def test_build_markdown_contains_gate_verdict():
    result = dc.compare(0.10, 0.005, 0.05, 0.004)
    text = dc.build_markdown(result, control_model="a.onnx", distill_model="b.onnx")
    assert "Test 102" in text
    assert "GECTI" in text
    assert "a.onnx" in text
    assert "b.onnx" in text


def test_build_markdown_uses_turkish_decimal_comma():
    result = dc.compare(0.10, 0.005, 0.05, 0.004)
    text = dc.build_markdown(result)
    assert "0,5000" in text
    assert "0.5000" not in text


def test_build_markdown_reports_failure():
    result = dc.compare(0.10, 0.005, 0.09, 0.005)
    text = dc.build_markdown(result)
    assert "BASARISIZ" in text


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_main_returns_zero_when_gate_passes(tmp_path):
    control = _write_er(tmp_path / "c.json", 0.10, 0.005)
    distill = _write_er(tmp_path / "d.json", 0.05, 0.004)
    out = tmp_path / "out.json"
    md = tmp_path / "out.md"
    code = dc.main(
        ["--control", str(control), "--distill", str(distill), "--json", str(out), "--markdown", str(md)]
    )
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["passed"] is True
    assert "Test 102" in md.read_text(encoding="utf-8")


def test_main_returns_one_when_gate_fails(tmp_path):
    control = _write_er(tmp_path / "c.json", 0.10, 0.005)
    distill = _write_er(tmp_path / "d.json", 0.095, 0.005)
    assert dc.main(["--control", str(control), "--distill", str(distill)]) == 1


def test_main_returns_two_on_bad_input(tmp_path):
    control = _write_er(tmp_path / "c.json", 0.10, 0.005)
    assert dc.main(["--control", str(control), "--distill", str(tmp_path / "yok.json")]) == 2


def test_parser_defaults():
    args = dc.build_parser().parse_args(["--control", "a", "--distill", "b"])
    assert args.gain_min == pytest.approx(dc.DISTILL_GAIN_MIN)
    assert args.z == pytest.approx(dc.DISTILL_Z)
