"""Faz 6 Asama B (Bolum 12.2): Test 53, 55, 56.

Test 49-52, 54, 57, 58 C# tarafinda (``Backgammon.Tests/OutcomeDistributionV2Tests.cs``
ve ``Backgammon.Inference.Tests/OutputVersion2Tests.cs``); Test 59
``ml/tests/test_export_output_version.py`` icinde. Bu dosya Python tarafindaki
uc testi barindirir.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest
import torch

from calibration import (
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    apply_temperature,
    assert_single_temperature,
    calibration_metrics,
    fit_temperature,
    fit_temperature_ce,
)
from equity import (
    EQUITY_WEIGHTS,
    PROB_COUNT,
    PROB_ORDER,
    equity_from_cumulative,
    equity_from_exclusive,
    normalize_exclusive,
    to_cumulative,
)
from losses import DEFAULT_C_CAL, calibration_loss, total_loss_v2, value_loss_ce_6class

REPO = Path(__file__).resolve().parent.parent.parent
OUTCOME_CS = REPO / "Backgammon.Core" / "Match" / "OutcomeDistribution.cs"


# ---------------------------------------------------------------------------
# Test 53 - EquityFormula_PythonMatchesCSharp
# ---------------------------------------------------------------------------


def test_53_equity_formula_python_matches_csharp() -> None:
    """**Duman testi** - Python ic tutarliligi (Faz 7 Bolum 9.9 ile indirgendi).

    .. deprecated:: Faz 7
       Bu test artik **capraz dil sozlesmesi degildir**. C# ve Python ayni girdiyi
       hicbir zaman gormez; formul iki tarafta birlikte degisirse bu test yesil
       kalir. Sozlesme ``ml/tests/test_equity_parity.py`` (Test 122/123) ve
       ``Backgammon.Tests/ReferenceData/equity_golden.json`` dosyasidir.

    Burada kalan sey: Python tarafinin kendi icinde tutarli oldugu (dislayici ve
    kumulatif ifadeler ayni sayiyi verir, aralik [-3, +3], antisimetri).
    """
    assert PROB_COUNT == 6
    assert PROB_ORDER == ("W", "GW", "BW", "L", "GL", "BL")
    assert list(EQUITY_WEIGHTS) == [1.0, 2.0, 3.0, -1.0, -2.0, -3.0]

    # Birim vektorler: E tam olarak {+3,+2,+1,-1,-2,-3} olmali (Test 49 ile ayni tablo).
    unit = np.eye(6, dtype=np.float64)
    assert list(equity_from_exclusive(unit)) == [1.0, 2.0, 3.0, -1.0, -2.0, -3.0]

    # Karisik vektorler: iki ifade sayisal olarak ayni sonucu vermeli.
    rng = np.random.default_rng(20261114)
    raw = rng.random((256, 6))
    probs = normalize_exclusive(raw)
    exclusive = equity_from_exclusive(probs)
    cumulative = equity_from_cumulative(**to_cumulative(probs))
    assert np.allclose(exclusive, cumulative, atol=1e-12)

    # Aralik degismezi: E her zaman [-3, +3] icinde.
    assert np.all(exclusive >= -3.0 - 1e-12)
    assert np.all(exclusive <= 3.0 + 1e-12)

    # Antisimetri: olasiliklar W<->L, GW<->GL, BW<->BL degisince E -> -E (Test 50 ile ayni).
    swapped = probs[:, [3, 4, 5, 0, 1, 2]]
    assert np.allclose(equity_from_exclusive(swapped), -exclusive, atol=1e-12)


def test_53_csharp_equity_source_is_unchanged() -> None:
    """C# kaynagindaki formul metni beklenen bicimde duruyor mu (suruklenme korumasi)."""
    text = OUTCOME_CS.read_text(encoding="utf-8")

    # ``Equity`` getter'i kumulatif ifadeyi kullanmali.
    assert re.search(
        r"return\s+\(double\)Win\s*\+\s*WinGammon\s*\+\s*WinBackgammon\s*"
        r"-\s*Lose\s*-\s*LoseGammon\s*-\s*LoseBackgammon\s*;",
        text,
    ), "C# Equity ifadesi beklenen kumulatif bicimde degil"

    # ``FromProbabilities`` kumulatif alanlari dislayici degerlerden turetmelidir.
    assert re.search(r"float\s+win\s*=\s*Clamp01\(nw\s*\+\s*ngw\s*\+\s*nbw\)", text)
    assert re.search(r"float\s+winGammon\s*=\s*Clamp\(ngw\s*\+\s*nbw", text)
    assert re.search(r"float\s+winBackgammon\s*=\s*Clamp\(nbw", text)
    assert re.search(r"float\s+loseGammon\s*=\s*Clamp\(ngl\s*\+\s*nbl", text)
    assert re.search(r"float\s+loseBackgammon\s*=\s*Clamp\(nbl", text)

    # Sinif sayisi iki tarafta ayni olmali.
    assert re.search(r"const\s+int\s+ProbabilityCount\s*=\s*6\s*;", text)


