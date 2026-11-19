"""gnubg seviye farki (ppg) olcumu -- Faz 7-R, R-F ``m`` marji.

Neden bu modul var
------------------
``faz 7 v2.5.md`` R-F maddesi 3, "esdeger" iddiasinin esigini ``m`` ppg olarak
tanimliyor. Kullanicinin 0,02 ppg degeri **yer tutucuydu**; anlamli olmasi icin
``m``'nin olculmus bir seviye farkindan turetilmesi gerekiyor. Bu modul o farki
olcer: gnubg'nin kendi kendine oynadigi oyunlarda 0-ply / 2-ply / 3-ply
seviyeleri arasindaki ppg farki.

Iki olcum yolu
--------------
1. **Money** (birincil). gnubg'nin gomulu Python'u (``-p``) ile oyun oyun
   oynatilir; her oyunun kazananini ve puanini ``gnubg.match()`` verir. Money
   oyununda mac sonu kirpilmesi ve Crawford yoktur, bu yuzden ppg'nin en temiz
   olcumudur.
2. **Mac** (ikincil). ``new match L`` ile oynatilir; R-F zaten 5 ve 9 puanlik
   maclari ayri satir olarak istiyor. Mac sonu oyunu kirpildigi icin ppg burada
   **mac basina** bir gozlem sayilir.

Istatistik
----------
Guven araligi **kume bootstrap**'i ile hesaplanir: money'de kume = oyun, mac
oyununda kume = mac. Boylece ayni mac icindeki kup/Crawford korelasyonu yok
sayilmaz. Guc hesabinda sigma'nin **ust** siniri kullanilir (Kural 4).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml import match_power  # noqa: E402
from ml.gnubg_er import find_gnubg  # noqa: E402

PPG_VERSION = 1
PPG_PATH = "ml/artifacts/ppg_levels.json"
PPG_MD_PATH = "ml/artifacts/ppg_levels.md"

#: 0 = money oyunu; digerleri mac uzunlugu.
MONEY = 0
CONTEXTS: tuple[int, ...] = (MONEY, 5, 9)
PAIRINGS: tuple[tuple[int, int], ...] = ((0, 2), (2, 3))

DEFAULT_MONEY_GAMES = 400
DEFAULT_MATCHES = 40
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = 3600.0

BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261121

#: Kural 4: sigma ust guven sinirindan hesaplanir.
SIGMA_UPPER_FACTOR = 1.25

#: ``m`` = bu oran x olculen seviye farki (kullanicinin "yarisi" istegi).
MARGIN_FRACTION = 0.5

#: ``m`` icin alt sinir; sifir veya negatif marj anlamsizdir.
MARGIN_FLOOR = 0.001

MONEY_MARKER = "PPGJSON "
SCORE_RE = re.compile(
    r"The score \(after (\d+) games?\) is: (.+?) (\d+), (.+?) (\d+) "
    r"\(match to (\d+) points?(, Crawford game)?\)"
)
MATCH_WON_RE = re.compile(r"^(.+?) has won the match\.?$", re.MULTILINE)

#: gnubg'nin gomulu Python'unda calisan, kendine yeterli money kosucusu.
MONEY_RUNNER = '''\
import gnubg, json, time
plies0 = %(plies0)d
plies1 = %(plies1)d
games = %(games)d
seed = %(seed)d
gnubg.command("set player 0 gnubg")
gnubg.command("set player 1 gnubg")
gnubg.command("set player 0 chequerplay evaluation plies %%d" %% plies0)
gnubg.command("set player 1 chequerplay evaluation plies %%d" %% plies1)
gnubg.command("set player 0 cubedecision evaluation plies %%d" %% plies0)
gnubg.command("set player 1 cubedecision evaluation plies %%d" %% plies1)
gnubg.command("set matchlength 0")
gnubg.command("set seed %%d" %% seed)
out = []
t0 = time.time()
for _ in range(games):
    gnubg.command("new game")
    info = gnubg.match()["games"][-1]["info"]
    out.append([info["winner"], int(info["points-won"])])
print("%(marker)s" + json.dumps({"games": out, "seconds": time.time() - t0}))
'''


class PpgError(RuntimeError):
    """ppg olcumu yapilamadi."""


# ----------------------------------------------------------------------
# Cikti ayristirma
# ----------------------------------------------------------------------


def parse_score_line(line: str) -> dict[str, Any] | None:
    """Tek bir ``The score (after N games) is: ...`` satirini ayristirir."""
    m = SCORE_RE.search(line)
    if m is None:
        return None
    return {
        "games": int(m.group(1)),
        "name0": m.group(2).strip(),
        "score0": int(m.group(3)),
        "name1": m.group(4).strip(),
        "score1": int(m.group(5)),
        "length": int(m.group(6)),
        "crawford": m.group(7) is not None,
    }


@dataclass
class MatchResult:
    """Tek bir kendine-oynama macinin sonucu."""

    length: int
    names: tuple[str, str]
    scores: list[tuple[int, int]] = field(default_factory=list)
    crawford: list[bool] = field(default_factory=list)
    finished: bool = False
    winner: str | None = None

    @property
    def games(self) -> int:
        return len(self.scores)

    @property
    def per_game(self) -> list[tuple[int, int]]:
        """Oyun basina (oyuncu0, oyuncu1) puan farki."""
        out: list[tuple[int, int]] = []
        prev = (0, 0)
        for cur in self.scores:
            out.append((cur[0] - prev[0], cur[1] - prev[1]))
            prev = cur
        return out

    @property
    def final(self) -> tuple[int, int]:
        return self.scores[-1] if self.scores else (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "names": list(self.names),
            "games": self.games,
            "final": list(self.final),
            "crawfordGames": sum(1 for c in self.crawford if c),
            "finished": self.finished,
            "winner": self.winner,
            "perGame": [list(p) for p in self.per_game],
        }


def parse_match_output(text: str, *, length: int) -> MatchResult:
    """gnubg ciktisindan mac sonucunu cikarir."""
    rows = [r for r in (parse_score_line(ln) for ln in text.splitlines()) if r]
    if not rows:
        raise PpgError("skor satiri bulunamadi (mac baslamamis olabilir)")

    names = (rows[0]["name0"], rows[0]["name1"])
    result = MatchResult(length=length, names=names)
    for row in rows:
        if (row["name0"], row["name1"]) != names:
            raise PpgError(
                "oyuncu adlari mac icinde degisti: %r -> %r"
                % (names, (row["name0"], row["name1"]))
            )
        result.scores.append((row["score0"], row["score1"]))
        result.crawford.append(bool(row["crawford"]))

    won = MATCH_WON_RE.search(text)
    if won is not None:
        result.finished = True
        result.winner = won.group(1).strip()
    return result


def parse_money_output(text: str) -> list[tuple[int, int]]:
    """Money kosucusunun ciktisindan oyun basina (oyuncu0, oyuncu1) puanlari."""
    for line in text.splitlines():
        idx = line.find(MONEY_MARKER)
        if idx < 0:
            continue
        payload = json.loads(line[idx + len(MONEY_MARKER):])
        out: list[tuple[int, int]] = []
        for winner, points in payload["games"]:
            if winner == "X":
                out.append((int(points), 0))
            elif winner == "O":
                out.append((0, int(points)))
            else:
                raise PpgError("bilinmeyen kazanan: %r" % (winner,))
        return out
    raise PpgError("money kosucusu cikti vermedi (PPGJSON satiri yok)")


# ----------------------------------------------------------------------
# Kendine oynama
# ----------------------------------------------------------------------


def build_script(*, plies0: int, plies1: int, length: int, seed: int | None) -> str:
    """Mac icin gnubg komut dosyasi."""
    if length <= 0:
        raise PpgError("mac uzunlugu pozitif olmali: %r" % (length,))
    lines = [
        "set player 0 gnubg",
        "set player 1 gnubg",
        "set player 0 chequerplay evaluation plies %d" % plies0,
        "set player 1 chequerplay evaluation plies %d" % plies1,
        "set player 0 cubedecision evaluation plies %d" % plies0,
        "set player 1 cubedecision evaluation plies %d" % plies1,
    ]
    if seed is not None:
        lines.append("set seed %d" % int(seed))
    lines.append("new match %d" % length)
    lines.append("quit")
    return "\n".join(lines) + "\n"


class SelfPlaySession:
    """Iki gnubg oyuncusunu farkli derinliklerde karsilastirir."""

    def __init__(
        self,
        exe: str | Path | None = None,
        *,
        plies0: int,
        plies1: int,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        found = find_gnubg(exe)
        if found is None:
            raise PpgError("gnubg-cli bulunamadi (GNUBG_CLI ortam degiskenini ayarlayin)")
        self.exe = Path(found)
        self.plies0 = int(plies0)
        self.plies1 = int(plies1)
        self.timeout = float(timeout)

    def play_match(self, length: int, *, seed: int | None = None) -> MatchResult:
        script = build_script(
            plies0=self.plies0, plies1=self.plies1, length=length, seed=seed
        )
        try:
            proc = subprocess.run(
                [str(self.exe), "-t"],
                input=script,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - yavas makine
            raise PpgError("mac zaman asimi (%0.0f s)" % self.timeout) from exc
        text = (proc.stdout or "") + (proc.stderr or "")
        return parse_match_output(text, length=length)

    def play_money(self, games: int, *, seed: int = 1) -> list[tuple[int, int]]:
        """``games`` adet money oyunu oynatir; oyun basina puanlari doner."""
        if games <= 0:
            raise PpgError("oyun sayisi pozitif olmali: %r" % (games,))
        script = MONEY_RUNNER % {
            "plies0": self.plies0,
            "plies1": self.plies1,
            "games": int(games),
            "seed": int(seed),
            "marker": MONEY_MARKER,
        }
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8", newline="\n"
        )
        try:
            handle.write(script)
            handle.close()
            try:
                proc = subprocess.run(
                    [str(self.exe), "-p", handle.name],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:  # pragma: no cover
                raise PpgError("money kosucusu zaman asimi (%0.0f s)" % self.timeout) from exc
        finally:
            Path(handle.name).unlink(missing_ok=True)
        text = (proc.stdout or "") + (proc.stderr or "")
        return parse_money_output(text)


# ----------------------------------------------------------------------
# Istatistik
# ----------------------------------------------------------------------


def _bootstrap_ci(
    values: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Ortalamanin bootstrap guven araligi."""
    if not values:
        raise PpgError("bootstrap icin bos seri")
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    lo = means[int((alpha / 2.0) * resamples)]
    hi = means[min(resamples - 1, int((1.0 - alpha / 2.0) * resamples))]
    return float(lo), float(hi)


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mu = _mean(values)
    return float(math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1)))


