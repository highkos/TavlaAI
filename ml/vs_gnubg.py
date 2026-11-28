"""Model vs gnubg 0-ply mac olcumu - Faz 7-R adim 0 (F7-89).

R-D oncesi **taban**: modelin gnubg 0-ply'a karsi kazanma orani ve ppg'si.

Tasarim (kullanicinin adim 0 kosulu):

* **Kupsuz para oyunu** (cubeless money game); ppg = oyun basina puan.
* **Eslestirilmis zar**: her zar dizisi iki kez oynanir.
* **Renk takasi**: ayni zar dizisi bir kez biz beyaz, bir kez biz siyah.
  Boylece zar sansi iki kolda **ayni** olur ve fark yalnizca hamle
  seciminden gelir (Kural 7).
* **gnubg 0-ply**: her adayin 0-ply equity'si, ``argmax``. Bu, merdiven
  olcumundeki "gnubg 0-ply" tanimiyla **ayni**dir.
* **Bizim taraf**: ``policy`` (0-ply ONNX argmax) veya ``search1``
  (1-ply arama). ``search1`` Python'da kosar; C# ile paritesi
  ``ml/artifacts/search1_parity.json`` ile kanitlanmistir (kararli
  vakalarda 357/357, skor MAE 5,4e-8).

Istatistik: ppg icin **eslesmis** fark (ayni zar dizisinin iki rengi
arasindaki fark) kullanilir; GA oyun duzeyinde bootstrap ile hesaplanir.
Eslesmis tasarim, zar gurultusunu buyuk olcude iptal eder.
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
from tools import reference_gen as refgen  # noqa: E402

MATCH_VERSION = 1
MATCH_PATH = "ml/artifacts/vs_gnubg.json"
MATCH_MD_PATH = "ml/artifacts/vs_gnubg.md"
#: F8-02: varsayilan model **panelde en iyi** olan modeldir. Onceki varsayilan
#: ``stage_d_l2/model_v30`` panelde 5x daha kotuydu (contact ER 0.0348 vs
#: 0.0070), yani gecmis ppg olcumleri gercek en guclu modeli olcmuyordu.
DEFAULT_MODEL = "ml/runs/capacity_rd/large/seed0/model.onnx"
DEFAULT_GAMES = 2000
DEFAULT_MAX_PLIES = 200
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261125
OUR_PATHS = ("policy", "value", "search1")

#: Denetim noktasi (checkpoint) bicim surumu. Uzun ppg kosulari saatler surer ve
#: tek bir surec cokmesi tum olcumu kaybettirir; bu yuzden her **cift**
#: tamamlandiginda sonuc JSONL olarak diske yazilir ve kosu kaldigi yerden
#: devam eder (F7-116).
CHECKPOINT_VERSION = 1


class MatchError(RuntimeError):
    """Mac olcumu yapilamadi."""


def _checkpoint_key(
    model_path: Path, path: str, gnubg_plies: int, seed: int, max_plies: int
) -> dict[str, Any]:
    """Denetim noktasinin hangi kosuya ait oldugunu belirleyen imza.

    Farkli bir model/yol/tohum ile uretilmis kayitlarin sessizce karistirilmasini
    engeller: imza uyusmazsa kosu **hata verir**, devam etmez.
    """
    return {
        "checkpointVersion": CHECKPOINT_VERSION,
        "model": str(model_path),
        "path": str(path),
        "gnubgPlies": int(gnubg_plies),
        "seed": int(seed),
        "maxPlies": int(max_plies),
    }


def _load_checkpoint(
    checkpoint: Path, key: dict[str, Any]
) -> dict[int, tuple[list[float], list[int], list[bool]]]:
    """Var olan denetim noktasini okur; yarim yazilmis son satiri atlar."""
    if not checkpoint.exists():
        return {}
    done: dict[int, tuple[list[float], list[int], list[bool]]] = {}
    with checkpoint.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # Surec yazarken oldu: son satir yarim olabilir, yeniden oynanir.
                continue
            if record.get("key") != key:
                raise MatchError(
                    "denetim noktasi farkli bir kosuya ait: %s\n  beklenen: %s\n  bulunan: %s"
                    % (checkpoint, key, record.get("key"))
                )
            done[int(record["pair"])] = (
                [float(v) for v in record["scores"]],
                [int(v) for v in record["plies"]],
                [bool(v) for v in record["finished"]],
            )
    return done


def _append_checkpoint(
    handle,
    key: dict[str, Any],
    pair: int,
    result: tuple[list[float], list[int], list[bool]],
) -> None:
    """Bir ciftin sonucunu denetim noktasina ekler ve **diske indirir**."""
    scores, plies, finished = result
    handle.write(
        json.dumps(
            {
                "key": key,
                "pair": int(pair),
                "scores": [float(v) for v in scores],
                "plies": [int(v) for v in plies],
                "finished": [bool(v) for v in finished],
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    handle.flush()
    os.fsync(handle.fileno())


def _bootstrap_ci(values: np.ndarray, resamples: int, seed: int) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(resamples, values.size))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _dice_sequence(rng: np.random.Generator, length: int) -> list[tuple[int, int]]:
    """Bir oyun icin zar dizisi (21 eslesme, gercek olasilikla)."""
    rolls = er_paths.DICE_ROLLS
    weights = np.asarray(er_paths.DICE_WEIGHTS, dtype=np.float64)
    weights = weights / weights.sum()
    idx = rng.choice(len(rolls), size=length, p=weights)
    return [rolls[int(i)] for i in idx]


def _case(board, turn, dice, white_off, black_off) -> dict[str, Any]:
    expanded = [dice[0]] * 4 if dice[0] == dice[1] else list(dice)
    max_steps, states = refgen.legal_after_states(
        board, turn, expanded, white_off, black_off
    )
    return {
        "name": "live",
        "board": list(board),
        "turn": int(turn),
        "dice": [int(dice[0]), int(dice[1])],
        "whiteOff": int(white_off),
        "blackOff": int(black_off),
        "maxSteps": int(max_steps),
        "afterStates": [
            {"board": list(b), "whiteOff": int(w), "blackOff": int(k)}
            for (b, w, k) in sorted(states)
        ],
    }


def _gnubg_chooser(session: gnubg_er.GnubgSession, plies: int = 0):
    """gnubg ``plies``-ply argmax'i."""

    def choose(case: dict[str, Any]) -> int:
        turn = int(case["turn"])
        boards = [a["board"] for a in case["afterStates"]]
        tables = session.eval_afterstates(boards, -turn)
        equities = [-gnubg_er._equity_at(t, plies) for t in tables]
        return int(np.argmax(equities))

    return choose


