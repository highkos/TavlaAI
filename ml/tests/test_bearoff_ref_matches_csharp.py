"""Faz 5 §8 Test 34: `ml/bearoff_ref.py` bagimsiz DP'si C# uretimiyle ayni tabloyu verir."""

from __future__ import annotations

from pathlib import Path

import pytest

import bearoff_ref

REPO = Path(__file__).resolve().parent.parent.parent
BEAROFF_BIN = REPO / "ml" / "artifacts" / "bearoff1_v1.bin"

# Nicemleme: uint16 = round(x * 65535) -> en buyuk okuma hatasi 1/65535.
QUANTUM = 1.0 / 65535.0


@pytest.fixture(scope="module")
def csharp_table() -> dict:
    assert BEAROFF_BIN.exists(), f"bearoff DB yok: {BEAROFF_BIN}"
    return bearoff_ref.read_bin(str(BEAROFF_BIN))


@pytest.fixture(scope="module")
def python_table():
    # Python referansi C# dosyasindan BAGIMSIZ hesaplanir.
    states, cdf_rows, used = bearoff_ref.compute_cdf(12)
    return {"states": states, "cdf_rows": cdf_rows, "used": used}


def test_bearoff_ref_max_rolls_matches(csharp_table: dict, python_table: dict) -> None:
    assert csharp_table["max_rolls"] == python_table["used"], (
        "MaxRolls uyusmuyor: C# %d, Python %d"
        % (csharp_table["max_rolls"], python_table["used"])
    )
    assert csharp_table["max_rolls"] == 22, "beklenen MaxRolls = 22"
    assert len(csharp_table["table"]) == bearoff_ref.POSITIONS


def test_bearoff_ref_matches_csharp(csharp_table: dict, python_table: dict) -> None:
    used = python_table["used"]
    cdf_rows = python_table["cdf_rows"]
    table = csharp_table["table"]

    worst = 0.0
    worst_at = (-1, -1)
    out_of_tolerance = 0

    for p in range(bearoff_ref.POSITIONS):
        row = table[p]
        for k in range(used + 1):
            diff = abs(cdf_rows[k][p] - row[k] / 65535.0)
            if diff > worst:
                worst = diff
                worst_at = (p, k)
            if diff > 2.0 * QUANTUM:
                out_of_tolerance += 1

    assert out_of_tolerance == 0, (
        "%d hucre tolerans disinda (en buyuk fark %.3e, pozisyon %d, k=%d)"
        % (out_of_tolerance, worst, worst_at[0], worst_at[1])
    )
    assert worst <= 2.0 * QUANTUM, "en buyuk fark %.3e > %.3e" % (worst, 2.0 * QUANTUM)


def test_bearoff_ref_cdf_is_monotone(csharp_table: dict) -> None:
    max_rolls = csharp_table["max_rolls"]
    table = csharp_table["table"]
    for p in range(0, bearoff_ref.POSITIONS, 97):
        row = table[p]
        for k in range(1, max_rolls + 1):
            assert row[k] >= row[k - 1], "CDF monoton degil: pozisyon %d, k=%d" % (p, k)
        assert abs(row[max_rolls] / 65535.0 - 1.0) <= 2.0 * QUANTUM, (
            "CDF son degeri 1 degil: pozisyon %d -> %.6f" % (p, row[max_rolls] / 65535.0)
        )
