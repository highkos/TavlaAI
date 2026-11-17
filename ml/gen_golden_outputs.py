"""Faz 2 golden vektorlerini ORT-Python'dan gecirip beklenen ciktilari kaydeder.

Cikti: ml/artifacts/golden_outputs.json
C# tarafi (Backgammon.Inference.Tests, Test 9) ayni vektorleri ORT-C#'ta calistirip
bu dosyadaki degerlerle karsilastirir. Boylece C# <-> Python cikti paritesi kurulur.

Kullanim:
    python gen_golden_outputs.py
"""

from __future__ import annotations

import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MODEL = os.path.join(HERE, "artifacts", "model_v1.onnx")
GOLDEN = os.path.join(HERE, "..", "Backgammon.Tests", "ReferenceData", "vector_golden.json")
OUT = os.path.join(HERE, "artifacts", "golden_outputs.json")
TOLERANCE = 1e-5


def _hex_to_vector(hex_str: str) -> np.ndarray:
    return np.array([np.uint32(int(h, 16)).view(np.float32) for h in hex_str.split(",")], dtype=np.float32)


def _f32_hex(value: float) -> str:
    return f"{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def main() -> int:
    import onnxruntime as ort

    with open(GOLDEN, "r", encoding="utf-8") as f:
        golden = json.load(f)

    vectors = np.stack([_hex_to_vector(r["vectorHex"]) for r in golden["records"]])
    assert vectors.shape == (len(golden["records"]), golden["vectorSize"])

    sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    values, logits = sess.run(None, {"features": vectors})
    values = values.reshape(-1)
    logits = logits.reshape(-1)

    assert np.all(np.isfinite(values))
    assert np.all(np.isfinite(logits))

    payload = {
        "modelVersion": int(sess.get_modelmeta().custom_metadata_map["model_version"]),
        "featureVersion": golden["featureVersion"],
        "vectorSize": golden["vectorSize"],
        "tolerance": TOLERANCE,
        "generatedBy": "gen_golden_outputs.py - Faz 4 v3",
        "sourceGolden": "Backgammon.Tests/ReferenceData/vector_golden.json",
        "records": [
            {
                "valueHex": _f32_hex(values[i]),
                "policyLogitHex": _f32_hex(logits[i]),
            }
            for i in range(values.shape[0])
        ],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"wrote {OUT}: {len(payload['records'])} records")
    print(f"value range   : [{values.min():.4f}, {values.max():.4f}]")
    print(f"logit range   : [{logits.min():.4f}, {logits.max():.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())