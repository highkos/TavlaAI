"""Faz 5 §9.2: kup karari uyumu olcumu.

`Backgammon.MatchBench gen-positions` ile uretilen pozisyonlari gnubg'nin Python
modulune verir, `cfevaluate` ile kup kararini alir ve `Backgammon.MatchBench cube`
ciktisiyla karsilastirir.

Kullanim (gnubg'nin kendi Python yorumlayicisi ile calistirilmalidir):

    gnubg-cli.exe -p "F:/.../ml/match_bench.py"

Ciktilar:
    ml/artifacts/stage_b_cube_gnubg.json
    ml/artifacts/stage_b_cube.md
"""

import json
import os
import sys

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
OURS = os.path.join(ARTIFACTS, "stage_b_cube_ours.json")
DICE = os.path.join(ARTIFACTS, "stage_b_cube_dice.json")
GNUBG_OUT = os.path.join(ARTIFACTS, "stage_b_cube_gnubg.json")
REPORT = os.path.join(ARTIFACTS, "stage_b_cube.md")


def to_gnubg_board(case):
    """Bizim board[26] (+Beyaz/-Siyah, 0 = Beyaz bar, 25 = Siyah bar) -> gnubg tahtasi.

    Esleme (F6-22): bizim konvansiyonda ``DistanceToOff(p, +1) = 25 - p``, yani Beyaz'in
    1-noktasi bizim 24, Siyah'in 1-noktasi bizim 1. gnubg'de ``anBoard[0][i]`` oyuncu 0'in
    ``i+1`` noktasidir. Bu yuzden:

        gnubg row0[i] = board[24 - i]      (i = 0..23)
        gnubg row1[i] = -board[1 + i]      (i = 0..23)

    Bar indeksleri (24) dogrudan tasinir. Onceki surum noktalari ters esliyordu; bu,
    Faz 5 kup uyum sayilarini gecersiz kilan bir hataydi.
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
    """Pozisyonu gnubg Python API'sinin gercekten kullandigi bicime cevirir (F6-28).

    ``gnubg.evaluate`` / ``gnubg.cfevaluate`` ``cubeinfo`` icindeki ``move`` alanini
    **yok sayar**: her zaman ``anBoard[1]``i zar atan oyuncu kabul eder ve sonucu onun
    perspektifinden dondurur. Bu yuzden zar atan oyuncuyu fiziksel olarak ``anBoard[1]``e
    tasiriz; aksi halde equity sabit bir oyuncuyla karsilastirilir.

    Doner: ``(board, score, cube_owner)``; ucu de gnubg oyuncu numaralandirmasinda
    (0 = zar atmayan, 1 = zar atan).
    """
    row0, row1 = to_gnubg_board(case)
    owner = gnubg_owner(case.get("cubeOwner", 0), case.get("cubeValue", 1))
    if case["turn"] == 1:
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

    # ``move`` yok sayilir (F6-28); zar atan oyuncu her zaman gnubg oyuncu 1'dir.
    ci = gnubg.cubeinfo(cube, owner, 1, matchto, score, crawford, 0)
    ec = gnubg.evalcontext(plies, 1, 1, 0, 0.0)
    result = gnubg.cfevaluate(board, ci, ec)
    optimal, nodouble, take, drop, code, text = result
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
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    syy = sum((b - my) ** 2 for _, b in pairs)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return sxy / ((sxx ** 0.5) * (syy ** 0.5))


def main():
    with open(POSITIONS, "r", encoding="utf-8") as f:
        positions = json.load(f)
    with open(OURS, "r", encoding="utf-8") as f:
        ours = json.load(f)

    our_by_name = {c["name"]: c for c in ours["cases"]}

    dice_by_name = {}
    if os.path.exists(DICE):
        with open(DICE, "r", encoding="utf-8") as f:
            dice_by_name = {c["name"]: c["equityDiceAvg"] for c in json.load(f)["cases"]}

    rows = []
    for case in positions["cases"]:
        name = case["name"]
        if name not in our_by_name:
            continue
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
        entry["ours"] = our_by_name[name]
        if name in dice_by_name:
            entry["equityDiceAvg"] = dice_by_name[name]
        rows.append(entry)

    with open(GNUBG_OUT, "w", encoding="utf-8") as f:
        json.dump({"cases": rows}, f, indent=2)

    lines = []
    lines.append("# Faz 5 §9.2 — Kup karari uyumu (gnubg referansi)\n")
    lines.append("Pozisyon kaynagi: `Backgammon.MatchBench gen-positions` (rastgele oyunlardan).")
    lines.append("gnubg karari: `cfevaluate` (cubeful), `deterministic=1`.")
    lines.append("Bizim karar: `EquityCubeAdvisor` (model + `HeuristicOutcomeDistribution`).\n")
    lines.append("> **Bu dosya tarihsel bir kayittir.** Asama F'de uc olcum/sözlesme hatasi")
    lines.append("> bulundu (F6-28 gnubg `cubeinfo.move`, F6-29 danisman perspektifi, F6-30 mac")
    lines.append("> ciftleme karsilastirmasi). Asagidaki sayilar bu duzeltmelerden **once**")
    lines.append("> alinmistir; guncel ve gecerli olcum `ml/artifacts/stage_f_cube.md` dosyasidir.\n")

    summary = {}
    for plies in (0, 2):
        key = "gnubg%d" % plies
        valid = [r for r in rows
                 if not r.get("skipped") and "error" not in r[key]
                 and r[key]["shouldDouble"] is not None
                 and r["ours"].get("evaluated", True)]
        n = len(valid)
        if n == 0:
            continue

        both_double = sum(1 for r in valid if r[key]["shouldDouble"] and r["ours"]["shouldDouble"])
        both_nodouble = sum(1 for r in valid if not r[key]["shouldDouble"] and not r["ours"]["shouldDouble"])
        ours_only = sum(1 for r in valid if r["ours"]["shouldDouble"] and not r[key]["shouldDouble"])
        gnubg_only = sum(1 for r in valid if r[key]["shouldDouble"] and not r["ours"]["shouldDouble"])

        both_take = sum(1 for r in valid if r[key]["shouldTake"] and r["ours"]["shouldTake"])
        both_pass = sum(1 for r in valid if not r[key]["shouldTake"] and not r["ours"]["shouldTake"])
        ours_take_only = sum(1 for r in valid if r["ours"]["shouldTake"] and not r[key]["shouldTake"])
        gnubg_take_only = sum(1 for r in valid if r[key]["shouldTake"] and not r["ours"]["shouldTake"])

        # Equity korelasyonu: bizim E ile gnubg'nin cubeless equity'si.
        pairs = []
        for r in valid:
            g = r[key]
            if "cubelessEquity" in g:
                pairs.append((r["ours"]["equityNoDouble"], g["cubelessEquity"]))
        corr = pearson(pairs) if len(pairs) > 2 else None
        mean_abs = (sum(abs(a - b) for a, b in pairs) / len(pairs)) if pairs else None

        # Zar-ortalamali varyant (Faz 6 onerisi): ayni pozisyonlar uzerinde.
        dpairs = [(r["equityDiceAvg"], r[key]["cubelessEquity"]) for r in valid
                  if "equityDiceAvg" in r and "cubelessEquity" in r[key]]
        dcorr = pearson(dpairs) if len(dpairs) > 2 else None
        dmean = (sum(abs(a - b) for a, b in dpairs) / len(dpairs)) if dpairs else None

        double_agree = (both_double + both_nodouble) / n
        take_agree = (both_take + both_pass) / n
        both_agree = sum(
            1
            for r in valid
            if r[key]["shouldDouble"] == r["ours"]["shouldDouble"]
            and r[key]["shouldTake"] == r["ours"]["shouldTake"]
        ) / n

        summary[key] = {
            "n": n,
            "doubleAgreement": double_agree,
            "takeAgreement": take_agree,
            "bothAgreement": both_agree,
            "equityCorrelation": corr,
            "equityMeanAbsDiff": mean_abs,
            "diceCorrelation": dcorr,
            "diceMeanAbsDiff": dmean,
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

        lines.append("## gnubg %d-ply\n" % plies)
        lines.append("| Metrik | Deger |")
        lines.append("|---|---|")
        lines.append("| Karsilastirilan pozisyon | %d |" % n)
        lines.append("| Ciftleme uyumu | %.2f%% |" % (100.0 * double_agree))
        lines.append("| Kabul/ret uyumu | %.2f%% |" % (100.0 * take_agree))
        lines.append("| Her iki karar uyumu | %.2f%% |" % (100.0 * both_agree))
        if corr is not None:
            lines.append("| Equity korelasyonu (Pearson), tek-kayit | %.4f |" % corr)
            lines.append("| Equity ortalama \\|delta\\|, tek-kayit | %.4f |" % mean_abs)
        if dcorr is not None:
            lines.append("| Equity korelasyonu (Pearson), zar-ortalamali | %.4f |" % dcorr)
            lines.append("| Equity ortalama \\|delta\\|, zar-ortalamali | %.4f |" % dmean)
        lines.append("")
        lines.append("| Ciftleme | gnubg: ciftle | gnubg: ciftleme |")
        lines.append("|---|---|---|")
        lines.append("| **bizim: ciftle** | %d | %d |" % (both_double, ours_only))
        lines.append("| **bizim: ciftleme** | %d | %d |" % (gnubg_only, both_nodouble))
        lines.append("")
        lines.append("| Kabul | gnubg: kabul | gnubg: ret |")
        lines.append("|---|---|---|")
        lines.append("| **bizim: kabul** | %d | %d |" % (both_take, ours_take_only))
        lines.append("| **bizim: ret** | %d | %d |" % (gnubg_take_only, both_pass))
        lines.append("")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("karsilastirilan:", len(rows))
    for key, s in summary.items():
        print(
            "%s: ciftleme uyumu %.2f%%, kabul uyumu %.2f%%, her ikisi %.2f%%"
            % (key, 100.0 * s["doubleAgreement"], 100.0 * s["takeAgreement"], 100.0 * s["bothAgreement"])
        )
    print("rapor:", REPORT)


if __name__ == "__main__":
    main()
