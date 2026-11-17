"""Faz 6 v3 Bölüm 12.1 (Aşama A) — ölçüm hattı ve taban kilidi testleri.

Test 41a–48. gnubg gerektiren testler `pytest.mark.skipif` ile atlanır; küme,
bölünme, kodlama ve rapor testleri gnubg kurulu olmadan da çalışır.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

import er_harness as H
import gnubg_er as G

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_PATH = H.CORPUS_PATH
BASELINE_PATH = H.BASELINE_REPORT
STAGE_D_MODEL = H.ML_DIR / "artifacts" / "model_stage_d_v10.onnx"
PHASES_DOC = REPO_ROOT / "PHASES.md"
OUTCOME_DISTRIBUTION = REPO_ROOT / "Backgammon.Core" / "Match" / "OutcomeDistribution.cs"
ENUMS_CS = REPO_ROOT / "Backgammon.Core" / "Enums.cs"
SELF_PLAY_RUNNER = REPO_ROOT / "Backgammon.SelfPlay" / "SelfPlayRunner.cs"

GNUBG = G.find_gnubg()
requires_gnubg = pytest.mark.skipif(GNUBG is None, reason="gnubg-cli kurulu degil")


def _corpus() -> dict:
    if not CORPUS_PATH.is_file():
        pytest.skip("referans küme yok: %s" % CORPUS_PATH)
    return H.load_corpus(CORPUS_PATH)


def _baseline_text() -> str:
    if not BASELINE_PATH.is_file():
        pytest.skip("taban raporu yok: %s" % BASELINE_PATH)
    return BASELINE_PATH.read_text(encoding="utf-8")


def _stage_d_model() -> Path:
    if not STAGE_D_MODEL.is_file():
        pytest.skip("stage_d modeli yok: %s" % STAGE_D_MODEL)
    return STAGE_D_MODEL


# ----------------------------------------------------------------------
# 41a — Faz 5 değerinin yeniden üretimi
# ----------------------------------------------------------------------


@requires_gnubg
def test_er_harness_reproduces_stage_d_50_positions() -> None:
    """41a: 50 pozisyonluk alt kümede ER 0,1941 ± 0,01."""
    model = _stage_d_model()
    cases = G.load_cases(H.LEGACY_CASES)
    usable, _skipped = G.split_cases(cases)
    usable = usable[: H.STAGE_D_USABLE]
    assert len(usable) == H.STAGE_D_USABLE

    results, _ = G.measure(
        model, usable, gnubg=GNUBG, plies=G.DEFAULT_PLIES, progress=False
    )
    stats = G.summarize(results)
    assert abs(stats["mean"] - H.STAGE_D_ER_MEAN) <= H.STAGE_D_ER_TOLERANCE, (
        "ER %.4f, Faz 5 değeri %.4f, tolerans ±%.2f"
        % (stats["mean"], H.STAGE_D_ER_MEAN, H.STAGE_D_ER_TOLERANCE)
    )


# ----------------------------------------------------------------------
# 41b — 200 pozisyonluk küme
# ----------------------------------------------------------------------


def test_er_harness_reports_200_positions() -> None:
    """41b: küme 200 pozisyon; rapor ölçülmüş ER'yi içerir (eşik yok)."""
    corpus = _corpus()
    assert len(corpus["cases"]) == H.TARGET_POSITIONS

    text = _baseline_text()
    assert "## 41b" in text
    # Ölçüm satırı: | `all` | 200 | **0.xxxx** | ...
    match = re.search(r"\|\s*`all`\s*\|\s*(\d+)\s*\|\s*\*\*([0-9.]+)\*\*", text)
    assert match is not None, "41b ölçüm satırı raporda yok"
    assert int(match.group(1)) == H.TARGET_POSITIONS
    assert 0.0 <= float(match.group(2)) <= 3.0


# ----------------------------------------------------------------------
# 41c — OutcomeDistribution kodlaması
# ----------------------------------------------------------------------


def test_outcome_distribution_encoding_is_documented() -> None:
    """41c: sınıf kümülatif kodlama kullanır ve rapor bunu yazar."""
    source = OUTCOME_DISTRIBUTION.read_text(encoding="utf-8")
    for field in ("Win", "WinGammon", "WinBackgammon", "LoseGammon", "LoseBackgammon"):
        assert field in source, "OutcomeDistribution.%s yok" % field
    # `Lose` türetilmiş olmalı (kümülatif kodlamanın kanıtı).
    assert "1f - Win" in source, "Lose türetilmiş değil; kodlama kümülatif olmayabilir"
    # Kümülatif kodlamanın değişmezi: WinBackgammon ≤ WinGammon ≤ Win.
    assert "WinBackgammon > WinGammon" in source
    assert "WinGammon > Win" in source

    assert H.OUTCOME_ENCODING == "cumulative"
    text = _baseline_text()
    assert "## 41c" in text
    assert "`cumulative`" in text


# ----------------------------------------------------------------------
# 41d — resultType winner'ı içeriyor mu?
# ----------------------------------------------------------------------


