# Değerlendirme raporu

| Alan | Değer |
|---|---|
| Model | `ml\runs\stage_d\onnx\model_v10.onnx` |
| Oyun / rakip | 200 |
| Seed | 777 |
| DepthPly | 1 |
| MaxCandidatesRoot / Inner | 4 / 4 |

| Rakip | Oyun | Kazanma | Ortalama puan | 95% GA |
|---|---|---|---|---|
| RandomBot | 200 | 80.50 % | +1.5800 ± 0.1308 | [+1.3237, +1.8363] |
| PipBot | 200 | 40.50 % | -0.2300 ± 0.1452 | [-0.5146, +0.0546] |
| Model:model_v5 | 200 | 54.50 % | +0.2300 ± 0.1475 | [-0.0590, +0.5190] |

Protokol: sabit seed, `argmax`, renkler değişimli. Puanlar küp olmadan
(cubeValue = 1) ve Jacoby kapalı olarak Faz 1 `GameResult.Points`'tur.
