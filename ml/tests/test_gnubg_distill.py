"""Test 127: gnubg ogretmen deneyi (dis inceleme madde 1.3).

`ml/gnubg_distill.py` pozisyonlari gnubg 2-ply ile etiketler, deger kafasini
MSE ile egitir ve iki ER olcumunden karar uretir. Bu dosya etiketleme
sozlesmesini, veri kumesi G/Ç'sini, egitim dongusunu ve karar fonksiyonunu
gnubg **calistirmadan** dogrular (gnubg gerektiren testler `skip` eder).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import gnubg_distill as gd


# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------


def test_127a_constants() -> None:
    assert gd.DEFAULT_PLIES == 2
    assert gd.TARGET_ER == 0.03
    assert gd.MIN_GAIN == 0.20
    assert gd.DEFAULT_POSITIONS > 0
    assert gd.DEFAULT_STEPS > 0


def test_127a_verdict_labels_are_distinct() -> None:
    labels = {
        gd.VERDICT_TEACHER_EFFECTIVE,
        gd.VERDICT_PARTIAL,
        gd.VERDICT_CAPACITY,
        gd.VERDICT_UNPROVEN,
        gd.VERDICT_UNKNOWN,
        gd.VERDICT_INSUFFICIENT_DATA,
    }
    assert len(labels) == 6
    for label in labels:
        assert label in gd.VERDICT_TEXT


def test_127a_license_note_mentions_gpl() -> None:
    assert "GPL" in gd.LICENSE_NOTE


# ----------------------------------------------------------------------
# distill_verdict
# ----------------------------------------------------------------------


def test_127b_verdict_unknown_when_missing() -> None:
    assert gd.distill_verdict(None, 0.03) == gd.VERDICT_UNKNOWN
    assert gd.distill_verdict(0.0740, None) == gd.VERDICT_UNKNOWN
    assert gd.distill_verdict(None, None) == gd.VERDICT_UNKNOWN


def test_127b_verdict_unknown_when_nan() -> None:
    assert gd.distill_verdict(float("nan"), 0.03) == gd.VERDICT_UNKNOWN
    assert gd.distill_verdict(0.0740, float("inf")) == gd.VERDICT_UNKNOWN


def test_127b_verdict_without_paired_is_unproven() -> None:
    """R-07: eslesmis kanit yoksa nokta tahmini karar veremez."""
    assert gd.distill_verdict(0.0740, 0.0299) == gd.VERDICT_UNPROVEN
    assert gd.distill_verdict(0.0740, 0.03) == gd.VERDICT_UNPROVEN
    assert gd.distill_verdict(0.0740, 0.0500) == gd.VERDICT_UNPROVEN


def test_127b_verdict_pipeline_requires_ci_upper_below_target() -> None:
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert gd.distill_verdict(0.0740, 0.0299, paired=paired) == gd.VERDICT_TEACHER_EFFECTIVE


def test_127b_verdict_point_estimate_below_target_is_not_pipeline() -> None:
    """R-07'nin tam kalbi: nokta tahmini hedefin altinda ama GA ust siniri ustunde."""
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.041}
    assert gd.distill_verdict(0.0740, 0.0299, paired=paired) == gd.VERDICT_PARTIAL


def test_127b_verdict_partial_when_gain_proven_above_target() -> None:
    paired = {"n": 300, "meanDiff": 0.024, "excludesZero": True, "ciHighAfter": 0.06}
    assert gd.distill_verdict(0.0740, 0.0500, paired=paired) == gd.VERDICT_PARTIAL


def test_127b_verdict_unproven_when_ci_includes_zero() -> None:
    paired = {"n": 300, "meanDiff": 0.0176, "excludesZero": False, "ciHighAfter": 0.07}
    assert gd.distill_verdict(0.0740, 0.0500, paired=paired) == gd.VERDICT_UNPROVEN


def test_127b_verdict_never_returns_capacity() -> None:
    """R-07: kapasite cikarimi kaldirildi; etiket artik uretilmez."""
    paired = {"n": 300, "meanDiff": 0.0, "excludesZero": False, "ciHighAfter": 0.5}
    for before, after in ((0.0740, 0.0740), (0.0740, 0.0900), (0.10, 0.0801), (0.0, 0.5)):
        assert gd.distill_verdict(before, after, paired=paired) != gd.VERDICT_CAPACITY


