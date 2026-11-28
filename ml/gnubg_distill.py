"""Faz 7: gnubg'yi **ogretmen** olarak kullanma (dis inceleme madde 1.3).

Neden bu deney? Inceleme, en buyuk kaldracin kendi aramamizin bilgisini
damitmak degil, **gnubg 2-ply etiketlerini** ogretmen olarak kullanmak
oldugunu one surdu. Mantik basit ve karar verici:

* Etiketlerle ER **0,03'un altina** iniyorsa **ogretmen etkilidir**: gnubg
  etiketleri kendi aramamizin urettigi hedeflerden daha fazla bilgi tasiyor.
* Inmiyorsa ogretmen etkili degildir.

**Bu deney kapasite/pipeline ayrimini KURMAZ** (Faz 7-R adim 0). Eski metin
"inmiyorsa sorun kapasitedir" diyordu; bu bir nedensel iddiaydi ve olcumle
desteklenmiyordu. Ayrim ancak `ml/learning_curve.py` egrisiyle kurulur.

Yontem:

1. ``refgen.random_positions`` ile rastgele yasal oyunlardan pozisyon uret.
2. Her pozisyonu gnubg ``hint`` ile 2-ply etiketle: hedef, **en iyi hamlenin
   mover bakis acisindan** equity'sidir (``hints[0].equity``).
3. Girdi vektoru ``gnubg_er.vectorize(..., perspective=turn)`` — yani
   ``er_harness``in kullandigi vektorun **aynisi** (Test 53 paritesi).
4. Deger kafasini MSE ile egit: ``probs @ EQUITY_WEIGHTS ~ y`` (F7-17 kurali).
5. ER'yi ``er_harness`` ile olc ve ``distill_verdict`` ile karar ver.

Lisans notu: gnubg **GPL**'dir. Etiketler yalnizca **arastirma/olcum** icin
kullanilir; urun dagitimi icin lisans netlestirilmelidir (bkz. ``LICENSE_NOTE``).

Kullanim::

    python ml/gnubg_distill.py label --out ml/runs/gnubg_distill/dataset.npz \
        --positions 1000 --plies 2 --seed 7
    python ml/gnubg_distill.py train --data ml/runs/gnubg_distill/dataset.npz \
        --ckpt ml/runs/stage_d_l2/checkpoints/ckpt_v30.pt \
        --out ml/runs/gnubg_distill/ckpt_gnubg.pt --steps 2000
    python ml/gnubg_distill.py verdict --before 0.0740 --after 0.0310
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _p in (str(HERE), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Ogretmen derinligi. gnubg ``hint`` 0..7 destekler; 2-ply hem hizli hem de
#: ``er_harness``in yetkili hakem derinligidir (F7-04).
DEFAULT_PLIES = 2
#: Etiketlenecek pozisyon sayisi (varsayilan).
DEFAULT_POSITIONS = 1000
#: Rastgele oyunlarda en fazla kac yarim hamle ilerlenir.
DEFAULT_MAX_PLIES = 40
#: Egitim adimi / ogrenme orani / yigin boyu.
DEFAULT_STEPS = 2000
DEFAULT_LR = 1e-3
DEFAULT_BATCH = 256
#: Politika egitiminde deger teriminin agirligi (politika ana hedeftir).
DEFAULT_VALUE_WEIGHT = 0.5
#: Incelemenin karar esigi: ER bu degerin altina inerse **ogretmen etkilidir**.
TARGET_ER = 0.03
#: "Isaretli iyilesme" icin gereken en kucuk goreli kazanc. Faz 7-R'den sonra
#: yalnizca **raporlama** amaciyla kullanilir; karar etiketini degistirmez
#: (karar eslesmis GA'ya baglidir, Kural 3).
MIN_GAIN = 0.20

#: Eslesmis fark icin bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
PAIRED_BOOTSTRAP_RESAMPLES = 20000
PAIRED_BOOTSTRAP_SEED = 20261121

#: Karar etiketleri.
#: Etiketler **nedensel iddia tasimaz** (Faz 7-R adim 0). Eski ``pipeline``
#: etiketi "dar bogaz pipeline" diyordu; olcumun gosterdigi tek sey
#: **ogretmen etiketlerinin ise yaradigidir**. Kapasite/pipeline ayrimi
#: ``ml/learning_curve.py`` egrisiyle kurulur, bu fonksiyonla degil.
VERDICT_TEACHER_EFFECTIVE = "ogretmen-etkili"
VERDICT_PARTIAL = "kismi"
#: **Kaldirildi** (Faz 7-R R-07). Etiketlerin ise yaramamasi kapasiteyi
#: kanitlamaz; bu yuzden ``distill_verdict`` bu etiketi **asla dondurmez**.
#: Sabit, eski artifact'lari okuyabilmek icin duruyor.
VERDICT_CAPACITY = "kapasite"
VERDICT_UNPROVEN = "belirsiz"
VERDICT_UNKNOWN = "bilinmiyor"
#: Yeni (Faz 7-R R-07): n < gereken n. Karar **verilemez**, "kazanc yok" da
#: denemez.
VERDICT_INSUFFICIENT_DATA = "veri-yetersiz"

LICENSE_NOTE = (
    "gnubg GPL lisanslidir. Bu modulun urettigi etiketler yalnizca arastirma "
    "ve olcum icindir; urun dagitimi oncesinde lisans netlestirilmelidir."
)


# ----------------------------------------------------------------------
# Veri yapilari
# ----------------------------------------------------------------------


@dataclass
class LabeledPosition:
    """Tek bir pozisyonun ogretmen etiketi."""

    vector: list[float]
    equity: float
    turn: int
    dice: tuple[int, ...]
    best_move: str
    candidates: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "turn": self.turn,
            "dice": list(self.dice),
            "bestMove": self.best_move,
            "candidates": self.candidates,
        }


@dataclass
class Dataset:
    """Etiketli veri kumesi (``x``: [N, 221], ``y``: [N])."""

    x: np.ndarray
    y: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def stats(self) -> dict[str, Any]:
        if len(self) == 0:
            return {"count": 0}
        y = np.asarray(self.y, dtype=np.float64)
        return {
            "count": int(y.shape[0]),
            "mean": float(np.mean(y)),
            "std": float(np.std(y)),
            "min": float(np.min(y)),
            "max": float(np.max(y)),
            "zeroShare": float(np.mean(np.abs(y) < 1e-9)),
        }


# ----------------------------------------------------------------------
# Etiketleme
# ----------------------------------------------------------------------


def generate_positions(
    count: int, *, seed: int = 7, max_plies: int = DEFAULT_MAX_PLIES
) -> list[tuple[list[int], int, list[int], int, int]]:
    """Rastgele yasal oyunlardan ``(board, turn, dice, whiteOff, blackOff)``."""
    import tools.reference_gen as refgen  # noqa: PLC0415

    if count <= 0:
        return []
    rng = random.Random(seed)
    return refgen.random_positions(rng, count, max_plies=max_plies)


def label_positions(
    referee,
    positions: Iterable[tuple[list[int], int, list[int], int, int]],
    *,
    progress: Callable[[int, int, LabeledPosition | None], None] | None = None,
) -> tuple[list[LabeledPosition], list[dict[str, Any]]]:
    """Pozisyonlari gnubg ``hint`` ile etiketler.

    Etiketlenemeyen pozisyon **sessizce atlanmaz**: ``skipped`` listesine
    nedeniyle yazilir ve cagiran taraf orani raporlar.
    """
    import gnubg_er  # noqa: PLC0415

    out: list[LabeledPosition] = []
    skipped: list[dict[str, Any]] = []
    items = list(positions)
    total = len(items)
    for i, (board, turn, dice, wo, bo) in enumerate(items, start=1):
        try:
            hints, _text = referee.hint(board, turn, dice)
        except Exception as exc:  # gnubg hatasi / ayristirma hatasi
            skipped.append({"index": i, "reason": type(exc).__name__ + ": " + str(exc)})
            if progress:
                progress(i, total, None)
            continue
        if not hints:
            skipped.append({"index": i, "reason": "hint listesi bos (yasal hamle yok)"})
            if progress:
                progress(i, total, None)
            continue
        best = hints[0]
        item = LabeledPosition(
            vector=gnubg_er.vectorize(board, wo, bo, perspective=int(turn)),
            equity=float(best.equity),
            turn=int(turn),
            dice=tuple(int(d) for d in dice),
            best_move=str(best.move),
            candidates=len(hints),
        )
        out.append(item)
        if progress:
            progress(i, total, item)
    return out, skipped


def build_dataset(
    labeled: Sequence[LabeledPosition], *, meta: dict[str, Any] | None = None
) -> Dataset:
    """``LabeledPosition`` listesinden ``Dataset``."""
    if not labeled:
        return Dataset(
            x=np.zeros((0, 221), dtype=np.float32),
            y=np.zeros((0,), dtype=np.float32),
            meta=dict(meta or {}),
        )
    x = np.asarray([p.vector for p in labeled], dtype=np.float32)
    y = np.asarray([p.equity for p in labeled], dtype=np.float32)
    return Dataset(x=x, y=y, meta=dict(meta or {}))


def save_dataset(dataset: Dataset, path: Path) -> None:
    """``.npz`` olarak yazar (``x``, ``y``, ``meta`` JSON)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        p,
        x=dataset.x,
        y=dataset.y,
        meta=np.asarray(json.dumps(dataset.meta, sort_keys=True)),
    )


def load_dataset(path: Path) -> Dataset:
    """``.npz`` okur."""
    with np.load(Path(path), allow_pickle=False) as data:
        meta: dict[str, Any] = {}
        if "meta" in data:
            raw = data["meta"]
            text = str(raw.item()) if raw.shape == () else str(raw)
            meta = json.loads(text) if text else {}
        return Dataset(
            x=np.asarray(data["x"], dtype=np.float32),
            y=np.asarray(data["y"], dtype=np.float32),
            meta=meta,
        )


# ----------------------------------------------------------------------
# Egitim
# ----------------------------------------------------------------------


def equity_of_probs(probs) -> Any:
    """6 sinifli olasilik -> skaler equity (``EQUITY_WEIGHTS`` ile)."""
    import torch  # noqa: PLC0415
    from equity import EQUITY_WEIGHTS  # noqa: PLC0415

    w = torch.as_tensor(EQUITY_WEIGHTS, dtype=probs.dtype, device=probs.device)
    return probs @ w


