# GÖREV EMİRİ (v1): Dünya Sınıfı Güç, 6 Çıktılı Değer Kafası, Ölçekli Eğitim, Kusursuz Ürün — Faz 6

## 🎯 Proje Vizyonu

Faz 1 v4 (motor), Faz 2 v4 (221 nöronlu vektörleştirici), Faz 3 v7 (politika yönlendirmeli
expectiminimax arama), Faz 4 v3 (ONNX köprüsü, self-play, eğitim laboratuvarı, lig,
`eval_bench`, gnubg ER ölçümü) ve Faz 5 v1 (bearoff veritabanı, küp/maç katmanı,
`Backgammon.UI`, Unity ürünü) üzerine; bu faz **gücü** ve **ürünü** aynı anda hedefler.

Faz 5 bittiğinde oyun **oynanabilir** bir üründü ama **güçlü değildi**: gnubg ER **0,1941**,
`PipBot`'a karşı **%40,5**, değer kafası **≈11,4 kat aşırı dağınık** (kalibrasyon eğimi
0,0874). Faz 6 bu üç sayıyı tersine çevirmek zorundadır.

Faz 6 bittiğinde:

* Model **6 çıktılı** değer kafası üretir (`W, GW, BW, L, GL, BL`) ve equity bu altı
  olasılıktan **türetilir**; küp kararı ile arama **aynı** sayıyı görür.
* Değer kafası **kalibre**dir: gnubg'ye karşı eğim **0,85–1,15** aralığında.
* Model **gnubg 2-ply** karşısında **≥ %50**, **gnubg 0-ply** karşısında **≥ %65** kazanır.
* gnubg ER (2-ply küpsüz, 200 pozisyon) **< 0,02**; 3-ply'de **< 0,01**. Bu, **insan dünya
  şampiyonu seviyesidir** (en iyi insanlar ≈ 0,02–0,03 ER).
* Eğitim **iki hatta** koşabilir: **Track L** (bu makine: GTX 1650, 4 GB) ve **Track H**
  (EVREN platformu: 8 düğüm × 8 NVIDIA H200, InfiniBand NDR 400G). Aynı kod, aynı
  konfigürasyon şeması, aynı shard biçimi; yalnızca ölçek farklı.
* Ürün **kusursuz**dur: açılış kitabı, hamle sıralaması ve equity kaybı gösterimi, 6
  olasılıklı analiz paneli, geri al/yinele, maç kaydet/yükle, renk körü güvenli palet,
  klavye girişi, TR/EN yerelleştirme, kurulum paketi.

> **Dürüstlük notu (güç beklentisi).** Dünya şampiyonu seviyesi ≈ **0,003 ER**'dir (gnubg
> 4-ply + büyük ağ). Faz 6'nın hedefi **0,01–0,02 ER**'dir; bu **insan dünya şampiyonu**
> seviyesidir ama **gnubg 4-ply** seviyesi değildir. Aradaki farkın dağılımına dair
> **tahmin** (ölçüm değil, `PHASES.md` §8.3 ile uyumlu): eğitim ölçeği ≈ %55, arama
> derinliği ≈ %25, 6 çıktılı kafa + kalibrasyon ≈ %15, kapasite ≈ %5. Faz 6 ilk üçünü
> hedefler. **Uydurma "başarı" sayısı yazılmaz; ölçüm raporlanır.**

> **Donanım dürüstlüğü.** Ağ **36 bin parametre**dir; H200'ün 989 TFLOPS bf16'sı bu ağ
> için **anlamsızdır**. H200'ün gerçek değeri **paralel self-play veri üretimi** ve **çok
> daha büyük ağ**dır. Bu doküman H200'ü "daha hızlı eğitim" için değil, **"daha çok ve daha
> iyi veri"** için kullanır (Bölüm 3.3). Aksi iddia edilirse yanlış olur.

---

## 0. Çalışma Kuralları (Ajan İçin Zorunlu)

1. **Hot path'te sıfır allocation hedefi (C# çekirdek):** `OnnxPolicyValueEvaluator`,
   `BearoffAwareEvaluator`, `MatchAwareEvaluator`, `EquityCubeAdvisor`, `BackgammonSearch`
   ısınma sonrası heap allocation yapmamalıdır (`GC.GetAllocatedBytesForCurrentThread`
   farkı ile ölçülür). **Unity katmanı bu kuralın dışındadır**, ancak arama ve değerlendirme
   çağrıları Unity'den de olsa bu kurala uyar.
2. **Faz 1–5 API'lerine bağlılık.** Faz 1 v4, Faz 2 v4, Faz 3 v7, Faz 4 v3 ve Faz 5 v1'deki
   tipler, imzalar, `AfterStateList` SoA yapısı, **221 vektör haritası** ve `SHARD_FORMAT.md`
   v1 **olduğu gibi** kullanılır. **`BackgammonSearch`, `BackgammonVectorizer`,
   `AfterStateList` gövdeleri DEĞİŞMEZ.** Bu dokümanda **açıkça onaylanmış** eklemeler:
   (a) `output_version = 2` ONNX sözleşmesi (Bölüm 5.4), (b) `ShardFormat` **v2** (Bölüm 7.2,
   v1 okunmaya devam eder), (c) `SearchSettings`'e **iki** yeni alan (Bölüm 9.2),
   (d) `ml/tests/test_docs_consistency.py` `EXPECTED_COUNTS` güncellemesi. Bunların dışında
   bir değişiklik gerekiyorsa **gerekçeli teklif olarak raporla ve onay bekle**.
