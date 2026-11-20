"""Faz 7-R adim 0: Python-C# hamle kumesi esitligi testleri (Test 188-192).

R-T59 ``MoveSet_Equal``        -- ayni kume esit sayilir
R-T60 ``MoveSet_Mismatch``     -- eksik/fazla aday yakalanir
R-T61 ``MoveSet_ReportGate``   -- kapi ve GA
R-T62 ``MoveSet_Markdown``     -- uyusmazlik tablosu
R-T63 ``MoveSet_Cli``          -- CLI sozlesmesi
"""

from __future__ import annotations

import pytest

import moveset_parity as M


def _case(name="c1", turn=1, dice=(3, 5)):
    return {
        "name": name,
        "board": list(M.refgen.START_BOARD),
        "turn": turn,
        "dice": list(dice),
        "whiteOff": 0,
        "blackOff": 0,
    }


def _cs_from_python(case):
    """Python kumesini C# ciktisi gibi paketler (esitlik icin)."""
    dice = case["dice"]
    expanded = [dice[0]] * 4 if dice[0] == dice[1] else list(dice)
    _ms, states = M.refgen.legal_after_states(
        case["board"], case["turn"], expanded, case["whiteOff"], case["blackOff"]
    )
    return {
        "name": case["name"],
        "afterStates": [
            {"board": list(b), "whiteOff": w, "blackOff": k} for (b, w, k) in states
        ],
    }


def test_188_moveset_equal_sets_agree():
    case = _case()
    result = M.compare_case(case, _cs_from_python(case))
    assert result["equal"] is True
    assert result["onlyPy"] == 0
    assert result["onlyCs"] == 0
    assert result["pyCount"] > 0


def test_189_moveset_mismatch_detected():
    case = _case()
    cs = _cs_from_python(case)
    cs["afterStates"] = cs["afterStates"][:-1]
    result = M.compare_case(case, cs)
    assert result["equal"] is False
    assert result["onlyPy"] >= 1
    assert result["onlyCs"] == 0


def test_190_moveset_report_gate_and_ci():
    report = M.MoveSetReport(corpus="c.json")
    report.cases = [
        {"name": "a", "equal": True, "dice": [1, 2], "pyCount": 1, "csCount": 1, "onlyPy": 0, "onlyCs": 0},
        {"name": "b", "equal": True, "dice": [1, 2], "pyCount": 1, "csCount": 1, "onlyPy": 0, "onlyCs": 0},
    ]
    assert report.rate == pytest.approx(1.0)
    assert report.passed is True
    low, high = report.ci
    assert low == pytest.approx(1.0)
    assert high == pytest.approx(1.0)

    report.cases.append(
        {"name": "c", "equal": False, "dice": [1, 2], "pyCount": 2, "csCount": 1, "onlyPy": 1, "onlyCs": 0}
    )
    assert report.rate == pytest.approx(2 / 3)
    assert report.passed is False
    payload = report.to_dict()
    assert payload["passed"] is False
    assert len(payload["mismatches"]) == 1


def test_191_moveset_markdown_lists_mismatches():
    report = M.MoveSetReport(corpus="c.json")
    report.cases = [
        {"name": "ok", "equal": True, "dice": [1, 2], "pyCount": 1, "csCount": 1, "onlyPy": 0, "onlyCs": 0},
        {"name": "bad", "equal": False, "dice": [3, 4], "pyCount": 2, "csCount": 1, "onlyPy": 1, "onlyCs": 0},
    ]
    md = M.build_markdown(report)
    assert "Kume esitligi" in md
    assert "`bad`" in md
    assert "DUSTU" in md


def test_192_moveset_cli_contract():
    parser = M.build_parser()
    args = parser.parse_args(["--cs", "cs.json"])
    assert args.cs == "cs.json"
    assert args.cases == M.DEFAULT_CASES
    assert args.out == M.MOVESET_PATH
    assert args.markdown == M.MOVESET_MD_PATH
    with pytest.raises(SystemExit):
        parser.parse_args([])
