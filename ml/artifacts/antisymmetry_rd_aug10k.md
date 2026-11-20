# Faz 7-R - Renk takasi (antisimetri)

Soru: **model renk takasinda ayni seyi mi soyluyor?**

Model: `ml\runs\rd_aug10k\onnx\model_v10.onnx`

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | -0,9426 | `\|corr\| >= 0.99` | DUSTU |
| ER farki GA | [-0,0391; -0,0216] | sifiri icermeli | DUSTU |

| Ayrinti | Deger |
|---|---|
| Vaka | 1000 |
| Girdi renk-simetrisi (`flip_perspective`) | 0/24436 uyusmazlik |
| `mean \|e(+1)+e(-1)\|` | 0,2827 |
| `max \|e(+1)+e(-1)\|` | 1,9108 |
| `\|e(+1)+e(-1)\| <= 0,001` | 456/24436 |
| Politika antisimetrisi (`argmax(+1) == argmin(-1)`) | 392/1000 (0,3920) |
| ER(+1) | 0,0485 |
| ER(-1) | 0,0788 |
| ER farki | -0,0302 |

**Karar: DUSTU**

## Notlar

- Girdi vektoru renk takasinda simetrikse kusur **modelde**dir; girdi simetrisi bu raporda ayrica olculur.
- Kapi bir **teshis**tir: `|corr| >= 0.99` bu mimariyle ulasilabilir degil. Karar iki bakisli ER (F7-101) ve ppg ile verilir.
- KORELASYON KAPISI DUSTU: |corr| = 0.9426 < 0.99
- ER FARKI KAPISI DUSTU: GA [-0.0391; -0.0216] sifiri disliyor

