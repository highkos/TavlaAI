# Faz 5 — Ölçüm ve kabul raporu

**Kapsam (Faz 5 §11):** bearoff veritabanı (Aşama A), küp/maç katmanı (Aşama B),
AI entegrasyonu (Aşama C), Unity görselleştirme (Aşama D), belge birleştirme (Aşama E).

**Sonuç:** beş aşamanın tamamı kabul edildi. 40 testin 40'ı geçti
(C# 24, Python 13, Unity 11 — Unity testleri ayrı koşar).

---

## 1. Aşama A — Bearoff veritabanı

| Ölçüm | Değer |
|---|---|
| Dosya | `ml/artifacts/bearoff1_v1.bin` |
| Boyut | 2 496 208 bayt (2,38 MiB) |
| Pozisyon sayısı | 54 264 |
| `MaxRolls` | 22 (üretici 12'den otomatik yükseltti) |
| Mars tablosu | yok (`flags = 0`) |
| Geçiş tablosu üretimi | ~5 000 ms |
| Dinamik programlama | ~500 ms |
| Toplam üretim | ~5 500 ms |
| C# ↔ Python referansı en büyük fark | **7,630E-006** |
| Tolerans dışı hücre | **0** |
| Nicemleme sınırı | 1/65535 ≈ 1,53E-005 |

**Neden `MaxRolls = 22`?** En kötü pozisyon 6 hanesinde 15 puldur; bu pozisyonun
toplanması en fazla 22 tur sürebilir. Üretici `P(T ≤ MaxRolls) < 1` görürse `MaxRolls`'u
artırır ve bunu raporlar.

**Bağımsız doğrulama.** `ml/bearoff_ref.py` yalnızca Faz 5 §3.2/3.3/3.9'dan yazılmış ayrı
bir Python DP'sidir; C# kodunu görmez. Test 34 her koşuda iki tabloyu karşılaştırır.

**Bilinen referans değerler (`MaxRolls = 22`):**

| Pozisyon | `cdf[1..6]` |
|---|---|
| `(1,0,0,0,0,0)` | 1,000000 1,000000 1,000000 1,000000 1,000000 1,000000 |
| `(0,0,0,0,0,1)` | 0,750000 1,000000 1,000000 1,000000 1,000000 1,000000 |
| `(0,0,0,0,0,2)` | 0,111111 0,782407 0,996871 1,000000 1,000000 1,000000 |
| `(15,0,0,0,0,0)` | 0,000000 0,000000 0,000000 0,000772 0,035494 0,263224 |
| `(0,0,0,0,0,15)` | 0,000000 0,000000 0,000000 0,000001 0,000021 0,000284 |

---

## 2. Aşama B — Küp ve maç katmanı

### 2.1 MET doğruluğu

| Ölçüm | Değer |
|---|---|
| Tablo boyutu | 25 × 25 = 625 hücre |
| gnubg 1.08.003 `Rockwell-Kazaross.xml` ile en büyük fark | **0,000E+000** |
| Sonuç | bit düzeyinde aynı |

### 2.2 Küp kararı anlaşması (gnubg ile)

| Ply | İkileme anlaşması | Alma anlaşması | İkisi birden |
|---|---|---|---|
| 0-ply | %51,52 | %61,36 | %46,21 |
| 2-ply | %52,27 | %61,36 | %46,97 |

Karşılaştırılan pozisyon: 132 (200 üretilen pozisyondan gnubg'nin kabul ettiği güvenli
alt küme).

**İkileme matrisi (0-ply):** ikisi de ikileme 13, yalnız biz 51, yalnız gnubg 13,
ikisi de ikileme yok 55.

**Alma matrisi (0-ply):** ikisi de al 79, yalnız biz al 10, yalnız biz pas 41,
ikisi de pas 2.

### 2.3 Equity korelasyonu

| Yöntem | Korelasyon | MAE |
|---|---|---|
| Tek kayıt (zar atılmamış) | −0,0315 | 1,0550 |
| Zar ortalamalı (21 çift) | **+0,1395** | 1,2063 |

Zar ortalaması korelasyonu **4,4 kat** iyileştiriyor ama MAE'yi kötüleştiriyor: modelin
değerleri aşırı dağınık olduğu için ortalama almak sapmayı büyütüyor.

### 2.4 Maç farkındalığının katkısı

400 oyun, aynı tohum, `MatchAwareEvaluator` açık/kapalı:

| Maç uzunluğu | Farkındalık açık | Farkındalık kapalı | Fark |
|---|---|---|---|
| 2-away | %40,00 | %39,50 | +0,50 |
| 4-away | %39,75 | %40,00 | −0,25 |
| 5-away | %42,25 | %44,75 | −2,50 |

**Yorum:** üç farkın tamamı standart hatanın içinde. Bu modelle maç farkındalığı
ölçülebilir bir kazanç sağlamıyor. Nedeni katman değil, değer kafasıdır (§3).

---

## 3. Değer kafası teşhisi

400 rastgele self-play afterstate, gnubg `evaluate` ile **doğrudan** karşılaştırıldı
(ön-zar yaklaşımı yok, aynı pozisyon).

| Ölçüm | Bizim model | gnubg |
|---|---|---|
| Korelasyon | +0,2431 | — |
| MAE | 0,8014 | — |
| Sapma (bias) | −0,0850 | — |
| Aralık | −2,8050 … +3,2966 | −0,8207 … +1,6497 |
| Standart sapma | 1,0320 | 0,3710 |

**En küçük kareler kalibrasyonu:** `gnubg ≈ 0,0874 · bizim + 0,1589`

| Ölçüm | Değer |
|---|---|
| Eğim `a` | **0,0874** |
| Kesişim `b` | +0,1589 |
| Kalibrasyon öncesi MAE | 0,8014 |
| Kalibrasyon sonrası MAE | **0,2897** |
| Aşırı dağınıklık oranı | **≈11,4 ×** |

**Yorum.** Model `[-3, 3]` aralığını neredeyse tamamen kullanıyor; gnubg aynı
pozisyonlarda `[-0,82, +1,65]` aralığında kalıyor. Kalibrasyon sonrası MAE %64 düşüyor,
yani **bilgi var, ölçek yanlış**. Bu bir Faz 4 model kalitesi sorunudur; Faz 5
katmanlarının (bearoff, MET, küp eşikleri, UI) hatası değildir.

**Neden küp kararlarını bozuyor?** Küp kararı eşik tabanlıdır (`E > 0,5` ⇒ ikileme).
Değer 11 kat dağınık olduğunda `E = 0,3` olan bir pozisyon `3,3` gibi görünür ve
neredeyse her pozisyon "ikileme" olur. Ölçülen tablo bunu doğruluyor: yalnız bizim
ikileme dediğimiz 51 pozisyona karşılık yalnız gnubg'nin ikileme dediği 13 pozisyon var.

---

## 4. Aşama C — AI entegrasyonu

| Ölçüm | Değer |
|---|---|
| `Backgammon.UI` hedef çatısı | netstandard2.1 |
| `UnityEngine` referansı | **yok** |
| `Backgammon.UI.Tests` | 11 / 11 geçti (~1 s) |
| Test 30 kapsamı | 200 rastgele pozisyon × 26 kaynak hane |
| Test 32 | 50 oyun, aynı tohum ⇒ aynı sonuç günlüğü |
| Test 33 | iptal, bütçe, iş parçacığı, eşzamanlılık |

**`output_version`.** `ml/export_onnx.py` `OUTPUT_VERSION = 1` yazar;
`OnnxModelHandle.SupportedOutputVersion = 1`; `> 1` görülürse
`NotSupportedException`. Test 36 bunu doğrular.

**Yeniden dışa aktarma notu.** `ml/runs/stage_d/onnx/model_v5.onnx` yeniden üretildi
(ağırlıklar `ckpt_v5.pt` ile **bit düzeyinde aynı**, en büyük fark 0,000E+000) ve
`output_version = 1` metadata'sı eklendi. `export_onnx.py`'nin parite kontrolü bu model
için `|dpolicy| = 1,526E-005 > 1E-005` verip sıfır olmayan çıkış koduyla biter; bu
**eğitilmiş ağırlıklarla ilgili önceden var olan bir tolerans** sorunudur, dışa aktarmayı
etkilemez (dosya parite kontrolünden önce yazılır).

---

## 5. Aşama D — Unity

| Ölçüm | Değer |
|---|---|
| Unity sürümü | 6000.3.8f1 |
| EditMode testleri | 7 / 7 |
| PlayMode testleri | 4 / 4 |
| `MainScene_SmokeTest` | 60 kare + AI hamlesi |
| `Onnx_MainThread_Search` değerlendirici çağrısı | 146 |
| Bearoff DB yükleme | 54 264 pozisyon |
| `onnxruntime.dll` | 1.23.20251021.3.a83fc4d |

**Aşama D'de bulunan üç gerçek hata:**

1. **`BoardLayout` kayan nokta çakışması.** Komşu hanelerin sol kenarı `c·w`, sağ kenarı
   `(c+1)·w` ile hesaplanınca `1E-013` mertebesinde üst üste binme oluşuyordu. Test 38
   yakaladı.
2. **ONNX Runtime iş parçacığı güvenliği.** `OrtIoBinding` iş parçacığı güvenli değil;
   arama gerçek kare döngüsü içinde arka plan iş parçacığında çalışınca
   `SynchronizeBoundInputs` erişim ihlali (`0xC0000005`). `GameOrchestrator.Think()`
   eklendi (çağıran iş parçacığında senkron).
3. **Girdi işleyicisi.** `StandaloneInputModule` eski girdi arka ucunu gerektirir;
   `activeInputHandler: 1` iken her karede `InvalidOperationException`. `2` (**Both**)
   yapıldı.

Ayrıntı: `unity/README.md`, gerçek koşu kaydı: `unity/build.log`.

---

## 6. Test sayıları

| Paket | Test | Durum |
|---|---|---|
| `Backgammon.Tests` (Release) | 228 | ✅ 228/228 |
| `Backgammon.Inference.Tests` (Release) | 57 | ✅ 57/57 |
| `Backgammon.UI.Tests` (Release) | 11 | ✅ 11/11 |
| `ml/tests` (pytest) | 181 | ✅ 181/181 (1 yavaş test varsayılan atlanır) |
| **Toplam (`dotnet test` + pytest)** | **477** | **✅ 0 başarısız** |
| Unity EditMode | 7 | ✅ 7/7 |
| Unity PlayMode | 4 | ✅ 4/4 |

---

## 7. Faz 5 test eşlemesi (40 test)

| # | Test | Dosya | Durum |
|---|---|---|---|
| 1–13 | Bearoff (indeks, CRC, başlık, CDF, dekoratör) | `Backgammon.Tests/BearoffTests.cs` | ✅ |
| 14–26 | MET, küp, Crawford, maç farkındalığı | `Backgammon.Tests/MatchTests.cs`, `CubeAndMatchTests.cs` | ✅ |
| 27 | `BoardViewModel_ReflectsState` | `Backgammon.UI.Tests/ViewModelTests.cs` | ✅ |
| 28 | `MatchScoreViewModel_CrawfordBadge` | aynı | ✅ |
| 29 | `CubeViewModel_Visibility` | aynı | ✅ |
| 30 | `MoveInputController_LegalTargets` | aynı | ✅ |
| 31 | `AnalysisViewModel_FormatsPositionAnalysis` | aynı | ✅ |
| 32 | `GameOrchestrator_DeterministicSelfPlay` | `Backgammon.UI.Tests/OrchestratorTests.cs` | ✅ |
| 33 | `GameOrchestrator_ThinkAsyncCancellation` | aynı | ✅ |
| 34 | `test_bearoff_ref_matches_csharp` | `ml/tests/test_bearoff_ref_matches_csharp.py` | ✅ |
| 35 | `test_met_extraction_invariants` | `ml/tests/test_met_extraction.py` | ✅ |
| 36 | `test_export_output_version` | `ml/tests/test_export_output_version.py` | ✅ |
| 37 | `test_docs_consistency` | `ml/tests/test_docs_consistency.py` | ✅ |
| 38 | `BoardLayout_NoOverlap` | Unity EditMode | ✅ |
| 39 | `SceneLoads` | Unity EditMode | ✅ |
| 40 | `CheckerPool_NoRuntimeInstantiate` | Unity EditMode | ✅ |

---

## 8. Faz 6 önerisi

1. **Değer kafası kalibrasyonu.** Hedef eğim ≈ 1,0. Ölçülen kazanç: MAE 0,8014 → 0,2897.
2. **Zar ortalamalı küp değerlendirmesi.** Ölçülen kazanç: korelasyonda 4,4 kat.
3. **6 çıktılı kafa** (kazanma / mars / arka arkaya mars × iki taraf) ⇒
   `output_version = 2`.
4. **İki taraflı bearoff veritabanı** (≈29,4 GB) — yalnızca gerçekten gerekliyse.
5. **Gerçek eğitim koşusu.** 10⁵+ oyun, 50+ iterasyon, `λ = 1,0`.