def _our_chooser(scorer: gnubg_er.OnnxScorer, path: str):
    if path == "policy":
        return lambda case: er_paths.choose_policy(scorer, case)
    if path == "value":
        return lambda case: er_paths.choose_value(scorer, case)
    if path == "search1":
        return lambda case: er_paths.choose_search1(scorer, case)[0]
    raise MatchError("bilinmeyen yol: %s" % path)


def _play_pair(
    task: tuple[int, int],
    our_choose: Callable[[dict[str, Any]], int],
    gnubg_choose: Callable[[dict[str, Any]], int],
    max_plies: int,
) -> tuple[list[float], list[int], list[bool]]:
    """Bir cifti (ayni zar dizisi, iki renk) oynar.

    Zar dizisi **cift basina** turetilir; boylece paralel calistirmada sira
    bagimsizligi korunur ve sonuc tek surecli kosuyla ayni dagilimdan gelir.
    """
    pair, seed = task
    rng = np.random.default_rng([int(seed), int(pair)])
    dice_seq = _dice_sequence(rng, max_plies)
    scores: list[float] = []
    plies: list[int] = []
    finished: list[bool] = []
    for our_side in (1, -1):
        result = play_game(
            dice_seq=dice_seq,
            our_side=our_side,
            our_choose=our_choose,
            gnubg_choose=gnubg_choose,
            max_plies=max_plies,
            allow_unfinished=True,
        )
        scores.append(float(result["score"]))
        plies.append(int(result["plies"]))
        finished.append(bool(result["finished"]))
    return scores, plies, finished


_WORKER: dict[str, Any] = {}


