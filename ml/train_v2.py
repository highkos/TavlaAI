"""Faz 6 Bolum 8: Asama D — olcekli egitim dongusu (6 cikti li deger kafasi).

Faz 4 ``ml/train.py`` **skaler** deger kafasi icin yazilmisti. Faz 6'nin 6 cikti li
dislayici kafasi (``output_version = 2``) farkli bir hedef ve kayip yolu gerektirir:

    hedef : 6 sinifli dislayici dagilim (``ml/targets.py`` + bu moduldeki vektor TD)
    kayip : ``L = c_value*CE + c_policy*L_policy + c_cal*L_cal`` (``ml/losses.py``)

Bu modul Faz 4 dongusunun yerini **almaz**; paralel yasar. Faz 4/5 testleri ve
``ml/train.py`` degismez.

Vektor TD(lambda) [F6-17]
-------------------------
Faz 4'un skaler zinciri ``y[t] = -((1-lam)*V[t+1] + lam*y[t+1])`` idi. 6 sinifli
kafada isaret cevirme yerine **sinif yarilarini takas** eden bir ``flip`` vardir::

    flip([W, GW, BW, L, GL, BL]) = [L, GL, BL, W, GW, BW]

``flip`` bir involusyondur (``flip(flip(p)) == p``) ve skaler negasyonun dagilim
karsiligidir. ``lam = 1.0`` secildiginde zincir ``flip``'in tekrari olur ve
``flip^2 = id`` oldugu icin sonuc **tam olarak** oyuncunun bakis acisindan tek-sicak
Monte Carlo hedefine esitlenir (``ml/tests/test_stage_d.py`` bunu dogrular).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import yaml

import calibration
import er_harness
import gnubg_er
from equity import EQUITY_WEIGHTS, PROB_COUNT, PROB_ORDER, equity_from_exclusive
from export_onnx import export
from losses import (
    DEFAULT_C_CAL,
    DEFAULT_C_POLICY,
    DEFAULT_C_VALUE,
    calibration_loss,
    policy_loss_torch,
    total_loss_v2,
    value_loss_ce_6class,
)
from model import CAPACITY_PROFILES, DEFAULT_PROFILE, build_model, parameter_count
from critical import (
    CRITICAL_BOOST,
    CriticalError,
    build_report as build_critical_report,
    critical_mask_policy,
    critical_mask_value,
    critical_mask_value_margin,
    best_equity,
    decision_margin,
    sampling_weights as critical_sampling_weights,
)
from replay import (
    VALUE_TARGET_SEARCH_DISTILL,
    VALUE_TARGET_TD_LAMBDA,
    PolicySample,
    ReplayBuffer,
    build_policy_samples,
    filter_informative,
    non_terminal_vectors,
    target_entropy_ratio,
    uniform_policy_baseline,
)
from targets import DEFAULT_LAMBDA, exclusive_target, validate_result

VECTOR_SIZE = 221

#: ``flip`` permutasyonu: kazanan yarisini kaybeden yarisina cevirir.
FLIP_INDEX = np.array([3, 4, 5, 0, 1, 2], dtype=np.int64)

#: Equity agirliklari (``ml/equity.py`` ile ayni).
EQUITY_WEIGHTS_F32 = np.asarray(EQUITY_WEIGHTS, dtype=np.float32)

#: ``metrics.jsonl`` surum etiketi (alan kumesi degisirse artar).
METRICS_SCHEMA = 1


# ----------------------------------------------------------------------
# Vektor TD(lambda)
# ----------------------------------------------------------------------


def flip_exclusive(probs) -> np.ndarray:
    """``[W, GW, BW, L, GL, BL]`` -> ``[L, GL, BL, W, GW, BW]`` (involusyon)."""
    p = np.asarray(probs, dtype=np.float64)
    if p.shape[-1] != PROB_COUNT:
        raise ValueError(f"son eksen {PROB_COUNT} olmali: {p.shape}")
    return p[..., FLIP_INDEX]


def td_lambda_targets_exclusive(
    probs_hat,
    terminal: np.ndarray,
    lam: float = DEFAULT_LAMBDA,
) -> np.ndarray:
    """``t = 0..T-2`` icin 6 sinifli dislayici lambda-return hedefleri.

    Args:
        probs_hat: ``[T-1, 6]``; ``t`` kararindan **sonraki** afterstate'in tahmini
            (yani ``p_hat[t]`` = ``t`` kararinin sectigi afterstate dagilimi).
        terminal: ``[6]``; oyun sonucunun **kazanan** bakis acisindan tek-sicak hedefi.
        lam: ``[0, 1]``. ``1.0`` -> saf Monte Carlo.

    Returns:
        ``[T-1, 6]``; her satir o karari veren oyuncunun bakis acisindan.
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lam [0,1] araliginda olmali")

    p = np.asarray(probs_hat, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != PROB_COUNT:
        raise ValueError(f"probs_hat [N,{PROB_COUNT}] olmali: {p.shape}")
    n = p.shape[0]
    if n == 0:
        return np.zeros((0, PROB_COUNT), dtype=np.float64)

    z = np.asarray(terminal, dtype=np.float64).reshape(-1)
    if z.shape[0] != PROB_COUNT:
        raise ValueError(f"terminal {PROB_COUNT} elemanli olmali: {z.shape}")

    y = np.empty((n, PROB_COUNT), dtype=np.float64)
    y[n - 1] = flip_exclusive(z)
    for t in range(n - 2, -1, -1):
        y[t] = flip_exclusive((1.0 - lam) * p[t + 1] + lam * y[t + 1])
    return y


# ----------------------------------------------------------------------
# Ornekler
# ----------------------------------------------------------------------


@dataclass
class ExclusiveSamples:
    """6 sinifli deger egitimi icin duzlestirilmis ornekler."""

    x: np.ndarray  # (N, 221) float32
    y: np.ndarray  # (N, 6) float32
    game_index: np.ndarray  # (N,) int32
    decision_index: np.ndarray  # (N,) int32
    #: F7-08: ornegin uretildigi kararda en iyi iki aday arasindaki equity farki.
    #: ``q`` yoksa ``NaN``. Deger kafasinin kritiklik olcutu budur.
    margin: np.ndarray | None = None  # (N,) float64
    #: F7-08: ayni karardaki **arama degeri** (``max(q)``). Bolum 5.3'un
    #: ``|equity|`` bacagi bunun uzerinden uygulanir; hedef equity uzerinden
    #: uygulanirsa para oyununda dejenere olur.
    best_equity: np.ndarray | None = None  # (N,) float64
    #: F7-17: ``search_distill`` modunda **skaler** deger hedefi (arama kok
    #: equity'si, shard'in ``searchValue`` alani). Dolu ise deger kafasi 6
    #: sinifli CE yerine **equity regresyonu** ile egitilir; ``y`` yalnizca
    #: teshis/olcum icin TD(lambda) referansi olarak kalir.
    equity_target: np.ndarray | None = None  # (N,) float32

    def __len__(self) -> int:
        return int(self.x.shape[0])

    @property
    def equity(self) -> np.ndarray:
        return equity_from_exclusive(self.y).astype(np.float32)


def _empty_samples() -> ExclusiveSamples:
    return ExclusiveSamples(
        x=np.zeros((0, VECTOR_SIZE), dtype=np.float32),
        y=np.zeros((0, PROB_COUNT), dtype=np.float32),
        game_index=np.zeros((0,), dtype=np.int32),
        decision_index=np.zeros((0,), dtype=np.int32),
    )


def predict_probs(model, x: np.ndarray, device, batch_size: int = 4096) -> np.ndarray:
    """``model(x)`` -> ``[N, 6]`` dislayici olasiliklar (no-grad)."""
    out = np.empty((x.shape[0], PROB_COUNT), dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            stop = min(start + batch_size, x.shape[0])
            t = torch.from_numpy(x[start:stop]).to(device)
            probs, _ = model(t)
            out[start:stop] = probs.detach().to("cpu").numpy()
    return out


def _decision_margin_or_nan(q: Any) -> float:
    """Shard kararinin aday equity'lerinden marj (``q`` yoksa ``NaN``)."""
    if q is None:
        return float("nan")
    try:
        return float(decision_margin(q))
    except CriticalError:
        return float("nan")


def _best_equity_or_nan(q: Any) -> float:
    """Shard kararinin aday equity'lerinden en iyisi (``q`` yoksa ``NaN``)."""
    if q is None:
        return float("nan")
    try:
        return float(best_equity(q))
    except CriticalError:
        return float("nan")


def build_exclusive_samples(
    model,
    games: Sequence[Any],
    *,
    lam: float = DEFAULT_LAMBDA,
    device=None,
    batch_size: int = 4096,
    target_mode: str = VALUE_TARGET_TD_LAMBDA,
) -> ExclusiveSamples:
    """Buffer'daki oyunlar icin 6 sinifli hedefleri **mevcut agla** kurar.

    Zincir tum kararlar uzerinden kurulur (rakip kararlar dahil); kayba yalnizca
    ``IsLearner`` kararlar girer (Faz 4 Bolum 6.2 kurali korunur).

    ``target_mode = "search_distill"`` (Faz 7 Bolum 5.4 / Test 102) iken ek olarak
    ``equity_target`` doldurulur: shard'in ``searchValue`` alani, yani ogretmen
    aramasinin kok equity'si. Shard bicimi degismedigi icin 6 sinifli dagilim
    tasinmaz; deger kafasi bu modda **equity regresyonu** ile egitilir (F7-17).
    ``y`` yine TD(lambda) referansi olarak hesaplanir (teshis/olcum icin).
    """
    if target_mode not in (VALUE_TARGET_TD_LAMBDA, VALUE_TARGET_SEARCH_DISTILL):
        raise ValueError(f"bilinmeyen value_target_mode: {target_mode!r}")
    from replay import is_usable_game
    from shards import DEC_CHOSEN_IS_TERMINAL, DEC_IS_LEARNER

    usable = [g for g in games if is_usable_game(g)]
    if not usable:
        return _empty_samples()

    per_game: list[np.ndarray] = []
    offsets: list[int] = []
    total = 0
    for g in usable:
        vecs = non_terminal_vectors(g)
        if vecs is None:
            per_game.append(np.zeros((0, VECTOR_SIZE), dtype=np.float32))
        else:
            per_game.append(vecs)
        offsets.append(total)
        total += per_game[-1].shape[0]

    if total == 0:
        return _empty_samples()

    flat = np.concatenate([v for v in per_game if v.shape[0] > 0], axis=0)
    # ``lam = 1`` saf Monte Carlo'dur: zincir ``p_hat``'a hic dokunmaz, dolayisiyla
    # ileri gecis atlanir ve hedefler agdan bagimsiz olur (sabit MC probe).
    if lam >= 1.0:
        p_hat_all = np.zeros((flat.shape[0], PROB_COUNT), dtype=np.float32)
    else:
        p_hat_all = predict_probs(model, flat, device, batch_size=batch_size)

    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    gi: list[int] = []
    di: list[int] = []
    mg: list[float] = []
    be: list[float] = []
    et: list[float] = []

    for k, g in enumerate(usable):
        vecs = per_game[k]
        n_hat = vecs.shape[0]
        if n_hat < 1:
            continue
        validate_result(g.winner, g.result_type)
        base = offsets[k]
        p_hat = p_hat_all[base:base + n_hat]
        terminal = exclusive_target(g.winner, g.result_type, g.winner)
        targets = td_lambda_targets_exclusive(p_hat, terminal, lam)

        for t in range(n_hat):
            d = g.decisions[t]
            if not (d.flags & DEC_IS_LEARNER):
                continue
            if d.flags & DEC_CHOSEN_IS_TERMINAL:
                continue
            if not np.all(np.isfinite(targets[t])):
                continue
            xs.append(vecs[t])
            ys.append(targets[t])
            gi.append(k)
            di.append(t)
            mg.append(_decision_margin_or_nan(d.q))
            be.append(_best_equity_or_nan(d.q))
            if target_mode == VALUE_TARGET_SEARCH_DISTILL:
                et.append(float(d.search_value))

    if not xs:
        return _empty_samples()

    return ExclusiveSamples(
        x=np.stack(xs, axis=0).astype(np.float32, copy=False),
        y=np.stack(ys, axis=0).astype(np.float32, copy=False),
        game_index=np.asarray(gi, dtype=np.int32),
        decision_index=np.asarray(di, dtype=np.int32),
        margin=np.asarray(mg, dtype=np.float64),
        best_equity=np.asarray(be, dtype=np.float64),
        equity_target=(
            np.asarray(et, dtype=np.float32)
            if target_mode == VALUE_TARGET_SEARCH_DISTILL
            else None
        ),
    )


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


def evaluate_exclusive(model, samples: ExclusiveSamples, device) -> dict[str, float]:
    """Sabit bir kume uzerinde CE, equity MAE ve kalibrasyon egimi."""
    if len(samples) == 0:
        return {
            "ce": float("nan"),
            "equity_mae": float("nan"),
            "calibration_slope": float("nan"),
            "calibration_intercept": float("nan"),
        }
    probs = predict_probs(model, samples.x, device)
    p = np.clip(probs.astype(np.float64), 1e-30, 1.0)
    ce = float(-np.mean(np.sum(samples.y.astype(np.float64) * np.log(p), axis=-1)))
    pred_eq = equity_from_exclusive(probs)
    tgt_eq = samples.equity.astype(np.float64)
    if pred_eq.size < 2:
        return {
            "ce": ce,
            "equity_mae": float(np.mean(np.abs(pred_eq - tgt_eq))),
            "calibration_slope": float("nan"),
            "calibration_intercept": float("nan"),
        }
    metrics = calibration.calibration_metrics(pred_eq, tgt_eq)
    return {
        "ce": ce,
        "equity_mae": float(metrics.get("mae", float("nan"))),
        "calibration_slope": float(metrics.get("slope", float("nan"))),
        "calibration_intercept": float(metrics.get("intercept", float("nan"))),
    }


def evaluate_policy(
    model,
    samples: Sequence[PolicySample],
    device,
    *,
    groups_per_batch: int = 512,
) -> tuple[float, int]:
    """Politika kaybi (grup softmax). Kararlar toplu olarak ileri gecirilir."""
    usable = [s for s in samples if s.vectors.shape[0] >= 2]
    if not usable:
        return float("nan"), 0
    total = 0.0
    used = 0
    model.eval()
    with torch.no_grad():
        for start in range(0, len(usable), groups_per_batch):
            chunk = usable[start:start + groups_per_batch]
            vecs = np.concatenate([s.vectors for s in chunk], axis=0)
            tgt = np.concatenate([s.target for s in chunk], axis=0)
            sizes = [int(s.vectors.shape[0]) for s in chunk]
            x = torch.from_numpy(vecs).to(device)
            _, lg = model(x)
            lg = lg.reshape(-1)
            t = torch.from_numpy(tgt).to(device)
            total += float(policy_loss_torch(lg, t, sizes, min_group=2)) * len(chunk)
            used += len(chunk)
    if used == 0:
        return float("nan"), 0
    return total / used, used


# ----------------------------------------------------------------------
# Egitim adimlari
# ----------------------------------------------------------------------


@dataclass
class StepStats:
    value_loss: list[float] = field(default_factory=list)
    policy_loss: list[float] = field(default_factory=list)
    cal_loss: list[float] = field(default_factory=list)
    grad_norm: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, float]:
        def mean(xs: list[float]) -> float:
            return float(np.mean(xs)) if xs else float("nan")

        def last(xs: list[float]) -> float:
            return float(xs[-1]) if xs else float("nan")

        return {
            "value_loss_mean": mean(self.value_loss),
            "value_loss_last": last(self.value_loss),
            "policy_loss_mean": mean(self.policy_loss),
            "policy_loss_last": last(self.policy_loss),
            "cal_loss_mean": mean(self.cal_loss),
            "cal_loss_last": last(self.cal_loss),
            "grad_norm_mean": mean(self.grad_norm),
            "grad_norm_max": float(np.max(self.grad_norm)) if self.grad_norm else float("nan"),
        }


def _autocast(device, enabled: bool):
    if not enabled:
        return torch.autocast(device_type="cpu", enabled=False)
    if device.type == "cuda":
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    return torch.autocast(device_type="cpu", dtype=torch.bfloat16)


def train_steps_v2(
    model,
    optimizer,
    value_samples: ExclusiveSamples,
    policy_samples: Sequence[PolicySample],
    *,
    steps: int,
    value_batch: int,
    policy_batch: int,
    c_value: float,
    c_policy: float,
    c_cal: float,
    clip_grad_norm: float,
    device,
    rng: np.random.Generator,
    amp: bool = False,
    scaler=None,
    value_weights: np.ndarray | None = None,
    policy_weights: np.ndarray | None = None,
) -> StepStats:
    stats = StepStats()
    if steps <= 0:
        return stats

    n_value = len(value_samples)
    n_policy = len(policy_samples)
    weights = torch.from_numpy(EQUITY_WEIGHTS_F32).to(device)

    # Faz 7 Bolum 5.3 / Test 98: kritik karar ornekleme agirligi. Agirlik
    # verilmezse eski davranis (tekduze) korunur.
    if value_weights is not None:
        value_weights = np.asarray(value_weights, dtype=np.float64).reshape(-1)
        if value_weights.size != n_value:
            raise ValueError("value_weights uzunlugu ornek sayisina esit olmali")
    if policy_weights is not None:
        policy_weights = np.asarray(policy_weights, dtype=np.float64).reshape(-1)
        if policy_weights.size != n_policy:
            raise ValueError("policy_weights uzunlugu ornek sayisina esit olmali")

    model.train()
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)

        with _autocast(device, amp):
            if n_value > 0:
                k = min(value_batch, n_value)
                if value_weights is None:
                    idx = rng.integers(0, n_value, size=k)
                else:
                    idx = rng.choice(n_value, size=k, p=value_weights)
                x = torch.from_numpy(value_samples.x[idx]).to(device)
                y = torch.from_numpy(value_samples.y[idx]).to(device)
                probs, _ = model(x)
                if value_samples.equity_target is not None:
                    # F7-17: damitma modunda hedef 6 sinifli dagilim degil, ogretmen
                    # aramasinin kok equity'sidir. Deger kafasi equity regresyonu ile
                    # egitilir; kalibrasyon terimi ayni buyuklugu iki kez saymamak
                    # icin kapatilir.
                    et = torch.from_numpy(value_samples.equity_target[idx]).to(device)
                    lv = torch.mean((probs @ weights - et) ** 2)
                    lcal = torch.zeros((), device=device)
                else:
                    lv = value_loss_ce_6class(probs, y)
                    lcal = calibration_loss(probs @ weights, y @ weights)
            else:
                lv = torch.zeros((), device=device)
                lcal = torch.zeros((), device=device)

            if n_policy > 0:
                k = min(policy_batch, n_policy)
                if policy_weights is None:
                    pidx = rng.integers(0, n_policy, size=k)
                else:
                    pidx = rng.choice(n_policy, size=k, p=policy_weights)
                batch = [policy_samples[int(i)] for i in pidx]
                vecs = np.concatenate([b.vectors for b in batch], axis=0)
                tgt = np.concatenate([b.target for b in batch], axis=0)
                sizes = [int(b.vectors.shape[0]) for b in batch]
                xt = torch.from_numpy(vecs).to(device)
                _, lg = model(xt)
                lg = lg.reshape(-1)
                tt = torch.from_numpy(tgt).to(device)
                lp = policy_loss_torch(lg, tt, sizes, min_group=2)
            else:
                lp = torch.zeros((), device=device)

            loss = total_loss_v2(lv, lp, lcal, c_value, c_policy, c_cal)

        if scaler is not None and scaler.is_enabled():
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            gn = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            gn = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad_norm)
            optimizer.step()

        stats.value_loss.append(float(lv.detach()))
        stats.policy_loss.append(float(lp.detach()))
        stats.cal_loss.append(float(lcal.detach()))
        stats.grad_norm.append(float(gn))

    model.eval()
    return stats


