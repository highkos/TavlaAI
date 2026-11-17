# Faz 6 §10.5 — Kup karari uyumu (Aşama F, Test 84)

Pozisyon kaynagi: `ml/artifacts/stage_b_positions.json` (200 pozisyon, 133 karsilastirilabilir).
gnubg karari: `cfevaluate` (cubeful), `deterministic=1`.
Bizim karar: `EquityCubeAdvisor` + Aşama D modeli (6 cikti).

Iki varyant:

- **diceAveraged** — `CubeAdvisorOptions.DiceAveraged = true` (Faz 6 varsayilani, §10.2).
- **singleRecord** — `DiceAveraged = false` (Faz 5 davranisi).

## Olcum hatti duzeltmeleri (F6-28, F6-29, F6-30)

Bu tablodaki sayilar uc olcum/sözlesme hatasi duzeltildikten sonra alinmistir:

- **F6-28** — gnubg'nin Python API'si `cubeinfo['move']` alanini **yok sayar** ve her
  zaman `anBoard[1]`'i sirada kabul eder. `gnubg_view()` hamleyi yapan oyuncuyu
  fiziksel olarak `anBoard[1]`'e tasir. Duzeltme oncesi korelasyon 0,11 idi.
- **F6-29** — `EquityCubeAdvisor.EvaluateDiceAveraged` afterstate'leri `-perspective`
  ile degerlendirip isareti ceviriyordu. Ag afterstate'i **hamleyi yapanin**
  perspektifinden ogrenir (`ShardWriter`, `ml/gnubg_er.py`, `BackgammonSearch`),
  bu yuzden isaret cevrimi kaldirildi.
- **F6-30** — mac oyununda ciftleme karsilastirmasi `max(doubleTake, doublePass)`
  kullaniyordu; bu, rakibin isbirligi yaptigini varsayar. Rakip kendi equity'sini
  maksimize ettigi icin dogru deger `min(doubleTake, doublePass)`'tir. Duzeltme
  ciftleme uyumunu 73,13% -> 84,96%'ya tasidi (32 yanlis ciftlemenin 19'u dondu).

## gnubg 0-ply

| Metrik | singleRecord (Faz 5) | diceAveraged (Faz 6) | Faz 5 taban |
|---|---|---|---|
| Karsilastirilan pozisyon | 133 | 133 | 132 |
| Ciftleme uyumu | 75.94% | 84.96% | 52.27% |
| Kabul/ret uyumu | 81.20% | 88.72% | 61.36% |
| Her iki karar uyumu | 73.68% | 81.20% | 46.97% |
| Equity korelasyonu (Pearson) | 0.8218 | 0.8330 | — |
| Equity ortalama \|delta\| | 0.6266 | 0.3738 | 1.2063 |
| Equity p90 \|delta\| | 1.2851 | 0.9038 | — |

### singleRecord — karisiklik matrisleri

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 24 | 10 |
| **bizim: ciftleme** | 22 | 77 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 83 | 22 |
| **bizim: ret** | 3 | 25 |

### diceAveraged — karisiklik matrisleri

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 39 | 13 |
| **bizim: ciftleme** | 7 | 74 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 77 | 6 |
| **bizim: ret** | 9 | 41 |

## gnubg 2-ply

| Metrik | singleRecord (Faz 5) | diceAveraged (Faz 6) | Faz 5 taban |
|---|---|---|---|
| Karsilastirilan pozisyon | 133 | 133 | 132 |
| Ciftleme uyumu | 75.94% | 84.96% | 52.27% |
| Kabul/ret uyumu | 81.20% | 88.72% | 61.36% |
| Her iki karar uyumu | 73.68% | 81.20% | 46.97% |
| Equity korelasyonu (Pearson) | 0.8216 | 0.8327 | — |
| Equity ortalama \|delta\| | 0.6256 | 0.3737 | 1.2063 |
| Equity p90 \|delta\| | 1.2851 | 0.9038 | — |

### singleRecord — karisiklik matrisleri

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 24 | 10 |
| **bizim: ciftleme** | 22 | 77 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 83 | 22 |
| **bizim: ret** | 3 | 25 |

### diceAveraged — karisiklik matrisleri

| Ciftleme | gnubg: ciftle | gnubg: ciftleme |
|---|---|---|
| **bizim: ciftle** | 39 | 13 |
| **bizim: ciftleme** | 7 | 74 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 77 | 6 |
| **bizim: ret** | 9 | 41 |

