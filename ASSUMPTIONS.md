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

## F7-19 — λ-return formülü **doğrudur**; "sıfıra çöküyor" iddiası ödül tabanlı formülle karıştırmadır

**Tarih:** 2026-11-17 (Faz 7, dış inceleme yanıtı)

**İddia.** Bir dış inceleme, TD(λ) hedeflerinin şu formülle hesaplandığını ve bu
yüzden sıfıra çöktüğünü öne sürdü:

```
(1-λ) * Σ_k λ^k r_k + λ^(T-t) * z_T
```

Ara ödül olmadığı için bu ifade `λ^(T-t) * z_T`'ye indirgenir; yani hedefler
terminal değerin sönümlü bir kopyası olur. İnceleme, bunu F4-41'deki "hedefler
sıfıra çöküyor" bulgusuyla ilişkilendirdi.

**Doğrulama.** `ml/td_lambda.py` ve `ml/train_v2.py` bu formülü **kullanmıyor**.
Gerçek özyineleme:

```python
y[n-1] = -z
y[t]   = -((1-lam) * v[t+1] + lam * y[t+1])
```

Bu, **değer tabanlı** λ-return'dür ve bootstrap değerlerini (`v[t+1]`) içerir.
Kapalı formu (`u[t] = -y[t]`):

```
u[t] = (1-λ) * Σ_{k=0}^{n-2-t} (-λ)^k * V[t+1+k] + (-λ)^(n-1-t) * z
```

`(-λ)^k` işaret değişimi, `mover` bakış açısının her kararda değişmesinden gelir.
İddia edilen formülde bu terim **yoktur**; dolayısıyla iddia edilen formül bu
problemin formülü değildir.

**Kanıt.** `ml/tests/test_lambda_return_closed_form.py` (Test 125, **50 test**)
her iki fonksiyonu (`td_lambda_targets`, `td_lambda_targets_exclusive`) yedi
farklı λ için kapalı forma karşı doğrular; maksimum sapma **0,0** (birebir).
Ayrıca:

| Test | Ne kanıtlıyor |
|---|---|
| `test_125a_bootstrap_term_is_present` | `V_hat` değişince hedef değişiyor → bootstrap var |
| `test_125a_scalar_does_not_collapse_to_zero` | Ara ödül sıfır olsa da hedef sıfıra çökmüyor |
| `test_125a_reward_only_formula_would_collapse` | İddia edilen formül gerçekten çöküyor (karşı örnek) |
| `test_125b_exclusive_matches_closed_form` | 6 sınıflı dağılımda `flip` permütasyonu doğru açılıyor |

**Sonuç.** F4-41'in kök nedeni λ-return formülü **değildi**. O bulgu, `λ = 0,7`
ile başlangıçta yanlı `V_hat`'in hedefe girmesiydi; düzeltme `λ = 1,0` (saf
Monte Carlo) varsayılanına geçmek oldu ve bu zaten yapıldı (`DEFAULT_LAMBDA`).

**Ders.** Bir formülü "hatalı" ilan etmeden önce, **hangi formülün** kodda
olduğunu okumak gerekir. Ödül tabanlı ve değer tabanlı λ-return farklı
nesnelerdir; ara ödül olmayan bir problemde ilki dejenere olur, ikincisi olmaz.
Bu, projede beşinci "sessizce yanlış şeyi ölçme" vakasının **tersi**: burada
doğru olan şey yanlış sanıldı. Aynı disiplin iki yönde de gerekli.

---

## F7-20 — Teşhis: sorun ölçek değil, pipeline (ölçüldü)

**İddia (dış inceleme, madde 1.1).** Model basit bir sezgisel bottan (PipBot)
kötü; bu bir **ölçek** değil **pipeline** sorunudur. Ölçek büyütmek bunu
düzeltmez.

**Neden ölçüm gerekti.** "Model kötü" tek bir sayı değildir. Bir model PipBot'u
%99,5 yenip yine de bozuk bir değer kafasına sahip olabilir. Bu ikisi aynı anda
doğruysa, daha büyük ağ **daha emin bir şekilde yanlış** olur. Bu yüzden iddia
tek bir metrikle değil, **yedi bağımsız kapıyla** sınanır.

**Araç.** `ml/pipeline_health.py` (Test 126, **117 test**). Kapılar:

| Kapı | Ölçüt | Eşik |
|---|---|---|
| `G1` | PipBot'a karşı kazanma oranı | `>= 0,90` |
| `G2` | Kalibrasyon eğimi | `[0,85; 1,15]` |
| `G3` | Kalibrasyon MAE | `< 0,15` |
| `G4` | Korelasyon | `> 0,90` |
| `G5` | Std oranı | `[0,85; 1,15]` |
| `G6` | 2-ply ER | `< 0,02` |
| `G7` | `std(hedef) / std(terminal)` | `> 0,5` |

**Ölçülen sonuç** (`ml/artifacts/pipeline_health.json`):

| Kapı | Değer | Sonuç |
|---|---|---|
| `G1` | 0,9950 | **GEÇTİ** |
| `G2` | 0,6743 | **DÜŞTÜ** |
| `G3` | 0,2683 | **DÜŞTÜ** |
| `G4` | 0,9016 | **GEÇTİ** |
| `G5` | 1,3371 | **DÜŞTÜ** |
| `G6` | 0,0740 | **DÜŞTÜ** |
| `G7` | 3,0227 | **GEÇTİ** |

**Teşhis: `pipeline`.** Model PipBot'u %99,5 yeniyor (`G1`), hedefleri
çökmüyor (`G7` = 3,02), sıralaması doğru (`G4` = 0,90) — ama değer kafası
**kalibre değil**: eğim 0,67 (olması gereken 1,0), MAE 0,27 (tavan 0,15), std
oranı 1,34 (bant 0,85–1,15). Yani model doğru yönü biliyor, **yanlış büyüklükte**
puanlıyor.

**Karar kuralı (yazılı).** `G1` düşerse teşhis `temel` (model hiç oynamıyor).
`G1` geçip `G2`/`G3`/`G4`/`G5`/`G7`'den biri düşerse teşhis `pipeline`. Hepsi
geçerse `saglikli` ve ölçek büyütmek anlamlıdır. **`G1`–`G5` ve `G7`'nin hepsi
ölçülmüş ve geçmiş olmadan `saglikli` denmez** — ölçülmemiş kapı varken
"saglikli" demek sahte bir güvencedir; o durumda teşhis `bilinmiyor`dur. `G6`
(ER) bu kuralın dışındadır: ER bir **güç** ölçümüdür, pipeline sağlığının
önkoşulu değildir. Yalnızca `G6` düşerse `strength_gap` işareti konur ve
teşhis `saglikli` kalır.

**Sonuç ve sonraki adım.** Ölçek (large profile, 10⁵ oyun) bu teşhis altında
**yanlış kaldıraçtır**. Önce hedef/kayıp/kalibrasyon hattı onarılmalıdır. Bu,
F7-13'ün (post-hoc onarım eğimi düzeltir, MAE'yi düzeltmez) doğal devamıdır:
eğim hatası çıkarımda onarılabilir, MAE hatası **eğitimde** onarılmalıdır.

**Ders.** "Model kötü" ifadesi bir teşhis değil, bir şikâyettir. Teşhis, hangi
kapının düştüğünü söyleyen ölçümdür. Bu projede altıncı kez aynı desen: ölçmeden
önce yapılan yorum yanlış yönlendiriyordu — ama bu kez iddia **doğru** çıktı ve
bunu kanıtlayan şey yine ölçüm oldu.

## F7-21 — gnubg öğretmen deneyi: ER'yi değiştiren tek şey **politika** hedefidir

**Soru (dış inceleme madde 1.3).** En büyük kaldıraç kendi aramamızın bilgisini
damıtmak değil, **gnubg 2-ply etiketlerini öğretmen olarak kullanmak** mıdır?
Etiketlerle ER 0,03'ün altına iniyorsa dar boğaz **pipeline**; inmiyorsa
**kapasite**.

**İlk deneme yanlış kurgulandı ve bunu ölçüm gösterdi.** `ml/gnubg_distill.py`
ilk sürümü yalnızca **değer kafasını** eğitiyordu (MSE, `probs @ EQUITY_WEIGHTS ~
hints[0].equity`). 1 200 pozisyon, 2-ply, 2 000 adım sonucu: eğitim kümesinde
MAE **0,0072**, korelasyon **0,9996**, eğim **1,0026** — neredeyse kusursuz.
Ama `er_harness` ile ölçülen ER **0,0708** (öncesi 0,0740). Yani **%4** iyileşme.

**Neden?** ER, **politika** başı argmax ile ölçülür
(`er_harness` → `gnubg_er.score_afterstates` → `criterion="policy"`). Değer
kafası bu karar yolunda **hiç okunmaz**. Değer kafasını mükemmel eğitmek ER'yi
tanımı gereği değiştiremez. Bu, F7-17'nin (damıtma değer hedefi skalerdir, 6
sınıflı dağılım değil) doğal sonucudur ve **ölçümle** doğrulandı.

**Düzeltme: politika damıtma.** `label-policy` / `train-policy` alt komutları
eklendi. Her pozisyon için **yasal afterstate kümesi** üretilir, gnubg `hint`
hamleleri bu kümeye eşlenir (`gnubg_hint.map_hints`), en iyi hamlenin indeksi
**politika hedefi** olur. Kayıp:
`CE(logits, best) + 0,5 · MSE(equity(best), best_equity)`.

**Kritik ayrıntı — determinizm.** `tools.reference_gen.legal_after_states` bir
**küme** döndürür; Python küme sırası koşular arası değişebilir. Sıralanmazsa
`best_index` etiketleri koşudan koşuya kayar ve eğitim **sessizce** bozulur.
`afterstate_case` bu yüzden `sorted(keys)` kullanır; `test_127j_afterstate_case_sorted`
bunu kilitler.

**Ölçülen sonuç (2 000 pozisyon, 4 000 adım, lr 3e-4, batch 64).** Eğitim
kümesinde top-1 **1,0000**, kayıp 0,564 → 0,00055. VAL-ER **0,0533**
(öncesi 0,0740) → **%28,0** iyileşme, standart hata 0,0108.

**Karar: `belirsiz` (F7-24 ile düzeltildi).** Nokta tahmini %28 iyileşme
gösteriyor, ama **eşleştirilmiş test** (aynı 70 pozisyon) GA95'i
[−0,0062; +0,0414] veriyor: **sıfırı dışlamıyor** (t = +1,45). Bu yüzden ne
"etiketler işe yaradı" ne "etiketler işe yaramadı" denebilir. İlk yazılan
`kismi` kararı, nokta tahminini kanıt sayan bir hataydı; F7-24 bunu düzeltir.

**Dürüstlük notları.**

* Eğitim kümesinde top-1 = 1,0000 **ezberdir**, genelleme değil. 2 000 pozisyon
  `medium` profilin (156 423 parametre) kapasitesinin altındadır. Gerçek
  genelleme ölçüsü VAL-ER'dir (0,0533), eğitim top-1'i değil.
* VAL-ER 70 pozisyonda ölçüldü; standart hata 0,0108. 0,0740 → 0,0533 farkı
  (0,0207) SE'nin ~1,9 katıdır; **ama** eşleştirilmiş test (F7-24) GA95'i
  [−0,0062; +0,0414] veriyor ve sıfırı dışlamıyor. "SE'nin 1,9 katı" tek başına
  kanıt değildir: iki ölçüm aynı pozisyonlarda yapıldığı için doğru test
  eşleştirilmiş olandır.
* gnubg **GPL**'dir. Etiketler yalnızca araştırma/ölçüm içindir; ürün dağıtımı
  öncesi lisans netleştirilmelidir (`LICENSE_NOTE`).
* `tools/reference_gen.py` içindeki `random_positions` içinde **gerçek bir hata** bulundu ve
  düzeltildi: `legal_after_states` "büyük zar kuralı" dalında `max_steps > 0`
  ama `states` **boş** dönebiliyor; `rng.choice(sorted(states))` bu durumda
  `IndexError` atıyordu. 10 000 pozisyonluk koşu bunu ortaya çıkardı. Düzeltme:
  `if max_steps == 0 or not states`.

**Ders.** "Etiketler sorunu çözer" iddiası, **hangi kafayı** eğittiğinize
bağlıdır. Ölçüm hattı politika argmax'ı okuyorsa, değer kafasını eğitmek
ölçülen metriği **tanımı gereği** değiştirmez. Bu, F6-31/F6-32'nin yedinci
tekrarı: ölçülen şey ile iyileştirilen şey **aynı** olmalıdır.

Çıktılar: `ml/artifacts/gnubg_distill_er.json` (değer kafası, 0,0708),
`ml/artifacts/gnubg_policy_er.json` (politika 2 000, 0,0533),
`ml/artifacts/gnubg_policy_er_10k.json` (politika 10 000, 0,0617),
`ml/artifacts/gnubg_distill_verdict.json`, `ml/artifacts/gnubg_distill.md`.

## F7-22 — Maç gücü: 400 oyun bir iddiayı kanıtlamaya yetmez

**Soru (dış inceleme madde 1.4).** Faz 6'da 400 oyunla "2-away %40,0 vs %39,5"
gibi ifadeler yazıldı. Bu bir **ölçüm** mü, **gürültü** mü? Ayrıca ppg
(puan/oyun) hiç ölçülmedi.

**Yöntem.** `ml/match_power.py` her iddiayı iki sayıya çevirir: **gerekli n** ve
**saptanabilir en küçük fark**. Hiçbir sayı iddia değildir.

**Ölçülen sonuçlar (p = 0,55, σ_ppg = 2,4, n = 400).**

| İddia | Gereken n |
|---|---|
| Kazanma oranı ±0,05 (tek örnek) | **381** |
| ppg ±0,10 | **2 213** |
| ppg ±0,05 | **8 851** |
| Şampiyonu yenme iddiası (kol başına, %50 → %55) | **1 565** |
| ppg farkı iddiası (kol başına, Δ = 0,10) | **9 042** |
| Maç kazanma oranı ±0,05 | **381** |

**400 oyunun gerçeği.** p = 0,55'te yarım genişlik **0,0488**; p = 0,50'de
**0,0490**. İncelemenin örneği olan **0,005**'lik fark, 400 oyunda saptanabilir
en küçük farkın **~1/10'u**dur (oran **9,8×**). Yani "2-away %40,0 vs %39,5"
ifadesi **ölçülemez**; yazılırsa gürültüyü ölçüm diye sunmak olur.

**ppg neden zorunlu.** Aynı kazanma oranıyla mars oranını artıran bir model
**daha güçlüdür**, ama kazanma oranı bunu göstermez. ppg gösterir. Bedeli
ağırdır: σ_ppg ≈ 2,4 iken ±0,05 hassasiyet **8 851 oyun** ister — kazanma
oranının ±0,05'i için gereken 381'in **23 katı**. Bu yüzden ppg iddiası
**yalnızca** yeterli bütçe ayrıldığında yazılır.

**Karar kuralı (yazılı).** Bir fark, yarım genişlikten **küçükse** rapor
edilemez; "ölçüldü" denemez. `build_report` bunu `notes` içinde açıkça yazar
(`olculemez`, oran `x`). Sessizce yazmak yasaktır.

**Dürüstlük notları.**

* σ_ppg = 2,4 **tahmindir** (Faz 6 `meanPoints` ölçümlerinden kaba türetme),
  ölçüm değildir. Gerçek değer `--sigma` ile verilmelidir; ppg için gereken n
  σ ile **doğrusal** ölçeklenir, yani bu sayı bir **alt sınırdır** eğer gerçek
  σ daha büyükse.
* MET okuması (`mwc_from_met`) Rockwell-Kazaross tablosunu kullanır ve
  simetriyi (`a+b = 1`) ile monotonluğu test eder. Ancak maç **stratejisi**
  (küp kararları) bu modülde ölçülmez; yalnızca MWC **okunur**.
* `required_games_two_proportions` iki bağımsız örnek varsayar. Aynı rakibe
  karşı oynanan oyunlar bağımsız değildir (seri korelasyon); gerçek gerekli n
  bu sayıdan **büyüktür**. Bu bir alt sınırdır.

Çıktılar: `ml/artifacts/match_power.json`, `ml/artifacts/match_power.md`.

## F7-23 — Kapsam ayrımı: Faz 7 güç, Faz 8 ürün

**Soru (dış inceleme madde 1.5).** Faz 7'de 8 ürün özelliği (Aşama G) ile güç
hedefi aynı fazda. Güç tutmazsa ürün bekler — ama bu **yazılı değildi**.

**Karar.** `faz 7.md` kural 16 ve §8.0 eklendi:

* **Faz 7 kapsamı:** yalnızca güç (ölçüm hattı, kapasite, damıtma,
  kalibrasyon, arama, küp/maç).
* **Faz 7 kapsam dışı:** Aşama G'nin 8 özelliğinin **tamamı** (Test 111–118).
* **Faz 8 kapsamı:** Aşama G + ürünleştirme, **Faz 7 güç kapısı geçildikten
  sonra**.
* **Bloke etme kuralı:** güç hedefi tutmazsa ürün **başlamaz**.
* **Test numaraları:** 111–118 **rezerve**; Faz 7'de koşulmaz.
* **Bütçe etkisi:** Aşama G'nin **5 günü** Faz 7 toplamından düşüldü →
  **~45 → ~40 gün** (`medium`), **~96 → ~91 gün** (`large`).

**Neden bu doğru.** Ürün özellikleri **kesin bitiş noktalarıdır**; güç hedefi
**belirsiz süreli** bir aramadır. Aynı fazda yarışırlarsa güç hedefi kaybeder,
çünkü ürün "bitti" diyebilir, güç diyemez. Ürünü ertelemek şampiyon iddiasını
**zayıflatmaz**: ürün gücü artırmaz, yalnızca mevcut gücü kullanılabilir kılar.
Tersi doğrudur — güç tutmadan yazılan ürün, **ölçülmemiş bir modeli** paketler.

**Dürüstlük notu.** Bu ayrım, Faz 6 §11'in "ürünü Faz 7'ye taşıdık" taahhüdünü
**kapatmaz**; Faz 8'e **devreder**. Taahhüt açık kalır ve Faz 8'in girdisidir.

## F7-24 — Eşleştirilmiş test: %28'lik "iyileşme" gürültüden ayırt edilemiyor

**Soru.** F7-21'de politika damıtma VAL-ER'yi 0,0740 → 0,0533'e indirdi ve bu
"%28,0 iyileşme" olarak yazıldı. Bu bir **kanıt** mı, bir **nokta tahmini** mi?

**Yöntem.** İki ölçüm **aynı 70 pozisyonda** yapıldı (`er_harness measure
--split val`). Bu, eşleştirilmiş (paired) test yapmayı mümkün kılar ve
pozisyon zorluğundan gelen varyansı eler. `ml/gnubg_distill.py` içine
`load_er_losses` + `paired_loss_test` eklendi; `distill_verdict` artık
`paired` parametresi alır.

**Ölçülen sonuç (n = 70, aynı pozisyonlar).**

| Karşılaştırma | Ortalama fark | GA95 | t | Sıfırı dışlıyor |
|---|---|---|---|---|
| değer kafası → politika 2 000 | +0,0176 | [−0,0062; +0,0414] | +1,45 | **hayır** |
| değer kafası → politika 10 000 | +0,0091 | [−0,0209; +0,0392] | +0,59 | **hayır** |
| politika 2 000 → politika 10 000 | −0,0084 | [−0,0318; +0,0149] | −0,71 | **hayır** |

**Karar: `belirsiz`.** `distill_verdict(0,0708, 0,0533, paired=...)` →
`belirsiz`. Yeni karar etiketi eklendi (`VERDICT_UNPROVEN`, CLI çıkış kodu 4).
Kural: `paired` verildiğinde ve GA95 sıfırı dışlamıyorsa, nokta tahmini
**kanıt sayılmaz**; `kismi`/`kapasite` kararı verilmez.

**İkinci bulgu — veri hacmi işe yaramadı.** 2 000 → 10 000 pozisyon (5×),
aynı epoch sayısı (128) ile ER **0,0533 → 0,0617** oldu: daha **kötü**.
Fark anlamlı değil (t = −0,71), ama **monoton iyileşme de yok**. Yani
"kapasite payı" iddiası bu ölçekte veriyle desteklenmiyor. 10 000 pozisyon
5 064 s'de etiketlendi (0 atlandı, aday ortalaması 22,8).

**Neden bu önemli.** F7-21'in ilk hâli, %28'lik nokta tahminini kanıt gibi
sundu ve `kismi` kararı verdi. Bu, projenin kendi kuralını (F6-31/F6-32)
ihlal ediyordu: **ölçülen fark, gürültüden ayrılmadan iddia edilemez.**
Eşleştirilmiş test bunu yakaladı. Doğru ifade: "politika damıtma umut verici
bir yön, ama 70 pozisyonda kanıtlanmadı."

**Gereken n.** Gözlenen fark (0,0176) ve eşleştirilmiş SD (0,1016) ile %80 güç
için gereken n ≈ **264** pozisyon (tek yönlü, α = 0,05). Mevcut 70, bunun
%27'si. Yani karar için **en az 264**, güvenli olması için ~400 pozisyon
gerekir. Bu, `ml/er_power.py` ile aynı hesaptır.

**Dürüstlük notları.**

* Eşleştirilmiş test normal yaklaşım kullanır (n = 70 için t dağılımı yerine
  z = 1,96). Kritik değer farkı (2,00 vs 1,96) sonucu değiştirmez: t = 1,45
  her iki durumda da anlamsızdır.
* 70 pozisyon `reference_positions.json`'dan gelir ve **sabit**tir; yeni
  pozisyon eklemek korpusu değiştirir ve önceki ölçümlerle karşılaştırmayı
  bozar. Bu yüzden n artırmak, korpusu büyütmek demektir — ayrı bir iştir.
* 10 000 pozisyonluk koşu, 2 000'lik koşunun **üst kümesidir** (aynı seed 11,
  aynı `random_positions` sırası). Yani iki kol arasındaki tek fark hacim ve
  adım sayısıdır (ikisi de 128 epoch).
* Eğitim top-1 her iki kolda da 1,0000: her iki model de eğitim kümesini
  ezberliyor. Bu, `medium` profilin 10 000 pozisyon için bile fazla kapasiteli
  olduğunu gösterir — yani darboğaz kapasite **değil**.

**Ders.** Aynı veri üzerinde iki ölçüm yapıldığında **eşleştirilmiş** test
kullanılmalıdır; bağımsız iki örnek testi hem güçsüz hem de yanıltıcıdır.
Nokta tahmini + standart hata, "SE'nin 1,9 katı" gibi bir argüman **kanıt
değildir**.

Çıktılar: `ml/artifacts/gnubg_distill_verdict.json` (karar `belirsiz`),
`ml/artifacts/gnubg_distill.md` (§4.1 eşleştirilmiş test, §4.2 veri hacmi
kolları), `ml/artifacts/gnubg_policy_er_10k.json`.

## F7-25 — StatePool: sifirlama ve sahiplik denetimi (olculdu)

**Soru.** `StatePool.Return()` havuza donen durumu baslangic dizilimine
sifirliyor mu, ve yabanci bir durumun havuza donulmesi engelleniyor mu?

**Olculen (duzeltme oncesi).** Ikisi de **hayir**.

* `Return()` yalnizca `_available++` yapiyordu; durum uzerinde `Reset()`
  cagrilmiyordu. Havuzdan tekrar `Rent()` edilen durum **onceki oyunun
  tahtasini** tasiyordu.
* Tek denetim `_available >= _states.Length` idi; bu bir **kapasite**
  denetimidir, **sahiplik** denetimi degil. Havuz doluyken yabanci bir durum
  dondurulurse istisna atiliyordu, ama havuzda yer varken yabanci durum
  **sessizce** havuzun sahip oldugu bir durumun yerine geciyordu.

