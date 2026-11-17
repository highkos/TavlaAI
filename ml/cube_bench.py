"""Faz 6 §10.5: kup karari uyumu olcumu (Aşama F, Test 84).

Faz 5'in `match_bench.py`'si tek bir "bizim" dosyasi okuyordu. Bu betik iki varyanti
karsilastirir:

    stage_f_cube_ours.json         -> DiceAveraged = true  (Faz 6 varsayilani)
    stage_f_cube_ours_single.json  -> DiceAveraged = false (Faz 5 davranisi)

Kullanim (gnubg'nin kendi Python yorumlayicisi ile calistirilmalidir):

    gnubg-cli.exe -p "F:/.../ml/cube_bench.py"

Ciktilar:
    ml/artifacts/stage_f_cube_gnubg.json
    ml/artifacts/stage_f_cube.md
"""

import json
import os

import gnubg

DEFAULT_ROOT = r"F:\Projects\VijualStudioski\TavlaAI_Project"


def _repo_root():
    """gnubg'nin Python modu dosyayi `exec` ile calistirir; `__file__` tanimli olmaz."""
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    env = os.environ.get("TAVLA_ROOT")
    if env:
        return env
    for candidate in (os.getcwd(), DEFAULT_ROOT):
        if os.path.isdir(os.path.join(candidate, "ml", "artifacts")):
            return candidate
    raise RuntimeError("Depo koku bulunamadi; TAVLA_ROOT ortam degiskenini ayarlayin.")


HERE = os.path.join(_repo_root(), "ml")
ARTIFACTS = os.path.join(HERE, "artifacts")

POSITIONS = os.path.join(ARTIFACTS, "stage_b_positions.json")
VARIANTS = (
    ("diceAveraged", os.path.join(ARTIFACTS, "stage_f_cube_ours.json")),
    ("singleRecord", os.path.join(ARTIFACTS, "stage_f_cube_ours_single.json")),
)
GNUBG_OUT = os.path.join(ARTIFACTS, "stage_f_cube_gnubg.json")
REPORT = os.path.join(ARTIFACTS, "stage_f_cube.md")

# Faz 5 §9.2 taban degerleri (karsilastirma icin).
BASELINE = {
    "doubleAgreement": 0.5227,
    "takeAgreement": 0.6136,
    "bothAgreement": 0.4697,
    "equityMeanAbsDiff": 1.2063,
}


def to_gnubg_board(case):
    """Bizim board[26] (+Beyaz/-Siyah, 0 = Beyaz bar, 25 = Siyah bar) -> gnubg tahtasi.

    Esleme (F6-22): bizim konvansiyonda ``DistanceToOff(p, +1) = 25 - p``, yani Beyaz'in
    1-noktasi bizim 24, Siyah'in 1-noktasi bizim 1. gnubg'de ``anBoard[0][i]`` oyuncu 0'in
    ``i+1`` noktasidir. Bu yuzden:

        gnubg row0[i] = board[24 - i]      (i = 0..23)
        gnubg row1[i] = -board[1 + i]      (i = 0..23)

    Bar indeksleri (24) dogrudan tasinir.
    """
    board = case["board"]
    row0 = [max(board[24 - i], 0) for i in range(24)] + [max(board[0], 0)]
    row1 = [max(-board[1 + i], 0) for i in range(24)] + [max(-board[25], 0)]
    return (tuple(row0), tuple(row1))


def parse_recommendation(text):
    """gnubg oneri metnini (double, take) ikilisine cevirir."""
    t = text.lower()
    if "beaver" in t:
        return (False, True)
    if "too good" in t:
        return (False, False)
    if t.startswith("no double") or t.startswith("no redouble"):
        double = False
    elif t.startswith("double") or t.startswith("redouble"):
        double = True
    else:
        double = None
    take = "take" in t and "pass" not in t
    return (double, take)


def gnubg_owner(our_owner, cube):
    """Bizim cubeOwner (0 = ortada, +1 = Beyaz, -1 = Siyah) -> gnubg (-1 = ortada, 0, 1)."""
    if cube <= 1 or our_owner == 0:
        return -1
    return 0 if our_owner > 0 else 1


