# Unity Görselleştirme — TavlaAI (Faz 5, Aşama D)

Bu klasör **belge** amaçlıdır. Unity projesinin kendisi ayrı bir yerde durur:

```
F:\Projects\Unity\Tavla3D
```

Unity sürümü: **6000.3.8f1** (URP 17.3.0, uGUI 2.0.0, Input System 1.18.0,
test-framework 1.6.0).

---

## 1. Mimari

```
Assets/
  Plugins/                     <- tools/sync-unity-plugins.ps1 tarafından kopyalanır
    Managed/
      Backgammon.Core.dll
      Backgammon.Inference.dll
      Backgammon.UI.dll
      Microsoft.ML.OnnxRuntime.dll
    x86_64/
      onnxruntime.dll
      onnxruntime_providers_shared.dll
  StreamingAssets/
    models/model.onnx          <- ml/runs/stage_d/onnx/model_v5.onnx
    bearoff/bearoff1_v1.bin    <- ml/artifacts/bearoff1_v1.bin
  Backgammon.UI/
    Scripts/
      Bootstrap/               GameBootstrap
      Board/                   BoardView, BoardPointView, CheckerView, CheckerPool,
                               BarView, TrayView
      Dice/                    DiceView
      Cube/                    CubeView
      Hud/                     MatchScoreView, CrawfordBadgeView, MatchLengthView
      Analysis/                AnalysisPanelView
      Settings/                SettingsPanelView
      Input/                   BoardInputController
      Infrastructure/          OnnxBackendFactory, PipDifferenceEvaluator, UiFactory,
                               UnityMainThreadDispatcher, SpriteLibrary
    Resources/Sprites/         (opsiyonel) board, point, bar, tray, cube,
                               checker_white, checker_black, die_1..die_6
    Editor/                    SceneBuilder, BuildScript
    Tests/
      EditMode/                BoardLayoutTests (Test 38), SceneLoadsTests (Test 39),
                               CheckerPoolTests (Test 40)
      PlayMode/                SmokeTests, OnnxBackendTests, FullGameTests
  Scenes/Main.unity            SceneBuilder tarafından üretilir
```

**Kritik kural:** `Backgammon.UI` (netstandard2.1) **hiçbir** `UnityEngine` türü
içermez. Unity'ye bağımlı her şey bu klasördeki MonoBehaviour'lardadır. Bu sayede
`Backgammon.UI.Tests` Unity'siz çalışır (Test 27–33).

---

## 2. Plugin senkronizasyonu

```powershell
pwsh -NoProfile -File tools\sync-unity-plugins.ps1
```

Betik `dotnet build -c Release` yapar, DLL'leri ve varlıkları `Assets/Plugins` ve
`Assets/StreamingAssets` altına kopyalar, `onnxruntime.dll` sürümünü doğrular.
`-SkipBuild` ile yalnızca kopyalama yapılır.

---

## 3. Sahne üretimi

```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.3.8f1\Editor\Unity.exe" `
  -batchmode -nographics -quit `
  -projectPath F:\Projects\Unity\Tavla3D `
  -logFile F:\Projects\Unity\Tavla3D\Logs\scene.log `
  -executeMethod TavlaAI.Editor.BuildScript.BuildScene
```

`Assets/Scenes/Main.unity` üretilir: kamera, Canvas, EventSystem, `BoardRoot`,
`DiceRoot`, `CubeRoot`, `MatchScorePanel`, `CrawfordBadge`, `MatchLengthPanel`,
`AnalysisPanel`, `SettingsPanel`, `BoardInput` ve tek bir `GameBootstrap`.

---

## 4. Testler

```powershell
# EditMode (Test 38-40)
& "...\Unity.exe" -batchmode -nographics -projectPath F:\Projects\Unity\Tavla3D `
  -logFile ...\Logs\editmode.log -runTests -testPlatform EditMode `
  -testResults ...\Logs\editmode-results.xml

# PlayMode (duman + ONNX arka uç + tam oyun)
& "...\Unity.exe" -batchmode -nographics -projectPath F:\Projects\Unity\Tavla3D `
  -logFile ...\Logs\playmode.log -runTests -testPlatform PlayMode `
  -testResults ...\Logs\playmode-results.xml
```

**Lisans kuralı (Faz 5 §11):** batchmode lisansı yoksa "Unity testleri geçti"
**yazılmaz**. Bu makinede lisans mevcuttur; sonuçlar `unity/build.log` içindedir.

---

## 5. Aşama D'de bulunan üç gerçek hata

### 5.1 `BoardLayout` kayan nokta çakışması

`BoardLayout.Calculate` komşu hanelerin sol kenarını `c * columnWidth`, sağ kenarını
`(c + 1) * columnWidth` ile hesaplıyordu. Kayan noktada bu iki ifade birbirini
tutmuyor ve dikdörtgenler `1e-13` mertebesinde üst üste biniyordu. Test 38 bunu
yakaladı. Düzeltme: her hane için `left` ve `right` **aynı** ifade ailesinden
türetilir; genişlik `right - left` olarak alınır.

### 5.2 ONNX Runtime iş parçacığı güvenliği

`OrtIoBinding` iş parçacığı güvenli **değildir**. Arama gerçek kare döngüsü içinde
arka plan iş parçacığında çalıştırıldığında `SynchronizeBoundInputs` erişim ihlali
(`0xC0000005`) üretiyordu. Tek başına çalışan arka plan aramaları geçiyordu; hata
yalnızca sahne + kare döngüsü + ONNX birlikteyken ortaya çıkıyordu.

