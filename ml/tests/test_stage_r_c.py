"""Faz 7-R Asama R-C testleri (Test 134-138).

R-T7  ``G7_TwoSided``              -- G7 ust siniri var; 3,02 DUSTU
R-T8  ``G7_Lambda1_RatioIsOne``    -- lam=1 + model yok => oran = 1 (+-1e-6)
R-T9  ``Verdict_PairedFirst``      -- GA sifiri iceriyorsa nokta tahmin pipeline diyemez
R-T10 ``Verdict_NoCapacityInference`` -- veri yetersizse ``veri-yetersiz``
R-T11 ``LearningCurve_Runs``       -- 1x/2x/4x/8x noktalari + egim GA'si
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import gnubg_distill as gd
import learning_curve as lc
import pipeline_health as ph
import shards as shard_mod


# ----------------------------------------------------------------------
# Test 134 -- R-T7: G7 cift tarafli
# ----------------------------------------------------------------------


def test_134_g7_has_an_upper_bound() -> None:
    assert ph.TARGET_STD_RATIO_MAX == 1.5


def test_134_g7_lambda_one_is_a_unit_sign_test() -> None:
    """Onay kosulu: ``lam = 1`` modu **birim/isaret testi** olarak adlandirilir."""
    gate = ph.gate_target_std_ratio(1.0, lam=1.0)
    assert gate.passed is True
    assert gate.display_label == ph.GATE_LABEL_G7_UNIT
    assert "Birim/isaret" in gate.display_label
    assert ph.TARGET_STD_RATIO_UNIT_TOL == 1e-6


def test_134_g7_lambda_one_tolerance_is_tight() -> None:
    """Bant yok: 1'den 1e-5 sapma **duser**, 1e-7 sapma gecer."""
    assert ph.gate_target_std_ratio(1.0 + 1e-7, lam=1.0).passed is True
    assert ph.gate_target_std_ratio(1.0 + 1e-5, lam=1.0).passed is False


def test_134_g7_measured_anomaly_now_fails() -> None:
    """Faz 7'de olculen 3,0227 artik **DUSTU** (tek tarafli kapi gizliyordu)."""
    gate = ph.gate_target_std_ratio(3.0227, lam=0.7)
    assert gate.passed is False
    assert gate.value == pytest.approx(3.0227)
    assert "ust sinir" in gate.note


def test_134_g7_healthy_ratio_passes() -> None:
    assert ph.gate_target_std_ratio(1.0, lam=1.0).passed is True
    assert ph.gate_target_std_ratio(0.6821, lam=0.7).passed is True


def test_134_g7_collapse_still_fails() -> None:
    """Olculen 0,176031 (lam=0,7, model yok) gercek cokme - duser."""
    assert ph.gate_target_std_ratio(0.176, lam=0.7).passed is False


def test_134_g7_lambda_floor_is_derived_not_arbitrary() -> None:
    """Onay kosulu: ``lam < 1`` alt siniri lam'dan turetilir (0,5 degil)."""
    assert ph.target_std_ratio_lower(0.7) == pytest.approx(0.7 ** (1.0 / 0.3))
    assert ph.target_std_ratio_lower(0.7) == pytest.approx(0.30457, abs=1e-4)
    assert ph.target_std_ratio_lower(0.7) != pytest.approx(0.5)


def test_134_g7_label_states_the_band() -> None:
    assert "1,5" in ph.GATE_LABELS["G7"]
    assert "lam^(1/(1-lam))" in ph.GATE_LABELS["G7"]


def test_134_g7_thresholds_are_exported() -> None:
    report = ph.diagnose()
    data = report.to_dict()
    assert data["thresholds"]["targetStdRatioMax"] == 1.5
    assert data["thresholds"]["targetStdRatioUnitTol"] == 1e-6
    assert data["thresholds"]["lam"] == 1.0
    assert data["thresholds"]["targetStdRatioLower"] is None


# ----------------------------------------------------------------------
# Test 134b -- R-09: G5 onaylanmis Faz 6 bandina dondu
# ----------------------------------------------------------------------


