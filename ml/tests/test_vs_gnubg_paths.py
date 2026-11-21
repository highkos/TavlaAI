"""K5: ``vs_gnubg`` oyun yollari (Test 284-286).

K5 "politika-argmax **ve** deger-0-ply oyununun ppg'sini olc" diyor. ``value``
yolu ``er_paths.PLAY_PATHS`` icinde vardi ama ``vs_gnubg.OUR_PATHS`` icinde
yoktu, yani ER'si olculuyor ama ppg'si olculemiyordu. Bu testler iki listenin
ayni kaldigini ve dagitim tablosunun her yolu dogru fonksiyona bagladigini
kilitler.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import er_paths  # noqa: E402
import vs_gnubg  # noqa: E402


def test_284_vs_gnubg_paths_match_er_paths():
    """Iki yol listesi ayni kume olmali (K5: value yolu ppg'de de olculebilsin)."""
    assert set(vs_gnubg.OUR_PATHS) == set(er_paths.PLAY_PATHS)
    assert "value" in vs_gnubg.OUR_PATHS
    assert "policy" in vs_gnubg.OUR_PATHS
    assert "search1" in vs_gnubg.OUR_PATHS


def test_285_vs_gnubg_chooser_dispatch(monkeypatch):
    """Her yol kendi ``er_paths`` fonksiyonuna baglanir; karismaz."""
    calls: list[str] = []

    def fake_policy(scorer, case):
        calls.append("policy")
        return 0

    def fake_value(scorer, case):
        calls.append("value")
        return 1

    def fake_search1(scorer, case):
        calls.append("search1")
        return (2, 0)

    monkeypatch.setattr(er_paths, "choose_policy", fake_policy)
    monkeypatch.setattr(er_paths, "choose_value", fake_value)
    monkeypatch.setattr(er_paths, "choose_search1", fake_search1)

    case = {"turn": 1, "afterStates": []}
    assert vs_gnubg._our_chooser(object(), "policy")(case) == 0
    assert vs_gnubg._our_chooser(object(), "value")(case) == 1
    assert vs_gnubg._our_chooser(object(), "search1")(case) == 2
    assert calls == ["policy", "value", "search1"]


def test_286_vs_gnubg_chooser_rejects_unknown():
    """Bilinmeyen yol sessizce dusmez (Kural 6)."""
    with pytest.raises(vs_gnubg.MatchError):
        vs_gnubg._our_chooser(object(), "value2")
