# -*- coding: utf-8 -*-
"""Faz 7-S - large/xlarge kapasite profilleri, siralama kafasi ve veri dilimleri."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import capacity_train  # noqa: E402
import gnubg_distill  # noqa: E402
import model_large  # noqa: E402
import model_xlarge  # noqa: E402
from model import (  # noqa: E402
    CAPACITY_PROFILES,
    PROB_COUNT,
    VECTOR_SIZE,
    build_model,
    parameter_count,
)

torch = pytest.importorskip("torch")


# ----------------------------------------------------------------------
# Profil tanimlari
# ----------------------------------------------------------------------


def test_profiles_match_plan():
    """Faz 7-S plani: large 512-512-512, xlarge 1024-1024-512."""
    assert CAPACITY_PROFILES["large"] == (512, 512, 512)
    assert CAPACITY_PROFILES["xlarge"] == (1024, 1024, 512)
    assert model_large.HIDDEN == CAPACITY_PROFILES["large"]
    assert model_xlarge.HIDDEN == CAPACITY_PROFILES["xlarge"]


def test_parameter_counts():
    """large ~642K, xlarge ~1.8M (planda 1.9M deniyor; fark 7. cikti)."""
    large = parameter_count(build_model(output_version=2, profile="large"))
    xlarge = parameter_count(build_model(output_version=2, profile="xlarge"))
    assert large == 642_567
    assert xlarge == 1_805_319
    assert 600_000 < large < 700_000
    assert 1_700_000 < xlarge < 2_000_000


def test_wrappers_build_same_model_as_build_model():
    """Sarmalayicilar ayri mimari tutmaz; ayni state_dict anahtarlarini uretir."""
    for wrapper, profile in (
        (model_large.build_large, "large"),
        (model_xlarge.build_xlarge, "xlarge"),
    ):
        a = wrapper(seed=0)
        b = build_model(VECTOR_SIZE, seed=0, output_version=2, profile=profile)
        assert list(a.state_dict()) == list(b.state_dict())
        for key, tensor in a.state_dict().items():
            assert tensor.shape == b.state_dict()[key].shape


def test_wrapper_forward_contract_is_two_outputs():
    """Siralama kafasi kapaliyken sozlesme degismez: (probs, policy_logit)."""
    for wrapper in (model_large.build_large, model_xlarge.build_xlarge):
        net = wrapper(seed=0)
        out = net(torch.zeros(3, VECTOR_SIZE))
        assert len(out) == 2
        probs, logits = out
        assert probs.shape == (3, PROB_COUNT)
        assert logits.shape == (3, 1)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_rank_head_adds_third_output_only_when_requested():
    net = model_xlarge.build_xlarge(seed=0, rank_head=True)
    out = net(torch.zeros(2, VECTOR_SIZE))
    assert len(out) == 3
    assert out[2].shape == (2, 1)
    assert net.rank_head is not None

    plain = model_xlarge.build_xlarge(seed=0)
    assert plain.rank_head is None
    assert len(plain(torch.zeros(2, VECTOR_SIZE))) == 2


def test_rank_head_rejected_for_output_version_one():
    with pytest.raises(ValueError):
        build_model(output_version=1, rank_head=True)


def test_strip_rank_head_keeps_export_contract():
    """Ihracat oncesi ayiklama, siralama kafasiz modelin anahtarlarini verir."""
    trained = model_large.build_large(seed=0, rank_head=True)
    stripped = capacity_train._strip_rank_head(trained.state_dict())
    plain = model_large.build_large(seed=0)
    assert set(stripped) == set(plain.state_dict())
    assert not any(k.startswith("rank_head.") for k in stripped)


# ----------------------------------------------------------------------
# Siralama kaybi
# ----------------------------------------------------------------------


def _toy_dataset(n: int = 12, width: int = 5, *, dist: bool = False):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n * width, VECTOR_SIZE)).astype(np.float32)
    offsets = np.arange(0, (n + 1) * width, width, dtype=np.int64)
    best = rng.integers(0, width, size=n).astype(np.int32)
    y = rng.normal(size=n).astype(np.float32)
    return gnubg_distill.PolicyDataset(
        x=x,
        offsets=offsets,
        best=best,
        y=y,
        meta={"kind": "policy"},
        dist=(
            rng.dirichlet(np.ones(PROB_COUNT), size=n).astype(np.float32)
            if dist
            else None
        ),
    )


def test_rank_weight_requires_rank_head():
    net = model_large.build_large(seed=0)
    with pytest.raises(ValueError):
        gnubg_distill.train_policy_head(
            net, _toy_dataset(), steps=2, batch=4, rank_weight=0.5
        )


def test_rank_weight_trains_and_reports():
    net = model_large.build_large(seed=0, rank_head=True)
    report = gnubg_distill.train_policy_head(
        net, _toy_dataset(), steps=20, batch=4, rank_weight=0.5, seed=0
    )
    assert report["rankWeight"] == pytest.approx(0.5)
    assert report["stepsRun"] == 20
    assert np.isfinite(report["lastLoss"])


def test_rank_loss_decreases_on_separable_data():
    """Siralama terimi ogrenilebilir bir sinyali gercekten dusurur."""
    net = model_large.build_large(seed=0, rank_head=True)
    data = _toy_dataset(n=32, width=4)
    report = gnubg_distill.train_policy_head(
        net, data, steps=300, batch=16, rank_weight=1.0, value_weight=0.0, seed=0
    )
    history = report["history"]
    assert np.mean(history[-20:]) < np.mean(history[:20])


# ----------------------------------------------------------------------
# Dogrulama ayrimi ve erken durdurma
# ----------------------------------------------------------------------


def test_val_fraction_splits_deterministically():
    data = _toy_dataset(n=40, width=3)
    net = model_large.build_large(seed=0)
    a = gnubg_distill.train_policy_head(
        net, data, steps=4, batch=4, val_fraction=0.25, eval_every=2, seed=7
    )
    net2 = model_large.build_large(seed=0)
    b = gnubg_distill.train_policy_head(
        net2, data, steps=4, batch=4, val_fraction=0.25, eval_every=2, seed=7
    )
    assert a["valCount"] == b["valCount"] == 10
    assert a["trainCount"] == b["trainCount"] == 30
    assert a["valHistory"] == b["valHistory"]


def test_val_fraction_rejects_full_split():
    net = model_large.build_large(seed=0)
    with pytest.raises(ValueError):
        gnubg_distill.train_policy_head(
            net, _toy_dataset(), steps=2, batch=4, val_fraction=1.0
        )


def test_patience_stops_early_and_restores_best():
    net = model_large.build_large(seed=0)
    report = gnubg_distill.train_policy_head(
        net,
        _toy_dataset(n=16, width=3),
        steps=200,
        batch=4,
        val_fraction=0.25,
        patience=1,
        eval_every=1,
        seed=0,
    )
    assert report["stepsRun"] <= 200
    assert report["bestStep"] >= 1
    assert report["bestValCe"] is not None


# ----------------------------------------------------------------------
# Veri dilimleri
# ----------------------------------------------------------------------


def test_subset_preserves_candidates_and_labels():
    data = _toy_dataset(n=10, width=4, dist=True)
    sub = data.subset([1, 4, 7])
    assert len(sub) == 3
    assert sub.has_dist()
    for new_i, old_i in enumerate([1, 4, 7]):
        assert np.array_equal(sub.candidates(new_i), data.candidates(old_i))
        assert int(sub.best[new_i]) == int(data.best[old_i])
        assert float(sub.y[new_i]) == pytest.approx(float(data.y[old_i]))
        assert np.allclose(sub.dist[new_i], data.dist[old_i])


def test_subset_rejects_out_of_range():
    data = _toy_dataset(n=4, width=2)
    with pytest.raises(IndexError):
        data.subset([0, 9])


def test_concat_policy_datasets_roundtrip():
    a = _toy_dataset(n=5, width=3, dist=True)
    b = _toy_dataset(n=7, width=3, dist=True)
    merged = gnubg_distill.concat_policy_datasets([a, b])
    assert len(merged) == 12
    assert merged.has_dist()
    assert int(merged.offsets[-1]) == int(a.offsets[-1]) + int(b.offsets[-1])
    assert np.array_equal(merged.candidates(0), a.candidates(0))
    assert np.array_equal(merged.candidates(5), b.candidates(0))
    assert merged.meta["shards"] == 2


def test_concat_drops_dist_when_shards_disagree():
    a = _toy_dataset(n=3, width=2, dist=True)
    b = _toy_dataset(n=3, width=2, dist=False)
    merged = gnubg_distill.concat_policy_datasets([a, b])
    assert not merged.has_dist()


def test_concat_rejects_empty():
    with pytest.raises(ValueError):
        gnubg_distill.concat_policy_datasets([])


# ----------------------------------------------------------------------
# Karar kurali
# ----------------------------------------------------------------------


def test_decide_requires_threshold_gain():
    rows = [
        {"profile": "medium", "valueEr": 0.040},
        {"profile": "large", "valueEr": 0.039},  # %2.5 kazanc: esik alti
    ]
    result = capacity_train.decide(rows)
    assert result["available"] is True
    assert result["winner"] is None
    assert result["arms"][0]["meetsThreshold"] is False


def test_decide_picks_winner_above_threshold():
    rows = [
        {"profile": "medium", "valueEr": 0.040},
        {"profile": "large", "valueEr": 0.030},  # %25 kazanc
        {"profile": "xlarge", "valueEr": 0.032},
    ]
    result = capacity_train.decide(rows)
    assert result["winner"] == "large"
    assert result["arms"][0]["profile"] == "large"


def test_decide_without_baseline():
    result = capacity_train.decide([{"profile": "large", "valueEr": 0.03}])
    assert result["available"] is False
    assert result["winner"] is None


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def test_markdown_contains_every_profile():
    rows = [
        {
            "profile": "medium",
            "params": 156_423,
            "hidden": [256, 256, 128],
            "elapsedSeconds": 12.0,
            "valTop1": 0.5,
            "valueEr": 0.04,
            "valueSe": 0.001,
            "search1Er": 0.02,
            "search1Se": 0.0005,
            "policyEr": 0.05,
            "policySe": 0.002,
            "antisymmetryCorr": -0.7,
            "antisymmetryMeanAbsSum": 0.1,
            "stoppedEarly": True,
        }
    ]
    text = capacity_train.build_markdown(rows, corpus="v2", plies=2)
    assert "medium" in text
    assert "156.423" in text
    assert "0.040000" in text
    assert "evet" in text


# ----------------------------------------------------------------------
# Ogrenme orani zamanlamasi ve L2
# ----------------------------------------------------------------------


def test_lr_schedule_rejects_unknown_name():
    net = model_large.build_large(seed=0)
    with pytest.raises(ValueError):
        gnubg_distill.train_policy_head(
            net, _toy_dataset(), steps=2, batch=4, lr_schedule="step"
        )


def test_lr_final_ratio_must_be_positive():
    net = model_large.build_large(seed=0)
    with pytest.raises(ValueError):
        gnubg_distill.train_policy_head(
            net, _toy_dataset(), steps=2, batch=4, lr_schedule="cosine", lr_final_ratio=0.0
        )


def test_cosine_schedule_and_weight_decay_are_reported():
    net = model_large.build_large(seed=0)
    report = gnubg_distill.train_policy_head(
        net,
        _toy_dataset(),
        steps=6,
        batch=4,
        weight_decay=1e-4,
        lr_schedule="cosine",
        lr_final_ratio=0.2,
        seed=0,
    )
    assert report["lrSchedule"] == "cosine"
    assert report["weightDecay"] == pytest.approx(1e-4)
    assert report["lrFinalRatio"] == pytest.approx(0.2)
    assert np.isfinite(report["lastLoss"])


def test_weight_decay_shrinks_weights_relative_to_plain_adam():
    """L2 cezasi ayni veri/adimda agirlik normunu kucultmelidir."""
    data = _toy_dataset(n=16, width=3)
    plain = model_large.build_large(seed=0)
    gnubg_distill.train_policy_head(plain, data, steps=40, batch=8, seed=0)
    decayed = model_large.build_large(seed=0)
    gnubg_distill.train_policy_head(
        decayed, data, steps=40, batch=8, weight_decay=1e-1, seed=0
    )

    def _norm(net) -> float:
        return float(
            sum(p.detach().pow(2).sum().item() for p in net.parameters()) ** 0.5
        )

    assert _norm(decayed) < _norm(plain)


# ----------------------------------------------------------------------
# Parti basina genislik (duzensiz aday kumeleri)
# ----------------------------------------------------------------------


def test_ragged_batches_use_their_own_width():
    """Global genislige yastiklamak yerine parti kendi genisligine kirpilir.

    Ayni veri kumesinde tek bir cok-genis pozisyon varsa, eski kod her adimi o
    genislikte hesapliyordu. Sonuc degismemeli, yalnizca maliyet dusmeli.
    """
    rng = np.random.default_rng(3)
    widths = [2, 2, 2, 2, 2, 2, 2, 2, 2, 40]
    offsets = np.concatenate([[0], np.cumsum(widths)]).astype(np.int64)
    n = len(widths)
    data = gnubg_distill.PolicyDataset(
        x=rng.normal(size=(int(offsets[-1]), VECTOR_SIZE)).astype(np.float32),
        offsets=offsets,
        best=np.zeros(n, dtype=np.int32),
        y=rng.normal(size=n).astype(np.float32),
        meta={"kind": "policy"},
    )
    net = model_large.build_large(seed=0)
    report = gnubg_distill.train_policy_head(
        net, data, steps=5, batch=4, val_fraction=0.2, eval_every=5, seed=0
    )
    assert report["width"] == 40
    assert np.isfinite(report["valCe"])


# ----------------------------------------------------------------------
# Parite toleransi
# ----------------------------------------------------------------------


def test_parity_policy_tolerance_scales_with_logit_magnitude():
    """Politika logit'i sinirsiz; mutlak 1e-5 esigi egitilmis modelde yetmez."""
    import export_onnx

    assert export_onnx.PARITY_RELATIVE_TOLERANCE > 0
    # |logit| = 50 icin etkin esik mutlak esigin uzerine cikmali.
    effective = max(
        export_onnx.PARITY_TOLERANCE, export_onnx.PARITY_RELATIVE_TOLERANCE * 50.0
    )
    assert effective > export_onnx.PARITY_TOLERANCE


