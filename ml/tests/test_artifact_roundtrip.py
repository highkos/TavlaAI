"""Artefakt raporlarinin kendi JSON ciktilarindan bayt bayt yeniden uretilebildigini dogrular.

`PHASES.md` §9.1 bu garantiyi belgeler: `ml/artifacts/*.md` dosyalari elle duzenlenmez,
ilgili `.json` ciktisindan uretilir. Bu test, uretici sablonu ile yayimlanan rapor
arasindaki kaymayi yakalar.
"""

from __future__ import annotations

import json
from pathlib import Path

import eval_bench
import gnubg_er
import league
import settings_bench

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def _read(name: str) -> str:
    return (ARTIFACTS / name).read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def _json(name: str) -> dict:
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def test_settings_table_markdown_matches_json() -> None:
    data = _json("settings_table.json")
    rows = [settings_bench.ComboResult(**row) for row in data["rows"]]
    generated = settings_bench.build_markdown(Path(data["model"]), rows, data["seed"])
    assert generated.replace("\r\n", "\n").strip() == _read("settings_table.md")


def test_stage_d_er_markdown_matches_json() -> None:
    data = _json("stage_d_er.json")
    results = [
        gnubg_er.PositionResult(
            name=p["name"],
            turn=p["turn"],
            dice=tuple(p["dice"]),
            afterstate_count=p["afterstateCount"],
            gnubg_best_index=p["gnubgBestIndex"],
            gnubg_best_equity=p["gnubgBestEquity"],
            gnubg_hint_move=p["gnubgHintMove"],
            gnubg_hint_equity=p["gnubgHintEquity"],
            model_afterstate_index=p["modelAfterstateIndex"],
            model_equity=p["modelEquity"],
            equity_loss=p["equityLoss"],
            model_value=p["modelValue"],
            exact_match=p["exactMatch"],
            notes=tuple(p["notes"]),
        )
        for p in data["positions"]
    ]
    generated = gnubg_er.build_markdown(
        results,
        data["skippedCases"],
        model_path=Path(data["model"]),
        gnubg_path=Path(data["gnubg"]),
        gnubg_ver=data["gnubgVersion"],
        plies=data["plies"],
        total_cases=data["totalCases"],
        criterion=data["criterion"],
    )
    assert generated.replace("\r\n", "\n").strip() == _read("stage_d_er.md")


def test_stage_d_eval_markdown_matches_json() -> None:
    data = _json("stage_d_eval.json")
    results = [league.EvalResult.from_dict(r) for r in data["reports"]]
    generated = eval_bench.build_markdown(
        Path(data["model"]),
        results,
        games=200,
        seed=data["seed"],
        depth=data["depthPly"],
        max_root=data["maxCandidatesRoot"],
        max_inner=data["maxCandidatesInner"],
    )
    assert generated.replace("\r\n", "\n").strip() == _read("stage_d_eval.md")
