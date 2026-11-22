"""``large`` kapasite profili icin ince sarmalayici (Faz 7-S).

Mimari :data:`ml.model.CAPACITY_PROFILES` icinde **tek** yerde tanimlidir
(``large = (512, 512, 512)``, ~642K parametre). Bu modul ayri bir kopya
tutmaz; yalnizca ``large`` profilini sabitleyen, adlandirilmis bir giris
noktasi sunar. Boylece mimari degisikligi tek yerde kalir ve
``build_model(profile="large")`` ile buradaki sarmalayici **ayni** modeli
uretir (bkz. ``ml/tests/test_capacity_profiles.py``).

Kullanim::

    from model_large import build_large
    model = build_large(seed=0)
"""

from __future__ import annotations

import torch.nn as nn

from model import CAPACITY_PROFILES, VECTOR_SIZE, build_model

#: Bu modulun sabitledigi profil adi.
PROFILE = "large"

#: Gizli katman genislikleri (``ml.model.CAPACITY_PROFILES`` ile ayni nesne).
HIDDEN = CAPACITY_PROFILES[PROFILE]


def build_large(
    in_dim: int = VECTOR_SIZE, *, seed: int | None = None, rank_head: bool = False
) -> nn.Module:
    """``large`` profilinde ``output_version = 2`` modeli kurar.

    ``rank_head=True`` iken egitim-disi ikili siralama kafasi da eklenir;
    ``forward`` o zaman ``(probs, policy_logit, rank_logit)`` dondurur.
    """
    return build_model(
        in_dim,
        seed=seed,
        output_version=2,
        profile=PROFILE,
        rank_head=rank_head,
    )
