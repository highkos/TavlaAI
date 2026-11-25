# -*- coding: utf-8 -*-
"""Faz 7-S5 - 100k asamasi: tohum secimi, ppg karari ve veri dogrulama."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import stage_100k  # noqa: E402


def _sweep(rows):
    return {"profile": "xlarge", "rows": rows}


def _row(seed, val_top1, **extra):
    row = {"seed": seed, "valTop1": val_top1}
    row.update(extra)
    return row


def _ppg(value, low, high, **extra):
    payload = {"ppg": value, "ppgCiLow": low, "ppgCiHigh": high}
    payload.update(extra)
    return payload


# ----------------------------------------------------------------------
# Tohum secimi
# ----------------------------------------------------------------------


def test_383_select_seed_picks_highest_val_top1():
    """Tohum secimi yalnizca valTop1'e bakar."""
    sweep = _sweep([_row(0, 0.81), _row(1, 0.84), _row(2, 0.82)])
    assert stage_100k.select_seed(sweep)["seed"] == 1


def test_384_select_seed_ignores_er_fields():
    """ER alanlari yuksek olsa da secim degismez (yanlilik onlenir)."""
    sweep = _sweep(
        [
            _row(0, 0.80, erSearch1=0.0100, erValue=0.0100),
            _row(1, 0.85, erSearch1=0.0900, erValue=0.0900),
        ]
    )
    assert stage_100k.select_seed(sweep)["seed"] == 1


def test_385_select_seed_tie_breaks_on_lowest_seed():
    """Esit valTop1'de kucuk tohum kazanir; secim deterministik olmali."""
    sweep = _sweep([_row(3, 0.83), _row(1, 0.83), _row(2, 0.83)])
    assert stage_100k.select_seed(sweep)["seed"] == 1


def test_386_select_seed_rejects_empty_rows():
    with pytest.raises(stage_100k.StageError):
        stage_100k.select_seed(_sweep([]))


def test_387_load_sweep_rejects_missing_fields(tmp_path):
    path = tmp_path / "sweep.json"
    path.write_text(json.dumps({"rows": [{"seed": 0}]}), encoding="utf-8")
    with pytest.raises(stage_100k.StageError):
        stage_100k.load_sweep(path)


def test_388_load_sweep_rejects_missing_file(tmp_path):
    with pytest.raises(stage_100k.StageError):
        stage_100k.load_sweep(tmp_path / "yok.json")


# ----------------------------------------------------------------------
# Karar
# ----------------------------------------------------------------------


def test_389_report_marks_worse_when_ci_below_negative_margin():
    """GA ust siniri -m altinda -> daha-kotu (F7-117 olcumu)."""
    report = stage_100k.build_report(
        _ppg(-0.2623, -0.3039, -0.2198), None, _row(0, 0.8294)
    )
    assert report["verdict"] == "daha-kotu"
    assert report["branch"] == stage_100k.BRANCHES["daha-kotu"]


def test_390_report_marks_equivalent_when_ci_above_negative_margin():
    report = stage_100k.build_report(
        _ppg(-0.0500, -0.0900, -0.0100), None, _row(0, 0.83)
    )
    assert report["verdict"] == "esdeger"


def test_391_report_marks_undecided_when_ci_straddles():
    report = stage_100k.build_report(
        _ppg(-0.1200, -0.2000, -0.0400), None, _row(0, 0.83)
    )
    assert report["verdict"] == "esdegerlik-kanitlanmadi"


def test_392_report_rejects_non_positive_margin():
    with pytest.raises(stage_100k.StageError):
        stage_100k.build_report(_ppg(-0.1, -0.2, 0.0), None, _row(0, 0.8), margin=0.0)


def test_393_report_rejects_missing_ci():
    with pytest.raises(stage_100k.StageError):
        stage_100k.build_report({"ppg": -0.1}, None, _row(0, 0.8))


def test_394_report_compares_against_baseline():
    """Fark ve bir-SE kontrolu taban kosuya gore hesaplanir."""
    report = stage_100k.build_report(
        _ppg(-0.2623, -0.3039, -0.2198, ppgStdError=0.02141, games=4400),
        _ppg(-0.2445, -0.3055, -0.1835, ppgStdError=0.03101, games=2000),
        _row(0, 0.8294),
    )
    diff = report["difference"]
    assert diff["ppg"] == pytest.approx(-0.0178, abs=1e-4)
    assert diff["stdError"] == pytest.approx(0.03768, abs=1e-4)
    assert diff["withinOneSe"] is True
    assert diff["ciOverlaps"] is True
    assert report["baseline"]["verdict"] == "daha-kotu"


def test_395_report_without_baseline_has_no_difference():
    report = stage_100k.build_report(_ppg(-0.2, -0.3, -0.1), None, _row(0, 0.8))
    assert "baseline" not in report
    assert "difference" not in report


