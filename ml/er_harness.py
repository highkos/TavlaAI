#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 6 Aşama A — yeniden üretilebilir ER ölçüm hattı ve dondurulmuş referans küme.

Faz 6 v3 Bölüm 12.1 (Test 41a–48) ve Bölüm 15 (Aşama A) bu modülü ister:

* **41a** — Faz 5 `stage_d_er.md` değeri (0,1941) 50 pozisyonluk alt kümede
  ±0,01 toleransla yeniden üretilir.
* **41b** — 200 pozisyonluk referans kümede ölçülen ER raporlanır (eşik yok).
* **41c** — `OutcomeDistribution` kodlaması (dışlayıcı/kümülatif) belirlenir.
* **41d** — `resultType`'ın `winner`'ı içerip içermediği belirlenir.
* **41e** — 100 oyunluk self-play çıktısı `du` ile ölçülür; KB/karar raporlanır.
* **42** — aynı seed + aynı model → aynı ER (bit düzeyinde, CPU).
* **43** — gnubg yoksa sıfır olmayan çıkış kodu, uydurma değer yok.
* **44** — 200 pozisyonluk küme hash'i sabit; CAL/VAL-ER/TEST-ER ayrık.
* **45** — küme temas/yarış/bearoff/bar/kapalı tahta fazlarının her birinden ≥ 20.
* **46** — 200 pozisyonda ER standart hatası hesaplanır ve raporlanır.
* **47** — `PHASES.md` §7 tablosundaki sayılar ölçümle uyuşur.
* **48** — gnubg sürümü + ply + mod rapora yazılır.

Tasarım kararları
-----------------
* **Tek doğruluk kaynağı korunur.** Vektörleştirme C#'tadır; bu modül Faz 4'te
  yazılmış `ml/gnubg_er.py` vektörleştiricisini **olduğu gibi** kullanır, yenisini
  yazmaz (Kural 3).
* **Küme dondurulur.** `ml/artifacts/reference_corpus_v1.json` içeriğinin SHA-256
  özeti dosyaya yazılır; içerik değişirse Test 44 kırılır.
* **Sızıntı yok.** CAL / VAL-ER / TEST-ER bölünmesi pozisyon adına göre
  deterministiktir ve üç küme ayrıktır (Kural 10, Bölüm 6.4).
* **Uydurma sayı yok.** gnubg yoksa ölçüm yapılmaz, sıfır olmayan çıkış kodu döner.

Kullanım::

    python ml/er_harness.py build-corpus
    python ml/er_harness.py verify-corpus
    python ml/er_harness.py measure --model ml/artifacts/model_stage_d_v10.onnx --split all
    python ml/er_harness.py legacy --model ml/artifacts/model_stage_d_v10.onnx --limit 50
    python ml/er_harness.py data-volume --shards ml/runs/stage_d/shards/it10
    python ml/er_harness.py baseline --model ml/artifacts/model_stage_d_v10.onnx
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import er_power  # noqa: E402  (yol kurulumundan sonra)
import gnubg_er  # noqa: E402
import gnubg_hint  # noqa: E402
import proof_corpus  # noqa: E402
import tools.reference_gen as refgen  # noqa: E402

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------

CORPUS_VERSION = 1
CORPUS_PATH = ML_DIR / "artifacts" / "reference_corpus_v1.json"
LEGACY_CASES = REPO_ROOT / "Backgammon.Tests" / "ReferenceData" / "reference_positions.json"
BASELINE_REPORT = ML_DIR / "artifacts" / "stage_f_baseline.md"

#: Küme üretim tohumu. Değişirse küme değişir ve Test 44 kırılır — **bilinçli**.
CORPUS_SEED = 20261114

#: Toplam pozisyon sayısı (Bölüm 12.1, Test 44).
TARGET_POSITIONS = 200

#: Faz başına en az pozisyon (Bölüm 12.1, Test 45).
PHASE_MINIMUM = 20

#: Faz başına hedef (5 × 40 = 200).
PHASE_TARGET = 40

#: Bölünme oranları (Bölüm 6.4). Toplam 200 → 60 / 70 / 70.
SPLIT_RATIOS = (("cal", 0.30), ("val", 0.35), ("test", 0.35))

#: Faz adları (sıra raporlamada kullanılır).
PHASES = ("contact", "race", "bearoff", "bar", "closed")

PHASE_LABELS = {
    "contact": "temas",
    "race": "yarış",
    "bearoff": "bearoff",
    "bar": "bar",
    "closed": "kapalı tahta",
}

#: Faz 5 `stage_d_er.md` referans değeri (50 kullanılabilir pozisyon, 2-ply).
STAGE_D_ER_MEAN = 0.1941
STAGE_D_ER_TOLERANCE = 0.01
STAGE_D_USABLE = 50

#: Test 46: hedef standart hata (pilot ölçüm sonrası kesinleşir).
TARGET_STANDARD_ERROR = 0.005

#: Kanıt korpusu (Faz 7 Bölüm 4.5) — iterasyon kümesinden **ayrı** örneklem.
PROOF_CORPUS_PATH = proof_corpus.PROOF_CORPUS_PATH

#: Hakem türleri (Faz 7 Bölüm 4.2). ``eval`` <= 2-ply, ``hint`` >= 3-ply.
REFEREES = ("eval", "hint")

#: Her ER raporunun taşımak zorunda olduğu hakem alanları (Test 90).
REFEREE_REPORT_FIELDS = ("command", "column", "plies", "prob")

#: ``eval`` çıktısında okunan sütun adları (F6-32: asla ``"3"`` yok).
EVAL_COLUMNS = ("static", "1", "2")

#: ``hint`` çıktısında okunan sütun adı.
HINT_COLUMN = "hint"

#: ``eval`` için olasılık/equity alanı.
EVAL_PROB_FIELD = "equity"

#: ``hint`` için olasılık/equity alanı.
HINT_PROB_FIELD = "cubelessEquity"

#: `resultType` alanının `winner`'ı içerip içermediği (Test 41d).
#: Kaynak: `Backgammon.Core/Enums.cs` `GameResultType` = {None=0, Single=1, Gammon=2,
#: Backgammon=3} ve `Backgammon.SelfPlay/SelfPlayRunner.cs` L132-134 `game.Winner` ile
#: `game.ResultType`'ı **ayrı** alanlara yazar. Yani resultType winner'ı **içermez**.
RESULT_TYPE_CONTAINS_WINNER = False

#: `OutcomeDistribution` kodlaması (Test 41c).
#: Kaynak: `Backgammon.Core/Match/OutcomeDistribution.cs` — `Win` = P(en az tek kazanır),
#: `WinGammon` = P(en az mars kazanır), `WinBackgammon` = P(arka arkaya kazanır);
#: `Lose = 1 - Win` türetilir. Bu **kümülatif** kodlamadır (gnubg geleneği).
OUTCOME_ENCODING = "cumulative"


# ----------------------------------------------------------------------
# Faz sınıflandırması
# ----------------------------------------------------------------------


def _home_points(player: int) -> range:
    """Oyuncunun ev haneleri (1 = beyaz 19..24, -1 = siyah 1..6)."""
    return range(19, 25) if player > 0 else range(1, 7)


def is_closed_home(board: Sequence[int], player: int) -> bool:
    """Oyuncunun evi tamamen kapalı mı (her hanede en az 2 taş)."""
    return all(int(board[p]) * player >= 2 for p in _home_points(player))


