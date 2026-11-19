# -*- coding: utf-8 -*-
"""Faz 7-R Asama R-B: ER'yi **uc oynanis yolu** icin ayri ayri olcer.

Faz 6/7'de ER tek bir yoldan olculuyordu: politika kafasi argmax'i
(``gnubg_er.score_afterstates(criterion="policy")``). Bu, urunun **gercek**
oynanis yolu degildir: ``SearchSettings.ProductionDepthPly = 1`` iken urun
1-ply arama yapar (``ASSUMPTIONS.md`` F7-46). Tek yol raporlamak, "ER 0,0533"
gibi bir sayinin hangi oynanisa ait oldugunu belirsiz birakir.

Bu modul uc yolu **ayri ayri** olcer ve her biri icin ortalama, medyan,
bootstrap %95 GA, faz kirilimi ve **gercek oyun frekansiyla agirlikli** ER
verir:

``policy``
    Politika kafasi argmax'i (0-ply, ``ArgMaxCandidate``).
``value``
    Deger kafasi argmax'i (0-ply).
``search1``
    1-ply expectiminimax: her aday afterstate icin rakibin 21 zar atisinin
    en iyi yanitinin beklenen degeri (deger kafasiyla).

Kural 4: guc hesabi **nokta tahmininden** yapilmaz; :func:`power_rows`
``sigma``'nin ust guven sinirini kullanir.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import er_power  # noqa: E402
import gnubg_er  # noqa: E402
from tools import reference_gen as refgen  # noqa: E402

#: Raporlanan oynanis yollari.
PLAY_PATHS = ("policy", "value", "search1")

#: Yol etiketleri (rapora yazilir).
PATH_LABELS = {
    "policy": "politika kafasi argmax (0-ply)",
    "value": "deger kafasi argmax (0-ply)",
    "search1": "1-ply expectiminimax (deger kafasi)",
}

#: 21 zar atisi (cift zarlar tek kez).
DICE_ROLLS = tuple(
    (d1, d2) for d1 in range(1, 7) for d2 in range(d1, 7)
)

#: Zar olasiliklari (36'da). Cift 1/36, cift olmayan 2/36.
#:
#: **F7-80:** eski kod 21 zari **esit** (1/21) agirlikla ortaliyordu. Bu, Python
#: olcum aracini urun aramasindan ayiriyordu: C# `BackgammonSearch` gercek zar
#: olasiligini kullanir. Fark, karar yakinsa (ust-2 fark ~0,001) argmax'i
#: cevirebiliyordu; 500 vakalik parite olcumunde 28 uyusmazligin **tamami**
#: ust-2 farki <= 0,0155 olan vakalardi.
DICE_WEIGHTS = tuple(1 if d1 == d2 else 2 for (d1, d2) in DICE_ROLLS)

#: Agirlik toplami (36).
DICE_WEIGHT_SUM = sum(DICE_WEIGHTS)

#: Bootstrap yeniden ornekleme sayisi (Kural 3: >= 10 000).
BOOTSTRAP_RESAMPLES = 20000

#: Bootstrap tohumu.
BOOTSTRAP_SEED = 20261119


# ----------------------------------------------------------------------
# Terminal deger
# ----------------------------------------------------------------------


def terminal_equity(
    board: Sequence[int], white_off: int, black_off: int, turn: int
) -> float | None:
    """Oyun bittiyse **turn** bakis acisindan puan degerini dondurur.

    Bitis yoksa ``None``. Puanlar: 1 (tek), 2 (mars), 3 (backgammon).
    Mars: kaybeden hic tas toplamadi. Backgammon: kaybeden hic tas toplamadi
    **ve** kendi evinde veya barda tasi var.
    """
    if white_off < refgen.PIECES and black_off < refgen.PIECES:
        return None

    white_won = white_off >= refgen.PIECES
    winner_off = white_off if white_won else black_off
    loser_off = black_off if white_won else white_off
    if winner_off < refgen.PIECES:
        return None

    points = 1
    if loser_off == 0:
        points = 2
        # F7-80: mars/backgammon ayrimi **kazananin** evine ve **kaybedenin**
        # barina bakar. Bu kod tabaninda Beyaz'in evi 19..24, Siyah'in evi
        # 1..6; Beyaz'in bari 0, Siyah'in bari 25 (bkz. ``refgen.is_home`` ve
        # ``gnubg_er._bar_index``). Eski kod evleri ve barlari **ters**
        # kullaniyordu: 500 vakalik parite olcumunde 4 vakada mars yerine
        # backgammon (ya da tersi) uretiyordu.
        if white_won:
            in_home = board[25] < 0 or any(board[i] < 0 for i in range(19, 25))
        else:
            in_home = board[0] > 0 or any(board[i] > 0 for i in range(1, 7))
        if in_home:
            points = 3

    won_by_turn = (white_won and turn > 0) or ((not white_won) and turn < 0)
    return float(points) if won_by_turn else -float(points)


# ----------------------------------------------------------------------
# Yol secimi
# ----------------------------------------------------------------------


def _vectors_for(
    states: Sequence[tuple], perspective: int
) -> list[list[float]]:
    return [
        gnubg_er.vectorize(b, w, k, perspective=perspective) for (b, w, k) in states
    ]


def choose_policy(scorer: gnubg_er.OnnxScorer, case: dict[str, Any]) -> int:
    """Politika kafasi argmax'i."""
    turn = int(case["turn"])
    states = [
        (a["board"], a["whiteOff"], a["blackOff"]) for a in case["afterStates"]
    ]
    logits = scorer.logits(_vectors_for(states, turn))
    return max(range(len(logits)), key=lambda i: logits[i])


