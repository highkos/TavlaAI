# -*- coding: utf-8 -*-
"""Faz 7-R Asama R-B testleri (Test 128-132).

Korpus v2'nin v1'in dort kusurunu gercekten kapattigini **olcer**; iddiayi
tekrarlamaz. Her test ``ASSUMPTIONS.md`` F7-47'deki bir kusura karsilik gelir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_DIR.parent
for path in (str(ML_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import corpus2  # noqa: E402
import er_harness  # noqa: E402
import er_paths  # noqa: E402
import er_power  # noqa: E402


# ----------------------------------------------------------------------
# Yardimcilar
# ----------------------------------------------------------------------


def _synthetic_cases() -> list[dict]:
    """Iki oyun, her biri iki fazda -- bolunme butunlugu icin."""
    from tools import reference_gen as refgen

    cases = []
    specs = [
        ("gA", 0, "contact"),
        ("gA", 1, "race"),
        ("gB", 0, "contact"),
        ("gB", 1, "bar"),
        ("gC", 0, "contact"),
        ("gC", 1, "contact"),
    ]
    for index, (game_id, ply, phase) in enumerate(specs):
        board = list(refgen.START_BOARD)
        cases.append(
            {
                "name": "t-%02d" % index,
                "gameId": game_id,
                "ply": ply,
                "source": corpus2.SOURCE_SELF,
                "phase": phase,
                "board": board,
                "turn": 1,
                "dice": [3, 1],
                "whiteOff": 0,
                "blackOff": 0,
                "maxSteps": 2,
                "afterStates": [
                    {"board": board, "whiteOff": 0, "blackOff": 0},
                    {"board": board, "whiteOff": 0, "blackOff": 0},
                ],
            }
        )
    return cases


# ----------------------------------------------------------------------
# Test 128 -- bolunme oyuna gore
# ----------------------------------------------------------------------


def test_corpus2_split_is_by_game():
    """Test 128: bir oyunun **tum** pozisyonlari ayni bolunmede olmali.

    v1'de bolunme pozisyon duzeyindeydi (``er_harness.assign_splits``); ayni
    oyunun pozisyonlari CAL ve TEST'e dusebiliyordu. Bu, TEST'i sizdirdigi
    icin ER'yi iyimser gosterir.
    """
    cases = _synthetic_cases()
    splits = corpus2.assign_splits_by_game(cases, seed=1234)

    membership: dict[str, str] = {}
    for split_name, names in splits.items():
        for name in names:
            membership[name] = split_name

    assert set(membership) == {c["name"] for c in cases}

    game_split: dict[str, str] = {}
    for case in cases:
        split_name = membership[case["name"]]
        previous = game_split.setdefault(case["gameId"], split_name)
        assert previous == split_name, (
            "oyun %s iki bolunmede: %s ve %s" % (case["gameId"], previous, split_name)
        )


def test_corpus2_split_covers_every_case_exactly_once():
    """Test 128b: bolunmeler toplami vaka sayisina esit, tekrar yok."""
    cases = _synthetic_cases()
    splits = corpus2.assign_splits_by_game(cases, seed=99)
    all_names = [n for names in splits.values() for n in names]
    assert len(all_names) == len(set(all_names)) == len(cases)


# ----------------------------------------------------------------------
# Test 129 -- sizinti filtresi
# ----------------------------------------------------------------------


def test_corpus2_no_leak_from_training():
    """Test 129: egitim kumesindeki tahta korpusta **kalmamali**.

    Filtre ayna/perspektif-kanonik hash kullanir; ayni pozisyon Beyaz'in ya da
    Siyah'in bakis acisindan yazilsa da yakalanir.
    """
    from tools import reference_gen as refgen

    board = list(refgen.START_BOARD)
    mirrored = corpus2.mirror_board(board)

    cases = [
        {
            "name": "leak-1",
            "board": board,
            "whiteOff": 0,
            "blackOff": 0,
        },
        {
            "name": "leak-2",
            "board": mirrored,
            "whiteOff": 0,
            "blackOff": 0,
        },
        {
            "name": "clean-1",
            "board": [0] * 26,
            "whiteOff": 0,
            "blackOff": 0,
        },
    ]

    forbidden = {corpus2.board_hash(board, 0, 0)}
    result = corpus2.leak_filter(cases, forbidden)

    assert result.removed_count == 2, "ayna da yakalanmali"
    assert [c["name"] for c in result.kept] == ["clean-1"]
    assert result.to_dict()["removed"] == 2


def test_corpus2_leak_filter_reports_zero_explicitly():
    """Test 129b: sizinti yoksa da sayi **acikca** raporlanir (Kural 6)."""
    cases = [{"name": "a", "board": [0] * 26, "whiteOff": 0, "blackOff": 0}]
    result = corpus2.leak_filter(cases, set())
    payload = result.to_dict()
    assert payload["removed"] == 0
    assert payload["kept"] == 1
    assert payload["removedNames"] == []


def test_corpus2_mirror_hash_is_perspective_invariant():
    """Test 129c: ayna hash'i degistirmemeli."""
    from tools import reference_gen as refgen

    board = list(refgen.START_BOARD)
    assert corpus2.board_hash(board, 0, 0) == corpus2.board_hash(
        corpus2.mirror_board(board), 0, 0
    )
    assert corpus2.board_hash(board, 3, 5) == corpus2.board_hash(
        corpus2.mirror_board(board), 5, 3
    )


