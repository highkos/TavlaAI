"""Faz 4 v3 Bolum 9 (Asama D) — GNU Backgammon ER olcumu testleri.

gnubg gerektiren testler `pytest.mark.skipif` ile atlanir; ayristirma, tahta donusumu
ve vektorlestirme testleri gnubg kurulu olmadan da calisir.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

import gnubg_er as G

REFERENCE_PATH = G.DEFAULT_CASES
GOLDEN_VECTOR_PATH = Path(__file__).resolve().parent.parent.parent / "Backgammon.Tests" / "ReferenceData" / "vector_golden.json"

GNUBG = G.find_gnubg()
requires_gnubg = pytest.mark.skipif(GNUBG is None, reason="gnubg-cli kurulu degil")

STAGE_D_MODEL = Path(__file__).resolve().parent.parent / "runs" / "stage_d" / "onnx" / "model_v10.onnx"


def _stage_d_model() -> Path:
    if not STAGE_D_MODEL.is_file():
        pytest.skip("stage_d modeli yok: %s" % STAGE_D_MODEL)
    return STAGE_D_MODEL


def _start_board() -> list[int]:
    board = [0] * 26
    board[1] = 2
    board[12] = 5
    board[17] = 3
    board[19] = 5
    board[24] = -2
    board[13] = -5
    board[8] = -3
    board[6] = -5
    return board


# ----------------------------------------------------------------------
# Tahta donusumu
# ----------------------------------------------------------------------


def test_board_to_simple_start_position():
    simple = G.board_to_simple(_start_board())
    assert simple == [0, -2, 0, 0, 0, 0, 5, 0, 3, 0, 0, 0, -5, 5, 0, 0, 0, -3, 0, -5, 0, 0, 0, 0, 2, 0]


def test_board_to_simple_swaps_bars_and_flips_signs():
    board = [0] * 26
    board[0] = 3  # beyaz bar
    board[25] = -4  # siyah bar
    board[7] = 2
    board[20] = -6

    simple = G.board_to_simple(board)
    assert simple[0] == 4  # X bari = siyah bari
    assert simple[25] == 3  # O bari = beyaz bari
    assert simple[7] == -2
    assert simple[20] == 6


def test_board_to_simple_rejects_short_board():
    with pytest.raises(ValueError):
        G.board_to_simple([0] * 25)


def test_gnubg_turn_mapping():
    assert G.gnubg_turn(1) == 0  # Beyaz = O
    assert G.gnubg_turn(-1) == 1  # Siyah = X
    with pytest.raises(ValueError):
        G.gnubg_turn(0)


# ----------------------------------------------------------------------
# Pip sayimi
# ----------------------------------------------------------------------


def test_pip_count_start_position_is_167():
    board = _start_board()
    assert G.pip_count(board, 1) == 167
    assert G.pip_count(board, -1) == 167


def test_pip_count_bar_checker_is_25():
    board = [0] * 26
    board[0] = 1
    assert G.pip_count(board, 1) == 25
    board = [0] * 26
    board[25] = -1
    assert G.pip_count(board, -1) == 25


# ----------------------------------------------------------------------
# Vektorlestirme (altin kayitlarla)
# ----------------------------------------------------------------------


@pytest.mark.skipif(not GOLDEN_VECTOR_PATH.is_file(), reason="vector_golden.json yok")
def test_vectorize_matches_golden_records():
    data = json.loads(GOLDEN_VECTOR_PATH.read_text(encoding="utf-8"))
    assert data["vectorSize"] == G.VECTOR_SIZE

    for record in data["records"]:
        actual = G.vectorize(
            record["board"],
            record["whiteBorneOff"],
            record["blackBorneOff"],
            cube_value=record["cubeValue"],
            cube_owner=record["cubeOwner"],
            match_length=record["matchLength"],
            white_score=record["whiteScore"],
            black_score=record["blackScore"],
            is_crawford=record["isCrawfordGame"],
            perspective=record["perspective"],
        )
        expected = [struct.unpack(">f", bytes.fromhex(h))[0] for h in record["vectorHex"].split(",")]
        assert len(actual) == G.VECTOR_SIZE
        for index, (a, e) in enumerate(zip(actual, expected)):
            assert abs(a - e) <= 1e-6, "kayit %s indeks %d" % (record.get("board"), index)


def test_vectorize_rejects_bad_perspective():
    with pytest.raises(ValueError):
        G.vectorize(_start_board(), 0, 0, perspective=0)


def test_vectorize_is_mirror_symmetric_on_start_position():
    board = _start_board()
    white = G.vectorize(board, 0, 0, perspective=1)
    black = G.vectorize(board, 0, 0, perspective=-1)
    assert white[G.ACTIVE_PIP] == pytest.approx(black[G.OPP_PIP])
    assert white[G.OPP_PIP] == pytest.approx(black[G.ACTIVE_PIP])
    assert white[G.IS_CONTACT] == black[G.IS_CONTACT] == 1.0


# ----------------------------------------------------------------------
# gnubg cikti ayristirma
# ----------------------------------------------------------------------


HINT_SAMPLE = """
    1. Cubeless 0-ply   8/5 6/5                      Eq.: +0,160
       0,551 0,174 0,013 - 0,449 0,124 0,005
        0-ply cubeless prune
    2. Cubeless 0-ply   24/23 13/10                  Eq.: -0,008 (-0,168)
       0,500 0,120 0,008 - 0,500 0,130 0,006
    3. Cubeless 0-ply   24/18(2) 13/7(2)             Eq.: -0,021 (-0,181)
