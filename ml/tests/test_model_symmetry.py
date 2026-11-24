"""F7-116: mimari antisimetri (Higgins agirlik simetrisi) — Test 342-348.

Renk takasi ``T = antisymmetry.flip_perspective`` girdi uzerinde bir
**girisimdir** (``T^2 = I``). Bu yuzden girdi uzayi ``V- = {v : Tv = -v}``
(109 boyut) ve ``V+ = {v : Tv = v}`` (112 boyut) alt uzaylarina ayrilir.
:class:`model.BackgammonNetV3` tek kolu yalnizca ``V-`` uzerinde calistirir ve
bias kullanmaz; boylece

* ``value(Tx) = -value(x)``,
* ``policy_logit(Tx) = -policy_logit(x)``,
* ``probs(Tx) = Pi probs(x)`` (``Pi = (W L)(GW GL)(BW BL)``)

**tanim geregi** saglanir. Egitim artirimi (``augment_perspectives``) bu
kusuru cozmez; kullanici bu yolu acikca reddetti.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import antisymmetry  # noqa: E402
import model  # noqa: E402

PERM = [3, 4, 5, 0, 1, 2]  # Pi: (W L)(GW GL)(BW BL)


def _flip_batch(x: torch.Tensor) -> torch.Tensor:
    return torch.tensor(
        [antisymmetry.flip_perspective(row.tolist()) for row in x], dtype=torch.float32
    )


def test_342_symmetry_bases_are_orthonormal_and_complete():
    """``Q-``/``Q+`` ortonormal ve birlikte tam baz olusturur."""
    q_minus, q_plus = model.symmetry_bases()
    assert q_minus.shape == (model.VECTOR_SIZE, 109)
    assert q_plus.shape == (model.VECTOR_SIZE, 112)
    eye_minus = torch.eye(q_minus.shape[1])
    eye_plus = torch.eye(q_plus.shape[1])
    assert float((q_minus.T @ q_minus - eye_minus).abs().max()) < 1e-6
    assert float((q_plus.T @ q_plus - eye_plus).abs().max()) < 1e-6
    assert float((q_minus.T @ q_plus).abs().max()) < 1e-6
    recon = q_minus @ q_minus.T + q_plus @ q_plus.T
    assert float((recon - torch.eye(model.VECTOR_SIZE)).abs().max()) < 1e-6


def test_343_flip_map_matches_flip_perspective():
    """``_flip_map`` ile ``antisymmetry.flip_perspective`` birebir ayni donusum."""
    fmap = model._flip_map()
    assert len(fmap) == model.VECTOR_SIZE
    rng = torch.Generator().manual_seed(7)
    for _ in range(20):
        v = torch.randn(model.VECTOR_SIZE, generator=rng).tolist()
        expected = antisymmetry.flip_perspective(v)
        rebuilt = [0.0] * model.VECTOR_SIZE
        for i, (j, sign) in enumerate(fmap):
            rebuilt[j] = sign * v[i]
        assert max(abs(a - b) for a, b in zip(expected, rebuilt)) < 1e-12


def test_344_flip_map_is_an_involution():
    """``T^2 = I``: baz ayriminin gecerlilik kosulu."""
    fmap = model._flip_map()
    for i, (j, sign) in enumerate(fmap):
        back, back_sign = fmap[j]
        assert back == i
        assert back_sign * sign == pytest.approx(1.0)


def test_345_value_and_policy_are_exactly_antisymmetric():
    """``value(Tx) = -value(x)`` ve ``policy_logit(Tx) = -policy_logit(x)``."""
    net = model.build_model(output_version=2, profile="medium", symmetry=True, seed=3)
    net.eval()
    x = torch.randn(16, model.VECTOR_SIZE)
    with torch.no_grad():
        probs_a, logit_a = net(x)
        probs_b, logit_b = net(_flip_batch(x))
    assert float((logit_a + logit_b).abs().max()) < 1e-5
    assert float((probs_b[:, PERM] - probs_a).abs().max()) < 1e-5
    assert float(probs_a.sum(dim=-1).sub(1.0).abs().max()) < 1e-5


def test_346_equity_is_exactly_antisymmetric():
    """Turetilen equity de tam antisimetrik olmali (kup/karar bunu kullanir)."""
    from equity import equity_from_exclusive

    net = model.build_model(output_version=2, profile="small", symmetry=True, seed=5)
    net.eval()
    x = torch.randn(16, model.VECTOR_SIZE)
    with torch.no_grad():
        probs_a, _ = net(x)
        probs_b, _ = net(_flip_batch(x))
    eq_a = equity_from_exclusive(probs_a.tolist())
    eq_b = equity_from_exclusive(probs_b.tolist())
    assert max(abs(a + b) for a, b in zip(eq_a, eq_b)) < 1e-5


def test_347_symmetric_model_has_no_bias_in_odd_branch():
    """Tek kol **bias'siz** olmali; aksi halde antisimetri bozulur."""
    net = model.build_model(output_version=2, profile="small", symmetry=True, seed=1)
    for name, module in net.named_modules():
        if isinstance(module, torch.nn.Linear) and name.startswith("backbone.net"):
            assert module.bias is None, name
    assert net.value_head.bias is None
    assert net.policy_head.bias is None
    assert net.probs_odd.bias is None


