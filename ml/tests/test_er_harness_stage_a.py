"""Faz 7 Asama A: ``er_harness`` genisletmesi (``--referee hint``, ``--power``).

Test 90 (hakem sozlesmesi), Test 91/92 (hint protokolu) ve Test 124 (guc
sozlesmesi) bu genisletmeye dayanir. gnubg gerektiren yollar ``slow`` isaretlidir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import er_harness
import er_power
import gnubg_er
import gnubg_hint
import proof_corpus

#: Guc sozlesmesinin regresyon degerleri (``ml/artifacts/stage_h_er_2ply.json``).
STAGE_H_MEASUREMENT = er_harness.ML_DIR / "artifacts" / "stage_h_er_2ply.json"
EXPECTED_REQUIRED_N = 1670
EXPECTED_REQUIRED_N_POINT = 1288
EXPECTED_SIGMA = 0.109072
EXPECTED_SIGMA_CI_HIGH = 0.124178


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------


def test_referees_constant() -> None:
    assert er_harness.REFEREES == ("eval", "hint")


def test_proof_corpus_path_is_the_frozen_file() -> None:
    assert er_harness.PROOF_CORPUS_PATH == proof_corpus.PROOF_CORPUS_PATH
    assert er_harness.PROOF_CORPUS_PATH.is_file()


# ---------------------------------------------------------------------------
# measure_split / measure_split_hint
# ---------------------------------------------------------------------------


def test_measure_split_rejects_hint_referee() -> None:
    with pytest.raises(ValueError):
        er_harness.measure_split(
            Path("x.onnx"),
            [],
            split="all",
            gnubg=Path("gnubg"),
            referee="hint",
        )


def test_measure_split_hint_rejects_two_ply() -> None:
    with pytest.raises(ValueError):
        er_harness.measure_split_hint(
            Path("x.onnx"),
            [],
            split="all",
            gnubg=Path("gnubg"),
            plies=2,
        )


def test_measure_split_hint_rejects_five_ply() -> None:
    with pytest.raises(ValueError):
        er_harness.measure_split_hint(
            Path("x.onnx"),
            [],
            split="all",
            gnubg=Path("gnubg"),
            plies=5,
        )


# ---------------------------------------------------------------------------
# _load_measure_cases
# ---------------------------------------------------------------------------


def _measure_args(**overrides):
    args = er_harness.build_parser().parse_args(["measure", "--model", "x.onnx"])
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_load_measure_cases_iteration() -> None:
    cases = er_harness._load_measure_cases(_measure_args())
    assert len(cases) == er_harness.TARGET_POSITIONS


def test_load_measure_cases_proof() -> None:
    args = _measure_args(corpus_kind="proof", corpus=proof_corpus.PROOF_CORPUS_PATH)
    cases = er_harness._load_measure_cases(args)
    assert len(cases) == proof_corpus.TARGET_POSITIONS
    assert all(len(case["afterStates"]) >= 2 for case in cases)


def test_load_measure_cases_proof_rejects_split() -> None:
    args = _measure_args(
        corpus_kind="proof", corpus=proof_corpus.PROOF_CORPUS_PATH, split="cal"
    )
    with pytest.raises(ValueError):
        er_harness._load_measure_cases(args)


# ---------------------------------------------------------------------------
# _cmd_measure hata yollari (gnubg gerekmez)
# ---------------------------------------------------------------------------


def test_cmd_measure_without_gnubg_returns_two(monkeypatch, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: None)
    assert er_harness._cmd_measure(_measure_args()) == 2
    assert "gnubg-cli bulunamadi" in capsys.readouterr().err


def test_cmd_measure_missing_model_returns_two(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: Path("gnubg"))
    args = _measure_args(model=tmp_path / "nope.onnx")
    assert er_harness._cmd_measure(args) == 2
    assert "model bulunamadi" in capsys.readouterr().err


def test_cmd_measure_eval_rejects_three_ply(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: Path("gnubg"))
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    args = _measure_args(model=model, plies=3, referee="eval")
    assert er_harness._cmd_measure(args) == 2
    assert "en fazla 2-ply" in capsys.readouterr().err


def test_cmd_measure_hint_rejects_two_ply(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: Path("gnubg"))
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    args = _measure_args(model=model, plies=2, referee="hint")
    assert er_harness._cmd_measure(args) == 2
    assert "en az 3-ply" in capsys.readouterr().err


def test_cmd_measure_hint_rejects_five_ply(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(gnubg_er, "find_gnubg", lambda explicit=None: Path("gnubg"))
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    args = _measure_args(model=model, plies=5, referee="hint")
    assert er_harness._cmd_measure(args) == 2
    assert "en fazla 4-ply" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _cmd_power (Test 124)
# ---------------------------------------------------------------------------


def _power_args(**overrides):
    args = er_harness.build_parser().parse_args(["power", "--json", str(STAGE_H_MEASUREMENT)])
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_cmd_power_regression_values(tmp_path, capsys) -> None:
    out = tmp_path / "power.json"
    assert er_harness._cmd_power(_power_args(out=out)) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["n"] == 200
    assert payload["sigma"] == pytest.approx(EXPECTED_SIGMA, abs=1e-6)
    assert payload["sigmaCiHigh"] == pytest.approx(EXPECTED_SIGMA_CI_HIGH, abs=1e-6)
    assert payload["requiredN"] == EXPECTED_REQUIRED_N
    assert payload["requiredNPointEstimate"] == EXPECTED_REQUIRED_N_POINT
    assert payload["claim"] == er_power.REFUTED


def test_cmd_power_payload_has_every_required_field(tmp_path) -> None:
    out = tmp_path / "power.json"
    assert er_harness._cmd_power(_power_args(out=out)) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert er_power.validate_er_report(payload) == []
    for name in er_power.ER_REPORT_FIELDS:
        assert name in payload


def test_cmd_power_required_n_uses_upper_bound(tmp_path) -> None:
    out = tmp_path / "power.json"
    assert er_harness._cmd_power(_power_args(out=out)) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["requiredN"] > payload["requiredNPointEstimate"]


def test_cmd_power_appends_sigma_log(tmp_path) -> None:
    log = tmp_path / "er_sigma_log.json"
    assert er_harness._cmd_power(_power_args(sigma_log=log, stage="A")) == 0
    data = json.loads(log.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["stage"] == "A"
    for name in er_power.SIGMA_LOG_FIELDS:
        assert name in entry


def test_cmd_power_appends_without_overwriting(tmp_path) -> None:
    log = tmp_path / "er_sigma_log.json"
    assert er_harness._cmd_power(_power_args(sigma_log=log, stage="A")) == 0
    assert er_harness._cmd_power(_power_args(sigma_log=log, stage="B")) == 0
    data = json.loads(log.read_text(encoding="utf-8"))
    assert [entry["stage"] for entry in data["entries"]] == ["A", "B"]


def test_cmd_power_rejects_invalidated_measurement(tmp_path, capsys) -> None:
    source = json.loads(STAGE_H_MEASUREMENT.read_text(encoding="utf-8"))
    target = tmp_path / "m.json"
    target.write_text(json.dumps(source), encoding="utf-8")
    er_power.invalidate(target, gate="F-A3", reason="test")
    assert er_harness._cmd_power(_power_args(json=target)) == 2
    assert "gecersiz isaretli" in capsys.readouterr().err


def test_cmd_power_rejects_too_few_positions(tmp_path, capsys) -> None:
    target = tmp_path / "m.json"
    target.write_text(
        json.dumps({"model": "m", "positions": [{"equityLoss": 0.1}]}), encoding="utf-8"
    )
    assert er_harness._cmd_power(_power_args(json=target)) == 2
    assert "en az 2 pozisyon" in capsys.readouterr().err


def test_cmd_power_rejects_negative_losses(tmp_path, capsys) -> None:
    target = tmp_path / "m.json"
    target.write_text(
        json.dumps(
            {"model": "m", "positions": [{"equityLoss": 0.1}, {"equityLoss": -0.2}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        er_harness._cmd_power(_power_args(json=target))


# ---------------------------------------------------------------------------
# CLI sozlesmesi
# ---------------------------------------------------------------------------


def test_parser_measure_defaults() -> None:
    args = er_harness.build_parser().parse_args(["measure", "--model", "x.onnx"])
    assert args.referee == "eval"
    assert args.corpus_kind == "iteration"
    assert args.plies == gnubg_er.DEFAULT_PLIES


def test_parser_measure_accepts_hint() -> None:
    args = er_harness.build_parser().parse_args(
        ["measure", "--model", "x.onnx", "--referee", "hint", "--plies", "3"]
    )
    assert args.referee == "hint"
    assert args.plies == 3


def test_parser_power_defaults() -> None:
    args = er_harness.build_parser().parse_args(["power", "--json", "m.json"])
    assert args.target == er_power.CHAMPION_ER_TARGET
    assert args.half_width == 0.005
    assert args.resamples == er_power.BOOTSTRAP_RESAMPLES
    assert args.stage == "A"


def test_parser_rejects_unknown_referee() -> None:
    with pytest.raises(SystemExit):
        er_harness.build_parser().parse_args(
            ["measure", "--model", "x.onnx", "--referee", "static"]
        )


def test_hint_referee_min_plies_matches_gnubg_hint() -> None:
    assert gnubg_hint.HINT_REFEREE_MIN_PLIES == 3
    assert gnubg_hint.HINT_MAX_PLIES == 4


# ---------------------------------------------------------------------------
# Test 90 - hakem derinligi sozlesmesi
# ---------------------------------------------------------------------------


def test_referee_report_fields_constant() -> None:
    assert er_harness.REFEREE_REPORT_FIELDS == ("command", "column", "plies", "prob")


def test_eval_columns_never_contain_three() -> None:
    assert er_harness.EVAL_COLUMNS == ("static", "1", "2")
    assert "3" not in er_harness.EVAL_COLUMNS


@pytest.mark.parametrize("plies,column", [(0, "static"), (1, "1"), (2, "2")])
def test_referee_fields_eval(plies: int, column: str) -> None:
    fields = er_harness.referee_fields("eval", plies)
    assert fields == {
        "command": "eval",
        "column": column,
        "plies": plies,
        "prob": er_harness.EVAL_PROB_FIELD,
    }


def test_referee_fields_eval_rejects_three_ply() -> None:
    with pytest.raises(ValueError):
        er_harness.referee_fields("eval", 3)


@pytest.mark.parametrize("plies", [3, 4])
def test_referee_fields_hint(plies: int) -> None:
    fields = er_harness.referee_fields("hint", plies)
    assert fields == {
        "command": "hint",
        "column": er_harness.HINT_COLUMN,
        "plies": plies,
        "prob": er_harness.HINT_PROB_FIELD,
    }


@pytest.mark.parametrize("plies", [0, 1, 2, 5])
def test_referee_fields_hint_rejects_out_of_range(plies: int) -> None:
    with pytest.raises(ValueError):
        er_harness.referee_fields("hint", plies)


def test_referee_fields_rejects_unknown_referee() -> None:
    with pytest.raises(ValueError):
        er_harness.referee_fields("static", 1)


def test_referee_contract_accepts_eval_report() -> None:
    report = {"command": "eval", "column": "2", "plies": 2, "prob": "equity"}
    assert er_harness.referee_contract(report) == []


def test_referee_contract_accepts_hint_report() -> None:
    report = {"command": "hint", "column": "hint", "plies": 3, "prob": "cubelessEquity"}
    assert er_harness.referee_contract(report) == []


def test_referee_contract_reports_missing_fields() -> None:
    problems = er_harness.referee_contract({"command": "eval"})
    assert len(problems) == 3
    assert all(problem.startswith("eksik alan") for problem in problems)


def test_referee_contract_rejects_eval_three_ply() -> None:
    report = {"command": "eval", "column": "3", "plies": 3, "prob": "equity"}
    problems = er_harness.referee_contract(report)
    assert any("uretemez" in problem for problem in problems)
    assert any("sutunu" in problem for problem in problems)


def test_referee_contract_rejects_eval_wrong_column() -> None:
    report = {"command": "eval", "column": "1", "plies": 2, "prob": "equity"}
    assert any("sutunu" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_eval_wrong_prob() -> None:
    report = {"command": "eval", "column": "2", "plies": 2, "prob": "cubelessEquity"}
    assert any("olasilik" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_hint_two_ply() -> None:
    report = {"command": "hint", "column": "hint", "plies": 2, "prob": "cubelessEquity"}
    assert any("hakem olamaz" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_hint_five_ply() -> None:
    report = {"command": "hint", "column": "hint", "plies": 5, "prob": "cubelessEquity"}
    assert any("uretemez" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_hint_wrong_column() -> None:
    report = {"command": "hint", "column": "2", "plies": 3, "prob": "cubelessEquity"}
    assert any("sutunu" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_hint_wrong_prob() -> None:
    report = {"command": "hint", "column": "hint", "plies": 3, "prob": "equity"}
    assert any("olasilik" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_rejects_unknown_command() -> None:
    report = {"command": "static", "column": "static", "plies": 0, "prob": "equity"}
    assert any("bilinmeyen komut" in problem for problem in er_harness.referee_contract(report))


@pytest.mark.parametrize("plies", [-1, 1.5, True, "2"])
def test_referee_contract_rejects_bad_plies(plies) -> None:
    report = {"command": "eval", "column": "2", "plies": plies, "prob": "equity"}
    assert any("plies" in problem for problem in er_harness.referee_contract(report))


def test_referee_contract_on_real_stage_h_report() -> None:
    report = json.loads(STAGE_H_MEASUREMENT.read_text(encoding="utf-8"))
    report.update(er_harness.referee_fields("eval", int(report["plies"])))
    assert er_harness.referee_contract(report) == []
