"""Faz 7-R Asama R-F: seviye farki (ppg) olcumu testleri (Test 148-157).

R-T34 ``PpgParse_ScoreLine``      -- gercek gnubg skor satiri ayristirilir
R-T35 ``PpgParse_Crawford``       -- Crawford isareti taninir
R-T36 ``PpgParse_MatchDeltas``    -- kumulatif skordan oyun basina puan cikar
R-T37 ``PpgParse_MoneyOutput``    -- X/O -> oyuncu 0/1 eslemesi
R-T38 ``PpgParse_RejectsGarbage`` -- skor/marker yoksa hata (sessiz dusme yok)
R-T39 ``PpgScript_Plies``         -- komut dosyasi derinlikleri ve mac uzunlugunu tasir
R-T40 ``PpgSummary_Cluster``      -- kume bootstrap'i mac ici korelasyonu hesaba katar
R-T41 ``PpgMargin_Derived``       -- m olculen farktan turetilir, GA alt sinirindan
R-T42 ``PpgMargin_Floor``         -- m sifira cokemez
R-T43 ``PpgReport_RequiredGames`` -- gereken n sigma UST sinirindan (Kural 4)
"""

from __future__ import annotations

import math

import pytest

import ppg_measure as pm


#: Gercek gnubg 1.08 ciktisi (5 puanlik mac, 0-ply vs 2-ply).
REAL_MATCH = """
The score (after 1 game) is: gnubg 2, MONSTER 0 (match to 5 points)
The score (after 2 games) is: gnubg 2, MONSTER 1 (match to 5 points)
The score (after 3 games) is: gnubg 4, MONSTER 1 (match to 5 points, Crawford game)
The score (after 4 games) is: gnubg 6, MONSTER 1 (match to 5 points)
gnubg has won the match.
"""

#: Gercek money kosucusu ciktisi.
REAL_MONEY = (
    'PPGJSON {"games": [["O", 1], ["O", 1], ["X", 4], ["X", 1], ["O", 4]], '
    '"seconds": 8.1}'
)


def test_148_ppg_parse_score_line():
    row = pm.parse_score_line(
        "The score (after 3 games) is: gnubg 4, MONSTER 1 (match to 5 points)"
    )
    assert row is not None
    assert row["games"] == 3
    assert row["name0"] == "gnubg"
    assert row["score0"] == 4
    assert row["name1"] == "MONSTER"
    assert row["score1"] == 1
    assert row["length"] == 5
    assert row["crawford"] is False


def test_149_ppg_parse_crawford():
    row = pm.parse_score_line(
        "The score (after 3 games) is: gnubg 4, MONSTER 1 "
        "(match to 5 points, Crawford game)"
    )
    assert row is not None
    assert row["crawford"] is True
    assert pm.parse_score_line("gnubg moves 24/23 13/8.") is None


def test_150_ppg_parse_match_deltas():
    res = pm.parse_match_output(REAL_MATCH, length=5)
    assert res.names == ("gnubg", "MONSTER")
    assert res.games == 4
    assert res.per_game == [(2, 0), (0, 1), (2, 0), (2, 0)]
    assert res.final == (6, 1)
    assert res.finished is True
    assert res.winner == "gnubg"
    assert res.crawford == [False, False, True, False]


def test_151_ppg_parse_money_output():
    games = pm.parse_money_output(REAL_MONEY)
    assert games == [(0, 1), (0, 1), (4, 0), (1, 0), (0, 4)]


def test_152_ppg_parse_rejects_garbage():
    with pytest.raises(pm.PpgError):
        pm.parse_match_output("no score here", length=5)
    with pytest.raises(pm.PpgError):
        pm.parse_money_output("no marker here")
    with pytest.raises(pm.PpgError):
        pm.parse_money_output('PPGJSON {"games": [["Z", 1]]}')


