"""Ogrenme egrisi icin **etiketli havuz** - Faz 7-R adim 0, madde 2.

Neden ayri modul. ``learning_curve.py`` egriyi cizer ama gercek egitim hattina
bagli degildi (``main()`` ``SystemExit`` atiyordu). Bu modul o hatti kurar:

1. Oyunlar oynanir (``corpus2._play_game``, model politika argmax'i ile) ve
   her karar pozisyonu ``gameId`` ile kaydedilir.
2. Her pozisyonun **tum** adaylari gnubg 2-ply ``eval`` ile etiketlenir
   (``GnubgSession.eval_afterstates``). Tek referans: egitim hedefi de,
   ER olcumu de ayni tablodan gelir.
3. Bolum **oyun duzeyinde** yapilir: held-out oyunlar egitimde gorunmez.
4. Havuz ``.npz`` olarak yazilir; ``make_train_fn`` ondan gercek bir
   ``TrainFn`` uretir.

Neden ``eval`` ve ``hint`` degil. ``hint`` en fazla ``HINT_MOVE_CAP = 10``
hamle dondurur (R-17), yani adaylarin cogu etiketsiz kalir ve ER
hesaplanamaz. ``eval`` her afterstate icin tam tablo verir; boylece
"modelin sectigi adayin equity'si" her zaman bilinir.

Neden oyun duzeyinde bolum. Ayni oyunun pozisyonlari guclu korelidir; pozisyon
duzeyinde bolum sizinti uretir (F7-12). Kume bootstrap'i da oyun duzeyinde
yapilir (``learning_curve.fit_log_slope(cluster=True)``).
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import corpus2  # noqa: E402
import gnubg_distill  # noqa: E402
import gnubg_er  # noqa: E402

#: Havuz surumu (semada degisiklik olursa artar).
POOL_VERSION = 1

#: Varsayilan havuz yolu.
POOL_PATH = "ml/artifacts/curve_pool.npz"

#: Varsayilan oyun sayisi (egitim + held-out).
DEFAULT_GAMES = 60

#: Held-out oyun sayisi (oyun duzeyinde, egitimde gorunmez).
DEFAULT_HELD_OUT_GAMES = 12

#: gnubg hakem derinligi.
DEFAULT_PLIES = 2

#: Oyun basina en fazla hamle (``corpus2.MAX_GAME_PLIES`` ile ayni).
MAX_GAME_PLIES = 40

#: Bolum etiketleri.
SPLIT_TRAIN = "train"
SPLIT_HELD_OUT = "heldout"

#: ER olcumunde kullanilan bakis acisi (F7-101).
#: ``active``   -- havuzun kendi vektoru (oynayacak tarafin bakisi).
#: ``opponent`` -- ayni fiziksel afterstate'in karsi bakisi (``flip_perspective``).
#: ``both``     -- ikisi birden; ortalama ve asimetri orani da raporlanir.
PERSPECTIVE_ACTIVE = "active"
PERSPECTIVE_OPPONENT = "opponent"
PERSPECTIVE_BOTH = "both"
PERSPECTIVES = (PERSPECTIVE_ACTIVE, PERSPECTIVE_OPPONENT, PERSPECTIVE_BOTH)


class CurvePoolError(RuntimeError):
    """Havuz kurulamadi / okunamadi."""


# ----------------------------------------------------------------------
# Havuz
# ----------------------------------------------------------------------


@dataclass
class CurvePool:
    """Etiketli pozisyon havuzu (ragged aday kumesi + oyun kimligi)."""

    x: np.ndarray
    offsets: np.ndarray
    best: np.ndarray
    y: np.ndarray
    cand_equity: np.ndarray
    game_ids: list[str]
    split: list[str]
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.best.shape[0])

    def candidates(self, i: int) -> np.ndarray:
        return self.x[int(self.offsets[i]) : int(self.offsets[i + 1])]

    def candidate_equities(self, i: int) -> np.ndarray:
        return self.cand_equity[int(self.offsets[i]) : int(self.offsets[i + 1])]

    def indices(self, split: str) -> list[int]:
        return [i for i, s in enumerate(self.split) if s == split]

    def train_indices(self) -> list[int]:
        return self.indices(SPLIT_TRAIN)

    def held_out_indices(self) -> list[int]:
        return self.indices(SPLIT_HELD_OUT)

    def subset(self, indices: Sequence[int]) -> gnubg_distill.PolicyDataset:
        """Verilen pozisyonlardan ``PolicyDataset`` uretir."""
        rows: list[np.ndarray] = []
        offsets: list[int] = [0]
        best: list[int] = []
        y: list[float] = []
        for i in indices:
            block = self.candidates(int(i))
            rows.append(block)
            offsets.append(offsets[-1] + int(block.shape[0]))
            best.append(int(self.best[int(i)]))
            y.append(float(self.y[int(i)]))
        if not rows:
            return gnubg_distill.PolicyDataset(
                x=np.zeros((0, gnubg_er.VECTOR_SIZE), dtype=np.float32),
                offsets=np.zeros((1,), dtype=np.int64),
                best=np.zeros((0,), dtype=np.int32),
                y=np.zeros((0,), dtype=np.float32),
                meta={},
            )
        return gnubg_distill.PolicyDataset(
            x=np.concatenate(rows, axis=0).astype(np.float32),
            offsets=np.asarray(offsets, dtype=np.int64),
            best=np.asarray(best, dtype=np.int32),
            y=np.asarray(y, dtype=np.float32),
            meta={},
        )

    def stats(self) -> dict[str, Any]:
        if len(self) == 0:
            return {"count": 0}
        counts = np.diff(np.asarray(self.offsets, dtype=np.int64))
        train = self.train_indices()
        held = self.held_out_indices()
        return {
            "count": int(len(self)),
            "candidates": int(self.x.shape[0]),
            "candidatesMean": float(np.mean(counts)),
            "candidatesMin": int(np.min(counts)),
            "candidatesMax": int(np.max(counts)),
            "train": len(train),
            "heldOut": len(held),
            "trainGames": len({self.game_ids[i] for i in train}),
            "heldOutGames": len({self.game_ids[i] for i in held}),
            "meanEquity": float(np.mean(np.asarray(self.y, dtype=np.float64))),
        }


def save_pool(pool: CurvePool, path: Path = Path(POOL_PATH)) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        p,
        x=pool.x,
        offsets=pool.offsets,
        best=pool.best,
        y=pool.y,
        cand_equity=pool.cand_equity,
        game_ids=np.asarray(pool.game_ids, dtype="U32"),
        split=np.asarray(pool.split, dtype="U16"),
        meta=np.asarray(json.dumps(pool.meta, sort_keys=True)),
    )


def load_pool(path: Path = Path(POOL_PATH)) -> CurvePool:
    p = Path(path)
    if not p.exists():
        raise CurvePoolError("havuz yok: %s" % p)
    with np.load(p, allow_pickle=False) as data:
        raw = data["meta"]
        text = str(raw.item()) if raw.shape == () else str(raw)
        return CurvePool(
            x=np.asarray(data["x"], dtype=np.float32),
            offsets=np.asarray(data["offsets"], dtype=np.int64),
            best=np.asarray(data["best"], dtype=np.int32),
            y=np.asarray(data["y"], dtype=np.float32),
            cand_equity=np.asarray(data["cand_equity"], dtype=np.float32),
            game_ids=[str(v) for v in data["game_ids"]],
            split=[str(v) for v in data["split"]],
            meta=json.loads(text) if text else {},
        )


# ----------------------------------------------------------------------
# Havuz kurma
# ----------------------------------------------------------------------


def _play_games(
    games: int,
    *,
    model_path: Path | None,
    seed: int,
    max_plies: int = MAX_GAME_PLIES,
) -> list[dict[str, Any]]:
    """``games`` oyun oynar ve karar kayitlarini dondurur."""
    rng = random.Random(seed)
    scorer = gnubg_er.OnnxScorer(Path(model_path)) if model_path else None

    def factory(turn: int) -> Callable[[list[tuple]], tuple]:
        if scorer is None:
            return corpus2._random_chooser(rng)
        return corpus2._model_chooser(scorer, turn)

    records: list[dict[str, Any]] = []
    for i in range(games):
        records.extend(
            corpus2._play_game(
                rng,
                game_id="cp-%03d" % i,
                source="curve",
                chooser_factory=factory,
                max_plies=max_plies,
            )
        )
    return records


def _label_case(
    session: gnubg_er.GnubgSession, case: dict[str, Any]
) -> tuple[list[list[float]], list[float]] | None:
    """Bir vakanin **tum** adaylarini gnubg ``eval`` ile etiketler."""
    turn = int(case["turn"])
    after_states = case["afterStates"]
    if not after_states:
        return None
    tables = session.eval_afterstates([a["board"] for a in after_states], -turn)
    equities = [-gnubg_er._equity_at(table, session.plies) for table in tables]
    vectors = [
        gnubg_er.vectorize(
            a["board"], int(a["whiteOff"]), int(a["blackOff"]), perspective=turn
        )
        for a in after_states
    ]
    return vectors, [float(e) for e in equities]


def _label_game(
    game_id: str,
    records: Sequence[dict[str, Any]],
    session: gnubg_er.GnubgSession,
) -> tuple[list[tuple[list[list[float]], list[float]]], int]:
    """Bir oyunun tum karar noktalarini etiketler; (etiketler, atlanan)."""
    out: list[tuple[list[list[float]], list[float]]] = []
    skipped = 0
    for k, record in enumerate(records):
        case = corpus2._case_from_record(record, "%s-%02d" % (game_id, k))
        if case is None:
            skipped += 1
            continue
        labeled = _label_case(session, case)
        if labeled is None:
            skipped += 1
            continue
        vectors, equities = labeled
        if len(vectors) < 2:
            skipped += 1
            continue
        out.append((vectors, equities))
    return out, skipped


_LABEL_WORKER: dict[str, Any] = {}


def _init_label_worker(gnubg: str, plies: int, timeout: int, persistent: bool) -> None:
    _LABEL_WORKER["session"] = gnubg_er.GnubgSession(
        Path(gnubg), plies=plies, timeout=timeout, persistent=persistent
    )


def _worker_label_game(
    task: tuple[str, Sequence[dict[str, Any]]],
) -> tuple[list[tuple[list[list[float]], list[float]]], int]:
    game_id, records = task
    return _label_game(game_id, records, _LABEL_WORKER["session"])


def build_pool(
    *,
    games: int = DEFAULT_GAMES,
    held_out_games: int = DEFAULT_HELD_OUT_GAMES,
    model_path: Path | None = None,
    gnubg: Path | None = None,
    plies: int = DEFAULT_PLIES,
    seed: int = 0,
    timeout: int = 120,
    max_plies: int = MAX_GAME_PLIES,
    persistent: bool = True,
    workers: int = 1,
    progress: Callable[[str], None] | None = None,
) -> CurvePool:
    """Oyun oynar, tum adaylari etiketler ve oyun duzeyinde boler.

    ``persistent`` gnubg'yi tek surecte tutar; etiketleme 3-5 kat hizlanir.
    ``workers > 1`` etiketlemeyi **surec** duzeyinde paralellestirir; her surec
    kendi kalici gnubg oturumunu acar. Sonuc sirasi korunur (``imap``).
    """
    if games <= 0:
        raise CurvePoolError("games > 0 olmali")
    if not 0 < held_out_games < games:
        raise CurvePoolError("0 < held_out_games < games olmali")
    if workers < 1:
        raise CurvePoolError("workers >= 1 olmali")

    records = _play_games(games, model_path=model_path, seed=seed, max_plies=max_plies)
    if progress:
        progress("%d oyun, %d karar kaydi" % (games, len(records)))

    by_game: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_game.setdefault(str(record["gameId"]), []).append(record)

    ordered_games = sorted(by_game)
    held_games = set(ordered_games[:held_out_games])

    exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()

    rows: list[np.ndarray] = []
    offsets: list[int] = [0]
    best: list[int] = []
    y: list[float] = []
    cand_equity: list[float] = []
    game_ids: list[str] = []
    split: list[str] = []
    skipped = 0

    def _consume(game_id: str, labeled: list[tuple[list[list[float]], list[float]]]) -> None:
        nonlocal skipped
        for vectors, equities in labeled:
            rows.append(np.asarray(vectors, dtype=np.float32))
            offsets.append(offsets[-1] + len(vectors))
            best.append(int(np.argmax(equities)))
            y.append(float(max(equities)))
            cand_equity.extend(equities)
            game_ids.append(game_id)
            split.append(SPLIT_HELD_OUT if game_id in held_games else SPLIT_TRAIN)
        if progress and len(best) and len(best) % 50 < len(labeled):
            progress("%d pozisyon etiketlendi" % len(best))

    if workers == 1:
        session = gnubg_er.GnubgSession(
            exe, plies=plies, timeout=timeout, persistent=persistent
        )
        try:
            for game_id in ordered_games:
                labeled, game_skipped = _label_game(game_id, by_game[game_id], session)
                skipped += game_skipped
                _consume(game_id, labeled)
        finally:
            session.close()
    else:
        import multiprocessing as mp  # noqa: PLC0415

        ctx = mp.get_context("spawn")
        tasks = [(game_id, by_game[game_id]) for game_id in ordered_games]
        with ctx.Pool(
            processes=workers,
            initializer=_init_label_worker,
            initargs=(str(exe), plies, timeout, persistent),
        ) as pool:
            for game_id, (labeled, game_skipped) in zip(
                ordered_games, pool.imap(_worker_label_game, tasks)
            ):
                skipped += game_skipped
                _consume(game_id, labeled)

    if not best:
        raise CurvePoolError("hicbir pozisyon etiketlenemedi")

    meta = {
        "poolVersion": POOL_VERSION,
        "games": int(games),
        "heldOutGames": int(held_out_games),
        "plies": int(plies),
        "seed": int(seed),
        "maxPlies": int(max_plies),
        "model": str(model_path) if model_path else None,
        "gnubg": str(exe),
        "labeled": len(best),
        "skipped": int(skipped),
        "license": (
            "gnubg GPL lisanslidir. Bu havuzun etiketleri yalnizca arastirma ve "
            "olcum icindir; urun dagitimi oncesinde lisans netlestirilmelidir."
        ),
    }
    return CurvePool(
        x=np.concatenate(rows, axis=0).astype(np.float32),
        offsets=np.asarray(offsets, dtype=np.int64),
        best=np.asarray(best, dtype=np.int32),
        y=np.asarray(y, dtype=np.float32),
        cand_equity=np.asarray(cand_equity, dtype=np.float32),
        game_ids=game_ids,
        split=split,
        meta=meta,
    )


# ----------------------------------------------------------------------
# Gercek egitim hatti
# ----------------------------------------------------------------------


def _pad(pool: CurvePool, indices: Sequence[int]) -> tuple[np.ndarray, np.ndarray, int]:
    counts = [int(pool.offsets[i + 1] - pool.offsets[i]) for i in indices]
    width = max(counts) if counts else 0
    x = np.zeros((len(indices), width, gnubg_er.VECTOR_SIZE), dtype=np.float32)
    mask = np.zeros((len(indices), width), dtype=bool)
    for row, i in enumerate(indices):
        block = pool.candidates(int(i))
        k = int(block.shape[0])
        x[row, :k] = block
        mask[row, :k] = True
    return x, mask, width


def _flip_rows(x: np.ndarray) -> np.ndarray:
    """Her satiri karsi bakisa cevirir (``antisymmetry.flip_perspective``)."""
    from antisymmetry import flip_perspective  # noqa: PLC0415

    flat = x.reshape(-1, gnubg_er.VECTOR_SIZE)
    out = np.empty_like(flat)
    for i in range(flat.shape[0]):
        out[i] = np.asarray(flip_perspective(flat[i]), dtype=flat.dtype)
    return out.reshape(x.shape)


def measure_er(
    model,
    pool: CurvePool,
    indices: Sequence[int],
    *,
    paths: Sequence[str] = ("policy", "value"),
    device: str = "cpu",
    perspective: str = PERSPECTIVE_ACTIVE,
) -> dict[str, list[float]]:
    """Held-out pozisyonlarda **pozisyon duzeyinde** ER kayiplari.

    Referans: havuzdaki gnubg ``eval`` equity'leri. ``policy`` yolu politika
    logit argmax'ini, ``value`` yolu deger kafasi argmax'ini secer. Terminal
    aday yok: havuz yalnizca yasal afterstate'lerden olusur.

    ``perspective`` (F7-101): ``active`` havuzun kendi vektorunu kullanir;
    ``opponent`` ayni fiziksel afterstate'i karsi bakistan besler ve equity'leri
    isaret cevirir. **Tek bakisli ER, renk takasi kusurunu gizler**: havuzdaki
    afterstate'ler her zaman *oynayan* tarafin bakisindadir, dolayisiyla
    ``active`` olcumu karsi bakisi hic sinamaz. Iki bakisi birlikte olcmek icin
    ``measure_er_both`` kullanin.
    """
    import torch  # noqa: PLC0415

    if perspective not in (PERSPECTIVE_ACTIVE, PERSPECTIVE_OPPONENT):
        raise CurvePoolError("bilinmeyen bakis: %s" % perspective)
    if not indices:
        return {p: [] for p in paths}
    x, mask, width = _pad(pool, indices)
    if width <= 0:
        return {p: [] for p in paths}
    if perspective == PERSPECTIVE_OPPONENT:
        x = _flip_rows(x)

    model.eval()
    losses: dict[str, list[float]] = {p: [] for p in paths}
    with torch.no_grad():
        for start in range(0, len(indices), 64):
            stop = min(start + 64, len(indices))
            xt = torch.from_numpy(x[start:stop]).to(device)
            mt = torch.from_numpy(mask[start:stop]).to(device)
            out = model(xt.reshape(-1, gnubg_er.VECTOR_SIZE))
            probs = out[0].reshape(stop - start, width, -1)
            logits = out[1].reshape(stop - start, width).masked_fill(~mt, -1e9)
            values = gnubg_distill.equity_of_probs(probs)
            for row in range(stop - start):
                i = int(indices[start + row])
                equities = pool.candidate_equities(i)
                if perspective == PERSPECTIVE_OPPONENT:
                    equities = -equities
                k = int(equities.shape[0])
                best_equity = float(np.max(equities))
                for path in paths:
                    if path == "policy":
                        pick = int(torch.argmax(logits[row, :k]).to("cpu"))
                    elif path == "value":
                        pick = int(torch.argmax(values[row, :k]).to("cpu"))
                    else:
                        raise CurvePoolError("bilinmeyen yol: %s" % path)
                    losses[path].append(best_equity - float(equities[pick]))
    return losses


def measure_er_both(
    model,
    pool: CurvePool,
    indices: Sequence[int],
    *,
    paths: Sequence[str] = ("policy", "value"),
    device: str = "cpu",
) -> dict[str, list[float]]:
    """Iki bakisli ER (F7-101).

    Donen anahtarlar her yol icin: ``<yol>`` (oynayan bakis), ``<yol>Opp``
    (karsi bakis) ve ``<yol>Mean`` (ikisinin pozisyon duzeyinde ortalamasi).
    ``Mean`` R-D'nin dogru olcutudur: artirim tek bakisi kotulestirip digerini
    duzeltiyorsa, karar ortalamaya gore verilir.
    """
    active = measure_er(model, pool, indices, paths=paths, device=device)
    opponent = measure_er(
        model,
        pool,
        indices,
        paths=paths,
        device=device,
        perspective=PERSPECTIVE_OPPONENT,
    )
    out: dict[str, list[float]] = {}
    for path in paths:
        out[path] = active[path]
        out[path + "Opp"] = opponent[path]
        out[path + "Mean"] = [
            (a + b) / 2.0 for a, b in zip(active[path], opponent[path])
        ]
    return out


def perspective_asymmetry(report: dict[str, list[float]], path: str = "value") -> float:
    """Iki bakis ER'sinin orani (buyuk/kucuk); 1.0 = tam simetrik."""
    active = float(np.mean(report[path])) if report.get(path) else 0.0
    opponent = float(np.mean(report[path + "Opp"])) if report.get(path + "Opp") else 0.0
    lo, hi = min(active, opponent), max(active, opponent)
    if lo <= 0.0:
        return float("inf") if hi > 0.0 else 1.0
    return hi / lo


