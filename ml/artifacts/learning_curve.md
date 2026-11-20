# Faz 7-R - Ogrenme egrisi

Soru: **ER hedefin uzerindeyse, daha cok veri mi yoksa onarilmis
bir hat mi gerekiyor?** Ayni hat, ayni tohum, yalnizca veri hacmi
degisir. Karar, ER'nin `log2(veri)` basina egiminden verilir.

## 1. Noktalar

| Carpan | Pozisyon | ER `policy` | ER `value` | ER `search1` | Kal. egimi | Kal. MAE | In-sample | In-sample birimi | Held-out |
|---|---|---|---|---|---|---|---|---|---|
| 1x | 165 | 0.0504 | 0.2114 | - | - | - | 1.1721 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0504 |
| 2x | 330 | 0.0414 | 0.2245 | - | - | - | 0.8910 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0414 |
| 4x | 660 | 0.0341 | 0.1099 | - | - | - | 0.5563 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0341 |
| 8x | 1320 | 0.0267 | 0.0523 | - | - | - | 0.3413 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0267 |
| 16x | 2640 | 0.0215 | 0.0473 | - | - | - | 0.2204 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0215 |
| 32x | 5280 | 0.0166 | 0.0398 | - | - | - | 0.2553 | karisik: capraz-entropi (nat/pozisyon) + w*MSE (equity^2) | 0.0166 |

> **In-sample metrikler basari sayilmaz** (Kural 5). Held-out
> kolonu tek basina okunmalidir. In-sample kolonu bir ER
> **degildir**: birimi yanindaki sutunda yazilidir.

## 2. Egim (ER / log2 veri)

| Yol | Kazanc | %95 GA | Ham egim | Nokta | Kume | Yeniden ornekleme |
|---|---|---|---|---|---|---|
| `policy` | 0.0067 | [0.0061; 0.0073] | -0.0067 | 6 | 200 | 20000 |
| `value` | 0.0414 | [0.0396; 0.0449] | -0.0414 | 6 | 200 | 20000 |

Kume bootstrap'i: **oyun** (oyun duzeyinde = dogru; pozisyon duzeyinde GA'yi yapay daraltir).

Tohumlar: **1, 2, 3, 4, 5** (havuzlanmis).

**Kazanc** = ER'nin `log2(veri)` basina **dususu** (pozitif = veri arttkca ER iyilesiyor). Ham egim ayni buyuklugun isaretli hali.

Esik: **0.0050** (ER kazanci / log2 veri).

## 3. Tohum bazli kararlar

| Tohum | Kazanc | Karar |
|---|---|---|
| 1 | 0.0068 | `olcek` |
| 2 | 0.0062 | `belirsiz` |
| 3 | 0.0066 | `olcek` |
| 4 | 0.0056 | `belirsiz` |
| 5 | 0.0085 | `olcek` |

**Tohum oybirligi: YOK.** Havuzlanmis bootstrap tohumlari ek veri gibi ele alir ve GA'yi daraltir; bu yuzden havuz karari tek basina yetmez. `olcek`/`pipeline` icin **tum tohumlarin** ayni karari vermesi gerekir.

## 4. Doygunluk fiti `ER = a*N^-b + c`

| Yol | a | b | c (taban) | RMSE | Nokta |
|---|---|---|---|---|---|
| `policy` | 0.2865 | 0.3500 | **0.0033** | 0.0008 | 6 |
| `value` | 5.0251 | 0.6000 | **0.0087** | 0.0298 | 6 |

`c` **taban parametresidir**: veri sonsuza giderken ER'nin indigi deger. Log-egim modeli taban tasimaz (ER sifira iner), ki bu gercek degildir.

## 5. Karar

**`belirsiz`**

Egim guven araligi esigi kesiyor: **karar verilemez**. Daha fazla nokta ya da daha buyuk korpus gerekir.

## 6. Notlar

- tohum 1: kazanc 0.0068 GA [0.0056; 0.0080] -> olcek
- tohum 2: kazanc 0.0062 GA [0.0049; 0.0076] -> belirsiz
- tohum 3: kazanc 0.0066 GA [0.0053; 0.0077] -> olcek
- tohum 4: kazanc 0.0056 GA [0.0044; 0.0067] -> belirsiz
- tohum 5: kazanc 0.0085 GA [0.0068; 0.0099] -> olcek
- TOHUM OYBIRLIGI YOK: s1=olcek, s2=belirsiz, s3=olcek, s4=belirsiz, s5=olcek -> havuz karari 'belirsiz' sayilir
- Havuzlanmis 5 tohum: 1, 2, 3, 4, 5

