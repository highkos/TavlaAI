# -*- coding: utf-8 -*-
"""Faz 7-R Asama R-B: korpus v2 -- olcum altyapisi.

Korpus v1 (``ml/artifacts/reference_corpus_v1.json``) **dondurulmus** kalir ve
``legacy`` tabani olarak kullanilir. Bu modul onun yerine gecen **v2**'yi uretir
ve v1'in olculen dort kusurunu kapatir (``ASSUMPTIONS.md`` F7-47):

1. **Dagilim.** v1'de contact orani %19,5'ti (39/200); gercek oyunda contact
   baskindir. v2'de contact **>= %60** zorunludur.
2. **Bearoff/closed.** v1'de 37 bearoff + 44 closed vardi. Bearoff urunde **tam
   veritabanindan** cozulur, closed gercek oyunda **nadirdir**; ikisi de baslik
   ER'sine girmez, ayri ``diagnostic_*`` kumesine gider.
3. **Bolunme.** v1 **pozisyona** gore bolunuyordu; ayni oyunun pozisyonlari CAL
   ve TEST'e dusebiliyordu. v2 **oyuna** gore bolunur (``gameId``).
4. **Sizinti.** v1 ile damitma verisi ayni ureticiden geliyordu ve hicbir filtre
   yoktu. v2 ayna/perspektif-kanonik tahta hash'i ile sizinti filtresi uygular
   ve **cikarilan tahta sayisini** raporlar.

Ayrica her pozisyon ``gameId``, ``ply`` ve ``source`` tasir; TEST kumesine
erisim **denetim kaydina** yazilir (``TestAccessLog``).
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import er_harness  # noqa: E402
import gnubg_er  # noqa: E402
from tools import reference_gen as refgen  # noqa: E402

#: Korpus sema surumu.
CORPUS2_VERSION = 2

#: Dondurulmus v2 dosyasi.
CORPUS2_PATH = ML_DIR / "artifacts" / "reference_corpus_v2.json"

#: TEST erisim denetim kaydi.
TEST_ACCESS_LOG = ML_DIR / "artifacts" / "corpus2_test_access.jsonl"

#: v1 tabani (dondurulmus, degistirilmez).
LEGACY_CORPUS_PATH = er_harness.CORPUS_PATH

#: Hedef pozisyon sayisi (R-B: >= 1000).
TARGET_POSITIONS_V2 = 1000

#: Contact orani alt siniri (R-B: >= %60).
CONTACT_SHARE_MIN = 0.60

#: Rastgele oyun kaynagi ust siniri (R-B: <= %10).
RANDOM_SHARE_MAX = 0.10

#: Baslik ER'sine giren fazlar.
HEADLINE_PHASES = ("contact", "race", "bar")

#: Yalnizca teshis kumesine giren fazlar.
DIAGNOSTIC_PHASES = ("bearoff", "closed")

#: Tum fazlar.
PHASES_V2 = HEADLINE_PHASES + DIAGNOSTIC_PHASES

#: Kaynak etiketleri.
SOURCE_GNUBG2 = "gnubg2"
SOURCE_SELF = "self"
SOURCE_RANDOM = "random"
SOURCES = (SOURCE_GNUBG2, SOURCE_SELF, SOURCE_RANDOM)

#: Bolunme oranlari (v1 ile ayni: 30/35/35).
SPLIT_RATIOS_V2 = (("cal", 0.30), ("val", 0.35), ("test", 0.35))

#: Bolunme adlari.
SPLITS_V2 = tuple(name for name, _ in SPLIT_RATIOS_V2)

#: Guc tablosunda kullanilan minimum algilanabilir farklar (R-B madde 5).
POWER_DELTAS = (0.01, 0.02)

#: Baslik kumesinin **katmanli** faz paylari.
#:
#: Contact'i gercek oyun payinin uzerine cikariyoruz (R-B: >= %60) cunku
#: contact kararlari hem en zor hem de ER'nin en buyuk kaynagi. Gercek oyun
#: paylari oyunlardan **olculur** (``realGamePhaseWeights``) ve agirlikli ER
#: hesabinda kullanilir; boylece katmanlastirma yanliligi duzeltilir.
PHASE_SHARES = (("contact", 0.60), ("bar", 0.25), ("race", 0.15))

#: Rastgele oyun kaynagi icin hedef pay (ust sinir :data:`RANDOM_SHARE_MAX`).
RANDOM_SHARE_TARGET = 0.05

#: Bir oyunun en fazla ply sayisi (sonsuz dongu korumasi).
MAX_GAME_PLIES = 400


# ----------------------------------------------------------------------
# Kanonik tahta hash'i (sizinti filtresi)
# ----------------------------------------------------------------------


def mirror_board(board: Sequence[int]) -> list[int]:
    """Tahtayi **perspektif degistirerek** aynalar (Beyaz <-> Siyah).

    Proje duzeni: ``board[0]`` = Beyaz bar, ``board[1..24]`` = 1..24,
    ``board[25]`` = Siyah bar; pozitif = Beyaz. Aynalamada Beyaz'in ``i``
    hanesi Siyah'in ``i`` hanesi olur, yani Beyaz'in ``25 - i`` hanesine duser
    ve isaret ters doner.
    """
    if len(board) < 26:
        raise ValueError("board en az 26 eleman olmali: %d" % len(board))
    out = [0] * 26
    out[0] = -int(board[25])
    out[25] = -int(board[0])
    for i in range(1, 25):
        out[i] = -int(board[25 - i])
    return out


def canonical_board_key(
    board: Sequence[int], white_off: int = 0, black_off: int = 0
) -> tuple[int, ...]:
    """Ayna ve perspektiften bagimsiz kanonik tahta anahtari.

    Iki temsil uretilir -- ``(board, wo, bo)`` ve ``(mirror(board), bo, wo)`` --
    ve **sozluk sirasi kucuk olani** secilir. Boylece ayni pozisyon Beyaz'in ya
    da Siyah'in bakis acisindan yazilsa da **ayni anahtari** verir. Sizinti
    filtresi bu anahtar uzerinden calisir.
    """
    a = tuple(int(v) for v in board) + (int(white_off), int(black_off))
    m = mirror_board(board)
    b = tuple(int(v) for v in m) + (int(black_off), int(white_off))
    return a if a <= b else b


def board_hash(board: Sequence[int], white_off: int = 0, black_off: int = 0) -> str:
    """Kanonik anahtarin kisa (16 hex) SHA-256 ozeti."""
    key = canonical_board_key(board, white_off, black_off)
    payload = ",".join(str(v) for v in key).encode("ascii")
    return hashlib.sha256(payload).hexdigest()[:16]


# ----------------------------------------------------------------------
# Sizinti filtresi
# ----------------------------------------------------------------------


@dataclass
class LeakFilterResult:
    """Sizinti filtresinin sonucu."""

    kept: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    training_hashes: int

    @property
    def removed_count(self) -> int:
        return len(self.removed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trainingHashes": self.training_hashes,
            "kept": len(self.kept),
            "removed": self.removed_count,
            "removedNames": [c.get("name") for c in self.removed],
        }


def training_hashes(cases: Iterable[dict[str, Any]]) -> set[str]:
    """Egitim/damitma kumelerindeki tahtalarin kanonik hash kumesi."""
    out: set[str] = set()
    for case in cases:
        out.add(
            board_hash(
                case["board"],
                int(case.get("whiteOff", 0)),
                int(case.get("blackOff", 0)),
            )
        )
    return out


def leak_filter(
    cases: Sequence[dict[str, Any]], forbidden: Iterable[str]
) -> LeakFilterResult:
    """``forbidden`` hash'lerini tasiyan vakalari **cikarir**.

    Kural 6 ("sessiz geri dusme yok"): cikarilan her vaka **raporlanir**;
    sayi sifirsa da bu acikca yazilir.
    """
    banned = set(forbidden)
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for case in cases:
        h = board_hash(
            case["board"],
            int(case.get("whiteOff", 0)),
            int(case.get("blackOff", 0)),
        )
        if h in banned:
            removed.append(case)
        else:
            kept.append(case)
    return LeakFilterResult(kept=kept, removed=removed, training_hashes=len(banned))

# ----------------------------------------------------------------------
# Oyun uretimi
# ----------------------------------------------------------------------


def _random_dice(rng: random.Random) -> list[int]:
    """Rastgele zar; cift zarda dort ayni deger (Faz 1 sozlesmesi)."""
    d1 = rng.randint(1, 6)
    d2 = rng.randint(1, 6)
    return [d1, d1, d1, d1] if d1 == d2 else sorted([d1, d2])


def _random_chooser(rng: random.Random) -> Callable[[list[tuple]], tuple]:
    def choose(states: list[tuple]) -> tuple:
        return rng.choice(states)

    return choose


def _model_chooser(
    scorer: gnubg_er.OnnxScorer, turn: int
) -> Callable[[list[tuple]], tuple]:
    """Politika kafasi argmax'i ile hamle secer (0-ply, urunun ``ArgMaxCandidate``'i)."""

    def choose(states: list[tuple]) -> tuple:
        vectors = [
            gnubg_er.vectorize(b, w, k, perspective=turn) for (b, w, k) in states
        ]
        logits = scorer.logits(vectors)
        best = max(range(len(logits)), key=lambda i: logits[i])
        return states[best]

    return choose


def _play_game(
    rng: random.Random,
    *,
    game_id: str,
    source: str,
    chooser_factory: Callable[[int], Callable[[list[tuple]], tuple]],
    max_plies: int = MAX_GAME_PLIES,
) -> list[dict[str, Any]]:
    """Tek bir oyun oynar ve **karar pozisyonlarini** dondurur.

    Her kayit ``gameId``, ``ply``, ``source``, ``board``, ``turn``, ``dice``,
    ``whiteOff``, ``blackOff`` tasir. Oyun bitince (bir taraf 15 tasini toplarsa)
    durur.
    """
    board = list(refgen.START_BOARD)
    white_off = black_off = 0
    turn = 1 if rng.random() < 0.5 else -1
    out: list[dict[str, Any]] = []

    for ply in range(max_plies):
        dice = _random_dice(rng)
        max_steps, states = refgen.legal_after_states(
            board, turn, dice, white_off, black_off
        )
        if max_steps == 0 or not states:
            turn = -turn
            continue

        ordered = sorted(states)
        out.append(
            {
                "gameId": game_id,
                "ply": ply,
                "source": source,
                "board": list(board),
                "turn": int(turn),
                "dice": list(dice),
                "whiteOff": int(white_off),
                "blackOff": int(black_off),
            }
        )

        chooser = chooser_factory(turn)
        nb, white_off, black_off = chooser(ordered)
        board = list(nb)
        if white_off == refgen.PIECES or black_off == refgen.PIECES:
            break
        turn = -turn

    return out


def _gnubg_play_game(
    rng: random.Random,
    *,
    game_id: str,
    referee,
    max_plies: int = MAX_GAME_PLIES,
) -> list[dict[str, Any]]:
    """gnubg 2-ply ``hint`` ile oynanan tek oyun.

    ``hint`` **tahta + sira + zar** ister; bu yuzden ``_play_game``'in chooser
    soyutlamasi burada yetmez ve dongu ayri yazilir.
    """
    import gnubg_hint  # noqa: PLC0415

    board = list(refgen.START_BOARD)
    white_off = black_off = 0
    turn = 1 if rng.random() < 0.5 else -1
    out: list[dict[str, Any]] = []

    for ply in range(max_plies):
        dice = _random_dice(rng)
        max_steps, states = refgen.legal_after_states(
            board, turn, dice, white_off, black_off
        )
        if max_steps == 0 or not states:
            turn = -turn
            continue

        out.append(
            {
                "gameId": game_id,
                "ply": ply,
                "source": SOURCE_GNUBG2,
                "board": list(board),
                "turn": int(turn),
                "dice": list(dice),
                "whiteOff": int(white_off),
                "blackOff": int(black_off),
            }
        )

        ordered = sorted(states)
        chosen = None
        try:
            hints, _raw = referee.hint(board, turn, dice)
            case = {
                "board": list(board),
                "turn": int(turn),
                "dice": list(dice),
                "whiteOff": int(white_off),
                "blackOff": int(black_off),
            }
            matched, _failures = gnubg_hint.map_hints(hints, case)
            for entry in matched:
                key = entry.get("afterstateKey")
                for (b, w, k) in ordered:
                    if gnubg_hint.afterstate_key(b, w, k) == key:
                        chosen = (b, w, k)
                        break
                if chosen is not None:
                    break
        except Exception:  # noqa: BLE001 - gnubg hatasi oyunu durdurmaz
            chosen = None

        if chosen is None:
            chosen = rng.choice(ordered)

        nb, white_off, black_off = chosen
        board = list(nb)
        if white_off == refgen.PIECES or black_off == refgen.PIECES:
            break
        turn = -turn

    return out

# ----------------------------------------------------------------------
# Vaka uretimi
# ----------------------------------------------------------------------


def _case_from_record(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Bir oyun kaydindan korpus vakasi uretir (>= 2 afterstate sarti)."""
    board = record["board"]
    turn = int(record["turn"])
    dice = [int(d) for d in record["dice"]]
    white_off = int(record["whiteOff"])
    black_off = int(record["blackOff"])

    max_steps, states = refgen.legal_after_states(
        board, turn, dice, white_off, black_off
    )
    if max_steps == 0 or len(states) < 2:
        return None

    return {
        "name": name,
        "gameId": str(record["gameId"]),
        "ply": int(record["ply"]),
        "source": str(record["source"]),
        "phase": er_harness.classify_phase(board, turn),
        "board": list(board),
        "turn": turn,
        "dice": dice,
        "whiteOff": white_off,
        "blackOff": black_off,
        "maxSteps": int(max_steps),
        "afterStates": [
            {"board": list(b), "whiteOff": int(w), "blackOff": int(k)}
            for (b, w, k) in sorted(states)
        ],
    }