def classify_phase(board: Sequence[int], turn: int) -> str:
    """Pozisyonu beş fazdan birine atar (Bölüm 12.1, Test 45).

    Sıra önemlidir: bar > bearoff > kapalı tahta > yarış > temas.
    """
    if int(board[0]) > 0 or int(board[25]) < 0:
        return "bar"
    if refgen.is_bear_off_mode(board, turn):
        return "bearoff"
    if is_closed_home(board, -turn):
        return "closed"
    if not gnubg_er.is_contact(board):
        return "race"
    return "contact"


# ----------------------------------------------------------------------
# Küme üretimi (deterministik)
# ----------------------------------------------------------------------


def _candidate_positions(seed: int, count: int, max_plies: int = 60) -> list[tuple]:
    """Tohumlu rastgele oyunlardan aday pozisyon toplar.

    Her aday ``(board, turn, dice, whiteOff, blackOff)`` beşlisidir. Yalnızca
    **en az 2 yasal afterstate** olan pozisyonlar alınır: tek adaylı pozisyonda
    ER tanım gereği 0'dır ve ölçüm gücü katmaz.
    """
    rng = random.Random(seed)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = list(refgen.START_BOARD)
        white_off = black_off = 0
        turn = 1 if rng.random() < 0.5 else -1

        for _ in range(max_plies):
            d1 = rng.randint(1, 6)
            d2 = rng.randint(1, 6)
            dice = [d1, d1, d1, d1] if d1 == d2 else [d1, d2]

            max_steps, states = refgen.legal_after_states(
                board, turn, dice, white_off, black_off
            )
            # `max_steps > 0` iken `states` boş olabilir: büyük zar kuralı
            # filtresi hiçbir sonucu eşleştiremezse küme boşalır. Bu durumda
            # hamle yokmuş gibi davranılır.
            if max_steps == 0 or not states:
                turn = -turn
                continue

            if len(states) >= 2 and rng.random() < 0.35:
                out.append((list(board), turn, sorted(dice), white_off, black_off))
                if len(out) >= count:
                    return out

            nb, white_off, black_off = rng.choice(sorted(states))
            board = list(nb)
            if white_off == refgen.PIECES or black_off == refgen.PIECES:
                break
            turn = -turn

    return out


def _random_dice(rng: random.Random) -> list[int]:
    """Rastgele zar; çift zarda dört aynı değer (Faz 1 sözleşmesi)."""
    d1 = rng.randint(1, 6)
    d2 = rng.randint(1, 6)
    return [d1, d1, d1, d1] if d1 == d2 else sorted([d1, d2])


def _spread(
    rng: random.Random,
    board: list[int],
    points: Sequence[int],
    sign: int,
    total: int,
) -> None:
    """``total`` taşı ``points`` üzerine 1..5'lik gruplar hâlinde dağıtır."""
    order = list(points)
    rng.shuffle(order)
    remaining = total
    for index, point in enumerate(order):
        if remaining == 0:
            break
        left = len(order) - index - 1
        low = max(1, remaining - 5 * left)
        high = min(5, remaining)
        if low > high:
            low = high
        take = rng.randint(low, high)
        board[point] = sign * take
        remaining -= take
    if remaining:
        board[order[0]] += sign * remaining


def _closed_positions(seed: int, count: int) -> list[tuple]:
    """Rakibin evi tamamen kapalı pozisyonlar (``closed`` fazı).

    Rastgele oyun bu fazı neredeyse hiç üretmez (kapalı ev nadirdir), bu yüzden
    aile parametrik olarak kurulur: siyahın 1..6 haneleri 2'şer taşla kapalı,
    kalan 3 siyah taşı 8..18 arasında; beyazın 15 taşı 7..24 arasında dağıtılır
    ve **en az bir beyaz taş 7 numarada** tutularak temas garanti edilir.
    """
    rng = random.Random(seed ^ 0xC105ED)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        for point in range(1, 7):
            board[point] = -2
        spot = rng.randint(8, 18)
        board[spot] = -3

        free = [p for p in range(7, 25) if p != spot]
        rng.shuffle(free)
        remaining = 14  # 1 taş 7 numaraya ayrıldı
        for point in free:
            if remaining == 0:
                break
            take = rng.randint(1, min(5, remaining))
            board[point] = take
            remaining -= take
        if remaining:
            board[free[0]] += remaining
        board[7] = board[7] + 1 if board[7] else 1

        if classify_phase(board, 1) != "closed":
            continue
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _race_positions(seed: int, count: int) -> list[tuple]:
    """Temassız ama bearoff olmayan pozisyonlar (``race`` fazı).

    Siyah 1..8, beyaz 11..18 aralığına dağıtılır: siyahın en ileri taşı
    beyazın en geri taşının gerisinde kalır (temas yok), beyazın taşları evde
    olmadığı için bearoff da değildir.
    """
    rng = random.Random(seed ^ 0x7ACE01)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        _spread(rng, board, range(1, 9), -1, 15)
        _spread(rng, board, range(11, 19), 1, 15)
        if classify_phase(board, 1) != "race":
            continue
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _bearoff_positions(seed: int, count: int) -> list[tuple]:
    """Beyazın tüm taşları evinde olan pozisyonlar (``bearoff`` fazı).

    Rastgele oyun bearoff'a nadiren ulaşır; aile parametrik kurulur. Siyah
    1..12 aralığına dağıtılır, böylece beyazın evi (19..24) yalnız beyazındır.
    """
    rng = random.Random(seed ^ 0xBEAF0F)
    out: list[tuple] = []
    guard = 0
    while len(out) < count and guard < count * 200:
        guard += 1
        board = [0] * 26
        _spread(rng, board, range(19, 25), 1, 15)
        _spread(rng, board, range(1, 13), -1, 15)
        if classify_phase(board, 1) != "bearoff":
            continue
        out.append((board, 1, _random_dice(rng), 0, 0))
    return out


def _case_from_position(name: str, position: tuple) -> dict[str, Any]:
    """Bir pozisyondan küme kaydı üretir (afterstate listesi dahil)."""
    board, turn, dice, white_off, black_off = position
    max_steps, states = refgen.legal_after_states(board, turn, dice, white_off, black_off)
    return {
        "name": name,
        "phase": classify_phase(board, turn),
        "board": list(board),
        "turn": int(turn),
        "dice": [int(d) for d in dice],
        "whiteOff": int(white_off),
        "blackOff": int(black_off),
        "maxSteps": int(max_steps),
        "afterStates": [
            {"board": list(b), "whiteOff": int(w), "blackOff": int(k)}
            for (b, w, k) in sorted(states)
        ],
    }


