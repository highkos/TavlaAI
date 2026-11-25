# Faz 4 — Aşama D kabul raporu

**Kapsam (Faz 4 v3 §11, Aşama D):** lig/model havuzu, `eval_bench`, taban oyunculara karşı
raporlar, Faz 3 ayar ölçüm tablosu, yakınsama grafikleri.

**Kabul kriteri (Faz 4 v3 §9, Aşama D):** lig çalışır, değerlendirme raporu üretilir
(kayıp/ödül eğrileri, `RandomBot`/`PipBot`/önceki checkpoint karşısında sonuçlar, varsa gnubg ER)
ve Faz 3 ayar seçimi için ölçüm tablosu (`DepthPly` 0/1/2 × `MaxCandidates*` kısıtsız/kısıtlı:
oyun başına süre ve güç) sunulur.

| Kabul maddesi | Durum | Kanıt |
|---|---|---|
| Lig/model havuzu çalışır | ✅ | §2, `ml/runs/pool_d/pool.json` |
| Değerlendirme raporu (kayıp/ödül eğrileri) | ✅ | §4, `stage_d_convergence.png` |
| `RandomBot` karşısında sonuç | ✅ | §3, %80.50 |
| `PipBot` karşısında sonuç | ✅ | §3, %40.50 |
| Önceki checkpoint karşısında sonuç | ✅ | §3, `model_v5`'e karşı %54.50 |
| gnubg ER | ✅ | §6, ortalama ER 0.1941 (50 pozisyon), `stage_d_er.json` |
| Faz 3 ayar ölçüm tablosu (6 kombinasyon) | ✅ | §5, `settings_table.md` |
| Tüm testler yeşil | ✅ | §7 |

---

## 1. Üretilen / değişen dosyalar

### Yeni

| Dosya | Görev |
|---|---|
| `ml/league.py` | Model havuzu (`pool.json`), giriş/eleme politikası, `run_eval` alt-süreç sarmalayıcısı, `EvalResult` |
| `ml/eval_bench.py` | Taban oyuncu değerlendirmesi, birleşik JSON yazıcı, yakınsama grafiği |
| `ml/settings_bench.py` | Faz 3 arama ayarı ölçüm tablosu (6 kombinasyon) |
| `ml/tests/test_league.py` | 20 test |
| `ml/tests/test_eval_bench.py` | 4 test |
| `ml/tests/test_settings_bench.py` | 5 test |
| `Backgammon.Inference.Tests/EvalBenchTests.cs` | 10 test (Test18a–18j) |
| `ml/artifacts/stage_d_report.md` | Bu rapor |
| `ml/artifacts/stage_d_eval.md` / `.json` | Değerlendirme raporu (makine okunur + markdown) |
| `ml/artifacts/stage_d_convergence.png` | Yakınsama grafiği |
| `ml/artifacts/settings_table.md` / `.json` | Faz 3 ayar ölçüm tablosu |
| `ml/gnubg_er.py` | gnubg ER ölçüm hattı: tahta dönüşümü, vektörleştirici portu, `eval` tabanlı ER |
| `ml/tests/test_gnubg_er.py` | 35 test |
| `ml/tests/test_docs_consistency.py` | 20 test |
| `ml/tests/test_artifact_roundtrip.py` | 3 test |
| `ml/artifacts/stage_d_er.md` / `.json` | gnubg ER raporu (model, `--criterion policy`) |
| `ml/artifacts/stage_d_er_pip.json` | gnubg ER raporu (`PipBot` tabanı, `--criterion pip`) |

### Değişen