"""


def test_parse_hint_reads_rank_move_equity_and_loss():
    moves = G.parse_hint(HINT_SAMPLE)
    assert len(moves) == 3
    assert moves[0].rank == 1
    assert moves[0].move == "8/5 6/5"
    assert moves[0].equity == pytest.approx(0.160)
    assert moves[0].loss is None
    assert moves[1].equity == pytest.approx(-0.008)
    assert moves[1].loss == pytest.approx(-0.168)
    assert moves[2].move == "24/18(2) 13/7(2)"


def test_parse_hint_handles_decimal_point():
    text = "    1. Cubeless 2-ply   13/7 8/5    Eq.: +0.123\n"
    moves = G.parse_hint(text)
    assert len(moves) == 1
    assert moves[0].equity == pytest.approx(0.123)


def test_parse_hint_returns_empty_for_garbage():
    assert G.parse_hint("no hints here") == []


EVAL_SAMPLE = """
Position ID:\t4HPwATDgc/ABMA
Evaluator: \tContact
        Win     W(g)    W(bg)   L(g)    L(bg)   Equity    Cubeful
static: 0,522   0,154   0,008   0,130   0,007   +0,068    +0,090
 1 ply: 0,527   0,148   0,008   0,128   0,005   +0,077    +0,104
 2 ply: 0,525   0,150   0,007   0,125   0,005   +0,076    +0,098