def test_127b_verdict_insufficient_data_when_n_below_required() -> None:
    paired = {"n": 70, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert (
        gd.distill_verdict(0.0740, 0.0299, paired=paired, required_n=285)
        == gd.VERDICT_INSUFFICIENT_DATA
    )


def test_127b_verdict_sufficient_data_when_n_meets_required() -> None:
    paired = {"n": 300, "meanDiff": 0.02, "excludesZero": True, "ciHighAfter": 0.0299}
    assert (
        gd.distill_verdict(0.0740, 0.0299, paired=paired, required_n=285)
        == gd.VERDICT_TEACHER_EFFECTIVE
    )


def test_127b_verdict_custom_target() -> None:
    paired = {"n": 300, "meanDiff": 0.05, "excludesZero": True, "ciHighAfter": 0.055}
    assert gd.distill_verdict(0.10, 0.05, target=0.06, paired=paired) == gd.VERDICT_TEACHER_EFFECTIVE


def test_127b_verdict_detail_reports_no_capacity_inference() -> None:
    paired = {"n": 300, "meanDiff": 0.0, "excludesZero": False, "ciHighAfter": 0.5}
    detail = gd.distill_verdict_detail(0.0740, 0.0740, paired=paired)
    assert detail["capacityInference"] is False
    assert detail["verdict"] == gd.VERDICT_UNPROVEN
    assert detail["n"] == 300


def test_127b_verdict_detail_meets_min_gain_is_reported_not_decided() -> None:
    paired = {"n": 300, "meanDiff": 0.001, "excludesZero": True, "ciHighAfter": 0.09}
    detail = gd.distill_verdict_detail(0.10, 0.099, paired=paired)
    assert detail["meetsMinGain"] is False
    assert detail["verdict"] == gd.VERDICT_PARTIAL


# ----------------------------------------------------------------------
# Eslesmis test (paired)
# ----------------------------------------------------------------------


def test_127l_paired_identical_samples_have_zero_difference() -> None:
    a = {"p1": 0.1, "p2": 0.2, "p3": 0.3}
    out = gd.paired_loss_test(a, dict(a))
    assert out["n"] == 3
    assert out["meanDiff"] == pytest.approx(0.0)
    assert out["se"] == pytest.approx(0.0)
    assert out["excludesZero"] is False


def test_127l_paired_uses_only_common_positions() -> None:
    a = {"p1": 0.1, "p2": 0.2, "p3": 0.3}
    b = {"p1": 0.0, "p2": 0.1, "p9": 9.0}
    out = gd.paired_loss_test(a, b)
    assert out["n"] == 2
    assert out["meanDiff"] == pytest.approx(0.1)


def test_127l_paired_sign_is_before_minus_after() -> None:
    a = {"p1": 0.5, "p2": 0.5}
    b = {"p1": 0.1, "p2": 0.1}
    out = gd.paired_loss_test(a, b)
    assert out["meanDiff"] == pytest.approx(0.4)


def test_127l_paired_consistent_gain_excludes_zero() -> None:
    before = {"p%d" % i: 0.30 for i in range(40)}
    after = {"p%d" % i: 0.10 + 0.001 * i for i in range(40)}
    out = gd.paired_loss_test(before, after)
    assert out["excludesZero"] is True
    assert out["ciLow"] > 0.0
    assert out["t"] > 0.0


def test_127l_paired_consistent_loss_excludes_zero() -> None:
    before = {"p%d" % i: 0.10 for i in range(40)}
    after = {"p%d" % i: 0.30 + 0.001 * i for i in range(40)}
    out = gd.paired_loss_test(before, after)
    assert out["excludesZero"] is True
    assert out["ciHigh"] < 0.0


def test_127l_paired_noisy_gain_does_not_exclude_zero() -> None:
    before = {"p%d" % i: 0.20 for i in range(20)}
    after = {"p%d" % i: (0.05 if i % 2 == 0 else 0.35) for i in range(20)}
    out = gd.paired_loss_test(before, after)
    assert out["excludesZero"] is False


def test_127l_paired_ci_brackets_mean() -> None:
    before = {"p%d" % i: 0.2 + 0.01 * i for i in range(30)}
    after = {"p%d" % i: 0.1 + 0.005 * i for i in range(30)}
    out = gd.paired_loss_test(before, after)
    assert out["ciLow"] < out["meanDiff"] < out["ciHigh"]


def test_127l_paired_t_matches_mean_over_se() -> None:
    before = {"p%d" % i: 0.2 + 0.01 * i for i in range(30)}
    after = {"p%d" % i: 0.1 + 0.005 * i for i in range(30)}
    out = gd.paired_loss_test(before, after)
    assert out["t"] == pytest.approx(out["meanDiff"] / out["se"])


def test_127l_paired_wider_z_widens_ci() -> None:
    before = {"p%d" % i: 0.2 + 0.01 * i for i in range(30)}
    after = {"p%d" % i: 0.1 + 0.005 * i for i in range(30)}
    narrow = gd.paired_loss_test(before, after, z=1.0)
    wide = gd.paired_loss_test(before, after, z=2.58)
    assert (wide["ciHigh"] - wide["ciLow"]) > (narrow["ciHigh"] - narrow["ciLow"])


def test_127l_paired_too_few_positions_is_not_significant() -> None:
    out = gd.paired_loss_test({"p1": 0.5}, {"p1": 0.1})
    assert out["n"] == 1
    assert out["excludesZero"] is False


def test_127l_paired_empty_is_not_significant() -> None:
    out = gd.paired_loss_test({}, {})
    assert out["n"] == 0
    assert out["excludesZero"] is False


def test_127l_paired_has_all_keys() -> None:
    out = gd.paired_loss_test({"p1": 0.2, "p2": 0.3}, {"p1": 0.1, "p2": 0.2})
    for key in ("n", "meanDiff", "sd", "se", "t", "ciLow", "ciHigh", "excludesZero"):
        assert key in out


def test_127l_verdict_unproven_when_paired_does_not_exclude_zero() -> None:
    paired = {"n": 70, "meanDiff": 0.0176, "se": 0.0121, "t": 1.45,
              "ciLow": -0.0062, "ciHigh": 0.0414, "excludesZero": False}
    assert gd.distill_verdict(0.0708, 0.0533, paired=paired) == gd.VERDICT_UNPROVEN


def test_127l_verdict_partial_when_paired_excludes_zero() -> None:
    paired = {"n": 70, "meanDiff": 0.0176, "se": 0.004, "t": 4.4,
              "ciLow": 0.0098, "ciHigh": 0.0254, "excludesZero": True}
    assert gd.distill_verdict(0.0708, 0.0533, paired=paired) == gd.VERDICT_PARTIAL


def test_127l_verdict_pipeline_beats_unproven() -> None:
    paired = {"n": 70, "meanDiff": 0.0, "se": 0.01, "t": 0.0,
              "ciLow": -0.02, "ciHigh": 0.02, "excludesZero": False,
              "ciHighAfter": 0.0299}
    assert gd.distill_verdict(0.0708, 0.0299, paired=paired) == gd.VERDICT_TEACHER_EFFECTIVE


def test_127l_verdict_without_paired_is_unproven() -> None:
    assert gd.distill_verdict(0.0708, 0.0533) == gd.VERDICT_UNPROVEN


def test_127l_verdict_unproven_text_mentions_ci() -> None:
    text = gd.VERDICT_TEXT[gd.VERDICT_UNPROVEN]
    assert "GA" in text
    assert "sifiri" in text


def test_127l_parse_arm_splits_label_and_path() -> None:
    label, path = gd.parse_arm("2000=ml/artifacts/x.json")
    assert label == "2000"
    assert str(path).replace("\\", "/") == "ml/artifacts/x.json"


def test_127l_parse_arm_rejects_missing_equals() -> None:
    with pytest.raises(ValueError):
        gd.parse_arm("noequals")


def test_127l_parse_arm_rejects_empty_label() -> None:
    with pytest.raises(ValueError):
        gd.parse_arm("=ml/artifacts/x.json")


def test_127l_cli_rejects_bad_arm_spec(tmp_path: Path) -> None:
    out = tmp_path / "v.json"
    code = gd.main(
        [
            "verdict",
            "--before",
            "0.07",
            "--after",
            "0.05",
            "--arm",
            "bad",
            "--json",
            str(out),
            "--quiet",
        ]
    )
    assert code == 2
    assert not out.exists()


def test_127l_cli_skips_missing_arm_file(tmp_path: Path) -> None:
    out = tmp_path / "v.json"
    code = gd.main(
        [
            "verdict",
            "--before",
            "0.07",
            "--after",
            "0.05",
            "--arm",
            "x=" + str(tmp_path / "nope.json"),
            "--json",
            str(out),
            "--quiet",
        ]
    )
    # Eslesmis kanit yok -> "belirsiz" (cikis 4). Eksik kol dosyasi hata degil.
    assert code == 4
    assert "arms" not in json.loads(out.read_text(encoding="utf-8"))


def test_127l_load_er_losses_reads_positions(tmp_path: Path) -> None:
    payload = {
        "positions": [
            {"name": "a", "equityLoss": 0.1},
            {"name": "b", "equityLoss": 0.2},
            {"name": "c"},
        ]
    }
    path = tmp_path / "er.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    losses = gd.load_er_losses(path)
    assert losses == {"a": 0.1, "b": 0.2}


def test_127l_load_er_losses_empty_when_no_positions(tmp_path: Path) -> None:
    path = tmp_path / "er.json"
    path.write_text(json.dumps({"positions": []}), encoding="utf-8")
    assert gd.load_er_losses(path) == {}


def test_127l_markdown_renders_paired_section() -> None:
    report = {
        "dataset": {"count": 0},
        "verdict": gd.VERDICT_UNPROVEN,
        "erBefore": 0.0708,
        "erAfter": 0.0533,
        "paired": {"n": 70, "meanDiff": 0.0176, "se": 0.0121, "t": 1.45,
                   "ciLow": -0.0062, "ciHigh": 0.0414, "excludesZero": False},
    }
    md = gd.build_markdown(report)
    assert "### 4.1 Eslesmis test" in md
    assert "Sifiri disliyor" in md
    assert "**hayir**" in md


def test_127l_markdown_renders_arms_section() -> None:
    report = {
        "dataset": {"count": 0},
        "verdict": gd.VERDICT_UNPROVEN,
        "arms": [
            {"label": "2000", "positions": 70, "er": 0.0533,
             "pairedVsBefore": {"meanDiff": 0.0176, "ciLow": -0.0062,
                                "ciHigh": 0.0414, "excludesZero": False}},
            {"label": "10000", "positions": 70, "er": 0.0617},
        ],
    }
    md = gd.build_markdown(report)
    assert "### 4.2 Veri hacmi kollari" in md
    assert "| 2000 | 70 | 0.0533 |" in md
    assert "| 10000 | 70 | 0.0617 | - | - | - |" in md


def test_127l_markdown_omits_paired_section_without_data() -> None:
    md = gd.build_markdown({"dataset": {"count": 0}, "verdict": gd.VERDICT_UNKNOWN})
    assert "### 4.1" not in md
    assert "### 4.2" not in md


def test_127l_notes_mention_paired_when_present() -> None:
    report = {
        "erBefore": 0.0708,
        "erAfter": 0.0533,
        "paired": {"n": 70, "meanDiff": 0.0176, "se": 0.0121, "t": 1.45,
                   "ciLow": -0.0062, "ciHigh": 0.0414, "excludesZero": False},
    }
    notes = gd._verdict_notes(report)
    joined = " ".join(notes)
    assert "Eslesmis test" in joined
    assert "dislamiyor" in joined


def test_127l_notes_say_no_paired_test_when_absent() -> None:
    notes = gd._verdict_notes({"erBefore": 0.0708, "erAfter": 0.0533})
    joined = " ".join(notes)
    assert "Eslesmis test yapilmadi" in joined
    assert "GA95" not in joined


# ----------------------------------------------------------------------
# Dataset
# ----------------------------------------------------------------------


def _labeled(n: int = 4, *, seed: int = 0) -> list[gd.LabeledPosition]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        out.append(
            gd.LabeledPosition(
                vector=[float(v) for v in rng.random(221)],
                equity=float(i) * 0.1 - 0.2,
                turn=1 if i % 2 == 0 else -1,
                dice=(3, 4),
                best_move="13/10 13/9",
                candidates=10,
            )
        )
    return out


def test_127c_build_dataset_shapes() -> None:
    ds = gd.build_dataset(_labeled(5))
    assert ds.x.shape == (5, 221)
    assert ds.y.shape == (5,)
    assert ds.x.dtype == np.float32
    assert len(ds) == 5


def test_127c_build_dataset_empty() -> None:
    ds = gd.build_dataset([])
    assert len(ds) == 0
    assert ds.x.shape == (0, 221)
    assert ds.stats() == {"count": 0}


def test_127c_build_dataset_meta_is_copied() -> None:
    meta = {"plies": 2}
    ds = gd.build_dataset(_labeled(2), meta=meta)
    meta["plies"] = 9
    assert ds.meta["plies"] == 2


def test_127c_stats() -> None:
    ds = gd.build_dataset(_labeled(4))
    stats = ds.stats()
    assert stats["count"] == 4
    assert stats["min"] == pytest.approx(-0.2)
    assert stats["max"] == pytest.approx(0.1)
    assert stats["std"] > 0.0


def test_127c_stats_zero_share() -> None:
    ds = gd.Dataset(
        x=np.zeros((3, 221), dtype=np.float32),
        y=np.array([0.0, 0.0, 1.0], dtype=np.float32),
    )
    assert ds.stats()["zeroShare"] == pytest.approx(2.0 / 3.0)


def test_127c_save_load_roundtrip(tmp_path: Path) -> None:
    ds = gd.build_dataset(_labeled(3), meta={"plies": 2, "seed": 7})
    path = tmp_path / "sub" / "d.npz"
    gd.save_dataset(ds, path)
    assert path.is_file()
    back = gd.load_dataset(path)
    assert len(back) == 3
    assert back.meta["plies"] == 2
    assert np.allclose(back.x, ds.x)
    assert np.allclose(back.y, ds.y)


def test_127c_load_dataset_without_meta(tmp_path: Path) -> None:
    path = tmp_path / "d.npz"
    np.savez_compressed(
        path, x=np.zeros((2, 221), dtype=np.float32), y=np.zeros((2,), dtype=np.float32)
    )
    back = gd.load_dataset(path)
    assert back.meta == {}
    assert len(back) == 2


def test_127c_labeled_position_to_dict() -> None:
    d = _labeled(1)[0].to_dict()
    assert set(d) == {"equity", "turn", "dice", "bestMove", "candidates"}
    assert d["dice"] == [3, 4]


# ----------------------------------------------------------------------
# Etiketleme (sahte hakem)
# ----------------------------------------------------------------------


class _FakeHint:
    def __init__(self, move: str, equity: float) -> None:
        self.move = move
        self.equity = equity
        self.loss = None
        self.rank = 1


class _FakeReferee:
    def __init__(self, *, fail_on: set[int] | None = None, empty_on: set[int] | None = None) -> None:
        self.calls: list[tuple] = []
        self.fail_on = fail_on or set()
        self.empty_on = empty_on or set()

    def hint(self, board, turn, dice):
        self.calls.append((list(board), turn, list(dice)))
        index = len(self.calls)
        if index in self.fail_on:
            raise RuntimeError("gnubg patladi")
        if index in self.empty_on:
            return [], ""
        return [_FakeHint("13/10 13/9", 0.1234), _FakeHint("13/9 13/10", 0.1000)], ""


def _positions(n: int = 3) -> list[tuple]:
    import tools.reference_gen as refgen

    return [(list(refgen.START_BOARD), 1, [3, 4], 0, 0) for _ in range(n)]


def test_127d_label_positions_basic() -> None:
    referee = _FakeReferee()
    labeled, skipped = gd.label_positions(referee, _positions(3))
    assert len(labeled) == 3
    assert skipped == []
    assert labeled[0].equity == pytest.approx(0.1234)
    assert labeled[0].best_move == "13/10 13/9"
    assert labeled[0].candidates == 2
    assert len(labeled[0].vector) == 221


def test_127d_label_positions_uses_mover_perspective() -> None:
    import gnubg_er

    referee = _FakeReferee()
    labeled, _ = gd.label_positions(referee, _positions(1))
    expected = gnubg_er.vectorize(
        list(__import__("tools.reference_gen", fromlist=["x"]).START_BOARD),
        0,
        0,
        perspective=1,
    )
    assert labeled[0].vector == pytest.approx(expected)


def test_127d_label_positions_records_failures() -> None:
    referee = _FakeReferee(fail_on={2})
    labeled, skipped = gd.label_positions(referee, _positions(3))
    assert len(labeled) == 2
    assert len(skipped) == 1
    assert skipped[0]["index"] == 2
    assert "RuntimeError" in skipped[0]["reason"]


def test_127d_label_positions_records_empty_hint() -> None:
    referee = _FakeReferee(empty_on={1})
    labeled, skipped = gd.label_positions(referee, _positions(2))
    assert len(labeled) == 1
    assert "bos" in skipped[0]["reason"]


def test_127d_label_positions_progress_callback() -> None:
    seen: list[tuple[int, int, bool]] = []
    referee = _FakeReferee(fail_on={2})
    gd.label_positions(
        referee,
        _positions(3),
        progress=lambda i, total, item: seen.append((i, total, item is not None)),
    )
    assert seen == [(1, 3, True), (2, 3, False), (3, 3, True)]


def test_127d_label_positions_empty_input() -> None:
    labeled, skipped = gd.label_positions(_FakeReferee(), [])
    assert labeled == []
    assert skipped == []


# ----------------------------------------------------------------------
# Egitim
# ----------------------------------------------------------------------


def _tiny_model():
    from model import build_model

    return build_model(221, 32, 16, seed=0, output_version=2, profile="small")


def test_127e_train_reduces_loss() -> None:
    torch = pytest.importorskip("torch")
    model = _tiny_model()
    rng = np.random.default_rng(3)
    x = rng.random((64, 221)).astype(np.float32)
    y = (x[:, 0] * 2.0 - 1.0).astype(np.float32)
    ds = gd.Dataset(x=x, y=y)
    report = gd.train_value_head(model, ds, steps=60, lr=1e-2, batch=32, seed=0)
    assert report["steps"] == 60
    assert report["count"] == 64
    assert report["lastLoss"] < report["firstLoss"]
    assert len(report["history"]) == 60


def test_127e_train_reports_metrics() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    rng = np.random.default_rng(4)
    x = rng.random((32, 221)).astype(np.float32)
    y = rng.normal(size=32).astype(np.float32)
    report = gd.train_value_head(model, gd.Dataset(x=x, y=y), steps=5, batch=16)
    for key in ("finalMse", "finalMae", "correlation", "slope"):
        assert key in report
    assert report["finalMse"] >= 0.0
    assert report["finalMae"] >= 0.0


def test_127e_train_rejects_empty_dataset() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    with pytest.raises(ValueError):
        gd.train_value_head(model, gd.build_dataset([]), steps=1)


def test_127e_train_rejects_zero_steps() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    ds = gd.Dataset(
        x=np.zeros((2, 221), dtype=np.float32), y=np.zeros((2,), dtype=np.float32)
    )
    with pytest.raises(ValueError):
        gd.train_value_head(model, ds, steps=0)


def test_127e_train_batch_larger_than_data_is_clamped() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    ds = gd.Dataset(
        x=np.zeros((3, 221), dtype=np.float32), y=np.zeros((3,), dtype=np.float32)
    )
    report = gd.train_value_head(model, ds, steps=2, batch=1024)
    assert report["batch"] == 3


def test_127e_train_leaves_model_in_eval_mode() -> None:
    torch = pytest.importorskip("torch")
    model = _tiny_model()
    ds = gd.Dataset(
        x=np.zeros((2, 221), dtype=np.float32), y=np.zeros((2,), dtype=np.float32)
    )
    gd.train_value_head(model, ds, steps=1)
    assert model.training is False


# ----------------------------------------------------------------------
# Istatistik yardimcilari
# ----------------------------------------------------------------------


def test_127f_pearson_perfect() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert gd._pearson(a, a) == pytest.approx(1.0)


def test_127f_pearson_negative() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert gd._pearson(a, -a) == pytest.approx(-1.0)


def test_127f_pearson_constant_is_nan() -> None:
    assert np.isnan(gd._pearson(np.zeros(4), np.arange(4.0)))


def test_127f_pearson_too_short_is_nan() -> None:
    assert np.isnan(gd._pearson(np.array([1.0]), np.array([1.0])))


def test_127f_slope_identity() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert gd._slope(a, a) == pytest.approx(1.0)


def test_127f_slope_double() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert gd._slope(a, 2.0 * a) == pytest.approx(2.0)


def test_127f_slope_constant_is_nan() -> None:
    assert np.isnan(gd._slope(np.zeros(4), np.arange(4.0)))


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def test_127g_markdown_has_sections() -> None:
    md = gd.build_markdown(
        {
            "dataset": {"count": 10, "mean": 0.0, "std": 0.5, "min": -1.0, "max": 1.0},
            "skipped": 2,
            "value": {"finalMae": 0.2, "correlation": 0.9, "slope": 1.0, "er": 0.0708},
            "policy": {"steps": 100, "width": 20, "valueWeight": 0.5,
                       "firstLoss": 1.0, "lastLoss": 0.1, "top1": 1.0},
            "verdict": gd.VERDICT_TEACHER_EFFECTIVE,
            "erBefore": 0.0740,
            "erAfter": 0.0200,
            "target": 0.03,
            "notes": ["bir not"],
        }
    )
    assert "## 1. Veri kumesi" in md
    assert "## 2. Deger kafasi denemesi" in md
    assert "## 3. Politika damitma" in md
    assert "## 4. Karar" in md
    assert "## 5. Durustluk notlari" in md
    assert "**`ogretmen-etkili`**" in md
    assert "GPL" in md
    assert "| Iyilesme | 73.0% |" in md


def test_127g_markdown_without_optional_blocks() -> None:
    md = gd.build_markdown({"dataset": {"count": 0}, "verdict": gd.VERDICT_UNKNOWN})
    assert "## 2. Deger kafasi denemesi" not in md
    assert "## 3. Politika damitma" not in md
    assert "## 5. Durustluk notlari" not in md
    assert "**`bilinmiyor`**" in md


def test_127g_markdown_mentions_policy_rationale() -> None:
    md = gd.build_markdown({})
    assert "politika" in md
    assert "criterion" in md


def test_127g_markdown_missing_er_shows_dash() -> None:
    md = gd.build_markdown({"dataset": {"count": 1}, "verdict": gd.VERDICT_UNKNOWN})
    assert "| ER once | - |" in md
    assert "| ER sonra | - |" in md


def test_127g_markdown_ends_with_newline() -> None:
    assert gd.build_markdown({}).endswith("\n")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_127h_parser_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        gd.build_parser().parse_args([])


def test_127h_parser_label_defaults() -> None:
    args = gd.build_parser().parse_args(["label", "--out", "x.npz"])
    assert args.positions == gd.DEFAULT_POSITIONS
    assert args.plies == gd.DEFAULT_PLIES
    assert args.seed == 7


def test_127h_parser_train_defaults() -> None:
    args = gd.build_parser().parse_args(
        ["train", "--data", "d.npz", "--ckpt", "c.pt", "--out", "o.pt"]
    )
    assert args.steps == gd.DEFAULT_STEPS
    assert args.lr == pytest.approx(gd.DEFAULT_LR)
    assert args.device == "cpu"


def test_127h_cli_verdict_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "v.json"
    out_md = tmp_path / "v.md"
    code = gd.main(
        [
            "verdict",
            "--before",
            "0.0740",
            "--after",
            "0.0200",
            "--json",
            str(out_json),
            "--markdown",
            str(out_md),
            "--quiet",
        ]
    )
    # R-07: eslesmis kanit olmadan "pipeline" denemez -> "belirsiz" (cikis 4).
    assert code == 4
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["verdict"] == gd.VERDICT_UNPROVEN
    assert "GPL" in out_md.read_text(encoding="utf-8")


def test_127h_cli_verdict_no_gain_is_unproven_exit_four(tmp_path: Path) -> None:
    """R-07: kazanc yok -> 'kapasite' DEGIL, 'belirsiz' (cikis 4)."""
    code = gd.main(
        ["verdict", "--before", "0.0740", "--after", "0.0740", "--quiet"]
    )
    assert code == 4


def test_127h_cli_verdict_insufficient_data_exit_five(tmp_path: Path) -> None:
    before = tmp_path / "b.json"
    after = tmp_path / "a.json"
    before.write_text(
        json.dumps({"positions": [{"name": "p%d" % i, "equityLoss": 0.2} for i in range(20)]}),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps({"positions": [{"name": "p%d" % i, "equityLoss": 0.1} for i in range(20)]}),
        encoding="utf-8",
    )
    code = gd.main(
        [
            "verdict",
            "--before", "0.2",
            "--after", "0.1",
            "--er-before-json", str(before),
            "--er-after-json", str(after),
            "--required-n", "285",
            "--quiet",
        ]
    )
    assert code == 5


def test_127h_cli_verdict_unknown_exit_three(tmp_path: Path) -> None:
    code = gd.main(
        ["verdict", "--before", "nan", "--after", "0.02", "--quiet"]
    )
    assert code == 3


def test_127h_cli_train_missing_data_returns_two(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    code = gd.main(
        [
            "train",
            "--data",
            str(tmp_path / "nope.npz"),
            "--ckpt",
            str(tmp_path / "nope.pt"),
            "--out",
            str(tmp_path / "o.pt"),
            "--quiet",
        ]
    )
    assert code == 2


# ----------------------------------------------------------------------
# Gercek gnubg (varsa)
# ----------------------------------------------------------------------


def _gnubg_available() -> bool:
    try:
        import gnubg_er

        return gnubg_er.find_gnubg() is not None
    except Exception:
        return False


@pytest.mark.skipif(not _gnubg_available(), reason="gnubg kurulu degil")
def test_127i_real_gnubg_labels_one_position() -> None:
    import gnubg_er
    import gnubg_hint

    referee = gnubg_hint.HintReferee(gnubg_er.find_gnubg(), plies=2, timeout=60)
    labeled, skipped = gd.label_positions(referee, _positions(1))
    assert skipped == []
    assert len(labeled) == 1
    assert -3.0 <= labeled[0].equity <= 3.0
    assert labeled[0].candidates >= 1
    assert len(labeled[0].vector) == 221


def test_127i_generate_positions_is_deterministic() -> None:
    a = gd.generate_positions(3, seed=11)
    b = gd.generate_positions(3, seed=11)
    assert len(a) == 3
    assert [p[0] for p in a] == [p[0] for p in b]


def test_127i_generate_positions_zero() -> None:
    assert gd.generate_positions(0) == []


# ----------------------------------------------------------------------
# Politika damitma (F7-21)
# ----------------------------------------------------------------------


class _PolicyReferee:
    """Gecerli bir hamle donduren sahte hakem (afterstate'e eslesir)."""

    def __init__(self, move: str = "13/10 13/9", equity: float = 0.25) -> None:
        self.move = move
        self.equity = equity
        self.calls = 0

    def hint(self, board, turn, dice):
        self.calls += 1
        return [_FakeHint(self.move, self.equity)], ""


def test_127j_afterstate_case_is_deterministic() -> None:
    import tools.reference_gen as refgen

    a = gd.afterstate_case(list(refgen.START_BOARD), 1, [3, 4], 0, 0)
    b = gd.afterstate_case(list(refgen.START_BOARD), 1, [3, 4], 0, 0)
    assert a is not None and b is not None
    assert a["afterStates"] == b["afterStates"]
    assert len(a["afterStates"]) > 1


def test_127j_afterstate_case_sorted() -> None:
    import tools.reference_gen as refgen

    case = gd.afterstate_case(list(refgen.START_BOARD), 1, [3, 4], 0, 0)
    keys = [(tuple(a["board"]), a["whiteOff"], a["blackOff"]) for a in case["afterStates"]]
    assert keys == sorted(keys)


def test_127j_afterstate_case_none_when_no_moves() -> None:
    assert gd.afterstate_case([0] * 26, 1, [3, 4], 15, 15) is None


def test_127j_afterstate_case_carries_metadata() -> None:
    import tools.reference_gen as refgen

    case = gd.afterstate_case(list(refgen.START_BOARD), -1, [6, 6], 2, 3)
    assert case["turn"] == -1
    assert case["dice"] == [6, 6]
    assert case["whiteOff"] == 2
    assert case["blackOff"] == 3


def test_127j_label_policy_basic() -> None:
    import tools.reference_gen as refgen

    referee = _PolicyReferee()
    positions = [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)]
    labeled, skipped = gd.label_policy_positions(referee, positions)
    assert skipped == []
    assert len(labeled) == 1
    item = labeled[0]
    assert item.candidates == len(item.vectors)
    assert 0 <= item.best_index < item.candidates
    assert item.best_equity == pytest.approx(0.25)
    assert item.best_move == "13/10 13/9"
    assert all(len(v) == 221 for v in item.vectors)


def test_127j_label_policy_is_reproducible() -> None:
    import tools.reference_gen as refgen

    positions = [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)]
    a, _ = gd.label_policy_positions(_PolicyReferee(), positions)
    b, _ = gd.label_policy_positions(_PolicyReferee(), positions)
    assert a[0].best_index == b[0].best_index
    assert a[0].vectors == b[0].vectors


