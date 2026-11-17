"""Faz 6 Bolum 6.1: D1-D3 kalibrasyon teshisi.

Faz 5 taban cizgisi kalibrasyonu bozuk (``ml/artifacts/stage_f_baseline.md``):
egim 0.2431, korelasyon 0.2431, MAE 0.8014, std orani 2.78. Bu modul, bozulmanin
kaynagini **olcer**; tahmin etmez.

D1 - Egitim olcegi
    Ayni mimari ve hedefle, artan oyun sayisiyla ogrenme egrisi. Egri hala
    iniyorsa sorun olcek, cikti ise olcek degil.

D2 - Hedef tanimi
    ``lambda = 1.0`` (saf Monte Carlo) vs ``lambda = 0.7`` (TD). TD hedefi
    baslangicta yanlidir; kalibrasyonu bozuyorsa D2 isaretlenir.

D3 - Kafa yapisi
    Tek skaler deger kafasi vs 6 cikti li dislayici olasilik kafasi. Skaler kafa
    dagilim uretmedigi icin mars/backgammon bilgisini tasiyamaz.

Karar agaci (Faz 6 Bolum 6.1):

    D1 isaretli  -> veri olcegini buyut (Asama C)
    D2 isaretli  -> ``lambda = 1.0``
    D3 isaretli  -> 6 cikti li kafa + ``L_cal``

Kullanim:
    python diagnose.py --shards runs/stage_d/shards --out artifacts/stage_f_diagnosis.md
    python diagnose.py --shards runs/stage_d/shards --only d3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import calibration  # noqa: E402
import equity  # noqa: E402
import losses  # noqa: E402
import model as model_mod  # noqa: E402
import replay as replay_mod  # noqa: E402
import targets as targets_mod  # noqa: E402
from replay import ReplayBuffer, is_usable_game  # noqa: E402
from shards import DEC_CHOSEN_IS_TERMINAL, DEC_IS_LEARNER  # noqa: E402

#: D1 olcek noktalari (Faz 6 Bolum 6.1). Mevcut veri yetmezse kirpilir.
D1_SCALES = (125, 250, 500, 1000, 5000, 10000)

#: D2 hedef tanimlari.
D2_LAMBDAS = (1.0, 0.7)

#: D3 kafa yapilari.
D3_HEADS = ("scalar", "six")

#: Teshis icin sabit egitim butcesi (adim). Kucuk tutulur: amac kiyas, mutlak basari degil.
DEFAULT_STEPS = 300
DEFAULT_BATCH = 256
DEFAULT_LR = 1e-3
DEFAULT_SEED = 20261114

#: CAL / VAL oyun sayisi (egitim kumesinden ayri).
CAL_GAMES = 100
VAL_GAMES = 100

#: D1 "hala iniyor" esigi: son iki nokta arasindaki MAE iyilesmesi bundan kucukse
#: ogrenme egrisi duzlesmis sayilir.
D1_PLATEAU_RATIO = 0.05


@dataclass
class DiagnosisConfig:
    """Tek bir teshis kosusu."""

    label: str
    games: int
    lam: float = 1.0
    head: str = "six"
    steps: int = DEFAULT_STEPS
    batch: int = DEFAULT_BATCH
    lr: float = DEFAULT_LR
    seed: int = DEFAULT_SEED
    c_cal: float = losses.DEFAULT_C_CAL


@dataclass
class DiagnosisResult:
    """Tek bir kosunun olculen sonuclari."""

    label: str
    games: int
    lam: float
    head: str
    train_samples: int = 0
    val_samples: int = 0
    value_loss: float = float("nan")
    cal_loss: float = float("nan")
    metrics: dict[str, float] = field(default_factory=dict)
    calibrated: bool = False
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "games": self.games,
            "lambda": self.lam,
            "head": self.head,
            "trainSamples": self.train_samples,
            "valSamples": self.val_samples,
            "valueLoss": self.value_loss,
            "calLoss": self.cal_loss,
            "metrics": self.metrics,
            "calibrated": self.calibrated,
            "seconds": round(self.seconds, 2),
        }


# ----------------------------------------------------------------------
# Veri hazirlama
# ----------------------------------------------------------------------


def load_games(shard_dir: str) -> list:
    """Shard dizininden kullanilabilir oyunlari okur (deterministik sira)."""
    buf = ReplayBuffer(max_games=1_000_000)
    buf.add_shard_dir(shard_dir)
    return [g for g in buf.games if is_usable_game(g)]


def _decision_rows(game) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bir oyunun ogrenci kararlari: (vektorler, perspektifler, karar indeksleri)."""
    vecs: list[np.ndarray] = []
    persp: list[int] = []
    idx: list[int] = []
    for t, d in enumerate(game.decisions):
        if not (d.flags & DEC_IS_LEARNER):
            continue
        if d.flags & DEC_CHOSEN_IS_TERMINAL:
            continue
        if d.chosen_vector is None:
            continue
        vecs.append(np.asarray(d.chosen_vector, dtype=np.float32))
        persp.append(int(d.mover))
        idx.append(t)
    if not vecs:
        return (
            np.zeros((0, model_mod.VECTOR_SIZE), dtype=np.float32),
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
        )
    return np.stack(vecs, axis=0), np.asarray(persp, dtype=np.int64), np.asarray(idx, dtype=np.int64)


