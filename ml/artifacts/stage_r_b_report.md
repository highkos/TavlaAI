# Faz 7-R — Aşama R-B raporu (ölçüm altyapısı)

Tarih: 2026-07-18 · Durum: **tamamlandı, onay bekliyor**

Bu rapor `faz 7 v2.5.md` §8'in istediği 7 maddeyi verir. Aşama R-C'ye
**onay alınmadan geçilmeyecektir** (Kural 10).

---

## 1. Değişen / oluşturulan dosyalar

| Yol | Tür | Ne yapar |
|---|---|---|
| `ml/corpus2.py` | **yeni** | Korpus v2 üreticisi: katmanlı faz seçimi, oyun düzeyinde bölünme, ayna-kanonik sızıntı filtresi, `gameId`/`ply`/`source`, gerçek oyun faz payları, güç tablosu, CLI (`build`/`verify`/`power`) |
| `ml/er_paths.py` | **yeni** | ER'yi üç oynanış yolu (`policy`, `value`, `search1`) için ayrı ölçer; bootstrap %95 GA, faz ve kaynak kırılımı, gerçek oyun frekansıyla ağırlıklı ER, σ üst sınırından güç tablosu, CLI (`measure`) |
| `ml/tests/test_corpus2.py` | **yeni** | Test 127–132 (17 test) |
| `ml/artifacts/reference_corpus_v2.json` | **yeni** | 1000 pozisyon, digest `e0466b9e…` |
| `ml/artifacts/corpus2_records.json` | **yeni** | 43 oyunun ham kayıtları (yeniden üretilebilirlik) |
| `ml/artifacts/er_paths_v1.json` | **yeni** | v1 (dondurulmuş) üç yol ölçümü |
| `ml/artifacts/er_paths_v2.json` | **yeni** | v2 üç yol ölçümü |
| `ml/artifacts/er_paths_v2_val.json` | **yeni** | v2 VAL bölünmesi + kaynak kırılımı |
| `ASSUMPTIONS.md` | değişti | F7-55 … F7-62 |
| `ml/artifacts/reference_corpus_v1.json` | **değişmedi** | Dondurulmuş legacy taban |

---

## 2. R-01 … R-17 kararları

Ayrıntılı kanıt tablosu `ASSUMPTIONS.md` **F7-38**'de. Özet: **16 doğrulandı,
1 kısmen, 0 çürütüldü.**

| # | Karar | Kanıt |
|---|---|---|
| R-01 | doğrulandı | `stage_b_er_medium.json` 0,063957 vs `stage_b_er_large.json` 0,066414; fark **+0,002457** < `noiseThreshold` **0,002535** |
| R-02 | doğrulandı | `gnubg_distill.py:157` hamle-öncesi vektör + zara bağlı etiket |
| R-03 | doğrulandı | `train_value_head` tüm veri kümesi üzerinde `finalMse` |
| R-04 | doğrulandı | `train_policy_head` `cross_entropy` (sert top-1) |
| R-05 | doğrulandı | `DEFAULT_STEPS=2000` sabit; 2k→~256 epoch, 10k→~51 epoch |
| R-06 | doğrulandı | `top1` eğitim kümesi üzerinde |
| R-07 | doğrulandı | `distill_verdict` eşleşmiş testten **önce** `VERDICT_PIPELINE` döner |
| R-08 | doğrulandı + mekanizma | işaretli hedef vs işaretsiz terminal → oran yapısal olarak >1 |
| R-09 | doğrulandı | `STD_RATIO_MIN/MAX = 0,85/1,15` vs `Faz 6 v3.md:389` **0,7–1,4** |
| R-10 | doğrulandı | öğrenme eğrisi kodu yok |
| R-11 | doğrulandı | `ProductionDepthPly = 1`; ER `criterion="policy"` ile ölçülüyordu |
| R-12 | doğrulandı | v1 contact **%19,5**; bölünme faz düzeyinde |
| R-13 | doğrulandı | aynı üretici ailesi; filtre yok |
| R-14 | doğrulandı | VAL n=70; "264" gözlenen etkiden hesaplanmış (Kural 4 ihlali) |
| R-15 | doğrulandı | §4.4 merdiveni tahmin; 4. satır yapısal olarak 0 |
| R-16 | doğrulandı | §4.4 ölçütü **üstünlük** testi; şampiyon iddiası **denklik** ister |
| R-17 | **kısmen** | `HINT_MOVE_CAP=10` doğru; etiketsiz aday maskesi yok — ama etkisi ölçülmedi |

