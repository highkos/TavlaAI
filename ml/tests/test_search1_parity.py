"""Faz 7-R adim 0 madde 4: C#/Python ``search1`` paritesi testleri (Test 176-181)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import search1_parity as sp  # noqa: E402


def _case(name: str = "c0") -> dict:
    board = [0] * 26
    board[24] = 15
    board[1] = -15
    return {
        "name": name,
        "board": board,
        "turn": 1,
        "whiteOff": 0,
        "blackOff": 0,
        "dice": [3, 1],
        "afterStates": [
            {"board": board, "whiteOff": 0, "blackOff": 0},
            {"board": board, "whiteOff": 1, "blackOff": 0},
        ],
    }


def test_176_parity_build_cs_corpus_omits_phase(tmp_path):
    path = tmp_path / "cs.json"
    sp.build_cs_corpus([_case()], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["count"] == 1
    case = data["cases"][0]
    # ``phase`` yazilmaz: StateFromJson onu GamePhase olarak cozer ve
    # korpustaki contact/bar/race degerlerini reddeder.
    assert "phase" not in case
    assert case["dice"] == [3, 1]
    assert len(case["board"]) == 26
    assert "afterStates" not in case


def test_177_parity_compare_case_agree():
    case = _case()
    keys = [
        sp._key(a["board"], a["whiteOff"], a["blackOff"]) for a in case["afterStates"]
    ]
    cs_case = {
        "bestIndex": 1,
        "candidates": [
            {
                "index": 0,
                "score": -0.10,
                "board": case["afterStates"][0]["board"],
                "whiteOff": 0,
                "blackOff": 0,
            },
            {
                "index": 1,
                "score": -0.10,
                "board": case["afterStates"][1]["board"],
                "whiteOff": 1,
                "blackOff": 0,
            },
        ],
    }

    class _Scorer:
        def values(self, vectors):  # noqa: D401 - test double
            # ``search1_values`` isareti cevirir: -0,10 dondurur.
            return [0.10] * len(vectors)

    # Python tarafi 0. adayi secer (esitlikte ilk); C# 1. adayi secmis.
    result = sp.compare_case(case, cs_case, _Scorer())
    assert result.candidates == 2
    assert result.matched == 2
    assert result.score_mae == pytest.approx(0.0, abs=1e-9)
    assert result.cs_best == str(keys[1])
    assert result.py_best == str(keys[0])
    assert result.argmax_agree is False


def test_178_parity_report_gate():
    report = sp.ParityReport(depth=1, model="m", corpus="c")
    report.cases = [
        sp.CaseParity("a", 2, 2, True, 0.01, 0.02, "x", "x", top2_gap=0.5),
        sp.CaseParity("b", 2, 2, True, 0.01, 0.02, "x", "x", top2_gap=0.5),
    ]
    assert report.count == 2
    assert report.agree == 2
    assert report.agree_rate == pytest.approx(1.0)
    assert report.argmax_ok is True
    assert report.score_ok is True
    assert report.passed is True

    report.cases[1] = sp.CaseParity(
        "b", 2, 2, False, 0.01, 0.02, "x", "y", top2_gap=0.5
    )
    assert report.agree_rate == pytest.approx(0.5)
    assert report.argmax_ok is False
    assert report.passed is False


def test_179_parity_report_score_gate():
    report = sp.ParityReport(depth=1, model="m", corpus="c")
    report.cases = [
        sp.CaseParity("a", 2, 2, True, 0.50, 0.60, "x", "x", top2_gap=0.5)
    ]
    assert report.argmax_ok is True
    assert report.score_ok is False
    assert report.passed is False


def test_180_parity_markdown():
    report = sp.ParityReport(depth=1, model="m.onnx", corpus="c.json")
    report.cases = [
        sp.CaseParity("a", 2, 2, True, 0.01, 0.02, "x", "x", top2_gap=0.5)
    ]
    report.notes.append("not-1")
    text = sp.build_markdown(report)
    assert "search1" in text
    assert "Argmax uyusmasi" in text
    assert "Skor MAE" in text
    assert "GECTI" in text
    assert "not-1" in text
    # Turkce ondalik virgul kullanilmaz: bu rapor nokta ile yazar.
    assert "0.0100" in text


def test_181_parity_to_dict():
    report = sp.ParityReport(depth=1, model="m", corpus="c")
    report.cases = [
        sp.CaseParity("a", 2, 2, True, 0.01, 0.02, "x", "x", top2_gap=0.5)
    ]
    data = report.to_dict()
    assert data["parityVersion"] == sp.PARITY_VERSION
    assert data["count"] == 1
    assert data["argmaxAgree"] == 1
    assert data["passed"] is True
    assert data["cases"][0]["name"] == "a"
    assert np.isfinite(data["argmaxCiLow"])