def build_dataset(games: list) -> dict:
    """Oyun listesinden ``x``, dislayici hedefler ve equity hedefleri uretir."""
    xs: list[np.ndarray] = []
    one_hot: list[np.ndarray] = []
    eq: list[float] = []
    game_of: list[int] = []

    for k, g in enumerate(games):
        vecs, persp, _idx = _decision_rows(g)
        if vecs.shape[0] == 0:
            continue
        tgt = targets_mod.exclusive_targets(g.winner, int(g.result_type), persp)
        xs.append(vecs)
        one_hot.append(tgt)
        eq.append(equity.equity_from_exclusive(tgt))
        game_of.append(np.full((vecs.shape[0],), k, dtype=np.int64))

    if not xs:
        return {
            "x": np.zeros((0, model_mod.VECTOR_SIZE), dtype=np.float32),
            "one_hot": np.zeros((0, 6), dtype=np.float32),
            "equity": np.zeros((0,), dtype=np.float32),
            "game": np.zeros((0,), dtype=np.int64),
        }

    return {
        "x": np.concatenate(xs, axis=0).astype(np.float32, copy=False),
        "one_hot": np.concatenate(one_hot, axis=0).astype(np.float32, copy=False),
        "equity": np.concatenate(eq, axis=0).astype(np.float32, copy=False),
        "game": np.concatenate(game_of, axis=0),
    }


def split_games(games: list, n_train: int) -> tuple[list, list, list]:
    """Deterministik bolme: egitim | CAL | VAL (Faz 6 Bolum 6.4, Kural 10)."""
    n_train = min(n_train, max(0, len(games) - CAL_GAMES - VAL_GAMES))
    train = games[:n_train]
    cal = games[n_train:n_train + CAL_GAMES]
    val = games[n_train + CAL_GAMES:n_train + CAL_GAMES + VAL_GAMES]
    return train, cal, val


# ----------------------------------------------------------------------
# Egitim
# ----------------------------------------------------------------------


def _device():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _forward_equity(model, x, head: str):
    """Model ciktisindan equity uretir (``[B]``)."""
    import torch

    out = model(x)
    if head == "six":
        probs = out[0]
        weights = torch.tensor(equity.EQUITY_WEIGHTS, dtype=probs.dtype, device=probs.device)
        return probs @ weights, probs
    return out[0].reshape(-1), None


