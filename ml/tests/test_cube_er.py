"""Faz 7-R Asama R-C ek: kup karari ER'si testleri (Test 139-147).

R-T23 ``CubeParse_RealOutput``      -- gercek gnubg ciktisi ayristirilir
R-T24 ``CubeParse_RankedOrder``     -- satirlar **siralanmis**; numaraya guvenilmez
R-T25 ``CubeParse_Redouble``        -- "No redouble" / "Redouble, ..." taninir
R-T26 ``CubeParse_TooGood``         -- "Too good to (re)double, pass" => no-double
R-T27 ``CubeValue_MinNotMax``       -- ciftleme degeri = min(pass, take), max DEGIL
R-T28 ``CubeLoss_NonNegative``      -- kayip >= 0 ve en iyi eylemde 0
R-T29 ``CubeSummary_Bootstrap``     -- GA nokta tahminini icerir, n ve sigma tutarli
R-T30 ``CubePower_SigmaUpper``      -- gereken n sigma'nin UST sinirindan (Kural 4)
R-T31 ``CubeCorpus_CrossProduct``   -- caprazlama + goreli kup sahipligi
R-T32 ``CubeCorpus_NoCrawford``     -- Crawford baglami ER'ye girmez
R-T33 ``CubeCorpus_PhaseKey``       -- ``phase`` C# ``GamePhase`` ile cakismaz
"""

from __future__ import annotations

import math

import pytest

import cube_er as ce


#: Gercek gnubg 1.08 ciktisi (para oyunu, 2-ply, cubeful).
REAL_NO_DOUBLE = """
Cube analysis
2-ply cubeless equity +0,076
  0,525 0,150 0,007 - 0,475 0,125 0,005
Cubeful equities:
1. No double           +0,098
2. Double, pass        +1,000  (+0,902)
3. Double, take        -0,171  (-0,269)
Proper cube action: No double, beaver (23,0%)
"""

#: Ayni pozisyon, en iyi eylem "Double, take" => satirlar SIRALANMIS.
REAL_DOUBLE_TAKE = """
Cube analysis
2-ply cubeless equity +0,221 (Money: +0,270)
  0,592 0,199 0,011 - 0,408 0,121 0,004
Cubeful equities:
1. Double, take        +0,632
2. Double, pass        +1,000  (+0,368)
3. No double           +0,598  (-0,034)
Proper cube action: Double, take
"""

REAL_REDOUBLE = """
Cube analysis
2-ply cubeless equity +0,310
  0,650 0,120 0,004 - 0,350 0,090 0,002
Cubeful equities:
1. No redouble         +0,412
2. Redouble, pass      +1,000  (+0,588)
3. Redouble, take      +0,180  (-0,232)
Proper cube action: No redouble, take (26,5%)
"""

REAL_TOO_GOOD = """
Cube analysis
2-ply cubeless equity +0,880
  0,940 0,300 0,020 - 0,060 0,010 0,000
Cubeful equities:
1. No redouble         +0,905
2. Redouble, pass      +1,000  (+0,095)
3. Redouble, take      +0,760  (-0,145)
Proper cube action: Too good to redouble, pass (25,4%)
"""


# ----------------------------------------------------------------------
# Test 139 -- R-T23: gercek cikti
# ----------------------------------------------------------------------


def test_139_parses_real_no_double_output() -> None:
    a = ce.parse_cube_analysis(REAL_NO_DOUBLE)
    assert a["action"] == ce.ACTION_NO_DOUBLE
    assert a["take"] is None
    assert a["noDouble"] == pytest.approx(0.098)
    assert a["doublePass"] == pytest.approx(1.0)
    assert a["doubleTake"] == pytest.approx(-0.171)
    assert a["cubelessEquity"] == pytest.approx(0.076)
    assert a["beaver"] is True
    assert a["beaverPct"] == pytest.approx(23.0)


def test_139_missing_block_raises() -> None:
    with pytest.raises(ce.CubeErError):
        ce.parse_cube_analysis("no cube analysis here")


def test_139_missing_equity_lines_raise() -> None:
    with pytest.raises(ce.CubeErError):
        ce.parse_cube_analysis("Cube analysis\nProper cube action: No double\n")


# ----------------------------------------------------------------------
# Test 140 -- R-T24: sirali satirlar
# ----------------------------------------------------------------------


