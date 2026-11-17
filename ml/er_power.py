"""Faz 7 Bolum 4.5/4.6: ER olcumunun istatistiksel gucu ve gecersiz isaretleme.

Bu modul **tek** bir isi yapar: "ER <= hedef" iddiasinin yazilabilir olup
olmadigini matematiksel olarak karara baglar. Iddia **uc durumludur**
(Bolum 4.5.3) ve gereken orneklem **sigma'nin ust guven sinirindan** hesaplanir
(Bolum 4.5.1) -- nokta tahmininden degil.

Neden bu kadar kati: Faz 6'da "3-ply ER 0,0972" sayisi aslinda 0-ply olcumuydu
(F6-32) ve aylarca fark edilmedi. Ayni sinif hata, bir ortalamanin belirsizligini
yok sayip "ER <= 0,005" yazmakla da olusur: n = 200'de standart hata 0,0077'dir,
yani hedef 0,005 **standart hatanin altindadir** ve iddia yanlislanamaz.

Sozlesme (Test 124):
  * ``required_n`` / ``required_n_from_upper`` -- orneklem buyuklugu
  * ``claim_er_at_most`` -- uc durumlu iddia
  * ``screen`` / ``prove`` -- iki asamali kanit
  * ``assert_valid`` / ``invalidate`` -- gecersiz isaretleme (Bolum 4.6)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

#: Tek tarafli %95 icin z (hedefin **asilmamasi** yonunde tek kuyruk).
#: Yuvarlanmis deger kullanilir: Bolum 4.5 tablosundaki regresyon sayilari
#: (1 288 / 1 829 / 1 670) bu degerlerle uretildi.
Z_ONE_SIDED = 1.645

#: Iki tarafli %95 icin z.
Z_TWO_SIDED = 1.96

#: Bootstrap yeniden orneklem sayisi (Bolum 4.5.1).
BOOTSTRAP_RESAMPLES = 20000

#: Bootstrap tohumu -- sabit, yoksa GA her kosuda degisir ve tekrar uretilemez.
BOOTSTRAP_SEED = 20261116

#: Kanit olcumunun saat tavani (Bolum 4.5.3).
PROOF_CAP_HOURS = 40.0

#: Tarama olcumunun saat tavani (Bolum 4.5.3).
SCREEN_CAP_HOURS = 16.0

#: Sampiyon iddiasinin ER hedefi.
CHAMPION_ER_TARGET = 0.005

#: Iki asama arasinda sigma/ortalama oraninin izin verilen kaymasi (Bolum 4.5.2).
SCALE_FAMILY_DRIFT_LIMIT = 0.30

#: Kuyruk teshisi esikleri (Bolum 4.5.3).
SKEWNESS_ALERT = 2.0
TAIL_SHARE_ALERT = 0.40
TRIMMED_DEVIATION_ALERT = 0.30

#: ``er_sigma_log.json`` icin zorunlu alanlar (Bolum 4.5.2).
SIGMA_LOG_FIELDS = (
    "stage",
    "model",
    "n",
    "sigma",
    "sigmaCiLow",
    "sigmaCiHigh",
    "mean",
    "ciLow",
    "ciHigh",
    "skewness",
    "tailShare",
    "measuredAt",
)

#: ER raporunda zorunlu alanlar (Test 124).
ER_REPORT_FIELDS = (
    "n",
    "sigma",
    "sigmaCiLow",
    "sigmaCiHigh",
    "standardError",
    "ciLow",
    "ciHigh",
    "skewness",
    "tailShare",
)

#: Uc durumlu iddia sonucu.
PROVEN = "proven"
REFUTED = "refuted"
NOT_PROVEN = "not_proven"

CLAIM_STATES = (PROVEN, REFUTED, NOT_PROVEN)


class MeasurementInvalidatedError(RuntimeError):
    """Bir olcum dosyasi ``gecersiz`` isaretlenmis (Bolum 4.6)."""


# ----------------------------------------------------------------------
# Orneklem buyuklugu
# ----------------------------------------------------------------------


def required_n(sigma: float, half_width: float, *, two_sided: bool = True) -> int:
    """``half_width`` yari genisliginde GA icin gereken n.

    ``n = (z * sigma / half_width) ** 2``, yukari yuvarlanir. Bu, **nokta
    tahmini** uzerinden hesaplar; kanit icin :func:`required_n_from_upper`
    kullanilmalidir (Bolum 4.5.1).
    """
    if sigma <= 0.0:
        raise ValueError("sigma pozitif olmali: %r" % (sigma,))
    if half_width <= 0.0:
        raise ValueError("half_width pozitif olmali: %r" % (half_width,))
    z = Z_TWO_SIDED if two_sided else Z_ONE_SIDED
    return int(math.ceil((z * sigma / half_width) ** 2))


def required_n_from_upper(sigma_ci_high: float, half_width: float, *, two_sided: bool = False) -> int:
    """Gereken n'i sigma'nin **ust guven sinirindan** hesaplar (Bolum 4.5.1).

    Nokta tahminini kullanmak n'i sistematik olarak **eksik** hesaplar: bugunku
    dagilimda sigma = 0,109072 -> n = 1 288, ama sigma'nin ust siniri 0,124178
    -> n = 1 670, yani **%30 fazla**. Eksik n, "kanitlandi" sanilan bir iddiayi
    aslinda kanitlanmamis birakir.
    """
    return required_n(sigma_ci_high, half_width, two_sided=two_sided)


def n_within_cap(n_required: int, hours_per_position: float, cap_hours: float = PROOF_CAP_HOURS) -> tuple[int, bool]:
    """Tavan icinde kosulabilecek n'i ve tavanin asilip asilmadigini doner.

    Tavan asilirsa olcum **iptal edilmez**; tavan kadar kosulur (Bolum 4.5.3).
    """
    if hours_per_position <= 0.0:
        raise ValueError("hours_per_position pozitif olmali: %r" % (hours_per_position,))
    n_cap = int(math.floor(cap_hours / hours_per_position))
    if n_cap < 1:
        raise ValueError(
            "tavan tek pozisyonu bile karsilamiyor (%.3f saat/poz, tavan %.1f saat)"
            % (hours_per_position, cap_hours)
        )
    if n_required <= n_cap:
        return n_required, False
    return n_cap, True


# ----------------------------------------------------------------------
# Dagilim ozetleri
# ----------------------------------------------------------------------


def _skewness(x: np.ndarray) -> float:
    """Ornek carpikligi (Fisher-Pearson, duzeltmesiz)."""
    n = x.size
    if n < 3:
        return 0.0
    mean = x.mean()
    sd = x.std(ddof=0)
    if sd == 0.0:
        return 0.0
    return float(np.mean(((x - mean) / sd) ** 3))


def _excess_kurtosis(x: np.ndarray) -> float:
    n = x.size
    if n < 4:
        return 0.0
    mean = x.mean()
    sd = x.std(ddof=0)
    if sd == 0.0:
        return 0.0
    return float(np.mean(((x - mean) / sd) ** 4) - 3.0)


def _tail_share(x: np.ndarray, top: int = 10) -> float:
    """En buyuk ``top`` kaybin toplam kayba orani."""
    total = float(x.sum())
    if total <= 0.0:
        return 0.0
    ordered = np.sort(x)[::-1]
    return float(ordered[:top].sum() / total)


def _trimmed_mean(x: np.ndarray, proportion: float) -> float:
    """Simetrik kirpilmis ortalama (teshis amacli; ER yerine gecmez)."""
    n = x.size
    k = int(math.floor(n * proportion))
    if 2 * k >= n:
        return float(x.mean())
    ordered = np.sort(x)
    return float(ordered[k : n - k].mean())


def _bootstrap_ci(x: np.ndarray, statistic, *, resamples: int, seed: int) -> tuple[float, float]:
    """Istatistigin %95 bootstrap GA'si (yuzdelik yontem)."""
    rng = np.random.default_rng(seed)
    n = x.size
    draws = np.empty(resamples, dtype=np.float64)
    for i in range(resamples):
        sample = x[rng.integers(0, n, n)]
        draws[i] = statistic(sample)
    low, high = np.percentile(draws, [2.5, 97.5])
    return float(low), float(high)