def build_corpus(seed: int = CORPUS_SEED, target: int = TARGET_POSITIONS) -> dict[str, Any]:
    """Dondurulmuş referans kümeyi deterministik olarak üretir.

    Faz dengesi: her fazdan en az :data:`PHASE_MINIMUM`, hedef :data:`PHASE_TARGET`.
    Faz hedefleri dolmazsa kalan pozisyonlar en çok aday veren fazlardan tamamlanır
    ve bu durum ``notes`` alanına yazılır.
    """
    # Faz başına hedefin biraz üstünde aday topla, sonra dengele.
    pool = _candidate_positions(seed, target * 3)
    # Rastgele oyunun üretemediği fazları (kapalı tahta, yarış, bearoff)
    # parametrik ailelerle besle.
    pool = (
        _closed_positions(seed, PHASE_TARGET * 2)
        + _race_positions(seed, PHASE_TARGET * 2)
        + _bearoff_positions(seed, PHASE_TARGET * 2)
        + pool
    )

    buckets: dict[str, list[tuple]] = {phase: [] for phase in PHASES}
    for position in pool:
        phase = classify_phase(position[0], position[1])
        if len(buckets[phase]) < PHASE_TARGET:
            buckets[phase].append(position)

    selected: list[tuple] = []
    for phase in PHASES:
        selected.extend(buckets[phase])

    notes: list[str] = []
    used = {id(p) for p in selected}
    leftovers = [p for p in pool if id(p) not in used]

    # Tek adaylı pozisyonlar ER ölçümüne güç katmaz (ER tanım gereği 0) ve
    # `is_usable` bunları dışlar; kümede tutulmazlar. Aynı tahta da tekrar
    # sayılmaz: sıra veya zar farklı olsa bile aynı tahta sızıntı sayılır
    # (Kural 10).
    seen: set[tuple] = set()
    cases: list[dict[str, Any]] = []

    def _accept(position: tuple) -> bool:
        case = _case_from_position("f6-%03d" % len(cases), position)
        if len(case["afterStates"]) < 2:
            return False
        key = tuple(int(v) for v in case["board"])
        if key in seen:
            return False
        seen.add(key)
        cases.append(case)
        return True

    for position in selected:
        _accept(position)

    cursor = 0
    while len(cases) < target and cursor < len(leftovers):
        _accept(leftovers[cursor])
        cursor += 1

    if cursor:
        notes.append(
            "faz hedefleri dolmadı; %d pozisyon artan adaylardan tamamlandı" % cursor
        )

    counts = {phase: 0 for phase in PHASES}
    for case in cases:
        counts[case["phase"]] += 1

    short = {phase: n for phase, n in counts.items() if n < PHASE_MINIMUM}
    if short:
        notes.append("faz minimumu sağlanamadı: %r" % short)

    corpus = {
        "corpusVersion": CORPUS_VERSION,
        "generator": "ml/er_harness.py",
        "seed": seed,
        "targetPositions": target,
        "phaseMinimum": PHASE_MINIMUM,
        "phaseCounts": counts,
        "notes": notes,
        "cases": cases,
    }
    corpus["digest"] = corpus_digest(corpus)
    corpus["splits"] = assign_splits(cases, seed)
    return corpus


# ----------------------------------------------------------------------
# Özet ve bölünme
# ----------------------------------------------------------------------


def _canonical_cases(cases: Sequence[dict[str, Any]]) -> str:
    """Küme içeriğinin kanonik (sıra bağımsız) metni."""
    payload = [
        {
            "name": case["name"],
            "phase": case["phase"],
            "board": [int(v) for v in case["board"]],
            "turn": int(case["turn"]),
            "dice": [int(d) for d in case["dice"]],
            "whiteOff": int(case["whiteOff"]),
            "blackOff": int(case["blackOff"]),
            "afterStates": [
                {
                    "board": [int(v) for v in a["board"]],
                    "whiteOff": int(a["whiteOff"]),
                    "blackOff": int(a["blackOff"]),
                }
                for a in case["afterStates"]
            ],
        }
        for case in cases
    ]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def corpus_digest(corpus: dict[str, Any]) -> str:
    """Küme içeriğinin SHA-256 özeti (Test 44)."""
    return hashlib.sha256(_canonical_cases(corpus["cases"]).encode("utf-8")).hexdigest()


def assign_splits(cases: Sequence[dict[str, Any]], seed: int) -> dict[str, list[str]]:
    """CAL / VAL-ER / TEST-ER bölünmesi — faz katmanlı, deterministik, ayrık.

    Her fazın üyeleri tohumla karıştırılır, sonra oranlara göre bölünür. Böylece
    her bölünme her fazdan pozisyon içerir ve üç küme **ayrıktır** (Kural 10).
    """
    rng = random.Random(seed ^ 0x5F6A3C)
    by_phase: dict[str, list[str]] = {phase: [] for phase in PHASES}
    for case in cases:
        by_phase[case["phase"]].append(case["name"])

    splits: dict[str, list[str]] = {name: [] for name, _ in SPLIT_RATIOS}
    for phase in PHASES:
        names = sorted(by_phase[phase])
        rng.shuffle(names)
        total = len(names)
        cursor = 0
        for index, (split_name, ratio) in enumerate(SPLIT_RATIOS):
            if index == len(SPLIT_RATIOS) - 1:
                take = total - cursor
            else:
                take = int(round(total * ratio))
            splits[split_name].extend(names[cursor:cursor + take])
            cursor += take

    for split_name in splits:
        splits[split_name].sort()
    return splits


def split_membership(corpus: dict[str, Any]) -> dict[str, str]:
    """Pozisyon adı → bölünme adı eşlemesi."""
    out: dict[str, str] = {}
    for split_name, names in corpus["splits"].items():
        for name in names:
            out[name] = split_name
    return out


def select_cases(corpus: dict[str, Any], split: str) -> list[dict[str, Any]]:
    """Bölünmeye göre küme vakalarını döndürür (``all`` = tümü)."""
    if split == "all":
        return list(corpus["cases"])
    if split not in corpus["splits"]:
        raise ValueError("bilinmeyen bölünme: %r" % split)
    wanted = set(corpus["splits"][split])
    return [case for case in corpus["cases"] if case["name"] in wanted]


# ----------------------------------------------------------------------
# Küme G/Ç
# ----------------------------------------------------------------------


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    """Dondurulmuş kümeyi okur."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_corpus(corpus: dict[str, Any], path: Path = CORPUS_PATH) -> None:
    """Kümeyi yazar (LF, UTF-8, sonunda yeni satır)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(corpus, indent=1, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def verify_corpus(corpus: dict[str, Any]) -> list[str]:
    """Küme tutarlılık denetimleri; ihlal listesi döner (boş = sağlıklı)."""
    problems: list[str] = []

    if len(corpus["cases"]) != corpus.get("targetPositions", TARGET_POSITIONS):
        problems.append(
            "pozisyon sayısı %d, beklenen %d"
            % (len(corpus["cases"]), corpus.get("targetPositions", TARGET_POSITIONS))
        )

    digest = corpus_digest(corpus)
    if digest != corpus.get("digest"):
        problems.append("özet uyuşmuyor: %s != %s" % (digest, corpus.get("digest")))

    counts = {phase: 0 for phase in PHASES}
    for case in corpus["cases"]:
        counts[case["phase"]] = counts.get(case["phase"], 0) + 1
    for phase, n in counts.items():
        if n < PHASE_MINIMUM:
            problems.append("faz %s: %d < %d" % (phase, n, PHASE_MINIMUM))

    names = [case["name"] for case in corpus["cases"]]
    if len(set(names)) != len(names):
        problems.append("pozisyon adları benzersiz değil")

    membership = split_membership(corpus)
    if set(membership) != set(names):
        problems.append("bölünme kapsamı küme ile uyuşmuyor")
    for split_name, split_names in corpus["splits"].items():
        if len(set(split_names)) != len(split_names):
            problems.append("bölünme %s içinde tekrar var" % split_name)
    total_split = sum(len(v) for v in corpus["splits"].values())
    if total_split != len(names):
        problems.append("bölünmeler toplamı %d != %d" % (total_split, len(names)))

    for case in corpus["cases"]:
        if len(case["afterStates"]) < 2:
            problems.append("%s: afterstate < 2" % case["name"])
        white, black = gnubg_er.case_piece_counts(case)
        if white != gnubg_er.PIECES_PER_PLAYER or black != gnubg_er.PIECES_PER_PLAYER:
            problems.append("%s: taş sayısı %d/%d" % (case["name"], white, black))

    return problems


# ----------------------------------------------------------------------
# Ölçüm
# ----------------------------------------------------------------------


@dataclass
class SplitMeasurement:
    """Bir bölünmenin ER ölçümü."""

    split: str
    count: int
    mean: float
    median: float
    maximum: float
    exact_match_rate: float
    standard_error: float
    standard_deviation: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "count": self.count,
            "mean": round(self.mean, 6),
            "median": round(self.median, 6),
            "max": round(self.maximum, 6),
            "exactMatchRate": round(self.exact_match_rate, 6),
            "standardError": round(self.standard_error, 6),
            "standardDeviation": round(self.standard_deviation, 6),
        }