def test_shard_result_type_contains_winner() -> None:
    """41d: `resultType` yalnız çarpan taşır; `winner` ayrı alandır."""
    enums = ENUMS_CS.read_text(encoding="utf-8")
    block = enums.split("enum GameResultType", 1)[1].split("}", 1)[0]
    for name in ("None", "Single", "Gammon", "Backgammon"):
        assert name in block, "GameResultType.%s yok" % name
    assert "Winner" not in block, "GameResultType winner taşımamalı"

    runner = SELF_PLAY_RUNNER.read_text(encoding="utf-8")
    assert "game.Winner = result.Winner" in runner
    assert "game.ResultType = (byte)result.ResultType" in runner

    assert H.RESULT_TYPE_CONTAINS_WINNER is False
    text = _baseline_text()
    assert "## 41d" in text
    assert "**Sonuç: HAYIR.**" in text


# ----------------------------------------------------------------------
# 41e — Veri hacmi ölçülür
# ----------------------------------------------------------------------


def test_data_volume_is_measured() -> None:
    """41e: shard varsa bayt/karar ölçülür ve rapora yazılır."""
    shard_dir = H.ML_DIR / "runs" / "stage_d" / "shards" / "it10"
    paths = H.collect_shards(shard_dir)
    if not paths:
        pytest.skip("ölçülecek shard yok: %s" % shard_dir)

    volume = H.measure_data_volume(paths)
    assert volume["measured"] is True
    assert volume["decisions"] > 0
    assert volume["bytesPerDecisionRaw"] > 0
    assert volume["bytesPerDecisionDisk"] > 0
    # Sıkıştırma ham boyuttan küçük olmalı.
    assert volume["bytesPerDecisionDisk"] < volume["bytesPerDecisionRaw"]

    text = _baseline_text()
    assert "## 41e" in text
    assert "Ham bayt/karar" in text
    assert "**Ölçülmedi**" not in text.split("## 41e", 1)[1].split("## 47", 1)[0]


# ----------------------------------------------------------------------
# 42 — Determinizm
# ----------------------------------------------------------------------


def test_er_harness_is_deterministic() -> None:
    """42: aynı tohum → aynı küme; aynı model → aynı ER (CPU)."""
    first = H.build_corpus(seed=H.CORPUS_SEED, target=H.TARGET_POSITIONS)
    second = H.build_corpus(seed=H.CORPUS_SEED, target=H.TARGET_POSITIONS)
    assert first["digest"] == second["digest"]
    assert first["splits"] == second["splits"]

    corpus = _corpus()
    assert corpus["digest"] == first["digest"], "dondurulmuş küme üreticiyle uyuşmuyor"

    if GNUBG is None:
        return
    model = _stage_d_model()
    cases = H.select_cases(corpus, "cal")[:3]
    first_run, _ = G.measure(model, cases, gnubg=GNUBG, plies=2, progress=False)
    second_run, _ = G.measure(model, cases, gnubg=GNUBG, plies=2, progress=False)
    assert [r.equity_loss for r in first_run] == [r.equity_loss for r in second_run]


# ----------------------------------------------------------------------
# 43 — gnubg yoksa uydurma değer yok
# ----------------------------------------------------------------------


def test_er_harness_rejects_missing_gnubg(tmp_path: Path) -> None:
    """43: gnubg yoksa sıfır olmayan çıkış kodu, hiçbir sayı üretilmez."""
    bogus = tmp_path / "yok-gnubg-cli.exe"
    out = tmp_path / "baseline.md"
    code = H.main(
        [
            "baseline",
            "--model",
            str(_stage_d_model()),
            "--gnubg",
            str(bogus),
            "--out",
            str(out),
            "--quiet",
        ]
    )
    assert code != 0
    assert not out.exists()

    code = H.main(
        [
            "measure",
            "--model",
            str(_stage_d_model()),
            "--gnubg",
            str(bogus),
            "--quiet",
        ]
    )
    assert code != 0


# ----------------------------------------------------------------------
# 44 — Küme dondurulmuş ve bölünmeler ayrık
# ----------------------------------------------------------------------


def test_reference_corpus_is_frozen() -> None:
    """44: SHA-256 sabit; CAL / VAL-ER / TEST-ER ayrık ve tam."""
    corpus = _corpus()
    assert H.verify_corpus(corpus) == []
    assert corpus["digest"] == H.corpus_digest(corpus)

    names = {case["name"] for case in corpus["cases"]}
    cal = set(corpus["splits"]["cal"])
    val = set(corpus["splits"]["val"])
    test = set(corpus["splits"]["test"])

    assert not (cal & val), "CAL ve VAL-ER kesişiyor"
    assert not (cal & test), "CAL ve TEST-ER kesişiyor"
    assert not (val & test), "VAL-ER ve TEST-ER kesişiyor"
    assert cal | val | test == names, "bölünmeler kümeyi tam kapsamıyor"

    # Bölünmeler arasında tahta tekrarı olmamalı (sızıntı).
    def boards(subset: set[str]) -> set[str]:
        return {
            json.dumps(case["board"])
            for case in corpus["cases"]
            if case["name"] in subset
        }

    assert not (boards(cal) & boards(test)), "CAL ve TEST-ER aynı tahtayı paylaşıyor"
    assert not (boards(val) & boards(test)), "VAL-ER ve TEST-ER aynı tahtayı paylaşıyor"