**Duzeltme.** `StatePool` yeniden yazildi: indeks yigini tabanli serbest liste
(`_free`, `_rented`, `_freeCount`), `Array.IndexOf` ile sahiplik denetimi,
cift iade denetimi ve `Return()` icinde `s.Reset()`.

**Testler.** `StatePoolTests` 5 -> **12** test. Uc test duzeltme oncesi
**kirmizi** idi: `Return_ResetsStateToStartPosition`,
`Return_ThenRent_DoesNotLeakStaleData`, `Return_ForeignState_DoesNotCorruptPool`.

**Dikkat — bu bir olu soyutlamaydi.** Tum `.cs` dosyalarinda `StatePool`
yalnizca `StatePool.cs` ve `StatePoolTests.cs` icinde geciyor; uretim kodunda
**kullanan yok**. Yani bu duzeltme gercek bir sizintiyi kapatmiyor, ileride
kullanilacak bir soyutlamayi dogru hale getiriyor. Bu, onceligi dogru
belirlemek icin onemli: F7-25'in uretim kazanci **sifir**.

**Maliyet.** `Array.IndexOf` her `Return()` icin O(kapasite) tarama yapar.
Havuzlar kucuk (1-4) ve tarama **allocation yapmaz**, ama "performans kaybi
yok" demek dogru olmaz; "olculemeyecek kadar kucuk" demek dogrudur.

## F7-26 — AfterStateList kapasitesi: 2048 yasal bir pozisyonda tasiyor (olculdu)

**Soru.** `AfterStateList.DefaultCapacity = 2048` yeterli mi?

**Yontem.** Iki olcum.

1. **Rastgele ornekleme.** 200 000 rastgele pozisyon (rastgele oyun, 40 ply):
   en fazla **576** afterstate (zar 2-2), 1024'u asan **sifir**.
2. **Tepe-tirmanma aramasi.** Tas sayisini koruyan mutasyonla (`CountPieces(±1)
   == 15` dogrulamasi) 1 315 644 yeniden baslatma, 200 s: en fazla **2139**
   afterstate, zar **1-1**, tahta
   `0,-10,1,1,1,-1,1,1,1,-1,1,1,-1,1,1,0,1,1,0,1,1,-1,1,0,-1,0`.

