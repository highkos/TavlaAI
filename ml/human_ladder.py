#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 7 Bolum 4.4 - insan karsilastirma merdiveni (Test 94).

"Dunya sampiyonunu yenmek" iddiasi **referanssiz** olculemez. Bu modul yedi
basamakli merdiveni kurar:

| Basamak | Referans | Kaynak |
|---|---|---|
| 0 | gnubg 0-ply | olculur (3-ply hakeme karsi) |
| 1 | gnubg 1-ply | olculur (3-ply hakeme karsi) |
| 2 | gnubg 2-ply | olculur (3-ply hakeme karsi) |
| 3 | gnubg 3-ply (`hint`) | **hakemin kendisi** - kayip tanim geregi 0 |
| 4 | gnubg 4-ply (`hint`) | **olculmedi** - maliyeti sinirsiz (F7-07) |
| 5 | Dunya sampiyonu insan | **literatur** |
| 6 | gnubg 4-ply + buyuk ag | **literatur** |

**Durustluk kurali.** 5. ve 6. basamak **bizim olcumumuz degildir**; literatur
degeridir ve ``source = "literature"`` olarak etiketlenir. 4. basamak da
**olculmedi** olarak etiketlenir: 4-ply ``hint`` (filtre acik) `f6-040`'ta
**900 s** zaman asimina carpti, yani belge 4.2.4'teki 62,57 s/pozisyon
tahmini temsili degildir (F7-07). Uydurma sayi uretilmez.

**Yontem.** Her basamak icin gnubg'nin **kendi** hamle secimi alinir ve
**3-ply hakeme** karsi kaybi olculur:

* ``plies <= 2`` - butun afterstate'ler ``eval`` ile degerlendirilir, argmax
  gnubg'nin secimidir (tam kapsama).
* ``plies == 3`` - hakemin kendisi; kayip **tanim geregi 0**'dir ve
  ``source = "self"`` olarak etiketlenir - olcum gibi raporlanmaz.

Secilen afterstate 3-ply ``hint`` listesinde yoksa pozisyon **sansurlu** olur ve
yalnizca **alt sinir** raporlanir (F7-03). Kapsama birinci sinif metriktir.

Kullanim::

    python ml/human_ladder.py --split cal --json ml/artifacts/stage_a_ladder.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
