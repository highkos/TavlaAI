"""K5: iki ``er_paths`` raporunun karsilastirilmasi (Test 299-301)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import er_paths  # noqa: E402


def _report(
    *,
    model: str = "m.onnx",
    case_count: int = 1000,
    corpus: str = "v2",
    split: str = "all",
    plies: int = 2,
    means: dict[str, tuple[float, float]] | None = None,
) -> dict:
    means = means or {
        "policy": (0.02, 0.002),
        "value": (0.04, 0.003),
        "search1": (0.02, 0.0015),
    }
    return {
        "model": model,
        "referee": {"command": "eval", "column": str(plies), "plies": plies, "prob": "equity"},
        "caseCount": case_count,
        "corpus": corpus,
        "split": split,
        "paths": {
            p: {"path": p, "mean": m, "standardError": se, "count": case_count}
            for p, (m, se) in means.items()
        },
    }


def test_299_compare_reports_rows_and_z():
    """Fark ve iki ornekli z dogru hesaplanir; esik |z| >= 1.96."""
    control = _report(means={"value": (0.040, 0.003), "search1": (0.020, 0.0015)})
    treatment = _report(means={"value": (0.030, 0.003), "search1": (0.020, 0.0015)})
    result = er_paths.compare_reports(control, treatment)
    rows = {r["path"]: r for r in result["rows"]}
    assert set(rows) == {"value", "search1"}
    assert rows["value"]["diff"] == pytest.approx(-0.010)
    assert rows["value"]["se"] == pytest.approx((0.003**2 + 0.003**2) ** 0.5)
    assert rows["value"]["z"] == pytest.approx(-0.010 / (0.003 * 2**0.5))
    assert rows["value"]["significant"] is True
    assert rows["search1"]["diff"] == pytest.approx(0.0)
    assert rows["search1"]["significant"] is False
    assert result["anySignificant"] is True


def test_300_compare_reports_rejects_mismatched_design():
    """Korpus/vaka/plies farki karsilastirmayi gecersiz kilar (Kural 7)."""
    base = _report()
    with pytest.raises(er_paths.CompareError):
        er_paths.compare_reports(base, _report(case_count=999))
    with pytest.raises(er_paths.CompareError):
        er_paths.compare_reports(base, _report(corpus="legacy-v1"))
    with pytest.raises(er_paths.CompareError):
        er_paths.compare_reports(base, _report(split="val"))
    with pytest.raises(er_paths.CompareError):
        er_paths.compare_reports(base, _report(plies=0))
    # Ortak yol yoksa karsilastirma anlamsizdir; kismi ortusme serbesttir.
    with pytest.raises(er_paths.CompareError):
        er_paths.compare_reports(
            _report(means={"policy": (0.02, 0.002)}),
            _report(means={"value": (0.04, 0.003)}),
        )


def test_301_compare_markdown_reports_no_effect():
    """Anlamli fark yoksa markdown bunu acikca soyler."""
    control = _report(means={"value": (0.040, 0.003)})
    treatment = _report(means={"value": (0.0401, 0.003)})
    result = er_paths.compare_reports(
        control, treatment, label_control="KL=0", label_treatment="KL=0,5"
    )
    md = er_paths.build_compare_markdown(result)
    assert "KL=0" in md and "KL=0,5" in md
    assert "| `value` | 0.040000 | 0.040100 |" in md
    assert "Hicbir yol anlamli degismedi" in md
    assert result["anySignificant"] is False
