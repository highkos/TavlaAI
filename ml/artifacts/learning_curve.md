# Faz 7-R - Ogrenme egrisi

Soru: **ER hedefin uzerindeyse, daha cok veri mi yoksa onarilmis
bir hat mi gerekiyor?** Ayni hat, ayni tohum, yalnizca veri hacmi
degisir. Karar, ER'nin `log2(veri)` basina egiminden verilir.

## 1. Noktalar

| Carpan | Pozisyon | ER `policy` | ER `value` | ER `search1` | Kal. egimi | Kal. MAE | In-sample | In-sample birimi | Held-out |
|---|---|---|---|---|---|---|---|---|---|
| 1x | 165 | 0.0525 | 0.1915 | - | - | - | 1.0688 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0525 |
| 2x | 330 | 0.0441 | 0.1321 | - | - | - | 0.8408 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0441 |
| 4x | 660 | 0.0355 | 0.0879 | - | - | - | 0.6612 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0355 |
| 8x | 1320 | 0.0276 | 0.0588 | - | - | - | 0.4051 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0276 |
| 16x | 2640 | 0.0236 | 0.0469 | - | - | - | 0.2700 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0236 |
| 32x | 5280 | 0.0184 | 0.0365 | - | - | - | 0.2509 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0184 |
| 64x | 10560 | 0.0158 | 0.0330 | - | - | - | 0.1593 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0158 |

> **In-sample metrikler basari sayilmaz** (Kural 5). Held-out
> kolonu tek basina okunmalidir. In-sample kolonu bir ER
> **degildir**: birimi yanindaki sutunda yazilidir.

### 1.1 Korpus

| Alan | Deger |
|---|---|
| `etiket` | gnubg-2ply |
| `havuz` | curve_pool_400.npz |
| `oyun` | 400 |
| `plies` | 2 |

Korpus **acikca** yazilir: egri hangi veri uzerinde kosuldugu bilinmeden okunamaz (K4).

## 2. Egim (ER / log2 veri)

| Yol | Kazanc | %95 GA | Ham egim | Nokta | Kume | Yeniden ornekleme |
|---|---|---|---|---|---|---|
| `policy` | 0.0062 | [0.0059; 0.0065] | -0.0062 | 7 | 400 | 20000 |
| `value` | 0.0253 | [0.0244; 0.0267] | -0.0253 | 7 | 400 | 20000 |

Kume bootstrap'i: **oyun** (oyun duzeyinde = dogru; pozisyon duzeyinde GA'yi yapay daraltir).

Tohumlar: **1, 2, 3, 4, 5** (havuzlanmis).

**Kazanc** = ER'nin `log2(veri)` basina **dususu** (pozitif = veri arttkca ER iyilesiyor). Ham egim ayni buyuklugun isaretli hali.

Esik: **0.0050** (ER kazanci / log2 veri).

## 3. Tohum bazli kararlar

| Tohum | Kazanc | Karar |
|---|---|---|
| 1 | 0.0062 | `olcek` |
| 2 | 0.0059 | `olcek` |
| 3 | 0.0067 | `olcek` |
| 4 | 0.0060 | `olcek` |
| 5 | 0.0062 | `olcek` |

**Tohum oybirligi: VAR.** Havuzlanmis bootstrap tohumlari ek veri gibi ele alir ve GA'yi daraltir; bu yuzden havuz karari tek basina yetmez. `olcek`/`pipeline` icin **tum tohumlarin** ayni karari vermesi gerekir.

## 4. Doygunluk fiti `ER = a*N^-b + c`

| Yol | a | b | c (taban) | c %95 GA | RMSE | Nokta | Yeniden ornekleme |
|---|---|---|---|---|---|---|---|
| `policy` | 0.2442 | 0.3000 | **0.0003** | [0.0001; 0.0066] | 0.0006 | 7 | 2000 |
| `value` | 6.1105 | 0.7000 | **0.0223** | [0.0148; 0.0252] | 0.0023 | 7 | 2000 |

`c` **taban parametresidir**: veri sonsuza giderken ER'nin indigi deger. Log-egim modeli taban tasimaz (ER sifira iner), ki bu gercek degildir. `c` icin GA **oyun kumeleri** uzerinden bootstrap ile hesaplanir; nokta tahmini tek basina kanit sayilmaz (Kural 3).

## 4.2 "N icin gereken veri" (K4)

Etiket yalnizca tohum tutarliligina birakilmaz. Fit edilmis `ER = a*N^-b + c` modeli ters cozulur: hedef ER'ye ulasmak kac pozisyon ister? Hedef, olculen en iyi ER'nin **0.5000** kati (yani "ER'yi yariya indirmek").

| Yol | En iyi ER | Hedef | Taban c | Gereken N | Butce | Etiket |
|---|---|---|---|---|---|---|
| policy | 0.0158 | 0.0079 | 0.0003 | 103433 | 1056000 | `olcek` |
| value | 0.0330 | 0.0165 | 0.0223 | **ulasilamaz** | 1056000 | `pipeline` |

`ulasilamaz` = hedef, fit edilmis tabanin **altinda**: hicbir veri miktari o seviyeye indirmez. Bu, o yol icin **pipeline** sorunudur, olcek sorunu degil. Butce = en buyuk olcumun 100.0000 kati.

## 5. Karar

**`olcek`**

Egim esigin uzerinde: veri ikiye katlandiginda ER olculebilir bicimde dusuyor. **Olcek buyutmek dogru kaldiractir.**

## 6. Notlar

- tohum 1: kazanc 0.0062 GA [0.0055; 0.0069] -> olcek
- tohum 2: kazanc 0.0059 GA [0.0053; 0.0066] -> olcek
- tohum 3: kazanc 0.0067 GA [0.0060; 0.0075] -> olcek
- tohum 4: kazanc 0.0060 GA [0.0053; 0.0066] -> olcek
- tohum 5: kazanc 0.0062 GA [0.0055; 0.0069] -> olcek
- Havuzlanmis 5 tohum: 1, 2, 3, 4, 5

