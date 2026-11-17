"""Test 93. Olcum butunlugu -- dort bagimsiz prob (Faz 7 Bolum 4.3).

Kapsam:
  * Prob 1 -- tahta donusumu (F6-31 avcisi)
  * Prob 2 -- sutun secimi (F6-32 avcisi)
  * Prob 3 -- perspektif (F6-29: ag antisimetrik degil, isaret tutarli olmali)
  * Prob 4 -- pip sayisi

Sutun secimi, rapor ve sabit testleri gnubg olmadan da calisir; tahta, perspektif
ve pip probu gercek gnubg ister ve `requires_gnubg` ile atlanir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gnubg_er as G
import measure_integrity as M

GNUBG = G.find_gnubg()
requires_gnubg = pytest.mark.skipif(GNUBG is None, reason="gnubg-cli kurulu degil")


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_93_probe_names_are_the_four_required() -> None:
    """Faz 7 Bolum 4.3 dort prob ister: tahta, sutun, perspektif, pip."""
    assert M.PROBE_NAMES == ("board", "column", "perspective", "pip")


def test_93_every_probe_has_a_label() -> None:
    for name in M.PROBE_NAMES:
        assert M.PROBE_LABELS[name]


def test_93_doc_board_matches_the_spec() -> None:
    """Beyaz 1 pul projede 24, Siyah 1 pul projede 1."""
    board = list(M.DOC_BOARD)
    assert len(board) == 26
    assert board[24] == 1
    assert board[1] == -1
    assert sum(1 for v in board if v) == 2


def test_93_doc_board_variants_are_distinct() -> None:
    """Isaret-ters ve aynalanmis donusumler ayni tahta olmamali."""
    assert list(M.DOC_BOARD_SIGN_FLIPPED) != list(M.DOC_BOARD)
    assert list(M.DOC_BOARD_MIRRORED) != list(M.DOC_BOARD)
    assert list(M.DOC_BOARD_SIGN_FLIPPED) == list(M.DOC_BOARD_MIRRORED)


def test_93_bar_board_has_one_piece_on_each_bar() -> None:
    board = list(M.BAR_BOARD)
    assert board[0] == 1
    assert board[25] == -1
    assert sum(1 for v in board if v) == 2


def test_93_start_pip_constant_matches_reference_generator() -> None:
    import tools.reference_gen as refgen

    assert G.pip_count(refgen.START_BOARD, 1) == M.START_PIP
    assert G.pip_count(refgen.START_BOARD, -1) == M.START_PIP


def test_93_bar_pip_constant_matches_pip_count() -> None:
    assert G.pip_count(list(M.BAR_BOARD), 1) == M.BAR_PIP
    assert G.pip_count(list(M.BAR_BOARD), -1) == M.BAR_PIP


# ----------------------------------------------------------------------
# Prob 2 -- sutun secimi (gnubg gerektirmez)
# ----------------------------------------------------------------------


def test_93_column_probe_passes() -> None:
    result = M.probe_column_selection()
    assert result.ok, result.detail
    assert result.name == M.PROBE_COLUMN


def test_93_column_probe_covers_every_case() -> None:
    result = M.probe_column_selection()
    assert len(result.evidence["cases"]) == len(M.COLUMN_CASES)
    assert all(row["ok"] for row in result.evidence["cases"])


def test_93_column_probe_reports_max_eval_plies() -> None:
    result = M.probe_column_selection()
    assert result.evidence["maxEvalPlies"] == 2


@pytest.mark.parametrize("plies,expected", [(0, 0.1), (1, 0.2), (2, 0.3)])
def test_93_equity_at_selects_the_requested_column(plies: int, expected: float) -> None:
    table = {"static": 0.1, "1": 0.2, "2": 0.3}
    assert G._equity_at(table, plies) == expected


def test_93_equity_at_does_not_prefer_static_when_it_is_largest() -> None:
    """F6-32'nin tam sekli: eski kod `static`'i en derin sanip seciyordu."""
    table = {"static": 0.9, "1": 0.2, "2": 0.3}
    assert G._equity_at(table, 2) == 0.3


@pytest.mark.parametrize("plies", [3, 4, 5])
def test_93_equity_at_rejects_depth_beyond_two(plies: int) -> None:
    table = {"static": 0.1, "1": 0.2, "2": 0.3}
    with pytest.raises(ValueError):
        G._equity_at(table, plies)


@pytest.mark.parametrize(
    "table,plies",
    [
        ({"static": 0.1, "1": 0.2}, 2),
        ({"static": 0.1}, 1),
        ({}, 0),
    ],
)
def test_93_equity_at_rejects_missing_column(table: dict, plies: int) -> None:
    with pytest.raises(ValueError):
        G._equity_at(table, plies)


def test_93_column_probe_detects_a_broken_equity_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prob gercekten ayirt edici mi: bozuk bir `_equity_at` yakalanmali."""

    def broken(table: dict, plies: int) -> float:
        return table.get("static", 0.0)

    monkeypatch.setattr(G, "_equity_at", broken)
    result = M.probe_column_selection()
    assert not result.ok
    assert "ValueError" in result.detail or "beklendi" in result.detail


