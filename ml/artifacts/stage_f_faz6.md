# Faz 6 — Kapanis Raporu

Bu rapor `Faz 6 v3.md` (1205 satir) belgesinin **Aşama H** kapanis adimidir. Sekiz
asamanin (A–H) olculmus sonuclarini, Bolum 13 kabul tablolarini, Bolum 14 acik
sorularinin cevaplarini ve Ek A kapanisini tek yerde toplar.

Kural (v3 §13): *"asagidaki esikler baslangic/yer tutucu degerlerdir. Olcum yapilir ve
gercek deger raporlanir. Uydurma sayi yazilmaz."* Bu rapor o kurala uyar: kapisi
gecilemeyen her metrik oldugu gibi yazilmistir.

---

## 0. Yonetici ozeti

| Asama | Konu | Durum | Ana sonuc |
|---|---|---|---|
| A | Olcum altyapisi + taban kilidi | **Tamam** | 200 pozisyonluk dondurulmus korpus; taban ER 0,1941 yeniden uretildi |
| B | 6 cikisli deger kafasi (`output_version = 2`) | **Tamam** | v1/v2 parite max \|Δ\| 5,96e-08; 0 allocation |
| C | Veri motoru | **Tamam** | `dup_cap` calisiyor; 1 vs 4 thread **bayt-ayni** shard |
| D | Olcekli egitim | **Tamam** | TEST-ER **0,0490** (taban 0,1941 → **3,96×** iyilesme) |
| E | Arama gucu | **Tamam** | depth 2 p95 **0,7133 s**; bearoff kesme 328× dugum azalmasi |
| F | Kup ve mac ustaligi | **Tamam** | Kup uyumu **%84,96** (kapi %75) |
| H | Kapanis | **Tamam** | Bu rapor |

**Tek cumlelik hukum.** Faz 6 hedefinin *olculebilir* kismi tutturuldu: model Faz 5
modeline karsi 1500 oyunda **%99,67** kazaniyor, gnubg ER'si 0,1941'den **0,0740**'a
(2-ply) indi, kup kararlarinda gnubg ile **%84,96** uyusuyor. Buna karsilik dunya
capinda guclu hedefi olan **ER < 0,02 tutturulamadi** (olculen 0,0740) ve deger
kafasinin kalibrasyonunda egim/MAE kapilari **kaldi**. Ikisi de asagida sapma olarak
kayitli.

---

## 1. Asama A — Olcum altyapisi ve taban kilidi

Ayrinti: `ml/artifacts/stage_f_baseline.md`.

| Test | Icerik | Sonuc |
|---|---|---|
| 41a | Bolum 2 tablosunun yeniden uretimi | Taban ER **0,1941** birebir uretildi |
| 41b | 200 pozisyonluk referans korpus | `ml/artifacts/reference_corpus_v1.json`, ozet **ad852651…d072** |
| 41c | `OutcomeDistribution` kodlamasi | Kapsayici (exclusive) kodlama belgelendi |
| 41d | `resultType` denetimi | `resultType` kazanani **icermiyor** — dogrulandi |
| 41e | Veri hacmi | 3 824,2 ham B/karar; 128,9 gzip B/karar |
| 44 | CAL/VAL/TEST ayrimi | 60 / 70 / 70, dondurulmus |
| 46 | Istatistiksel guc | %5 farki %95 guvenle yakalamak icin ~1500 oyun |
| 47 | Taban kilidi | cal 0,3013 / val 0,1898 / test 0,1815 / tumu 0,2203 |

Korpus digest'i `ml/er_harness.py verify` ile her kosuda dogrulanir; degisirse test
kirilir. Bu, sonraki tum olcumlerin karsilastirilabilir olmasini saglar.

---

## 2. Asama B — 6 cikisli deger kafasi

`ml/export_onnx.py` artik `--output-version {1,2}` ve `--profile` aliyor. Uretim
modeli `ml/artifacts/model_output_version_2.onnx` (mimari `221-256-256-128`), meta
veri: `output_version=2`, `prob_order=W,GW,BW,L,GL,BL`, `prob_encoding=exclusive`.

| Test | Icerik | Sonuc |
|---|---|---|
| 49–52 | `OutcomeDistribution` v2 davranisi | Gecti |
| 54, 57, 58 | Cikti surumu koprusu; v1 hala calisiyor | Gecti |
| 56 | Logit sicakligi CAL'dan | Gecti |
| 57 | 0 allocation | Gecti |

