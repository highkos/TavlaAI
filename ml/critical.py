#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.3 - kritik karar agirliklandirma (Test 98).

**Fikir.** ER, **kritik** kararlarda kazanilir; ortalama pozisyonlar zaten
kolaydir. Bu yuzden ``|equity|`` buyuk **ve** karar marji kucuk kararlar
ornekleme agirligini **2x** alir (Bolum 5.3).

**Neden ornekleme agirligi, kayip agirligi degil?** Belge "ornekleme agirligini
2x alir" der. Kayip agirligi gradyan olcegini degistirir ve ogrenme oranini
yeniden ayarlamayi gerektirir; ornekleme agirligi ise yalnizca hangi orneklerin
daha sik gorulecegini degistirir ve mevcut egitim dongusune **tek satirla**
girer. Bu yuzden ``rng.choice(n, size=k, p=weights)`` kullanilir.

**Iki kafa, iki olcut.** Karar marji **politika** orneklerinde ``PolicySample.q``
uzerinden olculur. Deger orneklerinde aday kumesi ornekte tasinmaz; bu yuzden
marj, ornegin uretildigi **shard kararindan** (``DecisionRecord.q``) alinip
``ExclusiveSamples.margin`` alanina yazilir (bkz. F7-08).

**F7-08 - eski deger olcutu dejeneresti.** Ilk surum deger kafasi icin
``|equity(y)| >= 0,5`` kullaniyordu. Para oyununda bir deger orneginin equity'si
**her zaman** +-1, +-2 veya +-3'tur; dolayisiyla esik **hicbir seyi ayirmaz**
(olculen: 1 187 935 / 1 187 935 = %100). Bu yuzden deger kafasi artik **marj**
olcutunu kullanir: ER yalnizca **marji kucuk** kararlarda kaybedilir, cunku
deger hatasi ancak marj kucukken secimi degistirebilir. Marj olcutu ayirt
edicidir (politika yarisinda %26 kritik olculdu).

Eski equity olcutu **silinmedi**: ``critical_mask_value`` hala vardir, ancak
``build_report`` onu yalnizca marj **verilmediginde** kullanir ve rapora
``criterion = "equity"`` + ``degenerate = true`` yazar. Sessizce etkisiz bir
agirliklandirma calistirmak, "kritik agirliklandirma yapildi" yanilgisini uretirdi.

Kullanim::

    from critical import critical_mask_policy, sampling_weights, weight_distribution
    mask = critical_mask_policy(policy_samples)
    weights = sampling_weights(mask)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

#: Faz 7 Bolum 5.3: kritik kararin ornekleme agirligi.
CRITICAL_BOOST = 2.0

#: ``|equity|`` esigi: bu degerin altindaki pozisyonlar "kolay" sayilir.
CRITICAL_EQUITY_THRESHOLD = 0.5

#: Karar marji esigi: en iyi iki aday arasindaki fark bunun altindaysa karar kritik.
CRITICAL_MARGIN_THRESHOLD = 0.05

#: Deger kafasi kritiklik olcutu: karar marji (F7-08 duzeltmesi).
VALUE_CRITERION_MARGIN = "margin"

#: Deger kafasi kritiklik olcutu: ``|equity(y)|`` (para oyununda **dejenere**).
VALUE_CRITERION_EQUITY = "equity"


class CriticalError(ValueError):
    """Kritiklik hesabi yapilamadi."""


# ----------------------------------------------------------------------
# Tek karar
# ----------------------------------------------------------------------


def decision_margin(q: Sequence[float] | np.ndarray) -> float:
    """En iyi iki aday arasindaki equity farki (``|E| < 2`` ise 0.0)."""
    values = np.asarray(q, dtype=np.float64).reshape(-1)
    if values.size < 2:
        return 0.0
    if not np.all(np.isfinite(values)):
        raise CriticalError("q sonlu olmali")
    top2 = np.sort(values)[-2:]
    return float(top2[1] - top2[0])


def best_equity(q: Sequence[float] | np.ndarray) -> float:
    """En iyi adayin equity'si (``|E| == 0`` ise 0.0)."""
    values = np.asarray(q, dtype=np.float64).reshape(-1)
    if values.size == 0:
        return 0.0
    if not np.all(np.isfinite(values)):
        raise CriticalError("q sonlu olmali")
    return float(np.max(values))


