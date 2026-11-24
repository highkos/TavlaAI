"""F7-117: ayri **kup agi** (kup kararlarini kendi agiyla ogren).

Neden ayri ag? F7-104, hamle kalitesinin kup kararina **transfer olmadigini**
gosterdi: 6'li dagilim + MET uzerinden kapali bicimde turetilen kup karari
(`EquityCubeAdvisor`) hamle aginin iyilesmesinden faydalanmiyor. TD-Gammon da
kupu ogrenmedi; dunya sampiyonu hedefi icin kup kararlari ayri ogrenilmeli.

Tasarim
-------
* **Girdi**: 221'lik vektor, **pre-roll** pozisyon (zar atilmamis). Zar
  beklentisi agin icinde ogrenilir; disarida 21 zar x ~20 hamle gezmek
  gerekmez (Faz 6 §10.2'deki `DiceAveraged` maliyetinin yerini alir).
* **Cikti**: 3 cubeful equity — ``noDouble``, ``doublePass``, ``doubleTake``.
  Karar bunlarin `argmax`'idir; esik/kalibrasyon ogrenilmis olur.
* **Antisimetri**: uc cikti da equity oldugu icin bakis cevrilince **isaret
  doner**. Bu yuzden :class:`model.SymmetricBackbone` tek kolu kullanilir ve
  cikti katmani bias'sizdir: ``f(Tx) = -f(x)`` **tanim geregi**.
* **Etiket**: gnubg kup analizi (`cube_er.CubeSession.analyse`). Ayni pozisyon
  farkli mac skorlari ve kup sahiplikleriyle caprazlanir; mac-farkindalik
  boylece ogrenilir.

Kullanim::

    python ml/cube_net.py label --out ml/runs/cube/labels.json
    python ml/cube_net.py train --labels ml/runs/cube/labels.json --out-dir ml/runs/cube
    python ml/cube_net.py measure --model ml/runs/cube/model.onnx --labels ml/runs/cube/labels.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _p in (str(HERE), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gnubg_er  # noqa: E402

CUBE_NET_VERSION = 1
DEFAULT_LABELS = HERE / "runs" / "cube" / "labels.json"
DEFAULT_OUT_DIR = HERE / "runs" / "cube"
DEFAULT_CORPUS = HERE / "artifacts" / "reference_corpus_v2.json"

#: Cikti sutunlari: cubeful equity'ler (bizim bakisimizdan).
TARGET_ORDER = ("noDouble", "doublePass", "doubleTake")
TARGET_COUNT = len(TARGET_ORDER)

#: Karar esigi: iki eylem arasindaki fark bundan kucukse **ciftlememe**
#: tercih edilir (muhafazakar; gnubg de esitlikte no-double yazar).
DECISION_EPS = 1e-9


class CubeNetError(RuntimeError):
    """Kup agi islemi yapilamadi."""


# ----------------------------------------------------------------------
# Veri
# ----------------------------------------------------------------------


@dataclass
class CubeDataset:
    """Etiketlenmis kup pozisyonlari."""

    vectors: list[list[float]]
    targets: list[list[float]]
    names: list[str]
    actions: list[str]
    takes: list[bool | None]
    meta: dict[str, Any]

    def __len__(self) -> int:
        return len(self.vectors)

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for action in self.actions:
            counts[action] = counts.get(action, 0) + 1
        return {
            "count": len(self),
            "actions": counts,
            "vectorSize": gnubg_er.VECTOR_SIZE,
            "targetOrder": list(TARGET_ORDER),
        }


def _case_vector(case: dict[str, Any]) -> list[float]:
    """Pre-roll pozisyonu 221'lik vektore cevirir (bizim bakisimizdan)."""
    return gnubg_er.vectorize(
        case["board"],
        int(case.get("whiteOff", 0) or 0),
        int(case.get("blackOff", 0) or 0),
        cube_value=int(case.get("cubeValue", 1) or 1),
        cube_owner=int(case.get("cubeOwner", 0) or 0),
        match_length=int(case.get("matchLength", 0) or 0),
        white_score=int(case.get("whiteScore", 0) or 0),
        black_score=int(case.get("blackScore", 0) or 0),
        is_crawford=bool(case.get("isCrawfordGame", False)),
        perspective=int(case.get("turn", 1) or 1),
    )


