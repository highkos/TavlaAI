"""Faz 8 Adim A1: sans-duzeltilmis H2H olcumu (Test 409-432).

bgsage ``H2H_LUCK_ADJUST.md`` matematigi: her zar olayinda 21 zar icin
referans devam equity'si hesaplanir, gerceklesen zarin katkisi kendi
ortalamasina gore merkezlenir, toplam sans oyundan dusulur. Duzeltme
**yansizdir** (``E[D_t | H_t] = 0``); kazanc yalnizca varyanstan gelir.

Bu testler sozlesmeyi kilitler:

* ayni tablo girdisi hem gerceklesen zar hem ortalama icin kullanilir
  (oynanan hamle kullanilsaydi yanlilik eklenirdi),
* donus kurali (``-V_rakip``) ve terminal/zorunlu-pas dallari,
* ``SE_adj`` kapali formu ve ``beta*``,
* isaret donusumu (A atiyor ``+1``, B atiyor ``-1``),
* tohum determinizmi ve is parcacigi sayisindan bagimsizlik,
* denetim noktasi imzasi.
"""

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

import er_paths  # noqa: E402
import luck_adjust  # noqa: E402
import ppg_measure  # noqa: E402
import vs_gnubg  # noqa: E402


# ----------------------------------------------------------------------
# Yardimcilar
# ----------------------------------------------------------------------


class FakeScorer:
    """Vektoru anahtar olarak kullanan sahte degerlendirici."""

    def __init__(self, table: dict[tuple, float] | None = None, default: float = 0.0):
        self.table = table or {}
        self.default = default
        self.value_calls = 0
        self.logit_calls = 0

    def _lookup(self, vector) -> float:
        key = tuple(int(round(float(x))) for x in vector)
        return float(self.table.get(key, self.default))

    def values(self, vectors):
        self.value_calls += 1
        return [self._lookup(v) for v in vectors]

    def logits(self, vectors):
        self.logit_calls += 1
        return [self._lookup(v) for v in vectors]


def _fake_vectorize(board, white_off, black_off, *, perspective=1, **kwargs):
    """``gnubg_er.vectorize`` yerine 4 elemanli isaret vektoru."""
    return [float(board[0]), float(white_off), float(black_off), float(perspective)]


def _case(turn: int, dice=(3, 4), board=None, white_off=0, black_off=0):
    return {
        "name": "live",
        "board": list(board if board is not None else [0] * 26),
        "turn": int(turn),
        "dice": [int(dice[0]), int(dice[1])],
        "whiteOff": int(white_off),
        "blackOff": int(black_off),
        "maxSteps": 1,
        "afterStates": [],
    }


# ----------------------------------------------------------------------
# roll_correction
# ----------------------------------------------------------------------


def test_409_roll_correction_is_centered_for_constant_table():
    """Sabit tablo -> her zar icin duzeltme **sifir** (merkezleme)."""
    table = [0.25] * len(er_paths.DICE_ROLLS)
    for dice in er_paths.DICE_ROLLS:
        assert luck_adjust.roll_correction(table, dice) == pytest.approx(0.0)


def test_410_roll_correction_matches_manual_weighting():
    """``D = q(R) - sum_r p(r) q(r)``; cift 1/36, diger 2/36."""
    table = [float(i) for i in range(len(er_paths.DICE_ROLLS))]
    total = sum(w * v for w, v in zip(er_paths.DICE_WEIGHTS, table))
    mean = total / 36.0
    # (1,1) ilk girdi, agirlik 1
    assert luck_adjust.roll_correction(table, (1, 1)) == pytest.approx(0.0 - mean)
    # (1,2) ikinci girdi, agirlik 2
    assert luck_adjust.roll_correction(table, (2, 1)) == pytest.approx(1.0 - mean)
    # (6,6) son girdi
    assert luck_adjust.roll_correction(table, (6, 6)) == pytest.approx(20.0 - mean)


def test_411_roll_correction_rejects_wrong_table_length():
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.roll_correction([0.0] * 20, (1, 1))


