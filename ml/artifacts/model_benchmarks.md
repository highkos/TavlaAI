# Model kıyaslama paneli (Faz 8 Görev 2)

Plan etiketli sabit setler üzerinde gnubg referanslı ER. **Yalnızca ekleme**:
eski satırlar değiştirilmez, yeni ölçüm sona eklenir.

Setler: `contact` = attacking + priming + anchoring + backgame;
`race` = purerace + racing. Set hash'i değişirse satırlar karşılaştırılamaz.

| # | Zaman | Model | sha256 | Çıktı | Set | Hash | n | ER ort. | Medyan | Maks | Tam eşleşme |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-27T22:53:53Z | `ml/runs/capacity100k_rd_sweep/xlarge/seed1/model.onnx` | `e7379074a907` | v2 | contact | `a3382435bb32` | 149 | 0.0075 | 0.0000 | 0.3270 | 80.5% |
| 1 | 2026-11-27T22:53:53Z | `ml/runs/capacity100k_rd_sweep/xlarge/seed1/model.onnx` | `e7379074a907` | v2 | race | `2cdc833a7e68` | 80 | 0.0151 | 0.0000 | 0.2450 | 60.0% |
| 2 | 2026-11-27T23:07:04Z | `ml/runs/capacity100k_rd_sweep/xlarge/seed0/model.onnx` | `19091c5bf1a7` | v2 | contact | `a3382435bb32` | 149 | 0.0098 | 0.0000 | 0.3270 | 76.5% |
| 2 | 2026-11-27T23:07:04Z | `ml/runs/capacity100k_rd_sweep/xlarge/seed0/model.onnx` | `19091c5bf1a7` | v2 | race | `2cdc833a7e68` | 80 | 0.0226 | 0.0000 | 0.3320 | 56.2% |
| 3 | 2026-11-27T23:16:21Z | `ml/runs/capacity100k_rd_sweep/large/seed1/model.onnx` | `2a2c48ed9499` | v2 | contact | `a3382435bb32` | 149 | 0.0105 | 0.0000 | 0.3270 | 77.2% |
| 3 | 2026-11-27T23:16:21Z | `ml/runs/capacity100k_rd_sweep/large/seed1/model.onnx` | `2a2c48ed9499` | v2 | race | `2cdc833a7e68` | 80 | 0.0162 | 0.0000 | 0.2450 | 58.8% |
| 4 | 2026-11-27T23:25:38Z | `ml/runs/capacity100k_rd_sweep/medium/seed1/model.onnx` | `299e2e619e52` | v2 | contact | `a3382435bb32` | 149 | 0.0081 | 0.0000 | 0.3270 | 77.2% |
| 4 | 2026-11-27T23:25:38Z | `ml/runs/capacity100k_rd_sweep/medium/seed1/model.onnx` | `299e2e619e52` | v2 | race | `2cdc833a7e68` | 80 | 0.0140 | 0.0000 | 0.2450 | 62.5% |
| 5 | 2026-11-27T23:35:04Z | `ml/runs/capacity_rd/large/seed0/model.onnx` | `788ec39ce4ab` | v2 | contact | `a3382435bb32` | 149 | 0.0070 | 0.0000 | 0.2030 | 77.2% |
| 5 | 2026-11-27T23:35:04Z | `ml/runs/capacity_rd/large/seed0/model.onnx` | `788ec39ce4ab` | v2 | race | `2cdc833a7e68` | 80 | 0.0122 | 0.0000 | 0.2370 | 65.0% |
| 6 | 2026-11-27T23:44:34Z | `ml/runs/capacity30k_rd_sweep/xlarge/seed1/model.onnx` | `0aade041a38e` | v2 | contact | `a3382435bb32` | 149 | 0.0085 | 0.0000 | 0.1940 | 75.8% |
| 6 | 2026-11-27T23:44:34Z | `ml/runs/capacity30k_rd_sweep/xlarge/seed1/model.onnx` | `0aade041a38e` | v2 | race | `2cdc833a7e68` | 80 | 0.0129 | 0.0000 | 0.2370 | 63.7% |
| 7 | 2026-11-27T23:53:56Z | `ml/runs/stage_d_l2/onnx/model_v30.onnx` | `13c7092eacbf` | v2 | contact | `a3382435bb32` | 149 | 0.0348 | 0.0000 | 0.6660 | 60.4% |
| 7 | 2026-11-27T23:53:56Z | `ml/runs/stage_d_l2/onnx/model_v30.onnx` | `13c7092eacbf` | v2 | race | `2cdc833a7e68` | 80 | 0.0388 | 0.0000 | 0.4610 | 57.5% |
| 8 | 2026-11-28T00:03:33Z | `ml/runs/stage_d_l2/onnx/model_v1.onnx` | `5d2603b4a071` | v2 | contact | `a3382435bb32` | 149 | 0.0512 | 0.0000 | 0.6240 | 52.3% |
| 8 | 2026-11-28T00:03:33Z | `ml/runs/stage_d_l2/onnx/model_v1.onnx` | `5d2603b4a071` | v2 | race | `2cdc833a7e68` | 80 | 0.0453 | 0.0000 | 0.4610 | 52.5% |
| 9 | 2026-11-28T00:13:12Z | `ml/runs/gnubg_distill/model_gnubg.onnx` | `5933669e313a` | v2 | contact | `a3382435bb32` | 149 | 0.0548 | 0.0000 | 0.8790 | 53.0% |
| 9 | 2026-11-28T00:13:12Z | `ml/runs/gnubg_distill/model_gnubg.onnx` | `5933669e313a` | v2 | race | `2cdc833a7e68` | 80 | 0.0479 | 0.0000 | 0.4610 | 51.2% |
| 10 | 2026-11-28T00:22:50Z | `ml/runs/k5_dist/model_kl05.onnx` | `9eaa08c0958e` | v2 | contact | `a3382435bb32` | 149 | 0.0189 | 0.0000 | 0.3660 | 69.8% |
| 10 | 2026-11-28T00:22:50Z | `ml/runs/k5_dist/model_kl05.onnx` | `9eaa08c0958e` | v2 | race | `2cdc833a7e68` | 80 | 0.0355 | 0.0000 | 0.5640 | 55.0% |