def _as_dict(case: Any) -> dict[str, Any]:
    """``CubeCase`` de olabilir, ``dict`` de; tek bicime indirger."""
    if isinstance(case, dict):
        return case
    to_dict = getattr(case, "to_dict", None)
    if to_dict is None:
        raise CubeNetError("vaka dict ya da CubeCase olmali: %r" % (type(case),))
    return to_dict()


def _label_one(payload: tuple[dict[str, Any], str, int]) -> tuple[list[float], list[float], str, str, bool]:
    """Tek vakayi etiketler (paralel isci icin; kendi gnubg oturumunu kurar)."""
    import cube_er  # noqa: PLC0415

    case, exe, plies = payload
    session = cube_er.CubeSession(Path(exe), plies=int(plies), timeout=300)
    analysis, _text = session.analyse(case)
    cube_value = int(case.get("cubeValue", 1) or 1)
    return (
        _case_vector(case),
        [float(analysis[key]) for key in TARGET_ORDER],
        str(case.get("name", "case")),
        str(analysis["action"]),
        float(analysis["doubleTake"]) < float(cube_value),
    )


def label_cases(
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path | None = None,
    plies: int = 2,
    progress: bool = False,
    workers: int = 1,
) -> CubeDataset:
    """Her vakayi gnubg kup analiziyle etiketler.

    gnubg'nin ``Proper cube action`` metni **karar** etiketidir; ``noDouble`` /
    ``doublePass`` / ``doubleTake`` satirlari ise **regresyon hedefidir**.
    Ikisi de saklanir: ag regresyonu ogrenir, karar `decide` ile turetilir ve
    olcumde gnubg'nin karariyla karsilastirilir.

    ``workers > 1`` iken her isci kendi gnubg surecini kurar; sonuclar **girdi
    sirasina** gore birlestirilir, boylece etiket dosyasi tek islemli kosuyla
    birebir ayni olur.
    """
    exe = Path(gnubg) if gnubg else gnubg_er.find_gnubg()
    normalized = [_as_dict(raw) for raw in cases]
    if workers > 1 and len(normalized) > 1:
        from concurrent.futures import ProcessPoolExecutor  # noqa: PLC0415

        payloads = [(case, str(exe), int(plies)) for case in normalized]
        rows: list[Any] = []
        with ProcessPoolExecutor(max_workers=int(workers)) as pool:
            for index, row in enumerate(pool.map(_label_one, payloads), start=1):
                rows.append(row)
                if progress and index % 25 == 0:
                    print("  etiket %d/%d" % (index, len(normalized)), file=sys.stderr, flush=True)
        return CubeDataset(
            vectors=[row[0] for row in rows],
            targets=[row[1] for row in rows],
            names=[row[2] for row in rows],
            actions=[row[3] for row in rows],
            takes=[row[4] for row in rows],
            meta={"gnubgPlies": int(plies), "gnubg": str(exe), "workers": int(workers)},
        )

    import cube_er  # noqa: PLC0415

    session = cube_er.CubeSession(exe, plies=plies, timeout=300)
    vectors: list[list[float]] = []
    targets: list[list[float]] = []
    names: list[str] = []
    actions: list[str] = []
    takes: list[bool | None] = []
    for index, case in enumerate(normalized, start=1):
        analysis, _text = session.analyse(case)
        vectors.append(_case_vector(case))
        targets.append([float(analysis[key]) for key in TARGET_ORDER])
        names.append(str(case.get("name", "case%d" % index)))
        actions.append(str(analysis["action"]))
        # gnubg "take" alanini yalnizca ciftlemek dogruyken yazar. Kabul/red
        # karari her vakada tanimli oldugu icin hedef equity'den turetiliyor:
        # kabul etmek `doubleTake`, reddetmek `cubeValue` getirir.
        cube_value = int(case.get("cubeValue", 1) or 1)
        takes.append(float(analysis["doubleTake"]) < float(cube_value))
        if progress and index % 25 == 0:
            print("  etiket %d/%d" % (index, len(normalized)), file=sys.stderr, flush=True)
    return CubeDataset(
        vectors=vectors,
        targets=targets,
        names=names,
        actions=actions,
        takes=takes,
        meta={"gnubgPlies": int(plies), "gnubg": str(exe)},
    )


