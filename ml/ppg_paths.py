"""Oyun yolu x model ppg matrisi - K5 (F7-106).

K5 "politika-argmax **ve** deger-0-ply oyununun ppg'sini olc" diyor. R-F
(F7-104) yalnizca ``search1`` yolunu olctu; ``policy`` ve ``value`` yollari
ER'de vardi (``er_paths.PLAY_PATHS``) ama ppg'de yoktu. Bu modul ayni
modelleri uc yol uzerinde yan yana koyar.

Neden onemli: gnubg 0-ply da **after-state degerlendirmesiyle** oynar, yani
``value`` yolu gnubg 0-ply ile elma-elmaya kiyaslanabilen tek yoldur.
``search1`` bir ply arar, ``policy`` ise deger kafasini hic kullanmaz; uc
yolun ppg'si, kafalarin urun katkisini ayristirir.

Fark hesaplari ``ppg_models.pair_difference`` ile yapilir; GA yorumu ve
``CAVEAT`` oradan gelir (iki ornekli, ayni zar tohumu).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ppg_models as pm  # noqa: E402

PPG_PATHS_PATH = "ml/artifacts/ppg_paths.json"
PPG_PATHS_MD_PATH = "ml/artifacts/ppg_paths.md"

#: Sira onemli: tabloda bu sirayla cikar (zayiftan gucluye).
PATH_ORDER = ("policy", "value", "search1")

PATH_LABELS = {
    "policy": "politika-argmax",
    "value": "deger-0-ply",
    "search1": "search1 (deger 1-ply)",
}

#: Urun yolu: ``search1`` (F7-104). Yol farklari buna karsi verilir.
PRODUCT_PATH = "search1"


class PpgPathsError(RuntimeError):
    """Yol matrisi kurulamadi."""


def model_label(model_path: str) -> str:
    """``ml/runs/stage_d_l2/onnx/model_v30.onnx`` -> ``stage_d_l2/model_v30``."""
    p = Path(model_path)
    parent = p.parent
    if parent.name == "onnx":
        parent = parent.parent
    return "%s/%s" % (parent.name, p.stem) if parent.name else p.stem


def load_match(path: str | Path) -> pm.ModelPpg:
    """``vs_gnubg.py`` ciktisini okur; etiket model ve yoldan turetilir."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise PpgPathsError("mac dosyasi yok: %s" % p)
    data = json.loads(p.read_text(encoding="utf-8"))
    our_path = str(data.get("path", ""))
    if our_path not in PATH_ORDER:
        raise PpgPathsError("bilinmeyen yol: %r" % our_path)
    label = "%s [%s]" % (model_label(str(data.get("model", ""))), our_path)
    return pm.load_match(p, label)


def build_report(
    matches: Sequence[pm.ModelPpg], baseline: str | None = None
) -> dict[str, Any]:
    """Yol x model matrisi ve iki yonlu farklar."""
    if not matches:
        raise PpgPathsError("en az bir mac gerekli")
    models: list[str] = []
    cells: dict[str, dict[str, pm.ModelPpg]] = {}
    for m in matches:
        label = model_label(m.model)
        if label not in cells:
            cells[label] = {}
            models.append(label)
        if m.path in cells[label]:
            raise PpgPathsError("ayni model+yol iki kez: %s [%s]" % (label, m.path))
        cells[label][m.path] = m
    if baseline is None:
        baseline = models[0]
    if baseline not in cells:
        raise PpgPathsError("bilinmeyen taban: %s" % baseline)

    path_diffs: list[dict[str, Any]] = []
    for label in models:
        row = cells[label]
        if PRODUCT_PATH not in row:
            continue
        for p in PATH_ORDER:
            if p == PRODUCT_PATH or p not in row:
                continue
            path_diffs.append(pm.pair_difference(row[p], row[PRODUCT_PATH]).to_dict())

    model_diffs: list[dict[str, Any]] = []
    for p in PATH_ORDER:
        if p not in cells[baseline]:
            continue
        for label in models:
            if label == baseline or p not in cells[label]:
                continue
            model_diffs.append(
                pm.pair_difference(cells[label][p], cells[baseline][p]).to_dict()
            )

    return {
        "version": 1,
        "baseline": baseline,
        "caveat": pm.CAVEAT,
        "pathOrder": list(PATH_ORDER),
        "pathLabels": dict(PATH_LABELS),
        "productPath": PRODUCT_PATH,
        "models": models,
        "cells": {
            label: {p: m.to_dict() for p, m in row.items()}
            for label, row in cells.items()
        },
        "pathDiffs": path_diffs,
        "modelDiffs": model_diffs,
    }


