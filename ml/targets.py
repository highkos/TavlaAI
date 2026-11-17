"""Faz 6 Bolum 8.3: 6 sinifli dislayici deger hedeflerinin kurulmasi.

Shard v1 (``ml/shards.py``) her oyun icin ``winner`` (+1 beyaz / -1 siyah),
``result_type`` (1 Single / 2 Gammon / 3 Backgammon) ve ``result_points`` tasir.
Her karar icin hedef, **karar veren oyuncunun** bakis acisindan yazilir:

    oyuncu kazandi -> ilk uc sutun  (W, GW, BW)
    oyuncu kaybetti -> son uc sutun  (L, GL, BL)

``result_type`` yalnizca **carpani** tasir (``GameResultType``), kazanani tasimaz;
kazanan ayri okunmalidir (Faz 6 Test 41d). Bu modul o ayrimi tek yerde tutar.

Iki hedef turu vardir:

``one_hot``
    Oyun sonucundan dogrudan (Monte Carlo, ``lambda = 1.0``). Varyansi yuksektir
    ama yanli degildir.

``td_lambda``
    ``ml/td_lambda.py`` ile ara deger tahminlerinden. Varyansi dusuktur ama
    baslangicta yanli olabilir. Faz 6 Bolum 8.2 (F4-41) varsayilani ``lambda = 1.0``.
"""

from __future__ import annotations

import numpy as np

from equity import PROB_COUNT, equity_from_exclusive, one_hot_exclusive

#: Faz 6 Bolum 8.2 (F4-41): varsayilan TD lambda. D2 teshisi 1.0'a cekti.
DEFAULT_LAMBDA = 1.0

#: ``GameResultType`` -> dislayici sutun ofseti (0 tabanli).
RESULT_TYPE_OFFSET = {1: 0, 2: 1, 3: 2}


def exclusive_target(winner: int, result_type: int, perspective: int) -> np.ndarray:
    """Tek karar icin dislayici 6'li hedef (``ml.equity.one_hot_exclusive`` sarmali)."""
    return one_hot_exclusive(winner, result_type, perspective)


def exclusive_targets(
    winner: int,
    result_type: int,
    perspectives,
) -> np.ndarray:
    """Bir oyunun tum kararlari icin ``[N, 6]`` hedef matrisi."""
    persp = np.asarray(perspectives, dtype=np.int64).reshape(-1)
    out = np.zeros((persp.size, PROB_COUNT), dtype=np.float64)
    for i, p in enumerate(persp):
        out[i] = one_hot_exclusive(winner, result_type, int(p))
    return out


def target_equity(winner: int, result_type: int, perspective: int) -> float:
    """Tek karar icin hedef equity (oyun sonucundan, ``lambda = 1.0``)."""
    return float(equity_from_exclusive(exclusive_target(winner, result_type, perspective)))


def target_equities(winner: int, result_type: int, perspectives) -> np.ndarray:
    """Bir oyunun tum kararlari icin hedef equity vektoru."""
    return equity_from_exclusive(exclusive_targets(winner, result_type, perspectives))


def validate_result(winner: int, result_type: int) -> None:
    """Shard alanlarinin tutarliligini dogrular (Faz 6 Test 41d)."""
    if winner not in (1, -1):
        raise ValueError(f"winner +1 veya -1 olmali: {winner}")
    if result_type not in RESULT_TYPE_OFFSET:
        raise ValueError(f"result_type 1..3 olmali: {result_type}")


def result_points_from_type(result_type: int) -> int:
    """``result_type`` -> mars carpani (1/2/3). ``cubeValue`` burada uygulanmaz."""
    if result_type not in RESULT_TYPE_OFFSET:
        raise ValueError(f"result_type 1..3 olmali: {result_type}")
    return result_type


def mix_targets(one_hot: np.ndarray, td: np.ndarray, lam: float = DEFAULT_LAMBDA) -> np.ndarray:
    """``lam = 1`` -> saf Monte Carlo; ``lam = 0`` -> saf TD. Arada dogrusal karisim."""
    if not 0.0 <= lam <= 1.0:
        raise ValueError(f"lambda 0..1 araliginda olmali: {lam}")
    a = np.asarray(one_hot, dtype=np.float64)
    b = np.asarray(td, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"sekil uyusmuyor: {a.shape} vs {b.shape}")
    return lam * a + (1.0 - lam) * b