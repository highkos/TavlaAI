"""Test 91-92. Derin `hint` hakemi (Faz 7 Bolum 4.2).

Kapsam:
  * Test 91 -- hamle notasyonu -> tahta (F7-02 aynalama dahil)
  * Test 92 -- derinlik denetimi (F7-01) ve 10 hamle tavani (F7-03)
  * F7-04 -- hakem secim politikasi (2-ply `eval`, >=3-ply `hint`)

gnubg gerektiren testler `requires_gnubg` ile atlanir; notasyon, aynalama,
filtre komutlari ve rapor testleri gnubg olmadan da calisir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gnubg_er as G
import gnubg_hint as H

GNUBG = G.find_gnubg()
requires_gnubg = pytest.mark.skipif(GNUBG is None, reason="gnubg-cli kurulu degil")

CORPUS_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "reference_corpus_v1.json"


def _corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _case(name: str) -> dict:
    for case in _corpus()["cases"]:
        if case["name"] == name:
            return case
    raise KeyError(name)


# ----------------------------------------------------------------------
# F7-04 -- hakem secimi
# ----------------------------------------------------------------------


@pytest.mark.parametrize("plies", [0, 1, 2])
def test_91_referee_for_plies_uses_eval_up_to_two(plies: int) -> None:
    """F7-04: 2-ply'ye kadar yetkili hakem `eval`'dir."""
    assert H.referee_for_plies(plies) == H.SOURCE_EVAL


@pytest.mark.parametrize("plies", [3, 4])
def test_91_referee_for_plies_uses_hint_from_three(plies: int) -> None:
    """F7-04: 3-ply ve uzerinde yetkili hakem `hint`'tir."""
    assert H.referee_for_plies(plies) == H.SOURCE_HINT


@pytest.mark.parametrize("plies", [-1, 5, 6])
def test_91_referee_for_plies_rejects_out_of_range(plies: int) -> None:
    """F7-01: `hint` 4-ply'den derine inemez; negatif derinlik anlamsizdir."""
    with pytest.raises(ValueError):
        H.referee_for_plies(plies)


def test_91_assert_referee_choice_rejects_hint_at_two_ply() -> None:
    """F7-04: `hint@2` hakem olarak secilemez."""
    with pytest.raises(ValueError):
        H.assert_referee_choice(2, H.SOURCE_HINT)
    H.assert_referee_choice(2, H.SOURCE_EVAL)
    H.assert_referee_choice(3, H.SOURCE_HINT)


def test_91_ladder_method_note_names_both_protocols() -> None:
    """F7-04: 2/3 sinirindaki yontem degisikligi raporlanabilir olmali."""
    note = H.LADDER_METHOD_NOTE
    assert "eval" in note and "hint" in note
    assert "2-ply" in note and "3-ply" in note


def test_91_method_note_differs_by_plies() -> None:
    """F7-04: 2-ply ve 3-ply raporlari farkli yontem notu tasir."""
    two = H.HintReferee.__new__(H.HintReferee)
    two.plies = 2
    three = H.HintReferee.__new__(H.HintReferee)
    three.plies = 3
    assert two.method_note != three.method_note
    assert "eval" in two.method_note
    assert three.method_note == H.LADDER_METHOD_NOTE


# ----------------------------------------------------------------------
# Test 91 -- notasyon ve aynalama (F7-02)
# ----------------------------------------------------------------------


def test_91_off_target_and_bar_index() -> None:
    """Toplama hedefi ve bar indeksi oyuncuya gore degisir."""
    assert H.off_target(1) == 25 and H.off_target(-1) == 0
    assert H._point("off", 1) == 25 and H._point("off", -1) == 0
    assert H._point("bar", 1) == 0 and H._point("bar", -1) == 25


@pytest.mark.parametrize(
    "text,expected",
    [("1", 1), ("6", 6), ("12", 12), ("18", 18), ("24", 24)],
)
def test_91_point_is_identity_for_black(text: str, expected: int) -> None:
    """F7-02: Siyah (turn=-1) mutlak numaralandirma kullanir."""
    assert H._point(text, -1) == expected


@pytest.mark.parametrize(
    "text,expected",
    [("1", 24), ("6", 19), ("12", 13), ("18", 7), ("24", 1)],
)
def test_91_point_is_mirrored_for_white(text: str, expected: int) -> None:
    """F7-02: Beyaz (turn=+1) aynalanmis numaralandirma kullanir (p -> 25-p)."""
    assert H._point(text, 1) == expected


