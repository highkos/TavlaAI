# TavlaAI — Faz 1–4 Uçtan Uca Rapor

Bu belge, TavlaAI projesinin **dört fazının tamamını** tek bir yerde, uçtan uca anlatır:
her fazın amacı, teslim edilenler, kritik tasarım kararları, kabul kriterleri, **ölçülmüş**
sonuçlar ve bilinen sınırlar.

| Belge | İçerik |
|---|---|
| **`PHASES.md`** (bu dosya) | Faz 1–4 uçtan uca anlatım, kabul kriterleri, ölçüm özetleri |
| `ARCHITECTURE.md` | Tasarım ayrıntısı (§1–§42) |
| `ASSUMPTIONS.md` | Belirsizlik/karar günlüğü (B/C/D/E, F2, F3, F4-01…F4-54) |
| `SHARD_FORMAT.md` | Self-play shard ikili biçimi v1 |
| `ml/artifacts/stage_c_report.md` | Aşama C kabul raporu (smoke eğitimi) |
| `ml/artifacts/stage_d_report.md` | Aşama D kabul raporu (lig, eval, ayar tablosu, gnubg ER) |

> **Okuma notu:** Bu belgedeki tüm sayılar gerçek koşulardan alınmıştır. Hiçbir ölçüm
> uydurulmamıştır; ölçülemeyen kalemler açıkça "ölçülmedi" olarak işaretlenmiştir.

---

## 0. Yönetici özeti

| Faz | Konu | Durum | Ana ölçüm |
|---|---|---|---|
| 1 | Backgammon motoru (kurallar, küp, maç, hash, fuzz) | ✅ Tamam | `GenerateAllLegalMoves` ~480 000 çağrı/sn, 0 bayt/çağrı |
| 2 | 221 elemanlı durum vektörü | ✅ Tamam | `Vectorize` ~3 650 000 çağrı/sn, 500×221 altın eşleşme |
| 3 | Politika yönlendirmeli expectiminimax arama | ✅ Tamam | Referans eşitliği max \|Δ\| = 0, determinizm birebir |
| 4 | ONNX köprüsü, self-play, eğitim laboratuvarı, lig, değerlendirme | ✅ Tamam | `RandomBot` %80,50 · `PipBot` %40,50 · gnubg ER 0,1941 |

**Toplam test durumu:** 418 test, 0 başarısız (bkz. §6).

**Dürüst değerlendirme:** Faz 4'ün eğitilmiş ağı (`model_v10.onnx`) `RandomBot`'u açık ara
yener, `PipBot` karşısında hafif negatiftir ve gnubg'ye göre hamle kalitesi (ER 0,1941)
**basit `PipBot` sezgiselinden (ER 0,1283) daha kötüdür**. Bu beklenen bir sonuçtur: 10
iterasyon × 100 oyunluk referans koşusu bir **altyapı doğrulamasıdır**, güç hedefi değildir
(bkz. §5.9 ve §7).

---

## 1. Ortak ilkeler (dört fazda da korunan)

1. **Unity-bağımsız motor.** `Backgammon.Core` hiçbir `UnityEngine.*` tipine referans vermez
   (`noEngineReferences: true`). Aynı ikili Unity içinde, CLI'da ve sunucuda çalışır.
2. **Sıfır allocation hot path.** Yasal hamle üretimi, afterstate üretimi, vektörleştirme ve
   ONNX çıkarımı çağrı başına **0 bayt** tahsis eder (ölçülmüş).
3. **Determinizm.** Aynı girdi → aynı çıktı. `Dictionary`/`HashSet`/`object.GetHashCode()`
   hot path'te kullanılmaz; tüm RNG'ler tohumludur (`Xoshiro256StarStar`).
4. **Katman bağımlılığı tek yönlü.** `Core` → `Inference` → `SelfPlay`; `ml/` yalnızca ONNX
   ve shard dosyaları üzerinden konuşur. `Core`, ONNX/PyTorch bilmez.
5. **Uydurma değer yok.** Ölçülemeyen her kalem raporda "ölçülmedi" olarak işaretlenir;
   eşikler ilk ölçümden **sonra** belirlenir.
6. **Bağımsız doğrulama.** Her kritik bileşen, farklı dilde/algortimada yazılmış ikinci bir
   uygulamayla karşılaştırılır (Python referans üreteci, `vector_golden.json`, gnubg).

---

## 2. Faz 1 — Backgammon motoru

**Spesifikasyon:** Tavla Motoru Spesifikasyonu Faz 1 v4 (ek dosya, depoda değil)

### 2.1 Amaç

Tam kural motoru: yasal hamle üretimi, vurma/toplama, bar, küp (double/take/pass), Crawford,
Jacoby, mars/backgammon, Zobrist hash, faz makinesi. Ağ yok, değerlendirme yok — yalnızca
kurallar ve hızlı durum geçişleri.

### 2.2 Teslim edilenler

| Dosya | Sorumluluk |
|---|---|
| `BackgammonState.cs` | Tek gerçek kaynak: `sbyte[26]` board, zar, `borneOff`, `turn`, küp, maç, `phase`, `hash` |
| `MoveStep.cs` / `MoveSequence.cs` | Değer tipleri (`MaxSteps = 4`) |
| `MoveList.cs` | Önceden ayrılmış çıktı buffer'ı (kapasite 2048) |
| `AfterStateList.cs` | SoA: `Boards`, `WhiteBorneOff`, `BlackBorneOff`, `Hash`, `Sequences`, `IsTerminal`, `ResultType`, `ResultPoints` |
| `LegalMoveGenerator.cs` | Tek geçişli DFS + hash tekilleştirme |
| `BackgammonEngine.cs` | `ApplyStep`/`UndoStep`, `ApplyMove`/`UndoMove`, `SetDice`, `EndTurn`, `PassTurn`, `LoadAfterState`, `IsGameOver`, `StartNextGame`, `MirrorTo`, `CopyFrom`, `ComputeZobristHash` |
| `Zobrist.cs` | Düz `ulong[]` tablolar, SplitMix64, sabit tohum |
| `Xoshiro256StarStar.cs` / `CryptoRandom.cs` | Deterministik / kriptografik RNG |
| `StatePool.cs` | `BackgammonState` geri dönüşümü (thread-safe değil) |
| `EngineSettings.cs`, `Enums.cs`, `GameResult.cs` | Yapılandırma ve sonuç tipleri |
| `tools/reference_gen.py` | Bağımsız Python referans üreteci |

### 2.3 Kritik tasarım kararları

* **`sbyte[26]` board.** `[0]` = Beyaz bar (≥0), `[1..24]` = haneler, `[25]` = Siyah bar (≤0).
  Bir hanede en fazla 15 taş → `[-15, +15]` `sbyte`'a sığar. 26 bayt tek cache satırı.
* **Kopyalamasız DFS.** `ApplyStep` → özyineleme → `UndoStep`. State hiç kopyalanmaz.
* **Tek geçişli üretim.** En uzun diziler `[ThreadStatic]` buffer'da toplanır; daha derin bir
  dizi bulunursa buffer sıfırlanır. Buffer taşarsa (65 536 kayıt) davranış birebir aynı kalan
  iki geçişli yola düşülür (E-02).
* **Nesil sayaçlı tekilleştirme tablosu.** Her çağrıda `Array.Clear` yok; `_gen` artırılır.
* **`ResultPoints` mars çarpanıdır (1/2/3), `cubeValue` hariç.** Küp çarpımı çağıranın işi.
  Bu değişmez Faz 3'ün `Points / cubeValue` kuralını da tutarlı kılar (D-01).
* **`cubePassed` hash'e girmez.** Pozisyonun parçası değil, akış bilgisidir (D-03).
* **`IsBearOffMode` her `GenerateSteps` çağrısında yeniden hesaplanır** — toplama modu bir
  hamle içinde açılıp kapanabilir (C-05).
* **`Debug.Assert` yerine fırlatan yardımcı.** `[Conditional("DEBUG")]` `DebugAssert`;
  ihlalde `InvalidOperationException`. Release'te çağrı tamamen kaldırılır (B-09).

### 2.4 Kabul kriterleri

| Gereksinim | Durum | Kanıt |
|---|---|---|
| `SetDice`: RNG'siz, `phase = Moving`, dublede 4 zar, sıralı | ✅ | `EngineFlowTests` |
| `AfterStateList` (SoA) tüm alanlar + `Swap` + `AddPass` | ✅ | `AfterStateListTests` |
| `GenerateAfterStates` = `GenerateAllLegalMoves` (aynı küme **ve** sıra) | ✅ | `AfterStateListTests` |
| Afterstate hash'i `turn` + küp içerir, zar içermez | ✅ | `ZobristTests` |
| `IsGameOver` Jacoby uyumlu, `Points` `cubeValue` hariç | ✅ | `CubeAndMatchTests` |
| `state.hash == ComputeZobristHash(state)` her mutasyondan sonra | ✅ | `SanityCheck` madde 7 |
| Bağımsız referans ile 57 pozisyon / 927 sonuç pozisyonu | ✅ | `ReferenceComparisonTests` |
| Fuzz: 1 000 000 oyun, 0 hata | ✅ | `Fuzz_OneMillionGames` (`[Explicit]`) |
| Steady-state 0 bayt/çağrı | ✅ | `PerformanceTests` |
| ≥ 300 000 çağrı/sn (hamle üretimi) | ✅ | ~480 000 |

### 2.5 Ölçülen performans (Release, tek çekirdek)

| Ölçüm | Hedef | Ölçülen |
|---|---|---|
| `GenerateAllLegalMoves` (orta oyun, 21 hamle) | ≥ 300 000 çağrı/sn | **~480 000 çağrı/sn** (≈ 2,1 µs) |
| `GenerateAfterStates` (orta oyun, 21 afterstate) | ≥ 300 000 çağrı/sn | **~340 000 çağrı/sn** (≈ 2,9 µs) |
| Rastgele oyun hızı | ≥ 5 000 oyun/sn/çekirdek → **revize 1 000** | **~1 700 oyun/sn/çekirdek** |
| Rastgele oyun hızı (12 thread) | — | **~9 200 oyun/sn** toplam |
| Steady-state allocation | 0 bayt | **0 bayt** / 50 000 çağrı |

**Hedef revizyonu (E-03):** 5 000 oyun/sn ≈ 2 µs/tur demektir; tek başına yasal hamle üretimi
~2 µs sürdüğü için mevcut mimaride ulaşılabilir değildir. Regresyon koruması 1 000
oyun/sn/çekirdek olarak sabitlendi; ölçülen değer raporlanıyor.

### 2.6 Fuzz (tam ölçek koşusu)

`TAVLA_FUZZ_GAMES=1000000` ile: **1 000 000 oyun, 96 761 627 tur, 208 317 127 adım,
1 803 177 934 afterstate**, en uzun oyun 478 tur, süre 1 sa 2 dk, **0 hata**. Her turda
`GenerateAllLegalMoves`/`GenerateAfterStates` sayı-sıra eşitliği, afterstate hash tekilliği,
`ApplyMove`→`UndoMove` özdeşliği ve `SanityCheck` doğrulandı.

### 2.7 Bilinen sınırlar

* **gnubg referans verisi (E-01).** Bölüm 8 madde 5 gnubg çıktısından referans veri ister.
  Faz 1 sırasında gnubg kurulu değildi; bunun yerine **bağımsız Python uygulaması**
  (`tools/reference_gen.py`) ile 57 pozisyon üretildi. Bu, uygulama hatası sınıfını yakalar
  ama gnubg ile karşılaştırmanın yerini tam tutmaz. **Faz 4'te gnubg kuruldu** ve gerçek
  gnubg ER ölçümü yapıldı (bkz. §5.8) — ancak bu, hamle üretimi referansı değil, **hamle
  kalitesi** ölçümüdür.
* **`AfterStateList.DefaultCapacity = 2048`.** 4 zarlı pozisyonlarda teorik üst sınır
  ölçülmedi; kapasite aşılırsa `InvalidOperationException` atar (sessiz taşma yok).

---

## 3. Faz 2 — Durum vektörleştirici (221 nöron)

**Spesifikasyon:** Tavla Durum Vektörü Spesifikasyonu Faz 2 v4 (ek dosya, depoda değil)

### 3.1 Amaç

`BackgammonState`'i sinir ağının girdisi olan **221 elemanlı `float32` vektöre** çevirmek —
sıfır allocation, bit-düzeyinde deterministik, C# ve Python'da **birebir aynı**.

### 3.2 Vektör haritası

| Aralık | İçerik |
|---|---|
| `0..95` | Aktif oyuncunun 24 hanesi × 4 nöron |
| `96..191` | Rakibin 24 hanesi × 4 nöron |
| `192` / `193` | Aktif / rakip bar (`n / 2`) |
| `194` / `195` | Aktif / rakip toplanan (`n / 15`) |
| `196` | Küp sahibi × perspektif |
| `197` | Küp değeri: `min(log2(v) / 6, 1)`, `v ≤ 1` ise 0 |
| `198` | Money game bayrağı |
| `199` | Crawford bayrağı |
| `200` / `201` | Aktif / rakip pip (`pip / 167`) |
| `202` / `203` | Aktif / rakip kaçmış taş (`n / 15`) |
| `204` | Temas bayrağı |
| `205..212` | Aktif oyuncunun "kalan puan" one-hot (8 kova) |
| `213..220` | Rakibin "kalan puan" one-hot (8 kova) |

**Hane bloğu (4 nöron):** `[n == 1, n >= 2, n >= 3, n > 3 ? (n-3)/2 : 0]`.

### 3.3 Teslim edilenler

| Dosya | Sorumluluk |
|---|---|
| `VectorLayout.cs` | Tüm offset'ler ve `VectorSize = 221` (tek doğruluk kaynağı) |
| `VectorizerScalars.cs` | `readonly struct`: `CubeValue`, `CubeOwner`, `MatchLength`, `WhiteScore`, `BlackScore`, `IsCrawfordGame` |
| `BackgammonVectorizer.cs` | `Vectorize`, `VectorizeBatch`, yardımcı fonksiyonlar |
| `Backgammon.Tests/ReferenceData/vector_golden.json` | 500 kayıt × 221 nöron altın veri |
| `tools/vector_verify.py` | Bağımsız Python/numpy `float32` doğrulayıcı |

### 3.4 Kritik tasarım kararları

* **`VectorizerScalars` yalnızca board'da olmayan bilgiyi taşır** (F2-01). `borneOff` çifti
  bilinçli olarak dışarıda — hem ayrı parametre hem struct alanı tekrar olurdu.
* **`VectorizeBatch` terminal kayıt reddeder** (`ArgumentException`). Arama, terminal
  adayları listenin başına taşımak **zorundadır** (Faz 3'te kod düzeyinde zorlanır).
* **`FeatureVersion` artırılmadan vektör düzeni değiştirilemez**; altın dosya da yeniden
  üretilmelidir.
* **`escapedCount` tuzağı.** Rakibin tahtada taşı yoksa `_oppMinJ` **`_INF`** döndürmelidir;
  `None` döndürmek Python portunda 25/500 uyuşmazlığa yol açtı (F4-54'te belgelendi).

### 3.5 Kabul kriterleri

| Gereksinim | Durum | Kanıt |
|---|---|---|
| 221 nöron, offset'ler `VectorLayout` ile birebir | ✅ | `VectorizerTests` |
| C# ↔ Python bit-düzeyi eşitlik (500 × 221) | ✅ | `CrossLanguageGolden_FileMatches` + `tools/vector_verify.py` |
| Terminal/maç-bitişi reddi | ✅ | `VectorizerTests` |
| Steady-state 0 bayt/çağrı (3 API) | ✅ | `PerformanceTests` |
| ≥ 2 000 000 `Vectorize`/sn | ✅ | ~3 650 000 |

### 3.6 Ölçülen performans (Release, tek çekirdek)

| Ölçüm | Hedef | Ölçülen |
|---|---|---|
| `Vectorize` (state) | ≥ 2 000 000 çağrı/sn | **~3 650 000 çağrı/sn** (≈ 0,27 µs) |
| `VectorizeBatch` | raporla | **~3 100 000 kayıt/sn** |
| Steady-state allocation | 0 bayt | **0 bayt** / 10 000 çağrı (3 API) |

Çağrı başına iş yükü çok küçük olduğu için `PerformanceTests` iki testte **en iyi 3 turun**
hızını ölçer (`MeasureBestOf`, F2-20).

### 3.7 Bilinen sınırlar

* Vektör **money game / küpsüz / Jacoby kapalı** varsayımıyla tasarlandı; küp ve maç bilgisi
  yalnızca 4 skaler nöronla temsil edilir. Küp kararları (double/take) için ayrı bir ağ
  gerekir — kapsam dışı (F4-01).
* "Kalan puan" one-hot 8 kovada doyuma ulaşır (`away >= 8` aynı kovaya düşer).

---

## 4. Faz 3 — Politika yönlendirmeli expectiminimax arama

**Spesifikasyon:** Faz 3 v7 (ek dosya, depoda değil)

### 4.1 Amaç

Faz 1 motoru ve Faz 2 vektörü üzerine, **değerlendirici-agnostik** bir arama motoru: kök
aday üretimi, politika sıralaması, alfa-beta + Star1 budaması, eval cache, kök politika
hedefi (Faz 4 eğitimi için). Ağ yok — yalnızca arayüzler.

### 4.2 Teslim edilenler

`Backgammon.Core/Search/` altında, Faz 1 ve Faz 2'ye **hiç dokunmadan**:

| Dosya | Sorumluluk |
|---|---|
| `IEvaluators.cs` | `IPositionEvaluator`, `IPolicyEvaluator`, `IPolicyValueEvaluator`, `ICombinedBatchEvaluator`, `ICubeEvaluator`/`NullCubeEvaluator`, `ICubePolicyEvaluator`/`NullCubePolicyEvaluator` |
| `RollSet.cs` | 21'lik normal zar kümesi (ağırlık 36) + 15'lik açılış kümesi; `RemainingWeightAfter` |
| `SearchSettings.cs` | `DepthPly`, aday kısıtları, budama/cache/politika anahtarları, `PolicyTemperature` |
| `SearchResult.cs` | `RootCandidate` (salt-okunur struct) + `ref struct SearchResult` |
| `SearchWorkspace.cs` | Ply başına önceden ayrılmış tamponlar + doğrudan eşlemeli eval cache |
| `BackgammonSearch.cs` | `Search`, `AnalyzePreRoll`, `SearchNode`, `ChanceNode` |

### 4.3 Kritik tasarım kararları

* **Değer sözleşmesi.** Küpsüz para equity'si, `[L, U] = [-3, +3]`, **hamleyi yapanın**
  gözünden; çocuk değeri `-v` olarak döner (negamax).
* **Kırpma sahipliği.** Değerlendirici **kırpmaz** (yalnızca `IsFinite`); kırpma **aramanın**
  işidir (`ClampInPlace`). Bu, `ReferenceSearch` ile gerçek aramanın aynı sayıda kırpma
  uygulamasını garanti eder (F3-03).
* **Ply semantiği.** `depthPly` = **chance (zar) katmanı** sayısı. `0` = afterstate'ler
  doğrudan değerlendirilir; `1` = her aday için rakibin 21 zarı üzerinden ağırlıklı ortalama.
  `node = 2·(DepthPly − d)`, `MaxSupportedPly = 4` → `MaxNodes = 10`.
* **`SearchResult` `ref struct`'tır** (F3-01): span alanları taşır, sıfır allocation korunur,
  ama bir alanda saklanamaz. Faz 4 sonucu hemen tüketmelidir.
* **`ICombinedBatchEvaluator` `IPositionEvaluator`'dan türetilmez** (F3-02). Çağrı noktaları
  sabittir: kökte `EvaluateAndScoreBatch` (yalnızca `MaxCandidatesRoot > 0`), yapraklarda
  `EvaluateBatch`, iç max düğümlerinde `ScoreBatch`. Tip kontrolü arama başında **bir kez**.
* **Terminal bölümleme zorunlu.** `PartitionNonTerminal` kararlı `Swap` ile
  terminal-olmayanları başa taşır; `VectorizeBatch` terminal kayıt görünce istisna atar.
* **`Kind` semantiği.** `0` = terminal, `1` = arandı, `2` = kısıt nedeniyle aranmadı
  (`best` karşılaştırmasına girmez, politika hedefi 0).
* **Cache anahtarı** = afterstate Zobrist hash'i `^ depth` (+ ayar imzası). Yalnızca **kesin**
  `Q` yazılır; budanmış sınır değerleri asla. Politika `Version`'ı cache'i temizlemez.
* **`BeginSearch()` vs `Reset()`.** `BeginSearch` istatistikleri ve kök tamponlarını sıfırlar,
  cache'i **korur**. `Reset()` cache'i **kesinlikle** temizler (model yeniden yükleme sonrası
  zorunlu — Test 17).

### 4.4 Budama

**Alfa-beta (fail-soft).** Her aday `(max(best, α), β)` penceresiyle aranır; `best >= β` olunca
döngü kırılır. Kökte erken kesme yapılmaz (`RootCandidates` tüm adaylar için dolu kalmalı).
`ExactRootScores = true` iken kökte her aday `(L, U)` ile aranır — politika hedefi için
**kesin** `Q` gerekir.

**Star1 (chance düğümü budaması).** `q_r ∈ [L, U]` olduğu için kalan zarların katkısı
`[R·L, R·U]` aralığındadır:

```
A = (36α − S − R·U) / w        B = (36β − S − R·L) / w
A >= U  →  (S + (w+R)·U) / 36
B <= L  →  (S + (w+R)·L) / 36
α_c = −min(B, U)               β_c = −max(A, L)
q <= A  →  (S + w·q + R·U) / 36
q >= B  →  (S + w·q + R·L) / 36
```

### 4.5 Kabul kriterleri (Faz 3 v7 testleri)

| Test | Kriter | Sonuç |
|---|---|---|
| 1 | `ReferenceSearch` ile referans eşitliği (6 pozisyon × derinlik 0/1) | **max \|Δ\| = 0** |
| 4 | `RollSet` ağırlıkları (21 zar, toplam 36) | ✅ |
| 8 | Determinizm (tekrarlı arama, farklı thread, farklı workspace) | birebir aynı |
| 8e | Politika `Version`'ı cache'i temizlemez | ✅ |
| 10 | Arama sırasında 0 bayt allocation | ✅ |
| 12 | `EvaluateAndScoreBatch` = ayrı çağrılar | birebir aynı |
| 13a | Pas durumunda `RootPolicyTarget` boş | ✅ |
| 16 | `ICombinedBatchEvaluator` kökte (`MaxCandidatesRoot = 4`) | politika hedefi toplamı 1 |
| 16f | `ICombinedBatchEvaluator` `IPositionEvaluator`'dan türetilmez | ✅ |
| 17 | `SetModel` → `Version` artışı → `Reset()` cache temizliği | ✅ |

### 4.6 Bilinen sınırlar

* **Küp kararı yok.** `ICubeEvaluator`/`ICubePolicyEvaluator` arayüzleri tanımlı ama
  `NullCubeEvaluator` dışında uygulama yok — küp oyunu kapsam dışı (F4-01).
* **`MaxSupportedPly = 4`.** Daha derin arama `SearchWorkspace` tamponlarını aşar.
* **`AfterStateList.DefaultCapacity = 2048`** (F3-06). 4 zarlı pozisyonlarda teorik üst sınır
  ölçülmedi; aşılırsa istisna atar.

---

## 5. Faz 4 — Sinir ağı, ONNX köprüsü, self-play ve eğitim laboratuvarı

**Spesifikasyon:** Faz 4 v3 (ek dosya, depoda değil)

### 5.1 Amaç

Faz 3 aramasını gerçek bir sinir ağıyla beslemek, kendi kendine oyun verisi üretmek, eğitmek,
lig/model havuzuyla ilerlemeyi ölçmek ve hamle kalitesini gnubg'ye karşı doğrulamak.

### 5.2 Katman haritası

```
ml/  (Python, PyTorch)
  model.py  export_onnx.py  shards.py  td_lambda.py  losses.py
  replay.py  train.py  league.py  eval_bench.py  settings_bench.py  gnubg_er.py
		│  model_vN.onnx + metadata + parity.json
		▼
Backgammon.Inference  (netstandard2.1, ORT 1.23.2)
  OnnxEvaluatorOptions  OnnxModelHandle  OnnxPolicyValueEvaluator
		│  IPositionEvaluator + IPolicyEvaluator + ICombinedBatchEvaluator
		▼
Backgammon.Core  (Faz 1–3)
  BackgammonSearch  SearchWorkspace  BackgammonVectorizer
		│
		▼
Backgammon.SelfPlay  (net10.0 Exe)
  ShardFormat  ShardModel  ShardWriter  ShardReader  EvalBench  Program
		│  *.bgsp / *.bgsp.gz
		▼
ml/shards.py  →  replay.py  →  train.py
```

### 5.3 Ağ mimarisi ve ONNX sözleşmesi

* Gövde: `Linear(221,128) → GELU → Linear(128,64) → GELU`.
* `value_head = Linear(64,1)` — **bias sıfır, lineer** (kırpma yok).
* `policy_head = Linear(64,1)` — aday başına **tek logit**; **ağ içinde softmax yok**.
* Girdi `features` `[B,221]` float32; çıktılar `value` `[B,1]`, `policy_logit` `[B,1]`.
* **Batch ekseni üç tensörde de dinamik olmak zorundadır.** `opset_version = 15`.
* Metadata: `feature_version`, `vector_size`, `model_version`, `arch`, `trained_by`.

**Grup softmax iki yerde uygulanır ve aynı sonucu vermelidir:**
`OnnxPolicyValueEvaluator.ScoreBatch` (C#) ve `ml/losses.py` (Python).
`ml/tests/test_tau_crosscheck.py` bunu aynı `Q`/`τ` üzerinde karşılaştırır.

### 5.4 Kova (bucket) mekanizması

* Kovalar `1, 2, 4, 8, …, MaxBatch` (`MaxBatch = 2048`).
* Girdi tamponu kovaya göre **sıfırla doldurulur**; ORT'a kova boyutu bildirilir; yalnızca
  ilk `count` satır kullanılır. Satırlar bağımsız olduğu için sıfır dolgu çıktıyı etkilemez.
* `OrtValue.CreateTensorValueFromMemory` + `OrtIoBinding`; binding'ler ve tamponlar
  **kurucuda bir kez** ayrılır.
* **Ölçüm: tüm kovalarda 0 bayt/çağrı.** Varsayılan `session.Run(NamedOnnxValue)` yolu
  1 401–1 472 bayt/çağrı tahsis eder.
* Sabit maliyet ~12 µs; 2048 kovada ~1,83 ms (≈ 547 çağrı/s).

**CUDA tuzağı (F4-35).** `OrtIoBinding.BindInput`, girdi CPU belleğindeyken ve oturum CUDA
iken **CPU→cihaz kopyasını bind anında** yapar; `SynchronizeBoundInputs()` bunu tekrarlamaz.
Bu yüzden yapıcıda bir kez bağlanan girdi, sonradan doldurulduğunda cihaz **sıfır** görür
(belirti: çıktı tam olarak `model(0)` değerine eşit). Çözüm: CUDA oturumlarında girdi her
çağrıda `ClearBoundInputs()` + `BindInput()` ile yeniden bağlanır. CPU EP'de atlanır.

### 5.5 CPU vs CUDA (gerçek GPU ölçümü)

Makine: `DESKTOP-2T0QNN5`, 12 mantıksal çekirdek, **NVIDIA GeForce GTX 1650 (4 GB, sürücü
580.88)**, ORT 1.23.2, `IntraOpThreads = 1`, `InterOpThreads = 1`, `use_tf32 = 0`.

| Kova | CPU µs | CPU poz/s | CUDA µs | CUDA poz/s | Kazanan |
|---|---|---|---|---|---|
| 1 | 13,79 | 72 516 | 194,62 | 5 138 | CPU (14×) |
| 8 | 20,03 | 399 421 | 185,67 | 43 088 | CPU (9×) |
| 32 | 61,68 | 518 811 | 219,45 | 145 819 | CPU (3,6×) |
| 128 | 176,72 | 724 302 | 295,30 | 433 457 | CPU (1,7×) |
| 512 | 727,05 | 704 219 | 573,57 | 892 652 | **CUDA (1,3×)** |
| 2048 | 2 820,78 | 726 041 | 1 650,01 | 1 241 204 | **CUDA (1,7×)** |

**Kesişme noktası kova 128 ile 512 arasındadır.** CUDA EP'nin sabit çekirdek başlatma
gecikmesi ~180 µs olduğundan küçük batch'lerde CPU belirgin şekilde öndedir.

**CPU↔CUDA çıktı paritesi** (tolerans 1e-4): tüm kovalarda `max abs Δvalue ≤ 2,98E-008`,
`max abs Δpriority ≤ 1,49E-008`.

**Karar kuralı:** self-play tek süreçte küçük/orta batch (≤ 2048, tipik olarak ≤ 128) ile
çalışır → **CPU EP yeterlidir ve daha hızlıdır**; `OnnxEvaluatorOptions.UseCuda = false`
doğru varsayılandır. GPU yalnızca çok oyunculu toplu çıkarım sunucusunda anlamlı olur
(kapsam dışı).

### 5.6 Shard biçimi (v1)

Ayrıntı: `SHARD_FORMAT.md`.

* 32 baytlık başlık: `"BGSP"`, `formatVersion = 1`, `featureVersion`, `vectorSize = 221`,
  `modelVersion`, `logTopCandidates`, `flags`, `reserved`.
* Oyun kaydı: `gameId`, `learnerSide`, `flags` (bit0 = aborted), `cubeValue`, `decisionCount`,
  kararlar, `winner`, `resultType`, `resultPoints`.
* Karar kaydı: `mover`, `flags` (bit0 `IsPass`, bit1 `IsLearner`, bit2 `ChosenIsTerminal`),
  `candidateTotal`, `loggedCount`, `searchValue`, `chosenVector[221]`, `Q[loggedCount]`,
  `policyTargetCs[loggedCount]`, `candVectors[loggedCount][221]`.
* Yalnızca `Kind == 1` adaylar loglanır, `Q`'ya göre azalan, en fazla `logTopCandidates`.
* Küçük-endian; `*.bgsp` veya gzip'li `*.bgsp.gz`.

**Çapraz dil doğrulaması:** C# `Shard_CrossLanguageFixture` → `ml/artifacts/csharp_shard.bgsp`
→ Python `test_reads_csharp_written_shard` + `test_csharp_policy_targets_match_python_softmax`.

### 5.7 Eğitim hedefleri

**TD(λ) değer hedefi** (yalnızca `IsLearner = 1` kararlar):

```
y[T-2] = -z
y[t]   = -((1-λ)·V̂[t+1] + λ·y[t+1])      t = T-3 … 0
```

İşaret: her karar o anki oyuncunun bakış açısından değerlendirilir, bu yüzden bir sonraki
durumun değeri negatiflenir. `DEFAULT_LAMBDA = 0.7`.

**Politika hedefi** (loglanan `Kind == 1` adaylar kümesi `E` üzerinde):

```
π_k = softmax_{k∈E}(Q_k / τ_train)
L_policy = -Σ_{k∈E} π_k · log p_k
```

`|E| < 2` olan kararlar atlanır; terminal ve `Kind == 2` adaylar dışlanır. `τ_train = 0.05`.

**Toplam kayıp:** `L = L_value + c_policy · L_policy`, `c_policy = 1.0`. Değer kaybı Huber
(varsayılan) veya MSE olabilir.

**Hedef keskinliği kapısı (F4-40).** `train.policy_min_sharpness` (varsayılan 0,99): hedef
entropisi `log|E|`'ye bu eşikten daha yakın kararlar **eğitimden** elenir. Raporlama tüm
uygun kararlar üzerinden yapılır. Gerekçe §5.9'da.

### 5.8 Self-play sürücüsü

| Dosya | Sorumluluk |
|---|---|
| `SelfPlayConfig.cs` | JSON yapılandırma + `Validate()` + `ToSearchSettings()` + `ToEvaluatorOptions()` |
| `SelfPlayAgent.cs` | Bir iş parçacığının `OnnxPolicyValueEvaluator` + `SearchWorkspace` + `SearchSettings` demeti |
| `SelfPlayRunner.cs` | Oyun döngüsü, hamle seçimi, karar başına vektörleştirme, aday loglama |
| `CommandLine.cs` | `--config` + `--ad=deger` çevrimdışı geçersiz kılmalar, `--help` |
| `Program.cs` | Model yükleme, iş parçacığı havuzu, shard yazımı, rapor |
| `EvalBench.cs` | `RandomBot`/`PipBot`/`Model` rakiplerine karşı `argmax` değerlendirmesi |
| `ShardFormat.cs`, `ShardModel.cs`, `ShardWriter.cs`, `ShardReader.cs` | v1 ikili biçim |

`OnnxModelHandle` **tüm** ajanlar arasında paylaşılır (tek `InferenceSession`); her ajan kendi
`OrtIoBinding`/tampon demetine sahiptir, böylece eşzamanlı `EvaluateBatch` güvenlidir.

**Oyun döngüsü:**

```
NewGame -> RollOpening
loop:
	Search(state, settings, workspace, evaluator)   // ExactRootScores = true
	Decide(...)                                     // softmax örnekleme veya argmax
	ApplyMove(state, chosen.Sequence)  |  PassTurn(state)
	IsGameOver(state, out result) -> break
	EndTurn(state, engineSettings)
	RollDice(state, rng)
	if ply >= MaxPlies -> flags |= Aborted; break
```

`Decide`: `ply < ExplorationPlies` ise `softmax(Q / selectionTemperature)` (yalnızca
`Kind ∈ {0,1}`), sonrasında `argmax(Q)`. Değerlendirme/lig maçlarında her zaman `argmax`.

**Determinizm:** `--threads N` ile oyunlar `i % N` kuralıyla dağıtılır; iş parçacığı `t`
RNG'si `Seed + t * 0x9E3779B97F4A7C15` ile tohumlanır. **Yalnızca `N = 1` birebir
tekrarlanabilir.**

### 5.9 Python eğitim laboratuvarı

| Dosya | Sorumluluk |
|---|---|
| `model.py` | `Backbone` (221→128→64, GELU) + `value_head` + `policy_head` |
| `export_onnx.py` | ONNX dışa aktarma (opset 15, dinamik batch) + PyTorch↔ORT parite kontrolü |
| `shards.py` | v1 shard okuyucu/yazıcı (C# ile aynı şema) |
| `td_lambda.py` | TD(λ) geriye dönük özyineleme |
| `losses.py` | Grup softmax çapraz entropi, MSE/Huber, toplam kayıp |
| `replay.py` | Replay buffer, değer/politika örnekleri, hedef keskinliği filtresi |
| `train.py` | Senkron eğitim döngüsü |
| `league.py` | Lig / model havuzu |
| `eval_bench.py` | Taban oyuncu raporları + yakınsama grafiği |
| `settings_bench.py` | Faz 3 arama ayarı ölçüm tablosu |
| `gnubg_er.py` | GNU Backgammon ER ölçümü |
| `config.yaml` | Tüm hiperparametreler |

**İterasyon akışı:**

```
for it in 1..iterations:
	(1) export(model) -> onnx/model_v{N}.onnx
	(2) Backgammon.SelfPlay --model ... --games G --depth D --out shards/it{it}
	(3) buffer.add_shard_dir(shards/it{it})          # son buffer_games oyun
	(4) value_samples  = build_value_samples(model, buffer, lam)   # mevcut agla
		policy_samples = build_policy_samples(buffer, tau_train)
	(5) train_steps(S adim, AdamW, clip_grad_norm)
	(6) olcum: sabit MC probe, buffer kayiplari, H/log|E|, gradyan normu
```

> **Not (F4-54):** `train.py` ONNX modelini iterasyonun **başında** (satır 590), checkpoint'i
> **sonunda** (satır 733) yazar. Yani `model_vN.onnx` ile `ckpt_vN.pt` bir iterasyon farklıdır.
> Bu bir hata değildir; `model_v1.onnx.parity.json` 5/5 doğrular.

**Ölçüm kümeleri:**

* **Sabit MC probe** — 1. iterasyonda `λ = 1.0` ile üretilir; hedefler `±z` olduğu için
  **ağdan bağımsızdır**. "Değer kaybı 0. adıma göre düşer" kriteri bu kümeyle ölçülür.
* **Sabit TD probe** — 1. iterasyonda `λ = 0.7` ile üretilir (sabit ama ağa bağımlı).
* **Buffer** — her iterasyonda güncel hedeflerle yeniden hesaplanır; politika kaybı düzgün
  baz `log|E|` ile karşılaştırılır.

### 5.10 Lig (model havuzu)

| Dosya | Sorumluluk |
|---|---|
| `ml/league.py` | `League`, `PoolEntry`, `EvalResult`, `run_eval`, `should_enter_pool`, `evaluate_for_entry` |
| `ml/runs/pool_d/pool.json` | Havuz indeksi (üye listesi + politika) |
| `ml/runs/pool_d/v{N}.onnx` | Dondurulmuş model artefaktları |

`League` alanları: `pool_dir`, `max_size` (10), `eviction` (`oldest` | `weakest`), `entries`.
Her `PoolEntry`: `name`, `onnx_path`, `model_version`, `iteration`, `strength`, `strength_se`;
`lower_confidence_bound = strength − 1,96·strength_se`.

**Akış:** oyunların %80'i kendi kopyasına karşı (iki taraf da `IsLearner`), %20'si donmuş
havuz modeline karşı (`learnerSide = ±1`, rastgele renk). Havuz rakibinin kararları
`IsLearner = 0` ile loglanır; kayıp hesaplanmaz, yalnızca TD önyüklemesi için kullanılır.
Her `K` iterasyonda sabit tohumlu `argmax` ile `N_eval = 400` oyun oynanır; giriş eşiği =
güven aralığının alt sınırı `> 0`.

**Ölçülen maliyet:**

| Derinlik | 400 oyunluk lig değerlendirmesi |
|---|---|
| 0 | ~7 s |
| 1 | ~690 s |

### 5.11 `eval_bench` — taban oyuncu raporları

| Tür | Uygulama | Not |
|---|---|---|
| `RandomBot` | `EvalBench.PlayRandom` — rastgele yasal hamle | hızlı, zayıf |
| `PipBot` | `EvalBench.PlayPip` — `rakipPip − kendiPip` maksimizasyonu | vurma eğilimli, oyunlar uzun |
| `Model` | `EvalBench.PlayModel` — başka bir ONNX modeli, `argmax` | önceki checkpoint / havuz üyesi |

**Protokol:** sabit seed; oyun `g` için `seed + g·0x9E3779B97F4A7C15`; renkler `g % 2` ile
değişir; öğrenen her zaman `argmax`. Sonuç: oyun başına ortalama puan ± standart hata ve
%95 güven aralığı.

### 5.12 gnubg ER ölçüm hattı

`ml/gnubg_er.py`, referans pozisyonlarda modelin hamle kalitesini **GNU Backgammon 1.08.003**
ile ölçer. Çıktı: pozisyon başına equity kaybı (ER) + özet (markdown/JSON).

**Alt süreç protokolü** (`gnubg-cli.exe -t`, komutlar stdin'e **bayt olarak**):

* `set board` için oyun içinde olmak gerekir — **her** tahta yüklemesinden önce `new game`.
  Aksi hâlde gnubg tahtayı **sessizce reddeder** ve önceki tahta kalır.
* `set cube use off` `new game`'den **önce** gelmelidir.
* `set evaluation chequerplay evaluation plies N` yalnızca `eval`'i etkiler; **`hint` her
  zaman 0-ply çalışır** (plies 0/1/2/3 aynı sonucu verir).
* `set evaluation chequerplay evaluation cubeful off` → cubeless equity.
* `eval` equity'si **sıradaki oyuncunun** bakış açısındandır; afterstate'i `turn = -turn` ile
  yükleyip sonucu negatife çevirmek gerekir.
* `show pipcount` sıradaki oyuncuyu **önce** yazar; ayrıştırıcı isimle eşleştirir
  (`MONSTER` = X = Siyah, `gnubg` = O = Beyaz).
* Çoklu `eval` çıktısı `The pip counts are:` satırından bölünür (`Position ID:` satırı
  `set board` tarafından da yankılandığı için kullanılamaz).
* Sayılar **ondalık virgül** ile yazılır (`+0,160`).

**Tahta dönüşümü.** gnubg'de X = Siyah (24→1 oynar, evi 1–6), O = Beyaz'dır:

```python
simple[0] = -board[25]          # Siyah bar
simple[i] = -board[i]           # i = 1..24
simple[25] = board[0]           # Beyaz bar
```

Doğrulama: başlangıç pozisyonu `4HPwATDgc/ABMA` position ID'sini ve 167/167 pip verir.

**ER tanımı:**

1. Modelin `afterStates` listesi 221 elemanlı vektöre çevrilir (Python portu
   `vector_golden.json`'a karşı **500/500** doğrulanmıştır) ve ONNX modeline verilir.
2. **Tüm** afterstate'ler tek gnubg sürecinde 2-ply cubeless `eval` ile değerlendirilir.
3. `E_best = max(equity)`, `E_model` = modelin seçtiği afterstate'in equity'si,
   `ER = E_best − E_model`.

`E_best` ve `E_model` aynı değerlendiriciden geldiği için ER tutarlıdır. gnubg'nin `hint`
sıralaması yalnızca bilgi amaçlı saklanır.

**Hamle seçimi (`--criterion`):**

| Değer | Anlamı |
|---|---|
| `policy` (varsayılan) | Politika başı argmax — C# `ArgMaxCandidate` ile aynı |
| `value` | Değer kafası argmax |
| `pip` | `rakipPip − kendiPip` argmax (`PipBot` tabanı) |

**Kullanılabilir vakalar.** `reference_positions.json` içindeki 57 vakanın **50'si** kullanılır
(15/15 taş + boş olmayan `afterStates`); 7 el yapımı vaka gnubg tarafından geçersiz sayılır.
Toplam **920 afterstate**. Her tahta yüklemesinden sonra `show pipcount` ile Python'un pip
sayımı karşılaştırılır; uyuşmazsa vaka atılır.

**Sonuç (Aşama D, `model_v10.onnx`):**

| Ölçüm | `policy` | `pip` tabanı |
|---|---|---|
| Ortalama ER | 0,1941 | **0,1283** |
| Medyan ER | 0,1410 | **0,0740** |
| Maksimum ER | **0,5600** | 0,9660 |
| gnubg ile aynı hamle | %32,0 | **%42,0** |

gnubg yoksa betik **uydurma değer üretmez**; çıkış kodu 2 ile temiz hata verir.

### 5.13 Aşama C — smoke eğitimi (kabul)

`python ml/train.py --out ml/runs/stage_c_accept --iterations 10 --games 100 --steps 200
--depth 0 --device cuda --eval-random 200 --seed 20260214 --lam 1.0`

10 iterasyon × 100 oyun = **1000 oyun**, iterasyon başına 200 eğitim adımı (toplam 2000).

| Ölçüm | Değer |
|---|---|
| Toplam süre | 308 s |
| Oyun başına self-play süresi (depth 0) | ~0,25 s |
| Değer örnekleri (son iterasyon) | 98 658 |
| Politika kararları (son iterasyon) | 83 835 (eğitime giren: 63 405) |
| Gradyan normu (son iterasyon ort. / maks.) | 2,42 / 4,62 — **sonlu** |
| NaN / Inf | **yok** |

| Kabul kriteri | Sonuç |
|---|---|
| 1000 oyunluk smoke tamamlandı | **EVET** |
| Kayıplar ve gradyanlar sonlu | **EVET** |
| Değer kaybı 0. adıma göre düşer | **EVET** — 1,9153 → 1,5629 (**−18,4 %**) |
| Politika kaybı düzgün bazın (`log\|E\|`) altına iner | **EVET** — 1,8513 < 2,1264 |
| Hedef entropisi / `log\|E\|` oranı raporlanır | **EVET** — 0,9984 → **0,3934** |
| `RandomBot`'a karşı kazanma oranı raporlanır | **EVET** — **%64,25** (400 oyun, ±%2,4) |

**`RandomBot` karşılaştırması (400 oyun, seed 424242, depth 0, argmax):**

| Model | λ | c_policy | Kazanma | Oyun başına puan |
|---|---|---|---|---|
| Eğitilmemiş ağ (`model_v1`) | — | — | %53,00 | +0,165 ± 0,102 |
| 10 iterasyon, kapı 0,99 | 0,7 | 1,0 | %40,25 | −0,435 ± 0,100 |
| 5 iterasyon, kapı yok | 0,7 | 0,0 | %57,50 | +0,345 ± 0,115 |
| **10 iterasyon, kapı 0,99** | **1,0** | **1,0** | **%64,25** | **+0,678 ± 0,092** |

**Aşama C bulguları (ölçülmüş, tahmin değil):**

1. **`λ = 0,7` + `γ = 1` uzun oyunlarda hedefleri sıfıra çökertiyor.** ~100 kararlık bir
   oyunda `0,7^20 ≈ 8e-4`; ilk ~80 kararın hedefi ~0. Ağ "her şeye 0 tahmin et" çözümüne
   yakınsıyor. Ölçüm: `λ = 0,7` ile değer kaybı 2,9373 → 2,8811 (**−1,9 %**), `λ = 1,0` ile
   1,9153 → 1,5629 (**−18,4 %**). `RandomBot` kazanma: %40,25 vs %64,25.
2. **Düzgüne yakın politika hedefleri değer fonksiyonunu bozuyor.** Eğitilmemiş ağın `Q`
   değerleri ~±0,04 aralığında olduğu için `softmax(Q / 0,05)` neredeyse düzgün çıkıyor
   (`H/log|E| = 0,998`). Politika gradyanı bilgi taşımıyor ama `c_policy = 1,0` ile büyüklüğü
   değer gradyanından ~20 kat fazla. Ölçüm (`λ = 0,7`, 5 iterasyon): `c_policy = 1,0` → %21,5;
   `c_policy = 0` → %58,0. **Uygulanan koruma:** `policy_min_sharpness = 0,99` (F4-40).
3. **Shard boyutu tahmini yanlıştı.** Spesifikasyonun ~11 KB/karar tahmini
   `logTopCandidates = 12` ve 221 float vektör (884 B/aday) ile uyumlu değil; gerçek değer
   **~1,0 KB/karar** (depth 0, gzip yok) ve **~0,14 KB/karar** (depth 1, gzip).

### 5.14 Aşama D — referans koşusu (kabul)

| Alan | Değer |
|---|---|
| Dizin | `ml/runs/stage_d` |
| Ayarlar | 10 iterasyon × 100 oyun, `S = 200`, `DepthPly = 1`, `MaxCandidates 4/4`, `λ = 1.0`, CPU |
| Seed | 20260214 |
| Süre | 1316 s (self-play 890 s) |
| Değer kaybı | 4,6620 → 2,5475 |
| Buffer politika kaybı | 1,3638 → 1,1916 (düzgün baz 1,3394) |
| Hedef entropisi / `log\|E\|` | 0,9969 → 0,3716 |
| Gradyan normu | 1,82 / 8,67 → 2,64 / 7,00 |
| Havuz | `v5` (taban), `v10` (+0,40 ± 0,1385 ile girdi) |

**Değerlendirme** (`model_v10.onnx`, seed 777, depth 1, 4/4, 200 oyun/rakip):

| Rakip | Kazanma | Ortalama puan | %95 GA |
|---|---|---|---|
| `RandomBot` | **%80,50** | +1,5800 ± 0,1308 | [+1,3237, +1,8363] |
| `PipBot` | %40,50 | −0,2300 ± 0,1452 | [−0,5146, +0,0546] |
| `Model:model_v5` | %54,50 | +0,2300 ± 0,1475 | [−0,0590, +0,5190] |

`PipBot` karşısında 28 oyun `max_plies` nedeniyle berabere bitti (uzun oyun eğilimi, F4-45).

### 5.15 Faz 3 arama ayarı ölçüm tablosu

`ml/settings_bench.py` altı kombinasyonu ölçer (`model_stage_c.onnx`, seed 1, `PipBot`):

| Ayar | Depth | Root/Inner | Oyun/s | s/oyun | B/oyun | Oyun | PipBot kazanma | Ortalama puan | %95 GA |
|---|---|---|---|---|---|---|---|---|---|
| depth 0, kısıtsız | 0 | 0 / 0 | 62,37 | 0,016 | 1 131 815 | 100 | %13,00 | −1,0000 ± 0,1639 | [−1,3213, −0,6787] |
| depth 0, kısıtlı | 0 | 4 / 4 | 87,32 | 0,011 | 293 877 | 100 | %9,00 | −1,0000 ± 0,1484 | [−1,2908, −0,7092] |
| depth 1, kısıtsız | 1 | 0 / 0 | 0,59 | 1,695 | 1 637 306 | 20 | %30,00 | −0,2500 ± 0,4284 | [−1,0897, +0,5897] |
| depth 1, kısıtlı | 1 | 4 / 4 | 2,17 | 0,461 | 304 375 | 20 | %45,00 | +0,0000 ± 0,4588 | [−0,8993, +0,8993] |
| depth 2, kısıtsız | 2 | 0 / 0 | zaman aşımı | > 600 | — | 0 | — | — | — |
| depth 2, kısıtlı | 2 | 4 / 4 | 0,02 | 50,0 | 481 997 | 2 | %0,00 | −1,5000 ± 1,5000 | [−4,4400, +4,4400] |

**Yorum:** aday kısıtlaması (4/4) depth 0'da **1,4× hızlandırır** ve shard'ı **3,9×
küçültür**; depth 1'de **3,7× hızlandırır** ve kazanma oranını %30 → %45'e çıkarır. Depth 2
kısıtsız pratik değildir (> 600 s/oyun); kısıtlı depth 2 bile oyun başına 50 s sürer.

### 5.16 Faz 4 kabul kriterleri

| # | Kriter | Durum | Kanıt |
|---|---|---|---|
| 1 | ONNX ihraç + PyTorch↔ORT parite | ✅ | `model_v1.onnx.parity.json` (5/5) |
| 2 | Dinamik batch ekseni (üç tensörde) | ✅ | `OrtParityTests` |
| 3 | Kova mekanizması, 0 bayt/çağrı | ✅ | `ConcurrencyAndAllocationTests` |
| 4 | CPU↔CUDA paritesi ≤ 1e-4 | ✅ | `InferenceBenchmark` (max 2,98E-008) |
| 5 | Değerlendirici sözleşmesi (kırpma, offset, terminal) | ✅ | `EvaluatorContractTests` |
| 6 | Faz 3 v7 entegrasyonu (Test 1/8/12/16/17) | ✅ | `Phase3IntegrationTests` |
| 7 | Shard v1 çapraz dil (C# ↔ Python) | ✅ | `ShardCrossLanguageTests` |
| 8 | Self-play sürücüsü, tek iş parçacığı determinizmi | ✅ | `SelfPlayDriverTests` |
| 9 | TD(λ) + politika hedefleri | ✅ | `ml/tests/test_td_lambda.py`, `test_losses.py` |
| 10 | 1000 oyunluk smoke, sonlu kayıp/gradyan | ✅ | `stage_c_report.md` |
| 11 | Değer kaybı düşüşü (sabit MC probe) | ✅ | −18,4 % |
| 12 | Politika kaybı < düzgün baz | ✅ | 1,8513 < 2,1264 |
| 13 | Hedef entropisi raporlanır | ✅ | 0,9984 → 0,3934 |
| 14 | `RandomBot` kazanma oranı raporlanır | ✅ | %64,25 (Aşama C), %80,50 (Aşama D) |
| 15 | Lig / model havuzu | ✅ | `ml/league.py`, `pool.json` |
| 16 | `eval_bench` üç rakip türü | ✅ | `EvalBenchTests` |
| 17 | Faz 3 arama ayarı ölçüm tablosu | ✅ | `settings_table.md` |
| 18 | **gnubg ER ölçümü** | ✅ | `stage_d_er.md` (ER 0,1941) |
| 19 | Yakınsama grafiği | ✅ | `ml/artifacts/stage_d_convergence.png` |
| 20 | Aşama D referans koşusu | ✅ | `stage_d_report.md` |

---

## 6. Test durumu (birleşik)

| Paket | Proje | Test | Süre | Durum |
|---|---|---|---|---|
| C# motor | `Backgammon.Tests` (Release) | **297** | ~29 dk 56 s | ✅ 297/297 |
| C# çıkarım | `Backgammon.Inference.Tests` (Release) | **100** | ~18 s | ✅ 100/100 (Test 61 CUDA yoksa `Inconclusive`) |
| C# UI | `Backgammon.UI.Tests` (Release) | **88** | ~5 s | ✅ 88/88 |
| Python | `ml/tests` | **1592** | ~10 dk | ✅ 1592/1592 (3 yavaş/koşullu test atlanır) |
| **Toplam** | | **2077** | | **✅ 0 başarısız** |

**Unity testleri (ayrı, Unity gerektirir):**

| Platform | Test | Süre | Durum |
|---|---|---|---|
| EditMode | **7** | ~0,6 s | ✅ 7/7 |
| PlayMode | **17** | ~20 s | ✅ 17/17 |

Unity testleri `dotnet test` kapsamında değildir; `unity/build.log` içinde kayıtlıdır.

**Neden `Backgammon.Tests` yalnızca Release'te?** Debug derlemesinde `SanityCheck`/`DebugAssert`
etkin olduğu için 1 000 000 oyunluk fuzz ve performans testleri kullanılamaz hızda çalışır
(F4-53). Release'te 6 test eksik görünür: `[Conditional("DEBUG")]` işaretli çağrı yerleri
Release'te derlenmez — bu beklenen farktır (Faz 1'den beri aynı).

**Bilinen kararsız test:** `PerformanceTests.GenerateAfterStates_Throughput` eşiği
(> 300 000 afterstate/sn) yüke duyarlıdır. Tam koşu sırasında başka ağır iş paralel
çalışıyorsa 296 000 civarına düşüp kırmızı görünebilir; **tek başına koşulduğunda
6/6 geçer**. Bu bir gerileme değildir. Doğrulama:
`dotnet test Backgammon.Tests -c Release --filter "FullyQualifiedName~PerformanceTests"`.

**Test dağılımı:**

| Paket | Dosya | Kapsam |
|---|---|---|
| `Backgammon.Tests` | `BackgammonStateTests`, `MoveStructureTests`, `CoordinateTests` | Veri yapıları, koordinat yardımcıları |
| | `ZobristTests` | Hash tanımı, `MirrorTo` simetrisi, artımlı = tam |
| | `SanityCheckTests` | `SanityCheck` maddelerinin gerçekten yakaladığı |
| | `EngineFlowTests` | `ApplyStep`/`UndoStep`, `ApplyMove`/`UndoMove`, `SetDice`, `LoadAfterState`, `EndTurn` |
| | `LegalMoveGeneratorTests` | Uç durumlar + brute-force referans (1000+ pozisyon) + simetri |
| | `CubeAndMatchTests` | Küp, Crawford, Jacoby, mars, maç akışı |
| | `ReferenceComparisonTests` | Bağımsız Python referansı (57 pozisyon / 927 sonuç) |
| | `FuzzTests` | Seed'li oyun fuzz'ı (2 000 varsayılan, `[Explicit]` 1 000 000) |
| | `PerformanceTests` | Hız, allocation, çok çekirdekli ölçeklenme |
| | `VectorizerTests`, `VectorGoldenData` | 221 nöron, altın veri |
| | `AfterStateListTests`, `StatePoolTests` | SoA, havuz |
| `Backgammon.Inference.Tests` | `OrtParityTests` | PyTorch↔ORT, dinamik batch |
| | `EvaluatorContractTests` | Kırpma, offset, terminal, `Version`, `SetModel` |
| | `ConcurrencyAndAllocationTests` | İş parçacığı güvenliği, 0 bayt/çağrı |
| | `Phase3IntegrationTests` | Faz 3 v7 Test 1/8/12/16/17 |
| | `ShardCrossLanguageTests` | C# ↔ Python shard |
| | `SelfPlayDriverTests`, `EvalBenchTests` | Sürücü, değerlendirme |
| | `InferenceBenchmark`, `SpikeZeroAllocation` | `[Explicit]` ölçüm |
| `Backgammon.Tests` | `BearoffTests` | Faz 5 Aşama A: Test 1–13 (indeks, CRC, başlık, CDF, dekoratör) |
| `Backgammon.Tests` | `MatchTests`, `CubeAndMatchTests` | Faz 5 Aşama B: Test 14–26 (MET, küp, Crawford, maç farkındalığı) |
| `Backgammon.UI.Tests` | `ViewModelTests` | Faz 5 Aşama C: Test 27–31 (board/küp/skor/analiz VM, hamle girişi) |
| `Backgammon.UI.Tests` | `OrchestratorTests` | Faz 5 Aşama C: Test 32–33 (deterministik self-play, iptal) + `Think()` |
| `ml/tests` | `test_model`, `test_export_parity`, `test_golden_input` | Ağ, ONNX, altın girdi |
| | `test_losses`, `test_td_lambda`, `test_numerics`, `test_tau_crosscheck` | Kayıplar, TD(λ), sayısal kararlılık |
| | `test_shards`, `test_replay`, `test_train` | Shard, buffer, eğitim döngüsü |
| | `test_league`, `test_eval_bench`, `test_settings_bench` | Lig, değerlendirme, ayar tablosu |
| | `test_gnubg_er` | gnubg ER (35 test; gnubg yoksa `skipif`) |
| | `test_docs_consistency` | Belge tutarlılığı (20 test): yol varlığı, test sayıları, bölüm/karar kimliği sırası |
| | `test_artifact_roundtrip` | Artefakt raporlarının kendi `.json` çıktısından bayt bayt yeniden üretimi (3 test) |
| | `test_met_extraction` | Faz 5 Test 35: MET değişmezleri + gnubg XML eşleşmesi (4 test) |
| | `test_bearoff_ref_matches_csharp` | Faz 5 Test 34: bağımsız Python DP ↔ C# tablosu (3 test) |
| | `test_export_output_version` | Faz 5 Test 36 + Faz 6 Test 59: `output_version` metadata'sı ve v2 paritesi (8 test) |
| | `test_stage_b` | Faz 6 Aşama B: Test 53, 55, 56 (equity formülü, `L_cal`, sıcaklık) (9 test) |
| | `test_stage_c` | Faz 6 Aşama C: Test 63, 64, 65, 67 (shard v1 okunabilirliği, Linux yayını, `outcomeProbs` yokluğu, veri hacmi) (4 test) |
| `Backgammon.Tests` | `OutcomeDistributionV2Tests` | Faz 6 Aşama B: Test 49–52 (dışlayıcı equity, antisimetri, normalizasyon) |
| `Backgammon.Inference.Tests` | `OutputVersion2Tests` | Faz 6 Aşama B: Test 54, 57, 58 (v2 kabul, sıfır allocation, v1 geriye uyum) |
| `Backgammon.Inference.Tests` | `StageCDataEngineTests` | Faz 6 Aşama C: Test 60, 61, 62, 65, 66 (paralel determinizm, GPU ölçümü, açılış çeşitliliği, `dup_cap`) |

---

## 7. Birleşik ölçüm tablosu

| Faz | Ölçüm | Değer |
|---|---|---|
| 1 | `GenerateAllLegalMoves` | ~480 000 çağrı/sn |
| 1 | `GenerateAfterStates` | ~340 000 çağrı/sn |
| 1 | Rastgele oyun (tek çekirdek / 12 thread) | ~1 700 / ~9 200 oyun/sn |
| 1 | Fuzz (1 000 000 oyun) | 0 hata, 1 sa 2 dk |
| 2 | `Vectorize` | ~3 650 000 çağrı/sn |
| 2 | `VectorizeBatch` | ~3 100 000 kayıt/sn |
| 2 | Altın eşleşme | 500 × 221 birebir |
| 3 | Referans eşitliği | max \|Δ\| = 0 |
| 3 | Arama allocation | 0 bayt |
| 4 | ONNX çıkarım (CPU, kova 128) | ~724 000 poz/sn |
| 4 | ONNX çıkarım (CUDA, kova 2048) | ~1 241 000 poz/sn |
| 4 | ONNX allocation | 0 bayt/çağrı (tüm kovalar) |
| 4 | CPU↔CUDA paritesi | max 2,98E-008 |
| 4 | Aşama C değer kaybı | 1,9153 → 1,5629 (−18,4 %) |
| 4 | Aşama C `RandomBot` | %64,25 |
| 4 | Aşama D değer kaybı | 4,6620 → 2,5475 |
| 4 | Aşama D `RandomBot` / `PipBot` / `model_v5` | %80,50 / %40,50 / %54,50 |
| 4 | gnubg ER (`policy` / `pip`) | 0,1941 / **0,1283** |
| 5 | Bearoff DB boyutu / `MaxRolls` | 2 496 208 bayt / 22 |
| 5 | Bearoff C# ↔ Python referansı | max \|Δ\| = 7,630E-006 |
| 5 | MET (Rockwell–Kazaross) ↔ gnubg 1.08.003 | max \|Δ\| = **0,000E+000** (625 hücre) |
| 5 | Küp anlaşması (gnubg 0-ply, 132 pozisyon) | ikileme %51,52 / alma %61,36 / ikisi %46,21 |
| 5 | Değer kafası kalibrasyonu (400 afterstate) | eğim **0,0874**, korelasyon +0,2431, MAE 0,8014 |
| 5 | Unity EditMode / PlayMode | 7/7 / 5/5 |

---

## 8. Bilinen sınırlar ve sonraki adımlar

### 8.1 Kapsam dışı (bilinçli)

* **Küp kararları (Faz 4'te).** Faz 4'te `ICubeEvaluator`/`ICubePolicyEvaluator` arayüzleri vardı,
  uygulama yoktu; tüm eğitim ve ölçüm **money game, küpsüz, Jacoby kapalı** varsayımıyla yapıldı
  (F4-01). **Faz 5'te kapandı:** `EquityCubeAdvisor` + `MatchEquityTable` (bkz. §12.3).
* **Çok oyunculu toplu çıkarım sunucusu.** GPU yalnızca orada anlamlı olurdu (spec v3 §10).
* **İki taraflı bearoff veritabanı.** 2 944 581 696 pozisyon ≈ 29,4 GB; Faz 6'ya ertelendi (F5-06).
* **Unity entegrasyonu (Faz 4'te).** Faz 4'te `Backgammon.Core.asmdef` hazırdı ama sahne/UI yoktu.
  **Faz 5'te kapandı:** `F:\Projects\Unity\Tavla3D` (bkz. §12.5).

### 8.2 Ölçülmüş zayıflıklar

1. **Model `PipBot`'tan zayıf.** gnubg ER: model 0,1941 vs `PipBot` 0,1283. 10 × 100 oyunluk
   referans koşusu bir **altyapı doğrulamasıdır**; güç hedefi değildir. Gerçek eğitim için
   mertebe olarak 10⁵–10⁶ oyun ve çok daha fazla iterasyon gerekir.
2. **`PipBot` karşısında uzun oyunlar.** 200 oyunun 28'i `max_plies` nedeniyle berabere
   bitti; `PipBot` vurma eğilimli olduğu için oyunlar uzuyor (F4-45).
3. **`λ = 0,7` + `γ = 1` uyumsuz.** Uzun oyunlarda hedefler sıfıra çöküyor; `λ = 1,0`
   (Monte Carlo) veya `γ < 1` gerekir (F4-41).
4. **Depth 2 pratik değil.** Kısıtsız > 600 s/oyun; kısıtlı bile 50 s/oyun.
5. **`--threads > 1` deterministik değil.** İş parçacığı başına ayrı RNG (F4-39).

### 8.3 Sonraki adımlar (öncelik sırası)

1. **Gerçek eğitim koşusu.** 10⁵+ oyun, 50+ iterasyon, `λ = 1,0`, `DepthPly = 1`,
   `MaxCandidates 4/4`, CPU. Hedef: `PipBot` karşısında > %55, gnubg ER < 0,10.
2. **Küp ağı.** Ayrı bir `ICubeEvaluator` uygulaması + küp self-play verisi.
3. **gnubg referans verisi (Faz 1 E-01).** gnubg artık kurulu; `reference_positions.json`
   şemasıyla gnubg'den hamle üretimi referansı alınabilir.
4. **Depth 2 için performans.** Aday kısıtlaması + transposition table genişletmesi.
5. **Belge tutarlılığı.** `ml/tests/test_docs_consistency.py` sayıların belgelerle
   uyuşmasını otomatik doğrular (bkz. §9).

---

## 9. Belge tutarlılığı testi

`ml/tests/test_docs_consistency.py`, belgelerdeki sayısal iddiaların gerçekle uyuşmasını
doğrular:

* `PHASES.md` §6'daki test sayıları (`245`, `57`, `28`, `194`) ile `pytest --collect-only` ve
  C# test dosyalarındaki `[Test]` sayıları tutarlı mı?
* Belgelerde referans verilen tüm artefakt dosyaları (`ml/artifacts/*.md`, `*.json`,
  `*.onnx`, `SHARD_FORMAT.md`) mevcut mu?
* `ARCHITECTURE.md` bölüm numaraları tekrar/sıra hatası içeriyor mu?
* `ASSUMPTIONS.md` karar kimlikleri (`B-`, `C-`, `D-`, `E-`, `F2-`, `F3-`, `F4-`, `F5-`)
  benzersiz ve sıralı mı?
* `ml/artifacts/*.md` raporları, ilgili `.json` çıktısından hâlâ bayt bayt yeniden
  üretilebiliyor mu (`test_artifact_roundtrip.py`)?

Bu test, bu belgenin yazılması sırasında bulunan belge kaymalarını (ARCHITECTURE.md §18 ve
§34'teki eski test sayıları, `ASSUMPTIONS.md` F4-24'teki "gnubg kurulu değil" ifadesi)
tekrar oluşmaktan korur.

### 9.1 Artefakt üreticileri ve Türkçe diyakritikler

`ml/artifacts/` altındaki raporların tamamı bir Python betiği tarafından üretilir; elle
düzenlenmez. Üreticiler (`ml/eval_bench.py`, `ml/league.py`, `ml/settings_bench.py`,
`ml/gnubg_er.py`) metin şablonlarını **Türkçe diyakritiklerle** (`ı`, `ş`, `ğ`, `ü`, `ö`, `ç`)
yazar. Bu sayede:

* Rapor yeniden üretildiğinde diyakritikler korunur (ASCII'ye düşmez).
* `settings_table.md`, `stage_d_er.md` ve `stage_d_eval.md` dosyaları, ilgili `.json`
  çıktısından **bayt bayt aynı** şekilde yeniden üretilir. Bu eşitlik
  `ml/tests/test_artifact_roundtrip.py` ile her test koşusunda doğrulanır.

Bir rapor metnini değiştirmek gerektiğinde önce üreticideki şablonu, sonra `.json` içindeki
etiketleri güncelleyin; aksi hâlde bir sonraki üretim eski metni geri getirir.

---

## 10. Yeniden üretim komutları

```powershell
# 1. Derleme (0 uyarı / 0 hata beklenir)
dotnet build TavlaAI_Project.slnx -c Release --nologo -v q

# 2. C# motor testleri (Release zorunlu, ~25 dk)
dotnet test Backgammon.Tests -c Release --nologo

# 3. C# çıkarım testleri (~2 s)
dotnet test Backgammon.Inference.Tests -c Release --nologo

# 4. Python testleri (~12 s)
python -m pytest ml/tests -q

# 5. Vektör altın doğrulaması (bağımsız Python/numpy)
python tools/vector_verify.py

# 6. Referans veri üretimi (bağımsız Python motoru)
python tools/reference_gen.py

# 7. Smoke eğitimi (Aşama C, ~5 dk CUDA)
python ml/train.py --out ml/runs/stage_c_accept --iterations 10 --games 100 `
	--steps 200 --depth 0 --device cuda --eval-random 200 --seed 20260214 --lam 1.0

# 8. Aşama D referans koşusu (~22 dk CPU)
python ml/train.py --out ml/runs/stage_d --iterations 10 --games 100 `
	--steps 200 --depth 1 --max-root 4 --max-inner 4 --lam 1.0 --seed 20260214

# 9. Değerlendirme (üç rakip)
python ml/eval_bench.py --model ml/runs/stage_d/onnx/model_v10.onnx `
	--opponents random,pip --vs-model ml/runs/pool_d/v5.onnx `
	--games 200 --seed 777 --depth 1 --max-root 4 --max-inner 4 `
	--out ml/artifacts/stage_d_eval.md --json ml/artifacts/stage_d_eval.json

# 10. Faz 3 arama ayarı tablosu
python ml/settings_bench.py --model ml/artifacts/model_stage_c.onnx --profile quick `
	--out ml/artifacts/settings_table.md --json ml/artifacts/settings_table.json

# 11. gnubg ER ölçümü (~35 dk)
python ml/gnubg_er.py --model ml/runs/stage_d/onnx/model_v10.onnx --plies 2 `
	--criterion policy --out ml/artifacts/stage_d_er.md --json ml/artifacts/stage_d_er.json

# 12. Yakınsama grafiği
python ml/eval_bench.py --plot ml/runs/stage_d/train_report.json `
	--plot-out ml/artifacts/stage_d_convergence.png
```

---

## 11. Belge haritası

| Soru | Belge |
|---|---|
| Dört fazın tamamı, kabul kriterleri, ölçümler | **`PHASES.md`** (bu dosya) |
| Bir bileşen nasıl tasarlandı, neden böyle? | `ARCHITECTURE.md` §1–§42 |
| Belirsiz bir noktada hangi karar verildi, neden? | `ASSUMPTIONS.md` |
| Shard dosyası nasıl okunur/yazılır? | `SHARD_FORMAT.md` |
| Aşama C smoke eğitimi ayrıntıları | `ml/artifacts/stage_c_report.md` |
| Faz 5 (bearoff, küp/maç, UI, Unity) | **`PHASES.md` §12** + `ARCHITECTURE.md` §43 |
| Unity projesi kurulumu, testleri, bulunan hatalar | `unity/README.md` |
| Unity derleme/test kaydı | `unity/build.log` |
| Faz 5 ölçüm raporu | `ml/artifacts/stage_e_faz5.md` |
| Küp kararı karşılaştırması (gnubg) | `ml/artifacts/stage_b_cube.md` |
| Değer kafası teşhisi | `ml/artifacts/stage_b_afterstates.md` |
| Aşama D lig/eval/ayar/gnubg ayrıntıları | `ml/artifacts/stage_d_report.md` |
| Faz 6 Aşama D ölçekli eğitim raporu | `ml/artifacts/stage_f_train.md` |
| Faz 6 Aşama E arama gücü raporu | `ml/artifacts/stage_e_search.md` |
| CPU vs CUDA kararı (Faz 6 Aşama C) | `ml/artifacts/stage_c_gpu_decision.md` |
| gnubg ER ham çıktısı | `ml/artifacts/stage_d_er.md`, `stage_d_er.json`, `stage_d_er_pip.json` |
| Değerlendirme ham çıktısı | `ml/artifacts/stage_d_eval.md`, `stage_d_eval.json` |
| Arama ayarı tablosu | `ml/artifacts/settings_table.md`, `settings_table.json` |
| CPU vs CUDA ölçümü | `ml/artifacts/inference_benchmark.txt` |
| Yakınsama grafiği | `ml/artifacts/stage_d_convergence.png` |

---

## 12. Faz 5 — Bearoff veritabanı, küp/maç katmanı, UI ve Unity

Faz 5'in hedefi, Faz 4'te eğitilen ağı **oynanabilir bir ürüne** dönüştürmekti: kesin
bearoff değerlendirmesi, küp ve maç farkındalığı, Unity'den bağımsız bir UI katmanı ve
Unity sahnesi. Ağırlık merkezi **motor değil, ürün**tür; ağ kalitesi Faz 4'teki seviyede
kalmıştır (bkz. §12.8).

### 12.1 Aşama planı ve kabul durumu

| Aşama | Kapsam | Test | Durum |
|---|---|---|---|
| A | Bearoff veritabanı + dekoratör | 1–13 | ✅ 13/13 |
| B | Küp/maç katmanı | 14–26 | ✅ 47/47 (14–26 + genişletilmiş küp testleri) |
| C | AI entegrasyonu (`Backgammon.UI`) | 27–37 | ✅ 27–33 C# (12/12), 34–37 Python (13 test) |
| D | Unity görselleştirme | 38–40 | ✅ EditMode 7/7, PlayMode 5/5 |
| E | Belge birleştirme | — | ✅ bu bölüm |

### 12.2 Aşama A — Bearoff veritabanı

**Tasarım kararı (F5-01):** veritabanı **modelin içinde değil**, `BackgammonSearch` ile
`OnnxPolicyValueEvaluator` **arasında bir dekoratördür**. Böylece:

* Faz 1 API'si hiç değişmedi (`AfterStateList.CopyRecordFrom` gibi eklemeler yapılmadı).
* Ağ, bearoff pozisyonlarını hiç görmez; kesin değer ağın hatasını taşımaz.
* Dekoratör kapatılabilir (`BearoffAwareOptions.DisableBearoff`) ⇒ A/B karşılaştırması
  aynı ikiliyle yapılabilir.

**Format (F5-02):** 64 baytlık başlık + `positions × (maxRolls+1) × uint16` CDF tablosu.
`magic = "TVB1"`, `version = 1`, `points = 6`, `checkers = 15`, `positions = 54 264`,
`payloadCrc32` (CRC-32/ISO-HDLC). Nicemleme `round(clamp(x,0,1) × 65535)`; en büyük
okuma hatası `1/65535 ≈ 1,53E-005`.

**Sıralama (F5-03):** kendi colex sıralaması — `Rank(c) = Σ_{i=0..5} C(S_i + i, i+1)`.
gnubg indeksine bağımlılık yok; `Unrank` ile tam tur doğrulandı (54 264 pozisyon).

**DP (F5-04):** `P(T(c) ≤ k) = (1/36) Σ_zar max_hamle P(T(c') ≤ k−1)`. Yasal hamleler
`LegalMoveGenerator`'dan gelir, yeniden yazılmadı. `MaxRolls` 12'den **22**'ye otomatik
yükseltildi (en kötü pozisyon: 6 hanesinde 15 pul).

**Dosya:** `ml/artifacts/bearoff1_v1.bin` — 2 496 208 bayt (2,38 MiB), `MaxRolls = 22`,
mars tablosu yok. Üretim ~5,5 s (geçiş tablosu ~5,0 s + DP ~0,5 s).

**Bağımsız doğrulama:** `ml/bearoff_ref.py` yalnızca §3.2/3.3/3.9'dan yazılmış ayrı bir
Python DP'sidir. C# tablosuyla en büyük fark **7,630E-006** (nicemleme sınırının altında),
tolerans dışı hücre **0**. Test 34 bunu her koşuda doğrular.

**Kesin denklem (§3.7):** `pA[k] = cdfA[k] − cdfA[k−1]`,
`P(A kazanır) = Σ_k pA[k]·(1 − cdfB[k−1])`, `E = 1 − 2·P(win)`. Saf yarışta mars yoktur;
arka arkaya mars zaten imkânsızdır.

### 12.3 Aşama B — Küp ve maç katmanı

**Küp ve maç ağın dışındadır (F5-07).** Gerekçe: küp kararı `argmax` değil **eşik**
kararıdır; maç kazancı ise MET ile kapalı biçimde hesaplanır. İkisi de ağa sokulursa
hem eğitim verisi hem de kalibrasyon ikiye katlanır, karşılığında hiçbir şey kazanılmaz.

**Negamax tuzağı (F5-08):** maç kazanma olasılığı `MWC` **monoton** olduğu için hamle
seçimini değiştirmez; ama `MWC` doğrudan negamax'a verilirse işaret/ölçek bozulur.
Doğru dönüşüm `ME = 2·MWC − 1`'dir. `MatchAwareEvaluator` bunu uygular; money game'de
tam kimliktir.

**MET (F5-09):** Rockwell–Kazaross tablosu `Backgammon.Core/Match/met_rk.json` içine
gömülüdür (25 × 25). gnubg 1.08.003'ün `Rockwell-Kazaross.xml` dosyasıyla **625 hücrenin
tamamında max |Δ| = 0,000E+000** — bit düzeyinde aynı.

**Küp eşikleri (F5-10):** money game'de `E_doubleTake = 2E`, `E_doublePass = 1`.
Buradan `E > 0,5` ⇒ ikileme; `E > 1,0` ⇒ ikileme ama rakip pas geçer (too good);
`E < 0,5` ⇒ alma. **Spec ile ilk uygulama çelişiyordu** (`MoneyTakePoint = 1,0`
kullanılıyordu); spec'in türetmesi doğru olduğu için uygulama düzeltildi
(`MoneyTooGoodPoint = 1,0`, `shouldTake = E < 0,5 − ε`).

**Maç farkındalığının ölçülen katkısı:** 400 oyunluk karşılaştırmada 2-away %40,00 vs
%39,50, 4-away %39,75 vs %40,00, 5-away %42,25 vs %44,75 — **hepsi standart hatanın
içinde**. Yani bu modelle maç farkındalığı ölçülebilir bir kazanç sağlamıyor. Nedeni
§12.8'deki değer kafası sorunudur, katmanın kendisi değil.

### 12.4 Aşama C — AI entegrasyonu (`Backgammon.UI`)

`Backgammon.UI` **netstandard2.1** ve **hiçbir `UnityEngine` türü içermez**. Bu, Test
27–33'ün Unity olmadan `dotnet test` ile koşmasını sağlar.

| Tür | Görev |
|---|---|
| `GameOrchestrator` | Zincir kurulumu, arama, oyun akışı, küp, analiz |
| `PositionAnalysis` | UI'ye hazır DTO (equity, MWC, dağılım, pip, rolls-to-off, küp) |
| `BoardViewModel` / `CubeViewModel` / `MatchScoreViewModel` | Durum yansıması |
| `AnalysisViewModel` | tr-TR biçimlendirme, "Kesin"/"Tahmin" rozeti |
| `MoveInputController` | Yasal hedef üretimi, kısmi hamle, geri alma |
| `BoardLayout` | 24 hane + bar + tepsi + küp dikdörtgenleri (çakışmasız) |
| `SearchOutcome` | `SearchResult` (`ref struct`) için `Task<T>` uyumlu taşıyıcı |

**Zincir:** `MatchAwareEvaluator` (dış) → `BearoffAwareEvaluator` → temel değerlendirici.
Money game'de `MatchAwareEvaluator` atlanır. `Version` değişince `SearchWorkspace.Reset()`
zorunludur (Faz 3 §3.5).

**Eşzamanlılık:** `SemaphoreSlim(1,1)` — aynı anda tek arama. İkinci çağrı
`InvalidOperationException` atar (Test 33).

### 12.5 Aşama D — Unity

Unity **6000.3.8f1**, URP 17.3.0, uGUI 2.0.0, Input System 1.18.0, test-framework 1.6.0.
Proje: `F:\Projects\Unity\Tavla3D`. Kurulum ve test komutları `unity/README.md`
içinde, gerçek koşu kaydı `unity/build.log` içindedir.

**Aşama D'de bulunan üç gerçek hata:**

1. **`BoardLayout` kayan nokta çakışması.** Komşu hanelerin sol kenarı `c·w`, sağ kenarı
   `(c+1)·w` ile hesaplanınca kayan noktada `1E-013` mertebesinde üst üste binme oluşuyordu.
   Test 38 yakaladı; `left`/`right` aynı ifade ailesinden türetilerek düzeltildi.
2. **ONNX Runtime iş parçacığı güvenliği.** `OrtIoBinding` iş parçacığı güvenli değildir.
   Arama gerçek kare döngüsü içinde arka plan iş parçacığında çalıştırıldığında
   `SynchronizeBoundInputs` erişim ihlali (`0xC0000005`) üretiyordu. Tek başına çalışan
   arka plan aramaları geçiyordu; hata yalnızca sahne + kare döngüsü + ONNX birlikteyken
   ortaya çıkıyordu. Düzeltme: `GameOrchestrator.Think()` — arama **çağıran iş
   parçacığında** senkron çalışır; Unity tarafı bunu kullanır. `ThinkAsync` Unity'den
   bağımsız katmanda ve testlerde aynen geçerlidir.
3. **Girdi işleyicisi.** `StandaloneInputModule` yalnızca eski girdi arka ucuyla çalışır;
   proje Input System paketini kullanıyordu (`activeInputHandler: 1`) ve her karede
   `InvalidOperationException` atıyordu. `activeInputHandler: 2` (**Both**) yapıldı.

**Lisans:** batchmode lisansı bu makinede mevcuttur; "Unity testleri geçti" ifadesi
gerçekten geçen sonuçlara dayanmaktadır (`unity/build.log`).

### 12.5.1 Aşama D sonrası oynanabilirlik yamaları

Aşama D kapandığında oyun **oynanamıyordu**: bardan giriş ve toplama tıklanamıyor,
insanın küp teklifi yanıtsız kalıyordu. Dört dosya düzeltildi.

| # | Kusur | Düzeltme |
|---|---|---|
| 1 | `BarView`/`TrayView` yalnızca görüntüydü (`IPointerClickHandler` yok) | `IPointerClickHandler`, `Point`, `Clicked`, `Initialize(int)`, `SetHighlight(bool)` eklendi |
| 2 | `BoardView.ApplyHighlights` yalnızca 1..24'ü dolaşıyordu; bar (0/25) ve tepsi (0/25) hiç vurgulanmıyordu | `CreateBar(name, point)` / `CreateTray(name, point)`; `raycastTarget = true`; `TrayClicked` olayı; bar/tepsi vurguları |
| 3 | `BoardInputController` tepsi tıklamasını bilmiyordu | `TrayClicked` aboneliği, `OnTrayClicked(int)`, `HitTest` içinde `HitTestTray` (sürükle-bırak ile toplama) |
| 4 | `GameBootstrap.Update` içinde `GamePhase.CubeOffered` dalı yoktu → insan küp teklifinde kilitlenme | `_pendingAiTake` alanı; "Kup" düğmesi `OfferDouble()`'dan **önce** `EvaluateCube().ShouldTake` saklar; `Update` saklanan kararı uygular |

**Neden `OfferDouble()`'dan önce?** `EquityCubeAdvisor.Decide` yalnızca `PreRoll`
fazında gerçek karar üretir; `CubeOffered` fazında `ShouldTake = true` sabitini
döndürür. Karar bu yüzden tekliften önce yakalanır.

**Yeni test:** `FullGameTests.FullGame_ReachesGameOver` (PlayMode) bir oyunu her iki
taraf da AI ile oynayarak `GameOver` fazına kadar götürür; `SmokeTests`'in 60 karelik
penceresi bu kilitlenmeleri yakalayamıyordu. Süre 3,98 s (`DepthPly = 0`).

**Windows derlemesi:** `TavlaAI.Editor.BuildScript.BuildWindows64` →
`F:\Projects\Unity\Tavla3D\Build\Tavla3D.exe`. Derleme çalıştırıldığında
`Player.log` içinde hiçbir istisna/uyarı yoktur.

### 12.5.2 Sprite katmanı (görsel zenginlik)

Aşama D sonunda tahta düz renkli dikdörtgenlerden oluşuyordu. `SpriteLibrary`
eklenerek tahta, haneler, pullar, zarlar, küp, bar ve tepsiler sprite ile çizilir
hâle geldi.

| Özellik | Davranış |
|---|---|
| Kaynak seçimi | Önce `Resources/Sprites/<ad>`, yoksa **kodla üretilen** sprite |
| Önbellek | `Dictionary<string, Sprite>`, `HideFlags.DontSave` — kare içinde ayırma yok |
| Varlık adları | `board`, `point`, `checker_white`, `checker_black`, `die_1`…`die_6`, `cube`, `bar`, `tray` |
| PNG kuralı | **Texture Type = Sprite (2D and UI)**; aksi hâlde `Resources.Load<Sprite>` `null` döner |
| Çizim sırası | uGUI'de son kardeş üstte → `CheckerPool` **en son** kurulur |

Değişen dosyalar: `SpriteLibrary.cs` (yeni), `UiFactory`, `CheckerView`,
`CheckerPool`, `BoardView`, `DiceView`, `CubeView`. `CheckerPool.Place(Color, …)`
aşırı yüklemesi korunduğu için Test 40 anlamı değişmedi.

Doğrulama: `CompileOnly` 0 hata, EditMode 7/7, PlayMode 5/5
(`FullGame_ReachesGameOver` 1,82 s), `BuildWindows64` `Succeeded (0 hata)`,
player 12 s istisnasız. Piksel analizi (1600×1000 pencere): ahşap %53,0,
koyu üçgen %16,9, açık üçgen %12,5, siyah pul %11,5, beyaz pul %6,2.

### 12.5.3 Duyarlı kenar çubuğu yerleşimi

Kullanıcı geri bildirimi: *"Tavla tahtası üzerinde buton/yazılar oyun alanını
kapatıyor. Sağ tarafta oyunu engellemeyecek şekilde dizayn et. Seçenekler
butonunu tıklamadan da seçenekler menüsü ekranda gözüküyor."*

| Sorun | Kök neden | Çözüm |
|---|---|---|
| Denetimler tahtanın üstünde | `BoardRoot` 1600×1000 ortada; HUD/kontrol çubuğu üstüne biniyordu | `BoardArea` (esnetilmiş) + `BoardFitter` (en-boy oranı korunur) + sağa sabitlenmiş kenar çubuğu |
| Ayarlar paneli kendiliğinden açık | `SetVisible` yalnızca `Background`'ı kapatıyordu; `_summary` ve 3 düğme kardeş nesneydi | Tüm çocuklar `Content` altında; `SetVisible` onu açar/kapatır; `IsVisible` eklendi |
| `ApplyStep: n değerinde kalan zar yok` | Tur bitince `MoveInputController`'daki kısmi hamle yaşıyordu | `RefreshViews` sıra/faz değişiminde `Reset()`; `CompleteMove` hamleyi kopya durumda doğrular |

Yerleşim sabitleri tek yerde: `Infrastructure/UiLayout.cs` (tahta 1500×938,
oran 1,5991; kenar çubuğu 352, sağ boşluk 20, ayrılan 392). Hem
`Editor/SceneBuilder.cs` hem `Bootstrap/GameBootstrap.cs` bu sabitleri kullanır,
böylece Editör ve oyuncu yerleşimi ayrışamaz.

Kenar çubuğu dikey sırası: `MatchScore` (20) → `Crawford` (118) →
`MatchLength` (158) → `Dice` (236) → `Cube` (360) → `Analysis` (572) →
`Settings` (780) → `ControlBar` (1002).

Doğrulama: `CompileOnly` 0 hata, `BuildScene` 30 288 B, EditMode 7/7,
**PlayMode 8/8** (`LayoutTests` 2 + `InputResetTests` 1 yeni),
`BuildWindows64` `Succeeded (0 hata)`. `LayoutTests` tahta ile her denetimin
dünya koordinatlarındaki kesişimini ölçer; yerleşim ileride bozulursa test
kırmızıya döner.

### 12.5.4 Hamle girişi (taş tıklayınca gitmiyor)

Kullanıcı geri bildirimi: *"AI'ye karşı oyun oynarken zara göre taşları hareket
ettirmiyor. Oynatacağım taşı tıklayınca gideceği alternatifleri doğru gösteriyor,
ancak seçtiğimde taş gitmiyor."*

| Sorun | Kök neden | Çözüm |
|---|---|---|
| Taş hareket etmiyor | `MoveInputController` yasal hamleleri **taban** pozisyondan üretiyor, `TryAddStep` sonrası yeniden üretmiyordu; ikinci tıklama bayat listeye göre doğrulanıp `IsLegal` korumasında sessizce düşüyordu | `_baseState` + `_scratch` alanları ve `Regenerate()`: yasal hamleler **kısmi hamleden sonraki** pozisyondan üretilir |
| Kısmi hamle görünmüyor | `BoardView` yalnızca `GameOrchestrator.State`'i çiziyordu | `BoardInputController.ApplyPreview()`: `State.Clone()` üzerinde kısmi hamleyi uygular, `_model.Update` + `_board.Refresh` |
| İkinci zarın hedefleri kayboluyor | Başarılı `TryAddStep` sonrası `ClearSelection()` çağrılıyordu | Çağrı kaldırıldı; seçim taşın gittiği haneye taşınır |
| Yarım hamle kayboluyor | "Turu bitir" kısmi hamleyi uygulamıyordu | `CommitPartialMove()` eklendi; "Turu bitir" önce onu çağırır. Ayrıca "Geri al" (`UndoStep()`) düğmesi eklendi |
| Kalan zarlar güncellenmiyor | `DiceView` yalnızca tur değişiminde yenileniyordu | `_boardModel.Changed` → `DiceView.Refresh` (abonelik `new BoardViewModel()` **sonrasında**) |

**Yan bulgu:** `BearoffDatabase.IsOneSidedBearoff` rakibin ev bölgesindeki
taşlarını kabul ediyordu. `ToCounts` ev bölgesini `(byte)`'a çevirdiği için
negatif değerler sessizce bozuluyor ve `BearoffIndex.Rank`
`Toplam taş sayısı 15'i aşamaz: 268` istisnası atıyordu (`FullGameTests`
kırmızıya döndü). Rakip ev bölgesi kontrolü eklendi (beyaz için 19–24, siyah
için 1–6); bu aynı zamanda doğru semantiktir — rakip ev bölgesindeyse pozisyon
temastır ve tek taraflı bearoff tablosu geçersizdir. Regresyon testi:
`BearoffTests.BearoffDatabase_RejectsContactPositions`.

Doğrulama: `dotnet build` 0 hata; `Backgammon.Tests` **245/245**,
`Backgammon.Inference.Tests` 57/57, `Backgammon.UI.Tests` **19/19**
(Test 30b yeni), `ml/tests` 20/20; `CompileOnly` 0 hata, `BuildScene` 30 299 B,
EditMode 7/7, **PlayMode 10/10** (`MoveFlowTests` 2 yeni),
`BuildWindows64` `Succeeded (0 hata)`, oyuncu duman testi istisnasız.

### 12.5.5 Oynanış hataları (altı yama)

Kullanıcı geri bildirimi: *"1. rakibin taşını kırdığımda benim taş eksiliyor
(kayboluyor) 2. Rakibin taşı kırılınca kırık hanesinden içeri girmiyor, meçhul.
3. taşları toplarken toplanan taşlar görünmüyor. 4. oyun sonunda skor değişmiyor.
5. rakip hangi zarı attığı görülmüyor. 6. Rakibin ve benim katlama isteklerim
işlemiyor."*

Altı hatanın beşi üç kök nedene indirgenir; altıncısı iki ayrı kusurdur.

| # | Sorun | Kök neden | Çözüm |
|---|---|---|---|
| 1 + 2 | Vurulan rakip taşı **siliniyor**, bara girmiyor | `MoveInputController.TryAddStep` adımı `new MoveStep(from, to, die, MoveFlags.None)` ile yeniden inşa ediyor, `Hit` bayrağını atıyordu. `ApplyStep` rakibin taşını yalnızca `step.IsHit` ise bara gönderir; bayraksız adım `board[To]`'yu sıfırlayıp taşı yok ediyordu | `TryAddStep` artık üretecin verdiği `MoveStep`'i **olduğu gibi** kopyalar (`Hit`/`BearOff`/`FromBar` korunur) |
| 3 | Toplanan taşlar tepside görünmüyor | `TrayView.SetCount` yalnızca etiketi yazıyordu; `BoardView.Refresh()` tepsilere hiç taş yerleştirmiyordu | `BoardView.StackTray(LayoutRect, int, Sprite)` (2 sütunlu ızgara) + `Refresh()` sonunda beyaz/siyah tepsi çağrıları. `CheckerPool` kapasitesi 30 yeterlidir (toplam taş her zaman 15+15) |
| 4 | Oyun sonunda skor değişmiyor | `GameOrchestrator.Refresh()` `_isGameOver`/`_result` yazıyor ama sonucu skora **uygulamıyordu**; puan yalnızca `StartNextGame()` içinde işleniyordu | `BackgammonEngine.StartNextGame` → `ApplyResult` + `PrepareNextGame` olarak ikiye ayrıldı. `GameOrchestrator` `_resultApplied` bayrağıyla `Refresh()` içinde `ApplyResult`'u **anında** çağırır; `StartNextGame()` yalnızca `PrepareNextGame` yapar (tek uygulama) |
| 5 | Rakibin zarları görünmüyor | `EndTurn` `rolledDice`'i sıfırlar; `GameBootstrap.Update` AI için `RollDice()` → `StartAiThink()` → `ApplyMove` → `EndTurn` zincirini **aynı karede** çalıştırıyordu | `DiceView.SetOverride/ClearOverride` (tahtada zar yokken sabitlenen zarları çizer) + `GameBootstrap`'ta `AiRollDisplaySeconds = 0.9f`, `AiDiceTailSeconds = 1.6f`, `_aiRollPending`, `_aiDiceVisibleUntil`, `CaptureAiRoll`, `ShowAiDiceTail`, `UpdateAiDiceOverride` |
| 6a | İnsanın küp teklifi işlemiyor | `CanOffer` `phase == PreRoll` ister; zar atıldığında faz `Moving` olduğu için düğme **sessizce** hiçbir şey yapmıyordu | `BackgammonEngine.RevertRoll(state, in es)` (atılmış ama oynanmamış zarı geri alır) + `GameOrchestrator.TryOfferDouble()` |
| 6b | Rakibin (AI) küp kararı işlemiyor | `EquityCubeAdvisor.Decide` `phase == PreRoll` değilse `ShouldTake = true` döner; `OfferDouble()` fazı `CubeOffered` yaptığı için karar teklif **sonrasında** yanlış hesaplanıyordu | Karar `OfferDouble()`'dan **önce** alınır ve `GameOrchestrator.PendingOpponentTake` içinde saklanır |

**Regresyon testleri.**

| Dosya | Test | Kapsam |
|---|---|---|
| `Backgammon.UI.Tests/GameplayFixTests.cs` | 7 | vuruş bayrağı korunur, vurulan taş bara gider, toplama bayrağı, oyun sonunda anında skor, çift sayım yok, `TryOfferDouble` zarı geri alır, taş oynandıktan sonra reddedilir |
| `Backgammon.Tests/MatchFlowSplitTests.cs` | 16 | `ApplyResult` (puan × küp, mars, maç sonu, para oyunu, Crawford, geçersiz kazanan), `PrepareNextGame` (sıfırla + skoru koru, maç bitti, Crawford), `StartNextGame` (tek uygulama), `RevertRoll` (oynanmamış, çift, oynanmış, `Moving` değil, Crawford) |
| `Assets/Backgammon.UI/Tests/PlayMode/GameplayFixPlayModeTests.cs` | 3 | vurulan taş bara gider + havuzda **30** taş çizilir, toplanan taş tepside çizilir, `DiceView` sabitlemesi |

> **Doğrulama numarası:** havuzdaki görünür taş sayısı her zaman **30** olmalıdır.
> Vurulan taş silinirse veya toplanan taş çizilmezse 29 çıkar.

Doğrulama: `dotnet build` 0 hata; `Backgammon.UI.Tests` **19/19**,
`Backgammon.Tests` **245/245**, `Backgammon.Inference.Tests` 57/57,
`ml/tests` 20/20; `CompileOnly` 0 hata, EditMode 7/7, **PlayMode 13/13**,
`BuildWindows64` `Succeeded (0 hata)`.

### 12.6 Aşama E — Belge birleştirme

* `PHASES.md` §12 (bu bölüm), §6/§7/§8/§9/§11 güncellendi.
* `ARCHITECTURE.md` §43 eklendi.
* `ASSUMPTIONS.md` F5-01…F5-20 eklendi.
* `ml/tests/test_docs_consistency.py` `EXPECTED_COUNTS` güncellendi.
* `Faz 5.md` §9.3 (Unity ölçüm tablosu) dolduruldu.
* `ml/artifacts/stage_e_faz5.md` — ölçüm raporu.

### 12.7 Ölçümler

| Ölçüm | Değer |
|---|---|
| Bearoff DB | 2 496 208 bayt, 54 264 pozisyon, `MaxRolls = 22` |
| Bearoff C# ↔ Python | max \|Δ\| = 7,630E-006, tolerans dışı 0 |
| MET ↔ gnubg | max \|Δ\| = 0,000E+000 (625 hücre) |
| Küp anlaşması (0-ply, 132 poz.) | ikileme %51,52 / alma %61,36 / ikisi %46,21 |
| Küp anlaşması (2-ply, 132 poz.) | ikileme %52,27 / alma %61,36 / ikisi %46,97 |
| Equity korelasyonu (tek kayıt) | −0,0315 (MAE 1,0550) |
| Equity korelasyonu (zar ortalamalı) | +0,1395 (MAE 1,2063) |
| Değer kafası korelasyonu (400 afterstate) | +0,2431 (MAE 0,8014, sapma −0,0850) |
| Değer kafası kalibrasyonu | `gnubg ≈ 0,0874·bizim + 0,1589` |
| Bizim değer aralığı / std | −2,8050…+3,2966 / 1,0320 |
| gnubg değer aralığı / std | −0,8207…+1,6497 / 0,3710 |
| Maç farkındalığı (400 oyun) | 2-away %40,00 vs %39,50; 4-away %39,75 vs %40,00; 5-away %42,25 vs %44,75 |
| Unity EditMode / PlayMode | 7/7 / 5/5 |

### 12.8 Ölçülmüş zayıflık: değer kafası aşırı dağınık

Aşama B'de küp anlaşmasının düşük çıkması üzerine 400 rastgele afterstate, gnubg'nin
`evaluate` fonksiyonuyla **doğrudan** karşılaştırıldı (ön-zar yaklaşımı yok):

* Korelasyon **+0,2431**, MAE **0,8014**, sapma **−0,0850**.
* En küçük kareler kalibrasyonu `gnubg ≈ a·bizim + b` ⇒ **a = 0,0874**, **b = +0,1589**.
* Yani modelin değer kafası **≈11,4 kat aşırı dağınık**: `[-3,3]` aralığını neredeyse
  tamamen kullanıyor, gnubg ise `[-0,82, +1,65]` aralığında kalıyor.
* Kalibrasyon sonrası MAE **0,2897**'ye düşüyor — yani bilgi **var**, ölçek yanlış.

Bu bir **Faz 4 model kalitesi** sorunudur, Aşama B/C uygulama hatası değildir. Küp
kararları eşik tabanlı olduğu için aşırı dağınık değer doğrudan yanlış ikileme/pas
kararına dönüşür. Ayrıntı: `ml/artifacts/stage_b_afterstates.md`.

**Faz 6 önerisi (öncelik sırası):**

1. Değer kafasına kalibrasyon katmanı veya kalibrasyon kaybı ekle; hedef eğim ≈ 1,0.
2. `EquityCubeAdvisor`'a zar ortalamalı değerlendirme seçeneği ekle (ölçülen kazanç:
   korelasyonda 4,4 kat iyileşme).
3. 6 çıktılı kafa (kazanma/mars/arka arkaya mars × iki taraf) ⇒ `output_version = 2`.
4. İki taraflı bearoff veritabanı (≈29,4 GB) — yalnızca gerçekten gerekliyse.

### 12.9 Belgelenen sapmalar (Faz 5)

| # | Spec ne diyor | Ne yapıldı | Neden |
|---|---|---|---|
| 1 | §5.1 `PositionAnalysis` yalnızca `readonly` alanlar | Tam kurucu eklendi | Alanlarla `readonly struct` başlatılamaz |
| 2 | §5.3 `Task<SearchResult>` | `Task<SearchOutcome>` | `SearchResult` bir `ref struct`; `Task<T>` tür argümanı olamaz (CS0306) |
| 3 | `MatchAwareEvaluator` ctor'u `IPolicyValueEvaluator` ister | `internal PolicyValueAdapter` eklendi | `BearoffAwareEvaluator` `IPolicyValueEvaluator` uygulamıyor |
| 4 | §5.4 arama iptal edilebilir | İptal yalnızca arama **başlamadan** etkili | `BackgammonSearch`'te iptal kancası yok; §0 kural 2 eklemeyi yasaklıyor |
| 5 | §6.2 `Backgammon.UI.Tests` için xUnit | NUnit 4.3.2 | Depo standardı NUnit |
| 6 | §6.8 `LegalTargets(fromPoint)` | `LegalTargetsFrom(int)` eklendi; "seçim yok" işareti `0` → `-1` | `0` beyaz barın indeksidir, "seçim yok" anlamına gelemez |
| 7 | §5.3 arama arka plan iş parçacığında | Unity'de `Think()` (çağıran iş parçacığı) | `OrtIoBinding` iş parçacığı güvenli değil (§12.5) |
| 8 | §6.2 Unity testleri `dotnet test` kapsamında | Ayrı Unity koşusu | Unity testleri Unity Editor gerektirir |

### 12.5.6 İkinci oynanış turu (altı yama)

Kullanıcı geri bildirimi: *"1. money game haricindeki çok sayılı oyunu seçince
oyun bitiminde skor değişmiyor. 2. ai katlama teklif ettiğinde çarpan 1 gözüküyor.
Kabul etsem de etmesem de değişen olmuyor. 3. Seçeneklerde renk seçimi de olmalı.
default beyaz olmalı. 4. eğer atılan zar bloke ise sıranın karşı tarafa geçmesi
gerekiyor. 5. ilk başlangıçta yüksek zar atan başlamalı önce. 6. Oyuncu hangi
rengi seçerse seçsin, taşları toplama alanı sağ altta olmalı."*

| # | Sorun | Kök neden | Çözüm |
|---|---|---|---|
| 1 | Çok sayılı maçta oyun bitince skor değişmiyor | "Yeni oyun" düğmesi `BackgammonEngine.NewGame()` çağırıyordu; bu `BackgammonState.Reset()` üzerinden `whiteScore`/`blackScore` alanlarını **sıfırlıyordu**. §12.5.5/4'te eklenen anında `ApplyResult` doğru çalışıyordu ama skor hemen ardından siliniyordu | `GameOrchestrator.NewGame()` artık maç bitmemişse `BackgammonEngine.PrepareNextGame()` (skoru, `matchLength`, Crawford bayraklarını korur), maç bittiyse `NewMatch(matchLength, EnableJacoby)` çağırır |
| 2a | AI küp teklifinde "Kabul"/"Ret" düğmeleri ölü | `CubeView.Initialize()` `Accepted`/`Declined` delegelerini **değer olarak** `CreateButton`'a geçiriyordu; `GameBootstrap` bu olaylara `Initialize()`'dan **sonra** abone olduğu için düğmeler kalıcı olarak `null` delegesi tutuyordu | `RaiseAccepted()`/`RaiseDeclined()` örnek metotları eklendi; olay tıklama anında okunur (`MatchLengthView.Raise` ile aynı desen) |
| 2b | Teklif sırasında küp "1" gösteriyor | `BackgammonEngine.OfferDouble` yalnızca `phase = CubeOffered` yapar; `cubeValue` **`Take` anına kadar değişmez**. `CubeViewModel.Value` bu yüzden teklif sırasında eski değeri veriyordu | `CubeViewModel.DisplayValue` eklendi: `Visibility == Offered ? Value * 2 : Value`. `CubeView` değer ve "teklif: N" etiketlerinde bunu kullanır |
| 3 | Renk seçimi yok | `SettingsPanelView` yalnızca zorluk/ipucu/kup sunuyordu; `GameBootstrap.HumanPlayer`/`AiPlayer` `const sbyte` idi | `SettingsPanelView.ColorKey`/`PlayerColor`/`ToggleColor()` (varsayılan **Beyaz**, `PlayerPrefs`), `GameBootstrap.HumanPlayer`/`AiPlayer` örnek özellik, `ApplyPlayerColor()` |
| 4 | Bloke zarda sıra geçmiyor | `BackgammonEngine.PassTurn()` vardı ama hiçbir yerden çağrılmıyordu; `Moving` fazında yasal hamle yoksa akış kilitleniyordu | `GameOrchestrator.HasLegalMoves` eklendi; `GameBootstrap.Update()` `BlockedPassSeconds` (1,2 sn) bekledikten sonra `EndTurn()` çağırır ve `DiceView.SetCaption("hamle yok - sira geciyor")` gösterir |
| 5 | Açılışta yüksek zar atan başlamıyor gibi | `RollOpening` zaten `d1 > d2 ? 1 : -1` ile yüksek zarı seçiyordu. Gerçek sorun: AI açılışı kazandığında `RollDice()` → `StartAiThink()` → `ApplyMove()` → `EndTurn()` **aynı karede** çalıştığı için açılış zarları hiç görünmüyordu | `GameBootstrap.AnnounceOpeningRoll()` + `_openingRollPending` / `OpeningRollSeconds` (1,6 sn) beklemesi; `DiceView.SetCaption("acilis d1-d2 - sen basliyorsun|rakip basliyor")` |
| 6 | Toplama alanı renge göre yukarıda kalıyor | `BoardLayout` `WhiteTray` alt / `BlackTray` üst olarak sabitti; siyah oynayan insanın tepsi sağ **üstte** kalıyordu | `BoardLayout.Calculate(w, h, bool flipVertical)` eklendi (satırlar ve tepsiler dikey aynalanır, nokta kümeleri ayrık kalır); `BoardView.FlipVertical` özelliği `Recalculate()`'ı geçersiz kılar ve bar yarılarını takas eder |

**Regresyon testleri.**

| Dosya | Test | Kapsam |
|---|---|---|
| `Backgammon.UI.Tests/GameplayFix2Tests.cs` | 9 | `NewGame` maç skorunu korur, maç bittiğinde yeni maç başlatır, `DisplayValue` teklifte 2 / `Take` sonrası 2, varsayılan yerleşimde beyaz tepsi sağ altta, çevrilmiş yerleşimde siyah tepsi sağ altta, çevirme nokta kümelerini ayrık tutar, `HasLegalMoves` bloke konumda `false` / açılışta `true` |
| `Assets/Backgammon.UI/Tests/PlayMode/GameplayFix2PlayModeTests.cs` | 4 | teklifte küp etiketi "2" + iki düğme görünür, **Kabul/Ret düğmeleri olayı tetikler** (ölü düğme regresyonu), renk değişimi tahtayı çevirir ve kendi tepsi sağ altta kalır, bloke zarda sıra otomatik geçer |

> **Doğrulama numarası:** `Backgammon.UI.Tests` **19 → 28**, Unity PlayMode **13 → 17**.
> `ml/tests/test_docs_consistency.py` `EXPECTED_COUNTS["ui"]` 28 olmalıdır.

Doğrulama: `dotnet build` 0 hata; `Backgammon.UI.Tests` **28/28**,
`Backgammon.Tests` **245/245**, `Backgammon.Inference.Tests` 57/57,
`ml/tests` 194/194 + belge tutarlılığı 21/21; `CompileOnly` 0 hata,
EditMode 7/7, **PlayMode 17/17**, `BuildWindows64` `Succeeded (0 hata)`,
player duman testi temiz.

## 13. Faz 6 — Aşama A: ölçüm hattı ve taban kilidi

Faz 6'nın ilk aşaması **güç değil, ölçüm** aşamasıdır: bundan sonraki her iyileştirme
tek bir dondurulmuş referans küme üzerinde, aynı gnubg sürümüyle, aynı ply'de
ölçülecektir. Aşama A bu sözleşmeyi kurar.

### 13.1 Teslim edilenler

| Dosya | İçerik |
|---|---|
| `ml/er_harness.py` | Yeniden üretilebilir ER ölçüm hattı. `ml/gnubg_er.py`'yi **olduğu gibi** kullanır (tek doğruluk kaynağı); yeni vektörleştirici yazmaz |
| `ml/artifacts/reference_corpus_v1.json` | Dondurulmuş **200** pozisyonluk referans küme (tohum `20261114`, SHA-256 `ad85265177515b41fb5e95b3904c231966ececd6928db178be0d84473469d072`) |
| `ml/artifacts/model_stage_d_v10.onnx` | Faz 5 taban modeli (0,1941 ER'i üreten ağ), yeniden üretim için depoya işlendi |
| `ml/artifacts/stage_f_baseline.md` | Üretilen taban raporu (Test 41a–48) |
| `ml/tests/test_er_harness.py` | 12 test (41a–48) |

### 13.2 Referans küme

Küme beş fazı kapsar ve her fazdan en az 20 pozisyon içerir (Test 45):

| Faz | Pozisyon |
|---|---|
| temas (`contact`) | 39 |
| yarış (`race`) | 40 |
| bearoff (`bearoff`) | 37 |
| bar (`bar`) | 40 |
| kapalı tahta (`closed`) | 44 |

Rastgele oyun `race`, `bearoff` ve özellikle `closed` fazlarını neredeyse hiç üretmediği
için bu üç faz **parametrik ailelerle** kurulur (`_race_positions`, `_bearoff_positions`,
`_closed_positions`); `contact` ve `bar` tohumlu rastgele oyundan gelir. Küme
`(tahta)` düzeyinde tekilleştirilir: aynı tahta iki kez sayılmaz.

Bölünme faz katmanlı ve deterministiktir: **CAL 60 / VAL-ER 70 / TEST-ER 70**. Üç küme
ayrıktır ve tahta paylaşmaz (Kural 10, Test 44). Model seçimi yalnız VAL-ER üzerinden
yapılır; TEST-ER'e erişim `ml/runs/<ad>/test_access.log` dosyasına yazılır.

### 13.3 Ölçülen taban

| Ölçüm | Değer |
|---|---|
| 41a — Faz 5 değerinin yeniden üretimi (50 pozisyon) | **0,1941** (fark 0,0000; tolerans ±0,01) ✅ |
| 41b — 200 pozisyon ortalama ER | **0,2203** (medyan 0,1325, maks 1,6770, eşleşme %14,0) |
| 41b — CAL / VAL-ER / TEST-ER | 0,3013 / 0,1898 / 0,1820 |
| 46 — standart hata (200 pozisyon) | 0,0187; hedef SE 0,005 için gereken n ≈ 2 786 |
| 41e — veri hacmi (100 oyun, 9 088 karar) | **3 824 bayt/karar** ham, **129 bayt/karar** gzip |
| 41c — `OutcomeDistribution` kodlaması | **kümülatif** (`Win` = P(en az tek), `Lose = 1 − Win`) |
| 41d — `resultType` `winner` içeriyor mu | **hayır** (yalnız çarpan: 1/2/3) |
| 48 — gnubg | `GNU Backgammon 1.08.003-mingw 32-Bit 20240428`, 2-ply, cubeless, money |

> **Dürüst not:** 200 pozisyonluk kümede standart hata 0,0187'dir. Yani 0,01–0,02 ER
> hedefi bu kümeyle **ölçülemez**; Test 46'nın çıktısı (n ≈ 2 786) Faz 6'nın ilerleyen
> aşamalarında referans kümenin büyütülmesi gerektiğini söyler. Bu bir kusur değil,
> ölçümün kendi sınırını önceden bildirmesidir.

### 13.4 Yeniden üretim

```bash
python ml/er_harness.py build-corpus          # kümeyi yeniden üret (deterministik)
python ml/er_harness.py verify-corpus         # özet + faz + bölünme denetimi
python ml/er_harness.py legacy --model ml/artifacts/model_stage_d_v10.onnx --limit 50
python ml/er_harness.py measure --model ml/artifacts/model_stage_d_v10.onnx --split all
python ml/er_harness.py data-volume --shards ml/runs/stage_d/shards/it10
python ml/er_harness.py baseline --model ml/artifacts/model_stage_d_v10.onnx --shards ml/runs/stage_d/shards/it10
```

gnubg yoksa hat sıfır olmayan çıkış kodu döner ve **hiçbir sayı üretmez** (Test 43).
## 14. Faz 6 — Aşama B: 6 çıktılı değer kafası ve kalibrasyon

Aşama A **ölçtü**; Aşama B **değer kafasını değiştirir**. Faz 5'in tek skaler değer
kafası, oyun sonucunun *büyüklüğünü* (mars/backgammon payını) temsil edemiyordu. Bu
aşama kafayı **dışlayıcı 6 sınıfa** çevirir, `output_version = 2` ONNX sözleşmesini
kurar ve kalibrasyon teşhisini (D1–D3) ölçer.

### 14.1 Teslim edilenler

| Dosya | İçerik |
|---|---|
| `ml/equity.py` | Dışlayıcı ↔ kümülatif dönüşüm ve equity formülü (C# aynası) |
| `ml/targets.py` | Shard v1 `winner` + `resultType` → 6 sınıflı dışlayıcı hedef |
| `ml/calibration.py` | Kalibrasyon metrikleri, kabul kriterleri, logit sıcaklık ölçekleme |
| `ml/diagnose.py` | D1/D2/D3 teşhis hattı ve rapor üreteci |
| `ml/losses.py` | `value_loss_ce_6class`, `calibration_loss`, `total_loss_v2` |
| `ml/gen_test_models.py` | C# ONNX fikstürlerini yeniden üretir |
| `ml/artifacts/model_output_version_2.onnx` | Gerçek v2 grafiği (parite 5,96e-08) |
| `ml/artifacts/stage_f_diagnosis.md` | Üretilen D1–D3 raporu |
| `Backgammon.Tests/OutcomeDistributionV2Tests.cs` | Test 49–52 |
| `Backgammon.Inference.Tests/OutputVersion2Tests.cs` | Test 54, 57, 58 |
| `ml/tests/test_stage_b.py` | Test 53, 55, 56 |

### 14.2 Dışlayıcı 6 sınıf

Ağ çıktısı **dışlayıcı** altı sınıftır ve toplamı 1'dir:

| Sıra | Sınıf | Anlam | Equity ağırlığı |
|---|---|---|---|
| 0 | `W` | kazanır, tek | +1 |
| 1 | `GW` | kazanır, mars | +2 |
| 2 | `BW` | kazanır, backgammon | +3 |
| 3 | `L` | kaybeder, tek | −1 |
| 4 | `GL` | kaybeder, mars | −2 |
| 5 | `BL` | kaybeder, backgammon | −3 |

`E = W + 2·GW + 3·BW − (L + 2·GL + 3·BL) ∈ [−3, +3]`.

`OutcomeDistribution` sınıfı **kümülatif** kodlamayı korur (Faz 5 §4.3, gnubg geleneği);
`FromProbabilities` dışlayıcı girdiyi kümülatife çevirir:

```
Win = W+GW+BW,  WinGammon = GW+BW,  WinBackgammon = BW
LoseGammon = GL+BL,  LoseBackgammon = BL,  Lose = 1 − Win
```

İki equity ifadesi cebirsel olarak **aynıdır**; Test 49/53 bunu sayısal olarak doğrular.
`FromProbabilities` **monotonluk zorlamaz** (dışlayıcı sınıflar arasında `W ≥ GW ≥ BW`
gibi bir zorunluluk yoktur) ve geçersiz girdide `IsValid = false` döner.

### 14.3 `output_version = 2` ONNX sözleşmesi

| Alan | v1 | v2 |
|---|---|---|
| Girdi | `features [batch,221]` | `features [batch,221]` |
| Çıktı | `value [batch,1]`, `policy_logit [batch,1]` | `probs [batch,6]`, `policy_logit [batch,1]` |
| `output_version` metadata | `1` | `2` |
| `prob_order` metadata | — | `W,GW,BW,L,GL,BL` |
| `prob_encoding` metadata | — | `exclusive` |

`OnnxModelHandle.SupportedOutputVersion` **2**'dir. `output_version = 1` modeller
**bit düzeyinde aynı** çalışmaya devam eder (Test 58); `output_version = 3` reddedilir.
`prob_order`/`prob_encoding` metadata'sı **sürüm kontrolünden önce** doğrulanır: sıra
yazılı değilse handle modeli yanlış yorumlayabilir ve bu sessiz bir hatadır (F6-10).

### 14.4 Kalibrasyon teşhisi (D1–D3)

983 oyun, 300 adım sabit bütçe, tohum `20261114`, CAL 100 / VAL 100 oyun.

| Teşhis | Ölçüm | Karar |
|---|---|---|
| **D1** — eğitim ölçeği | MAE 1,2327 (125 oyun) → 0,8487 (250) → 0,8052 (500); eğim 0,6208 → 0,9190 → 0,9851 | **işaretli** — eğri hâlâ iniyor, sorun ölçek |
| **D2** — hedef tanımı | `λ=1.0` MAE 0,9734 / eğim 1,0424 vs `λ=0.7` MAE 0,9707 / eğim 1,0490 | işaretli değil (fark %0,3, gürültü) |
| **D3** — kafa yapısı | 6 çıktılı MAE 0,9362 vs skaler 0,9734 (**%3,8** iyileşme) | **işaretli** |

Yükseltme sırası (Faz 6 §6.2) bu ölçüme göre uygulanır: **6 çıktılı kafa** → `L_cal`
(`c_cal = 0,1`) → logit sıcaklık (tek `T`) → isotonic (son çare).

> **Dürüst not.** D1'in 5 000 / 10 000 noktaları mevcut 983 oyunla **ölçülemez**;
> ölçülebilen en büyük nokta raporlanmıştır. Daha büyük ölçek Aşama C'de yeni self-play
> verisiyle ölçülmelidir. Eğitim bütçesi sabit ve küçüktür: bu rapor **kıyas** içindir,
> mutlak başarı iddiası taşımaz.

### 14.5 Bulunan kritik hata: `terminal_value` işaret hatası (F6-07)

D2 teşhisi yazılırken iki hedef kurucusu karşılaştırıldı ve **Faz 4'ten beri var olan**
bir hata bulundu: `ml/replay.py::terminal_value`, `z`'yi `winner` ile çarpıyordu. Oysa
`td_lambda_targets` işareti her adımda zaten çevirir:

```
y[T-1] = -z
y[t]   = -((1-λ)·V[t+1] + λ·y[t+1])
```

Son karar veren oyuncu **kazanandır** (ölçüldü: 200/200 oyunda `last mover == winner`),
yani `y[T-2]` kaybedenin bakış açısıdır ve `-z` olmalıdır. `winner = -1` (siyah kazanır)
durumunda işaret **iki kez** çevriliyor ve o oyunun tüm hedefleri ters yazılıyordu.

**Ölçüm.** 87 628 örneğin **43 986**'sı (%50,2) yanlıştı; ilk örnekler tam olarak
`[-3,+3,-3,+3,…]` ↔ `[+3,-3,+3,-3,…]` biçiminde işaret terstine dönüyordu. %50,2 oranı,
oyunların yarısını siyahın kazanmasıyla birebir uyuşur.

**Etki.** Düzeltmeden önce D2 `λ=1.0` için eğim **−0,2270**, korelasyon **−0,0305**
veriyordu (anlamsız); düzeltmeden sonra eğim **1,0424**, korelasyon **0,7757**.
Eğitilmemiş v1 modeli ile gerçek equity arasındaki korelasyon **−0,2167**, işareti
çevrilmiş equity ile **+0,2167** — ağ "kazanma" yönünü sistematik olarak ters öğrenmiş
durumda. **Faz 4/5 kontrol noktaları geçersizdir** (F6-12); Aşama C sıfırdan eğitir.

### 14.6 Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 49 | `OutcomeDistribution_EquityFormula_Exclusive` | C# | ✅ |
| 50 | `OutcomeDistribution_IsAntisymmetric` | C# | ✅ |
| 51 | `OutcomeDistribution_FromProbabilities_Normalizes` | C# | ✅ |
| 52 | `OutcomeDistribution_FromProbabilities_NoMonotonicityForcing` | C# | ✅ |
| 53 | `EquityFormula_PythonMatchesCSharp` | pytest | ✅ |
| 54 | `Onnx_OutputVersion2_IsAccepted` | C# | ✅ |
| 55 | `CalibrationLoss_ImprovesSlope` | pytest | ✅ |
| 56 | `LogitTemperatureScaling_UsesCalOnly` | pytest | ✅ |
| 57 | `Onnx_OutputVersion2_ZeroAllocation` | C# | ✅ |
| 58 | `Onnx_OutputVersion1_StillWorks` | C# | ✅ |
| 59 | `Export_OutputVersion2_Parity` | pytest | ✅ |

### 14.7 Yeniden üretim

```bash
python ml/gen_test_models.py                                   # C# ONNX fikstürleri
python ml/export_onnx.py --output-version 2 --profile medium \
    --out ml/artifacts/model_output_version_2.onnx             # v2 grafiği + parite
python ml/diagnose.py --steps 300                              # D1-D3 raporu
python -m pytest ml/tests/test_stage_b.py -q                   # Test 53, 55, 56
dotnet test TavlaAI_Project.slnx --filter "OutcomeDistributionV2Tests|OutputVersion2Tests"
```

---

## 15. Faz 6 — Aşama C: veri motoru

Aşama B **kafayı** düzeltti; Aşama C **veriyi** düzeltir. Faz 4/5 kontrol noktaları
işaret hatası nedeniyle geçersizdir (F6-12), yani eğitim verisinin sıfırdan ve
**tekrarlanabilir** biçimde üretilmesi gerekir. Bu aşama paralel determinizmi kurar,
`dup_cap` tekrar ayıklamasını ekler, shard v1'in değişmediğini kanıtlar ve veri hacmini
ölçer.

### 15.1 Teslim edilenler

| Dosya | İçerik |
|---|---|
| `Backgammon.SelfPlay/DupCapFilter.cs` | Oyun sonrası deterministik tekrar ayıklama + `DupCapStats` |
| `Backgammon.SelfPlay/Program.cs` | Oyun başına tohum (`seed(gameIndex) = baseSeed + gameIndex`), `dup_cap` geçişi, tepe bellek/disk hızı raporu |
| `Backgammon.SelfPlay/SelfPlayRunner.cs` | `ResetSeed(ulong)` — iş parçacığından bağımsız oyun tohumu |
| `Backgammon.SelfPlay/SelfPlayConfig.cs` | `DupCap` (varsayılan 3, 0 = kapalı) |
| `Backgammon.SelfPlay/CommandLine.cs` | `--dup-cap <n>` |
| `Backgammon.SelfPlay/ShardFormat.cs` | `ShardDecisionFlags.DupCapped = 8` (eklemeli; `formatVersion` 1 kalır) |
| `ml/shards.py` | `DEC_DUP_CAPPED`, `DecisionRecord.is_dup_capped` |
| `Backgammon.Inference.Tests/StageCDataEngineTests.cs` | Test 60, 61, 62, 65, 66 |
| `ml/tests/test_stage_c.py` | Test 63, 64, 65, 67 |

### 15.2 Paralel determinizm (Test 60)

Faz 4'ün şeması **iş parçacığına bağlıydı**: `threadSeed = seed + threadIndex·salt` ve
her iş parçacığı tek bir RNG'yi oyunlar arasında sırayla tüketiyordu. Bu, `--threads N`
çıktısını `--threads 1`'den farklı yapıyordu — yani veri **yeniden üretilemezdi**.

Yeni şema:

```
seed(gameIndex) = baseSeed + gameIndex          (iş parçacığından bağımsız)
havuz kararı    = Xoshiro256StarStar(seed ^ salt)  (ayrı RNG; oyun akışını etkilemez)
```

`SelfPlayRunner.ResetSeed(seed)` her oyundan önce çağrılır. Sonuç: `--threads 4` çıktısı
`--threads 1` çıktısıyla **birebir aynıdır** (Test 60 bunu doğrudan `Program.Main`
üzerinden, shard dosyalarının SHA'sını karşılaştırarak doğrular).

> **Uyarı.** Bu değişiklik eski shard'ların yeniden üretilebilirliğini **bozar**:
> `ml/runs/stage_d/shards` eski şemayla üretildi. Biçim değişmediği için hâlâ
> **okunabilir** (Test 63), ama aynı tohumla yeniden üretilemez. Bu beklenen ve kabul
> edilen bir sonuçtur (F6-13).

### 15.3 `dup_cap` (Test 62, 66)

Aynı afterstate'in tekrar tekrar eğitilmesi veri hacmini şişirir. `dup_cap` (varsayılan
**3**) aynı parmak izine sahip kararın en fazla 3 kez eğitime girmesini sağlar.

| Tasarım kararı | Gerekçe |
|---|---|
| **Oyun sonrası** tek geçiş | Tekrar sayacı global durumdur; iş parçacıklarına dağıtılırsa Test 60 kırılır |
| `GameId` sırasına göre | İş parçacığı sayısı ve tamamlanma sırası sonucu değiştirmez |
| Parmak izi = `chosenVector` üzerinde FNV-1a 64 | Shard v1 karar öncesi Zobrist hash'i saklamaz; biçim değişmez |
| Karar **silinmez**, `IsLearner` temizlenir | TD(λ) zinciri tüm kararların `chosenVector`'üne ihtiyaç duyar |
| İlk **10 ply** muaf | Açılış çeşitliliği yok olmasın (Test 62) |

Elenen karar `DupCapped` bayrağı alır, `Q`/`PolicyTargetCs`/`CandidateVectors` atılır;
`chosenVector` korunur. Ölçüm (200 oyun, `--dup-cap 1`): 15 603 açılış-dışı öğrenen
kararın **23**'ü (%0,15) elendi — gerçek self-play'de tekrar nadirdir, `dup_cap` bir
güvenlik ağıdır.

**Açılış çeşitliliği (Test 62).** 200 oyun, `T = 0,05`, 10 keşif ply'i: açılış
afterstate dağılımının entropisi **6,5479 bit** (üst sınır `log2(200) = 7,64`).
`dup_cap = 1` ile açılış kararlarının sayısı **değişmez** (200/200).

### 15.4 Shard v1 değişmedi (Test 63, 65)

`formatVersion` **1** kalır, `vectorSize` **221** kalır, `SHARD_FORMAT.md` §1–§4 aynıdır.
Tek ekleme `ShardDecisionFlags` bit3 (`DupCapped = 8`) — eklemeli, geriye uyumlu.

`finalProbs`/`outcomeProbs` alanları **yoktur ve olmayacaktır** (Faz 6 §7.1): 6 sınıflı
hedef `winner` + `resultType`'tan **türetilir** (`ml/targets.py`). Test 65 bunu iki
tarafta da doğrular (C#: yansıma ile alan yokluğu; Python: `hasattr` + türetme).

Test 63, Faz 4'te C# tarafından yazılmış `ml/artifacts/csharp_shard.bgsp` dosyasını ve
`ml/runs/stage_d/shards` altındaki 10 üretim shard'ını okur; her oyun için
`winner`/`resultType` geçerliliğini ve türetilen hedefin tek-sıcak olduğunu doğrular.

### 15.5 Linux yayını (Test 64)

`dotnet publish -r linux-x64 --self-contained true` **başarılı**; çıktı ELF ikilisi
(`\x7fELF`). Bu makinede **WSL yok** (`wsl -l -v` → dağıtım yok) ve **Docker yok**, bu
yüzden *çalıştırma* adımı atlanır ve gerekçe test çıktısına yazılır (F6-15). Yayın ve
ELF doğrulaması her koşuda yapılır — test sessizce geçmez.

### 15.6 Yürütme sağlayıcısı: CPU vs CUDA (Test 61)

Faz 6 v3 §12.3 "CUDA ≥ CPU" varsayıyordu. **Ölçüm bu varsayımı çürüttü.** CUDA
sağlayıcısı bu makinede gerçekten yüklendi (doğrulama: `torch\lib` `PATH`'te değilken
`cublasLt64_12.dll` eksik hatası alınır; eklendiğinde oturum açılır) ve yine de CPU
kazandı:

| Ölçüm | CPU | CUDA | CUDA/CPU |
|---|---|---|---|
| Test 61, 20 oyun, `depth 0`, ısınmalı | **119,26 oyun/sn** | 29,11 oyun/sn | 0,24× |
| CLI, 60 oyun, `depth 0`, `log-top 4` | **85,91 oyun/sn** | 24,68 oyun/sn | 0,29× |
| CLI, `depth 1`, `max 4/4` | **1,52 oyun/sn** | 0,25 oyun/sn | 0,16× |
| CLI, `depth 2`, `max 4/4` | **0,03 oyun/sn** | < 0,01 oyun/sn | < 0,3× |

Tepe bellek: CPU 87 MB, CUDA 381 MB. **Karar: CPU**
(`SelfPlayConfig.DefaultUseCuda = false`). Ayrıntı ve yeniden üretim:
`ml/artifacts/stage_c_gpu_decision.md`.

**Neden.** Model ~156 bin parametre; bir forward geçişi CPU'da ~1 µs, GPU çekirdek
başlatma gecikmesi tek başına 20–50 µs. `depth 0`'da kova 32–64 satıra yuvarlanır, yani
hesap başlatma maliyetinin altında kalır. Derinlik arttıkça arama ağacı C# tarafında
CPU'da gezildiği için fark **büyür**. İş parçacıkları arası kova birleştirme (v3 §7.3)
uygulanırsa kova 2048'e çıkar ve GPU kazanabilir — bu ayrı bir deneydir.

> **Ölçüm tuzağı (düzeltildi).** Isınma geçişi olmadan 6 oyunla yapılan ilk ölçümde CUDA
> 1,47× *hızlı* göründü. Sebep ölçüm hatasıydı: CPU soğuk (JIT + ONNX oturumu + dosya ön
> belleği), CUDA sıcak koşuyordu. Test 61 artık ısınma geçişi yapar, 20 oyun ölçer ve
> CPU'yu iki kez (CUDA'dan önce ve sonra) ölçüp büyüğünü alır.

Test 61 artık "CUDA kazanmalı" demiyor; **ölçülen kazananın seçili olmasını** ister
(`SelfPlayConfig.DefaultUseCuda` ile karşılaştırır, eşik 1,2×). Başka donanımda CUDA
kazanırsa test kırmızı olur ve sabitin çevrilmesini söyler — sessiz sapma olmaz.
Varsayılan CPU derlemesinde CUDA EP yoktur, test `Inconclusive` olur ve CPU ölçümünü
yazdırır. GPU ölçümü için:

```bash
dotnet build -c Release -p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu
```

Determinizm iddiası **taşınmaz** (Faz 6 §7.3): GPU yolu yalnızca hız içindir.

### 15.7 Veri hacmi ölçümü (Test 67)

60 oyun / koşu, `model_stage_d_v10.onnx`, `depth 0`, `log-top 4`, i7-9750H (6C/12T):

| thread | oyun/sn | tepe bellek (MB) | disk yazma (MB/s) |
|---|---|---|---|
| 1 | 85,70 | 81 | 24,34 |
| 6 | 190,14 | 160 | 54,01 |
| 12 | 209,96 | 254 | 59,64 |

Ölçeklenme: 6 thread **2,22×**, 12 thread **2,45×** (thread 1'e göre; koşudan koşuya ±%10 oynar). Shard boyutu
`log-top 4` ile **~298 KB/oyun** (sıkıştırmasız). `log-top 12` ile ~11,5 KB/karar
(`SHARD_FORMAT.md` §4) → oyun başına ~0,8 MB. 10⁵ oyun ≈ **80 GB**; F: sürücüsünde
427 GB boş alan var, yani sığar. Bu bir **ölçüm**dür, formül iddiası değildir.

> **Dürüst not.** `depth 0` (yalnızca kök) en hızlı ayardır; gerçek eğitim verisi
> `depth 1–2` ile üretilecek ve hız **belirgin biçimde düşecektir**. Yukarıdaki sayılar
> üst sınırdır, üretim hızı değildir.

### 15.8 Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 60 | `SelfPlay_ThreadsAreDeterministic` | C# | ✅ |
| 61 | `SelfPlay_GpuBatching_IsFaster` | C# | ✅ ölçüldü: CPU 4,1× hızlı → CPU seçildi (varsayılan CPU derlemesinde `Inconclusive`) |
| 62 | `SelfPlay_OpeningDiversity` | C# | ✅ |
| 63 | `ShardV1_IsStillReadable` | pytest | ✅ |
| 64 | `SelfPlay_LinuxPublish_Runs` | pytest | ⏭️ yayın ✅, çalıştırma atlandı (WSL/Docker yok) |
| 65 | `Shard_NoOutcomeProbsField` | C# + pytest | ✅ |
| 66 | `DupCap_Works` | C# | ✅ |
| 67 | `SelfPlay_Throughput_IsMeasured` | pytest | ✅ |

### 15.9 Yeniden üretim

```bash
dotnet build Backgammon.SelfPlay -c Release
python -m pytest ml/tests/test_stage_c.py -q                    # Test 63, 64, 65, 67
dotnet test TavlaAI_Project.slnx --filter "StageCDataEngineTests"  # Test 60, 61, 62, 65, 66

# Determinizm elle doğrulama (birebir aynı olmalı)
Backgammon.SelfPlay --model ml/artifacts/model_stage_d_v10.onnx \
	--games 12 --seed 7 --threads 1 --depth 0 --out /tmp/t1 --prefix a --gzip false
Backgammon.SelfPlay --model ml/artifacts/model_stage_d_v10.onnx \
	--games 12 --seed 7 --threads 4 --depth 0 --out /tmp/t4 --prefix a --gzip false
```

---

## 16. Faz 6 — Aşama D: ölçekli eğitim

Aşama B kafayı, Aşama C veriyi düzeltti. Aşama D **eğitimi** düzeltir: 6 çıktılı kafayla
vektör TD(λ) döngüsü, kapasite/AMP kararlarının ölçülmesi, determinizm ve
devam-ettirme garantileri, ve L0/L1/L2/L3 eğitim merdiveni.

**Kabul (v3 §12.4, v3-DÜZELTME satır 802–804).** ER < 0,02 bir **kapı değil, hedeftir**.
Aşama D kabulü: "L1/L2/L3 hedefleri raporlanır; ulaşılan/ulaşılamayan değerler
`ml/artifacts/stage_f_train.md`'ye yazılır; sapma analizi yapılır."

### 16.1 Teslim edilenler

| Dosya | İçerik |
|---|---|
| `ml/train_v2.py` | 6 çıktılı kafayla vektör TD(λ) eğitim döngüsü (~1 230 satır) |
| `ml/tests/test_stage_d.py` | Test 68, 69, 70, 71a, 71b, 72, 73, 74 + 3 birim testi |
| `ml/replay.py` | `non_terminal_vectors` takma adı |
| `ml/gnubg_er.py` | `OnnxScorer` `output_version = 2` desteği |
| `ml/config.yaml` | `train.lam` 0,7 → **1,0** (F6-19) |
| `Backgammon.SelfPlay/ShardWriter.cs` | Toplu float yazımı (F6-21) |
| `ml/tests/conftest.py` | `slow` işaretçisi kaydı |
| `ml/artifacts/stage_f_train.md` | L0/L1/L2/L3 hedef-vs-ulaşılan tablosu + sapma analizi |

### 16.2 Vektör TD(λ): sınıf-yarısı takası (F6-17)

Faz 4'ün skaler zinciri `y[t] = -((1-λ)·V[t+1] + λ·y[t+1])` idi. Altı sınıflı dağılımda
"`-V`"nin karşılığı işaret çevrimi değil, sınıf yarılarının **takasıdır**:

```
flip([W, GW, BW, L, GL, BL]) = [L, GL, BL, W, GW, BW]
y[n-1] = flip(z_terminal)
y[t]   = flip((1-λ)·p̂[t+1] + λ·y[t+1])
```

`flip` bir **involusyondur** (`flip(flip(p)) == p`), bu yüzden `λ = 1,0`'da zincir
`flip^k(z)`'ye indirgenir ve `flip² = id` olduğu için sonuç **tam olarak** oyuncu bakış
açısından tek-sıcak Monte Carlo hedefidir. F6-07'deki işaret hatasının vektör karşılığı
böylece yapısal olarak imkânsız hâle gelir. `λ ≥ 1,0` iken `build_exclusive_samples`
ileri geçişi tamamen atlar (zincir ağa bağlı değildir).

### 16.3 İki probe (F6-19)

| Probe | Hedefler | Ne ölçer |
|---|---|---|
| `probe_value` (TD) | 1. iterasyonun modelinden dondurulmuş | "ilk modelden ne kadar uzaklaştık" |
| `probe_mc` (MC) | `λ = 1,0`, ağdan bağımsız tek-sıcak | gerçek öğrenme eğrisi |

Dondurulmuş TD probe'un hedefleri modelden geldiği için model ilerledikçe **yanıltıcı
biçimde kötüleşir**. Faz 4 bu sorunu `probe_mc` ile çözmüştü; `train_v2.py`'nin ilk
sürümünde bu alan eksikti. Her iki probe `probe.npz` içine yazılır ve `--resume`'da
aynen geri yüklenir (Test 72'nin bit düzeyinde determinizmi buna bağlıdır).

### 16.4 Isınma zorunlu (F6-20)

`medium` profiliyle **eğitilmemiş** ağdan 2 000 oyunluk self-play: **1 584 oyun
(%79,2)** `--max-plies 500` sınırında iptal, 454,8 karar/oyun, 251 MB shard, 8,5 GB
tepe bellek. Isınma sonrası: iptal **0**, 65,7 karar/oyun, 26,9 MB, 1,1 GB. Bu yüzden
`--init-from <ckpt.pt>` (yalnızca ağırlıklar; optimizer/iterasyon taşınmaz, profil aynı
olmak zorunda) kural hâline getirildi.

### 16.5 `ShardWriter` toplu float yazımı (F6-21)

`WriteFloats` float başına **4 × `WriteByte`** yerine tek bir `byte[]` doldurup **tek
`Stream.Write`** yapar; `WriteFile` çıktıyı 64 KB `BufferedStream` ile sarar. 2 000
oyunluk shard: **>7 dk / 8,5 GB** → **12,7 s / 1,1 GB**. Bayt çıktısı değişmedi, yani
Test 60'ın bit düzeyinde determinizm iddiası korunur.

### 16.6 Ölçülen eğitim merdiveni

| Koşu | Profil | Oyun/iter | İter | Süre | Hedef ER | VAL-ER | TEST-ER | Durum |
|---|---|---|---|---|---|---|---|---|
| L0 | `small` | 500 | 20 | 34,4 dk | — (harness) | 0,1550 | **0,1429** | ✅ |
| L1 | `medium` | 2 000 | 30 | 61,0 dk | < 0,10 | 0,0658 | **0,0708** | ✅ |
| L2 | `medium` | 10 000 | 30 | 196,0 dk | < 0,05 | 0,0619 | **0,0490** | ⚠️ |
| L3 | `medium` | 100 000 | 50 | ~40 sa (tahmin) | < 0,02 | — | — | ⏭️ |
| Faz 5 taban | — | — | — | — | — | — | 0,1941 | — |

**Toplam iyileşme (L2 vs Faz 5):** 0,1941 → 0,0490 = **3,96×** (TEST-ER); VAL-ER
üzerinden 0,1941 → 0,0619 = **3,14×**. L2'nin TEST-ER'i < 0,05 hedefinin altındadır,
ancak VAL-ER kazancı **anlamsızdır**: L1 0,0658 → L2 0,0619, fark 0,0039, 40
pozisyonun standart hatası 0,016–0,020. Yani oyun/iterasyonu **5×** artırmak ER'de
**ölçülebilir** bir kazanç üretmedi; ER ~0,06–0,07 bandında **plato** yaptı.
Darboğaz kapasite değil (Test 68 `medium`'u seçti), **öğretmen kalitesi**dir
(`depth 0` self-play) ve **ölçüm çözünürlüğü**dür. Ayrıntı ve sapma analizi:
`ml/artifacts/stage_f_train.md`.

### 16.7 Kapasite ve AMP kararları (Test 68, 70)

| Karar | Ölçüm | Sonuç |
|---|---|---|
| Kapasite | `medium` ER 0,3535 ± 0,0712 vs `large` 0,2651 ± 0,0594; fark 0,0884 < eşik 0,0927 | **`medium`** |
| AMP | FP32 2,61 s vs AMP 16,19 s (0,16×); ΔCE 0,00085 | **FP32** |

AMP CPU'da **6,2× yavaş**: `torch.autocast` `bfloat16`'ya düşer ve i7-9750H (Coffee
Lake) AVX-512 BF16 desteklemez. GPU'da (SM ≥ 8.0) yeniden ölçülmelidir; `decide_amp`
bunu otomatik yapar.

### 16.8 Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 68 | `Capacity_Gain_IsMeasured` | pytest | ✅ `medium` seçildi |
| 69 | `TrackH_H0_Parity` | pytest | ⏭️ Ek A kapısı açılmadı (F6-18) |
| 70 | `Amp_IsMeasured` | pytest | ✅ FP32 seçildi |
| 71a | `Training_IsReproducible_CPU` | pytest | ✅ bit düzeyinde aynı `metrics.jsonl` |
| 71b | `Training_IsReproducible_GPU` | pytest | ✅ tolerans içinde (CUDA varsa) |
| 72 | `Checkpoint_Resume_IsExact` | pytest | ✅ kesintisiz koşuyla aynı |
| 73 | `BestModel_SelectedByValEr` | pytest | ✅ |
| 74 | `TestAccess_IsLogged` | pytest | ✅ 2. erişim `exploratory` |

### 16.9 Yeniden üretim

```bash
python -m pytest ml/tests/test_stage_d.py -q

# L0 — harness dogrulamasi (34 dk)
python ml/train_v2.py --out ml/runs/stage_d_l0 --profile small \
	--iterations 20 --games 500 --steps 200 --depth 0 --device cpu --seed 1 \
	--val-er-every 5 --val-er-cases 20 --test-er --test-er-cases 20

# L1 — isitmali medium (61 dk)
python ml/train_v2.py --out ml/runs/stage_d_l1 --profile medium \
	--iterations 30 --games 2000 --steps 300 --depth 0 --device cpu --seed 7 \
	--selfplay-threads 4 --buffer-games 12000 \
	--init-from ml/runs/stage_d_boot/checkpoints/ckpt_v3.pt \
	--val-er-every 5 --val-er-cases 40 --test-er --test-er-cases 40
```

---

## 17. Faz 6 — Aşama E: arama gücü

**Kaynak:** `Faz 6 v3.md` §9 (Arama Gücü), §12.5 (Test 75–82), §13.4 (Performans).
**Rapor:** `ml/artifacts/stage_e_search.md`.

### 17.1 Amaç ve değişmez kural

Aşama E'nin tek amacı **hız**tır; güç değil. v3 §9.5'in değişmez kuralı: *her optimizasyon
`Reference(depth)` ile birebir aynı sonucu vermelidir; fark varsa bu optimizasyon değil hatadır.*
Bu yüzden Aşama E'de hiçbir sezgisel budama, hiçbir yaklaşık değer, hiçbir "iyileştirme" kabul
edilmedi — yalnızca **sonucu kanıtlanabilir biçimde değiştirmeyen** iki mekanizma eklendi.

### 17.2 Eklenen iki mekanizma

| Mekanizma | Ayar | Varsayılan | Sonucu değiştirir mi? |
|---|---|---|---|
| Transposition table | `SearchSettings.TranspositionCapacity` | **0 (kapalı)** | Hayır — yalnızca EXACT girişler |
| Bearoff kesmesi | `SearchSettings.UseBearoffCutoff` | **false** | Hayır — kesin değer sabit noktadır |

**TT anahtarı** `s.hash ^ (depth · sabit) ^ (kalan zar maskesi · sabit)`. Zar maskesi zorunludur:
`Zobrist` tabloları zar içermez, dolayısıyla aynı tahtaya farklı kalan zarlarla ulaşan iki düğüm
aynı hash'i üretir; maske olmadan TT yanlış değer döndürürdü.

**Yalnızca EXACT.** `LOWER`/`UPPER` bayrakları biçim olarak ayrıldı ama kesme için kullanılmadı.
`ChanceNode` 21 zar üzerinden ağırlıklı ortalama aldığı için bir sınır değerin ortalamaya girmesi
ortalamayı da sınır yapar; sınırların yukarı propagasyonu bu motorda güvenli değildir (F6-24).

**Bearoff kesmesi** yalnızca değerlendirici `IExactValueEvaluator` uyguluyorsa etkilidir.
`BearoffAwareEvaluator` uygular; `MatchAwareEvaluator` **uygulamaz** (`E → ME` dönüşümü tek skaler
`E`'nin monoton fonksiyonu değildir).

### 17.3 Ölçümler

| Test | Ölçüm | Sonuç |
|---|---|---|
| 75 | `Default`/`Reference` yeni alanlar; 24 pozisyon | 0 / false; değer ve hamle birebir aynı; TT isabet 0 |
| 76 | 20 pozisyon, depth 2, TT 2¹², 3 tur | değer ve hamle birebir aynı; 3. tur **863 isabet** |
| 77 | 12 saf yarış, depth 1 | düğüm **3 939 → 12** (**328×**); değer ve hamle aynı |
| 78 | 16 pozisyon, TT / TT+kısıt / bearoff kesmesi | `Reference(depth)` ile **birebir aynı** |
| 79 | 30 pozisyon, depth 2, aday 4/4, TT 2²⁰ | p50 **0,1217 s**, p95 **0,7133 s**, oyun **5,24 s** |
| 80 | 200 pozisyon + 20 bitiş, TT açık | **0 bayt** allocation |
| 81 | `SearchTests` 39 test; `Default`/`Reference` 9+11 alan | değişmedi; referans eşitliği korunuyor |
| 82 | 24 pozisyon, kalıcı workspace, 3 konfigürasyon | TT ek kazanç **%2,9**; cache tek başına **%0,4** daha iyi |

### 17.4 Ablasyon kararı — TT üretimde açılmaz

Test 82, gerçek kullanım biçimini ölçer (`SelfPlayAgent` workspace'i kararlar arasında yaşatır;
`Reset()` yalnızca model yeniden yüklenince çağrılır):

| Konfigürasyon | Değerlendirici | Düğüm | TT isabet | Süre |
|---|---|---|---|---|
| cache açık, TT kapalı | 91 203 | 92 392 | 0 | 3,546 s |
| ikisi de açık | 89 876 | 91 065 | 21 | 3,446 s |
| cache kapalı, TT açık | 93 501 | 94 753 | 84 | 3,534 s |

TT, eval cache'in üzerine yalnızca **%2,9** ekliyor; cache tek başına TT'den **%0,4** daha iyi.
Sebep: pahalı iş (yaprak değerlendirme + chance düğümü) zaten `UseEvalCache` tarafından
anahtarlanıyor ve tavla'da gerçek transpozisyon (aynı tahta + aynı zar + aynı derinlik) nadirdir.

v3 §9.5 "kazanç yoksa sadeleştirilir ve raporlanır" der. Karar: **TT varsayılan olarak kapalı
kalır ve üretim yollarında (`SelfPlayAgent`, `GameOrchestrator`) açılmaz.** Kod opt-in olarak
korunur — §9.3'ün zorunlu teslimatıdır ve Test 76/78/80 ona bağlıdır (F6-25).

### 17.5 Performans kapıları

| Metrik | Ölçülen | v3 §9.5 hedefi | Durum |
|---|---|---|---|
| p50 karar süresi (depth 2) | **0,1217 s** | ≤ 0,15 s | ✅ |
| p95 karar süresi (depth 2) | **0,7133 s** | ≤ 2 s | ✅ |
| Ortalama oyun (27 karar) | **5,24 s** | ≤ 5 s (kapı **değil**) | ⚠️ %5 aşım |
| Isınma sonrası allocation | **0 bayt** | 0 | ✅ |

Ortalama oyun süresi v3 §9.5'te açıkça **kapı değil** ilan edilir ("raporlanır"). 5,24 s,
5 s'lik raporlama hedefinin %5 üzerindedir; iki gerçek kapı (p50, p95) rahat geçilmiştir.

### 17.6 Alınmayan optimizasyonlar

| # | Öneri | Neden alınmadı |
|---|---|---|
| 1 | Sezgisel "E > 0,9 → kes" | v3 §9.5 [v3-DÜZELTME]: sonucu değiştirir, değişmez kuralı ihlal eder |
| 2 | TT `LOWER`/`UPPER` kesmesi | Chance katmanı ağırlıklı ortalaması sınır propagasyonunu güvensiz kılar (F6-24) |
| 3 | Depth 3 | v3 §9.6 kapsam dışı; vektör değerli expectiminimax gövde değişikliği gerektirir |
| 4 | Star2 / daha agresif aday kısıtı | Sonucu değiştirir; Aşama E'nin kapsamı dışı |

### 17.7 Test sayıları

`Backgammon.Tests` **256 → 264** (+8: Test 75–82). Toplam **624 → 632**.
`Backgammon.Inference.Tests` 64, `Backgammon.UI.Tests` 85, `ml/tests` 219 — değişmedi.

### 17.8 Yeniden üretim

```powershell
dotnet test Backgammon.Tests\Backgammon.Tests.csproj -c Release `
  --filter "FullyQualifiedName~SearchPowerTests" --logger "console;verbosity=detailed"
```

---

## 18. Faz 6 — Aşama F: küp ve maç ustalığı

Aşama F'nin hedefi, Faz 5'te kurulan küp/maç katmanını **ölçülebilir** biçimde gnubg seviyesine
yaklaştırmaktır. Bu bölüm üç hatanın (F6-28, F6-29, F6-30) bulunup düzeltilmesini ve düzeltme
sonrası küp kararı uyumunu belgeler. Üçü de birbirini maskeliyordu; sırayla açıldı.

### 18.1 Ölçüm hattı: `ml/cube_bench.py`

Betik gnubg'nin **kendi Python yorumlayıcısıyla** çalışır (`gnubg-cli.exe -p ml/cube_bench.py`),
çünkü `onnxruntime` gnubg'nin gömülü yorumlayıcısında içe aktarılamaz. İş bölümü:

1. `Backgammon.MatchBench cube` → `ml/artifacts/stage_f_cube_ours.json` (`DiceAveraged = true`)
   ve `stage_f_cube_ours_single.json` (`DiceAveraged = false`).
2. `cube_bench.py` → gnubg `cfevaluate` (0-ply ve 2-ply) → `stage_f_cube_gnubg.json`.
3. `cube_bench.py` → `stage_f_cube.md` (uyum tabloları + karışıklık matrisleri).

Pozisyon kaynağı `ml/artifacts/stage_b_positions.json` (200 pozisyon; 133'ü gnubg için güvenli).

### 18.2 F6-28 — gnubg Python API'si `cubeinfo.move` alanını yok sayar

`gnubg.evaluate` ve `gnubg.cfevaluate`, `cubeinfo` sözlüğündeki `move` alanını **okumaz**; her
zaman `anBoard[1]`'i sırada kabul eder ve sonucu onun bakış açısından döndürür. Kanıt:

- `cubeinfo(1, -1, 0, ...)` ile `cubeinfo(1, -1, 1, ...)` **bayt bayt aynı** çıktı (dört farklı
  pozisyonda, iki ayrı süreçte).
- `anBoard` satırlarını takas etmek sonucu **işaret çevirerek** değiştirir (`p0-money`: +0,1819 →
  +0,3323; `p3-money`: +1,5216 → −1,1249).
- Metin protokolü (`set turn 0|1` + `eval`) sırayı **doğru** okur (`p0-money`: turn +1 → 0,332,
  turn −1 → 0,182). Yani `ml/gnubg_er.py::GnubgSession` etkilenmez.

Düzeltme: `ml/cube_bench.py::gnubg_view(case)` hamleyi yapan oyuncuyu her zaman `anBoard[1]`'e
yerleştirir, skor demetini ve küp sahibini buna göre eşler; `cubeinfo` koşulsuz `move=1` alır.

### 18.3 F6-29 — Küp danışmanı afterstate'leri hamleyi yapanın perspektifinden değerlendirmeli

`EquityCubeAdvisor.EvaluateDiceAveraged`, afterstate'leri `-perspective` ile değerlendirip
`v = -values[i]` ve `dists[best].Flip()` uyguluyordu. Bu "negamax" varsayımı Faz 6'da geçersiz:
`ShardWriter` her karar için `VectorizeAfterMove(..., mover, ...)` yazar, `ml/gnubg_er.py`
`score_afterstates` `perspective=turn` kullanır ve `BackgammonSearch.SearchNode` de `s.turn`
geçirir. Ağ **antisimetrik değildir** (ölçüldü: `mean |V(Q, p) + V(Q, −p)| = 0,65`), bu yüzden
işaret çevirme doğrudan yanlılık üretiyordu.

Düzeltme: `EvaluateBatch`/`EvaluateDistributionBatch` artık `perspective` alır; `v = values[i]`
ve `dists[best]` (Flip yok).

### 18.4 F6-30 — Maç oyununda çiftleme karşılaştırması `min`, `max` değil

`EquityCubeAdvisor.Decide`, maç oyununda çiftleme kararını `Math.Max(doubleTake, doublePass)`
ile veriyordu. `max`, **rakibin işbirliği yaptığını** varsayar. Rakip kendi equity'sini maksimize
eder, yani bizimkini minimize eder; çiftlemeden sonra gerçekleşen değer
`Math.Min(doubleTake, doublePass)` olmalıdır.

Kanıt: `max` ile 32 fazla çiftleme vardı; bunların 19'u `min` altında "çiftleme"ye dönüyor —
hata tamamen tek yönlüydü. `tooGood` da sıkılaştırıldı: eski `doublePass > doubleTake` koşulu,
rakip pas verdiğinde bizim yine 1 puan kazandığımızı yok sayıyordu. Yeni koşul
`doublePass > doubleTake && noDouble > doubleTake`.

### 18.5 Sonuç — gnubg 0-ply, 133 geçerli pozisyon

| Metrik | Faz 5 taban | F6-28 sonrası | F6-29 sonrası | **F6-30 sonrası** |
|---|---|---|---|---|
| Çiftleme uyumu | 52,27 % | 67,67 % | 73,68 % | **84,96 %** |
| Kabul/ret uyumu | 61,36 % | 77,44 % | 88,72 % | **88,72 %** |
| Her iki karar uyumu | 46,97 % | 61,65 % | 69,17 % | **81,20 %** |
| Equity korelasyonu (Pearson) | — | 0,7803 | 0,8330 | **0,8330** |
| Equity ortalama \|Δ\| | 1,2063 | 0,5249 | 0,3738 | **0,3738** |
| Equity p90 \|Δ\| | — | 1,0293 | 0,9038 | **0,9038** |
| İşaretli yanlılık (biz − gnubg) | — | +0,2587 | −0,1872 | **−0,1872** |

Kabul/ret ve equity metriklerinin F6-30'da **değişmemesi** beklenen sonuçtur: `min`/`max` yalnızca
"çiftle mi?" kararını etkiler. Bu, düzeltmenin gerçekten tek bir karşılaştırmaya dokunduğunun
kanıtıdır.

**Kapı durumu (v3 §13.3).** Çiftleme uyumu ≥ %75 → **84,96 %**, geçildi. Ortalama \|Δ\| < 1,2063
→ **0,3738**, geçildi.

`singleRecord` (`DiceAveraged = false`, Faz 5 davranışı) 75,94 % / 81,20 % / 73,68 %,
korelasyon 0,8218, ortalama \|Δ\| 0,6266. Bu yol **üretimde kullanılmaz**; sıra başı pozisyonu
değerlendirdiği için ağın hiç görmediği bir girdi dağılımına düşer (bkz. F6-29).

gnubg 2-ply ile fark yok denecek kadar azdır (korelasyon 0,8327, ortalama \|Δ\| 0,3737): bizim
kararımız gnubg'nin arama derinliğine duyarsızdır, çünkü danışman zaten 21 zar çifti üzerinden
tam bir 1-ply zar düğümü çözer.

### 18.6 Karışıklık matrisleri (`diceAveraged`, gnubg 0-ply)

| Çiftleme | gnubg: çiftle | gnubg: çiftleme |
|---|---|---|
| **bizim: çiftle** | 39 | 13 |
| **bizim: çiftleme** | 7 | 74 |

| Kabul | gnubg: kabul | gnubg: ret |
|---|---|---|
| **bizim: kabul** | 77 | 6 |
| **bizim: ret** | 9 | 41 |

Düzeltme öncesi çiftleme matrisi 0 / 46 / 43 / 44 idi: gnubg "çiftle" derken biz **hiç**
çiftlemiyorduk. F6-29 sonrası 42 / 31 / 4 / 56 oldu (hâlâ 31 fazla çiftleme). F6-30 sonrası
39 / 13 / 7 / 74 — hata artık iki yöne de dağıldı (13 vs 7), yani sistematik değil.

### 18.7 Kalan yanlılık ve sınırlar

- `diceAveraged` medyanı −0,093 (ortalama −0,187). Kalan fark **model kalitesidir**, sözleşme
  hatası değil: ağ ER kümesinde 0,049 ER'ye kalibre, ama küp pozisyonları farklı bir dağılımdan
  gelir.
- `singleRecord` ortalama −0,56 yanlılık gösterir; nedeni 18.3'te açıklandığı gibi sıra başı
  girdisidir. `CubeAdvisorOptions.DiceAveraged` varsayılanı `true`'dur.
- gnubg `cubeinfo` varsayılanı `jacoby: 1`'dir (Jacoby kuralı **açık**). Money-game
  karşılaştırmalarında bu ikincil bir fark yaratabilir; ölçülmedi, açık uç olarak kaydedildi.
- Maç kazanç ölçümü (Test 87) **tavan etkisine** takıldı: `PipBot` yalnızca pip sayısını
  minimize eden açgözlü bir bot ve 2/4/5-away maçlarında ~%99 kaybediyor. Hedef (%45) fazlasıyla
  aşıldı ama ölçümün ayırt ediciliği yok; ayrıntı ve yorum §18.8'de.

### 18.8 Maç kazancı (Test 87)

`Backgammon.MatchBench match-gain`, 2/4/5-away maçlarında `matchAware` açık/kapalı olarak
400'er oyun oynar. Sonuçlar (`ml/artifacts/stage_f_match_gain.json`, `model_v15.onnx`):

| Maç | matchAware | Kazanma | Puan/maç | Çiftleme | Pas |
|---|---|---|---|---|---|
| 2-away | kapalı | 99,50 % | 2,2550 ± 0,0363 | 213 | 30 |
| 2-away | açık | 99,50 % | 2,3025 ± 0,0354 | 214 | 28 |
| 4-away | kapalı | 99,00 % | 2,2525 ± 0,0382 | 482 | 32 |
| 4-away | açık | 99,00 % | 2,2800 ± 0,0387 | 485 | 32 |
| 5-away | kapalı | 99,50 % | 2,3600 ± 0,0340 | 517 | 8 |
| 5-away | açık | 99,50 % | 2,3800 ± 0,0338 | 520 | 8 |

Hedef (2-away ≥ %45) **fazlasıyla aşıldı**. Ancak bu ölçümün ayırt ediciliği yoktur: rakip
`PipBot` pip sayısını açgözlü minimize eden, vuruşları hiç değerlendirmeyen bir bottur; Aşama D
modeli (TEST-ER 0,049) ona karşı tavan yapıyor. `matchAware` açık/kapalı farkı yalnızca
puan/maç sütununda görünür (2-away 2,2550 → 2,3025; 4-away 2,2525 → 2,2800; 5-away 2,3600 →
2,3800) — yani maç farkındalığı **kazanma oranını** değil, **kazanılan puanı** iyileştiriyor. Bu
beklenen yöndedir: 2-away'de maçı kazandıran tek oyun olduğu için küp yönetimi puanı büyütür,
oyun kazanma olasılığını değiştirmez. Çiftleme sayıları da tutarlıdır: 2-away'de 213/214,
4-away'de 482/485, 5-away'de 517/520 — maç farkındalığı çiftleme sıklığını değiştirmiyor, yalnızca
**ne zaman** çiftleneceğini değiştiriyor.

Faz 5 tabanı (`stage_b_match_gain.json`, `model_v2.onnx`) 2-away'de %40,00 / %39,50 idi. Aradaki
fark model kalitesi **ve** F6-29/F6-30 düzeltmeleridir: Faz 5'te küp danışmanı işareti ters
olduğu için gerideyken çiftliyor, öndeyken pas veriyordu.

### 18.9 Yeniden üretim

```powershell
dotnet build Backgammon.MatchBench\Backgammon.MatchBench.csproj -c Release
$exe = "Backgammon.MatchBench\bin\Release\net10.0\Backgammon.MatchBench.exe"
& $exe cube --positions ml\artifacts\stage_b_positions.json `
  --out ml\artifacts\stage_f_cube_ours.json `
  --model ml\runs\stage_d_l2\onnx\model_v15.onnx --dice-averaged 1
& $exe cube --positions ml\artifacts\stage_b_positions.json `
  --out ml\artifacts\stage_f_cube_ours_single.json `
  --model ml\runs\stage_d_l2\onnx\model_v15.onnx --dice-averaged 0

$env:TAVLA_ROOT = "F:\Projects\VijualStudioski\TavlaAI_Project"
& "F:\Program Files (x86)\gnubg\gnubg-cli.exe" -p "F:/Projects/VijualStudioski/TavlaAI_Project/ml/cube_bench.py"

& $exe match-gain --model ml\runs\stage_d_l2\onnx\model_v15.onnx --games 400 `
  --out ml\artifacts\stage_f_match_gain.json
```

### 18.10 Dogrulama

```
ml/tests                     550/550  (3 yavas/kosullu test atlanir)
Backgammon.Tests             285/285
Backgammon.Inference.Tests    64/64
Backgammon.UI.Tests           85/85
```

Asama E sonunda 264 olan C# motor testi sayisi, Asama F'nin `CubePowerTests` dosyasiyla
(Test 83, 85, 86, 88) **268**'e cikti. Python tarafinda `ml/tests/test_stage_f.py` uc olcum
testi ekledi (Test 84, 87, 89): 219 → **224**. Toplam **641**.

Faz 7 Asama A alti yeni pytest dosyasi ekledi (`test_er_power.py` 47, `test_gnubg_hint.py` 68,
`test_measurement_integrity.py` 45, `test_equity_parity.py` 26, `test_proof_corpus.py` 45,
`test_er_harness_stage_a.py` 55, `test_human_ladder.py` 37): 224 → **550**. C# tarafinda
`EquityGoldenTests` yedi test ekledi: 268 → **275**. Toplam **974**.
## 19. Aşama H — Kapanış

Aşama H kod üretmez; **ölçer, raporlar ve kapatır**. Çıktısı
`ml/artifacts/stage_f_faz6.md` (Faz 6 kapanış raporu) ve bu bölümdür.

### 19.1 Kapsam

v3 §13.5: *"Tüm testler yeşil; PHASES.md §13, ARCHITECTURE.md §44, ASSUMPTIONS.md
F6-01…F6-xx yazılır; Bölüm 13 tabloları ölçülmüş değerlerle dolu; Ek A cevapları
(erişim alındı/alınmadı) yazılır."* Bölüm numaraları v3 yazıldıktan sonra kaydığı için
gerçekleşen karşılıkları §19 (bu bölüm), ARCHITECTURE.md §50 ve ASSUMPTIONS.md
F6-01…F6-31'dir.

### 19.2 Yeni ölçüm araçları

| Dosya | İş |
|---|---|
| `ml/calibration_bench.py` | §13.2 kalibrasyon ölçümü — gnubg **metin protokolü** ile |
| `Backgammon.MatchBench` `bench` alt komutu | ONNX çıkarım throughput'u (kova 1…2048, CPU/CUDA) |
| `Backgammon.MatchBench` `dump-afterstates` | Kalibrasyon için afterstate dökümü |

`ml/calibration_bench.py` neden ayrı bir dosya: Faz 5'in `ml/afterstate_bench.py`
betiği gnubg'nin **Python API**'sini kullanıyordu ve o yol bu projede güvenilir
değil (F6-28: `cubeinfo['move']` yok sayılır). Yeni betik metin protokolünü
(`GnubgSession.eval_afterstates`) kullanır, pip sayılarını doğrular ve
`measure_position` ile aynı perspektif sözleşmesini uygular.

### 19.3 Ölçülen değerler

**Güç (§13.1).**

| Ölçüm | Faz 5 | Faz 6 | Kapı |
|---|---|---|---|
| gnubg ER 2-ply (200 poz.) | 0,1941 (50 poz.) | **0,0740** | hedef < 0,02 → tutmadı |
| gnubg ER 0-ply (200 poz.) | — | **0,0972** | — |
| gnubg ER 3-ply (200 poz.) | — | **ölçülemez** (F6-32) | hedef < 0,01 → ölçülmedi |
| PipBot karşısında | %40,50 | **%99,50** | — |
| RandomBot karşısında | %80,50 | **%100,00** | — |
| Faz 5 `v5.onnx` karşısında (1 500 oyun) | — | **%99,67** | > %50, p < 0,05 → **geçti** |

**3-ply satırı hakkında (F6-32).** Aşama H'de "3-ply ER 0,0972" olarak raporlanan değer
**3-ply değildir**: gnubg'nin `eval` komutu `set evaluation chequerplay evaluation plies N`
ayarından bağımsız olarak yalnızca `static` / `1 ply` / `2 ply` satırlarını basar ve
`_equity_at` istenen sütunu bulamayınca sessizce `static`'e (0-ply) düşüyordu. `--plies 0`
ölçümü `--plies 3` ile 200/200 pozisyonda birebir aynı çıktı. Yani gerçek merdiven
**0-ply 0,0972 → 2-ply 0,0740**: model hakem güçlendikçe *iyileşiyor*. Sessiz geri düşüş
kaldırıldı (`MAX_EVAL_PLIES = 2`, aksi halde `ValueError`), `er_harness measure` desteklenmeyen
derinlikte çalışmadan çıkıyor. Gerçek 3-ply hakem `hint` protokolü + hamle→afterstate eşlemesi
gerektirir; Faz 7'ye devredildi.

**Kalibrasyon (§13.2).** 400 afterstate, `model_v30.onnx`, gnubg 0-ply / 2-ply:
eğim **0,6601** / 0,6743, korelasyon **+0,8989** / +0,9016, MAE **0,2755** / 0,2683,
std oranı **1,3617** / 1,3371. Korelasyon ve std oranı kapıları geçti; **eğim ve MAE
kapıları kaldı**.

**Küp ve maç (§13.3).** Çiftleme uyumu **%84,96**, kabul/ret **%88,72**, her ikisi
**%81,20**, ortalama |Δ| **0,3738** — hepsi kapı içinde. 2-away maç farkındalığı
**%99,50** (hedef ≥ %45, tavan etkisi). Crawford doğru (Test 85).

**Performans (§13.4).** Üretim modeli `medium` (221-256-256-128): CPU kova 128
**237 708** poz/sn, CUDA kova 2048 **875 580** poz/sn. v3 eşikleri (700 000 /
1 200 000) `small` mimarisinde ölçülmüştü; `medium` 4,5× daha ağır olduğu için
**belgelenmiş sapma** olarak raporlanır. Arama allocation **0 bayt**, depth 2 p95
**0,7133 s/karar** (kapı ≤ 2 s), depth 2 ortalama oyun **5,24 s** (raporlanır),
12-thread self-play **584,97 oyun/s**.

### 19.4 F6-31 — Faz 5 kalibrasyon ölçümü aynalı tahta kullanıyordu

Aşama H'nin en önemli bulgusu bir **ölçüm hatasıdır**, kod hatası değil. Faz 5'in
`ml/afterstate_bench.py::to_gnubg_board` tahtayı gnubg'ye aynalanmış veriyordu
(`row0[i] = board[1+i]`, `row1[i] = -board[24-i]`; doğrusu `row0[i] = board[24-i]`,
`row1[i] = -board[1+i]`). Simetrik bir pozisyonda doğru çevirim +1,0000 verirken
hatalı çevirim +0,2819 veriyor; asimetrik bir pozisyonda işaret bile değişiyor.

Sonuç: Faz 5'in "eğim 0,0874, korelasyon +0,2431, MAE 0,8014, std 2,78" rakamları
modelin gerçek kalibrasyonu **değildi**. Gerçek değerler eğim 0,6601, korelasyon
+0,8989, MAE 0,2755, std 1,3617. Yani Faz 6'nın kalibrasyondaki "iyileşmesi"nin bir
kısmı gerçek eğitim kazancı, bir kısmı ise **tabanın düzeltilmesidir**. İkisi
birbirinden ayrıştırılamaz, çünkü Faz 5'in doğru tabanı hiç ölçülmemişti.

Aynı ölçüm gnubg Python API'siyle tekrarlandığında eğim −0,0011, korelasyon −0,0022
çıktı — yani gürültü. Dört farklı tahta çevirimi denendi, hiçbiri metin protokolüyle
uyuşmadı. **Kalibrasyon ölçümü için tek güvenilir yol gnubg metin protokolüdür.**

### 19.5 Sapmalar

Kapanış raporunun §10 tablosu on iki sapma listeler. Özet: ER hedefleri (D1, D2)
tutmadı; kalibrasyon eğim/MAE kapıları (D3, D4) kaldı; ONNX throughput kapıları
(D5, D6) mimariyle birlikte ölçeklenmediği için karşılanamadı; `large` profili (D8),
`search_distill` (D9), Ek A (D10), Test 64'ün koşum adımı (D11) ve Test 69 (D12)
kapsam dışı kaldı. Hiçbiri gizlenmemiştir.

### 19.6 Doğrulama

```
ml/tests                     550/550  (3 yavaş/koşullu test atlanır)
Backgammon.Tests             285/285
Backgammon.Inference.Tests    64/64
Backgammon.UI.Tests           85/85
```

Toplam **974**. Aşama H kapanıştan sonra F6-32 için **2** regresyon testi ekledi
(`test_equity_at_rejects_unsupported_ply`, `test_max_eval_plies_matches_gnubg_contract`):
222 → **224**. Faz 7 Asama A alti yeni pytest dosyasi ve `EquityGoldenTests` ekledi:
224 → **550** (pytest), 268 → **275** (C# cekirdek). `ml/tests/test_docs_consistency.py`
belge tutarlılığını (bölüm numaraları, test sayıları, atıf edilen yollar) korumaya devam ediyor.

## 20. Faz 7 — Aşama A: ölçüm hattı ve hakem sözleşmesi

Faz 7'nin tamamı **ölçüm dürüstlüğü** üzerine kuruludur: hiçbir sayı, kaynağı
yazılmadan rapora girmez. Aşama A bu altyapıyı kurdu ve **hiçbir eğitim koşusu
başlatmadı**.

### 20.1 Yeni ölçüm araçları

| Dosya | İş |
|---|---|
| `ml/er_power.py` | İstatistiksel güç: `required_n`, `sigma_ci`, `power_curve`, tarama modu |
| `ml/gnubg_hint.py` | `hint` hakemi: hamle filtresi genişletme, perspektif çevirme, sansür tespiti |
| `ml/measure_integrity.py` | Dört bağımsız doğrulama probu (Test 93) |
| `ml/proof_corpus.py` | 2 000 pozisyonluk kanıt korpusu, SHA-256 dondurulmuş |
| `ml/human_ladder.py` | 7 basamaklı insan karşılaştırma merdiveni (Test 94) |
| `ml/equity.py` | float32 aynası (F7-06) |
| `ml/er_harness.py` | `--referee hint`, `--power`, `referee_contract` |

### 20.2 F7-01 — gnubg `hint` hamle filtresi adayları buduyor

`hint` varsayılan olarak yalnızca filtrelenmiş adayları listeler; modelin
afterstate'i listede olmayabilir. Düzeltme: `set evaluation movefilter <plies>
<level> 1000 0 0.0` **her** `level in range(plies)` için. Sözdizimi
`set evaluation movefilter`'dır — `set evaluation chequerplay movefilter`
**değil**.

### 20.3 F7-02 — gnubg hamle notasyonu hamleyi yapanın perspektifinde

X (Siyah, `turn = -1`) mutlak; O (Beyaz, `turn = +1`) aynalanmış (`p -> 25 - p`).
`parts[i].rstrip("*")` zorunlu. Bu düzeltilmeden hamle → afterstate eşlemesi
sistematik olarak yanlıştı.

### 20.4 F7-03 — `hint` en fazla 10 hamle yazdırıyor

200 pozisyonun 39'unda (**%19,5**) modelin afterstate'i listede yoktu.
`plies <= 2` için `eval` yedeği (%100 kapsama); `plies >= 3` için **sansürlü**,
yalnızca alt sınır. Bu, F-A9 kapısının (kapsama ≥ %99) neden karşılanmadığının
kaynağıdır.

### 20.5 F7-04 — `hint@2` ile `eval@2` aynı şey değil

10 pozisyonun 6'sı birebir, 4'ü **0,118**'e varan farkla ayrıştı. Karar:
**2-ply hakem = `eval`; 3/4-ply hakem = `hint`; `hint@2` asla hakem değildir.**

### 20.6 F7-05 / F7-06 — equity tek kaynak, iki dilde bit düzeyinde

`OutcomeDistribution.Flip()` bit düzeyinde involüsyon **değil** (en büyük sapma
1,34e-07). C#/Python paritesi float32 aynası olmadan kurulamaz: aynasız sapma
**0,156**, aynayla **0 uyuşmazlık** (296 geçerli kayıt × 5 kümülatif alan +
`equityHex`). `ml/tests/test_equity_parity.py` (26 test) `atol = 0` ile doğrular.

### 20.7 F7-07 — 4-ply `hint` maliyeti sınırsızdır

60 pozisyonluk CAL kümesinde 4-ply `hint` 14 pozisyonda 2 412,9 s
(**172 s/pozisyon**), 15. pozisyonda 900 s zaman aşımı. 1 670 pozisyon ≈ **80
saat** > 40 saat tavanı. Merdiven hakemi **3-ply**'a indirildi; 4. basamak
`source = "unmeasured"` olarak raporlandı.

### 20.8 Ölçülen insan merdiveni (60 CAL pozisyon, 3-ply hakem, 642,6 s)

| # | Referans | Kaynak | Kapsama | ER | %95 GA |
|---|---|---|---|---|---|
| 0 | gnubg 0-ply | ölçülür | %86,7 | **0,0522** | [0,0270; 0,0773] |
| 1 | gnubg 1-ply | ölçülür | %80,0 | **0,0530** | [0,0274; 0,0787] |
| 2 | gnubg 2-ply | ölçülür | %91,7 | **0,0525** | [0,0264; 0,0785] |
| 3 | gnubg 3-ply | hakemin kendisi | %100 | 0 (tanım) | — |
| 4 | gnubg 4-ply | **ölçülmedi** | — | — | — |
| 5 | dünya şampiyonu insan | literatür | — | 0,0025 | — |
| 6 | gnubg 4-ply + büyük ağ | literatür | — | 0,003 | — |

**Merdiven düz.** Bölüm 4.4'ün beklediği 0,10 / 0,08 / 0,05 düşüşü **görülmedi**.
Bu, belgenin ölçülmemiş bir varsayımıydı; ölçüm onu çürüttü.

### 20.9 σ̂ ve güç sözleşmesi

`ml/artifacts/stage_h_er_2ply.json` (n = 200, gnubg 2-ply): ortalama **0,073970**,
σ **0,109072**, SE **0,007713**. σ'nın %95 GA'sı (bootstrap, 20 000 yeniden
örnekleme) [0,092153; 0,124178] → **±%14,7**. Kanıt n'i **üst güven sınırından**
hesaplandı: σ = 0,124178, h = 0,005 → **1 670** (tek yönlü). `er_sigma_log.json`
Aşama A satırıyla açıldı (12 alan).

### 20.10 Aşama A kabul durumu (Bölüm 10.6)

| Kriter | Durum |
|---|---|
| Test 90–94 yeşil | GEÇTİ |
| Test 122–123 yeşil (iki dilde bit düzeyinde) | GEÇTİ |
| Test 124 yeşil (güç sözleşmesi) | GEÇTİ |
| Hakem sözleşmesi zorunlu (`methodNote`) | GEÇTİ |
| `hint` 3-ply ve 4-ply veriyor | GEÇTİ |
| Hamle → afterstate eşlemesi 200/200 | GEÇTİ (0 hata) |
| Dört doğrulama probu kalıcı test | GEÇTİ (45 test) |
| İnsan merdiveni 0–4 ölçülmüş | **KISMİ** — 0–3 ölçüldü, 4 ölçülemedi (F7-07) |
| σ ölçülmüş, kanıt n'i üst güven sınırından | GEÇTİ (1 670) |
| Kanıt korpusu üretildi ve SHA-256 donduruldu | GEÇTİ |
| `assert_valid` negatif testi yeşil | GEÇTİ |

### 20.11 Doğrulama

```
ml/tests                     550/550  (3 yavaş/koşullu test atlanır)
Backgammon.Tests             285/285
Backgammon.Inference.Tests    64/64
Backgammon.UI.Tests           85/85
```

Toplam **974**. Aşama A yedi yeni pytest dosyası ve `EquityGoldenTests` ekledi:
224 → **550** (pytest), 268 → **275** (C# çekirdek).

## 21. Faz 7 — Aşama B: kapasite ve veri (Test 95–98)

Aşama B'nin sorusu tek cümleydi: **`large` profile geçmek %15 kazanç getiriyor
mu?** Cevap **hayır** — ve bu, ölçümün en değerli çıktısıdır.

### 21.1 Test 95 — profil ölçümü ve parite

| Profil | Mimari | Parametre | ONNX | Parite max abs | CPU kova 128 |
|---|---|---|---|---|---|
| `medium` | 221-256-256-128 | 156 423 | 615,5 KB | **5,96e-08** | 347 448 poz/sn |
| `large` | 221-512-512-512 | 642 567 | 2 514,5 KB | **5,96e-08** | 141 875 poz/sn |

F-B3 kapısı (parite ≤ 1e-6) **geçti**. `large` throughput'ta 2,45× yavaş.

### 21.2 Test 96 — kapasite kararı: `medium` kalır

İki profil, **aynı** 6 shard (`it5, it10, it15, it20, it25, it30`), aynı tohum
(11), aynı adım (3 000), aynı λ (1,0), aynı kritik çarpan (2,0), CPU:

| Profil | Parametre | Eğitim | VAL-ER | SE | depth 2 p95 |
|---|---|---|---|---|---|
| `medium` | 156 423 | 679,8 s | **0,0640** | 0,0119 | 4,4972 s |
| `large` | 642 567 | 1 297,8 s | **0,0664** | 0,0120 | 13,6816 s |

| Bacak | Kriter | Ölçülen | Durum |
|---|---|---|---|
| (a) | `large` VAL-ER kazancı ≥ %15 | **−%3,7** | **TUTMADI** |
| (b) | `large` depth 2 p95 ≤ 2 s | **13,68 s** | **TUTMADI** |

Gözlenen fark −0,0024, gürültü eşiğinin (0,0025) **altında** ve işareti **ters**.
Yani "fark yok" bile denemez; `large` hafifçe **daha kötü**.

**Yorum.** 3 000 adım, 642 567 parametreli bir ağı doyurmuyor. `large` `medium`
kadarını öğreniyor, fazladan kapasitesini kullanamıyor, yalnızca optimizasyon
zorluğu ekliyor. "Daha büyük ağ daha iyi" varsayımı **ölçülerek reddedildi**.

### 21.3 F7-10 — ilk koşu geçersizdi

İlk Test 96 koşusu (1 000 adım, tek shard) `medium` 0,2631 / `large` 0,2532
verdi ve "%3,8 kazanç" diye raporlandı. Bu **yanlıştı**: `ml/train_v2.py` ONNX'i
her iterasyonun **başında** aktarır, yani `--iterations 1` koşusunda
`model_v1.onnx` **rastgele başlangıçtır**. Ölçülen şey eğitilmiş model değildi.

| Model | VAL-ER | SE |
|---|---|---|
| `model_v1.onnx` (eğitim öncesi) | 0,2631 | 0,0356 |
| `model_v1_trained.onnx` (eğitim sonrası) | **0,0640** | 0,0119 |

Fark **4,1×**. Düzeltme: `ml/export_ckpt.py` (checkpoint → ONNX). Bölüm 21.2'nin
tüm sayıları bu yolla üretilmiş eğitilmiş modellerden gelir.

### 21.4 F7-09 — depth 2, gerçek ONNX ile bütçeyi 10 kat aşıyor

| Model | Derinlik | p50 | p95 | Ortalama | ONNX çağrısı / karar |
|---|---|---|---|---|---|
| `medium` | 0 | 0,0003 s | 0,0010 s | 0,0004 s | 1 |
| `medium` | 1 | 0,0233 s | 0,0902 s | 0,0328 s | 85 |
| `medium` | **2** | **2,0300 s** | **4,4972 s** | **2,1471 s** | 6 028 |
| `large` | 1 | 0,0718 s | 0,2598 s | 0,0895 s | 85 |
| `large` | **2** | **6,5306 s** | **13,6816 s** | **6,9198 s** | 5 948 |

Faz 6 Test 79'un 0,7133 s p95'i **sentetik** `HashEvaluator` ile ölçülmüştü;
gerçek çıkarım maliyetini içermiyordu. Maliyet ONNX **çağrı sayısıyla** doğrusal
(~0,35 ms/çağrı, kova boyutundan bağımsız): depth 2, 84×84 = 7 056 yaprak şans
düğümü üretir. Üretimde kullanılabilir derinlik **depth 1**'dir (p95 0,09 s,
bütçenin %4,5'i).

### 21.5 Test 97 — açılış çeşitliliği

`DupCapFilter.DefaultOpeningPlies = 10`, `DefaultCap = 3`. Sentetik tekrarlı
oyunlarla doğrulandı: `OpeningExempt == Games × 10`, `d < 10` hiçbir karar
kırpılmadı, kırpılan karar `ChosenVector`'ü koruyup `Q`/`PolicyTargetCs`/
`CandidateVectors`'ü kaybetti, `cap = 0` filtreyi kapatıyor, farklı parmak izleri
korunuyor. **9 C# testi yeşil.**

### 21.6 Test 98 — kritik karar ağırlığı (F7-08)

`ml/critical.py` + `ml/train_v2.py` entegrasyonu. Dağılım (6 shard, 3 000 adım):

| Başlık | Örnek | Kritik | Oran | Etkin örnek | Etkin oran |
|---|---|---|---|---|---|
| değer | 1 187 935 | 1 187 935 | **%100** | 1 187 935 | %100 |
| politika | 864 734 | 224 477 | **%25,96** | 771 296 | %89,2 |

**Politika yarısı çalışıyor.** **Değer yarısı dejenere (F7-08):** para oyununda
her değer örneğinin `|equity| = 1`'dir, dolayısıyla `|equity| >= 0,5` eşiği
hiçbir şeyi ayırmaz. `weight_distribution` artık `degenerate` bayrağı döndürür ve
`train_v2` dejenere başlık için ağırlığı **uygulamaz**, durumu **raporlar**.
Değer başlığı için doğru ölçüt henüz tasarlanmadı.

### 21.7 B1 / B2 / B3 yolu — **SEÇİLMEDİ**

Bölüm 5.1.6 üç yol tanımlar ve **kullanıcı onayı** ister. Ölçüm sonrası durum:

| Yol | Bu ölçümden sonra |
|---|---|
| **B1 — EVREN kapısı** (~1 ay) | **Geçersiz** — `large`'ın kazancı zaten ölçüldü: −%3,7 |
| **B2 — Kabul** (~3 ay) | **Geçersiz** — takvim `large`'a geçişi varsayıyordu |
| **B3 — Kapsam daraltma** (~2 ay) | **Tek tutarlı yol** — `medium` kalır, bütçe büyümez, ER hedefi ≤ 0,02, **şampiyon iddiası düşer** |

**Onay bekliyor.** Onay olmadan `large` ile hiçbir eğitim koşusu başlatılmaz.

### 21.8 Aşama B kabul durumu (Bölüm 10.7)

| Kapı | Kriter | Ölçülen | Durum |
|---|---|---|---|
| F-B1 | `large` VAL-ER kazancı ≥ %15 | −%3,7 | **TUTMADI** |
| F-B2 | `large` depth 2 p95 ≤ 2 s | 13,68 s | **TUTMADI** |
| F-B3 | `large` export paritesi ≤ 1e-6 | 5,96e-08 | **GEÇTİ** |
| Test 95 | Profil ölçümü + parite | iki profil | GEÇTİ |
| Test 96 | Kapasite kararı | `medium` kalır | GEÇTİ |
| Test 97 | İlk 10 ply `dup_cap` muafiyeti | 9 C# testi | GEÇTİ |
| Test 98 | Kritik karar ağırlığı | politika %26,0; değer dejenere | **KISMİ** |

### 21.9 Doğrulama

```
ml/tests                     1386/1386  (3 yavaş/koşullu test atlanır)
Backgammon.Tests             285/285
Backgammon.Inference.Tests   100/100
Backgammon.UI.Tests           88/88
```

Toplam **1615**. Aşama B üç yeni pytest dosyası (`test_critical.py` 76,
`test_capacity_bench.py` 48, `test_export_ckpt.py` 12) ve `StageBDataQualityTests` (9)
ekledi. B3 kararı dört dosya daha ekledi: `test_distill.py` (34), `test_calibrate.py` (32),
`test_critical.py` içindeki 20 marj testi ve `ProductionDepthTests` (10).
550 → **749** (pytest), 64 → **83** (inference).

## 22. Faz 7 — Aşama B sonrası: B3 kapsam daraltması (onaylandı)

**Tarih:** 2026-11-17. **Durum:** tamamlandı, 771 pytest + 285 + 100 + 88 C# testi yeşil.

### 22.1 Karar

Aşama B ölçümü B1 ve B2'yi **geçersiz** kıldı: `large`'ın kazancı zaten **−%3,7**
olarak ölçüldü (medium 0,0640 / large 0,0664), yani EVREN erişimi veya 3 aylık
takvim bu kararı değiştiremez. **B3 onaylandı** ve altı kalem yürürlüğe girdi:

| # | Karar | Uygulama |
|---|---|---|
| 1 | `large` dosyası kapatıldı | `large` üretim adayı değil; eğitim koşusu başlatılmaz |
| 2 | Depth 2 üretimden çıkarıldı | `SearchSettings.ProductionDepthPly = 1`, `SelfPlayConfig.Validate` reddeder |
| 3 | Test 98 onarıldı | Değer kafası **karar marjı** ölçütü; kritik oran %100 → **%33,3** |
| 4 | Kalibrasyon önceliklendirildi | `ml/calibrate.py`; eğim 0,6447 → **0,9584**, MAE 0,2641 → **0,1782** |
| 5 | Damıtma 500 000 karar | `ml/distill.py`; 500 000 = **70,7 saat** (tavan 72) |
| 6 | ER hedefi ≤ 0,02 | Bölüm 4.4 birinci koşulu uygulanmaz; **şampiyon iddiası düşer** |

### 22.2 Yeni modüller

| Dosya | Satır | Test | İş |
|---|---|---|---|
| `ml/distill.py` | ~300 | 34 | Damıtma hacmi planı; `DISTILL_VOLUME_CAP = 500_000`, `DISTILL_TIME_CAP_HOURS = 72`, `DEC_DISTILLED = 16` |
| `ml/calibrate.py` | ~330 | 32 | CAL/VAL bölmesi, affine onarım, dört kapı; Kural 10 (yalnızca CAL) |
| `ml/critical.py` | +90 | +20 | `critical_mask_value_margin`, `VALUE_CRITERION_*`, `criterion` alanı |
| `ml/train_v2.py` | +60 | — | `ExclusiveSamples.margin` / `.best_equity`, probe kalıcılığı |
| `Backgammon.Inference.Tests/ProductionDepthTests.cs` | ~150 | 10 | Depth 2 üretimde açılamaz |

### 22.3 Ölçümler

**Test 98 onarımı** (200 oyunluk gerçek shard kümesi, 12 264 değer örneği):

| Ölçüt | Kritik oran | Etkin oran | Dejenere? |
|---|---|---|---|
| Eski: `\|equity(y)\| >= 0,5` | **%100,0** | %100,0 | **evet** |
| Yeni: `\|best_equity\| >= 0,5` **ve** `marj <= 0,05` | **%33,3** | %88,9 | hayır |

**Kalibrasyon onarımı** (CAL 200 / VAL 200, tohum 20261117):

| Metrik | Öncesi (VAL) | Sonrası (VAL) | Kapı | Sonuç |
|---|---|---|---|---|
| Eğim | 0,6447 | **0,9584** | 0,85–1,15 | geçti |
| Korelasyon | +0,9022 | +0,9022 | ≥ 0,75 | geçti |
| MAE | 0,2641 | **0,1782** | ≤ 0,15 | **KALDI** |
| Std oranı | 1,3993 | **0,9414** | 0,7–1,4 | geçti |

Affine onarım `hedef ~ 0,6727 * tahmin + 0,1402`. Korelasyon **değişmedi**
(doğrusal dönüşüm Pearson'u değiştirmez). MAE kapı dışında kaldığı için post-hoc
onarım **yetmiyor**; `L_cal` yeniden eğitimi (Aşama D) zorunlu.

**Damıtma planı** (4,07 s/karar, 8× paralel → 1,9656 karar/sn):

| Hacim | Süre | Kısıtlayan |
|---|---|---|
| **500 000** | **70,7 saat** | hacim |
| 2 000 000 | 72,0 saat (kırpılmış) | **süre** |

### 22.4 Yeni bulgular

`ASSUMPTIONS.md`: **F7-12** (değer maskesi onarımı), **F7-13** (post-hoc
kalibrasyon eğimi düzeltir, MAE'yi düzeltmez), **F7-14** (damıtma hacmi ile 72
saat çelişiyordu), **F7-15** (depth 2 üretimden çıkarıldı).

### 22.5 Açık kalan

- **MAE 0,1782 > 0,15.** `L_cal` yeniden eğitimi koşulmadı; Aşama D'nin eğitim
  koşusu bu boşluğu kapatmalı.
- **Depth 2 geri dönüşü** yaprak-cephe toplu değerlendirmesine bağlı; kapsam dışı.
- **Damıtma koşusu** (500 000 karar, ~70,7 saat) henüz başlatılmadı; Aşama C.
- **ER ≤ 0,02** hedefi ölçülmedi; mevcut 2-ply ER 0,0740.

## 23. Faz 7 — Aşama C: arama damıtma (Test 99–102)

**Tarih:** 2026-11-17. **Durum:** hat tamamlandı, **Test 102 kapısı BAŞARISIZ
(güçsüz)**. 771 pytest + 285 + 100 + 88 C# testi yeşil.

### 23.1 Ne yapıldı

Üretim modeli 1-ply oynuyor (F7-15). 2-ply daha iyi karar veriyor ama karar
başına ~2,0 s (p95 2,85 s) sürüyor ve 2 s bütçesini aşıyor. Bu yüzden 2-ply
**öğretmen** olarak kullanılıp bilgisi 1-ply öğrenciye aktarıldı.

| Bileşen | Dosya | Test |
|---|---|---|
| Arama damıtma modu | `Backgammon.Core/Search/SearchSettings.cs`, `BackgammonSearch.cs` | Test 99 (10) |
| Shard bayrağı | `Backgammon.SelfPlay/ShardModel.cs` (`DEC_DISTILLED = 16`) | Test 100 (8) |
| Determinizm | `Backgammon.Inference.Tests/DistillDeterminismTests.cs` | Test 101 (9) |
| Kapı | `ml/distill_compare.py` | Test 102 (32) |

Shard **şema değişikliği olmadı** (F7-16): politika hedefi mevcut `q`, değer
hedefi mevcut `searchValue`. `DEC_DISTILLED` yalnızca işaret taşır.

### 23.2 Ölçülen maliyet

| Kol | Oyun | Derinlik | Karar | Duvar saati | Oyun başına |
|---|---|---|---|---|---|
| Damıtma | 20 | 2 | 1 048 | **1 034,26 s** | **51,7 s** |
| Kontrol | 20 | 1 | 1 128 | **19,13 s** | 0,96 s |

Öğretmen **54×** daha pahalı. Bu, §5.1.1 bütçesinin ana girdisidir.

### 23.3 Test 102 — BAŞARISIZ

| Ölçüm | Kontrol | Damıtılmış |
|---|---|---|
| VAL-ER (2-ply gnubg, n=70) | 0,0883 | 0,0602 |
| SE | 0,0153 | 0,0120 |

Kazanç nokta tahmini **0,3182** (eşik 0,25) ama %95 GA **[-0,0351; 0,6715]**
sıfırı içeriyor → kapı **başarısız**.

**Bu "damıtma işe yaramaz" demek değildir.** Gerekli n (gözlenen dağılımdan):
%80 güç için kol başına **264**, tam %25 kazanç için **427** pozisyon. Koşu
**70** kullandı — gerekenin **1/4'ü**. Kapı tasarım gereği karar veremezdi.

### 23.4 Yeni varsayımlar

`ASSUMPTIONS.md`: **F7-16** (damıtma yeni shard alanı gerektirmedi), **F7-17**
(damıtma değer hedefi 6 sınıflı dağılım değil skaler equity; kalibrasyon terimi
kapatılır, bu yüzden CE/MAE sütunları kollar arasında karşılaştırılamaz).

**F7-10 dördüncü kez tekrarlandı:** ilk denemede iki kolun `model_v1.onnx`
dosyaları bayt bayt aynı çıktı, çünkü `train_v2.py` ONNX'i eğitimden **önce**
yazar. Doğru yol `ml/export_ckpt.py` ile checkpoint'ten aktarmaktır.

### 23.5 Açık kalan

- **Test 102 kararlı değil.** Tekrar için ≥ 200 oyun (damıtma kolu 2,87 h) ve
  ≥ 500 val pozisyonu gerekir. Bu tamamlanana kadar §5.4'ün kazanç iddiası
  kanıtlanmış sayılmaz.
- **F7-03 sansürü.** 3/4-ply'de modelin hamlesi `hint` ilk-10 listesinde
  değilse pozisyon **sansürlü** sayılır; kapsama ~%80,5. F-A9 kapısı %99 ister.
- **F7-04 yöntem değişimi.** 2-ply hakemi `eval`, 3/4-ply hakemi `hint`; her
  rapor `methodNote` taşımalı.

---

## 24. Aşama C+ — Pipeline sağlığı teşhisi (F7-20)

Dış incelemenin 1.1 maddesi ("sorun ölçek değil, pipeline") **ölçüldü**.
`ml/pipeline_health.py` yedi bağımsız kapı tanımlar ve mevcut artifact'lardan
tek bir teşhis üretir. Test 126 (`ml/tests/test_pipeline_health.py`, **117
test**) her kapı sınırını, dört teşhis sonucunu ve CLI çıkış kodlarını doğrular.

### 24.1 Kapılar ve ölçülen değerler

| Kapı | Ölçüt | Değer | Sonuç |
|---|---|---|---|
| `G1` | PipBot kazanma oranı ≥ 0,90 | 0,9950 | **GEÇTİ** |
| `G2` | Kalibrasyon eğimi [0,85; 1,15] | 0,6743 | **DÜŞTÜ** |
| `G3` | Kalibrasyon MAE < 0,15 | 0,2683 | **DÜŞTÜ** |
| `G4` | Korelasyon > 0,90 | 0,9016 | **GEÇTİ** |
| `G5` | Std oranı [0,85; 1,15] | 1,3371 | **DÜŞTÜ** |
| `G6` | 2-ply ER < 0,02 | 0,0740 | **DÜŞTÜ** |
| `G7` | `std(hedef)/std(terminal)` > 0,5 | 3,0227 | **GEÇTİ** |

**Teşhis: `pipeline`.** Model PipBot'u %99,5 yeniyor, hedefleri çökmüyor
(`G7` = 3,02), sıralaması doğru (`G4` = 0,90) — ama değer kafası kalibre
değil. Yani model doğru yönü biliyor, **yanlış büyüklükte** puanlıyor.

### 24.2 Karar kuralı

`G1` düşerse `temel`. `G1` geçip `G2`/`G3`/`G4`/`G5`/`G7`'den biri düşerse
`pipeline`. Hepsi geçerse `saglikli`. **`G1`–`G5` ve `G7`'nin hepsi ölçülmüş ve
geçmiş olmadan `saglikli` denmez** — ölçülmemiş kapı varken "sağlıklı" demek
sahte bir güvencedir; o durumda teşhis `bilinmiyor`dur. `G6` (ER) bu kuralın
dışındadır: ER bir **güç** ölçümüdür. Yalnızca `G6` düşerse `strength_gap`
işareti konur ve teşhis `saglikli` kalır.

### 24.3 G7'nin ölçülmesi

`G7` shard'lardan hesaplanır: `replay.build_value_samples` ile TD(λ) hedefleri
üretilir, aynı kararların terminal değerleriyle karşılaştırılır. `V_hat`
verilmezse hedefler tam olarak `±z` olur ve oran yapısal olarak 1 çıkar — yani
**bilgi taşımaz**. Bu yüzden `--model` zorunludur. Ölçümde
`ml/runs/stage_d_l2/checkpoints/ckpt_v30.pt` kullanıldı: 1 108 karar, hedef std
1,3542, terminal std 0,4480, oran **3,0227**.

### 24.4 Sonuç

Ölçek (large profil, 10⁵ oyun) bu teşhis altında **yanlış kaldıraçtır**. Önce
hedef/kayıp/kalibrasyon hattı onarılmalıdır. Bu, F7-13'ün doğal devamıdır:
eğim hatası çıkarımda onarılabilir, MAE hatası **eğitimde** onarılmalıdır.

Çıktılar: `ml/artifacts/pipeline_health.json`, `ml/artifacts/pipeline_health.md`.

## 25. Aşama C+ — gnubg öğretmen deneyi (F7-21)

### 25.1 Soru

Dış inceleme (madde 1.3) en büyük kaldıracın **gnubg 2-ply etiketleri** olduğunu
öne sürdü: etiketlerle ER 0,03'ün altına iniyorsa dar boğaz **pipeline**,
inmiyorsa **kapasite**. Bu, §24'ün (`pipeline` teşhisi) doğal devamıdır.

### 25.2 İlk kurgu ve neden yanlıştı

`ml/gnubg_distill.py` ilk sürümü yalnızca **değer kafasını** eğitti. 1 200
pozisyon, 2-ply, 2 000 adım: eğitim MAE **0,0072**, korelasyon **0,9996**,
eğim **1,0026**. Ölçülen ER: **0,0708** (öncesi 0,0740) — %4.

**Neden:** ER **politika** başı argmax ile ölçülür
(`gnubg_er.score_afterstates`, `criterion="policy"`). Değer kafası bu yolda
okunmaz. Değer kafasını mükemmel eğitmek ER'yi **tanımı gereği** değiştirmez.

### 25.3 Düzeltme — politika damıtma

`label-policy` / `train-policy` alt komutları eklendi:

1. `afterstate_case` yasal afterstate kümesini **sıralı** üretir (küme sırası
   koşular arası değişirse `best_index` kayar ve eğitim sessizce bozulur).
2. gnubg `hint` hamleleri `gnubg_hint.map_hints` ile bu kümeye eşlenir.
3. En iyi hamlenin indeksi **politika hedefi** olur.
4. Kayıp: `CE(logits, best) + 0,5 · MSE(equity(best), best_equity)`.

### 25.4 Ölçülen sonuç

| Ölçüm | Değer |
|---|---|
| Pozisyon | 2 000 (2-ply, seed 7) |
| Aday ortalaması | 22,4 |
| Adım / lr / batch | 4 000 / 3e-4 / 64 |
| Eğitim top-1 | 1,0000 (**ezber**) |
| Kayıp | 0,564 → 0,00055 |
| **VAL-ER (öncesi)** | **0,0740** |
| **VAL-ER (sonrası)** | **0,0533** |
| İyileşme | **%28,0** |
| Standart hata | 0,0108 |

### 25.5 Karar

`distill_verdict(0,0740, 0,0533)` → **`kismi`** (nokta tahmini kuralı). Bu
karar §28'de **`belirsiz`** olarak düzeltildi: eşleştirilmiş test GA95'i
sıfırı dışlamıyor. Aşağıdaki tablo nokta tahminleridir, kanıt değildir.

### 25.6 Yan bulgu — `random_positions` hatası

10 000 pozisyonluk koşu `IndexError` ile düştü:
`tools/reference_gen.py` içindeki `random_positions` içinde `legal_after_states` "büyük zar
kuralı" dalında `max_steps > 0` ama `states` **boş** dönebiliyor, ve
`rng.choice(sorted(states))` boş listede patlıyor. Düzeltme:
`if max_steps == 0 or not states`. Bu, 2 000 pozisyonluk koşuda **görünmedi**
(şans); 10 000'de ortaya çıktı.

### 25.7 Çıktılar

`ml/artifacts/gnubg_distill_er.json`, `ml/artifacts/gnubg_policy_er.json`,
`ml/artifacts/gnubg_policy_er_10k.json`,
`ml/artifacts/gnubg_distill_verdict.json`, `ml/artifacts/gnubg_distill.md`.

## 26. Maç gücü analizi (F7-22)

### 26.1 Soru

Faz 6'da 400 oyunla "2-away %40,0 vs %39,5" gibi ifadeler yazıldı. Bu ölçüm
mü, gürültü mü? ppg neden yok?

### 26.2 Yöntem

`ml/match_power.py` her iddiayı **gerekli n** ve **saptanabilir en küçük fark**
olarak yazar. Hiçbir sayı iddia değildir.

### 26.3 Ölçülen sonuçlar (p = 0,55, σ_ppg = 2,4, n = 400)

| İddia | Gereken n |
|---|---|
| Kazanma oranı ±0,05 | 381 |
| ppg ±0,10 | 2 213 |
| ppg ±0,05 | 8 851 |
| Şampiyonu yenme (kol başına) | 1 565 |
| ppg farkı (kol başına, Δ = 0,10) | 9 042 |
| Maç kazanma oranı ±0,05 | 381 |

400 oyunda yarım genişlik p = 0,55'te **0,0488**, p = 0,50'de **0,0490**.
İncelemenin örneği olan **0,005**'lik fark bunun **~1/10'u** (oran 9,8×):
**ölçülemez**.

### 26.4 Karar kuralı

Bir fark yarım genişlikten küçükse **rapor edilemez**. `build_report` bunu
`notes` içinde `olculemez` ve oran `x` olarak yazar. Sessizce yazmak yasaktır.

### 26.5 Dürüstlük notları

* σ_ppg = 2,4 **tahmindir**; gerçek değer `--sigma` ile verilmelidir.
* İki oran testi **bağımsız** örnek varsayar; aynı rakibe karşı seri korelasyon
  gerçek gerekli n'i **büyütür** — sayı bir **alt sınırdır**.
* MET yalnızca **okunur**; maç stratejisi (küp) ölçülmez.

### 26.6 Çıktılar

`ml/artifacts/match_power.json`, `ml/artifacts/match_power.md`.

## 27. Kapsam ayrımı — Faz 7 güç, Faz 8 ürün (F7-23)

Dış inceleme (madde 1.5) haklıydı: 8 ürün özelliği ile güç hedefi aynı fazda
olamaz. `faz 7.md` kural 16 ve §8.0 eklendi:

| Karar | Değer |
|---|---|
| Faz 7 kapsamı | Yalnızca güç |
| Faz 7 kapsam dışı | Aşama G'nin 8 özelliği (Test 111–118) |
| Faz 8 kapsamı | Aşama G + ürünleştirme, güç kapısı sonrası |
| Bloke etme | Güç tutmazsa ürün **başlamaz** |
| Test 111–118 | **Rezerve**; Faz 7'de koşulmaz |
| Bütçe | **~45 → ~40 gün** (`medium`), **~96 → ~91 gün** (`large`) |

Ürün gücü **artırmaz**, yalnızca mevcut gücü kullanılabilir kılar. Bu yüzden
ertelemek şampiyon iddiasını zayıflatmaz; tersi doğrudur — güç tutmadan yazılan
ürün **ölçülmemiş bir modeli** paketler.

## 28. Eşleştirilmiş test — %28'lik iyileşme kanıtlanmadı (F7-24)

### 28.1 Soru

§25'te politika damıtma VAL-ER'yi 0,0740 → 0,0533'e indirdi ve "%28,0
iyileşme" yazıldı. Bu bir **kanıt** mı, bir **nokta tahmini** mi?

### 28.2 Yöntem

İki ölçüm **aynı 70 pozisyonda** yapıldı (`er_harness measure --split val`).
Bu, eşleştirilmiş (paired) test yapmayı mümkün kılar ve pozisyon zorluğundan
gelen varyansı eler. `ml/gnubg_distill.py` içine `load_er_losses` +
`paired_loss_test` eklendi; `distill_verdict` artık `paired` parametresi alır.

### 28.3 Ölçülen sonuç (n = 70, aynı pozisyonlar)

| Karşılaştırma | Ortalama fark | GA95 | t | Sıfırı dışlıyor |
|---|---|---|---|---|
| değer kafası → politika 2 000 | +0,0176 | [−0,0062; +0,0414] | +1,45 | **hayır** |
| değer kafası → politika 10 000 | +0,0091 | [−0,0209; +0,0392] | +0,59 | **hayır** |
| politika 2 000 → politika 10 000 | −0,0084 | [−0,0318; +0,0149] | −0,71 | **hayır** |

### 28.4 Karar

`distill_verdict(0,0708, 0,0533, paired=...)` → **`belirsiz`**. Yeni karar
etiketi `VERDICT_UNPROVEN` (CLI çıkış kodu 4). Kural: `paired` verildiğinde ve
GA95 sıfırı dışlamıyorsa nokta tahmini **kanıt sayılmaz**; `kismi`/`kapasite`
kararı verilmez.

### 28.5 İkinci bulgu — veri hacmi işe yaramadı

2 000 → 10 000 pozisyon (5×), aynı epoch sayısı (128) ile ER
**0,0533 → 0,0617**: daha **kötü**. Fark anlamlı değil (t = −0,71) ama
**monoton iyileşme de yok**. "Kapasite payı" iddiası bu ölçekte veriyle
desteklenmiyor. 10 000 pozisyon 5 064 s'de etiketlendi (0 atlandı, aday
ortalaması 22,8). Eğitim top-1 her iki kolda da 1,0000: darboğaz kapasite
**değil**.

### 28.6 Gereken n

Gözlenen fark (0,0176) ve eşleştirilmiş SD (0,1016) ile %80 güç için gereken
n ≈ **264** pozisyon (tek yönlü, α = 0,05). Mevcut 70, bunun %27'si. Karar
için en az 264, güvenli olması için ~400 pozisyon gerekir.

### 28.7 Dürüstlük notları

* Eşleştirilmiş test normal yaklaşım kullanır (z = 1,96). t dağılımı kritik
  değeri 2,00'dir; t = 1,45 her iki durumda da anlamsızdır.
* 70 pozisyon `reference_positions.json`'dan gelir ve **sabittir**; n artırmak
  korpusu büyütmek demektir, ayrı bir iştir.
* 10 000 pozisyonluk koşu, 2 000'lik koşunun **üst kümesidir** (aynı seed 11).
  İki kol arasındaki tek fark hacim ve adım sayısıdır (ikisi de 128 epoch).
* §25.5'teki `kismi` kararı, nokta tahminini kanıt sayan bir hataydı. Bu
  bölüm onu düzeltir; §25.5 artık §28'e atıf yapar.

### 28.8 Çıktılar

`ml/artifacts/gnubg_distill_verdict.json` (karar `belirsiz`),
`ml/artifacts/gnubg_distill.md` (§4.1 eşleştirilmiş test, §4.2 veri hacmi
kolları), `ml/artifacts/gnubg_policy_er_10k.json`.

## 29. Kod denetimi — 15 kusur, kanıtla doğrulama (F7-25 – F7-37)

`faz 7 v2.md` on beş kusur bildirdi. Her iddia **kaynak koda karşı** doğrulandı;
hiçbiri satır numarasına güvenilerek uygulanmadı. Sonuç: **13 düzeltme**,
**1 zaten doğru**, **1 iddia yanlış**.

### 29.1 Kritik

| # | İddia | Karar | Kanıt |
|---|---|---|---|
| 1 | `StatePool.Return` `Reset()` çağırmıyor | ✅ gerçek | Havuzdan alınan durum eski taşır; test kırmızı |
| 2 | Sahiplik kontrolü yok | ✅ gerçek | Tek kontrol `_available >= Length`, yani kapasite |
| 3 | `AfterStateList` kapasitesi 2048 yetmiyor | ✅ gerçek | Ölçülen en kötü tahta **2139** afterstate (1-1) |

**HATA 3 ölçümü.** 200 000 rastgele pozisyonda en fazla **576** afterstate
(2-2) görüldü; hiçbiri 1024'ü aşmadı. Rastgele örnekleme bu yüzden kusuru
göstermez. Parça sayısını koruyan tepe-tırmanma araması (420 s, 93 yeniden
başlatma) **2139**'a ulaştı: tahta
`0,-10,1,1,1,-1,1,1,1,-1,1,1,-1,1,1,0,1,1,0,1,1,-1,1,0,-1,0`, zar 1-1.
2139 bir **alt sınırdır**, teorik maksimum değil. `DefaultCapacity` 2048 → **4096**
(~1,9× pay) ve `MeasuredMaxAfterStates = 2139` sabiti eklendi; regresyon testi
tam bu tahtayı kurup `Count == 2139` doğrular.

### 29.2 Orta

| # | İddia | Karar | Not |
|---|---|---|---|
| 4 | Dizi tamponu `AfterStateList`'ten küçük | ✅ gerçek, ama yön güvenli | `SeqBufCapacity` 65 536 > 4096; `SequenceBufferCapacity` açıldı, test invariant'ı kilitledi |
| 5 | Terminal `ResultPoints` küp değerini içeriyor | ❌ zaten doğru | `IsGameOver` yalnız `IsTerminal` iken çağrılır; test eklendi |
| 6 | `StateFromJson` `phase` alanını yok sayıyor | ✅ gerçek | `phase` opsiyonel okunur; sayı 0-5 veya ad kabul edilir |
| 7 | `DefaultModelPath` sessizce fixture'a düşüyor | ✅ kısmen | Yorum vardı, uyarı yoktu; iki `Console.Error` uyarısı eklendi |
| 8 | `SelfPlayAgent` her hamlede `BackgammonState` ayırıyor | ❌ **iddia yanlış** | Sınıf hiç `BackgammonState` tutmuyor; `SelfPlayRunner` alan olarak taşır |
| 9 | `AddPass` hash'i doğrulamadan kopyalıyor | ✅ gerçek | `[Conditional("DEBUG")] VerifyHash` eklendi |
| 10 | `_gen` taşması koruması hiç ateşlenmiyor | ✅ gerçek | `int` taşması `int.MinValue`'ya gider, 0'a asla; `uint`'e çevrildi |
| 11 | `BuildBenchList` gereksiz 4096 ayırıyor | ✅ gerçek | `new AfterStateList()` |
| 12 | `DiceAveragedEquity` her çağrıda `SearchWorkspace` ayırıyor | ✅ gerçek | `[ThreadStatic]` yeniden kullanım + `Reset()` |
| 13 | `RunCrawford` sabit 0,9 equity kullanıyor | ⚠️ ölçüm tercihi | Sabit equity senaryoları deterministik yapar; `--model` opsiyonu **eklendi**, varsayılan değişmedi |

### 29.3 Küçük

| # | İddia | Karar | Not |
|---|---|---|---|
| 14 | `Swap` paralel dizileri belgelendirmiyor | ✅ gerçek | `<remarks>` eklendi; `BoardOf` salt-okunur |
| 15 | `StepBuf` derinlik sınırını kontrol etmiyor | ✅ gerçek, erişilemez | `MaxSequenceLength` zaten koruyor; yine de açık koruma eklendi |

### 29.4 Düzeltilmeyen iki madde

* **HATA 5** zaten doğruydu. `GenerateAfterStates` adımları doğrudan uygular ve
  `IsGameOver`'i yalnız `output.IsTerminal[index]` iken çağırır. Davranış bir
  testle sabitlendi (küp 1/2/4/8 için `ResultPoints == 1`).
* **HATA 8** yanlıştı. `SelfPlayAgent` yalnız `SearchWorkspace` ve
  `OnnxPolicyValueEvaluator` tutar. `SearchTests.Test10_ZeroAllocation`
  ısınma sonrası sıfır ayırma zaten kanıtlıyor. **Kod değişmedi.**

### 29.5 Kapsam dışı bulgu

`crawford` koşusu **5/6** veriyor: `normal-double-pass` (5-away/5-away, E = 0,9)
`shouldDouble = false` dönüyor. `git stash` ile **HEAD'de de 5/6** olduğu
doğrulandı — önceden var olan bir kusur, bu denetimin kapsamı dışında (F7-35).
Ayrı bir `EquityCubeAdvisor` işi gerektirir.

### 29.6 Doğrulama

```
Backgammon.Tests             297/297   (29 dk 56 s)
Backgammon.Inference.Tests   100/100
Backgammon.UI.Tests           88/88
ml/tests                    1386/1386  (3 yavaş/koşullu test atlanır)
```

Toplam **1871**. Derleme 0 uyarı / 0 hata.


## 30. Faz 7-R Aşama R-B — ölçüm altyapısı (F7-55 – F7-62)

`faz 7 v2.5.md` §8 yalnızca R-A ve R-B'yi istiyor; R-C onay alınmadan
başlamayacak. Ayrıntılı rapor: `ml/artifacts/stage_r_b_report.md`.

### 30.1 Ne değişti

| Yol | Tür | Ne yapar |
|---|---|---|
| `ml/corpus2.py` | yeni | Korpus v2: katmanlı faz seçimi, **oyun düzeyinde** bölünme, ayna-kanonik sızıntı filtresi, `gameId`/`ply`/`source`, gerçek oyun faz payları, güç tablosu |
| `ml/er_paths.py` | yeni | ER'yi **üç oynanış yolu** için ayrı ölçer; bootstrap %95 GA, faz ve kaynak kırılımı, ağırlıklı ER, σ üst sınırından güç tablosu |
| `ml/tests/test_corpus2.py` | yeni | Test 128–133 (17 test) |
| `ml/artifacts/reference_corpus_v2.json` | yeni | 1000 pozisyon, digest `e0466b9e…` |
| `ml/artifacts/er_paths_v1.json` / `er_paths_v2.json` / `er_paths_v2_val.json` | yeni | Üç yol ölçümleri |

### 30.2 Korpus v2

| Alan | Değer |
|---|---|
| Pozisyon | **1000** |
| Faz | contact **600** (%60,0) · bar 250 · race 150 · bearoff 0 · closed 0 |
| Kaynak | gnubg 2-ply self-play **664** · kendi model self-play **286** · rastgele **50** (%5,0) |
| Oyun | 43 |
| Bölünme (oyun düzeyinde) | cal 300 / val 350 / test 350 |
| Sızıntı filtresi | 9 652 eğitim hash'i → **26 tahta çıkarıldı** |
| Teşhis kümesi | 1 566 (başlık ER'sine girmez) |
| Digest | `e0466b9e673dca6cbdd05d8246730deea9371fa9a425055db715e8390e4a97b8` |

Gerçek oyun faz payları **ölçüldü**: contact 0,5564 · bar 0,3706 · race 0,0730.

**Bulunan hata:** ilk sürüm bölünmeyi faz içinde yapıyordu; bir oyun birden çok
fazda pozisyon taşıdığı için aynı oyun hem CAL hem TEST'e düşüyordu
(`verify_corpus2` 300+ ihlal). Düzeltme: bölünme tek seferde, oyun düzeyinde.

### 30.3 ER — üç yol (model_v30, gnubg eval 2-ply, bootstrap 20 000)

| Korpus | Yol | n | Ortalama | %95 GA | σ üst | Ağırlıklı |
|---|---|---|---|---|---|---|
| **v2** | `policy` | 1000 | **0,0402** | [0,0350; 0,0457] | 0,1025 | 0,0434 |
| **v2** | `value` | 1000 | **0,0442** | [0,0384; 0,0504] | 0,1130 | 0,0478 |
| **v2** | `search1` | 1000 | **0,0210** | [0,0181; 0,0240] | 0,0540 | 0,0221 |
| v1 | `policy` | 200 | 0,0740 | [0,0594; 0,0893] | 0,1241 | — |
| v1 | `search1` | 200 | 0,0515 | [0,0382; 0,0659] | 0,1180 | — |

v1 `policy` = **0,0740**, tarihsel `stage_h_er_2ply.json` değeri **0,073970**
ile aynı — yeni harness eski ölçümü birebir yeniden üretiyor.

**Üretim yolu `search1`** (`ProductionDepthPly = 1`) ve ER **0,0210**; bugüne
kadar raporlanan 0,0533/0,0617'den belirgin biçimde iyi (F7-46'nın nicel
sonucu).

### 30.4 v1 ↔ v2

| Yol | v1 | v2 | Fark | z | %95 GA | Sıfır dışı |
|---|---|---|---|---|---|---|
| `policy` | 0,0740 | 0,0402 | **−0,0338** | −4,13 | [−0,0498; −0,0178] | evet |
| `value` | 0,0746 | 0,0442 | **−0,0304** | −3,52 | [−0,0473; −0,0135] | evet |
| `search1` | 0,0515 | 0,0210 | **−0,0305** | −4,22 | [−0,0447; −0,0163] | evet |

v1 korpusu ER'yi `policy` yolunda **%84 göreli** abartıyordu. Karşılaştırma
eşleşmemiş ve faz karışımı farklı; ayrıştırma R-C'ye bırakıldı (Kural 7).

### 30.5 Güç tablosu (σ **üst** sınırından, Kural 4)

| Korpus | Yol | σ üst | n (Δ=0,01) | n (Δ=0,02) | mevcut n | Δ=0,01 yeterli |
|---|---|---|---|---|---|---|
| v2 | `policy` | 0,1025 | **285** | 72 | 1000 | evet |
| v2 | `value` | 0,1130 | **346** | 87 | 1000 | evet |
| v2 | `search1` | 0,0540 | **79** | 20 | 1000 | evet |
| v1 | `policy` | 0,1241 | 418 | 105 | 200 | **hayır** |

v1'in 200 pozisyonu Δ=0,01 için hiçbir yolda yeterli değildi. R-14'ün
düzeltilmiş hali: doğru sayı **285** — "264" değil.

### 30.6 R-Q3 — vektörleştirici tutarlı, **model değil**

`gnubg_er.vectorize` ayna tutarlılığı **40/40 doğru**; F6-31 sınıfı hata yok.
Ama modelin değer çıktısı **antisimetrik değil**:

| Ölçüm | Değer | Beklenen |
|---|---|---|
| `corr(e(+1), e(−1))` | **−0,7019** | −1,0000 |
| ortalama `\|e(+1)+e(−1)\|` | **1,0044** | 0,0000 |
| politika argmax iki perspektifte aynı | **1/59** | 59/59 |

Neden: `ml/train_v2.py`'de `flip_exclusive` yalnızca TD(λ) hedef zincirinde
kullanılıyor; girdi vektörü için perspektif artırımı **yok**. Naif düzeltme
(logit ortalaması) ER'yi kötüleştirdi (0,0500 → 0,1674); doğru yol eğitimde
artırımdır → R-D maddesi.

### 30.7 R-Q4 — `random_positions`

Hamle seçimi `rng.choice(sorted(states))` → yasal afterstate'ler üzerinde
**tekdüze**. İki ölçülmüş kusur: (1) her ply'de `p = 0,5` örnekleme erken
ply'leri aşırı temsil ediyor (`ply < 10` %14,0, medyan 34); (2) v1'in 200
benzersiz tahtasından **yalnızca 1'i** (%0,50) damıtma çıktısında — R-13 doğru
ama etkisi küçük, sızıntı aynı **dağılım** üzerinden.

### 30.8 On-policy iyimserlik ölçüldü (v2 VAL, n=350)

| Yol | gnubg2 | self | self/gnubg2 |
|---|---|---|---|
| `policy` | 0,0484 | 0,0433 | 0,90 |
| `value` | 0,0637 | 0,0382 | **0,60** |
| `search1` | 0,0227 | 0,0096 | **0,42** |

`self` her yolda daha düşük ER veriyor; `search1`'de fark **2,4×**. Başlık
ER'si bir **alt sınır** olarak okunmalı; `gnubg2` sütunu muhafazakâr referans.

### 30.9 gnubg etiketleme maliyeti

Tek çekirdek 2-ply `hint`: ortalama **0,562 s**/pozisyon. 4 süreçte
**4,696 poz/s** (2,6× ölçekleme). 10 000 pozisyon ≈ 36 dk; 50 000 ≈ 3,0 sa.
`faz 7.md` §5.1.1'deki "8× hızlanma" varsayımı **desteklenmiyor**.

### 30.10 Doğrulama

```
ml/tests                    1386/1386  (3 yavaş/koşullu test atlanır)
```

Test 128–133 yeşil. `test_docs_consistency.py` 21/21 yeşil.

---

## 31. Faz 7-R Aşama R-C — teşhis hattı onarımları (F7-63 – F7-71)

`faz 7 v2.5.md` §4 Aşama R-C, maddeler 1–5. Amaç: ölçüm hattındaki **ölçüm
hatalarını** gerçek arızalardan ayırmak ve karar fonksiyonlarını Kural 3'e
uygun hâle getirmek.

### 31.1 G7 iki modda, iki taraflı (madde 1)

`ml/pipeline_health.py`:

* `signed_terminal_series(z, decision_indices, n_decisions)` — terminal değeri
  **karar başına işaretli** hâle getirir (`(-1)^(n-t) · z`), `td_lambda_targets`
  zinciriyle birebir aynı.
* `spread_from_shards` artık işaretli terminal kullanır; eski (hatalı)
  karşılaştırma `legacyRatio` alanında **kayıt için** durur.
* `TARGET_STD_RATIO_MAX = 1,5` eklendi; bant **kapalı** aralık `[0,5; 1,5]`.
* `TargetSpread` yeni alanlar: `signed`, `legacyTerminalStd`, `legacyRatio`.

**Ölçüm** (`it1_0000.bgsp.gz`, 627 737 örnek, `ckpt_v15.pt`,
`ml/artifacts/g7_modes.json`):

| Mod | Oran (işaretli) | Eski oran | Hedef std | Terminal std | Sonuç |
|---|---|---|---|---|---|
| λ=1, model yok | **1,000000** | 2,8781 | 1,4839 | 1,4839 | GEÇTİ |
| λ=1, model var | **1,000000** | 2,8781 | 1,4839 | 1,4839 | GEÇTİ |
| λ=0,7, model yok | 0,176031 | 0,5066 | 0,2612 | 1,4839 | **DÜŞTÜ** |
| λ=0,7, model var | 0,682135 | 1,9633 | 1,0122 | 1,4839 | GEÇTİ |

λ=1'de oran **tam olarak 1** — hedefler terminal değerlerin kopyasıdır.
λ=0,7 + model yok: hedefler sıfıra çöker → 0,176; kapı bunu **doğru** yakalar.
λ=0,7 + model var: `V̂` hedefleri taşır → 0,682, bantta.

**Sonuç:** 3,0227 bir çökme değil, **birim uyumsuzluğuydu** (işaretsiz
`resultPoints/cubeValue` vs işaretli TD hedefi). G7 artık **1,0000 ile GEÇTİ**.

### 31.2 G5 onaylanmış banda döndü (madde 2)

`Faz 6 v3.md` §6.3 ve §13.2: `0,7 ≤ oran ≤ 1,4`. Kodda `0,85–1,15` vardı ve
gerekçesi hiçbir belgede yoktu (R-09).

| Bant | 1,3371 | 2,78 (Faz 5) |
|---|---|---|
| Faz 6: [0,7; 1,4] | **GEÇTİ** | DÜŞTÜ |
| Faz 7 sıkı: [0,85; 1,15] | DÜŞTÜ | DÜŞTÜ |

`STD_RATIO_MIN/MAX` → `0,7 / 1,4`; sıkı bant `STD_RATIO_LEGACY_MIN/MAX` olarak
kayıt için durur ve her kapı notunda raporlanır.

### 31.3 `distill_verdict` yeniden yazıldı (madde 3)

`ml/gnubg_distill.py`:

* `paired_er_test(before, after, *, resamples=20000, seed=...)` — eşleştirilmiş
  fark **ve** `er_after`'ın **mutlak** bootstrap %95 GA'sı.
* `distill_verdict(..., paired, required_n)` — sıra: `bilinmiyor` → `belirsiz`
  (paired yok) → `veri-yetersiz` (n < required_n) → `pipeline`
  (`ciHighAfter ≤ target`) → `kısmi` (GA sıfırı dışlıyor ve `meanDiff > 0`) →
  `belirsiz`.
* `VERDICT_INSUFFICIENT_DATA = "veri-yetersiz"` (yeni).
* `VERDICT_CAPACITY` **artık üretilmiyor**; metni "Kaldırıldı" diye başlıyor.
* `distill_verdict_detail(...)` — `capacityInference: false` alanı.
* CLI: `--required-n`; çıkış kodu **5** = `veri-yetersiz`.

### 31.4 `ml/learning_curve.py` (madde 4)

Yeni modül. Aynı hat, aynı tohum, yalnızca veri hacmi: N, 2N, 4N, 8N.

* `CurvePoint` — `multiplier`, `positions`, `losses` (pozisyon düzeyinde, üç
  yol), `slope`, `mae`, `inSampleLoss`, `heldOutLoss`.
* `fit_log_slope(points, path, resamples, seed)` — OLS eğimi + **pozisyon
  düzeyinde** bootstrap %95 GA. `gain = -slope` (pozitif = ER düşüyor).
* `run_curve(sizes, train_fn, seed, ...)` — enjekte edilebilir eğitim hattı.
* `CurveReport.decision` — `ölçek` / `pipeline` / `belirsiz` / `veri-yok`.
* `CurveReport.scaling_summary()` — `diagnose(scaling=...)` için özet.
* `build_markdown`, CLI (`--base-positions`, `--multipliers`, `--out`).

> Gerçek eğitim hattı **henüz bağlanmadı**; `main()` bilerek `SystemExit` atar.
> Gerçek koşum R-D'de yapılacak.

### 31.5 `scaling_evidence` alanı (madde 5)

`HealthReport.scaling_evidence` → `yok | eğim<ε | eğim≥ε`;
`scaling_note` gerekçeyi ve GA kesişmesini yazar; `to_dict()` içinde
`scalingEvidence` / `scalingNote` / `scaling`. CLI: `--scaling <json>`.
`ε = 0,005` (`SCALING_SLOPE_EPSILON`).

`yok` **"ölçek işe yaramaz" demek değildir**; "ölçülmedi" demektir.

### 31.6 Onarılmış teşhis

`ml/artifacts/pipeline_health_r_c.json`:

| Kapı | Etiket | Değer | Sonuç | Önce |
|---|---|---|---|---|
| G1 | PipBot kazanma oranı ≥ 0,90 | 0,9950 | GEÇTİ | GEÇTİ |
| G2 | Kalibrasyon eğimi [0,85; 1,15] | 0,6743 | **DÜŞTÜ** | DÜŞTÜ |
| G3 | Kalibrasyon MAE < 0,15 | 0,2683 | **DÜŞTÜ** | DÜŞTÜ |
| G4 | Korelasyon > 0,90 | 0,9016 | GEÇTİ | GEÇTİ |
| G5 | Std oranı [0,7; 1,4] (Faz 6) | 1,3371 | **GEÇTİ** | DÜŞTÜ (yanlış bant) |
| G6 | 2-ply ER < 0,02 | 0,0740 | **DÜŞTÜ** | DÜŞTÜ |
| G7 | Hedef saçılımı [0,5; 1,5] | 1,0000 | **GEÇTİ** | GEÇTİ (yanlış ölçüm) |

Teşhis **`pipeline`** (değişmedi), ama artık **üç** gerçek arıza var:
kalibrasyon eğimi, kalibrasyon MAE, ER. Önceki raporda G5 ve G7 de "düşen"
görünüyordu; ikisi de **ölçüm hatasıydı**.

### 31.7 Testler

| Test | Ad | Dosya | Durum |
|---|---|---|---|
| 134 | `G7_TwoSided` (+ G5 Faz 6 bandı) | `ml/tests/test_stage_r_c.py` | YEŞİL |
| 135 | `G7_Lambda1_RatioIsOne` | `ml/tests/test_stage_r_c.py` | YEŞİL |
| 136 | `Verdict_PairedFirst` | `ml/tests/test_stage_r_c.py` | YEŞİL |
| 137 | `Verdict_NoCapacityInference` | `ml/tests/test_stage_r_c.py` | YEŞİL |
| 138 | `LearningCurve_Runs` | `ml/tests/test_stage_r_c.py` | YEŞİL |

`pytest ml/tests` → **1375 passed, 3 skipped** (1222 toplandı; R-B'de 1159).
`test_docs_consistency.py` → 21/21.

### 31.8 Test numarası çakışması (düzeltildi)

R-B'de `test_corpus2.py` Test 127–132 olarak numaralandı; ancak
`ml/tests/test_gnubg_distill.py` **zaten** "Test 127" başlığını taşıyordu
(`f8b9917`). Son test numarası 127'ydi, yani R-T1 = **128** olmalıydı.
Düzeltildi: `test_corpus2.py` → Test 128–133, R-C testleri → Test 134–138.

### 31.9 Açık noktalar

1. **G7 üst sınırı (1,5) onay bekliyor** (Kural 2).
2. **Gerçek öğrenme eğrisi koşulmadı** — `scaling_evidence = yok`.
3. `er_paths.search1` Python, C# `BackgammonSearch` değil — parite kanıtlanmadı.
4. `er_paths.terminal_equity` C# `IsGameOver` ile doğrulanmadı.
5. R-02 / R-03 / R-06 / R-17 / F7-55 → R-D'de.
6. R-Q1 (GPL) ve R-Q5 (G7 λ/terminal birimi) açık; R-Q5 **kısmen**
   yanıtlandı (birim uyumsuzluğu kanıtlandı ve düzeltildi). R-Q2 **kapandı**
   (§43, F7-114): `hint` altı olasılığı zaten veriyor, artık ayrıştırılıyor.
7. `degisenler.zip` hâlâ izlenmiyor.

### 31.10 Sonraki aşama

**R-D — gnubg öğretmen hattı yeniden tasarımı.** Önkoşul: bu raporun onayı.

---

## 32. Faz 7-R Aşama R-C ek — küp kararı ER'si (F7-72 – F7-77)

### 32.1 Neden ayrı bir eksen

Bütün hamle ER'si ölçümleri **küpsüzdür**. Dünya şampiyonu seviyesi küp
kararlarını da gerektirir; küp hatası hamle hatasından bağımsızdır ve
toplanmaz. Bu bölüm küp kararını ayrı ölçer.

### 32.2 `crawford` 5/6 → 7/7

`Backgammon.MatchBench crawford` **5/6** veriyordu. Düşen senaryo
`normal-double-pass` (5-away/5-away, E = 0,9) idi.

Kök neden `EquityCubeAdvisor.Decide` içindeki tek taraflı "çok iyi" tanımı:
`tooGood = doublePass > doubleTake && noDouble > doubleTake`. Bu yalnızca
"rakip kabul eder" durumunu yakalar. 5-away/5-away'de E = 0,9'da rakip
**reddeder**; teklif eden 1 puan alır (MWC 0,607) ama oynamaya devam etse
marslarla 0,692 MWC'ye ulaşır. Doğru cevap **çiftlememek**tir — yani
senaryonun beklentisi yanlıştı.

Düzeltme: `doubleValue = min(doubleTake, doublePass)` üzerinden iki taraflı
tanım. `RunCrawford` yeniden yazıldı (senaryo başına `Equity`, 7 senaryo,
`too-good-to-double` eklendi). **Sonuç 7/7.**

| Senaryo | E | Çiftle | Kabul | Doğru |
|---|---|---|---|---|
| `crawford-no-cube` | 0,90 | hayır | evet | ✅ |
| `crawford-no-cube-black` | 0,90 | hayır | evet | ✅ |
| `one-away-cannot-double` | 0,90 | hayır | evet | ✅ |
| `post-crawford-free-drop` | 0,90 | evet | evet | ✅ |
| `normal-double-pass` | 0,30 | evet | hayır | ✅ |
| `too-good-to-double` | 0,90 | hayır | hayır | ✅ |
| `one-away-no-double` | 0,90 | hayır | evet | ✅ |

`ml/artifacts/stage_b_crawford.json` yeniden üretildi (eskisi 6/6 diyordu).

### 32.3 Küp ER'si tanımı

gnubg `eval` üç *cubeful* equity verir. Rakip bizim equity'mizi **minimize**
eder:

```
doubleValue = min(doublePass, doubleTake)
best        = max(noDouble, doubleValue)
cubeLoss    = max(0, best - secilen)
```

**`max` tuzağı.** `max(noDouble, doublePass, doubleTake)` yanlıştır:
`doublePass` her zaman `+1,000` olduğu için her pozisyonda "çiftle" der.
Gerçek çıktıyla doğrulandı — `noDouble 0,216 / doublePass 1,000 /
doubleTake −0,001` → `best 0,216`, `bestAction no-double`,
`loss(no-double) 0,000`, `loss(double) 0,217`.

### 32.4 Ölçüm

Referans sözleşmesi: gnubg `eval`, **2-ply**, cubeful on, küp açık;
`Cubeful equities` bloğu + `Proper cube action` satırı. Korpus: 50 pozisyon
(`--stride 20`) × 4 bağlam × 2 sahiplik = **400 vaka**; faz dağılımı
240 contact / 104 bar / 56 race. Bootstrap 20 000.

| Ölçüm | Değer |
|---|---|
| **Küp ER'si** | **0,0642** |
| %95 GA | [0,0469; 0,0837] |
| sigma | 0,1894 |
| Standart hata | 0,0095 |
| Çiftleme uyumu | 300/400 (0,7500) |
| Kabul/red uyumu | 64/76 (0,8421) |
| Hedef | < 0,0200 → **karşılanmıyor (3,2×)** |

Karışıklık matrisi (çiftleme):

| gnubg \ biz | Çiftleme yok | Çiftle |
|---|---|---|
| **Çiftleme yok** | 242 | **82** |
| **Çiftle** | **18** | 58 |

Hata **asimetrik**: 82 yanlış çiftleme, 18 kaçırılmış çiftleme. Danışman
fazla agresif.

Bağlama göre: para oyunu **0,0284** (uyum 0,81), 5-puan maçı **0,0860**
(0,745), 9-puan maçı **0,0564** (0,70). Sahipliğe göre: merkez **0,0575**
(0,78), bizde **0,0709** (0,72).

Güç (Kural 4, sigma üst sınırı 0,2367): Δ = 0,02 → gereken n **380**
(mevcut 400 yeterli); Δ = 0,01 → **1517** (yetersiz).

### 32.5 Korpusun üç sessiz hatası (düzeltildi)

1. **Crawford bağlamı.** Dördüncü bağlam `(5, 4, 1)` bir Crawford oyunudur;
   orada küp yoktur. 150 vaka sıfır bilgiyle ölçüme giriyordu. Yerine
   `(5, 2, 1)` konuldu; Crawford ayrı doğrulama senaryosu oldu.
2. **Mutlak küp sahipliği.** `cubeOwner = 1` mutlak yazıldığında sıra `-1`
   olan pozisyonlarda küp rakipte kalıyor, `CanOffer` false dönüyordu
   (400 vakanın 68'i). Sahiplik artık göreli: `1` → `turn`, `-1` → `-turn`.
3. **`phase` anahtar çakışması.** Korpus `phase: "contact"` yazıyordu; C#
   `StateFromJson` bunu `GamePhase` sanıp `phase çözümlenemedi: contact`
   ile duruyordu. Anahtar `phaseClass` oldu.

Ayrıca `--stride` eklendi: korpus fazlara göre gruplandığı için düz
`--limit` yalnızca `contact` seçiyordu.

### 32.6 gnubg çıktısı: satırlar sıralanır

gnubg cubeful satırları **sıralar**, sabit numaralamaz. En iyi eylem
"Double, take" ise çıktı `1. Double, take / 2. Double, pass / 3. No double`
olur. Numaraya göre eşleştirme `noDouble` alanına `+0,632` yazıyordu.
Artık etikete göre eşleştirilir; equity satırları `Proper cube action`
satırından **önceki** parçada aranır. Tanınan biçimler: `No double`,
`No redouble`, `Double/Redouble, pass`, `Double/Redouble, take`,
`Too good to (re)double, pass`, `..., beaver`.

### 32.7 Kapsam genişletmesi

| Aşama | Ek kapsam |
|---|---|
| R-C | küp ER'si ölçümü — **tamamlandı** |
| R-D | küp-farkındalıklı damıtma: değer kafası 6'lı dağılımı da öğrenmeli |
| R-E | kapasite testi küp ER'sini de raporlar |
| R-F | güç iddiası **küp dahil**; para + 5-puan + 9-puan ayrı raporlanır |

### 32.8 Testler

| Test | Ad | Dosya | Durum |
|---|---|---|---|
| 139 | `CubeParse_RealOutput` | `ml/tests/test_cube_er.py` | YEŞİL |
| 140 | `CubeParse_RankedOrder` | `ml/tests/test_cube_er.py` | YEŞİL |
| 141 | `CubeParse_Redouble` | `ml/tests/test_cube_er.py` | YEŞİL |
| 142 | `CubeParse_TooGood` | `ml/tests/test_cube_er.py` | YEŞİL |
| 143 | `CubeValue_MinNotMax` | `ml/tests/test_cube_er.py` | YEŞİL |
| 144 | `CubeLoss_NonNegative` | `ml/tests/test_cube_er.py` | YEŞİL |
| 145 | `CubeSummary_Bootstrap` | `ml/tests/test_cube_er.py` | YEŞİL |
| 146 | `CubePower_SigmaUpper` | `ml/tests/test_cube_er.py` | YEŞİL |
| 147 | `CubeCorpus_CrossProduct` | `ml/tests/test_cube_er.py` | YEŞİL |

### 32.9 Açık noktalar

1. **Küp ER'si 0,0642 — hedef 0,02 karşılanmıyor.** Düzeltme R-D/R-E'de.
2. Hata yönü (82 yanlış / 18 kaçırılmış) `HeuristicOutcomeDistribution`'ın
   sabit mars oranlarıyla (contact 0,20 / race 0,05) tutarlı; ölçülmedi.
3. gnubg `cubeinfo` varsayılanı `jacoby: 1`; para oyununda ikincil bir fark
   yaratabilir — ölçülmedi.
4. Δ = 0,01 için n = 1517 gerekiyor; mevcut 400 yetersiz.
5. **G7 üst sınırı (1,5) hâlâ onay bekliyor** (Kural 2).

---

## 33. Faz 7-R — G7 iki modlu kapı (F7-78)

### 33.1 Onaylanan değişiklik

Kullanıcı G7 üst sınırını **1,5** olarak onayladı ve iki koşul koydu:

1. `λ = 1` modları için kapı `|oran − 1| < 1e-6` olmalı ve **"birim/işaret
   testi"** olarak adlandırılmalı.
2. `λ < 1` alt sınırı **λ'dan türetilmeli**, keyfî olmamalı.

### 33.2 Uygulama

| Öğe | Değer |
|---|---|
| `TARGET_STD_RATIO_MAX` | **1,5** (onaylandı) |
| `TARGET_STD_RATIO_UNIT_TOL` | **1e-6** |
| `LAMBDA_UNIT_TOL` | **1e-9** |
| `TARGET_STD_RATIO_MIN` | **kaldırıldı** (0,5 keyfîydi) |
| `target_std_ratio_lower(lam)` | `lam ** (1 / (1 - lam))` |
| `GATE_LABEL_G7_UNIT` | `Birim/isaret testi \|oran-1\| < 1e-6 (lam=1)` |
| `GATE_LABEL_G7_LAMBDA` | `Hedef sacilimi [lam^(1/(1-lam)); 1,5]` |

`λ → 1` için alt sınır `1/e = 0,3679`; `λ = 0,7` için **0,30457**.

### 33.3 Neden türetilmiş alt sınır

TD(λ) hedefi terminal değeri `lam ** (T − t)` ağırlığıyla yumuşatır. Etkin ufuk
geometrik ortalamadır: `h = 1 / (1 − lam)`. Hedefin en az bu kadar terminal
ağırlığı koruması gerekir; bu da oran için `lam ** (1 / (1 − lam))` alt sınırını
verir. Keyfî 0,5 bu gerekçeyi taşımıyordu.

### 33.4 Neden `λ = 1`'de bant yok

`λ = 1` modunda doğru değer **tam olarak 1**'dir: hedef işaretli terminal
serisidir ve terminal de işaretli okunur (F7-63). Bant kullanmak, birim
uyuşmazlığını gizleyen hatayı geri getirirdi. Bu yüzden `λ = 1` modu bir
**birim/işaret testidir**, tolerans testi değil.

### 33.5 Doğrulanan sınıflandırmalar

| Ölçüm | Mod | Sonuç |
|---|---|---|
| 0,176031 (λ=0,7, modelsiz) | λ<1 | **başarısız** (gerçek çökme) |
| 3,0227 (eski anomali) | λ=1 | **başarısız** (üst sınır) |
| 1,000000 (λ=1) | λ=1 | **başarılı** (birim testi) |
| 0,682135 (λ=0,7) | λ<1 | **başarılı** |

### 33.6 Raporlama

`HealthReport.lam` eklendi; `to_dict()["thresholds"]` artık
`targetStdRatioMax`, `targetStdRatioUnitTol`, `targetStdRatioLower` (λ=1 iken
`None`) ve `lam` taşır. `Gate.label` / `Gate.display_label` eklendi; CLI
`--lam` ile beslenir, konsol ve Markdown çıktısı `display_label` kullanır.

### 33.7 Testler

`ml/tests/test_pipeline_health.py` ve `ml/tests/test_stage_r_c.py` güncellendi;
**194 test** geçiyor.

---

## 34. Faz 7-R — Seviye farkı (ppg) ölçümü (F7-79)

### 34.1 Amaç

Kullanıcı `m = 0,02 ppg` değerini **geçici** onayladı ve gerçek `sigma_ppg`
ölçümünü istedi: `m`, gnubg 0-ply ile 2-ply arasındaki **ölçülmüş** ppg
farkının yarısı olmalı ki "eşdeğer" bir seviye farkını ayırt etsin.

### 34.2 Araç

`ml/ppg_measure.py` (yeni, 10 test — Test 148–157).

- **Money:** gnubg'nin gömülü Python'u (`gnubg-cli.exe -p script.py`),
  `set matchlength 0` + `new game`, sonuç `gnubg.match()["games"][-1]["info"]`.
  `new session` yolu kullanılamaz: oyun sınırı yok ve gömülü Python'dan
  kesilemiyor.
- **Maç:** `new match L` + `The score (after N games) is:` satırının ayrıştırılması.
- **GA:** küme bootstrap'i, 20 000 yeniden örnekleme. Money'de küme = oyun,
  maçta küme = maç. `sigma_used = max(sigma_oyun, sigma_kume)`.

### 34.3 Ölçüm sonucu

| Karşılaştırma | Bağlam | n | Fark (ppg) | %95 GA | σ |
|---|---|---|---|---|---|
| 0-ply vs 2-ply | money | 2400 oyun | **−0,2229** | [−0,3425; −0,1037] | 2,9960 |
| 0-ply vs 2-ply | maç-5 | 40 maç / 99 oyun | −0,8546 | [−1,8950; +0,1867] | 5,3717 |
| 0-ply vs 2-ply | maç-9 | 40 maç / 233 oyun | −1,2169 | [−2,3245; −0,3527] | 7,9001 |
| 2-ply vs 3-ply | money | 400 oyun | −0,0625 | [−0,3600; +0,2400] | 3,0581 |
| 2-ply vs 3-ply | maç-5 | 40 maç / 113 oyun | +0,1096 | [−0,8279; +1,1388] | 5,3569 |
| 2-ply vs 3-ply | maç-9 | 40 maç / 213 oyun | −0,8990 | [−1,8590; −0,0512] | 6,8013 |

**`m = 0,1115 ppg`** (0-2 money farkının yarısı; GA sıfırı dışlıyor).

**Onay (2026-11-21).** Kullanıcı `m = 0,1115 ppg` değerini **kesin** olarak
kabul etti; `0,02` yer tutucusu tamamen geçersiz. Bu, R-F'nin iddia eşiğini
ve gereken oyun sayısını (4337) bağlar. Kalan kısıt: 2000 oyunluk R-F
koşuları bu eşik için **güçsüz**; "eşdeğer" iddiası kurulmadı, yalnızca
"anlamlı fark" iddiası kuruldu.

### 34.4 Dört bulgu

1. **400 oyun yetersizdi.** Aynı hücre 400 oyunla `−0,1300`, GA
   `[−0,4150; +0,1550]` — sıfırı içeriyor. 2400 oyunla GA sıfırı **dışlıyor**.
   "Bir seviye farkı" premisi ancak 2400 oyunda kuruldu.
2. **`sigma_ppg` tahminden çok yüksek.** Ölçülen **2,9960** (money),
   5,37–7,90 (maç). Kullanıcının 1,4 tahmini ve
   `match_power.DEFAULT_PPG_SIGMA = 2,4` **düşük**. `m = 0,1115` için gereken
   oyun **4337**; `m = 0,02` için ~80 000 olurdu — pratikte imkânsız. Ölçüm
   R-F'yi **yapılabilir** kıldı.
3. **2-ply vs 4-ply ölçülemez.** Oyun başına 60 s'yi aştı (5 oyun 300 s'de
   bitmedi). İkincil karşılaştırma **2-ply vs 3-ply** oldu (6 s/oyun) ve 400
   oyunla **güçsüz** kaldı; gereken n ≈ 4519.
4. **Maç bağlamında ppg ölçeği farklı.** Maç-9'da fark −1,22 ppg; bu checker
   oyunundan çok **küp yetersizliğini** yansıtır. Bu yüzden `m` **money'den**
   türetildi; maç hücreleri ayrı raporlanır.

### 34.5 `derive_margin` semantiği

`m = 0,5 × |nokta tahmini|`. Taban olarak GA'nın sıfıra en yakın sınırını
kullanmak **yanlıştı**: o zaman `m` örneklem büyüklüğüyle küçülür ve R-F'nin
maliyeti yapay olarak düşer. `m` seviye farkının özelliğidir, ölçüm
hassasiyetinin değil. GA bunun yerine **güvenilirlik notu** olarak raporlanır.

### 34.6 İkinci hata: marj kaynağı girdi sırasına bağlıydı

`build_report` `money[0]` alıyordu; `--merge` yeni hücreyi listenin **sonuna**
eklediği için marj yanlışlıkla `2-ply vs 3-ply @ money` hücresinden türetildi
(`m = 0,1200`, güçsüz hücre). Düzeltme: karşılaştırmalar
`(plies_a, plies_b, length)` ile **sıralanır**; `report` alt komutu marjı güncel
kodla **yeniden hesaplar**.

### 34.7 R-F'ye etkisi

| Öğe | Önce (yer tutucu) | Sonra (ölçüldü) |
|---|---|---|
| `m` | 0,02 ppg | **0,1115 ppg** |
| σ_ppg | 1,4 (tahmin) | **2,9960** (money) |
| Gereken oyun | ~80 000 | **4337** |
| Duvar saati (6 işçi) | ~6 saat | **~20 dakika** |

### 34.8 Açık noktalar

1. 2-ply vs 3-ply money hücresi güçsüz (400 oyun); gereken n ≈ 4519.
2. Maç hücrelerinde σ 5,37–7,90; maç iddiası için gereken n 13 900–30 200.
3. gnubg `cubeinfo` varsayılanı `jacoby: 1`; para oyununda ikincil fark
   yaratabilir — ölçülmedi.
4. `m` yalnızca **money** bağlamı için geçerli; maç bağlamı ayrı `m` gerektirir.

## 35. Faz 7-R — "adım 0" kapıları (F7-80 – F7-83)

R-D'ye geçmeden kullanıcının istediği **dört** kapı. Üçü kod, biri ölçüm.

### 35.1 Kapı 1 — renk takası (antisimetri)

`ml/antisymmetry.py` (yeni). `mirror_board`, `flip_perspective`,
`augment_perspectives`, `measure_antisymmetry`, `build_markdown`.

**Ölçüm (model_v30, corpus v2, 500 vaka, gnubg 2-ply):**

| Ölçüm | Değer | Kapı | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | **−0,8915** | `\|corr\| ≥ 0,99` | **DUSTU** |
| ER farkı GA | **[−0,0620; −0,0340]** | sıfırı içermeli | **DUSTU** |
| Girdi renk-simetrisi | 0/12 167 uyusmazlık | 0 | GEÇTİ |
| `mean \|e(+1)+e(−1)\|` | 0,7152 | 0'a yakın | DUSTU |
| Politika antisimetrisi | 174/500 (0,3480) | — | — |
| ER(+1) / ER(−1) | 0,0396 / 0,0875 | — | — |

**Teşhis: kusur modelde, girdide değil.** Girdi vektörü renk takasında
kusursuz simetrik. Kök neden F7-55: `ml/train_v2.py` girdi vektörüne bakış
artırımı uygulamıyor.

**Politika antisimetrisi "aynı argmax" değildir.** Doğru ifade
`argmax(logit(+1)) == argmin(logit(−1))`; ilk sürüm iki argmax'ı
karşılaştırıyordu ve ER(−1) = 0,4907 gibi anlamsız bir sayı üretiyordu.

**Bu "önce" durumudur.** Kapı **R-D'de** geçmelidir; R-D eğitimi
`augment_perspectives` veya girdi kanonikleştirmesi kullanmak zorunda.

### 35.2 Kapı 2 — `learning_curve.py` gerçek eğitime bağlandı

`ml/curve_pool.py` (yeni): gnubg 2-ply kendine karşı oyun, her karar
noktasında **tüm** adaylar etiketli, bölüm **oyun düzeyinde**
(`--held-out-games`). `CurvePool`: `x` [M,221], `offsets`, `best`, `y`,
`cand_equity`, `game_ids`, `split`, `meta`.

`make_train_fn` → `TrainFn` sözleşmesi: N pozisyon örnekle, `epochs` **sabit**
(veri değişir, epoch değişmez), held-out'ta **pozisyon başına** kayıp +
`gameIds` döndür.

`learning_curve.py`: `_cluster_means` eklendi; `fit_log_slope(..., cluster=True)`
**oyun düzeyi** küme bootstrap; `run_curve_multi_seed` tohumları havuzlar ve
oyun kimliklerini tohumla önekler (`s0:g3`); CLI `--pool`/`--seeds`/`--epochs`/
`--no-cluster`/`--out`/`--markdown`; `main()` artık `SystemExit` atmıyor.

Küme GA'sı pozisyon GA'sından **dar olamaz** (test 184).

### 35.3 Kapı 3 — etiketler

`pipeline_health.verdict`: değer kapısı düştüğünde `scaling_evidence` okunur —
`eğim<eps` → `pipeline`, `eğim≥eps` → yeni **`ölçek`**, `yok` → yeni
**`belirsiz`**. `yok` "ölçek yardım etmiyor" değil, "ölçülmedi" demektir. CLI
çıkış kodları 4 = `belirsiz`, 5 = `ölçek`.

`gnubg_distill.VERDICT_PIPELINE` → **`VERDICT_TEACHER_EFFECTIVE =
"ogretmen-etkili"`**. Eski ad bir **neden** iddia ediyordu; yeni ad yalnızca
ölçümü adlandırır. `capacityInference: false`.

### 35.4 Kapı 4 — C#–Python `search1` paritesi

`ml/search1_parity.py` (yeni) + `Backgammon.MatchBench search1` alt komutu.
500 vaka, corpus v2, `--stride 2`.

**Dört gerçek kusur bulundu — dördü de Python ölçüm tarafında:**

1. **Zar ağırlığı.** 21 zar **eşit** (1/21) ağırlıklıydı; C# gerçek olasılığı
   kullanır (çift 1/36, çift olmayan 2/36). → `DICE_WEIGHTS`.
2. **Rakibin terminal afterstate'leri** değer kafasından tahmin ediliyordu;
   rakip mars/backgammon yapabiliyorsa sistematik iyimser (0,34–0,98 equity).
   → `terminal_equity` ile oyun kuralından.
3. **`terminal_equity` ev/bar geleneği ters.** Beyaz'ın evi 19..24, barı 0;
   Siyah'ın evi 1..6, barı 25. 4 vakada mars ↔ backgammon karıştı.
4. **`tools/reference_gen.py` icindeki `_single_step_uses_die` off sayacı.** Sayaçları
   `key`'den alıp bir kez daha artırıyordu → hiç eşleşmiyordu → büyük-zar
   filtresi **her** tek-adımlı sonucu atıyordu → `legal_after_states` boş küme.
   Bu kusur **ürün** kodunu da etkiliyordu (korpus üretimi, `er_harness`).

**Sonuç (düzeltmelerden sonra):**

| Ölçüm | Değer |
|---|---|
| Kararlı vaka (üst-2 fark > 0,02) | 357 |
| Berabere vaka (çıkarıldı) | 143 |
| Argmax uyuşması (kararlı) | **357/357 = 1,0000**, GA [1,0000; 1,0000] |
| Skor MAE | **5,36e-08** (float32 yuvarlama) |
| Skor maksimum fark | 7,51e-07 |

Python `search1` ile C# `BackgammonSearch` **sayısal olarak aynı**. Kalan 6
"uyuşmazlık" tam berabere (üst-2 fark = 0); orada argmax kayan nokta
gürültüsüdür. Kapı **kararlı** vakalar üzerinde işlenir (`TIE_TOL = 0.02`).

**Başlık ER'si değişmedi:** `policy` 0,0402 → 0,0402; `value` 0,0442 → 0,0442;
`search1` 0,0210 → **0,0209**. Kusurlar az sayıda (bear-off / terminal)
pozisyonu etkiliyordu. `ml/artifacts/er_paths_v2.json` düzeltilmiş ölçümle
değiştirildi.

### 35.5 Artefaktlar

| Dosya | İçerik |
|---|---|
| `ml/artifacts/antisymmetry.json` / `.md` | renk takası ölçümü (500 vaka) |
| `ml/artifacts/curve_pool.npz` | 200 oyun / 6 596 pozisyon / 129 819 aday, oyun düzeyinde bölünmüş |
| `ml/artifacts/learning_curve.json` / `.md` | 3 tohum, 4 nokta, oyun düzeyi küme bootstrap |
| `ml/artifacts/search1_corpus.json` | parite girdisi (500 vaka) |
| `ml/artifacts/search1_cs.json` | C# `Backgammon.MatchBench search1` çıktısı |
| `ml/artifacts/search1_parity.json` / `.md` | parite raporu |

**Öğrenme eğrisi sonucu (3 tohum, 500→4 000 pozisyon, 20 sabit epoch):**

| Çarpan | Pozisyon | ER `policy` | ER `value` | In-sample |
|---|---|---|---|---|
| 1× | 500 | 0,0395 | 0,1463 | 0,6667 |
| 2× | 1 000 | 0,0287 | 0,0782 | 0,3573 |
| 4× | 2 000 | 0,0242 | 0,0460 | 0,2883 |
| 8× | 4 000 | 0,0189 | 0,0454 | 0,1788 |

| Yol | Kazanç (ER / log2 veri) | %95 GA | Karar |
|---|---|---|---|
| `policy` | **0,0066** | [0,0053; 0,0080] | eşik 0,0050 üstü |
| `value` | **0,0335** | [0,0298; 0,0387] | eşik üstü |

**Karar: `ölçek`.** Veri ikiye katlandığında ER ölçülebilir biçimde düşüyor.
Tohum bazında: tohum 1 → `belirsiz` (GA [0,0039; 0,0089]), tohum 2 → `ölçek`,
tohum 3 → `belirsiz`. Havuzlanmış karar `ölçek`; **tek tohum yeterli değil**,
bu yüzden ≥3 tohum kuralı korunur.

`search1` sütunu boş: `curve_pool.make_train_fn` yalnızca politika ve değer
kaybını döndürür; 1-ply arama kaybı eğitim hedefi değildir. Boş sütun
**gizlenmez**.

### 35.6 Testler

| Dosya | Test | Aralık |
|---|---|---|
| `ml/tests/test_antisymmetry.py` | 10 | 158–167 |
| `ml/tests/test_curve_pool.py` | 8 | 168–175 |
| `ml/tests/test_search1_parity.py` | 6 | 176–181 |
| `ml/tests/test_learning_curve_cluster.py` | 6 | 182–187 |

### 35.7 Açık kalanlar

1. **Renk takası kapısı DÜŞTÜ** — R-D'de geçmesi zorunlu.
2. `curve_pool` etiketleri gnubg GPL; ürün dağıtımı öncesi lisans netleşmeli
   (R-Q1).
3. `search1` paritesi **cubeless**; küp kararı ayrı eksen (F7-73).
4. `TIE_TOL = 0.02` bir **ölçüm** tercihidir, model kusuru değil; 143/500 vaka
   berabere çıktı çünkü corpus v2'de birçok pozisyonda tek yasal hamle var.

## 36. Faz 7-R — "adım 0" ucuz ölçümleri (F7-84 – F7-92)

Kullanıcı R-D'ye geçmeden **yedi** ucuz ölçüm istedi. Bu bölüm ölçümleri ve
kararlarını verir; ayrıntılı gerekçe `ASSUMPTIONS.md` F7-84 – F7-92'de.

### 36.1 Renk takası ürün yolunu etkiliyor mu? (F7-84)

**Cevap: evet, ama "görülmeyen bakış" yüzünden değil.** Kod doğrulandı:

* Python `er_paths.search1_values` rakip düğümleri `_vectors_for(ordered, opponent)`
  ile **rakibin** bakışından değerlendirir.
* C# `BackgammonSearch` `EndTurn(child)` sonrası `s.turn` ile aynı şeyi yapar.
* Eğitim verisi **her kararı hamle sırası olan tarafın** bakışından yazar
  (`corpus2._play_game`, `curve_pool._label_case` → `perspective=turn`).

Yani **iki bakış da** hem eğitimde hem aramada görülüyor. Kusur "bakış hiç
görülmüyor" değil, **`f(x,+1) = −f(x,−1)` simetrisinin eksik olması**. Bu yüzden
kapı bir *genelleme* teşhisidir, ürün yolunda kör nokta değildir.

### 36.2 Çıkarım anında antisimetrikleştirme (F7-85)

`ê(x) = (f(x,+1) − f(x,−1))/2` (politika için logit farkı). 500 vaka:

| Yol | Düzeltme öncesi | Sonrası | Fark | %95 GA |
|---|---|---|---|---|
| `policy` | 0,0396 | **0,0344** | −0,00525 | [−0,0135; +0,0024] |

**Kazanç yönünde ama kanıtlanmadı.** Eşleştirilmiş fark σ ≈ 0,09; 0,005'lik
etkiyi ayırt etmek için **n ≈ 1 245** vaka gerekir, 500 yetmez. Nokta tahmini
olarak raporlanır, kapı olarak **kullanılmaz**.

**F7-55'teki "naif düzeltme" neydi?** Logitlerin **ortalaması** alınmıştı
(`(f(+1)+f(−1))/2`). Doğru işlem **fark**tır; ortalama işareti yanlış tarafa
çevirir ve ER'yi 0,0500 → **0,1674** yapar. Kusur buydu.

### 36.3 `_single_step_uses_die` kusurunun veriye etkisi (F7-86)

Kusur yalnızca `max_steps == 1` **ve** çift olmayan zar **ve** büyük zar
oynanabiliyorken tetikleniyordu.

| Yol | Tetiklenme |
|---|---|
| Kendi zarı (eğitim yolu) | **0/1 000 (0,00 %)** |
| Rakip 21 zarı | 210/21 000 (1,00 %) |
| En az bir tetiklenen vaka | 26/1 000 (2,60 %) |

**Eğitim verisi etkilenmedi** (6 596 pozisyon / 129 819 aday): kendi zarı
yolunda hiç tetiklenmiyor. Yeniden üretim **gerekmez**. `search1` ER'si
0,020962 → 0,020936 (ölçüm gürültüsü).

### 36.4 Öğrenme eğrisi: 5 tohum, 165×–5 280× (F7-87, F7-88, F7-92)

| Çarpan | Pozisyon | ER `policy` | ER `value` | In-sample (birleşik) |
|---|---|---|---|---|
| 1× | 165 | 0,0504 | 0,2114 | 1,1721 |
| 2× | 330 | 0,0414 | 0,2245 | 0,8910 |
| 4× | 660 | 0,0341 | 0,1099 | 0,5563 |
| 8× | 1 320 | 0,0267 | 0,0523 | 0,3413 |
| 16× | 2 640 | 0,0215 | 0,0473 | 0,2204 |
| 32× | 5 280 | **0,0166** | 0,0398 | 0,2553 |

| Yol | Kazanç (ER / log2 veri) | %95 GA | Karar |
|---|---|---|---|
| `policy` | **0,0067** | [0,0061; 0,0073] | eşik 0,0050 üstü |
| `value` | 0,0414 | [0,0396; 0,0449] | eşik üstü |

**Karar: `belirsiz`.** Tohum oybirliği yok: s1 `ölçek`, s2 `belirsiz`,
s3 `ölçek`, s4 `belirsiz`, s5 `ölçek`. F7-87 kuralı gereği havuz kararı tek
başına yetmez. Havuzlanmış GA eşiği kesmiyor ama **tohumlar ayrışıyor**.

**Doygunluk fiti `ER = a·N^−b + c`:**

| Yol | a | b | c (taban) | RMSE |
|---|---|---|---|---|
| `policy` | 0,2865 | 0,35 | **0,0033** | 0,0008 |
| `value` | 5,0251 | 0,60 | 0,0087 | 0,0298 |

Politika tabanı `c = 0,0033`, gnubg **0-ply**'in aynı korpustaki ER'sinden
(0,00444) **düşük**. Bu bir **ekstrapolasyondur** (6 nokta, `b` grid sınırında);
kanıt değil, yön göstergesidir.

**64× neden yok?** Havuzda 5 281 eğitim pozisyonu var; 32× = 5 280 tam sığar,
64× = 10 560 ister. "Ölçülemez" olarak işaretlenir, uydurulmaz.

**In-sample birimi.** `train_policy_head` tek bir **birleşik** kayıp döndürür:
`çapraz-entropi (nat/pozisyon) + 0,5·MSE (equity²)`. Bu bir ER **değildir**.
Birim artık `IN_SAMPLE_UNITS["combined"]` üzerinden türetilir
(`CurvePoint.resolved_in_sample_unit`); eski artefaktlarda alan boş olsa bile
rapor birimi yazar.

**Yeni yetenek.** `learning_curve.py --from-json <rapor.json> --markdown <çıktı>`
ölçüm yapmadan raporu yeniden üretir (`CurveReport.from_dict` /
`CurvePoint.from_dict`). Bir sunum alanı değiştiğinde 50 dakikalık eğri
tekrar koşulmaz.

### 36.5 gnubg 0/1/2-ply ER merdiveni (F7-89)

Aynı korpus (corpus v2, 500 vaka), hakem gnubg **2-ply**:

| Oyuncu | ER | %95 GA | Tam eşleşme |
|---|---|---|---|
| gnubg **0-ply** | **0,00444** | [0,00320; 0,00582] | 0,818 |
| gnubg **1-ply** | **0,00256** | [0,00179; 0,00347] | 0,836 |
| gnubg **2-ply** | **ölçülemez** | — | — |
| **model** `policy` | 0,0402 | — | — |
| **model** `search1` | 0,0209 | — | — |
| **model** `value` | 0,0442 | — | — |

2-ply **ölçülemez**: hakem kendini ölçemez; gnubg `eval` 2-ply'den derin sütun
üretmez (F6-32). Sıfır **yazılmaz**.

Model hamle seçiminde 0-ply'ın **9,0×** (politika) / **4,7×** (`search1`)
altında. Bu, "ürün botu 0-ply'ı yener" iddiasıyla çelişmez (oyun gücü ≠ hamle
ER'si) ama "model 0-ply seviyesinde" iddiasını **desteklemez**.

### 36.6 Python–C# hamle kümesi eşitliği (F7-90)

`ml/moveset_parity.py` + `Backgammon.MatchBench moveset`: corpus v2'nin
**tamamı** (1 000 pozisyon), sıralı aday kümesi karşılaştırması →
**1 000/1 000 uyuşma**, uyuşmazlık yok.

100 bin pozisyon R-D öncesi "ucuz" kapsamın dışında (ayrı rastgele pozisyon
üreteci + her pozisyon için C# koşumu gerekir); R-D sırasında arka planda
koşulacak. Kalıcı öneri: Python hamle üretimi kaldırılıp C#'tan çağrılmalı —
dört kusurun dördü de Python tarafında çıktı.

### 36.7 `search1` paritesinde dışarıda kalan 143 vaka (F7-80 devamı)

Eski 500 vakalık koşuda 357/357 "kararlı" vaka uyuşuyordu ve 143 vaka
dışarıda kalıyordu. **Eleme ölçütü:** üst-2 fark `> TIE_TOL = 0,02`. Yeni
1 000 vakalık koşuda:

| Ölçüm | Değer |
|---|---|
| Kararlı vaka | 717 |
| Berabere (dışarıda) | 283 |
| Dışarıdakilerde argmax uyuşması | 271/283 (0,9576) |
| Dışarıdakilerin üst-2 farkı (medyan / maks) | 0,0056 / 0,0200 |
| Dışarıda kalan uyuşmazlıkların üst-2 farkı | hepsi **0,000000** |
| Yanlılık şüphesi (uyuşmazlık farkı > 0,010) | **YOK** |

Dışarıda kalan uyuşmazlıkların tamamı üst-2 farkı `≤ 0,010` bölgesinde, yani
argmax'ın matematiksel olarak **tanımsız** olduğu yerde. Filtre gerçek bir
kusuru saklamıyor. Skor MAE 5,5e-8 parite iddiasını destekliyor.

### 36.8 Çalışma ağacı izolasyonu (F7-91)

`Backgammon.UI/GameOrchestrator.cs` (+43 satır) bu ajanın değişikliği değildi ve
üç rapordur "hangi kod durumunda test koştu" belirsizliği yaratıyordu.

**Karar:** paralel çalışma ayrı bir git worktree'ye taşındı —
`F:\Projects\VijualStudioski\TavlaAI_parallel`, dal `parallel/ui-optimistic-move`,
içerik `GameOrchestrator.ApplyMoveOptimistic`. Değişiklik **korundu**, ana ağaç
`git checkout --` ile **temizlendi**. Ana ağaç artık yalnızca bu ajanın
değişikliklerini taşır.

### 36.9 Testler

| Dosya | Test | Aralık |
|---|---|---|
| `ml/tests/test_antisymmetry.py` | 10 + 5 | 158–167, 204–208 |
| `ml/tests/test_curve_pool.py` | 8 | 168–175 |
| `ml/tests/test_search1_parity.py` | 6 | 176–181 |
| `ml/tests/test_learning_curve_cluster.py` | 6 + 5 + 3 | 182–187, 193–197, 209–211 |
| `ml/tests/test_moveset_parity.py` | 5 | 188–192 |
| `ml/tests/test_gnubg_ladder.py` | 5 | 199–203 |
| `ml/tests/test_perspective_augment.py` | 6 | 212–217 |
| `ml/tests/test_learning_curve_k4.py` | 10 | 218–227 |
| `ml/tests/test_replay_verify.py` | 7 | 228–234 |
| `ml/tests/test_distill_dist_k5.py` | 7 | 235–241 |

Numaralandırma çakışmaları giderildi: `test_gnubg_ladder` 173–177 → **199–203**,
`test_antisymmetry` antisimetrikleştirme 194–198 → **204–208**.

### 36.10 Açık kalanlar

1. **Renk takası kapısı hâlâ DÜŞTÜ** — R-D'de `augment_perspectives` ile
   geçmesi zorunlu; geçmezse çıkarım anı antisimetrikleştirmesi kalıcı çözüm
   (§36.12).
2. Öğrenme eğrisi kararı **`belirsiz`**; 400 oyunluk havuz + 64× noktası ile
   yeniden koşuldu (§36.14).
3. ~~64× noktası için havuz yetersiz~~ — `curve_pool_400.npz` ile çözüldü
   (10 580 eğitim pozisyonu ≥ 10 560).
4. 100 bin pozisyonluk hamle kümesi eşitliği R-D sırasında koşulacak.
5. `curve_pool` etiketleri gnubg GPL; ürün dağıtımı öncesi lisans netleşmeli.
6. K3 (oyun frekansı ağırlıklı ER + ppg) ve K6 (m = 0,02 ppg) **R-F'ye**
   bırakıldı; gerekçe §36.16.
### 36.11 R-D öncesi taban: model vs gnubg 0-ply (2000 oyun)

Adım 0'ın son ölçümü. `ml/vs_gnubg.py` ile küpsüz para oyunu, eşleştirilmiş
zar + renk takası, 6 paralel süreç, **2000 oyun** (1000 çift). Model
`ml/runs/stage_d_l2/onnx/model_v30.onnx`, yol `search1`, rakip gnubg 0-ply.

| Ölçüm | Değer |
|---|---|
| Oyun | 2000 (1000 çift) |
| Kazanma | 868/2000 = 0,4340 |
| **ppg** | **−0,1635** |
| ppg %95 GA | [−0,2230; −0,1050] |
| Eşleştirilmiş fark | −0,3270 |
| Eşleştirilmiş fark %95 GA | [−0,4420; −0,2120] |
| Oyun başına ply | 55,9 |

**Sonuç.** Model gnubg 0-ply'a **kaybediyor**; hem ppg hem eşleştirilmiş fark
GA'sı sıfırın altında. 20 oyunluk pilot (+0,2 ppg) tamamen gürültüydü —
20 oyunluk standart hata ~0,3 ppg mertebesindedir. Pilot artefaktı denetim
izi olarak duruyor ama karar dayanağı değil.

**R-D için.** Başarı ölçütü bu tabana göre **eşleştirilmiş** olacak: aynı 1000
zar dizisi, aynı renk takası, aynı gnubg 0-ply. Anlamlılık eşiği m = 0,02 ppg
(R-F'de kesinleşecek).

**Maliyet.** 6 paralel süreç, ~2,5 saat CPU (tek süreçte ~7,5 saat). Kalıcı
gnubg oturumu çağrı başına ~0,45 s → ~0,01 s indirdi; `intra_op_threads=1`
ile ONNX oturumları çekirdek başına ayrıldı.

**Yeni testler.** `ml/tests/test_gnubg_er.py`: kalıcı oturum tek-atımlık koşuyla
aynı tabloyu vermeli (durum taşımamalı), `OnnxScorer(intra_op_threads=...)`
kabul edilmeli. Pytest toplamı **1386**.
### 36.12 K1 — Perspektif artırımı ve antisimetrikleştirme (F7-94)

**Kök neden doğrulandı.** `ml/train_v2.py` içinde `perspective` kelimesi hiç
geçmiyordu: eğitim hattı iki bakışı hiç görmüyordu. F7-55'teki `corr = −0,8915`
ve renk takası kapısının düşmesi bunun doğrudan sonucu.

**Uygulama.** `ml/train_v2.py`:

| Fonksiyon | Görev |
|---|---|
| `_flip_vectors(x)` | `antisymmetry.flip_perspective`'i toplu uygular |
| `augment_value_samples(samples)` | değer örneklerini **çiftler hâlinde** çoğaltır |
| `augment_policy_samples(samples)` | politika örneklerini çiftler hâlinde çoğaltır |

Yerleşim **blok değil, iç içe** olmak zorunda: `[s0(+1), s0(−1), s1(+1), s1(−1), …]`.
İlk denemede `np.concatenate([orig, flipped])` kullanıldı ve 6 testin 4'ü düştü;
`_pair()` yardımcısı `out[0::2] = orig; out[1::2] = flipped` yazarak düzeltti.

**İnvolüsyon kanıtı.** `flip_perspective`, rastgele 221 boyutlu vektörde
`f(f(x)) == x` sağlıyor (maks fark **0,0**). `ACTIVE_OFFSET=0` ↔ `OPP_OFFSET=96`
takası `j → 25−j` ters çevirmesiyle, bar/off/pip/escaped/away skalerleri takas
edilir, `CUBE_OWNER` işaret değiştirir, para/Crawford/temas bayrakları korunur.

**İki ayrıntı.** `margin` **ters çevrilmez** (ilk iki adayın farkı; iki `q` da
işaret değiştirdiği için fark aynı kalır). `best_equity` ve `equity_target`
ters çevrilir. Politika hedefi takas altında **değişmez**.

**CLI.** `--augment-perspectives`. `main()` içinde kritik ağırlıklar
hesaplandıktan sonra devreye girer ve `value_weights`/`policy_weights`
dizilerini de ikiye katlar.

**Regresyon: ağırlık normalizasyonu.** İlk uygulama `np.repeat(w, 2)` ile
ağırlıkları çiftledi. `critical_sampling_weights` **normalize edilmiş** bir
olasılık vektörü döndürdüğü için toplam 2,0 oluyordu ve `train_steps_v2`
içindeki `rng.choice(..., p=value_weights)` şu hatayla düşüyordu:

```
ValueError: Probabilities do not sum to 1.
```

`_double_weights(w)` yardımcısı çiftlemeden sonra yeniden normalleştirir
(`w / w.sum()`; toplam 0 ise tekdüze dağıtır). Test 242 artık
`--critical-boost 2.0` ile koşuyor: ağırlık yolu ancak `boost > 1` ve
`degenerate == false` iken devreye girer, dolayısıyla eski test bu hatayı
görmüyordu.

**n = 1000 antisimetrikleştirme ölçümü.** `antisymmetry.py symmetrise` ile
mevcut model (`model_v30.onnx`, 2-ply, `reference_corpus_v2.json`):

| Yol | Önce | Sonra | Fark | %95 GA | Karar |
|---|---|---|---|---|---|
| politika | 0,0402 | 0,0343 | −0,0059 | [−0,0111; −0,0009] | **İYİLEŞTİ** |
| değer | 0,0442 | 0,0407 | −0,0035 | [−0,0098; +0,0024] | kanıtlanmadı |

`argmax` 1000 vakadan **315**'inde değişti. Yani çıkarım anı
antisimetrikleştirmesi (`ê(x) = (f(x,+1) − f(x,−1))/2`) **gerçek ve ucuz bir
politika kazancı**; R-D kapısı geçmezse kalıcı çözüm olarak kullanılabilir.
Maliyeti ONNX başına iki ileri geçiş.

### 36.13 K2 — `_single_step_uses_die` kusuru veriyi bozdu mu? (F7-95)

**Yöntem.** `ml/replay_verify.py` shard'ları **yeniden oynatır** ve her karar
için saklanan aday listesini denetler:

| Denetim | Anlamı |
|---|---|
| `pass_with_candidates` | pas kararı ama aday sayısı ≠ 1 |
| `pass_without_candidates` | pas kararı ama aday listesi boş |
| `move_without_candidates` | hamle kararı ama aday listesi boş |
| `chosen_not_in_candidates` | seçilen hamle aday kümesinde yok |

**Kritik bulgu.** Bir pas kararının `candidateTotal` değeri **0 değil, 1**'dir.
`Backgammon.Core/Search/BackgammonSearch.cs:339–343`:

```csharp
isPass = list.Count == 0;
if (isPass) { list.AddPass(s); }
```

İlk denetim `total == 0` varsaydı ve tek shard'da 76 900 yanlış "kirli" pas
bildirdi. `total != 1` olarak düzeltildi, ayrıca `pass_candidate_total_hist`
histogramı eklendi.

**Sonuç — 6 shard, 60 000 oyun, 3 710 732 karar:**

| Ölçüm | Değer |
|---|---|
| Shard | 6 |
| Oyun | 60 000 |
| Karar | 3 710 732 |
| Pas | 1 805 887 |
| Hamle | 1 904 845 |
| Pas + aday var | **0** |
| Pas + aday yok | **0** |
| Hamle + aday yok | **0** |
| Seçilen adayda değil | **0 / 1 805 887** |

**Karar: KORPUS TEMİZ.** `_single_step_uses_die` kusuru saklanan veride hayatta
kalma yanlılığı (survival bias) yaratmamış. Veriyi yeniden üretmeye gerek yok.
Artefakt: `ml/artifacts/replay_verify.json` / `.md`.

### 36.14 K4 — Öğrenme eğrisi düzeltmeleri (F7-96)

**Düzeltilenler.**

1. `CURVE_MULTIPLIERS` `(1,2,4,8,16,32)` → `(1,2,4,8,16,32,64)`.
2. Doygunluk fitine **küme bootstrap** %95 GA eklendi
   (`SATURATION_BOOTSTRAP_RESAMPLES = 2000`, `_cluster_resample_means`,
   `_saturation_core`). `c` için `cCiLow`/`cCiHigh` raporlanıyor.
3. `CurveReport` iki yeni alan: `corpus` (hangi havuz, kaç oyun, kaç ply,
   hangi etiket) ve `paired` (önce/sonra eşleştirilmiş karşılaştırma).
4. `paired_curve_comparison(before, after, …)` — aynı tohum/aynı nokta
   eşleştirmesiyle fark ve GA. R-D'de artırım öncesi/sonrası için hazır.
5. CLI: `--corpus ANAHTAR=DEĞER`, `--compare-before <json>`,
   `--saturation-resamples`.
6. Markdown: `### 1.1 Korpus`, `c %95 GA` / `Yeniden örnekleme` sütunları,
   `## 4.1 Eşleştirilmiş (paired) karşılaştırma`.

**64× için havuz.** 60 oyunluk havuz 5 281 eğitim pozisyonu veriyordu; 64×
noktası ≥ 10 560 istiyor. `curve_pool.py build --games 400 --held-out-games 80`
ile yeni havuz:

| Ölçüm | 60 oyunluk | 400 oyunluk |
|---|---|---|
| Pozisyon | 6 596 | **13 247** |
| Aday | 129 819 | **257 543** |
| Aday/pozisyon | 19,68 | 19,44 (min 2, maks 397) |
| Eğitim | 5 281 | **10 580** |
| Held-out | 1 315 | **2 667** |
| Oyun | 60 | 320 / 80 |

`ml/artifacts/curve_pool_400.npz`. 64× eşiği **aşıldı**.

**Sonuç (7 nokta, 5 tohum, 400 oyunluk havuz).**

| Çarpan | Pozisyon | ER `policy` | ER `value` |
|---|---|---|---|
| 1× | 165 | 0,0525 | 0,1915 |
| 2× | 330 | 0,0441 | 0,1321 |
| 4× | 660 | 0,0355 | 0,0879 |
| 8× | 1 320 | 0,0276 | 0,0588 |
| 16× | 2 640 | 0,0236 | 0,0469 |
| 32× | 5 280 | 0,0184 | 0,0365 |
| 64× | 10 560 | **0,0158** | **0,0330** |

- Eğim `policy` 0,0062 GA [0,0059; 0,0065]; `value` 0,0253 GA [0,0244; 0,0267].
- Doygunluk: `policy c = 0,0003` GA [0,0001; 0,0066]; `value c = 0,0223`
  GA [0,0148; 0,0252].
- **Tohum oybirliği: 5/5 `olcek`.** Önceki koşuda karar `belirsiz` ve oylar
  3× `olcek` / 2× `belirsiz` idi. Fark, 64× noktası + 400 oyunluk havuz:
  eğri 32×'te kesilince kazanç eşiğe yakın kalıyordu.
- **Değer platosu çözüldü**: 4× sonrası düzleşme (0,0460 → 0,0454) 60 oyunluk
  havuzun artefaktıydı; 400 oyunluk havuzda 64×'e kadar düşmeye devam ediyor
  (0,0330). K5'in "plato" gerekçesi bu ölçümle **zayıfladı**; 6 sınıflı KL
  yine de R-D'de açık kalıyor (bilgi içeriği argümanı geçerli).
- `paired` boş: `--compare-before` verilmedi. R-D'de artırım öncesi/sonrası
  için kullanılacak.

**Regresyon: `main()` içinde yerel `import json`.** 64× koşusunun ilk denemesi
tüm sonucu kaybetti (`UnboundLocalError: local variable 'json'`). Yerel import
modül düzeyindeki adı gölgeliyordu. Kaldırıldı; Test 243 bunu kilitliyor.

### 36.15 K5 — Değer başlığı platosu ve 6 sınıflı KL (F7-97)

**Plato.** Değer yolu 4× sonrası düzleşiyor (0,0460 → 0,0454) ama politika
düşmeye devam ediyor. Bu, değer başlığının **skaler equity** ile eğitilmesinin
bir sınırı: gnubg'nin 6 sınıflı dağılımı çok daha fazla bilgi taşıyor.

**Uygulama.**

| Dosya | Değişiklik |
|---|---|
| `ml/gnubg_er.py` | `_eval_key`, `parse_eval_dist`, `parse_evals_dist`; `eval_afterstates(..., dists=False)`; `_parse_eval_blocks` |
| `ml/gnubg_distill.py` | `PolicyPosition.best_dist`, `PolicyDataset.dist` + `has_dist()`, `stats()["hasDist"]`, `save/load` kalıcılığı, `train_policy_head(dist_weight=)`, CLI `--dists` / `--dist-weight` |

`train_policy_head` artık `KL(gnubg ‖ model)` terimini ekliyor:
`F.kl_div(log(best_probs), target, reduction="batchmean")`.

**İki tuzak.**

1. gnubg `eval` sütunları **kümülatif**, dışlayıcı değil:
   `Win, W(g), W(bg), L(g), L(bg), Equity`. `W(g)` backgammon'ları içerir.
   İlk sürüm bunları dışlayıcı sandı ve sessizce yanlış KL hedefi üretti
   (equity 0,49 yerine 0,33 olmalıydı). Test 236 yakaladı; `equity.from_cumulative`
   üzerinden yönlendirildi.
2. `HintReferee` gnubg oturumunu kendi üzerinde değil `.session` alanında
   tutuyor. `getattr(referee, "session", referee)` ile düzeltildi.

`dist` yalnızca **her** pozisyon dağılım taşıyorsa veri kümesine alınır; eksik
dağılımlı bir korpusta KL sessizce yanlış olmasın diye.

### 36.16 K3 ve K6 — kapsam kararı (F7-98)

**K3 (oyun frekansı ağırlıklı ER + ppg).** Hedef metrik değişikliği, R-D'nin
başlık sayısını doğrudan etkiler. R-D tabanı zaten **ppg** üzerinden kurulu
(§36.11, −0,1635 ppg) ve ppg oyun frekansını doğal olarak içerir. Bu yüzden K3
R-D'yi **bloke etmez**; ER tarafının ağırlıklandırması R-F'ye bırakıldı.

**K6 (m = 0,02 ppg).** Kullanıcı kararı: R-F'te kesinleşecek. R-D'de **m = 0,05**
ile başlanır; sonuç iyiyse 0,02'ye inilir. Gerekçe: σ_ppg ≈ 1,4 varsayımıyla
m = 0,02 için varyans azaltmasız on binlerce oyun gerekir; gerçek σ ölçülmeden
0,02'yi tek eşik yapmak istatistiksel gücü belirsiz bırakır.

### 36.17 CUDA `0xC0000409` (F7-99)

**Belirti.** `test_71b_training_is_reproducible_gpu` paralel yük altında
`0xC0000409` (STATUS_STACK_BUFFER_OVERRUN) ile düşüyor, tek başına 38 s'de
geçiyor. `metrics.jsonl` **tam** yazılmış oluyor: çökme eğitim sırasında değil,
**yıkım (teardown)** sırasında.

**Savunma.**

1. `ml/train_v2.py`: `_release_cuda(device)` — `main()` dönmeden önce
   `torch.cuda.synchronize()` → `gc.collect()` → `torch.cuda.empty_cache()` →
   `torch.cuda.synchronize()`. Bekleyen asenkron iş varken bağlamın yıkılması
   tetikleyici olduğu için önce senkronize edilir.
2. `ml/tests/test_stage_d.py`: `run_train` `returncode == 0xC0000409` görürse
   **bir kez** yeniden dener. Kalıcı bozulma ikinci denemede de çöker ve
   assert görünür olur.

**Sınır.** CRT seviyesindeki `__fastfail` Python istisnası değildir,
yakalanamaz. Bu bir savunmadır, garanti değil. Ortam: GTX 1650, CUDA var,
12 CPU, `torch.get_num_threads() == 6`.

**Onay (2026-11-21).** Kullanıcı teşhisi **kabul etti**: çökme ortam/paralel
yük sorunudur, kod hatası değil. Ek savunma (iş parçacığı sayısını sınırlama,
ORT oturum seçeneklerini gözden geçirme, CUDA işini serileştirme)
**istenmedi**; mevcut çıkış temizliği + tek yeniden deneme yeterli sayıldı.
Konu kapandı.
### 36.18 R-D koşusu ve politika kafası bulgusu (F7-100)

**İlk deneme yanlıştı.** `--augment-perspectives` hem değer hem politika
örneklerini çeviriyordu. 5 iterasyonluk deneme koşusu kapıyı **kötüleştirdi**:

| Ölçüm | Taban `v30` | Deneme (değer+politika) |
|---|---|---|
| `corr(e+1, e−1)` | −0,8846 | −0,8119 |
| `meanAbsSum` | 0,7410 | **0,4782** |
| `argmax` uyumu | 0,174 | **0,018** |
| ER(+1) | 0,0396 | 0,0573 |
| ER(−1) | 0,0875 | **0,5297** |

Değer kafası belirgin biçimde antisimetrikleşirken politika kafası
**rastgeleden kötü** hâle geldi (1/19 ≈ 0,053'ten de düşük).

**Kök neden.** Politika hedefi **oynayacak tarafın** dağılımıdır; girdi
çevrilince oynayacak taraf değişir, hedefin de çevrilmesi gerekir. Shard'larda
karşı tarafın hedefi **yok**. Aynı hedefle çevirmek modeli
`f(flip(x)) = f(x)` yani **simetrik** eğitir — kapının aradığı
`argmax(+1) == argmin(−1)` ilişkisinin tam tersi.

**Üretim yolu doğrulaması.** `BackgammonSearch` iki kafayı da her düğümde
**düğümün oynayacak tarafı** ile çağırıyor
(`BackgammonSearch.cs:365,374,382` — hepsi `s.turn`). Yani politika kafası
gerçekten perspektife göreli; kapı konvansiyonu doğru, eğitim verisi eksik.

**Düzeltme.** `--augment-perspectives` artık **yalnız değer** örneklerini
çevirir. Politika artırımı ayrı ve **varsayılan kapalı** bir bayrağa taşındı
(`--augment-policy-perspectives`, teşhis amaçlı). `train_report.json` iki
bayrağı ayrı kaydeder.

**Ağırlık normalizasyonu regresyonu.** İlk uygulama ağırlıkları `np.repeat(w, 2)`
ile çiftledi; `critical_sampling_weights` **normalize** bir olasılık vektörü
döndürdüğü için toplam 2,0 oluyordu ve `rng.choice(..., p=...)`
`ValueError: Probabilities do not sum to 1` ile düşüyordu. `_double_weights(w)`
çiftlemeden sonra yeniden normalleştirir. Test 242 artık `--critical-boost 2.0`
ile koşuyor (ağırlık yolu ancak `boost > 1` ve `degenerate == false` iken
devreye girer).

**R-D koşusu (değer-only, 10 iterasyon, 5 000 oyun, seed 11).**

| Ölçüm | Başlangıç | Bitiş |
|---|---|---|
| CE (buffer) | 0,9307 | **0,6762** |
| equity MAE | 0,8220 | **0,6166** |
| kalibrasyon eğimi | 0,9957 | **1,0043** |
| politika kaybı | 1,1007 | 1,1238 |
| süre | | 1 058 s |

**Kapı: GEÇMEDİ.** `corr = −0,5905` (eşik |corr| ≥ 0,99); normalize antisimetri
oranı 0,837 → 0,707. Veri artırımı bir **gradyan teşviki**dir; tam antisimetri
**mimari** ya da **çıkarım anında** zorlanmalıdır.

**Kalıcı çözüm: çıkarım anı antisimetrikleştirmesi.**
`ê(x) = (f(x,+1) − f(x,−1))/2` tanımı gereği **tam** antisimetriktir:
`ê(flip(x)) = (f(flip(x),+1) − f(flip(x),−1))/2 = (f(x,−1) − f(x,+1))/2 = −ê(x)`.
Ölçülen kazanç (n = 1000, `model_v30`): politika ER 0,0402 → 0,0343
(GA [−0,0111; −0,0009], **İYİLEŞTİ**). Maliyet ONNX başına iki ileri geçiş.

**Uyarı.** Aynı ölçüm R-D modelinde (`model_v10`) **ters** sonuç verdi:
politika ER 0,0385 → 0,0489 (+0,0104, GA [+0,0051; +0,0157]). Çıkarım anı
antisimetrikleştirmesi koşulsuz kalıcı çözüm değildir.

### 36.19 R-D ölçütü: iki bakışlı ER (F7-101)

> **DÜZELTME (§36.22 / F7-104).** Bu bölümün önerdiği ölçüt **yanlıştı**.
> Üretimde model her zaman sıra kimdeyse onun bakışını görür; (−1) bakışı
> hiç oluşmaz. İki bakışlı ER, ürünün kullanmadığı bir dağılımı ölçüyordu.
> ppg ölçümü artırımın tabandan 0,16 ppg **kötü** olduğunu gösterdi.
> Doğru ölçüt tek bakışlı ER'dir (ppg ile R² = 0,9994).

**Önceki yorum yanlıştı.** Eşleşmiş self-play deneyi (`rd_sp_ctl` vs
`rd_sp_aug`, 10 iterasyon, 2 000 oyun, depth 0, seed 11, `v30`'dan başlatılmış)
artırımın **her** tek-bakış metriğinde kötü olduğunu gösterdi ve R-D
hipotezinin yanlışlandığı sanıldı. Sebep ölçüm hatasıydı.

**Kök neden: havuz tek bakışlı.** `curve_pool` aday vektörlerini
`vectorize(..., perspective=turn)` ile üretir — her afterstate **oynayan**
tarafın bakışından yazılır. `flip_perspective(x)` ise aynı fiziksel
afterstate'in **oynayacak** tarafın bakışıdır; bu dağılım havuzda **hiç yok**
(havuz afterstate tutar, hamle-öncesi pozisyon tutmaz). Bu yüzden artırım
`ER(+1)`'i kötüleştirirken `ER(−1)`'i düzeltir; tek bakışlı ölçüm bu takası
göremez.

**`flip_perspective` doğru.** "12× fark" (yalnız çevrilmiş vektörlerle eğitim
0,0837 vs 0,0066) dönüşümün bozuk olduğu sanıldı. Kontrollü deney çürüttü
(aynı ağ, aynı adım, aynı tohum):

| Eğitim verisi | ER (orijinal held-out) | ER (çevrilmiş held-out) |
|---|---|---|
| orijinal | **0,0678** | 0,3304 |
| yalnız çevrilmiş | 0,3234 | **0,0642** |
| ikisi | 0,0942 | 0,0817 |

Fark **tam simetrik**; bozuk bir dönüşüm bunu üretemez. Ayrıca
`flip_perspective(v) == vectorize(aynı tahta, perspective=−turn)` 400 rastgele
pozisyonda birebir (maks fark 0,0; Test 160) ve ters-çevirmesiz varyant 12 hata
veriyor — `j → 25−j` terslemesi şart.

**Ölçüm (400 oyunluk havuz, 2 667 held-out pozisyon).**

| Model | ER(+1) pol/değer | ER(−1) pol/değer | **Ortalama** pol/değer | Asimetri (değer) |
|---|---|---|---|---|
| `v30` (taban) | 0,0270 / 0,0287 | 0,1081 / 0,1019 | 0,0675 / 0,0653 | 3,6× |
| `rd_sp_ctl` v10 | 0,0355 / 0,0354 | 0,1220 / 0,1282 | 0,0787 / 0,0818 | 3,6× |
| `rd_sp_aug` v10 | 0,0479 / 0,0489 | 0,0731 / 0,0799 | **0,0605 / 0,0644** | **1,6×** |

**Artırım kazanıyor.** Kontrole göre ortalama ER politika **−%23**, değer
**−%21**; asimetri oranı 3,6× → 1,6×. `v30` tabanının ortalamasını da geçiyor.
Tek bakışlı ER'deki kayıp (+0,012/+0,014) karşı bakıştaki kazancın
(−0,049/−0,048) yanında küçük.

**Araç.** Ölçüm `curve_pool`'a taşındı: `measure_er(..., perspective=)`,
`measure_er_both(...)` (`<yol>` / `<yol>Opp` / `<yol>Mean`),
`perspective_asymmetry(report, path)` ve CLI
`curve_pool measure-er --model ... --perspective both`. Test 245–249.

**Açık kalan.** İki bakışlı ER hâlâ **afterstate** dağılımı üzerindedir;
üretim yolu (arama) farklı bir dağılım görür. Nihai karar ppg'dir (K3) ve
R-F'de ölçülecek.

### 36.20 R-D 10 000 oyunluk doğrulama koşusu (F7-102)

> **DÜZELTME (§36.22 / F7-104).** "Kazanç" iki bakışlı ER'de görülüyordu.
> ppg ürün ölçümünde artırımlı model tabandan **0,16 ppg kötü** (z = −3,82).
> Bu bölümün sonucu geçersizdir.

Eşleşmiş deney 2 000 oyunla yapılmıştı. Aynı karşılaştırma **10 000 oyun**
(300 adım, depth 0, seed 11, 10 000 oyunluk buffer, `ckpt_v30.pt`'den
başlatılmış, 10 iterasyon) ile tekrarlandı. İki koşu **paralel** çalıştı.

| Koşu | Bayrak | CE (buffer) | equity MAE | politika kaybı | süre |
|---|---|---|---|---|---|
| `rd_ctl10k` | — | 0,9263 → 0,9104 | 0,8177 → 0,8099 | 1,0935 → **1,0738** | 2 626 s |
| `rd_aug10k` | `--augment-perspectives` | 0,9387 → 1,0249 | 0,8268 → 0,8983 | 1,0932 → 1,1909 | 4 594 s |

**Tek bakışlı metrikler yine artırımı kötü gösteriyor** (CE +0,086, equity MAE
+0,072, politika kaybı +0,117). İki bakışlı ölçüm bunun tersini söylüyor:

| Model | ER(+1) pol | ER(−1) pol | **Ort** pol | ER(+1) değer | ER(−1) değer | **Ort** değer | Asimetri pol/değer |
|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` (taban) | 0,0270 | 0,1081 | **0,0675** | 0,0287 | 0,1019 | **0,0653** | 4,00× / 3,55× |
| `rd_ctl10k/model_v10` (kontrol) | 0,0298 | 0,1202 | **0,0750** | 0,0302 | 0,1177 | **0,0739** | 4,03× / 3,90× |
| `rd_aug10k/model_v10` (artırımlı) | 0,0383 | 0,0691 | **0,0537** | 0,0387 | 0,0717 | **0,0552** | **1,80× / 1,85×** |

**Artırım kazanıyor ve fark büyüyor.** Kontrole göre ortalama ER politika
**−%28**, değer **−%25**; `v30` tabanına göre **−%20 / −%15**. Asimetri oranı
4,0× → 1,8×. 2 000 oyunluk deneydeki kazanç (−%23 / −%21) **korundu ve
büyüdü**, yani sonuç ölçek gürültüsü değil.

**Tek bakışlı ER neden yanıltıcı — sayısal kanıt.** Artırımlı model
`ER(+1)`'de 0,0270 → 0,0383 (**+0,0113 kötü**) ama `ER(−1)`'de 0,1081 → 0,0691
(**−0,0390 iyi**). Net etki ortalamada −0,0138. Tek bakışlı ölçüm yalnız ilk
sayıyı görür.

**Yan bulgu: kontrol de bozuluyor.** `rd_ctl10k` taban `v30`'a göre ortalamada
kötüleşiyor (0,0675 → 0,0750). Yani R-D'nin kendi kendine oynama turu, artırım
olmadan **zarar veriyor**; artırım bu bozulmayı tersine çevirip tabanın da
altına iniyor. Bu, F7-100'deki "politika kafası bozuluyor" gözleminin
artırıma değil, **kendi kendine oynama turuna** ait olduğunu gösteriyor.

**Kapı hâlâ geçmiyor ama her eksende iyileşiyor.** `|corr| ≥ 0,99` eşiği bu
mimariyle ulaşılabilir değil. Kapı **teşhis** olarak kalmalı; karar iki bakışlı
ER ve (R-F'de) ppg ile verilir.

| Model | `corr` | `meanAbsSum` | `argmax` uyumu | ER farkı | Kapı |
|---|---|---|---|---|---|
| `v30` (taban) | −0,8915 | 0,7152 | 0,348 | −0,0479 | DÜŞTÜ |
| `rd_ctl10k` (kontrol) | −0,8776 | 0,6006 | 0,295 | −0,0614 | DÜŞTÜ |
| `rd_aug10k` (artırımlı) | **−0,9426** | **0,2827** | **0,392** | **−0,0302** | DÜŞTÜ |

Artırım `corr`'u −0,8776 → −0,9426'ya (eşiğe yaklaşıyor), ER farkını
−0,0614 → −0,0302'ye (**yarıya**) indiriyor ve `meanAbsSum`'ı 0,7152 → 0,2827
yapıyor. Yani artırım doğru yönde çalışıyor; eşik mimari bir kısıt.

**Çıkarım anı antisimetrikleştirmesi artık gereksiz.** `rd_aug10k` üzerinde
(n = 1000): politika 0,0485 → 0,0457 (−0,0028, GA [−0,0083; +0,0028],
**kanıtlanmadı**); değer 0,0627 → 0,0573 (−0,0054, GA [−0,0123; +0,0013],
**kanıtlanmadı**). Model zaten 1,8× asimetrik olduğu için düzeltilecek pay
kalmamış — `v30`'daki 4,0× asimetride kazanç anlamlıydı. **Artırım,
antisimetrikleştirmenin yerini alıyor.**

**Araç.** `curve_pool measure-er` artık **çoklu model** alır ve
`--out` verilirse JSON + markdown karşılaştırma tablosu yazar
(`_model_label` koşu dizinini etikete katar; `onnx/` ara dizini atlanır).
Test 250–251. Artefaktlar: `ml/artifacts/er_two_perspective.json` / `.md`,
`ml/artifacts/antisymmetry_rd_aug10k.json`, `antisymmetry_rd_ctl10k.json`,
`antisymmetry_rd_aug10k_symmetrised.json`.



### 36.21 K3 — oyun sıklığına ağırlıklı ER (hedef metrik)

**Sorun.** `curve_pool` pozisyonları `corpus2` katmanlamasından gelir ve bu
katmanlama **temas ağırlıklıdır** (`PHASE_SHARES = contact 0,60 / bar 0,25 /
race 0,15`). Oynanan oyunlarda dağılım farklıdır, dolayısıyla ham ER oynanan
yolu temsil etmez: havuzda fazla temsil edilen faz ER'yi domine eder.

**Ölçülen gerçek dağılım.** `real_phase_shares` shard'lardan ölçer. **Tüm
adaylar** sayılır (`cand_vectors`), yalnız seçilen hamle değil: model üretimde
her adayı değerlendirir, seçilen aday ise vuruşa eğilimlidir ve "bar" payını
şişirir (yalnız-seçilen ölçümü bar 0,451 / temas 0,377 / yarış 0,172 veriyordu).
`stage_d_l2` shard 1, 10 000 oyun:

| Faz | Havuz payı (2 667 held-out) | Gerçek oyun payı (shard 1) | Ağırlık |
|---|---|---|---|
| contact | 0,6970 | 0,5219 | 0,75x |
| race | 0,1159 | 0,1292 | 1,12x |
| bar | 0,1871 | 0,3488 | **1,86x** |

Havuz teması 1,34x fazla, bar'ı 1,86x eksik temsil ediyor.

**Yöntem.** `game_frequency_weights(pool, indices, target)` her pozisyona
`target[faz] / have[faz]` ağırlığı verir, ortalamayı 1'e normalize eder
(ağırlıklı ER aynı ölçekte kalır), havuzda bulunmayan fazı düşürüp kalanları
yeniden normalize eder. `measure_er` / `measure_er_both` / `measure_summary`
`weights=` alır; ham liste pozisyon başına kalır, ağırlık yalnızca özetler.
`phase_of_vector` fazı vektörden okur: bar > yarış > temas (`ACTIVE_BAR` /
`OPP_BAR` / `IS_CONTACT`). `bearoff` / `closed` `HEADLINE_PHASES` dışında
olduğu için temas/yarışa katlanır — bilinçli.

**Sonuç — karar değişmiyor, güçleniyor.** 2 667 held-out pozisyon, iki bakışlı
ER:

| Model | Ort pol | **Ağırlıklı pol** | Fark | Ort değer | **Ağırlıklı değer** | Fark |
|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | 0,0675 | **0,0646** | −4,4% | 0,0653 | **0,0633** | −3,1% |
| `rd_ctl10k/model_v10` | 0,0750 | **0,0713** | −4,9% | 0,0739 | **0,0698** | −5,5% |
| `rd_aug10k/model_v10` | 0,0537 | **0,0492** | −8,5% | 0,0552 | **0,0500** | −9,3% |

Ağırlıklandırma **tüm** modellerin ER'sini düşürüyor (havuzun temas fazlalığı
ER'yi şişiriyordu) ve **artırımın kazancı büyüyor**:

- kontrole karşı: ağırlıksız −28,4% pol / −25,3% değer → ağırlıklı **−31,0% /
  −28,4%**
- `v30` tabanına karşı: ağırlıksız −20,5% / −15,5% → ağırlıklı **−23,8% /
  −21,0%**

Yani K3'nin "ham ER yanlı" uyarısı doğru, ama düzeltme R-D lehine. **Hedef
metrik artık ağırlıklı ER'dir; R-F bu metriği kullanır.**

**Araç.** `curve_pool measure-er --weight-by-game-frequency [--shard-dir ...]
[--shard-limit N]`; `--out` artık kendini tanımlayan bir sözlük yazar
(`pool`, `perspective`, `positions`, `weighted`, `realShares`, `shardDir`,
`shardLimit`, `models`) ve markdown'a K3 bölümünü ekler. Test 254–262.
Artefaktlar: `ml/artifacts/er_weighted.json` / `.md` (ağırlıklı),
`ml/artifacts/er_two_perspective.json` / `.md` (ağırlıksız, aynı şema).

**Sağlamlık — hedef seçimine duyarlı değil.** İki bağımsız gerçek-dağılım
tahminiyle aynı sonuç: shard ölçümü (bar 0,3488 / temas 0,5219 / yarış 0,1292)
ve korpus v2'nin `realGamePhaseWeights` alanı (bar 0,3706 / temas 0,5564 /
yarış 0,0730). İkincisiyle: kontrole karşı **−31,5% pol / −29,0% değer**,
`v30`'a karşı **−24,5% / −21,6%** — birincisiyle −31,0% / −28,4% ve −23,8% /
−21,0%. Fark 1 puandan az; **artırım kararı ağırlık seçimine bağlı değil.**
(`er_paths` zaten korpus ağırlığını kullanıyor; `curve_pool` afterstate
dağılımını kullanıyor — ER afterstate üzerinde ölçüldüğü için ikincisi daha
doğru, ama fark kararı değiştirmiyor.)

**Açık kalan.** (a) Gerçek paylar tek shard'dan (10 000 oyun) ölçüldü; 30
shard'ın tamamı daha dar bir GA verir ama paylar oyun sayısıyla hızlı sabitlenir.
(b) ER hâlâ **afterstate** düzeyinde; ppg eşleşmesi R-F'de ölçülecek.
(c) `m = 0,02 ppg` eşiği kullanıcı kararı, R-F'de netleşecek.
### 36.22 R-F — ppg ürün ölçümü R-D artırımını çürüttü (F7-104)

**Ölçüm.** Üç model, aynı koşu koşulları (küpsüz para oyunu, eşleştirilmiş
zar + renk takası, gnubg 0-ply, `search1`, tohum 2026, 2000 oyun = 1000
çift). Artefakt: `ml/artifacts/ppg_models.json` / `.md`.

| Model | Kazanma | ppg | ppg %95 GA | ER(pol, +1) | ER(val, +1) |
|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | 0,4340 | **−0,1635** | [−0,2230; −0,1050] | 0,0270 | 0,0287 |
| `rd_ctl10k/model_v10` | 0,4320 | **−0,1990** | [−0,2600; −0,1380] | 0,0298 | 0,0302 |
| `rd_aug10k/model_v10` | 0,3765 | **−0,3240** | [−0,3810; −0,2670] | 0,0383 | 0,0387 |

**İkili farklar** (iki örnekli GA):

| a | b | a − b | %95 GA | z | Anlamlı |
|---|---|---|---|---|---|
| `rd_ctl10k` | `v30` | −0,0355 | [−0,1213; +0,0503] | −0,81 | hayır |
| `rd_aug10k` | `v30` | **−0,1605** | [−0,2429; −0,0781] | **−3,82** | **evet** |

**Sonuç: R-D perspektif artırımı ürün metriğinde ÇÜRÜDÜ.** Artırımlı model
tabandan 0,16 ppg **daha kötü** (p = 1,3e-4). Kontrol koşusu tabandan
istatistiksel olarak ayırt edilemiyor — yani 10k ölçekli self-play turu
**ne yardım ediyor ne de zarar veriyor**; zararı veren şey artırım.

**Kök neden — §36.19 yanlış ölçütü seçti.** `search1` **yalnızca değer
kafasını** kullanır (`er_paths.search1_values` içindeki tek skorer çağrısı
`scorer.values`; `scorer.logits` yalnızca `policy` yolunda). Artırım
değer kafasını **iki** bakıştan eğitiyor ve **hareket eden tarafın** bakışı
pahasına: ER(+1) 0,0287 → 0,0387. ppg tam olarak bu eksende bozuluyor.
Üretimde `BackgammonSearch` her iki kafaya da `s.turn` verir, yani model
**her zaman sıra kimdeyse onun bakışını** görür; (−1) bakışı hiç oluşmaz.
Dolayısıyla **iki bakışlı ER, ürünün hiç kullanmadığı bir dağılımı
ölçüyordu.** Kullanıcının R-D öncesi uyarısı ("(−1) bakış hiç görülmeyebilir
ve kapı bir genelleme teşhisi olur") **doğruydu**.

**ER → ppg eşlemesi (K3'ün kalan teslimatı).** Üç nokta üzerinde doğrusal fit:

| Kafa | Eğim (ppg / ER) | Kesişim | R² |
|---|---|---|---|
| policy | **−14,30** | +0,2247 | **0,9994** |
| value | −15,64 | +0,2798 | 0,9941 |

ER'deki bir birim ~**14,3 ppg**'ye karşılık geliyor ve ilişki neredeyse tam
doğrusal. Bu, **tek bakışlı (hareket eden tarafın) ER'yi geçerli bir ppg
vekili** yapar — ve o ölçüt zaten artırımın kötü olduğunu söylüyordu
(0,0383 vs 0,0298 vs 0,0270). Üç nokta az; eğim bir büyüklük mertebesi
olarak okunmalı, kesin katsayı olarak değil.

**Güç.** `ppg_levels.md`'den ampirik eşik **m = 0,1115 ppg** (gnubg
0-ply vs 2-ply @ money farkı −0,2229'un yarısı; GA sıfırı dışlıyor).
m = 0,1115 için gereken oyun sayısı 0-2@money'de **4337**; 2000 oyun
**yetersiz**. Bu yüzden "fark var" iddiası sağlam (z = −3,82) ama
"fark m'den büyük" iddiası resmî olarak kurulamaz: aug-vs-v30 GA'sı
[−0,2429; −0,0781], −m = −0,1115'i **dışlamıyor**. Nokta tahmini
(−0,1605) m'yi aşıyor ve çok daha kesin olan ER ölçümü aynı yönü
gösteriyor; **artırımın reddi güvenli**, "bir seviye fark" iddiası değil.

**Kararlar.**

1. **İki bakışlı ER (§36.19) karar ölçütü olmaktan çıkarıldı.** Tek bakışlı
   (hareket eden tarafın) ER kullanılır; ppg ile R² = 0,9994.
2. **`--augment-perspectives` varsayılan olarak KAPALI kalır** ve
   üretim/eğitim koşularında kullanılmaz. Bayrak yalnızca teşhis için duruyor.
3. **Antisimetri kapısı (`|corr| >= 0,99`) zaten teşhis**; şimdi gerekçesi
   de kayıtlı: ölçtüğü eksen üründe oluşmuyor.
4. **Sonraki kaldıraç gnubg damıtma**, self-play değil. Kontrol koşusu
   tabandan farksız; aynı veriden daha fazla self-play turu beklemek için
   kanıt yok. K5'in 6 sınıflı KL damıtması (`--dist-weight`) uygulandı ve
   kullanılmadı; sıradaki deney odur.

**Açık kalan.** (a) 2000 oyun m = 0,1115 için yetersiz; "eşdeğer" iddiası
için ≥4337 oyun gerekir. (b) ER→ppg eğimi 3 noktadan; ara ER seviyelerinde
(örneğin 0,032) doğrulanmadı. (c) `policy` yolu (search1 değil) için ppg
ölçülmedi; politika kafasının ürün katkısı ayrı bir koşu ister.
### 36.23 K1 havuz kapısı ve K4 "N için gereken veri" ölçütü (F7-105)

**K1 — kapı n ≥ 1245'te ölçülemedi, havuzda ölçüldü.** `antisymmetry.py
measure` korpus v2'yi kullanır; `corpus2.TARGET_POSITIONS_V2 = 1000`, yani
K1'in istediği n ≥ 1245 oradan karşılanamaz (korpusu yeniden üretmeden).
400 oyunluk havuzun (`curve_pool_400.npz`) held-out kümesi **2667 pozisyon /
50 727 afterstate** veriyor — gereksinimin 2,7 katı — ve istatistikler
anlamsal olarak aynı (`gnubg_distill.equity_of_probs` ≡
`equity.equity_from_exclusive`; ikisi de `probs @ EQUITY_WEIGHTS`).
`curve_pool.py`'ye `measure_gate()` ve `gate` alt komutu eklendi; çıktı
`ml/artifacts/antisymmetry_pool.json` / `.md`.

| Model | corr | meanAbsSum | argmax | ER(+1) | ER(−1) | Fark | 95% GA |
|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | −0,9100 | 0,4340 | 0,362 | 0,0287 | 0,0815 | −0,0527 | [−0,0582; −0,0474] |
| `rd_ctl10k/model_v10` | −0,8967 | 0,4247 | 0,327 | 0,0302 | 0,0929 | −0,0627 | [−0,0687; −0,0569] |
| `rd_aug10k/model_v10` | **−0,9641** | **0,1479** | **0,438** | 0,0387 | 0,0499 | **−0,0112** | [−0,0151; −0,0078] |

Artırım **her eksende** iyileştiriyor (corr −0,9100 → −0,9641, meanAbsSum
0,4340 → 0,1479, argmax 0,362 → 0,438, ER farkı −0,0527 → −0,0112) ama
`|corr| ≥ 0,99` eşiğini **hâlâ geçmiyor**. Bu, kapının bir teşhis olduğunu
ve karar ölçütü olmadığını (§36.22) nicel olarak doğruluyor: artırım kusuru
4,7 kat azaltıyor, yine de ürün metriğinde 0,16 ppg kaybettiriyor. Yani
kusurun büyüklüğü ile ürün zararı arasında ilişki **yok**.

**K4 — etiket artık "N için gereken veri" ile de veriliyor.** Eskiden etiket
yalnızca eğim işaretine ve tohum oylamasına bakıyordu; K4 bunun "bu N için
gereken veri" tahminiyle çelişmemesi gerektiğini söyledi.
`learning_curve.py`'ye eklendi:

* `DATA_TARGET_RATIO = 0,5` — hedef, ölçülen en iyi ER'nin yarısı.
* `DATA_BUDGET_MULTIPLIER = 100` — bütçe, ölçülen en büyük pozisyon sayısının
  100 katı (1 056 000).
* `data_requirement(fit, target)` — `ER = a·N^−b + c`'yi ters çevirip
  `N = (a / (target − c)) ** (1/b)` verir; `target ≤ c` ise `inf` (taban
  hedefin üstünde → ne kadar veri olsa da ulaşılmaz).
* `DataRequirement.decision`: `inf` → `pipeline`, sonlu ve ≤ bütçe →
  `olcek`, sonlu ama bütçe üstü → `belirsiz`.
* `CurveReport.decision` artık **üç ölçütün anlaşmasını** istiyor: eğim,
  tohum oylaması ve `data_decision`. Çelişki → `belirsiz`.

Gerçek 7 noktalı eğri üzerinde sonuç (`ml/artifacts/learning_curve.md` §4.2):

| Yol | En iyi ER | Hedef | Taban (c) | Gereken N | Bütçe | Karar |
|---|---|---|---|---|---|---|
| `policy` | 0,0158 | 0,0079 | 0,0003 | **103 433** | 1 056 000 | `olcek` |
| `value` | 0,0330 | 0,0165 | **0,0223** | **inf** | 1 056 000 | `pipeline` |

**Bu, §36.22'nin nicel biçimidir.** Politika kafası ölçekle sınırlı
(103 433 pozisyon — ulaşılabilir), değer kafası ise **hatta** sınırlı:
tabanı 0,0223, hedefi 0,0165'in **üstünde**, yani ne kadar veri eklenirse
eklensin yarıya inmez. `search1` **yalnızca değer kafasını** kullandığı için
(`er_paths.search1_values`) ürün metriğini veri miktarı **iyileştiremez**.
Bu, "sonraki kaldıraç gnubg damıtma" kararının (§36.22, karar 4) sayısal
gerekçesidir.

**Testler.** `test_curve_pool.py` 271–275 (kapı: işaret/simetri, argmax
uyuşması, GA, etiket biçimi) ve `test_learning_curve_k4.py` 276–283
(`data_requirement` ters çevirme, `inf` taban durumu, bütçe sınırı, üç
ölçüt anlaşması/çelişkisi, markdown §4.2). Toplam pytest sayısı
1394 → **1407**.

**Açık kalan.** (a) Taban `c` GA'ları geniş (value: [0,0148; 0,0252]) —
`c`'nin hedefin üstünde olduğu **nokta tahminine** dayanıyor, GA'nın
tamamına değil. (b) `policy` yolunun ppg'si hâlâ ölçülmedi (K5 koşusu
sürüyor).

**Onay (2026-11-21).** Kullanıcı `DATA_TARGET_RATIO = 0,5` ve
`DATA_BUDGET_MULTIPLIER = 100` değerlerini **kabul etti**. Bu iki sabit
artık varsayım değil, onaylanmış parametredir; değiştirmek yeni bir onay
gerektirir (Kural 2).
## §36.24 — K5: yol × model ppg matrisi ve 6 sınıflı KL deneyi

K5 iki şey istiyordu: (a) **politika-argmax ve değer-0-ply** oyununun
ppg'sini ölç, (b) **6 sınıflı KL** ile değer başlığını yeniden eğit ve
`search1` ER/ppg'sini ölç. İkisi de yapıldı; ikincisi **negatif** çıktı.

**Neden `value` yolu elma-elmaya.** gnubg 0-ply da after-state
değerlendirmesiyle oynar; `value` yolu (değer kafası argmax, 0-ply) aynı
sözleşmeyi kullanır. `search1` bir ply arar, `policy` değer kafasına hiç
dokunmaz. Üç yolun ppg'si kafaların ürün katkısını ayrıştırır.

`ml/vs_gnubg.py`'nin `OUR_PATHS` listesi `er_paths.PLAY_PATHS`'ten eksikti
(`value` yoktu); eklendi ve Test 284 iki listeyi birbirine bağladı.
`ml/ppg_paths.py` matrisi kurar (`ml/artifacts/ppg_paths.json` / `.md`).

Küpsüz para oyunu, eşleştirilmiş zar + renk takası, gnubg 0-ply, 2000 oyun
(1000 çift), tohum 2026:

| Model | politika-argmax | değer-0-ply | search1 |
|---|---|---|---|
| `stage_d_l2/model_v30` | −0,4430 [−0,5020; −0,3835] | −0,4150 [−0,4740; −0,3560] | **−0,1635** [−0,2230; −0,1050] |
| `rd_ctl10k/model_v10` | −0,4605 [−0,5180; −0,4015] | −0,4445 [−0,5040; −0,3860] | **−0,1990** [−0,2600; −0,1380] |
| `rd_aug10k/model_v10` | −0,5160 [−0,5755; −0,4565] | −0,5570 [−0,6175; −0,4960] | **−0,3240** [−0,3810; −0,2670] |

**`search1` her modelde tek kafalı yollardan ~0,25 ppg daha iyi** (yol
farkları −0,19 ile −0,28 ppg arası, hepsi anlamlı, |z| 4,6–6,6). Yani 1-ply
arama gerçek iş yapıyor: ne politika kafası ne de değer kafası tek başına
rekabetçi. Bu, `search1`'in değer kafasının **mutlak kalibrasyonundan**
değil **sıralamasından** faydalandığının ilk doğrudan kanıtıdır — ve
§36.23'ün "değer tabanı 0,0223" bulgusuyla çelişmez: sıralama doğru olduğu
sürece mutlak hata aramada kısmen telafi olur.

Model farkları (aynı yol, `model_v30` referans): `policy` yolunda ne `ctl`
(−0,0175, z −0,41) ne `aug` (−0,0730, z −1,71) anlamlı; `value` yolunda
`ctl` anlamsız (−0,0295, z −0,69), `aug` anlamlı (−0,1420, z −3,28);
`search1`'te `ctl` anlamsız (−0,0355, z −0,81), `aug` anlamlı (−0,1605,
z −3,82). **R-D artırımının zararı yalnızca `search1`'te değil, `value`
yolunda da ölçülüyor** — yani zarar arama katmanından değil, değer kafasının
kendisinden geliyor.

**Bitmeyen oyunlar (yeni bulgu).** `policy` **ve** `value` kafaları tek
başına bitmeyen oyun üretebiliyor: `pol_ctl` ve `val_ctl` koşuları
`MatchError: oyun 200 ply'de bitmedi` ile çöktü. `play_game`'e
`allow_unfinished` eklendi; bu oyunlar **0 puan** sayılıp **sayılır ve
raporlanır** (sessizce atılmaz). Gerçek oranlar çok küçük: `ctl` policy
1/2000, `ctl` value 2/2000. `search1` koşularında hiç görülmedi.

**6 sınıflı KL deneyi (negatif).** `train_policy_head`'in `dist_weight`
terimi zaten **değer kafasının** 6 sınıflı çıktı dağılımına uygulanan
`KL(gnubg_dağılımı ‖ model_dağılımı)`'dır (`probs = out[0]`,
`best_probs = probs.gather(...)`), yani K5'in "değer başlığı 6 sınıflı KL
ile yeniden eğitilsin" isteği bu terimle karşılanır. R-Q2 (gnubg hint 6
olasılık veriyor mu) **doğrulandı**: `label-policy --dists` 6 sınıflı
dağılım üretiyor.

Kurulum: 3000 pozisyon gnubg 2-ply dağılımıyla etiketlendi
(`ml/runs/k5_dist/policy_dist_3k.npz`, 67 316 aday, ortalama dağılım
[0,3228 0,2979 0,0418 0,2477 0,0852 0,0046], 4235 s). İki kol da
`ckpt_v30.pt`'den başladı, 4000 adım, lr 3e-4, batch 64, tohum 0,
`--value-weight 0,5`. Tek fark `--dist-weight` (0 ve 0,5).

| Yol | KL=0 | KL=0,5 | Fark | z |
|---|---|---|---|---|
| `policy` | 0,025966 | 0,026273 | +0,000307 | +0,10 |
| `value` | 0,044881 | 0,044475 | −0,000406 | −0,09 |
| `search1` | 0,022617 | 0,021507 | −0,001110 | −0,50 |

**Hiçbir yol anlamlı değişmedi** (|z| < 0,5). KL terimi kaybı domine
ediyordu (son kayıp 0,00210 → 0,02097), yani ağırlık zayıf değildi.
Sonuç: **değer kafasının platisi bir etiket-temsili sorunu değil.** Kontrol
kolu aynı 3000 pozisyonla politika ER'sini %35 düşürdü (0,0402 → 0,0260)
ama değer ER'sini **hiç** oynatmadı (0,0442 → 0,0449). Aynı veri hacmi bir
kafayı ciddi biçimde hareket ettirirken diğerini oynatmıyor; 6 sınıflı hedef
pozisyon başına 6 kat sinyal vermesine rağmen fark yok. Bu, §36.23'ün "değer
kafası **hatta** sınırlı" tespitini bağımsız olarak doğruluyor: kaldıraç
daha iyi kayıp değil, **daha fazla etiketli veri** (ve o da taban 0,0223'ü
hedefin altına indirmeye yetmiyor).

**Testler.** `test_vs_gnubg_paths.py` 284–286 (iki yol listesi aynı küme,
`_our_chooser` her yolu kendi `er_paths` fonksiyonuna gönderir, bilinmeyen
yol hata), `test_ppg_paths.py` 287–293 + 298 (etiket, matris, yinelenen
hücre reddi, yol/model farkları, markdown, bitmeyen oyun sayımının **kendi**
modeline yazılması), `test_vs_gnubg_unfinished.py` 294–297 (varsayılan
hata, `allow_unfinished` davranışı, çift bayrakları, markdown koşullu
paragraf), `test_er_paths_compare.py` 299–301 (iki raporun yol bazında
karşılaştırılması, tasarım uyuşmazlığının reddi, "etki yok" metni).
Toplam pytest sayısı 1407 → **1425**.

**Açık kalan.** (a) KL deneyi 3000 pozisyonla sınırlı; 10–30 bin
pozisyonla tekrarlanmadı (etiketleme gnubg 2-ply'de ~1,4 s/pozisyon, yani
30 bin ~12 saat). (b) `dist_weight` için yalnızca 0 ve 0,5 denendi; ara
değerler denenmedi. (c) `policy`/`value` yollarının bitmeyen oyun oranı
`search1` için ölçülmedi (hiç görülmedi, ama sistematik sayım yok).

### 36.25 K5 kapanışı: kafa dengesi ve "kayıp ağırlığı" adayının elenmesi

K5'in değer platosu için saydığı üç adaydan sonuncusu **kayıp ağırlığı
(w*MSE)** idi. (b) 6 sınıflı KL §36.24'te, (c) antisimetri kusuru §36.23'te
elenmişti; bu bölüm (a)'yı kapatır.

**Neden akla yatkındı.** `train_v2.py` damıtma modunda değer kafasını
**skaler MSE** ile, politika kafasını grup-softmax çapraz entropisi ile
eğitiyor. Ağırlıklar eşit (`c_value = c_policy = 1,0`) ama büyüklükler
değil. Paylaşılan gövde tek olduğu için hangi terimin gradyanı büyükse
gövdeyi o yönlendirir.

**Ölçüm.** Yeni `ml/head_balance.py` aynı kontrol noktasını ve aynı veriyi
kullanarak her terimi **tek başına** geri yayar ve gövdeye taşıdığı gradyan
normunu ayrı ayrı raporlar. Karar sayısı kayıp oranı değil **gradyan
oranıdır**.

`ckpt_v30.pt`, 3000 pozisyon:

| Terim | Kayıp | ‖dL/d(gövde)‖ |
|---|---|---|
| Politika grup-softmax CE | 1,394324 | 1,351443 |
| Değer skaler MSE | 0,170902 | 0,914423 |
| Kalibrasyon MSE | 0,170902 | 0,914423 |
| Değer 6 sınıflı CE (teşhis) | 1,480352 | — |
| KL(gnubg ‖ model) (teşhis) | 0,190459 | 0,632914 |

Kayıp oranı **8,16** ama gradyan oranı yalnızca **1,48**; değer teriminin
gövde gradyanındaki payı **%40,4**. Değer kafası **aç değil**; aday elendi.

**Yan bulgu — R-F'nin mekanizması.** Aynı ölçüm üç modelde tekrarlandı
(`ml/artifacts/head_balance_compare.json` / `.md`):

| Model | Politika CE | Değer MSE | Oran | Değer payı |
|---|---|---|---|---|
| `stage_d_l2/model_v30` | 1,3943 | 0,1709 | 1,48 | %40,4 |
| `rd_ctl10k/model_v10` | 1,4699 | 0,1697 | 1,19 | %45,6 |
| `rd_aug10k/model_v10` | 1,5659 | **0,1200** | **3,33** | **%23,1** |

Perspektif artırımı değer kafasının **eğitim kaybını düşürüyor**
(0,1709 → 0,1200) ama **gövde gradyanını yarıya indiriyor**
(0,9144 → 0,4263). Değer payı en düşük model, R-F'de `value` ve `search1`
ppg'si en kötü olan modeldir (`value` −0,1420, `search1` −0,1605, ikisi de
anlamlı). Yorum: artırım değer hedefini **kafanın tek başına**
fit edilebilir hâle getirdi, gövde değer-ilişkili özellikleri kodlamayı
bıraktı. Bu, R-F'nin "artırım değer kafasını vurdu" hükmünün mekanik
açıklamasıdır ve `search1`'in neden en çok zarar gördüğünü açıklar (arama
yalnızca değer kafasını kullanır).

**Sonuç.** Üç adayın üçü de elendi. Değer kafasının platosu bir **eğitim
sinyali** sorunu değil; **hedef tanımı / mimari** sorunu. F7-105'in taban
analizi (değer tabanı 0,0223 > hedef 0,0165) aynı yöne bakıyor.

**Araç.** `python ml/head_balance.py` (tek model),
`python ml/head_balance.py --compare a.json b.json ...` (çoklu model).
Çıktılar `ml/artifacts/head_balance.json` / `.md`,
`head_balance_{ctl,aug}.json` / `.md`, `head_balance_compare.json` / `.md`.

**Testler.** `test_head_balance.py` 302–309 (veri kümesi doğrulaması,
kayıp/gradyan ayrımı, oran tutarlılığı, `to_dict` şekli, markdown
bölümleri, `dist` yokken `nan` teşhis terimleri, çoklu model
karşılaştırması, eksik/bozuk denge dosyasının reddi).
Toplam pytest sayısı 1425 → **1433**.

**Yan düzeltme — `learning_curve.json` geçerli JSON değildi.** K4'ün
`inf` (ulaşılamaz hedef) durumu `json.dump` ile `"positions": Infinity`
olarak yazılıyordu. `Infinity` **RFC 8259'da geçerli değildir**; Python'un
`json` modülü kabul eder ama JS `JSON.parse`, C# `System.Text.Json` ve
`jq` dosyayı **tümden** reddeder. `DataRequirement.to_dict` artık sonlu
olmayan `positions` için `null` yazar; anlamı `decision` alanı taşır
(`pipeline`). Artefakt yeniden yazıldı ve `test_310` bunu kilitler
(`allow_nan=False` ile serileştirme + `Infinity`/`NaN` yokluğu).
Toplam pytest sayısı 1433 → **1434**.

**Açık kalan.** (a) Ölçüm tek veri kümesinde (3000 pozisyon) yapıldı;
10–30 bin pozisyonla tekrarlanmadı. (b) Gradyan payı bir *anlık görüntü*;
eğitim boyunca izlenmedi (her adımda ölçmek ~%30 yavaşlatır). (c) Değer
payı ile ppg arasındaki ilişki üç noktaya dayanıyor; dördüncü bir modelle
doğrulanmadı.
## 38. Faz 7-S — Kapasite profilleri: `large` / `xlarge` 30 bin pozisyonda

K5'in açık sorusu şuydu: `medium` (156 423 parametre) yeterli mi, yoksa
kapasite mi sınırlıyor? Bu bölüm soruyu **aynı veri, aynı kayıp, aynı test
seti** ile üç profil üzerinde yanıtlıyor.

**Veri.** `ml/gnubg_distill.py label-policy` dokuz parçaya bölündü
(`--shards 9 --shard-index 0..8`); sekizi yerelde, biri uzak işçide
(F7-108) paralel koştu. `merge-policy` parçaları birleştirdi:
`ml/runs/capacity30k/policy_30k.npz` — **30 006 pozisyon, 664 778 aday**,
aday başına ortalama 22,2, `dist` etiketleri var. Etiketleme gnubg 2-ply.

**Eğitim.** `ml/capacity_train.py run` üç profili sırayla eğitti. Ortak
ayarlar: 5000 adım, `lr` 1e-3, `batch` 64, `value-weight` 0,5,
`dist-weight` 0,5, `val-fraction` 0,1, `patience` 6, `eval-every` 500,
`weight-decay` 1e-4, kosinüs zamanlama (`lr-final-ratio` 0,1), CUDA.
`xlarge` ayrıca `rank-weight` 0,5 ile eğitildi.

| Profil | Parametre | Gizli | Süre | En iyi adım | Val CE | Val top-1 | Val MSE | Erken durdu |
|---|---|---|---|---|---|---|---|---|
| `medium` | 156 423 | 256-256-128 | 354 s | 2500 | 0,62328 | 0,7841 | 0,025107 | hayır |
| `large` | 642 567 | 512-512-512 | 584 s | 2500 | 0,63597 | 0,7857 | 0,024412 | hayır |
| `xlarge` | 1 805 832 | 1024-1024-512 | 1877 s | 2000 | 0,62749 | 0,7704 | 0,019258 | **evet** |

**Ölçüm.** `er_paths.py measure --plies 2 --limit 1000` (korpus v2, gnubg
2-ply hakem) ve `antisymmetry.py measure --limit 500 --plies 2`.

| Profil | Politika ER | Değer ER | `search1` ER | Antisimetri corr | meanAbsSum |
|---|---|---|---|---|---|
| `medium` | **0,016824** ± 0,001402 | 0,038926 ± 0,003344 | 0,026074 ± 0,001924 | −0,9016 | 0,2944 |
| `large` | 0,018694 ± 0,001775 | 0,036066 ± 0,003181 | **0,022040** ± 0,001543 | **−0,9428** | **0,2384** |
| `xlarge` | 0,018891 ± 0,001995 | **0,035147** ± 0,003038 | 0,024256 ± 0,001791 | −0,8370 | 0,4211 |

**Karar: Test 96 kuralı gereği kazanan yok.** Değer ER'si kapasiteyle
tekdüze düşüyor (0,038926 → 0,036066 → 0,035147) ama 11,5× parametre
yalnızca **%9,7** kazanç getiriyor; eşik %15. `large` %7,3'te kalıyor ve
standart hatalar (0,0033 / 0,0032) farkı neredeyse yutuyor.

**Üç ayrı bulgu.**

1. **Politika kafası kapasiteden kazanmıyor, kaybediyor.** `medium`
   0,016824 ile en iyi; `large` 0,018694, `xlarge` 0,018891. 30 bin
   pozisyon 156 bin parametre için zaten yeterli; büyük ağ aynı sinyali
   daha çok ezberliyor (eğitim CE 0,4338 → 0,3900, doğrulama CE tersine
   dönüyor).
2. **`xlarge` erken durdu.** 2000. adımda en iyi doğrulama CE'sine ulaşıp
   6 değerlendirme boyunca iyileşmedi (5000 adımın %40'ı). 1,8 milyon
   parametre 30 bin pozisyonu taşımıyor; bu turda ölçülen şey kapasite
   tavanı değil **veri tavanı**.
3. **`search1` `large`'ı işaret ediyor.** Ürün yolu `search1`; orada
   `large` **%15,5** kazançla eşiği geçiyor (0,026074 → 0,022040),
   `xlarge` %7,0'da kalıyor. Değer-ER kuralının görmediği bir sinyal:
   `large`'ın değer kafası mutlak olarak çok daha iyi değil ama
   **sıralaması** daha iyi ve arama sıralamadan faydalanıyor (§36.24).
   Tek ölçüm, tek tohum, 1000 vaka — bu bir **aday**, karar değil.

**Antisimetri kapısı hiçbir profilde geçmiyor.** `large` en yakın
(−0,9428) ama eşik 0,99; `xlarge` **daha kötü** (−0,8370). Kapasite artışı
bu kusuru düzeltmiyor, büyütüyor. Bu, F7-101/F7-105'in "kusur mimaride,
kapasitede değil" teşhisini doğruluyor: çözüm `augment_perspectives` (R-D)
veya çıkarım anı antisimetrikleştirmesi.

**Ürün önerisi.** Varsayılan model `medium` olarak kalır (politika yolunda
en iyi, en hızlı, en küçük). `large` `search1` için aday olarak işaretlenir
ama R-D sonrası artırımlı eğitimle yeniden ölçülmeden ürüne alınmaz.
`xlarge` bu veri hacminde elenir; 100 bin+ pozisyon olmadan tekrar
denenmemeli.

**Altyapı değişiklikleri.**

* `ml/gnubg_distill.py` — `label-policy` `--shard-index`/`--shards`;
  yeni `merge-policy`; `PolicyDataset.subset()`; `concat_policy_datasets()`
  (parçalar `dist` konusunda anlaşmazsa `dist` düşürülür).
  `train_policy_head` yeniden yazıldı: `rank_weight`, `val_fraction`,
  `patience`, `eval_every`, `weight_decay`, `lr_schedule`, `lr_final_ratio`;
  deterministik doğrulama bölmesi; `_batch_tensors()` (parti başına
  genişlik kırpma); `_evaluate()`; en iyi duruma geri dönüşlü erken durma.
* `ml/model.py` — `BackgammonNetV2` `rank_head` aldı; sıralama kafası
  **yalnızca eğitimde** var, ONNX'e çıkmaz (`output_version = 2`
  sözleşmesi bozulmaz).
* `ml/model_large.py`, `ml/model_xlarge.py` — adlandırılmış giriş
  noktaları; ikinci bir mimari değil.
* `ml/capacity_train.py` — `run` / `measure` / `report` alt komutları.
  `measure --reuse` mevcut `er_paths.json` / `antisymmetry.json` dosyalarını
  gnubg'yi yeniden koşmadan okur. `report --notes` elle yazılmış yorumu
  rapora ekler.
* `ml/export_onnx.py` — `PARITY_RELATIVE_TOLERANCE = 1e-5`. Politika
  logit'i sınırsız; eğitilmiş modelde |logit| ≈ 52'ye çıkıyor ve float32
  birikim gürültüsü mutlak 1e-5 eşiğini aşıyor (göreli hata 2,2e-7'de
  kalıyor). `dp` artık `max(PARITY_TOLERANCE, PARITY_RELATIVE_TOLERANCE *
  max(1, |logit|))` ile karşılaştırılıyor.

**İki performans düzeltmesi.** (a) Küresel genişliğe yastıklama 10×
yavaşlatıyordu: veri kümesinin en geniş pozisyonu 443 aday, ortalama 22,2.
`_batch_tensors()` her partiyi kendi genişliğine kırpıyor; adım süresi
383,8 ms → 234 ms, `valCe` bit bit aynı. (b) Sabit `lr = 1e-3` 1500 adım
sonra aşırı öğreniyordu (`medium` 0,64605 → 0,83). `weight_decay = 1e-4` +
kosinüs zamanlama bunu düzeltiyor (ara denemede 0,61645).

**Belgeler.** `ml/artifacts/stage_large_xlarge_report.md` (tablo + karar +
yorum), `ml/artifacts/stage_large_xlarge.json` (makine okunur),
`ml/artifacts/stage_large_xlarge_notes.md` (yorumun kaynağı).
Toplam pytest sayısı 1434 → **1456**; §6 toplamı 1919 → **1941**.

**Açık kalan.** (a) Tek tohum: üç profilin her biri tek koşu, tohum
varyansı ölçülmedi; `large`–`medium` farkının (%7,3) tohum gürültüsünden
büyük olduğu gösterilmedi. (b) `search1` kazancı 1000 vaka üzerinden;
`large`–`medium` farkı 0,004034 ≈ 1,7 SE, sınırda. (c) `xlarge` erken
durduğu için "kapasite işe yaramıyor" sonucu yalnızca bu veri hacminde
geçerli. (d) Antisimetri 500 vaka; `large` ile `medium` arasındaki corr
farkı bu örneklemde anlamlı mı, ölçülmedi. (e) ppg ölçümü yapılmadı;
`search1` ER kazancının ppg'ye dönüşüp dönüşmediği bilinmiyor.
## 39. Faz 7-R — Aşama R-D: liste tabanlı KL politika kaybı (F7-110)

**Soru.** R-C sonunda politika kafası hâlâ "oynanan hamle" üzerinden sert
çapraz entropi ile eğitiliyordu. gnubg etiketleyicisi zaten **aday başına
equity** üretiyor (`cand_equity`, R-04/R-17); bu bilgi kullanılmıyordu.
Liste tabanlı kayıp bunu kullanır mı, ve kazanç gerçek mi?

**Kayıp.** `_policy_loss` (`ml/gnubg_distill.py`) iki modda çalışıyor:

* `policy_temperature = 0` → eski davranış, `F.cross_entropy(logits, best)`.
* `policy_temperature > 0` → liste bazlı KL. Etiketli adaylar için
  `target = softmax(cand_equity / T)`, `pred = softmax(logits)`,
  `KL(target ‖ pred)`; etiketsiz adaylar (`nan`) `-1e9` ile maskelenir.
  Pozisyon, en az bir etiketli aday varsa kayba girer.

Maskeli aday oranı `policy_30k_rd.npz` üzerinde **0,6272**; yani adayların
%62,7'si etiketsiz (gnubg `hint` en fazla 10 hamle yazıyor). Bunlar negatif
örnek değil, maskeleniyor (R-17).

**Sıcaklık pilotu.** `medium`, tohum 0, 5000 adım, 30 bin R-D verisi,
6 değer, sıralı koşu (~3,5 dk/değer):

| T | valTop1 | valValueMse | valCe |
|---|---|---|---|
| 0,02 | 0,8044 | 0,01408 | 0,2345 |
| 0,05 | 0,8127 | **0,01255** | 0,1133 |
| **0,1** | **0,8157** | 0,01329 | **0,1094** |
| 0,2 | 0,8051 | 0,01519 | 0,1707 |
| 0,5 | 0,7711 | 0,01630 | 0,2669 |
| 1,0 | 0,7391 | 0,01644 | 0,3142 |

Hepsi 5000 adımı tamamladı, erken durma yok. **T = 0,1 seçildi** (en iyi
`valCe` ve `valTop1`). T = 0,05 değer kafasında biraz daha iyi ama politika
CE'si %3,6 daha kötü; T ≥ 0,5 keskin bozuluyor — hedef dağılım düzleşince
sinyal kayboluyor.

**5 tohumlu `large` taraması** (T = 0,1, 5000 adım, hepsi `bestStep = 5000`,
erken durma yok):

| tohum | valCe | valTop1 | valValueMse |
|---|---|---|---|
| 0 | 0,10624 | 0,8224 | 0,01381 |
| 1 | 0,10680 | 0,8181 | 0,01198 |
| 2 | 0,10604 | 0,8197 | 0,01134 |
| 3 | 0,10542 | 0,8184 | 0,01139 |
| 4 | 0,10747 | 0,8137 | 0,01203 |
| **ortalama** | **0,1064** (sd 0,00078) | **0,8185** (sd 0,0031) | **0,01211** (sd 0,00101) |

Karşılaştırma: R-E `large` (eski kayıp) valTop1 0,7829 (sd 0,0037),
valValueMse 0,0218 (sd 0,00487); R-E `medium` 0,7793 / 0,02358. Yani
`valTop1` **+4,6% göreli**, `valValueMse` **−44% göreli**.

**ER ölçümü — metodolojik düzeltme (`--stride`).** `reference_corpus_v2.json`
vakaları faz sırasına göre diziliyor: contact(600) → bar(250) → race(150).
Bu yüzden `--limit 300` **%100 contact** veriyordu; faz temsili değil.
`er_paths.py` ve `antisymmetry.py`'ye `--stride` eklendi ve `--limit`'ten
**önce** uygulanıyor. `--stride 3 --limit 300` → {bar 84, contact 200,
race 16}; gerçek oyun ağırlıkları {bar 0,3706, contact 0,5564, race 0,0730}.
**Alt örneklemeli her ER ölçümü `--stride` kullanmak zorunda.**

**ER sonuçları** (300 vaka, `--stride 3`, 2-ply):

| koşu | politika | değer | search1 |
|---|---|---|---|
| R-E `medium` (3 tohum) | 0,020402 | 0,034547 | 0,021723 |
| R-E `large` (3 tohum) | 0,016347 | 0,031124 | 0,023166 |
| **R-D `large` (5 tohum)** | **0,012408** (sd 0,00089) | **0,019507** (sd 0,00160) | **0,014360** (sd 0,00061) |

**Eşleşmiş bootstrap** (3 ortak tohum × 300 vaka, 2000 yeniden örnekleme):

| karşılaştırma | yol | kontrol | tedavi | göreli | p |
|---|---|---|---|---|---|
| R-E `large` → R-D `large` | politika | 0,016347 | 0,012511 | **−23,5%** | 0,0030 |
| | değer | 0,031123 | 0,018559 | **−40,4%** | 0,0000 |
| | search1 | 0,023166 | 0,014373 | **−38,0%** | 0,0000 |
| R-E `medium` → R-D `large` | politika | 0,020402 | 0,012511 | **−38,7%** | 0,0000 |
| | değer | 0,034547 | 0,018559 | **−46,3%** | 0,0000 |
| | search1 | 0,021723 | 0,014373 | **−33,8%** | 0,0000 |

Üç yolun üçü de anlamlı. R-D `large`, R-E `medium`'ı da anlamlı şekilde
geçiyor — yani kazanç yalnızca kapasite değil, kayıp değişikliği.

**Ablasyon — kayıp mı, veri mi?** Aynı R-D verisi, aynı tohum 0, yalnızca
`--policy-temperature 0` (eski kayıp): valCe 0,63653, valTop1 0,7861,
valValueMse 0,02437. ER: politika 0,016927, değer 0,031500, search1 0,023077.
R-D verisi + yeni kayıp (tohum 0): 0,011117 / 0,017263 / 0,013930.

| yol | eski kayıp | yeni kayıp | göreli | p |
|---|---|---|---|---|
| politika | 0,016927 | 0,011117 | **−34,3%** | 0,0030 |
| değer | 0,031500 | 0,017263 | **−45,2%** | 0,0000 |
| search1 | 0,023077 | 0,013930 | **−39,6%** | 0,0010 |

Kontrolün ER'si R-E `large` tohum 0'a neredeyse eşit (0,016927 vs 0,017157):
**veri değişikliği tek başına nötr, kazancın tamamı kayıp değişikliğinden.**

**Antisimetri — kapı hâlâ düşüyor ama pratik asimetri 4 kat azaldı.**
`|corr| ≥ 0,99` kapısı R-D'de de geçmiyor (corr −0,9464 … −0,9562). Ama
`erMinus` 0,19–0,24 → **0,047–0,054**, `argmaxRate` 0,18 → **0,47–0,52**.
Yani liste kaybı bakış tutarlılığını ciddi şekilde düzeltiyor; kalan corr
kusuru ER farkına neredeyse yansımıyor. `meanAbsSum` hafifçe kötüleşti
(0,23 → 0,29) — corr'un neden düşük kaldığının açıklaması bu olabilir:
büyük hatalar azaldı, küçük sistematik sapma kaldı.

**Çıkarım anında antisimetrikleştirme denendi, kazanmadı.** Önceki segmentte
`antisymmetry.py symmetrise` ile `ê(x) = (f(x,+1) − f(x,−1))/2` ölçüldü:
politika ER 0,038488 → 0,048880 (**+0,0104, kötü**), değer 0,200420 →
0,191039 (−0,0094, GA sıfırı içeriyor). Yani çıkarım anında düzeltme
kalıcı çözüm değil; eğitim tarafı (liste kaybı) doğru yol.

**Araç.** `ml/gnubg_distill.py` (`policy_temperature`, `_policy_loss`,
`TEMPERATURE_GRID`, `select_policy_temperature`); `ml/capacity_train.py`
(`--policy-temperature`, `compare --seeds`, `--stride`); `ml/er_paths.py` +
`ml/antisymmetry.py` (`--stride`). Koşu betikleri
`ml/runs/capacity_rd/run_tpilot.ps1`, `run_sweep_large.ps1`,
`run_control_large.ps1`, `run_measure_shard.ps1`. Karar dosyaları
`ml/runs/capacity_rd/compare/re_vs_rd_large.{json,md}`,
`ablation_loss.{json,md}`, `re_medium_vs_rd_large.{json,md}`.
Test sayısı 1494 → **1497** (3 yeni `--stride` testi); §6 toplamı
1979 → **1982**.

**Açık kalan.** (a) `xlarge` R-D ile denenmedi; `large` 5 tohumda hâlâ
erken durmuyor, `xlarge` için veri tavanı sorusu açık. (b) ER 300 vaka;
`--stride 3` faz temsili ama örneklem küçük — `search1` farkı 0,0088 ≈ 3 SE,
sağlam, ama `race` fazında yalnızca 16 vaka var. (c) ppg ölçümü yok; ER
kazancının ppg'ye dönüşüp dönüşmediği hâlâ bilinmiyor (eğim −14,30 ppg/ER
ile kaba tahmin: politika −0,0039 ER → ~0,056 ppg). (d) Antisimetri kapısı
(`|corr| ≥ 0,99`) hâlâ düşük; eşik mi yanlış, kusur mu kaldı, karar
verilmedi. (e) `maskedCandidateRate = 0,6272` — etiketsiz adayların hedef
dağılımdan tamamen çıkarılması, gerçek "ikinci en iyi" bilgisini
kaybettiriyor olabilir; denenmedi.
## 40. Faz 7-R / R-E — Kapasite yeniden testi ve küp ER'si

**Tarih.** 2026-02 (R-D sonrası).

**Amaç.** `large`, `medium`'a göre hamle kalitesinde gerçekten daha iyi mi —
aynı veri, aynı adım, aynı tohum setiyle, eşleştirilmiş bootstrap GA ile? Ve
bu kazanç **küp kararına** yansıyor mu? (Faz 7 v2.5 §4, R-E maddeleri 1–4.)

**Kurulum.** `ml/artifacts/reference_corpus_v2.json`, `--stride 3 --limit 300`
(faz temsili: bar 84 / contact 200 / race 16), gnubg 2-ply hakem, 3 tohum
(0, 1, 2), eşleştirilmiş bootstrap 2000 yeniden örnekleme, `Δ_min = %15`.

**Hamle ER'si.**

| koşu | politika | değer | search1 |
|---|---|---|---|
| `medium` (3 tohum) | 0,020402 | 0,034547 | 0,021723 |
| `large` (3 tohum) | 0,016347 | 0,031123 | 0,023166 |
| R-D `large` (5 tohum) | **0,012408** | **0,019507** | **0,014360** |

`medium` → `large` (aynı veri, aynı kayıp):

| yol | fark | %95 GA | göreli | p | anlamlı | Δ ≥ Δ_min |
|---|---|---|---|---|---|---|
| politika | −0,004056 | [−0,009667; −0,000293] | **−19,9 %** | 0,0250 | evet | **evet** |
| değer | −0,003423 | [−0,006753; −0,000223] | −9,9 % | 0,0390 | evet | hayır |
| search1 | +0,001442 | [−0,001374; +0,003934] | +6,6 % | 0,2760 | **hayır** | hayır |

`large` (R-E) → `large` (R-D, liste kaybı): politika −23,5 % (p = 0,0030),
değer −40,4 % (p = 0,0000), search1 −38,0 % (p = 0,0000) — üçü de anlamlı.

**Küp ER'si (madde 4).** `ml/artifacts/cube_corpus.json` (400 vaka, para +
5 ve 9 puan, Crawford hariç), gnubg 2-ply cubeful referans, 3 tohum. Hedef
**0,02**.

| koşu | tohum 0 | tohum 1 | tohum 2 | ortalama | sd |
|---|---|---|---|---|---|
| `medium` | 0,0753 | 0,0698 | 0,0772 | **0,0741** | 0,0038 |
| `large` | 0,0782 | 0,0576 | 0,0797 | **0,0718** | 0,0124 |
| R-D `large` | 0,0855 | 0,0898 | 0,0710 | **0,0821** | 0,0099 |

Eşleştirilmiş bootstrap (3 tohum × 400 vaka): `medium` → `large` −0,0022
GA [−0,0129; +0,0061] p = 0,6230; `large` → R-D `large` +0,0102
GA [−0,0092; +0,0343] p = 0,3810; `medium` → R-D `large` +0,0080
GA [−0,0079; +0,0265] p = 0,3250. **Hiçbiri anlamlı değil.**

**Kritik bulgu.** Liste kaybı hamle ER'sini üç yolda da %23–40 düşürdü ama
küp ER'sini **anlamlı şekilde değiştirmedi** (+0,0102, p = 0,38). Yani hamle
kalitesi kazancı küp kararına **transfer olmuyor**. Küp ER'si hedefin
3,6–4,1 katında (0,072–0,082 vs 0,02) ve R-C'de ölçülen 0,0642'den de kötü.

**Gecikme bütçesi.** Bütçe depth-2 p95 ≤ 2 s (Faz 7 §5.2 bacak b); üretim
derinliği **depth 1** (F7-09). 30 pozisyon, CPU:

| koşu | p50 | p95 | ortalama | bütçenin %'si |
|---|---|---|---|---|
| `medium` | 0,0175 s | **0,0626 s** | 0,0239 s | %3,1 |
| `large` | 0,0610 s | **0,2062 s** | 0,0714 s | %10,3 |
| R-D `large` | 0,0570 s | **0,2042 s** | 0,0744 s | %10,2 |

**B3 gerekçesiyle çelişki.** B3 (R-01) `medium`'u seçti çünkü `large` depth-2
p95 = 13,68 s > 2 s. Ama üretim depth-1'de çalışıyor ve orada `large` p95
0,2042 s. Yani B3'ün `large`'ı eleme gerekçesi **üretimde kullanılmayan bir
derinliğe** dayanıyordu. Bu bir hata değil, ama gerekçe artık geçerli değil.

**Karar: etiket `kanıtlanmadı`** (üç yolun üçü birden sağlanmadı;
`yanlışlandı` değil). Seçilen profil **`large`**: politika yolunda Δ_min ve GA
alt sınırı > 0 sağlanıyor, gecikme bütçenin %10'unda, ve R-D ile birlikte üç
yolda da anlamlı kazanç var. Ama "kapasite tek başına üç yolda kanıtlandı"
**denmez**.

**Araç.** `ml/capacity_train.py compare --seeds`; `Backgammon.MatchBench cube`
+ `ml/cube_er.py measure`; `Backgammon.MatchBench decision-latency`. Rapor
`ml/artifacts/stage_r_e_report.{json,md}`; karar dosyaları
`ml/runs/capacity_re/compare/medium_vs_large.{json,md}`,
`ml/runs/capacity_rd/compare/re_medium_vs_rd_large.{json,md}`.

**Açık kalan.** (a) Küp ER'si hiçbir profilde hedefe yaklaşmıyor; hamle
kalitesi ile küp kararı arasındaki bağ **kurulmadı**. (b) `xlarge` R-E'ye
girmedi. (c) ER 300 vaka, `race` fazında 16 vaka. (d) ppg ölçümü R-F'de.
## 41. Faz 7-R / R-F — Final kanıt tanımı (üç satır)

**Tarih.** 2026-02. **Durum.** Tamamlandı. **Etiket.** `eşdeğerlik kanıtlanmadı`.

**Amaç.** Modelin seviyesini tahminle değil ölçümle koymak. Nihai iddia **üç
ayrı satırdır** ve satırlar **toplanmaz** (Faz 7 v2.5 §4 R-F madde 4).

### Üç satırlık nihai rapor

| # | Satır | Ölçüm | Hedef | Sonuç |
|---|---|---|---|---|
| 1 | **Hamle kalitesi** | politika ER **0,0111** [0,0077; 0,0152], search1 **0,0139** [0,0101; 0,0185] (gnubg 2-ply hakem, 300 pozisyon) | gnubg 2-ply seviyesi | ❌ **Eşdeğer değil.** gnubg 0-ply 0,0062, gnubg 1-ply 0,0044 → model **gnubg 0-ply seviyesinde** |
| 2 | **Küp** | küp ER **0,0821** (3 tohum, 400 vaka) | 0,02 | ❌ **Karşılanmadı.** Hedefin **4,1 katı** |
| 3 | **Oyun gücü** | ppg **−0,2445** [−0,3055; −0,1835] (gnubg 2-ply'a karşı, 2000 oyun) | `H0: ppg_fark ≤ −m`, m = 0,1115 | ❌ **Eşdeğerlik kanıtlanmadı.** Üst sınır −0,1835 < −0,1115 → **daha kötü** |

**Rapor dili (madde 5).** "gnubg 4-ply'a göre eşdeğer" **denmez**;
"eşdeğerlik kanıtlanmadı" denir. "İnsan şampiyonu yendik" **denmez**.

### Madde 1 — Referans zinciri

Hakem kendi kendini ölçemez. İki derin hakem kullanıldı:

| Hakem | n | 0-ply | 1-ply | 2-ply | 3-ply | 4-ply |
|---|---|---|---|---|---|---|
| `hint`@3 | 40 | 0,0063 | 0,0027 | **0,0013** | — | — |
| `hint`@4 | 20 | 0,0049 | 0,0040 | **0,0006** | **0,0002** | ölçülemez |

**ER çözünürlük tabanı 0,0006–0,0013.** 4-ply'ın kendi ER'si **ölçülemez**
(5-ply/rollout bu makinede yok) ve satır öyle işaretlendi.

**Modelin merdivendeki yeri** (gnubg 2-ply hakem, 300 pozisyon):

| Oyuncu | ER | %95 GA | σ |
|---|---|---|---|
| gnubg 0-ply | **0,0062** | [0,0040; 0,0088] | 0,0212 |
| gnubg 1-ply | **0,0044** | [0,0029; 0,0063] | 0,0153 |
| R-D `large` politika | 0,0111 | [0,0077; 0,0152] | 0,0334 |
| R-D `large` search1 | 0,0139 | [0,0101; 0,0185] | 0,0375 |
| R-D `large` değer | 0,0173 | [0,0105; 0,0264] | 0,0711 |
| R-E `large` politika | 0,0172 | [0,0119; 0,0235] | 0,0524 |
| R-E `medium` politika | 0,0189 | [0,0133; 0,0255] | 0,0546 |

Model **gnubg 0-ply seviyesinde, biraz altında**. Tabanın 9–18 katı, yani
sinyal gürültüden net ayrılıyor.

**Yeni bulgu: `search1` politikadan kötü** (0,0139 vs 0,0111). Değer kafası en
zayıf yol (0,0173) ve `search1` derinlik-1 değerlendirmesini ondan alıyor.
**Arama, zayıf değer kafası yüzünden politikayı bozuyor.** Değer hedefi
değişikliği tartışması artık ölçülmüş bir gerekçeye sahip.

### Madde 2 — Rollout: ölçülemez

gnubg 1.08.003-mingw `rollout` komutu `Rollout done. Printing final results.`
basar ama **equity satırı basmaz**. Beş bağımsız deneme (`-t`, `-t -d`, `-c`,
`-p`, `set rollout cubeful off` + `set cube use off`, `set rollout trials 36`
+ `set rollout chequerplay plies 0`) hepsi aynı sonucu verdi. `rollout`
sonrası `eval` **statik** değer döndürür; Python API'sinde `rolloutcontext`
var ama `rollout` fonksiyonu yok; `--help` rollout seçeneği listelemez.

Maliyet ölçüldü: 36 deneme ≈ 30 s → 1296 deneme ≈ 18 dk → 400 rollout ≈
**120 saat tek çekirdek**. Kural 6 uyarınca **sıfır uydurulmadı**; satır
`ölçülemez` ve yerine madde 1'in çözünürlük tabanı kondu.

### Madde 3 — Oyun gücü

Eşleştirilmiş zar + renk takası, küpsüz para, 10 paralel süreç, gnubg
**2-ply** rakibe karşı 2000 oyun (1000 çift):

| Ölçüm | Değer |
|---|---|
| Kazanma | 839/2000 = 0,4195 |
| **ppg** | **−0,2445** |
| ppg %95 GA | **[−0,3055; −0,1835]** |
| Eşleştirilmiş fark | −0,4890 [−0,5990; −0,3770] |
| Oyun başına ply | 55,9 |
| Süre | ~3 sa 20 dk |

`H0: ppg_fark ≤ −m`, m = 0,1115. GA'nın **üst** sınırı −0,1835 < −0,1115 →
**eşdeğerlik kanıtlanmadı**; model m'den fazla kötü. Güç borcu: m ve
σ = 2,9960 için gereken **4337** oyun, koşulan **2000** → **%46**.

**Tutarlılık kontrolü.** gnubg 0-ply, gnubg 2-ply'a karşı **−0,2229 ppg**;
modelimiz **−0,2445 ppg**. İki bağımsız ölçüm (ER merdiveni ve ppg) **aynı
yeri** gösteriyor. Bu, ölçüm zincirinin kendi kendini doğrulamasıdır.

### Madde 4 — Küp ayrı satır

R-D `large` küp ER'si **0,0821** (3 tohum, 400 vaka), hedef 0,02 → **4,1 kat**.
R-E'de hiçbir eşleştirilmiş bootstrap anlamlı değildi (p ≥ 0,32). **Hamle
kalitesi kazancı küp kararına transfer olmuyor.**

### Araç

`ml/gnubg_ladder.py` (`--deep`, `--deep-referee-plies`, `--deep-player-plies`,
`--deep-limit`, `--models-only`, `--model-er` virgüllü liste);
`ml/gnubg_rollout.py`; `ml/vs_gnubg.py` (başlık artık `--gnubg-plies`'i
yansıtır — eski sürüm "0-ply" yazısını sabit tutuyordu). Artefaktlar
`ml/artifacts/gnubg_ladder{,_deep,_deep4}.{json,md}`, `gnubg_rollout.{json,md}`,
`ppg_rd_large_s0_2ply.{json,md}`, `stage_r_f_report.{json,md}`. Test sayısı
**1497** (11 yeni: `test_gnubg_ladder.py` 322–327 + 332,
`test_gnubg_rollout.py` 328–331); §6 toplamı **1982**.

### Açık kalan

(a) `search1` politikadan kötü — değer kafası en zayıf yol. (b) Küp ER'si hiç
iyileşmedi. (c) ppg güç borcu %46. (d) 4-ply'ın kendi ER'si ölçülemedi.
(e) gnubg GPL lisansı ürün dağıtımı öncesi çözülmedi (§36.10/5). (f)
`m = 0,1115` yalnızca money; maç hücreleri (5 ve 9 puan) ayrı raporlanmadı.
## 42. R-F kabul testleri — R-T19…R-T22

**Karar.** R-F'nin kabul ölçütü "Test R-T19…R-T22 yeşil"dir. Dört test tek
dosyada, spec'teki adlarıyla tutulur: `ml/tests/test_stage_r_f.py` (8 test).
`test_gnubg_ladder.py` ve `test_gnubg_rollout.py` ilgili modüllerin birim
testleridir; rollout testlerinin docstring'i yanlışlıkla R-T20/R-T21/R-T22
etiketi taşıyordu, düzeltildi.

**R-T19 `Ladder_Measured`.** Her basamak ya ölçülmüş (n > 0, sonlu ortalama,
σ > 0, GA ortalamayı içerir, `exactMatchRate` ∈ [0,1]) ya da **gerekçesiyle**
ölçülemez (`mean`/GA `None`, `reason` dolu) olmalı. Ölçülen en küçük ER
çözünürlük tabanını verir: **0,0013**.

**R-T20 `Ladder_NoSelfReferee`.** Üç merdivenin (shallow, deep3, deep4) her
basamağında ölçülmüş satırlar için `playerPlies < refereePlies`; ölçülemez
satırlarda tersi ve gerekçe zorunlu.

**R-T21 `Equivalence_Test`.** `ml/ppg_measure.py`'ye `equivalence_verdict`
eklendi: `H0: ppg_fark ≤ −m` testini **doğru yönde** çalıştırır. GA'nın alt
sınırı `−m`'in üstündeyse `esdeger` (H0 reddedilir), üst sınırı `−m`'in
altındaysa `daha-kotu` (kötülük kanıtlandı), aksi hâlde
`esdegerlik-kanitlanmadi`. Üç etiket `EQUIVALENCE_LABELS`'ta sabit. Sentetik
vakalarla yön testi + kötü girdi reddi (marj ≤ 0, GA nokta tahminini
içermiyor). Ayrıca `required_games` (Acklam `_norm_ppf`, α = 0,05 tek yönlü,
güç = 0,80) eklendi: m = 0,1115, σ = 2,9960 → **4464**. Onaylanmış sayı
**4337**; %3 fark hiçbir hükmü değiştirmez, ikisi de raporlanır.

**R-T22 `Final_Report_ThreeLines`.** `stage_r_f_report.json` **tam olarak üç
satır** (`moveQuality`, `cube`, `gameStrength`) taşır; her satırda `budget`
(dolu metin) ve `elapsedSeconds` (pozitif tamsayı) zorunlu.
`elapsedSecondsTotal` satırların toplamı olmalı. Oyun gücü satırının
`verdictLabel`'i `equivalence_verdict` çağrısının sonucuyla **aynı** olmalı
(`daha-kotu`). Üst düzey `verdict` = `karşılanmadı`.

**Bütçe ve süre (R-T22 için eklendi).** Hamle kalitesi bütçesi "ER ≤ gnubg
2-ply seviyesi (taban 0,0013)", ~3 sa 25 dk; küp bütçesi "küp ER ≤ 0,02",
~20 dk; oyun gücü bütçesi "H0: ppg_fark ≤ −m, m = 0,1115, 4337 oyun",
~3 sa 20 dk. Toplam **25 500 s (~7 sa 5 dk)**.

**Test sayısı.** 1497 → **1505** (8 yeni: `test_stage_r_f.py`); §6 toplamı
1982 → **1990**. `test_docs_consistency.py`, `PHASES.md` §6,
`ARCHITECTURE.md` §51.5 ve `ml/artifacts/stage_d_report.md` güncellendi.
## 43. R-Q2 kapanışı — `hint` altı olasılığı zaten veriyor

**Bulgu.** R-Q2 "`hint` kübüsüz 6 olasılığı veriyor mu, yoksa yalnızca skaler
equity mi?" sorusu **kısmen** yanıtlanmıştı: `label-policy --dists` 6 sınıflı
dağılım üretiyor, ama bunu `eval` yolundan (`eval_afterstates(dists=True)`)
alıyor. `hint` yolunda ise `parse_hint` yalnızca `equity` ve `loss`
ayrıştırıyordu.

**Ölçülen çıktı (gnubg 1.08.003-mingw, 2-ply, canlı):**

```
    1. Cubeless 0-ply   bar/22                       Eq.: -0,164
       0,357 0,115 0,007 - 0,643 0,000 0,000
```

Yani `hint` **altı olasılığı da yazıyor**: `w wg wb - l lg lb`. Bunlar zaten
ödenen çıktının içinde; ayrıştırılmadıkları için atılıyordu. `w` gammon ve
backgammon'u **kapsar**, dolayısıyla `w + l == 1` (ölçülen: 0,357 + 0,643 =
1,000).

**Değişiklik.** `ml/gnubg_er.py`: `HintMove`'ya `probs: tuple[float, ...] |
None = None` ve `win`/`win_gammon`/`win_backgammon`/`lose`/`lose_gammon`/
`lose_backgammon` özellikleri eklendi; `_HINT_PROBS_RE` + `_probs_after`
`Eq.` satırının altındaki satırı okur. Olasılık satırı yoksa `probs = None`
(eski davranış bozulmaz).

**Neden önemli.** R-F'nin en önemli bulgusu "değer kafası en zayıf yol
(ER 0,0173) ve `search1` onu miras aldığı için politikadan kötü (0,0139 vs
0,0111)" idi. Değer kafasını 6 sınıflı dağılımla eğitmek için gereken
etiketler artık **`hint` yolundan ek maliyet olmadan** alınabiliyor; ER
koşularında `hint` zaten çağrılıyor. Bu, açık "değer kafası hedefi"
kararının maliyet tarafını sıfıra indirir.

**Testler.** 333–335 (`test_gnubg_er.py`): altı olasılık okunur; `w + l == 1`
ve alt kümeler tutarlı; olasılık satırı yoksa `None`. Test sayısı 1505 →
**1508**; §6 toplamı 1990 → **1993**.

**Sınır.** `hint` çıktısındaki olasılıklar **cubeless** ve **seçili ply**
içindir; küp kararı için kullanılamaz. `eval` yolundaki `dists=True` ile aynı
sayılar beklenir ama bu ayrı bir doğrulama ister (yapılmadı).

## 44. Faz 7-S2 — `medium` / `large` / `xlarge` çok tohumlu karşılaştırma (R-D tarifiyle)

**Neden.** §38 karşılaştırması **tek tohumla** koşuldu ve rapor bunu açık madde
bıraktı: "`large`−`medium` farkı (%7,3) tohum gürültüsünden büyük olduğu
**gösterilmedi**". R-E kuralı "tek tohum karar için yetmez" der.

**Önceki tarama geçersiz.** İlk denemede tarama `policy-temperature 0,0` ve
R-D etiketli olmayan `capacity30k` veri kümesiyle koşuldu. O koşuda
`medium`→`xlarge` için `value` p=0,0092 ve `search1` p=0,0114 "anlamlı"
çıkmıştı. Bu bir **tarif yanlılığıydı**: `xlarge` liste tabanlı KL kaybı
olmadan eğitilince politika kafası zayıf kalıyor, `search1` de onu miras
alıyordu. R-D tarifiyle (`policy-temperature 0,1` + `capacity30k_rd`) fark
kayboldu. v1 raporu bu nedenle geçersiz kılındı.

**Yöntem.** `ml/runs/capacity30k_rd/policy_30k_rd.npz` (30.006 pozisyon /
664.778 aday, gnubg 2-ply etiketli), 3 profil × 3 tohum, 5000 adım, batch 64,
lr 1e-3 cosine (son oran 0,1), wd 1e-4, patience 6, value 0,5 / dist 0,5 /
**rank 0,0**, **policy-temperature 0,1**. Ölçüm: gnubg 2-ply hakem, **300 vaka,
`--stride 3`** (contact 200 / bar 84 / race 16). `--limit` tek başına faz
yanlıdır; bunun için `capacity_train.py`'nin `run`/`sweep` alt komutlarına
`--stride` ve `--timeout` eklendi (testler 336–337).

**Yeniden üretilebilirlik.** Yeni taramanın `large/seed0`'ı mevcut R-D
`large/seed0` modeliyle **bit-bit aynı** (`valTop1` 0,8223925358213928;
politika ER 0,011117; değer ER 0,017263; search1 ER 0,013930). Bu, tarifin
doğru olduğunu ve mevcut ppg tabanının doğrudan karşılaştırılabilir olduğunu
kanıtlar.

**Sonuç (3 tohum ortalaması).**

| Profil | Parametre | Politika ER | Değer ER | search1 ER | `valTop1` |
|---|---|---|---|---|---|
| `medium` | 156.423 | 0,012740 ± 0,001084 | 0,019375 ± 0,001959 | 0,014395 ± 0,001039 | 0,8130 |
| `large` | 642.567 | 0,012511 ± 0,001246 | 0,018559 ± 0,001259 | 0,014373 ± 0,000751 | 0,8201 |
| `xlarge` | 1.805.319 | 0,012217 ± 0,001046 | 0,018153 ± 0,000344 | 0,013859 ± 0,000549 | 0,8259 |

Sıralama üç yolda da `medium` > `large` > `xlarge` (ER düşük = iyi) **ama
farklar tohum gürültüsünün içinde**: profiller arası fark %1–6, tohumlar arası
sd %8–15.

**Eşleşmiş bootstrap (10.000 yeniden örnekleme).** Dokuz karşılaştırmanın
(3 çift × 3 yol) **hiçbiri anlamlı değil**; en küçük p 0,1880
(`medium`→`large` değer). Doğru tarifle kapasite farkı **ölçülemiyor**.

**Karar gecikmesi** (C# `MatchBench decision-latency`, 30 pozisyon, CPU):

| Profil | depth 1 p95 | depth 2 p95 |
|---|---|---|
| `medium` | 0,0667 s | 8,4087 s |
| `large` | 0,2183 s | 11,5479 s |
| `xlarge` | 0,5746 s | 32,0165 s |

**Test 96 kararı.** İki bacak: (a) göreli değer-ER kazancı ≥ %15 **ve**
(b) depth 2 p95 ≤ 2,0 s. (a) `medium`→`large` −%4,2 / `medium`→`xlarge` −%6,3 →
**ikisi de düştü**. (b) `medium` (8,41 s) dahil **hiçbir profil geçmedi**.

**Kazanan yok; `medium` üretim varsayılanı kalır.** Bu, §38'in `winner: null`
sonucunu 3 tohumla **doğrular**. (b) bacağının hiçbir profilde sağlanmaması, o
bacağın kapasite değil **donanım/bütçe uyumsuzluğu** olduğunu gösterir: 2,0 s
sınırı bu makinede depth 2 için ulaşılamaz.

**Doğruluk kazananı `xlarge`.** Üç yolda da en düşük ER ve en yüksek
`valTop1`, ama hiçbir fark anlamlı değil. Yorum: "kapasite ölçeklemesi para
etmiyor" değil, "**30 bin pozisyonda** para etmiyor" — 30k pozisyon 1,8M
parametreyi doyurmuyor. Kapasiteyi büyütmenin önkoşulu veriyi büyütmektir.

**ppg için seçilen model.** `ml/runs/capacity30k_rd_sweep/xlarge/seed0/model.onnx`.
Seçim ölçütü **eğitim-zamanı** `valTop1` (0,8294 — dokuz modelin en yükseği),
yani ER sonuçları görülmeden uygulanabilen bir kural. Tohum bazında ER farkları
gürültü içinde; ER'a göre tohum seçmek seçim yanlılığı olurdu.

**Antisimetri.** Dokuz modelin hepsi −0,9502…−0,9436; eşik |corr| ≥ 0,99.
Kapasite bu kusuru **düzeltmiyor** — kusur mimaride.

**Artefaktlar.** `ml/artifacts/stage_large_xlarge_multiseed.json` / `.md`;
ppg koşusu bitince `ppg_xlarge_s0_2ply` artefaktı eklenecek.

**Testler.** 336–337 (`test_capacity_profiles.py`). Test sayısı 1508 → **1510**;
§6 toplamı 1993 → **1995**.

## 45. Faz 7-S3 — Mimari antisimetri, ayri kup agi, denetim noktalari ve EVREN hazirligi (F7-116 – F7-119)

**Neden.** §44 iki açık bıraktı: (1) renk takası kusuru dokuz modelin
**hepsinde** var ve kapasite büyütmek düzeltmiyor; (2) `xlarge` doğruluk
kazananı ama fark anlamsız, yani "30k pozisyon 1,8M parametreyi doyurmuyor".
Kullanıcı üç mimari direktif verdi: antisimetriyi **mimari kısıtla** çöz
(eğitim artırımı **değil**), küp kararlarını **ayrı ağla** öğren, ve her şeyi
**EVREN GPU** platformunda sürdürülebilir hâle getir — EVREN pahalı olduğu için
hazırlık hatasız olmalı.

### 45.1 Higgins ağırlık simetrisi (F7-116)

`T = flip_perspective` bir involusyondur (`T² = I`), bu yüzden 221 boyutlu giriş
uzayı iki dik alt uzaya ayrılır: `V−` (109) ve `V+` (112). `Q_minus [221,109]` /
`Q_plus [221,112]` sabit ortonormal tabanlar buffer olarak kayıtlı ve ONNX'e
gömülü.

- **Tek kol** `u = x @ Q_minus`: **bias'sız** doğrusal katmanlar + `tanh` →
  `h(Tx) = −h(x)` **tam**.
- **Çift kol** `s = x @ Q_plus`: serbest GELU MLP → `e(Tx) = e(x)`.
- **Kafalar bias'sız**; `probs = softmax(cat([a+b, a−b]))` (`a` çift, `b` tek) →
  `probs(Tx) = Π probs(x)`, equity `2b₀+4b₁+6b₂` **tam** tek.

`GELU`/`SiLU` tek kolda **kullanılamaz**: `g(z) − g(−z) == z` olduğu için kol
doğrusala çöker. `tanh` bu tuzağa düşmez ve TD-Gammon'un sigmoid ailesindendir.

**Doğrulama.** Tabanlar ortonormal 6e−8, çapraz dik 1,3e−8, tamlık 6e−8; flip
haritası `flip_perspective` ile fark **0,0**; değer/politika antisimetrisi
3,35e−8; olasılık permütasyonu 5,96e−8. `medium` simetrik **131.619**
parametre (düz V2 156.423, ~%16 azalma).

**Kapı ilk kez geçti.** 300 adımlık duman testi: `corr = −1.0000`,
`ER farkı = 0,0000 [0,0000; 0,0000]` → **GEÇTİ**. Dokuz düz model
−0,9502…−0,9436 aralığındaydı. Kusur gerçekten mimarideydi.

**Arayüz.** `build_model(..., symmetry=True)`; `capacity_train.py`
`run`/`sweep` → `--symmetry`. ONNX sözleşmesi V2 ile **aynı** (iki çıktı), yani
C# tarafında değişiklik gerekmez.

### 45.2 Ayrı küp ağı (F7-117)

F7-104 hamle kalitesinin küp kararına **transfer olmadığını** gösterdi; TD-Gammon
da küpü öğrenmedi. `ml/cube_net.py`:

- **Girdi**: 221'lik **pre-roll** vektör. Zar beklentisi ağın **içinde** öğrenilir;
  `EquityCubeAdvisor.DiceAveraged`'in (Faz 6 §10.2) 21-zar maliyeti ortadan kalkar.
- **Çıktı**: üç cubeful equity — `noDouble`, `doublePass`, `doubleTake`.
- **Antisimetri**: üç çıktı da equity olduğu için `f(Tx) = −f(x)` **tanım gereği**
  (`SymmetricBackbone` tek kol + bias'sız çıktı katmanı).
- **Karar**: `shouldDouble = min(doublePass, doubleTake) > noDouble`. **`min`**,
  çünkü rakip en kötü cevabı seçer; `doublePass` zaten `cubeValue`'a eşit olduğundan
  `min` ikisini birlikte temsil eder (`cube_er.double_value` ile aynı).
- **Etiket**: gnubg küp analizi; tahta × 4 maç bağlamı × 2 küp sahipliği = pozisyon
  başına 8 vaka, böylece maç-farkındalık öğrenilir.

**İlk gerçek koşu.** 1000 pozisyon → **8.000 vaka** etiketlendi (gnubg 2-ply,
8 işçi). Dağılım: 6.658 `no-double` / 1.342 `double`; kabul oranı 0,7811;
`noDouble` ortalaması 0,0424, `doubleTake` ortalaması −0,3781. Eğitim ve ölçüm
sonuçları `ml/runs/cube/` altında.

### 45.3 Denetim noktaları ve ppg sessiz ölümünün kök nedeni (F7-118)

**Kök neden.** İki ppg koşusu (175/2200 ve 575/2200 çiftte) sessizce öldü.
Sebep **PowerShell**'di: `$ErrorActionPreference = "Stop"` altında yerel bir
komutun **stderr** çıktısı sonlandırıcı hata sayılır. `vs_gnubg.py` ilerlemeyi
stderr'e yazar; boru hattı ilk ilerleme satırından hemen sonra öldü. Çözüm:
`"Continue"` + `& python @cliArgs *>> $log` (`Tee-Object` değil). **EVREN
hazırlığı için en önemli tek ders.**

**ppg denetim noktası.** JSONL, çift başına bir satır, her satırdan sonra
`flush()` + `os.fsync()`. Anahtar `{sürüm, model, path, gnubgPlies, seed,
maxPlies}`; uyuşmazsa **hata verir** (iki koşu sessizce karışmaz). Çiftler
sıradan bağımsız (`default_rng([seed, pair])`), yani devam **birebir** aynı
sonucu verir.

**Eğitim denetim noktası.** `train_policy_head(..., checkpoint, checkpoint_every,
resume)`: adım, ağırlıklar, Adam, scheduler, geçmiş, en iyi durum ve **torch RNG
durumu** kaydedilir; atomik yazım (`.tmp` + `os.replace`). `checkpoint_every = 0`
tamamen kapatır. `capacity_train.py` → `--checkpoint-every` / `--resume`.

### 45.4 EVREN ön kontrolü (F7-119)

`ml/preflight.py` hiçbir şey eğitmez; PASS/FAIL tablosu basar, FAIL'de çıkış
kodu 1. Kontroller: Python ≥ 3.10; paketler; torch CUDA derlemesi; GPU görünürlüğü;
**gerçek GPU matmul**; `onnxruntime` `CUDAExecutionProvider`; gnubg (**WARN**);
girdi dosyaları; ≥ 5 GB disk; yazma izni; ve **uçtan uca küçük sınama** (model kur →
ileri → antisimetri → ONNX yaz → ONNX Runtime paritesi). Sınama gerçek
`export_profile` yolunu kullanır, yani ihracat zincirindeki her değişiklik
ön kontrolde yakalanır.

**Yerel sonuç.** `sonuç: HAZIR` (GTX 1650 4 GB, torch 2.5.1+cu121). `onnxruntime`
CPU sürümü olduğu için `--gpu` ile `onnxruntime:gpu` FAIL olur; EVREN'de
`onnxruntime-gpu` kurulmalıdır. Kılavuz: `EVREN.md`.

**Testler.** 338–341 (ppg denetim noktası), 342–349 (mimari simetri), 350–351
(`--symmetry` aktarımı), 352–361 (küp ağı), 362–366 (eğitim denetim noktası),
367–372 (ön kontrol). Test sayısı 1510 → **1534**; §6 toplamı 1995 → **2019**.

## 46. Faz 7-S4 — Higgins çıktı izdüşümü: antisimetriyi ifade gücünü kaybetmeden çözmek

§45'te mimari antisimetri (`BackgammonNetV3`, `V-`/`V+` izdüşümleri) kuruldu ve
renk takası korelasyonu **ilk kez** tam olarak −1,0000 çıktı. Ancak aynı koşuda
doğruluk belirgin biçimde düştü. Bu bölüm o düşüşün nedenini ölçer ve doğru
kurulumu belirler.

### 46.1 Teşhis: darboğaz izdüşümün kendisi

`ml/runs/diag_sym.py` beş varyantı aynı reçeteyle (medium, 1500 adım, tohum 0,
R-D listesi) karşılaştırdı:

| Varyant | Parametre | valTop1 | valValueMse |
|---|---:|---:|---:|
| `plain` (V2) | 156 423 | **0,7827** | 0,01686 |
| `sym-qminus-ew32` | 131 619 | 0,6614 | 0,05851 |
| `sym-qminus-ew128` | 158 211 | 0,6668 | 0,05649 |
| `sym-full-ew32` | 160 291 | 0,7527 | 0,02737 |
| `sym-full-ew128` | 186 883 | 0,7468 | 0,02904 |

Çift kolu genişletmek (ew32 → ew128) **hiçbir şey kazandırmıyor**. Tek kolu
tam girdiye bağlamak 0,09 valTop1 geri getiriyor. Yani sorun bias'sızlık ya da
`tanh` değil, **`Q_minus` izdüşümünün kendisi**.

**Neden?** Tek kol `u = x @ Q_minus` (109 boyut) üzerinde çalışınca çift
özelliklerden (pip sayacı, temas bayrağı, maç skoru) **tamamen kopuyor**. Oysa
tek bir fonksiyonun bu özelliklere ihtiyacı var: örneğin `pip_farkı` çift bir
özelliktir ama `pip_farkı × temas` tek bir fonksiyon üretir. İzdüşüm bu
etkileşimi matematiksel olarak imkânsız kılıyor.

### 46.2 `odd_full`'un çürütülmesi (önemli, yanlış yol)

İlk çözüm denemesi tek kolu **tam 221 boyutlu** girdiye bağlamaktı (`odd_full`).
Gerekçe: bias'sız `Linear` + tek `tanh` zaten `f(-x) = -f(x)` verir. Bu
**matematiksel olarak yanlıştır** ve ölçümle çürütüldü:

```
net(x) + net(-x)  = 0.0        (doğru: negasyon altında tek)
net(x) + net(Tx)  = 1.0369     (yanlış: T altında tek DEĞİL)
```

`T = flip_perspective` bir **permütasyon/isaret** dönüşümüdür, negasyon değil
(`Tx ≠ -x`). `f(Tx) = -f(x)` yalnızca `T Q- = -Q-` sağlandığında, yani girdi
`V-`'ye izdüşürüldüğünde garanti edilir. `odd_full` bu yüzden kaldırıldı;
`test_375` artık bu tuzağı belgeliyor.

### 46.3 Doğru çözüm: `HigginsNet` (çıktı izdüşümü)

Higgins'in önerisi **ağırlık** simetrisi değil, **çıktı** simetrisidir: tek ağ,
iki bakıştan değerlendirilir ve sonuçlar birleştirilir. `ml/model.py` içindeki
`HigginsNet` bunu uygular. `T = flip_perspective`, `Π = (W L)(GW GL)(BW BL)`:

* Tek çıktılar: `g(x) = (f(x) − f(Tx)) / 2` → `g(Tx) = −g(x)`.
  Değer ve politika logit'i bu yolla üretilir.
* Çift çıktı: `L(x) = (l(x) + Π l(Tx)) / 2` → `L(Tx) = Π L(x)`,
  dolayısıyla `probs(Tx) = Π probs(x)`.

Her ikisi de **tanım gereği** tamdır; eğitim artırımı gerekmez. Maliyet iki
ileri geçiştir (kullanıcı değerlendirmesi: ONNX için ihmal edilebilir).

**Ölçüm (medium, 1500 adım, tohum 0, aynı reçete):**

| Varyant | Parametre | valTop1 | valValueMse | antisimetri |
|---|---:|---:|---:|---:|
| `plain` (V2) | 156 423 | 0,7827 | 0,01686 | — |
| `basis` (`V-` izdüşümü) | 131 619 | 0,6614 | 0,05851 | tam |
| `higgins` (çıktı izdüşümü) | 156 423 | **0,7791** | 0,02607 | **tam** |

`higgins` düz modelle **istatistiksel olarak aynı** doğrulukta (0,7791 vs
0,7827) ve antisimetrisi **tam** (logit artığı 0,0; `probs` permütasyon artığı
0,0). `basis`'e göre +0,118 valTop1.

`valValueMse`'nin 0,01686 → 0,02607 çıkması **beklenen ve istenen** bir
sonuçtur: hedefin çift bileşeni artık atılıyor. O bileşen zaten kusurun
kendisiydi.

**ONNX paritesi.** `HigginsNet` ihracı çalışıyor: `maxAbsDeltaValue = 8,94e-08`,
`maxAbsDeltaPolicyLogit = 4,47e-08`. C# tarafı değişmez (aynı iki çıktı, aynı
adlar).

### 46.4 Tam reçeteyle doğrulama (5000 adım, medium, tohum 0)

| Ölçüm | plain (V2) | asis | higgins |
|---|---:|---:|---:|
| valTop1 | 0,8157 | 0,7001 | 0,7994 |
| valValueMse | 0,01329 | — | 0,02299 |
| ER politika | 0,01188 | — | 0,01726 |
| ER değer | 0,01825 | — | 0,02678 |
| ER search1 | 0,01545 | — | **0,01523** |
| antisimetri `corr` | −0,9436 ❌ | −1,0000 ✅ | **−1,0000 ✅** |

`higgins` antisimetri kapısını **geçen tek yüksek doğruluklu** kurulumdur.
`plain` kapıyı düşürür (−0,9436); `basis` geçer ama valTop1'de 0,1156
kaybeder. `higgins` o kaybın 0,0993'ünü geri kazanır ve **üretim yolu olan
search1 ER'sinde düz modelden hafifçe iyidir** (0,01523 vs 0,01545).

Politika ve değer ER'lerinin bir miktar yükselmesi beklenen bir sonuçtur:
hedefin çift bileşeni atıldığı için 0-ply argmax daha az keskinleşir; buna
karşılık 1-ply arama bu kaybı telafi eder. Üretimde oynanan yol search1'dir.

### 46.5 Karar

* Üretim varsayılanı **`symmetry_mode = "higgins"`** olur; `basis` korunur
  (parametre tasarrufu isteyen senaryolar için) ama varsayılan değildir.
* `odd_full` **kaldırıldı** (yanlış matematik).
* `capacity_train.py` `run`/`sweep` artık `--symmetry-mode {basis,higgins}`
  sunar; `train_profile` ve `export_profile` bu seçeneği taşır.

Ayrıntılı tablo: `ml/artifacts/symmetry_modes.md`.

**Testler.** 375 (`T` altında teklik ≠ negasyon altında teklik), 376
(`HigginsNet` tam antisimetri), 377 (parametre sayısı düz V2 ile eşit),
378 (bilinmeyen `symmetry_mode` reddi), 379 (`--symmetry-mode` aktarımı). Test sayısı 1545 → **1552**; §6 toplamı
2030 → **2037**.
## 47. Faz 7-S5 — 100k koşusu öncesi ölçüm yolu ve etiketleme dayanıklılığı

100k veriyle xlarge tekrar denemesi (F7-117 karar ağacının "Hayır" dalı)
başlatılmadan önce ölçüm ve veri üretim yolundaki iki gerçek kusur kapatıldı.
Bunlar yeni özellik değil, ücretli GPU saatini ve saatlerce CPU emeğini koruyan
düzeltmelerdir.

### 47.1 Ölçüm alt süreçlerinde zaman aşımı (F7-121)

`capacity_train.py` içindeki `_run()` `subprocess.run`'ı **zaman aşımı
vermeden** çağırıyordu. Takılan tek bir gnubg çağrısı taramanın tamamını süre
boyunca kilitler. Artık `_run(cmd, *, quiet, timeout=None)`:

* `timeout` değerini `subprocess.run`'a geçirir,
* `subprocess.TimeoutExpired` yakalar, stderr'e `zaman aşımı (N s): <cmd>` yazar,
* **124** döndürür (POSIX `timeout(1)` geleneği).

`--measure-timeout` varsayılanı **3600** s; `0` sınırsız demektir. Bayrak
`run`, `measure` ve `sweep` alt komutlarında mevcuttur.

### 47.2 Antisimetri kapısı için ayrı örneklem (F7-121)

`measure_profile` antisimetri adımını ER adımıyla **aynı** `--stride`/`--limit`
ile çağırıyordu. Ölçülen maliyet gnubg 2-ply'da **vaka başına ~9,5 s**
(20 vaka, `--stride 10` → 190 s). `--stride 3 --limit 300` = 100 vaka =
**~16 dk/tohum**; 15 koşuluk tarama için ~4 saat, yani eğitimin kendisinden
pahalı. Bu, daha önce "takıldı" sanılan şeyin gerçek nedeniydi.

`measure_profile` artık `sym_limit`/`sym_stride` alır; `--sym-limit` ve
`--sym-stride` parserlara eklendi. Kapı için 12 vaka yeterlidir: `higgins` ve
`basis` bu örneklemde `corr = −1,0000` veriyor (F7-120), yani kapı zaten kesin
sonuçlu. **Eşik değiştirilmedi** (`CORR_MIN = 0,99`, `SUM_TOL = 0,001`);
kapıyı gevşetmek yanlış modelleri geçirirdi.

### 47.3 Etiketlemede dilim düzeyinde devam (F7-122)

`ml/runs/capacity100k_rd/run_label.ps1` yeniden yazıldı:

* **24 dilim × 4168 pozisyon** (100 032), 12'şerli **iki dalga**,
* var olan `shard_<k>.npz` **atlanır**,
* eksik dilim kalırsa betik **1** ile çıkar ve eksikleri `supervisor.log`'a yazar,
* birleştirme yalnızca tüm dilimler hazır olduğunda çalışır.

Dilim ayrıklığı doğrulandı: `_cmd_label_policy` her dilim için
`seed = args.seed + shard_index` ve `count = ceil(positions / shards)` kullanır.
Bir çöküşte kayıp en fazla bir dalga (~3 saat) olur; aynı komutu yeniden
çalıştırmak yeterlidir.

### 47.4 `EVREN.md` §9 düzeltmesi

§9.2'deki örnek komut **geçersiz** bir bayrak kullanıyordu:
`--profiles medium,large,xlarge`. `sweep` tek `--profile` alır
(`choices=[small,medium,large,xlarge]`) ve çıktı klasörü `--out-dir`'dir.
Bölüm üç ayrı `sweep` çağrısına (PowerShell döngüsü) çevrildi ve
`--sym-stride 10 --sym-limit 120 --measure-timeout 3600` eklendi. §9.1 de
24 dilimli, devam edebilir betiğe göre güncellendi.

### 47.5 100k aşaması sürücüsü (`ml/stage_100k.py`)

3–5. adımlar tek bir araçla yürütülür; karar kuralı koda gömülüdür:

```powershell
# 1) veri hazır mı
python ml\stage_100k.py check --data ml\runs\capacity100k_rd\policy_100k_rd.npz

# 2) tohum seç — YALNIZCA valTop1, ER'ye bakılmaz
python ml\stage_100k.py select `
  --sweep ml\runs\capacity100k_rd_sweep\xlarge\sweep.json `
  --out ml\runs\capacity100k_rd_sweep\selection.json

# 3) ppg kararı + rapor
python ml\stage_100k.py report `
  --ppg ml\artifacts\ppg_xlarge_100k_s0_2ply.json `
  --baseline ml\artifacts\ppg_rd_large_s0_2ply.json `
  --selection ml\runs\capacity100k_rd_sweep\selection.json `
  --out-json ml\artifacts\ppg_xlarge_100k.json `
  --out-md ml\artifacts\stage_100k_report.md
```

`check` pozisyon sayısını `offsets` uzunluğundan alır; `x` **aday** dizisidir.
Aday sayısını pozisyon sayısı sanmak eşik kontrolünü sessizce yanlış yapar
(30k veride 664 778 vs 30 006). `select` eşitlikte küçük tohumu seçer, böylece
seçim deterministiktir. `report` `equivalence_verdict`'i doğrudan çağırır;
marj `0.1115` varsayılandır ve test 404 ile sabitlenmiştir.

**Testler.** 380 (`run` `measure_timeout`/`sym_limit`/`sym_stride` aktarır),
381 (varsayılanlar 3600,0 / None / None; `0` sınırsız), 382 (`_run`
`TimeoutExpired` üzerine 124 döner), 383–388 (tohum seçimi: en yüksek
`valTop1`, ER alanları yok sayılır, eşitlikte küçük tohum, boş/eksik sweep
reddi), 389–396 (karar: üç etiket, pozitif olmayan marj reddi, eksik GA reddi,
taban karşılaştırması, Markdown içeriği), 397–400 (veri doğrulama: `offsets`
sayımı, eksik dizi, kısa sayı, dosya yok), 401–404 (CLI: `select`, `report`,
`check` çıkış kodu, sabit marj). Test sayısı 1552 → **1592**; §6 toplamı
2037 → **2077**.
## 48. 100k etiketleme tamamlandı ve `dist` sütunu kurtarıldı (F7-126)

### 48.1 Etiketleme sonucu

24 dilim x 4 168 pozisyon, iki dalga x 12 süreç. Başlangıç 09:29:53, dalga 1
bitiş 14:27:11, dalga 2 bitiş 18:58:16, birleştirme 18:58:42. Toplam **9 sa 29 dk**.

| Ölçü | Değer |
|---|---|
| Pozisyon | **100 030** |
| Aday | 2 239 253 (ort. 22,39, en çok 581) |
| `hasDist` | **true** (`distMissing` 4 168, %4,2) |
| `hasCandEquity` | true |
| Maskelenen aday oranı | 0,6305 |
| Equity ortalama / std | 0,2252 / 0,6025 |
| Dilim başına süre | ~16 000 s (4,4 s/pozisyon) |

### 48.2 Bulunan veri kaybı

İlk birleştirme `hasDist: false` verdi. `shard_22`'de **tek** pozisyonun
dağılım etiketi alınamamış; `build_policy_dataset` bu yüzden o dilimde sütunu
hiç yazmamış; `concat_policy_datasets` de `all(...)` istediği için **100 030
pozisyonun tamamı** dağılım hedefini kaybetmiş. Ayrıntı: F7-126.

Düzeltme sonrası yeniden birleştirme (yeniden etiketleme yok): `hasDist: true`,
`distMissing: 4 168`. `stage_100k.py check` → `ready: true`.

### 48.3 Eğitim tarifi (koşudan önce sabit)

| Alan | Değer | Gerekçe |
|---|---|---|
| Adım | **15 000** | 30k'da 5 000 adım = 10,7 epoch; 100k'da aynı epoch için 15 000 (F7-124) |
| Tohum | 0, 1, 2 | hesaplama bütçesi; seçim yalnızca `valTop1` |
| Batch / lr | 64 / 1e-3, cosine, final 0,1 | R-D tarifi |
| Kayıplar | value 0,5 · dist 0,5 · policy T 0,1 | R-D tarifi |
| Mimari | `--symmetry --symmetry-mode higgins` | F7-118 |
| Ölçüm | `--stride 3 --limit 300`, antisimetri `--stride 10 --limit 120` | F7-121 |
| Karar | m = 0,1115, üç dal | F7-117 |

### 48.4 Karar kuralı (değişmedi)

`equivalence_verdict(ppg, ci_low, ci_high, 0.1115)`:
`ci_low > -0,1115` → `esdeger`; `ci_high < -0,1115` → `daha-kotu`; aksi
`esdegerlik-kanitlanmadi`. Tohum seçimi ER'ye bakmadan yapılır.

### 48.5 Testler

`test_239` yeni sözleşmeye göre yeniden yazıldı; 405–408 eklendi (doldurma,
düşürme, NaN maskeleme, kayıpsız gidiş-dönüş). Toplam 1577 → **1592**;
§6 toplamı 2062 → **2077**.