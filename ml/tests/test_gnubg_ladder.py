"""Faz 7-R adim 0: gnubg ER merdiveni testleri (Test 199-203).

R-T54 ``Ladder_RefereeCap``      -- hakem kendi kendini olcemez
R-T55 ``Ladder_Unmeasurable``    -- olculemeyen basamak sifir uydurmaz
R-T56 ``Ladder_Markdown``        -- rapor basamaklari ve model satirini tasir
R-T57 ``Ladder_ModelRows``       -- model satirlari er_paths'ten okunur
R-T58 ``Ladder_Cli``             -- CLI sozlesmesi
"""

from __future__ import annotations

import json

import pytest

import gnubg_ladder as L


def test_199_ladder_referee_cannot_measure_itself():
    """``P >= R`` hata vermeli: ER tanim geregi 0 olurdu."""
    with pytest.raises(L.LadderError):
        L.measure_rung(None, None, [], player_plies=2, referee_plies=2)
    with pytest.raises(L.LadderError):
        L.measure_rung(None, None, [], player_plies=3, referee_plies=2)


def test_200_ladder_unmeasurable_rung_has_no_fake_zero():
    rung = L.unmeasurable_rung(2, "hakem kendisi")
    assert rung["measurable"] is False
    assert rung["mean"] is None
    assert rung["ciLow"] is None
    assert rung["count"] == 0
    assert "hakem" in rung["reason"]


def test_201_ladder_markdown_shows_rungs_and_models():
    report = {
        "corpus": "c.json",
        "refereePlies": 2,
        "rungs": [
            {
                "playerPlies": 0,
                "refereePlies": 2,
                "measurable": True,
                "count": 500,
                "mean": 0.0044,
                "ciLow": 0.0032,
                "ciHigh": 0.0058,
                "sigma": 0.01,
                "exactMatchRate": 0.5,
            },
            L.unmeasurable_rung(2, "hakem kendisi"),
        ],
        "models": [
            {
                "label": "policy",
                "count": 500,
                "mean": 0.0402,
                "ciLow": 0.03,
                "ciHigh": 0.05,
                "sigma": 0.06,
            }
        ],
        "notes": ["not"],
    }
    md = L.build_markdown(report)
    assert "gnubg 0-ply" in md
    assert "olculemez" in md
    assert "`policy`" in md
    assert "0.0044" in md


def test_202_ladder_model_rows_reads_er_paths(tmp_path):
    payload = {
        "paths": {
            "policy": {"count": 500, "mean": 0.0402, "ciLow": 0.03, "ciHigh": 0.05, "sigma": 0.06},
            "value": {"count": 500, "mean": 0.0442, "ciLow": 0.03, "ciHigh": 0.06, "sigma": 0.07},
            "broken": {"count": 0},
        }
    }
    path = tmp_path / "er.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rows = L._model_rows(path)
    labels = [r["label"] for r in rows]
    assert labels == ["policy", "value"]
    assert rows[0]["mean"] == pytest.approx(0.0402)
    assert L._model_rows(tmp_path / "missing.json") == []


def test_203_ladder_cli_contract():
    parser = L.build_parser()
    args = parser.parse_args([])
    assert args.cases == L.DEFAULT_CASES
    assert args.player_plies == "0,1"
    assert args.out == L.LADDER_PATH
    assert args.markdown == L.LADDER_MD_PATH
    assert L.REFEREE_PLIES == 2
