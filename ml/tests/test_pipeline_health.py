"""Test 126: pipeline sagligi teshisi (G1-G7).

`faz 7.md` incelemesinin 1.1 maddesi: "sorun olcek degil, pipeline". Bu test
dosyasi o iddiayi olculebilir kilan `ml/pipeline_health.py` modulunun her
kapiyi dogru degerlendirdigini, teshis fonksiyonunun dort sonucu da
uretebildigini ve CLI cikis kodlarinin teshisle tutarli oldugunu dogrular
(ASSUMPTIONS.md F7-20).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import pipeline_health as ph


# ----------------------------------------------------------------------
# Esikler
# ----------------------------------------------------------------------


def test_126a_thresholds_are_the_documented_ones() -> None:
    assert ph.PIP_WIN_RATE_MIN == 0.90
    assert (ph.SLOPE_MIN, ph.SLOPE_MAX) == (0.85, 1.15)
    assert ph.MAE_MAX == 0.15
    assert ph.CORRELATION_MIN == 0.90
    # R-09: onaylanmis bant Faz 6'nin bandi (0,7-1,4); siki bant geri alindi.
    assert (ph.STD_RATIO_MIN, ph.STD_RATIO_MAX) == (0.7, 1.4)
    assert (ph.STD_RATIO_LEGACY_MIN, ph.STD_RATIO_LEGACY_MAX) == (0.85, 1.15)
    assert ph.ER_MAX == 0.02
    # Onay kosulu: lam=1 modu **birim/isaret testi**; bant degil.
    assert ph.TARGET_STD_RATIO_UNIT_TOL == 1e-6
    assert ph.TARGET_STD_RATIO_MAX == 1.5


def test_126a_gate_ids_are_complete_and_labelled() -> None:
    assert ph.GATE_IDS == ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
    for gid in ph.GATE_IDS:
        assert gid in ph.GATE_LABELS
        assert ph.GATE_LABELS[gid]


# ----------------------------------------------------------------------
# G1 - PipBot kazanma orani
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.90, 0.95, 0.995, 1.0])
def test_126b_g1_passes_at_or_above_threshold(value: float) -> None:
    gate = ph.gate_pip_win_rate(value)
    assert gate.gate_id == "G1"
    assert gate.passed is True
    assert gate.value == pytest.approx(value)


@pytest.mark.parametrize("value", [0.0, 0.5, 0.8999])
def test_126b_g1_fails_below_threshold(value: float) -> None:
    assert ph.gate_pip_win_rate(value).passed is False


def test_126b_g1_unmeasured() -> None:
    gate = ph.gate_pip_win_rate(None)
    assert gate.passed is None
    assert gate.value is None
    assert gate.note == "olculmedi"


# ----------------------------------------------------------------------
# G2 - kalibrasyon egimi
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.85, 0.9, 1.0, 1.15])
def test_126c_g2_passes_inside_band(value: float) -> None:
    assert ph.gate_slope(value).passed is True


@pytest.mark.parametrize("value", [0.0, 0.6743, 0.8499, 1.1501, 2.0])
def test_126c_g2_fails_outside_band(value: float) -> None:
    assert ph.gate_slope(value).passed is False


def test_126c_g2_unmeasured() -> None:
    assert ph.gate_slope(None).passed is None


# ----------------------------------------------------------------------
# G3 - MAE
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, 0.1, 0.1499])
def test_126d_g3_passes_below_cap(value: float) -> None:
    assert ph.gate_mae(value).passed is True


@pytest.mark.parametrize("value", [0.15, 0.2683, 1.0])
def test_126d_g3_fails_at_or_above_cap(value: float) -> None:
    assert ph.gate_mae(value).passed is False


def test_126d_g3_unmeasured() -> None:
    assert ph.gate_mae(None).passed is None


# ----------------------------------------------------------------------
# G4 - korelasyon
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.9001, 0.95, 1.0])
def test_126e_g4_passes_above_floor(value: float) -> None:
    assert ph.gate_correlation(value).passed is True


@pytest.mark.parametrize("value", [0.0, 0.5, 0.90])
def test_126e_g4_fails_at_or_below_floor(value: float) -> None:
    assert ph.gate_correlation(value).passed is False


def test_126e_g4_unmeasured() -> None:
    assert ph.gate_correlation(None).passed is None


# ----------------------------------------------------------------------
# G5 - std orani
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.85, 1.0, 1.15])
def test_126f_g5_passes_inside_band(value: float) -> None:
    assert ph.gate_std_ratio(value).passed is True


@pytest.mark.parametrize("value", [0.0, 0.6999, 1.4001, 2.78])
def test_126f_g5_fails_outside_band(value: float) -> None:
    assert ph.gate_std_ratio(value).passed is False


@pytest.mark.parametrize("value", [0.7, 0.8499, 1.3371, 1.1501, 1.4])
def test_126f_g5_passes_in_faz6_band(value: float) -> None:
    """R-09: 1,3371 Faz 6 bandinda **gecer**; siki bantta duser."""
    assert ph.gate_std_ratio(value).passed is True


def test_126f_g5_note_reports_both_bands() -> None:
    gate = ph.gate_std_ratio(1.3371)
    assert gate.passed is True
    assert "siki bant" in gate.note
    assert "DUSTU" in gate.note


def test_126f_g5_unmeasured() -> None:
    assert ph.gate_std_ratio(None).passed is None


# ----------------------------------------------------------------------
# G6 - ER
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, 0.01, 0.0199])
def test_126g_g6_passes_below_target(value: float) -> None:
    assert ph.gate_er(value).passed is True


@pytest.mark.parametrize("value", [0.02, 0.0740, 0.5])
def test_126g_g6_fails_at_or_above_target(value: float) -> None:
    assert ph.gate_er(value).passed is False


def test_126g_g6_unmeasured() -> None:
    assert ph.gate_er(None).passed is None


# ----------------------------------------------------------------------
# G7 - hedef sacilimi
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [1.0, 1.0 + 1e-7, 1.0 - 1e-7, 1.0 + 9e-7])
def test_126h_g7_unit_test_passes_near_one(value: float) -> None:
    """Onay kosulu: ``lam = 1`` modunda kapi **birim/isaret testi**dir."""
    gate = ph.gate_target_std_ratio(value, lam=1.0)
    assert gate.passed is True
    assert gate.display_label == ph.GATE_LABEL_G7_UNIT
    assert "birim/isaret" in gate.note


@pytest.mark.parametrize("value", [0.5, 0.9, 1.0 + 1e-5, 1.5, 3.0227])
def test_126h_g7_unit_test_fails_away_from_one(value: float) -> None:
    """Bant **yok**: 1'den her sapma birim/isaret uyusmazligidir."""
    gate = ph.gate_target_std_ratio(value, lam=1.0)
    assert gate.passed is False
    assert gate.display_label == ph.GATE_LABEL_G7_UNIT