def statistical_power(losses: Sequence[float], target_se: float = TARGET_STANDARD_ERROR) -> dict[str, float]:
    """ER standart hatası ve hedef SE için gereken pozisyon sayısı (Test 46).

    ``SE = s / sqrt(n)``; ``n_gerekli = (s / hedef_SE)^2``. Örneklem standart
    sapması ``n-1`` ile hesaplanır (örneklem kestirimi).
    """
    n = len(losses)
    if n < 2:
        return {
            "count": float(n),
            "standardDeviation": 0.0,
            "standardError": 0.0,
            "requiredCount": 0.0,
        }
    mean = sum(losses) / n
    variance = sum((x - mean) ** 2 for x in losses) / (n - 1)
    sd = math.sqrt(variance)
    se = sd / math.sqrt(n)
    required = (sd / target_se) ** 2 if target_se > 0 else 0.0
    return {
        "count": float(n),
        "standardDeviation": sd,
        "standardError": se,
        "requiredCount": required,
    }


def measure_split(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    split: str,
    gnubg: Path,
    plies: int = gnubg_er.DEFAULT_PLIES,
    timeout: int = gnubg_er.DEFAULT_TIMEOUT,
    progress: bool = True,
    referee: str = "eval",
) -> tuple[SplitMeasurement, list[gnubg_er.PositionResult]]:
    """Bir bölünmeyi ölçer ve özetle birlikte ham sonuçları döndürür.

    ``referee = "hint"`` iken derin hakem (:mod:`gnubg_hint`) kullanılır; bu yol
    ``PositionResult`` yerine ``HintPositionResult`` üretir ve **ayrı** bir
    fonksiyondan (:func:`measure_split_hint`) geçer.
    """
    if referee != "eval":
        raise ValueError("measure_split yalnızca 'eval' hakemini destekler: %r" % (referee,))
    results, _skipped = gnubg_er.measure(
        model_path,
        cases,
        gnubg=gnubg,
        plies=plies,
        timeout=timeout,
        progress=progress,
    )
    stats = gnubg_er.summarize(results)
    losses = [r.equity_loss for r in results]
    power = statistical_power(losses)
    measurement = SplitMeasurement(
        split=split,
        count=int(stats["count"]),
        mean=float(stats["mean"]),
        median=float(stats["median"]),
        maximum=float(stats["max"]),
        exact_match_rate=float(stats["exactMatchRate"]),
        standard_error=float(power["standardError"]),
        standard_deviation=float(power["standardDeviation"]),
    )
    return measurement, results


def referee_contract(report: dict[str, Any]) -> list[str]:
    """Bir ER raporunun hakem derinliği sözleşmesini denetler (Test 90).

    Her rapor **hangi komutun**, **hangi sütunun**, **hangi derinliğin** ve
    **hangi olasılık alanının** kullanıldığını yazmak zorundadır. Faz 6'da bu
    alanlar yoktu ve ``--plies 3`` sessizce 0-ply okudu (F6-32); hata ancak
    iki dosya bayt bayt aynı çıkınca fark edildi.

    İhlal listesi döner (boş = sözleşmeye uygun).
    """
    problems: list[str] = []
    for name in REFEREE_REPORT_FIELDS:
        if name not in report:
            problems.append("eksik alan: %s" % name)
    if problems:
        return problems

    command = report["command"]
    column = report["column"]
    plies = report["plies"]
    prob = report["prob"]

    if command not in REFEREES:
        problems.append("bilinmeyen komut: %r" % (command,))
        return problems
    if not isinstance(plies, int) or isinstance(plies, bool) or plies < 0:
        problems.append("plies negatif olmayan tam sayi olmali: %r" % (plies,))
        return problems

    if command == "eval":
        if plies > gnubg_er.MAX_EVAL_PLIES:
            problems.append(
                "eval %d-ply uretemez (en fazla %d)" % (plies, gnubg_er.MAX_EVAL_PLIES)
            )
        expected = "static" if plies == 0 else str(plies)
        if column != expected:
            problems.append("eval sutunu %r olmali, %r verilmis" % (expected, column))
        if column not in EVAL_COLUMNS:
            problems.append("eval sutunu bilinmiyor: %r" % (column,))
        if prob != EVAL_PROB_FIELD:
            problems.append("eval olasilik alani %r olmali, %r verilmis" % (EVAL_PROB_FIELD, prob))
    else:
        if plies < gnubg_hint.HINT_REFEREE_MIN_PLIES:
            problems.append(
                "hint %d-ply hakem olamaz (en az %d)"
                % (plies, gnubg_hint.HINT_REFEREE_MIN_PLIES)
            )
        if plies > gnubg_hint.HINT_MAX_PLIES:
            problems.append(
                "hint %d-ply uretemez (en fazla %d)" % (plies, gnubg_hint.HINT_MAX_PLIES)
            )
        if column != HINT_COLUMN:
            problems.append("hint sutunu %r olmali, %r verilmis" % (HINT_COLUMN, column))
        if prob != HINT_PROB_FIELD:
            problems.append(
                "hint olasilik alani %r olmali, %r verilmis" % (HINT_PROB_FIELD, prob)
            )
    return problems


def referee_fields(referee: str, plies: int) -> dict[str, Any]:
    """Bir hakem/derinlik çifti için sözleşme alanlarını üretir (Test 90)."""
    if referee not in REFEREES:
        raise ValueError("bilinmeyen hakem: %r" % (referee,))
    if referee == "eval":
        if plies > gnubg_er.MAX_EVAL_PLIES:
            raise ValueError("eval %d-ply uretemez" % plies)
        return {
            "command": "eval",
            "column": "static" if plies == 0 else str(plies),
            "plies": int(plies),
            "prob": EVAL_PROB_FIELD,
        }
    gnubg_hint.assert_referee_choice(plies, "hint")
    return {
        "command": "hint",
        "column": HINT_COLUMN,
        "plies": int(plies),
        "prob": HINT_PROB_FIELD,
    }


def measure_split_hint(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    split: str,
    gnubg: Path,
    plies: int = gnubg_hint.HINT_REFEREE_MIN_PLIES,
    timeout: int = gnubg_hint.DEFAULT_HINT_TIMEOUT,
    progress: Any = None,
) -> dict[str, Any]:
    """Derin (``hint``) hakemle bir bölünmeyi ölçer (Faz 7 Bölüm 4.2).

    Dönen sözlük :func:`gnubg_hint.measure` raporudur; ``split`` alanı eklenir.
    ``methodNote`` alanı **korunur**: 2-ply (``eval``) ile 3-ply (``hint``)
    arasındaki geçiş bir **yöntem değişikliğidir** (F7-04).
    """
    gnubg_hint.assert_referee_choice(plies, "hint")
    report = gnubg_hint.measure(
        model_path,
        cases,
        gnubg=gnubg,
        plies=plies,
        timeout=timeout,
        progress=progress,
    )
    report["split"] = split
    report.update(referee_fields("hint", plies))
    return report