def test_412_roll_correction_rejects_invalid_dice():
    table = [0.0] * len(er_paths.DICE_ROLLS)
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.roll_correction(table, (0, 7))


# ----------------------------------------------------------------------
# roll_table
# ----------------------------------------------------------------------


def _patch_states(monkeypatch, mapping):
    """``refgen.legal_after_states`` yerine zar -> afterstate listesi."""

    def fake(board, turn, dice, white_off, black_off):
        key = (int(dice[0]), int(dice[-1]))
        states = mapping.get(key, set())
        return (1 if states else 0), set(states)

    monkeypatch.setattr(luck_adjust.refgen, "legal_after_states", fake)
    monkeypatch.setattr(luck_adjust.gnubg_er, "vectorize", _fake_vectorize)


def test_413_roll_table_picks_reference_move_by_opponent_value(monkeypatch):
    """Referans hamle ``-V_rakip``'i **en buyuk** yapan (yani ``V_rakip`` en kucuk)."""
    # (1,1) icin iki aday: board[0]=1 -> V_rakip 0.9, board[0]=2 -> V_rakip 0.1
    _patch_states(monkeypatch, {(1, 1): {((1,) + (0,) * 25, 0, 0), ((2,) + (0,) * 25, 0, 0)}})
    scorer = FakeScorer({(1, 0, 0, -1): 0.9, (2, 0, 0, -1): 0.1})
    table = luck_adjust.roll_table(scorer, _case(turn=1), ref_path="value")
    assert len(table) == len(er_paths.DICE_ROLLS)
    # (1,1) -> -0.1 (en iyi hamle), diger zarlar zorunlu pas -> -V_rakip(tahta)
    assert table[0] == pytest.approx(-0.1)


def test_414_roll_table_terminal_move_uses_exact_award(monkeypatch):
    """Terminal hamlede deger kafasi degil **oyun kurali** kullanilir."""
    _patch_states(monkeypatch, {(1, 1): {((3,) + (0,) * 25, 15, 0)}})
    monkeypatch.setattr(luck_adjust.gnubg_er, "vectorize", _fake_vectorize)
    monkeypatch.setattr(
        luck_adjust.er_paths, "terminal_equity", lambda b, w, k, turn: 2.0
    )
    scorer = FakeScorer({(3, 15, 0, -1): -0.5})
    table = luck_adjust.roll_table(scorer, _case(turn=1), ref_path="value")
    assert table[0] == pytest.approx(2.0)


def test_415_roll_table_forced_pass_negates_opponent_value(monkeypatch):
    """Hamle yoksa devam degeri ``-V_rakip(ayni tahta)``."""
    _patch_states(monkeypatch, {})
    board = [7] + [0] * 25
    scorer = FakeScorer({(7, 0, 0, -1): 0.4})
    table = luck_adjust.roll_table(
        scorer, _case(turn=1, board=board), ref_path="value"
    )
    assert table == pytest.approx([-0.4] * len(er_paths.DICE_ROLLS))


def test_416_roll_table_policy_reference_uses_logits(monkeypatch):
    """``ref_path='policy'`` hamleyi politika logit'i ile secer."""
    _patch_states(monkeypatch, {(1, 1): {((1,) + (0,) * 25, 0, 0), ((2,) + (0,) * 25, 0, 0)}})
    # Deger kafasi 1'i, politika kafasi 2'yi tercih ediyor.
    scorer = FakeScorer({(1, 0, 0, -1): 0.1, (2, 0, 0, -1): 0.9})
    table = luck_adjust.roll_table(scorer, _case(turn=1), ref_path="policy")
    assert scorer.logit_calls >= 1
    assert table[0] == pytest.approx(-0.9)


def test_417_roll_table_rejects_unknown_reference():
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.roll_table(FakeScorer(), _case(turn=1), ref_path="bogus")


# ----------------------------------------------------------------------
# summarize
# ----------------------------------------------------------------------


