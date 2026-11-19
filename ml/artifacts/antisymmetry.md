# Faz 7-R - Renk takasi (antisimetri)

Soru: **model renk takasinda ayni seyi mi soyluyor?**

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | -0,8915 | `\|corr\| >= 0.99` | DUSTU |
| ER farki GA | [-0,0620; -0,0340] | sifiri icermeli | DUSTU |

| Ayrinti | Deger |
|---|---|
| Vaka | 500 |
| Girdi renk-simetrisi (`flip_perspective`) | 0/12167 uyusmazlik |
| `mean \|e(+1)+e(-1)\|` | 0,7152 |
| `max \|e(+1)+e(-1)\|` | 3,0299 |
| `\|e(+1)+e(-1)\| <= 0,001` | 116/12167 |
| Politika antisimetrisi (`argmax(+1) == argmin(-1)`) | 174/500 (0,3480) |
| ER(+1) | 0,0396 |
| ER(-1) | 0,0875 |
| ER farki | -0,0479 |

**Karar: DUSTU**

## Notlar

- Girdi vektoru renk takasinda simetrikse kusur **modelde**dir; girdi simetrisi bu raporda ayrica olculur.
- Bu olcum R-D **oncesi** durumdur. R-D egitimi iki perspektif artirimi (`augment_perspectives`) veya girdi kanoniklestirmesi kullanmak zorunda; kapi R-D sonunda yeniden aranir.
- KORELASYON KAPISI DUSTU: |corr| = 0.8915 < 0.99
- ER FARKI KAPISI DUSTU: GA [-0.0620; -0.0340] sifiri disliyor

