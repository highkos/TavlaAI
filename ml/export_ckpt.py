"""Egitilmis bir checkpoint'i ONNX'e aktarir (F7-10).

`ml/train_v2.py` ONNX'i her iterasyonun BASINDA disari aktarir; bu, self-play
icin dogrudur ama kosunun SONUNDAKI model hicbir zaman ONNX'e yazilmaz.
Bu betik o boslugu kapatir: checkpoint -> ONNX.

Kullanim:
    python ml/export_ckpt.py --ckpt ml/runs/stage_b_medium/ckpt_v1.pt \
        --out ml/runs/stage_b_medium/onnx/model_v1_trained.onnx --version 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from export_onnx import export  # noqa: E402
from model import CAPACITY_PROFILES, build_model  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Checkpoint -> ONNX")
    p.add_argument("--ckpt", required=True, help="ckpt_vN.pt yolu")
    p.add_argument("--out", required=True, help="cikti .onnx yolu")
    p.add_argument("--version", type=int, default=1, help="ONNX model surumu")
    p.add_argument("--profile", default=None, help="profil (varsayilan: checkpoint'ten)")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ckpt_path = Path(args.ckpt)
    if not ckpt_path.is_file():
        print("[hata] checkpoint yok: " + str(ckpt_path), file=sys.stderr)
        return 2

    state = torch.load(ckpt_path, map_location=args.device, weights_only=False)
    profile = args.profile or state.get("profile") or "medium"
    if profile not in CAPACITY_PROFILES:
        print("[hata] bilinmeyen profil: " + str(profile), file=sys.stderr)
        return 2

    h1, h2 = CAPACITY_PROFILES[profile][:2]
    model = build_model(
        221, h1, h2, seed=0, output_version=2, profile=profile
    ).to(args.device)
    model.load_state_dict(state["model"])
    model.eval()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export(model, str(out_path), args.version, trained_by="ml/export_ckpt.py")
    print("profil=" + profile + " | " + str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