def gnubg_view(case):
    """Pozisyonu gnubg Python API'sinin gercekten kullandigi bicime cevirir (F6-23).

    ``gnubg.evaluate`` ve ``gnubg.cfevaluate``, ``cubeinfo`` icindeki ``move`` alanini
    **yok sayar**: her zaman ``anBoard[1]``i zar atan oyuncu kabul eder ve sonucu onun
    perspektifinden dondurur. Olculdu (gnubg 1.08.003): ayni tahta icin ``move`` 0 ve 1
    birebir ayni ciktiyi verir; ``anBoard`` satirlari yer degistirildiginde ise sonuc
    diger oyuncunun perspektifine doner.

    Bu yuzden zar atan oyuncuyu her zaman ``anBoard[1]``e yerlestiririz. Aksi halde
    gnubg'nin equity'si zar atanla degil, sabit bir oyuncuyla karsilastirilir ve
    korelasyon anlamsiz cikar (olculdu: 0,11; isaret duzeltmesiyle -0,72).

    Doner: ``(board, score, cube_owner)``; ucu de gnubg oyuncu numaralandirmasinda
    (0 = zar atmayan, 1 = zar atan).
    """
    row0, row1 = to_gnubg_board(case)
    owner = gnubg_owner(case.get("cubeOwner", 0), case.get("cubeValue", 1))
    if case["turn"] == 1:
        # gnubg oyuncu 0 = Siyah, oyuncu 1 = Beyaz (zar atan).
        score = (case.get("blackScore", 0), case.get("whiteScore", 0))
        if owner >= 0:
            owner = 1 - owner
        return (row1, row0), score, owner
    score = (case.get("whiteScore", 0), case.get("blackScore", 0))
    return (row0, row1), score, owner


def is_safe(case):
    """gnubg'yi cokertmeyecek pozisyonlari secer."""
    board = case["board"]
    white_on = sum(v for v in board if v > 0)
    black_on = sum(-v for v in board if v < 0)
    if white_on == 0 or black_on == 0:
        return False
    matchto = case.get("matchLength", 0)
    if matchto > 0:
        if case.get("whiteScore", 0) >= matchto or case.get("blackScore", 0) >= matchto:
            return False
        if case.get("cubeValue", 1) > matchto:
            return False
    return True


def gnubg_decision(case, plies):
    board, score, owner = gnubg_view(case)
    cube = case.get("cubeValue", 1)
    matchto = case.get("matchLength", 0)
    crawford = 1 if case.get("isCrawfordGame") else 0

    # ``move`` yok sayilir (F6-23); zar atan oyuncu her zaman gnubg oyuncu 1'dir.
    ci = gnubg.cubeinfo(cube, owner, 1, matchto, score, crawford, 0)
    ec = gnubg.evalcontext(plies, 1, 1, 0, 0.0)
    optimal, nodouble, take, drop, code, text = gnubg.cfevaluate(board, ci, ec)
    cubeless = gnubg.evaluate(board, ci, ec)[5]
    double, take_flag = parse_recommendation(text)
    return {
        "optimal": float(optimal),
        "nodouble": float(nodouble),
        "take": float(take),
        "drop": float(drop),
        "code": int(code),
        "text": text,
        "shouldDouble": double,
        "shouldTake": take_flag,
        "cubelessEquity": float(cubeless),
    }


def pearson(pairs):
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    syy = sum((b - my) ** 2 for _, b in pairs)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return sxy / ((sxx ** 0.5) * (syy ** 0.5))


def summarise(rows, key, variant):
    valid = [r for r in rows
             if not r.get("skipped") and "error" not in r[key]
             and r[key]["shouldDouble"] is not None
             and r[variant].get("evaluated", True)]
    n = len(valid)
    if n == 0:
        return None

    both_double = sum(1 for r in valid if r[key]["shouldDouble"] and r[variant]["shouldDouble"])
    both_nodouble = sum(1 for r in valid if not r[key]["shouldDouble"] and not r[variant]["shouldDouble"])
    ours_only = sum(1 for r in valid if r[variant]["shouldDouble"] and not r[key]["shouldDouble"])
    gnubg_only = sum(1 for r in valid if r[key]["shouldDouble"] and not r[variant]["shouldDouble"])

    both_take = sum(1 for r in valid if r[key]["shouldTake"] and r[variant]["shouldTake"])
    both_pass = sum(1 for r in valid if not r[key]["shouldTake"] and not r[variant]["shouldTake"])
    ours_take_only = sum(1 for r in valid if r[variant]["shouldTake"] and not r[key]["shouldTake"])
    gnubg_take_only = sum(1 for r in valid if r[key]["shouldTake"] and not r[variant]["shouldTake"])

    pairs = [(r[variant]["equityNoDouble"], r[key]["cubelessEquity"]) for r in valid
             if "cubelessEquity" in r[key]]
    corr = pearson(pairs)
    mean_abs = (sum(abs(a - b) for a, b in pairs) / len(pairs)) if pairs else None

    # Hata buyuklugu: |bizim E - gnubg E| dagilimi (karisiklik matrisine ek).
    errors = sorted(abs(a - b) for a, b in pairs) if pairs else []
    p90 = errors[int(0.9 * (len(errors) - 1))] if errors else None

    return {
        "n": n,
        "doubleAgreement": (both_double + both_nodouble) / n,
        "takeAgreement": (both_take + both_pass) / n,
        "bothAgreement": sum(
            1 for r in valid
            if r[key]["shouldDouble"] == r[variant]["shouldDouble"]
            and r[key]["shouldTake"] == r[variant]["shouldTake"]
        ) / n,
        "equityCorrelation": corr,
        "equityMeanAbsDiff": mean_abs,
        "equityP90AbsDiff": p90,
        "doubleMatrix": {
            "bothDouble": both_double,
            "bothNoDouble": both_nodouble,
            "oursOnlyDouble": ours_only,
            "gnubgOnlyDouble": gnubg_only,
        },
        "takeMatrix": {
            "bothTake": both_take,
            "bothPass": both_pass,
            "oursOnlyTake": ours_take_only,
            "gnubgOnlyTake": gnubg_take_only,
        },
    }


