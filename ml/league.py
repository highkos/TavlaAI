"""Faz 4 v3 Bölüm 6.5 — lig (model havuzu).

Havuz, dondurulmus ONNX modellerinden olusur. Eğitim döngüsü her iterasyonda
``pool_fraction`` olasilikla havuzdan bir rakip secer; havuz rakibinin kararları
``IsLearner = 0`` olarak loglanır ve o kararlar için kayıp hesaplanmaz.

Havuza giris: her ``K`` iterasyonda ogrenen ağ ile havuzdaki **en guclu** model
arasinda sabit seed'li, ``argmax``, ``N_eval`` oyunluk değerlendirme maci yapılır.
Giris eşiği: oyun başına ortalama puanin **alt guven siniri** ``> 0``.

Havuz boyutu sinirlidir; tasinca ``eviction`` politikasina göre
(``"oldest"`` veya ``"weakest"``) bir uye cikarilir.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_MAX_SIZE = 10
DEFAULT_EVICTION = "oldest"
DEFAULT_ENTRY_THRESHOLD = 0.0
DEFAULT_EVAL_GAMES = 400
DEFAULT_EVAL_EVERY = 5
DEFAULT_POOL_FRACTION = 0.2

EVICTION_OLDEST = "oldest"
EVICTION_WEAKEST = "weakest"


class LeagueError(RuntimeError):
    """Lig islemleri basarisiz oldugunda firlatilir."""


# ----------------------------------------------------------------------
# Veri tipleri
# ----------------------------------------------------------------------


@dataclass
class PoolEntry:
    """Havuzdaki dondurulmus bir model."""

    name: str
    onnx_path: str
    model_version: int
    iteration: int
    strength: float = 0.0
    strength_se: float = 0.0

    @property
    def lower_confidence_bound(self) -> float:
        return self.strength - 1.96 * self.strength_se


@dataclass
class EvalResult:
    """``Backgammon.SelfPlay --eval-json`` ciktisindaki tek bir rakip raporu."""

    opponent: str
    games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    mean_points: float
    standard_error: float
    lower_confidence_bound: float
    upper_confidence_bound: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvalResult":
        return cls(
            opponent=str(d["opponent"]),
            games=int(d["games"]),
            wins=int(d["wins"]),
            losses=int(d["losses"]),
            draws=int(d["draws"]),
            win_rate=float(d["winRate"]),
            mean_points=float(d["meanPoints"]),
            standard_error=float(d["standardError"]),
            lower_confidence_bound=float(d["lowerConfidenceBound"]),
            upper_confidence_bound=float(d["upperConfidenceBound"]),
        )


# ----------------------------------------------------------------------
# Havuz
# ----------------------------------------------------------------------


@dataclass
class League:
    """Model havuzu + giris/eleme politikasi."""

    pool_dir: Path
    max_size: int = DEFAULT_MAX_SIZE
    eviction: str = DEFAULT_EVICTION
    index_name: str = "pool.json"
    entries: list[PoolEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.pool_dir = Path(self.pool_dir)
        if self.max_size < 1:
            raise ValueError("max_size >= 1 olmalidir")
        if self.eviction not in (EVICTION_OLDEST, EVICTION_WEAKEST):
            raise ValueError("eviction 'oldest' veya 'weakest' olmalidir: " + str(self.eviction))

    # -- kalicilik -----------------------------------------------------

    @property
    def index_path(self) -> Path:
        return self.pool_dir / self.index_name

    def save(self) -> None:
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "maxSize": self.max_size,
            "eviction": self.eviction,
            "entries": [asdict(e) for e in self.entries],
        }
        self.index_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(
        cls,
        pool_dir: Path,
        *,
        max_size: int | None = None,
        eviction: str | None = None,
    ) -> "League":
        pool_dir = Path(pool_dir)
        index = pool_dir / "pool.json"
        if not index.is_file():
            return cls(
                pool_dir=pool_dir,
                max_size=DEFAULT_MAX_SIZE if max_size is None else max_size,
                eviction=DEFAULT_EVICTION if eviction is None else eviction,
            )

        data = json.loads(index.read_text(encoding="utf-8"))
        entries = [PoolEntry(**e) for e in data.get("entries", [])]
        return cls(
            pool_dir=pool_dir,
            max_size=int(data.get("maxSize", DEFAULT_MAX_SIZE)) if max_size is None else max_size,
            eviction=str(data.get("eviction", DEFAULT_EVICTION)) if eviction is None else eviction,
            entries=entries,
        )

    # -- sorgular ------------------------------------------------------

    def __len__(self) -> int:
        return len(self.entries)

    def is_empty(self) -> bool:
        return not self.entries

    def strongest(self) -> PoolEntry | None:
        """En yuksek ölçülmüş gücü olan uye (esitlikte en yeni)."""
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: (e.strength, e.iteration))

    def names(self) -> list[str]:
        return [e.name for e in self.entries]

    def select_opponent(self, rng: Any, pool_fraction: float) -> PoolEntry | None:
        """``pool_fraction`` olasilikla havuzdan rastgele bir uye secer."""
        if not self.entries or pool_fraction <= 0.0:
            return None
        if float(rng.random()) >= pool_fraction:
            return None
        return self.entries[int(rng.integers(0, len(self.entries)))]

    # -- mutasyon ------------------------------------------------------

    def add(self, entry: PoolEntry) -> list[PoolEntry]:
        """Uyeyi ekler; boyut asilirsa politikaya göre uye cikarir.

        Donen liste cikarilan uyelerdir (dosyalari silinmis olarak).
        """
        if any(e.name == entry.name for e in self.entries):
            raise LeagueError("havuzda aynı isimde uye var: " + entry.name)

        self.entries.append(entry)
        evicted: list[PoolEntry] = []

        while len(self.entries) > self.max_size:
            if self.eviction == EVICTION_WEAKEST:
                victim = min(self.entries, key=lambda e: (e.strength, e.iteration))
            else:
                victim = min(self.entries, key=lambda e: e.iteration)

            self.entries.remove(victim)
            evicted.append(victim)
            self._delete_artifact(victim)

        self.save()
        return evicted

    def _delete_artifact(self, entry: PoolEntry) -> None:
        path = Path(entry.onnx_path)
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    def import_model(self, source: Path, name: str, model_version: int, iteration: int) -> Path:
        """ONNX dosyasini havuz klasorune kopyalar ve hedef yolu doner."""
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        target = self.pool_dir / (name + ".onnx")
        shutil.copyfile(source, target)
        return target


# ----------------------------------------------------------------------
# Degerlendirme (C# self-play uzerinden)
# ----------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_eval(
    *,
    learner_onnx: Path,
    games: int,
    seed: int,
    depth: int,
    opponent_onnx: Path | None = None,
    opponent_kind: str = "model",
    max_root: int = 0,
    max_inner: int = 0,
    max_plies: int = 500,
    max_batch: int = 2048,
    intra_op: int = 1,
    cuda: bool = False,
    project: str = "Backgammon.SelfPlay/Backgammon.SelfPlay.csproj",
    configuration: str = "Release",
    json_path: Path | None = None,
    timeout: float | None = None,
) -> list[EvalResult]:
    """``Backgammon.SelfPlay`` ile değerlendirme kosar ve raporlari doner.

    ``opponent_kind``: ``"random"``, ``"pip"`` veya ``"model"``.
    """
    if games <= 0:
        raise ValueError("games > 0 olmalidir")
    if opponent_kind not in ("random", "pip", "model"):
        raise ValueError("opponent_kind 'random' | 'pip' | 'model' olmalidir")
    if opponent_kind == "model" and opponent_onnx is None:
        raise ValueError("opponent_kind='model' için opponent_onnx gerekli")

    root = _repo_root()
    proj = root / project
    if not proj.is_file():
        raise LeagueError("self-play projesi bulunamadi: " + str(proj))

    out_json = Path(json_path) if json_path is not None else (
        root / "ml" / "artifacts" / "_eval_tmp.json"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_json.is_file():
        out_json.unlink()

    cmd: list[str] = [
        "dotnet", "run",
        "--project", str(proj),
        "-c", configuration,
        "--no-build",
        "--",
        "--model", str(learner_onnx),
        "--seed", str(seed),
        "--depth", str(depth),
        "--max-root", str(max_root),
        "--max-inner", str(max_inner),
        "--max-plies", str(max_plies),
        "--max-batch", str(max_batch),
        "--intra-op", str(intra_op),
        "--eval-json", str(out_json),
    ]

    if opponent_kind == "random":
        cmd.extend(["--eval-random", str(games)])
    elif opponent_kind == "pip":
        cmd.extend(["--eval-pip", str(games)])
    else:
        cmd.extend([
            "--eval-model", str(games),
            "--eval-model-path", str(opponent_onnx),
        ])

    if cuda:
        cmd.append("--cuda")

    proc = subprocess.run(
        cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise LeagueError(
            "değerlendirme basarisiz (exit " + str(proc.returncode) + ")\n"
            + "STDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr
        )

    if not out_json.is_file():
        raise LeagueError("değerlendirme JSON'u yazilmadi: " + str(out_json))

    data = json.loads(out_json.read_text(encoding="utf-8"))
    results = [EvalResult.from_dict(r) for r in data.get("reports", [])]
    if not results:
        raise LeagueError("değerlendirme JSON'unda rapor yok: " + str(out_json))
    return results


def should_enter_pool(
    result: EvalResult, threshold: float = DEFAULT_ENTRY_THRESHOLD
) -> bool:
    """Giris eşiği: alt guven siniri ``threshold``'un uzerinde mi?"""
    return result.lower_confidence_bound > threshold