def choose_value(scorer: gnubg_er.OnnxScorer, case: dict[str, Any]) -> int:
    """Deger kafasi argmax'i."""
    turn = int(case["turn"])
    states = [
        (a["board"], a["whiteOff"], a["blackOff"]) for a in case["afterStates"]
    ]
    values = scorer.values(_vectors_for(states, turn))
    return max(range(len(values)), key=lambda i: values[i])


def search1_values(
    scorer: gnubg_er.OnnxScorer, case: dict[str, Any]
) -> tuple[list[float], int]:
    """Her aday afterstate icin 1-ply degeri; (degerler, terminal_aday_sayisi).

    ``V1(a) = -E_zar[ max_o V_o(o) ]`` -- ``o`` rakibin ``a``'dan ulasabildigi
    afterstate'ler, ``V_o`` deger kafasinin **rakibin** bakis acisindan ciktisi.
    Rakip oynayamiyorsa (bar kapali) ``V1(a) = -V_o(a)`` yaklasimi kullanilir;
    bu, 1-ply aramanin standart 0-ply yanit yaklasimidir.
    """
    turn = int(case["turn"])
    opponent = -turn
    candidates = [
        (a["board"], a["whiteOff"], a["blackOff"]) for a in case["afterStates"]
    ]

    # 1) Adaylarin kendi degerleri (rakip bakisi) -- rakip oynayamazsa gerekli.
    own_vectors = _vectors_for(candidates, opponent)
    own_values = scorer.values(own_vectors)

    # 2) Her aday icin rakibin 21 zarina ait afterstate'leri topla.
    flat_vectors: list[list[float]] = []
    spans: list[list[tuple[int, int]]] = []
    terminal_count = 0
    for (board, white_off, black_off) in candidates:
        per_roll: list[tuple[int, int]] = []
        for (d1, d2) in DICE_ROLLS:
            dice = [d1, d1, d1, d1] if d1 == d2 else [d1, d2]
            max_steps, states = refgen.legal_after_states(
                board, opponent, dice, white_off, black_off
            )
            if max_steps == 0 or not states:
                per_roll.append((-1, -1))
                continue
            ordered = sorted(states)
            start = len(flat_vectors)
            flat_vectors.extend(_vectors_for(ordered, opponent))
            per_roll.append((start, len(flat_vectors)))
        spans.append(per_roll)

    flat_values = scorer.values(flat_vectors) if flat_vectors else []

    # F7-80: rakibin **terminal** afterstate'leri deger kafasindan degil
    # oyun kuralindan gelir. Eski kod bunlari deger kafasiyla tahmin ediyordu;
    # rakip mars/backgammon yapabiliyorsa 1-ply deger **sistematik olarak
    # iyimser** cikiyordu (olculen fark 0,34-0,98 equity).
    flat_exact: list[float | None] = [None] * len(flat_vectors)
    cursor = 0
    for (board, white_off, black_off) in candidates:
        for (d1, d2) in DICE_ROLLS:
            dice = [d1, d1, d1, d1] if d1 == d2 else [d1, d2]
            max_steps, states = refgen.legal_after_states(
                board, opponent, dice, white_off, black_off
            )
            if max_steps == 0 or not states:
                continue
            for (b, w, k) in sorted(states):
                exact = terminal_equity(b, w, k, opponent)
                if exact is not None:
                    flat_exact[cursor] = exact
                cursor += 1

    out: list[float] = []
    for index, per_roll in enumerate(spans):
        total = 0.0
        for roll, (start, end) in enumerate(per_roll):
            weight = DICE_WEIGHTS[roll]
            if start < 0:
                # Rakip oynayamaz: kendi (rakip bakisi) degeri.
                total += weight * own_values[index]
                continue
            best = max(
                flat_exact[j] if flat_exact[j] is not None else flat_values[j]
                for j in range(start, end)
            )
            total += weight * best
        out.append(-total / float(DICE_WEIGHT_SUM))

    # Terminal adaylar: deger kafasi yerine kesin puan.
    for index, (board, white_off, black_off) in enumerate(candidates):
        exact = terminal_equity(board, white_off, black_off, turn)
        if exact is not None:
            out[index] = exact
            terminal_count += 1

    return out, terminal_count


