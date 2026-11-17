"""Faz 7 Bolum 9.9 (Test 122, 123): C#/Python equity paritesi.

Tek altin dosya (``Backgammon.Tests/ReferenceData/equity_golden.json``), iki
tuketici. C# tarafi ``EquityGoldenTests``, Python tarafi bu modul.

**Sifir tolerans.** ``cumulativeHex`` ve ``equityHex`` alanlari bit duzeyinde
karsilastirilir. Kayan nokta toleransi **kabul edilmez**: fark varsa iki taraf
farkli formül kullaniyor demektir (F6-31/F6-32 sinifi sessiz hata).

Neden float32 aynasi: C# ``OutcomeDistribution`` alanlari ``float``'tir ve
``FromProbabilities`` icinde float32 yuvarlamasi yapar. ``ml/equity.py``'nin
``*_f32`` fonksiyonlari bu boru hattinin birebir kopyasidir.
"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest

import equity
from conftest import GOLDEN_EQUITY_PATH

#: F7-05: ``Flip`` involusyonu bit duzeyinde degil, float32 yuvarlamasi
#: mertebesindedir. Olculen ust sinir 1,4e-7.
FLIP_TOL = 1e-6

CUMULATIVE_KEYS = ("win", "winGammon", "winBackgammon", "loseGammon", "loseBackgammon")


# ----------------------------------------------------------------------
# Yardimcilar
# ----------------------------------------------------------------------


def _hex_f32(value) -> str:
    """C# ``BitConverter.SingleToUInt32Bits(v).ToString("x8")`` karsiligi."""
    bits = struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]
    return format(bits, "08x")


def _hex_f64(value) -> str:
    """C# ``BitConverter.DoubleToUInt64Bits(v).ToString("x16")`` karsiligi."""
    bits = struct.unpack("<Q", struct.pack("<d", float(value)))[0]
    return format(bits, "016x")


def _f32_from_hex(text: str) -> np.float32:
    bits = int(text, 16)
    return np.float32(struct.unpack("<f", struct.pack("<I", bits))[0])


@pytest.fixture(scope="module")
def golden() -> dict:
    assert GOLDEN_EQUITY_PATH.is_file(), (
        "altin dosya yok: " + str(GOLDEN_EQUITY_PATH)
        + " - `dotnet test Backgammon.Tests --filter GenerateEquityGolden` ile uretin"
    )
    return json.loads(GOLDEN_EQUITY_PATH.read_text(encoding="utf-8"))


def _records(golden: dict) -> list[dict]:
    return list(golden["records"])


def _valid_records(golden: dict) -> list[dict]:
    return [r for r in _records(golden) if r["isValid"]]


def _normalized_records(golden: dict) -> list[dict]:
    """``Flip`` yalnizca toplami 1 olan girdilerde involusyondur.

    ``unnormalized`` grubu kasitli olarak toplami 1 olmayan vektorler icerir;
    ``flip_f32`` normalize ettigi icin bu grupta karsilastirma anlamsizdir.
    """
    return [r for r in _valid_records(golden) if r["group"] != "unnormalized"]


def _exclusive_f32(record: dict) -> np.ndarray:
    return np.array([_f32_from_hex(h) for h in record["exclusiveHex"]], dtype=np.float32)


# ----------------------------------------------------------------------
# Test 123 - altin dosyanin tazeligi
# ----------------------------------------------------------------------


def test_123_golden_metadata_matches_python_constants(golden):
    assert golden["schemaVersion"] == 1
    assert golden["recordCount"] == 300
    assert len(golden["records"]) == 300
    assert "Faz 7" in golden["generatedBy"]


def test_123_prob_order_matches_python(golden):
    assert tuple(golden["probOrder"]) == equity.PROB_ORDER


def test_123_equity_weights_match_python(golden):
    assert np.array_equal(
        np.asarray(golden["equityWeights"], dtype=np.float64), equity.EQUITY_WEIGHTS
    )


def test_123_group_counts(golden):
    counts: dict[str, int] = {}
    for r in _records(golden):
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    assert counts == {
        "unit": 6,
        "random": 250,
        "boundary": 20,
        "unnormalized": 20,
        "invalid": 4,
    }


