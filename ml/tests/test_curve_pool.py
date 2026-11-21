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


def _phase_pool(phases: list[str]) -> cp.CurvePool:
    """Fazi vektor bayraklariyla kodlanmis kucuk havuz (K3 testleri)."""
    rows: list[np.ndarray] = []
    offsets = [0]
    best: list[int] = []
    y: list[float] = []
    cand_equity: list[float] = []
    game_ids: list[str] = []
    split: list[str] = []
    for k, phase in enumerate(phases):
        block = np.zeros((2, gnubg_er.VECTOR_SIZE), dtype=np.float32)
        for row in block:
            if phase == "bar":
                row[gnubg_er.ACTIVE_BAR] = 1.0
                row[gnubg_er.IS_CONTACT] = 1.0
            elif phase == "race":
                row[gnubg_er.IS_CONTACT] = 0.0
            else:
                row[gnubg_er.IS_CONTACT] = 1.0
        rows.append(block)
        offsets.append(offsets[-1] + 2)
        best.append(0)
        y.append(0.0)
        cand_equity.extend([0.0, -1.0])
        game_ids.append("g%d" % k)
        split.append(cp.SPLIT_HELD_OUT)
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


def test_254_phase_of_vector_reads_bar_race_contact():
    """Faz vektorden okunur: bar > yaris > temas (K3)."""
    bar = np.zeros(gnubg_er.VECTOR_SIZE, dtype=np.float32)
    bar[gnubg_er.OPP_BAR] = 2.0
    bar[gnubg_er.IS_CONTACT] = 1.0
    assert cp.phase_of_vector(bar) == "bar"

    race = np.zeros(gnubg_er.VECTOR_SIZE, dtype=np.float32)
    race[gnubg_er.IS_CONTACT] = 0.0
    assert cp.phase_of_vector(race) == "race"

    contact = np.zeros(gnubg_er.VECTOR_SIZE, dtype=np.float32)
    contact[gnubg_er.IS_CONTACT] = 1.0
    assert cp.phase_of_vector(contact) == "contact"


def test_255_phase_shares_sum_to_one():
    """Faz paylari 1'e toplar; bilinmeyen faz yok."""
    pool = _phase_pool(["contact", "contact", "race", "bar"])
    shares = cp.phase_shares(pool, pool.held_out_indices())
    assert set(shares) == set(cp.HEADLINE_PHASES)
    assert shares["contact"] == pytest.approx(0.5)
    assert shares["race"] == pytest.approx(0.25)
    assert shares["bar"] == pytest.approx(0.25)
    assert sum(shares.values()) == pytest.approx(1.0)


def test_256_game_frequency_weights_upweight_underrepresented_phase():
    """Korpus temas agirlikli; gercek oyun yaris agirlikliysa yaris agirlanir."""
    pool = _phase_pool(["contact", "contact", "contact", "race"])
    indices = pool.held_out_indices()
    target = {"contact": 0.5, "race": 0.5, "bar": 0.0}
    w = cp.game_frequency_weights(pool, indices, target)
    assert w.shape == (4,)
    # Ortalama 1'e normalize: agirlikli ER ayni olcekte kalir.
    assert float(np.mean(w)) == pytest.approx(1.0)
    # Yaris (havuzda 1/4, hedefte 1/2) temasdan (3/4 -> 1/2) daha agir.
    assert w[3] > w[0]
    assert w[0] == pytest.approx(w[1])
    assert w[1] == pytest.approx(w[2])


def test_257_game_frequency_weights_skip_absent_phase():
    """Havuzda olmayan faz hedefte varsa atlanir, paylar yeniden normalize edilir."""
    pool = _phase_pool(["contact", "race"])
    indices = pool.held_out_indices()
    w = cp.game_frequency_weights(pool, indices, {"contact": 0.2, "race": 0.2, "bar": 0.6})
    assert float(np.mean(w)) == pytest.approx(1.0)
    # Bar hic yok; kalan iki faz esit paya normalize edilir -> esit agirlik.
    assert w[0] == pytest.approx(w[1])


def test_258_game_frequency_weights_degenerate_target_is_uniform():
    """Hedef tamamen sifirsa agirlik uygulanamaz; duz agirlik doner."""
    pool = _phase_pool(["contact", "race"])
    w = cp.game_frequency_weights(pool, pool.held_out_indices(), {})
    assert np.allclose(w, 1.0)


def test_259_weighted_mean_matches_manual_and_rejects_length_mismatch():
    """Agirlikli ortalama elle hesapla ayni; uzunluk uyusmazligi hata verir."""
    values = [1.0, 3.0]
    weights = np.asarray([0.25, 0.75], dtype=np.float64)
    assert cp.weighted_mean(values, weights) == pytest.approx(2.5)
    assert cp.weighted_mean(values, None) == pytest.approx(2.0)
    assert cp.weighted_mean([], None) == 0.0
    with pytest.raises(cp.CurvePoolError):
        cp.weighted_mean(values, np.asarray([1.0], dtype=np.float64))


