"""K5: 6 sinifli dagilim hedefi (Test 235-241).

Kullanicinin ``tespitler.md`` K5 maddesi: deger yolu 4x'ten sonra plato yapiyor
(0.0460 -> 0.0454) ve politika dusmeye devam ediyor. Skaler equity tek basina
deger yoluna yeterli sinyal vermiyor; gnubg'nin 6 sinifli dagilimi ayni ileri
gecislerden cok daha fazla bilgi cikarir.

Bu dosya (a) gnubg ``eval`` tablosunun 6 sinifa dogru eslendigini, (b) dagilimin
veri kumesi uzerinden kayipsiz tasindigini, (c) KL teriminin gercekten ogrenildigini
dogrular.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import gnubg_distill as gd  # noqa: E402
import gnubg_er as ge  # noqa: E402

#: gnubg ``eval`` blogu: ``Win  W(g)  W(bg)  L(g)  L(bg)  Equity`` (kumulatif).
EVAL_TEXT = """
             Win   W(g)  W(bg)  L(g)  L(bg)   Equity  (EMG)
static:    0.6000 0.2000 0.0500 0.1000 0.0200  +0.3300
 1 ply:    0.6100 0.2100 0.0600 0.0900 0.0100  +0.3900
 2 ply:    0.6200 0.2200 0.0700 0.0800 0.0050  +0.4450
