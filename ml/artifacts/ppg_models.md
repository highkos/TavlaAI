# Modeller arasi ppg ve ER<->ppg eslemesi (F7-104)

Ayni kosu kosullari (kupsuz para oyunu, eslestirilmis zar + renk takasi, gnubg 0-ply, `search1`, tohum 2026).

## 1. Modeller

| Model | Oyun | Kazanma | ppg | ppg %95 GA | SE | ER(pol, +1) | ER(val, +1) |
|---|---|---|---|---|---|---|---|
| `v30` | 2000 | 0.4340 | **-0.1635** | [-0.2230; -0.1050] | 0.0303 | 0.0270 | 0.0287 |
| `rd_ctl10k` | 2000 | 0.4320 | **-0.1990** | [-0.2600; -0.1380] | 0.0315 | 0.0298 | 0.0302 |
| `rd_aug10k` | 2000 | 0.3765 | **-0.3240** | [-0.3810; -0.2670] | 0.0291 | 0.0383 | 0.0387 |

## 2. Ikili farklar

| a | b | a - b | %95 GA | z | Anlamli |
|---|---|---|---|---|---|
| `rd_ctl10k` | `v30` | -0.0355 | [-0.1213; +0.0503] | -0.81 | hayir |
| `rd_aug10k` | `v30` | -0.1605 | [-0.2429; -0.0781] | -3.82 | **evet** |

## 3. ER -> ppg eslemesi

| Kafa | Egim (ppg / ER) | Kesisim | R^2 | Nokta |
|---|---|---|---|---|
| policy | **-14.30** | +0.2247 | 0.9994 | 3 |
| value | **-15.64** | +0.2798 | 0.9941 | 3 |

Egim, ER'deki **bir birimin** kac ppg'ye karsilik geldigini soyler. Negatif egim beklenir: ER buyudukce ppg kuculur.

## 4. Uyari

Kosular ayni zar tohumunu (2026) kullanir ama modeller farkli hamle oynadigi icin oyunlar ayrilir; iki ornekli GA bu yuzden yaklasiktir. Her kosunun kendi eslesmis GA'si zar gurultusunu zaten iptal ettigi icin GA oldugundan dar gorunmez.

