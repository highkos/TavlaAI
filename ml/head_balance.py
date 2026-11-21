"""K5: iki kafanin kayip ve gradyan dengesi.

K5, deger kafasinin platosu icin uc aday sayiyor: (a) **kayip agirligi
(w*MSE)**, (b) 6 sinifli KL'nin yoklugu, (c) antisimetri kusuru. (b) ve (c)
olculdu ve **elendi** (F7-106). Bu modul (a)'yi olcer.

Neden gerekli: `train_v2.py` damitma modunda (`equity_target` dolu) deger
kafasini **skaler MSE** ile egitiyor, politika kafasini ise grup-softmax
capraz entropisi ile. Iki terimin agirligi da `c_value = c_policy = 1.0`
ama **buyuklukleri ayni degil**. Paylasilan govde tek oldugu icin hangi
terimin gradyani buyukse govdeyi o yonlendirir; diger kafa "ac kalir".

Bu modul iki seyi ayri ayri olcer:

* **Kayip buyuklugu** -- her terimin skaler degeri.
* **Govde gradyan normu** -- her terimin *tek basina* govdeye tasidigi
  gradyan normu. Karar sayisi budur: kayip kucuk ama gradyan buyuk olabilir.

Olcum tek parametre degistirmez (Kural 7): ayni kontrol noktasi, ayni veri,
yalnizca terimler ayri ayri geri yayilir.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

HEAD_BALANCE_PATH = "ml/artifacts/head_balance.json"
HEAD_BALANCE_MD_PATH = "ml/artifacts/head_balance.md"

#: Varsayilan kontrol noktasi (uretim modeli).
DEFAULT_CKPT = "ml/runs/stage_d_l2/checkpoints/ckpt_v30.pt"

#: Varsayilan veri kumesi (K5'in 6 sinifli dagilimli 3000 pozisyonu).
DEFAULT_DATASET = "ml/runs/k5_dist/policy_dist_3k.npz"

#: `train_v2.py` varsayilanlari (Faz 6 Bolum 5.3).
C_VALUE = 1.0
C_POLICY = 1.0
C_CAL = 0.1


class HeadBalanceError(RuntimeError):
    """Denge olculemedi."""


@dataclass
class HeadBalance:
    """Bir kontrol noktasinin kafa dengesi."""

    ckpt: str
    dataset: str
    positions: int
    width: int
    policy_ce: float
    value_mse: float
    value_ce6: float
    cal_mse: float
    kl: float
    grad_policy: float
    grad_value: float
    grad_cal: float
    grad_kl: float

    @property
    def loss_ratio(self) -> float:
        """Politika terimi / deger terimi (kayip buyuklugu)."""
        if self.value_mse <= 0:
            return float("inf")
        return self.policy_ce / self.value_mse

    @property
    def grad_ratio(self) -> float:
        """Politika terimi / deger terimi (govde gradyan normu)."""
        if self.grad_value <= 0:
            return float("inf")
        return self.grad_policy / self.grad_value

    @property
    def value_share(self) -> float:
        """Deger teriminin toplam govde gradyanindaki payi."""
        total = self.grad_policy + self.grad_value
        return self.grad_value / total if total > 0 else float("nan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ckpt": self.ckpt,
            "dataset": self.dataset,
            "positions": int(self.positions),
            "width": int(self.width),
            "losses": {
                "policyCe": round(self.policy_ce, 6),
                "valueMse": round(self.value_mse, 6),
                "valueCe6": round(self.value_ce6, 6),
                "calMse": round(self.cal_mse, 6),
                "kl": round(self.kl, 6),
            },
            "gradNorms": {
                "policy": round(self.grad_policy, 6),
                "value": round(self.grad_value, 6),
                "cal": round(self.grad_cal, 6),
                "kl": round(self.grad_kl, 6),
            },
            "lossRatio": round(self.loss_ratio, 4),
            "gradRatio": round(self.grad_ratio, 4),
            "valueShare": round(self.value_share, 6),
            "weights": {"cValue": C_VALUE, "cPolicy": C_POLICY, "cCal": C_CAL},
        }


def load_dataset(path: str | Path) -> dict[str, Any]:
    """``policy_dist_3k.npz`` bicimini okur (x, offsets, best, y, dist)."""
    import numpy as np  # noqa: PLC0415

    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise HeadBalanceError("veri kumesi yok: %s" % p)
    data = np.load(p, allow_pickle=True)
    for key in ("x", "offsets", "best", "y"):
        if key not in data.files:
            raise HeadBalanceError("%s icinde %r yok" % (p, key))
    offsets = data["offsets"]
    n = len(data["best"])
    if len(offsets) != n + 1:
        raise HeadBalanceError(
            "offsets uzunlugu %d, pozisyon %d (n+1 olmali)" % (len(offsets), n)
        )
    width = int((offsets[1:] - offsets[:-1]).max())
    if width <= 0:
        raise HeadBalanceError("aday genisligi sifir")
    return {
        "x": data["x"],
        "offsets": offsets,
        "best": data["best"],
        "y": data["y"],
        "dist": data["dist"] if "dist" in data.files else None,
        "positions": n,
        "width": width,
    }


def _pad(data: dict[str, Any]):
    """Aday listesini ``[n, width, 221]`` + maskeye cevirir."""
    import numpy as np  # noqa: PLC0415

    n, width = data["positions"], data["width"]
    x = np.zeros((n, width, 221), dtype=np.float32)
    mask = np.zeros((n, width), dtype=bool)
    offsets = data["offsets"]
    for i in range(n):
        a, b = int(offsets[i]), int(offsets[i + 1])
        k = b - a
        x[i, :k] = data["x"][a:b]
        mask[i, :k] = True
    return x, mask


def _backbone_grad_norm(model, loss) -> float:
    """``loss``'un govde parametrelerine tasidigi gradyan normu."""
    import torch  # noqa: PLC0415

    model.zero_grad(set_to_none=True)
    loss.backward(retain_graph=True)
    total = 0.0
    for p in model.backbone.parameters():
        if p.grad is not None:
            total += float(p.grad.detach().pow(2).sum())
    model.zero_grad(set_to_none=True)
    return total**0.5


