"""Faz 7-S: kapasite profillerini (medium/large/xlarge) ayni kosullarda egit ve olc.

Tek bir profil icin uctan uca akis:

1. politika veri kumesini yukle (``gnubg_distill.load_policy_dataset``),
2. ``train_policy_head`` ile egit (CE + deger + KL + opsiyonel siralama),
3. denetim noktasini yaz,
4. ONNX'e ihrac et (siralama kafasi **dusurulur**, ``output_version = 2``),
5. ``er_paths measure`` ve ``antisymmetry measure`` ile olc,
6. JSON + markdown satiri uret.

Ornek::

    python ml/capacity_train.py --data ml/runs/capacity30k/policy_30k.npz \
        --profile large --out-dir ml/runs/capacity/large \
        --steps 20000 --dist-weight 0.5 --val-fraction 0.1 --patience 5 \
        --measure --corpus ml/artifacts/reference_corpus_v2.json

Tasarim notu: bu surucu **yeni bir mimari tanimlamaz**. Gizli katman
genislikleri :data:`ml.model.CAPACITY_PROFILES` icinde tek yerde durur; burada
yalnizca profil secilir. ``ml/model_large.py`` / ``ml/model_xlarge.py`` ayni
profillerin adlandirilmis sarmalayicilaridir.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

DEFAULT_CORPUS = ML_DIR / "artifacts" / "reference_corpus_v2.json"
DEFAULT_OUT_DIR = ML_DIR / "runs" / "capacity"

#: Faz 7-S karar kurali: en iyi profil, medium'a gore **en az** bu kadar goreli
#: ER kazanci saglamali (Test 96 ile ayni esik).
CAPACITY_GAIN_THRESHOLD = 0.15


def _strip_rank_head(state: dict[str, Any]) -> dict[str, Any]:
    """Siralama kafasi agirliklarini ayiklar (ONNX sozlesmesi iki cikti)."""
    return {k: v for k, v in state.items() if not k.startswith("rank_head.")}


def train_profile(
    data: Path,
    *,
    profile: str,
    steps: int,
    lr: float,
    batch: int,
    value_weight: float,
    dist_weight: float,
    rank_weight: float,
    val_fraction: float,
    patience: int,
    eval_every: int,
    weight_decay: float,
    lr_schedule: str,
    lr_final_ratio: float,
    seed: int,
    device: str,
    quiet: bool = False,
    policy_temperature: float = 0.0,
    select_temperature: bool = False,
    symmetry: bool = False,
    symmetry_mode: str = "basis",
    checkpoint: Path | None = None,
    checkpoint_every: int = 0,
    resume: bool = False,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Bir profili egitir; ``(model, report, checkpoint_state)`` dondurur.

    ``policy_temperature > 0`` ise R-04 liste bazli kaybi kullanilir; bu kip
    veri kumesinde aday basina equity (``cand_equity``) gerektirir.
    ``select_temperature`` ise T'yi dogrulama bolmesinde secer (R-04).
    ``symmetry`` ise mimari antisimetri kullanilir (F7-116): renk takasi
    kusuru **tanim geregi** sifirdir, egitim artirimi gerekmez.
    ``symmetry_mode`` hangi antisimetrik kurulumu secistir (``basis`` veya
    ``higgins``).
    """
    import torch  # noqa: PLC0415

    import gnubg_distill  # noqa: PLC0415
    from model import CAPACITY_PROFILES, VECTOR_SIZE, build_model, parameter_count  # noqa: PLC0415

    if profile not in CAPACITY_PROFILES:
        raise ValueError("bilinmeyen profil: %r" % (profile,))
    dataset = gnubg_distill.load_policy_dataset(Path(data))
    if len(dataset) == 0:
        raise ValueError("veri kumesi bos: %s" % (data,))

    model = build_model(
        VECTOR_SIZE,
        seed=seed,
        output_version=2,
        profile=profile,
        rank_head=rank_weight > 0,
        symmetry=symmetry,
        symmetry_mode=symmetry_mode,
    )

    def progress(step: int, total: int, loss: float) -> None:
        if quiet:
            return
        if step % 500 == 0 or step == total:
            print("[%s %d/%d] loss=%.6f" % (profile, step, total, loss), file=sys.stderr)

    started = time.time()
    temperature_report = None
    if select_temperature:
        temperature_report = gnubg_distill.select_policy_temperature(
            model,
            dataset,
            val_fraction=val_fraction or 0.1,
            seed=seed,
            batch=batch,
            device=device,
        )
        policy_temperature = float(temperature_report["best"])
        if not quiet:
            print(
                "[%s] secilen T=%g" % (profile, policy_temperature), file=sys.stderr
            )
    report = gnubg_distill.train_policy_head(
        model,
        dataset,
        steps=steps,
        lr=lr,
        batch=batch,
        device=device,
        seed=seed,
        value_weight=value_weight,
        dist_weight=dist_weight,
        rank_weight=rank_weight,
        val_fraction=val_fraction,
        patience=patience,
        eval_every=eval_every,
        weight_decay=weight_decay,
        lr_schedule=lr_schedule,
        lr_final_ratio=lr_final_ratio,
        policy_temperature=policy_temperature,
        progress=progress,
        checkpoint=checkpoint,
        checkpoint_every=checkpoint_every,
        resume=resume,
    )
    elapsed = time.time() - started
    if temperature_report is not None:
        report["temperatureSelection"] = temperature_report
    report.update(
        {
            "profile": profile,
            "params": int(parameter_count(model)),
            "hidden": list(CAPACITY_PROFILES[profile]),
            "symmetry": bool(symmetry),
            "arch": model.arch,
            "device": device,
            "data": str(data),
            "elapsedSeconds": round(elapsed, 2),
            "datasetStats": dataset.stats(),
        }
    )
    state = {
        "model": model.state_dict(),
        "profile": profile,
        "outputVersion": 2,
        "symmetry": bool(symmetry),
        "capacityTrain": {k: v for k, v in report.items() if k != "history"},
    }
    return model, report, state