@dataclass
class PairingResult:
    """Bir (plies_a, plies_b) karsilastirmasinin tek baglamdaki sonucu."""

    plies_a: int
    plies_b: int
    length: int
    clusters: int
    games: int
    crawford_games: int
    wins_a: int
    wins_b: int
    delta_ppg: float
    ci_low: float
    ci_high: float
    sigma_game: float
    sigma_cluster: float
    sigma_used: float
    cluster_kind: str = "game"

    @property
    def is_money(self) -> bool:
        return self.length == MONEY

    @property
    def context(self) -> str:
        return "money" if self.is_money else "mac-%d" % self.length

    def to_dict(self) -> dict[str, Any]:
        return {
            "pliesA": self.plies_a,
            "pliesB": self.plies_b,
            "length": self.length,
            "context": self.context,
            "clusterKind": self.cluster_kind,
            "clusters": self.clusters,
            "games": self.games,
            "crawfordGames": self.crawford_games,
            "winsA": self.wins_a,
            "winsB": self.wins_b,
            "deltaPpg": self.delta_ppg,
            "ciLow": self.ci_low,
            "ciHigh": self.ci_high,
            "sigmaGame": self.sigma_game,
            "sigmaCluster": self.sigma_cluster,
            "sigmaUsed": self.sigma_used,
        }