def test_260_measure_summary_reports_weighted_fields():
    """``measure_summary`` agirlik verilince ``*Weighted`` alanlarini yazar (K3)."""
    pool = _phase_pool(["contact", "contact", "race", "bar"])
    indices = pool.held_out_indices()
    weights = cp.game_frequency_weights(
        pool, indices, {"contact": 0.2, "race": 0.4, "bar": 0.4}
    )

    class _Model:
        def eval(self) -> None:
            return None

        def __call__(self, x):
            import torch

            n = int(x.shape[0])
            probs = torch.full((n, 6), 1.0 / 6.0)
            # Her pozisyonun 2 adayi var; tek indisli adayi (kotu equity) sec.
            logits = torch.tensor([0.0, 1.0] * (n // 2), dtype=torch.float32)
            return [probs, logits]

    original = cp._load_onnx_model
    cp._load_onnx_model = lambda _p: _Model()
    try:
        summary = cp.measure_summary(
            Path("m.onnx"), pool, indices, perspective=cp.PERSPECTIVE_ACTIVE, weights=weights
        )
    finally:
        cp._load_onnx_model = original
    assert summary["weighted"] is True
    assert "policyWeighted" in summary and "valueWeighted" in summary
    assert summary["phaseShares"]["contact"] == pytest.approx(0.5)
    # Model her zaman kotu adayi secer -> kayip 1.0; agirlikli ortalama da 1.0.
    assert summary["policy"] == pytest.approx(1.0)
    assert summary["policyWeighted"] == pytest.approx(1.0)


def test_261_measure_er_cli_accepts_weight_flags():
    """CLI K3 bayraklarini kabul eder ve varsayilanlari dogru kurar."""
    parser = cp.build_parser()
    args = parser.parse_args(
        ["measure-er", "--model", "m.onnx", "--weight-by-game-frequency"]
    )
    assert args.weight_by_game_frequency is True
    assert args.shard_dir == "ml/runs/stage_d_l2/shards"
    assert args.shard_limit == 1
    plain = parser.parse_args(["measure-er", "--model", "m.onnx"])
    assert plain.weight_by_game_frequency is False


def test_262_build_er_markdown_adds_weighted_section():
    """Agirlikli satirlar markdown'a K3 bolumu ekler; agirliksizda eklemez."""
    rows = [
        {
            "model": "runs/a/model_v1.onnx",
            "positions": 100,
            "policy": 0.02,
            "policyOpp": 0.08,
            "policyMean": 0.05,
            "value": 0.02,
            "valueOpp": 0.08,
            "valueMean": 0.05,
            "policyAsymmetry": 4.0,
            "valueAsymmetry": 4.0,
            "weighted": True,
            "policyMeanWeighted": 0.04,
            "valueMeanWeighted": 0.045,
            "phaseShares": {"contact": 0.7, "race": 0.1, "bar": 0.2},
        }
    ]
    md = cp.build_er_markdown(rows, "p.npz", {"contact": 0.5, "race": 0.15, "bar": 0.35})
    assert "Oyun sikligina agirlikli ER (K3)" in md
    assert "| bar | 0.2000 | 0.3500 | 1.75x |" in md
    assert "| contact | 0.7000 | 0.5000 | 0.71x |" in md
    assert "**0.0400**" in md
    assert "-20.0%" in md

    plain = cp.build_er_markdown([dict(rows[0], weighted=False)], "p.npz")
    assert "Oyun sikligina agirlikli ER (K3)" not in plain


def _gate_pool() -> cp.CurvePool:
    """Kapi testleri icin iki adayli, bakis altinda farklilasan havuz.

    Aday 0 nokta blogu 1'de, aday 1 nokta blogu 24'te tas tasir. ``flip_perspective``
    blogu ``j -> 25 - j`` ile ters cevirdigi icin bu iki aday bakis altinda yer
    degistirir; boylece ``h(x) = sum(x)`` tek sayi (odd) bir sinyal uretir.
    """
    rows: list[np.ndarray] = []
    offsets = [0]
    best: list[int] = []
    y: list[float] = []
    cand_equity: list[float] = []
    game_ids: list[str] = []
    split: list[str] = []
    for k in range(4):
        block = np.zeros((2, gnubg_er.VECTOR_SIZE), dtype=np.float32)
        block[0, gnubg_er.ACTIVE_OFFSET] = float(k + 1)
        block[1, gnubg_er.OPP_OFFSET + 92] = float(k + 1)
        block[:, gnubg_er.IS_CONTACT] = 1.0
        rows.append(block)
        offsets.append(offsets[-1] + 2)
        best.append(0)
        y.append(0.0)
        cand_equity.extend([0.0, -1.0])
        game_ids.append("g%d" % k)
        split.append(cp.SPLIT_HELD_OUT)
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


def _signed_sum(arr: np.ndarray) -> np.ndarray:
    """``sum(ACTIVE) - sum(OPP)``; bakis takasi altinda **isaret doner**."""
    a = gnubg_er.ACTIVE_OFFSET
    o = gnubg_er.OPP_OFFSET
    width = 96
    return arr[:, a : a + width].sum(axis=1) - arr[:, o : o + width].sum(axis=1)


def _odd_model():
    """Bakis altinda tam antisimetrik model: ``d = h(x) - h(flip(x))``."""
    import torch
    from antisymmetry import flip_perspective

    class _Model:
        def eval(self) -> None:
            return None

        def __call__(self, x):
            arr = x.detach().cpu().numpy()
            n = arr.shape[0]
            flipped = np.stack(
                [
                    np.asarray(flip_perspective(arr[i]), dtype=np.float32)
                    for i in range(n)
                ]
            )
            d = _signed_sum(arr) - _signed_sum(flipped)
            e = np.tanh(d)
            probs = np.zeros((n, 6), dtype=np.float32)
            probs[:, 0] = (e + 1.0) / 2.0
            probs[:, 3] = 1.0 - probs[:, 0]
            return [torch.from_numpy(probs), torch.from_numpy(d.astype(np.float32))]

    return _Model()


def _even_model():
    """Bozuk model: cikti tek sayi degil, ``e = tanh(sum(x))`` (taka invaryanti)."""
    import torch

    class _Model:
        def eval(self) -> None:
            return None

        def __call__(self, x):
            arr = x.detach().cpu().numpy()
            n = arr.shape[0]
            h = arr.sum(axis=1)
            e = np.tanh(h)
            probs = np.zeros((n, 6), dtype=np.float32)
            probs[:, 0] = (e + 1.0) / 2.0
            probs[:, 3] = 1.0 - probs[:, 0]
            return [torch.from_numpy(probs), torch.from_numpy(h.astype(np.float32))]

    return _Model()


def test_271_measure_gate_antisymmetric_model_passes_every_axis():
    """Tam antisimetrik model: corr = -1, meanAbsSum = 0, argmax = 1, fark = 0 (K1)."""
    pool = _gate_pool()
    stats = cp.measure_gate(_odd_model(), pool, pool.held_out_indices(), resamples=200)
    assert stats["positions"] == 4.0
    assert stats["afterStates"] == 8.0
    assert stats["correlation"] == pytest.approx(-1.0, abs=1e-6)
    assert stats["meanAbsSum"] == pytest.approx(0.0, abs=1e-6)
    assert stats["argmaxAgreement"] == pytest.approx(1.0)
    assert stats["erDiff"] == pytest.approx(0.0, abs=1e-9)
    assert stats["erPlus"] == pytest.approx(0.0, abs=1e-9)
    assert stats["erMinus"] == pytest.approx(0.0, abs=1e-9)


def test_272_measure_gate_detects_broken_model():
    """Tek sayi olmayan cikti kapiyi duserir: meanAbsSum > 0, corr > -0.99 (K1)."""
    pool = _gate_pool()
    stats = cp.measure_gate(_even_model(), pool, pool.held_out_indices(), resamples=200)
    assert stats["meanAbsSum"] > 0.1
    assert stats["correlation"] > -0.99


def test_273_measure_gate_rejects_empty_indices():
    """Bos pozisyon kumesi sessizce 0 dondurmez, hata verir."""
    pool = _gate_pool()
    with pytest.raises(cp.CurvePoolError):
        cp.measure_gate(_odd_model(), pool, [])


def test_274_build_gate_markdown_renders_table():
    """Kapi markdown'i tablo satirini ve teshis notunu yazar."""
    rows = [
        {
            "model": "runs/a/model_v1.onnx",
            "positions": 2667.0,
            "afterStates": 50727.0,
            "correlation": -0.9100,
            "meanAbsSum": 0.4340,
            "argmaxAgreement": 0.3618,
            "erPlus": 0.0287,
            "erMinus": 0.0815,
            "erDiff": -0.0527,
            "erDiffCiLow": -0.0582,
            "erDiffCiHigh": -0.0474,
        }
    ]
    md = cp.build_gate_markdown(rows, "p.npz")
    assert "Antisimetri kapisi" in md
    assert "`runs/a/model_v1.onnx`" in md
    assert "| 2667 | 50727 | -0.9100 | 0.4340 | 0.362 |" in md
    assert "-0.0527" in md
    assert "teshis" in md


def test_275_gate_cli_parses_models_and_defaults():
    """``gate`` alt komutu modelleri ve varsayilanlari kabul eder."""
    parser = cp.build_parser()
    args = parser.parse_args(["gate", "--model", "a.onnx", "b.onnx"])
    assert args.command == "gate"
    assert args.model == ["a.onnx", "b.onnx"]
    assert args.pool == cp.POOL_PATH
    assert args.limit == 0
    assert args.resamples == 2000