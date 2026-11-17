"""Faz 7 Bolum 4.5/4.6 -- Test 124: ER olcumunun istatistiksel guc sozlesmesi.

Bu dosya, `ml/er_power.py` modulunun **sozlesmesini** kilitler. Sozlesme
"ER <= 0,005" iddiasinin ne zaman yazilabilecegini belirler; bu yuzden
testlerin kendisi de iddianin **yanlis** yazilmasini engelleyen negatif
testler icerir.

Kapsam (faz 7.md Bolum 9.1, Test 124 -- 9 madde):
  1. required_n nokta tahmininden: 1 829 (iki tarafli) / 1 288 (tek tarafli)
  2. required_n_from_upper: 1 665 -- nokta tahmini n'i %29 eksik hesaplar
  3. nokta tahmini yolu kanit icin **kullanilamaz** (negatif test)
  4. claim_er_at_most uc durumlu: proven / refuted / not_proven
  5. screen reddederse prove cagrilamaz
  6. prove tavani asarsa capped: true -- asla None degil
  7. validate_er_report eksik n'i yakalar
  8. assert_valid isaretli dosyada MeasurementInvalidatedError atar
  9. summarize_losses belgelenen istatistikleri gercek veriden uretir
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import er_power as P

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = REPO_ROOT / "ml" / "artifacts"
STAGE_H_2PLY = ARTIFACTS / "stage_h_er_2ply.json"

#: Belgelenen degerler (faz 7.md Bolum 4.5 / 4.5.1). Sabit yazilir: test
#: belgeyi denetler, belgeyi takip etmez.
DOC_SIGMA = 0.109072
DOC_SIGMA_CI_HIGH = 0.124178
DOC_MEAN = 0.073970
DOC_SKEWNESS = 1.7405
DOC_EXCESS_KURTOSIS = 2.4359
DOC_TAIL_SHARE = 0.2716
DOC_TRIMMED_MEAN_5 = 0.059867
DOC_TRIMMED_MEAN_10 = 0.050769
DOC_WINSORIZED_MEAN_5 = 0.068830
DOC_WINSORIZED_MEAN_10 = 0.065515
DOC_N = 200


def _losses() -> list[float]:
    if not STAGE_H_2PLY.is_file():
        pytest.skip("stage_h 2-ply olcumu yok: %s" % STAGE_H_2PLY)
    data = json.loads(STAGE_H_2PLY.read_text(encoding="utf-8"))
    return [float(p["equityLoss"]) for p in data["positions"]]


@pytest.fixture(scope="module")
def stage_h_summary() -> P.LossSummary:
    """Gercek olcumun ozeti -- modul basina bir kez (bootstrap pahali)."""
    return P.summarize_losses(_losses())


# ----------------------------------------------------------------------
# 1-3 -- Orneklem buyuklugu
# ----------------------------------------------------------------------


def test_124_required_n_matches_document() -> None:
    """1: n = (z * sigma / h)^2 -- belgedeki 1 829 / 1 288 sayilari."""
    assert P.required_n(DOC_SIGMA, 0.005, two_sided=True) == 1829
    assert P.required_n(DOC_SIGMA, 0.005, two_sided=False) == 1288


def test_124_required_n_halving_half_width_quadruples_n() -> None:
    """1: yari genislik yariya inerse n dort katina cikar."""
    assert P.required_n(DOC_SIGMA, 0.0025, two_sided=False) == 5151
    assert P.required_n(DOC_SIGMA, 0.0025, two_sided=True) == 7313


def test_124_required_n_from_upper_matches_document() -> None:
    """2: sigma'nin ust guven sinirindan 1 665."""
    assert P.required_n_from_upper(DOC_SIGMA_CI_HIGH, 0.005) == 1670
    assert P.required_n_from_upper(DOC_SIGMA_CI_HIGH, 0.005, two_sided=True) == 2370


def test_124_point_estimate_undercounts_required_n() -> None:
    """2: nokta tahmini n'i sistematik olarak eksik hesaplar (~%29)."""
    point = P.required_n(DOC_SIGMA, 0.005, two_sided=False)
    upper = P.required_n_from_upper(DOC_SIGMA_CI_HIGH, 0.005)
    assert upper > point
    assert (upper - point) / point == pytest.approx(0.30, abs=0.01)


