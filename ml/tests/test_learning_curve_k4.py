"""K4: ogrenme egrisi fit proseduru duzeltmeleri (Test 218-224).

Kullanicinin ``tespitler.md`` K4 maddesi:

* ``c`` icin guven araligi yoktu -> kume bootstrap GA'si eklendi.
* ``c >= 0`` kisiti zaten vardi; testle kilitlendi.
* Korpus raporda yazilmiyordu -> ``CurveReport.corpus`` + Markdown bolumu.
* 64x noktasi yoktu -> ``CURVE_MULTIPLIERS`` 64'u icerir.
* Eslesterilmis (paired) once/sonra karsilastirmasi yoktu -> eklendi.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import learning_curve as lc  # noqa: E402


def _point(mult: int, positions: int, losses, game_ids=None) -> lc.CurvePoint:
    return lc.CurvePoint(
        multiplier=mult,
        positions=positions,
        losses={"policy": list(losses)},
        game_ids={"policy": list(game_ids)} if game_ids else {},
    )


def _synthetic_curve(
    *, floor: float = 0.01, a: float = 0.3, b: float = 0.5, noise: float = 0.0, seed: int = 3
) -> list[lc.CurvePoint]:
    """``ER = a*N^-b + floor`` ureten noktalar (oyun kumeli)."""
    rng = np.random.default_rng(seed)
    points: list[lc.CurvePoint] = []
    for mult in (1, 2, 4, 8, 16, 32, 64):
        n = 165 * mult
        value = a * n ** (-b) + floor
        losses = value + rng.normal(scale=noise, size=n) if noise > 0 else np.full(n, value)
        ids = ["g%03d" % (i % 40) for i in range(n)]
        points.append(_point(mult, n, losses, ids))
    return points


def test_218_multipliers_include_64x():
    """K4: egri 64x'e uzatilmali (>= 10 560 pozisyon)."""
    assert 64 in lc.CURVE_MULTIPLIERS
    assert max(lc.CURVE_MULTIPLIERS) == 64
    assert 165 * 64 >= 10560


def test_219_saturation_floor_ci_brackets_truth():
    """K4: ``c`` icin kume bootstrap GA'si gercek tabani kapsamali."""
    points = _synthetic_curve(floor=0.01, noise=0.002)
    entry = lc.fit_saturation(points, path="policy", resamples=400, seed=11)
    assert entry["n"] == 7
    assert entry["resamples"] > 0
    assert np.isfinite(entry["c"])
    assert np.isfinite(entry["cCiLow"]) and np.isfinite(entry["cCiHigh"])
    assert entry["cCiLow"] <= entry["c"] <= entry["cCiHigh"]
    assert entry["cCiLow"] <= 0.01 <= entry["cCiHigh"]


def test_220_saturation_floor_ci_disabled_when_resamples_zero():
    """``resamples=0`` eski davranisi korur: GA yok, nan."""
    points = _synthetic_curve(floor=0.01)
    entry = lc.fit_saturation(points, path="policy", resamples=0)
    assert entry["resamples"] == 0
    assert np.isnan(entry["cCiLow"]) and np.isnan(entry["cCiHigh"])
    assert np.isfinite(entry["c"])


def test_221_saturation_floor_never_negative():
    """K4: ``c >= 0`` kisiti korunur (taban negatif olamaz)."""
    # Gürültülü, tabani sifira yakin veri: fit negatife kacmamali.
    rng = np.random.default_rng(5)
    points = []
    for mult in (1, 2, 4, 8):
        n = 165 * mult
        losses = np.abs(rng.normal(scale=0.02, size=n))
        points.append(_point(mult, n, losses, ["g%03d" % (i % 20) for i in range(n)]))
    entry = lc.fit_saturation(points, path="policy", resamples=100, seed=2)
    assert np.isfinite(entry["c"])
    assert entry["c"] >= 0.0
    if np.isfinite(entry["cCiLow"]):
        assert entry["cCiLow"] >= 0.0


def test_222_corpus_is_reported_in_markdown():
    """K4: korpus raporda acikca yazilmali."""
    report = lc.CurveReport(points=_synthetic_curve(floor=0.01))
    report.corpus = {"havuz": "curve_pool_400.npz", "oyun": "400", "plies": "2"}
    text = lc.build_markdown(report)
    assert "### 1.1 Korpus" in text
    assert "curve_pool_400.npz" in text
    assert "| `plies` | 2 |" in text


def test_223_paired_comparison_detects_improvement():
    """K4: eslestirilmis fark, ayni oyunlar uzerinde olculur."""
    before = lc.CurveReport(points=_synthetic_curve(floor=0.02, seed=1))
    after = lc.CurveReport(points=_synthetic_curve(floor=0.01, seed=1))
    paired = lc.paired_curve_comparison(before, after, resamples=500, seed=7)
    assert paired["clusters"] > 0
    assert paired["meanDiff"] < 0.0, "sonra daha iyi olmali (negatif fark)"
    assert paired["ciHigh"] < 0.0
    assert paired["improved"] is True
    assert len(paired["points"]) == len(lc.CURVE_MULTIPLIERS)


