"""Faz 7: "sorun olcek mi, pipeline mi?" teshisi.

Bir dis inceleme, modelin basit bir sezgisel bottan (PipBot) kotu oldugunu ve
bunun **olcek degil pipeline** sorunu oldugunu one surdu. Bu modul o soruyu
**olculebilir** hale getirir: her iddia icin ayri bir kapi tanimlar ve mevcut
artifact'lardan karar uretir.

Neden ayri bir modul? Cunku "model kotu" tek bir sayi degildir. Bir model
PipBot'u %99,5 yenip yine de **bozuk bir deger kafasina** sahip olabilir
(kalibrasyon egimi 0,67). Bu ikisi ayni anda dogruysa, olcek buyutmek ise
yaramaz: daha buyuk model daha emin bir sekilde yanlis olur.

Kapilar (hepsi bagimsiz, hepsi gerekli):

===========  ===========================================================
Kimlik       Olcut
===========  ===========================================================
``G1``       PipBot'a karsi kazanma orani >= 0,90 (gerekli, **yeterli degil**)
``G2``       Kalibrasyon egimi [0,85; 1,15]
``G3``       Kalibrasyon MAE < 0,15
``G4``       Korelasyon > 0,90
``G5``       Std orani [0,85; 1,15]
``G6``       2-ply ER < 0,02 (sampiyon hedefi)
``G7``       Hedef sacilimi cokmemis: ``std(hedef) / std(terminal) > 0,5``
===========  ===========================================================

``G1`` gecerken ``G2``/``G3``/``G5`` dusuyorsa teshis **"pipeline"**dir.
``G1`` de dusuyorsa teshis **"temel"**dir (model hic oynamiyor).
Hepsi gecerse teshis **"saglikli"**dir ve olcek buyutmek anlamlidir.

Kullanim::

    python ml/pipeline_health.py --calibration ml/artifacts/stage_h_calibration_2ply.json \
        --eval ml/artifacts/stage_h_eval_pip.json \
        --er ml/artifacts/stage_h_er_2ply.json \
        --json ml/artifacts/pipeline_health.json \
        --markdown ml/artifacts/pipeline_health.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ----------------------------------------------------------------------
# Esikler
# ----------------------------------------------------------------------

#: G1: PipBot'a karsi kazanma orani. Gerekli ama yeterli degil.
PIP_WIN_RATE_MIN = 0.90
#: G2: kalibrasyon egimi alt/ust siniri.
SLOPE_MIN = 0.85
SLOPE_MAX = 1.15
#: G3: kalibrasyon MAE tavani.
MAE_MAX = 0.15
#: G4: korelasyon alt siniri.
CORRELATION_MIN = 0.90
#: G5: std orani alt/ust siniri.
STD_RATIO_MIN = 0.85
STD_RATIO_MAX = 1.15
#: G6: sampiyon ER hedefi (2-ply gnubg).
ER_MAX = 0.02
#: G7: hedef saciliminin terminal sacilimina orani.
TARGET_STD_RATIO_MIN = 0.5

GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")

GATE_LABELS = {
    "G1": "PipBot kazanma orani >= 0,90",
    "G2": "Kalibrasyon egimi [0,85; 1,15]",
    "G3": "Kalibrasyon MAE < 0,15",
    "G4": "Korelasyon > 0,90",
    "G5": "Std orani [0,85; 1,15]",
    "G6": "2-ply ER < 0,02",
    "G7": "Hedef sacilimi cokmemis (> 0,5)",
}

#: Teshis etiketleri.
VERDICT_HEALTHY = "saglikli"
VERDICT_PIPELINE = "pipeline"
VERDICT_FOUNDATION = "temel"
VERDICT_UNKNOWN = "bilinmiyor"


# ----------------------------------------------------------------------
# Kapi degerlendirmesi
# ----------------------------------------------------------------------


@dataclass
class Gate:
    """Tek bir kapinin sonucu."""

    gate_id: str
    value: float | None
    passed: bool | None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate_id,
            "label": GATE_LABELS.get(self.gate_id, self.gate_id),
            "value": self.value,
            "passed": self.passed,
            "note": self.note,
        }


def _gate(gate_id: str, value: float | None, passed: bool | None, note: str = "") -> Gate:
    return Gate(gate_id=gate_id, value=value, passed=passed, note=note)


def gate_pip_win_rate(win_rate: float | None) -> Gate:
    """G1: PipBot'a karsi kazanma orani."""
    if win_rate is None:
        return _gate("G1", None, None, "olculmedi")
    return _gate("G1", float(win_rate), float(win_rate) >= PIP_WIN_RATE_MIN)