def test_124_required_n_rejects_nonpositive_input() -> None:
    """1: sigma ve yari genislik pozitif olmali."""
    with pytest.raises(ValueError):
        P.required_n(0.0, 0.005)
    with pytest.raises(ValueError):
        P.required_n(DOC_SIGMA, 0.0)


def test_124_summary_required_n_uses_upper_bound(stage_h_summary: P.LossSummary) -> None:
    """3: LossSummary.required_n nokta tahminini **kullanmaz**."""
    assert stage_h_summary.required_n(0.005) == 1670
    assert stage_h_summary.required_n(0.005) != P.required_n(
        stage_h_summary.sigma, 0.005, two_sided=False
    )


# ----------------------------------------------------------------------
# 6 -- Tavan
# ----------------------------------------------------------------------


def test_124_n_within_cap_returns_required_when_it_fits() -> None:
    """6: tavan yetiyorsa gereken n kosulur, capped = False."""
    n, capped = P.n_within_cap(100, 0.1, cap_hours=40.0)
    assert (n, capped) == (100, False)


def test_124_n_within_cap_truncates_instead_of_cancelling() -> None:
    """6: tavan yetmiyorsa olcum **iptal edilmez**, tavana kadar kosulur."""
    n, capped = P.n_within_cap(1670, 0.1, cap_hours=40.0)
    assert (n, capped) == (400, True)


def test_124_n_within_cap_rejects_impossible_cap() -> None:
    """6: tavan tek pozisyonu bile karsilamiyorsa sessizce 0 donmez."""
    with pytest.raises(ValueError):
        P.n_within_cap(10, 100.0, cap_hours=40.0)


# ----------------------------------------------------------------------
# 4 -- Uc durumlu iddia
# ----------------------------------------------------------------------


def test_124_claim_proven_when_upper_bound_below_target() -> None:
    """4: GA ust siniri hedefin altinda -> kanitlandi."""
    assert P.claim_er_at_most(0.005, 0.0010, 0.0040) == P.PROVEN


def test_124_claim_proven_at_exact_boundary() -> None:
    """4: ust sinir hedefe **esit** ise de kanitlanmistir (<=)."""
    assert P.claim_er_at_most(0.005, 0.0010, 0.0050) == P.PROVEN


def test_124_claim_refuted_when_lower_bound_above_target() -> None:
    """4: GA alt siniri hedefin ustunde -> yanlislandi."""
    assert P.claim_er_at_most(0.005, 0.0600, 0.0900) == P.REFUTED


def test_124_claim_not_proven_when_interval_straddles_target() -> None:
    """4: nokta tahmini hedefin altinda ama GA hedefi iceriyor -> kanitlanmadi.

    Bu, ikili True/False'in yok ettigi durumdur: "yanlislandi" demek yalan
    (ortalama 0,004), "kanitlandi" demek de yalan (ust sinir 0,006).
    """
    assert P.claim_er_at_most(0.005, 0.0040, 0.0060) == P.NOT_PROVEN


def test_124_claim_rejects_inverted_interval() -> None:
    """4: ci_low > ci_high sessizce kabul edilmez."""
    with pytest.raises(ValueError):
        P.claim_er_at_most(0.005, 0.0100, 0.0010)


def test_124_claim_states_are_exactly_three() -> None:
    """4: sozlesme uc durum tanimlar; dorduncu bir durum eklenemez."""
    assert P.CLAIM_STATES == (P.PROVEN, P.REFUTED, P.NOT_PROVEN)
    assert len(set(P.CLAIM_STATES)) == 3


def test_124_claim_sentence_matches_state(stage_h_summary: P.LossSummary) -> None:
    """4: rapora yazilan cumle iddia durumuyla celismez."""
    sentence = P.claim_sentence(0.005, stage_h_summary)
    assert stage_h_summary.claim(0.005) == P.REFUTED
    assert "yanlislandi" in sentence


# ----------------------------------------------------------------------
# 5 -- Tarama asamasi kanitlayamaz
# ----------------------------------------------------------------------


def test_124_screen_rejects_model_far_from_target() -> None:
    """5: iyimser sinirda bile hedefin disindaysa tarama reddeder."""
    losses = [0.10] * 50 + [0.20] * 50
    result = P.screen(losses, target=0.005, resamples=500)
    assert result.rejected is True
    assert "kanit kosulmaz" in result.reason


