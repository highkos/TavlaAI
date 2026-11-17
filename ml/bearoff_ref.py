"""Faz 5 §3.9 — 1 tarafli bearoff CDF tablosunun BAGIMSIZ Python referansi.

Bu betik C# kodunu OKUMADAN, yalnizca `Faz 5.md` Bolum 3.2 / 3.3 / 3.9 tanimindan
yazilmistir. Amac: iki bagimsiz uygulamanin ayni tabloyu urettigini gostermek
(Bolum 8, Test 34). Uretim araci DEGIL, dogrulama aracidir.

Kullanim:
    python ml/bearoff_ref.py --check ml/artifacts/bearoff1_v1.bin
    python ml/bearoff_ref.py --dump-known
"""

from __future__ import annotations

import argparse
import struct
import sys
from itertools import combinations_with_replacement

POINTS = 6
CHECKERS = 15
POSITIONS = 54264
HEADER_BYTES = 64
MAGIC = b"TVB1"
FORMAT_VERSION = 1

DICE = [(a, b) for a in range(1, 7) for b in range(a, 7)]


# ----------------------------------------------------------------------
# Indeksleme (Bolum 3.3)
# ----------------------------------------------------------------------

def _build_binom(n: int = 22, k: int = 7) -> list[list[int]]:
    table = [[0] * k for _ in range(n)]
    for i in range(n):
        table[i][0] = 1
        for j in range(1, k):
            if j > i:
                table[i][j] = 0
            elif j == i:
                table[i][j] = 1
            else:
                table[i][j] = table[i - 1][j - 1] + table[i - 1][j]
    return table


BINOM = _build_binom()


def choose(n: int, k: int) -> int:
    if n < 0 or k < 0 or k >= 7 or n >= 22:
        return 0
    return BINOM[n][k]


def rank(counts) -> int:
    total = 0
    s = 0
    for i in range(POINTS):
        s += counts[i]
        total += choose(s + i, i + 1)
    return total


def unrank(index: int) -> tuple[int, ...]:
    counts = [0] * POINTS
    remaining = index
    s_values = [0] * POINTS
    for i in range(POINTS - 1, -1, -1):
        best = 0
        for candidate in range(CHECKERS + 1):
            if choose(candidate + i, i + 1) <= remaining:
                best = candidate
            else:
                break
        s_values[i] = best
        remaining -= choose(best + i, i + 1)
    for i in range(POINTS):
        prev = s_values[i - 1] if i > 0 else 0
        counts[i] = s_values[i] - prev
    return tuple(counts)


def all_states() -> list[tuple[int, ...]]:
    states = [None] * POSITIONS
    for state in combinations_with_replacement(range(POINTS + 1), CHECKERS):
        counts = [0] * POINTS
        for p in state:
            if p < POINTS:
                counts[p] += 1
        states[rank(counts)] = tuple(counts)
    return states


# ----------------------------------------------------------------------
# Yasal hamleler (Bolum 3.9: bearoff modu, bagimsiz yazim)
# ----------------------------------------------------------------------

def single_moves(counts, die: int):
    """Tek zarla oynanabilir adimlar. ('off', i) veya ('move', i, j).

    `counts[i]` = `i+1` hanesindeki tas sayisi; 1-hane toplanmaya en yakin.
    Ilerleme yonu = azalan hane indeksi.
    """
    result = []
    for i in range(POINTS):
        if counts[i] == 0:
            continue
        dist = i + 1
        if dist <= die:
            further_back = any(counts[q] > 0 for q in range(i + 1, POINTS))
            if dist == die or not further_back:
                result.append(("off", i))
                continue
        j = i - die
        if j >= 0:
            result.append(("move", i, j))
    return result


def apply_move(counts, move):
    if move[0] == "off":
        i = move[1]
        out = list(counts)
        out[i] -= 1
        return tuple(out)
    _, i, j = move
    out = list(counts)
    out[i] -= 1
    out[j] += 1
    return tuple(out)


