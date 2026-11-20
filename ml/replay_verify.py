"""K2 - kayitli oyunlarin yeniden oynatma dogrulamasi.

Soru: ``_single_step_uses_die`` hatasi (buyuk-zar filtresi her tek-adimli
sonucu atiyordu) **uretilmis** veriye sizdi mi? Adim 0'da hata kosulunun
kendi zarinda %0 tetiklendigi olculdu, ama bu bir *hayatta kalma yanliligi*
olabilir: hata tetiklendiginde aday kumesi bosalir, oyun "pas" olarak
kaydedilir ve o karar egitimden **sessizce duser**. Yani kayitli veri temiz
gorunur cunku kirlenen kararlar hic yazilmamis olabilir.

Bu modul kayitli shard'lari okur ve **kaydin kendi ic tutarliligini** denetler:

* ``pass_with_candidates``  - pas kaydedilmis ama ``candidateTotal != 1``.
  **Beklenen deger 1'dir**: ``BackgammonSearch.SearchNode`` yasal hamle
  yokken listeye bir *pas afterstate'i* ekler (``list.AddPass(s)``), yani
  ``CandidateCount == 1``. 1'den buyuk deger "yasal hamle varken pas"
  demektir; hata sizintisinin dogrudan kanitidir.
* ``move_without_candidates`` - hamle kaydedilmis ama aday yok.
* ``chosen_not_in_candidates`` - secilen vektor aday kumesinde degil
  (yalnizca ``logged == candidateTotal`` iken denetlenir; ``dup_cap``
  kesilmis kumelerde secilen aday loglanmamis olabilir).
* ``pass_without_candidates`` - pas kaydedilmis ve ``candidateTotal == 1``
  (beklenen durum).

Karar: ``pass_with_candidates == 0`` ise korpus **temiz**, yeniden uretim
gerekmez. Aksi halde etkilenen oyun sayisi raporlanir.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

import shards

#: Secilen vektorun aday kumesinde sayilmasi icin tolerans. Vektorler float32
#: oldugu icin tam esitlik beklenmez; 1e-5 fazlasiyla siki.
CHOSEN_TOL = 1e-5

VERIFY_PATH = "ml/artifacts/replay_verify.json"
VERIFY_MD_PATH = "ml/artifacts/replay_verify.md"


@dataclass
class VerifyCounts:
    """Tek bir shard (veya toplam) icin sayaclar."""

    shards: int = 0
    games: int = 0
    decisions: int = 0
    passes: int = 0
    moves: int = 0
    pass_with_candidates: int = 0
    pass_without_candidates: int = 0
    move_without_candidates: int = 0
    chosen_not_in_candidates: int = 0
    chosen_checked: int = 0
    chosen_is_terminal: int = 0
    #: Pas kararlarinda gorulen ``candidateTotal`` dagilimi.
    pass_candidate_total_hist: dict[int, int] = field(default_factory=dict)
    #: ``pass_with_candidates`` gorulen oyun kimlikleri (ornek, ilk 20).
    affected_games: list[int] = field(default_factory=list)

    def add(self, other: "VerifyCounts") -> None:
        self.shards += other.shards
        self.games += other.games
        self.decisions += other.decisions
        self.passes += other.passes
        self.moves += other.moves
        self.pass_with_candidates += other.pass_with_candidates
        self.pass_without_candidates += other.pass_without_candidates
        self.move_without_candidates += other.move_without_candidates
        self.chosen_not_in_candidates += other.chosen_not_in_candidates
        self.chosen_checked += other.chosen_checked
        self.chosen_is_terminal += other.chosen_is_terminal
        for total, n in other.pass_candidate_total_hist.items():
            self.pass_candidate_total_hist[total] = (
                self.pass_candidate_total_hist.get(total, 0) + n
            )
        for gid in other.affected_games:
            if len(self.affected_games) < 20 and gid not in self.affected_games:
                self.affected_games.append(gid)

    @property
    def clean(self) -> bool:
        """Korpus temiz mi? (pas-varken-hamle ve hamle-varken-aday-yok sifir)."""
        return (
            self.pass_with_candidates == 0
            and self.move_without_candidates == 0
            and self.chosen_not_in_candidates == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifyVersion": 1,
            "shards": self.shards,
            "games": self.games,
            "decisions": self.decisions,
            "passes": self.passes,
            "moves": self.moves,
            "passWithCandidates": self.pass_with_candidates,
            "passWithoutCandidates": self.pass_without_candidates,
            "moveWithoutCandidates": self.move_without_candidates,
            "chosenNotInCandidates": self.chosen_not_in_candidates,
            "chosenChecked": self.chosen_checked,
            "chosenIsTerminal": self.chosen_is_terminal,
            "passCandidateTotalHist": {
                str(k): v for k, v in sorted(self.pass_candidate_total_hist.items())
            },
            "affectedGames": list(self.affected_games),
            "clean": self.clean,
        }


def _chosen_in_candidates(chosen: np.ndarray, cands: np.ndarray) -> bool:
    """``chosen`` aday satirlarindan biriyle (tolerans icinde) eslesiyor mu?"""
    if cands.shape[0] == 0:
        return False
    diff = np.max(np.abs(cands - chosen.reshape(1, -1)), axis=1)
    return bool(np.min(diff) <= CHOSEN_TOL)


def verify_games(games: Iterable[shards.GameRecord]) -> VerifyCounts:
    """Bir oyun akisini denetler."""
    counts = VerifyCounts()
    for game in games:
        counts.games += 1
        game_flagged = False
        for dec in game.decisions:
            counts.decisions += 1
            total = int(dec.candidate_total)
            logged = int(dec.logged_count)
            if dec.chosen_is_terminal:
                counts.chosen_is_terminal += 1
            if dec.is_pass:
                counts.passes += 1
                counts.pass_candidate_total_hist[total] = (
                    counts.pass_candidate_total_hist.get(total, 0) + 1
                )
                # Beklenen: yalnizca pas afterstate'i (CandidateCount == 1).
                if total != 1:
                    counts.pass_with_candidates += 1
                    game_flagged = True
                else:
                    counts.pass_without_candidates += 1
                continue
            counts.moves += 1
            if total == 0:
                counts.move_without_candidates += 1
                game_flagged = True
                continue
            # Secilen aday kumesinde mi? Yalnizca kesilmemis kumelerde anlamli.
            if (
                dec.chosen_vector is not None
                and dec.cand_vectors is not None
                and logged == total
            ):
                counts.chosen_checked += 1
                if not _chosen_in_candidates(dec.chosen_vector, dec.cand_vectors):
                    counts.chosen_not_in_candidates += 1
                    game_flagged = True
        if game_flagged and len(counts.affected_games) < 20:
            counts.affected_games.append(int(game.game_id))
    return counts


def verify_shard(path: str | Path) -> VerifyCounts:
    """Tek bir shard dosyasini denetler."""
    _, games = shards.read_shard(path)
    counts = verify_games(games)
    counts.shards = 1
    return counts


def verify_shard_dir(
    directory: str | Path,
    *,
    pattern: str = "*.bgsp*",
    limit: int = 0,
    progress: bool = False,
) -> VerifyCounts:
    """Bir dizindeki shard'lari (istege bagli olarak ilk ``limit`` tanesini) denetler."""
    root = Path(directory)
    files = sorted(root.rglob(pattern))
    if limit > 0:
        files = files[:limit]
    total = VerifyCounts()
    for index, path in enumerate(files, start=1):
        if progress:
            print("[%d/%d] %s" % (index, len(files), path.name), file=sys.stderr)
        total.add(verify_shard(path))
    return total