def test_127j_label_policy_skips_unmapped_hint() -> None:
    import tools.reference_gen as refgen

    referee = _PolicyReferee(move="13/10")
    positions = [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)]
    labeled, skipped = gd.label_policy_positions(referee, positions)
    assert labeled == []
    assert len(skipped) == 1
    assert "eslesmedi" in skipped[0]["reason"]


def test_127j_label_policy_skips_no_afterstate() -> None:
    referee = _PolicyReferee()
    labeled, skipped = gd.label_policy_positions(referee, [([0] * 26, 1, [3, 4], 15, 15)])
    assert labeled == []
    assert "afterstate" in skipped[0]["reason"]


def test_127j_label_policy_records_gnubg_failure() -> None:
    import tools.reference_gen as refgen

    class _Boom:
        def hint(self, board, turn, dice):
            raise RuntimeError("patladi")

    labeled, skipped = gd.label_policy_positions(
        _Boom(), [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)]
    )
    assert labeled == []
    assert "RuntimeError" in skipped[0]["reason"]


def test_127j_label_policy_progress_callback() -> None:
    import tools.reference_gen as refgen

    seen: list[tuple[int, int, bool]] = []
    positions = [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)] * 2
    gd.label_policy_positions(
        _PolicyReferee(),
        positions,
        progress=lambda i, total, item: seen.append((i, total, item is not None)),
    )
    assert seen == [(1, 2, True), (2, 2, True)]


