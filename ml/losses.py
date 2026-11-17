"""Faz 4 v3 Bolum 6.3 / 6.4: grup softmax capraz entropi ve toplam kayip.

Politika hedefi: `pi_k = softmax_{k in E}(Q_k / tau_train)`.
Ag dagilimi   : `p_k  = softmax_{k in E}(logit_k)`.
Kayip         : `L_policy = -sum_k pi_k * log p_k`, karar basina, sonra kararlar uzerinden ortalama.

`E` = loglanan adaylar (Kind == 1). Terminal (Kind == 0) ve Kind == 2 adaylar HARIC.
`|E| < 2` olan kararlar politika kaybindan ATLANIR.
"""

from __future__ import annotations

import numpy as np

DEFAULT_TAU_TRAIN = 0.05
DEFAULT_C_POLICY = 1.0


def policy_targets_from_q(q: np.ndarray | list[float], tau: float) -> np.ndarray:
    """`softmax(q / tau)` (sayisal kararlilik icin max cikarilir)."""
    if tau <= 0.0:
        raise ValueError("tau > 0 olmali")
    arr = np.asarray(q, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return np.zeros(0, dtype=np.float64)
    scaled = arr / tau
    scaled = scaled - np.max(scaled)
    e = np.exp(scaled)
    return e / np.sum(e)


def _segment_softmax(logits: np.ndarray, sizes: list[int]) -> np.ndarray:
    out = np.empty_like(logits)
    start = 0
    for n in sizes:
        seg = logits[start:start + n]
        m = np.max(seg)
        e = np.exp(seg - m)
        out[start:start + n] = e / np.sum(e)
        start += n
    return out


def policy_loss_numpy(
    logits: np.ndarray | list[float],
    target_probs: np.ndarray | list[float],
    group_sizes: list[int],
    *,
    min_group: int = 2,
) -> tuple[float, int]:
    """Grup softmax CE (numpy referansi).

    Args:
        logits: tum gruplarin logitleri, ardisik.
        target_probs: ayni sirada hedef olasiliklar (her grup icinde toplam 1).
        group_sizes: grup uzunluklari.
        min_group: bu uzunlugun altindaki gruplar atlanir.

    Returns:
        `(ortalama_kayip, kullanilan_grup_sayisi)`. Kullanilan grup yoksa `(0.0, 0)`.
    """
    lg = np.asarray(logits, dtype=np.float64).reshape(-1)
    tp = np.asarray(target_probs, dtype=np.float64).reshape(-1)
    if lg.shape != tp.shape:
        raise ValueError("logits ve target_probs ayni uzunlukta olmali")
    if sum(group_sizes) != lg.shape[0]:
        raise ValueError("group_sizes toplami logits uzunluguna esit olmali")

    probs = _segment_softmax(lg, group_sizes)
    total = 0.0
    used = 0
    start = 0
    for n in group_sizes:
        if n >= min_group:
            seg_p = probs[start:start + n]
            seg_t = tp[start:start + n]
            total += -float(np.sum(seg_t * np.log(np.maximum(seg_p, 1e-30))))
            used += 1
        start += n
    return (total / used if used else 0.0), used


def policy_loss_torch(logits, target_probs, group_sizes, *, min_group: int = 2):
    """Grup softmax CE (torch, egitim icin). `logits`/`target_probs` 1-B tensordur."""
    import torch

    total = logits.new_zeros(())
    used = 0
    start = 0
    for n in group_sizes:
        if n >= min_group:
            seg_l = logits[start:start + n]
            seg_t = target_probs[start:start + n]
            log_p = torch.log_softmax(seg_l, dim=0)
            total = total - torch.sum(seg_t * log_p)
            used += 1
        start += n
    if used == 0:
        return logits.new_zeros(())
    return total / used


def value_loss_mse(pred, target):
    """MSE (Faz 4 v3 Bolum 6.2)."""
    import torch

    return torch.mean((pred - target) ** 2)


def value_loss_huber(pred, target, delta: float = 1.0):
    """Huber (opsiyonel, yapilandirmadan)."""
    import torch

    return torch.nn.functional.huber_loss(pred, target, delta=delta)


def total_loss(value_loss, policy_loss, c_policy: float = DEFAULT_C_POLICY):
    """`loss = L_value + c_policy * L_policy`."""
    return value_loss + c_policy * policy_loss


def target_entropy_ratio(target_probs: np.ndarray | list[float], group_sizes: list[int]) -> float:
    """Hedef entropisinin `log|E|`'ye orani (duzgun hedef kontrolu, Bolum 6.3).

    1.0'a yakin => hedef neredeyse duzgun (ogrenme oldurucu). Kucuk => keskin hedef.
    """
    tp = np.asarray(target_probs, dtype=np.float64).reshape(-1)
    total = 0.0
    total_max = 0.0
    start = 0
    for n in group_sizes:
        if n >= 2:
            seg = tp[start:start + n]
            total += -float(np.sum(seg * np.log(np.maximum(seg, 1e-30))))
            total_max += float(np.log(n))
        start += n
    if total_max <= 0.0:
        return 0.0
    return total / total_max

# ---------------------------------------------------------------------------
# Faz 6 Bolum 5.3: 6 cikti li deger kafasi kaybi
# ---------------------------------------------------------------------------

#: Faz 6 Bolum 5.3: kalibrasyon kaybi agirligi.
DEFAULT_C_CAL = 0.1

#: Faz 6 Bolum 5.3: deger kaybi agirligi.
DEFAULT_C_VALUE = 1.0


def value_loss_ce_6class(probs, target_probs):
    """6 sinifli dislayici capraz entropi (Faz 6 Bolum 5.3).

    ``probs`` ve ``target_probs`` sekli ``[B, 6]`` (veya ``[6]``). Hedefler tek-sicak
    (one-hot) veya yumusak olabilir. ``L_value = -sum_i t_i * log p_i``, batch uzerinden
    ortalama.
    """
    import torch

    p = probs if probs.dim() > 1 else probs.unsqueeze(0)
    t = target_probs if target_probs.dim() > 1 else target_probs.unsqueeze(0)
    if p.shape[-1] != 6:
        raise ValueError(f"probs son ekseni 6 olmali: {tuple(p.shape)}")
    if t.shape != p.shape:
        raise ValueError(f"hedef sekli {tuple(t.shape)} != probs {tuple(p.shape)}")
    log_p = torch.log(torch.clamp(p, min=1e-30))
    return -torch.mean(torch.sum(t * log_p, dim=-1))


def calibration_loss(equity_pred, equity_target):
    """``L_cal = mean((E_pred - E_target)^2)`` (Faz 6 Bolum 5.3).

    Equity tahmini ``probs``'tan turetilir (``ml.equity.equity_from_exclusive``);
    hedef equity oyun sonucundan gelir. Bu terim, dagilimin *buyuklugunu* degil
    *beklenen degerini* dogru vermesini zorlar; tek basina CE bunu garanti etmez.
    """
    import torch

    return torch.mean((equity_pred - equity_target) ** 2)


def total_loss_v2(
    value_loss,
    policy_loss,
    cal_loss=None,
    c_value: float = DEFAULT_C_VALUE,
    c_policy: float = DEFAULT_C_POLICY,
    c_cal: float = DEFAULT_C_CAL,
):
    """``L = c_value*L_value + c_policy*L_policy + c_cal*L_cal`` (Faz 6 Bolum 5.3)."""
    total = c_value * value_loss + c_policy * policy_loss
    if cal_loss is not None and c_cal != 0.0:
        total = total + c_cal * cal_loss
    return total