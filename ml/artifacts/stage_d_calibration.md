# Asama D - kalibrasyon onarimi (oncelikli)

Kaynak: `pairs.json`.
Bolme: CAL 200 / VAL 200 (tohum 20261117, Kural 10: onarim **yalnizca CAL**'da ogrenilir).

## Onarim oncesi / sonrasi (VAL)

| Metrik | Onarim oncesi | Onarim sonrasi | Kapi | Once | Sonra |
|---|---|---|---|---|---|
| Egim | 0,9992 | 1,0006 | 0,85 - 1,15 | gecti | gecti |
| Korelasyon | +0,9999 | +0,9999 | >= 0,75 | gecti | gecti |
| MAE | 0,0081 | 0,0081 | <= 0,15 | gecti | gecti |
| Std orani | 1,0007 | 0,9993 | 0,7 - 1,4 | gecti | gecti |

Affine onarim: `hedef ~ 0,9987 * tahmin + 0,0007`.

## Yorum

Affine onarim **dort kapiyi da** VAL'de geciyor.

**Korelasyon degismez.** Dogrusal bir donusum Pearson korelasyonunu degistirmez; bu yuzden affine onarim korelasyonu **artirmaz**. Korelasyon kapi disindaysa tek cozum **yeniden egitimdir** (`L_cal`, `c_cal = 0.1`).

**Bu rapor modeli kalibre demiyor.** Affine onarim, dagitimli urunde uygulanacak bir **cikti duzeltmesidir**; agin kendisi hala olcek kaciriyor olabilir. Asil cozum Asama D'nin `L_cal` egitimidir.
