"""Belge tutarliligi testleri.

Belgelerdeki sayisal iddialarin ve capraz referanslarin gercekle uyusmasini dogrular.
Amac, `ARCHITECTURE.md` §18/§34 ve `ASSUMPTIONS.md` F4-24'te bulunan belge kaymalarinin
(eski test sayilari, "gnubg kurulu degil" ifadesi) tekrar olusmasini engellemektir.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASES = REPO_ROOT / "PHASES.md"
ARCHITECTURE = REPO_ROOT / "ARCHITECTURE.md"
ASSUMPTIONS = REPO_ROOT / "ASSUMPTIONS.md"
STAGE_D_REPORT = REPO_ROOT / "ml" / "artifacts" / "stage_d_report.md"

#: (belge, aciklama) — test sayilarinin tutarli olmasi gereken belgeler.
COUNT_DOCS = [
    (PHASES, "PHASES.md"),
    (ARCHITECTURE, "ARCHITECTURE.md"),
    (STAGE_D_REPORT, "ml/artifacts/stage_d_report.md"),
]

#: Belgenin iddia ettigi test sayilari (kaynak: gercek kosular).
EXPECTED_COUNTS = {
    "pytest": 1555,
    "inference": 100,
    "core": 297,
    "ui": 88,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _backticked_paths(text: str) -> set[str]:
    """Metindeki ters-tirnakli, depo-goreli **kalici** dosya yollarini dondurur.

    Yalnizca depoya islenmis yollar denetlenir: kok `.md` dosyalari, `ml/artifacts/`,
    `ml/tests/`, `ml/*.py`, `tools/` ve `Backgammon.*/` altindaki kaynak/veri dosyalari.
    `ml/runs/` (kosu ciktilari) ve yapilandirma varsayilanlari kapsam disidir.
    """
    tokens = set(re.findall(r"`([^`\n]+)`", text))
    out: set[str] = set()
    for token in tokens:
        if any(ch in token for ch in "{}*<>| %"):
            continue
        if not _is_committed_path(token):
            continue
        out.add(token)
    return out


_COMMITTED_PREFIXES = (
    "ml/artifacts/",
    "ml/tests/",
    "tools/",
    "Backgammon.Tests/ReferenceData/",
)

#: Depo kokundeki belgeler (yol ayirici icermez, ayrica denetlenir).
ROOT_DOCS = ("ARCHITECTURE.md", "ASSUMPTIONS.md", "PHASES.md", "SHARD_FORMAT.md")


def _is_committed_path(token: str) -> bool:
    """Yalnizca depo-goreli (en az bir '/' iceren) kalici yollari kabul eder.

    Ciplak dosya adlari (`train.py`, `pool.json`) kisayol oldugu icin atlanir.
    """
    if "/" not in token:
        return False
    if token.startswith(_COMMITTED_PREFIXES):
        return True
    if token.startswith("ml/") and token.count("/") == 1 and token.endswith(".py"):
        return True
    if token.startswith("Backgammon.") and token.endswith(".cs"):
        return True
    return False


@pytest.mark.parametrize("doc", [PHASES, ARCHITECTURE, ASSUMPTIONS, STAGE_D_REPORT],
                         ids=lambda p: p.name)
def test_referenced_paths_exist(doc: Path) -> None:
    """Belgede ters-tirnakla anilan her depo-goreli yol gercekten var olmali."""
    missing = sorted(p for p in _backticked_paths(_read(doc)) if not (REPO_ROOT / p).exists())
    assert not missing, f"{doc.name} var olmayan yollara referans veriyor: {missing}"


@pytest.mark.parametrize("name", ROOT_DOCS)
def test_root_documents_exist(name: str) -> None:
    """Belge haritasinda anilan kok belgeleri mevcut olmali."""
    assert (REPO_ROOT / name).is_file(), f"{name} depo kokunde yok"


@pytest.mark.parametrize("doc,label", COUNT_DOCS, ids=[label for _, label in COUNT_DOCS])
def test_test_counts_are_consistent(doc: Path, label: str) -> None:
    """Uc belge de ayni test sayilarini yazmali (kayma korumasi)."""
    text = _read(doc)
    for name, count in EXPECTED_COUNTS.items():
        pattern = rf"{count}\s*/\s*{count}"
        assert re.search(pattern, text), (
            f"{label}: {name} test sayisi '{count}/{count}' olarak bulunamadi"
        )


def test_phases_total_matches_sum() -> None:
    """PHASES.md §6'daki toplam, uc paketin toplamina esit olmali."""
    text = _read(PHASES)
    total = sum(EXPECTED_COUNTS.values())
    assert re.search(rf"\*\*{total}\*\*", text), (
        f"PHASES.md toplam test sayisi {total} olarak bulunamadi"
    )


def test_phases_section_6_is_test_status() -> None:
    """ARCHITECTURE.md §18/§34 'PHASES.md §6' diye referans veriyor; basligi tutmali."""
    text = _read(PHASES)
    match = re.search(r"^## 6\. (.+)$", text, re.MULTILINE)
    assert match, "PHASES.md icinde '## 6.' basligi yok"
    assert "Test" in match.group(1), (
        f"PHASES.md §6 basligi test durumu degil: {match.group(1)!r}"
    )


