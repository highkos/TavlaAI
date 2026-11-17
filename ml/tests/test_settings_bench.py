"""Faz 4 v3 Bolum 9 — arama ayari olcum tablosu testleri."""

from __future__ import annotations

from pathlib import Path

import pytest

from settings_bench import (
    DEFAULT_COMBOS,
    PROFILES,
    ComboResult,
    build_markdown,
)


def _row(label: str, depth: int, gps: float, mean: float, se: float, games: int) -> ComboResult:
    return ComboResult(
        label=label,
        depth=depth,
        max_root=0,
        max_inner=0,
        selfplay_games=20,
        selfplay_seconds=1.0,
        games_per_second=gps,
        bytes_per_game=1000.0,
        eval_games=games,
        mean_points=mean,
        standard_error=se,
        win_rate=0.5,
        lower_confidence_bound=mean - 1.96 * se,
        upper_confidence_bound=mean + 1.96 * se,
    )


def test_default_combos_cover_depth_0_1_2_and_both_candidate_modes():
    depths = {c[0] for c in DEFAULT_COMBOS}
    assert depths == {0, 1, 2}

    unrestricted = [c for c in DEFAULT_COMBOS if c[1] == 0 and c[2] == 0]
    restricted = [c for c in DEFAULT_COMBOS if c[1] > 0 and c[2] > 0]
    assert len(unrestricted) == 3
    assert len(restricted) == 3


def test_profiles_have_all_depths():
    for name, profile in PROFILES.items():
        assert set(profile) == {0, 1, 2}, name
        for depth, (sp, ev) in profile.items():
            assert sp >= 1, (name, depth)
            assert ev >= 1, (name, depth)


def test_build_markdown_has_all_columns_and_rows():
    rows = [
        _row("depth 0, kisitsiz", 0, 58.87, -1.0, 0.1, 100),
        _row("depth 1, kisitli (4/4)", 1, 2.10, 0.0, 0.2, 20),
    ]
    text = build_markdown(Path("m.onnx"), rows, seed=1)

    assert "| Ayar | DepthPly | MaxRoot / Inner | Oyun/s | s/oyun | B/oyun | Oyun |" in text
    assert "depth 0, kisitsiz" in text
    assert "depth 1, kisitli (4/4)" in text
    assert "58.87" in text
    assert "2.10" in text
    assert "`m.onnx`" in text


def test_build_markdown_notes_depth2_caveat():
    text = build_markdown(Path("m.onnx"), [_row("x", 2, 0.01, 0.0, 0.5, 2)], seed=1)
    assert "istatistiksel olarak anlamsızdır" in text


def test_build_markdown_handles_zero_throughput():
    text = build_markdown(Path("m.onnx"), [_row("x", 0, 0.0, 0.0, 0.0, 1)], seed=1)
    assert "nan" in text