def test_224_paired_comparison_no_change_is_not_significant():
    """Ayni egri kendisiyle karsilastirilirsa fark sifir; 'iyilesme' yok."""
    report = lc.CurveReport(points=_synthetic_curve(floor=0.01, seed=4))
    paired = lc.paired_curve_comparison(report, report, resamples=300, seed=9)
    assert abs(paired["meanDiff"]) < 1e-12
    assert paired["improved"] is False
    assert paired["ciLow"] <= 0.0 <= paired["ciHigh"]


def test_225_paired_comparison_requires_shared_points():
    """Ortak nokta yoksa sessiz sifir degil, acik 'veri yok' doner."""
    before = lc.CurveReport(points=[_point(1, 100, [0.1, 0.2], ["g0", "g1"])])
    after = lc.CurveReport(points=[_point(2, 200, [0.1, 0.2], ["g0", "g1"])])
    paired = lc.paired_curve_comparison(before, after)
    assert paired["points"] == []
    assert paired["improved"] is None
    assert paired["note"] == "ortak nokta yok"


def test_226_seed_prefix_is_stripped_for_pairing():
    """Havuzlanmis raporda oyun kimligi ``s3:`` onekli; eslestirme oneki atar."""
    assert lc._strip_seed_prefix("s3:cp-012") == "cp-012"
    assert lc._strip_seed_prefix("cp-012") == "cp-012"
    assert lc._strip_seed_prefix("sX:cp-012") == "sX:cp-012"
    point = _point(1, 4, [0.1, 0.3, 0.5, 0.7], ["s1:g0", "s1:g0", "s2:g0", "s2:g0"])
    means = lc._game_means(point, "policy")
    assert means == {"g0": pytest.approx(0.4)}


def test_227_report_roundtrip_preserves_corpus_and_paired():
    """``to_dict``/``from_dict`` yeni alanlari kaybetmemeli."""
    report = lc.CurveReport(points=_synthetic_curve(floor=0.01))
    report.corpus = {"havuz": "p.npz"}
    report.paired = {"meanDiff": -0.001, "improved": True, "points": []}
    back = lc.CurveReport.from_dict(report.to_dict())
    assert back.corpus == {"havuz": "p.npz"}
    assert back.paired["meanDiff"] == pytest.approx(-0.001)
    assert back.paired["improved"] is True


# Test 243
def test_main_writes_out_without_compare_before(tmp_path):
    """``main()`` ``--out`` yazmali; ``--compare-before`` yokken de.

    Regresyon: ``main()`` icindeki yerel ``import json`` modul adini yerel
    degiskene cevirip ``json.dumps`` cagrisini ``UnboundLocalError`` ile
    dusuruyordu. Bu, 5 tohumluk 90 dakikalik kosunun **raporunu** kaybettirdi.
    """
    import json

    import learning_curve as L

    report = L.CurveReport(seed=1, seeds=[1], bootstrap_resamples=10, bootstrap_seed=1)
    report.points.append(
        L.CurvePoint(
            multiplier=1,
            positions=10,
            losses={"value": [0.5, 0.4], "policy": [0.6, 0.5]},
            game_ids={"value": ["g1", "g2"], "policy": ["g1", "g2"]},
            slope=None,
            mae=None,
            in_sample_loss=0.5,
            held_out_loss=0.5,
        )
    )
    src = tmp_path / "in.json"
    src.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    out = tmp_path / "out.json"
    md = tmp_path / "out.md"

    code = L.main(
        [
            "--from-json", str(src),
            "--out", str(out),
            "--markdown", str(md),
            "--quiet",
        ]
    )
    assert code == 0
    assert out.is_file(), "--out yazilmadi"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["points"], "noktalar yazilmadi"
    assert md.is_file(), "--markdown yazilmadi"

# ----------------------------------------------------------------------
# K4: "N icin gereken veri" kriteri (Test 276-280)
# ----------------------------------------------------------------------


def test_276_data_requirement_inverts_the_fit():
    """``N = (a / (target - c)) ** (1/b)``; fit denklemi geri uretir."""
    fit = {"a": 0.3, "b": 0.5, "c": 0.01}
    n = lc.data_requirement(fit, 0.02)
    assert n == pytest.approx((0.3 / 0.01) ** 2.0)
    # Ters cozum gercekten hedefi veriyor mu?
    assert 0.3 * n ** -0.5 + 0.01 == pytest.approx(0.02)


def test_277_data_requirement_is_infinite_below_the_floor():
    """Hedef tabanin altindaysa hicbir N yetmez -> ``inf`` (pipeline sinyali)."""
    fit = {"a": 0.3, "b": 0.5, "c": 0.05}
    assert lc.data_requirement(fit, 0.05) == float("inf")
    assert lc.data_requirement(fit, 0.01) == float("inf")


