# Sans-duzeltilmis H2H para oyunu (Faz 8 Adim A1)

Model: `ml\runs\capacity100k_rd_sweep\xlarge\seed1\model.onnx`
Yol: `search1` · gnubg: **2-ply** · referans: `value` (0-ply deger kafasi)

| Olcum | Ham | Sans-duzeltilmis |
|---|---|---|
| ppg | -0.4300 | **-0.2721** |
| Standart hata | 0.13016 | **0.06200** |
| %95 GA (1,96 SE) | [-0.6851; -0.1749] | [-0.3936; -0.1506] |
| %95 GA (eslestirilmis bootstrap) | [-0.6700; -0.1700] | [-0.3911; -0.1542] |

| Kosul | Deger |
|---|---|
| Oyun / cift | 100 / 50 |
| Paralel surec | 10 |
| Tohum | 0 |
| beta (sabit) | 1.0000 |
| beta* (bilgi) | 1.0447 |
| Oyun basina ply | 53.1 |
| Bitmeyen oyun | 0 (0.0000) |
| Denetim noktasindan gelen cift | 0 |

## Varyans indirgeme

| Olcum | Deger |
|---|---|
| Sans ortalamasi (ppg) | -0.1579 |
| Sans standart sapmasi | 0.7754 |
| Puan standart sapmasi | 0.9203 |
| Duzeltilmis standart sapma | 0.4384 |
| corr(Y, L) | 0.8801 |
| Varyans orani R = s_Y^2 / s_Z^2 | 4.408 |
| SE azalmasi | 52.4% |
| SE kazanci (kat) | 2.10x |

## Karar (m = 0.1115 ppg)

`equivalence_verdict` (sans-duzeltilmis) -> **daha-kotu**

`equivalence_verdict` (ham) -> **daha-kotu**

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

