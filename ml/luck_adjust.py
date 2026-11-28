"""Sans-duzeltilmis kafa kafaya (H2H) para oyunu olcumu - Faz 8 Adim A1 (F8-01).

**Sorun.** Kaba ppg olcumu zar gurultusunu tasir: 4400 oyunluk bir kosuda
standart hata ~0,02 ppg. bgsage ayni guveni ~40 kat daha az oyunla elde
ediyor (SE 0,15053 -> 0,02426, 512 oyun). Fark, **kontrol degiskeni**
(control variate) yontemidir: her zar olayinin katkisi kendi alternatiflerine
gore merkezlenir ve toplam "sans" oyundan dusulur.

**Matematik** (bgsage ``H2H_LUCK_ADJUST.md``). ``H_t`` zar olayindan onceki
gecmis, ``R_t`` gerceklesen zar, ``p_t(r)`` zar yasasi. Her olasi zar icin
**A'nin puanindan** bir skor tanimlanir::

    q_t(H_t, r) = s_t * c_t * e_t(r)
    s_t = +1 (A atiyor) / -1 (B atiyor)
    c_t = hamle-zamani kup degeri (kupsuz oyunda 1)
    e_t(r) = referans politikanin tercih ettigi hamleden sonraki devam equity'si
             (atanin bakis acisindan)

    qbar_t = sum_r p_t(r) q_t(H_t, r)      (21 sirasiz zar; cift 1/36, diger 2/36)
    D_t    = q_t(H_t, R_t) - qbar_t
    L      = sum_t D_t
    Z      = Y - beta * L,   beta = 1

``E[D_t | H_t] = 0`` oldugu icin ``E[Z] = E[Y] = mu``: duzeltme **yansizdir**,
referans zayif olsa bile. Kazanc, ``2*Cov(Y,L) > Var(L)`` oldugunda gelir.

**Kritik kural.** Ayni tablo girdisi hem gerceklesen zar hem de ortalamaya
katki icin kullanilir. Gerceklesen zarda **oynanan** hamleyi kullanmak
``sum_r p_t(r)[q_oynanan(r) - q_referans(r)]`` kadar yanlilik ekler; bu terim
ayni degerlendiriciyle bile sifirdan farkli olabilir. Bu yuzden tablo
tamamen referans politika ile kurulur.

**Kupsuz oyun.** ``ml/vs_gnubg.py`` kupsuz para oyunu oynar; ``c_t = 1``.
Kup agaci (Adim D) geldiginde ``c_t`` hamle-zamani kup degerine baglanir.

**Referans.** Sabit ve ucuz bir referans: mevcut en iyi modelin **0-ply deger
kafasi**. Hamle secimi ve devam degeri ayni cagridan gelir. Referans ve
``beta`` olcumden **once** sabitlenir (bgsage: "freeze the choice for the
measurement run"); ``beta*`` yalniz bilgi amacli raporlanir.

**Birim.** Ayni zar dizisinin iki rengi (cift) bagimsiz birimdir. Istatistik
cift ortalamalari uzerinden hesaplanir; ``mean(cift ortalamalari)`` oyun
duzeyindeki ortalama ile **aynen** aynidir, yalnizca standart hata kumelenmis
(clustered) olur.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import er_paths  # noqa: E402
import gnubg_er  # noqa: E402
import ppg_measure  # noqa: E402
import vs_gnubg  # noqa: E402
from tools import reference_gen as refgen  # noqa: E402

LUCK_VERSION = 1
LUCK_PATH = "ml/artifacts/luck_adjust.json"
LUCK_MD_PATH = "ml/artifacts/luck_adjust.md"

#: Kontrol degiskeni katsayisi. ``L`` zaten puan cinsinden oldugu icin 1.
DEFAULT_BETA = 1.0

#: Referans politika secenekleri. ``search1`` en guclu (ve en pahali) referans.
REFERENCE_PATHS = ("value", "policy", "search1")

#: Rakip modlari (gorev emri: self-play, gnubg, ileride XG).
OPPONENTS = ("gnubg", "self")

#: Bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
BOOTSTRAP_RESAMPLES = 20000

#: Bootstrap tohumu (``vs_gnubg`` ile ayni aile).
BOOTSTRAP_SEED = 20261127

#: Denetim noktasi bicim surumu.
CHECKPOINT_VERSION = 1

#: %95 guven araligi carpani.
Z95 = 1.96


class LuckError(RuntimeError):
    """Sans-duzeltmesi yapilamadi."""


# ----------------------------------------------------------------------
# Zar tablosu
# ----------------------------------------------------------------------


def _dice_list(d1: int, d2: int) -> list[int]:
    """``refgen.legal_after_states`` icin zar listesi (cift ise dort kez)."""
    return [d1, d1, d1, d1] if d1 == d2 else [d1, d2]


def roll_table(
    scorer: gnubg_er.OnnxScorer,
    case: dict[str, Any],
    *,
    ref_path: str = "value",
) -> list[float]:
    """21 zar icin referans devam equity'si (**atanin** bakis acisindan).

    ``case`` ``vs_gnubg._case`` bicimindedir: ``board``, ``turn``, ``dice``,
    ``whiteOff``, ``blackOff``, ``afterStates``. Donen liste
    ``er_paths.DICE_ROLLS`` sirasindadir.

    * Terminal hamle -> kesin puan (``er_paths.terminal_equity``).
    * Zorunlu pas (hamle yok) -> ayni tahta, rakip atiyor:
      ``-V_rakip(tahta)``.
    * Diger -> referansin tercih ettigi afterstate'in devam degeri
      ``-V_rakip(afterstate)``.

    **Donus kurali.** ``gnubg_er.vectorize(..., perspective=P)`` vektoru P'nin
    taslarina gore kurar ve model **atandaki** oyuncunun degerini verir. Bir
    hamleden sonra sira rakibe gectigi icin devam degeri
    ``-V_rakip(afterstate)`` olur. Bu, ``er_paths.search1_values`` icindeki
    ``V1(a) = -E[max_o V_o(o)]`` ile **ayni** sozlesmedir.
    """
    if ref_path not in REFERENCE_PATHS:
        raise LuckError("ref_path %s olmali: %r" % (REFERENCE_PATHS, ref_path))

    turn = int(case["turn"])
    opponent = -turn
    board = case["board"]
    white_off = int(case["whiteOff"])
    black_off = int(case["blackOff"])

    spans: list[tuple[int, int] | None] = []
    flat: list[tuple[Any, int, int]] = []
    per_roll_states: list[list[tuple[Any, int, int]]] = []
    for (d1, d2) in er_paths.DICE_ROLLS:
        max_steps, states = refgen.legal_after_states(
            board, turn, _dice_list(d1, d2), white_off, black_off
        )
        if max_steps == 0 or not states:
            spans.append(None)
            per_roll_states.append([])
            continue
        ordered = sorted(states)
        start = len(flat)
        flat.extend(ordered)
        spans.append((start, len(flat)))
        per_roll_states.append(ordered)

    # Tek toplu cagri: 21 zar x aday sayisi vektor bir kerede degerlendirilir.
    # ``search1`` referansi kendi toplu cagrilarini yapar; burada bosuna
    # degerlendirme yapilmaz.
    vectors = (
        []
        if ref_path == "search1"
        else [gnubg_er.vectorize(b, w, k, perspective=opponent) for (b, w, k) in flat]
    )
    values = scorer.values(vectors) if vectors else []
    logits = (
        scorer.logits(vectors) if (vectors and ref_path == "policy") else []
    )

    out: list[float] = []
    for index, span in enumerate(spans):
        if span is None:
            v = scorer.values(
                [gnubg_er.vectorize(board, white_off, black_off, perspective=opponent)]
            )[0]
            out.append(-float(v))
            continue
        start, end = span
        if ref_path == "search1":
            # 1-ply referans: her aday icin rakibin en iyi yaniti da hesaba katilir.
            sub = {
                "turn": turn,
                "afterStates": [
                    {"board": list(b), "whiteOff": w, "blackOff": k}
                    for (b, w, k) in per_roll_states[index]
                ],
            }
            sub_values, _ = er_paths.search1_values(scorer, sub)
            best = max(range(len(sub_values)), key=lambda j: sub_values[j])
            out.append(float(sub_values[best]))
            continue
        # Devam degeri = -V_rakip; en iyi hamle bunu **en kucuk** yapan.
        if ref_path == "policy":
            best = max(range(start, end), key=lambda j: logits[j])
        else:
            best = min(range(start, end), key=lambda j: values[j])
        b, w, k = flat[best]
        exact = er_paths.terminal_equity(b, w, k, turn)
        out.append(float(exact) if exact is not None else -float(values[best]))
    return out


def roll_correction(table: Sequence[float], dice: Sequence[int]) -> float:
    """``D_t = q(R_t) - qbar`` (atanin bakis acisindan, kupsuz)."""
    if len(table) != len(er_paths.DICE_ROLLS):
        raise LuckError(
            "tablo %d girdi olmali, %d bulundu"
            % (len(er_paths.DICE_ROLLS), len(table))
        )
    key = (int(min(dice[0], dice[1])), int(max(dice[0], dice[1])))
    try:
        index = er_paths.DICE_ROLLS.index(key)
    except ValueError as exc:  # pragma: no cover - cagri sozlesmesi
        raise LuckError("gecersiz zar: %r" % (tuple(dice),)) from exc
    total = 0.0
    for weight, value in zip(er_paths.DICE_WEIGHTS, table):
        total += weight * float(value)
    mean = total / float(er_paths.DICE_WEIGHT_SUM)
    return float(table[index]) - mean


class LuckTracker:
    """``vs_gnubg.play_game`` kancasi: oyun basina ``L`` biriktirir."""

    def __init__(
        self,
        scorer: gnubg_er.OnnxScorer,
        our_side: int,
        *,
        ref_path: str = "value",
    ) -> None:
        self.scorer = scorer
        self.our_side = int(our_side)
        self.ref_path = ref_path
        self.total = 0.0
        self.rolls = 0

    def __call__(self, case: dict[str, Any]) -> None:
        turn = int(case["turn"])
        sign = 1.0 if turn == self.our_side else -1.0
        table = roll_table(self.scorer, case, ref_path=self.ref_path)
        self.total += sign * roll_correction(table, case["dice"])
        self.rolls += 1


# ----------------------------------------------------------------------
# Oyun / cift
# ----------------------------------------------------------------------


def play_game_with_luck(
    *,
    dice_seq: Sequence[tuple[int, int]],
    our_side: int,
    our_choose: Callable[[dict[str, Any]], int],
    gnubg_choose: Callable[[dict[str, Any]], int],
    scorer: gnubg_er.OnnxScorer,
    ref_path: str = "value",
    max_plies: int = vs_gnubg.DEFAULT_MAX_PLIES,
    allow_unfinished: bool = True,
) -> dict[str, Any]:
    """``vs_gnubg.play_game`` + sans birikimi."""
    tracker = LuckTracker(scorer, our_side, ref_path=ref_path)
    result = vs_gnubg.play_game(
        dice_seq=dice_seq,
        our_side=our_side,
        our_choose=our_choose,
        gnubg_choose=gnubg_choose,
        max_plies=max_plies,
        allow_unfinished=allow_unfinished,
        on_roll=tracker,
    )
    result["luck"] = float(tracker.total)
    result["rolls"] = int(tracker.rolls)
    return result


def _play_pair_with_luck(
    task: tuple[int, int],
    our_choose: Callable[[dict[str, Any]], int],
    gnubg_choose: Callable[[dict[str, Any]], int],
    scorer: gnubg_er.OnnxScorer,
    ref_path: str,
    max_plies: int,
) -> tuple[list[float], list[float], list[int], list[bool]]:
    """Bir cifti (ayni zar dizisi, iki renk) oynar; (puan, sans, ply, bitti)."""
    pair, seed = task
    rng = np.random.default_rng([int(seed), int(pair)])
    dice_seq = vs_gnubg._dice_sequence(rng, max_plies)
    scores: list[float] = []
    lucks: list[float] = []
    plies: list[int] = []
    finished: list[bool] = []
    for our_side in (1, -1):
        result = play_game_with_luck(
            dice_seq=dice_seq,
            our_side=our_side,
            our_choose=our_choose,
            gnubg_choose=gnubg_choose,
            scorer=scorer,
            ref_path=ref_path,
            max_plies=max_plies,
            allow_unfinished=True,
        )
        scores.append(float(result["score"]))
        lucks.append(float(result["luck"]))
        plies.append(int(result["plies"]))
        finished.append(bool(result["finished"]))
    return scores, lucks, plies, finished


_WORKER: dict[str, Any] = {}


def _init_worker(
    model_path: str,
    path: str,
    gnubg: str | None,
    gnubg_plies: int,
    max_plies: int,
    ref_path: str,
    opponent: str = "gnubg",
) -> None:
    scorer = gnubg_er.OnnxScorer(Path(model_path), intra_op_threads=1)
    our_choose = vs_gnubg._our_chooser(scorer, path)
    if opponent == "self":
        session = None
        opponent_choose = our_choose
    else:
        exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()
        session = gnubg_er.GnubgSession(
            exe, plies=gnubg_plies, timeout=300, persistent=True
        )
        opponent_choose = vs_gnubg._gnubg_chooser(session, gnubg_plies)
    _WORKER.update(
        session=session,
        scorer=scorer,
        our_choose=our_choose,
        gnubg_choose=opponent_choose,
        max_plies=int(max_plies),
        ref_path=ref_path,
    )


def _worker_play_pair(
    task: tuple[int, int],
) -> tuple[list[float], list[float], list[int], list[bool]]:
    return _play_pair_with_luck(
        task,
        _WORKER["our_choose"],
        _WORKER["gnubg_choose"],
        _WORKER["scorer"],
        _WORKER["ref_path"],
        _WORKER["max_plies"],
    )


# ----------------------------------------------------------------------
# Denetim noktasi
# ----------------------------------------------------------------------


def _checkpoint_key(
    model_path: Path,
    path: str,
    gnubg_plies: int,
    seed: int,
    max_plies: int,
    ref_path: str,
    beta: float,
) -> dict[str, Any]:
    return {
        "checkpointVersion": CHECKPOINT_VERSION,
        "luckVersion": LUCK_VERSION,
        "model": str(model_path),
        "path": str(path),
        "gnubgPlies": int(gnubg_plies),
        "seed": int(seed),
        "maxPlies": int(max_plies),
        "refPath": str(ref_path),
        "beta": float(beta),
    }


def _load_checkpoint(
    checkpoint: Path, key: dict[str, Any]
) -> dict[int, tuple[list[float], list[float], list[int], list[bool]]]:
    if not checkpoint.exists():
        return {}
    done: dict[int, tuple[list[float], list[float], list[int], list[bool]]] = {}
    with checkpoint.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("key") != key:
                raise LuckError(
                    "denetim noktasi farkli bir kosuya ait: %s\n  beklenen: %s\n  bulunan: %s"
                    % (checkpoint, key, record.get("key"))
                )
            done[int(record["pair"])] = (
                [float(v) for v in record["scores"]],
                [float(v) for v in record["lucks"]],
                [int(v) for v in record["plies"]],
                [bool(v) for v in record["finished"]],
            )
    return done


def _append_checkpoint(
    handle,
    key: dict[str, Any],
    pair: int,
    result: tuple[list[float], list[float], list[int], list[bool]],
) -> None:
    scores, lucks, plies, finished = result
    handle.write(
        json.dumps(
            {
                "key": key,
                "pair": int(pair),
                "scores": [float(v) for v in scores],
                "lucks": [float(v) for v in lucks],
                "plies": [int(v) for v in plies],
                "finished": [bool(v) for v in finished],
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    handle.flush()
    os.fsync(handle.fileno())


# ----------------------------------------------------------------------
# Istatistik
# ----------------------------------------------------------------------


def _bootstrap_ci(values: np.ndarray, resamples: int, seed: int) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(resamples, values.size))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(
    pair_scores: Sequence[float],
    pair_lucks: Sequence[float],
    *,
    beta: float = DEFAULT_BETA,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Cift ortalamalari uzerinden ham/duzeltilmis ppg ve standart hatalar.

    ``SE_adj = sqrt((s_Y^2 + beta^2 s_L^2 - 2 beta s_YL) / n)`` (bgsage).
    """
    y = np.asarray(pair_scores, dtype=np.float64)
    l = np.asarray(pair_lucks, dtype=np.float64)
    if y.size != l.size:
        raise LuckError("puan ve sans dizileri ayni uzunlukta olmali")
    n = int(y.size)
    if n < 2:
        raise LuckError("en az 2 cift gerekli: %d" % n)

    z = y - float(beta) * l
    s_y = float(y.std(ddof=1))
    s_l = float(l.std(ddof=1))
    s_z = float(z.std(ddof=1))
    cov = float(np.cov(y, l, ddof=1)[0, 1]) if n > 1 else 0.0
    var_l = s_l * s_l
    var_y = s_y * s_y

    se_raw = s_y / np.sqrt(n)
    se_adj = s_z / np.sqrt(n)
    mean_raw = float(y.mean())
    mean_adj = float(z.mean())

    beta_star = (cov / var_l) if var_l > 0.0 else 0.0
    ratio = (var_y / (s_z * s_z)) if s_z > 0.0 else None
    reduction = (100.0 * (1.0 - se_adj / se_raw)) if se_raw > 0.0 else None
    corr = (
        float(np.corrcoef(y, l)[0, 1]) if (var_y > 0.0 and var_l > 0.0) else None
    )

    raw_low, raw_high = _bootstrap_ci(y, resamples, seed)
    adj_low, adj_high = _bootstrap_ci(z, resamples, seed)

    return {
        "pairs": n,
        "games": 2 * n,
        "beta": float(beta),
        "betaStar": float(beta_star),
        "ppg": mean_raw,
        "ppgStdError": float(se_raw),
        "ppgCiLow": float(mean_raw - Z95 * se_raw),
        "ppgCiHigh": float(mean_raw + Z95 * se_raw),
        "ppgBootstrapCiLow": raw_low,
        "ppgBootstrapCiHigh": raw_high,
        "ppgAdjusted": mean_adj,
        "ppgAdjustedStdError": float(se_adj),
        "ppgAdjustedCiLow": float(mean_adj - Z95 * se_adj),
        "ppgAdjustedCiHigh": float(mean_adj + Z95 * se_adj),
        "ppgAdjustedBootstrapCiLow": adj_low,
        "ppgAdjustedBootstrapCiHigh": adj_high,
        "luckMean": float(l.mean()),
        "luckStd": s_l,
        "luckStdError": float(s_l / np.sqrt(n)),
        "scoreStd": s_y,
        "adjustedStd": s_z,
        "covariance": cov,
        "correlation": corr,
        "varianceRatio": ratio,
        "seReductionPercent": reduction,
        "seReductionFactor": (se_raw / se_adj) if se_adj > 0.0 else None,
    }