def test_126h_g7_unit_test_is_default_mode() -> None:
    """``lam`` verilmezse varsayilan 1,0 -> birim/isaret testi."""
    assert ph.gate_target_std_ratio(1.0).passed is True
    assert ph.gate_target_std_ratio(0.5).passed is False


def test_126h_g7_lambda_lower_bound_is_derived_from_lambda() -> None:
    """Onay kosulu: ``lam < 1`` alt siniri **lam'dan turetilir**."""
    for lam in (0.1, 0.3, 0.5, 0.7, 0.9, 0.99):
        assert ph.target_std_ratio_lower(lam) == pytest.approx(lam ** (1.0 / (1.0 - lam)))


def test_126h_g7_lambda_lower_bound_tends_to_inverse_e() -> None:
    """``lam -> 1`` icin alt sinir ``1/e``ye yaklasir (keyfi 0,5 degil)."""
    assert ph.target_std_ratio_lower(0.999) == pytest.approx(1.0 / math.e, abs=2e-3)
    assert ph.target_std_ratio_lower(0.7) == pytest.approx(0.30457, abs=1e-4)


def test_126h_g7_lambda_lower_bound_rejects_out_of_range() -> None:
    for lam in (0.0, 1.0, 1.5, -0.2):
        with pytest.raises(ValueError):
            ph.target_std_ratio_lower(lam)