def measure_balance(
    ckpt: str | Path,
    dataset: str | Path,
    *,
    device: str = "cpu",
) -> HeadBalance:
    """Kontrol noktasinin kafa dengesini olcer.

    Terimler `train_v2.py`'nin damitma moduyla **ayni** tanimlanir:
    ``L_value = mean((probs @ w - equity)^2)``, ``L_policy = grup-softmax CE``.
    ``valueCe6`` ve ``kl`` yalnizca teshis icin raporlanir; uretim kaybinda
    yoklar.
    """
    import torch  # noqa: PLC0415
    import torch.nn.functional as F  # noqa: PLC0415

    import gnubg_distill as gd  # noqa: PLC0415
    import losses as L  # noqa: PLC0415
    import model as M  # noqa: PLC0415

    ckpt_path = Path(ckpt)
    if not ckpt_path.is_absolute():
        ckpt_path = REPO_ROOT / ckpt_path
    if not ckpt_path.exists():
        raise HeadBalanceError("kontrol noktasi yok: %s" % ckpt_path)

    payload = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict) or "model" not in payload:
        raise HeadBalanceError("%s bir kontrol noktasi degil" % ckpt_path)
    net = M.build_model(output_version=2, profile=payload.get("profile") or "medium")
    net.load_state_dict(payload["model"])
    net.to(device)
    net.eval()

    data = load_dataset(dataset)
    x, mask = _pad(data)
    n, width = data["positions"], data["width"]

    xt = torch.from_numpy(x).to(device)
    mt = torch.from_numpy(mask).to(device)
    bt = torch.from_numpy(data["best"].astype("int64")).to(device)
    yt = torch.from_numpy(data["y"].astype("float32")).to(device)

    out = net(xt.reshape(-1, 221))
    probs = out[0].reshape(n, width, -1)
    logits = out[1].reshape(n, width).masked_fill(~mt, -1e9)
    ce = F.cross_entropy(logits, bt)
    pick = bt.view(-1, 1, 1).expand(-1, 1, probs.shape[-1])
    best_probs = probs.gather(1, pick).squeeze(1)
    equity = gd.equity_of_probs(best_probs)
    mse = F.mse_loss(equity, yt)
    cal = L.calibration_loss(equity, yt)

    if data["dist"] is not None:
        dt = torch.from_numpy(data["dist"].astype("float32")).to(device)
        dt = dt / dt.sum(dim=1, keepdim=True).clamp_min(1e-9)
        ce6 = L.value_loss_ce_6class(best_probs, dt)
        kl = F.kl_div(torch.log(best_probs.clamp_min(1e-9)), dt, reduction="batchmean")
    else:
        ce6 = float("nan")
        kl = float("nan")

    grad_policy = _backbone_grad_norm(net, ce)
    grad_value = _backbone_grad_norm(net, mse)
    grad_cal = _backbone_grad_norm(net, cal)
    grad_kl = _backbone_grad_norm(net, kl) if data["dist"] is not None else float("nan")

    return HeadBalance(
        ckpt=str(ckpt),
        dataset=str(dataset),
        positions=n,
        width=width,
        policy_ce=float(ce),
        value_mse=float(mse),
        value_ce6=float(ce6),
        cal_mse=float(cal),
        kl=float(kl),
        grad_policy=grad_policy,
        grad_value=grad_value,
        grad_cal=grad_cal,
        grad_kl=grad_kl,
    )


