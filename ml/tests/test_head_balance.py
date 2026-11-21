"""K5: kafa dengesi (Test 302-309).

K5'in deger platosu icin saydigi uc adaydan sonuncusu **kayip agirligi
(w*MSE)**. Bu dosya olcum modulunun sozlesmesini dogrular: veri kumesi
dogrulamasi, kayip/gradyan ayrimi, oranlarin tutarliligi, markdown ve
coklu model karsilastirmasi.

Gercek olcum ``ml/artifacts/head_balance.json`` icinde: kayip orani 8.16 ama
gradyan orani yalnizca 1.48 (degerin govde gradyanindaki payi %40.4). Yani
deger kafasi **ac degil**; aday elendi.
"""

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

import head_balance as hb  # noqa: E402


def _write_dataset(path: Path, positions: int = 6, width: int = 4, with_dist: bool = True):
    """Kucuk bir ``policy_dist_3k.npz`` yazar."""
    rng = np.random.default_rng(0)
    offsets = np.arange(positions + 1, dtype=np.int64) * width
    x = rng.normal(size=(positions * width, 221)).astype(np.float32)
    best = rng.integers(0, width, size=positions).astype(np.int32)
    y = rng.normal(size=positions).astype(np.float32)
    payload = {"x": x, "offsets": offsets, "best": best, "y": y}
    if with_dist:
        d = rng.random((positions, 6)).astype(np.float32)
        payload["dist"] = d / d.sum(axis=1, keepdims=True)
    np.savez(path, **payload)
    return path


def _write_ckpt(path: Path):
    torch = pytest.importorskip("torch")
    from model import build_model

    model = build_model(221, 32, 16, seed=0, output_version=2, profile="small")
    torch.save({"model": model.state_dict(), "profile": "small"}, path)
    return path


def test_302_load_dataset_validates(tmp_path):
    good = _write_dataset(tmp_path / "good.npz")
    data = hb.load_dataset(good)
    assert data["positions"] == 6
    assert data["width"] == 4
    assert data["dist"] is not None

    with pytest.raises(hb.HeadBalanceError, match="yok"):
        hb.load_dataset(tmp_path / "missing.npz")

    bad = tmp_path / "bad.npz"
    np.savez(bad, x=np.zeros((4, 221), np.float32), offsets=np.arange(3), best=np.zeros(2))
    with pytest.raises(hb.HeadBalanceError, match="'y' yok"):
        hb.load_dataset(bad)

    skew = tmp_path / "skew.npz"
    np.savez(
        skew,
        x=np.zeros((4, 221), np.float32),
        offsets=np.arange(2),
        best=np.zeros(2),
        y=np.zeros(2),
    )
    with pytest.raises(hb.HeadBalanceError, match="n\\+1"):
        hb.load_dataset(skew)


def test_303_measure_balance_reports_both_heads(tmp_path):
    pytest.importorskip("torch")
    ckpt = _write_ckpt(tmp_path / "ckpt.pt")
    ds = _write_dataset(tmp_path / "ds.npz")
    bal = hb.measure_balance(ckpt, ds)

    assert bal.positions == 6
    assert bal.width == 4
    assert bal.policy_ce > 0
    assert bal.value_mse > 0
    assert bal.grad_policy > 0
    assert bal.grad_value > 0
    # Kalibrasyon terimi deger terimiyle ayni buyukluktur (ayni MSE).
    assert bal.cal_mse == pytest.approx(bal.value_mse)
    assert bal.grad_cal == pytest.approx(bal.grad_value)


def test_304_ratios_are_consistent(tmp_path):
    pytest.importorskip("torch")
    ckpt = _write_ckpt(tmp_path / "ckpt.pt")
    ds = _write_dataset(tmp_path / "ds.npz")
    bal = hb.measure_balance(ckpt, ds)

    assert bal.loss_ratio == pytest.approx(bal.policy_ce / bal.value_mse)
    assert bal.grad_ratio == pytest.approx(bal.grad_policy / bal.grad_value)
    assert 0.0 < bal.value_share < 1.0
    assert bal.value_share == pytest.approx(
        bal.grad_value / (bal.grad_policy + bal.grad_value)
    )


