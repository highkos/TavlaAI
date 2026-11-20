"""Python-C# hamle kumesi esitligi - Faz 7-R adim 0 (F7-86).

``tools/reference_gen.py`` Python'da **ikinci bir hamle uretici** tutuyor.
Bu, dort ayri olcum kusurunun kaynagi oldu (F7-80). Kalici cozum, iki
ureticinin **kume esitligini** surekli dogrulamaktir.

Akis:

1. ``Backgammon.MatchBench moveset --positions <in> --out <cs.json>``
   C# ``LegalMoveGenerator`` ciktisini doker.
2. Bu modul ayni vakalari ``reference_gen.legal_after_states`` ile uretir.
3. Kume esitligi karsilastirilir: ``(board, whiteOff, blackOff)`` uclusu.

**Kume esitligi, siralama degil.** Iki uretici ayni kumeyi farkli sirada
uretebilir; siralama farki parite kusuru degildir. Bu yuzden karsilastirma
``set`` uzerinden yapilir ve siralama farki ayrica raporlanir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import reference_gen as refgen  # noqa: E402

MOVESET_VERSION = 1
MOVESET_PATH = "ml/artifacts/moveset_parity.json"
MOVESET_MD_PATH = "ml/artifacts/moveset_parity.md"
DEFAULT_CASES = "ml/artifacts/reference_corpus_v2.json"
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261124
AGREE_MIN = 1.0


class MoveSetError(RuntimeError):
    """Hamle kumesi karsilastirmasi yapilamadi."""


def _key(board: Sequence[int], white_off: int, black_off: int) -> tuple:
    return (tuple(int(x) for x in board), int(white_off), int(black_off))


def _bootstrap_ci(flags: np.ndarray, resamples: int, seed: int) -> tuple[float, float]:
    if flags.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, flags.size, size=(resamples, flags.size))
    means = flags[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def compare_case(case: dict[str, Any], cs_case: dict[str, Any]) -> dict[str, Any]:
    """Tek bir vaka icin Python ve C# kumelerini karsilastirir."""
    turn = int(case["turn"])
    dice = [int(d) for d in case["dice"]]
    expanded = [dice[0]] * 4 if dice[0] == dice[1] else list(dice)
    white_off = int(case.get("whiteOff", 0))
    black_off = int(case.get("blackOff", 0))

    max_steps, py_states = refgen.legal_after_states(
        case["board"], turn, expanded, white_off, black_off
    )
    py_set = set(_key(b, w, k) for (b, w, k) in py_states)

    cs_set = set()
    for a in cs_case.get("afterStates", []):
        cs_set.add(_key(a["board"], a["whiteOff"], a["blackOff"]))

    only_py = py_set - cs_set
    only_cs = cs_set - py_set
    return {
        "name": str(case.get("name", "?")),
        "turn": turn,
        "dice": dice,
        "maxSteps": int(max_steps),
        "pyCount": len(py_set),
        "csCount": len(cs_set),
        "onlyPy": len(only_py),
        "onlyCs": len(only_cs),
        "equal": py_set == cs_set,
        "onlyPySample": [list(k[0]) for k in list(only_py)[:2]],
        "onlyCsSample": [list(k[0]) for k in list(only_cs)[:2]],
    }


class MoveSetReport:
    """Hamle kumesi paritesinin tamami."""

    def __init__(self, *, corpus: str) -> None:
        self.corpus = corpus
        self.cases: list[dict[str, Any]] = []
        self.notes: list[str] = []

    @property
    def count(self) -> int:
        return len(self.cases)

    @property
    def agree(self) -> int:
        return sum(1 for c in self.cases if c["equal"])

    @property
    def rate(self) -> float:
        return self.agree / self.count if self.count else float("nan")

    @property
    def ci(self) -> tuple[float, float]:
        flags = np.asarray([1.0 if c["equal"] else 0.0 for c in self.cases], dtype=np.float64)
        return _bootstrap_ci(flags, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)

    @property
    def passed(self) -> bool:
        return bool(self.count > 0 and self.rate >= AGREE_MIN)

    def to_dict(self) -> dict[str, Any]:
        low, high = self.ci
        return {
            "movesetVersion": MOVESET_VERSION,
            "corpus": self.corpus,
            "count": self.count,
            "agree": self.agree,
            "rate": self.rate,
            "ciLow": low,
            "ciHigh": high,
            "agreeMin": AGREE_MIN,
            "passed": self.passed,
            "mismatches": [c for c in self.cases if not c["equal"]][:20],
            "notes": list(self.notes),
        }


