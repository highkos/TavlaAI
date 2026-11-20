"""Faz 7-R Asama R-C: ogrenme egrisi ("olcek mi pipeline mi?").

Faz 7'nin en pahali sorusu su: ER hedefin uzerindeyse, **daha cok veri** mi
gerekiyor, yoksa **hat** mi bozuk? Bu modul soruyu bir egriyle yanitlar.

Tasarim karari: ayni hat, ayni tohum, yalnizca **veri hacmi** degisir
(N, 2N, 4N, 8N). Her noktada ER uc oynanis yolu icin ayri olculur; ayrica
kalibrasyon egimi/MAE ve **in-sample** ile **held-out** kayip raporlanir.
Karar, ER'nin ``log2(veri)`` basina egiminden verilir.

Neden ``log2``? Cunku ogrenme egrisi literaturde ER ~ a - b*log(N) biciminde
modellenir; ``log2`` katsayisi "veri ikiye katlandiginda ER ne kadar duser"
diye dogrudan okunur. Egim **negatifse** veri artisi ER'yi dusuruyor demektir.

Neden bootstrap? Dort nokta ile egim tahmini cok gurultuludur. Guven araligi
**oyun duzeyinde** yeniden orneklenir: ayni oyunun pozisyonlari guclu
korelidir, pozisyon duzeyinde yeniden ornekleme GA'yi yapay olarak daraltir
(F7-12). Her noktanin kayiplari **oyun kumeleri** halinde yeniden orneklenir,
egim yeniden hesaplanir. Bu, "ayni dagilimdan yeni oyunlar gelseydi egim ne
olurdu" sorusunu yanitlar.

Kullanim (gercek egitim hatti ile)::

    python ml/curve_pool.py build --games 60 --model ml/runs/stage_d_l2/onnx/model_v30.onnx
    python ml/learning_curve.py --pool ml/artifacts/curve_pool.npz \
        --base-positions 200 --multipliers 1 2 4 --seeds 0 1 2 \
        --out ml/artifacts/learning_curve.json --markdown ml/artifacts/learning_curve.md

Kullanim (enjekte edilebilir, testler icin)::

    report = run_curve(sizes=(100, 200, 400, 800), train_fn=...)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

#: Veri hacmi carpanlari (Faz 7-R Asama R-C, madde 4).
#: K4: 64x eklendi. 64x icin **en az 10 560** egitim pozisyonu gerekir
#: (165 taban x 64); havuz kucukse nokta sessizce dusurulmez, raporda
#: ``eksik`` olarak isaretlenir.
CURVE_MULTIPLIERS = (1, 2, 4, 8, 16, 32, 64)

#: Bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261120

#: Olcekleme esigi: ER'nin log2(veri) basina dusus egimi.
#: ``pipeline_health.SCALING_SLOPE_EPSILON`` ile ayni olmali.
SCALING_SLOPE_EPSILON = 0.005

#: Raporlanan oynanis yollari (``er_paths.PLAY_PATHS`` ile ayni).
CURVE_PATHS = ("policy", "value", "search1")

#: Karar etiketleri.
DECISION_SCALES = "olcek"
DECISION_PIPELINE = "pipeline"
DECISION_UNDETERMINED = "belirsiz"
DECISION_NO_DATA = "veri-yok"

#: In-sample kaybin **birimi**. Kural 5: in-sample metrik basari sayilmaz;
#: birimi yazilmadan bir ER gibi okunabilir. Bu yuzden her raporda acikca
#: etiketlenir.
IN_SAMPLE_UNITS = {
    "policy": "capraz-entropi (nat/pozisyon)",
    "value": "MSE (equity^2)",
    "search1": "MSE (equity^2)",
    #: ``train_policy_head`` tek bir **birlesik** kayip dondurur; birimi
    #: iki terimin toplamidir ve ``value_weight`` ile olceklenir.
    "combined": "karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2)",
}

#: Doygunluk fiti ``ER = a * N^-b + c`` icin alt/ust sinirlar.
SATURATION_B_MIN = 0.0
SATURATION_B_MAX = 3.0
SATURATION_MIN_POINTS = 3

#: K4: taban parametresi ``c`` icin kume bootstrap yeniden ornekleme sayisi.
#: 0 = GA hesaplama (eski davranis).
SATURATION_BOOTSTRAP_RESAMPLES = 2000


# ----------------------------------------------------------------------
# Veri yapilari
# ----------------------------------------------------------------------


@dataclass
class CurvePoint:
    """Ogrenme egrisinin tek bir noktasi.

    ``losses`` **pozisyon duzeyinde** ER kayiplaridir; bootstrap bunlari
    yeniden ornekler. ``in_sample_loss`` ve ``held_out_loss`` ayri alanlardir:
    in-sample metrikler basari sayilmaz (Kural 5).
    """

    multiplier: int
    positions: int
    losses: dict[str, list[float]] = field(default_factory=dict)
    game_ids: dict[str, list[str]] = field(default_factory=dict)
    slope: float | None = None
    mae: float | None = None
    in_sample_loss: float | None = None
    held_out_loss: float | None = None
    in_sample_unit: str = ""
    note: str = ""

    @property
    def means(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path, values in self.losses.items():
            if values:
                out[path] = float(np.mean(np.asarray(values, dtype=np.float64)))
        return out

    @property
    def resolved_in_sample_unit(self) -> str:
        """In-sample kaybin birimi; olcum yoksa bos.

        Birim **olcumun** degil kayip fonksiyonunun ozelligidir, bu yuzden
        eski artefaktlarda alan bos olsa bile buradan turetilir.
        """
        if self.in_sample_loss is None:
            return ""
        return self.in_sample_unit or IN_SAMPLE_UNITS["combined"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "multiplier": self.multiplier,
            "positions": self.positions,
            "means": self.means,
            "counts": {p: len(v) for p, v in self.losses.items()},
            "games": {p: len(set(v)) for p, v in self.game_ids.items()},
            "calibrationSlope": self.slope,
            "calibrationMae": self.mae,
            "inSampleLoss": self.in_sample_loss,
            "inSampleUnit": self.resolved_in_sample_unit,
            "heldOutLoss": self.held_out_loss,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CurvePoint":
        """``to_dict`` ciktisindan geri kurar.

        ``losses``/``game_ids`` JSON'da **ozet** olarak durur (``means``,
        ``counts``, ``games``); yeniden kurarken ortalama tek elemanli liste
        olarak tasinir. Boylece ``means`` ve bootstrap kume sayisi korunur.
        """
        means = {str(k): float(v) for k, v in (data.get("means") or {}).items()}
        counts = {str(k): int(v) for k, v in (data.get("counts") or {}).items()}
        games = {str(k): int(v) for k, v in (data.get("games") or {}).items()}
        losses = {path: [value] for path, value in means.items()}
        game_ids = {
            path: ["g%d" % i for i in range(games.get(path, 0))] for path in means
        }
        del counts
        return cls(
            multiplier=int(data.get("multiplier", 0)),
            positions=int(data.get("positions", 0)),
            losses=losses,
            game_ids=game_ids,
            slope=data.get("calibrationSlope"),
            mae=data.get("calibrationMae"),
            in_sample_loss=data.get("inSampleLoss"),
            held_out_loss=data.get("heldOutLoss"),
            in_sample_unit=str(data.get("inSampleUnit") or ""),
            note=str(data.get("note") or ""),
        )


@dataclass
class CurveReport:
    """Ogrenme egrisinin tamami."""

    points: list[CurvePoint] = field(default_factory=list)
    slopes: dict[str, dict[str, float]] = field(default_factory=dict)
    seed: int = 0
    seeds: list[int] = field(default_factory=list)
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    bootstrap_seed: int = BOOTSTRAP_SEED
    clustered: bool = True
    seed_decisions: dict[int, str] = field(default_factory=dict)
    seed_gains: dict[int, float] = field(default_factory=dict)
    saturation: dict[str, dict[str, float]] = field(default_factory=dict)
    #: K4: egrinin hangi korpusta kosuldugu (acikca yazilir; "hangi veri?"
    #: sorusu raporda cevapsiz kalmamali).
    corpus: dict[str, Any] = field(default_factory=dict)
    #: K4: eslestirilmis (paired) oncesi/sonrasi karsilastirmasi.
    paired: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def slope_for(self, path: str) -> float | None:
        entry = self.slopes.get(path)
        return None if entry is None else entry.get("slope")

    @property
    def decision(self) -> str:
        """``olcek`` / ``pipeline`` / ``belirsiz`` / ``veri-yok``.

        Kural 3: nokta tahmini kanit degildir. ``olcek`` demek icin egimin
        **GA alt siniri** esigin uzerinde olmalidir; ``pipeline`` demek icin
        **GA ust siniri** esigin altinda olmalidir. Aksi halde ``belirsiz``.

        **Tohum oybirligi (F7-87).** Havuzlanmis bootstrap tohumlari *ek veri*
        gibi ele alir ve GA'yi yapay olarak daraltir: ayni oyun kumesi farkli
        tohumlarda tekrar sayilir. Bu yuzden havuz karari **tek basina**
        yetmez. Kural: ``olcek``/``pipeline`` demek icin **tum tohumlarin**
        ayni karari vermesi gerekir; aksi halde ``belirsiz``. Tek tohum
        yeterli degildir (kullanicinin adim 0 kosulu).
        """
        if not self.points or not self.slopes:
            return DECISION_NO_DATA
        entry = self.slopes.get("policy") or next(iter(self.slopes.values()))
        low = entry.get("gainCiLow")
        high = entry.get("gainCiHigh")
        if low is None or high is None:
            return DECISION_UNDETERMINED
        if float(low) >= SCALING_SLOPE_EPSILON:
            pooled = DECISION_SCALES
        elif float(high) < SCALING_SLOPE_EPSILON:
            pooled = DECISION_PIPELINE
        else:
            return DECISION_UNDETERMINED

        if len(self.seed_decisions) > 1:
            votes = set(self.seed_decisions.values())
            if votes != {pooled}:
                return DECISION_UNDETERMINED
        return pooled

    @property
    def seed_agreement(self) -> bool:
        """Tum tohumlar ayni karari verdi mi?"""
        if len(self.seed_decisions) <= 1:
            return True
        return len(set(self.seed_decisions.values())) == 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [p.to_dict() for p in self.points],
            "slopes": self.slopes,
            "decision": self.decision,
            "seed": self.seed,
            "seeds": self.seeds,
            "bootstrapResamples": self.bootstrap_resamples,
            "bootstrapSeed": self.bootstrap_seed,
            "clustered": self.clustered,
            "seedDecisions": {str(k): v for k, v in self.seed_decisions.items()},
            "seedGains": {str(k): v for k, v in self.seed_gains.items()},
            "seedAgreement": self.seed_agreement,
            "saturation": self.saturation,
            "corpus": self.corpus,
            "paired": self.paired,
            "scalingSlopeEpsilon": SCALING_SLOPE_EPSILON,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CurveReport":
        """``to_dict`` ciktisindan geri kurar (rapor yeniden uretimi icin)."""
        report = cls(
            points=[CurvePoint.from_dict(p) for p in data.get("points") or []],
            slopes={str(k): dict(v) for k, v in (data.get("slopes") or {}).items()},
            seed=int(data.get("seed", 0)),
            seeds=[int(s) for s in data.get("seeds") or []],
            bootstrap_resamples=int(data.get("bootstrapResamples", BOOTSTRAP_RESAMPLES)),
            bootstrap_seed=int(data.get("bootstrapSeed", BOOTSTRAP_SEED)),
            clustered=bool(data.get("clustered", True)),
            seed_decisions={
                int(k): str(v) for k, v in (data.get("seedDecisions") or {}).items()
            },
            seed_gains={
                int(k): float(v) for k, v in (data.get("seedGains") or {}).items()
            },
            saturation={
                str(k): dict(v) for k, v in (data.get("saturation") or {}).items()
            },
            corpus=dict(data.get("corpus") or {}),
            paired=dict(data.get("paired") or {}),
            notes=[str(n) for n in data.get("notes") or []],
        )
        return report

    def scaling_summary(self) -> dict[str, Any]:
        """``pipeline_health.diagnose(scaling=...)`` icin ozet."""
        entry = self.slopes.get("policy") or (next(iter(self.slopes.values())) if self.slopes else {})
        return {
            # ``slope`` burada **kazanc**tir: ER'nin log2(veri) basina DUSUSU.
            # Pozitif = veri arttikca ER iyilesiyor. Ham OLS egimi ``rawSlope``.
            "slope": entry.get("gain"),
            "ciLow": entry.get("gainCiLow"),
            "ciHigh": entry.get("gainCiHigh"),
            "rawSlope": entry.get("slope"),
            "path": entry.get("path", "policy"),
            "points": [p.positions for p in self.points],
            "decision": self.decision,
        }


# ----------------------------------------------------------------------
# Egim
# ----------------------------------------------------------------------


def _ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Tek degiskenli en kucuk kareler egimi."""
    if x.shape[0] < 2:
        return float("nan")
    xm = float(np.mean(x))
    ym = float(np.mean(y))
    denom = float(np.sum((x - xm) ** 2))
    if denom <= 0.0:
        return float("nan")
    return float(np.sum((x - xm) * (y - ym)) / denom)