def train_value_head(
    model,
    dataset: Dataset,
    *,
    steps: int = DEFAULT_STEPS,
    lr: float = DEFAULT_LR,
    batch: int = DEFAULT_BATCH,
    device: str = "cpu",
    seed: int = 0,
    progress: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Deger kafasini gnubg equity'sine MSE ile egitir.

    Yalnizca **deger** (``probs``) kafasi egitilir; politika kafasi dokunulmaz.
    Bu bilinclidir: deney "etiketler deger kafasini onarir mi?" sorusunu sorar,
    "politika da ogrenir mi?" sorusunu degil.
    """
    import torch  # noqa: PLC0415

    if len(dataset) == 0:
        raise ValueError("bos veri kumesi egitilemez")
    if steps <= 0:
        raise ValueError("steps > 0 olmali")

    torch.manual_seed(seed)
    x = torch.from_numpy(np.asarray(dataset.x, dtype=np.float32)).to(device)
    y = torch.from_numpy(np.asarray(dataset.y, dtype=np.float32)).to(device)
    n = int(x.shape[0])
    batch = max(1, min(int(batch), n))

    model.to(device)
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.Adam(params, lr=lr)
    loss_fn = torch.nn.MSELoss()

    history: list[float] = []
    for step in range(1, steps + 1):
        idx = torch.randint(0, n, (batch,), device=device)
        out = model(x[idx])
        probs = out[0] if isinstance(out, tuple) else out
        pred = equity_of_probs(probs)
        loss = loss_fn(pred, y[idx])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        value = float(loss.detach().to("cpu"))
        history.append(value)
        if progress:
            progress(step, steps, value)

    model.eval()
    with torch.no_grad():
        out = model(x)
        probs = out[0] if isinstance(out, tuple) else out
        pred = equity_of_probs(probs)
        final = float(loss_fn(pred, y).detach().to("cpu"))
        mae = float(torch.mean(torch.abs(pred - y)).detach().to("cpu"))
        corr = _pearson(pred.detach().to("cpu").numpy(), np.asarray(dataset.y, dtype=np.float64))
        slope = _slope(pred.detach().to("cpu").numpy(), np.asarray(dataset.y, dtype=np.float64))

    return {
        "steps": int(steps),
        "batch": int(batch),
        "lr": float(lr),
        "count": n,
        "firstLoss": history[0] if history else None,
        "lastLoss": history[-1] if history else None,
        "finalMse": final,
        "finalMae": mae,
        "correlation": corr,
        "slope": slope,
        "history": history,
    }


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    if a.shape[0] < 2:
        return float("nan")
    sa, sb = float(np.std(a)), float(np.std(b))
    if sa <= 0.0 or sb <= 0.0:
        return float("nan")
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def _slope(pred: np.ndarray, target: np.ndarray) -> float:
    """``target = a + b * pred`` regresyonundaki ``b`` (kalibrasyon egimi)."""
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    t = np.asarray(target, dtype=np.float64).reshape(-1)
    if p.shape[0] < 2:
        return float("nan")
    var = float(np.var(p))
    if var <= 0.0:
        return float("nan")
    return float(np.mean((p - p.mean()) * (t - t.mean())) / var)


# ----------------------------------------------------------------------
# Politika damitma (F7-21)
#
# ER **politika** basi argmax'i ile olculur (`er_harness` -> `score_afterstates`
# -> `criterion="policy"`). Bu yuzden yalnizca deger kafasini egitmek ER'i
# tanimi geregi degistiremez. Asagidaki hat, gnubg'nin en iyi hamlesini
# **politika** hedefi olarak kullanir; ER'e dogrudan dokunan tek yol budur.
# ----------------------------------------------------------------------


@dataclass
class PolicyPosition:
    """Tek pozisyonun ogretmen etiketli **aday kumesi**."""

    vectors: list[list[float]]
    best_index: int
    best_equity: float
    turn: int
    dice: tuple[int, ...]
    best_move: str
    candidates: int
    mapping_failures: int = 0
    #: K5: en iyi adayin gnubg 6 sinifli dagilimi (``equity.PROB_ORDER``).
    best_dist: list[float] | None = None
    #: R-04/R-17: **her** adayin gnubg equity'si; etiketlenemeyen aday ``None``.
    #: ``hint`` en fazla 10 hamle bastigi icin uzun aday kumelerinde bazi
    #: satirlar etiketsiz kalir ve egitimde **maskelenir** (negatif sayilmaz).
    candidate_equities: list[float | None] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bestIndex": self.best_index,
            "bestEquity": self.best_equity,
            "turn": self.turn,
            "dice": list(self.dice),
            "bestMove": self.best_move,
            "candidates": self.candidates,
            "mappingFailures": self.mapping_failures,
            "bestDist": list(self.best_dist) if self.best_dist else None,
            "labeledCandidates": (
                None
                if self.candidate_equities is None
                else sum(1 for v in self.candidate_equities if v is not None)
            ),
        }


@dataclass
class PolicyDataset:
    """Ragged aday kumesi: ``x`` [M, 221], ``offsets`` [N+1], ``best`` [N].

    ``dist`` [N, 6] opsiyoneldir; doluysa ``train_policy_head`` 6 sinifli KL
    terimini de ekler (K5: skaler equity tek basina deger yolunu 4x'ten sonra
    platoya sokuyordu).
    """

    x: np.ndarray
    offsets: np.ndarray
    best: np.ndarray
    y: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)
    dist: np.ndarray | None = None
    #: R-04: ``[M]`` aday basina gnubg equity'si; etiketsiz aday ``nan``.
    cand_equity: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.best.shape[0])

    def candidates(self, i: int) -> np.ndarray:
        return self.x[int(self.offsets[i]) : int(self.offsets[i + 1])]

    def has_dist(self) -> bool:
        """6 sinifli dagilim sutunu **kullanilabilir** mi (en az bir gecerli satir).

        Etiketi alinamayan pozisyonlar ``nan`` satiriyla temsil edilir; sutun
        bu yuzden tek bir eksik yuzunden tumden dusurulmez (F7-126).
        """
        if self.dist is None:
            return False
        arr = np.asarray(self.dist)
        if arr.ndim != 2 or int(arr.shape[0]) != len(self):
            return False
        return bool(np.isfinite(arr).all(axis=1).any())

    def dist_valid_mask(self) -> np.ndarray | None:
        """``[N]`` bool: dagilim hedefi gecerli olan pozisyonlar."""
        if not self.has_dist():
            return None
        return np.isfinite(np.asarray(self.dist, dtype=np.float32)).all(axis=1)

    def has_cand_equity(self) -> bool:
        """Aday basina equity sutunu dolu mu (liste bazli kayip icin gerekli)."""
        return (
            self.cand_equity is not None
            and int(np.asarray(self.cand_equity).shape[0]) == int(self.x.shape[0])
        )

    def masked_candidate_rate(self) -> float | None:
        """Etiketsiz aday orani (R-17: maskelenen oran raporlanir)."""
        if not self.has_cand_equity():
            return None
        values = np.asarray(self.cand_equity, dtype=np.float64)
        if values.size == 0:
            return None
        return float(np.mean(np.isnan(values)))

    def subset(self, indices: Sequence[int]) -> "PolicyDataset":
        """Verilen pozisyon indekslerinden yeni bir kume kurar (egitim/dogrulama)."""
        idx = np.asarray(list(indices), dtype=np.int64)
        if idx.size and (int(idx.min()) < 0 or int(idx.max()) >= len(self)):
            raise IndexError("alt kume indeksi aralik disi")
        counts = np.diff(np.asarray(self.offsets, dtype=np.int64))
        starts = np.asarray(self.offsets[:-1], dtype=np.int64)[idx]
        take = np.concatenate([np.arange(s, s + int(counts[i])) for s, i in zip(starts, idx)])
        offsets = np.zeros(idx.size + 1, dtype=np.int64)
        np.cumsum(counts[idx], out=offsets[1:])
        return PolicyDataset(
            x=np.asarray(self.x[take], dtype=np.float32),
            offsets=offsets,
            best=np.asarray(self.best[idx], dtype=np.int32),
            y=np.asarray(self.y[idx], dtype=np.float32),
            meta=dict(self.meta),
            dist=(
                np.asarray(self.dist[idx], dtype=np.float32)
                if self.has_dist()
                else None
            ),
            cand_equity=(
                np.asarray(self.cand_equity[take], dtype=np.float32)
                if self.has_cand_equity()
                else None
            ),
        )

    def stats(self) -> dict[str, Any]:
        if len(self) == 0:
            return {"count": 0}
        counts = np.diff(np.asarray(self.offsets, dtype=np.int64))
        y = np.asarray(self.y, dtype=np.float64)
        return {
            "count": int(len(self)),
            "candidates": int(self.x.shape[0]),
            "candidatesMean": float(np.mean(counts)),
            "candidatesMin": int(np.min(counts)),
            "candidatesMax": int(np.max(counts)),
            "mean": float(np.mean(y)),
            "std": float(np.std(y)),
            "min": float(np.min(y)),
            "max": float(np.max(y)),
            "hasDist": bool(self.has_dist()),
            "distMissing": (
                int((~self.dist_valid_mask()).sum())
                if self.has_dist()
                else int(len(self))
            ),
            "hasCandEquity": bool(self.has_cand_equity()),
            "maskedCandidateRate": self.masked_candidate_rate(),
        }


def afterstate_case(
    board: Sequence[int],
    turn: int,
    dice: Sequence[int],
    white_off: int,
    black_off: int,
) -> dict[str, Any] | None:
    """Yasal afterstate'leri **deterministik** sirada ``case`` sozlugune cevirir.

    ``tools.reference_gen.legal_after_states`` bir **kume** dondurur; siralama
    kosular arasi degisecegi icin burada siralanir. Aksi halde ``best_index``
    etiketleri kosudan kosuya kayar ve egitim sessizce bozulur.
    """
    import tools.reference_gen as refgen  # noqa: PLC0415

    _max_steps, keys = refgen.legal_after_states(board, turn, dice, white_off, black_off)
    if not keys:
        return None
    ordered = sorted(keys)
    return {
        "board": list(board),
        "turn": int(turn),
        "dice": [int(d) for d in dice],
        "whiteOff": int(white_off),
        "blackOff": int(black_off),
        "afterStates": [
            {"board": list(b), "whiteOff": int(w), "blackOff": int(o)}
            for (b, w, o) in ordered
        ],
    }


def label_policy_positions(
    referee,
    positions: Iterable[tuple[list[int], int, list[int], int, int]],
    *,
    dists: bool = False,
    plies: int = DEFAULT_PLIES,
    progress: Callable[[int, int, PolicyPosition | None], None] | None = None,
) -> tuple[list[PolicyPosition], list[dict[str, Any]]]:
    """Pozisyonlari gnubg ``hint`` ile **politika** hedefi olarak etiketler.

    Etiketlenemeyen pozisyon sessizce atlanmaz; ``skipped`` listesine nedeniyle
    yazilir ve cagiran taraf orani raporlar.

    ``dists=True`` ise en iyi adayin 6 sinifli gnubg dagilimi da (``best_dist``)
    etiketlenir; bu, ``train_policy_head``'in KL terimi icin gereklidir (K5).
    """
    import gnubg_er  # noqa: PLC0415
    import gnubg_hint  # noqa: PLC0415

    out: list[PolicyPosition] = []
    skipped: list[dict[str, Any]] = []
    items = list(positions)
    total = len(items)
    for i, (board, turn, dice, wo, bo) in enumerate(items, start=1):
        case = afterstate_case(board, turn, dice, wo, bo)
        if case is None:
            skipped.append({"index": i, "reason": "yasal afterstate yok"})
            if progress:
                progress(i, total, None)
            continue
        try:
            hints, _text = referee.hint(board, turn, dice)
        except Exception as exc:  # gnubg hatasi / ayristirma hatasi
            skipped.append({"index": i, "reason": type(exc).__name__ + ": " + str(exc)})
            if progress:
                progress(i, total, None)
            continue
        if not hints:
            skipped.append({"index": i, "reason": "hint listesi bos (yasal hamle yok)"})
            if progress:
                progress(i, total, None)
            continue
        matched, failures = gnubg_hint.map_hints(hints, case)
        if not matched:
            skipped.append(
                {"index": i, "reason": "hint hamleleri afterstate kumesine eslesmedi"}
            )
            if progress:
                progress(i, total, None)
            continue
        best_hint, best_index = max(matched, key=lambda pair: pair[0].equity)
        # R-04/R-17: her adayin equity'si; ``hint`` gormedigi aday ``None``.
        candidate_equities: list[float | None] = [None] * len(case["afterStates"])
        for hint, index in matched:
            candidate_equities[int(index)] = float(hint.equity)
        vectors = [
            gnubg_er.vectorize(
                a["board"], a["whiteOff"], a["blackOff"], perspective=int(turn)
            )
            for a in case["afterStates"]
        ]
        best_dist: list[float] | None = None
        if dists:
            best_after = case["afterStates"][int(best_index)]
            # ``HintReferee`` oturumu ``.session`` altinda tutar; dogrudan
            # ``GnubgSession`` verilmis olabilecegi icin ikisi de kabul edilir.
            session = getattr(referee, "session", referee)
            try:
                tables = session.eval_afterstates(
                    [best_after["board"]], int(turn), dists=True
                )
            except Exception as exc:  # gnubg hatasi: dagilim olmadan devam et
                skipped.append(
                    {"index": i, "reason": "dagilim etiketi alinamadi: " + str(exc)}
                )
                tables = []
            if tables:
                key = "static" if plies == 0 else str(plies)
                best_dist = tables[0].get(key)
        item = PolicyPosition(
            vectors=vectors,
            best_index=int(best_index),
            best_equity=float(best_hint.equity),
            turn=int(turn),
            dice=tuple(int(d) for d in dice),
            best_move=str(best_hint.move),
            candidates=len(vectors),
            mapping_failures=len(failures),
            best_dist=best_dist,
            candidate_equities=candidate_equities,
        )
        out.append(item)
        if progress:
            progress(i, total, item)
    return out, skipped


def build_policy_dataset(
    labeled: Sequence[PolicyPosition], *, meta: dict[str, Any] | None = None
) -> PolicyDataset:
    """``PolicyPosition`` listesinden ``PolicyDataset``."""
    if not labeled:
        return PolicyDataset(
            x=np.zeros((0, 221), dtype=np.float32),
            offsets=np.zeros((1,), dtype=np.int64),
            best=np.zeros((0,), dtype=np.int32),
            y=np.zeros((0,), dtype=np.float32),
            meta=dict(meta or {}),
        )
    offsets: list[int] = [0]
    rows: list[list[float]] = []
    best: list[int] = []
    y: list[float] = []
    dist: list[list[float]] = []
    cand_equity: list[float] = []
    have_cand_equity = True
    for p in labeled:
        rows.extend(p.vectors)
        offsets.append(len(rows))
        best.append(int(p.best_index))
        y.append(float(p.best_equity))
        # Eksik dagilim satiri ``nan`` ile yazilir ve egitimde maskelenir.
        # Eskiden tek bir eksik satir **tum** sutunu dusuruyordu (F7-126).
        if p.best_dist is None:
            dist.append([float("nan")] * 6)
        else:
            dist.append([float(v) for v in p.best_dist])
        if p.candidate_equities is None or len(p.candidate_equities) != len(p.vectors):
            have_cand_equity = False
        else:
            cand_equity.extend(
                float("nan") if v is None else float(v) for v in p.candidate_equities
            )
    dist_arr = np.asarray(dist, dtype=np.float32) if dist else None
    if dist_arr is not None and not np.isfinite(dist_arr).all(axis=1).any():
        dist_arr = None  # hicbir satir gecerli degil: sutunu hic yazma
    return PolicyDataset(
        x=np.asarray(rows, dtype=np.float32),
        offsets=np.asarray(offsets, dtype=np.int64),
        best=np.asarray(best, dtype=np.int32),
        y=np.asarray(y, dtype=np.float32),
        meta=dict(meta or {}),
        dist=dist_arr,
        cand_equity=(
            np.asarray(cand_equity, dtype=np.float32)
            if have_cand_equity and cand_equity
            else None
        ),
    )


def save_policy_dataset(dataset: PolicyDataset, path: Path) -> None:
    """``.npz`` olarak yazar (``x``, ``offsets``, ``best``, ``y``, ``meta``, ``dist``)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "x": dataset.x,
        "offsets": dataset.offsets,
        "best": dataset.best,
        "y": dataset.y,
        "meta": np.asarray(json.dumps(dataset.meta, sort_keys=True)),
    }
    if dataset.has_dist():
        payload["dist"] = np.asarray(dataset.dist, dtype=np.float32)
    if dataset.has_cand_equity():
        payload["cand_equity"] = np.asarray(dataset.cand_equity, dtype=np.float32)
    np.savez_compressed(p, **payload)


