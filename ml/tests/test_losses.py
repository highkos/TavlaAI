"""Faz 4 v3 Bolum 8, Test 2: grup softmax capraz entropi (elle hesaplanmis kucuk kumeler)."""

from __future__ import annotations

import math

import numpy as np
import pytest

import losses


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / np.sum(e)


def test_policy_targets_from_q_matches_softmax():
    q = np.array([0.4, -0.1, 0.9])
    tau = 0.05
    got = losses.policy_targets_from_q(q, tau)
    want = _softmax(q / tau)
    assert np.allclose(got, want, atol=1e-12)
    assert abs(float(np.sum(got)) - 1.0) < 1e-12


def test_policy_targets_rejects_nonpositive_tau():
    with pytest.raises(ValueError):
        losses.policy_targets_from_q([0.1, 0.2], 0.0)
    with pytest.raises(ValueError):
        losses.policy_targets_from_q([0.1, 0.2], -1.0)


def test_uniform_logits_uniform_target_gives_log_n():
    """2'li grup, duzgun logit ve duzgun hedef -> CE = ln 2."""
    loss, used = losses.policy_loss_numpy([0.0, 0.0], [0.5, 0.5], [2])
    assert used == 1
    assert abs(loss - math.log(2.0)) < 1e-12


def test_three_way_group_hand_computed():
    logits = [1.0, 2.0, 3.0]
    target = [0.0, 0.0, 1.0]
    p = _softmax(np.array(logits))
    want = -math.log(p[2])
    loss, used = losses.policy_loss_numpy(logits, target, [3])
    assert used == 1
    assert abs(loss - want) < 1e-12


def test_variable_length_groups_average():
    """Iki grup: 2'li (duzgun) ve 3'li (keskin). Ortalama alinir."""
    logits = [0.0, 0.0, 1.0, 2.0, 3.0]
    target = [0.5, 0.5, 0.0, 0.0, 1.0]
    l2 = math.log(2.0)
    l3 = -math.log(_softmax(np.array([1.0, 2.0, 3.0]))[2])
    loss, used = losses.policy_loss_numpy(logits, target, [2, 3])
    assert used == 2
    assert abs(loss - (l2 + l3) / 2.0) < 1e-12


def test_single_element_groups_are_skipped():
    """|E| < 2 olan kararlar politika kaybindan atlanir."""
    logits = [5.0, 0.0, 0.0]
    target = [1.0, 0.5, 0.5]
    loss, used = losses.policy_loss_numpy(logits, target, [1, 2])
    assert used == 1
    assert abs(loss - math.log(2.0)) < 1e-12


def test_all_groups_skipped_returns_zero():
    loss, used = losses.policy_loss_numpy([1.0, 2.0], [1.0, 1.0], [1, 1])
    assert used == 0
    assert loss == 0.0


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        losses.policy_loss_numpy([0.0, 0.0], [1.0], [2])
    with pytest.raises(ValueError):
        losses.policy_loss_numpy([0.0, 0.0], [0.5, 0.5], [3])


def test_torch_matches_numpy():
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(11)
    sizes = [2, 5, 1, 3, 4]
    n = sum(sizes)
    logits = rng.standard_normal(n).astype(np.float64)
    target = np.concatenate([losses.policy_targets_from_q(rng.standard_normal(s), 0.2) for s in sizes])

    np_loss, np_used = losses.policy_loss_numpy(logits, target, sizes)
    t_loss = losses.policy_loss_torch(
        torch.tensor(logits, dtype=torch.float64),
        torch.tensor(target, dtype=torch.float64),
        sizes,
    )
    assert np_used == 4
    assert abs(float(t_loss) - np_loss) < 1e-12


def test_torch_gradient_is_finite():
    torch = pytest.importorskip("torch")
    logits = torch.tensor([0.3, -0.2, 1.1, 0.0, 0.7], dtype=torch.float64, requires_grad=True)
    target = torch.tensor([0.6, 0.4, 0.2, 0.3, 0.5], dtype=torch.float64)
    loss = losses.policy_loss_torch(logits, target, [2, 3])
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.all(torch.isfinite(logits.grad))


def test_entropy_ratio_bounds():
    """Duzgun hedef -> 1.0; keskin hedef -> 0'a yakin."""
    uniform = [0.5, 0.5, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
    assert abs(losses.target_entropy_ratio(uniform, [2, 3]) - 1.0) < 1e-12

    sharp = [1.0, 0.0, 1.0, 0.0, 0.0]
    assert losses.target_entropy_ratio(sharp, [2, 3]) < 1e-6


def test_total_loss_combination():
    torch = pytest.importorskip("torch")
    v = torch.tensor(0.5)
    p = torch.tensor(0.25)
    assert abs(float(losses.total_loss(v, p, 2.0)) - 1.0) < 1e-12