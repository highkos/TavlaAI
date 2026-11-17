# Faz 7 Asama A - Olcum hatti onarimi raporu

**Tarih:** 2026-07-17
**Kapsam:** `faz 7.md` Bolum 4.3 (Test 93), 4.5 (Test 124), 4.6, 9.1, 9.9 (Test 122/123), 10.6.
**Moduller:** `ml/measure_integrity.py`, `ml/er_power.py`, `ml/proof_corpus.py`,
`ml/er_harness.py` (genisletme), `ml/equity.py` (float32 aynasi),
`Backgammon.Tests/EquityGoldenData.cs`, `Backgammon.Tests/EquityGoldenTests.cs`.

Faz 6'nin en pahali dersi suydu: **olcum hattinin kendisi dogrulanmadan hicbir
sayi raporlanmaz**. F6-31 (aynalanmis tahta) ve F6-32 (sessiz 0-ply dususu)
aylarca yanlis sayi uretti ve kimse fark etmedi. Asama A bu yuzden **once
olcum hattini** onarir, sonra olcer.

---

## 1. Dort bagimsiz dogrulama probu (Test 93)

`ml/measure_integrity.py` - `ml/artifacts/stage_a_integrity.json`.
Her prob **kalici testtir** (`ml/tests/test_measurement_integrity.py`, 45 test).

| Prob | Ne dogrular | Olculen | Durum |
|---|---|---|---|
| **Tahta** | `board_to_simple` dogru mu | `docBoardEquity` **1,0** (beklenen 1,0) | GECTI |
| | | `signFlippedEquity` 0,479, `mirroredEquity` 0,479 (ikisi de != 1,0) | ayirt edici |
| | | `startPositionId` `4HPwATDgc/ABMA` (bilinen gnubg sabiti) | GECTI |
| | | `startPips` [167, 167], `barPips` [25, 25] | GECTI |
| **Sutun** | `_equity_at` dogru ply sutununu mu okuyor | 10/10 vaka; `maxEvalPlies` 2 | GECTI |
| **Perspektif** | equity **siranin oyuncusunun** bakis acisinda mi | simetrik: 0,068 vs 0,068 (fark 0,0) | GECTI |
| | | asimetrik-00: -0,296 vs 0,626 (carpim -0,185296) | GECTI |
| | | asimetrik-01: -0,266 vs 0,493 (carpim -0,131138) | GECTI |
| **Pip** | `parse_pipcount` dogru mu | 12/12 vaka | GECTI |

**Kritik ayrim.** Ag **antisimetrik degildir** (F6-29): `random-002`'de iki
perspektif -0,296 ve +0,626 verir (toplam 0,33, sifir degil). Bu yuzden
perspektif probu **buyukluk esitligi** degil **isaret tutarliligi** arar.
Simetrik tahtada (baslangic) iki perspektif ayni degeri verir - fark tam 0,0.

**Ayirt edicilik kanitlandi.** `ml/tests/test_measurement_integrity.py` icinde
`monkeypatch` ile `_equity_at` bozulur ve sutun probunun **kirmizi yandigi**
dogrulanir. Yani prob "her zaman yesil" degildir.

---

## 2. Hakem derinligi sozlesmesi (Test 90)

`ml/er_harness.py`: `REFEREE_REPORT_FIELDS`, `referee_contract`, `referee_fields`.

Her ER raporu **hangi komutun**, **hangi sutunun**, **hangi derinligin** ve
**hangi olasilik alaninin** kullanildigini yazmak zorundadir:

| Alan | `eval` | `hint` |
|---|---|---|
| `command` | `"eval"` | `"hint"` |
| `column` | `"static"` (0-ply), `"1"`, `"2"` | `"hint"` |
| `plies` | 0, 1, 2 | 3, 4 |
| `prob` | `"equity"` | `"cubelessEquity"` |

