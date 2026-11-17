# Asama B - kapasite ve veri (Test 95-98)

| Alan | Deger |
|---|---|
| Parite esigi | 1e-06 (F-B3) |
| CPU kova | 128 |
| Karar kurali | goreli kazanc >= 15% **ve** depth 2 p95 <= 2.0 s |

## 1. Profiller (Test 95)

| Profil | Mimari | Parametre | ONNX | Parite max abs | CPU kova 128 (poz/sn) |
|---|---|---|---|---|---|
| `medium` | 221-256-256-128 | 156 423 | 615.5 KB | 5.96e-08 | 347 448 |
| `large` | 221-512-512-512 | 642 567 | 2514.5 KB | 5.96e-08 | 141 875 |

## 2. Karar (Test 96)

| Alan | Deger |
|---|---|
| medium VAL-ER | 0.0640 (SE 0.0119) |
| large VAL-ER | 0.0664 (SE 0.0120) |
| Fark | -0.0024 |
| Goreli kazanc | -3.7% (esik 15%) |
| Gurultu esigi | 0.0025 |
| depth 2 p95 | 13.68 s |
| **Secim** | **medium** |

**Gerekce.** iki bacak da saglanmadi; medium kalir

## 3. Veri kalitesi (Test 97, 98)

| Test | Ne dogrular | Durum |
|---|---|---|
| 97 | Ilk 10 ply'de `dup_cap` muafiyeti korunur | bkz. Backgammon.Inference.Tests/StageBDataQualityTests.cs |
| 98 | Kritik karar agirligi 2x uygulanir, dagilim raporlanir | bkz. ml/critical.py + ml/tests/test_critical.py |

### Kritik karar dagilimi (Test 98)

| Alan | Deger |
|---|---|
| Karar sayisi | 864734 |
| Kritik karar | 224477 (26.0%) |
| Agirlik | 2.0x |
| Etkin orneklem | 771296.1 |
| Equity esigi | 0.50 |
| Marj esigi | 0.050 |

## 4. B1 / B2 / B3 yolu

B1/B2/B3 yol secimi **kullanici onayi** gerektirir (Bolum 5.1.6). Bu rapor yolu secmez; yalnizca `large`'in teknik olarak uygun olup olmadigini olcer. Yol secilmeden `large` ile egitim kosusu baslatilmaz.

---

## 5. Karar gercekligi - iki olcum hatasi duzeltildi

Bolum 1-4 `ml/capacity_bench.py` tarafindan uretilir. Bu bolumden sonrasi elle
yazilmistir ve iki hatanin duzeltilmesini belgeler.

### 5.1 F7-10 - ilk Test 96 kosusu gecersizdi

Ilk kosu (1 000 adim, tek shard) `medium` **0,2631**, `large` **0,2532** verdi ve
"%3,8 kapasite kazanci" diye raporlandi. Bu **yanlisti**: `ml/train_v2.py` ONNX'i
her iterasyonun **basinda** disari aktarir, yani `--iterations 1` kosusunda
`model_v1.onnx` **rastgele baslangic** agirliklaridir. Olculen sey egitilmis model
degildi.

Duzeltme: `ml/export_ckpt.py` (checkpoint -> ONNX). Ayni checkpoint'ten:

| Model | VAL-ER | SE |
|---|---|---|
| `model_v1.onnx` (egitim oncesi) | 0,2631 | 0,0356 |
| `model_v1_trained.onnx` (egitim sonrasi) | **0,0640** | 0,0119 |

Fark **4,1x**. Bolum 2'deki tum sayilar `export_ckpt.py` ile uretilmis
egitilmis modellerden gelir.

### 5.2 Test 96 - nihai kosu

Iki profil, **ayni** 6 shard (`it5, it10, it15, it20, it25, it30`), ayni tohum
(11), ayni adim (3 000), ayni lam (1,0), ayni kritik carpan (2,0), CPU:

| Profil | Parametre | Egitim suresi | VAL-ER | SE |
|---|---|---|---|---|
| `medium` | 156 423 | 679,8 s | **0,0640** | 0,0119 |
| `large` | 642 567 | 1 297,8 s | **0,0664** | 0,0120 |

`large` **%3,7 daha kotu**. Gerekli kazanc **+%15**'ti. Gurultu esigi 0,0025;
gozlenen fark -0,0024, yani esigin **altinda** - istatistiksel olarak "fark yok"
bile denemez, isaret **ters**.