def make_train_fn(
    pool: CurvePool,
    *,
    epochs: int = 20,
    batch: int = 64,
    lr: float = 1e-3,
    device: str = "cpu",
    value_weight: float = gnubg_distill.DEFAULT_VALUE_WEIGHT,
    profile: str = "medium",
    paths: Sequence[str] = ("policy", "value"),
    progress: Callable[[str], None] | None = None,
) -> Callable[[int, int], dict[str, Any]]:
    """``learning_curve.TrainFn`` sozlesmesini saglayan gercek egitim hatti.

    **Epoch-sabit, veri-degisken** (R-D tasarim karari): adim sayisi
    ``epochs * N / batch`` olarak hesaplanir, yani veri hacmi degistiginde
    egitilen **epoch** sayisi sabit kalir. Kural 7: tek degisen sey veridir.

    Her cagri **sifirdan** bir model kurar (``profile``), egitir ve held-out
    ER'yi olcer. ``inSampleLoss`` son egitim kaybidir; basari sayilmaz
    (Kural 5).
    """
    import model as model_mod  # noqa: PLC0415

    train_all = pool.train_indices()
    held_out = pool.held_out_indices()
    if not train_all:
        raise CurvePoolError("egitim bolumu bos")
    if not held_out:
        raise CurvePoolError("held-out bolumu bos")

    def train_fn(positions: int, seed: int) -> dict[str, Any]:
        n = int(positions)
        if n <= 0:
            raise CurvePoolError("positions > 0 olmali")
        if n > len(train_all):
            raise CurvePoolError(
                "havuzda %d egitim pozisyonu var, %d istendi" % (len(train_all), n)
            )
        rng = np.random.default_rng(int(seed))
        picked = rng.permutation(len(train_all))[:n]
        indices = [train_all[int(i)] for i in picked]

        net = model_mod.build_model(profile=profile, output_version=2, seed=int(seed))
        dataset = pool.subset(indices)
        steps = max(1, int(round(epochs * n / float(batch))))
        if progress:
            progress("  egitim: %d pozisyon, %d adim" % (n, steps))
        result = gnubg_distill.train_policy_head(
            net,
            dataset,
            steps=steps,
            lr=lr,
            batch=batch,
            device=device,
            seed=int(seed),
            value_weight=value_weight,
        )
        losses = measure_er(net, pool, held_out, paths=paths, device=device)
        game_ids = {path: [pool.game_ids[i] for i in held_out] for path in paths}
        policy_mean = (
            float(np.mean(losses["policy"])) if losses.get("policy") else float("nan")
        )
        return {
            "losses": losses,
            "gameIds": game_ids,
            "slope": None,
            "mae": None,
            "inSampleLoss": result.get("lastLoss"),
            "inSampleUnit": (
                "karisik: capraz-entropi (nat/pozisyon) + %.2f*MSE (equity^2)"
                % float(value_weight)
            ),
            "heldOutLoss": policy_mean,
            "note": "epochs=%d batch=%d steps=%d profile=%s" % (epochs, batch, steps, profile),
        }

    return train_fn


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser():
    import argparse  # noqa: PLC0415

    p = argparse.ArgumentParser(
        prog="curve_pool",
        description="Ogrenme egrisi icin etiketli havuz - Faz 7-R adim 0",
    )
    sub = p.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="oyun oyna, etiketle, havuzu yaz")
    build.add_argument("--games", type=int, default=DEFAULT_GAMES)
    build.add_argument("--held-out-games", type=int, default=DEFAULT_HELD_OUT_GAMES)
    build.add_argument("--model", default=None, help="self-play modeli (ONNX)")
    build.add_argument("--gnubg", default=None)
    build.add_argument("--plies", type=int, default=DEFAULT_PLIES)
    build.add_argument("--seed", type=int, default=0)
    build.add_argument("--timeout", type=int, default=120)
    build.add_argument(
        "--no-persistent",
        dest="persistent",
        action="store_false",
        help="gnubg'yi her cagride yeniden baslat (yavas, varsayilan degil)",
    )
    build.add_argument("--out", default=POOL_PATH)
    build.add_argument(
        "--workers",
        type=int,
        default=1,
        help="etiketleme icin paralel surec sayisi (her surec kendi gnubg oturumu)",
    )
    build.add_argument("--quiet", action="store_true")

    show = sub.add_parser("show", help="havuz ozeti")
    show.add_argument("--pool", default=POOL_PATH)

    er = sub.add_parser("measure-er", help="held-out ER (tek veya iki bakis)")
    er.add_argument(
        "--model",
        required=True,
        nargs="+",
        help="ONNX model yolu (birden fazla verilirse karsilastirma tablosu basilir)",
    )
    er.add_argument("--pool", default=POOL_PATH)
    er.add_argument(
        "--perspective",
        choices=PERSPECTIVES,
        default=PERSPECTIVE_BOTH,
        help="active | opponent | both (varsayilan: both)",
    )
    er.add_argument("--limit", type=int, default=0, help="ilk N held-out pozisyon")
    er.add_argument("--out", default=None, help="JSON cikti yolu (opsiyonel)")
    return p


