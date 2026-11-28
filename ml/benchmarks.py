# -*- coding: utf-8 -*-
"""Faz 8 Görev 2: **plan etiketli sabit kıyaslama paneli** ve **model envanteri**.

Faz 7'ye kadar güç iddiaları tek bir 50 pozisyonluk ER setiyle ve tek bir
sayıyla ("ER 0,1941") yapılıyordu. Bu iki sorunu birlikte doğuruyordu:

1. **Plan körlüğü.** bgsage'in kendi kırılımı (purerace 0,02 / racing 0,25 /
   attacking 0,20 / priming 0,32 / anchoring 0,32) tek bir ortalama ER'de
   kaybolur. Hangi planda zayıf olduğumuz bilinmeden "daha iyi" iddiası
   kurulamaz (Faz 8 §0 kural 4).
2. **İzlenebilirlik kaybı.** `ml/runs/` gitignore'da; bir ONNX dosyası
   silindiğinde hiçbir uyarı çıkmıyordu (kırmızı çizgi G9).

Bu modül iki artefakt üretir:

``ml/artifacts/benchmark_sets.json``
    Plan etiketli, **sabit** (hash'li) pozisyon setleri. Setler bir kez
    üretilir; sonraki ölçümler aynı dosyayı okur, böylece iki model
    karşılaştırılabilir olur.
``ml/artifacts/model_benchmarks.json`` / ``.md``
    **Yalnızca ekleme** yapılan ölçüm günlüğü. Her kayıt bir model + bir set
    hash'i + ölçüm parametreleri taşır; eski kayıt asla değiştirilmez.
``ml/artifacts/model_inventory.json`` / ``.md``
    Her ONNX dosyasının yolu, sha256'sı, boyutu, çıktı sözleşmesi, onu üreten
    `F7-xx`/`F8-xx` kaydı ve paneldeki satırı. Eksik dosya sessiz kayıp değil,
    **alarm** olur.

Plan sınıflandırıcısı bgsage'in plan taksonomisini pip/punton kurallarıyla
yeniden kurar (kod kopyalanmadı; MPL-2.0 başlık taşıyan dosya alınmadı —
Faz 8 §9).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import gnubg_er  # noqa: E402
from tools import reference_gen as refgen  # noqa: E402

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------

BENCH_VERSION = 1

#: bgsage plan taksonomisi (Faz 8 §2 M2/M5).
PLANS = ("purerace", "racing", "attacking", "priming", "anchoring", "backgame")

#: Panel setleri: ad -> hangi planlardan oluşur.
SETS: dict[str, tuple[str, ...]] = {
    "contact": ("attacking", "priming", "anchoring", "backgame"),
    "race": ("purerace", "racing"),
    "all": PLANS,
}

#: gnubg `contact.bm` / `race.bm` muadili iki ana set.
PRIMARY_SETS = ("contact", "race")

DEFAULT_PER_PLAN = 40
DEFAULT_SEED = 20261127

SETS_PATH = Path("ml/artifacts/benchmark_sets.json")
BENCH_JSON_PATH = Path("ml/artifacts/model_benchmarks.json")
BENCH_MD_PATH = Path("ml/artifacts/model_benchmarks.md")
INVENTORY_JSON_PATH = Path("ml/artifacts/model_inventory.json")
INVENTORY_MD_PATH = Path("ml/artifacts/model_inventory.md")
ASSUMPTIONS_PATH = Path("ASSUMPTIONS.md")

#: Doğal pozisyon kaynakları (plan dağılımı bunlardan örneklenir).
DEFAULT_SOURCES = (
    Path("ml/artifacts/corpus2_records.json"),
    Path("ml/artifacts/reference_corpus_v1.json"),
)

#: Backgame eşiği (bgsage Stage 10 geçidi): 3+ anchor, VEYA 2 anchor + >=7 arka
#: pul + >=200 pip.
BACKGAME_MIN_ANCHORS = 3
BACKGAME_MIN_BACK_CHECKERS = 7
BACKGAME_MIN_PIP = 200

#: Prime uzunluğu ve bölgesi (4'ten 12'ye kadar ardışık yapılmış punton).
PRIME_MIN_RUN = 4
PRIME_ZONE = range(4, 13)

#: Anchoring için yarışta geride olma eşiği (pip).
ANCHORING_PIP_MARGIN = 10

#: Attacking için kendi evinde yapılmış punto sayısı eşiği.
ATTACKING_MIN_HOME_POINTS = 3

#: ``racing`` için temas bölgesinde kalan toplam pul üst sınırı. İki taraf da
#: neredeyse kaçmışsa pozisyon yarıştır; aksi halde temas hâlâ oyunu belirler ve
#: etiket ``attacking`` (genel temas planı) olur.
RACING_MAX_CONTACT_CHECKERS = 10


class BenchmarkError(RuntimeError):
    """Panel/envanter sözleşmesi ihlali."""


# ----------------------------------------------------------------------
# Plan sınıflandırıcısı
# ----------------------------------------------------------------------


def _count_of(value: int, player: int) -> int:
    if player > 0:
        return value if value > 0 else 0
    return -value if value < 0 else 0


def _point(turn: int, distance: int) -> int:
    """``turn`` oyuncusunun ``distance`` uzaklığındaki punto indeksi."""
    return 25 - distance if turn == 1 else distance


def _made(board: Sequence[int], turn: int, distance: int) -> bool:
    return _count_of(board[_point(turn, distance)], turn) >= 2


def home_points(board: Sequence[int], turn: int) -> int:
    """``turn`` oyuncusunun kendi evinde yapılmış punto sayısı (1..6)."""
    return sum(1 for d in range(1, 7) if _made(board, turn, d))


def anchor_count(board: Sequence[int], turn: int) -> int:
    """Rakibin evinde yapılmış punto (anchor) sayısı.

    ``turn`` için rakip evi 19..24 uzaklığındadır.
    """
    return sum(1 for d in range(19, 25) if _made(board, turn, d))


def back_checkers(board: Sequence[int], turn: int) -> int:
    """Rakibin evindeki + bardaki ``turn`` pulu sayısı."""
    total = _count_of(board[refgen.bar_index(turn)], turn)
    for d in range(19, 25):
        total += _count_of(board[_point(turn, d)], turn)
    return total


def prime_points(board: Sequence[int], turn: int, need: int = PRIME_MIN_RUN) -> tuple[int, ...]:
    """``need`` uzunlukta en uzun prime'ın punto indeksleri; yoksa boş demet.

    Prime 4..12 uzaklık bölgesinde aranır (bgsage priming tanımı).
    """
    best: tuple[int, ...] = ()
    run: list[int] = []
    for d in PRIME_ZONE:
        if _made(board, turn, d):
            run.append(_point(turn, d))
            if len(run) >= need and len(run) > len(best):
                best = tuple(run)
        else:
            run = []
    return best


def prime_front(board: Sequence[int], turn: int, need: int = PRIME_MIN_RUN) -> int:
    """Prime'ın eve en yakın uzaklığı; prime yoksa 0."""
    points = prime_points(board, turn, need)
    if not points:
        return 0
    return min(gnubg_er._distance_to_off(point, turn) for point in points)