def load_policy_dataset(path: Path) -> PolicyDataset:
    """``.npz`` okur."""
    with np.load(Path(path), allow_pickle=False) as data:
        meta: dict[str, Any] = {}
        if "meta" in data:
            raw = data["meta"]
            text = str(raw.item()) if raw.shape == () else str(raw)
            meta = json.loads(text) if text else {}
        dist = np.asarray(data["dist"], dtype=np.float32) if "dist" in data else None
        cand_equity = (
            np.asarray(data["cand_equity"], dtype=np.float32)
            if "cand_equity" in data
            else None
        )
        return PolicyDataset(
            x=np.asarray(data["x"], dtype=np.float32),
            offsets=np.asarray(data["offsets"], dtype=np.int64),
            best=np.asarray(data["best"], dtype=np.int32),
            y=np.asarray(data["y"], dtype=np.float32),
            meta=meta,
            dist=dist,
            cand_equity=cand_equity,
        )


def concat_policy_datasets(
    parts: Sequence[PolicyDataset], *, meta: dict[str, Any] | None = None
) -> PolicyDataset:
    """Paralel etiketlenmis dilimleri tek kumede birlestirir.

    Dilimler ayni ``dists`` ayarini kullanmalidir. Bir dilimde dagilim sutunu
    **hic** yoksa (eski bir kosudan geliyorsa) o dilimin satirlari ``nan`` ile
    doldurulur ve egitimde maskelenir; sutun tumden dusurulmez (F7-126).
    """
    parts = [p for p in parts if len(p) > 0]
    if not parts:
        raise ValueError("birlestirilecek bos olmayan dilim yok")
    has_dist = any(p.has_dist() for p in parts)
    has_cand_equity = all(p.has_cand_equity() for p in parts)
    offsets = np.zeros(1, dtype=np.int64)
    xs: list[np.ndarray] = []
    for p in parts:
        xs.append(np.asarray(p.x, dtype=np.float32))
        counts = np.diff(np.asarray(p.offsets, dtype=np.int64))
        offsets = np.concatenate([offsets, offsets[-1] + np.cumsum(counts)])
    merged_meta = dict(meta or {})
    merged_meta.setdefault("shards", len(parts))
    merged_meta.setdefault("shardLabeled", [int(len(p)) for p in parts])
    dist_parts: list[np.ndarray] = []
    if has_dist:
        for p in parts:
            if p.has_dist():
                dist_parts.append(np.asarray(p.dist, dtype=np.float32))
            else:
                dist_parts.append(np.full((len(p), 6), np.nan, dtype=np.float32))
    return PolicyDataset(
        x=np.concatenate(xs, axis=0),
        offsets=offsets,
        best=np.concatenate([np.asarray(p.best, dtype=np.int32) for p in parts]),
        y=np.concatenate([np.asarray(p.y, dtype=np.float32) for p in parts]),
        meta=merged_meta,
        dist=np.concatenate(dist_parts, axis=0) if has_dist else None,
        cand_equity=(
            np.concatenate([np.asarray(p.cand_equity, dtype=np.float32) for p in parts])
            if has_cand_equity
            else None
        ),
    )


def _pad_policy(dataset: PolicyDataset) -> tuple[np.ndarray, np.ndarray, int]:
    """Ragged kumeyi ``[N, L, 221]`` + maske olarak doldurur."""
    n = len(dataset)
    counts = np.diff(np.asarray(dataset.offsets, dtype=np.int64))
    width = int(np.max(counts)) if n else 0
    x = np.zeros((n, width, 221), dtype=np.float32)
    mask = np.zeros((n, width), dtype=bool)
    for i in range(n):
        c = dataset.candidates(i)
        k = int(c.shape[0])
        x[i, :k] = c
        mask[i, :k] = True
    return x, mask, width


def train_policy_head(
    model,
    dataset: PolicyDataset,
    *,
    steps: int = DEFAULT_STEPS,
    lr: float = DEFAULT_LR,
    batch: int = DEFAULT_BATCH,
    device: str = "cpu",
    seed: int = 0,
    value_weight: float = DEFAULT_VALUE_WEIGHT,
    dist_weight: float = 0.0,
    rank_weight: float = 0.0,
    val_fraction: float = 0.0,
    patience: int = 0,
    eval_every: int = 500,
    weight_decay: float = 0.0,
    lr_schedule: str = "none",
    lr_final_ratio: float = 0.1,
    policy_temperature: float = 0.0,
    progress: Callable[[int, int, float], None] | None = None,
    checkpoint: Path | None = None,
    checkpoint_every: int = 0,
    resume: bool = False,
) -> dict[str, Any]:
    """Politika kafasini gnubg'nin en iyi hamlesine capraz-entropi ile egitir.

    Kayip: ``CE(logits, best) + value_weight * MSE(equity(best), best_equity)
    + dist_weight * KL(gnubg_dagilimi || model_dagilimi)
    + rank_weight * ikili_siralama``.
    Politika terimi ER'i dogrudan hedefler; deger terimi yalnizca destek olur.

    ``dist_weight > 0`` icin veri kumesinde 6 sinifli dagilim bulunmalidir (K5).
    Skaler equity tek basina deger yolunu 4x'ten sonra platoya sokuyordu; tam
    dagilim hedefi ayni ileri gecislerden cok daha fazla sinyal cikarir.

    ``rank_weight > 0`` ikili (pairwise) siralama terimini ekler: en iyi adayin
    siralama skoru her diger adaydan buyuk olmali (lojistik kayip). Bu terim
    ``model.rank_head`` gerektirir ve **yalnizca egitimde** kullanilir.

    ``val_fraction > 0`` ise pozisyonlarin o orani deterministik olarak ayrilir;
    ``patience > 0`` iken dogrulama kaybi ``patience`` degerlendirme boyunca
    iyilesmezse egitim durur ve **en iyi** agirliklar geri yuklenir.

    ``weight_decay > 0`` Adam'a L2 cezasi ekler. ``lr_schedule = "cosine"``
    ogrenme oranini ``lr``'den ``lr * lr_final_ratio``'ya kosinus ile dusurur.
    Buyuk kapasitelerde (>=512 gizli birim) sabit ``lr=1e-3`` ile dogrulama
    kaybi 1500 adimdan sonra **iraksiyordu** (asiri ogrenme); bu iki dugme
    olmadan 30 bin pozisyonluk karsilastirma yanilti olur.

    ``policy_temperature > 0`` ise sert top-1 CE yerine **liste bazli** kayip
    kullanilir (R-04): ``KL(softmax(equity_gnubg / T) || softmax(logits))``.
    ``hint`` en fazla 10 hamle bastigi icin etiketsiz adaylar **maskelenir**
    (R-17: negatif sayilmaz). Bu kip ``dataset.cand_equity`` gerektirir.
    """
    import torch  # noqa: PLC0415
    import torch.nn.functional as F  # noqa: PLC0415

    if len(dataset) == 0:
        raise ValueError("bos veri kumesi egitilemez")
    if steps <= 0:
        raise ValueError("steps > 0 olmali")
    if dist_weight > 0 and not dataset.has_dist():
        raise ValueError(
            "dist_weight > 0 icin veri kumesinde 6 sinifli dagilim (dist) gerekli"
        )
    if rank_weight > 0 and getattr(model, "rank_head", None) is None:
        raise ValueError("rank_weight > 0 icin modelde rank_head gerekli")
    if not 0.0 <= val_fraction < 1.0:
        raise ValueError("val_fraction [0, 1) araliginda olmali")
    if lr_schedule not in ("none", "cosine"):
        raise ValueError("lr_schedule 'none' veya 'cosine' olmali")
    if not 0.0 < lr_final_ratio <= 1.0:
        raise ValueError("lr_final_ratio (0, 1] araliginda olmali")
    if policy_temperature < 0:
        raise ValueError("policy_temperature >= 0 olmali")
    if policy_temperature > 0 and not dataset.has_cand_equity():
        raise ValueError(
            "policy_temperature > 0 icin veri kumesinde aday basina equity "
            "(cand_equity) gerekli; ``label-policy`` ile yeniden etiketleyin"
        )

    torch.manual_seed(seed)
    n = len(dataset)
    # F7-127: duzensiz kumeyi **global genislige yastiklamak** 100k'da
    # ``(100030, 581, 221)`` = ~51 GB sanal dizi aciyor ve makine takasa
    # giriyordu. Parti artik dogrudan duzensiz diziden kurulur.
    counts = np.diff(np.asarray(dataset.offsets, dtype=np.int64))
    width = int(np.max(counts)) if n else 0
    if width <= 0:
        raise ValueError("aday kumesi bos")
    flat = np.asarray(dataset.x, dtype=np.float32)
    starts = np.asarray(dataset.offsets[:-1], dtype=np.int64)

    # Deterministik ayirma: ayni seed her zaman ayni dogrulama kumesini verir.
    n_val = int(round(n * val_fraction)) if val_fraction > 0 else 0
    if n_val >= n:
        raise ValueError("val_fraction tum veri kumesini ayiriyor")
    perm = np.random.default_rng(seed).permutation(n)
    val_idx = np.sort(perm[:n_val]) if n_val else np.zeros(0, dtype=np.int64)
    train_idx = np.sort(perm[n_val:]) if n_val else np.arange(n)
    n_train = int(train_idx.size)

    bt = torch.from_numpy(np.asarray(dataset.best, dtype=np.int64))
    yt = torch.from_numpy(np.asarray(dataset.y, dtype=np.float32))
    dt = (
        torch.from_numpy(np.asarray(dataset.dist, dtype=np.float32))
        if dist_weight > 0
        else None
    )
    # F7-126: dagilim etiketi alinamayan pozisyonlar KL teriminden cikarilir.
    dvalid = (
        torch.from_numpy(np.asarray(dataset.dist_valid_mask(), dtype=bool))
        if dt is not None
        else None
    )
    # R-04: aday basina equity; etiketsiz aday ``nan`` (maskelenecek).
    # ``cand_equity`` 1-B'dir; maske ile ayni genislige yastiklanir.
    ceq = None
    if policy_temperature > 0:
        padded = np.full((n, width), np.nan, dtype=np.float32)
        raw_equity = np.asarray(dataset.cand_equity, dtype=np.float32)
        for i in range(n):
            start = int(dataset.offsets[i])
            stop = int(dataset.offsets[i + 1])
            padded[i, : stop - start] = raw_equity[start:stop]
        ceq = torch.from_numpy(padded)
    tr_idx_t = torch.from_numpy(np.asarray(train_idx, dtype=np.int64))
    va_idx_t = (
        torch.from_numpy(np.asarray(val_idx, dtype=np.int64)) if n_val else None
    )

    def _batch_tensors(indices: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, int]:
        """Partiyi **kendi** aday genisligine kirpar.

        Veri kumesi duzensizdir (ortalama ~22 aday, en genis pozisyon 400'u
        asabilir). Global genislige yastiklamak her adimi 10 kata kadar
        sisiriyordu; maske zaten dolgu satirlarini -1e9 ile etkisizlestirdigi
        icin partiyi kendi genisligine kirpmak sonucu degistirmez.

        F7-127: parti, duzensiz ``flat``/``starts``/``counts`` uzerinden
        kurulur; global yastiklanmis dizi hic olusturulmaz.
        """
        idx_np = indices.detach().cpu().numpy()
        c = counts[idx_np]
        w = max(1, min(int(c.max()) if c.size else 0, width))
        xb = np.zeros((idx_np.size, w, 221), dtype=np.float32)
        mb = np.zeros((idx_np.size, w), dtype=bool)
        for r, i in enumerate(idx_np):
            s = int(starts[i])
            k = int(counts[i])
            xb[r, :k] = flat[s : s + k]
            mb[r, :k] = True
        return torch.from_numpy(xb).reshape(-1, 221), torch.from_numpy(mb), w

    def _policy_loss(
        logits: torch.Tensor, mb: torch.Tensor, eq: torch.Tensor | None, bb: torch.Tensor
    ) -> torch.Tensor:
        """Sert CE ya da liste bazli KL (R-04); etiketsiz adaylar maskeli."""
        if eq is None:
            return F.cross_entropy(logits, bb)
        labelled = mb & ~torch.isnan(eq)
        target_logits = torch.where(
            labelled, eq / policy_temperature, torch.full_like(eq, -1e9)
        )
        log_target = F.log_softmax(target_logits, dim=1)
        target = log_target.exp()
        log_pred = F.log_softmax(logits, dim=1)
        per_position = (target * (log_target - log_pred)).sum(dim=1)
        valid = labelled.any(dim=1)
        return (per_position * valid).sum() / valid.sum().clamp_min(1)

    def _evaluate(indices: torch.Tensor) -> dict[str, float]:
        """Verilen indekslerde kayip bilesenleri ve top-1 dogruluk."""
        model.eval()
        total = int(indices.numel())
        ce_sum = 0.0
        v_sum = 0.0
        correct = 0
        with torch.no_grad():
            for start in range(0, total, 64):
                sel = indices[start : start + 64]
                k = int(sel.numel())
                xb, mb, wb = _batch_tensors(sel)
                out = model(xb.to(device))
                probs = out[0].reshape(k, wb, -1)
                logits = out[1].reshape(k, wb).masked_fill(~mb.to(device), -1e9)
                eq = ceq[sel][:, :wb].to(device) if ceq is not None else None
                ce_sum += float(
                    _policy_loss(logits, mb.to(device), eq, bt[sel].to(device)).to("cpu")
                ) * k
                pick = bt[sel].to(device).view(-1, 1, 1).expand(-1, 1, probs.shape[-1])
                best_probs = probs.gather(1, pick).squeeze(1)
                v_sum += float(
                    F.mse_loss(equity_of_probs(best_probs), yt[sel].to(device)).to("cpu")
                ) * k
                correct += int(
                    (torch.argmax(logits, dim=1) == bt[sel].to(device)).sum().to("cpu")
                )
        model.train()
        return {
            "ce": ce_sum / total if total else float("nan"),
            "valueMse": v_sum / total if total else float("nan"),
            "top1": (correct / total) if total else float("nan"),
        }

    model.to(device)
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.Adam(params, lr=lr, weight_decay=weight_decay)
    sched = None
    if lr_schedule == "cosine":
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            opt, T_max=max(1, steps), eta_min=lr * lr_final_ratio
        )
    batch = max(1, min(int(batch), n_train))

    history: list[float] = []
    val_history: list[dict[str, Any]] = []
    best_state: dict[str, Any] | None = None
    best_val = float("inf")
    best_step = 0
    stale = 0
    stopped_early = False

    # F7-118: adim duzeyinde denetim noktasi. EVREN gibi ucretli platformlarda
    # bir kesinti tum kosuyu yakmamali. Kayit: adim, agirliklar, optimizer,
    # scheduler, gecmis, en iyi durum ve torch RNG durumu.
    start_step = 1
    resumed_from = 0
    if checkpoint is not None and resume and Path(checkpoint).exists():
        saved = torch.load(str(checkpoint), map_location="cpu", weights_only=False)
        model.load_state_dict(saved["model"])
        opt.load_state_dict(saved["opt"])
        if sched is not None and saved.get("sched") is not None:
            sched.load_state_dict(saved["sched"])
        history = list(saved.get("history") or [])
        val_history = list(saved.get("valHistory") or [])
        best_state = saved.get("bestState")
        best_val = float(saved.get("bestVal", float("inf")))
        best_step = int(saved.get("bestStep", 0))
        stale = int(saved.get("stale", 0))
        stopped_early = bool(saved.get("stoppedEarly", False))
        if saved.get("torchRng") is not None:
            torch.set_rng_state(saved["torchRng"])
        resumed_from = int(saved.get("step", 0))
        start_step = resumed_from + 1
        model.to(device)
        model.train()

    def _save_checkpoint(step: int) -> None:
        if checkpoint is None:
            return
        target = Path(checkpoint)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "step": int(step),
            "steps": int(steps),
            "model": model.state_dict(),
            "opt": opt.state_dict(),
            "sched": sched.state_dict() if sched is not None else None,
            "history": history,
            "valHistory": val_history,
            "bestState": best_state,
            "bestVal": best_val,
            "bestStep": best_step,
            "stale": stale,
            "stoppedEarly": stopped_early,
            "torchRng": torch.get_rng_state(),
        }
        tmp = target.with_suffix(target.suffix + ".tmp")
        torch.save(payload, str(tmp))
        os.replace(str(tmp), str(target))

    for step in range(start_step, steps + 1):
        idx = tr_idx_t[torch.randint(0, n_train, (batch,))]
        # Buyuk veri kumelerinde ``[N, L, 221]`` tensori GPU'ya sigmaz; partiler
        # CPU'da indekslenip cihaza tasinir (PCIe maliyeti adim basina ~24 MB).
        xb, mb, wb = _batch_tensors(idx)
        xb = xb.to(device)
        mb = mb.to(device)
        bb = bt[idx].to(device)
        out = model(xb)
        probs = out[0].reshape(batch, wb, -1)
        logits = out[1].reshape(batch, wb).masked_fill(~mb, -1e9)
        ce = _policy_loss(
            logits, mb, ceq[idx][:, :wb].to(device) if ceq is not None else None, bb
        )
        pick = bb.view(-1, 1, 1).expand(-1, 1, probs.shape[-1])
        best_probs = probs.gather(1, pick).squeeze(1)
        vloss = F.mse_loss(equity_of_probs(best_probs), yt[idx].to(device))
        loss = ce + value_weight * vloss
        if dt is not None:
            ok = dvalid[idx].to(device)
            if bool(ok.any()):
                # ``nan`` satirlar once sifira cevrilir: aksi halde ``nan * 0``
                # yine ``nan`` olur ve maskeleme kaybi zehirler (F7-126).
                target = torch.nan_to_num(dt[idx].to(device), nan=0.0)
                target = target / target.sum(dim=1, keepdim=True).clamp_min(1e-9)
                rows = F.kl_div(
                    torch.log(best_probs.clamp_min(1e-9)), target, reduction="none"
                ).sum(dim=1)
                kl = (rows * ok).sum() / ok.sum().clamp_min(1)
                loss = loss + dist_weight * kl
        if rank_weight > 0:
            rank = out[2].reshape(batch, wb)
            pos = rank.gather(1, bb.view(-1, 1))
            neg_mask = mb.clone()
            neg_mask.scatter_(1, bb.view(-1, 1), False)
            pair = F.softplus(-(pos - rank))
            rloss = (pair * neg_mask).sum() / neg_mask.sum().clamp_min(1)
            loss = loss + rank_weight * rloss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if sched is not None:
            sched.step()
        history.append(float(loss.detach().to("cpu")))
        if progress:
            progress(step, steps, history[-1])
        if checkpoint is not None and checkpoint_every > 0 and step % checkpoint_every == 0:
            _save_checkpoint(step)

        if va_idx_t is not None and (step % max(1, eval_every) == 0 or step == steps):
            metrics = _evaluate(va_idx_t)
            val_history.append({"step": step, **metrics})
            if metrics["ce"] < best_val - 1e-6:
                best_val = metrics["ce"]
                best_step = step
                stale = 0
                best_state = {
                    k: v.detach().clone() for k, v in model.state_dict().items()
                }
            else:
                stale += 1
                if patience > 0 and stale >= patience:
                    stopped_early = True
                    break

    if best_state is not None:
        model.load_state_dict(best_state)

    if checkpoint_every > 0:
        _save_checkpoint(steps)

    train_metrics = _evaluate(tr_idx_t)
    val_metrics = _evaluate(va_idx_t) if va_idx_t is not None else None
    # ``_evaluate`` sonunda modeli tekrar egitim moduna alir; cagiran taraf
    # egitilmis modeli cikarim icin aldigi icin burada eval'e donulmelidir.
    model.eval()

    return {
        "steps": int(steps),
        "stepsRun": len(history),
        "resumedFrom": int(resumed_from),
        "batch": int(batch),
        "lr": float(lr),
        "count": n,
        "trainCount": n_train,
        "valCount": n_val,
        "width": int(width),
        "valueWeight": float(value_weight),
        "distWeight": float(dist_weight),
        "rankWeight": float(rank_weight),
        "weightDecay": float(weight_decay),
        "lrSchedule": lr_schedule,
        "lrFinalRatio": float(lr_final_ratio),
        "policyTemperature": float(policy_temperature),
        "maskedCandidateRate": dataset.masked_candidate_rate(),
        "hasDist": bool(dataset.has_dist()),
        "firstLoss": history[0] if history else None,
        "lastLoss": history[-1] if history else None,
        "top1": train_metrics["top1"],
        "trainCe": train_metrics["ce"],
        "trainValueMse": train_metrics["valueMse"],
        "valTop1": val_metrics["top1"] if val_metrics else None,
        "valCe": val_metrics["ce"] if val_metrics else None,
        "valValueMse": val_metrics["valueMse"] if val_metrics else None,
        "bestStep": best_step,
        "bestValCe": best_val if best_state is not None else None,
        "stoppedEarly": stopped_early,
        "valHistory": val_history,
        "history": history,
    }