def test_123_invalid_records_are_invalid(golden):
    invalid = [r for r in _records(golden) if not r["isValid"]]
    assert len(invalid) == 4
    for r in invalid:
        assert r["equityHex"] == "0000000000000000"
        for key in CUMULATIVE_KEYS:
            assert r["cumulativeHex"][key] == "00000000"


# ----------------------------------------------------------------------
# Test 122 - bit duzeyi parite
# ----------------------------------------------------------------------


def test_122_cumulative_fields_match_bit_for_bit(golden):
    mismatches: list[str] = []
    for r in _valid_records(golden):
        c = equity.to_cumulative_f32(_exclusive_f32(r))
        for key in CUMULATIVE_KEYS:
            got = _hex_f32(c[_snake(key)])
            want = r["cumulativeHex"][key]
            if got != want:
                mismatches.append(
                    r["group"] + "[" + str(r["index"]) + "]." + key
                    + ": got " + got + " want " + want
                )
    assert not mismatches, "kumulatif alan uyusmazligi: " + "; ".join(mismatches[:10])


def test_122_equity_matches_bit_for_bit(golden):
    mismatches: list[str] = []
    for r in _valid_records(golden):
        c = equity.to_cumulative_f32(_exclusive_f32(r))
        got = _hex_f64(
            equity.equity_from_cumulative_f32(
                c["win"], c["win_gammon"], c["win_backgammon"],
                c["lose_gammon"], c["lose_backgammon"],
            )
        )
        want = r["equityHex"]
        if got != want:
            mismatches.append(
                r["group"] + "[" + str(r["index"]) + "]: got " + got + " want " + want
            )
    assert not mismatches, "equity uyusmazligi: " + "; ".join(mismatches[:10])


def test_122_equity_from_exclusive_shortcut_agrees(golden):
    """``equity_from_exclusive_f32`` (normalize + kumulatif + toplam) ayni sonucu vermeli."""
    for r in _valid_records(golden):
        got = _hex_f64(equity.equity_from_exclusive_f32(_exclusive_f32(r)))
        assert got == r["equityHex"], r["group"] + "[" + str(r["index"]) + "]"


def test_122_equity_in_range(golden):
    for r in _valid_records(golden):
        assert -3.0 <= r["equity"] <= 3.0


def test_122_unit_vectors_give_exact_weights(golden):
    unit = [r for r in _records(golden) if r["group"] == "unit"]
    assert len(unit) == 6
    for r in unit:
        assert r["equity"] == equity.EQUITY_WEIGHTS[r["index"]]


def test_122_unnormalized_records_are_normalized(golden):
    """Toplami 1 olmayan girdiler normalize edilir; equity yine [-3, 3] icinde."""
    rows = [r for r in _records(golden) if r["group"] == "unnormalized"]
    assert len(rows) == 20
    for r in rows:
        assert r["isValid"] is True
        assert -3.0 <= r["equity"] <= 3.0


# ----------------------------------------------------------------------
# F7-05 - Flip involusyonu
# ----------------------------------------------------------------------


def test_flip_is_involution_within_float32_rounding(golden):
    worst = 0.0
    for r in _normalized_records(golden):
        p = _exclusive_f32(r)
        back = equity.flip_f32(equity.flip_f32(p))
        worst = max(worst, float(np.max(np.abs(back.astype(np.float64) - p.astype(np.float64)))))
    assert worst <= FLIP_TOL, "en kotu sapma " + repr(worst)


def test_flip_negates_equity_within_float32_rounding(golden):
    worst = 0.0
    for r in _normalized_records(golden):
        p = _exclusive_f32(r)
        e = float(equity.equity_from_exclusive_f32(p))
        f = float(equity.equity_from_exclusive_f32(equity.flip_f32(p)))
        worst = max(worst, abs(e + f))
    assert worst <= FLIP_TOL, "en kotu sapma " + repr(worst)


# ----------------------------------------------------------------------
# Yardimci: camelCase -> snake_case
# ----------------------------------------------------------------------


def _snake(key: str) -> str:
    out = []
    for ch in key:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)