Düzeltme: `GameOrchestrator.Think()` eklendi — arama **çağıran iş parçacığında**
senkron çalışır. Unity tarafı (`GameBootstrap.StartAiThink`) bunu kullanır.
`ThinkAsync` Unity'den bağımsız katmanda ve testlerde aynen geçerlidir (Test 33).

### 5.3 Girdi işleyicisi

`StandaloneInputModule` yalnızca eski girdi arka ucuyla çalışır; proje Input System
paketini kullanıyordu (`activeInputHandler: 1`) ve her karede
`InvalidOperationException` atıyordu. `ProjectSettings.asset` içinde
`activeInputHandler: 2` (**Both**) yapıldı.

---

## 6. Ölçümler

| Ölçüm | Değer |
|---|---|
| EditMode testleri | 7 / 7 geçti |
| PlayMode testleri | 5 / 5 geçti |
| `MainScene_SmokeTest` süresi | 0,37 s (60 kare + AI) |
| `FullGame_ReachesGameOver` süresi | 1,82 s (tam oyun, `DepthPly = 0`) |
| `Onnx_MainThread_Search` değerlendirici çağrısı | 146 |
| Bearoff DB pozisyon sayısı | 54 264 |
| `onnxruntime.dll` sürümü | 1.23.20251021.3.a83fc4d |

---

## 7. Oynanabilirlik yamaları (Aşama D sonrası)

Aşama D bittiğinde oyun **iki yerde kilitleniyordu**: bardan giriş ve toplama.
Ayrıca insanın küp teklifi yanıtsız kalıyordu. Dört dosya düzeltildi.

### 7.1 Bardan giriş ve toplama

`BarView` yalnızca görüntüydü (`IPointerClickHandler` yoktu) ve `BoardView`
`ApplyHighlights` yalnızca 1..24 hanelerini dolaşıyordu; bar (0 / 25) hiç
vurgulanmıyor, tıklanamıyordu.

- `BarView` / `TrayView`: `IPointerClickHandler`, `Point`, `Clicked`,
  `Initialize(int)`, `SetHighlight(bool)` eklendi.
- `BoardView`: `CreateBar(name, point)` / `CreateTray(name, point)` imzaları
  değişti, `raycastTarget = true` yapıldı, `TrayClicked` olayı eklendi,
  `ApplyHighlights` bar ve tepsiyi de vurguluyor.
- `BoardInputController`: `TrayClicked` aboneliği, `OnTrayClicked(int)` işleyicisi
  ve `HitTest` içinde tepsi isabet testi (`HitTestTray`) eklendi. Böylece
  **sürükle-bırak ile toplama** da çalışır.

### 7.2 İnsanın küp teklifi

`GameBootstrap.Update` içinde `GamePhase.CubeOffered` dalı yoktu; insan küp
teklif ettiğinde AI yanıt vermiyor ve oyun donuyordu.

- `_pendingAiTake` alanı eklendi.
- "Kup" düğmesi `OfferDouble()` çağrısından **önce**
  `EvaluateCube().ShouldTake` değerini saklar. Bu şart: `EquityCubeAdvisor.Decide`
  yalnızca `PreRoll` fazında gerçek karar üretir, `CubeOffered` fazında
  `ShouldTake = true` sabitini döner.
- `Update` içindeki `CubeOffered` dalı, `state.turn == HumanPlayer` iken (yani
  teklif eden insan, yanıtlayan AI) saklanan kararı uygular.

### 7.3 Tam oyun testi

`SmokeTests` yalnızca 60 kare çalıştığı için yukarıdaki kilitlenmeleri
yakalayamıyordu. `FullGameTests.FullGame_ReachesGameOver` bir oyunu
`GameOver` fazına kadar oynatır (her iki taraf da AI ile), sonucun geçerli
olduğunu ve mars çarpanının en az 1 olduğunu doğrular.

---

## 8. Windows derlemesi

```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.3.8f1\Editor\Unity.exe" `
  -batchmode -nographics -quit `
  -projectPath F:\Projects\Unity\Tavla3D `
  -logFile F:\Projects\Unity\Tavla3D\Logs\build.log `
  -executeMethod TavlaAI.Editor.BuildScript.BuildWindows64
```

Çıktı: `F:\Projects\Unity\Tavla3D\Build\Tavla3D.exe` (+ `Tavla3D_Data`).
`StreamingAssets/models/model.onnx` ve `StreamingAssets/bearoff/bearoff1_v1.bin`
derlemeye kopyalanır; `onnxruntime.dll` `Tavla3D_Data/Plugins/x86_64` altındadır.

Doğrulama: derleme çalıştırıldığında
`%USERPROFILE%\AppData\LocalLow\DefaultCompany\Tavla3D\Player.log` içinde
**hiçbir** istisna/uyarı görünmemelidir.

---

## 9. Bilinen sınırlar