def build_markdown(counts: VerifyCounts, *, source: str) -> str:
    lines = [
        "# K2 - Kayitli oyunlarin yeniden oynatma dogrulamasi",
        "",
        "Soru: `_single_step_uses_die` hatasi **uretilmis** veriye sizdi mi?",
        "",
        "Kaynak: `%s`" % source,
        "",
        "| Olcum | Deger |",
        "|---|---|",
        "| Shard | %d |" % counts.shards,
        "| Oyun | %d |" % counts.games,
        "| Karar | %d |" % counts.decisions,
        "| Pas | %d |" % counts.passes,
        "| Hamle | %d |" % counts.moves,
        "| **Pas kaydi var, aday sayisi != 1** | **%d** |" % counts.pass_with_candidates,
        "| Pas kaydi var, aday sayisi == 1 (beklenen) | %d |"
        % counts.pass_without_candidates,
        "| Hamle kaydi var, aday yok | %d |" % counts.move_without_candidates,
        "| Secilen aday kumesinde degil | %d / %d |"
        % (counts.chosen_not_in_candidates, counts.chosen_checked),
        "| Secilen terminal | %d |" % counts.chosen_is_terminal,
        "",
        "Pas kararlarinda `candidateTotal` dagilimi: %s"
        % (
            ", ".join(
                "%d -> %d" % (k, v)
                for k, v in sorted(counts.pass_candidate_total_hist.items())
            )
            or "(pas yok)"
        ),
        "",
        "**Karar: %s**" % ("KORPUS TEMIZ" if counts.clean else "KIRLI - YENIDEN URETIM GEREKIR"),
        "",
    ]
    if counts.affected_games:
        lines.append(
            "Etkilenen oyun kimlikleri (ilk 20): %s"
            % ", ".join(str(g) for g in counts.affected_games)
        )
        lines.append("")
    lines.extend(
        [
            "**Yontem.** Her karar icin `candidateTotal` ile `DEC_IS_PASS` bayragi",
            "karsilastirilir. `BackgammonSearch.SearchNode` yasal hamle yokken listeye",
            "bir pas afterstate'i ekledigi icin (`list.AddPass(s)`) pas kararinin",
            "`CandidateCount` degeri **1**'dir; beklenen budur. Hata tetiklendiginde",
            "aday kumesi bosalir ve oyun pas yazar; bu yuzden",
            "`pass_with_candidates > 0` (yani `candidateTotal != 1`) hatanin",
            "**dogrudan** kanitidir. `chosen_not_in_candidates` yalnizca",
            "`logged == candidateTotal` iken denetlenir (dup_cap kesilmis kumelerde",
            "secilen aday loglanmamis olabilir).",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="K2: kayitli oyun yeniden oynatma dogrulamasi")
    p.add_argument("--shard-dir", required=True, help="shard kok dizini")
    p.add_argument("--pattern", default="*.bgsp*")
    p.add_argument("--limit", type=int, default=0, help="ilk N shard (0 = hepsi)")
    p.add_argument("--out", default=VERIFY_PATH)
    p.add_argument("--markdown", default=VERIFY_MD_PATH)
    p.add_argument("--progress", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    counts = verify_shard_dir(
        args.shard_dir, pattern=args.pattern, limit=args.limit, progress=args.progress
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(counts.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        build_markdown(counts, source=str(args.shard_dir)) + "\n", encoding="utf-8"
    )
    print("shard: %d, oyun: %d, karar: %d" % (counts.shards, counts.games, counts.decisions))
    print(
        "pas+aday: %d, hamle-aday-yok: %d, secilen-aday-disi: %d/%d"
        % (
            counts.pass_with_candidates,
            counts.move_without_candidates,
            counts.chosen_not_in_candidates,
            counts.chosen_checked,
        )
    )
    print("karar: %s" % ("KORPUS TEMIZ" if counts.clean else "KIRLI"))
    return 0 if counts.clean else 1


if __name__ == "__main__":
    sys.exit(main())