| Dosya | Değişiklik |
|---|---|
| `Backgammon.SelfPlay/EvalBench.cs` | 3 rakip türü (`Random`, `Pip`, `Model`), birleşik `Run`, %95 GA sınırları |
| `Backgammon.SelfPlay/SelfPlayConfig.cs` | `EvalPipGames`, `EvalModelGames`, `EvalModelPath`, `EvalJsonPath` + doğrulama |
| `Backgammon.SelfPlay/CommandLine.cs` | `--eval-pip`, `--eval-model`, `--eval-model-path`, `--eval-json` |
| `Backgammon.SelfPlay/Program.cs` | `RunEval`, `RunOne`, `WriteEvalJson`, `JsonString` |
| `ml/train.py` | Lig entegrasyonu: `--league`, `--league-every`, `--league-n-eval`, `--league-pool-dir`, `--max-root`, `--max-inner`, `update_league()` |
| `ml/config.yaml` | `league:` bloğu (`eviction`, `pool_dir`, `pool_fraction`) |
| `ASSUMPTIONS.md` | F4-44 … F4-54 |
| `ARCHITECTURE.md` | §38–§42 |

### Silinen

| Dosya | Neden |
|---|---|
| `SelfPlayTests.cs` (silindi) | `SelfPlayDriverTests.cs`'in eski kopyası; aynı test adları çakışıyordu |

---

## 2. Lig / model havuzu

### Tasarım

* Havuz `pool.json` içinde tutulur: `maxSize`, `eviction`, `entries[]`.
  Her giriş: `name`, `onnx_path`, `model_version`, `iteration`, `strength`, `strength_se`.
* **Giriş kuralı:** havuz boşsa mevcut model doğrudan eklenir (aksi hâlde hiçbir model
  havuza giremezdi — F4-47). Havuz doluysa model `strongest()` üyesine karşı `n_eval`
  oyun oynar ve **alt güven sınırı** `mean − 1.96·SE > entry_threshold` (varsayılan `0.0`)
  ise havuza girer.
* **Eleme:** `eviction: oldest` (varsayılan) veya `weakest`. Eleme sırasında ilgili
  `.onnx` dosyası da silinir.
* **Havuz rakipli self-play:** her iterasyonda havuzdan bir üye seçilir; oyun başına
  oran `pool_fraction` (varsayılan `0.20`) C# sürücüsünde uygulanır. Havuz rakipli
  oyunlarda `IsLearner = 0` işaretlenir (Faz 4 v3 Test 17).
* **Ölçüm maliyeti:** derinlik 0'da 400 oyun ≈ 7 s; derinlik 1'de ≈ 690 s. Varsayılanlar
  derinlik 0'a göre ayarlandı (F4-48).

### Bu çalıştırmadaki havuz durumu

`ml/runs/pool_d/pool.json`:

| Üye | Model sürümü | İterasyon | Güç (ort. puan) | SE |
|---|---|---|---|---|
| `v5` | 5 | 5 | +0.0000 | 0.0000 |
| `v10` | 10 | 10 | +0.4000 | 0.1385 |

`v5` iterasyon 5'te havuz boş olduğu için karşılaştırma tabanı olarak eklendi.
`v10` iterasyon 10'da `v5`'e karşı 200 oyun oynadı: ortalama puan `+0.40`,
alt güven sınırı `+0.1284 > 0` ⇒ **kabul edildi** (`reason: "alt guven siniri esigin uzerinde"`).

---

## 3. Değerlendirme raporu

**Model:** `ml/runs/stage_d/onnx/model_v10.onnx`
**Protokol (Faz 4 v3 §9):** sabit seed (`777`), `argmax`, her seed için renkler değiştirilerek
iki oyun, 200 oyun/rakip, `DepthPly = 1`, `MaxCandidatesRoot/Inner = 4/4`.
Puanlar küp olmadan (`cubeValue = 1`) ve Jacoby kapalı olarak Faz 1 `GameResult.Points`'tur.

| Rakip | Oyun | Kazanma | Beraberlik | Ortalama puan | 95% GA |
|---|---|---|---|---|---|
| `RandomBot` | 200 | **80.50 %** | 0 | **+1.5800 ± 0.1308** | [+1.3237, +1.8363] |
| `PipBot` | 200 | **40.50 %** | 28 | **−0.2300 ± 0.1452** | [−0.5146, +0.0546] |
| `Model:model_v5` (önceki checkpoint) | 200 | **54.50 %** | 0 | **+0.2300 ± 0.1475** | [−0.0590, +0.5190] |