# ----------------------------------------------------------------------
# measure --reuse
# ----------------------------------------------------------------------


def test_measure_reuse_reads_existing_artifacts(tmp_path):
    import json

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "model.onnx").write_bytes(b"")
    (run_dir / "er_paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "policy": {"mean": 0.01, "standardError": 0.001, "exactMatchRate": 0.6},
                    "value": {"mean": 0.02, "standardError": 0.002, "exactMatchRate": 0.5},
                    "search1": {"mean": 0.03, "standardError": 0.003, "exactMatchRate": 0.4},
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "antisymmetry.json").write_text(
        json.dumps({"correlation": -0.9, "meanAbsSum": 0.2}), encoding="utf-8"
    )
    (run_dir / "capacity.json").write_text(
        json.dumps(
            {
                "profile": "large",
                "row": {},
                "train": {"profile": "large", "params": 642_567},
                "parity": {"maxAbsDeltaValue": 1e-7},
                "measurement": None,
            }
        ),
        encoding="utf-8",
    )

    code = capacity_train.main(
        ["measure", "--out-dir", str(run_dir), "--reuse", "--quiet"]
    )
    assert code == 0
    payload = json.loads((run_dir / "capacity.json").read_text(encoding="utf-8"))
    assert payload["row"]["policyEr"] == pytest.approx(0.01)
    assert payload["row"]["policySe"] == pytest.approx(0.001)
    assert payload["row"]["search1Er"] == pytest.approx(0.03)
    assert payload["row"]["antisymmetryCorr"] == pytest.approx(-0.9)
    assert payload["row"]["params"] == 642_567


