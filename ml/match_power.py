"""Faz 7: mac seviyesinde guc analizi (dis inceleme madde 1.4).

Neden bu modul? Inceleme iki seyi dogru tespit etti:

1. **Kazanma orani icin guc analizi yok.** 400 oyunda ``±%5`` guven araligi
   vardir; "2-away %40,0 vs %39,5" ifadesi **gurultudur**, olcum degil.
2. **ppg (puan/oyun) olcumu yok.** Kazanma orani tek basina gucu anlatmaz:
   ayni kazanma oraniyla mars oranini artiran bir model daha gucludur. ppg
   bunu yakalar.

Bu modul iki seviyede guc hesabi yapar:

* **Oyun seviyesi** — kazanma orani (oran testi) ve ppg (ortalama testi).
* **Mac seviyesi** — mac kazanma olasiligi (oran testi) ve MET'ten MWC okuma.

Hicbir sayi "iddia" degildir; her biri **gerekli n** ve **saptanabilir etki**
olarak yazilir. Bir iddia, gucu yetmiyorsa kanitlanmis sayilmaz.

Kullanim::

    python ml/match_power.py --sigma 2.4 --win-rate 0.55 --json out.json
    python ml/match_power.py --eval ml/artifacts/stage_h_eval_pip.json --markdown out.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

#: Iki yonlu %95 guven duzeyi.
Z_TWO_SIDED = 1.959963984540054
#: Tek yonlu %95.
Z_ONE_SIDED = 1.6448536269514722
#: Varsayilan test gucu.
DEFAULT_POWER = 0.80
#: Varsayilan anlamlilik duzeyi.
DEFAULT_ALPHA = 0.05
#: Faz 6'da kullanilan oyun sayisi (karsilastirma tabani).
STAGE_H_GAMES = 400
#: Incelemenin isaret ettigi gurultu esigi.
NOISE_HALF_WIDTH = 0.05
#: Incelemenin ornekledigi "iddia edilen fark": 2-away %40,0 vs %39,5.
#: Yarim genislik bunun uzerindeyse fark **gurultudur**.
CLAIMED_DELTA = 0.005
#: ppg dagiliminin tipik standart sapmasi (Faz 6 ``meanPoints`` olcumlerinden
#: kaba tahmin; gercek deger ``--sigma`` ile verilmelidir).
DEFAULT_PPG_SIGMA = 2.4
#: MET dosyasi (Rockwell-Kazaross).
MET_PATH = REPO_ROOT / "Backgammon.Core" / "Match" / "met_rk.json"


# ----------------------------------------------------------------------
# z yardimcilari
# ----------------------------------------------------------------------


def z_for_power(power: float) -> float:
    """``z_{1-beta}`` (tek yonlu)."""
    if not 0.5 < power < 1.0:
        raise ValueError("power 0,5 ile 1,0 arasinda olmali: %r" % (power,))
    return NormalDist().inv_cdf(power)


def z_for_alpha(alpha: float, *, two_sided: bool = True) -> float:
    """``z_{1-alpha/2}`` (iki yonlu) veya ``z_{1-alpha}`` (tek yonlu)."""
    if not 0.0 < alpha < 0.5:
        raise ValueError("alpha 0 ile 0,5 arasinda olmali: %r" % (alpha,))
    return NormalDist().inv_cdf(1.0 - (alpha / 2.0 if two_sided else alpha))


# ----------------------------------------------------------------------
# Oran (kazanma orani) gucu
# ----------------------------------------------------------------------


def win_rate_half_width(p: float, n: int, *, z: float = Z_TWO_SIDED) -> float:
    """``n`` oyunda kazanma orani icin Wald guven araligi yari genisligi."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("p 0..1 olmali: %r" % (p,))
    if n <= 0:
        raise ValueError("n pozitif olmali: %r" % (n,))
    return float(z * math.sqrt(p * (1.0 - p) / n))


def required_games_win_rate(
    p: float, half_width: float, *, z: float = Z_TWO_SIDED
) -> int:
    """``half_width`` yari genisligi icin gereken oyun sayisi."""
    if not 0.0 < p < 1.0:
        raise ValueError("p 0 ile 1 arasinda olmali: %r" % (p,))
    if half_width <= 0.0:
        raise ValueError("half_width pozitif olmali: %r" % (half_width,))
    return int(math.ceil((z * z) * p * (1.0 - p) / (half_width * half_width)))


