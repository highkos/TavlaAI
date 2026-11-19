# Faz 7-R - Ogrenme egrisi

Soru: **ER hedefin uzerindeyse, daha cok veri mi yoksa onarilmis
bir hat mi gerekiyor?** Ayni hat, ayni tohum, yalnizca veri hacmi
degisir. Karar, ER'nin `log2(veri)` basina egiminden verilir.

## 1. Noktalar

| Carpan | Pozisyon | ER `policy` | ER `value` | ER `search1` | Kal. egimi | Kal. MAE | In-sample | Held-out |
|---|---|---|---|---|---|---|---|---|
| 1× | 500 | 0.0395 | 0.1463 | - | - | - | 0.6667 | 0.0395 |
| 2× | 1000 | 0.0287 | 0.0782 | - | - | - | 0.3573 | 0.0287 |
| 4× | 2000 | 0.0242 | 0.0460 | - | - | - | 0.2883 | 0.0242 |
| 8× | 4000 | 0.0189 | 0.0454 | - | - | - | 0.1788 | 0.0189 |

> **In-sample metrikler basari sayilmaz** (Kural 5). Held-out
> kolonu tek basina okunmalidir.

## 2. Egim (ER / log2 veri)

| Yol | Kazanc | %95 GA | Ham egim | Nokta | Kume | Yeniden ornekleme |
|---|---|---|---|---|---|---|
| `policy` | 0.0066 | [0.0053; 0.0080] | -0.0066 | 4 | 120 | 20000 |
| `value` | 0.0335 | [0.0298; 0.0387] | -0.0335 | 4 | 120 | 20000 |

Kume bootstrap'i: **oyun** (oyun duzeyinde = dogru; pozisyon duzeyinde GA'yi yapay daraltir).

Tohumlar: **1, 2, 3** (havuzlanmis).

**Kazanc** = ER'nin `log2(veri)` basina **dususu** (pozitif = veri arttkca ER iyilesiyor). Ham egim ayni buyuklugun isaretli hali.

Esik: **0.0050** (ER kazanci / log2 veri).

## 3. Karar

**`olcek`**

Egim esigin uzerinde: veri ikiye katlandiginda ER olculebilir bicimde dusuyor. **Olcek buyutmek dogru kaldiractir.**

## 4. Notlar

- Havuzlanmis 3 tohum: 1, 2, 3
- tohum 1: kazanc 0.0062 GA [0.0039; 0.0089] -> belirsiz
- tohum 2: kazanc 0.0073 GA [0.0051; 0.0096] -> olcek
- tohum 3: kazanc 0.0064 GA [0.0040; 0.0088] -> belirsiz