def test_measure_reuse_requires_capacity_json(tmp_path):
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    assert capacity_train.main(["measure", "--out-dir", str(run_dir), "--reuse", "--quiet"]) == 2


# ----------------------------------------------------------------------
# Karar: search1 kazanci
# ----------------------------------------------------------------------


def test_decide_reports_search1_gain_alongside_value_gain():
    rows = [
        {"profile": "medium", "valueEr": 0.040, "search1Er": 0.026},
        {"profile": "large", "valueEr": 0.036, "search1Er": 0.022},
    ]
    decision = capacity_train.decide(rows)
    arm = decision["arms"][0]
    assert arm["profile"] == "large"
    assert arm["relativeGain"] == pytest.approx(0.10)
    assert arm["search1RelativeGain"] == pytest.approx(0.026 / 0.026 - 0.022 / 0.026)
    assert arm["meetsThreshold"] is False


def test_decide_tolerates_missing_search1():
    rows = [
        {"profile": "medium", "valueEr": 0.040},
        {"profile": "large", "valueEr": 0.030},
    ]
    decision = capacity_train.decide(rows)
    assert decision["arms"][0]["search1RelativeGain"] is None
    assert decision["winner"] == "large"


def test_report_appends_notes(tmp_path):
    import json

    run = tmp_path / "capacity.json"
    run.write_text(
        json.dumps(
            {
                "profile": "medium",
                "row": {"profile": "medium", "valueEr": 0.04, "search1Er": 0.02},
            }
        ),
        encoding="utf-8",
    )
    notes = tmp_path / "notes.md"
    notes.write_text("## Yorum\r\n\r\nelle yazildi\r\n", encoding="utf-8")
    out = tmp_path / "report.md"
    code = capacity_train.main(
        [
            "report",
            "--run",
            str(run),
            "--markdown",
            str(out),
            "--notes",
            str(notes),
            "--quiet",
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "## Yorum" in text
    assert "elle yazildi" in text
    assert "\r" not in text

# ----------------------------------------------------------------------
# R-E: coklu tohum (sweep) ve eslesmis bootstrap (compare)
# ----------------------------------------------------------------------


def test_311_parse_seeds_accepts_list_and_rejects_duplicates():
    assert capacity_train._parse_seeds("0,1,2") == [0, 1, 2]
    assert capacity_train._parse_seeds(" 3 , 7 ") == [3, 7]
    with pytest.raises(ValueError):
        capacity_train._parse_seeds("0,0")
    with pytest.raises(ValueError):
        capacity_train._parse_seeds(" , ")


def test_312_aggregate_sweep_reports_mean_sd_and_se():
    rows = [
        {"seed": 0, "valueEr": 0.040, "search1Er": 0.020},
        {"seed": 1, "valueEr": 0.042, "search1Er": 0.021},
        {"seed": 2, "valueEr": 0.041, "search1Er": 0.019},
    ]
    summary = capacity_train.aggregate_sweep(rows)
    assert summary["count"] == 3
    assert summary["seeds"] == [0, 1, 2]
    value = summary["metrics"]["valueEr"]
    assert value["mean"] == pytest.approx(0.041)
    assert value["sd"] == pytest.approx(0.001)
    assert value["se"] == pytest.approx(0.001 / 3 ** 0.5)
    assert value["min"] == pytest.approx(0.040)
    assert value["max"] == pytest.approx(0.042)


def test_313_aggregate_sweep_single_seed_has_no_spread():
    summary = capacity_train.aggregate_sweep([{"seed": 0, "valueEr": 0.04}])
    assert summary["metrics"]["valueEr"]["sd"] is None
    assert summary["metrics"]["valueEr"]["se"] is None
    assert capacity_train.aggregate_sweep([])["count"] == 0


def test_314_paired_bootstrap_detects_shift_and_keeps_pairing():
    import random

    rng = random.Random(7)
    control = [[rng.gauss(0.04, 0.01) for _ in range(300)] for _ in range(3)]
    treatment = [[c - 0.002 for c in row] for row in control]
    result = capacity_train.paired_bootstrap(control, treatment, resamples=400)
    assert result["diff"] == pytest.approx(-0.002, abs=1e-12)
    assert result["ciHigh"] < 0.0
    assert result["significant"] is True
    assert result["seeds"] == 3
    assert result["cases"] == 300


def test_315_paired_bootstrap_null_is_not_significant():
    import random

    rng = random.Random(11)
    control = [[rng.gauss(0.04, 0.01) for _ in range(300)] for _ in range(3)]
    treatment = [[rng.gauss(0.04, 0.01) for _ in range(300)] for _ in range(3)]
    result = capacity_train.paired_bootstrap(control, treatment, resamples=400)
    assert result["significant"] is False
    assert result["ciLow"] < 0.0 < result["ciHigh"]


def test_316_paired_bootstrap_rejects_mismatched_shapes():
    with pytest.raises(ValueError):
        capacity_train.paired_bootstrap([[0.1, 0.2]], [[0.1, 0.2], [0.1, 0.2]])
    with pytest.raises(ValueError):
        capacity_train.paired_bootstrap([[0.1, 0.2]], [[0.1]])
    with pytest.raises(ValueError):
        capacity_train.paired_bootstrap([], [])


def _write_sweep_seed(root, seed, *, value, search1, cases=4):
    import json

    seed_dir = root / ("seed%d" % seed)
    seed_dir.mkdir(parents=True)
    losses = {
        "policy": [value] * cases,
        "value": [value] * cases,
        "search1": [search1] * cases,
    }
    (seed_dir / "er_paths.json").write_text(
        json.dumps({"caseLosses": losses, "caseNames": ["c%d" % i for i in range(cases)]}),
        encoding="utf-8",
    )
    return seed_dir


def test_317_compare_sweeps_uses_per_case_losses(tmp_path):
    import json

    control = tmp_path / "medium"
    treatment = tmp_path / "large"
    for seed in (0, 1, 2):
        _write_sweep_seed(control, seed, value=0.040, search1=0.026)
        _write_sweep_seed(treatment, seed, value=0.036, search1=0.022)
    out = tmp_path / "compare.json"
    md = tmp_path / "compare.md"
    code = capacity_train.main(
        [
            "compare",
            "--control",
            str(control),
            "--treatment",
            str(treatment),
            "--resamples",
            "200",
            "--json",
            str(out),
            "--markdown",
            str(md),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["seedCount"] == 3
    rows = {r["path"]: r for r in payload["rows"]}
    assert rows["value"]["control"] == pytest.approx(0.040)
    assert rows["value"]["treatment"] == pytest.approx(0.036)
    assert rows["value"]["diff"] == pytest.approx(-0.004)
    assert rows["value"]["relative"] == pytest.approx(-0.1)
    assert rows["value"]["significant"] is True
    text = md.read_text(encoding="utf-8")
    assert "R-E" in text
    assert "eslesmis bootstrap" in text


def test_318_compare_sweeps_requires_per_case_losses(tmp_path):
    import json

    control = tmp_path / "a"
    treatment = tmp_path / "b"
    for root in (control, treatment):
        seed_dir = root / "seed0"
        seed_dir.mkdir(parents=True)
        (seed_dir / "er_paths.json").write_text(
            json.dumps({"paths": {"value": {"mean": 0.04}}}), encoding="utf-8"
        )
    with pytest.raises(ValueError):
        capacity_train.compare_sweeps(control, treatment)


# ----------------------------------------------------------------------
# 319-321: faz temsili alt orneklem (--stride)
# ----------------------------------------------------------------------


def test_319_er_paths_parser_accepts_stride():
    import er_paths

    args = er_paths.build_parser().parse_args(
        ["measure", "--model", "m.onnx", "--stride", "3"]
    )
    assert args.stride == 3
    default = er_paths.build_parser().parse_args(["measure", "--model", "m.onnx"])
    assert default.stride == 1


def test_320_measure_profile_forwards_stride_to_both_tools(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, quiet=False):
        calls.append(list(cmd))
        return 0

    monkeypatch.setattr(capacity_train, "_run", fake_run)
    capacity_train.measure_profile(
        tmp_path / "model.onnx",
        corpus=tmp_path / "corpus.json",
        out_dir=tmp_path / "out",
        gnubg=None,
        plies=2,
        limit=300,
        quiet=True,
        stride=3,
    )
    assert len(calls) == 2
    for cmd in calls:
        assert "--stride" in cmd
        assert cmd[cmd.index("--stride") + 1] == "3"
        assert cmd[cmd.index("--limit") + 1] == "300"


def test_321_measure_profile_omits_stride_when_one(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, quiet=False):
        calls.append(list(cmd))
        return 0

    monkeypatch.setattr(capacity_train, "_run", fake_run)
    capacity_train.measure_profile(
        tmp_path / "model.onnx",
        corpus=tmp_path / "corpus.json",
        out_dir=tmp_path / "out",
        gnubg=None,
        plies=2,
        limit=None,
        quiet=True,
    )
    assert len(calls) == 2
    for cmd in calls:
        assert "--stride" not in cmd