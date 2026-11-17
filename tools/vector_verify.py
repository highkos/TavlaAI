#!/usr/bin/env python3
"""Faz 2 v4 -- bagimsiz capraz dil dogrulayicisi.

`Backgammon.Tests/ReferenceData/vector_golden.json` dosyasindaki her kaydi
spesifikasyondan (Faz 2 v4 Bolum 2-3) bagimsiz olarak yeniden vektorlestirir ve
`vectorHex` alanindaki uint32 bit desenleriyle **birebir** karsilastirir.

Amac: C# tarafinin urettigi altin dosyanin, ayni sozlesmeyi uygulayan ikinci bir
implementasyon (numpy float32) tarafindan da uretilebildigini kanitlamak. Bu,
Faz 4'teki Python okuyucusunun on kosuludur.

Kullanim:
    python tools/vector_verify.py [--file <yol>] [--verbose]

Cikis kodu 0 = tum kayitlar birebir eslesti, 1 = uyusmazlik var.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

# ---------------------------------------------------------------------------
# Sabitler (Faz 2 v4 Bolum 2)
# ---------------------------------------------------------------------------

VECTOR_SIZE = 221
POINTS = 24
POINT_BLOCK_SIZE = 4
ACTIVE_OFFSET = 0
OPP_OFFSET = 96
ACTIVE_BAR = 192
OPP_BAR = 193
ACTIVE_OFF = 194
OPP_OFF = 195
CUBE_OWNER = 196
CUBE_VALUE = 197
IS_MONEY_GAME = 198
IS_CRAWFORD = 199
ACTIVE_PIP = 200
OPP_PIP = 201
ACTIVE_ESCAPED = 202
OPP_ESCAPED = 203
IS_CONTACT = 204
ACTIVE_AWAY_OFFSET = 205
OPP_AWAY_OFFSET = 213
AWAY_BUCKETS = 8

BLOT = 0
GATE = 1
THREE_PLUS = 2
DENSITY = 3

PIP_DIVISOR = np.float32(167.0)
F2 = np.float32(2.0)
F6 = np.float32(6.0)
F15 = np.float32(15.0)
F1 = np.float32(1.0)
F0 = np.float32(0.0)

BOARD_SIZE = 26
WHITE_BAR = 0
BLACK_BAR = 25


# ---------------------------------------------------------------------------
# Faz 1 v4 ile ayni yardimcilar
# ---------------------------------------------------------------------------

def distance_to_off(point: int, player: int) -> int:
    """Toplama uzakligi: Beyaz icin 25-p, Siyah icin p."""
    return 25 - point if player == 1 else point


def bar_index(player: int) -> int:
    return WHITE_BAR if player == 1 else BLACK_BAR


def count_of(value: int, player: int) -> int:
    """Bir hanedeki `player` tas sayisi."""
    if player > 0:
        return value if value > 0 else 0
    return -value if value < 0 else 0


def active_max_j(board, player: int) -> int:
    """Bolum 3.2: barda tas varsa 25, tahtada tas yoksa 0."""
    if count_of(board[bar_index(player)], player) > 0:
        return 25

    max_j = 0
    for point in range(1, POINTS + 1):
        if count_of(board[point], player) > 0:
            j = distance_to_off(point, player)
            if j > max_j:
                max_j = j
    return max_j


def opponent_min_j(board, player: int) -> int:
    """Bolum 3.1: rakip barda tas varsa 0; tahtada tasi yoksa +inf; aksi halde min j."""
    opponent = -player

    if count_of(board[bar_index(opponent)], opponent) > 0:
        return 0

    min_j = sys.maxsize
    for point in range(1, POINTS + 1):
        if count_of(board[point], opponent) > 0:
            j = distance_to_off(point, player)
            if j < min_j:
                min_j = j
    return min_j


def pip_count(board, player: int) -> int:
    """Bolum 3.5: toplam pip; bar tasi 25 sayilir."""
    total = 0
    for point in range(1, POINTS + 1):
        n = count_of(board[point], player)
        if n:
            total += n * distance_to_off(point, player)

    bar = count_of(board[bar_index(player)], player)
    if bar:
        total += bar * 25
    return total


def escaped_count(board, player: int) -> int:
    """Bolum 3.3: j < jOppMin olan tahtadaki taslar. Bar/toplanan sayilmaz."""
    j_opp_min = opponent_min_j(board, player)
    if j_opp_min <= 0:
        return 0

    count = 0
    for point in range(1, POINTS + 1):
        n = count_of(board[point], player)
        if n and distance_to_off(point, player) < j_opp_min:
            count += n
    return count


def is_contact(board) -> bool:
    """Bolum 3.4: aktifMaxJ > jOppMin (perspektiften bagimsiz)."""
    return active_max_j(board, 1) > opponent_min_j(board, 1)


def cube_value_neuron(cube_value: int) -> np.float32:
    """Bolum 2: min(log2(cubeValue)/6, 1); cubeValue <= 1 icin 0."""
    if cube_value <= 1:
        return F0

    log2 = 0
    power = 1
    while power < cube_value:
        power <<= 1
        log2 += 1

    value = np.float32(log2) / F6
    return F1 if value > F1 else value


def away_bucket(away: int) -> int:
    """Bolum 2: min(away, 8) - 1."""
    return (away if away < AWAY_BUCKETS else AWAY_BUCKETS) - 1

# ---------------------------------------------------------------------------
# Vektorlestirici (Bolum 2)
# ---------------------------------------------------------------------------

def write_point_block(out: np.ndarray, offset: int, n: int) -> None:
    """Bir hanenin 4 noronu: blot, kapi, 3+, yogunluk."""
    out[offset + BLOT] = F1 if n == 1 else F0
    out[offset + GATE] = F1 if n >= 2 else F0
    out[offset + THREE_PLUS] = F1 if n >= 3 else F0
    out[offset + DENSITY] = np.float32(n - 3) / F2 if n > 3 else F0


def vectorize(board, white_borne_off: int, black_borne_off: int,
              cube_value: int, cube_owner: int, match_length: int,
              white_score: int, black_score: int, is_crawford: bool,
              perspective: int) -> np.ndarray:
    """221 noronluk vektoru uretir (Faz 2 v4 Bolum 2)."""
    out = np.zeros(VECTOR_SIZE, dtype=np.float32)

    # --- Hane bloklari (0..191) -------------------------------------------
    # Her iki blok da AYNI j cercevesini kullanir (rakip kendi cercevesine
    # cevrilmez) -- Bolum 1.2.
    for point in range(1, POINTS + 1):
        value = board[point]

        n_active = count_of(value, perspective)
        if n_active:
            j = distance_to_off(point, perspective)
            write_point_block(out, ACTIVE_OFFSET + POINT_BLOCK_SIZE * (j - 1), n_active)

        n_opp = count_of(value, -perspective)
        if n_opp:
            j = distance_to_off(point, perspective)
            write_point_block(out, OPP_OFFSET + POINT_BLOCK_SIZE * (j - 1), n_opp)

    # --- Sistem noronlari (192..220) --------------------------------------
    active_bar = count_of(board[bar_index(perspective)], perspective)
    opp_bar = count_of(board[bar_index(-perspective)], -perspective)
    out[ACTIVE_BAR] = np.float32(active_bar) / F2
    out[OPP_BAR] = np.float32(opp_bar) / F2

    active_off = white_borne_off if perspective > 0 else black_borne_off
    opp_off = black_borne_off if perspective > 0 else white_borne_off
    out[ACTIVE_OFF] = np.float32(active_off) / F15
    out[OPP_OFF] = np.float32(opp_off) / F15

    out[CUBE_OWNER] = np.float32(cube_owner * perspective)
    out[CUBE_VALUE] = cube_value_neuron(cube_value)
    out[IS_MONEY_GAME] = F1 if match_length == 0 else F0
    out[IS_CRAWFORD] = F1 if is_crawford else F0

    out[ACTIVE_PIP] = np.float32(pip_count(board, perspective)) / PIP_DIVISOR
    out[OPP_PIP] = np.float32(pip_count(board, -perspective)) / PIP_DIVISOR

    out[ACTIVE_ESCAPED] = np.float32(escaped_count(board, perspective)) / F15
    out[OPP_ESCAPED] = np.float32(escaped_count(board, -perspective)) / F15

    out[IS_CONTACT] = F1 if is_contact(board) else F0

    # away noronlari: money game'de hepsi 0 (zaten sifirlandi).
    if match_length > 0:
        active_away = match_length - (white_score if perspective > 0 else black_score)
        opp_away = match_length - (black_score if perspective > 0 else white_score)
        out[ACTIVE_AWAY_OFFSET + away_bucket(active_away)] = F1
        out[OPP_AWAY_OFFSET + away_bucket(opp_away)] = F1

    return out


# ---------------------------------------------------------------------------
# Karsilastirma
# ---------------------------------------------------------------------------

def bits(vector: np.ndarray) -> np.ndarray:
    return vector.astype(np.float32, copy=False).view(np.uint32)


def parse_hex(text: str) -> np.ndarray:
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    if len(tokens) != VECTOR_SIZE:
        raise ValueError("vectorHex %d eleman iceriyor, %d bekleniyordu." % (len(tokens), VECTOR_SIZE))
    return np.array([int(t, 16) for t in tokens], dtype=np.uint32)


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    default_file = os.path.join(here, "..", "Backgammon.Tests", "ReferenceData", "vector_golden.json")

    parser = argparse.ArgumentParser(description="Faz 2 v4 capraz dil altin dosya dogrulayicisi.")
    parser.add_argument("--file", default=default_file, help="Altin JSON yolu.")
    parser.add_argument("--verbose", action="store_true", help="Uyusmazliklarda ilk noronlari yaz.")
    args = parser.parse_args(argv)

    path = os.path.abspath(args.file)
    if not os.path.exists(path):
        print("Altin dosya yok: %s" % path, file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if data.get("vectorSize") != VECTOR_SIZE:
        print("vectorSize %r, %d bekleniyordu." % (data.get("vectorSize"), VECTOR_SIZE), file=sys.stderr)
        return 1

    records = data.get("records") or []
    if not records:
        print("Kayit yok.", file=sys.stderr)
        return 1

    mismatched = 0
    for index, record in enumerate(records):
        board = record["board"]
        if len(board) != BOARD_SIZE:
            print("Kayit %d: board %d eleman, %d bekleniyordu." % (index, len(board), BOARD_SIZE), file=sys.stderr)
            return 1

        expected = parse_hex(record["vectorHex"])
        actual = bits(vectorize(
            board,
            record["whiteBorneOff"],
            record["blackBorneOff"],
            record["cubeValue"],
            record["cubeOwner"],
            record["matchLength"],
            record["whiteScore"],
            record["blackScore"],
            record["isCrawfordGame"],
            record["perspective"],
        ))

        if not np.array_equal(expected, actual):
            mismatched += 1
            diff = np.nonzero(expected != actual)[0]
            print("Kayit %d UYUSMUYOR: %d noron farkli (ilk: %s)"
                  % (index, diff.size, diff[:8].tolist()), file=sys.stderr)
            if args.verbose:
                for neuron in diff[:8]:
                    print("  noron %d: beklenen 0x%08X, bulunan 0x%08X"
                          % (neuron, expected[neuron], actual[neuron]), file=sys.stderr)

    total = len(records)
    if mismatched:
        print("BASARISIZ: %d/%d kayit uyusmadi." % (mismatched, total), file=sys.stderr)
        return 1

    print("TAMAM: %d kayit x %d noron birebir eslesti (featureVersion=%s)."
          % (total, VECTOR_SIZE, data.get("featureVersion")))
    return 0


if __name__ == "__main__":
    sys.exit(main())