def export_profile(
    state: dict[str, Any],
    *,
    profile: str,
    out_path: Path,
    model_version: int,
    symmetry: bool = False,
    symmetry_mode: str = "basis",
) -> dict[str, Any]:
    """Egitilmis durumu ONNX'e yazar ve parite kontrolu yapar."""
    import export_onnx  # noqa: PLC0415
    from model import CAPACITY_PROFILES, VECTOR_SIZE, build_model  # noqa: PLC0415

    model = build_model(
        VECTOR_SIZE,
        output_version=2,
        profile=profile,
        symmetry=symmetry,
        symmetry_mode=symmetry_mode,
    )
    model.load_state_dict(_strip_rank_head(state["model"]))
    model.eval()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_onnx.export(
        model,
        str(out_path),
        model_version,
        "faz7s-capacity",
        output_version=2,
    )
    parity = export_onnx.parity_check(model, str(out_path), output_version=2)
    parity["profile"] = profile
    parity["hidden"] = list(CAPACITY_PROFILES[profile])
    parity["symmetry"] = bool(symmetry)
    parity["arch"] = model.arch
    parity["modelVersion"] = int(model_version)
    parity_path = Path(str(out_path) + ".parity.json")
    parity_path.write_text(json.dumps(parity, indent=2, sort_keys=True), encoding="utf-8")
    return parity