def gate_slope(slope: float | None) -> Gate:
    """G2: kalibrasyon egimi."""
    if slope is None:
        return _gate("G2", None, None, "olculmedi")
    ok = SLOPE_MIN <= float(slope) <= SLOPE_MAX
    return _gate("G2", float(slope), ok)


def gate_mae(mae: float | None) -> Gate:
    """G3: kalibrasyon MAE."""
    if mae is None:
        return _gate("G3", None, None, "olculmedi")
    return _gate("G3", float(mae), float(mae) < MAE_MAX)


def gate_correlation(correlation: float | None) -> Gate:
    """G4: korelasyon."""
    if correlation is None:
        return _gate("G4", None, None, "olculmedi")
    return _gate("G4", float(correlation), float(correlation) > CORRELATION_MIN)


def gate_std_ratio(std_ratio: float | None) -> Gate:
    """G5: std orani."""
    if std_ratio is None:
        return _gate("G5", None, None, "olculmedi")
    return _gate("G5", float(std_ratio), STD_RATIO_MIN <= float(std_ratio) <= STD_RATIO_MAX)


def gate_er(er: float | None) -> Gate:
    """G6: 2-ply ER."""
    if er is None:
        return _gate("G6", None, None, "olculmedi")
    return _gate("G6", float(er), float(er) < ER_MAX)


def gate_target_std_ratio(ratio: float | None) -> Gate:
    """G7: hedef sacilimi cokmemis mi."""
    if ratio is None:
        return _gate("G7", None, None, "olculmedi")
    return _gate("G7", float(ratio), float(ratio) > TARGET_STD_RATIO_MIN)


# ----------------------------------------------------------------------
# Hedef sacilimi (G7) - shard'lardan
# ----------------------------------------------------------------------


@dataclass
class TargetSpread:
    """TD hedeflerinin sacilimi vs terminal degerlerin sacilimi."""

    count: int
    target_std: float
    terminal_std: float
    target_mean: float
    terminal_mean: float
    zero_share: float

    @property
    def ratio(self) -> float:
        if self.terminal_std <= 0.0:
            return float("nan")
        return self.target_std / self.terminal_std

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "targetStd": self.target_std,
            "terminalStd": self.terminal_std,
            "targetMean": self.target_mean,
            "terminalMean": self.terminal_mean,
            "zeroShare": self.zero_share,
            "ratio": self.ratio,
        }


