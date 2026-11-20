# Faz 7-R - Renk takasi (antisimetri)

Soru: **model renk takasinda ayni seyi mi soyluyor?**

Model: `ml\runs\rd_ctl10k\onnx\model_v10.onnx`

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | -0,8776 | `\|corr\| >= 0.99` | DUSTU |
| ER farki GA | [-0,0726; -0,0507] | sifiri icermeli | DUSTU |

| Ayrinti | Deger |
|---|---|
| Vaka | 1000 |
| Girdi renk-simetrisi (`flip_perspective`) | 0/24436 uyusmazlik |
| `mean \|e(+1)+e(-1)\|` | 0,6006 |
| `max \|e(+1)+e(-1)\|` | 3,5577 |
| `\|e(+1)+e(-1)\| <= 0,001` | 227/24436 |
| Politika antisimetrisi (`argmax(+1) == argmin(-1)`) | 295/1000 (0,2950) |
| ER(+1) | 0,0456 |
| ER(-1) | 0,1070 |
| ER farki | -0,0614 |

**Karar: DUSTU**

## Notlar

- Girdi vektoru renk takasinda simetrikse kusur **modelde**dir; girdi simetrisi bu raporda ayrica olculur.
- Kapi bir **teshis**tir: `|corr| >= 0.99` bu mimariyle ulasilabilir degil. Karar iki bakisli ER (F7-101) ve ppg ile verilir.
- KORELASYON KAPISI DUSTU: |corr| = 0.8776 < 0.99
- ER FARKI KAPISI DUSTU: GA [-0.0726; -0.0507] sifiri disliyor

