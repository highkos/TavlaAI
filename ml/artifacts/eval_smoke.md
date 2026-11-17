# Değerlendirme raporu

| Alan | Değer |
|---|---|
| Model | `ml\artifacts\model_stage_c.onnx` |
| Oyun / rakip | 60 |
| Seed | 99 |
| DepthPly | 0 |
| MaxCandidatesRoot / Inner | 0 / 0 |

| Rakip | Oyun | Kazanma | Ortalama puan | 95% GA |
|---|---|---|---|---|
| RandomBot | 60 | 61.67 % | +0.7833 ± 0.2448 | [+0.3035, +1.2632] |
| PipBot | 60 | 18.33 % | -0.8667 ± 0.2223 | [-1.3024, -0.4310] |

Protokol: sabit seed, `argmax`, renkler değişimli. Puanlar küp olmadan
(cubeValue = 1) ve Jacoby kapalı olarak Faz 1 `GameResult.Points`'tur.
