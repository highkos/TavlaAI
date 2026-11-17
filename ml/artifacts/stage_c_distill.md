# Faz 7 Asama C - Arama damitma (search distillation)

Bu rapor `faz 7.md` §5.4 ve §9.3'un uygulama kaydidir. Tum sayilar bu depoda
kosulan gercek kosulardan alinmistir; hicbir deger tahmin edilmemistir.

## 1. Amac

Uretim modeli 1-ply aramayla oynuyor (F7-09). 2-ply arama daha iyi karar veriyor
ama karar basina ~2,0 s suruyor (p95 2,85 s) ve 2 s butcesini asiyor. Bu yuzden
2-ply **uretimde** kullanilamaz; ancak **ogretmen** olarak kullanilip bilgisi
1-ply modelin agina aktarilabilir. Test 102'nin sorusu: bu aktarim, ayni veri
butcesiyle egitilen kontrol modeline gore VAL-ER'i en az %25 dusuruyor mu?

## 2. Shard uretimi (olculen)

Iki kol da ayni tohum, ayni oyun sayisi, ayni aday butcesi ile uretildi; tek
fark ogretmen derinligi ve `--distill` bayragi.

| Ozellik | Damitma kolu | Kontrol kolu |
|---|---|---|
| Komut | `Backgammon.SelfPlay --distill` | `Backgammon.SelfPlay` |
| Tohum | 7 | 7 |
| Oyun | 20 | 20 |
| Derinlik | 2 | 1 |
| `--max-root` / `--max-inner` | 4 / 4 | 4 / 4 |
| `--log-top` | 8 | 8 |
| `--dup-cap` | 0 | 0 |
| `--exploration` | 0 | 0 |
| Karar | 1 048 | 1 128 |
| Kayitli aday | 3 068 | 3 418 |
| `DEC_DISTILLED` isaretli karar | 1 048 | 0 |
| Shard boyutu | 110 656 B | 123 124 B |
| Duvari saati | **1 034,26 s** | **19,13 s** |

Damitma kolu oyun basina **51,7 s**, kontrol kolu **0,96 s** surdu: ogretmen
**54x** daha pahali. Bu, §5.1.1'deki butce hesabinin ana girdisidir.

Shard formati **degismedi** (surum 1). Ogretmenin kok degeri mevcut
`searchValue` alanina, politika hedefi mevcut `q` alanina yazildi; yeni alan
eklenmedi (F7-16). `DEC_DISTILLED = 16` bayragi yalnizca hangi kararlarin
ogretmenden geldigini isaretler; eski okuyucular bilinmeyen bayragi yok sayar.

## 3. Deger hedefi: F7-17 sapmasi

Shard, ogretmenin kok dagilimini **6 sinifli olasilik vektoru olarak tasimiyor**;
yalnizca skaler `searchValue` (equity) var. Bu yuzden damitma kolunda deger kafasi
6-sinifli capraz entropi ile degil, **equity regresyonu** ile egitildi:

    L_value = mean( (probs @ [1,2,3,-1,-2,-3] - searchValue)^2 )

Kalibrasyon terimi bu kolda **kapatildi** (`lcal = 0`): ayni buyuklugu iki kez
saymak, kalibrasyon cezasini yapay olarak sisirirdi. Kontrol kolu eski
TD-lambda + CE + kalibrasyon yolunu kullanmaya devam etti.

Bu bir **tasarim sapmasidir**, gizli bir varsayim degil: iki kol ayni kayip
fonksiyonuyla egitilmiyor. Sonuc yorumlanirken bu dikkate alinmalidir.

## 4. Egitim (iki kol)

Her iki kol da `ckpt_v30.pt` (Stage D L2, `val_er 0.0619`) agirliklarindan
baslatildi; ayni tohum (7), ayni adim sayisi (300), ayni profil (`medium`),
CPU.

| Olcum | Damitma | Kontrol |
|---|---|---|
| Buffer CE | 1,326893 -> 1,318205 | 0,013699 -> 0,012104 |
| Equity MAE | 1,050336 -> 1,050600 | 0,017474 -> 0,013991 |
| Kalibrasyon egimi | 1,0629 -> 1,0654 | 1,0033 -> 0,9993 |
| Politika kaybi | 0,851234 -> 0,851578 | 0,830396 -> 0,829809 |
| Sure | 26,0 s | 26,8 s |

Damitma kolunun CE/MAE'si **karsilastirilamaz**: farkli hedef (equity regresyonu,
olcek ~1,0) farkli sayi uretir. Kontrol kolunun CE'si 0,012'ye dusuyor cunku
20 oyunu ezberliyor - bu bir **asiri ogrenme** gostergesidir, basari degil.