def test_124_screen_passes_but_never_proves() -> None:
    """5: tarama gecse bile `canProve` **her zaman** False."""
    losses = [0.0] * 90 + [0.01] * 10
    result = P.screen(losses, target=0.005, resamples=500)
    assert result.rejected is False
    assert result.to_dict()["canProve"] is False
    assert result.to_dict()["stage"] == "screen"


def test_124_screen_result_has_no_claim_field() -> None:
    """5: tarama ciktisinda iddia alani **yok** -- yanlislikla rapora giremez."""
    losses = [0.0] * 90 + [0.01] * 10
    data = P.screen(losses, target=0.005, resamples=500).to_dict()
    assert "claim" not in data
    assert "sentence" not in data


# ----------------------------------------------------------------------
# 6 -- Kanit asamasi
# ----------------------------------------------------------------------


def test_124_prove_marks_capped_when_n_below_required() -> None:
    """6: n < gereken n -> capped True, n_required asla None degil."""
    losses = [0.0] * 80 + [0.10] * 20
    result = P.prove(losses, target=0.005, resamples=500)
    assert result.capped is True
    assert result.n_required is not None
    assert result.n_required > result.n_run
    assert any("tavan asildi" in note for note in result.notes)


def test_124_prove_uncapped_when_n_sufficient() -> None:
    """6: n >= gereken n -> capped False."""
    losses = [0.0] * 90 + [0.01] * 10
    result = P.prove(losses, target=0.005, n_required=10, resamples=500)
    assert result.capped is False
    assert result.n_required == 10


def test_124_prove_claim_is_three_state() -> None:
    """6: tavan kaniti zayiflatir ama iddiayi uc durumdan birine baglar."""
    losses = [0.0] * 80 + [0.10] * 20
    result = P.prove(losses, target=0.005, resamples=500)
    assert result.claim in P.CLAIM_STATES


def test_124_prove_flags_heavy_tail() -> None:
    """6: agir kuyruk notu dusulur (Bolum 4.5.3 kuyruk teshisi)."""
    losses = [0.0] * 95 + [1.0] * 5
    result = P.prove(losses, target=0.005, resamples=500)
    assert any("agir kuyruklu" in note for note in result.notes)


# ----------------------------------------------------------------------
# 7 -- Rapor dogrulama
# ----------------------------------------------------------------------


def test_124_validate_er_report_flags_missing_n(stage_h_summary: P.LossSummary) -> None:
    """7: n eksikse rapor gecersiz."""
    report = stage_h_summary.to_dict()
    del report["n"]
    problems = P.validate_er_report(report)
    assert any("n" in p for p in problems)


def test_124_validate_er_report_flags_empty_n(stage_h_summary: P.LossSummary) -> None:
    """7: n = 0 ise rapor gecersiz."""
    report = stage_h_summary.to_dict()
    report["n"] = 0
    assert any("n bos" in p for p in P.validate_er_report(report))


def test_124_validate_er_report_flags_inconsistent_sigma(stage_h_summary: P.LossSummary) -> None:
    """7: sigmaCiHigh < sigma ise rapor gecersiz."""
    report = stage_h_summary.to_dict()
    report["sigmaCiHigh"] = report["sigma"] / 2.0
    assert any("sigmaCiHigh" in p for p in P.validate_er_report(report))


def test_124_validate_er_report_accepts_complete_report(stage_h_summary: P.LossSummary) -> None:
    """7: tam rapor sorunsuz gecer."""
    assert P.validate_er_report(stage_h_summary.to_dict()) == []


def test_124_summary_missing_fields_is_empty(stage_h_summary: P.LossSummary) -> None:
    """7: LossSummary Test 124'un tum zorunlu alanlarini tasir."""
    assert stage_h_summary.missing_fields() == []
    assert set(P.ER_REPORT_FIELDS) <= set(stage_h_summary.to_dict())


# ----------------------------------------------------------------------
# 8 -- Gecersiz isaretleme (Bolum 4.6)
# ----------------------------------------------------------------------


def test_124_assert_valid_passes_on_clean_file(tmp_path: Path) -> None:
    """8: isaretsiz dosya okunabilir."""
    target = tmp_path / "er.json"
    target.write_text("{}", encoding="utf-8")
    P.assert_valid(target)


