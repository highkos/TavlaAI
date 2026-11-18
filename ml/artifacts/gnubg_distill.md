# Faz 7 - gnubg ogretmen deneyi

Soru: **etiketler mi yetersiz, kapasite mi?** gnubg 2-ply
etiketleriyle **politika** kafasi egitilir ve ER yeniden olculur.

> **Neden politika, deger degil?** ER `er_harness` icinde **politika**
> basi argmax ile olculur (`criterion="policy"`). Deger kafasini
> egitmek bu karar yolunda okunmaz; olculen ER'yi tanimi geregi
> degistirmez. Bu, olcumle dogrulandi (bkz. bolum 2).

## 1. Veri kumesi

| Olcum | Deger |
|---|---|
| Pozisyon | 2000 |
| Atlanan | 0 |
| Hedef ortalama | +0.2410 |
| Hedef std | 0.5658 |
| Hedef min / max | -1.6430 / +2.0130 |

## 2. Deger kafasi denemesi (yetersiz kaldi)

| Olcum | Deger |
|---|---|
| Egitim MAE | 0.0072 |
| Korelasyon | 0.9996 |
| Egim | 1.0026 |
| Olculen ER | 0.0708 |

Egitim metrikleri neredeyse kusursuz, ama ER degismedi:
deger kafasi **politika argmax** yolunda okunmuyor.

## 3. Politika damitma (asil hat)

| Olcum | Deger |
|---|---|
| Adim | 4000 |
| Aday genisligi (en fazla) | 346 |
| Deger agirligi | 0.50 |
| Ilk / son kayip | 1.466293 / 0.000548 |
| Egitim top-1 | 1.0000 |

> Egitim top-1 **ezberdir**, genelleme degil. Gercek olcu VAL-ER'dir.

## 4. Karar

**`belirsiz`**

Nokta tahmini iyilesti ama eslesmis %95 GA **sifiri dislamiyor**: fark gurultuden ayirt edilemiyor. Ne 'etiketler ise yaradi' ne 'etiketler ise yaramadi' denebilir. Karar icin daha fazla pozisyon gerekir.

| Olcum | Deger |
|---|---|
| ER once | 0.0708 |
| ER sonra | 0.0533 |
| Hedef | 0.0300 |
| Iyilesme | 24.7% |

### 4.1 Eslesmis test

| Olcum | Deger |
|---|---|
| Pozisyon | 70 |
| Ortalama fark | +0.0176 |
| Std hata | 0.0121 |
| t | +1.45 |
| GA95 | [-0.0062; +0.0414] |
| Sifiri disliyor | **hayir** |

> GA sifiri dislamiyor: nokta tahmini iyilesme gosterse de fark **gurultuden ayirt edilemiyor**. Bu yuzden kazanc kanitlanmis sayilmaz.

### 4.2 Veri hacmi kollari

| Kol | Pozisyon | ER | Fark (once) | GA95 | Sifiri disliyor |
|---|---|---|---|---|---|
| 2000 | 70 | 0.0533 | +0.0176 | [-0.0062; +0.0414] | **hayir** |
| 10000 | 70 | 0.0617 | +0.0091 | [-0.0209; +0.0392] | **hayir** |

> Veri hacmi arttikca ER'nin **monoton** iyilesmesi beklenir. Iyilesmiyorsa kol farki gurultudur; hacim tek basina cozum degildir.

## 5. Durustluk notlari

- Egitim top-1 1.0000 **ezberdir**, genelleme degil: veri kumesi `medium` profilin kapasitesinin altinda. Gercek olcu VAL-ER'dir.
- Eslesmis test (n=70): ortalama fark +0.0176, GA95 [-0.0062; +0.0414], t=+1.45. GA sifiri **dislamiyor**.
- gnubg GPL'dir: etiketler yalnizca arastirma/olcum icindir, urun dagitimi oncesi lisans netlestirilmelidir.

> gnubg GPL lisanslidir. Bu modulun urettigi etiketler yalnizca arastirma ve olcum icindir; urun dagitimi oncesinde lisans netlestirilmelidir.

