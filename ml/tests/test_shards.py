"""Faz 4 v3 Bolum 8, Test 4: shard bicimi (v1) - gidis-donus, baslik, gzip, capraz dil."""

from __future__ import annotations

import gzip
import struct

import numpy as np
import pytest

import shards
from conftest import ARTIFACTS

CSHARP_SHARD = ARTIFACTS / "csharp_shard.bgsp"


def _make_decision(rng: np.random.RandomState, mover: int, logged: int, terminal: bool) -> shards.DecisionRecord:
    flags = shards.DEC_IS_LEARNER
    if terminal:
        flags |= shards.DEC_CHOSEN_IS_TERMINAL
    dec = shards.DecisionRecord(
        mover=mover,
        flags=flags,
        candidate_total=logged + 3,
        search_value=float(rng.randn()),
    )
    if not terminal:
        dec.chosen_vector = rng.randn(221).astype(np.float32)
    if logged > 0:
        dec.q = rng.randn(logged).astype(np.float32)
        dec.policy_target_cs = np.abs(rng.randn(logged)).astype(np.float32)
        dec.cand_vectors = rng.randn(logged, 221).astype(np.float32)
    return dec


def _make_games(count: int, seed: int = 5) -> list[shards.GameRecord]:
    rng = np.random.RandomState(seed)
    games = []
    for g in range(count):
        decisions = []
        n = 1 + (g % 4)
        for t in range(n):
            terminal = t == n - 1
            logged = 0 if terminal else 1 + (t % 3)
            decisions.append(_make_decision(rng, 1 if t % 2 == 0 else -1, logged, terminal))
        games.append(
            shards.GameRecord(
                game_id=1000 + g,
                learner_side=g % 3 - 1,
                flags=shards.GAME_FLAG_ABORTED if g == 2 else 0,
                cube_value=1 + (g % 2),
                decisions=decisions,
                winner=1 if g % 2 == 0 else -1,
                result_type=1 + (g % 3),
                result_points=1 + (g % 3),
            )
        )
    return games


def test_header_size_is_32():
    assert shards.HEADER_SIZE == 32
    assert shards.ShardHeader().pack().__len__() == 32


def test_round_trip_bit_exact(tmp_path):
    header = shards.ShardHeader(model_version=9, log_top_candidates=12, flags=3)
    games = _make_games(6)
    path = tmp_path / "round.bgsp"
    shards.write_shard(path, header, games)

    h2, g2 = shards.read_shard(path)
    assert h2 == header
    assert len(g2) == len(games)

    for a, b in zip(games, g2):
        assert a.game_id == b.game_id
        assert a.learner_side == b.learner_side
        assert a.flags == b.flags
        assert a.cube_value == b.cube_value
        assert a.winner == b.winner
        assert a.result_type == b.result_type
        assert a.result_points == b.result_points
        assert len(a.decisions) == len(b.decisions)
        for da, db in zip(a.decisions, b.decisions):
            assert da.mover == db.mover
            assert da.flags == db.flags
            assert da.candidate_total == db.candidate_total
            # search_value float32 olarak saklanir
            assert np.float32(da.search_value) == db.search_value
            if da.chosen_vector is None:
                assert db.chosen_vector is None
            else:
                assert np.array_equal(da.chosen_vector, db.chosen_vector)
            if da.q is None:
                assert db.q is None
            else:
                assert np.array_equal(da.q, db.q)
                assert np.array_equal(da.policy_target_cs, db.policy_target_cs)
                assert np.array_equal(da.cand_vectors, db.cand_vectors)


def test_gzip_round_trip(tmp_path):
    header = shards.ShardHeader(model_version=2)
    games = _make_games(4)
    path = tmp_path / "round.bgsp.gz"
    raw = shards.write_shard(path, header, games, gzip_out=True)

    assert gzip.decompress(path.read_bytes()).__len__() == raw
    h2, g2 = shards.read_shard(path)
    assert h2 == header
    assert len(g2) == len(games)


def test_bad_magic_raises(tmp_path):
    path = tmp_path / "bad.bgsp"
    path.write_bytes(b"XXXX" + b"\x00" * 28)
    with pytest.raises(shards.ShardFormatError):
        shards.read_shard(path)


def test_format_version_mismatch_raises(tmp_path):
    path = tmp_path / "v2.bgsp"
    path.write_bytes(struct.pack("<4sIIIIIII", b"BGSP", 2, 1, 221, 1, 0, 0, 0))
    with pytest.raises(shards.ShardFormatError, match="formatVersion"):
        shards.read_shard(path)


def test_vector_size_mismatch_raises(tmp_path):
    path = tmp_path / "vsz.bgsp"
    path.write_bytes(struct.pack("<4sIIIIIII", b"BGSP", 1, 1, 200, 1, 0, 0, 0))
    with pytest.raises(shards.ShardFormatError, match="vectorSize"):
        shards.read_shard(path)


def test_truncated_shard_raises(tmp_path):
    header = shards.ShardHeader()
    games = _make_games(2)
    path = tmp_path / "trunc.bgsp"
    shards.write_shard(path, header, games)
    raw = path.read_bytes()
    path.write_bytes(raw[:-7])
    with pytest.raises(shards.ShardFormatError):
        shards.read_shard(path)


def test_aborted_games_excluded_from_training_iteration():
    games = _make_games(6)
    seen = {g.game_id for g, _ in shards.iter_learner_decisions(games)}
    assert 1002 not in seen, "aborted oyun egitime girmemeli"
    assert 1000 in seen


def test_learner_flag_filters_decisions():
    games = _make_games(3)
    for game in games:
        for dec in game.decisions:
            assert dec.is_learner
    games[0].decisions[0].flags &= ~shards.DEC_IS_LEARNER
    pairs = list(shards.iter_learner_decisions(games))
    assert all(dec is not games[0].decisions[0] for _, dec in pairs)


@pytest.mark.skipif(not CSHARP_SHARD.is_file(), reason="C# fixture yok (Backgammon.Inference.Tests Shard_CrossLanguageFixture once kosmali)")
def test_reads_csharp_written_shard():
    """C# yazici -> Python okuyucu, bit duzeyinde ayni."""
    header, games = shards.read_shard(CSHARP_SHARD)
    assert header.format_version == 1
    assert header.feature_version == 1
    assert header.vector_size == 221
    assert header.model_version == 77
    assert header.log_top_candidates == 12
    assert len(games) == 3

    g0 = games[0]
    assert g0.game_id == 1
    assert g0.learner_side == 1
    assert g0.cube_value == 1
    assert g0.winner == 1
    assert g0.result_type == 2
    assert g0.result_points == 2
    assert len(g0.decisions) == 2

    d0 = g0.decisions[0]
    assert d0.mover == 1
    assert d0.is_learner
    assert not d0.chosen_is_terminal
    assert d0.candidate_total == 5
    assert d0.logged_count == 2
    assert d0.chosen_vector.shape == (221,)
    assert d0.cand_vectors.shape == (2, 221)
    # C# tarafi bu vektorleri i*0.5 + j*0.25 ile dolduruyor
    want = np.array([0.0 + j * 0.25 for j in range(221)], dtype=np.float32)
    assert np.array_equal(d0.chosen_vector, want)
    assert np.array_equal(d0.q, np.array([0.5, 0.4], dtype=np.float32))
    assert np.allclose(d0.policy_target_cs, [0.8807970779778823, 0.11920292202211755], atol=1e-6)

    d1 = g0.decisions[1]
    assert d1.chosen_is_terminal
    assert d1.chosen_vector is None
    assert d1.logged_count == 0

    assert games[1].is_aborted