def test_127j_policy_position_to_dict() -> None:
    import tools.reference_gen as refgen

    labeled, _ = gd.label_policy_positions(
        _PolicyReferee(), [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)]
    )
    data = labeled[0].to_dict()
    assert set(data) == {
        "bestIndex",
        "bestEquity",
        "turn",
        "dice",
        "bestMove",
        "candidates",
        "mappingFailures",
    }


def _policy_dataset(n: int = 3):
    import tools.reference_gen as refgen

    positions = [(list(refgen.START_BOARD), 1, [3, 4], 0, 0)] * n
    labeled, _ = gd.label_policy_positions(_PolicyReferee(), positions)
    return gd.build_policy_dataset(labeled, meta={"kind": "policy"})


def test_127j_build_policy_dataset_shapes() -> None:
    ds = _policy_dataset(3)
    assert len(ds) == 3
    assert ds.x.shape[1] == 221
    assert ds.offsets.shape == (4,)
    assert int(ds.offsets[0]) == 0
    assert int(ds.offsets[-1]) == ds.x.shape[0]
    assert ds.best.shape == (3,)
    assert ds.y.shape == (3,)


def test_127j_build_policy_dataset_empty() -> None:
    ds = gd.build_policy_dataset([])
    assert len(ds) == 0
    assert ds.x.shape == (0, 221)
    assert ds.offsets.tolist() == [0]
    assert ds.stats() == {"count": 0}


