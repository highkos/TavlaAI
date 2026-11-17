"""Faz 6 v3 Bolum 12.4 - Asama D (olcekli egitim) testleri: 68, 69, 70, 71a, 71b, 72, 73, 74.

Testler ``ml/train_v2.py`` dongusunu gercek olarak calistirir. Hiz icin kucuk sentetik
shard'lar kullanilir; olculen sey egitim dongusunun *davranisidir* (determinizm,
devam ettirme, secim, erisim kaydi), model kalitesi degil.

Test 69 (Track H / H0 paritesi) Ek A kapisi acilmadigi icin atlanir: Evren
platformunda H200 erisimi bu fazda yok (bkz. ASSUMPTIONS F6-18).
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

import gnubg_er
import shards
import train_v2
from conftest import ARTIFACTS

REPO_ROOT = Path(__file__).resolve().parents[2]
ML_DIR = REPO_ROOT / "ml"
TRAIN_V2 = ML_DIR / "train_v2.py"

GNUBG = gnubg_er.find_gnubg()

#: Test 71b toleranslari (Faz 6 Bolum 8.6).
GPU_LOSS_TOLERANCE = 1e-4
GPU_ER_TOLERANCE = 1e-3


# --------------------------------------------------------------------------- yardimcilar


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return (e / e.sum()).astype(np.float32)


def make_shard(
    directory: Path,
    *,
    games: int = 24,
    seed: int = 5,
    decisions: int = 12,
    candidates: int = 4,
) -> Path:
    """Kucuk, deterministik sentetik shard uretir (egitim dongusu icin yakit)."""
    rng = np.random.default_rng(seed)
    records: list[shards.GameRecord] = []
    for gid in range(games):
        learner = 1 if gid % 2 == 0 else -1
        decs: list[shards.DecisionRecord] = []
        for t in range(decisions):
            mover = learner if t % 2 == 0 else -learner
            flags = shards.DEC_IS_LEARNER if mover == learner else 0
            q = rng.standard_normal(candidates).astype(np.float32)
            decs.append(
                shards.DecisionRecord(
                    mover=mover,
                    flags=flags,
                    candidate_total=candidates,
                    search_value=float(np.max(q)),
                    chosen_vector=rng.standard_normal(shards.VECTOR_SIZE).astype(np.float32),
                    q=q,
                    policy_target_cs=_softmax(q),
                    cand_vectors=rng.standard_normal(
                        (candidates, shards.VECTOR_SIZE)
                    ).astype(np.float32),
                )
            )
        decs.append(
            shards.DecisionRecord(
                mover=-learner,
                flags=shards.DEC_CHOSEN_IS_TERMINAL,
                candidate_total=1,
                search_value=0.0,
            )
        )
        winner = learner if gid % 3 else -learner
        result_type = 1 + (gid % 3)
        records.append(
            shards.GameRecord(
                game_id=gid,
                learner_side=learner,
                flags=0,
                cube_value=1,
                decisions=decs,
                winner=winner,
                result_type=result_type,
                result_points=result_type,
            )
        )
    path = directory / "synthetic.bgsp"
    shards.write_shard(
        path,
        shards.ShardHeader(model_version=1, log_top_candidates=candidates),
        records,
    )
    return path


def run_train(out_dir: Path, shard_dir: Path, *extra: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(TRAIN_V2),
        "--out",
        str(out_dir),
        "--no-selfplay",
        "--shard-dir",
        str(shard_dir),
        "--quiet",
        *extra,
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=timeout)
    assert proc.returncode == 0, "train_v2 basarisiz:\n" + proc.stdout + "\n" + proc.stderr
    return proc


def read_metrics(out_dir: Path) -> list[dict]:
    path = out_dir / "metrics.jsonl"
    assert path.is_file(), "metrics.jsonl yok: " + str(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_timings(out_dir: Path) -> list[dict]:
    path = out_dir / "timings.jsonl"
    assert path.is_file(), "timings.jsonl yok: " + str(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def total_train_seconds(out_dir: Path) -> float:
    return float(sum(row["train_seconds"] for row in read_timings(out_dir)))


def _require_gnubg() -> None:
    if GNUBG is None:
        pytest.skip("gnubg bulunamadi; ER olcumu yapilamaz")


# --------------------------------------------------------------------------- Test 68


@pytest.mark.slow
def test_68_capacity_gain_is_measured(tmp_path: Path) -> None:
    """medium vs large, ayni veri -> ER farki olculur; kazanc yoksa medium kalir."""
    _require_gnubg()
    shard = make_shard(tmp_path, games=32, seed=17)

    measured: dict[str, dict[str, float]] = {}
    for profile in ("medium", "large"):
        out = tmp_path / profile
        run_train(
            out,
            shard,
            "--iterations", "2",
            "--steps", "6",
            "--profile", profile,
            "--seed", "21",
            "--device", "cpu",
            "--torch-threads", "1",
            "--val-er-every", "2",
            "--val-er-cases", "8",
        )
        rows = [r for r in read_metrics(out) if r.get("val_er") is not None]
        assert rows, profile + ": VAL-ER olculmedi"
        last = rows[-1]
        measured[profile] = {
            "er": float(last["val_er"]),
            "se": float(last.get("val_er_se") or 0.0),
        }

    decision = train_v2.decide_capacity(
        measured["medium"]["er"],
        measured["medium"]["se"],
        measured["large"]["er"],
        measured["large"]["se"],
    )
    (tmp_path / "capacity_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8"
    )

    assert decision["selected"] in ("medium", "large")
    assert math.isfinite(decision["difference"])
    assert decision["threshold"] >= 0.0
    # Karar kurali tutarli olmali: esik asilirsa large, asilmazsa medium.
    assert (decision["selected"] == "large") == (decision["difference"] > decision["threshold"])


# --------------------------------------------------------------------------- Test 69


def test_69_track_h_h0_parity() -> None:
    """Ek A (Evren/H200) kapisi acilmadigi icin Track H kosulamaz."""
    pytest.skip("Ek A kapisi acilmadi: Evren platformunda H200 erisimi yok (F6-18)")


# --------------------------------------------------------------------------- Test 70


@pytest.mark.slow
def test_70_amp_is_measured(tmp_path: Path) -> None:
    """FP32 vs FP16/BF16-AMP: sure ve kayip farki olculur; kazanc yoksa FP32."""
    shard = make_shard(tmp_path, games=32, seed=23)

    measured: dict[str, dict[str, float]] = {}
    for name, extra in (("fp32", ()), ("amp", ("--amp",))):
        out = tmp_path / name
        run_train(
            out,
            shard,
            "--iterations", "2",
            "--steps", "8",
            "--profile", "medium",
            "--seed", "31",
            "--device", "cpu",
            "--torch-threads", "1",
            *extra,
        )
        rows = read_metrics(out)
        measured[name] = {
            "seconds": total_train_seconds(out),
            "ce": float(rows[-1]["buffer_ce"]),
        }

    decision = train_v2.decide_amp(
        measured["fp32"]["seconds"],
        measured["fp32"]["ce"],
        measured["amp"]["seconds"],
        measured["amp"]["ce"],
    )
    (tmp_path / "amp_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8"
    )

    assert decision["selected"] in ("fp32", "amp")
    assert decision["seconds_fp32"] > 0.0
    assert decision["seconds_amp"] > 0.0
    assert math.isfinite(decision["speedup"])
    assert (decision["selected"] == "amp") == (
        decision["speedup"] >= decision["speedup_threshold"]
        and decision["loss_delta"] <= decision["loss_tolerance"]
    )


# --------------------------------------------------------------------------- Test 71a


def test_71a_training_is_reproducible_cpu(tmp_path: Path) -> None:
    """Ayni seed + ayni veri + ayni kod -> bit duzeyinde ayni metrics.jsonl (CPU)."""
    shard = make_shard(tmp_path, seed=41)
    common = (
        "--iterations", "3",
        "--steps", "4",
        "--profile", "small",
        "--seed", "1234",
        "--device", "cpu",
        "--torch-threads", "1",
    )
    first = tmp_path / "a"
    second = tmp_path / "b"
    run_train(first, shard, *common)
    run_train(second, shard, *common)

    a = (first / "metrics.jsonl").read_bytes()
    b = (second / "metrics.jsonl").read_bytes()
    assert a == b, "metrics.jsonl bit duzeyinde ayni degil"
    assert len(read_metrics(first)) == 3


# --------------------------------------------------------------------------- Test 71b


@pytest.mark.slow
def test_71b_training_is_reproducible_gpu(tmp_path: Path) -> None:
    """Ayni seed -> tolerans icinde ayni (|dloss| <= 1e-4, |dER| <= 1e-3)."""
    import torch

    if not torch.cuda.is_available():
        pytest.skip("CUDA yok")

    shard = make_shard(tmp_path, seed=43)
    common = [
        "--iterations", "2",
        "--steps", "4",
        "--profile", "small",
        "--seed", "55",
        "--device", "cuda",
    ]
    if GNUBG is not None:
        common += ["--val-er-every", "2", "--val-er-cases", "6"]

    first = tmp_path / "a"
    second = tmp_path / "b"
    run_train(first, shard, *common)
    run_train(second, shard, *common)

    rows_a = read_metrics(first)
    rows_b = read_metrics(second)
    assert len(rows_a) == len(rows_b) == 2

    er_compared = 0
    for x, y in zip(rows_a, rows_b):
        assert abs(x["buffer_ce"] - y["buffer_ce"]) <= GPU_LOSS_TOLERANCE
        if x.get("val_er") is not None and y.get("val_er") is not None:
            assert abs(x["val_er"] - y["val_er"]) <= GPU_ER_TOLERANCE
            er_compared += 1
    if GNUBG is not None:
        assert er_compared >= 1, "VAL-ER karsilastirilmadi"


# --------------------------------------------------------------------------- Test 72


def test_72_checkpoint_resume_is_exact(tmp_path: Path) -> None:
    """--resume ile devam, kesintisiz kosuyla ayni (CPU bit duzeyi)."""
    shard = make_shard(tmp_path, seed=47)
    common = (
        "--steps", "4",
        "--profile", "small",
        "--seed", "99",
        "--device", "cpu",
        "--torch-threads", "1",
    )
    full = tmp_path / "full"
    part = tmp_path / "part"

    run_train(full, shard, "--iterations", "4", *common)
    run_train(part, shard, "--iterations", "2", *common)

    checkpoint = part / "checkpoints" / "ckpt_v2.pt"
    assert checkpoint.is_file(), "checkpoint yazilmadi"

    run_train(part, shard, "--iterations", "4", *common, "--resume", str(checkpoint))

    a = (full / "metrics.jsonl").read_bytes()
    b = (part / "metrics.jsonl").read_bytes()
    assert a == b, "resume sonrasi metrics.jsonl kesintisiz kosuyla ayni degil"
    assert len(read_metrics(part)) == 4


# --------------------------------------------------------------------------- Test 73


@pytest.mark.slow
def test_73_best_model_selected_by_val_er(tmp_path: Path) -> None:
    """En iyi model VAL-ER ile secilir; TEST-ER'e bakilmaz."""
    _require_gnubg()
    shard = make_shard(tmp_path, seed=53)
    out = tmp_path / "run"
    run_train(
        out,
        shard,
        "--iterations", "2",
        "--steps", "3",
        "--profile", "small",
        "--seed", "7",
        "--device", "cpu",
        "--torch-threads", "1",
        "--val-er-every", "1",
        "--val-er-cases", "6",
    )

    best_path = out / "best.json"
    assert best_path.is_file(), "best.json yazilmadi"
    best = json.loads(best_path.read_text(encoding="utf-8"))

    rows = read_metrics(out)
    ers = [float(r["val_er"]) for r in rows if r.get("val_er") is not None]
    assert len(ers) == 2, "her iterasyonda VAL-ER olculmeliydi"
    assert best["val_er"] == pytest.approx(min(ers))
    assert best["model_version"] in [r["model_version"] for r in rows]

    # Secim sirasinda TEST-ER'e hic bakilmadi.
    assert not (out / "test_access.log").exists(), "secim sirasinda TEST-ER erisimi olmus"


