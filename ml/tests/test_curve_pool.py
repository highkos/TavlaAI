"""Faz 7-R adim 0 madde 2: ogrenme egrisi havuzu testleri (Test 168-175)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import curve_pool as cp  # noqa: E402
import gnubg_er  # noqa: E402


def _synthetic_pool(seed: int = 0, games: int = 4, per_game: int = 3) -> cp.CurvePool:
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    offsets = [0]
    best: list[int] = []
    y: list[float] = []
    cand_equity: list[float] = []
    game_ids: list[str] = []
    split: list[str] = []
    for g in range(games):
        for k in range(per_game):
            n = 2 + (g + k) % 3
            block = rng.normal(size=(n, gnubg_er.VECTOR_SIZE)).astype(np.float32)
            equities = rng.normal(size=n).astype(np.float32)
            rows.append(block)
            offsets.append(offsets[-1] + n)
            best.append(int(np.argmax(equities)))
            y.append(float(np.max(equities)))
            cand_equity.extend(float(v) for v in equities)
            game_ids.append("g%d" % g)
            split.append(cp.SPLIT_HELD_OUT if g == 0 else cp.SPLIT_TRAIN)
    return cp.CurvePool(
        x=np.concatenate(rows, axis=0),
        offsets=np.asarray(offsets, dtype=np.int64),
        best=np.asarray(best, dtype=np.int32),
        y=np.asarray(y, dtype=np.float32),
        cand_equity=np.asarray(cand_equity, dtype=np.float32),
        game_ids=game_ids,
        split=split,
        meta={"poolVersion": cp.POOL_VERSION},
    )


def test_168_curve_pool_accessors():
    pool = _synthetic_pool()
    assert len(pool) == 12
    assert pool.candidates(0).shape == (2, gnubg_er.VECTOR_SIZE)
    assert pool.candidate_equities(0).shape == (2,)
    assert len(pool.train_indices()) == 9
    assert len(pool.held_out_indices()) == 3
    assert pool.game_ids[0] == "g0"
    assert pool.split[0] == cp.SPLIT_HELD_OUT


def test_169_curve_pool_subset():
    pool = _synthetic_pool()
    indices = pool.train_indices()[:4]
    dataset = pool.subset(indices)
    assert len(dataset) == 4
    assert dataset.x.shape[1] == gnubg_er.VECTOR_SIZE
    assert dataset.offsets.shape[0] == 5
    assert dataset.best.shape[0] == 4
    assert dataset.y.shape[0] == 4
    # Ilk pozisyonun aday sayisi korunur.
    assert dataset.candidates(0).shape[0] == pool.candidates(indices[0]).shape[0]


def test_170_curve_pool_subset_empty():
    pool = _synthetic_pool()
    dataset = pool.subset([])
    assert len(dataset) == 0
    assert dataset.x.shape == (0, gnubg_er.VECTOR_SIZE)


def test_171_curve_pool_stats():
    pool = _synthetic_pool()
    stats = pool.stats()
    assert stats["count"] == 12
    assert stats["train"] == 9
    assert stats["heldOut"] == 3
    assert stats["trainGames"] == 3
    assert stats["heldOutGames"] == 1
    assert stats["candidatesMin"] >= 2
    assert stats["candidatesMax"] <= 4


def test_172_curve_pool_roundtrip(tmp_path):
    pool = _synthetic_pool()
    path = tmp_path / "pool.npz"
    cp.save_pool(pool, path)
    loaded = cp.load_pool(path)
    assert len(loaded) == len(pool)
    assert loaded.game_ids == pool.game_ids
    assert loaded.split == pool.split
    assert np.allclose(loaded.x, pool.x)
    assert np.allclose(loaded.cand_equity, pool.cand_equity)
    assert loaded.meta["poolVersion"] == cp.POOL_VERSION


def test_173_curve_pool_load_missing(tmp_path):
    with pytest.raises(cp.CurvePoolError):
        cp.load_pool(tmp_path / "yok.npz")


def test_174_curve_pool_pad():
    pool = _synthetic_pool()
    indices = pool.train_indices()
    x, mask, width = cp._pad(pool, indices)
    assert x.shape == (len(indices), width, gnubg_er.VECTOR_SIZE)
    assert mask.shape == (len(indices), width)
    assert width == max(pool.candidates(i).shape[0] for i in indices)
    # Dolgu satirlari maskede False.
    for row, i in enumerate(indices):
        k = pool.candidates(i).shape[0]
        assert mask[row, :k].all()
        assert not mask[row, k:].any()


def test_175_curve_pool_train_fn_contract():
    torch = pytest.importorskip("torch")
    pool = _synthetic_pool()
    train_fn = cp.make_train_fn(pool, epochs=1, batch=4, device="cpu", profile="small")
    result = train_fn(6, 0)
    assert set(result) >= {"losses", "gameIds", "slope", "mae", "inSampleLoss", "heldOutLoss", "note"}
    assert set(result["losses"]) == {"policy", "value"}
    assert len(result["losses"]["policy"]) == len(pool.held_out_indices())
    assert len(result["gameIds"]["policy"]) == len(pool.held_out_indices())
    assert all(np.isfinite(v) for v in result["losses"]["policy"])
    assert "epochs=1" in result["note"]
    # Istek havuzdan buyukse hata.
    with pytest.raises(cp.CurvePoolError):
        train_fn(10_000, 0)
    with pytest.raises(cp.CurvePoolError):
        train_fn(0, 0)