# ----------------------------------------------------------------------
# Veri hacmi (Test 41e)
# ----------------------------------------------------------------------


def measure_data_volume(shard_paths: Iterable[Path]) -> dict[str, Any]:
    """Shard'lardan bayt/karar ölçer (Test 41e).

    Ham (açılmış) ve sıkıştırılmış boyut ayrı raporlanır; ``du`` ile disk
    kullanımı da eklenir. Hiç shard yoksa ``measured = False`` döner — uydurma
    değer yazılmaz.
    """
    import gzip

    import shards

    total_raw = 0
    total_disk = 0
    total_games = 0
    total_decisions = 0
    files = 0

    for path in shard_paths:
        path = Path(path)
        if not path.is_file():
            continue
        files += 1
        total_disk += path.stat().st_size
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as handle:
                raw = handle.read()
        else:
            raw = path.read_bytes()
        total_raw += len(raw)
        _header, games = shards.read_shard_bytes(raw)
        total_games += len(games)
        total_decisions += sum(len(game.decisions) for game in games)

    if files == 0 or total_decisions == 0:
        return {
            "measured": False,
            "files": files,
            "games": total_games,
            "decisions": total_decisions,
        }

    return {
        "measured": True,
        "files": files,
        "games": total_games,
        "decisions": total_decisions,
        "rawBytes": total_raw,
        "diskBytes": total_disk,
        "bytesPerDecisionRaw": total_raw / total_decisions,
        "bytesPerDecisionDisk": total_disk / total_decisions,
        "decisionsPerGame": total_decisions / total_games if total_games else 0.0,
    }


def collect_shards(directory: Path) -> list[Path]:
    """Bir dizindeki tüm shard dosyalarını (``.bgsp`` / ``.bgsp.gz``) toplar."""
    directory = Path(directory)
    if directory.is_file():
        return [directory]
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.rglob("*") if p.suffix in (".bgsp", ".gz") and p.is_file()
    )


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _fmt(value: float, digits: int = 4) -> str:
    return ("%." + str(digits) + "f") % value