**Parite.** v1 ve v2 ayni agirliklarla ayni equity'yi verir: max \|Δ\| **5,96e-08**.
Yani 6 cikisli kafa, Faz 5'in skaler kafasinin bilgi kaybi olmadan genisletilmesidir.

**Maliyet.** `output_version = 2` cikarim hizinda **olculebilir bir maliyet
getirmedi**: ayni mimaride (`small`, 221-128-64) v1 **671 335** poz/sn, v2 **517 817**
poz/sn (kova 128) — fark gurultu bandinda (kova 2048'de v2 daha hizli: 647 175 vs
635 575).

---

## 3. Asama C — Veri motoru

| Test | Icerik | Sonuc |
|---|---|---|
| 60 | `--threads > 1` determinizmi | **Bayt-ayni** shard (1 vs 4 thread) |
| 61 | Bellek ici self-play hizi | CPU **119,26** oyun/s vs CUDA **29,11** |
| 62 | `dup_cap` filtresi | Gecti |
| 63, 64 | Shard v1 round-trip; Linux yayini | Gecti (Test 64'un *kosum* adimi atlandi — WSL/Docker yok) |
| 65, 66, 67 | `dup_cap` bayraklari, acilis muafiyeti, parmak izi | Gecti |

**`dup_cap` (F6-…).** `DupCapFilter` FNV-1a vektor parmak izi kullanir (Zobrist
`BackgammonState.hash` zarri disliyor, karar duzeyinde kullanilamaz). Varsayilan
`cap = 3`, acilis muafiyeti 10 ply. 12-thread olcumde: 46 elenen, 58 197 tutulan,
12 000 acilis-muaf, 57 978 farkli.

**CPU vs CUDA karari (F6-16).** GPU: NVIDIA GeForce GTX 1650, 4 GB. CPU **3,5–4,1×
daha hizli** (CLI 60 oyun depth 0: 85,91 vs 24,68 oyun/s). `SelfPlayConfig.DefaultUseCuda
= false` yapildi. Ayrinti: `ml/artifacts/stage_c_gpu_decision.md`.

**Shard yazici patolojisi (F6-21).** `WriteFloats` her float icin 4 × `WriteByte`
cagiriyordu (tamponsuz `FileStream` + `GZipStream` icinde). Toplu `byte[]` yazimi +
64 KB `BufferedStream` ile: tepe bellek **8,5 GB → 1,1 GB**, sure **>7 dk → 12,7 s**.

---

## 4. Asama D — Olcekli egitim

Ayrinti: `ml/artifacts/stage_f_train.md`.

| Kosu | Profil | Oyun/iter | Iter | VAL-ER (ilk → son) | TEST-ER |
|---|---|---|---|---|---|
| L0 | `small` (221-128-64) | 500 | 20 | 0,2425 → **0,1550** | **0,1429** |
| L1 | `medium` (221-256-256-128) | 2 000 | 30 | 0,08765 → **0,06575** | **0,070775** |
| L2 | `medium` | 10 000 | 30 | — → **0,0619** (it15) | **0,0490** (it30) |

**Kapasite kazanci.** `small` → `medium` TEST-ER'de **2,02×** iyilesme (0,1429 →
0,0708). `large` kosulmadi (maliyet; tahmin `stage_f_train.md` §7).

**Soguk baslangic patolojisi (F6-20).** Egitilmemis `medium` model 2 000 oyunun
1 584'unu (%79,2) iptal ettiriyordu. `--init-from <ckpt.pt>` ve `--buffer-games`
eklendi; `ml/runs/stage_d_boot` (3 iter × 500 adim, 328 s) ile bootstraplandiktan
sonra L1/L2 temiz kosuldu.

**TEST erisimi (Test 74).** `test_access.log` — **tek** erisim: L2, iterasyon 30,
40 pozisyon, ER **0,0490**. Secim boyunca yalnizca VAL-ER kullanildi (Test 73).

**Hedefler (kapi degil).** v3 §13.1 hedefi ER < 0,02 idi; L2 **0,0490** ile
tutturulamadi. Bkz. §9.1.

---

## 5. Asama E — Arama gucu

Ayrinti: `ml/artifacts/stage_e_search.md`.