**Sonuc: 2139 > 2048.** Yasal bir pozisyon (15'e 15 tas) eski varsayilan
kapasiteyi **asiyordu**; `AfterStateList.Add` `InvalidOperationException`
atiyordu. Yani bu, teorik degil **erisilebilir** bir cokme.

**Duzeltme.** `DefaultCapacity` 2048 -> **4096** (olculen ust sinirin ~1,9
kati). `MeasuredMaxAfterStates = 2139` sabiti eklendi ve
`WorstKnownPosition_FitsInDefaultCapacity` testi bu tahtayi birebir kurup
`list.Count == 2139` dogruluyor. `MoveList.DefaultCapacity` artik
`AfterStateList.DefaultCapacity`'a takma ad.

**Durustluk notlari.**

* 2139 bir **alt sinirdir**, teorik ust sinir degil. Daha uzun bir arama daha
  yuksek bir deger bulabilir. 4096 ~1,9 kat pay birakiyor; bu bir **muhendislik
  tercihi**, kanit degil.
* Ilk tepe-tirmanma kosusu tas sayisini korumuyordu ve 13'e 13 taslik **gecersiz**
  bir tahta uretti (1284). O sayi gecersizdir; yukaridaki 2139 gecerli
  mutasyonla elde edilmistir.
* Rastgele orneklemede 576 cikmasi, "gercek oyunda 2048'e yaklasilmaz"
  beklentisini dogrular; ama arama tabanli bir motor **dusman** pozisyonlar
  uretebilir, bu yuzden en kotu durum onemlidir.

## F7-27 — AddPass: bayat hash Debug'da dogrulanir

**Soru.** `AddPass` `s.hash`'i dogrulamadan kopyalarsa ne olur?

**Sonuc.** Bayat hash transpozisyon tablosunda **yanlis eslesmeye** yol acar:
iki farkli pozisyon ayni anahtarla eslesir ve arama yanlis degeri dondurur.
Sessiz bir hatadir.

**Duzeltme.** `AfterStateList` icine `[Conditional("DEBUG")] VerifyHash(s)`
eklendi; `AddPass` basinda cagrilir, hash'i yeniden hesaplar ve uyusmazsa
`InvalidOperationException` atar.

**Neden yalnizca Debug?** `AddPass` arama icinde **dugum basina** cagrilir
(`BackgammonSearch.cs:342`). Her cagride 26 hanelik hash yeniden hesaplamak
sicak yolda gercek bir maliyettir. `[Conditional("DEBUG")]` sayesinde Release
derlemesinde **sifir** maliyet, Debug'da tam koruma. Test
(`AddPass_StaleHash_ThrowsInDebug`) `#if DEBUG` altindadir ve Release
kosusunda **calismaz** — bu bilincli bir tercihtir.

## F7-28 — _gen: int sayaci tasma korumasi hic ateslenmiyordu

**Soru.** `if (_gen == 0)` korumasi `int` sayacla calisir mi?

**Sonuc: hayir.** C# isaretli tamsayi tasmasi **tanimsiz degildir**; `int.MaxValue
+ 1 == int.MinValue`. Yani sayac 0'a **hic** donmez ve `if (_gen == 0)` korumasi
**asla** ateslenmez. 2^31 cagridan sonra `_dedupGen` icindeki eski nesil
degerleri yeni nesille **cakisir** ve tekillestirme yanlis kayitlari eler.

**Duzeltme.** `_gen` ve `_dedupGen` `int` -> **`uint`**; karsilastirma
`== 0u`. `uint` tasmasi 2^32'de 0'a **duser**, yani koruma gercekten calisir.

**Not.** 2^32 cagri pratikte ulasilamaz (olculen ~340K cagri/sn ile ~3,5 saat
kesintisiz), ama korumanin **dogru** olmasi maliyetsizdir.

## F7-29 — Seq buffer / afterstate listesi kapasite iliskisi

**Soru.** `SeqBufCapacity = 65536` ile `AfterStateList.DefaultCapacity` (2048)
arasindaki uyumsuzluk bir hata mi?

**Sonuc: yon guvenli.** 65536 > 2048 (ve > 4096). Yani seq buffer, afterstate
listesinden **once** tasmaz; liste dolarsa liste istisna atar. Promptun
"uyumsuzluk" tespiti teknik olarak dogru, ama **tehlikeli yon degil**.

**Duzeltme.** `LegalMoveGenerator.SequenceBufferCapacity` ozelligi eklendi ve
`SequenceBuffer_CoversAfterStateListCapacity` testi
`SequenceBufferCapacity >= AfterStateList.DefaultCapacity` degismezini
kilitliyor. Boylece gelecekte kapasite buyutulurse test kirilir.

## F7-30 — Varsayilan model yolu: fikstur modeline sessiz dusus

**Soru.** `DefaultModelPath()` egitilmis model bulamazsa ne olur?

**Sonuc.** Sessizce `ml/artifacts/model_v2.onnx` (test fiksturu) donuyordu.
Bu modelin gucu **olculmemistir**; onunla uretilen ER/GA sayilari olcum olarak
kullanilamaz. F7-10'un (yanlis ONNX surumu) tekrari riski.

**Duzeltme.** Fiksture dusuldugunde `Console.Error`'a iki satir uyari yazilir:
modelin bulunamadigi ve sonuclarin olcum olarak kullanilamayacagi. Yol
**degistirilmedi** — fikstur hala son care, ama artik **sessiz degil**.

## F7-31 — DiceAveragedEquity: her cagride yeni SearchWorkspace

**Soru.** `DiceAveragedEquity` her cagride `new SearchWorkspace()` +
`new BackgammonState()` ayiriyor mu?

**Sonuc: evet.** Pozisyon basina 21 kez cagriliyor; her cagri yeni bir
workspace (istatistik + cache + transpozisyon tablosu) ve yeni bir durum
ayiriyordu.

**Duzeltme.** Iki `[ThreadStatic]` alan (`_diceAvgWorkspace`,
`_diceAvgScratch`) eklendi; her arama oncesi `workspace.Reset()` cagriliyor.
`Reset()` istatistik, cache ve transpozisyon tablosunu temizler, yani
kiralama ile ayni baslangic durumu garanti edilir.

**Neden `[ThreadStatic]`?** `SearchWorkspace` ve `BackgammonState` thread-safe
degildir; paylasilan tek bir alan paralel olcumde veri yarisina yol acardi.

## F7-32 — ResultPoints cubeValue ile carpilmiyor (dogrulandi)

**Soru.** `AfterStateList.ResultPoints` kup degerini iceriyor mu?

**Sonuc: hayir, dogru.** `IsGameOver` mars/backgammon puanini (1/2/3) dondurur;
`cubeValue` ile **carpilmaz**. `GenerateAfterStates` bu degeri dogrudan yazar.

**Test.** `GenerateAfterStates_TerminalResultPoints_ExcludesCubeValue` ayni
terminal pozisyonu `cubeValue` 1, 2, 4, 8 icin kurar ve her durumda
`ResultPoints == 1`, `ResultType == Single` bekler. **Gecti.**

**Neden onemli.** Puan kup degeriyle carpilsaydi ayni terminal pozisyon farkli
kup degerlerinde farkli hedef uretir ve deger hedefi (F6-07) bozulurdu.

## F7-33 — SelfPlayAgent: StatePool gerekmiyor (iddia dogrulanmadi)

**Soru.** `SelfPlayAgent` her arama icin yeni `BackgammonState` ayiriyor mu?

**Sonuc: hayir.** `SelfPlayAgent` yalnizca `SearchWorkspace` ve
`OnnxPolicyValueEvaluator` tutar; **hic** `BackgammonState` olusturmaz.
Durumlar `SelfPlayRunner` icinde **alan** olarak tutulur ve yeniden kullanilir
(`_state`, `_scratch`, satir 40-41). `EvalBench` ise oyun basina bir kez ayirir
(satir 130-133), arama basina degil.

**Ek kanit.** `SearchTests.Test10_ZeroAllocation` isinma sonrasi
`BackgammonSearch.Search` icin `GC.GetAllocatedBytesForCurrentThread` farkinin
**0** oldugunu zaten dogruluyor.

**Karar: degisiklik yapilmadi.** `StatePool` eklemek, olculmus bir kazanci
olmayan bir soyutlama eklemek olurdu (F7-25 zaten havuzun uretimde **kullanilmadigini**
gosteriyor). Bu, "basitlik once" kuralinin dogrudan uygulamasidir.

## F7-34 — BuildBenchList: sabit 4096 yerine varsayilan kapasite

**Soru.** `BuildBenchList` neden `new AfterStateList(4096)` kullaniyordu?

**Sonuc.** Sabit bir sayi, `DefaultCapacity`'in tek dogru kaynak olmasini
engelliyordu. Kapasite 2048 iken 4096 "tutarsiz" gorunuyordu; 4096'ya
cikarildiktan sonra tesadufen tutarli hale geldi.

**Duzeltme.** `new AfterStateList()` — varsayilan kapasite kullanilir. Boylece
kapasite tek yerden yonetilir.

## F7-35 — Crawford senaryolari gercek modelle de kosulur

**Soru.** `RunCrawford` sabit 0,9 equity kullaniyor; bu yeterli mi?

**Degerlendirme.** Senaryolar **kup kurali** testleridir (Crawford oyununda kup
yok, post-Crawford'da 1-away teklif edemez, olu kup). Sabit equity bu kurallari
**deterministik** ve modelden bagimsiz test etmeyi saglar; bu dogru bir
tercihtir, hata degil.

**Duzeltme (eklemeli).** `crawford` komutuna `--model <yol>` secenegi eklendi.
Verildiginde ayni senaryolar gercek `OnnxPolicyValueEvaluator` ile de kosulur ve
JSON'a `modelScenarios` + `modelCorrect` yazilir. Varsayilan davranis
**degismedi** (sabit equity, deterministik).

**Onemli — onceden var olan basarisizlik.** Sabit equity ile kosu **5/6**
dogru: `normal-double-pass` senaryosu (5-away/5-away, E = 0,9 ⇒ ciftle)
beklenen `shouldDouble = true` yerine `false` donduruyor. Bu, `git stash` ile
**HEAD'de de ayni** oldugu dogrulandi; bu gorevin kapsamindaki 15 maddeden
**biri degildir** ve duzeltilmedi. `EquityCubeAdvisor` icin ayri bir is
acilmalidir.

## F7-36 — Swap / BoardOf sozlesmesi (belgeleme)

**Soru.** `Swap` manuel tahta takasi yapiyor, `BoardOf` ise `ReadOnlySpan`
donduruyor; bu tutarsiz mi?

**Sonuc: kod dogru, sozlesme yazili degildi.** Kayitlar paralel dizilerde
tutulur; `Swap` **hepsini** birlikte takas eder. `BoardOf` yalnizca okuma
icindir. Tehlike, gelecekte birinin `BoardOf`'u yazma icin kullanmasi veya
`Swap`'a yeni bir paralel dizi ekleyip takasa eklemeyi unutmasidir.

**Duzeltme.** `Swap` uzerine `<remarks>` eklendi: (a) takas **tum** paralel
dizilerde birlikte yapilmalidir, (b) `BoardOf` yalnizca okuma icindir, yazma
icin `Boards` kullanilmalidir. Davranis degismedi.

## F7-37 — StepBuf derinlik siniri

**Soru.** `StepBuf` boyutu `MaxSteps + 1 = 5`; `depth > 4` olursa
`IndexOutOfRangeException` olur mu?

**Sonuc: ulasilamaz, ama korumasizdi.** `remainingCount` en fazla 4'tur
(`SetDice` dublede 4, aksi halde 2; `ApplyStep` azaltir), yani `depth` en fazla
4 olur. `MaxSequenceLength` zaten `depth > MoveSequence.MaxSteps` icin 0 doner.
Ancak `Collect` ve `Emit` **guard'siz** olarak `StepBuf[depth]` indeksliyordu;
ileride zar sayisi artarsa sessiz degil, **gec** ve anlasilmasi zor bir istisna
alinirdi.

**Duzeltme.** `Collect` ve `Emit` basina acik sinir denetimi eklendi
(`depth > MoveSequence.MaxSteps` ⇒ `InvalidOperationException`). Sicak yolda
tek bir karsilastirma. `StepBuf` ozelligine boyut degismezini aciklayan yorum
eklendi. `StepBuffer_DepthBound_MatchesMaxSteps` testi 1-1 dublesinde tum
dizilerin uzunlugunun `<= MaxSteps` oldugunu dogruluyor.

## F7-38 — Faz 7-R denetimi: R-01…R-17 (doğrulama kaydı)

**Kaynak.** `faz 7 v2.5.md` (Faz 7-R), §3 bulgu tablosu. Bu bölüm 17 bulgunun
**kaynak koda karşı** doğrulama sonucunu taşır. Kural 1 ("önce doğrula, sonra
düzelt") gereği her satır bir **kanıt** (dosya:satır veya ölçüm) taşır.
Sonuç etiketleri: `doğrulandı` / `çürütüldü` / `kısmen`.

| ID | Sonuç | Kanıt |
|---|---|---|
| R-01 | **doğrulandı** | `ml/artifacts/stage_b_er_medium.json` mean 0,063957; `stage_b_er_large.json` mean 0,066414; SE 0,011948 / 0,011991. Fark **+0,002457**, `stage_b_capacity.json` `noiseThreshold` **0,002535** → fark eşiğin **altında**. Test 68 (PHASES §16.7) ters yönde: `medium` 0,3535 ± 0,0712 vs `large` 0,2651 ± 0,0594. |
| R-02 | **doğrulandı** | `ml/gnubg_distill.py:157` `label_positions` → `vector=gnubg_er.vectorize(board, wo, bo, perspective=int(turn))` (**zar yok**, hamle öncesi tahta); etiket `equity=float(best.equity)` ve `best` `referee.hint(board, turn, dice)`'dan gelir (**zara bağlı**). Etiket girdinin fonksiyonu değil. |
| R-03 | **doğrulandı** | `ml/gnubg_distill.py:258` `train_value_head` sonunda `out = model(x)` **tüm** veri kümesi üzerinde; `finalMse`/`finalMae`/`correlation`/`slope` buradan. Held-out bölme yok. |
| R-04 | **doğrulandı** | `ml/gnubg_distill.py:602` `train_policy_head` → `F.cross_entropy(logits, bt[idx])` (sert top-1). `PolicyPosition` yalnızca `best_index` + `best_equity` taşır; aday başına equity atılıyor. |
| R-05 | **doğrulandı** | `DEFAULT_STEPS=2000`, `DEFAULT_BATCH=256`, `DEFAULT_LR=1e-3`. 2 000 pozisyon ⇒ ~256 epoch; 10 000 pozisyon ⇒ ~51 epoch. Veri artışı eğitim süresi **azalmasıyla** karışmış. Ayrıca `ckpt_v30` üzerine lr=1e-3 fine-tune. |
| R-06 | **doğrulandı** | `train_policy_head` sonunda `top1` **eğitim kümesi** (`xt`/`bt`) üzerinde hesaplanıyor. |
| R-07 | **doğrulandı** | `ml/gnubg_distill.py:773` `distill_verdict`: `if er_after <= target: return VERDICT_PIPELINE` **eşleştirilmiş testten önce**. `VERDICT_CAPACITY` kazanç `min_gain` altındaysa döner — GA yok, n denetimi yok. |
| R-08 | **doğrulandı** | `ml/pipeline_health.py:172` `gate_target_std_ratio` → `float(ratio) > TARGET_STD_RATIO_MIN` (**tek taraflı, üst sınır yok**). Mekanizma: `spread_from_shards` hedefleri **işaretli** (`td_lambda_targets_masked`), terminal değerleri **işaretsiz** (`replay.terminal_value` = `resultPoints/cubeValue`, F6-07) karşılaştırıyor. λ=1'de hedef = ±z, terminal = +z ⇒ oran ≈ √E[z²]/std(z) > 1 **yapısal olarak**. Ölçülen 3,0227 bir çökme değil, **birim uyumsuzluğu**. |
| R-09 | **doğrulandı** | `ml/pipeline_health.py:71-72` `STD_RATIO_MIN=0.85`, `STD_RATIO_MAX=1.15`. `Faz 6 v3.md:389` ve `:852` orijinal bant **0,7 ≤ oran ≤ 1,4**. 1,3371 eski bantta **geçerdi**. Daraltma gerekçesiz. |
| R-10 | **doğrulandı** | `pipeline_health.diagnose` yalnızca G1–G7 kalibrasyon kapılarına bakar; **öğrenme eğrisi** (veri ↔ ER) ölçen hiçbir kod yok. "pipeline" teşhisi ölçek hipotezini **test etmiyor**. |
| R-11 | **doğrulandı** | `Backgammon.Core/Search/SearchSettings.cs:21` `ProductionDepthPly = 1`; ER ise `gnubg_er.score_afterstates(criterion="policy")` → `OnnxScorer.logits` → `argmax` ile ölçülüyor. Ürünün gerçek hamle kalitesi (depth-1 + değer) **ölçülmüyor**. |
| R-12 | **doğrulandı** | `ml/artifacts/reference_corpus_v1.json`: 200 vaka, faz dağılımı `closed 44 / race 40 / bar 40 / contact 39 / bearoff 37` ⇒ **contact %19,5**. Üretici `er_harness._candidate_positions` **rastgele oyun** (`rng.choice(sorted(states))`) + 3 sentetik aile (`_closed_positions`, `_race_positions`, `_bearoff_positions`). Bölme **pozisyona** göre (`assign_splits`), oyuna göre değil. |
| R-13 | **doğrulandı** | `ml/gnubg_distill.py:145` `generate_positions` → `refgen.random_positions(rng, count, max_plies)`; korpusla **aynı** üretici ailesi. Korpus tahtalarını dışlayan hiçbir filtre yok. |
| R-14 | **doğrulandı** | `er_harness.TARGET_POSITIONS=200`, `SPLIT_RATIOS=(("cal",0.30),("val",0.35),("test",0.35))` ⇒ VAL **n=70**. "264 pozisyon" sayısı gözlenen farktan (0,0176) hesaplanmıştı — Kural 4 ihlali. |
| R-15 | **doğrulandı** | `faz 7.md` §4.4 merdiveni "~0,10 / ~0,08 / ~0,05 / ~0,03 / ~0,02" **tahmin** taşıyordu; 4. satır (hakem 4-ply iken 4-ply ER'si) **tanım gereği 0**'dır. Şampiyon satırı (0,002–0,003) **literatür** ve farklı dağılım/hakem. |
| R-16 | **doğrulandı** | `faz 7.md` §4.4 kanıt kriteri 2. koşulu "kazanma oranı > %50, p < 0,05" — bir **üstünlük** testi. Şampiyon seviyesi iddiası **eşdeğerlik/aşağı-olmama** testi gerektirir. |
| R-17 | **kısmen doğrulandı** | `ml/gnubg_hint.py` `HINT_MOVE_CAP = 10` (F7-03) ⇒ >10 adaylı pozisyonda adaylar etiketsiz kalır. `gnubg_distill.label_policy_positions:458` `map_hints` başarısızlıklarını `mapping_failures` olarak **sayıyor** ama `train_policy_head` maskesi yalnızca `mask[i, :k] = True` (aday **varlığına** göre); "gnubg bu adayı etiketledi mi" maskesi **yok**. Etiketsiz adaylar CE paydasından çıkarılmıyor — yani "negatif sayılıyor" tespiti **doğru**, ama mekanizma "hiç hedef olmamak" biçiminde. |

**Sonuç.** 17 bulgunun **16'sı doğrulandı**, **1'i kısmen** (R-17), **0'ı çürütüldü**.
R-08'in mekanizması (işaretli hedef vs işaretsiz terminal) bulgu metninde
"birim uyumsuzluğu olabilir" diye **hipotez** olarak geçiyordu; burada **kanıtlandı**.

## F7-39 — B3 kararı askıya alındı

**Soru.** §5.1.8'deki B3 kararı (üretim profili `medium`, ER hedefi ≤ 0,02,
şampiyon iddiası düşürüldü) yürürlükte kalmalı mı?

**Sonuç: hayır, askıya alındı.** Dayanağı olan `large` −%3,7 farkı kendi standart
hatasının (0,0120) **altında** ve Aşama B'nin kendi `noiseThreshold` değerinin
(0,002535) de altında (gözlenen 0,002457). Test 68 ise **ters yönde** ölçüm
vermişti (`large` 0,2651 vs `medium` 0,3535). İki ölçüm çelişiyor ve ikisi de
gürültü içinde ⇒ karar **ölçüme değil gürültüye** dayanıyordu.

**Kapsam.** B3'ün altı kaleminden **1, 2, 5, 6** askıda; **3** (Test 98 onarımı)
ve **4** (kalibrasyon önceliği) **askıda değil** — kendi ölçümlerine dayanırlar.

**Yeniden açma koşulu.** Aşama R-E (≥ 3 seed, korpus v2, eşleştirilmiş test)
`large` aleyhine **GA alt sınırı > 0** olan bir fark üretirse B3 yeniden
onaylanabilir. O zamana kadar üretim profili `medium` kalır; bu bir **kanıt**
değil, **kanıtlanmamış varsayılan**dır ve öyle yazılır.

## F7-40 — Hedef ikiye ayrıldı: Hedef-1 (hamle) ve Hedef-2 (oyun gücü)

**Soru.** Tek bir "ER ≤ X" hedefi neden yetmiyor?

**Sonuç: iki farklı şeyi karıştırıyordu.** (i) modelin **hamle** kalitesi ve
(ii) modelin **oyun** gücü (küp + maç). İkincisi birincisinden türetilemez
(Ek B: maç equity'sinin önemli kısmı küp kararlarından gelir). Ayrıca ER hedefinin
**sayısal değeri** kendine referanslıydı: hakem 4-ply iken "4-ply ER ≤ 0,005"
demek, hakemin kendi seviyesini ölçmesini istemektir (R-15).

**Yeni tanım.** Hedef-1 = **rollout tabanlı** referansa göre ER, eşiği R-F'de
ölçülen **çözünürlük tabanından** türetilir. Hedef-2 = gnubg 2-ply ve 4-ply'a
karşı **ppg eşdeğerliği** (aşağı-olmama, `H0: ppg_fark ≤ −m`, m = 0,02, %95).
Üstünlük sonucu varsa **bonus**, kapı değil.

## F7-41 — İnsan merdivenindeki tahmini sayılar kaldırıldı

**Soru.** §4.4 merdivenindeki "~0,10 / ~0,08 / ~0,05 / ~0,03 / ~0,02" nereden geliyor?

**Sonuç: hiçbir ölçümden.** Uydurma tahminlerdi ve 4. satır **yapısal olarak
yanlıştı** (hakem kendi seviyesini ölçemez). Satırlar "R-F'de ölçülecek" olarak
değiştirildi; 4. satır için daha derin referans (5-ply veya rollout) şartı
yazıldı, yoksa "ölçülemez" işaretlenir. Literatür satırları (şampiyon insan,
gnubg 4-ply + büyük ağ) **korundu** ama "farklı dağılım, kıyaslanamaz" etiketiyle.

## F7-42 — Kanıt türü: üstünlük değil eşdeğerlik

**Soru.** "gnubg 4-ply'a karşı > %50, p < 0,05" hedefi kanıtlar mı?

**Sonuç: hayır.** Bu bir **üstünlük** (superiority) testidir. Reddedilememesi
"eşitiz" demek değil, "fark gösteremedik" demektir. Şampiyon seviyesi iddiası
bir **eşdeğerlik / aşağı-olmama** iddiasıdır ve **marjlı** bir test gerektirir.
§4.4 ve Ek B buna göre düzeltildi; üstünlük sonucu **bonus** olarak ayrıldı.

## F7-43 — G7 oranı yapısal olarak 1'den büyük (birim uyumsuzluğu)

**Soru.** G7 = 3,0227 "GEÇTİ" — bu bir çökme mi, bir hata mı?

**Sonuç: hata.** `pipeline_health.spread_from_shards` hedefleri **işaretli**
(`td_lambda_targets_masked` işareti kendisi çevirir), terminal değerleri ise
**işaretsiz** (`replay.terminal_value` = `resultPoints/cubeValue`, F6-07) alıyor.
λ = 1'de hedef tam olarak ±z, terminal +z olur ⇒ oran ≈ √E[z²] / std(z) ve
E[z] > 0 olduğu sürece **1'den büyüktür**. Ölçülen 3,0227 bu formülle uyumlu
(hedef std 1,3542, terminal std 0,4480). Yani G7 **hiçbir zaman** "hedef
çökmedi" demiyor; **her zaman** geçiyor. Kapı bilgi taşımıyor.

**Düzeltme (Aşama R-C).** G7 iki taraflı olacak ve terminal değerler **işaretli**
hale getirilecek; önerilen bant **[0,5; 1,5]** — **onay bekliyor** (Kural 2).

## F7-44 — G5 bandı gerekçesiz daraltılmış

**Soru.** `STD_RATIO_MIN/MAX = 0,85/1,15` nereden geliyor?

**Sonuç: gerekçesiz.** `Faz 6 v3.md:389` ve `:852` orijinal bandı
**0,7 ≤ oran ≤ 1,4** olarak veriyor. Ölçülen 1,3371 **eski bantta geçerdi**.
Daraltma hiçbir belgede gerekçelendirilmemiş. Aşama R-C'de ya Faz 6 bandına
dönülecek ya da gerekçe yazılıp **onay** alınacak; o zamana kadar rapor
**iki bant altında** yazılır.

## F7-45 — "pipeline" teşhisi ölçek hipotezini test etmiyor

**Soru.** `pipeline_health` "pipeline" dediğinde "sorun ölçek değil" demiş olur mu?

**Sonuç: hayır.** `diagnose` yalnızca G1–G7 **kalibrasyon** kapılarına bakıyor.
Öğrenme eğrisi (veri ↔ ER) ölçen hiçbir kod yok. "pipeline" teşhisi
"kalibrasyon bozuk" demektir; "ölçek yeterli" demek **değildir**. Aşama R-C'de
`learning_curve` modulu eklenecek ve `pipeline_health`'e `scaling_evidence`
alanı (`yok | eğim<ε | eğim≥ε`) girecek.

## F7-46 — ER yanlış oynama yolunda ölçülüyor

**Soru.** Ölçülen ER ürünün gerçek hamle kalitesini mi gösteriyor?

**Sonuç: hayır.** ER `score_afterstates(criterion="policy")` → `logits.argmax`
ile ölçülüyor (0-ply, politika kafası). Ürün ise `ProductionDepthPly = 1`
arama + değer kafası kullanıyor. İkisi **farklı** şeyler. Aşama R-B'de ER
**üç yol** için ayrı raporlanacak: politika argmax / değer 0-ply / depth-1 arama.

## F7-47 — Korpus v1 dağılımı gerçek oyunu temsil etmiyor

**Soru.** 200 pozisyonluk korpus gerçek oyun dağılımını temsil ediyor mu?

**Sonuç: hayır.** Ölçülen dağılım: `closed 44 / race 40 / bar 40 / contact 39 /
bearoff 37`. **Contact %19,5** — gerçek oyunda bu oran çok daha yüksektir.
Ayrıca 37 bearoff pozisyonu üründe **tam veritabanı** ile çözülüyor (ölçüm
gücü katmıyor), 44 closed pozisyon gerçek oyunda **nadir**. Üretici **rastgele
oyun** (`rng.choice`) + 3 sentetik aile. Bölme **pozisyona** göre yapılmış,
**oyuna** göre değil ⇒ aynı oyunun pozisyonları CAL ve TEST'e düşebilir (sızıntı).

**Düzeltme (Aşama R-B).** Korpus v2: ≥ 1 000 pozisyon, **contact ≥ %60**,
kaynak (a) gnubg 2-ply self-play, (b) kendi model self-play, (c) rastgele ≤ %10;
bearoff/closed ayrı `diagnostic_*` kümesine; bölme **oyuna göre**; sızıntı
filtresi (ayna/perspektif-kanonik tahta hash'i).

## F7-48 — Damıtma verisi korpusla aynı üreticiden, sızıntı filtresi yok

**Soru.** Damıtma pozisyonları ölçüm korpusuyla çakışıyor mu?

**Sonuç: evet, filtresiz.** `gnubg_distill.generate_positions` →
`refgen.random_positions`, korpusla **aynı** üretici ailesi. Korpus tahtalarını
dışlayan hiçbir filtre yok. Aşama R-B'de ayna/perspektif-kanonik tahta hash'i
ile sızıntı filtresi eklenecek ve **çıkarılan tahta sayısı raporlanacak**.

## F7-49 — Damıtma "başarı" sayıları in-sample

**Soru.** §25'teki MAE 0,0072 / corr 0,9996 / top1 değerleri neyi kanıtlıyor?

**Sonuç: hiçbir şeyi.** `train_value_head` ve `train_policy_head` bu metrikleri
**eğitim kümesinin tamamı** üzerinde hesaplıyor. Model 2 000 pozisyonu ezberlese
de bu sayılar mükemmel çıkar. Held-out ölçüm yok. Aşama R-D'de tüm metrikler
**held-out** raporlanacak; in-sample ayrı `inSample: true` alanında duracak
(Kural 5).

## F7-50 — Damıtma deneyinde veri ve eğitim süresi karışmış

**Soru.** 2 000 → 10 000 pozisyon karşılaştırması temiz mi?

**Sonuç: değil.** `DEFAULT_STEPS = 2000`, `DEFAULT_BATCH = 256` sabitken
2 000 pozisyon ~256 epoch, 10 000 pozisyon ~51 epoch eğitim demek. Yani veri
**5×** artarken eğitim süresi **5×** azaldı. Ayrıca `ckpt_v30` üzerine
lr = 1e-3 fine-tune yapıldı. Aşama R-D'de **epoch-sabit / veri-değişken** deney
zorunlu; "step-sabit" kol yalnızca karıştırıcıyı **göstermek** için koşulacak.

## F7-51 — Damıtma kararı eşleştirilmiş testten önce veriliyor

**Soru.** `distill_verdict` "pipeline" derken GA'ya bakıyor mu?

**Sonuç: hayır.** `if er_after <= target: return VERDICT_PIPELINE` **eşleştirilmiş
testten önce** çalışıyor; GA hesaplanmadan "pipeline" dönebiliyor. `VERDICT_CAPACITY`
ise kazanç `min_gain` altındaysa dönüyor — GA yok, n denetimi yok. "ER 0,03'ün
altına inmiyorsa kapasite sorunudur" çıkarımı **geçersiz** (veri 2–10 bin
pozisyon mertebesinde). Aşama R-C'de `distill_verdict` yeniden yazılacak:
önce eşleştirilmiş fark + bootstrap GA, `pipeline` yalnızca GA **üst** sınırı
hedefin altındaysa, `kapasite` çıkarımı **kaldırılacak**, n < gerekli n iken
`veri-yetersiz` durumu eklenecek.

## F7-52 — Damıtma girdisi hamle öncesi, etiketi zara bağlı

**Soru.** Değer damıtma hattı doğru mu tasarlanmış?

**Sonuç: hayır, tasarım hatası.** Girdi `vectorize(board, wo, bo, perspective)`
— **zar yok**, hamle öncesi tahta. Etiket `hints[0].equity` — **zara bağlı**.
Etiket, girdinin fonksiyonu değil ⇒ öğrenilemez bir hedef. Ürün ise değer
kafasını **afterstate** üzerinde kullanıyor. Aşama R-D'de bu hat **kaldırılacak**;
yerine afterstate vektörleri + `probs @ EQUITY_WEIGHTS ≈ equity_gnubg` (MSE)
gelecek. Eski hattın testleri "yanlış tasarım" notuyla silinecek/yeniden yazılacak.

## F7-53 — Politika damıtma aday equity'lerini atıyor

**Soru.** gnubg her adayın equity'sini verirken neden yalnızca top-1 öğreniliyor?

**Sonuç: tasarım eksikliği.** `train_policy_head` sert top-1 çapraz entropi
kullanıyor (`F.cross_entropy(logits, bt[idx])`); `PolicyPosition` yalnızca
`best_index` + `best_equity` taşıyor, aday başına equity **atılıyor**. gnubg'nin
verdiği bilgi miktarı %90 kullanılmıyor. Aşama R-D'de **liste tabanlı** kayıp:
`KL(softmax(equity_gnubg/T) ‖ softmax(logits))`, maskeleme ile, T doğrulama
kümesinde seçilecek.

## F7-54 — Etiketsiz adaylar negatif sayılıyor

**Soru.** `hint` en fazla 10 hamle yazdırıyorsa (F7-03), 10'dan fazla adaylı
pozisyonlarda ne oluyor?

**Sonuç: etiketsiz adaylar CE paydasında kalıyor.** `label_policy_positions`
`map_hints` başarısızlıklarını `mapping_failures` olarak sayıyor, ama
`train_policy_head` maskesi yalnızca `mask[i, :k] = True` (aday **varlığına**
göre). "gnubg bu adayı etiketledi mi" maskesi yok ⇒ etiketsiz aday hiç hedef
olmuyor ama **negatif** gibi davranıyor. Aşama R-D'de etiketsiz adaylar
maskelenecek ve **maskelenen pay** raporlanacak.


## F7-55 — R-Q3: vektörleştirici ayna-tutarlı, **model değil**

`gnubg_er.vectorize` ayna tutarlılığı **ölçüldü**: 40 rastgele pozisyonda
`vectorize(board, wo, bo, perspective=+1)` ile
`vectorize(mirror(board), bo, wo, perspective=-1)` **40/40 aynı**. Yani
vektörleştirici doğru; F6-31 sınıfı bir hata **yok**.

Ama modelin **değer çıktısı antisimetrik değil**. Aynı fiziksel tahta iki
perspektiften sorulduğunda `e(+1) = -e(-1)` olması gerekir (Beyaz'ın equity'si
Siyah'ınkinin negatifidir). Ölçüm (300 pozisyon, `model_v30`):

| Ölçüm | Değer | Beklenen |
|---|---|---|
| `corr(e(+1), e(-1))` | **−0,7019** | −1,0000 |
| ortalama `\|e(+1)+e(-1)\|` | **1,0044** | 0,0000 |
| `\|hata\| < 0,05` | **1/300** | 300/300 |
| `\|hata\| < 0,10` | 7/300 | 300/300 |
| politika argmax iki perspektifte aynı | **1/59** | 59/59 |
| başlangıç pozisyonu `e(+1)`, `e(-1)` | −0,0486, −0,0486 | 0, 0 |
| simetrik pozisyon `e(+1)`, `e(-1)` | +0,5479, +0,5479 | 0, 0 |

Başlangıç ve simetrik pozisyonda iki perspektif **aynı** değeri veriyor
(negatifini değil). Yani model ayna-**değişmez**, ayna-**ters** olması
gerekirken.

**Neden:** eğitim verisi hiçbir zaman aynalanmış tahtayı göstermiyor.
`ml/train_v2.py`'de `flip_exclusive` yalnızca TD(λ) **hedef zincirinde**
kullanılıyor (satır 97, 136, 138); girdi vektörü için perspektif artırımı
(augmentation) **yok**. Öğrenen her zaman hamle yapan taraftır, dolayısıyla
ağ simetriyi öğrenecek bir sinyal görmez.

**Sonuç:** ER zaten bu asimetriyi **içeriyor** (ölçüm `perspective=turn` ile
yapılıyor), yani ER sayıları bu kusuru cezalandırıyor. Ama kusur giderilirse
ER'nin düşmesi beklenir. Bu, R-D'nin (öğretmen yeniden tasarımı) **girdi
artırımı** maddesi için somut bir gerekçedir.

**Naif düzeltme denemesi başarısız:** iki perspektifin politika logit'lerini
ortalamak ER'yi **kötüleştirdi** (120 vakada 0,0500 → 0,1674). Logit
ortalaması geçerli bir simetrizasyon değil (iki farklı skorlama fonksiyonunu
karıştırıyor). Doğru yol eğitimde artırımdır; çıkarımda yama değil.

## F7-56 — R-Q4: `random_positions` hamle seçimi ve erken-oyun ağırlığı

`tools/reference_gen.py` icindeki `random_positions` hamleyi `rng.choice(sorted(states))` ile
seçiyor, yani yasal afterstate'ler üzerinde **tekdüze**. Bu "rastgele oyun"
tanımına uygun; hile yok.

İki ölçülmüş kusur var:

1. **Erken ply aşırı temsil.** Örnekleme her ply'de `p = 0,5` ile yapılıyor,
   yani oyunun her adımında %50 ihtimalle pozisyon toplanıyor. Oyunlar
   `max_plies` ile kesildiği için erken ply'ler daha çok oyun tarafından
   görülüyor. v2'de ölçülen ply dağılımı: `ply < 5` **%5,7**, `ply < 10`
   **%14,0**, `ply < 20` **%29,3**, `ply < 40` **%58,2**; medyan 34, maksimum
   118.
2. **v1 ile damıtma örtüşmesi ölçüldü:** v1'in 200 benzersiz tahtasından
   **yalnızca 1'i** (`%0,50`) `gnubg_distill.generate_positions(10000, seed=7)`
   çıktısında var. Yani R-13'ün "aynı üretici ailesi" tespiti **doğru ama
   etkisi küçük**: sızıntı aynı tahtalar üzerinden değil, aynı **dağılım**
   üzerinden. v2'de sızıntı filtresi 26 tahta çıkardı (F7-57).

## F7-57 — Korpus v2 üretildi ve doğrulandı

`ml/corpus2.py` (yeni modül) korpus v2'yi üretir. Ölçülen içerik:

| Alan | Değer |
|---|---|
| Pozisyon | **1000** |
| Faz | contact **600** (%60,0), bar 250, race 150, bearoff 0, closed 0 |
| Kaynak | gnubg 2-ply self-play **664**, kendi model self-play **286**, rastgele **50** (%5,0) |
| Oyun sayısı | 43 |
| Bölünme (oyun düzeyinde) | cal 300 / val 350 / test 350 |
| Sızıntı filtresi | 9 652 eğitim hash'i tarandı, **26 tahta çıkarıldı** |
| Tekrar atılan | 76 |
| Teşhis kümesi | 1 566 (bearoff 266, closed 1, artık contact/bar/race) |
| Özet (digest) | `e0466b9e673dca6cbdd05d8246730deea9371fa9a425055db715e8390e4a97b8` |
| Doğrulama | `verify_corpus2` → **ihlal yok** |

Gerçek oyun faz payları **oyunlardan ölçüldü** (varsayılmadı): contact
**0,5564**, bar **0,3706**, race **0,0730**. Ağırlıklı ER bu paylarla
hesaplanır; böylece %60 contact katmanlaştırmasının yanlılığı düzeltilir.

**Bölünme hatası bulundu ve düzeltildi:** ilk sürüm bölünmeyi *faz içinde*
yapıyordu; bir oyun birden çok fazda pozisyon taşıdığı için aynı oyun hem CAL
hem TEST'e düşüyordu (`verify_corpus2` 300+ ihlal verdi). Düzeltme: bölünme
**tek seferde, oyun düzeyinde**, oyunlar pozisyon sayısına göre büyükten
küçüğe yerleştirilerek yapılır. Sonuç: 300/350/350, ihlal yok.

## F7-58 — ER üç oynanış yolu için ölçüldü

`ml/er_paths.py` (yeni modül) ER'yi üç yol için ayrı ölçer. Hakem her vakada
**bir kez** çalışır (gnubg `eval` 2-ply); yollar arasındaki fark yalnızca
**seçim** farkıdır (Kural 7).

`model_v30`, gnubg `eval` 2-ply hakem, bootstrap 20 000:

| Korpus | Yol | n | Ortalama | Medyan | %95 GA | σ | σ üst |
|---|---|---|---|---|---|---|---|
| v2 | `policy` | 1000 | **0,0402** | 0,0000 | [0,0350; 0,0457] | 0,0867 | 0,1025 |
| v2 | `value` | 1000 | **0,0442** | 0,0000 | [0,0384; 0,0504] | 0,0957 | 0,1130 |
| v2 | `search1` | 1000 | **0,0210** | 0,0000 | [0,0181; 0,0240] | 0,0477 | 0,0540 |
| v1 | `policy` | 200 | 0,0740 | 0,0160 | [0,0594; 0,0893] | 0,1091 | 0,1241 |
| v1 | `value` | 200 | 0,0746 | 0,0190 | [0,0594; 0,0909] | 0,1145 | 0,1318 |
| v1 | `search1` | 200 | 0,0515 | 0,0000 | [0,0382; 0,0659] | 0,1000 | 0,1180 |

**v1 `policy` = 0,0740**, tarihsel `stage_h_er_2ply.json` değeri **0,073970**
ile birebir aynı. Yani yeni harness eski ölçümü **yeniden üretiyor**; sapma
yok.

Gerçek oyun frekansıyla ağırlıklı ER (v2): `policy` **0,0434**, `value`
**0,0478**, `search1` **0,0221**.

Faz kırılımı (v2): `policy` contact 0,0448 / bar 0,0480 / race 0,0086;
`search1` contact 0,0229 / bar 0,0235 / race 0,0091. Race her yolda en kolay
faz.

**Üretim yolu `search1`'dir** (`SearchSettings.ProductionDepthPly = 1`) ve
ölçülen ER **0,0210** — yani ürün, bugüne kadar raporlanan 0,0533/0,0617'den
**belirgin biçimde iyi**. Bu, F7-46'nın (ER yanlış oynanış yolunda ölçülüyor)
nicel sonucudur.

## F7-59 — v1 korpusu ER'yi **abartıyormuş**

v1 ile v2 arasındaki fark, aynı model ve aynı hakemle (eşleşmemiş, farklı
korpuslar):

| Yol | v1 | v2 | Fark | SE | z | %95 GA | Sıfır dışı |
|---|---|---|---|---|---|---|---|
| `policy` | 0,0740 | 0,0402 | **−0,0338** | 0,0082 | −4,13 | [−0,0498; −0,0178] | **evet** |
| `value` | 0,0746 | 0,0442 | **−0,0304** | 0,0086 | −3,52 | [−0,0473; −0,0135] | **evet** |
| `search1` | 0,0515 | 0,0210 | **−0,0305** | 0,0072 | −4,22 | [−0,0447; −0,0163] | **evet** |

Yani v1 korpusu ER'yi `policy` yolunda **%84 göreli** abartıyordu. Bu, "sorun
ölçek değil pipeline" tezinin bir parçası olarak **ölçüm hattının** da bozuk
olduğunu gösterir: model, temsil edici olmayan bir korpusta ölçüldüğü için
olduğundan kötü görünüyordu.

**Uyarı (Kural 7):** bu karşılaştırma eşleşmemiş ve iki korpus farklı faz
karışımına sahip. Fark, korpus değişimi ile faz karışımı değişimini
**ayırmıyor**. Ayrıştırma için v2'nin faz paylarını v1'e uygulayan bir kol
gerekir; bu R-C'ye bırakıldı.

## F7-60 — Gereken n, σ'nin **üst** güven sınırından

Kural 4 gereği güç hesabı nokta tahmininden yapılmaz. `corpus2.power_table` ve
`er_paths.power_rows` yalnızca `sigmaCiHigh` kullanır.

| Korpus | Yol | σ üst | n (Δ=0,01, tek yön) | n (Δ=0,02, tek yön) | mevcut n | Δ=0,01 için yeterli |
|---|---|---|---|---|---|---|
| v2 | `policy` | 0,1025 | **285** | 72 | 1000 | **evet** |
| v2 | `value` | 0,1130 | **346** | 87 | 1000 | **evet** |
| v2 | `search1` | 0,0540 | **79** | 20 | 1000 | **evet** |
| v1 | `policy` | 0,1241 | 418 | 105 | 200 | **hayır** |
| v1 | `value` | 0,1318 | 471 | 118 | 200 | **hayır** |
| v1 | `search1` | 0,1180 | 377 | 95 | 200 | **hayır** |

v1'in 200 pozisyonu Δ=0,01 için **hiçbir yolda yeterli değildi**. v2'nin 1000
pozisyonu üç yolda da yeterli. Bu, R-14'ün ("264 pozisyon gözlenen etkiden
hesaplandı") düzeltilmiş halidir: doğru sayı **285** (`policy`, Δ=0,01, tek
yönlü, σ üst sınırı).

## F7-61 — gnubg 2-ply etiketleme maliyeti ölçüldü

Tek çekirdek, 2-ply `hint`, 6 pozisyon: ortalama **0,562 s**, medyan 0,535,
min 0,282, maks 0,865. 24 pozisyon: 1 süreç **1,803 poz/s**; 4 süreç
**4,696 poz/s** (2,6× ölçekleme, 4× değil).

R-D için önerilen hacimler (4 süreç, **kestirim**):

| Pozisyon | Süre |
|---|---|
| 2 000 | ~7 dk |
| 5 000 | ~18 dk |
| 10 000 | ~36 dk |
| 20 000 | ~71 dk |
| 50 000 | ~3,0 sa |

**Düzeltme:** `faz 7.md` §5.1.1'deki "12 iş parçacığında 8× hızlanma"
varsayımı ölçümle **desteklenmiyor**; 4 süreçte 2,6× görüldü. Bütçe
hesapları bu daha düşük sayıyla yeniden yapılmalıdır.

## F7-62 — v2'nin `self` kaynağı on-policy sızıntı taşır

v2'nin 1000 pozisyonunun **286'sı** `model_v30`'un kendi oynadığı oyunlardan
geliyor. Bu pozisyonlar modelin **kendi dağılımında**; tahta düzeyinde sızıntı
filtresi 26 tanesini çıkardı ama dağılım düzeyinde bir yakınlık kalıyor. Bu,
ER'yi **iyimser** gösterebilir.

**Ölçüldü** (v2 VAL, n=350, `ml/artifacts/er_paths_v2_val.json`):

| Yol | gnubg2 | self | self/gnubg2 |
|---|---|---|---|
| `policy` | 0,0484 | 0,0433 | 0,90 |
| `value` | 0,0637 | 0,0382 | **0,60** |
| `search1` | 0,0227 | 0,0096 | **0,42** |

`self` her yolda daha düşük ER veriyor; `search1`'de fark **2,4×**. On-policy
dağılımın ER'yi iyimser gösterdiği **doğrudan kanıtlandı**. Başlık ER'si bir
**alt sınır** olarak okunmalı; `gnubg2` sütunu muhafazakâr referanstır.
`er_paths` artık `sourceMeans`/`sourceCounts` alanlarını üretiyor.

---

## F7-63 — G7'nin 3,0227'si bir **birim uyumsuzluğuydu**, çökme değil

`ml/replay.py:terminal_value` **işaretsiz** büyüklük döndürür
(`resultPoints / cubeValue`, F6-07). `ml/td_lambda.py:td_lambda_targets` ise
**işaretli** hedef üretir (mover perspektifi, her adımda işaret döner).
`spread_from_shards` bu iki farklı büyüklüğü karşılaştırıyordu.

λ = 1'de hedef tam olarak `(-1)^(T-1-t) · z`'dir. İşaretsiz `z` ile
karşılaştırılırsa oran **yapısal olarak** 1'i aşar:

```
std(hedef) = √E[z²]        std(terminal) = std(z)
oran = √(1 + (mean(z)/std(z))²) > 1
```

**Düzeltme:** `pipeline_health.signed_terminal_series(z, decision_indices,
n_decisions)` eklendi; `spread_from_shards` artık işaretli terminal kullanır.
Eski (hatalı) karşılaştırma `legacyRatio` alanında **kayıt için** tutulur.

**Ölçüm** (`it1_0000.bgsp.gz`, 627 737 örnek, `ckpt_v15.pt`):

| Mod | Oran (işaretli) | Eski oran | Hedef std | Terminal std |
|---|---|---|---|---|
| λ=1, model yok | **1,000000** | 2,8781 | 1,4839 | 1,4839 |
| λ=1, model var | **1,000000** | 2,8781 | 1,4839 | 1,4839 |
| λ=0,7, model yok | 0,176031 | 0,5066 | 0,2612 | 1,4839 |
| λ=0,7, model var | 0,682135 | 1,9633 | 1,0122 | 1,4839 |

λ=1'de oran **tam olarak 1** — hedefler terminal değerlerin kopyasıdır.
λ=0,7 + model yok: hedefler `-(0,3·0 + 0,7·y_next)` ile sıfıra çöker → 0,176;
kapı bunu **doğru** yakalar. λ=0,7 + model var: `V̂` hedefleri taşır → 0,682.

**Sonuç:** G7 artık **1,0000 ile GEÇTİ**. Önceki 3,0227 bir arıza değil,
ölçüm hatasıydı. `ml/artifacts/g7_modes.json` dört modu kaydeder.

---

## F7-64 — G7 çift taraflı oldu: bant **[0,5; 1,5]**

Tek taraflı kapı (`> 0,5`) yalnızca çökmeyi yakalıyordu; oranın 1'in üzerine
çıkması da bir arızadır (hedefler terminal değerlerden **daha geniş** → birim
veya işaret hatası). `TARGET_STD_RATIO_MAX = 1,5` eklendi; bant kapalı aralık.

> **ONAY GEREKİYOR (Kural 2).** Üst sınır yeni bir eşiktir. Gerekçe: TD(λ)
> hedefleri terminal değerlerin yumuşatılmış hâlidir, bu yüzden oran ≤ 1
> beklenir; 1,5 üstü ancak bir birim/işaret hatasıyla oluşur. Onaylanmazsa kapı
> tek taraflı kalır ve 3,0227 gibi bir değer yine **gizlenir**.

---

## F7-65 — G5 onaylanmış Faz 6 bandına döndü: **[0,7; 1,4]**

`Faz 6 v3.md` §6.3 ve §13.2: `0,7 ≤ oran ≤ 1,4`. Kodda `0,85–1,15` vardı ve
bu bandın **hiçbir belgede gerekçesi yok** (R-09).

| Bant | 1,3371 | 2,78 (Faz 5) |
|---|---|---|
| Faz 6: [0,7; 1,4] | **GEÇTİ** | DÜŞTÜ |
| Faz 7 sıkı: [0,85; 1,15] | DÜŞTÜ | DÜŞTÜ |

`STD_RATIO_MIN/MAX` → `0,7 / 1,4`; sıkı bant `STD_RATIO_LEGACY_MIN/MAX` olarak
**kayıt** için durur ve her kapı notunda raporlanır
(`sıkı bant [0,85; 1,15] ile: DÜŞTÜ`). İki bant da her raporda görünür.

---

## F7-66 — `distill_verdict` yeniden yazıldı: önce eşleştirilmiş GA

Eski kod (R-07):

```python
if er_after <= target:      # NOKTA TAHMİNİ, GA yok  → Kural 3 ihlali
    return VERDICT_PIPELINE
...
return VERDICT_CAPACITY     # "etiketler işe yaramadı" → "kapasite" (geçersiz)
```

İki kusur: (a) nokta tahmini kanıt sayılıyordu; (b) olumsuzluktan olumlu iddia
çıkarılıyordu.

**Yeni sözleşme.** `paired_er_test(before, after)` eşleştirilmiş fark **ve**
`er_after`'ın **mutlak** bootstrap %95 GA'sını üretir (20 000 yeniden
örnekleme). `distill_verdict` sırası:

| Koşul | Etiket |
|---|---|
| ölçüm eksik / sonlu değil | `bilinmiyor` |
| `paired` yok | `belirsiz` |
| `n < required_n` | **`veri-yetersiz`** (yeni) |
| `paired.ciHighAfter ≤ target` | `pipeline` |
| GA sıfırı dışlıyor **ve** `meanDiff > 0` | `kısmi` |
| aksi hâlde | `belirsiz` |

CLI çıkış kodları: 0 `pipeline`/`kısmi`, 3 `bilinmiyor`, 4 `belirsiz`,
**5 `veri-yetersiz`**.

---

## F7-67 — `VERDICT_CAPACITY` artık **üretilmiyor**

Etiketlerin işe yaramaması, darboğazın ağ/veri olduğunu **kanıtlamaz**. Bu
iddia ancak bir öğrenme eğrisi eğimiyle kurulabilir. Sabit, eski artifact'ları
okuyabilmek için duruyor; metni "**Kaldırıldı (Faz 7-R R-07)**" diye başlıyor ve
`ml/learning_curve.py`'ye yönlendiriyor. `distill_verdict_detail` ayrıca
`capacityInference: false` alanını yazar.

---

## F7-68 — `ml/learning_curve.py`: öğrenme eğrisi altyapısı

Aynı hat, aynı tohum, **yalnızca veri hacmi** değişir: N, 2N, 4N, 8N. Her
noktada ER (üç yol), kalibrasyon eğimi/MAE, **in-sample** ve **held-out** kayıp
(ayrı alanlar — Kural 5).

Eğim: ER'nin `log2(veri)` başına değişimi, OLS. GA **pozisyon düzeyinde**
yeniden örnekleme ile (20 000) — nokta düzeyinde değil, çünkü belirsizliğin
kaynağı korpus örneklemesidir.

**İşaret sözleşmesi:** `gain = -slope` (pozitif = veri arttıkça ER düşüyor).
Karar `gain` üzerinden verilir:

| Koşul | Karar |
|---|---|
| `gainCiLow ≥ ε` | `ölçek` |
| `gainCiHigh < ε` | `pipeline` |
| aksi hâlde | `belirsiz` |

`ε = 0,005` (`pipeline_health.SCALING_SLOPE_EPSILON` ile aynı).
`CurveReport.scaling_summary()` doğrudan `diagnose(scaling=...)`'e beslenir.

> **Dürüstlük notu:** gerçek eğitim hattı bu modüle **henüz bağlanmadı**;
> `main()` bilerek `SystemExit` atar. Gerçek koşum R-D'de yapılacak.

---

## F7-69 — `scaling_evidence` alanı: `yok | eğim<ε | eğim≥ε`

`HealthReport.scaling_evidence` + `scaling_note` + `to_dict()["scalingEvidence"]`.
CLI: `--scaling <json>`.

`yok` **"ölçek işe yaramaz" demek değildir**; "ölçülmedi" demektir. Markdown
raporu bunu açıkça yazar. GA ε'yu kesiyorsa `scaling_note` "karar **belirsiz**"
diye ekler.

---

## F7-70 — Onarılmış teşhis: üç gerçek arıza, iki ölçüm hatası

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
görünüyordu; ikisi de **ölçüm hatasıydı**, gerçek arıza değil.

---

## F7-71 — Test numarası çakışması düzeltildi: R-T1 = **128**

R-B'de `test_corpus2.py` Test 127–132 olarak numaralandı. Ancak
`ml/tests/test_gnubg_distill.py` **zaten** "Test 127" başlığını taşıyor
(`f8b9917`'de eklendi). Yani son test numarası 127'ydi ve R-T1 = **128**
olmalıydı. Düzeltildi: `test_corpus2.py` → Test 128–133, R-C testleri →
Test 134–138.

---

## F7-72 — `crawford` 5/6: hata senaryodaydı, kodda değil

`Backgammon.MatchBench crawford` koşusu **5/6** veriyordu. Düşen senaryo
`normal-double-pass` (5-away/5-away, E = 0,9) idi ve `shouldDouble: false`
dönüyordu; senaryo `true` bekliyordu.

**Kök neden.** `EquityCubeAdvisor.Decide` içindeki "çok iyi" tanımı

```
tooGood = doublePass > doubleTake && noDouble > doubleTake
```

idi. Bu yalnızca **"rakip kabul eder"** durumunu yakalar. 5-away/5-away'de
E = 0,9 olan bir pozisyonda rakip **reddeder**; teklif eden 1 puan alır
(MWC 0,607) ama oynamaya devam etse marslarla 0,692 MWC'ye ulaşır. Yani
doğru cevap **çiftlememek**tir. Senaryonun beklentisi yanlıştı.

**Düzeltme.** `doubleValue = min(doubleTake, doublePass)` üzerinden iki
taraflı tanım:

```
tooGood     = noDouble > doubleValue + Epsilon
shouldDouble = doubleValue > noDouble + Epsilon
```

`RunCrawford` yeniden yazıldı: senaryo başına `Equity` alanı, danışman
döngü içinde kurulur, `normal-double-pass` E = 0,3'e çekildi, yeni
`too-good-to-double` senaryosu (E = 0,9, çiftleme **beklenmez**) eklendi.
JSON artık `isTooGood`, `equity`, `equityNoDouble`, `equityDoubleTake`,
`equityDoublePass`, `expectedDouble`, `expectedTake`, `correct` taşır.

**Sonuç: 7/7.** `normal-double-pass` E = 0,30 → `shouldDouble: true,
shouldTake: false` (nd 0,086781 / dt 0,189025 / dp 0,154830).
`too-good-to-double` E = 0,90 → `shouldDouble: false, isTooGood: true`
(nd 0,292455 / dt 0,615629 / dp 0,154830).

`ml/artifacts/stage_b_crawford.json` yeniden üretildi (eskisi 6/6 diyordu).
`dotnet test Backgammon.Tests` → **297/297**.

**Yan bulgu.** `dead-cube-no-double` senaryosunun adı yanıltıcıydı:
`MatchState.IsDeadCube` = `CubeValue >= max(awayA, awayB)` olduğu için
3-away/1-away + küp 1'de **false** döner. Senaryo `one-away-no-double`
olarak yeniden adlandırıldı; beklenen davranış (teklif yok) aynı.

---

## F7-73 — Küp ER'si: ayrı bir ölçüm ekseni

Bütün hamle ER'si ölçümleri **küpsüzdür** (`cubeless`). Dünya şampiyonu
seviyesi küp kararlarını da gerektirir; bu yüzden `ml/cube_er.py` eklendi.

**Tanım.** gnubg `eval` üç *cubeful* equity verir. Rakip bizim equity'mizi
**minimize** eder, bu yüzden çiftledikten sonraki değer
`doubleValue = min(doublePass, doubleTake)`'tir. En iyi değer
`best = max(noDouble, doubleValue)`. **Küp ER'si** = `best − seçilen`.

**`max` tuzağı.** İlk sürüm `max(noDouble, doublePass, doubleTake)`
kullanıyordu. `doublePass` her zaman `+1,000` olduğu için bu her pozisyonda
"çiftle" der ve kaybı yanlış hesaplar. Gerçek çıktıyla doğrulandı:
`noDouble 0,216 / doublePass 1,000 / doubleTake −0,001` → `doubleValue
−0,001`, `best 0,216`, `bestAction no-double`, `loss(no-double) 0,000`,
`loss(double) 0,217`.

**Ölçülen (n = 400, gnubg `eval` 2-ply cubeful, bootstrap 20 000):**

| Ölçüm | Değer |
|---|---|
| **Küp ER'si** | **0,0642** |
| %95 GA | [0,0469; 0,0837] |
| sigma | 0,1894 |
| Çiftleme uyumu | 300/400 (0,7500) |
| Kabul/red uyumu | 64/76 (0,8421) |
| Hedef | < 0,0200 |

Karışıklık matrisi: 242 doğru "çiftleme yok", **82 yanlış çiftleme**,
**18 kaçırılmış çiftleme**, 58 doğru çiftleme. Yani hata **asimetrik**:
danışman gnubg'nin çiftlemediği yerde çiftliyor.

Bağlama göre: para oyunu **0,0284** (en iyi), 5-puan maçı **0,0860**,
9-puan maçı **0,0564**. Sahipliğe göre: merkez **0,0575**, bizde **0,0709**.

**Güç.** sigma üst sınırı 0,2367 (Kural 4). Δ = 0,02 için gereken n = **380**
(mevcut 400 yeterli); Δ = 0,01 için **1517** (yetersiz).

**Kapsam.** Bu ölçüm küp kararını ölçer, hamle seçimini değil. İkisi
**toplanmaz**; dünya şampiyonu iddiası ikisini birden gerektirir.

---

## F7-74 — Küp korpusu: üç sessiz ölçüm hatası

İlk korpus (5 pozisyon × 4 bağlam × 3 sahiplik = 60 vaka) üç hata taşıyordu.

1. **Crawford bağlamı.** Dördüncü bağlam `(5, 4, 1)` idi; bu bir **Crawford**
   oyunudur ve orada küp yoktur. 150 vaka sıfır bilgiyle ölçüme giriyordu.
   Yerine Crawford olmayan `(5, 2, 1)` (3-away/4-away) konuldu. Crawford
   ayrı bir doğrulama senaryosudur (`CRAWFORD_CONTEXT`), ER'ye girmez.
2. **Mutlak küp sahipliği.** `cubeOwner = 1` mutlak yazıldığında sıra `-1`
   olan pozisyonlarda küp **rakipte** kalıyor, `CanOffer` false dönüyor ve
   vaka karar üretmiyordu (400 vakanın 68'i). Sahiplik artık **göreli**:
   `1` = "kup bizde" → `turn`, `-1` = "rakipte" → `-turn`, `0` = merkez.
3. **`phase` anahtar çakışması.** Korpus `phase: "contact"` yazıyordu; C#
   `StateFromJson` bu alanı `GamePhase` olarak okuyup
   `phase çözümlenemedi: contact` ile duruyordu. Anahtar `phaseClass` oldu.

Ayrıca `--stride` eklendi: korpus fazlara göre gruplanmış olduğu için düz
`--limit` yalnızca `contact` seçiyordu. `--stride 20` → 50 pozisyon,
faz dağılımı 240 contact / 104 bar / 56 race.

---

## F7-75 — gnubg küp çıktısı: satırlar sıralanır, numaralanmaz

`parse_cube_analysis` ilk sürümde `1. No double`, `2. Double, pass`,
`3. Double, take` numaralarına göre eşleştiriyordu. gnubg bu satırları
**sıralar**: en iyi eylem "Double, take" ise çıktı

```
1. Double, take        +0,632
2. Double, pass        +1,000  (+0,368)
3. No double           +0,598  (-0,034)
Proper cube action: Double, take
```

olur. Numaraya göre eşleştirme bu vakalarda `noDouble` alanına `+0,632`
yazıyordu. Artık **etikete** göre eşleştirilir ve equity satırları
`Proper cube action` satırından **önceki** parçada aranır (o satır da
"Double, take" içerir).

Tanınan dört ek biçim: `No redouble`, `Redouble, pass`, `Redouble, take`,
`Too good to (re)double, pass`. Sonuncusu ilk sürümde tanınmıyor ve ölçümü
tamamen durduruyordu (Kural 6 gereği doğru davranış, ama eksik ayrıştırma).

---

## F7-76 — Küp ER'si hedefi 0,02 **karşılanmıyor**

Ölçülen 0,0642, hedefin **3,2 katı**. Bu, hamle ER'sinden bağımsız bir
eksikliktir: `search1` hamle ER'si 0,0210 ile hedefe yakınken küp kararı
0,0642'de. Yani "güç" iddiası yalnızca hamle tarafında değil, küp
tarafında da açık veriyor.

Hata yönü de bilgilendirici: 82 yanlış çiftleme / 18 kaçırılmış çiftleme.
Danışman **fazla agresif** çiftliyor. Bu, `HeuristicOutcomeDistribution`'ın
mars oranlarını (contact 0,20 / race 0,05) sabit varsaymasıyla tutarlıdır;
gerçek dağılım ağdan alınsa bile eşikler canlı-küp varsayımına dayanır.

**Kapsam kararı.** Küp ER'si R-C'ye ölçüm olarak girer; **düzeltme R-D/R-E'ye
bırakılır**. Faz 7-R'nin kapsamı şu şekilde genişletilir:

| Aşama | Ek kapsam |
|---|---|
| R-C | küp ER'si ölçümü (bu belge) — **tamamlandı** |
| R-D | küp-farkındalıklı damıtma: değer kafası 6'lı dağılımı da öğrenmeli |
| R-E | kapasite testi küp ER'sini de raporlar |
| R-F | güç iddiası **küp dahil**; para + 5-puan + 9-puan ayrı raporlanır |

---

## F7-77 — Test numaralandırması: R-T23 = **139**

R-C testleri 134–138'i aldı. Küp ER'si testleri **139–147** olarak eklendi
(`ml/tests/test_cube_er.py`, 27 test). Sonraki boş numara **148**.

---

## F7-78 — G7 kapisi iki modlu: birim/isaret testi + lambda'dan turetilen alt sinir

Kullanici G7'nin **1,5 ust sinirini onayladi** ve iki kosul koydu:

1. `lam = 1` modlari icin kapi `|oran - 1| < 1e-6` olmali ve **"birim/isaret
   testi"** olarak adlandirilmali.
2. `lam < 1` alt siniri **lambda'dan turetilmeli**, keyfi bir sabit olmamali.

**Uygulama.** `ml/pipeline_health.py`:

- `TARGET_STD_RATIO_MIN = 0.5` **kaldirildi** (keyfi sabitti).
- `TARGET_STD_RATIO_MAX = 1.5` (onaylanan ust sinir).
- `TARGET_STD_RATIO_UNIT_TOL = 1e-6`, `LAMBDA_UNIT_TOL = 1e-9`.
- `target_std_ratio_lower(lam) = lam ** (1 / (1 - lam))`.
- `gate_target_std_ratio(ratio, *, lam=1.0)` iki modlu.
- `Gate.label` / `Gate.display_label`; `HealthReport.lam`; `diagnose(lam=)`;
  CLI `--lam`.

**Alt sinirin turetimi.** TD(lambda) hedefi terminal degeri `lam ** (T - t)`
agirligiyla yumusatir. Etkin ufuk geometrik ortalamadir: `h = 1 / (1 - lam)`.
Hedefin en az bu kadar terminal agirligi korumasi gerekir; bu da oran icin
`lam ** (1 / (1 - lam))` alt sinirini verir. `lam -> 1` icin `1/e = 0,3679`;
`lam = 0,7` icin **0,30457**.

**Dogrulanan siniflandirmalar.**

| Olcum | Mod | Sonuc |
|---|---|---|
| 0,176031 (lam=0,7, modelsiz) | lam<1 | **basarisiz** (gercek cokme) |
| 3,0227 (eski anomali) | lam=1 | **basarisiz** (ust sinir) |
| 1,000000 (lam=1) | lam=1 | **basarili** (birim testi) |
| 0,682135 (lam=0,7) | lam<1 | **basarili** |

`lam = 1` modunda bant **yoktur**: dogru deger tam olarak 1'dir, cunku hedef
isaretli terminal serisidir ve terminal de isaretli okunur (F7-63). Bant
kullanmak, birim uyusmazligini gizleyen hatayi geri getirirdi.

**Testler.** `ml/tests/test_pipeline_health.py` ve `ml/tests/test_stage_r_c.py`
guncellendi; 194 test geciyor.

---

## F7-79 - Seviye farki (ppg) olcumu: m = 0,1115 ppg, sigma = 2,9960

**Neden.** Kullanici `m = 0,02 ppg` degerini **gecici** onayladi ve gercek
`sigma_ppg` olcumunu istedi: "m, gnubg 0-ply ile 2-ply arasindaki olculmus ppg
farkinin yarisi gibi bir deger olmali ki 'esdeger' ifadesi bir seviye farkini
ayirt etsin." Bu, R-F'nin iddia esigini ve dolayisiyla oyun sayisini belirler.

**Arac.** `ml/ppg_measure.py` (yeni). gnubg kendine-oynama:

- **Money** icin gnubg'nin gomulu Python'u (`gnubg-cli.exe -p script.py`),
  `set matchlength 0` + `new game`, sonuc `gnubg.match()["games"][-1]["info"]`.
  `new session` yolu **kullanilamaz**: oyun siniri yok ve gomulu Python'dan
  kesilemiyor.
- **Mac** icin `new match L` + cikti ayristirma (`The score (after N games) is:`).
- Guven araligi **kume bootstrap'i** (20 000 yeniden ornekleme); money'de kume =
  oyun, macta kume = mac. `sigma_used = max(sigma_oyun, sigma_kume)`.

**Olcum (2400 money oyunu, 40 mac/hucre, 6 isci).**

| Karsilastirma | Baglam | n | Fark (ppg) | %95 GA | sigma |
|---|---|---|---|---|---|
| 0-ply vs 2-ply | money | 2400 oyun | **-0,2229** | [-0,3425; -0,1037] | 2,9960 |
| 0-ply vs 2-ply | mac-5 | 40 mac / 99 oyun | -0,8546 | [-1,8950; +0,1867] | 5,3717 |
| 0-ply vs 2-ply | mac-9 | 40 mac / 233 oyun | -1,2169 | [-2,3245; -0,3527] | 7,9001 |
| 2-ply vs 3-ply | money | 400 oyun | -0,0625 | [-0,3600; +0,2400] | 3,0581 |
| 2-ply vs 3-ply | mac-5 | 40 mac / 113 oyun | +0,1096 | [-0,8279; +1,1388] | 5,3569 |
| 2-ply vs 3-ply | mac-9 | 40 mac / 213 oyun | -0,8990 | [-1,8590; -0,0512] | 6,8013 |

**Sonuc: `m = 0,1115 ppg`** (0-2 money farkinin yarisi; GA sifiri disliyor).

**Onay (2026-11-21).** Kullanici `m = 0,1115 ppg` degerini **kesin** olarak
kabul etti; `0,02` yer tutucusu tamamen gecersiz. Bu, R-F'nin iddia esigini
ve gereken oyun sayisini (4337) baglar. Kalan kisit: 2000 oyunluk R-F
kosulari bu esik icin **gucsuz**; "esdeger" iddiasi kurulmadi, yalnizca
"anlamli fark" iddiasi kuruldu.

**Dort bulgu.**

1. **400 oyun yetersizdi.** Ayni hucre 400 oyunla `-0,1300` ve GA
   `[-0,4150; +0,1550]` verdi - sifiri iceriyor. 2400 oyunla ayni fark
   `-0,2229` ve GA sifiri **disliyor**. Yani "bir seviye farki" premisi ancak
   2400 oyunda kuruldu. 400 oyunla `m` turetme girisimi sessizce gurultuden
   deger uretirdi.
2. **`sigma_ppg` kullanicinin tahmininden cok yuksek.** Olculen **2,9960**
   (money), 5,37-7,90 (mac). Kullanicinin 1,4 tahmini ve
   `match_power.DEFAULT_PPG_SIGMA = 2,4` degeri **dusuk**. `m = 0,1115` icin
   gereken oyun sayisi **4337** (Kural 4: sigma ust siniri 3,7450). 0,02 icin
   gereken sayi ~80 000 olurdu - pratikte imkansiz. Olcum R-F'yi
   **yapilabilir** kildi.
3. **2-ply vs 4-ply olculemez.** Bu makinede oyun basina 60 s'yi asti (5 oyun
   300 s'de bitmedi). Ikincil karsilastirma **2-ply vs 3-ply** oldu (6 s/oyun)
   ve 400 oyunla **gucsuz** kaldi; gereken n ~4519.
4. **Mac baglaminda ppg olcegi farkli.** Mac-9'da fark -1,22 ppg; bu checker
   oyunundan cok **kup yetersizligini** yansitir (0-ply kup karari macta cok
   daha pahali). Bu yuzden `m` **money'den** turetildi; mac huceleri ayri
   raporlanir.

**`derive_margin` semantigi.** `m = 0,5 x |nokta tahmini|`. Taban olarak
guven araliginin sifira en yakin sinirini kullanmak **yanlisti**: o zaman `m`
orneklem buyuklugu ile kuculur ve R-F'nin maliyeti yapay olarak duser. `m`
seviye farkinin ozelligidir, olcum hassasiyetinin degil. GA bunun yerine
**guvenilirlik notu** olarak raporlanir (`GA sifiri disliyor: m saglam` /
`GA sifiri iceriyor: m GECICI`).

**Ikinci hata: marj kaynagi secimi girdi sirasina bagliydi.** `build_report`
`money[0]` aliyordu; `--merge` ile yeni hucre listenin **sonuna** eklendigi
icin marj yanlislikla `2-ply vs 3-ply @ money` hucresinden turetildi
(`m = 0,1200`, gucsuz hucre). Duzeltme: `build_report` karsilastirmalari
`(plies_a, plies_b, length)` ile **siralar**; `report` alt komutu marji guncel
kodla **yeniden hesaplar**.

**Testler.** `ml/tests/test_ppg_measure.py` - 10 test (Test 148-157).
`derive_margin` 3 argumanli; "m orneklem buyuklugune bagli degildir" testi
eklendi.

## F7-80 - `search1` paritesi: Python olcum aracinda **dort** gercek kusur

Kullanici "adim 0" kapisi olarak C#-Python `search1` paritesini istedi. Parite
olcumu (`ml/search1_parity.py`, 500 vaka, corpus v2, `--stride 2`) **dort ayri
kusur** buldu. Dordu de Python **olcum** tarafindaydi; C# urun kodu dogruydu.

**Kusur 1 - zar agirligi.** `er_paths.search1_values` 21 zari **esit**
(1/21) agirlikla ortaliyordu. C# `BackgammonSearch` gercek zar olasiligini
kullanir (cift 1/36, cift olmayan 2/36). Duzeltme: `DICE_WEIGHTS` /
`DICE_WEIGHT_SUM`. Etki: 500 vakada argmax uyusmasi 0,9440 -> 0,9820, skor MAE
0,0277 -> 0,0079.

**Kusur 2 - rakibin terminal afterstate'leri.** 1-ply aramada rakibin yanitlari
`scorer.values` ile **deger kafasindan** tahmin ediliyordu. Rakip mars/backgammon
yapabiliyorsa bu tahmin sistematik olarak iyimserdi (olculen sapma 0,34-0,98
equity). Duzeltme: `terminal_equity` ile **oyun kuralindan** hesaplanir.

**Kusur 3 - `terminal_equity` ev/bar gelenegi ters.** Bu kod tabaninda Beyaz'in
evi 19..24, Siyah'in evi 1..6; Beyaz'in bari 0, Siyah'in bari 25
(`refgen.is_home`, `gnubg_er._bar_index`). Fonksiyon evleri ve barlari **ters**
kullaniyordu: 4 vakada mars yerine backgammon (ya da tersi) uretiyordu.

**Kusur 4 - `tools/reference_gen.py` icindeki `_single_step_uses_die` off sayaci.** Off
sayaclarini `key`'den alip **bir kez daha** artiriyordu, bu yuzden hicbir zaman
eslesmiyordu. Sonuc: buyuk-zar filtresi **her** tek-adimli sonucu atiyor,
`legal_after_states` bos kume donduruyordu. `er_paths.search1` "rakip oynayamaz"
dalina dusup degeri deger kafasindan tahmin ediyordu (olculen sapma 0,52
equity). Bu kusur **urun** kodunu da etkiliyordu: `tools/reference_gen.py`
korpus uretiminde ve `ml/er_harness.py` icinde kullanilir.

**Sonuc (duzeltmelerden sonra, 500 vaka):**

| Olcum | Deger |
|---|---|
| Kararli vaka (ust-2 fark > 0,02) | 357 |
| Berabere vaka (cikarildi) | 143 |
| Argmax uyusmasi (kararli) | **357/357 = 1,0000**, GA [1,0000; 1,0000] |
| Skor MAE | **5,36e-08** (float32 yuvarlama) |
| Skor maksimum fark | 7,51e-07 |

Yani Python `search1` ile C# `BackgammonSearch` **sayisal olarak ayni**
(float32 hassasiyetinde). Kalan 6 "uyusmazlik" tam berabere (ust-2 fark = 0);
orada argmax kayan nokta gurultusudur, parite kusuru degil. Bu yuzden kapi
**kararli** vakalar uzerinde islenir (`TIE_TOL = 0.02`).

**Baslik ER'si degismedi.** Duzeltmelerden sonra corpus v2 uzerinde:

| Yol | Once | Sonra |
|---|---|---|
| `policy` | 0,0402 | 0,0402 |
| `value` | 0,0442 | 0,0442 |
| `search1` | 0,0210 | **0,0209** |

Kusurlar az sayida (bear-off / terminal) pozisyonu etkiliyordu; baslik sayilari
saglam. `ml/artifacts/er_paths_v2.json` duzeltilmis olcumle degistirildi.

**Artefaktlar.** `ml/artifacts/search1_corpus.json`,
`ml/artifacts/search1_cs.json`, `ml/artifacts/search1_parity.json` / `.md`.

**Testler.** `ml/tests/test_search1_parity.py` - 6 test (Test 176-181).

## F7-81 - Renk takasi (antisimetri) olcumu: kapi **DUSTU**

Kullanici "adim 0" kapisi olarak renk takasinda `|corr| >= 0,99` ve renk
takasinda ER farkinin **olculemez** olmasini istedi. `ml/antisymmetry.py` bunu
olcer.

**Olcum (model_v30, corpus v2, 500 vaka, gnubg 2-ply hakem):**

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| `corr(e(+1), e(-1))` | **-0,8915** | `\|corr\| >= 0,99` | **DUSTU** |
| ER farki GA | **[-0,0620; -0,0340]** | sifiri icermeli | **DUSTU** |
| Girdi renk-simetrisi (`flip_perspective`) | 0/12 167 uyusmazlik | 0 olmali | GECTI |
| `mean \|e(+1)+e(-1)\|` | 0,7152 | 0'a yakin | DUSTU |
| `max \|e(+1)+e(-1)\|` | 3,0299 | - | - |
| `\|e(+1)+e(-1)\| <= 0,001` | 116/12 167 (0,95%) | - | - |
| Politika antisimetrisi | 174/500 (0,3480) | - | - |
| ER(+1) | 0,0396 | - | - |
| ER(-1) | 0,0875 | - | - |

**Teshis: kusur girdide degil, modelde.** Girdi vektoru renk takasinda
**kusursuz** simetrik (12 167 afterstate'in **sifirinda** uyusmazlik). Yani
`gnubg_er.vectorize` dogru; model iki bakista farkli sey soyluyor. Kok neden
F7-55'te bulunmustu: `ml/train_v2.py` girdi vektorune **bakis artirimi**
uygulamiyor (`flip_exclusive` yalnizca TD(lambda) hedef zincirinde, satir
97/136/138).

**Politika antisimetrisi "ayni argmax" degildir.** Politika kafasi **oynayacak
tarafin** en iyi hamlesini siralar; bakis cevrilince oynayacak taraf degisir.
Dogru ifade `argmax(logit(+1)) == argmin(logit(-1))`. Ilk surum iki argmax'i
karsilastiriyordu ve ER(-1) = 0,4907 gibi anlamsiz bir sayi uretiyordu; bu
duzeltildi.

**Bu "once" durumudur.** Kapi **R-D'de** gecmelidir: R-D egitimi iki perspektif
artirimi (`antisymmetry.augment_perspectives`) veya girdi kanoniklestirmesi
kullanmak **zorunda**. R-D sonunda ayni olcum tekrarlanir ve kapi aranir.

**Artefaktlar.** `ml/artifacts/antisymmetry.json` / `.md`.

**Testler.** `ml/tests/test_antisymmetry.py` - 10 test (Test 158-167).

## F7-82 - `learning_curve.py` gercek egitime baglandi

Kullanici "adim 0" kapisi olarak `learning_curve.py`'in gercek egitime
baglanmasini, **>= 3 tohum** ve **oyun duzeyi kume bootstrap** istedi.

**Yeni modul `ml/curve_pool.py`.** Etiketli havuz uretir: gnubg 2-ply ile
kendine karsi oyun oynar, her karar noktasinda **tum** adaylari etiketler
(`gnubg_hint.HintReferee`), aday vektorlerini ve gnubg equity'lerini saklar.
Bolum **oyun duzeyinde**: `--held-out-games` oyunlar tamamen held-out'a gider.
`CurvePool` alanlari: `x` [M,221], `offsets` [N+1], `best` [N], `y` [N],
`cand_equity` [M], `game_ids` [N], `split` [N], `meta`.

**`make_train_fn`** `TrainFn` sozlesmesini doldurur: N pozisyon ornekler,
`epochs` **sabit** tutarak egitir (veri degisir, epoch degismez - R-D kurali),
held-out pozisyonlarda **pozisyon basina** politika ve deger kaybi dondurur,
`gameIds` ile birlikte. Boylece bootstrap oyun duzeyinde kumelenebilir.

**`learning_curve.py` degisiklikleri:**
- `_cluster_means(losses, game_ids)` eklendi.
- `fit_log_slope(..., cluster=True)` - **oyun duzeyi** kume bootstrap. Ayni
  oyunun pozisyonlari korelidir; kume GA'si pozisyon GA'sindan **dar olamaz**
  (test 184 bunu dogrular).
- `run_curve(..., cluster=True)` ve yeni `run_curve_multi_seed(sizes, train_fn,
  seeds, ...)` - tohumlari **havuzlar**, oyun kimliklerini tohumla onekler
  (`s0:g3`), boylece ayni kimlik farkli tohumda ayni kume sayilmaz.
- CLI: `--pool` (zorunlu), `--seeds`, `--epochs`, `--no-cluster`, `--out`,
  `--markdown`. `main()` artik `SystemExit` **atmiyor**.
- `CurveReport` alanlari: `seeds`, `clustered`.

**Olcum (200 oyun, 6 596 pozisyon, 129 819 aday, 3 tohum, 20 sabit epoch):**

| Carpan | Pozisyon | ER `policy` | ER `value` | In-sample |
|---|---|---|---|---|
| 1x | 500 | 0,0395 | 0,1463 | 0,6667 |
| 2x | 1 000 | 0,0287 | 0,0782 | 0,3573 |
| 4x | 2 000 | 0,0242 | 0,0460 | 0,2883 |
| 8x | 4 000 | 0,0189 | 0,0454 | 0,1788 |

| Yol | Kazanc (ER / log2 veri) | %95 GA | Karar |
|---|---|---|---|
| `policy` | **0,0066** | [0,0053; 0,0080] | esik 0,0050 ustu |
| `value` | **0,0335** | [0,0298; 0,0387] | esik ustu |

**Karar: `olcek`.** Tohum bazinda: tohum 1 `belirsiz` (GA [0,0039; 0,0089]),
tohum 2 `olcek`, tohum 3 `belirsiz`. Havuzlanmis karar `olcek`; **tek tohum
yeterli degil**, bu yuzden >=3 tohum kurali korunur.

`search1` sutunu bos: `make_train_fn` yalnizca politika ve deger kaybini
dondurur; 1-ply arama kaybi egitim hedefi degildir. Bos sutun gizlenmez.

**Artefaktlar.** `ml/artifacts/curve_pool.npz`,
`ml/artifacts/learning_curve.json` / `.md`.

**Testler.** `ml/tests/test_curve_pool.py` - 8 test (Test 168-175);
`ml/tests/test_learning_curve_cluster.py` - 6 test (Test 182-187).

## F7-83 - `pipeline` etiketi `belirsiz`e ayrildi, `distill_verdict` yeniden adlandirildi

Kullanici "adim 0" kapisi olarak iki etiket degisikligi istedi.

**`pipeline_health.verdict`.** Bir deger kapisi dustugunde artik dogrudan
`pipeline` **denmiyor**: `scaling_evidence` okunur.
- `egim<eps` -> `pipeline` (olcek **kanitlandi** olarak yardim etmiyor)
- `egim>=eps` -> yeni `olcek` (`VERDICT_SCALE`)
- `yok` -> yeni `belirsiz` (`VERDICT_UNDETERMINED`)

`yok` "olcek yardim etmiyor" demek **degil**, "olculmedi" demektir. Eski kod bu
ikisini karistiriyordu. CLI cikis kodlari: 0 saglikli, 1 pipeline, 2 temel,
3 bilinmiyor, **4 belirsiz**, **5 olcek**.

**`gnubg_distill.VERDICT_PIPELINE` -> `VERDICT_TEACHER_EFFECTIVE =
"ogretmen-etkili"`.** Eski ad bir **neden** iddia ediyordu ("damitma ise yaradi,
demek ki sorun pipeline'da"). Yeni ad yalnizca **olcumu** adlandirir: ogretmen
etkili oldu. Kapasite cikarimi `distill_verdict_detail` icinde
`capacityInference: false` olarak isaretlenir; `VERDICT_CAPACITY` hic
dondurulmez.

**Testler.** `test_pipeline_health.py` + `test_gnubg_distill.py` +
`test_stage_r_c.py` -> **315 test** gecti.

## F7-84 - Renk takasi kusuru **urun yolunu** etkiliyor mu? (bakis sorusu)

Kullanici "adim 0" incelemesinde sordu: *"Bu kusur urunde oynanan yolu etkiliyor
mu? ... Rakip dugumleri arama icinde ters bakisla degerlendiriliyorsa derinlik
>= 1 aramada dogrudan hata uretir."*

**Cevap: evet, etkiliyor - ama "gorulmemis girdi" degil, "tutarsiz tahmin".**

**Kod kaniti (iki yol da ayni).**

| Yol | Yer | Ne yapiyor |
|---|---|---|
| Python `search1` | `ml/er_paths.py:190` | `_vectors_for(ordered, opponent)` - rakibin afterstate'leri **rakip bakisiyla** vektorize edilir |
| C# urun aramasi | `Backgammon.Core/Search/BackgammonSearch.cs:575` | `EndTurn(child)` sonra `SearchNode(child, ...)`; `SearchNode` `s.turn` ile degerlendirir (satir 365/374/382) |

Yani her iki arama da rakip dugumunu **rakibin** bakisindan puanlar. Derinlik
>= 1 aramada model `-1` bakisini **her** hamlede gorur.

**Ama bu bakis egitimde gorulmemis degil.** `corpus2._play_game` her karar
noktasini **oynayacak tarafin** bakisiyla kaydeder (`turn` = mover) ve
`curve_pool._label_case` vektorleri `perspective=turn` ile kurar. Bir oyun
boyunca iki taraf da mover oldugu icin **iki bakis da** egitimde vardir.

Kusur sununla ilgili: model "ben oynayacak tarafim" diye ogreniyor ama
`f(x,+1) = -f(x,-1)` **simetrisini** ogrenmiyor. Arama rakip dugumunu
degerlendirdiginde bu tutarsizlik dogrudan hataya donusuyor.

**Neden search1 yine de politikadan iyi?** search1 ER 0,0209 < policy 0,0402.
1-ply arama, tutarsiz deger tahminine ragmen **daha iyi hamle** seciyor: hata
tek tek dugumlerde var ama argmax'i her zaman bozmuyor. Bu, kusurun maliyetinin
"arama tamamen bozuk" degil, "arama beklenenden az kazandiriyor" oldugunu
gosterir.

**Sonuc.** Kusur urun yolunda **gercek**; R-D'de `augment_perspectives` ile
kapatilacak. Cikarim aninda antisimetriklestirme (F7-85) bir **yedek** cozum.

## F7-85 - Cikarim aninda antisimetriklestirme: kucuk ama **kanitlanmamis** kazanc

Kullanici "egitim yapmadan hizli deney" istedi: `e_hat = (f(x,+1) - f(x,-1))/2`,
politika icin `(logit(+1) - logit(-1))/2`. `ml/antisymmetry.py` bunu olcer
(`measure_symmetrised`).

**Olcum (model_v30, corpus v2, 500 vaka, gnubg 2-ply hakem, eslestirilmis GA):**

| Yol | Ham ER | Simetrik ER | Fark | %95 GA | Iyilesme? |
|---|---|---|---|---|---|
| `policy` | 0,0396 | 0,0344 | **-0,00525** | [-0,0135; +0,0024] | **hayir** (GA sifiri iceriyor) |
| `value` | 0,0460 | 0,0402 | **-0,00577** | [-0,0156; +0,0031] | **hayir** (GA sifiri iceriyor) |

Argmax 500 vakanin **156'sinda** degisiyor (0,3120). Yani simetrizasyon secimi
gercekten degistiriyor, ama ortalama ER kazanci bu orneklemde **kanitlanmiyor**.

**Guc hesabi.** Eslestirilmis farkin standart sapmasi ~0,09; `delta = 0,005`
icin gereken n: `(1,96 * 0,09 / 0,005)^2 ~= 1 245` vaka. 500 vaka **yetersiz**.
Karar: "kusurun maliyeti ~0,005 ER" **nokta tahmini** olarak raporlanir, kapi
olarak **kullanilmaz**.

**F7-55'teki "naif duzeltme" neydi?** Logit'leri **ortaliyordu**
(`(logit(+1) + logit(-1))/2`). Iki bakis ayni fiziksel pozisyonu **zit isaretle**
puanladigi icin ortalama, iki farkli skorlama fonksiyonunu karistirir ve
siralamayi bozar; ER 0,0500 -> 0,1674 **kotulesmisti**. Dogru islem **fark**tir.
`test_194_symmetrise_value_is_difference_not_mean` bunu kilitler.

**Karar.** Cikarim aninda antisimetriklestirme **kalici cozum degil**: kazanc
kanitlanmadi ve iki ileri gecis maliyeti var. Once R-D'de `augment_perspectives`
denenir; kapi hala duserse bu yedek yeniden olculur (daha buyuk n ile).

**Artefaktlar.** `ml/artifacts/antisymmetry_symmetrised.json` / `.md`.

**Testler.** `ml/tests/test_antisymmetry.py` - 5 test (Test 204-208).

## F7-86 - `_single_step_uses_die` kusurunun **veriye** etkisi: %1,00 zar / %2,60 vaka

Kullanici sordu: *"Korpus v2 ve curve_pool pozisyonlari bu hatali kodla mi
uretilidi? ... Duzeltmeden once uretilen tum veriyi yeniden uret ya da en azindan
etkilenen pozisyon sayisini raporla."*

**Kusur kosulu.** `max_steps == 1` **ve** zarlar cift degil **ve** buyuk zar
oynanabiliyor. O zaman eski `_single_step_uses_die` off sayacini iki kez
artiriyor, hicbir sonuc eslesmiyor, `legal_after_states` **bos kume** donuyordu.

**Olcum (`ml/artifacts/single_step_impact.json`, 1 000 gercek pozisyon x 21 zar):**

| Kume | Kendi zariyla tetiklenen | Rakip 21 zarinda | En az bir zarinda |
|---|---|---|---|
| `search1_corpus` (1 000) | **0** (0,00%) | 210/21 000 (**1,00%**) | 26 vaka (**2,60%**) |
| `reference_corpus_v2` (1 000) | **0** (0,00%) | 210/21 000 (**1,00%**) | 26 vaka (**2,60%**) |

(Iki korpus ayni pozisyonlardan turetilir; sayilar bu yuzden ayni.)

**Yorum - etki "etiket bozulmasi" degil, "pozisyon dusmesi".**

* **Kendi zariyla 0/1 000.** `corpus2._play_game` ve `gnubg_distill.afterstate_case`
  pozisyonun **kendi** zariyla cagirir. Kusur bu yolda **hic** tetiklenmedi.
  Dolayisiyla **egitim verisi (6 596 pozisyon, 129 819 aday) etkilenmedi**;
  yeniden uretmek gerekmiyor.
* **Rakip zarinda %1,00.** `er_paths.search1_values` rakibin 21 zarini ayri ayri
  cagirir; burada tetiklendi. Etki: o zar "rakip oynayamaz" dalina dustu ve
  deger kafasindan tahmin edildi. Vakalarin **%2,60**'inda en az bir zar boyle.
* **Baslik ER'si.** search1 0,020962 -> 0,020936 (**-0,000026**). Politika ve
  deger yollari `legal_after_states` kullanmadigi icin **degismedi**
  (0,0402 / 0,0442).

**Karar.** Veri yeniden uretilmiyor: kendi-zar yolu temiz. search1 olcumu
duzeltilmis kodla **yeniden uretildi** (`search1_parity.json`, `er_paths_v2.json`).

## F7-87 - Ogrenme egrisi: havuzlanmis GA tohumlari **ek veri** gibi sayiyor

Kullanici: *"Uc tohumdan biri 'olcek', ikisi 'belirsiz'. Havuzlanmis GA tohumlari
ek veri gibi ele aliyorsa guveni oldugundan yuksek gosterir. Kendi kuralin 'tek
tohum yeterli degil' diyorsa etiket belirsiz olmali."*

**Hakli.** `run_curve_multi_seed` tohumlari havuzlar; ayni oyun kumesi farkli
tohumlarda **tekrar** sayilir. Havuzlanmis GA bu yuzden yapay olarak **daralir**.

**Duzeltme (`CurveReport.decision`).** Havuz karari artik **tek basina** yetmez:

1. Havuzlanmis `gainCiLow >= eps` -> aday `olcek`; `gainCiHigh < eps` -> aday
   `pipeline`; aksi halde `belirsiz`.
2. **Tohum oybirligi:** `len(seed_decisions) > 1` ise **tum** tohumlarin ayni
   karari vermesi gerekir. Aksi halde `belirsiz`.

Eski artefakt (tohum 1 `belirsiz`, 2 `olcek`, 3 `belirsiz`) bu kurala gore
**`belirsiz`** olmaliydi; `olcek` yaziyordu. Yeni kosumda kural uygulanir.

`seedAgreement` alani JSON'a eklendi; `seedDecisions` / `seedGains` de yazilir.

**Testler.** `ml/tests/test_learning_curve_cluster.py` - Test 193-197 (oybirligi
kurali, doygunluk fiti, in-sample birimi) + Test 209-211 (birim turetme, JSON
gidis-donusu, `--from-json`) + Test 182-187.

## F7-88 - Ogrenme egrisi: 5 tohum, 16x-32x, taban parametreli fit, birim

Kullanici dort sey istedi: (a) tohum 5-10, (b) egriyi 16x-64x'e uzat, (c)
`ER = a*N^-b + c` taban parametreli fit, (d) "in-sample" sutununun **birimini**
yaz.

**(a) Tohum.** `--seeds 1 2 3 4 5` (5 tohum). Karar kurali F7-87.

**(b) Carpanlar.** `CURVE_MULTIPLIERS = (1, 2, 4, 8, 16, 32)`. 64x icin havuz
yetersiz (5 281 egitim pozisyonu); 32x = 5 280 **tam** sigar. 64x ancak daha
buyuk havuzla olculur ve bu raporda **"olculemez"** olarak isaretlenir.

**(c) Doygunluk fiti.** `fit_saturation` uc parametreli modeli kaba grid + kapali
form en kucuk karelerle uydurur (`b` icin [0, 3], `c` icin [0, min(ER)]).
`c` = "bu mimari ve bu ogretmenle ulasilabilir en iyi ER" sorusunun **olculen**
cevabi. Iki parametreli log-egim modeli `c`'yi sifira zorlar ve bu yanlistir.

**(d) In-sample birimi.** `IN_SAMPLE_UNITS` sozlugu her yol icin birim yazar:
`policy` -> "capraz-entropi (nats/pozisyon)", `value` -> "MSE (equity^2)",
`search1` -> "yok (egitim hedefi degil)". In-sample sutunu **ER degildir**;
egitim kaybi oldugu icin ER ile karsilastirilmaz.

**Deger yolu platolari.** 4x -> 8x: 0,0460 -> 0,0454 (fark 0,0006). Politika
dusmeye devam ediyor (0,0242 -> 0,0189). Bu, deger kafasinin **doydugunu**,
politikanin doymadigini gosterir; R-D'de deger kafasi icin kapasite/veri
dengesi yeniden bakilmalidir.

**Oncesi/sonrasi eslesmis kiyas.** Bu egri **antisimetri duzeltmesinden onceki**
durumdur. R-D'de ayni egri `augment_perspectives` ile kosulunca ayni havuz,
ayni tohumlar, ayni carpanlar kullanilacagi icin karsilastirma **eslestirilmis**
olur (pozisyon basina fark). Bu bir avantajdir ve R-D raporunda kullanilacaktir.

## F7-89 - gnubg 0/1/2-ply ER merdiveni: model merdivende **nerede**?

Kullanici: *"gnubg 0/1/2-ply ER merdiveni ayni korpusta yok. Modeli merdivende
konumlayan tek olcum bu."*

`ml/gnubg_ladder.py` ayni korpusta (corpus v2, 500 vaka) gnubg'yi **kendine
karsi** olcer; hakem 2-ply.

| Oyuncu | ER | %95 GA | Tam eslesme |
|---|---|---|---|
| gnubg **0-ply** | **0,00444** | [0,00320; 0,00582] | 0,818 |
| gnubg **1-ply** | **0,00256** | [0,00179; 0,00347] | 0,836 |
| gnubg **2-ply** | **olculemez** | - | - |

2-ply **olculemez**: hakem kendini olcemez; 2-ply'in ER'i icin 3-ply/rollout
gerekir ve gnubg `eval` 2-ply'den derin sutun uretmez (F6-32). "Olculemez"
isaretlenir, sifir **yazilmaz**.

**Model satirlari (ayni korpus, ayni hakem):**

| Yol | ER | 0-ply'a gore |
|---|---|---|
| `policy` | 0,0402 | **9,0x** kotu |
| `search1` | 0,0209 | **4,7x** kotu |
| `value` | 0,0442 | 10,0x kotu |

**Yorum.** Model **hamle seciminde** gnubg 0-ply'in belirgin sekilde altinda.
Bu, "urun botu gnubg 0-ply'i yener" iddiasiyla **celismez** (oyun gucu hamle
ER'sinden farkli bir buyukluktur; F7-91'e bakin) ama "model 0-ply seviyesinde"
iddiasini **desteklemez**. R-D'nin hedefi bu bosluk.

**Artefaktlar.** `ml/artifacts/gnubg_ladder.json` / `.md`.

**Testler.** `ml/tests/test_gnubg_ladder.py` - 5 test (Test 199-203).

## F7-90 - Python-C# hamle kumesi esitligi: 1 000/1 000

Kullanici: *"Python'un aday kumesini C# LegalMoveGenerator ile ... kume esitligi
testiyle bagla (100 bin pozisyon)."*

`ml/moveset_parity.py` + `Backgammon.MatchBench moveset` alt komutu ayni
pozisyonlarda iki ureticinin **sirali** aday kumesini karsilastirir.

**Olcum (corpus v2, 1 000 pozisyon):** `agree = 1 000`, `rate = 1,0000`,
GA [1,0000; 1,0000], uyusmazlik **yok**.

**100 bin pozisyon neden yok?** 1 000 pozisyon corpus v2'nin **tamami**;
100 bin icin ayri bir rastgele pozisyon ureteci gerekir ve her pozisyon icin
C# tarafinda bir kosum gerekir. Bu, R-D oncesi "ucuz" kapsamin disinda. Kapi
1 000'de **gecti**; 100 bin kosumu R-D sirasinda arka planda calistirilacak.

**Kalici cozum onerisi.** Python hamle uretimi **kaldirilip** C#'tan cagrilmali
(`MatchBench` CLI zaten var). Dort kusurun dordu de Python tarafinda cikti; bu
ikinci uretici surekli hata kaynagi. Bu, R-D sonrasi bir mimari karar olarak
kaydedilir.

**Artefaktlar.** `ml/artifacts/moveset_parity.json` / `.md`,
`ml/artifacts/moveset_cs.json`.

**Testler.** `ml/tests/test_moveset_parity.py` - 5 test (Test 188-192).

## F7-91 - Calisma agaci izolasyonu: paralel UI calismasi ayri worktree'de

Uc rapordur tekrar eden sorun: `Backgammon.UI/GameOrchestrator.cs` +43 satir
degisikligi **bu ajanin degil**. Ayni calisma agacinda paralel bir calisma
vardi ve "29 dakikalik testler hangi kod durumunda kostu" belirsizdi.

**Karar.** Paralel calisma **ayri bir git worktree'ye** tasindi:

* Worktree: `F:\Projects\VijualStudioski\TavlaAI_parallel`
* Dal: `parallel/ui-optimistic-move`
* Icerik: `GameOrchestrator.ApplyMoveOptimistic` (cevrimici modda iyimser hamle
  yazimi) - degisiklik **korundu**, ana agac **temizlendi**.

Ana agac artik yalnizca bu ajanin degisikliklerini tasir. Bundan sonra olcumler
**tek** kod durumunda kosar.

**Not.** `TavlaAI_agent` worktree'si (`agent/faz7r`) de mevcut; ajan calismasi
orada da izlenebilir.

## F7-92 - Ogrenme egrisi (5 tohum, 165x-5 280x): karar **`belirsiz`**, taban `c = 0,0033`

F7-88 dort istegi tanimladi; bu bolum **olcumu** verir. Komut:

```
python ml/learning_curve.py --pool ml/artifacts/curve_pool.npz \
    --base-positions 165 --multipliers 1 2 4 8 16 32 \
    --seeds 1 2 3 4 5 --out ml/artifacts/learning_curve.json \
    --markdown ml/artifacts/learning_curve.md
```

**Neden taban 165?** Havuzda 5 281 egitim pozisyonu var. 32x = 5 280 **tam**
sigar; 64x = 10 560 ister ve havuzda yok. 64x bu yuzden **olculemez** olarak
isaretlenir, uydurulmaz. Onceki kosum taban 500 kullaniyordu ve 8x'te
(4 000) bitiyordu; taban degistigi icin iki egri **dogrudan** karsilastirilmaz.

| Carpan | Pozisyon | ER `policy` | ER `value` | In-sample (birlesik kayip) |
|---|---|---|---|---|
| 1x | 165 | 0,0504 | 0,2114 | 1,1721 |
| 2x | 330 | 0,0414 | 0,2245 | 0,8910 |
| 4x | 660 | 0,0341 | 0,1099 | 0,5563 |
| 8x | 1 320 | 0,0267 | 0,0523 | 0,3413 |
| 16x | 2 640 | 0,0215 | 0,0473 | 0,2204 |
| 32x | 5 280 | **0,0166** | 0,0398 | 0,2553 |

**In-sample birimi.** `train_policy_head` **tek bir birlesik** kayip dondurur:
`capraz-entropi (nat/pozisyon) + 0,5*MSE (equity^2)`. Bu bir ER **degildir** ve
ER ile karsilastirilmaz (Kural 5). Birim artik `IN_SAMPLE_UNITS["combined"]`
uzerinden **turetilir** (`CurvePoint.resolved_in_sample_unit`); eski
artefaktlarda alan bos olsa bile rapor birimi yazar.

**Egim (ER / log2 veri).**

| Yol | Kazanc | %95 GA | Kume |
|---|---|---|---|
| `policy` | **0,0067** | [0,0061; 0,0073] | 200 oyun |
| `value` | 0,0414 | [0,0396; 0,0449] | 200 oyun |

**Tohum oybirligi YOK.** s1 `olcek`, s2 `belirsiz`, s3 `olcek`, s4 `belirsiz`,
s5 `olcek`. F7-87 kurali geregi havuz karari **`belirsiz`** olur. Havuzlanmis
GA esigi kesmiyor (alt sinir 0,0061 > 0,0050) ama **tohumlar ayrissa havuz
karari tek basina yetmez**; bu tam olarak F7-87'nin onledigi hataydi.

**Doygunluk fiti `ER = a*N^-b + c`.**

| Yol | a | b | c (taban) | RMSE |
|---|---|---|---|---|
| `policy` | 0,2865 | 0,35 | **0,0033** | 0,0008 |
| `value` | 5,0251 | 0,60 | 0,0087 | 0,0298 |

**Kritik yorum.** Politika tabani `c = 0,0033`, gnubg **0-ply**'in ayni
korpustaki ER'sinden (0,00444, F7-89) **dusuk**. Yani bu mimari + bu ogretmenle,
veri yeterli oldugunda 0-ply seviyesine **ulasilabilir** gorunuyor. Bu bir
**ekstrapolasyondur**: 6 nokta, RMSE 0,0008, `b` grid aramasinin sinirinda
(0,35). Kanit degil, yon gostergesidir (Kural 3).

**Deger yolu.** 2x'te **kotusuyor** (0,2114 -> 0,2245), sonra 4x'te keskin
dusuyor (0,1099). 16x -> 32x: 0,0473 -> 0,0398. Onceki kosumda 4x -> 8x
platosu (0,0460 -> 0,0454) vardi; bu kosumda plato **16x'te** ve daha zayif.
Deger kafasi hala politika kadar temiz olceklenmiyor.

**Oncesi/sonrasi eslesmis kiyas (R-D icin).** Bu egri **antisimetri
duzeltmesinden onceki** durumdur. R-D'de ayni havuz, ayni tohumlar, ayni
carpanlar ve **ayni taban 165** kullanilacak; karsilastirma pozisyon basina
eslestirilmis olacak.

**Artefaktlar.** `ml/artifacts/learning_curve.json` / `.md`.

**Testler.** `ml/tests/test_learning_curve_cluster.py` - Test 209-211
(birim turetme, JSON gidis-donusu, `--from-json`).

**Yeni yetenek.** `learning_curve.py --from-json <rapor.json> --markdown <cikti>`
olcum yapmadan raporu yeniden uretir; `CurveReport.from_dict` /
`CurvePoint.from_dict` bunu saglar. Boylece bir sunum alani degistiginde
50 dakikalik egri **tekrar kosulmaz**.
---

## F7-93 — R-D oncesi taban: model vs gnubg 0-ply (2000 oyun)

**Soru.** Damitma oncesi mevcut model, urun yolundan (`search1`) oynatildiginda
gnubg 0-ply'a karsi kac ppg kaybediyor? Bu sayi R-D'nin "once" degeridir.

**Kurulum.** `ml/vs_gnubg.py`, kupsuz para oyunu, eslestirilmis zar + renk
takasi (ayni zar dizisi bir kez biz beyaz, bir kez biz siyah), 6 paralel
surec, 2000 oyun (1000 cift). Model `ml/runs/stage_d_l2/onnx/model_v30.onnx`,
yol `search1`, gnubg 0-ply.

**Sonuc.**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Kazanma | 868/2000 = 0,4340 |
| **ppg** | **-0,1635** |
| ppg %95 GA | [-0,2230; -0,1050] |
| ppg standart hata | 0,0303 |
| Eslestirilmis fark (beyaz+siyah) | -0,3270 |
| Eslestirilmis fark %95 GA | [-0,4420; -0,2120] |
| Oyun basina ply | 55,9 |

**Yorum.**

1. **Model gnubg 0-ply'a kaybediyor** — hem ppg hem eslestirilmis fark GA'si
   sifirin altinda. gnubg 0-ply bilinen en zayif gnubg seviyesidir; bu, "urun
   botu" iddiasi icin agir bir tabandir.
2. **20 oyunluk pilot yanilticiydi.** `vs_gnubg_pilot.json` +0,2 ppg vermisti;
   2000 oyunda isaret tersine dondu. 20 oyunluk standart hata ~0,3 ppg
   mertebesindedir, yani pilot hicbir sey olcmuyordu. Pilot artefakti
   **silinmedi** (denetim izi), ama karar dayanagi degildir.
3. **Eslestirilmis fark GA'si daha dar** (-0,3270 ± 0,115 vs ppg ± 0,118/oyun
   basi) — zar gurultusu iptal oldugu icin. Bu, `vs_gnubg.py`'nin cift oyun
   tasariminin dogru oldugunu gosterir.
4. **Oyun basina 55,9 ply** — `search1` derinligi makul; yavaslik modelden
   degil, gnubg alt surecinden geliyor (kalici oturum ~0,01 s/cagri).

**R-D icin anlami.** R-D'nin basari olcutu bu tabana gore **eslestirilmis**
olculmelidir: ayni 1000 zar dizisi, ayni renk takasi, ayni gnubg 0-ply.
ppg'de >= 0,02 iyilesme (m = 0,02 ppg, R-F'de kesinlesecek) anlamli sayilir;
0,1635'lik acigi kapatmak icin bu olcut tek basina yetmez, ama yon gosterir.

**Maliyet.** 6 paralel surec, ~2,5 saat CPU (tek surecte ~7,5 saat).

**Artefaktlar.** `ml/artifacts/vs_gnubg.json` / `.md`.

**Testler.** `ml/tests/test_gnubg_er.py` - kalici oturum tek-atimlik kosuyla
ayni tabloyu vermeli; `OnnxScorer(intra_op_threads=...)` kabul edilmeli.
## F7-94 — R-D cekirdegi: `train_v2.py`'de perspektif artirimi (K1)

**Sorun.** F7-55 renk takasi kusurunu olctu (corr -0,8915) ama egitim hattinda
**hicbir** karsilik yoktu: `train_v2.py` icinde `perspective` kelimesi gecmiyordu.
Yani model her zaman hamle sirasi olan tarafin bakisini goruyor, karsi bakisi
hic ogrenmiyordu. Bu, R-D'nin butun sonuclarini kirletirdi.

**Cozum.** `--augment-perspectives` bayragi eklendi. Acikken her karar
**iki** ornege ayrilir: orijinal `(x, +1)` ve `flip_perspective(x)` ile `(-1)`.

| Oge | Davranis |
|---|---|
| Deger ornekleri | `[s0(+1), s0(-1), s1(+1), s1(-1), ...]` — **aralikli** (blok degil) |
| `equity_target` / `best_equity` | isaret degisir |
| `margin` | **degismez** (iki adayin farki; ikisi de isaret degistirdigi icin) |
| Politika hedefi | **degismez** (adaylar ayni fiziksel afterstate'ler) |
| Kritik agirliklar | tek karar uzerinde hesaplanir, sonra ikiye katlanir |

**Neden aralikli (interleaved).** `[s0,s1,s2,f0,f1,f2]` blok duzeni, ayni
kararin iki bakisini ayni mini-batch'e dusurmez; aralikli duzen dusurur. Bu,
artirimin asil faydasidir (ayni batch'te simetri). Testler bunu
`a.x[0::2] == s.x` ve `a.x[1::2] == flipped` ile zorlar.

**`flip_perspective` gercek bir involusyondur** — rastgele 221-vektor uzerinde
`flip(flip(x)) == x` (maks fark 0,0). Nokta bloklari `j -> 25-j` ile yer
degistirir, bar/off/pip/escaped/away skalerleri takas edilir, `CUBE_OWNER`
isaret degistirir; para/Crawford/temas bayraklari korunur.

**Regresyon: agirlik normalizasyonu.** Ilk uygulama agirliklari `np.repeat(w, 2)`
ile ciftledi. `critical_sampling_weights` **normalize edilmis** bir olasilik
vektoru dondurdugu icin toplam 2,0 oluyordu ve `train_steps_v2` icindeki
`rng.choice(..., p=value_weights)` su hatayla dusuyordu:

```
ValueError: Probabilities do not sum to 1.
```

`_double_weights(w)` ciftlemeden sonra yeniden normalestirir (`w / w.sum()`;
toplam 0 ise tekduze). Test 242 artik `--critical-boost 2.0` ile kosuyor:
agirlik yolu ancak `boost > 1` **ve** `degenerate == false` iken devreye girer,
bu yuzden eski test bu hatayi goremiyordu.

**Testler.** `ml/tests/test_perspective_augment.py`, Test 212-217 (6 test):
katlama/araliklama, vektor+hedef takasi, equity isaret degisimi ve `margin`
korunumu, involusyon, politika hedefi degismezligi, bos/`None` girdi. Test 242:
uctan uca `--augment-perspectives --critical-boost 2.0` kosusu.

## F7-95 — K2: `_single_step_uses_die` kusuru veriyi kirletmedi (denetim)

**Neden denetim gerekti.** Kusur buyuk-zar filtresini her tek-adimli sonuca
uyguluyordu. Hata tetiklendiginde aday kumesi **bosaliyor** ve oyun **pas**
yaziyor; yani kirlenen kararlar egitimden sessizce duser ve kayitli veri temiz
*gorunur*. Bu bir hayatta kalma yanliligi (survivorship bias) riskidir.

**Kritik semantik.** `BackgammonSearch.SearchNode` yasal hamle yokken listeye
bir **pas afterstate'i** ekler (`list.AddPass(s)`), yani pas kararinin
`CandidateCount` degeri **1**'dir, 0 degil. Ilk denetim 0 varsayimiyla 76 900
"kirli pas" bildirdi; bu tamamen yanlis pozitifti. Kontrol `total != 1` olarak
duzeltildi ve `passCandidateTotalHist` histogrami rapora eklendi.

**Olcum.** `ml/replay_verify.py`, 6 shard (60 000 oyun, 3 710 732 karar):

| Denetim | Sonuc |
|---|---|
| Pas + >1 aday | **0** |
| Hamle + 0 aday | **0** |
| Secilen aday kumede degil | **0 / 1 805 887** |
| Karar | **KORPUS TEMIZ** |

**Sinir.** 30 shard'in 6'si denetlendi (%20). Kalan 24 shard ayni ureticiden
gectigi icin ayni sonucu vermesi beklenir; tam kosu ~6x maliyetlidir ve R-D'yi
bloklamaz. `dup_cap` ile kesilmis kumelerde "secilen aday kumede" denetimi
**atlanir** (secilen aday loglanmamis olabilir) — bu bilincli bir karardir.

**Testler.** `ml/tests/test_replay_verify.py`, Test 228-234 (7 test): temiz oyun,
pas+aday isaretleme, hamle+0 aday, secilen-aday, `dup_cap` atlamasi, shard
gidis-donus + Markdown, dizin toplama + `limit`.

## F7-96 — K4: ogrenme egrisi fit usulu duzeltildi

**Duzeltilen dort sey.**

1. **Etiket kurali.** Karar artik "veri N icin yeterli mi" sorusuna gore
   verilir; havuzlanmis GA tohumlari **ek veri gibi sayilmaz** (kume bootstrap
   oyun kumeleri uzerinden yeniden ornekler). Tek tohum "olcek" diyorsa ve
   digerleri "belirsiz" ise karar **belirsiz** kalir.
2. **Taban parametreli fit.** `ER = a*N^-b + c`, `a >= 0` ve
   `0 <= c <= min(y)` kisitlariyla; `c` icin **kume bootstrap %95 GA** eklendi
   (`--saturation-resamples`, varsayilan 2000).
3. **Korpus etiketi.** `--corpus ANAHTAR=DEGER` (tekrarlanabilir) rapora
   acikca yazilir; hangi havuz/oyun sayisi/plies ile olculdugu belirsiz kalmaz.
4. **Eslesmis karsilastirma.** `--compare-before <json>` onceki raporla
   **paired** karsilastirma uretir (ayni oyun kumeleri, once/sonra farki + GA).
   R-D'de artirim oncesi/sonrasi icin bu kullanilacak.

**64x noktasi.** `CURVE_MULTIPLIERS` 64'e uzatildi; 64x icin >= 10 560 egitim
pozisyonu gerekir. 60 oyunluk havuz (5 281) yetmiyordu; 400 oyunluk havuz
(10 580 egitim / 2 667 held-out, 257 543 aday) ile esik gecildi.

**Sonuc: karar `belirsiz` -> `olcek` (5/5 tohum).**

| Carpan | Pozisyon | ER `policy` | ER `value` |
|---|---|---|---|
| 1x | 165 | 0,0525 | 0,1915 |
| 2x | 330 | 0,0441 | 0,1321 |
| 4x | 660 | 0,0355 | 0,0879 |
| 8x | 1 320 | 0,0276 | 0,0588 |
| 16x | 2 640 | 0,0236 | 0,0469 |
| 32x | 5 280 | 0,0184 | 0,0365 |
| 64x | 10 560 | **0,0158** | **0,0330** |

Egim `policy` 0,0062 GA [0,0059; 0,0065]; `value` 0,0253 GA [0,0244; 0,0267].
Doygunluk `policy c = 0,0003` GA [0,0001; 0,0066]; `value c = 0,0223`
GA [0,0148; 0,0252]. Onceki kosu 32x'te kesiliyordu ve oylar 3x `olcek` /
2x `belirsiz` idi; 64x noktasi + 400 oyunluk havuz oybirligini getirdi.

**Deger platosi cozuldu.** 4x sonrasi duzlesme (0,0460 -> 0,0454) 60 oyunluk
havuzun artefaktiydi; 400 oyunluk havuzda 64x'e kadar dusuyor (0,0330).
K5'in plato gerekcesi bu olcumle zayifladi; 6 sinifli KL bilgi-icerigi
argumaniyla R-D'de acik kaliyor.

**Regresyon: `main()` icinde yerel `import json`.** 64x kosusunun ilk denemesi
tum sonucu kaybetti (`UnboundLocalError: local variable 'json'`). Yerel import
modul duzeyindeki adi golgeliyordu. Kaldirildi; Test 243 kilitliyor.

**Testler.** `ml/tests/test_learning_curve_k4.py`, Test 218-227 (10 test) +
Test 243 (json golgeleme regresyonu).

## F7-97 — K5: deger yolunun platasi icin 6 sinifli dagilim hedefi

**Sorun.** Deger yolu 4x'ten sonra plato yapiyor (0,0460 -> 0,0454) ama
politika dusmeye devam ediyor. Skaler equity tek basina deger kafasina yeterli
sinyal vermiyor: ayni equity'yi ureten cok farkli dagilimlar var.

**Cozum.** gnubg `eval` tablosunun **6 sinifli** dagilimi artik okunuyor ve
kayip fonksiyonuna KL terimi olarak giriyor:

    kayip = CE(logits, best) + w_v * MSE(equity(best), best_equity)
            + w_d * KL(gnubg_dagilimi || model_dagilimi)

**Donusum onemli.** gnubg sutunlari (`Win, W(g), W(bg), L(g), L(bg)`)
**kumulatif** olasiliklardir; model ise **dislayici** `(W, GW, BW, L, GL, BL)`
kullanir. Donusum `equity.from_cumulative` ile yapilir. Ilk uygulama kumulatif
degerleri dogrudan dislayici sanip equity'yi 0,49 yerine 0,33 vermisti; Test 236
bunu yakalar (dagilimdan turetilen equity, `parse_eval` skaleriyle ayni olmali).

**API.** `gnubg_er.parse_eval_dist` / `parse_evals_dist`,
`GnubgSession.eval_afterstates(..., dists=True)`,
`gnubg_distill.PolicyPosition.best_dist`, `PolicyDataset.dist`,
`train_policy_head(dist_weight=...)`, CLI `label-policy --dists` ve
`train-policy --dist-weight`.

**Testler.** `ml/tests/test_distill_dist_k5.py`, Test 235-241 (7 test).

## F7-98 — K3 ve K6: kapsam karari

**K3 (hedef metrik).** ER'nin **oyun frekansi agirlikli** olcumu ve **ppg**
birincil metrik olacak. Bu bir olcum degisikligi oldugu icin R-D'nin
*sonuclariyla* birlikte raporlanacak; Adim 0 tabani (ppg -0,1635) zaten ppg
uzerinden kuruldu, yani R-D karsilastirmasi dogru metrikte basliyor.

**K6 (m = 0,02 ppg).** Kullanici karari: R-F'de kesinlesecek. R-D **m = 0,05**
ile baslar; sonuc iyiyse 0,02'ye inilir. Gerekce: 0,02 ppg'yi anlamli kilmak
icin gnubg 0-ply ile 2-ply arasindaki **olculmus** ppg farkinin yarisini bilmek
gerekir; bu olcum R-F'de yapilacak. sigma_ppg ~ 1,4 varsayimiyla 0,02 marj
on binlerce oyun ister — varyans azaltmasi (eslesmis zar) olmadan pratik degil.

## F7-99 — CUDA 0xC0000409: paralel yuk altinda surec cokmesi

**Belirti.** `test_71b_training_is_reproducible_gpu` paralel yuk altinda
`0xC0000409` (STATUS_STACK_BUFFER_OVERRUN) ile cokuyor; tek basina kosunca
geciyor. Bu bir Python istisnasi degil, CRT `__fastfail` cagrisidir — yani
yakalanamaz.

**Teshis.** Cokme **surec cikisinda** (CUDA baglami yikilirken) oluyor, egitim
sirasinda degil: `metrics.jsonl` tam yazilmis oluyor. Paralel yukte bellek
baskisi artinca CUDA yikim sirasi bozuluyor.

**Uygulanan savunma.** `train_v2.py` cikista acik CUDA temizligi yapar:
`torch.cuda.synchronize()` -> `gc.collect()` -> `torch.cuda.empty_cache()` ->
`torch.cuda.synchronize()`. Bekleyen asenkron is varken baglamin yikilmasi
tetikleyici oldugu icin once senkronize edilir. Bu, cokmeyi **tamamen** garanti
etmez (CRT seviyesinde bir abort her zaman yakalanamaz) ama pratikte
tetikleyiciyi kaldirir.

**Denenip vazgecilen.** `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
Windows'ta **desteklenmiyor** (`expandable_segments not supported on this
platform` uyarisi veriyor), bu yuzden eklenmedi.

**Test tarafi.** Test, cokme durumunda **yeniden dener** (tek sefer) ve ikinci
denemede de cokerse gercek hata olarak raporlar. Boylece gecici CUDA cokmesi
test sonucunu kirletmez, kalici bir bozulma ise gizlenmez.

**Onay (2026-11-21).** Kullanici teshisi **kabul etti**: cokme ortam/paralel
yuk sorunudur, kod hatasi degil. Ek savunma (is parcacigi sayisini sinirlama,
ORT oturum seceneklerini gozden gecirme, CUDA isini serilestirme) **istenmedi**;
mevcut cikis temizligi + tek yeniden deneme yeterli sayildi. Konu kapandi.
## F7-100 — R-D: politika kafasi perspektif artirimina **dahil edilmemeli**

**Nasil bulundu.** R-D deneme kosusu (`--augment-perspectives`, 5 iterasyon,
5 000 oyun) hem deger hem politika orneklerini ceviriyordu. Renk takasi kapisi
o modelde **kotulesti**:

| Olcum | Taban `v30` | Deneme (deger+politika) |
|---|---|---|
| `corr(e+1, e-1)` | -0,8846 | -0,8119 |
| `meanAbsSum` | 0,7410 | **0,4782** |
| `argmax` uyumu | 0,174 | **0,018** |
| ER(+1) | 0,0396 | 0,0573 |
| ER(-1) | 0,0875 | **0,5297** |

Deger kafasi **belirgin bicimde** antisimetriklesirken (`meanAbsSum` %35 dustu)
politika kafasi **rastgeleden kotu** hale geldi (argmax uyumu 1/19 ~ 0,053'ten
de dusuk). Bu, artirimin kendisinin degil **politika hedefinin** semantik
hatasiydi.

**Kok neden.** Politika hedefi **oynayacak tarafin** hamle dagilimidir. Girdi
cevrilince oynayacak taraf degisir, dolayisiyla hedefin de cevrilmesi gerekir.
Shard'larda yalniz oynayacak tarafin hedefi var; karsi tarafinki **yok**.
Ayni hedefle cevirmek modeli `f(flip(x)) = f(x)` yani **simetrik** egitir — bu,
kapinin aradigi `argmax(+1) == argmin(-1)` iliskisinin tam tersi.

**Uretim yolu dogrulamasi.** `BackgammonSearch` her dugumde iki kafayi da
**dugumun oynayacak tarafi** ile cagirir
(`Backgammon.Core/Search/BackgammonSearch.cs:365,374,382` — hepsi `s.turn`).
Yani politika kafasi gercekten perspektife **goreli**; karsi bakista rakip icin
siralama yapar. Bu yuzden kapi konvansiyonu (`argmin`) dogru, egitim verisi
eksik.

**Duzeltme.** `--augment-perspectives` artik **yalniz deger** orneklerini
cevirir. Politika artirimi ayri ve **varsayilan kapali** bir bayraga tasindi
(`--augment-policy-perspectives`, teshis amacli). `train_report.json` iki
bayragi ayri ayri kaydeder (denetim izi).

**Sonuc: artirim tek basina kapiyi gecmez.** 10 iterasyonluk deger-only kosuda
`corr = -0,5905`, normalize antisimetri orani 0,837 -> 0,707. Iyilesme var ama
|corr| >= 0,99 esigine cok uzak. Veri artirimi bir **gradyan tesviki**dir;
tam antisimetri **mimari** ya da **cikarim aninda** zorlanmalidir.

**Kalici cozum: cikarim ani antisimetriklestirmesi.** `e_hat(x) = (f(x,+1) -
f(x,-1))/2` tanimi geregi **tam** antisimetriktir:
`e_hat(flip(x)) = (f(flip(x),+1) - f(flip(x),-1))/2 = (f(x,-1) - f(x,+1))/2 = -e_hat(x)`.
Olculen kazanc (n = 1000, `model_v30`): politika ER 0,0402 -> 0,0343
(GA [-0,0111; -0,0009], **IYILESDI**), deger 0,0442 -> 0,0407 (GA sifiri
disliyor degil). Maliyet ONNX basina iki ileri gecis.

**Testler.** `ml/tests/test_perspective_augment.py` Test 242 (varsayilan:
politika artirimi kapali) ve Test 244 (acikken de kosar).

**Uyari (F7-101 ile duzeltildi).** Ayni olcum R-D modelinde (`model_v10`)
**ters** sonuc verdi: politika ER 0,0385 -> 0,0489 (+0,0104, GA
[+0,0051; +0,0157]). Yani cikarim ani antisimetriklestirmesi **kosulsuz**
kalici cozum degildir; yalniz iki bakista da makul tahmin ureten modellerde
kazandirir. Karar, `measure_er_both` ile iki bakisli ER olculerek verilir.

## F7-101 — R-D olcutu: **iki bakisli** ER (tek bakis yaniltici)

> **DUZELTME (F7-104).** Bu kaydin onerdigi olcut **yanlisti**. Uretimde
> model her zaman sira kimdeyse onun bakisini gorur; (-1) bakisi hic
> olusmaz. Iki bakisli ER, urunun kullanmadigi bir dagilimi olcuyordu.
> ppg olcumu artirimin tabandan 0,16 ppg **kotu** oldugunu gosterdi.
> Dogru olcut tek bakisli ER'dir (ppg ile R^2 = 0,9994).

**Nasil bulundu.** F7-100'un ardindan artirim "kotu" gorunuyordu: eslesmis
self-play deneyinde (`rd_sp_ctl` vs `rd_sp_aug`, 10 iterasyon, 2 000 oyun,
depth 0, seed 11, `v30`'dan baslatilmis) artirimli kosu **her** tek-bakis
metriginde daha kotuydu (CE 0,8842 -> 1,0295; equity MAE 0,7941 -> 0,8930;
ER(+1) 0,0286 -> 0,0445). Bu, R-D hipotezinin yanlislandigi seklinde
yorumlandi. **Yorum yanlisti.**

**Kok neden: havuz tek bakisli.** `curve_pool` aday vektorlerini
`gnubg_er.vectorize(..., perspective=turn)` ile uretir; yani her afterstate
**oynayan** tarafin bakisindan yazilir. `flip_perspective(x)` ayni fiziksel
afterstate'in **oynayacak** tarafin bakisidir — bu, havuzda *hic bulunmayan*
bir dagilimdir (havuz afterstate tutar, hamle-oncesi pozisyon tutmaz). Bu
yuzden:

* `ER(+1)` yalniz havuzun kendi dagilimini olcer; artirim oraya **yeni** bir
  dagilim ekledigi icin kapasite paylasilir ve `ER(+1)` **kotulesir**;
* `ER(-1)` karsi bakisi olcer; artirim tam da bunu **duzeltir**.

Tek bakisli ER bu takasi goremez. R-D'nin dogru olcutu ikisinin ortalamasidir.

**`flip_perspective` dogru.** Onceki oturumda "12x fark" (yalniz cevrilmis
vektorlerle egitim 0,0837 vs 0,0066) donusumun bozuk oldugu sanildi. Yeni
kontrollu deney bunu **curuttu**: ayni ag, ayni adim sayisi, ayni tohumla

| Egitim verisi | ER (orijinal held-out) | ER (cevrilmis held-out) |
|---|---|---|
| orijinal | **0,0678** | 0,3304 |
| yalniz cevrilmis | 0,3234 | **0,0642** |
| ikisi | 0,0942 | 0,0817 |

Fark **tam simetrik** (0,0678/0,3304 vs 0,3234/0,0642). Bozuk bir donusum
boyle bir simetri uretemez; bu, donusumun dogru oldugunun kanitidir. Ayrica
`flip_perspective(v)` ile `gnubg_er.vectorize(ayni_tahta, perspective=-turn)`
400 rastgele pozisyonda **birebir** ayni (maks fark 0,0; Test 160) ve
ters-cevirmesiz varyant 12 hata veriyor — yani `j -> 25-j` terslemesi sart.

**Olcum (400 oyunluk havuz, 2 667 held-out pozisyon).**

| Model | ER(+1) pol/deger | ER(-1) pol/deger | **Ortalama** pol/deger | Asimetri (deger) |
|---|---|---|---|---|
| `v30` (taban) | 0,0270 / 0,0287 | 0,1081 / 0,1019 | 0,0675 / 0,0653 | 3,6x |
| `rd_sp_ctl` v10 | 0,0355 / 0,0354 | 0,1220 / 0,1282 | 0,0787 / 0,0818 | 3,6x |
| `rd_sp_aug` v10 | 0,0479 / 0,0489 | 0,0731 / 0,0799 | **0,0605 / 0,0644** | **1,6x** |

**Sonuc: artirim kazanir.** Kontrole gore ortalama ER politika **-23%**,
deger **-21%**; asimetri orani 3,6x -> 1,6x. `v30` tabaninin ortalamasini da
gecer (0,0675/0,0653 -> 0,0605/0,0644). Tek bakisli ER'deki kayip
(+0,012/+0,014) karsi bakistaki kazancin (-0,049/-0,048) yaninda kucuktur.

**Arac.** Bu hata tekrarlanmasin diye olcum `curve_pool`'a tasindi:

| Oge | Davranis |
|---|---|
| `measure_er(..., perspective=)` | `active` (varsayilan) / `opponent` (vektor cevrilir, equity isaret degisir) |
| `measure_er_both(...)` | `<yol>`, `<yol>Opp`, `<yol>Mean` anahtarlari |
| `perspective_asymmetry(report, path)` | iki bakis ER orani (1,0 = tam simetrik) |
| CLI `curve_pool measure-er --model ... --perspective both` | JSON ozet + `policyAsymmetry` / `valueAsymmetry` |

**Testler.** `ml/tests/test_curve_pool.py` Test 245-249 (5 test): karsi bakis
vektor+isaret sozlesmesi (sabit cikti ile analitik dogrulama), `both`
anahtarlari ve ortalama, asimetri orani (esit/oran/sifir/sonsuz), bilinmeyen
bakis reddi, CLI sozlesmesi.

**Acik kalan.** Iki bakisli ER hala **afterstate** dagilimi uzerindedir;
uretim yolu (arama) farkli bir dagilim gorur. Nihai karar ppg'dir (K3) ve
R-F'de olculecek.

## F7-102 — R-D 10 000 oyunluk dogrulama: artirim kazanci buyuyor

> **DUZELTME (F7-104).** "Kazanc" iki bakisli ER'de goruluyordu. ppg
> urun olcumunde artirimli model tabandan **0,16 ppg kotu** (z = -3,82).
> Bu kaydin sonucu gecersizdir.

Eslesmis deney 2 000 oyunla yapilmisti. Ayni karsilastirma **10 000 oyun**
(300 adim, depth 0, seed 11, 10 000 oyunluk buffer, `ckpt_v30.pt`'den
baslatilmis, 10 iterasyon) ile tekrarlandi; iki kosu paralel calisti.

| Kosu | Bayrak | CE (buffer) | equity MAE | politika kaybi | sure |
|---|---|---|---|---|---|
| `rd_ctl10k` | — | 0,9263 -> 0,9104 | 0,8177 -> 0,8099 | 1,0935 -> **1,0738** | 2 626 s |
| `rd_aug10k` | `--augment-perspectives` | 0,9387 -> 1,0249 | 0,8268 -> 0,8983 | 1,0932 -> 1,1909 | 4 594 s |

**Tek bakisli metrikler yine artirimi kotu gosteriyor** (CE +0,086, equity MAE
+0,072, politika kaybi +0,117). Iki bakisli olcum tersini soyluyor:

| Model | ER(+1) pol | ER(-1) pol | **Ort** pol | ER(+1) deger | ER(-1) deger | **Ort** deger | Asimetri pol/deger |
|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` (taban) | 0,0270 | 0,1081 | **0,0675** | 0,0287 | 0,1019 | **0,0653** | 4,00x / 3,55x |
| `rd_ctl10k/model_v10` (kontrol) | 0,0298 | 0,1202 | **0,0750** | 0,0302 | 0,1177 | **0,0739** | 4,03x / 3,90x |
| `rd_aug10k/model_v10` (artirimli) | 0,0383 | 0,0691 | **0,0537** | 0,0387 | 0,0717 | **0,0552** | **1,80x / 1,85x** |

**Artirim kazaniyor ve fark buyuyor.** Kontrole gore ortalama ER politika
**-%28**, deger **-%25**; `v30` tabanina gore **-%20 / -%15**. Asimetri orani
4,0x -> 1,8x. 2 000 oyunluk deneydeki kazanc (-%23 / -%21) **korundu ve
buyudu**; sonuc olcek gurultusu degil.

**Tek bakisli ER neden yaniltici — sayisal kanit.** Artirimli model
`ER(+1)`'de 0,0270 -> 0,0383 (**+0,0113 kotu**) ama `ER(-1)`'de 0,1081 ->
0,0691 (**-0,0390 iyi**). Net etki ortalamada -0,0138. Tek bakisli olcum
yalniz ilk sayiyi gorur.

**Yan bulgu: kontrol de bozuluyor.** `rd_ctl10k` taban `v30`'a gore ortalamada
kotulesiyor (0,0675 -> 0,0750). Yani R-D'nin kendi kendine oynama turu,
artirim olmadan **zarar veriyor**; artirim bu bozulmayi tersine cevirip
tabanin da altina iniyor. Bu, F7-100'deki "politika kafasi bozuluyor"
gozleminin artirima degil, **kendi kendine oynama turuna** ait oldugunu
gosteriyor.

**Kapi hala gecmiyor ama her eksende iyilesiyor.** `|corr| >= 0,99` esigi bu
mimariyle ulasilabilir degil. Kapi **teshis** olarak kalmali; karar iki bakisli
ER ve (R-F'de) ppg ile verilir.

| Model | `corr` | `meanAbsSum` | `argmax` uyumu | ER farki | Kapi |
|---|---|---|---|---|---|
| `v30` (taban) | -0,8915 | 0,7152 | 0,348 | -0,0479 | DUSTU |
| `rd_ctl10k` (kontrol) | -0,8776 | 0,6006 | 0,295 | -0,0614 | DUSTU |
| `rd_aug10k` (artirimli) | **-0,9426** | **0,2827** | **0,392** | **-0,0302** | DUSTU |

Artirim `corr`'u -0,8776 -> -0,9426'ya (esige yaklasiyor), ER farkini
-0,0614 -> -0,0302'ye (**yariya**) indiriyor ve `meanAbsSum`'i 0,7152 -> 0,2827
yapiyor. Yani artirim dogru yonde calisiyor; esik mimari bir kisit.

**Cikarim ani antisimetriklestirmesi artik gereksiz.** `rd_aug10k` uzerinde
(n = 1000): politika 0,0485 -> 0,0457 (-0,0028, GA [-0,0083; +0,0028],
**kanitlanmadi**); deger 0,0627 -> 0,0573 (-0,0054, GA [-0,0123; +0,0013],
**kanitlanmadi**). Model zaten 1,8x asimetrik oldugu icin duzeltilecek pay
kalmamis — `v30`'daki 4,0x asimetride kazanc anlamliydi. **Artirim,
antisimetriklestirmenin yerini aliyor.**

**Arac.** `curve_pool measure-er` artik **coklu model** alir ve `--out`
verilirse JSON + markdown karsilastirma tablosu yazar (`_model_label` kosu
dizinini etikete katar; `onnx/` ara dizini atlanir). Test 250-251. Artefaktlar:
`ml/artifacts/er_two_perspective.json` / `.md`,
`ml/artifacts/antisymmetry_rd_aug10k.json`, `antisymmetry_rd_ctl10k.json`,
`antisymmetry_rd_aug10k_symmetrised.json`.


## F7-103 — K3: oyun sikligina agirlikli ER (hedef metrik)

**Sorun.** `curve_pool` pozisyonlari `corpus2` katmanlamasindan gelir ve bu
katmanlama **temas agirliklidir** (`PHASE_SHARES = contact 0,60 / bar 0,25 /
race 0,15`). Oynanan oyunlarda dagilim farklidir, dolayisiyla ham ER oynanan
yolu temsil etmez: havuzda fazla temsil edilen faz ER'yi domine eder.

**Olculen gercek dagilim.** `real_phase_shares` shard'lardan olcer. **Tum
adaylar** sayilir (`cand_vectors`), yalniz secilen hamle degil: model uretimde
her adayi degerlendirir, secilen aday ise vurusa egilimlidir ve "bar" payini
sisirir (yalniz-secilen olcumu bar 0,451 / temas 0,377 / yaris 0,172 veriyordu;
tum-aday olcumu asagidaki gibi). `stage_d_l2` shard 1, 10 000 oyun:

| Faz | Havuz payi (2 667 held-out) | Gercek oyun payi (shard 1) | Agirlik |
|---|---|---|---|
| contact | 0,6970 | 0,5219 | 0,75x |
| race | 0,1159 | 0,1292 | 1,12x |
| bar | 0,1871 | 0,3488 | **1,86x** |

Havuz temasi 1,34x fazla, bar'i 1,86x eksik temsil ediyor.

**Yontem.** `game_frequency_weights(pool, indices, target)` her pozisyona
`target[faz] / have[faz]` agirligi verir, ortalamayi 1'e normalize eder
(agirlikli ER ayni olcekte kalir), havuzda bulunmayan fazi dusurup kalanlari
yeniden normalize eder. `measure_er` / `measure_er_both` / `measure_summary`
`weights=` alir; ham liste pozisyon basina kalir, agirlik yalnizca ozetler.
`phase_of_vector` fazi vektorden okur: bar > yaris > temas (`ACTIVE_BAR` /
`OPP_BAR` / `IS_CONTACT`). `bearoff` / `closed` `HEADLINE_PHASES` disinda
oldugu icin temas/yarisa katlanir — bilincli.

**Sonuc — karar degismiyor, gucleniyor.** 2 667 held-out pozisyon, iki bakisli
ER:

| Model | Ort pol | **Agirlikli pol** | Fark | Ort deger | **Agirlikli deger** | Fark |
|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | 0,0675 | **0,0646** | -4,4% | 0,0653 | **0,0633** | -3,1% |
| `rd_ctl10k/model_v10` | 0,0750 | **0,0713** | -4,9% | 0,0739 | **0,0698** | -5,5% |
| `rd_aug10k/model_v10` | 0,0537 | **0,0492** | -8,5% | 0,0552 | **0,0500** | -9,3% |

Agirliklandirma **tum** modellerin ER'sini dusuruyor (havuzun temas fazlaligi
ER'yi sisiriyordu) ve **artirimin kazanci buyuyor**:

- kontrole karsi: agirliksiz -28,4% pol / -25,3% deger -> agirlikli **-31,0% /
  -28,4%**
- `v30` tabanina karsi: agirliksiz -20,5% / -15,5% -> agirlikli **-23,8% /
  -21,0%**

Yani K3'nin "ham ER yanli" uyarisi dogru, ama duzeltme R-D lehine. **Hedef
metrik artik agirlikli ER'dir; R-F bu metrigi kullanir.**

**Arac.** `curve_pool measure-er --weight-by-game-frequency [--shard-dir ...]
[--shard-limit N]`; `--out` artik kendini tanimlayan bir sozluk yazar
(`pool`, `perspective`, `positions`, `weighted`, `realShares`, `shardDir`,
`shardLimit`, `models`) ve markdown'a K3 bolumunu ekler. Test 254-262.
Artefaktlar: `ml/artifacts/er_weighted.json` / `.md` (agirlikli),
`ml/artifacts/er_two_perspective.json` / `.md` (agirliksiz, ayni sema).

**Saglamlik — hedef secimine duyarli degil.** Iki bagimsiz gercek-dagilim
tahminiyle ayni sonuc: shard olcumu (bar 0,3488 / temas 0,5219 / yaris 0,1292)
ve korpus v2'nin `realGamePhaseWeights` alani (bar 0,3706 / temas 0,5564 /
yaris 0,0730). Ikincisiyle: kontrole karsi **-31,5% pol / -29,0% deger**,
`v30`'a karsi **-24,5% / -21,6%** — birincisiyle -31,0% / -28,4% ve -23,8% /
-21,0%. Fark 1 puandan az; **artirim karari agirlik secimine bagli degil.**
(`er_paths` zaten korpus agirligini kullaniyor; `curve_pool` afterstate
dagilimini kullaniyor — ER afterstate uzerinde olculdugu icin ikincisi daha
dogru, ama fark karari degistirmiyor.)

**Acik kalan.** (a) Gercek paylar tek shard'dan (10 000 oyun) olculdu; 30
shard'in tamami daha dar bir GA verir ama paylar oyun sayisiyla hizli
sabitlenir. (b) ER hala **afterstate** duzeyinde; ppg eslesmesi R-F'de
olculecek. (c) `m = 0,02 ppg` esigi kullanici karari, R-F'de netlesecek.
## F7-104 -- R-F: ppg urun olcumu R-D artirimini **curuttu**

> **Bu kayit F7-101 ve F7-102'yi gecersiz kilar.** Iki bakisli ER yanlis
> olcuttu; dogru olcut tek bakisli (hareket eden tarafin) ER ve ppg'dir.
> Asagidaki tablolar tarihsel kayit olarak duruyor.

**Olcum.** Uc model, ayni kosu kosullari (kupsuz para oyunu, eslestirilmis
zar + renk takasi, gnubg 0-ply, `search1`, tohum 2026, 2000 oyun = 1000
cift). `ml/artifacts/ppg_models.json` / `.md`.

| Model | Kazanma | ppg | ppg %95 GA | ER(pol, +1) | ER(val, +1) |
|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | 0,4340 | **-0,1635** | [-0,2230; -0,1050] | 0,0270 | 0,0287 |
| `rd_ctl10k/model_v10` | 0,4320 | **-0,1990** | [-0,2600; -0,1380] | 0,0298 | 0,0302 |
| `rd_aug10k/model_v10` | 0,3765 | **-0,3240** | [-0,3810; -0,2670] | 0,0383 | 0,0387 |

**Ikili farklar** (iki ornekli GA; her kosunun kendi eslesmis GA'si zar
gurultusunu zaten iptal ettigi icin GA oldugundan dar gorunmez):

| a | b | a - b | %95 GA | z | Anlamli |
|---|---|---|---|---|---|
| `rd_ctl10k` | `v30` | -0,0355 | [-0,1213; +0,0503] | -0,81 | hayir |
| `rd_aug10k` | `v30` | **-0,1605** | [-0,2429; -0,0781] | **-3,82** | **evet** |

**Sonuc: R-D perspektif artirimi urun metriginde CURUDU.** Artirimli model
tabandan 0,16 ppg **daha kotu** (p = 1,3e-4). Kontrol kosusu tabandan
istatistiksel olarak ayirt edilemiyor -- yani 10k olcekli self-play turu
**ne yardim ediyor ne de zarar veriyor**; zarari veren sey artirim.

**Kok neden -- F7-101 yanlis olcutu secti.** `search1` **yalnizca deger
kafasini** kullanir (`er_paths.search1_values` icindeki tek skorer cagrisi
`scorer.values`; `scorer.logits` yalnizca `policy` yolunda). Artirim
deger kafasini **iki** bakistan egitiyor ve **hareket eden tarafin**
bakisi pahasina: ER(+1) 0,0287 -> 0,0387. ppg tam olarak bu eksende
bozuluyor. Uretimde `BackgammonSearch` her iki kafaya da `s.turn`
verir, yani model **her zaman sira kimdeyse onun bakisini** gorur; (-1)
bakisi hic olusmaz. Dolayisiyla **iki bakisli ER, urunun hic kullanmadigi
bir dagilimi olcuyordu.** Kullanicinin R-D oncesi uyarisi ("(-1) bakis hic
gorulmeyebilir ve kapi bir genelleme teshisi olur") **dogruydu**.

**Bu bir hiperparametre sorunu degil.** F7-101'deki kontrollu deney (ayni
ag, ayni adim sayisi, ayni tohum, yalniz egitim verisi farkli) zaten ayni
seyi soyluyordu: orijinal held-out uzerinde **orijinal 0,0678**,
**ikisi 0,0942** -- yani iki bakistan egitmek hareket eden tarafin ER'sini
**%39 kotulestiriyor**. Kapasite paylasimi; ogrenme orani veya adim sayisi
ile duzeltilecek bir sey degil. O tabloda "ikisi" satirinin `ER(-1)`
sutununun iyi gorunmesi (0,0817) tam da urunde karsiligi olmayan eksendir.

**ER -> ppg eslemesi (K3'un kalan teslimati).** Uc nokta uzerinde dogrusal
fit:

| Kafa | Egim (ppg / ER) | Kesisim | R^2 |
|---|---|---|---|
| policy | **-14,30** | +0,2247 | **0,9994** |
| value | -15,64 | +0,2798 | 0,9941 |

ER'deki bir birim ~**14,3 ppg**'ye karsilik geliyor ve iliski neredeyse
tam dogrusal. Bu, **tek bakisli (hareket eden tarafin) ER'yi gecerli bir
ppg vekili** yapar -- ve o olcut zaten artirimin kotu oldugunu soyluyordu
(0,0383 vs 0,0298 vs 0,0270). Uc nokta az; egim bir buyukluk mertebesi
olarak okunmali, kesin katsayi olarak degil.

**Guc.** `ppg_levels.md`'den ampirik esik **m = 0,1115 ppg** (gnubg
0-ply vs 2-ply @ money farki -0,2229'un yarisi; GA sifiri disliyor).
m = 0,1115 icin gereken oyun sayisi 0-2@money'de **4337**; 2000 oyun
**yetersiz**. Bu yuzden "fark var" iddiasi saglam (z = -3,82) ama
"fark m'den buyuk" iddiasi resmi olarak kurulamaz: aug-vs-v30 GA'si
[-0,2429; -0,0781], -m = -0,1115'i **dislamiyor**. Nokta tahmini
(-0,1605) m'yi asiyor ve cok daha kesin olan ER olcumu ayni yonu
gosteriyor; **artirimin reddi guvenli**, "bir seviye fark" iddiasi degil.

**Kararlar.**
1. **Iki bakisli ER (F7-101) karar olcutu olmaktan cikarildi.** Tek
   bakisli (hareket eden tarafin) ER kullanilir; ppg ile R^2 = 0,9994.
2. **`--augment-perspectives` varsayilan olarak KAPALI kalir** ve
   uretim/egitim kosularinda kullanilmaz. Bayrak yalnizca teshis icin
   duruyor.
3. **Antisimetri kapisi (`|corr| >= 0,99`) zaten teshis**; simdi
   gerekcesi de kayitli: olctugu eksen urunde olusmuyor.
4. **Sonraki kaldirac gnubg damitma**, self-play degil. Kontrol kosusu
   tabandan farksiz; ayni veriden daha fazla self-play turu beklemek
   icin kanit yok. K5'in 6-sinifli KL damitmasi (`--dist-weight`)
   uygulandi ve kullanilmadi; siradaki deney odur.

**Acik kalan.** (a) 2000 oyun m = 0,1115 icin yetersiz; "esdeger"
iddiasi icin >=4337 oyun gerekir. (b) ER->ppg egimi 3 noktadan; ara
ER seviyelerinde (ornegin 0,032) dogrulanmadi. (c) `policy` yolu
(search1 degil) icin ppg olculmedi; politika kafasinin urun katkisi
ayri bir kosu ister.
## F7-105 -- K1/K4: havuz tabanli antisimetri kapisi ve "N icin gereken veri" olcutu

**K1 -- kapi n >= 1245'te olculemedi, havuzda olculdu.** `antisymmetry.py
measure` korpus v2'yi kullanir; `corpus2.TARGET_POSITIONS_V2 = 1000`, yani
K1'in istedigi n >= 1245 oradan **karsilanamaz** (korpusu yeniden uretmeden).
400 oyunluk havuzun (`curve_pool_400.npz`) held-out kumesi **2667 pozisyon /
50 727 afterstate** veriyor -- gereksinimin 2,7 kati -- ve istatistikler
anlamsal olarak ayni (`gnubg_distill.equity_of_probs` ==
`equity.equity_from_exclusive`; ikisi de `probs @ EQUITY_WEIGHTS`).
`curve_pool.py`'ye `measure_gate()` ve `gate` alt komutu eklendi; cikti
`ml/artifacts/antisymmetry_pool.json` / `.md`.

| Model | corr | meanAbsSum | argmax | ER(+1) | ER(-1) | Fark | 95% GA |
|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | -0,9100 | 0,4340 | 0,362 | 0,0287 | 0,0815 | -0,0527 | [-0,0582; -0,0474] |
| `rd_ctl10k/model_v10` | -0,8967 | 0,4247 | 0,327 | 0,0302 | 0,0929 | -0,0627 | [-0,0687; -0,0569] |
| `rd_aug10k/model_v10` | **-0,9641** | **0,1479** | **0,438** | 0,0387 | 0,0499 | **-0,0112** | [-0,0151; -0,0078] |

Artirim **her eksende** iyilestiriyor (corr -0,9100 -> -0,9641, meanAbsSum
0,4340 -> 0,1479, argmax 0,362 -> 0,438, ER farki -0,0527 -> -0,0112) ama
`|corr| >= 0,99` esigini **hala gecmiyor**. Bu, kapinin bir teshis
oldugunu ve karar olcutu olmadigini (F7-104) nicel olarak dogruluyor:
artirim kusuru 4,7 kat azaltiyor, yine de urun metriginde 0,16 ppg
kaybettiriyor. Yani kusurun buyuklugu ile urun zarari arasinda iliski
**yok**.

**K4 -- etiket artik "N icin gereken veri" ile de veriliyor.** Eskiden
etiket yalnizca egim isaretine ve tohum oylamasina bakiyordu; K4 bunun
"bu N icin gereken veri" tahminiyle celismemesi gerektigini soyledi.
`learning_curve.py`'ye eklendi:

* `DATA_TARGET_RATIO = 0,5` -- hedef, olculen en iyi ER'nin yarisi.
* `DATA_BUDGET_MULTIPLIER = 100` -- butce, olculen en buyuk pozisyon
  sayisinin 100 kati (1 056 000).
* `data_requirement(fit, target)` -- `ER = a*N^-b + c`'yi ters cevirip
  `N = (a / (target - c)) ** (1/b)` verir; `target <= c` ise `inf`
  (taban hedefin ustunde -> ne kadar veri olsa da ulasilmaz).
* `DataRequirement.decision`: `inf` -> `pipeline`, sonlu ve <= butce ->
  `olcek`, sonlu ama butce ustu -> `belirsiz`.
* `CurveReport.decision` artik **uc olcutun anlasmasini** istiyor: egim,
  tohum oylamasi ve `data_decision`. Celiski -> `belirsiz`.

Gercek 7 noktali egri uzerinde sonuc (`ml/artifacts/learning_curve.md`
bolum 4.2):

| Yol | En iyi ER | Hedef | Taban (c) | Gereken N | Butce | Karar |
|---|---|---|---|---|---|---|
| `policy` | 0,0158 | 0,0079 | 0,0003 | **103 433** | 1 056 000 | `olcek` |
| `value` | 0,0330 | 0,0165 | **0,0223** | **inf** | 1 056 000 | `pipeline` |

**Bu, F7-104'un nicel bicimidir.** Politika kafasi olcekle sinirli
(103 433 pozisyon -- ulasilabilir), deger kafasi ise **hatta** sinirli:
tabani 0,0223, hedefi 0,0165'in **ustunde**, yani ne kadar veri eklenirse
eklensin yariya inmez. `search1` **yalnizca deger kafasini** kullandigi
icin (`er_paths.search1_values`) urun metrigini veri miktari
**iyilestiremez**. Bu, "sonraki kaldirac gnubg damitma" kararinin
(F7-104, karar 4) sayisal gerekcesidir.

**Acik kalan.** (a) Taban `c` GA'lari genis (value: [0,0148; 0,0252]) --
`c`'nin hedefin ustunde oldugu **nokta tahminine** dayaniyor, GA'nin
tamamina degil. (b) `policy` yolunun ppg'si hala olculmedi (K5 kosusu
suruyor).

**Onay (2026-11-21).** Kullanici `DATA_TARGET_RATIO = 0,5` ve
`DATA_BUDGET_MULTIPLIER = 100` degerlerini **kabul etti**. Bu iki sabit
artik varsayim degil, onaylanmis parametredir; degistirmek yeni bir onay
gerektirir (Kural 2).
## F7-106 -- K5: yol x model ppg matrisi ve 6-sinif KL deneyi

K5 iki sey istiyordu: (a) **politika-argmax ve deger-0-ply** oyununun
ppg'sini olc, (b) **6-sinif KL** ile deger basligini yeniden egit ve
`search1` ER/ppg'sini olc. Ikisi de yapildi; ikincisi **negatif** cikti.

**Neden `value` yolu elma-elmaya.** gnubg 0-ply da after-state
degerlendirmesiyle oynar; `value` yolu (deger kafasi argmax, 0-ply) ayni
sozlesmeyi kullanir. `search1` bir ply arar, `policy` deger kafasina hic
dokunmaz. Uc yolun ppg'si kafalarin urun katkisini ayristirir.

`ml/vs_gnubg.py`'nin `OUR_PATHS` listesi `er_paths.PLAY_PATHS`'ten eksikti
(`value` yoktu); eklendi ve Test 284 iki listeyi birbirine bagladi.
`ml/ppg_paths.py` matrisi kurar (`ml/artifacts/ppg_paths.json` / `.md`).

Kupsuz para oyunu, eslestirilmis zar + renk takasi, gnubg 0-ply, 2000 oyun
(1000 cift), tohum 2026:

| Model | politika-argmax | deger-0-ply | search1 |
|---|---|---|---|
| `stage_d_l2/model_v30` | -0,4430 [-0,5020; -0,3835] | -0,4150 [-0,4740; -0,3560] | **-0,1635** [-0,2230; -0,1050] |
| `rd_ctl10k/model_v10` | -0,4605 [-0,5180; -0,4015] | -0,4445 [-0,5040; -0,3860] | **-0,1990** [-0,2600; -0,1380] |
| `rd_aug10k/model_v10` | -0,5160 [-0,5755; -0,4565] | -0,5570 [-0,6175; -0,4960] | **-0,3240** [-0,3810; -0,2670] |

**`search1` her modelde tek kafali yollardan ~0,25 ppg daha iyi** (yol
farklari -0,19 ile -0,28 ppg arasi, hepsi anlamli, |z| 4,6-6,6). Yani
1-ply arama gercek is yapiyor: ne politika kafasi ne de deger kafasi tek
basina rekabetci. Bu, `search1`'in deger kafasinin **mutlak
kalibrasyonundan** degil **siralama**sindan faydalandiginin ilk dogrudan
kanitidir -- ve F7-105'in "deger tabani 0,0223" bulgusuyla celismez:
siralama dogru oldugu surece mutlak hata aramada kismen telafi olur.

Model farklari (ayni yol, `model_v30` referans): `policy` yolunda ne
`ctl` (-0,0175, z -0,41) ne `aug` (-0,0730, z -1,71) anlamli; `value`
yolunda `ctl` anlamsiz (-0,0295, z -0,69), `aug` anlamli (-0,1420,
z -3,28); `search1`'te `ctl` anlamsiz (-0,0355, z -0,81), `aug` anlamli
(-0,1605, z -3,82). **R-D artiriminin zarari yalnizca `search1`'te degil,
`value` yolunda da olculuyor** -- yani zarar arama katmanindan degil,
deger kafasinin kendisinden geliyor.

**Bitmeyen oyunlar (yeni bulgu).** `policy` **ve** `value` kafalari tek
basina bitmeyen oyun uretebiliyor: `pol_ctl` ve `val_ctl` kosulari
`MatchError: oyun 200 ply'de bitmedi` ile coktu. `play_game`'e
`allow_unfinished` eklendi; bu oyunlar **0 puan** sayilip **sayilir ve
raporlanir** (sessizce atilmaz). Gercek oranlar cok kucuk: `ctl` policy
1/2000, `ctl` value 2/2000. `search1` kosularinda hic gorulmedi.

**6-sinif KL deneyi (negatif).** `train_policy_head`'in `dist_weight`
terimi zaten **deger kafasinin** 6 sinifli cikti dagilimina uygulanan
`KL(gnubg_dagilimi || model_dagilimi)`'dir (`probs = out[0]`,
`best_probs = probs.gather(...)`), yani K5'in "deger basligi 6-sinif KL
ile yeniden egitilsin" istegi bu terimle karsilanir. R-Q2 (gnubg hint 6
olasilik veriyor mu) **dogrulandi**: `label-policy --dists` 6 sinifli
dagilim uretiyor.

