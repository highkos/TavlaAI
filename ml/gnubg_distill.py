"""Faz 7: gnubg'yi **ogretmen** olarak kullanma (dis inceleme madde 1.3).

Neden bu deney? Inceleme, en buyuk kaldracin kendi aramamizin bilgisini
damitmak degil, **gnubg 2-ply etiketlerini** ogretmen olarak kullanmak
oldugunu one surdu. Mantik basit ve karar verici:

* Etiketlerle ER **0,03'un altina** iniyorsa sorun **pipeline**dir (hedef/kayip
  hatti). Kendi aramamizla urettigimiz hedefler yeterince bilgi tasimiyor.
* Inmiyorsa sorun **kapasite**dir (ag kucuk, veri az). O zaman olcek buyutmek
  dogru kaldractir.

Bu, F7-20'nin (teshis: `pipeline`) dogal devamidir: teshis "pipeline" dedi, bu
deney **hangi** pipeline onariminin ise yaradigini olcer.

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
#: Incelemenin karar esigi: ER bu degerin altina inerse sorun pipeline'dir.
TARGET_ER = 0.03
#: "Isaretli iyilesme" icin gereken en kucuk goreli kazanc. Faz 7-R'den sonra
#: yalnizca **raporlama** amaciyla kullanilir; karar etiketini degistirmez
#: (karar eslesmis GA'ya baglidir, Kural 3).
MIN_GAIN = 0.20

#: Eslesmis fark icin bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
PAIRED_BOOTSTRAP_RESAMPLES = 20000
PAIRED_BOOTSTRAP_SEED = 20261121

#: Karar etiketleri.
VERDICT_PIPELINE = "pipeline"
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "bestIndex": self.best_index,
            "bestEquity": self.best_equity,
            "turn": self.turn,
            "dice": list(self.dice),
            "bestMove": self.best_move,
            "candidates": self.candidates,
            "mappingFailures": self.mapping_failures,
        }


@dataclass
class PolicyDataset:
    """Ragged aday kumesi: ``x`` [M, 221], ``offsets`` [N+1], ``best`` [N]."""

    x: np.ndarray
    offsets: np.ndarray
    best: np.ndarray
    y: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.best.shape[0])

    def candidates(self, i: int) -> np.ndarray:
        return self.x[int(self.offsets[i]) : int(self.offsets[i + 1])]

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
    progress: Callable[[int, int, PolicyPosition | None], None] | None = None,
) -> tuple[list[PolicyPosition], list[dict[str, Any]]]:
    """Pozisyonlari gnubg ``hint`` ile **politika** hedefi olarak etiketler.

    Etiketlenemeyen pozisyon sessizce atlanmaz; ``skipped`` listesine nedeniyle
    yazilir ve cagiran taraf orani raporlar.
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
        vectors = [
            gnubg_er.vectorize(
                a["board"], a["whiteOff"], a["blackOff"], perspective=int(turn)
            )
            for a in case["afterStates"]
        ]
        item = PolicyPosition(
            vectors=vectors,
            best_index=int(best_index),
            best_equity=float(best_hint.equity),
            turn=int(turn),
            dice=tuple(int(d) for d in dice),
            best_move=str(best_hint.move),
            candidates=len(vectors),
            mapping_failures=len(failures),
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
    for p in labeled:
        rows.extend(p.vectors)
        offsets.append(len(rows))
        best.append(int(p.best_index))
        y.append(float(p.best_equity))
    return PolicyDataset(
        x=np.asarray(rows, dtype=np.float32),
        offsets=np.asarray(offsets, dtype=np.int64),
        best=np.asarray(best, dtype=np.int32),
        y=np.asarray(y, dtype=np.float32),
        meta=dict(meta or {}),
    )


def save_policy_dataset(dataset: PolicyDataset, path: Path) -> None:
    """``.npz`` olarak yazar (``x``, ``offsets``, ``best``, ``y``, ``meta``)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        p,
        x=dataset.x,
        offsets=dataset.offsets,
        best=dataset.best,
        y=dataset.y,
        meta=np.asarray(json.dumps(dataset.meta, sort_keys=True)),
    )


def load_policy_dataset(path: Path) -> PolicyDataset:
    """``.npz`` okur."""
    with np.load(Path(path), allow_pickle=False) as data:
        meta: dict[str, Any] = {}
        if "meta" in data:
            raw = data["meta"]
            text = str(raw.item()) if raw.shape == () else str(raw)
            meta = json.loads(text) if text else {}
        return PolicyDataset(
            x=np.asarray(data["x"], dtype=np.float32),
            offsets=np.asarray(data["offsets"], dtype=np.int64),
            best=np.asarray(data["best"], dtype=np.int32),
            y=np.asarray(data["y"], dtype=np.float32),
            meta=meta,
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
    progress: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Politika kafasini gnubg'nin en iyi hamlesine capraz-entropi ile egitir.

    Kayip: ``CE(logits, best) + value_weight * MSE(equity(best), best_equity)``.
    Politika terimi ER'i dogrudan hedefler; deger terimi yalnizca destek olur.
    """
    import torch  # noqa: PLC0415
    import torch.nn.functional as F  # noqa: PLC0415

    if len(dataset) == 0:
        raise ValueError("bos veri kumesi egitilemez")
    if steps <= 0:
        raise ValueError("steps > 0 olmali")

    torch.manual_seed(seed)
    n = len(dataset)
    x, mask, width = _pad_policy(dataset)
    if width <= 0:
        raise ValueError("aday kumesi bos")

    xt = torch.from_numpy(x).to(device)
    mt = torch.from_numpy(mask).to(device)
    bt = torch.from_numpy(np.asarray(dataset.best, dtype=np.int64)).to(device)
    yt = torch.from_numpy(np.asarray(dataset.y, dtype=np.float32)).to(device)

    model.to(device)
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.Adam(params, lr=lr)
    batch = max(1, min(int(batch), n))

    history: list[float] = []
    for step in range(1, steps + 1):
        idx = torch.randint(0, n, (batch,), device=device)
        out = model(xt[idx].reshape(-1, 221))
        probs = out[0].reshape(batch, width, -1)
        logits = out[1].reshape(batch, width).masked_fill(~mt[idx], -1e9)
        ce = F.cross_entropy(logits, bt[idx])
        pick = bt[idx].view(-1, 1, 1).expand(-1, 1, probs.shape[-1])
        best_probs = probs.gather(1, pick).squeeze(1)
        vloss = F.mse_loss(equity_of_probs(best_probs), yt[idx])
        loss = ce + value_weight * vloss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        history.append(float(loss.detach().to("cpu")))
        if progress:
            progress(step, steps, history[-1])

    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for start in range(0, n, 64):
            stop = min(start + 64, n)
            out = model(xt[start:stop].reshape(-1, 221))
            logits = out[1].reshape(stop - start, width).masked_fill(~mt[start:stop], -1e9)
            pred = torch.argmax(logits, dim=1)
            correct += int((pred == bt[start:stop]).sum().to("cpu"))
            total += stop - start

    return {
        "steps": int(steps),
        "batch": int(batch),
        "lr": float(lr),
        "count": n,
        "width": int(width),
        "valueWeight": float(value_weight),
        "firstLoss": history[0] if history else None,
        "lastLoss": history[-1] if history else None,
        "top1": (correct / total) if total else float("nan"),
        "history": history,
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
    hesaplar. Ikincisi zorunludur: "pipeline" iddiasi "ER hedefin altinda"
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
    * ``paired["ciHighAfter"] <= target`` -> ``pipeline``: ER'nin **GA ust
      siniri** hedefin altinda, yani etiketler sorunu cozdu.
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
            return VERDICT_PIPELINE
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
    VERDICT_PIPELINE: (
        "Etiketler sorunu cozdu: ER hedefin altina indi. Dar bogaz **pipeline**"
        "di (hedef/kayip hatti), kapasite degil. Kendi aramamizin urettigi "
        "hedefler yeterli bilgi tasimiyordu."
    ),
    VERDICT_PARTIAL: (
        "Anlamli iyilesme var ama ER hedefin uzerinde. Hem **pipeline** hem "
        "**kapasite** payi var: once etiket hattini (gnubg ogretmen) kalici hale "
        "getirin, sonra olcek buyutun."
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
    lp.add_argument("--quiet", action="store_true")

    tp = sub.add_parser("train-policy", help="politika kafasini gnubg hamlesine egit")
    tp.add_argument("--data", type=Path, required=True)
    tp.add_argument("--ckpt", type=Path, required=True)
    tp.add_argument("--out", type=Path, required=True)
    tp.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    tp.add_argument("--lr", type=float, default=DEFAULT_LR)
    tp.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    tp.add_argument("--value-weight", type=float, default=DEFAULT_VALUE_WEIGHT)
    tp.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    tp.add_argument("--seed", type=int, default=0)
    tp.add_argument("--json", type=Path, default=None)
    tp.add_argument("--quiet", action="store_true")

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
    positions = generate_positions(
        args.positions, seed=args.seed, max_plies=args.max_plies
    )
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

    labeled, skipped = label_policy_positions(referee, positions, progress=progress)
    meta = {
        "kind": "policy",
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
            print("[%d/%d] loss=%.6f" % (step, total, loss), file=sys.stderr)

    report = train_policy_head(
        model,
        dataset,
        steps=args.steps,
        lr=args.lr,
        batch=args.batch,
        device=args.device,
        seed=args.seed,
        value_weight=args.value_weight,
        progress=progress,
    )

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
            "loss=%.6f top1=%.4f adayGenislik=%d -> %s"
            % (report["lastLoss"], report["top1"], report["width"], args.out)
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
    if args.command == "train-policy":
        return _cmd_train_policy(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
