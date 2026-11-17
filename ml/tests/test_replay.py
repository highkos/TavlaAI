"""Faz 4 v3 Bolum 6.1/6.2/6.3: replay buffer ve hedef yeniden hesaplama testleri."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from replay import (
    VALUE_TARGET_SEARCH_DISTILL,
    VALUE_TARGET_TD_LAMBDA,
    PolicySample,
    ReplayBuffer,
    build_policy_samples,
    build_value_samples,
    filter_informative,
    is_usable_game,
    policy_targets_from_q,
    target_entropy_ratio,
    terminal_value,
    uniform_policy_baseline,
)
from shards import (
    DEC_CHOSEN_IS_TERMINAL,
    DEC_IS_LEARNER,
    DEC_IS_PASS,
    GAME_FLAG_ABORTED,
    DecisionRecord,
    GameRecord,
)

VECTOR_SIZE = 221


class ConstModel(torch.nn.Module):
    """Tum girdiler icin sabit deger donduren sahte ag."""

    def __init__(self, value: float) -> None:
        super().__init__()
        self.value = float(value)

    def forward(self, x):
        b = x.shape[0]
        return torch.full((b, 1), self.value), torch.zeros((b, 1))


def _vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal(VECTOR_SIZE).astype(np.float32)


def _decision(mover: int, *, learner: bool, terminal: bool = False, seed: int = 0,
              q=None, cand=None) -> DecisionRecord:
    flags = 0
    if learner:
        flags |= DEC_IS_LEARNER
    if terminal:
        flags |= DEC_CHOSEN_IS_TERMINAL
    return DecisionRecord(
        mover=mover,
        flags=flags,
        candidate_total=1 if terminal else (0 if q is None else int(len(q))),
        search_value=0.0,
        chosen_vector=None if terminal else _vec(seed),
        q=None if q is None else np.asarray(q, dtype=np.float32),
        policy_target_cs=None,
        cand_vectors=None if cand is None else np.asarray(cand, dtype=np.float32),
    )


def _game(t_count: int = 5, *, winner: int = 1, result_points: int = 2,
          cube_value: int = 1, learner_all: bool = True) -> GameRecord:
    decisions = []
    for t in range(t_count - 1):
        decisions.append(_decision(1 if t % 2 == 0 else -1, learner=learner_all, seed=t))
    decisions.append(_decision(1, learner=learner_all, terminal=True))
    return GameRecord(
        game_id=1,
        learner_side=0,
        flags=0,
        cube_value=cube_value,
        decisions=decisions,
        winner=winner,
        result_type=2,
        result_points=result_points,
    )


# ----------------------------------------------------------------------
# Buffer
# ----------------------------------------------------------------------


def test_buffer_fifo_eviction():
    buf = ReplayBuffer(max_games=3)
    games = [_game() for _ in range(5)]
    for i, g in enumerate(games):
        g.game_id = i
    buf.add(games)
    assert len(buf) == 3
    assert [g.game_id for g in buf.games] == [2, 3, 4]


def test_buffer_rejects_bad_capacity():
    with pytest.raises(ValueError):
        ReplayBuffer(0)


def test_is_usable_game_rejects_aborted():
    g = _game()
    assert is_usable_game(g)
    g.flags |= GAME_FLAG_ABORTED
    assert not is_usable_game(g)


def test_is_usable_game_rejects_short_game():
    g = _game(t_count=2)
    g.decisions = g.decisions[:1]
    assert not is_usable_game(g)


# ----------------------------------------------------------------------
# Deger hedefleri
# ----------------------------------------------------------------------


def test_terminal_value_sign():
    """``z`` isaretsiz buyukluktur; isareti ``td_lambda_targets`` zinciri cevirir.

    Faz 6 Asama B (F6-07): eski surum ``z``'yi ``winner`` ile carpiyordu; bu, siyah
    kazandiginda tum hedefleri ters ceviriyordu.
    """
    assert terminal_value(2, 1, 1) == pytest.approx(2.0)
    assert terminal_value(2, 1, -1) == pytest.approx(2.0)
    assert terminal_value(3, 2, 1) == pytest.approx(1.5)
    assert terminal_value(3, 2, -1) == pytest.approx(1.5)

    with pytest.raises(ValueError):
        terminal_value(2, 1, 0)


def test_value_targets_lambda_zero():
    """lam = 0 => y[T-2] = -z, y[t] = -V_hat[t+1]."""
    model = ConstModel(0.25)
    g = _game(t_count=5, winner=1, result_points=2, cube_value=1)
    s = build_value_samples(model, [g], lam=0.0, device=torch.device("cpu"))

    assert len(s) == 4
    # t = 0,1,2,3 ; y[3] = -2 ; y[0..2] = -0.25
    assert s.y[3] == pytest.approx(-2.0, abs=1e-6)
    for t in (0, 1, 2):
        assert s.y[t] == pytest.approx(-0.25, abs=1e-6)


def test_value_targets_lambda_one():
    """lam = 1 => y[T-2] = -z, y[t] = -y[t+1] (isaret degisir)."""
    model = ConstModel(0.25)
    g = _game(t_count=5, winner=1, result_points=2, cube_value=1)
    s = build_value_samples(model, [g], lam=1.0, device=torch.device("cpu"))

    assert s.y[3] == pytest.approx(-2.0, abs=1e-6)
    assert s.y[2] == pytest.approx(+2.0, abs=1e-6)
    assert s.y[1] == pytest.approx(-2.0, abs=1e-6)
    assert s.y[0] == pytest.approx(+2.0, abs=1e-6)


def test_value_targets_lambda_half():
    """lam = 0.5, V_hat = 0.25, z = 2."""
    model = ConstModel(0.25)
    g = _game(t_count=5, winner=1, result_points=2, cube_value=1)
    s = build_value_samples(model, [g], lam=0.5, device=torch.device("cpu"))

    y3 = -2.0
    y2 = -((1 - 0.5) * 0.25 + 0.5 * y3)
    y1 = -((1 - 0.5) * 0.25 + 0.5 * y2)
    y0 = -((1 - 0.5) * 0.25 + 0.5 * y1)

    assert s.y[3] == pytest.approx(y3, abs=1e-6)
    assert s.y[2] == pytest.approx(y2, abs=1e-6)
    assert s.y[1] == pytest.approx(y1, abs=1e-6)
    assert s.y[0] == pytest.approx(y0, abs=1e-6)


def test_value_targets_only_learner_decisions_enter_loss():
    """Zincir tum kararlar uzerinden kurulur; kayba yalnizca IsLearner girer."""
    model = ConstModel(0.25)
    g = _game(t_count=5, winner=1, result_points=2, cube_value=1)
    # t = 1 ve t = 3 ogrenen degil
    g.decisions[1].flags &= ~DEC_IS_LEARNER
    g.decisions[3].flags &= ~DEC_IS_LEARNER

    s = build_value_samples(model, [g], lam=0.5, device=torch.device("cpu"))

    assert len(s) == 2
    assert list(s.decision_index) == [0, 2]

    y3 = -2.0
    y2 = -((1 - 0.5) * 0.25 + 0.5 * y3)
    y1 = -((1 - 0.5) * 0.25 + 0.5 * y2)
    y0 = -((1 - 0.5) * 0.25 + 0.5 * y1)

    assert s.y[0] == pytest.approx(y0, abs=1e-6)
    assert s.y[1] == pytest.approx(y2, abs=1e-6)


def test_value_targets_skip_aborted_games():
    model = ConstModel(0.0)
    g = _game()
    g.flags |= GAME_FLAG_ABORTED
    s = build_value_samples(model, [g], lam=0.7, device=torch.device("cpu"))
    assert len(s) == 0


def test_value_targets_search_distill_mode():
    model = ConstModel(0.0)
    g = _game(t_count=4)
    for t, d in enumerate(g.decisions):
        d.search_value = float(t) * 0.1

    s = build_value_samples(
        model, [g], lam=0.7, device=torch.device("cpu"),
        target_mode=VALUE_TARGET_SEARCH_DISTILL,
    )
    assert len(s) == 3
    assert list(s.y) == pytest.approx([0.0, 0.1, 0.2], abs=1e-6)


def test_value_targets_reject_unknown_mode():
    model = ConstModel(0.0)
    with pytest.raises(ValueError):
        build_value_samples(model, [_game()], target_mode="nope")


def test_value_targets_cube_value_scales_z():
    model = ConstModel(0.0)
    g = _game(t_count=3, winner=-1, result_points=3, cube_value=2)
    s = build_value_samples(model, [g], lam=1.0, device=torch.device("cpu"))
    # z = 3/2 = 1.5 (isaretsiz) ; y[1] = -z = -1.5 ; y[0] = -y[1] = +1.5
    assert s.y[1] == pytest.approx(-1.5, abs=1e-6)
    assert s.y[0] == pytest.approx(1.5, abs=1e-6)


def test_value_targets_match_perspective_equity_at_lambda_one():
    """``lam = 1`` hedefleri, perspektif tabanli dislayici equity ile ayni olmali.

    Faz 6 Asama B (F6-07) regresyon testi: siyah kazanan oyunlarda isaret
    cevrilmemelidir. Son karar veren oyuncu kazanandir; ``t = T-2`` kaybedendir.
    """
    model = ConstModel(0.0)
    for winner in (1, -1):
        g = _game(t_count=5, winner=winner, result_points=2, cube_value=1)
        s = build_value_samples(model, [g], lam=1.0, device=torch.device("cpu"))

        # t = 3 (T-2) kaybedenin karari -> -2 ; t = 2 kazananin -> +2 ; ...
        expected = [2.0, -2.0, 2.0, -2.0]
        assert list(s.y) == pytest.approx(expected, abs=1e-6), f"winner={winner}"


# ----------------------------------------------------------------------
# Politika hedefleri
# ----------------------------------------------------------------------


def test_policy_targets_from_q_matches_softmax():
    q = np.array([0.5, 0.4, 0.1], dtype=np.float32)
    p = policy_targets_from_q(q, 0.05)
    ref = np.exp(q / 0.05)
    ref = ref / ref.sum()
    assert p == pytest.approx(ref, abs=1e-6)
    assert float(p.sum()) == pytest.approx(1.0, abs=1e-6)


def test_policy_targets_reject_bad_tau():
    with pytest.raises(ValueError):
        policy_targets_from_q(np.array([1.0, 0.0]), 0.0)


def test_policy_samples_skip_small_groups_and_terminal():
    g = _game(t_count=4)
    # t = 0: |E| = 3 (uygun)
    g.decisions[0].q = np.array([0.3, 0.2, 0.1], dtype=np.float32)
    g.decisions[0].cand_vectors = np.stack([_vec(10), _vec(11), _vec(12)], axis=0)
    # t = 1: |E| = 1 (atlanir)
    g.decisions[1].q = np.array([0.3], dtype=np.float32)
    g.decisions[1].cand_vectors = np.stack([_vec(13)], axis=0)
    # t = 2: |E| = 2 (uygun)
    g.decisions[2].q = np.array([0.2, 0.1], dtype=np.float32)
    g.decisions[2].cand_vectors = np.stack([_vec(14), _vec(15)], axis=0)

    samples = build_policy_samples([g], tau_train=0.05, min_group=2)
    assert len(samples) == 2
    assert samples[0].vectors.shape == (3, VECTOR_SIZE)
    assert samples[1].vectors.shape == (2, VECTOR_SIZE)
    assert float(samples[0].target.sum()) == pytest.approx(1.0, abs=1e-6)


def test_policy_samples_skip_non_learner():
    g = _game(t_count=3)
    for d in g.decisions:
        d.flags &= ~DEC_IS_LEARNER
    g.decisions[0].q = np.array([0.3, 0.2], dtype=np.float32)
    g.decisions[0].cand_vectors = np.stack([_vec(20), _vec(21)], axis=0)
    assert build_policy_samples([g]) == []


def test_uniform_baseline_and_entropy_ratio():
    samples = [
        PolicySample(vectors=np.zeros((2, VECTOR_SIZE), np.float32),
                     target=np.array([0.5, 0.5], np.float32), q=np.zeros(2, np.float32)),
        PolicySample(vectors=np.zeros((4, VECTOR_SIZE), np.float32),
                     target=np.full(4, 0.25, np.float32), q=np.zeros(4, np.float32)),
    ]
    assert uniform_policy_baseline(samples) == pytest.approx((np.log(2) + np.log(4)) / 2, abs=1e-6)
    # Duzgun hedefler => oran 1.0
    assert target_entropy_ratio(samples) == pytest.approx(1.0, abs=1e-6)


def test_entropy_ratio_small_for_sharp_targets():
    samples = [
        PolicySample(vectors=np.zeros((4, VECTOR_SIZE), np.float32),
                     target=np.array([1.0, 0.0, 0.0, 0.0], np.float32), q=np.zeros(4, np.float32)),
    ]
    assert target_entropy_ratio(samples) == pytest.approx(0.0, abs=1e-6)

def test_filter_informative_drops_uniform_targets():
    """Duzgune yakin hedefler (H/log|E| ~ 1) egitimden elenir."""
    sharp = PolicySample(
        vectors=np.zeros((4, VECTOR_SIZE), np.float32),
        target=np.array([1.0, 0.0, 0.0, 0.0], np.float32),
        q=np.zeros(4, np.float32),
    )
    flat = PolicySample(
        vectors=np.zeros((4, VECTOR_SIZE), np.float32),
        target=np.full(4, 0.25, np.float32),
        q=np.zeros(4, np.float32),
    )
    assert sharp.entropy_ratio == pytest.approx(0.0, abs=1e-6)
    assert flat.entropy_ratio == pytest.approx(1.0, abs=1e-6)

    kept = filter_informative([sharp, flat], 0.99)
    assert kept == [sharp]

    # 1.0 => kapi kapali
    assert filter_informative([sharp, flat], 1.0) == [sharp, flat]