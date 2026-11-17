"""Faz 4 v3 Bolum 8, Test 1: PyTorch <-> ORT-Python cikti paritesi.

`parity_cases.json` CIKTI paritesidir (ayni girdi vektoru icin PyTorch ve ORT ciktilari).
Faz 2 `vector_golden.json` ise GIRDI paritesidir (C# Vectorize <-> numpy). Karistirilmamali.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from conftest import MODEL_PATH, PARITY_PATH

BATCHES = (1, 2, 13, 64, 2048)
TOLERANCE = 1e-5
EXPORT_SEED = 20260101


def _ort():
    return pytest.importorskip("onnxruntime")


def _hex_to_float(hex_str: str) -> float:
    """8 haneli uint32 hex -> float32."""
    return float(np.uint32(int(hex_str, 16)).view(np.float32))


def _hex_to_vector(hex_str: str) -> np.ndarray:
    return np.array([_hex_to_float(h) for h in hex_str.split(",")], dtype=np.float32)


def _session():
    ort = _ort()
    return ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])


def test_artifacts_exist():
    assert MODEL_PATH.is_file(), f"model yok: {MODEL_PATH}"
    assert PARITY_PATH.is_file(), f"parite dosyasi yok: {PARITY_PATH}"


def test_metadata_contract():
    sess = _session()
    meta = sess.get_modelmeta().custom_metadata_map
    assert meta["feature_version"] == "1"
    assert meta["vector_size"] == "221"
    assert int(meta["model_version"]) >= 1
    assert meta["arch"] == "221-128-64"
    assert meta["trained_by"]

    inp = sess.get_inputs()[0]
    assert inp.name == "features"
    assert inp.shape == ["batch", 221]
    assert {o.name for o in sess.get_outputs()} == {"value", "policy_logit"}


@pytest.mark.parametrize("batch", BATCHES)
def test_parity_pytorch_vs_ort(batch: int):
    torch = pytest.importorskip("torch")
    import model as model_mod

    net = model_mod.build_model(seed=EXPORT_SEED)
    rng = np.random.default_rng(0x4F4E4E58)
    # export_onnx.py ile ayni sirayi tuketmek icin onceki batchleri de cek
    x = None
    for b in BATCHES:
        x = rng.standard_normal((b, 221)).astype(np.float32)
        if b == batch:
            break

    with torch.no_grad():
        tv, tp = net(torch.from_numpy(x))
    tv = tv.numpy().reshape(-1)
    tp = tp.numpy().reshape(-1)

    ov, op = _session().run(None, {"features": x})
    ov = ov.reshape(-1)
    op = op.reshape(-1)

    dv = float(np.max(np.abs(tv - ov)))
    dp = float(np.max(np.abs(tp - op)))
    assert dv <= TOLERANCE, f"batch={batch} max|dvalue|={dv:.3e}"
    assert dp <= TOLERANCE, f"batch={batch} max|dpolicy|={dp:.3e}"


def test_parity_json_matches_ort():
    payload = json.loads(PARITY_PATH.read_text(encoding="utf-8"))

    assert payload["featureVersion"] == 1
    assert payload["vectorSize"] == 221
    assert payload["tolerance"] == TOLERANCE
    assert payload["maxAbsDeltaValue"] <= TOLERANCE
    assert payload["maxAbsDeltaPolicyLogit"] <= TOLERANCE
    assert len(payload["records"]) == len(BATCHES)

    vectors = np.stack([_hex_to_vector(r["vectorHex"]) for r in payload["records"]])
    assert vectors.shape == (len(BATCHES), 221)

    ov, op = _session().run(None, {"features": vectors})
    ov = ov.reshape(-1)
    op = op.reshape(-1)

    max_dv = max(abs(ov[i] - _hex_to_float(r["expectedValueHex"])) for i, r in enumerate(payload["records"]))
    max_dp = max(abs(op[i] - _hex_to_float(r["expectedPolicyLogitHex"])) for i, r in enumerate(payload["records"]))
    assert max_dv <= TOLERANCE, f"max|dvalue|={max_dv:.3e}"
    assert max_dp <= TOLERANCE, f"max|dpolicy|={max_dp:.3e}"


def test_value_is_unclipped():
    """Deger basi KIRPILMAZ (Bolum 3): grafta Clip dugumu olmamali."""
    onnx = pytest.importorskip("onnx")
    m = onnx.load(str(MODEL_PATH))
    op_types = [n.op_type for n in m.graph.node]
    assert "Clip" not in op_types, f"grafta Clip var: {op_types}"

    rng = np.random.default_rng(7)
    x = (rng.standard_normal((512, 221)) * 4.0).astype(np.float32)
    ov, _ = _session().run(None, {"features": x})
    assert np.all(np.isfinite(ov))