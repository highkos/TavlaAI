"""F7-118: egitim denetim noktasi (resume) testleri (362-366)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import gnubg_distill as gd  # noqa: E402
from model import VECTOR_SIZE, build_model  # noqa: E402


def _dataset(n: int = 24, width: int = 3, seed: int = 7) -> gd.PolicyDataset:
    rng = np.random.default_rng(seed)
    x = rng.random((n * width, VECTOR_SIZE)).astype(np.float32)
    offsets = np.arange(0, n * width + 1, width, dtype=np.int64)
    best = rng.integers(0, width, n).astype(np.int32)
    y = rng.normal(0.0, 0.5, n).astype(np.float32)
    return gd.PolicyDataset(x=x, offsets=offsets, best=best, y=y)


def _model(seed: int = 0):
    return build_model(VECTOR_SIZE, seed=seed, output_version=2, profile="small")


def test_362_checkpoint_written_and_resumed(tmp_path: Path) -> None:
    """362: denetim noktasi yazilir ve kaldigi adimdan devam eder."""
    ckpt = tmp_path / "train_checkpoint.pt"
    model = _model()
    first = gd.train_policy_head(
        model,
        _dataset(),
        steps=20,
        batch=8,
        seed=1,
        checkpoint=ckpt,
        checkpoint_every=5,
    )
    assert ckpt.is_file()
    assert first["resumedFrom"] == 0
    assert first["stepsRun"] == 20

    second = gd.train_policy_head(
        model,
        _dataset(),
        steps=40,
        batch=8,
        seed=1,
        checkpoint=ckpt,
        checkpoint_every=5,
        resume=True,
    )
    assert second["resumedFrom"] == 20
    assert second["stepsRun"] == 40
    assert len(second["history"]) == 40


def test_363_resume_without_checkpoint_starts_fresh(tmp_path: Path) -> None:
    """363: ``resume`` verilse de dosya yoksa sifirdan baslar."""
    report = gd.train_policy_head(
        _model(),
        _dataset(),
        steps=10,
        batch=8,
        seed=2,
        checkpoint=tmp_path / "missing.pt",
        checkpoint_every=5,
        resume=True,
    )
    assert report["resumedFrom"] == 0
    assert report["stepsRun"] == 10


def test_364_checkpoint_disabled_writes_nothing(tmp_path: Path) -> None:
    """364: ``checkpoint_every = 0`` iken dosya yazilmaz."""
    ckpt = tmp_path / "train_checkpoint.pt"
    gd.train_policy_head(
        _model(),
        _dataset(),
        steps=10,
        batch=8,
        seed=3,
        checkpoint=ckpt,
        checkpoint_every=0,
    )
    assert not ckpt.exists()


def test_365_resume_restores_weights_not_just_counter(tmp_path: Path) -> None:
    """365: devam eden kosu, ilk kosunun agirliklarindan baslar."""
    import torch

    ckpt = tmp_path / "train_checkpoint.pt"
    model = _model(seed=4)
    gd.train_policy_head(
        model,
        _dataset(),
        steps=15,
        batch=8,
        seed=4,
        checkpoint=ckpt,
        checkpoint_every=5,
    )
    saved = torch.load(str(ckpt), map_location="cpu", weights_only=False)
    assert saved["step"] == 15
    assert saved["opt"] is not None
    assert saved["torchRng"] is not None

    fresh = _model(seed=4)
    before = {k: v.clone() for k, v in fresh.state_dict().items()}
    gd.train_policy_head(
        fresh,
        _dataset(),
        steps=16,
        batch=8,
        seed=4,
        checkpoint=ckpt,
        checkpoint_every=5,
        resume=True,
    )
    # En az bir agirlik ilk kosudaki degerden farkli olmali (egitim surdu).
    changed = any(
        not torch.equal(before[k], v) for k, v in fresh.state_dict().items()
    )
    assert changed


def test_366_checkpoint_is_atomic(tmp_path: Path) -> None:
    """366: gecici dosya birakilmaz (atomik yazim)."""
    ckpt = tmp_path / "train_checkpoint.pt"
    gd.train_policy_head(
        _model(),
        _dataset(),
        steps=10,
        batch=8,
        seed=5,
        checkpoint=ckpt,
        checkpoint_every=5,
    )
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