def successors(counts, d1: int, d2: int) -> tuple[tuple[int, ...], ...]:
    """Maksimum sayida zar kullanildiktan sonra ulasilabilen durumlar."""
    dice = (d1, d1, d1, d1) if d1 == d2 else (d1, d2)
    collected = []

    def dfs(state, remaining, depth):
        collected.append((depth, state))
        used = set()
        for k, die in enumerate(remaining):
            if die in used:
                continue
            used.add(die)
            rest = remaining[:k] + remaining[k + 1:]
            for move in single_moves(state, die):
                dfs(apply_move(state, move), rest, depth + 1)

    dfs(counts, dice, 0)
    best = max(depth for depth, _ in collected)
    return tuple(sorted({state for depth, state in collected if depth == best}))


def build_successor_table(states):
    """succ[p][d] = pozisyon p icin d. zar kombinasyonunun ardisil siralari."""
    table = []
    for state in states:
        row = []
        for d1, d2 in DICE:
            row.append(tuple(rank(s) for s in successors(state, d1, d2)))
        table.append(row)
    return table


# ----------------------------------------------------------------------
# Dinamik programlama (Bolum 3.9)
# ----------------------------------------------------------------------

def compute_cdf(max_rolls: int = 12, limit: int = 64):
    """Bolum 3.9: tek politika (E[T] minimize eden hamle) altinda CDF.

    Oyuncu her pozisyonda **tek** bir politika izler: beklenen tur sayisini en aza
    indiren hamle. ``P(T <= k)``'yi her ``k`` icin ayri ayri maksimize etmek yanlistir;
    ayni zar atisinda farkli ``k`` icin farkli hamle secilemez.
    """
    states = all_states()
    succ = build_successor_table(states)

    def pips(state):
        return sum((i + 1) * state[i] for i in range(6))

    order = sorted(range(POSITIONS), key=lambda p: (pips(states[p]), p))

    # 1) E[T] — topolojik sirada (her hamle pip sayisini azaltir).
    expected = [0.0] * POSITIONS
    for p in order:
        if p == 0:
            continue
        total = 0.0
        for di, (d1, d2) in enumerate(DICE):
            weight = 1 if d1 == d2 else 2
            total += weight * min(expected[s] for s in succ[p][di])
        expected[p] = 1.0 + total / 36.0

    # 2) Politika: her (pozisyon, zar) icin E[T]'yi en aza indiren ardil.
    policy = [[0] * len(DICE) for _ in range(POSITIONS)]
    for p in range(1, POSITIONS):
        for di in range(len(DICE)):
            policy[p][di] = min(succ[p][di], key=lambda s: (expected[s], s))

    # 3) Dagitim: p_k(c) = (1/36) * sum_zar w * p_{k-1}(c*).
    previous = [0.0] * POSITIONS
    previous[0] = 1.0
    rows = [[0.0] * POSITIONS]
    cumulative = [0.0] * POSITIONS
    cdf_rows = [list(cumulative)]

    used = 0
    for k in range(1, limit + 1):
        current = [0.0] * POSITIONS
        # "Hepsi toplanmis" yutan durumdur: T = 0 kesindir; k >= 1 icin olasilik 0.
        current[0] = 0.0
        for p in range(1, POSITIONS):
            total = 0.0
            for di, (d1, d2) in enumerate(DICE):
                weight = 1 if d1 == d2 else 2
                total += weight * previous[policy[p][di]]
            current[p] = total / 36.0
        previous = current
        rows.append(list(previous))

        for p in range(POSITIONS):
            cumulative[p] += previous[p]
            if cumulative[p] > 1.0:
                cumulative[p] = 1.0
        cdf_rows.append(list(cumulative))

        used = k
        if k >= max_rolls and all(cumulative[p] >= 1.0 - 1e-12 for p in range(1, POSITIONS)):
            break

    if not all(cumulative[p] >= 1.0 - 1e-12 for p in range(1, POSITIONS)):
        raise RuntimeError("DP 64 turda tamamlanmadi")

    # Sira 0 = "hepsi toplanmis" yutan durumu: cdf[0] = 0 kalir, k >= 1 icin 1.
    for k in range(1, used + 1):
        cdf_rows[k][0] = 1.0

    return states, cdf_rows, used