# --------------------------------------------------------------------------- Test 74


@pytest.mark.slow
def test_74_test_access_is_logged(tmp_path: Path) -> None:
    """TEST-ER erisimi test_access.log'a yazilir; ikinci erisim 'kesifsel' etiketlenir."""
    _require_gnubg()
    shard = make_shard(tmp_path, seed=59)
    out = tmp_path / "run"
    common = (
        "--iterations", "1",
        "--steps", "2",
        "--profile", "small",
        "--seed", "3",
        "--device", "cpu",
        "--torch-threads", "1",
        "--test-er",
        "--test-er-cases", "4",
    )

    run_train(out, shard, *common)
    log_path = out / "test_access.log"
    assert log_path.is_file(), "test_access.log yazilmadi"
    lines = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 1
    assert lines[0]["label"] == "primary"
    assert lines[0]["split"] == "test"
    assert lines[0]["count"] == 4
    assert lines[0]["er"] is not None
    assert lines[0]["timestamp"]

    run_train(out, shard, *common)
    lines = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 2
    assert lines[1]["label"] == "exploratory"
    assert lines[1]["access_index"] == 2


# --------------------------------------------------------------------------- vektor TD


def test_vector_td_lambda_one_equals_monte_carlo() -> None:
    """``lam = 1.0`` vektor TD, tek-sicak MC hedefine **tam** esit olmali (F6-17)."""
    import targets

    rng = np.random.default_rng(0)
    n = 9
    probs = rng.random((n, 6))
    probs /= probs.sum(axis=1, keepdims=True)

    for winner in (1, -1):
        for result_type in (1, 2, 3):
            terminal = targets.exclusive_target(winner, result_type, winner)
            y = train_v2.td_lambda_targets_exclusive(probs, terminal, 1.0)
            for t in range(n):
                # t kararindaki oyuncu: terminale (n - t) adim var; cift -> kazanan.
                mover = winner if (n - t) % 2 == 0 else -winner
                expected = targets.exclusive_target(winner, result_type, mover)
                assert np.allclose(y[t], expected), (winner, result_type, t)


def test_flip_is_involution() -> None:
    rng = np.random.default_rng(1)
    p = rng.random((5, 6))
    assert np.allclose(train_v2.flip_exclusive(train_v2.flip_exclusive(p)), p)
    assert np.allclose(train_v2.flip_exclusive(p).sum(axis=-1), p.sum(axis=-1))


def test_td_lambda_zero_uses_next_state() -> None:
    """``lam = 0`` -> hedef yalnizca bir sonraki durumun tahmini (isaret cevrilmis)."""
    rng = np.random.default_rng(2)
    n = 4
    probs = rng.random((n, 6))
    probs /= probs.sum(axis=1, keepdims=True)
    terminal = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    y = train_v2.td_lambda_targets_exclusive(probs, terminal, 0.0)
    for t in range(n - 1):
        assert np.allclose(y[t], train_v2.flip_exclusive(probs[t + 1]))
    assert np.allclose(y[n - 1], train_v2.flip_exclusive(terminal))
