# Kafa dengesi -- kayip ve govde gradyani (K5)

Kontrol noktasi: `ml/runs/rd_aug10k/checkpoints/ckpt_v10.pt`

Veri: `ml/runs/k5_dist/policy_dist_3k.npz` -- **3000** pozisyon, aday genisligi 292.

## Kayip buyuklugu

| Terim | Deger | Uretim kaybinda |
|---|---|---|
| Politika grup-softmax CE | 1.565903 | evet (c=1.0) |
| Deger skaler MSE | 0.120001 | evet (c=1.0) |
| Kalibrasyon MSE | 0.120001 | evet (c=0.1) |
| Deger 6 sinifli CE | 1.421306 | hayir (teshis) |
| KL(gnubg || model) | 0.131450 | hayir (teshis) |

## Govde gradyan normu

| Terim | ||dL/d(govde)|| |
|---|---|
| Politika | 1.418299 |
| Deger | 0.426250 |
| Kalibrasyon | 0.426250 |
| KL | 0.444869 |

| Oran | Deger |
|---|---|
| Kayip: politika / deger | 13.05 |
| Gradyan: politika / deger | **3.33** |
| Degerin govde gradyanindaki payi | 23.1% |

Paylasilan govde tek oldugu icin hangi terimin gradyani buyukse govdeyi o yonlendirir. **Karar sayisi kayip orani degil gradyan oranidir.**