# ----------------------------------------------------------------------
# 45 — Faz kapsamı
# ----------------------------------------------------------------------


def test_reference_corpus_covers_all_phases() -> None:
    """45: temas, yarış, bearoff, bar, kapalı tahta — her biri ≥ 20."""
    corpus = _corpus()
    counts = {phase: 0 for phase in H.PHASES}
    for case in corpus["cases"]:
        counts[case["phase"]] += 1
    for phase in H.PHASES:
        assert counts[phase] >= H.PHASE_MINIMUM, "%s: %d < %d" % (
            phase,
            counts[phase],
            H.PHASE_MINIMUM,
        )
    assert sum(counts.values()) == H.TARGET_POSITIONS


# ----------------------------------------------------------------------
# 46 — İstatistiksel güç
# ----------------------------------------------------------------------


def test_statistical_power_is_measured() -> None:
    """46: standart hata ve gereken n hesaplanır, rapora yazılır."""
    power = H.statistical_power([0.0, 0.1, 0.2, 0.3])
    assert power["count"] == 4.0
    expected_sd = math.sqrt(
        sum((x - 0.15) ** 2 for x in (0.0, 0.1, 0.2, 0.3)) / 3
    )
    assert power["standardDeviation"] == pytest.approx(expected_sd)
    assert power["standardError"] == pytest.approx(expected_sd / 2.0)
    assert power["requiredCount"] == pytest.approx(
        (expected_sd / H.TARGET_STANDARD_ERROR) ** 2
    )

    text = _baseline_text()
    assert "## 46" in text
    assert "Std hata" in text
    assert "Gereken n" in text


# ----------------------------------------------------------------------
# 47 — PHASES.md taban kilidi
# ----------------------------------------------------------------------


def test_baseline_lock_matches_phases() -> None:
    """47: `PHASES.md` §7'deki ER değeri raporla uyuşur."""
    phases = PHASES_DOC.read_text(encoding="utf-8")
    # PHASES.md Türkçe ondalık virgül kullanır (0,1941).
    assert "0,1941" in phases or "0.1941" in phases, "PHASES.md §7'de 0,1941 yok"

    text = _baseline_text()
    assert "## 47" in text
    match = re.search(r"gnubg ER \(2-ply\) \| ([0-9.]+) \| ([0-9.]+) \|", text)
    assert match is not None, "47 tablo satırı yok"
    assert float(match.group(1)) == pytest.approx(H.STAGE_D_ER_MEAN)
    assert abs(float(match.group(2)) - H.STAGE_D_ER_MEAN) <= H.STAGE_D_ER_TOLERANCE


# ----------------------------------------------------------------------
# 48 — gnubg sürümü kaydedilir
# ----------------------------------------------------------------------


def test_gnubg_version_is_recorded() -> None:
    """48: gnubg sürümü, ply ve mod rapora yazılır."""
    text = _baseline_text()
    assert "## Ölçüm koşulları (Test 48)" in text
    assert "gnubg sürümü" in text
    assert "2-ply, cubeless, money game" in text
    assert "politika başı argmax" in text

    if GNUBG is not None:
        version = G.gnubg_version(GNUBG)
        assert version, "gnubg sürümü okunamadı"
        assert version in text, "sürüm raporda yok: %s" % version


# ----------------------------------------------------------------------
# 90 — gnubg "eval" derinlik sözleşmesi (F6-32)
# ----------------------------------------------------------------------


def test_equity_at_rejects_unsupported_ply() -> None:
    """90: ``_equity_at`` desteklenmeyen derinlikte sessizce başka sütuna düşmez.

    gnubg'nin ``eval`` komutu yalnızca ``static`` (0-ply), ``1 ply`` ve ``2 ply``
    satırlarını basar. ``set evaluation chequerplay evaluation plies 3`` ayarı bu
    tabloyu derinleştirmez; eski kod ``str(plies)`` bulunamayınca sıralamanın son
    anahtarını (``static``) döndürüyordu ve "3-ply" ölçümü farkında olmadan 0-ply
    değerini okuyordu (F6-32).
    """
    table = {"static": 0.5, "1": 0.6, "2": 0.7}

    assert G._equity_at(table, 0) == pytest.approx(0.5)
    assert G._equity_at(table, 1) == pytest.approx(0.6)
    assert G._equity_at(table, 2) == pytest.approx(0.7)

    with pytest.raises(ValueError, match="3-ply"):
        G._equity_at(table, 3)
    with pytest.raises(ValueError, match="4-ply"):
        G._equity_at(table, 4)


def test_max_eval_plies_matches_gnubg_contract() -> None:
    """90: ``MAX_EVAL_PLIES`` gnubg'nin belgelenmiş üst sınırıdır."""
    assert G.MAX_EVAL_PLIES == 2
    assert G.DEFAULT_PLIES <= G.MAX_EVAL_PLIES