@pytest.mark.parametrize("value", [0.3046, 0.4, 0.6821, 1.0, 1.4999, 1.5])
def test_126h_g7_lambda_band_passes(value: float) -> None:
    """``lam = 0,7``: alt sinir 0,3046, ust sinir 1,5."""
    gate = ph.gate_target_std_ratio(value, lam=0.7)
    assert gate.passed is True
    assert gate.display_label == ph.GATE_LABEL_G7_LAMBDA
    assert "lam^(1/(1-lam))" in gate.note


@pytest.mark.parametrize("value", [0.0, 0.176, 0.3045])
def test_126h_g7_lambda_band_fails_below_derived_floor(value: float) -> None:
    """Olculen 0,176031 (lam=0,7, model yok) **gercek cokme** - duser."""
    gate = ph.gate_target_std_ratio(value, lam=0.7)
    assert gate.passed is False
    assert "coktu" in gate.note


@pytest.mark.parametrize("value", [1.5001, 2.0, 3.0227])
def test_126h_g7_lambda_band_fails_above_ceiling(value: float) -> None:
    """R-08: 3,0227 artik **DUSTU** - tek tarafli kapi bunu gizliyordu."""
    gate = ph.gate_target_std_ratio(value, lam=0.7)
    assert gate.passed is False
    assert "ust sinir" in gate.note


def test_126h_g7_ceiling_is_approved_value() -> None:
    assert ph.TARGET_STD_RATIO_MAX == 1.5


def test_126h_g7_unmeasured() -> None:
    assert ph.gate_target_std_ratio(None).passed is None


def test_126h_g7_nan_ratio_fails() -> None:
    # terminal_std == 0 -> ratio nan -> kapi dusmeli (sessizce gecmemeli).
    assert ph.gate_target_std_ratio(float("nan")).passed is False
    assert ph.gate_target_std_ratio(float("nan"), lam=0.7).passed is False


# ----------------------------------------------------------------------
# target_spread
# ----------------------------------------------------------------------


def test_126i_target_spread_identical_series_ratio_one() -> None:
    z = np.array([1.0, -1.0, 2.0, -2.0, 3.0])
    spread = ph.target_spread(z, z)
    assert spread.count == 5
    assert spread.ratio == pytest.approx(1.0)
    assert spread.zero_share == pytest.approx(0.0)


def test_126i_target_spread_collapsed_targets_ratio_zero() -> None:
    z = np.array([1.0, -1.0, 2.0, -2.0])
    spread = ph.target_spread(np.zeros(4), z)
    assert spread.target_std == pytest.approx(0.0)
    assert spread.ratio == pytest.approx(0.0)
    assert spread.zero_share == pytest.approx(1.0)


def test_126i_target_spread_halved_targets_ratio_half() -> None:
    z = np.array([1.0, -1.0, 2.0, -2.0])
    spread = ph.target_spread(z * 0.5, z)
    assert spread.ratio == pytest.approx(0.5)


def test_126i_target_spread_empty() -> None:
    spread = ph.target_spread([], [])
    assert spread.count == 0
    assert spread.target_std == 0.0
    assert spread.terminal_std == 0.0


def test_126i_target_spread_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        ph.target_spread([1.0, 2.0], [1.0])


def test_126i_target_spread_zero_terminal_std_gives_nan() -> None:
    spread = ph.target_spread([1.0, 2.0], [0.0, 0.0])
    assert np.isnan(spread.ratio)


def test_126i_target_spread_accepts_generators() -> None:
    spread = ph.target_spread((v for v in [1.0, -1.0]), (v for v in [1.0, -1.0]))
    assert spread.count == 2