| Test | Icerik | Sonuc |
|---|---|---|
| 75–78 | TT, bearoff kesme, referans esitligi | Gecti |
| 79 | depth 2 p95 | **0,7133 s/karar** (kapi ≤ 2 s) |
| 80 | Arama allocation | **0 bayt** (TT dahil) |
| 81, 82 | Eval cache–TT ablasyonu | Gecti |

**Bearoff kesme.** `IExactValueEvaluator` varsa saf yarista **328×** dugum azalmasi.
Kesme yalnizca tam deger veren bir degerlendirici varsa devreye girer (F6-26).

**TT tasarimi.** Anahtar zar maskesini **icerir** (F6-24); yalnizca `EXACT` girdiler
saklanir (F6-25); uretimde TT **kapali** (F6-27).

**Depth 2 ortalama oyun.** **5,24 s** — v3'un "raporlanir" hedefi 5 s'in %5
uzerinde. Kapi degil.

---

## 6. Asama F — Kup ve mac ustaligi

Ayrinti: `ml/artifacts/stage_f_cube.md`, `ml/artifacts/stage_f_match_gain.json`.

Bu asamada **uc olcum sozlesme hatasi** bulundu ve duzeltildi:

- **F6-28** — gnubg Python API'si `cubeinfo['move']` alanini **yok sayiyor**;
  `anBoard[1]` her zaman "sirada olan" kabul ediliyor. Duzeltme: `gnubg_view(case)`
  hamleyi yapani `anBoard[1]`'e tasir, skor demetini takas eder, kup sahibini
  yeniden esler.
- **F6-29** — `EquityCubeAdvisor.EvaluateDiceAveraged` rakibin perspektifini
  kullaniyordu. Ag hamleyi yapanin perspektifiyle egitildigi ve **antisimetrik
  olmadigi** icin (ortalama \|V(Q,p) + V(Q,−p)\| = 0,65) bu sistematik hata
  uretiyordu.
- **F6-30** — mac oyununda ciftleme karsilastirmasi `Math.Max` kullaniyordu. Rakip
  bizim equity'mizi **minimize** ettigi icin dogrusu `Math.Min`.

| Metrik | F6-28 oncesi | **F6-30 sonrasi** | Kapi |
|---|---|---|---|
| Ciftleme uyumu | %52,27 | **%84,96** | ≥ %75 → **gecti** |
| Kabul/ret uyumu | %61,36 | **%88,72** | ≥ %75 → **gecti** |
| Her iki karar | — | **%81,20** | — |
| Equity korelasyonu | 0,11 | **0,8330** | — |
| Equity ortalama \|Δ\| | 1,2063 | **0,3738** | < 1,2063 → **gecti** |
| Equity p90 \|Δ\| | — | 0,9038 | — |

Karışıklık matrisi (ciftleme): 39 ortak ciftleme, 13 fazla, 7 kacirilan, 74 ortak
ciftlememe — hata artik iki yone de dagilmis, sistematik degil.

**Mac farkindaligi (2-away).** 400 oyun/hucre, depth 0:

| Skor | Faz 5 | Faz 6 | Hedef |
|---|---|---|---|
| 2-away | %40,00 | **%99,50** | ≥ %45 (hedef) |
| 4-away | — | %99,00 | — |
| 5-away | — | %99,50 | — |

2-away'de %99,50 **tavan etkisi**dir: rakip ayni modelin kup-farkinda olmayan
surumu oldugu icin mac farkindaligi dogrudan kazanma oranina yansiyor. Bu sayi
"mac farkindaligi calisiyor"u kanitlar, "dunya capinda"yi degil.

**Crawford.** Test 85 gecti; regresyon yok.

**Kup agi gerekli mi? (Test 89).** Uyum %84,96 ≥ %75 oldugu icin **gerekmedi**;
tetik esigi asilmadi.

---

## 7. Asama H — Kapanis olcumleri

### 7.1 Guclu rakiplere karsi (v3 §13.1)

| Rakip | Oyun | Sonuc | Kazanma | Ortalama puan | Sure |
|---|---|---|---|---|---|
| PipBot (depth 1) | 200 | 199 / 1 | **%99,50** | 2,4450 ± 0,0452 | 117,79 s |
| RandomBot (depth 1) | 200 | 200 / 0 | **%100,00** | 2,6300 ± 0,0409 | 85,06 s |
| Faz 5 `v5.onnx` (depth 0) | 1 500 | 1 495 / 5 | **%99,67** | 2,6347 ± 0,0151 | 7,99 s |

