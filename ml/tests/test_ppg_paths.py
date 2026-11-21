"""K5: oyun yolu x model ppg matrisi testleri (Test 287-293, 298)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import ppg_paths as pp  # noqa: E402


def _write_match(
    tmp_path: Path,
    name: str,
    *,
    model: str,
    path: str,
    ppg: float,
    se: float = 0.05,
    games: int = 2000,
    unfinished: int = 0,
) -> Path:
    payload = {
        "model": model,
        "path": path,
        "games": games,
        "wins": games // 2,
        "winRate": 0.5,
        "ppg": ppg,
        "ppgCiLow": ppg - 1.96 * se,
        "ppgCiHigh": ppg + 1.96 * se,
        "ppgStdError": se,
        "meanPlies": 40.0,
        "unfinished": unfinished,
        "seed": 2026,
    }
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_287_ppg_paths_model_label():
    """``onnx/`` segmenti etiketten dusurulur."""
    assert (
        pp.model_label("ml/runs/stage_d_l2/onnx/model_v30.onnx") == "stage_d_l2/model_v30"
    )
    assert pp.model_label("ml/runs/rd_aug10k/model_v10.onnx") == "rd_aug10k/model_v10"
    assert pp.model_label("model.onnx") == "model"


def test_288_ppg_paths_load_match_label(tmp_path):
    """Etiket model ve yoldan turetilir; yol dosyadan okunur."""
    p = _write_match(
        tmp_path,
        "a.json",
        model="ml/runs/stage_d_l2/onnx/model_v30.onnx",
        path="value",
        ppg=-0.2,
    )
    m = pp.load_match(p)
    assert m.label == "stage_d_l2/model_v30 [value]"
    assert m.path == "value"
    assert m.ppg == pytest.approx(-0.2)


def test_289_ppg_paths_load_match_rejects_unknown_path(tmp_path):
    """Bilinmeyen yol sessizce kabul edilmez (Kural 6)."""
    p = _write_match(tmp_path, "b.json", model="m.onnx", path="value2", ppg=0.0)
    with pytest.raises(pp.PpgPathsError):
        pp.load_match(p)


def test_290_ppg_paths_matrix_and_duplicates(tmp_path):
    """Matris model x yol olarak kurulur; ayni hucre iki kez gelemez."""
    a = pp.load_match(
        _write_match(tmp_path, "1.json", model="runs/a/onnx/m.onnx", path="policy", ppg=-0.5)
    )
    b = pp.load_match(
        _write_match(tmp_path, "2.json", model="runs/a/onnx/m.onnx", path="search1", ppg=-0.1)
    )
    report = pp.build_report([a, b])
    assert report["models"] == ["a/m"]
    assert set(report["cells"]["a/m"]) == {"policy", "search1"}
    with pytest.raises(pp.PpgPathsError):
        pp.build_report([a, a])


def test_291_ppg_paths_path_diffs(tmp_path):
    """Yol farklari urun yoluna (search1) karsi verilir."""
    a = pp.load_match(
        _write_match(tmp_path, "1.json", model="runs/a/onnx/m.onnx", path="policy", ppg=-0.5)
    )
    b = pp.load_match(
        _write_match(tmp_path, "2.json", model="runs/a/onnx/m.onnx", path="search1", ppg=-0.1)
    )
    report = pp.build_report([a, b])
    assert len(report["pathDiffs"]) == 1
    d = report["pathDiffs"][0]
    assert d["a"].endswith("[policy]")
    assert d["b"].endswith("[search1]")
    assert d["diff"] == pytest.approx(-0.4)
    assert d["significant"] is True


def test_292_ppg_paths_model_diffs(tmp_path):
    """Model farklari ayni yol icinde, tabana karsi verilir."""
    base = pp.load_match(
        _write_match(tmp_path, "1.json", model="runs/a/onnx/m.onnx", path="value", ppg=-0.1)
    )
    other = pp.load_match(
        _write_match(tmp_path, "2.json", model="runs/b/onnx/m.onnx", path="value", ppg=-0.3)
    )
    report = pp.build_report([base, other], baseline="a/m")
    assert report["baseline"] == "a/m"
    assert len(report["modelDiffs"]) == 1
    d = report["modelDiffs"][0]
    assert d["a"].endswith("[value]")
    assert d["diff"] == pytest.approx(-0.2)


def test_293_ppg_paths_markdown_and_errors(tmp_path):
    """Markdown matrisi ve iki fark tablosunu tasir; bos girdi hata verir."""
    a = pp.load_match(
        _write_match(tmp_path, "1.json", model="runs/a/onnx/m.onnx", path="policy", ppg=-0.5)
    )
    b = pp.load_match(
        _write_match(tmp_path, "2.json", model="runs/a/onnx/m.onnx", path="search1", ppg=-0.1)
    )
    md = pp.build_markdown(pp.build_report([a, b]))
    assert "politika-argmax" in md
    assert "search1 (deger 1-ply)" in md
    assert "## Yol farklari" in md
    assert "## Uyari" in md
    with pytest.raises(pp.PpgPathsError):
        pp.build_report([])
    with pytest.raises(pp.PpgPathsError):
        pp.build_report([a, b], baseline="yok/m")


def test_298_ppg_paths_unfinished_per_model(tmp_path):
    """Bitmeyen oyun sayisi **kendi** modelinin satirinda cikar.

    Regresyon: dongu degiskeni sizintisi yuzunden tum satirlar son modelin
    sayisini gosteriyordu.
    """
    a = pp.load_match(
        _write_match(
            tmp_path,
            "1.json",
            model="runs/a/onnx/m.onnx",
            path="value",
            ppg=-0.1,
            unfinished=3,
        )
    )
    b = pp.load_match(
        _write_match(
            tmp_path,
            "2.json",
            model="runs/b/onnx/m.onnx",
            path="value",
            ppg=-0.2,
            unfinished=0,
        )
    )
    md = pp.build_markdown(pp.build_report([a, b]))
    assert "## Bitmeyen oyunlar" in md
    assert "| `a/m` | deger-0-ply | 3 | 0.0015 |" in md
    assert "`b/m` | deger-0-ply | 0" not in md