def test_127j_policy_dataset_candidates() -> None:
    ds = _policy_dataset(2)
    first = ds.candidates(0)
    assert first.shape[0] == int(ds.offsets[1]) - int(ds.offsets[0])
    assert first.shape[1] == 221


def test_127j_policy_dataset_stats() -> None:
    ds = _policy_dataset(3)
    stats = ds.stats()
    assert stats["count"] == 3
    assert stats["candidates"] == ds.x.shape[0]
    assert stats["candidatesMin"] == stats["candidatesMax"]
    assert stats["mean"] == pytest.approx(0.25)


def test_127j_policy_dataset_roundtrip(tmp_path: Path) -> None:
    ds = _policy_dataset(2)
    path = tmp_path / "policy.npz"
    gd.save_policy_dataset(ds, path)
    back = gd.load_policy_dataset(path)
    assert len(back) == len(ds)
    assert back.meta == ds.meta
    assert back.offsets.tolist() == ds.offsets.tolist()
    assert back.best.tolist() == ds.best.tolist()
    assert np.allclose(back.x, ds.x)


def test_127j_policy_dataset_load_without_meta(tmp_path: Path) -> None:
    ds = _policy_dataset(1)
    path = tmp_path / "policy.npz"
    np.savez_compressed(
        path, x=ds.x, offsets=ds.offsets, best=ds.best, y=ds.y
    )
    back = gd.load_policy_dataset(path)
    assert back.meta == {}