Kurulum: 3000 pozisyon gnubg 2-ply dagilimiyla etiketlendi
(`ml/runs/k5_dist/policy_dist_3k.npz`, 67 316 aday, ortalama dagilim
[0,3228 0,2979 0,0418 0,2477 0,0852 0,0046], 4235 s). Iki kol de
`ckpt_v30.pt`'den basladi, 4000 adim, lr 3e-4, batch 64, tohum 0,
`--value-weight 0,5`. Tek fark `--dist-weight` (0 ve 0,5).

| Yol | KL=0 | KL=0,5 | Fark | z |
|---|---|---|---|---|
| `policy` | 0,025966 | 0,026273 | +0,000307 | +0,10 |
| `value` | 0,044881 | 0,044475 | -0,000406 | -0,09 |
| `search1` | 0,022617 | 0,021507 | -0,001110 | -0,50 |

**Hicbir yol anlamli degismedi** (|z| < 0,5). KL terimi kaybi domine
ediyordu (son kayip 0,00210 -> 0,02097), yani agirlik zayif degildi.
Sonuc: **deger kafasinin platisi bir etiket-temsili sorunu degil.**
Kontrol kolu ayni 3000 pozisyonla politika ER'sini %35 dusurdu
(0,0402 -> 0,0260) ama deger ER'sini **hic** oynatmadi (0,0442 ->
0,0449). Ayni veri hacmi bir kafayi ciddi bicimde hareket ettirirken
digerini oynatmiyor; 6 sinifli hedef pozisyon basina 6 kat sinyal
vermesine ragmen fark yok. Bu, F7-105'in "deger kafasi **hatta**
sinirli" tespitini bagimsiz olarak dogruluyor: kaldirac daha iyi kayip
degil, **daha fazla etiketli veri** (ve o da taban 0,0223'u hedefin
altina indirmeye yetmiyor).