def _opponent_behind(board: Sequence[int], turn: int, points: Sequence[int]) -> bool:
    """Rakibin prime'ı geçmek zorunda olan pulu var mı.

    Rakip kendi evine doğru ilerler; prime'ın **rakibin** bakış açısındaki en
    yakın noktasından daha geride olan her pul prime'ı geçmek zorundadır.
    """
    if not points:
        return False
    opponent = -turn
    front = min(gnubg_er._distance_to_off(point, opponent) for point in points)
    for point in range(1, 25):
        if _count_of(board[point], opponent) and (
            gnubg_er._distance_to_off(point, opponent) > front
        ):
            return True
    return _count_of(board[refgen.bar_index(opponent)], opponent) > 0


def _opponent_blots_in_home(board: Sequence[int], turn: int) -> int:
    opponent = -turn
    return sum(1 for d in range(1, 7) if _count_of(board[_point(turn, d)], opponent) == 1)


def contact_zone_checkers(board: Sequence[int], turn: int) -> int:
    """``turn`` oyuncusunun hâlâ temas bölgesinde olan pul sayısı."""
    return refgen.PIECES - gnubg_er.escaped_count(board, turn)


def classify_plan(board: Sequence[int], turn: int) -> str:
    """Pozisyonun plan etiketi (``PLANS`` içinden, deterministik).

    Öncelik sırası: ``purerace`` → ``backgame`` → ``priming`` → ``attacking``
    (evde blot/bar) → ``anchoring`` → ``racing`` (temas bölgesi boşalıyor) →
    ``attacking`` (genel temas planı). Sıra sabittir; aynı pozisyon her zaman
    aynı etiketi alır (test 436).
    """
    if turn not in (1, -1):
        raise BenchmarkError("turn 1 veya -1 olmali: %r" % (turn,))
    if not gnubg_er.is_contact(board):
        return "purerace"

    anchors = anchor_count(board, turn)
    back = back_checkers(board, turn)
    pip = gnubg_er.pip_count(board, turn)
    opponent_pip = gnubg_er.pip_count(board, -turn)

    if anchors >= BACKGAME_MIN_ANCHORS or (
        anchors >= 2 and back >= BACKGAME_MIN_BACK_CHECKERS and pip >= BACKGAME_MIN_PIP
    ):
        return "backgame"

    front = prime_points(board, turn)
    if front and _opponent_behind(board, turn, front):
        return "priming"

    on_bar = _count_of(board[refgen.bar_index(-turn)], -turn) > 0
    if (_opponent_blots_in_home(board, turn) > 0 or on_bar) and (
        home_points(board, turn) >= ATTACKING_MIN_HOME_POINTS
    ):
        return "attacking"

    if anchors >= 1 and pip > opponent_pip + ANCHORING_PIP_MARGIN:
        return "anchoring"

    in_contact = contact_zone_checkers(board, turn) + contact_zone_checkers(board, -turn)
    if in_contact <= RACING_MAX_CONTACT_CHECKERS:
        return "racing"

    return "attacking"


