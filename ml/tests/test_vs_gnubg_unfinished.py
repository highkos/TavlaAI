"""K5: bitmeyen oyun davranisi (Test 294-297).

K5 kosusunda ``policy`` yolu ``oyun 200 ply'de bitmedi`` hatasiyla dustu:
politika kafasi tek basina donguye girebiliyor. Mac kosusunun tamamen
olmasi yerine bu oyunlar **sayilir ve raporlanir**; varsayilan davranis
hala katidir (sessiz dusme yok, Kural 6).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import vs_gnubg  # noqa: E402


def _stuck_chooser(case):
    """Hic ilerlemeyen secici: her zaman ilk adayi secer."""
    return 0


def test_294_play_game_raises_by_default():
    """Varsayilan kati: bitmeyen oyun hata verir."""
    with pytest.raises(vs_gnubg.MatchError):
        vs_gnubg.play_game(
            dice_seq=[(3, 4)] * 8,
            our_side=1,
            our_choose=_stuck_chooser,
            gnubg_choose=_stuck_chooser,
            max_plies=8,
        )


def test_295_play_game_allow_unfinished():
    """``allow_unfinished`` ile 0 puan ve ``finished=False`` doner."""
    result = vs_gnubg.play_game(
        dice_seq=[(3, 4)] * 8,
        our_side=1,
        our_choose=_stuck_chooser,
        gnubg_choose=_stuck_chooser,
        max_plies=8,
        allow_unfinished=True,
    )
    assert result["finished"] is False
    assert result["score"] == 0.0
    assert result["plies"] == 8


def test_296_play_pair_reports_finished_flags():
    """``_play_pair`` her iki renk icin de bitme bayragini dondurur."""
    scores, plies, finished = vs_gnubg._play_pair(
        (0, 1), _stuck_chooser, _stuck_chooser, 8
    )
    assert len(scores) == len(plies) == len(finished) == 2
    assert finished == [False, False]
    assert scores == [0.0, 0.0]


def test_297_markdown_reports_unfinished():
    """Bitmeyen oyun sayisi markdown'da ayrica gorunur."""
    report = {
        "model": "m.onnx",
        "path": "policy",
        "gnubgPlies": 0,
        "games": 2,
        "pairs": 1,
        "workers": 1,
        "wins": 0,
        "winRate": 0.0,
        "ppg": 0.0,
        "ppgCiLow": 0.0,
        "ppgCiHigh": 0.0,
        "ppgStdError": 0.0,
        "pairedDiffMean": 0.0,
        "pairedDiffCiLow": 0.0,
        "pairedDiffCiHigh": 0.0,
        "meanPlies": 200.0,
        "unfinished": 2,
        "unfinishedRate": 1.0,
    }
    md = vs_gnubg.build_markdown(report)
    assert "Bitmeyen oyun | 2" in md
    assert "**Bitmeyen oyunlar.**" in md
    report["unfinished"] = 0
    report["unfinishedRate"] = 0.0
    assert "**Bitmeyen oyunlar.**" not in vs_gnubg.build_markdown(report)