# ----------------------------------------------------------------------
# Sonuc tipleri
# ----------------------------------------------------------------------


def _probe(name: str = M.PROBE_COLUMN, ok: bool = True) -> M.ProbeResult:
    return M.ProbeResult(name, ok, "ok" if ok else "kaldi", {"x": 1})


def test_93_probe_result_to_dict_round_trips() -> None:
    payload = _probe().to_dict()
    assert payload["name"] == M.PROBE_COLUMN
    assert payload["label"] == M.PROBE_LABELS[M.PROBE_COLUMN]
    assert payload["ok"] is True
    assert payload["evidence"] == {"x": 1}


def test_93_probe_result_label_falls_back_to_name() -> None:
    assert M.ProbeResult("bilinmeyen", True, "ok").label == "bilinmeyen"


def test_93_report_ok_requires_all_probes() -> None:
    report = M.IntegrityReport("gnubg", [_probe(ok=True), _probe(ok=True)])
    assert report.ok
    assert report.failed == []


def test_93_report_not_ok_when_any_probe_fails() -> None:
    report = M.IntegrityReport("gnubg", [_probe(ok=True), _probe(M.PROBE_PIP, ok=False)])
    assert not report.ok
    assert report.failed == [M.PROBE_PIP]


def test_93_empty_report_is_not_ok() -> None:
    assert not M.IntegrityReport("gnubg").ok


def test_93_report_to_dict_lists_failures() -> None:
    report = M.IntegrityReport("gnubg", [_probe(M.PROBE_BOARD, ok=False)])
    payload = report.to_dict()
    assert payload["ok"] is False
    assert payload["failed"] == [M.PROBE_BOARD]
    assert len(payload["probes"]) == 1


def test_93_assert_integrity_passes_on_clean_report() -> None:
    M.assert_integrity(M.IntegrityReport("gnubg", [_probe()]))


def test_93_assert_integrity_raises_on_failure() -> None:
    with pytest.raises(M.IntegrityError):
        M.assert_integrity(M.IntegrityReport("gnubg", [_probe(M.PROBE_PIP, ok=False)]))


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def test_93_markdown_has_a_row_per_probe() -> None:
    report = M.IntegrityReport("gnubg", [_probe(M.PROBE_BOARD), _probe(M.PROBE_PIP)])
    text = M.build_markdown(report)
    assert "GECTI" in text
    assert M.PROBE_LABELS[M.PROBE_BOARD] in text
    assert M.PROBE_LABELS[M.PROBE_PIP] in text


def test_93_markdown_marks_failure() -> None:
    report = M.IntegrityReport("gnubg", [_probe(M.PROBE_PIP, ok=False)])
    text = M.build_markdown(report)
    assert "BASARISIZ" in text
    assert "**kaldi**" in text


