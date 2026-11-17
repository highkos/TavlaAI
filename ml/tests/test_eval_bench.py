"""Faz 4 v3 Bolum 9 — degerlendirme tezgahi testleri."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval_bench import build_markdown, evaluate, plot_convergence
from league import EvalResult


def _result(opponent: str, mean: float, se: float) -> EvalResult:
    return EvalResult(
        opponent=opponent,
        games=400,
        wins=200,
        losses=200,
        draws=0,
        win_rate=0.5,
        mean_points=mean,
        standard_error=se,
        lower_confidence_bound=mean - 1.96 * se,
        upper_confidence_bound=mean + 1.96 * se,
    )


def test_build_markdown_contains_protocol_and_table():
    text = build_markdown(
        Path("model.onnx"),
        [_result("RandomBot", 0.4, 0.1), _result("PipBot", -0.2, 0.1)],
        games=400,
        seed=7,
        depth=1,
        max_root=0,
        max_inner=4,
    )
    assert "`model.onnx`" in text
    assert "| DepthPly | 1 |" in text
    assert "| MaxCandidatesRoot / Inner | 0 / 4 |" in text
    assert "RandomBot" in text
    assert "PipBot" in text
    assert "argmax" in text


def test_evaluate_rejects_unknown_opponent(tmp_path: Path):
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    with pytest.raises(ValueError):
        evaluate(model, games=1, opponents=["gnubg"])


def test_plot_convergence_writes_png(tmp_path: Path):
    pytest.importorskip("matplotlib")

    report = {
        "games_per_iteration": 100,
        "steps_per_iteration": 200,
        "depth": 0,
        "history": [
            {
                "iteration": 1,
                "probe_mc_value_loss": 2.0,
                "probe_value_loss": 2.0,
                "buffer_value_loss": 2.0,
                "buffer_policy_loss": 2.2,
                "buffer_uniform_baseline": 2.2,
                "buffer_target_entropy_ratio": 0.99,
                "grad_norm_mean": 0.5,
                "grad_norm_max": 1.0,
            },
            {
                "iteration": 2,
                "probe_mc_value_loss": 1.5,
                "probe_value_loss": 1.6,
                "buffer_value_loss": 1.7,
                "buffer_policy_loss": 1.9,
                "buffer_uniform_baseline": 2.1,
                "buffer_target_entropy_ratio": 0.5,
                "grad_norm_mean": 1.2,
                "grad_norm_max": 2.5,
            },
        ],
    }
    src = tmp_path / "train_report.json"
    src.write_text(json.dumps(report), encoding="utf-8")

    out = plot_convergence(src, tmp_path / "chart.png")
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_plot_convergence_rejects_empty_history(tmp_path: Path):
    pytest.importorskip("matplotlib")
    src = tmp_path / "r.json"
    src.write_text(json.dumps({"history": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        plot_convergence(src, tmp_path / "c.png")