def _load_onnx_model(path: Path):
    """ONNX modelini ``measure_er`` sozlesmesine sarar (torch ciktilari)."""
    import onnxruntime as ort  # noqa: PLC0415
    import torch  # noqa: PLC0415

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    class _OnnxModel:
        def eval(self) -> None:
            return None

        def __call__(self, x):
            arr = x.detach().cpu().numpy() if hasattr(x, "detach") else np.asarray(x)
            return [torch.from_numpy(o) for o in session.run(None, {input_name: arr})]

    return _OnnxModel()


def measure_summary(
    model_path: Path,
    pool: CurvePool,
    indices: Sequence[int],
    *,
    perspective: str = PERSPECTIVE_BOTH,
) -> dict[str, Any]:
    """Tek model icin ER ozeti (``measure-er`` ciktisi)."""
    model = _load_onnx_model(model_path)
    if perspective == PERSPECTIVE_BOTH:
        report = measure_er_both(model, pool, indices)
    else:
        report = measure_er(model, pool, indices, perspective=perspective)
    summary: dict[str, Any] = {
        "model": str(model_path),
        "positions": len(indices),
        "perspective": perspective,
    }
    for key, values in report.items():
        summary[key] = float(np.mean(values)) if values else None
    if perspective == PERSPECTIVE_BOTH:
        summary["policyAsymmetry"] = perspective_asymmetry(report, "policy")
        summary["valueAsymmetry"] = perspective_asymmetry(report, "value")
    return summary