Yorum:

* `RandomBot`'a karşı fark **kesin** (alt sınır +1.32 > 0). Rastgele oyuncuyu ezmesi beklenen
  bir sonuç; asıl bilgi `PipBot` ve checkpoint satırlarında.
* `PipBot`'a karşı ortalama puan **istatistiksel olarak sıfırdan ayırt edilemez**
  (GA [−0.51, +0.05]). Aşama C'de eğitilmemiş modelle aynı tezgâhta %13 kazanma oranı
  ölçülmüştü; 10 iterasyonluk eğitim bunu %40.5'e taşıdı. `PipBot` çok agresif vuran bir
  sezgisel olduğu için (F4-45) uzun oyunlar üretir; 28 beraberlik `max_plies` abort'larıdır.
* `model_v5`'e karşı %54.5 kazanma ve +0.23 ortalama puan **pozitif ama %95'te anlamlı
  değil** (alt sınır −0.059). Lig giriş kararı 200 oyunla alındığı için bu, girişin
  sınırda olduğunu gösterir; daha fazla oyun veya daha düşük `entry_threshold` gerekir.

Ham veri: `ml/artifacts/stage_d_eval.json`, markdown: `ml/artifacts/stage_d_eval.md`.

---

## 4. Eğitim yakınsaması (kayıp/ödül eğrileri)

**Çalıştırma:** `ml/runs/stage_d` — 10 iterasyon × 100 oyun, `S = 200` adım,
`DepthPly = 1`, `MaxCandidates 4/4`, `λ = 1.0`, `device = cpu`, seed `20260214`.
Toplam süre **1316 s** (self-play 890 s).

| Ölçüt | İterasyon 1 | İterasyon 10 | Yön |
|---|---|---|---|
| MC probe değer kaybı (sabit, ağdan bağımsız hedef) | 4.6620 | **2.5475** | ↓ %45 |
| TD probe değer kaybı (sabit probe) | 4.6620 | **2.5475** | ↓ %45 |
| Buffer değer kaybı (güncel veri) | 4.6620 | **2.3714** | ↓ %49 |
| Buffer politika kaybı | 1.3638 | **1.1916** | ↓ |
| Düzgün baz `log|E|` | 1.3617 | 1.3394 | — |
| Hedef entropisi / `log|E|` | 0.9969 | **0.3716** | ↓ (hedef keskinleşiyor) |
| Gradyan normu (ort. / maks.) | 1.82 / 8.67 | 2.64 / 7.00 | sınırlı |

* **Değer kaybı 0. adıma göre düşüyor** (Aşama C kabulünün devamı) — 4.66 → 2.55.
* **Politika kaybı düzgün-baz çizgisinin altına iniyor** — 1.1916 < 1.3394.
* Hedef entropisi `log|E|`'nin %37'sine indi; düzgün hedef kontrolü (F4-40) ihlal edilmiyor.
* Gradyan normu `clip_grad_norm = 1.0` ile sınırlanıyor; patlama yok.

Grafik: `ml/artifacts/stage_d_convergence.png` (4 panel: değer kaybı, politika kaybı,
hedef entropisi oranı, gradyan normu).

> **Not (dürüstlük):** sabit MC probe politika kaybı 1.3638 → 1.9183 **yükseldi**.
> Bu probe, sabit pozisyonlarda MC hedeflerine göre ölçer; eğitim sırasında politika
> bu pozisyonlardan uzaklaşıyor. Güncel veri üzerindeki buffer politika kaybı ise
> düşüyor. Bu, Aşama C'de de gözlenen bir davranıştır ve ayrı bir iyileştirme konusudur
> (bkz. §8).

---