def is_critical(
    q: Sequence[float] | np.ndarray,
    *,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
    margin_threshold: float = CRITICAL_MARGIN_THRESHOLD,
) -> bool:
    """``|equity|`` buyuk **ve** marj kucuk mu (Bolum 5.3 tanimi)."""
    if equity_threshold < 0.0:
        raise CriticalError("equity_threshold negatif olamaz")
    if margin_threshold < 0.0:
        raise CriticalError("margin_threshold negatif olamaz")
    return (
        abs(best_equity(q)) >= float(equity_threshold)
        and decision_margin(q) <= float(margin_threshold)
    )


# ----------------------------------------------------------------------
# Maskeler
# ----------------------------------------------------------------------


def critical_mask_policy(
    samples: Sequence[Any],
    *,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
    margin_threshold: float = CRITICAL_MARGIN_THRESHOLD,
) -> np.ndarray:
    """Politika ornekleri icin kritiklik maskesi (``q`` uzerinden)."""
    mask = np.zeros((len(samples),), dtype=bool)
    for i, sample in enumerate(samples):
        q = getattr(sample, "q", None)
        if q is None:
            continue
        mask[i] = is_critical(
            q,
            equity_threshold=equity_threshold,
            margin_threshold=margin_threshold,
        )
    return mask


def critical_mask_value(
    samples: Any,
    *,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
) -> np.ndarray:
    """Deger ornekleri icin kritiklik maskesi (``|equity(y)|`` uzerinden).

    Deger orneklerinde aday kumesi yoktur; bu yuzden **yalnizca** equity
    buyuklugu kullanilir. Marj olcutu burada **uygulanamaz** ve uygulanmis gibi
    raporlanmaz.
    """
    equity = np.asarray(samples.equity, dtype=np.float64).reshape(-1)
    if equity.size == 0:
        return np.zeros((0,), dtype=bool)
    if not np.all(np.isfinite(equity)):
        raise CriticalError("equity sonlu olmali")
    return np.abs(equity) >= float(equity_threshold)


def critical_mask_value_margin(
    margins: Sequence[float] | np.ndarray,
    *,
    best_equity: Sequence[float] | np.ndarray | None = None,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
    margin_threshold: float = CRITICAL_MARGIN_THRESHOLD,
) -> np.ndarray:
    """Deger ornekleri icin **karar** tabanli kritiklik maskesi (F7-08 duzeltmesi).

    ``margins[i]``, ``i``. deger orneginin uretildigi kararda en iyi iki aday
    arasindaki equity farkidir. Marj kucukse deger hatasi secimi degistirebilir;
    ER tam olarak orada kaybedilir.

    Args:
        margins: Karar marjlari.
        best_equity: Verilirse Bolum 5.3'un **tam** olcutu uygulanir:
            ``|best_equity| >= equity_threshold`` **ve** ``margin <= margin_threshold``.
            Verilmezse yalnizca marj olcutu kullanilir. ``best_equity`` burada
            **arama degeri**dir (hedef equity degil); para oyununda hedef equity
            her zaman +-1 oldugu icin eski olcut dejenere oluyordu (F7-08).
        equity_threshold: ``|best_equity|`` esigi.
        margin_threshold: Marj esigi.

    ``NaN`` marj (shard'da ``q`` yok) **kritik sayilmaz** - bilinmeyen bir marj
    icin agirlik uydurulmaz.
    """
    if margin_threshold < 0.0:
        raise CriticalError("margin_threshold negatif olamaz")
    if equity_threshold < 0.0:
        raise CriticalError("equity_threshold negatif olamaz")

    values = np.asarray(margins, dtype=np.float64).reshape(-1)
    if values.size == 0:
        return np.zeros((0,), dtype=bool)

    finite = np.isfinite(values)
    mask = np.zeros(values.shape, dtype=bool)
    mask[finite] = values[finite] <= float(margin_threshold)

    if best_equity is not None:
        best = np.asarray(best_equity, dtype=np.float64).reshape(-1)
        if best.shape != values.shape:
            raise CriticalError(
                "best_equity ve margins ayni uzunlukta olmali: "
                + str(best.shape) + " vs " + str(values.shape)
            )
        best_finite = np.isfinite(best)
        mask &= best_finite & (np.abs(np.where(best_finite, best, 0.0)) >= float(equity_threshold))

    return mask


# ----------------------------------------------------------------------
# Agirliklar
# ----------------------------------------------------------------------


