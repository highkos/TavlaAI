"""Faz 4 v3 Bölüm 9 — değerlendirme tezgahi (``eval_bench``).

Taban oyunculara karşı rapor uretir:

* ``RandomBot`` — rastgele yasal hamle
* ``PipBot`` — afterstate'i ``rakipPip - kendiPip`` degerini maksimize eden sezgisel
* onceki checkpoint'ler / havuz uyeleri (``--vs-model``)

Protokol (spec Bölüm 9): sabit seed'ler, ``argmax``, her seed için renkler degistirilerek
iki oyun. Sonuç: oyun başına ortalama puan ± standart hata.

Ayrica ``--plot`` ile eğitim raporundan yakinsama grafigi uretir.

Kullanim::

    python ml/eval_bench.py --model ml/artifacts/model_stage_c.onnx \
        --games 400 --seed 1 --depth 0 --opponents random,pip --out report.md

    python ml/eval_bench.py --model A.onnx --vs-model B.onnx --games 400

    python ml/eval_bench.py --plot ml/artifacts/stage_c_train_report.json --out chart.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from league import (  # noqa: E402
    EvalResult,
    format_report,
    run_eval,
)

DEFAULT_GAMES = 400
DEFAULT_SEED = 1
DEFAULT_DEPTH = 0


# ----------------------------------------------------------------------
# Tek model degerlendirmesi
# ----------------------------------------------------------------------


def evaluate(
    model: Path,
    *,
    games: int = DEFAULT_GAMES,
    seed: int = DEFAULT_SEED,
    depth: int = DEFAULT_DEPTH,
    max_root: int = 0,
    max_inner: int = 0,
    max_plies: int = 500,
    opponents: Sequence[str] = ("random", "pip"),
    vs_models: Sequence[Path] = (),
    cuda: bool = False,
    json_path: Path | None = None,
) -> list[EvalResult]:
    """Modeli verilen taban oyunculara ve modellere karşı degerlendirir."""
    results: list[EvalResult] = []

    for kind in opponents:
        kind = kind.strip().lower()
        if not kind:
            continue
        if kind not in ("random", "pip"):
            raise ValueError("bilinmeyen taban oyuncu: " + kind)

        results.extend(
            run_eval(
                learner_onnx=model,
                games=games,
                seed=seed,
                depth=depth,
                opponent_kind=kind,
                max_root=max_root,
                max_inner=max_inner,
                max_plies=max_plies,
                cuda=cuda,
            )
        )

    for other in vs_models:
        other = Path(other)
        for res in run_eval(
            learner_onnx=model,
            games=games,
            seed=seed,
            depth=depth,
            opponent_onnx=other,
            opponent_kind="model",
            max_root=max_root,
            max_inner=max_inner,
            max_plies=max_plies,
            cuda=cuda,
        ):
            # C# surucusu rakip adini "Model" olarak dondurur; raporda hangi
            # checkpoint oldugu gorunsun diye dosya adiyla degistirilir.
            res.opponent = "Model:" + other.stem
            results.append(res)

    if json_path is not None:
        write_eval_json(
            Path(json_path),
            model=model,
            results=results,
            seed=seed,
            depth=depth,
            max_root=max_root,
            max_inner=max_inner,
        )

    return results


def write_eval_json(
    path: Path,
    *,
    model: Path,
    results: Sequence[EvalResult],
    seed: int,
    depth: int,
    max_root: int,
    max_inner: int,
) -> Path:
    """Tum rakiplerin sonuclarini tek bir JSON dosyasina yazar.

    C# surucusu her cagrida JSON'u bastan yazar; bu yüzden birlestirme
    Python tarafinda yapılır (bkz. ASSUMPTIONS F4-52).
    """
    payload = {
        "model": str(model),
        "seed": int(seed),
        "depthPly": int(depth),
        "maxCandidatesRoot": int(max_root),
        "maxCandidatesInner": int(max_inner),
        "reports": [
            {
                "opponent": r.opponent,
                "games": r.games,
                "wins": r.wins,
                "losses": r.losses,
                "draws": r.draws,
                "winRate": r.win_rate,
                "meanPoints": r.mean_points,
                "standardError": r.standard_error,
                "lowerConfidenceBound": r.lower_confidence_bound,
                "upperConfidenceBound": r.upper_confidence_bound,
            }
            for r in results
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Yakinsama grafigi
# ----------------------------------------------------------------------


def plot_convergence(report_path: Path, out_path: Path) -> Path:
    """``train_report.json`` icinden kayıp/entropi egrilerini cizer."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    history = data.get("history") or []
    if not history:
        raise ValueError("raporda 'history' yok: " + str(report_path))

    it = [int(h["iteration"]) for h in history]

    def series(key: str) -> list[float]:
        return [float(h.get(key, float("nan"))) for h in history]

    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.5))
    fig.suptitle(
        "Faz 4 — eğitim yakinsamasi (G={g}, S={s}, depth={d})".format(
            g=data.get("games_per_iteration", "?"),
            s=data.get("steps_per_iteration", "?"),
            d=data.get("depth", "?"),
        )
    )

    ax = axes[0][0]
    ax.plot(it, series("probe_mc_value_loss"), "o-", label="MC probe (sabit)")
    ax.plot(it, series("probe_value_loss"), "s--", label="TD probe (sabit)")
    ax.plot(it, series("buffer_value_loss"), "^:", label="buffer (guncel)")
    ax.set_title("Değer kaybı")
    ax.set_xlabel("iterasyon")
    ax.set_ylabel("MSE")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[0][1]
    ax.plot(it, series("buffer_policy_loss"), "o-", label="politika kaybı")
    ax.plot(it, series("buffer_uniform_baseline"), "s--", label="düzgün baz log|E|")
    ax.set_title("Politika kaybı")
    ax.set_xlabel("iterasyon")
    ax.set_ylabel("capraz entropi")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1][0]
    ax.plot(it, series("buffer_target_entropy_ratio"), "o-", color="tab:green")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1.0)
    ax.set_title("Hedef entropisi / log|E|")
    ax.set_xlabel("iterasyon")
    ax.set_ylabel("oran")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)

    ax = axes[1][1]
    ax.plot(it, series("grad_norm_mean"), "o-", label="|g| ortalama")
    ax.plot(it, series("grad_norm_max"), "s--", label="|g| maksimum")
    ax.set_title("Gradyan normu")
    ax.set_xlabel("iterasyon")
    ax.set_ylabel("L2")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def build_markdown(
    model: Path,
    results: Sequence[EvalResult],
    *,
    games: int,
    seed: int,
    depth: int,
    max_root: int,
    max_inner: int,
) -> str:
    lines = [
        "# Değerlendirme raporu",
        "",
        "| Alan | Değer |",
        "|---|---|",
        "| Model | `" + str(model) + "` |",
        "| Oyun / rakip | " + str(games) + " |",
        "| Seed | " + str(seed) + " |",
        "| DepthPly | " + str(depth) + " |",
        "| MaxCandidatesRoot / Inner | " + str(max_root) + " / " + str(max_inner) + " |",
        "",
        format_report(results),
        "",
        "Protokol: sabit seed, `argmax`, renkler değişimli. Puanlar küp olmadan",
        "(cubeValue = 1) ve Jacoby kapalı olarak Faz 1 `GameResult.Points`'tur.",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Faz 4 değerlendirme tezgahi")
    parser.add_argument("--model", default=None, help="degerlendirilecek ONNX modeli")
    parser.add_argument("--vs-model", action="append", default=[], help="karşı model (tekrarlanabilir)")
    parser.add_argument("--opponents", default="random,pip", help="taban oyuncular (virgulle)")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--max-root", type=int, default=0)
    parser.add_argument("--max-inner", type=int, default=0)
    parser.add_argument("--max-plies", type=int, default=500)
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument("--out", default=None, help="markdown rapor yolu")
    parser.add_argument("--json", default=None, help="ham JSON cikti yolu")
    parser.add_argument("--plot", default=None, help="train_report.json yolu (grafik modu)")
    parser.add_argument("--plot-out", default=None, help="grafik PNG yolu")
    args = parser.parse_args(argv)

    if args.plot:
        out = Path(args.plot_out or "ml/artifacts/convergence.png")
        path = plot_convergence(Path(args.plot), out)
        print("grafik yazildi: " + str(path))
        return 0

    if not args.model:
        parser.error("--model veya --plot gerekli")

    model = Path(args.model)
    if not model.is_file():
        parser.error("model bulunamadi: " + str(model))

    opponents = [s for s in str(args.opponents).split(",") if s.strip()]
    results = evaluate(
        model,
        games=args.games,
        seed=args.seed,
        depth=args.depth,
        max_root=args.max_root,
        max_inner=args.max_inner,
        max_plies=args.max_plies,
        opponents=opponents,
        vs_models=[Path(p) for p in args.vs_model],
        cuda=args.cuda,
        json_path=Path(args.json) if args.json else None,
    )

    markdown = build_markdown(
        model,
        results,
        games=args.games,
        seed=args.seed,
        depth=args.depth,
        max_root=args.max_root,
        max_inner=args.max_inner,
    )
    print(markdown)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print("rapor yazildi: " + str(out))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
