# Faz 7-R - Seviye farki (ppg) olcumu

gnubg kendine-oynama. Money: **2400** oyun/hucre. Mac: **40** mac/hucre. **6** paralel isci.

Guven araligi kume bootstrap'i (20000 yeniden ornekleme): money'de kume = oyun, mac oyununda kume = mac.

## Karsilastirmalar

| Karsilastirma | Baglam | Kume | Oyun | Fark (ppg) | %95 GA | sigma (oyun) | sigma (kume) | sigma (kullanilan) |
|---|---|---|---|---|---|---|---|---|
| 0-ply vs 2-ply | money | 2400 | 2400 | -0,2229 | [-0,3425; -0,1037] | 2,9960 | 2,9960 | 2,9960 |
| 0-ply vs 2-ply | mac-5 | 40 | 99 | -0,8546 | [-1,8950; 0,1867] | 3,1919 | 5,3717 | 5,3717 |
| 0-ply vs 2-ply | mac-9 | 40 | 233 | -1,2169 | [-2,3245; -0,3527] | 2,9112 | 7,9001 | 7,9001 |
| 2-ply vs 3-ply | money | 400 | 400 | -0,0625 | [-0,3600; 0,2400] | 3,0581 | 3,0581 | 3,0581 |
| 2-ply vs 3-ply | mac-5 | 40 | 113 | 0,1096 | [-0,8279; 1,1388] | 3,0157 | 5,3569 | 5,3569 |
| 2-ply vs 3-ply | mac-9 | 40 | 213 | -0,8990 | [-1,8590; -0,0512] | 4,1504 | 6,8013 | 6,8013 |

## Turetilen marj

- Kaynak: **0-ply vs 2-ply @ money**
- Yontem: GA sifiri disliyor: m saglam
- **m = 0,1115 ppg** (olculen farkin 0,50 kati)

## Gereken oyun sayisi (sigma ust siniri, Kural 4)

| Hucre | Gereken oyun |
|---|---|
| 0-2@money | 4337 |
| 0-2@mac-5 | 13942 |
| 0-2@mac-9 | 30155 |
| 2-3@money | 4519 |
| 2-3@mac-5 | 13866 |
| 2-3@mac-9 | 22351 |

## Sinirlar

- Bu bir **seviye farki** olcumudur (gnubg'ye karsi gnubg), insan sampiyona karsi bir iddia degildir.
- Mac oyununda mac sonu oyunu kirpilir; ppg mac basina gozlem sayilir.
- 4-ply chequerplay bu makinede oyun basina 60 s'yi astigi icin ikincil karsilastirma 2-ply vs 3-ply olarak olculdu.
