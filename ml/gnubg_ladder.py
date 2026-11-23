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
import gnubg_hint

LADDER_VERSION = 2
LADDER_PATH = "ml/artifacts/gnubg_ladder.json"
LADDER_MD_PATH = "ml/artifacts/gnubg_ladder.md"
DEFAULT_CASES = "ml/artifacts/reference_corpus_v2.json"
DEFAULT_PLAYER_PLIES = (0, 1)
REFEREE_PLIES = gnubg_er.MAX_EVAL_PLIES

#: Derin hakem (``hint``) merdiveni: oyuncu derinlikleri ve hakem derinligi.
#: R-F madde 1'in istedigi "daha derin hakem" budur; ``hint`` 4-ply'e kadar
#: deger uretir (F7-01), ``eval`` yalnizca 2-ply'e (F6-32).
DEEP_REFEREE_PLIES = gnubg_hint.HINT_MAX_PLIES
DEEP_PLAYER_PLIES = (0, 1, 2, 3)
DEEP_DEFAULT_LIMIT = 100
DEEP_LADDER_PATH = "ml/artifacts/gnubg_ladder_deep.json"
DEEP_LADDER_MD_PATH = "ml/artifacts/gnubg_ladder_deep.md"
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261123

#: R-F madde 1, olculemeyen basamaklar. gnubg ``eval`` en fazla 2-ply sutun
#: uretir (F6-32); 2-ply ve uzeri icin **daha derin** bir hakem gerekir ve o
#: hakem gnubg'de yok. Satirlar sifir uydurmadan ``olculemez`` isaretlenir.
UNMEASURABLE_PLIES = (2, 3, 4)

_UNMEASURABLE_REASONS = {
    2: (
        "Hakem kendi kendini olcemez; 2-ply'in ER'i icin 3-ply/rollout "
        "referans gerekir ve gnubg 'eval' 2-ply'den derin sutun uretmez "
        "(F6-32). R-F madde 1 uyarinca 'olculemez' isaretlendi."
    ),
    3: (
        "3-ply oyuncu icin 4-ply hakem gerekir; gnubg 3-ply'i yalnizca "
        "'hint' protokolu ile verir ve 'hint' afterstate basina deger "
        "dondurmez (F6-32). R-F madde 1 uyarinca 'olculemez' isaretlendi."
    ),
    4: (
        "4-ply gnubg'de yok (en derin statik degerlendirme 3-ply, en derin "
        "'eval' sutunu 2-ply). R-F madde 1'in ongordugu 'daha derin referans "
        "(5-ply/rollout)' bu makinede mevcut degil; satir 'olculemez'."
    ),
}


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