def _run(cmd: Sequence[str], *, quiet: bool) -> int:
    if not quiet:
        print("$ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(list(cmd), cwd=str(REPO_ROOT))
    return int(proc.returncode)


def measure_profile(
    onnx_path: Path,
    *,
    corpus: Path,
    out_dir: Path,
    gnubg: Path | None,
    plies: int,
    limit: int | None,
    quiet: bool,
    per_case: bool = True,
    timeout: float | None = None,
    stride: int = 1,
) -> dict[str, Any]:
    """``er_paths`` ve ``antisymmetry`` olcumlerini calistirir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    er_json = out_dir / "er_paths.json"
    er_md = out_dir / "er_paths.md"
    sym_json = out_dir / "antisymmetry.json"
    sym_md = out_dir / "antisymmetry.md"

    er_cmd = [
        sys.executable,
        str(ML_DIR / "er_paths.py"),
        "measure",
        "--model",
        str(onnx_path),
        "--corpus",
        str(corpus),
        "--plies",
        str(plies),
        "--out",
        str(er_json),
    ]
    if per_case:
        # Eslesmis bootstrap (``compare``) pozisyon basina kaybi ister.
        er_cmd.append("--per-case")
    if gnubg:
        er_cmd += ["--gnubg", str(gnubg)]
    if stride > 1:
        er_cmd += ["--stride", str(stride)]
    if limit:
        er_cmd += ["--limit", str(limit)]
    if timeout:
        er_cmd += ["--timeout", str(int(timeout))]
    if quiet:
        er_cmd.append("--quiet")
    er_code = _run(er_cmd, quiet=quiet)

    sym_cmd = [
        sys.executable,
        str(ML_DIR / "antisymmetry.py"),
        "measure",
        "--model",
        str(onnx_path),
        "--plies",
        str(plies),
        "--out",
        str(sym_json),
        "--markdown",
        str(sym_md),
    ]
    if gnubg:
        sym_cmd += ["--gnubg", str(gnubg)]
    if stride > 1:
        sym_cmd += ["--stride", str(stride)]
    if limit:
        sym_cmd += ["--limit", str(limit)]
    if timeout:
        sym_cmd += ["--timeout", str(int(timeout))]
    sym_code = _run(sym_cmd, quiet=quiet)

    result: dict[str, Any] = {
        "erPaths": None,
        "antisymmetry": None,
        "erExit": er_code,
        "antisymmetryExit": sym_code,
    }
    if er_json.is_file():
        result["erPaths"] = json.loads(er_json.read_text(encoding="utf-8"))
    if sym_json.is_file():
        result["antisymmetry"] = json.loads(sym_json.read_text(encoding="utf-8"))
    return result


def summarize(
    report: dict[str, Any], measurement: dict[str, Any] | None
) -> dict[str, Any]:
    """Rapor satirina gereken alanlari tek sozlukte toplar."""
    row: dict[str, Any] = {
        "profile": report.get("profile"),
        "params": report.get("params"),
        "hidden": report.get("hidden"),
        "trainCount": report.get("trainCount"),
        "valCount": report.get("valCount"),
        "stepsRun": report.get("stepsRun"),
        "bestStep": report.get("bestStep"),
        "stoppedEarly": report.get("stoppedEarly"),
        "trainTop1": report.get("top1"),
        "valTop1": report.get("valTop1"),
        "trainValueMse": report.get("trainValueMse"),
        "valValueMse": report.get("valValueMse"),
        "elapsedSeconds": report.get("elapsedSeconds"),
        "distWeight": report.get("distWeight"),
        "rankWeight": report.get("rankWeight"),
    }
    if measurement:
        paths = (measurement.get("erPaths") or {}).get("paths") or {}
        for name in ("policy", "value", "search1"):
            entry = paths.get(name) or {}
            row[name + "Er"] = entry.get("mean")
            row[name + "Se"] = entry.get("standardError")
            row[name + "Exact"] = entry.get("exactMatchRate")
        sym = measurement.get("antisymmetry") or {}
        row["antisymmetryCorr"] = sym.get("correlation")
        row["antisymmetryMeanAbsSum"] = sym.get("meanAbsSum")
    return row


def build_markdown(rows: Sequence[dict[str, Any]], *, corpus: str, plies: int) -> str:
    """Karsilastirma tablosu (Turkce)."""
    lines = [
        "# Faz 7-S: Kapasite profilleri (medium / large / xlarge)",
        "",
        "Korpus: `%s`, hakem: gnubg %d-ply. Tum profiller **ayni** veri kumesi,"
        % (corpus, plies),
        "**ayni** kayip agirliklari ve **ayni** test seti ile egitildi/olculdu.",
        "",
        "| Profil | Parametre | Gizli | Egitim | Val top-1 | Deger ER | search1 ER |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| %s | %s | %s | %s s | %s | %s | %s |"
            % (
                row.get("profile"),
                _fmt_int(row.get("params")),
                "-".join(str(w) for w in (row.get("hidden") or [])),
                _fmt_num(row.get("elapsedSeconds"), 0),
                _fmt_num(row.get("valTop1"), 4),
                _fmt_er(row.get("valueEr"), row.get("valueSe")),
                _fmt_er(row.get("search1Er"), row.get("search1Se")),
            )
        )
    lines.append("")
    lines.append("| Profil | Politika ER | Antisimetri corr | meanAbsSum | Erken durdu |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                row.get("profile"),
                _fmt_er(row.get("policyEr"), row.get("policySe")),
                _fmt_num(row.get("antisymmetryCorr"), 4),
                _fmt_num(row.get("antisymmetryMeanAbsSum"), 4),
                "evet" if row.get("stoppedEarly") else "hayir",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _fmt_int(value: Any) -> str:
    return "-" if value is None else "{:,}".format(int(value)).replace(",", ".")


def _fmt_num(value: Any, digits: int) -> str:
    return "-" if value is None else ("%." + str(digits) + "f") % float(value)


def _fmt_er(mean: Any, se: Any) -> str:
    if mean is None:
        return "-"
    if se is None:
        return "%.6f" % float(mean)
    return "%.6f ± %.6f" % (float(mean), float(se))


def decide(rows: Sequence[dict[str, Any]], *, baseline: str = "medium") -> dict[str, Any]:
    """Test 96 kurali: medium'a gore >= %15 goreli kazanc **ve** daha iyi ER."""
    by_profile = {str(r.get("profile")): r for r in rows}
    base = by_profile.get(baseline)
    if base is None or base.get("valueEr") is None:
        return {"baseline": baseline, "available": False, "winner": None, "arms": []}
    base_er = float(base["valueEr"])
    base_search = base.get("search1Er")
    arms: list[dict[str, Any]] = []
    for name, row in by_profile.items():
        if name == baseline or row.get("valueEr") is None:
            continue
        er = float(row["valueEr"])
        gain = (base_er - er) / base_er if base_er > 0 else 0.0
        search_gain = None
        if base_search and row.get("search1Er") is not None:
            search_gain = (float(base_search) - float(row["search1Er"])) / float(base_search)
        arms.append(
            {
                "profile": name,
                "valueEr": er,
                "relativeGain": gain,
                "search1Er": row.get("search1Er"),
                "search1RelativeGain": search_gain,
                "meetsThreshold": bool(gain >= CAPACITY_GAIN_THRESHOLD),
            }
        )
    arms.sort(key=lambda a: a["valueEr"])
    winner = None
    if arms and arms[0]["meetsThreshold"]:
        winner = arms[0]["profile"]
    return {
        "baseline": baseline,
        "baselineValueEr": base_er,
        "available": True,
        "threshold": CAPACITY_GAIN_THRESHOLD,
        "arms": arms,
        "winner": winner,
    }


#: R-E: eslesmis bootstrap yeniden ornekleme sayisi.
BOOTSTRAP_RESAMPLES = 2000
#: R-E: iki tarafli %95 guven araligi.
BOOTSTRAP_ALPHA = 0.05


def aggregate_sweep(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Tohum satirlarini tek ozete indirger (ortalama / sd / se).

    R-E'nin "tek tohum yeterli degil" kurali: karar **tohum ortalamasina**
    ve tohumlar arasi sacilima bakar. ``n < 2`` ise ``sd``/``se`` ``None``.
    """
    if not rows:
        return {"seeds": [], "count": 0, "metrics": {}}
    metrics: dict[str, Any] = {}
    keys = sorted({k for row in rows for k in row if k.endswith("Er")})
    for key in keys:
        values = [float(r[key]) for r in rows if r.get(key) is not None]
        if not values:
            continue
        mean = sum(values) / len(values)
        if len(values) > 1:
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            sd = var ** 0.5
            se = sd / (len(values) ** 0.5)
        else:
            sd = None
            se = None
        metrics[key] = {
            "mean": mean,
            "sd": sd,
            "se": se,
            "min": min(values),
            "max": max(values),
            "n": len(values),
        }
    return {
        "seeds": [r.get("seed") for r in rows],
        "count": len(rows),
        "metrics": metrics,
    }


def _load_case_losses(run_dir: Path) -> dict[str, list[float]] | None:
    """``er_paths.json`` icindeki pozisyon basina kayiplari okur."""
    payload = _read_json(Path(run_dir) / "er_paths.json")
    if not payload:
        return None
    losses = payload.get("caseLosses")
    if not isinstance(losses, dict) or not losses:
        return None
    return {str(k): [float(v) for v in vals] for k, vals in losses.items()}


def paired_bootstrap(
    control: Sequence[Sequence[float]],
    treatment: Sequence[Sequence[float]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    alpha: float = BOOTSTRAP_ALPHA,
    seed: int = 0,
) -> dict[str, Any]:
    """Tohum x vaka matrislerinde **eslesmis** bootstrap.

    ``control[k][i]`` ve ``treatment[k][i]`` ayni tohum ve ayni pozisyondur;
    fark ``treatment - control`` alinir. Yeniden ornekleme **pozisyon**
    uzerinden yapilir (tohumlar ayni pozisyon kumesini gorur), boylece hem
    vaka hem tohum degiskenligi ayni araliga girer.
    """
    import random  # noqa: PLC0415

    if len(control) != len(treatment):
        raise ValueError("tohum sayisi farkli: %d vs %d" % (len(control), len(treatment)))
    if not control:
        raise ValueError("bos matris")
    widths = {len(row) for row in list(control) + list(treatment)}
    if len(widths) != 1:
        raise ValueError("vaka sayisi tohumlar arasinda farkli: %r" % (sorted(widths),))
    n_cases = widths.pop()
    if n_cases == 0:
        raise ValueError("vaka sayisi sifir")

    diffs = [
        [treatment[k][i] - control[k][i] for i in range(n_cases)]
        for k in range(len(control))
    ]
    observed = sum(sum(row) for row in diffs) / (len(diffs) * n_cases)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        picks = [rng.randrange(n_cases) for _ in range(n_cases)]
        total = 0.0
        for row in diffs:
            total += sum(row[i] for i in picks)
        means.append(total / (len(diffs) * n_cases))
    means.sort()
    lo = means[int((alpha / 2) * (resamples - 1))]
    hi = means[int((1 - alpha / 2) * (resamples - 1))]
    below = sum(1 for m in means if m <= 0.0)
    p_one_sided = min(below, resamples - below) / resamples
    return {
        "diff": observed,
        "ciLow": lo,
        "ciHigh": hi,
        "pTwoSided": min(1.0, 2 * p_one_sided),
        "significant": bool(lo > 0.0 or hi < 0.0),
        "resamples": resamples,
        "alpha": alpha,
        "seeds": len(diffs),
        "cases": n_cases,
    }


def compare_sweeps(
    control_dir: Path,
    treatment_dir: Path,
    *,
    label_control: str = "kontrol",
    label_treatment: str = "tedavi",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = 0,
    seeds: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Iki coklu-tohum klasorunu yol bazinda eslesmis bootstrap ile karsilastirir.

    ``seeds`` verilirse yalnizca o tohumlar kullanilir; iki tarafin tohum
    sayisi farkli oldugunda (or. 3'e karsi 5) ortak kumeyi secmek icin.
    """
    control_seeds = sorted(p for p in Path(control_dir).glob("seed*") if p.is_dir())
    treatment_seeds = sorted(p for p in Path(treatment_dir).glob("seed*") if p.is_dir())
    if seeds is not None:
        wanted = {"seed%d" % int(s) for s in seeds}
        control_seeds = [p for p in control_seeds if p.name in wanted]
        treatment_seeds = [p for p in treatment_seeds if p.name in wanted]
    if not control_seeds or not treatment_seeds:
        raise ValueError("seed* klasoru yok: %s / %s" % (control_dir, treatment_dir))
    if len(control_seeds) != len(treatment_seeds):
        raise ValueError(
            "tohum sayisi farkli: %d vs %d" % (len(control_seeds), len(treatment_seeds))
        )

    control_losses = [_load_case_losses(p) for p in control_seeds]
    treatment_losses = [_load_case_losses(p) for p in treatment_seeds]
    if any(x is None for x in control_losses) or any(x is None for x in treatment_losses):
        raise ValueError(
            "er_paths.json pozisyon basina kayip icermiyor; "
            "olcumu ``--per-case`` ile yeniden kosun"
        )

    rows: list[dict[str, Any]] = []
    for path in ("policy", "value", "search1"):
        ctrl = [x[path] for x in control_losses if x and path in x]
        trt = [x[path] for x in treatment_losses if x and path in x]
        if len(ctrl) != len(control_seeds) or len(trt) != len(treatment_seeds):
            continue
        stats = paired_bootstrap(ctrl, trt, resamples=resamples, seed=seed)
        ctrl_mean = sum(sum(r) for r in ctrl) / (len(ctrl) * len(ctrl[0]))
        trt_mean = sum(sum(r) for r in trt) / (len(trt) * len(trt[0]))
        stats.update(
            {
                "path": path,
                "control": ctrl_mean,
                "treatment": trt_mean,
                "relative": (stats["diff"] / ctrl_mean) if ctrl_mean else None,
            }
        )
        rows.append(stats)
    if not rows:
        raise ValueError("iki klasorde ortak yol yok")

    return {
        "version": 1,
        "labelControl": label_control,
        "labelTreatment": label_treatment,
        "controlDir": str(control_dir),
        "treatmentDir": str(treatment_dir),
        "seedCount": len(control_seeds),
        "rows": rows,
        "anySignificant": any(r["significant"] for r in rows),
    }


def build_compare_markdown(result: dict[str, Any]) -> str:
    """R-E karsilastirma tablosu (Turkce)."""
    lines = [
        "# R-E: coklu-tohum eslesmis karsilastirma -- %s vs %s"
        % (result["labelControl"], result["labelTreatment"]),
        "",
        "Tohum sayisi **%d**, eslesmis bootstrap %d yeniden ornekleme, %%95 GA."
        % (result["seedCount"], result["rows"][0]["resamples"]),
        "",
        "| Yol | %s | %s | Fark | %%95 GA | Goreli | p | Anlamli |"
        % (result["labelControl"], result["labelTreatment"]),
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(
            "| `%s` | %.6f | %.6f | %+.6f | [%+.6f, %+.6f] | %s | %.4f | %s |"
            % (
                row["path"],
                row["control"],
                row["treatment"],
                row["diff"],
                row["ciLow"],
                row["ciHigh"],
                "-" if row["relative"] is None else "%+.1f%%" % (100 * row["relative"]),
                row["pTwoSided"],
                "evet" if row["significant"] else "hayir",
            )
        )
    lines.append("")
    if not result["anySignificant"]:
        lines.append(
            "**Hicbir yol anlamli degismedi.** Bu, etkinin sifir oldugu kaniti "
            "degil, guc siniridir; tohum sayisi artirilmadan karar verilmemeli."
        )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="capacity_train",
        description="Faz 7-S: kapasite profilini egit, ihrac et, olc.",
    )
    sub = ap.add_subparsers(dest="command")

    run = sub.add_parser("run", help="tek profili egit + ihrac et + olc")
    run.add_argument("--data", type=Path, required=True, help="politika veri kumesi (.npz)")
    run.add_argument(
        "--profile",
        required=True,
        choices=["small", "medium", "large", "xlarge"],
        help="kapasite profili",
    )
    run.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    run.add_argument("--steps", type=int, default=20000)
    run.add_argument("--lr", type=float, default=1e-3)
    run.add_argument("--batch", type=int, default=256)
    run.add_argument("--value-weight", type=float, default=0.5)
    run.add_argument("--dist-weight", type=float, default=0.0)
    run.add_argument("--rank-weight", type=float, default=0.0)
    run.add_argument(
        "--symmetry",
        action="store_true",
        help="mimari antisimetri (Higgins agirlik simetrisi, F7-116): renk takasi "
        "kusuru tanim geregi sifir; egitim artirimi gerekmez",
    )
    run.add_argument(
        "--symmetry-mode",
        choices=["basis", "higgins"],
        default="basis",
        help="antisimetrik kurulum: 'higgins' = duz govde + cikti izdusumu "
        "(duz modelle ayni ifade gucu, iki ileri gecis); 'basis' = V-/V+ izdusumlu "
        "tek gecis (varsayilan)",
    )
    run.add_argument("--val-fraction", type=float, default=0.1)
    run.add_argument("--patience", type=int, default=5)
    run.add_argument("--eval-every", type=int, default=500)
    run.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help="her N adimda denetim noktasi yaz (0 = kapali; F7-118)",
    )
    run.add_argument(
        "--resume",
        action="store_true",
        help="<out-dir>/train_checkpoint.pt varsa oradan devam et (F7-118)",
    )
    run.add_argument("--weight-decay", type=float, default=1e-4)
    run.add_argument("--lr-schedule", default="cosine", choices=["none", "cosine"])
    run.add_argument("--lr-final-ratio", type=float, default=0.1)
    run.add_argument(
        "--policy-temperature",
        type=float,
        default=0.0,
        help=">0 ise R-04 liste bazli KL(softmax(equity/T) || softmax(logits)) "
        "kullanilir; veri kumesinde aday basina equity gerekir",
    )
    run.add_argument(
        "--select-temperature",
        action="store_true",
        help="T'yi dogrulama bolmesinde sec (R-04); --policy-temperature'i ezer",
    )
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    run.add_argument("--model-version", type=int, default=1)
    run.add_argument("--measure", action="store_true", help="ER ve antisimetri olc")
    run.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    run.add_argument("--plies", type=int, default=2)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument(
        "--stride",
        type=int,
        default=1,
        help="olcumde her N'inci vaka (faz temsili alt orneklem; korpus fazlara gore sirali)",
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="gnubg hakem cagrisi basina saniye",
    )
    run.add_argument("--gnubg", type=Path, default=None)
    run.add_argument("--json", type=Path, default=None)
    run.add_argument("--quiet", action="store_true")

    mea = sub.add_parser("measure", help="var olan kosuyu yeniden olc ve capacity.json'u tazele")
    mea.add_argument("--out-dir", type=Path, required=True, help="``run`` cikti klasoru")
    mea.add_argument("--model", type=Path, default=None, help="ONNX yolu (varsayilan: <out-dir>/model.onnx)")
    mea.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    mea.add_argument("--plies", type=int, default=2)
    mea.add_argument("--limit", type=int, default=None)
    mea.add_argument(
        "--stride",
        type=int,
        default=1,
        help="her N'inci vaka (faz temsili alt orneklem; korpus fazlara gore sirali)",
    )
    mea.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="gnubg hakem cagrisi basina saniye (varsayilan: er_paths/antisymmetry kendi degeri)",
    )
    mea.add_argument("--gnubg", type=Path, default=None)
    mea.add_argument("--json", type=Path, default=None)
    mea.add_argument(
        "--reuse",
        action="store_true",
        help="yeniden olcme; klasordeki er_paths.json / antisymmetry.json dosyalarini kullan",
    )
    mea.add_argument("--quiet", action="store_true")

    rep = sub.add_parser("report", help="birden cok profili karsilastir ve karar ver")
    rep.add_argument(
        "--run",
        type=Path,
        action="append",
        required=True,
        metavar="CAPACITY_JSON",
        help="``run`` ciktisi (tekrarlanabilir)",
    )
    rep.add_argument("--baseline", default="medium")
    rep.add_argument("--corpus", default="v2")
    rep.add_argument("--plies", type=int, default=2)
    rep.add_argument("--markdown", type=Path, default=None)
    rep.add_argument("--json", type=Path, default=None)
    rep.add_argument(
        "--notes",
        type=Path,
        default=None,
        help="raporun sonuna eklenecek yorum (markdown)",
    )
    rep.add_argument("--quiet", action="store_true")

    swp = sub.add_parser(
        "sweep", help="ayni profili birden cok tohumla egit (R-E: tek tohum yetmez)"
    )
    swp.add_argument("--data", type=Path, required=True, help="politika veri kumesi (.npz)")
    swp.add_argument(
        "--profile",
        required=True,
        choices=["small", "medium", "large", "xlarge"],
        help="kapasite profili",
    )
    swp.add_argument("--out-dir", type=Path, required=True, help="tohum klasorlerinin ustu")
    swp.add_argument(
        "--seeds",
        default="0,1,2",
        help="virgulle ayrilmis tohum listesi (varsayilan: 0,1,2)",
    )
    swp.add_argument(
        "--skip-existing",
        action="store_true",
        help="capacity.json zaten varsa o tohumu yeniden egitme (yarida kalan tarama)",
    )
    swp.add_argument("--steps", type=int, default=20000)
    swp.add_argument("--lr", type=float, default=1e-3)
    swp.add_argument("--batch", type=int, default=256)
    swp.add_argument("--value-weight", type=float, default=0.5)
    swp.add_argument("--dist-weight", type=float, default=0.0)
    swp.add_argument("--rank-weight", type=float, default=0.0)
    swp.add_argument(
        "--symmetry",
        action="store_true",
        help="mimari antisimetri (Higgins agirlik simetrisi, F7-116)",
    )
    swp.add_argument(
        "--symmetry-mode",
        choices=["basis", "higgins"],
        default="basis",
        help="antisimetrik kurulum (varsayilan: basis)",
    )
    swp.add_argument("--val-fraction", type=float, default=0.1)
    swp.add_argument("--patience", type=int, default=5)
    swp.add_argument("--eval-every", type=int, default=500)
    swp.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help="her N adimda denetim noktasi yaz (0 = kapali; F7-118)",
    )
    swp.add_argument(
        "--resume",
        action="store_true",
        help="profil klasorundeki train_checkpoint.pt varsa oradan devam et (F7-118)",
    )
    swp.add_argument("--weight-decay", type=float, default=1e-4)
    swp.add_argument("--lr-schedule", default="cosine", choices=["none", "cosine"])
    swp.add_argument("--lr-final-ratio", type=float, default=0.1)
    swp.add_argument(
        "--policy-temperature",
        type=float,
        default=0.0,
        help=">0 ise R-04 liste bazli KL(softmax(equity/T) || softmax(logits)) "
        "kullanilir; veri kumesinde aday basina equity gerekir",
    )
    swp.add_argument(
        "--select-temperature",
        action="store_true",
        help="T'yi dogrulama bolmesinde sec (R-04); --policy-temperature'i ezer",
    )
    swp.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    swp.add_argument("--model-version", type=int, default=1)
    swp.add_argument("--measure", action="store_true", help="her tohum icin ER ve antisimetri olc")
    swp.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    swp.add_argument("--plies", type=int, default=2)
    swp.add_argument("--limit", type=int, default=None)
    swp.add_argument(
        "--stride",
        type=int,
        default=1,
        help="olcumde her N'inci vaka (faz temsili alt orneklem; korpus fazlara gore sirali)",
    )
    swp.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="gnubg hakem cagrisi basina saniye",
    )
    swp.add_argument("--gnubg", type=Path, default=None)
    swp.add_argument("--json", type=Path, default=None)
    swp.add_argument("--quiet", action="store_true")

    cmp_ = sub.add_parser(
        "compare", help="iki coklu-tohum klasorunu eslesmis bootstrap ile karsilastir"
    )
    cmp_.add_argument("--control", type=Path, required=True, help="taban sweep klasoru")
    cmp_.add_argument("--treatment", type=Path, required=True, help="tedavi sweep klasoru")
    cmp_.add_argument("--label-control", default="kontrol")
    cmp_.add_argument("--label-treatment", default="tedavi")
    cmp_.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    cmp_.add_argument("--seed", type=int, default=0)
    cmp_.add_argument(
        "--seeds",
        default=None,
        help="virgulle ayrilmis tohum listesi; iki tarafin ortak tohumlarini secmek icin",
    )
    cmp_.add_argument("--markdown", type=Path, default=None)
    cmp_.add_argument("--json", type=Path, default=None)
    cmp_.add_argument("--quiet", action="store_true")

    return ap


