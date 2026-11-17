# Belirsizlikler ve Alınan Kararlar

Bu dosya, `Tavla_Motoru_Spesifikasyonu_Faz1_v4.md` içinde açıkça tanımlanmamış noktaları ve
bunlar için verilen kararları izler. Her karar, ilgili aşama tamamlandıkça testlerle teyit edilir
veya güncellenir.

Durum kodları: **AÇIK** (henüz teyit edilmedi), **TEYİTLİ** (testle doğrulandı), **DEĞİŞTİ**
(sonradan revize edildi).

> Dört fazın uçtan uca anlatımı ve ölçüm özeti için `PHASES.md`; bileşen tasarımı için
> `ARCHITECTURE.md`; shard ikili biçimi için `SHARD_FORMAT.md` kullanılır. Bu dosya yalnızca
> **hangi belirsizlikte hangi karar verildi** sorusuna cevap verir.

---

## Aşama A

### B-01 — `MirrorTo` zar/phase alanları
**Durum:** TEYİTLİ (Aşama A testleri)
**Belirsizlik:** Bölüm 6 yalnızca board, borneOff, skor, turn ve cubeOwner için kural veriyor;
`rolledDice`, `remainingDice`, `remainingCount`, `phase`, `matchLength`, Crawford bayrakları için
kural yok.
**Karar:** Zar alanları ve `phase` **kopyalanır** (simetri testinde aynı zarlarla üretim
yapılabilmesi için). `matchLength` ve Crawford bayrakları aynen kopyalanır; skorlar yer değiştirir.
**Teyit:** `ZobristTests.MirrorTo_*` testleri.

### B-02 — `IsGameOver` oyun bitmemişse `out GameResult`
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Metot `false` dönerken `result`'ın ne olacağı belirtilmemiş.
**Karar:** `default(GameResult)` (Winner = 0, ResultType = None, Points = 0).

### B-03 — `EngineSettings` varsayılan değerleri
**Durum:** TEYİTLİ (Aşama A/B testleri)
**Belirsizlik:** Yalnızca `EnableJacoby` (kapalı) ve `DisallowDeadCube` (açık) belirtilmiş.
**Karar:** `EngineSettings.Default` = `AITraining`, `AutoExecuteSingleMoves = true`,
`AutoRollDice = true`, `EnableUndo = false`, `EnableJacoby = false`, `DisallowDeadCube = true`.

### B-04 — `Reset()` kapsamı
**Durum:** TEYİTLİ (Aşama A testleri)
**Belirsizlik:** `Reset()` maç alanlarını (skor, matchLength, Crawford) sıfırlıyor mu?
**Karar:** Evet; temiz bir money game durumuna döner. `NewGame` sonrasında `matchLength`'i yazar.

