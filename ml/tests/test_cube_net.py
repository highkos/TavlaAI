"""F7-117: ayri kup agi testleri (352-359)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import cube_net  # noqa: E402
import gnubg_er  # noqa: E402


def _synthetic_dataset(count: int = 40, seed: int = 3) -> cube_net.CubeDataset:
    import numpy as np

    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((count, gnubg_er.VECTOR_SIZE)).astype(float).tolist()
    targets = []
    actions = []
    takes = []
    for index in range(count):
        no_double = float(rng.normal(0.0, 0.3))
        double_pass = no_double + float(rng.normal(0.1, 0.2))
        double_take = no_double + float(rng.normal(0.05, 0.2))
        targets.append([no_double, double_pass, double_take])
        doubled = max(double_pass, double_take) > no_double
        actions.append("double" if doubled else "no-double")
        takes.append(double_take < 1.0)
    return cube_net.CubeDataset(
        vectors=vectors,
        targets=targets,
        names=["c%d" % i for i in range(count)],
        actions=actions,
        takes=takes,
        meta={"gnubgPlies": 2},
    )


def test_352_cube_net_is_exactly_antisymmetric() -> None:
    """352: ``f(Tx) = -f(x)`` — uc cubeful equity de isaret doner."""
    import torch

    from antisymmetry import flip_perspective

    net = cube_net.build_cube_net(hidden=(64, 64), seed=5)
    net.eval()
    rng = torch.Generator().manual_seed(9)
    x = torch.randn(16, gnubg_er.VECTOR_SIZE, generator=rng)
    flipped = torch.tensor(
        [flip_perspective(row) for row in x.tolist()], dtype=torch.float32
    )
    with torch.no_grad():
        direct = net(x)
        mirrored = net(flipped)
    assert direct.shape == (16, cube_net.TARGET_COUNT)
    assert float(torch.max(torch.abs(direct + mirrored))) < 1e-5


def test_353_cube_net_has_no_bias_in_odd_branch() -> None:
    """353: tek kolda ve cikti katmaninda bias yok (antisimetrinin on kosulu)."""
    net = cube_net.build_cube_net(hidden=(32, 32), seed=1)
    assert net.head.bias is None
    for module in net.backbone.net:
        if hasattr(module, "bias"):
            assert module.bias is None


def test_354_decide_matches_equity_argmax() -> None:
    """354: karar uc equity'nin argmax'i; esitlikte ciftlememe."""
    # Ciftleme degeri min(doublePass, doubleTake): rakip en kotu cevabi secer.
    doubled = cube_net.decide([0.10, 1.00, 0.30])
    assert doubled["shouldDouble"] is True
    assert doubled["shouldTake"] is True
    assert doubled["bestValue"] == pytest.approx(0.30)

    quiet = cube_net.decide([0.50, 1.00, 0.10])
    assert quiet["shouldDouble"] is False
    assert quiet["bestValue"] == pytest.approx(0.50)

    tie = cube_net.decide([0.30, 1.00, 0.30])
    assert tie["shouldDouble"] is False

    # Rakip kabul etmemeli: doubleTake >= cubeValue.
    pass_case = cube_net.decide([0.10, 1.00, 1.20])
    assert pass_case["shouldTake"] is False
    assert pass_case["bestValue"] == pytest.approx(1.00)


def test_355_decide_rejects_wrong_arity() -> None:
    """355: yanlis sayida equity hata verir."""
    with pytest.raises(cube_net.CubeNetError):
        cube_net.decide([0.1, 0.2])


def test_356_dataset_roundtrip(tmp_path: Path) -> None:
    """356: etiket dosyasi kaydedilip aynen geri okunur."""
    dataset = _synthetic_dataset(12)
    path = cube_net.save_dataset(dataset, tmp_path / "labels.json")
    back = cube_net.load_dataset(path)
    assert len(back) == len(dataset)
    assert back.vectors[0] == pytest.approx(dataset.vectors[0])
    assert back.targets[0] == pytest.approx(dataset.targets[0])
    assert back.actions == dataset.actions
    assert back.stats()["targetOrder"] == list(cube_net.TARGET_ORDER)


def test_357_dataset_rejects_unknown_version(tmp_path: Path) -> None:
    """357: bilinmeyen etiket surumu sessizce kabul edilmez."""
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"version": 99, "cases": []}), encoding="utf-8")
    with pytest.raises(cube_net.CubeNetError):
        cube_net.load_dataset(path)


def test_358_train_and_export_roundtrip(tmp_path: Path) -> None:
    """358: egitim + ONNX ihracati + parite dogrulamasi calisir."""
    pytest.importorskip("onnxruntime")
    dataset = _synthetic_dataset(48)
    net, report = cube_net.train_cube(
        dataset,
        out_dir=tmp_path,
        steps=60,
        batch=16,
        hidden=(32, 32),
        seed=2,
        quiet=True,
    )
    assert report["count"] == 48
    assert report["params"] > 0
    assert report["arch"].startswith("cube-sym-")
    assert 0.0 <= report["actionAgreement"] <= 1.0
    assert (tmp_path / "checkpoint.pt").exists()

    parity = cube_net.export_cube_net(net, tmp_path / "model.onnx", hidden=(32, 32))
    assert parity["maxAbsDelta"] < 1e-5
    assert (tmp_path / "model.onnx").exists()


def test_359_measure_reports_agreement_and_loss() -> None:
    """359: olcum karar uyumu ve kup kaybi uretir."""
    dataset = _synthetic_dataset(20)
    net = cube_net.build_cube_net(hidden=(32, 32), seed=4)
    report = cube_net.measure_cube_net(net, dataset)
    assert report["count"] == 20
    assert 0.0 <= report["actionAgreement"] <= 1.0
    assert report["meanCubeLoss"] >= 0.0
    assert report["takeCases"] == 20


def test_360_parser_accepts_all_subcommands() -> None:
    """360: CLI uc alt komutu da tanir."""
    parser = cube_net.build_parser()
    label = parser.parse_args(["label", "--limit", "5"])
    assert label.command == "label" and label.limit == 5
    train = parser.parse_args(["train", "--steps", "10", "--hidden", "64,64"])
    assert train.command == "train" and train.steps == 10
    assert cube_net._parse_hidden(train.hidden) == (64, 64)
    measure = parser.parse_args(["measure"])
    assert measure.command == "measure"


def test_361_parallel_labelling_matches_serial() -> None:
    """361: paralel etiketleme girdi sirasini ve degerleri korur."""
    import cube_er

    positions = [
        {
            "name": "p%d" % i,
            "board": [0] * 26,
            "turn": 1 if i % 2 == 0 else -1,
            "whiteOff": 0,
            "blackOff": 0,
            "phase": "contact",
        }
        for i in range(2)
    ]
    for index, position in enumerate(positions):
        position["board"][1] = 2 if index == 0 else -2
        position["board"][24] = -2 if index == 0 else 2
        position["board"][25] = 0
    cases = cube_er.build_cube_corpus(positions, contexts=((0, 0, 0),), owners=(0,))
    assert len(cases) == 2

    serial = cube_net.label_cases(cases, plies=0)
    parallel = cube_net.label_cases(cases, plies=0, workers=2)
    assert parallel.names == serial.names
    assert parallel.actions == serial.actions
    assert parallel.takes == serial.takes
    for got, want in zip(parallel.targets, serial.targets):
        assert got == pytest.approx(want)

def test_373_train_reports_held_out_agreement(tmp_path: Path) -> None:
    """373: rapor dogrulama bolumu karar uyumunu da verir (asiri iyimserlik onlenir)."""
    dataset = _synthetic_dataset(60)
    _net, report = cube_net.train_cube(
        dataset, out_dir=tmp_path, steps=20, batch=16, hidden=(32, 32), quiet=True
    )
    assert 0.0 <= report["valActionAgreement"] <= 1.0
    assert report["valCount"] > 0
    assert (tmp_path / "checkpoint.pt").exists()


def test_374_export_subcommand_writes_onnx_from_checkpoint(tmp_path: Path) -> None:
    """374: `export` alt komutu egitimi tekrarlamadan checkpoint'ten ONNX yazar."""
    dataset = _synthetic_dataset(40)
    cube_net.train_cube(
        dataset, out_dir=tmp_path, steps=10, batch=16, hidden=(32, 32), quiet=True
    )
    out = tmp_path / "model.onnx"
    code = cube_net.main(
        [
            "export",
            "--checkpoint",
            str(tmp_path / "checkpoint.pt"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    assert out.exists() and out.stat().st_size > 0
    parity = json.loads(Path(str(out) + ".parity.json").read_text(encoding="utf-8"))
    assert parity["maxAbsDelta"] < 1e-5
    assert parity["params"] > 0