def test_134b_g5_uses_the_faz6_band() -> None:
    """``Faz 6 v3.md`` 6.3 ve 13.2: ``0,7 <= oran <= 1,4``."""
    assert (ph.STD_RATIO_MIN, ph.STD_RATIO_MAX) == (0.7, 1.4)


def test_134b_g5_measured_value_passes_the_faz6_band() -> None:
    gate = ph.gate_std_ratio(1.3371)
    assert gate.passed is True


def test_134b_g5_reports_both_bands() -> None:
    gate = ph.gate_std_ratio(1.3371)
    assert "siki bant" in gate.note
    assert "DUSTU" in gate.note
    assert (ph.STD_RATIO_LEGACY_MIN, ph.STD_RATIO_LEGACY_MAX) == (0.85, 1.15)


def test_134b_g5_label_names_the_faz6_band() -> None:
    assert "0,7" in ph.GATE_LABELS["G5"]
    assert "1,4" in ph.GATE_LABELS["G5"]


def test_134b_g5_still_catches_the_faz5_value() -> None:
    """Faz 5'te olculen 2,78 her iki bantta da duser."""
    assert ph.gate_std_ratio(2.78).passed is False


# ----------------------------------------------------------------------
# Test 135 -- R-T8: lam=1 + model yok => oran = 1
# ----------------------------------------------------------------------


def test_135_signed_terminal_series_alternates() -> None:
    out = ph.signed_terminal_series(2.0, [0, 1, 2, 3], 4)
    assert list(out) == [2.0, -2.0, 2.0, -2.0]


def test_135_signed_terminal_series_matches_td_chain() -> None:
    """``td_lambda_targets`` ile birebir ayni isaret: y[T-2] = -z."""
    import td_lambda

    z = 3.0
    n = 5
    y = td_lambda.td_lambda_targets(np.zeros(n), z, lam=1.0)
    signed = ph.signed_terminal_series(z, range(n), n)
    assert np.allclose(y, signed)


def test_135_lambda1_ratio_is_exactly_one() -> None:
    """lam=1'de hedefler tam olarak +-z'dir; oran 1 cikmalidir."""
    rng = np.random.default_rng(7)
    zs = rng.choice([-3.0, -2.0, -1.0, 1.0, 2.0, 3.0], size=400)
    lengths = rng.integers(2, 12, size=400)
    targets: list[float] = []
    terminals: list[float] = []
    for z, n in zip(zs, lengths):
        targets.extend(ph.signed_terminal_series(float(z), range(int(n)), int(n)))
        terminals.extend(ph.signed_terminal_series(float(z), range(int(n)), int(n)))
    spread = ph.target_spread(targets, terminals)
    assert spread.ratio == pytest.approx(1.0, abs=1e-6)


def test_135_unsigned_terminals_inflate_the_ratio() -> None:
    """R-08 mekanizmasi: isaretsiz z ile oran yapisal olarak 1'i asar."""
    rng = np.random.default_rng(11)
    zs = rng.choice([-2.0, -1.0, 1.0, 2.0], size=500)
    lengths = rng.integers(2, 10, size=500)
    targets: list[float] = []
    signed: list[float] = []
    unsigned: list[float] = []
    for z, n in zip(zs, lengths):
        targets.extend(ph.signed_terminal_series(float(z), range(int(n)), int(n)))
        signed.extend(ph.signed_terminal_series(float(z), range(int(n)), int(n)))
        unsigned.extend([float(z)] * int(n))
    good = ph.target_spread(targets, signed, legacy_terminals=unsigned)
    assert good.ratio == pytest.approx(1.0, abs=1e-6)
    assert good.legacy_ratio > 1.0
    assert good.signed is True


def test_135_spread_from_shards_uses_signed_terminals(tmp_path: Path) -> None:
    """Gercek shard uzerinden: lam=1 => oran 1, eski olcum > 1."""
    games = _synthetic_games()
    path = tmp_path / "s.bgsp"
    shard_mod.write_shard(path, shard_mod.ShardHeader(), games)
    spread = ph.spread_from_shards([path], model_path=None, lam=1.0)
    assert spread.count > 0
    assert spread.ratio == pytest.approx(1.0, abs=1e-6)
    assert spread.legacy_ratio > 1.0