# ----------------------------------------------------------------------
# Set üretimi
# ----------------------------------------------------------------------


def _load_source_cases(path: Path) -> list[dict[str, Any]]:
    """Kaynak dosyadan ``board``/``turn`` taşıyan vakaları okur."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        cases = data.get("cases")
        if not isinstance(cases, list):
            raise BenchmarkError("cases listesi yok: %s" % path)
    elif isinstance(data, list):
        cases = data
    else:
        raise BenchmarkError("desteklenmeyen kaynak bicimi: %s" % path)
    out: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        board = case.get("board")
        turn = case.get("turn")
        if not isinstance(board, list) or len(board) != refgen.BOARD_SIZE:
            continue
        if turn not in (1, -1):
            continue
        out.append(case)
    return out


def _case_key(case: dict[str, Any]) -> str:
    """Pozisyonun kimliği: aynı board+turn+dice iki kez girmesin."""
    payload = [
        [int(v) for v in case["board"]],
        int(case["turn"]),
        [int(d) for d in case.get("dice", [])],
        int(case.get("whiteOff", 0)),
        int(case.get("blackOff", 0)),
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def _normalize_case(case: dict[str, Any], plan: str, index: int) -> dict[str, Any]:
    """Set dosyasına yazılacak sade kayıt."""
    board = [int(v) for v in case["board"]]
    turn = int(case["turn"])
    white_off = int(case.get("whiteOff", 0))
    black_off = int(case.get("blackOff", 0))
    dice = sorted(int(d) for d in case.get("dice", [1, 1]))
    if len(dice) == 2 and dice[0] == dice[1]:
        dice = [dice[0]] * 4
    if len(dice) not in (2, 4):
        raise BenchmarkError("zar 2 veya 4 elemanli olmali: %r" % (dice,))

    after_states = case.get("afterStates")
    if not after_states:
        _max_steps, states = refgen.legal_after_states(board, turn, dice, white_off, black_off)
        after_states = [
            {"board": list(b), "whiteOff": wo, "blackOff": bo} for b, wo, bo in sorted(states)
        ]
    else:
        after_states = [
            {
                "board": [int(v) for v in a["board"]],
                "whiteOff": int(a.get("whiteOff", 0)),
                "blackOff": int(a.get("blackOff", 0)),
            }
            for a in after_states
        ]

    return {
        "name": "%s-%03d" % (plan, index),
        "plan": plan,
        "board": board,
        "turn": turn,
        "dice": dice,
        "whiteOff": white_off,
        "blackOff": black_off,
        "afterStates": after_states,
    }


def build_sets(
    sources: Sequence[Path] = DEFAULT_SOURCES,
    *,
    per_plan: int = DEFAULT_PER_PLAN,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Plan etiketli sabit setleri **deterministik** olarak üretir.

    Aynı ``sources`` + ``per_plan`` + ``seed`` her zaman aynı dosyayı verir
    (test 437). Plan başına hedef dolmazsa eksik sayı ``shortfall`` alanına
    yazılır — sessizce az pozisyonla ölçüm yapılmaz.
    """
    if per_plan <= 0:
        raise BenchmarkError("per_plan pozitif olmali: %r" % (per_plan,))

    buckets: dict[str, list[dict[str, Any]]] = {plan: [] for plan in PLANS}
    seen: set[str] = set()
    for path in sources:
        if not Path(path).exists():
            raise BenchmarkError("kaynak bulunamadi: %s" % path)
        for case in _load_source_cases(Path(path)):
            key = _case_key(case)
            if key in seen:
                continue
            seen.add(key)
            plan = classify_plan(case["board"], int(case["turn"]))
            buckets[plan].append(case)

    rng = random.Random(seed)
    cases: list[dict[str, Any]] = []
    shortfall: dict[str, int] = {}
    for plan in PLANS:
        pool = buckets[plan]
        if len(pool) > per_plan:
            chosen = rng.sample(pool, per_plan)
        else:
            chosen = list(pool)
            shortfall[plan] = per_plan - len(pool)
        chosen.sort(key=_case_key)
        for i, case in enumerate(chosen):
            cases.append(_normalize_case(case, plan, i))

    cases.sort(key=lambda c: (PLANS.index(c["plan"]), c["name"]))
    return {
        "benchVersion": BENCH_VERSION,
        "generator": "ml/benchmarks.py",
        "seed": seed,
        "perPlan": per_plan,
        "sources": [str(p).replace("\\", "/") for p in sources],
        "plans": list(PLANS),
        "sets": {name: list(plans) for name, plans in SETS.items()},
        "shortfall": shortfall,
        "planCounts": {plan: sum(1 for c in cases if c["plan"] == plan) for plan in PLANS},
        "setHashes": {
            name: set_hash([c for c in cases if c["plan"] in plans])
            for name, plans in SETS.items()
        },
        "cases": cases,
    }


