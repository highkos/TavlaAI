"""Faz 5 §8 Test 34: `ml/bearoff_ref.py` referansi C# `bearoff1_v1.bin` ile uyusur.

Tam DP dogrulamasi (`bearoff_ref.check`) yaklasik 5 dakika surer; bu yuzden varsayilan
kosuda **erisilebilir kapanisi kucuk** ornek pozisyonlar uzerinde ayni DP yeniden
hesaplanir ve ikili dosyayla karsilastirilir. Tam kontrol `TAVLA_BEAROFF_FULL=1` ile
etkinlesir.
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

import pytest

import bearoff_ref as br

REPO = Path(__file__).resolve().parent.parent.parent
BEAROFF_BIN = REPO / "ml" / "artifacts" / "bearoff1_v1.bin"

#: Kuantalama toleransi: 1/65535 ~ 1.53e-05; iki kuantalama adimi birakilir.
TOLERANCE = 2.0 / 65535.0

#: Erisilebilir kapanisi kucuk (toplam tas <= 4) ornek pozisyonlar.
SMALL_SAMPLES = [
    (1, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 1),
    (2, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 2),
    (3, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 3),
    (4, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 4),
    (1, 1, 0, 0, 0, 0),
    (0, 0, 1, 0, 0, 1),
    (1, 0, 0, 0, 0, 1),
    (0, 1, 0, 0, 1, 0),
    (2, 0, 0, 0, 0, 1),
    (0, 0, 0, 1, 0, 2),
    (0, 0, 0, 0, 0, 0),
]

#: `bearoff_ref.py --dump-known` ile olculen referans degerler (MaxRolls = 22).
KNOWN_CDF = {
    (1, 0, 0, 0, 0, 0): [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    (0, 0, 0, 0, 0, 1): [0.75, 1.0, 1.0, 1.0, 1.0, 1.0],
    (2, 0, 0, 0, 0, 0): [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    (0, 0, 0, 0, 0, 2): [0.111111, 0.782407, 0.996871, 1.0, 1.0, 1.0],
    (15, 0, 0, 0, 0, 0): [0.0, 0.0, 0.0, 0.000772, 0.035494, 0.263224],
    (0, 0, 0, 0, 0, 15): [0.0, 0.0, 0.0, 0.000001, 0.000021, 0.000284],
    (0, 0, 0, 0, 0, 0): [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
}


@pytest.fixture(scope="module")
def binary() -> dict:
    assert BEAROFF_BIN.exists(), f"bearoff ikili dosyasi yok: {BEAROFF_BIN}"
    return br.read_bin(str(BEAROFF_BIN))


def test_header_and_crc(binary: dict) -> None:
    raw = BEAROFF_BIN.read_bytes()
    assert raw[0:4] == br.MAGIC
    assert struct.unpack_from("<H", raw, 4)[0] == br.FORMAT_VERSION
    assert raw[6] == br.POINTS
    assert raw[7] == br.CHECKERS
    assert struct.unpack_from("<I", raw, 8)[0] == br.POSITIONS

    payload_bytes = struct.unpack_from("<I", raw, 20)[0]
    crc = struct.unpack_from("<I", raw, 16)[0]
    payload = raw[br.HEADER_BYTES:br.HEADER_BYTES + payload_bytes]
    assert len(payload) == payload_bytes
    assert zlib.crc32(payload) & 0xFFFFFFFF == crc
    assert len(raw) == br.HEADER_BYTES + payload_bytes

    assert binary["max_rolls"] == 22, "en kotu pozisyon 22 tur gerektirir"
    assert binary["flags"] & 1 == 0, "Faz 5'te gammon tablosu yok"


def test_rank_unrank_roundtrip() -> None:
    seen = set()
    for index in range(br.POSITIONS):
        counts = br.unrank(index)
        assert sum(counts) <= br.CHECKERS
        assert br.rank(counts) == index
        seen.add(counts)
    assert len(seen) == br.POSITIONS


def test_cdf_is_monotone(binary: dict) -> None:
    table = binary["table"]
    max_rolls = binary["max_rolls"]
    for p in range(br.POSITIONS):
        row = table[p]
        previous = 0.0
        for k in range(max_rolls + 1):
            value = row[k] / 65535.0
            assert value >= previous - 1e-9, f"pozisyon {p}, k={k} monoton degil"
            previous = value
        assert row[max_rolls] == 65535, f"pozisyon {p} MaxRolls'ta 1.0'a ulasmiyor"


def test_known_reference_values(binary: dict) -> None:
    table = binary["table"]
    for counts, expected in KNOWN_CDF.items():
        p = br.rank(counts)
        for k, want in enumerate(expected, start=1):
            got = table[p][k] / 65535.0
            assert got == pytest.approx(want, abs=TOLERANCE), (
                f"{counts} k={k}: beklenen {want:.6f}, bulunan {got:.6f}"
            )


def _subset_cdf(sample: tuple[int, ...], max_rolls: int):
    """Ornek pozisyonun erisilebilir kapanisi uzerinde Bolum 3.9 DP'sini yeniden kosar."""
    seen = {sample}
    frontier = [sample]
    while frontier:
        nxt = []
        for state in frontier:
            for d1, d2 in br.DICE:
                for target in br.successors(state, d1, d2):
                    if target not in seen:
                        seen.add(target)
                        nxt.append(target)
        frontier = nxt

    states = sorted(seen, key=lambda s: (sum((i + 1) * s[i] for i in range(br.POINTS)), s))
    index = {s: i for i, s in enumerate(states)}
    zero = index[(0, 0, 0, 0, 0, 0)]
    succ = [
        [tuple(index[t] for t in br.successors(s, d1, d2)) for d1, d2 in br.DICE]
        for s in states
    ]

    expected = [0.0] * len(states)
    for i, _ in enumerate(states):
        if i == zero:
            continue
        total = 0.0
        for di, (d1, d2) in enumerate(br.DICE):
            weight = 1 if d1 == d2 else 2
            total += weight * min(expected[j] for j in succ[i][di])
        expected[i] = 1.0 + total / 36.0

    policy = [[0] * len(br.DICE) for _ in states]
    for i in range(len(states)):
        if i == zero:
            continue
        for di in range(len(br.DICE)):
            policy[i][di] = min(succ[i][di], key=lambda j: (expected[j], j))

    previous = [0.0] * len(states)
    previous[zero] = 1.0
    cumulative = [0.0] * len(states)
    rows = [list(cumulative)]
    for _ in range(1, max_rolls + 1):
        current = [0.0] * len(states)
        for i in range(len(states)):
            if i == zero:
                continue
            total = 0.0
            for di, (d1, d2) in enumerate(br.DICE):
                weight = 1 if d1 == d2 else 2
                total += weight * previous[policy[i][di]]
            current[i] = total / 36.0
        previous = current
        for i in range(len(states)):
            cumulative[i] += previous[i]
            if cumulative[i] > 1.0:
                cumulative[i] = 1.0
        rows.append(list(cumulative))

    for k in range(1, max_rolls + 1):
        rows[k][zero] = 1.0

    return states, rows, index