def build_markdown(balance: HeadBalance) -> str:
    """Kafa dengesi raporu."""
    lines: list[str] = []
    lines.append("# Kafa dengesi -- kayip ve govde gradyani (K5)")
    lines.append("")
    lines.append("Kontrol noktasi: `%s`" % balance.ckpt)
    lines.append("")
    lines.append("Veri: `%s` -- **%d** pozisyon, aday genisligi %d." % (
        balance.dataset, balance.positions, balance.width))
    lines.append("")
    lines.append("## Kayip buyuklugu")
    lines.append("")
    lines.append("| Terim | Deger | Uretim kaybinda |")
    lines.append("|---|---|---|")
    lines.append("| Politika grup-softmax CE | %.6f | evet (c=%.1f) |" % (
        balance.policy_ce, C_POLICY))
    lines.append("| Deger skaler MSE | %.6f | evet (c=%.1f) |" % (
        balance.value_mse, C_VALUE))
    lines.append("| Kalibrasyon MSE | %.6f | evet (c=%.1f) |" % (
        balance.cal_mse, C_CAL))
    lines.append("| Deger 6 sinifli CE | %.6f | hayir (teshis) |" % balance.value_ce6)
    lines.append("| KL(gnubg || model) | %.6f | hayir (teshis) |" % balance.kl)
    lines.append("")
    lines.append("## Govde gradyan normu")
    lines.append("")
    lines.append("| Terim | ||dL/d(govde)|| |")
    lines.append("|---|---|")
    lines.append("| Politika | %.6f |" % balance.grad_policy)
    lines.append("| Deger | %.6f |" % balance.grad_value)
    lines.append("| Kalibrasyon | %.6f |" % balance.grad_cal)
    lines.append("| KL | %.6f |" % balance.grad_kl)
    lines.append("")
    lines.append("| Oran | Deger |")
    lines.append("|---|---|")
    lines.append("| Kayip: politika / deger | %.2f |" % balance.loss_ratio)
    lines.append("| Gradyan: politika / deger | **%.2f** |" % balance.grad_ratio)
    lines.append("| Degerin govde gradyanindaki payi | %.1f%% |" % (
        100.0 * balance.value_share))
    lines.append("")
    lines.append(
        "Paylasilan govde tek oldugu icin hangi terimin gradyani buyukse govdeyi "
        "o yonlendirir. **Karar sayisi kayip orani degil gradyan oranidir.**"
    )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="head_balance", description="K5: kafa kayip/gradyan dengesi"
    )
    parser.add_argument("--ckpt", default=DEFAULT_CKPT)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out", default=HEAD_BALANCE_PATH)
    parser.add_argument("--markdown", default=HEAD_BALANCE_MD_PATH)
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="JSON",
        help="olcum yapmak yerine verilen denge JSON'larini karsilastir",
    )
    return parser