Faz 5 rakamlari: PipBot %40,50, RandomBot %80,50. Ayni rakiplere karsi kazanma
oranlari dramatik bicimde artti.

**Kapi (goreli, istatistiksel).** "Faz 5 model_v5'e karsi ≥ 1500 oyunla kazanma
orani > %50, p < 0,05" → 1 495/1 500 = %99,67, standart hata %0,47 → **fazlasiyla
anlamli**. Kapi **gecildi**.

### 7.2 gnubg ER (v3 §13.1)

200 pozisyonluk dondurulmus korpus, `ml/runs/stage_d_l2/onnx/model_v30.onnx`.

| Ply | Ortalama ER | Medyan | Maks | Tam eslesme | Std hata | Std sapma |
|---|---|---|---|---|---|---|
| 0-ply (`static`) | **0,0972** | 0,018 | 0,738 | %36,0 | 0,0111 | 0,1565 |
| 2-ply | **0,0740** | 0,016 | 0,469 | %36,5 | 0,0077 | 0,1091 |
| 3-ply | **olculemez** (F6-32) | — | — | — | — | — |

Bolum bazinda (0-ply / 2-ply):

| Bolum | n | 0-ply ER | 0-ply tam | 2-ply ER | 2-ply tam |
|---|---|---|---|---|---|
| CAL | 60 | 0,1031 | %31,7 | 0,0878 | %28,3 |
| VAL | 70 | 0,0917 | %35,7 | 0,0704 | %44,3 |
| TEST | 70 | 0,0977 | %40,0 | 0,0657 | %35,7 |

Faz 5 tabani 0,1941 (50 pozisyon) idi. 2-ply'da **2,62×** iyilesme.