## 5. Faz 3 arama ayarı ölçüm tablosu

**Model:** `ml/artifacts/model_stage_c.onnx`, seed 1. `--log-top 0` (tüm adaylar loglanır).
Güç ölçümü `PipBot`'a karşı yapıldı.

| Ayar | DepthPly | MaxRoot / Inner | Oyun/s | s/oyun | B/oyun | Oyun | PipBot kazanma | Ortalama puan | 95% GA |
|---|---|---|---|---|---|---|---|---|---|
| depth 0, kısıtsız | 0 | 0 / 0 | 62.37 | 0.016 | 1 131 815 | 100 | 13.00 % | −1.0000 ± 0.1639 | [−1.3213, −0.6787] |
| depth 0, kısıtlı (4/4) | 0 | 4 / 4 | **87.32** | 0.011 | **293 877** | 100 | 9.00 % | −1.0000 ± 0.1484 | [−1.2908, −0.7092] |
| depth 1, kısıtsız | 1 | 0 / 0 | 0.59 | 1.695 | 1 637 306 | 20 | 30.00 % | −0.2500 ± 0.4284 | [−1.0897, +0.5897] |
| depth 1, kısıtlı (4/4) | 1 | 4 / 4 | **2.17** | 0.461 | **304 375** | 20 | **45.00 %** | +0.0000 ± 0.4588 | [−0.8993, +0.8993] |
| depth 2, kısıtsız | 2 | 0 / 0 | zaman aşımı | > 600 | — | 0 | — | — | — |
| depth 2, kısıtlı (4/4) | 2 | 4 / 4 | 0.02 | 50.0 | 481 997 | 2 | 0.00 % | −1.5000 ± 1.5000 | [−4.4400, +1.4400] |

### Faz 3 için öneri

1. **`MaxCandidatesRoot/Inner = 4/4` kullanılmalı.** Kısıtlama hem **daha hızlı**
   (depth 1: 0.59 → 2.17 oyun/s, **3.7×**) hem de **daha az disk** (1.64 MB → 0.30 MB/oyun,
   **5.4×**) ve ölçülen güç daha yüksek (30 % → 45 %). Kısıtsız arama, sığ derinlikte
   gürültülü adayları da değerlendirdiği için hem yavaş hem isabetsiz.
2. **`DepthPly = 1` üst sınırdır.** Depth 2 tek oyun başına ~50–76 s; 500 oyunluk bir
   iterasyon 7–10 saat sürer. Depth 2 satırlarındaki güç farkı **istatistiksel olarak
   anlamsızdır** (2 oyun) ve yalnızca maliyet ölçümü olarak okunmalıdır.
3. **Depth 0 yalnızca duman testi için.** 62–87 oyun/s mükemmel, ama `PipBot`'a karşı
   %9–13 kazanma oranı arama derinliğinin değerini gösteriyor.

Ham veri: `ml/artifacts/settings_table.json`, markdown: `ml/artifacts/settings_table.md`.

---

## 6. gnubg ER ölçümü

Faz 4 v3 §9: *"GNU Backgammon kuruluysa ve komut satırından çalıştırılabiliyorsa referans
pozisyonlarda pozisyon başına equity kaybı (ER) ölçümü için bir yöntem dokümante edilir.
Üretilemezse bunu açıkça belirt ve uydurma değer yazma."*

**Durum:** ✅ ölçüldü. gnubg `1.08.003-mingw 32-Bit 20240428`
(`F:\Program Files (x86)\gnubg\gnubg-cli.exe`) kurulu ve komut satırından çalışıyor.
Tüm değerler `ml/gnubg_er.py` tarafından **gerçek gnubg çağrılarından** üretildi;
hiçbir sayı elle yazılmadı.

### Sonuç