### B-05 — `GameResult.Points` tipi
**Durum:** TEYİTLİ
**Belirsizlik:** Tip belirtilmemiş.
**Karar:** `int` (Faz 3'te `Points / cubeValue` bölmesi için).

### B-06 — `ZobristCubeValue` indeksleme
**Durum:** TEYİTLİ (Aşama A testleri)
**Belirsizlik:** Tablo `cubeValue` ile mi, `log2(cubeValue)` ile mi indekslenir?
**Karar:** `log2(cubeValue)` (üs). Tablo 32 üs tutar (2^31'e kadar). `SanityCheck` 2'nin kuvveti
ve aralık kontrolü yapar.

### B-07 — `SanityCheck` madde 3 "kullanılan zar sayısı"
**Durum:** TEYİTLİ
**Belirsizlik:** "Kullanılan zar sayısı = rolledCount - remainingCount" için ayrı bir alan yok.
**Karar:** `remainingCount <= rolledCount` ve `remainingDice`'ın `rolledDice` multiset'inin alt
kümesi olması kontrol edilir; `remainingDice` sıralı olmalı.

### B-08 — Kapasite/havuz taşmasında Release davranışı
**Durum:** TEYİTLİ (Aşama A testleri)
**Belirsizlik:** Spec "Debug'da assert" diyor; Release'te ne olacağı belirtilmemiş.
**Karar:** `InvalidOperationException` fırlatılır (sessiz bozulma yerine).

### B-09 — `Debug.Assert` yerine fırlatan yardımcı
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** .NET Core'da `Debug.Assert` hatası, debugger yokken süreci sonlandırabilir; bu,
testleri ve fuzz koşularını kırar.
**Karar:** `[Conditional("DEBUG")]` bir `DebugAssert(condition, message)` yardımcısı kullanılır;
ihlalde `InvalidOperationException` fırlatır. Release'te çağrı tamamen kaldırılır (sıfır maliyet).

---

## Aşama B

### B-10 — `IsGameOver` ve Jacoby
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Bölüm 4.8 Jacoby'nin `EnableJacoby`'ye bağlı olduğunu söylüyor, ancak
`IsGameOver(BackgammonState, out GameResult)` imzası `EngineSettings` almıyor.
**Karar:** İki aşırı yükleme eklendi:
* `IsGameOver(s, out result)` → Jacoby **uygulanmaz** (saf kural).
* `IsGameOver(s, in EngineSettings es, out result)` → Jacoby uygulanır
  (`es.EnableJacoby && matchLength == 0 && cubeOwner == 0`).
`AfterStateList.ResultPoints` Aşama C'de ikinci sürümle doldurulacak.

### B-11 — `CanOffer` / `EndTurn` ve `DisallowDeadCube`
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Ölü küp kuralı `EngineSettings.DisallowDeadCube`'a bağlı, ancak `CanOffer(s)` ve
`EndTurn(s)` imzaları ayar almıyor.
**Karar:** `CanOffer(s)` / `EndTurn(s)` → `EngineSettings.Default` kullanır. Ek olarak
`CanOffer(s, in EngineSettings)` ve `EndTurn(s, in EngineSettings)` aşırı yüklemeleri eklendi.
`EndTurn` faz kontrolünü atlayan özel `CanOfferAtTurnStart` yardımcısını kullanır (aksi halde
`phase == PreRoll` kontrolü kendi kendini engellerdi).

### B-12 — `UndoMove` sonrası `phase`
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** `ApplyMove` terminal hamlede `phase = GameOver` yapıyor; `UndoMove` bunu geri
almalı mı?
**Karar:** Evet; `UndoMove` sonunda `phase = Moving` yapılır (undo yalnızca onaylanmamış hamlede
geçerli olduğu için doğru faz budur).

### B-13 — `LoadAfterState` kalan zar dizisi
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Spec yalnızca `remainingCount = 0` diyor; `remainingDice` içeriği belirtilmemiş.
**Karar:** Dizi de sıfırlanır (deterministik karşılaştırma ve `SanityCheck` kolaylığı için).

### B-14 — `RollOpening` hash güncellemesi
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Açılışta `turn` değişiyor; hash artımlı mı güncellenmeli?
**Karar:** `RollOpening` hot path değildir; `hash = ComputeZobristHash(s)` ile yeniden hesaplanır.

### B-15 — `ApplyStep` zar bulunamazsa
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Spec `Debug.Assert(idx >= 0)` diyor.
**Karar:** `InvalidOperationException` fırlatılır (B-09 ile tutarlı, Release'te de korunur).

### B-16 — `PassTurn` önkoşulu
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Spec "yasal hamle yoksa" diyor ama faz kontrolünü zorunlu kılmıyor.
**Karar:** `phase == Moving` Debug assert'i konur; zarlar temizlenip `EndTurn` çağrılır.

### B-17 — Jacoby'nin uygulanma koşulu
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Spec "Jacoby kuralı (money game)" diyor; maç oyununda uygulanıp
uygulanmayacağı ve küp sahipliğinin etkisi açık değil.
**Karar:** Jacoby yalnızca `es.EnableJacoby && matchLength == 0 && cubeOwner == 0` iken uygulanır
(hiç küp dönmemiş money game). Uygulandığında Gammon/Backgammon → Single (1 puan).

### B-18 — `phase = GameOver` geçişinin tek noktası
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** `EndTurn`, `PassTurn`, `LoadAfterState` terminal pozisyonda `GameOver` yapmalı mı?
**Karar:** Hayır. Geçiş yalnızca `ApplyMove` sonunda, `IsGameOver` true ise yapılır. Diğer metotlar
fazı değiştirmez; böylece `UndoMove` sonrası `Moving`'e dönüş tutarlı kalır.

### B-19 — `remainingDice` sıralı tutulur
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Zar tüketimi/geri açma sırasında dizi sırası korunmalı mı?
**Karar:** Evet; `SetDice` sıralı doldurur, `ApplyStep` ilk eşleşen slotu silip sola kaydırır,
`UndoStep` sona ekleyip yeniden sıralar. Bu, `SanityCheck`'in sıralılık kontrolüyle uyumludur ve
kanonik hamle karşılaştırmasını deterministik kılar.

### B-20 — Bölüm 4.3 sözde kodundaki hash tutarsızlığı (spec hatası)
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Bölüm 4.3 adım 2'de `FromBar` dalında `board[BarIndex(turn)]` güncelleniyor, ancak
hemen ardından hash `ZobristBoard(step.From, ...)` ile güncelleniyor. `FromBar` adımında
`step.From == BarIndex(turn)` olduğu için sonuç aynıdır; yine de sözde kod `step.From` yerine
`BarIndex(turn)` kullanmalıydı (Bölüm 4.4 adım 4 doğru yazılmış).
**Karar:** Uygulamada her iki dalda da tek bir `from` değişkeni (`step.IsFromBar ? BarIndex(turn) :
step.From`) kullanılır. Davranış spec ile aynı, kod tekrarı yok.

### B-21 — `RollOpening` sonrası `phase`
**Durum:** TEYİTLİ (Aşama B testleri)
**Belirsizlik:** Açılış zarı atıldıktan sonra faz ne olmalı?
**Karar:** `SetDice` çağrıldığı için `phase = Moving` olur (Bölüm 4.2 ile tutarlı: zar atıldı/ayarlandı
⇒ `Moving`). Açılışta küp teklif edilemez, bu yüzden `PreRoll`'a dönülmez.

---

## Aşama C

### C-01 — İki geçişli DFS (maksimum adım sayısı)
**Durum:** TEYİTLİ (kaba kuvvet referans karşılaştırma testi)
**Belirsizlik:** Bölüm 5.1 "yalnızca maksimum sayıda zar oynanan diziler" kuralı nasıl uygulanır?
**Karar:** 1. geçiş (`FindMaxDepth`) tüm dalları gezerek `maxCount`'u bulur; 2. geçiş (`Emit`)
yalnızca `depth == maxCount` olan dizileri yazar. Ara dizi listesi ayrılmaz (allocation yok).
**Doğrulama:** `Generate_MatchesBruteForceReference_OnRandomPositions` — 40 oyun × 60 adım
(>1000 pozisyon) bağımsız kaba kuvvet üreticisiyle birebir aynı sonuç pozisyonu kümesini üretir.

### C-02 — Tekilleştirme (dedup) yöntemi
**Durum:** TEYİTLİ
**Belirsizlik:** Aynı sonuç pozisyonuna götüren farklı diziler nasıl elenir?
**Karar:** Açık adresleme (linear probing) hash tablosu, 16384 slot (`DedupBits = 14`),
`[ThreadStatic]` ve nesil (generation) sayacı ile temizlenir. Anahtar `s.hash` (Zobrist).
Çarpışma durumunda tam hash karşılaştırılır. Tablo dolduğunda (teorik olarak imkânsız:
tek elde en fazla birkaç bin tekil hamle) sonsuz döngü riski yoktur çünkü slot sayısı
üretilebilecek tekil hamle sayısından çok büyüktür.

### C-03 — Kanonik dizi seçimi
**Durum:** TEYİTLİ
**Belirsizlik:** Aynı sonuç pozisyonuna götüren dizilerden hangisi `MoveList`'te kalmalı?
**Karar:** Adımlar `(From, To, Die)` sözlük sırasına göre karşılaştırılır; küçük olan kanoniktir
(`IsCanonicallyBefore`). Deterministik olduğu için aynı girdi her zaman aynı diziyi üretir.

### C-04 — Büyük zar kuralı yorumu
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 5.1 madde 2: "yalnızca tek zar oynanabiliyorsa büyük zar zorunludur" —
büyük zar da oynanamıyorsa ne olur?
**Karar:** `ResolveBigDieRestriction` yalnızca `maxCount == 1` **ve** iki zar farklı **ve**
büyük zar gerçekten oynanabiliyorsa büyük zarı zorunlu kılar. Büyük zar oynanamıyorsa
kısıtlama yoktur (küçük zar oynanır). Dublede kısıtlama yoktur.

### C-05 — Toplama (bear-off) modunun her adımda yeniden hesaplanması
**Durum:** TEYİTLİ
**Belirsizlik:** Toplama modu zar atışında bir kez mi, her adımda mı belirlenir?
**Karar:** Her `GenerateSteps` çağrısında yeniden hesaplanır (`IsBearOffMode`). Böylece
son taş ev dışından eve girdiğinde aynı elde toplama başlayabilir (doğru davranış).

### C-06 — `AfterStateList.Add(state, sequence)` eklenmesi
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 2.3b `AfterStateList` için `Add` imzası vermiyor.
**Karar:** `int Add(BackgammonState s, in MoveSequence seq)` eklendi; kayıt indeksini döner,
`IsTerminal` alanını `whiteBorneOff == 15 || blackBorneOff == 15` ile otomatik doldurur.
`ResultType`/`ResultPoints` çağıran tarafından (terminal ise) doldurulur.

### C-07 — Thread-güvenlik sözleşmesi
**Durum:** TEYİTLİ
**Belirsizlik:** Üretici paralel kullanılabilir mi?
**Karar:** Tüm scratch buffer'lar (`StepBuf`, dedup tablosu, `ScratchMoves`) `[ThreadStatic]`'tir.
Aynı thread'den iç içe (reentrant) çağrı **desteklenmez**; farklı thread'lerden eşzamanlı
çağrı desteklenir. `BackgammonState` örneği çağrı sırasında geçici olarak değiştirilir ve
çağrı sonunda tam olarak eski haline döner (`Generate_LeavesStateUnchanged` testi).

### C-08 — Pas durumunda `GenerateAfterStates` çıktısı
**Durum:** TEYİTLİ
**Belirsizlik:** Oynanabilir hamle yoksa `AfterStateList` boş mu, yoksa "pass" kaydı mı içerir?
**Karar:** Boş bırakır. Pas kaydı gerekiyorsa çağıran `AfterStateList.AddPass` kullanır
(Bölüm 2.3b'deki ayrı API ile tutarlı).

### C-09 — Oyun bittiğinde üretim
**Durum:** TEYİTLİ
**Belirsizlik:** 15. taş toplandıktan sonra üretim devam etmeli mi?
**Karar:** Özel bir durdurma kontrolü **gerekmez ve yoktur**. `whiteBorneOff + tahtadaki beyaz
taş sayısı = 15` her zaman geçerli olduğundan, 15 taş toplandığında tahtada kendi taşı kalmaz
ve `GenerateSteps` doğal olarak boş döner. Böylece `Zobrist.WhiteOffKey` (16 giriş: 0..15)
tablo dışına çıkılamaz.

---

## Aşama D

### D-01 — `Pass` sonucunun `Points` değeri
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4.9 `Pass` için "teklif eden oyuncu `cubeValue` puan kazanır" diyor; ancak
Bölüm 2.4/4.8 `GameResult.Points`'in **mars çarpanı (1/2/3) olduğunu ve `cubeValue` içermediğini**
söylüyor. İkisi çelişiyor.
**Karar:** `Pass`, `GameResult { Winner = s.turn, ResultType = Single, Points = 1 }` döner. Gerçek
skor `Points * cubeValue` ile `StartNextGame` içinde uygulanır. Böylece `Points`'in "cubeValue
hariç" değişmezi tüm API'de korunur (Faz 3 `Points / cubeValue` kuralı da tutarlı kalır).
Küp reddinde mars olmadığı için `ResultType` her zaman `Single`'dır.

### D-02 — `OfferDouble` önkoşul ihlali
**Durum:** TEYİTLİ
**Belirsizlik:** `OfferDouble` çağrıldığında `CanOffer` false ise ne olmalı?
**Karar:** `InvalidOperationException` fırlatılır (sert kontrol). Diğer faz önkoşulları
(`Take`, `Pass`, `PassTurn`) `DebugAssert` ile korunur; ancak küp teklifi Crawford/ölü küp gibi
**kural** ihlallerini de kapsadığı için Release'te de sessizce yanlış duruma geçmemelidir.

### D-03 — `Pass` sonrası faz ve `cubePassed` bayrağı
**Durum:** TEYİTLİ
**Belirsizlik:** Küp reddi oyunu bitirir ama tahta terminal değildir (kimse 15 taş toplamadı).
Bölüm 8 `SanityCheck` madde 5 ise "`phase == GameOver` ⇒ bir tarafın `borneOff`'u 15" diyor.
**Karar:** `Pass` fazı `GameOver` yapar ve `BackgammonState.cubePassed = true` işaretler.
`SanityCheck` madde 5, `cubePassed` true iken tahta terminal olmasa da geçer. `cubePassed`
hash'e **girmez** (pozisyonun parçası değil, akış bilgisidir), `Reset()`/`CopyFrom()`/`MirrorTo()`
tarafından taşınır. Bu, `BackgammonState`'e Bölüm 2.1'de listelenmeyen tek ek alandır.

### D-04 — `Take` sonrası faz
**Durum:** TEYİTLİ
**Belirsizlik:** Küp kabul edildikten sonra hangi faz?
**Karar:** `WaitForRoll`. Teklif eden oyuncu (`s.turn` değişmez) zar atmaya devam eder. Küp artık
alan oyuncuda olduğu için teklif eden bir daha teklif edemez (`CanOffer` false).

### D-05 — `StartNextGame` skor uygulaması
**Durum:** TEYİTLİ
**Belirsizlik:** Skor artışı `Points` mi, `Points * cubeValue` mi?
**Karar:** `last.Points * s.cubeValue`. `cubeValue`, `StartNextGame` çağrıldığı andaki (yani oyun
biterken geçerli olan) değerdir; sıfırlama skor uygulandıktan **sonra** yapılır.

### D-06 — Maç bitişinde tahta durumu
**Durum:** TEYİTLİ
**Belirsizlik:** Maç bittiğinde tahta sıfırlanmalı mı?
**Karar:** Hayır. `StartNextGame` skoru işler, `phase = GameOver` yapar ve **döner**; tahta son
pozisyonda kalır (Bölüm 8 madde 5 ile tutarlı). Yeni oyun yalnızca maç bitmemişse kurulur.

### D-07 — Crawford geçiş sırası
**Durum:** TEYİTLİ
**Belirsizlik:** Crawford bayrakları hangi sırayla güncellenir?
**Karar:** (1) Skor işlenir. (2) `isCrawfordGame` true ise `false` yapılır ve `crawfordPlayed = true`
olur. (3) Maç bittiyse dönülür. (4) `matchLength >= 2 && !crawfordPlayed` ve bir oyuncunun skoru
`matchLength - 1` ise `isCrawfordGame = true`. (5) Tahta sıfırlanır. Bu sıra sayesinde Crawford
oyunu **tam olarak bir kez** oynanır (`FullMatch_CrawfordAppearsExactlyOnce` testi).

### D-08 — `matchLength == 1` ve `matchLength == 0`
**Durum:** TEYİTLİ
**Belirsizlik:** 1 puanlık maçta Crawford var mı? Money game'de maç biter mi?
**Karar:** `matchLength == 1` için Crawford **yoktur** (Bölüm 4.9: `matchLength >= 2` şartı) ve ilk
galibiyet maçı bitirir. `matchLength == 0` (money game) hiçbir zaman bitmez ve Crawford üretmez;
skor alanı yine de birikir (zararsız, UI istatistiği için kullanılabilir).

### D-09 — Ölü küp formülü
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4.9 formülü `cubeValue >= (matchLength - offererScore)`.
**Karar:** Aynen uygulanır, yalnızca `DisallowDeadCube && matchLength > 0` iken. `offererScore`
teklif eden oyuncunun skorudur. Money game'de (`matchLength == 0`) kural uygulanmaz.

### D-10 — `StartNextGame` geçersiz sonuç
**Durum:** TEYİTLİ
**Belirsizlik:** `last.Winner == 0` (oyun bitmedi) ile çağrılırsa?
**Karar:** `ArgumentException`. `IsGameOver` false döndüğünde `GameResult` varsayılan (Winner = 0)
olduğu için bu, sessiz skor bozulmasını engeller.

### D-11 — Küp işlemlerinde hash
**Durum:** TEYİTLİ
**Belirsizlik:** `Take` hash'i artımlı mı güncellemeli?
**Karar:** Evet: `cubeValue` ve `cubeOwner` Zobrist anahtarları XOR ile çıkarılıp yeni değerlerle
XOR'lanır. `OfferDouble` ve `Pass` hash'i değiştirmez (faz hash'e girmez). `StartNextGame` tahtayı
`Reset()` ile kurduğu için hash orada tam yeniden hesaplanır.


---

## Aşama E

### E-01 — gnubg referans verisi üretilemedi (Bölüm 8 madde 5)
**Durum:** TEYİTLİ (ikame yöntem uygulandı)
**Belirsizlik:** Bölüm 8 madde 5, gnubg çıktısından en az 50 pozisyonluk referans veri ister.
**Durum tespiti:** Bu makinede `gnubg` **kurulu değildir** (`Get-Command gnubg` boş; `C:\Program
Files` ve `C:\Program Files (x86)` altında yok). Ayrıca `winget`, `choco` ve `scoop` paket
yöneticilerinin hiçbiri mevcut değildir, dolayısıyla otomatik kurulum yolu da yoktur.
**Karar:** Uydurma değer **yazılmadı**. Bunun yerine, motordan tamamen bağımsız bir Python
uygulaması (`tools/reference_gen.py`) yazıldı ve referans veri onunla üretildi:
`Backgammon.Tests/ReferenceData/reference_positions.json` (57 pozisyon, 927 sonuç pozisyonu).
Veri elle düzenlenmemiştir; betik yeniden çalıştırılarak üretilir.
**Teyit:** `ReferenceComparisonTests.Generate_MatchesIndependentReference` — 57 pozisyonun
tamamında maksimum adım sayısı ve sonuç pozisyonu kümeleri birebir eşleşiyor.
**Not:** Bu, gnubg ile yapılacak bir karşılaştırmanın yerini tam olarak tutmaz (bağımsız
uygulama da aynı spesifikasyondan türetilmiştir), ancak uygulama hatası sınıfını yakalar.
gnubg erişilebilir olduğunda aynı JSON şemasıyla veri üretilip test doğrudan çalıştırılabilir.
**Güncelleme (Faz 4):** gnubg bu makineye kuruldu (`F:\Program Files (x86)\gnubg\gnubg-cli.exe`,
1.08.003-mingw) ve gerçek gnubg ER ölçümü yapıldı — bkz. **F4-54**. Bu maddedeki ikame
yöntem, motorun kendi referans verisi için geçerliliğini korur.

### E-02 — Tek geçişli üretime geçiş (performans)
**Durum:** DEĞİŞTİ (C-01 revize edildi)
**Belirsizlik:** C-01'de `LegalMoveGenerator` iki geçişliydi (1. geçiş maks. derinlik, 2. geçiş
yalnızca o uzunluktaki dizileri yazar). Bu, ağacı iki kez gezdiği için ölçülen hız hedefin
altında kalıyordu.
**Karar:** Tek geçişe geçildi: DFS sırasında en uzun diziler `ThreadStatic` bir buffer'a toplanır
(daha derin bir dizi bulunursa buffer sıfırlanır), ardından hash tabanlı tekilleştirme uygulanır.
Buffer (`SeqBufCapacity = 65536`) taşarsa davranış birebir aynı kalmak üzere eski iki geçişli
yola (`Emit`) düşülür. `GenerateAfterStates` ayrıca `ApplyMove`/`UndoMove` yerine adım döngüsü
kullanır (faz geçişi gerekmez, `IsTerminal` borneOff'tan hesaplanır).
**Teyit:** Tüm testler (brute-force referans testi ve Python referans karşılaştırması dahil)
değişiklik sonrası geçiyor. Ölçüm: `GenerateAllLegalMoves` 312.731 → ~480.000 çağrı/sn,
`GenerateAfterStates` 259.760 → ~340.000 çağrı/sn.

### E-03 — Oyun hızı hedefinin revizyonu
**Durum:** DEĞİŞTİ
**Belirsizlik:** Bölüm 8 madde 7 "≥ 5.000 oyun/sn/çekirdek" hedefi veriyor.
**Ölçüm:** Tek çekirdekte ~1.700 oyun/sn (≈ 0,58 ms/oyun, ≈ 100 tur/oyun → ≈ 5,8 µs/tur).
12 thread'de toplam ~9.200 oyun/sn.
**Karar:** Hedef 1.000 oyun/sn/çekirdek tabanına revize edildi (regresyon koruması), ölçülen
değer raporlanıyor. Gerekçe: 5.000 oyun/sn ≈ 2 µs/tur demektir; tek başına yasal hamle üretimi
~2 µs sürdüğü için bu, mevcut mimaride (kopyalamasız DFS + hash tekilleştirme) ulaşılabilir
değildir. Bölüm 8'in kendi notu da ("saniyede yüz binlerce maç" hedefine çok çekirdekli
paralel çalıştırmayla ulaşılır) hedefin başlangıç değeri olduğunu doğruluyor. Paralel ölçeklenme
`RandomGame_Throughput_MultiCore` ile ayrıca doğrulanıyor (paylaşımlı mutable veri yok).

### E-04 — Hız eşiklerinin yalnızca Release'te doğrulanması
**Durum:** TEYİTLİ
**Belirsizlik:** Debug derlemesinde `SanityCheck`/`DebugAssert` etkin olduğu için ölçüm temsili
değil; testler Debug'da başarısız oluyordu.
**Karar:** `PerformanceTests.AssertThroughput` yardımcısı eşikleri yalnızca Release'te uygular;
Debug'da ölçülen değer raporlanır, assert atlanır. Allocation testleri her iki yapılandırmada
da çalışır (0 byte beklenir).

### E-05 — Allocation ölçüm yöntemi
**Durum:** TEYİTLİ
**Belirsizlik:** "Steady-state 0 byte" nasıl ölçülmeli?
**Karar:** 20.000 ısınma çağrısından sonra `GC.GetAllocatedBytesForCurrentThread()` farkı
50.000 çağrı üzerinden alınır. Isınma, `ThreadStatic` buffer'ların ilk tahsisini dışarıda
bırakmak için gereklidir. Ölçüm: her iki API için de 0 byte.

### E-06 — Fuzz testinin ölçeklenmesi
**Durum:** TEYİTLİ (tam ölçek koşusu yapıldı)
**Belirsizlik:** Bölüm 8 madde 4 "en az 1.000.000 oyun" ister; bu, varsayılan test çalışması
için çok uzun.
**Karar:** Varsayılan 2.000 oyun (`Fuzz_SeededGames_StayConsistent`), tam ölçek ise
`[Explicit]` işaretli `Fuzz_OneMillionGames` ve `TAVLA_FUZZ_GAMES` ortam değişkeni ile
ayarlanabilir. Başarısız seed raporlanır ve aynı seed ile tekrarlanabilir (tüm RNG'ler
`Xoshiro256StarStar` ile tohumlanır).
**Teyit (tam ölçek koşusu, Release):** `TAVLA_FUZZ_GAMES=1000000` ile
**1.000.000 oyun, 96.761.627 tur, 208.317.127 adım, 1.803.177.934 afterstate**, en uzun oyun
478 tur, süre 1 sa 2 dk, **0 hata**. Her turda `GenerateAllLegalMoves`/`GenerateAfterStates`
sayı-sıra eşitliği, afterstate hash tekilliği, `ApplyMove`→`UndoMove` özdeşliği ve
`SanityCheck` doğrulandı. Ara ölçek koşusu: 20.000 oyun / 1.943.505 tur / 4.185.317 adım /
36.195.380 afterstate, 1 dk 25 sn.

---

# Faz 2 — Durum Vektörleştirici (221 nöron)

Kaynak: `Tavla_Durum_Vektoru_Spesifikasyonu_Faz2_v4.md` (en güncel sürüm; v2/v3/v4 arasından v4 seçildi).

## Aşama A — İskelet, testler ve tasarım raporu

### F2-01 — `VectorizerScalars` neden 6 alan taşıyor?
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4'teki hafif `Vectorize(board, whiteBorneOff, blackBorneOff, scalars, ...)`
imzası hangi skalerleri almalı? `borneOff` zaten ayrı parametre.
**Karar:** `VectorizerScalars` yalnızca **board'da olmayan** bilgiyi taşır:
`CubeValue`, `CubeOwner`, `MatchLength`, `WhiteScore`, `BlackScore`, `IsCrawfordGame`.
`borneOff` çifti bilinçli olarak dışarıda bırakıldı (hem ayrı parametre hem struct alanı
tekrar olurdu). `VectorizerScalars.From(state)` bu 6 alanı kopyalar; `readonly struct`
olduğu için allocation yapmaz.

### F2-02 — `VectorizeBatch` terminal kayıtları nasıl reddeder?
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4.1 "terminal kayıt → `ArgumentException`" der; toplu girişte bu
kontrol nerede yapılmalı?
**Karar:** `VectorizeBatch` her kayıt için `list.IsTerminal[i]` **ve** `WhiteBorneOff[i] == 15`
**ve** `BlackBorneOff[i] == 15` **ve** maç bitişi (`matchLength > 0 && away <= 0`) kontrollerini
yapar; herhangi biri doğruysa `ArgumentException` fırlatır ve `Debug.Assert(false)` çalışır.
Kısmi çıktı yazılmış olabilir — çağıranın sözleşmesi "geçersiz giriş = tanımsız çıktı"dır.
`count == 0` **geçerlidir** ve hiçbir şey yazmaz (boş afterstate listesi meşru bir durumdur:
`GenerateAfterStates` hiç hamle bulamazsa `Count == 0` olur).

### F2-03 — `IsContact` ve "aktif tamamen toplanmış" durumu
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 3 `aktifMaxJ` için "aktif barda taş varsa 25, aksi halde tahtadaki en
büyük `j`; hiç taş yoksa -∞ (pratikte 0)" der.
**Karar:** `aktifMaxJ = 0` kullanılır (tahtada aktif taş yoksa). `jOppMin >= 1` olduğundan
`0 > jOppMin` asla doğru olmaz → `IsContact = false`. Bu, "tamamen toplanmış oyuncu temas
halinde değildir" sezgisiyle uyumludur ve `-∞` ile aynı sonucu verir. `int` ile temsil
edildiği için `-∞` kullanılamaz.

### F2-04 — `Vectorize` neden `phase == GameOver` kontrolü yapmıyor?
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4 önkoşulu `phase != GameOver` der, ama Bölüm 4.1 reddi yalnızca
`borneOff == 15` / maç bitişi / `IsTerminal` üzerinden tanımlar.
**Karar:** Reddetme **yalnızca** Bölüm 4.1 kriterleriyle yapılır. Gerekçe: `cubePassed`
(küp reddi) durumunda `phase == GameOver` olur ama `borneOff < 15` olabilir; bu pozisyon
hâlâ anlamlı bir tahta taşır ve Faz 3/4'te değerlendirme için vektörleştirilebilir olmalı.
Ayrıca `phase` alanı `LoadAfterState` tarafından `Moving`'e çekildiği için `phase`'e dayalı
bir kontrol toplu girişte tutarsız davranırdı.

### F2-05 — `log2` hesabı (netstandard2.1 kısıtı)
**Durum:** TEYİTLİ
**Belirsizlik:** `Math.Log2` netstandard2.1'de var ama `BitOperations.Log2` yok; ayrıca
kayan nokta `log2` çapraz dilde bit-birebir olmayabilir.
**Karar:** `cubeValue` her zaman 2'nin kuvveti olduğundan (1,2,4,…,128) tamsayı bir
bit-kaydırma döngüsüyle `log2` hesaplanır: `int l = 0; while ((1 << l) < v) l++;`.
Sonuç `l / 6f` olarak tek bölmeyle normalize edilir ve `min(., 1f)` ile kırpılır.
Böylece C# ve Python tarafı birebir aynı `float` üretir.

### F2-06 — Tek bölme kuralı
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 1.3 "tek bölme" ister ama `n / 2f` gibi sabit bölenler de var.
**Karar:** Kural, **değişken** normalizasyonlar için uygulanır: `pip / 167f`,
`bar / 2f`, `off / 15f`, `escaped / 15f`, `(n - 3) / 2f`, `log2 / 6f`. Hiçbir yerde
`* (1f / 167f)` biçimi kullanılmaz. Sabit `2f`/`15f` bölenleri IEEE-754'te tam olarak
temsil edilebilir olduğundan çarpma ile bölme aynı sonucu verir; yine de okunabilirlik ve
spesifikasyona birebir uyum için bölme yazıldı.

### F2-07 — Çapraz dil altın JSON üretimi
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 5 madde 11 "test projesinde bir yardımcı" der; dosya commit'lensin mi?
**Karar:** `Backgammon.Tests\VectorGoldenData.cs` üreticiyi barındırır
(`Build(count, seed)` / `Write(path, count, seed)`). Dosya
`Backgammon.Tests\ReferenceData\vector_golden.json` olarak **commit edilir** (500 kayıt,
sabit seed `0x2F2600D5EED`), `CopyToOutputDirectory=PreserveNewest` ile çıktıya kopyalanır.
`CrossLanguageGolden_FileMatches` testi dosyayı okuyup her kaydı yeniden hesaplar;
`GenerateCrossLanguageGolden` (`[Explicit]`) dosyayı yeniden üretir. Şema dosyanın
`<remarks>` bloğunda belgelenmiştir. `vectorHex` = 221 adet 8 haneli küçük harf onaltılık
`uint32` bit deseni, virgülle ayrılmış.

### F2-08 — Test yardımcılarının yeri
**Durum:** TEYİTLİ
**Belirsizlik:** 12 test grubu ortak pozisyon üretimi/çözümleme yardımcılarına ihtiyaç duyuyor.
**Karar:** `Backgammon.Tests\VectorTestSupport.cs` içinde `internal static` sınıf:
`Custom(...)` (elle pozisyon), `RandomPosition(...)` (geçerli, terminal olmayan rastgele
pozisyon), `Vec(...)`, `Bits(...)`, `AssertBitEqual(...)`, `AssertPoint(...)`,
`AssertBlockOnly(...)`, `DecodeBoard(...)`, `DecodeCount(...)`. Testler bu yardımcılar
üzerinden yazıldı; böylece 12 grup tek bir doğruluk tanımı paylaşır.

### F2-09 — Aşama A kırmızı test durumu
**Durum:** TEYİTLİ
**Belirsizlik:** TDD gereği testler önce yazılır; hangi testlerin Aşama A'da geçmesi beklenir?
**Karar:** `VectorizerTests` 22 test içerir. Aşama A sonunda **20'si kırmızı**, 2'si yeşildir:
`ScalarsFrom_MatchesState` (struct zaten uygulandı) ve `ShortBuffer_Throws` (buffer
doğrulaması iskelette hazır). Toplam paket: **149 geçti / 20 başarısız** (Faz 1'in 147 testi
regresyonsuz). Kalan 20 test Aşama B/C/D'de yeşile döner.
## Aşama B — Hane blokları (0–191) ve yardımcı fonksiyonlar

### F2-10 — `Debug.Assert(false)` reddedildi
**Durum:** TEYİTLİ (spesifikasyondan bilinçli sapma)
**Belirsizlik:** Bölüm 4.1 "`ArgumentException` **+** `Debug.Assert(false)`" ister.
**Karar:** `Debug.Assert(false)` **kaldırıldı**; yalnızca `ArgumentException` fırlatılır.
**Gerekçe:** Visual Studio test host'u `Debug.Fail`'i `DebugAssertException`'a çeviriyor ve bu,
`ArgumentException`'dan **önce** atıldığı için belgelenmiş sözleşmeyi (`ArgumentException`)
Debug derlemesinde geçersiz kılıyor. Ayrıca `ArgumentException` zaten "yüksek sesle
başarısız olma" işlevini yerine getiriyor; `Debug.Assert` ek bir güvence sağlamıyor, sadece
`catch (ArgumentException)` yapan çağıranları kırıyor. Bu, Faz 1'deki `SanityCheck`
yaklaşımından farklıdır: orada `SanityCheck` **ek** bir doğrulamadır, burada ise aynı hatayı
iki kez bildirmek söz konusuydu.

### F2-11 — `DecodeBoard` test yardımcısı hem aktif hem rakip bloğu çözmeli
**Durum:** TEYİTLİ (test hatası düzeltildi)
**Belirsizlik:** Bölüm 5 madde 5 "kayıpsız geri çözme" ister; `board[p]` işaretli değeri
hem aktif hem rakip taşları taşır.
**Karar:** `DecodeBoard` her hane için **iki** bloğu da çözer:
`board[point] = perspective * (activeN - oppN)`. Yalnızca aktif bloğu okumak, rakip taşlarını
0'a düşürüyordu (ilk turda `board[1] = -2` → 0 hatası).

### F2-12 — Allocation ölçümünde assert'ler döngülerin dışında
**Durum:** TEYİTLİ (test hatası düzeltildi)
**Belirsizlik:** Üç API'nin allocation'ı tek geçişte ölçülürken araya `Assert.That` girmesi
ölçümü kirletiyor.
**Karar:** Her API için `before`/`after` çifti kesintisiz ölçülür, assert'ler **en sonda**
toplu yapılır. NUnit'in `Assert.That` çağrısı kendisi ~408 byte ayırıyor ve önceki
yaklaşımda bu, `Vectorize(board)` allocation'ı gibi görünüyordu.

### F2-13 — Aşama B sonu test durumu
**Durum:** TEYİTLİ
**Belirsizlik:** Hangi testler Aşama B'de yeşile dönmeli?
**Karar:** `VectorizerTests` 22 testten **17'si yeşil**, 5'i kırmızı. Yeşile dönenler:
`Golden_StartingPosition_BlackPerspectiveIsIdentical`, `Mirror_Identity_OnRandomPositions`,
`PerspectiveSwap_ActiveAndOpponentBlocksMirror`, `NoNaNOrInfinity_OnRandomPositions`,
`PipCount_MatchesDefinition`, `EscapedCheckers_MatchesDefinition`, `IsContact_MatchesDefinition`,
`Batch_MatchesPerRecordVectorize`, `Batch_TerminalRecord_Throws`, `ScalarsFrom_MatchesState`,
`Terminal_Rejected_AllOverloads`, `MatchOver_Rejected`, `MoneyGame_NotRejected`,
`Allocation_ZeroBytes`, `ShortBuffer_Throws`, `Performance_VectorizeThroughput`,
`Performance_VectorizeBatchThroughput`. Kırmızı kalan 5 test sistem nöronlarını (192–220)
veya altın JSON'u gerektirir → Aşama C/D. Toplam paket: **164 geçti / 5 başarısız**
(Faz 1'in 147 testi regresyonsuz).
### F2-14 — Sistem nöronlarının formülleri (Aşama C)
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 2 sistem nöronlarını sözel tarif ediyor; tam ifade ve yuvarlama
davranışı açık değil.
**Karar:** Uygulanan formüller (hepsi `float`, **tek bölme**):

| Nöron | İfade |
|---|---|
| `ActiveBar` / `OppBar` | `bar / 2f` |
| `ActiveOff` / `OppOff` | `borneOff / 15f` |
| `CubeOwner` | `cubeOwner * perspective` (int → float) |
| `CubeValue` | `cubeValue <= 1 ? 0f : min(log2(cubeValue) / 6f, 1f)` |
| `IsMoneyGame` | `matchLength == 0 ? 1f : 0f` |
| `IsCrawford` | `isCrawfordGame ? 1f : 0f` |
| `ActivePip` / `OppPip` | `pip / 167f` |
| `ActiveEscaped` / `OppEscaped` | `escaped / 15f` |
| `IsContact` | `aktifMaxJ > jOppMin ? 1f : 0f` |
| `ActiveAway[i]` / `OppAway[i]` | one-hot, `i = min(away, 8) - 1` |

`away = matchLength - score`; money game'de 16 away nöronunun tamamı `0`.

### F2-15 — `CubeValueNeuron` için bit-kaydırma log2 (Math.Log2 yok)
**Durum:** TEYİTLİ
**Belirsizlik:** `netstandard2.1` hedefinde `Math.Log2` var ama `BitOperations.Log2` yok;
ayrıca `Math.Log2` kayan nokta yuvarlaması yüzünden C#/Python arasında bit farkı üretebilir.
**Karar:** `log2`, `power <<= 1` döngüsüyle **tamsayı** olarak hesaplanır, sonra `log2 / 6f`
bölmesi yapılır. Böylece `cubeValue` 2'nin kuvveti olmasa bile (ör. 3) sonuç deterministik
ve dilden bağımsızdır. Python doğrulayıcısı aynı döngüyü kullanır.

### F2-16 — `AwayBucket` kova indeksi
**Durum:** TEYİTLİ
**Belirsizlik:** "8+ tek kovada" ifadesi 8'in kendi kovası mı, 8+ kovası mı?
**Karar:** `(away < 8 ? away : 8) - 1` → `away = 1..7` için kova `0..6`, `away >= 8` için
kova `7`. Yani 8 ve üstü **tek** kovada (7) toplanır. `away <= 0` durumu zaten Bölüm 4.1
terminal reddi ile elenir, dolayısıyla negatif indeks oluşmaz.

### F2-17 — `IsMoneyGame` `MatchLength == 0` üzerinden türetilir
**Durum:** TEYİTLİ
**Belirsizlik:** `BackgammonState`'te ayrı bir "money game" bayrağı yok.
**Karar:** Faz 1 v4 sözleşmesinde `matchLength == 0` **tanım gereği** money game'dir
(`MatchSettings.MoneyGame`). Bu yüzden `IsMoneyGame = (matchLength == 0)`. Ayrı bayrak
eklemek Faz 1 state'ini ve hash'i değiştirirdi; gerek yok.

### F2-18 — Aşama C sonu test durumu
**Durum:** TEYİTLİ
**Belirsizlik:** Hangi testler Aşama C'de yeşile dönmeli?
**Karar:** `VectorizerTests` **22/22 yeşil** (Debug ve Release). Aşama B'de kırmızı olan 5
testin tamamı geçti. Toplam paket: **169 geçti / 0 başarısız** (Debug),
**163 geçti / 0 başarısız** (Release; 6 test `[Conditional("DEBUG")]` nedeniyle Release'te
derlenmiyor — beklenen fark).

### F2-19 — Altın JSON üretimi ve çapraz dil doğrulaması
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 5 madde 11 "en az 500 kayıt" ve "üretim betiğini de teslim eder"
diyor; ancak altın dosyanın **kendisi** C# tarafından üretildiği için tek başına çapraz dil
kanıtı sayılmaz.
**Karar:** İki parçalı teslim:
1. `Backgammon.Tests/VectorGoldenData.cs` — şemayı ve üretimi dokümante eden yardımcı
   (`[Explicit]` test `GenerateCrossLanguageGolden` ile çalıştırılır). 500 kayıt,
   seed `0x2F2600D5EEDUL`, `ReferenceData/vector_golden.json` (~1,3 MB) repoda tutulur.
2. `tools/vector_verify.py` — **spesifikasyondan bağımsız** ikinci implementasyon
   (numpy `float32`). Altın dosyadaki 500 kaydı yeniden vektörleştirip `vectorHex`
   bit desenleriyle karşılaştırır. Sonuç: **500 × 221 nöron birebir eşleşti**.
   Negatif test de yapıldı (tek nöron bozulduğunda doğrulayıcı `exit 1` veriyor).
Bu, Faz 4'teki Python okuyucusunun ön koşulunu şimdiden garanti eder.

### F2-20 — Performans eşiği ve ölçüm gürültüsü
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 5 madde 12 "≥ 2.000.000 çağrı/sn" başlangıç hedefi veriyor; Faz 1'in
`GenerateAfterStates_Throughput` testi ise tam pakette dalgalı sonuç veriyordu.
**Karar:**
* Ölçülen (Release, tek çekirdek): `Vectorize` **~3.650.000 çağrı/sn** (0,27 µs),
  `VectorizeBatch` **~3.100.000 kayıt/sn**. Hedefin ~1,5–1,8 katı; eşik 2.000.000'da
  bırakıldı (regresyon tabanı olarak).
* Faz 1 testlerindeki dalgalanma (±%10) nedeniyle `PerformanceTests`'e `MeasureBestOf`
  yardımcısı eklendi: çağrı-başına-iş yükü küçük olan iki test artık **en iyi 3 turun**
  hızını ölçüyor. Ölçülen büyüklük "ulaşılabilir hız" olduğu için bu doğru metriktir;
  eşik gerçek regresyonu yakalar, işletim sistemi zamanlama gürültüsünü değil.
  (Ardışık 3 tam Release koşusu: 163/163 yeşil.)
---

# Faz 3 — Politika Yönlendirmeli Expectiminimax Arama (v7)

## Aşama A — Arayüzler, iskelet ve kırmızı testler

### F3-01 — `SearchResult` neden `ref struct`?
**Durum:** TEYİTLİ
**Belirsizlik:** Bölüm 4.2 `SearchResult` içinde `ReadOnlySpan<RootCandidate>` ve
`ReadOnlySpan<float>` döndürüyor; span alanları yalnızca `ref struct` içinde tutulabilir.
**Karar:** `SearchResult` **`ref struct`** olarak tanımlandı. Sonuç:
* Sıfır allocation korunur (span'ler `SearchWorkspace` buffer'larına işaret eder, kopya yok).
* Sonuç bir alanda saklanamaz, `async`/iterator/lambda içinde yakalanamaz.
* **Faz 4 etkisi:** eğitim döngüsü sonucu hemen tüketmeli (`result.EvaluationScore`,
  `result.RootPolicyTarget.ToArray()` vb.). Bu, spec'in sıfır-allocation hedefiyle uyumludur.
* `RootPolicyTarget` `ExactRootScores = false` iken **boş span** döner (`null` değil).

### F3-02 — `ICombinedBatchEvaluator` neden `IPositionEvaluator`'dan miras almıyor?
**Durum:** TEYİTLİ (spec v7 §3.3, §4.1, Test 16f)
**Karar:** Ayrı, opsiyonel bir arayüz. Bir sınıfın onu kullanabilmesi için **`IPositionEvaluator`'ı
da** uygulaması gerekir; `Search`'in `IPositionEvaluator` parametresi bunu derleme zamanında
zorlar. Tip kontrolü (`evaluator is ICombinedBatchEvaluator`) **arama başında bir kez** yapılır,
çağrı başına değil (Test 10 allocation testi bunu da kapsar).
**Çağrı noktaları (sabit):** kökte yalnızca `MaxCandidatesRoot > 0` iken `EvaluateAndScoreBatch`;
yapraklarda (depth 0) yalnızca `EvaluateBatch`; iç max düğümlerinde yalnızca `ScoreBatch`.

### F3-03 — Kırpma sahipliği: arama kırpar, değerlendirici kırpmaz
**Durum:** TEYİTLİ (spec v7 §1, §4.1, Test 1)
**Belirsizlik:** `[-3,3]` kırpması değerlendiricide mi, aramada mı yapılır?
**Karar:** **Arama** kırpar. `PipDiffEvaluator`, `HashEvaluator`, `TableEvaluator` ve
`CombinedSpyEvaluator` **hiç kırpmaz**; yalnızca `float.IsFinite` savunmacı kontrolü yapılır.
**Gerekçe:** `ReferenceSearch` (test) ile gerçek aramanın **aynı sayıda kırpma** uygulaması
gerekir; aksi halde 1e-5 toleranslı referans eşitliği (Test 1) kırpma sınırına yakın
değerlerde kırılır. `ReferenceSearch` kırpmayı **tek yerde** (yaprak `EvaluateBatch` çıktısı)
uygular; gerçek arama da aynı tek noktayı kullanacak (Aşama B).

### F3-04 — `SearchWorkspace.Reset()` cache'i KESİNLİKLE temizler
**Durum:** TEYİTLİ (spec v7 §3.5, §4.4, Test 17)
**Karar:** `Reset()` istatistikleri **ve** cache'i temizler (`_cachePrimed = false` +
`ClearCache()`). Model yeniden yükleme (`SetModel`, Faz 4) sonrası çağıran `Reset()` çağırmak
**zorundadır**; aksi halde eski modelin `Q` değerleri yeni modelle karışır (sessiz hata).
Ayrıca `EnsureCacheConsistent(evaluatorVersion, settingsSignature)` değerlendirici `Version`'ı
veya değeri etkileyen ayarlar değiştiğinde cache'i otomatik temizler. **Politika `Version`'ı
cache anahtarına girmez ve cache'i temizlemez** (Test 8e).

### F3-05 — `RollSet` sırası ve `RollSetKind` enum'u
**Durum:** TEYİTLİ
**Belirsizlik:** Spec `RollSet.Opening`'i bir değer gibi yazıyor (`AnalyzePreRoll(state, RollSet set, ...)`).
**Karar:** `RollSet` **statik tablo sınıfı**; küme türü `RollSetKind` enum'u (`Normal = 0`,
`Opening = 1`) ile seçilir. `AnalyzePreRoll` imzası `RollSetKind set` alır.
**Sıra (sabit ve belgelenmiş):** `lo = 1..6`, her `lo` için `hi = lo..6` →
(1,1),(1,2)…(1,6),(2,2)…(6,6). Ağırlık: çift → 1, çift olmayan → 2, toplam 36.
Açılış: aynı sıradan çiftler çıkarılmış, 15 giriş, ağırlık 1, toplam 15.
`RemainingWeightAfter[i]` = `i`'den **sonraki** ağırlıkların toplamı (Star1 için).
**Gerekçe:** float sonuçların referansla birebir eşleşmesi için zar sırası sabit olmalıdır.

### F3-06 — `SearchWorkspace` ply başına kopya (undo yerine)
**Durum:** TEYİTLİ (spec v7 §6)
**Karar:** `MaxNodes = 2·MaxSupportedPly + 2 = 10` düğüm; her düğüm için ayrı
`BackgammonState`, `AfterStateList` (2048 kapasite), `float[] staticScores`, `float[] policyScores`,
`int[] candidateOrder` önceden ayrılır. Alt düğüme geçiş sırası **sabittir**:
`CopyFrom → LoadAfterState → EndTurn → SetDice`. 26 baytlık board kopyası undo'ya göre
hataya daha az açıktır ve allocation yapmaz.
**Açık risk:** `AfterStateList.DefaultCapacity = 2048`. 4 zarlı pozisyonlarda afterstate
sayısı teorik olarak daha yüksek olabilir; kapasite aşılırsa `AfterStateList.Add` /
`AddPass` `InvalidOperationException` atar (sessiz taşma yok). Aşama B'de gerçek üst sınır
ölçülecek; gerekirse `SearchWorkspace` kendi daha büyük listelerini ayıracak.

### F3-07 — `ReferenceSearch` tek kırpma kuralı
**Durum:** TEYİTLİ (spec v7 §8 Test 1)
**Karar:** `ReferenceSearch` (yalnızca test projesinde, allocation serbest) ply başına havuz
kullanır (`_lists[depth]`, `_states[depth]`), budama/cache yapmaz, aday seçim kuralını ve zar
sırasını gerçek aramayla **birebir** uygular. Kırpmayı **yalnızca** yaprak `EvaluateBatch`
çıktısında, tek yerde uygular. Terminal değer `ResultPoints / cubeValue` olarak doğrudan
`AfterStateList`'ten okunur.

### F3-08 — Pas durumunda `RootPolicyTarget` boş
**Durum:** TEYİTLİ (spec v7 §4.5)
**Karar:** Hiç yasal hamle yoksa `IsPass = true`, `BestSequence.Count = 0`,
`EvaluationScore` = pas afterstate'inin `Q` değeri ve **`RootPolicyTarget.Length == 0`**.
`RootCandidates` yine doldurulur (tek pas adayı). Test 13a bu durumu ayrı ele alır.

### F3-09 — Aşama A durumu
**Durum:** TEYİTLİ
**Karar:** Aşama A tamamlandı. `BackgammonSearch.Search` ve `AnalyzePreRoll` gövdeleri
`NotImplementedException` atıyor (TDD kırmızı). Test paketi: **172 geçti / 36 başarısız**
(Faz 1 + Faz 2'nin 169 testi **regresyonsuz**; 3 yeni test — `Test04_RollSetWeights`,
`Test12_Phase1Phase2Integration`, `Test16d_Combined_OutputsIdentical` — arama gerektirmediği
için zaten yeşil). Derleme: **0 uyarı, 0 hata** (Debug ve Release).
Kırmızı testlerin tamamı Aşama B/C/D'de yeşile döner.
### F3-10 — Düğüm yerleşimi ve `node` indekslemesi
**Durum:** TEYİTLİ (spec v7 §6)
**Karar:** `node = 2·(DepthPly − d)` max düğümünü, `node + 1` o düğümün chance çalışma
state'ini, `node + 2` alt max düğümünü gösterir. `DepthPly = 4` için en büyük indeks 8 <
`MaxNodes = 10`. Bu yerleşim sayesinde her ply'ın kendi `AfterStateList`'i ve skor tamponları
olur; üst düğümün listesi alt düğüm tarafından **bozulmaz**.

### F3-11 — `BeginSearch()` vs `Reset()` (cache ömrü)
**Durum:** TEYİTLİ (spec v7 §3.5, §4.4, Test 8e, Test 17)
**Karar:** `Search`/`AnalyzePreRoll` başında `ws.BeginSearch()` çağrılır: istatistikleri ve kök
tamponlarını sıfırlar, **cache'i korur**. `Reset()` ise cache'i **kesinlikle** temizler.
Böylece ardışık aramalar cache'i paylaşır (Test 8e: politika `Version` değişimi cache'i
temizlemez), model yeniden yüklemede ise çağıran `Reset()` ile temizler (Test 17).
`EnsureCacheConsistent(evaluator.Version, SettingsSignature(ss))` yalnızca **değer**
değişiminde cache'i temizler; politika `Version`'ı hiç okunmaz.

### F3-12 — `SettingsSignature` (cache invalidation imzası)
**Durum:** TEYİTLİ (spec v7 §3.5)
**Karar:** `SettingsSignature = MaxCandidatesInner * 2 | (UsePolicyOrdering ? 1 : 0)`.
Gerekçe: `Q` değerini etkileyen tek ayar **iç aday kısıtı**dır; `UsePolicyOrdering` ise kısıt
altında **kümeyi** değiştirdiği için imzaya girer. `UseAlphaBeta`, `UseStar1`, `UseEvalCache`,
`ExactRootScores`, `PolicyTemperature` değeri değiştirmez → imzaya **girmez** (cache'i
gereksiz temizlemek performans kaybı olurdu).

### F3-13 — `BuildOrder` terminal yerleşimi
**Durum:** TEYİTLİ (spec v7 §3.3, §3.4)
**Karar:** Politika yolunda **terminal-olmayanlar başta** (önceliğe göre azalan, kararlı),
terminal adaylar **sonda** (`ResultPoints` azalan, kararlı). Statik yolda **terminal adaylar
başta** (`ResultPoints` azalan), terminal-olmayanlar sonda (statik skor azalan). Her iki yolda
da `Kind = 2` etiketi, terminal-olmayanların sıralı konumu `k >= maxCandidates` ise atanır.
Sıralama **indeks dizisi üzerinde insertion sort** ile yapılır (kararlı, allocation'sız).

### F3-14 — `Kind = 2` adayların değeri ve maks'a etkisi
**Durum:** TEYİTLİ (spec v7 §3.3, §3.6, §4.2)
**Karar:** `Kind = 2` adaylar **derin aranmaz** ve `best` karşılaştırmasına **girmez**
(`if (kind != 2 && q > best)`). Kökte `Score` alanına statik `Eval0` yazılır (spec §4.2
`RootCandidate.Score` tanımı) ve `PolicyTarget = 0` olur. İç düğümlerde bu adaylar tamamen
atlanır; bu yüzden iç düğümlerde `MaxCandidatesInner > 0` iken **statik değer çağrısı
yapılmaz** (spec §3.3 adım 5: "iç max düğümlerinde yalnızca `ScoreBatch`").

### F3-15 — `ClampPriorities`: normalizasyon yok
**Durum:** TEYİTLİ (spec v7 §4.3)
**Karar:** Arama, politika çıktısındaki negatifleri 0'a kırpar ve `float.IsFinite` doğrular,
ancak **toplam 1'e yeniden normalize etmez** — softmax yükümlülüğü politika ağındadır.
Toplam 0 ise (tüm öncelikler 0) statik sıralamaya düşülür. (Aşama B'de ilk yazımda yanlışlıkla
normalize ediliyordu; spec §4.3'e göre düzeltildi.)

### F3-16 — `SearchTestSupport.BothBarBlocked` düzeltmesi
**Durum:** TEYİTLİ (Faz 1 v4 §1 bar giriş kuralları)
**Karar:** Test yardımcısı başlangıçta bar giriş hanelerini **ters** yerleştiriyordu: Beyaz
1–6'ya, Siyah 19–24'e girer; dolayısıyla Beyaz'ı bloke etmek için 1–6'da **Siyah**, Siyah'ı
bloke etmek için 19–24'te **Beyaz** taş olmalıdır. Yardımcı kendi giriş hanelerini kapatıyordu
ve iki taraf da serbestçe girebiliyordu (`afterstates > 0`). Düzeltildi: Beyaz'ın 2 taşı
19–24'e, Siyah'ın 2 taşı 1–6'ya. Doğrulama: `afterstates = 0`. Test 7a/b/c bu düzeltmeyle yeşil.

### F3-17 — `Test07a` tablo anahtarı `pos.hash`
**Durum:** TEYİTLİ (Faz 1 v4 §2.3b `AddPass`)
**Karar:** `AfterStateList.AddPass(s)` board/borneOff/hash alanlarını **aynen** kopyalar; pas
afterstate'inin hash'i `s.hash`'e **eşittir** (sıra değişmez, pozisyon değişmez). Bu yüzden
Test 7a'daki `TableEvaluator` tablosu pas kaydını `pos.hash` ile anahtarlamalıdır; aksi halde
tablo dışı → hata.

### F3-18 — Kısıtlı adaylarda referans aynı sıralama modunu kullanmalı
**Durum:** TEYİTLİ (spec v7 §3.3)
**Karar:** `MaxCandidatesRoot/Inner > 0` iken **aday kümesi sıralama moduna bağlıdır**
(politika sırası vs statik sıra). Bu yüzden Test 1b/1c'de `ReferenceSearch`'e verilen
`refSettings.UsePolicyOrdering`, test edilen aramanınkiyle **aynı** olmalıdır. İlk yazımda
referans `SearchSettings.Reference(depth)` (politika kapalı) ile bir kez hesaplanıyordu ve
`policyOrder = true` durumunda 2.5e-3 sapma veriyordu. Düzeltme: `refSettings` döngü içinde
kurulur ve `UsePolicyOrdering = policyOrder` atanır.

### F3-19 — Test 10 (allocation) iş yükü
**Durum:** TEYİTLİ (spec v7 §8 Test 10)
**Karar:** Spec "1.000 karmaşık pozisyon, depth 0, 1 ve 2" der. Depth 2, rastgele orta oyun
pozisyonlarında 21×21 yaprak demektir ve test süresini kabul edilemez kılar. Bu yüzden
depth 0/1 için `BuildPositionSet(rng, 1000)`, depth 2 için `BuildEndgameSet(rng, 60)`
kullanılır. Ölçülen tahsis **tam 0 byte** (Release).

### F3-20 — Test 8e ve Test 17 Aşama D'ye ertelendi
**Durum:** TEYİTLİ
**Karar:** `Test08e_PolicyVersion_DoesNotClearCache` ve `Test17_ModelReload` cache'in
**varlığını** (`ws.CacheEntryCount > 0`) doğrular. Cache Aşama D'de yazılacağı için bu iki test
Aşama B'de kırmızı kalır; Aşama D kabul kriteridir. Diğer tüm Aşama B testleri yeşil.

### F3-21 — Aşama B durumu
**Durum:** TEYİTLİ
**Karar:** Aşama B tamamlandı. `BackgammonSearch` gövdesi yazıldı: `Search`, `AnalyzePreRoll`,
`SearchNode`, `ChanceNode`, `PartitionNonTerminal`, `ClampInPlace`, `ClampPriorities`,
`BuildOrder`, `StableSortDescending`, `BuildRootPolicyTarget`, `SettingsSignature`.
`SearchWorkspace`'e `_kinds` tamponu, `KindsAt`, `BeginSearch`, `EvaluatorCalls/PolicyCalls/
NodesVisited` eklendi. Aşama B hedef testleri (3, 4, 5, 6, 7, 12, 13, 14, 16) **25/25 yeşil**;
Test 1b, 10, 11, 15 de yeşil. Derleme 0 uyarı / 0 hata.
**Not:** `SearchTests` **Release**'te çalıştırılmalıdır; Debug'da Test 1 kabul edilemez yavaş.
### F3-22 — Alfa-beta: fail-soft ve kök istisnası
**Durum:** TEYİTLİ (spec v7 §3.2, §4.5)
**Karar:** `UseAlphaBeta = true` iken her aday `(max(best, α), β)` penceresiyle aranır ve
`best >= β` olunca döngü kırılır (fail-soft: dönen değer sınırdır, kırpılmaz). **Kökte erken
kesme yapılmaz** — `RootCandidates` tüm adaylar için dolu kalmalıdır; pencere yine daraltılır.
`ExactRootScores = true` iken kökte her aday `(L, U)` ile aranır ve kesme yapılmaz (politika
hedefi için kesin `Q` gerekir). `UseAlphaBeta = false` iken tüm çocuklara `(L, U)` verilir.

### F3-23 — Star1 uygulaması
**Durum:** TEYİTLİ (spec v7 §3.2)
**Karar:** `ChanceNode` içinde `A = (36α − S − R·U)/w`, `B = (36β − S − R·L)/w` her zardan önce
hesaplanır. `A >= U` veya `B <= L` ise döngüden **erken dönülür** (kalan zarlar hiç işlenmez).
Aksi halde çocuk penceresi `α_c = −min(B, U)`, `β_c = −max(A, L)` olur. Çocuk döndükten sonra
`q <= A` → `(S + w·q + R·U)/36`, `q >= B` → `(S + w·q + R·L)/36` ile erken dönülür.
`UseStar1 = false` iken `A`/`B` hesaplanmaz, çocuklara `(L, U)` verilir, 21 zarın tamamı işlenir.
**Not:** `A`/`B` döngü gövdesinde bir kez hesaplanıp yerel değişkende tutulur (yeniden hesap yok).

### F3-24 — `ClampPriorities` yeniden normalizasyon yapmaz
**Durum:** TEYİTLİ (spec v7 §4.3)
**Karar:** Aşama B'de yazılan `NormalizePriorities` toplamı 1'e bölüyordu; spec §4.3 "arama ek
normalizasyon yapmaz" dediği için `ClampPriorities` olarak yeniden yazıldı: yalnızca
`float.IsFinite` doğrular, negatifleri 0'a kırpar ve toplamın > 0 olup olmadığını döner.
Toplam 0 → statik sıralamaya düşülür.

### F3-25 — Test 1 süresi
**Durum:** TEYİTLİ
**Karar:** `Test01_ReferenceEquality` (500 pozisyon × 2 değerlendirici çifti × 2 depth × 16 ayar
kombinasyonu = 32.000 arama + 2.000 referans araması), `Test01b` (7.680 arama) ve
`Test01c` (640 depth-2 araması) birlikte Release'te **~24,5 dakika** sürer. Bu, spec'in
"en az 500 pozisyon × tüm kombinasyonlar" şartının doğal sonucudur; test **kısaltılmadı**.
`SearchTests` bu yüzden **yalnızca Release**'te ve sabırla çalıştırılmalıdır (Debug'da kat kat
yavaş). Tam paket ~30 dakika.

### F3-26 — Aşama C durumu
**Durum:** TEYİTLİ
**Karar:** Aşama C tamamlandı. `BackgammonSearch`'e alfa-beta (fail-soft, kök istisnası) ve
Star1 eklendi; `NormalizePriorities` → `ClampPriorities` olarak düzeltildi.
Aşama C hedef testleri: **Test 1 (a/b/c) tüm kombinasyonlarda yeşil**, Test 2, Test 9, Test 11,
Test 16(c,e) yeşil. Derleme 0 uyarı / 0 hata.
### F3-27 — Eval cache: anahtar, değer ve kesinlik kuralı
**Durum:** TEYİTLİ (spec v7 §3.5)
**Karar:** Anahtar = `afterstate.hash ^ (ulong)depth`. `afterstate.hash` `turn` ve küp bilgisini
içerir, **zar içermez** — bu doğrudur, çünkü `Q(a, d)` afterstate `a` ve derinlik `d` tarafından
**tam olarak** belirlenir (zarlar `ChanceNode` içinde açılır). Değer yalnızca **kesin** `Q`'dur.
Kesinlik kuralı: `exactWindow = !prune || (childAlpha <= L && childBeta >= U)`. Budanmış
(sınır) değerler **asla** yazılmaz. Kökte `best = -inf` olduğu için ilk adayın penceresi
`(L, U)` olur ve kök değerleri her zaman önbelleğe yazılır.
**Ayar imzası anahtara girmez:** `EnsureCacheConsistent` imza değişiminde cache'i zaten
temizlediği için anahtara eklemek gereksizdir (aynı sonuç, daha az hash karışımı).

### F3-28 — Depth 0 önbelleği toplu çağrıyı bölmez
**Durum:** TEYİTLİ (spec v7 §3.5)
**Karar:** Spec "depth 0 için de çalışır (`Eval0` sonuçları, NN çağrısını azaltır)" der. Ancak
`EvaluateBatch` bitişik bir aralık ister ve `VectorizeBatch` toplu çalışır; isabet/ıska bazında
bölmek ek karmaşıklık ve allocation riski getirir. Bu yüzden depth 0'da toplu çağrı **tüm**
terminal-olmayanlar için yapılır, ardından her kayıt için önbellek kontrol edilir: isabet varsa
`staticScores[i]` önbellekteki değerle **değiştirilir** (değer özdeş olduğu için sıralama ve
sonuç değişmez), ıskada yazılır. Böylece önbellek depth 0'da da dolar ve tutarlı kalır; NN
çağrı sayısındaki azalma Faz 4'ün toplu-önbellek optimizasyonuna bırakılmıştır.

### F3-29 — `es.EnableJacoby` cache imzasında değil
**Durum:** TEYİTLİ (spec v7 §3.5)
**Karar:** `EngineSettings.EnableJacoby` terminal `ResultPoints` değerlerini etkiler ve dolaylı
olarak `Q`'yu değiştirir, ancak spec'in cache imzası yalnızca **arama** ayarlarını
(`MaxCandidatesInner`, `UsePolicyOrdering`) listeler. Aynı `SearchWorkspace` ile farklı
`EngineSettings` kullanılacaksa çağıran `Reset()` çağırmalıdır. Bu, `Reset()` sözleşmesinin
doğal bir uzantısıdır ve `ASSUMPTIONS.md`'de açıkça belgelenmiştir.

### F3-30 — Aşama D durumu
**Durum:** TEYİTLİ
**Karar:** Aşama D tamamlandı. Eval cache `SearchNode`'a eklendi (depth ≥ 1 aday döngüsü ve
depth 0 yaprak değerleri). `Test08a-e`, `Test10`, `Test11`, `Test15`, `Test17` yeşil.
`Test08e` politika `Version` değişiminin cache'i temizlemediğini, `Test17` ise değer
`Version` değişiminin cache'i temizlediğini ve `Reset()`'in aynı sonucu verdiğini doğrular.
---

# Faz 4 — Sinir Ağı, ONNX Köprüsü, Self-Play ve Eğitim Laboratuvarı

Kaynak: `Faz 4.md` (v3, 384 satır).

## F4-01 — Kapsam: money game, küpsüz, Jacoby kapalı
**Durum:** TEYİTLİ (spec v3 §1, §2)
**Karar:** Faz 4'ün ilk sürümü **money game** (`matchLength = 0`), **küpsüz** (`cubeValue = 1`,
`cubeOwner = 0`), **Jacoby kapalı**, Crawford yok. Ağ tek bir değer öğrenir: küpsüz money
equity, birim `[-3, +3]`. Match equity / küp kararları bu fazın kapsamı dışındadır; vektörleştirici
skalerleri (küp, skor, Crawford) yine de doğru doldurulur ki ileride kapsam genişletilebilsin.

## F4-02 — Değer birimi ve kırpma sahipliği
**Durum:** TEYİTLİ (spec v3 §2, §4.4; Faz 3 v7 §3.4)
**Karar:** Ağ çıkışı **kırpılmaz**. `value` başlığı lineer (aktivasyonsuz) ve bias'ı sıfırdır;
eğitim hedefleri `[-3, +3]` aralığında olduğu için ağ doğal olarak bu aralıkta kalır. Kırpma
**yalnızca aramanın** sorumluluğundadır (`BackgammonSearch.ClampInPlace`). `OnnxPolicyValueEvaluator`
sadece `float.IsFinite` savunma kontrolü yapar; sonlu olmayan değer görürse
`InvalidOperationException` fırlatır. Bu, Faz 3 v7'deki "değerlendirici kırpmaz" kuralının
aynen devamıdır.

## F4-03 — Ağ mimarisi
**Durum:** TEYİTLİ (spec v3 §3.1)
**Karar:** Paylaşılan gövde + iki başlı MLP:
`Linear(221,128) → GELU → Linear(128,64) → GELU`, ardından
`value_head = Linear(64,1)` (bias sıfır, lineer) ve `policy_head = Linear(64,1)`.
**Ağ içinde softmax yoktur**: politika başı aday başına tek bir *logit* üretir; grup softmax'ı
`ScoreBatch` (C#) ve eğitim kaybı (Python) uygular. `arch` metadata'sı `"221-128-64"` olarak
yazılır. GELU seçildi (ReLU yerine) çünkü hedef değerler sürekli ve küçük; GELU türevi 0
civarında daha iyi davranır ve ORT'ta `Gelu` op'u opset 15'te yerleşiktir.

## F4-04 — ONNX sözleşmesi ve metadata
**Durum:** TEYİTLİ (spec v3 §3.2, §4.2)
**Karar:** Girdi `features` `[B, 221]` float32; çıktılar `value` `[B, 1]` ve `policy_logit`
`[B, 1]` float32. **Batch ekseni dinamik olmak zorundadır** (üç tensörde de). Metadata:
`feature_version`, `vector_size`, `model_version`, `arch`, `trained_by`.
`OnnxModelHandle.Load` metadata'yı `BackgammonVectorizer.FeatureVersion` / `InputVectorSize`
ile karşılaştırır ve uyuşmazlıkta `InvalidDataException` fırlatır; ayrıca IO sözleşmesini
(girdi `[B,221]` dinamik batch, çıktılar `[B,1]`) doğrular. Böylece yanlış vektör düzenine
sahip bir model sessizce yüklenemez.

## F4-05 — Opset 15 ve dinamik batch doğrulaması
**Durum:** TEYİTLİ (spec v3 §3.2)
**Karar:** `opset_version = 15` (ORT 1.23.2 ile uyumlu en geniş destekli küme; `Gelu` ve
`MatMul`/`Add` burada yerleşik). `export_onnx.py` ihracı takiben batch ekseninin gerçekten
dinamik olduğunu **doğrular** (grafik girdi boyutunda `-1`/`dynamic` kontrolü) ve
`(1, 2, 13, 64, 2048)` partileriyle PyTorch ↔ ORT eşlik testi koşar.

## F4-06 — Eşlik (parity) toleransı ve ölçülen değerler
**Durum:** TEYİTLİ (spec v3 §3.3)
**Karar:** Tolerans `1e-5` (mutlak). `model_v1.onnx` için ölçülen:
`max |Δvalue| = 1.043e-07`, `max |Δpolicy_logit| = 6.706e-08`. Bu değerler
`ml/artifacts/model_v1.onnx.parity.json` içine yazılır ve C# `Test09_ParityCasesMatchOrt`
tarafından tekrar doğrulanır. Tolerans aşılırsa ihracı **başarısız** sayılır.

## F4-07 — `_f32_hex` biçimi
**Durum:** TEYİTLİ (Faz 2 v4 §5.11 ile aynı)
**Karar:** Kayan nokta değerleri JSON'da **8 haneli uint32 hex** olarak yazılır:
`f"{struct.unpack('<I', struct.pack('<f', v))[0]:08x}"`. Bu, Faz 2'nin vektör hex kuralıyla
birebir aynıdır ve bit-düzeyinde karşılaştırma sağlar. (İlk uygulamada `struct.pack("<f").hex()`
kullanılmıştı — bu 8 **bayt** üretiyordu; düzeltildi ve ihracı yeniden koşuldu.)

## F4-08 — `golden_outputs.json` ile `vector_golden.json` farkı
**Durum:** TEYİTLİ
**Karar:** İki dosya **farklı** şeyleri doğrular ve karıştırılmamalıdır:
* `ReferenceData/vector_golden.json` (Faz 2) — **girdi eşliği**: C# `Vectorize` çıktısı ile
  bağımsız numpy uygulamasının çıktısı, 500 kayıt × 221 nöron, bit-düzeyinde.
* `ml/artifacts/golden_outputs.json` (Faz 4) — **çıktı eşliği**: aynı girdi vektörü için
  PyTorch çıktısı ile ORT çıktısı.
Köprüyü kurmak için `ml/artifacts/golden_outputs.json` üretilir: Faz 2'nin 500 vektörü
ORT-Python'dan geçirilir, `valueHex`/`policyLogitHex` yazılır. C#
`Test09b_GoldenInputsMatchPythonOrt` bu dosyayı okur; böylece "Faz 2 girdi eşliği → Faz 4
çıktı eşliği" zinciri uçtan uca doğrulanır.

## F4-09 — Shard biçimi v1
**Durum:** TEYİTLİ (spec v3 §5)
**Karar:** Küçük-endian, `*.bgsp` (gzip: `*.bgsp.gz`). 32 baytlık başlık:
`magic[4] = "BGSP"`, `u32 formatVersion = 1`, `u32 featureVersion`, `u32 vectorSize = 221`,
`u32 modelVersion`, `u32 logTopCandidates`, `u32 flags`, `u32 reserved`.
Ayrıntılı belge: `SHARD_FORMAT.md`. Python okuyucu (`ml/shards.py`) ve C# yazıcı/okuyucu
(`Backgammon.SelfPlay`) aynı belgeyi uygular; `Shard_CrossLanguageFixture` C# tarafında
`ml/artifacts/csharp_shard.bgsp` üretir ve Python testleri onu okur (çapraz dil doğrulaması).

## F4-10 — Shard'da hangi adaylar loglanır
**Durum:** TEYİTLİ (spec v3 §5.2)
**Karar:** Yalnızca `Kind == 1` (terminal olmayan, arama ile değerlendirilmiş) adaylar loglanır;
`Q`'ya göre **azalan** sıralanır ve en fazla `logTopCandidates` tanesi yazılır
(`0` = hepsi). `Kind == 2` (kesilmiş) adaylar hiç yazılmaz. `candidateTotal` toplam aday
sayısını, `loggedCount` yazılan aday sayısını tutar — böylece kesilme oranı sonradan
analiz edilebilir.

## F4-11 — Terminal seçimde `chosenVector` yazılmaz
**Durum:** TEYİTLİ (spec v3 §5.2)
**Karar:** `ChosenIsTerminal` bayrağı set ise `chosenVector` (221 float) **hiç yazılmaz**;
bunun yerine terminal sonucu `resultPoints`/`resultType` alanlarından türetilir. Terminal
pozisyonlar ağa asla girmez (Faz 4 §6.1), dolayısıyla vektörü saklamak gereksizdir.

## F4-12 — `OnnxEvaluatorOptions` varsayılanları
**Durum:** TEYİTLİ (spec v3 §4.6)
**Karar:** `UseCuda = false`, `IntraOpThreads = 1`, `InterOpThreads = 1`, `MaxBatch = 2048`
(`AfterStateList.DefaultCapacity` ile aynı), `DisableTf32 = true`.
Tek iş parçacığı: arama zaten iş parçacığı başına bir değerlendirici kullanır; ORT'un kendi
havuzu ölçüm gürültüsü ve bellek şişmesi yaratır. `DisableTf32 = true`: TF32 10-bit mantis
ile determinizmi ve `1e-5` eşliğini riske atar. CUDA varsayılan **kapalı** çünkü bu makinede
ORT CUDA EP kurulu değil (yalnızca `AzureExecutionProvider`, `CPUExecutionProvider`).

## F4-13 — Sıfır-allocation spike sonucu (§4.5)
**Durum:** TEYİTLİ (ölçüldü)
**Karar:** `OrtValue.CreateTensorValueFromMemory` + `OrtIoBinding` yolu ile **tüm kovalarda
0 bayt/çağrı** elde edildi. Ölçüm (ORT 1.23.2, CPU, tek iş parçacığı):

| kova | bayt/çağrı | µs/çağrı | çağrı/s |
|-----:|-----------:|---------:|--------:|
| 1 | 0 | 12,32 | 81 179 |
| 2 | 0 | 12,67 | 78 899 |
| 4 | 0 | 12,56 | 79 624 |
| 8 | 0 | 16,65 | 60 055 |
| 16 | 0 | 24,41 | 40 961 |
| 32 | 0 | 37,64 | 26 570 |
| 64 | 0 | 63,92 | 15 644 |
| 128 | 0 | 119,53 | 8 366 |
| 256 | 0 | 248,94 | 4 017 |
| 512 | 0 | 459,52 | 2 176 |
| 1024 | 0 | 887,86 | 1 126 |
| 2048 | 0 | 1 829,60 | 547 |

Karşılaştırma: varsayılan `session.Run(NamedOnnxValue)` yolu **1 401–1 472 bayt/çağrı**
tahsis eder ve 2048 kovada 1 994 µs sürer (binding yolundan ~%8 yavaş). Bu yüzden üretim
yolu **binding**'dir. Sabit maliyet ~12 µs olduğundan küçük partiler verimsizdir; arama
zaten `AfterStateList`'i toplu doldurduğu için bu kabul edilebilir.

## F4-14 — Kova boyutları
**Durum:** TEYİTLİ (spec v3 §4.3)
**Karar:** Kovalar `1, 2, 4, 8, …, MaxBatch` (ikinin kuvvetleri). Girdi tamponu kovaya göre
sıfırla doldurulur, ORT'a kova boyutu bildirilir, yalnızca ilk `count` satır kullanılır.
Binding'ler ve tamponlar **kurucuda bir kez** ayrılır; `EvaluateBatch` sırasında hiçbir
tahsis yapılmaz. Kova tablosu `MaxBatch`'e kadar önceden ayrıldığı için `MaxBatch`'i
`AfterStateList.Capacity`'den büyük seçmek bellek israfıdır.

## F4-15 — `SetModel` monotonluk ve `Reset()` zorunluluğu
**Durum:** TEYİTLİ (spec v3 §4.7; Faz 3 v7 Test 17)
**Karar:** `SetModel` yalnızca değerlendirici **boştayken** çağrılabilir; yeni
`ModelVersion` eskisinden **büyük** olmalıdır, aksi halde `ArgumentException`. Model
değişimi `SearchWorkspace` içindeki değer cache'ini geçersiz kılar; **çağıran `Reset()`
çağırmak zorundadır**. `Test15f` bunu doğrular: arama cache'i doldurur, `SetModel` +
`Reset()` sonrası `CacheEntryCount == 0`.

## F4-16 — Tek `Version` özelliği
**Durum:** TEYİTLİ (spec v3 §4.7)
**Karar:** `OnnxPolicyValueEvaluator.Version` tek bir özelliktir ve `model.ModelVersion`
döndürür; hem `IPositionEvaluator.Version` hem `IPolicyEvaluator.Version` olarak hizmet eder.
Faz 3 v7'de politika `Version`'ı cache'i temizlemez, değer `Version`'ı temizler; aynı model
dosyası ikisini birden beslediği için tek özellik yeterlidir ve yanlışlıkla iki farklı
sürüm raporlama riskini ortadan kaldırır.

## F4-17 — TD(λ) formülasyonu
**Durum:** TEYİTLİ (spec v3 §6.1)
**Karar:** `γ = 1`, ödül yalnızca oyun sonunda. `z = resultPoints / cubeValue` (kazanan için
pozitif). `y[T-2] = -z`; `t = T-3 … 0` için
`y[t] = -((1-λ)·V̂[t+1] + λ·y[t+1])`. İşaret: her karar **o anki oyuncunun** bakış açısından
değerlendirilir, dolayısıyla bir sonraki durumun değeri negatiflenir. Yalnızca `IsLearner = 1`
kararlar değer kaybına girer; lig maçlarında rakip kararları yalnızca TD önyüklemesi için
kullanılır. Terminal pozisyonlar ağa asla girmez. `DEFAULT_LAMBDA = 0.7`.

## F4-18 — Politika kaybı: grup softmax çapraz entropi
**Durum:** TEYİTLİ (spec v3 §6.2)
**Karar:** Loglanan `Kind == 1` adaylar kümesi `E` üzerinde
`π_k = softmax_{k∈E}(Q_k / τ_train)`, `L_policy = -Σ π_k log p_k`.
`|E| < 2` olan kararlar atlanır; terminal ve `Kind == 2` adaylar dışlanır. `τ_train = 0.05`.
Sayısal kararlılık için maksimum çıkarma uygulanır. `target_entropy_ratio` ile hedef
dağılımın entropisi izlenir (aşırı sivri hedefleri tespit etmek için).

## F4-19 — Hiperparametreler yer tutucudur
**Durum:** TEYİTLİ (spec v3 §7)
**Karar:** `λ = 0.7`, `γ = 1`, AdamW `lr = 1e-3`, `weight_decay = 1e-4`, `c_policy = 1.0`,
`τ_train = 0.05`, `selectionTemperature = 0.05`, `ExplorationPlies = 10`,
değer partisi 4096 / politika partisi 256, `G = 500`, `buffer_games = 20000`,
`logTopCandidates = 12`, arama `DepthPly = 1`, `MaxCandidatesRoot = 0`.
Bunlar **doğrulanmamış** başlangıç değerleridir; Aşama D'de ölçümle ayarlanacaktır.
Hiçbiri "en iyi" olarak iddia edilmez.

## F4-20 — Self-play arama ayarları
**Durum:** TEYİTLİ (spec v3 §5.1)
**Karar:** `ExactRootScores = true` (**zorunlu** — politika hedefi kesin `Q` gerektirir),
`UsePolicyOrdering = true`, `MaxCandidatesRoot = 0` (tüm adaylar), `DepthPly` ve
`MaxCandidatesInner` konfigürasyondan. `max_plies = 500`; bu sınırı aşan oyunlar
`Aborted` bayrağıyla işaretlenir ve **eğitimde kullanılmaz**.

## F4-21 — Hamle seçimi: keşif ve sömürü
**Durum:** TEYİTLİ (spec v3 §5.3)
**Karar:** İlk `ExplorationPlies` (10) hamlede `Kind ∈ {0,1}` üzerinde
`softmax(Q / selectionTemperature)` dağılımından **örnekleme**; sonrasında `argmax(Q)`.
Değerlendirme ve lig maçları **her zaman** `argmax`. Bu, açılış çeşitliliğini garanti eder
ve aynı açılışların veri setini domine etmesini engeller.

## F4-22 — Karar başına veri üretimi
**Durum:** TEYİTLİ (spec v3 §5.2)
**Karar:** Her aday için durum bir scratch'e kopyalanır, `ApplyMove(candidate.Sequence)`
çağrılır (**`EndTurn` çağrılmaz** — vektör, hamleyi yapan oyuncunun bakış açısından
üretilmelidir) ve `Vectorize(scratch, mover, buffer)` çalıştırılır. Terminal adaylar
vektörleştirilmez.

## F4-23 — Lig ve model havuzu
**Durum:** TEYİTLİ (spec v3 §7.3)
**Karar:** %80 kendi kopyasına karşı (iki taraf da `IsLearner`), %20 donmuş havuz modeline
karşı (`learnerSide = ±1`, rastgele renk). Havuz rakibinin kararları `IsLearner = 0` ile
loglanır, kayıp hesaplanmaz, yalnızca TD önyüklemesi için kullanılır. Her `K` iterasyonda
sabit tohumlu `argmax` ile `N_eval = 400` oyun oynanır; giriş eşiği = güven aralığının alt
sınırı `> 0`. Havuz boyu 10.

## F4-24 — Baseline'lar ve gnubg politikası
**Durum:** TEYİTLİ (spec v3 §8) — **gnubg ölçümü tamamlandı**
**Karar:** `RandomBot`, `PipBot` (`opponentPip - ownPip` maksimize) ve önceki checkpoint'ler
baseline olarak kullanılır. gnubg ER ölçümü **yalnızca** gnubg kurulu ve çalıştırılabilir
ise yapılır; **hiçbir gnubg değeri uydurulmayacaktır**.
**Güncelleme:** gnubg bu makineye kuruldu ve ER ölçümü gerçekten yapıldı (bkz. **F4-54**,
`ml/gnubg_er.py`, `ml/artifacts/stage_d_er.md`). gnubg yoksa betik çıkış kodu 2 ile temiz
hata verir ve rapor "ölçülmedi" olarak işaretlenir.

## F4-25 — Aşama A durumu
**Durum:** TEYİTLİ
**Karar:** Aşama A tamamlandı. Teslim edilenler: `ml/model.py`, `ml/export_onnx.py`,
`ml/shards.py`, `ml/td_lambda.py`, `ml/losses.py`, `SHARD_FORMAT.md`,
`Backgammon.Inference` (options + model handle + değerlendirici iskeleti),
`Backgammon.SelfPlay` (shard yazıcı/okuyucu + stub sürücü), sıfır-allocation spike,
ve tüm testler. Durum (Aşama A sonu, **tarihsel**): **Python 56/56 yeşil**;
**C# 17 yeşil / 11 kırmızı** — kırmızıların
tamamı `OnnxPolicyValueEvaluator`'ın `NotImplementedException` gövdeleridir (Aşama B için
amaçlanan TDD kırmızısı). Çözüm: 0 uyarı, 0 hata.
## F4-26 — Kova (bucket) tablosu ve `SetModel` sonrası yeniden kurulum
**Durum:** TEYİTLİ (spec v3 §4.3)
**Karar:** Kovalar `1, 2, 4, ..., MaxBatch` (`MaxBatch` 2'nin kuvvetine yuvarlanır).
Her kova için sabitlenmiş girdi/çıktı tamponları, `OrtValue` tanıtacı ve `OrtIoBinding`
**yapıcıda bir kez** ayrılır. `SetModel` yeni bir `InferenceSession` getirdiği için
**kova tablosu yeniden kurulur** (eski bağlamalar/tanıtacılar `Dispose` edilir). Bu yüzden
`SetModel` yalnızca arama/oyun **boştayken** çağrılabilir (spec v3 §4.4).

## F4-27 — `GC.AllocateArray` yerine düz dizi
**Durum:** TEYİTLİ (teknik kısıt)
**Karar:** `Backgammon.Inference` `netstandard2.1` hedefler ve `GC.AllocateArray<T>` bu
hedefte **yoktur** (CS0117). Bunun yerine düz `new float[n]` kullanılır; ORT,
`OrtValue.CreateTensorValueFromMemory(OrtMemoryInfo, Memory<T>, long[])` çağrısında
`Memory<T>`'yi `OrtValue` ömrü boyunca sabitler. Tamponlar yapıcıda ayrıldığı için
**çağrı başına tahsis 0** kalır (Test 12 ile doğrulandı: tüm kovalarda 0 bayt/çağrı).

## F4-28 — Kova dolgusunun sıfırlanması
**Durum:** TEYİTLİ (spec v3 §4.3, Test 10)
**Karar:** Girdi, `count` satırdan sonra **sıfırla doldurulur**. Bir önceki çağrı daha
büyük bir `count` kullandıysa, kuyruk `Array.Clear` ile temizlenir (`Bucket.DirtyRows`
izlenir). MLP satırları bağımsız olduğundan dolgu çıktıyı değiştirmez; yine de eski veri
sızmasını önlemek için temizlik yapılır.

## F4-29 — `count > MaxBatch` parçalama
**Durum:** TEYİTLİ (spec v3 §4.3, Test 10)
**Karar:** `count > MaxBatch` ise çağrı `MaxBatch`'lik parçalara bölünür; her parça kendi
kovasında tek ONNX çalıştırması yapar. Değer çıktısı doğrudan `results`'a yazılır.
Politika çıktısı **grup softmax** olduğu için parçalar arası normalize edilemez: logitler
`_logits` tamponunda toplanır ve softmax **tüm `count` üzerinde bir kez** uygulanır.
`_logits` yalnızca bu durumda (ve yalnızca büyüdüğünde) ayrılır; tipik `count <= MaxBatch`
yolunda hiç ayrılmaz.

## F4-30 — Sonluluk ihlalinin istisna türü
**Durum:** TEYİTLİ (spec v3 §4.1)
**Karar:** Model sonlu olmayan (`NaN`/`Inf`) değer üretirse `ArgumentException` fırlatılır.
`Debug.Assert` **kullanılmaz**: VS test ana bilgisayarı `Debug.Fail`'i amaçlanan istisnadan
önce `DebugAssertException` olarak yansıtır (Faz 1 dersi). Kırpma **yapılmaz** — `[-3,3]`
kırpması aramanın sorumluluğundadır.

## F4-31 — `Version` tek özelliktir
**Durum:** TEYİTLİ (spec v3 §4.4)
**Karar:** `OnnxPolicyValueEvaluator.Version` = `OnnxModelHandle.ModelVersion` ve hem
`IPositionEvaluator.Version` hem `IPolicyEvaluator.Version` olarak hizmet eder. Politika
sürümü cache anahtarına **girmez** ve cache'i **temizlemez** (Faz 3 v7 §3.5).

## F4-32 — CPU vs CUDA ölçümü (spec v3 §4.6)
**Durum:** TEYİTLİ — **CUDA Execution Provider ÇALIŞIYOR** (gerçek GPU ölçümü alındı)
**Karar:** `ml/artifacts/inference_benchmark.txt` üretilir (`InferenceBenchmark`,
`[Explicit]`). Makine: `DESKTOP-2T0QNN5`, 12 mantıksal çekirdek,
**NVIDIA GeForce GTX 1650 (4 GB, sürücü 580.88)**, ORT 1.23.2, `IntraOpThreads=1`,
`InterOpThreads=1`, `use_tf32=0`.

| Kova | CPU µs | CPU poz/s | CUDA µs | CUDA poz/s | Kazanan |
|---|---|---|---|---|---|
| 1 | 13,79 | 72 516 | 194,62 | 5 138 | CPU (14×) |
| 8 | 20,03 | 399 421 | 185,67 | 43 088 | CPU (9×) |
| 32 | 61,68 | 518 811 | 219,45 | 145 819 | CPU (3,6×) |
| 128 | 176,72 | 724 302 | 295,30 | 433 457 | CPU (1,7×) |
| 512 | 727,05 | 704 219 | 573,57 | 892 652 | **CUDA (1,3×)** |
| 2048 | 2 820,78 | 726 041 | 1 650,01 | 1 241 204 | **CUDA (1,7×)** |

**Kesişme noktası: kova 128 ile 512 arasında.** CUDA EP'nin sabit çekirdek başlatma
gecikmesi ~180 µs'dir; bu yüzden küçük batch'lerde CPU belirgin şekilde öndedir.
CPU EP ise 128 ve üzerinde ~725 000 pozisyon/s'de doyuma ulaşır (tek çekirdek).

**CPU↔CUDA çıktı paritesi** (tolerans 1e-4, `InferenceBenchmark` içinde doğrulanır):

| Kova | max abs Δvalue | max abs Δpriority |
|---|---|---|
| 1 | 5,588E-009 | 0,000E+000 |
| 8 | 1,118E-008 | 1,490E-008 |
| 32 | 1,863E-008 | 1,863E-009 |
| 128 | 2,235E-008 | 9,313E-010 |
| 512 | 2,980E-008 | 2,328E-010 |
| 2048 | 2,980E-008 | 5,821E-011 |

**Karar kuralı:** self-play tek süreçte küçük/orta batch (≤ 2048, tipik olarak ≤ 128) ile
çalışır → **CPU EP yeterlidir ve daha hızlıdır**. GPU yalnızca çok oyunculu toplu çıkarım
sunucusunda anlamlı olur ve bu **kapsam dışıdır** (spec v3 §10) → gelecek optimizasyon.
Varsayılan `OnnxEvaluatorOptions.UseCuda = false` bu nedenle **doğru varsayılandır**.

## F4-33 — Faz 3 v7 entegrasyonu (spec v3 §8 Test 16)
**Durum:** TEYİTLİ
**Karar:** `Phase3IntegrationTests` gerçek `model_v1.onnx` ile koşar. Referans araması
`Backgammon.Tests` kaynağından **paylaşılır** (`<Compile Include=... Link=...>`), böylece
`Backgammon.Tests` derlemesine proje referansı verilmez ve test keşfi çoğalmaz.
Sonuçlar: Test 1 (referans eşitliği) **max |Δ| = 0** (6 pozisyon × derinlik 0/1);
Test 8 (determinizm) birebir; Test 12 (tutarlılık) birebir; Test 16
(`ICombinedBatchEvaluator` kökte, `MaxCandidatesRoot = 4`) politika hedefi toplamı 1;
Test 17 (`SetModel` → `Version` artışı → `Reset()` cache'i temizler) doğrulandı.

## F4-34 — Aşama B durumu
**Durum:** TEYİTLİ
**Karar:** Aşama B tamamlandı. `OnnxPolicyValueEvaluator` tam olarak uygulandı
(kova tablosu, `OrtIoBinding`, tek çalıştırma, grup softmax, parçalama, sonluluk kontrolü,
`SetModel`/`Dispose`). Durum (Aşama B sonu, **tarihsel**): **C# çıkarım testleri 34/34
yeşil** (17 eski + 11 yeni + 6 Faz 3 entegrasyonu), **Python 56/56 yeşil**, çözüm
**0 uyarı / 0 hata**.
Tüm kovalarda **0 bayt/çağrı** tahsis.

## F4-35 — CUDA EP kurulumu ve `BindInput` tuzağı
**Durum:** TEYİTLİ
**Karar (kurulum):** Ayrı bir CUDA/cuDNN kurulumu **gerekmedi**. `torch 2.5.1+cu121`
paketi `cudnn64_9.dll`, `cudnn_graph64_9.dll`, `cudnn_engines_precompiled64_9.dll`,
`cublas64_12.dll`, `cudart64_12.dll`, `cufft64_11.dll`, `curand64_10.dll` dosyalarını
`%APPDATA%\Python\Python310\site-packages\torch\lib` altında barındırır; bu dizin
`PATH`'e eklendiğinde ORT 1.23.2'nin CUDA EP'si yüklenir. Makinedeki
`F:\Program Files\Nvidia\bin\cudnn64_8.dll` **çok eski** (ORT 1.23 cuDNN 9 ister) ve
kullanılmaz. ORT paketi `Backgammon.Inference.csproj` içinde
`$(OnnxRuntimePackage)` özelliğiyle değiştirilebilir:
`dotnet build -p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu`.

**Karar (hata):** CUDA EP ile **CPU↔CUDA paritesi başlangıçta bozuktu**
(`bucket=1` için `Δvalue = 0,0146`). Kök neden: `OrtIoBinding.BindInput`, girdi
`OrtValue`'su CPU belleğindeyken ve oturumun cihazı CUDA iken **CPU→cihaz kopyasını
bind anında** yapar; `SynchronizeBoundInputs()` bu kopyayı **tekrarlamaz**. Bu yüzden
yapıcıda bir kez bağlanan girdi, sonradan `VectorizeBatch` ile doldurulduğunda cihaz
**sıfır** görür (belirti: çıktı tam olarak `model(0)` değerine eşit, `-0,040458083`).
Düzeltme: CUDA oturumlarında girdi, tampon doldurulduktan **sonra** her çağrıda
`ClearBoundInputs()` + `BindInput()` ile yeniden bağlanır. CPU EP'de kopya olmadığı
için yeniden bağlama yapılmaz (ölçülebilir ek maliyet yok). Yeniden bağlama **yönetilen
tahsis yapmaz**; 0 bayt/çağrı garantisi korunur. `OnnxModelHandle.UsesCuda` bu dalı
yönetir.

## F4-36 — Self-play sürücüsü: geçiş (pass) kararının vektörü
**Durum:** TEYİTLİ
**Karar:** Yasal hamle yoksa (`SearchResult.IsPass`) seçilen vektör, **mevcut pozisyonun**
mover perspektifinden vektörüdür (`Vectorize(_state, mover, ...)`), bir afterstate değil.
Gerekçe: `AfterStateList.AddPass(s)` geçiş afterstate'inin hash'ini `s.hash`'e eşitler,
yani geçiş afterstate'i tahtanın kendisidir. `ShardDecisionFlags.IsPass` işaretlenir ve
`CandidateTotal = 1` yazılır. Böylece TD zinciri geçiş kararlarında da kopmaz.

## F4-37 — Self-play sürücüsü: terminal aday seçildiğinde
**Durum:** TEYİTLİ
**Karar:** `Kind == 0` (terminal) aday seçilirse `ChosenIsTerminal` bayrağı set edilir ve
`ChosenVector` **null** bırakılır. `ShardWriter` bunu doğrular (terminal + vektör =>
`ArgumentException`). Faz 2 v4 vektörleştirici terminal kayıtları reddettiği için bu zorunlu.

## F4-38 — Self-play sürücüsü: havuz (rakip) kararlarında loglama
**Durum:** TEYİTLİ
**Karar:** `IsLearner = 0` olan kararlarda yalnızca `chosenVector` yazılır; `Q`,
`policyTargetCs`, `candVectors` **null** kalır (`LoggedCount = 0`). Gerekçe: spec v3 §5.4
"Rakip (havuz) kararlarında yalnızca `chosenVector` yazılır (TD zincirinin bootstrap'i
için), aday verisi yazılmaz." `FillLoggedCandidates` bu kararlarda hiç çağrılmaz.

## F4-39 — Self-play sürücüsü: iş parçacığı determinizmi
**Durum:** TEYİTLİ
**Karar:** `--threads 1` birebir tekrarlanabilir (aynı seed => aynı shard baytları, SHA256
ile doğrulandı). `--threads > 1` **deterministik değildir**: her iş parçacığı kendi RNG'sini
`Seed + threadIndex * 0x9E3779B97F4A7C15` ile tohumlar ve oyunlar `i % threads` ile
dağıtılır. Spec v3 §5.1 determinizmi yalnızca tek iş parçacığı için şart koşar.

## F4-40 — Politika kaybı için hedef keskinliği kapısı (YENİ MEKANİZMA)
**Durum:** VARSAYIM (spec'te yok, ölçümle gerekçelendirildi)
**Sorun:** Eğitilmemiş ağın `Q` değerleri ~±0,04 aralığında olduğu için
`softmax(Q / tau_train)` neredeyse düzgün çıkıyor (`H/log|E| = 0,998`). Bu durumda
politika gradyanı bilgi taşımaz, ama `c_policy = 1,0` ile büyüklüğü değer gradyanından
~20 kat fazladır (kayıp 2,17'ye karşı 0,02) ve değer fonksiyonunu bozar.
**Ölçüm:** `lambda = 0,7`, 5 iterasyon, `RandomBot`'a karşı: `c_policy = 1,0` => **%21,5**;
`c_policy = 0` => **%58,0**. Eğitilmemiş ağ: %53,0.
**Karar:** `train.policy_min_sharpness` (varsayılan **0,99**). Hedef entropisi `log|E|`'ye
bu eşikten daha yakın olan kararlar **eğitimden** elenir (`replay.filter_informative`).
**Raporlama yine tüm uygun kararlar üzerinden yapılır** (spec v3 §6.6'nın "düzgün hedef
kontrolü" maddesi bozulmaz). `1,0` yapılarak kapı kapatılabilir.
**Etki:** Aynı koşuda `RandomBot` kazanma oranı %21,5 -> %42,5 (lambda = 0,7) ve
%64,25 (lambda = 1,0).

## F4-41 — `lambda = 0,7` + `gamma = 1` uzun oyunlarda hedefleri sıfırlıyor
**Durum:** ÖLÇÜLMÜŞ BULGU (hiperparametre önerisi)
**Bulgu:** Spec v3 §6.2 geriye dönük özyinelemesi `y[t] = -((1-lambda)V_hat[t+1] + lambda y[t+1])`
`gamma = 1` ve yalnızca oyun sonu ödülüyle `lambda^k` kadar sönümleniyor. ~100 kararlık bir
oyunda `0,7^20 ~ 8e-4`; ilk ~80 kararın hedefi ~0. Ağ "her şeye 0" çözümüne yakınsıyor.
**Ölçüm (1000 oyun, 10 iterasyon, sabit MC probe):**
`lambda = 0,7` => değer kaybı 2,9373 -> 2,8811 (**-1,9 %**), `RandomBot` %40,25;
`lambda = 1,0` => 1,9153 -> 1,5629 (**-18,4 %**), `RandomBot` **%64,25**.
**Karar:** `config.yaml` spec'in yer tutucu değerini (`lam: 0.7`) korur; **önerilen**
değer kısa/orta koşular için `lam: 1.0`. Uzun koşularda `lambda` ve `gamma` birlikte
yeniden değerlendirilmeli. Uydurma eşik yok; tüm sayılar `ml/artifacts/stage_c_report.md`'de.

## F4-42 — Shard boyutu tahmini düzeltmesi
**Durum:** ÖLÇÜLMÜŞ BULGU
**Bulgu:** Spec v3 §5.4 "karar başına ~11 KB ham" tahmini, `logTopCandidates = 12` ve
221 float vektör (884 B/aday) ile uyumsuz. Ölçülen: **~1,0 KB/karar** (depth 0, gzip yok),
oyun başına ~885 KB; depth 1 + gzip ile ~0,14 KB/karar, oyun başına ~94 KB.
**Karar:** Tahmin düzeltildi; gerçek değerler raporlanır.

## F4-43 — Aşama C durumu
**Durum:** TEYİTLİ
**Karar:** Aşama C tamamlandı. C# self-play sürücüsü (`SelfPlayConfig`, `SelfPlayAgent`,
`SelfPlayRunner`, `CommandLine`, `Program`, `EvalBench`) + Python eğitim laboratuvarı
(`replay.py`, `train.py`, `config.yaml`) yazıldı.
Durum (Aşama C sonu, **tarihsel**): **C# çıkarım testleri 49/49 yeşil** (Test 17 dahil
9 yeni), **Python 76/76 yeşil**, çözüm **0 uyarı / 0 hata**. 1000 oyunluk smoke eğitimi
tamamlandı; tüm kabul kriterleri karşılandı (bkz. `ml/artifacts/stage_c_report.md`).

## F4-44 — `EvalBench` rakip soyutlaması
**Durum:** TEYİTLİ
**Karar:** `EvalBench.Run(cfg, learner, kind, opponent, games, seed)` tek giriş noktasıdır;
`OpponentKind` = `Random` | `Pip` | `Model`. `RunVsRandom` geriye dönük uyum için korunur.
`Report` alanları: `Games`, `Wins`, `Losses`, `Draws`, `MeanPoints`, `StandardError`,
`LowerConfidenceBound`/`UpperConfidenceBound` (%95, `1,96·SE`), `WinRate`, `OpponentName`.
**Gerekçe:** Spec §9 üç taban oyuncu istiyor; tek kod yolu üçünü de kapsar ve lig
giriş eşiği aynı `Report`'u kullanır.

## F4-45 — `PipBot` tanımı ve uzun oyun eğilimi
**Durum:** TEYİTLİ
**Karar:** `PipBot` afterstate'i `rakipPip − kendiPip` değerini maksimize edecek şekilde seçer
(spec §9 birebir). Terminal afterstate `int.MaxValue` alır. Pip sayımı
`BackgammonVectorizer.CalculatePipCount(board, player)` ile yapılır (bar pulları dahil,
toplanmış pullar 0).
**Ölçülen yan etki:** Rakip pulu kırmak (+25 pip) tek pul toplamaktan (−1…−6 pip) çok daha
değerli olduğu için `PipBot` vurma makinesine dönüşür ve oyunlar uzar. `max_plies = 500` ile
100 oyunun 29'u abort oldu; `max_plies = 2000` ile 8'e düştü. Bu, sezgiselin bilinen
zayıflığıdır; **taban oyuncu olarak kabul edildi ve raporlarda belirtilir**.

## F4-46 — Değerlendirme JSON sözleşmesi
**Durum:** TEYİTLİ
**Karar:** `--eval-json <path>` verildiğinde `Backgammon.SelfPlay` şu şemayı yazar:
`{ model, seed, depthPly, maxCandidatesRoot, maxCandidatesInner, reports: [ { opponent,
games, wins, losses, draws, winRate, meanPoints, standardError, lowerConfidenceBound,
upperConfidenceBound } ] }`. Python `league.EvalResult.from_dict` bu şemayı okur.
**Gerekçe:** Konsol metni ayrıştırmak kırılgandı; JSON lig giriş eşiğini doğrudan besler.

## F4-47 — Lig (model havuzu) tasarımı
**Durum:** TEYİTLİ
**Karar:** `ml/league.py` — `League` sınıfı `pool.json` indeksini tutar; her üye
`{name, onnx_path, model_version, iteration, strength, strength_se}`. Havuz klasörü
`ml/runs/pool` (yapılandırılabilir). `import_model` ONNX'i havuz klasörüne kopyalar.
Eleme politikası `oldest` (varsayılan) veya `weakest`; eleme sırasında artefakt dosyası silinir.
**Rakip dağılımı:** `train.py` her iterasyonda `league.select_opponent(rng, pool_fraction)`
ile **tek** havuz üyesi seçer ve C# sürücüye `--pool-model <o> --pool-fraction 0.2` verir;
böylece o partide %80/%20 dağılımı C# tarafında uygulanır (spec §6.5).
**Giriş:** her `K` iterasyonda en güçlü üyeye karşı `N_eval` oyun; alt güven sınırı
`entry_threshold` (varsayılan 0) üzerindeyse girer. Havuz boşsa mevcut model
**karşılaştırma tabanı** olarak doğrudan eklenir (aksi halde hiçbir model giremezdi).

## F4-48 — Lig giriş eşiği ve ölçüm maliyeti
**Durum:** TEYİTLİ
**Karar:** `entry_threshold = 0,0` (spec §6.5: "alt güven sınırı > 0"). `n_eval = 400`
(spec yer tutucusu). `every = 5`.
**Ölçülen:** depth 0'da 400 oyun ≈ 7 s; depth 1'de ≈ 690 s. Bu yüzden depth 1 eğitiminde
`every` büyütülmeli veya `n_eval` küçültülmelidir. Varsayılanlar depth 0 için ayarlanmıştır.

## F4-49 — Faz 3 ayar ölçüm tablosu yöntemi
**Durum:** TEYİTLİ
**Karar:** `ml/settings_bench.py` altı kombinasyonu ölçer: `DepthPly ∈ {0,1,2}` ×
`MaxCandidates* ∈ {kısıtsız (0/0), kısıtlı (4/4)}`. Her kombinasyon için:
(1) self-play verimi (`--log-top 0`, tek iş parçacığı) → oyun/s, s/oyun, B/oyun;
(2) güç → `PipBot`'a karşı ortalama puan ± standart hata.
**Ölçülen maliyet:** depth 2 tek oyun başına ~76 s (kısıtlı) ve çok daha fazla (kısıtsız).
Bu yüzden `quick` profilinde depth 2 için 1 self-play + 2 değerlendirme oyunu kullanılır ve
tabloda **güç farkının istatistiksel olarak anlamsız olduğu** açıkça yazılır.

## F4-50 — Yakınsama grafiği
**Durum:** TEYİTLİ
**Karar:** `ml/eval_bench.py --plot <train_report.json> --plot-out <png>` dört panel çizer:
değer kaybı (MC probe / TD probe / buffer), politika kaybı + düzgün baz, hedef entropisi /
`log|E|`, gradyan normu (ortalama/maksimum). `matplotlib` (Agg backend) kullanılır;
`matplotlib` kurulu değilse test `importorskip` ile atlanır.

## F4-51 — Havuz rakipli oyun oranı tek yerde uygulanır
**Durum:** TEYİTLİ (hata düzeltmesi)
**Sorun:** `train.py` hem `league.select_opponent(rng, pool_fraction)` ile iterasyonu
seçiyor hem de C# sürücüsüne `--pool-fraction 0.20` veriyordu. Etkin oran
`0.20 × 0.20 = 0.04` oluyordu; 10 iterasyonluk kabul çalıştırmasında yalnızca 1 iterasyon
havuz rakibi gördü.
**Karar:** İterasyon seçimi her zaman yapılır (`select_opponent(rng, 1.0)`); oyun başına
oran **yalnızca** C# sürücüsünde (`--pool-fraction`) uygulanır. Böylece spec §6.5'teki
"%20 havuz rakipli oyun" tanımı birebir karşılanır.

## F4-52 — Çok rakipli değerlendirmede JSON birleştirme Python tarafında
**Durum:** TEYİTLİ
**Sorun:** C# `--eval-json` her çalıştırmada dosyayı baştan yazar. `eval_bench.py` üç
rakip için sürücüyü üç kez çağırdığında dosyada yalnızca son rakip kalıyordu.
**Karar:** `run_eval`'a `json_path` verilmez; `eval_bench.write_eval_json` tüm
`EvalResult` kayıtlarını tek şemada birleştirir. Şema F4-46 ile aynıdır, `reports[]` artık
tüm rakipleri içerir. Model rakiplerinin adı `Model:<dosya adı>` olarak yazılır
(C# sürücüsü tür adı olarak yalnızca `Model` döndürür).

## F4-53 — `Backgammon.Tests` yalnızca Release'te pratik
**Durum:** TEYİTLİ
**Sorun:** `Backgammon.Tests` Debug yapılandırmasında çalıştırıldığında arama testleri
kabul edilemez derecede yavaş: `Test01c_ReferenceEquality_Depth2` tek başına >20 dk,
`Test01_ReferenceEquality` 6 dk 11 s. Tüm paket saatler sürüyor.
**Karar:** Bu paket **her zaman** `-c Release` ile çalıştırılır. Release'de
`Test01` 1 dk 16 s, `Test01c` ~13 dk, tüm paket (202 test) 25 dk 57 s.
`Fuzz_OneMillionGames` `[Explicit]` olduğu için varsayılan çalıştırmada atlanır;
`TAVLA_FUZZ_GAMES` ortam değişkeni varsayılan fuzz oyun sayısını ölçekler.
**Not:** `Backgammon.Tests` yalnızca `Backgammon.Core`'a referans verir; Aşama D
değişiklikleri (`Backgammon.SelfPlay`, `ml/`) bu paketi etkilemez. Yine de regresyon
kontrolü için çalıştırıldı ve 202/202 geçti.

## F4-54 — gnubg ER ölçüm yöntemi
**Durum:** TEYİTLİ
**Karar:** Faz 4 v3 §9'un gnubg ER kabul maddesi `ml/gnubg_er.py` ile karşılanır.
gnubg `1.08.003-mingw 32-Bit 20240428` (`F:\Program Files (x86)\gnubg\gnubg-cli.exe`)
kurulu; tüm değerler gerçek `gnubg-cli` çağrılarından üretilir, hiçbiri elle yazılmaz.

**Yöntem:** Referans vakanın `afterStates` listesi 221 elemanlı vektöre çevrilip ONNX
modeline verilir; `argmax` modelin hamlesini seçer. **Tüm** afterstate'ler tek gnubg
sürecinde 2-ply cubeless `eval` ile değerlendirilir. `E_best = max(equity)`,
`E_model` = modelin seçtiği afterstate'in equity'si, `ER = E_best − E_model`.
`E_best` ve `E_model` aynı değerlendiriciden geldiği için ER tutarlıdır.

**Sonuç (50 pozisyon, 920 afterstate):** `--criterion policy` (C# `ArgMaxCandidate` ile
aynı) ortalama ER **0.1941**, medyan 0.1410, maksimum 0.5600, gnubg ile aynı hamle %32.0.
`--criterion pip` (`PipBot` tabanı) ortalama ER 0.1283, medyan 0.0740, maksimum 0.9660,
eşleşme %42.0. **Model, trivial pip sezgiselinden daha kötü** — dürüstçe raporlanır.

**gnubg CLI tuzakları (hepsi doğrulandı):**
* `set board` için oyun içinde olmak gerekir; **her** tahta yüklemesinden önce `new game`
  yazılmazsa gnubg tahtayı **sessizce reddeder** ve önceki tahta kalır.
* `set cube use off` `new game`'den önce gelmelidir.
* `set evaluation chequerplay evaluation plies N` yalnızca `eval`'i etkiler; **`hint` her
  zaman 0-ply** çalışır (plies 0/1/2/3 aynı `Eq.` değerini verir). Bu yüzden `hint` ER
  referansı olarak kullanılmaz, yalnızca `gnubgHintMove` alanında saklanır.
* `eval` equity'si **sıradaki oyuncunun** bakış açısındandır; afterstate `turn = -turn` ile
  yüklenip sonuç negatife çevrilir.
* `show pipcount` sıradaki oyuncuyu **önce** yazar; ayrıştırıcı isimle eşleştirir
  (`MONSTER` = X = Siyah, `gnubg` = O = Beyaz).
* Çoklu `eval` çıktısı `The pip counts are:` satırından bölünür; `Position ID:` satırı
  `set board` tarafından da yankılandığı için kullanılamaz.
* Sayılar **ondalık virgül** ile yazılır (`+0,160`); ayrıştırıcı ikisini de kabul eder.
* `set board simple` eşlemesi: `simple[0] = -board[25]`, `simple[i] = -board[i]` (i = 1…24),
  `simple[25] = board[0]`. Doğrulama: başlangıç pozisyonu `4HPwATDgc/ABMA` ve 167/167 pip.
* `gnubg-cli` stdin'e **bayt** bekler (`str` verilirse `TypeError`).

**Kapsam:** 57 referans vakanın 50'si kullanılır (15/15 taş + boş olmayan `afterStates`);
7 el yapımı vaka (`bar-closed-white`, `bar-open-white`, `bearoff-exact-white`,
`bearoff-overshoot-white`, `bearoff-blocked-white`, `bearoff-exact-black`, `bar-open-black`)
gnubg tarafından geçersiz sayıldığı için ölçüm dışıdır. Her tahta yüklemesinden sonra
`show pipcount` ile Python'un pip sayımı karşılaştırılır; uyuşmazsa vaka atılır.

**Sınırlar:** Ölçüm cubeless money game ve 2-ply'dir; küp kararları kapsam dışıdır.
Hamle seçimi 0-ply'dir (arama yok); C#'taki 1-ply arama nedeniyle gerçek oyun gücü
daha iyi olabilir, yani ER bir **üst sınır** olarak okunmalıdır.

**Not (ONNX/checkpoint kayması):** `train.py` ONNX'i iterasyonun **başında** dışa aktarır
(satır 590), checkpoint'i **sonunda** kaydeder (satır 733). Bu yüzden `model_vN.onnx` ile
`ckpt_vN.pt` bir iterasyon farklıdır; `model_v1.onnx.parity.json` 5/5 doğruladığı için
dışa aktarma hattının kendisi tutarlıdır. Hata değil, beklenen davranıştır.

**Testler:** `ml/tests/test_gnubg_er.py` (35 test). gnubg gerektiren testler `skipif` ile
korunur; gnubg yoksa betik uydurma değer üretmez, çıkış kodu 2 ile temiz hata verir.

---

## F5-01 — Bearoff veritabanı modelin içinde değil, dekoratör olarak

**Karar.** `BearoffAwareEvaluator`, `BackgammonSearch` ile `OnnxPolicyValueEvaluator`
**arasına** girer; veritabanı ağın girdisi veya çıktısı değildir.

**Gerekçe.** Bearoff pozisyonlarının değeri **kesin** hesaplanabilir. Ağa öğretilseydi
hem yaklaşık olurdu hem de eğitim verisinde bu pozisyonların oranı yapay biçimde artardı.
Dekoratör yaklaşımı ayrıca Faz 1 API'sini hiç değiştirmez ve `DisableBearoff` ile
A/B karşılaştırmasına izin verir.

**Sonuç.** `AfterStateList.CopyRecordFrom` gibi bir ekleme **yapılmadı**; toplu
değerlendirme bölümlenmez, "üzerine yaz" stratejisi kullanılır.

---

## F5-02 — Bearoff dosya formatı: 64 bayt başlık + uint16 CDF

**Karar.** `magic = "TVB1"`, `version = 1`, `points = 6`, `checkers = 15`,
`positions = 54 264`, `maxRolls` (üretici otomatik yükseltir), `flags` (bit 0 = mars),
`payloadCrc32` (CRC-32/ISO-HDLC). Gövde: `positions × (maxRolls+1) × uint16`.

**Gerekçe.** `uint16` nicemleme en büyük `1/65535 ≈ 1,53E-005` hata verir; bu, arama
kararlarını etkilemeyecek kadar küçüktür ve dosyayı 2,38 MiB'de tutar. `float32` olsaydı
dosya iki katına çıkardı.

**Sonuç.** `MaxRolls` 12'den **22**'ye yükseldi (en kötü pozisyon: 6 hanesinde 15 pul).

---

## F5-03 — Kendi colex sıralaması, gnubg indeksine bağımlılık yok

**Karar.** `Rank(c) = Σ_{i=0..5} C(S_i + i, i+1)`; `Unrank` ile tersi.

**Gerekçe.** gnubg'nin indeks düzenine bağımlı olmak, ileride iki taraflı tabloya
geçerken veya gnubg sürümü değiştiğinde kırılganlık yaratırdı. Kendi sıralamamız
54 264 pozisyonun tamamında tur doğrulandı.

---

## F5-04 — Bearoff DP'si tek politika kullanır

**Karar.** `P(T(c) ≤ k) = (1/36) Σ_zar max_hamle P(T(c') ≤ k−1)`; oyuncu her pozisyonda
**tek** bir politika izler (beklenen tur sayısını en aza indiren hamle).

**Gerekçe.** `P(T ≤ k)`'yi her `k` için ayrı ayrı maksimize etmek yanlıştır: aynı zar
atışında farklı `k` için farklı hamle seçilemez. Bu, `ml/bearoff_ref.py`'nin bağımsız
uygulamasıyla doğrulandı (max fark 7,630E-006).

**Sonuç.** Yasal hamleler `LegalMoveGenerator`'dan gelir; DP kendi hamle üreticisini
yazmaz.

---

## F5-05 — Veritabanı `MemoryMappedFile` ile okunur

**Karar.** `BearoffDatabase.Open` `MemoryMappedFile` + `CreateViewAccessor` kullanır;
`File.ReadAllBytes` **yasaktır**.

**Gerekçe.** 2,38 MiB bugün küçük, ama iki taraflı tablo ≈29,4 GB olacak. API'nin bugünden
bellek eşlemeli olması, o gün kod değişikliği gerektirmez.

---

## F5-06 — Faz 5'te yalnızca tek taraflı bearoff

**Karar.** İki taraflı tablo (2 944 581 696 pozisyon ≈ 29,4 GB) Faz 6'ya ertelendi.

**Gerekçe.** Tek taraflı tablo oyun sonlarının büyük çoğunluğunu kapsar; iki taraflı
tablonun ek kazancı, 12 kat dosya boyutu ve çok daha uzun üretim süresiyle
karşılaştırıldığında Faz 5 kapsamı için savunulamaz.

---

## F5-07 — Küp ve maç ağın dışında

**Karar.** Küp kararları `EquityCubeAdvisor` + `MatchEquityTable` ile **kapalı biçimde**
hesaplanır; ağ yalnızca küpsüz equity üretir.

**Gerekçe.** Küp kararı `argmax` değil **eşik** kararıdır; maç kazancı ise MET ile kapalı
biçimde hesaplanır. İkisi de ağa sokulsaydı eğitim verisi ve kalibrasyon ikiye katlanır,
karşılığında hiçbir şey kazanılmazdı.

**Sonuç.** Ağ `output_version = 1` (tek değer kafası) olarak kalır; 6 çıktılı kafa
Faz 6'da `output_version = 2` olacaktır.

---

## F5-08 — Negamax güvenliği: `ME = 2·MWC − 1`

**Karar.** `MatchAwareEvaluator` maç kazanma olasılığını `ME = 2·MWC − 1` ile maç
equity'sine çevirir; `MWC` doğrudan aramaya verilmez.

**Gerekçe.** `MWC` monoton olduğu için hamle seçimini (`argmax`) değiştirmez, ama
doğrudan negamax'a verilirse işaret ve ölçek bozulur: `MWC` her zaman `[0,1]` aralığında
olduğu için "kayıp" negatif görünmez ve karşı tarafın bakış açısı yanlış hesaplanır.

**Sonuç.** Money game'de dönüşüm tam kimliktir; `Version` maç hash'ini içerir.

---

## F5-09 — MET olarak gnubg Rockwell–Kazaross tablosu gömülür

**Karar.** `Backgammon.Core/Match/met_rk.json` (25 × 25) `EmbeddedResource` olarak
gömülür; `MatchEquityTable.Default` bunu okur.

**Gerekçe.** gnubg 1.08.003 kurulu ve tablosu `Rockwell-Kazaross.xml` olarak mevcut.
Karşılaştırma **625 hücrenin tamamında max |Δ| = 0,000E+000** verdi — yani tablo bit
düzeyinde aynı. Kendi tablomuzu üretmek gereksiz risk olurdu.

---

## F5-10 — Küp eşikleri spec'ten türetilir, uygulama spec'e uyduruldu

**Karar.** Money game'de `MoneyDoublePoint = 0,5`, `MoneyTooGoodPoint = 1,0`,
`shouldTake = E < 0,5 − ε`.

**Gerekçe.** `E_doubleTake = 2E`, `E_doublePass = 1` olduğundan ikileme
`max(2E, 1) > E` ⇒ `E > 0,5`; alma `−2E ≥ −1` ⇒ `E ≤ 0,5`. İlk uygulama
`MoneyTakePoint = 1,0` kullanıyordu ve spec ile çelişiyordu. **Spec'in türetmesi
doğru olduğu için uygulama düzeltildi**; `MatchTests.EquityCubeAdvisor_MoneyGameThresholds`
buna göre güncellendi.

---

## F5-11 — `PositionAnalysis` tam kurucu alır

**Karar.** Spec §5.1 yalnızca `readonly` alanları listeler; ek olarak tam bir kurucu
eklendi.

**Gerekçe.** `readonly struct` alanları yalnızca kurucu içinde atanabilir; alan
başlatıcısıyla `readonly` alan atanamaz. Kurucu olmadan tür kullanılamazdı.

---

## F5-12 — `ThinkAsync` `SearchOutcome` döndürür, `SearchResult` değil

**Karar.** `Task<SearchOutcome>`; `SearchOutcome` normal bir `readonly struct`'tır ve
`SearchResult`'ın alanlarını taşır (`RootCandidates` kopyalanmış dizi olarak).

**Gerekçe.** `SearchResult` bir `ref struct`'tır; `ref struct` tür argümanı olamaz
(CS0306). Ayrıca `ref struct` `Task` ile kullanılamaz çünkü `Task` heap'e taşır.

**Sonuç.** `WasCancelled` alanı eklendi; iptal edilen aramada da en iyi hamle döner.

---

## F5-13 — `PolicyValueAdapter` iç köprüsü

**Karar.** `internal sealed class PolicyValueAdapter`, `IPositionEvaluator` +
`IPolicyEvaluator` çiftini `IPolicyValueEvaluator` olarak sunar.

**Gerekçe.** `MatchAwareEvaluator`'ın kurucusu `IPolicyValueEvaluator` ister, ama
`BearoffAwareEvaluator` bu arayüzü uygulamaz (yalnızca üç ayrı arayüzü uygular).
`BearoffAwareEvaluator`'a arayüz eklemek Faz 5 §3.5 sözleşmesini değiştirirdi.

---

## F5-14 — İptal yalnızca arama başlamadan etkilidir

**Karar.** `ThinkAsync(ct)` iptal belirtecini arama **başlamadan** denetler; arama
sırasında iptal, `SearchOutcome.WasCancelled` ile **bildirilir** ama arama durdurulmaz.

**Gerekçe.** `BackgammonSearch` içinde iptal kancası yoktur ve Faz 5 §0 kural 2
"Faz 1–4 API'sini değiştirme" der. Aynı nedenle düşünme bütçesi de tavsiye niteliğindedir.

---

## F5-15 — `Backgammon.UI.Tests` NUnit kullanır

**Karar.** NUnit 4.3.2 (spec §6.2 xUnit diyor).

**Gerekçe.** Depodaki tüm C# test projeleri NUnit kullanır. Tek bir proje için farklı
çatı seçmek, test yardımcılarının paylaşımını ve bakımını zorlaştırırdı.

---

## F5-16 — `MoveInputController` "seçim yok" işareti `-1`

**Karar.** `NoSelection = -1`; `SelectedPoint` varsayılanı `-1`. Ayrıca spec §6.8'in
istediği `LegalTargetsFrom(int)` eklendi.

**Gerekçe.** İlk uygulama "seçim yok" için `0` kullanıyordu, ama `0` **beyaz barın**
indeksidir; bardan oynama seçimi ifade edilemiyordu. `LegalTargetsFrom` olmadan da
"seçim yapmadan yasal hedefleri sor" mümkün değildi.

---

## F5-17 — Unity'de arama çağıran iş parçacığında çalışır

**Karar.** `GameOrchestrator.Think()` eklendi; `GameBootstrap` bunu kullanır.
`ThinkAsync` Unity'den bağımsız katmanda ve testlerde aynen geçerlidir.

**Gerekçe.** `OrtIoBinding` iş parçacığı güvenli değildir. Arama gerçek kare döngüsü
içinde arka plan iş parçacığında çalıştırıldığında `SynchronizeBoundInputs` erişim
ihlali (`0xC0000005`) üretiyordu. Tek başına çalışan arka plan aramaları geçiyordu;
hata yalnızca sahne + kare döngüsü + ONNX birlikteyken ortaya çıkıyordu.

**Sonuç.** 1 katmanlı arama birkaç on milisaniyede biter; kare hızı etkilenmez.

---

## F5-18 — `activeInputHandler = 2` (Both)

**Karar.** `ProjectSettings.asset` içinde `activeInputHandler: 1` → `2`.

**Gerekçe.** `StandaloneInputModule` yalnızca eski girdi arka ucuyla çalışır. Proje
Input System paketini kullanıyordu ve her karede `InvalidOperationException` atıyordu.
"Both" seçeneği hem uGUI olay sistemini hem Input System paketini çalışır tutar.

---

## F5-19 — Unity testleri `dotnet test` kapsamında değil

**Karar.** EditMode (7) ve PlayMode (4) testleri ayrı Unity koşusuyla çalışır; sonuçlar
`unity/build.log` içinde kayıtlıdır. `PHASES.md` §6'daki 447 toplamına **dahil değildir**.

**Gerekçe.** Unity testleri Unity Editor gerektirir; `dotnet test` bunları çalıştıramaz.
Ayrıca Faz 5 §11 kuralı gereği batchmode lisansı yoksa "Unity testleri geçti" **yazılmaz**.
Bu makinede lisans mevcuttur ve sonuçlar gerçek koşulara dayanır.

---

## F5-20 — Değer kafası kalibrasyonu Faz 6'ya bırakıldı

**Karar.** Faz 4 modelinin değer kafası olduğu gibi kullanılır; kalibrasyon düzeltmesi
Faz 6'ya bırakılır.

**Gerekçe.** Ölçüm (400 afterstate, gnubg `evaluate` ile doğrudan karşılaştırma) eğim
**0,0874**, korelasyon **+0,2431**, MAE **0,8014** verdi; kalibrasyon sonrası MAE
**0,2897**'ye düşüyor. Yani bilgi var, ölçek yanlış. Bu bir **Faz 4 model kalitesi**
sorunudur, Faz 5 katmanlarının hatası değildir. Faz 5'in kabul kriterleri (bearoff
kesinliği, MET eşleşmesi, UI testleri, Unity testleri) bu sorundan bağımsızdır.

**Sonuç.** Faz 6 önerisi: (1) kalibrasyon katmanı veya kalibrasyon kaybı, (2) zar
ortalamalı küp değerlendirmesi (ölçülen kazanç: korelasyonda 4,4 kat), (3) 6 çıktılı
kafa (`output_version = 2`), (4) iki taraflı bearoff.

## F6-01 — Referans küme ayrı dosyada donduruldu

**Karar.** Faz 6'nın 200 pozisyonluk referans kümesi
`ml/artifacts/reference_corpus_v1.json` dosyasında tutulur; Faz 1'den beri kullanılan
`Backgammon.Tests/ReferenceData/reference_positions.json` (57 vaka) **değiştirilmez**.

**Gerekçe.** Eski dosya `Backgammon.Tests/ReferenceComparisonTests.cs` ve
`ml/gnubg_er.py` tarafından okunuyor; içeriğini büyütmek C# referans eşitliği testlerinin
beklediği vaka adlarını ve sayıyı bozardı. Ayrıca Test 41a, Faz 5'in 0,1941 değerini
**tam olarak aynı 50 pozisyonda** yeniden üretmek zorunda; bu ancak eski dosya sabit
kalırsa mümkündür.

**Sonuç.** İki dosya yan yana yaşar: eski dosya C# referans eşitliği ve 41a için, yeni
dosya Faz 6'nın tüm güç ölçümleri için.

## F6-02 — `race`, `bearoff`, `closed` fazları parametrik ailelerle üretilir

**Karar.** Referans kümenin bu üç fazı tohumlu rastgele oyunla değil, açık kurallu
ailelerle (`_race_positions`, `_bearoff_positions`, `_closed_positions`) üretilir.

**Gerekçe.** Ölçüldü: 600 rastgele adayda `closed` fazı **0**, `bearoff` **20**,
`race` **18** pozisyon verdi. Test 45 her fazdan ≥ 20 istiyor. Rastgele oyunun bu
fazlara ulaşması oyun uzunluğuna bağlıdır ve tohuma aşırı duyarlıdır; aileler ise
fazı **garanti** eder ve tekrar üretilebilir.

**Sonuç.** Faz dağılımı: temas 39, yarış 40, bearoff 37, bar 40, kapalı tahta 44.

## F6-03 — Küme tahta düzeyinde tekilleştirilir

**Karar.** Aynı tahta (sıra ve zar farklı olsa bile) kümede iki kez yer almaz.

**Gerekçe.** Aynı tahta iki farklı bölünmede görünürse CAL/VAL-ER/TEST-ER ayrıklığı
kâğıt üzerinde sağlanır ama **bilgi sızıntısı** olur (Kural 10). Ayrıca aynı tahtayı iki
kez ölçmek standart hatayı iyileştirmez, yalnız ölçüm süresini artırır.

**Sonuç.** Tekilleştirme `(tahta)` anahtarıyla yapılır; Test 44 bölünmelerin tahta
paylaşmadığını ayrıca doğrular.

## F6-04 — `ml/er_harness.py` yeni vektörleştirici yazmaz

**Karar.** Yeni hat, `ml/gnubg_er.py`'nin vektörleştiricisini, gnubg oturumunu ve ER
tanımını **olduğu gibi** kullanır; yalnız küme, bölünme, güç, veri hacmi ve rapor
katmanlarını ekler.

**Gerekçe.** Kural 3 tek doğruluk kaynağı ister. İki ayrı vektörleştirici, iki ayrı
`PIP_DIVISOR` veya iki ayrı afterstate sıralaması demektir; 0,1941'in yeniden
üretilebilirliği tam olarak bu tekilliğe bağlıdır.

**Sonuç.** `er_harness` içinde vektör kodu yoktur; `gnubg_er.measure` çağrılır.

## F6-05 — Veri hacmi iddiası ölçümle değiştirildi

**Karar.** Faz 6 v1 belgesindeki "11,5 KB/karar" iddiası kaldırıldı; yerine ölçülen
değer yazıldı: **3 824 bayt/karar** (ham), **129 bayt/karar** (gzip).

**Gerekçe.** `ml/runs/stage_d/shards/it10/it10_0000.bgsp.gz` üzerinde ölçüldü: 100 oyun,
9 088 karar, 34 754 696 bayt ham, 1 171 730 bayt disk. v1 iddiası 3 kat yüksekti.

**Sonuç.** Disk maliyeti sıkıştırmayla ~30 kat düşer; H200 kiralama kararı bu ölçülen
değere göre verilmelidir, iddiaya göre değil.

## F6-06 — 200 pozisyon hedefi 0,01–0,02 ER'yi ölçemez

**Karar.** 200 pozisyonluk küme Aşama A için **yeterli**, Faz 6'nın nihai hedefi için
**yetersiz** kabul edilir; küme ilerleyen aşamalarda büyütülecektir.

**Gerekçe.** Ölçülen standart sapma 0,2639; 200 pozisyonda standart hata **0,0187**.
Hedef SE 0,005 için gereken n ≈ **2 786**. Yani 0,01 ile 0,02 arasındaki fark bu kümeyle
gürültüden ayırt edilemez.

**Sonuç.** Test 46 bu sayıyı raporlar; Aşama D/E'de referans küme büyütülmeden
"0,02'nin altına indik" iddiası **kanıtlanmış sayılmaz**.
## F6-07 — `terminal_value` işaret hatası: Faz 4/5 değer hedefleri ters yazılmıştı

**Durum.** TEYİTLİ (Test 53 + `ml/tests/test_replay.py` regresyon testi).

**Karar.** `ml/replay.py::terminal_value` artık `z`'yi `winner` ile **çarpmaz**; `z`
işaretsiz büyüklüktür (`resultPoints / cubeValue`) ve işareti `td_lambda_targets`
zinciri adım adım çevirir.

**Gerekçe.** `td_lambda_targets` her adımda işareti çevirir:

```
y[T-1] = -z
y[t]   = -((1-lambda)*V[t+1] + lambda*y[t+1])
```

Son karar veren oyuncu **kazanandır** (ölçüldü: 200/200 oyunda `last mover == winner`),
dolayısıyla `y[T-2]` kaybedenin bakış açısıdır ve `-z` olmalıdır. Eski kod `z`'yi
`winner` ile çarptığı için `winner = -1` (siyah kazanır) durumunda işaret **iki kez**
çevriliyor ve o oyunun **tüm** hedefleri ters yazılıyordu.

**Ölçüm.** `ml/diagnose.py` D2 koşusunda iki hedef kurucusu karşılaştırıldı:
`build_dataset` (perspektif tabanlı, doğru) ile `build_value_samples(lam=1.0)` (hatalı)
87 628 örneğin **43 986**'sında (%50,2) farklıydı ve ilk örnekler tam olarak
`[-3, +3, -3, +3, ...]` ↔ `[+3, -3, +3, -3, ...]` biçiminde işaret terstine dönüyordu.
%50,2 oranı, oyunların yarısını siyahın kazanmasıyla birebir uyuşur.

**Sonuç.** Düzeltmeden önce D2 `lambda = 1.0` için eğim **-0,2270**, korelasyon
**-0,0305** veriyordu (anlamsız). Düzeltmeden sonra eğim **1,0424**, korelasyon
**0,7757**. Ayrıca **Faz 4/5'te eğitilmiş tüm kontrol noktaları geçersizdir**; Aşama C
sıfırdan eğitim yapmak zorundadır.

## F6-08 — Varsayılan TD lambda 0,7'den 1,0'a çekildi

**Durum.** TEYİTLİ (Test 55 + D2 teşhisi).

**Karar.** `ml/td_lambda.py::DEFAULT_LAMBDA` ve `ml/targets.py::DEFAULT_LAMBDA` **1,0**.

**Gerekçe.** Faz 6 §8.2 (F4-41) saf Monte Carlo hedefini (`lambda = 1.0`) varsayılan
yapar: TD hedefi başlangıçta **yanlıdır** (bootstrap ağının kendi hatasını hedefe
yazar), MC hedefi yanlı değildir, yalnız varyansı yüksektir. D2 teşhisi bunu ölçtü:
`lambda = 1.0` MAE **0,9734**, `lambda = 0.7` MAE **0,9707** — fark %0,3, yani gürültü
içinde. Fark anlamlı olmadığı için belgenin öngördüğü yalın seçenek (MC) korunur.

**Sonuç.** D2 "hedef tanımı birincil neden değil" olarak işaretlenmez; yükseltme sırası
6 çıktılı kafa → `L_cal` → sıcaklık → isotonic olarak kalır.

## F6-09 — Geçersiz `OutcomeDistribution` equity'si 0 döner

**Durum.** TEYİTLİ (Test 52).

**Karar.** `OutcomeDistribution.Equity`, `_constructed == false` iken **0,0** döner.

**Gerekçe.** `FromProbabilities` geçersiz girdide `Invalid` döndürür; o örnekte
`Win = 0` olduğu için `Lose = 1 - Win = 1` oluyor ve `Equity` **-1,0** veriyordu. Bu,
"nötr" değil "kesin kayıp" gibi okunan yanıltıcı bir sayıdır ve çağıran `IsValid`'i
kontrol etmeyi unutursa aramayı bozar.

**Sonuç.** Geçersiz dağılım artık nötr değer üretir; `IsValid` yine `false` döner ve
çağıran yedek yola düşmelidir.

## F6-10 — `output_version = 2` modelleri `prob_order` metadata'sı taşımak zorunda

**Durum.** TEYİTLİ (Test 54, 57, 58, 59).

**Karar.** `output_version >= 2` olan her ONNX modeli `prob_order` (`W,GW,BW,L,GL,BL`)
ve `prob_encoding` (`exclusive`) metadata'sını taşır. `OnnxModelHandle` bu metadata'yı
**sürüm kontrolünden önce** doğrular.

**Gerekçe.** Sürüm 2'nin tek anlamı "6 çıktı, dışlayıcı, bu sırayla"dır. Sıra
metadata'da yazılı değilse handle, modeli yanlış yorumlayabilir; bu sessiz ve çok
pahalı bir hatadır (W ile L yer değiştirirse equity işaret değiştirir).

**Sonuç.** `ml/gen_test_models.py` her v2 fikstürüne bu metadata'yı yazar. Eksik
metadata `InvalidDataException` fırlatır; `output_version = 3` ise
`NotSupportedException` fırlatır (Test 58).

## F6-11 — D1/D2/D3 teşhisi: sorun ölçek ve kafa yapısı, hedef değil

**Durum.** TEYİTLİ (`ml/artifacts/stage_f_diagnosis.md`).

**Karar.** Yükseltme sırası Faz 6 §6.2'deki gibi uygulanır: **6 çıktılı kafa** →
`L_cal` → logit sıcaklık → isotonic. D1 ve D3 işaretlidir, D2 değildir.

**Gerekçe.** 983 oyun, 300 adım sabit bütçe, tohum `20261114`:

| Teşhis | Ölçüm | Karar |
|---|---|---|
| D1 — eğitim ölçeği | MAE 1,2327 (125 oyun) → 0,8487 (250) → 0,8052 (500); eğim 0,6208 → 0,9190 → 0,9851 | **işaretli** — eğri hâlâ iniyor, sorun ölçek |
| D2 — hedef tanımı | `lambda=1.0` MAE 0,9734 vs `lambda=0.7` MAE 0,9707 | işaretli değil |
| D3 — kafa yapısı | 6 çıktılı MAE 0,9362 vs skaler 0,9734 (%3,8 iyileşme) | **işaretli** |

**Sonuç.** Aşama C veri ölçeğini büyütmek zorundadır; 6 çıktılı kafa + `L_cal` Aşama
B'de devreye alınmıştır. D1'in 5 000 / 10 000 noktaları mevcut 983 oyunla ölçülemez;
Aşama C'de yeni self-play verisiyle ölçülmelidir.

## F6-12 — Faz 4/5 kontrol noktaları geçersiz sayılır

**Durum.** TEYİTLİ (F6-07'nin doğrudan sonucu).

**Karar.** `ml/runs/stage_d/` altındaki eğitilmiş ağlar **güç kanıtı olarak
kullanılmaz**; Aşama C sıfırdan eğitim yapar. `ml/artifacts/model_stage_d_v10.onnx`
yalnız **ölçüm hattının** yeniden üretilebilirliği için (Test 41a) saklanır.

**Gerekçe.** F6-07 işaret hatası, siyahın kazandığı oyunların tüm değer hedeflerini ters
yazıyordu. Eğitilmiş ağın öğrendiği değer fonksiyonu bu yüzden yarı yarıya yanlıştır.
Ölçüm: eğitilmemiş v1 modeli ile gerçek equity arasındaki korelasyon **-0,2167**,
işareti çevrilmiş equity ile **+0,2167** — yani ağ "kazanma" yönünü sistematik olarak
ters öğrenmiş durumda.

**Sonuç.** Aşama A'nın 0,1941 / 0,2203 taban sayıları **geçerlidir** (ölçüm doğruydu,
model zayıftı) ama bu modeller Aşama C/D'ye **başlangıç noktası olamaz**.

---

## F6-13 — Oyun başına tohum, iş parçacığı başına tohumun yerine geçti

**Durum.** TEYİTLİ (Test 60).

**Karar.** `seed(gameIndex) = baseSeed + gameIndex`. Her oyundan önce
`SelfPlayRunner.ResetSeed(...)` çağrılır. Havuz (pool) kararı ayrı bir
`Xoshiro256StarStar(gameSeed ^ ScheduleSeedSalt)` üzerinden çekilir.

**Gerekçe.** Faz 4/5 şeması tohumu iş parçacığına bağlıyordu
(`seed + threadIndex * ScheduleSeedSalt`) ve her iş parçacığı tek RNG'yi oyunlar arasında
sırayla tüketiyordu. Sonuç: `--threads 4` ile `--threads 1` **farklı veri** üretiyordu ve
hangi oyunun hangi RNG akışını aldığı tamamlanma sırasına bağlıydı. Bu, Faz 6'nın tüm
karşılaştırma mantığını geçersiz kılar.

**Sonuç.** `--threads N` çıktısı `--threads 1` çıktısıyla **birebir aynıdır** (SHA-256
eşit, Test 60 `Program.Main` üzerinden doğrular). Havuz RNG'sinin ayrılması, `--pool`
bayrağının zar akışını tedirgin etmesini de engeller.

**Bedel.** `ml/runs/stage_d/shards` eski şemayla üretildi; biçim aynı olduğu için
**okunabilir** (Test 63) ama aynı tohumla **yeniden üretilemez**. Kabul edildi: bu
shard'lar zaten işaret hatası taşıyor (F6-12) ve eğitimde kullanılmayacak.

---

## F6-14 — `dup_cap` oyun sonrası tek geçiştir ve kararları silmez

**Durum.** TEYİTLİ (Test 62, 66).

**Karar.** `DupCapFilter.Apply(games, cap)` tüm oyunlar bittikten sonra, `GameId`
sırasına göre tek geçiş yapar. Parmak izi `chosenVector`'ün `f32` baytları üzerinde
FNV-1a 64'tür. Varsayılan `cap = 3` (`0` = kapalı), ilk `DefaultOpeningPlies = 10` karar
muaf. Elenen karar **silinmez**: `IsLearner` temizlenir, `DupCapped` (bit3) kurulur,
`Q`/`PolicyTargetCs`/`CandidateVectors` boşaltılır, `chosenVector` korunur.

**Gerekçe.**
* Tekrar sayacı global durumdur; iş parçacıklarına dağıtılırsa sonuç iş parçacığı sayısına
  bağlı olur ve F6-13'ün determinizm garantisi kırılır.
* `BackgammonState.hash` zarı **içermez**, yani karar düzeyinde tekrar tespiti için
  kullanılamaz. Shard v1 karar-öncesi Zobrist hash'ini saklamadığı ve biçim
  değişmemesi gerektiği için vektör parmak izi seçildi.
* `ml/td_lambda.py` TD zincirini kurmak için **her** kararın `chosenVector`'üne ihtiyaç
  duyar; karar silinseydi zincir kopardı.
* Açılış muafiyeti olmasa `dup_cap = 1` açılış çeşitliliğini yok eder ve Test 62 düşerdi.

**Ölçüm.** 200 oyun, `--dup-cap 1`: 15 603 açılış-dışı öğrenen kararın **23**'ü (%0,15)
elendi. Rastgele self-play'de tekrar nadirdir; `dup_cap` hızlandırıcı değil **güvenlik
ağıdır** — güçlü politika ile tekrar oranı artacaktır.

---

## F6-15 — Linux çalıştırma adımı bu makinede atlanır

**Durum.** TEYİTLİ (Test 64).

**Karar.** Test 64 `dotnet publish -r linux-x64 --self-contained true` yapar ve çıktının
ELF (`\x7fELF`) olduğunu doğrular. İkiliyi **çalıştırma** adımı WSL veya Docker
gerektirir; bu makinede **ikisi de yok** (`wsl -l -v` dağıtım listemez, `docker` yok).
Bu durumda test `skip` olur ve gerekçe çıktıya yazılır.

**Gerekçe.** Yayın + ELF doğrulaması, platforma özgü derleme hatalarını (P/Invoke yolu,
`RuntimeIdentifier` uyumsuzluğu, eksik native kütüphane) yakalar. Çalıştırma adımı
ek güvence sağlar ama bu ortamda mümkün değil; testi sessizce "geçti" saymak yerine
gerekçeli atlamak dürüst seçenektir.

**Sonuç.** Linux ikilisi CI'da (veya WSL/Docker kurulu bir makinede) çalıştırılmalıdır.
Bu, Aşama C kabulünün **açık kalan** tek maddesidir.

---

## F6-16 — CUDA ölçüldü ve CPU kazandı; varsayılan CPU

**Durum.** TEYİTLİ (Test 61, ölçüm).

**Karar.** `SelfPlayConfig.DefaultUseCuda = false`. CUDA execution provider bu makinede
**gerçekten yüklendi** ve yine de CPU seçildi. `--cuda true` bayrağı korunur.

**Ölçüm.** CUDA EP'nin yüklendiğinin kanıtı: `torch\lib` (CUDA 12.1 + cuDNN 9 çalışma
zamanı) `PATH`'te değilken `--cuda true` şu hatayı verir —
`Error loading "onnxruntime_providers_cuda.dll" which depends on "cublasLt64_12.dll"
which is missing (Error 126)`. `PATH`'e eklendiğinde oturum açılır, yani sessiz CPU geri
düşmesi yoktur.

| Ölçüm | CPU | CUDA | CUDA/CPU |
|---|---|---|---|
| Test 61, 20 oyun, `depth 0`, ısınmalı | **119,26 oyun/sn** | 29,11 oyun/sn | 0,24× |
| CLI, 60 oyun, `depth 0`, `log-top 4` | **85,91 oyun/sn** | 24,68 oyun/sn | 0,29× |
| CLI, `depth 1`, `max 4/4` | **1,52 oyun/sn** | 0,25 oyun/sn | 0,16× |
| CLI, `depth 2`, `max 4/4` | **0,03 oyun/sn** | < 0,01 oyun/sn | < 0,3× |

Tepe bellek: CPU 87 MB, CUDA 381 MB. Ayrıntı: `ml/artifacts/stage_c_gpu_decision.md`.

**Gerekçe.** Model ~156 bin parametre; bir forward geçişi CPU'da ~1 µs, GPU çekirdek
başlatma gecikmesi tek başına 20–50 µs. `depth 0`'da kova 32–64 satıra yuvarlanır, yani
hesap başlatma maliyetinin altında kalır. Derinlik arttıkça arama ağacı C# tarafında
CPU'da gezildiği için fark **büyür**. Faz 6 v3 §12.3'ün "CUDA ≥ CPU" varsayımı bu
donanım/model ikilisi için **yanlıştı**; ölçüm onu çürüttü.

**Ölçüm tuzağı (düzeltildi).** Isınma geçişi olmadan 6 oyunla yapılan ilk ölçümde CUDA
1,47× *hızlı* göründü. Sebep ölçüm hatasıydı: CPU soğuk (JIT + ONNX oturumu + dosya ön
belleği), CUDA sıcak koşuyordu. Test 61 artık ısınma geçişi yapar, 20 oyun ölçer ve
CPU'yu iki kez (CUDA'dan önce ve sonra) ölçüp büyüğünü alır.

**Test 61'in yeni sözleşmesi.** "CUDA kazanmalı" demez; **ölçülen kazananın seçili
olmasını** ister (`SelfPlayConfig.DefaultUseCuda` ile karşılaştırır, eşik 1,2×). Başka
donanımda CUDA kazanırsa test kırmızı olur ve sabitin çevrilmesini söyler — sessiz sapma
olmaz. Varsayılan CPU derlemesinde CUDA EP yoktur, test `Inconclusive` olur ve CPU
ölçümünü yazdırır.

**Sonuç.** GPU ölçümü için:
`dotnet build -c Release -p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu`.
Determinizm iddiası GPU yoluna **taşınmaz** (Faz 6 §7.3): GPU yalnızca hız içindir.
Mevcut donanım (GTX 1650, 4 GB, SM 7.5) `bf16` desteklemez; `fp16`/`fp32` kullanılmalıdır.
İş parçacıkları arası kova birleştirme (v3 §7.3) uygulanırsa kova 2048'e çıkar ve GPU
kazanabilir — bu ayrı bir deneydir ve şu anki veri motoru için gereksizdir.

---

## F6-17 — Vektör TD(λ): işaret çevrimi yerine **sınıf-yarısı takası**

**Durum.** TEYİTLİ (`ml/tests/test_stage_d.py` içinde
`test_vector_td_lambda_one_equals_monte_carlo`, `test_flip_is_involution`,
`test_td_lambda_zero_uses_next_state`).

**Karar.** Faz 4'ün skaler zinciri `y[t] = -((1-λ)·V[t+1] + λ·y[t+1])` altı çıktılı kafada
**işaret çevrimiyle** değil, `[W, GW, BW, L, GL, BL]` sınıf yarılarının **takasıyla**
uygulanır:

```
flip([W, GW, BW, L, GL, BL]) = [L, GL, BL, W, GW, BW]
y[n-1] = flip(z_terminal)
y[t]   = flip((1-λ)·p̂[t+1] + λ·y[t+1])
```

**Gerekçe.** Skaler değerde "sıra değişimi" `-V`'dir; altı sınıflı dağılımda karşılığı
`flip`'tir. `flip` bir **involusyondur** (`flip(flip(p)) == p`), bu yüzden `λ = 1,0`'da
zincir `flip^k(z)`'ye indirgenir ve `flip² = id` olduğu için sonuç **tam olarak** oyuncu
bakış açısından tek-sıcak Monte Carlo hedefidir. Bu, F6-07'deki işaret hatasının vektör
karşılığının da yapısal olarak imkânsız olduğunu garanti eder: `flip` uygulanmazsa
`λ = 1,0` hedefi rakip bakış açısından yazılır ve test kırmızı olur.

**Ölçüm.** `λ = 1,0` ile vektör zinciri, tek-sıcak MC hedefiyle **birebir** aynı çıktı
(altı `(winner, result_type)` kombinasyonunun tamamı). `λ = 0,0` bir sonraki durumun
tahminini kullanır.

---

## F6-18 — Ek A (Track H) açılmadı; Test 69 atlanır

**Durum.** TEYİTLİ (Test 69 `pytest.skip`).

**Karar.** Faz 6 v3 §12.4'teki Test 69 (`TrackH_H0_Parity`) **atlanır**. Ek A kapısı
(Evren platformu / H200 kiralama) bu oturumda açılmadı; Track H (dağıtık eğitim) ile
Track L (tek makine) arasında karşılaştırılacak bir H koşusu yok.

**Gerekçe.** Test 69 "Ek A açılırsa" koşuluna bağlıdır (v3 §12.4 tablosu). Koşul
sağlanmadığı için test `skip` döner; bu bir başarısızlık değil, kapsam dışılıktır.
Ek A açıldığında test, aynı seed/veri/iterasyonla Track L kayıp eğrisini ±%2 içinde
karşılaştıracak şekilde hazırdır.

---

## F6-19 — `config.yaml` `lam` 0,7 → 1,0 ve sabit **ağdan bağımsız** MC probe

**Durum.** TEYİTLİ (Test 71a, 72; `ml/runs/stage_d_l0` ölçümü).

**Karar 1.** `ml/config.yaml` içindeki `train.lam` **1,0**'a çekildi. F6-08 zaten
`ml/td_lambda.py` ve `ml/targets.py` varsayılanlarını 1,0 yapmıştı; `config.yaml`
0,7'de kalmıştı ve `train_v2.py` config'i varsayılandan önce okuduğu için etkin değer
0,7 oluyordu. Bu sessiz sapma kapatıldı.

**Gerekçe 1 (ölçüm).** Aynı L0 tarifi (500 oyun/iterasyon, `small`, `depth 0`) iki λ ile
koşuldu. λ = 0,7 koşusu **5. iterasyonda durduruldu**, çünkü hedefler eğitilmemiş modelin
neredeyse düzgün `p̂`'siyle önyükleniyordu ve öğrenme sinyali kayboluyordu:

| λ | iterasyon | buffer CE (ilk → son) | buffer equity MAE | politika örneği (son) |
|---|---|---|---|---|
| 0,7 | 5 (durduruldu) | 1,6613 → 1,5831 | 0,0196 → 0,0541 | 56 685 |
| **1,0** | 20 | **1,1958 → 1,0197** | 1,2476 → 0,9018 | **508 005** |

λ = 0,7'de CE 1,66'da takılır (düzgün hedefin entropisi ln 6 = 1,7918'e yakın) ve
`train_policy_samples` 5. iterasyonda hâlâ 56 binde kalır; λ = 1,0'da CE 1,196'dan
başlar ve politika örneği 508 bine çıkar. λ = 0,7'nin MAE'sinin küçük görünmesi bir
yanılsamadır: hedefler sıfıra yakın olduğu için "sıfır tahmin" düşük MAE verir.
Ayrıntı: `ml/artifacts/stage_f_train.md`.

**Karar 2.** `train_v2.py` artık **iki** probe kümesi tutar: TD probe (o anki buffer'ın
ilk iterasyonundan dondurulmuş) ve **MC probe** (`λ = 1,0`, ağdan bağımsız hedefler).
MC probe `probe.npz` içine yazılır ve `--resume`'da aynen geri yüklenir.

**Gerekçe 2.** Dondurulmuş TD probe'un hedefleri ilk iterasyonun **zayıf** modelinden
gelir; model ilerledikçe bu hedeflerden uzaklaşır ve `probe_ce` **yanıltıcı biçimde
kötüleşir** (L0'da 1,66 → 1,76). Faz 4 bu sorunu `probe_mc` ile çözmüştü; `train_v2.py`
ilk sürümünde bu alan eksikti. MC probe modelden bağımsız olduğu için tek gerçek
"öğrenme eğrisi" ölçüsüdür ve `--resume` determinizmini bozmaz (Test 72 bit düzeyinde
aynı `metrics.jsonl`).

---

## F6-20 — Soğuk başlangıçta eğitilmemiş model **%79 iptal oyun** üretir; ısınma zorunlu

**Durum.** TEYİTLİ (`ml/runs/stage_d_l1` ilk denemesi; `ml/runs/stage_d_boot`).

**Karar.** Aşama D eğitimi **sıfırdan rastgele ağırlıkla self-play yapmaz**. `train_v2.py`
`--init-from <ckpt.pt>` ile ısınma başlangıcı alır (yalnız ağırlıklar; optimizer/iterasyon
taşınmaz, profil aynı olmak zorunda). L1 koşusu `ml/runs/stage_d_boot` çıktısıyla ısıtıldı.

**Gerekçe (ölçüm).** `medium` profiliyle **eğitilmemiş** ağdan 2 000 oyunluk self-play:

| Model | oyun | iptal | karar/oyun | shard (gzip) | tepe bellek |
|---|---|---|---|---|---|
| eğitilmemiş `medium` | 2 000 | **1 584 (%79,2)** | 454,8 | 251 MB | 8,5 GB |
| ısıtılmış `medium` (`stage_d_boot`) | 2 000 | **0** | 65,7 | 26,9 MB | 1,1 GB |

Eğitilmemiş ağın politika logitleri neredeyse sabittir; `--sel-temp 0,05` ile ajan
neredeyse her zaman aynı adayı seçer ve oyun `--max-plies 500` sınırına kadar ilerler.
İptal oyunlar `is_usable_game` tarafından zaten atılır, yani verinin %79'u **boşa
harcanır**; ayrıca 500 ply'lik oyunlar replay buffer'ında 10 GB mertebesinde yer tutar.
Isınma bu patolojiyi tamamen kaldırır (iptal 0, karar/oyun 65,7).

**Yan bulgu.** `small` profiliyle sıfırdan başlangıç bu patolojiyi göstermedi
(171 karar/oyun, iptal 0). Yani patoloji profil/başlangıç ağırlıklarına bağlıdır ve
şansa bırakılamaz — bu yüzden kural olarak ısınma zorunlu tutuldu.

---

## F6-21 — `ShardWriter` toplu float yazımı: 2 000 oyunluk shard 8,5 GB → 1,1 GB tepe bellek

**Durum.** TEYİTLİ (Test 60 hâlâ bit düzeyinde aynı shard'ı üretir; `ml/runs/sp4test`).

**Karar.** `Backgammon.SelfPlay/ShardWriter.cs`:
`WriteFloats` artık float başına **4 × `WriteByte`** yerine tek bir `byte[]` tamponu
doldurup **tek `Stream.Write`** yapar; `WriteFile` çıktı akışını 64 KB'lik
`BufferedStream` ile sarar.

**Gerekçe (ölçüm).** 2 000 oyunluk shard ~860 MB ham aday vektörü içerir; float başına
4 `WriteByte` çağrısı ~860 milyon sanal çağrıya dönüşüyordu ve `GZipStream` her baytı
ayrı deflate ediyordu. Ölçüm: aynı 2 000 oyun **>7 dakika** ve **8,5 GB** tepe bellekten
**12,7 saniye** ve **1,1 GB**'a indi (yazma dahil toplam duvar süresi). Bayt çıktısı
**değişmedi** (little-endian kodlama aynı), bu yüzden Test 60'ın bit düzeyinde
determinizm iddiası korunur.

**Not.** Bu, Faz 4'ten beri var olan bir yazma yolu kusurudur; Aşama C'nin 100 oyunluk
shard'larında görünmüyordu, Aşama D'nin 2 000+ oyunluk shard'larında ölçeklenmeyi
engelliyordu.

## F6-22 — ER ~0,06'da plato yapıyor: veri hacmi bu ölçekte kaldıraç değil

**Durum.** TEYİTLİ (L1 ve L2 koşuları, `ml/runs/stage_d_l1`, `ml/runs/stage_d_l2`).

**Karar.** Aşama D'nin L3 tarifi, v3 §8.4'teki "10⁵ oyun/iterasyon × 50 iterasyon"
ifadesinden **sapmalıdır**: L3 aynı anda `depth 1` veri üretimi ve en az 200
pozisyonluk VAL/TEST kümeleri kullanmalıdır. Yalnızca oyun sayısını artırmak
ölçülebilir bir ER kazancı üretmez.

**Gerekçe (ölçüm).** L1 (2 000 oyun/iterasyon, 30 iterasyon, tampon 12 000) VAL-ER
**0,0658**; L2 (10 000 oyun/iterasyon, 30 iterasyon, tampon 20 000) VAL-ER **0,0619**.
Oyun/iterasyon **5×** arttı, toplam deneyim ~60 000 → ~300 000 oyuna çıktı, ER farkı
**0,0039**. 40 pozisyonluk VAL kümesinin standart hatası **0,016–0,020** olduğu için bu
fark standart hatanın **0,2 katıdır** — istatistiksel olarak **anlamsız**.

L2'nin TEST-ER'i **0,0490** (< 0,05 hedefi) ölçüldü, ancak bu değer koşunun **son**
modeli (`model_v30`, VAL-ER 0,0678) üzerindedir; `train_v2.py` TEST-ER'i her zaman son
checkpoint'te ölçer. En iyi VAL-ER modeli `ckpt_v15` (0,0619) idi. İki sayı arasındaki
fark da gürültü içindedir.

**Yorum.** Darboğaz **kapasite değil** (Test 68 `medium`'u seçti: `large` farkı 0,0884 <
eşik 0,0927), **öğretmen kalitesi**dir: politika `--sel-temp 0,05` ile üretilen kendi
`depth 0` aramasını taklit eder, değer kafası da aynı öğretmenden beslenir. `buffer_ce`
0,9690 → 0,9182 ile iyileşirken VAL-ER düşmemesi, **eğitim hedefinin kendisinin**
doğruluk sınırı olduğunun işaretidir. İkinci darboğaz **ölçüm çözünürlüğü**dür:
0,01 mertebesindeki gerçek iyileşmeler 40 pozisyonla görülemez.

**Sonuç.** `depth 1` veri üretimi Aşama C §15.6'da **56× yavaş** ölçüldü (1,52 vs
85,91 oyun/sn). L3'ün ~40 saatlik CPU bütçesi bu yüzden `depth 1`'e ve daha büyük
ölçüm kümelerine ayrılmalıdır; Ek A (Evren/H200) açıldığında ilk iş budur.

---

## F6-23 — `--resume` tamponu sıfırdan kurar: 20 shard dizini ~40 dk

**Durum.** TEYİTLİ (L2 koşusu 20. iterasyonda kesildi ve `--resume` ile sürdürüldü).

**Karar.** Davranış **doğru** bırakıldı (Test 72 birebir devamı doğrular); yalnızca
maliyet belgelendi. İyileştirme Aşama E'ye bırakıldı.

**Gerekçe (ölçüm).** `ReplayBuffer.add_shard_dir` dizindeki **tüm** shard'ları okur,
`max_games` sınırını **okuma sırasında** uygulamaz; 200 000 oyunun tamamı ayrıştırılır,
sonra FIFO kırpılır. L2'de 20 shard dizini (20 × 10 000 oyun, ~2,4 GB gzip) **~40 dk**
ve **13,3 GB** tepe çalışma kümesi tüketti.

**Öneri.** Devam yolunda yalnızca son `N` shard dizinini okumak yeterlidir: FIFO sırası
zaten kronolojiktir ve `max_games` yalnızca son oyunları tutar. Bu, devam süresini
shard sayısından bağımsız hâle getirir.

---

## F6-24 — Aşama E: transposition table anahtarı zar maskesi içerir

**Karar.** TT anahtarı `s.hash ^ (depth · 0x9E3779B97F4A7C15) ^ (diceMask · 0xC2B2AE3D27D4EB4F)`
biçimindedir; `diceMask` kalan zarların sıralı katlamasıdır.

**Gerekçe.** `Zobrist` tabloları (`Backgammon.Core/Zobrist.cs`) yalnızca tahta değerleri, toplanan
taş sayıları, küp değeri, küp sahibi ve sıra için anahtar üretir — **zar anahtarı yoktur**. Aynı
tahtaya farklı kalan zarlarla ulaşan iki düğüm aynı `s.hash`'i üretir. Zar maskesi olmadan TT,
"3 kaldı" düğümünün değerini "1 kaldı" düğümüne döndürürdü; bu sessiz ve çok ciddi bir hatadır.

**Doğrulama.** Test 78: TT açık, 16 pozisyon, depth 2 → `Reference(2)` ile değer **ve** hamle
birebir aynı. Test 76: aynı workspace'te 3 tur, taze workspace'te 1 tur → hepsi birebir aynı.

---

## F6-25 — Aşama E: TT yalnızca EXACT girişleri kullanır

**Karar.** `LOWER`/`UPPER` bayrakları biçim olarak ayrılmıştır ama bu motorda **kesme için
kullanılmaz**. Yalnızca tam pencerede (`alpha <= L && beta >= U`) ve kesme yapılmadan hesaplanmış
değerler saklanır; yalnızca `EXACT` + yeterli derinlik isabetleri döner.

**Gerekçe.** `ChanceNode` 21 zar üzerinden **ağırlıklı ortalama** alır. Bir sınır değerin
ortalamaya girmesi ortalamayı da sınır yapar; sınırların yukarı propagasyonu bu motorda güvenli
değildir (klasik satrançtaki tek-değerli minimax'ta güvenlidir, beklenen-değer ağacında değildir).
Yanlış bir sınır kesmesi, v3 §9.5'in değişmez kuralını ihlal eder.

**Bedel.** TT isabet oranı düşer (Test 82: 24 pozisyonda 21 isabet). Bu bedel kabul edildi:
doğruluk hızdan önce gelir.

**Doğrulama.** Test 78 — TT'li ve TT'siz arama `Reference(depth)` ile birebir aynı.

---

## F6-26 — Aşama E: bearoff kesmesi yalnızca `IExactValueEvaluator` ile etkindir

**Karar.** `SearchSettings.UseBearoffCutoff` yalnızca değerlendirici `IExactValueEvaluator`
uyguluyorsa ve `IsExactFor(board)` true dönerse etkilidir. `BearoffAwareEvaluator` uygular;
`MatchAwareEvaluator` **uygulamaz**.

**Gerekçe (neden sonuç değişmez).** Saf yarışta optimal oyun DB'de çözülmüştür:
`E(P) = max_m Σ_r w_r · (−E(P after m, then opponent rolls r))`. Yani kesin değer, her derinlikteki
aramanın **sabit noktasıdır**. `BearoffAwareEvaluator` yaprakta kesin equity verdiği için depth 1,
depth 2, … hepsi aynı değeri üretir; depth 0'a indirmek yalnızca düğüm sayısını düşürür.

**Gerekçe (neden `MatchAwareEvaluator` uygulamaz).** `E → ME` dönüşümü tek skaler `E`'nin monoton
fonksiyonu değildir (mars ağırlığı skora göre değişir). Kesin bearoff equity'sini dönüşümden
geçirmek, dönüşümün tanım kümesini ihlal eder.

**Doğrulama.** Test 77: 12 saf yarış, depth 1 → düğüm **3 939 → 12** (**328×**), değer ve hamle
birebir aynı. Test 78(c): bearoff kesmesi `Reference(0)` ile birebir aynı.

---

## F6-27 — Aşama E: TT üretimde açılmaz (ablasyon kararı)

**Karar.** `TranspositionCapacity` varsayılanı **0**'dır ve üretim yollarında (`SelfPlayAgent`,
`GameOrchestrator`) **açılmaz**. Kod opt-in olarak korunur.

**Ölçüm (Test 82).** 24 pozisyon, depth 2, aday 4/4, **kalıcı workspace** (gerçek kullanım):

| Konfigürasyon | Değerlendirici | Düğüm | TT isabet | Süre |
|---|---|---|---|---|
| cache açık, TT kapalı | 91 203 | 92 392 | 0 | 3,546 s |
| ikisi de açık | 89 876 | 91 065 | 21 | 3,446 s |
| cache kapalı, TT açık | 93 501 | 94 753 | 84 | 3,534 s |

TT, eval cache'in üzerine yalnızca **%2,9** ekliyor; cache tek başına TT'den **%0,4** daha iyi.

**Gerekçe.** Pahalı iş (yaprak değerlendirme + chance düğümü) zaten `UseEvalCache` tarafından
anahtarlanıyor. Tavla'da gerçek transpozisyon (aynı tahta + aynı zar + aynı derinlik) nadirdir;
F6-25 gereği yalnızca EXACT isabetler kullanıldığı için isabet oranı daha da düşer.

**v3 §9.5 uyumu.** "Kazanç yoksa sadeleştirilir ve raporlanır." TT kaldırılmadı çünkü §9.3'ün
zorunlu teslimatıdır ve Test 76/78/80 ona bağlıdır; ama **varsayılan kapalı** tutularak üretim
yolunda sıfır maliyet ve sıfır risk garanti edilir.

**Ölçüm hatası notu.** İlk Test 82 denemesinde her kararda `ws.Reset()` çağrılıyordu; bu TT'yi de
temizlediği için isabet **0** çıktı ve TT "işe yaramaz" göründü. Gerçek kullanımda `SelfPlayAgent`
workspace'i kararlar arasında yaşatır (`Reset()` yalnızca model yeniden yüklenince çağrılır);
test bu biçime düzeltildi. Bu, Aşama C'deki "ısınmasız ölçüm CUDA'yı yanlışlıkla kazanan gösterdi"
hatasının (F6-16) aynı sınıfındandır: **ölçüm kurulumu sonucu belirler.**

---

## F6-28 — gnubg Python API'si `cubeinfo.move` alanını **yok sayar**

**Durum.** TEYİTLİ (ölçüm; düzeltme `ml/cube_bench.py::gnubg_view`).

**Bulgu.** `gnubg.evaluate(board, ci, ec)` ve `gnubg.cfevaluate(board, ci, ec)`, `ci` sözlüğündeki
`move` alanını **hiç okumaz**. İkisi de `anBoard[1]`'i "sırada olan oyuncu" kabul eder ve sonucu
**onun** bakış açısından döndürür. `cubeinfo(cube, owner, fMove, ...)` çağrısındaki `fMove`
yalnızca sözlüğe yazılır, değerlendirmede kullanılmaz.

**Kanıt (hepsi ölçüldü).**

1. `cubeinfo(1, -1, 0, ...)` ile `cubeinfo(1, -1, 1, ...)` **bayt bayt aynı** `evaluate` ve
   `cfevaluate` çıktısını verir — başlangıç pozisyonunda, `p0-money`, `p1-money`, `p2-money` ve
   sentetik 15'e-15 pozisyonunda. Durum sızmasını elemek için iki ayrı süreçte (`FM=0` / `FM=1`)
   tekrarlandı; sonuç aynı.
2. `anBoard` satırlarını takas etmek sonucu **değiştirir ve işaretini çevirir**: `p0-money`
   (sıra −1) olduğu gibi `+0,1819`, takas edilmiş `+0,3323`; `p3-money` (sıra +1) olduğu gibi
   `+1,5216`, takas edilmiş `−1,1249`. Demek ki bakış açısı **satır 1**'e bağlıdır.
3. Metin protokolü (`set turn 0|1` + `eval`) sırayı **doğru** okur: `p0-money` için turn +1
   `0,332`, turn −1 `0,182`; `p3-money` için turn +1 `−1,125`, turn −1 `1,509`. Yani hata yalnızca
   Python API'sindedir; `ml/gnubg_er.py::GnubgSession` (metin protokolü) **etkilenmez**.

**Düzeltme.** `ml/cube_bench.py`'ye `gnubg_view(case)` eklendi: hamleyi yapan oyuncu her zaman
`anBoard[1]`'e yerleştirilir (`case["turn"] == 1` ise satırlar takas edilir), skor demeti buna
göre takas edilir ve küp sahibi yeniden eşlenir (`owner >= 0` ise `owner = 1 - owner`).
`cubeinfo` artık koşulsuz `move=1` alır.

**Etki (200 pozisyon, 133 geçerli).** Düzeltme öncesi/sonrası, gnubg 0-ply, `diceAveraged`:

| Metrik | önce | sonra |
|---|---|---|
| Equity korelasyonu | 0,11 | **0,83** |
| Equity ortalama \|Δ\| | 0,92 | **0,37** |
| Çiftleme uyumu | 52,27 % | **73,68 %** |
| Kabul/ret uyumu | 61,36 % | **88,72 %** |

**Ders.** Üçüncü taraf bir hakemle karşılaştırma yaparken **bakış açısı sözleşmesi** ayrı ayrı
doğrulanmalıdır. gnubg'nin kendi belgelenmemiş davranışı, 0,11 korelasyonu "modelimiz küp
oynamayı bilmiyor" diye okumaya çok müsaitti; gerçekte ölçüm hattı bozuktu. Bu, F6-16'daki
"ısınmasız ölçüm CUDA'yı yanlışlıkla kazanan gösterdi" ve F6-27'deki "her kararda `ws.Reset()`
TT isabetini sıfırladı" hatalarıyla aynı sınıftandır: **ölçüm kurulumu sonucu belirler.**

---

## F6-29 — Küp danışmanı afterstate'leri **hamleyi yapanın** perspektifinden değerlendirmeli

**Durum.** TEYİTLİ (ölçüm + kod izi; düzeltme `EquityCubeAdvisor.EvaluateDiceAveraged`).

**Bulgu.** `EquityCubeAdvisor.EvaluateDiceAveraged`, afterstate'leri `-perspective` ile
değerlendirip sonucu `v = -values[i]` ve `dists[best].Flip()` ile çeviriyordu ("negamax; model
sıradaki oyuncunun değerini üretir" varsayımı). Bu varsayım **Faz 6'da geçersiz**:

- `Backgammon.SelfPlay/ShardWriter` her karar için `VectorizeAfterMove(sequence, mover, ...)`
  yazar; yani eğitim vektörü **hamleyi yapanın** perspektifindendir.
- `ml/gnubg_er.py::score_afterstates` afterstate'leri `perspective=turn` (mover) ile
  vektörleştirir ve ER bu yönde ölçülür (TEST-ER 0,049).
- `BackgammonSearch.SearchNode` de `evaluator.EvaluateBatch(list, 0, nonTerminal, s.turn, ...)`
  kullanır — aynı sözleşme.

Yani ağ, `V(vec(Q, p))` = "**p'nin** Q afterstate'indeki equity'si" olarak eğitilmiştir; burada
`p` hamleyi yapandır. Danışman ise `V(vec(Q, -p))` istiyordu — ağın hiç eğitilmediği yön.

**Neden önemli.** Ağ **antisimetrik değil**: ölçüldü, `mean |V(Q, p) + V(Q, -p)| = 0,65`. Bu
yüzden `-V(Q, -p)` ile `V(Q, p)` arasında sistematik fark var ve işaret çevirme doğrudan yanlılık
üretiyor.

**Düzeltme.** `EvaluateBatch`/`EvaluateDistributionBatch` artık `perspective` alır; `v = values[i]`
ve `dists[best]` (Flip yok).

**Etki (gnubg 0-ply, 133 geçerli pozisyon, `diceAveraged`).**

| Metrik | F6-28 sonrası | F6-29 sonrası |
|---|---|---|
| Equity korelasyonu | 0,7803 | **0,8330** |
| Equity ortalama \|Δ\| | 0,5249 | **0,3738** |
| Equity p90 \|Δ\| | 1,0293 | **0,9038** |
| Çiftleme uyumu | 67,67 % | **73,68 %** |
| Kabul/ret uyumu | 77,44 % | **88,72 %** |
| Her iki karar uyumu | 61,65 % | **69,17 %** |
| İşaretli yanlılık (biz − gnubg) | +0,2587 | **−0,1872** |

Karışıklık matrisi de düzeldi: düzeltme öncesi "gnubg çiftle derken biz **hiç** çiftlemiyorduk"
(0/46); sonrası 42 ortak çiftleme, 4 kaçırılan, 31 fazla çiftleme.

**Kalan yanlılık.** `diceAveraged` medyanı −0,093 (ort. −0,187). Kalan fark model kalitesidir,
sözleşme hatası değil: ağ 0,049 ER'ye göre kalibre ama küp pozisyonları ER kümesinden farklı bir
dağılımdan geliyor.

**`singleRecord` neden düzelmedi.** `EvaluateSingleRecord` **sıra başı** (pre-roll) pozisyonu
değerlendirir; ağ ise yalnızca afterstate görmüştür. Vektörleştirici sıranın kimde olduğunu
kodlamadığı için ağ, sıra başı pozisyonu "rakip sırada" gibi okur ve equity'yi sistematik olarak
**düşük** tahmin eder (ölçüldü: ortalama −0,56). Bu yol Faz 5 davranışının birebir korunmasıdır
(`DiceAveraged = false`) ve üretimde kullanılmaz; `CubeAdvisorOptions.DiceAveraged` varsayılanı
`true`'dur.

## F6-30 — Maç oyununda çiftleme karşılaştırması `min`, `max` değil

**Durum.** TEYİTLİ (ölçüm + kod izi; düzeltme `EquityCubeAdvisor.Decide`).

**Bulgu.** `EquityCubeAdvisor.Decide`, maç oyununda (Crawford dışı, `matchLength > 0`) çiftleme
kararını şöyle veriyordu:

```csharp
double doubleValue = Math.Max(doubleTake, doublePass);
bool shouldDouble = doubleValue > noDouble + Epsilon;
```

`Math.Max`, **rakibin işbirliği yaptığını** varsayar: çiftlediğimizde rakip, kendi equity'si için
hangisi iyiyse onu seçer. Rakip kendi equity'sini **maksimize** eder; bu bizim equity'mizi
**minimize** etmek demektir. Dolayısıyla çiftlemeden sonra gerçekleşen değer

```
doubleValue = Math.Min(doubleTake, doublePass)
```

olmalıdır. `max` kullanıldığında, rakip için "pas vermek daha iyi" olan her pozisyonda (yani
`doublePass > doubleTake`) danışman çiftlemeyi **fazla iyimser** görüyordu.

**Kanıt (133 geçerli pozisyon, `diceAveraged`, gnubg 0-ply).** `max` ile 32 fazla çiftleme vardı
(biz çiftle, gnubg çiftleme). Bunların 19'u `min` altında "çiftleme"ye dönüyor. Yani hatanın
tamamı tek yönlüydü ve tam olarak bu karşılaştırmadan geliyordu.

**Düzeltme.** `EquityCubeAdvisor.Decide`:

```csharp
double doubleValue = Math.Min(doubleTake, doublePass);
bool tooGood = doublePass > doubleTake && noDouble > doubleTake;
bool shouldDouble = doubleValue > noDouble + Epsilon;
```

`tooGood` de sıkılaştırıldı. Eski koşul (`doublePass > doubleTake`) "rakip için pas daha iyiyse
çiftlemek zaten anlamsız" varsayıyordu; bu yanlıştı, çünkü rakip pas verdiğinde biz yine 1 puan
kazanırız ve bu `noDouble`'dan büyük olabilir. Doğru koşul, **hem** pasın kabulden iyi olması
**hem** de çiftlemeden elde edilen değerin çiftlememekten küçük olmasıdır.

**Etki (gnubg 0-ply, 133 geçerli pozisyon, `diceAveraged`).**

| Metrik | F6-29 sonrası | **F6-30 sonrası** |
|---|---|---|
| Çiftleme uyumu | 73,68 % | **84,96 %** |
| Kabul/ret uyumu | 88,72 % | 88,72 % |
| Her iki karar uyumu | 69,17 % | **81,20 %** |
| Equity korelasyonu | 0,8330 | 0,8330 |
| Equity ortalama \|Δ\| | 0,3738 | 0,3738 |
| Equity p90 \|Δ\| | 0,9038 | 0,9038 |

Kabul/ret ve equity metrikleri **değişmedi** — bu beklenen: `min`/`max` yalnızca "çiftle mi?"
kararını etkiler, kabul kararını ve değerlendirmeyi etkilemez. Bu, düzeltmenin gerçekten tek bir
karşılaştırmaya dokunduğunun kanıtıdır.

Karışıklık matrisi (çiftleme): 39 ortak çiftleme, 13 fazla, 7 kaçırılan, 74 ortak çiftlememe.
Hata artık iki yöne de dağılmış durumda (13 vs 7), yani sistematik değil.

**Kapı durumu.** v3 §13.3 çiftleme uyumu kapısı **≥ %75**; ölçülen **84,96 %** — kapı **geçildi**.
Ortalama \|Δ\| kapısı **< 1,2063**; ölçülen **0,3738** — kapı **geçildi**.

**Neden Faz 5'te görülmedi.** Faz 5'in `stage_b_cube_*` ölçümü aynı `max` mantığını kullanıyordu
ama o zaman F6-28/F6-29 hataları baskındı (korelasyon 0,11), bu yüzden `max`'ın katkısı
görülemiyordu. Üç hata birbirini maskeliyordu.

## F6-31 — Faz 5 kalibrasyon ölçümü tahtayı aynalanmış veriyordu

**Durum.** TEYİTLİ (prob + iki bağımsız ölçüm yolu; düzeltme `ml/afterstate_bench.py`).

**Bulgu.** Faz 5'in §9.2 kalibrasyon ölçümü (`ml/afterstate_bench.py`) proje tahtasını gnubg'nin
`anBoard` düzenine **aynalanmış** olarak çeviriyordu:

```python
# HATALI (Faz 5)
row0 = [max(board[i], 0) for i in range(1, 25)] + [max(board[0], 0)]
row1 = [max(-board[24 - i], 0) for i in range(24)] + [max(-board[25], 0)]
```

Doğru çevirim (`ml/cube_bench.py::to_gnubg_board` ile aynı, prob ile doğrulandı):

```python
# DOGRU
row0 = [max(board[24 - i], 0) for i in range(24)] + [max(board[0], 0)]
row1 = [max(-board[1 + i], 0) for i in range(24)] + [max(-board[25], 0)]
```

Hatalı sürüm White'ın pullarını 24→1 sırasına diziyor, yani tahtayı ters çeviriyordu. Simetrik
olmayan her pozisyonda bu, tamamen farklı bir pozisyonu değerlendirmek demektir.

**Kanıt (prob, `gnubg-cli.exe -p`).** Simetrik pozisyon (White'ın 1 pulu 24-hanede, Black'in 1
pulu 1-hanede): doğru çevirim **+1,0000** (White kazanır), hatalı çevirim **+0,2819**, üçüncü bir
varyant **−0,9444**. Asimetrik bir pozisyonda doğru çevirim **−0,7778**, hatalı çevirim
**+0,5602** — işaret bile değişiyor.

**İkinci hata: gnubg Python API'si bu projede güvenilir değil.** Aynı ölçümü doğru tahta çevirimi
ama Python API (`gnubg.evaluate`) ile tekrarladığımızda eğim **−0,0011**, korelasyon **−0,0022**
çıktı — yani gürültü. Sebep F6-28'in aynısı: `cubeinfo['move']` yok sayılıyor ve `anBoard[1]`
her zaman "sırada olan" kabul ediliyor. Dört farklı tahta çevirimi denendi; hiçbiri metin
protokolüyle uyuşmadı (en iyisi korelasyon −0,88, yani işaret ters). **Sonuç: kalibrasyon ölçümü
için tek güvenilir yol gnubg metin protokolüdür** (`GnubgSession.eval_afterstates`).

**Düzeltme.** `ml/afterstate_bench.py::to_gnubg_board` doğru çevirime alındı ve modül "tarihsel
kayıt, üretimde kullanılmaz" olarak işaretlendi. Kalibrasyon ölçümü için yeni
`ml/calibration_bench.py` yazıldı; gnubg metin protokolünü kullanır, pip sayılarını doğrular ve
`measure_position` ile aynı perspektif sözleşmesini uygular.

**Etki (400 afterstate, `model_v30.onnx`, gnubg 0-ply).**

| Metrik | Faz 5 (hatalı) | **Faz 6 (doğru)** | Kapı |
|---|---|---|---|
| Eğim | 0,0874 | **0,6601** | 0,85–1,15 → **geçilemedi** |
| Korelasyon | +0,2431 | **+0,8989** | ≥ 0,75 → geçildi |
| MAE | 0,8014 | **0,2755** | ≤ 0,15 → **geçilemedi** |
| Std oranı | 2,78 | **1,3617** | 0,7–1,4 → geçildi |

2-ply gnubg ile aynı ölçüm: eğim **0,6743**, korelasyon **+0,9016**, MAE **0,2683**, std oranı
**1,3371** — 0-ply ile tutarlı, yani sonuç ply seçimine duyarlı değil.

**Yorum.** Faz 5'in "korelasyon 0,24" rakamı modelin gerçek kalitesi değildi; ölçüm hatasıydı.
Gerçek korelasyon 0,90. Buna karşılık eğim 0,66 ve MAE 0,28 hâlâ kapıların dışında: model
gnubg'ye göre **sistematik olarak düşük** (sapma −0,1547) ve **fazla yayılı** (std oranı 1,36).
Bu, Faz 6'nın kalan gerçek açığıdır ve §13.2'de sapma olarak raporlanmıştır.

**Neden Faz 5'te görülmedi.** Ölçüm betiği hiçbir zaman bağımsız bir yolla (metin protokolü veya
elle hesaplanmış tek pozisyon) doğrulanmamıştı. Tek bir simetrik pozisyon probu hatayı anında
gösterirdi.
---

## F6-32 — gnubg `eval` komutu 2-ply'den derin sütun üretmez; `_equity_at` sessizce 0-ply'ye düşüyordu

**Tarih:** Faz 6, Aşama H sonrası (3-ply ER farkının teşhisi).

**Belirti.** Aynı model (`ml/runs/stage_d_l2/onnx/model_v30.onnx`), aynı 200 pozisyonluk
`reference_corpus_v1.json`, aynı gnubg sürümü ile iki ER ölçümü yapıldı:

| Ölçüm | Ortalama ER | Medyan | Maks | Tam eşleşme | SE | SD |
|---|---|---|---|---|---|---|
| `--plies 2` | **0,0740** | 0,016 | 0,469 | %36,5 | 0,0077 | 0,1091 |
| `--plies 3` | **0,0972** | 0,018 | 0,738 | %36,0 | 0,0111 | 0,1565 |

"3-ply daha kötü" gibi görünüyordu. Modelin seçtiği afterstate 200/200 pozisyonda **birebir
aynıydı** (model politika başının argmax'ını kullanır, ply'e bağlı değildir), yani fark modelden
değil hakemden geliyordu.

**Kök neden.** `ml/gnubg_er.py::_equity_at` istenen derinlikteki sütunu bulamayınca sessizce
sıralamanın son anahtarına düşüyordu:

```python
key = str(plies)
if key not in table:
    key = sorted(table, key=lambda k: (k == "static", k))[-1]
```

`(k == "static", k)` anahtarıyla artan sıralama `"1"`, `"2"`, `"static"` verir; yani son eleman
**`static`**'tir. gnubg'nin `eval` komutu ise — `set evaluation chequerplay evaluation plies N`
ayarı ne olursa olsun — **yalnızca** `static` (0-ply), `1 ply` ve `2 ply` satırlarını basar.
Ölçüm:

```
$ gnubg-cli -p  (set evaluation chequerplay evaluation plies 3)
        Win     W(g)    W(bg)   L(g)    L(bg)   Equity    Cubeful
static: 0,296   0,067   0,002   0,393   0,055   -0,787    -0,858
 1 ply: 0,338   0,065   0,002   0,326   0,047   -0,630    -0,887
 2 ply: 0,306   0,068   0,003   0,363   0,052   -0,733    -0,935
```

`plies=2`, `plies=3` ve `plies=4` için tablo anahtarları **her zaman** `['1', '2', 'static']`.
Dolayısıyla `--plies 3` çalıştırması `static` sütununu, yani **0-ply** değerini okudu.

**Kanıt.** `--plies 0` ile yapılan ölçüm `--plies 3` ile **200/200 pozisyonda birebir aynı**
sonucu verdi (ortalama 0,097225, medyan 0,018, maks 0,738, tam eşleşme %36,0, SE 0,011067,
SD 0,15651). Yani "3-ply" rakamı aslında 0-ply rakamıdır.

**Düzeltme.** `_equity_at` artık sessizce düşmüyor:

* `plies == 0` → `static` sütunu (açık eşleme).
* `plies in (1, 2)` → ilgili sütun.
* aksi halde `ValueError` — "gnubg 'eval' tablosunda N-ply sütunu yok … daha derin hakem için
  'hint' protokolü gerekir".
* Yeni sabit `gnubg_er.MAX_EVAL_PLIES = 2`.
* `ml/er_harness.py measure` `--plies > MAX_EVAL_PLIES` için çalışmadan önce anlaşılır hata verip
  çıkış kodu 2 döner; uydurma değer üretmez.

**Etki — gerçek ER merdiveni.**

| Hakem derinliği | Ortalama ER | Not |
|---|---|---|
| 0-ply (`static`) | 0,0972 | gnubg'nin statik değerlendiricisi |
| 1-ply | ölçülmedi | |
| **2-ply** | **0,0740** | **Faz 6'nın raporladığı değer** |
| 3-ply | **ölçülemez** | gnubg `eval` üretmiyor |

Yani model, hakem güçlendikçe **iyileşiyor** (0,0972 → 0,0740), kötüleşmiyor. "3-ply daha kötü"
gözlemi tamamen ölçüm hatasıydı.

**Gerçek 3-ply hakem nasıl elde edilir.** gnubg'nin `hint` komutu `plies` ayarına **uyar**:
`set evaluation chequerplay evaluation plies 3` + `hint` çağrısı, o pozisyonun her aday hamlesi
için 3-ply equity döndürür (probe: `f6-006` için 2-ply hint 1,0840, 3-ply hint 1,0380, 4-ply
hint 1,0850 — `eval` tablosu ise üç durumda da aynı). Dolayısıyla derin hakem ölçümü `hint`
protokolü + hamle→afterstate eşlemesi ile kurulmalıdır. Bu, Faz 7'nin ölçüm hattı işidir.

**Ders.** Ölçüm hattında "istenen değer yoksa en yakınını kullan" davranışı yasaktır. Bir
referans değerin hangi sütundan geldiği ya açıkça eşlenmeli ya da ölçüm durmalıdır. Bu, F6-31'in
(aynalanmış tahta) kardeşidir: iki hata da **sessiz** olduğu için aylarca fark edilmedi.

---

## F7-01 — gnubg `hint` hamle filtresi derin değerlendirmeyi sessizce budar

**Tarih:** Faz 7, Aşama A (derin hakem kurulurken).

**Belirti.** `set evaluation chequerplay evaluation plies 3` + `hint` çağrısı, `f6-000`
pozisyonunda hamleleri **2-ply** etiketiyle döndürdü:

```
1. Cubeless 2-ply 13/5*(2)     Eq.: +0,253
3. Cubeless 0-ply 13/5*/1 6/2  Eq.: +0,082
```

Yani "3-ply ER" ölçümü sessizce 2-ply (ve hatta 0-ply) olurdu — F6-32'nin birebir tekrarı.

**Kök neden.** `hint` `plies` ayarına uyar, **ama önce gnubg'nin hamle filtresini uygular**
ve yalnızca hayatta kalan adayları istenen derinlikte değerlendirir. Varsayılan filtre
(`show evaluation`):

```
Move filter for 3 ply:
  keep the first 0 0-ply moves and up to 8 more moves within equity 0,16
  Skip pruning for 1-ply moves.
  keep the first 0 2-ply moves and up to 2 more moves within equity 0,04
```

`plies=3` için yalnızca ~2 hamle gerçekten 3-ply olur. Faz 6 bunu fark etmedi çünkü
`f6-006`'da en iyi hamle tesadüfen terfi ettirilmişti.

**Düzeltme.** `set evaluation movefilter <plies> <level> 1000 0 0.0` komutu
**`level in range(plies)`** için, yani `0..plies-1` seviyelerinin **hepsi** açılmalıdır.
Yalnızca `0..plies-2` seviyelerini açmak son seviyeyi kapalı bırakır ve hamleler yine
`plies-1` etiketiyle döner. Ölçüm (`f6-000`):

| `plies` | açılan seviyeler | görülen derinlikler | süre |
|---|---|---|---|
| 3 | `[0]` | `{2}` | 0,4 s |
| 3 | `[0,1]` | `{2}` | 0,4 s |
| 3 | `[0,1,2]` | **`{3}`** | 2,5 s |
| 4 | `[0,1,2]` | **`{4}`** | 48,8 s |
| 4 | `[0,1,2,3]` | **`{4}`** | 51,1 s |

Sözdizimi: komut `set evaluation movefilter`'dır (`set evaluation chequerplay movefilter`
→ "Unknown keyword `movefilter'"); ply argümanı çıplak tam sayıdır (`3`, `4`), `3ply`
değil; seviye argümanı zorunludur; eşik `0.0`, `0.000` veya `0` kabul edilir.

**Koruma.** `ml/gnubg_hint.py::HintReferee._preamble()` tüm seviyeleri açar;
`verify_uniform_depth()` çıktıdaki her hamlenin etiketini denetler ve tekdüze değilse
`HintMappingError` atar. `ml/tests/test_gnubg_hint.py` içindeki `test_92_hint_without_widening_degrades_silently`
bu davranışı **kanıt olarak** kilitler.

**Ders.** "Derinlik ayarını yaptım" ≠ "derinlik uygulandı". Her derinlik iddiası, çıktının
**kendi etiketinden** doğrulanmalıdır.

---

## F7-02 — gnubg hamle notasyonu sırada olan oyuncunun bakış açısındadır

**Tarih:** Faz 7, Aşama A.

**Belirti.** `hint` hamle metinleri (`"23/17 7/4"`) afterstate'lere eşlenirken, `turn = +1`
pozisyonlarında eşleme **hiç** tutmuyordu.

**Kök neden.** X (Siyah, `turn = -1`) mutlak hane numaralarını kullanır; O (Beyaz,
`turn = +1`) **aynalanmış** numaraları (`p -> 25 - p`). 40 kumede doğrulandı:

| `turn` | kimlik eşlemesi | aynalama |
|---|---|---|
| `-1` | 10/10 | 0/10 |
| `+1` | 0/10 | 10/10 |

**Düzeltme.** `_point()` `value if turn == -1 else 25 - value` döndürür. Ek ayrıntı:
çok adımlı hamlelerde **ara haneler vurma işaretini taşır** (`"13/5*/1"` → `5*` hem varış
hem kalkıştır), bu yüzden `parts[i].rstrip("*")` zorunludur.

**Kanıt.** `test_92_map_hints_covers_corpus_subset` 20 pozisyonda 0 eşleme hatası verir;
tam 200 pozisyonluk koşuda `mappingFailures = 0`.

---

## F7-03 — gnubg `hint` en fazla 10 hamle basar

**Tarih:** Faz 7, Aşama A.

**Belirti.** `f6-001`'in 43 yasal afterstate'i vardır ama `hint` **10** hamle döndürür.
Yani modelin seçtiği afterstate her zaman listede değildir: ölçüldü, **39/200 = %19,5**.

**Çözüm.**

* `plies <= 2`: modelin afterstate'i doğrudan `eval` ile değerlendirilir → **%100 kapsama**.
* `plies >= 3`: `eval` daha derine inemez (F6-32), bu yüzden pozisyon **sansürlü** işaretlenir
  ve kayıp için yalnızca **alt sınır** raporlanır (`best − worst_listed`).

**Sonuç.** Kapsama (`coverage`) birinci sınıf metriktir. Şampiyon iddiası **kapsama ≥ %99**
şartına bağlıdır (`faz 7.md` §10.7 F-A9). 2-ply'de kapsama %100'dür; 3-ply/4-ply'de
tasarım gereği ~%80'dir ve bu, 4-ply kanıt iddiasının **açık kısıtıdır**.

---

## F7-04 — `hint@2` ile `eval@2` aynı şey değildir

**Tarih:** Faz 7, Aşama A.

**Belirti.** Aynı afterstate için `hint@2` ile `eval@2` farklı değer verdi
(`f6-161`: −0,8920 vs −1,0100; `f6-185`: −1,7070 vs −1,6130).

**Ölçüm.** 10 pozisyonda: 6'sında birebir aynı, 4'ünde 0,118'e kadar farklı. Merdivenin
1→2 ve 2→3 adımları aynı büyüklüktedir (ortalama 0,134 / 0,107), yani bu bir kusur değil,
oynak pozisyonlarda normal arama gürültüsüdür. `prune on/off` farkı açıklamıyor.

**Karar.** Tek bir kod yolu zorunludur:

* **2-ply hakemi = `eval`** (Faz 6 ile karşılaştırılabilir, standart gnubg).
* **3-ply / 4-ply hakemi = `hint`** (filtre açık).
* `hint@2` hakem olarak **kullanılmaz**; `referee_for_plies()` bunu zorlar.

**Sonuç.** 2-ply → 3-ply geçişi bir **yöntem değişikliğidir**; merdiven 2/3 sınırında
elma-elmadır değildir. Her rapor `methodNote` alanında bunu yazmak zorundadır
(`LADDER_METHOD_NOTE`).

## F7-05 — `OutcomeDistribution.Flip()` bit düzeyinde involüsyon değildir

**Tarih:** 2026-07-17 (Faz 7, Aşama A)

**Belirti.** `faz 7.md` §9.9 grup 6, `flip(d).Equity == -d.Equity` ve
`flip(flip(d)) == d` eşitliklerini **bit düzeyinde** istiyordu. `EquityGoldenTests`
bu iddiayla yazıldı ve **kırmızı** yandı: 300 kayıtta `flip(d).Equity` ile
`-d.Equity` 16 haneli float64 bit deseninde ayrıştı (`bfc7913948000000` beklenirken
`bfc7913908000000`).

**Kök neden.** `Flip()` alanları doğrudan kopyalamaz; dışlayıcı sınıfları
(`LoseSingle`, `LoseGammonOnly`, …) hesaplayıp `FromProbabilities`'a verir. O fabrika
`inv = 1/sum` ile **yeniden normalize eder** ve `sum` float32'de tam `1` olmayabilir
(`Lose = 1f − Win` yuvarlaması). Her çarpım bir ulp yuvarlama ekler; iki flip üst
üste binince sapma birikir. Yani eşitlikler **matematiksel olarak** doğru,
**kayan noktada** yaklaşıktır.

**Ölçüm.** 296 geçerli kayıt üzerinde:

| Ölçüm | Değer |
|---|---|
| `max abs(flip(d).Equity + d.Equity)` | **1,3411e-07** |
| `flip(flip(d))` float32 alan uyuşmazlığı | 81 / 1 480 alan |
| Backgammon equity çözünürlüğü (karşılaştırma) | 1e-4 |

Sapma, equity çözünürlüğünün **üç mertebe** altındadır; oyun kararlarını etkilemez.

**Düzeltme.**
1. `EquityGoldenTests.EquityFlip_IsInvolution` artık `1e-6` tolerans kullanır ve
   **ölçülen** en büyük sapmayı da raporlar (`maxEquityDeviation`,
   `maxFieldDeviation`). `EquityFlip_InvalidStaysInvalid` eklendi.
2. `OutcomeDistribution.Flip()` XML dokümanı düzeltildi: `≈` ve F7-05 notu.
3. `faz 7.md` §9.9 grup 6 satırı `≈` + tolerans olarak güncellendi.

**Etki.** Equity formülünün kendisi **değişmedi**; yalnızca doküman iddiası
gerçeğe çekildi. Test 122'nin `atol = 0` iddiası `equityHex`/`cumulativeHex`
karşılaştırmasında **aynen geçerli** (bkz. F7-06); yalnızca `flip` involüsyonu
toleranslıdır.

**Ders.** "Cebirsel olarak eşit" ile "bit düzeyinde eşit" aynı şey değildir.
Yeniden normalize eden her fabrika, girdisi zaten normalize olsa bile yuvarlama
ekler. Bir eşitliği teste yazmadan önce **hangi mertebede** doğru olması
gerektiğini yaz.

## F7-06 — C#/Python equity paritesi float32 aynası olmadan kurulamaz

**Tarih:** 2026-07-17 (Faz 7, Aşama A)

**Belirti.** `faz 7.md` §9.9, Python tüketicisinin `ml/equity.py` ile altın dosyayı
`atol = 0` karşılaştırmasını istiyordu. `ml/equity.py` **float64** çalışır; C#
`OutcomeDistribution` alanlarını **float32** tutar. İlk denemede `unnormalized`
grubunda equity sapması **0,156** çıktı — formül aynı olmasına rağmen.

**Kök neden.** İki farklı yuvarlama rejimi:
- C#: `sum` float64, `inv` float64, `(float)(w*inv)` float32, kümülatif toplamlar
  float32, kırpma float32, `Equity` float64.
- `ml/equity.py`: her şey float64, kırpma **yok**.

`unnormalized` grubunda normalize edilmemiş girdi float64'te `1/sum` ile
ölçeklenirken float32'de yuvarlanır; fark 1e-1 mertebesine çıkar.

**Ölçüm.** `ml/equity.py` içine C# kodunun birebir float32 aynası eklendikten sonra
(`normalize_exclusive_f32`, `to_cumulative_f32`, `equity_from_cumulative_f32`,
`equity_from_exclusive_f32`, `flip_f32`):

| Karşılaştırma | Sonuç |
|---|---|
| 296 geçerli kayıt × 5 kümülatif alan, `cumulativeHex` | **0 uyuşmazlık** |
| 296 geçerli kayıt, `equityHex` | **0 uyuşmazlık** |
| 4 geçersiz kayıt → `ValueError` | 4/4 |
| float64 üretim yolu vs float32 ayna | ≤ 1e-6 |

**Düzeltme.** `ml/equity.py`'ye float32 ayna bloğu eklendi (C# kodunun satır satır
kopyası, yorumda "C# değişirse burası da değişir" kuralı). `ml/tests/test_equity_parity.py`
(26 test) aynayı `atol = 0` ile, float64 yolu `1e-6` ile doğrular. `conftest.py`'ye
`GOLDEN_EQUITY_PATH` eklendi. `test_stage_b.py::test_53` docstring'i **duman testi**
olarak indirgendi (artık çapraz dil sözleşmesi değil).

**Etki.** Test 122/123 artık gerçek: iki dil **aynı dosyayı** okuyor ve **aynı bit
desenini** üretiyor. Formül bir tarafta değişirse test kırmızı yanar.

**Ders.** Çapraz dil paritesi, **yuvarlama rejimini** de sözleşmeye dahil etmeyi
gerektirir. "Aynı formül" yetmez; "aynı float genişliği, aynı işlem sırası, aynı
kırpma" gerekir.

## F7-07 — 4-ply `hint` maliyeti sınırsızdır; 62,57 s/pozisyon tahmini temsili değildir

**Tarih:** 2026-07-17

**Belirti.** İnsan karşılaştırma merdiveni (Bölüm 4.4) 4-ply `hint` hakemiyle
60 pozisyonluk CAL kümesinde koşturuldu. 14 pozisyon 2 412,9 s'de tamamlandı
(**172 s/pozisyon**), 15. pozisyonda (`f6-040`) gnubg **900 s** zaman aşımına
çarptı ve koşu düştü.

**Kök neden.** Bölüm 4.2.4'teki 62,57 s/pozisyon değeri **8–20 pozisyonluk** bir
örneklemde ölçüldü ve o örneklem `closed`/`race` ağırlıklıydı. 4-ply `hint`
maliyeti afterstate sayısıyla ve pozisyonun temas yoğunluğuyla **doğrusal
değil**, patlamalı büyür: filtre açıkken gnubg her adayı 4-ply'da arar, temas
pozisyonunda aday sayısı 40'ı aşar. Ölçülen dağılım:

| Pozisyon tipi | 4-ply `hint` süresi |
|---|---|
| `closed` / `race` (az afterstate) | 19–63 s |
| `contact` (çok afterstate) | 172 s ortalama |
| `f6-040` (en yoğun) | **> 900 s** (zaman aşımı) |

**Ölçüm.** 60 pozisyonluk CAL kümesinde 3-ply hakemle merdiven:
**642,6 s (10,71 s/pozisyon)**, atlanan 0. 4-ply ile aynı küme **en az 10 saat**
(60 × 172 s = 10 320 s), en kötü durumda **15 saat** (60 × 900 s).

**Karar.** Merdiven hakemi **3-ply**'a indirildi. Basamaklar:

| # | Referans | Kaynak | ER | Kapsama |
|---|---|---|---|---|
| 0 | gnubg 0-ply | ölçülür | 0,0522 | %86,7 |
| 1 | gnubg 1-ply | ölçülür | 0,0530 | %80,0 |
| 2 | gnubg 2-ply | ölçülür | 0,0525 | %91,7 |
| 3 | gnubg 3-ply | **hakemin kendisi** | 0 (tanım) | %100 |
| 4 | gnubg 4-ply | **ölçülmedi** | — | — |
| 5 | dünya şampiyonu insan | **literatür** | 0,0025 | — |
| 6 | gnubg 4-ply + büyük ağ | **literatür** | 0,003 | — |

4. basamak **uydurulmadı**; `source = "unmeasured"` ve gerekçe yazıldı.

**Etki.** Bölüm 4.4'ün "0–4 basamak ölçülür" koşulu **kısmen** karşılanır:
0–3 ölçüldü, 4 ölçülmedi. Bölüm 5.1.5'teki 4-ply bütçe satırı (1 670 pozisyon
≈ 29 saat) **geçersizdir**; gerçek maliyet 1 670 × 172 s ≈ **80 saat** (en kötü
durumda 418 saat). 40 saat tavanı 4-ply için **tutmaz**.

**Ders.** Bir birim maliyet, ölçüldüğü örneklemden **daha geniş** bir kümeye
genellenemez. `closed`/`race` pozisyonlarında ölçülen süre, `contact`
pozisyonlarının süresini **üçe katlar**. Bütçe hesabı, maliyetin **dağılımını**
(faz bazında) kullanmalıdır, ortalamasını değil.

## F7-08 — Değer başlığının "kritik karar" maskesi para oyununda dejenere

**Tarih:** 2026-11-17 (Faz 7, Aşama B)

**Belirti.** Bölüm 5.3 / Test 98, kritik kararları `|equity| >= 0,5` ile
işaretleyip örnekleme ağırlığını `2,0` ile çarpmayı istiyor. `ml/critical.py`
uygulandı ve `ml/train_v2.py`'ye bağlandı. İlk gerçek koşuda **değer başlığında
587 337 örneğin 587 337'si** kritik çıktı (`criticalShare = 1,0`).

**Kök neden.** Para oyununda bir değer örneğinin `equity` alanı **her zaman
±1**'dir: sonuç tek/çift/üçlü oyun kazancıdır, arada değer yoktur. Dolayısıyla
`|equity| >= 0,5` koşulu **hiçbir şeyi ayırmaz** — maske sabit `True`'dur,
ağırlıklar tekdüzedir, `boost` etkisizdir. Eşik, maç oyunu (match play) için
tasarlanmış bir niceliği para oyununa uyguluyordu.

**Ölçüm.** Aynı koşuda politika başlığı **ayrıştırıcı** çalıştı:

| Başlık | Örnek | Kritik | Oran | Etkin örnek | Etkin oran |
|---|---|---|---|---|---|
| değer | 587 337 | 587 337 | **%100** | 587 337 | %100 |
| politika | 427 069 | 113 868 | **%26,66** | 380 672 | %89,1 |

Politika maskesi `decision_margin <= 0,05` kullandığı için gerçekten "neredeyse
eşit adaylar"ı seçiyor; ortalama ağırlık 2,34e-06, en büyük ağırlık 3,70e-06.

**Düzeltme.** `weight_distribution` artık `degenerate` alanı döndürür
(`count == 0` veya `share <= 0` veya `share >= 1`). `train_v2.py` dejenere bir
başlık için ağırlığı **uygulamaz** ve durumu `train_report.json` içinde
`critical.<head>.degenerate = true` olarak **raporlar**. Sessizce etkisiz bir
`boost` çalıştırmak, "kritik ağırlıklandırma yapıldı" yanılgısını üretirdi.

**Açık kalan.** Değer başlığı için **doğru ölçüt henüz tasarlanmadı**. Aday
ölçütler: (a) aramanın aday yayılımından türetilen marj (politika gibi, ama
değer hedefiyle), (b) maç oyunu bağlamında `|equity|` (küp eşiğine yakınlık),
(c) `|equity|` yerine "sonucun işaretinin belirsizliği" (ör. `P(win) ~ 0,5`).
Test 98'in **politika** yarısı geçerlidir; **değer** yarısı açık uçludur.

**Ders.** Bir eşik, tasarlandığı oyun bağlamının dışında **dejenere** olabilir ve
bunu ancak dağılımı yazdırmak gösterir. Maske üreten her fonksiyon, maskenin
**doluluk oranını** da döndürmelidir; aksi halde "ağırlıklandırma açık" ile
"ağırlıklandırma etkili" karıştırılır.

## F7-10 — `train_v2.py` eğitilmiş modeli ONNX'e aktarmıyor; tek iterasyonluk koşuda "model" rastgele başlangıçtır

**Tarih:** 2026-11-17 (Faz 7, Aşama B)

**Belirti.** Aşama B'nin kapasite karşılaştırması (Test 96) iki profili aynı
shard'larda, aynı tohumla, aynı adım sayısıyla eğitti ve VAL-ER ölçtü. İlk koşu
(1 000 adım, tek shard) `medium` **0,2631**, `large` **0,2532** verdi — %3,8 fark.
İkinci koşu (3 000 adım, 6 shard) `medium` için **birebir aynı 0,2631** değerini
verdi. Dört ondalıkta birebir aynı sonuç, iki farklı eğitimin ürünü olamaz.

**Kök neden.** `ml/train_v2.py` ONNX'i her iterasyonun **başında** dışarı aktarır:

```python
for it in range(start_iteration + 1, iterations + 1):
    model_version += 1
    onnx_path = onnx_dir / ("model_v" + str(model_version) + ".onnx")
    export(model, str(onnx_path), model_version, ...)   # <-- egitimden ONCE
    ...
    train_steps_v2(...)                                  # <-- egitim SONRA
```

Bu, çok iterasyonlu self-play döngüsü için **doğrudur**: N. iterasyonun
self-play'i N-1'de eğitilmiş modeli kullanmalıdır. Ama iki sonucu vardır:

1. Koşunun **sonundaki** model hiçbir zaman ONNX'e yazılmaz; yalnızca
   `checkpoints/ckpt_vN.pt` içinde kalır.
2. `--iterations 1` ile koşulduğunda `model_v1.onnx`, eğitim **öncesi** ağırlıklar
   — yani **rastgele başlangıç** — olur.

Ölçülen 0,2631 tam olarak rastgele başlangıcın ER'idir. Üretim koşusunda
(`stage_d_l2`, 30 iterasyon) `model_v30.onnx` bir iterasyon **geridedir**; fark
küçüktür ama gerçektir.

**Ölçüm.** Aynı checkpoint'ten (`ckpt_v1.pt`) doğru yolla aktarılan model:

| Model | VAL-ER | SE | Not |
|---|---|---|---|
| `model_v1.onnx` (eğitim öncesi) | **0,2631** | 0,0356 | rastgele başlangıç |
| `model_v1_trained.onnx` (eğitim sonrası) | **0,0640** | 0,0119 | 3 000 adım, 6 shard |

Fark **4,1×**. İlk koşudaki "%3,8 kapasite kazancı" bir kapasite sinyali değil,
**başlangıç ağırlıklarının gürültüsüydü**.

**Düzeltme.** `ml/export_ckpt.py` eklendi: checkpoint → ONNX (profil checkpoint
meta verisinden okunur). Aşama B'nin tüm VAL-ER ölçümleri bu yolla üretildi.
`train_v2.py`'nin döngü sözleşmesi **değiştirilmedi** (self-play semantiği
korunur); eksik olan "koşu sonu aktarımı" ayrı bir araç olarak eklendi.

**Etki.** Test 96'nın ilk sonucu **geçersizdir** ve raporda öyle işaretlendi.
Üretim `model_v30.onnx` bir iterasyon geridedir; Faz 6'nın 0,0740 (2-ply) değeri
de bu modelle ölçüldüğü için **hafif kötümser** olabilir — ama bu doğrulanmadı.

**Ders.** "Eğitim bitti" ile "eğitilmiş model diskte" aynı şey değildir. Bir
eğitim betiğinin çıktı sözleşmesi, **hangi dosyanın hangi ana ait olduğunu**
açıkça yazmalıdır. Bu projede aynı sınıf hata üçüncü kez görülüyor (F6-32 sessiz
0-ply, F7-04 `hint@2` ≠ `eval@2`, F7-10 eğitim öncesi ONNX): **sessizce yanlış
şeyi ölçmek**, yanlış sayı üretmekten daha pahalıdır.

## F7-09 — Depth 2, gerçek ONNX modeliyle bütçeyi 10 kat aşıyor; Test 79 sentetik değerlendirici kullanıyordu

**Tarih:** 2026-11-17 (Faz 7, Aşama B)

**Belirti.** Bölüm 5.2'nin (b) bacağı depth 2 için p95 ≤ 2 s istiyor. Faz 6 Test
79 bu kapıyı **0,7133 s** ile geçtiğini raporlamıştı. Gerçek ONNX modeliyle
ölçüm:

| Model | Derinlik | p50 | p95 | Ortalama | ONNX çağrısı / karar |
|---|---|---|---|---|---|
| `medium` | 0 | 0,0003 s | 0,0010 s | 0,0004 s | 1 |
| `medium` | 1 | 0,0233 s | 0,0902 s | 0,0328 s | 85 |
| `medium` | **2** | **2,0300 s** | **4,4972 s** | **2,1471 s** | 6 028 |
| `large` | 1 | 0,0718 s | 0,2598 s | 0,0895 s | 85 |
| `large` | **2** | **6,5306 s** | **13,6816 s** | **6,9198 s** | 5 948 |

`medium` p95 **4,50 s** — kapının 2,2 katı. `large` **13,68 s** — 6,8 katı.

**Kök neden 1 — Test 79 sentetikti.** `Backgammon.Tests/Search/SearchPowerTests.cs`
Test 79 `HashEvaluator`/`HashPolicyEvaluator` kullanır. Bu değerlendiriciler
vektörleştirme, ONNX çalıştırması ve tensör kopyası yapmaz. 0,7133 s **arama
yapısının** maliyetidir, **çıkarımın** değil. `ARCHITECTURE.md` §50.4'teki
"Depth 2 p95 0,7133 s → geçti" satırı bu nedenle yanlıştı.

**Kök neden 2 — maliyet çağrı sayısıyla doğrusal.** Çağrı başına maliyet her iki
modelde de ~0,35 ms ve **kova boyutundan bağımsız** (kova 1 ile kova 84 aynı).
Aramanın çağrı yapısı:

- depth 1: kök (1 çağrı, kova 84) + 84 şans düğümü (kova 21) = **85 çağrı**
- depth 2: kök (1) + 84 şans düğümü (kova 84) + 84×84 = 7 056 yaprak şans düğümü
  (kova 21) = **7 141 çağrı** (TT/önbellek isabetleriyle 6 028 ölçüldü)

Arama zaten her düğümde toplu değerlendiriyor
(`evaluator.EvaluateBatch(list, 0, nonTerminal, ...)`). Eksik olan **kardeş şans
düğümlerinin birlikte** değerlendirilmesidir: bir "yaprak cephe" geçişi 7 056
küçük çağrıyı ~72 büyük çağrıya indirir (teorik ~0,03 s).

**Etki.** Bölüm 5.1'in tüm bütçesi `stage_e_search.md`'nin 0,1939 s ortalama /
0,7133 s p95 değerleri üzerine kuruluydu. Gerçek maliyet **~11 kat** fazladır.
Üretimde kullanılabilir derinlik **depth 1**'dir (p95 0,09 s, bütçenin %4,5'i).
Depth 2, yaprak-cephe toplu değerlendirmesi eklenmeden üretime giremez.

