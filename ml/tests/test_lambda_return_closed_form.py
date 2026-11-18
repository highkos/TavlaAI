"""Test 125: TD(lambda) hedeflerinin kapali-form dogrulamasi.

`faz 7.md` incelemesinde "lambda-return formulu hatali" iddiasi dile getirildi:

    (1-lam) * sum_k lam^k r_k + lam^(T-t) * z_T

Bu, **odul tabanli** lambda-return'dur. Bu projede ara odul yoktur (odul yalnizca
oyun sonunda), bu yuzden o formul `lam^(T-t) * z_T` degerine coker. Ama dogru
tanim **deger tabanli** lambda-return'dur ve bootstrap degerlerini icerir:

    u[t] = (1-lam) * sum_{k=0}^{n-2-t} (-lam)^k * V[t+1+k] + (-lam)^(n-1-t) * z
    y[t] = -u[t]

Isaret degisimi (`(-lam)^k`) `mover` bakis acisinin her kararda degismesinden
gelir. Bu dosya, `td_lambda.td_lambda_targets` ve
`train_v2.td_lambda_targets_exclusive` fonksiyonlarinin bu kapali forma
**birebir** uydugunu kanitlar (ASSUMPTIONS.md F7-19).
"""

from __future__ import annotations

import numpy as np
import pytest

import td_lambda
from equity import PROB_COUNT
from train_v2 import FLIP_INDEX, td_lambda_targets_exclusive


LAMBDAS = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)


def _closed_form_scalar(v_hat, z, lam):
    """Deger tabanli lambda-return, kapali form (isaret degisimli)."""
    v = np.asarray(v_hat, dtype=np.float64)
    n = v.shape[0]
    out = np.empty(n, dtype=np.float64)
    for t in range(n):
        acc = 0.0
        for k in range(0, n - 1 - t):
            acc += ((-lam) ** k) * v[t + 1 + k]
        u = (1.0 - lam) * acc + ((-lam) ** (n - 1 - t)) * z
        out[t] = -u
    return out


def _closed_form_exclusive(p_hat, terminal, lam):
    """Ayni kapali form, 6 sinifli dislayici dagilim uzerinde.

    Dislayici dagilimda "isaret cevirme" bir **permutasyondur** (`flip`), negasyon
    degil. `flip` bir involusyon oldugu icin zincir acildiginda terimler
    `flip` / ozdeslik arasinda **donusumlu** olur:

        y[t] = (1-lam) * sum_{k=0}^{n-2-t} lam^k * G_k(p[t+1+k])
               + lam^(n-1-t) * G_{n-1-t}(z)

    burada `G_k` = `flip` (k cift) veya ozdeslik (k tek).
    """
    p = np.asarray(p_hat, dtype=np.float64)
    z = np.asarray(terminal, dtype=np.float64)
    n = p.shape[0]

    def g(vec, k):
        return vec[FLIP_INDEX] if k % 2 == 0 else vec

    out = np.empty((n, PROB_COUNT), dtype=np.float64)
    for t in range(n):
        acc = np.zeros(PROB_COUNT, dtype=np.float64)
        for k in range(0, n - 1 - t):
            acc += (lam ** k) * g(p[t + 1 + k], k)
        out[t] = (1.0 - lam) * acc + (lam ** (n - 1 - t)) * g(z, n - 1 - t)
    return out


# ----------------------------------------------------------------------
# Test 125a: skaler (equity) lambda-return
# ----------------------------------------------------------------------


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125a_scalar_matches_closed_form(lam):
    """`td_lambda_targets` kapali forma birebir uyar (tum lambda)."""
    v_hat = [0.1, -0.2, 0.3, -0.4, 0.05]
    z = 2.0
    got = td_lambda.td_lambda_targets(v_hat, z, lam)
    want = _closed_form_scalar(v_hat, z, lam)
    assert np.allclose(got, want, atol=1e-12), (lam, got, want)


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125a_scalar_single_decision(lam):
    """Tek karar (n=1): hedef dogrudan `-z`."""
    got = td_lambda.td_lambda_targets([0.5], 3.0, lam)
    assert np.allclose(got, [-3.0], atol=1e-12)


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125a_scalar_does_not_collapse_to_zero(lam):
    """Ara odul sifir olsa da hedef sifira cokmez: bootstrap degerleri var."""
    v_hat = [0.4, -0.3, 0.2, -0.1]
    got = td_lambda.td_lambda_targets(v_hat, 1.0, lam)
    assert np.all(np.abs(got) > 1e-6), got


def test_125a_lambda_one_is_pure_monte_carlo():
    """lam=1 -> hedef yalnizca terminal deger, isaret donusumlu."""
    v_hat = [9.9, -9.9, 9.9]
    got = td_lambda.td_lambda_targets(v_hat, 2.0, 1.0)
    assert np.allclose(got, [-2.0, 2.0, -2.0], atol=1e-12)


def test_125a_lambda_zero_is_next_value():
    """lam=0 -> hedef yalnizca bir sonraki tahmin (son eleman -z)."""
    v_hat = [9.9, -9.9, 9.9]
    got = td_lambda.td_lambda_targets(v_hat, 2.0, 0.0)
    assert np.allclose(got, [9.9, -9.9, -2.0], atol=1e-12)


