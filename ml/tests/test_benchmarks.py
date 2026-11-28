"""Faz 8 Görev 2: plan etiketli sabit kıyaslama paneli ve model envanteri (Test 436-447).

Panelin sözleşmesi:

* plan sınıflandırıcısı **deterministik** ve altı planı da üretir,
* set üretimi aynı tohumla **bayt-özdeş** dosya verir,
* set hash'i içeriğe duyarlıdır (sıra ve değer değişince değişir),
* ölçüm günlüğü **yalnızca ekleme** yapılır; aynı kayıt iki kez yazılamaz,
* markdown tablosu JSON ile **birebir** uyuşur,
* envanter eksik modeli **alarm** olarak bildirir (kırmızı çizgi G9).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
REPO = ML.parent
for path in (str(ML), str(REPO)):
    if path not in sys.path:
        sys.path.insert(0, path)

import benchmarks  # noqa: E402
import gnubg_er  # noqa: E402
from tools import reference_gen as refgen  # noqa: E402


# ----------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------


def _race_board() -> list[int]:
    """Temiz yarış: beyaz 19-24, siyah 1-6 (temas yok)."""
    board = [0] * refgen.BOARD_SIZE
    for point in range(19, 25):
        board[point] = 3 if point >= 22 else 2
    for point in range(1, 7):
        board[point] = -3 if point <= 3 else -2
    return board


def _backgame_board() -> list[int]:
    """Beyaz'ın rakibin evinde 3 anchor'ı + 12 arka pulu var."""
    board = [0] * refgen.BOARD_SIZE
    for point in range(1, 7):
        board[point] = 2
    board[7] = 3
    for point in range(19, 25):
        board[point] = -2
    board[18] = -3
    return board


def _priming_board() -> list[int]:
    """Beyaz'ın 4'lük prime'ı (punto 18-21) ve Siyah'ın geçmesi gereken pulu var."""
    board = [0] * refgen.BOARD_SIZE
    # Beyaz prime: punto 18,19,20,21 (Beyaz için uzaklık 7,6,5,4)
    for point in (18, 19, 20, 21):
        board[point] = 2
    board[24] = 3
    board[23] = 4
    # Siyah'ın prime'ı geçmesi gereken pulları: punto 22,23,24 (Beyaz'ın evi tarafı)
    board[22] = -3
    board[10] = -4
    board[5] = -4
    board[1] = -4
    return board


def _case(board: list[int], turn: int = 1, dice: list[int] | None = None) -> dict:
    return {
        "name": "x",
        "board": list(board),
        "turn": turn,
        "dice": list(dice or [3, 1]),
        "whiteOff": 0,
        "blackOff": 0,
    }


def _record(model_path: str, sha: str = "a" * 64, mean: float = 0.1) -> dict:
    return {
        "recordId": "%s|%s|policy|2|2026-01-01T00:00:00Z" % (model_path, sha[:16]),
        "timestamp": "2026-01-01T00:00:00Z",
        "model": {"path": model_path, "sha256": sha, "sizeBytes": 1, "outputVersion": 2},
        "criterion": "policy",
        "plies": 2,
        "benchVersion": benchmarks.BENCH_VERSION,
        "sets": {
            "contact": {
                "setHash": "b" * 64,
                "count": 4,
                "mean": mean,
                "median": mean,
                "max": mean * 2,
                "exactMatchRate": 0.5,
                "skipped": [],
                "perPlan": {"attacking": {"count": 4, "mean": mean, "max": mean * 2}},
            }
        },
    }


# ----------------------------------------------------------------------
# 436-438: plan sınıflandırıcısı
# ----------------------------------------------------------------------


def test_436_classify_plan_is_deterministic_and_covers_all_plans():
    """Aynı pozisyon her zaman aynı etiketi alır; altı planın hepsi üretilebilir."""
    boards = {
        "purerace": _race_board(),
        "backgame": _backgame_board(),
        "priming": _priming_board(),
    }
    for expected, board in boards.items():
        first = benchmarks.classify_plan(board, 1)
        for _ in range(5):
            assert benchmarks.classify_plan(board, 1) == first
        assert first == expected, "%s bekleniyordu, %s geldi" % (expected, first)

    # Başlangıç pozisyonu temas planıdır (ne yarış ne purerace).
    assert benchmarks.classify_plan(refgen.START_BOARD, 1) == "attacking"
    assert benchmarks.classify_plan(refgen.START_BOARD, -1) == "attacking"

    # Renk takası etiketi değiştirmemeli (antisimetri).
    flipped = [-v for v in refgen.START_BOARD]
    assert benchmarks.classify_plan(flipped, -1) == "attacking"

    assert set(benchmarks.PLANS) == {
        "purerace",
        "racing",
        "attacking",
        "priming",
        "anchoring",
        "backgame",
    }


def test_437_classify_plan_rejects_bad_turn():
    with pytest.raises(benchmarks.BenchmarkError):
        benchmarks.classify_plan(refgen.START_BOARD, 0)


def test_438_plan_helpers_agree_with_board_geometry():
    """``anchor_count``/``back_checkers``/``home_points`` punto geometrisiyle uyumlu."""
    board = _backgame_board()
    assert benchmarks.anchor_count(board, 1) == 6
    assert benchmarks.back_checkers(board, 1) == 12
    assert benchmarks.home_points(board, 1) == 0
    # Siyah'ın evi 1..6; orada Beyaz'ın 12 pulu var, Siyah'ın punto'su yok.
    assert benchmarks.anchor_count(board, -1) == 6
    assert benchmarks.home_points(board, -1) == 0
    assert benchmarks.back_checkers(board, -1) == 12
    assert benchmarks.prime_points(_priming_board(), 1) == (21, 20, 19, 18)
    assert benchmarks.prime_front(_priming_board(), 1) == 4
    assert benchmarks.prime_points(refgen.START_BOARD, 1) == ()


# ----------------------------------------------------------------------
# 439-441: set üretimi ve hash
# ----------------------------------------------------------------------


def test_439_build_sets_is_byte_identical_for_same_seed(tmp_path):
    """Aynı tohum + aynı kaynak -> bayt-özdeş dosya (test 437'nin dosya düzeyi)."""
    source = tmp_path / "src.json"
    cases = [
        _case(_race_board()),
        _case(_backgame_board()),
        _case(_priming_board()),
        _case(refgen.START_BOARD),
    ]
    source.write_text(json.dumps({"cases": cases}), encoding="utf-8")

    first = benchmarks.build_sets((source,), per_plan=2, seed=7)
    second = benchmarks.build_sets((source,), per_plan=2, seed=7)
    assert first["setHashes"] == second["setHashes"]
    assert first["cases"] == second["cases"]

    path_a = benchmarks.write_sets(first, tmp_path / "a.json")
    path_b = benchmarks.write_sets(second, tmp_path / "b.json")
    assert path_a.read_bytes() == path_b.read_bytes()


def test_440_build_sets_reports_shortfall_instead_of_silently_shrinking(tmp_path):
    source = tmp_path / "src.json"
    source.write_text(json.dumps({"cases": [_case(_race_board())]}), encoding="utf-8")
    data = benchmarks.build_sets((source,), per_plan=5, seed=1)
    assert data["shortfall"]["purerace"] == 4
    assert data["planCounts"]["purerace"] == 1
    assert data["planCounts"]["backgame"] == 0


def test_441_set_hash_is_order_and_content_sensitive():
    a = [{"name": "a", "plan": "racing"}]
    b = [{"name": "b", "plan": "racing"}]
    assert benchmarks.set_hash(a) == benchmarks.set_hash(list(a))
    assert benchmarks.set_hash(a) != benchmarks.set_hash(b)
    assert benchmarks.set_hash(a) != benchmarks.set_hash(a + a)
    # Sıra değişince hash değişir (set kimliği sıraya bağlıdır).
    two = [{"name": "a"}, {"name": "b"}]
    assert benchmarks.set_hash(two) != benchmarks.set_hash(list(reversed(two)))


# ----------------------------------------------------------------------
# 442-444: doğrulama
# ----------------------------------------------------------------------


def test_442_verify_sets_detects_tampered_plan_label(tmp_path):
    source = tmp_path / "src.json"
    source.write_text(
        json.dumps({"cases": [_case(_race_board()), _case(_backgame_board())]}),
        encoding="utf-8",
    )
    data = benchmarks.build_sets((source,), per_plan=1, seed=3)
    assert benchmarks.verify_sets(data) == []

    tampered = json.loads(json.dumps(data))
    tampered["cases"][0]["plan"] = "backgame" if tampered["cases"][0]["plan"] != "backgame" else "racing"
    problems = benchmarks.verify_sets(tampered)
    assert any("plan etiketi degisti" in p for p in problems)
    assert any("hash uyusmuyor" in p for p in problems)


def test_443_verify_sets_detects_missing_afterstates(tmp_path):
    source = tmp_path / "src.json"
    source.write_text(json.dumps({"cases": [_case(_race_board())]}), encoding="utf-8")
    data = benchmarks.build_sets((source,), per_plan=1, seed=3)
    data["cases"][0]["afterStates"] = []
    assert any("afterStates bos" in p for p in benchmarks.verify_sets(data))


def test_444_load_sets_rejects_wrong_version_and_unknown_set(tmp_path):
    path = tmp_path / "sets.json"
    path.write_text(json.dumps({"benchVersion": 999, "cases": []}), encoding="utf-8")
    with pytest.raises(benchmarks.BenchmarkError):
        benchmarks.load_sets(path)

    with pytest.raises(benchmarks.BenchmarkError):
        benchmarks.cases_for_set({"cases": []}, "yok-boyle-set")

    with pytest.raises(benchmarks.BenchmarkError):
        benchmarks.load_sets(tmp_path / "missing.json")


# ----------------------------------------------------------------------
# 445-446: ölçüm günlüğü
# ----------------------------------------------------------------------


def test_445_append_benchmark_is_append_only(tmp_path):
    path = tmp_path / "bench.json"
    first = _record("ml/runs/a/model.onnx", "a" * 64, 0.10)
    second = _record("ml/runs/b/model.onnx", "b" * 64, 0.20)

    benchmarks.append_benchmark(first, path)
    benchmarks.append_benchmark(second, path)
    records = benchmarks.load_benchmarks(path)
    assert [r["model"]["path"] for r in records] == [
        "ml/runs/a/model.onnx",
        "ml/runs/b/model.onnx",
    ]
    # İlk kayıt değişmedi.
    assert records[0] == first

    with pytest.raises(benchmarks.BenchmarkError):
        benchmarks.append_benchmark(first, path)
    assert len(benchmarks.load_benchmarks(path)) == 2


def test_446_bench_markdown_matches_json(tmp_path):
    path = tmp_path / "bench.json"
    benchmarks.append_benchmark(_record("ml/runs/a/model.onnx", "a" * 64, 0.10), path)
    benchmarks.append_benchmark(_record("ml/runs/b/model.onnx", "b" * 64, 0.20), path)
    records = benchmarks.load_benchmarks(path)

    markdown = benchmarks.build_bench_markdown(records)
    main_table = markdown.split("## Plan kırılımı")[0]
    rows = [line for line in main_table.splitlines() if line.startswith("| ") and "---" not in line]
    data_rows = [r for r in rows if not r.startswith("| # ")]
    expected = sum(len(r["sets"]) for r in records)
    assert len(data_rows) == expected

    for record in records:
        for name, summary in record["sets"].items():
            assert "%.4f" % summary["mean"] in markdown
            assert name in markdown
            assert record["model"]["path"] in markdown
            assert str(summary["setHash"])[:12] in markdown


# ----------------------------------------------------------------------
# 447: envanter (kırmızı çizgi G9)
# ----------------------------------------------------------------------


def test_447_inventory_flags_missing_models_and_records_sha256(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    model = root / "model.onnx"
    model.write_bytes(b"not-a-real-onnx")

    assumptions = tmp_path / "ASSUMPTIONS.md"
    assumptions.write_text(
        "## F7-001 — bir kayit\n\n`runs/model.onnx` olculdu.\n\n"
        "## F7-002 — baska kayit\n\nbaska sey.\n",
        encoding="utf-8",
    )

    benchmarks_records = [
        _record("runs/model.onnx", benchmarks.file_sha256(model)),
        _record("runs/silinen/model.onnx", "c" * 64),
    ]

    inventory = benchmarks.build_inventory(
        roots=(root,),
        benchmarks=benchmarks_records,
        assumptions=assumptions,
        repo_root=tmp_path,
    )
    assert inventory["count"] == 1
    entry = inventory["entries"][0]
    assert entry["sha256"] == benchmarks.file_sha256(model)
    assert entry["sizeBytes"] == model.stat().st_size
    # Bozuk ONNX okunamaz ama envanterde görünür.
    assert entry["outputVersion"] == -1
    assert entry["note"]
    assert entry["fRecords"] == ["F7-001"]
    assert entry["panelRows"] == [1]

    assert inventory["alarm"] is True
    assert [m["path"] for m in inventory["missing"]] == ["runs/silinen/model.onnx"]

    markdown = benchmarks.build_inventory_markdown(inventory)
    assert "**VAR**" in markdown
    assert "runs/silinen/model.onnx" in markdown
    assert entry["sha256"][:12] in markdown