# ----------------------------------------------------------------------
# Test 130 -- contact payi
# ----------------------------------------------------------------------


def test_corpus2_contact_share():
    """Test 130: baslik kumesinde contact **>= %60** olmali.

    v1'de contact %19,5'ti (39/200) ve bearoff %18,5 -- yani korpusun buyuk
    kismi urunde **tam veritabanindan** cozulen ya da gercek oyunda **nadir**
    fazlardan geliyordu (F7-47).
    """
    assert corpus2.CONTACT_SHARE_MIN == pytest.approx(0.60)

    shares = dict(corpus2.PHASE_SHARES)
    assert shares["contact"] >= corpus2.CONTACT_SHARE_MIN
    assert sum(shares.values()) == pytest.approx(1.0)

    # Teshis fazlari baslik kumesine girmemeli.
    assert "bearoff" in corpus2.DIAGNOSTIC_PHASES
    assert "closed" in corpus2.DIAGNOSTIC_PHASES
    for phase in corpus2.DIAGNOSTIC_PHASES:
        assert phase not in corpus2.HEADLINE_PHASES


def test_corpus2_headline_selection_is_stratified():
    """Test 130b: secim katmanli -- her baslik fazindan pay kadar vaka alinir."""
    from tools import reference_gen as refgen

    board = list(refgen.START_BOARD)
    pool = []
    for phase, count in (("contact", 100), ("bar", 100), ("race", 100), ("bearoff", 50)):
        for i in range(count):
            pool.append(
                {
                    "name": "%s-%03d" % (phase, i),
                    "gameId": "%s-g%03d" % (phase, i),
                    "ply": i,
                    "source": corpus2.SOURCE_SELF,
                    "phase": phase,
                    "board": board,
                }
            )

    selected, diagnostic, shortfall = corpus2._select_headline(pool, 100)
    counts = corpus2._phase_counts(selected)

    assert len(selected) == 100
    assert counts["contact"] == 60
    assert counts["bar"] == 25
    assert counts["race"] == 15
    assert counts["bearoff"] == 0
    assert shortfall == {}
    # Teshis kumesi secilenlerle cakismamali ve tum bearoff'lari icermeli.
    selected_names = {c["name"] for c in selected}
    diagnostic_names = {c["name"] for c in diagnostic}
    assert not (selected_names & diagnostic_names)
    assert sum(1 for c in diagnostic if c["phase"] == "bearoff") == 50


def test_corpus2_headline_shortfall_is_reported():
    """Test 130c: bir fazda yeterli vaka yoksa eksik **acikca** raporlanir."""
    from tools import reference_gen as refgen

    board = list(refgen.START_BOARD)
    pool = [
        {
            "name": "contact-%03d" % i,
            "gameId": "g%03d" % i,
            "ply": i,
            "source": corpus2.SOURCE_SELF,
            "phase": "contact",
            "board": board,
        }
        for i in range(100)
    ]
    selected, _diagnostic, shortfall = corpus2._select_headline(pool, 100)
    assert shortfall.get("bar", 0) > 0
    assert shortfall.get("race", 0) > 0
    assert len(selected) == 100


# ----------------------------------------------------------------------
# Test 131 -- uc yol raporlama
# ----------------------------------------------------------------------


def test_er_reports_three_paths():
    """Test 131: ER **uc** oynanis yolu icin ayri ayri raporlanmali.

    Tek yol raporlamak, "ER 0,0533" gibi bir sayinin hangi oynanisa ait
    oldugunu belirsiz birakir (F7-46). Urun ``ProductionDepthPly = 1`` iken
    1-ply arama yapar; olculen yol politika argmax'iydi.
    """
    assert er_paths.PLAY_PATHS == ("policy", "value", "search1")
    assert set(er_paths.PATH_LABELS) == set(er_paths.PLAY_PATHS)

    report = {
        "model": "m.onnx",
        "referee": {"command": "eval", "column": "2", "plies": 2, "prob": "equity"},
        "caseCount": 10,
        "phaseWeights": {"contact": 0.6},
        "paths": {},
    }
    for path in er_paths.PLAY_PATHS:
        report["paths"][path] = {
            "path": path,
            "count": 10,
            "mean": 0.05,
            "median": 0.04,
            "maximum": 0.2,
            "exactMatchRate": 0.5,
            "sigma": 0.1,
            "sigmaCiLow": 0.08,
            "sigmaCiHigh": 0.13,
            "ciLow": 0.02,
            "ciHigh": 0.08,
            "standardError": 0.03,
            "phaseMeans": {"contact": 0.05},
            "phaseCounts": {"contact": 10},
            "weightedMean": 0.05,
            "terminalCandidates": 0,
        }

    markdown = er_paths.build_markdown(report)
    for path in er_paths.PLAY_PATHS:
        assert "`%s`" % path in markdown
    assert "Hakem sozlesmesi" in markdown
    assert "Agirlikli" in markdown