def measure_deep_ladder(
    exe: Path,
    cases: Sequence[dict[str, Any]],
    *,
    referee_plies: int = DEEP_REFEREE_PLIES,
    player_plies: Sequence[int] = DEEP_PLAYER_PLIES,
    timeout: int = gnubg_hint.DEFAULT_HINT_TIMEOUT,
    limit: int | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    """``hint`` derin hakemine gore 0/1/2/3-ply ER merdiveni (R-F madde 1).

    Hakem maliyeti **pozisyon basina bir kez** odenir (``hint`` cagrisi), sonra
    her oyuncu derinligi icin yalnizca ``eval`` yapilir. Bu yuzden 4-ply hakem
    tek basina pahali olsa da merdivenin tamami tek hakem maliyetiyle cikar.

    ``hint`` en fazla ``HINT_MOVE_CAP`` hamle basar (F7-03); oyuncunun sectigi
    afterstate listede yoksa pozisyon **sansurlu** sayilir ve ER'e girmez.
    Sansurlu orani raporlanir; sessiz atlama yok (Kural 6).
    """
    if referee_plies < gnubg_hint.HINT_REFEREE_MIN_PLIES:
        raise LadderError(
            "derin hakem >= %d-ply olmali (F7-04); verilen %d"
            % (gnubg_hint.HINT_REFEREE_MIN_PLIES, referee_plies)
        )
    for p in player_plies:
        if p >= referee_plies:
            raise LadderError(
                "oyuncu derinligi (%d) hakem derinliginden (%d) kucuk olmali"
                % (p, referee_plies)
            )

    usable, skipped = gnubg_er.split_cases(cases)
    if limit:
        usable = usable[: int(limit)]
    if not usable:
        raise LadderError("kullanilabilir vaka yok")

    referee = gnubg_hint.HintReferee(exe, plies=referee_plies, timeout=timeout)
    players = {
        p: gnubg_er.GnubgSession(exe, plies=p, timeout=timeout)
        for p in player_plies
        if p <= gnubg_er.MAX_EVAL_PLIES
    }
    # gnubg `eval` en fazla 2-ply uretir (F6-32); 3-ply ve uzeri oyuncunun
    # kendi secimi `hint` listesinin 1. sirasidir.
    hint_players = {
        p: gnubg_hint.HintReferee(exe, plies=p, timeout=timeout)
        for p in player_plies
        if p > gnubg_er.MAX_EVAL_PLIES
    }

    losses: dict[int, list[float]] = {p: [] for p in player_plies}
    exact: dict[int, int] = {p: 0 for p in player_plies}
    censored: dict[int, int] = {p: 0 for p in player_plies}
    mapping_failures = 0

    for index, case in enumerate(usable, start=1):
        if progress:
            print(
                "[%d/%d] %s" % (index, len(usable), case.get("name", "?")),
                file=sys.stderr,
            )
        turn = int(case["turn"])
        hints, _text = referee.hint_checked(case["board"], turn, case["dice"])
        matched, failures = gnubg_hint.map_hints(hints, case)
        mapping_failures += len(failures)
        if not matched:
            for p in player_plies:
                censored[p] += 1
            continue
        ref = {idx: float(h.equity) for h, idx in matched}
        best = max(ref.values())
        boards = [a["board"] for a in case["afterStates"]]
        for p in player_plies:
            if p in players:
                tables = players[p].eval_afterstates(boards, -turn)
                play = [-gnubg_er._equity_at(t, p) for t in tables]
                pick = int(np.argmax(play))
            else:
                own, _own_text = hint_players[p].hint_checked(
                    case["board"], turn, case["dice"]
                )
                own_matched, _own_fail = gnubg_hint.map_hints(own, case)
                if not own_matched:
                    censored[p] += 1
                    continue
                pick = own_matched[0][1]
            if pick not in ref:
                censored[p] += 1
                continue
            loss = best - ref[pick]
            losses[p].append(loss)
            if abs(loss) < 1e-12:
                exact[p] += 1

    rungs: list[dict[str, Any]] = []
    for p in player_plies:
        arr = np.asarray(losses[p], dtype=np.float64)
        low, high = _bootstrap_ci(arr, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
        rungs.append(
            {
                "playerPlies": int(p),
                "refereePlies": int(referee_plies),
                "referee": "hint",
                "measurable": True,
                "count": int(arr.size),
                "skipped": len(skipped),
                "censored": int(censored[p]),
                "coverage": float(arr.size) / max(len(usable), 1),
                "mean": float(arr.mean()) if arr.size else None,
                "ciLow": low,
                "ciHigh": high,
                "sigma": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
                "exactMatchRate": exact[p] / max(arr.size, 1),
            }
        )
    return {
        "refereePlies": int(referee_plies),
        "referee": "hint",
        "positions": len(usable),
        "mappingFailures": mapping_failures,
        "methodNote": referee.method_note,
        "rungs": rungs,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Faz 7-R - gnubg ER merdiveni",
        "",
        "Soru: **model merdivende nerede?** Ayni korpusta gnubg'nin kendi",
        "0/1-ply ER'si, 2-ply hakeme gore; 2/3/4-ply satirlari olculemez.",
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


def build_deep_markdown(report: dict[str, Any]) -> str:
    """Derin hakem merdiveninin Markdown raporu."""
    lines = [
        "# Faz 7-R - derin hakem (`hint`) ER merdiveni",
        "",
        "Soru: **2-ply hakemin kendi ER'si ne kadar?** gnubg'nin 0/1/2/3-ply",
        "degerlendirmesi, **%d-ply `hint`** hakemine gore (R-F madde 1)."
        % report["refereePlies"],
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| Hakem | gnubg `hint`, %d-ply (filtre acik) |" % report["refereePlies"],
        "| Pozisyon | %d |" % report["positions"],
        "| Eslesme hatasi | %d |" % report["mappingFailures"],
        "",
        "| Oyuncu | n | Kapsama | Sansurlu | ER | %95 GA | sigma | Tam eslesme |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for rung in report["rungs"]:
        if rung.get("mean") is None:
            lines.append(
                "| gnubg %d-ply | 0 | - | %d | **olculemez** | - | - | - |"
                % (rung["playerPlies"], rung.get("censored", 0))
            )
            continue
        lines.append(
            "| gnubg %d-ply | %d | %.1f%% | %d | **%.4f** | [%.4f; %.4f] | %.4f | %.4f |"
            % (
                rung["playerPlies"],
                rung["count"],
                100.0 * rung.get("coverage", 0.0),
                rung.get("censored", 0),
                rung["mean"],
                rung["ciLow"],
                rung["ciHigh"],
                rung["sigma"],
                rung["exactMatchRate"],
            )
        )
    lines.append("")
    if report.get("methodNote"):
        lines.append("> **Yontem notu (F7-04):** %s" % report["methodNote"])
        lines.append("")
    lines.append(
        "**ER cozunurluk tabani.** 2-ply hakemin %d-ply hakeme gore ER'si, "
        "olculen model ER'lerinin altinda kalan gurultu tabanidir: bundan kucuk "
        "farklar yontem gurultusudur." % report["refereePlies"]
    )
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
        help=(
            "model ER artefakti; virgulle ayrilmis liste verilebilir "
            "(her biri merdivene ayri model olarak eklenir)"
        ),
    )
    parser.add_argument("--out", default=LADDER_PATH)
    parser.add_argument("--markdown", default=LADDER_MD_PATH)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument(
        "--models-only",
        action="store_true",
        help="olcum yapmadan yalnizca model satirlarini --model-er'den tazele",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="yalnizca derin (hint) hakem merdivenini olc",
    )
    parser.add_argument(
        "--deep-referee-plies", type=int, default=DEEP_REFEREE_PLIES
    )
    parser.add_argument(
        "--deep-player-plies",
        default=",".join(str(p) for p in DEEP_PLAYER_PLIES),
        help="virgulle ayrilmis oyuncu derinlikleri (derin hakem)",
    )
    parser.add_argument("--deep-limit", type=int, default=DEEP_DEFAULT_LIMIT)
    parser.add_argument("--deep-out", default=DEEP_LADDER_PATH)
    parser.add_argument("--deep-markdown", default=DEEP_LADDER_MD_PATH)
    return parser


def _model_rows(path: Path, prefix: str = "") -> list[dict[str, Any]]:
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
                "label": (prefix + path_name) if prefix else path_name,
                "count": int(entry.get("count", 0)),
                "mean": float(mean),
                "ciLow": float(entry.get("ciLow", float("nan"))),
                "ciHigh": float(entry.get("ciHigh", float("nan"))),
                "sigma": float(entry.get("sigma", float("nan"))),
            }
        )
    return rows


def _model_label(path: Path) -> str:
    """``ml/runs/capacity_rd/large/seed0/er_paths.json`` -> ``rd/large/seed0``."""
    parts = list(path.parts)
    if "runs" in parts:
        tail = parts[parts.index("runs") + 1 :]
        if tail and tail[-1].startswith("er_paths"):
            tail = tail[:-1]
        if tail:
            return "/".join(tail)
    return path.stem


def _collect_models(model_er: str) -> list[dict[str, Any]]:
    """``--model-er`` virgullu listesini merdiven model satirlarina cevirir."""
    model_paths = [Path(s.strip()) for s in str(model_er).split(",") if s.strip()]
    models: list[dict[str, Any]] = []
    for model_path in model_paths:
        prefix = "" if len(model_paths) == 1 else _model_label(model_path) + ":"
        models.extend(_model_rows(model_path, prefix))
    return models


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.models_only:
        out = Path(args.out)
        report = json.loads(out.read_text(encoding="utf-8"))
        report["models"] = _collect_models(args.model_er)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        md = Path(args.markdown)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(build_markdown(report) + "\n", encoding="utf-8")
        print("model satiri: %d" % len(report["models"]))
        print("JSON: %s" % out)
        return 0

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases") or cases.get("positions") or []
    if args.stride > 1:
        cases = cases[:: args.stride]
    if args.limit > 0:
        cases = cases[: args.limit]

    exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()

    if args.deep:
        deep_plies = [int(p) for p in str(args.deep_player_plies).split(",") if p.strip()]
        deep = measure_deep_ladder(
            exe,
            cases,
            referee_plies=args.deep_referee_plies,
            player_plies=deep_plies,
            timeout=args.timeout,
            limit=args.deep_limit if args.deep_limit > 0 else None,
            progress=args.progress,
        )
        for rung in deep["rungs"]:
            if rung["mean"] is None:
                print("gnubg %d-ply: olculemez" % rung["playerPlies"])
                continue
            print(
                "gnubg %d-ply vs hint@%d: ER %.4f GA [%.4f; %.4f] (n=%d, kapsama %.1f%%)"
                % (
                    rung["playerPlies"],
                    deep["refereePlies"],
                    rung["mean"],
                    rung["ciLow"],
                    rung["ciHigh"],
                    rung["count"],
                    100.0 * rung["coverage"],
                )
            )
        deep_out = Path(args.deep_out)
        deep_out.parent.mkdir(parents=True, exist_ok=True)
        deep_out.write_text(
            json.dumps(deep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        deep_md = Path(args.deep_markdown)
        deep_md.parent.mkdir(parents=True, exist_ok=True)
        deep_md.write_text(build_deep_markdown(deep) + "\n", encoding="utf-8")
        print("JSON: %s" % deep_out)
        return 0

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

    for p in UNMEASURABLE_PLIES:
        rungs.append(unmeasurable_rung(p, _UNMEASURABLE_REASONS[p]))

    model_paths = [Path(s.strip()) for s in str(args.model_er).split(",") if s.strip()]
    model_paths = [Path(s.strip()) for s in str(args.model_er).split(",") if s.strip()]
    models: list[dict[str, Any]] = _collect_models(args.model_er)

    report = {
        "ladderVersion": LADDER_VERSION,
        "corpus": str(args.cases),
        "refereePlies": int(REFEREE_PLIES),
        "rungs": rungs,
        "models": models,
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