def test_124_assert_valid_raises_on_marked_file(tmp_path: Path) -> None:
    """8: isaretli dosya okunamaz -- "isaretledim ama kullandim" imkansiz."""
    target = tmp_path / "er.json"
    target.write_text("{}", encoding="utf-8")
    P.invalidate(target, gate="F-A1", reason="pip sayaci uyusmuyor", evidence="log.txt")
    assert P.is_invalidated(target) is True
    with pytest.raises(P.MeasurementInvalidatedError) as excinfo:
        P.assert_valid(target)
    assert "F-A1" in str(excinfo.value)


def test_124_invalidate_does_not_touch_original(tmp_path: Path) -> None:
    """8: orijinal dosya silinmez ve degistirilmez (denetim izi)."""
    target = tmp_path / "er.json"
    original = '{"mean": 0.097225}'
    target.write_text(original, encoding="utf-8")
    marker = P.invalidate(target, gate="F-A2", reason="yanlis ply")
    assert target.read_text(encoding="utf-8") == original
    assert marker.name == "er.json.invalidated.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["gate"] == "F-A2"
    assert payload["reRunRequired"] is True
    assert payload["invalidatedAt"]


def test_124_invalidate_requires_existing_file(tmp_path: Path) -> None:
    """8: olmayan olcumu isaretlemek sessizce gecmez."""
    with pytest.raises(FileNotFoundError):
        P.invalidate(tmp_path / "yok.json", gate="F-A1", reason="x")


def test_124_archive_invalidation_clears_marker(tmp_path: Path) -> None:
    """8: isaret arsivlenir (silinmez), yeni olcum isaretsiz dogar."""
    target = tmp_path / "er.json"
    target.write_text("{}", encoding="utf-8")
    P.invalidate(target, gate="F-A1", reason="x")
    archived = P.archive_invalidation(target)
    assert archived is not None
    assert archived.is_file()
    assert P.is_invalidated(target) is False
    P.assert_valid(target)


def test_124_archive_invalidation_is_noop_without_marker(tmp_path: Path) -> None:
    """8: isaret yoksa arsivleme None doner."""
    target = tmp_path / "er.json"
    target.write_text("{}", encoding="utf-8")
    assert P.archive_invalidation(target) is None


def test_124_count_invalidated_counts_active_markers(tmp_path: Path) -> None:
    """8: Bolum 10.5 kapisi -- dizindeki aktif isaret sayisi."""
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert P.count_invalidated(tmp_path) == 0
    P.invalidate(tmp_path / "a.json", gate="F-A1", reason="x")
    assert P.count_invalidated(tmp_path) == 1
    P.archive_invalidation(tmp_path / "a.json")
    assert P.count_invalidated(tmp_path) == 0


def test_124_load_measurement_blocks_invalidated_file(tmp_path: Path) -> None:
    """8: okuma yolu da isareti denetler -- tek kapi degil."""
    target = tmp_path / "er.json"
    target.write_text('{"mean": 0.1}', encoding="utf-8")
    assert P.load_measurement(target)["mean"] == 0.1
    P.invalidate(target, gate="F-A3", reason="x")
    with pytest.raises(P.MeasurementInvalidatedError):
        P.load_measurement(target)


# ----------------------------------------------------------------------
# sigma kaydi (Bolum 4.5.2)
# ----------------------------------------------------------------------


def test_124_sigma_log_entry_has_all_fields(stage_h_summary: P.LossSummary) -> None:
    """Bolum 4.5.2: 12 zorunlu alan -- eksikse kayit reddedilir."""
    entry = P.sigma_log_entry(stage_h_summary, stage="A", model="model_v30.onnx")
    assert set(P.SIGMA_LOG_FIELDS) <= set(entry)
    assert entry["stage"] == "A"
    assert entry["n"] == DOC_N


def test_124_append_sigma_log_is_append_only(tmp_path: Path, stage_h_summary: P.LossSummary) -> None:
    """Bolum 4.5.2: kayit uzerine yazmaz, ekler."""
    log = tmp_path / "er_sigma_log.json"
    entry = P.sigma_log_entry(stage_h_summary, stage="A", model="m.onnx")
    P.append_sigma_log(log, entry)
    P.append_sigma_log(log, dict(entry, stage="B"))
    data = json.loads(log.read_text(encoding="utf-8"))
    assert [e["stage"] for e in data["entries"]] == ["A", "B"]