def _cluster_means(
    losses: Sequence[float], game_ids: Sequence[str] | None
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Kayiplari **oyun kumelerine** indirger.

    Donen: ``(kume ortalamalari, kume icindeki kayip dizileri)``. ``game_ids``
    yoksa her pozisyon kendi kumesidir (pozisyon duzeyi, geriye uyumlu).
    """
    arr = np.asarray(losses, dtype=np.float64)
    if game_ids is None or len(game_ids) != arr.shape[0]:
        return arr, [np.asarray([v], dtype=np.float64) for v in arr]
    order: dict[str, list[int]] = {}
    for i, gid in enumerate(game_ids):
        order.setdefault(str(gid), []).append(i)
    keys = sorted(order)
    means = np.asarray([float(np.mean(arr[order[k]])) for k in keys], dtype=np.float64)
    groups = [arr[order[k]] for k in keys]
    return means, groups


def fit_log_slope(
    points: Sequence[CurvePoint],
    *,
    path: str = "policy",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    cluster: bool = True,
) -> dict[str, float]:
    """ER'nin ``log2(veri)`` basina egimi + bootstrap %95 GA.

    Nokta tahmini OLS'tir. GA **oyun duzeyinde** yeniden ornekleme ile
    hesaplanir (``cluster=True``): her noktanin kayiplari once oyun kumelerine
    indirgenir, sonra **kumeler** yerine koyarak yeniden orneklenir. Ayni
    oyunun pozisyonlari guclu korelidir; pozisyon duzeyinde yeniden
    ornekleme GA'yi yapay olarak daraltir (F7-12).

    ``cluster=False`` eski (pozisyon duzeyi) davranistir; yalnizca
    ``game_ids`` yoksa anlamlidir.
    """
    usable = [p for p in points if p.losses.get(path)]
    if len(usable) < 2:
        return {
            "path": path,
            "slope": float("nan"),
            "ciLow": float("nan"),
            "ciHigh": float("nan"),
            "gain": float("nan"),
            "gainCiLow": float("nan"),
            "gainCiHigh": float("nan"),
            "n": 0,
            "clusters": 0,
            "resamples": 0,
            "clustered": bool(cluster),
        }
    x = np.log2(np.asarray([p.positions for p in usable], dtype=np.float64))
    y = np.asarray([float(np.mean(p.losses[path])) for p in usable], dtype=np.float64)
    slope = _ols_slope(x, y)

    rng = np.random.default_rng(seed)
    groups: list[list[np.ndarray]] = []
    for p in usable:
        ids = p.game_ids.get(path) if cluster else None
        _means, g = _cluster_means(p.losses[path], ids)
        groups.append(g)
    cluster_counts = [len(g) for g in groups]

    draws = np.empty(resamples, dtype=np.float64)
    for b in range(resamples):
        means = np.empty(len(groups), dtype=np.float64)
        for k, g in enumerate(groups):
            idx = rng.integers(0, len(g), size=len(g))
            means[k] = float(np.mean([float(np.mean(g[int(j)])) for j in idx]))
        draws[b] = _ols_slope(x, means)
    finite = draws[np.isfinite(draws)]
    if finite.size == 0:
        low = high = float("nan")
    else:
        low = float(np.percentile(finite, 2.5))
        high = float(np.percentile(finite, 97.5))
    return {
        "path": path,
        "slope": slope,
        "ciLow": low,
        "ciHigh": high,
        # ``gain = -slope``: ER'nin log2(veri) basina **dususu**. Karar bu
        # isaretle verilir; ham egim negatiftir (ER dusuyor).
        "gain": -slope,
        "gainCiLow": -high,
        "gainCiHigh": -low,
        "n": len(usable),
        "clusters": int(min(cluster_counts)) if cluster_counts else 0,
        "resamples": int(resamples),
        "clustered": bool(cluster),
    }


def _saturation_core(
    n: np.ndarray, y: np.ndarray
) -> tuple[float, float, float, float]:
    """``ER = a*N^-b + c`` icin kaba grid + kapali-form en kucuk kareler.

    Verilen ``b`` icin model ``c``'de dogrusaldir; ``a`` ve ``c`` kapali
    formda cozulur. Kisitlar: ``a >= 0``, ``0 <= c <= min(y)`` (taban
    negatif olamaz ve gozlenen en iyi ER'yi asamaz).

    Doner: ``(a, b, c, rmse)``; basarisizsa hepsi ``nan``.
    """
    floor = float(np.min(y))

    def rmse(a: float, b: float, c: float) -> float:
        pred = a * np.power(n, -b) + c
        return float(np.sqrt(np.mean((pred - y) ** 2)))

    best = (float("nan"), float("nan"), float("nan"), float("inf"))
    for b in np.linspace(SATURATION_B_MIN, SATURATION_B_MAX, 61):
        basis = np.power(n, -b)
        design = np.column_stack([basis, np.ones_like(basis)])
        try:
            coef, *_ = np.linalg.lstsq(design, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        a, c = float(coef[0]), float(coef[1])
        if a < 0.0 or c < 0.0 or c > floor + 1e-12:
            continue
        err = rmse(a, b, c)
        if err < best[3]:
            best = (a, float(b), c, err)
    return best


def _cluster_resample_means(
    point: CurvePoint, path: str, rng: np.random.Generator
) -> float:
    """Bir noktanin kaybini **oyun kumeleri** uzerinden yeniden ornekler."""
    losses = point.losses.get(path) or []
    ids = point.game_ids.get(path) or []
    if not losses:
        return float("nan")
    values = np.asarray(losses, dtype=np.float64)
    if len(ids) != len(values):
        # Kume kimligi yoksa pozisyon duzeyine dus (daha dar GA; raporda yazilir).
        return float(np.mean(rng.choice(values, size=values.size, replace=True)))
    by_cluster: dict[str, list[float]] = {}
    for gid, value in zip(ids, values):
        by_cluster.setdefault(gid, []).append(float(value))
    keys = list(by_cluster)
    picked = rng.integers(0, len(keys), size=len(keys))
    total = 0.0
    count = 0
    for k in picked:
        block = by_cluster[keys[int(k)]]
        total += float(np.sum(block))
        count += len(block)
    return total / count if count else float("nan")


def fit_saturation(
    points: Sequence[CurvePoint],
    *,
    path: str = "policy",
    resamples: int = SATURATION_BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float]:
    """Doygunluk fiti ``ER = a * N^-b + c`` (F7-87, K4).

    Log-egim modeli ``ER = a * N^-b`` **taban parametresi tasimaz**: veri
    sonsuza giderken ER sifira iner, ki bu gercek degildir. Uc parametreli
    model ``c`` tabanini tahmin eder; ``c`` "bu mimari ve bu ogretmenle
    ulasilabilir en iyi ER" sorusunun **olculen** cevabidir.

    Fit: dogrusal olmayan en kucuk kareler (``scipy`` yok; kaba grid + yerel
    iyilestirme). ``b`` icin ``[0, 3]`` araligi; ``c`` icin ``[0, min(ER)]``.

    **K4: ``c`` icin guven araligi.** Nokta tahmini tek basina kanit degildir
    (Kural 3). ``resamples > 0`` ise her nokta **oyun kumeleri** uzerinden
    yeniden orneklenir ve fit tekrarlanir; ``cCiLow``/``cCiHigh`` bu
    dagilimin %2.5/%97.5 yuzdelikleridir. Kume bootstrap'i zorunludur:
    ayni oyunun pozisyonlari guclu korelidir, pozisyon duzeyi GA'yi yapay
    daraltir.

    Doner: ``a``, ``b``, ``c``, ``cCiLow``, ``cCiHigh``, ``rmse``, ``n``,
    ``resamples``. Yetersiz nokta varsa ``nan`` dondurur (sessiz fallback
    yok, Kural 6).
    """
    usable = [p for p in points if p.losses.get(path)]
    empty = {
        "path": path,
        "a": float("nan"),
        "b": float("nan"),
        "c": float("nan"),
        "cCiLow": float("nan"),
        "cCiHigh": float("nan"),
        "rmse": float("nan"),
        "n": len(usable),
        "resamples": 0,
    }
    if len(usable) < SATURATION_MIN_POINTS:
        return empty

    n = np.asarray([float(p.positions) for p in usable], dtype=np.float64)
    y = np.asarray([float(np.mean(p.losses[path])) for p in usable], dtype=np.float64)
    a, b, c, err = _saturation_core(n, y)
    if not np.isfinite(err):
        return empty

    c_low = float("nan")
    c_high = float("nan")
    done = 0
    if resamples > 0:
        rng = np.random.default_rng(int(seed))
        draws: list[float] = []
        for _ in range(int(resamples)):
            ys = np.asarray(
                [_cluster_resample_means(p, path, rng) for p in usable],
                dtype=np.float64,
            )
            if not np.all(np.isfinite(ys)):
                continue
            _, _, cs, es = _saturation_core(n, ys)
            if np.isfinite(es):
                draws.append(float(cs))
        if draws:
            done = len(draws)
            c_low = float(np.percentile(draws, 2.5))
            c_high = float(np.percentile(draws, 97.5))

    return {
        "path": path,
        "a": a,
        "b": b,
        "c": c,
        "cCiLow": c_low,
        "cCiHigh": c_high,
        "rmse": err,
        "n": len(usable),
        "resamples": done,
    }


# ----------------------------------------------------------------------
# Kosum
# ----------------------------------------------------------------------

#: ``train_fn(positions, seed) -> dict`` sozlesmesi:
#:   ``{"losses": {path: [float, ...]}, "slope": float, "mae": float,
#:     "inSampleLoss": float, "heldOutLoss": float, "note": str}``
TrainFn = Callable[[int, int], dict[str, Any]]

#: ``measure_fn(model, positions) -> dict`` alternatifi; ``train_fn`` zaten
#: kayiplari donduruyorsa kullanilmaz.
MeasureFn = Callable[[Any, int], dict[str, list[float]]]


def run_curve(
    *,
    sizes: Sequence[int],
    train_fn: TrainFn,
    seed: int = 0,
    multipliers: Sequence[int] | None = None,
    resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    cluster: bool = True,
    progress: Callable[[str], None] | None = None,
) -> CurveReport:
    """Ayni hat, ayni tohum, degisen **yalnizca** veri hacmi.

    ``sizes`` artan sirali olmalidir; her eleman bir nokta uretir. ``train_fn``
    verilen pozisyon sayisiyla egitir ve **pozisyon duzeyinde** ER kayiplarini
    dondurur. Kural 7: bu fonksiyon disinda hicbir parametre degismemelidir;
    degisiyorsa cagiran taraf bunu ``notes``a yazmalidir.
    """
    ordered = sorted(int(s) for s in sizes)
    if len(ordered) < 2:
        raise ValueError("en az iki nokta gerekli")
    if len(set(ordered)) != len(ordered):
        raise ValueError("veri hacimleri tekrar etmemeli")
    if multipliers is not None:
        mults = [int(m) for m in multipliers]
        if len(mults) != len(ordered):
            raise ValueError("multipliers ile sizes ayni uzunlukta olmali")
    else:
        base = ordered[0]
        mults = [max(1, int(round(p / base))) for p in ordered]

    report = CurveReport(
        seed=int(seed),
        bootstrap_resamples=int(resamples),
        bootstrap_seed=int(bootstrap_seed),
    )
    report.clustered = bool(cluster)
    for k, positions in enumerate(ordered):
        if progress is not None:
            progress("nokta %d/%d: %d pozisyon" % (k + 1, len(ordered), positions))
        raw = train_fn(positions, int(seed))
        losses = {
            path: [float(v) for v in raw.get("losses", {}).get(path, [])]
            for path in CURVE_PATHS
        }
        raw_ids = raw.get("gameIds", {}) or {}
        game_ids = {
            path: [str(v) for v in raw_ids.get(path, [])] for path in CURVE_PATHS
        }
        point = CurvePoint(
            multiplier=int(mults[k]) if k < len(mults) else k + 1,
            positions=int(positions),
            losses=losses,
            game_ids=game_ids,
            slope=None if raw.get("slope") is None else float(raw["slope"]),
            mae=None if raw.get("mae") is None else float(raw["mae"]),
            in_sample_loss=(
                None if raw.get("inSampleLoss") is None else float(raw["inSampleLoss"])
            ),
            in_sample_unit=(
                ""
                if raw.get("inSampleLoss") is None
                else str(raw.get("inSampleUnit") or IN_SAMPLE_UNITS["combined"])
            ),
            held_out_loss=(
                None if raw.get("heldOutLoss") is None else float(raw["heldOutLoss"])
            ),
            note=str(raw.get("note", "")),
        )
        report.points.append(point)

    for path in CURVE_PATHS:
        if any(p.losses.get(path) for p in report.points):
            report.slopes[path] = fit_log_slope(
                report.points,
                path=path,
                resamples=resamples,
                seed=bootstrap_seed,
                cluster=cluster,
            )
    if not report.slopes:
        report.notes.append("hicbir noktada kayip yok: egim hesaplanamadi")
    return report


def run_curve_multi_seed(
    *,
    sizes: Sequence[int],
    train_fn: TrainFn,
    seeds: Sequence[int],
    multipliers: Sequence[int] | None = None,
    resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    cluster: bool = True,
    saturation_resamples: int = SATURATION_BOOTSTRAP_RESAMPLES,
    progress: Callable[[str], None] | None = None,
) -> CurveReport:
    """Ayni egriyi **birden cok tohumla** kosar ve havuzlar.

    Neden. Tek tohumla olculen egim, agirlik baslatmasinin ve mini-batch
    sirasinin gurultusunu tasir. En az **uc** tohum istenir (kullanicinin
    adim 0 kosulu). Havuzlama: her noktada tohumlarin kayiplari **birlestirilir**
    ve oyun kimlikleri tohumla **oneklenir** (ayni oyun kimligi farkli
    tohumlarda ayni kume sayilmasin). Egim, havuzlanmis veri uzerinde
    oyun duzeyinde kume bootstrap'i ile hesaplanir.

    Kural 7: tohumlar arasinda degisen tek sey tohumdur; veri hacimleri,
    epoch sayisi, mimari ve ogrenme orani aynidir.
    """
    seed_list = [int(s) for s in seeds]
    if len(seed_list) < 1:
        raise ValueError("en az bir tohum gerekli")
    if len(set(seed_list)) != len(seed_list):
        raise ValueError("tohumlar tekrar etmemeli")

    per_seed: list[CurveReport] = []
    for seed in seed_list:
        if progress is not None:
            progress("tohum %d" % seed)
        per_seed.append(
            run_curve(
                sizes=sizes,
                train_fn=train_fn,
                seed=seed,
                multipliers=multipliers,
                resamples=resamples,
                bootstrap_seed=bootstrap_seed,
                cluster=cluster,
                progress=progress,
            )
        )

    pooled = CurveReport(
        seed=seed_list[0],
        seeds=seed_list,
        bootstrap_resamples=int(resamples),
        bootstrap_seed=int(bootstrap_seed),
        clustered=bool(cluster),
    )
    base = per_seed[0]
    for k, point in enumerate(base.points):
        losses: dict[str, list[float]] = {path: [] for path in CURVE_PATHS}
        game_ids: dict[str, list[str]] = {path: [] for path in CURVE_PATHS}
        in_sample: list[float] = []
        held_out: list[float] = []
        for seed, report in zip(seed_list, per_seed):
            other = report.points[k]
            for path in CURVE_PATHS:
                losses[path].extend(other.losses.get(path, []))
                ids = other.game_ids.get(path, [])
                if ids:
                    game_ids[path].extend("s%d:%s" % (seed, g) for g in ids)
            if other.in_sample_loss is not None:
                in_sample.append(float(other.in_sample_loss))
            if other.held_out_loss is not None:
                held_out.append(float(other.held_out_loss))
        pooled.points.append(
            CurvePoint(
                multiplier=point.multiplier,
                positions=point.positions,
                losses=losses,
                game_ids=game_ids,
                slope=None,
                mae=None,
                in_sample_loss=float(np.mean(in_sample)) if in_sample else None,
                held_out_loss=float(np.mean(held_out)) if held_out else None,
                note="%d tohum havuzu" % len(seed_list),
            )
        )

    for path in CURVE_PATHS:
        if any(p.losses.get(path) for p in pooled.points):
            pooled.slopes[path] = fit_log_slope(
                pooled.points,
                path=path,
                resamples=resamples,
                seed=bootstrap_seed,
                cluster=cluster,
            )
    if not pooled.slopes:
        pooled.notes.append("hicbir noktada kayip yok: egim hesaplanamadi")

    # Tohum bazli kararlar: havuz karari tek basina yetmez (F7-87).
    for seed, report in zip(seed_list, per_seed):
        entry = report.slopes.get("policy") or {}
        pooled.seed_decisions[int(seed)] = report.decision
        gain = entry.get("gain")
        if gain is not None and np.isfinite(float(gain)):
            pooled.seed_gains[int(seed)] = float(gain)
        pooled.notes.append(
            "tohum %d: kazanc %s GA [%s; %s] -> %s"
            % (
                seed,
                _fmt(entry.get("gain")),
                _fmt(entry.get("gainCiLow")),
                _fmt(entry.get("gainCiHigh")),
                report.decision,
            )
        )

    # Doygunluk fiti: taban parametresi ``c`` (F7-87) + ``c`` GA (K4).
    for path in CURVE_PATHS:
        if any(p.losses.get(path) for p in pooled.points):
            pooled.saturation[path] = fit_saturation(
                pooled.points,
                path=path,
                resamples=int(saturation_resamples),
                seed=bootstrap_seed,
            )

    if len(seed_list) > 1 and not pooled.seed_agreement:
        pooled.notes.append(
            "TOHUM OYBIRLIGI YOK: %s -> havuz karari 'belirsiz' sayilir"
            % ", ".join(
                "s%d=%s" % (s, d) for s, d in sorted(pooled.seed_decisions.items())
            )
        )
    pooled.notes.append(
        "Havuzlanmis %d tohum: %s" % (len(seed_list), ", ".join(str(s) for s in seed_list))
    )
    return pooled


# ----------------------------------------------------------------------
# Eslestirilmis (paired) karsilastirma - K4
# ----------------------------------------------------------------------


def _strip_seed_prefix(game_id: str) -> str:
    """``s3:cp-012`` -> ``cp-012`` (tohum onekini at)."""
    head, sep, tail = game_id.partition(":")
    if sep and head.startswith("s") and head[1:].isdigit():
        return tail
    return game_id


def _game_means(point: CurvePoint, path: str) -> dict[str, float]:
    """Bir noktanin kaybini **oyun** duzeyinde ortalar (tohum oneki atilir)."""
    losses = point.losses.get(path) or []
    ids = point.game_ids.get(path) or []
    if not losses or len(ids) != len(losses):
        return {}
    buckets: dict[str, list[float]] = {}
    for gid, value in zip(ids, losses):
        buckets.setdefault(_strip_seed_prefix(str(gid)), []).append(float(value))
    return {k: float(np.mean(v)) for k, v in buckets.items()}


def paired_curve_comparison(
    before: CurveReport,
    after: CurveReport,
    *,
    path: str = "policy",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Ayni havuzda kosulmus iki egrinin **eslestirilmis** karsilastirmasi (K4).

    Neden eslestirilmis. Iki egri (ornegin antisimetri artirimi oncesi/sonrasi)
    **ayni held-out oyunlarini** degerlendirir. Bagimsiz iki ortalama
    karsilastirmak oyun gurultusunu iki kez sayar; fark **oyun basina**
    alinirsa ayni oyunun zorlugu sadelesir ve GA daralir.

    Yontem: her noktada oyun basina ortalama kayip alinir, ``fark = sonra -
    once`` hesaplanir, **oyun** kumeleri uzerinden bootstrap edilir. Negatif
    fark = sonra daha iyi (ER dustu).

    Doner: ``path``, ``points`` (nokta basina fark), ``meanDiff``,
    ``ciLow``, ``ciHigh``, ``clusters``, ``resamples``, ``improved``.
    """
    by_pos_before = {int(p.positions): p for p in before.points}
    by_pos_after = {int(p.positions): p for p in after.points}
    shared = sorted(set(by_pos_before) & set(by_pos_after))
    if not shared:
        return {
            "path": path,
            "points": [],
            "meanDiff": float("nan"),
            "ciLow": float("nan"),
            "ciHigh": float("nan"),
            "clusters": 0,
            "resamples": 0,
            "improved": None,
            "note": "ortak nokta yok",
        }

    point_rows: list[dict[str, Any]] = []
    #: Tum noktalarin oyun duzeyi farklari (havuzlanmis).
    pooled_diffs: list[float] = []
    for positions in shared:
        mb = _game_means(by_pos_before[positions], path)
        ma = _game_means(by_pos_after[positions], path)
        common = sorted(set(mb) & set(ma))
        diffs = [ma[g] - mb[g] for g in common]
        pooled_diffs.extend(diffs)
        point_rows.append(
            {
                "positions": int(positions),
                "multiplier": int(by_pos_after[positions].multiplier),
                "before": float(np.mean(list(mb.values()))) if mb else float("nan"),
                "after": float(np.mean(list(ma.values()))) if ma else float("nan"),
                "diff": float(np.mean(diffs)) if diffs else float("nan"),
                "clusters": len(common),
            }
        )

    if not pooled_diffs:
        return {
            "path": path,
            "points": point_rows,
            "meanDiff": float("nan"),
            "ciLow": float("nan"),
            "ciHigh": float("nan"),
            "clusters": 0,
            "resamples": 0,
            "improved": None,
            "note": "ortak oyun kimligi yok",
        }

    values = np.asarray(pooled_diffs, dtype=np.float64)
    mean_diff = float(np.mean(values))
    rng = np.random.default_rng(int(seed))
    draws = np.empty(int(resamples), dtype=np.float64)
    for i in range(int(resamples)):
        picked = rng.integers(0, values.size, size=values.size)
        draws[i] = float(np.mean(values[picked]))
    low = float(np.percentile(draws, 2.5))
    high = float(np.percentile(draws, 97.5))
    return {
        "path": path,
        "points": point_rows,
        "meanDiff": mean_diff,
        "ciLow": low,
        "ciHigh": high,
        "clusters": int(values.size),
        "resamples": int(resamples),
        #: GA tamamen sifirin altinda mi? (sonra anlamli olarak daha iyi)
        "improved": bool(high < 0.0),
        "note": "negatif fark = sonra daha iyi (ER dustu)",
    }


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and not math.isfinite(value):
        return "-"
    return ("%." + str(digits) + "f") % value


DECISION_TEXT = {
    DECISION_SCALES: (
        "Egim esigin uzerinde: veri ikiye katlandiginda ER olculebilir bicimde "
        "dusuyor. **Olcek buyutmek dogru kaldiractir.**"
    ),
    DECISION_PIPELINE: (
        "Egim esigin altinda: veri ikiye katlandiginda ER olculebilir bicimde "
        "dusmuyor. **Olcek buyutmek dogru kaldirac degildir**; once pipeline "
        "onarilmalidir."
    ),
    DECISION_UNDETERMINED: (
        "Egim guven araligi esigi kesiyor: **karar verilemez**. Daha fazla "
        "nokta ya da daha buyuk korpus gerekir."
    ),
    DECISION_NO_DATA: "Ogrenme egrisi olculmedi.",
}


def build_markdown(report: CurveReport, *, title: str = "Faz 7-R - Ogrenme egrisi") -> str:
    """Insan-okur Markdown rapor."""
    lines: list[str] = ["# " + title, ""]
    lines.append("Soru: **ER hedefin uzerindeyse, daha cok veri mi yoksa onarilmis")
    lines.append("bir hat mi gerekiyor?** Ayni hat, ayni tohum, yalnizca veri hacmi")
    lines.append("degisir. Karar, ER'nin `log2(veri)` basina egiminden verilir.")
    lines.append("")
    lines.append("## 1. Noktalar")
    lines.append("")
    header = "| Carpan | Pozisyon |"
    sep = "|---|---|"
    for path in CURVE_PATHS:
        header += " ER `%s` |" % path
        sep += "---|"
    header += " Kal. egimi | Kal. MAE | In-sample | In-sample birimi | Held-out |"
    sep += "---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for p in report.points:
        means = p.means
        row = "| %dx | %d |" % (p.multiplier, p.positions)
        for path in CURVE_PATHS:
            row += " %s |" % _fmt(means.get(path))
        row += " %s | %s | %s | %s | %s |" % (
            _fmt(p.slope),
            _fmt(p.mae),
            _fmt(p.in_sample_loss),
            p.resolved_in_sample_unit or "-",
            _fmt(p.held_out_loss),
        )
        lines.append(row)
    lines.append("")
    lines.append("> **In-sample metrikler basari sayilmaz** (Kural 5). Held-out")
    lines.append("> kolonu tek basina okunmalidir. In-sample kolonu bir ER")
    lines.append("> **degildir**: birimi yanindaki sutunda yazilidir.")
    lines.append("")
    if report.corpus:
        lines.append("### 1.1 Korpus")
        lines.append("")
        lines.append("| Alan | Deger |")
        lines.append("|---|---|")
        for key in sorted(report.corpus):
            lines.append("| `%s` | %s |" % (key, report.corpus[key]))
        lines.append("")
        lines.append(
            "Korpus **acikca** yazilir: egri hangi veri uzerinde kosuldugu "
            "bilinmeden okunamaz (K4)."
        )
        lines.append("")
    lines.append("## 2. Egim (ER / log2 veri)")
    lines.append("")
    lines.append(
        "| Yol | Kazanc | %95 GA | Ham egim | Nokta | Kume | Yeniden ornekleme |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for path in CURVE_PATHS:
        entry = report.slopes.get(path)
        if entry is None:
            continue
        lines.append(
            "| `%s` | %s | [%s; %s] | %s | %d | %d | %d |"
            % (
                path,
                _fmt(entry.get("gain")),
                _fmt(entry.get("gainCiLow")),
                _fmt(entry.get("gainCiHigh")),
                _fmt(entry.get("slope")),
                int(entry.get("n", 0)),
                int(entry.get("clusters", 0)),
                int(entry.get("resamples", 0)),
            )
        )
    lines.append("")
    lines.append(
        "Kume bootstrap'i: **%s** (oyun duzeyinde = dogru; pozisyon duzeyinde "
        "GA'yi yapay daraltir)."
        % ("oyun" if report.clustered else "pozisyon")
    )
    lines.append("")
    if report.seeds:
        lines.append("Tohumlar: **%s** (havuzlanmis)." % ", ".join(str(s) for s in report.seeds))
        lines.append("")
    lines.append(
        "**Kazanc** = ER'nin `log2(veri)` basina **dususu** (pozitif = veri "
        "arttkca ER iyilesiyor). Ham egim ayni buyuklugun isaretli hali."
    )
    lines.append("")
    lines.append("Esik: **%s** (ER kazanci / log2 veri)." % _fmt(SCALING_SLOPE_EPSILON))
    lines.append("")
    if report.seed_decisions:
        lines.append("## 3. Tohum bazli kararlar")
        lines.append("")
        lines.append("| Tohum | Kazanc | Karar |")
        lines.append("|---|---|---|")
        for seed in sorted(report.seed_decisions):
            lines.append(
                "| %d | %s | `%s` |"
                % (seed, _fmt(report.seed_gains.get(seed)), report.seed_decisions[seed])
            )
        lines.append("")
        lines.append(
            "**Tohum oybirligi: %s.** Havuzlanmis bootstrap tohumlari ek veri "
            "gibi ele alir ve GA'yi daraltir; bu yuzden havuz karari tek basina "
            "yetmez. `olcek`/`pipeline` icin **tum tohumlarin** ayni karari "
            "vermesi gerekir."
            % ("VAR" if report.seed_agreement else "YOK")
        )
        lines.append("")
    if report.saturation:
        lines.append("## 4. Doygunluk fiti `ER = a*N^-b + c`")
        lines.append("")
        lines.append("| Yol | a | b | c (taban) | c %95 GA | RMSE | Nokta | Yeniden ornekleme |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for path in CURVE_PATHS:
            entry = report.saturation.get(path)
            if entry is None:
                continue
            lines.append(
                "| `%s` | %s | %s | **%s** | [%s; %s] | %s | %d | %d |"
                % (
                    path,
                    _fmt(entry.get("a")),
                    _fmt(entry.get("b")),
                    _fmt(entry.get("c")),
                    _fmt(entry.get("cCiLow")),
                    _fmt(entry.get("cCiHigh")),
                    _fmt(entry.get("rmse")),
                    int(entry.get("n", 0)),
                    int(entry.get("resamples", 0)),
                )
            )
        lines.append("")
        lines.append(
            "`c` **taban parametresidir**: veri sonsuza giderken ER'nin indigi "
            "deger. Log-egim modeli taban tasimaz (ER sifira iner), ki bu "
            "gercek degildir. `c` icin GA **oyun kumeleri** uzerinden bootstrap "
            "ile hesaplanir; nokta tahmini tek basina kanit sayilmaz (Kural 3)."
        )
        lines.append("")
    if report.paired:
        paired = report.paired
        lines.append("## 4.1 Eslestirilmis (paired) karsilastirma")
        lines.append("")
        lines.append(
            "Ayni held-out oyunlari uzerinde **once/sonra** farki. Fark oyun "
            "basina alinir; ayni oyunun zorlugu sadelesir ve GA daralir."
        )
        lines.append("")
        rows = paired.get("points") or []
        if rows:
            lines.append("| Carpan | Pozisyon | Once | Sonra | Fark | Kume |")
            lines.append("|---|---|---|---|---|---|")
            for row in rows:
                lines.append(
                    "| %dx | %d | %s | %s | %s | %d |"
                    % (
                        int(row.get("multiplier", 0)),
                        int(row.get("positions", 0)),
                        _fmt(row.get("before")),
                        _fmt(row.get("after")),
                        _fmt(row.get("diff")),
                        int(row.get("clusters", 0)),
                    )
                )
            lines.append("")
        lines.append(
            "Havuzlanmis fark: **%s** %95 GA [%s; %s], kume %d, yeniden "
            "ornekleme %d. **Sonra anlamli olarak daha iyi: %s**"
            % (
                _fmt(paired.get("meanDiff")),
                _fmt(paired.get("ciLow")),
                _fmt(paired.get("ciHigh")),
                int(paired.get("clusters", 0)),
                int(paired.get("resamples", 0)),
                "EVET" if paired.get("improved") else "HAYIR",
            )
        )
        lines.append("")
        lines.append("Negatif fark = sonra daha iyi (ER dustu).")
        lines.append("")
    lines.append("## 5. Karar")
    lines.append("")
    lines.append("**`%s`**" % report.decision)
    lines.append("")
    lines.append(DECISION_TEXT.get(report.decision, ""))
    lines.append("")
    if report.notes:
        lines.append("## 6. Notlar")
        lines.append("")
        for note in report.notes:
            lines.append("- " + note)
        lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="learning_curve",
        description="Ogrenme egrisi: olcek mi pipeline mi?",
    )
    p.add_argument(
        "--base-positions",
        type=int,
        default=2000,
        help="1x noktasinin pozisyon sayisi (varsayilan 2000)",
    )
    p.add_argument(
        "--multipliers",
        type=int,
        nargs="+",
        default=list(CURVE_MULTIPLIERS),
        help="veri hacmi carpanlari",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="birden cok tohum (en az 3 onerilir); verilirse --seed yok sayilir",
    )
    p.add_argument(
        "--pool",
        type=Path,
        default=None,
        help="etiketli havuz (ml/curve_pool.py build); verilmezse hata",
    )
    p.add_argument("--epochs", type=int, default=20, help="sabit epoch sayisi")
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--profile", default="medium")
    p.add_argument("--device", default="cpu")
    p.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    p.add_argument(
        "--no-cluster",
        action="store_true",
        help="pozisyon duzeyi bootstrap (eski davranis; onerilmez)",
    )
    p.add_argument("--out", type=Path, default=None, help="cikti JSON")
    p.add_argument("--markdown", type=Path, default=None, help="cikti Markdown")
    p.add_argument(
        "--corpus",
        action="append",
        default=None,
        metavar="ANAHTAR=DEGER",
        help="korpus kumesi (tekrarlanabilir); raporda acikca yazilir (K4)",
    )
    p.add_argument(
        "--compare-before",
        type=Path,
        default=None,
        help="onceki rapor JSON'u; eslestirilmis (paired) karsilastirma ekler (K4)",
    )
    p.add_argument(
        "--saturation-resamples",
        type=int,
        default=SATURATION_BOOTSTRAP_RESAMPLES,
        help="taban parametresi c icin kume bootstrap sayisi (0 = kapali)",
    )
    p.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="olcum yapmadan, var olan rapor JSON'undan Markdown'i yeniden uret",
    )
    p.add_argument("--quiet", action="store_true")
    return p


def _parse_corpus(items: Sequence[str] | None) -> dict[str, Any]:
    """``ANAHTAR=DEGER`` listesini sozluge cevirir."""
    out: dict[str, Any] = {}
    for item in items or []:
        key, sep, value = str(item).partition("=")
        if not sep or not key:
            raise SystemExit("learning_curve: --corpus ANAHTAR=DEGER biciminde olmali: %s" % item)
        out[key.strip()] = value.strip()
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.from_json is not None:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        report = CurveReport.from_dict(data)
        if args.compare_before is not None:
            before = CurveReport.from_dict(
                json.loads(Path(args.compare_before).read_text(encoding="utf-8"))
            )
            report.paired = paired_curve_comparison(
                before, report, resamples=int(args.resamples)
            )
        if args.markdown is not None:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(build_markdown(report), encoding="utf-8")
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
        if not args.quiet:
            print("karar: %s" % report.decision)
        return 0

    sizes = [int(args.base_positions) * int(m) for m in args.multipliers]

    if args.pool is None:
        raise SystemExit(
            "learning_curve: --pool zorunlu. Once havuzu kurun: "
            "python ml/curve_pool.py build --games 60 "
            "--model ml/runs/stage_d_l2/onnx/model_v30.onnx"
        )

    import curve_pool  # noqa: PLC0415

    pool = curve_pool.load_pool(Path(args.pool))
    train_fn = curve_pool.make_train_fn(
        pool,
        epochs=int(args.epochs),
        batch=int(args.batch),
        lr=float(args.lr),
        device=str(args.device),
        profile=str(args.profile),
        progress=None if args.quiet else (lambda m: print(m)),
    )

    seeds = [int(s) for s in args.seeds] if args.seeds else [int(args.seed)]
    if len(seeds) >= 2:
        report = run_curve_multi_seed(
            sizes=sizes,
            train_fn=train_fn,
            seeds=seeds,
            multipliers=args.multipliers,
            resamples=args.resamples,
            cluster=not args.no_cluster,
            saturation_resamples=int(args.saturation_resamples),
            progress=None if args.quiet else (lambda m: print(m)),
        )
    else:
        report = run_curve(
            sizes=sizes,
            train_fn=train_fn,
            seed=seeds[0],
            multipliers=args.multipliers,
            resamples=args.resamples,
            cluster=not args.no_cluster,
            progress=None if args.quiet else (lambda m: print(m)),
        )
        report.seeds = seeds
    report.corpus = _parse_corpus(args.corpus)
    if args.compare_before is not None:
        before = CurveReport.from_dict(
            json.loads(Path(args.compare_before).read_text(encoding="utf-8"))
        )
        report.paired = paired_curve_comparison(
            before, report, resamples=int(args.resamples)
        )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")
    if not args.quiet:
        print("karar: %s" % report.decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