def train_and_evaluate(cfg: DiagnosisConfig, games: list) -> DiagnosisResult:
    """Tek bir teshis kosusu: egit, VAL uzerinde kalibrasyonu olc."""
    import torch

    started = time.time()
    result = DiagnosisResult(label=cfg.label, games=cfg.games, lam=cfg.lam, head=cfg.head)

    train_games, cal_games, val_games = split_games(games, cfg.games)
    if not train_games or not val_games:
        result.seconds = time.time() - started
        return result

    train = build_dataset(train_games)
    val = build_dataset(val_games)
    if train["x"].shape[0] == 0 or val["x"].shape[0] == 0:
        result.seconds = time.time() - started
        return result

    result.train_samples = int(train["x"].shape[0])
    result.val_samples = int(val["x"].shape[0])

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    if cfg.head == "six":
        net = model_mod.build_model(output_version=2, profile="small")
    else:
        net = model_mod.build_model(output_version=1, h1=128, h2=64)

    device = _device()
    net.to(device)
    net.train()

    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)

    x_all = torch.from_numpy(train["x"]).to(device)
    oh_all = torch.from_numpy(train["one_hot"]).to(device)
    eq_all = torch.from_numpy(train["equity"]).to(device)

    n = x_all.shape[0]
    rng = np.random.default_rng(cfg.seed)
    batch = min(cfg.batch, n)

    for _step in range(cfg.steps):
        idx = rng.choice(n, size=batch, replace=False)
        xb = x_all[idx]
        ohb = oh_all[idx]
        eqb = eq_all[idx]

        pred_eq, probs = _forward_equity(net, xb, cfg.head)
        if cfg.head == "six":
            value_loss = losses.value_loss_ce_6class(probs, ohb)
            cal_loss = losses.calibration_loss(pred_eq, eqb)
            loss = losses.total_loss_v2(value_loss, torch.zeros((), device=device),
                                        cal_loss, c_cal=cfg.c_cal)
        else:
            value_loss = losses.value_loss_mse(pred_eq, eqb)
            cal_loss = losses.calibration_loss(pred_eq, eqb)
            loss = losses.total_loss_v2(value_loss, torch.zeros((), device=device),
                                        cal_loss, c_cal=cfg.c_cal)

        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    net.eval()
    with torch.no_grad():
        xv = torch.from_numpy(val["x"]).to(device)
        ohv = torch.from_numpy(val["one_hot"]).to(device)
        eqv = torch.from_numpy(val["equity"]).to(device)
        pred_eq, probs = _forward_equity(net, xv, cfg.head)
        if cfg.head == "six":
            result.value_loss = float(losses.value_loss_ce_6class(probs, ohv).item())
        else:
            result.value_loss = float(losses.value_loss_mse(pred_eq, eqv).item())
        result.cal_loss = float(losses.calibration_loss(pred_eq, eqv).item())
        pred_np = pred_eq.detach().to("cpu").numpy().astype(np.float64)

    result.metrics = calibration.calibration_metrics(pred_np, val["equity"].astype(np.float64))
    result.calibrated = calibration.is_calibrated(result.metrics)
    result.seconds = time.time() - started
    return result


# ----------------------------------------------------------------------
# D1 / D2 / D3
# ----------------------------------------------------------------------


def _train_scalar(
    x: np.ndarray,
    y: np.ndarray,
    *,
    steps: int,
    batch: int,
    lr: float,
    seed: int,
    c_cal: float = 0.0,
):
    """Skaler deger kafasini egitir; ``(net, device)`` dondurur."""
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed)

    net = model_mod.build_model(output_version=1, h1=128, h2=64)
    device = _device()
    net.to(device)
    net.train()

    opt = torch.optim.Adam(net.parameters(), lr=lr)
    x_all = torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)).to(device)
    y_all = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32)).to(device)

    n = int(x_all.shape[0])
    if n == 0:
        net.eval()
        return net, device

    rng = np.random.default_rng(seed)
    size = min(batch, n)

    for _step in range(steps):
        idx = rng.choice(n, size=size, replace=False)
        out = net(x_all[idx])
        pred = (out[0] if isinstance(out, tuple) else out).reshape(-1)
        value_loss = losses.value_loss_mse(pred, y_all[idx])
        if c_cal > 0.0:
            cal_loss = losses.calibration_loss(pred, y_all[idx])
            loss = losses.total_loss_v2(
                value_loss, torch.zeros((), device=device), cal_loss, c_cal=c_cal
            )
        else:
            loss = value_loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    net.eval()
    return net, device


def _evaluate_scalar(net, device, val: dict) -> tuple[dict, float]:
    """VAL kumesinde kalibrasyon metrikleri ve MSE."""
    import torch

    with torch.no_grad():
        xv = torch.from_numpy(val["x"]).to(device)
        yv = torch.from_numpy(val["equity"]).to(device)
        out = net(xv)
        pred = (out[0] if isinstance(out, tuple) else out).reshape(-1)
        mse = float(losses.value_loss_mse(pred, yv).item())
        pred_np = pred.detach().to("cpu").numpy().astype(np.float64)
    metrics = calibration.calibration_metrics(pred_np, val["equity"].astype(np.float64))
    return metrics, mse