def test_127j_pad_policy_shapes() -> None:
    ds = _policy_dataset(3)
    x, mask, width = gd._pad_policy(ds)
    assert x.shape == (3, width, 221)
    assert mask.shape == (3, width)
    assert mask.all()
    assert width == int(ds.offsets[1] - ds.offsets[0])


def test_127j_train_policy_reduces_loss() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    ds = _policy_dataset(4)
    report = gd.train_policy_head(model, ds, steps=60, lr=1e-2, batch=4, seed=0)
    assert report["lastLoss"] < report["firstLoss"]
    assert report["count"] == 4
    assert report["width"] == int(ds.offsets[1] - ds.offsets[0])


def test_127j_train_policy_reports_top1() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    ds = _policy_dataset(4)
    report = gd.train_policy_head(model, ds, steps=20, batch=4, seed=0)
    assert 0.0 <= report["top1"] <= 1.0
    assert report["valueWeight"] == pytest.approx(gd.DEFAULT_VALUE_WEIGHT)


def test_127j_train_policy_rejects_empty() -> None:
    pytest.importorskip("torch")
    with pytest.raises(ValueError):
        gd.train_policy_head(_tiny_model(), gd.build_policy_dataset([]), steps=5)


def test_127j_train_policy_rejects_zero_steps() -> None:
    pytest.importorskip("torch")
    with pytest.raises(ValueError):
        gd.train_policy_head(_tiny_model(), _policy_dataset(2), steps=0)