def target_spread(targets: Iterable[float], terminals: Iterable[float]) -> TargetSpread:
    """Hedef ve terminal dizilerinden sacilim ozeti.

    ``targets``: TD(lam) hedefleri (equity, mover perspektifi).
    ``terminals``: ayni kararlarin terminal degerleri (mover perspektifi).

    Hedefler terminal degerlerin **kopyasi** ise ``ratio ~ 1``; hedefler sifira
    coktuyse ``ratio ~ 0``. Bootstrap kullanildiginda ``ratio`` 1'den kucuk
    olabilir (hedef yumusatilmis), ama 0,5'in altina inmesi cokme isaretidir.
    """
    t = np.asarray(list(targets), dtype=np.float64).reshape(-1)
    z = np.asarray(list(terminals), dtype=np.float64).reshape(-1)
    if t.shape[0] != z.shape[0]:
        raise ValueError("targets ve terminals ayni uzunlukta olmali")
    if t.shape[0] == 0:
        return TargetSpread(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return TargetSpread(
        count=int(t.shape[0]),
        target_std=float(np.std(t)),
        terminal_std=float(np.std(z)),
        target_mean=float(np.mean(t)),
        terminal_mean=float(np.mean(z)),
        zero_share=float(np.mean(np.abs(t) < 1e-9)),
    )


class _ZeroValueModel:
    """``V_hat = 0`` yerine gecen sahte model (G7 icin ``lam = 1`` onkosulu).

    ``replay.build_value_samples`` bir model nesnesi bekler; model verilmeden
    ``lam = 1`` kullanildiginda hedefler tam olarak ``+-z`` olur ve G7 orani
    yapisal olarak 1 cikar. Bu sinif o durumu acikca temsil eder.
    """

    def eval(self) -> "_ZeroValueModel":  # noqa: D102
        return self

    def to(self, _device: str) -> "_ZeroValueModel":  # noqa: D102
        return self

    def __call__(self, x):  # noqa: D102
        import torch  # noqa: PLC0415

        return torch.zeros((x.shape[0],), dtype=torch.float32, device=x.device)


def _zero_value_model() -> _ZeroValueModel:
    return _ZeroValueModel()


def _load_value_model(model_path: Path, device: str):
    """Checkpoint -> deger tahmini yapan model (``build_model`` imzasi F7-20)."""
    import torch  # noqa: PLC0415
    from model import CAPACITY_PROFILES, DEFAULT_PROFILE, VECTOR_SIZE, build_model  # noqa: PLC0415

    ckpt = torch.load(str(model_path), map_location=device, weights_only=False)
    profile = ckpt.get("profile") or DEFAULT_PROFILE
    if profile not in CAPACITY_PROFILES:
        raise ValueError(
            "bilinmeyen kapasite profili: " + repr(profile)
            + " (gecerli: " + str(sorted(CAPACITY_PROFILES)) + ")"
        )
    h1, h2 = CAPACITY_PROFILES[profile][:2]
    model = build_model(
        VECTOR_SIZE, h1, h2, seed=0, output_version=2, profile=profile
    )
    model.load_state_dict(ckpt["model"])
    model.to(device)
    model.eval()
    return _EquityValueModel(model)


class _EquityValueModel:
    """``BackgammonNetV2`` (6 sinif olasilik) -> skaler equity sarmalayici.

    ``replay._predict_values`` modelin **skaler** dondurmesini bekler; V2 ise
    ``(probs, policy_logit)`` dondurur. Sarmalayici olasiligi
    ``EQUITY_WEIGHTS`` ile skalerlestirir (F7-17 ile ayni kural).
    """

    def __init__(self, net) -> None:  # noqa: D107
        self.net = net

    def eval(self) -> "_EquityValueModel":  # noqa: D102
        self.net.eval()
        return self

    def to(self, device: str) -> "_EquityValueModel":  # noqa: D102
        self.net.to(device)
        return self

    def __call__(self, x):  # noqa: D102
        import torch  # noqa: PLC0415
        from equity import EQUITY_WEIGHTS  # noqa: PLC0415

        out = self.net(x)
        probs = out[0] if isinstance(out, tuple) else out
        w = torch.as_tensor(EQUITY_WEIGHTS, dtype=probs.dtype, device=probs.device)
        return probs @ w


def spread_from_shards(
    shard_paths: Sequence[Path],
    *,
    model_path: Path | None = None,
    lam: float = 1.0,
    device: str = "cpu",
) -> TargetSpread:
    """Shard'lardan hedef sacilimi (G7).

    ``model_path`` verilirse ``V_hat`` o modelle hesaplanir (gercek TD(lam)
    hedefleri). Verilmezse ``V_hat = 0`` varsayilir; bu durumda ``lam = 1``
    ile hedefler tam olarak ``+-z`` olur ve ``ratio == 1`` cikar - yani
    **bilgi tasimaz**. Gercek teshis icin model verilmelidir.
    """
    import replay  # noqa: PLC0415
    import shards as shard_mod  # noqa: PLC0415

    games: list[Any] = []
    for path in shard_paths:
        _header, loaded = shard_mod.read_shard(Path(path))
        games.extend(loaded)
    if not games:
        return TargetSpread(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = _zero_value_model() if model_path is None else _load_value_model(
        Path(model_path), device
    )

    samples = replay.build_value_samples(model, games, lam=lam, device=device)
    targets = np.asarray(samples.y, dtype=np.float64)

    # Ayni orneklerin terminal degerleri: her ornek kendi oyununun z'si.
    terminals = np.empty_like(targets)
    usable = [g for g in games if replay.is_usable_game(g)]
    for k, g in enumerate(usable):
        z = replay.terminal_value(g.result_points, g.cube_value, g.winner)
        sel = samples.game_index == k
        terminals[sel] = z
    return target_spread(targets, terminals)


# ----------------------------------------------------------------------
# Artifact okuma
# ----------------------------------------------------------------------


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def calibration_from_artifact(data: dict[str, Any] | None) -> dict[str, float | None]:
    """Kalibrasyon artifact'indan ``slope``/``mae``/``correlation``/``std_ratio``.

    Iki bicim desteklenir: duz ozet (``stage_h_calibration_2ply.json``) ve
    ``before``/``after`` iceren post-hoc bicim (``stage_d_calibration.json``).
    Post-hoc bicimde **``after``** tercih edilir: onarim uygulanmis hali.
    """
    out: dict[str, float | None] = {
        "slope": None,
        "mae": None,
        "correlation": None,
        "std_ratio": None,
    }
    if not data:
        return out
    src = data.get("after") if isinstance(data.get("after"), dict) else data
    for key in out:
        value = src.get(key)
        if value is not None:
            out[key] = float(value)
    return out


def pip_win_rate_from_artifact(data: dict[str, Any] | None) -> float | None:
    """``--eval-json`` ciktisindan PipBot kazanma orani."""
    if not data:
        return None
    for report in data.get("reports", []):
        name = str(report.get("opponent", "")).lower()
        if "pip" in name:
            value = report.get("winRate")
            if value is not None:
                return float(value)
    return None


def er_from_artifact(data: dict[str, Any] | None) -> float | None:
    """ER olcum artifact'indan ortalama ER."""
    if not data:
        return None
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else data
    value = summary.get("mean")
    return None if value is None else float(value)


# ----------------------------------------------------------------------
# Teshis
# ----------------------------------------------------------------------


@dataclass
class HealthReport:
    """Tum kapilarin ve teshisin ozeti."""

    gates: list[Gate] = field(default_factory=list)
    spread: TargetSpread | None = None
    sources: dict[str, str] = field(default_factory=dict)

    def by_id(self, gate_id: str) -> Gate | None:
        for g in self.gates:
            if g.gate_id == gate_id:
                return g
        return None

    @property
    def failed(self) -> list[str]:
        return [g.gate_id for g in self.gates if g.passed is False]

    @property
    def passed(self) -> list[str]:
        return [g.gate_id for g in self.gates if g.passed is True]

    @property
    def measured(self) -> list[str]:
        return [g.gate_id for g in self.gates if g.passed is not None]

    @property
    def verdict(self) -> str:
        """Teshis: ``saglikli`` / ``pipeline`` / ``temel`` / ``bilinmiyor``.

        ``saglikli`` demek icin **G1-G5 ve G7'nin hepsi olculmus ve gecmis**
        olmalidir. Olculmemis bir kapi varken "saglikli" demek sahte bir
        guvencedir; o durumda teshis ``bilinmiyor``dur. ``G6`` (ER) bu kuralin
        disindadir: ER bir **guc** olcumudur, pipeline sagliginin onkosulu
        degildir (bkz. :attr:`strength_gap`).
        """
        g1 = self.by_id("G1")
        if g1 is None or g1.passed is None:
            return VERDICT_UNKNOWN
        if g1.passed is False:
            return VERDICT_FOUNDATION
        # G1 gecti: kalibrasyon/deger kapilarindan biri dusuyorsa pipeline.
        value_gates = ("G2", "G3", "G4", "G5", "G7")
        any_failed = any(
            (g := self.by_id(gid)) is not None and g.passed is False for gid in value_gates
        )
        if any_failed:
            return VERDICT_PIPELINE
        # Hicbiri dusmedi; ama hepsi olculdu mu?
        all_measured = all(
            (g := self.by_id(gid)) is not None and g.passed is True for gid in value_gates
        )
        if not all_measured:
            return VERDICT_UNKNOWN
        # G1 ve deger kapilari gecti, yalnizca G6 (ER) dustu: bu bir **guc**
        # eksigi, pipeline arizasi degil.
        return VERDICT_HEALTHY

    @property
    def strength_gap(self) -> bool:
        """G1..G5,G7 gecti ama G6 dustu: pipeline saglikli, guc yetersiz."""
        g6 = self.by_id("G6")
        if g6 is None or g6.passed is not False:
            return False
        return self.verdict == VERDICT_HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "strengthGap": self.strength_gap,
            "gates": [g.to_dict() for g in self.gates],
            "failed": self.failed,
            "passed": self.passed,
            "measured": self.measured,
            "spread": self.spread.to_dict() if self.spread else None,
            "sources": self.sources,
            "thresholds": {
                "pipWinRateMin": PIP_WIN_RATE_MIN,
                "slopeMin": SLOPE_MIN,
                "slopeMax": SLOPE_MAX,
                "maeMax": MAE_MAX,
                "correlationMin": CORRELATION_MIN,
                "stdRatioMin": STD_RATIO_MIN,
                "stdRatioMax": STD_RATIO_MAX,
                "erMax": ER_MAX,
                "targetStdRatioMin": TARGET_STD_RATIO_MIN,
            },
        }


def diagnose(
    *,
    calibration: dict[str, Any] | None = None,
    eval_report: dict[str, Any] | None = None,
    er_report: dict[str, Any] | None = None,
    spread: TargetSpread | None = None,
    sources: dict[str, str] | None = None,
) -> HealthReport:
    """Artifact'lardan kapi listesi ve teshis uretir."""
    cal = calibration_from_artifact(calibration)
    gates = [
        gate_pip_win_rate(pip_win_rate_from_artifact(eval_report)),
        gate_slope(cal["slope"]),
        gate_mae(cal["mae"]),
        gate_correlation(cal["correlation"]),
        gate_std_ratio(cal["std_ratio"]),
        gate_er(er_from_artifact(er_report)),
        gate_target_std_ratio(spread.ratio if spread is not None else None),
    ]
    return HealthReport(gates=gates, spread=spread, sources=dict(sources or {}))


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and not math.isfinite(value):
        return "-"
    return ("%." + str(digits) + "f") % value


def _mark(passed: bool | None) -> str:
    if passed is None:
        return "olculmedi"
    return "GECTI" if passed else "DUSTU"


VERDICT_TEXT = {
    VERDICT_HEALTHY: (
        "Pipeline saglikli. Guc eksigi varsa **olcek** (daha cok veri, daha buyuk "
        "ag) anlamli bir kaldiractir."
    ),
    VERDICT_PIPELINE: (
        "Teshis **pipeline**. Model PipBot'u yeniyor ama deger kafasi bozuk "
        "(kalibrasyon/MAE/std orani). Bu durumda olcek buyutmek ise yaramaz: "
        "daha buyuk model daha emin bir sekilde yanlis olur. Once hedef/kayip/"
        "kalibrasyon hattini onarin."
    ),
    VERDICT_FOUNDATION: (
        "Teshis **temel**. Model basit bir sezgisel bottan bile zayif. Once "
        "oyun oynayabildigini (yasal hamle, terminal deger, isaret) dogrulayin; "
        "olcek ve kalibrasyon bu asamada anlamsizdir."
    ),
    VERDICT_UNKNOWN: (
        "Teshis **bilinmiyor**: G1 (PipBot kazanma orani) ya da deger "
        "kapilarindan (G2-G5, G7) en az biri olculmedi. Olculmemis kapi varken "
        "\"saglikli\" demek sahte bir guvencedir; once eksik olcumu tamamlayin."
    ),
}


def build_markdown(report: HealthReport, *, title: str = "Faz 7 - Pipeline sagligi") -> str:
    """Insan-okur Markdown rapor."""
    lines: list[str] = []
    lines.append("# " + title)
    lines.append("")
    lines.append("Soru: **sorun olcek mi, pipeline mi?** Bu rapor her iddiayi ayri bir")
    lines.append("kapiya baglar. Kapilar bagimsizdir; hepsi gereklidir.")
    lines.append("")
    lines.append("## 1. Kapilar")
    lines.append("")
    lines.append("| Kapi | Olcut | Deger | Sonuc |")
    lines.append("|---|---|---|---|")
    for g in report.gates:
        lines.append(
            "| %s | %s | %s | **%s** |"
            % (g.gate_id, GATE_LABELS.get(g.gate_id, g.gate_id), _fmt(g.value), _mark(g.passed))
        )
    lines.append("")
    lines.append("## 2. Teshis")
    lines.append("")
    lines.append("**`%s`**" % report.verdict)
    lines.append("")
    lines.append(VERDICT_TEXT.get(report.verdict, ""))
    lines.append("")
    if report.strength_gap:
        lines.append(
            "> **Guc boslugu.** G1-G5 ve G7 gecti, yalnizca G6 (ER < 0,02) dustu. "
            "Bu bir **guc** eksigidir, pipeline arizasi degil: olcek/kapasite "
            "artirmak dogru kaldiractir."
        )
        lines.append("")
    if report.spread is not None:
        s = report.spread
        lines.append("## 3. Hedef sacilimi (G7)")
        lines.append("")
        lines.append("| Olcum | Deger |")
        lines.append("|---|---|")
        lines.append("| Karar | %d |" % s.count)
        lines.append("| Hedef std | %s |" % _fmt(s.target_std))
        lines.append("| Terminal std | %s |" % _fmt(s.terminal_std))
        lines.append("| Oran | %s |" % _fmt(s.ratio))
        lines.append("| Hedef ortalamasi | %s |" % _fmt(s.target_mean))
        lines.append("| Terminal ortalamasi | %s |" % _fmt(s.terminal_mean))
        lines.append("| Sifir hedef orani | %s |" % _fmt(s.zero_share))
        lines.append("")
    if report.sources:
        lines.append("## 4. Kaynaklar")
        lines.append("")
        lines.append("| Rol | Dosya |")
        lines.append("|---|---|")
        for role, path in sorted(report.sources.items()):
            lines.append("| %s | `%s` |" % (role, path))
        lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline_health",
        description="Olcek mi pipeline mi? Kapili teshis.",
    )
    p.add_argument("--calibration", type=Path, default=None, help="kalibrasyon artifact JSON")
    p.add_argument("--eval", dest="eval_path", type=Path, default=None, help="--eval-json ciktisi")
    p.add_argument("--er", dest="er_path", type=Path, default=None, help="ER olcum JSON")
    p.add_argument("--targets", type=Path, default=None, help="hedef dizisi .npy (G7)")
    p.add_argument("--terminals", type=Path, default=None, help="terminal dizisi .npy (G7)")
    p.add_argument("--shards", type=Path, nargs="+", default=None, help="shard dosyalari (G7)")
    p.add_argument("--model", type=Path, default=None, help="V_hat icin checkpoint (.pt)")
    p.add_argument("--lam", type=float, default=1.0, help="TD lambda (G7)")
    p.add_argument("--json", type=Path, default=None, help="cikti JSON")
    p.add_argument("--markdown", type=Path, default=None, help="cikti Markdown")
    p.add_argument("--quiet", action="store_true")
    return p


