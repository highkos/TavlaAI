"""Faz 4 v3 Bolum 8, Test 6: tau capraz kontrolu.

C# `BuildRootPolicyTarget` -> shard `policyTargetCs`. Python ayni `Q` ve `tau` ile
`softmax(Q/tau)` hesaplayip 1e-5 icinde eslesmeli.
"""

from __future__ import annotations

import numpy as np
import pytest

import losses
import shards
from conftest import ARTIFACTS

CSHARP_SHARD = ARTIFACTS / "csharp_shard.bgsp"
TAU_CS = 0.05
TOLERANCE = 1e-5


def test_softmax_matches_hand_computed():
    """Q = [0.5, 0.4], tau = 0.05 -> softmax([10, 8])."""
    got = losses.policy_targets_from_q([0.5, 0.4], TAU_CS)
    e = np.exp(np.array([10.0, 8.0]) - 10.0)
    want = e / e.sum()
    assert np.allclose(got, want, atol=1e-12)
    assert abs(got[0] - 0.8807970779778823) < 1e-12
    assert abs(got[1] - 0.11920292202211755) < 1e-12


def test_tau_scaling_changes_sharpness():
    q = [0.5, 0.4]
    sharp = losses.policy_targets_from_q(q, 0.01)
    soft = losses.policy_targets_from_q(q, 1.0)
    assert sharp[0] > soft[0]
    assert abs(float(soft.sum()) - 1.0) < 1e-12


def test_identical_q_gives_uniform_target():
    got = losses.policy_targets_from_q([0.3, 0.3, 0.3], TAU_CS)
    assert np.allclose(got, [1.0 / 3.0] * 3, atol=1e-12)


@pytest.mark.skipif(not CSHARP_SHARD.is_file(), reason="C# fixture yok (Shard_CrossLanguageFixture once kosmali)")
def test_csharp_policy_targets_match_python_softmax():
    _, games = shards.read_shard(CSHARP_SHARD)
    checked = 0
    for game in games:
        for dec in game.decisions:
            if dec.logged_count < 2:
                continue
            want = losses.policy_targets_from_q(dec.q, TAU_CS)
            got = dec.policy_target_cs.astype(np.float64)
            assert abs(float(got.sum()) - 1.0) < TOLERANCE, f"hedef toplami 1 degil: {got.sum()}"
            max_d = float(np.max(np.abs(got - want)))
            assert max_d <= TOLERANCE, f"tau capraz kontrolu basarisiz: max|d|={max_d:.3e}"
            checked += 1
    assert checked >= 1, "kontrol edilecek karar bulunamadi"