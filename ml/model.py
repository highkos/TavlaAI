"""Faz 4 v3 Bolum 2 + Faz 6 Bolum 5: ortak govdeli cift basli MLP.

Iki cikti sozlesmesi vardir:

``output_version = 1`` (Faz 4/5, :class:`BackgammonNet`)
    Cikti : ``value`` [B, 1] (dogrusal, kirpilmamis), ``policy_logit`` [B, 1]

``output_version = 2`` (Faz 6, :class:`BackgammonNetV2`)
    Cikti : ``probs`` [B, 6] (softmax, **dislayici** siniflar), ``policy_logit`` [B, 1]

Dislayici sinif sirasi :data:`PROB_ORDER` = ``W, GW, BW, L, GL, BL`` (toplam 1).
Equity bu vektorden ``W + 2*GW + 3*BW - (L + 2*GL + 3*BL)`` ile turetilir; tek
dogruluk kaynagi C# ``OutcomeDistribution.Equity`` ozelligidir (bkz. ``ml/equity.py``).

Politika basi her afterstate icin TEK logit uretir. Grup softmax (ayni karardaki
adaylar arasinda) egitimde kayip icinde, C#'ta ScoreBatch icinde uygulanir.
"""

from __future__ import annotations

import torch
import torch.nn as nn

FEATURE_VERSION = 1
VECTOR_SIZE = 221

#: Faz 6 Bolum 5.1: dislayici sinif sayisi.
PROB_COUNT = 6

#: Faz 6 Bolum 5.1: ``probs`` sutun sirasi (ONNX metadata ``prob_order`` ile ayni).
PROB_ORDER = ("W", "GW", "BW", "L", "GL", "BL")

#: Faz 6 Bolum 5.1: ``probs`` kodlamasi (ONNX metadata ``prob_encoding`` ile ayni).
PROB_ENCODING = "exclusive"

#: Faz 6 Bolum 5.2: kapasite profilleri -> gizli katman genislikleri.
CAPACITY_PROFILES: dict[str, tuple[int, ...]] = {
    "small": (128, 64),
    "medium": (256, 256, 128),
    "large": (512, 512, 512),
    "xlarge": (1024, 1024, 512),
}

#: Faz 6 Bolum 3.1: Track L varsayilan profili.
DEFAULT_PROFILE = "medium"


class Backbone(nn.Module):
    """Ileride kup basi eklenebilsin diye ayri modul (Faz 4b).

    Faz 6 Bolum 5.2: gizli katman sayisi degiskendir (``hidden`` demeti).
    """

    def __init__(self, in_dim: int = VECTOR_SIZE, *hidden: int) -> None:
        super().__init__()
        if not hidden:
            raise ValueError("en az bir gizli katman genisligi gerekli")
        self.in_dim = in_dim
        self.hidden = tuple(int(h) for h in hidden)

        layers: list[nn.Module] = []
        prev = in_dim
        for width in self.hidden:
            layers.append(nn.Linear(prev, width))
            layers.append(nn.GELU())
            prev = width
        self.net = nn.Sequential(*layers)

    @property
    def out_dim(self) -> int:
        return self.hidden[-1]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class BackgammonNet(nn.Module):
    """``output_version = 1``: tek skaler deger basi (Faz 4/5 sozlesmesi)."""

    output_version = 1

    def __init__(self, in_dim: int = VECTOR_SIZE, h1: int = 128, h2: int = 64) -> None:
        super().__init__()
        self.backbone = Backbone(in_dim, h1, h2)
        self.value_head = nn.Linear(h2, 1)
        self.policy_head = nn.Linear(h2, 1)
        # Bolum 2: deger basi bias = 0
        nn.init.zeros_(self.value_head.bias)

    @property
    def arch(self) -> str:
        b = self.backbone
        return "-".join(str(w) for w in (b.in_dim, *b.hidden))

    def forward(self, x: torch.Tensor):
        h = self.backbone(x)
        value = self.value_head(h)
        policy_logit = self.policy_head(h)
        return value, policy_logit


class BackgammonNetV2(nn.Module):
    """``output_version = 2``: 6 cikti li **dislayici** olasilik basi (Faz 6 Bolum 5.1).

    ``probs`` softmax ile uretilir; boylece toplam 1 ve tum bilesenler >= 0 olur.
    Monotonluk **zorlanmaz** (Faz 6 Bolum 5.1): dislayici sinifler arasinda
    ``W >= GW >= BW`` gibi bir zorunlu siralama yoktur.
    """

    output_version = 2

    def __init__(self, in_dim: int = VECTOR_SIZE, *hidden: int) -> None:
        super().__init__()
        if not hidden:
            hidden = CAPACITY_PROFILES[DEFAULT_PROFILE]
        self.backbone = Backbone(in_dim, *hidden)
        self.probs_head = nn.Linear(self.backbone.out_dim, PROB_COUNT)
        self.policy_head = nn.Linear(self.backbone.out_dim, 1)
        # Baslangicta tek-kazanma agirlikli, kucuk mars/backgammon olasiligi: egitim
        # basinda equity ~ 0 ve dagilim gecerli (Faz 6 Bolum 5.1).
        nn.init.zeros_(self.probs_head.bias)
        with torch.no_grad():
            self.probs_head.bias[0] = 1.0
            self.probs_head.bias[3] = 1.0

    @property
    def arch(self) -> str:
        b = self.backbone
        return "-".join(str(w) for w in (b.in_dim, *b.hidden))

    def forward(self, x: torch.Tensor):
        h = self.backbone(x)
        probs = torch.softmax(self.probs_head(h), dim=-1)
        policy_logit = self.policy_head(h)
        return probs, policy_logit


def build_model(
    in_dim: int = VECTOR_SIZE,
    h1: int = 128,
    h2: int = 64,
    seed: int | None = None,
    output_version: int = 1,
    profile: str | None = None,
) -> nn.Module:
    """Model kurar.

    ``output_version = 1`` icin ``h1``/``h2`` kullanilir (Faz 4/5 uyumlulugu).
    ``output_version = 2`` icin ``profile`` (bkz. :data:`CAPACITY_PROFILES`) kullanilir;
    ``profile`` verilmezse :data:`DEFAULT_PROFILE`.
    """
    if seed is not None:
        torch.manual_seed(seed)

    if output_version == 1:
        model: nn.Module = BackgammonNet(in_dim, h1, h2)
    elif output_version == 2:
        name = profile or DEFAULT_PROFILE
        if name not in CAPACITY_PROFILES:
            raise ValueError(
                f"bilinmeyen kapasite profili: {name!r} (gecerli: {sorted(CAPACITY_PROFILES)})"
            )
        model = BackgammonNetV2(in_dim, *CAPACITY_PROFILES[name])
    else:
        raise ValueError(f"desteklenmeyen output_version: {output_version}")

    model.eval()
    return model


def parameter_count(model: nn.Module) -> int:
    """Egitilebilir parametre sayisi (Faz 6 Bolum 5.2 tablosu icin)."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)