def test_bearoff_ref_matches_csharp(binary: dict) -> None:
    """Test 34: C# tablosu, bagimsiz Python DP'siyle kuantalama toleransinda ayni."""
    table = binary["table"]
    max_rolls = binary["max_rolls"]

    worst = 0.0
    worst_at = None
    mismatches = 0
    compared = 0

    for sample in SMALL_SAMPLES:
        states, rows, index = _subset_cdf(sample, max_rolls)
        p = br.rank(sample)
        for k in range(max_rolls + 1):
            expected = rows[k][index[sample]]
            actual = table[p][k] / 65535.0
            diff = abs(expected - actual)
            compared += 1
            if diff > worst:
                worst = diff
                worst_at = (sample, k)
            if diff > TOLERANCE:
                mismatches += 1

    print(f"  karsilastirilan hucre = {compared}")
    print(f"  en buyuk fark = {worst:.3e} ({worst_at[0]}, k={worst_at[1]})")
    print(f"  tolerans disi = {mismatches}")

    assert mismatches == 0, (
        f"Python referansi ile C# tablosu uyusmuyor: {mismatches} hucre, "
        f"en buyuk fark {worst:.3e} ({worst_at})"
    )


@pytest.mark.skipif(
    os.environ.get("TAVLA_BEAROFF_FULL") != "1",
    reason="tam DP dogrulamasi ~5 dakika surer; TAVLA_BEAROFF_FULL=1 ile etkinlesir",
)
def test_bearoff_ref_full_check() -> None:
    assert br.check(str(BEAROFF_BIN)) == 0