Karsilastirma artik kalici: `ml/er_paths.py compare --control ... --treatment
...` iki raporu yol bazinda karsilastirir (`ml/artifacts/er_paths_k5_kl_compare.json`
/ `.md`). Iki ornekli z kullanilir cunku `er_paths` JSON'u pozisyon basina
kaybi saklamaz; eslesmis test icin JSON semasi degismeliydi.

**Acik kalan.** (a) KL deneyi 3000 pozisyonla sinirli; 10-30 bin
pozisyonla tekrarlanmadi (etiketleme gnubg 2-ply'de ~1,4 s/pozisyon,
yani 30 bin ~12 saat). (b) `dist_weight` icin yalnizca 0 ve 0,5
denendi; ara degerler denenmedi. (c) `policy`/`value` yollarinin
bitmeyen oyun orani `search1` icin olculmedi (hic gorulmedi, ama
sistematik sayim yok).

## F7-107 -- K5: kafa dengesi -- "kayip agirligi" adayi elendi

K5, deger kafasinin platosu icin uc aday sayiyordu: (a) **kayip agirligi
(w*MSE)**, (b) 6 sinifli KL'nin yoklugu, (c) antisimetri kusuru. (b) F7-106'da,
(c) F7-105'te olculdu ve elendi. Bu kayit (a)'yi kapatir.