def _synthetic_games() -> list[shard_mod.GameRecord]:
    """Kazanan/karisik isaretli, 4 kararli iki sentetik oyun."""
    rng = np.random.default_rng(3)
    games: list[shard_mod.GameRecord] = []
    for gid, (winner, points) in enumerate(((1, 2), (-1, 1))):
        decisions: list[shard_mod.DecisionRecord] = []
        for t in range(4):
            vec = rng.normal(size=shard_mod.VECTOR_SIZE).astype(np.float32)
            decisions.append(
                shard_mod.DecisionRecord(
                    mover=1 if t % 2 == 0 else -1,
                    flags=shard_mod.DEC_IS_LEARNER,
                    candidate_total=1,
                    search_value=0.0,
                    chosen_vector=vec,
                )
            )
        games.append(
            shard_mod.GameRecord(
                game_id=gid,
                learner_side=1,
                flags=0,
                cube_value=1,
                decisions=decisions,
                winner=winner,
                result_type=0,
                result_points=points,
            )
        )
    return games


# ----------------------------------------------------------------------
# Test 136 -- R-T9: once eslesmis GA
# ----------------------------------------------------------------------


def test_136_point_estimate_below_target_cannot_say_pipeline() -> None:
    """R-07'nin tam kalbi: nokta tahmini hedefin altinda, GA ust siniri ustunde."""
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.041}
    assert gd.distill_verdict(0.0740, 0.0299, paired=paired) != gd.VERDICT_TEACHER_EFFECTIVE


def test_136_pipeline_requires_ci_upper_below_target() -> None:
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert gd.distill_verdict(0.0740, 0.0299, paired=paired) == gd.VERDICT_TEACHER_EFFECTIVE


def test_136_no_paired_evidence_is_unproven() -> None:
    assert gd.distill_verdict(0.0740, 0.0001) == gd.VERDICT_UNPROVEN


def test_136_ci_including_zero_is_unproven() -> None:
    paired = {"n": 300, "meanDiff": 0.0176, "excludesZero": False, "ciHighAfter": 0.07}
    assert gd.distill_verdict(0.0740, 0.0500, paired=paired) == gd.VERDICT_UNPROVEN


def test_136_paired_er_test_reports_absolute_ci() -> None:
    before = {"p%d" % i: 0.20 for i in range(60)}
    after = {"p%d" % i: 0.10 + 0.001 * i for i in range(60)}
    out = gd.paired_er_test(before, after, resamples=2000, seed=5)
    assert out["n"] == 60
    assert out["ciLowAfter"] < out["meanAfter"] < out["ciHighAfter"]
    assert out["excludesZero"] is True
    assert out["meanDiff"] > 0.0


def test_136_paired_er_test_is_deterministic() -> None:
    before = {"p%d" % i: 0.2 for i in range(30)}
    after = {"p%d" % i: 0.1 for i in range(30)}
    a = gd.paired_er_test(before, after, resamples=500, seed=9)
    b = gd.paired_er_test(before, after, resamples=500, seed=9)
    assert a["ciLowAfter"] == b["ciLowAfter"]
    assert a["ciHighAfter"] == b["ciHighAfter"]


def test_136_paired_er_test_too_few_positions() -> None:
    out = gd.paired_er_test({"p1": 0.5}, {"p1": 0.1})
    assert out["n"] == 1
    assert out["excludesZero"] is False


# ----------------------------------------------------------------------
# Test 137 -- R-T10: kapasite cikarimi yok, veri-yetersiz var
# ----------------------------------------------------------------------


