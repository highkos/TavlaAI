"""K2: kayitli oyun yeniden oynatma dogrulamasi (Test 228-233).

Kullanicinin ``tespitler.md`` K2 maddesi: ``_single_step_uses_die`` hatasi
buyuk-zar filtresini her tek-adimli sonuca uyguluyordu. Hata tetiklendiginde
aday kumesi bosalir ve oyun **pas** yazar; yani kirlenen kararlar egitimden
sessizce duser ve kayitli veri temiz *gorunur*. Bu yuzden kaydin kendi ic
tutarliligi denetlenir.

Kritik semantik: ``BackgammonSearch.SearchNode`` yasal hamle yokken listeye
bir **pas afterstate'i** ekler (``list.AddPass(s)``), yani pas kararinin
``CandidateCount`` degeri **1**'dir. Beklenen budur; 1'den farkli olmasi
hatanin dogrudan kanitidir.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import replay_verify as rv  # noqa: E402
import shards  # noqa: E402


def _vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(shards.VECTOR_SIZE).astype(np.float32)


def _move_dec(mover: int, cands: list[np.ndarray], chosen: int, *, learner: bool = True):
    return shards.DecisionRecord(
        mover=mover,
        flags=shards.DEC_IS_LEARNER if learner else 0,
        candidate_total=len(cands),
        search_value=0.0,
        chosen_vector=cands[chosen].copy(),
        q=np.zeros(len(cands), dtype=np.float32),
        policy_target_cs=np.full(len(cands), 1.0 / len(cands), dtype=np.float32),
        cand_vectors=np.stack(cands),
    )


def _pass_dec(mover: int, *, candidate_total: int = 1):
    """Pas karari: ``AddPass`` tek aday ekler, aday listesi loglanmaz."""
    return shards.DecisionRecord(
        mover=mover,
        flags=shards.DEC_IS_PASS | shards.DEC_IS_LEARNER,
        candidate_total=candidate_total,
        search_value=0.0,
        chosen_vector=_vec(99),
        q=None,
        policy_target_cs=None,
        cand_vectors=None,
    )


def _game(game_id: int, decisions) -> shards.GameRecord:
    game = shards.GameRecord(game_id, 1, 0, 1)
    game.decisions = list(decisions)
    game.winner = 1
    game.result_type = 0
    game.result_points = 1
    return game


def test_228_clean_game_is_clean():
    cands = [_vec(1), _vec(2), _vec(3)]
    counts = rv.verify_games([_game(1, [_move_dec(1, cands, 0), _pass_dec(-1)])])
    assert counts.games == 1
    assert counts.decisions == 2
    assert counts.moves == 1
    assert counts.passes == 1
    assert counts.pass_with_candidates == 0
    assert counts.pass_without_candidates == 1
    assert counts.chosen_checked == 1
    assert counts.chosen_not_in_candidates == 0
    assert counts.clean is True


def test_229_pass_with_more_than_one_candidate_is_flagged():
    """Hatanin dogrudan kaniti: yasal hamle varken pas yazilmis."""
    counts = rv.verify_games([_game(7, [_pass_dec(1, candidate_total=5)])])
    assert counts.pass_with_candidates == 1
    assert counts.pass_without_candidates == 0
    assert counts.clean is False
    assert counts.affected_games == [7]


def test_230_move_without_candidates_is_flagged():
    dec = shards.DecisionRecord(
        mover=1,
        flags=shards.DEC_IS_LEARNER,
        candidate_total=0,
        search_value=0.0,
        chosen_vector=_vec(4),
    )
    counts = rv.verify_games([_game(3, [dec])])
    assert counts.move_without_candidates == 1
    assert counts.clean is False


def test_231_chosen_not_in_candidates_is_flagged():
    cands = [_vec(1), _vec(2)]
    dec = _move_dec(1, cands, 0)
    dec.chosen_vector = _vec(42)  # aday kumesinde degil
    counts = rv.verify_games([_game(5, [dec])])
    assert counts.chosen_checked == 1
    assert counts.chosen_not_in_candidates == 1
    assert counts.clean is False


def test_232_capped_candidate_list_skips_chosen_check():
    """``dup_cap`` kesilmis kumede secilen aday loglanmamis olabilir: denetlenmez."""
    cands = [_vec(1), _vec(2)]
    dec = _move_dec(1, cands, 0)
    dec.candidate_total = 9  # toplam 9, yalnizca 2'si loglanmis
    dec.chosen_vector = _vec(42)
    counts = rv.verify_games([_game(6, [dec])])
    assert counts.chosen_checked == 0
    assert counts.chosen_not_in_candidates == 0
    assert counts.clean is True


def test_233_shard_roundtrip_and_markdown(tmp_path):
    cands = [_vec(1), _vec(2)]
    games = [
        _game(1, [_move_dec(1, cands, 1), _pass_dec(-1)]),
        _game(2, [_pass_dec(1, candidate_total=3)]),
    ]
    path = tmp_path / "s.bgsp"
    shards.write_shard(path, shards.ShardHeader(), games)

    counts = rv.verify_shard(path)
    assert counts.shards == 1
    assert counts.games == 2
    assert counts.pass_with_candidates == 1
    assert counts.pass_candidate_total_hist == {1: 1, 3: 1}
    assert counts.clean is False

    text = rv.build_markdown(counts, source=str(path))
    assert "KIRLI" in text
    assert "1 -> 1, 3 -> 1" in text

    payload = counts.to_dict()
    assert payload["clean"] is False
    assert payload["passCandidateTotalHist"] == {"1": 1, "3": 1}


def test_234_verify_shard_dir_aggregates(tmp_path):
    cands = [_vec(1), _vec(2)]
    for k in range(3):
        shards.write_shard(
            tmp_path / ("s%d.bgsp" % k),
            shards.ShardHeader(),
            [_game(k, [_move_dec(1, cands, 0)])],
        )
    counts = rv.verify_shard_dir(tmp_path)
    assert counts.shards == 3
    assert counts.games == 3
    assert counts.moves == 3
    assert counts.clean is True
    # limit ilk N dosyayi alir
    limited = rv.verify_shard_dir(tmp_path, limit=2)
    assert limited.shards == 2
