"""F8-04: korpus v2 (yaris cesitliligi + etiket derinligi) sonuc analizi.

Onceden sabitlenmis karar kuralini uygular (ASSUMPTIONS.md F8-04):

    Kabul: ortalama contact ER < 0,0070 (temel) VE yaris ER < 0,0122 (temel)

Girdi: ``ml/artifacts/model_benchmarks.json`` (append-only panel kayitlari).
Cikti: konsol tablosu + ``ml/artifacts/stage_sl_v2_report.md``.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
REPO = ML_DIR.parent
BENCH = ML_DIR / "artifacts" / "model_benchmarks.json"
OUT_MD = ML_DIR / "artifacts" / "stage_sl_v2_report.md"

BASELINE_PATH = "ml/runs/capacity_rd/large/seed0/model.onnx"
CORPORA = ("mp100_2ply", "d12k_3ply", "d12k_2ply")
SEEDS = (0, 1, 2)


def load_records() -> list[dict]:
    data = json.loads(BENCH.read_text(encoding="utf-8"))
    return data["records"]


def latest_by_path(records: list[dict]) -> dict[str, dict]:
    """Ayni model icin en son olcum gecerlidir (append-only defter)."""
    out: dict[str, dict] = {}
    for r in records:
        out[r["model"]["path"]] = r
    return out


def metrics(rec: dict) -> tuple[float, float, float, float]:
    c = rec["sets"]["contact"]
    ra = rec["sets"]["race"]
    return c["mean"], c["exactMatchRate"], ra["mean"], ra["exactMatchRate"]


def main() -> int:
    by_path = latest_by_path(load_records())
    if BASELINE_PATH not in by_path:
        print("[hata] temel model panelde yok: " + BASELINE_PATH, file=sys.stderr)
        return 2
    b_c, b_cm, b_r, b_rm = metrics(by_path[BASELINE_PATH])

    rows: list[dict] = []
    for tag in CORPORA:
        per_seed = []
        for seed in SEEDS:
            path = "ml/runs/corpus_sl_v2/%s/seed%d/model.onnx" % (tag, seed)
            if path not in by_path:
                continue
            c, cm, r, rm = metrics(by_path[path])
            per_seed.append({"seed": seed, "cER": c, "cM": cm, "rER": r, "rM": rm})
        if not per_seed:
            rows.append({"tag": tag, "seeds": [], "n": 0})
            continue
        rows.append(
            {
                "tag": tag,
                "seeds": per_seed,
                "n": len(per_seed),
                "cER": statistics.fmean(p["cER"] for p in per_seed),
                "cM": statistics.fmean(p["cM"] for p in per_seed),
                "rER": statistics.fmean(p["rER"] for p in per_seed),
                "rM": statistics.fmean(p["rM"] for p in per_seed),
            }
        )

    lines: list[str] = []
    lines.append("# F8-04 — korpus v2: yarış çeşitliliği ve etiket derinliği\n")
    lines.append("**Tarih:** 2026-11-28. **Durum:** ölçüm raporu.\n")
    lines.append("## 1. Karar kuralı (koşudan önce sabit)\n")
    lines.append(
        "Kabul: ortalama contact ER **< %.6f** (temel) **ve** yarış ER "
        "**< %.6f** (temel). Aksi hâlde Adım B kapalı kalır ve `DEFAULT_MODEL` "
        "değişmez.\n" % (b_c, b_r)
    )
    lines.append("## 2. Ölçümler (A2 paneli, 229 vaka, gnubg 2-ply)\n")
    lines.append("| model | tohum | contact ER | contact eşleşme | yarış ER | yarış eşleşme |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        "| **temel** `capacity_rd/large/seed0` | — | **%.6f** | %.4f | **%.6f** | %.4f |"
        % (b_c, b_cm, b_r, b_rm)
    )
    for row in rows:
        for p in row["seeds"]:
            lines.append(
                "| `%s` | %d | %.6f | %.4f | %.6f | %.4f |"
                % (row["tag"], p["seed"], p["cER"], p["cM"], p["rER"], p["rM"])
            )
    lines.append("")
    lines.append("### Ortalamalar\n")
    lines.append("| korpus | n | contact ER | contact eşleşme | yarış ER | yarış eşleşme | karar |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        if not row["n"]:
            lines.append("| `%s` | 0 | — | — | — | — | ölçüm yok |" % row["tag"])
            continue
        ok = row["cER"] < b_c and row["rER"] < b_r
        lines.append(
            "| `%s` | %d | %.6f | %.4f | %.6f | %.4f | %s |"
            % (
                row["tag"],
                row["n"],
                row["cER"],
                row["cM"],
                row["rER"],
                row["rM"],
                "**KABUL**" if ok else "ret",
            )
        )
    lines.append("")

    accepted = [r for r in rows if r["n"] and r["cER"] < b_c and r["rER"] < b_r]
    lines.append("## 3. Sonuç\n")
    if accepted:
        best = min(accepted, key=lambda r: r["cER"])
        lines.append(
            "**Kabul edilen korpus: `%s`** (contact ER %.6f, yarış ER %.6f). "
            "Adım B bu korpusla ilerler.\n" % (best["tag"], best["cER"], best["rER"])
        )
    else:
        lines.append(
            "**Hiçbir korpus kabul eşiğini geçmedi.** Adım B (gnubg korpustan SL) "
            "kapatılır; `DEFAULT_MODEL` = `%s` olarak kalır.\n" % BASELINE_PATH
        )

    print("\n".join(lines))
    if not any(r["n"] for r in rows):
        # Olcum yokken rapor yazmak yaniltici bir artefakt uretir.
        print("\n[bilgi] hicbir korpus olculmedi; rapor yazilmadi.")
        return 1
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nyazildi: " + str(OUT_MD))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