def _fmt(value: float, digits: int = 4) -> str:
    return f"{value:+.{digits}f}"


def build_markdown(report: dict[str, Any]) -> str:
    """K5 yol matrisi raporu."""
    order = report["pathOrder"]
    labels = report["pathLabels"]
    models = report["models"]
    cells = report["cells"]
    lines = [
        "# Oyun yolu x model ppg matrisi (K5)",
        "",
        "Kupsuz para oyunu, eslestirilmis zar + renk takasi, gnubg 0-ply, "
        "2000 oyun (1000 cift), tohum 2026.",
        "",
        "| Model | %s |" % " | ".join(labels[p] for p in order),
        "|---|%s" % ("---|" * len(order)),
    ]
    for label in models:
        row = cells[label]
        parts = []
        for p in order:
            cell = row.get(p)
            if cell is None:
                parts.append("-")
            else:
                parts.append(
                    "**%s** [%s; %s]"
                    % (_fmt(cell["ppg"]), _fmt(cell["ppgCiLow"]), _fmt(cell["ppgCiHigh"]))
                )
        lines.append("| `%s` | %s |" % (label, " | ".join(parts)))
    lines.append("")
    lines.append(
        "`value` yolu gnubg 0-ply ile **elma-elmaya** kiyaslanabilen tek yoldur: "
        "ikisi de after-state degerlendirmesiyle oynar. `search1` bir ply arar, "
        "`policy` deger kafasini hic kullanmaz."
    )
    lines.append("")

    if report["pathDiffs"]:
        lines.append("## Yol farklari (ayni model, `%s` referans)" % report["productPath"])
        lines.append("")
        lines.append("| Model | Yol | Fark | 95% GA | z | Anlamli |")
        lines.append("|---|---|---|---|---|---|")
        for d in report["pathDiffs"]:
            lines.append(
                "| `%s` | %s | %s | [%s; %s] | %s | %s |"
                % (
                    d["a"].split(" [")[0],
                    labels.get(d["a"].split("[")[-1].rstrip("]"), d["a"]),
                    _fmt(d["diff"]),
                    _fmt(d["ciLow"]),
                    _fmt(d["ciHigh"]),
                    _fmt(d["z"], 2),
                    "evet" if d["significant"] else "hayir",
                )
            )
        lines.append("")
        lines.append("Negatif fark = o yol `%s`'ten daha kotu." % report["productPath"])
        lines.append("")

    if report["modelDiffs"]:
        lines.append("## Model farklari (ayni yol, `%s` referans)" % report["baseline"])
        lines.append("")
        lines.append("| Yol | Model | Fark | 95% GA | z | Anlamli |")
        lines.append("|---|---|---|---|---|---|")
        for d in report["modelDiffs"]:
            lines.append(
                "| %s | `%s` | %s | [%s; %s] | %s | %s |"
                % (
                    labels.get(d["a"].split("[")[-1].rstrip("]"), d["a"]),
                    d["a"].split(" [")[0],
                    _fmt(d["diff"]),
                    _fmt(d["ciLow"]),
                    _fmt(d["ciHigh"]),
                    _fmt(d["z"], 2),
                    "evet" if d["significant"] else "hayir",
                )
            )
        lines.append("")

    lines.append("## Uyari")
    lines.append("")
    lines.append(report["caveat"])
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Oyun yolu x model ppg matrisi (K5)")
    p.add_argument(
        "--match",
        action="append",
        default=[],
        metavar="JSON",
        help="vs_gnubg.py ciktisi; model ve yol dosyadan okunur",
    )
    p.add_argument("--baseline", default=None, help="Model farklarinin referansi")
    p.add_argument("--out", default=PPG_PATHS_PATH)
    p.add_argument("--markdown", default=PPG_PATHS_MD_PATH)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.match:
        raise SystemExit("en az bir --match gerekli")
    matches = [load_match(m) for m in args.match]
    report = build_report(matches, baseline=args.baseline)
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    if not md.is_absolute():
        md = REPO_ROOT / md
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")
    print(build_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