def required_games_two_proportions(
    p0: float,
    p1: float,
    *,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> int:
    """Iki oran testi icin **kol basina** gereken oyun sayisi.

    ``p0`` referans (sampiyon), ``p1`` bizim oranimiz. Formul:
    ``n = (z_a*sqrt(2*pbar*(1-pbar)) + z_b*sqrt(p0(1-p0)+p1(1-p1)))^2 / (p1-p0)^2``.
    """
    if not (0.0 < p0 < 1.0 and 0.0 < p1 < 1.0):
        raise ValueError("p0 ve p1 0 ile 1 arasinda olmali")
    delta = abs(p1 - p0)
    if delta <= 0.0:
        raise ValueError("p0 ve p1 farkli olmali")
    pbar = (p0 + p1) / 2.0
    za = z_for_alpha(alpha)
    zb = z_for_power(power)
    num = (
        za * math.sqrt(2.0 * pbar * (1.0 - pbar))
        + zb * math.sqrt(p0 * (1.0 - p0) + p1 * (1.0 - p1))
    ) ** 2
    return int(math.ceil(num / (delta * delta)))


# ----------------------------------------------------------------------
# Ortalama (ppg) gucu
# ----------------------------------------------------------------------


def ppg_half_width(sigma: float, n: int, *, z: float = Z_TWO_SIDED) -> float:
    """``n`` oyunda ppg icin guven araligi yari genisligi."""
    if sigma <= 0.0:
        raise ValueError("sigma pozitif olmali: %r" % (sigma,))
    if n <= 0:
        raise ValueError("n pozitif olmali: %r" % (n,))
    return float(z * sigma / math.sqrt(n))


def required_games_ppg(sigma: float, half_width: float, *, z: float = Z_TWO_SIDED) -> int:
    """``half_width`` yari genisligi icin gereken oyun sayisi (ppg)."""
    if sigma <= 0.0:
        raise ValueError("sigma pozitif olmali: %r" % (sigma,))
    if half_width <= 0.0:
        raise ValueError("half_width pozitif olmali: %r" % (half_width,))
    return int(math.ceil((z * sigma / half_width) ** 2))


def required_games_two_means(
    sigma: float,
    delta: float,
    *,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> int:
    """Iki ortalama testi icin **kol basina** gereken oyun sayisi.

    ``n = 2 * (z_a + z_b)^2 * sigma^2 / delta^2``.
    """
    if sigma <= 0.0:
        raise ValueError("sigma pozitif olmali: %r" % (sigma,))
    if delta <= 0.0:
        raise ValueError("delta pozitif olmali: %r" % (delta,))
    za = z_for_alpha(alpha)
    zb = z_for_power(power)
    return int(math.ceil(2.0 * (za + zb) ** 2 * sigma * sigma / (delta * delta)))


def detectable_ppg(sigma: float, n: int, *, z: float = Z_TWO_SIDED) -> float:
    """``n`` oyunda ppg'de saptanabilir en kucuk fark (yari genislik)."""
    return ppg_half_width(sigma, n, z=z)


def detectable_win_rate(p: float, n: int, *, z: float = Z_TWO_SIDED) -> float:
    """``n`` oyunda kazanma oraninda saptanabilir en kucuk fark."""
    return win_rate_half_width(p, n, z=z)


# ----------------------------------------------------------------------
# Mac seviyesi
# ----------------------------------------------------------------------


def required_matches(p: float, half_width: float, *, z: float = Z_TWO_SIDED) -> int:
    """Mac kazanma olasiligi icin gereken **mac** sayisi."""
    return required_games_win_rate(p, half_width, z=z)


def load_met(path: Path | None = None) -> dict[str, Any]:
    """Rockwell-Kazaross MET'ini okur."""
    p = Path(path) if path is not None else MET_PATH
    if not p.is_file():
        raise FileNotFoundError("MET yok: " + str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def mwc_from_met(away_self: int, away_opp: int, *, met: dict[str, Any] | None = None) -> float:
    """``away_self``/``away_opp`` icin mac kazanma sansi (MWC).

    ``table[a][b]`` = biz ``a`` uzaktayken, rakip ``b`` uzaktayken MWC.
    ``a = 0`` "biz bitirdik" demektir (MWC = 1,0).
    """
    data = met if met is not None else load_met()
    table = data["table"]
    limit = int(data.get("maxMatchLength", len(table) - 1))
    for name, value in (("away_self", away_self), ("away_opp", away_opp)):
        if not 0 <= int(value) <= limit:
            raise ValueError("%s 0..%d olmali: %r" % (name, limit, value))
    return float(table[int(away_self)][int(away_opp)])


# ----------------------------------------------------------------------
# Artifact okuma
# ----------------------------------------------------------------------


def ppg_from_eval(data: dict[str, Any] | None, *, opponent: str | None = None) -> float | None:
    """``--eval-json`` ciktisindan ppg (``meanPoints``)."""
    if not data:
        return None
    for report in data.get("reports", []):
        name = str(report.get("opponent", ""))
        if opponent is not None and opponent.lower() not in name.lower():
            continue
        value = report.get("meanPoints")
        if value is not None:
            return float(value)
    return None


def games_from_eval(data: dict[str, Any] | None, *, opponent: str | None = None) -> int | None:
    """``--eval-json`` ciktisindan oyun sayisi."""
    if not data:
        return None
    for report in data.get("reports", []):
        name = str(report.get("opponent", ""))
        if opponent is not None and opponent.lower() not in name.lower():
            continue
        value = report.get("games")
        if value is not None:
            return int(value)
    return None


# ----------------------------------------------------------------------
# Rapor
# ----------------------------------------------------------------------


@dataclass
class PowerReport:
    """Guc analizi ozeti."""

    win_rate: float
    ppg_sigma: float
    games: int
    win_rate_half_width: float
    ppg_half_width: float
    noise_floor: list[dict[str, Any]] = field(default_factory=list)
    required: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "winRate": self.win_rate,
            "ppgSigma": self.ppg_sigma,
            "games": self.games,
            "winRateHalfWidth": self.win_rate_half_width,
            "ppgHalfWidth": self.ppg_half_width,
            "noiseFloor": self.noise_floor,
            "required": self.required,
            "notes": self.notes,
        }


#: Gurultu tablosunda gosterilecek oyun sayilari.
NOISE_FLOOR_GAMES = (100, 200, 400, 1000, 5000, 20000, 100000)


def noise_floor(
    win_rate: float, sigma: float, *, games: Iterable[int] = NOISE_FLOOR_GAMES
) -> list[dict[str, Any]]:
    """Her oyun sayisi icin saptanabilir en kucuk fark (kazanma orani ve ppg)."""
    rows: list[dict[str, Any]] = []
    for n in games:
        n = int(n)
        if n <= 0:
            continue
        rows.append(
            {
                "games": n,
                "winRateHalfWidth": win_rate_half_width(win_rate, n),
                "ppgHalfWidth": ppg_half_width(sigma, n),
            }
        )
    return rows


def build_report(
    *,
    win_rate: float = 0.55,
    ppg_sigma: float = DEFAULT_PPG_SIGMA,
    games: int = STAGE_H_GAMES,
    champion_win_rate: float = 0.50,
    ppg_delta: float = 0.10,
    claimed_delta: float = CLAIMED_DELTA,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> PowerReport:
    """Guc analizi raporu uretir."""
    hw_wr = win_rate_half_width(win_rate, games)
    hw_ppg = ppg_half_width(ppg_sigma, games)
    required = {
        "gamesForWinRateHalfWidth5pct": required_games_win_rate(win_rate, NOISE_HALF_WIDTH),
        "gamesForPpgHalfWidth0_10": required_games_ppg(ppg_sigma, 0.10),
        "gamesForPpgHalfWidth0_05": required_games_ppg(ppg_sigma, 0.05),
        "gamesPerArmWinRateVsChampion": required_games_two_proportions(
            champion_win_rate, win_rate, alpha=alpha, power=power
        ),
        "gamesPerArmPpgVsChampion": required_games_two_means(
            ppg_sigma, ppg_delta, alpha=alpha, power=power
        ),
        "matchesForMatchWinRateHalfWidth5pct": required_matches(win_rate, NOISE_HALF_WIDTH),
    }
    notes = [
        "%d oyunda kazanma orani icin GA yari genisligi %.4f (incelemenin isaret "
        "ettigi gurultu esigi %.2f)." % (games, hw_wr, NOISE_HALF_WIDTH),
        "%d oyunda ppg icin GA yari genisligi %.4f (sigma = %.2f)." % (games, hw_ppg, ppg_sigma),
        "ppg olculmeden yalnizca kazanma oranina bakmak, mars oranini artiran bir "
        "modeli oldugundan **zayif** gosterir.",
    ]
    if hw_wr > NOISE_HALF_WIDTH:
        notes.append(
            "%d oyun %s esiginin ALTINDA: bu hacimde '%%40,0 vs %%39,5' gibi bir "
            "fark **gurultudur**, olcum degil." % (games, "gurultu esigi")
        )
    if claimed_delta > 0.0 and hw_wr > claimed_delta:
        notes.append(
            "Iddia edilen fark %.4f, %d oyunda saptanabilir en kucuk fark %.4f: "
            "oran %.1fx. Bu fark bu hacimde **olculemez**; gucu yetmiyor."
            % (claimed_delta, games, hw_wr, hw_wr / claimed_delta)
        )
    return PowerReport(
        win_rate=float(win_rate),
        ppg_sigma=float(ppg_sigma),
        games=int(games),
        win_rate_half_width=hw_wr,
        ppg_half_width=hw_ppg,
        noise_floor=noise_floor(win_rate, ppg_sigma),
        required=required,
        notes=notes,
    )


def build_markdown(report: PowerReport, *, title: str = "Faz 7 - Mac gucu analizi") -> str:
    """Insan-okur Markdown rapor."""
    lines: list[str] = ["# " + title, ""]
    lines.append("Soru: **bir iddiayi kanitlamak icin kac oyun gerekir?** Bu rapor")
    lines.append("her iddiayi gerekli n ve saptanabilir etki olarak yazar.")
    lines.append("")
    lines.append("## 1. Mevcut hacim")
    lines.append("")
    lines.append("| Olcum | Deger |")
    lines.append("|---|---|")
    lines.append("| Oyun | %d |" % report.games)
    lines.append("| Kazanma orani (varsayim) | %.4f |" % report.win_rate)
    lines.append("| Kazanma orani GA yari genisligi | %.4f |" % report.win_rate_half_width)
    lines.append("| ppg sigma | %.4f |" % report.ppg_sigma)
    lines.append("| ppg GA yari genisligi | %.4f |" % report.ppg_half_width)
    lines.append("")
    lines.append("## 2. Gurultu tabani")
    lines.append("")
    lines.append("| Oyun | Kazanma orani +/- | ppg +/- |")
    lines.append("|---|---|---|")
    for row in report.noise_floor:
        lines.append(
            "| %d | %.4f | %.4f |"
            % (row["games"], row["winRateHalfWidth"], row["ppgHalfWidth"])
        )
    lines.append("")
    lines.append("## 3. Gereken n")
    lines.append("")
    lines.append("| Iddia | Gereken |")
    lines.append("|---|---|")
    labels = {
        "gamesForWinRateHalfWidth5pct": "Kazanma orani +/-0,05 (tek ornek)",
        "gamesForPpgHalfWidth0_10": "ppg +/-0,10",
        "gamesForPpgHalfWidth0_05": "ppg +/-0,05",
        "gamesPerArmWinRateVsChampion": "Sampiyonu yenme iddiasi (kol basina)",
        "gamesPerArmPpgVsChampion": "ppg farki iddiasi (kol basina)",
        "matchesForMatchWinRateHalfWidth5pct": "Mac kazanma orani +/-0,05 (mac sayisi)",
    }
    for key, value in report.required.items():
        lines.append("| %s | %d |" % (labels.get(key, key), value))
    lines.append("")
    lines.append("## 4. Notlar")
    lines.append("")
    for note in report.notes:
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="match_power",
        description="Mac seviyesinde guc analizi (madde 1.4).",
    )
    p.add_argument("--win-rate", type=float, default=0.55, help="varsayilan kazanma orani")
    p.add_argument("--sigma", type=float, default=DEFAULT_PPG_SIGMA, help="ppg standart sapmasi")
    p.add_argument("--games", type=int, default=STAGE_H_GAMES, help="mevcut oyun sayisi")
    p.add_argument("--champion-win-rate", type=float, default=0.50)
    p.add_argument("--ppg-delta", type=float, default=0.10)
    p.add_argument("--claimed-delta", type=float, default=CLAIMED_DELTA)
    p.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    p.add_argument("--power", type=float, default=DEFAULT_POWER)
    p.add_argument("--eval", dest="eval_path", type=Path, default=None, help="--eval-json ciktisi")
    p.add_argument("--opponent", default=None, help="--eval icinde rakip filtresi")
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--markdown", type=Path, default=None)
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    win_rate = args.win_rate
    games = args.games
    if args.eval_path is not None:
        if not args.eval_path.is_file():
            print("[hata] eval dosyasi yok: " + str(args.eval_path), file=sys.stderr)
            return 2
        data = json.loads(args.eval_path.read_text(encoding="utf-8"))
        measured = ppg_from_eval(data, opponent=args.opponent)
        measured_games = games_from_eval(data, opponent=args.opponent)
        if measured_games is not None:
            games = measured_games
        if measured is not None and not args.quiet:
            print("olculen ppg = %.4f (%d oyun)" % (measured, games))

    report = build_report(
        win_rate=win_rate,
        ppg_sigma=args.sigma,
        games=games,
        champion_win_rate=args.champion_win_rate,
        ppg_delta=args.ppg_delta,
        claimed_delta=args.claimed_delta,
        alpha=args.alpha,
        power=args.power,
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
        print("oyun=%d kazanma +/-%.4f ppg +/-%.4f" % (
            report.games, report.win_rate_half_width, report.ppg_half_width
        ))
        for key, value in report.required.items():
            print("  %-40s %d" % (key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
