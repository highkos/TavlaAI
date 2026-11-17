"""Faz 5 §8 Test 35: `met_rk.json` Bölüm 4.2 değişmezlerini sağlar; `maxMatchLength` tutarlı."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extract_met import check

REPO = Path(__file__).resolve().parent.parent.parent
MET_JSON = REPO / "Backgammon.Core" / "Match" / "met_rk.json"
GNUBG_XML = Path(r"F:\Program Files (x86)\gnubg\met\Rockwell-Kazaross.xml")


@pytest.fixture(scope="module")
def payload() -> dict:
    assert MET_JSON.exists(), f"MET JSON yok: {MET_JSON}"
    return json.loads(MET_JSON.read_text(encoding="utf-8"))


def test_met_extraction_invariants(payload: dict) -> None:
    errors = check(payload)
    assert errors == [], "MET değişmez ihlalleri: " + "; ".join(errors[:10])


def test_met_max_match_length_consistent(payload: dict) -> None:
    n = payload["maxMatchLength"]
    table = payload["table"]

    assert n == 25, "gnubg Rockwell-Kazaross 25 puanlık tablodur"
    assert len(table) == n + 1
    assert all(len(row) == n + 1 for row in table)

    # Sınırlar.
    assert all(table[0][b] == 1.0 for b in range(1, n + 1))
    assert all(table[a][0] == 0.0 for a in range(1, n + 1))

    # Bilinen referans değerler (gnubg RK MET).
    assert table[1][2] == pytest.approx(0.676888, abs=1e-9)
    assert table[2][1] == pytest.approx(0.323112, abs=1e-9)
    assert table[1][1] == pytest.approx(0.5, abs=1e-12)
    assert table[5][5] == pytest.approx(0.5, abs=1e-12)


def test_met_matches_gnubg_xml(payload: dict) -> None:
    if not GNUBG_XML.exists():
        pytest.skip(f"gnubg MET XML yok: {GNUBG_XML}")

    import re

    raw = GNUBG_XML.read_text(encoding="utf-8", errors="replace")
    block = re.search(r"<pre-crawford-table[^>]*>(.*?)</pre-crawford-table>", raw, re.S)
    assert block is not None

    rows = re.findall(r"<row>(.*?)</row>", block.group(1), re.S)
    xml = [[float(x) for x in re.findall(r"<me>([-0-9.eE+]+)</me>", row)] for row in rows]
    assert len(xml) == 25

    table = payload["table"]
    worst = 0.0
    for a in range(1, 26):
        for b in range(1, 26):
            worst = max(worst, abs(table[a][b] - xml[a - 1][b - 1]))

    assert worst <= 1e-12, f"gnubg XML ile maksimum |Δ| = {worst:.3e}"


def _small_valid_payload() -> dict:
    """3 puanlık, değişmezleri sağlayan küçük bir MET."""
    table = [
        [0.5, 1.0, 1.0, 1.0],
        [0.0, 0.5, 0.70, 0.85],
        [0.0, 0.3, 0.50, 0.65],
        [0.0, 0.15, 0.35, 0.50],
    ]
    return {"name": "test", "source": "test", "maxMatchLength": 3, "table": table}


def test_met_rejects_malformed() -> None:
    good = _small_valid_payload()
    assert check(good) == []

    broken = json.loads(json.dumps(good))
    broken["table"][1][2] = 0.9
    broken["table"][2][1] = 0.9
    assert check(broken) != [], "simetri ihlali yakalanmalı"

    broken2 = json.loads(json.dumps(good))
    broken2["table"][1][1] = 0.4
    assert check(broken2) != [], "köşegen ihlali yakalanmalı"

    broken3 = json.loads(json.dumps(good))
    broken3["table"][1][3] = 0.60
    broken3["table"][3][1] = 0.40
    assert check(broken3) != [], "monotonluk ihlali yakalanmalı"