def summarize_clusters(
    clusters: Sequence[Sequence[float]],
    *,
    plies_a: int,
    plies_b: int,
    length: int,
    cluster_kind: str,
    crawford_games: int = 0,
    wins_a: int = 0,
    wins_b: int = 0,
) -> PairingResult:
    """Kumelerden ppg farki ve sigma'yi cikarir.

    Her kume bir gozlemdir (money'de oyun, mac oyununda mac). ``delta_ppg``
    kume ortalamalarinin ortalamasidir; mac oyununda her mac esit agirlik alir.
    """
    per_cluster: list[float] = []
    per_game: list[float] = []
    for cluster in clusters:
        if not cluster:
            continue
        per_cluster.append(_mean([float(d) for d in cluster]))
        per_game.extend(float(d) for d in cluster)
    if not per_cluster:
        raise PpgError("ozetlenecek oyun yok")

    delta = _mean(per_cluster)
    ci_low, ci_high = _bootstrap_ci(per_cluster)

    sigma_game = _std(per_game)
    mean_size = len(per_game) / len(per_cluster)
    sigma_cluster = _std(per_cluster) * math.sqrt(mean_size) if mean_size > 0 else 0.0
    sigma_used = max(sigma_game, sigma_cluster)

    return PairingResult(
        plies_a=plies_a,
        plies_b=plies_b,
        length=length,
        clusters=len(per_cluster),
        games=len(per_game),
        crawford_games=crawford_games,
        wins_a=wins_a,
        wins_b=wins_b,
        delta_ppg=delta,
        ci_low=ci_low,
        ci_high=ci_high,
        sigma_game=sigma_game,
        sigma_cluster=sigma_cluster,
        sigma_used=sigma_used,
        cluster_kind=cluster_kind,
    )


