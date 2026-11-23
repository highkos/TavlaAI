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

def test_322_ladder_marks_two_three_four_ply_unmeasurable():
    """R-F madde 1: 2/3/4-ply satirlari sifir uydurmadan isaretlenir."""
    assert L.UNMEASURABLE_PLIES == (2, 3, 4)
    for plies in L.UNMEASURABLE_PLIES:
        reason = L._UNMEASURABLE_REASONS[plies]
        assert reason.strip()
        rung = L.unmeasurable_rung(plies, reason)
        assert rung["playerPlies"] == plies
        assert rung["measurable"] is False
        assert rung["mean"] is None
        assert rung["ciLow"] is None
        assert rung["ciHigh"] is None
        assert rung["count"] == 0
        assert rung["reason"] == reason


def test_323_ladder_markdown_lists_all_unmeasurable_rows():
    report = {
        "corpus": "c.json",
        "refereePlies": 2,
        "rungs": [L.unmeasurable_rung(p, L._UNMEASURABLE_REASONS[p]) for p in L.UNMEASURABLE_PLIES],
        "models": [],
        "notes": [],
    }
    md = L.build_markdown(report)
    for plies in L.UNMEASURABLE_PLIES:
        assert "| gnubg %d-ply | - | **olculemez** | - | - | - |" % plies in md
    assert "2/3/4-ply" in md


def test_324_ladder_model_rows_supports_multiple_models(tmp_path):
    payload = {
        "paths": {
            "policy": {"count": 300, "mean": 0.0124, "ciLow": 0.011, "ciHigh": 0.014, "sigma": 0.02},
        }
    }
    path = tmp_path / "er_paths.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rows = L._model_rows(path, "rd/large/seed0:")
    assert rows[0]["label"] == "rd/large/seed0:policy"
    assert L._model_label(path) == "er_paths"
    nested = tmp_path / "runs" / "capacity_rd" / "large" / "seed0" / "er_paths.json"
    assert L._model_label(nested) == "capacity_rd/large/seed0"

def test_325_deep_ladder_rejects_shallow_referee_and_self_measurement():
    """R-F madde 1: derin hakem >= 3-ply olmali; oyuncu hakemden sig olmali."""
    with pytest.raises(L.LadderError):
        L.measure_deep_ladder(None, [], referee_plies=2, player_plies=(0, 1))
    with pytest.raises(L.LadderError):
        L.measure_deep_ladder(None, [], referee_plies=4, player_plies=(0, 4))
    with pytest.raises(L.LadderError):
        L.measure_deep_ladder(None, [], referee_plies=4, player_plies=(0, 5))


def test_326_deep_ladder_markdown_reports_coverage_and_floor():
    report = {
        "refereePlies": 4,
        "referee": "hint",
        "positions": 100,
        "mappingFailures": 0,
        "methodNote": "yontem",
        "rungs": [
            {
                "playerPlies": 2,
                "refereePlies": 4,
                "referee": "hint",
                "measurable": True,
                "count": 98,
                "skipped": 0,
                "censored": 2,
                "coverage": 0.98,
                "mean": 0.0031,
                "ciLow": 0.0022,
                "ciHigh": 0.0041,
                "sigma": 0.005,
                "exactMatchRate": 0.61,
            },
            {
                "playerPlies": 3,
                "refereePlies": 4,
                "referee": "hint",
                "measurable": True,
                "count": 0,
                "skipped": 0,
                "censored": 100,
                "coverage": 0.0,
                "mean": None,
                "ciLow": None,
                "ciHigh": None,
                "sigma": None,
                "exactMatchRate": 0.0,
            },
        ],
    }
    md = L.build_deep_markdown(report)
    assert "4-ply `hint`" in md
    assert "0.0031" in md
    assert "98.0%" in md
    assert "olculemez" in md
    assert "ER cozunurluk tabani" in md


def test_327_deep_ladder_cli_defaults():
    parser = L.build_parser()
    args = parser.parse_args(["--deep"])
    assert args.deep is True
    assert args.deep_referee_plies == L.DEEP_REFEREE_PLIES == 4
    assert args.deep_player_plies == "0,1,2,3"
    assert args.deep_limit == L.DEEP_DEFAULT_LIMIT
    assert args.deep_out == L.DEEP_LADDER_PATH
    assert args.deep_markdown == L.DEEP_LADDER_MD_PATH
    assert L.DEEP_REFEREE_PLIES >= L.gnubg_hint.HINT_REFEREE_MIN_PLIES

def test_332_models_only_refreshes_rows_without_measuring(tmp_path, monkeypatch):
    """``--models-only`` gnubg'ye hic dokunmadan model satirlarini tazeler."""
    out = tmp_path / "ladder.json"
    md = tmp_path / "ladder.md"
    out.write_text(
        json.dumps(
            {
                "ladderVersion": L.LADDER_VERSION,
                "corpus": "c.json",
                "refereePlies": 2,
                "rungs": [
                    {
                        "playerPlies": 0,
                        "refereePlies": 2,
                        "measurable": True,
                        "count": 300,
                        "skipped": 0,
                        "mean": 0.0062,
                        "ciLow": 0.0040,
                        "ciHigh": 0.0088,
                        "sigma": 0.0212,
                        "exactMatchRate": 0.8067,
                    }
                ],
                "models": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    er = tmp_path / "er_paths.json"
    er.write_text(
        json.dumps({"paths": {"policy": {"count": 300, "mean": 0.0111}}}),
        encoding="utf-8",
    )

    def _boom(*_a, **_k):
        raise AssertionError("models-only gnubg olcumu yapmamali")

    monkeypatch.setattr(L.gnubg_er, "GnubgSession", _boom)
    monkeypatch.setattr(L.gnubg_er, "find_gnubg", _boom)

    rc = L.main(
        [
            "--models-only",
            "--model-er",
            str(er),
            "--out",
            str(out),
            "--markdown",
            str(md),
        ]
    )
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert [m["label"] for m in report["models"]] == ["policy"]
    assert report["models"][0]["mean"] == 0.0111
    assert report["rungs"][0]["mean"] == 0.0062
    assert "0.0111" in md.read_text(encoding="utf-8")