"""


def test_parse_eval_extracts_cubeless_equity_per_ply():
    table = G.parse_eval(EVAL_SAMPLE)
    assert table["static"] == pytest.approx(0.068)
    assert table["1"] == pytest.approx(0.077)
    assert table["2"] == pytest.approx(0.076)


def test_parse_eval_returns_empty_for_garbage():
    assert G.parse_eval("nothing") == {}


def test_parse_pipcount_identifies_players_by_name():
    text = "The pip counts are: gnubg 24, MONSTER 278.\n"
    assert G.parse_pipcount(text) == (278, 24)

    text = "The pip counts are: MONSTER 278, gnubg 24.\n"
    assert G.parse_pipcount(text) == (278, 24)


def test_parse_pipcount_returns_none_for_garbage():
    assert G.parse_pipcount("nothing") is None


def test_parse_pipcounts_reads_every_block_in_order():
    text = (
        "The pip counts are: gnubg 24, MONSTER 278.\n"
        "The pip counts are: MONSTER 100, gnubg 50.\n"
    )
    assert G.parse_pipcounts(text) == [(278, 24), (100, 50)]


def test_parse_pipcounts_returns_empty_for_garbage():
    assert G.parse_pipcounts("nothing") == []


def test_parse_evals_splits_blocks_on_pipcount_line():
    text = (
        "The pip counts are: gnubg 24, MONSTER 278.\n"
        + EVAL_SAMPLE
        + "The pip counts are: gnubg 50, MONSTER 100.\n"
        + EVAL_SAMPLE.replace("+0,076", "+0,321")
    )
    tables = G.parse_evals(text)
    assert len(tables) == 2
    assert tables[0]["2"] == pytest.approx(0.076)
    assert tables[1]["2"] == pytest.approx(0.321)


def test_parse_evals_returns_empty_without_pipcount_lines():
    assert G.parse_evals(EVAL_SAMPLE) == []


def test_parse_number_handles_comma_and_sign():
    assert G.parse_number("+0,160") == pytest.approx(0.160)
    assert G.parse_number("-0.008") == pytest.approx(-0.008)


# ----------------------------------------------------------------------
# Referans veri
# ----------------------------------------------------------------------


@pytest.mark.skipif(not REFERENCE_PATH.is_file(), reason="reference_positions.json yok")
def test_split_cases_keeps_only_full_positions_with_afterstates():
    cases = G.load_cases(REFERENCE_PATH)
    usable, skipped = G.split_cases(cases)

    assert len(usable) + len(skipped) == len(cases)
    assert len(usable) == 50
    assert "bar-closed-white" in skipped
    assert "bearoff-exact-white" in skipped
    for case in usable:
        assert G.case_piece_counts(case) == (15, 15)
        assert case["afterStates"]


@pytest.mark.skipif(not REFERENCE_PATH.is_file(), reason="reference_positions.json yok")
def test_case_piece_counts_counts_bar_and_off():
    case = {
        "board": [2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -3],
        "whiteOff": 12,
        "blackOff": 12,
    }
    assert G.case_piece_counts(case) == (15, 15)


# ----------------------------------------------------------------------
# Ozet ve rapor
# ----------------------------------------------------------------------


def _position(name: str, loss: float, *, exact: bool = False) -> G.PositionResult:
    return G.PositionResult(
        name=name,
        turn=1,
        dice=[3, 1],
        afterstate_count=4,
        gnubg_best_index=0,
        gnubg_best_equity=0.1,
        gnubg_hint_move="8/5 6/5",
        gnubg_hint_equity=0.1,
        model_afterstate_index=0 if exact else 2,
        model_equity=0.1 - loss,
        equity_loss=loss,
        model_value=0.0,
        exact_match=exact,
    )


def test_summarize_computes_mean_median_and_match_rate():
    stats = G.summarize(
        [
            _position("a", 0.0, exact=True),
            _position("b", 0.1),
            _position("c", 0.2),
            _position("d", 0.3),
        ]
    )
    assert stats["count"] == 4
    assert stats["mean"] == pytest.approx(0.15)
    assert stats["median"] == pytest.approx(0.15)
    assert stats["max"] == pytest.approx(0.3)
    assert stats["exactMatchRate"] == pytest.approx(0.25)


def test_summarize_handles_empty_input():
    stats = G.summarize([])
    assert stats["count"] == 0
    assert stats["mean"] == 0.0


def test_build_markdown_contains_method_and_table():
    text = G.build_markdown(
        [_position("start-3-1", 0.05)],
        ["bar-closed-white"],
        model_path=Path("model.onnx"),
        gnubg_path=Path("gnubg-cli.exe"),
        gnubg_ver="GNU Backgammon 1.08.003",
        plies=2,
        total_cases=57,
        criterion="policy",
    )
    assert "`model.onnx`" in text
    assert "GNU Backgammon 1.08.003" in text
    assert "| Referans vaka | 57 (kullanılabilir 1) |" in text
    assert "`bar-closed-white`" in text
    assert "| 1 | `start-3-1` | 3-1 | 4 | 0 | +0.1000 | +0.0500 | +0.0500 | hayır |" in text
    assert "E_best = max(afterstate equity'leri)" in text


def test_write_json_roundtrip(tmp_path: Path):
    out = tmp_path / "er.json"
    G.write_json(
        out,
        [_position("start-3-1", 0.05)],
        ["bar-closed-white"],
        model_path=Path("model.onnx"),
        gnubg_path=Path("gnubg-cli.exe"),
        gnubg_ver="1.08",
        plies=2,
        total_cases=57,
        criterion="policy",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["criterion"] == "policy"
    assert payload["measuredCases"] == 1
    assert payload["skippedCases"] == ["bar-closed-white"]
    assert payload["summary"]["meanEquityLoss"] == pytest.approx(0.05)
    assert payload["positions"][0]["name"] == "start-3-1"
    assert payload["positions"][0]["exactMatch"] is False


# ----------------------------------------------------------------------
# gnubg kesfi
# ----------------------------------------------------------------------


def test_find_gnubg_returns_none_for_missing_explicit_path(tmp_path: Path):
    assert G.find_gnubg(tmp_path / "does-not-exist.exe") is None


def test_main_fails_cleanly_without_gnubg(tmp_path: Path, capsys):
    code = G.main(["--model", str(tmp_path / "missing.onnx"), "--gnubg", str(tmp_path / "nope.exe")])
    assert code == 2
    assert "gnubg-cli bulunamadi" in capsys.readouterr().err


# ----------------------------------------------------------------------
# gnubg gerektiren testler
# ----------------------------------------------------------------------


@requires_gnubg
def test_gnubg_version_is_reported():
    assert "Backgammon" in G.gnubg_version(GNUBG)


@requires_gnubg
def test_gnubg_accepts_start_position_and_reports_167_pips():
    session = G.GnubgSession(GNUBG, plies=2)
    moves, text = session.hint(_start_board(), 1, [3, 1])
    assert G.parse_pipcount(text) == (167, 167)
    assert moves
    assert moves[0].rank == 1


@requires_gnubg
def test_gnubg_eval_is_from_on_roll_perspective():
    """``eval`` equity'si **sirada olan** oyuncunun bakis acisindandir.

    Simetrik baslangic pozisyonunda iki taraf da ayni degeri gorur; asimetrik
    pozisyonda isaret ve buyukluk sirada olan oyuncuya gore degisir.
    """
    session = G.GnubgSession(GNUBG, plies=2)
    board = _start_board()
    white, _ = session.eval_position(board, 1)
    black, _ = session.eval_position(board, -1)
    assert white["2"] == pytest.approx(black["2"], abs=1e-6)

    # Beyaz 1 pip uzakta, siyah 15 pip uzakta: sirada olan oyuncunun isareti degisir.
    lopsided = [0] * 26
    lopsided[24] = 1
    lopsided[1] = -15
    white, _ = session.eval_position(lopsided, 1)
    black, _ = session.eval_position(lopsided, -1)
    assert white["2"] > 0.5
    assert black["2"] < -0.5


@requires_gnubg
def test_gnubg_rejects_illegal_board():
    session = G.GnubgSession(GNUBG, plies=2)
    illegal = [0] * 26
    illegal[1] = 15
    illegal[24] = -15
    illegal[0] = 1  # 16 tas: gecersiz
    with pytest.raises(G.GnubgError):
        session.hint(illegal, 1, [3, 1])


@requires_gnubg
def test_gnubg_eval_afterstates_loads_every_board():
    """Ardisik ``set board`` komutlari sessizce reddedilmemeli (``new game`` sart)."""
    session = G.GnubgSession(GNUBG, plies=2)
    boards = [_start_board()]
    moved = _start_board()
    moved[6] += 1
    moved[5] -= 1
    boards.append(moved)

    tables = session.eval_afterstates(boards, 1)
    assert len(tables) == 2
    assert tables[0]["2"] != pytest.approx(tables[1]["2"])


@requires_gnubg
def test_measure_position_is_self_consistent():
    """Tek yasal hamleli pozisyonda ER sifir olmali (E_best == E_model)."""
    cases = G.load_cases(REFERENCE_PATH)
    usable, _ = G.split_cases(cases)
    single = [c for c in usable if len(c["afterStates"]) == 1]
    assert single, "tek hamleli referans vaka bekleniyordu"

    session = G.GnubgSession(GNUBG, plies=2)
    scorer = G.OnnxScorer(_stage_d_model())
    result = G.measure_position(session, scorer, single[0], plies=2, criterion="policy")

    assert result.equity_loss == pytest.approx(0.0, abs=1e-9)
    assert result.exact_match is True
    assert result.gnubg_best_index == result.model_afterstate_index == 0


@requires_gnubg
def test_gnubg_persistent_session_matches_one_shot():
    """Kalici surec tek-atimlik kosuyla **ayni** tabloyu vermeli.

    Kalici surec bir performans optimizasyonudur (cagri basina ~0,45 s -> ~0,01 s);
    olcumu degistirmemelidir. Ayni tahta dizisi iki modda da ayni equity'yi
    dondurmezse uzun mac simulasyonlari sessizce kayar.
    """
    boards = [_start_board()]
    moved = _start_board()
    moved[6] += 1
    moved[5] -= 1
    boards.append(moved)

    one_shot = G.GnubgSession(GNUBG, plies=2)
    persistent = G.GnubgSession(GNUBG, plies=2, persistent=True)
    try:
        expected = one_shot.eval_afterstates(boards, 1)
        # Ayni oturumda iki kez: kalici surec durum tasimamali.
        first = persistent.eval_afterstates(boards, 1)
        second = persistent.eval_afterstates(boards, 1)
    finally:
        persistent.close()

    assert len(first) == len(expected) == 2
    for got, want in zip(first, expected):
        assert got["2"] == pytest.approx(want["2"], abs=1e-9)
    for got, want in zip(second, expected):
        assert got["2"] == pytest.approx(want["2"], abs=1e-9)


def test_onnx_scorer_accepts_intra_op_threads():
    """``intra_op_threads`` kabul edilmeli; ``None`` varsayilani korur."""
    scorer = G.OnnxScorer(_stage_d_model(), intra_op_threads=1)
    assert scorer is not None
    default = G.OnnxScorer(_stage_d_model())
    assert default is not None

# ----------------------------------------------------------------------
# F7-114 / R-Q2: ``hint`` alti olasiligi da veriyor
# ----------------------------------------------------------------------

_HINT_WITH_PROBS = """    1. Cubeless 0-ply   bar/22                       Eq.: -0,164
       0,357 0,115 0,007 - 0,643 0,000 0,000
        0-ply cubeless prune
    2. Cubeless 0-ply   13/10 6/5                    Eq.: -0,201 (-0,037)
       0,340 0,101 0,005 - 0,660 0,000 0,000