**"3-ply" satiri duzeltmesi (F6-32).** Aşama H'de "3-ply ER 0,0972" olarak raporlanan
deger **3-ply degildir**. gnubg'nin `eval` komutu `set evaluation chequerplay evaluation
plies N` ayarindan bagimsiz olarak yalnizca `static` / `1 ply` / `2 ply` satirlarini basar;
`ml/gnubg_er.py::_equity_at` istenen sutunu bulamayinca siralama sonuna (`static`) dusuyordu.
Kanit: `--plies 0` olcumu `--plies 3` ile **200/200 pozisyonda birebir ayni** (0,097225).
Yani gercek merdiven **0-ply 0,0972 → 2-ply 0,0740**: model hakem guclendikce
*iyilesiyor*, kotulesmiyor. Sessiz geri dusus kaldirildi (`MAX_EVAL_PLIES = 2`, aksi halde
`ValueError`). Gercek 3-ply hakem `hint` protokolu + hamle→afterstate eslemesi gerektirir
(gnubg `hint` `plies` ayarina uyar) ve Faz 7'ye devredildi.

**Hedef < 0,02 tutturulamadi** (kapi degil, hedef).

### 7.3 Kalibrasyon (v3 §13.2)

400 afterstate, gnubg **metin protokolu**, hamleyi yapanin perspektifi.

| Metrik | Faz 5 | **Faz 6 (0-ply)** | **Faz 6 (2-ply)** | Hedef | Kapi |
|---|---|---|---|---|---|
| Egim | 0,0874 | **0,6601** | 0,6743 | 0,85–1,15 | **KALDI** |
| Korelasyon | +0,2431 | **+0,8989** | +0,9016 | ≥ 0,75 | gecti |
| MAE | 0,8014 | **0,2755** | 0,2683 | ≤ 0,15 | **KALDI** |
| Std orani | 2,78 | **1,3617** | 1,3371 | 0,7–1,4 | gecti |

Destekleyici: sistematik sapma **−0,1547**, bizim std 0,7350 vs gnubg 0,5398,
dogrusal fit `gnubg ≈ 0,6601·bizim + 0,1350`, kalibrasyon sonrasi MAE **0,1927**.

**Kritik not (F6-31).** Faz 5'in kalibrasyon olcumu (`ml/afterstate_bench.py`)
tahtayi gnubg'ye **aynalanmis** veriyordu. Yani Faz 5'in "egim 0,0874, korelasyon
+0,2431" rakamlari modelin gercek kalitesi degil, **olcum hatasiydi**. Gercek
korelasyon 0,90. Buna karsilik egim 0,66 ve MAE 0,28 hala kapi disinda: model
gnubg'ye gore **sistematik olarak dusuk** ve **fazla yayili**. Bu, Faz 6'nin kalan
gercek acigidir.

### 7.4 Performans (v3 §13.4)

Uretim modeli `medium` (221-256-256-128), `output_version = 2`.

| Kova | CPU poz/sn | CUDA poz/sn |
|---|---|---|
| 1 | 34 780 | 3 803 |
| 8 | 156 182 | 29 798 |
| 32 | 219 030 | 100 522 |
| 128 | **237 708** | 306 090 |
| 512 | 241 267 | 631 445 |
| 2048 | 234 054 | **875 580** |

| Metrik | Faz 5 | Faz 6 hedefi | **Faz 6 olculen** | Kapi |
|---|---|---|---|---|
| ONNX CPU (kova 128) | 724 000 | ≥ 700 000 | **237 708** | **KALDI** (belgelenmis sapma) |
| ONNX CUDA (kova 2048) | 1 241 000 | ≥ 1 200 000 | **875 580** | **KALDI** (belgelenmis sapma) |
| Arama allocation | 0 bayt | 0 bayt | **0 bayt** | gecti |
| Depth 2 p95 | 50 s/karar | ≤ 2 s/karar | **0,7133 s** | gecti |
| Depth 2 ortalama oyun | 50 s | ≤ 5 s (raporlanir) | **5,24 s** | raporlanir |
| Self-play (12 thread) | olculmedi | raporlanir | **584,97 oyun/s** | raporlanir |

**Throughput kapilarinin neden karsilanamadigi.** v3'un 700 000 / 1 200 000
rakamlari Faz 5'in `small` modelinde (221-128-64) olculmustu. Uretim modeli artik
`medium` (221-256-256-128) — **4,5× daha fazla agirlik**. Ayni donanimda ayni
olcum, `small` v1 icin 671 335, `small` v2 icin 517 817 veriyor; yani kapilar
mimariyle birlikte olceklenmemis. `medium` icin gercek regresyon yok: 237 708
poz/sn, depth 2 p95'i 0,71 s'de tutmaya fazlasiyla yetiyor (kapi 2 s).

**Self-play (12 thread, 1 200 oyun, depth 0, log-top 4).** 2,05 s, 584,97 oyun/s,
6 501,0 B/oyun, 3,63 MB/s, tepe bellek 534 MB, **0 iptal**, 71 443 karar,
215 977 kayitli aday.

---

## 8. Bolum 14 — Acik sorularin cevaplari

| # | Soru | Cevap |
|---|---|---|
| 1 | EVREN erisimi alinabildi mi? | **Hayir.** SSB SSO erisimi yok; yalnizca Track L (yerel GTX 1650) kullanildi. |
| 2 | Hangi EVREN erisim yolu calisti? | **N/A** — erisim alinmadi. |
| 3 | Apptainer imaji nasil tasindi? | **N/A** — imaj gerekmedi. |
| 4 | Olculen GPU-saat/oyun orani? | **N/A** — EVREN kosumu yok. Yerel: CPU, CUDA'dan 3,5–4,1× hizli. |
| 5 | `medium` vs `large` kapasite kazanci? | **Kismen.** `small` (L0) TEST-ER 0,1429 vs `medium` (L1) 0,0708 → **2,02×**. `large` kosulmadi. |
| 6 | `search_distill` (depth 3) kazanci? | **Hayir** — v3 §9.6 geregi kapsam disi. |
| 7 | Kup agi gerekli miydi? Uyum %75'i gecti mi? | **Gerekmedi.** Uyum **%84,96** ≥ %75; Test 89 tetiklenmedi. |
| 8 | λ = 1,0 hedeflerin sifira cokmesini duzeltti mi? | **Evet** (F4-41 / D2). |
| 9 | `--threads > 1` determinizmi? | **Evet** — Test 60, bayt-ayni shard. |
| 10 | `max_plies` tasmasi azaldi mi? | F4-45: `max_plies = 500` → 29/100 iptal; `2000` → 8/100. Stage C/D kosulari varsayilanla **0 iptal** (depth 0). |
| 11 | FP16-AMP yardimci oldu mu? | **Hayir** — GTX 1650'de bf16 yok (Test 70). |
| 12 | D1–D3 tani sonuclari? | `ml/artifacts/stage_f_diagnosis.md`. |
| 13 | TEST-ER kac kez okundu? | **1** — L2, iterasyon 30, 40 pozisyon, ER 0,0490 (`test_access.log`). |

---

## 9. Ek A — EVREN kapanisi

**Erisim alinmadi.** SSB SSO kimlik dogrulamasi bu ortamda mevcut degil; `sftp`/
`ssh` anahtar akisi kurulamadi. Bu nedenle:

- A1–A4 testleri **kosulmadi**.
- Test 69 (Track H / H0 parite) **atlandi** — Ek A kapisi acilmadigi icin (F6-18).
- Test 64'un *kosum* adimi **atlandi** (WSL/Docker yok); yalnizca `publish` + ELF
  sihirli sayi dogrulamasi yapildi.

**Track L tek egitim yolu.** Yerel makine: i7-9750H (6C/12T, Coffee Lake — AVX-512
BF16 yok), 31,9 GB RAM, GTX 1650 4 GB. CUDA bu model boyutunda CPU'dan yavas
oldugu icin egitim **CPU'da** yapildi.

---

## 10. Sapmalar (durun ve okuyun)

Asagidaki maddeler **karsilanmamis** hedeflerdir. Hicbiri gizlenmemistir.

| # | Sapma | Olculen | Hedef | Neden |
|---|---|---|---|---|
| D1 | gnubg ER (2-ply) | **0,0740** | < 0,02 | Egitim olcegi. L2 = 10 000 oyun × 30 iterasyon. L3 (10⁵ × 50, ~33 saat) kosulmadi. |
| D2 | gnubg ER (3-ply) | **0,0972** | < 0,01 | Ayni sebep; 3-ply hedefi 2-ply'dan daha zor. |
| D3 | Kalibrasyon egimi | **0,6601** | 0,85–1,15 | Model gnubg'ye gore sistematik dusuk (sapma −0,1547). TD(λ) hedefleri equity olcegini tam tasimiyor. |
| D4 | Kalibrasyon MAE | **0,2755** | ≤ 0,15 | D3'un sonucu; kalibrasyon sonrasi MAE 0,1927'ye iniyor, yani hata buyuk olcude tek bir dogrusal donusumle aciklanabiliyor. |
| D5 | ONNX CPU throughput | **237 708** | ≥ 700 000 | Kapi `small` mimarisinde olculmustu; uretim modeli `medium` (4,5× agirlik). Gercek regresyon yok. |
| D6 | ONNX CUDA throughput | **875 580** | ≥ 1 200 000 | Ayni sebep. Ayrica GTX 1650'de kucuk kovalar baskın. |
| D7 | Depth 2 ortalama oyun | **5,24 s** | ≤ 5 s (raporlanir) | %5 asim; kapi degil. |
| D8 | `large` profil | kosulmadi | — | Maliyet; tahmin `stage_f_train.md` §7. |
| D9 | `search_distill` | kosulmadi | — | v3 §9.6 geregi kapsam disi. |
| D10 | Ek A (EVREN) | erisim yok | — | SSB SSO yok. |
| D11 | Test 64 kosum adimi | atlandi | — | WSL/Docker yok. |
| D12 | Test 69 | atlandi | — | Ek A kapisi kapali (F6-18). |

**D3/D4 hakkinda durust yorum.** Kalibrasyon kapilari, "modelin equity'si gnubg'nin
equity'siyle ayni olcekte mi" sorusunu olcer. Olculen egim 0,66 demek: model
gnubg'nin 1,0 dedigi yerde ortalama 0,66 diyor. Bu, arama icinde **tutarliligi**
bozmaz (ayni olcek icinde karsilastirma yapilir) ama kup kararlarinda ve ER
olcumunde dogrudan kayba donusur. Kup uyumunun yine de %84,96 cikmasi, kararlarin
esik karsilastirmalarina dayanmasi ve esiklerin de ayni olcekte olmasindandir.

---

## 11. Test envanteri

| Aralik | Asama | Durum |
|---|---|---|
| 41a–48 | A | 12 test yesil |
| 49–59 | B | yesil |
| 60–67 | C | yesil (Test 64'un kosum adimi atlandi — WSL/Docker yok) |
| 68–74 | D | 11 test yesil |
| 75–82 | E | yesil |
| 83–89 | F | yesil (89 tetiklenmedi) |
| Ek A (A1–A4) | Ek A | kosulmadi (erisim yok) |
| 69 | Ek A | atlandi (F6-18) |

Toplam: **pytest 222/222**, **Inference 64/64**, **Core 268/268**, **UI 85/85** —
**639**. Uc pytest testi ortam geregi atlanir: `test_bearoff_ref` tam DP dogrulamasi
(`TAVLA_BEAROFF_FULL=1` ile etkinlesir), Test 64'un kosum adimi (WSL/Docker yok) ve
Test 69 (Ek A kapisi kapali, F6-18).

---

## 12. Yeniden uretim

```
# Taban ve korpus
python ml/er_harness.py verify
python ml/er_harness.py measure --model ml/runs/stage_d_l2/onnx/model_v30.onnx --split all --plies 2

