"""Faz 4 v3 Bölüm 9 — Faz 3 arama ayarı ölçüm tablosu.

``DepthPly`` 0/1/2 x ``MaxCandidates*`` kısıtsız/kısıtlı kombinasyonlari için
oyun başına süre (self-play verimi) ve güç (``PipBot``'a karşı ortalama puan)
olcer.

Kullanim::

    python ml/settings_bench.py --model ml/artifacts/model_stage_c.onnx \
        --out ml/artifacts/settings_table.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from league import EvalResult, run_eval  # noqa: E402

# (DepthPly, MaxCandidatesRoot, MaxCandidatesInner, etiket)
DEFAULT_COMBOS: tuple[tuple[int, int, int, str], ...] = (
    (0, 0, 0, "depth 0, kısıtsız"),
    (0, 4, 4, "depth 0, kısıtlı (4/4)"),
    (1, 0, 0, "depth 1, kısıtsız"),
    (1, 4, 4, "depth 1, kısıtlı (4/4)"),
    (2, 0, 0, "depth 2, kısıtsız"),
    (2, 4, 4, "depth 2, kısıtlı (4/4)"),
)

# Derinlik basina oyun sayilari: (self-play, degerlendirme).
# Derinlik 2 tek oyun basina ~76 s surdugu icin orneklem kucuktur; raporda belirtilir.
PROFILES: dict[str, dict[int, tuple[int, int]]] = {
    "quick": {0: (20, 100), 1: (4, 20), 2: (1, 2)},
    "full": {0: (100, 400), 1: (20, 100), 2: (4, 20)},
}

_GAMES_PER_SECOND = re.compile(r"\(([0-9.]+) oyun/s\)")
_BYTES_PER_GAME = re.compile(r"\(([0-9.]+) B/oyun\)")


@dataclass
class ComboResult:
    label: str
    depth: int
    max_root: int
    max_inner: int
    selfplay_games: int
    selfplay_seconds: float
    games_per_second: float
    bytes_per_game: float
    eval_games: int
    mean_points: float
    standard_error: float
    win_rate: float
    lower_confidence_bound: float
    upper_confidence_bound: float
    timed_out: bool = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def measure_selfplay(
    model: Path,
    *,
    depth: int,
    max_root: int,
    max_inner: int,
    games: int,
    seed: int,
    out_dir: Path,
    cuda: bool = False,
    project: str = "Backgammon.SelfPlay/Backgammon.SelfPlay.csproj",
    configuration: str = "Release",
    timeout: float | None = None,
) -> tuple[float, float, float, bool]:
    """Self-play kosar; (saniye, oyun/s, bayt/oyun, zaman_aşımı) doner."""
    root = _repo_root()
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        "dotnet", "run",
        "--project", str(root / project),
        "-c", configuration,
        "--no-build",
        "--",
        "--model", str(model),
        "--games", str(games),
        "--seed", str(seed),
        "--threads", "1",
        "--out", str(out_dir),
        "--prefix", "bench",
        "--depth", str(depth),
        "--max-root", str(max_root),
        "--max-inner", str(max_inner),
        "--log-top", "0",
        "--max-plies", "500",
    ]
    if cuda:
        cmd.append("--cuda")

    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        proc = None
    elapsed = time.time() - t0

    if timed_out:
        return elapsed, 0.0, 0.0, True

    assert proc is not None
    if proc.returncode != 0:
        raise RuntimeError(
            "self-play basarisiz (exit " + str(proc.returncode) + ")\n"
            + "STDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr
        )

    gps = 0.0
    bpg = 0.0
    m = _GAMES_PER_SECOND.search(proc.stdout)
    if m:
        gps = float(m.group(1))
    m = _BYTES_PER_GAME.search(proc.stdout)
    if m:
        bpg = float(m.group(1))

    return elapsed, gps, bpg, False


def run_combo(
    model: Path,
    *,
    label: str,
    depth: int,
    max_root: int,
    max_inner: int,
    selfplay_games: int,
    eval_games: int,
    seed: int,
    work_dir: Path,
    cuda: bool = False,
    timeout: float | None = None,
) -> ComboResult:
    sp_dir = work_dir / ("sp_d" + str(depth) + "_r" + str(max_root) + "_i" + str(max_inner))
    seconds, gps, bpg, timed_out = measure_selfplay(
        model,
        depth=depth,
        max_root=max_root,
        max_inner=max_inner,
        games=selfplay_games,
        seed=seed,
        out_dir=sp_dir,
        cuda=cuda,
        timeout=timeout,
    )

    if timed_out:
        return ComboResult(
            label=label,
            depth=depth,
            max_root=max_root,
            max_inner=max_inner,
            selfplay_games=selfplay_games,
            selfplay_seconds=seconds,
            games_per_second=0.0,
            bytes_per_game=0.0,
            eval_games=0,
            mean_points=0.0,
            standard_error=0.0,
            win_rate=0.0,
            lower_confidence_bound=0.0,
            upper_confidence_bound=0.0,
            timed_out=True,
        )

    results = run_eval(
        learner_onnx=model,
        games=eval_games,
        seed=seed,
        depth=depth,
        opponent_kind="pip",
        max_root=max_root,
        max_inner=max_inner,
        cuda=cuda,
        json_path=work_dir / ("eval_d" + str(depth) + "_r" + str(max_root) + ".json"),
    )
    r: EvalResult = results[0]

    return ComboResult(
        label=label,
        depth=depth,
        max_root=max_root,
        max_inner=max_inner,
        selfplay_games=selfplay_games,
        selfplay_seconds=seconds,
        games_per_second=gps,
        bytes_per_game=bpg,
        eval_games=r.games,
        mean_points=r.mean_points,
        standard_error=r.standard_error,
        win_rate=r.win_rate,
        lower_confidence_bound=r.lower_confidence_bound,
        upper_confidence_bound=r.upper_confidence_bound,
        timed_out=timed_out,
    )


def build_markdown(model: Path, rows: Sequence[ComboResult], seed: int) -> str:
    lines = [
        "# Faz 3 arama ayarı ölçüm tablosu",
        "",
        "Model: `" + str(model) + "` — seed " + str(seed) + ".",
        "",
        "| Ayar | DepthPly | MaxRoot / Inner | Oyun/s | s/oyun | B/oyun | Oyun | PipBot kazanma | Ortalama puan | 95% GA |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        sec_per_game = (1.0 / r.games_per_second) if r.games_per_second > 0 else float("nan")
        if r.timed_out:
            lines.append(
                "| {l} | {d} | {mr} / {mi} | zaman aşımı | > {t:.0f} | - | {eg} | - | - | - |".format(
                    l=r.label,
                    d=r.depth,
                    mr=r.max_root,
                    mi=r.max_inner,
                    t=r.selfplay_seconds,
                    eg=r.eval_games,
                )
            )
            continue
        lines.append(
            "| {l} | {d} | {mr} / {mi} | {gps:.2f} | {spg:.3f} | {bpg:.0f} | {eg} | {wr:.2f} % | "
            "{mp:+.4f} ± {se:.4f} | [{lo:+.4f}, {hi:+.4f}] |".format(
                l=r.label,
                d=r.depth,
                mr=r.max_root,
                mi=r.max_inner,
                gps=r.games_per_second,
                spg=sec_per_game,
                bpg=r.bytes_per_game,
                eg=r.eval_games,
                wr=r.win_rate * 100.0,
                mp=r.mean_points,
                se=r.standard_error,
                lo=r.lower_confidence_bound,
                hi=r.upper_confidence_bound,
            )
        )

    lines.extend([
        "",
        "Notlar:",
        "",
        "* `Oyun/s` tek iş parçacığı, `--log-top 0` (tüm adaylar loglanır) ile ölçülmüştür;",
        "  gerçek eğitimde `logTopCandidates = 12` kullanılır ve shard yazımı daha ucuzdur.",
        "* `PipBot` sezgisel bir tabandır (afterstate'te `rakipPip - kendiPip` maksimizasyonu);",
        "  uzun oyunlara eğilimlidir, bu yüzden `max_plies = 500` ile bazı oyunlar abort olur.",
        "* Güç farkı ölçümünün standart hatası tabloda verilmiştir; küçük farklar anlamlı değildir.",
        "* Derinlik 2 tek oyun başına ~76 s sürdüğü için örneklem küçüktür (bkz. `Oyun` sütunu);",
        "  derinlik 2 satırlarındaki güç farkı **istatistiksel olarak anlamsızdır**, yalnızca",
        "  maliyet ölçümü olarak okunmalıdır.",
        "",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Faz 3 arama ayarı ölçüm tablosu")
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", default="ml/artifacts/settings_table.md")
    parser.add_argument("--json", default="ml/artifacts/settings_table.json")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="quick")
    parser.add_argument("--selfplay-games", type=int, default=None, help="tüm derinlikler için geçersiz kilma")
    parser.add_argument("--eval-games", type=int, default=None, help="tüm derinlikler için geçersiz kilma")
    parser.add_argument("--work-dir", default="ml/artifacts/settings_bench")
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument(
        "--timeout", type=float, default=900.0,
        help="kombinasyon başına self-play zaman aşımı (saniye, 0 = sinirsiz)",
    )
    args = parser.parse_args(argv)

    model = Path(args.model)
    if not model.is_file():
        parser.error("model bulunamadi: " + str(model))

    work_dir = Path(args.work_dir)
    rows: list[ComboResult] = []

    profile = PROFILES[args.profile]

    for depth, max_root, max_inner, label in DEFAULT_COMBOS:
        sp_games, ev_games = profile[depth]
        if args.selfplay_games is not None:
            sp_games = args.selfplay_games
        if args.eval_games is not None:
            ev_games = args.eval_games

        print("[bench] " + label + " (sp=" + str(sp_games) + ", eval=" + str(ev_games) + ") ...", flush=True)
        row = run_combo(
            model,
            label=label,
            depth=depth,
            max_root=max_root,
            max_inner=max_inner,
            selfplay_games=sp_games,
            eval_games=ev_games,
            seed=args.seed,
            work_dir=work_dir,
            cuda=args.cuda,
            timeout=(args.timeout if args.timeout and args.timeout > 0 else None),
        )
        rows.append(row)
        if row.timed_out:
            print("        zaman aşımı ({:.0f} s)".format(row.selfplay_seconds), flush=True)
        else:
            print(
                "        {gps:.2f} oyun/s, PipBot {wr:.2f} % ({mp:+.4f})".format(
                    gps=row.games_per_second, wr=row.win_rate * 100.0, mp=row.mean_points
                ),
                flush=True,
            )

    markdown = build_markdown(model, rows, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print("tablo yazildi: " + str(out))

    if args.json:
        jp = Path(args.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(
            json.dumps(
                {"model": str(model), "seed": args.seed, "rows": [asdict(r) for r in rows]},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print("json yazildi: " + str(jp))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