| Sınır | Açıklama |
|---|---|
| AI gücü | gnubg ER **0,1941** (PipBot 0,1283'ün altında). Değer başlığı aşırı dağınık (kalibrasyon eğimi 0,0874). Faz 6 / F5-20. |
| Zar | İnsan "Zar" düğmesine basmalı; otomatik değil. |
| Bardan sürükleme | Tepsiye sürükleme çalışır; bardan sürükleme yok (tıklama-tıklama çalışır). |

---

## 10. Sprite katmanı (görsel zenginlik)

Aşama D sonunda tahta düz renkli dikdörtgenlerden oluşuyordu. `SpriteLibrary`
eklenerek tahta, haneler, pullar, zarlar, küp, bar ve tepsiler **sprite** ile
çizilir hâle geldi.

### 10.1 Kaynak seçimi

`SpriteLibrary.Get(name, fallback)` iki aşamalıdır:

1. `Resources.Load<Sprite>("Sprites/" + name)` — varsa **sanat varlığı** kullanılır.
2. Yoksa sprite **kodla üretilir** (`Texture2D` + `Sprite.Create`).

Böylece proje **hiçbir PNG olmadan** zengin görünür; sonradan gerçek sanat
eklendiğinde **tek satır kod değişmez**. Üretilen dokular `HideFlags.DontSave`
ile işaretlenir ve `Dictionary` içinde önbelleklenir — kare içinde ayırma yoktur.

### 10.2 Varlık adları

`Assets/Backgammon.UI/Resources/Sprites/` altına bırakılacak dosyalar:

| Ad | Kullanım | Önerilen boyut |
|---|---|---|
| `board` | tahta zemini | 512 × 320 |
| `point` | hane üçgeni (yukarı bakar; üst satır dikey çevrilir) | 64 × 256 |
| `checker_white` / `checker_black` | pul | 128 × 128 |
| `die_1` … `die_6` | zar yüzleri | 96 × 96 |
| `cube` | küp yüzü | 96 × 96 |
| `bar` | bar şeridi | 32 × 128 |
| `tray` | toplama tepsisi | 128 × 32 |

> **Önemli:** Bu proje 3B/URP projesidir. PNG'ler **Texture Type = Sprite
> (2D and UI)** olarak içe aktarılmazsa `Resources.Load<Sprite>` `null` döner ve
> sessizce prosedürel yedeğe düşülür.

### 10.3 Çizim sırası

uGUI'de **son kardeş üstte** çizilir. `BoardView.Initialize` bu yüzden
`CheckerPool`'u **en son** kurar: pullar hane üçgenlerinin, barın ve tepsinin
üzerinde kalır. Bu sıra bozulursa pullar üçgenlerin altında kalır.

### 10.4 Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `Infrastructure/SpriteLibrary.cs` | **yeni** — kaynak seçimi + 13 prosedürel üretici |
| `Infrastructure/UiFactory.cs` | `CreateImage(name, parent, color, sprite)` aşırı yüklemesi |
| `Board/CheckerView.cs` | `SetSprite(Sprite)` |
| `Board/CheckerPool.cs` | `Initialize(parent, light, dark)`, `Place(sprite, color, x, y, size)` |
| `Board/BoardView.cs` | tahta zemini, hane üçgeni, pul/bar/tepsi sprite'ları, havuz sırası |
| `Dice/DiceView.cs` | `Die1Image` / `Die2Image`; zar yoksa metin, varsa sprite |
| `Cube/CubeView.cs` | küp sprite'ı + koyu değer yazısı (kontrast) |

`CheckerPool.Place(Color, …)` aşırı yüklemesi korunduğu için **Test 40**
(`CheckerPool_NoRuntimeInstantiate`) anlamı değişmedi.

### 10.5 Doğrulama

| Adım | Sonuç |
|---|---|
| `CompileOnly` | 0 hata, 0 uyarı |
| EditMode | 7 / 7 |
| PlayMode | 5 / 5 (`FullGame_ReachesGameOver` 1,82 s) |
| `BuildWindows64` | `Succeeded (0 hata)` |
| Windows player (12 s) | `Player.log` içinde istisna yok |
| Piksel analizi (1600×1000 pencere) | ahşap %53, koyu üçgen %17, açık üçgen %12, siyah pul %12, beyaz pul %6 |

## 11. Kenar çubuğu yerleşimi (duyarlı / responsive)

Kullanıcı geri bildirimi: *"Tavla tahtası üzerinde buton/yazılar oyun alanını
kapatıyor. Sağ tarafta oyunu engellemeyecek şekilde dizayn et."* Bu bölüm
yerleşimin nasıl kurulduğunu ve neden bir daha bozulamayacağını anlatır.

### 11.1 Tek doğruluk kaynağı: `UiLayout`

`Infrastructure/UiLayout.cs` tüm yerleşim sabitlerini tutar. Hem **sahne
üreticisi** (`Editor/SceneBuilder.cs`) hem **çalışma zamanı**
(`Bootstrap/GameBootstrap.cs`) bu sabitleri kullanır; böylece Editör ile
oyuncu yerleşimi birbirinden ayrışamaz.

| Sabit | Değer | Anlamı |
|---|---|---|
| `ReferenceWidth` / `ReferenceHeight` | 1920 / 1080 | Canvas referans çözünürlüğü |
| `BoardWidth` / `BoardHeight` | 1500 / 938 | Tahtanın referans boyutu |
| `BoardAspect` | 1.5991471 | `BoardWidth / BoardHeight` (16:10) |
| `BoardLeftMargin` / `BoardTopMargin` / `BoardBottomMargin` | 20 | Tahta alanı kenar boşlukları |
| `BoardRightGap` | 20 | Tahta alanı ile kenar çubuğu arası |
| `SidebarWidth` | 352 | Kenar çubuğu genişliği |
| `SidebarRightMargin` | 20 | Kenar çubuğunun sağ kenarı |
| `SidebarReserved` | 392 | `SidebarWidth + SidebarRightMargin + BoardRightGap` |
| `ControlBarY` / `ControlBarHeight` | 1002 / 66 | Alt düğme çubuğu |

### 11.2 Hiyerarşi

```
Canvas
├── BoardArea            (esnetilmiş; offsetMin = 20,20  offsetMax = -392,-20)
│   └── BoardRoot        (ortalanmış; Image + BoardFitter + BoardView)
├── SidebarBackground    (sağa sabitlenmiş)
├── MatchScoreView       (sağa sabitlenmiş)
├── CrawfordBadgeView
├── MatchLengthView
├── DiceView
├── CubeView
├── AnalysisPanelView
├── SettingsPanelView
├── BoardInput           (esnetilmiş; tıklama alanı)
└── GameBootstrap
```

`BoardArea` ekranla birlikte büyür/küçülür. `Board/BoardFitter.cs`
(`[DefaultExecutionOrder(-200)]`) `LateUpdate`'te tahtayı `BoardArea` içine
**en-boy oranını koruyarak** sığdırır:

```
width  = min(available.x, available.y * Aspect)
height = width / Aspect
```

`BoardView.LateUpdate` boyut değiştiğini görürse `Refresh()` çağırır ve hane
geometrisi yeniden hesaplanır. Böylece tahta her pencere boyutunda doğru
oranda kalır ve **hiçbir denetim oyun alanının üzerine binmez**.

### 11.3 Kenar çubuğu dikey sırası

| Denetim | `y` | Boyut |
|---|---|---|
| `MatchScoreView` | 20 | 352 × 90 |
| `CrawfordBadgeView` | 118 | 160 × 32 |
| `MatchLengthView` | 158 | 352 × 66 |
| `DiceView` | 236 | 260 × 112 |
| `CubeView` | 360 | 120 × 200 |
| `AnalysisPanelView` | 572 | 352 × 196 |
| `SettingsPanelView` | 780 | 352 × 220 |
| `ControlBar` (çalışma zamanı) | 1002 | 352 × 66 |

`ControlBar` `GameBootstrap` tarafından üretilir ve `UiFactory.CreateRightAnchored`
ile aynı sağa-sabitlenmiş çizgide durur.

### 11.4 "Ayarlar" paneli hatası

**Belirti:** "Seçenekler butonunu tıklamadan da seçenekler menüsü ekranda
gözüküyor."

**Kök neden:** `SettingsPanelView.SetVisible(bool)` yalnızca `Background`
nesnesini açıp kapatıyordu. `_summary` metni ve üç düğme (`Jacoby`, `Dead cube`,
`Derinlik`) panelin kökü altında **kardeş** nesnelerdi, dolayısıyla görünür
kalıyordu.

**Çözüm:** Tüm çocuklar bir `Content` `RectTransform` altında toplandı;
`SetVisible` artık `_content.gameObject`'i açar/kapatır. `IsVisible` özelliği
eklendi ve `Initialize` sonunda `SetVisible(false)` çağrılır. `GameBootstrap`
"Ayarlar" düğmesinde `SetVisible(!IsVisible)` kullanır.

### 11.5 Yarım kalan hamlenin temizlenmesi

**Belirti:** `Player.log` içinde `InvalidOperationException: ApplyStep: n
değerinde kalan zar yok.`

**Kök neden:** Oyuncu bir adım atıp turu bitirdiğinde `MoveInputController`
içindeki kısmi hamle yaşamaya devam ediyordu. Yeni turda eklenen adım önceki
turdan kalan adımla birleşince geçersiz bir dizi oluşuyordu.

**Çözüm (iki katman):**

1. `GameBootstrap.RefreshViews` sıra veya faz değiştiğinde `_moveInput.Reset()`
   çağırır (`_inputStateKnown` / `_inputTurn` / `_inputPhase` ile izlenir).
2. `BoardInputController.CompleteMove` hamleyi uygulamadan önce
   `BackgammonEngine.ApplyMove`'u **durumun derin kopyası** üzerinde dener
   (`IsLegal`). Kural denetiminden geçmeyen dizi uygulanmaz; seçim temizlenir.

> **Dikkat:** `BackgammonState` bir **sınıftır** ve içinde `sbyte[] board`
> barındırır. `BackgammonState probe = state;` yazmak yalnızca referansı
> kopyalar; `ApplyMove` gerçek oyunu bozar. Doğrulama mutlaka
> `state.Clone()` ile yapılmalıdır.

### 11.6 Doğrulama

| Adım | Sonuç |
|---|---|
| `CompileOnly` | 0 hata |
| `BuildScene` | `Assets/Scenes/Main.unity` — 30 288 B |
| EditMode | 7 / 7 |
| PlayMode | **8 / 8** (`LayoutTests` 2, `InputResetTests` 1) |
| `BuildWindows64` | `Succeeded (0 hata)` |
| Oyuncu ekran görüntüsü | tahta genişliğin ~%89'unu kaplar, kenar çubuğu sağda, çakışma yok |

`LayoutTests.MainScene_SidebarDoesNotOverlapBoard` tahta ile **her** denetimin
dünya koordinatlarındaki kesişimini ölçer; `MainScene_SettingsPanelStartsHidden`
panel görünürlüğünü kilitler; `InputResetTests` sıra değişiminde temizliği
doğrular. Yerleşim ileride bozulursa bu üç test kırmızıya döner.

## 12. Hamle girişi (taş tıklayınca gitmiyor hatası)

Kullanıcı geri bildirimi: *"AI'ye karşı oyun oynarken zara göre taşları hareket
ettirmiyor. Oynatacağım taşı tıklayınca gideceği alternatifleri doğru gösteriyor,
ancak seçtiğimde taş gitmiyor."* Bu bölüm iki ayrı kök nedeni ve kalıcı çözümü
anlatır.

### 12.1 Kök neden A — yasal hedefler eski pozisyondan üretiliyordu

`MoveInputController.Update(state)` her karede
`LegalMoveGenerator.GenerateAllLegalMoves(state, _moves)` çağırıyordu ve
`TryAddStep` sonrasında **yeniden üretmiyordu**. Yani ilk zar oynandıktan sonra
(ör. 19→20) `LegalTargets` hâlâ **başlangıç** pozisyonunu tarif ediyordu.

İkinci tıklama, `From` alanı ilk adımın `To` değeri olan bir adım üretiyor, bu
adım bayat listeye göre doğrulanıyor, `ApplyStep` kural denetiminden geçemiyor ve
`CompleteMove` içindeki `IsLegal` koruması hamleyi **sessizce** düşürüyordu.
Sonuç: taş hiç hareket etmiyor, hata da görünmüyordu.

**Çözüm:** `MoveInputController` artık taban pozisyonu (`_baseState`) ve bir
kazıma tamponu (`_scratch`) tutar. Yeni `Regenerate()` metodu:

1. `PartialMove.Count == 0` ise `_baseState` üzerinden yasal hamleleri üretir.
2. Aksi hâlde `_scratch.CopyFrom(_baseState)` yapar, `PartialMove`'u uygular ve
   yasal hamleleri **kısmi hamleden sonraki pozisyondan** üretir.

`Regenerate()`; `Update`, `TryAddStep`, `UndoStep` ve `Reset` tarafından çağrılır.
Böylece ikinci zarın hedefleri her zaman gerçek pozisyona göre hesaplanır.

### 12.2 Kök neden B — kısmi hamle hiç çizilmiyordu

`BoardView` yalnızca `GameOrchestrator.State`'i çiziyordu; kısmi hamle
`MoveInputController` içinde kaldığı için tahta değişmiyordu. Geçerli bir ilk
adım bile ekranda görünmüyordu.

**Çözüm:** `BoardInputController.ApplyPreview()` eklendi. `Refresh()`'in başında
çağrılır:

```csharp
BackgammonState preview = _orchestrator.State.Clone();
BackgammonEngine.ApplyMove(preview, _input.PartialMove);   // try/catch
_model.Update(preview);
_board.Refresh();
```

> **Dikkat:** `BackgammonState` bir **sınıftır**. `Clone()` olmadan
> `ApplyMove` gerçek oyunu bozar (bkz. §11.5).

### 12.3 Seçim artık yeni hanede kalıyor

`OnPointClicked` / `OnTrayClicked` / `OnDragEnded` içindeki
`_input.ClearSelection()` çağrıları başarılı `TryAddStep` sonrasından
**kaldırıldı**. Seçim, taşın gittiği haneye taşınır; böylece kalan zarın hedefleri
anında görünür ve oyuncu ikinci tıklamayı yapabilir.

### 12.4 Yeni düğmeler

| Düğme | Satır | Davranış |
|---|---|---|
| `Zar` | 1 | Zar atar |
| `Kup` | 1 | Küp teklif eder |
| `Turu bitir` | 1 | Önce `CommitPartialMove()` (kısmi hamleyi uygular), sonra `EndTurn()` |
| `Yeni oyun` | 2 | Yeni maç |
| `Geri al` | 2 | `UndoStep()` — son adımı geri alır (`CanUndo` ile pasifleşir) |
| `Ayarlar` | 2 | Ayarlar panelini açar/kapatır |

`BoardInputController` yeni üyeler: `CanUndo`, `UndoStep()`,
`CommitPartialMove()`.

### 12.5 Zar göstergesi kısmi hamlede de güncelleniyor

`GameBootstrap` artık `_boardModel.Changed` olayına abone
(`OnBoardModelChanged` → `DiceView.Refresh(_boardModel)`). Kısmi hamle
önizlemesi `_model.Update(preview)` çağırdığı için kalan zarlar ekranda anında
düşer.

> **Dikkat:** Abonelik `_boardModel = new BoardViewModel();` satırından **sonra**
> yapılmalıdır; aksi hâlde `NullReferenceException` alınır.

### 12.6 Doğrulama

| Adım | Sonuç |
|---|---|
| `dotnet build TavlaAI_Project.slnx -c Release` | 0 uyarı, 0 hata |
| `Backgammon.UI.Tests` | **12 / 12** (Test 30b: `MoveInputController_PartialMoveContinuesFromNewPosition`) |
| `Backgammon.Tests` | **229 / 229** |
| `CompileOnly` | 0 hata |
| `BuildScene` | `Assets/Scenes/Main.unity` — 30 299 B |
| EditMode | 7 / 7 |
| PlayMode | **10 / 10** (`MoveFlowTests` 2 yeni) |
| `BuildWindows64` | `Succeeded (0 hata)` |
| Oyuncu duman testi (14 s) | `Player.log` 38 satır, istisna yok |

`MoveFlowTests.ClickClick_PlaysBothDiceAndMovesChecker` gerçek tıklama akışını
(19 → 20 → 23) uçtan uca çalıştırır ve tahtanın gerçekten değiştiğini doğrular;
`PartialMove_IsRevertedWhenSelectionIsCleared` geri alma davranışını kilitler.

### 12.7 Yan bulgu — `IsOneSidedBearoff` temas pozisyonlarını kabul ediyordu

Bu düzeltme sırasında `FullGameTests` kırmızıya döndü:

```
ArgumentException: Toplam taş sayısı 15'i aşamaz: 268
  at BearoffIndex.Rank
  at BearoffDatabase.TryGetCdf
  at GameOrchestrator.RollsToOff
```

**Kök neden:** `BearoffDatabase.IsOneSidedBearoff(board, player)` yalnızca
**kendi** taşlarının ev bölgesinde olduğunu doğruluyor, rakibin aynı bölgede taşı
olup olmadığına bakmıyordu. `ToCounts` ev bölgesini `(byte)`'a çevirdiği için
rakibin negatif taşları (ör. `-3` → `253`) sessizce toplama giriyor ve
`Rank` 15 sınırını aşıyordu.

**Çözüm:** `IsOneSidedBearoff` artık rakibin ev bölgesinde taşı varsa `false`
döner (beyaz için 19–24, siyah için 1–6). Bu aynı zamanda doğru semantiktir:
rakip ev bölgesindeyse pozisyon **temastır** ve tek taraflı bearoff tablosu
geçersizdir. Regresyon testi:
`BearoffTests.BearoffDatabase_RejectsContactPositions`.

## 13. Oynanış hataları (altı yama)

Kullanıcı geri bildirimi:

> 1. rakibin taşını kırdığımda benim taş eksiliyor (kayboluyor)
> 2. Rakibin taşı kırılınca kırık hanesinden içeri girmiyor, meçhul.
> 3. taşları toplarken toplanan taşlar görünmüyor.
> 4. oyun sonunda skor değişmiyor.
> 5. rakip hangi zarı attığı görülmüyor.
> 6. Rakibin ve benim katlama isteklerim işlemiyor.

Altı hatanın **beşi** üç kök nedene indirgenir; altıncısı iki ayrı kusurdur.

### 13.1 Hata 1 + 2 — vurulan taş siliniyordu (bayrak kaybı)

**Kök neden.** `MoveInputController.TryAddStep` adımı yeniden inşa ediyordu:

```csharp
// ÖNCE — bayraklar atılıyor
MoveStep step = new MoveStep((byte)SelectedPoint, (byte)toPoint, die, MoveFlags.None);
```

`BackgammonEngine.ApplyStep` rakibin taşını **yalnızca** `step.IsHit` true ise
bara gönderir:

```csharp
if (step.IsHit)
{
    s.board[BarIndex(opp)] += (sbyte)opp;
    s.board[step.To] = 0;
}
s.board[step.To] += (sbyte)turn;
```

Bayraksız bir vuruş adımı bu yüzden `board[To]`'yu sıfırlıyor (rakip taşı
**yok oluyor**) ve bara hiç taş koymuyordu. Hata 1 ve 2 aynı kusurun iki yüzüdür.