def _model_label(path: str) -> str:
    """Karsilastirma tablosunda modeli **kosu diziniyle** birlikte adlandirir.

    Kosu dizinleri ayni dosya adini (`model_v10.onnx`) tekrar ettigi icin
    yalniz dosya adi kullanmak tabloyu okunamaz kilar. ONNX'ler tipik olarak
    `<kosu>/onnx/model_vN.onnx` altinda durur; bu yuzden `onnx` ara dizini
    atlanir ve kosu dizini one alinir.
    """
    p = Path(path)
    parts = [q for q in p.parts if q not in (".", "")]
    if len(parts) >= 3 and parts[-2] == "onnx":
        return "%s/%s" % (parts[-3], parts[-1])
    if len(parts) >= 2:
        return "%s/%s" % (parts[-2], parts[-1])
    return p.name


def build_er_markdown(rows: Sequence[dict[str, Any]], pool_path: str) -> str:
    """``measure-er`` satirlarindan karsilastirma tablosu (F7-101)."""
    lines = [
        "# Iki bakisli ER karsilastirmasi (F7-101)",
        "",
        "Havuz: `%s` — %d held-out pozisyon." % (pool_path, rows[0]["positions"] if rows else 0),
        "",
        "`ER(+1)` havuzun kendi (oynayan) bakisi, `ER(-1)` karsi bakis, `Ort`",
        "ikisinin ortalamasi. **R-D karari `Ort` sutununa gore verilir**; tek",
        "bakisli ER artirimin takasini goremez.",
        "",
        "| Model | ER(+1) pol | ER(-1) pol | **Ort** pol | ER(+1) deger | ER(-1) deger | **Ort** deger | Asimetri pol/deger |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| `%s` | %.4f | %.4f | **%.4f** | %.4f | %.4f | **%.4f** | %.2fx / %.2fx |"
            % (
                _model_label(r["model"]),
                r.get("policy") or 0.0,
                r.get("policyOpp") or 0.0,
                r.get("policyMean") or 0.0,
                r.get("value") or 0.0,
                r.get("valueOpp") or 0.0,
                r.get("valueMean") or 0.0,
                r.get("policyAsymmetry") or 0.0,
                r.get("valueAsymmetry") or 0.0,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show":
        pool = load_pool(Path(args.pool))
        print(json.dumps(pool.stats(), indent=2, sort_keys=True))
        return 0

    if args.command == "measure-er":
        pool = load_pool(Path(args.pool))
        indices = pool.held_out_indices()
        if args.limit > 0:
            indices = indices[: args.limit]
        rows = [
            measure_summary(
                Path(m), pool, indices, perspective=args.perspective
            )
            for m in args.model
        ]
        payload: Any = rows[0] if len(rows) == 1 else rows
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            if len(rows) > 1:
                out.with_suffix(".md").write_text(
                    build_er_markdown(rows, str(args.pool)), encoding="utf-8"
                )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    pool = build_pool(
        games=args.games,
        held_out_games=args.held_out_games,
        model_path=Path(args.model) if args.model else None,
        gnubg=Path(args.gnubg) if args.gnubg else None,
        plies=args.plies,
        seed=args.seed,
        timeout=args.timeout,
        persistent=args.persistent,
        workers=args.workers,
        progress=None if args.quiet else (lambda m: print(m)),
    )
    save_pool(pool, Path(args.out))
    print(json.dumps(pool.stats(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