**Yorum.** 3 000 adim, 642 567 parametreli bir agi doyurmaya yetmiyor. `large`
`medium`'un ogrendigi kadarini ogreniyor ama fazladan kapasitesini kullanamadigi
icin yalnizca optimizasyon zorlugu ekliyor. Bu, "daha buyuk ag daha iyi" varsayiminin
**olculmus** reddidir; belge bunu bir varsayim olarak tasimiyordu.

## 6. F7-09 - depth 2, gercek ONNX modeliyle butceyi 10 kat asiyor

Bolum 5.2'nin (b) bacagi `large` icin depth 2 p95 <= 2 s istiyor. Olcum
`Backgammon.MatchBench decision-latency` ile, **gercek ONNX** modeli uzerinde,
30 pozisyon, aday 4/4, TT 2^20:

| Model | Derinlik | p50 | p95 | Ortalama | ONNX cagrisi / karar |
|---|---|---|---|---|---|
| `medium` | 0 | 0,0003 s | 0,0010 s | 0,0004 s | 1 |
| `medium` | 1 | 0,0233 s | 0,0902 s | 0,0328 s | 85 |
| `medium` | **2** | **2,0300 s** | **4,4972 s** | **2,1471 s** | 6 028 |
| `large` | 1 | 0,0718 s | 0,2598 s | 0,0895 s | 85 |
| `large` | **2** | **6,5306 s** | **13,6816 s** | **6,9198 s** | 5 948 |

**Kapilar.** (b) bacagi `large` icin p95 <= 2 s: **13,68 s -> TUTMADI (6,8x)**.
Ama daha onemlisi: **`medium` de tutmuyor** (4,50 s, 2,2x). Yani sorun `large`'a
ozgu degil; **depth 2 aramasinin kendisi** uretim modeliyle butce disidir.

**Kok neden - cagri sayisi, model hizi degil.** Cagri basina maliyet her iki
modelde de ~0,35 ms ve **kova boyutundan bagimsiz**. Maliyet, ONNX cagri
sayisiyla dogrusal:

- depth 1: kok (1 cagri, kova 84) + 84 sans dugumu (kova 21) = **85 cagri**
- depth 2: kok (1) + 84 sans dugumu (kova 84) + 84x84 = 7 056 yaprak sans dugumu
  (kova 21) = **7 141 cagri** (TT/onbellek isabetleriyle 6 028 olculdu)

Yani pahali olan sey 7 056 kucuk ONNX cagrisidir. Arama zaten her dugumde
toplu degerlendiriyor (`EvaluateBatch(list, 0, nonTerminal, ...)`); eksik olan
**kardes sans dugumlerinin birlikte** degerlendirilmesidir. Boyle bir "yaprak
cephe" gecisi depth 2'yi ~72 cagriya indirir (teorik ~0,03 s) ama arama
cekirdeginde gercek bir yeniden yazim gerektirir.

**Faz 6 Test 79 neden 0,7133 s diyordu.** `Backgammon.Tests/Search/SearchPowerTests.cs`
Test 79 `HashEvaluator`/`HashPolicyEvaluator` kullanir - **sentetik**, ONNX degil.
0,7133 s gercek cikarim maliyetini icermiyordu. `ARCHITECTURE.md` §50.4'teki
"Depth 2 p95 0,7133 s -> gecti" satiri bu nedenle **yanlistir** ve duzeltildi.

**Sonuc.** Uretimde kullanilabilir derinlik **depth 1**'dir (p95 0,09 s, butcenin
%4,5'i). Depth 2 ancak yaprak-cephe toplu degerlendirmesi eklenirse butceye girer.

## 7. B1 / B2 / B3 yolu - **B3 ONAYLANDI** (2026-11-17)

Bolum 5.1.6, `large`'a gecis icin uc yol tanimlar ve **kullanici onayi** ister.
**Kullanici B3'u onayladi.** Asagidaki tablo, olculen sonuclarin her yolu nasil
etkiledigini gosterir; ardindan onaylanan alti kalem yazilidir.

