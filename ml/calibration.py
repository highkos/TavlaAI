"""Faz 6 Bolum 6: kalibrasyon teshisi, kabul kriterleri ve logit sicaklik olcekleme.

Faz 5 taban cizgisi (``ml/artifacts/stage_f_baseline.md``):

    egim (slope)      = 0.2431   (kabul: 0.85 .. 1.15)
    korelasyon        = 0.2431   (kabul: >= 0.75)
    MAE               = 0.8014   (kabul: <= 0.15)
    deger std orani   = 2.78     (kabul: 0.7 .. 1.4)

Yani ag, equity'nin **yonunu** kismen biliyor ama **buyuklugunu** fena halde
abartiyor. Bu modul, kalibrasyonun olculmesini ve duzeltilmesini saglar.

Yukseltme sirasi (Faz 6 Bolum 6.2) — **bu sirayla** uygulanir, atlanmaz:

    1. 6 cikti li deger kafasi (``output_version = 2``)
    2. ``L_cal`` terimi (``c_cal = 0.1``)
    3. logit sicaklik olcekleme: ``p_i' ~ p_i ** (1/T)``, **tek** ``T``
    4. isotonic regression (son care; monotonik olmayan iliskiyi duzeltemez)

Sicaklik **yalnizca CAL kumesinden** ogrenilir (Faz 6 Bolum 6.4 / Kural 10).
VAL ve TEST kumeleri sicakligi gormez; aksi halde raporlanan kalibrasyon iyimser olur.
"""

from __future__ import annotations

import numpy as np

from equity import PROB_COUNT, equity_from_exclusive, normalize_exclusive

#: Faz 6 Bolum 6.3: kabul kriterleri.
SLOPE_MIN = 0.85
SLOPE_MAX = 1.15
CORRELATION_MIN = 0.75
MAE_MAX = 0.15
STD_RATIO_MIN = 0.7
STD_RATIO_MAX = 1.4

#: Faz 5 taban cizgisi (raporlama icin).
BASELINE_SLOPE = 0.2431
BASELINE_CORRELATION = 0.2431
BASELINE_MAE = 0.8014
BASELINE_STD_RATIO = 2.78

#: Sicaklik arama araligi (Faz 6 Bolum 6.2).
TEMPERATURE_MIN = 0.05
TEMPERATURE_MAX = 20.0


def calibration_metrics(pred_equity, target_equity) -> dict[str, float]:
    """Kalibrasyon metrikleri (Faz 6 Bolum 6.3).

    ``slope``      : ``target``'in ``pred`` uzerine en kucuk kareler egimi. 1 = kalibre.
    ``intercept``  : ayni dogrunun kesisimi.
    ``correlation``: Pearson korelasyonu.
    ``mae``        : ortalama mutlak hata.
    ``std_ratio``  : ``std(pred) / std(target)``. 1 = olcek dogru.
    """
    p = np.asarray(pred_equity, dtype=np.float64).reshape(-1)
    t = np.asarray(target_equity, dtype=np.float64).reshape(-1)
    if p.shape != t.shape:
        raise ValueError(f"sekil uyusmuyor: {p.shape} vs {t.shape}")
    if p.size < 2:
        raise ValueError("en az 2 ornek gerekli")

    p_mean = float(np.mean(p))
    t_mean = float(np.mean(t))
    p_var = float(np.var(p))
    t_var = float(np.var(t))

    if p_var <= 0.0:
        slope = 0.0
        intercept = t_mean
        corr = 0.0
    else:
        cov = float(np.mean((p - p_mean) * (t - t_mean)))
        slope = cov / p_var
        intercept = t_mean - slope * p_mean
        if t_var <= 0.0:
            corr = 0.0
        else:
            corr = cov / float(np.sqrt(p_var * t_var))

    mae = float(np.mean(np.abs(p - t)))
    std_ratio = float(np.sqrt(p_var) / np.sqrt(t_var)) if t_var > 0.0 else float("inf")

    return {
        "slope": slope,
        "intercept": intercept,
        "correlation": corr,
        "mae": mae,
        "std_ratio": std_ratio,
        "count": float(p.size),
    }


