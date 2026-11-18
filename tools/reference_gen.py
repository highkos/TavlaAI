#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bağımsız referans yasal-hamle üreteci (Faz 1, Bölüm 8 madde 5).

Bu betik, C# `LegalMoveGenerator`'dan TAMAMEN BAĞIMSIZ bir Python uygulamasıdır.
Amaç: motorun ürettiği yasal hamle sayısını ve sonuç pozisyonu kümelerini
dışsal bir kaynakla karşılaştırmak (perft benzeri referans).

gnubg bu makinede kurulu olmadığı için (bkz. ASSUMPTIONS.md E-01) referans veri
gnubg yerine bu bağımsız uygulama ile üretilmiştir. Uydurma değer YOKTUR.

Kullanım:
    python tools/reference_gen.py > Backgammon.Tests/ReferenceData/reference_positions.json
"""

import json
import random
import sys

BOARD_SIZE = 26
PIECES = 15


# ----------------------------------------------------------------------
# Temel yardımcılar
# ----------------------------------------------------------------------

def bar_index(turn):
    return 0 if turn == 1 else 25


def distance_to_off(point, turn):
    return 25 - point if turn == 1 else point


def is_home(point, turn):
    return 19 <= point <= 24 if turn == 1 else 1 <= point <= 6


def can_land(board, to, turn):
    v = board[to]
    return v >= -1 if turn == 1 else v <= 1


def is_blot(board, to, turn):
    return board[to] == -1 if turn == 1 else board[to] == 1


def is_bear_off_mode(board, turn):
    if board[bar_index(turn)] * turn > 0:
        return False
    if turn == 1:
        return all(board[p] <= 0 for p in range(1, 19))
    return all(board[p] >= 0 for p in range(7, 25))


def has_piece_further_back(board, point, turn):
    if turn == 1:
        return any(board[q] > 0 for q in range(1, point))
    return any(board[q] < 0 for q in range(point + 1, 25))


# ----------------------------------------------------------------------
# Adım üretimi
# ----------------------------------------------------------------------

def generate_steps(board, turn, die):
    """(from, to, is_bear_off) üçlüleri döndürür."""
    steps = []
    bar = bar_index(turn)

    if board[bar] * turn > 0:
        entry = bar + die * turn
        if 1 <= entry <= 24 and can_land(board, entry, turn):
            steps.append((bar, entry, False))
        return steps

    bear_off = is_bear_off_mode(board, turn)
    off_target = 25 if turn == 1 else 0

    for p in range(1, 25):
        if board[p] * turn <= 0:
            continue

        if bear_off:
            dist = distance_to_off(p, turn)
            if dist <= die and (dist == die or not has_piece_further_back(board, p, turn)):
                steps.append((p, off_target, True))
                continue

        to = p + die * turn
        if 1 <= to <= 24 and can_land(board, to, turn):
            steps.append((p, to, False))

    return steps


def apply_step(board, turn, step):
    """Yeni board döndürür (girdi değişmez)."""
    frm, to, is_off = step
    nb = list(board)

    nb[frm] -= turn
    if is_off:
        return nb

    if is_blot(board, to, turn):
        nb[to] += turn          # vurulan taş rakibin barına gider
        nb[bar_index(-turn)] -= turn

    nb[to] += turn
    return nb


# ----------------------------------------------------------------------
# Yasal hamle üretimi (kaba kuvvet, pozisyon tabanlı tekilleştirme)
# ----------------------------------------------------------------------

def legal_after_states(board, turn, dice, white_off, black_off):
    """
    Döndürür: (max_steps, {(board_tuple, white_off, black_off), ...})
    """
    results = {}          # key -> None (küme)
    state = {"max": 0}

    def dfs(nb, remaining, depth, wo, bo):
        if depth > state["max"]:
            state["max"] = depth
            results.clear()

        extended = False
        seen_dice = set()

        for i, die in enumerate(remaining):
            if die in seen_dice:
                continue
            seen_dice.add(die)

            for step in generate_steps(nb, turn, die):
                frm, to, is_off = step
                nb2 = apply_step(nb, turn, step)
                wo2, bo2 = wo, bo
                if is_off:
                    if turn == 1:
                        wo2 += 1
                    else:
                        bo2 += 1

                rest = remaining[:i] + remaining[i + 1:]
                dfs(nb2, rest, depth + 1, wo2, bo2)
                extended = True

        if not extended and depth == state["max"]:
            results[(tuple(nb), wo, bo)] = None

    dfs(list(board), list(dice), 0, white_off, black_off)

    max_steps = state["max"]
    if max_steps == 0:
        return 0, set()

    # Büyük zar kuralı: yalnızca tek zar oynanabiliyorsa büyük zar zorunlu.
    if max_steps == 1 and len(dice) == 2 and dice[0] != dice[1]:
        higher = max(dice)
        if generate_steps(board, turn, higher):
            filtered = set()
            for key in results:
                # Tek adımlı sonuç: büyük zarla oynanmış mı?
                if _single_step_uses_die(board, turn, higher, key):
                    filtered.add(key)
            return max_steps, filtered

    return max_steps, set(results.keys())


def _single_step_uses_die(board, turn, die, key):
    nb, wo, bo = key
    for step in generate_steps(board, turn, die):
        frm, to, is_off = step
        nb2 = apply_step(board, turn, step)
        wo2, bo2 = (wo, bo)
        if is_off:
            if turn == 1:
                wo2 += 1
            else:
                bo2 += 1
        if (tuple(nb2), wo2, bo2) == key:
            return True
    return False


# ----------------------------------------------------------------------
# Rastgele oyun (pozisyon örnekleme için)
# ----------------------------------------------------------------------

START_BOARD = [0] * BOARD_SIZE
START_BOARD[1] = 2
START_BOARD[12] = 5
START_BOARD[17] = 3
START_BOARD[19] = 5
START_BOARD[24] = -2
START_BOARD[13] = -5
START_BOARD[8] = -3
START_BOARD[6] = -5


def random_positions(rng, count, max_plies=40):
    """Rastgele oyunlar oynayarak (board, turn, dice, wo, bo) pozisyonları toplar."""
    out = []
    while len(out) < count:
        board = list(START_BOARD)
        wo = bo = 0
        turn = 1 if rng.random() < 0.5 else -1

        for _ in range(max_plies):
            d1 = rng.randint(1, 6)
            d2 = rng.randint(1, 6)
            dice = [d1, d1, d1, d1] if d1 == d2 else [d1, d2]

            max_steps, states = legal_after_states(board, turn, dice, wo, bo)
            if max_steps == 0 or not states:
                turn = -turn
                continue

            if rng.random() < 0.5:
                out.append((list(board), turn, sorted(dice), wo, bo))
                if len(out) >= count:
                    break

            nb, wo, bo = rng.choice(sorted(states))
            board = list(nb)

            if wo == PIECES or bo == PIECES:
                break

            turn = -turn

    return out


# ----------------------------------------------------------------------
# Elle yazılmış uç durumlar
# ----------------------------------------------------------------------

def handcrafted():
    cases = []

    def add(name, board, turn, dice, wo=0, bo=0):
        cases.append((name, list(board), turn, sorted(dice), wo, bo))

    def empty():
        return [0] * BOARD_SIZE

    # 1) Bardan giriş, tüm 6 giriş hanesi kapalı -> pas.
    b = empty()
    b[0] = 1
    for p in range(1, 7):
        b[p] = -2
    b[24] = -3
    b[13] = -5
    b[8] = -5
    add("bar-closed-white", b, 1, [3, 5])

    # 2) Bar'da 1 taş + açık giriş -> yalnızca giriş hamleleri.
    b = empty()
    b[0] = 1
    for p in (1, 2, 4, 5, 6):
        b[p] = -2
    b[24] = -3
    b[13] = -5
    b[8] = -5
    add("bar-open-white", b, 1, [3, 5])

    # 3) Büyük zar kuralı: yalnızca büyük zar oynanabiliyor.
    b = empty()
    b[1] = 1
    b[9] = -2
    b[20] = -13
    add("big-die-white", b, 1, [3, 5], wo=14)

    # 4) Toplama: tam zar.
    b = empty()
    b[22] = 1
    b[24] = 14
    add("bearoff-exact-white", b, 1, [5, 6])

    # 5) Toplama: zar > en geri taş.
    b = empty()
    b[20] = 1
    b[24] = 14
    add("bearoff-overshoot-white", b, 1, [5, 6])

    # 6) Toplama yasağı: geride taş var.
    b = empty()
    b[18] = 1
    b[24] = 14
    add("bearoff-blocked-white", b, 1, [5, 6])

    # 7) Duble 4 hamle.
    b = empty()
    b[1] = 2
    b[12] = 5
    b[17] = 3
    b[19] = 5
    b[24] = -2
    b[13] = -5
    b[8] = -3
    b[6] = -5
    add("double-4-steps-white", b, 1, [2, 2])

    # 8) Siyah toplama.
    b = empty()
    b[3] = -1
    b[1] = -14
    add("bearoff-exact-black", b, -1, [2, 3])

    # 9) Siyah bar girişi.
    b = empty()
    b[25] = -1
    for p in (19, 20, 22, 23, 24):
        b[p] = 2
    b[1] = 3
    b[12] = 5
    b[17] = 5
    add("bar-open-black", b, -1, [2, 4])

    # 10) Başlangıç pozisyonu, 6-6.
    add("start-6-6", START_BOARD, 1, [6, 6])

    # 11) Başlangıç pozisyonu, 3-1.
    add("start-3-1", START_BOARD, 1, [3, 1])

    # 12) Başlangıç pozisyonu, 5-5.
    add("start-5-5", START_BOARD, 1, [5, 5])

    return cases


# ----------------------------------------------------------------------
# Ana akış
# ----------------------------------------------------------------------

def main():
    rng = random.Random(20240517)

    cases = handcrafted()
    cases.extend(
        ("random-%03d" % i, b, t, d, wo, bo)
        for i, (b, t, d, wo, bo) in enumerate(random_positions(rng, 45))
    )

    out = {
        "generator": "python-reference-1.0",
        "note": (
            "gnubg bu makinede kurulu olmadigi icin referans veri bagimsiz bir Python "
            "uygulamasi ile uretildi. Bkz. ASSUMPTIONS.md E-01."
        ),
        "cases": [],
    }

    for name, board, turn, dice, wo, bo in cases:
        # Duble: 4 zar olarak oynanır (Bölüm 4.2).
        if len(dice) == 2 and dice[0] == dice[1]:
            dice = [dice[0]] * 4

        max_steps, states = legal_after_states(board, turn, dice, wo, bo)
        out["cases"].append({
            "name": name,
            "board": board,
            "turn": turn,
            "dice": dice,
            "whiteOff": wo,
            "blackOff": bo,
            "maxSteps": max_steps,
            "afterStates": [
                {"board": list(b), "whiteOff": w, "blackOff": k}
                for (b, w, k) in sorted(states)
            ],
        })

    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