def test_126i_target_spread_to_dict_keys() -> None:
    d = ph.target_spread([1.0, -1.0], [1.0, -1.0]).to_dict()
    assert set(d) == {
        "count",
        "targetStd",
        "terminalStd",
        "targetMean",
        "terminalMean",
        "zeroShare",
        "ratio",
        "signed",
        "legacyTerminalStd",
        "legacyRatio",
    }


# ----------------------------------------------------------------------
# Artifact okuyuculari
# ----------------------------------------------------------------------


def test_126j_calibration_flat_form() -> None:
    data = {"slope": 0.6743, "mae": 0.2683, "correlation": 0.9016, "std_ratio": 1.3371}
    out = ph.calibration_from_artifact(data)
    assert out["slope"] == pytest.approx(0.6743)
    assert out["mae"] == pytest.approx(0.2683)
    assert out["correlation"] == pytest.approx(0.9016)
    assert out["std_ratio"] == pytest.approx(1.3371)


def test_126j_calibration_prefers_after_block() -> None:
    data = {
        "before": {"slope": 0.6447, "mae": 0.2641},
        "after": {"slope": 0.9584, "mae": 0.1782, "std_ratio": 0.9414},
    }
    out = ph.calibration_from_artifact(data)
    assert out["slope"] == pytest.approx(0.9584)
    assert out["mae"] == pytest.approx(0.1782)
    assert out["std_ratio"] == pytest.approx(0.9414)
    assert out["correlation"] is None


def test_126j_calibration_missing_keys_are_none() -> None:
    out = ph.calibration_from_artifact({"slope": 1.0})
    assert out["slope"] == pytest.approx(1.0)
    assert out["mae"] is None
    assert out["correlation"] is None
    assert out["std_ratio"] is None


def test_126j_calibration_none_input() -> None:
    out = ph.calibration_from_artifact(None)
    assert all(v is None for v in out.values())


def test_126j_pip_win_rate_found() -> None:
    data = {
        "reports": [
            {"opponent": "RandomBot", "winRate": 1.0},
            {"opponent": "PipBot", "winRate": 0.995},
        ]
    }
    assert ph.pip_win_rate_from_artifact(data) == pytest.approx(0.995)


def test_126j_pip_win_rate_case_insensitive() -> None:
    data = {"reports": [{"opponent": "pipbot-v2", "winRate": 0.91}]}
    assert ph.pip_win_rate_from_artifact(data) == pytest.approx(0.91)


def test_126j_pip_win_rate_absent() -> None:
    data = {"reports": [{"opponent": "RandomBot", "winRate": 1.0}]}
    assert ph.pip_win_rate_from_artifact(data) is None


def test_126j_pip_win_rate_none_input() -> None:
    assert ph.pip_win_rate_from_artifact(None) is None


def test_126j_er_flat_form() -> None:
    assert ph.er_from_artifact({"mean": 0.0740}) == pytest.approx(0.0740)


def test_126j_er_summary_form() -> None:
    assert ph.er_from_artifact({"summary": {"mean": 0.0602}}) == pytest.approx(0.0602)


def test_126j_er_absent() -> None:
    assert ph.er_from_artifact({}) is None
    assert ph.er_from_artifact(None) is None


# ----------------------------------------------------------------------
# Teshis
# ----------------------------------------------------------------------


def _report(**kwargs) -> ph.HealthReport:
    return ph.diagnose(**kwargs)


def _healthy_inputs() -> dict:
    return {
        "calibration": {
            "slope": 1.0,
            "mae": 0.10,
            "correlation": 0.95,
            "std_ratio": 1.0,
        },
        "eval_report": {"reports": [{"opponent": "PipBot", "winRate": 0.99}]},
        "er_report": {"mean": 0.01},
        "spread": ph.target_spread([1.0, -1.0], [1.0, -1.0]),
    }


def test_126k_verdict_healthy_when_all_gates_pass() -> None:
    report = _report(**_healthy_inputs())
    assert report.failed == []
    assert report.verdict == ph.VERDICT_HEALTHY
    assert report.strength_gap is False