def _init_worker(
    model_path: str,
    path: str,
    gnubg: str | None,
    gnubg_plies: int,
    max_plies: int,
) -> None:
    exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()
    session = gnubg_er.GnubgSession(exe, plies=gnubg_plies, timeout=300, persistent=True)
    scorer = gnubg_er.OnnxScorer(Path(model_path), intra_op_threads=1)
    _WORKER.update(
        session=session,
        our_choose=_our_chooser(scorer, path),
        gnubg_choose=_gnubg_chooser(session, gnubg_plies),
        max_plies=int(max_plies),
    )


def _worker_play_pair(task: tuple[int, int]) -> tuple[list[float], list[int], list[bool]]:
    return _play_pair(
        task, _WORKER["our_choose"], _WORKER["gnubg_choose"], _WORKER["max_plies"]
    )


def play_game(
    *,
    dice_seq: Sequence[tuple[int, int]],
    our_side: int,
    our_choose: Callable[[dict[str, Any]], int],
    gnubg_choose: Callable[[dict[str, Any]], int],
    max_plies: int = DEFAULT_MAX_PLIES,
    allow_unfinished: bool = False,
    on_roll: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Tek bir kupsuz para oyunu oynar; **bizim** bakisimizdan puan doner.

    ``allow_unfinished``: ``max_plies`` doldugunda hata yerine
    ``finished=False`` ve ``score=0.0`` doner. K5'te ``policy`` yolunun
    bitmeyen oyun uretebildigi goruldu (politika kafasi tek basina donguye
    girebiliyor); mac kosusunun tamamen dusmesi yerine bu oyunlar **sayilir
    ve raporlanir**. Varsayilan ``False``: sessiz dusme yok.

    ``on_roll``: **F8-01**. Her zar olayinda (hamle secilmeden **once**, zorunlu
    pas dahil) cagrilir; ``case`` sozlugunu alir. Sans-duzeltmesi
    (``ml/luck_adjust.py``) bu kancaya baglanir. ``None`` iken ek maliyet
    **sifirdir**; mevcut davranis bit-ozdes kalir.
    """
    board = list(refgen.START_BOARD)
    white_off = black_off = 0
    turn = 1
    plies = 0

    for ply in range(max_plies):
        if ply >= len(dice_seq):
            raise MatchError("zar dizisi bitti (max_plies cok kucuk)")
        dice = dice_seq[ply]
        case = _case(board, turn, dice, white_off, black_off)
        if on_roll is not None:
            on_roll(case)
        if not case["afterStates"]:
            turn = -turn
            plies += 1
            continue

        chooser = our_choose if turn == our_side else gnubg_choose
        index = int(chooser(case))
        chosen = case["afterStates"][index]
        board = list(chosen["board"])
        white_off = int(chosen["whiteOff"])
        black_off = int(chosen["blackOff"])
        plies += 1

        score = er_paths.terminal_equity(board, white_off, black_off, our_side)
        if score is not None:
            return {
                "score": float(score),
                "plies": plies,
                "ourSide": int(our_side),
                "finished": True,
            }
        turn = -turn

    if allow_unfinished:
        return {
            "score": 0.0,
            "plies": plies,
            "ourSide": int(our_side),
            "finished": False,
        }
    raise MatchError("oyun %d ply'de bitmedi" % max_plies)


def run_match(
    *,
    model_path: Path,
    games: int,
    path: str = "policy",
    gnubg: Path | None = None,
    gnubg_plies: int = 0,
    seed: int = 0,
    max_plies: int = DEFAULT_MAX_PLIES,
    workers: int = 1,
    progress: Callable[[str], None] | None = None,
    checkpoint: Path | None = None,
    restart: bool = False,
) -> dict[str, Any]:
    """``games`` oyun (yarisi her renkten) oynar ve ppg olcer.

    ``checkpoint`` verilirse her tamamlanan **cift** diske yazilir ve kosu
    kaldigi yerden devam eder (F7-116). ``restart`` denetim noktasini yok
    sayar ve sifirdan baslar.
    """
    if games < 2 or games % 2 != 0:
        raise MatchError("games cift ve >= 2 olmali (renk takasi icin)")
    if path not in OUR_PATHS:
        raise MatchError("yol %s olmali: %r" % (OUR_PATHS, path))
    if workers < 1:
        raise MatchError("workers >= 1 olmali")

    pairs = games // 2
    key = _checkpoint_key(Path(model_path), path, gnubg_plies, seed, max_plies)
    done: dict[int, tuple[list[float], list[int], list[bool]]] = {}
    if checkpoint is not None:
        checkpoint = Path(checkpoint)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        if restart and checkpoint.exists():
            checkpoint.unlink()
        done = _load_checkpoint(checkpoint, key)
        stale = [p for p in done if p >= pairs]
        for p in stale:
            del done[p]
    resumed = len(done)
    if progress and resumed:
        progress("denetim noktasindan devam: %d/%d cift hazir" % (resumed, pairs))

    tasks = [(pair, seed) for pair in range(pairs) if pair not in done]
    results: list[tuple[list[float], list[int], list[bool]] | None] = [None] * pairs
    for pair, value in done.items():
        results[pair] = value

    handle = checkpoint.open("a", encoding="utf-8") if checkpoint is not None else None
    try:
        if workers == 1:
            exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()
            session = gnubg_er.GnubgSession(exe, plies=gnubg_plies, timeout=300, persistent=True)
            scorer = gnubg_er.OnnxScorer(Path(model_path))
            our_choose = _our_chooser(scorer, path)
            gnubg_choose = _gnubg_chooser(session, gnubg_plies)
            try:
                for index, task in enumerate(tasks, start=1):
                    result = _play_pair(task, our_choose, gnubg_choose, max_plies)
                    results[task[0]] = result
                    if handle is not None:
                        _append_checkpoint(handle, key, task[0], result)
                    if progress and index % 25 == 0:
                        done_scores = [s for r in results if r for s in r[0]]
                        progress(
                            "%d/%d cift, ppg %.4f"
                            % (resumed + index, pairs, float(np.mean(done_scores)))
                        )
            finally:
                session.close()
        else:
            import multiprocessing as mp  # noqa: PLC0415

            ctx = mp.get_context("spawn")
            with ctx.Pool(
                processes=workers,
                initializer=_init_worker,
                initargs=(str(model_path), path, str(gnubg) if gnubg else None, gnubg_plies, max_plies),
            ) as pool:
                for index, (task, result) in enumerate(
                    zip(tasks, pool.imap(_worker_play_pair, tasks)), start=1
                ):
                    results[task[0]] = result
                    if handle is not None:
                        _append_checkpoint(handle, key, task[0], result)
                    if progress and index % 25 == 0:
                        done_scores = [s for r in results if r for s in r[0]]
                        progress(
                            "%d/%d cift, ppg %.4f"
                            % (resumed + index, pairs, float(np.mean(done_scores)))
                        )
    finally:
        if handle is not None:
            handle.close()

    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        raise MatchError("tamamlanmayan ciftler: %d adet" % len(missing))
    results = [r for r in results if r is not None]

    scores: list[float] = []
    pair_diffs: list[float] = []
    wins = 0
    plies_total = 0
    unfinished = 0
    for pair_scores, pair_plies, pair_finished in results:
        for score, plies, done in zip(pair_scores, pair_plies, pair_finished):
            scores.append(score)
            plies_total += plies
            if not done:
                unfinished += 1
            if score > 0:
                wins += 1
        pair_diffs.append(pair_scores[0] + pair_scores[1])

    arr = np.asarray(scores, dtype=np.float64)
    diffs = np.asarray(pair_diffs, dtype=np.float64)
    low, high = _bootstrap_ci(arr, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    dlow, dhigh = _bootstrap_ci(diffs, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    return {
        "matchVersion": MATCH_VERSION,
        "model": str(model_path),
        "path": path,
        "gnubgPlies": int(gnubg_plies),
        "games": len(scores),
        "pairs": pairs,
        "workers": int(workers),
        "wins": wins,
        "winRate": wins / len(scores),
        "ppg": float(arr.mean()),
        "ppgCiLow": low,
        "ppgCiHigh": high,
        "ppgStdError": float(arr.std(ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else float("nan"),
        "pairedDiffMean": float(diffs.mean()),
        "pairedDiffCiLow": dlow,
        "pairedDiffCiHigh": dhigh,
        "meanPlies": plies_total / len(scores),
        "unfinished": unfinished,
        "unfinishedRate": unfinished / len(scores),
        "seed": int(seed),
        "resumedPairs": int(resumed),
        "checkpoint": str(checkpoint) if checkpoint is not None else None,
    }


def build_markdown(report: dict[str, Any]) -> str:
    plies = int(report["gnubgPlies"])
    lines = [
        "# Faz 7-R - Model vs gnubg %d-ply (kupsuz para oyunu)" % plies,
        "",
        "R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi",
        "bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.",
        "",
        "Model: `%s`" % report["model"],
        "Yol: `%s`" % report["path"],
        "gnubg: **%d-ply**" % plies,
        "",
        "| Olcum | Deger |",
        "|---|---|",
        "| Oyun | %d (%d cift) |" % (report["games"], report["pairs"]),
        "| Paralel surec | %d |" % report.get("workers", 1),
        "| Kazanma | %d/%d (%.4f) |"
        % (report["wins"], report["games"], report["winRate"]),
        "| **ppg** | **%+.4f** |" % report["ppg"],
        "| ppg %%95 GA | [%+.4f; %+.4f] |" % (report["ppgCiLow"], report["ppgCiHigh"]),
        "| ppg standart hata | %.4f |" % report["ppgStdError"],
        "| Eslestirilmis fark (beyaz+siyah) | %+.4f |" % report["pairedDiffMean"],
        "| Eslestirilmis fark %%95 GA | [%+.4f; %+.4f] |"
        % (report["pairedDiffCiLow"], report["pairedDiffCiHigh"]),
        "| Oyun basina ply | %.1f |" % report["meanPlies"],
        "| Bitmeyen oyun | %d (%.4f) |"
        % (report.get("unfinished", 0), report.get("unfinishedRate", 0.0)),
        "| Denetim noktasindan gelen cift | %d |" % report.get("resumedPairs", 0),
        "",
        "**Yorum.** ppg > 0 ise model gnubg %d-ply'i yeniyor demektir. " % plies
        + "Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; "
        "zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.",
        "",
    ]
    if report.get("unfinished", 0):
        lines.append(
            "**Bitmeyen oyunlar.** `max_plies` doldugunda oyun **0 puan** "
            "sayilir (biz kazanamadik) ve yukarida ayrica raporlanir. Bu, tek "
            "kafali yollarin (`policy`, `value`) donguye girebildigini "
            "gosterir; `search1` kosularinda gorulmedi."
        )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vs_gnubg",
        description="Model vs gnubg 0-ply mac olcumu - Faz 7-R adim 0",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES)
    parser.add_argument("--path", default="policy", choices=list(OUR_PATHS))
    parser.add_argument("--gnubg", default=None)
    parser.add_argument("--gnubg-plies", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="paralel surec sayisi (her surec kendi gnubg + ONNX oturumunu acar)",
    )
    parser.add_argument("--out", default=MATCH_PATH)
    parser.add_argument("--markdown", default=MATCH_MD_PATH)
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="JSONL denetim noktasi: her cift tamamlandiginda yazilir, kosu devam eder",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="denetim noktasini yok say ve sifirdan basla",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    progress = None if args.quiet else (lambda m: print(m, file=sys.stderr))
    report = run_match(
        model_path=Path(args.model),
        games=args.games,
        path=args.path,
        gnubg=Path(args.gnubg) if args.gnubg else None,
        gnubg_plies=args.gnubg_plies,
        seed=args.seed,
        max_plies=args.max_plies,
        workers=args.workers,
        progress=progress,
        checkpoint=Path(args.checkpoint) if args.checkpoint else None,
        restart=args.restart,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")

    print("oyun: %d, kazanma: %.4f" % (report["games"], report["winRate"]))
    print(
        "ppg: %+.4f GA [%+.4f; %+.4f]"
        % (report["ppg"], report["ppgCiLow"], report["ppgCiHigh"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