# ---------------------------------------------------------------------------
# Test 55 - CalibrationLoss_ImprovesSlope
# ---------------------------------------------------------------------------


def _synthetic_outcomes(n: int, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    """1-B ozellikten uretilen dislayici 6 sinifli gercek dagilim.

    ``x`` buyudukce beyaz kazanma olasiligi **ve** mars/backgammon payi artar.
    Mars payi dogrusal olmadigi icin tek dogrusal model bu yapiyi tam temsil edemez;
    bu, kalibrasyon hatasini kasitli olarak uretir.
    """
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1.0, 1.0, size=(n, 1)).astype(np.float32)
    pw = 1.0 / (1.0 + np.exp(-3.0 * x[:, 0]))
    gammon = 0.35 * pw**2
    backgammon = 0.10 * pw**3
    lose = 1.0 - pw
    lose_gammon = 0.35 * lose**2
    lose_backgammon = 0.10 * lose**3

    probs = np.stack(
        [
            pw - gammon,
            gammon - backgammon,
            backgammon,
            lose - lose_gammon,
            lose_gammon - lose_backgammon,
            lose_backgammon,
        ],
        axis=1,
    ).astype(np.float32)
    probs = np.clip(probs, 1e-6, None)
    probs /= probs.sum(axis=1, keepdims=True)
    return torch.tensor(x), torch.tensor(probs)


_NEG = -1e9


