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


class _ConstantModel:
    """Girdiden bagimsiz sabit cikti: ER farki yalnizca equity isaretinden gelir."""

    def eval(self) -> None:
        return None

    def __call__(self, x):
        torch = pytest.importorskip("torch")
        n = int(x.shape[0])
        probs = torch.zeros(n, 6)
        probs[:, 0] = 1.0
        # Tum logitler esit -> argmax her zaman 0. secenegi.
        logits = torch.zeros(n)
        return [probs, logits]


def test_245_curve_pool_measure_er_opponent_perspective():
    """Karsi bakis: vektorler cevrilir **ve** equity'ler isaret degistirir (F7-101)."""
    pytest.importorskip("torch")
    pool = _synthetic_pool()
    indices = pool.held_out_indices()
    model = _ConstantModel()

    active = cp.measure_er(model, pool, indices, paths=("value",))
    opponent = cp.measure_er(
        model, pool, indices, paths=("value",), perspective=cp.PERSPECTIVE_OPPONENT
    )
    # Sabit secim (0) icin: active = max(e) - e[0], opponent = -min(e) + e[0].
    expected_active = []
    expected_opponent = []
    for i in indices:
        e = pool.candidate_equities(i)
        expected_active.append(float(np.max(e)) - float(e[0]))
        expected_opponent.append(-float(np.min(e)) + float(e[0]))
    assert active["value"] == pytest.approx(expected_active, abs=1e-5)
    assert opponent["value"] == pytest.approx(expected_opponent, abs=1e-5)
    # Iki bakis ayni sey degildir: havuz afterstate'leri tek bakistan tasir.
    assert active["value"] != pytest.approx(opponent["value"], abs=1e-6)


def test_246_curve_pool_measure_er_both_keys_and_mean():
    pytest.importorskip("torch")
    pool = _synthetic_pool()
    indices = pool.held_out_indices()
    report = cp.measure_er_both(_ConstantModel(), pool, indices)
    assert set(report) == {
        "policy",
        "value",
        "policyOpp",
        "valueOpp",
        "policyMean",
        "valueMean",
    }
    for path in ("policy", "value"):
        assert len(report[path]) == len(indices)
        assert report[path + "Mean"] == pytest.approx(
            [(a + b) / 2.0 for a, b in zip(report[path], report[path + "Opp"])], abs=1e-9
        )


def test_247_curve_pool_perspective_asymmetry():
    assert cp.perspective_asymmetry({"value": [0.02], "valueOpp": [0.02]}) == pytest.approx(1.0)
    assert cp.perspective_asymmetry({"value": [0.02], "valueOpp": [0.08]}) == pytest.approx(4.0)
    assert cp.perspective_asymmetry({"value": [0.08], "valueOpp": [0.02]}) == pytest.approx(4.0)
    assert cp.perspective_asymmetry({"value": [0.0], "valueOpp": [0.0]}) == pytest.approx(1.0)
    assert cp.perspective_asymmetry({"value": [0.0], "valueOpp": [0.05]}) == float("inf")


def test_248_curve_pool_measure_er_rejects_unknown_perspective():
    pytest.importorskip("torch")
    pool = _synthetic_pool()
    with pytest.raises(cp.CurvePoolError):
        cp.measure_er(_ConstantModel(), pool, pool.held_out_indices(), perspective="both")


def test_249_curve_pool_cli_measure_er_contract():
    parser = cp.build_parser()
    args = parser.parse_args(["measure-er", "--model", "m.onnx"])
    assert args.command == "measure-er"
    assert args.model == ["m.onnx"]
    assert args.perspective == cp.PERSPECTIVE_BOTH
    assert args.pool == cp.POOL_PATH
    assert args.out is None
    args = parser.parse_args(
        ["measure-er", "--model", "m.onnx", "--perspective", "opponent", "--limit", "5"]
    )
    assert args.perspective == cp.PERSPECTIVE_OPPONENT
    assert args.limit == 5
    # Birden fazla model karsilastirma tablosu uretir (F7-101).
    args = parser.parse_args(["measure-er", "--model", "a.onnx", "b.onnx", "c.onnx"])
    assert args.model == ["a.onnx", "b.onnx", "c.onnx"]
    with pytest.raises(SystemExit):
        parser.parse_args(["measure-er", "--model", "m.onnx", "--perspective", "yanlis"])


def test_250_curve_pool_build_er_markdown_columns():
    """Karsilastirma tablosu iki bakisi ve ortalamayi ayri sutunlarda verir (F7-101)."""
    rows = [
        {
            "model": "runs/a/model_v30.onnx",
            "positions": 200,
            "perspective": cp.PERSPECTIVE_BOTH,
            "policy": 0.0270,
            "policyOpp": 0.1081,
            "policyMean": 0.0675,
            "value": 0.0287,
            "valueOpp": 0.1019,
            "valueMean": 0.0653,
            "policyAsymmetry": 4.0,
            "valueAsymmetry": 3.6,
        },
        {
            "model": "runs/b/model_v10.onnx",
            "positions": 200,
            "perspective": cp.PERSPECTIVE_BOTH,
            "policy": 0.0479,
            "policyOpp": 0.0731,
            "policyMean": 0.0605,
            "value": 0.0489,
            "valueOpp": 0.0799,
            "valueMean": 0.0644,
            "policyAsymmetry": 1.5,
            "valueAsymmetry": 1.6,
        },
    ]
    md = cp.build_er_markdown(rows, "artifacts/curve_pool_400.npz")
    assert "F7-101" in md
    assert "artifacts/curve_pool_400.npz" in md
    assert "200 held-out" in md
    # Baslik satiri hem bakislari hem ortalamayi adlandirir.
    header = next(line for line in md.splitlines() if line.startswith("| Model"))
    for token in ("ER(+1) pol", "ER(-1) pol", "**Ort** pol", "**Ort** deger"):
        assert token in header
    # Her model icin bir satir; kosu dizini + dosya adi, ortalama kalin yazilir.
    body = [line for line in md.splitlines() if line.startswith("| `")]
    assert len(body) == 2
    assert "a/model_v30.onnx" in body[0] and "**0.0675**" in body[0]
    assert "b/model_v10.onnx" in body[1] and "**0.0605**" in body[1]
    assert "3.60x" in body[0]
    assert "1.60x" in body[1]


def test_251_curve_pool_model_label_disambiguates_runs():
    """Ayni dosya adi farkli kosularda tekrar eder; etiket kosu dizinini tasir."""
    assert (
        cp._model_label("ml/runs/rd_ctl10k/onnx/model_v10.onnx") == "rd_ctl10k/model_v10.onnx"
    )
    assert cp._model_label("model_v10.onnx") == "model_v10.onnx"
    assert cp._model_label("a/b/c.onnx") == "b/c.onnx"
    assert cp._model_label("a/onnx/c.onnx") == "a/c.onnx"
