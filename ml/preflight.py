"""F7-119: EVREN (GPU) on-kontrolu.

EVREN ucretli oldugu icin **kosuya baslamadan once** her sey dogrulanmali.
Bu betik hicbir sey egitmez; yalnizca ortami ve boru hattini sinar ve
PASS/FAIL tablosu basar. Herhangi bir FAIL varsa cikis kodu 1'dir.

Kontroller
----------
1. Python surumu (>= 3.10) ve zorunlu paketler (torch, numpy, onnx,
   onnxruntime).
2. ``--gpu`` verildiyse CUDA ve en az bir GPU; verilmediyse yalnizca bilgi.
3. gnubg calistirilabilir mi (ppg / etiketleme icin zorunlu).
4. Girdi dosyalari: egitim veri kumesi, referans korpus, ppg modeli.
5. Uctan uca kucuk sinama: model kur -> ileri gecis -> ONNX yaz -> ONNX
   Runtime ile parite -> antisimetri olcumu. Bu, "egitim basladi ama 3 saat
   sonra ihracatta patladi" durumunu onler.
6. Disk alani ve yazma izni.

Kullanim::

    python ml/preflight.py --gpu
    python ml/preflight.py --gpu --data ml/artifacts/gnubg_policy_30k.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _p in (str(HERE), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PREFLIGHT_VERSION = 1
MIN_PYTHON = (3, 10)
MIN_FREE_GB = 5.0

DEFAULT_DATA = HERE / "runs" / "capacity30k_rd" / "policy_30k_rd.npz"
DEFAULT_CORPUS = HERE / "artifacts" / "reference_corpus_v2.json"
DEFAULT_MODEL = HERE / "runs" / "capacity30k_rd_sweep" / "xlarge" / "seed0" / "model.onnx"


class Check:
    """Tek bir on-kontrol sonucu."""

    def __init__(self, name: str, ok: bool, detail: str = "", *, fatal: bool = True) -> None:
        self.name = name
        self.ok = bool(ok)
        self.detail = detail
        self.fatal = bool(fatal)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail, "fatal": self.fatal}

    def line(self) -> str:
        mark = "PASS" if self.ok else ("FAIL" if self.fatal else "WARN")
        return "  [%s] %-34s %s" % (mark, self.name, self.detail)


def _check_python() -> Check:
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    return Check(
        "python",
        ok,
        "%d.%d.%d (gerekli >= %d.%d)"
        % (version.major, version.minor, version.micro, *MIN_PYTHON),
    )


def _check_packages() -> list[Check]:
    checks: list[Check] = []
    for name in ("numpy", "torch", "onnx", "onnxruntime"):
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "?")
            checks.append(Check("paket:%s" % name, True, str(version)))
        except Exception as exc:  # noqa: BLE001
            checks.append(Check("paket:%s" % name, False, "eksik: %s" % exc))
    return checks


def _check_torch(require_gpu: bool) -> list[Check]:
    checks: list[Check] = []
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        return [Check("torch", False, "ice aktarilamadi: %s" % exc)]

    cuda_built = bool(getattr(torch.version, "cuda", None))
    checks.append(
        Check(
            "torch:cuda-derlemesi",
            cuda_built or not require_gpu,
            "cuda=%s" % (torch.version.cuda or "yok"),
            fatal=require_gpu,
        )
    )
    available = bool(torch.cuda.is_available())
    count = int(torch.cuda.device_count()) if available else 0
    detail = "kullanilabilir=%s, aygit=%d" % (available, count)
    if available and count:
        detail += ", ad=%s" % torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        detail += ", bellek=%.1f GB" % (props.total_memory / 1024**3)
    checks.append(Check("torch:cuda", available or not require_gpu, detail, fatal=require_gpu))

    # Gercek bir GPU islemi: yalnizca "is_available" demek yetmez.
    if available and count:
        try:
            a = torch.ones(64, 64, device="cuda")
            b = torch.ones(64, 64, device="cuda")
            value = float((a @ b).sum().to("cpu"))
            checks.append(Check("torch:gpu-matmul", abs(value - 64 * 64 * 64) < 1e-3, "ok"))
        except Exception as exc:  # noqa: BLE001
            checks.append(Check("torch:gpu-matmul", False, "hata: %s" % exc))
    return checks


def _check_onnxruntime(require_gpu: bool) -> list[Check]:
    try:
        import onnxruntime as ort
    except Exception as exc:  # noqa: BLE001
        return [Check("onnxruntime", False, "ice aktarilamadi: %s" % exc)]
    providers = list(ort.get_available_providers())
    has_cpu = "CPUExecutionProvider" in providers
    has_gpu = any(p in providers for p in ("CUDAExecutionProvider", "TensorrtExecutionProvider"))
    checks = [
        Check("onnxruntime:cpu", has_cpu, ",".join(providers) or "yok"),
        Check(
            "onnxruntime:gpu",
            has_gpu or not require_gpu,
            "CUDAExecutionProvider=%s" % has_gpu,
            fatal=require_gpu,
        ),
    ]
    return checks


def _check_gnubg() -> Check:
    try:
        import gnubg_er

        exe = gnubg_er.find_gnubg()
        return Check("gnubg", True, str(exe))
    except Exception as exc:  # noqa: BLE001
        return Check("gnubg", False, "bulunamadi: %s" % exc, fatal=False)


def _check_path(name: str, path: Path, *, fatal: bool = True) -> Check:
    path = Path(path)
    if not path.exists():
        return Check(name, False, "yok: %s" % path, fatal=fatal)
    size = path.stat().st_size
    return Check(name, True, "%s (%.1f MB)" % (path.name, size / 1024**2))


def _check_disk(path: Path) -> Check:
    try:
        usage = shutil.disk_usage(str(path))
        free_gb = usage.free / 1024**3
        return Check("disk", free_gb >= MIN_FREE_GB, "bos=%.1f GB" % free_gb)
    except Exception as exc:  # noqa: BLE001
        return Check("disk", False, "olculemedi: %s" % exc, fatal=False)


def _check_write(path: Path) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=str(path), prefix="preflight_")
        os.close(handle)
        os.unlink(name)
        return Check("yazma-izni", True, str(path))
    except Exception as exc:  # noqa: BLE001
        return Check("yazma-izni", False, "hata: %s" % exc)


def _check_pipeline(device: str) -> list[Check]:
    """Uctan uca kucuk sinama: kur -> ileri -> ONNX -> parite -> antisimetri."""
    checks: list[Check] = []
    try:
        import numpy as np
        import torch

        from model import VECTOR_SIZE, build_model, parameter_count
    except Exception as exc:  # noqa: BLE001
        return [Check("boru-hatti:ice-aktarma", False, "hata: %s" % exc)]

    try:
        model = build_model(VECTOR_SIZE, seed=0, output_version=2, profile="small", symmetry=True)
        model.to(device)
        model.eval()
        x = torch.zeros(4, VECTOR_SIZE, dtype=torch.float32, device=device)
        with torch.no_grad():
            probs, logits = model(x)
        ok = tuple(probs.shape) == (4, 6) and tuple(logits.shape) == (4, 1)
        checks.append(
            Check(
                "boru-hatti:ileri",
                ok,
                "probs=%s logits=%s params=%d"
                % (tuple(probs.shape), tuple(logits.shape), parameter_count(model)),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return checks + [Check("boru-hatti:ileri", False, "hata: %s" % exc)]

    try:
        from antisymmetry import flip_perspective

        rng = np.random.default_rng(3)
        raw = rng.standard_normal((8, VECTOR_SIZE)).astype(np.float32)
        flipped = np.asarray([flip_perspective(row.tolist()) for row in raw], dtype=np.float32)
        with torch.no_grad():
            direct = model(torch.from_numpy(raw).to(device))[1].to("cpu").numpy().reshape(-1)
            mirrored = model(torch.from_numpy(flipped).to(device))[1].to("cpu").numpy().reshape(-1)
        delta = float(np.max(np.abs(direct + mirrored)))
        checks.append(Check("boru-hatti:antisimetri", delta < 1e-4, "|f(x)+f(Tx)|=%.2e" % delta))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("boru-hatti:antisimetri", False, "hata: %s" % exc))

    try:
        import onnxruntime as ort

        from capacity_train import export_profile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "preflight.onnx"
            state = {
                "model": model.state_dict(),
                "profile": "small",
                "outputVersion": 2,
                "symmetry": True,
            }
            parity = export_profile(
                state,
                profile="small",
                out_path=out,
                model_version=0,
                symmetry=True,
            )
            sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
            probe = np.zeros((2, VECTOR_SIZE), dtype=np.float32)
            got = sess.run(None, {"features": probe})
            delta = max(
                float(parity.get("maxAbsDeltaValue", 1.0)),
                float(parity.get("maxAbsDeltaPolicyLogit", 1.0)),
            )
            checks.append(
                Check(
                    "boru-hatti:onnx",
                    delta < 1e-5 and len(got) == 2,
                    "delta=%.2e, cikti=%d" % (delta, len(got)),
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("boru-hatti:onnx", False, "hata: %s" % exc))
    return checks


def run_preflight(
    *,
    require_gpu: bool = False,
    data: Path | None = None,
    corpus: Path | None = None,
    model: Path | None = None,
    out_dir: Path | None = None,
    skip_pipeline: bool = False,
) -> dict[str, Any]:
    """Tum kontrolleri kosar; rapor sozlugu dondurur."""
    started = time.time()
    device = "cuda" if require_gpu else "cpu"
    checks: list[Check] = [_check_python()]
    checks.extend(_check_packages())
    checks.extend(_check_torch(require_gpu))
    checks.extend(_check_onnxruntime(require_gpu))
    checks.append(_check_gnubg())
    if data is not None:
        checks.append(_check_path("veri:egitim", Path(data)))
    if corpus is not None:
        checks.append(_check_path("veri:korpus", Path(corpus)))
    if model is not None:
        checks.append(_check_path("model:ppg", Path(model), fatal=False))
    target = Path(out_dir) if out_dir else HERE / "runs"
    checks.append(_check_disk(target))
    checks.append(_check_write(target))
    if not skip_pipeline:
        checks.extend(_check_pipeline(device))

    failed = [c for c in checks if not c.ok and c.fatal]
    warned = [c for c in checks if not c.ok and not c.fatal]
    return {
        "preflightVersion": PREFLIGHT_VERSION,
        "requireGpu": bool(require_gpu),
        "device": device,
        "ok": not failed,
        "failed": [c.name for c in failed],
        "warned": [c.name for c in warned],
        "checks": [c.as_dict() for c in checks],
        "elapsedSeconds": round(time.time() - started, 2),
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# EVREN on-kontrolu (F7-119)",
        "",
        "- surum: %d" % report["preflightVersion"],
        "- GPU zorunlu: %s" % ("evet" if report["requireGpu"] else "hayir"),
        "- cihaz: `%s`" % report["device"],
        "- sonuc: **%s**" % ("HAZIR" if report["ok"] else "HAZIR DEGIL"),
        "- sure: %.2f s" % report["elapsedSeconds"],
        "",
        "| kontrol | durum | ayrinti |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        mark = "PASS" if check["ok"] else ("FAIL" if check["fatal"] else "WARN")
        lines.append("| `%s` | %s | %s |" % (check["name"], mark, check["detail"]))
    if report["failed"]:
        lines.extend(["", "## Engeller", ""])
        lines.extend("- `%s`" % name for name in report["failed"])
    if report["warned"]:
        lines.extend(["", "## Uyarilar", ""])
        lines.extend("- `%s`" % name for name in report["warned"])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="preflight", description="EVREN on-kontrolu (F7-119)")
    ap.add_argument("--gpu", action="store_true", help="CUDA zorunlu olsun")
    ap.add_argument("--data", type=Path, default=None, help="egitim veri kumesi")
    ap.add_argument("--corpus", type=Path, default=None, help="referans korpus")
    ap.add_argument("--model", type=Path, default=None, help="ppg/ONNX modeli")
    ap.add_argument("--out-dir", type=Path, default=None, help="yazma izni ve disk kontrolu")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--markdown", type=Path, default=None)
    ap.add_argument("--skip-pipeline", action="store_true", help="boru hatti sinamasini atla")
    ap.add_argument("--quiet", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_preflight(
        require_gpu=args.gpu,
        data=args.data,
        corpus=args.corpus,
        model=args.model,
        out_dir=args.out_dir,
        skip_pipeline=args.skip_pipeline,
    )
    if not args.quiet:
        print("EVREN on-kontrolu (F7-119)")
        for check in report["checks"]:
            print(Check(check["name"], check["ok"], check["detail"], fatal=check["fatal"]).line())
        print(
            "\nsonuc: %s (%.2f s)"
            % ("HAZIR" if report["ok"] else "HAZIR DEGIL", report["elapsedSeconds"])
        )
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(build_markdown(report), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
