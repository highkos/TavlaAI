"""F7-10 regresyon testleri: checkpoint -> ONNX aktarimi.

`ml/train_v2.py` ONNX'i iterasyonun BASINDA yazar; kosunun sonundaki model
hicbir zaman ONNX'e cikmaz. `ml/export_ckpt.py` bu boslugu kapatir. Bu testler
aktarimin (a) dogru agirliklari kullandigini, (b) PyTorch ile parite ettigini,
(c) hata yollarini dogru raporladigini dogrular.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import export_ckpt  # noqa: E402
from model import build_model  # noqa: E402

PROFILE = "small"
TOLERANCE = 1e-5


def _ort():
    return pytest.importorskip("onnxruntime")


def _make_model(seed: int):
    model = build_model(221, 128, 64, seed=seed, output_version=2, profile=PROFILE)
    model.eval()
    return model


def _save_ckpt(path: Path, model, profile: str = PROFILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "profile": profile}, path)
    return path


def _features(batch: int = 4, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random((batch, 221), dtype=np.float32)


def _torch_outputs(model, x: np.ndarray):
    with torch.no_grad():
        probs, policy = model(torch.from_numpy(x))
    return probs.numpy(), policy.numpy()


def _ort_outputs(onnx_path: Path, x: np.ndarray):
    ort = _ort()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    names = [o.name for o in sess.get_outputs()]
    outs = sess.run(names, {"features": x})
    return dict(zip(names, outs))


# ----------------------------------------------------------------------
# Mutlu yol
# ----------------------------------------------------------------------


def test_export_ckpt_writes_file(tmp_path):
    model = _make_model(1)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model)
    out = tmp_path / "onnx" / "model_v1.onnx"
    rc = export_ckpt.main(
        ["--ckpt", str(ckpt), "--out", str(out), "--version", "1"]
    )
    assert rc == 0
    assert out.is_file()
    assert out.stat().st_size > 0


def test_export_ckpt_creates_parent_directory(tmp_path):
    model = _make_model(2)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model)
    out = tmp_path / "a" / "b" / "c" / "model_v1.onnx"
    assert not out.parent.is_dir()
    assert export_ckpt.main(["--ckpt", str(ckpt), "--out", str(out)]) == 0
    assert out.is_file()


def test_export_ckpt_matches_torch_outputs(tmp_path):
    model = _make_model(3)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model)
    out = tmp_path / "model_v1.onnx"
    assert export_ckpt.main(["--ckpt", str(ckpt), "--out", str(out)]) == 0

    x = _features()
    probs_t, policy_t = _torch_outputs(model, x)
    got = _ort_outputs(out, x)
    assert set(got) == {"probs", "policy_logit"}
    assert np.allclose(got["probs"], probs_t, atol=TOLERANCE)
    assert np.allclose(got["policy_logit"], policy_t, atol=TOLERANCE)


def test_export_ckpt_uses_checkpoint_weights_not_random_init(tmp_path):
    """F7-10'un ozu: aktarim rastgele baslangic agirliklarini YAZMAMALI."""
    model_a = _make_model(4)
    model_b = _make_model(5)
    ckpt_a = _save_ckpt(tmp_path / "a.pt", model_a)
    ckpt_b = _save_ckpt(tmp_path / "b.pt", model_b)
    out_a = tmp_path / "a.onnx"
    out_b = tmp_path / "b.onnx"
    assert export_ckpt.main(["--ckpt", str(ckpt_a), "--out", str(out_a)]) == 0
    assert export_ckpt.main(["--ckpt", str(ckpt_b), "--out", str(out_b)]) == 0

    x = _features()
    probs_a = _ort_outputs(out_a, x)["probs"]
    probs_b = _ort_outputs(out_b, x)["probs"]
    assert not np.allclose(probs_a, probs_b, atol=1e-6)


def test_export_ckpt_roundtrips_a_trained_checkpoint(tmp_path):
    """Checkpoint'teki agirliklar degistiginde ONNX ciktisi da degismeli."""
    model = _make_model(6)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model)
    out = tmp_path / "model_v1.onnx"
    assert export_ckpt.main(["--ckpt", str(ckpt), "--out", str(out)]) == 0
    x = _features()
    before = _ort_outputs(out, x)["probs"]

    with torch.no_grad():
        for param in model.parameters():
            param.add_(0.01)
    _save_ckpt(ckpt, model)
    out2 = tmp_path / "model_v1b.onnx"
    assert export_ckpt.main(["--ckpt", str(ckpt), "--out", str(out2)]) == 0
    after = _ort_outputs(out2, x)["probs"]
    assert not np.allclose(before, after, atol=1e-6)


def test_export_ckpt_profile_override(tmp_path):
    model = _make_model(7)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model, profile="bozuk")
    out = tmp_path / "model_v1.onnx"
    rc = export_ckpt.main(
        ["--ckpt", str(ckpt), "--out", str(out), "--profile", PROFILE]
    )
    assert rc == 0
    assert out.is_file()


# ----------------------------------------------------------------------
# Hata yollari
# ----------------------------------------------------------------------


def test_export_ckpt_missing_checkpoint_returns_2(tmp_path):
    rc = export_ckpt.main(
        ["--ckpt", str(tmp_path / "nope.pt"), "--out", str(tmp_path / "m.onnx")]
    )
    assert rc == 2


def test_export_ckpt_unknown_profile_returns_2(tmp_path):
    model = _make_model(8)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model, profile="devasa")
    rc = export_ckpt.main(
        ["--ckpt", str(ckpt), "--out", str(tmp_path / "m.onnx")]
    )
    assert rc == 2


def test_export_ckpt_unknown_profile_override_returns_2(tmp_path):
    model = _make_model(9)
    ckpt = _save_ckpt(tmp_path / "ckpt_v1.pt", model)
    rc = export_ckpt.main(
        [
            "--ckpt",
            str(ckpt),
            "--out",
            str(tmp_path / "m.onnx"),
            "--profile",
            "devasa",
        ]
    )
    assert rc == 2


# ----------------------------------------------------------------------
# CLI sozlesmesi
# ----------------------------------------------------------------------


def test_export_ckpt_parser_defaults():
    args = export_ckpt.build_parser().parse_args(["--ckpt", "a.pt", "--out", "b.onnx"])
    assert args.version == 1
    assert args.profile is None
    assert args.device == "cpu"


def test_export_ckpt_parser_requires_ckpt_and_out():
    with pytest.raises(SystemExit):
        export_ckpt.build_parser().parse_args([])


def test_export_ckpt_parser_rejects_bad_device():
    with pytest.raises(SystemExit):
        export_ckpt.build_parser().parse_args(
            ["--ckpt", "a.pt", "--out", "b.onnx", "--device", "tpu"]
        )