def test_127j_train_policy_leaves_eval_mode() -> None:
    pytest.importorskip("torch")
    model = _tiny_model()
    gd.train_policy_head(model, _policy_dataset(2), steps=5, batch=2)
    assert model.training is False


def test_127j_parser_label_policy_defaults() -> None:
    args = gd.build_parser().parse_args(["label-policy", "--out", "x.npz"])
    assert args.command == "label-policy"
    assert args.plies == gd.DEFAULT_PLIES
    assert args.positions == gd.DEFAULT_POSITIONS


def test_127j_parser_train_policy_defaults() -> None:
    args = gd.build_parser().parse_args(
        ["train-policy", "--data", "d.npz", "--ckpt", "c.pt", "--out", "o.pt"]
    )
    assert args.command == "train-policy"
    assert args.value_weight == pytest.approx(gd.DEFAULT_VALUE_WEIGHT)
    assert args.steps == gd.DEFAULT_STEPS


def test_127j_cli_train_policy_missing_data_returns_two(tmp_path: Path) -> None:
    ckpt = tmp_path / "c.pt"
    ckpt.write_bytes(b"x")
    code = gd.main(
        [
            "train-policy",
            "--data",
            str(tmp_path / "nope.npz"),
            "--ckpt",
            str(ckpt),
            "--out",
            str(tmp_path / "o.pt"),
            "--quiet",
        ]
    )
    assert code == 2