for _path in (str(ML_DIR), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gnubg_er  # noqa: E402  (yol kurulumundan sonra)
import gnubg_hint  # noqa: E402

#: Hakem derinligi - merdivenin olculen en derin basamagi.
REFEREE_PLIES = 3

#: Hakeme karsi olculen basamaklar.
MEASURED_RUNGS = (0, 1, 2)

#: Hakemin kendisi olan basamak (kayip tanim geregi 0).
SELF_RUNG = REFEREE_PLIES

#: Olculemeyen basamaklar (maliyet sinirsiz - F7-07).
UNMEASURED_RUNGS = (4,)

#: Literatur basamaklari (olculmez).
LITERATURE_RUNGS = (5, 6)

#: Literatur ER degerleri (Bolum 4.4 tablosu).
LITERATURE_ER = {5: 0.0025, 6: 0.003}

#: Literatur basamaklarinin etiketi.
LITERATURE_NOTE = (
    "Bu basamak bizim olcumumuz degildir; literatur degeridir ve 'literature' "
    "olarak etiketlenir (Bolum 4.4 durustluk kurali)."
)

#: 4-ply basamaginin olculememe gerekcesi (olculmus kanit).
UNMEASURED_NOTE = (
    "4-ply 'hint' (filtre acik) f6-040 pozisyonunda 900 s zaman asimina carpti; "
    "belge 4.2.4'teki 62,57 s/pozisyon tahmini temsili degildir (F7-07). "
    "Uydurma sayi uretilmedi."
)

#: Sampiyon iddiasinin ER esigi (Bolum 4.4, 4.5).
CHAMPION_ER_TARGET = 0.005

#: Basamak etiketleri.
RUNG_LABELS = {
    0: "gnubg 0-ply",
    1: "gnubg 1-ply",
    2: "gnubg 2-ply",
    3: "gnubg 3-ply (hint)",
    4: "gnubg 4-ply (hint)",
    5: "Dunya sampiyonu insan",
    6: "gnubg 4-ply + buyuk ag",
}

#: Varsayilan vaka dosyasi (dondurulmus 200 pozisyonluk korpus).
DEFAULT_CASES = REPO_ROOT / "ml" / "artifacts" / "reference_corpus_v1.json"

#: Varsayilan pilot boyu (0 = sinirsiz).
DEFAULT_LIMIT = 0

#: Varsayilan gnubg zaman asimi.
DEFAULT_TIMEOUT = gnubg_hint.DEFAULT_HINT_TIMEOUT

#: Rapor sema surumu.
SCHEMA_VERSION = 1


class LadderError(RuntimeError):
    """Merdiven olcumu yapilamadi."""


# ----------------------------------------------------------------------
# Tek pozisyon
# ----------------------------------------------------------------------


def _loss(
    index: int, equity_ref: dict[int, float], best: float, worst: float
) -> dict[str, Any]:
    """Secilen afterstate'in hakeme karsi kaybi."""
    if index in equity_ref:
        return {
            "loss": max(0.0, best - equity_ref[index]),
            "censored": False,
            "lowerBound": 0.0,
        }
    bound = max(0.0, best - worst)
    return {"loss": bound, "censored": True, "lowerBound": bound}


def choice_index_eval(
    session: gnubg_er.GnubgSession, case: dict[str, Any], plies: int
) -> int:
    """gnubg'nin ``plies``-ply secimini butun afterstate'ler uzerinden bulur."""
    boards = [after["board"] for after in case["afterStates"]]
    tables = session.eval_afterstates(boards, int(case["turn"]))
    equities = [gnubg_er._equity_at(table, plies) for table in tables]
    return max(range(len(equities)), key=lambda i: equities[i])


def measure_position_ladder(
    referee: gnubg_hint.HintReferee,
    sessions: dict[int, gnubg_er.GnubgSession],
    case: dict[str, Any],
) -> dict[str, Any]:
    """Tek pozisyonun butun olculen basamaklardaki kaybini olcer."""
    hints, _text = referee.hint_checked(case["board"], int(case["turn"]), case["dice"])
    best = float(hints[0].equity)
    matched, failures = gnubg_hint.map_hints(hints, case)
    equity_ref = {index: float(hint.equity) for hint, index in matched}
    worst = min(equity_ref.values()) if equity_ref else best

    rungs: dict[str, Any] = {}
    for plies in MEASURED_RUNGS:
        index = choice_index_eval(sessions[plies], case, plies)
        rungs[str(plies)] = _loss(index, equity_ref, best, worst)
    rungs[str(SELF_RUNG)] = {"loss": 0.0, "censored": False, "lowerBound": 0.0}

    return {
        "name": case.get("name", "?"),
        "phase": case.get("phase", "?"),
        "afterstateCount": len(case["afterStates"]),
        "hintCount": len(hints),
        "bestEquity": round(best, 6),
        "bestMove": hints[0].move,
        "mappingFailures": len(failures),
        "rungs": {
            key: {
                "loss": round(value["loss"], 6),
                "censored": value["censored"],
                "lowerBound": round(value["lowerBound"], 6),
            }
            for key, value in rungs.items()
        },
    }


# ----------------------------------------------------------------------
# Ozet
# ----------------------------------------------------------------------


@dataclass
class RungSummary:
    """Bir basamagin ozeti."""

    rung: int
    label: str
    source: str
    plies: int | None
    n: int = 0
    covered: int = 0
    censored: int = 0
    mean: float = 0.0
    mean_lower_bound: float = 0.0
    sigma: float = 0.0
    standard_error: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    note: str = ""

    @property
    def coverage(self) -> float:
        return self.covered / self.n if self.n else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rung": self.rung,
            "label": self.label,
            "source": self.source,
            "plies": self.plies,
            "n": self.n,
            "covered": self.covered,
            "censored": self.censored,
            "coverage": round(self.coverage, 4),
            "mean": round(self.mean, 6),
            "meanLowerBound": round(self.mean_lower_bound, 6),
            "sigma": round(self.sigma, 6),
            "standardError": round(self.standard_error, 6),
            "ciLow": round(self.ci_low, 6),
            "ciHigh": round(self.ci_high, 6),
            "note": self.note,
        }