"""


def test_333_parse_hint_reads_six_probabilities():
    """R-Q2: ``Eq.`` satirinin altindaki ``w wg wb - l lg lb`` okunur."""
    moves = G.parse_hint(_HINT_WITH_PROBS)
    assert len(moves) == 2
    first, second = moves
    assert first.probs == pytest.approx((0.357, 0.115, 0.007, 0.643, 0.0, 0.0))
    assert second.probs == pytest.approx((0.340, 0.101, 0.005, 0.660, 0.0, 0.0))
    assert first.win == pytest.approx(0.357)
    assert first.win_gammon == pytest.approx(0.115)
    assert first.win_backgammon == pytest.approx(0.007)
    assert first.lose == pytest.approx(0.643)
    assert first.lose_gammon == pytest.approx(0.0)
    assert first.lose_backgammon == pytest.approx(0.0)


def test_334_parse_hint_probabilities_are_a_distribution():
    """``w`` gammon/backgammon'u kapsar: ``w + l == 1`` ve alt kumeler tutarli."""
    for move in G.parse_hint(_HINT_WITH_PROBS):
        assert move.win + move.lose == pytest.approx(1.0, abs=1e-9)
        assert move.win_gammon <= move.win
        assert move.win_backgammon <= move.win_gammon
        assert move.lose_gammon <= move.lose
        assert move.lose_backgammon <= move.lose_gammon


def test_335_parse_hint_without_probability_line_is_none():
    """Olasilik satiri yoksa ``probs`` ``None``; eski davranis bozulmaz."""
    text = "    1. Cubeless 0-ply   bar/22                       Eq.: -0,164\n"
    moves = G.parse_hint(text)
    assert len(moves) == 1
    assert moves[0].probs is None
    assert moves[0].win is None
    assert moves[0].equity == pytest.approx(-0.164)