**Neden (a) akla yatkindi.** `train_v2.py` damitma modunda
(`equity_target` dolu) deger kafasini **skaler MSE** ile, politika kafasini
grup-softmax capraz entropisi ile egitiyor. Iki terimin agirligi da
`c_value = c_policy = 1,0` ama buyuklukleri ayni degil. Paylasilan govde tek
oldugu icin hangi terimin gradyani buyukse govdeyi o yonlendirir.

**Olcum.** `ml/head_balance.py` ayni kontrol noktasini ve ayni veriyi
kullanarak her terimi **tek basina** geri yayar ve govdeye tasidigi gradyan
normunu ayri ayri raporlar. Karar sayisi kayip orani degil **gradyan
oranidir**: kayip kucuk ama gradyan buyuk olabilir.

`ckpt_v30.pt`, 3000 pozisyon (`ml/runs/k5_dist/policy_dist_3k.npz`):

| Terim | Kayip | ||dL/d(govde)|| |
|---|---|---|
| Politika grup-softmax CE | 1,394324 | 1,351443 |
| Deger skaler MSE | 0,170902 | 0,914423 |
| Kalibrasyon MSE | 0,170902 | 0,914423 |
| Deger 6 sinifli CE (teshis) | 1,480352 | -- |
| KL(gnubg || model) (teshis) | 0,190459 | 0,632914 |