def test_348_symmetric_model_uses_fewer_parameters_than_v2():
    """Ilk katman ``221 -> 109``: parametre sayisi **duser** (Higgins kazanci)."""
    plain = model.build_model(output_version=2, profile="medium", seed=1)
    sym = model.build_model(output_version=2, profile="medium", symmetry=True, seed=1)
    assert model.parameter_count(sym) < model.parameter_count(plain)
    assert sym.arch.startswith("sym-")
    assert sym.output_version == 2
    # ONNX sozlesmesi degismez: iki cikti, ayni adlar.
    probs, logit = sym(torch.zeros(2, model.VECTOR_SIZE))
    assert probs.shape == (2, model.PROB_COUNT)
    assert logit.shape == (2, 1)


def test_349_symmetry_rejected_for_output_version_one():
    """``symmetry`` yalnizca ``output_version = 2`` icin anlamlidir."""
    with pytest.raises(ValueError):
        model.build_model(output_version=1, symmetry=True)


def test_375_odd_branch_is_odd_under_the_flip_not_under_negation():
    """Tek kol ``T`` altinda tek olmali; **negasyon** altinda teklik yetmez.

    ``T = flip_perspective`` bir permutasyon/isaret donusumudur (``Tx != -x``).
    Tek kolu tam 221 boyutlu girdiye baglamak yalnizca ``f(-x) = -f(x)`` verir,
    ``f(Tx) = -f(x)`` vermez; bu yuzden ``V-`` izdusumu **zorunludur**.
    """
    net = model.build_model(output_version=2, profile="small", symmetry=True, seed=3)
    net.eval()
    assert net.backbone.odd_in == net.backbone.odd_dim
    x = torch.randn(8, model.VECTOR_SIZE)
    with torch.no_grad():
        h_a, e_a = net.backbone(x)
        h_b, e_b = net.backbone(_flip_batch(x))
    assert float((h_a + h_b).abs().max()) < 1e-5
    assert float((e_a - e_b).abs().max()) < 1e-5
    # ``T`` negasyon degildir: ``Tx != -x``.
    assert float((_flip_batch(x) + x).abs().max()) > 1.0


def test_376_higgins_net_is_exactly_antisymmetric():
    """``HigginsNet`` cikti izdusumu ile **tam** antisimetri verir.

    Duz govde iki bakistan degerlendirilir: ``g(x) = (f(x) - f(Tx)) / 2`` ve
    ``L(x) = (l(x) + Pi l(Tx)) / 2``. Ikisi de tanim geregi tamdir.
    """
    net = model.build_model(
        output_version=2, profile="small", symmetry=True, symmetry_mode="higgins", seed=4
    )
    net.eval()
    assert net.arch.startswith("higgins-")
    x = torch.randn(8, model.VECTOR_SIZE)
    with torch.no_grad():
        probs_a, logit_a = net(x)
        probs_b, logit_b = net(_flip_batch(x))
    assert float((logit_a + logit_b).abs().max()) < 1e-6
    perm = list(model.PROB_PERM)
    assert float((probs_b - probs_a[:, perm]).abs().max()) < 1e-6
    assert float((probs_a.sum(-1) - 1.0).abs().max()) < 1e-5


def test_377_higgins_net_matches_plain_parameter_count():
    """``HigginsNet`` ifade gucu duz V2 ile aynidir: parametre sayisi esit."""
    plain = model.build_model(output_version=2, profile="medium", seed=1)
    hig = model.build_model(
        output_version=2, profile="medium", symmetry=True, symmetry_mode="higgins", seed=1
    )
    assert model.parameter_count(hig) == model.parameter_count(plain)
    probs, logit = hig(torch.zeros(2, model.VECTOR_SIZE))
    assert probs.shape == (2, model.PROB_COUNT)
    assert logit.shape == (2, 1)


def test_378_unknown_symmetry_mode_rejected():
    """Bilinmeyen ``symmetry_mode`` sessizce yok sayilmaz."""
    with pytest.raises(ValueError):
        model.build_model(output_version=2, symmetry=True, symmetry_mode="yok")