"""


def test_235_parse_eval_dist_maps_to_prob_order():
    dist = ge.parse_eval_dist(EVAL_TEXT)
    assert set(dist) == {"static", "1", "2"}
    static = dist["static"]
    assert len(static) == 6
    # PROB_ORDER = (W, GW, BW, L, GL, BL); gnubg kumulatif sutunlarindan turetilir.
    assert static[0] == pytest.approx(0.40)  # W  = Win - W(g)
    assert static[1] == pytest.approx(0.15)  # GW = W(g) - W(bg)
    assert static[2] == pytest.approx(0.05)  # BW = W(bg)
    assert static[3] == pytest.approx(0.30)  # L  = (1-Win) - L(g)
    assert static[4] == pytest.approx(0.08)  # GL = L(g) - L(bg)
    assert static[5] == pytest.approx(0.02)  # BL = L(bg)
    assert sum(static) == pytest.approx(1.0)
    assert dist["2"][3] == pytest.approx(0.30)


def test_236_parse_eval_dist_equity_matches_parse_eval():
    """Dagilimdan turetilen equity, ``parse_eval`` skaleriyle ayni olmali."""
    from equity import equity_from_exclusive

    dist = ge.parse_eval_dist(EVAL_TEXT)
    scalars = ge.parse_eval(EVAL_TEXT)
    for key, probs in dist.items():
        assert float(equity_from_exclusive(probs)) == pytest.approx(scalars[key], abs=1e-9)


def test_237_parse_evals_dist_splits_blocks():
    text = "The pip counts are: MONSTER 10, gnubg 12.\n" + EVAL_TEXT
    text += "The pip counts are: MONSTER 11, gnubg 13.\n" + EVAL_TEXT
    blocks = ge.parse_evals_dist(text)
    assert len(blocks) == 2
    assert blocks[0]["static"][0] == pytest.approx(0.40)
    assert blocks[1]["2"][3] == pytest.approx(0.30)


def _dataset(n: int = 4, *, with_dist: bool = True) -> gd.PolicyDataset:
    rng = np.random.default_rng(11)
    width = 3
    x = rng.random((n * width, 221)).astype(np.float32)
    offsets = np.arange(0, n * width + 1, width, dtype=np.int64)
    best = np.zeros(n, dtype=np.int32)
    y = np.zeros(n, dtype=np.float32)
    dist = None
    if with_dist:
        raw = rng.random((n, 6)).astype(np.float32)
        dist = raw / raw.sum(axis=1, keepdims=True)
    return gd.PolicyDataset(x=x, offsets=offsets, best=best, y=y, dist=dist)


def test_238_policy_dataset_has_dist_and_roundtrip(tmp_path):
    ds = _dataset(4)
    assert ds.has_dist() is True
    assert ds.stats()["hasDist"] is True

    path = tmp_path / "policy.npz"
    gd.save_policy_dataset(ds, path)
    back = gd.load_policy_dataset(path)
    assert back.has_dist() is True
    assert np.allclose(back.dist, ds.dist)

    plain = _dataset(4, with_dist=False)
    assert plain.has_dist() is False
    gd.save_policy_dataset(plain, tmp_path / "plain.npz")
    assert gd.load_policy_dataset(tmp_path / "plain.npz").has_dist() is False


def test_239_build_policy_dataset_keeps_dist_column_with_nan_rows():
    """F7-126: tek eksik satir **tum** dagilim sutununu dusurmemeli."""
    base = gd.PolicyPosition(
        vectors=[[0.0] * 221, [1.0] * 221],
        best_index=0,
        best_equity=0.1,
        turn=1,
        dice=(3, 4),
        best_move="8/5 6/3",
        candidates=2,
        best_dist=[0.5, 0.1, 0.0, 0.5, 0.0, 0.0],
    )
    full = gd.build_policy_dataset([base, base])
    assert full.has_dist() is True
    assert full.dist.shape == (2, 6)

    partial = gd.PolicyPosition(
        vectors=base.vectors,
        best_index=0,
        best_equity=0.1,
        turn=1,
        dice=(3, 4),
        best_move="8/5 6/3",
        candidates=2,
        best_dist=None,
    )
    mixed = gd.build_policy_dataset([base, partial])
    assert mixed.has_dist() is True
    assert mixed.dist.shape == (2, 6)
    assert mixed.dist_valid_mask().tolist() == [True, False]
    assert np.isnan(mixed.dist[1]).all()
    assert mixed.stats()["distMissing"] == 1

    # Hicbir satir gecerli degilse sutun hic yazilmaz.
    none_valid = gd.build_policy_dataset([partial, partial])
    assert none_valid.has_dist() is False
    assert none_valid.dist is None


def test_240_train_policy_head_rejects_dist_weight_without_dist():
    pytest.importorskip("torch")
    from model import build_model

    model = build_model(221, 32, 16, seed=0, output_version=2, profile="small")
    ds = _dataset(4, with_dist=False)
    with pytest.raises(ValueError, match="dist"):
        gd.train_policy_head(model, ds, steps=2, dist_weight=0.5)


def test_241_train_policy_head_learns_distribution():
    """KL terimi acikken dagilim hedefine yaklasmali (kayip dusmeli)."""
    torch = pytest.importorskip("torch")
    from model import build_model

    torch.manual_seed(0)
    model = build_model(221, 32, 16, seed=0, output_version=2, profile="small")
    ds = _dataset(8)
    report = gd.train_policy_head(
        model, ds, steps=80, lr=1e-2, batch=8, seed=0, dist_weight=1.0
    )
    assert report["distWeight"] == pytest.approx(1.0)
    assert report["hasDist"] is True
    assert report["lastLoss"] < report["firstLoss"]


# ----------------------------------------------------------------------
# F7-126: eksik dagilim satiri sutunu dusurmemeli (Test 405-408)
# ----------------------------------------------------------------------


def test_405_concat_fills_nan_for_parts_without_dist():
    """Bir dilimde sutun hic yoksa ``nan`` ile doldurulur, sutun dusurulmez."""
    with_dist = _dataset(3)
    without = _dataset(2, with_dist=False)
    merged = gd.concat_policy_datasets([with_dist, without])
    assert merged.has_dist() is True
    assert merged.dist.shape == (5, 6)
    assert merged.dist_valid_mask().tolist() == [True, True, True, False, False]
    assert np.isnan(merged.dist[3:]).all()
    assert merged.stats()["distMissing"] == 2


def test_406_concat_drops_dist_when_no_part_has_it():
    merged = gd.concat_policy_datasets(
        [_dataset(2, with_dist=False), _dataset(3, with_dist=False)]
    )
    assert merged.has_dist() is False
    assert merged.dist is None


def test_407_train_policy_head_masks_nan_dist_rows():
    """``nan`` hedefli satirlar KL terimine girmemeli (kayip ``nan`` olmamali)."""
    torch = pytest.importorskip("torch")
    from model import build_model

    ds = _dataset(8)
    ds.dist[2] = np.nan
    ds.dist[5] = np.nan
    assert ds.stats()["distMissing"] == 2

    torch.manual_seed(0)
    model = build_model(221, 32, 16, seed=0, output_version=2, profile="small")
    report = gd.train_policy_head(
        model, ds, steps=20, lr=1e-2, batch=8, seed=0, dist_weight=1.0
    )
    assert np.isfinite(report["lastLoss"])
    assert report["hasDist"] is True


def test_408_save_roundtrip_preserves_nan_dist_rows(tmp_path):
    ds = _dataset(4)
    ds.dist[1] = np.nan
    path = tmp_path / "nan.npz"
    gd.save_policy_dataset(ds, path)
    back = gd.load_policy_dataset(path)
    assert back.has_dist() is True
    assert back.dist_valid_mask().tolist() == [True, False, True, True]
    assert np.isnan(back.dist[1]).all()