def summarize_matches(
    results: Sequence[MatchResult], *, plies_a: int, plies_b: int, length: int
) -> PairingResult:
    """Mac sonuclarindan ppg farki ve sigma'yi cikarir."""
    clusters: list[list[float]] = []
    crawford = 0
    wins_a = 0
    wins_b = 0
    for res in results:
        if res.games == 0:
            continue
        clusters.append([float(a - b) for a, b in res.per_game])
        crawford += sum(1 for c in res.crawford if c)
        if res.finished and res.winner is not None:
            if res.winner == res.names[0]:
                wins_a += 1
            elif res.winner == res.names[1]:
                wins_b += 1
    return summarize_clusters(
        clusters,
        plies_a=plies_a,
        plies_b=plies_b,
        length=length,
        cluster_kind="match",
        crawford_games=crawford,
        wins_a=wins_a,
        wins_b=wins_b,
    )


def summarize_money(
    games: Sequence[tuple[int, int]], *, plies_a: int, plies_b: int
) -> PairingResult:
    """Money oyunlarindan ppg farki ve sigma'yi cikarir."""
    clusters = [[float(a - b)] for a, b in games]
    wins_a = sum(1 for a, b in games if a > b)
    wins_b = sum(1 for a, b in games if b > a)
    return summarize_clusters(
        clusters,
        plies_a=plies_a,
        plies_b=plies_b,
        length=MONEY,
        cluster_kind="game",
        wins_a=wins_a,
        wins_b=wins_b,
    )


def sigma_upper(sigma: float, *, factor: float = SIGMA_UPPER_FACTOR) -> float:
    """Kural 4: guc hesabinda sigma'nin **ust** siniri kullanilir."""
    if sigma < 0.0:
        raise PpgError("sigma negatif olamaz: %r" % (sigma,))
    return float(sigma * factor)


def derive_margin(delta_ppg: float, ci_low: float, ci_high: float) -> tuple[float, str]:
    """Olculen seviye farkindan ``m`` marjini turetir.

    ``m = MARGIN_FRACTION * |fark|``; taban **nokta tahminidir**. ``m`` seviye
    farkinin bir ozelligidir, olcum hassasiyetinin degil: GA'yi tabana
    koymak, daha cok oyun oynandikca marji kucultup R-F'nin maliyetini
    yapay olarak dusururdu. GA bunun yerine **guvenilirlik notu** olarak
    raporlanir: sifiri disliyorsa ``m`` saglamdir, iceriyorsa gecicidir ve
    gereken oyun sayisi ayrica verilir.
    """
    if delta_ppg == 0.0:
        return MARGIN_FLOOR, "fark-sifir"
    crosses = ci_low <= 0.0 <= ci_high
    note = (
        "GA sifiri iceriyor: m GECICI, olcum gucsuz"
        if crosses
        else "GA sifiri disliyor: m saglam"
    )
    return max(MARGIN_FLOOR, MARGIN_FRACTION * abs(delta_ppg)), note


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


