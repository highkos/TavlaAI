# Faz 6 — Aşama E: Arama gücü (Test 75–82)

**Tarih:** 2026-11-15
**Kaynak:** `Faz 6 v3.md` §9 (Arama Gücü), §12.5 (Test 75–82), §13.4 (Performans)
**Durum:** ✅ Tamamlandı — 8/8 test yeşil, tüm mevcut testler değişmeden geçiyor.

---

## 1. Ne yapıldı

| # | Değişiklik | Dosya |
|---|---|---|
| 1 | `SearchSettings.TranspositionCapacity` (int, varsayılan **0 = kapalı**) | `Backgammon.Core/Search/SearchSettings.cs` |
| 2 | `SearchSettings.UseBearoffCutoff` (bool, varsayılan **false**) | `Backgammon.Core/Search/SearchSettings.cs` |
| 3 | Transposition table: `_ttKey`/`_ttScore`/`_ttDepth`/`_ttFlag`, doğrudan eşleme, tembel ayırma | `Backgammon.Core/Search/SearchWorkspace.cs` |
| 4 | TT sonda/kesme + bearoff kesmesi | `Backgammon.Core/Search/BackgammonSearch.cs` |
| 5 | `IExactValueEvaluator` (yeni opsiyonel arayüz) | `Backgammon.Core/Search/IEvaluators.cs` |
| 6 | `BearoffAwareEvaluator` → `IExactValueEvaluator` | `Backgammon.Core/Bearoff/BearoffAwareEvaluator.cs` |
| 7 | `SearchResult.TranspositionHits` / `TranspositionStores` | `Backgammon.Core/Search/SearchResult.cs` |
| 8 | Test 75–82 | `Backgammon.Tests/Search/SearchPowerTests.cs` |

**Değişmeyen sözleşmeler:** `SearchSettings.Default` ve `SearchSettings.Reference(depth)` Faz 3
değerlerini birebir korur; yeni iki alan yalnızca **eklenmiştir** (Test 75, Test 81).

---

## 2. Transposition table tasarımı

### 2.1 Anahtar

```
key = s.hash  ^  (depth · 0x9E3779B97F4A7C15)  ^  (diceMask · 0xC2B2AE3D27D4EB4F)
diceMask = fold(remainingCount, remainingDice[0..remainingCount))
```

**Neden zar maskesi?** `Zobrist` tabloları **zar içermez** (`Zobrist.cs`: yalnızca tahta, toplanan
taş, küp değeri, küp sahibi ve sıra anahtarları vardır). Aynı tahtaya farklı **kalan zarlarla**
ulaşan iki düğüm aynı hash'i üretir; zar maskesi olmadan TT **yanlış** değer döndürürdü.

### 2.2 Giriş biçimi

| Alan | Tip | Not |
|---|---|---|
| `key` | `ulong` | yukarıdaki anahtar |
| `score` | `float` | kesin değer |
| `depth` | `byte` | `0..4`; **`0xFF` = boş yuva** |
| `flag` | `byte` | `EXACT=0`, `LOWER=1`, `UPPER=2` |

Kapasite 2'nin kuvveti olmalı (doğrudan eşleme: `slot = key & (capacity-1)`), en fazla 2²⁶.
Çakışmada üzerine yazılır. Dizi `SearchWorkspace` içinde **bir kez** ayrılır (Test 80: 0 bayt).

### 2.3 Yalnızca EXACT kullanılır — bilinçli karar

`LOWER`/`UPPER` bayrakları **biçim olarak** ayrılmıştır ama bu motorda **kesme için kullanılmaz**.
Gerekçe: `ChanceNode` 21 zar üzerinden **ağırlıklı ortalama** alır. Bir sınır değerin ortalamaya
girmesi, ortalamayı da sınır yapar; sınırların yukarı propagasyonu bu motorda güvenli değildir.
Yalnızca tam pencerede ve kesme yapılmadan hesaplanmış değerler saklanır → TT sonucu **değiştirmez**
(Test 78). Ayrıntı: `ASSUMPTIONS.md` F6-24.

### 2.4 Temizleme

`EnsureCacheConsistent` (değerlendirici `Version` veya `SettingsSignature` değişimi) artık TT'yi de
temizler. `SettingsSignature` `MaxCandidatesInner` ve `UsePolicyOrdering` içerir — yani değeri
etkileyen ayarlar değişince TT geçersiz olur. `MaxCandidatesRoot`, `UseAlphaBeta`, `UseStar1`
değeri etkilemez, imzaya girmez.

