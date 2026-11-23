"""gnubg rollout hakemi - Faz 7-R R-F madde 2.

R-F madde 2, 200-300 zor pozisyon icin gnubg **rollout** (varyans azaltmali,
>=1296 deneme) ile bir dogruluk referansi ister ve hakem ER'sinin rollout'a
gore sapmasini (ER cozunurluk tabani) raporlar.

**Olculen durum: bu makinede rollout hakemi kullanilamaz.** Kanit:

* ``gnubg-cli.exe`` 1.08.003-mingw. ``rollout`` komutu calisir ve
  ``Rollout done. Printing final results.`` satirini basar, ama **ardindan
  equity satiri yazmaz** (``-t``, ``-t -d``, ``-c``, ``-p`` kiplerinde ayni;
  ``set rollout cubeful off`` ve ``set cube use off`` ile de ayni).
* ``rollout`` sonrasinda ``eval`` cagrisi **statik** deger dondurur; rollout
  sonucu pozisyonun degerlendirmesine yazilmaz.
* gnubg Python API'sinde (``-p``) ``rollout`` fonksiyonu **yoktur**:
  ``dir(gnubg)`` -> ``rolloutcontext`` var, ``rollout`` yok.
* ``gnubg-cli.exe --help`` rollout'a ozel bir secenek listelemez.

Bu yuzden modul **sifir uydurmaz** (Kural 6): rollout satiri ``olculemez``
isaretlenir ve gerekcesi yazilir. Ayni buyuklugun (ER cozunurluk tabani)
olculebilir karsiligi ``gnubg_ladder.py --deep`` ile alinir: 2-ply hakemin
**4-ply ``hint``** hakemine gore ER'si.

Maliyet de olculdu: 36 denemelik bir rollout tek afterstate icin ~30 s
(0-ply chequerplay, yogun CPU'da); 1296 deneme ~18 dakika. 200 pozisyon x
2 aday = 400 rollout -> ~120 saat tek cekirdek. Yani olcum yalnizca ciktisi
degil, maliyeti nedeniyle de bu makinede yapilamaz.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import gnubg_er  # noqa: E402

ROLLOUT_VERSION = 1
ROLLOUT_PATH = "ml/artifacts/gnubg_rollout.json"
ROLLOUT_MD_PATH = "ml/artifacts/gnubg_rollout.md"

#: R-F madde 2'nin istedigi en az deneme sayisi.
REQUIRED_TRIALS = 1296

#: gnubg rollout'un sonuc bastigini gosteren isaret (tek basina yetmez).
_DONE_MARKER = "Rollout done. Printing final results."

#: Rollout sonucu basildiginda gorunen equity satiri.
_EQUITY_RE = re.compile(r"(?i)cubeless\s+equity|^equity", re.MULTILINE)

UNMEASURABLE_REASON = (
    "gnubg 1.08.003-mingw 'rollout' komutu calisir ama equity basmaz; "
    "'eval' rollout sonucunu dondurmez; Python API'sinde rollout fonksiyonu "
    "yoktur. R-F madde 2 uyarinca satir 'olculemez' isaretlendi."
)


class RolloutError(RuntimeError):
    """Rollout olcumu yapilamadi."""


def parse_rollout_equity(text: str) -> float | None:
    """Rollout ciktisindan cubeless equity'yi cikarir; yoksa ``None``.

    ``None`` donmesi **hata degil**, olculen durumdur: bu gnubg derlemesi
    rollout sonucunu basmiyor.
    """
    if _DONE_MARKER not in text:
        return None
    tail = text.split(_DONE_MARKER, 1)[1]
    match = _EQUITY_RE.search(tail)
    if not match:
        return None
    numbers = re.findall(r"[-+]?\d+[.,]\d+", tail[match.end() : match.end() + 200])
    if not numbers:
        return None
    return gnubg_er.parse_number(numbers[0])


def probe_rollout(
    exe: Path,
    *,
    trials: int = 36,
    timeout: int = 600,
) -> dict[str, Any]:
    """Rollout hakeminin bu derlemede sonuc verip vermedigini olcer.

    Bos tahtada (``new game``) tek bir rollout calistirir. Sonuc equity'si
    okunamazsa ``measurable=False`` ve gerekce doner.
    """
    session = gnubg_er.GnubgSession(exe, plies=2, timeout=timeout)
    commands = [
        "set cube use off",
        "new game",
        "set rollout trials %d" % int(trials),
        "set rollout chequerplay plies 0",
        "rollout",
        "show pipcount",
        "quit",
    ]
    text = session.run(commands)
    equity = parse_rollout_equity(text)
    return {
        "gnubg": str(exe),
        "trials": int(trials),
        "doneMarkerSeen": _DONE_MARKER in text,
        "equity": equity,
        "measurable": equity is not None,
        "reason": None if equity is not None else UNMEASURABLE_REASON,
    }


def build_report(probe: dict[str, Any], *, positions: int, candidates: int) -> dict[str, Any]:
    """R-F madde 2 raporu: rollout hakemi + maliyet tahmini."""
    return {
        "rolloutVersion": ROLLOUT_VERSION,
        "requiredTrials": REQUIRED_TRIALS,
        "positions": int(positions),
        "candidatesPerPosition": int(candidates),
        "probe": probe,
        "measurable": bool(probe.get("measurable")),
        "reason": probe.get("reason"),
        "substitute": {
            "module": "ml/gnubg_ladder.py --deep",
            "description": (
                "ER cozunurluk tabaninin olculebilir karsiligi: 2-ply hakemin "
                "4-ply `hint` hakemine gore ER'si (R-F madde 1)."
            ),
        },
        "notes": [
            "Rollout sonucu okunamadigi icin sifir uydurulmadi (Kural 6).",
            "Maliyet: 36 deneme ~30 s (0-ply chequerplay, yogun CPU); 1296 deneme "
            "~18 dk; 200 pozisyon x 2 aday = 400 rollout -> ~120 saat tek cekirdek.",
            "Ayni buyukluk `gnubg_ladder.py --deep` ile olculur.",
        ],
    }


def build_markdown(report: dict[str, Any]) -> str:
    probe = report["probe"]
    lines = [
        "# Faz 7-R - gnubg rollout hakemi (R-F madde 2)",
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| gnubg | `%s` |" % probe["gnubg"],
        "| Istenen deneme | %d |" % report["requiredTrials"],
        "| Denenen deneme | %d |" % probe["trials"],
        "| `Rollout done` satiri | %s |" % ("var" if probe["doneMarkerSeen"] else "yok"),
        "| Equity okundu | %s |" % ("evet" if probe["measurable"] else "**hayir**"),
        "| Pozisyon | %d |" % report["positions"],
        "| Aday/pozisyon | %d |" % report["candidatesPerPosition"],
        "| Durum | **%s** |" % ("olculdu" if report["measurable"] else "olculemez"),
        "",
    ]
    if not report["measurable"]:
        lines.append("**Gerekce.** %s" % report["reason"])
        lines.append("")
        lines.append(
            "**Yerine koyulan olcum.** %s" % report["substitute"]["description"]
        )
        lines.append("")
    lines.append("## Notlar")
    lines.append("")
    for note in report["notes"]:
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnubg_rollout",
        description="gnubg rollout hakemi - Faz 7-R R-F madde 2",
    )
    parser.add_argument("--gnubg", default=None)
    parser.add_argument("--trials", type=int, default=36)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--positions", type=int, default=200)
    parser.add_argument("--candidates", type=int, default=2)
    parser.add_argument("--out", default=ROLLOUT_PATH)
    parser.add_argument("--markdown", default=ROLLOUT_MD_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exe = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()
    if exe is None:
        print("gnubg-cli bulunamadi", file=sys.stderr)
        return 2
    probe = probe_rollout(exe, trials=args.trials, timeout=args.timeout)
    report = build_report(probe, positions=args.positions, candidates=args.candidates)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")
    print(build_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