def test_396_render_markdown_contains_verdict_and_branch():
    report = stage_100k.build_report(
        _ppg(-0.2623, -0.3039, -0.2198, games=4400, pairs=2200, path="search1"),
        _ppg(-0.2445, -0.3055, -0.1835, games=2000),
        _row(0, 0.8294, params=1805319, bestStep=4500),
    )
    text = stage_100k.render_markdown(report)
    assert "daha-kotu" in text
    assert "0.1115" in text
    assert "1805319" in text
    assert "search1" in text


# ----------------------------------------------------------------------
# Veri dogrulama
# ----------------------------------------------------------------------


def _write_npz(path, *, positions=4, candidates=10, with_dist=True, with_equity=True):
    offsets = np.linspace(0, candidates, positions + 1).astype(np.int64)
    payload = {
        "x": np.zeros((candidates, 221), dtype=np.float32),
        "offsets": offsets,
        "best": np.zeros(positions, dtype=np.int32),
        "y": np.zeros(positions, dtype=np.float32),
    }
    if with_dist:
        payload["dist"] = np.zeros((positions, 6), dtype=np.float32)
    if with_equity:
        payload["cand_equity"] = np.zeros(candidates, dtype=np.float32)
    np.savez(path, **payload)
    return path


def test_397_check_dataset_counts_positions_from_offsets(tmp_path):
    """Pozisyon sayisi ``offsets``'ten gelir; ``x`` aday dizisidir."""
    path = _write_npz(tmp_path / "d.npz", positions=4, candidates=10)
    result = stage_100k.check_dataset(path, min_count=4)
    assert result["count"] == 4
    assert result["candidates"] == 10
    assert result["meanCandidates"] == pytest.approx(2.5)
    assert result["ready"] is True


def test_398_check_dataset_flags_missing_arrays(tmp_path):
    path = _write_npz(
        tmp_path / "d.npz", positions=4, candidates=10, with_dist=False, with_equity=False
    )
    result = stage_100k.check_dataset(path, min_count=4)
    assert result["ready"] is False
    assert any("dist" in p for p in result["problems"])
    assert any("cand_equity" in p for p in result["problems"])


def test_399_check_dataset_flags_short_count(tmp_path):
    path = _write_npz(tmp_path / "d.npz", positions=4, candidates=10)
    result = stage_100k.check_dataset(path, min_count=100_000)
    assert result["ready"] is False
    assert any("pozisyon sayisi" in p for p in result["problems"])


def test_400_check_dataset_rejects_missing_file(tmp_path):
    with pytest.raises(stage_100k.StageError):
        stage_100k.check_dataset(tmp_path / "yok.npz")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_401_cli_select_writes_json(tmp_path):
    sweep_path = tmp_path / "sweep.json"
    sweep_path.write_text(
        json.dumps(_sweep([_row(0, 0.81), _row(1, 0.84)])), encoding="utf-8"
    )
    out = tmp_path / "sel.json"
    assert stage_100k.main(["select", "--sweep", str(sweep_path), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["seed"] == 1
    assert payload["valTop1"] == pytest.approx(0.84)
    assert len(payload["candidates"]) == 2


def test_402_cli_report_writes_json_and_markdown(tmp_path):
    ppg_path = tmp_path / "ppg.json"
    ppg_path.write_text(
        json.dumps(_ppg(-0.2623, -0.3039, -0.2198, games=4400)), encoding="utf-8"
    )
    base_path = tmp_path / "base.json"
    base_path.write_text(
        json.dumps(_ppg(-0.2445, -0.3055, -0.1835, games=2000)), encoding="utf-8"
    )
    sel_path = tmp_path / "sel.json"
    sel_path.write_text(json.dumps(_row(0, 0.8294)), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    code = stage_100k.main(
        [
            "report",
            "--ppg",
            str(ppg_path),
            "--baseline",
            str(base_path),
            "--selection",
            str(sel_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["verdict"] == "daha-kotu"
    assert payload["margin"] == pytest.approx(stage_100k.DEFAULT_MARGIN)
    assert "daha-kotu" in out_md.read_text(encoding="utf-8")


def test_403_cli_check_exit_code_reflects_readiness(tmp_path):
    path = _write_npz(tmp_path / "d.npz", positions=4, candidates=10)
    assert stage_100k.main(["check", "--data", str(path), "--min-count", "4"]) == 0
    assert stage_100k.main(["check", "--data", str(path), "--min-count", "99"]) == 1


def test_404_default_margin_is_fixed():
    """R-F madde 3/5: marj kosudan once sabitlenir."""
    assert stage_100k.DEFAULT_MARGIN == 0.1115