# ----------------------------------------------------------------------
# Dosya okuma / karsilastirma
# ----------------------------------------------------------------------

def read_bin(path: str):
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < HEADER_BYTES:
        raise ValueError("dosya baslik icin cok kisa")
    if data[0:4] != MAGIC:
        raise ValueError("magic uyusmuyor")
    version = struct.unpack_from("<H", data, 4)[0]
    if version != FORMAT_VERSION:
        raise ValueError("surum uyusmuyor: %d" % version)
    points = data[6]
    checkers = data[7]
    positions = struct.unpack_from("<I", data, 8)[0]
    max_rolls = data[12]
    flags = data[13]
    crc = struct.unpack_from("<I", data, 16)[0]
    payload_bytes = struct.unpack_from("<I", data, 20)[0]
    if points != POINTS or checkers != CHECKERS or positions != POSITIONS:
        raise ValueError("baslik alanlari uyusmuyor")
    payload = data[HEADER_BYTES:HEADER_BYTES + payload_bytes]
    if len(payload) != payload_bytes:
        raise ValueError("payload eksik")
    import zlib
    if zlib.crc32(payload) & 0xFFFFFFFF != crc:
        raise ValueError("payloadCrc32 uyusmuyor")
    row_bytes = (max_rolls + 1) * 2
    table = []
    for p in range(POSITIONS):
        base = p * row_bytes
        table.append(struct.unpack_from("<%dH" % (max_rolls + 1), payload, base))
    return {
        "max_rolls": max_rolls,
        "flags": flags,
        "table": table,
    }


def check(path: str) -> int:
    print("Referans DP hesaplaniyor (bu islem birkac dakika surebilir)...")
    states, rows, used = compute_cdf(12)
    print("  referans maxRolls = %d" % used)

    data = read_bin(path)
    print("  dosya    maxRolls = %d" % data["max_rolls"])
    if data["max_rolls"] != used:
        print("  HATA: maxRolls uyusmuyor")
        return 1

    table = data["table"]
    worst = 0
    worst_at = None
    mismatches = 0
    for p in range(POSITIONS):
        row = table[p]
        for k in range(used + 1):
            expected = rows[k][p]
            actual = row[k] / 65535.0
            diff = abs(expected - actual)
            if diff > worst:
                worst = diff
                worst_at = (p, k)
            if diff > 2.0 / 65535.0:
                mismatches += 1

    print("  en buyuk fark = %.3e (pozisyon %d, k=%d)" % (worst, worst_at[0], worst_at[1]))
    print("  tolerans disi = %d" % mismatches)
    if mismatches:
        print("  HATA: tablo referansla uyusmuyor")
        return 1
    print("  OK: C# ve Python tablolari ayni")
    return 0


def dump_known() -> int:
    states, rows, used = compute_cdf(12)
    samples = [
        (1, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 1),
        (2, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 2),
        (15, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 15),
        (0, 0, 0, 0, 0, 0),
    ]
    print("maxRolls = %d" % used)
    for sample in samples:
        p = rank(sample)
        values = ", ".join("%.6f" % rows[k][p] for k in range(1, min(used, 6) + 1))
        print("  %-24s cdf[1..%d] = %s" % (str(sample), min(used, 6), values))
    return 0


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Bagimsiz bearoff CDF referansi")
    parser.add_argument("--check", metavar="BIN", help="uretilen .bin dosyasini karsilastir")
    parser.add_argument("--dump-known", action="store_true", help="ornek pozisyon degerlerini yaz")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.check)
    if args.dump_known:
        return dump_known()
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
