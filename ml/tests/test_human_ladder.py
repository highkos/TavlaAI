"""Faz 7 Bolum 4.4 - insan karsilastirma merdiveni testleri (Test 94).

Merdivenin **durustluk kurali** test edilir: 5. ve 6. basamak asla "olculmus"
gibi raporlanmamali, ve merdiven "sampiyon olduk" cumlesi kurmamali.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gnubg_er
import human_ladder as hl


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------


def test_referee_plies_is_three() -> None:
    assert hl.REFEREE_PLIES == 3


def test_measured_and_literature_rungs() -> None:
    assert hl.MEASURED_RUNGS == (0, 1, 2)
    assert hl.SELF_RUNG == 3
    assert hl.UNMEASURED_RUNGS == (4,)
    assert hl.LITERATURE_RUNGS == (5, 6)
    assert not set(hl.MEASURED_RUNGS) & set(hl.LITERATURE_RUNGS)


def test_rung_labels_cover_every_rung() -> None:
    every = (
        set(hl.MEASURED_RUNGS)
        | {hl.SELF_RUNG}
        | set(hl.UNMEASURED_RUNGS)
        | set(hl.LITERATURE_RUNGS)
    )
    assert set(hl.RUNG_LABELS) == every
    assert len(hl.RUNG_LABELS) == 7


def test_unmeasured_note_cites_evidence() -> None:
    assert "f6-040" in hl.UNMEASURED_NOTE
    assert "900 s" in hl.UNMEASURED_NOTE
    assert "F7-07" in hl.UNMEASURED_NOTE


def test_literature_er_values() -> None:
    assert hl.LITERATURE_ER == {5: 0.0025, 6: 0.003}


def test_literature_note_mentions_literature() -> None:
    assert "literature" in hl.LITERATURE_NOTE
    assert "olcumumuz degildir" in hl.LITERATURE_NOTE


def test_champion_target_is_five_thousandths() -> None:
    assert hl.CHAMPION_ER_TARGET == 0.005


# ---------------------------------------------------------------------------
# _loss
# ---------------------------------------------------------------------------


def test_loss_when_choice_is_listed() -> None:
    result = hl._loss(3, {3: 0.20, 5: 0.10}, best=0.25, worst=0.10)
    assert result["loss"] == pytest.approx(0.05)
    assert result["censored"] is False
    assert result["lowerBound"] == 0.0


def test_loss_when_choice_is_missing_is_censored() -> None:
    result = hl._loss(9, {3: 0.20, 5: 0.10}, best=0.25, worst=0.10)
    assert result["censored"] is True
    assert result["loss"] == pytest.approx(0.15)
    assert result["lowerBound"] == pytest.approx(0.15)


def test_loss_never_negative() -> None:
    result = hl._loss(3, {3: 0.30}, best=0.25, worst=0.10)
    assert result["loss"] == 0.0


def test_loss_missing_never_negative() -> None:
    result = hl._loss(9, {3: 0.30}, best=0.25, worst=0.30)
    assert result["loss"] == 0.0


# ---------------------------------------------------------------------------
# summarize_rung
# ---------------------------------------------------------------------------


def test_summarize_rung_statistics() -> None:
    losses = [0.0, 0.1, 0.2, 0.3]
    summary = hl.summarize_rung(2, losses, [False] * 4)
    assert summary.n == 4
    assert summary.covered == 4
    assert summary.censored == 0
    assert summary.coverage == 1.0
    assert summary.mean == pytest.approx(0.15)
    assert summary.sigma == pytest.approx(0.129099, abs=1e-6)
    assert summary.standard_error == pytest.approx(0.06455, abs=1e-5)
    assert summary.ci_low < summary.mean < summary.ci_high


def test_summarize_rung_counts_censored() -> None:
    summary = hl.summarize_rung(1, [0.0, 0.2, 0.4], [False, True, True])
    assert summary.censored == 2
    assert summary.covered == 1
    assert summary.coverage == pytest.approx(1 / 3)


def test_summarize_rung_empty() -> None:
    summary = hl.summarize_rung(0, [], [])
    assert summary.n == 0
    assert summary.mean == 0.0
    assert summary.coverage == 0.0


def test_summarize_rung_single_sample_has_zero_sigma() -> None:
    summary = hl.summarize_rung(0, [0.1], [False])
    assert summary.sigma == 0.0
    assert summary.standard_error == 0.0


def test_summarize_rung_self_rung_is_labelled() -> None:
    summary = hl.summarize_rung(hl.SELF_RUNG, [0.0, 0.0], [False, False])
    assert summary.source == "self"
    assert "olcum degildir" in summary.note


def test_summarize_rung_measured_source() -> None:
    for rung in hl.MEASURED_RUNGS:
        assert hl.summarize_rung(rung, [0.0, 0.1], [False, False]).source == "measured"


def test_unmeasured_rung_has_no_numbers() -> None:
    summary = hl.unmeasured_rung(4)
    assert summary.source == "unmeasured"
    assert summary.n == 0
    assert summary.mean == 0.0
    assert summary.plies is None
    assert "f6-040" in summary.note


def test_rung_summary_to_dict_keys() -> None:
    payload = hl.summarize_rung(1, [0.0, 0.1], [False, False]).to_dict()
    assert set(payload) == {
        "rung",
        "label",
        "source",
        "plies",
        "n",
        "covered",
        "censored",
        "coverage",
        "mean",
        "meanLowerBound",
        "sigma",
        "standardError",
        "ciLow",
        "ciHigh",
        "note",
    }


# ---------------------------------------------------------------------------
# Literatur basamaklari
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rung", hl.LITERATURE_RUNGS)
def test_literature_rung_is_labelled(rung: int) -> None:
    summary = hl.literature_rung(rung)
    assert summary.source == "literature"
    assert summary.plies is None
    assert summary.n == 0
    assert summary.mean == hl.LITERATURE_ER[rung]
    assert "literature" in summary.note


def test_literature_rung_is_never_measured() -> None:
    for rung in hl.LITERATURE_RUNGS:
        assert hl.literature_rung(rung).source != "measured"


# ---------------------------------------------------------------------------
# Karar
# ---------------------------------------------------------------------------


def _rungs(deepest_losses, censored=None):
    censored = censored or [False] * len(deepest_losses)
    rungs = [hl.summarize_rung(r, [0.0] * len(deepest_losses), censored) for r in (0, 1)]
    rungs.append(hl.summarize_rung(2, deepest_losses, censored))
    rungs.append(hl.summarize_rung(hl.SELF_RUNG, [0.0] * len(deepest_losses), censored))
    rungs.extend(hl.unmeasured_rung(r) for r in hl.UNMEASURED_RUNGS)
    rungs.extend(hl.literature_rung(r) for r in hl.LITERATURE_RUNGS)
    return rungs


def test_verdict_rejects_single_sample() -> None:
    verdict = hl.ladder_verdict(_rungs([0.1]))
    assert verdict["usable"] is False
    assert verdict["state"] == "not_proven"
    assert "n < 2" in verdict["sentence"]


def test_verdict_rejects_zero_sigma() -> None:
    verdict = hl.ladder_verdict(_rungs([0.0, 0.0, 0.0]))
    assert verdict["usable"] is False
    assert "sigma = 0" in verdict["sentence"]


def test_verdict_accepts_spread() -> None:
    verdict = hl.ladder_verdict(_rungs([0.0, 0.1, 0.2, 0.3]))
    assert verdict["usable"] is True
    assert verdict["state"] == "measured"
    assert "Merdiven olculdu" in verdict["sentence"]


def test_verdict_never_claims_championship() -> None:
    for losses in ([0.0], [0.0, 0.0], [0.0, 0.1, 0.2, 0.3]):
        sentence = hl.ladder_verdict(_rungs(losses))["sentence"]
        assert "sampiyon olduk" not in sentence.lower()
        assert "reached" not in hl.ladder_verdict(_rungs(losses))


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------


def _report() -> dict:
    rungs = _rungs([0.0, 0.1, 0.2, 0.3])
    return {
        "schemaVersion": hl.SCHEMA_VERSION,
        "refereePlies": hl.REFEREE_PLIES,
        "methodNote": "test",
        "count": 4,
        "skippedCount": 0,
        "skipped": [],
        "elapsedSeconds": 10.0,
        "secondsPerPosition": 2.5,
        "rungs": [rung.to_dict() for rung in rungs],
        "verdict": hl.ladder_verdict(rungs),
        "positions": [],
    }


def test_build_markdown_lists_every_rung() -> None:
    text = hl.build_markdown(_report())
    for rung in hl.RUNG_LABELS.values():
        assert rung in text


def test_build_markdown_marks_literature() -> None:
    text = hl.build_markdown(_report())
    assert "**literatur**" in text
    assert "**olculmedi**" in text


def test_write_json_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "ladder.json"
    hl.write_json(_report(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["refereePlies"] == hl.REFEREE_PLIES
    assert len(data["rungs"]) == 7


# ---------------------------------------------------------------------------
# Vaka yukleme ve CLI
# ---------------------------------------------------------------------------


def test_load_cases_all() -> None:
    cases = hl.load_cases(hl.DEFAULT_CASES)
    assert len(cases) == 200


def test_load_cases_split() -> None:
    cases = hl.load_cases(hl.DEFAULT_CASES, "cal")
    assert len(cases) == 60


def test_load_cases_unknown_split_raises() -> None:
    with pytest.raises(hl.LadderError):
        hl.load_cases(hl.DEFAULT_CASES, "nope")


def test_load_cases_empty_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"cases": []}), encoding="utf-8")
    with pytest.raises(hl.LadderError):
        hl.load_cases(path)


def test_measure_rejects_empty_cases() -> None:
    with pytest.raises(hl.LadderError):
        hl.measure([], gnubg=Path("gnubg"))


def test_parser_defaults() -> None:
    args = hl.build_parser().parse_args([])
    assert args.limit == hl.DEFAULT_LIMIT
    assert args.offset == 0
    assert args.split == "all"
    assert args.cases == hl.DEFAULT_CASES


def test_main_without_gnubg_returns_two(monkeypatch, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: None)
    assert hl.main([]) == 2
    assert "gnubg-cli bulunamadi" in capsys.readouterr().err


def test_main_missing_cases_returns_two(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: Path("gnubg"))
    assert hl.main(["--cases", str(tmp_path / "nope.json")]) == 2
    assert "HATA" in capsys.readouterr().err
