# 100k veri ile xlarge — ppg sonucu

Soru: **veri 100k'ya cikinca xlarge medium/large'i geciyor mu?**

Model: `ml\runs\capacity100k_rd_sweep\xlarge\seed1\model.onnx`

| Olcum | Deger |
|---|---|
| Yol | `search1` |
| gnubg ply | 2 |
| Oyun / cift | 4400 / 2200 |
| ppg | **-0.1709** |
| ppg GA | [-0.2091; -0.1323] |
| Standart hata | 0.01966 |
| Tamamlanmamis oyun | 0 |
| Ortalama ply | 54.07 |

## Karar (m = 0.1115 ppg)

`equivalence_verdict` -> **daha-kotu**

Karar agaci dali: medium'da kal, veri buyutmeyi durdur (xlarge daha kotu)

## Tohum secimi (ER'ye bakmadan)

| Alan | Deger |
|---|---|
| Tohum | 1 |
| valTop1 | 0.8311 |
| valValueMse | 0.020163 |
| Parametre | 1805319 |
| En iyi adim | 14000 |

## Taban ile karsilastirma

| Kosu | ppg | GA | Oyun | Etiket |
|---|---|---|---|---|
| Taban (`ml\runs\capacity_rd\large\seed0\model.onnx`) | -0.2445 | [-0.3055; -0.1835] | 2000 | daha-kotu |
| 100k xlarge | -0.1709 | [-0.2091; -0.1323] | 4400 | daha-kotu |

Fark: **+0.0736** ppg
Fark standart hatasi: 0.03671
Fark bir standart hatanin icinde mi: **hayir**
Guven araliklari ortusuyor mu: **hayir**

## Notlar

- Karar kurali kosudan **once** sabitlendi: tohum secimi ER'ye bakmadan, m = 0.1115 ppg, uc sonuc dali.
- `esdeger` / `esdegerlik-kanitlanmadi` / `daha-kotu` etiketleri `H0: ppg_fark <= -m` testinin sonucudur; marj **para** oyunu icindir.
- ppg gnubg 2-ply hakeme karsi olculur; gnubg GPL lisanslidir, urun dagitimindan once lisans gozden gecirilmelidir.