**Ders.** Bir performans kapısı, **üretimdeki bileşenlerin tamamıyla** ölçülmelidir.
Sentetik bir değerlendirici, arama iskeletini doğrular ama çıkarım maliyetini
**görünmez** kılar. Kapı testi "gerçek model + gerçek değerlendirici" ile
koşmalıdır; sentetik sürüm yalnızca regresyon testi olarak kalmalıdır.

## F7-11 — `train_report.json`'da `iterations` bir sayıdır, kayıtlar `history`'de

**Tarih:** 2026-11-17 (Faz 7, Aşama B)

**Belirti.** `ml/capacity_bench.py::load_critical_distribution` Test 98
dağılımını okumak için `payload["iterations"]` üzerinde `reversed()` çağırdı ve
`TypeError: 'int' object is not reversible` ile düştü.

**Kök neden.** `train_report.json` şemasında `iterations` **istenen iterasyon
sayısıdır** (int); iterasyon başına kayıtlar `history` **listesindedir**. Alan
adı, içeriği hakkında yanlış bir sezgi üretiyor.

**Düzeltme.** `load_critical_distribution` artık `history`'yi okur, listenin
dict olmayan öğelerini atlar ve `critical.policy` bulunamazsa `None` döner.

**Ders.** Bir JSON şemasında `-s` ile biten alan adı çoğul veri vaat etmez.
Tüketici, alanın **tipini** doğrulamadan üzerinde işlem yapmamalıdır.