def measure_money(
    exe: str | Path | None,
    *,
    plies_a: int,
    plies_b: int,
    games: int,
    seed: int = 1,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
) -> PairingResult:
    """``games`` money oyununu (paralel) oynatip ozetler."""
    if games <= 0:
        raise PpgError("oyun sayisi pozitif olmali: %r" % (games,))
    session = SelfPlaySession(exe, plies0=plies_a, plies1=plies_b, timeout=timeout)

    workers = max(1, min(workers, games))
    base = games // workers
    extra = games % workers
    chunks = [base + (1 if i < extra else 0) for i in range(workers)]
    chunks = [c for c in chunks if c > 0]

    def one(i: int) -> list[tuple[int, int]]:
        return session.play_money(chunks[i], seed=seed + i)

    if len(chunks) == 1:
        batches = [one(0)]
    else:
        with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
            batches = list(pool.map(one, range(len(chunks))))

    all_games = [g for batch in batches for g in batch]
    return summarize_money(all_games, plies_a=plies_a, plies_b=plies_b)


def measure_matches(
    exe: str | Path | None,
    *,
    plies_a: int,
    plies_b: int,
    length: int,
    matches: int,
    seed: int = 0,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
) -> PairingResult:
    """``matches`` adet maci (paralel) oynatip ozetler."""
    if matches <= 0:
        raise PpgError("mac sayisi pozitif olmali: %r" % (matches,))
    session = SelfPlaySession(exe, plies0=plies_a, plies1=plies_b, timeout=timeout)

    def one(i: int) -> MatchResult:
        return session.play_match(length, seed=seed + i if seed else None)

    if workers <= 1:
        results = [one(i) for i in range(matches)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(one, range(matches)))

    return summarize_matches(results, plies_a=plies_a, plies_b=plies_b, length=length)


@dataclass
class PpgReport:
    """Tum karsilastirmalarin raporu."""

    money_games: int
    matches_per_cell: int
    workers: int
    pairings: list[PairingResult] = field(default_factory=list)
    margin: float = 0.0
    margin_note: str = ""
    margin_source: str = ""
    required_games: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PPG_VERSION,
            "moneyGames": self.money_games,
            "matchesPerCell": self.matches_per_cell,
            "workers": self.workers,
            "margin": self.margin,
            "marginNote": self.margin_note,
            "marginSource": self.margin_source,
            "requiredGames": self.required_games,
            "pairings": [p.to_dict() for p in self.pairings],
        }


def build_report(
    pairings: Sequence[PairingResult],
    *,
    money_games: int,
    matches_per_cell: int,
    workers: int,
    margin_source: str | None = None,
) -> PpgReport:
    """Marji ve gereken oyun sayisini hesaplayarak raporu kurar."""
    if not pairings:
        raise PpgError("rapor icin karsilastirma yok")

    # Deterministik sira: marj kaynagi secimi girdi sirasina bagli kalmamali.
    pairings = sorted(pairings, key=lambda p: (p.plies_a, p.plies_b, p.length))

    if margin_source is not None:
        chosen = None
        for p in pairings:
            if p.context == margin_source:
                chosen = p
                break
        if chosen is None:
            raise PpgError("marj kaynagi bulunamadi: %r" % (margin_source,))
    else:
        money = [p for p in pairings if p.is_money]
        chosen = money[0] if money else max(pairings, key=lambda p: p.length)

    margin, note = derive_margin(chosen.delta_ppg, chosen.ci_low, chosen.ci_high)
    report = PpgReport(
        money_games=money_games,
        matches_per_cell=matches_per_cell,
        workers=workers,
        pairings=list(pairings),
        margin=margin,
        margin_note=note,
        margin_source="%d-ply vs %d-ply @ %s"
        % (chosen.plies_a, chosen.plies_b, chosen.context),
    )

    for p in pairings:
        key = "%d-%d@%s" % (p.plies_a, p.plies_b, p.context)
        report.required_games[key] = match_power.required_games_ppg(
            sigma_upper(p.sigma_used), margin
        )
    return report


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


