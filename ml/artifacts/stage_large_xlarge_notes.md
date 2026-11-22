## Yorum

### 1. Kapasite değer kafasına yarıyor, ama yavaş

Değer ER'si kapasiteyle **tekdüze** düşüyor: 0,038926 → 0,036066 → 0,035147.
Yön doğru, eğim yanlış: 11,5× parametre (156 bin → 1,8 milyon) yalnızca
**%9,7** kazanç getiriyor. Test 96 eşiği %15; hiçbir profil geçmiyor.

`large`'ın `medium`'a göre kazancı %7,3 ve standart hatalar (0,0033 / 0,0032)
farkı neredeyse yutuyor. Yani `large` ile `medium` arasındaki fark bu
örneklemde **anlamlı değil**; `xlarge` ile `medium` arasındaki fark sınırda.

### 2. Politika kafası kapasiteden **kazanmıyor**, kaybediyor

Politika ER'si ters yönde: `medium` 0,016824 en iyi, `large` 0,018694,
`xlarge` 0,018891. Üçü de aynı veri kümesinde, aynı adım sayısıyla eğitildi.
Yorum: 30 bin pozisyon, 665 bin aday, 156 bin parametreli bir ağ için
**zaten yeterli**; daha büyük ağ aynı sinyali daha çok ezberliyor. Eğitim
CE'si de bunu söylüyor — `medium` 0,4338, `large` 0,3900, `xlarge` 0,4394
(`xlarge` erken durduğu için karşılaştırılabilir değil), doğrulama CE'si ise
tersine dönüyor.

### 3. `xlarge` erken durdu — bu bir uyarı, sonuç değil

`xlarge` 2000. adımda en iyi doğrulama CE'sine ulaşıp 6 değerlendirme
boyunca iyileşmedi ve durdu (5000 adımın %40'ı). Yani 1,8 milyon parametre
30 bin pozisyonu **taşımıyor**. `xlarge`'ı ciddiye almak için veri hacminin
en az 3–5× artması gerekir; bu turda ölçülen şey "kapasite tavanı" değil,
"veri tavanı"dır.

### 4. `search1` `large`'ı işaret ediyor

Ürün yolu `search1`. Orada `large` **%15,5** kazançla eşiği geçiyor
(0,026074 → 0,022040), `xlarge` ise %7,0'da kalıyor. Bu, değer-ER kuralının
görmediği bir sinyal: `large`'ın değer kafası mutlak olarak çok daha iyi
değil ama **sıralaması** daha iyi, ve arama sıralamadan faydalanıyor
(§36.24'ün bulgusu). Yine de tek ölçüm, tek tohum, 1000 vaka — bu bir
**aday**, karar değil.

### 5. Antisimetri kapısı hiçbir profilde geçmiyor

| Profil | corr | meanAbsSum | ER(+1) | ER(−1) |
|---|---|---|---|---|
| `medium` | −0,9016 | 0,2944 | 0,01900 | 0,24496 |
| `large` | −0,9428 | 0,2384 | 0,02115 | 0,24532 |
| `xlarge` | −0,8370 | 0,4211 | 0,01741 | 0,28647 |

`large` en yakın (−0,9428) ama eşik 0,99. `xlarge` **daha kötü** — kapasite
artışı bu kusuru düzeltmiyor, hatta büyütüyor. Bu, F7-101/F7-105'in
"kusur mimaride, kapasitede değil" teşhisini doğruluyor: çözüm
`augment_perspectives` (R-D) veya çıkarım anı antisimetrikleştirmesi, kapasite
değil.

### 6. Karar

**Test 96 kuralı gereği kazanan yok.** Ürün için öneri:

- **Varsayılan model `medium` olarak kalır.** Politika yolunda en iyi, en
  hızlı (354 s / 5000 adım), en küçük (156 bin parametre → ONNX ~1,6 MB).
- **`large` `search1` için aday olarak işaretlenir**, ancak R-D sonrası
  (artırımlı eğitimle) yeniden ölçülmeden ürüne alınmaz.
- **`xlarge` bu veri hacminde elenir.** 100 bin+ pozisyon olmadan tekrar
  denenmemeli.

### 7. Açık kalan

- Tek tohum. Üç profilin her biri tek koşu; tohum varyansı ölçülmedi.
  `large`–`medium` farkı (%7,3) tohum gürültüsünden büyük olduğu
  **gösterilmedi**.
- `search1` kazancı 1000 vaka üzerinden; `large` için SE 0,001543,
  `medium` için 0,001924. Fark 0,004034, yani ~1,7 SE — sınırda.
- `xlarge` erken durduğu için "kapasite işe yaramıyor" sonucu **yalnızca bu
  veri hacminde** geçerli.
- Antisimetri ölçümü 500 vaka; `large`'ın −0,9428'i ile `medium`'ın −0,9016'sı
  arasındaki fark bu örneklemde anlamlı mı, ölçülmedi.