def test_278_data_requirement_is_nan_for_invalid_fit():
    """Gecersiz fit sessizce 0 dondurmez, ``nan`` doner (Kural 6)."""
    assert np.isnan(lc.data_requirement({}, 0.02))
    assert np.isnan(lc.data_requirement({"a": float("nan"), "b": 0.5, "c": 0.0}, 0.02))
    assert np.isnan(lc.data_requirement({"a": 0.0, "b": 0.5, "c": 0.0}, 0.02))
    assert np.isnan(lc.data_requirement({"a": 0.3, "b": 0.0, "c": 0.0}, 0.02))


def test_279_data_requirement_decision_labels():
    """``inf`` -> pipeline, butce ici -> olcek, butce disi -> belirsiz."""
    base = dict(path="policy", best_er=0.02, target=0.01, floor=0.0, budget=1000.0)
    assert lc.DataRequirement(positions=float("inf"), **base).decision == lc.DECISION_PIPELINE
    assert lc.DataRequirement(positions=500.0, **base).decision == lc.DECISION_SCALES
    assert lc.DataRequirement(positions=5000.0, **base).decision == lc.DECISION_UNDETERMINED
    assert (
        lc.DataRequirement(positions=float("nan"), **base).decision
        == lc.DECISION_UNDETERMINED
    )


def test_280_report_data_decision_uses_policy_path_and_blocks_conflict():
    """Rapor etiketi veri kriteriyle celisirse ``belirsiz`` olur (K4)."""
    points = _synthetic_curve(floor=0.01, a=0.3, b=0.5)
    report = lc.CurveReport(
        points=points,
        slopes={"policy": {"slope": 0.05, "gainCiLow": 0.04, "gainCiHigh": 0.06}},
        saturation={"policy": {"a": 0.3, "b": 0.5, "c": 0.01}},
    )
    req = report.data_requirement("policy")
    assert req is not None
    assert req.target == pytest.approx(0.5 * report.best_er("policy"))
    assert req.budget == pytest.approx(100.0 * report.max_positions())
    # Tabani hedefin ustune cikar: veri kriteri "pipeline" der, egim "olcek".
    report.saturation["policy"] = {"a": 0.3, "b": 0.5, "c": 0.5}
    assert report.data_decision == lc.DECISION_PIPELINE
    assert report.decision == lc.DECISION_UNDETERMINED


def test_281_report_data_decision_agrees_with_slope_decision():
    """Iki kriter de ``olcek`` derse etiket korunur."""
    points = _synthetic_curve(floor=0.001, a=0.3, b=0.5)
    report = lc.CurveReport(
        points=points,
        slopes={"policy": {"slope": 0.05, "gainCiLow": 0.04, "gainCiHigh": 0.06}},
        saturation={"policy": {"a": 0.3, "b": 0.5, "c": 0.001}},
    )
    assert report.data_decision == lc.DECISION_SCALES
    assert report.decision == lc.DECISION_SCALES


def test_282_markdown_renders_data_requirement_section():
    """Markdown 4.2 bolumu tabloyu ve ``ulasilamaz`` isaretini yazar."""
    points = _synthetic_curve(floor=0.001, a=0.3, b=0.5)
    for point in points:
        point.losses["value"] = list(point.losses["policy"])
    report = lc.CurveReport(
        points=points,
        slopes={"policy": {"slope": 0.05, "gainCiLow": 0.04, "gainCiHigh": 0.06}},
        saturation={
            "policy": {"a": 0.3, "b": 0.5, "c": 0.001},
            "value": {"a": 0.3, "b": 0.5, "c": 0.9},
        },
    )
    md = lc.build_markdown(report)
    assert '## 4.2 "N icin gereken veri" (K4)' in md
    assert "| policy |" in md
    assert "| value |" in md
    assert "**ulasilamaz**" in md
    assert "pipeline" in md


def test_283_to_dict_carries_data_requirement_fields():
    """``to_dict`` veri kriteri alanlarini tasir; ``from_dict`` geri kurar."""
    points = _synthetic_curve(floor=0.001, a=0.3, b=0.5)
    report = lc.CurveReport(
        points=points,
        slopes={"policy": {"slope": 0.05, "gainCiLow": 0.04, "gainCiHigh": 0.06}},
        saturation={"policy": {"a": 0.3, "b": 0.5, "c": 0.001}},
    )
    data = report.to_dict()
    assert data["dataTargetRatio"] == pytest.approx(lc.DATA_TARGET_RATIO)
    assert data["dataBudgetMultiplier"] == pytest.approx(lc.DATA_BUDGET_MULTIPLIER)
    assert data["dataDecision"] == lc.DECISION_SCALES
    assert data["dataRequirements"]["policy"]["decision"] == lc.DECISION_SCALES
    again = lc.CurveReport.from_dict(data)
    assert again.decision == report.decision
    assert again.data_decision == report.data_decision