def is_calibrated(metrics: dict[str, float]) -> bool:
    """Faz 6 Bolum 6.3 kabul kriterlerinin tamami saglaniyor mu?"""
    return (
        SLOPE_MIN <= metrics["slope"] <= SLOPE_MAX
        and metrics["correlation"] >= CORRELATION_MIN
        and metrics["mae"] <= MAE_MAX
        and STD_RATIO_MIN <= metrics["std_ratio"] <= STD_RATIO_MAX
    )


def apply_temperature(probs, temperature: float) -> np.ndarray:
    """``p_i' ~ p_i ** (1/T)``, sonra normalize (Faz 6 Bolum 6.2 adim 3).

    ``T > 1`` dagilimi **yumusatir** (asiri guveni azaltir), ``T < 1`` keskinlestirir.
    ``T = 1`` degistirmez.
    """
    if temperature <= 0.0:
        raise ValueError("temperature > 0 olmali")
    p = normalize_exclusive(probs)
    if temperature == 1.0:
        return p
    powered = np.power(np.maximum(p, 1e-30), 1.0 / temperature)
    return powered / np.sum(powered, axis=-1, keepdims=True)


def fit_temperature(probs, target_equity, *, grid_size: int = 400) -> float:
    """**Yalnizca CAL kumesi** uzerinde tek bir ``T`` ogrenir (Faz 6 Bolum 6.2/6.4).

    Amac: sicaklik uygulanmis dagilimin equity'si ile hedef equity arasindaki
    ortalama mutlak hatayi en kucuk yapan ``T``'yi bulmak. Izgara aramasi kullanilir
    (deterministik, turev gerekmez, tek parametre).

    Args:
        probs: ``[N, 6]`` dislayici olasiliklar (CAL kumesi).
        target_equity: ``[N]`` hedef equity (CAL kumesi).
        grid_size: log-uzayda izgara noktasi sayisi.

    Returns:
        Secilen ``T`` (``TEMPERATURE_MIN .. TEMPERATURE_MAX`` araliginda).
    """
    p = normalize_exclusive(probs)
    t = np.asarray(target_equity, dtype=np.float64).reshape(-1)
    if p.shape[0] != t.shape[0]:
        raise ValueError(f"ornek sayisi uyusmuyor: {p.shape[0]} vs {t.shape[0]}")
    if p.shape[0] == 0:
        raise ValueError("bos CAL kumesi")

    grid = np.geomspace(TEMPERATURE_MIN, TEMPERATURE_MAX, grid_size)
    best_t = 1.0
    best_err = float("inf")
    for temperature in grid:
        scaled = apply_temperature(p, float(temperature))
        err = float(np.mean(np.abs(equity_from_exclusive(scaled) - t)))
        if err < best_err:
            best_err = err
            best_t = float(temperature)
    return best_t


def fit_temperature_ce(probs, target_probs, *, grid_size: int = 400) -> float:
    """Alternatif: CAL kumesinde capraz entropiyi en kucuk yapan ``T``.

    Equity-MAE yerine log-olabilirlik hedeflenir. Iki olcut de yalnizca CAL kumesini
    kullanir; hangisinin secilecegi ``ml/diagnose.py`` raporunda karsilastirilir.
    """
    p = normalize_exclusive(probs)
    t = np.asarray(target_probs, dtype=np.float64)
    if p.shape != t.shape:
        raise ValueError(f"sekil uyusmuyor: {p.shape} vs {t.shape}")

    grid = np.geomspace(TEMPERATURE_MIN, TEMPERATURE_MAX, grid_size)
    best_t = 1.0
    best_err = float("inf")
    for temperature in grid:
        scaled = apply_temperature(p, float(temperature))
        err = -float(np.mean(np.sum(t * np.log(np.maximum(scaled, 1e-30)), axis=-1)))
        if err < best_err:
            best_err = err
            best_t = float(temperature)
    return best_t


def assert_single_temperature(temperatures) -> float:
    """Tek bir ``T`` kullanildigini dogrular (Faz 6 Bolum 6.2: sinif basina ``T`` YOK)."""
    arr = np.asarray(list(temperatures), dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError("bos sicaklik listesi")
    if not np.allclose(arr, arr[0], rtol=0.0, atol=1e-12):
        raise ValueError(f"tek sicaklik bekleniyordu, farkli degerler: {sorted(set(arr.tolist()))}")
    return float(arr[0])


def prob_count() -> int:
    """Dislayici sinif sayisi (C# ``OutcomeDistribution.ProbabilityCount`` ile ayni)."""
    return PROB_COUNT