"""Faz 4 v3 Asama A + Faz 6 Asama B: C# testleri icin yardimci ONNX modelleri uretir.

Uretilenler (ml/artifacts/):
    model_v2.onnx                    ayni agirliklar, model_version = 2 (SetModel monotonluk testi)
    model_bad_feature_version.onnx   feature_version = 2 (yukleme reddi)
    model_bad_vector_size.onnx       vector_size = 200 (yukleme reddi)
    model_output_version_1.onnx      output_version = 1 (acik v1 sozlesmesi)
    model_bad_output_version.onnx    output_version = 3 (desteklenmeyen gelecek surum)
    model_output_version_2.onnx      gercek 6 cikti li v2 grafigi (export_onnx.py ile)

Kullanim:
    python gen_test_models.py
"""

from __future__ import annotations

import os
import sys

import onnx

HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(HERE, "artifacts")
BASE = os.path.join(ARTIFACTS, "model_v1.onnx")

#: Faz 6 Bolum 5.4: v2 modelleri bu metadata'yi bildirmek zorundadir.
PROB_METADATA = {"prob_order": "W,GW,BW,L,GL,BL", "prob_encoding": "exclusive"}


def _clone(out_name: str, overrides: dict[str, str]) -> str:
    m = onnx.load(BASE)
    existing = {entry.key for entry in m.metadata_props}
    for entry in m.metadata_props:
        if entry.key in overrides:
            entry.value = overrides[entry.key]
    for key, value in overrides.items():
        if key not in existing:
            entry = m.metadata_props.add()
            entry.key = key
            entry.value = value
    out = os.path.join(ARTIFACTS, out_name)
    onnx.save(m, out)
    return out


def _export_v2() -> str:
    """Gercek 6 cikti li v2 grafigi (metadata klonlamak yetmez: sekil [B,6] olmali)."""
    sys.path.insert(0, HERE)
    import export_onnx

    out = os.path.join(ARTIFACTS, "model_output_version_2.onnx")
    model = export_onnx.build_model(output_version=2, profile="medium", seed=20261114)
    export_onnx.export(model, out, model_version=1, trained_by="faz6-stage-b", output_version=2)
    return out


def main() -> int:
    if not os.path.isfile(BASE):
        print(f"temel model yok: {BASE}", file=sys.stderr)
        return 1

    print("wrote", _clone("model_v2.onnx", {"model_version": "2"}))
    print("wrote", _clone("model_bad_feature_version.onnx", {"feature_version": "2"}))
    print("wrote", _clone("model_bad_vector_size.onnx", {"vector_size": "200"}))
    print("wrote", _clone("model_output_version_1.onnx", {"output_version": "1"}))
    print("wrote", _clone("model_bad_output_version.onnx", {"output_version": "3", **PROB_METADATA}))
    print("wrote", _export_v2())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())