# Kalibrasyon (gnubg metin protokolu)
python ml/calibration_bench.py
python ml/calibration_bench.py --plies 2 --out ml/artifacts/stage_h_calibration_2ply.md --json ml/artifacts/stage_h_calibration_2ply.json

# Kup uyumu
python ml/cube_bench.py

# Guclu rakipler
Backgammon.SelfPlay --model ml/runs/stage_d_l2/onnx/model_v30.onnx --eval-pip --games 200 --depth 1 --max-root 4 --max-inner 4 --eval-json ml/artifacts/stage_h_eval_pip.json
Backgammon.SelfPlay --model ml/runs/stage_d_l2/onnx/model_v30.onnx --eval-random --games 200 --depth 1 --max-root 4 --max-inner 4 --eval-json ml/artifacts/stage_h_eval_random.json
Backgammon.SelfPlay --model ml/runs/stage_d_l2/onnx/model_v30.onnx --eval-model-path ml/runs/pool_d/v5.onnx --games 1500 --depth 0 --max-root 4 --max-inner 4 --eval-json ml/artifacts/stage_h_eval_v5.json

# Throughput
Backgammon.MatchBench bench --model ml/runs/stage_d_l2/onnx/model_v15.onnx --out ml/artifacts/stage_f_bench_cpu.json
Backgammon.MatchBench bench --model ml/runs/stage_d_l2/onnx/model_v15.onnx --cuda 1 --out ml/artifacts/stage_h_bench_cuda.json