# ----------------------------------------------------------------------
# Self-play
# ----------------------------------------------------------------------


def run_selfplay(
    cfg: dict,
    onnx_path: Path,
    shard_dir: Path,
    *,
    prefix: str,
    seed: int,
    games: int,
    depth: int,
    log_top: int,
    extra_args: Sequence[str] = (),
) -> str:
    """``Backgammon.SelfPlay`` surucusunu cagirir (Faz 4 sarmalayicisiyla ayni)."""
    from train import run_selfplay as _run_selfplay

    return _run_selfplay(
        cfg,
        onnx_path,
        shard_dir,
        prefix=prefix,
        seed=seed,
        games=games,
        depth=depth,
        log_top=log_top,
        extra_args=extra_args,
    )


# ----------------------------------------------------------------------
# VAL-ER / TEST-ER
# ----------------------------------------------------------------------


def _corpus_cases(split: str, limit: int) -> list[dict[str, Any]]:
    corpus = er_harness.load_corpus()
    cases = er_harness.select_cases(corpus, split)
    if limit > 0:
        cases = cases[:limit]
    return cases


def measure_er(
    onnx_path: Path,
    *,
    split: str,
    limit: int,
    plies: int,
    gnubg: Path,
) -> dict[str, Any]:
    """Bir bolunmenin ER olcumunu yapar (gnubg referansli)."""
    cases = _corpus_cases(split, limit)
    if not cases:
        return {"split": split, "count": 0, "mean": float("nan")}
    measurement, _results = er_harness.measure_split(
        onnx_path,
        cases,
        split=split,
        gnubg=gnubg,
        plies=plies,
        progress=False,
    )
    return measurement.to_dict()