---

## 3. Bearoff kesmesi

`UseBearoffCutoff = true` **ve** değerlendirici `IExactValueEvaluator` uyguluyor **ve**
`IsExactFor(board)` true ise düğümde derinlik 0'a indirilir.

**Neden sonuç değişmez?** Saf yarışta (temas yok) optimal oyun DB'de çözülmüştür:

```
E(P) = max_m  Σ_r w_r · (−E(P after m, then opponent rolls r))
```

Yani kesin değer, her derinlikteki aramanın sabit noktasıdır. `BearoffAwareEvaluator` yaprakta
kesin equity verdiği için depth 1, depth 2, … hepsi aynı değeri üretir; depth 0'a indirmek
yalnızca **düğüm sayısını** düşürür (Test 77: 3 939 → 12 düğüm, **328×**).

`MatchAwareEvaluator` bu arayüzü **uygulamaz**: `E → ME` dönüşümü tek skaler `E`'nin monoton
fonksiyonu değildir, dolayısıyla kesin bearoff equity'si dönüşümden geçirilemez.

---

## 4. Ölçümler

### 4.1 Test 75 — TT varsayılan olarak kapalı

| Kontrol | Sonuç |
|---|---|
| `SearchSettings.Default.TranspositionCapacity` | **0** |
| `SearchSettings.Default.UseBearoffCutoff` | **false** |
| `SearchSettings.Reference(d)` iki alan | **0 / false** |
| 24 pozisyon, `Default` vs açık `0` | değer ve hamle **birebir aynı** |
| TT isabet / yazma | **0 / 0** |
| `ws.TranspositionCapacity` | **0** (hiç ayrılmadı) |

### 4.2 Test 76 — TT deterministik

20 pozisyon, depth 2, aday 4/4, TT 2¹²:

| Koşul | Sonuç |
|---|---|
| Aynı workspace, 1. tur | referans |
| Aynı workspace, 2. tur (TT dolu) | **birebir aynı** değer + hamle |
| Taze workspace (TT boş) | **birebir aynı** değer + hamle |
| 3. tur TT isabet | **863** |

### 4.3 Test 77 — Bearoff kesmesi düğüm sayısını düşürür

12 saf yarış pozisyonu, depth 1, aday kısıtsız, `BearoffAwareEvaluator`:

| | Düğüm | Değer |
|---|---|---|
| Kesme yok | **3 939** | referans |
| Kesme açık | **12** | **birebir aynı** |

Düğüm azalması **328×**; hamle seçimi de aynı.

### 4.4 Test 78 — Optimizasyonlar `Reference(depth)` ile birebir aynı

16 pozisyon (başlangıç, orta oyun, bar, bitiş, rastgele), depth 2:

| Konfigürasyon | `Reference` karşılaştırması |
|---|---|
| TT 2¹², aday kısıtsız | değer **ve** hamle birebir aynı |
| TT 2¹² + aday 4/4 | `Reference(2)` (aynı 4/4 kısıtıyla) ile birebir aynı |
| Bearoff kesmesi (8 saf yarış) | `Reference(0)` ile birebir aynı |

### 4.5 Test 79 — Depth 2 yeterince hızlı

30 pozisyon (başlangıç/orta oyun/bar/bitiş karışık), depth 2, aday 4/4, TT 2²⁰, ısınma sonrası:

| Metrik | Ölçülen | v3 §9.5 hedefi | Durum |
|---|---|---|---|
| p50 karar süresi | **0,1217 s** | ≤ 0,15 s | ✅ (%81 bütçe) |
| p95 karar süresi | **0,7133 s** | ≤ 2 s | ✅ (%36 bütçe) |
| Ortalama karar | **0,1939 s** | — | rapor |
| Tahmini oyun (27 karar) | **5,24 s** | ≤ 5 s (kapı değil) | ⚠️ %5 aşım |