**Çözüm.** `TryAddStep` artık üretecin verdiği `MoveStep`'i **olduğu gibi**
kopyalar:

```csharp
MoveSequence seq = _moves[k];
MoveStep step = seq.Steps[seq.Count - 1];   // Hit / BearOff / FromBar korunur
```

Aynı kusur `BearOff` bayrağını da düşürdüğü için toplama hamleleri de sessizce
bozuluyordu; bu düzeltme hata 3'ün motor tarafını da kapatır.

### 13.2 Hata 3 — toplanan taşlar tepside çizilmiyordu

`TrayView.SetCount(int)` yalnızca `CountLabel.text` yazıyordu; `BoardView.Refresh()`
tepsilere **hiç taş yerleştirmiyordu**. `CheckerPool` 30 taş kapasitelidir ve
toplam taş sayısı her zaman 15 + 15 = 30 olduğu için kapasite yeterlidir —
eksik olan tek şey çizim çağrısıydı.

**Çözüm.** `BoardView.StackTray(LayoutRect, int, Sprite)` eklendi (2 sütunlu
ızgara) ve `Refresh()` sonunda çağrılıyor:

```csharp
StackTray(_layout.WhiteTray, _model.WhiteBorneOff, SpriteLibrary.CheckerWhite);
StackTray(_layout.BlackTray, _model.BlackBorneOff, SpriteLibrary.CheckerBlack);
```