def evaluate_for_entry(
    league: League,
    learner_onnx: Path,
    *,
    games: int = DEFAULT_EVAL_GAMES,
    seed: int = 0,
    depth: int = 1,
    max_root: int = 0,
    max_inner: int = 0,
    max_plies: int = 500,
    cuda: bool = False,
    json_path: Path | None = None,
) -> EvalResult | None:
    """Ogrenen agi havuzun en guclu uyesine karşı oynatir.

    Havuz bossa ``None`` doner (giris serbesttir; cagiran taraf karar verir).
    """
    strongest = league.strongest()
    if strongest is None:
        return None

    results = run_eval(
        learner_onnx=learner_onnx,
        games=games,
        seed=seed,
        depth=depth,
        opponent_onnx=Path(strongest.onnx_path),
        opponent_kind="model",
        max_root=max_root,
        max_inner=max_inner,
        max_plies=max_plies,
        cuda=cuda,
        json_path=json_path,
    )
    return results[0]


def format_report(results: Iterable[EvalResult]) -> str:
    """Insan okunur ozet tablo."""
    lines = [
        "| Rakip | Oyun | Kazanma | Ortalama puan | 95% GA |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            "| {o} | {g} | {w:.2f} % | {m:+.4f} ± {se:.4f} | [{lo:+.4f}, {hi:+.4f}] |".format(
                o=r.opponent,
                g=r.games,
                w=r.win_rate * 100.0,
                m=r.mean_points,
                se=r.standard_error,
                lo=r.lower_confidence_bound,
                hi=r.upper_confidence_bound,
            )
        )
    return "\n".join(lines)