`referee_contract(report)` ihlalleri listeler; `referee_fields(referee, plies)`
alanlari uretir ve gecersiz ciftte `ValueError` firlatir. Sozlesme **capraz
denetimli**: `eval` + `plies = 3` hem "uretemez" hem "sutun yanlis" hatasi verir
(F6-32'nin tam olarak kacirdigi sey). `EVAL_COLUMNS` icinde `"3"` **yoktur** ve
bu bir testtir.

---

## 3. Ortak equity altin dosyasi (Test 122, 123)

`Backgammon.Tests/ReferenceData/equity_golden.json` - 300 kayit, iki dil
**ayni dosyayi** okur.

| Grup | Kayit | Amac |
|---|---|---|
| `unit` | 6 | birim vektorler tam olarak {+1,+2,+3,-1,-2,-3} vermeli |
| `random` | 250 | tohumlu rastgele olasilik vektorleri |
| `boundary` | 20 | 6 saf sinir + 12 bozulmus (1e-6, 0,05) + 2 karisik |
| `unnormalized` | 20 | normalize edilmemis girdi (olcek 0,25 / 7,5 / 100 / 1e-3 / 1e3) |
| `invalid` | 4 | sifir toplam, negatif, NaN, +Inf |

Her kayit `exclusiveHex` (6 x 8 hane float32), `cumulativeHex` (5 x 8 hane
float32), `equityHex` (16 hane float64) tasir. Test **bit duzeyinde** esitlik
arar (`atol = 0`).

**F7-06 - float32 aynasi zorunlu.** C# `OutcomeDistribution` alanlarini `float`
tutar; `ml/equity.py` float64 calisir. Ilk denemede `unnormalized` grubunda
sapma **0,156** cikti. Cozum: `ml/equity.py` icine C# kodunun **birebir float32
aynasi** eklendi (`normalize_exclusive_f32`, `to_cumulative_f32`,
`equity_from_cumulative_f32`, `equity_from_exclusive_f32`, `flip_f32`). Sonuc:

| Karsilastirma | Sonuc |
|---|---|
| 296 gecerli kayit x 5 kumulatif alan, `cumulativeHex` | **0 uyusmazlik** |
| 296 gecerli kayit, `equityHex` | **0 uyusmazlik** |
| 4 gecersiz kayit -> `ValueError` | 4/4 |
| float64 uretim yolu vs float32 aynasi | <= 1e-6 |

**F7-05 - `flip` bit duzeyinde involusyon degildir.** `Flip()` alanlari
`FromProbabilities` ile yeniden kurar; `inv = 1/sum` her alana bir ulp yuvarlama
ekler. Olculen ust sinir **1,3411e-07** (296 kayit), yani backgammon equity
cozunurlugunun (1e-4) **uc mertebe** altinda. Grup 6 testi bu yuzden `1e-6`
tolerans kullanir; `atol = 0` burada yanlis bir iddia olurdu.

`ml/tests/test_stage_b.py::test_53` **duman testine indirgendi**: artik capraz
dil sozlesmesi degil, Python ic tutarlilik testi.

---

## 4. Sigma olcumu ve guc sozlesmesi (Test 124)

`ml/er_power.py` - `ml/artifacts/stage_a_power.json`, `ml/artifacts/er_sigma_log.json`.
Kaynak: `ml/artifacts/stage_h_er_2ply.json` (n = 200, gnubg 2-ply).

| Buyukluk | Deger |
|---|---|
| n | 200 |
| Ortalama (ER) | **0,073970** |
| sigma | **0,109072** |
| sigma %95 GA (bootstrap, 20 000 yeniden orneklem, tohum 20261116) | **[0,092153; 0,124178]** -> **+-%14,7** |
| Standart hata | 0,007713 |
| Ortalama %95 GA (bootstrap) | **[0,059500; 0,089225]** |
| Medyan | 0,0160 |
| Maksimum | 0,4690 |
| Carpiklik | 1,7405 |
| Fazla basiklik | 2,4359 |
| En buyuk 10 kaybin payi | **%27,16** |
| Sifir kayipli pozisyon | 73 / 200 |
| %5 kirpilmis ortalama | 0,059867 |
| %5 winsorized ortalama | 0,068830 |

**Gereken n (yarim genislik 0,005).**

| Kaynak | sigma | n (tek tarafli) |
|---|---|---|
| Nokta tahmini | 0,109072 | **1 288** |
| **Ust %95 sinir (kullanilan)** | **0,124178** | **1 670** |

Belirsizligi yok saymak n'i **%30 eksik** hesaplar. Bu, "GA'yi GA ile hesaplama"
hatasinin ta kendisidir.

**Uc durumlu iddia.** `claim_er_at_most(0,005, 0,0595, 0,0892)` -> **`refuted`**
(GA alt siniri 0,0595 hedefin **ustunde**). Yani bugunku model icin
"ER <= 0,005" iddiasi **yanlislandi** - "kanitlanamadi" degil, **yanlislandi**.

**Sigma kaydi.** `ml/artifacts/er_sigma_log.json` Asama A satiriyla acildi;
12 zorunlu alanin hepsi dolu (`stage`, `model`, `n`, `sigma`, `sigmaCiLow`,
`sigmaCiHigh`, `mean`, `ciLow`, `ciHigh`, `skewness`, `tailShare`, `measuredAt`).
`append_sigma_log` **ekler**, uzerine yazmaz.

---

## 5. Kanit korpusu (Bolum 4.5)

`Backgammon.Tests/ReferenceData/er_proof_corpus_v1.json` - `ml/proof_corpus.py`.

| Alan | Deger |
|---|---|
| Dosya | `Backgammon.Tests/ReferenceData/er_proof_corpus_v1.json` |
| Boyut | **2 000 pozisyon** (1 670'e %20 pay) |
| **SHA-256** | **`17657950ea9cf260115e3689f5fe46be2431e4ec65eb9dd52c1548b65558f828`** |
| Tohum | 20260717 |
| Sema | `schemaVersion = 1` |
| Dosya boyutu | 368 437 bayt |
| Uretim suresi | 19,8 s |

**Tabakalama.** `faz x pip farki kovasi`. Pip kovalari: `0-10`, `10-25`,
`25-50`, `50+` (mutlak fark). 5 faz x 4 kova = **20 kova x 100 pozisyon**.

| Faz | 0-10 | 10-25 | 25-50 | 50+ | Toplam |
|---|---|---|---|---|---|
| `contact` | 100 | 100 | 100 | 100 | 400 |
| `race` | 100 | 100 | 100 | 100 | 400 |
| `bearoff` | 100 | 100 | 100 | 100 | 400 |
| `bar` | 100 | 100 | 100 | 100 | 400 |
| `closed` | 100 | 100 | 100 | 100 | 400 |

`faz 7.md` 4.5 zorunlu tabakayi (temas / yaris / bearoff x pip kovalari, her
kovada >= 100) **karsilar**; `bar` ve `closed` fazlari **ek** olarak kapsanir
(gercek oyunda sik gorulur; disarida birakmak kanit orneginde sistematik bosluk
yaratirdi).

**Dosya bicimi.** Pozisyonlar **afterstate listesi olmadan** yazilir;
afterstate'ler `proof_corpus.materialize_afterstates` ile deterministik olarak
yeniden uretilir. Boylece dosya 368 KB kalir (afterstate listesiyle ~18 MB
olurdu). Her pozisyonda **>= 2 yasal afterstate** vardir (tek adayli pozisyonda
ER tanim geregi 0'dir ve olcume guc katmaz).

**Sizinti korumasi.** Ayni tahta + ayni kapanmis tas sayisi korpusta **tekrar
sayilmaz** (Kural 10). 2 000 pozisyonun 2 000'i benzersizdir.

**Neden ayri korpus.** Dondurulmus 200 pozisyonluk korpus
(`ml/artifacts/reference_corpus_v1.json`, ozet `ad8526...`) **iterasyon**
olcumleri icindir. Ayni veriyle hem ayar hem kanit yapmak sizintidir.

---

## 6. Gecersiz isaretleme mekanizmasi (Bolum 4.6)

`ml/er_power.py`: `invalidate`, `is_invalidated`, `assert_valid`,
`archive_invalidation`, `count_invalidated`, `MeasurementInvalidatedError`.

* Isaret **kardes dosyaya** yazilir (`<ad>.invalidated.json`); orijinal
  **silinmez ve duzenlenmez** - silmek denetim izini yok eder.
* `assert_valid(path)` isaretli dosyayi okumayi **teknik olarak imkansiz** kilar:
  `load_measurement` her okumada once `assert_valid` cagirir.
* `ml/er_harness.py power` gecersiz isaretli dosyada **cikis kodu 2** doner.
* Negatif test yesil: `test_cmd_power_rejects_invalidated_measurement`.

---

## 7. Insan karsilastirma merdiveni (Test 94)

`ml/human_ladder.py` - `ml/artifacts/stage_a_ladder.json` / `.md`.
60 pozisyonluk CAL kumesi, hakem gnubg `hint` **3-ply** (filtre acik).

| # | Referans | Kaynak | n | Kapsama | ER | %95 GA |
|---|---|---|---|---|---|---|
| 0 | gnubg 0-ply | olculur | 60 | %86,7 | **0,0522** | [0,0270; 0,0773] |
| 1 | gnubg 1-ply | olculur | 60 | %80,0 | **0,0530** | [0,0274; 0,0787] |
| 2 | gnubg 2-ply | olculur | 60 | %91,7 | **0,0525** | [0,0264; 0,0785] |
| 3 | gnubg 3-ply | **hakemin kendisi** | 60 | %100 | 0 (tanim) | - |
| 4 | gnubg 4-ply | **olculmedi** | - | - | - | - |
| 5 | dunya sampiyonu insan | **literatur** | - | - | 0,0025 | - |
| 6 | gnubg 4-ply + buyuk ag | **literatur** | - | - | 0,003 | - |

Sure **642,6 s (10,71 s/pozisyon)**, atlanan 0.

**F7-07 - 4-ply olculemedi.** 4-ply `hint` ile ayni kume kosuldugunda 14
pozisyon 2 412,9 s'de bitti (**172 s/pozisyon**) ve 15. pozisyon (`f6-040`)
**900 s** zaman asimina carpti. Bölum 4.2.4'teki 62,57 s/pozisyon tahmini
`closed`/`race` agirlikli 8-20 pozisyonluk bir orneklemden geliyordu ve
`contact` pozisyonlarini temsil etmiyor. 4. basamak **uydurulmadi**:
`source = "unmeasured"` ve gerekce yazildi.

**Beklenmeyen sonuc - merdiven duz.** Bölum 4.4 tablosu 0,10 / 0,08 / 0,05
bekliyordu; olculen **0,0522 / 0,0530 / 0,0525**. Uc derinlik de ayni yerdedir.
Neden: (a) hakem 3-ply, (b) korpus 200 pozisyonluk referans kumesi (kolay
pozisyonlar), (c) kayip birkac pozisyonda yogunlasiyor - butun sig derinlikler
**ayni** hamleyi kaciriyor. Bu, belgenin merdiven beklentisinin **olculmemis bir
varsayim** oldugunu gosterir; sayilar oldugu gibi raporlanir.

**Kapsama.** %80-92 - F7-03'un ongordugu gibi, gnubg'nin secimi 3-ply `hint`
ilk-10 listesinde her zaman yok. Sansurlu pozisyonlar **alt sinirla** raporlanir.

**Durustluk.** 5. ve 6. basamak `source = "literature"` etiketlidir ve
`LITERATURE_NOTE` tasir. `ladder_verdict` **"sampiyon olduk" cumlesi kurmaz**;
sampiyon iddiasi modelin kendi ER'siyle verilir (Bölum 4.4, 4.5). Bu bir testtir.

---

## 8. Asama A kabul durumu (Bolum 10.6)

| Kriter | Durum |
|---|---|
| Test 90-94 yesil | GECTI |
| Test 122-123 yesil (equity altin dosyasi, iki dilde bit duzeyinde) | GECTI |
| Test 124 yesil (guc sozlesmesi) | GECTI |
| Hakem sozlesmesi zorunlu (`methodNote`) | GECTI |
| `hint` 3-ply ve 4-ply veriyor | GECTI |
| Hamle -> afterstate eslemesi 200/200 | GECTI (0 hata) |
| Dort dogrulama probu kalici test | GECTI (45 test) |
| Insan merdiveni 0-4 olculmus, 5-6 literatur etiketli | **KISMI** - 0-3 olculdu, 4 olculemedi (F7-07) |
| Ortak equity altin dosyasi iki dilde bit duzeyinde | GECTI (0 uyusmazlik) |
| sigma olculmus, kanit n'i **ust guven sinirindan** | GECTI (1 670) |
| `er_sigma_log.json` Asama A satiriyla acildi (12 alan) | GECTI |
| `ml/er_power.py` tarama modu calisiyor | GECTI |
| Kanit korpusu uretildi ve SHA-256 donduruldu | GECTI |
| `assert_valid` negatif testi yesil | GECTI |

**Acik kalan.** Test 94'un "0-4 basamak olculur" kosulu **kismen** karsilandi:
0-3 olculdu, 4 olculemedi cunku 4-ply `hint` maliyeti sinirsizdir (F7-07).
4. basamak `source = "unmeasured"` olarak, gerekcesiyle raporlandi - uydurma
sayi uretilmedi. Bu, Asama A'nin bilinen ve belgelenmis siniridir.

---

## 9. Test sayilari

| Paket | Once | Simdi | Fark |
|---|---|---|---|
| `ml/tests` (pytest) | 227 | **550** | +323 |
| `Backgammon.Tests` (C# cekirdek) | 268 | **275** | +7 |

Yeni pytest dosyalari: `test_er_power.py` (47), `test_gnubg_hint.py` (68),
`test_measurement_integrity.py` (45), `test_equity_parity.py` (26),
`test_proof_corpus.py` (45), `test_er_harness_stage_a.py` (55),
`test_human_ladder.py` (37).
Yeni C# testleri: `EquityGoldenTests` (7).