def summarize_rung(rung: int, losses: Sequence[float], censored: Sequence[bool]) -> RungSummary:
    """Bir basamagin kayiplarindan ozet uretir."""
    n = len(losses)
    summary = RungSummary(
        rung=rung,
        label=RUNG_LABELS[rung],
        source="self" if rung == SELF_RUNG else "measured",
        plies=rung,
        n=n,
        censored=sum(1 for flag in censored if flag),
    )
    summary.covered = n - summary.censored
    if n == 0:
        return summary
    summary.mean = sum(losses) / n
    summary.mean_lower_bound = summary.mean
    if n >= 2:
        variance = sum((x - summary.mean) ** 2 for x in losses) / (n - 1)
        summary.sigma = math.sqrt(variance)
        summary.standard_error = summary.sigma / math.sqrt(n)
        half = 1.96 * summary.standard_error
        summary.ci_low = summary.mean - half
        summary.ci_high = summary.mean + half
    if rung == SELF_RUNG:
        summary.note = "hakemin kendisi; kayip tanim geregi 0 - olcum degildir"
    return summary


def literature_rung(rung: int) -> RungSummary:
    """Literatur basamagi - **olculmez**, etiketlenir."""
    return RungSummary(
        rung=rung,
        label=RUNG_LABELS[rung],
        source="literature",
        plies=None,
        mean=LITERATURE_ER[rung],
        mean_lower_bound=LITERATURE_ER[rung],
        note=LITERATURE_NOTE,
    )


def unmeasured_rung(rung: int) -> RungSummary:
    """Olculemeyen basamak - **uydurma sayi yok**, gerekce yazilir."""
    return RungSummary(
        rung=rung,
        label=RUNG_LABELS[rung],
        source="unmeasured",
        plies=None,
        note=UNMEASURED_NOTE,
    )


def ladder_verdict(rungs: Sequence[RungSummary]) -> dict[str, Any]:
    """Merdivenin **kullanilabilirligini** yazar - sampiyon iddiasini degil.

    Sampiyon iddiasi **modelimizin** gnubg 4-ply'a karsi ER'siyle verilir
    (Bolum 4.4, 4.5); bu merdiven yalnizca referans basamaklarini olcer. Bu
    ayrimi karistirmamak icin burada "sampiyon olduk" cumlesi **kurulmaz**.
    """
    measured = {r.rung: r for r in rungs if r.source == "measured"}
    deepest = measured.get(max(MEASURED_RUNGS)) if measured else None
    if deepest is None or deepest.n < 2:
        return {
            "usable": False,
            "state": "not_proven",
            "sentence": (
                "Merdiven kullanilamaz: en derin olculen basamakta n < 2 "
                "(belirsizlik hesaplanamaz)."
            ),
        }
    if deepest.sigma == 0.0:
        return {
            "usable": False,
            "state": "not_proven",
            "sentence": (
                "Merdiven kullanilamaz: %d-ply basamaginda sigma = 0 "
                "(butun kayiplar ayni; orneklem ayirt edici degil)."
                % deepest.rung
            ),
        }
    return {
        "usable": True,
        "state": "measured",
        "sentence": (
            "Merdiven olculdu: %d-ply basamagi ER %.4f, GA [%.4f; %.4f], "
            "kapsama %.1f%%. Sampiyon iddiasi modelin kendi ER'siyle verilir."
            % (
                deepest.rung,
                deepest.mean,
                deepest.ci_low,
                deepest.ci_high,
                100.0 * deepest.coverage,
            )
        ),
    }


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


