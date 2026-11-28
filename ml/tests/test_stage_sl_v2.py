"""F8-04: ``ml/stage_sl_v2.py`` karar kurali testleri."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import stage_sl_v2 as sv


def _rec(path: str, c: float, cm: float, r: float, rm: float) -> dict:
    return {
        "model": {"path": path},
        "sets": {
            "contact": {"mean": c, "exactMatchRate": cm},
            "race": {"mean": r, "exactMatchRate": rm},
        },
    }


def _write_bench(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "model_benchmarks.json"
    p.write_text(json.dumps({"benchVersion": 1, "records": records}), encoding="utf-8")
    return p


def test_f804_latest_by_path_keeps_last_record() -> None:
    """Append-only defterde ayni model icin **son** olcum gecerlidir."""
    recs = [
        _rec("a.onnx", 0.5, 0.1, 0.5, 0.1),
        _rec("a.onnx", 0.1, 0.9, 0.1, 0.9),
    ]
    out = sv.latest_by_path(recs)
    assert out["a.onnx"]["sets"]["contact"]["mean"] == pytest.approx(0.1)


def test_f804_metrics_unpacks_four_values() -> None:
    c, cm, r, rm = sv.metrics(_rec("a.onnx", 0.01, 0.8, 0.02, 0.6))
    assert (c, cm, r, rm) == pytest.approx((0.01, 0.8, 0.02, 0.6))


def test_f804_verdict_accepts_when_both_below_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = _write_bench(
        tmp_path,
        [
            _rec(sv.BASELINE_PATH, 0.0070, 0.77, 0.0122, 0.65),
            _rec("ml/runs/corpus_sl_v2/mp100_2ply/seed0/model.onnx", 0.0060, 0.80, 0.0110, 0.66),
            _rec("ml/runs/corpus_sl_v2/mp100_2ply/seed1/model.onnx", 0.0062, 0.80, 0.0112, 0.66),
            _rec("ml/runs/corpus_sl_v2/mp100_2ply/seed2/model.onnx", 0.0061, 0.80, 0.0111, 0.66),
        ],
    )
    monkeypatch.setattr(sv, "BENCH", bench)
    monkeypatch.setattr(sv, "OUT_MD", tmp_path / "report.md")
    assert sv.main() == 0
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "KABUL" in text
    assert "mp100_2ply" in text


def test_f804_verdict_rejects_when_contact_worse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = _write_bench(
        tmp_path,
        [
            _rec(sv.BASELINE_PATH, 0.0070, 0.77, 0.0122, 0.65),
            _rec("ml/runs/corpus_sl_v2/d12k_3ply/seed0/model.onnx", 0.0090, 0.78, 0.0100, 0.66),
        ],
    )
    monkeypatch.setattr(sv, "BENCH", bench)
    monkeypatch.setattr(sv, "OUT_MD", tmp_path / "report.md")
    assert sv.main() == 0
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Hiçbir korpus kabul eşiğini geçmedi" in text


def test_f804_verdict_rejects_when_race_worse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contact iyilesip yaris kotulesirse kabul **edilmez** (iki kosul birlikte)."""
    bench = _write_bench(
        tmp_path,
        [
            _rec(sv.BASELINE_PATH, 0.0070, 0.77, 0.0122, 0.65),
            _rec("ml/runs/corpus_sl_v2/d12k_2ply/seed0/model.onnx", 0.0050, 0.80, 0.0200, 0.60),
        ],
    )
    monkeypatch.setattr(sv, "BENCH", bench)
    monkeypatch.setattr(sv, "OUT_MD", tmp_path / "report.md")
    assert sv.main() == 0
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Hiçbir korpus kabul eşiğini geçmedi" in text


def test_f804_no_measurements_writes_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Olcum yokken rapor yazilmaz (yaniltici artefakt onlenir)."""
    bench = _write_bench(tmp_path, [_rec(sv.BASELINE_PATH, 0.0070, 0.77, 0.0122, 0.65)])
    out = tmp_path / "report.md"
    monkeypatch.setattr(sv, "BENCH", bench)
    monkeypatch.setattr(sv, "OUT_MD", out)
    assert sv.main() == 1
    assert not out.exists()


def test_f804_missing_baseline_returns_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = _write_bench(tmp_path, [_rec("other.onnx", 0.1, 0.1, 0.1, 0.1)])
    monkeypatch.setattr(sv, "BENCH", bench)
    monkeypatch.setattr(sv, "OUT_MD", tmp_path / "report.md")
    assert sv.main() == 2


def test_f804_corpora_and_seeds_are_fixed() -> None:
    """Karar kurali kosudan once sabit: korpus ve tohum listesi degismez."""
    assert sv.CORPORA == ("mp100_2ply", "d12k_3ply", "d12k_2ply")
    assert sv.SEEDS == (0, 1, 2)
