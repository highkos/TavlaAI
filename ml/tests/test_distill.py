# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.1.3 / 5.4 - damitma hacmi plani testleri."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import distill  # noqa: E402
from distill import (  # noqa: E402
    CAPPED_BY_TIME,
    CAPPED_BY_VOLUME,
    DEC_DISTILLED,
    DISTILL_DEPTH,
    DISTILL_PARALLEL_SPEEDUP,
    DISTILL_SECONDS_PER_DECISION,
    DISTILL_TIME_CAP_HOURS,
    DISTILL_VOLUME_CAP,
    DistillError,
    DistillPlan,
    build_markdown,
    decisions_per_second,
    estimate_seconds,
    plan_volume,
)


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_volume_cap_is_500k():
    """Kullanici karari: damitma 500 000 karar ile sinirlanir."""
    assert DISTILL_VOLUME_CAP == 500_000


def test_time_cap_is_72_hours():
    assert DISTILL_TIME_CAP_HOURS == 72.0


def test_depth_is_three():
    assert DISTILL_DEPTH == 3


def test_distilled_flag_is_16():
    """Bolum 5.4 / Test 100: DEC_DISTILLED = 16."""
    assert DEC_DISTILLED == 16


def test_cost_model_constants_match_spec():
    """Bolum 5.1.3: 4,07 s/karar, 8x paralel."""
    assert DISTILL_SECONDS_PER_DECISION == pytest.approx(4.07)
    assert DISTILL_PARALLEL_SPEEDUP == pytest.approx(8.0)


# ----------------------------------------------------------------------
# Hiz ve sure
# ----------------------------------------------------------------------


def test_decisions_per_second_matches_spec():
    """4,07 s/karar ve 8x -> 1,97 karar/sn (Bolum 5.1.3)."""
    assert decisions_per_second(4.07, 8.0) == pytest.approx(1.9656, abs=1e-4)


def test_decisions_per_second_rejects_zero_seconds():
    with pytest.raises(DistillError):
        decisions_per_second(0.0, 8.0)


def test_decisions_per_second_rejects_negative_speedup():
    with pytest.raises(DistillError):
        decisions_per_second(4.07, -1.0)


def test_decisions_per_second_rejects_nan():
    with pytest.raises(DistillError):
        decisions_per_second(float("nan"), 8.0)


def test_estimate_seconds_linear():
    assert estimate_seconds(1000, 2.0) == pytest.approx(500.0)


def test_estimate_seconds_rejects_negative_volume():
    with pytest.raises(DistillError):
        estimate_seconds(-1, 2.0)


def test_estimate_seconds_rejects_zero_dps():
    with pytest.raises(DistillError):
        estimate_seconds(10, 0.0)


# ----------------------------------------------------------------------
# Plan
# ----------------------------------------------------------------------


def test_default_plan_fits_72_hours():
    """500 000 karar 72 saate sigar (70,7 saat)."""
    plan = plan_volume()
    assert plan.volume == 500_000
    assert plan.hours < 72.0
    assert plan.hours == pytest.approx(70.7, abs=0.2)
    assert plan.capped_by == CAPPED_BY_VOLUME
    assert plan.feasible is True


def test_plan_never_exceeds_volume_cap():
    plan = plan_volume(volume_cap=500_000, seconds_per_decision=0.1)
    assert plan.volume == 500_000
    assert plan.capped_by == CAPPED_BY_VOLUME


def test_plan_shrinks_to_time_ceiling_when_over():
    """Tavan asilirsa hacim tavana kadar duser, kosu iptal edilmez."""
    plan = plan_volume(volume_cap=2_000_000)
    assert plan.requested == 2_000_000
    assert plan.volume < 2_000_000
    assert plan.hours <= 72.0
    assert plan.capped_by == CAPPED_BY_TIME
    assert plan.feasible is True


def test_plan_two_million_is_infeasible_in_72_hours():
    """Bolum 5.1.3'un duzelttigi hata: 2 M karar 72 saate SIGMAZ."""
    plan = plan_volume(volume_cap=2_000_000)
    assert plan.volume < 2_000_000
    assert plan.hours == pytest.approx(72.0, abs=0.01)


