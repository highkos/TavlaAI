"""Faz 4 v3 Bolum 8, Test 7: sayisal dayaniklilik (1000 oyunluk duman testi)."""

from __future__ import annotations

import numpy as np
import pytest

import losses
import td_lambda


def _synthetic_games(count: int, seed: int = 3) -> list[dict]:
    """Her oyun: 2..8 karar, son karar terminal, rastgele Q ve V_hat."""
    rng = np.random.RandomState(seed)
    games = []
    for _ in range(count):
        n = int(rng.randint(2, 9))
        v_hat = rng.randn(n - 1).astype(np.float64) * 0.5
        groups = [int(rng.randint(1, 6)) for _ in range(n - 1)]
        qs = [rng.randn(g).astype(np.float64) * 0.5 for g in groups]
        is_learner = rng.rand(n - 1) < 0.5
        games.append(
            {
                "v_hat": v_hat,
                "groups": groups,
                "qs": qs,
                "is_learner": is_learner,
                "z": float(rng.choice([-3, -2, -1, 1, 2, 3])),
            }
        )
    return games


def test_thousand_game_smoke_all_finite():
    games = _synthetic_games(1000)
    total_value = 0.0
    total_policy = 0.0
    value_count = 0
    policy_count = 0

    for g in games:
        y, mask = td_lambda.td_lambda_targets_masked(g["v_hat"], g["z"], g["is_learner"], 0.7)
        assert np.all(np.isfinite(y))
        total_value += float(np.sum(y[mask] ** 2))
        value_count += int(mask.sum())

        for q, n in zip(g["qs"], g["groups"]):
            target = losses.policy_targets_from_q(q, 0.05)
            assert np.all(np.isfinite(target))
            assert abs(float(target.sum()) - 1.0) < 1e-9
            logits = q.copy()
            loss, used = losses.policy_loss_numpy(logits, target, [n])
            assert np.isfinite(loss)
            if used:
                total_policy += loss
                policy_count += 1

    assert value_count > 0
    assert policy_count > 0
    assert np.isfinite(total_value)
    assert np.isfinite(total_policy)


def test_extreme_q_does_not_overflow():
    """Cok buyuk/kucuk Q degerleri softmax'ta tasmamali."""
    q = np.array([1e6, -1e6, 0.0])
    target = losses.policy_targets_from_q(q, 0.05)
    assert np.all(np.isfinite(target))
    assert abs(float(target.sum()) - 1.0) < 1e-9
    assert target[0] > 0.999


def test_extreme_logits_loss_is_finite():
    logits = np.array([1e4, -1e4, 0.0])
    target = np.array([1.0, 0.0, 0.0])
    loss, used = losses.policy_loss_numpy(logits, target, [3])
    assert used == 1
    assert np.isfinite(loss)
    assert loss < 1e-6


def test_torch_training_step_is_finite():
    """Gercek ag uzerinde ileri/geri gecis: kayip ve gradyanlar sonlu."""
    torch = pytest.importorskip("torch")
    import model as model_mod

    net = model_mod.build_model(seed=99)
    net.train()
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)

    rng = np.random.RandomState(4)
    x = torch.from_numpy(rng.randn(64, 221).astype(np.float32))
    y = torch.from_numpy(rng.randn(64, 1).astype(np.float32))

    v, p = net(x)
    v_loss = losses.value_loss_mse(v, y)
    p_loss = losses.policy_loss_torch(p.reshape(-1), torch.softmax(p.reshape(-1), dim=0), [64])
    loss = losses.total_loss(v_loss, p_loss, 1.0)
    opt.zero_grad()
    loss.backward()

    assert torch.isfinite(loss)
    for name, param in net.named_parameters():
        assert param.grad is not None, f"{name} gradyani yok"
        assert torch.all(torch.isfinite(param.grad)), f"{name} gradyani sonlu degil"

    opt.step()
    v2, _ = net(x)
    assert torch.all(torch.isfinite(v2))


def test_value_head_bias_starts_at_zero():
    torch = pytest.importorskip("torch")
    import model as model_mod

    net = model_mod.build_model(seed=1)
    assert float(net.value_head.bias.detach().abs().max()) == 0.0