def choose_search1(
    scorer: gnubg_er.OnnxScorer, case: dict[str, Any]
) -> tuple[int, int]:
    """1-ply arama argmax'i; (indeks, terminal_aday_sayisi)."""
    values, terminal_count = search1_values(scorer, case)
    return max(range(len(values)), key=lambda i: values[i]), terminal_count

# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


@dataclass
class PathMeasurement:
    """Tek bir oynanis yolunun ER olcumu."""

    path: str
    count: int
    mean: float
    median: float
    maximum: float
    exact_match_rate: float
    sigma: float
    sigma_ci_low: float
    sigma_ci_high: float
    ci_low: float
    ci_high: float
    standard_error: float
    phase_means: dict[str, float] = field(default_factory=dict)
    phase_counts: dict[str, int] = field(default_factory=dict)
    weighted_mean: float = 0.0
    terminal_candidates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": PATH_LABELS.get(self.path, self.path),
            "count": self.count,
            "mean": round(self.mean, 6),
            "median": round(self.median, 6),
            "maximum": round(self.maximum, 6),
            "exactMatchRate": round(self.exact_match_rate, 6),
            "sigma": round(self.sigma, 6),
            "sigmaCiLow": round(self.sigma_ci_low, 6),
            "sigmaCiHigh": round(self.sigma_ci_high, 6),
            "ciLow": round(self.ci_low, 6),
            "ciHigh": round(self.ci_high, 6),
            "standardError": round(self.standard_error, 6),
            "phaseMeans": {k: round(v, 6) for k, v in sorted(self.phase_means.items())},
            "phaseCounts": dict(sorted(self.phase_counts.items())),
            "weightedMean": round(self.weighted_mean, 6),
            "terminalCandidates": self.terminal_candidates,
        }


