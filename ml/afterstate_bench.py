"""Faz 5 §9.2: modelin deger kafasini gnubg ile dogrudan karsilastirir.

`Backgammon.MatchBench dump-afterstates` cikti dosyasini okur, her afterstate icin
gnubg'nin cubeless equity'sini alir ve korelasyon / MAE hesaplar.

Kullanim (gnubg'nin kendi Python yorumlayicisi ile):

    gnubg-cli.exe -p "F:/.../ml/afterstate_bench.py"

UYARI (F6-31): Bu betik gnubg'nin Python API'sini kullanir ve o yol bu projede
GUVENILIR DEGILDIR (bkz. F6-28: `cubeinfo['move']` yok sayilir). Faz 5'te
urettigi `stage_b_afterstates.md` sayilari tahta yonunun aynalanmasi nedeniyle
hataliydi. Kalibrasyon olcumu icin `ml/calibration_bench.py` (gnubg metin
protokolu) kullanilmalidir; bu betik yalnizca tarihsel kayit icin tutulmaktadir.
"""

import json
import os

import gnubg

DEFAULT_ROOT = r"F:\Projects\VijualStudioski\TavlaAI_Project"


def _repo_root():
    env = os.environ.get("TAVLA_ROOT")
    if env:
        return env
    for candidate in (os.getcwd(), DEFAULT_ROOT):
        if os.path.isdir(os.path.join(candidate, "ml", "artifacts")):
            return candidate
    raise RuntimeError("Depo koku bulunamadi; TAVLA_ROOT ortam degiskenini ayarlayin.")


ARTIFACTS = os.path.join(_repo_root(), "ml", "artifacts")
SOURCE = os.path.join(ARTIFACTS, "stage_b_afterstates.json")
REPORT = os.path.join(ARTIFACTS, "stage_b_afterstates.md")


def to_gnubg_board(case):
    """Proje tahtasini gnubg `anBoard` duzenine cevirir.

    Proje: board[1..24] = White'in 1..24 hanesi, board[25] = White'in topladigi.
    gnubg: anBoard[0] = oynayanin rakibi, anBoard[1] = oynayan; her biri
    1..24 hanesi + 25. eleman olarak toplanan pul sayisi.

    F6-31: onceki surum her iki satiri da aynaliyordu (`board[1+i]` /
    `board[24-i]`), bu da White'in pullarini 24..1 sirasina diziyordu.
    """
    board = case["board"]
    row0 = [max(board[24 - i], 0) for i in range(24)] + [max(board[0], 0)]
    row1 = [max(-board[1 + i], 0) for i in range(24)] + [max(-board[25], 0)]
    return (tuple(row0), tuple(row1))


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
    with open(SOURCE, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    ci = gnubg.cubeinfo(1, -1, 0, 0, (0, 0), 0, 0)
    ec = gnubg.evalcontext(0, 1, 1, 0, 0.0)

    pairs = []
    skipped = 0
    for case in cases:
        board = to_gnubg_board(case)
        if sum(board[0]) == 0 or sum(board[1]) == 0:
            skipped += 1
            continue
        try:
            cubeless = gnubg.evaluate(board, ci, ec)[5]
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        pairs.append((case["ourValue"], float(cubeless)))

    corr = pearson(pairs)
    mae = sum(abs(a - b) for a, b in pairs) / len(pairs)
    bias = sum(a - b for a, b in pairs) / len(pairs)
    ours = [a for a, _ in pairs]
    theirs = [b for _, b in pairs]

    lines = []
    lines.append("# Faz 5 §9.2 — Model deger kafasi vs gnubg (afterstate)\n")
    lines.append("Kaynak: `Backgammon.MatchBench dump-afterstates` (rastgele self-play).")
    lines.append("gnubg: `evaluate` (cubeless, 0-ply, deterministic).")
    lines.append("Perspektif: her iki tarafta da hamleyi yapan oyuncu.\n")
    lines.append("| Metrik | Deger |")
    lines.append("|---|---|")
    lines.append("| Karsilastirilan afterstate | %d |" % len(pairs))
    lines.append("| Atlanan | %d |" % skipped)
    lines.append("| Korelasyon (Pearson) | %.4f |" % corr)
    lines.append("| Ortalama mutlak hata (MAE) | %.4f |" % mae)
    lines.append("| Sistematik sapma (bizim - gnubg) | %+.4f |" % bias)
    lines.append("| Bizim equity araligi | %+.4f .. %+.4f |" % (min(ours), max(ours)))
    lines.append("| gnubg equity araligi | %+.4f .. %+.4f |" % (min(theirs), max(theirs)))
    lines.append("| Bizim standart sapma | %.4f |" % _std(ours))
    lines.append("| gnubg standart sapma | %.4f |" % _std(theirs))
    lines.append("")

    # Dogrusal kalibrasyon: gnubg ~ a * bizim + b. Modelin asiri dagilmasi icin tani.
    n = len(pairs)
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    a = sxy / sxx if sxx > 0 else 1.0
    b = my - a * mx
    cal = [(a * x + b, y) for x, y in pairs]
    cal_mae = sum(abs(x - y) for x, y in cal) / n
    cal_corr = pearson(cal)

    lines.append("## Dogrusal kalibrasyon (tani)")
    lines.append("")
    lines.append("`gnubg ~ a * bizim + b` en kucuk kareler fiti:")
    lines.append("")
    lines.append("| Katsayi | Deger |")
    lines.append("|---|---|")
    lines.append("| a (olcek) | %.4f |" % a)
    lines.append("| b (kayma) | %+.4f |" % b)
    lines.append("| Kalibrasyon sonrasi MAE | %.4f |" % cal_mae)
    lines.append("| Kalibrasyon sonrasi korelasyon | %.4f |" % cal_corr)
    lines.append("")
    lines.append("`a < 1` modelin deger kafasinin **asiri dagilmis** (over-dispersed) oldugunu gosterir.")
    lines.append("")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(os.path.join(ARTIFACTS, "stage_b_afterstate_pairs.json"), "w", encoding="utf-8") as f:
        json.dump({"a": a, "b": b, "pairs": pairs}, f)

    print("afterstate:", len(pairs), "atlanan:", skipped)
    print("korelasyon: %+.4f  MAE: %.4f  sapma: %+.4f" % (corr, mae, bias))
    print("bizim aralik: %+.4f .. %+.4f (std %.4f)" % (min(ours), max(ours), _std(ours)))
    print("gnubg aralik: %+.4f .. %+.4f (std %.4f)" % (min(theirs), max(theirs), _std(theirs)))
    print("kalibrasyon: a=%.4f b=%+.4f -> MAE %.4f, corr %.4f" % (a, b, cal_mae, cal_corr))
    print("rapor:", REPORT)


def _std(values):
    n = len(values)
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5


if __name__ == "__main__":
    main()
