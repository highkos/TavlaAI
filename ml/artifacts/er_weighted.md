# Iki bakisli ER karsilastirmasi (F7-101)

Havuz: `ml/artifacts/curve_pool_400.npz` — 2667 held-out pozisyon.

`ER(+1)` havuzun kendi (oynayan) bakisi, `ER(-1)` karsi bakis, `Ort`
ikisinin ortalamasi. **R-D karari `Ort` sutununa gore verilir**; tek
bakisli ER artirimin takasini goremez.

| Model | ER(+1) pol | ER(-1) pol | **Ort** pol | ER(+1) deger | ER(-1) deger | **Ort** deger | Asimetri pol/deger |
|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30.onnx` | 0.0270 | 0.1081 | **0.0675** | 0.0287 | 0.1019 | **0.0653** | 4.00x / 3.55x |
| `rd_ctl10k/model_v10.onnx` | 0.0298 | 0.1202 | **0.0750** | 0.0302 | 0.1177 | **0.0739** | 4.03x / 3.90x |
| `rd_aug10k/model_v10.onnx` | 0.0383 | 0.0691 | **0.0537** | 0.0387 | 0.0717 | **0.0552** | 1.80x / 1.85x |

## Oyun sikligina agirlikli ER (K3)

Havuz temas agirliklidir; gercek oyunlarda faz paylari farklidir.
`game_frequency_weights` her pozisyonu `hedef/havuz` oraniyla
agirliklandirir (ortalama 1'e normalize), boylece agirlikli ER
oynanan dagilimi temsil eder.

| Faz | Havuz payi | Gercek oyun payi | Agirlik |
|---|---|---|---|
| contact | 0.6970 | 0.5219 | 0.75x |
| race | 0.1159 | 0.1292 | 1.12x |
| bar | 0.1871 | 0.3488 | 1.86x |

| Model | Ort pol | **Agirlikli pol** | Fark | Ort deger | **Agirlikli deger** | Fark |
|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30.onnx` | 0.0675 | **0.0646** | -4.4% | 0.0653 | **0.0633** | -3.1% |
| `rd_ctl10k/model_v10.onnx` | 0.0750 | **0.0713** | -4.9% | 0.0739 | **0.0698** | -5.5% |
| `rd_aug10k/model_v10.onnx` | 0.0537 | **0.0492** | -8.5% | 0.0552 | **0.0500** | -9.3% |