def test_plan_volume_is_floor_of_time_budget():
    dps = decisions_per_second(4.07, 8.0)
    plan = plan_volume(volume_cap=10_000_000)
    assert plan.volume == int(math.floor(72.0 * 3600.0 * dps))


def test_plan_zero_volume_cap_is_infeasible():
    plan = plan_volume(volume_cap=0)
    assert plan.volume == 0
    assert plan.feasible is False
    assert plan.capped_by is None


def test_plan_rejects_negative_volume_cap():
    with pytest.raises(DistillError):
        plan_volume(volume_cap=-1)


def test_plan_rejects_zero_time_cap():
    with pytest.raises(DistillError):
        plan_volume(time_cap_hours=0.0)


def test_plan_rejects_negative_depth():
    with pytest.raises(DistillError):
        plan_volume(depth=-1)


def test_plan_reports_depth():
    assert plan_volume(depth=4).depth == 4


def test_plan_is_deterministic():
    a = plan_volume()
    b = plan_volume()
    assert a.to_dict() == b.to_dict()


def test_plan_to_dict_has_all_fields():
    payload = plan_volume().to_dict()
    for key in (
        "requested",
        "volume",
        "seconds",
        "hours",
        "capped_by",
        "feasible",
        "decisions_per_second",
        "volume_cap",
        "time_cap_hours",
        "depth",
    ):
        assert key in payload


def test_plan_seconds_and_hours_agree():
    plan = plan_volume()
    assert plan.hours == pytest.approx(plan.seconds / 3600.0)


def test_plan_faster_machine_keeps_volume_cap():
    """Daha hizli makine hacmi artirmaz; tavan hacimdir."""
    slow = plan_volume(seconds_per_decision=4.0)   # 2,0 karar/sn -> 518 400 > 500 000
    fast = plan_volume(seconds_per_decision=1.0)
    assert slow.volume == 500_000
    assert fast.volume == 500_000
    assert fast.hours < slow.hours


def test_plan_slower_machine_shrinks_volume():
    plan = plan_volume(seconds_per_decision=20.0)
    assert plan.volume < 500_000
    assert plan.capped_by == CAPPED_BY_TIME


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def test_markdown_mentions_volume_and_hours():
    text = build_markdown(plan_volume())
    assert "500 000" in text
    assert "70,7" in text
    assert "Asama C" in text


def test_markdown_explains_time_cap_when_binding():
    text = build_markdown(plan_volume(volume_cap=2_000_000))
    assert "Sure tavani baglayici" in text
    assert "tavana kadar" in text


def test_markdown_explains_volume_cap_when_binding():
    text = build_markdown(plan_volume())
    assert "Hacim tavani baglayici" in text


def test_markdown_flags_infeasible():
    text = build_markdown(plan_volume(volume_cap=0))
    assert "kosulamaz" in text


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_writes_json_and_markdown(tmp_path):
    json_path = tmp_path / "plan.json"
    md_path = tmp_path / "plan.md"
    code = distill.main(["--json", str(json_path), "--markdown", str(md_path)])
    assert code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["volume"] == 500_000
    assert md_path.read_text(encoding="utf-8").startswith("# Asama C")


def test_cli_returns_nonzero_when_infeasible(tmp_path):
    code = distill.main(["--volume-cap", "0", "--json", str(tmp_path / "p.json")])
    assert code == 1


def test_cli_accepts_measured_cost(tmp_path):
    json_path = tmp_path / "plan.json"
    distill.main(
        [
            "--seconds-per-decision", "3.2",
            "--parallel-speedup", "6",
            "--json", str(json_path),
        ]
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["decisions_per_second"] == pytest.approx(6.0 / 3.2)
    # 1,875 karar/sn x 72 saat = 486 000 karar; sure tavani baglayici.
    assert payload["volume"] == 486_000
    assert payload["capped_by"] == CAPPED_BY_TIME