@pytest.mark.parametrize("text", ["0", "25", "26", "-3", "x", ""])
def test_91_point_rejects_invalid(text: str) -> None:
    """Gecersiz hane sessizce yutulmaz."""
    with pytest.raises(H.HintMappingError):
        H._point(text, -1)


def test_91_parse_move_single_hop() -> None:
    assert H.parse_move("15/6", -1) == [(15, 6, False)]
    assert H.parse_move("15/6", 1) == [(10, 19, False)]


def test_91_parse_move_hit_marker() -> None:
    """Vurma isareti hedefte kalir, kalkista tasinmaz."""
    assert H.parse_move("13/5*", -1) == [(13, 5, True)]


def test_91_parse_move_multiplier() -> None:
    """`(2)` / `(3)` / `(4)` carpanlari adimi tekrarlar."""
    assert H.parse_move("13/5*(2)", -1) == [(13, 5, True), (13, 5, True)]
    assert H.parse_move("8/7(3)", -1) == [(8, 7, False)] * 3
    assert H.parse_move("6/5(4)", -1) == [(6, 5, False)] * 4


def test_91_parse_move_intermediate_hit() -> None:
    """`13/5*/1`: ara hane hem varis hem kalkistir (vurma isareti orada kalir)."""
    assert H.parse_move("13/5*/1", -1) == [(13, 5, True), (5, 1, False)]


def test_91_parse_move_two_tokens() -> None:
    assert H.parse_move("bar/22 8/5", -1) == [(25, 22, False), (8, 5, False)]
    assert H.parse_move("bar/22 8/5", 1) == [(0, 3, False), (17, 20, False)]


def test_91_parse_move_bear_off() -> None:
    assert H.parse_move("6/off", -1) == [(6, 0, False)]
    assert H.parse_move("6/off", 1) == [(19, 25, False)]


@pytest.mark.parametrize("move", ["", "   ", "15", "15/", "/6"])
def test_91_parse_move_rejects_malformed(move: str) -> None:
    with pytest.raises(H.HintMappingError):
        H.parse_move(move, -1)


def test_91_apply_move_does_not_mutate_input() -> None:
    board = [0] * 26
    board[13] = -2
    before = list(board)
    H.apply_move(board, -1, "13/7", 0, 0)
    assert board == before


def test_91_apply_move_moves_a_piece() -> None:
    board = [0] * 26
    board[13] = -2
    out, wo, bo = H.apply_move(board, -1, "13/7", 0, 0)
    assert out[13] == -1 and out[7] == -1
    assert (wo, bo) == (0, 0)


def test_91_apply_move_hit_sends_to_bar() -> None:
    """Vurulan tas rakibin barina gider."""
    board = [0] * 26
    board[13] = -1
    board[7] = 1
    out, _, _ = H.apply_move(board, -1, "13/7*", 0, 0)
    assert out[7] == -1
    assert out[0] == 1


def test_91_apply_move_bear_off_increments_counter() -> None:
    board = [0] * 26
    board[6] = -1
    out, wo, bo = H.apply_move(board, -1, "6/off", 0, 3)
    assert out[6] == 0
    assert (wo, bo) == (0, 4)


def test_91_apply_move_rejects_empty_source() -> None:
    board = [0] * 26
    with pytest.raises(H.HintMappingError):
        H.apply_move(board, -1, "13/7", 0, 0)


def test_91_afterstate_key_is_hashable_and_stable() -> None:
    board = [0] * 26
    board[13] = -2
    key = H.afterstate_key(board, 1, 2)
    assert key == H.afterstate_key(list(board), 1, 2)
    assert key in {key}
    assert key[1:] == (1, 2)


# ----------------------------------------------------------------------
# Test 92 -- derinlik denetimi (F7-01)
# ----------------------------------------------------------------------


def test_92_parse_depths_reads_labels() -> None:
    text = (
        "    1. Cubeless 3-ply 13/5*(2)                        Eq.: +0,253\n"
        "    2. Cubeless 2-ply 13/5*/1 6/2                     Eq.: +0,082\n"
    )
    assert H.parse_depths(text) == [(3, "13/5*(2)"), (2, "13/5*/1 6/2")]


def test_92_verify_uniform_depth_accepts_uniform() -> None:
    text = "1. Cubeless 3-ply 13/5*(2) Eq.: +0,253\n2. Cubeless 3-ply 8/5 Eq.: +0,100\n"
    assert H.verify_uniform_depth(text, 3) == []