3. **Tek doğruluk kaynağı.** Vektörleştirme yalnızca C#'ta. **Python'da vektörleştirici
   yazılmaz.** Bearoff DP'sinin tek doğruluk kaynağı C#'tır. **Yeni:** 6 çıktılı kafanın
   equity türetmesi de **tek yerde** (C# `OutcomeDistribution.FromProbabilities`) yapılır;
   Python eğitim tarafı aynı formülü **test ile** doğrular (Test 52).
4. **Bağımlılık yönü tek yönlüdür:** `Unity → Backgammon.UI → Backgammon.Core`.
   `Backgammon.UI` **`Backgammon.Inference`'a referans vermez**. `Backgammon.Core` hiçbir
   Unity tipi bilmez.
5. **TDD.** Her aşamada testler **önce** yazılır (kırmızı). Unity testleri **EditMode**;
   PlayMode yalnızca sahne/etkileşim dumanı içindir.
6. **Aşamalı teslim.** Bölüm 15'e göre ilerle, onay almadan sonraki aşamaya geçme.
   Belirsiz noktayı tahmin etme, **açık soru** olarak raporla.
7. **Doğrulanmamış sayılar.** Bu dokümandaki eşik, tolerans ve boyut sayıları
   **başlangıç/yer tutucu** değerlerdir (Bölüm 13). Formül olarak verilmiş sayılar
   (ör. `C(21,6) = 54264`, `54264² = 2 944 581 696`) **kesin matematiktir**, ölçüm değildir.
8. **Yeniden üretilebilirlik.** Her eğitim koşusu `ml/runs/<ad>/` altında
   `config.yaml` (kopya), `git rev` (varsa), `seed`, `torch`/`cuda` sürümü ve
   `metrics.jsonl` bırakır. **Seed'siz koşu raporlanmaz.**
9. **Donanım nötrlüğü.** Hiçbir kod yolu yalnızca CUDA'da çalışmaz; `--device cpu` her
   zaman geçerli bir yedektir. Hiçbir kod yolu yalnızca EVREN'de çalışmaz; Track L
   tam işlevsel bir yedektir.

---

## 1. Kapsam ve Sabit Kararlar

| Konu | Karar |
|---|---|
| Oyun türü | **Money game + maç oyunu** (Faz 5 ile aynı) |
| Küp | Kapsam içi; tek küp, `cubeValue ∈ {1..64}`, `cubeOwner ∈ {0,±1}`. Beaver/Raccoon/Chouette **kapsam dışı** |
| Jacoby | Yapılandırılabilir, varsayılan **kapalı** |
| Crawford | Kapsam içi (Faz 5'te hazır) |
| Vektör | **221 nöron, `feature_version = 1` DEĞİŞMEZ.** Yeni özellik eklenmez |
| Değer kafası | **6 çıktı** (`W, GW, BW, L, GL, BL`), `output_version = 2` |
| Equity türetmesi | `E = W − L + GW − GL + BW − BL` (C# tek kaynak) |
| Politika kafası | Tek logit (Faz 4 sözleşmesi **değişmez**) |
| Arama | Expectiminimax; **depth 2 varsayılan**, depth 3 seçenek |
| Bearoff | 1 taraflı DB (Faz 5) **korunur**; 2 taraflı DB **kapsam dışı** (Bölüm 14) |
| Eğitim hattı | **Track L** (yerel GTX 1650) + **Track H** (EVREN H200) |
| Shard biçimi | **v2** (6 çıktı hedefi + oyun sonu dağılımı); v1 **okunur** |
| Ürün | Unity 6000.3.8f1, URP 2D, uGUI (Faz 5 ile aynı) |
| Dil/çerçeve | C# `netstandard2.1` (Core/Inference/UI), `net10.0` (testler/araçlar), Python ≥ 3.10 |
| Test çerçevesi | NUnit (C#), pytest (Python), Unity Test Framework |

---

## 2. Başlangıç Durumu (ölçülmüş, Faz 5 sonu)

Bu sayılar **ölçülmüştür** ve Faz 6'nın kıyas tabanıdır. Hiçbiri tahmin değildir.

| Ölçüm | Değer | Kaynak |
|---|---|---|
| gnubg ER (2-ply küpsüz, 50 pozisyon) | **0,1941** | `ml/artifacts/stage_d_er.md` |
| `PipBot` ER | 0,1283 | aynı |
| `PipBot` karşısında kazanma | **%40,50** | `PHASES.md` §7 |
| `RandomBot` karşısında kazanma | %80,50 | aynı |
| `model_v5` karşısında kazanma | %54,50 | aynı |
| Değer kafası korelasyonu (400 afterstate) | **+0,2431** | `ml/artifacts/stage_b_afterstates.md` |
| Değer kafası MAE | 0,8014 | aynı |
| Değer kafası kalibrasyon eğimi | **0,0874** | aynı |
| Değer aralığı / std (bizim) | −2,8050…+3,2966 / 1,0320 | aynı |
| Değer aralığı / std (gnubg) | −0,8207…+1,6497 / 0,3710 | aynı |
| Küp anlaşması (0-ply, 132 poz.) | ikileme %51,52 / alma %61,36 | `ml/artifacts/stage_b_cube.md` |
| Küp anlaşması (2-ply, 132 poz.) | ikileme %52,27 / alma %61,36 | aynı |
| Maç farkındalığı (400 oyun) | 2-away %40,00 vs %39,50 | `PHASES.md` §12.3 |
| ONNX çıkarım (CPU, kova 128) | ~724 000 poz/sn | `PHASES.md` §7 |
| ONNX çıkarım (CUDA, kova 2048) | ~1 241 000 poz/sn | aynı |
| Ağ boyutu | 221→128→64→{1,1} ≈ **36 000 parametre** | `ml/model.py` |
| Bearoff DB | 2 496 208 bayt, 54 264 pozisyon, `MaxRolls = 22` | `PHASES.md` §12.2 |
| MET ↔ gnubg | max \|Δ\| = 0,000E+000 (625 hücre) | `PHASES.md` §12.3 |
| Test sayıları | core 245, inference 57, ui 85, pytest 181 | `ml/tests/test_docs_consistency.py` |
| Unity | EditMode 7/7, PlayMode 43/43 | Faz 5 sonu |

**Yorum.** Üç bağımsız ölçüm aynı şeyi söylüyor: model **bilgi taşıyor** ama **ölçeği
yanlış** ve **yeterince eğitilmemiş**. Kalibrasyon sonrası MAE 0,8014 → **0,2897**'ye
düşüyor (bilgi var, ölçek yanlış). `PipBot`'a karşı %40,5 ise **eğitim ölçeği** sorunudur
(500 oyun, 20 iterasyon). Faz 6 ikisini de ayrı ayrı ele alır.

---

## 3. Donanım Gerçekliği ve İki Eğitim Hattı

### 3.1 Track L — bu makine (ölçülmüş)

| Bileşen | Değer |
|---|---|
| CPU | Intel Core i7-9750H, **6 çekirdek / 12 iş parçacığı**, 2,60 GHz |
| RAM | **31,9 GB** |
| GPU | **NVIDIA GeForce GTX 1650**, 4 GB GDDR5, Turing (SM 7.5) |
| GPU notu | **bf16 yok** (Turing bf16 desteklemez); FP16 tensor çekirdeği var |
| CUDA (PyTorch) | 12.1, `torch 2.5.1+cu121`, `torch.cuda.is_available() == True` |
| ONNX Runtime (Python) | 1.23.2, sağlayıcılar: `AzureExecutionProvider`, `CPUExecutionProvider` — **CUDA sağlayıcısı KURULU DEĞİL** |
| Disk (F:) | 427 GB boş |
| OS | Windows 10 Pro |
| gnubg | `F:\Program Files (x86)\gnubg\gnubg-cli.exe` (1.08.003-mingw 32-Bit) |

**Track L'nin gerçek darboğazı GPU değil, self-play'dir.** 36 bin parametreli bir MLP
GTX 1650'de saniyede milyonlarca pozisyon işler; asıl maliyet **C# motorunda oyun
üretmek** ve **veriyi diske yazmaktır**. Bu yüzden Track L'de:

* Eğitim **FP32** yapılır (AMP'nin karmaşıklığı bu ağ boyutunda kazanç sağlamaz; ölçülür
  ve raporlanır — Test 70).
* Self-play **12 iş parçacığı** ile paralelleştirilir; her iş parçacığı **kendi RNG**'sini
  alır (F4-39) ve **deterministik mod** `--threads 1` ile doğrulanabilir kalır.
* ONNX Runtime CUDA sağlayıcısı **kurulur** (`Microsoft.ML.OnnxRuntime.Gpu` NuGet paketi
  zaten `-p:OnnxRuntimePackage=` ile seçilebilir; Python tarafı için `onnxruntime-gpu`).
  Kurulum başarısız olursa CPU'ya düşer ve bu **raporlanır**.

### 3.2 Track H — EVREN platformu (araştırma sonucu, Bölüm 4)

| Bileşen | Değer |
|---|---|
| Küme | **8 düğüm × 8 NVIDIA H200 = 64 GPU** |
| GPU bellek | H200: **141 GB HBM3e** / GPU |
| Düğüm içi | **NVLink** |
| Düğüm arası | **InfiniBand NDR 400G** |
| İş zamanlayıcı | **Slurm** |
| Konteyner | **Apptainer** (`.sif`) |
| Depolama | Nesne depolama (S3 uyumlu, presigned URL) |
| Ödeme | **CR kredi**, GPU-saat; HOLD → SETTLE → RELEASE |

### 3.3 H200'ü **ne için** kullanacağız (kritik karar)

**Yanlış kullanım:** 36 bin parametreli ağı 8 GPU'ya DDP ile dağıtmak. İletişim maliyeti
hesaplamadan büyüktür; hiçbir kazanç yoktur.

**Doğru kullanım — üç eksen:**

1. **Paralel veri üretimi (asıl kazanç).** Her GPU kendi self-play işçisini çalıştırır;
   C# motoru CPU'da oyun üretir, ONNX Runtime CUDA sağlayıcısı **toplu** değerlendirme
   yapar. 64 GPU × (kova 2048) ile ölçülen 1,24 M poz/sn'nin katları hedeflenir. Bu,
   Track L'de **günler** süren 10⁶ oyunu **saatlere** indirir.
2. **Daha büyük ağ.** H200'ün 141 GB'ı 800 bin–5 milyon parametreli bir ağı rahatça alır.
   Kapasite artışı **ölçülür** (Test 68); kazanç yoksa **küçük ağda kalınır** ve bu
   raporlanır.
3. **Daha derin arama.** Depth 3 aramada her kök kararı ~21 × 20 × 21 ≈ 8 800 yaprak
   üretir; 64 GPU bunu gerçek zamanlı kılar. **Ürün** yine depth 2 kullanır; depth 3
   yalnızca **veri etiketleme** (search distillation) ve **ölçüm** içindir.

**Yapılmayacak:** çoklu-GPU DDP ile eğitim (ağ çok küçük), model paralelliği, tensor
paralelliği, FSDP. Bunlar bu ölçekte **zarar**dır.

### 3.4 Ortak kod tabanı kuralı

Track L ve Track H **aynı** `ml/` kodunu, **aynı** `config.yaml` şemasını, **aynı** shard
biçimini kullanır. Fark yalnızca:

| Alan | Track L | Track H |
|---|---|---|
| `run.device` | `cuda` (veya `cpu`) | `cuda` |
| `selfplay.threads` | 12 | 8 (düğüm başına) |
| `selfplay.cuda` | `true` | `true` |
| `selfplay.max_batch` | 2048 | 8192 |
| `model.h1/h2/h3` | 256/256/128 | 512/512/512/256 |
| `train.value_batch` | 4096 | 32768 |
| `train.steps_per_iteration` | 200 | 2000 |
| `selfplay.games` | 2 000 | 50 000 |
| `run.iterations` | 50 | 200 |

**Hiçbir kod yolu `if (evren)` içermez.** Fark yalnızca konfigürasyondadır.

---

## 4. EVREN Platformu — Erişim ve Kullanım (araştırma sonucu)

> **Kaynak:** `https://evren.ssyz.org.tr` (ana sayfa, `/infrastructure`, `/pricing`,
> `/explore`, `/llm-inference`), `robots.txt`, `sitemap.xml` ve sitenin istemci paketi
> (`/assets/index-*.js`) içindeki SSS metinleri ve yol haritası. **Bu bölüm bir
> araştırma özetidir; resmî doküman değildir.** Kesin prosedür için `ssyz@ssb.gov.tr`
> ile teyit gerekir (Açık Soru 1).

### 4.1 Platform nedir

EVREN, **T.C. Cumhurbaşkanlığı Savunma Sanayii Başkanlığı (SSB)** bünyesinde geliştirilen
uçtan uca yerli yapay zekâ platformudur. Kapsam: veri etiketleme, ön etiketleme (SAM 3,
YOLO), **64× NVIDIA H200 üzerinde dağıtık model eğitimi**, çıkarım ve model paylaşımı.

### 4.2 Erişim (ilk adım — bloklayıcı)

* Kimlik doğrulama **`kimlik.ssb.gov.tr`** üzerinden SSO ile yapılır. Yani **kurumsal bir
  hesap gerekir**; halka açık self-servis kayıt **yoktur**.
* Sitede **"EVREN Kaşifi"** başvuru sayfası vardır (`/kasif`).
* İletişim: **`ssyz@ssb.gov.tr`**, +90-312-411-9000.
* **Sonuç:** Track H **varsayılan olarak kullanılamaz**. Bu yüzden Faz 6 **Track L ile
  tamamlanabilir** olmak zorundadır; Track H bir **hızlandırıcıdır**, ön koşul değildir.

### 4.3 İş akışı (sitenin kendi anlatımı)

1. **Veri yükleme:** presigned URL ile nesne depolamaya (`s3.ssyz.org.tr`).
2. **Eğitim işi:** `/training` altında iş oluşturulur; iş **Slurm** üzerinden
   **Apptainer** konteynerinde bare-metal kümede çalışır.
3. **İzleme:** eğitim metrikleri canlı akar (`/training/:jobId`).
4. **Kayıt:** model `/models` altında sürümlenir; `/experiments` deney kaydı tutar.
5. **Dışa aktarım:** `/admin/e/export_formats` ile tanımlı biçimlerde indirilir.
6. **Kredi:** HOLD → SETTLE → RELEASE. İş başlamadan bakiye kontrol edilir; yetersizse
   iş **başlatılmaz**.

### 4.4 Bizim işimize yarayan üç erişim yolu (bu sırayla dene)

| # | Yol | Ne zaman | Nasıl |
|---|---|---|---|
| 1 | **GPU Rezervasyon** (`/gpu-reservations`) | En esnek; kendi kodumuzu koşarız | Düğüm/GPU rezerve et, `apptainer exec --nv` ile kendi imajımızı çalıştır |
| 2 | **Notebook** (`/workspace`, **BETA**, yönetici kısıtlı) | Etkileşimli deneme | Jupyter benzeri; GPU tahsisi oturum bazlı |
| 3 | **Eğitim işi** (`/training`) | Üretim koşusu | Ön ayar (`training_presets`) + mimari (`architectures`) seçilir; **bizim özel PyTorch döngümüz hazır ön ayarlara uymaz**, bu yüzden özel imaj gerekir |

**Kritik:** Bizim eğitim döngümüz **standart bir ön ayar değildir** (YOLO/LLM değil).
Bu yüzden **kendi Apptainer imajımızı** getirmemiz gerekir. İmaj içinde:
`python 3.10`, `torch` (CUDA 12.x), `onnx`, `onnxruntime-gpu`, `numpy`, **ve .NET 8/10
runtime** (self-play üreticisi için).

### 4.5 Veri taşıma kararı: **veriyi değil, üreticiyi taşı**

10⁶ oyun ≈ **310 GB** ham / **180 GB** gzip (Bölüm 7.4). Bunu internete yüklemek
pratiksizdir. Bu yüzden:

* **C# self-play üreticisi `linux-x64` için self-contained yayınlanır:**
  `dotnet publish Backgammon.SelfPlay -c Release -r linux-x64 --self-contained true
  -p:PublishSingleFile=true`. Tek dosya, .NET kurulumu gerektirmez.
* Bu ikili **Apptainer imajına** kopyalanır; **veri kümede üretilir**.
* Kümeden dışarı yalnızca **model ağırlıkları** (≈150 KB–5 MB) ve **metrikler** çıkar.
* Yerelde üretilmiş shard'lar gerekiyorsa **nesne depolamaya** yüklenir (presigned URL).

### 4.6 Slurm iş şablonu (başlangıç noktası — kümenin gerçek yapılandırmasına göre uyarla)

```bash
#!/bin/bash
#SBATCH --job-name=tavla-selfplay
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:h200:1
#SBATCH --time=12:00:00
#SBATCH --output=tavla-%j.out

set -euo pipefail
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export DOTNET_gcServer=1

apptainer exec --nv \
  --bind "$PWD/data:/data" \
  --bind "$PWD/out:/out" \
  tavla.sif \
  /opt/tavla/Backgammon.SelfPlay \
    --model /out/model.onnx \
    --games 50000 \
    --threads 32 \
    --depth 1 \
    --max-root 4 --max-inner 4 \
    --log-top 12 \
    --cuda true \
    --max-batch 8192 \
    --out /out/shards \
    --prefix sp
```

**Uyarılar (doğrulanmamış, sahada teyit edilecek):**
`--gres=gpu:h200:N` biçimi, bölüm (`partition`) adı, `--cpus-per-task` üst sınırı,
Apptainer `--nv` desteği ve `$PWD` bağlama izinleri **kümeye özeldir**. İlk iş
**`sinfo`, `scontrol show partition`, `apptainer --version`, `nvidia-smi`** çıktılarıyla
keşif yapılmalı ve **raporlanmalıdır** (Test 66).

### 4.7 Kredi maliyeti tahmini (formül; sayı **ölçülecek**)

Platformun kendi SSS'i: *"Maliyet, seçilen model mimarisinin saatlik kredi katsayısı ile
tahmini eğitim süresinin çarpımıdır."* Katsayılar (`training_cost_factors`) **yönetici
tarafından** tanımlanır ve bize görünmez. Bu yüzden Faz 6:

* Her koşu öncesi **tahmini GPU-saat** hesaplar: `saat = (oyun × karar/oyun × aday × 21)
  / (poz/sn × 3600)`.
* Koşuyu **küçük bir pilot** (ör. 1 GPU × 1 saat) ile başlatır, **gerçek** GPU-saat/oyun
  oranını ölçer, sonra ölçeği büyütür.
* **Bakiye yetersizse iş başlatılmaz** — bu bir hata değil, beklenen davranıştır; Track L'e
  düşülür ve raporlanır.

### 4.8 Track H kabul kapısı

Track H'ye geçiş **şu üç koşulun hepsi** sağlanınca yapılır:

1. Erişim alındı (SSO hesabı çalışıyor).
2. `tavla.sif` imajı kümede **başarıyla** çalıştı (Test 65: `nvidia-smi` + `dotnet --info`
   + 100 oyunluk duman koşusu).
3. Pilot koşunun **ölçülen** GPU-saat/oyun oranı, Track L'in **en az 20 katı** hızında.

Aksi halde Track H **kullanılmaz** ve bu **gerekçesiyle raporlanır**.
---

## 5. Model Mimarisi v2 — 6 Çıktılı Değer Kafası

### 5.1 Neden 6 çıktı

Faz 5'in ölçümü kesin: tek skaler değer kafası **≈11,4 kat aşırı dağınık** (eğim 0,0874).
Kök neden, tek skalerin **üç ayrı olayı** (kazanma, mars, arka arkaya mars) tek bir sayıya
sıkıştırmasıdır. gnubg ve TD-Gammon bunu **altı olasılıkla** çözer:

```
W  = P(kazanır, tek)          L  = P(kaybeder, tek)
GW = P(kazanır, mars)         GL = P(kaybeder, mars)
BW = P(kazanır, arka arkaya)  BL = P(kaybeder, arka arkaya)

W + GW + BW + L + GL + BL = 1
W ≥ GW ≥ BW ≥ 0        L ≥ GL ≥ BL ≥ 0
E = W − L + GW − GL + BW − BL        ∈ [−3, +3]
```

Bu formülasyon **kendiliğinden sınırlıdır** ve **antisimetriktir** (oyuncu değişince
`W↔L, GW↔GL, BW↔BL` ve `E → −E`). Faz 3 v7 negamax'ı **değişmez**.

### 5.2 Ağ topolojisi

```
girdi  : features      [B, 221]  float32   (feature_version = 1, DEĞİŞMEZ)
gövde  : Linear(221, h1) → GELU → Linear(h1, h2) → GELU [→ Linear(h2, h3) → GELU]
çıktı  : probs         [B, 6]    float32   (softmax, sıra: W, GW, BW, L, GL, BL)
         policy_logit  [B, 1]    float32   (softmax YOK — Faz 4 sözleşmesi)
```

| Profil | `h1` | `h2` | `h3` | Parametre (yaklaşık) | Kullanım |
|---|---|---|---|---|---|
| `small` | 128 | 64 | — | 36 bin | Faz 5 tabanı (kıyas) |
| `medium` | 256 | 256 | 128 | **≈ 140 bin** | **Track L varsayılanı** |
| `large` | 512 | 512 | 512 | ≈ 660 bin | Track H |
| `xlarge` | 1024 | 1024 | 512 | ≈ 2,1 M | Track H (yalnızca ölçüm kazancı varsa) |

**Kapasite kuralı:** bir üst profil yalnızca **ölçülen** kazanç varsa kullanılır
(Test 68: aynı veri, aynı iterasyon, `medium` vs `large` → ER farkı ≥ 0,002). Kazanç
yoksa **küçük profilde kalınır** ve bu raporlanır.

### 5.3 Kayıp fonksiyonu

```
L = c_value · L_value + c_policy · L_policy + c_cal · L_cal

L_value  = KL(hedef_dağılım ‖ tahmin)          # 6 sınıflı çapraz entropi
L_policy = grup-softmax çapraz entropisi        # Faz 4 ile aynı
L_cal    = (E_tahmin − E_hedef)²                # equity kalibrasyon terimi
```

* `L_value` **hedef dağılımı** gerektirir. Hedef, oyun sonucundan **birebir** gelir:
  oyun bittiğinde `(winner, resultType)` → **one-hot 6 vektör**. Bu, TD(λ) ile
  yumuşatılır (Bölüm 8.3).
* `L_cal` **düşük ağırlıkla** (`c_cal = 0,1`) eklenir; amacı eğimi 1'e çekmek, değilse
  dağılımı bozmak. **`c_cal = 0` ile karşılaştırma yapılır ve raporlanır** (Test 55).
* `policy_min_sharpness` (Faz 4, F4-40) **korunur**.

### 5.4 ONNX sözleşmesi — `output_version = 2`

| Alan | v1 (Faz 4/5) | **v2 (Faz 6)** |
|---|---|---|
| Girdi | `features` `[B,221]` | `features` `[B,221]` (**aynı**) |
| Çıktı 1 | `value` `[B,1]` | **`probs` `[B,6]`** |
| Çıktı 2 | `policy_logit` `[B,1]` | `policy_logit` `[B,1]` (**aynı**) |
| Metadata | `feature_version`, `vector_size`, `model_version`, `arch`, `trained_by`, `output_version` | aynı + **`prob_order = "W,GW,BW,L,GL,BL"`** |
| Opset | 15 | 15 (yükseltme gerekirse gerekçeli rapor) |

**`OnnxModelHandle` davranışı (değişir):** bugün `SupportedOutputVersion = 1` sabitidir
(`Backgammon.Inference/OnnxModelHandle.cs` L40) ve `output_version > 1` →
`NotSupportedException` atar. Faz 6 bu sabiti **2** yapar. `output_version == 1` →
bugünkü yol **aynen** çalışır (geriye dönük uyumluluk **zorunlu**). `output_version == 2`
→ `probs` okunur, `E` C#'ta türetilir. `output_version > 2` → `NotSupportedException`
(Faz 5 davranışı korunur).

**`OnnxPolicyValueEvaluator` (değişir):** `output_version == 2` iken `probs`'u
`OutcomeDistribution`'a yazar; `E`'yi mevcut `OutcomeDistribution.Equity` **özelliğinden**
(`double`) okur. **Sıfır allocation kuralı korunur** (Test 57).

### 5.5 `OutcomeDistribution` genişletmesi

Faz 5'te `OutcomeDistribution` **zaten var** (`Backgammon.Core/Match/OutcomeDistribution.cs`)
ve **5 alan** saklar: `Win`, `WinGammon`, `WinBackgammon`, `LoseGammon`, `LoseBackgammon`.
`Lose` **türetilir** (`1 − Win`); `Equity` **özelliği** (`double`) ve `IsValid` **özelliği**
zaten vardır. Yani 6 sonuç, 5 alanla temsil edilir — **bu tasarım korunur**.

Faz 6 **tek** ekleme yapar:

```csharp
// Ağ çıktısından (6 float, gnubg sırası: W, GW, BW, L, GL, BL) kurulum.
// Toplamı 1'e normalize eder, monotonluğu zorlar, IsValid ile doğrular.
public static OutcomeDistribution FromProbabilities(
    float w, float gw, float bw, float l, float gl, float bl);
```

`FromProbabilities` **normalize eder** (toplam 1 değilse) ve **monotonluğu zorlar**
(`W ≥ GW ≥ BW`, `L ≥ GL ≥ BL`); ihlal varsa **düzeltir** ve `DebugAssert` ile uyarır.
Bu, ağın sayısal taşmasına karşı **savunma**dır (Test 52). `Equity` **yeniden
yazılmaz** — tek doğruluk kaynağı mevcut özelliktir.

### 5.6 `HeuristicOutcomeDistributionEvaluator` (Faz 5) ne olur

**Korunur.** `Backgammon.Core/Match/HeuristicOutcomeDistributionEvaluator.cs` zaten
`IOutcomeDistributionEvaluator`'ı uygular ve sınıf yorumunda *"Faz 6'da bu sınıfın yerini
ağın 6 çıktılı değer başı alacak; arayüz değişmeyecek"* yazar. Faz 6 bunu **harfiyen**
uygular: arayüz **değişmez**, ağ varsa `OnnxOutcomeDistributionEvaluator` (yeni) kullanılır,
yoksa sezgisel sarmalayıcı devrededir. Sezgisel sarmalayıcı **kalibre edilmez**.

---

## 6. Kalibrasyon

### 6.1 Sorun

Faz 5 ölçümü: `gnubg ≈ 0,0874 · bizim + 0,1589`. Yani model `[-3,3]`'ün neredeyse
tamamını kullanıyor, gnubg `[-0,82, +1,65]`'te kalıyor. Kalibrasyon sonrası MAE
0,8014 → 0,2897.

### 6.2 Çözüm sırası (ucuzdan pahalıya)

| # | Yöntem | Ne zaman | Ölçüm |
|---|---|---|---|
| 1 | **6 çıktılı kafa** (Bölüm 5) | Her zaman | Eğim doğal olarak 1'e yaklaşır |
| 2 | **`L_cal` terimi** (`c_cal = 0,1`) | 1 yetmezse | Test 55 |
| 3 | **Sıcaklık ölçekleme** (`E' = a·E + b`, `a,b` **sadece** doğrulama kümesinden) | 1+2 yetmezse | Test 56 |
| 4 | **İzotonik regresyon** (6 olasılığa ayrı ayrı) | Son çare | Test 56 |

**Kural:** 3 ve 4 **yalnızca çıkarımda** uygulanır ve **ONNX içine gömülür** (ayrı bir
`Calibration` düğümü olarak), böylece C# tarafı hiçbir şey bilmez. Kalibrasyon
parametreleri **eğitim kümesinden değil, ayrı doğrulama kümesinden** hesaplanır
(sızıntı yasak).

### 6.3 Kabul

| Ölçüm | Eşik |
|---|---|
| Kalibrasyon eğimi `a` | **0,85 ≤ a ≤ 1,15** |
| Korelasyon (400 afterstate, gnubg 2-ply) | **≥ 0,75** (Faz 5: 0,2431) |
| MAE | **≤ 0,15** (Faz 5: 0,8014) |
| Değer std oranı (bizim/gnubg) | **0,7 ≤ oran ≤ 1,4** (Faz 5: 2,78) |

---

## 7. Veri Motoru

### 7.1 Shard biçimi v2

`SHARD_FORMAT.md` **v2** olarak güncellenir. **v1 okunmaya devam eder** (eski koşular
yeniden üretilebilir kalır).

**Değişen alanlar:**

| # | Alan | v1 | **v2** |
|---|---|---|---|
| 8 | `formatVersion` | 1 | **2** |
| 20 | `logTopCandidates` | `u32` | `u32` (aynı) |
| 24 | `flags` | `u32` | `u32` — **bit0: `hasOutcomeProbs`** |
| — | Karar kaydı: `chosenVector` | `f32[221]` | `f32[221]` (aynı) |
| — | Karar kaydı: **yeni** `outcomeProbs` | — | **`f32[6]`** (yalnızca `hasOutcomeProbs = 1` ise) |
| — | Oyun kaydı: `resultType` | `u8` | `u8` (aynı) |
| — | Oyun kaydı: **yeni** `finalProbs` | — | **`f32[6]`** (oyun sonu one-hot, TD hedefi) |

**Neden:** 6 çıktılı kafa, her karar için **6 boyutlu hedef** ister. Oyun sonu one-hot
`finalProbs` **tek başına yeterlidir** (TD zinciri onu geriye yayar); `outcomeProbs`
**search distillation** için (depth 3 aramasının ürettiği dağılım) opsiyoneldir.

**Boyut etkisi:** karar başına +24 bayt (≈ %0,2). **İhmal edilebilir.**

### 7.2 Paralel self-play

**Bugünkü durum:** `--threads > 1` **deterministik değil** (F4-39: iş parçacığı başına
ayrı RNG). Faz 6 bunu **özellik** yapar:

* Her iş parçacığı `seed = baseSeed + threadIndex` alır.
* **Deterministik mod** `--threads 1` ile **birebir** aynı shard'ı üretir (Test 60).
* `--threads N` çıktısı, `N` ayrı `--threads 1` koşusunun **kümesiyle** aynıdır
  (sıra farklı olabilir; **içerik** aynı). Test 60 bunu doğrular.

**Ölçülecek:** oyun/sn (thread 1, 6, 12), bellek tepe noktası, disk yazma hızı.

### 7.3 GPU toplu çıkarım

`--cuda true --max-batch 2048` zaten var. Faz 6 ekler:

* **Kova birleştirme:** birden çok iş parçacığının adayları **tek** ONNX çağrısında
  toplanır (`max_batch` sınırına kadar). Bu, GPU kullanımını %10'lardan %80'lere çıkarır.
* **Ölçüm:** poz/sn (thread 1/6/12 × batch 128/512/2048/8192). Test 61.

### 7.4 Veri hacmi matematiği (kesin)

`SHARD_FORMAT.md` §4: `logTopCandidates = 12` ile karar başına ≈ **11 500 bayt**.
Bir oyun ≈ 55 ply ≈ **27 karar/oyuncu** → ≈ **310 KB/oyun** ham.

| Oyun | Ham | gzip (≈1,7×) | Track L süresi | Track H süresi |
|---|---|---|---|---|
| 10⁴ | 3,1 GB | 1,8 GB | saatler | dakikalar |
| 10⁵ | 31 GB | 18 GB | **günler** | saatler |
| 10⁶ | 310 GB | 180 GB | **pratik değil** | **saatler** |

**Track L hedefi: 10⁵ oyun** (F: sürücüsünde 427 GB boş — yeterli).
**Track H hedefi: 10⁶ oyun** (kümede üretilir, dışarı yalnızca model çıkar).

### 7.5 Veri kalitesi

* **Tekrar ayıklama:** aynı Zobrist hash'e sahip kararlar **tutulmaz** (Faz 1 hash'i
  hazır). Ölçülecek: tekrar oranı.
* **Açılış çeşitliliği:** ilk 10 ply'de `selection_temperature = 0,05` (Faz 4) **korunur**;
  sıfırlanırsa veri tek bir açılışa çöker. Test 62 bunu doğrular (açılış dağılımı
  entropisi ≥ eşik).
* **Berabere/iptal oyunlar** (`aborted`) eğitime **girmez** (Faz 4 kuralı korunur).
* **`max_plies` taşması** (F4-45: 200 oyunun 28'i) **azaltılır**: `max_plies = 500`
  korunur ama `PipBot` gibi vurma eğilimli rakiplere karşı oyunlar **ayrı** sayılır.

---

## 8. Eğitim Hattı

### 8.1 Döngü

```
for iter in 1..N:
    1. self-play  → shard'lar (mevcut modelle, depth 1, keşif 10 ply)
    2. replay buffer'a ekle (FIFO, max_games)
    3. hedefleri kur (TD(λ) veya search distillation)
    4. S adım eğit (value + policy + cal)
    5. her eval_every: doğrulama kaybı, kalibrasyon eğimi, ER (küçük küme)
    6. her league.every: lig giriş kontrolü (Faz 4)
    7. checkpoint + metrics.jsonl
```

### 8.2 Faz 4'ten devralınan düzeltmeler (zorunlu)

| # | Sorun | Faz 6 kuralı |
|---|---|---|
| F4-41 | `λ = 0,7` + `γ = 1` uyumsuz; hedefler sıfıra çöküyor | **`λ = 1,0` (Monte Carlo) varsayılan**; `γ = 1` |
| F4-39 | `--threads > 1` deterministik değil | Bölüm 7.2 |
| F4-45 | `max_plies` taşması | Bölüm 7.5 |
| F4-40 | Düzgün hedef politika gradyanını bozuyor | `policy_min_sharpness = 0,99` **korunur** |
| F4-35 | GPU paketi derleme zamanında seçiliyor | `-p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu` |

### 8.3 Hedef kurma

| Mod | Ne zaman | Formül |
|---|---|---|
| `td_lambda` | **Varsayılan** | `G_t = (1−λ)·Σ λ^{k} r_{t+k} + λ^{T−t} z_T`, `λ = 1,0` → saf MC |
| `search_distill` | Track H, depth 3 | Hedef = depth-3 aramanın kök dağılımı (6 boyut) |

**`search_distill` neden Track H'ye özel:** depth 3 arama, karar başına ~8 800 yaprak
değerlendirir. Track L'de 10⁵ oyun × 27 karar × 8 800 = **2,4 × 10¹⁰** değerlendirme
eder; GTX 1650'de bu **aylar** sürer. Track H'de saatler.

### 8.4 Track L koşu planı (somut)

| Aşama | Oyun | İterasyon | Profil | Tahmini süre | Hedef |
|---|---|---|---|---|---|
| L0 | 500 | 20 | `small` | ~1 saat | Faz 5 tabanını **yeniden üret** (ER ≈ 0,19) |
| L1 | 10⁴ | 30 | `medium` | ~1 gün | ER < 0,10 |
| L2 | 5 × 10⁴ | 50 | `medium` | ~3 gün | ER < 0,05 |
| L3 | 10⁵ | 50 | `medium` | ~5 gün | **ER < 0,02** |

**L0 zorunludur** — Faz 5 sonucunu **birebir** yeniden üretemiyorsak ölçüm hattı
bozuktur ve L1+ anlamsızdır (Test 67).

### 8.5 Track H koşu planı (somut)

| Aşama | Oyun | İterasyon | Profil | GPU | Hedef |
|---|---|---|---|---|---|
| H0 | 10⁴ | 20 | `medium` | 1 | Track L L1 ile **aynı** sonucu ver (parite) |
| H1 | 10⁵ | 50 | `large` | 8 | ER < 0,03 |
| H2 | 10⁶ | 200 | `large` | 8–16 | **ER < 0,02** |
| H3 | 10⁶ | 200 | `xlarge` + depth-3 distill | 32–64 | **ER < 0,01** |

**H0 parite kapısı:** aynı seed, aynı veri, aynı iterasyon → Track L ile **aynı** kayıp
eğrisi (±%2). Fark varsa **önce** bu düzeltilir (Test 69).

### 8.6 Checkpoint ve sürümleme

* Her iterasyon: `ckpt_v{N}.pt` + `model_v{N}.onnx` + `metrics.jsonl` satırı.
* `model_version` monoton artar; **asla** geri yazılmaz.
* Lig havuzu (`ml/runs/pool`) Faz 4 mantığıyla korunur.
* **En iyi model** ölçütü: doğrulama `L_value` **değil**, **ER** (küçük referans küme,
  her 10 iterasyonda). Kayıp iyileşirken ER kötüleşebilir; ürün ER'yi seçer.
---

## 9. Arama Gücü

### 9.1 Bugünkü durum

`SearchSettings.Default`: `DepthPly = 1`, `MaxCandidatesRoot = 0`, `MaxCandidatesInner = 0`,
`UseAlphaBeta = true`, `UseStar1 = true`, `UseEvalCache = true`, `UsePolicyOrdering = true`,
`ExactRootScores = false`, `PolicyTemperature = 1,0`.

Depth 2 **pratik değil** (F4: kısıtsız > 600 s/oyun; kısıtlı bile 50 s/oyun). Faz 6 bunu
**çözmek zorundadır**, çünkü ER hedefi depth 2 olmadan ulaşılamaz.

### 9.2 `SearchSettings`'e iki yeni alan (onaylanmış ekleme)

```csharp
/// <summary>Faz 6: transposition table kapasitesi (girdi sayısı). 0 = kapalı.</summary>
public int TranspositionCapacity;

/// <summary>Faz 6: bearoff bölgesinde aramayı kes (kesin DB varsa).</summary>
public bool UseBearoffCutoff;
```

**Varsayılanlar:** `TranspositionCapacity = 0` (kapalı — Faz 5 davranışı **birebir**
korunur), `UseBearoffCutoff = false`. **Mevcut testler değişmez.**

### 9.3 Transposition table

* Anahtar: **Zobrist hash** (Faz 1'de hazır) + `DepthPly` + `remainingDice` maskesi.
* Değer: `float` skor + `byte` derinlik + `byte` bayrak (EXACT/LOWER/UPPER).
* Kapasite: **2²⁰ = 1 048 576** girdi (≈ 16 MB). Doğrudan eşleme (direct-mapped),
  çakışmada **üzerine yaz** (en basit, en hızlı).
* **Sıfır allocation:** dizi `SearchWorkspace` içinde **bir kez** ayrılır.
* **Determinizm:** TT, aynı seed + aynı sıra ile **birebir** aynı sonucu vermelidir
  (Test 76). Paralel arama **yok**; TT tek iş parçacığında.

### 9.4 Bearoff kesme

`IsBearOffMode` (Faz 1) zaten var. Faz 6:

* `UseBearoffCutoff = true` **ve** `BearoffDatabase` yüklü **ve** pozisyon saf bearoff ise
  → arama **derinliği 0'a indirilir** ve `BearoffAwareEvaluator` **kesin** equity verir.
* Bu, Faz 5 §3.8'in **arama düzeyinde** uygulanmasıdır (Faz 5'te yalnızca değerlendirici
  düzeyindeydi).
* **Kazanç ölçülür:** bearoff pozisyonlarında düğüm sayısı ve süre (Test 77).

### 9.5 Depth 2 performansı

**Hedef:** depth 2, `MaxCandidatesRoot = 4`, `MaxCandidatesInner = 4`, TT açık →
**≤ 2 s/karar** (Track L, CPU). Bugün 50 s/oyun; hedef **≤ 5 s/oyun**.

**Yöntemler (sırayla, her biri ölçülür):**

1. **TT** (Bölüm 9.3) — en büyük kazanç, en düşük risk.
2. **Aday kısıtlaması** — `MaxCandidatesRoot/Inner = 4` (Faz 3'te var, kullanılmıyor).
3. **Star1** — zaten açık.
4. **Politika sıralaması** — zaten açık.
5. **Erken kesme** — `|E| > 0,9` ise (neredeyse kesin) alt düğümlerde derinleşme.
   **Yeni**, `SearchSettings`'e alan **eklemez**; sabit eşik olarak `BackgammonSearch`
   içinde **kapalı** gelir, `TranspositionCapacity > 0` iken açılır.

**Kural:** her optimizasyon **`Reference(depth)`** ile **birebir** aynı sonucu vermelidir
(Test 78). Fark varsa **hata**dır, optimizasyon değil.

### 9.6 Depth 3 (yalnızca Track H, yalnızca veri etiketleme)

* Ürün **depth 2** kullanır. Depth 3 **yalnızca** `search_distill` hedefi üretir.
* `MaxCandidatesRoot = 4`, `MaxCandidatesInner = 2` ile sınırlanır.
* Ölçüm: depth 3 distill ile eğitilen model, depth 1 self-play ile eğitilen modelden
  **ne kadar** güçlü? (Test 79). Kazanç yoksa **kullanılmaz**.

---

## 10. Küp ve Maç Ustalığı

### 10.1 Bugünkü durum

`EquityCubeAdvisor` (Faz 5) gnubg 0-ply ile ikileme %51,52 / alma %61,36 uyuşuyor.
`HeuristicOutcomeDistributionEvaluator` **kalibre edilmemiş**tir (sezgisel; ağ yokken devrede).

### 10.2 Zar-ortalamalı küp değerlendirmesi

Faz 5 §9.2'de **ölçülmüş** bir bulgu var (`ml/artifacts/stage_b_cube.md`, 132 pozisyon):

| Metrik (gnubg 0-ply) | Tek kayıt | Zar-ortalamalı |
|---|---|---|
| Equity korelasyonu (Pearson) | **−0,0315** | **+0,1395** |
| Equity ortalama \|Δ\| | 1,0550 | 1,2063 |

Yani zar-ortalamalı değerlendirme **korelasyonu işaret değiştirecek kadar** düzeltiyor
(−0,03 → +0,14) ama **ortalama mutlak hatayı iyileştirmiyor** (1,0550 → 1,2063). Bu, hatanın
**sistematik bir sapma** (bias) olduğunu, gürültü olmadığını gösterir — Bölüm 6'daki
kalibrasyonun nedeni tam olarak budur. Faz 6 bu yüzden zar-ortalamayı **varsayılan** yapar,
ama **tek başına yeterli saymaz**:

* `EquityCubeAdvisor` pozisyonu **21 zar çifti** üzerinden ortalama alarak değerlendirir
  (küp kararı **sıra başında** verilir, zar atılmamıştır).
* Maliyet: 21× değerlendirme. **Yalnızca sıra başında** (oyun başına ~27 kez), bu yüzden
  kabul edilebilir. Ölçülür (Test 84).
* `CubeAdvisorOptions.DiceAveraged` (yeni alan, varsayılan **true**); `false` → Faz 5 davranışı.
* **Kabul kapısı:** zar-ortalamalı ortalama \|Δ\| **1,2063'ün altına** inmelidir; inmiyorsa
  kalibrasyon (Bölüm 6) tamamlanmadan küp ağına (10.4) geçilmez.

### 10.3 6 çıktılı kafadan küp kararı

`E = W − L + GW − GL + BW − BL` **tek başına yetmez**; küp kararı **MWC** ister. Faz 5'te bu
**zaten var**: `MatchAwareEvaluator.MatchWinningChance` (`Backgammon.Core/Match/MatchAwareEvaluator.cs`
L145–164) 6 olasılığı **tek tek** MET'e çevirir:

```
mwc  = winSingle      · MET.MatchWinningChance(awayMover-1, awayOpponent)
     + winGammon      · MET.MatchWinningChance(awayMover-2, awayOpponent)
     + winBackgammon  · MET.MatchWinningChance(awayMover-3, awayOpponent)
     + loseSingle     · MET.MatchWinningChance(awayMover,   awayOpponent-1)
     + loseGammon     · MET.MatchWinningChance(awayMover,   awayOpponent-2)
     + loseBackgammon · MET.MatchWinningChance(awayMover,   awayOpponent-3)
```

`MatchEquityTable`'ın genel API'si `MatchWinningChance(awayA, awayB)` ve
`MatchEquity(awayA, awayB)`'dir (L113, L134); `MaxMatchLength` varsayılan **25** (L26).
Faz 6 bu hesabı **değiştirmez**, yalnızca besleyen 6 olasılığın **kalitesini** artırır. İki
iyileştirme yapılır:

1. **Gammon ayrımı korunur.** `E`'yi tek sayıya indirgemek mars bilgisini **kaybeder**.
   Küp kararı **6 olasılığın tamamını** kullanır (`OutcomeDistribution` → MWC).
2. **Crawford/post-Crawford** doğru ele alınır (Faz 5'te hazır, Test 85 ile doğrulanır).

### 10.4 Küp ağı (opsiyonel, ölçüm kapılı)

gnubg'nin ayrı bir küp ağı vardır. Faz 6 **dener**, kazanç yoksa **kullanmaz**:

* Girdi: 221 vektör + `cubeValue` + `cubeOwner` + skor farkı (zaten vektörde).
* Çıktı: `[B, 4]` = `(double/take, too-good, beaver?)` — **basitleştirilmiş**.
* Eğitim verisi: self-play'de **küp kararları** loglanır (shard v2'ye **eklenmez**;
  ayrı bir `cube_*.bgsp` biçimi — Bölüm 14'te kapsam dışı bırakıldı, **yalnızca** ölçüm
  için).

**Karar:** küp ağı **yalnızca** `EquityCubeAdvisor`'ın uyumu **%75'in altında** kalırsa
devreye girer. Aksi halde **gereksiz karmaşıklıktır** ve eklenmez.

### 10.5 Kabul

| Ölçüm | Eşik |
|---|---|
| Küp uyumu (gnubg 2-ply, 132 pozisyon) | **≥ %75** (Faz 5: %52,27) |
| Crawford senaryoları | 100 % doğru (Test 85) |
| Maç farkındalığı (400 oyun, 2-away) | **≥ %45** (Faz 5: %40,00) |
| `x128` küp kilidi | **regresyon yok** (Faz 5 §43.13) |

---

## 11. Ürün Mükemmelliği (Unity)

> **Kural:** bu bölümdeki her madde **ölçülebilir** bir kabul kriterine bağlanır.
> "Güzel görünüyor" kabul kriteri değildir.

### 11.1 Zorunlu (must)

| # | Özellik | Kabul kriteri |
|---|---|---|
| P1 | **Açılış kitabı** | İlk 2 zar (≤ 3 ply) için en iyi hamle **anında** (≤ 50 ms) gelir; kitap self-play'den üretilir, `ml/artifacts/opening_book.json` |
| P2 | **Hamle sıralaması + equity kaybı** | Analiz paneli ilk 5 hamleyi `E` ve **kayıp** ile listeler; kayıp = `E_best − E_hamle` |
| P3 | **6 olasılıklı analiz paneli** | `W/GW/BW/L/GL/BL` + `E` + `MWC` + pip sayıları + Keith count |
| P4 | **Geri al / yinele** | Hamle, tur ve oyun düzeyinde; 50 adım geriye |
| P5 | **Maç kaydet / yükle** | JSON biçimi, sürüm alanı, ileri uyumlu |
| P6 | **Renk körü güvenli palet** | Deuteranopia/protanopia simülasyonunda pul kontrastı **≥ 3:1** (WCAG AA) |
| P7 | **Klaveye girişi** | `1..9,0` hane seç, `Enter` onayla, `Esc` iptal, `U` geri al |
| P8 | **TR/EN yerelleştirme** | Tüm görünür metinler kaynak dosyadan; sabit metin **yok** |
| P9 | **Kurulum paketi** | Inno Setup; `TavlaAI-Setup-x.y.z.exe`; kaldırma çalışır |
| P10 | **Kare hızı** | 1080p'de **≥ 60 fps**; GC spike **≤ 1 ms** |
| P11 | **AI güç seviyeleri** | 4 seviye: `Başlangıç` (depth 0), `Orta` (depth 1), `İyi` (depth 2), `Uzman` (depth 2 + TT + bearoff) |
| P12 | **Analiz modu** | İnsan–insan oyna, AI her hamleyi değerlendirsin (asenkron, UI kilitlemez) |

### 11.2 Olmalı (should)

| # | Özellik | Kabul kriteri |
|---|---|---|
| P13 | Zar animasyonu | ≤ 400 ms, atlanabilir |
| P14 | Ses efektleri | Zar, hamle, vuruş, toplama; kapatılabilir |
| P15 | Tahta teması | En az 2 tema (klasik, modern); `CenterBand`'e logo alanı |
| P16 | Pip sayacı | Her iki oyuncu için canlı |
| P17 | Maç geçmişi | Son 20 oyunun sonucu ve skoru |
| P18 | Otomatik güncelleme | Sürüm kontrolü + indirme (opsiyonel, kapatılabilir) |

### 11.3 Yapılmayacak (won't)

* Çevrimiçi çok oyunculu, hesap sistemi, bulut senkronizasyonu.
* Mobil/WebGL/IL2CPP derleme (yalnızca Windows x64).
* Sentis arka ucu (Faz 5 kararı korunur).
* 3B tahta (2D URP kalır).

### 11.4 `CenterBand` kullanımı

Faz 5 §43.17'de eklenen orta bant (`CenterGapRatio = 0.06f`) **logo alanı** olarak
kullanılır. Logo **opsiyoneldir**; yoksa bant boş kalır (mevcut görünüm korunur).
`BoardView.CenterBandLogo` (yeni, opsiyonel `Sprite`).
---

## 12. Test ve Doğrulama (Zorunlu, Önce Yazılır)

Numaralandırma Faz 5'in bıraktığı yerden (**Test 40**) devam eder. Her test **önce kırmızı**
yazılır. `[Test]` sayıları `ml/tests/test_docs_consistency.py` `EXPECTED_COUNTS` içine
işlenir.

### 12.1 Aşama A — Ölçüm hattı ve taban kilidi (Test 41–48)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 41 | `ErHarness_ReproducesStageD` | pytest | Faz 5 `stage_d_er.md` değerleri (0,1941) **birebir** yeniden üretilir |
| 42 | `ErHarness_IsDeterministic` | pytest | Aynı seed + aynı model → aynı ER (bit düzeyinde) |
| 43 | `ErHarness_RejectsMissingGnubg` | pytest | gnubg yoksa **sıfır olmayan** çıkış kodu, uydurma değer yok |
| 44 | `ReferenceCorpus_IsFrozen` | pytest | 200 pozisyonluk referans küme hash'i sabit; değişirse test kırılır |
| 45 | `ReferenceCorpus_CoversAllPhases` | pytest | Küme: temas, yarış, bearoff, bar, kapalı tahta — her biri ≥ 20 pozisyon |
| 46 | `StatisticalPower_IsSufficient` | pytest | 200 pozisyonda ER standart hatası **≤ 0,005** (hesaplanır, raporlanır) |
| 47 | `BaselineLock_MatchesPhases` | pytest | `PHASES.md` §7 tablosundaki her sayı ölçümle uyuşur |
| 48 | `GnubgVersion_IsRecorded` | pytest | gnubg sürümü + ply + mod rapora yazılır; sürüm değişirse uyarı |

### 12.2 Aşama B — 6 çıktılı kafa ve kalibrasyon (Test 49–58)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 49 | `OutcomeDistribution_EquityFormula` | C# | Mevcut `Equity` özelliği `W+WG+WBG−L−LG−LBG` verir; 6 birim vektörde `E ∈ {+3,+2,+1,−1,−2,−3}` |
| 50 | `OutcomeDistribution_IsAntisymmetric` | C# | `FromProbabilities` ile oyuncu değişince `E → −E`, olasılıklar `W↔L`, `GW↔GL`, `BW↔BL` |
| 51 | `OutcomeDistribution_FromProbabilities_Normalizes` | C# | Toplam 1 değilse normalize eder; toplam 1 olur |
| 52 | `OutcomeDistribution_FromProbabilities_EnforcesMonotonicity` | C# | `W < GW` gibi ihlalleri düzeltir; `DebugAssert` uyarır |
| 53 | `Onnx_OutputVersion2_IsAccepted` | C# | `output_version = 2` yüklenir, `probs` okunur, `E` türetilir |
| 54 | `Onnx_OutputVersion1_StillWorks` | C# | **Geriye dönük uyumluluk**: v1 model aynen çalışır |
| 55 | `CalibrationLoss_ImprovesSlope` | pytest | `c_cal = 0,1` ile eğim, `c_cal = 0`'a göre 1'e **daha yakın** |
| 56 | `TemperatureScaling_UsesValidationOnly` | pytest | Sıcaklık parametreleri **yalnızca** doğrulama kümesinden; eğitim kümesi sızıntısı yok |
| 57 | `Onnx_OutputVersion2_ZeroAllocation` | C# | `GC.GetAllocatedBytesForCurrentThread` farkı **0** (ısınma sonrası) |
| 58 | `Export_OutputVersion2_Parity` | pytest | PyTorch ↔ ORT-Python `probs` paritesi **≤ 1e-5** |

### 12.3 Aşama C — Veri motoru (Test 59–66)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 59 | `ShardV2_RoundTrip` | C# + pytest | C# yazar → Python okur → C# okur; `finalProbs` bit düzeyinde korunur |
| 60 | `SelfPlay_ThreadsAreDeterministic` | C# | `--threads N` çıktısı, `N` ayrı `--threads 1` koşusunun **kümesiyle** aynı |
| 61 | `SelfPlay_GpuBatching_IsFaster` | C# | `--cuda true --max-batch 2048` ≥ `--cuda false` (ölçülür, raporlanır) |
| 62 | `SelfPlay_OpeningDiversity` | C# | İlk 10 ply'de açılış dağılımı entropisi ≥ eşik (tek açılışa çökme yok) |
| 63 | `ShardV1_IsStillReadable` | pytest | Faz 4/5 shard'ları okunur; `hasOutcomeProbs = 0` → `finalProbs` yok sayılır |
| 64 | `SelfPlay_LinuxPublish_Runs` | CI | `dotnet publish -r linux-x64 --self-contained` çıktısı çalışır (WSL/Docker) |
| 65 | `Evren_Image_Smoke` | manuel | `tavla.sif` içinde `nvidia-smi`, `dotnet --info`, 100 oyunluk koşu **başarılı** |
| 66 | `Evren_Discovery_Reported` | manuel | `sinfo`, `scontrol show partition`, `apptainer --version` çıktıları rapora yazılır |

### 12.4 Aşama D — Ölçekli eğitim (Test 67–74)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 67 | `TrackL_L0_ReproducesStageD` | pytest | 500 oyun / 20 iterasyon → ER ≈ 0,19 (±0,02) |
| 68 | `Capacity_Gain_IsMeasured` | pytest | `medium` vs `large`, aynı veri → ER farkı **ölçülür**; kazanç yoksa `medium` kalır |
| 69 | `TrackH_H0_Parity` | pytest | Aynı seed/veri/iterasyon → Track L ile kayıp eğrisi **±%2** |
| 70 | `Amp_IsMeasured` | pytest | FP32 vs FP16-AMP: süre ve kayıp farkı **ölçülür**; kazanç yoksa FP32 |
| 71 | `Training_IsReproducible` | pytest | Aynı seed → aynı `metrics.jsonl` (bit düzeyinde) |
| 72 | `Checkpoint_Resume_IsExact` | pytest | `--resume` ile devam, kesintisiz koşuyla **aynı** sonucu verir |
| 73 | `BestModel_SelectedByEr` | pytest | En iyi model **ER** ile seçilir, doğrulama kaybı ile değil |
| 74 | `ErTarget_IsMet` | pytest | **ER < 0,02** (2-ply, 200 pozisyon) — Aşama D kabul kapısı |

### 12.5 Aşama E — Arama gücü (Test 75–82)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 75 | `Transposition_IsDisabledByDefault` | C# | `TranspositionCapacity = 0` → Faz 5 davranışı **birebir** |
| 76 | `Transposition_IsDeterministic` | C# | TT açık, aynı seed → aynı sonuç |
| 77 | `BearoffCutoff_ReducesNodes` | C# | Saf bearoff'ta düğüm sayısı **belirgin** düşer; sonuç **aynı** |
| 78 | `Optimizations_MatchReference` | C# | TT + aday kısıtı + erken kesme, `Reference(depth)` ile **birebir** aynı skorlar |
| 79 | `Depth3Distill_Gain_IsMeasured` | pytest | depth-3 distill ile eğitilen model, depth-1 self-play'ten **ne kadar** güçlü |
| 80 | `Depth2_IsFastEnough` | C# | depth 2, `MaxCandidates 4/4`, TT açık → **≤ 5 s/oyun** (Track L) |
| 81 | `Search_ZeroAllocation_WithTT` | C# | TT açıkken de ısınma sonrası **0 bayt** |
| 82 | `Search_ExistingTestsUnchanged` | C# | Faz 3'ün tüm arama testleri **değişmeden** geçer |

### 12.6 Aşama F — Küp ve maç (Test 83–90)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 83 | `CubeAdvisor_DiceAveraged_IsDefault` | C# | `DiceAveraged = true` varsayılan; `false` → Faz 5 davranışı |
| 84 | `CubeAdvisor_DiceAveraged_IsAccurate` | pytest | gnubg 2-ply uyumu **≥ %75** |
| 85 | `Crawford_Scenarios_AreCorrect` | C# | Crawford'da küp yok; post-Crawford serbest düşüş |
| 86 | `CubeDecision_UsesAllSixProbs` | C# | Mars bilgisi korunur; tek `E`'ye indirgenmez |
| 87 | `MatchAware_Gain_IsMeasured` | pytest | 400 oyun, 2-away → **≥ %45** |
| 88 | `CubeX128_DoesNotFreeze` | Unity PlayMode | Faz 5 §43.13 regresyonu **yok** |
| 89 | `CubeNet_OnlyIfNeeded` | pytest | Küp ağı **yalnızca** uyum < %75 ise devreye girer |
| 90 | `Met_StillMatchesGnubg` | C# | 625 hücre, max \|Δ\| = 0 (Faz 5 korunur) |

### 12.7 Aşama G — Ürün (Test 91–98)

| # | Test | Tür | Ne doğrular |
|---|---|---|---|
| 91 | `OpeningBook_CoversFirstTwoRolls` | C# | İlk 2 zar için en iyi hamle **≤ 50 ms** |
| 92 | `AnalysisPanel_ShowsSixProbs` | Unity PlayMode | `W/GW/BW/L/GL/BL` + `E` + `MWC` görünür |
| 93 | `UndoRedo_50Steps` | Unity PlayMode | 50 adım geri/yinele tutarlı |
| 94 | `SaveLoad_RoundTrip` | C# | Kaydet → yükle → **aynı** durum (hash eşit) |
| 95 | `ColorBlind_Contrast` | pytest | Deuteranopia/protanopia simülasyonunda pul kontrastı **≥ 3:1** |
| 96 | `KeyboardInput_Works` | Unity PlayMode | `1..9,0`, `Enter`, `Esc`, `U` çalışır |
| 97 | `Localization_NoHardcodedStrings` | pytest | Görünür metinlerin tamamı kaynak dosyadan |
| 98 | `FrameRate_60Fps` | Unity PlayMode | 1080p'de **≥ 60 fps**, GC spike **≤ 1 ms** |

---

## 13. Ölçüm, Benchmark ve Kabul Kriterleri

> **Kural (Faz 5 §0.7 ile aynı):** aşağıdaki eşikler **başlangıç/yer tutucu** değerlerdir.
> Ölçüm yapılır ve **gerçek** değer raporlanır. Uydurma sayı yazılmaz.

### 13.1 Güç

| Ölçüm | Faz 5 | **Faz 6 hedefi** | Ölçüm yeri |
|---|---|---|---|
| gnubg ER (2-ply, 200 poz.) | 0,1941 | **< 0,02** | `ml/artifacts/stage_f_er.md` |
| gnubg ER (3-ply, 200 poz.) | — | **< 0,01** | aynı |
| gnubg 0-ply karşısında kazanma | — | **≥ %65** | `ml/artifacts/stage_f_h2h.md` |
| gnubg 2-ply karşısında kazanma | — | **≥ %50** | aynı |
| `PipBot` karşısında kazanma | %40,50 | **≥ %65** | aynı |
| `RandomBot` karşısında kazanma | %80,50 | **≥ %95** | aynı |

### 13.2 Kalibrasyon

| Ölçüm | Faz 5 | **Faz 6 hedefi** |
|---|---|---|
| Eğim | 0,0874 | **0,85–1,15** |
| Korelasyon | +0,2431 | **≥ 0,75** |
| MAE | 0,8014 | **≤ 0,15** |
| Std oranı | 2,78 | **0,7–1,4** |

### 13.3 Küp ve maç

| Ölçüm | Faz 5 | **Faz 6 hedefi** |
|---|---|---|
| Küp uyumu (2-ply) | %52,27 / %61,36 | **≥ %75 / ≥ %75** |
| Maç farkındalığı (2-away) | %40,00 | **≥ %45** |
| Crawford | doğru | **doğru (regresyon yok)** |

### 13.4 Performans

| Ölçüm | Faz 5 | **Faz 6 hedefi** |
|---|---|---|
| ONNX çıkarım (CPU, kova 128) | 724 000 poz/sn | **≥ 700 000** (regresyon yok) |
| ONNX çıkarım (CUDA, kova 2048) | 1 241 000 poz/sn | **≥ 1 200 000** |
| Arama allocation | 0 bayt | **0 bayt** (TT dahil) |
| Depth 2 süre | 50 s/oyun | **≤ 5 s/oyun** |
| Self-play (12 thread) | ölçülmedi | **ölçülür ve raporlanır** |
| Unity fps (1080p) | ölçülmedi | **≥ 60** |

### 13.5 Aşama kabul kriterleri

* **Aşama A:** Test 41–48 yeşil; Bölüm 2 tablosu **yeniden üretilir**; referans küme dondurulur.
* **Aşama B:** Test 49–58 yeşil; `output_version = 2` çalışır; v1 **hâlâ** çalışır.
* **Aşama C:** Test 59–66 yeşil; shard v2 round-trip; Linux yayını çalışır.
* **Aşama D:** Test 67–74 yeşil; **ER < 0,02**; Track L **veya** Track H (biri yeterli).
* **Aşama E:** Test 75–82 yeşil; depth 2 **≤ 5 s/oyun**; referans eşitliği korunur.
* **Aşama F:** Test 83–90 yeşil; küp uyumu **≥ %75**.
* **Aşama G:** Test 91–98 yeşil; kurulum paketi üretilir.
* **Aşama H:** Tüm testler yeşil; `PHASES.md` §13, `ARCHITECTURE.md` §44, `ASSUMPTIONS.md`
  F6-01…F6-xx yazılır; Bölüm 13 tabloları **ölçülmüş** değerlerle dolu.

---

## 14. Kapsam Dışı ve Açık Sorular

**Kapsam dışı (bilinçli):**

* **2 taraflı bearoff veritabanı.** `54264² = 2 944 581 696` pozisyon; dokümante edilmiş
  boyut ≈ 29,4 GB. **Gerek yok:** saf yarışta mars olasılığı ≈ 0'dır ve 1 taraflı DB +
  Faz 5 §3.7 formülü **kesin** equity verir. 6 çıktılı kafa mars bilgisini **temas**
  pozisyonlarında taşır. **Karar: eklenmez.**
* **Race / CRASH / contact veritabanları.** gnubg'de var; nöral yaklaşımda **gereksiz**.
* **Beaver, Raccoon, Chouette, çok oyunculu.**
* **Çevrimiçi çok oyunculu, hesap sistemi, bulut.**
* **Mobil / WebGL / IL2CPP.**
* **Sentis arka ucu.**
* **Çoklu-GPU DDP eğitimi** (ağ çok küçük — Bölüm 3.3).
* **Küp ağı** — yalnızca uyum < %75 ise (Bölüm 10.4).
* **`AfterStateList` / `BackgammonVectorizer` / `BackgammonSearch` gövde değişikliği.**

**Açık sorular — Aşama H'de cevaplandı:**

1. **EVREN erişimi alındı mı?** *(Evet/Hayır + gerekçe.)* Alınmadıysa Track L tek hat
   olarak kalır ve bu **açıkça** raporlanır.
2. **EVREN'de hangi erişim yolu çalıştı?** GPU Rezervasyon / Notebook / Eğitim işi.
   `sbatch` şablonunun **gerçek** hali (partition, gres biçimi, süre sınırı) raporlanır.
3. **Apptainer imajı nasıl taşındı?** (registry / `--bind` / doğrudan kopya.)
4. **Ölçülen GPU-saat/oyun oranı nedir?** Track L'in kaç katı?
5. **`medium` vs `large` kapasite kazancı ölçüldü mü?** ER farkı kaç?
6. **`search_distill` (depth 3) kazancı ölçüldü mü?** Kaç ER puanı?
7. **Küp ağı gerekli miydi?** Uyum %75'i geçti mi?
8. **`λ = 1,0` hedeflerin sıfıra çökmesini çözdü mü?** (F4-41)
9. **`--threads > 1` determinizmi sağlandı mı?** (F4-39)
10. **`max_plies` taşması azaldı mı?** (F4-45)
11. **FP16-AMP kazanç sağladı mı?** (GTX 1650'de bf16 yok.)
12. **gnubg 2-ply karşısında %50 geçildi mi?** Geçilmediyse **hangi** pozisyon
    sınıfında kaybediliyor (temas/yarış/bearoff)?

---

## 15. Aşamalı Teslimat Planı

| Aşama | Teslimat | Kabul kriteri |
|---|---|---|
| **A** | `ml/er_harness.py` (yeniden üretilebilir ER), dondurulmuş 200 pozisyonluk referans küme, `ml/artifacts/stage_f_baseline.md`, Test 41–48 | Test 41–48 yeşil; Bölüm 2 **yeniden üretilir** |
| **B** | `OutcomeDistribution.Equity`/`FromProbabilities`, `output_version = 2` (export + `OnnxModelHandle` + `OnnxPolicyValueEvaluator`), `L_cal`, sıcaklık ölçekleme, Test 49–58 | Test 49–58 yeşil; v1 **hâlâ** çalışır; 0 allocation |
| **C** | `ShardFormat` v2, paralel deterministik self-play, GPU kova birleştirme, `linux-x64` self-contained yayın, `tavla.sif` tarifi, Test 59–66 | Test 59–66 yeşil; Linux ikilisi çalışır |
| **D** | Track L koşu planı (L0–L3) **veya** Track H (H0–H3), `ml/artifacts/stage_f_train.md`, Test 67–74 | **ER < 0,02**; en az bir hat tamamlandı |
| **E** | TT, bearoff kesme, aday kısıtı, erken kesme, depth-3 distill, Test 75–82 | Test 75–82 yeşil; depth 2 **≤ 5 s/oyun**; referans eşitliği |
| **F** | Zar-ortalamalı küp, 6 olasılıklı küp kararı, Crawford doğrulaması, (gerekirse) küp ağı, Test 83–90 | Test 83–90 yeşil; küp uyumu **≥ %75** |
| **G** | Açılış kitabı, analiz paneli, geri al/yinele, kaydet/yükle, palet, klavye, TR/EN, kurulum paketi, Test 91–98 | Test 91–98 yeşil; `TavlaAI-Setup-*.exe` üretilir |
| **H** | `ml/artifacts/stage_f_faz6.md`, `PHASES.md` §13, `ARCHITECTURE.md` §44, `ASSUMPTIONS.md` F6-01…F6-xx, `EXPECTED_COUNTS` güncellemesi, Bölüm 14 cevapları | Tüm testler yeşil; Bölüm 13 tabloları **ölçülmüş** değerlerle dolu |

---

## 🏁 Başlangıç Komutu

Bu dokümanı, **Faz 1 (v4)**, **Faz 2 (v4)**, **Faz 3 (v7)**, **Faz 4 (v3)** ve
**Faz 5 (v1)** spesifikasyonlarını, ayrıca `PHASES.md`, `ARCHITECTURE.md`,
`ASSUMPTIONS.md`, `SHARD_FORMAT.md` ve `ml/config.yaml` dosyalarını oku.
**Yalnızca Aşama A'yı** tamamla ve şunları raporla:

1. **Oluşturulan/değişen dosya listesi** (tam yollar).
2. **ER hattı yeniden üretimi:** Faz 5'in 0,1941 değeri **birebir** çıktı mı? Sapma varsa
   **nereden** geliyor (gnubg sürümü, ply, pozisyon kümesi, argmax kuralı)?
3. **Referans küme:** 200 pozisyonun sınıf dağılımı (temas/yarış/bearoff/bar), hash'i,
   neden dondurulduğu.
4. **İstatistiksel güç:** 200 pozisyonda ER standart hatası kaç? 0,005'in altında mı?
   Değilse **kaç** pozisyon gerekir?
5. **`PHASES.md` §7 tablosu:** her sayı ölçümle uyuşuyor mu? Uyuşmayan varsa hangisi?
6. **gnubg sürümü ve modu:** tam sürüm dizesi, ply, cubeless/cubeful, money/match.
7. **Faz 1–5 uyum notları:** `BackgammonSearch`, `BackgammonVectorizer`,
   `AfterStateList`, `Backgammon.Core` **hiç değişmedi** mi (diff ile kanıtla).
8. **Belirsiz bulduğun noktalar** ve Bölüm 14'teki açık sorulardan **Aşama A ile ilgili**
   olanların cevapları.

Onay gelmeden **Aşama B'ye geçme**.

---

## Sürüm Notu (v1)

**Amaç:** Faz 5'in bıraktığı **güç açığını** (ER 0,1941 → hedef < 0,02) ve **ürün
eksiklerini** tek bir uygulanabilir emirde toplamak; eğitimi **iki donanım hattında**
(yerel GTX 1650 ve EVREN H200) çalışabilir kılmak.

**Yeni olan (Faz 5 v1'e göre):**

1. **6 çıktılı değer kafası** (Bölüm 5): `W, GW, BW, L, GL, BL`; equity **türetilir**.
   `output_version = 2`; v1 **geriye dönük uyumlu**.
2. **Kalibrasyon** (Bölüm 6): 4 kademeli çözüm; kabul eğimi 0,85–1,15.
3. **Shard v2** (Bölüm 7.1): `finalProbs` + opsiyonel `outcomeProbs`; v1 **okunur**.
4. **Deterministik paralel self-play** (Bölüm 7.2): F4-39'u **özelliğe** çevirir.
5. **GPU kova birleştirme** (Bölüm 7.3): GPU kullanımını %10 → %80.
6. **İki eğitim hattı** (Bölüm 3): Track L (GTX 1650) ve Track H (EVREN H200); **aynı kod**,
   farklı konfigürasyon. H200 **veri üretimi** için, eğitim için değil.
7. **EVREN araştırması** (Bölüm 4): erişim (SSB SSO), iş akışı (Slurm + Apptainer),
   **veriyi değil üreticiyi taşı** kararı, `sbatch` şablonu, kredi formülü, kabul kapısı.
8. **Arama gücü** (Bölüm 9): TT, bearoff kesme, aday kısıtı; depth 2 **≤ 5 s/oyun**.
9. **Küp ustalığı** (Bölüm 10): zar-ortalamalı değerlendirme varsayılan; 6 olasılıklı karar.
10. **Ürün mükemmelliği** (Bölüm 11): 12 zorunlu + 6 olmalı özellik, her biri **ölçülebilir**.
11. **58 yeni test** (Test 41–98), aşama aşama.
12. **Dürüstlük** (Bölüm 0 ve 3.3): H200 "daha hızlı eğitim" değildir; 0,003 ER
    **hedeflenmez**; her sayı **ölçülür**.

**Faz 5'ten devralınan ve **kapatılan** açık sorunlar:**

| # | Faz 5 sorunu | Faz 6 çözümü |
|---|---|---|
| F4-41 | `λ = 0,7` hedefleri sıfıra çökertiyor | `λ = 1,0` varsayılan (Bölüm 8.2) |
| F4-39 | `--threads > 1` deterministik değil | Bölüm 7.2 + Test 60 |
| F4-45 | `max_plies` taşması | Bölüm 7.5 |
| F5-? | Değer kafası 11,4× aşırı dağınık | Bölüm 5 + 6 |
| F5-? | `PipBot`'a karşı %40,5 | Bölüm 8 (ölçek) |
| F5-? | Depth 2 pratik değil | Bölüm 9 |
| F5-? | Küp uyumu %52 | Bölüm 10 |