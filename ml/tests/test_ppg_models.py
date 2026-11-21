"""Testler 263-270: modeller arasi ppg karsilastirmasi (F7-104)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
REPO_ROOT = ML.parent
for p in (str(ML), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ppg_models  # noqa: E402


def _match(
    label: str,
    ppg: float,
    se: float,
    games: int = 2000,
    win_rate: float = 0.43,
    er_pol: float | None = None,
    er_val: float | None = None,
) -> ppg_models.ModelPpg:
    return ppg_models.ModelPpg(
        label=label,
        model=f"ml/runs/{label}/onnx/model_v10.onnx",
        path="search1",
        games=games,
        wins=int(round(win_rate * games)),
        win_rate=win_rate,
        ppg=ppg,
        ppg_ci_low=ppg - 1.96 * se,
        ppg_ci_high=ppg + 1.96 * se,
        ppg_std_error=se,
        mean_plies=55.0,
        seed=2026,
        er_policy=er_pol,
        er_value=er_val,
    )


def test_263_pair_difference_matches_hand_computation():
    a = _match("a", -0.3240, 0.0291)
    b = _match("b", -0.1635, 0.0303)
    d = ppg_models.pair_difference(a, b)
    assert d.diff == pytest.approx(-0.1605, abs=1e-9)
    assert d.standard_error == pytest.approx(math.hypot(0.0291, 0.0303), abs=1e-12)
    assert d.ci_low < d.diff < d.ci_high
    assert d.z == pytest.approx(d.diff / d.standard_error, abs=1e-12)
    assert d.significant is True


def test_264_pair_difference_flags_non_significant():
    a = _match("a", -0.1990, 0.0315)
    b = _match("b", -0.1635, 0.0303)
    d = ppg_models.pair_difference(a, b)
    assert abs(d.z) < ppg_models.Z95
    assert d.significant is False


def test_265_pair_difference_rejects_zero_standard_error():
    a = _match("a", -0.1, 0.0)
    b = _match("b", -0.2, 0.0)
    with pytest.raises(ppg_models.PpgModelsError):
        ppg_models.pair_difference(a, b)


def test_266_fit_er_ppg_recovers_known_slope():
    models = [
        _match("m1", 0.0, 0.03, er_pol=0.01),
        _match("m2", -0.2, 0.03, er_pol=0.03),
        _match("m3", -0.4, 0.03, er_pol=0.05),
    ]
    fit = ppg_models.fit_er_ppg(models, "policy")
    assert fit.slope == pytest.approx(-10.0, abs=1e-9)
    assert fit.intercept == pytest.approx(0.1, abs=1e-9)
    assert fit.r_squared == pytest.approx(1.0, abs=1e-9)
    assert fit.points == 3
    assert fit.predict(0.02) == pytest.approx(-0.1, abs=1e-9)


def test_267_fit_er_ppg_needs_two_points():
    models = [_match("m1", 0.0, 0.03, er_pol=0.01)]
    with pytest.raises(ppg_models.PpgModelsError):
        ppg_models.fit_er_ppg(models, "policy")


def test_268_fit_er_ppg_rejects_constant_er():
    models = [
        _match("m1", 0.0, 0.03, er_pol=0.01),
        _match("m2", -0.2, 0.03, er_pol=0.01),
    ]
    with pytest.raises(ppg_models.PpgModelsError):
        ppg_models.fit_er_ppg(models, "policy")


def test_269_build_report_uses_baseline_pairs_and_skips_missing_head():
    models = [
        _match("base", -0.1635, 0.0303, er_pol=0.0270),
        _match("ctl", -0.1990, 0.0315, er_pol=0.0298),
        _match("aug", -0.3240, 0.0291, er_pol=0.0383),
    ]
    report = ppg_models.build_report(models, baseline="base")
    assert [p["a"] for p in report["pairs"]] == ["ctl", "aug"]
    assert all(p["b"] == "base" for p in report["pairs"])
    # er_value is None everywhere -> only the policy fit survives
    assert [f["head"] for f in report["fits"]] == ["policy"]
    assert report["caveat"] == ppg_models.CAVEAT
    md = ppg_models.build_markdown(report)
    assert "ER -> ppg eslemesi" in md
    assert "`aug`" in md
    assert "**evet**" in md


def test_270_parse_model_spec_and_load_match_round_trip(tmp_path):
    payload = {
        "matchVersion": 1,
        "model": "ml/runs/x/onnx/model_v10.onnx",
        "path": "search1",
        "gnubgPlies": 0,
        "games": 2000,
        "pairs": 1000,
        "workers": 3,
        "wins": 753,
        "winRate": 0.3765,
        "ppg": -0.324,
        "ppgCiLow": -0.381,
        "ppgCiHigh": -0.267,
        "ppgStdError": 0.029093559727348665,
        "pairedDiffMean": -0.648,
        "pairedDiffCiLow": -0.76,
        "pairedDiffCiHigh": -0.533,
        "meanPlies": 54.4765,
        "seed": 2026,
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    m = ppg_models.parse_model_spec(f"aug={p},0.038333,0.038675")
    assert m.label == "aug"
    assert m.ppg == pytest.approx(-0.324)
    assert m.er_policy == pytest.approx(0.038333)
    assert m.er_value == pytest.approx(0.038675)
    assert m.ppg_sigma == pytest.approx(0.029093559727348665 * math.sqrt(2000), rel=1e-9)
    # no ER suffix -> both None
    m2 = ppg_models.parse_model_spec(f"plain={p}")
    assert m2.er_policy is None and m2.er_value is None
    with pytest.raises(ppg_models.PpgModelsError):
        ppg_models.parse_model_spec("no-equals-sign")
