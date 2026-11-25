"""100k veri ile xlarge kosusunun 3-5. adimlari.

Uc is yapar:

1. ``select``  — tarama ciktisindan **yalnizca valTop1**'e bakarak tohum secer.
   ER'ye bakmadan secim yapmak, tohum secme yanliligini onler (EVREN 9.3).
2. ``report``  — ppg sonucunu ``equivalence_verdict`` ile etiketler, taban
   kosuyla karsilastirir ve ``ml/artifacts`` altina JSON + Markdown yazar.
3. ``check``   — birlesik veri dosyasinin egitime hazir olup olmadigini dogrular.

Karar kurali kosudan **once** sabittir: ``m = 0.1115`` ppg, uc sonuc dali.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from ppg_measure import EQUIVALENCE_LABELS, equivalence_verdict  # noqa: E402

#: R-F madde 3/5: para oyunu icin sabitlenmis denklik marji (ppg).
DEFAULT_MARGIN = 0.1115

#: Karar agacinin dallari (EVREN 9.3).
BRANCHES = {
    "esdeger": "xlarge'a gec (fark marj icinde, kotu taraf kanitlanmadi)",
    "esdegerlik-kanitlanmadi": "medium'da kal (kanit gucsuz; veri buyutmeyi durdur)",
    "daha-kotu": "medium'da kal, veri buyutmeyi durdur (xlarge daha kotu)",
}


class StageError(RuntimeError):
    """100k asamasi icin kullanici hatasi."""


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise StageError("dosya yok: %s" % (path,)) from None
    except json.JSONDecodeError as exc:
        raise StageError("gecersiz JSON (%s): %s" % (path, exc)) from None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def load_sweep(path: Path) -> Dict[str, Any]:
    """``sweep.json`` okur ve ``rows`` listesini dogrular."""
    data = _read_json(path)
    if not isinstance(data, dict):
        raise StageError("sweep dosyasi nesne olmali: %s" % (path,))
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise StageError("sweep dosyasinda 'rows' bos: %s" % (path,))
    for row in rows:
        if not isinstance(row, dict):
            raise StageError("sweep satiri nesne olmali: %r" % (row,))
        if "seed" not in row or "valTop1" not in row:
            raise StageError("sweep satirinda seed/valTop1 yok: %r" % (row,))
    return data


def select_seed(sweep: Mapping[str, Any]) -> Dict[str, Any]:
    """En yuksek ``valTop1``'li satiri secer; esitlikte kucuk tohum kazanir.

    **ER alanlarina bakilmaz.** Secim yalnizca dogrulama isabetine dayanir;
    aksi halde ER'ye bakarak tohum secmek yanlilik uretir.
    """
    rows = list(sweep["rows"])
    if not rows:
        raise StageError("sweep satiri yok; tohum secilemez")
    best = max(rows, key=lambda r: (float(r["valTop1"]), -int(r["seed"])))
    return dict(best)


def _ci_contains(low: float, high: float, value: float) -> bool:
    return low <= value <= high


def build_report(
    ppg: Mapping[str, Any],
    baseline: Optional[Mapping[str, Any]],
    selection: Mapping[str, Any],
    *,
    margin: float = DEFAULT_MARGIN,
) -> Dict[str, Any]:
    """ppg sonucunu etiketler ve taban kosuyla karsilastirir."""
    if margin <= 0.0:
        raise StageError("marj pozitif olmali: %r" % (margin,))
    for key in ("ppg", "ppgCiLow", "ppgCiHigh"):
        if key not in ppg:
            raise StageError("ppg dosyasinda %r yok" % (key,))
    value = float(ppg["ppg"])
    low = float(ppg["ppgCiLow"])
    high = float(ppg["ppgCiHigh"])
    verdict = equivalence_verdict(value, low, high, margin)
    if verdict not in EQUIVALENCE_LABELS:
        raise StageError("beklenmeyen etiket: %r" % (verdict,))

    report: Dict[str, Any] = {
        "margin": margin,
        "verdict": verdict,
        "branch": BRANCHES[verdict],
        "ppg": value,
        "ppgCiLow": low,
        "ppgCiHigh": high,
        "ppgStdError": ppg.get("ppgStdError"),
        "games": ppg.get("games"),
        "pairs": ppg.get("pairs"),
        "path": ppg.get("path"),
        "gnubgPlies": ppg.get("gnubgPlies"),
        "model": ppg.get("model"),
        "seed": ppg.get("seed"),
        "unfinished": ppg.get("unfinished"),
        "meanPlies": ppg.get("meanPlies"),
        "selection": {
            "seed": int(selection["seed"]),
            "valTop1": float(selection["valTop1"]),
            "valValueMse": selection.get("valValueMse"),
            "params": selection.get("params"),
            "bestStep": selection.get("bestStep"),
        },
    }

    if baseline is not None:
        base_value = float(baseline["ppg"])
        base_low = float(baseline["ppgCiLow"])
        base_high = float(baseline["ppgCiHigh"])
        diff = value - base_value
        se_new = ppg.get("ppgStdError")
        se_base = baseline.get("ppgStdError")
        if se_new is not None and se_base is not None:
            diff_se = math.sqrt(float(se_new) ** 2 + float(se_base) ** 2)
        else:
            diff_se = None
        report["baseline"] = {
            "model": baseline.get("model"),
            "ppg": base_value,
            "ppgCiLow": base_low,
            "ppgCiHigh": base_high,
            "ppgStdError": se_base,
            "games": baseline.get("games"),
            "verdict": equivalence_verdict(base_value, base_low, base_high, margin),
        }
        report["difference"] = {
            "ppg": diff,
            "stdError": diff_se,
            "ciOverlaps": _ci_contains(base_low, base_high, value)
            or _ci_contains(low, high, base_value),
            "withinOneSe": None if diff_se is None else abs(diff) <= diff_se,
        }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    """Raporu Turkce Markdown olarak uretir."""
    lines: List[str] = []
    lines.append("# 100k veri ile xlarge — ppg sonucu")
    lines.append("")
    lines.append("Soru: **veri 100k'ya cikinca xlarge medium/large'i geciyor mu?**")
    lines.append("")
    lines.append("Model: `%s`" % (report.get("model"),))
    lines.append("")
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| Yol | `%s` |" % (report.get("path"),))
    lines.append("| gnubg ply | %s |" % (report.get("gnubgPlies"),))
    lines.append("| Oyun / cift | %s / %s |" % (report.get("games"), report.get("pairs")))
    lines.append("| ppg | **%+.4f** |" % (report["ppg"],))
    lines.append(
        "| ppg GA | [%+.4f; %+.4f] |" % (report["ppgCiLow"], report["ppgCiHigh"])
    )
    if report.get("ppgStdError") is not None:
        lines.append("| Standart hata | %.5f |" % (report["ppgStdError"],))
    lines.append("| Tamamlanmamis oyun | %s |" % (report.get("unfinished"),))
    if report.get("meanPlies") is not None:
        lines.append("| Ortalama ply | %.2f |" % (report["meanPlies"],))
    lines.append("")
    lines.append("## Karar (m = %.4f ppg)" % (report["margin"],))
    lines.append("")
    lines.append("`equivalence_verdict` -> **%s**" % (report["verdict"],))
    lines.append("")
    lines.append("Karar agaci dali: %s" % (report["branch"],))
    lines.append("")

    selection = report.get("selection") or {}
    if selection:
        lines.append("## Tohum secimi (ER'ye bakmadan)")
        lines.append("")
        lines.append("| Alan | Deger |")
        lines.append("|---|---|")
        lines.append("| Tohum | %s |" % (selection.get("seed"),))
        lines.append("| valTop1 | %.4f |" % (float(selection.get("valTop1", 0.0)),))
        if selection.get("valValueMse") is not None:
            lines.append("| valValueMse | %.6f |" % (selection["valValueMse"],))
        if selection.get("params") is not None:
            lines.append("| Parametre | %s |" % (selection["params"],))
        if selection.get("bestStep") is not None:
            lines.append("| En iyi adim | %s |" % (selection["bestStep"],))
        lines.append("")

    baseline = report.get("baseline")
    if baseline:
        lines.append("## Taban ile karsilastirma")
        lines.append("")
        lines.append("| Kosu | ppg | GA | Oyun | Etiket |")
        lines.append("|---|---|---|---|---|")
        lines.append(
            "| Taban (`%s`) | %+.4f | [%+.4f; %+.4f] | %s | %s |"
            % (
                baseline.get("model"),
                baseline["ppg"],
                baseline["ppgCiLow"],
                baseline["ppgCiHigh"],
                baseline.get("games"),
                baseline["verdict"],
            )
        )
        lines.append(
            "| 100k xlarge | %+.4f | [%+.4f; %+.4f] | %s | %s |"
            % (
                report["ppg"],
                report["ppgCiLow"],
                report["ppgCiHigh"],
                report.get("games"),
                report["verdict"],
            )
        )
        lines.append("")
        diff = report.get("difference") or {}
        if diff:
            lines.append("Fark: **%+.4f** ppg" % (diff["ppg"],))
            if diff.get("stdError") is not None:
                lines.append("Fark standart hatasi: %.5f" % (diff["stdError"],))
            if diff.get("withinOneSe") is not None:
                lines.append(
                    "Fark bir standart hatanin icinde mi: **%s**"
                    % ("evet" if diff["withinOneSe"] else "hayir",)
                )
            lines.append(
                "Guven araliklari ortusuyor mu: **%s**"
                % ("evet" if diff.get("ciOverlaps") else "hayir",)
            )
            lines.append("")

    lines.append("## Notlar")
    lines.append("")
    lines.append(
        "- Karar kurali kosudan **once** sabitlendi: tohum secimi ER'ye bakmadan, "
        "m = %.4f ppg, uc sonuc dali." % (report["margin"],)
    )
    lines.append(
        "- `esdeger` / `esdegerlik-kanitlanmadi` / `daha-kotu` etiketleri "
        "`H0: ppg_fark <= -m` testinin sonucudur; marj **para** oyunu icindir."
    )
    lines.append(
        "- ppg gnubg 2-ply hakeme karsi olculur; gnubg GPL lisanslidir, urun "
        "dagitimindan once lisans gozden gecirilmelidir."
    )
    lines.append("")
    return "\n".join(lines)


def check_dataset(path: Path, *, min_count: int = 100_000) -> Dict[str, Any]:
    """Birlesik veri dosyasinin egitime hazir oldugunu dogrular.

    ``x`` **aday** dizisidir; pozisyon sayisi ``offsets`` uzunlugunun bir
    eksigidir. Aday sayisini pozisyon sayisi sanmak, esik kontrolunu sessizce
    yanlis yapar.
    """
    import numpy as np

    if not path.exists():
        raise StageError("veri dosyasi yok: %s" % (path,))
    with np.load(path, allow_pickle=False) as data:
        keys = set(data.files)
        if "offsets" in keys:
            count = int(data["offsets"].shape[0]) - 1
        elif "y" in keys:
            count = int(data["y"].shape[0])
        else:
            count = 0
        candidates = int(data["x"].shape[0]) if "x" in keys else 0
        has_dist = "dist" in keys
        has_cand_equity = "cand_equity" in keys
        has_best = "best" in keys
    problems: List[str] = []
    if count < min_count:
        problems.append("pozisyon sayisi %d < %d" % (count, min_count))
    if not has_dist:
        problems.append("'dist' dizisi yok")
    if not has_cand_equity:
        problems.append("'cand_equity' dizisi yok")
    if not has_best:
        problems.append("'best' dizisi yok")
    if candidates < count:
        problems.append("aday sayisi %d < pozisyon sayisi %d" % (candidates, count))
    return {
        "path": str(path),
        "count": count,
        "candidates": candidates,
        "meanCandidates": (candidates / count) if count else 0.0,
        "hasDist": has_dist,
        "hasCandEquity": has_cand_equity,
        "hasBest": has_best,
        "ready": not problems,
        "problems": problems,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stage_100k",
        description="100k xlarge kosusunun tohum secimi, ppg karari ve raporu",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sel = sub.add_parser("select", help="valTop1 ile tohum sec (ER'ye bakmadan)")
    p_sel.add_argument("--sweep", required=True, help="<profil>/sweep.json yolu")
    p_sel.add_argument("--out", required=True, help="secim JSON'u")

    p_rep = sub.add_parser("report", help="ppg kararini uygula ve rapor yaz")
    p_rep.add_argument("--ppg", required=True, help="yeni ppg JSON'u")
    p_rep.add_argument("--baseline", default=None, help="taban ppg JSON'u")
    p_rep.add_argument("--selection", default=None, help="select ciktisi")
    p_rep.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    p_rep.add_argument("--out-json", required=True)
    p_rep.add_argument("--out-md", required=True)

    p_chk = sub.add_parser("check", help="birlesik veri dosyasini dogrula")
    p_chk.add_argument("--data", required=True)
    p_chk.add_argument("--min-count", type=int, default=100_000)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "select":
        sweep = load_sweep(Path(args.sweep))
        best = select_seed(sweep)
        payload = {
            "profile": sweep.get("profile"),
            "sweep": str(args.sweep),
            "seed": int(best["seed"]),
            "valTop1": float(best["valTop1"]),
            "valValueMse": best.get("valValueMse"),
            "params": best.get("params"),
            "bestStep": best.get("bestStep"),
            "candidates": [
                {"seed": int(r["seed"]), "valTop1": float(r["valTop1"])}
                for r in sweep["rows"]
            ],
        }
        _write_json(Path(args.out), payload)
        print(
            "secim: tohum %d (valTop1 %.4f) -> %s"
            % (payload["seed"], payload["valTop1"], args.out)
        )
        return 0

    if args.command == "report":
        ppg = _read_json(Path(args.ppg))
        baseline = _read_json(Path(args.baseline)) if args.baseline else None
        selection = _read_json(Path(args.selection)) if args.selection else {}
        report = build_report(ppg, baseline, selection, margin=args.margin)
        _write_json(Path(args.out_json), report)
        Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
        with Path(args.out_md).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_markdown(report))
        print("karar: %s -> %s" % (report["verdict"], report["branch"]))
        return 0

    if args.command == "check":
        result = check_dataset(Path(args.data), min_count=args.min_count)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ready"] else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