**Not:** v3 §9.5 ortalama oyun süresini açıkça **kapı değil** ilan eder ("ortalama oyun süresi
raporlanır"). 5,24 s, 5 s'lik raporlama hedefinin %5 üzerindedir; p50/p95 kapıları rahat geçer.

### 4.6 Test 80 — TT açıkken sıfır allocation

200 pozisyon × depth 0/1 + 20 bitiş pozisyonu × depth 2, TT 2¹², ısınma sonrası:

**0 bayt.** TT dizileri ısınmada ayrılır; `EnsureTransposition` kapasite değişmediğinde hiçbir şey
yapmaz.

### 4.7 Test 81 — Faz 3 arama testleri değişmedi

| Kontrol | Sonuç |
|---|---|
| `SearchTests` test sayısı | **39** (değişmedi) |
| `SearchSettings.Default` 9 alan | Faz 3 değerleri birebir |
| `SearchSettings.Reference(0..2)` 11 alan | Faz 3 sözleşmesi birebir |
| Referans eşitliği (8 pozisyon, depth 1) | değer **ve** hamle birebir |

### 4.8 Test 82 — Eval cache / TT ablasyonu

24 pozisyon, depth 2, aday 4/4, **kalıcı workspace** (gerçek kullanım: `SelfPlayAgent` workspace'i
kararlar arasında yaşatır, `Reset()` yalnızca model yeniden yüklenince çağrılır):

| Konfigürasyon | Değerlendirici | Düğüm | TT isabet | Süre | Hızlanma |
|---|---|---|---|---|---|
| cache açık, TT kapalı | 91 203 | 92 392 | 0 | 3,546 s | 1,000× |
| ikisi de açık | 89 876 | 91 065 | 21 | 3,446 s | **1,029×** |
| cache kapalı, TT açık | 93 501 | 94 753 | 84 | 3,534 s | 1,004× |

**Karar (v3 §9.5: "kazanç yoksa sadeleştirilir ve raporlanır"):**

- TT, eval cache'in **üzerine** yalnızca **%2,9** ekliyor.
- Eval cache tek başına, TT tek başına olduğundan **%0,4** daha iyi.
- Sebep: pahalı iş (yaprak değerlendirme + chance düğümü) zaten `UseEvalCache` tarafından
  anahtarlanıyor; tavla'da gerçek transpozisyon (aynı tahta + aynı zar + aynı derinlik) nadirdir.
- **Sonuç:** TT **varsayılan olarak kapalı kalır** ve üretim yollarında (`SelfPlayAgent`,
  `GameOrchestrator`) **açılmaz**. Kod opt-in olarak korunur: §9.3'ün zorunlu teslimatıdır ve
  Test 76/78/80 ona bağlıdır.

---

## 5. Test tablosu

| # | Test | Tür | Durum |
|---|---|---|---|
| 75 | `Transposition_IsDisabledByDefault` | C# | ✅ |
| 76 | `Transposition_IsDeterministic` | C# | ✅ |
| 77 | `BearoffCutoff_ReducesNodes` | C# | ✅ |
| 78 | `Optimizations_MatchReference` | C# | ✅ |
| 79 | `Depth2_IsFastEnough` | C# | ✅ |
| 80 | `Search_ZeroAllocation_WithTT` | C# | ✅ |
| 81 | `Search_ExistingTestsUnchanged` | C# | ✅ |
| 82 | `EvalCache_TT_Ablation` | C# | ✅ |

**Toplam:** 8/8 yeşil. `Backgammon.Tests` 256 → **264**.

---

## 6. Sapmalar ve açık noktalar

| # | Konu | Karar |
|---|---|---|
| E-1 | TT `LOWER`/`UPPER` kesmesi kullanılmıyor | Bilinçli: chance katmanı ağırlıklı ortalaması sınır propagasyonunu güvensiz kılar (F6-24) |
| E-2 | TT ölçülebilir kazanç sağlamıyor (%2,9) | Varsayılan kapalı; üretimde açılmaz; kod opt-in korunur (F6-25) |
| E-3 | Ortalama oyun 5,24 s > 5 s raporlama hedefi | Kapı değil (v3 §9.5); p50/p95 kapıları geçildi |
| E-4 | Depth 3 kapsam dışı | v3 §9.6 gereği; vektör değerli expectiminimax gövde değişikliği gerektirir |
| E-5 | Sezgisel "E > 0,9" erken kesmesi | v3 §9.5 [v3-DÜZELTME] gereği **alınmadı** |

---

## 7. Yeniden üretim

```powershell
# Aşama E testleri (8 test, ~2 dk 40 s)
dotnet test Backgammon.Tests\Backgammon.Tests.csproj -c Release `
  --filter "FullyQualifiedName~SearchPowerTests" --logger "console;verbosity=detailed"

# Tüm çekirdek paketi
dotnet test Backgammon.Tests\Backgammon.Tests.csproj -c Release
```

Ölçüm çıktıları `TestContext.Progress` ile konsola yazılır (`Test 76 | …`, `Test 79 | …` vb.).