def test_153_ppg_script_plies():
    script = pm.build_script(plies0=0, plies1=2, length=5, seed=7)
    assert "set player 0 chequerplay evaluation plies 0" in script
    assert "set player 1 chequerplay evaluation plies 2" in script
    assert "set player 0 cubedecision evaluation plies 0" in script
    assert "set seed 7" in script
    assert "new match 5" in script
    with pytest.raises(pm.PpgError):
        pm.build_script(plies0=0, plies1=2, length=0, seed=None)


def test_154_ppg_summary_cluster():
    # Iki mac: ilk mac 4 oyun (hepsi +2), ikinci mac 2 oyun (hepsi 0).
    clusters = [[2.0, 2.0, 2.0, 2.0], [0.0, 0.0]]
    res = pm.summarize_clusters(
        clusters, plies_a=0, plies_b=2, length=5, cluster_kind="match"
    )
    assert res.clusters == 2
    assert res.games == 6
    # Mac ortalamalari [2,0; 0,0] => ortalama 1,0 (her mac esit agirlik).
    assert res.delta_ppg == pytest.approx(1.0)
    # Kume duzeltmesi: mac basina sigma sqrt(2); ortalama 3 oyun => sqrt(6)
    assert res.sigma_cluster == pytest.approx(math.sqrt(6.0), rel=1e-9)
    assert res.sigma_used >= res.sigma_cluster - 1e-12
    assert res.ci_low <= res.delta_ppg <= res.ci_high


def test_155_ppg_margin_derived():
    # m = yarim x nokta tahmini; isaret onemsiz.
    margin, note = pm.derive_margin(0.40, 0.30, 0.50)
    assert margin == pytest.approx(0.20)
    assert "saglam" in note
    margin_neg, note_neg = pm.derive_margin(-0.20, -0.35, -0.05)
    assert margin_neg == pytest.approx(0.10)
    assert "saglam" in note_neg
    # GA sifiri iceriyorsa m gecicidir ve bu acikca soylenir.
    margin2, note2 = pm.derive_margin(-0.13, -0.415, 0.155)
    assert margin2 == pytest.approx(0.065)
    assert "GECICI" in note2
    # m orneklem buyuklugune bagli DEGILDIR: ayni fark, dar GA, ayni m.
    assert pm.derive_margin(-0.13, -0.20, -0.06)[0] == pytest.approx(0.065)


def test_156_ppg_margin_floor():
    assert pm.derive_margin(0.0, 0.0, 0.0)[0] == pm.MARGIN_FLOOR
    assert pm.derive_margin(1e-9, 1e-9, 1e-9)[0] == pm.MARGIN_FLOOR
    assert pm.MARGIN_FLOOR > 0.0


def test_157_ppg_report_required_games():
    money = pm.summarize_money(
        [(2, 0), (0, 2), (4, 0), (0, 1), (1, 0), (0, 4)],
        plies_a=0,
        plies_b=2,
    )
    assert money.context == "money"
    assert money.is_money is True
    assert money.wins_a == 3
    assert money.wins_b == 3

    match = pm.summarize_clusters(
        [[2.0, 0.0], [0.0, 2.0]], plies_a=0, plies_b=2, length=5, cluster_kind="match"
    )
    report = pm.build_report(
        [money, match], money_games=6, matches_per_cell=2, workers=1
    )
    # Marj money hucresinden turetilir.
    assert report.margin_source.startswith("0-ply vs 2-ply @ money")
    assert report.margin > 0.0
    # Gereken n, sigma'nin UST sinirindan hesaplanir (Kural 4).
    expected = pm.match_power.required_games_ppg(
        pm.sigma_upper(money.sigma_used), report.margin
    )
    assert report.required_games["0-2@money"] == expected
    assert expected > pm.match_power.required_games_ppg(
        money.sigma_used, report.margin
    )
    md = pm.build_markdown(report)
    assert "m = " in md
    assert "," in md  # Turkce ondalik virgul