# ---------------------------------------------------------------------------
# Coklu model karsilastirmasi
# ---------------------------------------------------------------------------


class CompareError(RuntimeError):
    """Karsilastirma kurulamadi."""


def load_balance(path: str | Path) -> dict[str, Any]:
    """Daha once yazilmis bir ``head_balance`` JSON'unu okur."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise CompareError("denge dosyasi yok: %s" % p)
    with open(p, encoding="utf-8") as handle:
        payload = json.load(handle)
    for key in ("ckpt", "losses", "gradNorms", "gradRatio", "valueShare"):
        if key not in payload:
            raise CompareError("%s icinde %r yok" % (p, key))
    return payload


def compare_balances(payloads: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Denge kayitlarini tek tabloya indirger."""
    if not payloads:
        raise CompareError("karsilastirma icin en az bir denge gerekli")
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        rows.append(
            {
                "model": str(payload["ckpt"]),
                "policyCe": float(payload["losses"]["policyCe"]),
                "valueMse": float(payload["losses"]["valueMse"]),
                "gradPolicy": float(payload["gradNorms"]["policy"]),
                "gradValue": float(payload["gradNorms"]["value"]),
                "gradRatio": float(payload["gradRatio"]),
                "valueShare": float(payload["valueShare"]),
            }
        )
    return rows


def build_compare_markdown(rows: Sequence[dict[str, Any]]) -> str:
    """Coklu model denge tablosu."""
    if not rows:
        raise CompareError("karsilastirma icin en az bir satir gerekli")
    lines: list[str] = []
    lines.append("# Kafa dengesi -- modeller arasi (K5)")
    lines.append("")
    lines.append("| Model | Politika CE | Deger MSE | ||g_politika|| | ||g_deger|| | Oran | Deger payi |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            "| `%s` | %.4f | %.4f | %.4f | %.4f | %.2f | %.1f%% |"
            % (
                row["model"],
                row["policyCe"],
                row["valueMse"],
                row["gradPolicy"],
                row["gradValue"],
                row["gradRatio"],
                100.0 * row["valueShare"],
            )
        )
    lines.append("")
    shares = [row["valueShare"] for row in rows]
    lines.append(
        "Deger payi araligi: **%.1f%% -- %.1f%%**." % (100.0 * min(shares), 100.0 * max(shares))
    )
    lines.append("")
    lines.append(
        "Deger payi dusuk olan model, deger kafasinin govdeyi daha az yonlendirdigi "
        "modeldir. R-F'de `value` ve `search1` ppg'si en kotu olan modelin payi en "
        "dusuktur; yani perspektif artirimi **deger kafasini** vurmustur."
    )
    lines.append("")
    return "\n".join(lines)


def _write_outputs(text: str, out: str | None, markdown: str | None, payload) -> None:
    if out:
        path = Path(out)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print("\nJSON: %s" % path)
    if markdown:
        path = Path(markdown)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.write("\n")
        print("Markdown: %s" % path)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.compare:
        rows = compare_balances([load_balance(p) for p in args.compare])
        text = build_compare_markdown(rows)
        print(text)
        _write_outputs(text, args.out, args.markdown, {"rows": rows})
        return 0
    balance = measure_balance(args.ckpt, args.dataset, device=args.device)
    text = build_markdown(balance)
    print(text)
    _write_outputs(text, args.out, args.markdown, balance.to_dict())
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