def test_418_summarize_matches_closed_form_standard_error():
    """``SE_adj = sqrt((s_Y^2 + b^2 s_L^2 - 2 b s_YL) / n)``."""
    y = np.array([1.0, -1.0, 2.0, 0.0, 1.5, -0.5])
    l = np.array([0.5, -0.2, 0.9, 0.1, -0.4, 0.3])
    beta = 1.0
    stats = luck_adjust.summarize(y, l, beta=beta, resamples=200, seed=1)
    z = y - beta * l
    assert stats["ppg"] == pytest.approx(float(y.mean()))
    assert stats["ppgAdjusted"] == pytest.approx(float(z.mean()))
    assert stats["ppgStdError"] == pytest.approx(float(y.std(ddof=1) / np.sqrt(y.size)))
    assert stats["ppgAdjustedStdError"] == pytest.approx(
        float(z.std(ddof=1) / np.sqrt(z.size))
    )
    assert stats["pairs"] == 6
    assert stats["games"] == 12


def test_419_summarize_zero_luck_equals_raw():
    """Sans sifirsa duzeltilmis olcum ham olcume **esit** olur."""
    y = np.array([1.0, -2.0, 3.0, 0.5])
    l = np.zeros_like(y)
    stats = luck_adjust.summarize(y, l, resamples=200, seed=2)
    assert stats["ppgAdjusted"] == pytest.approx(stats["ppg"])
    assert stats["ppgAdjustedStdError"] == pytest.approx(stats["ppgStdError"])
    assert stats["betaStar"] == pytest.approx(0.0)
    assert stats["seReductionPercent"] == pytest.approx(0.0)


def test_420_summarize_beta_star_is_cov_over_var():
    y = np.array([1.0, -1.0, 2.0, 0.0, 1.5, -0.5])
    l = np.array([0.5, -0.2, 0.9, 0.1, -0.4, 0.3])
    stats = luck_adjust.summarize(y, l, resamples=200, seed=3)
    expected = float(np.cov(y, l, ddof=1)[0, 1] / np.var(l, ddof=1))
    assert stats["betaStar"] == pytest.approx(expected)


def test_421_summarize_rejects_short_sample():
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.summarize([1.0], [0.0])


def test_422_summarize_rejects_length_mismatch():
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.summarize([1.0, 2.0], [0.0])


# ----------------------------------------------------------------------
# LuckTracker
# ----------------------------------------------------------------------


def test_423_tracker_sign_conversion(monkeypatch):
    """A atiyorsa ``+D``, B atiyorsa ``-D`` (A'nin puanindan)."""
    monkeypatch.setattr(
        luck_adjust, "roll_table", lambda scorer, case, ref_path="value": [1.0] + [0.0] * 20
    )
    tracker = luck_adjust.LuckTracker(FakeScorer(), our_side=1)
    tracker(_case(turn=1, dice=(1, 1)))
    ours = tracker.total
    tracker2 = luck_adjust.LuckTracker(FakeScorer(), our_side=1)
    tracker2(_case(turn=-1, dice=(1, 1)))
    assert ours == pytest.approx(-tracker2.total)
    assert ours != pytest.approx(0.0)


def test_424_tracker_accumulates_over_rolls(monkeypatch):
    monkeypatch.setattr(
        luck_adjust, "roll_table", lambda scorer, case, ref_path="value": [1.0] + [0.0] * 20
    )
    tracker = luck_adjust.LuckTracker(FakeScorer(), our_side=1)
    for _ in range(3):
        tracker(_case(turn=1, dice=(1, 1)))
    assert tracker.rolls == 3
    assert tracker.total == pytest.approx(3.0 * (1.0 - 1.0 / 36.0))


# ----------------------------------------------------------------------
# play_game kancasi
# ----------------------------------------------------------------------


def _stuck_chooser(case):
    return 0


def test_425_play_game_calls_on_roll_for_every_ply():
    """Kanca her zar olayinda (zorunlu pas dahil) bir kez cagrilir."""
    calls: list[dict] = []
    result = vs_gnubg.play_game(
        dice_seq=[(3, 4)] * 6,
        our_side=1,
        our_choose=_stuck_chooser,
        gnubg_choose=_stuck_chooser,
        max_plies=6,
        allow_unfinished=True,
        on_roll=calls.append,
    )
    assert len(calls) == result["plies"] == 6
    assert all("dice" in c and "turn" in c for c in calls)