---

## 3. Korpus v2 dağılımı, özet ve sızıntı filtresi

| Alan | Değer |
|---|---|
| Pozisyon | **1000** |
| Faz | contact **600** (%60,0) · bar 250 · race 150 · bearoff 0 · closed 0 |
| Kaynak | gnubg 2-ply self-play **664** · kendi model self-play **286** · rastgele **50** (%5,0) |
| Oyun | 43 |
| Bölünme (oyun düzeyinde) | cal 300 / val 350 / test 350 |
| Sızıntı filtresi | 9 652 eğitim hash'i tarandı → **26 tahta çıkarıldı** |
| Tekrar atılan | 76 |
| Teşhis kümesi (başlık ER'sine girmez) | 1 566 |
| **Digest** | `e0466b9e673dca6cbdd05d8246730deea9371fa9a425055db715e8390e4a97b8` |
| `verify_corpus2` | **ihlal yok** |

Gerçek oyun faz payları **oyunlardan ölçüldü**: contact **0,5564**, bar
**0,3706**, race **0,0730**. Ağırlıklı ER bu payları kullanır.

**Bulunan ve düzeltilen hata:** ilk sürüm bölünmeyi faz içinde yapıyordu; bir
oyun birden çok fazda pozisyon taşıdığı için aynı oyun hem CAL hem TEST'e
düşüyordu (`verify_corpus2` 300+ ihlal). Düzeltme: bölünme tek seferde, oyun
düzeyinde, oyunlar pozisyon sayısına göre büyükten küçüğe yerleştirilerek.

---

## 4. gnubg 2-ply etiketleme maliyeti ve R-D hacimleri

Tek çekirdek, 2-ply `hint`, 6 pozisyon: ortalama **0,562 s** (medyan 0,535,
min 0,282, maks 0,865). 24 pozisyon: 1 süreç **1,803 poz/s**; 4 süreç
**4,696 poz/s** — **2,6×** ölçekleme.

| Pozisyon | Süre (4 süreç, kestirim) |
|---|---|
| 2 000 | ~7 dk |
| 5 000 | ~18 dk |
| 10 000 | ~36 dk |
| 20 000 | ~71 dk |
| 50 000 | ~3,0 sa |

**Bütçe düzeltmesi:** `faz 7.md` §5.1.1'deki "12 iş parçacığında 8× hızlanma"
varsayımı ölçümle desteklenmiyor. Bütçe bu daha düşük sayıyla yeniden
yapılmalıdır.

---

## 5. `model_v30` ER — üç yol, iki korpus

Hakem: gnubg `eval` 2-ply, sütun `2`, alan `equity`. Bootstrap 20 000.

| Korpus | Yol | n | Ortalama | Medyan | %95 GA | σ | σ üst | Ağırlıklı |
|---|---|---|---|---|---|---|---|---|
| **v2** | `policy` | 1000 | **0,0402** | 0,0000 | [0,0350; 0,0457] | 0,0867 | 0,1025 | 0,0434 |
| **v2** | `value` | 1000 | **0,0442** | 0,0000 | [0,0384; 0,0504] | 0,0957 | 0,1130 | 0,0478 |
| **v2** | `search1` | 1000 | **0,0210** | 0,0000 | [0,0181; 0,0240] | 0,0477 | 0,0540 | 0,0221 |
| v1 | `policy` | 200 | 0,0740 | 0,0160 | [0,0594; 0,0893] | 0,1091 | 0,1241 | — |
| v1 | `value` | 200 | 0,0746 | 0,0190 | [0,0594; 0,0909] | 0,1145 | 0,1318 | — |
| v1 | `search1` | 200 | 0,0515 | 0,0000 | [0,0382; 0,0659] | 0,1000 | 0,1180 | — |

**Yeniden üretim kontrolü:** v1 `policy` = **0,0740**, tarihsel
`stage_h_er_2ply.json` değeri **0,073970** ile aynı. Yeni harness eski ölçümü
birebir yeniden üretiyor.

**Faz kırılımı (v2):** `policy` contact 0,0448 / bar 0,0480 / race 0,0086;
`search1` contact 0,0229 / bar 0,0235 / race 0,0091.

**Üretim yolu `search1`** (`ProductionDepthPly = 1`) ve ER **0,0210** — bugüne
kadar raporlanan 0,0533/0,0617'den belirgin biçimde iyi. F7-46'nın nicel
sonucu.

### v1 ↔ v2 (eşleşmemiş, farklı korpus)

| Yol | v1 | v2 | Fark | SE | z | %95 GA | Sıfır dışı |
|---|---|---|---|---|---|---|---|
| `policy` | 0,0740 | 0,0402 | **−0,0338** | 0,0082 | −4,13 | [−0,0498; −0,0178] | **evet** |
| `value` | 0,0746 | 0,0442 | **−0,0304** | 0,0086 | −3,52 | [−0,0473; −0,0135] | **evet** |
| `search1` | 0,0515 | 0,0210 | **−0,0305** | 0,0072 | −4,22 | [−0,0447; −0,0163] | **evet** |

v1 korpusu ER'yi `policy` yolunda **%84 göreli** abartıyordu. **Uyarı:** bu
karşılaştırma eşleşmemiş ve iki korpus farklı faz karışımına sahip; fark,
korpus değişimi ile faz karışımı değişimini ayırmıyor (Kural 7). Ayrıştırma
R-C'ye bırakıldı.

### Kaynak kırılımı — on-policy iyimserlik ölçüldü (v2 VAL, n=350)

| Yol | gnubg2 | self | self/gnubg2 |
|---|---|---|---|
| `policy` | 0,0484 | 0,0433 | 0,90 |
| `value` | 0,0637 | 0,0382 | **0,60** |
| `search1` | 0,0227 | 0,0096 | **0,42** |

`self` kaynağı (modelin kendi oynadığı oyunlar) her yolda daha düşük ER
veriyor; `search1`'de fark **2,4×**. Bu, on-policy dağılımın ER'yi iyimser
gösterdiğinin **doğrudan kanıtıdır** (F7-62). Başlık ER'si bu nedenle bir
**alt sınır** olarak okunmalı; `gnubg2` sütunu daha muhafazakâr referanstır.

### Güç tablosu (σ **üst** sınırından, Kural 4)

| Korpus | Yol | σ üst | n (Δ=0,01) | n (Δ=0,02) | mevcut n | Δ=0,01 yeterli |
|---|---|---|---|---|---|---|
| v2 | `policy` | 0,1025 | **285** | 72 | 1000 | **evet** |
| v2 | `value` | 0,1130 | **346** | 87 | 1000 | **evet** |
| v2 | `search1` | 0,0540 | **79** | 20 | 1000 | **evet** |
| v1 | `policy` | 0,1241 | 418 | 105 | 200 | **hayır** |
| v1 | `value` | 0,1318 | 471 | 118 | 200 | **hayır** |
| v1 | `search1` | 0,1180 | 377 | 95 | 200 | **hayır** |

v1'in 200 pozisyonu Δ=0,01 için **hiçbir yolda yeterli değildi**. R-14'ün
düzeltilmiş hali: doğru sayı **285** (`policy`, Δ=0,01, tek yönlü, σ üst
sınırı) — "264" değil.

---

## 6. R-Q3 ve R-Q4 yanıtları

### R-Q3 — vektörleştirici tutarlı, **model değil**

`gnubg_er.vectorize` ayna tutarlılığı **40/40 doğru**. F6-31 sınıfı hata
**yok**.

Ama modelin değer çıktısı **antisimetrik değil**. Aynı fiziksel tahta iki
perspektiften sorulduğunda `e(+1) = −e(−1)` olmalı:

| Ölçüm | Değer | Beklenen |
|---|---|---|
| `corr(e(+1), e(−1))` | **−0,7019** | −1,0000 |
| ortalama `\|e(+1)+e(−1)\|` | **1,0044** | 0,0000 |
| `\|hata\| < 0,05` | **1/300** | 300/300 |
| politika argmax iki perspektifte aynı | **1/59** | 59/59 |
| başlangıç pozisyonu | −0,0486 / −0,0486 | 0 / 0 |
| simetrik pozisyon | +0,5479 / +0,5479 | 0 / 0 |

**Neden:** eğitim verisi hiçbir zaman aynalanmış tahtayı göstermiyor.
`ml/train_v2.py`'de `flip_exclusive` yalnızca TD(λ) **hedef zincirinde**
kullanılıyor; girdi vektörü için perspektif artırımı **yok**.

**Sonuç:** ER bu asimetriyi zaten içeriyor (ölçüm `perspective=turn`).
Giderilirse ER'nin düşmesi beklenir → R-D'nin girdi artırımı maddesi için
somut gerekçe. Naif düzeltme (logit ortalaması) ER'yi **kötüleştirdi**
(0,0500 → 0,1674); doğru yol eğitimde artırımdır.

### R-Q4 — `random_positions` hamle seçimi

Hamle seçimi `rng.choice(sorted(states))` → yasal afterstate'ler üzerinde
**tekdüze**. Hile yok.

İki ölçülmüş kusur:

1. **Erken ply aşırı temsil.** Her ply'de `p = 0,5` örnekleme. v2'de
   `ply < 5` **%5,7**, `ply < 10` **%14,0**, `ply < 20` **%29,3**,
   `ply < 40` **%58,2**; medyan 34, maks 118.
2. **v1 ↔ damıtma örtüşmesi:** v1'in 200 benzersiz tahtasından **yalnızca 1'i**
   (%0,50) `gnubg_distill.generate_positions(10000, seed=7)` çıktısında.
   R-13 doğru ama etkisi küçük: sızıntı aynı tahtalar değil, aynı **dağılım**
   üzerinden.

---

## 7. Belirsiz / açık noktalar

1. **v2'nin `self` kaynağı on-policy sızıntı taşır.** 1000 pozisyonun 286'sı
   `model_v30`'un kendi oyunlarından. Tahta düzeyinde filtre 26 tanesini
   çıkardı ama dağılım düzeyinde yakınlık kalıyor; ER'yi iyimser gösterebilir.
   Kaynak kırılımı artık `er_paths` çıktısında var; R-C'de raporlanmalı.
2. **v1↔v2 farkı ayrıştırılmadı.** Korpus değişimi ile faz karışımı değişimi
   karışık (Kural 7). Ayrıştırma kolu R-C'ye bırakıldı.
3. **R-17'nin etkisi ölçülmedi.** `HINT_MOVE_CAP=10` nedeniyle etiketsiz
   adayların oranı ve bunun politika kaybına etkisi ölçülmedi; R-D'de
   maskelenmiş pay raporlanmalı.
4. **`search1` gerçek ürün araması değil.** `er_paths.search1` Python'da
   yazılmış 1-ply expectiminimax; C# `BackgammonSearch` ile birebir aynı
   olduğu **kanıtlanmadı**. Ürün ER'si iddiası için C# ile paralellik testi
   gerekir (R-C).
5. **`search1` terminal değerleri basitleştirilmiş.** Mars/backgammon
   hesabı `er_paths.terminal_equity` içinde; C# `IsGameOver` ile (Jacoby,
   küp) birebir eşleşmesi test edilmedi.
6. **Küp yok.** Tüm ölçümler küpsüz (cubeless). R-F küpü ayrı raporlayacak.
7. **`gnubg eval` 2-ply tavanı.** 3/4-ply hakem `hint` yolundan geçer ve
   yöntem değişir (F7-04); bu raporda kullanılmadı.
8. **R-Q1 (GPL) hukuki görüş bekliyor.** Ajan yalnızca durumu raporlar.
9. **R-Q2 (hint 6 olasılık veriyor mu) doğrulanmadı.**
10. **R-Q5 (G7=3,02 hangi λ ve hangi terminal birimi) hâlâ açık.** R-C'de
    kapatılmalı.

---

## Test durumu

`ml/tests/test_corpus2.py` — **17 test yeşil** (Test 127–132).
`ml/tests/test_docs_consistency.py` — **21 test yeşil**.