def set_hash(cases: Sequence[dict[str, Any]]) -> str:
    """Set içeriğinin sha256'sı (sıra dahil, biçim sabit)."""
    payload = json.dumps(list(cases), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_sets(data: dict[str, Any], path: Path = SETS_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def load_sets(path: Path = SETS_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise BenchmarkError("set dosyasi yok: %s (once 'build' calistirin)" % path)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("benchVersion") != BENCH_VERSION:
        raise BenchmarkError(
            "benchVersion uyumsuz: %r (beklenen %d)" % (data.get("benchVersion"), BENCH_VERSION)
        )
    return data


def cases_for_set(data: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Set adına düşen vakalar (``SETS`` tanımına göre)."""
    if name not in SETS:
        raise BenchmarkError("bilinmeyen set %r (secenekler: %s)" % (name, ", ".join(SETS)))
    plans = set(SETS[name])
    return [c for c in data["cases"] if c["plan"] in plans]


def verify_sets(data: dict[str, Any]) -> list[str]:
    """Set dosyasının kendi içinde tutarlı olduğunu doğrular; sorun listesi döner."""
    problems: list[str] = []
    cases = data.get("cases") or []
    if not cases:
        problems.append("cases bos")
        return problems
    for name, plans in SETS.items():
        subset = [c for c in cases if c.get("plan") in set(plans)]
        expected = (data.get("setHashes") or {}).get(name)
        actual = set_hash(subset)
        if expected != actual:
            problems.append("set %s hash uyusmuyor: %s != %s" % (name, expected, actual))
    for case in cases:
        if case.get("plan") not in PLANS:
            problems.append("bilinmeyen plan: %r" % (case.get("plan"),))
        if not case.get("afterStates"):
            problems.append("afterStates bos: %s" % case.get("name"))
        recomputed = classify_plan(case["board"], int(case["turn"]))
        if recomputed != case.get("plan"):
            problems.append(
                "plan etiketi degisti: %s (%s -> %s)"
                % (case.get("name"), case.get("plan"), recomputed)
            )
    return problems


# ----------------------------------------------------------------------
# Ölçüm günlüğü (yalnızca ekleme)
# ----------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def measure_model(
    model_path: Path,
    data: dict[str, Any],
    *,
    gnubg: Path,
    plies: int = 2,
    criterion: str = "policy",
    set_names: Sequence[str] = PRIMARY_SETS,
    progress: bool = True,
) -> dict[str, Any]:
    """Bir modeli setler üzerinde ölçer; kayıt sözlüğü döner (dosyaya yazmaz)."""
    model_path = Path(model_path)
    if not model_path.exists():
        raise BenchmarkError("model bulunamadi: %s" % model_path)

    scorer = gnubg_er.OnnxScorer(model_path)
    output_version = int(scorer.output_version)
    del scorer

    results: dict[str, Any] = {}
    for name in set_names:
        cases = cases_for_set(data, name)
        if not cases:
            raise BenchmarkError("set bos: %s" % name)
        measured, skipped = gnubg_er.measure(
            model_path,
            cases,
            gnubg=gnubg,
            plies=plies,
            criterion=criterion,
            progress=progress,
        )
        summary = gnubg_er.summarize(measured)
        results[name] = {
            "setHash": set_hash(cases),
            "count": int(summary["count"]),
            "mean": round(summary["mean"], 6),
            "median": round(summary["median"], 6),
            "max": round(summary["max"], 6),
            "exactMatchRate": round(summary["exactMatchRate"], 6),
            "skipped": list(skipped),
            "perPlan": _per_plan_summary(measured, cases),
        }

    return {
        "recordId": "%s|%s|%s|%d|%s"
        % (model_path.as_posix(), file_sha256(model_path)[:16], criterion, plies, _now()),
        "timestamp": _now(),
        "model": {
            "path": model_path.as_posix(),
            "sha256": file_sha256(model_path),
            "sizeBytes": model_path.stat().st_size,
            "outputVersion": output_version,
        },
        "criterion": criterion,
        "plies": plies,
        "benchVersion": BENCH_VERSION,
        "sets": results,
    }


def _per_plan_summary(
    measured: Sequence[gnubg_er.PositionResult], cases: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    by_name = {str(c.get("name")): c.get("plan") for c in cases}
    buckets: dict[str, list[float]] = {}
    for result in measured:
        plan = by_name.get(result.name)
        if plan is None:
            continue
        buckets.setdefault(plan, []).append(result.equity_loss)
    out: dict[str, Any] = {}
    for plan in PLANS:
        losses = buckets.get(plan)
        if not losses:
            continue
        out[plan] = {
            "count": len(losses),
            "mean": round(sum(losses) / len(losses), 6),
            "max": round(max(losses), 6),
        }
    return out


def load_benchmarks(path: Path = BENCH_JSON_PATH) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    records = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise BenchmarkError("records listesi yok: %s" % path)
    return records


def append_benchmark(record: dict[str, Any], path: Path = BENCH_JSON_PATH) -> Path:
    """Kaydı **yalnızca ekler**; aynı ``recordId`` varsa hata verir (test 439)."""
    path = Path(path)
    records = load_benchmarks(path)
    if any(r.get("recordId") == record.get("recordId") for r in records):
        raise BenchmarkError("kayit zaten var (ekleme-yalniz): %s" % record.get("recordId"))
    records.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"benchVersion": BENCH_VERSION, "records": records}, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def build_bench_markdown(records: Sequence[dict[str, Any]]) -> str:
    """Ölçüm günlüğünün markdown tablosu."""
    lines = [
        "# Model kıyaslama paneli (Faz 8 Görev 2)",
        "",
        "Plan etiketli sabit setler üzerinde gnubg referanslı ER. **Yalnızca ekleme**:",
        "eski satırlar değiştirilmez, yeni ölçüm sona eklenir.",
        "",
        "Setler: `contact` = attacking + priming + anchoring + backgame;",
        "`race` = purerace + racing. Set hash'i değişirse satırlar karşılaştırılamaz.",
        "",
        "| # | Zaman | Model | sha256 | Çıktı | Set | Hash | n | ER ort. | Medyan | Maks | Tam eşleşme |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, record in enumerate(records, start=1):
        model = record.get("model", {})
        for name, summary in (record.get("sets") or {}).items():
            lines.append(
                "| %d | %s | `%s` | `%s` | v%s | %s | `%s` | %d | %.4f | %.4f | %.4f | %.1f%% |"
                % (
                    i,
                    record.get("timestamp", "?"),
                    model.get("path", "?"),
                    str(model.get("sha256", ""))[:12],
                    model.get("outputVersion", "?"),
                    name,
                    str(summary.get("setHash", ""))[:12],
                    int(summary.get("count", 0)),
                    float(summary.get("mean", 0.0)),
                    float(summary.get("median", 0.0)),
                    float(summary.get("max", 0.0)),
                    100.0 * float(summary.get("exactMatchRate", 0.0)),
                )
            )
    lines.append("")
    lines.append("## Plan kırılımı (son kayıt)")
    lines.append("")
    if records:
        last = records[-1]
        lines.append("| Set | Plan | n | ER ort. | Maks |")
        lines.append("|---|---|---|---|---|")
        for name, summary in (last.get("sets") or {}).items():
            for plan, stats in (summary.get("perPlan") or {}).items():
                lines.append(
                    "| %s | %s | %d | %.4f | %.4f |"
                    % (name, plan, int(stats["count"]), float(stats["mean"]), float(stats["max"]))
                )
    else:
        lines.append("_Kayıt yok._")
    lines.append("")
    lines.extend(_comparison_lines(records))
    return "\n".join(lines)


def _comparison_lines(records: Sequence[dict[str, Any]]) -> list[str]:
    """Her modelin **en son** ölçümünü yan yana koyan karşılaştırma tablosu.

    Panelin amacı tek sayı değil **sıralama**; bu tablo ``contact`` setine göre
    artan ER sırasında verir. Aynı model birden çok kez ölçüldüyse yalnız son
    kayıt kullanılır (günlük ekleme-yalnız olduğu için bu her zaman en yenidir).
    """
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        path = (record.get("model") or {}).get("path")
        if path:
            latest[path] = record
    if not latest:
        return ["## Model karşılaştırması", "", "_Kayıt yok._", ""]

    set_names: list[str] = []
    for record in latest.values():
        for name in (record.get("sets") or {}):
            if name not in set_names:
                set_names.append(name)

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, str]:
        summary = (item[1].get("sets") or {}).get("contact") or {}
        return (float(summary.get("mean", float("inf"))), item[0])

    lines = ["## Model karşılaştırması", ""]
    header = ["Model", "sha256"]
    for name in set_names:
        header.extend(["%s ER" % name, "%s eşleşme" % name])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for path, record in sorted(latest.items(), key=sort_key):
        cells = ["`%s`" % path, "`%s`" % str((record.get("model") or {}).get("sha256", ""))[:12]]
        for name in set_names:
            summary = (record.get("sets") or {}).get(name) or {}
            if summary:
                cells.append("%.4f" % float(summary.get("mean", 0.0)))
                cells.append("%.1f%%" % (100.0 * float(summary.get("exactMatchRate", 0.0))))
            else:
                cells.extend(["—", "—"])
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def write_bench_markdown(records: Sequence[dict[str, Any]], path: Path = BENCH_MD_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(build_bench_markdown(records))
    return path


# ----------------------------------------------------------------------
# Model envanteri (kırmızı çizgi G9)
# ----------------------------------------------------------------------


def _f_records_for(relative: str, assumptions: Path = ASSUMPTIONS_PATH) -> list[str]:
    """``ASSUMPTIONS.md`` içinde bu yolu anan `F7-xx`/`F8-xx` kayıtları."""
    assumptions = Path(assumptions)
    if not assumptions.exists():
        return []
    text = assumptions.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"(?m)^## (F\d+-\d+)\b", text)
    hits: list[str] = []
    needle = relative.replace("\\", "/")
    parent = Path(needle).parent.as_posix()
    for i in range(1, len(sections) - 1, 2):
        record_id = sections[i]
        body = sections[i + 1].replace("\\", "/")
        if needle in body or (parent and parent in body):
            hits.append(record_id)
    return hits


def _panel_rows(records: Sequence[dict[str, Any]], relative: str) -> list[int]:
    """Panel günlüğünde bu modelin satır numaraları (1 tabanlı)."""
    rows: list[int] = []
    for i, record in enumerate(records, start=1):
        if (record.get("model") or {}).get("path") == relative:
            rows.append(i)
    return rows


def build_inventory(
    *,
    roots: Sequence[Path] = (Path("ml/runs"), Path("ml/artifacts")),
    benchmarks: Sequence[dict[str, Any]] | None = None,
    assumptions: Path = ASSUMPTIONS_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Tüm ONNX dosyalarının envanteri; eksik dosya **alarm** üretir."""
    if benchmarks is None:
        benchmarks = load_benchmarks()

    repo_root = Path(repo_root).resolve()
    entries: list[dict[str, Any]] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.onnx")):
            try:
                relative = path.resolve().relative_to(repo_root).as_posix()
            except ValueError:
                relative = path.as_posix()
            try:
                output_version = int(gnubg_er.OnnxScorer(path).output_version)
            except Exception as exc:  # bozuk ONNX de envanterde görünmeli
                output_version = -1
                note = "okunamadi: %s" % exc
            else:
                note = ""
            entries.append(
                {
                    "path": relative,
                    "sha256": file_sha256(path),
                    "sizeBytes": path.stat().st_size,
                    "outputVersion": output_version,
                    "fRecords": _f_records_for(relative, assumptions),
                    "panelRows": _panel_rows(benchmarks, relative),
                    "note": note,
                }
            )

    # Panelde ölçülmüş ama diskte olmayan modeller: sessiz kayıp alarmı.
    present = {e["path"] for e in entries}
    missing: list[dict[str, Any]] = []
    for record in benchmarks:
        model = record.get("model") or {}
        path = model.get("path")
        if path and path not in present:
            missing.append(
                {
                    "path": path,
                    "sha256": model.get("sha256", ""),
                    "recordId": record.get("recordId", ""),
                }
            )

    return {
        "inventoryVersion": 1,
        "generatedAt": _now(),
        "roots": [Path(r).as_posix() for r in roots],
        "count": len(entries),
        "entries": entries,
        "missing": missing,
        "alarm": bool(missing),
    }


def build_inventory_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Model envanteri (Faz 8 Görev 2, kırmızı çizgi G9)",
        "",
        "Üretim: `python ml/benchmarks.py inventory`. Her ONNX dosyası için yol, sha256,",
        "boyut, çıktı sözleşmesi, onu üreten `F7-xx`/`F8-xx` kaydı ve panel satırı.",
        "",
        "**Alarm:** panelde ölçülmüş ama diskte bulunmayan model = sessiz kayıp.",
        "",
        "- Üretim zamanı: %s" % inventory.get("generatedAt", "?"),
        "- Dosya sayısı: %d" % int(inventory.get("count", 0)),
        "- Alarm: **%s**" % ("VAR" if inventory.get("alarm") else "yok"),
        "",
        "| Yol | sha256 | Bayt | Çıktı | F kaydı | Panel satırı |",
        "|---|---|---|---|---|---|",
    ]
    for entry in inventory.get("entries", []):
        lines.append(
            "| `%s` | `%s` | %d | v%s | %s | %s |"
            % (
                entry["path"],
                str(entry["sha256"])[:12],
                int(entry["sizeBytes"]),
                entry["outputVersion"],
                ", ".join(entry["fRecords"]) or "—",
                ", ".join(str(r) for r in entry["panelRows"]) or "—",
            )
        )
    if inventory.get("missing"):
        lines.append("")
        lines.append("## Eksik dosyalar (alarm)")
        lines.append("")
        lines.append("| Yol | sha256 | Kayıt |")
        lines.append("|---|---|---|")
        for item in inventory["missing"]:
            lines.append(
                "| `%s` | `%s` | `%s` |"
                % (item["path"], str(item["sha256"])[:12], item["recordId"])
            )
    lines.append("")
    return "\n".join(lines)


def write_inventory(inventory: dict[str, Any], json_path: Path = INVENTORY_JSON_PATH, md_path: Path = INVENTORY_MD_PATH) -> tuple[Path, Path]:
    json_path = Path(json_path)
    md_path = Path(md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(inventory, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    with open(md_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(build_inventory_markdown(inventory))
    return json_path, md_path


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Faz 8 plan etiketli kiyaslama paneli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="sabit setleri uret")
    p_build.add_argument("--per-plan", type=int, default=DEFAULT_PER_PLAN)
    p_build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_build.add_argument("--source", type=Path, action="append", default=None)
    p_build.add_argument("--out", type=Path, default=SETS_PATH)

    p_check = sub.add_parser("check", help="set dosyasini dogrula")
    p_check.add_argument("--sets", type=Path, default=SETS_PATH)

    p_measure = sub.add_parser("measure", help="bir modeli panelde olc")
    p_measure.add_argument("--model", type=Path, required=True)
    p_measure.add_argument("--sets", type=Path, default=SETS_PATH)
    p_measure.add_argument("--set", dest="set_names", action="append", default=None)
    p_measure.add_argument("--plies", type=int, default=2)
    p_measure.add_argument("--criterion", default="policy", choices=list(gnubg_er.CRITERIA))
    p_measure.add_argument("--gnubg", type=Path, default=None)
    p_measure.add_argument("--out", type=Path, default=BENCH_JSON_PATH)
    p_measure.add_argument("--markdown", type=Path, default=BENCH_MD_PATH)
    p_measure.add_argument("--quiet", action="store_true")

    p_inv = sub.add_parser("inventory", help="ONNX envanterini uret")
    p_inv.add_argument("--benchmarks", type=Path, default=BENCH_JSON_PATH)
    p_inv.add_argument("--json", type=Path, default=INVENTORY_JSON_PATH)
    p_inv.add_argument("--markdown", type=Path, default=INVENTORY_MD_PATH)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "build":
        sources = tuple(args.source) if args.source else DEFAULT_SOURCES
        data = build_sets(sources, per_plan=args.per_plan, seed=args.seed)
        path = write_sets(data, args.out)
        print("setler yazildi: %s" % path)
        print("plan sayilari: %s" % json.dumps(data["planCounts"], ensure_ascii=False))
        if data["shortfall"]:
            print("EKSIK: %s" % json.dumps(data["shortfall"], ensure_ascii=False))
        for name, digest in data["setHashes"].items():
            print("  %-8s %s" % (name, digest))
        return 0

    if args.command == "check":
        data = load_sets(args.sets)
        problems = verify_sets(data)
        if problems:
            for problem in problems:
                print("SORUN: %s" % problem)
            return 1
        print("setler tutarli: %d vaka" % len(data["cases"]))
        return 0

    if args.command == "measure":
        gnubg = gnubg_er.find_gnubg(args.gnubg)
        if gnubg is None:
            print("gnubg bulunamadi", file=sys.stderr)
            return 2
        data = load_sets(args.sets)
        problems = verify_sets(data)
        if problems:
            for problem in problems:
                print("SORUN: %s" % problem, file=sys.stderr)
            return 1
        set_names = tuple(args.set_names) if args.set_names else PRIMARY_SETS
        record = measure_model(
            args.model,
            data,
            gnubg=gnubg,
            plies=args.plies,
            criterion=args.criterion,
            set_names=set_names,
            progress=not args.quiet,
        )
        append_benchmark(record, args.out)
        records = load_benchmarks(args.out)
        write_bench_markdown(records, args.markdown)
        for name, summary in record["sets"].items():
            print(
                "%-8s n=%d ER=%.4f medyan=%.4f maks=%.4f eslesme=%.1f%%"
                % (
                    name,
                    summary["count"],
                    summary["mean"],
                    summary["median"],
                    summary["max"],
                    100.0 * summary["exactMatchRate"],
                )
            )
        return 0

    if args.command == "inventory":
        benchmarks = load_benchmarks(args.benchmarks)
        inventory = build_inventory(benchmarks=benchmarks)
        json_path, md_path = write_inventory(inventory, args.json, args.markdown)
        print("envanter: %s (%d dosya)" % (json_path, inventory["count"]))
        print("markdown: %s" % md_path)
        if inventory["alarm"]:
            print("ALARM: %d model diskte yok" % len(inventory["missing"]))
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