def append_test_access(
    log_path: Path,
    *,
    model_version: int,
    iteration: int,
    measurement: dict[str, Any],
) -> dict[str, Any]:
    """TEST-ER erisimini ``test_access.log``'a yazar (Faz 6 Bolum 6.4).

    Ilk erisim ``primary``, sonrakiler ``exploratory`` olarak etiketlenir; ikinci
    etiket raporda "kesifsel" olarak isaretlenir.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    previous = 0
    if log_path.is_file():
        previous = sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip())
    label = "primary" if previous == 0 else "exploratory"
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_version": int(model_version),
        "iteration": int(iteration),
        "split": "test",
        "count": int(measurement.get("count", 0)),
        "er": measurement.get("mean"),
        "label": label,
        "access_index": previous + 1,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


# ----------------------------------------------------------------------
# Yardimcilar
# ----------------------------------------------------------------------


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml bir sozluk olmali")
    return cfg


def _get(cfg: dict, section: str, key: str, default: Any) -> Any:
    sec = cfg.get(section) or {}
    return sec.get(key, default)


def _finite(value: Any) -> Any:
    """``metrics.jsonl`` icin NaN/Inf -> ``None`` (gecerli JSON, deterministik)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    return {k: _finite(v) for k, v in record.items()}


def _write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(_clean(record), sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


# ----------------------------------------------------------------------
# Sabit probe kumesi (ogrenme egrisi)
# ----------------------------------------------------------------------


def subsample_value(samples: ExclusiveSamples, n: int, rng: np.random.Generator) -> ExclusiveSamples:
    """Sabit boyutlu, deterministik alt ornek (probe kumesi)."""
    if n <= 0 or len(samples) <= n:
        return samples
    idx = np.sort(rng.choice(len(samples), size=n, replace=False))
    return ExclusiveSamples(
        x=samples.x[idx],
        y=samples.y[idx],
        game_index=samples.game_index[idx],
        decision_index=samples.decision_index[idx],
        margin=None if samples.margin is None else samples.margin[idx],
        best_equity=None if samples.best_equity is None else samples.best_equity[idx],
    )


def subsample_policy(
    samples: Sequence[PolicySample], n: int, rng: np.random.Generator
) -> list[PolicySample]:
    if n <= 0 or len(samples) <= n:
        return list(samples)
    idx = np.sort(rng.choice(len(samples), size=n, replace=False))
    return [samples[int(i)] for i in idx]


# ----------------------------------------------------------------------
# R-D: perspektif artirimi (F7-94)
# ----------------------------------------------------------------------


def _flip_vectors(vectors: np.ndarray) -> np.ndarray:
    """Her satiri **karsi bakisa** cevirir (``antisymmetry.flip_perspective``)."""
    from antisymmetry import flip_perspective

    arr = np.asarray(vectors, dtype=np.float32)
    out = np.empty_like(arr)
    for i in range(arr.shape[0]):
        out[i] = np.asarray(flip_perspective(arr[i]), dtype=np.float32)
    return out


def augment_value_samples(samples: ExclusiveSamples) -> ExclusiveSamples:
    """Deger orneklerini **iki** perspektifle cogaltir (R-D, F7-94).

    Ayni fiziksel pozisyon ikinci kez, karsi bakistan yazilmis vektorle ve
    **ters** hedefle girer:

    * ``x``             -> ``flip_perspective(x)``
    * ``y``             -> ``flip_exclusive(y)`` (``W`` yarisi ``L`` yarisina doner)
    * ``equity_target`` -> isaret doner
    * ``best_equity``   -> isaret doner
    * ``margin``        -> **degismez**: ayni fiziksel aday kumesinin en iyi iki
      adayi arasindaki fark, bakistan bagimsiz bir buyukluktur.

    Donen ornek sayisi ``2 * len(samples)``; ciftler bitisiktir:
    ``[s0(+1), s0(-1), s1(+1), s1(-1), ...]``.

    **Neden gerekli.** Modelin iki bakista tutarli olmasi icin ayni pozisyonun
    iki yazimi da kayba girmelidir; aksi halde ``f(x,+1) = -f(x,-1)`` simetrisi
    hicbir zaman dayatilmaz (F7-55 kusurunun kok nedeni).
    """
    n = len(samples)
    if n == 0:
        return samples

    def _pair(original: np.ndarray, flipped: np.ndarray) -> np.ndarray:
        """``[a0, b0, a1, b1, ...]`` - ciftler bitisik."""
        out = np.empty((2 * n,) + original.shape[1:], dtype=original.dtype)
        out[0::2] = original
        out[1::2] = flipped
        return out

    x = _pair(samples.x, _flip_vectors(samples.x))
    y = _pair(samples.y, flip_exclusive(samples.y).astype(np.float32))
    gi = _pair(samples.game_index, samples.game_index)
    di = _pair(samples.decision_index, samples.decision_index)
    margin = (
        None if samples.margin is None else _pair(samples.margin, samples.margin)
    )
    best = (
        None
        if samples.best_equity is None
        else _pair(samples.best_equity, -samples.best_equity)
    )
    et = (
        None
        if samples.equity_target is None
        else _pair(samples.equity_target, -samples.equity_target).astype(np.float32)
    )
    return ExclusiveSamples(
        x=x,
        y=y,
        game_index=gi,
        decision_index=di,
        margin=margin,
        best_equity=best,
        equity_target=et,
    )


def augment_policy_samples(samples: Sequence[PolicySample]) -> list[PolicySample]:
    """Politika orneklerini iki perspektifle cogaltir (R-D, F7-94).

    Aday kumesi **ayni fiziksel afterstate'lerdir**; yalnizca vektorler karsi
    bakistan yazilir. Bu yuzden hedef dagilim (``target``) ve ``q`` vektor
    olarak degismez.

    **UYARI (F7-100): bu artirim yanlistir, varsayilan kapalidir.** Hedef
    *oynayacak tarafin* dagilimidir; girdi cevrilince oynayacak taraf degisir,
    dolayisiyla hedefin de cevrilmesi gerekir. Shard'larda karsi tarafin hedefi
    yok. Ayni hedefle cevirmek kafayi ``f(flip(x)) = f(x)`` yani **simetrik**
    egitir; renk takasi kapisinin aradigi ``argmax(+1) == argmin(-1)``
    iliskisinin tam tersi. Olculdu: argmax uyumu 0,174 -> 0,018.
    """
    out: list[PolicySample] = []
    for s in samples:
        out.append(s)
        out.append(
            PolicySample(vectors=_flip_vectors(s.vectors), target=s.target, q=s.q)
        )
    return out


def _double_weights(weights: np.ndarray) -> np.ndarray:
    """Kritik ornekleme agirliklarini orneklerle ayni sirada ciftler.

    ``augment_*`` ornekleri ``[s0, f0, s1, f1, ...]`` duzeninde cogaltir; bu
    yuzden agirlik da ``repeat(2)`` ile ciftlenmelidir (``concatenate`` blok
    verip agirliklari kaydirir). Ciftlemeden sonra toplam 2 olur;
    ``rng.choice(p=...)`` toplamin 1 olmasini istedigi icin yeniden
    normalestirilir.
    """
    doubled = np.repeat(np.asarray(weights, dtype=np.float64), 2)
    total = float(doubled.sum())
    if total <= 0.0:
        return np.full(doubled.shape[0], 1.0 / doubled.shape[0], dtype=np.float64)
    return doubled / total


def save_probe(
    path: Path,
    value: ExclusiveSamples,
    policy: Sequence[PolicySample],
    mc: ExclusiveSamples | None = None,
) -> None:
    """Probe kumelerini diske yazar; ``--resume`` ayni egriyi surdurur (Test 72)."""
    arrays: dict[str, np.ndarray] = {
        "x": value.x,
        "y": value.y,
        "gi": value.game_index,
        "di": value.decision_index,
    }
    if value.margin is not None:
        arrays["margin"] = value.margin
    if value.best_equity is not None:
        arrays["best_equity"] = value.best_equity
    if mc is not None:
        arrays["mc_x"] = mc.x
        arrays["mc_y"] = mc.y
        arrays["mc_gi"] = mc.game_index
        arrays["mc_di"] = mc.decision_index
        if mc.margin is not None:
            arrays["mc_margin"] = mc.margin
        if mc.best_equity is not None:
            arrays["mc_best_equity"] = mc.best_equity
    if policy:
        arrays["p_vecs"] = np.concatenate([s.vectors for s in policy], axis=0)
        arrays["p_tgt"] = np.concatenate([s.target for s in policy], axis=0)
        arrays["p_sizes"] = np.asarray([s.vectors.shape[0] for s in policy], dtype=np.int64)
    else:
        arrays["p_vecs"] = np.zeros((0, VECTOR_SIZE), dtype=np.float32)
        arrays["p_tgt"] = np.zeros((0,), dtype=np.float32)
        arrays["p_sizes"] = np.zeros((0,), dtype=np.int64)
    np.savez_compressed(str(path), **arrays)


def load_probe(
    path: Path,
) -> tuple[ExclusiveSamples, list[PolicySample], ExclusiveSamples | None]:
    z = np.load(str(path))
    value = ExclusiveSamples(
        x=z["x"].astype(np.float32, copy=False),
        y=z["y"].astype(np.float32, copy=False),
        game_index=z["gi"].astype(np.int32, copy=False),
        decision_index=z["di"].astype(np.int32, copy=False),
        margin=z["margin"].astype(np.float64, copy=False) if "margin" in z.files else None,
        best_equity=(
            z["best_equity"].astype(np.float64, copy=False)
            if "best_equity" in z.files
            else None
        ),
    )
    mc: ExclusiveSamples | None = None
    if "mc_x" in z.files:
        mc = ExclusiveSamples(
            x=z["mc_x"].astype(np.float32, copy=False),
            y=z["mc_y"].astype(np.float32, copy=False),
            game_index=z["mc_gi"].astype(np.int32, copy=False),
            decision_index=z["mc_di"].astype(np.int32, copy=False),
            margin=z["mc_margin"].astype(np.float64, copy=False) if "mc_margin" in z.files else None,
            best_equity=(
                z["mc_best_equity"].astype(np.float64, copy=False)
                if "mc_best_equity" in z.files
                else None
            ),
        )
    sizes = z["p_sizes"]
    vecs = z["p_vecs"]
    tgt = z["p_tgt"]
    policy: list[PolicySample] = []
    offset = 0
    for raw in sizes:
        size = int(raw)
        policy.append(
            PolicySample(
                vectors=vecs[offset:offset + size],
                target=tgt[offset:offset + size],
                q=np.zeros(size, dtype=np.float32),
            )
        )
        offset += size
    return value, policy, mc


# ----------------------------------------------------------------------
# Karar kurallari (Test 68 / Test 70)
# ----------------------------------------------------------------------

#: Test 68: ``large`` profilinin kalması icin gereken anlamlilik carpani (SE cinsinden).
CAPACITY_MARGIN_SE = 1.0

#: Test 70: AMP'nin kalmasi icin gereken hiz kazanci.
AMP_SPEEDUP_THRESHOLD = 1.10

#: Test 70: AMP'nin kabul edilebilir kayip sapmasi.
AMP_LOSS_TOLERANCE = 0.01


def decide_capacity(
    er_medium: float,
    se_medium: float,
    er_large: float,
    se_large: float,
    *,
    margin_se: float = CAPACITY_MARGIN_SE,
) -> dict[str, Any]:
    """Test 68: ``medium`` vs ``large`` ER farki olculur; kazanc yoksa ``medium`` kalir.

    Esik, iki olcumun standart hatalarinin bileskesidir (``margin_se * hypot``).
    Boylece yalnizca gurultunun uzerindeki kazanc profili degistirir.
    """
    difference = float(er_medium) - float(er_large)
    threshold = float(margin_se) * math.hypot(float(se_medium), float(se_large))
    keep_large = difference > threshold
    return {
        "er_medium": float(er_medium),
        "se_medium": float(se_medium),
        "er_large": float(er_large),
        "se_large": float(se_large),
        "difference": difference,
        "threshold": threshold,
        "selected": "large" if keep_large else "medium",
        "reason": (
            "large, medium'dan esik uzerinde iyi"
            if keep_large
            else "kazanc esigin altinda; medium kalir"
        ),
    }


def decide_amp(
    seconds_fp32: float,
    ce_fp32: float,
    seconds_amp: float,
    ce_amp: float,
    *,
    speedup_threshold: float = AMP_SPEEDUP_THRESHOLD,
    loss_tolerance: float = AMP_LOSS_TOLERANCE,
) -> dict[str, Any]:
    """Test 70: FP32 vs FP16/BF16-AMP; hiz kazanci yoksa FP32 kalir."""
    speedup = float(seconds_fp32) / float(seconds_amp) if seconds_amp > 0 else float("inf")
    loss_delta = abs(float(ce_amp) - float(ce_fp32))
    keep_amp = speedup >= float(speedup_threshold) and loss_delta <= float(loss_tolerance)
    return {
        "seconds_fp32": float(seconds_fp32),
        "seconds_amp": float(seconds_amp),
        "speedup": speedup,
        "ce_fp32": float(ce_fp32),
        "ce_amp": float(ce_amp),
        "loss_delta": loss_delta,
        "speedup_threshold": float(speedup_threshold),
        "loss_tolerance": float(loss_tolerance),
        "selected": "amp" if keep_amp else "fp32",
        "reason": (
            "AMP esikleri geciyor"
            if keep_amp
            else "hiz kazanci veya kayip toleransi saglanmadi; FP32 kalir"
        ),
    }


# ----------------------------------------------------------------------
# Ana dongu
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Faz 6 Asama D: olcekli egitim (6 cikti li kafa)")
    p.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    p.add_argument("--out", default=None, help="calisma dizini")
    p.add_argument("--profile", default=None, choices=sorted(CAPACITY_PROFILES))
    p.add_argument("--iterations", type=int, default=None)
    p.add_argument("--games", type=int, default=None, help="iterasyon basina oyun (G)")
    p.add_argument("--steps", type=int, default=None, help="iterasyon basina egitim adimi (S)")
    p.add_argument("--depth", type=int, default=None)
    p.add_argument("--max-root", type=int, default=None)
    p.add_argument("--max-inner", type=int, default=None)
    p.add_argument("--selfplay-threads", type=int, default=None, help="self-play is parcacik sayisi")
    p.add_argument("--device", default=None, choices=["cpu", "cuda"])
    p.add_argument("--amp", action="store_true", help="FP16/BF16 otomatik karisik duyarlilik")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--lam", type=float, default=None, help="vektor TD(lambda)")
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--c-policy", type=float, default=None)
    p.add_argument("--c-cal", type=float, default=None)
    p.add_argument("--resume", default=None, help="checkpoint .pt yolu")
    p.add_argument(
        "--init-from",
        default=None,
        help="yalniz agirliklari yukle (isinma baslangici); profil ayni olmali",
    )
    p.add_argument("--buffer-games", type=int, default=None, help="replay buffer oyun siniri")
    p.add_argument("--no-selfplay", action="store_true", help="self-play'i atla, mevcut shard'lari kullan")
    p.add_argument("--shard-dir", default=None, help="--no-selfplay icin shard kok dizini")
    p.add_argument("--val-er-every", type=int, default=None, help="kac iterasyonda bir VAL-ER (0 = kapali)")
    p.add_argument("--val-er-cases", type=int, default=None, help="VAL-ER pozisyon siniri (0 = hepsi)")
    p.add_argument("--val-er-plies", type=int, default=None, help="gnubg degerlendirme derinligi")
    p.add_argument("--test-er", action="store_true", help="kosu sonunda TEST-ER (bir kez, loglanir)")
    p.add_argument("--test-er-cases", type=int, default=None)
    p.add_argument("--torch-threads", type=int, default=None, help="0 = dokunma")
    p.add_argument("--probe-size", type=int, default=None, help="sabit probe deger ornegi (0 = hepsi)")
    p.add_argument("--probe-policy-size", type=int, default=None, help="sabit probe politika ornegi")
    p.add_argument(
        "--critical-boost",
        type=float,
        default=None,
        help="Faz 7 Test 98: kritik karar ornekleme agirligi (1.0 = kapali)",
    )
    p.add_argument(
        "--value-target-mode",
        default=None,
        choices=[VALUE_TARGET_TD_LAMBDA, VALUE_TARGET_SEARCH_DISTILL],
        help="deger hedefi: td_lambda (varsayilan) | search_distill (Faz 7 Bolum 5.4)",
    )
    p.add_argument("--no-deterministic", action="store_true", help="deterministik algoritmalari kapat")
    p.add_argument(
        "--augment-perspectives",
        action="store_true",
        help=(
            "R-D: deger orneklerini iki perspektifle egit (F7-94, renk takasi kapisi). "
            "Politika kafasi **artirilmaz**: hedefi oynayacak tarafin dagilimidir ve "
            "girdi cevrilince hedef de cevrilmelidir; shard'larda karsi tarafin hedefi yok."
        ),
    )
    p.add_argument(
        "--augment-policy-perspectives",
        action="store_true",
        help=(
            "TESHIS AMACLI, varsayilan kapali: politika orneklerini de cevirir ama "
            "hedefi ayni birakir. Bu, kafayi **simetrik** egitir; olculdu: renk takasi "
            "argmax uyumu 0,174 -> 0,018 (F7-100). Uretimde kullanilmaz."
        ),
    )
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cfg = load_config(args.config)
    run_cfg = cfg.get("run") or {}
    train_cfg = cfg.get("train") or {}
    model_cfg = cfg.get("model") or {}
    buffer_cfg = cfg.get("buffer") or {}
    sp_cfg = cfg.get("selfplay") or {}

    out_dir = Path(args.out or run_cfg.get("out_dir", "ml/runs/stage_d"))
    if not out_dir.is_absolute():
        out_dir = repo_root() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    iterations = int(args.iterations if args.iterations is not None else run_cfg.get("iterations", 20))
    games = int(args.games if args.games is not None else sp_cfg.get("games", 500))
    steps = int(args.steps if args.steps is not None else train_cfg.get("steps_per_iteration", 200))
    depth = int(args.depth if args.depth is not None else sp_cfg.get("depth", 1))
    if args.max_root is not None:
        cfg.setdefault("selfplay", {})["max_candidates_root"] = int(args.max_root)
    if args.max_inner is not None:
        cfg.setdefault("selfplay", {})["max_candidates_inner"] = int(args.max_inner)
    if args.selfplay_threads is not None:
        cfg.setdefault("selfplay", {})["threads"] = int(args.selfplay_threads)
    seed = int(args.seed if args.seed is not None else run_cfg.get("seed", 1))
    critical_boost = float(
        args.critical_boost
        if args.critical_boost is not None
        else train_cfg.get("critical_boost", CRITICAL_BOOST)
    )
    value_target_mode = str(
        args.value_target_mode
        if args.value_target_mode is not None
        else train_cfg.get("value_target_mode", VALUE_TARGET_TD_LAMBDA)
    )
    if value_target_mode not in (VALUE_TARGET_TD_LAMBDA, VALUE_TARGET_SEARCH_DISTILL):
        raise SystemExit("bilinmeyen value_target_mode: " + value_target_mode)

    val_er_every = int(
        args.val_er_every if args.val_er_every is not None else run_cfg.get("val_er_every", 0)
    )
    val_er_cases = int(
        args.val_er_cases if args.val_er_cases is not None else run_cfg.get("val_er_cases", 0)
    )
    val_er_plies = int(
        args.val_er_plies if args.val_er_plies is not None else run_cfg.get("val_er_plies", 2)
    )
    test_er_cases = int(
        args.test_er_cases if args.test_er_cases is not None else run_cfg.get("test_er_cases", 0)
    )

    device_name = str(args.device or run_cfg.get("device", "cpu"))
    if device_name == "cuda" and not torch.cuda.is_available():
        print("[uyari] CUDA yok, CPU'ya dusuluyor", file=sys.stderr)
        device_name = "cpu"
    device = torch.device(device_name)

    if args.torch_threads is not None and args.torch_threads > 0:
        torch.set_num_threads(int(args.torch_threads))
    # Faz 6 Bolum 8.6: CPU bit duzeyinde deterministik, GPU tolerans icinde. CUDA'da
    # deterministik algoritmalar zorlanmaz (non-deterministik op'lar zaten tolerans
    # ile karsilanir; zorlamak sadece uyari uretir).
    if not args.no_deterministic and device.type == "cpu":
        torch.use_deterministic_algorithms(True, warn_only=True)

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    profile = str(args.profile or model_cfg.get("profile", DEFAULT_PROFILE))
    if profile not in CAPACITY_PROFILES:
        raise ValueError(f"bilinmeyen profil: {profile!r}")
    model = build_model(VECTOR_SIZE, seed=seed, output_version=2, profile=profile).to(device)

    lr = float(args.lr if args.lr is not None else train_cfg.get("lr", 1e-3))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=lr, weight_decay=float(train_cfg.get("weight_decay", 1e-4))
    )

    lam = float(args.lam if args.lam is not None else train_cfg.get("lam", DEFAULT_LAMBDA))
    c_policy = float(args.c_policy if args.c_policy is not None else train_cfg.get("c_policy", DEFAULT_C_POLICY))
    c_cal = float(args.c_cal if args.c_cal is not None else train_cfg.get("c_cal", DEFAULT_C_CAL))
    c_value = float(train_cfg.get("c_value", DEFAULT_C_VALUE))
    tau_train = float(train_cfg.get("tau_train", 0.05))
    clip_grad_norm = float(train_cfg.get("clip_grad_norm", 1.0))
    value_batch = int(train_cfg.get("value_batch", 4096))
    policy_batch = int(train_cfg.get("policy_batch", 256))
    policy_min_sharpness = float(train_cfg.get("policy_min_sharpness", 0.99))
    log_top = int(sp_cfg.get("log_top_candidates", 12))
    dup_cap = int(sp_cfg.get("dup_cap", 3))

    amp = bool(args.amp)
    scaler = None
    if amp and device.type == "cuda":
        scaler = torch.amp.GradScaler("cuda", enabled=True)

    buffer = ReplayBuffer(
        int(args.buffer_games if args.buffer_games is not None else buffer_cfg.get("max_games", 20000))
    )
    buffer_dirs: list[str] = []
    history: list[dict[str, Any]] = []
    best: dict[str, Any] = {"model_version": None, "val_er": None, "iteration": None}
    model_version = 0
    start_iteration = 0

    if args.init_from:
        init_path = Path(args.init_from)
        if not init_path.is_absolute():
            init_path = repo_root() / init_path
        init_state = torch.load(init_path, map_location=device, weights_only=False)
        init_profile = str(init_state.get("profile", profile))
        if init_profile != profile:
            raise ValueError(
                "--init-from profili uyusmuyor: checkpoint=" + init_profile + ", istenen=" + profile
            )
        model.load_state_dict(init_state["model"])
        print("[init] " + str(init_path) + " (profil " + init_profile + ")")

    if args.resume:
        state = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        if "optimizer" in state:
            optimizer.load_state_dict(state["optimizer"])
        model_version = int(state.get("model_version", 0))
        start_iteration = int(state.get("iteration", 0))
        history = list(state.get("history", []))
        best = dict(state.get("best", best))
        buffer_dirs = list(state.get("buffer_shard_dirs", []))
        if "torch_rng_state" in state:
            torch.set_rng_state(state["torch_rng_state"])
        if "numpy_rng_state" in state:
            rng.bit_generator.state = state["numpy_rng_state"]
        for d in buffer_dirs:
            if Path(d).is_file():
                buffer.add_shard(d)
            else:
                buffer.add_shard_dir(d)
        print("[resume] " + str(args.resume) + " (iterasyon " + str(start_iteration) + ")")

    shard_root = out_dir / "shards"
    if args.shard_dir:
        shard_root = Path(args.shard_dir)
        if not shard_root.is_absolute():
            shard_root = repo_root() / shard_root
    onnx_dir = out_dir / "onnx"
    ckpt_dir = out_dir / "checkpoints"
    for d in (onnx_dir, ckpt_dir):
        d.mkdir(parents=True, exist_ok=True)
    if not shard_root.is_file():
        shard_root.mkdir(parents=True, exist_ok=True)

    metrics_path = out_dir / "metrics.jsonl"
    timings_path = out_dir / "timings.jsonl"
    best_path = out_dir / "best.json"
    test_log_path = out_dir / "test_access.log"

    if start_iteration == 0:
        for p in (metrics_path, timings_path):
            if p.exists():
                p.unlink()

    probe_value: ExclusiveSamples | None = None
    probe_policy: list[PolicySample] | None = None
    probe_mc: ExclusiveSamples | None = None
    probe_path = out_dir / "probe.npz"
    if probe_path.is_file():
        probe_value, probe_policy, probe_mc = load_probe(probe_path)
    probe_size = int(
        args.probe_size if args.probe_size is not None else run_cfg.get("probe_size", 4096)
    )
    probe_policy_size = int(
        args.probe_policy_size
        if args.probe_policy_size is not None
        else run_cfg.get("probe_policy_size", 1024)
    )

    gnubg_path = gnubg_er.find_gnubg() if (val_er_every > 0 or args.test_er) else None
    if (val_er_every > 0 or args.test_er) and gnubg_path is None:
        print("[uyari] gnubg bulunamadi; ER olcumu atlanacak", file=sys.stderr)

    t_start = time.time()

    for it in range(start_iteration + 1, iterations + 1):
        t_it = time.time()

        model_version += 1
        onnx_path = onnx_dir / ("model_v" + str(model_version) + ".onnx")
        export(model, str(onnx_path), model_version, trained_by="ml/train_v2.py")

        sp_seconds = 0.0
        if not args.no_selfplay:
            t_sp = time.time()
            shard_dir = shard_root / ("it" + str(it))
            if shard_dir.exists():
                shutil.rmtree(shard_dir)
            run_selfplay(
                cfg, onnx_path, shard_dir,
                prefix="it" + str(it),
                seed=seed + it,
                games=games,
                depth=depth,
                log_top=log_top,
                extra_args=["--dup-cap", str(dup_cap)],
            )
            sp_seconds = time.time() - t_sp
            buffer.add_shard_dir(shard_dir)
            buffer_dirs.append(str(shard_dir))
        else:
            if str(shard_root) not in buffer_dirs:
                if shard_root.is_file():
                    buffer.add_shard(shard_root)
                else:
                    buffer.add_shard_dir(shard_root)
                buffer_dirs.append(str(shard_root))

        usable = buffer.usable_games()

        t_tgt = time.time()
        value_samples = build_exclusive_samples(
            model, usable, lam=lam, device=device, target_mode=value_target_mode
        )
        policy_samples = build_policy_samples(usable, tau_train=tau_train, min_group=2)
        target_seconds = time.time() - t_tgt

        if probe_value is None:
            # Probe **sabit bir teshis** kumesidir: hedef modundan bagimsiz olarak
            # TD(lambda) referansiyla kurulur (F7-17).
            probe_value = subsample_value(
                build_exclusive_samples(
                    model, usable, lam=lam, device=device,
                    target_mode=VALUE_TARGET_TD_LAMBDA,
                ),
                probe_size,
                np.random.default_rng(seed ^ 0x5EED),
            )
            probe_policy = subsample_policy(
                policy_samples, probe_policy_size, np.random.default_rng(seed ^ 0x5EEF)
            )
            # Sabit, agdan bagimsiz probe: lambda = 1 (saf Monte Carlo) hedefleri.
            probe_mc = subsample_value(
                build_exclusive_samples(model, usable, lam=1.0, device=device),
                probe_size,
                np.random.default_rng(seed ^ 0x5EEE),
            )
            save_probe(probe_path, probe_value, probe_policy, probe_mc)

        train_policy = filter_informative(policy_samples, policy_min_sharpness)

        if len(value_samples) == 0 and len(train_policy) == 0:
            raise RuntimeError(
                "egitim ornegi yok: shard dizini bos veya tum kararlar elendi ("
                + str(shard_root) + ")"
            )

        # Faz 7 Bolum 5.3 / Test 98: kritik karar agirliklandirma.
        value_weights = None
        policy_weights = None
        critical_report = None
        if critical_boost > 1.0:
            # F7-08 duzeltmesi: deger kafasi artik KARAR MARJI olcutunu kullanir.
            # Eski |equity| olcutu para oyununda her ornegi "kritik" yapiyordu
            # (equity = +-1), yani hicbir seyi ayirmiyordu.
            critical_report = build_critical_report(
                value_samples,
                train_policy,
                value_margins=value_samples.margin,
                value_best_equity=value_samples.best_equity,
                boost=critical_boost,
            )
            # Ayirt edicilik yoksa agirlik uygulanmaz ve bu raporlanir.
            if not critical_report.value["degenerate"]:
                value_weights = critical_sampling_weights(
                    critical_mask_value_margin(
                        value_samples.margin,
                        best_equity=value_samples.best_equity,
                    ),
                    boost=critical_boost,
                )
            if not critical_report.policy["degenerate"]:
                policy_weights = critical_sampling_weights(
                    critical_mask_policy(train_policy), boost=critical_boost
                )

        # R-D (F7-94): perspektif artirimi. Kritik agirliklar **tekil** kararlar
        # uzerinde hesaplanir, sonra ciftlenir; boylece rapor sayilari sismez.
        # Agirliklar da orneklerle ayni sirada olmali: `repeat(2)` ic ice
        # yerlesim verir, `concatenate` ise blok verip agirliklari kaydirirdi.
        # Ciftlemeden sonra toplam 2 olur; `rng.choice(p=...)` toplamin 1
        # olmasini istedigi icin yeniden normalestirilir.
        #
        # **Yalniz deger kafasi.** Politika hedefi oynayacak tarafin
        # dagilimidir; girdi cevrilince hedef de cevrilmelidir ve shard'larda
        # karsi tarafin hedefi yok. Ayni hedefle cevirmek kafayi **simetrik**
        # egitir; olculdu (F7-100): renk takasi argmax uyumu 0,174 -> 0,018.
        if args.augment_perspectives:
            value_samples = augment_value_samples(value_samples)
            if value_weights is not None:
                value_weights = _double_weights(value_weights)
        if args.augment_policy_perspectives:
            train_policy = augment_policy_samples(train_policy)
            if policy_weights is not None:
                policy_weights = _double_weights(policy_weights)

        t_tr = time.time()
        stats = train_steps_v2(
            model, optimizer, value_samples, train_policy,
            steps=steps,
            value_batch=value_batch,
            policy_batch=policy_batch,
            c_value=c_value,
            c_policy=c_policy,
            c_cal=c_cal,
            clip_grad_norm=clip_grad_norm,
            device=device,
            rng=rng,
            amp=amp,
            scaler=scaler,
            value_weights=value_weights,
            policy_weights=policy_weights,
        )
        train_seconds = time.time() - t_tr

        probe_metrics = evaluate_exclusive(model, probe_value, device)
        probe_p_loss, probe_p_used = evaluate_policy(model, probe_policy or [], device)
        mc_metrics = (
            evaluate_exclusive(model, probe_mc, device)
            if probe_mc is not None
            else {"ce": float("nan"), "equity_mae": float("nan"),
                  "calibration_slope": float("nan"), "calibration_intercept": float("nan")}
        )
        buf_metrics = evaluate_exclusive(model, value_samples, device)
        buf_p_loss, buf_p_used = evaluate_policy(model, policy_samples, device)

        record: dict[str, Any] = {
            "schema": METRICS_SCHEMA,
            "iteration": it,
            "model_version": model_version,
            "profile": profile,
            "device": device_name,
            "amp": amp,
            "lam": lam,
            "seed": seed,
            "buffer_games": len(buffer),
            "usable_games": len(usable),
            "value_samples": len(value_samples),
            "policy_samples": len(policy_samples),
            "train_policy_samples": len(train_policy),
            "critical_boost": critical_boost,
            "critical": critical_report.to_dict() if critical_report else None,
            "probe_ce": probe_metrics["ce"],
            "probe_equity_mae": probe_metrics["equity_mae"],
            "probe_calibration_slope": probe_metrics["calibration_slope"],
            "probe_calibration_intercept": probe_metrics["calibration_intercept"],
            "probe_mc_ce": mc_metrics["ce"],
            "probe_mc_equity_mae": mc_metrics["equity_mae"],
            "probe_mc_calibration_slope": mc_metrics["calibration_slope"],
            "probe_mc_calibration_intercept": mc_metrics["calibration_intercept"],
            "probe_policy_loss": probe_p_loss,
            "probe_policy_groups": probe_p_used,
            "probe_uniform_baseline": uniform_policy_baseline(probe_policy or []),
            "probe_target_entropy_ratio": target_entropy_ratio(probe_policy or []),
            "buffer_ce": buf_metrics["ce"],
            "buffer_equity_mae": buf_metrics["equity_mae"],
            "buffer_calibration_slope": buf_metrics["calibration_slope"],
            "buffer_policy_loss": buf_p_loss,
            "buffer_policy_groups": buf_p_used,
            "buffer_uniform_baseline": uniform_policy_baseline(policy_samples),
            "buffer_target_entropy_ratio": target_entropy_ratio(policy_samples),
            "val_er": None,
            "val_er_count": 0,
        }
        record.update(stats.summary())

        if val_er_every > 0 and gnubg_path is not None and (
            it % max(1, val_er_every) == 0 or it == iterations
        ):
            measurement = measure_er(
                onnx_path,
                split="val",
                limit=val_er_cases,
                plies=val_er_plies,
                gnubg=gnubg_path,
            )
            record["val_er"] = measurement.get("mean")
            record["val_er_count"] = int(measurement.get("count", 0))
            record["val_er_se"] = measurement.get("standardError")
            current = measurement.get("mean")
            if current is not None and math.isfinite(float(current)):
                if best["val_er"] is None or float(current) < float(best["val_er"]):
                    best = {
                        "model_version": model_version,
                        "val_er": float(current),
                        "iteration": it,
                        "onnx": str(onnx_path),
                        "checkpoint": str(ckpt_dir / ("ckpt_v" + str(model_version) + ".pt")),
                    }
                    best_path.write_text(json.dumps(best, indent=2, sort_keys=True), encoding="utf-8")

        history.append(record)
        _write_jsonl(metrics_path, record)
        _write_jsonl(
            timings_path,
            {
                "iteration": it,
                "selfplay_seconds": sp_seconds,
                "target_seconds": target_seconds,
                "train_seconds": train_seconds,
                "iteration_seconds": time.time() - t_it,
            },
        )

        if not args.quiet:
            print(
                "[it {it:3d}] CE={ce:.5f} MAE={mae:.4f} a={a:.3f} | p={pl:.5f} "
                "| |g|={gn:.3f} | buf={bg} vs={vs} ps={ps}/{tps} | {sec:.1f}s".format(
                    it=it,
                    ce=buf_metrics["ce"],
                    mae=buf_metrics["equity_mae"],
                    a=buf_metrics["calibration_slope"],
                    pl=buf_p_loss,
                    gn=record["grad_norm_mean"],
                    bg=len(buffer),
                    vs=len(value_samples),
                    ps=len(policy_samples),
                    tps=len(train_policy),
                    sec=time.time() - t_it,
                )
            )

        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "iteration": it,
                "model_version": model_version,
                "profile": profile,
                "config": cfg,
                "history": history,
                "best": best,
                "buffer_shard_dirs": buffer_dirs,
                "torch_rng_state": torch.get_rng_state(),
                "numpy_rng_state": rng.bit_generator.state,
            },
            str(ckpt_dir / ("ckpt_v" + str(model_version) + ".pt")),
        )

    elapsed = time.time() - t_start

    test_entry: dict[str, Any] | None = None
    if args.test_er and gnubg_path is not None:
        final_onnx = onnx_dir / ("model_v" + str(model_version) + ".onnx")
        measurement = measure_er(
            final_onnx,
            split="test",
            limit=test_er_cases,
            plies=val_er_plies,
            gnubg=gnubg_path,
        )
        test_entry = append_test_access(
            test_log_path,
            model_version=model_version,
            iteration=iterations,
            measurement=measurement,
        )

    summary = {
        "iterations": iterations,
        "start_iteration": start_iteration,
        "games_per_iteration": games,
        "steps_per_iteration": steps,
        "depth": depth,
        "profile": profile,
        "parameters": parameter_count(model),
        "device": device_name,
        "amp": amp,
        "lam": lam,
        "seed": seed,
        "augment_perspectives": bool(args.augment_perspectives),
        "augment_policy_perspectives": bool(args.augment_policy_perspectives),
        "elapsed_seconds": elapsed,
        "best": best,
        "test_access": test_entry,
        "history": history,
    }
    with open(out_dir / "train_report.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if history:
        first = history[0]
        last = history[-1]
        print()
        print("=== Ozet ===")
        print(
            "iterasyon        : " + str(iterations) + " (G=" + str(games) + ", S=" + str(steps)
            + ", depth=" + str(depth) + ", profil=" + profile + ", device=" + device_name
            + ", amp=" + str(amp) + ")"
        )
        print("CE (buffer)      : " + f"{first['buffer_ce']:.6f}" + " -> " + f"{last['buffer_ce']:.6f}")
        print(
            "equity MAE       : " + f"{first['buffer_equity_mae']:.6f}" + " -> "
            + f"{last['buffer_equity_mae']:.6f}"
        )
        print(
            "kalibrasyon egimi: " + f"{first['buffer_calibration_slope']:.4f}" + " -> "
            + f"{last['buffer_calibration_slope']:.4f}"
        )
        print(
            "politika kaybi   : " + f"{first['buffer_policy_loss']:.6f}" + " -> "
            + f"{last['buffer_policy_loss']:.6f}"
        )
        print(
            "MC deger kaybi   : " + f"{first['probe_mc_ce']:.6f}" + " -> "
            + f"{last['probe_mc_ce']:.6f}" + "  (sabit, agdan bagimsiz hedef)"
        )
        print(
            "MC equity MAE    : " + f"{first['probe_mc_equity_mae']:.6f}" + " -> "
            + f"{last['probe_mc_equity_mae']:.6f}"
        )
        if last.get("val_er") is not None:
            print("VAL-ER           : " + f"{last['val_er']:.4f}" + " (" + str(last["val_er_count"]) + " pozisyon)")
        if best.get("val_er") is not None:
            print(
                "en iyi (VAL-ER)  : v" + str(best["model_version"]) + " ER="
                + f"{best['val_er']:.4f}" + " (iterasyon " + str(best["iteration"]) + ")"
            )
        if test_entry is not None:
            print(
                "TEST-ER          : " + f"{test_entry['er']:.4f}" + " (" + test_entry["label"]
                + ", " + str(test_entry["count"]) + " pozisyon)"
            )
        print("toplam sure      : " + f"{elapsed:.1f}" + " s")

    _release_cuda(device)
    return 0


def _release_cuda(device) -> None:
    """CUDA baglamini **acikca** kapatir (F7-99).

    Windows'ta paralel yuk altinda surec cikisinda ``0xC0000409``
    (STATUS_STACK_BUFFER_OVERRUN) goruluyordu. Cokme egitim sirasinda degil,
    yikim sirasinda oluyordu: ``metrics.jsonl`` tam yazilmis oluyordu. Bekleyen
    asenkron is varken baglamin yikilmasi tetikleyici oldugu icin once
    senkronize edilir, sonra onbellek bosaltilir. CRT seviyesindeki bir abort
    her zaman yakalanamaz; bu bir savunmadir, garanti degil.
    """
    if device is None or getattr(device, "type", None) != "cuda":
        return
    try:
        import gc  # noqa: PLC0415

        import torch  # noqa: PLC0415

        torch.cuda.synchronize()
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    except Exception:  # pragma: no cover - savunma
        pass


if __name__ == "__main__":
    raise SystemExit(main())