#: R-04: ``T`` dogrulama kumesinde secilir; bu izgara taranir.
TEMPERATURE_GRID = (0.02, 0.05, 0.1, 0.2, 0.5, 1.0)


def select_policy_temperature(
    model,
    dataset: PolicyDataset,
    *,
    temperatures: Sequence[float] = TEMPERATURE_GRID,
    val_fraction: float = 0.1,
    seed: int = 0,
    batch: int = 64,
    device: str = "cpu",
) -> dict[str, Any]:
    """Dogrulama kumesinde ``T``'yi secer (R-04: "T dogrulamada secilir").

    Her ``T`` icin **ayni** agirliklarla liste bazli KL hesaplanir; en dusuk
    dogrulama KL'sini veren ``T`` secilir. Bu bir *hedef keskinligi*
    kalibrasyonudur, egitim degil: model guncellenmez.
    """
    import torch  # noqa: PLC0415
    import torch.nn.functional as F  # noqa: PLC0415

    if not dataset.has_cand_equity():
        raise ValueError("T secimi icin aday basina equity (cand_equity) gerekli")
    if not temperatures:
        raise ValueError("bos sicaklik izgarasi")
    if any(t <= 0 for t in temperatures):
        raise ValueError("sicakliklar > 0 olmali")

    n = len(dataset)
    n_val = int(round(n * val_fraction)) if val_fraction > 0 else 0
    if n_val <= 0:
        raise ValueError("T secimi icin val_fraction > 0 gerekli")
    perm = np.random.default_rng(seed).permutation(n)
    val_idx = np.sort(perm[:n_val])

    x, mask, width = _pad_policy(dataset)
    # ``cand_equity`` aday basina 1-B'dir; maske ile ayni sekilde yastiklanir.
    ceq = np.full((n, width), np.nan, dtype=np.float32)
    raw_equity = np.asarray(dataset.cand_equity, dtype=np.float32)
    for i in range(n):
        start = int(dataset.offsets[i])
        stop = int(dataset.offsets[i + 1])
        ceq[i, : stop - start] = raw_equity[start:stop]
    xt = torch.from_numpy(x)
    mt = torch.from_numpy(mask)
    et = torch.from_numpy(ceq)

    model.to(device)
    model.eval()
    totals = {float(t): 0.0 for t in temperatures}
    count = 0
    with torch.no_grad():
        for start in range(0, int(val_idx.size), batch):
            sel = torch.from_numpy(np.asarray(val_idx[start : start + batch], dtype=np.int64))
            k = int(sel.numel())
            m = mt[sel]
            w = max(1, min(int(m.sum(dim=1).max().item()), width))
            xb = xt[sel][:, :w].reshape(-1, 221).to(device)
            mb = m[:, :w].to(device)
            eq = et[sel][:, :w].to(device)
            logits = model(xb)[1].reshape(k, w).masked_fill(~mb, -1e9)
            labelled = mb & ~torch.isnan(eq)
            valid = labelled.any(dim=1)
            log_pred = F.log_softmax(logits, dim=1)
            for t in temperatures:
                target_logits = torch.where(
                    labelled, eq / float(t), torch.full_like(eq, -1e9)
                )
                log_target = F.log_softmax(target_logits, dim=1)
                target = log_target.exp()
                per_position = (target * (log_target - log_pred)).sum(dim=1)
                totals[float(t)] += float(
                    ((per_position * valid).sum() / valid.sum().clamp_min(1)).to("cpu")
                ) * k
            count += k
    scores = {t: (v / count if count else float("nan")) for t, v in totals.items()}
    best = min(scores, key=lambda t: scores[t])
    return {
        "best": best,
        "scores": {("%g" % t): scores[t] for t in sorted(scores)},
        "valCount": count,
        "valFraction": float(val_fraction),
        "seed": int(seed),
    }


# ----------------------------------------------------------------------
# F8-03: korpus SL (Adim B) - bgsage "run_sl_training.py" deseni
# ----------------------------------------------------------------------

#: bgsage per-Net ayrimi: temas ve saf yaris ayri aglarda egitilir.
SL_NET_NAMES: tuple[str, ...] = ("contact", "race")

#: Per-Net varsayilan epoch sayisi (bgsage Ek A: contact daha buyuk korpus).
SL_DEFAULT_EPOCHS: dict[str, int] = {"contact": 6, "race": 10}

#: Per-Net varsayilan ogrenme orani takvimi ``(alpha_baslangic, alpha_son)``.
SL_DEFAULT_ALPHA: dict[str, tuple[float, float]] = {
    "contact": (1e-3, 1e-4),
    "race": (2e-3, 2e-4),
}

#: Korpus dizininde aranan bildirim dosyasi.
SL_MANIFEST_NAME = "manifest.json"

#: ``gnubg_er.IS_CONTACT`` noronunun 221 vektordeki indeksi.
SL_CONTACT_NEURON = 204


def sl_schedule(
    epochs: int, alpha_start: float, alpha_end: float
) -> list[dict[str, float]]:
    """Per-Net epoch/alpha takvimi (bgsage deseni).

    Her epoch icin ogrenme orani ``alpha_start``dan ``alpha_end``e **dogrusal**
    iner. bgsage kosinus yerine bu basit takvimi kullanir; epoch sayisi kucuk
    oldugu icin (6-12) fark olcumsuzdur ve dogrusal takvim tekrar uretilebilir.
    """
    if epochs <= 0:
        raise ValueError("epochs > 0 olmali")
    if alpha_start <= 0 or alpha_end <= 0:
        raise ValueError("alpha degerleri > 0 olmali")
    if alpha_end > alpha_start:
        raise ValueError("alpha_end <= alpha_start olmali (takvim iner)")
    if epochs == 1:
        return [{"epoch": 1, "alpha": float(alpha_start)}]
    step = (alpha_start - alpha_end) / float(epochs - 1)
    return [
        {"epoch": i + 1, "alpha": float(alpha_start - step * i)} for i in range(epochs)
    ]


