# Faz 5 §9.2 — Kup karari uyumu (gnubg referansi)

> **Bu dosya tarihsel bir kayittir.** Asama F'de uc olcum/sözlesme hatasi bulundu
> (F6-28 gnubg `cubeinfo.move`, F6-29 danisman perspektifi, F6-30 mac ciftleme
> karsilastirmasi). Asagidaki sayilar bu duzeltmelerden **once** alinmistir; guncel ve
> gecerli olcum `ml/artifacts/stage_f_cube.md` dosyasidir. Bu dosya yalnizca Faz 5'in
> ne raporladigini belgelemek icin korunmustur.

Pozisyon kaynagi: `Backgammon.MatchBench gen-positions` (rastgele oyunlardan).
gnubg karari: `cfevaluate` (cubeful), `deterministic=1`.
Bizim karar: `EquityCubeAdvisor` (model + `HeuristicOutcomeDistribution`).

## gnubg 0-ply

| Metrik | Deger |
|---|---|
| Karsilastirilan pozisyon | 132 |
| Ciftleme uyumu | 51.52% |
| Kabul/ret uyumu | 61.36% |
| Her iki karar uyumu | 46.21% |
| Equity korelasyonu (Pearson), tek-kayit | -0.0315 |
| Equity ortalama \|delta\|, tek-kayit | 1.0550 |
| Equity korelasyonu (Pearson), zar-ortalamali | 0.1395 |
| Equity ortalama \|delta\|, zar-ortalamali | 1.2063 |

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 13 | 51 |
| **bizim: ciftleme** | 13 | 55 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 79 | 10 |
| **bizim: ret** | 41 | 2 |

## gnubg 2-ply

| Metrik | Deger |
|---|---|
| Karsilastirilan pozisyon | 132 |
| Ciftleme uyumu | 52.27% |
| Kabul/ret uyumu | 61.36% |
| Her iki karar uyumu | 46.97% |
| Equity korelasyonu (Pearson), tek-kayit | -0.0313 |
| Equity ortalama \|delta\|, tek-kayit | 1.0546 |
| Equity korelasyonu (Pearson), zar-ortalamali | 0.1396 |
| Equity ortalama \|delta\|, zar-ortalamali | 1.2067 |

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 14 | 50 |
| **bizim: ciftleme** | 13 | 55 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 79 | 10 |
| **bizim: ret** | 41 | 2 |

