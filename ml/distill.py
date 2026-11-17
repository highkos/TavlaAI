#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Faz 7 Bolum 5.1.3 / 5.4 - damitma hacmi planlamasi.

**Neden bu modul var?** Bolum 5.1.3'un ilk taslagi "2 000 000 karar <= 72 saat"
diyordu; bu **aritmetik olarak imkansizdir** (2 M x 4,07 s / 8 = 282 saat). Dogrusu:
72 saatlik butceye **500 000 karar** sigar. Bu modul, hacmi **tek bir yerde**
hesaplar; boylece "500 bin" ile "72 saat" celiskisi tekrar belgeye sizmaz.

**Kullanici karari (Faz 7 Asama B sonrasi).** Damitma **500 000 karar** ile
sinirlanir. Tavan (72 saat) asilirsa hacim **tavana kadar** dusurulur - yani
kosu iptal edilmez, **sigdigi kadar** kosar. Bu, Bolum 5.1.4'teki "tavan asilirsa
tavan kadar kosulur" kuralinin aynisidir.

**Maliyet modeli (Bolum 5.1.3, tahmin).** Depth 3 ortalama **4,07 s/karar**;
12 thread'de 8x paralel hizlanma -> **1,97 karar/sn**. Bu sayilar **tahmindir**;
gercek olcum Asama C'de yapilir ve `--seconds-per-decision` ile buraya verilir.

Kullanim::

    python ml/distill.py --json ml/artifacts/stage_c_distill_plan.json
    python ml/distill.py --seconds-per-decision 3.2 --parallel-speedup 6
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from typing import Any

#: Damitma hacim tavani (karar). Bolum 5.1.3: 72 saatlik butceye sigan hacim.
DISTILL_VOLUME_CAP = 500_000

#: Damitma sure tavani (saat). Bolum 10.4 / F-E2.
DISTILL_TIME_CAP_HOURS = 72.0

#: Ogretmen arama derinligi. Bolum 5.4: depth 3 cevrimdisi.
DISTILL_DEPTH = 3

#: Depth 3 ortalama karar suresi (saniye) - Bolum 5.1.3 **tahmini**.
DISTILL_SECONDS_PER_DECISION = 4.07

#: 12 thread'de paralel hizlanma - Bolum 5.1.3 **tahmini**.
DISTILL_PARALLEL_SPEEDUP = 8.0

#: Shard bayragi (Bolum 5.4 / Test 100). v1 okuyucusu bunu **bilinmeyen** bayrak
#: olarak yok sayar; bu yuzden shard bicimi degismez.
DEC_DISTILLED = 16

#: Hacmin neden kirpildigi.
CAPPED_BY_VOLUME = "volume"
CAPPED_BY_TIME = "time"


class DistillError(ValueError):
    """Damitma plani hesaplanamadi."""


def decisions_per_second(
    seconds_per_decision: float = DISTILL_SECONDS_PER_DECISION,
    parallel_speedup: float = DISTILL_PARALLEL_SPEEDUP,
) -> float:
    """Saniyede uretilebilen damitma karari (Bolum 5.1.3 modeli)."""
    if not math.isfinite(seconds_per_decision) or seconds_per_decision <= 0.0:
        raise DistillError("seconds_per_decision > 0 olmali")
    if not math.isfinite(parallel_speedup) or parallel_speedup <= 0.0:
        raise DistillError("parallel_speedup > 0 olmali")
    return float(parallel_speedup) / float(seconds_per_decision)


def estimate_seconds(volume: int, dps: float) -> float:
    """``volume`` karar uretmenin tahmini suresi (saniye)."""
    if volume < 0:
        raise DistillError("volume negatif olamaz")
    if not math.isfinite(dps) or dps <= 0.0:
        raise DistillError("dps > 0 olmali")
    return float(volume) / float(dps)


