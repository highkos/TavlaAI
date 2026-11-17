"""Faz 5 §4.2: gnubg Rockwell-Kazaross MET'ini cikarir ve gomulu kaynak JSON'una yazar.

gnubg MET dosyasi `met/Rockwell-Kazaross.xml` icinde `pre-crawford-table` olarak durur.
Tablolar 25x25'tir ve **1 tabanli** "away" skorlariyla indekslenir: XML'deki
`row[i][j]` = "i+1 away" olan oyuncunun, "j+1 away" olan rakibe karsi mac kazanma
olasiligi (MWC). Bu yuzden `MWC(a, b) = xml[a-1][b-1]` (a, b >= 1).

Cikti semasi (Faz 5 §4.2):

    {
      "name": "Rockwell-Kazaross",
      "source": "...",
      "maxMatchLength": 25,
      "table": [[...], ...]        # table[a][b] = MWC(a, b), a/b = 0..25
    }

`table[0][b] = 1` (b > 0), `table[a][0] = 0` (a > 0), `table[0][0] = 0.5`
(tanimsiz; API `ArgumentException` firlatir, deger yalnizca dizi butunlugu icin).

Kullanim:
    python ml/extract_met.py                 # yazar + dogrular
    python ml/extract_met.py --check         # yalnizca dogrular
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

GNUBG_MET = r"F:\Program Files (x86)\gnubg\met\Rockwell-Kazaross.xml"
OUT_PATH = os.path.join("Backgammon.Core", "Match", "met_rk.json")

TOL_SYMMETRY = 1e-9
TOL_DIAGONAL = 1e-9


def parse_xml(path: str) -> tuple[list[list[float]], str]:
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    match = re.search(r"<pre-crawford-table[^>]*>(.*?)</pre-crawford-table>", raw, re.S)
    if match is None:
        raise RuntimeError("pre-crawford-table bulunamadi: " + path)

    rows = re.findall(r"<row>(.*?)</row>", match.group(1), re.S)
    table = [[float(x) for x in re.findall(r"<me>([-0-9.eE+]+)</me>", row)] for row in rows]
    if not table:
        raise RuntimeError("MET tablosu bos")

    width = len(table[0])
    if any(len(row) != width for row in table):
        raise RuntimeError("MET tablosu dikdortgen degil")
    if len(table) != width:
        raise RuntimeError("MET tablosu kare degil: %dx%d" % (len(table), width))

    info = re.search(r"<description>(.*?)</description>", raw, re.S)
    description = info.group(1).strip() if info else ""
    return table, description


def build(xml_table: list[list[float]]) -> dict:
    n = len(xml_table)
    max_match_length = n  # 1..n away
    size = max_match_length + 1

    table = [[0.0] * size for _ in range(size)]
    for a in range(size):
        for b in range(size):
            if a == 0 and b == 0:
                table[a][b] = 0.5
            elif a == 0:
                table[a][b] = 1.0
            elif b == 0:
                table[a][b] = 0.0
            else:
                table[a][b] = xml_table[a - 1][b - 1]

    return {
        "name": "Rockwell-Kazaross",
        "source": (
            "gnubg 1.08.003 met/Rockwell-Kazaross.xml, <pre-crawford-table> "
            "(1 tabanli away indeksleri; MWC(a,b) = xml[a-1][b-1])"
        ),
        "maxMatchLength": max_match_length,
        "table": table,
    }


def check(payload: dict) -> list[str]:
    """Faz 5 §4.2 degismezlerini dogrular. Hata listesi dondurur (bos = basarili)."""
    errors: list[str] = []
    table = payload["table"]
    n = payload["maxMatchLength"]
    size = n + 1

    if len(table) != size or any(len(row) != size for row in table):
        errors.append("tablo boyutu %d x %d olmali" % (size, size))
        return errors

    for a in range(size):
        for b in range(size):
            v = table[a][b]
            if not isinstance(v, float) or v != v or v in (float("inf"), float("-inf")):
                errors.append("(%d,%d) sonlu degil" % (a, b))
            elif v < 0.0 or v > 1.0:
                errors.append("(%d,%d) = %r aralik disi" % (a, b, v))

    for b in range(1, size):
        if abs(table[0][b] - 1.0) > 0.0:
            errors.append("MWC(0,%d) = %r, 1 olmali" % (b, table[0][b]))
    for a in range(1, size):
        if abs(table[a][0] - 0.0) > 0.0:
            errors.append("MWC(%d,0) = %r, 0 olmali" % (a, table[a][0]))

    for a in range(1, size):
        for b in range(1, size):
            s = table[a][b] + table[b][a]
            if abs(s - 1.0) > TOL_SYMMETRY:
                errors.append("simetri (%d,%d): toplam %r" % (a, b, s))

    for a in range(1, size):
        if abs(table[a][a] - 0.5) > TOL_DIAGONAL:
            errors.append("kosegen (%d,%d) = %r" % (a, a, table[a][a]))

    for a in range(1, size - 1):
        for b in range(1, size):
            if not table[a + 1][b] < table[a][b]:
                errors.append("monotonluk a (%d,%d): %r >= %r" % (a, b, table[a + 1][b], table[a][b]))
    for a in range(1, size):
        for b in range(1, size - 1):
            if not table[a][b + 1] > table[a][b]:
                errors.append("monotonluk b (%d,%d): %r <= %r" % (a, b, table[a][b + 1], table[a][b]))

    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="gnubg Rockwell-Kazaross MET cikarimi")
    parser.add_argument("--xml", default=GNUBG_MET)
    parser.add_argument("--out", default=OUT_PATH)
    parser.add_argument("--check", action="store_true", help="yalnizca mevcut JSON'u dogrula")
    args = parser.parse_args(argv)

    if args.check:
        payload = json.loads(io.open(args.out, encoding="utf-8").read())
    else:
        xml_table, description = parse_xml(args.xml)
        payload = build(xml_table)
        payload["source"] += " | " + description
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=1)
        io.open(args.out, "w", encoding="utf-8", newline="\n").write(text + "\n")
        print("yazildi: %s (%d bayt)" % (args.out, len(text) + 1))

    errors = check(payload)
    if errors:
        print("HATA: %d degismez ihlali" % len(errors))
        for e in errors[:20]:
            print("  " + e)
        return 1

    table = payload["table"]
    print("maxMatchLength = %d" % payload["maxMatchLength"])
    print("MWC(1,2) = %.6f  MWC(2,1) = %.6f" % (table[1][2], table[2][1]))
    print("MWC(2,2) = %.6f  MWC(5,5) = %.6f" % (table[2][2], table[5][5]))
    print("OK: tum degismezler saglandi")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