def test_305_to_dict_shape(tmp_path):
    pytest.importorskip("torch")
    ckpt = _write_ckpt(tmp_path / "ckpt.pt")
    ds = _write_dataset(tmp_path / "ds.npz")
    payload = hb.measure_balance(ckpt, ds).to_dict()

    assert set(payload) == {
        "ckpt",
        "dataset",
        "positions",
        "width",
        "losses",
        "gradNorms",
        "lossRatio",
        "gradRatio",
        "valueShare",
        "weights",
    }
    assert set(payload["losses"]) == {"policyCe", "valueMse", "valueCe6", "calMse", "kl"}
    assert set(payload["gradNorms"]) == {"policy", "value", "cal", "kl"}
    assert payload["weights"] == {"cValue": 1.0, "cPolicy": 1.0, "cCal": 0.1}
    json.dumps(payload)  # seri hale gelmeli


def test_306_markdown_sections(tmp_path):
    pytest.importorskip("torch")
    ckpt = _write_ckpt(tmp_path / "ckpt.pt")
    ds = _write_dataset(tmp_path / "ds.npz")
    text = hb.build_markdown(hb.measure_balance(ckpt, ds))

    assert "# Kafa dengesi" in text
    assert "## Kayip buyuklugu" in text
    assert "## Govde gradyan normu" in text
    assert "Gradyan: politika / deger" in text
    assert "Degerin govde gradyanindaki payi" in text
    assert "Karar sayisi kayip orani degil gradyan oranidir" in text


def test_307_dataset_without_dist_yields_nan_diagnostics(tmp_path):
    """``dist`` yoksa 6 sinifli CE ve KL teshis terimleri ``nan`` olmali."""
    pytest.importorskip("torch")
    ckpt = _write_ckpt(tmp_path / "ckpt.pt")
    ds = _write_dataset(tmp_path / "nodist.npz", with_dist=False)
    bal = hb.measure_balance(ckpt, ds)

    assert np.isnan(bal.value_ce6)
    assert np.isnan(bal.kl)
    assert np.isnan(bal.grad_kl)
    # Uretim terimleri hala gecerli.
    assert bal.policy_ce > 0
    assert bal.grad_value > 0
    payload = bal.to_dict()
    assert payload["losses"]["valueCe6"] != payload["losses"]["valueCe6"]  # nan


def _fake_balance(ckpt: str, share: float) -> dict:
    return {
        "ckpt": ckpt,
        "losses": {"policyCe": 1.4, "valueMse": 0.17, "valueCe6": 1.4, "calMse": 0.17, "kl": 0.1},
        "gradNorms": {"policy": 1.0, "value": share / (1.0 - share), "cal": 0.0, "kl": 0.0},
        "gradRatio": (1.0 - share) / share,
        "valueShare": share,
    }


def test_308_compare_balances_builds_rows(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(_fake_balance("m/a.pt", 0.40)), encoding="utf-8")
    b.write_text(json.dumps(_fake_balance("m/b.pt", 0.20)), encoding="utf-8")

    rows = hb.compare_balances([hb.load_balance(a), hb.load_balance(b)])
    assert [r["model"] for r in rows] == ["m/a.pt", "m/b.pt"]
    assert rows[0]["valueShare"] == pytest.approx(0.40)
    assert rows[1]["gradValue"] == pytest.approx(0.25)

    text = hb.build_compare_markdown(rows)
    assert "# Kafa dengesi -- modeller arasi" in text
    assert "Deger payi araligi: **20.0% -- 40.0%**" in text
    assert "`m/a.pt`" in text


def test_309_compare_rejects_missing_or_incomplete(tmp_path):
    with pytest.raises(hb.CompareError, match="yok"):
        hb.load_balance(tmp_path / "nope.json")

    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"ckpt": "x"}), encoding="utf-8")
    with pytest.raises(hb.CompareError, match="'losses' yok"):
        hb.load_balance(partial)

    with pytest.raises(hb.CompareError, match="en az bir"):
        hb.compare_balances([])
    with pytest.raises(hb.CompareError, match="en az bir"):
        hb.build_compare_markdown([])