def run_d1(games: list, steps: int = DEFAULT_STEPS) -> list[DiagnosisResult]:
    """D1: artan oyun sayisiyla ogrenme egrisi."""
    available = max(0, len(games) - CAL_GAMES - VAL_GAMES)
    scales = [s for s in D1_SCALES if s <= available]
    if not scales:
        scales = [available] if available > 0 else []
    out: list[DiagnosisResult] = []
    for scale in scales:
        cfg = DiagnosisConfig(label=f"D1-{scale}", games=scale, lam=1.0, head="six", steps=steps)
        out.append(train_and_evaluate(cfg, games))
    return out


def run_d2(games: list, steps: int = DEFAULT_STEPS) -> list[DiagnosisResult]:
    """D2: hedef tanimi (``lambda = 1.0`` MC vs ``lambda = 0.7`` TD).

    Kiyas adil olsun diye **skaler** kafa kullanilir: TD-lambda skaler bir
    hedef uretir, 6 sinifli dislayici hedefle dogrudan kiyaslanamaz. Once
    ``lambda = 1.0`` ile bir bootstrap agi egitilir; ``lambda < 1`` icin
    TD-lambda hedefleri bu agin tahminleriyle kurulur (Faz 4 ``replay``).
    """
    available = max(0, len(games) - CAL_GAMES - VAL_GAMES)
    train_games, _cal_games, val_games = split_games(games, available)
    out: list[DiagnosisResult] = []
    if not train_games or not val_games:
        return out

    val = build_dataset(val_games)
    mc = build_dataset(train_games)
    if val["x"].shape[0] == 0 or mc["x"].shape[0] == 0:
        return out

    bootstrap, device = _train_scalar(
        mc["x"], mc["equity"], steps=steps, batch=DEFAULT_BATCH,
        lr=DEFAULT_LR, seed=DEFAULT_SEED,
    )

    for lam in D2_LAMBDAS:
        started = time.time()
        result = DiagnosisResult(
            label=f"D2-lam{lam:g}", games=available, lam=lam, head="scalar"
        )
        result.val_samples = int(val["x"].shape[0])

        samples = replay_mod.build_value_samples(
            bootstrap, train_games, lam=lam, device=device
        )
        result.train_samples = len(samples)
        if len(samples) == 0:
            result.seconds = time.time() - started
            out.append(result)
            continue

        net, _dev = _train_scalar(
            samples.x, samples.y, steps=steps, batch=DEFAULT_BATCH,
            lr=DEFAULT_LR, seed=DEFAULT_SEED,
        )
        metrics, mse = _evaluate_scalar(net, device, val)
        result.metrics = metrics
        result.value_loss = mse
        result.cal_loss = mse
        result.calibrated = calibration.is_calibrated(metrics)
        result.seconds = time.time() - started
        out.append(result)
    return out


def run_d3(games: list, steps: int = DEFAULT_STEPS) -> list[DiagnosisResult]:
    """D3: kafa yapisi (skaler vs 6 cikti)."""
    available = max(0, len(games) - CAL_GAMES - VAL_GAMES)
    out: list[DiagnosisResult] = []
    for head in D3_HEADS:
        cfg = DiagnosisConfig(label=f"D3-{head}", games=available, lam=1.0,
                              head=head, steps=steps)
        out.append(train_and_evaluate(cfg, games))
    return out


def d1_is_flagged(results: list[DiagnosisResult]) -> bool:
    """D1 isaretli mi: ogrenme egrisi son iki noktada hala iniyor mu?"""
    usable = [r for r in results if np.isfinite(r.metrics.get("mae", float("nan")))]
    if len(usable) < 2:
        return False
    prev, last = usable[-2], usable[-1]
    if prev.metrics["mae"] <= 0.0:
        return False
    improvement = (prev.metrics["mae"] - last.metrics["mae"]) / prev.metrics["mae"]
    return improvement > D1_PLATEAU_RATIO


def d2_is_flagged(results: list[DiagnosisResult]) -> bool:
    """D2 isaretli mi: ``lambda = 1.0`` kalibrasyonu belirgin sekilde iyilestiriyor mu?"""
    by_lam = {r.lam: r for r in results if np.isfinite(r.metrics.get("mae", float("nan")))}
    if 1.0 not in by_lam or 0.7 not in by_lam:
        return False
    return by_lam[1.0].metrics["mae"] < by_lam[0.7].metrics["mae"]