> **Doğrulama numarası:** havuzdaki görünür taş sayısı her zaman **30** olmalıdır.
> Vurulan taş silinirse veya toplanan taş çizilmezse 29 çıkar. PlayMode testleri
> tam olarak bu sayımı denetler.

### 13.3 Hata 4 — oyun sonunda skor değişmiyordu

`GameOrchestrator.Refresh()` `_isGameOver` / `_result` alanlarını **yazıyor** ama
sonucu skora **uygulamıyordu**; puan yalnızca `StartNextGame()` içinde
işleniyordu. Kullanıcı "Yeni oyun"a basmadan skor güncellenmiyordu.

**Çözüm.** `BackgammonEngine.StartNextGame` ikiye ayrıldı:

| Metot | Görev |
|---|---|
| `ApplyResult(state, in last)` | Sonucu skora işler, maç bitti mi karar verir |
| `PrepareNextGame(state)` | Tahtayı sıfırlar, Crawford'u kurar, skoru **korur** |
| `StartNextGame(state)` | `ApplyResult` + `PrepareNextGame` (eski davranış) |

`GameOrchestrator` artık `_resultApplied` bayrağıyla `Refresh()` içinde
`ApplyResult`'u **anında** çağırır; `StartNextGame()` yalnızca
`PrepareNextGame` yapar. Böylece puan tam olarak bir kez işlenir.

