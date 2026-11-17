"""Faz 5 §9.1 — bearoff tablosunun gnubg ile karşılaştırılması.

``Backgammon.BearoffGen --measure`` komutu, iki tarafı da 1 taraflı bearoff olan
200 rastgele pozisyonu ``ml/artifacts/bearoff_measure.json`` dosyasına yazar. Bu betik
her pozisyonu ``gnubg-cli`` ile değerlendirir ve bizim tam equity'mizle karşılaştırır.

gnubg saf yarışta kendi bearoff veritabanını kullanır (``gnubg_os0.bd`` / ``gnubg_ts0.bd``);
bu yüzden karşılaştırma gerçek bir referanstır, sinir ağı tahmini değildir.

Kullanım::

    python ml/bearoff_gnubg.py --in ml/artifacts/bearoff_measure.json
    python ml/bearoff_gnubg.py --in ... --out ml/artifacts/bearoff_gnubg.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gnubg_er import (  # noqa: E402
    _NUMBER,
    GnubgError,
    GnubgSession,
    find_gnubg,
    gnubg_version,
    parse_eval,
    parse_evals,
    parse_number,
    parse_pipcounts,
    pip_count,
)

DEFAULT_INPUT = Path("ml/artifacts/bearoff_measure.json")
DEFAULT_OUTPUT = Path("ml/artifacts/bearoff_gnubg.md")
DEFAULT_PLIES = 2

# gnubg-cli tek süreçte ~200 tahtayı işlerken girdi tamponu taşıyor; küçük partiler
# kullanmak hem güvenli hem de aynı hızda.
BATCH = 20


_BEAROFF_ROW_RE = re.compile(
    r"^\s*(?P<rolls>\d+)\s+(?P<player>" + _NUMBER + r")\s+(?P<opponent>" + _NUMBER + r")",
    re.MULTILINE,
)


def parse_bearoff_distribution(text: str) -> dict[int, float] | None:
    """``Evaluator: Bearoff1`` tablosundaki *sırada olan* oyuncunun tam dağılımını döner.

    Anahtar = tur sayısı (gnubg satır etiketi), değer = ``P(tam olarak k turda toplar)``.
    Satır numaralandırması gnubg sürümüne göre 0'dan başlayabildiği için etiket kullanılır.
    Bearoff tablosu yoksa ``None``.
    """
    if "Evaluator:" not in text or "Bearoff" not in text:
        return None

    start = text.find("Bearing off")
    if start < 0:
        return None
    end = text.find("Average rolls", start)
    block = text[start:end if end > 0 else len(text)]

    values: dict[int, float] = {}
    for match in _BEAROFF_ROW_RE.finditer(block):
        values[int(match.group("rolls"))] = parse_number(match.group("player")) / 100.0
    return values or None


def evaluate(session: GnubgSession, boards: list[list[int]], turn: int) -> list[tuple[float, dict[int, float] | None]]:
    """Tahtaları gnubg sürecinde değerlendirir.

    Her tahta için ``(cubeless equity, tam dağılım veya None)`` döner. Equity sırada olan
    oyuncunundur; dağılım ``P(tam olarak k turda toplar)``, ``k = 1..``.
    """
    results: list[tuple[float, dict[int, float] | None]] = []
    for start in range(0, len(boards), BATCH):
        results.extend(_evaluate_batch(session, boards[start : start + BATCH], turn))
    return results


def _evaluate_batch(
    session: GnubgSession, boards: list[list[int]], turn: int
) -> list[tuple[float, dict[int, float] | None]]:
    commands = session._preamble()
    for board in boards:
        commands.append("new game")
        commands.extend(session.load_board(board, turn))
        commands.append("show pipcount")
        commands.append("eval")

    text = session.run(commands)
    pips = parse_pipcounts(text)
    tables = parse_evals(text)
    if len(pips) != len(boards) or len(tables) != len(boards):
        raise GnubgError(
            "toplu eval çıktısı eksik (pip %d, tablo %d, tahta %d)"
            % (len(pips), len(tables), len(boards))
        )

    blocks = text.split("The pip counts are:")[1:]
    results: list[tuple[float, dict[int, float] | None]] = []
    for board, (monster_pips, gnubg_pips), table, block in zip(boards, pips, tables, blocks):
        if monster_pips != pip_count(board, -1) or gnubg_pips != pip_count(board, 1):
            raise GnubgError("tahta yüklenmedi (pip uyuşmuyor)")
        key = str(session.plies)
        if key not in table:
            raise GnubgError("eval tablosunda %s-ply satırı yok: %s" % (key, sorted(table)))
        results.append((table[key], parse_bearoff_distribution(block)))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bearoff tablosunu gnubg ile karşılaştırır.")
    parser.add_argument("--in", dest="input", default=str(DEFAULT_INPUT))
    parser.add_argument("--out", dest="output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--plies", type=int, default=DEFAULT_PLIES)
    parser.add_argument("--gnubg", default=None)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    exe = find_gnubg(args.gnubg)
    if exe is None:
        print("HATA: gnubg-cli bulunamadı. Ölçüm yapılmadı; uydurma değer yazılmaz.", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    positions = payload["positions"]
    if args.limit > 0:
        positions = positions[: args.limit]
    if not positions:
        print("HATA: girdi dosyasında pozisyon yok.", file=sys.stderr)
        return 2

    session = GnubgSession(exe, plies=args.plies)
    boards = [p["board"] for p in positions]
    gnubg_results = evaluate(session, boards, 1)

    diffs: list[float] = []
    rows: list[tuple[list[int], list[int], float, float, float]] = []
    dist_diffs: list[float] = []
    dist_positions = 0
    for position, (gnubg_equity, gnubg_dist) in zip(positions, gnubg_results):
        ours = float(position["whiteEquity"])
        diff = abs(ours - gnubg_equity)
        diffs.append(diff)
        rows.append((position["whiteCounts"], position["blackCounts"], ours, gnubg_equity, diff))

        our_dist = position.get("whiteDistribution")
        if gnubg_dist and our_dist:
            dist_positions += 1
            for k, ours_p in enumerate(our_dist, start=1):
                if k in gnubg_dist:
                    dist_diffs.append(abs(ours_p - gnubg_dist[k]))

    diffs_sorted = sorted(diffs)
    maximum = diffs_sorted[-1]
    mean = sum(diffs) / len(diffs)
    median = diffs_sorted[len(diffs_sorted) // 2]
    within_001 = sum(1 for d in diffs if d <= 0.01) / len(diffs) * 100.0
    within_0001 = sum(1 for d in diffs if d <= 0.001) / len(diffs) * 100.0

    print("gnubg            : %s" % gnubg_version(exe))
    print("pozisyon         : %d" % len(diffs))
    print("maksimum |Δ|     : %.6f" % maximum)
    print("ortalama |Δ|     : %.6f" % mean)
    print("medyan |Δ|       : %.6f" % median)
    print("|Δ| <= 0.01      : %.1f%%" % within_001)
    print("|Δ| <= 0.001     : %.1f%%" % within_0001)

    dist_max = max(dist_diffs) if dist_diffs else 0.0
    dist_mean = (sum(dist_diffs) / len(dist_diffs)) if dist_diffs else 0.0
    print("dağılım |Δ|      : maks %.6f  ortalama %.6f  (%d pozisyon, %d hücre)"
          % (dist_max, dist_mean, dist_positions, len(dist_diffs)))

    worst = sorted(range(len(rows)), key=lambda i: rows[i][4], reverse=True)[:10]
    print()
    print("En büyük 10 fark:")
    for i in worst:
        white, black, ours, theirs, diff = rows[i]
        print(
            "  W%s B%s  bizim %+.6f  gnubg %+.6f  Δ %.6f"
            % (white, black, ours, theirs, diff)
        )

    lines = [
        "# Bearoff tablosu — gnubg karşılaştırması",
        "",
        "Faz 5 §9.1. Değerler `Backgammon.BearoffGen --measure` ve `ml/bearoff_gnubg.py` ile",
        "**ölçülmüştür**; uydurma değer yoktur.",
        "",
        "| Ölçüm | Değer |",
        "|---|---|",
        "| gnubg sürümü | `%s` |" % gnubg_version(exe),
        "| gnubg ply | %d (cubeless) |" % args.plies,
        "| Pozisyon sayısı | %d |" % len(diffs),
        "| Maksimum `\\|Δ\\|` equity | %.6f |" % maximum,
        "| Ortalama `\\|Δ\\|` equity | %.6f |" % mean,
        "| Medyan `\\|Δ\\|` equity | %.6f |" % median,
        "| `\\|Δ\\| ≤ 0,01` oranı | %.1f%% |" % within_001,
        "| `\\|Δ\\| ≤ 0,001` oranı | %.1f%% |" % within_0001,
        "| Dağılım maksimum `\\|Δ\\|` | %.6f |" % dist_max,
        "| Dağılım ortalama `\\|Δ\\|` | %.6f |" % dist_mean,
        "| Dağılım karşılaştırılan pozisyon | %d |" % dist_positions,
        "",
        "## En büyük 10 fark",
        "",
        "| Beyaz (1→6) | Siyah (1→6) | Bizim | gnubg | `\\|Δ\\|` |",
        "|---|---|---|---|---|",
    ]
    for i in worst:
        white, black, ours, theirs, diff = rows[i]
        lines.append(
            "| `%s` | `%s` | %+.6f | %+.6f | %.6f |"
            % (white, black, ours, theirs, diff)
        )
    lines.append("")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print()
    print("rapor            : %s" % output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
