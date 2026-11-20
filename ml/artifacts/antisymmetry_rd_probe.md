# Faz 7-R - Renk takasi (antisimetri)

Soru: **model renk takasinda ayni seyi mi soyluyor?**

Model: `runs\stage_rd_probe\onnx\model_v5.onnx`

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | -0,8119 | `\|corr\| >= 0.99` | DUSTU |
| ER farki GA | [-0,4998; -0,4456] | sifiri icermeli | DUSTU |

| Ayrinti | Deger |
|---|---|
| Vaka | 1000 |
| Girdi renk-simetrisi (`flip_perspective`) | 0/24436 uyusmazlik |
| `mean \|e(+1)+e(-1)\|` | 0,4782 |
| `max \|e(+1)+e(-1)\|` | 5,1612 |
| `\|e(+1)+e(-1)\| <= 0,001` | 619/24436 |
| Politika antisimetrisi (`argmax(+1) == argmin(-1)`) | 18/1000 (0,0180) |
| ER(+1) | 0,0573 |
| ER(-1) | 0,5297 |
| ER farki | -0,4723 |

**Karar: DUSTU**

## Notlar

- Girdi vektoru renk takasinda simetrikse kusur **modelde**dir; girdi simetrisi bu raporda ayrica olculur.
- Kapi bir **teshis**tir: `|corr| >= 0.99` bu mimariyle ulasilabilir degil. Karar iki bakisli ER (F7-101) ve ppg ile verilir.
- KORELASYON KAPISI DUSTU: |corr| = 0.8119 < 0.99
- ER FARKI KAPISI DUSTU: GA [-0.4998; -0.4456] sifiri disliyor