def test_92_verify_uniform_depth_flags_pruned_moves() -> None:
    """F7-01: filtre acilmazsa hamleler daha sig etiketle doner."""
    text = "1. Cubeless 3-ply 13/5*(2) Eq.: +0,253\n2. Cubeless 2-ply 8/5 Eq.: +0,100\n"
    problems = H.verify_uniform_depth(text, 3)
    assert len(problems) == 1
    assert "2-ply" in problems[0] and "3-ply" in problems[0]


def test_92_verify_uniform_depth_empty_text_is_vacuous() -> None:
    assert H.verify_uniform_depth("", 3) == []


def test_92_hint_move_cap_is_ten() -> None:
    """F7-03: gnubg `hint` en fazla 10 hamle basar."""
    assert H.HINT_MOVE_CAP == 10


def test_92_hint_max_plies_is_four() -> None:
    assert H.HINT_MAX_PLIES == 4


# ----------------------------------------------------------------------
# Test 92 -- filtre komutlari (F7-01), gnubg gerekmez
# ----------------------------------------------------------------------


class _FakeSession:
    def _preamble(self) -> list[str]:
        return ["set cube use off", "new game"]


def _referee(plies: int) -> H.HintReferee:
    ref = H.HintReferee.__new__(H.HintReferee)
    ref.plies = plies
    ref.session = _FakeSession()
    return ref


@pytest.mark.parametrize("plies", [1, 2, 3, 4])
def test_92_preamble_widens_every_filter_level(plies: int) -> None:
    """F7-01: `plies` icin 0..plies-1 seviyelerinin **hepsi** acilmalidir."""
    commands = _referee(plies)._preamble()
    filters = [c for c in commands if c.startswith("set evaluation movefilter")]
    assert len(filters) == plies
    for level, command in enumerate(filters):
        assert command == "set evaluation movefilter %d %d %d 0 0.0" % (
            plies,
            level,
            H.WIDE_FILTER_ACCEPT,
        )


def test_92_preamble_keeps_session_commands() -> None:
    commands = _referee(3)._preamble()
    assert commands[:2] == ["set cube use off", "new game"]


def test_92_wide_filter_accept_exceeds_any_candidate_count() -> None:
    """F7-01: esik 1000, 21 zar x 15 taslik en genis aday kumesini asar."""
    assert H.WIDE_FILTER_ACCEPT >= 1000


# ----------------------------------------------------------------------
# Test 92 -- gercek gnubg ile derinlik ve esleme
# ----------------------------------------------------------------------


@requires_gnubg
@pytest.mark.slow
def test_92_hint_checked_is_uniform_at_three_ply() -> None:
    """F7-01: filtre acikken 3-ply cagrisi tekduze 3-ply doner."""
    case = _case("f6-000")
    referee = H.HintReferee(GNUBG, plies=3, timeout=900)
    moves, text = referee.hint_checked(case["board"], int(case["turn"]), case["dice"])
    assert moves
    assert H.verify_uniform_depth(text, 3) == []
    assert {d for d, _ in H.parse_depths(text)} == {3}


@requires_gnubg
@pytest.mark.slow
def test_92_hint_without_widening_degrades_silently() -> None:
    """F7-01 kaniti: filtre acilmazsa 3-ply istegi 2-ply etiketiyle doner."""
    case = _case("f6-000")
    session = G.GnubgSession(GNUBG, plies=3, timeout=900)
    moves, text = session.hint(case["board"], int(case["turn"]), case["dice"])
    assert moves
    depths = {d for d, _ in H.parse_depths(text)}
    assert depths != {3}, "filtre acilmadan 3-ply dondu; F7-01 gecersiz"
    assert H.verify_uniform_depth(text, 3) != []


@requires_gnubg
@pytest.mark.slow
def test_92_map_hints_covers_corpus_subset() -> None:
    """F7-02: notasyon aynalamasi 20 pozisyonda 20/20 eslesmeli."""
    cases = _corpus()["cases"][:20]
    referee = H.HintReferee(GNUBG, plies=1, timeout=900)
    total = 0
    failures = 0
    for case in cases:
        hints, _text = referee.hint(case["board"], int(case["turn"]), case["dice"])
        matched, bad = H.map_hints(hints, case)
        total += len(hints)
        failures += len(bad)
        assert matched, case["name"]
    assert failures == 0, "%d/%d hamle eslesmedi" % (failures, total)