| Yol | Kosul | Bu olcumden sonra durum |
|---|---|---|
| **B1 - EVREN kapisi** | Ek A erisimi acilir, ~1 ay | **Gecersiz.** `large`'in kazanci zaten olculdu: -%3,7. Erisim acilsa bile `large`'a gecisin teknik gerekcesi yok. |
| **B2 - Kabul** | Kullanici ~3 aylik takvimi onaylar | **Gecersiz.** 3 aylik takvim `large`'a gecisi varsayiyordu; `large` kazanmiyor. |
| **B3 - Kapsam daraltma** | L4/L5 atlanir, yalnizca L3 + damitma, ~2 ay | **Tek tutarli yol.** `medium` kalir, butce buyumez. ER hedefi <= 0,02'ye duser ve **sampiyon iddiasi duser**. |

**Onaylanan karar.** Olcum B3'u isaret ediyordu: `large` iki bacagi da
kaybettigi icin kapasite artisi **gundemden cikmistir**. B3 onaylandi:

- Butce **1,5 ay** (medium) olarak kalir; 3,2 aylik `large` takvimi **duser**.
- ER hedefi **<= 0,02** olur (sampiyon iddiasi degil, "gnubg 2-ply seviyesine
  yaklasma" iddiasi).
- Kalan kaldirac **veri ve arama**dir, kapasite degil: depth 1 uretim derinligi,
  yaprak-cephe toplu degerlendirmesi (F7-09), kritik karar agirligi (politika
  basligi %26 kritik - calisiyor), `dup_cap` acilis cesitliligi (Test 97).

### 7.1 Onaylanan alti kalem

| # | Karar | Uygulama | Durum |
|---|---|---|---|
| 1 | **`large` dosyasi kapatildi** | `large` uretim adayi degil; egitim kosusu baslatilmaz | kapali |
| 2 | **Depth 2 uretimden cikarildi** | `SearchSettings.ProductionDepthPly = 1`; `SelfPlayConfig.Validate` depth > 1'i reddeder; `MatchBench decision-latency` varsayilani 1 | uygulandi |
| 3 | **Test 98 onarildi** | Deger kafasi `\|equity\|` yerine **karar marji** olcutu; kritik oran %100 -> **%33,3** | uygulandi |
| 4 | **Kalibrasyon onceliklendirildi** | `ml/calibrate.py`; VAL'de egim 0,6447 -> **0,9584**, MAE 0,2641 -> **0,1782** (kapi 0,15 - **hala KALDI**) | olculdu |
| 5 | **Damitma 500 000 karar** | `ml/distill.py`; 500 000 karar = **70,7 saat** (tavan 72); tavan asilirsa hacim **tavana kadar** duser | uygulandi |
| 6 | **ER hedefi <= 0,02** | Bolum 4.4 birinci kosulu (GA ust <= 0,005) **uygulanmaz**; Ek B 1. satiri yazilmaz | yururlukte |

### 7.2 Test 98 onariminin olcumu (F7-08)

| Olcut | Kritik oran | Etkin oran | Degenere? |
|---|---|---|---|
| Eski: `\|equity(y)\| >= 0,5` | **%100,0** | %100,0 | **evet** |
| Yeni: `\|best_equity\| >= 0,5` **ve** `marj <= 0,05` | **%33,3** | %88,9 | hayir |

Olcum 200 oyunluk gercek shard kumesinde (12 264 deger ornegi) yapildi. Marj
dagilimi: p10 0,0000 / p50 0,0373 / p90 0,1917; orneklerin %87,5'inde `q` var.

### 7.3 Kalibrasyon onariminin olcumu (Asama D, oncelikli)

| Metrik | Onarim oncesi (VAL) | Onarim sonrasi (VAL) | Kapi | Sonuc |
|---|---|---|---|---|
| Egim | 0,6447 | **0,9584** | 0,85 - 1,15 | gecti |
| Korelasyon | +0,9022 | +0,9022 | >= 0,75 | gecti |
| MAE | 0,2641 | **0,1782** | <= 0,15 | **KALDI** |
| Std orani | 1,3993 | **0,9414** | 0,7 - 1,4 | gecti |

Affine onarim `hedef ~ 0,6727 * tahmin + 0,1402`, **yalnizca CAL** (200 cift) uzerinde
ogrenildi, **VAL** (200 cift) uzerinde raporlandi. Korelasyon **degismedi** - dogrusal
donusum Pearson korelasyonunu degistirmez. MAE kapi disinda kaldigi icin **post-hoc
onarim yetmiyor**; `L_cal` yeniden egitimi (Asama D) zorunludur.

**Onay olmadan `large` ile hicbir egitim kosusu baslatilmaz.**

## 8. Asama B kabul durumu (Bolum 10.7)

| Kapi | Kriter | Olculen | Durum |
|---|---|---|---|
| F-B1 | `large` VAL-ER kazanci >= %15 | **-%3,7** | **TUTMADI** |
| F-B2 | `large` depth 2 p95 <= 2 s | **13,68 s** | **TUTMADI** |
| F-B3 | `large` export paritesi <= 1e-6 | **5,96e-08** | **GECTI** |
| Test 95 | Profil olcumu + parite | iki profil, parite 5,96e-08 | GECTI |
| Test 96 | Kapasite karari | `medium` kalir | GECTI (karar verildi) |
| Test 97 | Ilk 10 ply `dup_cap` muafiyeti | 9 C# testi yesil | GECTI |
| Test 98 | Kritik karar agirligi | politika %26,0 kritik; deger **dejenere** (F7-08) | **KISMI** |

**Acik kalan.** Test 98'in **deger** yarisi dejenere (F7-08): para oyununda
`|equity| = 1` oldugu icin `|equity| >= 0,5` esigi hicbir seyi ayirmaz. Politika
yarisi calisir. Deger basligi icin dogru olcut **henuz tasarlanmadi**.

## 9. Yeniden uretim

```
python ml/train_v2.py --profile medium --iterations 1 --steps 3000 --no-selfplay \
    --shard-dir ml/runs/stage_b_shards --out ml/runs/stage_b_medium --device cpu \
    --seed 11 --lam 1.0 --critical-boost 2.0 --val-er-every 0 \
    --probe-size 2000 --probe-policy-size 200 --torch-threads 5 --quiet

python ml/export_ckpt.py --ckpt ml/runs/stage_b_medium/checkpoints/ckpt_v1.pt \
    --out ml/runs/stage_b_medium/onnx/model_v1_trained.onnx --version 1

python ml/er_harness.py measure --model ml/runs/stage_b_medium/onnx/model_v1_trained.onnx \
    --split val --plies 2 --json ml/artifacts/stage_b_er_medium.json

dotnet run --project Backgammon.MatchBench -- decision-latency \
    --model ml/runs/stage_b_medium/onnx/model_v1_trained.onnx --depth 2 --positions 30 \
    --out ml/artifacts/stage_b_latency_medium.json

python ml/capacity_bench.py --er-medium 0.0640 --se-medium 0.0119 \
    --er-large 0.0664 --se-large 0.0120 --p95-large 13.6816 \
    --critical-json ml/runs/stage_b_medium/train_report.json \
    --json ml/artifacts/stage_b_capacity.json --markdown ml/artifacts/stage_g_capacity.md
```

`ml/runs/stage_b_shards` alti shard'in kopyasidir (`it5, it10, it15, it20, it25,
it30`); `ml/runs/stage_d_l2/shards` altindan alinmistir.

**UYARI.** Son komut `--markdown ml/artifacts/stage_g_capacity.md` ile bolum 1-4'u
**yeniden yazar** ve bolum 5-9'u **siler**. Bu bolumleri korumak icin once
`--markdown` ile gecici bir dosyaya yaz, sonra elle birlestir.

## 10. Testler

| Dosya | Test | Ne kilitler |
|---|---|---|
| `ml/tests/test_capacity_bench.py` | 48 | profil olcumu, parite, karar kurali, `load_critical_distribution` semasi (F7-11) |
| `ml/tests/test_critical.py` | 56 | kritik maske, agirlik, dejenere tespiti (F7-08) |
| `ml/tests/test_export_ckpt.py` | 12 | checkpoint -> ONNX aktarimi, PyTorch paritesi, hata yollari (F7-10) |
| `Backgammon.Inference.Tests/StageBDataQualityTests.cs` | 9 | Test 97 (`dup_cap` acilis muafiyeti), Test 98 (kritik carpan) |

`test_export_ckpt.py` F7-10'u kilitler: iki farkli checkpoint'ten aktarilan iki
ONNX modeli **farkli** cikti vermek zorundadir; aksi halde aktarim sessizce
rastgele baslangic agirliklarini yaziyor demektir.