def test_137_insufficient_data_when_n_below_required() -> None:
    paired = {"n": 70, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert (
        gd.distill_verdict(0.0740, 0.0299, paired=paired, required_n=285)
        == gd.VERDICT_INSUFFICIENT_DATA
    )


def test_137_sufficient_data_when_n_meets_required() -> None:
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert (
        gd.distill_verdict(0.0740, 0.0299, paired=paired, required_n=285)
        == gd.VERDICT_TEACHER_EFFECTIVE
    )


def test_137_capacity_is_never_returned() -> None:
    paired = {"n": 300, "meanDiff": 0.0, "excludesZero": False, "ciHighAfter": 0.5}
    for before, after in (
        (0.0740, 0.0740),
        (0.0740, 0.0900),
        (0.10, 0.0801),
        (0.0, 0.5),
        (0.5, 0.5),
    ):
        assert gd.distill_verdict(before, after, paired=paired) != gd.VERDICT_CAPACITY


def test_137_capacity_text_says_it_was_removed() -> None:
    text = gd.VERDICT_TEXT[gd.VERDICT_CAPACITY]
    assert "Kaldirildi" in text
    assert "learning_curve" in text


def test_137_insufficient_data_text_exists() -> None:
    assert gd.VERDICT_INSUFFICIENT_DATA == "veri-yetersiz"
    assert gd.VERDICT_INSUFFICIENT_DATA in gd.VERDICT_TEXT


def test_137_detail_reports_no_capacity_inference() -> None:
    paired = {"n": 300, "meanDiff": 0.0, "excludesZero": False, "ciHighAfter": 0.5}
    detail = gd.distill_verdict_detail(0.0740, 0.0740, paired=paired)
    assert detail["capacityInference"] is False
    assert detail["verdict"] == gd.VERDICT_UNPROVEN


def test_137_cli_exit_code_five_for_insufficient_data(tmp_path: Path) -> None:
    before = tmp_path / "b.json"
    after = tmp_path / "a.json"
    before.write_text(
        json.dumps({"positions": [{"name": "p%d" % i, "equityLoss": 0.2} for i in range(20)]}),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps({"positions": [{"name": "p%d" % i, "equityLoss": 0.1} for i in range(20)]}),
        encoding="utf-8",
    )
    code = gd.main(
        [
            "verdict",
            "--before", "0.2",
            "--after", "0.1",
            "--er-before-json", str(before),
            "--er-after-json", str(after),
            "--required-n", "285",
            "--quiet",
        ]
    )
    assert code == 5


# ----------------------------------------------------------------------
# Test 138 -- R-T11: ogrenme egrisi
# ----------------------------------------------------------------------


def _fake_train(positions: int, seed: int) -> dict:
    """Sentetik hat: ER ~ 0.10 - 0.02*log2(positions/100) + gurultu."""
    rng = np.random.default_rng(seed + positions)
    base = 0.10 - 0.02 * np.log2(positions / 100.0)
    n = 200
    return {
        "losses": {
            "policy": list(np.maximum(0.0, rng.normal(base, 0.05, size=n))),
            "value": list(np.maximum(0.0, rng.normal(base * 1.1, 0.06, size=n))),
            "search1": list(np.maximum(0.0, rng.normal(base * 0.5, 0.03, size=n))),
        },
        "slope": 0.9,
        "mae": 0.2,
        "inSampleLoss": 0.01,
        "heldOutLoss": base,
    }


def test_138_curve_produces_all_multipliers() -> None:
    report = lc.run_curve(
        sizes=[100, 200, 400, 800],
        train_fn=_fake_train,
        seed=1,
        resamples=500,
    )
    assert [p.multiplier for p in report.points] == [1, 2, 4, 8]
    assert [p.positions for p in report.points] == [100, 200, 400, 800]


def test_138_curve_reports_three_paths() -> None:
    report = lc.run_curve(sizes=[100, 200], train_fn=_fake_train, resamples=200)
    for point in report.points:
        assert set(point.means) == {"policy", "value", "search1"}


def test_138_curve_reports_slope_with_ci() -> None:
    report = lc.run_curve(
        sizes=[100, 200, 400, 800], train_fn=_fake_train, seed=2, resamples=500
    )
    entry = report.slopes["policy"]
    assert entry["slope"] < 0.0
    assert entry["ciLow"] <= entry["slope"] <= entry["ciHigh"]
    assert entry["resamples"] == 500


def test_138_curve_separates_in_sample_from_held_out() -> None:
    report = lc.run_curve(sizes=[100, 200], train_fn=_fake_train, resamples=200)
    for point in report.points:
        assert point.in_sample_loss is not None
        assert point.held_out_loss is not None
        assert point.in_sample_loss != point.held_out_loss


def test_138_curve_decision_is_three_state() -> None:
    report = lc.run_curve(
        sizes=[100, 200, 400, 800], train_fn=_fake_train, seed=3, resamples=500
    )
    assert report.decision in (
        lc.DECISION_SCALES,
        lc.DECISION_PIPELINE,
        lc.DECISION_UNDETERMINED,
        lc.DECISION_NO_DATA,
    )


def test_138_flat_curve_is_pipeline() -> None:
    def flat(positions: int, seed: int) -> dict:
        rng = np.random.default_rng(seed + positions)
        return {"losses": {"policy": list(np.abs(rng.normal(0.05, 0.01, size=300)))}}

    report = lc.run_curve(
        sizes=[100, 200, 400, 800], train_fn=flat, seed=4, resamples=1000
    )
    assert report.decision == lc.DECISION_PIPELINE


def test_138_steep_curve_is_scales() -> None:
    def steep(positions: int, seed: int) -> dict:
        rng = np.random.default_rng(seed + positions)
        base = 0.20 - 0.05 * np.log2(positions / 100.0)
        return {"losses": {"policy": list(np.abs(rng.normal(base, 0.01, size=300)))}}

    report = lc.run_curve(
        sizes=[100, 200, 400, 800], train_fn=steep, seed=5, resamples=1000
    )
    assert report.decision == lc.DECISION_SCALES


def test_138_curve_rejects_single_point() -> None:
    with pytest.raises(ValueError):
        lc.run_curve(sizes=[100], train_fn=_fake_train)


def test_138_curve_rejects_duplicate_sizes() -> None:
    with pytest.raises(ValueError):
        lc.run_curve(sizes=[100, 100], train_fn=_fake_train)


def test_138_curve_markdown_has_all_sections() -> None:
    report = lc.run_curve(sizes=[100, 200], train_fn=_fake_train, resamples=200)
    md = lc.build_markdown(report)
    assert "## 1. Noktalar" in md
    assert "## 2. Egim" in md
    assert "## 5. Karar" in md
    assert md.endswith("\n")


def test_138_curve_scaling_summary_feeds_pipeline_health() -> None:
    report = lc.run_curve(
        sizes=[100, 200, 400, 800], train_fn=_fake_train, seed=6, resamples=500
    )
    summary = report.scaling_summary()
    health = ph.diagnose(scaling=summary)
    assert health.scaling_evidence in ph.SCALING_STATES
    assert health.scaling_evidence != ph.SCALING_NONE


def test_138_curve_to_dict_is_json_serialisable() -> None:
    report = lc.run_curve(sizes=[100, 200], train_fn=_fake_train, resamples=200)
    text = json.dumps(report.to_dict(), sort_keys=True)
    assert "points" in text
    assert "decision" in text


def test_138_epsilon_matches_pipeline_health() -> None:
    assert lc.SCALING_SLOPE_EPSILON == ph.SCALING_SLOPE_EPSILON


def test_138_scaling_evidence_states_are_exactly_three() -> None:
    assert ph.SCALING_STATES == ("yok", "egim<eps", "egim>=eps")


def test_138_scaling_evidence_none_without_data() -> None:
    assert ph.diagnose().scaling_evidence == ph.SCALING_NONE


def test_138_scaling_evidence_below_epsilon() -> None:
    health = ph.diagnose(scaling={"slope": 0.001, "ciLow": -0.002, "ciHigh": 0.004})
    assert health.scaling_evidence == ph.SCALING_BELOW


def test_138_scaling_evidence_at_or_above_epsilon() -> None:
    health = ph.diagnose(scaling={"slope": 0.02, "ciLow": 0.01, "ciHigh": 0.03})
    assert health.scaling_evidence == ph.SCALING_AT_OR_ABOVE


def test_138_scaling_note_flags_ci_overlap() -> None:
    health = ph.diagnose(scaling={"slope": 0.006, "ciLow": 0.001, "ciHigh": 0.011})
    assert "belirsiz" in health.scaling_note
