# Kafa dengesi -- kayip ve govde gradyani (K5)

Kontrol noktasi: `ml/runs/rd_ctl10k/checkpoints/ckpt_v10.pt`

Veri: `ml/runs/k5_dist/policy_dist_3k.npz` -- **3000** pozisyon, aday genisligi 292.

## Kayip buyuklugu

| Terim | Deger | Uretim kaybinda |
|---|---|---|
| Politika grup-softmax CE | 1.469924 | evet (c=1.0) |
| Deger skaler MSE | 0.169684 | evet (c=1.0) |
| Kalibrasyon MSE | 0.169684 | evet (c=0.1) |
| Deger 6 sinifli CE | 1.460501 | hayir (teshis) |
| KL(gnubg || model) | 0.170645 | hayir (teshis) |

## Govde gradyan normu

| Terim | ||dL/d(govde)|| |
|---|---|
| Politika | 1.077796 |
| Deger | 0.903265 |
| Kalibrasyon | 0.903265 |
| KL | 0.505696 |

| Oran | Deger |
|---|---|
| Kayip: politika / deger | 8.66 |
| Gradyan: politika / deger | **1.19** |
| Degerin govde gradyanindaki payi | 45.6% |

Paylasilan govde tek oldugu icin hangi terimin gradyani buyukse govdeyi o yonlendirir. **Karar sayisi kayip orani degil gradyan oranidir.**