def d3_is_flagged(results: list[DiagnosisResult]) -> bool:
    """D3 isaretli mi: 6 cikti li kafa skaler kafadan belirgin sekilde iyi mi?"""
    by_head = {r.head: r for r in results if np.isfinite(r.metrics.get("mae", float("nan")))}
    if "six" not in by_head or "scalar" not in by_head:
        return False
    return by_head["six"].metrics["mae"] < by_head["scalar"].metrics["mae"]


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float, digits: int = 4) -> str:
    if value is None or not np.isfinite(value):
        return "-"
    return f"{value:.{digits}f}"


def build_markdown(
    d1: list[DiagnosisResult],
    d2: list[DiagnosisResult],
    d3: list[DiagnosisResult],
    *,
    game_count: int,
    steps: int,
) -> str:
    """``stage_f_diagnosis.md`` icerigi."""
    lines: list[str] = []
    lines.append("# Faz 6 — Aşama B: D1–D3 kalibrasyon teşhisi")
    lines.append("")
    lines.append("Bu rapor `ml/diagnose.py` tarafından üretilir; elle düzenlenmez.")
    lines.append("")
    lines.append("## Girdi")
    lines.append("")
    lines.append(f"- Kullanılabilir oyun sayısı: **{game_count}**")
    lines.append(f"- Eğitim bütçesi: **{steps}** adım (tüm koşularda sabit)")
    lines.append(f"- CAL / VAL oyun sayısı: **{CAL_GAMES}** / **{VAL_GAMES}**")
    lines.append(f"- Tohum: **{DEFAULT_SEED}**")
    lines.append("")
    lines.append("## Faz 5 taban çizgisi (karşılaştırma)")
    lines.append("")
    lines.append("| Metrik | Faz 5 | Kabul |")
    lines.append("|---|---|---|")
    lines.append(f"| Eğim | {calibration.BASELINE_SLOPE:.4f} | "
                 f"{calibration.SLOPE_MIN:.2f} – {calibration.SLOPE_MAX:.2f} |")
    lines.append(f"| Korelasyon | {calibration.BASELINE_CORRELATION:.4f} | "
                 f"≥ {calibration.CORRELATION_MIN:.2f} |")
    lines.append(f"| MAE | {calibration.BASELINE_MAE:.4f} | "
                 f"≤ {calibration.MAE_MAX:.2f} |")
    lines.append(f"| Std oranı | {calibration.BASELINE_STD_RATIO:.2f} | "
                 f"{calibration.STD_RATIO_MIN:.1f} – {calibration.STD_RATIO_MAX:.1f} |")
    lines.append("")

    def table(title: str, results: list[DiagnosisResult], note: str) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(note)
        lines.append("")
        lines.append("| Koşu | Oyun | λ | Kafa | Örnek | Değer kaybı | L_cal | Eğim | Korelasyon | MAE | Std oranı | Kalibre |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in results:
            m = r.metrics
            lines.append(
                f"| `{r.label}` | {r.games} | {r.lam:g} | {r.head} | {r.train_samples} | "
                f"{_fmt(r.value_loss)} | {_fmt(r.cal_loss)} | {_fmt(m.get('slope', float('nan')))} | "
                f"{_fmt(m.get('correlation', float('nan')))} | {_fmt(m.get('mae', float('nan')))} | "
                f"{_fmt(m.get('std_ratio', float('nan')), 2)} | "
                f"{'✅' if r.calibrated else '❌'} |"
            )
        lines.append("")

    table("D1 — Eğitim ölçeği", d1,
          "Aynı mimari ve hedefle artan oyun sayısı. Eğri hâlâ iniyorsa sorun ölçektir.")
    table("D2 — Hedef tanımı", d2,
          "`λ = 1.0` (saf Monte Carlo) vs `λ = 0.7` (TD). TD hedefi başlangıçta yanlıdır. "
          "Kıyas adil olsun diye **skaler** kafa kullanılır: TD-λ skaler bir hedef üretir. "
          "`λ < 1` hedefleri, `λ = 1.0` ile eğitilmiş bir bootstrap ağının tahminleriyle kurulur.")
    table("D3 — Kafa yapısı", d3,
          "Tek skaler değer kafası vs 6 çıktılı dışlayıcı olasılık kafası.")

    f1 = d1_is_flagged(d1)
    f2 = d2_is_flagged(d2)
    f3 = d3_is_flagged(d3)

    lines.append("## Karar")
    lines.append("")
    lines.append("| Teşhis | İşaretli | Eylem |")
    lines.append("|---|---|---|")
    lines.append(f"| D1 — eğitim ölçeği | {'✅ evet' if f1 else '❌ hayır'} | "
                 f"{'Veri ölçeğini büyüt (Aşama C)' if f1 else 'Ölçek birincil neden değil'} |")
    lines.append(f"| D2 — hedef tanımı | {'✅ evet' if f2 else '❌ hayır'} | "
                 f"{'`λ = 1.0` kullan' if f2 else '`λ` birincil neden değil'} |")
    lines.append(f"| D3 — kafa yapısı | {'✅ evet' if f3 else '❌ hayır'} | "
                 f"{'6 çıktılı kafa + `L_cal`' if f3 else 'Kafa yapısı birincil neden değil'} |")
    lines.append("")
    lines.append("Uygulanan sıra (Faz 6 §6.2): 6 çıktılı kafa → `L_cal` → logit sıcaklık → isotonic.")
    lines.append("")
    lines.append("## Sınırlar")
    lines.append("")
    lines.append(f"- Mevcut veri **{game_count}** oyun; D1'in 5 000 / 10 000 noktaları bu veriyle")
    lines.append("  ölçülemez. Ölçülebilen en büyük nokta raporlanmıştır; daha büyük ölçek")
    lines.append("  Aşama C'de yeni self-play verisiyle ölçülmelidir.")
    lines.append("- Eğitim bütçesi sabit ve küçüktür: amaç **kıyas**, mutlak başarı değildir.")
    lines.append("- ER ölçümü bu raporun kapsamı dışındadır; `ml/er_harness.py` ile ayrıca yapılır.")
    lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Faz 6 D1-D3 kalibrasyon teshisi")
    ap.add_argument("--shards", default=os.path.join(HERE, "runs", "stage_d", "shards"))
    ap.add_argument("--out", default=os.path.join(HERE, "artifacts", "stage_f_diagnosis.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "artifacts", "stage_f_diagnosis.json"))
    ap.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    ap.add_argument("--only", default="all", choices=["all", "d1", "d2", "d3"])
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    games = load_games(args.shards)
    if not games:
        print(f"oyun bulunamadi: {args.shards}", file=sys.stderr)
        return 2

    print(f"yuklenen oyun: {len(games)}")

    d1: list[DiagnosisResult] = []
    d2: list[DiagnosisResult] = []
    d3: list[DiagnosisResult] = []

    if args.only in ("all", "d1"):
        d1 = run_d1(games, args.steps)
        for r in d1:
            print(f"  {r.label}: mae={_fmt(r.metrics.get('mae', float('nan')))} "
                  f"slope={_fmt(r.metrics.get('slope', float('nan')))} ({r.seconds:.1f}s)")

    if args.only in ("all", "d2"):
        d2 = run_d2(games, args.steps)
        for r in d2:
            print(f"  {r.label}: mae={_fmt(r.metrics.get('mae', float('nan')))} "
                  f"slope={_fmt(r.metrics.get('slope', float('nan')))} ({r.seconds:.1f}s)")

    if args.only in ("all", "d3"):
        d3 = run_d3(games, args.steps)
        for r in d3:
            print(f"  {r.label}: mae={_fmt(r.metrics.get('mae', float('nan')))} "
                  f"slope={_fmt(r.metrics.get('slope', float('nan')))} ({r.seconds:.1f}s)")

    markdown = build_markdown(d1, d2, d3, game_count=len(games), steps=args.steps)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown)
    print(f"yazildi: {args.out}")

    payload = {
        "gameCount": len(games),
        "steps": args.steps,
        "calGames": CAL_GAMES,
        "valGames": VAL_GAMES,
        "seed": DEFAULT_SEED,
        "d1": [r.to_dict() for r in d1],
        "d2": [r.to_dict() for r in d2],
        "d3": [r.to_dict() for r in d3],
        "flags": {
            "d1": d1_is_flagged(d1),
            "d2": d2_is_flagged(d2),
            "d3": d3_is_flagged(d3),
        },
    }
    with open(args.json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2)
    print(f"yazildi: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())