def main():
    with open(POSITIONS, "r", encoding="utf-8") as f:
        positions = json.load(f)

    ours = {}
    for name, path in VARIANTS:
        if not os.path.exists(path):
            raise RuntimeError("Varyant dosyasi yok: " + path)
        with open(path, "r", encoding="utf-8") as f:
            ours[name] = {c["name"]: c for c in json.load(f)["cases"]}

    rows = []
    for case in positions["cases"]:
        name = case["name"]
        entry = {"name": name, "matchLength": case.get("matchLength", 0)}
        if not is_safe(case):
            entry["skipped"] = True
            rows.append(entry)
            continue
        for plies in (0, 2):
            try:
                entry["gnubg%d" % plies] = gnubg_decision(case, plies)
            except Exception as exc:  # noqa: BLE001
                entry["gnubg%d" % plies] = {"error": str(exc)}
        for variant, _ in VARIANTS:
            if name in ours[variant]:
                entry[variant] = ours[variant][name]
        rows.append(entry)

    with open(GNUBG_OUT, "w", encoding="utf-8") as f:
        json.dump({"cases": rows}, f, indent=2)

    compared = sum(
        1
        for r in rows
        if not r.get("skipped")
        and "error" not in r.get("gnubg0", {})
        and r.get("gnubg0", {}).get("shouldDouble") is not None
        and r.get("diceAveraged", {}).get("evaluated", True)
    )

    lines = []
    lines.append("# Faz 6 §10.5 — Kup karari uyumu (Aşama F, Test 84)\n")
    lines.append("Pozisyon kaynagi: `ml/artifacts/stage_b_positions.json` (%d pozisyon, %d karsilastirilabilir)."
                 % (len(rows), compared))
    lines.append("gnubg karari: `cfevaluate` (cubeful), `deterministic=1`.")
    lines.append("Bizim karar: `EquityCubeAdvisor` + Aşama D modeli (6 cikti).")
    lines.append("")
    lines.append("Iki varyant:")
    lines.append("")
    lines.append("- **diceAveraged** — `CubeAdvisorOptions.DiceAveraged = true` (Faz 6 varsayilani, §10.2).")
    lines.append("- **singleRecord** — `DiceAveraged = false` (Faz 5 davranisi).")
    lines.append("")
    lines.append("## Olcum hatti duzeltmeleri (F6-28, F6-29, F6-30)")
    lines.append("")
    lines.append("Bu tablodaki sayilar uc olcum/sözlesme hatasi duzeltildikten sonra alinmistir:")
    lines.append("")
    lines.append("- **F6-28** — gnubg'nin Python API'si `cubeinfo['move']` alanini **yok sayar** ve her")
    lines.append("  zaman `anBoard[1]`'i sirada kabul eder. `gnubg_view()` hamleyi yapan oyuncuyu")
    lines.append("  fiziksel olarak `anBoard[1]`'e tasir. Duzeltme oncesi korelasyon 0,11 idi.")
    lines.append("- **F6-29** — `EquityCubeAdvisor.EvaluateDiceAveraged` afterstate'leri `-perspective`")
    lines.append("  ile degerlendirip isareti ceviriyordu. Ag afterstate'i **hamleyi yapanin**")
    lines.append("  perspektifinden ogrenir (`ShardWriter`, `ml/gnubg_er.py`, `BackgammonSearch`),")
    lines.append("  bu yuzden isaret cevrimi kaldirildi.")
    lines.append("- **F6-30** — mac oyununda ciftleme karsilastirmasi `max(doubleTake, doublePass)`")
    lines.append("  kullaniyordu; bu, rakibin isbirligi yaptigini varsayar. Rakip kendi equity'sini")
    lines.append("  maksimize ettigi icin dogru deger `min(doubleTake, doublePass)`'tir. Duzeltme")
    lines.append("  ciftleme uyumunu 73,13% -> 84,96%'ya tasidi (32 yanlis ciftlemenin 19'u dondu).")
    lines.append("")

    summary = {}
    for plies in (0, 2):
        key = "gnubg%d" % plies
        lines.append("## gnubg %d-ply\n" % plies)
        lines.append("| Metrik | singleRecord (Faz 5) | diceAveraged (Faz 6) | Faz 5 taban |")
        lines.append("|---|---|---|---|")
        s_single = summarise(rows, key, "singleRecord")
        s_dice = summarise(rows, key, "diceAveraged")
        summary[key] = {"singleRecord": s_single, "diceAveraged": s_dice}
        if s_single is None or s_dice is None:
            lines.append("| (yetersiz veri) | | | |")
            lines.append("")
            continue

        def pct(v):
            return "%.2f%%" % (100.0 * v)

        def num(v):
            return "—" if v is None else "%.4f" % v

        lines.append("| Karsilastirilan pozisyon | %d | %d | 132 |"
                     % (s_single["n"], s_dice["n"]))
        lines.append("| Ciftleme uyumu | %s | %s | %s |"
                     % (pct(s_single["doubleAgreement"]), pct(s_dice["doubleAgreement"]),
                        pct(BASELINE["doubleAgreement"])))
        lines.append("| Kabul/ret uyumu | %s | %s | %s |"
                     % (pct(s_single["takeAgreement"]), pct(s_dice["takeAgreement"]),
                        pct(BASELINE["takeAgreement"])))
        lines.append("| Her iki karar uyumu | %s | %s | %s |"
                     % (pct(s_single["bothAgreement"]), pct(s_dice["bothAgreement"]),
                        pct(BASELINE["bothAgreement"])))
        lines.append("| Equity korelasyonu (Pearson) | %s | %s | — |"
                     % (num(s_single["equityCorrelation"]), num(s_dice["equityCorrelation"])))
        lines.append("| Equity ortalama \\|delta\\| | %s | %s | %s |"
                     % (num(s_single["equityMeanAbsDiff"]), num(s_dice["equityMeanAbsDiff"]),
                        num(BASELINE["equityMeanAbsDiff"])))
        lines.append("| Equity p90 \\|delta\\| | %s | %s | — |"
                     % (num(s_single["equityP90AbsDiff"]), num(s_dice["equityP90AbsDiff"])))
        lines.append("")

        for variant, label in (("singleRecord", "singleRecord"), ("diceAveraged", "diceAveraged")):
            s = summary[key][variant]
            lines.append("### %s — karisiklik matrisleri\n" % label)
            lines.append("| Ciftleme | gnubg: ciftle | gnubg: ciftleme |")
            lines.append("|---|---|---|")
            lines.append("| **bizim: ciftle** | %d | %d |"
                         % (s["doubleMatrix"]["bothDouble"], s["doubleMatrix"]["oursOnlyDouble"]))
            lines.append("| **bizim: ciftleme** | %d | %d |"
                         % (s["doubleMatrix"]["gnubgOnlyDouble"], s["doubleMatrix"]["bothNoDouble"]))
            lines.append("")
            lines.append("| Kabul | gnubg: kabul | gnubg: ret |")
            lines.append("|---|---|---|")
            lines.append("| **bizim: kabul** | %d | %d |"
                         % (s["takeMatrix"]["bothTake"], s["takeMatrix"]["oursOnlyTake"]))
            lines.append("| **bizim: ret** | %d | %d |"
                         % (s["takeMatrix"]["gnubgOnlyTake"], s["takeMatrix"]["bothPass"]))
            lines.append("")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("karsilastirilan:", len(rows))
    for key, s in summary.items():
        for variant in ("singleRecord", "diceAveraged"):
            v = s[variant]
            if v is None:
                continue
            print("%s/%s: ciftleme %.2f%%, kabul %.2f%%, her ikisi %.2f%%, ort|d| %.4f"
                  % (key, variant, 100.0 * v["doubleAgreement"], 100.0 * v["takeAgreement"],
                     100.0 * v["bothAgreement"], v["equityMeanAbsDiff"]))
    print("rapor:", REPORT)


if __name__ == "__main__":
    main()