def split_by_contact(dataset: PolicyDataset) -> dict[str, PolicyDataset]:
    """Politika veri kumesini ``contact`` / ``race`` alt kumelerine ayirir.

    Ayrim **vektorun kendisinden** yapilir: ``gnubg_er.vectorize`` 204.
    noronda ``is_contact`` bayragini tasir, dolayisiyla tahta yeniden
    kurulmaz. Bos alt kume sonuc sozlugune **girmez** (cagiran taraf eksik
    Net'i raporlar).
    """
    if len(dataset) == 0:
        return {}
    x = np.asarray(dataset.x, dtype=np.float32)
    if x.ndim != 2 or int(x.shape[1]) <= SL_CONTACT_NEURON:
        raise ValueError("vektor genisligi 221 olmali (IS_CONTACT noronu yok)")
    # ``x`` duzensiz aday dizisidir ([M, 221]); pozisyon basina **ilk** aday
    # satiri temsilcidir (bayrak pozisyonun kendisine aittir).
    starts = np.asarray(dataset.offsets[:-1], dtype=np.int64)
    flags = x[starts, SL_CONTACT_NEURON] > 0.5
    out: dict[str, PolicyDataset] = {}
    for name, mask in (("contact", flags), ("race", ~flags)):
        idx = np.flatnonzero(mask)
        if idx.size:
            out[name] = dataset.subset(idx.tolist())
    return out


def load_sl_corpus(
    corpus_dir: Path, *, nets: Sequence[str] | None = None
) -> tuple[dict[str, PolicyDataset], dict[str, Any]]:
    """Korpus dizinini okur ve per-Net veri kumelerini dondurur.

    Beklenen duzen (bgsage ``run_sl_training.py`` veri dizini)::

        <corpus_dir>/
          manifest.json     # opsiyonel: {"nets": {"contact": {...}, ...}}
          contact.npz       # ``label-policy`` ciktisi
          race.npz

    ``manifest.json`` yoksa ``*.npz`` dosyalari adlarindan turetilir ve
    varsayilan epoch/alpha takvimi kullanilir. Tek bir ``all.npz`` varsa
    ``split_by_contact`` ile ikiye ayrilir.
    """
    root = Path(corpus_dir)
    if not root.is_dir():
        raise FileNotFoundError("korpus dizini yok: " + str(root))
    wanted = tuple(nets) if nets else SL_NET_NAMES
    for name in wanted:
        if name not in SL_NET_NAMES:
            raise ValueError("bilinmeyen Net: " + repr(name))

    manifest: dict[str, Any] = {"dir": str(root), "nets": {}}
    manifest_path = root / SL_MANIFEST_NAME
    if manifest_path.is_file():
        # utf-8-sig: Windows araclari (PowerShell 5.1 `Set-Content -Encoding utf8`)
        # BOM yazar; BOM'lu bildirim gecerli sayilir.
        raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("manifest.json bir nesne olmali")
        manifest["source"] = "manifest"
        declared = raw.get("nets") or {}
        if not isinstance(declared, dict):
            raise ValueError("manifest.json 'nets' bir nesne olmali")
    else:
        manifest["source"] = "auto"
        declared = {}

    datasets: dict[str, PolicyDataset] = {}
    for name in wanted:
        entry = declared.get(name) or {}
        rel = entry.get("data") if isinstance(entry, dict) else None
        path = root / (rel or (name + ".npz"))
        if path.is_file():
            datasets[name] = load_policy_dataset(path)
            manifest["nets"][name] = {
                "data": path.name,
                "count": int(len(datasets[name])),
                "epochs": int(entry.get("epochs", SL_DEFAULT_EPOCHS[name])),
                "alpha": list(entry.get("alpha", SL_DEFAULT_ALPHA[name])),
            }
            continue
        # Tek dosya duzeni: all.npz -> temas/yaris ayrimi.
        single = root / "all.npz"
        if single.is_file():
            if "all" not in datasets:
                datasets["all"] = load_policy_dataset(single)
            split = split_by_contact(datasets["all"])
            if name in split:
                datasets[name] = split[name]
                manifest["nets"][name] = {
                    "data": single.name + "#" + name,
                    "count": int(len(split[name])),
                    "epochs": int(entry.get("epochs", SL_DEFAULT_EPOCHS[name])),
                    "alpha": list(entry.get("alpha", SL_DEFAULT_ALPHA[name])),
                }
    if not manifest["nets"]:
        raise FileNotFoundError(
            "korpus dizininde kullanilabilir Net yok (contact.npz / race.npz / all.npz): "
            + str(root)
        )
    manifest["missing"] = [n for n in wanted if n not in manifest["nets"]]
    return datasets, manifest