def test_er_path_measurement_requires_weights_for_weighted_mean():
    """Test 131b: agirlik yoksa agirlikli ortalama ham ortalamaya duser."""
    measurement = er_paths._summarize_path(
        "policy", [0.1, 0.2, 0.3], ["contact", "contact", "race"], {}
    )
    assert measurement.weighted_mean == pytest.approx(measurement.mean)
    assert measurement.phase_counts == {"contact": 2, "race": 1}


def test_er_path_measurement_uses_real_game_weights():
    """Test 131c: agirlikli ortalama gercek oyun paylariyla hesaplanir."""
    measurement = er_paths._summarize_path(
        "policy",
        [0.10, 0.10, 0.40],
        ["contact", "contact", "race"],
        {"contact": 0.75, "race": 0.25},
    )
    expected = 0.10 * 0.75 + 0.40 * 0.25
    assert measurement.weighted_mean == pytest.approx(expected, abs=1e-9)


# ----------------------------------------------------------------------
# Test 132 -- bootstrap GA
# ----------------------------------------------------------------------


def test_er_bootstrap_ci():
    """Test 132: her yol **bootstrap %95 GA** raporlamali (Kural 3).

    Nokta tahmini kanit degildir; GA sifiri iceriyorsa iddia
    ``kanitlanmadi`` olur.
    """
    losses = [0.0, 0.01, 0.02, 0.05, 0.10, 0.15, 0.30, 0.0, 0.02, 0.04]
    measurement = er_paths._summarize_path(
        "policy", losses, ["contact"] * len(losses), {}
    )

    assert measurement.ci_low < measurement.mean < measurement.ci_high
    assert measurement.sigma_ci_low < measurement.sigma < measurement.sigma_ci_high
    assert measurement.count == len(losses)
    assert er_paths.BOOTSTRAP_RESAMPLES >= 10000


def test_er_bootstrap_ci_is_deterministic():
    """Test 132b: ayni girdi ayni GA'yi vermeli (tohum sabit)."""
    losses = [0.0, 0.02, 0.05, 0.11, 0.20]
    a = er_paths._summarize_path("policy", losses, ["contact"] * 5, {})
    b = er_paths._summarize_path("policy", losses, ["contact"] * 5, {})
    assert a.ci_low == b.ci_low
    assert a.ci_high == b.ci_high
    assert a.sigma_ci_high == b.sigma_ci_high


def test_er_bootstrap_ci_widens_with_spread():
    """Test 132c: daha genis yayilim daha genis GA vermeli."""
    tight = er_paths._summarize_path("policy", [0.05] * 20, ["contact"] * 20, {})
    wide = er_paths._summarize_path(
        "policy", [0.0, 0.5] * 10, ["contact"] * 20, {}
    )
    assert (wide.ci_high - wide.ci_low) > (tight.ci_high - tight.ci_low)


# ----------------------------------------------------------------------
# Test 133 -- guc tablosu sigma ust sinirindan
# ----------------------------------------------------------------------


def test_power_uses_sigma_upper_bound():
    """Test 133: gereken n **sigma'nin ust guven sinirindan** hesaplanmali.

    Nokta tahmininden hesaplamak n'i sistematik olarak eksik verir (Kural 4,
    kazananin laneti). ``er_power.required_n_from_upper`` bunu belgeler.
    """
    sigma = 0.10
    sigma_high = 0.13

    rows = corpus2.power_table(sigma_high, deltas=(0.01, 0.02))
    assert len(rows) == 2
    for row in rows:
        assert row["sigmaCiHigh"] == pytest.approx(sigma_high)
        expected = er_power.required_n_from_upper(
            sigma_high, row["deltaMin"], two_sided=False
        )
        assert row["nOneSided"] == expected

    # Ust sinirdan hesaplanan n, nokta tahmininden **buyuk** olmali.
    n_point = er_power.required_n_from_upper(sigma, 0.01, two_sided=False)
    n_upper = er_power.required_n_from_upper(sigma_high, 0.01, two_sided=False)
    assert n_upper > n_point


def test_power_table_rejects_non_positive_sigma():
    """Test 133b: sifir/negatif sigma sessizce gecmemeli (Kural 6)."""
    with pytest.raises(ValueError):
        corpus2.power_table(0.0)
    with pytest.raises(ValueError):
        corpus2.power_table(-0.1)


def test_power_rows_use_sigma_ci_high_not_sigma():
    """Test 133c: ``power_rows`` nokta tahminini **kullanmamali**."""
    report = {
        "paths": {
            "policy": {
                "count": 100,
                "sigma": 0.05,
                "sigmaCiHigh": 0.20,
            }
        }
    }
    rows = er_paths.power_rows(report, deltas=(0.01,))
    assert len(rows) == 1
    row = rows[0]
    assert row["sigmaCiHigh"] == pytest.approx(0.20)
    assert row["nOneSided"] == er_power.required_n_from_upper(
        0.20, 0.01, two_sided=False
    )
    assert row["nOneSided"] > er_power.required_n_from_upper(
        0.05, 0.01, two_sided=False
    )