@dataclass
class DistillPlan:
    """Damitma hacmi plani."""

    #: Istenen hacim (tavan).
    requested: int
    #: Gercekten kosulacak hacim.
    volume: int
    #: Tahmini sure (saniye).
    seconds: float
    #: Tahmini sure (saat).
    hours: float
    #: Hacmi kisitlayan sey: ``"volume"``, ``"time"`` veya ``None``.
    capped_by: str | None
    #: Kosulabilir mi (``volume > 0``)?
    feasible: bool
    #: Kullanilan hiz (karar/sn).
    decisions_per_second: float
    #: Kullanilan hacim tavani.
    volume_cap: int
    #: Kullanilan sure tavani (saat).
    time_cap_hours: float
    #: Ogretmen derinligi.
    depth: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_volume(
    *,
    volume_cap: int = DISTILL_VOLUME_CAP,
    time_cap_hours: float = DISTILL_TIME_CAP_HOURS,
    seconds_per_decision: float = DISTILL_SECONDS_PER_DECISION,
    parallel_speedup: float = DISTILL_PARALLEL_SPEEDUP,
    depth: int = DISTILL_DEPTH,
) -> DistillPlan:
    """Hacmi **hem** hacim tavanina **hem** sure tavanina sigdirir.

    Kural (Bolum 5.1.4 ile ayni): tavan asilirsa kosu **iptal edilmez**, hacim
    **tavana kadar** dusurulur. Yani ``volume = min(volume_cap, floor(tavan_sn * dps))``.

    Args:
        volume_cap: Istenen en fazla karar sayisi (varsayilan 500 000).
        time_cap_hours: Sure tavani (varsayilan 72 saat).
        seconds_per_decision: Karar basina saniye (olculurse gercek deger verilir).
        parallel_speedup: Paralel hizlanma.
        depth: Ogretmen derinligi (yalnizca raporlanir).

    Returns:
        :class:`DistillPlan`.
    """
    if volume_cap < 0:
        raise DistillError("volume_cap negatif olamaz")
    if not math.isfinite(time_cap_hours) or time_cap_hours <= 0.0:
        raise DistillError("time_cap_hours > 0 olmali")
    if depth < 0:
        raise DistillError("depth negatif olamaz")

    dps = decisions_per_second(seconds_per_decision, parallel_speedup)
    time_cap_seconds = float(time_cap_hours) * 3600.0
    max_by_time = int(math.floor(time_cap_seconds * dps))

    if max_by_time < volume_cap:
        volume = max(0, max_by_time)
        capped_by: str | None = CAPPED_BY_TIME
    else:
        volume = int(volume_cap)
        capped_by = CAPPED_BY_VOLUME if volume_cap > 0 else None

    seconds = estimate_seconds(volume, dps)
    return DistillPlan(
        requested=int(volume_cap),
        volume=volume,
        seconds=seconds,
        hours=seconds / 3600.0,
        capped_by=capped_by,
        feasible=volume > 0,
        decisions_per_second=dps,
        volume_cap=int(volume_cap),
        time_cap_hours=float(time_cap_hours),
        depth=int(depth),
    )


def build_markdown(plan: DistillPlan) -> str:
    """Insan-okur plan raporu (Turkce ondalik virgulu)."""

    def f(value: float, digits: int = 2) -> str:
        return ("%.*f" % (digits, value)).replace(".", ",")

    lines = [
        "# Asama C - damitma hacmi plani",
        "",
        "| Alan | Deger |",
        "|---|---|",
        "| Ogretmen derinligi | %d |" % plan.depth,
        "| Hiz | %s karar/sn |" % f(plan.decisions_per_second, 3),
        "| Hacim tavani | %s karar |" % format(plan.volume_cap, ",").replace(",", " "),
        "| Sure tavani | %s saat |" % f(plan.time_cap_hours, 1),
        "| **Kosulacak hacim** | **%s karar** |" % format(plan.volume, ",").replace(",", " "),
        "| Tahmini sure | %s saat |" % f(plan.hours, 1),
        "| Kisitlayan | %s |" % (plan.capped_by or "-"),
        "| Kosulabilir | %s |" % ("evet" if plan.feasible else "**hayir**"),
        "",
    ]
    if plan.capped_by == CAPPED_BY_TIME:
        lines.append(
            "**Sure tavani baglayici.** Istenen %s karar %s saatlik tavana sigmiyor; "
            "hacim **%s karara** dusuruldu. Kosu iptal edilmez, **tavana kadar** kosar "
            "(Bolum 5.1.4 kurali)."
            % (
                format(plan.requested, ",").replace(",", " "),
                f(plan.time_cap_hours, 1),
                format(plan.volume, ",").replace(",", " "),
            )
        )
    elif plan.capped_by == CAPPED_BY_VOLUME:
        lines.append(
            "**Hacim tavani baglayici.** %s karar %s saatte bitiyor; tavanin altinda."
            % (
                format(plan.volume, ",").replace(",", " "),
                f(plan.hours, 1),
            )
        )
    else:
        lines.append("**Hacim sifir.** Plan kosulamaz.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Faz 7 damitma hacmi plani")
    ap.add_argument("--volume-cap", type=int, default=DISTILL_VOLUME_CAP)
    ap.add_argument("--time-cap-hours", type=float, default=DISTILL_TIME_CAP_HOURS)
    ap.add_argument("--seconds-per-decision", type=float, default=DISTILL_SECONDS_PER_DECISION)
    ap.add_argument("--parallel-speedup", type=float, default=DISTILL_PARALLEL_SPEEDUP)
    ap.add_argument("--depth", type=int, default=DISTILL_DEPTH)
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = plan_volume(
        volume_cap=args.volume_cap,
        time_cap_hours=args.time_cap_hours,
        seconds_per_decision=args.seconds_per_decision,
        parallel_speedup=args.parallel_speedup,
        depth=args.depth,
    )

    if args.json:
        directory = os.path.dirname(os.path.abspath(args.json))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2)
    if args.markdown:
        directory = os.path.dirname(os.path.abspath(args.markdown))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(build_markdown(plan))

    print(
        "damitma: hacim %d / %d | %.1f saat | kisitlayan %s | kosulabilir %s"
        % (plan.volume, plan.requested, plan.hours, plan.capped_by or "-", plan.feasible)
    )
    return 0 if plan.feasible else 1


if __name__ == "__main__":
    raise SystemExit(main())
