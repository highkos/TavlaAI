"""Faz 7 Bolum 4.3 (Test 93) -- dort bagimsiz dogrulama probu.

Her olcum betigi, **ilk calistirmadan once** en az bir kez bagimsiz bir yolla
dogrulanir. Bu modul o dort probu kalici hale getirir:

1. **Tahta donusumu** -- simetrik/asimetrik referans tahtalar gnubg'ye verilir ve
   beklenen equity karsilastirilir. F6-31'i (aynalanmis tahta) bu prob yakalar.
2. **Sutun secimi** -- ``_equity_at`` yapay tablolarla test edilir; yanlis sutun
   ``ValueError`` vermelidir. F6-32'yi (sessiz 0-ply dususu) bu prob yakalar.
3. **Perspektif** -- ayni tahta iki perspektiften degerlendirilir; isaret tutarli
   olmalidir. gnubg'nin agi **antisimetrik degildir** (F6-29), bu yuzden buyukluk
   farki normaldir; aranan sey isaret tutarliligidir.
4. **Pip sayisi** -- her tahta icin ``show pipcount`` bagimsiz hesapla karsilastirilir
   (gnubg gecersiz pip sayisini reddeder).

Kullanim::

    python ml/measure_integrity.py --json ml/artifacts/stage_a_integrity.json
    python ml/measure_integrity.py --markdown ml/artifacts/stage_a_integrity.md

gnubg yoksa modul **uydurma deger uretmez**; sifir olmayan cikis kodu doner.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import gnubg_er  # noqa: E402
import tools.reference_gen as refgen  # noqa: E402

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------

PROBE_BOARD = "board"
PROBE_COLUMN = "column"
PROBE_PERSPECTIVE = "perspective"
PROBE_PIP = "pip"

PROBE_NAMES: tuple[str, ...] = (PROBE_BOARD, PROBE_COLUMN, PROBE_PERSPECTIVE, PROBE_PIP)

PROBE_LABELS: dict[str, str] = {
    PROBE_BOARD: "Tahta donusumu",
    PROBE_COLUMN: "Sutun secimi",
    PROBE_PERSPECTIVE: "Perspektif",
    PROBE_PIP: "Pip sayisi",
}

#: Faz 7 Bolum 4.3'un istedigi referans tahta: Beyaz 1 pul projede 24, Siyah 1 pul
#: projede 1. Proje cercevesinde iki taraf da kendi 1-hanesinde (1 pip uzakta) oldugu
#: icin "simetrik" gorunur; gnubg cercevesinde ise X 1 pip, O 24 pip uzaktadir, yani
#: X kazanir ve beklenen equity **+1,0**'dir. Olculdu: +1,0.
DOC_BOARD: tuple[int, ...] = tuple(
    (1 if i == 24 else 0) + (-1 if i == 1 else 0) for i in range(26)
)

#: Ayni tahtanin **isaret-ters** donusumu (``simple[i] = board[i]``). Olculdu: +0,479.
DOC_BOARD_SIGN_FLIPPED: tuple[int, ...] = tuple(-v for v in DOC_BOARD)

#: Ayni tahtanin **aynalanmis** donusumu (``simple[i] = -board[25-i]``). Olculdu: +0,479.
DOC_BOARD_MIRRORED: tuple[int, ...] = tuple(
    (1 if i == 1 else 0) + (-1 if i == 24 else 0) for i in range(26)
)

#: Beklenen equity ve tolerans (Faz 7 Bolum 4.3).
DOC_BOARD_EXPECTED = 1.0
DOC_BOARD_TOLERANCE = 0.02

#: Baslangic pozisyonunun gnubg Position ID'si -- **bilinen sabit**, bizim kodumuzdan
#: bagimsiz. Tahta gercekten yuklenmediyse bu kimlik cikmaz.
START_POSITION_ID = "4HPwATDgc/ABMA"
START_PIP = 167

#: Bar tasi 25 pip sayilir; iki taraf da tek tasini barda tutan tahta.
BAR_BOARD: tuple[int, ...] = tuple(
    (1 if i == 0 else 0) + (-1 if i == 25 else 0) for i in range(26)
)
BAR_PIP = 25

#: Perspektif probu icin asimetrik tahtalar (``random-002`` ve ``random-003`` kumeden).
PERSPECTIVE_TOLERANCE = 0.02

#: Pip probunda kac kume pozisyonu denetlenecek.
PIP_SAMPLE = 12

_POSITION_ID_RE = re.compile(r"Position ID:\s*(\S+)")


class IntegrityError(RuntimeError):
    """Bir dogrulama probu beklenen sonucu vermedi."""


# ----------------------------------------------------------------------
# Sonuc tipleri
# ----------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Tek bir probun sonucu."""

    name: str
    ok: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return PROBE_LABELS.get(self.name, self.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "ok": self.ok,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


@dataclass
class IntegrityReport:
    """Dort probun toplu sonucu."""

    gnubg: str
    probes: list[ProbeResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.probes) and all(p.ok for p in self.probes)

    @property
    def failed(self) -> list[str]:
        return [p.name for p in self.probes if not p.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gnubg": self.gnubg,
            "ok": self.ok,
            "failed": self.failed,
            "probes": [p.to_dict() for p in self.probes],
        }


# ----------------------------------------------------------------------
# Prob 1 -- tahta donusumu
# ----------------------------------------------------------------------


def _position_id(text: str) -> str | None:
    """Ciktidaki **son** ``Position ID`` (ilk olan ``new game`` echo'sudur)."""
    ids = _POSITION_ID_RE.findall(text)
    return ids[-1] if ids else None


def probe_board_conversion(session: "gnubg_er.GnubgSession") -> ProbeResult:
    """Tahta donusumunu bagimsiz referanslarla dogrular (F6-31 avcisi)."""
    evidence: dict[str, Any] = {}
    problems: list[str] = []

    table, _ = session.eval_position(list(DOC_BOARD), 1)
    doc_equity = table["static"]
    evidence["docBoardEquity"] = round(doc_equity, 6)
    evidence["docBoardExpected"] = DOC_BOARD_EXPECTED
    if abs(doc_equity - DOC_BOARD_EXPECTED) > DOC_BOARD_TOLERANCE:
        problems.append(
            "referans tahta equity %.4f, beklenen %.4f (+-%.2f)"
            % (doc_equity, DOC_BOARD_EXPECTED, DOC_BOARD_TOLERANCE)
        )

    # Isaret-ters ve aynalanmis donusumler **farkli** sonuc vermeli; aksi halde prob
    # hicbir seyi ayirt etmiyor demektir.
    flipped, _ = session.eval_position(list(DOC_BOARD_SIGN_FLIPPED), 1)
    mirrored, _ = session.eval_position(list(DOC_BOARD_MIRRORED), 1)
    evidence["signFlippedEquity"] = round(flipped["static"], 6)
    evidence["mirroredEquity"] = round(mirrored["static"], 6)
    if abs(flipped["static"] - doc_equity) <= DOC_BOARD_TOLERANCE:
        problems.append("isaret-ters donusum ayni equity'yi veriyor: prob ayirt edici degil")
    if abs(mirrored["static"] - doc_equity) <= DOC_BOARD_TOLERANCE:
        problems.append("aynalanmis donusum ayni equity'yi veriyor: prob ayirt edici degil")

    start_table, start_raw = session.eval_position(list(refgen.START_BOARD), 1)
    start_id = _position_id(start_raw)
    evidence["startPositionId"] = start_id
    evidence["startPositionIdExpected"] = START_POSITION_ID
    if start_id != START_POSITION_ID:
        problems.append(
            "baslangic Position ID %r, beklenen %r" % (start_id, START_POSITION_ID)
        )

    start_pips = gnubg_er.parse_pipcount(start_raw)
    evidence["startPips"] = list(start_pips) if start_pips else None
    if start_pips != (START_PIP, START_PIP):
        problems.append("baslangic pip sayisi %r, beklenen (%d, %d)" % (start_pips, START_PIP, START_PIP))

    bar_table, bar_raw = session.eval_position(list(BAR_BOARD), 1)
    bar_pips = gnubg_er.parse_pipcount(bar_raw)
    evidence["barPips"] = list(bar_pips) if bar_pips else None
    if bar_pips != (BAR_PIP, BAR_PIP):
        problems.append("bar pip sayisi %r, beklenen (%d, %d)" % (bar_pips, BAR_PIP, BAR_PIP))

    detail = "ok" if not problems else "; ".join(problems)
    return ProbeResult(PROBE_BOARD, not problems, detail, evidence)


# ----------------------------------------------------------------------
# Prob 2 -- sutun secimi (gnubg gerektirmez)
# ----------------------------------------------------------------------

#: (tablo, plies, beklenen) -- beklenen ``None`` ise ``ValueError`` beklenir.
COLUMN_CASES: tuple[tuple[dict[str, float], int, float | None], ...] = (
    ({"static": 0.1, "1": 0.2, "2": 0.3}, 0, 0.1),
    ({"static": 0.1, "1": 0.2, "2": 0.3}, 1, 0.2),
    ({"static": 0.1, "1": 0.2, "2": 0.3}, 2, 0.3),
    # F6-32: eski kod ``static``'i en derin sanip seciyordu. ``static`` en buyuk
    # deger oldugunda bile 2-ply sütunu secilmelidir.
    ({"static": 0.9, "1": 0.2, "2": 0.3}, 2, 0.3),
    ({"static": 0.9, "1": 0.2, "2": 0.3}, 0, 0.9),
    # Derinlik tabloda yoksa sessizce dusmek yasak.
    ({"static": 0.1, "1": 0.2, "2": 0.3}, 3, None),
    ({"static": 0.1, "1": 0.2, "2": 0.3}, 4, None),
    ({"static": 0.1, "1": 0.2}, 2, None),
    ({"static": 0.1}, 1, None),
    ({}, 0, None),
)


def probe_column_selection() -> ProbeResult:
    """``_equity_at`` dogru sutunu seciyor mu, yanlista hata veriyor mu."""
    evidence: dict[str, Any] = {"cases": []}
    problems: list[str] = []

    for table, plies, expected in COLUMN_CASES:
        row: dict[str, Any] = {"table": dict(table), "plies": plies, "expected": expected}
        try:
            got = gnubg_er._equity_at(table, plies)
        except ValueError as exc:
            row["raised"] = "ValueError"
            row["ok"] = expected is None
            if expected is not None:
                problems.append(
                    "plies=%d icin %.3f beklendi, ValueError: %s" % (plies, expected, exc)
                )
        else:
            row["got"] = got
            row["ok"] = expected is not None and abs(got - expected) < 1e-12
            if expected is None:
                problems.append("plies=%d icin ValueError beklendi, %.3f alindi" % (plies, got))
            elif abs(got - expected) >= 1e-12:
                problems.append("plies=%d icin %.3f beklendi, %.3f alindi" % (plies, expected, got))
        evidence["cases"].append(row)

    evidence["maxEvalPlies"] = gnubg_er.MAX_EVAL_PLIES
    if gnubg_er.MAX_EVAL_PLIES != 2:
        problems.append("MAX_EVAL_PLIES %d, beklenen 2" % gnubg_er.MAX_EVAL_PLIES)

    detail = "ok" if not problems else "; ".join(problems)
    return ProbeResult(PROBE_COLUMN, not problems, detail, evidence)


# ----------------------------------------------------------------------
# Prob 3 -- perspektif
# ----------------------------------------------------------------------


def probe_perspective(
    session: "gnubg_er.GnubgSession",
    boards: Sequence[Sequence[int]] | None = None,
) -> ProbeResult:
    """Ayni tahta iki perspektiften degerlendirilir; isaret tutarli olmali.

    gnubg ``eval`` equity'yi **sirada olan oyuncunun** bakis acisindan basar. Bu yuzden

    * simetrik bir tahtada iki perspektif **ayni** degeri vermelidir (ayni oyuncu
      avantaji), ve
    * asimetrik bir tahtada iki perspektif **zit isaretli** olmalidir.

    Buyukluk farki normaldir: gnubg'nin agi antisimetrik degildir (F6-29).
    """
    evidence: dict[str, Any] = {"cases": []}
    problems: list[str] = []

    symmetric = list(refgen.START_BOARD)
    sym_white, _ = session.eval_position(symmetric, 1)
    sym_black, _ = session.eval_position(symmetric, -1)
    sym_delta = abs(sym_white["static"] - sym_black["static"])
    evidence["cases"].append(
        {
            "name": "start-symmetric",
            "whitePerspective": round(sym_white["static"], 6),
            "blackPerspective": round(sym_black["static"], 6),
            "delta": round(sym_delta, 6),
            "kind": "symmetric",
        }
    )
    if sym_delta > PERSPECTIVE_TOLERANCE:
        problems.append(
            "simetrik tahtada perspektifler farkli: %.4f vs %.4f"
            % (sym_white["static"], sym_black["static"])
        )

    if boards is None:
        boards = _asymmetric_boards()
    for index, board in enumerate(boards):
        white, _ = session.eval_position(list(board), 1)
        black, _ = session.eval_position(list(board), -1)
        product = white["static"] * black["static"]
        evidence["cases"].append(
            {
                "name": "asymmetric-%02d" % index,
                "whitePerspective": round(white["static"], 6),
                "blackPerspective": round(black["static"], 6),
                "product": round(product, 6),
                "kind": "asymmetric",
            }
        )
        if product > 0:
            problems.append(
                "asimetrik tahtada isaretler ayni (%.4f vs %.4f)"
                % (white["static"], black["static"])
            )

    detail = "ok" if not problems else "; ".join(problems)
    return ProbeResult(PROBE_PERSPECTIVE, not problems, detail, evidence)


def _asymmetric_boards() -> list[list[int]]:
    """Kumeden acikca asimetrik iki tahta (``random-002``, ``random-003``)."""
    cases = gnubg_er.load_cases(gnubg_er.DEFAULT_CASES)
    usable, _ = gnubg_er.split_cases(cases)
    wanted = ("random-002", "random-003")
    picked = [list(c["board"]) for c in usable if c["name"] in wanted]
    if len(picked) < len(wanted):
        raise IntegrityError(
            "asimetrik referans tahtalar bulunamadi: %s" % (wanted,)
        )
    return picked


# ----------------------------------------------------------------------
# Prob 4 -- pip sayisi
# ----------------------------------------------------------------------


def probe_pip_count(
    session: "gnubg_er.GnubgSession",
    boards: Sequence[Sequence[int]] | None = None,
) -> ProbeResult:
    """``show pipcount`` bagimsiz hesapla karsilastirilir."""
    evidence: dict[str, Any] = {"cases": []}
    problems: list[str] = []

    if boards is None:
        cases = gnubg_er.load_cases(gnubg_er.DEFAULT_CASES)
        usable, _ = gnubg_er.split_cases(cases)
        boards = [list(c["board"]) for c in usable[:PIP_SAMPLE]]

    for index, board in enumerate(boards):
        _, raw = session.eval_position(list(board), 1)
        pips = gnubg_er.parse_pipcount(raw)
        expected = (gnubg_er.pip_count(board, -1), gnubg_er.pip_count(board, 1))
        ok = pips == expected
        evidence["cases"].append(
            {
                "index": index,
                "gnubg": list(pips) if pips else None,
                "expected": list(expected),
                "ok": ok,
            }
        )
        if not ok:
            problems.append("tahta %d: gnubg %r, beklenen %r" % (index, pips, expected))

    evidence["checked"] = len(boards)
    detail = "ok" if not problems else "; ".join(problems[:5])
    return ProbeResult(PROBE_PIP, not problems, detail, evidence)


# ----------------------------------------------------------------------
# Toplu kosum
# ----------------------------------------------------------------------


def run_all(
    exe: Path | str | None = None,
    *,
    plies: int = 0,
    timeout: int = 300,
    boards: Sequence[Sequence[int]] | None = None,
) -> IntegrityReport:
    """Dort probu sirayla kosar ve raporu doner."""
    resolved = gnubg_er.find_gnubg(exe)
    if resolved is None:
        raise IntegrityError(
            "gnubg-cli bulunamadi; GNUBG_CLI ortam degiskenini ayarlayin"
        )
    session = gnubg_er.GnubgSession(resolved, plies=plies, timeout=timeout)

    report = IntegrityReport(gnubg=str(resolved))
    report.probes.append(probe_board_conversion(session))
    report.probes.append(probe_column_selection())
    report.probes.append(probe_perspective(session, boards))
    report.probes.append(probe_pip_count(session, boards))
    return report


def assert_integrity(report: IntegrityReport) -> None:
    """Rapor temiz degilse ``IntegrityError`` atar."""
    if not report.ok:
        raise IntegrityError(
            "olcum butunlugu probu basarisiz: %s" % ", ".join(report.failed)
        )


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def build_markdown(report: IntegrityReport) -> str:
    lines = [
        "# Olcum butunlugu -- dort bagimsiz prob (Faz 7 Bolum 4.3, Test 93)",
        "",
        "gnubg: `%s`" % report.gnubg,
        "",
        "Genel sonuc: **%s**" % ("GECTI" if report.ok else "BASARISIZ"),
        "",
        "| Prob | Sonuc | Ayrinti |",
        "|---|---|---|",
    ]
    for probe in report.probes:
        lines.append(
            "| %s | %s | %s |"
            % (probe.label, "gecti" if probe.ok else "**kaldi**", probe.detail)
        )
    lines.append("")
    for probe in report.probes:
        lines.append("## %s" % probe.label)
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(probe.evidence, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_json(report: IntegrityReport, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Faz 7 Bolum 4.3 -- olcum butunlugu probu (Test 93)"
    )
    parser.add_argument("--gnubg", default=None, help="gnubg-cli yolu")
    parser.add_argument("--plies", type=int, default=0, help="eval derinligi (0/1/2)")
    parser.add_argument("--timeout", type=int, default=300, help="gnubg zaman asimi (s)")
    parser.add_argument("--json", default=None, help="JSON rapor yolu")
    parser.add_argument("--markdown", default=None, help="Markdown rapor yolu")
    parser.add_argument("--quiet", action="store_true", help="yalnizca ozet yaz")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_all(args.gnubg, plies=args.plies, timeout=args.timeout)
    except IntegrityError as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        write_json(report, args.json)
    if args.markdown:
        target = Path(args.markdown)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_markdown(report) + "\n", encoding="utf-8")

    if not args.quiet:
        for probe in report.probes:
            print("%-18s %s  %s" % (probe.label, "OK  " if probe.ok else "FAIL", probe.detail))
    print("genel: %s" % ("GECTI" if report.ok else "BASARISIZ"))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
