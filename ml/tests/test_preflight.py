"""F7-119: EVREN on-kontrolu testleri (367-371)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import preflight  # noqa: E402


def test_367_check_line_marks_states() -> None:
    """367: PASS / FAIL / WARN isaretleri dogru."""
    assert "[PASS]" in preflight.Check("a", True).line()
    assert "[FAIL]" in preflight.Check("b", False).line()
    assert "[WARN]" in preflight.Check("c", False, fatal=False).line()


def test_368_preflight_reports_required_checks(tmp_path: Path) -> None:
    """368: temel kontroller raporda yer alir ve sonuc tutarlidir."""
    report = preflight.run_preflight(out_dir=tmp_path, skip_pipeline=True)
    names = {c["name"] for c in report["checks"]}
    for required in ("python", "paket:numpy", "paket:torch", "disk", "yazma-izni"):
        assert required in names
    assert report["ok"] == (not report["failed"])
    assert report["preflightVersion"] == preflight.PREFLIGHT_VERSION


def test_369_missing_data_file_fails(tmp_path: Path) -> None:
    """369: olmayan veri dosyasi FAIL uretir."""
    report = preflight.run_preflight(
        data=tmp_path / "nope.npz", out_dir=tmp_path, skip_pipeline=True
    )
    assert report["ok"] is False
    assert "veri:egitim" in report["failed"]


def test_370_missing_gnubg_is_only_a_warning(tmp_path: Path, monkeypatch) -> None:
    """370: gnubg yoksa FAIL degil WARN (egitim gnubg'siz de calisir)."""
    import gnubg_er

    def boom():
        raise RuntimeError("yok")

    monkeypatch.setattr(gnubg_er, "find_gnubg", boom)
    report = preflight.run_preflight(out_dir=tmp_path, skip_pipeline=True)
    assert "gnubg" in report["warned"]
    assert "gnubg" not in report["failed"]


def test_371_markdown_lists_every_check(tmp_path: Path) -> None:
    """371: markdown tablosu her kontrolu ve sonucu yazar."""
    report = preflight.run_preflight(out_dir=tmp_path, skip_pipeline=True)
    text = preflight.build_markdown(report)
    assert "# EVREN on-kontrolu" in text
    for check in report["checks"]:
        assert "`%s`" % check["name"] in text
    assert ("HAZIR" in text) is True


def test_372_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    """372: CLI cikti dosyalarini yazar; cikis kodu sonuca uyar."""
    js = tmp_path / "preflight.json"
    md = tmp_path / "preflight.md"
    code = preflight.main(
        [
            "--out-dir",
            str(tmp_path),
            "--skip-pipeline",
            "--json",
            str(js),
            "--markdown",
            str(md),
            "--quiet",
        ]
    )
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert md.is_file()
    assert code == (0 if payload["ok"] else 1)