def test_126k_verdict_healthy_with_strength_gap() -> None:
    inputs = _healthy_inputs()
    inputs["er_report"] = {"mean": 0.0740}
    report = _report(**inputs)
    assert report.failed == ["G6"]
    assert report.verdict == ph.VERDICT_HEALTHY
    assert report.strength_gap is True


def test_126k_verdict_pipeline_when_value_gate_fails() -> None:
    inputs = _healthy_inputs()
    inputs["calibration"] = {
        "slope": 0.6743,
        "mae": 0.2683,
        "correlation": 0.9016,
        "std_ratio": 1.3371,
    }
    report = _report(**inputs)
    # Adim 0: "pipeline" nedensel iddia; olcek kaniti yoksa etiket belirsiz.
    assert report.verdict == ph.VERDICT_UNDETERMINED
    assert report.strength_gap is False
    # R-09: 1,3371 artik G5'ten gecmez; kalan iki deger kapisi duser.
    assert set(report.failed) == {"G2", "G3"}


def test_126k_verdict_pipeline_requires_scaling_evidence() -> None:
    """Ayni girdi + olcek kaniti -> ``pipeline``; kanit yoksa ``belirsiz``."""
    inputs = _healthy_inputs()
    inputs["calibration"] = {
        "slope": 0.6743,
        "mae": 0.2683,
        "correlation": 0.9016,
        "std_ratio": 1.3371,
    }
    assert _report(**inputs).verdict == ph.VERDICT_UNDETERMINED
    inputs["scaling"] = {"slope": 0.0, "ciLow": -0.01, "ciHigh": 0.01}
    assert _report(**inputs).verdict == ph.VERDICT_PIPELINE


def test_126k_verdict_scale_when_scaling_helps() -> None:
    """Deger kapisi duser ama egim esigin uzerinde -> ``olcek``."""
    inputs = _healthy_inputs()
    inputs["calibration"] = {
        "slope": 0.6743,
        "mae": 0.2683,
        "correlation": 0.9016,
        "std_ratio": 1.3371,
    }
    inputs["scaling"] = {"slope": 0.05, "ciLow": 0.03, "ciHigh": 0.07}
    assert _report(**inputs).verdict == ph.VERDICT_SCALE


def test_126k_verdict_foundation_when_g1_fails() -> None:
    inputs = _healthy_inputs()
    inputs["eval_report"] = {"reports": [{"opponent": "PipBot", "winRate": 0.40}]}
    report = _report(**inputs)
    assert report.verdict == ph.VERDICT_FOUNDATION


def test_126k_verdict_foundation_dominates_pipeline() -> None:
    inputs = _healthy_inputs()
    inputs["eval_report"] = {"reports": [{"opponent": "PipBot", "winRate": 0.10}]}
    inputs["calibration"] = {"slope": 0.1, "mae": 0.9, "correlation": 0.1, "std_ratio": 3.0}
    report = _report(**inputs)
    assert report.verdict == ph.VERDICT_FOUNDATION


def test_126k_verdict_unknown_without_g1() -> None:
    report = _report(calibration={"slope": 1.0})
    assert report.verdict == ph.VERDICT_UNKNOWN
    assert report.strength_gap is False


def test_126k_verdict_unknown_with_no_inputs() -> None:
    report = _report()
    assert report.verdict == ph.VERDICT_UNKNOWN
    assert report.measured == []


