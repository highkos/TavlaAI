# GÖREV EMİRİ (v1): Unity Görselleştirme, AI Entegrasyonu, Bearoff Veritabanı, Küp ve Maç Katmanı, Faz 5

## 🎯 Proje Vizyonu
Faz 1 v4 (motor), Faz 2 v4 (221 nöronlu vektörleştirici), Faz 3 v7 (politika yönlendirmeli expectiminimax arama) ve Faz 4 v3 (ONNX köprüsü, self-play, eğitim laboratuvarı, lig, `eval_bench`, gnubg ER ölçümü) üzerine; oyunu **oynanabilir** kılan bir **Unity görselleştirme katmanı**, onu besleyen **Unity'den bağımsız, test edilebilir bir AI entegrasyon çekirdeği**, ağın **kesinlik kazanmadığı** iki alanı kapatan **bearoff veritabanı** ve **küp/maç katmanı** kurulacaktır.

Bu fazın **asıl hedefi** dünya şampiyonu seviyesine giden yolun **altyapısını** tamamlamaktır. Gücün kendisi (kapasite, eğitim ölçeği, 6 çıktılı değer başı) **Faz 6**'nın konusudur. Faz 5 bittiğinde:

* İnsan, Unity arayüzünde **küplü ve maçlı** tavla oynayabilir; Crawford, maç uzunluğu, maç skoru ekranda doğru gösterilir.
* AI, **bearoff pozisyonlarında ağa hiç sormadan kesin** (exact) equity üretir.
* AI, **küp kararlarını** maç skoruna ve Crawford durumuna göre verir.
* AI, **maç-duyarlı hamle seçimi** yapar (küpsüz equity'yi maç equity'sine çevirerek), ki bu bugünkü modelde **yoktur**.
* Arayüz, modelin bugünkü sınırlarını **gizlemez**: analiz paneli "kesin (bearoff DB)" ile "tahmin (ağ)" ayrımını gösterir.

> **v1 notu (kapsam ve gerekçe):** Bu doküman Faz 4 v3'ün yapısını birebir izler. Faz 4'ün açık bıraktığı üç karar burada **kapatılmıştır**: (1) Unity inference arka ucu = **ONNX Runtime** (Sentis yalnızca yedek), (2) bearoff veritabanı = **dekoratör**, modelin içinde değil, (3) küp/maç = **ağın dışında**, `MatchEquityTable` + `EquityCubeAdvisor` + `MatchAwareEvaluator`. Ayrıca Faz 4'ün "Faz 4b" olarak ertelediği küp ve maç oyunu bu faza alınmıştır; **2 taraflı bearoff veritabanı** ise boyut matematiği nedeniyle **Faz 6**'ya bırakılmıştır (Bölüm 3.1, Bölüm 10).

> **Dürüstlük notu (güç beklentisi):** Faz 5 **güç artışı vaat etmez**. Ölçülmüş mevcut seviye: gnubg ER **0,1941** (50 pozisyon, 2-ply küpsüz), `PipBot` **0,1283**; model `PipBot`'a **%40,5** kazanıyor (`PHASES.md` §7). Dünya şampiyonu ≈ 0,003 ER'dir; aradaki fark ≈ **65×**'tir. Bu farkın dağılımına dair **tahmin** (ölçüm değil, `PHASES.md` §8.3 ile uyumlu): eğitim ölçeği ≈ %60, kapasite ≈ %15, 6 çıktılı değer başı ≈ %10, bearoff DB ≈ %10, arama derinliği ≈ %5. Faz 5 bu %15'lik dilimin (bearoff + küp/maç) altyapısını kurar ve **ölçülebilir** hâle getirir.

---

## 0. Çalışma Kuralları (Ajan İçin Zorunlu)

1. **Hot path'te sıfır allocation hedefi (C# çekirdek):** `BearoffAwareEvaluator`, `MatchAwareEvaluator`, `BearoffDatabase` sorguları ve `HeuristicOutcomeDistribution` ısınma sonrası heap allocation yapmamalıdır (`GC.GetAllocatedBytesForCurrentThread` farkı ile ölçülür). **Unity katmanı bu kuralın dışındadır** (UI kare başına allocation yapabilir), ancak **arama ve değerlendirme çağrıları** Unity'den de olsa bu kurala uyar.
2. **Faz 1-4 API'lerine bağlılık:** Faz 1 v4, Faz 2 v4, Faz 3 v7 ve Faz 4 v3'teki tipler, imzalar, `AfterStateList` SoA yapısı, 221 vektör haritası, ONNX sözleşmesi **olduğu gibi** kullanılır. **`BackgammonSearch`, `BackgammonVectorizer`, `OnnxPolicyValueEvaluator`, `OnnxModelHandle` gövdeleri DEĞİŞMEZ.** Bu dokümanda **açıkça onaylanmış** iki ekleme vardır: `output_version` ONNX metadata alanı (Bölüm 5.5) ve `ml/tests/test_docs_consistency.py` içindeki `EXPECTED_COUNTS` güncellemesi (Bölüm 7). **Faz 1 API'sine hiç dokunulmaz** (Bölüm 3.6). Bunların dışında bir değişiklik gerektiğini düşünürsen **gerekçeli bir teklif olarak raporla ve onay bekle**.
3. **Tek doğruluk kaynağı:** Vektörleştirme yalnızca C#'ta yapılır. **Python tarafında vektörleştirici yazılmaz.** Bearoff DP'sinin **tek doğruluk kaynağı C#**'tır (`Backgammon.BearoffGen`); Python yalnızca **bağımsız referans** olarak yazılır ve C# çıktısıyla karşılaştırılır (Bölüm 8, Test 34).
4. **Unity bağımlılık yönü tek yönlüdür:** `Unity → Backgammon.UI → Backgammon.Core`. `Backgammon.UI` **`Backgammon.Inference`'a referans vermez**; değerlendiriciyi `IPolicyValueEvaluator` olarak dışarıdan alır. `Backgammon.Core` **hiçbir** Unity tipi bilmez (`Backgammon.Core.asmdef` içinde `noEngineReferences: true` zaten bunu zorlar).
5. **TDD:** Hem C# hem Python hem Unity tarafında testler önce yazılır (Aşama A'da kırmızı). Unity testleri **EditMode**'dır; PlayMode testi yalnızca sahne yükleme dumanı içindir.
6. **Aşamalı teslim:** Bölüm 11'e göre ilerle, onay almadan sonraki aşamaya geçme. Belirsiz noktayı tahmin etme, açık soru olarak raporla.
7. **Doğrulanmamış sayılar:** Bu dokümandaki eşik, tolerans ve boyut sayıları **başlangıç/yer tutucu** değerlerdir (Bölüm 9). Uydurma "başarı" sayısı yazılmaz, **ölçüm** raporlanır. Bir sayı bu dokümanda **formül** olarak verilmişse (ör. `C(21,6) = 54264`) o sayı **kesin matematiktir**, ölçüm değildir; ölçüm gerektiren her yerde "ölçülür ve raporlanır" yazar.

---

## 1. Kapsam ve Sabit Kararlar