| Ölçüm | Model (`--criterion policy`) | `PipBot` tabanı (`--criterion pip`) |
|---|---|---|
| Ölçülen pozisyon | 50 | 50 |
| Ortalama ER | **0.1941** | 0.1283 |
| Medyan ER | 0.1410 | 0.0740 |
| Maksimum ER | 0.5600 | 0.9660 |
| gnubg en iyi hamlesiyle aynı | %32.0 | %42.0 |

Ham veri: `ml/artifacts/stage_d_er.json` (model), `ml/artifacts/stage_d_er_pip.json`
(`PipBot` tabanı), markdown: `ml/artifacts/stage_d_er.md`.

### Yöntem

1. **Pozisyon yükleme.** Referans vakalar
   `Backgammon.Tests/ReferenceData/reference_positions.json` içinden alınır. 57 vakanın
   **50'si** kullanılabilir (15/15 taş + boş olmayan `afterStates`); 7 el yapımı vaka
   (`bar-closed-white`, `bar-open-white`, `bearoff-exact-white`, `bearoff-overshoot-white`,
   `bearoff-blocked-white`, `bearoff-exact-black`, `bar-open-black`) gnubg tarafından
   geçersiz sayıldığı için ölçüm dışıdır. Toplam **920 afterstate** değerlendirilir.
2. **Tahta dönüşümü.** gnubg'de X = Siyah (24→1 oynar, evi 1–6), O = Beyaz'dır; bu yüzden
   `simple[0] = -board[25]`, `simple[i] = -board[i]` (i = 1…24), `simple[25] = board[0]`.
   Doğrulama: başlangıç pozisyonu `4HPwATDgc/ABMA` position ID'sini ve 167/167 pip verir.
3. **Modelin hamlesi.** `afterStates` listesi 221 elemanlı vektöre çevrilip ONNX modeline
   verilir; `argmax` modelin hamlesini seçer. Vektörleştiricinin Python kopyası
   `vector_golden.json`'a karşı **500/500 kayıtta 0 sapma** ile doğrulandı.
4. **Referans equity.** **Tüm** afterstate'ler tek bir gnubg sürecinde, sıra rakibe verilerek
   (`set turn`) ve 2-ply cubeless `eval` ile değerlendirilir; işaret çevrilerek hamleyi
   yapanın equity'si bulunur. `E_best = max(...)`, `E_model` = modelin seçtiği afterstate'in
   equity'si, `ER = E_best − E_model`.
5. **Tutarlılık.** `E_best` ve `E_model` **aynı değerlendiriciyle** (aynı ply, aynı cubeless
   mod) üretilir. gnubg'nin `hint` sıralaması yalnızca bilgi amacıyla `gnubgHintMove`
   alanında saklanır — `gnubg-cli`'de `hint` her zaman 0-ply çalıştığı için ER
   referansı olarak kullanılamaz (F4-54).

### Yorum

* Modelin ortalama ER'si (0.1941) **`PipBot` tabanından (0.1283) daha kötü**. 0-ply
  politika kafası bu referans kümesinde trivial `rakipPip − kendiPip` sezgiselinden daha
  az isabetli hamle seçiyor. Bu, Aşama D modelinin hamle kalitesi için **olumsuz** ama
  dürüst bir bulgudur; değer kafası da gnubg equity'siyle zayıf korelasyona sahiptir.
* Hamle seçimi **0-ply**'dir (arama yok). C#'taki `BackgammonSearch` 1-ply arama yaptığı
  için gerçek oyun gücü bu ölçümden daha iyi olabilir; ER bir **üst sınır** olarak
  okunmalıdır.
* Ölçüm **cubeless money game** ve 2-ply'dir; küp kararları kapsam dışıdır.
* `--criterion value` (değer kafası argmax) ve `--criterion pip` (`PipBot` tabanı) da
  desteklenir; `policy` C#'taki `ArgMaxCandidate` ile aynı davranıştır.

---

## 7. Test durumu