def _load_npy(path: Path | None) -> np.ndarray | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return np.load(p)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    spread: TargetSpread | None = None
    targets = _load_npy(args.targets)
    terminals = _load_npy(args.terminals)
    if targets is not None and terminals is not None:
        spread = target_spread(targets, terminals)
    elif args.shards:
        spread = spread_from_shards(args.shards, model_path=args.model, lam=args.lam)

    sources: dict[str, str] = {}
    for role, path in (
        ("calibration", args.calibration),
        ("eval", args.eval_path),
        ("er", args.er_path),
    ):
        if path is not None:
            sources[role] = str(path)

    report = diagnose(
        calibration=_read_json(args.calibration),
        eval_report=_read_json(args.eval_path),
        er_report=_read_json(args.er_path),
        spread=spread,
        sources=sources,
    )

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(build_markdown(report), encoding="utf-8")

    if not args.quiet:
        print("teshis: %s" % report.verdict)
        for g in report.gates:
            print("  %s %-42s %10s  %s" % (g.gate_id, GATE_LABELS.get(g.gate_id, ""), _fmt(g.value), _mark(g.passed)))
        if report.strength_gap:
            print("  -> guc boslugu: pipeline saglikli, ER hedefi tutmuyor")

    # Cikis kodu: 0 = saglikli, 1 = pipeline, 2 = temel, 3 = bilinmiyor
    return {
        VERDICT_HEALTHY: 0,
        VERDICT_PIPELINE: 1,
        VERDICT_FOUNDATION: 2,
        VERDICT_UNKNOWN: 3,
    }[report.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