def test_127j_cli_train_policy_missing_ckpt_returns_two(tmp_path: Path) -> None:
    data = tmp_path / "d.npz"
    gd.save_policy_dataset(_policy_dataset(1), data)
    code = gd.main(
        [
            "train-policy",
            "--data",
            str(data),
            "--ckpt",
            str(tmp_path / "nope.pt"),
            "--out",
            str(tmp_path / "o.pt"),
            "--quiet",
        ]
    )
    assert code == 2


def test_127k_random_positions_handles_empty_state_set() -> None:
    """F7-21 yan bulgu: `legal_after_states` bos kume dondurebiliyor.

    `random_positions` bu durumda `rng.choice([])` cagirip `IndexError`
    atiyordu. 10 000 pozisyonluk kosu bunu ortaya cikardi; 2 000'lik kosuda
    gorunmedi. Bu test regresyonu kilitler.
    """
    import random

    import tools.reference_gen as refgen

    positions = refgen.random_positions(random.Random(11), 3000, max_plies=40)
    assert len(positions) == 3000
    for board, turn, dice, wo, bo in positions:
        assert len(board) == 26
        assert turn in (1, -1)
        assert len(dice) in (2, 4)
        assert 0 <= wo <= 15 and 0 <= bo <= 15


def test_127k_random_positions_is_deterministic() -> None:
    import random

    import tools.reference_gen as refgen

    a = refgen.random_positions(random.Random(5), 50, max_plies=20)
    b = refgen.random_positions(random.Random(5), 50, max_plies=20)
    assert a == b
