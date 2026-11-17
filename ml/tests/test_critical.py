# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.3 / Test 98 - kritik karar agirliklandirma testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import critical  # noqa: E402
from critical import (  # noqa: E402
    CRITICAL_BOOST,
    CRITICAL_EQUITY_THRESHOLD,
    CRITICAL_MARGIN_THRESHOLD,
    VALUE_CRITERION_EQUITY,
    VALUE_CRITERION_MARGIN,
    CriticalError,
    best_equity,
    build_report,
    critical_mask_policy,
    critical_mask_value,
    critical_mask_value_margin,
    decision_margin,
    is_critical,
    sampling_weights,
    weight_distribution,
)


class _Policy:
    def __init__(self, q):
        self.q = np.asarray(q, dtype=np.float32)


class _Value:
    def __init__(self, equity):
        self.equity = np.asarray(equity, dtype=np.float64)


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_98_boost_is_two():
    assert CRITICAL_BOOST == pytest.approx(2.0)


def test_98_equity_threshold_positive():
    assert CRITICAL_EQUITY_THRESHOLD > 0.0


def test_98_margin_threshold_positive():
    assert CRITICAL_MARGIN_THRESHOLD > 0.0


def test_98_margin_threshold_below_equity_threshold():
    assert CRITICAL_MARGIN_THRESHOLD < CRITICAL_EQUITY_THRESHOLD


# ----------------------------------------------------------------------
# decision_margin / best_equity
# ----------------------------------------------------------------------


def test_98_margin_two_candidates():
    assert decision_margin([0.10, 0.30]) == pytest.approx(0.20)


def test_98_margin_ignores_lower_candidates():
    assert decision_margin([-0.5, 0.10, 0.30]) == pytest.approx(0.20)


def test_98_margin_single_candidate_is_zero():
    assert decision_margin([0.42]) == 0.0


def test_98_margin_empty_is_zero():
    assert decision_margin([]) == 0.0


def test_98_margin_rejects_non_finite():
    with pytest.raises(CriticalError):
        decision_margin([0.1, float("nan")])


def test_98_best_equity_max():
    assert best_equity([-0.4, 0.2, 0.7]) == pytest.approx(0.7)


def test_98_best_equity_empty_is_zero():
    assert best_equity([]) == 0.0


def test_98_best_equity_rejects_non_finite():
    with pytest.raises(CriticalError):
        best_equity([float("inf")])


# ----------------------------------------------------------------------
# is_critical
# ----------------------------------------------------------------------


def test_98_critical_when_big_equity_and_tight_margin():
    assert is_critical([0.60, 0.62]) is True


def test_98_not_critical_when_margin_wide():
    assert is_critical([0.60, 0.90]) is False


def test_98_not_critical_when_equity_small():
    assert is_critical([0.10, 0.11]) is False


def test_98_critical_uses_absolute_equity():
    assert is_critical([-0.60, -0.62]) is True


def test_98_critical_boundary_equity_inclusive():
    assert is_critical([0.5, 0.5]) is True


def test_98_critical_boundary_margin_inclusive():
    # 0.55 - 0.5 float64'te 0.050000000000000044'tur; tam sinir icin
    # ikili gosterimde tam olan degerler secilir.
    assert is_critical([0.5, 0.75], margin_threshold=0.25) is True


def test_98_critical_just_over_margin():
    assert is_critical([0.5, 0.56]) is False


def test_98_critical_rejects_negative_equity_threshold():
    with pytest.raises(CriticalError):
        is_critical([0.5, 0.5], equity_threshold=-1.0)


def test_98_critical_rejects_negative_margin_threshold():
    with pytest.raises(CriticalError):
        is_critical([0.5, 0.5], margin_threshold=-1.0)


def test_98_critical_custom_thresholds():
    assert is_critical([0.2, 0.21], equity_threshold=0.1, margin_threshold=0.02) is True


# ----------------------------------------------------------------------
# Maskeler
# ----------------------------------------------------------------------


def test_98_policy_mask_length():
    samples = [_Policy([0.6, 0.61]), _Policy([0.1, 0.9])]
    assert critical_mask_policy(samples).shape == (2,)


def test_98_policy_mask_values():
    samples = [_Policy([0.6, 0.61]), _Policy([0.1, 0.9]), _Policy([-0.7, -0.71])]
    mask = critical_mask_policy(samples)
    assert mask.tolist() == [True, False, True]


def test_98_policy_mask_skips_missing_q():
    class _NoQ:
        q = None

    assert critical_mask_policy([_NoQ()]).tolist() == [False]


def test_98_policy_mask_empty():
    assert critical_mask_policy([]).shape == (0,)


def test_98_value_mask_uses_absolute_equity():
    samples = _Value([0.1, -0.6, 0.5, -0.49])
    assert critical_mask_value(samples).tolist() == [False, True, True, False]