def _cmd_run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model, report, state = train_profile(
        args.data,
        profile=args.profile,
        steps=args.steps,
        lr=args.lr,
        batch=args.batch,
        value_weight=args.value_weight,
        dist_weight=args.dist_weight,
        rank_weight=args.rank_weight,
        val_fraction=args.val_fraction,
        patience=args.patience,
        eval_every=args.eval_every,
        weight_decay=args.weight_decay,
        lr_schedule=args.lr_schedule,
        lr_final_ratio=args.lr_final_ratio,
        seed=args.seed,
        device=args.device,
        quiet=args.quiet,
        policy_temperature=float(getattr(args, "policy_temperature", 0.0) or 0.0),
        select_temperature=bool(getattr(args, "select_temperature", False)),
        symmetry=bool(getattr(args, "symmetry", False)),
        symmetry_mode=str(getattr(args, "symmetry_mode", "basis") or "basis"),
        checkpoint=out_dir / "train_checkpoint.pt",
        checkpoint_every=int(getattr(args, "checkpoint_every", 0) or 0),
        resume=bool(getattr(args, "resume", False)),
    )

    import torch  # noqa: PLC0415

    ckpt = out_dir / "checkpoint.pt"
    torch.save(state, str(ckpt))
    (out_dir / "train_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    onnx_path = out_dir / "model.onnx"
    parity = export_profile(
        state,
        profile=args.profile,
        out_path=onnx_path,
        model_version=args.model_version,
        symmetry=bool(getattr(args, "symmetry", False)),
        symmetry_mode=str(getattr(args, "symmetry_mode", "basis") or "basis"),
    )

    measurement = None
    if args.measure:
        measurement = measure_profile(
            onnx_path,
            corpus=Path(args.corpus),
            out_dir=out_dir,
            gnubg=Path(args.gnubg) if args.gnubg else None,
            plies=args.plies,
            limit=args.limit,
            quiet=args.quiet,
            timeout=float(getattr(args, "timeout", 0.0) or 0.0) or None,
            stride=int(getattr(args, "stride", 1) or 1),
        )

    row = summarize(report, measurement)
    row["parityMaxAbsDeltaValue"] = parity.get("maxAbsDeltaValue")
    row["parityMaxAbsDeltaPolicyLogit"] = parity.get("maxAbsDeltaPolicyLogit")
    payload = {
        "profile": args.profile,
        "row": row,
        "train": report,
        "parity": parity,
        "measurement": measurement,
    }
    json_path = Path(args.json) if args.json else out_dir / "capacity.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if not args.quiet:
        print(
            "profil=%s params=%d valTop1=%s degerER=%s search1ER=%s -> %s"
            % (
                args.profile,
                int(report["params"]),
                _fmt_num(row.get("valTop1"), 4),
                _fmt_er(row.get("valueEr"), row.get("valueSe")),
                _fmt_er(row.get("search1Er"), row.get("search1Se")),
                json_path,
            )
        )
    return 0


def _read_json(path: Path) -> Any:
    """Dosya varsa JSON'unu, yoksa ``None`` dondurur."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_measure(args: argparse.Namespace) -> int:
    """Var olan bir kosunun ONNX'ini yeniden olcup ``capacity.json``'u tazeler.

    ``run --measure`` egitimi ve olcumu tek surecte yapar; ancak olcum
    (gnubg 2-ply hakem, 1000 vaka) egitimden kat kat uzun surdugu icin pratikte
    ayri kosulur. Bu alt komut ayni sozlesmeyi korur: ``capacity.json`` icindeki
    ``row`` ve ``measurement`` alanlari yenilenir, ``train``/``parity`` dokunulmaz.
    """
    out_dir = Path(args.out_dir)
    json_path = Path(args.json) if args.json else out_dir / "capacity.json"
    if not json_path.is_file():
        print("capacity.json yok: %s" % (json_path,), file=sys.stderr)
        return 2
    onnx_path = Path(args.model) if args.model else out_dir / "model.onnx"
    if not onnx_path.is_file():
        print("ONNX yok: %s" % (onnx_path,), file=sys.stderr)
        return 2

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if args.reuse:
        measurement = {
            "erPaths": _read_json(out_dir / "er_paths.json"),
            "antisymmetry": _read_json(out_dir / "antisymmetry.json"),
            "erExit": 0,
            "antisymmetryExit": 0,
        }
    else:
        measurement = measure_profile(
            onnx_path,
            corpus=Path(args.corpus),
            out_dir=out_dir,
            gnubg=Path(args.gnubg) if args.gnubg else None,
            plies=args.plies,
            limit=args.limit,
            quiet=args.quiet,
            timeout=float(getattr(args, "timeout", 0.0) or 0.0) or None,
            stride=int(getattr(args, "stride", 1) or 1),
        )
    row = summarize(payload.get("train") or {}, measurement)
    row["parityMaxAbsDeltaValue"] = (payload.get("parity") or {}).get("maxAbsDeltaValue")
    row["parityMaxAbsDeltaPolicyLogit"] = (payload.get("parity") or {}).get(
        "maxAbsDeltaPolicyLogit"
    )
    payload["row"] = row
    payload["measurement"] = measurement
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if not args.quiet:
        print(
            "profil=%s politikaER=%s degerER=%s search1ER=%s -> %s"
            % (
                payload.get("profile"),
                _fmt_er(row.get("policyEr"), row.get("policySe")),
                _fmt_er(row.get("valueEr"), row.get("valueSe")),
                _fmt_er(row.get("search1Er"), row.get("search1Se")),
                json_path,
            )
        )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    rows: list[dict[str, Any]] = []
    for path in args.run:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        row = dict(payload.get("row") or {})
        row.setdefault("profile", payload.get("profile"))
        rows.append(row)
    rows.sort(key=lambda r: ["small", "medium", "large", "xlarge"].index(str(r["profile"])))
    decision = decide(rows, baseline=args.baseline)
    markdown = build_markdown(rows, corpus=args.corpus, plies=args.plies)
    markdown += "\n## Karar\n\n"
    if not decision["available"]:
        markdown += "Taban profil (`%s`) olcumu yok; karar uretilemedi.\n" % args.baseline
    else:
        markdown += (
            "Kural: `%s` profiline gore **>= %%%.0f** goreli deger-ER kazanci.\n\n"
            % (args.baseline, 100 * decision["threshold"])
        )
        markdown += (
            "| Profil | Deger ER | Goreli kazanc | Esik | search1 ER | search1 kazanc |\n"
            "|---|---|---|---|---|---|\n"
        )
        for arm in decision["arms"]:
            search_gain = arm.get("search1RelativeGain")
            markdown += "| %s | %.6f | %+.1f%% | %s | %s | %s |\n" % (
                arm["profile"],
                arm["valueEr"],
                100 * arm["relativeGain"],
                "gecti" if arm["meetsThreshold"] else "kaldi",
                "-" if arm.get("search1Er") is None else "%.6f" % arm["search1Er"],
                "-" if search_gain is None else "%+.1f%%" % (100 * search_gain),
            )
        markdown += "\n**Kazanan:** %s\n" % (
            decision["winner"] or "yok (esigi gecen profil yok)"
        )
    if args.notes:
        notes = Path(args.notes).read_text(encoding="utf-8").replace("\r\n", "\n")
        markdown += "\n" + notes.strip("\n") + "\n"
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(markdown, encoding="utf-8")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps({"rows": rows, "decision": decision}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if not args.quiet:
        print(markdown)
    return 0


def _parse_seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for chunk in str(text).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        seeds.append(int(chunk))
    if not seeds:
        raise ValueError("tohum listesi bos")
    if len(set(seeds)) != len(seeds):
        raise ValueError("yinelenen tohum: %r" % (seeds,))
    return seeds


def _cmd_sweep(args: argparse.Namespace) -> int:
    """Ayni profili N tohumla egitir; her tohum kendi klasorune yazilir.

    R-E kurali: tek tohum karar icin yetmez. Bu alt komut ``run``'i tohum
    basina cagirir ve sonunda ``sweep.json`` icine tohum satirlarini ve
    tohum-ortalamasi ozetini yazar.
    """
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = _parse_seeds(args.seeds)

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        seed_dir = out_dir / ("seed%d" % seed)
        seed_dir.mkdir(parents=True, exist_ok=True)
        existing = seed_dir / "capacity.json"
        if getattr(args, "skip_existing", False) and existing.is_file():
            payload = _read_json(existing) or {}
            if payload.get("row"):
                row = dict(payload["row"])
                row["seed"] = seed
                rows.append(row)
                if not args.quiet:
                    print(
                        "=== %s tohum %d mevcut, atlandi" % (args.profile, seed),
                        file=sys.stderr,
                    )
                continue
        child = argparse.Namespace(**vars(args))
        child.out_dir = seed_dir
        child.seed = seed
        child.json = seed_dir / "capacity.json"
        child.command = "run"
        if not args.quiet:
            print("=== %s tohum %d -> %s" % (args.profile, seed, seed_dir), file=sys.stderr)
        code = _cmd_run(child)
        if code != 0:
            print("tohum %d basarisiz (kod %d)" % (seed, code), file=sys.stderr)
            return code
        payload = _read_json(seed_dir / "capacity.json") or {}
        row = dict(payload.get("row") or {})
        row["seed"] = seed
        rows.append(row)

    summary = aggregate_sweep(rows)
    payload = {
        "profile": args.profile,
        "seeds": seeds,
        "rows": rows,
        "summary": summary,
    }
    json_path = Path(args.json) if args.json else out_dir / "sweep.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if not args.quiet:
        print(
            "%s: %d tohum, degerER=%s, search1ER=%s -> %s"
            % (
                args.profile,
                len(seeds),
                _fmt_er(
                    (summary["metrics"].get("valueEr") or {}).get("mean"),
                    (summary["metrics"].get("valueEr") or {}).get("se"),
                ),
                _fmt_er(
                    (summary["metrics"].get("search1Er") or {}).get("mean"),
                    (summary["metrics"].get("search1Er") or {}).get("se"),
                ),
                json_path,
            )
        )
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    seeds = _parse_seeds(args.seeds) if getattr(args, "seeds", None) else None
    result = compare_sweeps(
        Path(args.control),
        Path(args.treatment),
        label_control=args.label_control,
        label_treatment=args.label_treatment,
        resamples=args.resamples,
        seed=args.seed,
        seeds=seeds,
    )
    text = build_compare_markdown(result)
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
    if not args.quiet:
        print(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "measure":
        return _cmd_measure(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "sweep":
        return _cmd_sweep(args)
    if args.command == "compare":
        return _cmd_compare(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