def sampling_weights(
    mask: np.ndarray, *, boost: float = CRITICAL_BOOST
) -> np.ndarray:
    """Maskeden normalize ornekleme agirligi uretir (toplam 1)."""
    flags = np.asarray(mask, dtype=bool).reshape(-1)
    if boost < 1.0:
        raise CriticalError("boost >= 1.0 olmali")
    if flags.size == 0:
        return np.zeros((0,), dtype=np.float64)
    weights = np.where(flags, float(boost), 1.0)
    total = float(np.sum(weights))
    if not math.isfinite(total) or total <= 0.0:
        raise CriticalError("agirlik toplami gecersiz")
    return weights / total


def weight_distribution(
    mask: np.ndarray,
    *,
    boost: float = CRITICAL_BOOST,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
    margin_threshold: float = CRITICAL_MARGIN_THRESHOLD,
    criterion: str = VALUE_CRITERION_EQUITY,
) -> dict[str, Any]:
    """Dagilim raporu (Test 98 "dagilim raporlanir" kosulu)."""
    flags = np.asarray(mask, dtype=bool).reshape(-1)
    count = int(flags.size)
    critical = int(np.count_nonzero(flags))
    weights = sampling_weights(flags, boost=boost)
    effective = float(1.0 / np.sum(weights ** 2)) if count else 0.0
    share = (critical / count) if count else 0.0
    return {
        "count": count,
        "critical": critical,
        "criticalShare": share,
        # Ayirt edicilik yoksa agirliklandirma sessizce "tekduze" olur; bunu
        # gizlemek yerine isaretleriz (bkz. F7-08).
        "degenerate": bool(count == 0 or share <= 0.0 or share >= 1.0),
        "criterion": str(criterion),
        "boost": float(boost),
        "equityThreshold": float(equity_threshold),
        "marginThreshold": float(margin_threshold),
        "effectiveCount": effective,
        "effectiveShare": (effective / count) if count else 0.0,
        "meanWeight": float(np.mean(weights)) if count else 0.0,
        "maxWeight": float(np.max(weights)) if count else 0.0,
    }


@dataclass
class CriticalReport:
    """Iki kafanin kritiklik ozeti."""

    value: dict[str, Any]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "policy": self.policy}


def build_report(
    value_samples: Any,
    policy_samples: Sequence[Any],
    *,
    value_margins: Sequence[float] | np.ndarray | None = None,
    value_best_equity: Sequence[float] | np.ndarray | None = None,
    boost: float = CRITICAL_BOOST,
    equity_threshold: float = CRITICAL_EQUITY_THRESHOLD,
    margin_threshold: float = CRITICAL_MARGIN_THRESHOLD,
) -> CriticalReport:
    """Iki kafa icin kritiklik dagilimini uretir.

    Args:
        value_samples: ``.equity`` tasiyan deger ornekleri.
        policy_samples: ``.q`` tasiyan politika ornekleri.
        value_margins: Deger orneklerinin karar marjlari. **Verilirse** deger
            kafasi marj olcutunu kullanir (F7-08 duzeltmesi). Verilmezse eski
            ``|equity|`` olcutune duser ve bu durum ``criterion``/``degenerate``
            alanlarinda **acikca** raporlanir.
        value_best_equity: Deger orneklerinin kararlarindaki **arama degeri**.
            Verilirse Bolum 5.3'un tam olcutu (``|equity|`` **ve** marj) uygulanir.
    """
    if value_margins is not None:
        value_mask = critical_mask_value_margin(
            value_margins,
            best_equity=value_best_equity,
            equity_threshold=equity_threshold,
            margin_threshold=margin_threshold,
        )
        value_criterion = VALUE_CRITERION_MARGIN
    else:
        value_mask = critical_mask_value(value_samples, equity_threshold=equity_threshold)
        value_criterion = VALUE_CRITERION_EQUITY

    policy_mask = critical_mask_policy(
        policy_samples,
        equity_threshold=equity_threshold,
        margin_threshold=margin_threshold,
    )
    return CriticalReport(
        value=weight_distribution(
            value_mask,
            boost=boost,
            equity_threshold=equity_threshold,
            margin_threshold=margin_threshold,
            criterion=value_criterion,
        ),
        policy=weight_distribution(
            policy_mask,
            boost=boost,
            equity_threshold=equity_threshold,
            margin_threshold=margin_threshold,
            criterion=VALUE_CRITERION_MARGIN,
        ),
    )