def _tr(value: float, digits: int = 4) -> str:
    return ("%0.*f" % (digits, value)).replace(".", ",")


def build_markdown(report: PpgReport, *, title: str = "Faz 7-R - Seviye farki (ppg) olcumu") -> str:
    lines = ["# " + title, ""]
    lines.append(
        "gnubg kendine-oynama. Money: **%d** oyun/hucre. Mac: **%d** mac/hucre. "
        "**%d** paralel isci." % (report.money_games, report.matches_per_cell, report.workers)
    )
    lines.append("")
    lines.append(
        "Guven araligi kume bootstrap'i (%d yeniden ornekleme): money'de kume = oyun, "
        "mac oyununda kume = mac." % BOOTSTRAP_RESAMPLES
    )
    lines.append("")
    lines.append("## Karsilastirmalar")
    lines.append("")
    lines.append(
        "| Karsilastirma | Baglam | Kume | Oyun | Fark (ppg) | %95 GA | sigma (oyun) "
        "| sigma (kume) | sigma (kullanilan) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for p in report.pairings:
        lines.append(
            "| %d-ply vs %d-ply | %s | %d | %d | %s | [%s; %s] | %s | %s | %s |"
            % (
                p.plies_a,
                p.plies_b,
                p.context,
                p.clusters,
                p.games,
                _tr(p.delta_ppg),
                _tr(p.ci_low),
                _tr(p.ci_high),
                _tr(p.sigma_game),
                _tr(p.sigma_cluster),
                _tr(p.sigma_used),
            )
        )
    lines.append("")
    lines.append("## Turetilen marj")
    lines.append("")
    lines.append("- Kaynak: **%s**" % report.margin_source)
    lines.append("- Yontem: %s" % report.margin_note)
    lines.append(
        "- **m = %s ppg** (olculen farkin %s kati)"
        % (_tr(report.margin), _tr(MARGIN_FRACTION, 2))
    )
    lines.append("")
    lines.append("## Gereken oyun sayisi (sigma ust siniri, Kural 4)")
    lines.append("")
    lines.append("| Hucre | Gereken oyun |")
    lines.append("|---|---|")
    for key, n in report.required_games.items():
        lines.append("| %s | %d |" % (key, n))
    lines.append("")
    lines.append("## Sinirlar")
    lines.append("")
    lines.append(
        "- Bu bir **seviye farki** olcumudur (gnubg'ye karsi gnubg), insan "
        "sampiyona karsi bir iddia degildir."
    )
    lines.append(
        "- Mac oyununda mac sonu oyunu kirpilir; ppg mac basina gozlem sayilir."
    )
    lines.append(
        "- 4-ply chequerplay bu makinede oyun basina 60 s'yi astigi icin ikincil "
        "karsilastirma 2-ply vs 3-ply olarak olculdu."
    )
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _parse_ints(text: str) -> tuple[int, ...]:
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise PpgError("liste bos")
    return tuple(out)


def _parse_pairings(text: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        a, b = part.split("-")
        out.append((int(a), int(b)))
    if not out:
        raise PpgError("plies cifti listesi bos")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ppg_measure",
        description="gnubg seviye farki (ppg) olcumu -- Faz 7-R R-F marji",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("measure", help="kendine-oynama olcumunu calistir")
    m.add_argument("--gnubg", default=None, help="gnubg-cli yolu")
    m.add_argument("--money-games", type=int, default=DEFAULT_MONEY_GAMES)
    m.add_argument("--matches", type=int, default=DEFAULT_MATCHES)
    m.add_argument("--contexts", default="0,5,9", help="0=money, digerleri mac uzunlugu")
    m.add_argument("--pairings", default="0-2,2-3", help="plies ciftleri")
    m.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    m.add_argument("--margin-source", default=None, help="marj icin baglam etiketi")
    m.add_argument(
        "--merge",
        action="store_true",
        help="--out varsa yukle ve yalnizca yeniden olculen hucreleri degistir",
    )
    m.add_argument("--out", default=PPG_PATH)
    m.add_argument("--md", default=PPG_MD_PATH)

    r = sub.add_parser("report", help="kayitli olcumden markdown uret")
    r.add_argument("--in", dest="src", default=PPG_PATH)
    r.add_argument("--md", default=PPG_MD_PATH)
    r.add_argument("--margin-source", default=None, help="marj icin baglam etiketi")
    return parser


def _load_report(path: Path) -> PpgReport:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairings = [
        PairingResult(
            plies_a=int(p["pliesA"]),
            plies_b=int(p["pliesB"]),
            length=int(p["length"]),
            clusters=int(p.get("clusters", 0)),
            games=int(p["games"]),
            crawford_games=int(p.get("crawfordGames", 0)),
            wins_a=int(p.get("winsA", 0)),
            wins_b=int(p.get("winsB", 0)),
            delta_ppg=float(p["deltaPpg"]),
            ci_low=float(p["ciLow"]),
            ci_high=float(p["ciHigh"]),
            sigma_game=float(p["sigmaGame"]),
            sigma_cluster=float(p["sigmaCluster"]),
            sigma_used=float(p["sigmaUsed"]),
            cluster_kind=str(p.get("clusterKind", "game")),
        )
        for p in data.get("pairings", [])
    ]
    return PpgReport(
        money_games=int(data.get("moneyGames", 0)),
        matches_per_cell=int(data.get("matchesPerCell", 0)),
        workers=int(data.get("workers", 0)),
        pairings=pairings,
        margin=float(data.get("margin", 0.0)),
        margin_note=str(data.get("marginNote", "")),
        margin_source=str(data.get("marginSource", "")),
        required_games={k: int(v) for k, v in (data.get("requiredGames") or {}).items()},
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "report":
        stored = _load_report(Path(args.src))
        # Marji ve gereken oyun sayisini guncel kodla yeniden hesapla.
        report = build_report(
            stored.pairings,
            money_games=stored.money_games,
            matches_per_cell=stored.matches_per_cell,
            workers=stored.workers,
            margin_source=args.margin_source,
        )
        Path(args.src).write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        Path(args.md).write_text(build_markdown(report), encoding="utf-8")
        print("m = %.4f ppg (%s)" % (report.margin, report.margin_note))
        print("kaynak: %s" % report.margin_source)
        print("yazildi: %s" % args.md)
        return 0

    contexts = _parse_ints(args.contexts)
    pairings = _parse_pairings(args.pairings)

    results: list[PairingResult] = []
    for a, b in pairings:
        for ctx in contexts:
            if ctx == MONEY:
                print("olculuyor: %d-ply vs %d-ply @ money (%d oyun)" % (a, b, args.money_games))
                res = measure_money(
                    args.gnubg,
                    plies_a=a,
                    plies_b=b,
                    games=args.money_games,
                    seed=args.seed,
                    workers=args.workers,
                    timeout=args.timeout,
                )
            else:
                print("olculuyor: %d-ply vs %d-ply @ %d puan (%d mac)" % (a, b, ctx, args.matches))
                res = measure_matches(
                    args.gnubg,
                    plies_a=a,
                    plies_b=b,
                    length=ctx,
                    matches=args.matches,
                    seed=args.seed,
                    workers=args.workers,
                    timeout=args.timeout,
                )
            print(
                "  fark=%0.4f ppg GA=[%0.4f; %0.4f] sigma=%0.4f oyun=%d"
                % (res.delta_ppg, res.ci_low, res.ci_high, res.sigma_used, res.games)
            )
            results.append(res)

    if args.merge and Path(args.out).is_file():
        previous = _load_report(Path(args.out))
        fresh = {(p.plies_a, p.plies_b, p.length) for p in results}
        kept = [
            p
            for p in previous.pairings
            if (p.plies_a, p.plies_b, p.length) not in fresh
        ]
        results = kept + results
        print("birlestirildi: %d korunan + %d yeni hucre" % (len(kept), len(fresh)))

    report = build_report(
        results,
        money_games=args.money_games,
        matches_per_cell=args.matches,
        workers=args.workers,
        margin_source=args.margin_source,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.md).write_text(build_markdown(report), encoding="utf-8")
    print("m = %0.4f ppg (%s)" % (report.margin, report.margin_note))
    print("yazildi: %s" % args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
