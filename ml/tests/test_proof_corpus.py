"""Faz 7 Bolum 4.5: kanit korpusu testleri (``ml/proof_corpus.py``).

Kanit korpusu sampiyon iddiasinin **orneklemi**dir; bozulursa iddia da bozulur.
Bu yuzden dosya dondurulmustur: SHA-256 ozeti testte sabittir.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

import er_harness
import gnubg_er
import proof_corpus as pc
import tools.reference_gen as refgen

#: Dondurulmus korpusun SHA-256 ozeti (``ml/artifacts/stage_a_measurement.md``).
FROZEN_SHA256 = "17657950ea9cf260115e3689f5fe46be2431e4ec65eb9dd52c1548b65558f828"

#: Kova sayisi: 5 faz x 4 pip kovasi.
EXPECTED_BUCKETS = 20


# ---------------------------------------------------------------------------
# Pip farki ve kova etiketleri
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "difference,label",
    [
        (0, "0-10"),
        (9, "0-10"),
        (-9, "0-10"),
        (10, "10-25"),
        (-10, "10-25"),
        (24, "10-25"),
        (25, "25-50"),
        (-49, "25-50"),
        (50, "50+"),
        (-500, "50+"),
    ],
)
def test_pip_bucket_label(difference: int, label: str) -> None:
    assert pc.pip_bucket_label(difference) == label


def test_pip_bucket_label_covers_every_integer() -> None:
    for value in range(-400, 401):
        assert pc.pip_bucket_label(value)


def test_bucket_key_format() -> None:
    assert pc.bucket_key("contact", 7) == "contact|0-10"
    assert pc.bucket_key("race", -60) == "race|50+"


def test_all_bucket_keys_are_unique_and_complete() -> None:
    keys = pc.all_bucket_keys()
    assert len(keys) == EXPECTED_BUCKETS
    assert len(set(keys)) == EXPECTED_BUCKETS
    for phase in pc.PROOF_PHASES:
        for low, high in pc.PIP_BUCKETS:
            label = "%d+" % low if high is None else "%d-%d" % (low, high)
            assert "%s|%s" % (phase, label) in keys


def test_required_phases_are_subset_of_proof_phases() -> None:
    assert set(pc.REQUIRED_PHASES) <= set(pc.PROOF_PHASES)
    assert set(pc.EXTRA_PHASES) <= set(pc.PROOF_PHASES)
    assert not set(pc.REQUIRED_PHASES) & set(pc.EXTRA_PHASES)


# ---------------------------------------------------------------------------
# Kotalar
# ---------------------------------------------------------------------------


def test_bucket_quotas_sum_to_total() -> None:
    quotas = pc.bucket_quotas(pc.TARGET_POSITIONS)
    assert sum(quotas.values()) == pc.TARGET_POSITIONS
    assert len(quotas) == EXPECTED_BUCKETS


def test_bucket_quotas_respect_minimum() -> None:
    quotas = pc.bucket_quotas(pc.TARGET_POSITIONS)
    for key, quota in quotas.items():
        assert quota >= pc.MIN_PER_BUCKET, key


def test_bucket_quotas_reject_too_small_total() -> None:
    with pytest.raises(pc.ProofCorpusError):
        pc.bucket_quotas(EXPECTED_BUCKETS * (pc.MIN_PER_BUCKET - 1))


def test_bucket_quotas_are_balanced() -> None:
    quotas = pc.bucket_quotas(pc.TARGET_POSITIONS)
    values = list(quotas.values())
    assert max(values) - min(values) <= 1


# ---------------------------------------------------------------------------
# Pip farki ve faz siniflandirmasi
# ---------------------------------------------------------------------------


def test_pip_difference_start_position_is_zero() -> None:
    assert pc.pip_difference(refgen.START_BOARD, 1) == 0
    assert pc.pip_difference(refgen.START_BOARD, -1) == 0


def test_phase_of_matches_er_harness() -> None:
    rng = random.Random(4242)
    for _ in range(200):
        board = [0] * 26
        for _ in range(15):
            board[rng.randint(1, 24)] += 1
        for _ in range(15):
            board[rng.randint(1, 24)] -= 1
        for turn in (1, -1):
            assert pc._phase_of(board, turn) == er_harness.classify_phase(board, turn)


def test_phase_of_detects_bar() -> None:
    board = [0] * 26
    board[0] = 1
    board[5] = 14
    board[20] = -15
    assert pc._phase_of(board, 1) == "bar"


# ---------------------------------------------------------------------------
# Dondurulmus dosya
# ---------------------------------------------------------------------------


def test_proof_corpus_file_exists() -> None:
    assert pc.PROOF_CORPUS_PATH.is_file(), pc.PROOF_CORPUS_PATH


def test_proof_corpus_sha256_is_frozen() -> None:
    assert pc.sha256_of(pc.PROOF_CORPUS_PATH) == FROZEN_SHA256


def test_proof_corpus_schema() -> None:
    data = pc.load_corpus()
    assert data["schemaVersion"] == pc.SCHEMA_VERSION
    assert data["generatedBy"] == pc.GENERATOR
    assert data["seed"] == pc.PROOF_SEED
    assert data["targetPositions"] == pc.TARGET_POSITIONS
    assert data["minPerBucket"] == pc.MIN_PER_BUCKET
    assert data["count"] == pc.TARGET_POSITIONS
    assert len(data["cases"]) == pc.TARGET_POSITIONS


def test_proof_corpus_stratification_is_complete() -> None:
    data = pc.load_corpus()
    stratification = data["stratification"]
    assert set(stratification) == set(pc.all_bucket_keys())
    for key, value in stratification.items():
        assert value >= pc.MIN_PER_BUCKET, key
    assert sum(stratification.values()) == pc.TARGET_POSITIONS


def test_proof_corpus_required_phases_have_minimum() -> None:
    data = pc.load_corpus()
    per_phase: dict[str, int] = {}
    for case in data["cases"]:
        per_phase[case["phase"]] = per_phase.get(case["phase"], 0) + 1
    for phase in pc.REQUIRED_PHASES:
        assert per_phase.get(phase, 0) >= pc.MIN_PER_BUCKET, phase
    for phase in pc.EXTRA_PHASES:
        assert per_phase.get(phase, 0) >= pc.MIN_PER_BUCKET, phase


def test_proof_corpus_case_fields() -> None:
    data = pc.load_corpus()
    for case in data["cases"]:
        assert set(case) == {
            "name",
            "phase",
            "pipBucket",
            "pipDiff",
            "board",
            "turn",
            "dice",
            "whiteOff",
            "blackOff",
        }
        assert len(case["board"]) == 26
        assert case["turn"] in (1, -1)
        assert 1 <= len(case["dice"]) <= 4
        assert all(1 <= d <= 6 for d in case["dice"])


def test_proof_corpus_names_are_unique_and_ordered() -> None:
    data = pc.load_corpus()
    names = [case["name"] for case in data["cases"]]
    assert names == ["p-%04d" % index for index in range(len(names))]


def test_proof_corpus_phase_and_bucket_are_consistent() -> None:
    data = pc.load_corpus()
    for case in data["cases"]:
        assert case["phase"] == pc._phase_of(case["board"], case["turn"]), case["name"]
        assert case["pipDiff"] == pc.pip_difference(case["board"], case["turn"]), case["name"]
        assert case["pipBucket"] == pc.pip_bucket_label(case["pipDiff"]), case["name"]


def test_proof_corpus_has_no_duplicate_boards() -> None:
    data = pc.load_corpus()
    seen = set()
    for case in data["cases"]:
        key = (tuple(case["board"]), case["whiteOff"], case["blackOff"])
        assert key not in seen, case["name"]
        seen.add(key)


def test_proof_corpus_piece_counts_are_15_15() -> None:
    data = pc.load_corpus()
    for case in data["cases"]:
        white, black = gnubg_er.case_piece_counts(case)
        assert (white, black) == (15, 15), case["name"]


def test_proof_corpus_afterstates_are_materialized() -> None:
    cases = pc.load_cases()
    assert len(cases) == pc.TARGET_POSITIONS
    for case in cases:
        assert len(case["afterStates"]) >= 2, case["name"]
        assert "maxSteps" in case


def test_proof_corpus_all_cases_are_usable() -> None:
    usable, skipped = gnubg_er.split_cases(pc.load_cases())
    assert len(usable) == pc.TARGET_POSITIONS
    assert skipped == []


def test_proof_corpus_does_not_store_afterstates() -> None:
    data = pc.load_corpus()
    for case in data["cases"]:
        assert "afterStates" not in case


# ---------------------------------------------------------------------------
# Uretim determinizmi
# ---------------------------------------------------------------------------


def test_race_candidates_are_deterministic() -> None:
    first = pc._race_candidates(pc.PROOF_SEED, 50)
    second = pc._race_candidates(pc.PROOF_SEED, 50)
    assert first == second


def test_race_candidates_cover_all_pip_buckets() -> None:
    pool = pc._race_candidates(pc.PROOF_SEED, 2000)
    buckets = {pc.bucket_key("race", pc.pip_difference(p[0], p[1])) for p in pool}
    assert buckets == {"race|%s" % label for label in ("0-10", "10-25", "25-50", "50+")}


def test_bar_candidates_have_a_checker_on_the_bar() -> None:
    for board, _turn, _dice, _wo, _bo in pc._bar_candidates(pc.PROOF_SEED, 20):
        assert board[0] > 0 or board[25] < 0


def test_closed_candidates_have_closed_home() -> None:
    for board, turn, _dice, _wo, _bo in pc._closed_candidates(pc.PROOF_SEED, 20):
        assert er_harness.is_closed_home(board, -turn)


# ---------------------------------------------------------------------------
# Dosya islemleri
# ---------------------------------------------------------------------------


def test_write_and_load_roundtrip(tmp_path: Path) -> None:
    corpus = {
        "schemaVersion": pc.SCHEMA_VERSION,
        "generatedBy": pc.GENERATOR,
        "seed": 1,
        "targetPositions": 1,
        "minPerBucket": 1,
        "pipBuckets": [[0, 10]],
        "requiredPhases": ["contact"],
        "extraPhases": [],
        "stratification": {"contact|0-10": 1},
        "count": 1,
        "cases": [
            {
                "name": "p-0000",
                "phase": "contact",
                "pipBucket": "0-10",
                "pipDiff": 0,
                "board": list(refgen.START_BOARD),
                "turn": 1,
                "dice": [3, 5],
                "whiteOff": 0,
                "blackOff": 0,
            }
        ],
    }
    path = tmp_path / "corpus.json"
    digest = pc.write_corpus(corpus, path)
    assert digest == pc.sha256_of(path)
    assert len(digest) == 64
    loaded = pc.load_corpus(path)
    assert loaded["count"] == 1
    assert loaded["cases"][0]["name"] == "p-0000"


def test_load_corpus_rejects_bad_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schemaVersion": 99, "cases": []}), encoding="utf-8")
    with pytest.raises(pc.ProofCorpusError):
        pc.load_corpus(path)


def test_load_corpus_rejects_missing_cases(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schemaVersion": pc.SCHEMA_VERSION}), encoding="utf-8")
    with pytest.raises(pc.ProofCorpusError):
        pc.load_corpus(path)


def test_materialize_afterstates_is_idempotent() -> None:
    case = {
        "name": "x",
        "board": list(refgen.START_BOARD),
        "turn": 1,
        "dice": [3, 5],
        "whiteOff": 0,
        "blackOff": 0,
    }
    once = pc.materialize_afterstates(case)
    twice = pc.materialize_afterstates(once)
    assert once["afterStates"] == twice["afterStates"]
    assert once["maxSteps"] == twice["maxSteps"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_verify_returns_zero() -> None:
    assert pc.main(["--verify"]) == 0


def test_main_verify_missing_file_returns_two(tmp_path: Path) -> None:
    assert pc.main(["--verify", "--out", str(tmp_path / "nope.json")]) == 2


def test_build_parser_defaults() -> None:
    args = pc.build_parser().parse_args([])
    assert args.seed == pc.PROOF_SEED
    assert args.count == pc.TARGET_POSITIONS
    assert args.verify is False