def test_140_ranked_order_is_parsed_by_label() -> None:
    """F7-73: gnubg satirlari **siralar**; 1/2/3 numarasi sabit degil."""
    a = ce.parse_cube_analysis(REAL_DOUBLE_TAKE)
    assert a["action"] == ce.ACTION_DOUBLE
    assert a["take"] is True
    assert a["noDouble"] == pytest.approx(0.598)
    assert a["doublePass"] == pytest.approx(1.0)
    assert a["doubleTake"] == pytest.approx(0.632)


def test_140_proper_line_does_not_leak_into_equities() -> None:
    """``Proper cube action: Double, take`` equity satiri sanilmamali."""
    a = ce.parse_cube_analysis(REAL_DOUBLE_TAKE)
    assert a["doubleTake"] == pytest.approx(0.632)
    assert a["doubleTake"] != pytest.approx(1.0)


# ----------------------------------------------------------------------
# Test 141 -- R-T25: redouble
# ----------------------------------------------------------------------


def test_141_no_redouble_is_no_double() -> None:
    a = ce.parse_cube_analysis(REAL_REDOUBLE)
    assert a["action"] == ce.ACTION_NO_DOUBLE
    assert a["noDouble"] == pytest.approx(0.412)
    assert a["doublePass"] == pytest.approx(1.0)
    assert a["doubleTake"] == pytest.approx(0.180)


def test_141_redouble_take_is_double() -> None:
    parsed = ce.normalize_action("Redouble, take")
    assert parsed["action"] == ce.ACTION_DOUBLE
    assert parsed["take"] is True


def test_141_redouble_pass_is_double() -> None:
    parsed = ce.normalize_action("Redouble, pass")
    assert parsed["action"] == ce.ACTION_DOUBLE
    assert parsed["take"] is False


# ----------------------------------------------------------------------
# Test 142 -- R-T26: too good
# ----------------------------------------------------------------------


def test_142_too_good_to_redouble_is_no_double() -> None:
    a = ce.parse_cube_analysis(REAL_TOO_GOOD)
    assert a["action"] == ce.ACTION_NO_DOUBLE
    assert a["take"] is None


def test_142_too_good_to_double_is_no_double() -> None:
    parsed = ce.normalize_action("Too good to double, pass")
    assert parsed["action"] == ce.ACTION_NO_DOUBLE


def test_142_unknown_action_raises() -> None:
    with pytest.raises(ce.CubeErError):
        ce.normalize_action("Something else entirely")


# ----------------------------------------------------------------------
# Test 143 -- R-T27: min, max degil
# ----------------------------------------------------------------------


def test_143_double_value_is_min_of_pass_and_take() -> None:
    """Rakip bizim equity'mizi **minimize** eder; ``max`` yanlistir."""
    a = ce.parse_cube_analysis(REAL_NO_DOUBLE)
    assert ce.double_value(a) == pytest.approx(-0.171)


def test_143_max_would_pick_the_pass_line() -> None:
    """Eski ``max`` hatasi: ``doublePass`` her zaman 1,000 oldugu icin kazanir."""
    a = ce.parse_cube_analysis(REAL_NO_DOUBLE)
    assert max(a["noDouble"], a["doublePass"], a["doubleTake"]) == pytest.approx(1.0)
    assert ce.best_value(a) == pytest.approx(0.098)


def test_143_best_action_matches_gnubg() -> None:
    assert ce.best_action(ce.parse_cube_analysis(REAL_NO_DOUBLE)) == ce.ACTION_NO_DOUBLE
    assert ce.best_action(ce.parse_cube_analysis(REAL_DOUBLE_TAKE)) == ce.ACTION_DOUBLE


# ----------------------------------------------------------------------
# Test 144 -- R-T28: kayip negatif olamaz
# ----------------------------------------------------------------------


def test_144_loss_is_zero_at_the_best_action() -> None:
    for text in (REAL_NO_DOUBLE, REAL_DOUBLE_TAKE, REAL_REDOUBLE, REAL_TOO_GOOD):
        a = ce.parse_cube_analysis(text)
        assert ce.cube_loss(a, ce.best_action(a)) == pytest.approx(0.0)


def test_144_loss_is_positive_at_the_wrong_action() -> None:
    a = ce.parse_cube_analysis(REAL_NO_DOUBLE)
    assert ce.cube_loss(a, ce.ACTION_DOUBLE) == pytest.approx(0.098 - (-0.171))


def test_144_loss_never_negative() -> None:
    a = ce.parse_cube_analysis(REAL_DOUBLE_TAKE)
    for action in ce.ACTIONS:
        assert ce.cube_loss(a, action) >= 0.0


# ----------------------------------------------------------------------
# Test 145 -- R-T29: ozet + bootstrap
# ----------------------------------------------------------------------