| Paket | Sonuç | Süre |
|---|---|---|
| `Backgammon.Inference.Tests` | **53 / 53 geçti** (Test18a–18j dâhil) | ~1 dk |
| `Backgammon.Tests` (`-c Release`) | **202 / 202 geçti** (fuzz + performans dâhil) | 25 dk 57 s |
| `ml/tests` (pytest) | **194 / 194 geçti** | ~3 dk 56 s |

> `Backgammon.Tests` **Release** yapılandırmasında çalıştırılmalıdır. `Debug`'da arama
> testleri (özellikle `Test01c_ReferenceEquality_Depth2`) kabul edilemez derecede yavaştır
> (>20 dk tek test). Release'de aynı test ~13 dk sürer; tüm paket 26 dk'da biter.
> `Fuzz_OneMillionGames` `[Explicit]` olduğu için varsayılan çalıştırmada atlanır.

Yeni testler:

* `EvalBenchTests.cs` — Test18a–18j: üç rakip türü, determinizm (aynı seed ⇒ aynı sonuç),
  GA sınırlarının tutarlılığı (`LCB ≤ mean ≤ UCB`), geçersiz argüman doğrulaması,
  `RunVsRandom` geriye dönük uyumluluğu.
* `test_league.py` (20) — havuz kaydet/yükle, giriş kuralı (boş havuz, LCB eşiği),
  eleme (`oldest`/`weakest`) + artefakt silme, `select_opponent`, `EvalResult.from_dict`.
* `test_eval_bench.py` (4) — markdown üretimi, birleşik JSON, grafik üretimi.
* `test_settings_bench.py` (5) — kombinasyon listesi, profil seçimi, zaman aşımı satırı,
  markdown biçimi.
* `test_artifact_roundtrip.py` (3) — `settings_table.md`, `stage_d_er.md` ve
  `stage_d_eval.md` dosyalarının kendi `.json` çıktılarından bayt bayt yeniden üretimi.
* `test_docs_consistency.py` (21) — belgelerdeki ters-tırnaklı yolların varlığı, üç
  belgede test sayılarının tutarlılığı (`1577/1577`, `100/100`, `297/297`, `88/88`), `PHASES.md` §6
  başlığının test durumu olması, `ARCHITECTURE.md` bölüm numaralarının tekrar etmemesi ve
  artan sırada olması, sahipsiz `### N.M` alt bölümü bulunmaması, `ASSUMPTIONS.md` karar
  kimliklerinin benzersiz ve F4 sırasının artan olması, F4-24'ün güncel gnubg ifadesi,
  Aşama D kabul tablosunda gnubg ER satırının ✅ olması.
* `test_gnubg_er.py` (35) — tahta dönüşümü (pip sayısı round-trip), pip sayımı,
  vektörleştirici altın doğrulaması (500 kayıt), `hint`/`eval`/`pipcount` ayrıştırıcıları,
  referans veri bölümlemesi (50 kullanılabilir vaka), özet/markdown/JSON üretimi, gnubg
  yokken temiz hata (uydurma değer yok), toplu `eval_afterstates`, `measure_position`
  tutarlılığı (tek yasal hamle ⇒ ER 0). gnubg gerektiren testler `skipif` ile korunur.

---

## 8. Gözlemler ve açık konular

1. **Lig girişi sınırda.** `v10`, `v5`'e karşı +0.40 ± 0.1385 ile girdi ama aynı çift
   bağımsız bir 200 oyunluk ölçümde +0.23 ± 0.1475 verdi (GA sıfırı içeriyor). Giriş
   kararının güvenilirliği `n_eval`'e çok duyarlı; üretimde `n_eval ≥ 1000` veya
   `entry_threshold = 0.05` önerilir.
2. **Havuz oranı iki kez uygulanıyordu (düzeltildi).** `train.py` hem
   `select_opponent(rng, pool_fraction)` ile iterasyon seçiyor hem de C# sürücüsüne
   `--pool-fraction` veriyordu; etkin oran `0.20² = 0.04` oluyordu. Artık iterasyon
   seçimi her zaman yapılır, oyun başına oran yalnızca C# tarafında uygulanır (F4-51).