def test_93_write_json_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "integrity.json"
    M.write_json(M.IntegrityReport("gnubg", [_probe()]), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_93_position_id_takes_the_last_occurrence() -> None:
    text = "Position ID:\tAAAA\nPosition ID:\tBBBB\n"
    assert M._position_id(text) == "BBBB"


def test_93_position_id_returns_none_when_absent() -> None:
    assert M._position_id("no id here") is None


def test_93_parser_defaults() -> None:
    args = M.build_parser().parse_args([])
    assert args.plies == 0
    assert args.timeout == 300
    assert args.json is None
    assert args.markdown is None
    assert args.quiet is False


def test_93_parser_accepts_paths() -> None:
    args = M.build_parser().parse_args(["--json", "a.json", "--markdown", "a.md", "--plies", "2"])
    assert args.json == "a.json"
    assert args.markdown == "a.md"
    assert args.plies == 2


def test_93_main_returns_two_when_gnubg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(G, "find_gnubg", lambda explicit=None: None)
    assert M.main(["--quiet"]) == 2


# ----------------------------------------------------------------------
# Prob 1, 3, 4 -- gercek gnubg
# ----------------------------------------------------------------------


@requires_gnubg
@pytest.mark.slow
def test_93_board_conversion_probe_passes() -> None:
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_board_conversion(session)
    assert result.ok, result.detail
    assert result.evidence["docBoardEquity"] == pytest.approx(1.0, abs=0.02)
    assert result.evidence["startPositionId"] == M.START_POSITION_ID
    assert result.evidence["startPips"] == [167, 167]
    assert result.evidence["barPips"] == [25, 25]


@requires_gnubg
@pytest.mark.slow
def test_93_board_conversion_probe_is_discriminating() -> None:
    """Isaret-ters ve aynalanmis donusumler **farkli** equity vermeli."""
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_board_conversion(session)
    assert result.evidence["signFlippedEquity"] != pytest.approx(1.0, abs=0.02)
    assert result.evidence["mirroredEquity"] != pytest.approx(1.0, abs=0.02)


@requires_gnubg
@pytest.mark.slow
def test_93_perspective_probe_passes() -> None:
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_perspective(session)
    assert result.ok, result.detail
    kinds = {case["kind"] for case in result.evidence["cases"]}
    assert kinds == {"symmetric", "asymmetric"}


@requires_gnubg
@pytest.mark.slow
def test_93_perspective_symmetric_case_is_equal() -> None:
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_perspective(session)
    symmetric = [c for c in result.evidence["cases"] if c["kind"] == "symmetric"]
    assert len(symmetric) == 1
    assert symmetric[0]["delta"] <= M.PERSPECTIVE_TOLERANCE


@requires_gnubg
@pytest.mark.slow
def test_93_perspective_asymmetric_cases_have_opposite_signs() -> None:
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_perspective(session)
    asymmetric = [c for c in result.evidence["cases"] if c["kind"] == "asymmetric"]
    assert asymmetric
    for case in asymmetric:
        assert case["product"] < 0


@requires_gnubg
@pytest.mark.slow
def test_93_pip_probe_passes() -> None:
    session = G.GnubgSession(GNUBG, plies=0, timeout=300)
    result = M.probe_pip_count(session)
    assert result.ok, result.detail
    assert result.evidence["checked"] == M.PIP_SAMPLE
    assert all(case["ok"] for case in result.evidence["cases"])


@requires_gnubg
@pytest.mark.slow
def test_93_run_all_returns_four_probes() -> None:
    report = M.run_all(GNUBG, plies=0, timeout=300)
    assert [p.name for p in report.probes] == list(M.PROBE_NAMES)
    assert report.ok, report.failed


@requires_gnubg
@pytest.mark.slow
def test_93_run_all_raises_without_gnubg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(G, "find_gnubg", lambda explicit=None: None)
    with pytest.raises(M.IntegrityError):
        M.run_all(None)