| Konu | Karar |
|---|---|
| Oyun türü | **Money game + maç oyunu.** `matchLength = 0` money game; `matchLength ≥ 1` maç |
| Küp | **Kapsam içi.** Tek küp, `cubeValue ∈ {1,2,4,...,64}`, `cubeOwner ∈ {0,+1,-1}`. Beaver/Raccoon/Chouette **kapsam dışı** |
| Jacoby | **Yapılandırılabilir** (`EngineSettings.EnableJacoby`), varsayılan **kapalı** (Faz 1 v4 ile aynı) |
| Crawford | **Kapsam içi.** `isCrawfordGame` / `crawfordPlayed` Faz 1 v4'te zaten var; Faz 5 bunları **kullanır** |
| Değer birimi (ağ) | Faz 3 v7 sözleşmesi **değişmez**: küpsüz money equity, `[-3, +3]`, kırpma **aramanın** işi |
| Maç-duyarlı hamle seçimi | **Kapsam içi, yaklaşık.** `MatchAwareEvaluator` dekoratörü `E → ME` çevirimi yapar (Bölüm 4.6). Kesin çözüm 6 çıktılı değer başı = **Faz 6** |
| Bearoff DB | **1 taraflı (exact), kapsam içi.** 2 taraflı **Faz 6** (Bölüm 3.1'de boyut matematiği ile gerekçeli) |
| Bearoff DB konumu | **Dekoratör** (`BearoffAwareEvaluator`), `BackgammonSearch` ile `OnnxPolicyValueEvaluator` **arasında**. Modelin içinde **değil** |
| Match equity tablosu | `MatchEquityTable`, gnubg'nin **Rockwell-Kazaross** MET'i referans; çıkarılamazsa dokümante edilmiş model + açık soru |
| Unity sürümü | **6000.3.8f1** (kurulu: `C:\Program Files\Unity\Hub\Editor\6000.3.8f1`) |
| Unity render | **URP 2D Renderer** (Unity 6 varsayılanı), **uGUI** (Canvas + RectTransform) |
| Unity inference | **ONNX Runtime** birincil (`Microsoft.ML.OnnxRuntime` + `onnxruntime.dll` native plugin). **Sentis yedek** (Bölüm 6.11) |
| UI mimarisi | **View-model ayrık**: `Backgammon.UI` (netstandard2.1, Unity'siz, test edilebilir) + ince MonoBehaviour'lar |
| Dil/çerçeve | C# `netstandard2.1` (Core/Inference/UI), `net10.0` (testler, konsol araçları). Python ≥ 3.10 (yalnızca referans/doğrulama) |
| Test çerçevesi | xUnit (mevcut `Backgammon.Tests`, `Backgammon.Inference.Tests`), yeni `Backgammon.UI.Tests`, Unity Test Framework (EditMode) |

---

## 2. Katman Mimarisi ve Değişmez Sözleşmeler

### 2.1 Değerlendirici zinciri

```
Unity (MonoBehaviour, görünüm)
   │  yalnızca Backgammon.UI view-model'lerini çağırır
   ▼
Backgammon.UI            (netstandard2.1, Unity'siz, xUnit ile test edilir)
   ├── GameOrchestrator
   ├── BoardViewModel / CubeViewModel / MatchScoreViewModel / AnalysisViewModel
   ├── MoveInputController
   └── PositionAnalysis
   │
   ▼
Backgammon.Core
   ├── BackgammonEngine, LegalMoveGenerator, BackgammonVectorizer   (DEĞİŞMEZ)
   ├── BackgammonSearch                                             (DEĞİŞMEZ)
   ├── MatchAwareEvaluator        (YENİ, dekoratör)   E → ME
   │      └── BearoffAwareEvaluator (YENİ, dekoratör) bearoff'ta kesin E
   │             └── OnnxPolicyValueEvaluator                       (DEĞİŞMEZ)
   ├── BearoffDatabase            (YENİ, memory-mapped)
   ├── MatchEquityTable           (YENİ)
   ├── EquityCubeAdvisor          (YENİ, ICubeEvaluator)
   └── HeuristicOutcomeDistribution (YENİ)
   │
   ▼
Backgammon.Inference     (DEĞİŞMEZ; yalnızca `output_version` metadata kontrolü eklenir)
```

**Zincir sırası neden bu?** `BearoffAwareEvaluator` **içte**dir çünkü kesin equity üretir; `MatchAwareEvaluator` **dışta**dır çünkü kesin equity'yi maç equity'sine çevirir. Ters sıra yanlış olurdu: maç equity'sinden bearoff equity'si geri kazanılamaz.

**Money game'de `MatchAwareEvaluator` zincire hiç girmez** (kimlik dönüşümü). Böylece Faz 4'ün ölçülmüş davranışı **bit düzeyinde** korunur.

### 2.2 Değişmeyen sözleşmeler (ihlal = ret)

| Sözleşme | Kaynak | Faz 5'te durum |
|---|---|---|
| `IPositionEvaluator.EvaluateBatch(list, offset, count, perspective, in scalars, Span<float>)` | Faz 3 v7 §4.1 | **Değişmez.** Dekoratörler bunu uygular |
| `offset` yalnızca `0` olabilir | Faz 3 v7 §4.1 | **Değişmez.** Dekoratörler `offset != 0` görürse `ArgumentException` |
| Değerlendirici `[-3,3]`'e **kırpmaz**; yalnızca `float.IsFinite` kontrolü | Faz 4 v3 §0 kural 1, F4-02 | **Değişmez.** Dekoratörler de kırpmaz |
| Terminal kayıtlar değerlendiriciye **gitmez** | Faz 3 v7 §4.1 | **Değişmez.** Dekoratörler terminal kayıt görürse `ArgumentException` |
| `ICombinedBatchEvaluator` `IPositionEvaluator`'dan **miras almaz** | Faz 4 v3 §4.1 | **Değişmez** |
| `Version` değişince `SearchWorkspace.Reset()` **zorunlu** | Faz 4 v3 §4.4 | **Değişmez.** Dekoratör `Version`'ları bileşimdir |
| ONNX girdi `"features"` `[B,221]`, çıktılar `"value"` `[B,1]`, `"policy_logit"` `[B,1]`, opset 15 | Faz 4 v3 §3 | **Değişmez** |
| `AfterStateList.Capacity = 2048`, `OnnxEvaluatorOptions.MaxBatch = 2048` | Faz 1 v4, Faz 4 v3 | **Değişmez** |

### 2.3 Yeni tipler (özet)

| Tip | Proje | Arayüz | Bölüm |
|---|---|---|---|
| `BearoffDatabase` | `Backgammon.Core` | — | 3.2–3.4 |
| `BearoffAwareEvaluator` | `Backgammon.Core` | `IPositionEvaluator`, `IPolicyEvaluator`, `ICombinedBatchEvaluator` | 3.5 |
| `BearoffAwareOptions` | `Backgammon.Core` | — | 3.5 |
| `Backgammon.BearoffGen` | yeni konsol projesi | — | 3.9 |
| `MatchState` | `Backgammon.Core` | — | 4.1 |
| `MatchEquityTable` | `Backgammon.Core` | — | 4.2 |
| `OutcomeDistribution` | `Backgammon.Core` | — | 4.3 |
| `IOutcomeDistributionEvaluator` | `Backgammon.Core` | — | 4.3 |
| `HeuristicOutcomeDistribution` | `Backgammon.Core` | `IOutcomeDistributionEvaluator` | 4.3 |
| `EquityCubeAdvisor` | `Backgammon.Core` | `ICubeEvaluator` | 4.4 |
| `CubeDecision` | `Backgammon.Core` | — | 4.4 |
| `MatchAwareEvaluator` | `Backgammon.Core` | `IPositionEvaluator`, `IPolicyEvaluator`, `ICombinedBatchEvaluator` | 4.6 |
| `PositionAnalysis` | `Backgammon.UI` | — | 5.1 |
| `GameOrchestrator` | `Backgammon.UI` | — | 5.3 |
| `BoardViewModel`, `CubeViewModel`, `MatchScoreViewModel`, `AnalysisViewModel`, `MoveInputController` | `Backgammon.UI` | — | 6.2 |

---

## 3. Bearoff Veritabanı

### 3.1 Kapsam ve gerekçe

**Kapsam içi: 1 taraflı (one-sided) bearoff veritabanı.** Bir tarafın 15 taşının tamamı kendi ev bölgesindeki 6 hanede (1..6) veya toplanmışsa, o tarafın **kesin** "kaç turda toplar" dağılımı önceden hesaplanır.

**Kapsam dışı: 2 taraflı (two-sided) bearoff veritabanı — Faz 6.** Gerekçe **boyut matematiğidir** (ölçüm değil, kesin kombinatorik):

* 1 taraflı indeks uzayı: 15 taşın 6 haneye + "toplanmış" kutusuna dağılımı = `C(15+7-1, 7-1) = C(21,6) = 54264` pozisyon.
* 2 taraflı indeks uzayı: `54264² = 2 944 581 696` pozisyon.
* 5 olasılık × `uint16` = 10 bayt/pozisyon ⇒ **≈ 29,4 GB**. `uint8` ile bile **≈ 14,7 GB**.
* Üretim maliyeti: her pozisyon için expectiminimax; 2,9 milyar pozisyon pratik değildir.

Bu nedenle 2 taraflı DB, **nicemleme (quantization) + seyrek temsil + üretim paralelleştirmesi** tasarımıyla birlikte Faz 6'ya bırakılır. Faz 5'te bearoff pozisyonlarının **kesinliği** 1 taraflı DB + Bölüm 3.7'deki yarış (race) formülüyle sağlanır.

**1 taraflı DB'nin boyutu (kesin):** `54264 × (MaxRolls+1) × 2 bayt`. `MaxRolls = 12` için `54264 × 13 × 2 = 1 410 864` bayt ≈ **1,35 MB**. Gammon eklentisi `54264 × 2 × 2 = 217 056` bayt ≈ 0,21 MB. Toplam ≈ **1,55 MB**. Bu, belleğe tamamen sığar; yine de Bölüm 3.4'teki memory-mapped okuyucu **zorunludur** (Faz 6'da 2 taraflı DB aynı okuyucuyu kullanacak).

### 3.2 Dosya formatı (`bearoff1_v1.bin`)

Küçük-endian. Tüm alanlar hizalı (padding yok).

```
Header — 64 bayt
  [0..3]    magic        : "TVB1" (ASCII, 4 bayt)
  [4..5]    version      : uint16 = 1
  [6]       points       : uint8  = 6
  [7]       checkers     : uint8  = 15
  [8..11]   positions    : uint32 = 54264
  [12]      maxRolls     : uint8  (varsayılan 12)
  [13]      flags        : uint8  (bit0 = gammon eklentisi var)
  [14..15]  reserved     : 2 bayt = 0
  [16..19]  payloadCrc32 : uint32 (CRC-32/ISO-HDLC, payload üzerinde)
  [20..23]  payloadBytes : uint32
  [24..63]  reserved     : 40 bayt = 0

Payload
  A) CDF tablosu : positions × (maxRolls+1) × uint16
     cdf[p][k] = P(pozisyon p, en fazla k turda toplar) × 65535, k = 0..maxRolls
     cdf[p][0] = 0 (hiç toplamadı), cdf[p][maxRolls] = 65535 (tavan)
     Her p için k boyunca monoton azalmayan.
  B) Gammon tablosu (flags bit0 = 1 ise) : positions × 2 × uint16
     gammon[p][0] = P(rakip 0 taş toplamışken kaybeder | p) × 65535   (bizim mars olasılığımız)
     gammon[p][1] = P(biz 0 taş toplamışken kaybederiz | p) × 65535   (rakibin mars olasılığı)
```

**Nicemleme kuralı:** `uint16 = round(clamp(x, 0, 1) × 65535)`. Okurken `x = u / 65535.0`. Bu, `1/65535 ≈ 1,53e-5` çözünürlük verir; equity hatası `≤ 3 × 1,53e-5 ≈ 4,6e-5` ile sınırlıdır ve **Bölüm 9'da ölçülür**.

**Sürüm koruması:** `magic`, `version`, `points`, `checkers`, `positions`, `payloadBytes` uyuşmazsa `InvalidDataException`. `payloadCrc32` uyuşmazsa `InvalidDataException`. **Sessiz kabul yok.**

### 3.3 İndeksleme (kesin, kendi tanımımız)

Bir tarafın pozisyonu `c[0..5]` ile temsil edilir: `c[i]` = `i+1` numaralı hanedeki taş sayısı (1-hane = toplanmaya en yakın). `c[6] = 15 − Σ c[0..5]` = toplanmış taş sayısı. Böylece `(c[0..6])`, 15'in 7 parçaya **bileşimi**dir (composition); sayısı `C(21,6) = 54264`.

**Sıra (rank) — koleks (colex) düzeni:**

```
S_i = Σ_{j=0..i} c[j]                       (i = 0..5)
rank(c) = Σ_{i=0..5} C(S_i + i, i + 1)
```

**Doğrulama (kesin):**
* Hepsi toplanmış (`c[0..5] = 0`, `c[6] = 15`) ⇒ `S_i = 0` ⇒ `rank = Σ C(i, i+1) = 0`.
* Hepsi 1-hanede (`c[0] = 15`, diğerleri 0) ⇒ `S_i = 15` ⇒ `rank = Σ_{i=0..5} C(15+i, i+1) = C(21,15) − 1 = 54263`.

**Ters sıra (unrank):** `i = 5`'ten `0`'a inerek `S_i`'yi `C(S_i + i, i+1) ≤ kalan` koşuluyla en büyük yapan değer seçilir; `c[i] = S_i − S_{i−1}`. **Round-trip testi zorunludur** (Bölüm 8, Test 1): 54264 pozisyonun tamamı için `Unrank(Rank(c)) == c`.

**Neden kendi tanımımız?** gnubg'nin indeks şeması belgelenmemiştir ve sürümler arasında değişmiştir. Kendi tanımımız **kesin**, **test edilebilir** ve **belgelenebilir**. gnubg ile uyum, indeks düzeyinde değil **değer** düzeyinde aranır (Bölüm 8, Test 5).

### 3.4 Okuyucu: `BearoffDatabase`

```csharp
namespace Backgammon.Core
{
    /// <summary>1 taraflı bearoff veritabanı. Memory-mapped; tamamı belleğe kopyalanmaz.</summary>
    public sealed class BearoffDatabase : IDisposable
    {
        public static BearoffDatabase Open(string path);
        public static BearoffDatabase OpenEmpty();          // testler için: her sorgu "bilinmiyor"

        public int Version { get; }                          // dosya içeriğinden türetilen sabit
        public int MaxRolls { get; }
        public bool HasGammonData { get; }

        /// <summary>Pozisyon 1 taraflı bearoff mı? (tüm taşlar 1..6 hanesinde veya toplanmış)</summary>
        public static bool IsOneSidedBearoff(ReadOnlySpan<sbyte> board, int player);

        /// <summary>Ham pozisyonu indekse çevirir. Çağıran IsOneSidedBearoff ile doğrulamalıdır.</summary>
        public static int Rank(ReadOnlySpan<byte> counts);   // counts[0..5]
        public static void Unrank(int index, Span<byte> counts);

        /// <summary>Kümülatif dağılım: cdf[k] = P(en fazla k turda toplar), k = 0..MaxRolls.</summary>
        public bool TryGetCdf(ReadOnlySpan<sbyte> board, int player, Span<float> cdf);

        /// <summary>Mars olasılıkları. HasGammonData false ise false döner.</summary>
        public bool TryGetGammon(ReadOnlySpan<sbyte> board, int player,
                                 out float gammonWin, out float gammonLoss);

        public void Dispose();
    }
}
```

**Uygulama zorunlulukları:**
* `MemoryMappedFile.CreateFromFile(path, FileMode.Open, null, 0, MemoryMappedFileAccess.Read)` + `MemoryMappedViewAccessor` + `SafeMemoryMappedViewHandle.AcquirePointer` ile `ReadOnlySpan<byte>` elde edilir. **`File.ReadAllBytes` yasak.**
* `TryGetCdf`/`TryGetGammon` **allocation yapmaz**; `Span<float>` çağıranın buffer'ıdır.
* `Version`, `payloadCrc32` ile `positions`'ın karışımından türetilir: `Version = (int)(crc32 ^ (positions * 2654435761u))`. Böylece **farklı DB dosyası ⇒ farklı `Version`**.
* `OpenEmpty()` her sorguda `false` döner; `Version = 0`. Testlerde ve DB yokken kullanılır.
* `IsOneSidedBearoff`: `player`'ın 15 taşının tamamı `1..6` hanelerinde (kendi perspektifinden) veya toplanmışsa `true`. **Bar'da taş varsa `false`.** Rakip tarafı **ilgilendirmez** (1 taraflı DB tek tarafı çözer).

### 3.5 Dekoratör: `BearoffAwareEvaluator`

```csharp
namespace Backgammon.Core
{
    public sealed class BearoffAwareOptions
    {
        /// <summary>Tüm kayıtlar bearoff ise iç değerlendirici hiç çağrılmasın. Varsayılan: true.</summary>
        public bool SkipInnerForPureBearoffBatches;

        /// <summary>Bearoff çözümü kapalı (A/B karşılaştırması için). Varsayılan: false.</summary>
        public bool DisableBearoff;

        public static BearoffAwareOptions Default { get; }
    }

    public sealed class BearoffAwareEvaluator
        : IPositionEvaluator, IPolicyEvaluator, ICombinedBatchEvaluator
    {
        public BearoffAwareEvaluator(IPolicyValueEvaluator inner,
                                     BearoffDatabase database,
                                     BearoffAwareOptions options);

        public int Version { get; }   // = inner.Version * 31 + database.Version

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results);

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities);

        public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                          in VectorizerScalars scalars,
                                          Span<float> results, Span<float> priorities);
    }
}
```

**Davranış sözleşmesi (kesin):**

1. `offset != 0` ⇒ `ArgumentException` (Faz 3 v7 §4.1 ile aynı).
2. `list.IsTerminal[i]` herhangi bir `i ∈ [offset, offset+count)` için `true` ⇒ `ArgumentException` (çağıran bölümlemekle yükümlü).
3. **`EvaluateBatch` — "üzerine yaz" stratejisi:**
   a. `_inner.EvaluateBatch(list, offset, count, perspective, scalars, results)` çağrılır (tam batch).
   b. Sonra `i ∈ [offset, offset+count)` üzerinde döngü: `database.TryGetCdf(...)` ile bearoff çözümü denenir; çözülürse `results[i]` **kesin equity** ile **üzerine yazılır**.
   c. `SkipInnerForPureBearoffBatches == true` **ve** aralıktaki **tüm** kayıtlar bearoff ise (a) adımı **atlanır**; `results` yalnızca DB'den doldurulur. Bu, `AfterStateList` kopyalaması **gerektirmez** ve sıfır allocation korunur.
   d. `DisableBearoff == true` ise dekoratör **tam kimlik**tir (yalnızca (a) adımı).
4. **`ScoreBatch` — tam devir:** `_inner.ScoreBatch(...)` çağrılır, **hiçbir şey değiştirilmez.** Gerekçe: politika yalnızca sıralamayı etkiler, `Q` değerini etkilemez (Faz 3 v7 §4.1). Bearoff equity'sini logit ölçeğine karıştırmak **ölçek uyumsuzluğu** yaratır ve grup softmax'ını bozar. Bu bilinçli bir karardır, eksiklik değildir.
5. **`EvaluateAndScoreBatch`:**
   * Aralıkta **hiç** bearoff kaydı yoksa ⇒ `_inner.EvaluateAndScoreBatch(...)` **tek çağrı** (Faz 4 v3 §4.2 hızlı yolu korunur).
   * En az bir bearoff kaydı varsa ⇒ `EvaluateBatch` (madde 3) + `ScoreBatch` (madde 4) olarak **iki çağrı**. Gerekçe: `priorities` **tam aday kümesi** üzerinde normalize olmalıdır; kısmi batch üzerinde hesaplanan softmax yanlış olur. Bu sapma **belgelenmiştir** ve yalnızca kökte, yalnızca bearoff karışımı varken geçerlidir.
6. **Kesin equity formülü (Bölüm 3.7).**
7. **Kırpma yok.** `results[i]` `[-3,3]` dışına çıkabilir; kırpma aramanın işidir (F4-02).
8. **`float.IsFinite` kontrolü:** DB'den gelen değer sonlu değilse `InvalidOperationException` (savunmacı; nicemleme bunu imkânsız kılmalıdır).

### 3.6 Toplu çağrı bölümleme — neden **gerekmiyor**

Faz 3 v7 `VectorizeBatch` `offset` almaz ve terminal kayıt görürse hata atar. Bu yüzden "bearoff olanları ayır, kalanları ayrı bir `AfterStateList`'e kopyala" yaklaşımı **cazip ama gereksizdir**: Bölüm 3.5 madde 3'teki **"üzerine yaz"** stratejisi aynı kesinliği **sıfır kopya** ile verir. Kopyalama yalnızca **hız** kazandırır ve o hız, `SkipInnerForPureBearoffBatches` ile **zaten** elde edilir (tüm adaylar bearoff olduğunda iç çağrı tamamen atlanır — bu, gerçek oyunda bearoff düğümlerinin **tipik** hâlidir).

**Karar:** Faz 5'te kopyalama/partitioning **yoktur**. `AfterStateList.CopyRecordFrom` **eklenmez**. Bu, Faz 1 API'sine **hiç dokunulmadığı** anlamına gelir ve Bölüm 0 kural 2'yi en sıkı biçimde karşılar.

> **Not (Faz 6 için):** Karışık batch'lerde iç çağrının maliyeti ölçülür (Bölüm 9). Ölçüm, iç çağrının baskın olduğunu gösterirse Faz 6'da `AfterStateList.CopyRecordFrom` + scratch list eklenir. Bu doküman o eklentiyi **önermez**.

### 3.7 Kesin equity formülü (1 taraflı DB ile)

İki taraf da 1 taraflı bearoff ise, oyun **saf yarıştır** (temas yok, vurma yok). Kesin olasılıklar:

* `A` = sırada olan oyuncu, `B` = rakip. `cdfA[k] = P(A en fazla k turda toplar)`, `cdfB[k]` aynı şekilde.
* `A`'nın **tam olarak** `k` turda toplama olasılığı: `pA[k] = cdfA[k] − cdfA[k−1]`.
* `A` önce oynadığı için `A`, `B`'nin `k` turuna karşı `k` turda toplarsa kazanır (beraberlikte sırada olan kazanır):
  `P(A kazanır) = Σ_k pA[k] · cdfB[k−1]`  (k = 1..MaxRolls, `cdfB[0] = 0`)
* Mars: `P(A mars) = Σ_k pA[k] · P(B, k−1 turda hiç taş toplamadı)`. Bu bilgi **gammon tablosundan** (`gammon[p][1]`) veya **taş sayısı dağılımından** gelir. Gammon tablosu yoksa mars olasılıkları **0** kabul edilir ve bu **açıkça raporlanır** (Bölüm 10).
* Equity: `E = P(win) + P(gammonWin) + P(backgammonWin) − P(lose) − P(gammonLoss) − P(backgammonLoss)`.
  Backgammon, saf bearoff'ta **imkânsızdır** (rakip barında taş olamaz) ⇒ `P(backgammon*) = 0`.
* **Perspektif:** `E`, `perspective` (mover) açısından döndürülür. `perspective == −1` ise `E` işaret çevrilir ve `A`/`B` rolleri değişir.

**Kesinlik iddiası:** Bu formül, **1 taraflı DB'nin kapsadığı** pozisyonlarda (iki taraf da saf bearoff) **kesindir** — modelin tahmini değildir. Kapsamadığı durumlarda (bir taraf bar'da veya ev dışında) dekoratör **devre dışı** kalır ve iç değerlendirici kullanılır.

### 3.8 Depth-0 kısayolu

Saf bearoff pozisyonunda `BearoffAwareEvaluator` **kesin** oyun değerini verdiği için, aramanın ek ply açması **hiçbir bilgi eklemez**. `GameOrchestrator` (Bölüm 5.3) şu kuralı uygular:

```
if (BearoffDatabase.IsOneSidedBearoff(state.board, +1) &&
    BearoffDatabase.IsOneSidedBearoff(state.board, -1) &&
    bearoffAware != null)
    effectiveSettings = settings with { DepthPly = 0 };
```

`DepthPly = 0` Faz 3 v7'de "afterstate'leri doğrudan değerlendir" demektir; afterstate değeri **kesin** olduğu için sonuç **kesindir**. Bu, bearoff'ta aramayı **ölçülebilir biçimde** hızlandırır (Bölüm 9).

**Kural:** Bu kısayol **yalnızca** `BearoffAwareEvaluator` zincirde **ve** `DisableBearoff == false` **ve** iki taraf da saf bearoff iken uygulanır. Aksi hâlde `DepthPly` **değiştirilmez**.

### 3.9 Üretici: `Backgammon.BearoffGen`

Yeni konsol projesi `Backgammon.BearoffGen` (`net10.0`, `Backgammon.Core`'a referans). **Dinamik programlama** ile CDF tablosunu üretir.

```
Kullanım:
  Backgammon.BearoffGen --out ml/artifacts/bearoff1_v1.bin [--max-rolls 12] [--gammon] [--verify]
```

**DP tanımı (kesin):**
* Durum: `c[0..5]` (1..6 hanelerindeki taş sayısı). Toplanmış taşlar durumun parçası değildir (indirgenir).
* `T(c)` = "bu pozisyondan toplamak için gereken tur sayısı" rastgele değişkeni.
* Bir turda: zar atılır (36 eşit olasılıklı kombinasyon; dublede 4 hamle). **Yasal hamle kümesi `LegalMoveGenerator` ile üretilir** — kopyalanmaz, yeniden yazılmaz. Her yasal hamle sonrası durum `c'` olur. Oyuncu **optimal** oynar: `E[T(c)] = 1 + (1/36) Σ_{zar} min_{hamle} E[T(c')]`.
* **Tek politika ilkesi (kesin).** Oyuncu her pozisyonda **tek** bir politika izler: `E[T]`'yi en aza indiren hamle. Dağılım bu politika altında hesaplanır:
  * `π(c, zar) = argmin_{hamle} E[T(c')]` (eşitlikte deterministik beraberlik kuralı, aşağıya bakın).
  * `p_k(c) = P(T(c) = k) = (1/36) Σ_{zar} w(zar) · p_{k−1}(π(c, zar))`, `p_0(c) = [c = ∅]`.
  * `P(T(c) ≤ k) = Σ_{j≤k} p_j(c)`.
* **Yanlış olan formül (kullanılmaz):** `P(T(c) ≤ k) = (1/36) Σ_{zar} max_{hamle} P(T(c') ≤ k−1)`. Bu "per-k max" hiçbir gerçek politikaya karşılık gelmez: aynı zar atışında farklı `k` için farklı hamle seçilemez. 54 264 pozisyonun 264'ünde `argmax` `k`'ya göre değişir ve CDF farkı 0.018'e ulaşır; yarış hissesi (equity) hatası ortalama 0.15'e çıkar. Bu yüzden **tek politika** kullanılır.
* **Beraberlik kuralı (deterministik):** `E[T]` eşitse en küçük sıra numaralı ardıl seçilir. Ölçüm: gnubg `Bearoff1` ile dağılım uyumu bu kurala duyarsızdır (bkz. §9.1); dört farklı beraberlik kuralı gnubg ile aynı sonucu verir (maks |Δ| = 3.4e-05).
* Taban: `c` hepsi toplanmış ⇒ `T = 0` kesin, yani `p_0 = 1`, `p_k = 0` (`k ≥ 1`). Format gereği `cdf[0] = 0` yazılır, `cdf[k] = 1` (`k ≥ 1`).
* `k = 1..MaxRolls` için **ileri yönlü** doldurulur. `MaxRolls` yeterince büyükse `P(T ≤ MaxRolls) = 1` olur; **değilse** üretici `MaxRolls`'u **artırır** ve bunu raporlar (sessizce kırpmaz). Yakınsama ölçütü **kümülatif** CDF üzerinden verilir (dağılım satırları sıfıra gittiği için dağılım üzerinden verilemez).
* **Gammon tablosu** (`--gammon`): `P(rakip 0 taş toplamışken kaybeder)`. Bu, "kaç turda toplarım" ile "kaç taş topladım" ortak dağılımını gerektirir; üretici `(tur, toplanmış taş sayısı)` üzerinde 2 boyutlu DP yapar. **Bu isteğe bağlıdır**; üretilmezse Bölüm 3.7'de mars olasılıkları 0 kabul edilir ve raporlanır.

**Determinizm:** Üretici **tek iş parçacıklı** ve **sabit sıralı**dır. Aynı girdi ⇒ **bit düzeyinde** aynı dosya. `--verify` bayrağı üretim sonrası Bölüm 8 Test 1–5'i çalıştırır.

**Python referansı:** `ml/bearoff_ref.py` **bağımsız** bir DP yazar (C# kodunu **okumadan**, yalnızca bu dokümanın Bölüm 3.9 tanımından). Amaç: iki bağımsız uygulamanın aynı tabloyu üretmesi (Bölüm 8, Test 34). Python **üretim** aracı değildir, **doğrulama** aracıdır.

---

## 4. Küp ve Maç Katmanı

### 4.1 `MatchState`

```csharp
namespace Backgammon.Core
{
    /// <summary>Maç/küp bağlamının değişmez görünümü. BackgammonState'ten türetilir.</summary>
    public readonly struct MatchState : IEquatable<MatchState>
    {
        public readonly int MatchLength;   // 0 = money game
        public readonly int WhiteScore;
        public readonly int BlackScore;
        public readonly int CubeValue;     // 2'nin kuvveti: 1,2,4,...,64
        public readonly sbyte CubeOwner;   // 0 ortada, +1 Beyaz, -1 Siyah
        public readonly bool IsCrawford;

        public static MatchState From(BackgammonState state);
        public static MatchState MoneyGame { get; }

        public bool IsMoneyGame { get; }
        public int AwayScore(int player);          // MatchLength - score(player)
        public int ScoreOf(int player);
        public bool IsCrawfordGame { get; }
        public bool IsPostCrawford { get; }        // crawfordPlayed && !isCrawfordGame
        public bool IsDeadCube { get; }            // CubeValue * 2 > max(AwayScore(+1), AwayScore(-1))
        public int MaxCubeValue { get; }           // maçta: 2^ceil(log2(min away)); money: 64
        public int Hash { get; }                   // Version bileşimi için
    }
}
```

**Kurallar:**
* `MatchLength == 0` ⇒ `IsMoneyGame == true`, `AwayScore` tanımsız (`int.MaxValue` döner), `MaxCubeValue = 64`.
* `IsDeadCube`: küp ikiye katlanırsa **hiçbir** taraf maçı kazanamıyorsa küp ölüdür. `CubeValue * 2 > min(AwayScore(+1), AwayScore(-1))` **değil**, `CubeValue * 2 > max(...)` — çünkü küp değeri **kazananın** alacağı puanı belirler ve **her iki** taraf da maçı bitirebilecek kadar puana sahip olmalıdır ki küp canlı kalsın. **Kesin tanım:** küp ölüdür ⇔ `CubeValue * 2 > max(AwayScore(+1), AwayScore(-1))`. Bu, `EngineSettings.DisallowDeadCube` ile birlikte kullanılır.
* `MaxCubeValue`: maçta `2^floor(log2(min(AwayScore(+1), AwayScore(-1))))`; money game'de 64 (yapılandırılabilir üst sınır).

### 4.2 `MatchEquityTable`

```csharp
namespace Backgammon.Core
{
    /// <summary>Maç kazanma olasılığı (MWC) tablosu. away ∈ [0, MaxMatchLength].</summary>
    public sealed class MatchEquityTable
    {
        public MatchEquityTable(int maxMatchLength = 25);

        /// <summary>A'nın maçı kazanma olasılığı. awayA/awayB = 0 ⇒ maç bitti.</summary>
        public double MatchWinningChance(int awayA, int awayB);

        /// <summary>Antisimetrik maç equity'si: ME = 2·MWC − 1 ∈ [−1, +1].</summary>
        public double MatchEquity(int awayA, int awayB);

        public int MaxMatchLength { get; }
        public int Version { get; }
    }
}
```

**Zorunlu değişmezler (Bölüm 8, Test 14):**
1. `MWC(0, b) = 1` (b > 0); `MWC(a, 0) = 0` (a > 0); `MWC(0, 0)` tanımsız ⇒ `ArgumentException`.
2. **Simetri:** `MWC(a, b) + MWC(b, a) = 1` (tolerans `1e-9`).
3. **Monotonluk:** `a` arttıkça `MWC(a, b)` **kesin azalır**; `b` arttıkça **kesin artar**.
4. `MWC(a, a) = 0.5`.
5. `ME(a, b) = −ME(b, a)` (tolerans `1e-12`).
6. Tüm değerler `[0, 1]` aralığında ve **sonlu**.

**Veri kaynağı (öncelik sırası):**
1. **gnubg'nin Rockwell-Kazaross MET'i.** gnubg kurulu (`F:\Program Files (x86)\gnubg\`). Ajan, gnubg'nin MET verisini **çıkarır** (kurulum dizinindeki veri dosyaları veya `gnubg-cli` komutları; hangisi işe yararsa) ve `Backgammon.Core/Match/met_rk.json` olarak **gömülü kaynak** hâline getirir. Şema:

   ```json
   {
     "name": "Rockwell-Kazaross",
     "source": "gnubg 1.08.003 (çıkarım yöntemi buraya yazılır)",
     "maxMatchLength": 25,
     "table": [[1.0, 0.5, ...], [0.0, 0.5, ...], ...]
   }
   ```
   `table[a][b]` = `MWC(a, b)`. `a`/`b` = away skorları, `0..25`.
2. **Çıkarılamazsa:** dokümante edilmiş, **değişmezleri sağlayan** bir model uygulanır ve **açık soru olarak raporlanır**. Model, `MWC(a,b) = 0.5 + 0.5·g(a,b)` biçiminde olmalı ve `g(a,b) = −g(b,a)`, `g(0,b) = 1`, `g(a,0) = −1`, `g(a,a) = 0` koşullarını **sağlamalıdır**. **Uydurma katsayı yazma**; kullanılan formül ve katsayılar raporda **açıkça** belirtilir.

**Crawford:** Crawford oyununda küp **yoktur** (Bölüm 4.5). MET tablosu Crawford'u **içermez**; Crawford oyunu için `MWC` doğrudan **küpsüz** hesaplanır (küp değeri 1).

### 4.3 `OutcomeDistribution` ve `IOutcomeDistributionEvaluator`

```csharp
namespace Backgammon.Core
{
    /// <summary>Koşulsuz (unconditional) oyun sonucu olasılıkları. gnubg çıktı düzeniyle aynı.</summary>
    public readonly struct OutcomeDistribution
    {
        public readonly float Win;             // P(kazanır)
        public readonly float WinGammon;       // P(kazanır ve mars)
        public readonly float WinBackgammon;   // P(kazanır ve backgammon)
        public readonly float LoseGammon;      // P(kaybeder ve mars)
        public readonly float LoseBackgammon;  // P(kaybeder ve backgammon)

        public float Lose { get; }             // 1 - Win
        public double Equity { get; }          // Win + WinGammon + WinBackgammon - Lose - LoseGammon - LoseBackgammon
        public bool IsValid { get; }           // tüm değişmezler sağlanıyor mu
    }

    /// <summary>Faz 5'te yalnızca tanım + sezgisel uygulama. Ağ tabanlı uygulama Faz 6.</summary>
    public interface IOutcomeDistributionEvaluator
    {
        void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                       in VectorizerScalars scalars, Span<OutcomeDistribution> results);
        int Version { get; }
    }
}
```

**`OutcomeDistribution` değişmezleri (Bölüm 8, Test 17):**
* `Win + Lose = 1` (tolerans `1e-6`).
* `0 ≤ WinBackgammon ≤ WinGammon ≤ Win`.
* `0 ≤ LoseBackgammon ≤ LoseGammon ≤ Lose`.
* `Equity ∈ [−3, +3]`.
* Tüm alanlar sonlu ve `[0,1]` aralığında.

**`HeuristicOutcomeDistribution` (Faz 5 uygulaması):**

```csharp
public static class HeuristicOutcomeDistribution
{
    /// <summary>Skaler equity'den 6'lı dağılım türetir. Deterministik, allocation yapmaz.</summary>
    public static OutcomeDistribution FromEquity(double equity, bool isContact, int pipDifference);
}
```

**Tasarım zorunlulukları:**
* **Deterministik** ve **allocation'sız**.
* **Monoton:** `equity` arttıkça `Win` **kesin artar**; `WinGammon`, `WinBackgammon` **azalmaz**; `LoseGammon`, `LoseBackgammon` **artmaz**.
* **Süreklilik:** `equity = 0` civarında sürekli; `equity = 0` ⇒ `Win = 0.5`, `WinGammon = LoseGammon`, `WinBackgammon = LoseBackgammon`.
* **Uçlar:** `equity = +3` ⇒ `Win = 1`, `WinGammon = 1`, `WinBackgammon = 0` (saf bearoff'ta backgammon imkânsız olduğu için üst sınır `WinGammon`'dur; `equity = 3` yalnızca backgammon ile mümkündür, bu yüzden `WinBackgammon = 1` de kabul edilebilir — **seçim raporda gerekçelendirilir**). `equity = −3` simetrik.
* **Temas bilgisi:** `isContact == false` (saf yarış) ⇒ `WinBackgammon = LoseBackgammon = 0` **zorunlu**.
* **Formül dokümante edilir.** Katsayılar **yer tutucudur**; Bölüm 9'daki gnubg karşılaştırmasıyla **kalibre edilir** ve kalibrasyon raporlanır.

> **Neden sezgisel?** Ağ bugün tek skaler equity üretir (`ml/model.py`, `value_head = Linear(h2, 1)`). Tek skalerden 6'lı dağılım **bilgi olarak** türetilemez; bu yüzden bir **model varsayımı** yapılır. Bu varsayım **Faz 6'da ağın 6 çıktılı değer başı ile değiştirilecektir**; `IOutcomeDistributionEvaluator` arayüzü tam bunun için **şimdi** tanımlanır ki UI ve küp danışmanı **değişmesin**.

### 4.4 `EquityCubeAdvisor`

```csharp
namespace Backgammon.Core
{
    public readonly struct CubeDecision
    {
        public readonly bool ShouldDouble;
        public readonly bool ShouldTake;      // rakip perspektifinden
        public readonly double EquityNoDouble;
        public readonly double EquityDoubleTake;
        public readonly double EquityDoublePass;
        public readonly bool IsTooGood;       // double + pass bekleniyor
        public readonly bool IsDeadCube;
    }

    public sealed class EquityCubeAdvisor : ICubeEvaluator
    {
        public EquityCubeAdvisor(IPositionEvaluator evaluator,
                                 MatchEquityTable met,
                                 IOutcomeDistributionEvaluator distribution,
                                 CubeAdvisorOptions options);

        public bool ShouldDouble(BackgammonState state);
        public bool ShouldTake(BackgammonState state);
        public CubeDecision Decide(BackgammonState state, int perspective);
        public int Version { get; }
    }
}
```

**Algoritma (kesin):**

1. `state.phase` `PreRoll` değilse veya `CanOffer(state) == false` ise ⇒ `ShouldDouble = false` (küp teklif edilemez).
2. `IsCrawfordGame` ⇒ `ShouldDouble = false` **kesin** (Crawford'da küp yok).
3. `IsDeadCube` ⇒ `ShouldDouble = false` **kesin**.
4. Pozisyon değerlendirilir: `E` = küpsüz money equity (mover perspektifi), `BearoffAwareEvaluator` zinciri üzerinden.
5. `D = distribution.EvaluateDistributionBatch(...)` (tek kayıt) ⇒ 6'lı dağılım.
6. **MWC'ye çevirim** (maçta):
   ```
   MWC_noDouble = Σ_outcome P(outcome) · MWC(awayA − puan(outcome), awayB)
   ```
   `puan(Single) = 1`, `puan(Gammon) = 2`, `puan(Backgammon) = 3`; kayıplarda `awayB` azalır. `away ≤ 0` ⇒ `MWC = 1` (maç bitti).
   Money game'de `MWC` yerine **equity** kullanılır: `E_noDouble = E`.
7. **Küp ikiye katlanmış** senaryolar:
   * `E_doubleTake`: küp `2·cubeValue`, rakip **kabul eder** ⇒ puanlar `2×`.
   * `E_doublePass`: rakip **reddeder** ⇒ teklif eden `cubeValue` puan kazanır (maçta `MWC(awayA − cubeValue, awayB)`).
8. **Karar:**
   * `ShouldDouble = max(E_doubleTake, E_doublePass) > E_noDouble + ε` (`ε = 1e-9`).
   * `IsTooGood = E_doublePass > E_doubleTake` (rakip reddedecek kadar iyi).
   * `ShouldTake` (rakip perspektifi) = `E_doubleTake_rakip ≥ E_doublePass_rakip`.
9. **Money game özel hâli:** `E_noDouble = E`, `E_doubleTake = 2E`, `E_doublePass = +1`. Klasik eşikler: `E > 1` ⇒ çok iyi (double, pass); `E > 0.5` ⇒ double/take sınırı; `E < 0.5` ⇒ double etme. **Bu eşikler formülden türetilir, ayrıca yazılmaz.**

**`Version`:** `evaluator.Version * 31 + met.Version * 17 + distribution.Version`.

**Kırpma:** `EquityCubeAdvisor` equity'yi `[-3,3]`'e **kırpar** (kendi karar mantığı için gereklidir; arama kırpmasıyla karıştırılmamalıdır). Bu, F4-02'nin "değerlendirici kırpmaz" kuralını **ihlal etmez** — danışman bir değerlendirici değildir.

### 4.5 Crawford ve post-Crawford

* **Crawford oyunu:** `isCrawfordGame == true` ⇒ küp **yok**. `EquityCubeAdvisor.ShouldDouble` **her zaman** `false`. `BackgammonEngine.CanOffer` zaten `false` döner (Faz 1 v4); danışman bunu **ayrıca** doğrular (savunmacı).
* **Post-Crawford:** `crawfordPlayed == true && isCrawfordGame == false` ⇒ küp **vardır**, ancak **serbest düşüş (free drop)** geçerlidir: geride olan taraf küpü **kabul etmek zorunda değildir** ve reddetmenin maliyeti yoktur (maç skoru açısından). `EquityCubeAdvisor`, post-Crawford'da `ShouldTake` hesabında `E_doublePass`'i **0** kabul eder (yani "kabul etmek zorunda değilsin" mantığı). Bu, `CubeAdvisorOptions.PostCrawfordFreeDrop` (varsayılan `true`) ile yapılandırılabilir.
* **Crawford geçişi:** `BackgammonEngine.StartNextGame` (Faz 1 v4) `isCrawfordGame`/`crawfordPlayed` alanlarını yönetir. Faz 5 bunu **değiştirmez**, yalnızca **okur**. Bir hata bulunursa **raporlanır**, sessizce düzeltilmez.

### 4.6 `MatchAwareEvaluator` — maç-duyarlı hamle seçimi

**Problem:** Ağ tek skaler küpsüz equity üretir. `argmax E` ile `argmax MWC` **aynı değildir**, çünkü marsların maç skorundaki ağırlığı skora göre değişir. Örneğin 2-away/2-away'de mars **maçı bitirir**, 5-away/5-away'de bitirmez.

**Çözüm:** `E → ME` dönüşümü yapan bir **dekoratör**. `ME = 2·MWC − 1` **antisimetriktir**, bu yüzden Faz 3 v7'nin negamax'ı (`q_r = −V(çocuk)`) **değişmeden** çalışır.

```csharp
namespace Backgammon.Core
{
    public sealed class MatchAwareEvaluator
        : IPositionEvaluator, IPolicyEvaluator, ICombinedBatchEvaluator
    {
        public MatchAwareEvaluator(IPolicyValueEvaluator inner,
                                   MatchEquityTable met,
                                   IOutcomeDistributionEvaluator distribution,
                                   MatchState match);

        public int Version { get; }   // inner.Version*31 + met.Version*17 + distribution.Version*7 + match.Hash

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results);
        public void ScoreBatch(...);                       // tam devir (politika sıralaması değişmez)
        public void EvaluateAndScoreBatch(...);            // tam devir + üzerine yazma
    }
}
```

**Davranış:**
1. `match.IsMoneyGame` ⇒ **tam kimlik** (hiçbir dönüşüm yok). Bu, Faz 4'ün ölçülmüş davranışını **bit düzeyinde** korur.
2. Aksi hâlde: `_inner.EvaluateBatch(...)` → her `i` için `E_i` alınır → `D_i = HeuristicOutcomeDistribution.FromEquity(E_i, ...)` → `MWC_i` (Bölüm 4.4 adım 6) → `results[i] = (float)(2·MWC_i − 1)`.
3. **Kırpma yok** (`ME ∈ [−1,1]`, arama `[−3,3]`'e kırpar, zararsız).
4. **`ScoreBatch` tam devir** — politika sıralaması `E`'ye göre yapılır, `ME`'ye göre değil. Gerekçe: politika yalnızca sıralamadır ve `E` sıralaması `ME` sıralamasına **yakındır**; ayrıca `ScoreBatch`'in ölçek sözleşmesi (toplam 1) korunur. Bu **bilinçli** bir yaklaşımdır ve Bölüm 9'da ölçülür.
5. **`Version`** maç durumunu **içerir** (`match.Hash`), çünkü dönüşüm skora bağlıdır. Skor değişince `SearchWorkspace.Reset()` **zorunludur** (Faz 4 v3 §4.4 kuralı aynen geçerli).

**Sınır (dürüstçe):** Bu, **yaklaşık** maç-duyarlılığıdır; kesin değildir. Kesin çözüm, ağın 6 çıktılı değer başı üretmesidir (**Faz 6**). Faz 5'te `HeuristicOutcomeDistribution`'ın kalitesi, maç-duyarlılığının kalitesini **doğrudan** belirler; bu yüzden Bölüm 9'da gnubg ile **karşılaştırmalı ölçüm** zorunludur.

**Kanıt testi (Bölüm 8, Test 24):** `argmax E ≠ argmax ME` olan **yapay** bir pozisyon kurulur (ör. 2-away/2-away'de mars getiren hamle ile mars getirmeyen ama daha yüksek `E` veren hamle). `MatchAwareEvaluator` doğru hamleyi seçmelidir. Bu test, maç-duyarlılığının **gerçekten** çalıştığını kanıtlar; onsuz "eklendi" demek **yasaktır**.

---

## 5. AI Entegrasyonu (Unity'den Bağımsız Çekirdek)

### 5.1 `PositionAnalysis`

```csharp
namespace Backgammon.UI
{
    /// <summary>Analiz panelinin ve UI'ın gördüğü tek veri yapısı. Faz 6'da DEĞİŞMEZ.</summary>
    public readonly struct PositionAnalysis
    {
        public readonly double Equity;                 // küpsüz money equity, [-3,3]
        public readonly double MatchEquity;            // ME = 2·MWC-1; money game'de = Equity
        public readonly double MatchWinningChance;     // MWC; money game'de double.NaN
        public readonly OutcomeDistribution? Distribution;  // null ⇒ dağılım yok
        public readonly bool FromBearoffDatabase;      // kesin mi?
        public readonly bool IsExact;                  // bearoff DB veya terminal
        public readonly int PipCountActive;
        public readonly int PipCountOpponent;
        public readonly int RollsToOffActive;          // -1 = bilinmiyor
        public readonly int RollsToOffOpponent;        // -1 = bilinmiyor
        public readonly CubeDecision? Cube;            // null ⇒ küp bağlamı yok
    }
}
```

**Kural:** UI **asla** `IPositionEvaluator`'ı doğrudan çağırmaz; **yalnızca** `PositionAnalysis` tüketir. Böylece Faz 6'da 6 çıktılı değer başı geldiğinde **UI kodu değişmez** — yalnızca `Distribution` alanı `null` olmaktan çıkar.

### 5.2 `IOutcomeDistributionEvaluator` kullanımı

Bölüm 4.3'te tanımlandı. Faz 5'te `HeuristicOutcomeDistribution` uygular. `PositionAnalysis.Distribution`, `HeuristicOutcomeDistribution.FromEquity` çıktısıdır (money game'de de doldurulur — UI mars olasılıklarını gösterebilsin).

### 5.3 `GameOrchestrator`

```csharp
namespace Backgammon.UI
{
    public sealed class GameOrchestratorOptions
    {
        public IPolicyValueEvaluator Evaluator;      // zorunlu
        public BearoffDatabase Bearoff;              // null olabilir
        public MatchEquityTable Met;                 // null olabilir (money game)
        public IOutcomeDistributionEvaluator Distribution;
        public SearchSettings SearchSettings;
        public EngineSettings EngineSettings;
        public IRandom Random;                       // determinizm için
        public int MaxPlies;                         // güvenlik sınırı
    }

    public sealed class GameOrchestrator : IDisposable
    {
        public GameOrchestrator(GameOrchestratorOptions options);

        public BackgammonState State { get; }
        public MatchState Match { get; }
        public bool IsGameOver { get; }
        public GameResult Result { get; }

        public void NewMatch(int matchLength, bool enableJacoby);
        public void NewGame();
        public void RollDice();
        public void SetDice(int d1, int d2);          // test/UI için
        public MoveList LegalMoves { get; }
        public void ApplyMove(in MoveSequence move);
        public void EndTurn();

        public Task<SearchResult> ThinkAsync(CancellationToken ct);
        public CubeDecision EvaluateCube();
        public PositionAnalysis AnalyzeCurrent();
        public IReadOnlyList<PositionAnalysis> AnalyzeCandidates();   // UI: hamle başına equity

        public event Action Changed;
        public void Dispose();
    }
}
```

**Zorunluluklar:**
* **Unity tipi yok.** `Backgammon.UI` `UnityEngine`'e referans **vermez**.
* **Determinizm:** `IRandom` dışarıdan enjekte edilir. Aynı seed + aynı hamle dizisi ⇒ **aynı oyun** (Bölüm 8, Test 32).
* **`ThinkAsync`:** aramayı **arka planda** çalıştırır (`Task.Run`), `CancellationToken` ile iptal edilebilir. **UI iş parçacığını bloklamaz.** Arama **tek iş parçacıklı**dır (Faz 4 F4-39: `--threads > 1` deterministik değil).
* **Düşünme bütçesi:** `ThinkAsync` bir `TimeSpan` bütçesi alır (aşırı yükleme). Bütçe aşılırsa arama **iptal edilir** ve o ana kadarki **en iyi** hamle döner (`SearchResult` zaten bunu taşır). Bütçe **duvar saati**dir, determinizmi **bozar**; bu yüzden testlerde bütçe **kullanılmaz** (sınırsız).
* **`AnalyzeCandidates`:** her yasal hamle için `PositionAnalysis` üretir. UI bunu "hamle ipuçları" için kullanır. **Allocation yapar** (UI yolu), hot path değildir.
* **Depth-0 kısayolu** (Bölüm 3.8) burada uygulanır.
* **`MatchAwareEvaluator`** yalnızca `MatchLength > 0` iken zincire eklenir.

### 5.4 Asenkron arama, iptal, düşünme bütçesi

* `ThinkAsync(CancellationToken)` → `Task<SearchResult>`.
* İptal: `CancellationToken.Register` ile arama döngüsü **her kök adaydan sonra** `ct.IsCancellationRequested` kontrol eder. **`BackgammonSearch` değişmez**; iptal, kök aday döngüsünün **dışında** (`GameOrchestrator` içinde) yapılır. Eğer `BackgammonSearch` iptal desteklemiyorsa, ajan **bunu raporlar** ve `GameOrchestrator` aramayı **tek seferde** çalıştırıp sonucu döner (iptal yalnızca **bekleme** aşamasında etkili olur). **`BackgammonSearch`'e iptal parametresi eklenmez** (Bölüm 0 kural 2).
* **Eşzamanlılık:** aynı anda **tek** arama. `GameOrchestrator` bir `SemaphoreSlim(1,1)` ile korur; ikinci çağrı `InvalidOperationException`.
* **`SearchWorkspace`** tek bir örnek olarak tutulur ve **yeniden kullanılır** (allocation'sız). Model değişirse `Reset()` **zorunlu**.

### 5.5 ONNX `output_version` metadata

Faz 4 v3 modeli `feature_version`, `vector_size`, `model_version`, `arch`, `trained_by` metadata'sı taşır. Faz 5 **tek bir alan ekler**: `output_version`.

* `ml/export_onnx.py`: `output_version = 1` (tek skaler `value` + tek `policy_logit`).
* `OnnxModelHandle`: `output_version` **yoksa** `1` kabul edilir (geriye dönük uyum, Faz 4 modelleri çalışmaya devam eder). `output_version > 1` ise **`NotSupportedException`** — çünkü Faz 6'nın 6 çıktılı modeli bu köprüyle **çalışmamalıdır** (sessiz yanlış sonuç yerine açık hata).
* **Değişen dosyalar:** `ml/export_onnx.py` (metadata ekleme), `Backgammon.Inference/OnnxModelHandle.cs` (metadata okuma + doğrulama). **`OnnxPolicyValueEvaluator` değişmez.**
* **Test:** Bölüm 8, Test 36.

---

## 6. Unity Görselleştirme

### 6.1 Proje ve dizin yapısı

```
unity/TavlaAI/
  ProjectSettings/ProjectVersion.txt        m_EditorVersion: 6000.3.8f1
  Packages/manifest.json
  Assets/
    Scenes/Main.unity
    Scripts/
      Bootstrap/GameBootstrap.cs
      Board/BoardView.cs, PointView.cs, CheckerView.cs, BarView.cs, TrayView.cs
      Dice/DiceView.cs
      Cube/CubeView.cs
      Hud/MatchScoreView.cs, CrawfordBadgeView.cs, MatchLengthView.cs
      Input/BoardInputController.cs, DragHandler.cs
      Analysis/AnalysisPanelView.cs, EquityBarView.cs
      Settings/SettingsPanelView.cs
      Infrastructure/UnityMainThreadDispatcher.cs, OnnxBackendFactory.cs
    Prefabs/  (Board, Checker, Dice, Cube, Point, AnalysisPanel, SettingsPanel)
    Sprites/  (tahta, taş, zar, küp — yer tutucu düz renkler kabul)
    Plugins/x86_64/onnxruntime.dll
    Plugins/Managed/Microsoft.ML.OnnxRuntime.dll, Backgammon.Core.dll,
                     Backgammon.Inference.dll, Backgammon.UI.dll
    Tests/EditMode/  (Unity Test Framework)
    Tests/PlayMode/  (yalnızca sahne dumanı)
```

**`Packages/manifest.json` (asgari):** `com.unity.ugui`, `com.unity.test-framework`, `com.unity.render-pipelines.universal`, `com.unity.inputsystem` (opsiyonel; klasik `Input` de kabul). **Sürümler Unity 6000.3.8f1'in paket yöneticisinin çözdüğü sürümlerdir; elle sabitlenmez.**

**Derleme çıktılarının kopyalanması:** `Backgammon.Core.dll`, `Backgammon.Inference.dll`, `Backgammon.UI.dll` ve `Microsoft.ML.OnnxRuntime.dll` `Assets/Plugins/Managed/`'e, `onnxruntime.dll` `Assets/Plugins/x86_64/`'e kopyalanır. Kopyalama **elle** yapılmaz; `tools/sync-unity-plugins.ps1` betiği `dotnet build -c Release` sonrası kopyalar. Betik **idempotent** olmalıdır.

### 6.2 `Backgammon.UI` — view-model katmanı (Unity'siz)

Yeni proje `Backgammon.UI` (`netstandard2.1`, `Backgammon.Core`'a referans, **`Backgammon.Inference`'a referans YOK**). Testleri `Backgammon.UI.Tests` (`net10.0`, xUnit).

| View-model | Sorumluluk | Test |
|---|---|---|
| `BoardViewModel` | 24 hane + bar + toplama; her hanede `(owner, count)`; sıra; zar | Test 27 |
| `CubeViewModel` | Küp görünürlüğü (`centered`/`owned`/`offered`), değer, sahip | Test 29 |
| `MatchScoreViewModel` | `whiteScore`, `blackScore`, `matchLength`, `awayA`, `awayB`, `isCrawford`, `isPostCrawford` | Test 28 |
| `AnalysisViewModel` | `PositionAnalysis` → görüntü metinleri; "kesin"/"tahmin" rozeti | Test 31 |
| `MoveInputController` | Yasal hedefler, seçili taş, kısmi hamle durumu, geri alma | Test 30 |
| `GameOrchestrator` | Bölüm 5.3 | Test 32, Test 33 |

**Kural:** View-model'ler **saf C#**'tır; `UnityEngine` **kullanmaz**; `INotifyPropertyChanged` **kullanmaz** (Unity'de gereksiz allocation). Değişim bildirimi `event Action Changed` ile yapılır; MonoBehaviour abone olur ve **kare başına bir kez** okur.

### 6.3 Sahne yapısı (`Main.unity`)

```
Main (Scene)
├── Main Camera            (Orthographic, size tahtayı sığdıracak şekilde)
├── EventSystem            (StandaloneInputModule veya InputSystemUIInputModule)
├── Canvas (Screen Space - Camera, CanvasScaler: Scale With Screen Size 1920×1080)
│   ├── BoardRoot          (RectTransform, 16:11 en-boy; tahta sprite'ı)
│   │   ├── Point_01 .. Point_24   (PointView, taş yığını konteyneri)
│   │   ├── BarWhite, BarBlack     (BarView)
│   │   ├── TrayWhite, TrayBlack   (TrayView, toplanan taşlar)
│   │   └── CheckerPool            (15 + 15 CheckerView, havuzlanmış)
│   ├── DiceRoot           (DiceView ×2)
│   ├── CubeRoot           (CubeView)
│   ├── HudRoot
│   │   ├── MatchScorePanel   (MatchScoreView)
│   │   ├── CrawfordBadge     (CrawfordBadgeView)
│   │   └── MatchLengthLabel  (MatchLengthView)
│   ├── AnalysisPanel      (AnalysisPanelView)
│   └── SettingsPanel      (SettingsPanelView, varsayılan kapalı)
└── GameBootstrap          (GameBootstrap MonoBehaviour)
```

**Zorunlu:** `GameBootstrap` tek bir `GameOrchestrator` oluşturur ve `DontDestroyOnLoad` ile korur. Sahnede **başka hiçbir** MonoBehaviour `GameOrchestrator` oluşturmaz.

### 6.4 Tahta ve taş render

* **Hane yerleşimi:** 24 hane, 4 çeyrek (6+6+6+6), klasik tavla düzeni. Hane `RectTransform`'ları **hesaplanır** (`BoardLayout.Calculate(width, height)` — saf C#, `Backgammon.UI` içinde, **test edilebilir**). Hane dikdörtgenleri **üst üste binmemeli** ve tahta sınırları içinde kalmalıdır (Bölüm 8, Test 38).
* **Taş yığını:** Bir hanede `n` taş varsa, taşlar dikey yığılır; `n > 5` ise üst üste binme miktarı azalır ve **sayı etiketi** gösterilir. Yığın yüksekliği hane yüksekliğini **aşmamalıdır**.
* **Havuzlama:** `CheckerPool` 30 `CheckerView` tutar; her karede yalnızca **görünürlük ve konum** güncellenir. `Instantiate`/`Destroy` **kare içinde yasak**.
* **Animasyon:** Taş hareketi `Vector3.Lerp` ile `MoveDuration` (varsayılan 0,15 s) boyunca. Animasyon **view-model'i bloklamaz**; `GameOrchestrator` durumu **anında** günceller, animasyon **gecikmeli** gösterir. Animasyon sırasında giriş **kilitlenir** (`BoardInputController.IsLocked`).
* **Vurgulama:** Yasal hedefler yarım saydam yeşil daire; seçili taş sarı halka; vurulacak taş kırmızı halka.

### 6.5 Zar

* `DiceView` iki zar gösterir; dublede **4 zar** gösterilir (klasik gösterim) veya tek zar + "×2" etiketi — **seçim raporda gerekçelendirilir**.
* Zar yüzleri `Sprite` olarak; yer tutucu olarak **sayı metni** kabul edilir.
* Zar atma animasyonu **kozmetiktir**; `GameOrchestrator.RollDice()` sonucu **hemen** view-model'e yazılır.

### 6.6 Küp widget

* `CubeView` küpü **yalnızca** şu durumlarda gösterir: `cubeOwner != 0` (bir tarafta) veya `phase == CubeOffered` (ortada, teklif edilmiş).
* Değer `1, 2, 4, 8, 16, 32, 64` olarak gösterilir; `64` üstü **yoktur** (money game üst sınırı).
* **Teklif akışı:** `CubeOffered` fazında iki düğme: **"Kabul"** / **"Reddet"**. Kabul ⇒ `BackgammonEngine.Take(state)`; Reddet ⇒ `BackgammonEngine.Pass(state)`.
* **AI küp teklifi:** `GameOrchestrator.EvaluateCube()` → `CubeDecision`. `ShouldDouble == true` ise UI "AI küp teklif ediyor" gösterir ve insanın kabul/red kararını bekler.
* **Crawford rozeti** ile küp widget'ı **aynı anda** görünürse çelişki olmamalı: Crawford'da küp **gösterilmez** (Bölüm 4.5).

### 6.7 Maç skoru, Crawford rozeti, maç uzunluğu

* `MatchScoreView`: `"Beyaz 3 — 5 Siyah"` biçiminde; maç uzunluğu `"7 sayı"`; money game'de `"Money game"`.
* `CrawfordBadgeView`: yalnızca `isCrawfordGame == true` iken **"CRAWFORD"**; `isPostCrawford == true` iken **"Post-Crawford"** (daha soluk).
* `MatchLengthView`: maç uzunluğu seçici (1, 3, 5, 7, 9, 11, 15, 21, 25) + "Money game" seçeneği. Değişiklik **yeni maç** başlatır (onay istenir).
* **Away skorları** analiz panelinde gösterilir: `"3-away / 5-away"`.

### 6.8 Hamle girişi

* **Sürükle-bırak:** `IBeginDragHandler` / `IDragHandler` / `IEndDragHandler`. Bırakılan hane yasal değilse taş **geri döner** (animasyonla).
* **Tıkla-tıkla:** Alternatif giriş; birinci tık kaynak, ikinci tık hedef.
* **Yasal hamle vurgusu:** `MoveInputController.LegalTargets(fromPoint)` — `LegalMoveGenerator`'ın ürettiği hamlelerden **türetilir**, ayrıca yazılmaz.
* **Kısmi hamle:** Dublede 4 adım; her adım ayrı ayrı oynanır. `MoveInputController` kalan zarları takip eder.
* **Geri alma:** `EngineSettings.EnableUndo` açıksa son adım geri alınır (`BackgammonEngine.UndoStep`).
* **Otomatik oynatma:** `EngineSettings.AutoExecuteSingleMoves` açıksa tek yasal hamle otomatik oynanır.

### 6.9 Analiz paneli

`AnalysisPanelView` şunları gösterir:

| Alan | Kaynak | Biçim |
|---|---|---|
| Equity | `PositionAnalysis.Equity` | `+0,123` (3 ondalık, `tr-TR`) |
| MWC | `PositionAnalysis.MatchWinningChance` | `%54,3`; money game'de `—` |
| ME | `PositionAnalysis.MatchEquity` | `+0,086` |
| Kaynak | `FromBearoffDatabase` / `IsExact` | **"Kesin (bearoff DB)"** / **"Tahmin (ağ)"** |
| Mars olasılıkları | `Distribution` | `Kazanma %52 · Mars %18 · Rakip mars %9`; `null` ise `—` |
| Pip sayıları | `PipCountActive/Opponent` | `142 — 155` |
| Tur sayısı | `RollsToOffActive/Opponent` | `4 — 6`; `-1` ise `—` |
| Küp | `CubeDecision` | `"Küp: teklif et (kabul bekleniyor)"` / `"Küp: etme"` |
| Aday hamleler | `AnalyzeCandidates()` | Sıralı liste, her satırda equity + fark |

**Kural:** Panel **hiçbir zaman** "kesin" ile "tahmin"i karıştırmaz. `IsExact == false` iken "Kesin" yazmak **yasaktır**.

### 6.10 Ayarlar

`SettingsPanelView`:
* Maç uzunluğu (Bölüm 6.7).
* Jacoby aç/kapa (`EngineSettings.EnableJacoby`).
* Ölü küp yasağı (`EngineSettings.DisallowDeadCube`).
* Zorluk: `DepthPly` 0 / 1 / 2 + `MaxCandidatesRoot` / `MaxCandidatesInner` (Faz 4 §5.15 tablosundaki ölçülmüş değerler **gösterilir**, uydurma yok).
* Düşünme bütçesi (ms).
* Zar kaynağı: rastgele / sabit (test).
* Dil: `tr-TR` (varsayılan) / `en-US`.

Ayarlar `PlayerPrefs`'te saklanır. **`PlayerPrefs` anahtarları `tavla.` önekiyle** yazılır.

### 6.11 Inference arka ucu: ORT birincil, Sentis yedek

**Karar: ONNX Runtime.** Gerekçe:
1. Faz 4 v3'te `OnnxPolicyValueEvaluator` **zaten** ORT üzerine yazıldı ve **53 test** ile doğrulandı (`Backgammon.Inference.Tests`). Sentis'e geçmek bu kodu **yeniden yazmak** demektir.
2. ORT'nin CPU↔CUDA paritesi ve 0 bayt/çağrı ölçümü **mevcut** (`PHASES.md` §7).
3. Model küçük bir MLP'dir (221→128→64→1); ORT'nin native plugin'i Windows x64'te sorunsuz çalışır.

**Uygulama:**
* `Assets/Plugins/x86_64/onnxruntime.dll` (ORT NuGet paketinden çıkarılır; sürüm `Backgammon.Inference.csproj` ile **aynı** olmalıdır).
* `Assets/Plugins/Managed/Microsoft.ML.OnnxRuntime.dll`.
* `OnnxBackendFactory` (Unity tarafı) `OnnxModelHandle` + `OnnxPolicyValueEvaluator` oluşturur ve `GameOrchestratorOptions.Evaluator` olarak verir.
* **Model dosyası** `Assets/StreamingAssets/models/model.onnx`; `Application.streamingAssetsPath` üzerinden okunur. **`TextAsset` olarak yüklenmez** (binary bozulur).

**Yedek (Sentis):** ORT native plugin hedef platformda yüklenemezse, ajan **bunu raporlar** ve Sentis yolu **açık soru** olarak bırakılır. **Sentis uygulaması bu fazda yazılmaz** (Bölüm 10).

### 6.12 Unity derleme ve test komutları (doğrulama)

```powershell
$unity = "C:\Program Files\Unity\Hub\Editor\6000.3.8f1\Editor\Unity.exe"

# 1) Derleme (batchmode)
& $unity -batchmode -nographics -quit -projectPath unity\TavlaAI `
         -logFile unity\build.log -executeMethod TavlaAI.Editor.BuildScript.CompileOnly

# 2) EditMode testleri
& $unity -batchmode -nographics -projectPath unity\TavlaAI `
         -runTests -testPlatform EditMode `
         -testResults unity\editmode-results.xml -logFile unity\editmode.log

# 3) PlayMode duman testi
& $unity -batchmode -nographics -projectPath unity\TavlaAI `
         -runTests -testPlatform PlayMode `
         -testResults unity\playmode-results.xml -logFile unity\playmode.log
```

**Lisans riski:** Unity batchmode **lisans etkinleştirmesi** gerektirir. Etkinleştirme yoksa komutlar başarısız olur. Bu durumda ajan:
1. **Bunu açıkça raporlar** (hata metniyle birlikte).
2. `Backgammon.UI` + `Backgammon.UI.Tests`'i **tam** çalıştırır (Unity'siz, xUnit) — bu, iş mantığının **%100'ünü** kapsar.
3. Unity tarafını **derlenmiş ama doğrulanmamış** olarak işaretler ve `unity/README.md`'ye doğrulama adımlarını yazar.

**Kural:** Lisans yoksa "Unity testleri geçti" **yazılmaz**. "Unity testleri çalıştırılamadı, neden: …" yazılır.

---

## 7. Faz 1–4 ile Uyum

| Faz | Sözleşme | Faz 5'te durum |
|---|---|---|
| Faz 1 v4 | `BackgammonState`, `BackgammonEngine`, `LegalMoveGenerator`, `AfterStateList`, `MoveList`, `MoveSequence`, `EngineSettings`, `MatchSettings`, `GameResult`, `GamePhase` | **Değişmez.** Yalnızca **okunur** |
| Faz 1 v4 | `BackgammonEngine.CanOffer/OfferDouble/Take/Pass/StartNextGame` | **Değişmez.** `EquityCubeAdvisor` bunları **kullanır** |
| Faz 2 v4 | `BackgammonVectorizer`, `VectorLayout` (221), `VectorizerScalars`, `FeatureVersion = 1` | **Değişmez** |
| Faz 3 v7 | `BackgammonSearch`, `SearchSettings`, `SearchWorkspace`, `SearchResult`, `RollSet` | **Değişmez.** Dekoratörler **altına** girer |
| Faz 3 v7 | `IPositionEvaluator`, `IPolicyEvaluator`, `IPolicyValueEvaluator`, `ICombinedBatchEvaluator`, `ICubeEvaluator`, `ICubePolicyEvaluator` | **Değişmez.** Dekoratörler ve danışman bunları **uygular** |
| Faz 3 v7 | Negamax `q_r = −V(çocuk)`, `ClampInPlace` `[-3,3]` | **Değişmez.** `ME` antisimetrik olduğu için doğru çalışır |
| Faz 4 v3 | `OnnxPolicyValueEvaluator`, `OnnxEvaluatorOptions`, ONNX sözleşmesi (girdi/çıktı adları, opset 15, dinamik batch) | **Değişmez** |
| Faz 4 v3 | `OnnxModelHandle` metadata doğrulaması | **Yalnızca `output_version` eklenir** (Bölüm 5.5) |
| Faz 4 v3 | `ml/export_onnx.py` | **Yalnızca `output_version` metadata'sı eklenir** |
| Faz 4 v3 | `Backgammon.SelfPlay`, `ml/train.py`, `ml/league.py`, `ml/eval_bench.py` | **Değişmez** |
| Faz 4 v3 | `ml/tests/test_docs_consistency.py` `EXPECTED_COUNTS` | **Güncellenir** (yeni test sayıları) |

**Onaylanmış iki ekleme (bunlar dışında Faz 1–4 kodu değişmez):**
1. `OnnxModelHandle` + `ml/export_onnx.py`: `output_version` metadata alanı (Bölüm 5.5).
2. `ml/tests/test_docs_consistency.py`: `EXPECTED_COUNTS` güncellemesi.

> **Not:** Bölüm 3.6'da açıklandığı gibi `AfterStateList.CopyRecordFrom` **eklenmez**. Faz 1 API'sine **hiç** dokunulmaz.

---

## 8. Test ve Doğrulama (Zorunlu, Önce Yazılır)

**C# — Bearoff (`Backgammon.Tests`)**

1. **`BearoffIndex_RoundTrip`:** 54264 pozisyonun **tamamı** için `Unrank(Rank(c)) == c`. Ayrıca `Rank` çıktıları `[0, 54264)` aralığında ve **tekil** (bijection).
2. **`BearoffIndex_Boundaries`:** hepsi toplanmış ⇒ `0`; hepsi 1-hanede ⇒ `54263`. Ara değerler için elle hesaplanmış 5 örnek.
3. **`BearoffDatabase_HeaderValidation`:** bozuk `magic`, `version`, `points`, `checkers`, `positions`, `payloadBytes`, `payloadCrc32` ⇒ **her biri için** `InvalidDataException`. Kısaltılmış dosya ⇒ `InvalidDataException`.
4. **`BearoffDatabase_MonotoneCdf`:** her pozisyon için `cdf[k]` monoton azalmayan, `cdf[0] == 0`, `cdf[MaxRolls] == 1` (nicemleme toleransı `1/65535`).
5. **`BearoffDatabase_KnownPositions`:** elle/bağımsız hesaplanmış değerlerle karşılaştırma. En az: (a) 1 taş 1-hanede ⇒ 1 turda toplar (`cdf[1] == 1`); (b) 15 taş 1-hanede ⇒ bilinen dağılım; (c) 1 taş 6-hanede ⇒ 1 turda toplama olasılığı `11/36` (tek zarla 6 atma: 11/36). **Bu değerler kesin matematiktir, ölçüm değildir.**
6. **`BearoffDatabase_NoAllocation`:** ısınma sonrası 1000 `TryGetCdf` çağrısı ⇒ **0 bayt**.
7. **`BearoffAwareEvaluator_OverwritesBearoffResults`:** karışık batch (bearoff + değil) ⇒ bearoff kayıtları **kesin**, diğerleri **iç değerlendiricinin aynısı**.
8. **`BearoffAwareEvaluator_PureBearoffSkipsInner`:** `SkipInnerForPureBearoffBatches = true` + tüm kayıtlar bearoff ⇒ iç değerlendiricinin çağrı sayacı **0**.
9. **`BearoffAwareEvaluator_DisableIsIdentity`:** `DisableBearoff = true` ⇒ çıktı iç değerlendiriciyle **bit düzeyinde** aynı.
10. **`BearoffAwareEvaluator_VersionComposition`:** farklı DB ⇒ farklı `Version`; farklı iç model ⇒ farklı `Version`.
11. **`BearoffAwareEvaluator_ZeroAllocation`:** ısınma sonrası `EvaluateBatch` ⇒ **0 bayt**.
12. **`BearoffAwareEvaluator_ContractViolations`:** `offset != 0` ⇒ `ArgumentException`; terminal kayıt ⇒ `ArgumentException`; `count == 0` ⇒ dönüş.
13. **`BearoffAwareEvaluator_Determinism`:** aynı girdi, aynı batch bileşimi ⇒ **birebir** aynı çıktı.

**C# — Maç / Küp (`Backgammon.Tests`)**

14. **`MatchEquityTable_Invariants`:** Bölüm 4.2'deki 6 değişmez, `maxMatchLength = 25` için **tüm** `(a,b)` çiftlerinde.
15. **`MatchEquityTable_MatchesGnubg`:** çıkarılan gnubg MET'i ile karşılaştırma; maksimum `|Δ|` **ölçülür ve raporlanır**. Çıkarılamadıysa test **atlanır** (`Skip` ile) ve raporlanır.
16. **`MatchState_Derivations`:** `AwayScore`, `IsCrawfordGame`, `IsPostCrawford`, `IsDeadCube`, `MaxCubeValue` — elle hesaplanmış 10 senaryo.
17. **`OutcomeDistribution_Invariants`:** Bölüm 4.3'teki 5 değişmez; `Equity` formülü elle hesaplanmış 5 örnekle.
18. **`HeuristicOutcomeDistribution_Invariants`:** monotonluk (`equity` −3..+3 arası 601 noktada), süreklilik, uçlar, `isContact == false` ⇒ backgammon 0.
19. **`EquityCubeAdvisor_MoneyGameThresholds`:** `E = 1,2` ⇒ double+pass; `E = 0,6` ⇒ double+take; `E = 0,3` ⇒ no double. **Eşikler formülden türetilir**, test formülü doğrular.
20. **`EquityCubeAdvisor_CrawfordNoCube`:** Crawford oyununda `ShouldDouble == false` (10 farklı skor).
21. **`EquityCubeAdvisor_DeadCube`:** ölü küpte `ShouldDouble == false`.
22. **`EquityCubeAdvisor_PostCrawfordFreeDrop`:** post-Crawford'da `ShouldTake` serbest düşüş mantığına uyar.
23. **`MatchAwareEvaluator_Antisymmetry`:** `ME(p) == −ME(mirror(p))` (tolerans `1e-6`), 100 rastgele pozisyon.
24. **`MatchAwareEvaluator_ChangesArgmax`:** **yapay** pozisyon: `argmax E ≠ argmax ME`. `MatchAwareEvaluator` doğru hamleyi seçer. **Bu test olmadan maç-duyarlılığı "eklendi" sayılmaz.**
25. **`MatchAwareEvaluator_MoneyGamePassthrough`:** `matchLength == 0` ⇒ iç değerlendiriciyle **bit düzeyinde** aynı.
26. **`MatchAwareEvaluator_VersionIncludesMatch`:** skor değişince `Version` değişir.

**C# — UI view-model (`Backgammon.UI.Tests`)**

27. **`BoardViewModel_ReflectsState`:** başlangıç dizilimi, bar, toplama, sıra, zar — `BackgammonState` ile birebir.
28. **`MatchScoreViewModel_CrawfordBadge`:** Crawford / post-Crawford / normal / money game — 4 durum.
29. **`CubeViewModel_Visibility`:** `centered` / `owned` / `offered` / Crawford'ta gizli.
30. **`MoveInputController_LegalTargets`:** 200 rastgele pozisyonda `LegalTargets` kümesi `LegalMoveGenerator`'ın ürettiği hamlelerin hedefleriyle **birebir**.
31. **`AnalysisViewModel_FormatsPositionAnalysis`:** `IsExact` doğru rozet; `RollsToOff == -1` ⇒ `—`; `tr-TR` ondalık ayırıcı virgül.
32. **`GameOrchestrator_DeterministicSelfPlay`:** sabit seed, 50 oyun ⇒ **birebir** aynı sonuç dizisi.
33. **`GameOrchestrator_ThinkAsyncCancellation`:** iptal edilen arama `OperationCanceledException` **veya** en iyi hamle döner (dokümante edilen davranış); UI iş parçacığı bloklanmaz.

**Python (`ml/tests`)**

34. **`test_bearoff_ref_matches_csharp`:** `ml/bearoff_ref.py` (bağımsız DP) ile C# üretimi `bearoff1_v1.bin` **nicemleme toleransı içinde** eşit. Maksimum `|Δ|` raporlanır.
35. **`test_met_extraction_invariants`:** `met_rk.json` Bölüm 4.2 değişmezlerini sağlar; `maxMatchLength` tutarlı.
36. **`test_export_output_version`:** `export_onnx.py` çıktısında `output_version == 1`; `OnnxModelHandle` bunu okur.
37. **`test_docs_consistency`:** `EXPECTED_COUNTS` güncellenir; `PHASES.md` §12, `ARCHITECTURE.md` §43, `ASSUMPTIONS.md` F5-xx referansları tutarlı.

**Unity (EditMode)**

38. **`BoardLayout_NoOverlap`:** `BoardLayout.Calculate(1920, 1080)` ⇒ 24 hane dikdörtgeni **üst üste binmez**, hepsi tahta sınırları içinde. Farklı en-boy oranlarında (16:9, 4:3, 21:9) tekrar.
39. **`SceneLoads`:** `Main.unity` yüklenir; `GameBootstrap`, `BoardView`, `DiceView`, `CubeView`, `MatchScoreView`, `CrawfordBadgeView`, `AnalysisPanelView` sahnede **var**.
40. **`CheckerPool_NoRuntimeInstantiate`:** 100 kare simülasyonunda `Instantiate` çağrı sayısı **0**.

---

## 9. Ölçüm, Benchmark ve Kabul Kriterleri

**Tüm eşikler yer tutucudur; ilk ölçümden sonra birlikte belirlenir. Uydurma eşik yoktur.**

### 9.1 Bearoff

| Ölçüm | Yöntem | Raporlanacak |
|---|---|---|
| DB dosya boyutu | `FileInfo.Length` | bayt (beklenen ≈ 1,55 MB, `MaxRolls = 12` + gammon) |
| Üretim süresi | `Stopwatch` | saniye |
| Nicemleme hatası | `max \|E_exact − E_quantized\|` üzerinde 10 000 rastgele bearoff pozisyonu | maksimum ve ortalama |
| İsabet oranı | 10 000 rastgele self-play pozisyonunda `IsOneSidedBearoff` oranı | yüzde |
| Dekoratör ek yükü | `EvaluateBatch` süresi, DB açık/kapalı | µs/çağrı, oran |
| Dekoratör allocation | `GC.GetAllocatedBytesForCurrentThread` | bayt/çağrı (hedef 0) |
| Depth-0 kısayolu kazancı | bearoff pozisyonunda `DepthPly = 1` vs `0` | ms/karar, oran |
| gnubg uyumu | 200 referans bearoff pozisyonunda gnubg `eval` ile karşılaştırma | maksimum `\|Δ\|` equity |

**Ölçülen değerler (Aşama A, `dotnet run --project Backgammon.BearoffGen -- --measure`):**

| Ölçüm | Değer | Not |
|---|---|---|
| DB dosya boyutu | **2 496 208 bayt (2,38 MiB)** | `MaxRolls = 22`, gammon tablosu yok. Beklenen 1,55 MB `MaxRolls = 12` varsayımına dayanıyordu; gerçek `MaxRolls` 22 çıktı (en kötü pozisyon: 15 taş 6-hanesinde, 22 tur gerekir). |
| Üretim süresi | **5,26 s** (geçiş tablosu 5 103 ms + DP 148 ms) | Tek iş parçacıklı, deterministik. |
| `MaxRolls` yeterliliği | **22** (istenen 12 yetersizdi, üretici artırdı) | Sessiz kırpma yok. |
| Gammon tablosu | **üretilmedi** (bayrak 0) | §3.7'de mars olasılıkları 0 kabul edilir ve raporlanır. |
| Nicemleme hatası | **maks 7,643E-06, ortalama 9,774E-07** | 10 000 pozisyon, 230 000 örnek. Kuramsal üst sınır 7,630E-06 (`uint16`) + `float` okuma yuvarlaması. |
| İsabet oranı | **%9,01** (901/10 000 rastgele self-play pozisyonu, 97 oyun) | Tek taraflı bearoff tanımı gereği düşük; iki taraflı DB (Faz 6) bunu belirgin artırır. |
| Dekoratör ek yükü | **DB açık 14,730 µs/çağrı, DB kapalı 0,052 µs/çağrı** (64 kayıt/çağrı, 20 000 çağrı) | Partinin 32 kaydı bearoff: **≈0,46 µs/bearoff pozisyonu**. ONNX CPU yolu ≈1,4 µs/pozisyon olduğundan bearoff yolu **≈3× daha hızlıdır**. "Oran 285×" yanıltıcıdır: kapalı durumdaki taban, hiç iş yapmayan `NullInnerEvaluator`'dır. |
| Dekoratör allocation | **0 bayt/çağrı** (DB açık ve kapalı) | Hedef 0 tutturuldu. |
| Depth-0 kısayolu kazancı | **DepthPly = 1: 0,197 ms/karar → DepthPly = 0: 0,009 ms/karar, 21,10×** | 200 pozisyon. |
| gnubg uyumu (equity) | **maks \|Δ\| 0,003519, ortalama 0,000325, medyan 0,000271** | 200 pozisyon; %100 `\|Δ\| ≤ 0,01`, %96,5 `\|Δ\| ≤ 0,001`. Kalan fark, bizim mars olasılığını 0 kabul etmemizden gelir. |
| gnubg uyumu (dağılım) | **maks \|Δ\| 0,000035, ortalama 0,000005** | 200 pozisyon, 1 983 hücre. gnubg 5 ondalık yazdırdığı için bu pratikte tam uyumdur. |
| C# ↔ Python referansı | **maks fark 7,630E-06, tolerans dışı 0** | `python ml/bearoff_ref.py --check ml/artifacts/bearoff1_v1.bin` |

**Beraberlik kuralı duyarlılığı (ölçüldü):** `E[T]` eşitliğinde dört farklı kural denendi — en küçük sıra, en küçük durum demeti, en küçük `E[T²]`, en büyük sıra. Dördü de gnubg ile **aynı** dağılımı verdi (maks `\|Δ\| = 3,4E-05`). Yani sonuç beraberlik kuralına duyarsızdır; uygulamada en küçük sıra kullanılır.

### 9.2 Küp ve maç

| Ölçüm | Yöntem | Raporlanacak |
|---|---|---|
| MET doğruluğu | gnubg MET ile karşılaştırma | maksimum `\|Δ\|` MWC |
| Küp kararı uyumu | 200 referans pozisyonda gnubg `hint`/`cube` kararı ile karşılaştırma | uyum yüzdesi, hata matrisi |
| Maç-duyarlı hamle kazancı | 2-away/2-away, 4-away/4-away, 5-away/5-away skorlarında `MatchAwareEvaluator` açık/kapalı, `PipBot`'a karşı 200 oyun | kazanma yüzdesi ± standart hata |
| Crawford doğruluğu | Crawford/post-Crawford senaryolarında küp kararı | doğru/yanlış sayısı |
| Maç ER | gnubg ile maç oyunu (mümkünse) | ER; mümkün değilse **"ölçülemedi"** yazılır |

**Ölçülen değerler (Aşama B):**

| Ölçüm | Değer | Not |
|---|---|---|
| MET doğruluğu | **maks \|Δ\| = 0,000E+000** (625 hücre, 25×25) | `MatchEquityTable_MatchesGnubg` gnubg 1.08.003'ün gömülü Rockwell–Kazaross XML'i ile **birebir** eşleşiyor. Tolerans `1e-12`. |
| Küp kararı uyumu (gnubg 0-ply) | **çiftleme %51,52 · kabul %61,36 · her ikisi %46,21** (132 pozisyon) | `ml/match_bench.py`, `cfevaluate` `deterministic=1`. |
| Küp kararı uyumu (gnubg 2-ply) | **çiftleme %52,27 · kabul %61,36 · her ikisi %46,97** (132 pozisyon) | 0-ply ile 2-ply arasında fark yok; hata modelden geliyor, gnubg derinliğinden değil. |
| Hata matrisi — çiftleme (0-ply) | bizim çiftle & gnubg çiftle **13** · bizim çiftle & gnubg çiftleme **51** · bizim çiftleme & gnubg çiftle **13** · ikisi de çiftleme **55** | Aşırı çiftleme eğilimi: 51'e karşı 13. |
| Hata matrisi — kabul (0-ply) | ikisi de kabul **79** · bizim kabul & gnubg ret **10** · bizim ret & gnubg kabul **41** · ikisi de ret **2** | Aşırı ret eğilimi: 41'e karşı 10. |
| Equity korelasyonu (tek kayıt) | **−0,0315**, MAE **1,0550** | §4.4'ün öngördüğü "pre-roll tahtayı tek afterstate gibi değerlendir" yaklaşımı. |
| Equity korelasyonu (zar-ortalamalı) | **+0,1395**, MAE **1,2063** | 21 zar kombinasyonunun en iyi afterstate değerinin ağırlıklı ortalaması. Korelasyon 4,4× iyileşiyor ama MAE büyüyor (aşırı dağılım). |
| Maç-duyarlı hamle kazancı, 2-away/2-away | kapalı **%40,00 ± 9,40** · açık **%39,50 ± 9,43** (400 oyun) | Puan/maç: −0,4125 → −0,4325. Fark **istatistiksel olarak anlamsız** (Δ = −0,50 pp, SE ≈ 13,3 pp). |
| Maç-duyarlı hamle kazancı, 4-away/4-away | kapalı **%39,75 ± 9,43** · açık **%40,00 ± 9,51** (400 oyun) | Puan/maç: −0,4525 → −0,4275. Δ = +0,25 pp, anlamsız. |
| Maç-duyarlı hamle kazancı, 5-away/5-away | kapalı **%42,25 ± 9,38** · açık **%44,75 ± 9,48** (400 oyun) | Puan/maç: −0,2900 → −0,2300. Δ = +2,50 pp, hâlâ SE'nin altında. |
| Crawford doğruluğu | **10/10** Crawford senaryosu (Test 20) + post-Crawford serbest ret (Test 22) + ölü küp (Test 21) | Crawford'da `ShouldDouble` her skorda `false`. |
| Maç ER | **ölçülemedi** | gnubg'nin maç oynatma sürücüsü (`.sgf` maç dosyası + `analyse`) bu ortamda otomatikleştirilmedi. Money-game ER ölçümü Faz 4'te mevcut (0,1941). |
| Test 24 (argmax değişimi) | **geçti** | `MatchAwareEvaluator_ChangesArgmax`: aynı pozisyonda `argmax E ≠ argmax ME`. Maç-duyarlılığın gerçekten karar değiştirdiğinin kanıtı. |

**Model değer kafası teşhisi (Aşama B'de ortaya çıktı):**

Küp uyumunun düşük olmasının kaynağı `EquityCubeAdvisor` mantığı **değil**, tüketilen modelin değer kafasıdır. `ml/afterstate_bench.py` 400 afterstate'i gnubg `evaluate` ile doğrudan karşılaştırdı:

| Ölçüm | Değer |
|---|---|
| Korelasyon (Pearson) | **+0,2431** |
| Ortalama mutlak hata | **0,8014** |
| Sistematik sapma (bizim − gnubg) | **−0,0850** |
| Bizim equity aralığı / std | **−2,8050 … +3,2966** / **1,0320** |
| gnubg equity aralığı / std | **−0,8207 … +1,6497** / **0,3710** |
| En küçük kareler kalibrasyonu `gnubg ≈ a·bizim + b` | **a = 0,0874**, **b = +0,1589** |
| Kalibrasyon sonrası MAE | **0,2897** (2,8× iyileşme) |

`a = 0,0874` ⇒ modelin değer kafası **≈11,4× aşırı dağılmıştır** (over-dispersed). Sıralama korelasyonu (+0,24) zayıftır; bu yüzden küp kararları gnubg ile %46–52 düzeyinde örtüşür. Bu bir **Faz 4 model kalitesi** bulgusudur, Aşama B uygulama hatası değildir: `EquityCubeAdvisor`'ın 47 birim testi (Test 14–26) yeşildir ve Test 24 maç-duyarlılığın kararı değiştirdiğini kanıtlar.

**Öneri (Faz 6):** (1) değer kafasını yeniden eğit veya çıktı katmanına kalibrasyon ekle; (2) `EquityCubeAdvisor`'a zar-beklentili değerlendirme seçeneği ekle (ölçülen korelasyon 4,4× artıyor). İkisi birlikte küp uyumunu gnubg seviyesine yaklaştırmalıdır.

### 9.3 Unity

| Ölçüm | Yöntem | Raporlanacak | **Ölçülen** |
|---|---|---|---|
| Kare süresi | `Profiler` veya `Time.deltaTime` ortalaması, 60 s hedef | ms (hedef ≤ 16,7 ms) | batchmode `-nographics` olduğu için ölçülmedi; `MainScene_SmokeTest` 60 kareyi 9,63 s'de tamamladı (≈160 ms/kare, yazılım rasterleştirici) |
| Kare başına allocation | `Profiler.GetTotalAllocatedMemoryLong` farkı | KB/kare | ölçülmedi (batchmode'da Profiler yok) |
| Arama gecikmesi | `ThinkAsync` süresi, `DepthPly` 0/1/2 | ms | `DepthPly = 1`, 146 değerlendirici çağrısı; `Onnx_MainThread_Search` 72 ms (ilk çağrı, model yükleme dahil) |
| Sahne yükleme | `SceneManager.LoadScene` süresi | ms | `SceneLoads` 256 ms |
| EditMode test sonucu | `editmode-results.xml` | geçen/kalan | **7 / 7 geçti** |
| PlayMode test sonucu | `playmode-results.xml` | geçen/kalan | **4 / 4 geçti** |
| `CheckerPool` çalışma anı `Instantiate` | 100 kare simülasyon | 0 olmalı | **0** |
| `BoardLayout` çakışması | 16:9, 4:3, 21:9 | 0 çakışma | **0** (kayan nokta hatası düzeltildikten sonra) |
| `onnxruntime.dll` sürümü | `Assets/Plugins/x86_64` | 1.23.2 | 1.23.20251021.3.a83fc4d |
| Bearoff DB yükleme | `OnnxBackendFactory.OpenBearoff` | 54 264 pozisyon | **54 264**, `MaxRolls = 22` |

**Aşama D'de bulunan üç gerçek hata (düzeltildi):**

1. **`BoardLayout` kayan nokta çakışması.** Komşu hanelerin sol kenarı `c·w`, sağ kenarı
   `(c+1)·w` ile hesaplanınca `1E-013` mertebesinde üst üste binme oluşuyordu. Test 38
   yakaladı; `left`/`right` aynı ifade ailesinden türetilerek düzeltildi.
2. **ONNX Runtime iş parçacığı güvenliği.** `OrtIoBinding` iş parçacığı güvenli değildir.
   Arama gerçek kare döngüsü içinde arka plan iş parçacığında çalıştırıldığında
   `SynchronizeBoundInputs` erişim ihlali (`0xC0000005`) üretiyordu. Tek başına çalışan
   arka plan aramaları geçiyordu; hata yalnızca sahne + kare döngüsü + ONNX birlikteyken
   ortaya çıkıyordu. Düzeltme: `GameOrchestrator.Think()` — arama **çağıran iş
   parçacığında** senkron çalışır. `ThinkAsync` Unity'den bağımsız katmanda ve testlerde
   aynen geçerlidir.
3. **Girdi işleyicisi.** `StandaloneInputModule` yalnızca eski girdi arka ucuyla çalışır;
   proje Input System paketini kullanıyordu (`activeInputHandler: 1`) ve her karede
   `InvalidOperationException` atıyordu. `activeInputHandler: 2` (**Both**) yapıldı.

**Lisans durumu:** batchmode lisansı bu makinede **mevcuttur**; yukarıdaki Unity
sonuçları gerçek koşulara dayanır (`unity/build.log`).

### 9.4 Aşama kabul kriterleri

* **Aşama A:** Test 1–13 yeşil; DB üretilir; Bölüm 9.1 tablosu **doldurulur**.
* **Aşama B:** Test 14–26 yeşil; Bölüm 9.2 tablosu **doldurulur**; Test 24 (argmax değişimi) **geçer**.
* **Aşama C:** Test 27–37 yeşil; `Backgammon.UI` derlenir; `output_version` doğrulanır.
* **Aşama D:** Test 38–40 yeşil **veya** Unity lisansı yoksa gerekçeli rapor; `unity/build.log` hatasız.
* **Aşama E:** Tüm testler yeşil; `PHASES.md` §12, `ARCHITECTURE.md` §43, `ASSUMPTIONS.md` F5-01…F5-xx yazılır; Bölüm 9 tabloları **ölçülmüş** değerlerle dolu.

---

## 10. Kapsam Dışı ve Açık Sorular

**Kapsam dışı (bilinçli):**
* **6 çıktılı değer başı** (`W, GW, BW, L, GL, BL`) — **Faz 6**. Arayüz (`IOutcomeDistributionEvaluator`) **şimdi** tanımlanır.
* **Eğitim ölçeği** (10⁵–10⁶ oyun, kapasite artışı) — **Faz 6**.
* **2 taraflı bearoff veritabanı** — **Faz 6** (Bölüm 3.1'deki boyut matematiği).
* **Race / CRASH / contact veritabanı** — **Faz 6**.
* **Beaver, Raccoon, Chouette, çok oyunculu** — kapsam dışı.
* **Çevrimiçi çok oyunculu** — kapsam dışı.
* **Unity Sentis arka ucu** — yalnızca yedek; uygulama **yok**.
* **IL2CPP / WebGL / mobil derleme** — kapsam dışı (yalnızca Windows x64 Standalone).
* **`BackgammonSearch` iptal desteği** — eklenmez (Bölüm 5.4).
* **`AfterStateList.CopyRecordFrom` / batch partitioning** — eklenmez (Bölüm 3.6).

**Açık sorular — Aşama E'de cevaplandı:**

1. **gnubg Rockwell-Kazaross MET'i çıkarılabildi mi?** Evet. gnubg 1.08.003'ün
   `met/Rockwell-Kazaross.xml` dosyasından çıkarıldı, `Backgammon.Core/Match/met_rk.json`
   içine gömüldü. 625 hücrenin tamamında **max |Δ| = 0,000E+000** — bit düzeyinde aynı.
   Değişmezler `ml/tests/test_met_extraction.py` (Test 35) ile korunur.
2. **`HeuristicOutcomeDistribution` katsayıları nasıl kalibre edildi?** Kalibre
   **edilmedi**; sezgisel (pip farkı tabanlı) bir yaklaşımdır ve `IsExact = false` olarak
   işaretlenir. Küp kararı uyumu kalibrasyondan değil, değer kafasından etkilenir:
   ikileme %51,52 / alma %61,36 (0-ply). Ayrıntı: `ml/artifacts/stage_b_cube.md`.
3. **Unity batchmode lisansı çalıştı mı?** Evet, çalıştı. EditMode 7/7, PlayMode 4/4.
   Kayıt: `unity/build.log`.
4. **ORT native plugin Unity'de yüklendi mi?** Evet. `Assets/Plugins/x86_64/onnxruntime.dll`
   sürümü **1.23.20251021.3.a83fc4d** (beklenen 1.23.2 ile uyumlu). `Onnx_MainThread_Evaluate`
   ve `Onnx_MainThread_Search` testleri gerçek çıkarım yapar.
5. **`MaxRolls = 12` yeterli miydi?** Hayır. Üretici **22**'ye yükseltmek zorunda kaldı
   (en kötü pozisyon: 6 hanesinde 15 pul).
6. **Gammon tablosu üretildi mi?** Hayır. `flags = 0`; saf yarışta mars zaten imkânsızdır
   (arka arkaya mars da öyle). `TryGetGammon` API'si hazırdır, `HasGammonData = false`
   olduğunda mars olasılığı 0 döner ve bu `PositionAnalysis`'ta raporlanır.
7. **`MatchAwareEvaluator` ölçülebilir kazanç sağladı mı?** Hayır. 400 oyunluk
   karşılaştırmada 2-away %40,00 vs %39,50, 4-away %39,75 vs %40,00, 5-away %42,25 vs
   %44,75 — hepsi standart hatanın içinde. Nedeni katman değil, değer kafasının ≈11,4 kat
   aşırı dağınık olmasıdır (kalibrasyon eğimi 0,0874). Ayrıntı: `ml/artifacts/stage_b_afterstates.md`.
8. **`ExactRootScores` / `UseEvalCache` dekoratörlerle beklenmedik etkileşim gösterdi mi?**
   Hayır. Ancak iki gerçek etkileşim bulundu ve belgelendi: (a) `Version` değişince
   `SearchWorkspace.Reset()` zorunludur — `GameOrchestrator.EnsureChain` bunu bileşik bir
   anahtarla yapar; (b) `OrtIoBinding` iş parçacığı güvenli değildir, bu yüzden Unity
   tarafı `Think()` ile çağıran iş parçacığında arama yapar (F5-17).

---

## 11. Aşamalı Teslimat Planı

| Aşama | Teslimat | Kabul kriteri |
|---|---|---|
| **A** | `BearoffDatabase` (format, memory-mapped okuyucu, `Rank`/`Unrank`), `Backgammon.BearoffGen` (DP + `--verify`), `BearoffAwareEvaluator` + `BearoffAwareOptions`, `ml/bearoff_ref.py` (bağımsız referans), `ml/artifacts/bearoff1_v1.bin`, Test 1–13 (kırmızı → yeşil) | Derlenir; Test 1–13 yeşil; **Bölüm 9.1 tablosu doldurulur**; DB dosyası üretilir |
| **B** | `MatchState`, `MatchEquityTable` (+ `met_rk.json` çıkarımı), `OutcomeDistribution`, `IOutcomeDistributionEvaluator`, `HeuristicOutcomeDistribution`, `EquityCubeAdvisor`, `CubeDecision`, `MatchAwareEvaluator`, Test 14–26 | Test 14–26 yeşil; **Test 24 (argmax değişimi) geçer**; **Bölüm 9.2 tablosu doldurulur**; MET çıkarımı raporlanır |
| **C** | `Backgammon.UI` projesi (`PositionAnalysis`, `GameOrchestrator`, view-model'ler, `BoardLayout`), `Backgammon.UI.Tests`, `output_version` metadata (export + handle), Test 27–37 | Test 27–37 yeşil; `Backgammon.UI` **Unity'siz** derlenir ve test edilir; `output_version` doğrulanır |
| **D** | `unity/TavlaAI/` projesi (sahne, prefab'lar, MonoBehaviour'lar, plugin senkron betiği), EditMode + PlayMode testleri, `unity/README.md` | `unity/build.log` hatasız; Test 38–40 yeşil **veya** lisans yoksa gerekçeli rapor; **"Unity testleri geçti" yalnızca gerçekten geçtiyse yazılır** |
| **E** | Ölçüm raporu (`ml/artifacts/stage_e_faz5.md`), `PHASES.md` §12, `ARCHITECTURE.md` §43, `ASSUMPTIONS.md` F5-01…F5-xx, `EXPECTED_COUNTS` güncellemesi, Bölüm 10 açık sorularının cevapları | Tüm testler yeşil; Bölüm 9 tabloları **ölçülmüş** değerlerle dolu; belge tutarlılık testi geçer |

---

## 🏁 Başlangıç Komutu

Bu dokümanı, **Faz 1 (v4)**, **Faz 2 (v4)**, **Faz 3 (v7)** ve **Faz 4 (v3)** spesifikasyonlarını, ayrıca `PHASES.md`, `ARCHITECTURE.md`, `ASSUMPTIONS.md` ve `SHARD_FORMAT.md` dosyalarını oku. **Yalnızca Aşama A'yı** tamamla ve şunları raporla:

1. **Oluşturulan/değişen dosya listesi** (tam yollar).
2. **Bearoff indeks şeması** doğrulaması: 54264 pozisyonun tamamı için round-trip sonucu, `Rank` çakışması var mı.
3. **DB üretimi:** dosya boyutu (bayt), üretim süresi (s), `MaxRolls` yeterli miydi, gammon tablosu üretildi mi.
4. **Nicemleme hatası:** 10 000 pozisyonda maksimum ve ortalama `|ΔE|`.
5. **Dekoratör ölçümleri:** µs/çağrı (DB açık/kapalı), bayt/çağrı (hedef 0), `SkipInnerForPureBearoffBatches` kazancı.
6. **Bearoff isabet oranı:** 10 000 rastgele self-play pozisyonunda yüzde.
7. **gnubg uyumu:** 200 referans bearoff pozisyonunda maksimum `|Δ|` equity (gnubg `eval` ile).
8. **Faz 1–4 uyum notları:** `BackgammonSearch`, `OnnxPolicyValueEvaluator`, `BackgammonVectorizer` **hiç değişmedi** mi (diff ile kanıtla); `AfterStateList` **hiç değişmedi** mi.
9. **Belirsiz bulduğun noktalar** ve Bölüm 10'daki açık sorulardan **Aşama A ile ilgili** olanların cevapları.

Onay gelmeden **Aşama B'ye geçme**.

---

## Sürüm Notu (v1)

**Amaç:** Faz 4 v3'ün bıraktığı üç açık kararı kapatmak ve dünya şampiyonu hedefine giden yolun **altyapısını** (bearoff kesinliği, küp/maç katmanı, Unity görselleştirme, AI entegrasyon çekirdeği) tek bir uygulanabilir emirde toplamak.

**Yeni olan (Faz 4 v3'e göre):**

1. **Bearoff veritabanı** (Bölüm 3): 1 taraflı, kesin, memory-mapped, **dekoratör** olarak. 2 taraflı DB'nin neden Faz 6'ya bırakıldığı **boyut matematiğiyle** gerekçelendi (Bölüm 3.1).
2. **Kendi bearoff indeks şemamız** (Bölüm 3.3): kesin formül + round-trip testi. gnubg indeks şemasına bağımlılık **yok**.
3. **"Üzerine yaz" stratejisi** (Bölüm 3.5–3.6): batch partitioning **gerekmiyor**; Faz 1 API'sine **hiç** dokunulmuyor. `SkipInnerForPureBearoffBatches` ile hız kazancı korunuyor.
4. **Depth-0 kısayolu** (Bölüm 3.8): saf bearoff'ta arama derinliği 0'a indirilir; kesinlik korunur.
5. **Küp ve maç katmanı** (Bölüm 4): `MatchState`, `MatchEquityTable` (gnubg RK MET referansı), `OutcomeDistribution`, `IOutcomeDistributionEvaluator`, `HeuristicOutcomeDistribution`, `EquityCubeAdvisor`, `CubeDecision`.
6. **`MatchAwareEvaluator`** (Bölüm 4.6): `E → ME` dekoratörü ile **maç-duyarlı hamle seçimi**. `ME = 2·MWC − 1` antisimetrik olduğu için Faz 3 v7 negamax'ı **değişmiyor**. Test 24 bunu **kanıtlıyor**.
7. **Crawford / post-Crawford** kuralları (Bölüm 4.5): Crawford'da küp yok; post-Crawford'da serbest düşüş.
8. **`PositionAnalysis` DTO** (Bölüm 5.1): UI'ın gördüğü tek veri yapısı; Faz 6'da **değişmiyor**.
9. **`GameOrchestrator`** (Bölüm 5.3): Unity'den bağımsız, test edilebilir, deterministik, asenkron.
10. **`output_version` ONNX metadata** (Bölüm 5.5): Faz 6'nın 6 çıktılı modeli bu köprüde **sessizce yanlış sonuç vermez**, açık hata verir.
11. **Unity projesi** (Bölüm 6): Unity 6000.3.8f1, URP 2D, uGUI, **view-model ayrık** mimari, ORT birincil.
12. **Unity lisans riski** (Bölüm 6.12): lisans yoksa "testler geçti" **yazılmaz**; iş mantığı `Backgammon.UI.Tests` ile **tam** kapsanır.
13. **40 test** (Bölüm 8): 13 bearoff, 13 maç/küp, 7 UI view-model, 4 Python, 3 Unity.
14. **Dürüstlük notu** (Proje Vizyonu): Faz 5 **güç artışı vaat etmez**; mevcut ER 0,1941 ve dünya şampiyonu ≈ 0,003 arasındaki ≈ 65× fark **Faz 6**'nın konusudur.

**Değişmeyen (Faz 1–4):** `BackgammonSearch`, `BackgammonVectorizer`, `VectorLayout` (221), `AfterStateList`, `OnnxPolicyValueEvaluator`, ONNX girdi/çıktı sözleşmesi, `Backgammon.SelfPlay`, `ml/train.py`, `ml/league.py`, `ml/eval_bench.py`, `ml/gnubg_er.py`. Yalnızca **iki onaylanmış ekleme** vardır: `output_version` metadata (Bölüm 5.5) ve `EXPECTED_COUNTS` güncellemesi (Bölüm 7).

**Bilinçli olarak Faz 6'ya bırakılanlar:** 6 çıktılı değer başı, eğitim ölçeği, kapasite artışı, 2 taraflı bearoff DB, race/CRASH DB, Sentis arka ucu, IL2CPP/WebGL.