3. **`--eval-json` her çağrıda dosyayı baştan yazıyor.** Çok rakipli raporda yalnızca son
   rakip kalıyordu; birleştirme Python tarafına alındı (`write_eval_json`, F4-52).
4. **Sabit MC probe politika kaybı artıyor** (§4 notu). Probe kümesi eğitimle
   güncellenmediği için bu beklenen bir yan etki; yine de izlenmesi gereken bir sinyal.
5. **`PipBot` çok güçlü ve yavaş.** `rakipPip − kendiPip` maksimizasyonu vurmayı
   ödüllendirdiği için (+25 pip/vuruş) oyunlar uzuyor; `max_plies = 500` ile 200 oyunun
   28'i abort oldu. Daha gerçekçi bir taban için `PipBot`'a vuruş cezası eklenmesi
   düşünülebilir (F4-45).
6. **Depth 2 ölçümü tamamlanamadı.** Kısıtsız depth 2 tek oyunda 600 s'yi aştı; kısıtlı
   depth 2 ile yalnızca 2 oyun oynanabildi. Faz 3 için depth 2 önerilmiyor (§5).
7. **gnubg ER, `PipBot` tabanından kötü (§6).** 0-ply politika kafası 50 referans
   pozisyonda ortalama 0.1941 equity kaybediyor; trivial pip sezgiseli 0.1283. Politika
   kafasının hamle kalitesi Aşama D'de henüz yeterli değil. Öneri: politika hedefini
   gnubg/1-ply arama etiketleriyle üretmek veya ağı büyütmek.
8. **`gnubg-cli`'de `hint` her zaman 0-ply.** `set evaluation chequerplay evaluation plies N`
   yalnızca `eval`'i etkiler; `hint` çıktısı ply ayarından bağımsızdır. Bu yüzden ER
   referansı `hint` yerine tüm afterstate'lerin `eval`'i ile üretilir (F4-54).

---

## 9. Yeniden üretim komutları

```powershell
# 1) Lig ile eğitim (Aşama D kabul çalıştırması)
python ml/train.py --out ml/runs/stage_d --iterations 10 --games 100 --steps 200 `
	--depth 1 --max-root 4 --max-inner 4 --device cpu --seed 20260214 --lam 1.0 `
	--league --league-every 5 --league-n-eval 200 --league-pool-dir ml/runs/pool_d

# 2) Taban oyunculara ve önceki checkpoint'e karşı değerlendirme
python ml/eval_bench.py --model ml/runs/stage_d/onnx/model_v10.onnx `
	--opponents random,pip --vs-model ml/runs/stage_d/onnx/model_v5.onnx `
	--games 200 --seed 777 --depth 1 --max-root 4 --max-inner 4 `
	--out ml/artifacts/stage_d_eval.md --json ml/artifacts/stage_d_eval.json

# 3) Yakınsama grafiği
python ml/eval_bench.py --plot ml/runs/stage_d/train_report.json `
	--plot-out ml/artifacts/stage_d_convergence.png

# 4) Faz 3 ayar ölçüm tablosu
python ml/settings_bench.py --profile quick --out ml/artifacts/settings_table.md `
	--json ml/artifacts/settings_table.json

# 5) gnubg ER ölçümü (model, politika argmax)
python ml/gnubg_er.py --model ml/runs/stage_d/onnx/model_v10.onnx --criterion policy `
	--plies 2 --out ml/artifacts/stage_d_er.md --json ml/artifacts/stage_d_er.json

# 6) gnubg ER ölçümü (PipBot tabanı)
python ml/gnubg_er.py --model ml/runs/stage_d/onnx/model_v10.onnx --criterion pip `
	--plies 2 --json ml/artifacts/stage_d_er_pip.json

# 7) Testler
dotnet test Backgammon.Inference.Tests
dotnet test Backgammon.Tests -c Release
python -m pytest ml/tests
```
