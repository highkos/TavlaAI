"""Faz 4 v3 Bolum 6.1: senkron (ardisik) egitim dongusu.

Her iterasyonda:
  (1) mevcut checkpoint'i ``model_v{N}.onnx`` olarak disa aktar
  (2) C# ``Backgammon.SelfPlay`` ile ``G`` oyun uret
  (3) shard'lari replay buffer'a ekle (son ``buffer_games`` oyun)
  (4) buffer'daki tum oyunlar icin deger hedeflerini mevcut agla yeniden hesapla
  (5) ``S`` egitim adimi
  (6) ``K`` iterasyonda bir degerlendirme

Asenkron/paralel isletim bu fazin kapsami disindadir (Bolum 6.1).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import yaml

from export_onnx import export
from losses import (
    policy_loss_numpy,
    policy_loss_torch,
    total_loss,
    value_loss_huber,
    value_loss_mse,
)
from model import build_model
from league import (
    DEFAULT_ENTRY_THRESHOLD,
    DEFAULT_EVAL_EVERY,
    DEFAULT_EVAL_GAMES,
    DEFAULT_POOL_FRACTION,
    League,
    PoolEntry,
    evaluate_for_entry,
    should_enter_pool,
)
from replay import (
    VALUE_TARGET_SEARCH_DISTILL,
    VALUE_TARGET_TD_LAMBDA,
    PolicySample,
    ReplayBuffer,
    ValueSamples,
    build_policy_samples,
    build_value_samples,
    filter_informative,
    target_entropy_ratio,
    uniform_policy_baseline,
)

VECTOR_SIZE = 221


# ----------------------------------------------------------------------
# Yapilandirma
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


# ----------------------------------------------------------------------
# Tahmin yardimcilari
# ----------------------------------------------------------------------


def predict_values(model, x: np.ndarray, device, batch_size: int = 4096) -> np.ndarray:
    out = np.empty((x.shape[0],), dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            stop = min(start + batch_size, x.shape[0])
            t = torch.from_numpy(x[start:stop]).to(device)
            v, _ = model(t)
            out[start:stop] = v.reshape(-1).detach().to("cpu").numpy()
    return out


def predict_logits(model, x: np.ndarray, device, batch_size: int = 8192) -> np.ndarray:
    out = np.empty((x.shape[0],), dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            stop = min(start + batch_size, x.shape[0])
            t = torch.from_numpy(x[start:stop]).to(device)
            _, lg = model(t)
            out[start:stop] = lg.reshape(-1).detach().to("cpu").numpy()
    return out


def evaluate_value_loss(model, samples: ValueSamples, device, mode: str, delta: float) -> float:
    if len(samples) == 0:
        return float("nan")
    pred = predict_values(model, samples.x, device)
    diff = pred.astype(np.float64) - samples.y.astype(np.float64)
    if mode == "huber":
        a = np.abs(diff)
        loss = np.where(a <= delta, 0.5 * diff * diff, delta * (a - 0.5 * delta))
        return float(np.mean(loss))
    return float(np.mean(diff * diff))


def evaluate_policy_loss(model, samples: Sequence[PolicySample], device) -> tuple[float, int]:
    if not samples:
        return float("nan"), 0
    vecs = np.concatenate([s.vectors for s in samples], axis=0)
    logits = predict_logits(model, vecs, device)
    targets = np.concatenate([s.target for s in samples], axis=0)
    sizes = [int(s.vectors.shape[0]) for s in samples]
    return policy_loss_numpy(logits, targets, sizes, min_group=2)


# ----------------------------------------------------------------------
# Egitim adimlari
# ----------------------------------------------------------------------


@dataclass
class StepStats:
    value_loss: list[float] = field(default_factory=list)
    policy_loss: list[float] = field(default_factory=list)
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
            "grad_norm_mean": mean(self.grad_norm),
            "grad_norm_max": float(np.max(self.grad_norm)) if self.grad_norm else float("nan"),
        }


def train_steps(
    model,
    optimizer,
    value_samples: ValueSamples,
    policy_samples: Sequence[PolicySample],
    *,
    steps: int,
    value_batch: int,
    policy_batch: int,
    c_policy: float,
    clip_grad_norm: float,
    value_loss_mode: str,
    huber_delta: float,
    device,
    rng: np.random.Generator,
) -> StepStats:
    stats = StepStats()
    if steps <= 0:
        return stats

    n_value = len(value_samples)
    n_policy = len(policy_samples)

    model.train()
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)

        if n_value > 0:
            k = min(value_batch, n_value)
            idx = rng.integers(0, n_value, size=k)
            x = torch.from_numpy(value_samples.x[idx]).to(device)
            y = torch.from_numpy(value_samples.y[idx]).to(device)
            v, _ = model(x)
            v = v.reshape(-1)
            if value_loss_mode == "huber":
                lv = value_loss_huber(v, y, delta=huber_delta)
            else:
                lv = value_loss_mse(v, y)
        else:
            lv = torch.zeros((), device=device)

        if n_policy > 0:
            k = min(policy_batch, n_policy)
            pidx = rng.integers(0, n_policy, size=k)
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

        loss = total_loss(lv, lp, c_policy)
        loss.backward()
        gn = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad_norm)
        optimizer.step()

        stats.value_loss.append(float(lv.detach()))
        stats.policy_loss.append(float(lp.detach()))
        stats.grad_norm.append(float(gn))

    model.eval()
    return stats


# ----------------------------------------------------------------------
# Self-play cagrisi
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
) -> None:
    sp = cfg.get("selfplay") or {}
    project = repo_root() / str(sp.get("project", "Backgammon.SelfPlay/Backgammon.SelfPlay.csproj"))
    configuration = str(sp.get("configuration", "Release"))

    shard_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        "dotnet", "run",
        "--project", str(project),
        "-c", configuration,
        "--no-build",
        "--",
        "--model", str(onnx_path),
        "--games", str(games),
        "--seed", str(seed),
        "--threads", str(int(sp.get("threads", 1))),
        "--out", str(shard_dir),
        "--prefix", prefix,
        "--depth", str(depth),
        "--max-root", str(int(sp.get("max_candidates_root", 0))),
        "--max-inner", str(int(sp.get("max_candidates_inner", 0))),
        "--log-top", str(log_top),
        "--exploration", str(int(sp.get("exploration_plies", 10))),
        "--sel-temp", str(float(sp.get("selection_temperature", 0.05))),
        "--policy-temp", str(float(sp.get("policy_temperature", 1.0))),
        "--max-plies", str(int(sp.get("max_plies", 500))),
        "--games-per-shard", str(int(sp.get("games_per_shard", 0))),
        "--pool-fraction", str(float(sp.get("pool_fraction", 0.0))),
        "--max-batch", str(int(sp.get("max_batch", 2048))),
        "--intra-op", str(int(sp.get("intra_op_threads", 1))),
    ]

    if bool(sp.get("gzip", False)):
        cmd.append("--gzip")
    if bool(sp.get("cuda", False)):
        cmd.append("--cuda")

    cmd.extend(extra_args)

    proc = subprocess.run(cmd, cwd=str(repo_root()), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "self-play basarisiz (exit " + str(proc.returncode) + ")\n"
            + "STDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr
        )
    return proc.stdout


def run_eval_random(cfg: dict, onnx_path: Path, games: int, seed: int, depth: int) -> dict[str, float]:
    sp = cfg.get("selfplay") or {}
    project = repo_root() / str(sp.get("project", "Backgammon.SelfPlay/Backgammon.SelfPlay.csproj"))
    configuration = str(sp.get("configuration", "Release"))

    cmd: list[str] = [
        "dotnet", "run",
        "--project", str(project),
        "-c", configuration,
        "--no-build",
        "--",
        "--model", str(onnx_path),
        "--eval-random", str(games),
        "--seed", str(seed),
        "--depth", str(depth),
        "--max-root", str(int(sp.get("max_candidates_root", 0))),
        "--max-inner", str(int(sp.get("max_candidates_inner", 0))),
        "--max-plies", str(int(sp.get("max_plies", 500))),
        "--max-batch", str(int(sp.get("max_batch", 2048))),
        "--intra-op", str(int(sp.get("intra_op_threads", 1))),
    ]
    if bool(sp.get("cuda", False)):
        cmd.append("--cuda")

    proc = subprocess.run(cmd, cwd=str(repo_root()), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "eval-random basarisiz (exit " + str(proc.returncode) + ")\n"
            + "STDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr
        )

    out: dict[str, float] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "win rate":
            out["win_rate_pct"] = float(value.replace("%", "").strip())
        elif key == "mean points":
            parts = value.split("+/-")
            out["mean_points"] = float(parts[0].strip())
            if len(parts) > 1:
                out["mean_points_se"] = float(parts[1].strip())
        elif key == "wins / losses":
            parts = value.split("(")[0].split("/")
            out["wins"] = float(parts[0].strip())
            out["losses"] = float(parts[1].strip())
    return out


# ----------------------------------------------------------------------
# Lig guncellemesi
# ----------------------------------------------------------------------


def update_league(
    league: League,
    onnx_path: Path,
    model_version: int,
    iteration: int,
    *,
    n_eval: int,
    seed: int,
    depth: int,
    threshold: float,
    cuda: bool,
) -> dict[str, Any]:
    """Havuza giris kontrolu (spec Bolum 6.5).

    Havuz bossa mevcut model ilk uye olarak eklenir (karsilastirma tabani).
    Aksi halde en guclu uyeye karsi ``n_eval`` oyun oynanir; ortalama puanin
    alt guven siniri ``threshold``'un uzerindeyse model havuza girer.
    """
    info: dict[str, Any] = {
        "iteration": iteration,
        "model_version": model_version,
        "pool_size_before": len(league),
        "entered": False,
        "evicted": [],
    }

    if league.is_empty():
        name = "v" + str(model_version)
        target = league.import_model(Path(onnx_path), name, model_version, iteration)
        league.add(
            PoolEntry(
                name=name,
                onnx_path=str(target),
                model_version=model_version,
                iteration=iteration,
                strength=0.0,
                strength_se=0.0,
            )
        )
        info["entered"] = True
        info["reason"] = "havuz bos — karsilastirma tabani olarak eklendi"
        info["pool_size_after"] = len(league)
        return info

    strongest = league.strongest()
    info["opponent"] = strongest.name if strongest is not None else None

    result = evaluate_for_entry(
        league,
        Path(onnx_path),
        games=n_eval,
        seed=seed,
        depth=depth,
        cuda=cuda,
    )

    if result is None:
        info["reason"] = "degerlendirme yapilamadi"
        info["pool_size_after"] = len(league)
        return info

    info["mean_points"] = result.mean_points
    info["standard_error"] = result.standard_error
    info["lower_confidence_bound"] = result.lower_confidence_bound
    info["win_rate"] = result.win_rate

    if should_enter_pool(result, threshold):
        name = "v" + str(model_version)
        target = league.import_model(Path(onnx_path), name, model_version, iteration)
        evicted = league.add(
            PoolEntry(
                name=name,
                onnx_path=str(target),
                model_version=model_version,
                iteration=iteration,
                strength=result.mean_points,
                strength_se=result.standard_error,
            )
        )
        info["entered"] = True
        info["evicted"] = [e.name for e in evicted]
        info["reason"] = "alt guven siniri esigin uzerinde"
    else:
        info["reason"] = "alt guven siniri esigin altinda"

    info["pool_size_after"] = len(league)
    return info


# ----------------------------------------------------------------------
# Ana dongu
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Faz 4 v3 senkron egitim dongusu")
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--out", default=None, help="calisma dizini (config: run.out_dir)")
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--games", type=int, default=None, help="iterasyon basina oyun (G)")
    parser.add_argument("--steps", type=int, default=None, help="iterasyon basina egitim adimi (S)")
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--max-root", type=int, default=None, help="kok aday siniri (0 = kisitsiz)")
    parser.add_argument("--max-inner", type=int, default=None, help="ic dugum aday siniri (0 = kisitsiz)")
    parser.add_argument("--device", default=None, choices=["cpu", "cuda"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--eval-random", type=int, default=None, help="RandomBot'a karsi oyun sayisi")
    parser.add_argument("--c-policy", type=float, default=None, help="politika kaybi katsayisi")
    parser.add_argument("--lr", type=float, default=None, help="ogrenme orani")
    parser.add_argument("--lam", type=float, default=None, help="TD(lambda)")
    parser.add_argument("--resume", default=None, help="checkpoint .pt yolu")
    parser.add_argument("--no-selfplay", action="store_true", help="self-play'i atla, mevcut shard'lari kullan")
    parser.add_argument("--league", action="store_true", help="lig/model havuzunu etkinlestir")
    parser.add_argument("--no-league", action="store_true", help="ligi kapat")
    parser.add_argument("--league-every", type=int, default=None, help="lig giris kontrolu sikligi")
    parser.add_argument("--league-n-eval", type=int, default=None, help="lig giris maci oyun sayisi")
    parser.add_argument("--league-pool-dir", default=None, help="lig havuz klasoru")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)

    run_cfg = cfg.get("run") or {}
    train_cfg = cfg.get("train") or {}
    model_cfg = cfg.get("model") or {}
    buffer_cfg = cfg.get("buffer") or {}
    eval_cfg = cfg.get("eval") or {}

    out_dir = Path(args.out or run_cfg.get("out_dir", "ml/runs/stage_c"))
    if not out_dir.is_absolute():
        out_dir = repo_root() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    iterations = int(args.iterations if args.iterations is not None else run_cfg.get("iterations", 20))
    games = int(args.games if args.games is not None else _get(cfg, "selfplay", "games", 500))
    steps = int(args.steps if args.steps is not None else train_cfg.get("steps_per_iteration", 200))
    depth = int(args.depth if args.depth is not None else _get(cfg, "selfplay", "depth", 1))
    if args.max_root is not None:
        cfg.setdefault("selfplay", {})["max_candidates_root"] = int(args.max_root)
    if args.max_inner is not None:
        cfg.setdefault("selfplay", {})["max_candidates_inner"] = int(args.max_inner)
    seed = int(args.seed if args.seed is not None else run_cfg.get("seed", 1))
    eval_every = int(run_cfg.get("eval_every", 5))
    eval_random_games = int(
        args.eval_random if args.eval_random is not None else eval_cfg.get("random_games", 0)
    )

    device_name = str(args.device or run_cfg.get("device", "cpu"))
    if device_name == "cuda" and not torch.cuda.is_available():
        print("[uyari] CUDA yok, CPU'ya dusuluyor", file=sys.stderr)
        device_name = "cpu"
    device = torch.device(device_name)

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    h1 = int(model_cfg.get("h1", 128))
    h2 = int(model_cfg.get("h2", 64))
    model = build_model(VECTOR_SIZE, h1, h2, seed=seed).to(device)

    if args.resume:
        state = torch.load(args.resume, map_location=device)
        model.load_state_dict(state["model"])
        print("[resume] " + str(args.resume))

    lr = float(args.lr if args.lr is not None else train_cfg.get("lr", 1e-3))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=float(train_cfg.get("weight_decay", 1e-4)),
    )

    lam = float(args.lam if args.lam is not None else train_cfg.get("lam", 0.7))
    c_policy = float(args.c_policy if args.c_policy is not None else train_cfg.get("c_policy", 1.0))
    tau_train = float(train_cfg.get("tau_train", 0.05))
    clip_grad_norm = float(train_cfg.get("clip_grad_norm", 1.0))
    value_batch = int(train_cfg.get("value_batch", 4096))
    policy_batch = int(train_cfg.get("policy_batch", 256))
    value_loss_mode = str(train_cfg.get("value_loss", "mse"))
    huber_delta = float(train_cfg.get("huber_delta", 1.0))
    policy_min_sharpness = float(train_cfg.get("policy_min_sharpness", 0.99))
    target_mode = str(train_cfg.get("value_target_mode", VALUE_TARGET_TD_LAMBDA))
    if target_mode not in (VALUE_TARGET_TD_LAMBDA, VALUE_TARGET_SEARCH_DISTILL):
        raise ValueError("bilinmeyen value_target_mode: " + target_mode)

    log_top = int(_get(cfg, "selfplay", "log_top_candidates", 12))
    buffer = ReplayBuffer(int(buffer_cfg.get("max_games", 20000)))

    league_cfg = cfg.get("league") or {}
    league_enabled = bool(league_cfg.get("enabled", False))
    if args.league:
        league_enabled = True
    if args.no_league:
        league_enabled = False
    league_every = int(
        args.league_every if args.league_every is not None
        else league_cfg.get("every", DEFAULT_EVAL_EVERY)
    )
    league_n_eval = int(
        args.league_n_eval if args.league_n_eval is not None
        else league_cfg.get("n_eval", DEFAULT_EVAL_GAMES)
    )
    league_threshold = float(league_cfg.get("entry_threshold", DEFAULT_ENTRY_THRESHOLD))
    league_fraction = float(league_cfg.get("pool_fraction", DEFAULT_POOL_FRACTION))
    league = League.load(
        Path(str(args.league_pool_dir or league_cfg.get("pool_dir", "ml/runs/pool"))),
        max_size=int(league_cfg.get("pool_size", 10)),
        eviction=str(league_cfg.get("eviction", "oldest")),
    )
    if league_enabled:
        print("[league] havuz: " + str(league.pool_dir) + " (" + str(len(league)) + " uye)")

    shard_root = out_dir / "shards"
    onnx_dir = out_dir / "onnx"
    ckpt_dir = out_dir / "checkpoints"
    for d in (shard_root, onnx_dir, ckpt_dir):
        d.mkdir(parents=True, exist_ok=True)

    history: list[dict[str, Any]] = []
    probe_value: ValueSamples | None = None
    probe_policy: list[PolicySample] | None = None
    probe_mc: ValueSamples | None = None
    model_version = 0

    t_start = time.time()

    for it in range(1, iterations + 1):
        t_it = time.time()

        # (1) export
        model_version += 1
        onnx_path = onnx_dir / ("model_v" + str(model_version) + ".onnx")
        export(model, str(onnx_path), model_version, trained_by="ml/train.py")

        # (2) self-play
        sp_seconds = 0.0
        pool_opponent: PoolEntry | None = None
        if not args.no_selfplay:
            t_sp = time.time()
            shard_dir = shard_root / ("it" + str(it))
            if shard_dir.exists():
                shutil.rmtree(shard_dir)
            # Havuzdan her iterasyonda bir uye secilir; oyun basina oran
            # (pool_fraction) C# surucusunde uygulanir. Burada oran da
            # uygulanirsa etkin oran pool_fraction^2 olur (bkz. ASSUMPTIONS F4-51).
            pool_opponent = (
                league.select_opponent(rng, 1.0) if league_enabled else None
            )
            sp_extra: list[str] = []
            if pool_opponent is not None:
                sp_extra.extend([
                    "--pool-model", str(pool_opponent.onnx_path),
                    "--pool-fraction", str(league_fraction),
                ])

            run_selfplay(
                cfg, onnx_path, shard_dir,
                prefix="it" + str(it),
                seed=seed + it,
                games=games,
                depth=depth,
                log_top=log_top,
                extra_args=sp_extra,
            )
            sp_seconds = time.time() - t_sp
            # (3) buffer
            buffer.add_shard_dir(shard_dir)
        else:
            buffer.add_shard_dir(shard_root)

        usable = buffer.usable_games()

        # (4) hedefler
        value_samples = build_value_samples(
            model, usable, lam=lam, device=device, target_mode=target_mode
        )
        policy_samples = build_policy_samples(usable, tau_train=tau_train, min_group=2)

        if probe_value is None:
            probe_value = value_samples
            probe_policy = policy_samples
            # Sabit, agdan bagimsiz probe: lambda = 1 (Monte Carlo) hedefleri.
            probe_mc = build_value_samples(
                model, usable, lam=1.0, device=device, target_mode=VALUE_TARGET_TD_LAMBDA
            )

        train_policy = filter_informative(policy_samples, policy_min_sharpness)

        # (5) egitim
        stats = train_steps(
            model, optimizer, value_samples, train_policy,
            steps=steps,
            value_batch=value_batch,
            policy_batch=policy_batch,
            c_policy=c_policy,
            clip_grad_norm=clip_grad_norm,
            value_loss_mode=value_loss_mode,
            huber_delta=huber_delta,
            device=device,
            rng=rng,
        )

        # (6) olcum — sabit probe kumesi (ogrenme egrisi) + guncel buffer
        probe_v_loss = evaluate_value_loss(model, probe_value, device, value_loss_mode, huber_delta)
        probe_p_loss, probe_p_used = evaluate_policy_loss(model, probe_policy or [], device)
        uniform = uniform_policy_baseline(probe_policy or [])
        ent_ratio = target_entropy_ratio(probe_policy or [])

        mc_v_loss = evaluate_value_loss(model, probe_mc, device, value_loss_mode, huber_delta)
        buf_v_loss = evaluate_value_loss(model, value_samples, device, value_loss_mode, huber_delta)
        buf_p_loss, buf_p_used = evaluate_policy_loss(model, policy_samples, device)
        buf_uniform = uniform_policy_baseline(policy_samples)
        buf_ent_ratio = target_entropy_ratio(policy_samples)

        record: dict[str, Any] = {
            "iteration": it,
            "model_version": model_version,
            "buffer_games": len(buffer),
            "usable_games": len(usable),
            "value_samples": len(value_samples),
            "policy_samples": len(policy_samples),
            "probe_value_loss": probe_v_loss,
            "probe_policy_loss": probe_p_loss,
            "probe_policy_groups": probe_p_used,
            "uniform_baseline": uniform,
            "target_entropy_ratio": ent_ratio,
            "probe_mc_value_loss": mc_v_loss,
            "train_policy_samples": len(train_policy),
            "buffer_value_loss": buf_v_loss,
            "buffer_policy_loss": buf_p_loss,
            "buffer_policy_groups": buf_p_used,
            "buffer_uniform_baseline": buf_uniform,
            "buffer_target_entropy_ratio": buf_ent_ratio,
            "selfplay_seconds": sp_seconds,
            "pool_opponent": pool_opponent.name if pool_opponent is not None else None,
            "pool_size": len(league),
            "iteration_seconds": time.time() - t_it,
        }
        record.update(stats.summary())

        if eval_random_games > 0 and (it % max(1, eval_every) == 0 or it == iterations):
            record["eval_random"] = run_eval_random(cfg, onnx_path, eval_random_games, seed + 1000 + it, depth)

        if league_enabled and (it % max(1, league_every) == 0 or it == iterations):
            record["league"] = update_league(
                league, onnx_path, model_version, it,
                n_eval=league_n_eval,
                seed=seed + 2000 + it,
                depth=depth,
                threshold=league_threshold,
                cuda=bool(_get(cfg, "selfplay", "cuda", False)),
            )

        history.append(record)

        if not args.quiet:
            print(
                "[it {it:3d}] MC v={mcv:+.5f} | buffer v={bvl:+.5f} p={bpl:.5f} "
                "(uniform {ub:.5f}) H/logE={hr:.3f} | |g|={gn:.3f} | buf={bg} vs={vs} "
                "ps={ps}/{tps} | {sec:.1f}s".format(
                    it=it,
                    mcv=mc_v_loss,
                    bvl=buf_v_loss,
                    bpl=buf_p_loss,
                    ub=buf_uniform,
                    hr=buf_ent_ratio,
                    gn=record["grad_norm_mean"],
                    bg=len(buffer),
                    vs=len(value_samples),
                    ps=len(policy_samples),
                    tps=len(train_policy),
                    sec=record["iteration_seconds"],
                )
            )

        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "iteration": it,
                "model_version": model_version,
                "config": cfg,
            },
            str(ckpt_dir / ("ckpt_v" + str(model_version) + ".pt")),
        )

    elapsed = time.time() - t_start

    summary = {
        "iterations": iterations,
        "games_per_iteration": games,
        "steps_per_iteration": steps,
        "depth": depth,
        "device": device_name,
        "seed": seed,
        "elapsed_seconds": elapsed,
        "history": history,
    }
    with open(out_dir / "train_report.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if history:
        first = history[0]
        last = history[-1]
        print()
        print("=== Ozet ===")
        print("iterasyon        : " + str(iterations) + " (G=" + str(games) + ", S=" + str(steps) +
              ", depth=" + str(depth) + ", device=" + device_name + ")")
        print("MC deger kaybi   : " + f"{first['probe_mc_value_loss']:.6f}" + " -> " +
              f"{last['probe_mc_value_loss']:.6f}" + "  (sabit, agdan bagimsiz hedef)")
        print("TD deger kaybi   : " + f"{first['probe_value_loss']:.6f}" + " -> " +
              f"{last['probe_value_loss']:.6f}" + "  (sabit probe)")
        print("politika kaybi   : " + f"{first['probe_policy_loss']:.6f}" + " -> " +
              f"{last['probe_policy_loss']:.6f}" + " (duzgun baz " +
              f"{last['uniform_baseline']:.6f}" + ")")
        print("buffer deger     : " + f"{first['buffer_value_loss']:.6f}" + " -> " +
              f"{last['buffer_value_loss']:.6f}")
        print("buffer politika  : " + f"{first['buffer_policy_loss']:.6f}" + " -> " +
              f"{last['buffer_policy_loss']:.6f}" + " (duzgun baz " +
              f"{last['buffer_uniform_baseline']:.6f}" + ")")
        print("Hedef entropi/log|E| : " + f"{last['buffer_target_entropy_ratio']:.4f}")
        print("toplam sure      : " + f"{elapsed:.1f}" + " s")
        if "eval_random" in last:
            er = last["eval_random"]
            print("RandomBot        : kazanma " + f"{er.get('win_rate_pct', float('nan')):.2f}" +
                  " %, ortalama puan " + f"{er.get('mean_points', float('nan')):+.4f}" +
                  " +/- " + f"{er.get('mean_points_se', float('nan')):.4f}")
        if league_enabled:
            print("lig havuzu       : " + str(len(league)) + " uye (" + str(league.pool_dir) + ")")
            for e in league.entries:
                print("  - " + e.name + " (it " + str(e.iteration) + ", guc " +
                      f"{e.strength:+.4f}" + " +/- " + f"{e.strength_se:.4f}" + ")")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())