def _summarize_path(
    path: str,
    losses: Sequence[float],
    phases: Sequence[str],
    weights: dict[str, float],
    terminal_candidates: int = 0,
) -> PathMeasurement:
    """Bir yolun kayiplarini ozetler (bootstrap GA dahil)."""
    if not losses:
        raise ValueError("bos kayip listesi: %r" % (path,))
    summary = er_power.summarize_losses(
        list(losses), resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
    )
    phase_means: dict[str, float] = {}
    phase_counts: dict[str, int] = {}
    for loss, phase in zip(losses, phases):
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        phase_means.setdefault(phase, 0.0)
        phase_means[phase] += loss
    for phase in phase_means:
        phase_means[phase] /= float(phase_counts[phase])

    total_weight = sum(weights.get(p, 0.0) for p in phase_means)
    if total_weight > 0.0:
        weighted = sum(
            phase_means[p] * weights.get(p, 0.0) for p in phase_means
        ) / total_weight
    else:
        weighted = summary.mean

    ordered = sorted(losses)
    median = ordered[len(ordered) // 2] if len(ordered) % 2 else 0.5 * (
        ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]
    )

    return PathMeasurement(
        path=path,
        count=summary.n,
        mean=summary.mean,
        median=median,
        maximum=summary.maximum,
        exact_match_rate=0.0,
        sigma=summary.sigma,
        sigma_ci_low=summary.sigma_ci_low,
        sigma_ci_high=summary.sigma_ci_high,
        ci_low=summary.ci_low,
        ci_high=summary.ci_high,
        standard_error=summary.standard_error,
        phase_means=phase_means,
        phase_counts=phase_counts,
        weighted_mean=weighted,
        terminal_candidates=terminal_candidates,
    )


def measure_paths(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    plies: int = 2,
    timeout: int = 120,
    progress: bool = True,
    phase_weights: dict[str, float] | None = None,
    paths: Sequence[str] = PLAY_PATHS,
) -> dict[str, Any]:
    """Ayni vakalar uzerinde **uc yolu** olcer.

    Referans equity her vakada **bir kez** hesaplanir (gnubg ``eval``), sonra
    her yolun sectigi adayin equity'si ayni tablodan okunur. Boylece yollar
    arasindaki fark yalnizca **secim** farkidir; hakem farki degildir
    (Kural 7: tek parametre degisir).
    """
    import gnubg_er  # noqa: PLC0415

    usable, skipped = gnubg_er.split_cases(cases)
    session = gnubg_er.GnubgSession(gnubg, plies=plies, timeout=timeout)
    scorer = gnubg_er.OnnxScorer(Path(model_path))

    losses: dict[str, list[float]] = {p: [] for p in paths}
    phases: list[str] = []
    sources: list[str] = []
    matches: dict[str, int] = {p: 0 for p in paths}
    terminal_counts: dict[str, int] = {p: 0 for p in paths}

    for index, case in enumerate(usable, start=1):
        if progress:
            print("[%d/%d] %s" % (index, len(usable), case.get("name", "?")), file=sys.stderr)
        turn = int(case["turn"])
        after_states = case["afterStates"]
        tables = session.eval_afterstates([a["board"] for a in after_states], -turn)
        equities = [-gnubg_er._equity_at(table, plies) for table in tables]
        best_index = max(range(len(equities)), key=lambda i: equities[i])
        best_equity = equities[best_index]

        phases.append(str(case.get("phase", "?")))
        sources.append(str(case.get("source", "?")))

        for path in paths:
            if path == "policy":
                chosen = choose_policy(scorer, case)
                terminal = 0
            elif path == "value":
                chosen = choose_value(scorer, case)
                terminal = 0
            elif path == "search1":
                chosen, terminal = choose_search1(scorer, case)
            else:
                raise ValueError("bilinmeyen yol: %r" % (path,))
            losses[path].append(best_equity - equities[chosen])
            terminal_counts[path] += terminal
            if chosen == best_index:
                matches[path] += 1

    weights = phase_weights or {}
    out: dict[str, Any] = {
        "model": str(model_path),
        "referee": {
            "command": "eval",
            "column": "static" if plies == 0 else str(plies),
            "plies": int(plies),
            "prob": "equity",
        },
        "caseCount": len(usable),
        "skipped": list(skipped),
        "phaseWeights": dict(sorted(weights.items())),
        "paths": {},
    }
    for path in paths:
        measurement = _summarize_path(
            path, losses[path], phases, weights, terminal_counts[path]
        )
        measurement.exact_match_rate = matches[path] / max(len(usable), 1)
        payload = measurement.to_dict()
        payload["sourceMeans"] = _group_means(losses[path], sources)
        payload["sourceCounts"] = _group_counts(sources)
        out["paths"][path] = payload
    return out


