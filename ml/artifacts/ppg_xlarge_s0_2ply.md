# Faz 7-R - Model vs gnubg 2-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\capacity30k_rd_sweep\xlarge\seed0\model.onnx`
Yol: `search1`
gnubg: **2-ply**

| Olcum | Deger |
|---|---|
| Oyun | 4400 (2200 cift) |
| Paralel surec | 10 |
| Kazanma | 1859/4400 (0.4225) |
| **ppg** | **-0.2623** |
| ppg %95 GA | [-0.3039; -0.2198] |
| ppg standart hata | 0.0214 |
| Eslestirilmis fark (beyaz+siyah) | -0.5245 |
| Eslestirilmis fark %95 GA | [-0.6023; -0.4473] |
| Oyun basina ply | 56.2 |
| Bitmeyen oyun | 0 (0.0000) |
| Denetim noktasindan gelen cift | 27 |

**Yorum.** ppg > 0 ise model gnubg 2-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

## Karar (m = 0.1115 ppg)

`equivalence_verdict(ppg = -0.2623, ciLow = -0.3039, ciHigh = -0.2198, m = 0.1115)`

GA'nin ust ucu **-0.2198 < -m = -0.1115**. Yani xlarge, gnubg 2-ply'a karsi
esdegerlik marjindan **daha kotu**; sonuc `daha-kotu`.

## Taban ile karsilastirma

| Model | ppg | %95 GA | Karar |
|---|---:|---|---|
| large seed0 (taban) | -0.2445 | [-0.3055; -0.1835] | `daha-kotu` |
| **xlarge seed0** | **-0.2623** | **[-0.3039; -0.2198]** | **`daha-kotu`** |

Iki GA buyuk olcude ortusuyor; nokta tahminleri arasindaki fark (-0.0178 ppg)
standart hatanin (0.0214) **altinda**. Yani xlarge, large'dan ppg'de anlamli
olarak iyi degil: egitim valTop1'de 0.0093 daha iyi olmasi oyun gucune
tasinmadi.

Bu, kapasite taramasinin (F7-116) bulgusuyla tutarli: 30k pozisyonda medium,
large ve xlarge arasinda hicbir karsilastirma anlamli cikmadi (en kucuk
p = 0.1880). Kapasite artisi **veriyle sinirli**, model genisligiyle degil.

## Karar agaci sonucu

```
ppg bitti mi? -> Evet
xlarge ppg, medium'dan iyi mi? -> HAYIR
  -> Veriyi 100K+'a cikar, xlarge'i tekrar dene.
```

Bu dal secildi. Hazir plan: `EVREN.md` §9. Etiketleme betigi:
`ml/runs/capacity100k_rd/run_label.ps1` (12 dilim x 8335 = 100 020 pozisyon).

## Notlar

* `resumedPairs = 27`: kosu bir kez kesildi ve denetim noktasindan devam etti.
  Denetim noktasi anahtari model + yol + plies + tohum iceriyor, yani devam
  eden ciftler ayni kosuya ait.
* `unfinished = 0`: 200 hamle sinirina takilan oyun yok, dolayisiyla ppg
  ortalamasi eksik oyunlardan etkilenmiyor.
* Ortalama 56.2 ply, taban olcumdeki 55.9 ile ayni; oyun uzunlugu degismedi,
  yani fark oyun stili degisikliginden degil karar kalitesinden geliyor.