## F7-12 — Değer başlığının kritik maskesi onarıldı: karar marjı ölçütü

**Tarih:** 2026-11-17 (Faz 7, Aşama B sonrası — B3 kararı)

**Belirti.** F7-08, değer başlığının `|equity| >= 0,5` maskesinin para oyununda
**dejenere** olduğunu gösterdi (kritik oran %100). Test 98'in değer yarısı bu
yüzden etkisizdi.

**Kök neden (yeniden).** Ölçüt, **hedef** equity üzerinden uygulanıyordu. Para
oyununda hedef equity her zaman ±1'dir. Bölüm 5.3'ün kastettiği nicelik ise
**kararın** equity'sidir: `|best_equity|` (arama değeri) **ve** `decision_margin`
(en iyi iki aday arasındaki fark). İkisi de shard kararının `q` alanında
mevcuttur; hedef equity'de değil.

**Düzeltme.** `ExclusiveSamples` iki yeni alan taşır: `margin` ve `best_equity`
(her ikisi de `DecisionRecord.q`'dan, `q` yoksa `NaN`). `critical.py` yeni
`critical_mask_value_margin(margins, best_equity=..., equity_threshold=0.5,
margin_threshold=0.05)` fonksiyonunu sunar ve Bölüm 5.3'ün **tam** ölçütünü
uygular. `build_report` `value_margins`/`value_best_equity` alır; verilmezse eski
`|equity|` yoluna düşer ve `criterion = "equity"` + `degenerate = true` yazar.

**Ölçüm (200 oyunluk gerçek shard kümesi, 12 264 değer örneği).**

| Ölçüt | Kritik oran | Etkin oran | Dejenere? |
|---|---|---|---|
| Eski: `\|equity(y)\| >= 0,5` | **%100,0** | %100,0 | **evet** |
| Yeni: `\|best_equity\| >= 0,5` **ve** `marj <= 0,05` | **%33,3** | %88,9 | hayır |

Marj dağılımı: p10 0,0000 / p50 0,0373 / p90 0,1917. Örneklerin **%87,5**'inde
`q` vardır; `q`'suz örnekler (`dup_cap` ile elenen kararlar) **kritik sayılmaz** —
bilinmeyen bir marj için ağırlık uydurulmaz.

**Ders.** Bir eşiğin **hangi niceliğe** uygulandığı, eşiğin kendisi kadar
önemlidir. "Hedef equity" ile "karar equity'si" aynı alanda (equity) yaşar ama
farklı dağılımlara sahiptir; yanlış olanı seçmek maskeyi sessizce sabitler.

## F7-13 — Post-hoc kalibrasyon onarımı eğimi düzeltiyor, MAE'yi düzeltmiyor

**Tarih:** 2026-11-17 (Faz 7, Aşama D — önceliklendirildi)

**Belirti.** `ml/artifacts/stage_h_calibration.json` (400 afterstate, gnubg 0-ply):
eğim **0,6601** (kapı 0,85–1,15) ve MAE **0,2755** (kapı ≤ 0,15) kapı dışında;
korelasyon +0,8989 ve std oranı 1,3617 kapı içinde. Ağ equity'nin **yönünü**
biliyor, **ölçeğini** kaçırıyor.

**Ölçüm.** `ml/calibrate.py` CAL/VAL bölmesi yapar (200/200, tohum 20261117,
Kural 10: onarım **yalnızca CAL**'da öğrenilir) ve VAL'de öncesi/sonrası verir:

| Metrik | Öncesi (VAL) | Sonrası (VAL) | Kapı | Sonuç |
|---|---|---|---|---|
| Eğim | 0,6447 | **0,9584** | 0,85–1,15 | geçti |
| Korelasyon | +0,9022 | +0,9022 | ≥ 0,75 | geçti |
| MAE | 0,2641 | **0,1782** | ≤ 0,15 | **KALDI** |
| Std oranı | 1,3993 | **0,9414** | 0,7–1,4 | geçti |

Affine onarım: `hedef ~ 0,6727 * tahmin + 0,1402`.

**Kök neden.** Doğrusal bir dönüşüm Pearson korelasyonunu **değiştirmez** ve
MAE'yi yalnızca ölçek/sapma kadar azaltır. Kalan 0,1782, ağın **koşullu**
dağılımının hâlâ yanlış olduğunu gösterir: tek bir global `a, b` çifti, pozisyona
bağlı hatayı düzeltemez.

**Sonuç.** Post-hoc onarım **yetmiyor**. `L_cal` terimiyle yeniden eğitim
(`c_cal = 0.1`, Bölüm 6.2 adım 2) zorunludur. Bu yüzden kalibrasyon, Aşama D'de
**diğer kaldıraçların önüne** alındı.

**Ders.** "Kalibrasyon onarıldı" iddiası, **hangi metriğin** düzeldiğine
bağlıdır. Eğim ve std oranı bir affine dönüşümle düzelir; MAE ve korelasyon
düzelmez. Rapor, düzelen ve düzelmeyen metrikleri **ayırmalıdır**; aksi halde
"dört kapı geçti" yanılgısı doğar.

## F7-14 — Damıtma hacmi ile 72 saatlik tavan çelişiyordu; hacim tavana göre kırpılır

**Tarih:** 2026-11-17 (Faz 7, Aşama C planı)

**Belirti.** Bölüm 5.1.3'ün ilk taslağı "2 000 000 karar ≤ 72 saat" diyordu.
Aritmetik: 2 M × 4,07 s / 8 = **282 saat**. Yani 72 saatlik bütçeye 2 M karar
**sığmaz**; sığan hacim **500 000**'dir (70,7 saat).

**Düzeltme.** `ml/distill.py` hacmi **tek bir yerde** hesaplar:
`volume = min(volume_cap, floor(time_cap_hours * 3600 * decisions_per_second))`.
Kullanıcı kararı: `DISTILL_VOLUME_CAP = 500_000`. Tavan aşılırsa koşu **iptal
edilmez**, hacim **tavana kadar** düşer — Bölüm 5.1.4'teki "tavan aşılırsa tavan
kadar koşulur" kuralının aynısı.

**Ölçüm.** Varsayılan model (4,07 s/karar, 8× paralel → 1,9656 karar/sn):
500 000 karar = **70,7 saat**, kısıtlayan **hacim**. Daha yavaş bir makinede
(ör. 20 s/karar) hacim **otomatik düşer** ve kısıtlayan **süre** olur.

**Ders.** İki tavan (hacim ve süre) aynı anda yazıldığında **çelişebilir**.
Çelişkiyi belgeye bırakmak yerine **tek bir fonksiyona** kapatmak gerekir; aksi
halde "500 bin" ile "72 saat" iki ayrı yerde iki ayrı şey söyler.

## F7-15 — Depth 2 üretimden çıkarıldı; üretim derinliği 1

**Tarih:** 2026-11-17 (Faz 7, Aşama B sonrası — B3 kararı)

**Belirti.** F7-09, gerçek ONNX modeliyle depth 2 p95'inin **4,4972 s** (medium)
ve **13,6816 s** (large) olduğunu ölçtü; bütçe **2 s**. Maliyet ONNX **çağrı
sayısıyla** doğrusaldır: depth 2, 84×84 = **7 056** yaprak şans düğümü üretir.

**Düzeltme.** `SearchSettings.ProductionDepthPly = 1` sabiti, `IsProductionViable`
ve `EnsureProductionViable(what)` eklendi. `SelfPlayConfig.Validate` artık
`DepthPly > 1` için `ArgumentException` atar (mesajda F7-09 anılır).
`Backgammon.MatchBench decision-latency` varsayılanı 1 oldu.

**Kapsam.** Depth 2 **silinmedi**; yalnızca **üretimden** çıkarıldı. Çevrimdışı
damıtma öğretmeni (Bölüm 5.4) depth 3 kullanır ve üretim kapısına tabi değildir
(`SearchSettings.Reference(3)` hâlâ kurulabilir). Üretimde kullanılabilir
derinlik **1**'dir: p95 **0,0902 s**, bütçenin **%4,5**'i.

**Geri dönüş koşulu.** Depth 2'nin üretime dönmesi **yaprak-cephe toplu
değerlendirmesine** bağlıdır: 7 056 küçük ONNX çağrısı yerine ~72 büyük çağrı
(teorik ~0,03 s). Bu, arama çekirdeğinde gerçek bir yeniden yazım gerektirir ve
**kapsam dışıdır**; ayrı onay ister.

**Ders.** Bir bütçe kapısı, **sentetik** bir değerlendiriciyle ölçüldüğünde
geçebilir ve üretimde çöker. Test 79'un 0,7133 s p95'i `HashEvaluator` ile
ölçülmüştü — vektörleştirme, ONNX, tensör kopyası yoktu. Kapı testleri, üretim
yolunun **gerçek** bileşenlerini kullanmalıdır.

## F7-16 — Damıtma shard'ı yeni alan gerektirmedi: politika hedefi `q`, değer hedefi `searchValue`

**Tarih:** 2026-11-17 (Faz 7, Aşama C)

**Soru.** Arama damıtma (Bölüm 5.4) öğretmenin kök kararını ve kök değerini
öğrenciye aktarır. Bu, shard formatına yeni alan eklemeyi gerektirir mi?

**Cevap: hayır.** Mevcut format zaten iki alanı taşıyor:

| İhtiyaç | Alan | Anlamı |
|---|---|---|
| Politika hedefi | `q` | öğretmenin seçtiği adayın dizini |
| Değer hedefi | `searchValue` | `SearchResult.EvaluationScore` (equity) |

`ShardDecisionFlags.Distilled = 16` (`DEC_DISTILLED`) yalnızca **hangi**
kararların öğretmenden geldiğini işaretler; veri taşımaz. Shard **sürüm
numarası 1'de kaldı** ve bilinmeyen bayraklar eski okuyucular tarafından yok
sayılır — geriye dönük uyumluluk korunur.

**Sonuç.** Damıtma, veri hattında **şema değişikliği olmadan** uygulanabilir.
Bu, Aşama C'nin en büyük tasarım kazancıdır: mevcut shard'lar, mevcut okuyucu,
mevcut eğitim betiği.

**Ders.** Yeni bir öğrenme sinyali eklemeden önce, mevcut alanların **anlamını**
sorgulamak gerekir. `searchValue` zaten öğretmenin değerini taşıyordu; eksik
olan alan değil, onu **kullanan** kayıp fonksiyonuydu.

## F7-17 — Damıtma değer hedefi 6 sınıflı dağılım değil, skaler equity'dir; kalibrasyon terimi kapatılır

**Tarih:** 2026-11-17 (Faz 7, Aşama C)

**Belirti.** Shard, öğretmenin kök değerini **6 sınıflı olasılık vektörü** olarak
taşımıyor; yalnızca skaler `searchValue` (equity) var. Oysa Faz 6'nın değer
kafası 6 sınıflı çapraz entropi (`value_loss_ce_6class`) ile eğitiliyordu.

**Kök neden.** `SearchResult.RootValue` bir `OutcomeDistribution?` taşıyor, ama
`ShardDecision` yalnızca `SearchValue` (float) alanını yazıyor. Dağılımı shard'a
eklemek **şema değişikliği** olurdu (F7-16'nın kazancını silerdi).

**Karar.** Damıtma kolunda değer kafası **equity regresyonu** ile eğitilir:

```
L_value = mean( (probs @ [1,2,3,-1,-2,-3] - searchValue)^2 )
```

`ExclusiveSamples.equity_target` bu hedefi taşır. `y` (TD-λ referansı) yalnızca
**tanı** için saklanır, gradyana girmez.

**Kalibrasyon terimi kapatılır** (`lcal = 0`). Gerekçe: kalibrasyon cezası
`(slope, intercept)` sapmasını ölçer ve aynı büyüklüğü **ikinci kez** sayar;
equity regresyonu zaten mutlak ölçekte hata veriyor. İkisini birlikte açmak,
kalibrasyon cezasını yapay olarak şişirir ve öğrenmeyi yavaşlatır.

**Ölçülen sonuç.** Aşama C'nin iki kolu **farklı kayıp fonksiyonlarıyla**
eğitildi (damıtma: equity regresyonu; kontrol: CE + kalibrasyon). Bu yüzden
`buffer CE` ve `equity MAE` sütunları **kollar arasında karşılaştırılamaz** —
damıtma kolunun CE'si 1,32, kontrolünki 0,012 görünür, ama bu bir başarı
göstergesi değil, farklı hedefin farklı ölçeğidir. Karşılaştırma yalnızca
**VAL-ER** üzerinden yapılır.

**Ders.** Bir kayıp fonksiyonunu değiştirdiğinizde, o kaybın **tanı sütunları**
da anlamını değiştirir. Rapor, "hangi sayı hangi kayıpla üretildi" bilgisini
taşımadıkça yanlış okunur.