def test_98_value_mask_empty():
    assert critical_mask_value(_Value([])).shape == (0,)


def test_98_value_mask_rejects_non_finite():
    with pytest.raises(CriticalError):
        critical_mask_value(_Value([float("nan")]))


# ----------------------------------------------------------------------
# sampling_weights
# ----------------------------------------------------------------------


def test_98_weights_sum_to_one():
    weights = sampling_weights(np.array([True, False, False, False]))
    assert float(np.sum(weights)) == pytest.approx(1.0)


def test_98_weights_boost_ratio():
    weights = sampling_weights(np.array([True, False]))
    assert weights[0] / weights[1] == pytest.approx(CRITICAL_BOOST)


def test_98_weights_uniform_when_no_critical():
    weights = sampling_weights(np.zeros((4,), dtype=bool))
    assert np.allclose(weights, 0.25)


def test_98_weights_empty():
    assert sampling_weights(np.zeros((0,), dtype=bool)).shape == (0,)


def test_98_weights_reject_boost_below_one():
    with pytest.raises(CriticalError):
        sampling_weights(np.array([True]), boost=0.5)


def test_98_weights_boost_one_is_uniform():
    weights = sampling_weights(np.array([True, False, False]), boost=1.0)
    assert np.allclose(weights, 1.0 / 3.0)


# ----------------------------------------------------------------------
# weight_distribution
# ----------------------------------------------------------------------


def test_98_distribution_counts():
    report = weight_distribution(np.array([True, False, False, False]))
    assert report["count"] == 4
    assert report["critical"] == 1
    assert report["criticalShare"] == pytest.approx(0.25)


def test_98_distribution_boost_field():
    report = weight_distribution(np.array([True, False]))
    assert report["boost"] == pytest.approx(CRITICAL_BOOST)


def test_98_distribution_thresholds_recorded():
    report = weight_distribution(np.array([True, False]))
    assert report["equityThreshold"] == pytest.approx(CRITICAL_EQUITY_THRESHOLD)
    assert report["marginThreshold"] == pytest.approx(CRITICAL_MARGIN_THRESHOLD)


def test_98_distribution_effective_count_below_count():
    report = weight_distribution(np.array([True, False, False, False]))
    assert report["effectiveCount"] < report["count"]


def test_98_distribution_effective_count_uniform():
    report = weight_distribution(np.zeros((4,), dtype=bool))
    assert report["effectiveCount"] == pytest.approx(4.0)


def test_98_distribution_empty():
    report = weight_distribution(np.zeros((0,), dtype=bool))
    assert report["count"] == 0
    assert report["criticalShare"] == 0.0
    assert report["effectiveCount"] == 0.0


def test_98_distribution_max_weight():
    report = weight_distribution(np.array([True, False]))
    assert report["maxWeight"] == pytest.approx(2.0 / 3.0)


def test_98_distribution_not_degenerate_when_mixed():
    report = weight_distribution(np.array([True, False, False]))
    assert report["degenerate"] is False


def test_98_distribution_degenerate_when_all_critical():
    report = weight_distribution(np.array([True, True]))
    assert report["degenerate"] is True


def test_98_distribution_degenerate_when_none_critical():
    report = weight_distribution(np.array([False, False]))
    assert report["degenerate"] is True


def test_98_distribution_degenerate_when_empty():
    report = weight_distribution(np.zeros((0,), dtype=bool))
    assert report["degenerate"] is True


def test_98_value_mask_degenerates_on_money_game_equity():
    # F7-08: para oyununda |equity| = 1 oldugu icin 0.5 esigi her ornegi
    # "kritik" yapar; agirlik uygulanmaz ve bu raporlanir.
    samples = _Value([1.0, -1.0, 1.0, -2.0])
    report = weight_distribution(critical_mask_value(samples))
    assert report["criticalShare"] == pytest.approx(1.0)
    assert report["degenerate"] is True


# ----------------------------------------------------------------------
# build_report
# ----------------------------------------------------------------------


def test_98_build_report_has_both_heads():
    report = build_report(_Value([0.6, 0.1]), [_Policy([0.6, 0.61])])
    payload = report.to_dict()
    assert set(payload) == {"value", "policy"}


def test_98_build_report_value_counts():
    report = build_report(_Value([0.6, 0.1, -0.7]), [_Policy([0.6, 0.61])])
    assert report.value["critical"] == 2


def test_98_build_report_policy_counts():
    report = build_report(_Value([0.6]), [_Policy([0.6, 0.61]), _Policy([0.1, 0.9])])
    assert report.policy["critical"] == 1