## Plan kırılımı (son kayıt)

| Set | Plan | n | ER ort. | Maks |
|---|---|---|---|---|
| contact | attacking | 40 | 0.0182 | 0.3660 |
| contact | priming | 40 | 0.0319 | 0.3300 |
| contact | anchoring | 40 | 0.0084 | 0.1320 |
| contact | backgame | 29 | 0.0161 | 0.2820 |
| race | purerace | 40 | 0.0059 | 0.1440 |
| race | racing | 40 | 0.0653 | 0.5640 |

## Model karşılaştırması

| Model | sha256 | contact ER | contact eşleşme | race ER | race eşleşme |
|---|---|---|---|---|---|
| `ml/runs/capacity_rd/large/seed0/model.onnx` | `788ec39ce4ab` | 0.0070 | 77.2% | 0.0122 | 65.0% |
| `ml/runs/capacity100k_rd_sweep/xlarge/seed1/model.onnx` | `e7379074a907` | 0.0075 | 80.5% | 0.0151 | 60.0% |
| `ml/runs/capacity100k_rd_sweep/medium/seed1/model.onnx` | `299e2e619e52` | 0.0081 | 77.2% | 0.0140 | 62.5% |
| `ml/runs/capacity30k_rd_sweep/xlarge/seed1/model.onnx` | `0aade041a38e` | 0.0085 | 75.8% | 0.0129 | 63.7% |
| `ml/runs/capacity100k_rd_sweep/xlarge/seed0/model.onnx` | `19091c5bf1a7` | 0.0098 | 76.5% | 0.0226 | 56.2% |
| `ml/runs/capacity100k_rd_sweep/large/seed1/model.onnx` | `2a2c48ed9499` | 0.0105 | 77.2% | 0.0162 | 58.8% |
| `ml/runs/k5_dist/model_kl05.onnx` | `9eaa08c0958e` | 0.0189 | 69.8% | 0.0355 | 55.0% |
| `ml/runs/stage_d_l2/onnx/model_v30.onnx` | `13c7092eacbf` | 0.0348 | 60.4% | 0.0388 | 57.5% |
| `ml/runs/stage_d_l2/onnx/model_v1.onnx` | `5d2603b4a071` | 0.0512 | 52.3% | 0.0453 | 52.5% |
| `ml/runs/gnubg_distill/model_gnubg.onnx` | `5933669e313a` | 0.0548 | 53.0% | 0.0479 | 51.2% |
