"""Faz 7-R adim 0: renk takasi (antisimetri) testleri (Test 158-167).

R-T44 ``Antisymmetry_MirrorBoard``      -- tahta aynalamasi girisim ve isaret
R-T45 ``Antisymmetry_MirrorVector``     -- vektoruzer renk-simetriktir (yalniz kup sahibi)
R-T46 ``Antisymmetry_FlipPerspective``  -- ayni tahta karsi bakis + girisim
R-T47 ``Antisymmetry_FlipCase``         -- iki bakis ayni tahtayi kullanir
R-T48 ``Antisymmetry_Augment``          -- iki perspektif artirimi, ciftler ve isaret
R-T49 ``Antisymmetry_Pearson``          -- korelasyon bilinen veride
R-T50 ``Antisymmetry_ReportGate``       -- kapi dogruluk tablosu
R-T51 ``Antisymmetry_Markdown``         -- rapor kapi satirlarini tasir
R-T52 ``Antisymmetry_Bootstrap``        -- GA sifiri icerir/dislar
R-T53 ``Antisymmetry_Cli``              -- CLI sozlesmesi
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

import antisymmetry as A
import gnubg_er as G


def _random_case(rng: random.Random) -> dict:
    board = [0] * 26
    for _ in range(30):
        board[rng.randint(1, 24)] += rng.choice([1, -1])
    board[0] = rng.randint(0, 2)
    board[25] = -rng.randint(0, 2)
    turn = rng.choice([1, -1])
    after = []
    for _ in range(rng.randint(1, 4)):
        b = [0] * 26
        for _ in range(30):
            b[rng.randint(1, 24)] += rng.choice([1, -1])
        after.append(
            {"board": b, "whiteOff": rng.randint(0, 3), "blackOff": rng.randint(0, 3)}
        )
    return {
        "name": "c%d" % rng.randint(0, 9999),
        "board": board,
        "turn": turn,
        "whiteOff": rng.randint(0, 3),
        "blackOff": rng.randint(0, 3),
        "gameId": "g-%d" % rng.randint(0, 9),
        "phase": "contact",
        "ply": rng.randint(1, 40),
        "dice": [rng.randint(1, 6), rng.randint(1, 6)],
        "afterStates": after,
    }


def test_158_antisymmetry_mirror_board():
    rng = random.Random(11)
    for _ in range(200):
        case = _random_case(rng)
        board = case["board"]
        mirrored = A.mirror_board(board)
        assert len(mirrored) == 26
        assert mirrored[0] == -board[25]
        assert mirrored[25] == -board[0]
        for i in range(1, 25):
            assert mirrored[i] == -board[25 - i]
        assert A.mirror_board(mirrored) == board
    with pytest.raises(A.AntisymmetryError):
        A.mirror_board([0] * 10)


def test_159_antisymmetry_mirror_vector():
    """Vektoruzer renk-simetriktir: aynalama vektorde yalnizca kup sahibini cevirir."""
    rng = random.Random(12)
    for _ in range(500):
        board = [0] * 26
        for _ in range(30):
            board[rng.randint(1, 24)] += rng.choice([1, -1])
        board[0] = rng.randint(0, 2)
        board[25] = -rng.randint(0, 2)
        wo, bo = rng.randint(0, 3), rng.randint(0, 3)
        turn = rng.choice([1, -1])
        co = rng.choice([0, 1, -1])
        cv = rng.choice([1, 2, 4])
        ml = rng.choice([0, 5, 9])
        ws = rng.randint(0, ml - 1) if ml else 0
        bs = rng.randint(0, ml - 1) if ml else 0
        cr = rng.choice([False, True]) if ml else False

        plus = G.vectorize(
            board, wo, bo, cube_value=cv, cube_owner=co, match_length=ml,
            white_score=ws, black_score=bs, is_crawford=cr, perspective=turn,
        )
        minus = G.vectorize(
            A.mirror_board(board), bo, wo, cube_value=cv, cube_owner=co,
            match_length=ml, white_score=bs, black_score=ws, is_crawford=cr,
            perspective=-turn,
        )
        assert A.mirror_vector(plus) == pytest.approx(minus, abs=1e-9)
    with pytest.raises(A.AntisymmetryError):
        A.mirror_vector([0.0] * 10)


def test_160_antisymmetry_flip_perspective():
    """Ayni tahta, karsi bakis: bloklar yer degistirir ve ters cevrilir."""
    rng = random.Random(13)
    for _ in range(400):
        board = [0] * 26
        for _ in range(30):
            board[rng.randint(1, 24)] += rng.choice([1, -1])
        board[0] = rng.randint(0, 2)
        board[25] = -rng.randint(0, 2)
        wo, bo = rng.randint(0, 3), rng.randint(0, 3)
        turn = rng.choice([1, -1])
        co = rng.choice([0, 1, -1])
        cv = rng.choice([1, 2, 4])
        ml = rng.choice([0, 5, 9])
        ws = rng.randint(0, ml - 1) if ml else 0
        bs = rng.randint(0, ml - 1) if ml else 0
        cr = rng.choice([False, True]) if ml else False

        plus = G.vectorize(
            board, wo, bo, cube_value=cv, cube_owner=co, match_length=ml,
            white_score=ws, black_score=bs, is_crawford=cr, perspective=turn,
        )
        minus = G.vectorize(
            board, wo, bo, cube_value=cv, cube_owner=co, match_length=ml,
            white_score=ws, black_score=bs, is_crawford=cr, perspective=-turn,
        )
        flipped = A.flip_perspective(plus)
        assert flipped == pytest.approx(minus, abs=1e-9)
        assert A.flip_perspective(flipped) == pytest.approx(plus, abs=1e-9)
    with pytest.raises(A.AntisymmetryError):
        A.flip_perspective([0.0] * 10)


def test_161_antisymmetry_flip_case():
    """Iki bakis **ayni** fiziksel tahtayi kullanir; yalnizca vektor degisir."""
    rng = random.Random(14)
    for _ in range(100):
        case = _random_case(rng)
        turn = int(case["turn"])
        plus = G.vectorize(case["board"], case["whiteOff"], case["blackOff"], perspective=turn)
        minus = G.vectorize(case["board"], case["whiteOff"], case["blackOff"], perspective=-turn)
        assert A.flip_perspective(plus) == pytest.approx(minus, abs=1e-9)
        for after in case["afterStates"]:
            vp = G.vectorize(after["board"], after["whiteOff"], after["blackOff"], perspective=turn)
            vm = G.vectorize(after["board"], after["whiteOff"], after["blackOff"], perspective=-turn)
            assert A.flip_perspective(vp) == pytest.approx(vm, abs=1e-9)


def test_162_antisymmetry_augment():
    rng = random.Random(15)
    cases = [_random_case(rng) for _ in range(7)]
    augmented = A.augment_perspectives(cases)
    assert len(augmented) == 2 * len(cases)
    for i, case in enumerate(cases):
        turn = int(case["turn"])
        first = augmented[2 * i]
        second = augmented[2 * i + 1]
        assert first["name"] == case["name"]
        assert first["perspective"] == turn
        assert first["valueSign"] == 1.0
        assert second["name"] == case["name"]
        assert second["perspective"] == -turn
        assert second["valueSign"] == -1.0
        # Ayni fiziksel tahta: artirim tahtayi degistirmez.
        assert first["board"] == case["board"]
        assert second["board"] == case["board"]
        assert first["afterStates"] == case["afterStates"]
        assert second["afterStates"] == case["afterStates"]
        # Girdi vektorleri birbirinin bakis takasi.
        vp = G.vectorize(case["board"], case["whiteOff"], case["blackOff"], perspective=turn)
        vm = G.vectorize(case["board"], case["whiteOff"], case["blackOff"], perspective=-turn)
        assert A.flip_perspective(vp) == pytest.approx(vm, abs=1e-9)
    assert A.augment_perspectives([]) == []


def test_163_antisymmetry_pearson():
    a = np.asarray([1.0, 2.0, 3.0, 4.0])
    assert A._pearson(a, a) == pytest.approx(1.0)
    assert A._pearson(a, -a) == pytest.approx(-1.0)
    assert A._pearson(a, np.asarray([1.0, 1.0, 1.0, 1.0])) != A._pearson(a, a)
    assert math.isnan(A._pearson(np.asarray([1.0]), np.asarray([2.0])))
    assert math.isnan(A._pearson(a, np.asarray([2.0, 2.0, 2.0, 2.0])))


def test_164_antisymmetry_report_gate():
    ok = A.AntisymmetryReport(
        correlation=-0.995, er_diff=0.0, er_diff_ci_low=-0.01, er_diff_ci_high=0.01,
        er_diff_excludes_zero=False,
    )
    assert ok.corr_ok and ok.er_ok and ok.passed

    bad_corr = A.AntisymmetryReport(
        correlation=-0.70, er_diff=0.0, er_diff_ci_low=-0.01, er_diff_ci_high=0.01,
        er_diff_excludes_zero=False,
    )
    assert not bad_corr.corr_ok and bad_corr.er_ok and not bad_corr.passed

    bad_er = A.AntisymmetryReport(
        correlation=-0.995, er_diff=0.02, er_diff_ci_low=0.005, er_diff_ci_high=0.03,
        er_diff_excludes_zero=True,
    )
    assert bad_er.corr_ok and not bad_er.er_ok and not bad_er.passed

    nan = A.AntisymmetryReport(correlation=float("nan"))
    assert not nan.corr_ok and not nan.passed

    assert A.AntisymmetryReport(correlation=0.995).corr_ok
    assert A.AntisymmetryReport(correlation=-0.99).corr_ok
    assert not A.AntisymmetryReport(correlation=-0.9899).corr_ok


def test_165_antisymmetry_markdown():
    report = A.AntisymmetryReport(
        count=1000, model="ml/runs/x/onnx/model_v30.onnx",
        correlation=-0.7019, mean_abs_sum=1.0044, max_abs_sum=2.1,
        sum_within_tol=3, sum_total=20000, argmax_agreement=1, argmax_total=59,
        er_plus=0.0402, er_minus=0.0410, er_diff=0.0008,
        er_diff_ci_low=-0.0020, er_diff_ci_high=0.0036,
        er_diff_excludes_zero=False,
    )
    text = A.build_markdown(report)
    assert "corr(e(+1), e(-1))" in text
    assert "0,7019" in text
    assert "ER farki GA" in text
    assert "GECTI" in text
    assert "DUSTU" in text
    assert "model_v30.onnx" in text
    assert "1/59" in text
    assert "3/20000" in text
    assert "**Karar: DUSTU**" in text


def test_166_antisymmetry_bootstrap():
    low, high = A._bootstrap_ci([0.01] * 50, resamples=500, seed=1)
    assert low == pytest.approx(0.01) and high == pytest.approx(0.01)
    low, high = A._bootstrap_ci([-1.0, 1.0] * 50, resamples=500, seed=1)
    assert low < 0.0 < high
    low, high = A._bootstrap_ci([0.5] * 50, resamples=500, seed=1)
    assert low > 0.0
    nan_low, nan_high = A._bootstrap_ci([], resamples=10, seed=1)
    assert math.isnan(nan_low) and math.isnan(nan_high)


def test_167_antisymmetry_cli():
    parser = A.build_parser()
    args = parser.parse_args(["measure", "--model", "m.onnx"])
    assert args.command == "measure"
    assert args.model == "m.onnx"
    assert args.cases == "ml/artifacts/reference_corpus_v2.json"
    assert args.plies == 2
    assert args.stride == 1
    assert args.limit == 0
    assert args.out == A.ANTISYMMETRY_PATH
    assert args.markdown == A.ANTISYMMETRY_MD_PATH
    with pytest.raises(SystemExit):
        parser.parse_args(["measure"])
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ----------------------------------------------------------------------
# Cikarim aninda antisimetriklestirme (Test 204-208)
# ----------------------------------------------------------------------


def test_204_symmetrise_value_is_difference_not_mean():
    """``e_hat = (e+ - e-) / 2`` -- **fark**, ortalama degil.

    F7-55'teki basarisiz "naif duzeltme" logit'leri **ortaliyordu**; iki bakis
    ayni pozisyonu zit isaretle puanladigi icin ortalama sifira coker.
    """
    assert A.symmetrise_value(0.8, -0.8) == pytest.approx(0.8)
    assert A.symmetrise_value(0.8, 0.8) == pytest.approx(0.0)
    assert A.symmetrise_value(0.0, 0.0) == pytest.approx(0.0)
    # Kusurlu model: iki bakis zit isaretli degil.
    assert A.symmetrise_value(0.6, -0.4) == pytest.approx(0.5)
    # Ortalama alsaydik 0,1 cikardi -- yanlis.
    assert (0.6 + -0.4) / 2 == pytest.approx(0.1)


def test_205_symmetrise_logits_is_difference():
    plus = [1.0, 2.0, 3.0]
    minus = [-1.0, -2.0, -3.0]
    out = A.symmetrise_logits(plus, minus)
    assert out == pytest.approx([1.0, 2.0, 3.0])
    # Kusurlu: siralama degisebilir.
    out2 = A.symmetrise_logits([0.0, 1.0], [0.0, -1.0])
    assert out2 == pytest.approx([0.0, 1.0])
    with pytest.raises(A.AntisymmetryError):
        A.symmetrise_logits([1.0], [1.0, 2.0])


def test_206_symmetrised_report_delta_and_gate():
    report = A.SymmetrisedReport(model="m.onnx", corpus="c.json", plies=2)
    report.cases = 4
    report.raw_policy = [0.10, 0.10, 0.10, 0.10]
    report.sym_policy = [0.05, 0.05, 0.05, 0.05]
    report.raw_value = [0.20, 0.20, 0.20, 0.20]
    report.sym_value = [0.20, 0.20, 0.20, 0.20]
    delta, low, high = report.policy_delta
    assert delta == pytest.approx(-0.05)
    assert high < 0.0
    assert report.policy_improved is True
    vdelta, vlow, vhigh = report.value_delta
    assert vdelta == pytest.approx(0.0)
    assert report.value_improved is False
    payload = report.to_dict()
    assert payload["policy"]["improved"] is True
    assert payload["value"]["improved"] is False
    assert payload["cases"] == 4


def test_207_symmetrised_markdown_has_both_paths():
    report = A.SymmetrisedReport(model="m.onnx", corpus="c.json", plies=2)
    report.cases = 2
    report.raw_policy = [0.10, 0.10]
    report.sym_policy = [0.05, 0.05]
    report.raw_value = [0.20, 0.20]
    report.sym_value = [0.15, 0.15]
    report.argmax_changed = 1
    md = A.build_symmetrised_markdown(report)
    assert "`policy`" in md
    assert "`value`" in md
    assert "IYILESDI" in md
    assert "argmax" in md.lower()


def test_208_symmetrise_cli_contract():
    parser = A.build_parser()
    args = parser.parse_args(["symmetrise", "--model", "m.onnx"])
    assert args.command == "symmetrise"
    assert args.out == A.SYMMETRISED_PATH
    assert args.markdown == A.SYMMETRISED_MD_PATH
    assert args.plies == 2


def test_252_antisymmetry_report_dict_round_trip():
    """``from_dict`` kaydedilmis raporu yeniden bicimlendirir (olcum tekrarlanmaz)."""
    report = A.AntisymmetryReport(
        count=1000,
        correlation=-0.9426,
        mean_abs_sum=0.2827,
        max_abs_sum=3.5577,
        sum_within_tol=227,
        sum_total=24436,
        vectorizer_checked=24436,
        vectorizer_mismatches=0,
        argmax_agreement=392,
        argmax_total=1000,
        er_plus=0.0485,
        er_minus=0.0788,
        er_diff=-0.0302,
        er_diff_ci_low=-0.0391,
        er_diff_ci_high=-0.0216,
        er_diff_excludes_zero=True,
        model="ml/runs/rd_aug10k/onnx/model_v10.onnx",
        notes=["not 1"],
    )
    back = A.AntisymmetryReport.from_dict(report.to_dict())
    assert back.to_dict() == report.to_dict()
    # Turetilmis alanlar da ayni: kapi karari kaybolmaz.
    assert back.passed == report.passed
    assert back.argmax_rate == pytest.approx(report.argmax_rate)
    assert back.vectorizer_symmetric is True
    # Markdown ayni sekilde uretilir.
    assert A.build_markdown(back) == A.build_markdown(report)


def test_253_antisymmetry_report_from_dict_tolerates_missing_keys():
    """Eski/kismi artefaktlar patlamaz; eksikler varsayilana duser."""
    back = A.AntisymmetryReport.from_dict({"count": 5, "correlation": -0.5})
    assert back.count == 5
    assert back.correlation == pytest.approx(-0.5)
    assert back.corr_min == A.CORR_MIN
    assert back.sum_tol == A.SUM_TOL
    assert back.notes == []
    assert back.passed is False