def test_125a_bootstrap_term_is_present():
    """lam<1 iken V_hat degistiginde hedef DEGISMELI (bootstrap kaniti)."""
    z = 1.0
    a = td_lambda.td_lambda_targets([0.0, 0.0, 0.0], z, 0.5)
    b = td_lambda.td_lambda_targets([0.0, 0.0, 5.0], z, 0.5)
    assert not np.allclose(a, b), "V_hat hedefe girmiyor: bootstrap yok"


def test_125a_reward_only_formula_would_collapse():
    """Iddia edilen (odul tabanli) formul ara odul yokken coker - kanit."""
    lam = 0.7
    n = 4
    z = 2.0
    reward_only = np.array([(lam ** (n - 1 - t)) * z for t in range(n)])
    real = td_lambda.td_lambda_targets([0.1, -0.2, 0.3, -0.4], z, lam)
    # Odul tabanli formul isaret degisimini de kacirir.
    assert not np.allclose(np.abs(reward_only), np.abs(real), atol=1e-6)


# ----------------------------------------------------------------------
# Test 125b: 6 sinifli dislayici lambda-return
# ----------------------------------------------------------------------


def _random_probs(rng, n):
    p = rng.random((n, PROB_COUNT))
    return p / p.sum(axis=1, keepdims=True)


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125b_exclusive_matches_closed_form(lam):
    """`td_lambda_targets_exclusive` kapali forma birebir uyar."""
    rng = np.random.default_rng(20261117)
    p_hat = _random_probs(rng, 5)
    terminal = np.zeros(PROB_COUNT)
    terminal[0] = 1.0
    got = td_lambda_targets_exclusive(p_hat, terminal, lam)
    want = _closed_form_exclusive(p_hat, terminal, lam)
    assert np.allclose(got, want, atol=1e-12), lam


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125b_exclusive_rows_are_distributions(lam):
    """Her satir gecerli bir olasilik dagilimi (toplam 1, negatif yok)."""
    rng = np.random.default_rng(7)
    p_hat = _random_probs(rng, 6)
    terminal = np.zeros(PROB_COUNT)
    terminal[3] = 1.0
    got = td_lambda_targets_exclusive(p_hat, terminal, lam)
    assert np.allclose(got.sum(axis=1), 1.0, atol=1e-12)
    assert np.all(got >= -1e-12)


@pytest.mark.parametrize("lam", LAMBDAS)
def test_125b_exclusive_last_row_is_flipped_terminal(lam):
    """Son satir terminalin isaret donusumu."""
    rng = np.random.default_rng(11)
    p_hat = _random_probs(rng, 3)
    terminal = np.zeros(PROB_COUNT)
    terminal[0] = 1.0
    got = td_lambda_targets_exclusive(p_hat, terminal, lam)
    assert np.allclose(got[-1], terminal[FLIP_INDEX], atol=1e-12)


def test_125b_exclusive_lambda_one_is_pure_monte_carlo():
    """lam=1 -> hedef yalnizca terminal, satirlar donusumlu."""
    rng = np.random.default_rng(3)
    p_hat = _random_probs(rng, 4)
    terminal = np.zeros(PROB_COUNT)
    terminal[0] = 1.0
    got = td_lambda_targets_exclusive(p_hat, terminal, 1.0)
    flipped = terminal[FLIP_INDEX]
    for t in range(4):
        want = flipped if (3 - t) % 2 == 0 else terminal
        assert np.allclose(got[t], want, atol=1e-12), t


def test_125b_exclusive_bootstrap_term_is_present():
    """lam<1 iken p_hat hedefe girmeli."""
    terminal = np.zeros(PROB_COUNT)
    terminal[0] = 1.0
    a = td_lambda_targets_exclusive(np.full((3, PROB_COUNT), 1.0 / PROB_COUNT), terminal, 0.5)
    b = np.full((3, PROB_COUNT), 1.0 / PROB_COUNT)
    b[2] = np.zeros(PROB_COUNT)
    b[2, 5] = 1.0
    c = td_lambda_targets_exclusive(b, terminal, 0.5)
    assert not np.allclose(a, c), "p_hat hedefe girmiyor: bootstrap yok"


def test_125b_exclusive_rejects_bad_shape():
    with pytest.raises(ValueError):
        td_lambda_targets_exclusive(np.zeros((3, 5)), np.zeros(PROB_COUNT), 0.5)
    with pytest.raises(ValueError):
        td_lambda_targets_exclusive(np.zeros((3, PROB_COUNT)), np.zeros(5), 0.5)
    with pytest.raises(ValueError):
        td_lambda_targets_exclusive(np.zeros((3, PROB_COUNT)), np.zeros(PROB_COUNT), 1.5)


def test_125b_exclusive_empty_input():
    got = td_lambda_targets_exclusive(np.zeros((0, PROB_COUNT)), np.zeros(PROB_COUNT), 0.5)
    assert got.shape == (0, PROB_COUNT)
