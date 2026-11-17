"""Faz 4 v3 Bolum 6.1/6.2/6.3: replay buffer ve hedef yeniden hesaplama.

Buffer son ``buffer_games`` oyunu tutar. Her iterasyonda deger hedefleri
**mevcut agla** yeniden hesaplanir (Bolum 6.2, forward view TD(lambda)).
Politika hedefleri cevrimdisi olarak ``softmax(Q / tau_train)`` ile uretilir
(Bolum 6.3) ve aga bagli degildir.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np

from shards import (
    DEC_CHOSEN_IS_TERMINAL,
    DEC_IS_LEARNER,
    GameRecord,
    read_shard,
)
from td_lambda import DEFAULT_LAMBDA, td_lambda_targets_masked

VECTOR_SIZE = 221

VALUE_TARGET_TD_LAMBDA = "td_lambda"
VALUE_TARGET_SEARCH_DISTILL = "search_distill"


# ----------------------------------------------------------------------
# Buffer
# ----------------------------------------------------------------------


class ReplayBuffer:
    """Son ``max_games`` oyunu tutan FIFO tampon."""

    def __init__(self, max_games: int = 20000) -> None:
        if max_games <= 0:
            raise ValueError("max_games pozitif olmali")
        self.max_games = int(max_games)
        self._games: deque[GameRecord] = deque()

    def __len__(self) -> int:
        return len(self._games)

    @property
    def games(self) -> list[GameRecord]:
        return list(self._games)

    def add(self, games: Iterable[GameRecord]) -> int:
        """Oyunlari ekler; tasan en eski oyunlar dusurulur. Eklenen sayisini doner."""
        added = 0
        for g in games:
            self._games.append(g)
            added += 1
            while len(self._games) > self.max_games:
                self._games.popleft()
        return added

    def add_shard(self, path: str | Path) -> int:
        _header, games = read_shard(path)
        return self.add(games)

    def add_shard_dir(self, directory: str | Path, pattern: str = "*.bgsp*",
                      recursive: bool = True) -> int:
        """Dizindeki (varsayilan olarak alt dizinler dahil) tum shard'lari ekler."""
        d = Path(directory)
        if not d.is_dir():
            return 0
        paths = sorted(d.rglob(pattern) if recursive else d.glob(pattern))
        added = 0
        for p in paths:
            if p.is_file():
                added += self.add_shard(p)
        return added

    def clear(self) -> None:
        self._games.clear()

    def usable_games(self) -> list[GameRecord]:
        """Egitime uygun (aborted olmayan, en az 2 kararli) oyunlar."""
        return [g for g in self._games if is_usable_game(g)]


def is_usable_game(game: GameRecord) -> bool:
    """``aborted`` oyunlar atlanir (Bolum 6.2)."""
    if game.is_aborted:
        return False
    if len(game.decisions) < 2:
        return False
    if game.cube_value <= 0:
        return False
    if game.winner not in (1, -1):
        return False
    return True


# ----------------------------------------------------------------------
# Deger hedefleri (Bolum 6.2)
# ----------------------------------------------------------------------


@dataclass
class ValueSamples:
    """Deger egitimi icin duzlestirilmis ornekler."""

    x: np.ndarray  # (N, 221) float32
    y: np.ndarray  # (N,) float32
    game_index: np.ndarray  # (N,) int32
    decision_index: np.ndarray  # (N,) int32

    def __len__(self) -> int:
        return int(self.x.shape[0])


def terminal_value(result_points: int, cube_value: int, winner: int) -> float:
    """``z = resultPoints / cubeValue``, kazanan icin pozitif (isaretsiz buyukluk).

    ``td_lambda_targets`` zinciri isareti kendisi cevirdigi icin ``z`` burada
    **isaretsiz** olmalidir. Faz 4/5'te burada ``winner`` ile carpiliyordu; bu,
    siyah (``winner = -1``) kazandiginda tum hedefleri ters ceviriyordu
    (Faz 6 Asama B, F6-07).
    """
    if cube_value <= 0:
        raise ValueError("cube_value pozitif olmali")
    if winner not in (1, -1):
        raise ValueError("winner +1 veya -1 olmali")
    return float(result_points) / float(cube_value)


def _non_terminal_vectors(game: GameRecord) -> np.ndarray | None:
    """``t = 0..T-2`` kararlarinin ``chosenVector`` dizisi (T-1, 221) veya None.

    Son karar (``t = T-1``) terminaldir ve vektoru yoktur (Bolum 6.2).
    """
    rows: list[np.ndarray] = []
    for d in game.decisions[:-1]:
        if d.chosen_vector is None:
            return None
        rows.append(np.asarray(d.chosen_vector, dtype=np.float32))
    if not rows:
        return None
    return np.stack(rows, axis=0)


#: Faz 6 Asama D: ``_non_terminal_vectors`` icin genel ad (``ml/train_v2.py`` kullanir).
non_terminal_vectors = _non_terminal_vectors


