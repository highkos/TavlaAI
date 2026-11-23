"""Faz 7-R R-F madde 2: gnubg rollout hakemi testleri (Test 328-330).

R-T20 ``Rollout_Unmeasurable``  -- sonuc yoksa sifir uydurulmaz
R-T21 ``Rollout_Parse``         -- equity satiri ayristirilir
R-T22 ``Rollout_Report``        -- rapor gerekceyi ve yerine koyulan olcumu tasir
"""

from __future__ import annotations

import gnubg_rollout as R


def test_328_rollout_equity_is_none_without_result():
    """Olculen durum: ``Rollout done`` var, equity yok -> ``None``."""
    text = (
        "36 games will be played per rollout.\n"
        "Rollout done. Printing final results.\n"
        "The pip counts are: MONSTER 180, gnubg 155.\n"
    )
    assert R.parse_rollout_equity(text) is None
    assert R.parse_rollout_equity("nothing here") is None


def test_329_rollout_equity_parses_when_present():
    text = (
        "Rollout done. Printing final results.\n"
        "\n"
        "Cubeless equity: +0,123\n"
        "  0,500 0,100 0,010 - 0,500 0,100 0,010\n"
    )
    assert R.parse_rollout_equity(text) == 0.123


def test_330_rollout_report_marks_unmeasurable_and_names_substitute():
    probe = {
        "gnubg": "gnubg-cli.exe",
        "trials": 36,
        "doneMarkerSeen": True,
        "equity": None,
        "measurable": False,
        "reason": R.UNMEASURABLE_REASON,
    }
    report = R.build_report(probe, positions=200, candidates=2)
    assert report["measurable"] is False
    assert report["requiredTrials"] == 1296
    assert report["reason"] == R.UNMEASURABLE_REASON
    assert "gnubg_ladder.py --deep" in report["substitute"]["module"]
    md = R.build_markdown(report)
    assert "olculemez" in md
    assert "Gerekce" in md
    assert "gnubg_ladder.py --deep" in md
    assert "1296" in md


def test_331_rollout_cli_defaults():
    parser = R.build_parser()
    args = parser.parse_args([])
    assert args.trials == 36
    assert args.positions == 200
    assert args.candidates == 2
    assert args.out == R.ROLLOUT_PATH
    assert args.markdown == R.ROLLOUT_MD_PATH
