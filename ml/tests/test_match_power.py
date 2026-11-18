"""Test 128: mac seviyesinde guc analizi (dis inceleme madde 1.4).

`ml/match_power.py` her iddiayi **gerekli n** ve **saptanabilir etki** olarak
yazar. Bu dosya z/yarim-genislik/n formullerini kapali formla, MET okumasini
gercek dosyayla ve CLI sozlesmesini dogrular.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import match_power as mp


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_128a_constants() -> None:
    assert mp.Z_TWO_SIDED == pytest.approx(1.959963984540054)
    assert mp.Z_ONE_SIDED == pytest.approx(1.6448536269514722)
    assert mp.DEFAULT_POWER == 0.80
    assert mp.DEFAULT_ALPHA == 0.05
    assert mp.STAGE_H_GAMES == 400
    assert mp.NOISE_HALF_WIDTH == 0.05
    assert mp.DEFAULT_PPG_SIGMA > 0.0


def test_128a_noise_floor_games_ascending() -> None:
    games = list(mp.NOISE_FLOOR_GAMES)
    assert games == sorted(games)
    assert all(n > 0 for n in games)


def test_128a_met_path_points_at_repo_file() -> None:
    assert mp.MET_PATH.name == "met_rk.json"
    assert mp.MET_PATH.is_file()


# ----------------------------------------------------------------------
# z yardimcilari
# ----------------------------------------------------------------------


def test_128b_z_for_power_matches_normal_dist() -> None:
    from statistics import NormalDist

    for power in (0.55, 0.6, 0.8, 0.9, 0.95):
        assert mp.z_for_power(power) == pytest.approx(NormalDist().inv_cdf(power))


def test_128b_z_for_power_80pct() -> None:
    assert mp.z_for_power(0.80) == pytest.approx(0.8416212335729143, abs=1e-12)


def test_128b_z_for_power_monotone() -> None:
    values = [mp.z_for_power(p) for p in (0.55, 0.7, 0.8, 0.9, 0.99)]
    assert values == sorted(values)


@pytest.mark.parametrize("power", [0.5, 0.4, 1.0, 1.5, 0.0, -0.1])
def test_128b_z_for_power_rejects_out_of_range(power: float) -> None:
    with pytest.raises(ValueError):
        mp.z_for_power(power)


def test_128b_z_for_alpha_two_sided() -> None:
    assert mp.z_for_alpha(0.05) == pytest.approx(mp.Z_TWO_SIDED, abs=1e-12)
    assert mp.z_for_alpha(0.01) == pytest.approx(2.5758293035489004, abs=1e-9)


def test_128b_z_for_alpha_one_sided() -> None:
    assert mp.z_for_alpha(0.05, two_sided=False) == pytest.approx(mp.Z_ONE_SIDED, abs=1e-12)


def test_128b_z_for_alpha_one_sided_smaller_than_two_sided() -> None:
    assert mp.z_for_alpha(0.05, two_sided=False) < mp.z_for_alpha(0.05, two_sided=True)


@pytest.mark.parametrize("alpha", [0.0, 0.5, 0.6, -0.1, 1.0])
def test_128b_z_for_alpha_rejects_out_of_range(alpha: float) -> None:
    with pytest.raises(ValueError):
        mp.z_for_alpha(alpha)


# ----------------------------------------------------------------------
# Kazanma orani gucu
# ----------------------------------------------------------------------


def test_128c_half_width_closed_form() -> None:
    p, n = 0.55, 400
    expected = mp.Z_TWO_SIDED * math.sqrt(p * (1.0 - p) / n)
    assert mp.win_rate_half_width(p, n) == pytest.approx(expected)


def test_128c_half_width_shrinks_with_n() -> None:
    a = mp.win_rate_half_width(0.55, 100)
    b = mp.win_rate_half_width(0.55, 400)
    c = mp.win_rate_half_width(0.55, 1600)
    assert a > b > c
    assert b == pytest.approx(a / 2.0)
    assert c == pytest.approx(a / 4.0)


def test_128c_half_width_max_at_half() -> None:
    assert mp.win_rate_half_width(0.5, 400) > mp.win_rate_half_width(0.9, 400)


def test_128c_half_width_zero_at_extremes() -> None:
    assert mp.win_rate_half_width(0.0, 400) == pytest.approx(0.0)
    assert mp.win_rate_half_width(1.0, 400) == pytest.approx(0.0)


@pytest.mark.parametrize("p", [-0.1, 1.1])
def test_128c_half_width_rejects_bad_p(p: float) -> None:
    with pytest.raises(ValueError):
        mp.win_rate_half_width(p, 400)


@pytest.mark.parametrize("n", [0, -5])
def test_128c_half_width_rejects_bad_n(n: int) -> None:
    with pytest.raises(ValueError):
        mp.win_rate_half_width(0.5, n)


def test_128c_required_games_inverts_half_width() -> None:
    p, hw = 0.55, 0.05
    n = mp.required_games_win_rate(p, hw)
    assert mp.win_rate_half_width(p, n) <= hw + 1e-12
    assert mp.win_rate_half_width(p, n - 1) > hw


def test_128c_required_games_400_at_stage_h() -> None:
    # 0,55 icin +/-0,05 esigi 381 oyun ister: Faz 6'nin 400 oyunu tam sinirda.
    assert mp.required_games_win_rate(0.55, 0.05) == 381


def test_128c_required_games_scales_with_inverse_square() -> None:
    a = mp.required_games_win_rate(0.55, 0.05)
    b = mp.required_games_win_rate(0.55, 0.025)
    assert b == pytest.approx(4 * a, rel=0.01)


@pytest.mark.parametrize("p", [0.0, 1.0])
def test_128c_required_games_rejects_degenerate_p(p: float) -> None:
    with pytest.raises(ValueError):
        mp.required_games_win_rate(p, 0.05)


@pytest.mark.parametrize("hw", [0.0, -0.01])
def test_128c_required_games_rejects_bad_half_width(hw: float) -> None:
    with pytest.raises(ValueError):
        mp.required_games_win_rate(0.55, hw)


def test_128c_two_proportions_positive() -> None:
    n = mp.required_games_two_proportions(0.50, 0.55)
    assert n > 0
    assert isinstance(n, int)


def test_128c_two_proportions_grows_as_delta_shrinks() -> None:
    big = mp.required_games_two_proportions(0.50, 0.60)
    small = mp.required_games_two_proportions(0.50, 0.52)
    assert small > big


def test_128c_two_proportions_grows_with_power() -> None:
    low = mp.required_games_two_proportions(0.50, 0.55, power=0.60)
    high = mp.required_games_two_proportions(0.50, 0.55, power=0.95)
    assert high > low


def test_128c_two_proportions_symmetric_in_delta() -> None:
    a = mp.required_games_two_proportions(0.50, 0.55)
    b = mp.required_games_two_proportions(0.55, 0.50)
    assert a == b


def test_128c_two_proportions_rejects_equal_rates() -> None:
    with pytest.raises(ValueError):
        mp.required_games_two_proportions(0.5, 0.5)


@pytest.mark.parametrize("p0,p1", [(0.0, 0.5), (0.5, 1.0), (-0.1, 0.5)])
def test_128c_two_proportions_rejects_bad_rates(p0: float, p1: float) -> None:
    with pytest.raises(ValueError):
        mp.required_games_two_proportions(p0, p1)


# ----------------------------------------------------------------------
# ppg gucu
# ----------------------------------------------------------------------


def test_128d_ppg_half_width_closed_form() -> None:
    sigma, n = 2.4, 400
    assert mp.ppg_half_width(sigma, n) == pytest.approx(mp.Z_TWO_SIDED * sigma / math.sqrt(n))


def test_128d_ppg_half_width_shrinks_with_n() -> None:
    a = mp.ppg_half_width(2.4, 100)
    b = mp.ppg_half_width(2.4, 400)
    assert b == pytest.approx(a / 2.0)


@pytest.mark.parametrize("sigma", [0.0, -1.0])
def test_128d_ppg_half_width_rejects_bad_sigma(sigma: float) -> None:
    with pytest.raises(ValueError):
        mp.ppg_half_width(sigma, 400)


@pytest.mark.parametrize("n", [0, -1])
def test_128d_ppg_half_width_rejects_bad_n(n: int) -> None:
    with pytest.raises(ValueError):
        mp.ppg_half_width(2.4, n)


def test_128d_required_games_ppg_inverts_half_width() -> None:
    sigma, hw = 2.4, 0.10
    n = mp.required_games_ppg(sigma, hw)
    assert mp.ppg_half_width(sigma, n) <= hw + 1e-12
    assert mp.ppg_half_width(sigma, n - 1) > hw


def test_128d_required_games_ppg_known_value() -> None:
    # 2,4 sigma ile +/-0,10 ppg icin 2213 oyun gerekir (olculen deger).
    assert mp.required_games_ppg(2.4, 0.10) == 2213


def test_128d_required_games_ppg_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        mp.required_games_ppg(0.0, 0.1)
    with pytest.raises(ValueError):
        mp.required_games_ppg(2.4, 0.0)


def test_128d_two_means_closed_form() -> None:
    sigma, delta = 2.4, 0.10
    za = mp.z_for_alpha(0.05)
    zb = mp.z_for_power(0.80)
    expected = math.ceil(2.0 * (za + zb) ** 2 * sigma * sigma / (delta * delta))
    assert mp.required_games_two_means(sigma, delta) == expected


def test_128d_two_means_grows_as_delta_shrinks() -> None:
    assert mp.required_games_two_means(2.4, 0.05) > mp.required_games_two_means(2.4, 0.10)


def test_128d_two_means_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        mp.required_games_two_means(0.0, 0.1)
    with pytest.raises(ValueError):
        mp.required_games_two_means(2.4, 0.0)


def test_128d_detectable_ppg_equals_half_width() -> None:
    assert mp.detectable_ppg(2.4, 400) == pytest.approx(mp.ppg_half_width(2.4, 400))


def test_128d_detectable_win_rate_equals_half_width() -> None:
    assert mp.detectable_win_rate(0.55, 400) == pytest.approx(
        mp.win_rate_half_width(0.55, 400)
    )


def test_128d_detectable_ppg_decreases_with_n() -> None:
    assert mp.detectable_ppg(2.4, 1000) < mp.detectable_ppg(2.4, 100)


# ----------------------------------------------------------------------
# Mac seviyesi + MET
# ----------------------------------------------------------------------


def test_128e_required_matches_matches_win_rate() -> None:
    assert mp.required_matches(0.55, 0.05) == mp.required_games_win_rate(0.55, 0.05)


def test_128e_load_met_reads_table() -> None:
    met = mp.load_met()
    assert "table" in met
    assert int(met["maxMatchLength"]) == 25
    assert len(met["table"]) == 26


def test_128e_load_met_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mp.load_met(tmp_path / "nope.json")


def test_128e_mwc_zero_away_is_one() -> None:
    met = mp.load_met()
    assert mp.mwc_from_met(0, 5, met=met) == pytest.approx(1.0)


def test_128e_mwc_symmetric_complement() -> None:
    met = mp.load_met()
    a = mp.mwc_from_met(3, 5, met=met)
    b = mp.mwc_from_met(5, 3, met=met)
    assert a + b == pytest.approx(1.0, abs=1e-9)


def test_128e_mwc_monotone_in_away_self() -> None:
    met = mp.load_met()
    values = [mp.mwc_from_met(a, 5, met=met) for a in range(0, 6)]
    assert values == sorted(values, reverse=True)


def test_128e_mwc_monotone_in_away_opp() -> None:
    met = mp.load_met()
    values = [mp.mwc_from_met(5, b, met=met) for b in range(0, 6)]
    assert values == sorted(values)


def test_128e_mwc_rejects_out_of_range() -> None:
    met = mp.load_met()
    with pytest.raises(ValueError):
        mp.mwc_from_met(26, 5, met=met)
    with pytest.raises(ValueError):
        mp.mwc_from_met(5, -1, met=met)


# ----------------------------------------------------------------------
# Artifact okuma
# ----------------------------------------------------------------------


def test_128f_ppg_from_eval_reads_mean_points() -> None:
    data = {"reports": [{"opponent": "PipBot", "meanPoints": 2.445, "games": 200}]}
    assert mp.ppg_from_eval(data) == pytest.approx(2.445)


def test_128f_ppg_from_eval_filters_opponent() -> None:
    data = {
        "reports": [
            {"opponent": "PipBot", "meanPoints": 2.445, "games": 200},
            {"opponent": "RandomBot", "meanPoints": 2.63, "games": 200},
        ]
    }
    assert mp.ppg_from_eval(data, opponent="random") == pytest.approx(2.63)


def test_128f_ppg_from_eval_none_cases() -> None:
    assert mp.ppg_from_eval(None) is None
    assert mp.ppg_from_eval({}) is None
    assert mp.ppg_from_eval({"reports": []}) is None
    assert mp.ppg_from_eval({"reports": [{"opponent": "X"}]}) is None


def test_128f_games_from_eval_reads_games() -> None:
    data = {"reports": [{"opponent": "PipBot", "games": 200}]}
    assert mp.games_from_eval(data) == 200


def test_128f_games_from_eval_none_cases() -> None:
    assert mp.games_from_eval(None) is None
    assert mp.games_from_eval({"reports": [{"opponent": "X"}]}) is None


def test_128f_real_pip_artifact() -> None:
    path = Path(__file__).resolve().parents[1] / "artifacts" / "stage_h_eval_pip.json"
    if not path.is_file():
        pytest.skip("stage_h_eval_pip.json yok")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert mp.games_from_eval(data) == 200
    assert mp.ppg_from_eval(data) == pytest.approx(2.445, abs=1e-6)


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def test_128g_noise_floor_rows() -> None:
    rows = mp.noise_floor(0.55, 2.4)
    assert len(rows) == len(mp.NOISE_FLOOR_GAMES)
    for row in rows:
        assert set(row) == {"games", "winRateHalfWidth", "ppgHalfWidth"}
        assert row["winRateHalfWidth"] > 0.0
        assert row["ppgHalfWidth"] > 0.0


def test_128g_noise_floor_monotone() -> None:
    rows = mp.noise_floor(0.55, 2.4)
    wr = [r["winRateHalfWidth"] for r in rows]
    ppg = [r["ppgHalfWidth"] for r in rows]
    assert wr == sorted(wr, reverse=True)
    assert ppg == sorted(ppg, reverse=True)


def test_128g_noise_floor_skips_non_positive() -> None:
    rows = mp.noise_floor(0.55, 2.4, games=[0, -1, 100])
    assert len(rows) == 1
    assert rows[0]["games"] == 100


def test_128g_build_report_keys() -> None:
    report = mp.build_report()
    data = report.to_dict()
    assert set(data) == {
        "winRate",
        "ppgSigma",
        "games",
        "winRateHalfWidth",
        "ppgHalfWidth",
        "noiseFloor",
        "required",
        "notes",
    }
    assert set(data["required"]) == {
        "gamesForWinRateHalfWidth5pct",
        "gamesForPpgHalfWidth0_10",
        "gamesForPpgHalfWidth0_05",
        "gamesPerArmWinRateVsChampion",
        "gamesPerArmPpgVsChampion",
        "matchesForMatchWinRateHalfWidth5pct",
    }


def test_128g_build_report_400_games_cannot_resolve_claimed_delta() -> None:
    # Incelemenin ornegi: 2-away %40,0 vs %39,5 -> fark 0,005.
    report = mp.build_report(games=400, win_rate=0.40)
    assert report.win_rate_half_width > mp.CLAIMED_DELTA
    assert any("olculemez" in note for note in report.notes)


def test_128g_build_report_400_games_is_noisy_at_half_width_threshold() -> None:
    # p = 0,50'de yarim genislik en buyuktur; 300 oyunda 0,05 esigini asar.
    report = mp.build_report(games=300, win_rate=0.50, champion_win_rate=0.40)
    assert report.win_rate_half_width > mp.NOISE_HALF_WIDTH
    assert any("gurultu" in note for note in report.notes)


def test_128g_build_report_large_sample_is_quiet() -> None:
    report = mp.build_report(games=100000, win_rate=0.55)
    assert report.win_rate_half_width < mp.NOISE_HALF_WIDTH


def test_128g_build_report_ppg_needs_more_games_than_win_rate() -> None:
    report = mp.build_report()
    assert (
        report.required["gamesForPpgHalfWidth0_05"]
        > report.required["gamesForWinRateHalfWidth5pct"]
    )


def test_128g_build_report_notes_mention_ppg() -> None:
    report = mp.build_report()
    assert any("ppg" in note for note in report.notes)


def test_128g_build_markdown_has_sections() -> None:
    text = mp.build_markdown(mp.build_report())
    for heading in ("## 1.", "## 2.", "## 3.", "## 4."):
        assert heading in text
    assert text.endswith("\n")


def test_128g_build_markdown_lists_every_required_row() -> None:
    report = mp.build_report()
    text = mp.build_markdown(report)
    for value in report.required.values():
        assert str(value) in text


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_128h_cli_defaults_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert mp.main([]) == 0
    out = capsys.readouterr().out
    assert "oyun=400" in out


def test_128h_cli_quiet_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert mp.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_128h_cli_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "p.json"
    assert mp.main(["--json", str(out), "--quiet"]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["games"] == 400


def test_128h_cli_writes_markdown(tmp_path: Path) -> None:
    out = tmp_path / "p.md"
    assert mp.main(["--markdown", str(out), "--quiet"]) == 0
    assert out.read_text(encoding="utf-8").startswith("# ")


def test_128h_cli_missing_eval_returns_two(tmp_path: Path) -> None:
    assert mp.main(["--eval", str(tmp_path / "nope.json"), "--quiet"]) == 2


def test_128h_cli_eval_overrides_games(tmp_path: Path) -> None:
    src = tmp_path / "eval.json"
    src.write_text(
        json.dumps({"reports": [{"opponent": "PipBot", "meanPoints": 2.445, "games": 200}]}),
        encoding="utf-8",
    )
    out = tmp_path / "p.json"
    assert mp.main(["--eval", str(src), "--json", str(out), "--quiet"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["games"] == 200


def test_128h_cli_custom_games(capsys: pytest.CaptureFixture[str]) -> None:
    assert mp.main(["--games", "1000"]) == 0
    assert "oyun=1000" in capsys.readouterr().out