@dataclass
class LossSummary:
    """Bir ER olcumunun tam istatistiksel ozeti (Test 124 zorunlu alanlari)."""

    n: int
    mean: float
    sigma: float
    sigma_ci_low: float
    sigma_ci_high: float
    standard_error: float
    ci_low: float
    ci_high: float
    skewness: float
    excess_kurtosis: float
    tail_share: float
    median: float
    maximum: float
    zero_loss_count: int
    trimmed_mean_5: float
    trimmed_mean_10: float
    winsorized_mean_5: float
    winsorized_mean_10: float
    bootstrap_resamples: int
    bootstrap_seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "mean": round(self.mean, 6),
            "sigma": round(self.sigma, 6),
            "sigmaCiLow": round(self.sigma_ci_low, 6),
            "sigmaCiHigh": round(self.sigma_ci_high, 6),
            "standardError": round(self.standard_error, 6),
            "ciLow": round(self.ci_low, 6),
            "ciHigh": round(self.ci_high, 6),
            "skewness": round(self.skewness, 4),
            "excessKurtosis": round(self.excess_kurtosis, 4),
            "tailShare": round(self.tail_share, 4),
            "median": round(self.median, 6),
            "maximum": round(self.maximum, 6),
            "zeroLossCount": self.zero_loss_count,
            "trimmedMean5": round(self.trimmed_mean_5, 6),
            "trimmedMean10": round(self.trimmed_mean_10, 6),
            "winsorizedMean5": round(self.winsorized_mean_5, 6),
            "winsorizedMean10": round(self.winsorized_mean_10, 6),
            "bootstrapResamples": self.bootstrap_resamples,
            "bootstrapSeed": self.bootstrap_seed,
        }

    def missing_fields(self) -> list[str]:
        """Test 124'un zorunlu alanlarindan eksik olanlar."""
        data = self.to_dict()
        return [name for name in ER_REPORT_FIELDS if name not in data]

    def required_n(self, half_width: float = CHAMPION_ER_TARGET, *, two_sided: bool = False) -> int:
        """Kanit icin gereken n -- **sigma'nin ust sinirindan**."""
        return required_n_from_upper(self.sigma_ci_high, half_width, two_sided=two_sided)

    def claim(self, target: float = CHAMPION_ER_TARGET) -> str:
        return claim_er_at_most(target, self.ci_low, self.ci_high)

    def tail_diagnostics(self) -> dict[str, Any]:
        """Kuyruk teshisi (Bolum 4.5.3) -- yanlis negatifin erken uyarisi."""
        deviation = abs(self.trimmed_mean_10 - self.mean) / self.mean if self.mean > 0 else 0.0
        return {
            "skewness": round(self.skewness, 4),
            "skewnessAlert": self.skewness > SKEWNESS_ALERT,
            "tailShare": round(self.tail_share, 4),
            "tailShareAlert": self.tail_share > TAIL_SHARE_ALERT,
            "trimmedMean10": round(self.trimmed_mean_10, 6),
            "trimmedDeviation": round(deviation, 4),
            "trimmedDeviationAlert": deviation > TRIMMED_DEVIATION_ALERT,
            "heavyTailed": (
                self.skewness > SKEWNESS_ALERT
                or self.tail_share > TAIL_SHARE_ALERT
                or deviation > TRIMMED_DEVIATION_ALERT
            ),
        }


