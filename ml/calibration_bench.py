"""Faz 6 Bolum 13.2: deger kafasi kalibrasyonunu gnubg'ye karsi olcer.

`Backgammon.MatchBench dump-afterstates` ciktisini okur, her afterstate icin
gnubg'nin cubeless equity'sini alir ve Bolum 13.2'deki dort metrigi hesaplar:

* egim  (`gnubg ~ a * bizim + b` en kucuk kareler fitindeki `a`)
* korelasyon (Pearson)
* MAE
* standart sapma orani (bizim / gnubg)

gnubg'ye **metin protokolu** ile baglanir (`ml/gnubg_er.py::GnubgSession`), cunku
Python API'sinin `anBoard` yonelimi F6-28'de yanlis cikmisti; metin protokolu pip
sayilarini dogrulayarak tahtanin gercekten yuklendigini garanti eder.

Kullanim::

    python ml/calibration_bench.py [--source ...] [--out ...] [--json ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from gnubg_er import GnubgSession, _equity_at, find_gnubg  # noqa: E402

ARTIFACTS = os.path.join(HERE, "artifacts")
DEFAULT_SOURCE = os.path.join(ARTIFACTS, "stage_h_afterstates.json")
DEFAULT_REPORT = os.path.join(ARTIFACTS, "stage_h_calibration.md")
DEFAULT_JSON = os.path.join(ARTIFACTS, "stage_h_calibration.json")
#: Asama D (`ml/calibrate.py`) icin ham (bizim, gnubg) ciftleri.
DEFAULT_PAIRS = os.path.join(ARTIFACTS, "stage_h_calibration_pairs.json")

# Bolum 13.2 kapi araliklari.
SLOPE_RANGE = (0.85, 1.15)
CORRELATION_GATE = 0.75
MAE_GATE = 0.15
STD_RATIO_RANGE = (0.7, 1.4)

PLIES = 0


def pearson(pairs):
    n = len(pairs)
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    syy = sum((b - my) ** 2 for _, b in pairs)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return sxy / ((sxx ** 0.5) * (syy ** 0.5))


def _std(values):
    n = len(values)
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5


def _verdict(ok):
    return "gecti" if ok else "**KALDI**"


def _f(value, digits=4, sign=False):
    """Raporlarda Turkce ondalik virgulu kullanir."""
    text = ("%+.*f" if sign else "%.*f") % (digits, value)
    return text.replace(".", ",")


def measure_pairs(cases, session, plies=PLIES):
    """Her afterstate icin (bizim equity, gnubg equity) cifti uretir.

    gnubg afterstate'i **hamleyi yapanin** bakis acisindan degerlendirir: sira rakibe
    verilir (`-perspective`) ve isaret cevrilir. Bu, `ml/gnubg_er.py::measure_position`
    ile ayni sozlesmedir (F6-29).
    """
    pairs = []
    skipped = 0
    for case in cases:
        perspective = int(case.get("perspective", 1))
        board = case["board"]
        try:
            tables = session.eval_afterstates([board], -perspective)
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        if not tables or not tables[0]:
            skipped += 1
            continue
        pairs.append((float(case["ourValue"]), -_equity_at(tables[0], plies)))
    return pairs, skipped


def build_report(pairs, skipped, source_name, model_name):
    n = len(pairs)
    corr = pearson(pairs)
    mae = sum(abs(a - b) for a, b in pairs) / n
    bias = sum(a - b for a, b in pairs) / n
    ours = [a for a, _ in pairs]
    theirs = [b for _, b in pairs]
    our_std = _std(ours)
    their_std = _std(theirs)
    std_ratio = our_std / their_std if their_std > 0 else float("inf")

    mx = sum(ours) / n
    my = sum(theirs) / n
    sxx = sum((a - mx) ** 2 for a in ours)
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    slope = sxy / sxx if sxx > 0 else 1.0
    intercept = my - slope * mx
    cal_pairs = [(slope * x + intercept, y) for x, y in pairs]
    cal_mae = sum(abs(x - y) for x, y in cal_pairs) / n

    slope_ok = SLOPE_RANGE[0] <= slope <= SLOPE_RANGE[1]
    corr_ok = corr is not None and corr >= CORRELATION_GATE
    mae_ok = mae <= MAE_GATE
    std_ok = STD_RATIO_RANGE[0] <= std_ratio <= STD_RATIO_RANGE[1]

    lines = []
    lines.append("# Faz 6 Bolum 13.2 - Deger kafasi kalibrasyonu (olculmus)\n")
    lines.append("Kaynak: `%s` (rastgele self-play afterstate'leri)." % source_name)
    lines.append("Model: `%s`." % model_name)
    lines.append("gnubg: metin protokolu, `eval` 0-ply, cubeless (`ml/gnubg_er.py::GnubgSession`).")
    lines.append("Perspektif: her afterstate hamleyi yapanin bakis acisindan (F6-29 sozlesmesi).\n")
    lines.append("| Metrik | Faz 5 | Faz 6 (olculen) | Hedef | Kapi |")
    lines.append("|---|---|---|---|---|")
    lines.append("| Egim | 0,0874 | **%s** | 0,85 - 1,15 | %s |" % (_f(slope), _verdict(slope_ok)))
    lines.append("| Korelasyon | +0,2431 | **%s** | >= 0,75 | %s |" % (_f(corr, sign=True), _verdict(corr_ok)))
    lines.append("| MAE | 0,8014 | **%s** | <= 0,15 | %s |" % (_f(mae), _verdict(mae_ok)))
    lines.append("| Std orani | 2,78 | **%s** | 0,7 - 1,4 | %s |" % (_f(std_ratio), _verdict(std_ok)))
    lines.append("")
    lines.append("## Destekleyici olcumler\n")
    lines.append("| Metrik | Deger |")
    lines.append("|---|---|")
    lines.append("| Karsilastirilan afterstate | %d |" % n)
    lines.append("| Atlanan | %d |" % skipped)
    lines.append("| Sistematik sapma (bizim - gnubg) | %s |" % _f(bias, sign=True))
    lines.append("| Bizim equity araligi | %s .. %s |" % (_f(min(ours), sign=True), _f(max(ours), sign=True)))
    lines.append("| gnubg equity araligi | %s .. %s |" % (_f(min(theirs), sign=True), _f(max(theirs), sign=True)))
    lines.append("| Bizim standart sapma | %s |" % _f(our_std))
    lines.append("| gnubg standart sapma | %s |" % _f(their_std))
    lines.append("| Dogrusal fit `gnubg ~ a*bizim + b` | a = %s, b = %s |" % (_f(slope), _f(intercept, sign=True)))
    lines.append("| Kalibrasyon sonrasi MAE | %s |" % _f(cal_mae))
    lines.append("")

    failed = []
    if not slope_ok:
        failed.append("egim")
    if not corr_ok:
        failed.append("korelasyon")
    if not mae_ok:
        failed.append("MAE")
    if not std_ok:
        failed.append("std orani")

    lines.append("## Yorum\n")
    if not failed:
        lines.append("Dort metrik de Bolum 13.2 kapi araliginda.")
    else:
        lines.append("Kapi disinda kalan metrikler: **%s**." % ", ".join(failed))
        lines.append("")
        lines.append(
            "Faz 5'e gore degisim: egim 0,0874 -> %s, korelasyon +0,2431 -> %s,"
            % (_f(slope), _f(corr, sign=True))
        )
        lines.append("MAE 0,8014 -> %s, std orani 2,78 -> %s." % (_f(mae), _f(std_ratio)))
        lines.append("")
        lines.append(
            "**Not (F6-31).** Faz 5'in kalibrasyon olcumu (`ml/afterstate_bench.py`) tahtayi"
        )
        lines.append(
            "gnubg Python API'sine **aynalanmis** veriyordu: `row0[i] = board[1+i]` ve"
        )
        lines.append("`row1[i] = -board[24-i]`, dogrusu `row0[i] = board[24-i]` ve")
        lines.append("`row1[i] = -board[1+i]`. Aynali tahta baska bir pozisyondur, bu yuzden")
        lines.append("Faz 5'in 0,0874 egimi ve +0,2431 korelasyonu **olcum hatasiydi**,")
        lines.append("modelin gercek kalibrasyonu degildi. Ayrintilar: `ASSUMPTIONS.md` F6-31.")
    lines.append("")

    payload = {
        "count": n,
        "skipped": skipped,
        "slope": slope,
        "intercept": intercept,
        "correlation": corr,
        "mae": mae,
        "bias": bias,
        "our_std": our_std,
        "gnubg_std": their_std,
        "std_ratio": std_ratio,
        "calibrated_mae": cal_mae,
        "gates": {
            "slope": slope_ok,
            "correlation": corr_ok,
            "mae": mae_ok,
            "std_ratio": std_ok,
        },
    }
    return "\n".join(lines) + "\n", payload


def build_parser():
    ap = argparse.ArgumentParser(description="Faz 6 Bolum 13.2 kalibrasyon olcumu")
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--out", default=DEFAULT_REPORT)
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--pairs", default=DEFAULT_PAIRS)
    ap.add_argument("--gnubg", default=None)
    ap.add_argument("--plies", type=int, default=PLIES)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    with open(args.source, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    exe = find_gnubg(args.gnubg)
    if exe is None:
        raise SystemExit("gnubg-cli bulunamadi; --gnubg veya GNUBG_CLI ayarlayin")
    session = GnubgSession(exe, plies=args.plies)
    pairs, skipped = measure_pairs(cases, session, args.plies)
    if not pairs:
        raise SystemExit("karsilastirilacak afterstate yok")

    report, payload = build_report(
        pairs,
        skipped,
        os.path.basename(args.source),
        "ml/runs/stage_d_l2/onnx/model_v30.onnx",
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    if args.pairs:
        # Asama D kalibrasyon onarimi bu ham ciftleri kullanir (Kural 10 bolmesi
        # orada yapilir; burada bolme YOK).
        with open(args.pairs, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "count": len(pairs),
                    "source": os.path.basename(args.source),
                    "pairs": [[float(a), float(b)] for a, b in pairs],
                },
                f,
                indent=2,
            )

    print(
        "kalibrasyon: %d afterstate, atlanan %d | egim %s | korelasyon %s | MAE %s | std %s"
        % (
            payload["count"],
            skipped,
            _f(payload["slope"]),
            _f(payload["correlation"], sign=True),
            _f(payload["mae"]),
            _f(payload["std_ratio"]),
        )
    )
    print("rapor:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())