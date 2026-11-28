# Sans-duzeltilmis H2H para oyunu (Faz 8 Adim A1)

Model: `ml\runs\capacity100k_rd_sweep\xlarge\seed1\model.onnx`
Yol: `search1` · rakip: **self-play** · referans: `value`

| Olcum | Ham | Sans-duzeltilmis |
|---|---|---|
| ppg | +0.0000 | **+0.0000** |
| Standart hata | 0.00000 | **0.00000** |
| %95 GA (1,96 SE) | [+0.0000; +0.0000] | [+0.0000; +0.0000] |
| %95 GA (eslestirilmis bootstrap) | [+0.0000; +0.0000] | [+0.0000; +0.0000] |

| Kosul | Deger |
|---|---|
| Oyun / cift | 200 / 100 |
| Paralel surec | 10 |
| Tohum | 0 |
| beta (sabit) | 1.0000 |
| beta* (bilgi) | 0.0000 |
| Oyun basina ply | 51.7 |
| Bitmeyen oyun | 0 (0.0000) |
| Denetim noktasindan gelen cift | 0 |

## Varyans indirgeme

| Olcum | Deger |
|---|---|
| Sans ortalamasi (ppg) | +0.0000 |
| Sans standart sapmasi | 0.0000 |
| Puan standart sapmasi | 0.0000 |
| Duzeltilmis standart sapma | 0.0000 |
| corr(Y, L) | - |
| Varyans orani R = s_Y^2 / s_Z^2 | - |
| SE azalmasi | - |
| SE kazanci (kat) | - |

## Karar (m = 0.1115 ppg)

`equivalence_verdict` (sans-duzeltilmis) -> **esdeger**

`equivalence_verdict` (ham) -> **esdeger**

## Yontem

Her zar olayinda 21 zar icin referans devam equity'si hesaplanir;
gerceklesen zarin katkisi kendi ortalamasina gore merkezlenir
(`D_t = q(R_t) - qbar_t`). Toplam sans `L` oyundan dusulur:
`Z = Y - beta*L`, `beta = 1`. `E[D_t | H_t] = 0` oldugu icin duzeltme
**yansizdir**; kazanc yalnizca varyanstan gelir.

Ayni tablo girdisi hem gerceklesen zar hem ortalama icin kullanilir
(oynanan hamle kullanilsaydi yanlilik eklenirdi). Referans ve `beta`
olcumden **once** sabitlendi; `beta*` yalniz bilgi amaclidir.

Birim **cift**tir (ayni zar dizisinin iki rengi); `mean(cift
ortalamalari)` oyun duzeyindeki ortalama ile aynidir, standart hata
kumelenmistir.