def _measurement(loss: float, *, action: str = ce.ACTION_NO_DOUBLE, owner: int = 0, turn: int = 1):
    return ce.CubeMeasurement(
        name="m",
        match_length=0,
        cube_owner=owner,
        turn=turn,
        is_crawford=False,
        gnubg_action=action,
        our_action=action,
        gnubg_take=None,
        our_take=True,
        loss=loss,
        cubeless_equity=0.0,
        no_double=0.0,
        double_pass=1.0,
        double_take=0.0,
        agree=True,
        take_agree=None,
    )


def test_145_summary_ci_brackets_the_mean() -> None:
    ms = [_measurement(x) for x in (0.0, 0.1, 0.2, 0.3, 0.4)]
    s = ce.summarize_cube(ms, resamples=2000)
    assert s["count"] == 5
    assert s["mean"] == pytest.approx(0.2)
    assert s["ciLow"] <= s["mean"] <= s["ciHigh"]
    assert s["sigma"] == pytest.approx(0.15811388300841897)


def test_145_summary_rejects_empty() -> None:
    with pytest.raises(ce.CubeErError):
        ce.summarize_cube([])


def test_145_owner_bucket_is_relative_to_the_doubler() -> None:
    """F7-73: sira -1 iken kup -1'de ise bu **bizim** kupumuzdur."""
    ms = [
        _measurement(0.0, owner=0, turn=1),
        _measurement(0.0, owner=1, turn=1),
        _measurement(0.0, owner=-1, turn=-1),
    ]
    s = ce.summarize_cube(ms, resamples=1000)
    assert s["byOwner"]["centre"]["count"] == 1
    assert s["byOwner"]["ours"]["count"] == 2
    assert "theirs" not in s["byOwner"]


# ----------------------------------------------------------------------
# Test 146 -- R-T30: guc hesabi sigma ust sinirindan
# ----------------------------------------------------------------------


def test_146_power_uses_sigma_upper_bound() -> None:
    ms = [_measurement(0.0), _measurement(0.2)]
    s = ce.summarize_cube(ms, resamples=1000)
    rows = ce.power_rows(s, deltas=(0.01,))
    sigma_high = s["sigma"] * ce.SIGMA_UPPER_FACTOR
    assert rows[0]["sigmaHigh"] == pytest.approx(sigma_high)
    expected = math.ceil((1.645 * sigma_high / 0.01) ** 2)
    assert rows[0]["requiredN"] == expected


def test_146_power_rejects_non_positive_delta() -> None:
    ms = [_measurement(0.0), _measurement(0.2)]
    s = ce.summarize_cube(ms, resamples=1000)
    with pytest.raises(ce.CubeErError):
        ce.power_rows(s, deltas=(0.0,))


# ----------------------------------------------------------------------
# Test 147 -- R-T31/R-T32: korpus
# ----------------------------------------------------------------------


def _position(turn: int = 1) -> dict:
    board = [0] * 26
    board[0] = 2 * turn
    board[25] = -2 * turn
    return {"name": "p", "board": board, "turn": turn, "phase": "contact"}


def test_147_cross_product_size() -> None:
    cases = ce.build_cube_corpus([_position()], contexts=((0, 0, 0), (5, 0, 0)), owners=(0, 1))
    assert len(cases) == 4


def test_147_owner_is_relative_to_turn() -> None:
    cases = ce.build_cube_corpus([_position(turn=-1)], contexts=((0, 0, 0),), owners=(0, 1))
    owners = sorted(c.cube_owner for c in cases)
    assert owners == [-1, 0]


def test_147_phase_key_does_not_collide_with_game_phase() -> None:
    """``phase`` C# tarafinda ``GamePhase``; korpus ayri anahtar kullanir."""
    cases = ce.build_cube_corpus([_position()], contexts=((0, 0, 0),), owners=(0,))
    payload = cases[0].to_dict()
    assert "phaseClass" in payload
    assert "phase" not in payload


def test_147_crawford_context_is_detected() -> None:
    cases = ce.build_cube_corpus([_position()], contexts=(ce.CRAWFORD_CONTEXT,), owners=(0,))
    assert cases[0].is_crawford is True


def test_147_default_contexts_are_not_crawford() -> None:
    """F7-73: Crawford baglami ER'ye girmemeli (orada kup yok)."""
    cases = ce.build_cube_corpus([_position()], owners=(0,))
    assert all(not c.is_crawford for c in cases)
    assert ce.CRAWFORD_CONTEXT not in ce.MATCH_CONTEXTS