def test_126k_verdict_unknown_when_value_gates_unmeasured() -> None:
    """G1 gecse bile deger kapilari olculmediyse "saglikli" denemez."""
    report = _report(eval_report={"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    assert report.failed == []
    assert report.verdict == ph.VERDICT_UNKNOWN


def test_126k_verdict_healthy_ignores_unmeasured_g6() -> None:
    """G6 (ER) olculmemis olsa da pipeline sagligi iddia edilebilir."""
    inputs = _healthy_inputs()
    del inputs["er_report"]
    report = _report(**inputs)
    assert report.by_id("G6").passed is None
    assert report.verdict == ph.VERDICT_HEALTHY
    assert report.strength_gap is False


def test_126k_g7_failure_alone_is_undetermined_without_scaling() -> None:
    inputs = _healthy_inputs()
    inputs["spread"] = ph.target_spread(np.zeros(4), [1.0, -1.0, 2.0, -2.0])
    report = _report(**inputs)
    assert report.failed == ["G7"]
    assert report.verdict == ph.VERDICT_UNDETERMINED
    inputs["scaling"] = {"slope": 0.0, "ciLow": -0.01, "ciHigh": 0.01}
    assert _report(**inputs).verdict == ph.VERDICT_PIPELINE


def test_126k_g4_failure_alone_is_undetermined_without_scaling() -> None:
    inputs = _healthy_inputs()
    inputs["calibration"] = {
        "slope": 1.0,
        "mae": 0.10,
        "correlation": 0.50,
        "std_ratio": 1.0,
    }
    report = _report(**inputs)
    assert report.failed == ["G4"]
    assert report.verdict == ph.VERDICT_UNDETERMINED
    inputs["scaling"] = {"slope": 0.0, "ciLow": -0.01, "ciHigh": 0.01}
    assert _report(**inputs).verdict == ph.VERDICT_PIPELINE


def test_126k_gate_order_is_stable() -> None:
    report = _report(**_healthy_inputs())
    assert [g.gate_id for g in report.gates] == list(ph.GATE_IDS)


def test_126k_by_id_returns_none_for_unknown() -> None:
    report = _report(**_healthy_inputs())
    assert report.by_id("G99") is None
    assert report.by_id("G1") is not None


def test_126k_passed_and_measured_lists() -> None:
    report = _report(calibration={"slope": 1.0})
    assert report.measured == ["G2"]
    assert report.passed == ["G2"]
    assert report.failed == []


def test_126k_sources_are_copied() -> None:
    report = _report(sources={"calibration": "a.json"})
    assert report.sources == {"calibration": "a.json"}
    report.sources["x"] = "y"
    assert "x" not in _report(sources={"calibration": "a.json"}).sources


# ----------------------------------------------------------------------
# to_dict
# ----------------------------------------------------------------------


def test_126l_to_dict_shape() -> None:
    d = _report(**_healthy_inputs()).to_dict()
    assert d["verdict"] == ph.VERDICT_HEALTHY
    assert d["strengthGap"] is False
    assert len(d["gates"]) == 7
    assert d["spread"]["count"] == 2
    assert d["thresholds"]["erMax"] == pytest.approx(0.02)


def test_126l_to_dict_spread_none() -> None:
    d = _report().to_dict()
    assert d["spread"] is None


def test_126l_to_dict_is_json_serialisable() -> None:
    d = _report(**_healthy_inputs()).to_dict()
    text = json.dumps(d, sort_keys=True)
    assert "verdict" in text


def test_126l_gate_to_dict_has_label() -> None:
    d = ph.gate_er(0.01).to_dict()
    assert d["gate"] == "G6"
    assert d["label"] == ph.GATE_LABELS["G6"]
    assert d["passed"] is True


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def test_126m_markdown_contains_all_gates() -> None:
    md = ph.build_markdown(_report(**_healthy_inputs()))
    for gid in ph.GATE_IDS:
        assert "| " + gid + " |" in md


def test_126m_markdown_states_verdict() -> None:
    md = ph.build_markdown(_report(**_healthy_inputs()))
    assert "**`" + ph.VERDICT_HEALTHY + "`**" in md


def test_126m_markdown_pipeline_text() -> None:
    inputs = _healthy_inputs()
    inputs["calibration"] = {"slope": 0.5, "mae": 0.5, "correlation": 0.5, "std_ratio": 2.0}
    inputs["scaling"] = {"slope": 0.0, "ciLow": -0.01, "ciHigh": 0.01}
    md = ph.build_markdown(_report(**inputs))
    assert ph.VERDICT_TEXT[ph.VERDICT_PIPELINE] in md


def test_126m_markdown_undetermined_text() -> None:
    inputs = _healthy_inputs()
    inputs["calibration"] = {"slope": 0.5, "mae": 0.5, "correlation": 0.5, "std_ratio": 2.0}
    md = ph.build_markdown(_report(**inputs))
    assert ph.VERDICT_TEXT[ph.VERDICT_UNDETERMINED] in md


def test_126m_markdown_strength_gap_note() -> None:
    inputs = _healthy_inputs()
    inputs["er_report"] = {"mean": 0.5}
    md = ph.build_markdown(_report(**inputs))
    assert "Guc boslugu" in md


def test_126m_markdown_spread_section_only_when_measured() -> None:
    assert "Hedef sacilimi (G7)" in ph.build_markdown(_report(**_healthy_inputs()))
    assert "Hedef sacilimi (G7)" not in ph.build_markdown(_report())


def test_126m_markdown_sources_section() -> None:
    md = ph.build_markdown(_report(sources={"er": "ml/artifacts/x.json"}))
    assert "## 5. Kaynaklar" in md
    assert "`ml/artifacts/x.json`" in md


def test_126m_markdown_ends_with_newline() -> None:
    assert ph.build_markdown(_report()).endswith("\n")


def test_126m_markdown_unmeasured_marker() -> None:
    md = ph.build_markdown(_report())
    assert "olculmedi" in md


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_126n_cli_exit_healthy(tmp_path: Path) -> None:
    cal = _write(tmp_path / "cal.json", {"slope": 1.0, "mae": 0.1, "correlation": 0.95, "std_ratio": 1.0})
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    er = _write(tmp_path / "er.json", {"mean": 0.01})
    np.save(tmp_path / "t.npy", np.array([1.0, -1.0, 2.0, -2.0]))
    np.save(tmp_path / "z.npy", np.array([1.0, -1.0, 2.0, -2.0]))
    code = ph.main(
        [
            "--calibration",
            str(cal),
            "--eval",
            str(ev),
            "--er",
            str(er),
            "--targets",
            str(tmp_path / "t.npy"),
            "--terminals",
            str(tmp_path / "z.npy"),
            "--quiet",
        ]
    )
    assert code == 0


def test_126n_cli_exit_pipeline(tmp_path: Path) -> None:
    cal = _write(tmp_path / "cal.json", {"slope": 0.5, "mae": 0.5, "correlation": 0.5, "std_ratio": 2.0})
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    # Adim 0: olcek kaniti yoksa cikis kodu 4 (belirsiz).
    assert ph.main(["--calibration", str(cal), "--eval", str(ev), "--quiet"]) == 4
    sc = _write(tmp_path / "sc.json", {"slope": 0.0, "ciLow": -0.01, "ciHigh": 0.01})
    code = ph.main(
        ["--calibration", str(cal), "--eval", str(ev), "--scaling", str(sc), "--quiet"]
    )
    assert code == 1


def test_126n_cli_exit_scale(tmp_path: Path) -> None:
    cal = _write(tmp_path / "cal.json", {"slope": 0.5, "mae": 0.5, "correlation": 0.5, "std_ratio": 2.0})
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    sc = _write(tmp_path / "sc.json", {"slope": 0.05, "ciLow": 0.03, "ciHigh": 0.07})
    code = ph.main(
        ["--calibration", str(cal), "--eval", str(ev), "--scaling", str(sc), "--quiet"]
    )
    assert code == 5


def test_126n_cli_exit_foundation(tmp_path: Path) -> None:
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.1}]})
    code = ph.main(["--eval", str(ev), "--quiet"])
    assert code == 2


