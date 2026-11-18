# Faz 7 - Mac gucu analizi

Soru: **bir iddiayi kanitlamak icin kac oyun gerekir?** Bu rapor
her iddiayi gerekli n ve saptanabilir etki olarak yazar.

## 1. Mevcut hacim

| Olcum | Deger |
|---|---|
| Oyun | 200 |
| Kazanma orani (varsayim) | 0.5500 |
| Kazanma orani GA yari genisligi | 0.0689 |
| ppg sigma | 2.4000 |
| ppg GA yari genisligi | 0.3326 |

## 2. Gurultu tabani

| Oyun | Kazanma orani +/- | ppg +/- |
|---|---|---|
| 100 | 0.0975 | 0.4704 |
| 200 | 0.0689 | 0.3326 |
| 400 | 0.0488 | 0.2352 |
| 1000 | 0.0308 | 0.1488 |
| 5000 | 0.0138 | 0.0665 |
| 20000 | 0.0069 | 0.0333 |
| 100000 | 0.0031 | 0.0149 |

## 3. Gereken n

| Iddia | Gereken |
|---|---|
| Kazanma orani +/-0,05 (tek ornek) | 381 |
| ppg +/-0,10 | 2213 |
| ppg +/-0,05 | 8851 |
| Sampiyonu yenme iddiasi (kol basina) | 1565 |
| ppg farki iddiasi (kol basina) | 9042 |
| Mac kazanma orani +/-0,05 (mac sayisi) | 381 |

## 4. Notlar

- 200 oyunda kazanma orani icin GA yari genisligi 0.0689 (incelemenin isaret ettigi gurultu esigi 0.05).
- 200 oyunda ppg icin GA yari genisligi 0.3326 (sigma = 2.40).
- ppg olculmeden yalnizca kazanma oranina bakmak, mars oranini artiran bir modeli oldugundan **zayif** gosterir.
- 200 oyun gurultu esigi esiginin ALTINDA: bu hacimde '%40,0 vs %39,5' gibi bir fark **gurultudur**, olcum degil.
- Iddia edilen fark 0.0050, 200 oyunda saptanabilir en kucuk fark 0.0689: oran 13.8x. Bu fark bu hacimde **olculemez**; gucu yetmiyor.

