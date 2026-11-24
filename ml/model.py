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

import math

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

#: Renk takasi (``antisymmetry.flip_perspective``) girdi uzerinde bir **girisimdir**
#: (``T^2 = I``). Bu yuzden girdi uzayi iki alt uzaya ayrilir:
#: ``V+ = {v : Tv = v}`` (simetrik) ve ``V- = {v : Tv = -v}`` (antisimetrik).
#: Asagidaki iki fonksiyon bu ayrimi **tam** olarak kurar; mimari kisiti
#: (Higgins agirlik simetrisi) bunun uzerine oturur.
_POINT_BLOCKS = 24
_BLOCK_WIDTH = 4
_AWAY_WIDTH = 8


def _flip_map() -> list[tuple[int, float]]:
    """``T`` permutasyonu: ``T e_i = isaret * e_j`` (bkz. ``antisymmetry.flip_perspective``).

    Nokta bloklari ``ACTIVE <-> OPP`` yer degistirir **ve** her blok icinde 24
    nokta blogu ters cevrilir (bloklar "haneden cikisa uzaklik" ile indekslenir).
    Skaler noronlar (bar, off, pip, escaped, away) yer degistirir; kup sahibi
    isaret dondurur; para/Crawford/contact bayraklari ayni kalir.
    """
    out: list[tuple[int, float]] = [(i, 1.0) for i in range(VECTOR_SIZE)]
    width = _POINT_BLOCKS * _BLOCK_WIDTH
    for i in range(width):
        out[i] = (width + _BLOCK_WIDTH * (23 - i // _BLOCK_WIDTH) + i % _BLOCK_WIDTH, 1.0)
    for i in range(width, 2 * width):
        k = i - width
        out[i] = (_BLOCK_WIDTH * (23 - k // _BLOCK_WIDTH) + k % _BLOCK_WIDTH, 1.0)
    for left, right in ((192, 193), (194, 195), (200, 201), (202, 203)):
        out[left] = (right, 1.0)
        out[right] = (left, 1.0)
    out[196] = (196, -1.0)  # CUBE_OWNER: goreli kup sahibi isaret dondurur
    for k in range(_AWAY_WIDTH):
        out[205 + k] = (213 + k, 1.0)
        out[213 + k] = (205 + k, 1.0)
    return out


def symmetry_bases() -> tuple[torch.Tensor, torch.Tensor]:
    """``(Q_minus, Q_plus)``: ``V-`` ve ``V+`` icin **ortonormal** bazlar.

    ``Q_minus`` ``[221, 109]``, ``Q_plus`` ``[221, 112]``. Her ikisi de sabittir
    (ogrenilmez) ve ONNX'e tampon olarak gomulur. ``u = x @ Q_minus`` girdinin
    antisimetrik, ``s = x @ Q_plus`` simetrik bilesenidir; ``x = u @ Q_minus^T +
    s @ Q_plus^T`` (bazlar tam).
    """
    fmap = _flip_map()
    seen = [False] * VECTOR_SIZE
    minus_cols: list[torch.Tensor] = []
    plus_cols: list[torch.Tensor] = []
    root = math.sqrt(2.0)
    for i in range(VECTOR_SIZE):
        if seen[i]:
            continue
        j, sign = fmap[i]
        if j == i:
            seen[i] = True
            col = torch.zeros(VECTOR_SIZE, dtype=torch.float32)
            col[i] = 1.0
            (minus_cols if sign < 0 else plus_cols).append(col)
            continue
        seen[i] = seen[j] = True
        plus = torch.zeros(VECTOR_SIZE, dtype=torch.float32)
        plus[i] = 1.0
        plus[j] = 1.0
        minus = torch.zeros(VECTOR_SIZE, dtype=torch.float32)
        minus[i] = 1.0
        minus[j] = -1.0
        plus_cols.append(plus / root)
        minus_cols.append(minus / root)
    return torch.stack(minus_cols, dim=1), torch.stack(plus_cols, dim=1)


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

    ``rank_head=True`` iken ek bir **siralama kafasi** (tek dogrusal cikti) eklenir
    ve ``forward`` uc deger dondurur. Bu kafa **yalnizca egitimde** kullanilir
    (ikili siralama kaybi); ONNX sozlesmesi degismez cunku ihracatta
    ``rank_head=False`` ile model yeniden kurulur (bkz. ``ml/capacity_train.py``).
    """

    output_version = 2

    def __init__(
        self, in_dim: int = VECTOR_SIZE, *hidden: int, rank_head: bool = False
    ) -> None:
        super().__init__()
        if not hidden:
            hidden = CAPACITY_PROFILES[DEFAULT_PROFILE]
        self.backbone = Backbone(in_dim, *hidden)
        self.probs_head = nn.Linear(self.backbone.out_dim, PROB_COUNT)
        self.policy_head = nn.Linear(self.backbone.out_dim, 1)
        self.rank_head: nn.Linear | None = (
            nn.Linear(self.backbone.out_dim, 1) if rank_head else None
        )
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
        if self.rank_head is not None:
            return probs, policy_logit, self.rank_head(h)
        return probs, policy_logit


class SymmetricBackbone(nn.Module):
    """Renk takasina gore **tam** antisimetrik govde (Higgins agirlik simetrisi).

    Girdi once ``V-`` (109) ve ``V+`` (112) bilesenlerine ayrilir. Tek (odd)
    kol ``u`` uzerinde **bias'siz** dogrusal katmanlar ve **tek** aktivasyonla
    (``tanh``) calisir; boylece ``h(Tx) = -h(x)`` **tam** saglanir. Cift (even)
    kol ``s`` uzerinde serbest bir MLP'dir ve ``e(Tx) = e(x)``.

    Neden ``GELU`` degil? Herhangi bir ``g`` icin ``g(z) - g(-z)`` tektir, ama
    ``GELU(z) = z*Phi(z)`` ve ``SiLU(z) = z*sigma(z)`` icin
    ``g(z) - g(-z) == z`` cikar; yani bu aktivasyonlarla tek bir kol **dogrusal**
    olur. ``tanh`` bu tuzaga dusmez ve TD-Gammon'un sigmoid secimiyle ayni
    ailedendir.

    Kazanc: ilk katman ``221 -> 109`` (yarisi) ve **tam** antisimetri; kayip:
    gizli katmanlarda bias yok (zaten tek cikti icin gerekli).
    """

    def __init__(
        self,
        in_dim: int = VECTOR_SIZE,
        *hidden: int,
        even_width: int | None = None,
    ) -> None:
        super().__init__()
        if not hidden:
            raise ValueError("en az bir gizli katman genisligi gerekli")
        self.in_dim = in_dim
        self.hidden = tuple(int(h) for h in hidden)
        q_minus, q_plus = symmetry_bases()
        if q_minus.shape[0] != in_dim:
            raise ValueError(
                "simetrik govde yalnizca %d'lik vektor icin tanimli (verilen: %d)"
                % (VECTOR_SIZE, in_dim)
            )
        self.register_buffer("q_minus", q_minus)
        self.register_buffer("q_plus", q_plus)
        self.odd_dim = int(q_minus.shape[1])
        self.even_dim = int(q_plus.shape[1])
        # Tek kol **V-** uzerinde calisir. ``T Q- = -Q-`` oldugu icin
        # ``(Tx) @ Q- = -(x @ Q-)``; bias'siz dogrusal katmanlar + tek ``tanh``
        # ile ``f(-u) = -f(u)``, dolayisiyla ``f(Tx) = -f(x)`` **tam** saglanir.
        # Not: tek kolu tam 221 boyutlu girdiye baglamak antisimetriyi
        # **bozar** — tek fonksiyon olmak negasyon altinda teklik demektir,
        # ``T`` ise bir permutasyon/isaret donusumudur (``Tx != -x``).
        self.odd_in = self.odd_dim

        layers: list[nn.Module] = []
        prev = self.odd_in
        for width in self.hidden:
            layers.append(nn.Linear(prev, width, bias=False))
            layers.append(nn.Tanh())
            prev = width
        self.net = nn.Sequential(*layers)

        self.even_width = int(
            even_width if even_width is not None else max(32, self.hidden[-1] // 4)
        )
        self.even_net = nn.Sequential(
            nn.Linear(self.even_dim, self.even_width),
            nn.GELU(),
            nn.Linear(self.even_width, self.even_width),
            nn.GELU(),
        )

    @property
    def out_dim(self) -> int:
        return self.hidden[-1]

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.net(x @ self.q_minus), self.even_net(x @ self.q_plus)


class BackgammonNetV3(nn.Module):
    """``output_version = 2`` + **mimari antisimetri** (F7-116).

    Cikti sozlesmesi :class:`BackgammonNetV2` ile **ayni**: ``probs`` [B, 6]
    (softmax, dislayici) ve ``policy_logit`` [B, 1]. C# tarafi degismez.

    Simetri kurallari (``T = flip_perspective``):

    * ``value(Tx) = -value(x)``: deger basi bias'siz, tek koldan beslenir.
    * ``policy_logit(Tx) = -policy_logit(x)``: ayni sekilde tek ve bias'siz.
    * ``probs(Tx) = Pi probs(x)``, ``Pi = (W L)(GW GL)(BW BL)``: logit'ler
      ``[a+b, a-b]`` olarak kurulur; ``a`` cift koldan (cift), ``b`` tek koldan
      (tek) gelir. Boylece ``equity = 2*b0 + 4*b1 + 6*b2`` **tam** tek olur.

    Sonuc: ``measure_antisymmetry`` korelasyonu **tanim geregi** -1'dir; egitim
    artirimi (``augment_perspectives``) gerekmez.
    """

    output_version = 2

    def __init__(
        self,
        in_dim: int = VECTOR_SIZE,
        *hidden: int,
        rank_head: bool = False,
        even_width: int | None = None,
    ) -> None:
        super().__init__()
        if not hidden:
            hidden = CAPACITY_PROFILES[DEFAULT_PROFILE]
        self.backbone = SymmetricBackbone(in_dim, *hidden, even_width=even_width)
        out = self.backbone.out_dim
        self.value_head = nn.Linear(out, 1, bias=False)
        self.policy_head = nn.Linear(out, 1, bias=False)
        self.probs_odd = nn.Linear(out, 3, bias=False)
        self.probs_even = nn.Linear(self.backbone.even_width, 3)
        self.rank_head: nn.Linear | None = (
            nn.Linear(out, 1, bias=False) if rank_head else None
        )
        # Egitim basinda equity ~ 0: a = (1, 0, 0) -> logit (1,0,0,1,0,0) -> W = L = 0.5.
        nn.init.zeros_(self.probs_even.weight)
        nn.init.zeros_(self.probs_even.bias)
        with torch.no_grad():
            self.probs_even.bias[0] = 1.0

    @property
    def arch(self) -> str:
        b = self.backbone
        return "sym-" + "-".join(str(w) for w in (b.in_dim, *b.hidden))

    def forward(self, x: torch.Tensor):
        h, e = self.backbone(x)
        value = self.value_head(h)
        policy_logit = self.policy_head(h)
        a = self.probs_even(e)
        b = self.probs_odd(h)
        probs = torch.softmax(torch.cat([a + b, a - b], dim=-1), dim=-1)
        if self.rank_head is not None:
            return probs, policy_logit, self.rank_head(h)
        return probs, policy_logit


#: ``probs`` permutasyonu ``Pi``: ``probs(Tx) = Pi probs(x)``. ``PROB_ORDER``
#: ``(W, GW, BW, L, GL, BL)`` icin ``Pi`` ilk ucluyu son ucluye cevirir.
PROB_PERM = (3, 4, 5, 0, 1, 2)


def flip_index() -> tuple[torch.Tensor, torch.Tensor]:
    """``T``'yi indeks/isaret olarak dondurur: ``(Tx)[i] = sign[i] * x[index[i]]``."""
    fmap = _flip_map()
    index = torch.tensor([j for j, _ in fmap], dtype=torch.long)
    sign = torch.tensor([s for _, s in fmap], dtype=torch.float32)
    return index, sign


class HigginsNet(nn.Module):
    """Higgins antisimetrikleştirmesi: duz govde + cikti izdusumu (F7-116).

    Tesauro'nun "Higgins" kurulumu: **tek** ag, iki bakistan da degerlendirilir
    ve sonuclar birlestirilir. Boylece iki ayri ag (beyaz/siyah) yerine tek ag
    kullanilir — Higgins'in parametre tasarrufu budur.

    ``T = flip_perspective`` icin:

    * Tek (odd) ciktilar: ``g(x) = (f(x) - f(Tx)) / 2`` → ``g(Tx) = -g(x)``.
      Deger ve politika logit'i bu yolla uretilir.
    * Cift (even) cikti: ``L(x) = (l(x) + Pi l(Tx)) / 2`` → ``L(Tx) = Pi L(x)``,
      dolayisiyla ``probs(Tx) = Pi probs(x)``.

    Her iki ifade de **tanim geregi** tamdir; egitim artirimi gerekmez. Maliyet
    iki ileri gecistir (kullanici degerlendirmesi: ONNX icin ihmal edilebilir).
    Ifade gucu duz :class:`BackgammonNetV2` ile **ayni**; yalnizca cikti uzayinin
    istenmeyen (cift/tek) bileseni atilir.
    """

    output_version = 2

    def __init__(
        self, in_dim: int = VECTOR_SIZE, *hidden: int, rank_head: bool = False
    ) -> None:
        super().__init__()
        if not hidden:
            hidden = CAPACITY_PROFILES[DEFAULT_PROFILE]
        self.backbone = Backbone(in_dim, *hidden)
        self.probs_head = nn.Linear(self.backbone.out_dim, PROB_COUNT)
        self.policy_head = nn.Linear(self.backbone.out_dim, 1)
        self.rank_head: nn.Linear | None = (
            nn.Linear(self.backbone.out_dim, 1) if rank_head else None
        )
        nn.init.zeros_(self.probs_head.bias)
        with torch.no_grad():
            self.probs_head.bias[0] = 1.0
            self.probs_head.bias[3] = 1.0
        index, sign = flip_index()
        self.register_buffer("flip_index", index)
        self.register_buffer("flip_sign", sign)
        self.register_buffer(
            "prob_perm", torch.tensor(PROB_PERM, dtype=torch.long), persistent=False
        )

    @property
    def arch(self) -> str:
        b = self.backbone
        return "higgins-" + "-".join(str(w) for w in (b.in_dim, *b.hidden))

    def _raw(self, x: torch.Tensor):
        h = self.backbone(x)
        rank = self.rank_head(h) if self.rank_head is not None else None
        return self.probs_head(h), self.policy_head(h), rank

    def forward(self, x: torch.Tensor):
        flipped = x.index_select(1, self.flip_index) * self.flip_sign
        logits_a, policy_a, rank_a = self._raw(x)
        logits_b, policy_b, rank_b = self._raw(flipped)
        logits = 0.5 * (logits_a + logits_b.index_select(1, self.prob_perm))
        policy_logit = 0.5 * (policy_a - policy_b)
        probs = torch.softmax(logits, dim=-1)
        if self.rank_head is not None:
            return probs, policy_logit, 0.5 * (rank_a - rank_b)
        return probs, policy_logit


def build_model(
    in_dim: int = VECTOR_SIZE,
    h1: int = 128,
    h2: int = 64,
    seed: int | None = None,
    output_version: int = 1,
    profile: str | None = None,
    rank_head: bool = False,
    symmetry: bool = False,
    even_width: int | None = None,
    symmetry_mode: str = "basis",
) -> nn.Module:
    """Model kurar.

    ``output_version = 1`` icin ``h1``/``h2`` kullanilir (Faz 4/5 uyumlulugu).
    ``output_version = 2`` icin ``profile`` (bkz. :data:`CAPACITY_PROFILES`) kullanilir;
    ``profile`` verilmezse :data:`DEFAULT_PROFILE`.

    ``rank_head`` yalnizca ``output_version = 2`` icin anlamlidir ve egitim
    sirasinda ikili siralama kaybini besleyen **egitim-disi** bir kafadir.

    ``symmetry=True`` ise renk takasina gore **tam** antisimetrik mimari kurulur
    (Higgins agirlik simetrisi, F7-116). ``symmetry_mode`` hangi kurulumu
    secistir:

    ``"basis"``
        :class:`BackgammonNetV3` — tek ileri gecis, ``V-``/``V+`` izdusumleri.
        Parametre tasarrufu saglar ama tek kol cift ozellikleri kullanamaz.
    ``"higgins"``
        :class:`HigginsNet` — duz V2 govdesi, cikti antisimetrikleştirilir
        (``(f(x) - f(Tx))/2``). Iki ileri gecis; **duz modelle ayni ifade
        gucu** ve tam antisimetri.
    """
    if seed is not None:
        torch.manual_seed(seed)

    if output_version == 1:
        if rank_head:
            raise ValueError("rank_head yalnizca output_version = 2 icin desteklenir")
        if symmetry:
            raise ValueError("symmetry yalnizca output_version = 2 icin desteklenir")
        model: nn.Module = BackgammonNet(in_dim, h1, h2)
    elif output_version == 2:
        name = profile or DEFAULT_PROFILE
        if name not in CAPACITY_PROFILES:
            raise ValueError(
                f"bilinmeyen kapasite profili: {name!r} (gecerli: {sorted(CAPACITY_PROFILES)})"
            )
        if symmetry:
            if symmetry_mode == "higgins":
                model = HigginsNet(
                    in_dim, *CAPACITY_PROFILES[name], rank_head=rank_head
                )
            elif symmetry_mode == "basis":
                model = BackgammonNetV3(
                    in_dim,
                    *CAPACITY_PROFILES[name],
                    rank_head=rank_head,
                    even_width=even_width,
                )
            else:
                raise ValueError(
                    f"bilinmeyen symmetry_mode: {symmetry_mode!r} (gecerli: basis, higgins)"
                )
        else:
            model = BackgammonNetV2(in_dim, *CAPACITY_PROFILES[name], rank_head=rank_head)
    else:
        raise ValueError(f"desteklenmeyen output_version: {output_version}")

    model.eval()
    return model


def parameter_count(model: nn.Module) -> int:
    """Egitilebilir parametre sayisi (Faz 6 Bolum 5.2 tablosu icin)."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)