def train_corpus_sl(
    model,
    datasets: dict[str, PolicyDataset],
    manifest: dict[str, Any],
    *,
    order: Sequence[str] | None = None,
    batch: int = DEFAULT_BATCH,
    device: str = "cpu",
    seed: int = 0,
    value_weight: float = DEFAULT_VALUE_WEIGHT,
    dist_weight: float = 0.0,
    val_fraction: float = 0.0,
    patience: int = 0,
    eval_every: int = 500,
    weight_decay: float = 0.0,
    policy_temperature: float = 0.0,
    mix: bool = False,
    progress: Callable[[str, int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Per-Net SL asamasi: her Net kendi epoch/alpha takvimiyle egitilir.

    Tek monolotik agimiz oldugu icin bgsage'in ayri Net'leri burada bir
    **mufredat** olarak uygulanir. Iki duzen var:

    - ``mix=False`` (varsayilan, **sirali**): ``contact`` tamamen bitince
      agirliklar ``race`` epoch'larina tasinir. gnubg/bgsage'in *ayri* Net'leri
      icin dogru desen; tek paylasilan agda ise kucuk Net'in son fazi buyuk
      Net'in ogrendigini siler (F8-03'te olculdu: yalniz ``contact`` 0,0072,
      ardindan ``race`` fazi 0,0287 — **feci unutma**).
    - ``mix=True`` (**serpistirilmis**): her epoch icinde Net'ler kucukten
      buyuge dogru sirayla egitilir; epoch daima en buyuk Net ile kapanir, yani
      kucuk Net'in gradyani bir sonraki epoch'ta yeniden capalanir. Tek
      paylasilan ag icin dogru desen.
    """
    if not datasets:
        raise ValueError("SL icin veri kumesi yok")
    seq = [n for n in (order or SL_NET_NAMES) if n in datasets]
    if not seq:
        raise ValueError("SL icin istenen Net'lerin hicbiri yuklenmedi")

    plans: dict[str, dict[str, Any]] = {}
    for name in seq:
        entry = (manifest.get("nets") or {}).get(name) or {}
        epochs = int(entry.get("epochs", SL_DEFAULT_EPOCHS[name]))
        alpha = entry.get("alpha", SL_DEFAULT_ALPHA[name])
        if not isinstance(alpha, (list, tuple)) or len(alpha) != 2:
            raise ValueError("alpha iki elemanli olmali: " + repr(alpha))
        plans[name] = {
            "epochs": epochs,
            "alpha": [float(alpha[0]), float(alpha[1])],
            "schedule": sl_schedule(epochs, float(alpha[0]), float(alpha[1])),
        }

    if mix:
        # Kucukten buyuge: epoch'un son gradyani en buyuk Net'ten gelsin.
        max_epochs = max(p["epochs"] for p in plans.values())
        units: list[tuple[int, str, dict[str, float]]] = []
        for epoch in range(1, max_epochs + 1):
            for name in sorted(seq, key=lambda n: (len(datasets[n]), n)):
                schedule = plans[name]["schedule"]
                if epoch <= len(schedule):
                    units.append((epoch, name, schedule[epoch - 1]))
    else:
        units = []
        for name in seq:
            for item in plans[name]["schedule"]:
                units.append((int(item["epoch"]), name, item))

    nets_report: dict[str, Any] = {}
    total_steps = 0
    for epoch, name, item in units:
        dataset = datasets[name]
        steps = max(1, int(round(len(dataset) / max(1, batch))))
        report = train_policy_head(
            model,
            dataset,
            steps=steps,
            lr=float(item["alpha"]),
            batch=batch,
            device=device,
            seed=seed + epoch,
            value_weight=value_weight,
            dist_weight=dist_weight,
            val_fraction=val_fraction,
            patience=patience,
            eval_every=eval_every,
            weight_decay=weight_decay,
            policy_temperature=policy_temperature,
            progress=(
                None
                if progress is None
                else (
                    lambda step, total, loss, _n=name, _e=epoch: progress(
                        _n, _e, step, loss
                    )
                )
            ),
        )
        total_steps += steps
        entry = nets_report.setdefault(
            name,
            {
                "count": int(len(dataset)),
                "epochs": plans[name]["epochs"],
                "alpha": list(plans[name]["alpha"]),
                "history": [],
            },
        )
        entry["history"].append(
            {
                "epoch": epoch,
                "alpha": float(item["alpha"]),
                "steps": steps,
                "lastLoss": float(report["lastLoss"]),
                "top1": float(report["top1"]),
                "valTop1": report.get("valTop1"),
                "valLoss": report.get("valLoss"),
            }
        )

    for name, entry in nets_report.items():
        entry["lastLoss"] = entry["history"][-1]["lastLoss"]
        entry["top1"] = entry["history"][-1]["top1"]
        entry["valTop1"] = entry["history"][-1]["valTop1"]

    return {
        "nets": nets_report,
        "order": seq,
        "mix": bool(mix),
        "totalSteps": total_steps,
        "totalPositions": int(sum(v["count"] for v in nets_report.values())),
        "manifestSource": manifest.get("source"),
        "missingNets": list(manifest.get("missing") or []),
    }


# ----------------------------------------------------------------------
# Eslesmis test
# ----------------------------------------------------------------------


def load_er_losses(path: Path) -> dict[str, float]:
    """``er_harness measure`` JSON'undan pozisyon basina equity kaybi.

    Anahtar pozisyon adidir; iki olcum ayni korpusu kullandigi icin
    eslesmis (paired) karsilastirma yapilabilir.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for pos in data.get("positions") or []:
        name = pos.get("name")
        loss = pos.get("equityLoss")
        if name is None or loss is None:
            continue
        out[str(name)] = float(loss)
    return out


def parse_arm(text: str) -> tuple[str, Path]:
    """``etiket=yol`` bicimindeki kol tanimini ayristirir."""
    if "=" not in text:
        raise ValueError("kol tanimi 'etiket=yol' biciminde olmali: " + repr(text))
    label, _, raw = text.partition("=")
    label = label.strip()
    if not label:
        raise ValueError("kol etiketi bos olamaz: " + repr(text))
    return label, Path(raw.strip())


def paired_loss_test(
    before: dict[str, float],
    after: dict[str, float],
    *,
    z: float = 1.96,
) -> dict[str, Any]:
    """Ayni pozisyonlarda iki ER olcumunun eslesmis farki.

    ``meanDiff = mean(before - after)``; pozitif deger iyilesme demektir.
    ``excludesZero`` yalnizca %95 GA sifiri disliyorsa ``True`` olur: ancak o
    zaman "iyilesme kanitlandi" denebilir. Eslesmis test, ayni korpusu
    kullandigi icin pozisyon zorlugundan gelen varyansi eler ve bagimsiz
    iki ornek testinden **daha gucludur**.
    """
    names = sorted(set(before) & set(after))
    n = len(names)
    if n < 2:
        return {
            "n": n,
            "meanDiff": 0.0,
            "sd": 0.0,
            "se": 0.0,
            "t": 0.0,
            "ciLow": 0.0,
            "ciHigh": 0.0,
            "excludesZero": False,
        }
    diffs = [float(before[k]) - float(after[k]) for k in names]
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    sd = math.sqrt(var)
    se = sd / math.sqrt(n)
    t_stat = mean / se if se > 0.0 else 0.0
    low = mean - z * se
    high = mean + z * se
    return {
        "n": n,
        "meanDiff": mean,
        "sd": sd,
        "se": se,
        "t": t_stat,
        "ciLow": low,
        "ciHigh": high,
        "excludesZero": bool(low > 0.0 or high < 0.0),
    }


# ----------------------------------------------------------------------
# Karar
# ----------------------------------------------------------------------


def paired_er_test(
    before: dict[str, float],
    after: dict[str, float],
    *,
    resamples: int = PAIRED_BOOTSTRAP_RESAMPLES,
    seed: int = PAIRED_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Ayni pozisyonlarda iki ER olcumunun **eslesmis** karsilastirmasi.

    ``paired_loss_test`` yalnizca normal yaklasimla fark GA'si veriyordu; bu
    fonksiyon **bootstrap** GA uretir ve ayrica ``er_after``in **mutlak** GA'sini
    hesaplar. Ikincisi zorunludur: "ogretmen etkili" iddiasi "ER hedefin altinda"
    demektir ve bu, farkin degil **mutlak** ER'nin GA'siyla sinanmalidir
    (Faz 7-R R-07: eski kod ``er_after <= target`` nokta tahminine bakiyordu).

    Donen alanlar:
      ``n``, ``meanBefore``, ``meanAfter``, ``meanDiff``, ``sdDiff``,
      ``seDiff``, ``ciLowDiff``, ``ciHighDiff``, ``excludesZero``,
      ``ciLowAfter``, ``ciHighAfter``, ``resamples``, ``seed``.
    """
    names = sorted(set(before) & set(after))
    n = len(names)
    empty = {
        "n": n,
        "meanBefore": float("nan"),
        "meanAfter": float("nan"),
        "meanDiff": 0.0,
        "sdDiff": 0.0,
        "seDiff": 0.0,
        "ciLowDiff": 0.0,
        "ciHighDiff": 0.0,
        "excludesZero": False,
        "ciLowAfter": float("nan"),
        "ciHighAfter": float("nan"),
        "resamples": 0,
        "seed": int(seed),
    }
    if n < 2:
        return empty

    b = np.asarray([float(before[k]) for k in names], dtype=np.float64)
    a = np.asarray([float(after[k]) for k in names], dtype=np.float64)
    diff = b - a
    mean_diff = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1))
    se_diff = sd_diff / math.sqrt(n)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(int(resamples), n))
    boot_diff = diff[idx].mean(axis=1)
    boot_after = a[idx].mean(axis=1)
    low_diff = float(np.percentile(boot_diff, 2.5))
    high_diff = float(np.percentile(boot_diff, 97.5))
    low_after = float(np.percentile(boot_after, 2.5))
    high_after = float(np.percentile(boot_after, 97.5))
    return {
        "n": n,
        "meanBefore": float(np.mean(b)),
        "meanAfter": float(np.mean(a)),
        "meanDiff": mean_diff,
        "sdDiff": sd_diff,
        "seDiff": se_diff,
        "ciLowDiff": low_diff,
        "ciHighDiff": high_diff,
        "excludesZero": bool(low_diff > 0.0 or high_diff < 0.0),
        "ciLowAfter": low_after,
        "ciHighAfter": high_after,
        "resamples": int(resamples),
        "seed": int(seed),
    }


def distill_verdict(
    er_before: float | None,
    er_after: float | None,
    *,
    target: float = TARGET_ER,
    min_gain: float = MIN_GAIN,
    paired: dict[str, Any] | None = None,
    required_n: int | None = None,
) -> str:
    """gnubg ogretmen deneyinin karari (Faz 7-R R-07 ile yeniden yazildi).

    Kural 3 geregi **once eslesmis fark + bootstrap GA** gelir; nokta tahmini
    tek basina kanit degildir.

    * olcum eksik / sonlu degil -> ``bilinmiyor``
    * ``paired`` yok -> ``belirsiz`` (eslesmis kanit yok)
    * ``required_n`` verildi ve ``n < required_n`` -> ``veri-yetersiz``
    * ``paired["ciHighAfter"] <= target`` -> ``ogretmen-etkili``: ER'nin **GA
      ust siniri** hedefin altinda, yani ogretmen etiketleri ise yaradi. Bu
      **kapasite/pipeline ayrimi degildir**; o ayrim ogrenme egrisiyle kurulur.
    * GA sifiri disliyor ve ``meanDiff > 0`` -> ``kismi``: kazanc kanitlandi
      ama ER hedefin uzerinde.
    * aksi halde -> ``belirsiz``.

    **Kapasite cikarimi kaldirildi.** Etiketlerin ise yaramamasi, dar bogazin
    ag/veri oldugunu **kanitlamaz**; o iddia ancak ``ml/learning_curve.py``
    egimiyle kurulabilir. Bu yuzden ``VERDICT_CAPACITY`` artik donmez.
    """
    if er_before is None or er_after is None:
        return VERDICT_UNKNOWN
    if not (math.isfinite(er_before) and math.isfinite(er_after)):
        return VERDICT_UNKNOWN
    if paired is None:
        return VERDICT_UNPROVEN
    n = int(paired.get("n", 0) or 0)
    if required_n is not None and n < int(required_n):
        return VERDICT_INSUFFICIENT_DATA
    ci_high_after = paired.get("ciHighAfter")
    if ci_high_after is not None and math.isfinite(float(ci_high_after)):
        if float(ci_high_after) <= float(target):
            return VERDICT_TEACHER_EFFECTIVE
    if paired.get("excludesZero", False) and float(paired.get("meanDiff", 0.0)) > 0.0:
        return VERDICT_PARTIAL
    return VERDICT_UNPROVEN


def distill_verdict_detail(
    er_before: float | None,
    er_after: float | None,
    *,
    target: float = TARGET_ER,
    min_gain: float = MIN_GAIN,
    paired: dict[str, Any] | None = None,
    required_n: int | None = None,
) -> dict[str, Any]:
    """``distill_verdict``in gerekceli hali (rapor icin)."""
    verdict = distill_verdict(
        er_before,
        er_after,
        target=target,
        min_gain=min_gain,
        paired=paired,
        required_n=required_n,
    )
    meets_min_gain = None
    if er_before is not None and er_after is not None and er_before > 0.0:
        meets_min_gain = bool(er_after <= er_before * (1.0 - min_gain))
    return {
        "verdict": verdict,
        "target": float(target),
        "minGain": float(min_gain),
        "meetsMinGain": meets_min_gain,
        "requiredN": None if required_n is None else int(required_n),
        "n": None if paired is None else int(paired.get("n", 0) or 0),
        "paired": paired,
        "capacityInference": False,
    }


VERDICT_TEXT = {
    VERDICT_TEACHER_EFFECTIVE: (
        "**Ogretmen etkili.** ER'nin GA ust siniri hedefin altina indi: gnubg "
        "etiketleri ise yaradi. Bu, kendi aramamizin urettigi hedeflerin "
        "yetersiz kaldigini gosterir. **Kapasite/pipeline ayrimi bu etiketten "
        "cikmaz**; o ayrim `ml/learning_curve.py` egrisiyle kurulur."
    ),
    VERDICT_PARTIAL: (
        "Anlamli iyilesme var ama ER hedefin uzerinde. Ogretmen **kismen** "
        "etkili: etiket hattini (gnubg ogretmen) kalici hale getirin. "
        "Kapasite payi bu olcumden cikmaz; ogrenme egrisiyle olculmelidir."
    ),
    VERDICT_CAPACITY: (
        "**Kaldirildi (Faz 7-R R-07).** Etiketlerin ise yaramamasi kapasiteyi "
        "kanitlamaz; bu etiket artik uretilmez. 'Olcek mi pipeline mi' karari "
        "`ml/learning_curve.py` egimiyle verilir."
    ),
    VERDICT_INSUFFICIENT_DATA: (
        "Orneklem **yetersiz**: n, gereken n'nin altinda. Bu durumda ne "
        "'kazanc var' ne 'kazanc yok' denebilir. Gereken n, sigma'nin **ust "
        "guven sinirindan** hesaplanir (Kural 4)."
    ),
    VERDICT_UNPROVEN: (
        "Nokta tahmini iyilesti ama eslesmis %95 GA **sifiri dislamiyor**: fark"
        " gurultuden ayirt edilemiyor. Ne 'etiketler ise yaradi' ne 'etiketler"
        " ise yaramadi' denebilir. Karar icin daha fazla pozisyon gerekir."
    ),
    VERDICT_UNKNOWN: (
        "Karar icin iki ER olcumu de gerekli (once/sonra). Eksik olcumle karar "
        "verilmez."
    ),
}


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def build_markdown(report: dict[str, Any], *, title: str = "Faz 7 - gnubg ogretmen deneyi") -> str:
    """Insan-okur Markdown rapor."""
    lines: list[str] = ["# " + title, ""]
    lines.append("Soru: **etiketler mi yetersiz, kapasite mi?** gnubg 2-ply")
    lines.append("etiketleriyle **politika** kafasi egitilir ve ER yeniden olculur.")
    lines.append("")
    lines.append("> **Neden politika, deger degil?** ER `er_harness` icinde **politika**")
    lines.append("> basi argmax ile olculur (`criterion=\"policy\"`). Deger kafasini")
    lines.append("> egitmek bu karar yolunda okunmaz; olculen ER'yi tanimi geregi")
    lines.append("> degistirmez. Bu, olcumle dogrulandi (bkz. bolum 2).")
    lines.append("")

    data = report.get("dataset") or {}
    lines.append("## 1. Veri kumesi")
    lines.append("")
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| Pozisyon | %d |" % int(data.get("count", 0)))
    lines.append("| Atlanan | %d |" % int(report.get("skipped", 0)))
    if data.get("count"):
        lines.append("| Hedef ortalama | %+.4f |" % float(data.get("mean", 0.0)))
        lines.append("| Hedef std | %.4f |" % float(data.get("std", 0.0)))
        lines.append("| Hedef min / max | %+.4f / %+.4f |" % (data.get("min", 0.0), data.get("max", 0.0)))
    lines.append("")

    value = report.get("value") or {}
    if value:
        lines.append("## 2. Deger kafasi denemesi (yetersiz kaldi)")
        lines.append("")
        lines.append("| Olcum | Deger |")
        lines.append("|---|---|")
        lines.append("| Egitim MAE | %.4f |" % float(value.get("finalMae", 0.0)))
        lines.append("| Korelasyon | %.4f |" % float(value.get("correlation", 0.0)))
        lines.append("| Egim | %.4f |" % float(value.get("slope", 0.0)))
        if value.get("er") is not None:
            lines.append("| Olculen ER | %.4f |" % float(value["er"]))
        lines.append("")
        lines.append("Egitim metrikleri neredeyse kusursuz, ama ER degismedi:")
        lines.append("deger kafasi **politika argmax** yolunda okunmuyor.")
        lines.append("")

    policy = report.get("policy") or {}
    if policy:
        lines.append("## 3. Politika damitma (asil hat)")
        lines.append("")
        lines.append("| Olcum | Deger |")
        lines.append("|---|---|")
        lines.append("| Adim | %d |" % int(policy.get("steps", 0)))
        lines.append("| Aday genisligi (en fazla) | %d |" % int(policy.get("width", 0)))
        lines.append("| Deger agirligi | %.2f |" % float(policy.get("valueWeight", 0.0)))
        lines.append("| Ilk / son kayip | %.6f / %.6f |" % (policy.get("firstLoss") or 0.0, policy.get("lastLoss") or 0.0))
        lines.append("| Egitim top-1 | %.4f |" % float(policy.get("top1", 0.0)))
        lines.append("")
        lines.append("> Egitim top-1 **ezberdir**, genelleme degil. Gercek olcu VAL-ER'dir.")
        lines.append("")

    lines.append("## 4. Karar")
    lines.append("")
    verdict = report.get("verdict", VERDICT_UNKNOWN)
    lines.append("**`%s`**" % verdict)
    lines.append("")
    lines.append(VERDICT_TEXT.get(verdict, ""))
    lines.append("")
    before = report.get("erBefore")
    after = report.get("erAfter")
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| ER once | %s |" % ("-" if before is None else "%.4f" % before))
    lines.append("| ER sonra | %s |" % ("-" if after is None else "%.4f" % after))
    lines.append("| Hedef | %.4f |" % float(report.get("target", TARGET_ER)))
    if before is not None and after is not None and before > 0.0:
        lines.append("| Iyilesme | %.1f%% |" % (100.0 * (before - after) / before))
    lines.append("")

    paired = report.get("paired") or {}
    if paired:
        lines.append("### 4.1 Eslesmis test")
        lines.append("")
        lines.append("| Olcum | Deger |")
        lines.append("|---|---|")
        lines.append("| Pozisyon | %d |" % int(paired.get("n", 0)))
        lines.append("| Ortalama fark | %+.4f |" % float(paired.get("meanDiff", 0.0)))
        lines.append("| Std hata | %.4f |" % float(paired.get("se", 0.0)))
        lines.append("| t | %+.2f |" % float(paired.get("t", 0.0)))
        lines.append(
            "| GA95 | [%+.4f; %+.4f] |"
            % (float(paired.get("ciLow", 0.0)), float(paired.get("ciHigh", 0.0)))
        )
        lines.append(
            "| Sifiri disliyor | %s |"
            % ("evet" if paired.get("excludesZero") else "**hayir**")
        )
        lines.append("")
        if not paired.get("excludesZero"):
            lines.append(
                "> GA sifiri dislamiyor: nokta tahmini iyilesme gosterse de fark"
                " **gurultuden ayirt edilemiyor**. Bu yuzden kazanc kanitlanmis"
                " sayilmaz."
            )
            lines.append("")

    arms = report.get("arms") or []
    if arms:
        lines.append("### 4.2 Veri hacmi kollari")
        lines.append("")
        lines.append("| Kol | Pozisyon | ER | Fark (once) | GA95 | Sifiri disliyor |")
        lines.append("|---|---|---|---|---|---|")
        for arm in arms:
            pv = arm.get("pairedVsBefore") or {}
            if pv:
                lines.append(
                    "| %s | %d | %.4f | %+.4f | [%+.4f; %+.4f] | %s |"
                    % (
                        arm.get("label", "?"),
                        int(arm.get("positions", 0)),
                        float(arm.get("er", 0.0)),
                        float(pv.get("meanDiff", 0.0)),
                        float(pv.get("ciLow", 0.0)),
                        float(pv.get("ciHigh", 0.0)),
                        "evet" if pv.get("excludesZero") else "**hayir**",
                    )
                )
            else:
                lines.append(
                    "| %s | %d | %.4f | - | - | - |"
                    % (
                        arm.get("label", "?"),
                        int(arm.get("positions", 0)),
                        float(arm.get("er", 0.0)),
                    )
                )
        lines.append("")
        lines.append(
            "> Veri hacmi arttikca ER'nin **monoton** iyilesmesi beklenir. "
            "Iyilesmiyorsa kol farki gurultudur; hacim tek basina cozum degildir."
        )
        lines.append("")

    notes = report.get("notes") or []
    if notes:
        lines.append("## 5. Durustluk notlari")
        lines.append("")
        for note in notes:
            lines.append("- " + note)
        lines.append("")

    lines.append("> " + LICENSE_NOTE)
    lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gnubg_distill",
        description="gnubg 2-ply etiketleriyle deger kafasi damitma (madde 1.3).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    lab = sub.add_parser("label", help="pozisyon uret ve gnubg ile etiketle")
    lab.add_argument("--out", type=Path, required=True, help="cikti .npz")
    lab.add_argument("--positions", type=int, default=DEFAULT_POSITIONS)
    lab.add_argument("--plies", type=int, default=DEFAULT_PLIES)
    lab.add_argument("--seed", type=int, default=7)
    lab.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)
    lab.add_argument("--gnubg", type=Path, default=None)
    lab.add_argument("--timeout", type=int, default=60)
    lab.add_argument("--quiet", action="store_true")

    tr = sub.add_parser("train", help="deger kafasini etiketlerle egit")
    tr.add_argument("--data", type=Path, required=True)
    tr.add_argument("--ckpt", type=Path, required=True)
    tr.add_argument("--out", type=Path, required=True)
    tr.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    tr.add_argument("--lr", type=float, default=DEFAULT_LR)
    tr.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    tr.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    tr.add_argument("--seed", type=int, default=0)
    tr.add_argument("--json", type=Path, default=None)
    tr.add_argument("--quiet", action="store_true")

    vd = sub.add_parser("verdict", help="iki ER olcumunden karar uret")
    vd.add_argument("--before", type=float, required=True)
    vd.add_argument("--after", type=float, required=True)
    vd.add_argument("--target", type=float, default=TARGET_ER)
    vd.add_argument("--min-gain", type=float, default=MIN_GAIN)
    vd.add_argument(
        "--required-n",
        type=int,
        default=None,
        help="gereken n (sigma ust sinirindan); n altindaysa 'veri-yetersiz'",
    )
    vd.add_argument("--value-json", type=Path, default=None, help="deger kafasi egitim raporu")
    vd.add_argument("--value-er", type=float, default=None, help="deger kafasi denemesinin ER'si")
    vd.add_argument("--er-before-json", type=Path, default=None, help="once olcumu (er_harness JSON)")
    vd.add_argument("--er-after-json", type=Path, default=None, help="sonra olcumu (er_harness JSON)")
    vd.add_argument(
        "--arm",
        action="append",
        default=[],
        metavar="ETIKET=YOL",
        help="ek olcum kolu (tekrarlanabilir); veri hacmi karsilastirmasi icin",
    )
    vd.add_argument("--policy-json", type=Path, default=None, help="politika egitim raporu")
    vd.add_argument("--dataset", type=Path, default=None, help="politika veri kumesi (.npz)")
    vd.add_argument("--skipped", type=int, default=0)
    vd.add_argument("--json", type=Path, default=None)
    vd.add_argument("--markdown", type=Path, default=None)
    vd.add_argument("--quiet", action="store_true")

    lp = sub.add_parser(
        "label-policy", help="pozisyon uret ve gnubg ile **politika** hedefi etiketle"
    )
    lp.add_argument("--out", type=Path, required=True, help="cikti .npz")
    lp.add_argument("--positions", type=int, default=DEFAULT_POSITIONS)
    lp.add_argument("--plies", type=int, default=DEFAULT_PLIES)
    lp.add_argument("--seed", type=int, default=7)
    lp.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)
    lp.add_argument("--gnubg", type=Path, default=None)
    lp.add_argument("--timeout", type=int, default=60)
    lp.add_argument(
        "--dists",
        action="store_true",
        help="en iyi adayin 6 sinifli gnubg dagilimini da etiketle (K5)",
    )
    lp.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="0 tabanli dilim numarasi (paralel etiketleme icin)",
    )
    lp.add_argument(
        "--shards",
        type=int,
        default=1,
        help="toplam dilim sayisi; her dilim ayri bir tohum kullanir",
    )
    lp.add_argument("--quiet", action="store_true")

    mp = sub.add_parser(
        "merge-policy", help="paralel etiketlenmis politika dilimlerini birlestir"
    )
    mp.add_argument(
        "--shard",
        type=Path,
        action="append",
        required=True,
        metavar="NPZ",
        help="girdi dilimi (tekrarlanabilir)",
    )
    mp.add_argument("--out", type=Path, required=True, help="birlesik cikti .npz")
    mp.add_argument("--json", type=Path, default=None)
    mp.add_argument("--quiet", action="store_true")

    tp = sub.add_parser("train-policy", help="politika kafasini gnubg hamlesine egit")
    tp.add_argument("--data", type=Path, required=True)
    tp.add_argument("--ckpt", type=Path, required=True)
    tp.add_argument("--out", type=Path, required=True)
    tp.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    tp.add_argument("--lr", type=float, default=DEFAULT_LR)
    tp.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    tp.add_argument("--value-weight", type=float, default=DEFAULT_VALUE_WEIGHT)
    tp.add_argument(
        "--dist-weight",
        type=float,
        default=0.0,
        help="6 sinifli KL teriminin agirligi (K5; veri kumesinde dist gerekir)",
    )
    tp.add_argument(
        "--rank-weight",
        type=float,
        default=0.0,
        help="ikili siralama (pairwise ranking) teriminin agirligi; >0 icin model "
        "siralama kafasi ile kurulur (yalnizca egitimde, ONNX'e cikmaz)",
    )
    tp.add_argument(
        "--profile",
        default=None,
        help="kapasite profilini zorla (large/xlarge); checkpoint profilini ezer",
    )
    tp.add_argument(
        "--val-fraction",
        type=float,
        default=0.0,
        help="dogrulama icin ayrilan pozisyon orani (0 = ayirma yok)",
    )
    tp.add_argument(
        "--patience",
        type=int,
        default=0,
        help="dogrulama kaybi iyilesmezse kac degerlendirmeden sonra dur (0 = kapali)",
    )
    tp.add_argument(
        "--eval-every",
        type=int,
        default=500,
        help="dogrulama degerlendirme araligi (adim)",
    )
    tp.add_argument(
        "--weight-decay",
        type=float,
        default=0.0,
        help="Adam L2 cezasi (buyuk kapasitede asiri ogrenmeyi bastirir)",
    )
    tp.add_argument(
        "--lr-schedule",
        default="none",
        choices=["none", "cosine"],
        help="ogrenme orani zamanlamasi (cosine = lr -> lr*lr_final_ratio)",
    )
    tp.add_argument(
        "--lr-final-ratio",
        type=float,
        default=0.1,
        help="kosinus zamanlamasinin son orani (lr'in kaci)",
    )
    tp.add_argument(
        "--policy-temperature",
        type=float,
        default=0.0,
        help=">0 ise sert top-1 CE yerine liste bazli KL(softmax(equity/T) || "
        "softmax(logits)) kullanilir (R-04); aday basina equity gerekir",
    )
    tp.add_argument(
        "--select-temperature",
        action="store_true",
        help="egitimden once dogrulama kumesinde T'yi tara ve en iyisini kullan",
    )
    tp.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    tp.add_argument("--seed", type=int, default=0)
    tp.add_argument("--json", type=Path, default=None)
    tp.add_argument("--quiet", action="store_true")

    cs = sub.add_parser(
        "corpus-sl",
        help="korpus SL asamasi: per-Net (contact/race) epoch/alpha takvimi (F8-03)",
    )
    cs.add_argument(
        "--corpus-dir",
        type=Path,
        required=True,
        help="korpus dizini (contact.npz / race.npz / all.npz + opsiyonel manifest.json)",
    )
    cs.add_argument(
        "--init-from",
        type=Path,
        required=True,
        help="warm-start checkpoint (G2: sifirdan baslangic reddedilir)",
    )
    cs.add_argument("--out", type=Path, required=True, help="cikti checkpoint")
    cs.add_argument(
        "--nets",
        default=",".join(SL_NET_NAMES),
        help="egitilecek Net'ler, virgulle ayrilmis (varsayilan: contact,race)",
    )
    cs.add_argument(
        "--order",
        default=None,
        help="mufredat sirasi (varsayilan: --nets sirasi)",
    )
    cs.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    cs.add_argument("--value-weight", type=float, default=DEFAULT_VALUE_WEIGHT)
    cs.add_argument("--dist-weight", type=float, default=0.0)
    cs.add_argument("--val-fraction", type=float, default=0.0)
    cs.add_argument("--patience", type=int, default=0)
    cs.add_argument("--eval-every", type=int, default=500)
    cs.add_argument("--weight-decay", type=float, default=0.0)
    cs.add_argument("--policy-temperature", type=float, default=0.0)
    cs.add_argument(
        "--mix",
        action="store_true",
        help="Net'leri epoch icinde serpistir (tek paylasilan ag icin onerilen; F8-03)",
    )
    cs.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    cs.add_argument("--seed", type=int, default=0)
    cs.add_argument("--json", type=Path, default=None)
    cs.add_argument("--quiet", action="store_true")

    return p


def _cmd_label(args: argparse.Namespace) -> int:
    import gnubg_er  # noqa: PLC0415
    import gnubg_hint  # noqa: PLC0415

    exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()
    positions = generate_positions(
        args.positions, seed=args.seed, max_plies=args.max_plies
    )
    if not positions:
        print("[hata] pozisyon uretilemedi", file=sys.stderr)
        return 2

    referee = gnubg_hint.HintReferee(exe, plies=args.plies, timeout=args.timeout)
    started = time.time()

    def progress(i: int, total: int, item: LabeledPosition | None) -> None:
        if args.quiet:
            return
        if i % 25 == 0 or i == total:
            print("[%d/%d] %.1f s" % (i, total, time.time() - started), file=sys.stderr)

    labeled, skipped = label_positions(referee, positions, progress=progress)
    meta = {
        "plies": int(args.plies),
        "seed": int(args.seed),
        "maxPlies": int(args.max_plies),
        "requested": int(args.positions),
        "labeled": len(labeled),
        "skipped": len(skipped),
        "elapsedSeconds": round(time.time() - started, 2),
        "gnubg": str(exe),
        "license": LICENSE_NOTE,
    }
    dataset = build_dataset(labeled, meta=meta)
    save_dataset(dataset, args.out)
    if not args.quiet:
        print("etiketlendi=%d atlandi=%d -> %s" % (len(labeled), len(skipped), args.out))
    return 0 if labeled else 1


def _cmd_train(args: argparse.Namespace) -> int:
    import torch  # noqa: PLC0415
    from model import CAPACITY_PROFILES, DEFAULT_PROFILE, VECTOR_SIZE, build_model  # noqa: PLC0415

    if not Path(args.data).is_file():
        print("[hata] veri kumesi yok: " + str(args.data), file=sys.stderr)
        return 2
    if not Path(args.ckpt).is_file():
        print("[hata] checkpoint yok: " + str(args.ckpt), file=sys.stderr)
        return 2
    dataset = load_dataset(args.data)
    if len(dataset) == 0:
        print("[hata] veri kumesi bos", file=sys.stderr)
        return 2

    state = torch.load(str(args.ckpt), map_location=args.device, weights_only=False)
    profile = state.get("profile") or DEFAULT_PROFILE
    if profile not in CAPACITY_PROFILES:
        print("[hata] bilinmeyen profil: " + repr(profile), file=sys.stderr)
        return 2
    h1, h2 = CAPACITY_PROFILES[profile][:2]
    model = build_model(VECTOR_SIZE, h1, h2, seed=0, output_version=2, profile=profile)
    model.load_state_dict(state["model"])

    def progress(step: int, total: int, loss: float) -> None:
        if args.quiet:
            return
        if step % 200 == 0 or step == total:
            print("[%d/%d] mse=%.6f" % (step, total, loss), file=sys.stderr)

    report = train_value_head(
        model,
        dataset,
        steps=args.steps,
        lr=args.lr,
        batch=args.batch,
        device=args.device,
        seed=args.seed,
        progress=progress,
    )

    out_state = dict(state)
    out_state["model"] = model.state_dict()
    out_state["profile"] = profile
    out_state["gnubgDistill"] = {k: v for k, v in report.items() if k != "history"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out_state, str(args.out))

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    if not args.quiet:
        print(
            "mse=%.6f mae=%.4f corr=%.4f egim=%.4f -> %s"
            % (
                report["finalMse"],
                report["finalMae"],
                report["correlation"],
                report["slope"],
                args.out,
            )
        )
    return 0


def _cmd_verdict(args: argparse.Namespace) -> int:
    paired: dict[str, Any] | None = None
    if (
        args.er_before_json is not None
        and args.er_after_json is not None
        and Path(args.er_before_json).is_file()
        and Path(args.er_after_json).is_file()
    ):
        paired = paired_er_test(
            load_er_losses(args.er_before_json), load_er_losses(args.er_after_json)
        )
    verdict = distill_verdict(
        args.before,
        args.after,
        target=args.target,
        min_gain=args.min_gain,
        paired=paired,
        required_n=args.required_n,
    )
    report: dict[str, Any] = {
        "verdict": verdict,
        "erBefore": float(args.before),
        "erAfter": float(args.after),
        "target": float(args.target),
        "minGain": float(args.min_gain),
        "skipped": int(args.skipped),
        "license": LICENSE_NOTE,
    }
    if args.dataset is not None and Path(args.dataset).is_file():
        report["dataset"] = load_policy_dataset(args.dataset).stats()
    if args.value_json is not None and Path(args.value_json).is_file():
        report["value"] = json.loads(Path(args.value_json).read_text(encoding="utf-8"))
    if args.value_er is not None:
        report.setdefault("value", {})["er"] = float(args.value_er)
    if args.policy_json is not None and Path(args.policy_json).is_file():
        report["policy"] = json.loads(Path(args.policy_json).read_text(encoding="utf-8"))
    if paired is not None:
        report["paired"] = paired
    arms: list[dict[str, Any]] = []
    for spec in args.arm or []:
        try:
            label, path = parse_arm(spec)
        except ValueError as exc:
            print("[hata] " + str(exc), file=sys.stderr)
            return 2
        if not path.is_file():
            continue
        losses = load_er_losses(path)
        if not losses:
            continue
        arm: dict[str, Any] = {
            "label": label,
            "positions": len(losses),
            "er": sum(losses.values()) / len(losses),
        }
        if args.er_before_json is not None and Path(args.er_before_json).is_file():
            arm["pairedVsBefore"] = paired_loss_test(
                load_er_losses(args.er_before_json), losses
            )
        arms.append(arm)
    if arms:
        report["arms"] = arms
    report["notes"] = _verdict_notes(report)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")
    if not args.quiet:
        print("karar: %s" % verdict)
        print(VERDICT_TEXT[verdict])
    if verdict == VERDICT_UNKNOWN:
        return 3
    if verdict == VERDICT_UNPROVEN:
        return 4
    if verdict == VERDICT_INSUFFICIENT_DATA:
        return 5
    return 0


def _verdict_notes(report: dict[str, Any]) -> list[str]:
    """Rapora yazilan durustluk notlari (sabit metin, olcume gore secilir)."""
    notes: list[str] = []
    policy = report.get("policy") or {}
    if policy.get("top1") is not None and float(policy["top1"]) >= 0.999:
        notes.append(
            "Egitim top-1 %.4f **ezberdir**, genelleme degil: veri kumesi `medium`"
            " profilin kapasitesinin altinda. Gercek olcu VAL-ER'dir."
            % float(policy["top1"])
        )
    before = report.get("erBefore")
    after = report.get("erAfter")
    paired = report.get("paired") or {}
    if before and after and before > 0.0:
        if paired:
            notes.append(
                "Eslesmis test (n=%d): ortalama fark %+.4f, GA95 [%+.4f; %+.4f],"
                " t=%+.2f. GA sifiri %s."
                % (
                    int(paired.get("n", 0)),
                    float(paired.get("meanDiff", 0.0)),
                    float(paired.get("ciLow", 0.0)),
                    float(paired.get("ciHigh", 0.0)),
                    float(paired.get("t", 0.0)),
                    "**disliyor**" if paired.get("excludesZero") else "**dislamiyor**",
                )
            )
        else:
            notes.append(
                "VAL-ER 70 pozisyonda olculdu; iyilesme %.1f%%. Eslesmis test"
                " yapilmadi, bu yuzden 'GA sifiri icermez' denemez."
                % (100.0 * (before - after) / before)
            )
    notes.append(
        "gnubg GPL'dir: etiketler yalnizca arastirma/olcum icindir, urun"
        " dagitimi oncesi lisans netlestirilmelidir."
    )
    return notes


def _cmd_label_policy(args: argparse.Namespace) -> int:
    import gnubg_er  # noqa: PLC0415
    import gnubg_hint  # noqa: PLC0415

    exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()
    shards = int(getattr(args, "shards", 1) or 1)
    shard_index = int(getattr(args, "shard_index", 0) or 0)
    if shards < 1:
        print("[hata] --shards >= 1 olmali", file=sys.stderr)
        return 2
    if not 0 <= shard_index < shards:
        print("[hata] --shard-index 0..shards-1 araliginda olmali", file=sys.stderr)
        return 2
    # Her dilim ayri bir tohum kullanir: dilimler ayrik pozisyon kumeleri uretir ve
    # birlestirildiklerinde tek kosunun orneklemi kadar gecerli bir orneklem olur.
    seed = int(args.seed) + shard_index
    count = int(args.positions) if shards == 1 else int(math.ceil(args.positions / shards))
    positions = generate_positions(count, seed=seed, max_plies=args.max_plies)
    if not positions:
        print("[hata] pozisyon uretilemedi", file=sys.stderr)
        return 2

    referee = gnubg_hint.HintReferee(exe, plies=args.plies, timeout=args.timeout)
    started = time.time()

    def progress(i: int, total: int, item: PolicyPosition | None) -> None:
        if args.quiet:
            return
        if i % 25 == 0 or i == total:
            print("[%d/%d] %.1f s" % (i, total, time.time() - started), file=sys.stderr)

    labeled, skipped = label_policy_positions(
        referee, positions, dists=args.dists, plies=args.plies, progress=progress
    )
    meta = {
        "kind": "policy",
        "plies": int(args.plies),
        "seed": seed,
        "maxPlies": int(args.max_plies),
        "requested": int(count),
        "labeled": len(labeled),
        "skipped": len(skipped),
        "dists": bool(args.dists),
        "shards": shards,
        "shardIndex": shard_index,
        "elapsedSeconds": round(time.time() - started, 2),
        "gnubg": str(exe),
        "license": LICENSE_NOTE,
    }
    dataset = build_policy_dataset(labeled, meta=meta)
    save_policy_dataset(dataset, args.out)
    if not args.quiet:
        stats = dataset.stats()
        print(
            "etiketlendi=%d atlandi=%d adayOrt=%.1f -> %s"
            % (
                len(labeled),
                len(skipped),
                float(stats.get("candidatesMean", 0.0)),
                args.out,
            )
        )
    return 0 if labeled else 1


def _cmd_merge_policy(args: argparse.Namespace) -> int:
    parts = [load_policy_dataset(p) for p in args.shard]
    if not parts:
        print("[hata] dilim verilmedi", file=sys.stderr)
        return 2
    merged = concat_policy_datasets(parts)
    merged.meta.update(
        {
            "kind": "policy",
            "merged": True,
            "shardFiles": [str(p) for p in args.shard],
            "labeled": int(len(merged)),
            "dists": bool(merged.has_dist()),
            "license": LICENSE_NOTE,
        }
    )
    save_policy_dataset(merged, args.out)
    stats = merged.stats()
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps({"stats": stats, "meta": merged.meta}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if not args.quiet:
        print(
            "birlestirildi=%d aday=%d adayOrt=%.1f dist=%s -> %s"
            % (
                len(merged),
                int(stats.get("candidates", 0)),
                float(stats.get("candidatesMean", 0.0)),
                merged.has_dist(),
                args.out,
            )
        )
    return 0


def _cmd_train_policy(args: argparse.Namespace) -> int:
    import torch  # noqa: PLC0415
    from model import CAPACITY_PROFILES, DEFAULT_PROFILE, VECTOR_SIZE, build_model  # noqa: PLC0415

    if not Path(args.data).is_file():
        print("[hata] veri kumesi yok: " + str(args.data), file=sys.stderr)
        return 2
    if not Path(args.ckpt).is_file():
        print("[hata] checkpoint yok: " + str(args.ckpt), file=sys.stderr)
        return 2
    dataset = load_policy_dataset(args.data)
    if len(dataset) == 0:
        print("[hata] veri kumesi bos", file=sys.stderr)
        return 2

    state = torch.load(str(args.ckpt), map_location=args.device, weights_only=False)
    profile = args.profile or state.get("profile") or DEFAULT_PROFILE
    if profile not in CAPACITY_PROFILES:
        print("[hata] bilinmeyen profil: " + repr(profile), file=sys.stderr)
        return 2
    h1, h2 = CAPACITY_PROFILES[profile][:2]
    rank_weight = float(getattr(args, "rank_weight", 0.0) or 0.0)
    model = build_model(
        VECTOR_SIZE,
        h1,
        h2,
        seed=0,
        output_version=2,
        profile=profile,
        rank_head=rank_weight > 0,
    )
    # Profil ezildiginde (or. medium -> xlarge) agirliklar sekil olarak uyusmaz;
    # o durumda sifirdan baslanir ve bu raporda acikca isaretlenir.
    init_mode = "checkpoint"
    try:
        model.load_state_dict(state["model"])
    except RuntimeError:
        if args.profile is None:
            raise
        init_mode = "scratch"
        print(
            "[bilgi] checkpoint agirliklari %s profiline uymuyor; sifirdan baslaniyor"
            % profile,
            file=sys.stderr,
        )

    def progress(step: int, total: int, loss: float) -> None:
        if args.quiet:
            return
        if step % 200 == 0 or step == total:
            print("[%d/%d] loss=%.6f" % (step, total, loss), file=sys.stderr)

    policy_temperature = float(getattr(args, "policy_temperature", 0.0) or 0.0)
    temperature_report = None
    if getattr(args, "select_temperature", False):
        temperature_report = select_policy_temperature(
            model,
            dataset,
            val_fraction=float(getattr(args, "val_fraction", 0.0) or 0.0) or 0.1,
            seed=args.seed,
            batch=args.batch,
            device=args.device,
        )
        policy_temperature = float(temperature_report["best"])
        if not args.quiet:
            print(
                "[bilgi] secilen T=%g (dogrulama KL=%s)"
                % (
                    policy_temperature,
                    "%.6f" % temperature_report["scores"]["%g" % policy_temperature],
                ),
                file=sys.stderr,
            )

    report = train_policy_head(
        model,
        dataset,
        steps=args.steps,
        lr=args.lr,
        batch=args.batch,
        device=args.device,
        seed=args.seed,
        value_weight=args.value_weight,
        dist_weight=args.dist_weight,
        rank_weight=rank_weight,
        val_fraction=float(getattr(args, "val_fraction", 0.0) or 0.0),
        patience=int(getattr(args, "patience", 0) or 0),
        eval_every=int(getattr(args, "eval_every", 500) or 500),
        weight_decay=float(getattr(args, "weight_decay", 0.0) or 0.0),
        lr_schedule=str(getattr(args, "lr_schedule", "none") or "none"),
        lr_final_ratio=float(getattr(args, "lr_final_ratio", 0.1) or 0.1),
        policy_temperature=policy_temperature,
        progress=progress,
    )
    report["profile"] = profile
    report["initMode"] = init_mode
    if temperature_report is not None:
        report["temperatureSelection"] = temperature_report

    out_state = dict(state)
    out_state["model"] = model.state_dict()
    out_state["profile"] = profile
    out_state["gnubgPolicyDistill"] = {k: v for k, v in report.items() if k != "history"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out_state, str(args.out))

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    if not args.quiet:
        print(
            "profil=%s baslangic=%s loss=%.6f top1=%.4f valTop1=%s adayGenislik=%d -> %s"
            % (
                profile,
                init_mode,
                report["lastLoss"],
                report["top1"],
                "yok" if report["valTop1"] is None else "%.4f" % report["valTop1"],
                report["width"],
                args.out,
            )
        )
    return 0


def _cmd_corpus_sl(args: argparse.Namespace) -> int:
    """Korpus SL asamasi (F8-03 / Adim B).

    G2 kurali: ``--init-from`` **zorunlu**dur ve checkpoint profili ile
    ``--profile`` uyusmazsa kosu **reddedilir** (sessiz sifirdan baslangic yok).
    """
    import torch  # noqa: PLC0415
    from model import CAPACITY_PROFILES, DEFAULT_PROFILE, VECTOR_SIZE, build_model  # noqa: PLC0415

    init = Path(args.init_from)
    if not init.is_file():
        print("[hata] warm-start checkpoint yok: " + str(init), file=sys.stderr)
        return 2
    nets = [n.strip() for n in str(args.nets).split(",") if n.strip()]
    if not nets:
        print("[hata] --nets bos", file=sys.stderr)
        return 2
    try:
        datasets, manifest = load_sl_corpus(args.corpus_dir, nets=nets)
    except (FileNotFoundError, ValueError) as exc:
        print("[hata] " + str(exc), file=sys.stderr)
        return 2

    state = torch.load(str(init), map_location=args.device, weights_only=False)
    profile = state.get("profile") or DEFAULT_PROFILE
    if profile not in CAPACITY_PROFILES:
        print("[hata] bilinmeyen profil: " + repr(profile), file=sys.stderr)
        return 2
    h1, h2 = CAPACITY_PROFILES[profile][:2]
    model = build_model(VECTOR_SIZE, h1, h2, seed=0, output_version=2, profile=profile)
    try:
        model.load_state_dict(state["model"])
    except RuntimeError as exc:
        # G2: sifirdan baslangic reddedilir; sekil uyusmazligi sessizce yutulmaz.
        print(
            "[hata] warm-start agirliklari profile uymuyor (%s): %s" % (profile, exc),
            file=sys.stderr,
        )
        return 2

    def progress(net: str, epoch: int, step: int, loss: float) -> None:
        if args.quiet:
            return
        if step % 200 == 0:
            print("[%s e%d %d] loss=%.6f" % (net, epoch, step, loss), file=sys.stderr)

    order = None
    if args.order:
        order = [n.strip() for n in str(args.order).split(",") if n.strip()]
    report = train_corpus_sl(
        model,
        datasets,
        manifest,
        order=order,
        batch=args.batch,
        device=args.device,
        seed=args.seed,
        value_weight=args.value_weight,
        dist_weight=args.dist_weight,
        val_fraction=args.val_fraction,
        patience=args.patience,
        eval_every=args.eval_every,
        weight_decay=args.weight_decay,
        policy_temperature=args.policy_temperature,
        mix=bool(args.mix),
        progress=progress,
    )
    report["profile"] = profile
    report["initMode"] = "checkpoint"
    report["initFrom"] = str(init)
    report["corpusDir"] = str(args.corpus_dir)
    report["manifest"] = manifest

    out_state = dict(state)
    out_state["model"] = model.state_dict()
    out_state["profile"] = profile
    out_state["corpusSl"] = {k: v for k, v in report.items() if k != "manifest"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out_state, str(args.out))

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    if not args.quiet:
        parts = [
            "%s(n=%d,top1=%.4f)" % (n, v["count"], v["top1"])
            for n, v in report["nets"].items()
        ]
        print(
            "profil=%s baslangic=checkpoint netler=%s adim=%d -> %s"
            % (profile, " ".join(parts), report["totalSteps"], args.out)
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "label":
        return _cmd_label(args)
    if args.command == "train":
        return _cmd_train(args)
    if args.command == "verdict":
        return _cmd_verdict(args)
    if args.command == "label-policy":
        return _cmd_label_policy(args)
    if args.command == "merge-policy":
        return _cmd_merge_policy(args)
    if args.command == "train-policy":
        return _cmd_train_policy(args)
    if args.command == "corpus-sl":
        return _cmd_corpus_sl(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
