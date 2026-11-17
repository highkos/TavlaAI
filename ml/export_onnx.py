"""Faz 4 v3 Bolum 3 + Faz 6 Bolum 5.4: PyTorch checkpoint -> ONNX + metadata + parite.

Kullanim:
    python export_onnx.py --out artifacts/model_v1.onnx --model-version 1
    python export_onnx.py --checkpoint artifacts/ckpt_v1.pt --out artifacts/model_v1.onnx
    python export_onnx.py --output-version 2 --profile medium --out artifacts/model_v2.onnx

Cikti:
    <out>                 ONNX modeli (dinamik batch ekseni)
    <out>.parity.json     PyTorch <-> ORT-Python cikti paritesi (parity_cases.json semasi)

Sozlesme (Bolum 3 / Faz 6 Bolum 5.4):
    output_version = 1
        girdi  : "features"     [B, 221] float32
        ciktilar: "value"       [B, 1]   float32 (kirpilmamis)
                  "policy_logit" [B, 1]  float32 (softmax YOK)
    output_version = 2
        girdi  : "features"     [B, 221] float32
        ciktilar: "probs"       [B, 6]   float32 (softmax, **dislayici**)
                  "policy_logit" [B, 1]  float32 (softmax YOK)
        metadata: prob_order = "W,GW,BW,L,GL,BL", prob_encoding = "exclusive"
    opset  : 15 (export/parite basarisiz olursa daha yuksegi gerekceli raporlanir)
    metadata: feature_version, vector_size, model_version, arch, trained_by, output_version
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import (  # noqa: E402
    CAPACITY_PROFILES,
    DEFAULT_PROFILE,
    FEATURE_VERSION,
    PROB_COUNT,
    PROB_ENCODING,
    PROB_ORDER,
    VECTOR_SIZE,
    BackgammonNet,
    BackgammonNetV2,
    build_model,
)

OPSET = 15
INPUT_NAME = "features"
OUTPUT_VALUE = "value"
OUTPUT_PROBS = "probs"
OUTPUT_POLICY = "policy_logit"
PARITY_BATCHES = (1, 2, 13, 64, 2048)
PARITY_TOLERANCE = 1e-5

#: Faz 6 Bolum 5.4: cikti sozlesmesi surumu. 1 = tek skaler "value" + tek "policy_logit".
#: 2 = 6 olasilikli "probs" + tek "policy_logit". ``OnnxModelHandle`` 2'den buyugunu reddeder.
OUTPUT_VERSION = 2

#: Geriye donuk uyumluluk icin hala uretilebilen eski sozlesme.
LEGACY_OUTPUT_VERSION = 1


def _output_names(output_version: int) -> list[str]:
    if output_version == LEGACY_OUTPUT_VERSION:
        return [OUTPUT_VALUE, OUTPUT_POLICY]
    if output_version == 2:
        return [OUTPUT_PROBS, OUTPUT_POLICY]
    raise ValueError(f"desteklenmeyen output_version: {output_version}")


def _f32_hex(value: float) -> str:
    """float32 bit deseni, 8 haneli uint32 hex (Faz 2 v4 §5.11 ile ayni gosterim)."""
    return f"{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def _vector_hex(vec: np.ndarray) -> str:
    """Faz 2 v4 §5.11 ile ayni bicim: virgulle ayrilmis 8 haneli uint32 hex."""
    bits = np.asarray(vec, dtype=np.float32).view(np.uint32)
    return ",".join(f"{int(b):08x}" for b in bits)


def _device_of(model) -> torch.device:
    """Modelin bulundugu cihaz (export/parite cihazdan bagimsiz olmali)."""
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def export(model, out_path: str, model_version: int, trained_by: str,
           output_version: int | None = None) -> None:
    model.eval()
    version = int(output_version if output_version is not None else getattr(model, "output_version", OUTPUT_VERSION))
    names = _output_names(version)
    dummy = torch.zeros(1, model.backbone.in_dim, dtype=torch.float32, device=_device_of(model))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)

    torch.onnx.export(
        model,
        (dummy,),
        out_path,
        input_names=[INPUT_NAME],
        output_names=names,
        dynamic_axes={
            INPUT_NAME: {0: "batch"},
            names[0]: {0: "batch"},
            names[1]: {0: "batch"},
        },
        opset_version=OPSET,
        do_constant_folding=True,
        export_params=True,
    )

    import onnx

    m = onnx.load(out_path)
    meta = {
        "feature_version": str(FEATURE_VERSION),
        "vector_size": str(VECTOR_SIZE),
        "model_version": str(model_version),
        "arch": model.arch,
        "trained_by": trained_by,
        "output_version": str(version),
    }
    if version >= 2:
        meta["prob_order"] = ",".join(PROB_ORDER)
        meta["prob_encoding"] = PROB_ENCODING
    for k, v in meta.items():
        entry = m.metadata_props.add()
        entry.key = k
        entry.value = v
    onnx.save(m, out_path)

    # Dinamik batch ekseni gercekten dinamik mi?
    dims = m.graph.input[0].type.tensor_type.shape.dim
    if len(dims) != 2 or dims[0].dim_param == "":
        raise RuntimeError("Batch ekseni dinamik degil: export sozlesmesi ihlali")

    if version >= 2:
        probs_dims = m.graph.output[0].type.tensor_type.shape.dim
        if len(probs_dims) != 2 or probs_dims[1].dim_value != PROB_COUNT:
            raise RuntimeError(
                f"'probs' cikti sekli [B,{PROB_COUNT}] degil: export sozlesmesi ihlali"
            )


def parity_check(model, onnx_path: str, seed: int = 0x4F4E4E58,
                 output_version: int | None = None) -> dict:
    import onnxruntime as ort

    version = int(output_version if output_version is not None else getattr(model, "output_version", OUTPUT_VERSION))
    names = _output_names(version)

    rng = np.random.default_rng(seed)
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    max_dv = 0.0
    max_dp = 0.0
    records = []

    dev = _device_of(model)
    for batch in PARITY_BATCHES:
        x = rng.standard_normal((batch, VECTOR_SIZE)).astype(np.float32)
        with torch.no_grad():
            tv, tp = model(torch.from_numpy(x).to(dev))
        tv = tv.detach().cpu().numpy().reshape(batch, -1)
        tp = tp.detach().cpu().numpy().reshape(-1)

        ov, op = sess.run(names, {INPUT_NAME: x})
        ov = ov.reshape(batch, -1)
        op = op.reshape(-1)

        dv = float(np.max(np.abs(tv - ov)))
        dp = float(np.max(np.abs(tp - op)))
        max_dv = max(max_dv, dv)
        max_dp = max(max_dp, dp)

        if dv > PARITY_TOLERANCE or dp > PARITY_TOLERANCE:
            raise RuntimeError(
                f"Parite basarisiz (batch={batch}): |dvalue|={dv:.3e} |dpolicy|={dp:.3e} "
                f"tolerans={PARITY_TOLERANCE:.0e}"
            )

        # parity_cases.json icin ilk satiri kaydet
        record = {
            "vectorHex": _vector_hex(x[0]),
            "expectedPolicyLogitHex": _f32_hex(op[0]),
        }
        if version >= 2:
            record["expectedProbsHex"] = [_f32_hex(v) for v in ov[0]]
        else:
            record["expectedValueHex"] = _f32_hex(ov[0][0])
        records.append(record)

    report = {
        "modelVersion": None,  # cagiran doldurur
        "featureVersion": FEATURE_VERSION,
        "vectorSize": VECTOR_SIZE,
        "outputVersion": version,
        "tolerance": PARITY_TOLERANCE,
        "generatedBy": "export_onnx.py - Faz 6",
        "maxAbsDeltaValue": max_dv,
        "maxAbsDeltaPolicyLogit": max_dp,
        "records": records,
    }
    if version >= 2:
        report["probOrder"] = list(PROB_ORDER)
        report["probEncoding"] = PROB_ENCODING
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/model_v1.onnx")
    ap.add_argument("--model-version", type=int, default=1)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--h1", type=int, default=128)
    ap.add_argument("--h2", type=int, default=64)
    ap.add_argument("--output-version", type=int, default=LEGACY_OUTPUT_VERSION,
                    choices=[LEGACY_OUTPUT_VERSION, 2])
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(CAPACITY_PROFILES))
    ap.add_argument("--trained-by", default="faz4-stage-a")
    args = ap.parse_args(argv)

    version = args.output_version
    if args.checkpoint:
        if version >= 2:
            model = BackgammonNetV2(*CAPACITY_PROFILES[args.profile])
        else:
            model = BackgammonNet(h1=args.h1, h2=args.h2)
        state = torch.load(args.checkpoint, map_location="cpu")
        # Egitim laboratuvari (ml/train.py) denetim noktasini {"model", "optimizer", ...}
        # olarak sarar; duz state_dict de kabul edilir.
        if isinstance(state, dict) and "model" in state:
            state = state["model"]
        model.load_state_dict(state)
        model.eval()
    else:
        model = build_model(
            h1=args.h1, h2=args.h2, seed=args.seed,
            output_version=version, profile=args.profile,
        )

    export(model, args.out, args.model_version, args.trained_by, output_version=version)
    report = parity_check(model, args.out, output_version=version)
    report["modelVersion"] = args.model_version

    parity_path = args.out + ".parity.json"
    with open(parity_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"exported  : {args.out}")
    print(f"parity    : {parity_path}")
    print(f"arch      : {model.arch}")
    print(f"out ver   : {version}")
    print(f"max |dval|: {report['maxAbsDeltaValue']:.3e}")
    print(f"max |dpol|: {report['maxAbsDeltaPolicyLogit']:.3e}")
    print(f"tolerance : {PARITY_TOLERANCE:.0e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())