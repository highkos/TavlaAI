"""Faz 7-R adim 0 madde 2: oyun duzeyi kume bootstrap + cok tohum (Test 182-187)."""

from __future__ import annotations

import sys
from pathlib import Path

import math

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


# ----------------------------------------------------------------------
# Tohum oybirligi, doygunluk fiti, in-sample birimi (Test 193-197)
# ----------------------------------------------------------------------


def _curve_point(mult, positions, mean, path="policy"):
    return lc.CurvePoint(
        multiplier=mult,
        positions=positions,
        losses={path: [mean] * 10},
        game_ids={path: ["g%d" % i for i in range(10)]},
    )


def test_193_decision_requires_seed_unanimity():
    """Havuz 'olcek' dese bile tohumlar ayrissa karar 'belirsiz' olmali."""
    report = lc.CurveReport()
    report.points = [_curve_point(1, 100, 0.10), _curve_point(2, 200, 0.08), _curve_point(4, 400, 0.06)]
    report.slopes = {
        "policy": {"gain": 0.02, "gainCiLow": 0.01, "gainCiHigh": 0.03, "path": "policy"}
    }
    # Tek tohum: havuz karari gecerli.
    assert report.decision == lc.DECISION_SCALES
    assert report.seed_agreement is True

    # Iki tohum ayni karari verirse yine gecerli.
    report.seed_decisions = {0: lc.DECISION_SCALES, 1: lc.DECISION_SCALES}
    assert report.decision == lc.DECISION_SCALES

    # Bir tohum ayrisirsa -> belirsiz.
    report.seed_decisions = {0: lc.DECISION_SCALES, 1: lc.DECISION_UNDETERMINED}
    assert report.decision == lc.DECISION_UNDETERMINED
    assert report.seed_agreement is False


def test_194_decision_pipeline_also_requires_unanimity():
    report = lc.CurveReport()
    report.points = [_curve_point(1, 100, 0.10), _curve_point(2, 200, 0.10)]
    report.slopes = {
        "policy": {"gain": 0.0, "gainCiLow": -0.001, "gainCiHigh": 0.001, "path": "policy"}
    }
    assert report.decision == lc.DECISION_PIPELINE
    report.seed_decisions = {0: lc.DECISION_PIPELINE, 1: lc.DECISION_SCALES}
    assert report.decision == lc.DECISION_UNDETERMINED


def test_195_saturation_fit_recovers_floor():
    """``ER = a*N^-b + c``: sentetik veride ``c`` geri kazanilmali."""
    a, b, c = 0.5, 0.5, 0.02
    points = []
    for mult, n in [(1, 100), (2, 200), (4, 400), (8, 800), (16, 1600)]:
        mean = a * n ** (-b) + c
        points.append(_curve_point(mult, n, mean))
    fit = lc.fit_saturation(points, path="policy")
    assert fit["c"] == pytest.approx(c, abs=0.01)
    assert fit["b"] == pytest.approx(b, abs=0.15)
    assert fit["rmse"] < 0.005
    assert fit["n"] == 5


def test_196_saturation_fit_needs_three_points():
    fit = lc.fit_saturation([_curve_point(1, 100, 0.1), _curve_point(2, 200, 0.09)], path="policy")
    assert math.isnan(fit["c"])
    assert fit["n"] == 2


def test_197_in_sample_unit_is_labelled_in_markdown():
    report = lc.CurveReport()
    point = _curve_point(1, 100, 0.10)
    point.in_sample_loss = 0.6667
    point.in_sample_unit = lc.IN_SAMPLE_UNITS["policy"]
    report.points = [point]
    report.slopes = {
        "policy": {"gain": 0.02, "gainCiLow": 0.01, "gainCiHigh": 0.03, "path": "policy"}
    }
    md = lc.build_markdown(report)
    assert "In-sample birimi" in md
    assert "capraz-entropi" in md
    assert "bir ER" in md
    assert lc.CURVE_MULTIPLIERS == (1, 2, 4, 8, 16, 32)


# ----------------------------------------------------------------------
# In-sample birimi turetme + JSON'dan rapor yeniden uretimi (Test 209-211)
# ----------------------------------------------------------------------


def test_209_in_sample_unit_falls_back_to_combined():
    """Birim alani bos olsa bile in-sample kayip varsa birim **yazilir**."""
    point = _curve_point(1, 100, 0.10)
    point.in_sample_loss = 1.1721
    assert point.in_sample_unit == ""
    assert point.resolved_in_sample_unit == lc.IN_SAMPLE_UNITS["combined"]
    assert point.to_dict()["inSampleUnit"] == lc.IN_SAMPLE_UNITS["combined"]

    # Olcum yoksa birim de yok: uydurulmaz.
    empty = _curve_point(1, 100, 0.10)
    assert empty.resolved_in_sample_unit == ""
    assert empty.to_dict()["inSampleUnit"] == ""


def test_210_report_roundtrip_preserves_decision_and_units():
    report = lc.CurveReport()
    for mult, n, mean in [(1, 100, 0.10), (2, 200, 0.08), (4, 400, 0.06)]:
        point = _curve_point(mult, n, mean)
        point.in_sample_loss = 0.5
        report.points.append(point)
    report.slopes = {
        "policy": {"gain": 0.02, "gainCiLow": 0.01, "gainCiHigh": 0.03, "path": "policy"}
    }
    report.seeds = [1, 2]
    report.seed_decisions = {1: lc.DECISION_SCALES, 2: lc.DECISION_SCALES}
    report.seed_gains = {1: 0.02, 2: 0.021}
    report.notes = ["not"]

    restored = lc.CurveReport.from_dict(report.to_dict())
    assert restored.decision == report.decision
    assert restored.seeds == [1, 2]
    assert restored.seed_decisions == {1: lc.DECISION_SCALES, 2: lc.DECISION_SCALES}
    assert restored.seed_gains == {1: 0.02, 2: 0.021}
    assert restored.notes == ["not"]
    assert [p.positions for p in restored.points] == [100, 200, 400]
    assert [p.means["policy"] for p in restored.points] == pytest.approx(
        [0.10, 0.08, 0.06]
    )
    # Kume sayisi korunur: bootstrap oyun duzeyinde kalir.
    assert len(set(restored.points[0].game_ids["policy"])) == 10
    assert restored.points[0].resolved_in_sample_unit == lc.IN_SAMPLE_UNITS["combined"]


def test_211_from_json_regenerates_markdown_without_measuring(tmp_path):
    import json

    report = lc.CurveReport()
    for mult, n, mean in [(1, 100, 0.10), (2, 200, 0.08), (4, 400, 0.06)]:
        point = _curve_point(mult, n, mean)
        point.in_sample_loss = 0.5
        report.points.append(point)
    report.slopes = {
        "policy": {"gain": 0.02, "gainCiLow": 0.01, "gainCiHigh": 0.03, "path": "policy"}
    }
    src = tmp_path / "curve.json"
    src.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    md = tmp_path / "curve.md"

    assert lc.main(["--from-json", str(src), "--markdown", str(md), "--quiet"]) == 0
    text = md.read_text(encoding="utf-8")
    assert "In-sample birimi" in text
    assert lc.IN_SAMPLE_UNITS["combined"] in text
    assert "| 4x | 400 |" in text