# ----------------------------------------------------------------------
# Kosu
# ----------------------------------------------------------------------


def run_luck_match(
    *,
    model_path: Path,
    games: int,
    path: str = "search1",
    gnubg: Path | None = None,
    gnubg_plies: int = 2,
    seed: int = 0,
    max_plies: int = vs_gnubg.DEFAULT_MAX_PLIES,
    workers: int = 1,
    beta: float = DEFAULT_BETA,
    ref_path: str = "value",
    opponent: str = "gnubg",
    margin: float | None = None,
    progress: Callable[[str], None] | None = None,
    checkpoint: Path | None = None,
    restart: bool = False,
) -> dict[str, Any]:
    """``games`` oyun oynar; ham ve sans-duzeltilmis ppg'yi olcer.

    ``opponent``: ``"gnubg"`` (mevcut H2H tabani) veya ``"self"`` (ayni model
    iki renkte). Self-play'de beceri farki **sifirdir**, yani oyun sonucu
    varyansinin neredeyse tamami zardan gelir; kontrol degiskeni bu rejimde
    en yuksek indirgemeyi verir (bgsage: 0,13914 -> 0,01911).
    """
    if games < 2 or games % 2 != 0:
        raise LuckError("games cift ve >= 2 olmali (renk takasi icin)")
    if path not in vs_gnubg.OUR_PATHS:
        raise LuckError("yol %s olmali: %r" % (vs_gnubg.OUR_PATHS, path))
    if ref_path not in REFERENCE_PATHS:
        raise LuckError("ref_path %s olmali: %r" % (REFERENCE_PATHS, ref_path))
    if opponent not in OPPONENTS:
        raise LuckError("opponent %s olmali: %r" % (OPPONENTS, opponent))
    if workers < 1:
        raise LuckError("workers >= 1 olmali")

    pairs = games // 2
    key = _checkpoint_key(
        Path(model_path), path, gnubg_plies, seed, max_plies, ref_path, beta
    )
    done: dict[int, tuple[list[float], list[float], list[int], list[bool]]] = {}
    if checkpoint is not None:
        checkpoint = Path(checkpoint)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        if restart and checkpoint.exists():
            checkpoint.unlink()
        done = _load_checkpoint(checkpoint, key)
        for stale in [p for p in done if p >= pairs]:
            del done[stale]
    resumed = len(done)
    if progress and resumed:
        progress("denetim noktasindan devam: %d/%d cift hazir" % (resumed, pairs))

    tasks = [(pair, seed) for pair in range(pairs) if pair not in done]
    results: list[
        tuple[list[float], list[float], list[int], list[bool]] | None
    ] = [None] * pairs
    for pair, value in done.items():
        results[pair] = value

    handle = checkpoint.open("a", encoding="utf-8") if checkpoint is not None else None
    try:
        if workers == 1:
            scorer = gnubg_er.OnnxScorer(Path(model_path))
            our_choose = vs_gnubg._our_chooser(scorer, path)
            if opponent == "self":
                session = None
                gnubg_choose = our_choose
            else:
                exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()
                session = gnubg_er.GnubgSession(
                    exe, plies=gnubg_plies, timeout=300, persistent=True
                )
                gnubg_choose = vs_gnubg._gnubg_chooser(session, gnubg_plies)
            try:
                for index, task in enumerate(tasks, start=1):
                    result = _play_pair_with_luck(
                        task, our_choose, gnubg_choose, scorer, ref_path, max_plies
                    )
                    results[task[0]] = result
                    if handle is not None:
                        _append_checkpoint(handle, key, task[0], result)
                    if progress and index % 25 == 0:
                        progress("%d/%d cift" % (resumed + index, pairs))
            finally:
                if session is not None:
                    session.close()
        else:
            import multiprocessing as mp  # noqa: PLC0415

            ctx = mp.get_context("spawn")
            with ctx.Pool(
                processes=workers,
                initializer=_init_worker,
                initargs=(
                    str(model_path),
                    path,
                    str(gnubg) if gnubg else None,
                    gnubg_plies,
                    max_plies,
                    ref_path,
                    opponent,
                ),
            ) as pool:
                for index, (task, result) in enumerate(
                    zip(tasks, pool.imap(_worker_play_pair, tasks)), start=1
                ):
                    results[task[0]] = result
                    if handle is not None:
                        _append_checkpoint(handle, key, task[0], result)
                    if progress and index % 25 == 0:
                        progress("%d/%d cift" % (resumed + index, pairs))
    finally:
        if handle is not None:
            handle.close()

    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        raise LuckError("tamamlanmayan ciftler: %d adet" % len(missing))
    filled = [r for r in results if r is not None]

    pair_scores: list[float] = []
    pair_lucks: list[float] = []
    plies_total = 0
    unfinished = 0
    for scores, lucks, plies, finished in filled:
        pair_scores.append((scores[0] + scores[1]) / 2.0)
        pair_lucks.append((lucks[0] + lucks[1]) / 2.0)
        plies_total += sum(plies)
        unfinished += sum(1 for f in finished if not f)

    stats = summarize(pair_scores, pair_lucks, beta=beta)
    report: dict[str, Any] = {
        "luckVersion": LUCK_VERSION,
        "model": str(model_path),
        "path": path,
        "referencePath": ref_path,
        "opponent": opponent,
        "gnubgPlies": int(gnubg_plies) if opponent == "gnubg" else 0,
        "workers": int(workers),
        "seed": int(seed),
        "maxPlies": int(max_plies),
        "meanPlies": plies_total / float(2 * len(filled)),
        "unfinished": unfinished,
        "unfinishedRate": unfinished / float(2 * len(filled)),
        "resumedPairs": int(resumed),
        "checkpoint": str(checkpoint) if checkpoint is not None else None,
        "pairScores": [float(v) for v in pair_scores],
        "pairLucks": [float(v) for v in pair_lucks],
    }
    report.update(stats)
    if margin is not None:
        report["margin"] = float(margin)
        report["verdict"] = ppg_measure.equivalence_verdict(
            report["ppgAdjusted"],
            report["ppgAdjustedCiLow"],
            report["ppgAdjustedCiHigh"],
            float(margin),
        )
        report["verdictRaw"] = ppg_measure.equivalence_verdict(
            report["ppg"],
            report["ppgCiLow"],
            report["ppgCiHigh"],
            float(margin),
        )
    return report


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _tr(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return ("%+." + str(digits) + "f") % value


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Sans-duzeltilmis H2H para oyunu (Faz 8 Adim A1)",
        "",
        "Model: `%s`" % report["model"],
        "Yol: `%s` · rakip: **%s** · referans: `%s`"
        % (
            report["path"],
            (
                "gnubg %d-ply" % report["gnubgPlies"]
                if report.get("opponent", "gnubg") == "gnubg"
                else "self-play"
            ),
            report["referencePath"],
        ),
        "",
        "| Olcum | Ham | Sans-duzeltilmis |",
        "|---|---|---|",
        "| ppg | %s | **%s** |"
        % (_tr(report["ppg"]), _tr(report["ppgAdjusted"])),
        "| Standart hata | %.5f | **%.5f** |"
        % (report["ppgStdError"], report["ppgAdjustedStdError"]),
        "| %%95 GA (1,96 SE) | [%s; %s] | [%s; %s] |"
        % (
            _tr(report["ppgCiLow"]),
            _tr(report["ppgCiHigh"]),
            _tr(report["ppgAdjustedCiLow"]),
            _tr(report["ppgAdjustedCiHigh"]),
        ),
        "| %%95 GA (eslestirilmis bootstrap) | [%s; %s] | [%s; %s] |"
        % (
            _tr(report["ppgBootstrapCiLow"]),
            _tr(report["ppgBootstrapCiHigh"]),
            _tr(report["ppgAdjustedBootstrapCiLow"]),
            _tr(report["ppgAdjustedBootstrapCiHigh"]),
        ),
        "",
        "| Kosul | Deger |",
        "|---|---|",
        "| Oyun / cift | %d / %d |" % (report["games"], report["pairs"]),
        "| Paralel surec | %d |" % report["workers"],
        "| Tohum | %d |" % report["seed"],
        "| beta (sabit) | %.4f |" % report["beta"],
        "| beta* (bilgi) | %.4f |" % report["betaStar"],
        "| Oyun basina ply | %.1f |" % report["meanPlies"],
        "| Bitmeyen oyun | %d (%.4f) |"
        % (report["unfinished"], report["unfinishedRate"]),
        "| Denetim noktasindan gelen cift | %d |" % report["resumedPairs"],
        "",
        "## Varyans indirgeme",
        "",
        "| Olcum | Deger |",
        "|---|---|",
        "| Sans ortalamasi (ppg) | %s |" % _tr(report["luckMean"]),
        "| Sans standart sapmasi | %.4f |" % report["luckStd"],
        "| Puan standart sapmasi | %.4f |" % report["scoreStd"],
        "| Duzeltilmis standart sapma | %.4f |" % report["adjustedStd"],
        "| corr(Y, L) | %s |"
        % ("%.4f" % report["correlation"] if report["correlation"] is not None else "-"),
        "| Varyans orani R = s_Y^2 / s_Z^2 | %s |"
        % (
            "%.3f" % report["varianceRatio"]
            if report["varianceRatio"] is not None
            else "-"
        ),
        "| SE azalmasi | %s |"
        % (
            "%.1f%%" % report["seReductionPercent"]
            if report["seReductionPercent"] is not None
            else "-"
        ),
        "| SE kazanci (kat) | %s |"
        % (
            "%.2fx" % report["seReductionFactor"]
            if report["seReductionFactor"] is not None
            else "-"
        ),
        "",
    ]
    if "verdict" in report:
        lines += [
            "## Karar (m = %.4f ppg)" % report["margin"],
            "",
            "`equivalence_verdict` (sans-duzeltilmis) -> **%s**" % report["verdict"],
            "",
            "`equivalence_verdict` (ham) -> **%s**" % report["verdictRaw"],
            "",
        ]
    lines += [
        "## Yontem",
        "",
        "Her zar olayinda 21 zar icin referans devam equity'si hesaplanir;",
        "gerceklesen zarin katkisi kendi ortalamasina gore merkezlenir",
        "(`D_t = q(R_t) - qbar_t`). Toplam sans `L` oyundan dusulur:",
        "`Z = Y - beta*L`, `beta = 1`. `E[D_t | H_t] = 0` oldugu icin duzeltme",
        "**yansizdir**; kazanc yalnizca varyanstan gelir.",
        "",
        "Ayni tablo girdisi hem gerceklesen zar hem ortalama icin kullanilir",
        "(oynanan hamle kullanilsaydi yanlilik eklenirdi). Referans ve `beta`",
        "olcumden **once** sabitlendi; `beta*` yalniz bilgi amaclidir.",
        "",
        "Birim **cift**tir (ayni zar dizisinin iki rengi); `mean(cift",
        "ortalamalari)` oyun duzeyindeki ortalama ile aynidir, standart hata",
        "kumelenmistir.",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luck_adjust",
        description="Sans-duzeltilmis H2H para oyunu olcumu - Faz 8 Adim A1",
    )
    parser.add_argument("--model", default=vs_gnubg.DEFAULT_MODEL)
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--path", default="search1", choices=list(vs_gnubg.OUR_PATHS))
    parser.add_argument("--gnubg", default=None)
    parser.add_argument("--gnubg-plies", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-plies", type=int, default=vs_gnubg.DEFAULT_MAX_PLIES)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--beta", type=float, default=DEFAULT_BETA)
    parser.add_argument("--ref-path", default="value", choices=list(REFERENCE_PATHS))
    parser.add_argument("--opponent", default="gnubg", choices=list(OPPONENTS))
    parser.add_argument("--margin", type=float, default=None)
    parser.add_argument("--out", default=LUCK_PATH)
    parser.add_argument("--markdown", default=LUCK_MD_PATH)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    progress = None if args.quiet else (lambda msg: print(msg, flush=True))
    report = run_luck_match(
        model_path=Path(args.model),
        games=int(args.games),
        path=args.path,
        gnubg=Path(args.gnubg) if args.gnubg else None,
        gnubg_plies=int(args.gnubg_plies),
        seed=int(args.seed),
        max_plies=int(args.max_plies),
        workers=int(args.workers),
        beta=float(args.beta),
        ref_path=args.ref_path,
        opponent=args.opponent,
        margin=args.margin,
        progress=progress,
        checkpoint=Path(args.checkpoint) if args.checkpoint else None,
        restart=bool(args.restart),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")
    print(
        "ppg %+.4f (SE %.5f) -> duzeltilmis %+.4f (SE %.5f), SE azalmasi %s"
        % (
            report["ppg"],
            report["ppgStdError"],
            report["ppgAdjusted"],
            report["ppgAdjustedStdError"],
            (
                "%.1f%%" % report["seReductionPercent"]
                if report["seReductionPercent"] is not None
                else "-"
            ),
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