def measure(
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    timeout: int = DEFAULT_TIMEOUT,
    progress: Any = None,
) -> dict[str, Any]:
    """Merdiveni olcer ve rapor sozlugu doner."""
    selected = list(cases)
    if not selected:
        raise LadderError("vaka listesi bos")

    referee = gnubg_hint.HintReferee(gnubg, plies=REFEREE_PLIES, timeout=timeout)
    sessions = {
        plies: gnubg_er.GnubgSession(gnubg, plies=plies, timeout=timeout)
        for plies in MEASURED_RUNGS
    }

    positions: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    started = time.time()
    for i, case in enumerate(selected, 1):
        try:
            positions.append(measure_position_ladder(referee, sessions, case))
        except (gnubg_er.GnubgError, gnubg_hint.HintMappingError) as exc:
            skipped.append({"name": case.get("name", "?"), "reason": str(exc)[:200]})
        if progress is not None:
            progress(i, len(selected), positions[-1] if positions else {"name": "?"})
    elapsed = time.time() - started

    rungs: list[RungSummary] = []
    for rung in MEASURED_RUNGS:
        losses = [position["rungs"][str(rung)]["loss"] for position in positions]
        censored = [position["rungs"][str(rung)]["censored"] for position in positions]
        rungs.append(summarize_rung(rung, losses, censored))
    rungs.append(summarize_rung(SELF_RUNG, [0.0] * len(positions), [False] * len(positions)))
    for rung in UNMEASURED_RUNGS:
        rungs.append(unmeasured_rung(rung))
    for rung in LITERATURE_RUNGS:
        rungs.append(literature_rung(rung))

    return {
        "schemaVersion": SCHEMA_VERSION,
        "refereePlies": REFEREE_PLIES,
        "methodNote": gnubg_hint.LADDER_METHOD_NOTE,
        "count": len(positions),
        "skippedCount": len(skipped),
        "skipped": skipped,
        "elapsedSeconds": round(elapsed, 1),
        "secondsPerPosition": round(elapsed / len(selected), 2) if selected else 0.0,
        "rungs": [rung.to_dict() for rung in rungs],
        "verdict": ladder_verdict(rungs),
        "positions": positions,
    }


