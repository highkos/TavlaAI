# Insan karsilastirma merdiveni (Test 94)

| Alan | Deger |
|---|---|
| Hakem derinligi | gnubg `hint`, 3-ply (filtre acik) |
| Pozisyon | 60 (atlanan 0) |
| Sure | 642.6 s (10.71 s/pozisyon) |

## Basamaklar

| # | Referans | Kaynak | n | Kapsama | ER | GA |
|---|---|---|---|---|---|---|
| 0 | gnubg 0-ply | measured | 60 | 86.7% | 0.0522 | [0.0270; 0.0773] |
| 1 | gnubg 1-ply | measured | 60 | 80.0% | 0.0530 | [0.0274; 0.0787] |
| 2 | gnubg 2-ply | measured | 60 | 91.7% | 0.0525 | [0.0264; 0.0785] |
| 3 | gnubg 3-ply (hint) | self | 60 | 100.0% | 0.0000 | [0.0000; 0.0000] |
| 4 | gnubg 4-ply (hint) | **olculmedi** | - | - | - | - |
| 5 | Dunya sampiyonu insan | **literatur** | - | - | 0.0025 | - |
| 6 | gnubg 4-ply + buyuk ag | **literatur** | - | - | 0.0030 | - |

## Karar

**measured** - Merdiven olculdu: 2-ply basamagi ER 0.0525, GA [0.0264; 0.0785], kapsama 91.7%. Sampiyon iddiasi modelin kendi ER'siyle verilir.

## Yontem notu

2-ply degerleri gnubg `eval` ile, 3-ply ve 4-ply degerleri gnubg `hint` ile olculur (F7-04). Iki protokol ayni pozisyonda birebir ayni sonucu vermez; 2/3 sinirindaki merdiven adimi elma-elmadir degildir.

5. ve 6. basamak **olculmedi**: literatur degeridir ve oyle
etiketlenmistir. 4. basamak da **olculmedi**: 4-ply `hint` maliyeti
sinirsizdir (F7-07). Kendi modelimizin ER'si 0-3 basamaklarinda olculur.
