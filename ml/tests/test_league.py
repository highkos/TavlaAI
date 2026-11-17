"""Faz 4 v3 Bolum 6.5 — lig (model havuzu) testleri."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from league import (
    EVICTION_OLDEST,
    EVICTION_WEAKEST,
    EvalResult,
    League,
    LeagueError,
    PoolEntry,
    format_report,
    should_enter_pool,
)


def _entry(name: str, iteration: int, strength: float = 0.0, se: float = 0.0) -> PoolEntry:
    return PoolEntry(
        name=name,
        onnx_path="pool/" + name + ".onnx",
        model_version=iteration,
        iteration=iteration,
        strength=strength,
        strength_se=se,
    )


# ----------------------------------------------------------------------
# Temel davranis
# ----------------------------------------------------------------------


def test_empty_league_has_no_strongest_and_no_opponent(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    assert len(league) == 0
    assert league.is_empty()
    assert league.strongest() is None
    assert league.select_opponent(np.random.default_rng(0), 0.2) is None


def test_strongest_picks_highest_strength_then_newest(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [
        _entry("a", 1, strength=0.1),
        _entry("b", 2, strength=0.5),
        _entry("c", 3, strength=0.5),
    ]
    assert league.strongest().name == "c"


def test_add_rejects_duplicate_name(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [_entry("a", 1)]
    with pytest.raises(LeagueError):
        league.add(_entry("a", 2))


def test_invalid_eviction_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        League(pool_dir=tmp_path, eviction="random")


def test_invalid_max_size_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        League(pool_dir=tmp_path, max_size=0)


# ----------------------------------------------------------------------
# Eleme politikalari
# ----------------------------------------------------------------------


def test_oldest_eviction_removes_lowest_iteration(tmp_path: Path):
    league = League(pool_dir=tmp_path, max_size=2, eviction=EVICTION_OLDEST)
    league.entries = [_entry("a", 1, strength=0.9), _entry("b", 2, strength=0.1)]

    evicted = league.add(_entry("c", 3, strength=0.5))

    assert [e.name for e in evicted] == ["a"]
    assert league.names() == ["b", "c"]


def test_weakest_eviction_removes_lowest_strength(tmp_path: Path):
    league = League(pool_dir=tmp_path, max_size=2, eviction=EVICTION_WEAKEST)
    league.entries = [_entry("a", 1, strength=0.9), _entry("b", 2, strength=0.1)]

    evicted = league.add(_entry("c", 3, strength=0.5))

    assert [e.name for e in evicted] == ["b"]
    assert league.names() == ["a", "c"]


def test_eviction_deletes_artifact_file(tmp_path: Path):
    league = League(pool_dir=tmp_path, max_size=1, eviction=EVICTION_OLDEST)
    artifact = tmp_path / "a.onnx"
    artifact.write_bytes(b"x")

    league.entries = [
        PoolEntry(name="a", onnx_path=str(artifact), model_version=1, iteration=1)
    ]
    league.add(_entry("b", 2))

    assert not artifact.exists()


# ----------------------------------------------------------------------
# Kalicilik
# ----------------------------------------------------------------------


def test_save_load_round_trip(tmp_path: Path):
    league = League(pool_dir=tmp_path, max_size=4, eviction=EVICTION_WEAKEST)
    league.entries = [_entry("a", 1, strength=0.25, se=0.05)]
    league.save()

    loaded = League.load(tmp_path)
    assert loaded.max_size == 4
    assert loaded.eviction == EVICTION_WEAKEST
    assert loaded.names() == ["a"]
    assert loaded.entries[0].strength == pytest.approx(0.25)
    assert loaded.entries[0].strength_se == pytest.approx(0.05)


def test_load_missing_index_returns_empty(tmp_path: Path):
    league = League.load(tmp_path / "does_not_exist")
    assert league.is_empty()
    assert league.max_size == 10


def test_load_overrides_win(tmp_path: Path):
    league = League(pool_dir=tmp_path, max_size=4, eviction=EVICTION_WEAKEST)
    league.save()

    loaded = League.load(tmp_path, max_size=7, eviction=EVICTION_OLDEST)
    assert loaded.max_size == 7
    assert loaded.eviction == EVICTION_OLDEST


def test_import_model_copies_file(tmp_path: Path):
    src = tmp_path / "src.onnx"
    src.write_bytes(b"onnx-bytes")

    league = League(pool_dir=tmp_path / "pool")
    target = league.import_model(src, "v1", 1, 1)

    assert target.is_file()
    assert target.read_bytes() == b"onnx-bytes"
    assert target.parent == tmp_path / "pool"


# ----------------------------------------------------------------------
# Rakip secimi
# ----------------------------------------------------------------------


def test_select_opponent_zero_fraction_never_selects(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [_entry("a", 1)]
    rng = np.random.default_rng(0)
    for _ in range(50):
        assert league.select_opponent(rng, 0.0) is None


def test_select_opponent_full_fraction_always_selects(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [_entry("a", 1), _entry("b", 2)]
    rng = np.random.default_rng(0)
    for _ in range(50):
        picked = league.select_opponent(rng, 1.0)
        assert picked is not None
        assert picked.name in ("a", "b")


def test_select_opponent_fraction_is_roughly_respected(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [_entry("a", 1)]
    rng = np.random.default_rng(12345)

    hits = sum(1 for _ in range(4000) if league.select_opponent(rng, 0.2) is not None)
    assert 0.17 <= hits / 4000.0 <= 0.23


# ----------------------------------------------------------------------
# Giris esigi
# ----------------------------------------------------------------------


def _result(mean: float, se: float) -> EvalResult:
    return EvalResult(
        opponent="Model",
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


def test_should_enter_pool_uses_lower_confidence_bound():
    assert should_enter_pool(_result(0.5, 0.1), 0.0) is True
    assert should_enter_pool(_result(0.1, 0.1), 0.0) is False
    assert should_enter_pool(_result(0.0, 0.0), 0.0) is False
    assert should_enter_pool(_result(0.1, 0.1), -0.5) is True


def test_pool_entry_lower_confidence_bound_property():
    entry = _entry("a", 1, strength=0.3, se=0.1)
    assert entry.lower_confidence_bound == pytest.approx(0.3 - 0.196)


# ----------------------------------------------------------------------
# C# JSON sozlesmesi
# ----------------------------------------------------------------------


def test_eval_result_from_csharp_json():
    payload = {
        "opponent": "PipBot",
        "games": 100,
        "wins": 41,
        "losses": 51,
        "draws": 8,
        "winRate": 0.41,
        "meanPoints": -0.27,
        "standardError": 0.2054,
        "lowerConfidenceBound": -0.6726,
        "upperConfidenceBound": 0.1326,
    }
    r = EvalResult.from_dict(payload)
    assert r.opponent == "PipBot"
    assert r.games == 100
    assert r.win_rate == pytest.approx(0.41)
    assert r.mean_points == pytest.approx(-0.27)
    assert r.lower_confidence_bound == pytest.approx(-0.6726)


def test_format_report_renders_table():
    text = format_report([_result(0.25, 0.05), _result(-0.5, 0.1)])
    assert "| Rakip |" in text
    assert "Model" in text
    assert "+0.2500" in text
    assert "-0.5000" in text


def test_pool_index_is_valid_json(tmp_path: Path):
    league = League(pool_dir=tmp_path)
    league.entries = [_entry("a", 1, strength=0.1, se=0.02)]
    league.save()

    data = json.loads((tmp_path / "pool.json").read_text(encoding="utf-8"))
    assert data["maxSize"] == 10
    assert data["eviction"] == EVICTION_OLDEST
    assert data["entries"][0]["name"] == "a"