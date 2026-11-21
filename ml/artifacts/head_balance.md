# Kafa dengesi -- kayip ve govde gradyani (K5)

Kontrol noktasi: `ml/runs/stage_d_l2/checkpoints/ckpt_v30.pt`

Veri: `ml/runs/k5_dist/policy_dist_3k.npz` -- **3000** pozisyon, aday genisligi 292.

## Kayip buyuklugu

| Terim | Deger | Uretim kaybinda |
|---|---|---|
| Politika grup-softmax CE | 1.394324 | evet (c=1.0) |
| Deger skaler MSE | 0.170902 | evet (c=1.0) |
| Kalibrasyon MSE | 0.170902 | evet (c=0.1) |
| Deger 6 sinifli CE | 1.480352 | hayir (teshis) |
| KL(gnubg || model) | 0.190459 | hayir (teshis) |

## Govde gradyan normu

| Terim | ||dL/d(govde)|| |
|---|---|
| Politika | 1.351443 |
| Deger | 0.914423 |
| Kalibrasyon | 0.914423 |
| KL | 0.632914 |

| Oran | Deger |
|---|---|
| Kayip: politika / deger | 8.16 |
| Gradyan: politika / deger | **1.48** |
| Degerin govde gradyanindaki payi | 40.4% |

Paylasilan govde tek oldugu icin hangi terimin gradyani buyukse govdeyi o yonlendirir. **Karar sayisi kayip orani degil gradyan oranidir.**