def save_dataset(dataset: CubeDataset, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CUBE_NET_VERSION,
        "targetOrder": list(TARGET_ORDER),
        "meta": dataset.meta,
        "stats": dataset.stats(),
        "cases": [
            {
                "name": name,
                "vector": vector,
                "target": target,
                "action": action,
                "take": take,
            }
            for name, vector, target, action, take in zip(
                dataset.names, dataset.vectors, dataset.targets, dataset.actions, dataset.takes
            )
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_dataset(path: Path) -> CubeDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(payload.get("version", 0)) != CUBE_NET_VERSION:
        raise CubeNetError("desteklenmeyen etiket surumu: %r" % (payload.get("version"),))
    cases = payload["cases"]
    return CubeDataset(
        vectors=[list(c["vector"]) for c in cases],
        targets=[list(c["target"]) for c in cases],
        names=[str(c["name"]) for c in cases],
        actions=[str(c["action"]) for c in cases],
        takes=[c.get("take") for c in cases],
        meta=dict(payload.get("meta") or {}),
    )


# ----------------------------------------------------------------------
# Ag
# ----------------------------------------------------------------------


def build_cube_net(*, hidden: Sequence[int] = (256, 256, 128), seed: int | None = None):
    """Kup agini kurar: simetrik govde + bias'siz 3 cikti."""
    import torch  # noqa: PLC0415
    import torch.nn as nn  # noqa: PLC0415

    from model import SymmetricBackbone  # noqa: PLC0415

    if seed is not None:
        torch.manual_seed(seed)

    class CubeNet(nn.Module):
        """``f(Tx) = -f(x)``: uc cubeful equity, tek kol, bias yok."""

        output_version = 2

        def __init__(self) -> None:
            super().__init__()
            self.backbone = SymmetricBackbone(gnubg_er.VECTOR_SIZE, *hidden)
            self.head = nn.Linear(self.backbone.out_dim, TARGET_COUNT, bias=False)

        @property
        def arch(self) -> str:
            b = self.backbone
            return "cube-sym-" + "-".join(str(w) for w in (b.in_dim, *b.hidden))

        def forward(self, x):
            h, _even = self.backbone(x)
            return self.head(h)

    net = CubeNet()
    net.eval()
    return net


def parameter_count(net) -> int:
    return sum(p.numel() for p in net.parameters() if p.requires_grad)


# ----------------------------------------------------------------------
# Egitim
# ----------------------------------------------------------------------


def train_cube(
    dataset: CubeDataset,
    *,
    out_dir: Path,
    steps: int = 4000,
    lr: float = 1e-3,
    batch: int = 128,
    val_fraction: float = 0.15,
    weight_decay: float = 1e-4,
    seed: int = 0,
    device: str = "cpu",
    hidden: Sequence[int] = (256, 256, 128),
    quiet: bool = False,
) -> tuple[Any, dict[str, Any]]:
    """Kup agini egitir; ``(net, report)`` dondurur."""
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415

    if len(dataset) < 8:
        raise CubeNetError("en az 8 etiketli vaka gerekli: %d" % len(dataset))

    x = torch.tensor(dataset.vectors, dtype=torch.float32)
    y = torch.tensor(dataset.targets, dtype=torch.float32)

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(dataset))
    n_val = max(1, int(round(len(dataset) * val_fraction)))
    val_idx = torch.tensor(order[:n_val], dtype=torch.long)
    train_idx = torch.tensor(order[n_val:], dtype=torch.long)

    net = build_cube_net(hidden=hidden, seed=seed)
    net.to(device)
    net.train()
    opt = torch.optim.Adam(
        [p for p in net.parameters() if p.requires_grad], lr=lr, weight_decay=weight_decay
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, steps), eta_min=lr * 0.1)
    loss_fn = torch.nn.MSELoss()

    started = time.time()
    history: list[float] = []
    best_state: dict[str, Any] | None = None
    best_val = float("inf")
    best_step = 0
    n_train = int(train_idx.numel())
    for step in range(1, steps + 1):
        sel = train_idx[torch.randint(0, n_train, (min(batch, n_train),))]
        pred = net(x[sel].to(device))
        loss = loss_fn(pred, y[sel].to(device))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        value = float(loss.detach().to("cpu"))
        history.append(value)
        if step % 250 == 0 or step == steps:
            net.eval()
            with torch.no_grad():
                val = float(loss_fn(net(x[val_idx].to(device)), y[val_idx].to(device)).to("cpu"))
            net.train()
            if val < best_val:
                best_val = val
                best_step = step
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            if not quiet:
                print(
                    "[cube %d/%d] loss=%.6f val=%.6f" % (step, steps, value, val),
                    file=sys.stderr,
                )

    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        pred = net(x.to(device)).to("cpu")
        mse = float(loss_fn(pred, y).to("cpu"))
        mae = float(torch.mean(torch.abs(pred - y)).to("cpu"))
        val_pred = net(x[val_idx].to(device)).to("cpu")
        val_mse = float(loss_fn(val_pred, y[val_idx]).to("cpu"))
        rows = pred.tolist()
    # Karar uyumu: `decide` (min semantigi) gnubg'nin ciftle/ciftleme karariyla
    # karsilastirilir. Argmax **yanlis** olurdu: ciftleme degeri
    # `min(doublePass, doubleTake)`.
    agree = 0
    for index, equities in enumerate(rows):
        ours = "double" if decide(equities)["shouldDouble"] else "no-double"
        if ours == dataset.actions[index]:
            agree += 1
    # Ayni olcut dogrulama bolumunde: tum veri uzerindeki uyum egitim
    # ornegini de kapsadigi icin tek basina iyimserdir.
    val_agree = 0
    for index in val_idx.tolist():
        ours = "double" if decide(rows[index])["shouldDouble"] else "no-double"
        if ours == dataset.actions[index]:
            val_agree += 1

    report = {
        "cubeNetVersion": CUBE_NET_VERSION,
        "arch": net.arch,
        "params": int(parameter_count(net)),
        "hidden": list(hidden),
        "count": len(dataset),
        "trainCount": n_train,
        "valCount": n_val,
        "steps": int(steps),
        "bestStep": int(best_step),
        "bestValMse": best_val,
        "valMse": val_mse,
        "mse": mse,
        "mae": mae,
        "actionAgreement": agree / len(dataset),
        "valActionAgreement": val_agree / n_val,
        "elapsedSeconds": round(time.time() - started, 2),
        "device": device,
        "seed": int(seed),
        "lr": lr,
        "batch": int(batch),
        "weightDecay": weight_decay,
        "targetOrder": list(TARGET_ORDER),
        "datasetStats": dataset.stats(),
        "history": history,
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"model": net.state_dict(), "cubeNet": report}, str(out_dir / "checkpoint.pt"))
    (out_dir / "train_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return net, report


def export_cube_net(net, out_path: Path, *, hidden: Sequence[int] = (256, 256, 128)) -> dict:
    """Kup agini ONNX'e yazar ve sayisal pariteyi dogrular."""
    import numpy as np  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415
    import torch  # noqa: PLC0415

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Ihracat CPU'da yapilir: ONNX Runtime CPU oturumu ve `torch.onnx.export`
    # ayni cihazda olmali, aksi halde buffer'lar (Q_minus/Q_plus) uyusmaz.
    net.to("cpu")
    net.eval()
    dummy = torch.zeros(1, gnubg_er.VECTOR_SIZE, dtype=torch.float32)
    torch.onnx.export(
        net,
        (dummy,),
        str(out_path),
        input_names=["features"],
        output_names=["cube_equity"],
        dynamic_axes={"features": {0: "batch"}, "cube_equity": {0: "batch"}},
        opset_version=15,
        do_constant_folding=True,
        export_params=True,
    )

    import onnx  # noqa: PLC0415

    m = onnx.load(str(out_path))
    for key, value in {
        "feature_version": "1",
        "vector_size": str(gnubg_er.VECTOR_SIZE),
        "arch": net.arch,
        "trained_by": "faz7-cube-net",
        "output_version": "2",
        "cube_net_version": str(CUBE_NET_VERSION),
        "target_order": ",".join(TARGET_ORDER),
        "symmetry": "exact",
    }.items():
        entry = m.metadata_props.add()
        entry.key = key
        entry.value = value
    onnx.save(m, str(out_path))

    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(11)
    max_delta = 0.0
    for size in (1, 2, 13, 64):
        x = rng.standard_normal((size, gnubg_er.VECTOR_SIZE)).astype(np.float32)
        with torch.no_grad():
            expected = net(torch.from_numpy(x)).numpy()
        got = sess.run(["cube_equity"], {"features": x})[0]
        max_delta = max(max_delta, float(np.max(np.abs(expected - got))))
    if max_delta > 1e-5:
        raise CubeNetError("ONNX paritesi bozuk: |delta|=%.3e" % max_delta)
    return {"maxAbsDelta": max_delta, "arch": net.arch, "params": int(parameter_count(net))}


# ----------------------------------------------------------------------
# Karar
# ----------------------------------------------------------------------


def decide(equities: Sequence[float], *, cube_value: int = 1) -> dict[str, Any]:
    """Uc cubeful equity'den kup karari.

    ``shouldDouble``: ``min(doublePass, doubleTake) > noDouble``. **min**, cunku
    rakip bize en kotu cevabi secer: kabul ederse ``doubleTake``, reddederse
    ``cubeValue``; ``doublePass`` zaten ``cubeValue``'a esit oldugundan
    ``min`` ikisini birlikte temsil eder (``cube_er.double_value`` ile ayni).
    ``shouldTake`` (rakip perspektifi): kabul ``-doubleTake``, red ``-cubeValue``;
    kabul ancak ``doubleTake < cubeValue`` ise dogru.
    """
    if len(equities) != TARGET_COUNT:
        raise CubeNetError("%d equity gerekli, %d verildi" % (TARGET_COUNT, len(equities)))
    no_double, double_pass, double_take = (float(v) for v in equities)
    doubled = min(double_pass, double_take)
    should_double = doubled > no_double + DECISION_EPS
    should_take = double_take < float(cube_value) - DECISION_EPS
    return {
        "shouldDouble": bool(should_double),
        "shouldTake": bool(should_take),
        "noDouble": no_double,
        "doublePass": double_pass,
        "doubleTake": double_take,
        "bestValue": max(no_double, doubled),
        "loss": max(0.0, max(no_double, doubled) - (doubled if should_double else no_double)),
    }


def measure_cube_net(net, dataset: CubeDataset) -> dict[str, Any]:
    """Etiketli vakalarda karar uyumu ve kup equity kaybi."""
    import torch  # noqa: PLC0415

    net.eval()
    device = next(net.parameters()).device
    x = torch.tensor(dataset.vectors, dtype=torch.float32)
    with torch.no_grad():
        pred = net(x.to(device)).to("cpu").tolist()

    agree = 0
    take_agree = 0
    take_total = 0
    losses: list[float] = []
    for index, equities in enumerate(pred):
        decision = decide(equities)
        ours = "double" if decision["shouldDouble"] else "no-double"
        if ours == dataset.actions[index]:
            agree += 1
        expected_take = dataset.takes[index]
        if expected_take is not None:
            take_total += 1
            if bool(decision["shouldTake"]) == bool(expected_take):
                take_agree += 1
        # gnubg'nin cubeful equity'siyle kayip (etiket = gnubg analizi).
        # Ciftlemenin degeri `min(doublePass, doubleTake)`: rakip en kotu
        # cevabi secer.
        target = dataset.targets[index]
        doubled = min(target[1], target[2])
        best = max(target[0], doubled)
        chosen = doubled if decision["shouldDouble"] else target[0]
        losses.append(max(0.0, best - chosen))

    mean_loss = sum(losses) / len(losses) if losses else float("nan")
    return {
        "cubeNetVersion": CUBE_NET_VERSION,
        "count": len(dataset),
        "actionAgreement": agree / len(dataset) if dataset else float("nan"),
        "takeAgreement": (take_agree / take_total) if take_total else None,
        "takeCases": take_total,
        "meanCubeLoss": mean_loss,
        "maxCubeLoss": max(losses) if losses else float("nan"),
        "targetOrder": list(TARGET_ORDER),
    }


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _load_positions(path: Path, limit: int | None, stride: int) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) and "cases" in payload else payload
    if stride > 1:
        cases = cases[::stride]
    if limit is not None:
        cases = cases[:limit]
    return list(cases)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="cube_net", description="F7-117: ayri kup agi")
    sub = ap.add_subparsers(dest="command", required=True)

    lab = sub.add_parser("label", help="pozisyonlari gnubg kup analiziyle etiketle")
    lab.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    lab.add_argument("--out", type=Path, default=DEFAULT_LABELS)
    lab.add_argument("--limit", type=int, default=400)
    lab.add_argument("--stride", type=int, default=1)
    lab.add_argument("--plies", type=int, default=2)
    lab.add_argument("--workers", type=int, default=1)
    lab.add_argument("--gnubg", default=None)
    lab.add_argument("--quiet", action="store_true")

    trn = sub.add_parser("train", help="kup agini egit ve ONNX'e yaz")
    trn.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    trn.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    trn.add_argument("--steps", type=int, default=4000)
    trn.add_argument("--lr", type=float, default=1e-3)
    trn.add_argument("--batch", type=int, default=128)
    trn.add_argument("--val-fraction", type=float, default=0.15)
    trn.add_argument("--weight-decay", type=float, default=1e-4)
    trn.add_argument("--seed", type=int, default=0)
    trn.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    trn.add_argument("--hidden", default="256,256,128")
    trn.add_argument("--quiet", action="store_true")

    mea = sub.add_parser("measure", help="etiketli vakalarda karar uyumunu olc")
    mea.add_argument("--model", type=Path, default=DEFAULT_OUT_DIR / "model.onnx")
    mea.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    mea.add_argument("--out", type=Path, default=None)

    exp = sub.add_parser("export", help="checkpoint.pt'yi yeniden egitmeden ONNX'e yaz")
    exp.add_argument("--checkpoint", type=Path, default=DEFAULT_OUT_DIR / "checkpoint.pt")
    exp.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR / "model.onnx")
    exp.add_argument("--hidden", default=None, help="varsayilan: checkpoint'teki genislikler")
    return ap