def _group_counts(groups: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in groups:
        counts[group] = counts.get(group, 0) + 1
    return dict(sorted(counts.items()))


def _group_means(values: Sequence[float], groups: Sequence[str]) -> dict[str, float]:
    """Grup (kaynak) basina ortalama -- on-policy sizinti denetimi icin.

    ``self`` kaynagi modelin kendi oynadigi oyunlardan gelir; ``gnubg2``'den
    belirgin sekilde dusuk ER, dagilim duzeyinde sizinti isaretidir (F7-62).
    """
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for value, group in zip(values, groups):
        totals[group] = totals.get(group, 0.0) + value
        counts[group] = counts.get(group, 0) + 1
    return {g: round(totals[g] / counts[g], 6) for g in sorted(totals)}


# ----------------------------------------------------------------------
# Guc tablosu
# ----------------------------------------------------------------------


def power_rows(
    report: dict[str, Any], deltas: Sequence[float] = (0.01, 0.02)
) -> list[dict[str, Any]]:
    """Her yol ve ``delta`` icin gereken n -- **sigma ust sinirindan** (Kural 4).

    Nokta tahmininden hesaplamak n'i sistematik olarak eksik verir; bu yuzden
    ``sigmaCiHigh`` kullanilir.
    """
    rows: list[dict[str, Any]] = []
    for path, data in sorted(report["paths"].items()):
        for delta in deltas:
            rows.append(
                {
                    "path": path,
                    "deltaMin": float(delta),
                    "sigmaCiHigh": float(data["sigmaCiHigh"]),
                    "nOneSided": er_power.required_n_from_upper(
                        float(data["sigmaCiHigh"]), float(delta), two_sided=False
                    ),
                    "nTwoSided": er_power.required_n_from_upper(
                        float(data["sigmaCiHigh"]), float(delta), two_sided=True
                    ),
                    "currentCount": int(data["count"]),
                }
            )
    return rows


def build_markdown(report: dict[str, Any]) -> str:
    """ER raporunu markdown olarak uretir (uc yol + guc tablosu)."""
    lines: list[str] = []
    lines.append("# ER raporu -- uc oynanis yolu")
    lines.append("")
    lines.append("Model: `%s`" % report["model"])
    lines.append("")
    lines.append(
        "Hakem sozlesmesi: `%s` / sutun `%s` / %d-ply / alan `%s`"
        % (
            report["referee"]["command"],
            report["referee"]["column"],
            report["referee"]["plies"],
            report["referee"]["prob"],
        )
    )
    lines.append("")
    lines.append("Vaka sayisi: **%d**" % report["caseCount"])
    lines.append("")
    lines.append("| Yol | n | Ortalama | Medyan | %95 GA | sigma | sigma ust | Agirlikli | Tam eslesme |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for path in PLAY_PATHS:
        if path not in report["paths"]:
            continue
        d = report["paths"][path]
        lines.append(
            "| `%s` | %d | %.4f | %.4f | [%.4f; %.4f] | %.4f | %.4f | %.4f | %.1f%% |"
            % (
                path,
                d["count"],
                d["mean"],
                d["median"],
                d["ciLow"],
                d["ciHigh"],
                d["sigma"],
                d["sigmaCiHigh"],
                d["weightedMean"],
                100.0 * d["exactMatchRate"],
            )
        )
    lines.append("")
    lines.append("## Faz kirilimi")
    lines.append("")
    for path in PLAY_PATHS:
        if path not in report["paths"]:
            continue
        d = report["paths"][path]
        parts = [
            "%s %.4f (n=%d)" % (p, d["phaseMeans"][p], d["phaseCounts"][p])
            for p in sorted(d["phaseMeans"])
        ]
        lines.append("- `%s`: %s" % (path, ", ".join(parts)))
    lines.append("")
    lines.append("## Kaynak kirilimi (on-policy sizinti denetimi)")
    lines.append("")
    for path in PLAY_PATHS:
        if path not in report["paths"]:
            continue
        d = report["paths"][path]
        parts = [
            "%s %.4f (n=%d)" % (s, d["sourceMeans"][s], d["sourceCounts"][s])
            for s in sorted(d.get("sourceMeans", {}))
        ]
        lines.append("- `%s`: %s" % (path, ", ".join(parts)))
    lines.append("")
    lines.append("## Guc tablosu (sigma ust sinirindan)")
    lines.append("")
    lines.append("| Yol | delta_min | n (tek yonlu) | n (iki yonlu) | mevcut n |")
    lines.append("|---|---|---|---|---|")
    for row in power_rows(report):
        lines.append(
            "| `%s` | %.2f | %d | %d | %d |"
            % (
                row["path"],
                row["deltaMin"],
                row["nOneSided"],
                row["nTwoSided"],
                row["currentCount"],
            )
        )
    lines.append("")
    return "\n".join(lines)

# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser():
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        prog="er_paths", description="Faz 7-R: ER'yi uc oynanis yolu icin olc"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    measure = sub.add_parser("measure", help="uc yolu olc")
    measure.add_argument("--model", type=Path, required=True)
    measure.add_argument("--corpus", type=Path, default=None)
    measure.add_argument("--legacy", action="store_true", help="v1 dondurulmus korpusu kullan")
    measure.add_argument("--split", default="all")
    measure.add_argument("--limit", type=int, default=None)
    measure.add_argument("--gnubg", type=Path, default=None)
    measure.add_argument("--plies", type=int, default=2)
    measure.add_argument("--timeout", type=int, default=120)
    measure.add_argument("--out", type=Path, default=None)
    measure.add_argument("--quiet", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import json  # noqa: PLC0415

    import corpus2  # noqa: PLC0415
    import er_harness  # noqa: PLC0415

    args = build_parser().parse_args(argv)

    if args.command != "measure":
        return 2

    if args.legacy:
        corpus = er_harness.load_corpus()
        weights: dict[str, float] = {}
    else:
        path = args.corpus or corpus2.CORPUS2_PATH
        corpus = corpus2.load_corpus2(Path(path))
        weights = dict(corpus.get("realGamePhaseWeights", {}))

    cases = corpus2.select_cases(corpus, args.split) if not args.legacy else er_harness.select_cases(corpus, args.split)
    if args.limit is not None:
        cases = cases[: max(args.limit, 0)]

    gnubg = args.gnubg or gnubg_er.find_gnubg()
    if gnubg is None:
        print("gnubg bulunamadi", file=sys.stderr)
        return 2

    report = measure_paths(
        Path(args.model),
        cases,
        gnubg=Path(gnubg),
        plies=args.plies,
        timeout=args.timeout,
        progress=not args.quiet,
        phase_weights=weights,
    )
    report["corpus"] = "legacy-v1" if args.legacy else "v2"
    report["split"] = args.split

    text = build_markdown(report)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print("\nJSON: %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())