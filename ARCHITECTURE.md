# TavlaAI — Mimari Özeti (Faz 1–4)

> Bu dosya dört fazın **tasarım** belgesidir. Uçtan uca anlatım, kabul kriterleri ve
> ölçüm özetleri için `PHASES.md`; karar gerekçeleri için `ASSUMPTIONS.md`;
> shard ikili biçimi için `SHARD_FORMAT.md` kullanılır.

**Bölüm haritası**

| Bölüm | Faz | Konu |
|---|---|---|
| §1–§11 | 1 | Motor, veri modeli, yasal hamle üretimi, küp/maç akışı, fuzz, benchmark |
| §12–§18 | 2 | 221 elemanlı durum vektörü, normalizasyon, çapraz dil eşitliği |
| §19–§26 | 3 | Politika yönlendirmeli expectiminimax, ply semantiği, budama, cache |
| §27–§34 | 4 | ONNX köprüsü, ağ mimarisi, kova mekanizması, shard, eğitim hedefleri |
| §35–§37 | 4 | Self-play sürücüsü, Python eğitim laboratuvarı, Aşama C ölçümü |
| §38–§42 | 4 | Lig/model havuzu, `eval_bench`, ayar tablosu, Aşama D, gnubg ER |

Bu doküman, dört fazın (`Tavla_Motoru_Spesifikasyonu_Faz1_v4.md`,
`Tavla_Durum_Vektoru_Spesifikasyonu_Faz2_v4.md`, Faz 3 v7 ve Faz 4 v3) uygulanmış
mimarisini özetler. Belirsiz noktalarda alınan kararlar ve gerekçeleri `ASSUMPTIONS.md`
dosyasındadır; bu doküman yalnızca **ne** ve **neden** sorusuna cevap verir.

---

## 1. Katman ayrımı

```
TavlaAI_Project/
├── Backgammon.Core/          → Unity'den bağımsız, saf C# (netstandard2.1, C# 9)
│   ├── Backgammon.Core.asmdef        (Unity tarafı: noEngineReferences = true)
│   └── *.cs
├── Backgammon.Tests/         → NUnit test projesi (net10.0)
│   ├── Backgammon.Tests.asmdef       (Unity tarafı: Editor-only, test runner referanslı)
│   └── *.cs
├── tools/reference_gen.py    → Bağımsız Python referans üreteci (bkz. §9)
├── ASSUMPTIONS.md            → Belirsizlik/karar günlüğü
└── ARCHITECTURE.md           → bu dosya
```

**Kural:** `Backgammon.Core` hiçbir Unity tipine (`UnityEngine.*`, `MonoBehaviour`, `Vector3`,
`Random`) referans vermez. Bu, motorun hem Unity içinde hem de bağımsız bir sunucu/CLI
sürecinde (Faz 3/4 arama motoru) aynen kullanılabilmesini sağlar. `Backgammon.Core.asmdef`
içindeki `noEngineReferences: true` bunu Unity tarafında da zorunlu kılar.

`Backgammon.Core.csproj` bilinçli olarak muhafazakâr ayarlanmıştır:

| Ayar | Değer | Gerekçe |
|---|---|---|
| `TargetFramework` | `netstandard2.1` | Unity 2021.2+ ile uyumlu en geniş ortak payda |
| `LangVersion` | `9.0` | Unity'nin desteklediği C# sürümü |
| `Nullable` | `disable` | Unity derleyicisiyle uyum; null kontrolleri elle yapılır |
| `AllowUnsafeBlocks` | `false` | Spesifikasyon unsafe kod istemiyor; `Span`/`stackalloc` yeterli |
| `ImplicitUsings` | `disable` | Unity tarafında örtük `using` yok |

---

## 2. Veri modeli

### 2.1 `BackgammonState` — tek gerçek kaynak

`BackgammonState` bir `sealed class`'tır (struct değil): arama sırasında **kopyalanmaz**,
`ApplyStep`/`UndoStep` ile yerinde mutasyona uğratılır. Alanlar:

| Alan | Tip | Açıklama |
|---|---|---|
| `board` | `readonly sbyte[26]` | `[0]` Beyaz bar (≥0), `[1..24]` haneler, `[25]` Siyah bar (≤0) |
| `rolledDice` | `readonly byte[2]` | Atılan zarlar (duble ise iki slot aynı) |
| `remainingDice` | `readonly byte[4]` | Oynanmayan zarlar, **her zaman sıralı** |
| `remainingCount` | `int` | Oynanmayan zar sayısı (dublede 4'e kadar) |
| `whiteBorneOff` / `blackBorneOff` | `byte` | Toplanan taş sayısı |
| `turn` | `sbyte` | `+1` Beyaz, `-1` Siyah |
| `cubeValue`, `cubeOwner` | `int`, `sbyte` | Küp değeri (2'nin kuvveti) ve sahibi (`-1/0/+1`) |
| `matchLength`, `whiteScore`, `blackScore` | `int` | Maç bağlamı |
| `isCrawfordGame`, `crawfordPlayed`, `cubePassed` | `bool` | Crawford/red bayrakları |
| `phase` | `GamePhase` | Faz makinesi (§5) |
| `hash` | `ulong` | Zobrist anahtarı, **artımlı** güncellenir |

`sbyte` seçimi bilinçlidir: bir hanede en fazla 15 taş olabilir, yani `[-15, +15]` aralığı
`sbyte`'a sığar. 26 baytlık board tek bir cache satırına sığar; `AfterStateList`'te 26 baytlık
kopyalar `Array.Copy` ile tek hamlede taşınır.

### 2.2 `MoveStep` / `MoveSequence` — değer tipleri

`MoveStep` (`From`, `To`, `Die`, `Flags`) ve `MoveSequence` (`Count`, `S0..S3`) **struct**'tır ve
`readonly` alan taşımaz; böylece `MoveList` içinde bitişik dizide durur ve kopyalama maliyeti
yoktur. `MoveSequence.MaxSteps = 4` sabittir (duble üst sınırı), dolayısıyla dizi tahsisi
gerekmez.

`MoveFlags` bit alanıdır: `Hit = 1`, `BearOff = 2`, `FromBar = 4`. `BearOff` ve `Hit` asla
birlikte set edilmez (toplanan taş vurulamaz).

### 2.3 `MoveList` — önceden ayrılmış çıktı buffer'ı

`MoveList` sabit kapasiteli (`DefaultCapacity = 2048`) bir `MoveSequence[]` sarmalayıcısıdır.
`Add` kapasite aşılırsa **istisna atar** (sessiz veri kaybı yerine gürültülü hata). Üretici her
çağrıda yeni liste döndürmez; çağıran listeyi yeniden kullanır.

### 2.4 `AfterStateList` — SoA (Structure of Arrays)

Faz 2/3'ün arama katmanı, her yasal hamlenin **sonuç pozisyonunu** tek tek `BackgammonState`
kopyalayarak tutmak yerine düz dizilerde tutar:

```
Boards          : sbyte[Capacity * 26]   // tüm board'lar bitişik
WhiteBorneOff   : byte[Capacity]
BlackBorneOff   : byte[Capacity]
Hash            : ulong[Capacity]
Sequences       : MoveSequence[Capacity]
IsTerminal      : bool[Capacity]
ResultType      : byte[Capacity]         // 0 = değil, 1 = Single, 2 = Gammon, 3 = Backgammon
ResultPoints    : byte[Capacity]         // mars çarpanı; cubeValue HARİÇ
```

Neden SoA: (a) tek `Array.Copy` ile board kopyalanır, (b) arama katmanı yalnızca `Hash` ve
`ResultPoints` üzerinde tarama yaparken board verisine hiç dokunmaz (cache dostu), (c) `Swap(i, j)`
tüm alanları tutarlı biçimde takas eder (Faz 3'ün "en iyi N hamleyi öne al" optimizasyonu için).

`ResultPoints` **mars çarpanıdır** (1/2/3); `cubeValue` çarpımı çağıranın sorumluluğundadır
(Spesifikasyon 2.3b). Jacoby kuralı `EngineSettings.EnableJacoby && matchLength == 0 &&
cubeOwner == 0` iken uygulanır.

### 2.5 `StatePool`

`Rent()`/`Return()` ile `BackgammonState` geri dönüşümü. **Thread-safe değildir** — her thread
kendi havuzunu kullanır (Spesifikasyon 3'ün "paylaşımlı mutable veri yok" kuralı).

---

## 3. Sıfır-allocation stratejisi

Hot path'te (yasal hamle üretimi + afterstate üretimi) **hiçbir heap tahsisi yapılmaz**. Ölçüm:
`PerformanceTests.*_SteadyState_ZeroAllocation` → 50.000 çağrıda **0 byte**.

Bunu sağlayan mekanizmalar:

1. **Kopyalamasız DFS.** `ApplyStep` → özyineleme → `UndoStep`. State hiç kopyalanmaz.
2. **`[ThreadStatic]` scratch buffer'lar.** `LegalMoveGenerator` içinde:
   - `_stepBuf` — derinlik başına bir `MoveStep[24]` (bir zarın üretebileceği en fazla adım)
   - `_seqBuf` / `_seqHashBuf` — tek geçişli toplama buffer'ı (65536 kayıt)
   - `_dedupHash` / `_dedupIndex` / `_dedupGen` — açık adreslemeli tekilleştirme tablosu
   - `_scratchMoves` — `GenerateAfterStates`'in ara `MoveList`'i
3. **Nesil sayacı (generation counter) ile tablo temizliği.** Tekilleştirme tablosu her çağrıda
   `Array.Clear` ile sıfırlanmaz; `_gen` artırılır ve eski nesil kayıtlar "boş" sayılır. Nesil
   taşarsa (2³¹ çağrı) tablo bir kez gerçekten temizlenir.
4. **Önceden ayrılmış çıktı.** `MoveList` ve `AfterStateList` çağıran tarafından bir kez
   ayrılır, `Clear()` ile yeniden kullanılır.
5. **`in` parametreleri.** `MoveSequence`, `EngineSettings` gibi struct'lar `in` ile geçirilir.

---

## 4. Zobrist hash ve artımlı güncelleme

`Zobrist` sınıfı düz (`flat`) `ulong[]` tablolar kullanır; sabit tohum `0x9E3779B97F4A7C15UL`
ve SplitMix64 ile üretilir — yani tablolar **deterministiktir** ve süreçler arasında aynıdır
(Faz 3'ün cache'i diske yazılabilsin diye).

Hash kapsamı (Spesifikasyon 2.1):

| Dahil | Hariç |
|---|---|
| `board[0..25]` (barlar dahil) | `rolledDice`, `remainingDice`, `remainingCount` |
| `whiteBorneOff`, `blackBorneOff` | `phase` |
| `turn` | `matchLength`, skorlar, Crawford bayrakları, `cubePassed` |
| `cubeValue` (log2 indeksi), `cubeOwner` | |

`turn == -1` iken `TurnKey` XOR'lanır, `+1` iken hiçbir şey XOR'lanmaz — böylece `EndTurn`
**her zaman** `TurnKey` XOR'layabilir.

**Değişmez kural:** her mutasyondan sonra `state.hash == ComputeZobristHash(state)`.
Bu, `SanityCheck` maddesi 7 ile Debug'da her adımda doğrulanır ve testlerde
`AssertHashConsistent` yardımcısıyla ayrıca kontrol edilir.

`MirrorTo` hash'i **tam yeniden hesaplar** (artımlı değil) — hot path'te değildir ve
`dst.board[i] = -src.board[25 - i]` dönüşümü artımlı XOR ile ifade edilemez.

---

## 5. Faz makinesi

```
  ┌──────────────────────┐
  │ DetermineFirstPlayer │  RollOpening
  └──────────┬───────────┘
			 ▼
  ┌──────► PreRoll ◄──────────────────┐
  │   (küp teklifi serbest)           │
  │                                   │
  │ OfferDouble          EndTurn      │
  ▼                      (CanOffer)   │
CubeOffered ──Take──► WaitForRoll ────┤
  │                        │          │
  │ Pass                   │ RollDice │
  ▼                        ▼          │
GameOver                 Moving ──────┘
					(ApplyMove → GameOver olabilir)
```

- `phase = GameOver` geçişinin **tek yeri** `ApplyMove`'un sonudur (Spesifikasyon 4.6) — buna ek
  olarak küp reddi (`Pass`) doğrudan `GameOver` yapar ve `cubePassed = true` işaretler.
- `EndTurn`, `PassTurn` ve `LoadAfterState` **asla** `GameOver` yapmaz.
- `LoadAfterState` önkoşulu: `dst.turn` zaten hamleyi yapan oyuncudur; metot `turn`'ü değiştirmez.

---

## 6. Yasal hamle üretimi

`LegalMoveGenerator` iki genel API sunar:

```csharp
static void GenerateAllLegalMoves(BackgammonState s, MoveList output);
static void GenerateAfterStates(BackgammonState s, in EngineSettings es, AfterStateList output);
```

İkisi **aynı kümeyi ve aynı sırayı** üretir (Spesifikasyon 7); `GenerateAfterStates` pratikte
`GenerateAllLegalMoves`'un çıktısını adım adım uygulayıp `AfterStateList`'e yazar.

### 6.1 Algoritma — tek geçişli DFS + tekilleştirme

1. `remainingDice` üzerinde DFS; her düğümde `GenerateSteps` o zar için yasal adımları üretir.
2. DFS sırasında **en uzun** diziler `_seqBuf`'a toplanır. Daha derin bir dizi bulunursa buffer
   sıfırlanır (`count = 0`) — böylece sonuçta yalnızca maksimum uzunluktaki diziler kalır
   (Spesifikasyon 5.1 madde 1 ve 5.4).
3. Maksimum uzunluk belirlendikten sonra **büyük zar kuralı** uygulanır: yalnızca tek zar
   oynanabiliyorsa ve büyük zar oynanabiliyorsa, yalnızca büyük zarı kullanan diziler tutulur.
4. Kalan diziler **hash tabanlı** tekilleştirilir: aynı sonuç pozisyonuna götüren dizilerden
   yalnızca biri (kanonik olan) yazılır.
5. `_seqBuf` taşarsa (65536 kayıt) davranış birebir aynı kalmak üzere klasik iki geçişli yola
   (`Emit`) düşülür.

### 6.2 Kural uygulama noktaları

| Kural | Yer |
|---|---|
| Bar önceliği (barda taş varsa yalnızca giriş) | `GenerateSteps` başı |
| Bloke hane (`CanLand`) | `GenerateSteps` |
| Vurma (`IsBlot` → `MoveFlags.Hit`) | `GenerateSteps` |
| Toplama modu (`IsBearOffMode`) | `GenerateSteps`, her çağrıda yeniden hesaplanır |
| "Geride taş varken toplama yasağı" (`HasPieceFurtherBack`) | `GenerateSteps` |
| Maksimum zar kuralı | `Collect` (en uzun dizi filtresi) |
| Büyük zar kuralı | `ResolveBigDieRestriction` |
| Tekilleştirme | `Record` + `IsCanonicallyBefore` |

`IsBearOffMode` her `GenerateSteps` çağrısında yeniden hesaplanır (karar C-05): toplama modu bir
hamle içinde **açılabilir** (son ev dışı taş eve girince) veya **kapanabilir** (taş vurulup bara
gidince), dolayısıyla düğüm başında bir kez hesaplanması yanlış olur.

### 6.3 Determinizm

Aynı girdi (board + zar + turn) her zaman **aynı sırada** aynı çıktıyı üretir:

- `remainingDice` sıralı tutulur, DFS bu sırayla gezer.
- Tekilleştirmede aynı hash'e düşen dizilerden kanonik olanı `(From, To, Die)` sözlük sırasına
  göre seçilir (`IsCanonicallyBefore`).
- Hiçbir yerde `Dictionary`, `HashSet` veya `object.GetHashCode()` kullanılmaz (bunların
  enumerasyon sırası çalıştırmalar arasında değişebilir).

---

## 7. Rastgelelik

`IRandom` arayüzü (`NextUInt()`, `RollDie()`) iki uygulama ile gelir:

| Sınıf | Kullanım | Özellik |
|---|---|---|
| `Xoshiro256StarStar` | Arama, fuzz, tekrar üretilebilir simülasyon | `ulong` tohum, SplitMix64 ile başlatma, reddetme örneklemesi ile tarafsız `RollDie` |
| `CryptoRandom` | Gerçek oyun zarı | 256 baytlık tamponlu `RandomNumberGenerator`, `IDisposable` |

`RollDie()` **reddetme örneklemesi** kullanır (`NextUInt() % 6` değil): modulo yanlılığı
deterministik simülasyonlarda ölçülebilir sapma yaratır.

---

## 8. Test stratejisi

| Dosya | Kapsam |
|---|---|
| `BackgammonStateTests`, `MoveStructureTests`, `CoordinateTests` | Veri yapıları, koordinat yardımcıları |
| `ZobristTests` | Hash tanımı, `MirrorTo` simetrisi, artımlı = tam |
| `SanityCheckTests` | `SanityCheck` maddelerinin gerçekten yakaladığı |
| `EngineFlowTests` | `ApplyStep`/`UndoStep`, `ApplyMove`/`UndoMove`, `SetDice`, `LoadAfterState`, `EndTurn` |
| `LegalMoveGeneratorTests` | Elle yazılmış uç durumlar (bar, bloke, maksimum zar, büyük zar, duble 4/3/2/1, toplama, toplama modunun açılması/kapanması, Beyaz **ve** Siyah) + **brute-force referans karşılaştırması** (1000+ rastgele pozisyon) + simetri |
| `CubeAndMatchTests` | Küp, Crawford, Jacoby, mars, maç akışı |
| `ReferenceComparisonTests` | **Bağımsız Python referansı** ile 57 pozisyon / 927 sonuç pozisyonu |
| `FuzzTests` | Seed'li oyun fuzz'ı (varsayılan 2.000, `[Explicit]` 1.000.000) + maç akışı fuzz'ı |
| `PerformanceTests` | Hız, allocation, çok çekirdekli ölçeklenme |

**Bağımsız doğrulama katmanı.** `LegalMoveGenerator` iki ayrı bağımsız kaynakla karşılaştırılır:

1. `LegalMoveGeneratorTests` içindeki **brute-force referans üreteci** — aynı projede ama
   tamamen farklı bir algoritma (dizi listesi + sonuç pozisyonu kümesi, tekilleştirme tablosu yok).
2. `tools/reference_gen.py` — **farklı dilde** (Python) bağımsız uygulama; çıktısı
   `ReferenceData/reference_positions.json` olarak sabitlenmiştir.

---

## 9. Spesifikasyon Bölüm 7 kontrol listesi

| Gereksinim | Durum | Yer |
|---|---|---|
| `SetDice(state, d1, d2)`: RNG'siz, `phase = Moving`, dublede 4 zar, sıralı | ✅ | `BackgammonEngine.SetDice` |
| `AfterStateList` (SoA) tüm alanlar + `Swap` + `AddPass` | ✅ | `AfterStateList.cs` |
| `GenerateAfterStates` ile `GenerateAllLegalMoves` aynı küme/sıra | ✅ | `LegalMoveGenerator.cs`, test: `AfterStateListTests` |
| Afterstate hash'i `turn` ve küp bilgisini içerir, zar içermez | ✅ | `Zobrist.cs`, test: `ZobristTests` |
| `LoadAfterState` + `EndTurn` | ✅ | `BackgammonEngine.cs` |
| `IsGameOver(state, out GameResult)`, Jacoby uyumlu, `Points` cubeValue hariç | ✅ | `BackgammonEngine.IsGameOver` |
| `MirrorTo`, `CopyFrom`, `ComputeZobristHash` | ✅ | `BackgammonEngine.cs` |
| `DistanceToOff`, `IsHome`, `BarIndex` herkese açık | ✅ | `BackgammonEngine.cs` |
| `state.hash` her mutasyondan sonra `ComputeZobristHash` ile eşit | ✅ | `SanityCheck` madde 7 + testler |
| `ApplyStep`/`UndoStep` tam sözde kod uyumu | ✅ | `BackgammonEngine.cs` |
| `AfterStateList.ResultPoints` Jacoby uygulanmış, `cubeValue` hariç | ✅ | `LegalMoveGenerator.GenerateAfterStates` |

---

## 10. Ölçülen performans (Release, tek çekirdek)

| Ölçüm | Spesifikasyon hedefi | Ölçülen |
|---|---|---|
| `GenerateAllLegalMoves` (orta oyun, 21 hamle) | ≥ 300.000 çağrı/sn | **~480.000 çağrı/sn** (≈ 2,1 µs) |
| `GenerateAfterStates` (orta oyun, 21 afterstate) | ≥ 300.000 çağrı/sn | **~340.000 çağrı/sn** (≈ 2,9 µs) |
| Rastgele oyun hızı | ≥ 5.000 oyun/sn/çekirdek | **~1.700 oyun/sn/çekirdek** (revize: 1.000, bkz. E-03) |
| Rastgele oyun hızı (12 thread) | — | **~9.200 oyun/sn** toplam |
| Steady-state allocation | 0 byte | **0 byte** / 50.000 çağrı |

Hedef revizyonlarının gerekçesi `ASSUMPTIONS.md` E-02 ve E-03'te.

---

## 11. Faz 2-4 için notlar

- **Faz 2 (değerlendirme):** `AfterStateList` doğrudan tüketilebilir; `Hash` alanı cache
  anahtarıdır, `ResultPoints` terminal kayıtlarda nihai skoru verir.
- **Faz 3 (arama):** `StatePool` + `LoadAfterState` + `EndTurn` üçlüsü, ağaç düğümlerini
  kopyalamadan ilerletmeyi sağlar. `MirrorTo` ile "sıradaki oyuncu hep +1" perspektifi elde
  edilir; bu, aynı pozisyonun iki perspektifte iki kez değerlendirilmesini önler.
- **Faz 4 (paralel):** Paylaşımlı mutable veri yoktur; her thread kendi `BackgammonState`,
  `MoveList`, `AfterStateList` ve `IRandom` örneğini kullanır. `[ThreadStatic]` scratch
  buffer'lar bunu otomatik olarak sağlar.

---

# Tavla Motoru — Faz 2 (Durum Vektörü) Mimari Özeti

Faz 2, Faz 1 motorunun ürettiği `AfterStateList` kayıtlarını **221 nöronluk sabit boyutlu
bir `float` vektörüne** dönüştürür. Ağ mimarisi, eğitim ve arama bu fazın kapsamı dışındadır
(spesifikasyon Bölüm 7).

## 12. Katman ve dosya yerleşimi

| Dosya | Sorumluluk |
|---|---|
| `Backgammon.Core/VectorLayout.cs` | 221 nöronun **tüm** indeks sabitleri; `ActivePointIndex(j,k)`, `OppPointIndex(j,k)` |
| `Backgammon.Core/VectorizerScalars.cs` | `readonly struct` — 6 skaler alan + `From(state)` |
| `Backgammon.Core/BackgammonVectorizer.cs` | `Vectorize` (2 aşırı yükleme), `VectorizeBatch`, yardımcı fonksiyonlar, doğrulama |
| `Backgammon.Tests/VectorTestSupport.cs` | Test yardımcıları (pozisyon kurma, çözme, bit karşılaştırma) |
| `Backgammon.Tests/VectorGoldenData.cs` | Altın JSON şeması + üretim yardımcısı |
| `Backgammon.Tests/VectorizerTests.cs` | Bölüm 5'in 12 test grubu (22 test) |
| `Backgammon.Tests/ReferenceData/vector_golden.json` | 500 kayıtlık çapraz dil altın dosyası |
| `tools/vector_verify.py` | **Bağımsız** Python (numpy `float32`) doğrulayıcı |

`BackgammonVectorizer` **statiktir** ve **durum tutmaz**; `BackgammonState`'i değiştirmez,
`ComputeZobristHash` çağırmaz (spesifikasyon Bölüm 6, E4).

## 13. Vektör haritası (221 nöron)

```
  0 ..  95   Aktif oyuncu hane bloğu      (24 hane x 4 nöron)
 96 .. 191   Rakip hane bloğu             (24 hane x 4 nöron)
192          ActiveBar      = aktifBar / 2
193          OppBar         = rakipBar / 2
194          ActiveOff      = aktifToplanan / 15
195          OppOff         = rakipToplanan / 15
196          CubeOwner      = cubeOwner * perspective
197          CubeValue      = min(log2(cubeValue) / 6, 1)
198          IsMoneyGame    = (matchLength == 0)
199          IsCrawford     = isCrawfordGame
200          ActivePip      = aktifPip / 167
201          OppPip         = rakipPip / 167
202          ActiveEscaped  = aktifKaçak / 15
203          OppEscaped     = rakipKaçak / 15
204          IsContact      = (aktifMaxJ > jOppMin)
205 .. 212   ActiveAway[0..7]  one-hot
213 .. 220   OppAway[0..7]     one-hot
```

### 13.1 Hane bloğu (4 nöron)

`j = DistanceToOff(point, perspective)` (1 = toplamaya en yakın, 24 = en uzak),
`k = 0..3`, indeks `blockOffset + 4*(j-1) + k`:

| `k` | Ad | Değer |
|---|---|---|
| 0 | `Blot` | `N == 1` |
| 1 | `Gate` | `N >= 2` |
| 2 | `ThreePlus` | `N >= 3` |
| 3 | `Density` | `N > 3 ? (N-3)/2f : 0` |

**Kritik:** rakip bloğu da **aynı `j` çerçevesini** kullanır — rakip kendi çerçevesine
çevrilmez (spesifikasyon Bölüm 1.2). Bu sayede `Vectorize(s, -p)` çağrısı aktif/rakip
bloklarını yer değiştirir ve hane sırasını tersine çevirir (Bölüm 5 madde 3).

Bar taşları hane bloklarına **girmez**; yalnızca `ActiveBar`/`OppBar` nöronlarında görünür.

### 13.2 Yardımcı tanımlar (Bölüm 3)

| Fonksiyon | Tanım |
|---|---|
| `CalculatePipCount` | `Σ n·DistanceToOff(p, player)` (p = 1..24) + `bar·25`. Başlangıç 167, en fazla 375 |
| `jOppMin` | Rakip barda taş varsa `0`; tahtada taşı yoksa `+∞`; aksi halde `min DistanceToOff(p, perspective)` |
| `aktifMaxJ` | Aktif barda taş varsa `25`; tahtada taşı yoksa `0`; aksi halde `max j` |
| `GetEscapedCheckersCount` | `j < jOppMin` olan tahtadaki taşlar (bar ve toplanmış sayılmaz) |
| `IsContact` | `aktifMaxJ > jOppMin` — perspektiften bağımsız, simetrik |

## 14. Normalizasyon ve bit-düzeyi sözleşmesi

* Tüm aritmetik **`float` (float32)** ve **tek bölme** ile yapılır: `pip / 167f`,
  `bar / 2f`, `escaped / 15f`, `log2 / 6f`. `* (1f/167f)` **kullanılmaz** — float32'de
  yuvarlama farklı olur ve C#/Python bit eşitliği bozulur (spesifikasyon Bölüm 1.3).
* Bilinçli doygunluk yalnızca iki yerde: `CubeValue` (`min(.,1)`) ve away one-hot kovalama.
* `Math.Log2` / `BitOperations.Log2` **kullanılmaz**; `log2` tamsayı bit-kaydırma döngüsüyle
  hesaplanır (F2-15). Böylece 2'nin kuvveti olmayan küp değerleri de deterministiktir.
* `Vectorize` **ilk 221 elemanın tamamını** yazar (kirli buffer'a güvenilmez) ve 221'in
  ötesine **dokunmaz** (Bölüm 5 madde 6).

## 15. Terminal ve maç-bitişi reddi (Bölüm 4.1)

`Vectorize`, `Vectorize(board, ...)` ve `VectorizeBatch` şu durumlarda `ArgumentException`
fırlatır:

1. `borneOff == 15` (oyun bitmiş),
2. `matchLength > 0 && away <= 0` (maç bitmiş),
3. `VectorizeBatch` için ayrıca `list.IsTerminal[i] == true`.

`Debug.Assert(false)` **kullanılmaz** — VS test host'u `Debug.Fail`'i `DebugAssertException`'a
çevirip `ArgumentException`'dan önce attığı için sözleşmeyi bozar (F2-10).

## 16. Çapraz dil eşitliği

`ReferenceData/vector_golden.json` şeması (spesifikasyon Bölüm 5 madde 11):

```json
{
  "featureVersion": 1,
  "vectorSize": 221,
  "generatedBy": "Faz 2 v4 test suite",
  "records": [
    { "board": [26 int], "whiteBorneOff": int, "blackBorneOff": int,
      "cubeValue": int, "cubeOwner": int, "matchLength": int,
      "whiteScore": int, "blackScore": int, "isCrawfordGame": bool,
      "perspective": int, "vectorHex": "221 uint32 hex, virgülle ayrılmış" }
  ]
}
```

* Üretim: `[Explicit]` test `GenerateCrossLanguageGolden` → `VectorGoldenData.Write`.
  500 kayıt, seed `0x2F2600D5EEDUL`.
* Doğrulama: `CrossLanguageGolden_FileMatches` (C# tarafı) + `tools/vector_verify.py`
  (bağımsız Python/numpy `float32` tarafı). Son ölçüm: **500 × 221 nöron birebir eşleşti**.
* `FeatureVersion` artırılmadan vektör düzeni **değiştirilemez**; altın dosya da yeniden
  üretilmelidir.

## 17. Ölçülen performans (Release, tek çekirdek)

| Ölçüm | Spesifikasyon hedefi | Ölçülen |
|---|---|---|
| `Vectorize` (state) | ≥ 2.000.000 çağrı/sn | **~3.650.000 çağrı/sn** (≈ 0,27 µs) |
| `VectorizeBatch` | raporla | **~3.100.000 kayıt/sn** |
| Steady-state allocation | 0 byte | **0 byte** / 10.000 çağrı (3 API) |

Çağrı başına iş yükü çok küçük olduğu için `PerformanceTests` iki testte **en iyi 3 turun**
hızını ölçer (`MeasureBestOf`); gerekçe `ASSUMPTIONS.md` F2-20.

## 18. Test durumu

> **Tarihsel kayıt.** Bu tablo Faz 2 tamamlandığındaki durumu gösterir. Güncel sayılar için
> `PHASES.md` §6 ve bu dosyanın §34'üne bakın.

| Derleme | Toplam | Geçti | Başarısız |
|---|---|---|---|
| Debug | 169 | **169** | 0 |
| Release | 194 | **194** | 0 |

Release'te 6 test eksik görünür: `[Conditional("DEBUG")]` işaretli `SanityCheck`/`DebugAssert`
çağrı yerleri Release'te derlenmez. Bu beklenen farktır (Faz 1'den beri aynı).

---

# Faz 3 — Politika Yönlendirmeli Expectiminimax Arama

## 19. Katman ve dosya yerleşimi

`Backgammon.Core\Search\` altında, Faz 1 ve Faz 2'ye **hiç dokunmadan**:

| Dosya | Sorumluluk |
|---|---|
| `IEvaluators.cs` | `IPositionEvaluator`, `IPolicyEvaluator`, `IPolicyValueEvaluator`, `ICombinedBatchEvaluator`, `ICubeEvaluator`/`NullCubeEvaluator`, `ICubePolicyEvaluator`/`NullCubePolicyEvaluator` |
| `RollSet.cs` | 21'lik normal zar kümesi (ağırlık toplamı 36) ve 15'lik açılış kümesi; `RemainingWeightAfter` Star1 için |
| `SearchSettings.cs` | `DepthPly`, aday kısıtları, budama/cache/politika anahtarları, `PolicyTemperature`; `Default` ve `Reference(depth)` |
| `SearchResult.cs` | `RootCandidate` (salt-okunur struct) ve `ref struct SearchResult` |
| `SearchWorkspace.cs` | Ply başına önceden ayrılmış state/liste/skor/sıra tamponları, kök tamponları, doğrudan eşlemeli eval cache |
| `BackgammonSearch.cs` | `Search`, `AnalyzePreRoll`, `SearchNode`, `ChanceNode` ve yardımcılar |

**Bağımlılık yönü:** `Search` → `LegalMoveGenerator` (Faz 1), `BackgammonEngine` (Faz 1),
`VectorizerScalars` (Faz 2). Faz 1/2, Faz 3'ü **bilmez**. Ağ (Faz 4) yalnızca arayüzleri uygular.

## 20. Değer sözleşmesi ve negamax

* Değer = **küpsüz (cubeless) para equity'si**, küp değeri 1'e normalize, aralık `[L, U] = [-3, +3]`.
* Her değer **hamleyi yapan** oyuncunun (mover) gözündendir. Çocuk düğümün değeri üst düğüme
  `-v` olarak döner (negamax). `turn` çevrildiği için perspektif otomatik döner.
* **Kırpma sahipliği:** değerlendirici `[-3,3]`'e kırpmaz, yalnızca `float.IsFinite` doğrular.
  Kırpma **aramanın** sorumluluğundadır (`ClampInPlace`). Bu ayrım, `ReferenceSearch` ile gerçek
  aramanın **aynı sayıda** kırpma uygulamasını garanti eder (Test 1).
* Terminal değer: `list.ResultPoints[i] / cubeValue` — `AfterStateList`'ten **doğrudan** okunur,
  değerlendiriciye hiç gidilmez.

## 21. Ply semantiği ve düğüm yerleşimi

`depthPly` = **chance (zar) katmanı** sayısı. `0` = afterstate'ler doğrudan değerlendirilir;
`1` = her aday için rakibin 21 zarı üzerinden ağırlıklı ortalama.

```
node = 2·(DepthPly − d)      max düğümü
node + 1                     o düğümün chance çalışma state'i
node + 2                     alt max düğümü
```

`MaxSupportedPly = 4` → `MaxNodes = 10`, en büyük indeks 8. Her düğümün **kendi**
`AfterStateList`'i, `staticScores`, `policyScores`, `candidateOrder`, `kinds` tamponu vardır;
üst düğümün listesi alt düğüm tarafından bozulmaz (undo yerine ply başına kopya).

Alt düğüme geçiş sırası **sabittir** (Faz 1 v4 §4.5 önkoşulu):

```
dst.CopyFrom(parent) → LoadAfterState(dst, list, i) → EndTurn(dst) → SetDice(dst, d1, d2)
```

## 22. Aday üretimi, bölümleme ve sıralama

1. `LegalMoveGenerator.GenerateAfterStates(s, es, list)` — Faz 1 ile **aynı** küme ve sıra.
   Liste boşsa `list.AddPass(s)` (pas afterstate'i; hash `s.hash` ile **aynıdır**).
2. **Terminal bölümleme (zorunlu):** `PartitionNonTerminal` kararlı `Swap` ile
   terminal-olmayanları başa taşır. `VectorizeBatch` terminal kayıt görünce
   `ArgumentException` attığı için bölümleme **kod düzeyinde zorlanır**.
3. **Politika yolu** (`UsePolicyOrdering && policy != null && nonTerminal > 1`):
   `ScoreBatch` → negatifler 0'a kırpılır (**yeniden normalize edilmez**, softmax ağın işi).
   Terminal-olmayanlar önceliğe göre azalan (kararlı), terminal adaylar **sonda**
   (`ResultPoints` azalan).
4. **Statik yol:** `EvaluateBatch` → terminal adaylar **başta** (`ResultPoints` azalan),
   terminal-olmayanlar statik skora göre azalan.
5. Sıralama **indeks dizisi üzerinde insertion sort** (kararlı, allocation'sız).
6. `MaxCandidatesRoot/Inner > 0` ise politika sırasına göre ilk `K` aday derin aranır;
   kalanlar `Kind = 2` olur, **`best` karşılaştırmasına girmez**. Kökte `Score` = statik `Eval0`,
   `PolicyTarget = 0`. İç düğümlerde tamamen atlanır (statik çağrı bile yapılmaz).

`ICombinedBatchEvaluator` çağrı noktaları **sabittir** (spec §3.3 adım 5): kökte
`MaxCandidatesRoot > 0` iken `EvaluateAndScoreBatch`; yapraklarda yalnızca `EvaluateBatch`;
iç max düğümlerinde yalnızca `ScoreBatch`. Tip kontrolü **arama başında bir kez** yapılır.

## 23. Budama

### 23.1 Alfa-beta (fail-soft)

`UseAlphaBeta = true` iken her aday `(max(best, α), β)` penceresiyle aranır; `best >= β` olunca
döngü kırılır. Kökte **erken kesme yapılmaz** (`RootCandidates` tüm adaylar için dolu kalmalı);
pencere yine daraltılır. `ExactRootScores = true` iken kökte her aday `(L, U)` ile aranır ve
kesme yapılmaz — politika hedefi için **kesin** `Q` gerekir.

### 23.2 Star1 (chance düğümü budaması)

`q_r ∈ [L, U]` olduğu için kalan zarların katkısı `[R·L, R·U]` aralığındadır. `S` = o ana kadarki
ağırlıklı toplam, `w` = zarın ağırlığı, `R = RemainingWeightAfter[r]`:

```
A = (36α − S − R·U) / w        B = (36β − S − R·L) / w
A >= U  →  (S + (w+R)·U) / 36
B <= L  →  (S + (w+R)·L) / 36
α_c = −min(B, U)               β_c = −max(A, L)
q <= A  →  (S + w·q + R·U) / 36
q >= B  →  (S + w·q + R·L) / 36
```

`UseStar1 = false` iken çocuklara tam pencere verilir ve 21 zarın tamamı işlenir.

## 24. Kök politika hedefi (Faz 4 eğitimi için)

`ExactRootScores = true` iken `RootPolicyTarget` doldurulur: `π(a) = softmax(Q(a)/τ)`, yalnızca
`Kind ∈ {0, 1}` adaylar için; `Kind = 2` → `0`. Sayısal kararlılık için `max(Q)` çıkarılır.
`τ <= 0` → `ArgumentException`. `ExactRootScores = false` iken `RootPolicyTarget.Length == 0`
(boş span, `null` değil). Hiç yasal hamle yoksa `IsPass = true` ve hedef boştur.

**Terminal adaylar (`Kind = 0`) softmax'a girer** (`PolicyTarget > 0`), ancak Faz 4 politika
cross-entropy'sinde **hariç tutulur**: politika ağı terminal adaylar için hiç çağrılmaz, ağın
çıktısı tanımsızdır. `Kind = 2` adaylar da hariç tutulur (aranmadılar).

## 25. Eval cache

* Doğrudan eşlemeli, "her zaman değiştir", `2^cacheBits` giriş (varsayılan `2^20`).
* Anahtar: afterstate Zobrist hash'i `^ depth` (+ ayar imzası). Değer: **yalnızca kesin** `Q`.
  Budanmış (sınır) değerler asla yazılmaz.
* `EnsureCacheConsistent(evaluator.Version, SettingsSignature(ss))` yalnızca **değeri** etkileyen
  değişimde cache'i temizler. `SettingsSignature = MaxCandidatesInner·2 | (UsePolicyOrdering ? 1 : 0)`.
* **Politika `Version`'ı cache anahtarına girmez ve cache'i temizlemez** (politika yalnızca sırayı
  etkiler, `Q`'yu etkilemez).
* `Search`/`AnalyzePreRoll` başında `BeginSearch()` çağrılır: istatistikleri ve kök tamponlarını
  sıfırlar, **cache'i korur**. `Reset()` ise cache'i **kesinlikle** temizler (model yeniden
  yükleme sonrası zorunlu — Test 17).

## 26. Determinizm

* Aynı `(state, ayarlar, değerlendirici, politika)` → **aynı sonuç** (tekrar, farklı thread,
  farklı workspace).
* Aday sırası, tie-break (eşitlikte düşük indeks) ve zar sırası sabittir.
* Cache açık/kapalı ve `UsePolicyOrdering` açık/kapalı **değeri değiştirmez**; yalnızca hızı
  değiştirir. Arama içinde RNG kullanılmaz.
---

# Faz 4 — Sinir Ağı, ONNX Köprüsü, Self-Play ve Eğitim Laboratuvarı

## 27. Katman haritası

```
┌──────────────────────────────────────────────────────────────────────┐
│  ml/  (Python, PyTorch)                                              │
│  model.py  export_onnx.py  shards.py  td_lambda.py  losses.py        │
│  gen_golden_outputs.py  gen_test_models.py  tests/                   │
└───────────────┬──────────────────────────────────────────────────────┘
                │  model_v1.onnx + metadata + parity.json
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Backgammon.Inference  (netstandard2.1, ORT 1.23.2)                  │
│  OnnxEvaluatorOptions  OnnxModelHandle  OnnxPolicyValueEvaluator     │
└───────────────┬──────────────────────────────────────────────────────┘
                │  IPositionEvaluator + IPolicyEvaluator + ICombinedBatchEvaluator
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Backgammon.Core  (Faz 1–3)                                          │
│  BackgammonSearch  SearchWorkspace  BackgammonVectorizer             │
└───────────────┬──────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Backgammon.SelfPlay  (net10.0 Exe)                                  │
│  ShardFormat  ShardModel  ShardWriter  ShardReader  Program          │
└───────────────┬──────────────────────────────────────────────────────┘
                │  *.bgsp / *.bgsp.gz
                ▼
        ml/shards.py  →  replay.py  →  train.py
```

`Backgammon.Core` **hiçbir** ONNX/PyTorch bağımlılığı taşımaz; ağ erişimi tamamen
`Backgammon.Inference` içindedir. Bu, Faz 1'den beri korunan "motor Unity-bağımsız ve
sıfır-tahsis" ilkesinin devamıdır.

## 28. Ağ mimarisi ve ONNX sözleşmesi

* Gövde: `Linear(221,128) → GELU → Linear(128,64) → GELU`.
* `value_head = Linear(64,1)`, **bias sıfır, lineer** (kırpma yok).
* `policy_head = Linear(64,1)` — aday başına **tek logit**; **ağ içinde softmax yok**.
* Girdi `features` `[B,221]` float32; çıktılar `value` `[B,1]`, `policy_logit` `[B,1]`.
* **Batch ekseni üç tensörde de dinamik olmak zorundadır.**
* `opset_version = 15`.
* Metadata: `feature_version`, `vector_size`, `model_version`, `arch`, `trained_by`.

Grup softmax'ı iki yerde uygulanır ve **ikisi de aynı sonucu vermelidir**:
`OnnxPolicyValueEvaluator.ScoreBatch` (C#, çıkarım) ve `ml/losses.py` (Python, eğitim).
`ml/tests/test_tau_crosscheck.py` bu iki uygulamayı aynı `Q`/`τ` üzerinde karşılaştırır.

## 29. Değerlendirici: kova (bucket) mekanizması

* Kovalar `1, 2, 4, 8, …, MaxBatch` (ikinin kuvvetleri, `MaxBatch = 2048`).
* Girdi tamponu kovaya göre **sıfırla doldurulur**; ORT'a kova boyutu bildirilir; yalnızca
  ilk `count` satır kullanılır. Sıfır dolgu çıktıyı etkilemez çünkü satırlar bağımsızdır.
* `OrtValue.CreateTensorValueFromMemory(OrtMemoryInfo, Memory<T>, long[] shape)` +
  `OrtIoBinding` yolu kullanılır. Binding'ler ve tamponlar **kurucuda bir kez** ayrılır.
* Ölçüm: **tüm kovalarda 0 bayt/çağrı** (bkz. `ASSUMPTIONS.md` F4-13). Varsayılan
  `session.Run(NamedOnnxValue)` yolu 1 401–1 472 bayt/çağrı tahsis eder.
* Sabit maliyet ~12 µs; 2048 kovada ~1,83 ms (≈547 çağrı/s).

### 29.1 Aşama B: nihai uygulama ayrıntıları

* **Kova tablosu:** `MaxBatch` ikinin kuvvetine yuvarlanır (`log2` + 1 kova). Her kova için
  `float[] Input` (`size * 221`), `float[] ValueOut` (`size`), `float[] PolicyOut` (`size`),
  üç `OrtValue` ve bir `OrtIoBinding` **yapıcıda** ayrılır.
* **`GC.AllocateArray` yok:** `netstandard2.1` hedefinde mevcut değil (CS0117). Düz dizi
  kullanılır; ORT `Memory<T>`'yi `OrtValue` ömrü boyunca sabitler → çağrı başına tahsis 0.
* **Dolgu temizliği:** `Bucket.DirtyRows` izlenir; önceki çağrı daha büyük `count`
  kullandıysa kuyruk `Array.Clear` ile sıfırlanır.
* **Tek çalıştırma:** `SynchronizeBoundInputs` → `RunWithBinding` → `SynchronizeBoundOutputs`.
  Her çağrıda **her iki** çıktı da hesaplanır; yalnızca istenen doldurulur.
* **CUDA'da girdi yeniden baglanir:** `OrtIoBinding.BindInput` CPU->cihaz kopyasini bind
  aninda yaptigi icin, CUDA oturumlarinda tampon doldurulduktan sonra
  `ClearBoundInputs()` + `BindInput()` cagrilir (bkz. 29.3). CPU EP'de atlanir.
* **Parçalama:** `count > MaxBatch` → `MaxBatch`'lik parçalar. Değerler doğrudan yazılır;
  politika logitleri `_logits` tamponunda toplanıp softmax **tüm `count` üzerinde bir kez**
  uygulanır (grup softmax parçalanamaz). `_logits` yalnızca bu yolda ve yalnızca büyüdüğünde
  ayrılır.
* **`SetModel`:** yeni oturum → **kova tablosu yeniden kurulur** (eski bağlamalar/tanıtacılar
  `Dispose`). Bu yüzden yalnızca boştayken çağrılabilir.
* **`Dispose`:** tüm `OrtValue`/`OrtIoBinding`/`RunOptions` serbest bırakılır; idempotent.

### 29.2 Ölçüm (spec v3 §4.6)

`ml/artifacts/inference_benchmark.txt` (`InferenceBenchmark`, `[Explicit]`).
ORT 1.23.2, `IntraOpThreads = 1`, `InterOpThreads = 1`, `use_tf32 = 0`,
12 mantıksal çekirdek, **NVIDIA GeForce GTX 1650 (4 GB, sürücü 580.88)**:

| Kova | CPU µs | CPU poz/s | CUDA µs | CUDA poz/s | Kazanan |
|---|---|---|---|---|---|
| 1 | 13,79 | 72 516 | 194,62 | 5 138 | CPU (14×) |
| 8 | 20,03 | 399 421 | 185,67 | 43 088 | CPU (9×) |
| 32 | 61,68 | 518 811 | 219,45 | 145 819 | CPU (3,6×) |
| 128 | 176,72 | 724 302 | 295,30 | 433 457 | CPU (1,7×) |
| 512 | 727,05 | 704 219 | 573,57 | 892 652 | **CUDA (1,3×)** |
| 2048 | 2 820,78 | 726 041 | 1 650,01 | 1 241 204 | **CUDA (1,7×)** |

**Kesişme noktası kova 128 ile 512 arasındadır.** CUDA EP'nin sabit çekirdek başlatma
gecikmesi ~180 µs olduğundan küçük batch'lerde CPU belirgin şekilde öndedir; CPU EP ise
128 ve üzerinde ~725 000 pozisyon/s'de doyuma ulaşır (tek çekirdek).

**CPU↔CUDA çıktı paritesi** (tolerans 1e-4; `InferenceBenchmark` bunu doğrular):

| Kova | max abs Δvalue | max abs Δpriority |
|---|---|---|
| 1 | 5,588E-009 | 0,000E+000 |
| 8 | 1,118E-008 | 1,490E-008 |
| 32 | 1,863E-008 | 1,863E-009 |
| 128 | 2,235E-008 | 9,313E-010 |
| 512 | 2,980E-008 | 2,328E-010 |
| 2048 | 2,980E-008 | 5,821E-011 |

**Karar kuralı:** self-play tek süreçte küçük/orta batch (≤ 2048, tipik olarak ≤ 128) ile
çalışır → **CPU EP yeterlidir ve daha hızlıdır**; `OnnxEvaluatorOptions.UseCuda = false`
doğru varsayılandır. GPU yalnızca çok oyunculu toplu çıkarım sunucusunda anlamlı olur ve
kapsam dışıdır (spec v3 §10).

### 29.3 CUDA EP kurulumu ve `BindInput` tuzağı

Ayrı bir CUDA/cuDNN kurulumu **gerekmedi**: `torch 2.5.1+cu121`, ORT 1.23.2'nin istediği
cuDNN 9 ve CUDA 12 DLL'lerini `%APPDATA%\Python\Python310\site-packages\torch\lib`
altında barındırır. Bu dizin `PATH`'e eklendiğinde CUDA EP yüklenir. Makinedeki
`cudnn64_8.dll` çok eskidir. ORT paketi `Backgammon.Inference.csproj` içindeki
`$(OnnxRuntimePackage)` özelliğiyle değiştirilir
(`-p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu`).

**Kritik:** `OrtIoBinding.BindInput`, girdi `OrtValue`'su CPU belleğindeyken ve oturumun
cihazı CUDA iken **CPU→cihaz kopyasını bind anında** yapar; `SynchronizeBoundInputs()`
bunu tekrarlamaz. Bu yüzden yapıcıda bir kez bağlanan girdi, sonradan `VectorizeBatch` ile
doldurulduğunda cihaz **sıfır** görür (çıktı tam olarak `model(0)` değerine eşit olur).
Çözüm: CUDA oturumlarında girdi, tampon doldurulduktan **sonra** her çağrıda
`ClearBoundInputs()` + `BindInput()` ile yeniden bağlanır. CPU EP'de kopya olmadığı için
yeniden bağlama yapılmaz. Yeniden bağlama yönetilen tahsis yapmaz → 0 bayt/çağrı korunur.
`OnnxModelHandle.UsesCuda` bu dalı yönetir.

## 30. Değerlendirici sözleşmesi

| Yön | Kural |
|-----|-------|
| Kırpma | **Değerlendirici kırpmaz.** Yalnızca `float.IsFinite` savunma kontrolü; sonlu değilse `InvalidOperationException`. Kırpma `BackgammonSearch.ClampInPlace`'e aittir. |
| `offset` | **Her zaman 0.** `VectorizeBatch` offset kabul etmez; `offset != 0` → `ArgumentException`. |
| Terminal kayıt | `EvaluateBatch`/`ScoreBatch` aralığında terminal kayıt varsa `ArgumentException` (arama terminal-olmayanları öne taşımak zorundadır). |
| `ScoreBatch` normalizasyonu | Çıktı **grup softmax**'tır: `count` aday üzerinde toplam 1. `count == 0` → no-op. `count == 1` → `1.0`. |
| `Version` | Tek özellik = `model.ModelVersion`; hem değer hem politika sürümü. |
| `SetModel` | Yalnızca boştayken; yeni sürüm **büyük** olmalı; sonrasında çağıran `SearchWorkspace.Reset()` çağırmalı. |
| İş parçacığı | `OnnxModelHandle` paylaşılabilir; `OnnxPolicyValueEvaluator` **paylaşılamaz** (binding durumu var). |

### 30.1 Sonluluk ihlali

Model `NaN`/`Inf` üretirse `ArgumentException`. `Debug.Assert` **kullanılmaz** (VS test ana
bilgisayarı `Debug.Fail`'i amaçlanan istisnadan önce yansıtır). Kırpma yapılmaz.

### 30.2 Faz 3 v7 entegrasyon sonucu (spec v3 §8 Test 16)

`Phase3IntegrationTests` gerçek `model_v1.onnx` ile koşar; referans araması
`Backgammon.Tests` kaynağından `<Compile Include=... Link=...>` ile paylaşılır.

| Faz 3 v7 testi | Sonuç |
|---|---|
| 1 — referans eşitliği (6 pozisyon × derinlik 0/1) | **max \|Δ\| = 0** |
| 8 — determinizm (tekrarlı arama) | birebir aynı |
| 12 — `EvaluateAndScoreBatch` = ayrı çağrılar | birebir aynı |
| 16 — `ICombinedBatchEvaluator` kökte (`MaxCandidatesRoot = 4`) | politika hedefi toplamı 1 |
| 17 — `SetModel` → `Version` artışı → `Reset()` cache temizliği | doğrulandı |

## 31. Faz 3 v7 uyumluluk raporu

Faz 4 değerlendiricisi Faz 3 v7 arama motoruna **hiçbir değişiklik yapılmadan** takılır.
Aşağıdaki maddeler Faz 3 v7 sözleşmesinin Faz 4 tarafından nasıl karşılandığını belgeler.

### 31.1 `ICombinedBatchEvaluator` çağrı noktaları
Faz 3 v7 §3.3/§4.1 gereği çağrı noktaları **sabittir** ve Faz 4 bunları değiştirmez:

| Konum | Çağrılan yöntem | Koşul |
|-------|-----------------|-------|
| Kök, aday değerlendirme | `EvaluateAndScoreBatch` | yalnızca `MaxCandidatesRoot > 0` |
| Yaprak (depth 0) | `EvaluateBatch` | her zaman (terminal-olmayanlar için) |
| İç maks düğüm | `ScoreBatch` | her zaman |

Tip kontrolü (`evaluator is ICombinedBatchEvaluator`) **arama başında bir kez** yapılır.
`ICombinedBatchEvaluator` bilinçli olarak `IPositionEvaluator`'dan **türetilmez**
(Faz 3 v7 Test 16f). `OnnxPolicyValueEvaluator` üç arayüzü de uygular; arama onu
`ICombinedBatchEvaluator` olarak gördüğünde tek ORT çağrısıyla hem değer hem logit üretir.

### 31.2 `offset` kısıtı
`VectorizeBatch` offset parametresi almaz. Bu yüzden `EvaluateBatch(list, offset, count, …)`
`offset != 0` durumunda `ArgumentException` fırlatır. Arama, terminal-olmayanları listenin
**başına** taşıdığı için (`PartitionNonTerminal` + `Swap`) her zaman `offset = 0` kullanır.
Bu kısıt `Test08d_NonZeroOffsetThrows` ile doğrulanır.

### 31.3 Kırpma sahipliği
Faz 3 v7 §3.4: "değerlendiriciler `[-3,3]` aralığına kırpmaz; kırpma aramanın işidir."
Faz 4 ağı lineer değer başlığı kullanır ve **kırpma yapmaz**; yalnızca `IsFinite` kontrolü
vardır. `Test11b_ValuesAreFiniteAndUnclipped` hem sonluluğu hem de grafikte `Clip` düğümü
**bulunmadığını** doğrular. `ReferenceSearch` de aynı kurala uyar (kırpma tam olarak bir kez,
yaprak `EvaluateBatch` sonucunda).

### 31.4 `Reset()` ve cache temizliği
Faz 3 v7 §3.5 / Test 17: değer `Version` değişimi cache'i geçersiz kılar; `Reset()` cache'i
**kesinlikle** temizler; `BeginSearch()` **temizlemez** (yalnızca istatistik ve kök
tamponlarını sıfırlar). Faz 4'te model değişimi `SetModel` ile yapılır ve
`OnnxPolicyValueEvaluator.Version` yeni `ModelVersion`'ı döndürür; `Search` bir sonraki
çağrıda `EnsureCacheConsistent` üzerinden cache'i temizler. Ek olarak `SetModel` sonrası
`Reset()` çağrısı **çağıranın sorumluluğundadır** (F4-15) ve
`Test15f_SetModelThenWorkspaceResetClearsCache` bunu doğrular.

### 31.5 Determinizm
Aynı `(state, ayarlar, model)` → aynı sonuç. `IntraOpThreads = 1`, `DisableTf32 = true`,
sabit kova boyutu ve sıfır dolgu bunu garanti eder. `Test13`, `Test13b`, `Test13c` ve
`Test14b` sırasıyla tek oturum, farklı oturum, farklı parti bileşimi ve paralel arama
determinizmini doğrular.

## 32. Shard biçimi (v1)

Ayrıntılı belge: `SHARD_FORMAT.md`. Özet:

* 32 baytlık başlık: `"BGSP"`, `formatVersion = 1`, `featureVersion`, `vectorSize = 221`,
  `modelVersion`, `logTopCandidates`, `flags`, `reserved`.
* Oyun kaydı: `gameId`, `learnerSide`, `flags` (bit0 = aborted), `cubeValue`,
  `decisionCount`, kararlar, `winner`, `resultType`, `resultPoints`.
* Karar kaydı: `mover`, `flags` (bit0 IsPass, bit1 IsLearner, bit2 ChosenIsTerminal),
  `candidateTotal`, `loggedCount`, `searchValue`, `chosenVector[221]` (terminal değilse),
  `Q[loggedCount]`, `policyTargetCs[loggedCount]`, `candVectors[loggedCount][221]`.
* Yalnızca `Kind == 1` adaylar loglanır, `Q`'ya göre azalan sıralanır, en fazla
  `logTopCandidates` tanesi yazılır (`0` = hepsi).
* Küçük-endian; `*.bgsp` veya gzip'li `*.bgsp.gz`.

Çapraz dil doğrulaması: C# `Shard_CrossLanguageFixture` → `ml/artifacts/csharp_shard.bgsp`
→ Python `test_reads_csharp_written_shard` + `test_csharp_policy_targets_match_python_softmax`.

## 33. Eğitim hedefleri

### 33.1 TD(λ) değer hedefi
`γ = 1`, ödül yalnızca oyun sonunda. `z = resultPoints / cubeValue` (kazanan için pozitif).

```
y[T-2] = -z
y[t]   = -((1-λ)·V̂[t+1] + λ·y[t+1])      t = T-3 … 0
```

İşaret: her karar o anki oyuncunun bakış açısından değerlendirilir, bu yüzden bir sonraki
durumun değeri negatiflenir. Yalnızca `IsLearner = 1` kararlar değer kaybına girer.
Terminal pozisyonlar ağa asla girmez. `DEFAULT_LAMBDA = 0.7`.

### 33.2 Politika hedefi
Loglanan `Kind == 1` adaylar kümesi `E` üzerinde:

```
π_k = softmax_{k∈E}(Q_k / τ_train)
L_policy = -Σ_{k∈E} π_k · log p_k
```

`|E| < 2` olan kararlar atlanır; terminal ve `Kind == 2` adaylar dışlanır. `τ_train = 0.05`.
Sayısal kararlılık için maksimum çıkarma uygulanır.

### 33.3 Toplam kayıp
`L = L_value + c_policy · L_policy`, `c_policy = 1.0`. Değer kaybı Huber (varsayılan) veya
MSE olabilir; `ml/losses.py` ikisini de sunar.

## 34. Test stratejisi

| Katman | Proje | Kapsam |
|--------|-------|--------|
| Python | `ml/tests/` | ONNX ihraç/eşlik, kayıplar, TD(λ), shard biçimi, altın girdi, τ çapraz kontrolü, sayısal kararlılık |
| C# çıkarım | `Backgammon.Inference.Tests` | ORT eşliği, dinamik batch, determinizm, değerlendirici sözleşmesi, shard çapraz dil, kova allocation, iş parçacığı güvenliği |
| C# motor | `Backgammon.Tests` | Faz 1–3 (değişmedi) |

Eşik (güncel): Python `206/206`, C# çıkarım `60/60`, C# motor `256/256`, C# UI `85/85` (Release).
Unity testleri ayrı koşar (EditMode 7/7, PlayMode 4/4). Ayrıntılı tablo: `PHASES.md` §6.

---

## 35. Self-play sürücüsü (`Backgammon.SelfPlay`)

### 35.1 Bileşenler

| Dosya | Sorumluluk |
|---|---|
| `SelfPlayConfig.cs` | JSON yapılandırma + `Validate()` + `ToSearchSettings()` + `ToEvaluatorOptions()` |
| `SelfPlayAgent.cs` | Bir iş parçacığının `OnnxPolicyValueEvaluator` + `SearchWorkspace` + `SearchSettings` demeti |
| `SelfPlayRunner.cs` | Oyun döngüsü, hamle seçimi, karar başına vektörleştirme, aday loglama |
| `CommandLine.cs` | `--config` + `--ad=deger` çevrimdışı geçersiz kılmalar, `--help` |
| `Program.cs` | Model yükleme, iş parçacığı havuzu, shard yazımı, rapor |
| `EvalBench.cs` | `RandomBot`'a karşı `argmax` değerlendirmesi (`--eval-random N`) |
| `ShardFormat/Model/Writer/Reader.cs` | v1 ikili biçim (bkz. §32) |

`OnnxModelHandle` **tüm** ajanlar arasında paylaşılır (tek `InferenceSession`); her ajan
kendi `OrtIoBinding`/tampon demetine sahiptir, böylece eşzamanlı `EvaluateBatch` güvenlidir.

### 35.2 Oyun döngüsü

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

`Decide` seçimi: `ply < ExplorationPlies` ise `softmax(Q / selectionTemperature)`
(yalnızca `Kind ∈ {0,1}`), sonrasında `argmax(Q)`. Değerlendirme/lig maçlarında her zaman
`argmax`.

### 35.3 Karar başına veri

1. Seçilen aday için `_scratch.CopyFrom(_state)` → `ApplyMove(sequence)` → `Vectorize(_scratch, mover, buf)`.
   **`EndTurn` çağrılmaz** (spec v3 §5.2).
2. `Kind == 0` ise `ChosenIsTerminal` set edilir, vektör yazılmaz.
3. `IsLearner` ise `FillLoggedCandidates`: yalnızca `Kind == 1` adaylar, `Q`'ya göre azalan,
   en fazla `LogTopCandidates`; `Q`, `PolicyTargetCs` (`RootCandidate.PolicyTarget`) ve
   `CandidateVectors` yazılır.
4. Geçiş kararında vektör mevcut pozisyondur (bkz. `ASSUMPTIONS.md` F4-36).

### 35.4 İş parçacıkları ve determinizm

`--threads N` ile oyunlar `i % N` kuralıyla dağıtılır; iş parçacığı `t` RNG'si
`Seed + t * 0x9E3779B97F4A7C15` ile tohumlanır. **Yalnızca `N = 1` birebir
tekrarlanabilir** (spec v3 §5.1).

---

## 36. Python eğitim laboratuvarı

### 36.1 Dosya düzeni

| Dosya | Sorumluluk |
|---|---|
| `model.py` | `Backbone` (221→128→64, GELU) + `value_head` + `policy_head` |
| `export_onnx.py` | ONNX dışa aktarma (opset 15, dinamik batch) + PyTorch↔ORT parite kontrolü |
| `shards.py` | v1 shard okuyucu/yazıcı (C# ile aynı şema) |
| `td_lambda.py` | TD(λ) geriye dönük özyineleme |
| `losses.py` | Grup softmax çapraz entropi, MSE/Huber, toplam kayıp |
| `replay.py` | Replay buffer, değer/politika örnekleri, hedef keskinliği filtresi |
| `train.py` | Senkron eğitim döngüsü (dışa aktar → self-play → buffer → hedefler → adımlar → ölçüm) |
| `config.yaml` | Tüm hiperparametreler (spec v3 §6.6 yer tutucuları) |
| `tests/` | 194 test |

### 36.2 İterasyon akışı

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

### 36.3 Ölçüm kümeleri

* **Sabit MC probe** — 1. iterasyonda `lam = 1.0` ile üretilir; hedefler `±z` olduğu için
  **ağdan bağımsızdır**. "Değer kaybı 0. adıma göre düşer" kriteri bu kümeyle ölçülür.
* **Sabit TD probe** — 1. iterasyonda `lam = 0.7` ile üretilir (sabit ama ağa bağımlı).
* **Buffer** — her iterasyonda güncel hedeflerle yeniden hesaplanır; politika kaybı
  düzgün baz `log|E|` ile karşılaştırılır.

### 36.4 Hedef keskinliği kapısı

`train.policy_min_sharpness` (varsayılan 0,99): hedef entropisi `log|E|`'ye bu eşikten
daha yakın kararlar **eğitimden** elenir. Raporlama tüm uygun kararlar üzerinden yapılır.
Gerekçe ve ölçümler: `ASSUMPTIONS.md` F4-40.

---

## 37. Aşama C ölçüm özeti

| Ölçüm | Değer |
|---|---|
| 1000 oyunluk smoke (10 × 100, depth 0, CUDA) | 308 s |
| Değer kaybı (sabit MC probe) | 1,9153 → 1,5629 (**−18,4 %**) |
| Politika kaybı (buffer) | 1,8513 < düzgün baz 2,1264 |
| Hedef entropisi / `log\|E\|` | 0,9984 → 0,3934 |
| `RandomBot` kazanma (400 oyun) | **%64,25** (eğitilmemiş ağ: %53,00) |
| Shard boyutu (depth 0, gzip yok) | ~885 KB/oyun, ~1,0 KB/karar |
| Shard boyutu (depth 1, gzip) | ~94 KB/oyun, ~0,14 KB/karar |

Ayrıntılı tablo ve bulgular: `ml/artifacts/stage_c_report.md`.
---

## 38. Lig (model havuzu)

### 38.1 Bileşenler

| Dosya | Sorumluluk |
|---|---|
| `ml/league.py` | `League`, `PoolEntry`, `EvalResult`, `run_eval`, `should_enter_pool`, `evaluate_for_entry` |
| `ml/runs/pool/pool.json` | Havuz indeksi (üye listesi + politika) |
| `ml/runs/pool/v{N}.onnx` | Dondurulmuş model artefaktları |

`League` alanları: `pool_dir`, `max_size` (10), `eviction` (`oldest` | `weakest`),
`entries`. Her `PoolEntry`: `name`, `onnx_path`, `model_version`, `iteration`,
`strength`, `strength_se`; `lower_confidence_bound = strength − 1,96·strength_se`.

### 38.2 Akış

```
train.py
  ├─ League.load(pool_dir)                    # pool.json
  ├─ her iterasyon:
  │    ├─ pool_opponent = league.select_opponent(rng, 1.0)   # havuz doluysa her zaman bir üye
  │    ├─ Backgammon.SelfPlay --pool-model <o> --pool-fraction 0.20
  │    │     └─ oyun başına %20 havuz rakibi, IsLearner = 0
  │    └─ eğitim
  └─ her `every` iterasyonda: update_league()
       ├─ havuz boş  → mevcut modeli karşılaştırma tabanı olarak ekle
       └─ havuz dolu → strongest()'e karşı n_eval oyun
                        LCB = mean − 1.96·SE > entry_threshold  ⇒  havuza gir
                        maxSize aşılırsa eviction (oldest | weakest) + artefakt sil
```

C# sürücü oyun akışında `%80` öğrenen-öğrenen, `%20` öğrenen-havuz üretir. Havuz
rakibinin kararları `IsLearner = 0` olarak loglanır; o kararlar için değer/politika kaybı
hesaplanmaz, yalnızca TD zincirinde bootstrap olarak kullanılır.

**Önemli:** oyun başına havuz oranı **yalnızca** C# sürücüsünde uygulanır; `train.py`
iterasyon seçiminde oran uygulamaz (bkz. `ASSUMPTIONS.md` F4-51).

### 38.3 Havuza giriş

```
her K iterasyonda:
    strongest = league.strongest()
    if strongest is None:  -> mevcut model taban olarak eklenir
    else:
        r = evaluate_for_entry(league, onnx, games=N_eval, seed=sabit, depth=D)
        if r.lower_confidence_bound > entry_threshold:  -> havuza ekle
```

Giriş sırasında ONNX havuz klasörüne kopyalanır; boyut aşılırsa politikaya göre bir üye
(ve dosyası) çıkarılır.

### 38.4 Ölçülen maliyet

| Derinlik | 400 oyunluk lig değerlendirmesi |
|---|---|
| 0 | ~7 s |
| 1 | ~690 s |

Bu yüzden `every`/`n_eval` derinliğe göre ayarlanmalıdır (bkz. `ASSUMPTIONS.md` F4-48).

### 38.5 Havuz dosyası

`pool.json`: `{ maxSize, eviction, entries: [{ name, onnx_path, model_version,
iteration, strength, strength_se }] }`. `onnx_path` havuz klasörüne görelidir;
eleme sırasında dosya da silinir.

### 38.6 Önceki checkpoint ile karşılaştırma

```powershell
python ml/eval_bench.py --model <yeni>.onnx --vs-model <eski>.onnx --games 400
```

`--vs-model` tekrarlanabilir; her model için ayrı bir `Model:<dosya adı>` satırı üretilir.
Çok rakipli JSON birleştirmesi Python tarafında yapılır (F4-52).

---
## 39. `eval_bench` — taban oyuncu raporları

### 39.1 Rakip türleri

| Tür | Uygulama | Not |
|---|---|---|
| `RandomBot` | `EvalBench.PlayRandom` — rastgele yasal hamle | hızlı, zayıf |
| `PipBot` | `EvalBench.PlayPip` — `rakipPip − kendiPip` maksimizasyonu | vurma eğilimli, oyunlar uzun |
| `Model` | `EvalBench.PlayModel` — başka bir ONNX modeli, `argmax` | önceki checkpoint / havuz üyesi |

### 39.2 Protokol

Sabit seed; oyun `g` için `seed + g·0x9E3779B97F4A7C15`; renkler `g % 2` ile değişir;
öğrenen her zaman `argmax`. Sonuç: oyun başına ortalama puan ± standart hata ve %95 GA.

### 39.3 Çıktı

`--eval-json` ile makine okunur JSON (bkz. `ASSUMPTIONS.md` F4-46);
`ml/eval_bench.py --out report.md` ile markdown tablo;
`ml/eval_bench.py --plot train_report.json --plot-out chart.png` ile dört panelli
yakınsama grafiği.

---

## 40. Faz 3 arama ayarı ölçüm tablosu

`ml/settings_bench.py` altı kombinasyonu ölçer:

| Ayar | DepthPly | MaxRoot / Inner |
|---|---|---|
| kısıtsız | 0, 1, 2 | 0 / 0 |
| kısıtlı | 0, 1, 2 | 4 / 4 |

Her kombinasyon için iki ölçüm:

1. **Verim** — `Backgammon.SelfPlay --log-top 0 --threads 1`; konsol çıktısındaki
   `oyun/s` ve `B/oyun` ayrıştırılır.
2. **Güç** — `PipBot`'a karşı ortalama puan ± standart hata.

`quick` profili: depth 0 → (20, 100), depth 1 → (4, 20), depth 2 → (1, 2)
(self-play, değerlendirme oyun sayıları). Depth 2 tek oyun başına ~76 s sürdüğü için
örneklem küçüktür ve tabloda bu açıkça belirtilir.

---

## 41. Aşama D kabul çalıştırması (referans)

| Alan | Değer |
|---|---|
| Dizin | `ml/runs/stage_d` |
| Ayarlar | 10 iterasyon × 100 oyun, `S = 200`, `DepthPly = 1`, `MaxCandidates 4/4`, `λ = 1.0`, CPU |
| Süre | 1316 s (self-play 890 s) |
| Değer kaybı | 4.662 → 2.548 |
| Buffer politika kaybı | 1.364 → 1.192 (düzgün baz 1.339) |
| Hedef entropisi / `log\|E\|` | 0.997 → 0.372 |
| Havuz | `v5` (taban), `v10` (+0.40 ± 0.139 ile girdi) |
| `RandomBot` | %80.50, +1.58 ± 0.13 |
| `PipBot` | %40.50, −0.23 ± 0.15 |
| `model_v5` | %54.50, +0.23 ± 0.15 |

Ayrıntılı rapor: `ml/artifacts/stage_d_report.md`.

---

## 42. gnubg ER ölçüm hattı

`ml/gnubg_er.py`, referans pozisyonlarda modelin hamle kalitesini GNU Backgammon'a karşı
ölçer. Çıktı: pozisyon başına equity kaybı (ER) + özet (markdown/JSON).

### 42.1 Alt süreç protokolü

`gnubg-cli.exe -t` (metin modu) başlatılır, komutlar **stdin'e bayt olarak** yazılır.
Kritik kurallar:

* `set board` için oyun içinde olmak gerekir — **her** tahta yüklemesinden önce `new game`.
  Aksi hâlde gnubg tahtayı **sessizce reddeder** ve önceki tahta kalır.
* `set cube use off` `new game`'den **önce** gelmelidir.
* `set evaluation chequerplay evaluation plies N` yalnızca `eval`'i etkiler; `hint` her zaman
  0-ply çalışır.
* `set evaluation chequerplay evaluation cubeful off` → cubeless equity.
* `eval` equity'si **sıradaki oyuncunun** bakış açısındandır; afterstate'i `turn = -turn`
  ile yükleyip sonucu negatife çevirmek gerekir.
* `show pipcount` sıradaki oyuncuyu **önce** yazar; ayrıştırıcı isimle eşleştirir
  (`MONSTER` = X = Siyah, `gnubg` = O = Beyaz).
* Çoklu `eval` çıktısı `The pip counts are:` satırından bölünür (`Position ID:` satırı
  `set board` tarafından da yankılandığı için kullanılamaz).
* Sayılar **ondalık virgül** ile yazılır (`+0,160`).

### 42.2 Tahta dönüşümü

gnubg'de X = Siyah (24→1 oynar, evi 1–6), O = Beyaz'dır. Proje tahtası
(`board[0]` = Beyaz bar, `board[1..24]` = noktalar, `board[25]` = Siyah bar; + = Beyaz):

```python
simple[0] = -board[25]          # Siyah bar
simple[i] = -board[i]           # i = 1..24
simple[25] = board[0]           # Beyaz bar
```

Doğrulama: başlangıç pozisyonu `4HPwATDgc/ABMA` position ID'sini ve 167/167 pip verir.

### 42.3 ER tanımı

1. Modelin `afterStates` listesi 221 elemanlı vektöre çevrilir (Python portu
   `vector_golden.json`'a karşı 500/500 doğrulanmıştır) ve ONNX modeline verilir.
2. **Tüm** afterstate'ler tek gnubg sürecinde 2-ply cubeless `eval` ile değerlendirilir.
3. `E_best = max(equity)`, `E_model` = modelin seçtiği afterstate'in equity'si,
   `ER = E_best − E_model`.

`E_best` ve `E_model` aynı değerlendiriciden geldiği için ER tutarlıdır. gnubg'nin `hint`
sıralaması yalnızca bilgi amaçlı saklanır.

### 42.4 Hamle seçimi (`--criterion`)

| Değer | Anlamı |
|---|---|
| `policy` (varsayılan) | Politika başı argmax — C# `ArgMaxCandidate` ile aynı |
| `value` | Değer kafası argmax |
| `pip` | `rakipPip − kendiPip` argmax (`PipBot` tabanı) |

### 42.5 Kullanılabilir vakalar

`reference_positions.json` içindeki 57 vakanın 50'si kullanılır (15/15 taş + boş olmayan
`afterStates`); 7 el yapımı vaka gnubg tarafından geçersiz sayılır. Toplam 920 afterstate.
Her tahta yüklemesinden sonra `show pipcount` ile Python'un pip sayımı karşılaştırılır;
uyuşmazsa vaka atılır.

### 42.6 Sonuç (Aşama D, `model_v10.onnx`)

| Ölçüm | `policy` | `pip` tabanı |
|---|---|---|
| Ortalama ER | 0.1941 | 0.1283 |
| Medyan ER | 0.1410 | 0.0740 |
| Maksimum ER | 0.5600 | 0.9660 |
| gnubg ile aynı hamle | %32.0 | %42.0 |

gnubg yoksa betik **uydurma değer üretmez**; çıkış kodu 2 ile temiz hata verir.

---

## 43. Faz 5 — Bearoff, küp/maç katmanı, UI ve Unity

### 43.1 Katman şeması

```
Unity (MonoBehaviour)                 F:\Projects\Unity\Tavla3D
        |  (yalnızca veri: Backgammon.UI türleri)
Backgammon.UI                         netstandard2.1, UnityEngine YOK
        |  GameOrchestrator
Backgammon.Core                       motor + arama + bearoff + küp/maç
        |  IPositionEvaluator / IPolicyEvaluator
Backgammon.Inference                  ONNX Runtime köprüsü
```

**Kural:** `Backgammon.UI` hiçbir `UnityEngine` türü içermez. Bu sayede Test 27–33
Unity olmadan `dotnet test` ile koşar. Unity'ye bağımlı her şey `Assets/Backgammon.UI/`
altındaki MonoBehaviour'lardadır.

### 43.2 Bearoff veritabanı

**Neden dekoratör?** Veritabanı modelin içine gömülseydi ağ, bearoff pozisyonlarını da
öğrenmek zorunda kalırdı; hâlbuki bu pozisyonların değeri **kesin** olarak hesaplanabilir.
`BearoffAwareEvaluator`, `BackgammonSearch` ile `OnnxPolicyValueEvaluator` arasına girer:

```
BackgammonSearch
   -> MatchAwareEvaluator        (maç varsa)
      -> BearoffAwareEvaluator   (bearoff ise kesin değer yazar)
         -> OnnxPolicyValueEvaluator
```

**"Üzerine yaz" stratejisi.** Toplu değerlendirme bölümlenmez; iç değerlendirici tüm
partiyi bir kez değerlendirir, sonra bearoff kayıtları kesin değerle **üzerine yazılır**.
`SkipInnerForPureBearoffBatches` açıksa ve parti tamamen bearoff ise iç çağrı hiç yapılmaz.
Bu tasarım Faz 1 API'sine (`AfterStateList.CopyRecordFrom` gibi) hiçbir ekleme gerektirmez.

**Format.** 64 baytlık başlık + `positions × (maxRolls+1) × uint16` CDF tablosu.

| Alan | Değer |
|---|---|
| `magic` | `"TVB1"` (`0x31425654`) |
| `version` | 1 |
| `points` / `checkers` | 6 / 15 |
| `positions` | 54 264 |
| `maxRolls` | 22 (üretici otomatik yükseltir) |
| `flags` | bit 0 = mars tablosu var |
| `payloadCrc32` | CRC-32/ISO-HDLC |

Okuma `MemoryMappedFile` ile yapılır; `File.ReadAllBytes` **yasak** (2,38 MiB dosya
kopyalanmaz, sayfalar talep üzerine eşlenir).

**Sıralama.** Kendi colex sıralaması: `Rank(c) = Σ_{i=0..5} C(S_i + i, i+1)`.
gnubg indeksine bağımlılık yoktur; `Unrank` ile 54 264 pozisyonun tamamı tur doğrulandı.

**Kesin denklem.** `pA[k] = cdfA[k] − cdfA[k−1]`,
`P(A kazanır) = Σ_k pA[k]·(1 − cdfB[k−1])`, `E = 1 − 2·P(win)`. Saf yarışta mars yoktur.
`float.IsFinite` denetimi vardır; bozuk veri `InvalidOperationException` atar.

**Kapsam.** Yalnızca **tek taraflı** bearoff. İki taraflı tablo 2 944 581 696 pozisyon
(≈29,4 GB) olduğu için Faz 6'ya ertelendi (F5-06).

### 43.3 Küp ve maç katmanı

**Küp ve maç ağın dışındadır.** Küp kararı `argmax` değil **eşik** kararıdır; maç kazancı
ise MET ile kapalı biçimde hesaplanır. İkisi de ağa sokulursa eğitim verisi ve kalibrasyon
ikiye katlanır, karşılığında hiçbir şey kazanılmaz.

**Negamax güvenliği.** `MWC` monoton olduğu için hamle seçimini değiştirmez, ama doğrudan
negamax'a verilirse işaret/ölçek bozulur. Doğru dönüşüm:

```
ME = 2 · MWC − 1
```

`MatchAwareEvaluator` bunu uygular; money game'de tam kimliktir. `Version` maç hash'ini
içerir, böylece maç değişince arama önbelleği geçersizleşir.

**MET.** Rockwell–Kazaross tablosu `Backgammon.Core/Match/met_rk.json` içine gömülüdür
(25 × 25, `EmbeddedResource`). gnubg 1.08.003'ün `Rockwell-Kazaross.xml` dosyasıyla
**625 hücrenin tamamında max |Δ| = 0,000E+000**.

**Küp eşikleri (money game).**

| Büyüklük | Türetme | Değer |
|---|---|---|
| `MoneyDoublePoint` | `max(2E, 1) > E` | 0,5 |
| `MoneyTooGoodPoint` | `E > 1` ⇒ ikileme ama pas | 1,0 |
| `shouldTake` | `−2E ≥ −1` ⇒ `E ≤ 0,5` | `E < 0,5 − ε` |

`E_doubleTake = 2E`, `E_doublePass = 1,0`. Maçta eşikler MET üzerinden hesaplanır;
Crawford oyununda küp yoktur (`CubeVisibility.Hidden`).

**Ölçülen katkı.** 400 oyunluk maç farkındalığı karşılaştırmasında farklar standart
hatanın içinde kaldı. Nedeni katman değil, değer kafasının aşırı dağınık olmasıdır
(bkz. §43.7).

### 43.4 `Backgammon.UI`

| Tür | Sorumluluk |
|---|---|
| `GameOrchestrator` | Zincir kurulumu, arama, oyun akışı, küp, analiz |
| `GameOrchestratorOptions` | Değerlendirici, bearoff, MET, dağılım, arama/motor ayarları, RNG |
| `PositionAnalysis` | UI'ye hazır DTO: equity, MWC, dağılım, pip, rolls-to-off, küp |
| `BoardViewModel` | 24 hane + bar + toplanan pullar + zar + sıra + faz |
| `CubeViewModel` | `Hidden` / `Centered` / `Owned` / `Offered` |
| `MatchScoreViewModel` | Skor, maç uzunluğu, away-score, Crawford/post-Crawford |
| `AnalysisViewModel` | tr-TR biçimlendirme, "Kesin"/"Tahmin" rozeti, `—` bilinmeyen |
| `MoveInputController` | Yasal hedef üretimi, kısmi hamle, geri alma |
| `BoardLayout` | 24 hane + bar + tepsi + küp dikdörtgenleri (çakışmasız) |
| `SearchOutcome` | `SearchResult` (`ref struct`) için `Task<T>` uyumlu taşıyıcı |
| `PolicyValueAdapter` | `IPositionEvaluator` + `IPolicyEvaluator` → `IPolicyValueEvaluator` |
| `DicePairs` | 21 sırasız zar çifti + ağırlıklar (toplam 36) |

**Zincir kurulumu.** `EnsureChain()` bileşik bir `_chainKey` hesaplar (değerlendirici
sürümü, bearoff sürümü, MET sürümü, dağılım sürümü, maç hash'i). Anahtar değişince
`SearchWorkspace.Reset()` **zorunludur** (Faz 3 §3.5).

**Eşzamanlılık.** `SemaphoreSlim(1,1)` — aynı anda tek arama. İkinci çağrı
`InvalidOperationException` atar. `IsSearching` bayrağı UI'nin kilit durumunu yansıtır.

**İki arama yolu.**

| Yol | Nerede | Davranış |
|---|---|---|
| `ThinkAsync(ct[, budget])` | Unity'den bağımsız katman, testler | `Task.Run` ile arka planda |
| `Think()` | Unity (`GameBootstrap`) | Çağıran iş parçacığında senkron |

`Think()`'in varlık nedeni §43.6'daki ONNX Runtime kısıtıdır.

### 43.5 Unity katmanı

Unity **6000.3.8f1**, URP 17.3.0, uGUI 2.0.0, Input System 1.18.0, test-framework 1.6.0.
Proje `F:\Projects\Unity\Tavla3D` altındadır; kurulum ve test komutları `unity/README.md`
içinde, gerçek koşu kaydı `unity/build.log` içindedir.

```
Assets/
  Plugins/            Backgammon.Core.dll, Backgammon.Inference.dll, Backgammon.UI.dll,
                      Microsoft.ML.OnnxRuntime.dll, x86_64/onnxruntime.dll
  StreamingAssets/    models/model.onnx, bearoff/bearoff1_v1.bin
  Backgammon.UI/
    Scripts/          Bootstrap, Board, Dice, Cube, Match, Analysis, Settings, Input,
                      Infrastructure
    Editor/           SceneBuilder, BuildScript
    Tests/            EditMode (Test 38-40), PlayMode (duman + ONNX arka uç)
  Scenes/Main.unity   SceneBuilder tarafından üretilir
```

**Sahne üretimi kod ile yapılır** (`SceneBuilder`), elle değil. Böylece sahne yeniden
üretilebilir ve `SceneLoads` testi gerçek sahneyi doğrular.

**Nesne havuzu.** `CheckerPool` 30 pulu önceden oluşturur; çalışma anında `Instantiate`
çağrısı **sıfırdır** (Test 40).

**Girdi.** `activeInputHandler: 2` (**Both**). `StandaloneInputModule` eski girdi arka
ucunu gerektirir; yalnızca Input System açıkken her karede `InvalidOperationException`
atıyordu.

### 43.6 İş parçacığı modeli (ölçülmüş kısıt)

`OrtIoBinding` **iş parçacığı güvenli değildir**. Unity/Mono altında arama gerçek kare
döngüsü içinde arka plan iş parçacığında çalıştırıldığında `SynchronizeBoundInputs`
erişim ihlali (`0xC0000005`) üretir. Tek başına çalışan arka plan aramaları geçer; hata
yalnızca sahne + kare döngüsü + ONNX birlikteyken ortaya çıkar.

Bu yüzden Unity tarafı `GameOrchestrator.Think()` kullanır: arama **çağıran iş
parçacığında** senkron çalışır. 1 katmanlı arama önbellekli toplu değerlendirme ile birkaç
on milisaniyede biter; kare hızı etkilenmez. `ThinkAsync` Unity'den bağımsız katmanda ve
testlerde aynen geçerlidir (Test 33).

### 43.7 Ölçülen değerler

| Ölçüm | Değer |
|---|---|
| Bearoff DB | 2 496 208 bayt, 54 264 pozisyon, `MaxRolls = 22` |
| Bearoff C# ↔ Python | max \|Δ\| = 7,630E-006 |
| MET ↔ gnubg | max \|Δ\| = 0,000E+000 (625 hücre) |
| Küp anlaşması (0-ply) | ikileme %51,52 / alma %61,36 / ikisi %46,21 |
| Değer kafası korelasyonu | +0,2431 (MAE 0,8014) |
| Değer kafası kalibrasyonu | `gnubg ≈ 0,0874·bizim + 0,1589` |
| Unity EditMode / PlayMode | 7/7 / 23/23 |
| `Backgammon.Tests` (çekirdek) | 245/245 |
| `Backgammon.UI.Tests` | 45/45 |
| `Backgammon.Inference.Tests` | 57/57 |
| `ml/tests` (pytest) | 194 geçti / 1 atlandı |

> **Not:** `PerformanceTests` içindeki hız eşikleri (`RandomGame_Throughput*`) makine yüküne
> duyarlıdır. Test paketi tek başına çalıştırılmalıdır; Unity derlemesi / PlayMode testleriyle
> aynı anda koşulursa eşik aşımı nedeniyle yanlış kırmızı verebilir.

**Değer kafası aşırı dağınık.**
karşılaştırıldığında eğim **0,0874** çıktı: model `[-3,3]` aralığını neredeyse tamamen
kullanıyor, gnubg `[-0,82, +1,65]` aralığında kalıyor. Kalibrasyon sonrası MAE
0,8014 → 0,2897'ye düşüyor, yani bilgi var ama ölçek yanlış. Bu bir **Faz 4 model
kalitesi** sorunudur; küp kararları eşik tabanlı olduğu için doğrudan yanlış
ikileme/pas kararına dönüşür. Ayrıntı: `ml/artifacts/stage_b_afterstates.md`.

### 43.8 İkinci oynanış turu — durum sahipliği dersleri

Altı kullanıcı hatası, üç mimari derse indirgenir.

**(a) Skor sahibi tek yer olmalı.** `BackgammonState.Reset()` maç alanlarını
(`whiteScore`, `blackScore`, `matchLength`, Crawford bayrakları) da sıfırlar. Bu yüzden
`BackgammonEngine.NewGame()` **yalnızca yeni maç** için doğrudur. Parti geçişi
`PrepareNextGame()` ile yapılır; o da skoru korur. `GameOrchestrator.NewGame()` artık bu
ayrımı uygular:

```
NewGame()
  mac bittiyse  -> NewMatch(matchLength, EnableJacoby)
  aksi halde    -> ApplyResult (bekleyen) + PrepareNextGame
```

**(b) Olay delegeleri kurulum anında kopyalanmamalı.** `CubeView.Initialize()` içinde
`CreateButton(..., model.Accepted)` gibi bir çağrı, abonelik sonradan yapıldığında
düğmeyi kalıcı olarak ölü bırakır. Kural: düğme her zaman **örnek metot** alır
(`RaiseAccepted`), olayı tıklama anında okur. `MatchLengthView.Raise` bu desenin
referansıdır.

**(c) Türetilmiş görünüm değerleri modelde hesaplanmalı.** `OfferDouble` küp değerini
`Take` anına kadar değiştirmez (motor kuralı doğrudur: teklif henüz kabul edilmedi).
Görünümün "teklif edilen değer"i göstermesi gerekir; bu yüzden `CubeViewModel.DisplayValue`
eklendi. Unity katmanı `Value` yerine `DisplayValue` kullanır.

**Yerleşim çevirme.** "Kendi toplama alanın her zaman sağ altta" kuralı
`BoardLayout.Calculate(w, h, humanTrayBottom)` ile yerleşime taşındı; `BoardView.HumanTrayBottom`
yalnızca bir bayrak. `BoardInputController` değişmedi çünkü isabet testi tepsi `Image`
dikdörtgenlerini okur ve `BoardView` onları yeniden yerleştirir — **yerleşim tek
kaynaktan** gelir.

**Tahta aynalanmaz (üçüncü oynanış turu dersi).** İlk sürüm tahtayı dikey olarak
dikey aynalıyordu (hane satırları 13..24 alta iniyordu). Renk değiştirildiğinde tahta
tanınmaz hale geliyordu: üçgen yönü hane numarasından (`point > 12`) türetildiği için
tüm üçgenler ters dönüyor, bar yarıları ve pulların yığılma kenarı da kayıyordu.
Kural artık şu: **hane yerleşimi oyuncu renginden bağımsızdır**; yalnızca tepsi yarıları
takas edilir. Üçgen yönü de satırdan türetilir (`BoardPointView.SetFaceFlipped`).

**Sıra kuralları motorda.** Üçüncü turda üç kural `BackgammonEngine`'e taşındı ve
tek doğruluk kaynağı yapıldı:

| Kural | API |
|---|---|
| Zar yalnızca sıra başında atılır | `BackgammonEngine.CanRoll` → `GameOrchestrator.CanRoll` → "Zar" düğmesi `interactable` |
| Zarların tamamı oynanamıyorsa sıra kapanır (5-5'te 2 hamle) | `BackgammonEngine.ShouldEndTurn` → `GameOrchestrator.ApplyMove` |
| Son taş toplandıysa oyun biter | `BackgammonEngine.IsGameOver` → `GameOrchestrator.Refresh` |

Bardan giriş zorunluluğu `LegalMoveGenerator`'da zaten vardı; ancak
`MoveInputController` her dizinin **tüm** adımlarını hedef olarak yayınladığı için
oyuncu barda taş varken ikinci adımı seçebiliyordu. `_mustEnterFromBar` bayrağı bu
sızıntıyı kapatır.

**Bloke zar.** `BackgammonEngine.PassTurn()` motorda vardı ama akış onu çağırmıyordu.
`GameOrchestrator.HasLegalMoves` + `GameBootstrap`'ta 1,2 sn'lik bekleme, kullanıcıya
"hamle yok - sira geciyor" geri bildirimini verirken sırayı devreder.

### 43.9 Dördüncü oynanış turu — bayat oyuncu derlemesi dersi

Kullanıcı üç hata bildirdi: (1) Siyah oynarken toplama bölgesinde Beyaz taş
vurunca kendi taşının eksilmesi, (2) insan kazandığında yapay zekânın hamle yapmaya
devam etmesi, (3) skorun güncellenmemesi. Ayrıca "hangi renk seçilirse seçilsin kendi
toplama alanı sağ altta olmalı" şartı yeniden hatırlatıldı.

**Üçü de kaynak kodda tekrarlanamadı.** Önce regresyon testleri yazıldı
(`GameplayFix4Tests` + `GameplayFix4PlayModeTests`), sonra üretim kodu okundu:

| Bildirim | Kanıt |
|---|---|
| Vurulan taş siliniyor | `BackgammonEngine.ApplyStep` vurma dalı taşı **rakip barına** yazar (`board[oppBar] += opp`), silmez. `Hit_InBearOffArea_KeepsAllThirtyCheckers` 30 pulun tamamını doğrular. |
| Oyun bitince rakip oynuyor | `GameBootstrap.Update()` `IsGameOver` iken erken döner; `GameOrchestrator.ApplyMove` `EndTurn`'ü `phase == Moving` ile korur. `HumanWin_EndsGame_UpdatesScore_AndStopsAi` 10 kare boyunca sıra/zar/faz/skorun değişmediğini doğrular. |
| Skor güncellenmiyor | `GameOrchestrator.Refresh()` `_isGameOver && !_resultApplied` iken `ApplyResult` çağırır ve `_resultApplied` ile **bir kez** uygular. |
| Tepsi sağ altta | `BoardLayout.Calculate(w, h, humanTrayBottom)` yalnızca tepsileri takas eder; `GameBootstrap.ApplyPlayerColor` `HumanTrayBottom = _humanPlayer < 0` atar. |

**Kök neden: bayat oyuncu derlemesi.** `Build\Tavla3D.exe` 11.11.2026 tarihliydi,
kaynaklar ise 12.11.2026. Kullanıcı düzeltmelerden **önceki** çalıştırılabilir dosyayı
deniyordu. Ders: **davranış raporu ile kaynak kodu çeliştiğinde önce derleme
zaman damgalarını karşılaştır.**

**Yine de iki motor sertleştirmesi yapıldı.**

**(a) `EndTurn` oyun bitti bilgisini korur.** `BackgammonEngine.EndTurn` artık
`phase == GameOver` veya `whiteBorneOff/blackBorneOff >= 15` iken **hiçbir şey yapmaz**.
Önceden "Turu bitir" düğmesi ya da bloke-zar yolu son taş toplandıktan sonra fazı
`GameOver`'dan çıkarıp sırayı çevirebiliyordu. Tek doğruluk kaynağı motordur; UI'ya
güvenilmez.

**(b) Varsayılan renk testleri renkten bağımsız.** Varsayılan oyuncu rengi Siyah
olduğundan `MoveFlowTests.ClickClick_PlaysBothDiceAndMovesChecker` giriş kilidine
takılıyordu (`BoardInputController.IsLocked = state.turn != HumanPlayer || phase != Moving`).
Test artık `ApplyPlayerColor(1, true)` ile oyuncuyu Beyaz yapıp devam eder; üretim
kodunda değişiklik gerekmedi.

**Yeni test envanteri.**

| Dosya | Kapsam |
|---|---|
| `Backgammon.UI.Tests\GameplayFix4Tests.cs` | 9 test: vurma sonrası 15+15 taş, ev bölgesinde blot vurma hamlesinin üretilmesi, `EndTurn`'ün oyun sonu koruması, skorun bir kez uygulanması, tepsi yarısı, hane dikdörtgenlerinin renkten bağımsızlığı, hane 1/24 geometrisi |
| `Unity\...\PlayMode\GameplayFix4PlayModeTests.cs` | 3 test: tahtada 30 pulun tamamının görünür ve tahta içinde kalması, insan kazanınca skor + AI durması, her iki renkte tepsinin sağ altta olması |

### 43.10 Beşinci oynanış turu — yığın etiketi çizim sırası ve tahta kontrastı

Kullanıcı iki madde bildirdi: (1) Siyah oynarken toplama bölgesine yakın bir Beyaz
taşı vurunca Siyah taş sayısının 14'e düşmesi, (2) tahtanın orta alanının daha
kontrastlı olması, "oyunun içi" gibi görünmesi.

**Taş kaybı motorda yok — kanıt fuzz testi.** Önce iddiayı çürütecek test yazıldı.
`GameplayFix5Tests.Orchestrator_RandomGames_NeverLoseCheckers` 25 rastgele oyun
oynar; **her hamleden sonra** ve her `AnalyzeCurrent()` çağrısından sonra
`CountPieces(+1) == 15`, `CountPieces(-1) == 15`, toplam 30 ve bar işaret tutarlılığı
doğrulanır. Test geçti: motor hiçbir yolda taş silmiyor. `ApplyStep` vurma dalı taşı
rakip barına yazar, `UndoStep` bunun tam tersidir.

**Kök neden: çizim sırası.** `BoardPointView.CountLabel` hane dikdörtgeninin
çocuğuydu; hane dikdörtgenleri `CheckerPool`'dan **önce** oluşturulduğu için uGUI
çizim sırasında etiket pulların **altında** kalıyordu. 5'ten kalın yığınlarda sayı
görünmüyor, bu da "taş eksildi" izlenimi veriyordu. Düzeltme: `Initialize` sonunda
24 etiketin tamamı `_root`'a yeniden ebeveynlenir (havuzdan sonra), `Recalculate`
bunları hane dikdörtgenlerine yerleştirir ve okunabilirlik için her birine siyah
`Outline` (1,5 px) eklenir.

**Kontrast.** Tahtanın orta şeridi opak ve koyu yapıldı; haneler arasındaki aydınlık
farkı büyütüldü ve oyun alanını ikiye bölen ince bir orta çizgi eklendi.

| Öğe | Önce | Sonra |
|---|---|---|
| `PointLight` | `(0.90, 0.86, 0.74, 0.95)` | `(0.96, 0.92, 0.80, 0.98)` |
| `PointDark` | `(0.45, 0.20, 0.18, 0.95)` | `(0.33, 0.11, 0.10, 0.98)` |
| `BarColor` | yok (yumuşak alfa şerit) | `(0.11, 0.08, 0.06, 0.96)` — opak |
| `TrayColor` | yok | `(0.16, 0.12, 0.09, 0.82)` |
| `CenterLineColor` | yok | `(0.05, 0.035, 0.025, 0.55)` |
| `SpriteLibrary.CreateBar` | alfa ile solan şerit | opak, koyu kenarlı, iç highlight'lı kabartma |

`CenterLine` görseli tepsinin sol kenarına kadar uzanır ve yüksekliği
`max(2, boardHeight * 0.004)`'tür. Canlı oyuncuda orta hat boyunca örneklenen
parlaklık: bar bölgesi 12–29, oyun alanı 79–101 — kontrast gözle görülür.

**Yeni test envanteri.**

| Dosya | Kapsam |
|---|---|
| `Backgammon.UI.Tests\GameplayFix5Tests.cs` | 3 test: 25 oyunluk fuzz (her hamlede 15+15 taş), her iki renkte ev bölgesinde vurma sonrası 15 taş |
| `Unity\...\PlayMode\GameplayFix5PlayModeTests.cs` | 2 test: 3 rastgele oyunda her hamleden sonra 30 pulun görünmesi (15 beyaz + 15 siyah sprite), orta alan kontrastı (bar opaklığı > 0,85, bar parlaklığı < 0,20, hane parlaklık farkı > 0,35, `CenterLine` varlığı) |

### 43.11 Altıncı oynanış turu — bar tonu ve sahte orta çizgi

Kullanıcı iki görsel hata bildirdi: (1) kontrast değişikliğinden sonra **Siyah pul
kırıldığında** (bar üzerinde) neredeyse görünmez olması, (2) üçgenlerin buluştuğu
yerde **ince bir çizgi** çizilmiş gibi görünmesi ve tahtanın bütünlüğünü bozması.

**Bar tonu: koyu → açık ahşap.** §43.10'da bar neredeyse siyah yapılmıştı
(`0.11, 0.08, 0.06`). Siyah pulun gövdesi `(40, 42, 50)` yani parlaklık ~0,17; bar
ise ~0,09. Aradaki fark 0,08 — pul pratikte kayboluyordu. Orta ton da yetmedi:
tahta zemini koyu ahşap (parlaklık ~0,30–0,42) olduğu için orta tonlu bar yine
zemine karışıyordu. Çözüm **açık ahşap** tonudur; hem koyu zeminden hem iki pul
renginden net ayrılır.

| Öğe | §43.10 | §43.11 |
|---|---|---|
| `BarColor` | `(0.11, 0.08, 0.06, 0.96)` | `(0.70, 0.56, 0.40, 0.98)` |
| `TrayColor` | `(0.16, 0.12, 0.09, 0.82)` | `(0.66, 0.52, 0.37, 0.90)` |
| `CreateBar` gölge aralığı | `0.55 … 1.00` | `0.80 … 1.00` (kenar ×0,45) |

Ölçülen sonuç (canlı oyuncu, 1600×1000): bar parlaklığı **143,6/255 = 0,56**;
Siyah pul gövdesi 42,2/255 = 0,17 → fark **0,40**. Beyaz pul 0,93 → fark 0,37.
Bar sprite'ı eskiden kendi rengini 0,55'e kadar karartıyordu; gölge aralığı
daraltıldı ki ton korunsun.

**Siyah pula açık dış kontur.** Bar tonundan bağımsız güvence olarak
`SpriteLibrary.CreateChecker` artık dış banda ayrı bir `edge` rengi verir: Siyah
pul `(178, 184, 200)` (açık), Beyaz pul `(148, 140, 124)` (koyu). Böylece Siyah pul
koyu kırmızı hanede de (parlaklık ~0,18, gövdeyle neredeyse aynı) konturuyla
ayrılır. Alfa rampası `(1-d)*14` → `(1-d)*18` yapıldı; kontur 2–3 piksel kalınlıkta
ve doygun çizilir.

**Sahte orta çizgi kaldırıldı.** §43.10'da eklenen `CenterLine` görseli iki hane
satırının birleştiği yere 4 piksel kalınlığında koyu bir şerit çiziyordu; kullanıcı
bunu "üçgenlerin kesiştiği yerde ince bir çizgi" olarak gördü ve tahtanın
bütünlüğünü bozduğunu bildirdi. `CenterLineColor`, `_centerLine` alanı, görselin
oluşturulması ve yerleşimi tamamen silindi. Orta alanı ayırma işini artık **bar
tonu** yapar; ek bir çizgi gerekmez.

**Test güncellemesi.** `BoardMiddle_HasStrongContrast` yerine
`BoardMiddle_IsDistinct_AndBlackCheckerStaysReadable` yazıldı. Test artık:

- bar opaklığı > 0,85 ve **gerçek** parlaklığı (renk × sprite maskesi) 0,20–0,75
  aralığında,
- açık/koyu hane parlaklık farkı > 0,35,
- `CenterLine` **yok**,
- `|bar − Siyah gövde| > 0,15` ve `|bar − Beyaz gövde| > 0,15`,
- Siyah pulun dış konturu koyu haneden > 0,15 açık

koşullarını doğrular. Sprite maskeleri `Texture2D.GetPixels32()` ile okunur
(dokular `Apply(false, false)` ile okunabilir kalır).

### 43.12 Yedinci oynanış turu — koyu hanede Siyah pul görünürlüğü

Kullanıcı şunu bildirdi: "Siyah taş, beyaz taşı toplama bölgesine yakın noktalarda
(1, 2 ya da 3. nokta) kırdığında siyah taş gözükmüyor, 14 adet taş varmış gibi
görünüyor. Tavla engine değil de görsele aktarılan kısım hatalı olabilir." Ardından
sorunun **2. noktada** oluştuğunu doğruladı.

**Önce motor suçsuz ilan edildi.** `GameplayFix6PlayModeTests` içine
`Hit_OnDarkPoint2_KeepsThirtyCheckers_AndRendersHitter` eklendi. Test, Siyah 14 taş
6. noktada + 1 taş 5. noktada, Beyaz 1 blot 2. noktada + 14 taş 13. noktada
durumunu kurar, `SetDice(4, 4)` ile 6→2 vuruşunu oynar ve şunları doğrular:

- `board[2] == human`, `model.PointAt(2).Owner == human`, `Count == 1`,
- `WhiteBar.Count == 1`, `CountPieces(±1) == 15`,
- `CheckerPool.VisibleCount == 30`,
- 2. noktanın dikdörtgeni **içinde** tam olarak **1** Siyah pul var, boyutu sıfırdan
  büyük ve `Image.enabled == true`.

Test geçti: motor, `BoardViewModel` ve `CheckerPool` doğru çalışıyordu. Yerleşim
dökümü (`DumpPlacements`) vurucu Siyah pulu `pos=(969.83, -752.02)` noktasında,
2. noktanın `(969.83, -391.00) 90.08×391` dikdörtgeninin **içinde** gösterdi.

**Kök neden: saf kontrast.** Pul çiziliyordu ama görünmüyordu. Ölçüm:

| Öğe | Parlaklık (0–1) |
|---|---|
| `PointDark` (eski `0.33, 0.11, 0.10`) | 0,156 |
| Siyah pul gövdesi (eski `(40, 42, 50)`) | 0,165 |

Fark **0,009** — pratikte aynı renk. §43.11'de eklenen açık dış kontur 2–3 pikseldi
ve 60 piksel çapındaki pulda yeterince okunmuyordu.

**Palet düzeltmesi.**

| Öğe | §43.11 | §43.12 |
|---|---|---|
| `PointDark` | `(0.33, 0.11, 0.10, 0.98)` | `(0.26, 0.08, 0.07, 0.98)` |
| Siyah pul gövdesi | `(40, 42, 50)` | `(52, 56, 68)` |
| Siyah pul dış konturu | `(178, 184, 200)` | `(216, 222, 236)` |
| Beyaz pul dış konturu | `(148, 140, 124)` | `(104, 96, 82)` |
| Kontur bandı | `d > 0.84` | `d > 0.76` |

Kontur bandı yarıçapın ~%24'üne çıktı (60 piksel pulda ~7 piksel). Beyaz pulun
konturu da simetrik olarak koyulaştırıldı; aksi hâlde **açık** hanede Beyaz pul
aynı sorunu yaşıyordu (ölçülen fark 0,006).

**Ölçülen sonuç (canlı oyuncu, 1600×1000, `fix7_smoke.png`).** 24. nokta (koyu)
üzerindeki Siyah pul, yatay taramada:

- hane yüzü `(56, 20, 17)` → parlaklık 0,108,
- pul dış konturu `(216, 222, 235)` → 0,869 (fark **0,76**),
- pul gövdesi `(52, 56, 68)` → 0,220 (fark 0,11).

Açık hanedeki Beyaz pul: kontur `(104, 96, 82)` = 0,379, hane `(203, 194, 168)` =
0,761 (fark 0,38), gövde `(240, 236, 225)` = 0,926. Bar `(167, 134, 95)` = 0,542,
tepsi `(140, 108, 74)` = 0,44 — §43.11 tonları korundu, tahta bütünlüğü bozulmadı.

**Test güncellemesi.** `BlackChecker_OnDarkPoint_IsReadable` eklendi; `PointLight` /
`PointDark` alanlarını yansıma ile okur, `SpriteLibrary` dokularını 16 noktalı
halka örnekleyerek gerçek pul parlaklıklarını ölçer ve şu eşikleri doğrular:

- `lightLum − darkLum > 0.35`,
- `|blackEdge − darkLum| > 0.30`, `|blackBody − darkLum| > 0.08`,
- `|blackBody − lightLum| > 0.30`, `|whiteEdge − lightLum| > 0.30`,
- `|whiteBody − darkLum| > 0.30`, `|blackBody − whiteBody| > 0.30`.

**Ders.** "Taş kayboldu" şikâyeti her zaman durum hatası değildir. Önce yerleşimi
kanıtlayan bir test yazmak (kaç pul çizildi, hangi dikdörtgenin içinde) hatayı
motor ile görsel katman arasında kesin olarak böler; bu turda motoru temize
çıkardı ve tek bir palet düzeltmesine indirgedi.

### 43.13 Sekizinci oynanış turu — küp kilidi, açılış zarı ve tepsi görünümü

Üç ayrı şikâyet; ikisi motor, biri görsel.

**1. `x128` küp teklifi oyunu kilitliyordu (motor hatası).** Money game'de küp
`1 → 2 → 4 → 8 → 16 → 32 → 64` diye ikiye katlanır. `CanOfferAtTurnStart`
yalnızca Crawford ve ölü küp kurallarını kontrol ediyordu; **üst sınır yoktu**.
`64` iken yapılan teklif kabul edilince `cubeValue = 128` oluyor, `Take()`
`Refresh()` çağırıyor, `Refresh()` ilk iş olarak `MatchState.From(_state)`
yapıyor ve `MatchState` yapıcısı `cubeValue > 64` için
`ArgumentOutOfRangeException` atıyordu. İstisna `Changed` olayını hiç
tetiklemediği için tüm görünümler bayat kalıyordu: ne zar atılabiliyor ne taş
oynanabiliyordu.

Düzeltme iki katmanlı:

- `CanOfferAtTurnStart` artık `s.cubeValue >= MatchState.MoneyGameMaxCube`
  durumunda `false` döner. Böylece `64`'te teklif hiç kurulmaz; AI de teklif
  etmez (`GameBootstrap` `CanOffer` kontrolünü kullanır).
- `GameOrchestrator.Take()` / `Pass()` artık `phase != CubeOffered` ise hiçbir
  şey yapmaz. Savunma amaçlı: faz dışı bir çağrı küpü aralık dışına taşıyamaz.

Ayrıca "Kup" düğmesi `_cubeModel.CanOffer` değerine göre pasifleşir; oyuncu
teklif edilemeyen durumda düğmeye basıp "hiçbir şey olmuyor" sanmaz.

**2. Açılış zarında kimin hangi zarı attığı belli değildi.** Motor açılışta iki
zarı `rolledDice` içinde **sırasız** tutar (`RollOpening`: `d1`, `d2`, yüksek
olan başlar). Bu yüzden "sen/rakip" atfı motorda yapılamaz. `DiceView`'a
`SetOpeningRoll(humanDie, aiDie, humanStarts)` eklendi:

- kazananın zarı daima **büyük** olandır → `humanStarts` ise insanın zarı
  `max(d1,d2)`, değilse `min(d1,d2)`;
- her zarın altına `Sen` / `Rakip` etiketi yazılır (zar yüzleri 80 → 72 px,
  etiket bandı `y = 74`, kalan-zar satırı `y = 92`; panel yüksekliği 112
  değişmedi);
- kalan-zar satırı `acilis: sen X - rakip Y (sen basliyorsun)` gösterir.

Açılış gösterimi normal zar gösteriminden **önce** gelir (`_openingActive`).
`SetOverride` ve `SetCaption` açılış gösterimini kapatır; `ClearOpeningRoll`
açıkça temizler. `AnnounceOpeningRoll` gösterimi kurduktan hemen sonra
`DiceView.Refresh(_boardModel)` çağırır — `RollDice()` zaten `RefreshViews()`
tetiklediği için, o karede açılış gösterimi henüz kurulmamış olurdu ve etiketler
bir sonraki kareye (yani hiç) kalmazdı.

**3. Toplama alanı bar gibi görünmeliydi.** `SpriteLibrary.Tray` artık
`Bar`'ı döndürür (aynı sprite örneği) ve `BoardView.TrayColor = BarColor`.
Böylece doku, kenar kabartması ve opaklık **birebir** aynıdır. Eski tepsi
dokusu kenarlara doğru saydamlaşan 128×32 yatay bir şeritti; yenisi bar ile
aynı 32×128 dikey kabartma şerididir. **Genişlik ve yükseklik değişmedi**:
`BoardLayout` hâlâ `trayWidth = width * 0.08`, tepsi tam yükseklik.

**Ölçülen sonuç (canlı oyuncu, 1622×1056, `fix8_seq_13.png`).** Bar şeridi
`x 567..629`, tepsi `x 1173..1261`. Örneklenen yedi yükseklikte (200…800) her
iki şerit de **aynı** pikseli verir: `(177, 141, 101)`; ortalama `(170, 136, 97)`.
Açılış zarı karesinde (`fix8_seq_06.png`) etiketler: mavi `Sen` `x 1386..1407`
(merkez 1395) tam olarak birinci zarın (merkez 1396) altında, kırmızı `Rakip`
`x 1451..1482` (merkez 1466) ikinci zarın (merkez 1466) altında.

**Testler.**

- `Backgammon.UI.Tests/GameplayFix6Tests.cs` (yeni, 3 test):
  `CanOffer_AtMaxCubeValue_IsFalse`,
  `TryOfferDouble_AtMaxCubeValue_IsRefused_AndGameStaysPlayable`,
  `DoublingUpToMaxCube_KeepsStateValid_AndStopsAtMax`.
- `PlayMode/GameplayFix7PlayModeTests.cs` (yeni, 4 test):
  `CubeAtMaxValue_DoesNotFreezeGame_AndCubeButtonIsDisabled`,
  `OpeningRoll_LabelsWhichDieBelongsToWhom`,
  `OpeningRoll_IsVisibleImmediatelyAfterFirstRoll`,
  `Tray_LooksLikeBar_WithoutChangingSize` (aynı `Sprite.texture` örneği, aynı
  renk, doku tamamen opak, tepsi bar'dan geniş ve aynı yükseklikte).

**Ders.** Küp gibi sınırlı bir alanı ikiye katlayan her yol, alanın **üst
sınırını** da kontrol etmek zorundadır. `MatchState` sınırı biliyordu ama
`CanOffer` bilmiyordu; istisna da `Refresh()` içinde atıldığı için "oyun
dondu" olarak göründü — hata mesajı hiçbir yere yazılmadı.

### 43.14 Dokuzuncu oynanış turu — zar rastgeleliği

**Şikâyet.** "Zarlar her zaman aynı sıra ile geliyor; önce 5-2 sonra 6-6 gibi.
Random olması gerekiyor."

**Kök neden.** `GameBootstrap.Initialize` orkestratörü **sabit** bir tohumla
kuruyordu:

```csharp
Random = new Xoshiro256StarStar(0x7A71A_0005UL),
```

Motor deterministiktir ve rastgeleliği `IRandom` olarak **dışarıdan** alır
(Bölüm 3) — bu doğru tasarım, çünkü aynı tohum aynı oyunu üretir ve bu
benchmark/fuzz/self-play için zorunludur. Hata, **host** tarafında canlı oyuna
da sabit tohum verilmesiydi: her uygulama açılışında aynı zar dizisi geliyordu.

**Düzeltme.** `Backgammon.UI/DiceRandom.cs` eklendi:

- `DiceRandom.NewSeed()` → 64 bit tohum, `RandomNumberGenerator` (işletim
  sistemi CSPRNG'si) ile üretilir;
- `PlatformNotSupportedException` / `CryptographicException` durumunda
  `DateTime.UtcNow.Ticks ^ Guid.NewGuid().GetHashCode() ^ Environment.TickCount`
  yedeğine düşer;
- `DiceRandom.Create()` → `new Xoshiro256StarStar(NewSeed())`.

`GameBootstrap` artık `Random = DiceRandom.Create()` kullanır. Tohum **bir kez**,
orkestratör kurulurken alınır; `NewGame` / `NewMatch` aynı akışı sürdürür, yani
her yeni oyun dizinin devamını alır (yeniden tohumlamak akışı bozar ve
determinizmi anlamsız kılardı).

**Determinizm sözleşmesi korunur.** `Xoshiro256StarStar(seed)` değişmedi; aynı
tohum hâlâ aynı diziyi verir. Testler kendi sabit tohumlarını enjekte etmeye
devam eder (`GameplayFix6Tests`, `OrchestratorTests`, PlayMode testleri).

**Testler.**

- `Backgammon.UI.Tests/DiceRandomTests.cs` (yeni, 4 test):
  `NewSeed_ProducesDifferentValues` (32 çağrıda ≥31 farklı tohum),
  `Create_ProducesDifferentDiceSequences`,
  `Create_ProducesAllSixFaces` (600 atışta 1…6 hepsi),
  `FixedSeed_IsStillReproducible` (determinizm bozulmadı).
- `PlayMode/GameplayFix8PlayModeTests.cs` (yeni, 3 test):
  `Dice_AreNotFromTheOldFixedSeed` (canlı orkestratörün `_options.Random`'ı
  üzerinden 24 atış, eski sabit tohumun dizisiyle **aynı olmamalı**),
  `Dice_OpeningRollsVaryAcrossNewGames` (8 açılış zarı → en az 2 farklı çift),
  `Dice_SuccessiveRollsVary` (40 atış → en az 11 farklı çift).

**Ölçülen sonuç (canlı oyuncu, iki ayrı başlatma).** Açılış zarı kareleri
(`fix9_a_18.png`, `fix9_b_18.png`) piksel farkı: zar bölgesinde 962 piksel
> 20 fark. Zar yüzlerindeki pip sayısı (bağlı bileşen sayımı):

| Başlatma | 1. zar | 2. zar |
|---|---|---|
| A | 6 | 1 |
| B | 4 | 2 |

Aynı karelerde `Sen` / `Rakip` etiketleri de görünür durumda — §43.13'teki
açılış gösterimi rastgelelik düzeltmesinden etkilenmedi.

**Ders.** Deterministik motor tasarımı, host'un da deterministik olması
gerektiği anlamına gelmez. Tohum **motorun** değil **uygulamanın** kararıdır;
varsayılan değer her zaman işletim sisteminden gelmelidir, sabit tohum ise
yalnızca testlerde açıkça verilmelidir.

### 43.15 Dokuzuncu oynanış turu — bayat `Hit` bayrağı ve taş kaybı

**Şikâyet.** "Siyah ile oynarken 6-4 zar geldi. 8 ve 6'dan Beyaz'ı 2'de kırdım,
kapı almam gerekiyorken 2'nin üzerinde tek bir siyah taş vardı. İlerleyen oyunda
da orada tek taş göründü, toplamda 14 siyah taş verdi."

**Kök neden — `MoveInputController`'ın adım projeksiyonu.** Girdi katmanı,
oynanacak adımı `LegalMoveGenerator.GenerateAllLegalMoves` çıktısının **tüm**
adımlarını tarayarak buluyordu:

```csharp
for (int m = 0; m < moves.Count; m++)
{
    MoveSequence seq = moves.Moves[m];
    for (int k = 0; k < seq.Count; k++)   // <-- k > 0 tehlikeli
    {
        if (seq[k].From == from && seq[k].To == to) { ... }
    }
}
```

`GenerateAllLegalMoves` **maksimum uzunluktaki** dizileri üretir ve aynı son
duruma ulaşan dizileri Zobrist hash ile tekilleştirir. Bir dizinin `k > 0`
adımı, dizinin **kendi ara durumuna** aittir; o adımın `MoveFlags.Hit` biti
güncel (taban) duruma göre **bayattır**.

Somut olay: 6→2 (kırış) oynandıktan sonra kalan zar yeniden üretilir. Taban
listede `8->2 d6 f1 | 6->2 d4 f0` dizisi vardır; `8->2` adımı `Hit` bayrağıyla
bulunur. Oysa 2 numaralı hanede artık **kendi** taş vardır. `ApplyStep`, `Hit`
görünce:

```csharp
s.board[oppBar] += opp;
s.board[step.To] = 0;      // <-- az önce konan kendi taşını siler
s.board[step.To] += turn;
```

Sonuç: 14 siyah taş, 2'de tek siyah taş, boş bar. Şikâyetle birebir aynı.

Aynı tarama ikinci bir kusur da üretiyordu: `k > 0` adımlarının `From` alanı
bir **ara** hane olduğu için, o anda **boş** olan hanelerden hedef teklif
edilebiliyordu (ör. 3 boşken `3->2`).

**Neden "listede var mı?" filtresi de yanlış.** İlk düzeltme denemesi
`GenerateStepsFrom` çıktısını "bu `(From, To, Die)` üçlüsü hamle listesinde
geçiyor mu?" ile süzüyordu. Bu da hatalıdır: tekilleştirme yüzünden bazı
**yasal ilk adımlar** listede hiç görünmez. Örnek: 3-1 açılışında `19->22`
adımı yoktur, çünkü `19->20->23` aynı son duruma ulaşır ve tekilleştirmede
kazanan odur. Listeye bakan bir arayüz oyuncudan **yasal bir hamleyi saklar**.

**Düzeltme — motorda iki yeni API.**

1. `LegalMoveGenerator.GenerateStepsFrom(BackgammonState s, int fromPoint,
   MoveStep[] buffer)` — verilen **güncel** durumdan, kalan her zar için tek
   adımlar üretir (özel `GenerateSteps` yeniden kullanılır). Bayraklar her
   zaman günceldir; boş haneden adım çıkmaz. Maksimum uzunluk ve büyük zar
   kurallarını uygulamaz.

2. `LegalMoveGenerator.GenerateFirstSteps(BackgammonState s, MoveList
   maxLengthMoves, int fromPoint, MoveStep[] buffer)` — arayüzün kullanması
   gereken **doğru** projeksiyon. `GenerateStepsFrom` çıktısındaki her aday
   için:

   ```
   probe.CopyFrom(s); ApplyStep(probe, step);
   rest = MaxSequenceLength(probe, restrictDie, 1);
   keep  <=>  1 + rest == maxCount
   ```

   `maxCount = maxLengthMoves.Moves[0].Count`, `restrictDie =
   ResolveBigDieRestriction(s, maxCount)`. Böylece "bu ilk adım oyuncuyu
   maksimum uzunlukta bir diziye götürüyor mu?" sorusu **tekilleştirmeden
   bağımsız** olarak, kaba kuvvetle aynı sonucu vererek yanıtlanır.

   `MaxSequenceLength` özyinelemeli bir DFS'tir (`StepBuf[depth]`,
   `ApplyStep`/`UndoStep`, `depth > MoveSequence.MaxSteps` koruması) ve en
   uzun devamı döndürür. Kopya durum `[ThreadStatic] _probeState` üzerindedir;
   çağıranın durumu **asla** değişmez.

`MoveInputController.CollectTargets` ve `TryFindStep` artık
`GenerateFirstSteps` çağırır; `IsInMaxLengthMove` silindi.

**Savunma katmanları.** İki ek koruma eklendi:

- `BackgammonEngine.ApplyStep` içinde
  `DebugAssert(!step.IsHit || s.board[step.To] == -turn, "Hit adımında hedefte
  tam olarak bir rakip taş olmalı.")` — bayat bayrak artık sessizce taş
  silmek yerine hata verir. (`DebugAssert` Release'te de **fırlatır**.)
- `GameOrchestrator.ApplyMove` hamleyi önce bir **kopya** duruma uygular,
  iki tarafın taş sayısını karşılaştırır ve korunmadıysa hamleyi reddeder
  (`Debug.Assert(false, ...)`). Yani hatalı bir hamle tahtaya hiç ulaşmaz.

**Testler.**

- `Backgammon.UI.Tests/GameplayFix9Tests.cs` (yeni, 6 test):
  `Position_IsValid`, `Engine_ApplyMove_HitThenStack_KeepsFifteenEach`,
  `InputController_HitThenStack_KeepsFifteenEach`,
  `InputController_ReverseOrder_KeepsFifteenEach` (şikâyetteki sıra),
  `EveryLegalMove_ConservesCheckers` (40 rastgele pozisyon),
  `InputController_EveryProjectedStep_ConservesCheckers`
  (8 pozisyon × 26 kaynak hane).
- `Backgammon.Tests/FirstStepProjectionTests.cs` (yeni, 6 test) — tamamen
  bağımsız kaba kuvvet oracle'ı (`BruteForceMaxLength`, `AllStepsForDie`,
  `BruteForceFirstTargets`):
  `StepsFrom_EmptyPoint_YieldsNothing`,
  `StepsFrom_EveryStepIsApplicableAndConservesCheckers`,
  `FirstSteps_MatchBruteForceOracle` (25 pozisyon × 26 hane),
  `FirstSteps_IncludeDedupedAwayFirstMove` (3-1 açılışında hem `19->20` hem
  `19->22` teklif edilmeli),
  `FirstSteps_RespectBarPriority`,
  `FirstSteps_RespectBigDieRestriction`.
- `Backgammon.UI.Tests/ViewModelTests.MoveInputController_LegalTargets`
  beklentisi de `GenerateFirstSteps` ile kurulacak şekilde yeniden yazıldı;
  eski beklenti hatalı semantiği (tüm adımları tarama) kodluyordu.
- `PlayMode/GameplayFix9PlayModeTests.cs` (yeni, 2 test) — gerçek
  `GameBootstrap` + `BoardInputController` + `BoardViewModel` üzerinden
  şikâyetteki pozisyon: `HitThenStack_KeepsFifteenCheckersEach` ve
  `ReverseOrder_KeepsFifteenCheckersEach`. Her ikisi de motor tarafında
  15/15 taş, bar'da 1 Beyaz, 2'de 2 Siyah; görsel modelde de aynı sayıları
  doğrular.

**Doğrulama.** `Backgammon.UI.Tests` 61/61, `FirstStepProjectionTests` 6/6,
hedefli `Backgammon.Tests` (LegalMoveGenerator/CubeAndMatch/Fuzz) 65/65,
Unity PlayMode 36/36, EditMode 7/7, `BuildWindows64` başarılı.

**Ders.** Bir arama motorunun **çıktısı** (tekilleştirilmiş, en iyi/en uzun
diziler) ile **girdi katmanının ihtiyacı** (bu haneden şu an hangi adımlar
yasal) aynı şey değildir. Arayüz, motorun iç temsili üzerinden akıl
yürütmemeli; ihtiyacı olan soruyu motorun **kendi API'siyle** sormalıdır.
Ayrıca: bir bayrak alanı (`MoveFlags`) yalnızca üretildiği durum için geçerlidir;
durum değiştiğinde bayrak da yeniden üretilmelidir.

---

### 43.16 Onuncu tur — renk değiştirince tahtanın bakış açısı

**İstek.** "Renk değiştir seçeneği tercih edildiğinde (varsayılan Siyah) beyaz
renk siyah, siyah renk beyaz olsun; yani taşları oyuncu her iki renkte de aynı
yöne hareket ettirmiş olsun."

**Kök neden.** Motor Beyaz'ı `1 -> 24`, Siyah'ı `24 -> 1` yönünde hareket
ettirir. Tahta yerleşimi renkten bağımsız olduğu için (§43.12) oyuncu Beyaz
oynadığında kendi taşları ekranda **ters yöne** gidiyor gibi görünüyordu:
Siyah oynarken ev bölgesi sağ altta ve taşlar aşağı doğru akarken, Beyaz
oynarken ev bölgesi sağ üstte ve taşlar yukarı doğru akıyordu. Yalnızca
tepsilerin yer değiştirmesi (`HumanTrayBottom`) bu algıyı düzeltmiyordu.

**Çözüm — hane numaralarını 180° döndür.** `BoardLayout` artık bir `flip`
parametresi alır. `flip == true` iken hane `p`, **görsel yuvaya** `25 - p`
çizilir:

```
görsel yuva = flip ? (25 - hane) : hane
```

`BoardLayout.VisualSlot(point)` bu eşlemeyi verir; `PointAt(point)` artık
`Points[VisualSlot(point) - 1]` döndürür. `Points` dizisi **görsel yuvaya**
göre indekslidir (eskiden hane numarasına göreydi; aynalamasız durumda ikisi
aynıdır).

Oyuncu Beyaz oynarken `flip = true`:

| | Siyah oynarken | Beyaz oynarken |
|---|---|---|
| Oyuncunun ev bölgesi | 1..6 → yuva 1..6 (sağ alt) | 19..24 → yuva 6..1 (sağ alt) |
| Rakibin ev bölgesi | 19..24 → yuva 19..24 (sağ üst) | 1..6 → yuva 24..19 (sağ üst) |
| Oyuncunun hareketi | yuva `p -> p - z` | yuva `25-p -> 25-p-z` = aynı yön |
| Oyuncunun toplama kenarı | yuva 1 (sağ alt) | yuva 1 (sağ alt) |

Yani oyuncunun taşları **her iki renkte de görsel yuvayı küçültür** (sağ alta
doğru akar) ve ev bölgesi **her zaman sağ altta** kalır.

**Değişmeyenler (bilinçli).** Tahta çerçevesi, bar şeridi ve tepsi şeridi
aynalanmaz; yalnızca hane numaraları döner. `BoardLayout.Calculate(w, h,
humanTrayBottom, flip)` bu iki kararı **ayrı** tutar: tepsi yarımları
`humanTrayBottom`'a, hane yönü `flip`'e bağlıdır.

**Üçgen rengi.** Renk hane numarasına değil **görsel yuvaya** göre seçilir
(`BoardView.Recalculate` → `SetFaceColor(PointColor(_layout.VisualSlot(point)))`).
Aksi halde aynalama açık/koyu deseni de döndürür ve tahta "başka bir tahta"
gibi görünürdü. Bu sayede iki bakış açısında ekrandaki desen **birebir aynı**.

**Bar yarımları.** Eskiden sabitti (Beyaz üst, Siyah alt). Artık ev
bölgelerini izler: `whiteBarBottom = PointAt(19).Y >= height/2`. Böylece her
oyuncunun kırık taşları kendi ev bölgesine yakın yarımda birikir. Varsayılan
Siyah için sonuç **eskisiyle aynıdır** (Beyaz üst, Siyah alt); yalnızca Beyaz
oynanırken takas olur.

**Dokunulan dosyalar.**

- `Backgammon.UI/BoardLayout.cs` — `_flip` alanı, `Flip` ve `VisualSlot`,
  `Calculate(w, h, humanTrayBottom, flip)` aşırı yüklemesi; `PointAt` artık
  `VisualSlot` üzerinden.
- `Assets/Backgammon.UI/Scripts/Board/BoardView.cs` — `FlipPoints` özelliği
  (değişince yerleşim önbelleğini geçersiz kılar), `Recalculate` flip'i geçirir,
  üçgen rengi görsel yuvaya göre atanır, bar yarımları ev bölgesinden türetilir.
- `Assets/Backgammon.UI/Scripts/Board/BoardPointView.cs` — `SetFaceColor`.
- `Assets/Backgammon.UI/Scripts/Bootstrap/GameBootstrap.cs` —
  `ApplyPlayerColor` artık `BoardView.FlipPoints = _humanPlayer > 0` de yapar.

**Girdi katmanı.** `BoardInputController` ham motor hane numaralarıyla çalışır
ve `_board.Points[point - 1].Rect` üzerinden isabet testi yapar. `Points[i]`
görsel yuva `i + 1`'in dikdörtgenini tuttuğu ve `BoardPointView.Point` hâlâ
motor hane numarası olduğu için tıklama/sürükleme **hiç değişmeden** doğru
çalışır.

**Testler.**

- `Backgammon.UI.Tests/BoardPerspectiveTests.cs` (14 test): `VisualSlot`
  eşlemesi ve permütasyon olması, aralık denetimi, aynalamada hane
  dikdörtgenlerinin ayrık ve tahta içinde kalması, tahta/bar/tepsi
  dikdörtgenlerinin değişmemesi, `PointAt` ile `Points[VisualSlot]`
  tutarlılığı, oyuncunun ev bölgesinin her iki renkte sağ altta olması,
  oyuncunun taşlarının her iki renkte **aynı görsel yön**de gitmesi
  (`VisualSlot(hedef) == VisualSlot(kaynak) - zar`), toplama kenarının sağ
  altta olması, `flip` ile `humanTrayBottom` bağımsızlığı.
- `Assets/Backgammon.UI/Tests/PlayMode/GameplayFix10PlayModeTests.cs`
  (3 test): `FlipPoints` hane 1 ile 24'ün yerini takas eder ve bar yarımlarını
  takas ederken tepsi yerini korur; her iki flip durumunda da her pul **kendi**
  hanesinin dikdörtgeni içinde kalır; her iki renkte oyuncunun ev bölgesi sağ
  altta, rakibinki sağ üstte ve toplama kenarı sağ altta.
- `GameplayFix4PlayModeTests.HumanTray_IsBottomRight_ForBothColors`
  güncellendi: eski "hane dikdörtgenleri renkten bağımsız kalmalı" beklentisi
  artık geçersiz (aynalama tam olarak bunu değiştirir); yerine `FlipPoints`
  bayrağı ve ev bölgesinin sağ altta kalması doğrulanıyor.

**Doğrulama.** `Backgammon.UI.Tests` 75/75, Unity PlayMode 39/39, EditMode 7/7,
`BuildWindows64` başarılı. Canlı oyuncu karşılaştırması (aynı ikili, iki
başlatma, `tavla.color` kayıt defteri anahtarıyla Siyah/Beyaz):
bar şeridinde **0** farklı piksel, tepsi şeridinde 109.716 pikselin 585'i
(%0,5 — yalnızca toplanmış taşlar), açık/koyu üçgen piksel sayıları %3
içinde (99.471/153.054 ve 102.220/156.029), toplam 103.915 piksel farklı
(taşlar aynalandı). Yani tahta çerçevesi ve desen **birebir aynı**, taşlar
aynalanmış.

**Ders.** "Tahta dönmesin" ile "taşlar aynı yöne gitsin" çelişmez: döndürülen
şey tahta değil, **hane numaralarının yerleşimidir**. Çerçeve, bar ve tepsi
sabit kalırken hane eşlemesi 180° döndürüldüğünde oyuncunun ev bölgesi ve
hareket yönü her iki renkte aynı olur. Ayrıca bir görsel öğenin rengi,
"hangi numaralı hane" sorusuna değil "ekranın neresi" sorusuna bağlanmalıdır;
aksi halde aynalama deseni de döndürür.

---

### 43.17 On birinci tur — orta bant (ucgen uclari birlesmiyor)

**Istek.** "Tavla tahtasindaki asagidaki ucgenin uc noktasi ile yukaridaki ucgenin uc
noktalari birbirine cok yakin; gercek bir tavla tahtasinda ust ucgen ile alt ucgen arasinda
bir miktar mesafe olmali. (Belki ileride logo vs koyabilirim orta alana.)"

**Kok neden.** `BoardLayout` iki hane satirini tam olarak tahta yuksekliginin yarisina
oturtuyordu (`rowHeight = height * 0.5`). Ucgen sprite'inin ucu dikdortgenin kenarinda
bittigi icin ust satirin ucu ile alt satirin ucu **ayni cizgide** bulusuyordu. Gercek bir
tahtada ucgen uclari orta cizgide birlesmez; arada tahta yuzeyi gorunur.

**Cozum — orta bant.** `BoardLayout` iki satiri `CenterGapRatio` kadar ayirir:

```
centerGap   = height * CenterGapRatio        // 0.06
gapHalf     = centerGap * 0.5
pointHeight = rowHeight - gapHalf

ust satir : Y = 0,               H = pointHeight
alt satir : Y = rowHeight + gapHalf, H = pointHeight
```

Boylece ust satirin alt kenari `rowHeight - gapHalf`, alt satirin ust kenari
`rowHeight + gapHalf` olur; aradaki bosluk tam olarak `centerGap`'tir. Ucgen uclari bandin
kenarinda biter, banda **girmez**.

**Neden 0.06?** 1080 px yuksekliginde ~65 px, canli oyuncuda (774 px tahta) ~46 px
hesaplanan bant; sprite'in ucundaki saydamlik/anti-aliasing ile birlikte ekranda ~60 px
gorunur (tahta yuksekliginin ~%7,8'i). Daha kucuk degerde uclar yeniden "birlesik" gorunur,
daha buyuk degerde haneler kisalir ve 15'lik yiginlar sikisir.

**Yeni API.**

- `BoardLayout.CenterGapRatio` (`const float`, `0.06`).
- `BoardLayout.CenterGap` — bandin yuksekligi (piksel).
- `BoardLayout.CenterBand` — bandin dikdortgeni (tam tahta genisligi). Ileride logo/rozet
  yerlestirmek icin hazir; bar ve tepsi seritleri bu bandin uzerinden **kesintisiz** gecer
  (gercek tahtada da oyledir), bu yuzden bant "oyun alani" bandidir.

**Bozulmayanlar.**

- Bar ve tepsi seritleri hala **tam yuksekliktedir**; orta bant onlari bolmez.
- `flip` (bakIs acisi) ve `humanTrayBottom` bant konumunu/olculerini **degistirmez**.
- Hane dikdortgenleri hala birbiriyle kesismez ve tahta sinirlari icindedir.
- Pullar hala **kendi** hanesinin dikdortgeni icinde kalir; orta banda tasmaz. Pul boyutu
  `min(genislik, yukseklik/6) * 0.92` oldugu icin bant kadar (~%6) kuculur; 15 pul hala
  haneye tam sigar (`step = (H - size) / 14`).
- Orta banda tiklamak hicbir haneyi secmez (`BoardInputController.HitTest` `-1` doner);
  bant gorsel bir ayiricidir, hedef degildir.

**Dokunulan dosyalar.**

- `Backgammon.UI/BoardLayout.cs` — `CenterGapRatio`, `CenterGap`, `CenterBand`, bant
  hesabi ve iki satirin yeni `Y`/`Height` degerleri.
- `Backgammon.UI.Tests/GameplayFix2Tests.cs` — iki test `PointAt(1).Y == 250f` gibi
  **tam yarim yukseklik** bekliyordu; artik "hane 1 bandin altinda, hane 24 bandin ustunde"
  olcutu kullaniliyor (bant eklendigi icin satirlar tam yaridan baslamaz).

**Testler.**

- `Backgammon.UI.Tests/BoardCenterGapTests.cs` (10 test): bant her en-boy oraninda pozitif
  ve yukseklikle orantili; genislik degisince bant degismiyor; ust/alt hane dikdortgenleri
  bandin dogru tarafinda; `CenterBand` satirlar arasi bosluga birebir esit; bant tam tahta
  genisliginde; bant hicbir haneyle kesismiyor; `flip`/`humanTrayBottom` bandi
  degistirmiyor; bar ve tepsi tam yukseklikte; hane dikdortgenleri hala ayrik ve tahta
  icinde; 15 pul hala haneye sigiyor.
- `Assets/Backgammon.UI/Tests/PlayMode/GameplayFix11PlayModeTests.cs` (4 test): **gercekten
  cizilen** `BoardPointView.Rect` dikdortgenleri olculerek uclar arasinda bosluk oldugu ve
  bunun `height * CenterGapRatio` oldugu; bosluk her iki renkte ayni; bar ve tepsi
  yarimlari birlesince tam yukseklik kaplandigi; acilis diziliminde **hicbir pulun** orta
  banda girmedigi.

**Dogrulama.** `Backgammon.UI.Tests` 85/85, Unity PlayMode 43/43, EditMode 7/7,
`BuildWindows64` basarili. Canli oyuncu (1622x1056, tahta 1469x774): ust satirin ucu
`y=356`, alt satirin ucu `y=417` -> ekranda **60 px** bosluk (hesaplanan 46 px + sprite
ucundaki saydamlik). Siyah ve Beyaz bakis acilarinda bant ayni.

**Ders.** Bir gorsel ogenin "ucu" dikdortgenin kenarinda bitiyorsa, iki ogeyi ayirmanin yolu
onlari farkli dikdortgenlere koymaktir; sprite'a bosluk cizmek yerine **yerlesimi** ayirmak
hem test edilebilir hem de olcek bagimsizdir. Ayrica "satir yuksekligi = tahta/2" gibi bir
varsayim, tahtaya sonradan eklenen her dekoratif bant tarafindan bozulur; bu yuzden
satirlarin konumu tek bir sabitten (`CenterGapRatio`) turetilmelidir.

## 44. Faz 6 — Aşama A: ölçüm hattı ve taban kilidi

Faz 6'nın ilk aşaması güç değil **ölçüm** aşamasıdır. Bundan sonraki her iyileştirme tek
bir dondurulmuş referans küme üzerinde, aynı gnubg sürümüyle, aynı ply'de ölçülür.

### 44.1 Neden yeni bir hat?

Faz 4'te yazılan `ml/gnubg_er.py` ölçümü **doğru** yapıyordu ama **yeniden üretilebilir
değildi**: vaka dosyası 57 pozisyondu, 50'si kullanılabiliyordu, bölünme yoktu ve
istatistiksel güç raporlanmıyordu. 0,1941 sayısı bu yüzden tek bir koşuya bağlıydı.

`ml/er_harness.py` bu boşluğu kapatır ve **`gnubg_er.py`'yi olduğu gibi kullanır**:
vektörleştirme, gnubg oturumu, afterstate değerlendirmesi ve ER tanımı tek bir yerde
kalır (Kural 3). Yeni modül yalnız küme, bölünme, güç, veri hacmi ve rapor katmanlarını
ekler.

### 44.2 Referans küme

`ml/artifacts/reference_corpus_v1.json` — 200 pozisyon, tohum `20261114`,
SHA-256 `ad85265177515b41fb5e95b3904c231966ececd6928db178be0d84473469d072`.

Rastgele oyun `race`, `bearoff` ve özellikle `closed` fazlarını neredeyse hiç üretmez
(ölçüldü: 600 adayda `closed` = 0). Bu yüzden üç faz **parametrik ailelerle** kurulur:

| Aile | Kurulum |
|---|---|
| `_closed_positions` | Siyahın 1..6 haneleri 2'şer taşla kapalı; kalan 3 siyah taşı 8..18'de; beyaz 7..24'e dağıtılır ve **7 numarada en az bir beyaz taş** teması garanti eder |
| `_race_positions` | Siyah 1..8, beyaz 11..18: siyahın en ileri taşı beyazın en geri taşının gerisinde (temas yok), beyaz evde olmadığı için bearoff da değil |
| `_bearoff_positions` | Beyazın 15 taşı 19..24'te; siyah 1..12'de (beyazın evi yalnız beyazın) |

`contact` ve `bar` tohumlu rastgele oyundan gelir. Küme **tahta düzeyinde** tekilleştirilir:
aynı tahta iki kez sayılmaz, çünkü aynı tahta bölünmeler arasında sızıntıdır (Kural 10).

Faz dağılımı: temas 39, yarış 40, bearoff 37, bar 40, kapalı tahta 44 (Test 45: her biri ≥ 20).

### 44.3 Bölünme ve sızıntı koruması

Bölünme **faz katmanlı** ve deterministiktir: her fazın üyeleri tohumla karıştırılır, sonra
%30 / %35 / %35 oranıyla CAL / VAL-ER / TEST-ER'e dağıtılır → **60 / 70 / 70**.

* Üç küme ayrıktır ve **tahta paylaşmaz** (Test 44).
* Model seçimi yalnız **VAL-ER** üzerinden yapılır; TEST-ER'e erişim
  `ml/runs/<ad>/test_access.log` dosyasına yazılır (Bölüm 8.7).
* CAL yalnız kalibrasyon içindir (Bölüm 6.4).

### 44.4 Ölçülen taban

| Ölçüm | Değer |
|---|---|
| 41a — Faz 5 değerinin yeniden üretimi (50 pozisyon) | **0,1941** (fark 0,0000; tolerans ±0,01) |
| 41b — 200 pozisyon ortalama ER | **0,2203** (medyan 0,1325, maks 1,6770, eşleşme %14,0) |
| 41b — CAL / VAL-ER / TEST-ER | 0,3013 / 0,1898 / 0,1820 |
| 46 — standart hata (200 pozisyon) | 0,0187; hedef SE 0,005 için gereken n ≈ 2 786 |
| 41e — veri hacmi (100 oyun, 9 088 karar) | **3 824 bayt/karar** ham, **129 bayt/karar** gzip |
| 41c — `OutcomeDistribution` kodlaması | **kümülatif** |
| 41d — `resultType` `winner` içeriyor mu | **hayır** (yalnız çarpan 1/2/3) |
| 48 — gnubg | `GNU Backgammon 1.08.003-mingw 32-Bit 20240428`, 2-ply, cubeless, money |

**41c ayrıntısı.** `OutcomeDistribution` alanları `Win`, `WinGammon`, `WinBackgammon`,
`LoseGammon`, `LoseBackgammon`; `Lose = 1 − Win` türetilir ve değişmez
`WinBackgammon ≤ WinGammon ≤ Win`'dir. Yani sınıf **kümülatif** (gnubg geleneği) kodlama
kullanır. Faz 6'nın `FromProbabilities` metodu **dışlayıcı** girdi alıp sınıf içinde bu
kodlamaya dönüştürecektir (Bölüm 5.1).

**41d ayrıntısı.** `GameResultType` = `{None=0, Single=1, Gammon=2, Backgammon=3}` yalnız
çarpanı taşır; `SelfPlayRunner` `game.Winner` ve `game.ResultType`'ı **ayrı** alanlara
yazar. 6 sınıflı hedef türetilirken `winner` ayrı alandan okunmalıdır.

**41e ayrıntısı.** v1 belgesindeki "11,5 KB/karar" iddiası ölçümle **çürütüldü**: gerçek
değer 3 824 bayt/karar (ham) ve 129 bayt/karar (gzip). `log_top_candidates = 12` olduğu
için ham boyut büyüktür; disk maliyeti sıkıştırmayla ~30 kat düşer.

### 44.5 Ölçümün kendi sınırı

200 pozisyonluk kümede standart hata **0,0187**'dir. Faz 6'nın hedefi 0,01–0,02 ER
olduğuna göre bu küme hedefi **ayırt edemez**; Test 46'nın çıktısı (n ≈ 2 786) referans
kümenin ilerleyen aşamalarda büyütülmesi gerektiğini söyler. Bu, ölçümün kendi sınırını
önceden bildirmesidir — bir kusur değil, tasarım gereğidir.

### 44.6 Determinizm ve uydurma değer yasağı

* Aynı tohum → aynı küme (SHA-256 sabit), aynı model + CPU → aynı ER (Test 42).
* gnubg yoksa hat sıfır olmayan çıkış kodu döner ve **hiçbir sayı üretmez** (Test 43);
  `stage_f_baseline.md` yazılmaz.
* Rapor `ml/er_harness.py` tarafından **üretilir**; hiçbir sayı elle yazılmaz.

### 44.7 Yeniden üretim

```bash
python ml/er_harness.py build-corpus
python ml/er_harness.py verify-corpus
python ml/er_harness.py legacy --model ml/artifacts/model_stage_d_v10.onnx --limit 50
python ml/er_harness.py measure --model ml/artifacts/model_stage_d_v10.onnx --split all
python ml/er_harness.py data-volume --shards ml/runs/stage_d/shards/it10
python ml/er_harness.py baseline --model ml/artifacts/model_stage_d_v10.onnx --shards ml/runs/stage_d/shards/it10
```

**Dogrulama.** `ml/tests` **194/194** (1 yavaş test varsayılan atlanır), belge tutarlılığı
21/21. Aşama A testleri: 41a, 41b, 41c, 41d, 41e, 42, 43, 44, 45, 46, 47, 48.
## 45. Faz 6 — Aşama B: 6 çıktılı değer kafası, `output_version = 2` ve kalibrasyon

Aşama A ölçtü; Aşama B **değer kafasını değiştirir**. Faz 5'in tek skaler değer kafası
oyun sonucunun *büyüklüğünü* (mars/backgammon payını) temsil edemiyordu: kalibrasyon
eğimi 0,2431, MAE 0,8014, std oranı 2,78 — ağ equity'nin yönünü kısmen biliyor ama
büyüklüğünü fena halde abartıyordu. Bu bölüm kafanın nasıl değiştiğini, ONNX
sözleşmesinin nasıl evrildiğini ve teşhisin ne bulduğunu anlatır.

### 45.1 Neden 6 sınıf?

Tek skaler değer kafası `E ∈ [−3, +3]` üretir ama **dağılımı** üretmez. Küp kararı
(Bölüm 10.3) ve maç farkındalığı mars/backgammon olasılıklarını ayrı ayrı ister; skaler
kafadan bunları geri kazanmanın yolu yoktur. Dışlayıcı 6 sınıf hem equity'yi hem
dağılımı verir ve `E` doğrusal bir fonksiyonla türetilir — yani kafa **daha fazla bilgi**
taşır, aynı sayıyı üretir.

### 45.2 Dışlayıcı kodlama ve equity

| Sıra | Sınıf | Anlam | Ağırlık |
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

İki equity ifadesi cebirsel olarak **aynıdır**; Test 49 (C#) ve Test 53 (Python) bunu
sayısal olarak doğrular. `ml/equity.py` bu formülün Python aynasıdır ve **tek doğruluk
kaynağı C# tarafıdır** (Kural 3): Test 53 ayrıca C# kaynağındaki ifade metnini okuyup
beklenen biçimde durduğunu denetler, böylece iki taraf sessizce ayrışamaz.

**Monotonluk zorlanmaz.** Dışlayıcı sınıflar arasında `W ≥ GW ≥ BW` gibi bir zorunlu
sıralama yoktur (bir oyuncu çoğu zaman tek kazanırken mars da kazanabilir). Kümülatif
değişmezler (`WinBackgammon ≤ WinGammon ≤ Win`) dönüşümden **kendiliğinden** sağlanır;
`FromProbabilities` bunları kırpma ile garanti eder ama dışlayıcı değerleri değiştirmez.

**Geçersiz dağılım nötr değer üretir.** `FromProbabilities` negatif, NaN, sonsuz veya
toplam 0 girdide `IsValid = false` döner. Bu durumda `Equity` **0,0** verir (F6-09):
`Win = 0` olduğu için `Lose = 1 − Win = 1` oluyor ve eski kod **−1,0** döndürüyordu —
"nötr" değil "kesin kayıp" gibi okunan yanıltıcı bir sayı.

### 45.3 `output_version = 2` ONNX sözleşmesi

| Alan | v1 | v2 |
|---|---|---|
| Girdi | `features [batch,221]` | `features [batch,221]` |
| Çıktı | `value [batch,1]`, `policy_logit [batch,1]` | `probs [batch,6]`, `policy_logit [batch,1]` |
| `output_version` | `1` | `2` |
| `prob_order` | — | `W,GW,BW,L,GL,BL` |
| `prob_encoding` | — | `exclusive` |

`OnnxModelHandle.SupportedOutputVersion` **2**'dir. `output_version = 1` modeller **bit
düzeyinde aynı** çalışmaya devam eder (Test 58); `output_version = 3` reddedilir.

**Metadata sürüm kontrolünden önce doğrulanır** (F6-10). Sürüm 2'nin tek anlamı "6
çıktı, dışlayıcı, bu sırayla"dır; sıra metadata'da yazılı değilse handle modeli yanlış
yorumlayabilir ve `W` ile `L` yer değiştirirse equity işaret değiştirir — sessiz ve çok
pahalı bir hata. Eksik metadata `InvalidDataException`, desteklenmeyen sürüm
`NotSupportedException` fırlatır.

`ml/export_onnx.py` `--output-version {1,2}` ve `--profile` alır; `BackgammonNetV2`
`(probs, policy_logit)` döndürür. `ml/artifacts/model_output_version_2.onnx` gerçek v2
grafiğidir (mimari `221-256-256-128`, PyTorch ↔ ORT paritesi **5,96e-08**).

### 45.4 Kayıp fonksiyonu

```
L = c_value · L_value + c_policy · L_policy + c_cal · L_cal
L_value = −Σ_i t_i · log p_i          (6 sınıflı çapraz entropi)
L_cal   = mean((E_pred − E_target)²)  (equity kalibrasyonu)
```

`c_value = 1,0`, `c_cal = 0,1` (Faz 6 §5.3). `L_cal` **tek başına CE'nin garanti
etmediği** şeyi zorlar: dağılımın *beklenen değerinin* doğru olmasını. Test 55 bunu
kasıtlı olarak eksik (mars payını göremeyen) bir model üzerinde ölçer: `c_cal = 0` eğim
**1,5929**, `c_cal = 0,1` eğim **1,4969** — 1'e daha yakın; MAE 0,3123 → 0,2763.

### 45.5 Kalibrasyon teşhisi (D1–D3)

`ml/diagnose.py` üç hipotezi **aynı bütçeyle** (300 adım, tohum `20261114`, 983 oyun,
CAL 100 / VAL 100) yarıştırır. Amaç mutlak başarı değil **kıyas**tır.

| Teşhis | Ölçüm | Karar |
|---|---|---|
| **D1** — eğitim ölçeği | MAE 1,2327 (125 oyun) → 0,8487 (250) → 0,8052 (500); eğim 0,6208 → 0,9190 → 0,9851 | **işaretli** — eğri hâlâ iniyor, sorun ölçek |
| **D2** — hedef tanımı | `λ=1.0` MAE 0,9734 / eğim 1,0424 vs `λ=0.7` MAE 0,9707 / eğim 1,0490 | işaretli değil (fark %0,3, gürültü) |
| **D3** — kafa yapısı | 6 çıktılı MAE 0,9362 vs skaler 0,9734 (**%3,8** iyileşme) | **işaretli** |

Yükseltme sırası (Faz 6 §6.2) bu ölçüme göre uygulanır: **6 çıktılı kafa** → `L_cal` →
logit sıcaklık (tek `T`) → isotonic (son çare). D2 işaretli olmadığı için `λ` varsayılanı
**1,0** kalır (F6-08): TD hedefi başlangıçta yanlıdır (bootstrap ağının kendi hatasını
hedefe yazar), MC hedefi yanlı değildir, yalnız varyansı yüksektir.

**Sıcaklık yalnız CAL kümesinden öğrenilir** (Kural 10, Test 56). `fit_temperature`
imzası tek bir küme alır — eğitim/doğrulama kümesi parametresi **yoktur**; bu API
yüzeyiyle sızıntı yapısal olarak imkânsızdır. Tek bir `T` öğrenilir, sınıf başına `T`
yoktur (`assert_single_temperature` bunu zorlar). `p_i' ~ p_i ** (1/T)` dönüşümü
`softmax(log p / T)` ile aynıdır; entropi `T` ile kesin olarak artar, equity büyüklüğü
eleman bazında monoton olmak zorunda değildir (`E` sıfırı geçebilir).

### 45.6 Bulunan kritik hata: `terminal_value` işaret hatası (F6-07)

D2 teşhisi yazılırken iki hedef kurucusu (`build_dataset` ve
`build_value_samples(lam=1.0)`) karşılaştırıldı ve **Faz 4'ten beri var olan** bir hata
bulundu: `ml/replay.py::terminal_value`, `z`'yi `winner` ile çarpıyordu. Oysa
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
Aşama A'nın 0,1941 / 0,2203 taban sayıları geçerlidir (ölçüm doğruydu, model zayıftı)
ama bu modeller Aşama C/D'ye başlangıç noktası olamaz.

### 45.7 Testler

| # | Test | Tür | Dosya |
|---|---|---|---|
| 49 | `OutcomeDistribution_EquityFormula_Exclusive` | C# | `Backgammon.Tests/OutcomeDistributionV2Tests.cs` |
| 50 | `OutcomeDistribution_IsAntisymmetric` | C# | aynı |
| 51 | `OutcomeDistribution_FromProbabilities_Normalizes` | C# | aynı |
| 52 | `OutcomeDistribution_FromProbabilities_NoMonotonicityForcing` | C# | aynı |
| 53 | `EquityFormula_PythonMatchesCSharp` | pytest | `ml/tests/test_stage_b.py` |
| 54 | `Onnx_OutputVersion2_IsAccepted` | C# | `Backgammon.Inference.Tests/OutputVersion2Tests.cs` |
| 55 | `CalibrationLoss_ImprovesSlope` | pytest | `ml/tests/test_stage_b.py` |
| 56 | `LogitTemperatureScaling_UsesCalOnly` | pytest | aynı |
| 57 | `Onnx_OutputVersion2_ZeroAllocation` | C# | `Backgammon.Inference.Tests/OutputVersion2Tests.cs` |
| 58 | `Onnx_OutputVersion1_StillWorks` | C# | aynı |
| 59 | `Export_OutputVersion2_Parity` | pytest | `ml/tests/test_export_output_version.py` |

### 45.8 Yeniden üretim

```bash
python ml/gen_test_models.py                                   # C# ONNX fikstürleri
python ml/export_onnx.py --output-version 2 --profile medium \
	--out ml/artifacts/model_output_version_2.onnx             # v2 grafiği + parite
python ml/diagnose.py --steps 300                              # D1-D3 raporu
python -m pytest ml/tests/test_stage_b.py -q                   # Test 53, 55, 56
dotnet test TavlaAI_Project.slnx --filter "OutcomeDistributionV2Tests|OutputVersion2Tests"
```

**Doğrulama (Aşama B kapanışı).** `ml/tests` **206/206** (1 yavaş test varsayılan atlanır), `Backgammon.Tests`
**256/256**, `Backgammon.Inference.Tests` **60/60**, `Backgammon.UI.Tests` **85/85**.
Aşama B testleri: 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59.

---

## 46. Faz 6 — Aşama C: veri motoru (paralel determinizm, `dup_cap`, hacim)

Aşama B modelin **kafasını** düzeltti. Aşama C verinin **kendisini** düzeltir: Faz 4/5
kontrol noktaları işaret hatası yüzünden geçersizdir (F6-12), dolayısıyla eğitim verisi
sıfırdan, **yeniden üretilebilir** biçimde üretilmelidir. Aşama C dört söz verir:
(1) `--threads N` çıktısı `--threads 1` ile aynıdır, (2) aynı afterstate sınırsız
tekrarlanmaz, (3) shard v1 biçimi değişmez, (4) veri hacmi ölçülmüştür.

### 46.1 Neden eski şema yeniden üretilemiyordu

Faz 4'ün `Program.cs`'i tohumu **iş parçacığına** bağlıyordu:

```csharp
// ESKI (Faz 4/5) — kaldirildi
ulong threadSeed = config.Seed + (ulong)threadIndex * ScheduleSeedSalt;
var rng = new Xoshiro256StarStar(threadSeed);
// her is parcacigi tek RNG'yi oyunlar arasinda sirayla tuketiyordu
```

İki bağımsız kusur vardı:

1. **İş parçacığı sayısı veriyi değiştiriyordu.** `--threads 4` ile `--threads 1` farklı
   oyunlar üretir; yani "aynı tohum = aynı veri" garantisi yoktu.
2. **Oyun-tohum eşlemesi belirsizdi.** Hangi oyunun hangi RNG akışını aldığı, iş
   parçacıklarının tamamlanma sırasına bağlıydı — yani duvar saati bağımlı.

Bu, Faz 6'nın tüm ölçüm mantığını çürütür: aynı veri kümesini iki kez üretemezseniz
Aşama D/E'deki karşılaştırmalar anlamsızdır.

### 46.2 Yeni şema: oyun başına tohum

```csharp
// YENI — Program.PlayOne
runner.ResetSeed(config.Seed + gameId);          // oyun akisini belirleyen tek RNG
var poolRng = new Xoshiro256StarStar(gameSeed ^ ScheduleSeedSalt);  // ayri RNG
```

* `seed(gameIndex) = baseSeed + gameIndex` — **iş parçacığından bağımsız**.
* Havuz (pool) kararı ayrı bir RNG'den çekilir; böylece havuz seçimi oyunun zar
  akışını **tedirgin etmez**. Aksi hâlde `--pool` bayrağı veriyi değiştirirdi.
* `SelfPlayRunner._rng` artık `readonly` değil; `ResetSeed(ulong)` tek satırlık bir
  atama. Oyun içi hiçbir kod tohum kaynağını bilmez.

**Sonuç (Test 60).** `--threads 1` ve `--threads 4` çıktı shard'ları **birebir aynıdır**
(SHA-256 eşit). Test bunu `Program.Main`'i iki kez çağırıp dosya hash'lerini
karşılaştırarak doğrular; yani iddia kod yolunun tamamını kapsar.

**Bedeli (F6-13).** `ml/runs/stage_d/shards` eski şemayla üretildi; biçim aynı olduğu
için **okunabilir** (Test 63) ama aynı tohumla **yeniden üretilemez**. Kabul edildi:
bu shard'lar zaten işaret hatası taşıyor (F6-12) ve eğitimde kullanılmayacak.

### 46.3 `dup_cap`: oyun sonrası tekrar ayıklama

Aynı afterstate'in tekrar tekrar öğrenilmesi gradyanı çarpıtır ve diski şişirir.
`dup_cap` (varsayılan **3**, `0` = kapalı) aynı parmak izli kararın en fazla `n` kez
öğrenen kümesine girmesine izin verir.

Tasarım kısıtları ve çözümleri:

| Kısıt | Çözüm |
|---|---|
| Sayaç global durumdur; iş parçacıklarına dağıtılırsa Test 60 kırılır | **Oyun sonrası** tek geçiş (`DupCapFilter.Apply`) |
| Sonuç tamamlanma sırasına bağlı olmamalı | `GameId`'ye göre sırala, sonra gez |
| Shard v1 karar-öncesi Zobrist hash'i saklamaz, biçim değişmemeli | Parmak izi = `chosenVector` float32 baytları üzerinde **FNV-1a 64** |
| TD(λ) zinciri her kararın `chosenVector`'üne ihtiyaç duyar | Karar **silinmez**: `IsLearner` temizlenir, `DupCapped` (bit3) kurulur, `Q`/`PolicyTargetCs`/`CandidateVectors` boşaltılır |
| Açılış çeşitliliği yok olmasın (Test 62) | İlk `DefaultOpeningPlies = 10` karar muaf |

`BackgammonState.hash` karar düzeyinde kullanılamaz: zarı **içermez**, yani aynı taş
dizilimi farklı zarlarla aynı hash'i verir. Bu yüzden vektör parmak izi seçildi.

**Ölçüm.** 200 oyun, `--dup-cap 1`: 15 603 açılış-dışı öğrenen kararın **23**'ü
(%0,15) elendi. Rastgele self-play'de tekrar nadirdir; `dup_cap` bir hızlandırıcı değil,
**güvenlik ağıdır** — ileride güçlü politika ile tekrar oranı artacaktır.

### 46.4 Biçim sözleşmesi korunur

`formatVersion` **1**, `vectorSize` **221**, `SHARD_FORMAT.md` §1–§4 değişmedi. Tek
ekleme `ShardDecisionFlags` bit3 (`DupCapped = 8`) — eklemeli ve geriye uyumlu, eski
okuyucular bilinmeyen biti yok sayar.

`finalProbs`/`outcomeProbs` alanı **yoktur ve olmayacaktır** (Faz 6 §7.1). 6 sınıflı
hedef `winner` + `resultType`'tan türetilir (`ml/targets.py` içindeki `exclusive_target`). Test 65
bunu iki tarafta doğrular: C# tarafında yansıma ile alan yokluğu, Python tarafında
`hasattr` + türetilen hedefin tek-sıcak olması.

### 46.5 Linux yayını ve yürütme sağlayıcısı kararı

`dotnet publish -r linux-x64 --self-contained true` başarılı, çıktı ELF (`\x7fELF`).
Bu makinede **WSL yok** ve **Docker yok**; bu yüzden Test 64'ün *çalıştırma* adımı
atlanır ve gerekçe çıktıya yazılır (F6-15). Yayın + ELF doğrulaması her koşuda yapılır.

**CPU vs CUDA.** Faz 6 v3 §12.3 "CUDA ≥ CPU" varsayıyordu; ölçüm bunu çürüttü. CUDA
execution provider gerçekten yüklendi (doğrulama: `torch\lib` `PATH`'te değilken
`cublasLt64_12.dll` eksik hatası alınır) ve yine de CPU kazandı:

| Ölçüm | CPU | CUDA | CUDA/CPU |
|---|---|---|---|
| Test 61, 20 oyun, `depth 0`, ısınmalı | **119,26 oyun/sn** | 29,11 oyun/sn | 0,24× |
| CLI, 60 oyun, `depth 0`, `log-top 4` | **85,91 oyun/sn** | 24,68 oyun/sn | 0,29× |
| CLI, `depth 1`, `max 4/4` | **1,52 oyun/sn** | 0,25 oyun/sn | 0,16× |
| CLI, `depth 2`, `max 4/4` | **0,03 oyun/sn** | < 0,01 oyun/sn | < 0,3× |

Tepe bellek: CPU 87 MB, CUDA 381 MB. Karar `SelfPlayConfig.DefaultUseCuda = false`
olarak sabitlendi; ayrıntı `ml/artifacts/stage_c_gpu_decision.md` (F6-16).

**Neden.** Model ~156 bin parametre; forward geçişi CPU'da ~1 µs, GPU çekirdek başlatma
gecikmesi 20–50 µs. `depth 0`'da kova 32–64 satıra yuvarlanır, hesap başlatma
maliyetinin altında kalır. Derinlik arttıkça arama ağacı C# tarafında CPU'da gezildiği
için fark büyür. İş parçacıkları arası kova birleştirme (v3 §7.3) uygulanırsa kova
2048'e çıkar ve GPU kazanabilir — ayrı deney.

> **Ölçüm tuzağı.** Isınma geçişi olmadan 6 oyunla yapılan ilk ölçümde CUDA 1,47×
> *hızlı* göründü; sebep ölçüm hatasıydı (CPU soğuk, CUDA sıcak). Test 61 artık ısınma
> geçişi yapar, 20 oyun ölçer ve CPU'yu iki kez ölçüp büyüğünü alır.

Test 61 "CUDA kazanmalı" demez; **ölçülen kazananın seçili olmasını** ister (eşik 1,2×).
Başka donanımda CUDA kazanırsa test kırmızı olur ve sabitin çevrilmesini söyler. GPU
ölçümü için:

```bash
dotnet build -c Release -p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu
```

Determinizm iddiası GPU yoluna **taşınmaz** (Faz 6 §7.3): GPU yalnızca hız içindir.

### 46.6 Ölçülen veri hacmi

60 oyun/koşu, `model_stage_d_v10.onnx`, `depth 0`, `log-top 4`, i7-9750H (6C/12T):

| thread | oyun/sn | tepe bellek (MB) | disk yazma (MB/s) |
|---|---|---|---|
| 1 | 85,70 | 81 | 24,34 |
| 6 | 190,14 | 160 | 54,01 |
| 12 | 209,96 | 254 | 59,64 |

Ölçeklenme: 6 thread **2,22×**, 12 thread **2,45×** (koşudan koşuya ±%10 oynar). `log-top 4` ile ~298 KB/oyun;
`log-top 12` ile ~11,5 KB/karar → ~0,8 MB/oyun. 10⁵ oyun ≈ **80 GB** (F: üzerinde
427 GB boş). Bunlar **ölçüm**dür, formül değil.

> **Dürüst sınır.** `depth 0` yalnızca kök değerlendirmesi yapar; üretim verisi
> `depth 1–2` ile toplanacak ve hız belirgin biçimde düşecektir. Yukarıdaki sayılar
> **üst sınırdır**, üretim hızı değildir.

### 46.7 Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 60 | `SelfPlay_ThreadsAreDeterministic` | C# | ✅ |
| 61 | `SelfPlay_GpuBatching_IsFaster` | C# | ✅ ölçüldü: CPU 4,1× hızlı → CPU seçildi |
| 62 | `SelfPlay_OpeningDiversity` | C# | ✅ entropi 6,5479 bit |
| 63 | `ShardV1_IsStillReadable` | pytest | ✅ |
| 64 | `SelfPlay_LinuxPublish_Runs` | pytest | ⏭️ yayın ✅, çalıştırma atlandı |
| 65 | `Shard_NoOutcomeProbsField` | C# + pytest | ✅ |
| 66 | `DupCap_Works` | C# | ✅ |
| 67 | `SelfPlay_Throughput_IsMeasured` | pytest | ✅ |

**Doğrulama.** `ml/tests` **209/209** (2 yavaş test varsayılan atlanır),
`Backgammon.Tests` **256/256**, `Backgammon.Inference.Tests` **64/64**,
`Backgammon.UI.Tests` **85/85**. Aşama C testleri: 60, 61, 62, 63, 64, 65, 66, 67.

### 46.8 Yeniden üretim

```bash
dotnet build Backgammon.SelfPlay -c Release
python -m pytest ml/tests/test_stage_c.py -q
dotnet test TavlaAI_Project.slnx --filter "StageCDataEngineTests"

# Determinizm elle doğrulama (iki dizin birebir aynı olmalı)
Backgammon.SelfPlay --model ml/artifacts/model_stage_d_v10.onnx \
	--games 12 --seed 7 --threads 1 --depth 0 --out /tmp/t1 --prefix a --gzip false
Backgammon.SelfPlay --model ml/artifacts/model_stage_d_v10.onnx \
	--games 12 --seed 7 --threads 4 --depth 0 --out /tmp/t4 --prefix a --gzip false
```

---

## 47. Faz 6 — Aşama D: ölçekli eğitim (vektör TD(λ), kapasite, determinizm)

Aşama B modelin **kafasını**, Aşama C verinin **kendisini** düzeltti. Aşama D
**eğitimi** düzeltir: 6 çıktılı kafayla vektör TD(λ) döngüsü, kapasite/AMP
kararlarının ölçülmesi, determinizm ve devam-ettirme garantileri, ve L0/L1/L2/L3
eğitim merdiveni.

**Kabul (v3 §12.4, v3-DÜZELTME satır 802–804).** ER < 0,02 bir **kapı değil,
hedeftir**. Aşama D kabulü: "L1/L2/L3 hedefleri raporlanır; ulaşılan/ulaşılamayan
değerler `ml/artifacts/stage_f_train.md`'ye yazılır; sapma analizi yapılır."

### 47.1 Vektör TD(λ): işaret çevrimi yerine sınıf-yarısı takası (F6-17)

Faz 4'ün skaler zinciri `y[t] = -((1-λ)·V[t+1] + λ·y[t+1])` idi. Altı sınıflı
dağılımda "`-V`"nin karşılığı **işaret çevrimi değil**, sınıf yarılarının takasıdır:

```python
FLIP_INDEX = [3, 4, 5, 0, 1, 2]          # [W,GW,BW,L,GL,BL] -> [L,GL,BL,W,GW,BW]

y[n-1] = flip(z_terminal)
y[t]   = flip((1 - lam) * p_hat[t+1] + lam * y[t+1])
```

`flip` bir **involusyondur** (`flip(flip(p)) == p`). Bu yüzden `λ = 1,0`'da zincir
`flip^k(z)`'ye indirgenir ve `flip² = id` olduğu için sonuç **tam olarak** oyuncu
bakış açısından tek-sıcak Monte Carlo hedefidir. F6-07'deki işaret hatasının vektör
karşılığı böylece **yapısal olarak imkânsız** hâle gelir: `flip` uygulanmazsa
`λ = 1,0` hedefi rakip bakış açısından yazılır ve
`test_vector_td_lambda_one_equals_monte_carlo` kırmızı olur. Altı
`(winner, result_type)` kombinasyonunun tamamı doğrulanmıştır.

**Hız.** `λ ≥ 1,0` iken `build_exclusive_samples` ileri geçişi **tamamen atlar**
(zincir ağa bağlı değildir). L0/L1/L2'nin tamamı `λ = 1,0` ile koştu.

### 47.2 İki probe: TD probe ve ağdan bağımsız MC probe (F6-19)

| Probe | Hedefler | Ne ölçer | `--resume` |
|---|---|---|---|
| `probe_value` (TD) | 1. iterasyonun **zayıf** modelinden dondurulmuş | "ilk modelden ne kadar uzaklaştık" | `probe.npz` |
| `probe_mc` (MC) | `λ = 1,0`, **ağdan bağımsız** tek-sıcak | gerçek öğrenme eğrisi | `probe.npz` |

Dondurulmuş TD probe'un hedefleri modelden geldiği için model ilerledikçe **yanıltıcı
biçimde kötüleşir** (L0'da `probe_ce` 1,1991 → 1,0451 görünürken `probe_policy_loss`
2,2792 → 3,6167'ye çıkar). Faz 4 bu sorunu `probe_mc` ile çözmüştü; `train_v2.py`'nin
ilk sürümünde bu alan eksikti ve L0'un ilk koşusunda `probe_ce`'nin 1,66 → 1,76
kötüleşmesi yanlış yorumlanmaya açıktı.

**Neden `probe.npz` zorunlu.** Faz 4 probe'u **ilk iterasyonun buffer'ından** alıyordu.
`--resume` sonrası buffer shard'lardan yeniden kurulduğu için ilk iterasyonun buffer'ı
farklı olur, yani probe kümesi değişir ve `metrics.jsonl` **sapardı**. Çözüm: sabit
boyutlu probe (`--probe-size` 4096 değer örneği, `--probe-policy-size` 1024 politika
grubu) `np.random.default_rng(seed ^ 0x5EED / 0x5EEF / 0x5EEE)` ile alt örneklenir,
`probe.npz`'ye yazılır ve `--resume`'da aynen geri yüklenir. Test 72'nin bit düzeyinde
determinizmi buna bağlıdır.

> **Dürüst sınır.** MC probe'un **hedefleri** ağdan bağımsızdır ama **durum dağılımı**
> değildir: 1. iterasyonun buffer'ından örneklenir. L1'de `probe_mc_ce` 0,9726 → 1,0276
> kötüleşirken VAL-ER 0,0877 → 0,0658 iyileşti. İkisi çelişmez; farklı soruları
> yanıtlarlar. Gerçek kalite ölçüsü VAL-ER/TEST-ER'dir (gnubg, sabit korpus).

### 47.3 Isınma zorunlu: soğuk başlangıç %79 iptal oyun üretir (F6-20)

`medium` profiliyle **eğitilmemiş** ağdan 2 000 oyunluk self-play:

| Model | oyun | iptal | karar/oyun | shard (gzip) | tepe bellek |
|---|---|---|---|---|---|
| eğitilmemiş `medium` | 2 000 | **1 584 (%79,2)** | 454,8 | 251 MB | 8,5 GB |
| ısıtılmış `medium` | 2 000 | **0** | 65,7 | 26,9 MB | 1,1 GB |

Eğitilmemiş ağın politika logitleri neredeyse sabittir; `--sel-temp 0,05` ile ajan
neredeyse her zaman aynı adayı seçer ve oyun `--max-plies 500` sınırına kadar ilerler.
İptal oyunlar `is_usable_game` tarafından zaten atılır, yani verinin %79'u **boşa
harcanır**. Bu yüzden `--init-from <ckpt.pt>` (yalnızca ağırlıklar; optimizer/iterasyon
taşınmaz, profil aynı olmak zorunda) kural hâline getirildi.

**Yan bulgu.** `small` profiliyle sıfırdan başlangıç bu patolojiyi göstermedi
(171 karar/oyun, iptal 0). Yani patoloji profil/başlangıç ağırlıklarına bağlıdır ve
şansa bırakılamaz.

### 47.4 `ShardWriter` toplu float yazımı (F6-21)

`WriteFloats` float başına **4 × `WriteByte`** yerine tek bir `byte[]` doldurup **tek
`Stream.Write`** yapar; `WriteFile` çıktıyı 64 KB `BufferedStream` ile sarar.

| | önce | sonra |
|---|---|---|
| 2 000 oyunluk shard (duvar süresi) | >7 dk | **12,7 s** |
| tepe bellek | 8,5 GB | **1,1 GB** |
| hız | — | **440 oyun/sn** (4 iş parçacığı) |

Bayt çıktısı **değişmedi** (little-endian kodlama aynı), yani Test 60'ın bit düzeyinde
determinizm iddiası korunur. Bu, Faz 4'ten beri var olan bir yazma yolu kusurudur;
Aşama C'nin 100 oyunluk shard'larında görünmüyordu.

### 47.5 Ölçülen eğitim merdiveni

| Koşu | Profil | Oyun/iter | İter | Süre | Hedef ER | VAL-ER | TEST-ER | Durum |
|---|---|---|---|---|---|---|---|---|
| L0 | `small` | 500 | 20 | 34,4 dk | — (harness) | 0,1550 | **0,1429** | ✅ |
| L1 | `medium` | 2 000 | 30 | 61,0 dk | < 0,10 | 0,0658 | **0,0708** | ✅ |
| L2 | `medium` | 10 000 | 30 | 196,0 dk | < 0,05 | 0,0619 | **0,0490** | ⚠️ |
| L3 | `medium` | 100 000 | 50 | ~40 sa (tahmin) | < 0,02 | — | — | ⏭️ |
| Faz 5 taban | — | — | — | — | — | — | 0,1941 | — |

**Toplam iyileşme (L2 vs Faz 5):** 0,1941 → 0,0490 = **3,96×** (TEST-ER); VAL-ER
üzerinden 0,1941 → 0,0619 = **3,14×**.

L2'nin TEST-ER'i < 0,05 hedefinin altındadır, ancak **VAL-ER kazancı anlamsızdır**:
L1 0,0658 → L2 0,0619, fark 0,0039; 40 pozisyonun standart hatası 0,016–0,020.
Yani oyun/iterasyonu **5×** artırmak ER'de **ölçülebilir** bir kazanç üretmedi —
ER ~0,06–0,07 bandında **plato** yaptı. Bu, v3 §8.4'ün "daha çok oyun → daha iyi ER"
varsayımının ölçümle çürütüldüğü noktadır.

Darboğaz **kapasite değil**: Test 68 aynı veriyle `medium` (0,3535 ± 0,0712) ve
`large` (0,2651 ± 0,0594) profillerini karşılaştırdı, fark 0,0884 < eşik 0,0927 —
kazanç istatistiksel olarak anlamlı değil. Darboğaz **öğretmen kalitesi** (`depth 0`
self-play, `--sel-temp 0,05`) ve **ölçüm çözünürlüğü**dür. Bu yüzden L3, v3 §8.4'teki
gibi yalnızca 10⁵ oyun/iterasyon değil, aynı anda `depth 1` veri üretimi ve en az
200 pozisyonluk VAL/TEST kümeleri (SE ≈ 0,008) kullanmalıdır. Ek A (Evren/H200)
açıldığında ilk iş odur.

**Kalibrasyon.** L0'da eğim 0,99997 → 1,0076, L1'de 1,0205 → 1,0015, L2'de 0,9992 →
0,9851. Model **aşırı güvenli değil** — bu, Faz 5'in 2,78 std-oranıyla taban tabana
zıttır ve Aşama B'nin kalibrasyon teşhisinin (D1–D3) doğrudan sonucudur.

### 47.6 Kapasite ve AMP kararları (Test 68, 70)

| Karar | Ölçüm | Sonuç |
|---|---|---|
| Kapasite | `medium` ER 0,3535 ± 0,0712 vs `large` 0,2651 ± 0,0594; fark 0,0884 < eşik 0,0927 | **`medium`** |
| AMP | FP32 2,61 s vs AMP 16,19 s (0,16×); ΔCE 0,00085 | **FP32** |

AMP CPU'da **6,2× yavaş**: `torch.autocast` `bfloat16`'ya düşer ve i7-9750H (Coffee
Lake) AVX-512 BF16 desteklemez; her çarpma yazılım emülasyonuna gider. GPU'da
(SM ≥ 8.0) yeniden ölçülmelidir; `decide_amp` bunu otomatik yapar.

### 47.7 Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 68 | `Capacity_Gain_IsMeasured` | pytest | ✅ `medium` seçildi |
| 69 | `TrackH_H0_Parity` | pytest | ⏭️ Ek A kapısı açılmadı (F6-18) |
| 70 | `Amp_IsMeasured` | pytest | ✅ FP32 seçildi |
| 71a | `Training_IsReproducible_CPU` | pytest | ✅ bit düzeyinde aynı `metrics.jsonl` |
| 71b | `Training_IsReproducible_GPU` | pytest | ✅ tolerans içinde (CUDA varsa) |
| 72 | `Checkpoint_Resume_IsExact` | pytest | ✅ kesintisiz koşuyla aynı |
| 73 | `BestModel_SelectedByValEr` | pytest | ✅ `best.json` VAL-ER ile seçilir |
| 74 | `TestAccess_IsLogged` | pytest | ✅ 2. erişim `exploratory` |

**Doğrulama.** `ml/tests` **219/219** (3 yavaş/koşullu test atlanır),
`Backgammon.Tests` **264/264**, `Backgammon.Inference.Tests` **64/64**,
`Backgammon.UI.Tests` **85/85**. Aşama D testleri: 68, 69, 70, 71a, 71b, 72, 73, 74.

### 47.8 Yeniden üretim

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

## 48. Faz 6 — Aşama E: arama gücü (transposition table, bearoff kesmesi)

**Kaynak:** `Faz 6 v3.md` §9, §12.5 (Test 75–82), §13.4.
**Rapor:** `ml/artifacts/stage_e_search.md`. **Kararlar:** `ASSUMPTIONS.md` F6-22…F6-25.

### 48.1 Değişmez kural

Aşama E **hız** ekler, **güç** değil. v3 §9.5: *her optimizasyon `Reference(depth)` ile birebir
aynı sonucu vermelidir; fark varsa bu optimizasyon değil hatadır.* Bu yüzden hiçbir sezgisel
budama, hiçbir yaklaşık değer, hiçbir "iyileştirme" kabul edilmedi. Eklenen iki mekanizma da
**sonucu kanıtlanabilir biçimde değiştirmez** ve ikisi de **varsayılan olarak kapalıdır**.

### 48.2 `SearchSettings` — iki yeni alan

```csharp
public int  TranspositionCapacity;   // 0 = kapalı (varsayılan)
public bool UseBearoffCutoff;        // false (varsayılan)
```

`SearchSettings.Default` ve `SearchSettings.Reference(depth)` bu iki alanı **0 / false** olarak
açıkça yazar. Faz 3'ün 9 (Default) ve 11 (Reference) alanı birebir korunur — Test 75 ve Test 81
bunu kilitler.

### 48.3 Transposition table

**Depolama.** `SearchWorkspace` içinde dört paralel dizi: `_ttKey` (`ulong`), `_ttScore` (`float`),
`_ttDepth` (`byte`), `_ttFlag` (`byte`). Doğrudan eşleme: `slot = key & (capacity - 1)`.
Kapasite 2'nin kuvveti olmalı, en fazla 2²⁶. Çakışmada üzerine yazılır.

**Tembel ayırma.** `EnsureTransposition(capacity)` yalnızca kapasite **değiştiğinde** dizi ayırır.
Aynı kapasiteyle tekrar çağrıldığında hiçbir şey yapmaz → ısınma sonrası **0 bayt** allocation
(Test 80).

**Anahtar.**

```
key = s.hash ^ (depth · 0x9E3779B97F4A7C15) ^ (diceMask · 0xC2B2AE3D27D4EB4F)
diceMask = fold(remainingCount, remainingDice[0..remainingCount))
```

Zar maskesi **zorunludur**: `Zobrist` tabloları yalnızca tahta, toplanan taş, küp değeri, küp
sahibi ve sıra anahtarlarını içerir — **zar yoktur**. Aynı tahtaya farklı kalan zarlarla ulaşan
iki düğüm aynı `s.hash`'i üretir; maske olmadan TT yanlış değer döndürürdü.

**Boş yuva işareti.** `_ttDepth[i] == 0xFF` boş demektir (geçerli derinlik `0..MaxSupportedPly`).
`Array.Clear` derinliği 0 yapar ve 0 geçerli bir derinliktir; bu yüzden `ClearTransposition`
derinlik dizisini açıkça `0xFF` ile doldurur.

**Yalnızca EXACT — bilinçli sınırlama.** `LOWER`/`UPPER` bayrakları biçim olarak ayrılmıştır ama
bu motorda **kesme için kullanılmaz**. Gerekçe: `ChanceNode` 21 zar üzerinden **ağırlıklı ortalama**
alır. Bir sınır değerin ortalamaya girmesi ortalamayı da sınır yapar; sınırların yukarı
propagasyonu bu motorda güvenli değildir. Yalnızca **tam pencerede** (`alpha <= L && beta >= U`)
ve **kesme yapılmadan** hesaplanmış değerler saklanır → TT sonucu değiştirmez (Test 78, F6-24).

**Kökte kullanılmaz.** `isRoot` düğümünde TT okunmaz/yazılmaz; `RootCandidates` ve
`RootPolicyTarget` her çağrıda doldurulmalıdır.

**Temizleme.** `EnsureCacheConsistent` (değerlendirici `Version` veya `SettingsSignature` değişimi)
artık TT'yi de temizler. `SettingsSignature` = `MaxCandidatesInner · 2 | (UsePolicyOrdering ? 1 : 0)`
— yani **değeri etkileyen** ayarlar. `MaxCandidatesRoot`, `UseAlphaBeta`, `UseStar1` değeri
etkilemez, imzaya girmez.

**Sayaçlar.** `SearchResult.TranspositionHits` / `TranspositionStores`; `SearchWorkspace` içinde
`BeginSearch()` ile sıfırlanır.

### 48.4 Bearoff kesmesi

Yeni opsiyonel arayüz:

```csharp
public interface IExactValueEvaluator
{
	bool IsExactFor(ReadOnlySpan<sbyte> board);
}
```

`SearchNode` başında:

```csharp
if (d > 0 && exactEvaluator != null && exactEvaluator.IsExactFor(s.board))
{
	d = 0;
}
```

**Neden sonuç değişmez?** Saf yarışta (temas yok) optimal oyun DB'de çözülmüştür:

```
E(P) = max_m Σ_r w_r · (−E(P after m, then opponent rolls r))
```

Yani kesin değer, her derinlikteki aramanın **sabit noktasıdır**. `BearoffAwareEvaluator` yaprakta
kesin equity verdiği için depth 1, depth 2, … hepsi aynı değeri üretir; depth 0'a indirmek yalnızca
**düğüm sayısını** düşürür (Test 77: 3 939 → 12 düğüm, **328×**).

**Decorator kuralı.** `BearoffAwareEvaluator` `IExactValueEvaluator` uygular ve
`IsExactFor(board) = IsBearoffActive && IsSolvable(board)` döner. `MatchAwareEvaluator`
**uygulamaz**: `E → ME` dönüşümü tek skaler `E`'nin monoton fonksiyonu değildir, dolayısıyla
kesin bearoff equity'si dönüşümden geçirilemez.

### 48.5 Ölçümler

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

### 48.6 Ablasyon kararı — TT üretimde açılmaz

Test 82 gerçek kullanım biçimini ölçer: `SelfPlayAgent` workspace'i kararlar arasında **yaşatır**;
`Reset()` yalnızca model yeniden yüklenince çağrılır. (İlk denemede her kararda `Reset()`
çağrıldığı için TT hiç isabet üretmedi — ölçüm hatası düzeltildi.)

| Konfigürasyon | Değerlendirici | Düğüm | TT isabet | Süre |
|---|---|---|---|---|
| cache açık, TT kapalı | 91 203 | 92 392 | 0 | 3,546 s |
| ikisi de açık | 89 876 | 91 065 | 21 | 3,446 s |
| cache kapalı, TT açık | 93 501 | 94 753 | 84 | 3,534 s |

TT, eval cache'in üzerine yalnızca **%2,9** ekliyor; cache tek başına TT'den **%0,4** daha iyi.
Sebep: pahalı iş (yaprak değerlendirme + chance düğümü) zaten `UseEvalCache` tarafından
anahtarlanıyor ve tavla'da gerçek transpozisyon (aynı tahta + aynı zar + aynı derinlik) nadirdir.

v3 §9.5 "kazanç yoksa sadeleştirilir ve raporlanır" der. **Karar:** TT varsayılan olarak kapalı
kalır ve üretim yollarında (`SelfPlayAgent`, `GameOrchestrator`) **açılmaz**. Kod opt-in olarak
korunur — §9.3'ün zorunlu teslimatıdır ve Test 76/78/80 ona bağlıdır (F6-25).

### 48.7 Performans kapıları

| Metrik | Ölçülen | v3 §9.5 hedefi | Durum |
|---|---|---|---|
| p50 karar süresi (depth 2) | **0,1217 s** | ≤ 0,15 s | ✅ |
| p95 karar süresi (depth 2) | **0,7133 s** | ≤ 2 s | ✅ |
| Ortalama oyun (27 karar) | **5,24 s** | ≤ 5 s (kapı **değil**) | ⚠️ %5 aşım |
| Isınma sonrası allocation | **0 bayt** | 0 | ✅ |

Ortalama oyun süresi v3 §9.5'te açıkça **kapı değil** ilan edilir ("raporlanır"). 5,24 s,
5 s'lik raporlama hedefinin %5 üzerindedir; iki gerçek kapı (p50, p95) rahat geçilmiştir.

### 48.8 Alınmayan optimizasyonlar

| # | Öneri | Neden alınmadı |
|---|---|---|
| 1 | Sezgisel "E > 0,9 → kes" | v3 §9.5 [v3-DÜZELTME]: sonucu değiştirir, değişmez kuralı ihlal eder |
| 2 | TT `LOWER`/`UPPER` kesmesi | Chance katmanı ağırlıklı ortalaması sınır propagasyonunu güvensiz kılar (F6-24) |
| 3 | Depth 3 | v3 §9.6 kapsam dışı; vektör değerli expectiminimax gövde değişikliği gerektirir |
| 4 | Star2 / daha agresif aday kısıtı | Sonucu değiştirir; Aşama E kapsamı dışı |

### 48.9 Test tablosu

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

**Doğrulama.** `ml/tests` **219/219** (3 yavaş/koşullu test atlanır),
`Backgammon.Tests` **268/268**, `Backgammon.Inference.Tests` **64/64**,
`Backgammon.UI.Tests` **85/85**. Aşama E testleri: 75, 76, 77, 78, 79, 80, 81, 82.
(268 sayısı Aşama F'nin `CubePowerTests` dosyasını — Test 83, 85, 86, 88 — da içerir.)

### 48.10 Yeniden üretim

```powershell
dotnet test Backgammon.Tests\Backgammon.Tests.csproj -c Release `
  --filter "FullyQualifiedName~SearchPowerTests" --logger "console;verbosity=detailed"
```

---

## 49. Faz 6 — Aşama F: küp ve maç ustalığı (perspektif sözleşmesi)

Bu bölüm Aşama F'de bulunan üç ölçüm/sözleşme hatasını ve bunların mimari sonucunu belgeler.
Ayrıntılı sayısal rapor `ml/artifacts/stage_f_cube.md`, karar kayıtları `ASSUMPTIONS.md`
F6-28/F6-29/F6-30, faz anlatımı `PHASES.md` §18'dir.

### 49.1 Perspektif sözleşmesi (tek doğru kaynak)

Ağın değer çıktısı **her zaman** şu anlama gelir:

```
V(vec(Q, p))  =  "p oyuncusunun, Q afterstate'inde (yani p hamlesini yaptıktan sonra) equity'si"
```

Bu sözleşme üç yerde aynı biçimde uygulanır ve **üçü de aynı olmak zorundadır**:

| Yer | Çağrı |
|---|---|
| Eğitim verisi | `SelfPlayRunner.VectorizeAfterMove(sequence, mover, dest)` |
| ER ölçümü | `ml/gnubg_er.py::score_afterstates` → `vectorize(..., perspective=turn)` |
| Arama | `BackgammonSearch.SearchNode` → `EvaluateBatch(list, 0, n, s.turn, ...)` |

`EquityCubeAdvisor` de bu sözleşmeye uymak zorundadır. F6-29 öncesi uymuyordu: afterstate'leri
`-perspective` ile değerlendirip işareti çeviriyordu. Ağ **antisimetrik olmadığı** için
(`mean |V(Q, p) + V(Q, −p)| = 0,65`) bu, ölçülebilir yanlılık üretiyordu.

**Kural.** Bir afterstate değerlendirilirken perspektif, **o afterstate'i üreten hamleyi yapan**
oyuncudur. Sıra değişimi yalnızca *sıra başı* (pre-roll) pozisyonlar için geçerlidir ve ağ bu
girdi dağılımını hiç görmediği için güvenilir değildir (bkz. 49.4).

### 49.2 `EquityCubeAdvisor.EvaluateDiceAveraged` — düzeltilmiş akış

```
for each of 21 dice pairs (weight 1 for doubles, 2 otherwise):
	scratch = state + dice
	GenerateAfterStates(scratch)            # yasal hamle yoksa AddPass
	partition in place: [0, m) non-terminal, [m, n) terminal
	EvaluateBatch(list, 0, m, perspective)  # ← F6-29: mover perspektifi, işaret çevirme YOK
	EvaluateDistributionBatch(list, 0, m, perspective)
	best = argmax over non-terminal of values[i]
		   ve terminal of ResultPoints[i] / cubeValue
	accumulate weight * bestValue, weight * dists[best] (kümülatif)
convert cumulative → exclusive via OutcomeDistribution.FromProbabilities
clamp equity to [-3, 3]
```

Terminal afterstate'ler değerlendiriciye **verilmez** (vektörleştirilemezler); yerinde bölümleme
bunu garanti eder. Terminal kayıt her zaman "sıra sahibi tüm taşlarını topladı" demektir, bu
yüzden `ResultType` doğrudan W/GW/BW olarak biriktirilir.

### 49.3 `ml/cube_bench.py::gnubg_view` — gnubg bakış açısı köprüsü

gnubg'nin Python API'si `cubeinfo['move']` alanını **yok sayar** ve her zaman `anBoard[1]`'i
sırada kabul eder (F6-28). Bu yüzden köprü, hamleyi yapan oyuncuyu fiziksel olarak `anBoard[1]`'e
taşır:

```python
def gnubg_view(case):
	board = to_gnubg_board(case)          # mapB: satır 0 = Beyaz, satır 1 = Siyah
	score = (case["whiteScore"], case["blackScore"])
	owner = gnubg_owner(case["cubeOwner"], case["cubeValue"])
	if case["turn"] == 1:                 # hamle yapan Siyah → satır 1'e taşı
		board = [board[1], board[0]]
		score = (score[1], score[0])
		if owner >= 0:
			owner = 1 - owner
	return board, score, owner
```

`cubeinfo` her zaman `move=1` alır. Metin protokolü (`ml/gnubg_er.py::GnubgSession`) bu köprüyü
**kullanmaz**; `set turn 0|1` sırayı doğru okur ve ER ölçümü etkilenmemiştir.

### 49.4 `singleRecord` neden üretimde kullanılmaz

`EvaluateSingleRecord` **sıra başı** pozisyonu tek kayıt gibi değerlendirir. Vektörleştirici
sıranın kimde olduğunu kodlamaz; ağ yalnızca afterstate gördüğü için sıra başı pozisyonu "rakip
sırada" gibi okur ve equity'yi sistematik olarak **düşük** tahmin eder (ölçüldü: ortalama −0,56,
medyan −0,52). Bu yol `CubeAdvisorOptions.DiceAveraged = false` ile Faz 5 davranışını birebir
korumak için durur; varsayılan `true`'dur.

### 49.5 `EquityCubeAdvisor.Decide` — rakip işbirliği yapmaz

Maç oyununda çiftleme kararı, çiftlemeden sonra gerçekleşecek değeri tahmin etmek zorundadır.
Rakip kendi equity'sini **maksimize** eder, yani bizimkini **minimize** eder:

```
doubleValue = Math.Min(doubleTake, doublePass)   // F6-30; öncesi Math.Max idi
```

`Math.Max`, rakibin bizim için iyi olanı seçeceğini varsayar; bu, danışmanı sistematik olarak
fazla iyimser yapıyordu (32 fazla çiftlemenin 19'u buradan geliyordu). `tooGood` da sıkılaştırıldı:
`doublePass > doubleTake && noDouble > doubleTake` — rakip pas verdiğinde biz yine 1 puan
kazanırız, bu yüzden "pas daha iyi" tek başına "çiftlemek anlamsız" demek değildir.

Bu düzeltme yalnızca **çiftleme** kararını etkiler; kabul kararı ve equity tahmini değişmez.
Ölçümde tam olarak bu görüldü: çiftleme uyumu 73,68 % → **84,96 %**, kabul uyumu ve equity
metrikleri **birebir aynı** kaldı.

### 49.6 Ölçüm sonucu

gnubg 0-ply, 133 geçerli pozisyon, `diceAveraged`:

| Metrik | Faz 5 taban | Aşama F sonu |
|---|---|---|
| Çiftleme uyumu | 52,27 % | **84,96 %** |
| Kabul/ret uyumu | 61,36 % | **88,72 %** |
| Her iki karar uyumu | 46,97 % | **81,20 %** |
| Equity korelasyonu | — | **0,8330** |
| Equity ortalama \|Δ\| | 1,2063 | **0,3738** |

v3 §13.3 kapıları: çiftleme uyumu ≥ %75 → **geçildi**; ortalama \|Δ\| < 1,2063 → **geçildi**.

### 49.7 Ders — ölçüm kurulumu sonucu belirler

Aşama F'de dört ayrı "model kötü" görünen bulgu, aslında **ölçüm hattı** hatasıydı:

1. F6-16: ısınmasız 6 oyunluk koşu CUDA'yı yanlışlıkla 1,47× kazanan gösterdi (gerçek: 0,24×).
2. F6-27: her kararda `ws.Reset()` transposition table isabetini sıfırladı; TT "işe yaramaz"
   göründü.
3. F6-28/F6-29: gnubg bakış açısı ve danışman perspektifi yanlıştı; küp korelasyonu 0,11
   göründü (gerçek: 0,83).
4. F6-30: çiftleme karşılaştırması rakibin işbirliğini varsayıyordu; çiftleme uyumu 73,68 %
   göründü (gerçek: 84,96 %).

**Kural.** Üçüncü taraf bir hakemle karşılaştırma yapılırken **bakış açısı sözleşmesi** ayrı bir
doğrulama adımı olarak ele alınır: hakemin API'si, bilinen bir pozisyonda satırları takas ederek
sınanır ve sonucun işaret değiştirdiği görülmeden ölçüme güvenilmez. Aynı şekilde, bir karar
kuralı yazılırken "karşı taraf ne yapar?" sorusu **açıkça** cevaplanır; `max`/`min` seçimi
varsayıma bırakılmaz.

### 49.8 Dogrulama

```
ml/tests                     550/550  (3 yavas/kosullu test atlanir)
Backgammon.Tests             285/285
Backgammon.Inference.Tests    64/64
Backgammon.UI.Tests           85/85
```

Asama F C# testleri: 83, 85, 86, 88 (`Backgammon.Tests/Cube/CubePowerTests.cs`).
Olcum testleri (84, 87, 89) `ml/tests/test_stage_f.py` icinde yasar.
## 50. Aşama H — Kapanış ve ölçüm hattının son dersi

Aşama H kod üretmez. Ürettiği şey **ölçüm** ve **kayıt**tır: `ml/artifacts/stage_f_faz6.md`
(Faz 6 kapanış raporu), PHASES.md §19, ASSUMPTIONS.md F6-31.

### 50.1 Yeni ölçüm yüzeyi

| Bileşen | Sözleşme |
|---|---|
| `ml/calibration_bench.py` | gnubg **metin protokolü** ile kalibrasyon; `measure_position` ile aynı perspektif |
| `Backgammon.MatchBench bench` | ONNX çıkarım throughput'u; kova 1…2048, `--cuda 0\|1`, JSON çıktı |
| `Backgammon.MatchBench dump-afterstates` | Kalibrasyon girdisi (afterstate + `ourValue` + `perspective`) |

`ml/calibration_bench.py` bilinçli olarak `ml/afterstate_bench.py`'den **ayrı** bir dosyadır.
Faz 5 betiği gnubg'nin Python API'sini kullanıyordu; o yol bu projede güvenilir değil
(F6-28). Yeni betik metin protokolünü kullanır, pip sayılarını doğrular ve perspektif
sözleşmesini `ml/gnubg_er.py::measure_position` ile birebir aynı uygular.

### 50.2 F6-31 — aynalı tahta

Faz 5'in kalibrasyon ölçümü tahtayı gnubg'ye aynalanmış veriyordu:

```python
# HATALI (Faz 5)
row0 = [max(board[i], 0) for i in range(1, 25)] + [max(board[0], 0)]
row1 = [max(-board[24 - i], 0) for i in range(24)] + [max(-board[25], 0)]

# DOGRU
row0 = [max(board[24 - i], 0) for i in range(24)] + [max(board[0], 0)]
row1 = [max(-board[1 + i], 0) for i in range(24)] + [max(-board[25], 0)]
```

Hatalı sürüm White'ın pullarını 24→1 sırasına diziyor, yani tahtayı ters çeviriyordu.
Simetrik olmayan her pozisyonda bu, **başka bir pozisyonu** değerlendirmek demektir.

| Metrik | Faz 5 (hatalı) | Faz 6 (doğru) |
|---|---|---|
| Eğim | 0,0874 | **0,6601** |
| Korelasyon | +0,2431 | **+0,8989** |
| MAE | 0,8014 | **0,2755** |
| Std oranı | 2,78 | **1,3617** |

Faz 5'in "korelasyon 0,24" rakamı modelin kalitesi değildi. Gerçek korelasyon 0,90.
Buna karşılık eğim 0,66 ve MAE 0,28 hâlâ kapı dışında: model gnubg'ye göre sistematik
olarak **düşük** (sapma −0,1547) ve **fazla yayılı** (std oranı 1,36). Bu, Faz 6'nın
kalan gerçek açığıdır.

### 50.3 Ders — §49.7'nin devamı

§49.7 "ölçüm kurulumu sonucu belirler" diyordu ve dört örneği vardı. F6-31 **beşinci**
örnektir ve en sinsi olanıdır: hata ne API sözleşmesinde ne karar kuralında, **tahta
dönüşümündeydi**. Ne parite testi ne de tip denetimi bunu yakalar; yalnızca **elle
doğrulanmış tek bir pozisyon** yakalar.

**Kural (yeni).** Üçüncü taraf bir hakeme tahta veren her dönüşüm fonksiyonu, en az bir
**simetrik** ve bir **asimetrik** pozisyonla, beklenen işareti ve büyüklüğü önceden
yazılarak sınanır. Simetrik pozisyon aynalamayı, asimetrik pozisyon işaret hatasını
yakalar. Bu iki prob, `ml/cube_bench.py::to_gnubg_board`'un doğru olduğunu kanıtlayan
probun aynısıdır.

### 50.4 Kapanış durumu

| Ölçüm | Değer | Kapı |
|---|---|---|
| gnubg ER 2-ply (200 poz.) | 0,0740 | hedef < 0,02 → tutmadı |
| gnubg ER 0-ply (200 poz.) | 0,0972 | — |
| gnubg ER 3-ply (200 poz.) | ölçülemez (F6-32) | hedef < 0,01 → ölçülmedi |
| Faz 5 `v5.onnx` karşısında (1 500 oyun) | %99,67 | > %50, p < 0,05 → geçti |
| Kalibrasyon eğimi | 0,6601 | 0,85–1,15 → **kaldı** |
| Kalibrasyon korelasyonu | +0,8989 | ≥ 0,75 → geçti |
| Kalibrasyon MAE | 0,2755 | ≤ 0,15 → **kaldı** |
| Kalibrasyon std oranı | 1,3617 | 0,7–1,4 → geçti |
| Küp çiftleme uyumu | %84,96 | ≥ %75 → geçti |
| Küp ortalama \|Δ\| | 0,3738 | < 1,2063 → geçti |
| Arama allocation | 0 bayt | 0 bayt → geçti |
| Depth 2 p95 (sentetik değerlendirici) | 0,7133 s | ≤ 2 s → geçti (F7-09: gerçek ONNX ile 4,50 s) |
| ONNX CPU kova 128 | 237 708 poz/sn | ≥ 700 000 → belgelenmiş sapma |
| ONNX CUDA kova 2048 | 875 580 poz/sn | ≥ 1 200 000 → belgelenmiş sapma |

Throughput kapıları `small` mimarisinde (221-128-64) ölçülmüştü; üretim modeli artık
`medium` (221-256-256-128), yani 4,5× daha ağır. Aynı donanımda `small` v1 671 335,
`small` v2 517 817 veriyor — kapılar mimariyle birlikte ölçeklenmemiş.

**F7-09 düzeltmesi.** Yukarıdaki "depth 2 p95 0,7133 s" satırı **sentetik**
`HashEvaluator` ile ölçülmüştü; gerçek ONNX modeliyle aynı yapı **4,4972 s** veriyor
(`medium`, 30 pozisyon, aday 4/4, TT 2²⁰). Yani "depth 2 p95'i 0,71 s'de tutmaya
fazlasıyla yetiyor" cümlesi **yanlıştır**. Gerçek şudur: maliyet ONNX **çağrı
sayısıyla** doğrusal büyür (~0,35 ms/çağrı, kova boyutundan bağımsız) ve depth 2
7 056 yaprak şans düğümü üretir. Üretimde kullanılabilir derinlik **depth 1**'dir
(p95 0,0902 s). Ayrıntı: ASSUMPTIONS.md F7-09.

**"3-ply" satırı neden ölçülemez (F6-32).** gnubg'nin `eval` komutu, `set evaluation
chequerplay evaluation plies N` ayarından **bağımsız** olarak yalnızca `static` (0-ply),
`1 ply` ve `2 ply` satırlarını basar. `ml/gnubg_er.py::_equity_at` istenen sütunu
bulamayınca sıralamanın son anahtarına düşüyordu; `(k == "static", k)` anahtarıyla bu
**`static`**'tir. Yani `--plies 3` çalıştırması farkında olmadan **0-ply** değerini okudu.
Kanıt: `--plies 0` ölçümü `--plies 3` ile 200/200 pozisyonda birebir aynı (0,097225).
Gerçek merdiven **0-ply 0,0972 → 2-ply 0,0740**, yani model hakem güçlendikçe iyileşiyor.
Sessiz geri düşüş kaldırıldı: `MAX_EVAL_PLIES = 2`, aksi halde `ValueError`; `er_harness
measure` desteklenmeyen derinlikte çalışmadan çıkış kodu 2 döner. Gerçek 3-ply hakem
`hint` protokolü + hamle→afterstate eşlemesi gerektirir (gnubg `hint` `plies` ayarına
uyar) ve Faz 7'nin ölçüm hattı işidir.

### 50.5 Dogrulama

```
ml/tests                     550/550  (3 yavas/kosullu test atlanir)
Backgammon.Tests             285/285
Backgammon.Inference.Tests    64/64
Backgammon.UI.Tests           85/85
```

Toplam **974**. Asama H kapanistan sonra F6-32 icin **2** regresyon testi ekledi
(`test_equity_at_rejects_unsupported_ply`, `test_max_eval_plies_matches_gnubg_contract`):
222 → **224**. Faz 7 Asama A alti yeni pytest dosyasi ve `EquityGoldenTests` ekledi:
224 → **550** (pytest), 268 → **275** (C# cekirdek). `ml/tests/test_docs_consistency.py`
bolum numaralarinin artan ve benzersiz olmasini, test sayilarinin tutarliligini ve atif
edilen yollarin varligini korumaya devam ediyor.

## 51. Faz 7 — ölçüm hattı ve kapasite kararı

Faz 7'nin mimari katkısı yeni bir ağ ya da arama değil, **ölçüm hattının
sözleşmeye bağlanması**dır. Bu bölüm, hattın bileşenlerini ve Aşama B'nin
kapasite kararını kaydeder.

### 51.1 Ölçüm hattı bileşenleri

| Bileşen | Sözleşme |
|---|---|
| `ml/er_power.py` | `required_n`, `sigma_ci`, `power_curve`; güç hesabı **üst güven sınırından** |
| `ml/gnubg_hint.py` | `hint` hakemi; hamle filtresi genişletme, perspektif çevirme, sansür tespiti |
| `ml/measure_integrity.py` | Dört bağımsız doğrulama probu; biri düşerse ölçüm hattı durur |
| `ml/proof_corpus.py` | 2 000 pozisyon, SHA-256 dondurulmuş |
| `ml/human_ladder.py` | 7 basamaklı merdiven; ölçülmeyen basamak `unmeasured` |
| `ml/critical.py` | Kritik karar maskesi + ağırlık; `degenerate` bayrağı |
| `ml/capacity_bench.py` | Profil paritesi, throughput, iki bacaklı karar kuralı |
| `ml/export_ckpt.py` | Checkpoint → ONNX (F7-10) |
| `Backgammon.MatchBench decision-latency` | Gerçek ONNX ile depth-N p50/p95 |

**Kural.** Hiçbir sayı kaynağı yazılmadan rapora girmez. Her ölçüm satırı
`measured` / `literature` / `unmeasured` etiketlerinden birini taşır.

### 51.2 Hakem sözleşmesi (F7-01…F7-04)

| Derinlik | Yöntem | Gerekçe |
|---|---|---|
| 0, 1, 2 | `eval` | `hint@2` ≠ `eval@2` (F7-04); `eval` %100 kapsama |
| 3, 4 | `hint` + hamle→afterstate eşlemesi | `eval` 2-ply'da tavan yapar (F6-32) |

`hint` kullanıldığında hamle filtresi **her** `level in range(plies)` için
`1000 0 0.0` yapılır (F7-01) ve hamle notasyonu hamleyi yapanın perspektifinden
mutlak koordinata çevrilir (F7-02). `hint` en fazla 10 hamle yazdırdığı için
3-ply ve üzeri **sansürlüdür** (F7-03): kapsama %80–92, alt sınır.

### 51.3 Kapasite kararı — `medium` kalır

Bölüm 5.2 iki bacak ister: (a) `large` VAL-ER kazancı ≥ %15, (b) `large` depth 2
p95 ≤ 2 s. Ölçüm (6 shard, 3 000 adım, tohum 11, CPU):

| Profil | Parametre | VAL-ER | SE | depth 2 p95 |
|---|---|---|---|---|
| `medium` | 156 423 | **0,0640** | 0,0119 | 4,4972 s |
| `large` | 642 567 | **0,0664** | 0,0120 | 13,6816 s |

(a) **tutmadı** — `large` %3,7 daha *kötü*, gürültü eşiğinin (0,0025) altında ve
işareti ters. (b) **tutmadı** — 6,8×. Karar: **`medium` kalır, bütçe büyümez.**

**Mimari sonuç.** Kapasite artışı gündemden çıkmıştır. Kalan kaldıraçlar:
üretim derinliği (depth 1), yaprak-cephe toplu değerlendirmesi (F7-09), kritik
karar ağırlığı (politika başlığı %26 kritik), açılış çeşitliliği (Test 97).

### 51.4 F7-10 — eğitim çıktısı sözleşmesi

`ml/train_v2.py` ONNX'i her iterasyonun **başında** aktarır (self-play N-1
modelini kullanmalıdır). Sonuç: koşu sonundaki model yalnızca
`checkpoints/ckpt_vN.pt` içindedir ve `--iterations 1` koşusunda `model_v1.onnx`
**rastgele başlangıçtır**. `ml/export_ckpt.py` bu boşluğu kapatır.

| Model | VAL-ER |
|---|---|
| `model_v1.onnx` (eğitim öncesi) | 0,2631 |
| `model_v1_trained.onnx` (eğitim sonrası) | **0,0640** |

**Kural (yeni).** Bir eğitim betiğinin çıktı sözleşmesi, **hangi dosyanın hangi
ana ait olduğunu** açıkça yazmalıdır. "Eğitim bitti" ile "eğitilmiş model diskte"
aynı şey değildir.

### 51.5 Doğrulama

```
ml/tests                     1394/1394  (3 yavaş/koşullu test atlanır)
Backgammon.Tests             297/297
Backgammon.Inference.Tests   100/100
Backgammon.UI.Tests           88/88
```

Toplam **1879**. Aşama B üç yeni pytest dosyası (`test_critical.py` 76,
`test_capacity_bench.py` 48, `test_export_ckpt.py` 12) ve `StageBDataQualityTests` (9)
ekledi. B3 kararı dört dosya daha ekledi: `test_distill.py` (34), `test_calibrate.py` (32),
`test_critical.py` içindeki 20 marj testi ve `ProductionDepthTests` (10).
550 → **749** (pytest), 64 → **83** (inference).

## 52. Faz 7 — B3 kapsam daraltması: üretim derinliği 1, kalibrasyon önceliği

**Tarih:** 2026-11-17. Aşama B ölçümü `large`'ı eledi (`−%3,7` kazanç, depth 2
p95 13,68 s). Kullanıcı **B3** yolunu onayladı: `medium` kalır, bütçe 1,5 ay,
**ER hedefi ≤ 0,02**, şampiyon iddiası düşer.

### 52.1 Üretim derinliği sabitlendi

`SearchSettings.ProductionDepthPly = 1` (F7-09/F7-15). Gerçek ONNX modeliyle
ölçülen karar gecikmesi:

| Model | Derinlik | p50 | p95 | ONNX çağrısı/karar |
|---|---|---|---|---|
| `medium` | 1 | 0,0233 s | **0,0902 s** | 85 |
| `medium` | 2 | 2,0300 s | 4,4972 s | 6 028 |
| `large` | 1 | 0,0718 s | 0,2598 s | 85 |
| `large` | 2 | 6,5306 s | 13,6816 s | 5 948 |

Maliyet **çağrı sayısıyla** doğrusaldır (~0,35 ms/çağrı, kova boyutundan
bağımsız): depth 2, 84×84 = 7 056 yaprak şans düğümü üretir. Depth 1 bütçenin
**%4,5**'idir.

`SelfPlayConfig.Validate` artık `DepthPly > 1` için `ArgumentException` atar;
`Backgammon.MatchBench decision-latency` varsayılanı 1'dir. Depth 2 **silinmedi**:
çevrimdışı damıtma öğretmeni (depth 3) üretim kapısına tabi değildir.

### 52.2 Kritik karar maskesi onarıldı (Test 98)

Değer kafasının `|equity| >= 0,5` maskesi para oyununda **dejenere**ydi (hedef
equity her zaman ±1). Yeni ölçüt, shard kararının `q` alanından türetilen
**karar marjı** ve **arama değeri**dir:

| Ölçüt | Kritik oran | Etkin oran | Dejenere? |
|---|---|---|---|
| Eski: `\|equity(y)\| >= 0,5` | **%100,0** | %100,0 | **evet** |
| Yeni: `\|best_equity\| >= 0,5` **ve** `marj <= 0,05` | **%33,3** | %88,9 | hayır |

`ExclusiveSamples` artık `margin` ve `best_equity` taşır (probe `.npz`'ye de
yazılır). `build_report` `criterion` alanı döndürür; eski yola düşerse
`criterion = "equity"` + `degenerate = true` yazar.

### 52.3 Kalibrasyon önceliklendirildi

`ml/calibrate.py` CAL/VAL bölmesi yapar (Kural 10: onarım **yalnızca CAL**'da
öğrenilir) ve VAL'de öncesi/sonrası verir:

| Metrik | Öncesi | Sonrası | Kapı | Sonuç |
|---|---|---|---|---|
| Eğim | 0,6447 | **0,9584** | 0,85–1,15 | geçti |
| Korelasyon | +0,9022 | +0,9022 | ≥ 0,75 | geçti |
| MAE | 0,2641 | **0,1782** | ≤ 0,15 | **KALDI** |
| Std oranı | 1,3993 | **0,9414** | 0,7–1,4 | geçti |

Affine onarım `hedef ~ 0,6727 * tahmin + 0,1402`. **Korelasyon değişmez** —
doğrusal dönüşüm Pearson korelasyonunu değiştirmez. MAE kapı dışında kaldığı
için post-hoc onarım **yetmiyor**; `L_cal` yeniden eğitimi (Aşama D) zorunlu ve
**öncelikli**.

### 52.4 Damıtma hacmi tavana bağlandı

`ml/distill.py`: `volume = min(500 000, floor(72 saat × karar/sn))`. Varsayılan
modelde (4,07 s/karar, 8× paralel → 1,9656 karar/sn) 500 000 karar **70,7 saat**.
Tavan aşılırsa koşu **iptal edilmez**, hacim **tavana kadar** düşer. `DEC_DISTILLED = 16`
shard bayrağı v1 okuyucusunda **bilinmeyen** bayrak olarak yok sayılır; shard
biçimi değişmez.

### 52.5 Hedef yeniden tanımı

Hamle kalitesi hedefi **ER ≤ 0,02**'dir (gnubg 4-ply, tek taraflı %95 GA üst
sınırı). Bölüm 4.4'ün birinci koşulu (`GA üst ≤ 0,005`) **uygulanmaz**; Ek B'nin
1. satırı **yazılmaz**. Güç hesabı 0,02 için: σ̂ = 0,109072 → **n = 81** (iki
taraflı) / **115** (tek taraflı); σ̂_üst = 0,124178 → **n = 134**. Bu, 1 670
pozisyonluk kanıt ölçümünü gereksiz kılar.

## 53. Faz 7 — Aşama C: arama damıtma hattı

**Tarih:** 2026-11-17. **Durum:** hat tamam, Test 102 kapısı güçsüz (başarısız).

### 53.1 Sözleşme

`SearchSettings.DistillMode` açıkken arama, kök değeri `SearchResult.RootValue`
(`OutcomeDistribution?`) olarak döndürür. `SelfPlayConfig.DistillMode` derinlik
kuralını **tersine çevirir**: damıtma `DepthPly > 1` ister, damıtmasız koşu
`DepthPly > 1`'i yasaklar (F7-15). `ShardDecisionFlags.Distilled = 16` öğretmen
kararlarını işaretler; shard sürümü **1** kalır ve bilinmeyen bayraklar yok
sayılır.

### 53.2 Veri hedefi

| Hedef | Alan | Not |
|---|---|---|
| Politika | `q` | öğretmenin seçtiği aday dizini |
| Değer | `searchValue` | `SearchResult.EvaluationScore` (skaler equity) |

Shard 6 sınıflı dağılım **taşımaz**; bu yüzden damıtma kolunda değer kafası
çapraz entropi ile değil **equity regresyonu** ile eğitilir ve kalibrasyon
terimi kapatılır (F7-17). Sonuç: `buffer CE` / `equity MAE` sütunları kollar
arasında **karşılaştırılamaz**; tek ortak ölçüt VAL-ER'dir.

### 53.3 Ölçüm

| Kol | Oyun | Derinlik | Karar | Süre | VAL-ER | SE |
|---|---|---|---|---|---|---|
| Kontrol | 20 | 1 | 1 128 | 19,13 s | 0,0883 | 0,0153 |
| Damıtma | 20 | 2 | 1 048 | 1 034,26 s | 0,0602 | 0,0120 |

Kazanç 0,3182, GA [-0,0351; 0,6715] → **kapı başarısız** (güçsüz, reddedilmedi).
Gerekli n: %80 güç için 264, tam %25 kazanç için 427 pozisyon; koşu 70 kullandı.

### 53.4 Ders

`ml/train_v2.py` ONNX'i iterasyonun **başında** yazar (F7-10). Tek iterasyonluk
koşuda `model_v1.onnx` eğitilmemiş ağırlıktır; iki kol bu yüzden bayt bayt aynı
dosya üretti. Doğru yol `ml/export_ckpt.py` ile `ckpt_vN.pt` → ONNX'tir. Aynı
sınıf hata (F6-32, F7-04, F7-10, bu) **dördüncü** kez görüldü: ölçüm hattının
hangi dosyayı okuduğu açıkça yazılmadıkça sessizce yanlış sayı üretiliyor.

---

## 54. Pipeline sağlığı teşhisi (`ml/pipeline_health.py`)

### 54.1 Amaç

"Model kötü" tek bir sayı değildir. Bir model PipBot'u %99,5 yenip yine de
bozuk bir değer kafasına sahip olabilir. Bu ikisi aynı anda doğruysa, daha
büyük ağ **daha emin bir şekilde yanlış** olur. `ml/pipeline_health.py` bu
ayrımı ölçülebilir kılar: yedi bağımsız kapı, tek teşhis.

### 54.2 Yapı

| Öğe | Görev |
|---|---|
| `Gate` | Tek kapının değeri, geçti/düştü, notu |
| `TargetSpread` | TD hedefi vs terminal değer saçılımı (`G7`) |
| `HealthReport` | Kapı listesi + `verdict` + `strength_gap` |
| `gate_*` | Yedi saf fonksiyon (her biri `None` → `olculmedi`) |
| `target_spread` | İki diziden saçılım özeti |
| `spread_from_shards` | Shard → `V_hat` → TD(λ) hedefi → `TargetSpread` |
| `calibration_from_artifact` | Düz ve `before`/`after` biçimlerini okur |
| `pip_win_rate_from_artifact` | `--eval-json` çıktısından PipBot oranı |
| `er_from_artifact` | ER ölçüm JSON'undan ortalama |
| `diagnose` | Artifact'lar → `HealthReport` |
| `build_markdown` | İnsan-okur rapor |

### 54.3 Model yükleme (F7-20)

`ml/model.py::build_model` imzası `build_model(in_dim, h1, h2, *, seed,
output_version, profile)` şeklindedir — **profil adı tek başına geçilemez**.
`spread_from_shards` bu yüzden `CAPACITY_PROFILES[profile][:2]` ile `h1`/`h2`
türetir ve `output_version=2` verir. Ayrıca `BackgammonNetV2` **6 sınıflı
olasılık** döndürür; `replay._predict_values` ise **skaler** bekler. Bu yüzden
model `_EquityValueModel` ile sarılır: `probs @ EQUITY_WEIGHTS` (F7-17 ile aynı
kural). `--model` verilmezse `_ZeroValueModel` kullanılır (`V_hat = 0`).

### 54.4 Teşhis kuralı

`G1` düşerse `temel`; `G1` geçip `G2`/`G3`/`G4`/`G5`/`G7`'den biri düşerse
`pipeline`; hepsi ölçülmüş ve geçmişse `saglikli`; aksi halde `bilinmiyor`.
`G6` (ER) yalnızca `strength_gap` işaretini etkiler. CLI çıkış kodları:
0 `saglikli`, 1 `pipeline`, 2 `temel`, 3 `bilinmiyor`.

### 54.5 Ölçülen sonuç

`G1` 0,9950 **geçti**; `G2` 0,6743, `G3` 0,2683, `G5` 1,3371 **düştü**;
`G4` 0,9016 ve `G7` 3,0227 **geçti**; `G6` 0,0740 **düştü** → teşhis
**`pipeline`**. Ölçek büyütmek bu teşhis altında yanlış kaldıraçtır.

## 55. gnubg öğretmen hattı — politika damıtma

### 55.1 Neden değer kafası yetmez

ER **politika** başı argmax ile ölçülür:
`er_harness` → `gnubg_er.score_afterstates(criterion="policy")` →
`OnnxScorer.logits` → `argmax`. Değer kafası (`probs @ EQUITY_WEIGHTS`) bu
karar yolunda **hiç okunmaz**. Bu yüzden değer kafasını eğitmek ölçülen ER'yi
tanımı gereği değiştirmez. Ölçüm bunu doğruladı: değer kafası MAE 0,0072 /
korelasyon 0,9996 ile eğitildi, ER 0,0740 → 0,0708 (%4).

### 55.2 Hat

```
refgen.random_positions  ->  (board, turn, dice, wo, bo)
        |
        v
afterstate_case()        ->  yasal afterstate'ler, SIRALI (deterministik)
        |
        v
HintReferee.hint()       ->  gnubg 2-ply hamle listesi
        |
        v
gnubg_hint.map_hints()   ->  hamle -> afterstate indeksi
        |
        v
best_index = argmax(equity)  ->  POLITIKA HEDEFI
        |
        v
train_policy_head()      ->  CE(logits, best) + 0,5 * MSE(equity(best), y)
```

### 55.3 Determinizm sözleşmesi

`tools.reference_gen.legal_after_states` bir **küme** döndürür. Küme sırası
koşular arası değişebilir; sıralanmazsa `best_index` etiketleri kayar ve eğitim
**sessizce** bozulur. `afterstate_case` bu yüzden `sorted(keys)` kullanır ve
`test_127j_afterstate_case_sorted` bunu kilitler. Bu, F6-31/F6-32 sınıfındaki
sessiz hataların önlenmesidir.

### 55.4 Veri yapıları

| Tip | Alanlar | Not |
|---|---|---|
| `PolicyPosition` | `vectors`, `best_index`, `best_equity`, `turn`, `dice`, `best_move`, `candidates`, `mapping_failures` | Tek pozisyonun aday kümesi |
| `PolicyDataset` | `x` [M, 221], `offsets` [N+1], `best` [N], `y` [N], `meta` | Ragged; `candidates(i)` dilim döndürür |
| `_pad_policy` | `x` [N, L, 221], `mask` [N, L], `width` | Eğitim için doldurma |

`offsets` şeması seçildi çünkü aday sayısı pozisyondan pozisyona değişir
(ölçümde ortalama 22,4, en fazla 346). Sabit genişlikli doldurma bellek
israfı olurdu; `offsets` + `mask` hem kompakt hem geri alınabilir.

### 55.5 Kayıp

`L = CE(logits_masked, best) + value_weight * MSE(equity(best_probs), y)`

`logits` maske ile `-1e9`'a çekilir (yasal olmayan adaylar). `value_weight`
varsayılan **0,5**: politika ana hedeftir, değer yalnızca destek olur. Değer
terimi tamamen kaldırılsaydı `probs` kafası serbest kalır ve `equity` çıktısı
anlamsızlaşırdı; bu yüzden küçük ama sıfır olmayan bir ağırlık kullanılır.

### 55.6 Ölçülen sonuç

2 000 pozisyon / 4 000 adım / lr 3e-4 / batch 64 → eğitim top-1 1,0000
(**ezber**), VAL-ER **0,0740 → 0,0533** (%28,0 nokta tahmini, SE 0,0108).
Eşleştirilmiş test (§57) GA95'i [−0,0062; +0,0414] verir: sıfırı dışlamıyor.
Karar **`belirsiz`** — nokta tahmini kanıt değildir.

### 55.7 Lisans

gnubg **GPL**'dir. Etiketler yalnızca araştırma/ölçüm içindir; ürün dağıtımı
öncesi lisans netleştirilmelidir (`gnubg_distill.LICENSE_NOTE`).

## 56. Maç gücü analizi

### 56.1 Amaç

Her iddiayı **gerekli n** ve **saptanabilir en küçük fark** olarak yazmak.
Hiçbir sayı iddia değildir.

### 56.2 Formüller

| Ölçüm | Formül |
|---|---|
| Kazanma oranı yarım genişlik | `z * sqrt(p(1-p)/n)` |
| Gereken n (tek örnek) | `ceil(z^2 p(1-p) / hw^2)` |
| İki oran testi (kol başına) | `(z_a sqrt(2 p̄(1-p̄)) + z_b sqrt(p0(1-p0)+p1(1-p1)))^2 / Δ^2` |
| ppg yarım genişlik | `z σ / sqrt(n)` |
| Gereken n (ppg) | `ceil((z σ / hw)^2)` |
| İki ortalama testi (kol başına) | `2 (z_a + z_b)^2 σ^2 / Δ^2` |

### 56.3 Ölçülen sonuçlar (p = 0,55, σ = 2,4, n = 400)

| İddia | Gereken n |
|---|---|
| Kazanma oranı ±0,05 | 381 |
| ppg ±0,10 | 2 213 |
| ppg ±0,05 | 8 851 |
| Şampiyonu yenme (kol başına) | 1 565 |
| ppg farkı (kol başına) | 9 042 |

400 oyunda yarım genişlik **0,0488** (p = 0,55) / **0,0490** (p = 0,50).
İncelemenin örneği olan 0,005'lik fark bunun **1/10'u** → **ölçülemez**.

### 56.4 Karar kuralı

`hw > claimed_delta` ise rapor `notes` içinde `olculemez` ve oran `x` yazar.
Sessizce yazmak yasaktır. `CLAIMED_DELTA = 0,005` (incelemenin örneği).

### 56.5 Sınırlar

* σ_ppg = 2,4 **tahmindir**; `--sigma` ile gerçek değer verilmelidir.
* İki oran/ortalama testleri **bağımsız** örnek varsayar; seri korelasyon
  gerçek gerekli n'i büyütür → sayı bir **alt sınırdır**.
* MET (`mwc_from_met`) yalnızca **okunur**; küp stratejisi ölçülmez.

## 57. Eşleştirilmiş ER testi

### 57.1 Neden

`er_harness measure` iki farklı modeli **aynı** korpus üzerinde ölçer. Bu,
eşleştirilmiş (paired) test yapmayı mümkün kılar: pozisyon zorluğundan gelen
varyans farkta **sadeleşir**. Bağımsız iki örnek testi bu varyansı taşır ve
gereksiz yere güçsüzdür.

### 57.2 API

| Fonksiyon | İmza | Döndürdüğü |
|---|---|---|
| `load_er_losses` | `(path: Path) -> dict[str, float]` | pozisyon adı → `equityLoss` |
| `paired_loss_test` | `(before, after, *, z=1.96) -> dict` | `n`, `meanDiff`, `sd`, `se`, `t`, `ciLow`, `ciHigh`, `excludesZero` |
| `parse_arm` | `(text: str) -> (str, Path)` | `"etiket=yol"` ayrıştırma |
| `distill_verdict` | `(..., paired=None) -> str` | `paired` sıfırı dışlamıyorsa `belirsiz` |

`meanDiff = mean(before − after)`; **pozitif** değer iyileşme demektir.
`excludesZero` yalnızca %95 GA sıfırı dışlıyorsa `True` olur.

### 57.3 Karar kuralı

```
er_after <= target                      -> pipeline
paired verildi ve !excludesZero         -> belirsiz   (VERDICT_UNPROVEN, çıkış 4)
er_after <= er_before * (1 - min_gain)  -> kismi
aksi halde                              -> kapasite
```

`paired` verilmediğinde eski nokta-tahmini kuralı geçerlidir; bu geriye dönük
uyumluluk içindir, **tercih edilen yol `paired` vermektir**.

### 57.4 Rapor bölümleri

`build_markdown` iki yeni bölüm üretir:

* **§4.1 Eşleştirilmiş test** — n, ortalama fark, SE, t, GA95, sıfırı dışlıyor mu.
* **§4.2 Veri hacmi kolları** — `--arm ETIKET=YOL` ile verilen her kol için
  ER ve (varsa) `erBefore`'a göre eşleştirilmiş fark.

### 57.5 Ölçülen sonuç (n = 70)

| Karşılaştırma | Ortalama fark | GA95 | t | Sıfırı dışlıyor |
|---|---|---|---|---|
| değer kafası → politika 2 000 | +0,0176 | [−0,0062; +0,0414] | +1,45 | hayır |
| değer kafası → politika 10 000 | +0,0091 | [−0,0209; +0,0392] | +0,59 | hayır |
| politika 2 000 → politika 10 000 | −0,0084 | [−0,0318; +0,0149] | −0,71 | hayır |

Hiçbiri anlamlı değil. Ayrıca 5× veri ER'yi **kötüleştirdi** (0,0533 →
0,0617): monoton iyileşme yok, yani darboğaz kapasite değil.

### 57.6 Sınırlar

* Normal yaklaşım kullanılır (z = 1,96); n = 70 için t kritik değeri 2,00'dir.
  Sonuç değişmez (t = 1,45), ama n < 30 için bu yaklaşım zayıftır.
* Korpus sabittir (70 pozisyon). n artırmak korpusu büyütmek demektir.
* Eşleştirme yalnızca **aynı** korpus ve **aynı** hakem derinliği için
  geçerlidir; farklı derinliklerde ölçüm yapıldıysa eşleştirme anlamsızdır
  (F7-04).

## 58. Kod denetimi düzeltmeleri (F7-25 – F7-37)

`faz 7 v2.md`'nin on beş kusurundan **13'ü düzeltildi**, **1'i zaten doğruydu**,
**1'i yanlıştı**. Her iddia kaynak koda karşı doğrulandı.

### 58.1 Havuz ve kapasite

`StatePool` yeniden yazıldı: serbest liste artık bir **indeks yığını**
(`_free`, `_rented`, `_freeCount`). `Return()` önce `Array.IndexOf` ile
sahipliği doğrular (yabancı durum `InvalidOperationException`), sonra çift
iadeyi reddeder, sonra `s.Reset()` çağırır. Eski kod tek kontrol olarak
`_available >= _states.Length` kullanıyordu — bu bir **kapasite** kontrolüdür,
sahiplik değil. Havuz üretimde kullanılmıyor (yalnız testler), yani kazanç
sıfır; kusur yine de gerçekti.

`AfterStateList.DefaultCapacity` 2048 → **4096**. Gerekçe ölçüldü: parça
sayısını koruyan arama 1-1 zarda **2139** afterstate üreten bir tahta buldu.
`MeasuredMaxAfterStates = 2139` sabiti ve bu tahtayı kuran regresyon testi
eklendi. 2139 alt sınırdır; 4096 ~1,9× pay bırakır.

### 58.2 Sessiz hatalar

* `LegalMoveGenerator._gen` `int` idi. `int` taşması `int.MinValue`'ya gider,
  `0`'a asla; yani `if (_gen == 0)` koruması **hiç ateşlenmiyordu**. `uint`'e
  çevrildi (`_dedupGen` dahil).
* `AfterStateList.AddPass` hash'i doğrulamadan kopyalıyordu. `[Conditional("DEBUG")]
  VerifyHash` eklendi — Release'te sıfır maliyet, DEBUG'da yakalar.
* `StateFromJson` `phase` alanını yok sayıp her durumu `PreRoll` yapıyordu.
  Artık opsiyonel `phase` okunur (sayı 0-5 veya ad); aralık dışı `FormatException`.
* `DefaultModelPath` fixture'a düştüğünde sessizdi. İki `Console.Error` uyarısı
  eklendi; yol zinciri değişmedi.

### 58.3 Ölçüm yolu

`DiceAveragedEquity` her çağrıda `SearchWorkspace` ve `BackgammonState`
ayırıyordu; `[ThreadStatic]` alanlara taşındı ve her aramadan önce `Reset()`
çağrılır. `BuildBenchList` gereksiz yere 4096'lik liste ayırıyordu; varsayılana
döndü. `RunCrawford` sabit 0,9 equity kullanır — bu **ölçüm tercihidir**, kusur
değil: senaryoları modelden bağımsız ve deterministik yapar. `--model` opsiyonu
eklendi; verilirse aynı senaryolar gerçek `OnnxPolicyValueEvaluator` ile de
koşar ve JSON'a `modelScenarios` / `modelCorrect` yazar.

### 58.4 Düzeltilmeyenler

* **HATA 5** zaten doğruydu: `ResultPoints` küp değerini içermez, Jacoby
  uygulanmıştır. Bir testle sabitlendi.
* **HATA 8** yanlıştı: `SelfPlayAgent` hiç `BackgammonState` tutmaz;
  `SelfPlayRunner` durumu alan olarak taşır. Kod değişmedi.

### 58.5 Kapsam dışı

`crawford` 5/6: `normal-double-pass` senaryosu yanlış cevap veriyor ve bu
**HEAD'de de aynı**. Önceden var olan kusur; ayrı iş (F7-35).
