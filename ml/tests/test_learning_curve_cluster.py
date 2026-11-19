"""Faz 7-R adim 0 madde 2: oyun duzeyi kume bootstrap + cok tohum (Test 182-187)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import learning_curve as lc  # noqa: E402


def _point(mult: int, positions: int, losses, game_ids=None) -> lc.CurvePoint:
    return lc.CurvePoint(
        multiplier=mult,
        positions=positions,
        losses={"policy": list(losses)},
        game_ids={"policy": list(game_ids)} if game_ids else {},
    )


def test_182_cluster_means_groups_by_game():
    losses = [1.0, 3.0, 5.0, 7.0]
    ids = ["g0", "g0", "g1", "g1"]
    means, groups = lc._cluster_means(losses, ids)
    assert means.tolist() == [2.0, 6.0]
    assert len(groups) == 2
    assert groups[0].tolist() == [1.0, 3.0]
    assert groups[1].tolist() == [5.0, 7.0]


def test_183_cluster_means_without_ids():
    losses = [1.0, 2.0, 3.0]
    means, groups = lc._cluster_means(losses, None)
    assert means.tolist() == [1.0, 2.0, 3.0]
    assert len(groups) == 3
    # Yanlis uzunlukta kimlik listesi de pozisyon duzeyine duser.
    means2, groups2 = lc._cluster_means(losses, ["g0"])
    assert means2.tolist() == [1.0, 2.0, 3.0]
    assert len(groups2) == 3


def test_184_fit_log_slope_clustered_wider():
    """Ayni oyunun pozisyonlari korelidir: kume GA'si pozisyon GA'sindan dar olamaz."""
    rng = np.random.default_rng(7)
    points = []
    for k, mult in enumerate((1, 2, 4, 8)):
        n = 40
        base = 0.10 - 0.01 * k
        # Oyun basina sistematik sapma: kume ici korelasyon.
        game_effect = np.repeat(rng.normal(scale=0.02, size=10), 4)
        losses = base + game_effect + rng.normal(scale=0.001, size=n)
        ids = ["g%d" % (i // 4) for i in range(n)]
        points.append(_point(mult, 100 * mult, losses, ids))

    clustered = lc.fit_log_slope(points, path="policy", resamples=2000, cluster=True)
    positional = lc.fit_log_slope(points, path="policy", resamples=2000, cluster=False)
    assert clustered["clustered"] is True
    assert positional["clustered"] is False
    assert clustered["clusters"] == 10
    assert positional["clusters"] == 40
    width_c = clustered["ciHigh"] - clustered["ciLow"]
    width_p = positional["ciHigh"] - positional["ciLow"]
    assert width_c > width_p
    # Nokta tahmini ayni (OLS ayni veriden).
    assert clustered["slope"] == pytest.approx(positional["slope"])


def test_185_fit_log_slope_insufficient():
    entry = lc.fit_log_slope([_point(1, 100, [0.1])], path="policy", resamples=100)
    assert entry["n"] == 0
    assert np.isnan(entry["slope"])
    assert entry["clustered"] is True


def test_186_run_curve_multi_seed_pools():
    def train_fn(positions: int, seed: int) -> dict:
        n = 20
        base = 0.10 - 0.005 * (positions // 100)
        losses = [base + 0.001 * seed] * n
        ids = ["g%d" % (i // 5) for i in range(n)]
        return {
            "losses": {"policy": losses},
            "gameIds": {"policy": ids},
            "slope": None,
            "mae": None,
            "inSampleLoss": 0.5,
            "heldOutLoss": base,
            "note": "seed=%d" % seed,
        }

    report = lc.run_curve_multi_seed(
        sizes=(100, 200, 400),
        train_fn=train_fn,
        seeds=(0, 1, 2),
        resamples=500,
    )
    assert report.seeds == [0, 1, 2]
    assert len(report.points) == 3
    # Havuzlanmis: her noktada 3 tohum x 20 pozisyon.
    assert len(report.points[0].losses["policy"]) == 60
    # Oyun kimlikleri tohumla oneklenir: ayni kimlik farkli tohumda ayni kume olmaz.
    ids = report.points[0].game_ids["policy"]
    assert len(set(ids)) == 12
    assert all(i.startswith("s") for i in ids)
    assert report.clustered is True
    assert "policy" in report.slopes
    assert any("Havuzlanmis 3 tohum" in n for n in report.notes)


def test_187_run_curve_multi_seed_rejects_duplicates():
    def train_fn(positions: int, seed: int) -> dict:
        return {"losses": {"policy": [0.1]}, "gameIds": {"policy": ["g0"]}}

    with pytest.raises(ValueError):
        lc.run_curve_multi_seed(sizes=(10, 20), train_fn=train_fn, seeds=(0, 0))
    with pytest.raises(ValueError):
        lc.run_curve_multi_seed(sizes=(10, 20), train_fn=train_fn, seeds=())