@requires_gnubg
@pytest.mark.slow
def test_92_hint_returns_at_most_ten_moves() -> None:
    """F7-03: 43 afterstate'i olan pozisyonda bile `hint` 10 hamle basar."""
    case = _case("f6-001")
    assert len(case["afterStates"]) > H.HINT_MOVE_CAP
    referee = H.HintReferee(GNUBG, plies=1, timeout=900)
    hints, _text = referee.hint(case["board"], int(case["turn"]), case["dice"])
    assert len(hints) <= H.HINT_MOVE_CAP


@requires_gnubg
@pytest.mark.slow
def test_92_eval_afterstate_is_none_beyond_two_ply() -> None:
    """F7-03: 3-ply'de `eval` yolu yok; pozisyon sansurlu isaretlenmeli."""
    case = _case("f6-000")
    deep = H.HintReferee(GNUBG, plies=3, timeout=900)
    assert deep.eval_afterstate(case["board"], int(case["turn"])) is None
    shallow = H.HintReferee(GNUBG, plies=2, timeout=900)
    value = shallow.eval_afterstate(case["board"], int(case["turn"]))
    assert value is not None and isinstance(value, float)


# ----------------------------------------------------------------------
# Test 92 -- rapor ve ozet
# ----------------------------------------------------------------------


def _result(**kwargs) -> H.HintPositionResult:
    base = dict(
        name="x",
        turn=-1,
        dice=[3, 6],
        afterstate_count=10,
        hint_count=10,
        best_index=0,
        best_equity=0.5,
        best_move="13/7",
        model_afterstate_index=0,
        model_equity=0.5,
        equity_loss=0.0,
        exact_match=True,
        model_equity_source=H.SOURCE_HINT,
        censored=False,
        loss_lower_bound=0.0,
        mapping_failures=[],
        notes=[],
    )
    base.update(kwargs)
    return H.HintPositionResult(**base)


def test_92_summarize_reports_coverage_and_sources() -> None:
    results = [
        _result(name="a", equity_loss=0.0),
        _result(name="b", equity_loss=0.2, model_equity_source=H.SOURCE_EVAL),
        _result(
            name="c",
            equity_loss=0.0,
            model_equity_source=H.SOURCE_CENSORED,
            censored=True,
            loss_lower_bound=0.1,
        ),
    ]
    summary = H.summarize(results)
    assert summary["count"] == 3
    assert summary["coveredCount"] == 2
    assert summary["censoredCount"] == 1
    assert summary["coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert summary["sources"][H.SOURCE_HINT] == 1
    assert summary["sources"][H.SOURCE_EVAL] == 1
    assert summary["sources"][H.SOURCE_CENSORED] == 1
    assert summary["mean"] == pytest.approx(0.1)
    assert summary["meanLowerBound"] == pytest.approx(0.1)


def test_92_summarize_flags_mapping_failures() -> None:
    summary = H.summarize(
        [_result(mapping_failures=[{"move": "13/7", "reason": "afterstate kumede yok"}])]
    )
    assert summary["mappingFailures"] == 1
    assert summary["mappingOk"] is False


def test_92_build_markdown_warns_on_censoring() -> None:
    report = {
        "model": "m.onnx",
        "referee": "hint",
        "plies": 3,
        "criterion": "policy",
        "methodNote": H.LADDER_METHOD_NOTE,
        "summary": H.summarize(
            [
                _result(name="a"),
                _result(
                    name="b",
                    model_equity_source=H.SOURCE_CENSORED,
                    censored=True,
                    loss_lower_bound=0.3,
                ),
            ]
        ),
        "positions": [],
    }
    text = H.build_markdown(report)
    assert "Kapsama" in text
    assert "sansurlu" in text.lower()
    assert "F7-04" in text
    assert "F7-03" in text


def test_92_build_markdown_clean_report_has_no_warning() -> None:
    report = {
        "model": "m.onnx",
        "referee": "hint",
        "plies": 2,
        "criterion": "policy",
        "methodNote": "n",
        "summary": H.summarize([_result(name="a")]),
        "positions": [],
    }
    text = H.build_markdown(report)
    assert "UYARI" not in text


def test_92_write_json_round_trips(tmp_path: Path) -> None:
    report = {"model": "m", "summary": {"count": 1}, "positions": []}
    path = tmp_path / "out.json"
    H.write_json(report, path)
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_92_cli_parser_defaults() -> None:
    parser = H.build_parser()
    args = parser.parse_args(["--model", "m.onnx"])
    assert args.plies == 3
    assert args.criterion == "policy"
    assert args.timeout == H.DEFAULT_HINT_TIMEOUT