def build_baseline_markdown(
    *,
    model_path: Path,
    gnubg_path: Path | None,
    gnubg_version: str,
    plies: int,
    legacy: SplitMeasurement | None,
    legacy_skipped: Sequence[str],
    corpus: dict[str, Any] | None,
    measurements: Sequence[SplitMeasurement],
    data_volume: dict[str, Any] | None,
) -> str:
    """`ml/artifacts/stage_f_baseline.md` içeriğini üretir."""
    lines: list[str] = []
    add = lines.append

    add("# Faz 6 Aşama A — ölçüm hattı ve taban kilidi")
    add("")
    add("Bu rapor `ml/er_harness.py` tarafından **üretilir**; hiçbir sayı elle")
    add("yazılmamıştır. Faz 6 v3 Bölüm 12.1 (Test 41a–48) ve Bölüm 15 (Aşama A)")
    add("kabul kriterlerini karşılar.")
    add("")

    add("## Ölçüm koşulları (Test 48)")
    add("")
    add("| Alan | Değer |")
    add("| --- | --- |")
    add("| Model | `%s` |" % model_path.as_posix())
    add("| gnubg | `%s` |" % (gnubg_path.as_posix() if gnubg_path else "(bulunamadı)"))
    add("| gnubg sürümü | %s |" % (gnubg_version or "(okunamadı)"))
    add("| gnubg değerlendirme | %d-ply, cubeless, money game |" % plies)
    add("| Hamle seçimi | politika başı argmax (C# `ArgMaxCandidate` ile aynı) |")
    add("| ER tanımı | `E_best − E_model`, aynı değerlendirici |")
    add("")

    add("## 41a — Faz 5 değerinin yeniden üretimi")
    add("")
    if legacy is None:
        add("**Ölçülmedi** (gnubg bulunamadı veya eski vaka dosyası yok).")
    else:
        delta = legacy.mean - STAGE_D_ER_MEAN
        verdict = "✅ yeniden üretildi" if abs(delta) <= STAGE_D_ER_TOLERANCE else "❌ sapma"
        add("| Alan | Değer |")
        add("| --- | --- |")
        add("| Faz 5 `stage_d_er.md` | %s |" % _fmt(STAGE_D_ER_MEAN))
        add("| Bu ölçüm (%d pozisyon) | **%s** |" % (legacy.count, _fmt(legacy.mean)))
        add("| Fark | %+.4f |" % delta)
        add("| Tolerans | ±%s |" % _fmt(STAGE_D_ER_TOLERANCE))
        add("| Sonuç | %s |" % verdict)
        add("")
        if legacy_skipped:
            add("Dışarıda kalan vakalar: %s" % ", ".join("`%s`" % n for n in legacy_skipped))
            add("")

    add("## 41b — 200 pozisyonluk referans küme")
    add("")
    if corpus is None:
        add("**Küme yok.** `python ml/er_harness.py build-corpus` çalıştırılmalı.")
    else:
        add("| Alan | Değer |")
        add("| --- | --- |")
        add("| Küme sürümü | v%d |" % corpus["corpusVersion"])
        add("| Pozisyon | %d |" % len(corpus["cases"]))
        add("| Tohum | %d |" % corpus["seed"])
        add("| SHA-256 | `%s` |" % corpus["digest"])
        add("")
        add("Faz dağılımı (Test 45):")
        add("")
        add("| Faz | Pozisyon | En az |")
        add("| --- | --- | --- |")
        for phase in PHASES:
            n = corpus["phaseCounts"].get(phase, 0)
            mark = "✅" if n >= PHASE_MINIMUM else "❌"
            add("| %s (`%s`) | %d | %d %s |" % (PHASE_LABELS[phase], phase, n, PHASE_MINIMUM, mark))
        add("")
        add("Bölünme (Test 44, Kural 10):")
        add("")
        add("| Bölünme | Pozisyon |")
        add("| --- | --- |")
        for split_name, _ratio in SPLIT_RATIOS:
            add("| `%s` | %d |" % (split_name, len(corpus["splits"][split_name])))
        add("")
        if corpus.get("notes"):
            add("Notlar: %s" % "; ".join(corpus["notes"]))
            add("")

    if measurements:
        add("### Ölçülen ER (eşik yok — raporlanır)")
        add("")
        add("| Bölünme | Pozisyon | Ortalama ER | Medyan | Maksimum | Std hata | Std sapma | Eşleşme |")
        add("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for m in measurements:
            add(
                "| `%s` | %d | **%s** | %s | %s | %s | %s | %.1f%% |"
                % (
                    m.split,
                    m.count,
                    _fmt(m.mean),
                    _fmt(m.median),
                    _fmt(m.maximum),
                    _fmt(m.standard_error),
                    _fmt(m.standard_deviation),
                    100.0 * m.exact_match_rate,
                )
            )
        add("")
        add("## 46 — İstatistiksel güç")
        add("")
        add("| Bölünme | n | Std sapma | Std hata | Hedef SE | Gereken n |")
        add("| --- | --- | --- | --- | --- | --- |")
        for m in measurements:
            required = (
                (m.standard_deviation / TARGET_STANDARD_ERROR) ** 2
                if TARGET_STANDARD_ERROR > 0
                else 0.0
            )
            add(
                "| `%s` | %d | %s | %s | %s | %d |"
                % (
                    m.split,
                    m.count,
                    _fmt(m.standard_deviation),
                    _fmt(m.standard_error),
                    _fmt(TARGET_STANDARD_ERROR, 3),
                    int(math.ceil(required)),
                )
            )
        add("")
        add(
            "Hedef SE %s; gereken n pilot ölçümden hesaplanır (Bölüm 12.1, Test 46)."
            % _fmt(TARGET_STANDARD_ERROR, 3)
        )
        add("")

    add("## 41c — `OutcomeDistribution` kodlaması")
    add("")
    add("**Sonuç: `%s`.**" % OUTCOME_ENCODING)
    add("")
    add("`Backgammon.Core/Match/OutcomeDistribution.cs` alanları:")
    add("")
    add("* `Win` = P(en az tek kazanır) = `W + GW + BW`")
    add("* `WinGammon` = P(en az mars kazanır) = `GW + BW`")
    add("* `WinBackgammon` = `BW`")
    add("* `Lose` = `1 − Win` (türetilir)")
    add("* `LoseGammon`, `LoseBackgammon` aynı kümülatif mantıkla")
    add("")
    add("Yani sınıf **kümülatif** (gnubg geleneği) kodlama kullanır. Faz 6'nın")
    add("`FromProbabilities` metodu **dışlayıcı** girdi alır ve sınıf içinde bu")
    add("kodlamaya dönüştürür (Bölüm 5.1, Bölüm 5.5).")
    add("")

    add("## 41d — `resultType` `winner`'ı içeriyor mu?")
    add("")
    add("**Sonuç: %s.**" % ("EVET" if RESULT_TYPE_CONTAINS_WINNER else "HAYIR"))
    add("")
    add("`Backgammon.Core/Enums.cs` `GameResultType` = `{None=0, Single=1, Gammon=2,")
    add("Backgammon=3}` — yalnızca **çarpan** bilgisini taşır. `Backgammon.SelfPlay/")
    add("SelfPlayRunner.cs` L132–134 `game.Winner` ve `game.ResultType`'ı **ayrı**")
    add("alanlara yazar. Bu yüzden 6 sınıflı hedef türetilirken `winner` ayrı alandan")
    add("okunur (Bölüm 7.1).")
    add("")

    add("## 41e — Veri hacmi (ölçülmüş)")
    add("")
    if not data_volume or not data_volume.get("measured"):
        add("**Ölçülmedi** — shard bulunamadı. Uydurma değer yazılmadı.")
    else:
        add("| Alan | Değer |")
        add("| --- | --- |")
        add("| Shard dosyası | %d |" % data_volume["files"])
        add("| Oyun | %d |" % data_volume["games"])
        add("| Karar | %d |" % data_volume["decisions"])
        add("| Karar/oyun | %s |" % _fmt(data_volume["decisionsPerGame"], 2))
        add("| Ham bayt/karar | **%s** |" % _fmt(data_volume["bytesPerDecisionRaw"], 1))
        add("| Disk bayt/karar (gzip) | **%s** |" % _fmt(data_volume["bytesPerDecisionDisk"], 1))
        add("")
        add(
            "Faz 6 v3 Bölüm 7.4, v1'deki \"11,5 KB/karar\" iddiasını kaldırmıştı; "
            "ölçülen değer yukarıdadır."
        )
    add("")

    add("## 47 — `PHASES.md` §7 taban kilidi")
    add("")
    add("| Ölçüm | `PHASES.md` §7 | Bu ölçüm | Durum |")
    add("| --- | --- | --- | --- |")
    if legacy is not None:
        ok = abs(legacy.mean - STAGE_D_ER_MEAN) <= STAGE_D_ER_TOLERANCE
        add(
            "| gnubg ER (2-ply) | %s | %s | %s |"
            % (_fmt(STAGE_D_ER_MEAN), _fmt(legacy.mean), "✅" if ok else "❌")
        )
    else:
        add("| gnubg ER (2-ply) | %s | ölçülmedi | ⚠️ |" % _fmt(STAGE_D_ER_MEAN))
    add("")
    add("Diğer §7 satırları (kazanma oranları, kalibrasyon, küp uyumu) bu hattın")
    add("kapsamı dışındadır; kendi artefaktlarından doğrulanır.")
    add("")

    add("## 42 / 43 — Determinizm ve gnubg zorunluluğu")
    add("")
    add("* **42:** aynı seed + aynı model + CPU → aynı ER. `ml/tests/test_er_harness.py`")
    add("  bunu iki kez ölçerek doğrular.")
    add("* **43:** gnubg yoksa `main()` sıfır olmayan çıkış kodu döner ve **hiçbir**")
    add("  sayı üretmez (`gnubg_er.main` ile aynı davranış).")
    add("")

    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _cmd_build_corpus(args: argparse.Namespace) -> int:
    corpus = build_corpus(seed=args.seed, target=args.positions)
    problems = verify_corpus(corpus)
    save_corpus(corpus, args.out)
    print("Küme: %s" % args.out)
    print("Pozisyon: %d | özet: %s" % (len(corpus["cases"]), corpus["digest"]))
    for phase in PHASES:
        print("  %-8s %d" % (phase, corpus["phaseCounts"].get(phase, 0)))
    for split_name, _ratio in SPLIT_RATIOS:
        print("  %-8s %d" % (split_name, len(corpus["splits"][split_name])))
    if problems:
        for problem in problems:
            print("SORUN: %s" % problem, file=sys.stderr)
        return 1
    return 0


def _cmd_verify_corpus(args: argparse.Namespace) -> int:
    corpus = load_corpus(args.corpus)
    problems = verify_corpus(corpus)
    if problems:
        for problem in problems:
            print("SORUN: %s" % problem, file=sys.stderr)
        return 1
    print("Küme sağlıklı: %d pozisyon, özet %s" % (len(corpus["cases"]), corpus["digest"]))
    return 0


def _load_measure_cases(args: argparse.Namespace) -> list[dict[str, Any]]:
    """``--corpus-kind`` değerine göre vakaları yükler.

    ``iteration`` — dondurulmuş 200 pozisyonluk küme (bölünmelerle).
    ``proof``     — 2 000 pozisyonluk kanıt korpusu (bölünme yok, ``all``).
    """
    if args.corpus_kind == "proof":
        if args.split not in ("all",):
            raise ValueError("kanıt korpusunda bölünme yok; --split all kullanın")
        return proof_corpus.load_cases(args.corpus)
    corpus = load_corpus(args.corpus)
    return select_cases(corpus, args.split)


def _cmd_measure(args: argparse.Namespace) -> int:
    gnubg = gnubg_er.find_gnubg(args.gnubg)
    if gnubg is None:
        print(
            "HATA: gnubg-cli bulunamadi. Kurun veya --gnubg / GNUBG_CLI ile yol verin.\n"
            "      Uydurma değer uretilmedi.",
            file=sys.stderr,
        )
        return 2
    if not args.model.is_file():
        print("HATA: model bulunamadi: %s" % args.model, file=sys.stderr)
        return 2

    if args.referee == "hint":
        if args.plies < gnubg_hint.HINT_REFEREE_MIN_PLIES:
            print(
                "HATA: 'hint' hakemi en az %d-ply ister; --plies %d verildi.\n"
                "      2-ply icin --referee eval kullanin (F7-04: hint@2 != eval@2)."
                % (gnubg_hint.HINT_REFEREE_MIN_PLIES, args.plies),
                file=sys.stderr,
            )
            return 2
        if args.plies > gnubg_hint.HINT_MAX_PLIES:
            print(
                "HATA: 'hint' hakemi en fazla %d-ply uretir; --plies %d verildi."
                % (gnubg_hint.HINT_MAX_PLIES, args.plies),
                file=sys.stderr,
            )
            return 2
    else:
        if args.plies > gnubg_er.MAX_EVAL_PLIES:
            print(
                "HATA: gnubg 'eval' komutu en fazla %d-ply uretir; --plies %d desteklenmiyor.\n"
                "      Daha derin hakem icin '--referee hint' gerekir (ASSUMPTIONS.md F6-32).\n"
                "      Uydurma değer uretilmedi."
                % (gnubg_er.MAX_EVAL_PLIES, args.plies),
                file=sys.stderr,
            )
            return 2

    try:
        cases = _load_measure_cases(args)
    except ValueError as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2

    if args.referee == "hint":
        report = measure_split_hint(
            args.model,
            cases,
            split=args.split,
            gnubg=gnubg,
            plies=args.plies,
            timeout=args.timeout,
        )
        summary = report["summary"]
        print(
            "gnubg %s | %s | hint %d-ply | %d pozisyon | ortalama ER %.4f | kapsama %.2f%%"
            % (
                gnubg_er.gnubg_version(gnubg) or "(sürüm okunamadı)",
                args.split,
                args.plies,
                summary.get("count", 0),
                summary.get("mean", 0.0),
                100.0 * summary.get("coverage", 0.0),
            )
        )
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            gnubg_hint.write_json(report, args.json)
            print("JSON: %s" % args.json)
        return 0

    measurement, results = measure_split(
        args.model,
        cases,
        split=args.split,
        gnubg=gnubg,
        plies=args.plies,
        timeout=args.timeout,
        progress=not args.quiet,
    )
    print(
        "gnubg %s | %s | %d pozisyon | ortalama ER %.4f | std hata %.4f"
        % (
            gnubg_er.gnubg_version(gnubg) or "(sürüm okunamadı)",
            args.split,
            measurement.count,
            measurement.mean,
            measurement.standard_error,
        )
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": args.model.as_posix(),
            "split": args.split,
            "plies": args.plies,
            "referee": "eval",
            "summary": measurement.to_dict(),
            "positions": [r.to_dict() for r in results],
        }
        payload.update(referee_fields("eval", args.plies))
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print("JSON: %s" % args.json)
    return 0


def _cmd_legacy(args: argparse.Namespace) -> int:
    gnubg = gnubg_er.find_gnubg(args.gnubg)
    if gnubg is None:
        print(
            "HATA: gnubg-cli bulunamadi. Kurun veya --gnubg / GNUBG_CLI ile yol verin.\n"
            "      Uydurma değer uretilmedi.",
            file=sys.stderr,
        )
        return 2
    if not args.model.is_file():
        print("HATA: model bulunamadi: %s" % args.model, file=sys.stderr)
        return 2

    cases = gnubg_er.load_cases(args.cases)
    usable, skipped = gnubg_er.split_cases(cases)
    if args.limit is not None:
        usable = usable[: args.limit]

    results, _ = gnubg_er.measure(
        args.model,
        usable,
        gnubg=gnubg,
        plies=args.plies,
        timeout=args.timeout,
        progress=not args.quiet,
    )
    stats = gnubg_er.summarize(results)
    losses = [r.equity_loss for r in results]
    power = statistical_power(losses)
    print(
        "gnubg %s | legacy | %d pozisyon | ortalama ER %.4f | std hata %.4f"
        % (
            gnubg_er.gnubg_version(gnubg) or "(sürüm okunamadı)",
            int(stats["count"]),
            stats["mean"],
            power["standardError"],
        )
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": args.model.as_posix(),
            "cases": args.cases.as_posix(),
            "plies": args.plies,
            "summary": {
                "count": int(stats["count"]),
                "mean": round(float(stats["mean"]), 6),
                "median": round(float(stats["median"]), 6),
                "max": round(float(stats["max"]), 6),
                "exactMatchRate": round(float(stats["exactMatchRate"]), 6),
                "standardError": round(float(power["standardError"]), 6),
                "standardDeviation": round(float(power["standardDeviation"]), 6),
            },
            "skipped": list(skipped),
            "positions": [r.to_dict() for r in results],
        }
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print("JSON: %s" % args.json)
    return 0


def _cmd_data_volume(args: argparse.Namespace) -> int:
    paths = collect_shards(args.shards)
    volume = measure_data_volume(paths)
    if not volume.get("measured"):
        print("HATA: shard bulunamadi: %s" % args.shards, file=sys.stderr)
        return 2
    print(
        "%d dosya | %d oyun | %d karar | %.1f bayt/karar (ham) | %.1f bayt/karar (disk)"
        % (
            volume["files"],
            volume["games"],
            volume["decisions"],
            volume["bytesPerDecisionRaw"],
            volume["bytesPerDecisionDisk"],
        )
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(volume, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print("JSON: %s" % args.json)
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    gnubg = gnubg_er.find_gnubg(args.gnubg)
    if gnubg is None:
        print(
            "HATA: gnubg-cli bulunamadi. Kurun veya --gnubg / GNUBG_CLI ile yol verin.\n"
            "      Uydurma değer uretilmedi.",
            file=sys.stderr,
        )
        return 2
    if not args.model.is_file():
        print("HATA: model bulunamadi: %s" % args.model, file=sys.stderr)
        return 2

    version = gnubg_er.gnubg_version(gnubg)

    legacy_measurement: SplitMeasurement | None = None
    legacy_skipped: list[str] = []
    if args.cases.is_file():
        cases = gnubg_er.load_cases(args.cases)
        usable, legacy_skipped = gnubg_er.split_cases(cases)
        usable = usable[: args.legacy_limit]
        results, _ = gnubg_er.measure(
            args.model,
            usable,
            gnubg=gnubg,
            plies=args.plies,
            timeout=args.timeout,
            progress=not args.quiet,
        )
        stats = gnubg_er.summarize(results)
        power = statistical_power([r.equity_loss for r in results])
        legacy_measurement = SplitMeasurement(
            split="legacy",
            count=int(stats["count"]),
            mean=float(stats["mean"]),
            median=float(stats["median"]),
            maximum=float(stats["max"]),
            exact_match_rate=float(stats["exactMatchRate"]),
            standard_error=float(power["standardError"]),
            standard_deviation=float(power["standardDeviation"]),
        )

    corpus = load_corpus(args.corpus) if args.corpus.is_file() else None
    measurements: list[SplitMeasurement] = []
    if corpus is not None:
        for split_name in ("cal", "val", "test", "all"):
            cases = select_cases(corpus, split_name)
            measurement, _results = measure_split(
                args.model,
                cases,
                split=split_name,
                gnubg=gnubg,
                plies=args.plies,
                timeout=args.timeout,
                progress=not args.quiet,
            )
            measurements.append(measurement)

    volume = None
    if args.shards is not None:
        volume = measure_data_volume(collect_shards(args.shards))

    markdown = build_baseline_markdown(
        model_path=args.model,
        gnubg_path=gnubg,
        gnubg_version=version,
        plies=args.plies,
        legacy=legacy_measurement,
        legacy_skipped=legacy_skipped,
        corpus=corpus,
        measurements=measurements,
        data_volume=volume,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown)
    print("Markdown: %s" % args.out)
    return 0


def _cmd_power(args: argparse.Namespace) -> int:
    """Bir ER ölçüm dosyasından güç sözleşmesini üretir (Faz 7 Bölüm 4.5, Test 124)."""
    try:
        report = er_power.load_measurement(args.json)
    except er_power.MeasurementInvalidatedError as exc:
        print("HATA: %s" % exc, file=sys.stderr)
        return 2

    positions = report.get("positions") or []
    losses = [float(p["equityLoss"]) for p in positions]
    if len(losses) < 2:
        print("HATA: en az 2 pozisyon gerekli: %d" % len(losses), file=sys.stderr)
        return 2

    summary = er_power.summarize_losses(losses, resamples=args.resamples)
    n_required = er_power.required_n_from_upper(summary.sigma_ci_high, args.half_width)
    n_point = er_power.required_n(summary.sigma, args.half_width, two_sided=False)
    claim = er_power.claim_er_at_most(args.target, summary.ci_low, summary.ci_high)

    payload: dict[str, Any] = {
        "model": report.get("model"),
        "referee": report.get("referee", "eval"),
        "plies": report.get("plies"),
        "n": summary.n,
        "mean": round(summary.mean, 6),
        "median": round(summary.median, 6),
        "maximum": round(summary.maximum, 6),
        "sigma": round(summary.sigma, 6),
        "sigmaCiLow": round(summary.sigma_ci_low, 6),
        "sigmaCiHigh": round(summary.sigma_ci_high, 6),
        "standardError": round(summary.standard_error, 6),
        "ciLow": round(summary.ci_low, 6),
        "ciHigh": round(summary.ci_high, 6),
        "skewness": round(summary.skewness, 4),
        "excessKurtosis": round(summary.excess_kurtosis, 4),
        "tailShare": round(summary.tail_share, 4),
        "zeroLossCount": summary.zero_loss_count,
        "trimmedMean5": round(summary.trimmed_mean_5, 6),
        "winsorizedMean5": round(summary.winsorized_mean_5, 6),
        "bootstrapResamples": summary.bootstrap_resamples,
        "bootstrapSeed": summary.bootstrap_seed,
        "target": args.target,
        "halfWidth": args.half_width,
        "requiredN": n_required,
        "requiredNPointEstimate": n_point,
        "claim": claim,
        "claimSentence": er_power.claim_sentence(args.target, summary),
    }

    problems = er_power.validate_er_report(payload)
    if problems:
        for problem in problems:
            print("SORUN: %s" % problem, file=sys.stderr)
        return 1

    print(
        "n=%d | ER %.4f | GA [%.4f; %.4f] | sigma %.4f (GA [%.4f; %.4f]) | iddia: %s"
        % (
            summary.n,
            summary.mean,
            summary.ci_low,
            summary.ci_high,
            summary.sigma,
            summary.sigma_ci_low,
            summary.sigma_ci_high,
            claim,
        )
    )
    print(
        "gereken n: %d (sigma ust sinirindan) / %d (nokta tahmininden) | yari genislik %.4f"
        % (n_required, n_point, args.half_width)
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("JSON: %s" % args.out)

    if args.sigma_log:
        entry = er_power.sigma_log_entry(
            summary, stage=args.stage, model=str(report.get("model", "?"))
        )
        er_power.append_sigma_log(args.sigma_log, entry)
        print("sigma kaydi eklendi: %s (asama %s)" % (args.sigma_log, args.stage))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Faz 6 Aşama A — yeniden üretilebilir ER ölçüm hattı."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-corpus", help="dondurulmuş referans kümeyi üret")
    build.add_argument("--out", type=Path, default=CORPUS_PATH)
    build.add_argument("--seed", type=int, default=CORPUS_SEED)
    build.add_argument("--positions", type=int, default=TARGET_POSITIONS)
    build.set_defaults(func=_cmd_build_corpus)

    verify = sub.add_parser("verify-corpus", help="küme tutarlılığını denetle")
    verify.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    verify.set_defaults(func=_cmd_verify_corpus)

    measure = sub.add_parser("measure", help="bir bölünmede ER ölç")
    measure.add_argument("--model", required=True, type=Path)
    measure.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    measure.add_argument("--corpus-kind", choices=("iteration", "proof"), default="iteration")
    measure.add_argument("--split", choices=("cal", "val", "test", "all"), default="all")
    measure.add_argument("--referee", choices=REFEREES, default="eval")
    measure.add_argument("--gnubg", type=Path, default=None)
    measure.add_argument("--plies", type=int, default=gnubg_er.DEFAULT_PLIES)
    measure.add_argument("--timeout", type=int, default=gnubg_er.DEFAULT_TIMEOUT)
    measure.add_argument("--json", type=Path, default=None)
    measure.add_argument("--quiet", action="store_true")
    measure.set_defaults(func=_cmd_measure)

    power = sub.add_parser("power", help="ER ölçümünden güç sözleşmesi üret (Test 124)")
    power.add_argument("--json", required=True, type=Path, help="ölçüm dosyası")
    power.add_argument("--target", type=float, default=er_power.CHAMPION_ER_TARGET)
    power.add_argument("--half-width", type=float, default=0.005)
    power.add_argument("--resamples", type=int, default=er_power.BOOTSTRAP_RESAMPLES)
    power.add_argument("--out", type=Path, default=None)
    power.add_argument("--sigma-log", type=Path, default=None)
    power.add_argument("--stage", default="A")
    power.set_defaults(func=_cmd_power)

    legacy = sub.add_parser("legacy", help="Faz 5 vaka dosyasında ER ölç (41a)")
    legacy.add_argument("--model", required=True, type=Path)
    legacy.add_argument("--cases", type=Path, default=LEGACY_CASES)
    legacy.add_argument("--gnubg", type=Path, default=None)
    legacy.add_argument("--plies", type=int, default=gnubg_er.DEFAULT_PLIES)
    legacy.add_argument("--limit", type=int, default=STAGE_D_USABLE)
    legacy.add_argument("--timeout", type=int, default=gnubg_er.DEFAULT_TIMEOUT)
    legacy.add_argument("--json", type=Path, default=None)
    legacy.add_argument("--quiet", action="store_true")
    legacy.set_defaults(func=_cmd_legacy)

    volume = sub.add_parser("data-volume", help="shard'lardan bayt/karar ölç (41e)")
    volume.add_argument("--shards", required=True, type=Path)
    volume.add_argument("--json", type=Path, default=None)
    volume.set_defaults(func=_cmd_data_volume)

    baseline = sub.add_parser("baseline", help="stage_f_baseline.md üret")
    baseline.add_argument("--model", required=True, type=Path)
    baseline.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    baseline.add_argument("--cases", type=Path, default=LEGACY_CASES)
    baseline.add_argument("--legacy-limit", type=int, default=STAGE_D_USABLE)
    baseline.add_argument("--shards", type=Path, default=None)
    baseline.add_argument("--gnubg", type=Path, default=None)
    baseline.add_argument("--plies", type=int, default=gnubg_er.DEFAULT_PLIES)
    baseline.add_argument("--timeout", type=int, default=gnubg_er.DEFAULT_TIMEOUT)
    baseline.add_argument("--out", type=Path, default=BASELINE_REPORT)
    baseline.add_argument("--quiet", action="store_true")
    baseline.set_defaults(func=_cmd_baseline)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