def _misspecified_logits(x: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    """Yalnizca tek kazanma/kaybetme ekseni gorebilen kasitli eksik model."""
    a = scale * 3.0 * x
    pad = torch.full_like(a, _NEG)
    return torch.cat([a, pad, pad, -a, pad, pad], dim=1)


def _fit_scale(c_cal: float, steps: int = 600, lr: float = 0.05) -> float:
    """Tek olcek parametresini ``L_value + c_cal * L_cal`` ile egitir (deterministik)."""
    x_train, p_train = _synthetic_outcomes(4000, seed=1)
    weights = torch.tensor(EQUITY_WEIGHTS, dtype=torch.float32)
    scale = torch.tensor(1.0, requires_grad=True)
    optimizer = torch.optim.Adam([scale], lr=lr)

    for _ in range(steps):
        optimizer.zero_grad()
        probs = torch.softmax(_misspecified_logits(x_train, scale), dim=-1)
        value_loss = value_loss_ce_6class(probs, p_train)
        cal_loss = calibration_loss(probs @ weights, p_train @ weights)
        total_loss_v2(value_loss, torch.zeros(()), cal_loss, c_cal=c_cal).backward()
        optimizer.step()

    return float(scale.detach())


def _slope_for(c_cal: float) -> float:
    scale = _fit_scale(c_cal)
    x_val, p_val = _synthetic_outcomes(2000, seed=2)
    with torch.no_grad():
        probs = torch.softmax(_misspecified_logits(x_val, torch.tensor(scale)), dim=-1)
    pred = probs.numpy().astype(np.float64) @ EQUITY_WEIGHTS
    target = p_val.numpy().astype(np.float64) @ EQUITY_WEIGHTS
    return calibration_metrics(pred, target)["slope"]


def test_55_calibration_loss_improves_slope() -> None:
    """``c_cal = 0.1`` egimi 1'e, ``c_cal = 0``'a gore daha yakin yapar (Faz 6 Bolum 5.3)."""
    assert DEFAULT_C_CAL == pytest.approx(0.1)

    slope_without = _slope_for(0.0)
    slope_with = _slope_for(DEFAULT_C_CAL)

    # Kasitli eksik model egimi 1'in uzerine tasir; L_cal bunu 1'e ceker.
    assert slope_without > 1.0
    assert abs(slope_with - 1.0) < abs(slope_without - 1.0), (
        f"L_cal egimi 1'e yaklastirmadi: c_cal=0 -> {slope_without:.4f}, "
        f"c_cal={DEFAULT_C_CAL} -> {slope_with:.4f}"
    )


def test_55_calibration_loss_improves_mae() -> None:
    """Ayni kosuda ``L_cal`` equity MAE'sini de dusurur."""
    def mae_for(c_cal: float) -> float:
        scale = _fit_scale(c_cal)
        x_val, p_val = _synthetic_outcomes(2000, seed=2)
        with torch.no_grad():
            probs = torch.softmax(_misspecified_logits(x_val, torch.tensor(scale)), dim=-1)
        pred = probs.numpy().astype(np.float64) @ EQUITY_WEIGHTS
        target = p_val.numpy().astype(np.float64) @ EQUITY_WEIGHTS
        return calibration_metrics(pred, target)["mae"]

    assert mae_for(DEFAULT_C_CAL) < mae_for(0.0)


def test_55_total_loss_v2_weights() -> None:
    """``L = c_value*L_value + c_policy*L_policy + c_cal*L_cal`` (Faz 6 Bolum 5.3)."""
    value_loss = torch.tensor(2.0)
    policy_loss = torch.tensor(3.0)
    cal_loss = torch.tensor(5.0)

    total = total_loss_v2(value_loss, policy_loss, cal_loss, c_value=1.0, c_policy=0.5, c_cal=0.1)
    assert float(total) == pytest.approx(2.0 + 1.5 + 0.5)

    # c_cal = 0 -> L_cal terimi tamamen devre disi.
    without = total_loss_v2(value_loss, policy_loss, cal_loss, c_value=1.0, c_policy=0.5, c_cal=0.0)
    assert float(without) == pytest.approx(3.5)

    # L_cal verilmezse de ayni.
    assert float(total_loss_v2(value_loss, policy_loss, None, c_value=1.0, c_policy=0.5)) == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# Test 56 - LogitTemperatureScaling_UsesCalOnly
# ---------------------------------------------------------------------------


def _cal_and_train_sets():
    """Farkli sicaklik gerektiren iki kume: CAL ve (sizinti testi icin) TRAIN."""
    rng = np.random.default_rng(4242)
    base = normalize_exclusive(rng.random((512, 6)) * 3.0)
    target = equity_from_exclusive(base)

    # CAL: dagilim hedefe gore asiri guvenli -> T > 1 gerekir.
    cal_probs = normalize_exclusive(np.power(base, 3.0))
    # TRAIN: dagilim hedefe gore cok yumusak -> T < 1 gerekir.
    train_probs = normalize_exclusive(np.power(base, 0.4))
    return (cal_probs, target), (train_probs, target)


def test_56_temperature_is_single_scalar() -> None:
    """Tek bir ``T`` ogrenilir; sinif basina ``T`` yoktur (Faz 6 Bolum 6.2)."""
    (cal_probs, cal_target), _ = _cal_and_train_sets()
    temperature = fit_temperature(cal_probs, cal_target)

    assert isinstance(temperature, float)
    assert TEMPERATURE_MIN <= temperature <= TEMPERATURE_MAX

    # Ayni T tum siniflara uygulanir: cikti tek skaler, dizi degil.
    assert np.ndim(temperature) == 0

    # ``assert_single_temperature`` tekrarlanan skaleri kabul eder.
    assert assert_single_temperature([temperature] * 6) == pytest.approx(temperature)
    # Sinif basina farkli T reddedilir.
    with pytest.raises(ValueError):
        assert_single_temperature([1.0, 1.0, 1.0, 2.0, 2.0, 2.0])


def test_56_temperature_uses_cal_only() -> None:
    """Sicaklik **yalnizca** CAL kumesinden ogrenilir; egitim kumesi sizmaz (Kural 10)."""
    (cal_probs, cal_target), (train_probs, train_target) = _cal_and_train_sets()

    t_cal = fit_temperature(cal_probs, cal_target)
    t_train = fit_temperature(train_probs, train_target)

    # Iki kume farkli T gerektirir: fonksiyon gercekten verilen veriyi kullaniyor.
    assert t_cal != pytest.approx(t_train, rel=1e-3)

    # Saflık: ayni CAL girdisi, TRAIN kumesi hic var olmasa da ayni T'yi verir.
    assert fit_temperature(cal_probs, cal_target) == pytest.approx(t_cal, rel=0.0, abs=0.0)

    # CAL'de ogrenilen T, CAL'de equity MAE'sini iyilestirir.
    before = calibration_metrics(equity_from_exclusive(cal_probs), cal_target)["mae"]
    after = calibration_metrics(
        equity_from_exclusive(apply_temperature(cal_probs, t_cal)), cal_target
    )["mae"]
    assert after < before

    # TRAIN'de ogrenilen T, CAL'de daha kotu olmali (sizinti olsaydi boyle olmazdi).
    leaked = calibration_metrics(
        equity_from_exclusive(apply_temperature(cal_probs, t_train)), cal_target
    )["mae"]
    assert leaked > after


def test_56_fit_temperature_signature_has_no_train_arguments() -> None:
    """API yuzeyi sizintiya izin vermez: yalnizca tek kume alinir."""
    for func in (fit_temperature, fit_temperature_ce):
        params = list(inspect.signature(func).parameters)
        assert params[:2] == ["probs", "target_equity"] or params[:2] == ["probs", "target_probs"]
        assert not any("train" in name or "val" in name or "test" in name for name in params), (
            f"{func.__name__} egitim/dogrulama kumesi parametresi almamali: {params}"
        )


def test_56_apply_temperature_direction() -> None:
    """``T > 1`` yumusatir, ``T < 1`` keskinlestirir, ``T = 1`` degistirmez.

    ``p_i' ~ p_i ** (1/T)`` donusumu ``softmax(log p / T)`` ile aynidir; entropi
    ``T`` ile **kesin** olarak artar. Equity buyuklugu eleman bazinda monoton
    olmak zorunda degildir (``E`` sifiri gecebilir), bu yuzden ortalama uzerinden
    dogrulanir.
    """
    rng = np.random.default_rng(99)
    probs = normalize_exclusive(rng.random((64, 6)) * 5.0)

    def mean_entropy(p) -> float:
        return float(np.mean(-np.sum(p * np.log(np.maximum(p, 1e-30)), axis=-1)))

    def mean_abs_equity(p) -> float:
        return float(np.mean(np.abs(equity_from_exclusive(p))))

    assert np.allclose(apply_temperature(probs, 1.0), probs, atol=1e-12)

    softened = apply_temperature(probs, 4.0)
    sharpened = apply_temperature(probs, 0.25)

    assert mean_entropy(sharpened) < mean_entropy(probs) < mean_entropy(softened)
    assert mean_abs_equity(softened) < mean_abs_equity(probs) < mean_abs_equity(sharpened)

    with pytest.raises(ValueError):
        apply_temperature(probs, 0.0)