def test_126n_cli_exit_unknown(tmp_path: Path) -> None:
    assert ph.main(["--quiet"]) == 3


def test_126n_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    out_json = tmp_path / "out" / "r.json"
    out_md = tmp_path / "out" / "r.md"
    ph.main(
        [
            "--eval",
            str(ev),
            "--json",
            str(out_json),
            "--markdown",
            str(out_md),
            "--quiet",
        ]
    )
    assert out_json.is_file()
    assert out_md.is_file()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    # Yalnizca G1 olculdu: deger kapilari eksik -> "saglikli" denemez.
    assert data["verdict"] == ph.VERDICT_UNKNOWN
    assert "Kapilar" in out_md.read_text(encoding="utf-8")


def test_126n_cli_npy_targets_and_terminals(tmp_path: Path) -> None:
    np.save(tmp_path / "t.npy", np.array([1.0, -1.0, 2.0, -2.0]))
    np.save(tmp_path / "z.npy", np.array([1.0, -1.0, 2.0, -2.0]))
    ev = _write(tmp_path / "ev.json", {"reports": [{"opponent": "PipBot", "winRate": 0.99}]})
    out_json = tmp_path / "r.json"
    ph.main(
        [
            "--eval",
            str(ev),
            "--targets",
            str(tmp_path / "t.npy"),
            "--terminals",
            str(tmp_path / "z.npy"),
            "--json",
            str(out_json),
            "--quiet",
        ]
    )
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["spread"]["count"] == 4
    assert data["spread"]["ratio"] == pytest.approx(1.0)