def _dedupe(cases: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Kanonik tahta hash'ine gore tekrarlari atar; (kalan, atilan) dondurur."""
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    dropped = 0
    for case in cases:
        h = board_hash(case["board"], case["whiteOff"], case["blackOff"])
        if h in seen:
            dropped += 1
            continue
        seen.add(h)
        kept.append(case)
    return kept, dropped


# ----------------------------------------------------------------------
# Bolunme (oyuna gore)
# ----------------------------------------------------------------------


def assign_splits_by_game(
    cases: Sequence[dict[str, Any]], seed: int
) -> dict[str, list[str]]:
    """CAL / VAL / TEST bolunmesi -- **oyun** duzeyinde, faz katmanli.

    v1'de bolunme pozisyon duzeyindeydi ve ayni oyunun pozisyonlari farkli
    kumelere dusebiliyordu (sizinti). Burada **oyun kimligi** karistirilir ve
    bir oyunun **tum** pozisyonlari ayni kumeye gider.
    """
    rng = random.Random(seed ^ 0x2C0F2A)

    # Oyun -> pozisyon adlari. Bolunme **oyun** duzeyinde yapilir; bir oyunun
    # tum pozisyonlari ayni kumeye gider. Faz katmani oyun duzeyinde
    # uygulanirsa ayni oyun iki kumeye duser (v1'in hatasi); bu yuzden
    # katmanlastirma **yalnizca** oyunun baskin fazina gore siralama amaciyla
    # kullanilir, bolunme karari tek seferde verilir.
    by_game: dict[str, list[str]] = {}
    game_phase: dict[str, str] = {}
    for case in cases:
        by_game.setdefault(case["gameId"], []).append(case["name"])
        game_phase.setdefault(case["gameId"], case["phase"])

    games = sorted(by_game)
    rng.shuffle(games)

    # Oyunlar pozisyon sayisina gore **buyukten kucuge** yerlestirilir; her oyun
    # hedef payina gore en cok acigi olan kumeye gider. Boylece hem oyun
    # butunlugu korunur hem de kumeler pozisyon sayisinda dengeli olur (oyun
    # uzunluklari 80-220 ply arasinda degistigi icin saf oran bolmesi cok
    # dengesiz sonuc veriyordu).
    total_positions = sum(len(v) for v in by_game.values())
    targets = {name: ratio * total_positions for name, ratio in SPLIT_RATIOS_V2}
    filled = {name: 0 for name in SPLITS_V2}
    splits: dict[str, list[str]] = {name: [] for name in SPLITS_V2}

    for game_id in sorted(games, key=lambda g: (-len(by_game[g]), g)):
        size = len(by_game[game_id])
        best = max(
            SPLITS_V2,
            key=lambda name: (targets[name] - filled[name]) / max(targets[name], 1.0),
        )
        splits[best].extend(by_game[game_id])
        filled[best] += size

    for name in splits:
        splits[name].sort()
    return splits


def split_membership(corpus: dict[str, Any]) -> dict[str, str]:
    """Pozisyon adi -> bolunme adi."""
    out: dict[str, str] = {}
    for split_name, names in corpus["splits"].items():
        for name in names:
            out[name] = split_name
    return out


def select_cases(corpus: dict[str, Any], split: str) -> list[dict[str, Any]]:
    """Bolunmeye gore vakalari dondurur (``all`` = tumu)."""
    if split == "all":
        return list(corpus["cases"])
    if split not in corpus["splits"]:
        raise ValueError("bilinmeyen bolunme: %r" % (split,))
    wanted = set(corpus["splits"][split])
    return [c for c in corpus["cases"] if c["name"] in wanted]


# ----------------------------------------------------------------------
# TEST erisim denetim kaydi
# ----------------------------------------------------------------------


@dataclass
class TestAccessLog:
    """TEST kumesine erisimin **degistirilemez** kaydi (hash zinciri).

    Her kayit onceki kaydin ozetini tasir; bir kayit silinirse veya
    degistirilirse :meth:`verify` bunu yakalar. Amac: "TEST'e kac kez bakildi"
    sorusunun cevabini sonradan uyduramamak.
    """

    path: Path = TEST_ACCESS_LOG

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    @staticmethod
    def _digest(entry: dict[str, Any]) -> str:
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=True).encode("ascii")
        return hashlib.sha256(payload).hexdigest()[:16]

    def record(
        self, *, split: str, names: Sequence[str], note: str = ""
    ) -> dict[str, Any]:
        """Bir erisimi kaydeder ve kaydi dondurur."""
        entries = self._read()
        prev = entries[-1]["digest"] if entries else "0" * 16
        body = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "split": split,
            "count": len(names),
            "namesDigest": hashlib.sha256(
                "\n".join(sorted(names)).encode("utf-8")
            ).hexdigest()[:16],
            "note": note,
            "prev": prev,
        }
        body["digest"] = self._digest(body)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(body, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
        return body

    def verify(self) -> list[str]:
        """Zinciri denetler; ihlal listesi dondurur (bos = saglikli)."""
        problems: list[str] = []
        prev = "0" * 16
        for index, entry in enumerate(self._read()):
            if entry.get("prev") != prev:
                problems.append("kayit %d: prev uyusmuyor" % index)
            body = {k: v for k, v in entry.items() if k != "digest"}
            if self._digest(body) != entry.get("digest"):
                problems.append("kayit %d: ozet uyusmuyor" % index)
            prev = entry.get("digest", "")
        return problems

    def count(self, split: str | None = None) -> int:
        """Kayit sayisi (``split`` verilirse o bolunme icin)."""
        entries = self._read()
        if split is None:
            return len(entries)
        return sum(1 for e in entries if e.get("split") == split)


# ----------------------------------------------------------------------
# Guc tablosu
# ----------------------------------------------------------------------


def power_table(
    sigma_ci_high: float, deltas: Sequence[float] = POWER_DELTAS
) -> list[dict[str, Any]]:
    """``delta`` basina gereken n -- **sigma'nin ust guven sinirindan** (Kural 4).

    Nokta tahmininden hesaplamak n'i sistematik olarak eksik verir
    (``er_power.required_n_from_upper`` belgesi). Bu yuzden burada yalnizca
    ``sigma_ci_high`` kullanilir.
    """
    import er_power  # noqa: PLC0415

    if sigma_ci_high <= 0.0:
        raise ValueError("sigma_ci_high pozitif olmali: %r" % (sigma_ci_high,))
    rows: list[dict[str, Any]] = []
    for delta in deltas:
        rows.append(
            {
                "deltaMin": float(delta),
                "sigmaCiHigh": float(sigma_ci_high),
                "nOneSided": er_power.required_n_from_upper(
                    sigma_ci_high, float(delta), two_sided=False
                ),
                "nTwoSided": er_power.required_n_from_upper(
                    sigma_ci_high, float(delta), two_sided=True
                ),
            }
        )
    return rows

# ----------------------------------------------------------------------
# Korpus kurma
# ----------------------------------------------------------------------


def _phase_counts(cases: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {p: 0 for p in PHASES_V2}
    for case in cases:
        counts[case["phase"]] = counts.get(case["phase"], 0) + 1
    return counts


def _source_counts(cases: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in SOURCES}
    for case in cases:
        counts[case["source"]] = counts.get(case["source"], 0) + 1
    return counts


def real_game_phase_weights(
    records: Sequence[dict[str, Any]],
) -> dict[str, float]:
    """Gercek oyunlarda fazlarin **olculen** karar payi (baslik fazlari).

    Korpus katmanli oldugu icin ham ortalama yanlidir; agirlikli ER bu paylarla
    hesaplanir. Paylar oyun kayitlarindan olculur, varsayilmaz.
    """
    counts = {p: 0 for p in HEADLINE_PHASES}
    total = 0
    for record in records:
        phase = er_harness.classify_phase(record["board"], int(record["turn"]))
        if phase in counts:
            counts[phase] += 1
            total += 1
    if total == 0:
        return {p: 0.0 for p in HEADLINE_PHASES}
    return {p: round(counts[p] / total, 6) for p in HEADLINE_PHASES}


def _select_headline(
    pool: Sequence[dict[str, Any]], target: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Baslik kumesini **katmanli** secer (:data:`PHASE_SHARES`).

    Her fazdan hedef pay kadar vaka alinir; bir fazda yeterli vaka yoksa acik
    **kisilir** ve kalan kontenjan diger fazlara dagitilir. Hicbir faz sessizce
    bos birakilmaz: eksik kalan pay ``notes``'a yazilir (Kural 6).
    """
    buckets: dict[str, list[dict[str, Any]]] = {p: [] for p in HEADLINE_PHASES}
    diagnostic: list[dict[str, Any]] = []
    for case in pool:
        if case["phase"] in buckets:
            buckets[case["phase"]].append(case)
        else:
            diagnostic.append(case)

    quotas = {phase: int(round(target * share)) for phase, share in PHASE_SHARES}
    selected: list[dict[str, Any]] = []
    shortfall: dict[str, int] = {}
    for phase, _share in PHASE_SHARES:
        want = quotas[phase]
        bucket = buckets[phase]
        # Rastgele oyun kaynagi icin kontenjan ayir (R-B: <= %10, hedef %5).
        random_quota = int(round(want * RANDOM_SHARE_TARGET))
        random_cases = [c for c in bucket if c["source"] == SOURCE_RANDOM][:random_quota]
        others = [c for c in bucket if c["source"] != SOURCE_RANDOM]
        have = random_cases + others[: max(want - len(random_cases), 0)]
        selected.extend(have)
        if len(have) < want:
            shortfall[phase] = want - len(have)

    # Eksik kontenjani diger fazlardan doldur (contact oncelikli).
    deficit = target - len(selected)
    if deficit > 0:
        used = {c["name"] for c in selected}
        for phase, _share in PHASE_SHARES:
            for case in buckets[phase]:
                if deficit <= 0:
                    break
                if case["name"] in used:
                    continue
                selected.append(case)
                used.add(case["name"])
                deficit -= 1
            if deficit <= 0:
                break

    used = {c["name"] for c in selected}
    for phase in HEADLINE_PHASES:
        for case in buckets[phase]:
            if case["name"] not in used:
                diagnostic.append(case)

    return selected, diagnostic, shortfall


def build_corpus2(
    *,
    seed: int = 20261118,
    target: int = TARGET_POSITIONS_V2,
    gnubg_games: int = 0,
    self_games: int = 40,
    random_games: int = 6,
    model_path: Path | None = None,
    gnubg_exe: Path | None = None,
    gnubg_plies: int = 2,
    forbidden_hashes: Iterable[str] = (),
    progress: bool = True,
    records_cache: Path | None = None,
) -> dict[str, Any]:
    """Korpus v2'yi deterministik olarak uretir.

    Kaynaklar: (a) gnubg 2-ply self-play, (b) kendi model self-play,
    (c) rastgele oyun. Rastgele oyun payi :data:`RANDOM_SHARE_MAX`'i asarsa
    secim **rastgele vakalari kisarak** yapilir ve bu ``notes``'a yazilir.
    """
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []

    if records_cache is not None and Path(records_cache).is_file():
        with open(records_cache, encoding="utf-8") as handle:
            records = json.load(handle)
        if progress:
            print("  oyun kayitlari onbellekten: %d" % len(records), flush=True)
        gnubg_games = self_games = random_games = 0

    if gnubg_games > 0:
        if gnubg_exe is None:
            gnubg_exe = gnubg_er.find_gnubg()
        if gnubg_exe is None:
            raise RuntimeError(
                "gnubg bulunamadi; --gnubg-games 0 verin veya yolu gosterin"
            )
        import gnubg_hint  # noqa: PLC0415

        referee = gnubg_hint.HintReferee(gnubg_exe, plies=gnubg_plies, timeout=180)
        for i in range(gnubg_games):
            if progress:
                print("  gnubg oyun %d/%d" % (i + 1, gnubg_games), flush=True)
            records.extend(
                _gnubg_play_game(rng, game_id="g2-%03d" % i, referee=referee)
            )

    if self_games > 0:
        if model_path is None:
            raise RuntimeError("self-play icin --model gerekli")
        scorer = gnubg_er.OnnxScorer(Path(model_path))
        for i in range(self_games):
            if progress:
                print("  self oyun %d/%d" % (i + 1, self_games), flush=True)
            records.extend(
                _play_game(
                    rng,
                    game_id="sf-%03d" % i,
                    source=SOURCE_SELF,
                    chooser_factory=lambda turn, s=scorer: _model_chooser(s, turn),
                )
            )

    if random_games > 0:
        for i in range(random_games):
            records.extend(
                _play_game(
                    rng,
                    game_id="rn-%03d" % i,
                    source=SOURCE_RANDOM,
                    chooser_factory=lambda turn: _random_chooser(rng),
                )
            )

    if records_cache is not None and not Path(records_cache).is_file():
        Path(records_cache).parent.mkdir(parents=True, exist_ok=True)
        with open(records_cache, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(records, handle, separators=(",", ":"))
            handle.write("\n")

    cases: list[dict[str, Any]] = []
    for record in records:
        case = _case_from_record(record, "v2-%04d" % len(cases))
        if case is not None:
            cases.append(case)

    cases, dup_dropped = _dedupe(cases)

    leak = leak_filter(cases, forbidden_hashes)
    cases = leak.kept

    headline, diagnostic, shortfall = _select_headline(cases, target)

    notes: list[str] = []
    for phase, missing in sorted(shortfall.items()):
        notes.append(
            "faz %s kontenjani %d vaka eksik (havuzda yeterli vaka yok)" % (phase, missing)
        )
    random_share = (
        sum(1 for c in headline if c["source"] == SOURCE_RANDOM) / max(len(headline), 1)
    )
    if random_share > RANDOM_SHARE_MAX:
        keep_random = int(RANDOM_SHARE_MAX * len(headline))
        seen_random = 0
        trimmed: list[dict[str, Any]] = []
        for case in headline:
            if case["source"] == SOURCE_RANDOM:
                seen_random += 1
                if seen_random > keep_random:
                    diagnostic.append(case)
                    continue
            trimmed.append(case)
        notes.append(
            "rastgele oyun payi %.3f > %.2f; %d vaka teshis kumesine tasindi"
            % (random_share, RANDOM_SHARE_MAX, len(headline) - len(trimmed))
        )
        headline = trimmed

    counts = _phase_counts(headline)
    contact_share = counts["contact"] / max(len(headline), 1)
    if contact_share < CONTACT_SHARE_MIN:
        notes.append(
            "contact orani %.3f < %.2f (R-B ihlali; daha fazla self-play oyunu gerekli)"
            % (contact_share, CONTACT_SHARE_MIN)
        )

    corpus = {
        "corpusVersion": CORPUS2_VERSION,
        "realGamePhaseWeights": real_game_phase_weights(records),
        "generator": "ml/corpus2.py",
        "seed": seed,
        "targetPositions": target,
        "contactShareMin": CONTACT_SHARE_MIN,
        "randomShareMax": RANDOM_SHARE_MAX,
        "headlinePhases": list(HEADLINE_PHASES),
        "diagnosticPhases": list(DIAGNOSTIC_PHASES),
        "phaseCounts": counts,
        "contactShare": round(contact_share, 6),
        "sourceCounts": _source_counts(headline),
        "duplicatesDropped": dup_dropped,
        "leakFilter": leak.to_dict(),
        "notes": notes,
        "cases": headline,
        "diagnostic": diagnostic,
    }
    corpus["digest"] = corpus_digest(corpus)
    corpus["splits"] = assign_splits_by_game(headline, seed)
    return corpus


def corpus_digest(corpus: dict[str, Any]) -> str:
    """Korpus iceriginin kanonik ozeti (sira bagimsiz)."""
    payload = [
        {
            "name": c["name"],
            "gameId": c["gameId"],
            "ply": c["ply"],
            "source": c["source"],
            "phase": c["phase"],
            "board": [int(v) for v in c["board"]],
            "turn": int(c["turn"]),
            "dice": [int(d) for d in c["dice"]],
            "whiteOff": int(c["whiteOff"]),
            "blackOff": int(c["blackOff"]),
            "afterStates": [
                {
                    "board": [int(v) for v in a["board"]],
                    "whiteOff": int(a["whiteOff"]),
                    "blackOff": int(a["blackOff"]),
                }
                for a in c["afterStates"]
            ],
        }
        for c in sorted(corpus["cases"], key=lambda x: x["name"])
    ]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def verify_corpus2(corpus: dict[str, Any]) -> list[str]:
    """Korpus v2 tutarlilik denetimleri; ihlal listesi (bos = saglikli)."""
    problems: list[str] = []
    cases = corpus["cases"]

    if corpus.get("corpusVersion") != CORPUS2_VERSION:
        problems.append(
            "corpusVersion %r != %d" % (corpus.get("corpusVersion"), CORPUS2_VERSION)
        )

    if len(cases) < corpus.get("targetPositions", TARGET_POSITIONS_V2):
        problems.append(
            "pozisyon sayisi %d < hedef %d"
            % (len(cases), corpus.get("targetPositions", TARGET_POSITIONS_V2))
        )

    if corpus_digest(corpus) != corpus.get("digest"):
        problems.append("ozet uyusmuyor")

    counts = _phase_counts(cases)
    for phase in DIAGNOSTIC_PHASES:
        if counts.get(phase, 0):
            problems.append(
                "baslik kumesinde teshis fazi var: %s (%d)" % (phase, counts[phase])
            )

    contact_share = counts.get("contact", 0) / max(len(cases), 1)
    if contact_share < CONTACT_SHARE_MIN:
        problems.append(
            "contact orani %.3f < %.2f" % (contact_share, CONTACT_SHARE_MIN)
        )

    random_share = (
        sum(1 for c in cases if c["source"] == SOURCE_RANDOM) / max(len(cases), 1)
    )
    if random_share > RANDOM_SHARE_MAX:
        problems.append(
            "rastgele oyun payi %.3f > %.2f" % (random_share, RANDOM_SHARE_MAX)
        )

    names = [c["name"] for c in cases]
    if len(set(names)) != len(names):
        problems.append("pozisyon adlari benzersiz degil")

    for case in cases:
        for key in ("gameId", "ply", "source"):
            if key not in case:
                problems.append("%s: %s alani yok" % (case.get("name"), key))
        if len(case["afterStates"]) < 2:
            problems.append("%s: afterstate < 2" % case["name"])
        white, black = gnubg_er.case_piece_counts(case)
        if white != gnubg_er.PIECES_PER_PLAYER or black != gnubg_er.PIECES_PER_PLAYER:
            problems.append(
                "%s: tas sayisi %d/%d" % (case["name"], white, black)
            )

    membership = split_membership(corpus)
    if set(membership) != set(names):
        problems.append("bolunme kapsami korpus ile uyusmuyor")
    total_split = sum(len(v) for v in corpus["splits"].values())
    if total_split != len(names):
        problems.append("bolunmeler toplami %d != %d" % (total_split, len(names)))

    game_split: dict[str, str] = {}
    for case in cases:
        split_name = membership.get(case["name"])
        prev = game_split.setdefault(case["gameId"], split_name)
        if prev != split_name:
            problems.append(
                "oyun %s iki bolunmede: %s ve %s"
                % (case["gameId"], prev, split_name)
            )

    seen: dict[str, str] = {}
    for case in cases:
        h = board_hash(case["board"], case["whiteOff"], case["blackOff"])
        if h in seen:
            problems.append(
                "kanonik tahta tekrari: %s / %s" % (seen[h], case["name"])
            )
        seen[h] = case["name"]

    return problems


# ----------------------------------------------------------------------
# G/C
# ----------------------------------------------------------------------


def save_corpus2(corpus: dict[str, Any], path: Path = CORPUS2_PATH) -> None:
    """Korpusu yazar (LF, UTF-8, sonunda yeni satir)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(corpus, indent=1, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def load_corpus2(path: Path = CORPUS2_PATH) -> dict[str, Any]:
    """Korpusu okur."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser():
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        prog="corpus2", description="Faz 7-R korpus v2 (olcum altyapisi)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="korpus v2 uret")
    build.add_argument("--seed", type=int, default=20261118)
    build.add_argument("--target", type=int, default=TARGET_POSITIONS_V2)
    build.add_argument("--gnubg-games", type=int, default=0)
    build.add_argument("--self-games", type=int, default=40)
    build.add_argument("--random-games", type=int, default=6)
    build.add_argument("--model", type=Path, default=None)
    build.add_argument("--gnubg", type=Path, default=None)
    build.add_argument("--gnubg-plies", type=int, default=2)
    build.add_argument("--out", type=Path, default=CORPUS2_PATH)
    build.add_argument("--records-cache", type=Path, default=None)
    build.add_argument("--quiet", action="store_true")

    verify = sub.add_parser("verify", help="korpus v2 denetle")
    verify.add_argument("--corpus", type=Path, default=CORPUS2_PATH)

    power = sub.add_parser("power", help="guc tablosu (sigma ust sinirindan)")
    power.add_argument("--sigma-ci-high", type=float, required=True)
    power.add_argument("--delta", type=float, action="append", default=None)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "build":
        corpus = build_corpus2(
            seed=args.seed,
            target=args.target,
            gnubg_games=args.gnubg_games,
            self_games=args.self_games,
            random_games=args.random_games,
            model_path=args.model,
            gnubg_exe=args.gnubg,
            gnubg_plies=args.gnubg_plies,
            progress=not args.quiet,
            records_cache=args.records_cache,
        )
        save_corpus2(corpus, args.out)
        problems = verify_corpus2(corpus)
        print("korpus v2: %d pozisyon -> %s" % (len(corpus["cases"]), args.out))
        print("  faz: %r" % (corpus["phaseCounts"],))
        print("  kaynak: %r" % (corpus["sourceCounts"],))
        print("  contact orani: %.4f" % corpus["contactShare"])
        print("  sizinti filtresi: %r" % (corpus["leakFilter"],))
        print("  teshis kumesi: %d" % len(corpus["diagnostic"]))
        for note in corpus["notes"]:
            print("  NOT: %s" % note)
        if problems:
            for problem in problems:
                print("  IHLAL: %s" % problem)
            return 1
        return 0

    if args.command == "verify":
        corpus = load_corpus2(args.corpus)
        problems = verify_corpus2(corpus)
        if problems:
            for problem in problems:
                print("IHLAL: %s" % problem)
            return 1
        print("korpus v2 saglikli: %d pozisyon" % len(corpus["cases"]))
        return 0

    if args.command == "power":
        deltas = args.delta if args.delta else list(POWER_DELTAS)
        for row in power_table(args.sigma_ci_high, deltas):
            print(
                "delta=%.3f  sigma_ust=%.6f  n(tek)=%d  n(iki)=%d"
                % (
                    row["deltaMin"],
                    row["sigmaCiHigh"],
                    row["nOneSided"],
                    row["nTwoSided"],
                )
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())