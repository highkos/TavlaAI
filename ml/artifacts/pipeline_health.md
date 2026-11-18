# Faz 7 - Pipeline sagligi

Soru: **sorun olcek mi, pipeline mi?** Bu rapor her iddiayi ayri bir
kapiya baglar. Kapilar bagimsizdir; hepsi gereklidir.

## 1. Kapilar

| Kapi | Olcut | Deger | Sonuc |
|---|---|---|---|
| G1 | PipBot kazanma orani >= 0,90 | 0.9950 | **GECTI** |
| G2 | Kalibrasyon egimi [0,85; 1,15] | 0.6743 | **DUSTU** |
| G3 | Kalibrasyon MAE < 0,15 | 0.2683 | **DUSTU** |
| G4 | Korelasyon > 0,90 | 0.9016 | **GECTI** |
| G5 | Std orani [0,85; 1,15] | 1.3371 | **DUSTU** |
| G6 | 2-ply ER < 0,02 | 0.0740 | **DUSTU** |
| G7 | Hedef sacilimi cokmemis (> 0,5) | 3.0227 | **GECTI** |

## 2. Teshis

**`pipeline`**

Teshis **pipeline**. Model PipBot'u yeniyor ama deger kafasi bozuk (kalibrasyon/MAE/std orani). Bu durumda olcek buyutmek ise yaramaz: daha buyuk model daha emin bir sekilde yanlis olur. Once hedef/kayip/kalibrasyon hattini onarin.

## 3. Hedef sacilimi (G7)

| Olcum | Deger |
|---|---|
| Karar | 1108 |
| Hedef std | 1.3542 |
| Terminal std | 0.4480 |
| Oran | 3.0227 |
| Hedef ortalamasi | -0.0090 |
| Terminal ortalamasi | 1.2780 |
| Sifir hedef orani | 0.0000 |

## 4. Kaynaklar

| Rol | Dosya |
|---|---|
| calibration | `ml\artifacts\stage_h_calibration_2ply.json` |
| er | `ml\artifacts\stage_h_er_2ply.json` |
| eval | `ml\artifacts\stage_h_eval_pip.json` |

