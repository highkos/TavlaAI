# Aşama C — yürütme sağlayıcısı kararı (CPU vs CUDA)

**Tarih:** 2026-11-15
**Karar:** **CPU** (`SelfPlayConfig.DefaultUseCuda = false`)

Faz 6 v3 §12.3 (Test 61) "CUDA ≥ CPU" varsayıyordu. Bu makinede **ölçüm bu varsayımı
çürüttü**. Aşağıdaki sayılar ham ölçümdür; hiçbiri tahmin değildir.

## Donanım ve yazılım

| Bileşen | Değer |
|---|---|
| CPU | Intel Core i7-9750H, 6C/12T |
| GPU | NVIDIA GeForce GTX 1650, 4 GB GDDR5, Turing SM 7.5 |
| Sürücü | 580.88 (CUDA 13.0 uyumlu) |
| CUDA toolkit | v11.8 ve v12.3 kurulu |
| cuDNN | 9 (PyTorch paketiyle gelen `cudnn64_9.dll`) |
| ONNX Runtime | 1.23.2, `Microsoft.ML.OnnxRuntime.Gpu` |
| Model | `ml/artifacts/model_stage_d_v10.onnx` (221-256-256-128, ~156 bin parametre) |

**CUDA execution provider gerçekten yüklendi.** Doğrulama: `torch\lib` dizini `PATH`'te
değilken `--cuda true` şu hatayı verir —

```
Error loading "onnxruntime_providers_cuda.dll" which depends on "cublasLt64_12.dll"
which is missing. (Error 126)
```

`torch\lib` (CUDA 12.1 + cuDNN 9 çalışma zamanı) `PATH`'e eklendiğinde oturum açılır.
Yani aşağıdaki CUDA sayıları **gerçek GPU** üzerinden alınmıştır, sessiz CPU geri
düşmesi yoktur.

## Ölçüm 1 — Test 61 (bellek içi, shard yazımı yok)

`StageCDataEngineTests.Test61`, 20 oyun, `depth 0`, `log-top 4`, `max-batch 2048`,
ısınma geçişi dahil, CPU iki kez ölçülür (sıralama yanlılığını kırmak için):

| Sağlayıcı | oyun/sn |
|---|---|
| CPU (önce) | 116,23 |
| CPU (sonra) | 119,26 |
| **CPU (seçilen)** | **119,26** |
| CUDA | 29,11 |

**CUDA/CPU = 0,24×** → CUDA **4,1× daha yavaş**.

> **Ölçüm tuzağı (kayda değer).** Isınma geçişi olmadan, 6 oyunla yapılan ilk ölçümde
> CUDA 1,47× *hızlı* göründü. Sebep ölçüm hatasıydı: CPU ilk koşuyordu (JIT + ONNX oturumu
> + dosya ön belleği soğuk), CUDA ikinci (her şey sıcak). Isınma geçişi + 20 oyun + CPU'nun
> iki kez ölçülmesi bu yanlılığı kaldırdı. **Bu, Test 61'in ilk sürümündeki gerçek bir
> kusurdu ve düzeltildi.**

## Ölçüm 2 — CLI, 60 oyun, `depth 0`, `log-top 4`

| Sağlayıcı | oyun/sn | tepe bellek | disk yazma |
|---|---|---|---|
| CPU | **85,91** | 87 MB | 24,40 MB/s |
| CUDA | 24,68 | 381 MB | 7,01 MB/s |

**CUDA/CPU = 0,29×** → CUDA **3,5× daha yavaş**, ayrıca **4,4× daha fazla bellek**.

## Ölçüm 3 — CLI, derinlik taraması, `max-root 4 / max-inner 4`

| depth | CPU oyun/sn | CUDA oyun/sn | CUDA/CPU |
|---|---|---|---|
| 0 | 85,91 | 24,68 | 0,29× |
| 1 | 1,52 | 0,25 | 0,16× |
| 2 | 0,03 | < 0,01 | < 0,3× |

Derinlik arttıkça CUDA **daha da kötüleşiyor**: arama ağacı C# tarafında CPU'da
geziliyor, GPU yalnızca yaprak değerlendirmesini görüyor ve her çağrı için ödeme
yapılıyor.

## Neden GPU kaybediyor

1. **Model çok küçük.** ~156 bin parametre, 221→256→256→128. Bir forward geçişi CPU'da
   ~1 µs. GPU çekirdek başlatma gecikmesi tek başına ~20–50 µs.
2. **Kovalar küçük.** `depth 0`'da bir çağrı ~20–40 kök adayı taşır; kova 32 veya 64'e
   yuvarlanır. 4 GB'lık GTX 1650'de 32 satırlık bir matmul, çekirdek başlatma maliyetinin
   altında kalır.
3. **İş parçacıkları arası kova birleştirme yok.** Faz 6 v3 §7.3'te tarif edilen
   "threads arası batch birleştirme" henüz uygulanmadı. Uygulanırsa kova 2048'e çıkabilir
   ve GPU kazanabilir — ama bu ayrı bir deneydir ve **şu anki veri motoru için gereksizdir**.
4. **Bellek.** CUDA yolu 381 MB tepe bellek kullanıyor (CPU 87 MB). 12 iş parçacığında bu
   ~4,5 GB'a çıkar; makinede 31,9 GB var ama GTX 1650'nin 4 GB'ı zaten masaüstü
   uygulamalarıyla 1,8 GB dolu.

## Karar ve sonuçları

* `SelfPlayConfig.DefaultUseCuda = false` — **CPU** varsayılan.
* `--cuda true` bayrağı **korunur** (H200 gibi güçlü GPU'larda ve kova birleştirme
  uygulandığında gerekli olacak).
* Test 61 artık "CUDA kazanmalı" demiyor; **ölçülen kazananın seçili olmasını** istiyor
  (`SelfPlayConfig.DefaultUseCuda` ile karşılaştırır, eşik 1,2×). Başka donanımda CUDA
  kazanırsa test kırmızı olur ve sabitin çevrilmesini söyler — sessiz sapma olmaz.
* Determinizm iddiası GPU yoluna **taşınmaz** (Faz 6 §7.3). CPU yolu bit düzeyinde
  deterministtir (Test 60).

## Yeniden üretim

```powershell
# CUDA calisma zamanini PATH'e ekle (PyTorch paketindeki CUDA 12.1 + cuDNN 9)
$env:PATH = "$(python -c "import torch,os;print(os.path.join(os.path.dirname(torch.__file__),'lib'))");" + $env:PATH

dotnet test Backgammon.Inference.Tests -c Release `
	-p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu `
	--filter "FullyQualifiedName~Test61" --logger "console;verbosity=detailed"
```

Varsayılan (CPU) derlemede Test 61 `Inconclusive` olur ve CPU ölçümünü yazdırır.