def _winsorized_mean(x: np.ndarray, proportion: float) -> float:
    n = x.size
    k = int(math.floor(n * proportion))
    if 2 * k >= n:
        return float(x.mean())
    ordered = np.sort(x)
    low = ordered[k]
    high = ordered[n - k - 1]
    clipped = np.clip(ordered, low, high)
    return float(clipped.mean())


def summarize_losses(
    losses: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> LossSummary:
    """Equity kayiplarindan tam ozet uretir.

    ``sigma`` icin GA **bootstrap** ile hesaplanir: dagilim carpik oldugunda
    normal yaklasim (``sigma/sqrt(2n)``) dar kalir ve n'i eksik hesaplar
    (Bolum 4.5.1: gercek +-%14,7, normal yaklasim +-%9,8).
    """
    x = np.asarray(list(losses), dtype=np.float64)
    if x.size < 2:
        raise ValueError("en az 2 kayip gerekli: %d" % x.size)
    if np.any(x < 0.0):
        raise ValueError("equity kaybi negatif olamaz")

    n = int(x.size)
    mean = float(x.mean())
    sigma = float(x.std(ddof=1))
    se = sigma / math.sqrt(n)

    sigma_low, sigma_high = _bootstrap_ci(
        x, lambda s: float(s.std(ddof=1)), resamples=resamples, seed=seed
    )
    mean_low, mean_high = _bootstrap_ci(
        x, lambda s: float(s.mean()), resamples=resamples, seed=seed + 1
    )

    return LossSummary(
        n=n,
        mean=mean,
        sigma=sigma,
        sigma_ci_low=sigma_low,
        sigma_ci_high=sigma_high,
        standard_error=se,
        ci_low=mean_low,
        ci_high=mean_high,
        skewness=_skewness(x),
        excess_kurtosis=_excess_kurtosis(x),
        tail_share=_tail_share(x),
        median=float(np.median(x)),
        maximum=float(x.max()),
        zero_loss_count=int(np.count_nonzero(x == 0.0)),
        trimmed_mean_5=_trimmed_mean(x, 0.05),
        trimmed_mean_10=_trimmed_mean(x, 0.10),
        winsorized_mean_5=_winsorized_mean(x, 0.05),
        winsorized_mean_10=_winsorized_mean(x, 0.10),
        bootstrap_resamples=resamples,
        bootstrap_seed=seed,
    )


# ----------------------------------------------------------------------
# Uc durumlu iddia
# ----------------------------------------------------------------------


def claim_er_at_most(target: float, ci_low: float, ci_high: float) -> str:
    """``ER <= target`` iddiasini **uc durumdan** birine baglar (Bolum 4.5.3).

    * ``proven``     -- GA ust siniri hedefin altinda veya esit
    * ``refuted``    -- GA alt siniri hedefin **ustunde** (model hedefte degil)
    * ``not_proven`` -- GA hedefi **iceriyor** (nokta tahmini altinda olsa bile)

    Ucuncu durum durust orta haldir: "yanlislandi" demek yalan olur (nokta
    tahmini hedefin altinda), "kanitlandi" demek de yalan olur (ust sinir
    asiyor). Ikili ``True/False`` bu ayrimi **yok eder** ve tam olarak
    Faz 6'nin sessiz hata ailesine girer.
    """
    if ci_low > ci_high:
        raise ValueError("ci_low > ci_high: %r > %r" % (ci_low, ci_high))
    if ci_high <= target:
        return PROVEN
    if ci_low > target:
        return REFUTED
    return NOT_PROVEN


def claim_sentence(target: float, summary: LossSummary) -> str:
    """Rapora yazilacak tek cumle (Bolum 4.5.3 tablosu)."""
    state = summary.claim(target)
    if state == PROVEN:
        return "ER <= %.4f **kanitlandi** (n = %d, GA ust = %.4f)" % (
            target,
            summary.n,
            summary.ci_high,
        )
    if state == REFUTED:
        return "ER <= %.4f **yanlislandi** (GA alt = %.4f)" % (target, summary.ci_low)
    return (
        "ER = %.4f [%.4f; %.4f]; hedef araligin **icinde ama ust sinir asiyor** "
        "-> **kanitlanmadi**" % (summary.mean, summary.ci_low, summary.ci_high)
    )


# ----------------------------------------------------------------------
# Iki asamali kanit (Bolum 4.5.3)
# ----------------------------------------------------------------------


@dataclass
class ScreenResult:
    """Tarama asamasi ciktisi. Tarama **yalnizca reddeder** veya kanita gecirir."""

    summary: LossSummary
    target: float
    rejected: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = self.summary.to_dict()
        data.update(
            {
                "stage": "screen",
                "target": self.target,
                "rejected": self.rejected,
                "reason": self.reason,
                "canProve": False,
            }
        )
        return data


def screen(
    losses: Sequence[float],
    *,
    target: float = CHAMPION_ER_TARGET,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> ScreenResult:
    """Tarama: 3-ply, n = 200, 8-16 saat. **Kanitlayamaz.**

    3-ply daha zayif bir hakemdir; 4-ply ER >= 3-ply ER olur. Bu yuzden tarama
    yalnizca iki sey yapabilir: modeli **reddetmek** (iyimser sinirda bile
    hedefin disindaysa) veya **kanita gecirmek**. "Tarama gecti" bir iddia
    degildir ve rapora iddia olarak yazilamaz.
    """
    summary = summarize_losses(losses, resamples=resamples, seed=seed)
    optimistic = summary.mean - summary.ci_low
    if optimistic > target:
        return ScreenResult(
            summary=summary,
            target=target,
            rejected=True,
            reason=(
                "ER_screen - GA_alt = %.4f - %.4f = %.4f > %.4f; model iyimser "
                "sinirda bile hedefin disinda -> kanit kosulmaz"
                % (summary.mean, summary.ci_low, optimistic, target)
            ),
        )
    return ScreenResult(
        summary=summary,
        target=target,
        rejected=False,
        reason=(
            "ER_screen - GA_alt = %.4f <= %.4f; kanita gecirildi (kanitlanmadi)"
            % (optimistic, target)
        ),
    )


@dataclass
class ProofResult:
    """Kanit asamasi ciktisi."""

    summary: LossSummary
    target: float
    n_required: int
    n_run: int
    capped: bool
    claim: str
    sentence: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.summary.to_dict()
        data.update(
            {
                "stage": "proof",
                "target": self.target,
                "nRequired": self.n_required,
                "nRun": self.n_run,
                "capped": self.capped,
                "claim": self.claim,
                "sentence": self.sentence,
                "notes": list(self.notes),
            }
        )
        return data


def prove(
    losses: Sequence[float],
    *,
    target: float = CHAMPION_ER_TARGET,
    n_required: int | None = None,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> ProofResult:
    """Kanit: 4-ply, ``n = required_n(sigma_ust, hedef)``, tavan 40 saat.

    Tavan asilirsa olcum **iptal edilmez**; eldeki n ile kosulur ve sonuc
    ``capped: true`` olarak isaretlenir. Iddia yine **uc durumdan** birine
    baglanir -- tavan kaniti zayiflatir, iddiayi oldurmez.
    """
    summary = summarize_losses(losses, resamples=resamples, seed=seed)
    needed = summary.required_n(target) if n_required is None else int(n_required)
    capped = summary.n < needed
    notes: list[str] = []
    if capped:
        notes.append(
            "tavan asildi: gereken n = %d, kosulan n = %d; kanit daha genis GA ile "
            "raporlanir (Bolum 4.5.3)" % (needed, summary.n)
        )
    diag = summary.tail_diagnostics()
    if diag["heavyTailed"]:
        notes.append(
            "dagilim agir kuyruklu (carpiklik %.2f, kuyruk payi %.3f); ortalama "
            "kuyruga duyarli" % (summary.skewness, summary.tail_share)
        )
    return ProofResult(
        summary=summary,
        target=target,
        n_required=needed,
        n_run=summary.n,
        capped=capped,
        claim=summary.claim(target),
        sentence=claim_sentence(target, summary),
        notes=notes,
    )


# ----------------------------------------------------------------------
# Gecersiz isaretleme (Bolum 4.6)
# ----------------------------------------------------------------------


def invalidation_path(path: Path | str) -> Path:
    """Bir olcum dosyasinin kardes isaret dosyasi."""
    p = Path(path)
    return p.with_name(p.name + ".invalidated.json")


def invalidate(
    path: Path | str,
    *,
    gate: str,
    reason: str,
    evidence: str = "",
    now: datetime | None = None,
) -> Path:
    """Olcumu **gecersiz** olarak isaretler; orijinal dosyaya dokunmaz.

    Orijinal silinmez ve duzenlenmez: silmek denetim izini yok eder. Faz 6'da
    "3-ply ER 0,0972" sayisi silinseydi hatanin nasil dogdugu asla
    anlasilamazdi.
    """
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError("olcum dosyasi yok: %s" % target)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    payload = {
        "invalidatedAt": stamp,
        "gate": gate,
        "reason": reason,
        "evidence": evidence,
        "reRunRequired": True,
    }
    marker = invalidation_path(target)
    marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return marker


def is_invalidated(path: Path | str) -> bool:
    return invalidation_path(path).is_file()


def assert_valid(path: Path | str) -> None:
    """Gecersiz isaretli dosyayi okumayi **teknik olarak imkansiz** kilar.

    "Isaretledim ama yine de kullandim" davranisi isaretlemeyi anlamsiz kilar;
    bu fonksiyon o davranisi engeller.
    """
    marker = invalidation_path(path)
    if not marker.is_file():
        return
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    raise MeasurementInvalidatedError(
        "olcum gecersiz isaretli: %s (kapi=%s, neden=%s)"
        % (path, payload.get("gate", "?"), payload.get("reason", "?"))
    )


def archive_invalidation(path: Path | str, *, now: datetime | None = None) -> Path | None:
    """Isareti arsivler (silmez). Yeni olcum isaretsiz dogar.

    Ayni dosya ikinci kez gecersiz olursa ikinci arsiv yazilir; gecmis **ust
    uste yazilmaz**.
    """
    marker = invalidation_path(path)
    if not marker.is_file():
        return None
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    archived = marker.with_name(marker.name.replace(".invalidated.json", ".invalidated.%s.json" % stamp))
    marker.rename(archived)
    return archived


def count_invalidated(directory: Path | str) -> int:
    """Bir dizindeki aktif gecersiz isaret sayisi (Bolum 10.5 kapisi)."""
    return len(list(Path(directory).glob("*.invalidated.json")))


# ----------------------------------------------------------------------
# sigma kaydi (Bolum 4.5.2)
# ----------------------------------------------------------------------


def sigma_log_entry(
    summary: LossSummary,
    *,
    stage: str,
    model: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """``er_sigma_log.json`` icin tek satir (12 zorunlu alan)."""
    entry = {
        "stage": stage,
        "model": model,
        "n": summary.n,
        "sigma": round(summary.sigma, 6),
        "sigmaCiLow": round(summary.sigma_ci_low, 6),
        "sigmaCiHigh": round(summary.sigma_ci_high, 6),
        "mean": round(summary.mean, 6),
        "ciLow": round(summary.ci_low, 6),
        "ciHigh": round(summary.ci_high, 6),
        "skewness": round(summary.skewness, 4),
        "tailShare": round(summary.tail_share, 4),
        "measuredAt": (now or datetime.now(timezone.utc)).isoformat(),
    }
    missing = [name for name in SIGMA_LOG_FIELDS if name not in entry]
    if missing:
        raise ValueError("sigma kaydinda eksik alan: %s" % ", ".join(missing))
    return entry


def append_sigma_log(path: Path | str, entry: dict[str, Any]) -> None:
    """Kaydi **ekler** (uzerine yazmaz). Dosya yoksa olusturur."""
    missing = [name for name in SIGMA_LOG_FIELDS if name not in entry]
    if missing:
        raise ValueError("sigma kaydinda eksik alan: %s" % ", ".join(missing))
    target = Path(path)
    if target.is_file():
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "entries" not in data:
            raise ValueError("er_sigma_log.json bicimi bozuk: %s" % target)
    else:
        data = {"version": 1, "entries": []}
    data["entries"].append(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scale_family_drift(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """``sigma/ortalama`` oraninin asamalar arasi kaymasi (Bolum 4.5.2).

    Oran %30'dan fazla degisirse "sigma kuculecek" varsayimi **curutulmus**
    sayilir ve kanit n'i en kotu olculen sigma ile hesaplanir.
    """
    ratios = []
    for entry in entries:
        mean = float(entry.get("mean", 0.0))
        if mean > 0.0:
            ratios.append(float(entry["sigma"]) / mean)
    if len(ratios) < 2:
        return {"ratios": ratios, "drift": 0.0, "refuted": False, "worstSigma": None}
    low, high = min(ratios), max(ratios)
    drift = (high - low) / low if low > 0 else 0.0
    worst = max(float(e["sigma"]) for e in entries)
    return {
        "ratios": [round(r, 4) for r in ratios],
        "drift": round(drift, 4),
        "refuted": drift > SCALE_FAMILY_DRIFT_LIMIT,
        "worstSigma": round(worst, 6),
    }


# ----------------------------------------------------------------------
# Rapor dogrulama
# ----------------------------------------------------------------------


def validate_er_report(report: dict[str, Any]) -> list[str]:
    """Bir ER raporunun Test 124 zorunlu alanlarini tasiyip tasimadigini denetler."""
    problems: list[str] = []
    for name in ER_REPORT_FIELDS:
        if name not in report:
            problems.append("eksik alan: %s" % name)
    if "n" in report and not report["n"]:
        problems.append("n bos")
    if "sigma" in report and "sigmaCiHigh" in report:
        if float(report["sigmaCiHigh"]) < float(report["sigma"]):
            problems.append("sigmaCiHigh < sigma")
    return problems


def load_measurement(path: Path | str) -> dict[str, Any]:
    """Olcumu okur -- ama once gecersiz isaretini denetler."""
    assert_valid(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))