## 5. Test 102 kapisi - SONUC: BASARISIZ

`python ml/distill_compare.py` ciktisi:

| Olcum | Kontrol | Damitilmis |
|---|---|---|
| Model | `ml/runs/stage_c_control_train/onnx/model_v2_trained.onnx` | `ml/runs/stage_c_distill_train/onnx/model_v2_trained.onnx` |
| Pozisyon (val) | 70 | 70 |
| VAL-ER (2-ply gnubg) | 0,0883 | 0,0602 |
| SE | 0,0153 | 0,0120 |

| Kazanc | Deger |
|---|---|
| Nokta tahmini | **0,3182** |
| Standart hata | 0,1803 |
| %95 GA | **[-0,0351; 0,6715]** |
| Esik | 0,25 |
| Kapi | **BASARISIZ** |

Nokta tahmini esigi **asiyor** (31,8% > 25%) ama guven araligi sifiri iceriyor.
`faz 7.md` §5.4'un kurali geregi bu **basari sayilmaz**: "Aksi halde damitma
basarisiz sayilir ve sapma raporlanir."

**Dogruluk notu:** bu sonuc "damitma ise yaramaz" demek degildir. Bu sonuc
"bu veri hacmiyle damitmanin ise yarayip yaramadigina karar verilemez" demektir.
Asagidaki guc hesabi bunu nicelestiriyor.

## 6. Neden gucsuz - gerekli n

Gozlenen dagilimlardan (SE x sqrt(n)): sigma_kontrol = 0,1280,
sigma_damitma = 0,1004, birlesik sigma = 0,1150, gozlenen fark = 0,0281.

| Hedef | Guc | Kol basina n |
|---|---|---|
| Gozlenen fark (0,0281) | %80 | **264** |
| Gozlenen fark (0,0281) | %90 | **353** |
| Tam %25 kazanc (0,0221) | %80 | **427** |

Mevcut kosu kol basina **70** pozisyon ve **20** oyun kullandi - gerekenin
**1/4'u**. Yani kapi, tasarim geregi karar veremezdi.

Kararli bir Test 102 icin gereken:
- val tarafinda kol basina >= 500 pozisyon (mevcut korpus 70 veriyor; `test`
  bolumu de acilmadan once §4.4 tek-erisim kurali geregi kayit gerekir),
- egitim tarafinda >= 200 oyun (20 oyunla model ezberliyor, genelleme olculemez).

200 oyun damitma kolu = 200 x 51,7 s = **2,87 h**; kontrol kolu = 6,4 dk.
Bu, §5.1.1 butcesindeki "damitma turu" kaleminin gercek maliyetidir.

## 7. F7-10 tekrarlandi: ONNX disa aktarma sirasi

Ilk denemede iki kolun `model_v1.onnx` dosyalari **bayt bayt ayni** cikti
(SHA-256 `EA33E441B284BA6F...`) ve iki VAL-ER de birebir ayni (0,069857) olctu.
Neden F7-10'da zaten yazili: `ml/train_v2.py` ONNX'i her iterasyonun **basinda**
disa aktarir, cunku o dosya bir sonraki iterasyonun self-play'inde kullanilir.
`--iterations 1` ile yazilan `model_v1.onnx` bu yuzden **egitilmemis** agirliktir.

Bu kez dogru yol - F7-10'un duzeltmesi - kullanildi: `ml/export_ckpt.py` ile
`checkpoints/ckpt_v2.pt` -> `onnx/model_v2_trained.onnx`. Dogrulandi: damitma
`39E0F9ABBE5E252D...`, kontrol `9AD041602A5E4455...` - farkli dosyalar.

**Ders (dorduncu tekrar).** Ayni tuzak (F6-32, F7-04, F7-10, simdi bu) dort kez
goruldu: olcum hattinin hangi dosyayi okudugu **acikca** yazilmadikca sessizce
yanlis sayi uretiliyor. Bu rapordaki tum ER degerleri `*_trained.onnx`
dosyalarindan gelir; `model_vN.onnx` dosyalari **kullanilmadi**.

## 8. Karar

- Test 102 **BASARISIZ** (gucsuz, reddedilmedi).
- Damitma hatti **calisiyor**: shard uretimi, bayrak, hedef, egitim, olcum uctan
  uca dogrulandi.
- Bir sonraki turda (a) >= 200 oyun, (b) >= 500 val pozisyonu ile tekrarlanmali.
- Bu tamamlanana kadar §5.4'un "damitma kazanci" iddiasi **kanitlanmis sayilmaz**
  ve Faz 7'nin sampiyon iddiasi bu kaleme dayandirilamaz.