def build_markdown(report: dict[str, Any]) -> str:
    """Rapor sozlugunu Markdown'a cevirir."""
    lines = [
        "# Insan karsilastirma merdiveni (Test 94)",
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| Hakem derinligi | gnubg `hint`, %d-ply (filtre acik) |" % report["refereePlies"],
        "| Pozisyon | %d (atlanan %d) |" % (report["count"], report["skippedCount"]),
        "| Sure | %.1f s (%.2f s/pozisyon) |"
        % (report["elapsedSeconds"], report["secondsPerPosition"]),
        "",
        "## Basamaklar",
        "",
        "| # | Referans | Kaynak | n | Kapsama | ER | GA |",
        "|---|---|---|---|---|---|---|",
    ]
    for rung in report["rungs"]:
        if rung["source"] == "literature":
            lines.append(
                "| %d | %s | **literatur** | - | - | %.4f | - |"
                % (rung["rung"], rung["label"], rung["mean"])
            )
            continue
        if rung["source"] == "unmeasured":
            lines.append(
                "| %d | %s | **olculmedi** | - | - | - | - |"
                % (rung["rung"], rung["label"])
            )
            continue
        lines.append(
            "| %d | %s | %s | %d | %.1f%% | %.4f | [%.4f; %.4f] |"
            % (
                rung["rung"],
                rung["label"],
                rung["source"],
                rung["n"],
                100.0 * rung["coverage"],
                rung["mean"],
                rung["ciLow"],
                rung["ciHigh"],
            )
        )
    lines.extend(
        [
            "",
            "## Karar",
            "",
            "**%s** - %s" % (report["verdict"]["state"], report["verdict"]["sentence"]),
            "",
            "## Yontem notu",
            "",
            report["methodNote"],
            "",
            "5. ve 6. basamak **olculmedi**: literatur degeridir ve oyle",
            "etiketlenmistir. 4. basamak da **olculmedi**: 4-ply `hint` maliyeti",
            "sinirsizdir (F7-07). Kendi modelimizin ER'si 0-3 basamaklarinda olculur.",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(report: dict[str, Any], path: Path) -> None:
    """Raporu JSON olarak yazar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def load_cases(path: Path, split: str = "all") -> list[dict[str, Any]]:
    """Vaka dosyasini okur; ``split`` verilirse o bolunmeyi secer."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not cases:
        raise LadderError("vaka dosyasi bos: %s" % path)
    cases = list(cases)
    if split == "all":
        return cases
    splits = data.get("splits") if isinstance(data, dict) else None
    if not splits or split not in splits:
        raise LadderError("bilinmeyen bolunme: %r" % (split,))
    wanted = set(splits[split])
    return [case for case in cases if case.get("name") in wanted]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Faz 7 Bolum 4.4 - insan karsilastirma merdiveni (Test 94)."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--split", choices=("all", "cal", "val", "test"), default="all")
    parser.add_argument("--gnubg", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gnubg = gnubg_er.find_gnubg(args.gnubg)
    if gnubg is None:
        print(
            "HATA: gnubg-cli bulunamadi. Kurun veya --gnubg / GNUBG_CLI ile yol verin.\n"
            "      Uydurma deger uretilmedi.",
            file=sys.stderr,
        )
        return 2
    try:
        cases = load_cases(args.cases, args.split)
    except (OSError, ValueError, LadderError) as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2
    if args.offset:
        cases = cases[args.offset :]
    if args.limit:
        cases = cases[: args.limit]

    started = time.time()

    def _progress(index: int, total: int, position: dict[str, Any]) -> None:
        print(
            "  [%d/%d] %s (%.1f s)"
            % (index, total, position["name"], time.time() - started),
            flush=True,
        )

    report = measure(
        cases,
        gnubg=gnubg,
        timeout=args.timeout,
        progress=None if args.quiet else _progress,
    )
    print(
        "gnubg %s | %d pozisyon (atlanan %d) | %.1f s (%.2f s/pozisyon)"
        % (
            gnubg_er.gnubg_version(gnubg) or "(surum okunamadi)",
            report["count"],
            report["skippedCount"],
            report["elapsedSeconds"],
            report["secondsPerPosition"],
        )
    )
    for rung in report["rungs"]:
        if rung["source"] == "literature":
            print("  %d %-26s literatur   ER %.4f" % (rung["rung"], rung["label"], rung["mean"]))
        elif rung["source"] == "unmeasured":
            print("  %d %-26s olculmedi" % (rung["rung"], rung["label"]))
        else:
            print(
                "  %d %-26s %-8s n=%d kapsama %.1f%% ER %.4f GA [%.4f; %.4f]"
                % (
                    rung["rung"],
                    rung["label"],
                    rung["source"],
                    rung["n"],
                    100.0 * rung["coverage"],
                    rung["mean"],
                    rung["ciLow"],
                    rung["ciHigh"],
                )
            )
    print("karar: %s - %s" % (report["verdict"]["state"], report["verdict"]["sentence"]))

    if args.json:
        write_json(report, args.json)
        print("JSON: %s" % args.json)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")
        print("Markdown: %s" % args.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
