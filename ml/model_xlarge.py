"""``xlarge`` kapasite profili icin ince sarmalayici (Faz 7-S).

Mimari :data:`ml.model.CAPACITY_PROFILES` icinde **tek** yerde tanimlidir
(``xlarge = (1024, 1024, 512)``, ~1.8M parametre). Bu modul ayri bir kopya
tutmaz; yalnizca ``xlarge`` profilini sabitleyen, adlandirilmis bir giris
noktasi sunar.

**Siralama kafasi.** Faz 7-S plani xlarge icin 7 cikti (6 softmax + 1 lineer
siralama) ongoruyordu. Siralama kafasi burada **egitim-disi** bir kafa olarak
uygulanir: yalnizca ikili siralama kaybini besler ve ONNX sozlesmesine
**girmez** (``output_version = 2``, iki cikti). Gerekce: 7. cikti C#
``OnnxModelHandle`` sozlesmesini ve ``output_version`` surumunu degistirirdi;
bu ise kapasite deneyinin konusu degil. Siralama kafasinin egitimde kalici
bir kazanc saglayip saglamadigi ``ml/capacity_train.py --rank-weight`` ile
olculur.

Kullanim::

    from model_xlarge import build_xlarge
    model = build_xlarge(seed=0, rank_head=True)
"""

from __future__ import annotations

import torch.nn as nn

from model import CAPACITY_PROFILES, VECTOR_SIZE, build_model

#: Bu modulun sabitledigi profil adi.
PROFILE = "xlarge"

#: Gizli katman genislikleri (``ml.model.CAPACITY_PROFILES`` ile ayni nesne).
HIDDEN = CAPACITY_PROFILES[PROFILE]


def build_xlarge(
    in_dim: int = VECTOR_SIZE, *, seed: int | None = None, rank_head: bool = False
) -> nn.Module:
    """``xlarge`` profilinde ``output_version = 2`` modeli kurar.

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