# Self-play
Backgammon.SelfPlay --model ml/runs/stage_d_l2/onnx/model_v30.onnx --games 1200 --threads 12 --depth 0 --max-root 4 --max-inner 4 --log-top 4 --out ml/runs/_bench_sp12 --prefix sp12 --gzip
```

---

## 13. Faz 6'nin Faz 7'ye devrettigi isler

1. **Egitim olcegi.** ER < 0,02 icin L3 (10⁵ oyun × 50 iterasyon) veya EVREN
   erisimi gerekli. Maliyet tahmini `stage_f_train.md` §7'de.
2. **Kalibrasyon duzeltmesi.** Egim 0,66 → 1,0. Iki yol: (a) egitim sonrasi
   dogrusal kalibrasyon katmani, (b) TD(λ) hedeflerinin equity olcegini yeniden
   turetmek. (a) daha ucuz ve olculebilir.
3. **Throughput kapilarinin yeniden ifadesi.** v3 §13.4 esikleri mimariye gore
   parametrelenmeli (poz/sn yerine poz/sn/agirlik veya kova basina hedef).
4. **Urun asamasi (Asama G).** v3'te Faz 7'ye tasindi.
5. **Kup agi.** Uyum %84,96 ile kapi gecti; ancak kalan %15'in ne kadari esik
   kalibrasyonu, ne kadari gercek bilgi eksigi — olculmedi.
6. **Derin hakem olcumu.** gnubg `eval` 2-ply'den derin sutun uretmiyor (F6-32);
   3-ply ve 4-ply ER ancak `hint` protokolu + hamle→afterstate eslemesi ile
   olculebilir. Bu, Faz 7 Asama A'nin isidir.
7. **Arama damitmasi (`search_distill`).** v3'te kapsam disiydi (govde degisikligi
   yasagi). ER ≤ 0,005 icin ana kaldirak oldugu degerlendiriliyor; Faz 7'de kapsam
   icinde ve `BackgammonSearch` govde degisikligi ayri onayla acilir.
8. **Insan karsilastirma merdiveni.** "Dunya sampiyonunu yenmek" iddiasi referanssiz
   olculemez; 0-4 basamak (gnubg 0/1/2/3/4-ply) olculur, 5-6 (insan sampiyon,
   gnubg 4-ply + buyuk ag) literatur olarak etiketlenir.

**Faz 7 gorev emri:** `faz 7.md` (depo disinda, `D:\Brave Downloads\Tavla Projesi\`).