### 13.4 Hata 5 — rakibin zarları görünmüyordu

`BackgammonEngine.EndTurn` `rolledDice[0..1]`'i sıfırlar. `GameBootstrap.Update`
AI için `RollDice()` çağırıp **aynı karede** `StartAiThink()` → `ApplyMove` →
`EndTurn` zincirini çalıştırdığı için zarlar hiçbir karede çizilmiyordu.

**Çözüm (iki katman).**

1. `DiceView.SetOverride(byte, byte, string)` / `ClearOverride()` eklendi.
   `Refresh` sırasında tahtada zar yoksa (`Die1 == 0`) ve sabitleme varsa
   sabitlenen zarlar çizilir, `RemainingLabel` sabitleme başlığını gösterir.
2. `GameBootstrap` AI zarlarını yakalar ve ekranda tutar:

| Alan | Anlam |
|---|---|
| `AiRollDisplaySeconds = 0.9f` | AI düşünmeye başlamadan önce zarların görünme süresi |
| `AiDiceTailSeconds = 1.6f` | Hamleden sonra zarların ekranda kalma süresi |
| `_aiRollPending` / `_aiRollAt` | Zar gösterimi bekleniyor mu |
| `_aiDiceVisibleUntil` | Sabitlemenin sona ereceği an |
| `_aiDie1` / `_aiDie2` | Yakalanan zar değerleri |