def test_426_play_game_without_hook_is_unchanged():
    """``on_roll=None`` iken davranis bit-ozdes (ek maliyet sifir)."""
    a = vs_gnubg.play_game(
        dice_seq=[(3, 4)] * 6,
        our_side=1,
        our_choose=_stuck_chooser,
        gnubg_choose=_stuck_chooser,
        max_plies=6,
        allow_unfinished=True,
    )
    b = vs_gnubg.play_game(
        dice_seq=[(3, 4)] * 6,
        our_side=1,
        our_choose=_stuck_chooser,
        gnubg_choose=_stuck_chooser,
        max_plies=6,
        allow_unfinished=True,
        on_roll=None,
    )
    assert a == b


# ----------------------------------------------------------------------
# Determinizm / is parcacigi bagimsizligi
# ----------------------------------------------------------------------


def _pair(task, max_plies=4):
    scorer = FakeScorer(default=0.0)
    return luck_adjust._play_pair_with_luck(
        task, _stuck_chooser, _stuck_chooser, scorer, "value", max_plies
    )


def test_427_play_pair_is_deterministic():
    """Ayni gorev iki kez -> **ayni** puan ve sans."""
    first = _pair((3, 7))
    second = _pair((3, 7))
    assert first == second


def test_428_play_pair_is_independent_of_task_order():
    """Zar dizisi yalniz ``(tohum, cift)``'ten turer; sira/is parcacigi etkilemez."""
    alone = _pair((3, 7))
    for pair in (0, 1, 2):
        _pair((pair, 7))
    after = _pair((3, 7))
    assert alone == after


# ----------------------------------------------------------------------
# Denetim noktasi
# ----------------------------------------------------------------------


def test_429_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "luck.ckpt.jsonl"
    key = luck_adjust._checkpoint_key(
        Path("m.onnx"), "search1", 2, 5, 200, "value", 1.0
    )
    result = ([1.0, -1.0], [0.25, -0.25], [10, 12], [True, False])
    with path.open("a", encoding="utf-8") as handle:
        luck_adjust._append_checkpoint(handle, key, 4, result)
    loaded = luck_adjust._load_checkpoint(path, key)
    assert loaded[4] == result


def test_430_checkpoint_key_mismatch_raises(tmp_path):
    path = tmp_path / "luck.ckpt.jsonl"
    key = luck_adjust._checkpoint_key(
        Path("m.onnx"), "search1", 2, 5, 200, "value", 1.0
    )
    other = luck_adjust._checkpoint_key(
        Path("m.onnx"), "search1", 2, 5, 200, "policy", 1.0
    )
    with path.open("a", encoding="utf-8") as handle:
        luck_adjust._append_checkpoint(handle, key, 0, ([0.0, 0.0], [0.0, 0.0], [1, 1], [True, True]))
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust._load_checkpoint(path, other)


# ----------------------------------------------------------------------
# Rapor / karar
# ----------------------------------------------------------------------


def _report(**overrides):
    base = {
        "model": "m.onnx",
        "path": "search1",
        "referencePath": "value",
        "gnubgPlies": 2,
        "workers": 4,
        "seed": 0,
        "beta": 1.0,
        "betaStar": 0.9,
        "pairs": 100,
        "games": 200,
        "ppg": -0.2,
        "ppgStdError": 0.02,
        "ppgCiLow": -0.24,
        "ppgCiHigh": -0.16,
        "ppgBootstrapCiLow": -0.24,
        "ppgBootstrapCiHigh": -0.16,
        "ppgAdjusted": -0.15,
        "ppgAdjustedStdError": 0.01,
        "ppgAdjustedCiLow": -0.17,
        "ppgAdjustedCiHigh": -0.13,
        "ppgAdjustedBootstrapCiLow": -0.17,
        "ppgAdjustedBootstrapCiHigh": -0.13,
        "luckMean": 0.0,
        "luckStd": 1.2,
        "scoreStd": 2.0,
        "adjustedStd": 1.0,
        "correlation": 0.6,
        "varianceRatio": 4.0,
        "seReductionPercent": 50.0,
        "seReductionFactor": 2.0,
        "meanPlies": 54.0,
        "unfinished": 0,
        "unfinishedRate": 0.0,
        "resumedPairs": 0,
    }
    base.update(overrides)
    return base


