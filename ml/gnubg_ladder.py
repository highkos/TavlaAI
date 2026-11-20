"""gnubg ER merdiveni - Faz 7-R adim 0 (F7-85).

Modeli merdivende konumlandiran tek olcum: **ayni korpusta** gnubg'nin
kendi 0/1-ply ER'si, 2-ply hakeme gore.

Yontem (``gnubg_er.measure_position`` ile ayni mantik):

* Hakem ``R``-ply: her adayin referans equity'si.
* Oyuncu ``P``-ply: gnubg'nin kendi degerlendirmesi; ``argmax`` secilir.
* ``ER = max(ref) - ref[argmax_P]``.

**Hakem tavanı 2-ply.** gnubg ``eval`` yalnizca ``static``/``1 ply``/``2 ply``
sutunlari uretir (F6-32); 3-ply ve uzeri icin ``hint`` protokolu gerekir ve
``hint`` afterstate basina deger vermez. Bu yuzden:

* 0-ply ve 1-ply basamaklari **olculur** (hakem 2-ply),
* 2-ply basamagi **olculemez** (hakem kendisi olurdu; ER tanim geregi 0) ve
  raporda ``olculemez`` olarak isaretlenir -- R-F madde 1'in istedigi gibi.

Sessiz fallback yok (Kural 6): ``P >= R`` hata verir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

import gnubg_er

LADDER_VERSION = 1
LADDER_PATH = "ml/artifacts/gnubg_ladder.json"
LADDER_MD_PATH = "ml/artifacts/gnubg_ladder.md"
DEFAULT_CASES = "ml/artifacts/reference_corpus_v2.json"
DEFAULT_PLAYER_PLIES = (0, 1)
REFEREE_PLIES = gnubg_er.MAX_EVAL_PLIES
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261123


class LadderError(RuntimeError):
    """Merdiven olcumu yapilamadi."""


def _bootstrap_ci(values: np.ndarray, resamples: int, seed: int) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(resamples, values.size))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def measure_rung(
    referee: gnubg_er.GnubgSession,
    player: gnubg_er.GnubgSession,
    cases: Sequence[dict[str, Any]],
    *,
    player_plies: int,
    referee_plies: int = REFEREE_PLIES,
    progress: bool = False,
) -> dict[str, Any]:
    """Tek bir ``P``-ply basamagi olcer."""
    if player_plies >= referee_plies:
        raise LadderError(
            "player_plies (%d) < referee_plies (%d) olmali; aksi halde ER tanim "
            "geregi 0'dir" % (player_plies, referee_plies)
        )
    usable, skipped = gnubg_er.split_cases(cases)
    if not usable:
        raise LadderError("kullanilabilir vaka yok")

    losses: list[float] = []
    exact = 0
    for index, case in enumerate(usable, start=1):
        if progress:
            print(
                "[%d/%d] %s" % (index, len(usable), case.get("name", "?")),
                file=sys.stderr,
            )
        turn = int(case["turn"])
        boards = [a["board"] for a in case["afterStates"]]
        if not boards:
            continue
        ref_tables = referee.eval_afterstates(boards, -turn)
        ref = [-gnubg_er._equity_at(t, referee_plies) for t in ref_tables]
        play_tables = player.eval_afterstates(boards, -turn)
        play = [-gnubg_er._equity_at(t, player_plies) for t in play_tables]
        best = max(ref)
        pick = int(np.argmax(play))
        losses.append(best - ref[pick])
        if abs(best - ref[pick]) < 1e-12:
            exact += 1

    arr = np.asarray(losses, dtype=np.float64)
    low, high = _bootstrap_ci(arr, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    return {
        "playerPlies": int(player_plies),
        "refereePlies": int(referee_plies),
        "measurable": True,
        "count": int(arr.size),
        "skipped": len(skipped),
        "mean": float(arr.mean()),
        "ciLow": low,
        "ciHigh": high,
        "sigma": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        "exactMatchRate": exact / max(arr.size, 1),
    }


def unmeasurable_rung(plies: int, reason: str) -> dict[str, Any]:
    """Olculemeyen basamak -- sifir uydurulmaz."""
    return {
        "playerPlies": int(plies),
        "refereePlies": int(plies),
        "measurable": False,
        "count": 0,
        "skipped": 0,
        "mean": None,
        "ciLow": None,
        "ciHigh": None,
        "sigma": None,
        "exactMatchRate": None,
        "reason": reason,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Faz 7-R - gnubg ER merdiveni",
        "",
        "Soru: **model merdivende nerede?** Ayni korpusta gnubg'nin kendi",
        "0/1-ply ER'si, 2-ply hakeme gore.",
        "",
        "Korpus: `%s`" % report["corpus"],
        "Hakem: gnubg **%d-ply**" % report["refereePlies"],
        "",
        "| Oyuncu | n | ER | %95 GA | sigma | Tam eslesme |",
        "|---|---|---|---|---|---|",
    ]
    for rung in report["rungs"]:
        if not rung["measurable"]:
            lines.append(
                "| gnubg %d-ply | - | **olculemez** | - | - | - |"
                % rung["playerPlies"]
            )
            continue
        lines.append(
            "| gnubg %d-ply | %d | **%.4f** | [%.4f; %.4f] | %.4f | %.4f |"
            % (
                rung["playerPlies"],
                rung["count"],
                rung["mean"],
                rung["ciLow"],
                rung["ciHigh"],
                rung["sigma"],
                rung["exactMatchRate"],
            )
        )
    for m in report.get("models", []):
        lines.append(
            "| **model** `%s` | %d | **%.4f** | [%.4f; %.4f] | %.4f | - |"
            % (
                m["label"],
                m["count"],
                m["mean"],
                m["ciLow"],
                m["ciHigh"],
                m["sigma"],
            )
        )
    lines.append("")
    lines.append("## Notlar")
    lines.append("")
    for note in report.get("notes", []):
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnubg_ladder",
        description="gnubg ER merdiveni - Faz 7-R adim 0",
    )
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument(
        "--player-plies",
        default=",".join(str(p) for p in DEFAULT_PLAYER_PLIES),
        help="virgulle ayrilmis oyuncu derinlikleri",
    )
    parser.add_argument("--gnubg", default=None)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--model-er",
        default="ml/artifacts/er_paths_v2.json",
        help="model ER artefakti (merdivene eklenir)",
    )
    parser.add_argument("--out", default=LADDER_PATH)
    parser.add_argument("--markdown", default=LADDER_MD_PATH)
    parser.add_argument("--progress", action="store_true")
    return parser


def _model_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for path_name, entry in sorted((data.get("paths") or {}).items()):
        if not isinstance(entry, dict):
            continue
        mean = entry.get("mean")
        if mean is None:
            continue
        rows.append(
            {
                "label": path_name,
                "count": int(entry.get("count", 0)),
                "mean": float(mean),
                "ciLow": float(entry.get("ciLow", float("nan"))),
                "ciHigh": float(entry.get("ciHigh", float("nan"))),
                "sigma": float(entry.get("sigma", float("nan"))),
            }
        )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases") or cases.get("positions") or []
    if args.stride > 1:
        cases = cases[:: args.stride]
    if args.limit > 0:
        cases = cases[: args.limit]

    exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()
    referee = gnubg_er.GnubgSession(exe, plies=REFEREE_PLIES, timeout=args.timeout)

    plies = [int(p) for p in str(args.player_plies).split(",") if p.strip()]
    rungs = []
    for p in plies:
        player = gnubg_er.GnubgSession(exe, plies=p, timeout=args.timeout)
        rung = measure_rung(
            referee,
            player,
            cases,
            player_plies=p,
            progress=args.progress,
        )
        rungs.append(rung)
        print(
            "gnubg %d-ply: ER %.4f GA [%.4f; %.4f] (n=%d)"
            % (p, rung["mean"], rung["ciLow"], rung["ciHigh"], rung["count"])
        )

    rungs.append(
        unmeasurable_rung(
            REFEREE_PLIES,
            "Hakem kendi kendini olcemez; 2-ply'in ER'i icin 3-ply/rollout "
            "referans gerekir ve gnubg 'eval' 2-ply'den derin sutun uretmez "
            "(F6-32). R-F madde 1 uyarinca 'olculemez' isaretlendi.",
        )
    )

    report = {
        "ladderVersion": LADDER_VERSION,
        "corpus": str(args.cases),
        "refereePlies": int(REFEREE_PLIES),
        "rungs": rungs,
        "models": _model_rows(Path(args.model_er)),
        "notes": [
            "Hakem kendi kendini olcemez: oyuncu derinligi < hakem derinligi olmali.",
            "ER tanimi `gnubg_er.measure_position` ile ayni: max(ref) - ref[argmax_P].",
            "Ayni korpus, ayni hakem: model ER'si ile dogrudan karsilastirilabilir.",
            "Model satirlari `ml/artifacts/er_paths_v2.json`'dan okunur; burada "
            "yeniden olculmez (tek kaynak).",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")
    print("JSON: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