def measure_moveset(
    cases: Sequence[dict[str, Any]],
    cs_cases: Sequence[dict[str, Any]],
    *,
    corpus: str = "",
    progress: bool = False,
) -> MoveSetReport:
    """Python ve C# hamle kumelerini karsilastirir."""
    by_name = {str(c.get("name")): c for c in cs_cases}
    report = MoveSetReport(corpus=corpus)
    missing = 0
    for index, case in enumerate(cases, start=1):
        name = str(case.get("name"))
        if progress and index % 200 == 0:
            print("[%d/%d]" % (index, len(cases)), file=sys.stderr)
        cs_case = by_name.get(name)
        if cs_case is None:
            missing += 1
            continue
        report.cases.append(compare_case(case, cs_case))
    if missing:
        report.notes.append("C# ciktisinda yok: %d vaka" % missing)
    if not report.cases:
        raise MoveSetError("karsilastirilacak vaka yok")
    if not report.passed:
        report.notes.append(
            "KUME ESITLIGI DUSTU: %.4f < %.2f" % (report.rate, AGREE_MIN)
        )
    return report


def build_markdown(report: MoveSetReport) -> str:
    low, high = report.ci
    lines = [
        "# Faz 7-R - Python/C# hamle kumesi esitligi",
        "",
        "Soru: **Python `reference_gen` ile urun `LegalMoveGenerator` ayni",
        "yasal hamle kumesini mi uretiyor?**",
        "",
        "Korpus: `%s`" % report.corpus,
        "",
        "| Olcum | Deger | Kapi | Durum |",
        "|---|---|---|---|",
        "| Kume esitligi | %d/%d (%.4f) | `>= %.2f` | %s |"
        % (
            report.agree,
            report.count,
            report.rate,
            AGREE_MIN,
            "GECTI" if report.passed else "DUSTU",
        ),
        "",
        "| Ayrinti | Deger |",
        "|---|---|",
        "| Kume esitligi %%95 GA | [%.4f; %.4f] |" % (low, high),
        "| Vaka | %d |" % report.count,
        "",
    ]
    if report.notes:
        lines.append("## Notlar")
        lines.append("")
        for note in report.notes:
            lines.append("- " + note)
        lines.append("")
    mismatches = [c for c in report.cases if not c["equal"]]
    if mismatches:
        lines.append("## Uyusmazliklar (ilk 20)")
        lines.append("")
        lines.append("| Vaka | Zar | Python | C# | Yalniz Python | Yalniz C# |")
        lines.append("|---|---|---|---|---|---|")
        for c in mismatches[:20]:
            lines.append(
                "| `%s` | %d-%d | %d | %d | %d | %d |"
                % (
                    c["name"],
                    c["dice"][0],
                    c["dice"][1],
                    c["pyCount"],
                    c["csCount"],
                    c["onlyPy"],
                    c["onlyCs"],
                )
            )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moveset_parity",
        description="Python-C# hamle kumesi esitligi - Faz 7-R adim 0",
    )
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--cs", required=True, help="C# moveset ciktisi")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--out", default=MOVESET_PATH)
    parser.add_argument("--markdown", default=MOVESET_MD_PATH)
    parser.add_argument("--progress", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if args.stride > 1:
        cases = cases[:: args.stride]
    if args.limit > 0:
        cases = cases[: args.limit]

    cs_data = json.loads(Path(args.cs).read_text(encoding="utf-8"))
    cs_cases = cs_data.get("cases") if isinstance(cs_data, dict) else cs_data

    report = measure_moveset(
        cases, cs_cases, corpus=str(args.cases), progress=args.progress
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")

    print("vaka: %d" % report.count)
    print("kume esitligi: %d/%d (%.4f)" % (report.agree, report.count, report.rate))
    print("karar: %s" % ("GECTI" if report.passed else "DUSTU"))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
