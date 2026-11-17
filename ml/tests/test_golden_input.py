"""Faz 4 v3 Bolum 8, Test 5: Faz 2 golden girdi vektorleri -> ORT-Python ciktilari.

`golden_outputs.json` Python ORT tarafindan uretilir; C# testi (Test 9) ayni vektorleri
ORT-C#'ta calistirip bu degerlerle karsilastirir. Boylece girdi (Faz 2) ve cikti (Faz 4)
paritesi birbirine baglanir.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from conftest import ARTIFACTS, GOLDEN_VECTOR_PATH, MODEL_PATH

GOLDEN_OUTPUTS = ARTIFACTS / "golden_outputs.json"
TOLERANCE = 1e-5


def _hex_to_float(hex_str: str) -> float:
    return float(np.uint32(int(hex_str, 16)).view(np.float32))


def _load_golden() -> dict:
    assert GOLDEN_VECTOR_PATH.is_file(), f"golden vektor dosyasi yok: {GOLDEN_VECTOR_PATH}"
    return json.loads(GOLDEN_VECTOR_PATH.read_text(encoding="utf-8"))


def _golden_matrix(golden: dict) -> np.ndarray:
    return np.stack(
        [np.array([_hex_to_float(h) for h in r["vectorHex"].split(",")], dtype=np.float32) for r in golden["records"]]
    )


def test_golden_input_shape():
    golden = _load_golden()
    assert golden["featureVersion"] == 1
    assert golden["vectorSize"] == 221
    assert len(golden["records"]) == 500
    x = _golden_matrix(golden)
    assert x.shape == (500, 221)
    assert np.all(np.isfinite(x))


def test_golden_outputs_file_matches_ort():
    assert GOLDEN_OUTPUTS.is_file(), f"golden_outputs.json yok: {GOLDEN_OUTPUTS}"
    payload = json.loads(GOLDEN_OUTPUTS.read_text(encoding="utf-8"))
    golden = _load_golden()

    assert payload["featureVersion"] == golden["featureVersion"]
    assert payload["vectorSize"] == golden["vectorSize"]
    assert payload["tolerance"] == TOLERANCE
    assert len(payload["records"]) == len(golden["records"])

    ort = pytest.importorskip("onnxruntime")
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    values, logits = sess.run(None, {"features": _golden_matrix(golden)})
    values = values.reshape(-1)
    logits = logits.reshape(-1)

    max_dv = max(abs(values[i] - _hex_to_float(r["valueHex"])) for i, r in enumerate(payload["records"]))
    max_dp = max(abs(logits[i] - _hex_to_float(r["policyLogitHex"])) for i, r in enumerate(payload["records"]))
    assert max_dv <= TOLERANCE, f"max|dvalue|={max_dv:.3e}"
    assert max_dp <= TOLERANCE, f"max|dpolicy|={max_dp:.3e}"


def test_golden_outputs_are_finite_and_deterministic():
    ort = pytest.importorskip("onnxruntime")
    golden = _load_golden()
    x = _golden_matrix(golden)
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])

    v1, p1 = sess.run(None, {"features": x})
    v2, p2 = sess.run(None, {"features": x})
    assert np.array_equal(v1, v2), "ayni girdi ayni ciktiyi vermeli"
    assert np.array_equal(p1, p2)
    assert np.all(np.isfinite(v1))
    assert np.all(np.isfinite(p1))


def test_golden_batch_composition_invariance():
    """Batch bilesimi ciktiyi degistirmemeli (dinamik batch ekseni)."""
    ort = pytest.importorskip("onnxruntime")
    golden = _load_golden()
    x = _golden_matrix(golden)
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])

    v_all, p_all = sess.run(None, {"features": x})
    v_all = v_all.reshape(-1)
    p_all = p_all.reshape(-1)

    max_dv = 0.0
    max_dp = 0.0
    for start in (0, 1, 7, 100, 499):
        chunk = x[start:start + 1]
        v, p = sess.run(None, {"features": chunk})
        max_dv = max(max_dv, abs(float(v.reshape(-1)[0]) - float(v_all[start])))
        max_dp = max(max_dp, abs(float(p.reshape(-1)[0]) - float(p_all[start])))

    assert max_dv <= TOLERANCE, f"max|dvalue|={max_dv:.3e}"
    assert max_dp <= TOLERANCE, f"max|dpolicy|={max_dp:.3e}"