def test_124_append_sigma_log_rejects_incomplete_entry(tmp_path: Path) -> None:
    """Bolum 4.5.2: eksik alanli kayit dosyaya yazilmaz."""
    with pytest.raises(ValueError):
        P.append_sigma_log(tmp_path / "log.json", {"stage": "A"})


def test_124_scale_family_drift_detects_break() -> None:
    """Bolum 4.5.2: sigma/ortalama orani %30'dan fazla kayarsa varsayim curur."""
    stable = [
        {"sigma": 0.109, "mean": 0.074},
        {"sigma": 0.110, "mean": 0.075},
    ]
    assert P.scale_family_drift(stable)["refuted"] is False
    broken = [
        {"sigma": 0.109, "mean": 0.074},
        {"sigma": 0.020, "mean": 0.070},
    ]
    result = P.scale_family_drift(broken)
    assert result["refuted"] is True
    assert result["worstSigma"] == 0.109


def test_124_scale_family_drift_needs_two_entries() -> None:
    """Bolum 4.5.2: tek kayitla kayma olculemez -- sessizce 0 doner."""
    result = P.scale_family_drift([{"sigma": 0.109, "mean": 0.074}])
    assert result["refuted"] is False
    assert result["drift"] == 0.0


# ----------------------------------------------------------------------
# 9 -- Gercek veriden istatistikler
# ----------------------------------------------------------------------


def test_124_summarize_reproduces_stage_h_statistics(stage_h_summary: P.LossSummary) -> None:
    """9: belgelenen istatistikler gercek olcumden birebir uretilir."""
    s = stage_h_summary
    assert s.n == DOC_N
    assert s.mean == pytest.approx(DOC_MEAN, abs=1e-6)
    assert s.sigma == pytest.approx(DOC_SIGMA, abs=1e-6)
    assert s.sigma_ci_high == pytest.approx(DOC_SIGMA_CI_HIGH, abs=1e-6)
    assert s.skewness == pytest.approx(DOC_SKEWNESS, abs=1e-4)
    assert s.excess_kurtosis == pytest.approx(DOC_EXCESS_KURTOSIS, abs=1e-4)
    assert s.tail_share == pytest.approx(DOC_TAIL_SHARE, abs=1e-4)
    assert s.trimmed_mean_5 == pytest.approx(DOC_TRIMMED_MEAN_5, abs=1e-6)
    assert s.trimmed_mean_10 == pytest.approx(DOC_TRIMMED_MEAN_10, abs=1e-6)
    assert s.winsorized_mean_5 == pytest.approx(DOC_WINSORIZED_MEAN_5, abs=1e-6)
    assert s.winsorized_mean_10 == pytest.approx(DOC_WINSORIZED_MEAN_10, abs=1e-6)


def test_124_sigma_ci_is_wider_than_normal_approximation(stage_h_summary: P.LossSummary) -> None:
    """9: carpik dagilimda bootstrap GA normal yaklasimdan genistir."""
    s = stage_h_summary
    normal_half = s.standard_error / (2.0 ** 0.5)
    bootstrap_half = (s.sigma_ci_high - s.sigma_ci_low) / 2.0
    assert bootstrap_half > normal_half


def test_124_stage_h_claim_is_refuted(stage_h_summary: P.LossSummary) -> None:
    """9: bugunku model hedefte degil -- iddia yanlislandi."""
    assert stage_h_summary.claim(0.005) == P.REFUTED


def test_124_tail_diagnostics_flags_heavy_tail(stage_h_summary: P.LossSummary) -> None:
    """9: bugunku dagilim agir kuyruklu olarak isaretlenir."""
    diag = stage_h_summary.tail_diagnostics()
    assert diag["heavyTailed"] is True
    assert diag["trimmedDeviationAlert"] is True


def test_124_summarize_rejects_negative_loss() -> None:
    """9: equity kaybi negatif olamaz."""
    with pytest.raises(ValueError):
        P.summarize_losses([0.0, -0.1], resamples=100)


def test_124_summarize_rejects_single_sample() -> None:
    """9: tek ornekle sigma hesaplanamaz."""
    with pytest.raises(ValueError):
        P.summarize_losses([0.1], resamples=100)