`Update()` ilk iş olarak `UpdateAiDiceOverride()` çağırır; `Moving` fazında
`_aiRollPending` ise `StartAiThink()` geciktirilir. "Zar" düğmesi sabitlemeyi
temizler.

### 13.5 Hata 6 — katlama (küp) istekleri işlemiyordu

İki ayrı kusur vardı.

**(a) İnsan tarafı.** `BackgammonEngine.CanOffer` `phase == PreRoll` ister.
Kullanıcı "Kup" düğmesine bastığında zar çoktan atılmış (`Moving`) olduğu için
`CanOffer` false dönüyor ve düğme **sessizce** hiçbir şey yapmıyordu.

**Çözüm.** `BackgammonEngine.RevertRoll(state, in es)` eklendi: atılmış ama
**hiç oynanmamış** zarı geri alır (`phase = PreRoll`). `GameOrchestrator.TryOfferDouble()`
şu sırayı izler:

1. `phase == Moving` ve `PartialMove` boş ve `remainingCount == rolledDice` ise
   `RevertRoll` ile `PreRoll`'a dön.
2. `CanOffer` denetle, `OfferDouble()` çağır.
3. Rakibin (AI) kararını **`OfferDouble`'dan önce** hesapla ve
   `PendingOpponentTake` özelliğinde sakla.

**(b) AI tarafı.** `EquityCubeAdvisor.Decide` `phase == PreRoll` değilse
`ShouldDouble = false, ShouldTake = true` döner. `OfferDouble()` fazı
`CubeOffered` yaptığı için "al" kararı teklif **öncesinde** alınmalıdır — yukarıdaki
3. adım bunu garanti eder.

`GameBootstrap`'taki "Kup" düğmesi artık `_orchestrator.TryOfferDouble()` çağırır
ve `_orchestrator.PendingOpponentTake` değerini kullanır.

### 13.6 Regresyon testleri

| Dosya | Test sayısı | Kapsam |
|---|---|---|
| `Backgammon.UI.Tests/GameplayFixTests.cs` | 7 | vuruş bayrağı korunur, vurulan taş bara gider, toplama bayrağı, oyun sonunda anında skor, çift sayım yok, `TryOfferDouble` zarı geri alır, taş oynandıktan sonra reddedilir |
| `Backgammon.Tests/MatchFlowSplitTests.cs` | 16 | `ApplyResult` (puan × küp, mars, maç sonu, para oyunu, Crawford, geçersiz kazanan), `PrepareNextGame` (sıfırla + skoru koru, maç bitti, Crawford), `StartNextGame` (tek uygulama), `RevertRoll` (oynanmamış, çift, oynanmış, `Moving` değil, Crawford) |
| `Assets/Backgammon.UI/Tests/PlayMode/GameplayFixPlayModeTests.cs` | 3 | vurulan taş bara gider + 30 taş çizilir, toplanan taş tepside çizilir, `DiceView` sabitlemesi |

### 13.7 Doğrulama

| Adım | Sonuç |
|---|---|
| `dotnet build TavlaAI_Project.slnx -c Release` | 0 uyarı, 0 hata |
| `Backgammon.UI.Tests` | **19 / 19** |
| `Backgammon.Tests` | **245 / 245** |
| `Backgammon.Inference.Tests` | 57 / 57 |
| `pytest ml/tests` | 20 / 20 |
| `CompileOnly` | 0 hata |
| EditMode | 7 / 7 |
| PlayMode | **13 / 13** |
| `BuildWindows64` | Succeeded (0 hata) |
---

## 14. İkinci oynanış turu (altı yama)

Kullanıcı geri bildirimi (madde 1-6) ve kök nedenleri:

| # | Belirti | Kök neden | Düzeltme |
|---|---|---|---|
| 1 | Money game dışındaki maçlarda oyun bitince skor değişmiyor | "Yeni oyun" düğmesi `BackgammonEngine.NewGame()` çağırıyordu; bu `BackgammonState.Reset()` üzerinden `whiteScore`/`blackScore` alanlarını **sıfırlıyordu** | `GameOrchestrator.NewGame()` artık maç bitmemişse `BackgammonEngine.PrepareNextGame()` (skoru/Crawford'u korur), maç bittiyse `NewMatch()` çağırır |
| 2 | AI katlama teklifinde küp "1" görünüyor, kabul/ret işlemiyor | (a) `CubeView.Initialize()` `Accepted`/`Declined` delegelerini **değer olarak** `CreateButton`'a geçiriyordu; `GameBootstrap` aboneliği `Initialize()`'dan sonra olduğu için düğmeler kalıcı olarak ölüydü. (b) `OfferDouble` `cubeValue`'yu değiştirmediğinden `CubeViewModel.Value` teklif sırasında eski değeri gösteriyordu | (a) `RaiseAccepted()`/`RaiseDeclined()` örnek metotları eklendi (olay tıklama anında okunur). (b) `CubeViewModel.DisplayValue` eklendi: `Offered` iken `Value * 2` |
| 3 | Seçeneklerde renk seçimi yok | `SettingsPanelView` yalnızca zorluk/ipucu/kup seçenekleri sunuyordu; `GameBootstrap.HumanPlayer` `const` idi | `SettingsPanelView.ColorKey`/`PlayerColor`/`ToggleColor()` eklendi (varsayılan **Beyaz**, `PlayerPrefs`), `GameBootstrap.HumanPlayer`/`AiPlayer` örnek özellik oldu, `ApplyPlayerColor()` eklendi |
| 4 | Zar bloke ise sıra karşıya geçmiyor | `BackgammonEngine.PassTurn()` vardı ama hiç çağrılmıyordu | `GameOrchestrator.HasLegalMoves` eklendi; `GameBootstrap.Update()` `Moving` fazında hamle yoksa `DiceView.SetCaption("hamle yok - sira geciyor")` gösterip `BlockedPassSeconds` (1,2 sn) sonra `EndTurn()` çağırır |
| 5 | Açılışta yüksek zar atan başlamıyor gibi görünüyor | `RollOpening` zaten yüksek zarı seçiyordu; sorun AI açılışı kazandığında hamlesinin **aynı karede** oynanması ve açılış zarlarının hiç görünmemesiydi | `GameBootstrap.AnnounceOpeningRoll()` eklendi; `_openingRollPending` ile `OpeningRollSeconds` (1,6 sn) beklenir, `DiceView.SetCaption("acilis d1-d2 - sen basliyorsun|rakip basliyor")` |
| 6 | Toplama alanı oyuncunun rengine göre yukarıda kalıyor | `BoardLayout` `WhiteTray` alt / `BlackTray` üst olarak sabitlenmişti | `BoardLayout.Calculate(w, h, bool flipVertical)` eklendi; `BoardView.FlipVertical` ile siyah oynayan insanın tepsi **her zaman sağ altta** |

### 14.1 Renk seçimi ve tahta çevirme

`GameBootstrap.ApplyPlayerColor(sbyte color, bool restartMatch)`:

1. `_humanPlayer = color` (`+1` beyaz, `-1` siyah), `AiPlayer = -color`.
2. `BoardView.FlipVertical = _humanPlayer < 0` — `BoardView.Recalculate()` yeni
   `BoardLayout.Calculate(w, h, flip)` çağrısını yapar, bar yarılarını takas eder.
3. `MatchScoreView.HumanColor = _humanPlayer` — skor satırı `"Sen (Beyaz) 3 - 1 Rakip"`.
4. Renk değiştiyse ve `restartMatch` ise geçici durum sıfırlanır ve
   `_orchestrator.NewMatch(...)` çağrılır.

`BoardInputController.HitTestTray` değişmedi: tepsi `Image` dikdörtgenlerini
`BoardView` yeniden yerleştirdiği için isabet testi çevirmeyi otomatik izler.

### 14.2 Bloke zar akışı

`GameBootstrap.Update()` içinde `Moving` fazında:

```
if (!_orchestrator.HasLegalMoves) {
    if (_blockedAt == 0f) { _blockedAt = Time.unscaledTime; DiceView.SetCaption("hamle yok - sira geciyor"); }
    else if (Time.unscaledTime - _blockedAt >= BlockedPassSeconds) { _blockedAt = 0f; DiceView.ClearCaption(); _orchestrator.EndTurn(); }
}
```

`RefreshViews()` `phase != Moving` olduğunda `_blockedAt` değerini temizler.

### 14.3 Regresyon testleri

| Dosya | Test sayısı | Kapsam |
|---|---|---|
| `Backgammon.UI.Tests/GameplayFix2Tests.cs` | 9 | `NewGame` skoru korur, maç bittiğinde yeni maç, `DisplayValue` teklifte 2, `Take` sonrası 2, varsayılan yerleşimde beyaz tepsi sağ altta, çevrilmiş yerleşimde siyah tepsi sağ altta, çevirme noktaları ayrık tutar, `HasLegalMoves` bloke/açılış |
| `Assets/Backgammon.UI/Tests/PlayMode/GameplayFix2PlayModeTests.cs` | 4 | teklifte küp etiketi "2" + iki düğme görünür, **Kabul/Ret düğmeleri olayı tetikler** (ölü düğme regresyonu), renk değişimi tahtayı çevirir ve kendi tepsi sağ altta kalır, bloke zarda sıra otomatik geçer |

> **Not:** `DiceView.SetOverride` artık geçici durum yazısını (`_caption`) temizler.
> Sabitleme bilinçli bir gösterimdir; açılış zarı yazısı rakibin zarlarını ezmemelidir.

### 14.4 Doğrulama

| Adım | Sonuç |
|---|---|
| `dotnet build TavlaAI_Project.slnx -c Release` | 0 uyarı, 0 hata |
| `Backgammon.UI.Tests` | **28 / 28** |
| `Backgammon.Tests` | **245 / 245** (tek başına koşulduğunda; tam pakette `PerformanceTests.GenerateAfterStates_Throughput` makine yüküne göre eşiğin altında kalabilir) |
| `Backgammon.Inference.Tests` | 57 / 57 |
| `pytest ml/tests` | 181 / 181 (+1 yavaş test atlanır), belge tutarlılığı 20 / 20 |
| `CompileOnly` | 0 hata |
| EditMode | 7 / 7 |
| PlayMode | **17 / 17** |
| `BuildWindows64` | Succeeded (0 hata) |
| Player duman testi | `Player.log` temiz; tahta, tepsiler ve kenar çubuğu çiziliyor |