def test_98_build_report_custom_boost():
    report = build_report(_Value([0.6]), [_Policy([0.6, 0.61])], boost=3.0)
    assert report.value["boost"] == pytest.approx(3.0)


# ----------------------------------------------------------------------
# train_v2 entegrasyonu
# ----------------------------------------------------------------------


def test_98_train_steps_accepts_weights():
    import inspect

    import train_v2

    params = inspect.signature(train_v2.train_steps_v2).parameters
    assert "value_weights" in params
    assert "policy_weights" in params


def test_98_train_v2_cli_has_critical_boost():
    import train_v2

    args = train_v2.build_parser().parse_args(["--critical-boost", "2.5"])
    assert args.critical_boost == pytest.approx(2.5)


def test_98_train_v2_cli_default_is_none():
    import train_v2

    assert train_v2.build_parser().parse_args([]).critical_boost is None


def test_98_train_steps_rejects_wrong_weight_length():
    import torch

    import train_v2
    from model import build_model

    model = build_model(221, 16, 8, seed=1, output_version=2, profile="small")
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    samples = train_v2.ExclusiveSamples(
        x=np.zeros((4, 221), dtype=np.float32),
        y=np.zeros((4, 6), dtype=np.float32),
        game_index=np.zeros((4,), dtype=np.int64),
        decision_index=np.zeros((4,), dtype=np.int64),
    )
    with pytest.raises(ValueError):
        train_v2.train_steps_v2(
            model,
            optimizer,
            samples,
            [],
            steps=1,
            value_batch=2,
            policy_batch=2,
            c_value=1.0,
            c_policy=1.0,
            c_cal=0.1,
            clip_grad_norm=1.0,
            device=torch.device("cpu"),
            rng=np.random.default_rng(0),
            value_weights=np.ones((3,), dtype=np.float64),
        )


def test_98_train_steps_runs_with_weights():
    import torch

    import train_v2
    from model import build_model

    model = build_model(221, 16, 8, seed=1, output_version=2, profile="small")
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    rng = np.random.default_rng(0)
    samples = train_v2.ExclusiveSamples(
        x=rng.normal(size=(8, 221)).astype(np.float32),
        y=np.tile(np.array([[1, 0, 0, 0, 0, 0]], dtype=np.float32), (8, 1)),
        game_index=np.zeros((8,), dtype=np.int64),
        decision_index=np.zeros((8,), dtype=np.int64),
    )
    weights = sampling_weights(np.array([True, False, False, False, False, False, False, False]))
    stats = train_v2.train_steps_v2(
        model,
        optimizer,
        samples,
        [],
        steps=2,
        value_batch=4,
        policy_batch=2,
        c_value=1.0,
        c_policy=1.0,
        c_cal=0.1,
        clip_grad_norm=1.0,
        device=torch.device("cpu"),
        rng=np.random.default_rng(0),
        value_weights=weights,
    )
    assert len(stats.value_loss) == 2
    assert all(np.isfinite(v) for v in stats.value_loss)


# ----------------------------------------------------------------------
# F7-08 duzeltmesi: deger kafasi marj olcutu
# ----------------------------------------------------------------------


def test_98_value_criterion_constants():
    assert VALUE_CRITERION_MARGIN == "margin"
    assert VALUE_CRITERION_EQUITY == "equity"


def test_98_value_margin_mask_is_discriminative():
    """F7-08: marj olcutu para oyununda da ayirt edicidir."""
    margins = np.array([0.0, 0.01, 0.05, 0.06, 0.5, 2.0], dtype=np.float64)
    mask = critical_mask_value_margin(margins, margin_threshold=0.05)
    assert mask.tolist() == [True, True, True, False, False, False]


def test_98_value_margin_mask_is_not_degenerate_on_money_play():
    """F7-08'in ozu: |equity| olcutu %100 kritik verirken marj olcutu ayirir."""
    rng = np.random.default_rng(20261117)
    margins = rng.exponential(scale=0.2, size=5000)
    equity = np.ones(5000)  # para oyunu: her ornek |equity| = 1

    equity_mask = critical_mask_value(_Value(equity))
    margin_mask = critical_mask_value_margin(margins)

    assert equity_mask.mean() == 1.0, "eski olcut dejenere olmali"
    assert 0.0 < margin_mask.mean() < 1.0, "yeni olcut ayirt edici olmali"


def test_98_value_margin_mask_treats_nan_as_not_critical():
    margins = np.array([0.01, np.nan, 0.5], dtype=np.float64)
    mask = critical_mask_value_margin(margins, margin_threshold=0.05)
    assert mask.tolist() == [True, False, False]


def test_98_value_margin_mask_empty():
    mask = critical_mask_value_margin(np.zeros((0,), dtype=np.float64))
    assert mask.size == 0