def test_431_markdown_reports_both_estimates():
    md = luck_adjust.build_markdown(_report())
    assert "Sans-duzeltilmis" in md
    assert "-0.2000" in md and "-0.1500" in md
    assert "SE azalmasi" in md
    assert "50.0%" in md


def test_432_verdict_uses_adjusted_estimate(monkeypatch):
    """Karar **duzeltilmis** ppg uzerinden verilir; ham deger ayrica raporlanir."""
    seen: list[tuple] = []

    def fake_verdict(ppg, low, high, margin):
        seen.append((ppg, low, high, margin))
        return "esdeger" if ppg > -margin else "daha-kotu"

    monkeypatch.setattr(ppg_measure, "equivalence_verdict", fake_verdict)
    monkeypatch.setattr(
        luck_adjust,
        "_play_pair_with_luck",
        lambda *a, **k: ([1.0, 1.0], [0.0, 0.0], [10, 10], [True, True]),
    )
    monkeypatch.setattr(luck_adjust.gnubg_er, "find_gnubg", lambda *a, **k: Path("gnubg"))
    monkeypatch.setattr(
        luck_adjust.gnubg_er, "GnubgSession", lambda *a, **k: _NullSession()
    )
    monkeypatch.setattr(
        luck_adjust.gnubg_er, "OnnxScorer", lambda *a, **k: FakeScorer()
    )
    report = luck_adjust.run_luck_match(
        model_path=Path("m.onnx"),
        games=4,
        path="search1",
        gnubg_plies=2,
        workers=1,
        margin=0.1115,
    )
    assert report["verdict"] == "esdeger"
    assert report["verdictRaw"] == "esdeger"
    assert seen[0][0] == pytest.approx(report["ppgAdjusted"])
    assert seen[1][0] == pytest.approx(report["ppg"])
    assert report["pairs"] == 2
    assert report["games"] == 4


class _NullSession:
    def close(self) -> None:
        pass
# ----------------------------------------------------------------------
# Rakip modlari (gorev emri: self-play, gnubg)
# ----------------------------------------------------------------------


def test_433_run_luck_match_rejects_unknown_opponent():
    with pytest.raises(luck_adjust.LuckError):
        luck_adjust.run_luck_match(
            model_path=Path("m.onnx"), games=2, opponent="xg"
        )


def test_434_self_play_needs_no_gnubg(monkeypatch):
    """``opponent='self'`` gnubg ikilisi aramaz; iki renk de ayni seciciyi kullanir."""
    seen: list[tuple] = []

    def fake_pair(task, our_choose, opponent_choose, scorer, ref_path, max_plies):
        seen.append((our_choose, opponent_choose))
        return ([1.0, -1.0], [0.0, 0.0], [10, 10], [True, True])

    def boom(*args, **kwargs):
        raise AssertionError("self-play'de gnubg cagrilmamali")

    monkeypatch.setattr(luck_adjust, "_play_pair_with_luck", fake_pair)
    monkeypatch.setattr(luck_adjust.gnubg_er, "find_gnubg", boom)
    monkeypatch.setattr(luck_adjust.gnubg_er, "GnubgSession", boom)
    monkeypatch.setattr(luck_adjust.gnubg_er, "OnnxScorer", lambda *a, **k: FakeScorer())
    report = luck_adjust.run_luck_match(
        model_path=Path("m.onnx"), games=4, opponent="self", workers=1
    )
    assert report["opponent"] == "self"
    assert report["gnubgPlies"] == 0
    assert seen and seen[0][0] is seen[0][1]


def test_435_markdown_names_the_opponent():
    md = luck_adjust.build_markdown(_report(opponent="self", gnubgPlies=0))
    assert "self-play" in md
    md = luck_adjust.build_markdown(_report(opponent="gnubg", gnubgPlies=2))
    assert "gnubg 2-ply" in md