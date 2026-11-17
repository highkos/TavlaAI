"""Faz 4 v3 Bolum 8, Test 3: TD(lambda) hedefleri (elle hesaplanmis oyunlar)."""

from __future__ import annotations

import numpy as np
import pytest

import td_lambda


V_HAT = [0.1, -0.2, 0.3, -0.4]
Z = 2.0


def test_terminal_value():
    assert td_lambda.terminal_value(2, 1) == 2.0
    assert td_lambda.terminal_value(4, 2) == 2.0
    assert td_lambda.terminal_value(1, 2) == 0.5
    with pytest.raises(ValueError):
        td_lambda.terminal_value(1, 0)


def test_lambda_one_alternates_terminal_value():
    """lam = 1 -> y[t] = -y[t+1]; isaretler degisir, |y| = |z|."""
    y = td_lambda.td_lambda_targets(V_HAT, Z, 1.0)
    assert np.allclose(y, [2.0, -2.0, 2.0, -2.0], atol=1e-12)


def test_lambda_zero_uses_next_value():
    """lam = 0 -> y[t] = -V_hat[t+1] (son eleman -z)."""
    y = td_lambda.td_lambda_targets(V_HAT, Z, 0.0)
    assert np.allclose(y, [0.2, -0.3, 0.4, -2.0], atol=1e-12)


def test_lambda_default_hand_computed():
    """lam = 0.7, elle: y3=-2, y2=1.52, y1=-1.154, y0=0.8678."""
    y = td_lambda.td_lambda_targets(V_HAT, Z, 0.7)
    assert np.allclose(y, [0.8678, -1.154, 1.52, -2.0], atol=1e-12)


def test_lambda_recursion_definition():
    """Genel dogrulama: y[t] = -((1-lam)V[t+1] + lam*y[t+1])."""
    lam = 0.35
    v = np.array([0.5, -0.7, 0.2, 0.9, -0.1])
    y = td_lambda.td_lambda_targets(v, -1.5, lam)
    assert abs(y[-1] - 1.5) < 1e-12
    for t in range(len(v) - 2, -1, -1):
        want = -((1.0 - lam) * v[t + 1] + lam * y[t + 1])
        assert abs(y[t] - want) < 1e-12


def test_single_decision_game():
    """T = 1 (yalnizca terminal karar) -> hedef yok."""
    y = td_lambda.td_lambda_targets([], 3.0, 0.7)
    assert y.shape == (0,)


def test_two_decision_game():
    """T = 2 -> tek hedef y[0] = -z."""
    y = td_lambda.td_lambda_targets([0.9], 1.0, 0.7)
    assert np.allclose(y, [-1.0], atol=1e-12)


def test_invalid_lambda_raises():
    with pytest.raises(ValueError):
        td_lambda.td_lambda_targets(V_HAT, Z, -0.1)
    with pytest.raises(ValueError):
        td_lambda.td_lambda_targets(V_HAT, Z, 1.1)


def test_pass_decision_is_a_normal_link():
    """Pas bir karardir: mover degisir, zincir ayni kuralla ilerler.

    Oyun: t0 (beyaz oynar), t1 (siyah PAS), t2 (beyaz oynar), t3 (siyah terminal).
    """
    v = [0.2, -0.5, 0.4]
    y = td_lambda.td_lambda_targets(v, 1.0, 0.7)
    assert abs(y[2] - (-1.0)) < 1e-12
    assert abs(y[1] - (-((0.3) * 0.4 + 0.7 * (-1.0)))) < 1e-12
    assert abs(y[0] - (-((0.3) * (-0.5) + 0.7 * y[1]))) < 1e-12


def test_pool_opponent_decisions_excluded_from_mask_only():
    """IsLearner = 0 kararlar kayiptan cikarilir ama zincirde kalir."""
    v = [0.2, -0.5, 0.4, 0.1]
    is_learner = [True, False, True, False]
    y, mask = td_lambda.td_lambda_targets_masked(v, 1.0, is_learner, 0.7)
    y_all = td_lambda.td_lambda_targets(v, 1.0, 0.7)
    assert np.allclose(y, y_all, atol=1e-12)
    assert mask.tolist() == [True, False, True, False]
    assert int(mask.sum()) == 2


def test_mask_length_mismatch_raises():
    with pytest.raises(ValueError):
        td_lambda.td_lambda_targets_masked([0.1, 0.2], 1.0, [True], 0.7)


def test_gammon_and_backgammon_scaling():
    """z = resultPoints / cubeValue; gammon 2, backgammon 3."""
    assert td_lambda.terminal_value(2, 1) == 2.0
    assert td_lambda.terminal_value(3, 1) == 3.0
    assert td_lambda.terminal_value(6, 2) == 3.0