def _predict_values(model, x: np.ndarray, device, batch_size: int = 4096) -> np.ndarray:
    """``net(x)`` no-grad; (N,) float32."""
    import torch

    out = np.empty((x.shape[0],), dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            stop = min(start + batch_size, x.shape[0])
            t = torch.from_numpy(x[start:stop]).to(device)
            v = model(t)
            if isinstance(v, tuple):
                v = v[0]
            out[start:stop] = v.reshape(-1).detach().to("cpu").numpy()
    return out


def build_value_samples(
    model,
    games: Sequence[GameRecord],
    *,
    lam: float = DEFAULT_LAMBDA,
    device=None,
    target_mode: str = VALUE_TARGET_TD_LAMBDA,
    batch_size: int = 4096,
) -> ValueSamples:
    """Buffer'daki oyunlar icin deger hedeflerini mevcut agla yeniden hesaplar.

    Zincir **tum** kararlar uzerinden kurulur (rakip kararlar dahil); kayba
    yalnizca ``IsLearner`` kararlar girer (Bolum 6.2).
    """
    if target_mode not in (VALUE_TARGET_TD_LAMBDA, VALUE_TARGET_SEARCH_DISTILL):
        raise ValueError(f"bilinmeyen value_target_mode: {target_mode!r}")

    usable = [g for g in games if is_usable_game(g)]
    if not usable:
        return ValueSamples(
            x=np.zeros((0, VECTOR_SIZE), dtype=np.float32),
            y=np.zeros((0,), dtype=np.float32),
            game_index=np.zeros((0,), dtype=np.int32),
            decision_index=np.zeros((0,), dtype=np.int32),
        )

    # 1) Tum oyunlarin karar vektorlerini topla ve tek seferde tahmin et.
    per_game: list[np.ndarray] = []
    offsets: list[int] = []
    total = 0
    for g in usable:
        vecs = _non_terminal_vectors(g)
        if vecs is None:
            per_game.append(np.zeros((0, VECTOR_SIZE), dtype=np.float32))
        else:
            per_game.append(vecs)
        offsets.append(total)
        total += per_game[-1].shape[0]

    if total == 0:
        return ValueSamples(
            x=np.zeros((0, VECTOR_SIZE), dtype=np.float32),
            y=np.zeros((0,), dtype=np.float32),
            game_index=np.zeros((0,), dtype=np.int32),
            decision_index=np.zeros((0,), dtype=np.int32),
        )

    flat = np.concatenate([v for v in per_game if v.shape[0] > 0], axis=0)
    v_hat_all = _predict_values(model, flat, device, batch_size=batch_size)

    xs: list[np.ndarray] = []
    ys: list[float] = []
    gi: list[int] = []
    di: list[int] = []

    for k, g in enumerate(usable):
        vecs = per_game[k]
        n_hat = vecs.shape[0]  # T - 1
        if n_hat < 1:
            continue

        base = offsets[k]
        v_hat = v_hat_all[base:base + n_hat]

        if target_mode == VALUE_TARGET_SEARCH_DISTILL:
            targets = np.array(
                [d.search_value for d in g.decisions[:n_hat]], dtype=np.float64
            )
        else:
            z = terminal_value(g.result_points, g.cube_value, g.winner)
            is_learner = np.array(
                [bool(d.flags & DEC_IS_LEARNER) for d in g.decisions[:n_hat]], dtype=bool
            )
            targets, _mask = td_lambda_targets_masked(v_hat, z, is_learner, lam)

        for t in range(n_hat):
            d = g.decisions[t]
            if not (d.flags & DEC_IS_LEARNER):
                continue
            if d.flags & DEC_CHOSEN_IS_TERMINAL:
                continue
            if not np.isfinite(targets[t]):
                continue
            xs.append(vecs[t])
            ys.append(float(targets[t]))
            gi.append(k)
            di.append(t)

    if not xs:
        return ValueSamples(
            x=np.zeros((0, VECTOR_SIZE), dtype=np.float32),
            y=np.zeros((0,), dtype=np.float32),
            game_index=np.zeros((0,), dtype=np.int32),
            decision_index=np.zeros((0,), dtype=np.int32),
        )

    return ValueSamples(
        x=np.stack(xs, axis=0).astype(np.float32, copy=False),
        y=np.asarray(ys, dtype=np.float32),
        game_index=np.asarray(gi, dtype=np.int32),
        decision_index=np.asarray(di, dtype=np.int32),
    )


# ----------------------------------------------------------------------
# Politika hedefleri (Bolum 6.3)
# ----------------------------------------------------------------------


@dataclass
class PolicySample:
    """Tek bir uygun karar: ``E`` kumesi ve hedef dagilim."""

    vectors: np.ndarray  # (E, 221) float32
    target: np.ndarray  # (E,) float32, toplam 1
    q: np.ndarray  # (E,) float32

    @property
    def entropy_ratio(self) -> float:
        """Hedef entropisinin ``log|E|``'ye orani (1.0 = tamamen duzgun)."""
        e = int(self.vectors.shape[0])
        if e < 2:
            return 1.0
        p = np.asarray(self.target, dtype=np.float64)
        p = p[p > 0.0]
        h = float(-np.sum(p * np.log(p)))
        return h / float(np.log(e))


def filter_informative(
    samples: Sequence[PolicySample], max_entropy_ratio: float
) -> list[PolicySample]:
    """Hedefi yeterince keskin olmayan kararlari eler.

    ``max_entropy_ratio >= 1`` ise hicbir sey elenmez. Duzgune yakin hedefler
    (``H/log|E| ~ 1``) politika gradyanini bilgi tasimayan bir gurultuye cevirir;
    bu durumda politika terimi deger fonksiyonunu bozar (bkz. ASSUMPTIONS F4-40).
    """
    if max_entropy_ratio >= 1.0:
        return list(samples)
    return [s for s in samples if s.entropy_ratio <= max_entropy_ratio]


def policy_targets_from_q(q: np.ndarray, tau: float) -> np.ndarray:
    """``softmax(q / tau)``; sayisal kararlilik icin max cikarilir."""
    if tau <= 0.0:
        raise ValueError("tau pozitif olmali")
    q = np.asarray(q, dtype=np.float64)
    if q.size == 0:
        return np.zeros((0,), dtype=np.float32)
    scaled = q / float(tau)
    scaled = scaled - np.max(scaled)
    e = np.exp(scaled)
    s = float(np.sum(e))
    if not np.isfinite(s) or s <= 0.0:
        return np.full((q.size,), 1.0 / q.size, dtype=np.float32)
    return (e / s).astype(np.float32)


def build_policy_samples(
    games: Sequence[GameRecord],
    *,
    tau_train: float = 0.05,
    min_group: int = 2,
) -> list[PolicySample]:
    """``IsLearner`` ve ``|E| >= min_group`` olan kararlar icin politika ornekleri."""
    out: list[PolicySample] = []
    for g in games:
        if not is_usable_game(g):
            continue
        for d in g.decisions:
            if not (d.flags & DEC_IS_LEARNER):
                continue
            if d.flags & DEC_CHOSEN_IS_TERMINAL:
                continue
            if d.cand_vectors is None or d.q is None:
                continue
            e = int(d.q.shape[0])
            if e < min_group:
                continue
            vecs = np.asarray(d.cand_vectors, dtype=np.float32)
            if vecs.shape != (e, VECTOR_SIZE):
                continue
            out.append(
                PolicySample(
                    vectors=vecs,
                    target=policy_targets_from_q(d.q, tau_train),
                    q=np.asarray(d.q, dtype=np.float32),
                )
            )
    return out


def policy_group_sizes(samples: Sequence[PolicySample]) -> np.ndarray:
    return np.asarray([s.vectors.shape[0] for s in samples], dtype=np.int64)


def uniform_policy_baseline(samples: Sequence[PolicySample]) -> float:
    """Duzgun-baz cizgisi: ortalama ``log|E|`` (Bolum 6.3 izleme)."""
    if not samples:
        return float("nan")
    return float(np.mean([np.log(s.vectors.shape[0]) for s in samples]))


def target_entropy_ratio(samples: Sequence[PolicySample]) -> float:
    """Hedef entropisinin ``log|E|``'ye oraninin ortalamasi (Bolum 6.3 izleme)."""
    if not samples:
        return float("nan")
    ratios: list[float] = []
    for s in samples:
        e = s.vectors.shape[0]
        if e < 2:
            continue
        p = np.asarray(s.target, dtype=np.float64)
        p = p[p > 0.0]
        h = float(-np.sum(p * np.log(p)))
        ratios.append(h / float(np.log(e)))
    if not ratios:
        return float("nan")
    return float(np.mean(ratios))


# ----------------------------------------------------------------------
# Minibatch ornekleme
# ----------------------------------------------------------------------


def sample_indices(n: int, batch: int, rng: np.random.Generator) -> np.ndarray:
    if n <= 0:
        return np.zeros((0,), dtype=np.int64)
    if batch >= n:
        return np.arange(n, dtype=np.int64)
    return rng.choice(n, size=batch, replace=False).astype(np.int64)


def iter_value_batches(
    samples: ValueSamples, batch: int, rng: np.random.Generator
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    n = len(samples)
    if n == 0:
        return
    idx = sample_indices(n, batch, rng)
    yield samples.x[idx], samples.y[idx]


def iter_policy_batches(
    samples: Sequence[PolicySample], batch: int, rng: np.random.Generator
) -> Iterator[list[PolicySample]]:
    n = len(samples)
    if n == 0:
        return
    idx = sample_indices(n, batch, rng)
    yield [samples[int(i)] for i in idx]