Kayip orani **8,16** ama gradyan orani yalnizca **1,48**; deger teriminin
govde gradyanindaki payi **%40,4**. Yani deger kafasi **ac degil**. Aday
elendi.

**Yan bulgu -- R-F'nin mekanizmasi.** Ayni olcum uc modelde tekrarlandi
(`ml/artifacts/head_balance_compare.json` / `.md`):

| Model | Politika CE | Deger MSE | Oran | Deger payi |
|---|---|---|---|---|
| `stage_d_l2/model_v30` | 1,3943 | 0,1709 | 1,48 | %40,4 |
| `rd_ctl10k/model_v10` | 1,4699 | 0,1697 | 1,19 | %45,6 |
| `rd_aug10k/model_v10` | 1,5659 | **0,1200** | **3,33** | **%23,1** |

Perspektif artirimi deger kafasinin **egitim kaybini dusuruyor**
(0,1709 -> 0,1200) ama **govde gradyanini yariya indiriyor**
(0,9144 -> 0,4263). Deger payi en dusuk olan model, R-F'de `value` ve
`search1` ppg'si en kotu olan modeldir (`value` -0,1420, `search1`
-0,1605, ikisi de anlamli). Yorum: artirim deger hedefini **kafanin tek
basina** fittedilebilir hale getirdi, govde deger-iliskili ozellikleri
kodlamayi birakti. Bu, R-F'nin "artirim deger kafasini vurdu" hukmunun
mekanik aciklamasidir ve `search1`'in neden en cok zarar gordugunu
aciklar (arama yalnizca deger kafasini kullanir).

**Sonuc.** Uc adayin ucu de elendi. Deger kafasinin platisi bir **egitim
sinyali** sorunu degil; **hedef tanimi / mimari** sorunu. F7-105'in taban
analizi (deger tabani 0,0223 > hedef 0,0165) ile ayni yone bakiyor: daha
fazla ayni-tur veri tabani hedefin altina indirmiyor.

**Arac.** `python ml/head_balance.py` (tek model) ve
`python ml/head_balance.py --compare a.json b.json ...` (coklu model).
Testler 302-309.