def test_98_value_margin_mask_rejects_negative_threshold():
    with pytest.raises(CriticalError):
        critical_mask_value_margin([0.1], margin_threshold=-0.1)


def test_98_value_margin_mask_accepts_list():
    mask = critical_mask_value_margin([0.0, 0.2], margin_threshold=0.05)
    assert mask.tolist() == [True, False]


def test_98_build_report_uses_margin_when_given():
    value = _Value(np.ones(4))
    policy = [_Policy([1.0, 0.99]), _Policy([1.0, 0.5])]
    margins = np.array([0.0, 0.01, 0.5, 1.0], dtype=np.float64)

    report = build_report(value, policy, value_margins=margins)

    assert report.value["criterion"] == VALUE_CRITERION_MARGIN
    assert report.value["critical"] == 2
    assert report.value["degenerate"] is False
    assert report.policy["criterion"] == VALUE_CRITERION_MARGIN


def test_98_build_report_falls_back_to_equity_and_flags_degenerate():
    value = _Value(np.ones(4))
    policy = [_Policy([1.0, 0.99])]

    report = build_report(value, policy)

    assert report.value["criterion"] == VALUE_CRITERION_EQUITY
    assert report.value["degenerate"] is True, "eski olcut para oyununda dejenere"


def test_98_build_report_margin_none_is_equity_path():
    value = _Value(np.array([1.0, -1.0, 0.2, 0.1]))
    policy = [_Policy([1.0, 0.99])]

    report = build_report(value, policy, value_margins=None)

    assert report.value["criterion"] == VALUE_CRITERION_EQUITY
    assert report.value["critical"] == 2


def test_98_weight_distribution_reports_criterion():
    mask = np.array([True, False, False, False])
    dist = weight_distribution(mask, criterion=VALUE_CRITERION_MARGIN)
    assert dist["criterion"] == VALUE_CRITERION_MARGIN


def test_98_weight_distribution_default_criterion_is_equity():
    mask = np.array([True, False])
    assert weight_distribution(mask)["criterion"] == VALUE_CRITERION_EQUITY


def test_98_margin_weights_are_boosted():
    margins = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float64)
    mask = critical_mask_value_margin(margins)
    weights = sampling_weights(mask, boost=2.0)
    assert weights[0] == pytest.approx(2.0 / 6.0)
    assert weights[2] == pytest.approx(1.0 / 6.0)
    assert float(np.sum(weights)) == pytest.approx(1.0)


# ----------------------------------------------------------------------
# F7-08: Bolum 5.3'un tam olcutu (|equity| VE marj)
# ----------------------------------------------------------------------


def test_98_value_mask_with_best_equity_applies_both_legs():
    margins = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    best = np.array([1.0, 0.1, -1.0, -0.1], dtype=np.float64)
    mask = critical_mask_value_margin(margins, best_equity=best, equity_threshold=0.5)
    assert mask.tolist() == [True, False, True, False]


def test_98_value_mask_without_best_equity_uses_margin_only():
    margins = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    mask = critical_mask_value_margin(margins, equity_threshold=0.5)
    assert mask.tolist() == [True, True, True, True]


def test_98_value_mask_best_equity_length_mismatch_raises():
    with pytest.raises(CriticalError):
        critical_mask_value_margin([0.0, 0.0], best_equity=[1.0])


def test_98_value_mask_nan_best_equity_is_not_critical():
    margins = np.array([0.0, 0.0], dtype=np.float64)
    best = np.array([np.nan, 1.0], dtype=np.float64)
    mask = critical_mask_value_margin(margins, best_equity=best)
    assert mask.tolist() == [False, True]


def test_98_value_mask_rejects_negative_equity_threshold():
    with pytest.raises(CriticalError):
        critical_mask_value_margin([0.0], equity_threshold=-0.5)


def test_98_build_report_passes_best_equity_through():
    value = _Value(np.ones(3))
    margins = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    best = np.array([1.0, 0.1, -1.0], dtype=np.float64)

    report = build_report(value, [], value_margins=margins, value_best_equity=best)

    assert report.value["criterion"] == VALUE_CRITERION_MARGIN
    assert report.value["critical"] == 2
    assert report.value["degenerate"] is False


def test_98_money_play_old_criterion_is_degenerate_new_is_not():
    """F7-08 regresyonu: para oyununda eski olcut %100, yeni olcut ayirt edici."""
    rng = np.random.default_rng(7)
    n = 4000
    margins = rng.exponential(scale=0.15, size=n)
    best = rng.normal(scale=0.9, size=n)
    equity = np.ones(n)  # hedef equity her zaman +-1

    old = critical_mask_value(_Value(equity))
    new = critical_mask_value_margin(margins, best_equity=best)

    assert old.mean() == 1.0
    assert 0.05 < new.mean() < 0.95
