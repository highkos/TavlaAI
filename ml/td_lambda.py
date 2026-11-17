"""Faz 4 v3 Bolum 6.2: TD(lambda) forward-view (lambda-return) hedefleri.

gamma = 1, ara odul yok, odul yalnizca oyun sonunda.

Oyun icin kararlar t = 0..T-1; SON karar (t = T-1) terminaldir (kazananin hamlesi).
`mover` her kararda degisir (pas dahil), bu yuzden isaret cevrilir.

    y[T-2] = -z
    y[t]   = -( (1-lam) * V_hat[t+1] + lam * y[t+1] )      t = T-3 .. 0

z = resultPoints / cubeValue, KAZANAN icin pozitif.
"""

from __future__ import annotations

import numpy as np

#: Faz 6 Bolum 8.2 (F4-41): D2 teshisi sonrasi varsayilan ``lambda = 1.0`` (saf Monte
#: Carlo). Faz 4/5'te 0.7 idi; TD hedefi baslangicta yanli oldugu icin kalibrasyonu
#: bozuyordu. ``lambda`` yine de parametre olarak verilebilir.
DEFAULT_LAMBDA = 1.0


def terminal_value(result_points: float, cube_value: float) -> float:
    """Kazanan perspektifinde terminal deger `z = resultPoints / cubeValue`."""
    if cube_value <= 0:
        raise ValueError("cube_value > 0 olmali")
    return float(result_points) / float(cube_value)


def td_lambda_targets(
    v_hat: np.ndarray | list[float],
    z: float,
    lam: float = DEFAULT_LAMBDA,
) -> np.ndarray:
    """`t = 0..T-2` icin lambda-return hedeflerini dondurur.

    Args:
        v_hat: `V_hat_t` degerleri, uzunluk `T-1` (terminal karar deger almaz).
        z: kazanan perspektifinde terminal deger.
        lam: lambda, `[0, 1]`.

    Returns:
        `y` dizisi, uzunluk `T-1`, her eleman `mover_t` perspektifinde.
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lam [0,1] araliginda olmali")

    v = np.asarray(v_hat, dtype=np.float64).reshape(-1)
    n = v.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    y = np.empty(n, dtype=np.float64)
    y[n - 1] = -float(z)
    for t in range(n - 2, -1, -1):
        y[t] = -((1.0 - lam) * v[t + 1] + lam * y[t + 1])
    return y


def td_lambda_targets_masked(
    v_hat: np.ndarray | list[float],
    z: float,
    is_learner: np.ndarray | list[bool],
    lam: float = DEFAULT_LAMBDA,
) -> tuple[np.ndarray, np.ndarray]:
    """Hedefleri hesaplar ve yalnizca `IsLearner` kararlar icin maske dondurur.

    Zincir TUM kararlar uzerinden hesaplanir (rakip kararlarin `V_hat`'i da kullanilir);
    maske yalnizca kaybi kisitlar.
    """
    y = td_lambda_targets(v_hat, z, lam)
    mask = np.asarray(is_learner, dtype=bool).reshape(-1)
    if mask.shape[0] != y.shape[0]:
        raise ValueError("is_learner uzunlugu v_hat ile ayni olmali")
    return y, mask