def _parse_hidden(text: str) -> tuple[int, ...]:
    widths = tuple(int(chunk) for chunk in str(text).split(",") if chunk.strip())
    if not widths:
        raise CubeNetError("--hidden bos olamaz")
    return widths


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "label":
        import cube_er  # noqa: PLC0415

        positions = _load_positions(Path(args.corpus), args.limit, args.stride)
        cases = cube_er.build_cube_corpus(positions)
        if not args.quiet:
            print("kup vakasi: %d" % len(cases), file=sys.stderr)
        dataset = label_cases(
            cases,
            gnubg=Path(args.gnubg) if args.gnubg else None,
            plies=args.plies,
            progress=not args.quiet,
            workers=args.workers,
        )
        path = save_dataset(dataset, Path(args.out))
        print("etiket: %s (%d vaka)" % (path, len(dataset)))
        return 0

    if args.command == "train":
        dataset = load_dataset(Path(args.labels))
        net, report = train_cube(
            dataset,
            out_dir=Path(args.out_dir),
            steps=args.steps,
            lr=args.lr,
            batch=args.batch,
            val_fraction=args.val_fraction,
            weight_decay=args.weight_decay,
            seed=args.seed,
            device=args.device,
            hidden=_parse_hidden(args.hidden),
            quiet=args.quiet,
        )
        parity = export_cube_net(net, Path(args.out_dir) / "model.onnx", hidden=_parse_hidden(args.hidden))
        (Path(args.out_dir) / "parity.json").write_text(
            json.dumps(parity, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            "kup agi: params=%d valMse=%.6f karar uyumu=%.4f"
            % (report["params"], report["valMse"], report["actionAgreement"])
        )
        return 0

    if args.command == "export":
        import torch  # noqa: PLC0415

        payload = torch.load(str(args.checkpoint), map_location="cpu", weights_only=False)
        report = dict(payload.get("cubeNet") or {})
        hidden = (
            _parse_hidden(args.hidden)
            if args.hidden
            else tuple(int(w) for w in (report.get("hidden") or (256, 256, 128)))
        )
        net = build_cube_net(hidden=hidden)
        net.load_state_dict(payload["model"])
        net.eval()
        parity = export_cube_net(net, Path(args.out), hidden=hidden)
        Path(str(args.out) + ".parity.json").write_text(
            json.dumps(parity, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            "kup agi ihrac: %s (params=%d, delta=%.2e)"
            % (args.out, parity["params"], parity["maxAbsDelta"])
        )
        return 0

    if args.command == "measure":
        import onnxruntime as ort  # noqa: PLC0415
        import torch  # noqa: PLC0415

        dataset = load_dataset(Path(args.labels))
        sess = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
        x = torch.tensor(dataset.vectors, dtype=torch.float32).numpy()
        pred = sess.run(["cube_equity"], {"features": x})[0].tolist()

        class _Wrapper:
            def eval(self):
                return self

            def __call__(self, tensor):
                return torch.tensor(pred, dtype=torch.float32)

        report = measure_cube_net(_Wrapper(), dataset)
        report["model"] = str(args.model)
        out = Path(args.out) if args.out else Path(args.model).with_name("measure.json")
        out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(
            "karar uyumu=%.4f kup kaybi=%.4f -> %s"
            % (report["actionAgreement"], report["meanCubeLoss"], out)
        )
        return 0

    raise CubeNetError("bilinmeyen komut: %r" % (args.command,))


if __name__ == "__main__":
    raise SystemExit(main())