def test_126n_cli_missing_artifact_is_treated_as_unmeasured(tmp_path: Path) -> None:
    code = ph.main(["--calibration", str(tmp_path / "nope.json"), "--quiet"])
    assert code == 3


def test_126n_cli_parser_defaults() -> None:
    args = ph.build_parser().parse_args([])
    assert args.lam == pytest.approx(1.0)
    assert args.shards is None
    assert args.model is None
    assert args.quiet is False


# ----------------------------------------------------------------------
# Zero-value model (G7 onkosulu)
# ----------------------------------------------------------------------


def test_126o_zero_value_model_returns_zeros() -> None:
    import torch

    model = ph._zero_value_model()
    out = model(torch.zeros((5, 221), dtype=torch.float32))
    assert out.shape == (5,)
    assert float(out.abs().sum()) == pytest.approx(0.0)


def test_126o_zero_value_model_eval_and_to_are_chainable() -> None:
    model = ph._zero_value_model()
    assert model.eval() is model
    assert model.to("cpu") is model


# ----------------------------------------------------------------------
# Gercek artifact'lar (varsa)
# ----------------------------------------------------------------------


ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


@pytest.mark.parametrize(
    "name",
    [
        "stage_h_calibration_2ply.json",
        "stage_h_eval_pip.json",
        "stage_h_er_2ply.json",
    ],
)
def test_126p_real_artifacts_parse(name: str) -> None:
    path = ARTIFACTS / name
    if not path.is_file():
        pytest.skip("artifact yok: " + name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if "calibration" in name:
        out = ph.calibration_from_artifact(data)
        assert out["slope"] is not None
    elif "eval" in name:
        assert ph.pip_win_rate_from_artifact(data) is not None
    else:
        assert ph.er_from_artifact(data) is not None


def test_126p_real_verdict_is_pipeline() -> None:
    """F7-20: mevcut artifact'larla teshis ``pipeline`` olmali."""
    paths = {
        "calibration": ARTIFACTS / "stage_h_calibration_2ply.json",
        "eval": ARTIFACTS / "stage_h_eval_pip.json",
        "er": ARTIFACTS / "stage_h_er_2ply.json",
    }
    if not all(p.is_file() for p in paths.values()):
        pytest.skip("artifact eksik")
    report = ph.diagnose(
        calibration=json.loads(paths["calibration"].read_text(encoding="utf-8")),
        eval_report=json.loads(paths["eval"].read_text(encoding="utf-8")),
        er_report=json.loads(paths["er"].read_text(encoding="utf-8")),
    )
    # Adim 0: gercek artefaktlarda ogrenme egrisi olculmedi -> belirsiz.
    assert report.verdict == ph.VERDICT_UNDETERMINED
    assert report.scaling_evidence == ph.SCALING_NONE
    assert report.by_id("G1").passed is True
    assert report.by_id("G2").passed is False
    assert report.by_id("G3").passed is False
    # R-09: 1,3371 Faz 6 bandinda gecer; siki bant notu bunu kaydeder.
    assert report.by_id("G5").passed is True
    assert "DUSTU" in report.by_id("G5").note
