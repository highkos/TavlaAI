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
| G5 | Std orani [0,7; 1,4] (Faz 6) | 1.3371 | **GECTI** |
| G6 | 2-ply ER < 0,02 | 0.0740 | **DUSTU** |
| G7 | Hedef sacilimi [0,5; 1,5] | 1.0000 | **GECTI** |

## 2. Teshis

**`pipeline`**

Teshis **pipeline**. Model PipBot'u yeniyor ama deger kafasi bozuk (kalibrasyon/MAE/std orani). Bu durumda olcek buyutmek ise yaramaz: daha buyuk model daha emin bir sekilde yanlis olur. Once hedef/kayip/kalibrasyon hattini onarin.

## 3. Hedef sacilimi (G7)

| Olcum | Deger |
|---|---|
| Karar | 627737 |
| Hedef std | 1.4839 |
| Terminal std | 1.4839 |
| Oran | 1.0000 |
| Hedef ortalamasi | -0.0101 |
| Terminal ortalamasi | -0.0101 |
| Sifir hedef orani | 0.0000 |
| Isaretli karsilastirma | evet |
| Eski (isaretsiz) oran | 2.8781 |

> **R-08 kapatildi.** Eski olcum isaretsiz terminal degeri (`resultPoints/cubeValue`) isaretli TD hedefleriyle karsilastiriyordu; oran bu yuzden yapisal olarak 1'in uzerine cikiyordu. Isaretli karsilastirmada oran 1.0000.

## 4. Olcekleme kaniti (R-10)

| Olcum | Deger |
|---|---|
| Durum | **`yok`** |
| Gerekce | ogrenme egrisi olculmedi |

> Ogrenme egrisi **olculmedi**. Bu, "olcek ise yaramaz" demek degildir; karar icin `ml/learning_curve.py` kosulmalidir.

## 5. Kaynaklar

| Rol | Dosya |
|---|---|
| calibration | `ml\artifacts\stage_h_calibration_2ply.json` |
| er | `ml\artifacts\stage_h_er_2ply.json` |
| eval | `ml\artifacts\stage_h_eval_pip.json` |