def test_architecture_section_numbers_unique_and_ascending() -> None:
    """ARCHITECTURE.md bolum numaralari tekrar etmemeli ve artan sirada olmali."""
    numbers = [int(n) for n in re.findall(r"^## (\d+)\.", _read(ARCHITECTURE), re.MULTILINE)]
    assert numbers, "ARCHITECTURE.md icinde numarali bolum bulunamadi"
    assert numbers == sorted(numbers), f"ARCHITECTURE.md bolum sirasi bozuk: {numbers}"
    duplicates = {n for n in numbers if numbers.count(n) > 1}
    assert not duplicates, f"ARCHITECTURE.md tekrar eden bolum numaralari: {sorted(duplicates)}"


def test_architecture_subsection_parents_exist() -> None:
    """Her '### N.M' alt bolumu icin '## N.' ust bolumu bulunmali."""
    text = _read(ARCHITECTURE)
    parents = {int(n) for n in re.findall(r"^## (\d+)\.", text, re.MULTILINE)}
    orphans = sorted(
        {int(n) for n in re.findall(r"^### (\d+)\.\d+", text, re.MULTILINE)} - parents
    )
    assert not orphans, f"ARCHITECTURE.md sahipsiz alt bolumler: {orphans}"


def test_architecture_subsections_follow_their_parent() -> None:
    """'### N.M' alt bolumleri, '## N.' ile bir sonraki '## ' arasinda yer almali."""
    text = _read(ARCHITECTURE)
    current: int | None = None
    misplaced: list[str] = []
    for line in text.splitlines():
        top = re.match(r"^## (\d+)\.", line)
        if top:
            current = int(top.group(1))
            continue
        sub = re.match(r"^### (\d+)\.\d+", line)
        if sub and int(sub.group(1)) != current:
            misplaced.append(line.strip())
    assert not misplaced, f"ARCHITECTURE.md yanlis yerde alt bolumler: {misplaced}"


def test_assumptions_ids_are_unique() -> None:
    """Karar kimlikleri (B-/C-/D-/E-/F2-/F3-/F4-/F5-/F6-) benzersiz olmali."""
    text = _read(ASSUMPTIONS)
    ids = re.findall(r"^#{2,4} ((?:F2|F3|F4|F5|F6|[BCDE])-\d+)", text, re.MULTILINE)
    assert ids, "ASSUMPTIONS.md icinde karar kimligi bulunamadi"
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"ASSUMPTIONS.md tekrar eden karar kimlikleri: {duplicates}"


def test_assumptions_f6_ids_are_ascending() -> None:
    """F6 kararlari numara sirasinda olmali (ekleme sirasini korur)."""
    text = _read(ASSUMPTIONS)
    f6 = [int(n) for n in re.findall(r"^#{2,4} F6-(\d+)", text, re.MULTILINE)]
    assert f6, "ASSUMPTIONS.md icinde F6 karari bulunamadi"
    assert f6 == sorted(f6), f"ASSUMPTIONS.md F6 sirasi bozuk: {f6}"


def test_assumptions_f4_ids_are_ascending() -> None:
    """F4 kararlari numara sirasinda olmali (ekleme sirasini korur)."""
    text = _read(ASSUMPTIONS)
    f4 = [int(n) for n in re.findall(r"^#{2,4} F4-(\d+)", text, re.MULTILINE)]
    assert f4, "ASSUMPTIONS.md icinde F4 karari bulunamadi"
    assert f4 == sorted(f4), f"ASSUMPTIONS.md F4 sirasi bozuk: {f4}"


def test_gnubg_claim_is_current() -> None:
    """F4-24 artik 'gnubg kurulu degil' dememeli; olcum tamamlanmis olmali."""
    text = _read(ASSUMPTIONS)
    block = re.search(r"^#{2,4} F4-24\b.*?(?=^#{2,4} F4-25\b)", text, re.MULTILINE | re.DOTALL)
    assert block, "ASSUMPTIONS.md icinde F4-24 blogu bulunamadi"
    body = block.group(0)
    assert "gnubg ölçümü tamamlandı" in body or "gnubg olcumu tamamlandi" in body, (
        "F4-24 gnubg olcumunun tamamlandigini belirtmiyor"
    )
    assert "gnubg kurulu değildir" not in body, (
        "F4-24 hala 'gnubg kurulu degildir' diyor (artik yanlis)"
    )


def test_stage_d_acceptance_row_18_is_done() -> None:
    """Aşama D kabul tablosunda gnubg ER satiri tamamlanmis olmali."""
    text = _read(STAGE_D_REPORT)
    row = re.search(r"^\|\s*gnubg ER\s*\|.*$", text, re.MULTILINE)
    assert row, "stage_d_report.md kabul tablosunda 'gnubg ER' satiri yok"
    assert "✅" in row.group(0), f"gnubg ER satiri tamamlanmis degil: {row.group(0)}"
