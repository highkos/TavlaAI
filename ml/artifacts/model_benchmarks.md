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
| 11 | 2026-11-28T02:39:00Z | `ml/runs/corpus_sl_100k/seed0/model.onnx` | `ea4f1116e279` | v2 | contact | `a3382435bb32` | 149 | 0.0287 | 0.0000 | 0.5540 | 63.8% |
| 11 | 2026-11-28T02:39:00Z | `ml/runs/corpus_sl_100k/seed0/model.onnx` | `ea4f1116e279` | v2 | race | `2cdc833a7e68` | 80 | 0.0290 | 0.0000 | 0.5640 | 63.7% |
| 12 | 2026-11-28T02:48:07Z | `ml/runs/corpus_sl_100k/seed1/model.onnx` | `b11c863d1a90` | v2 | contact | `a3382435bb32` | 149 | 0.0318 | 0.0000 | 0.5290 | 63.1% |
| 12 | 2026-11-28T02:48:07Z | `ml/runs/corpus_sl_100k/seed1/model.onnx` | `b11c863d1a90` | v2 | race | `2cdc833a7e68` | 80 | 0.0313 | 0.0000 | 0.5640 | 60.0% |
| 13 | 2026-11-28T02:57:31Z | `ml/runs/corpus_sl_100k/seed2/model.onnx` | `751e67d53df9` | v2 | contact | `a3382435bb32` | 149 | 0.0269 | 0.0000 | 0.5290 | 63.1% |
| 13 | 2026-11-28T02:57:31Z | `ml/runs/corpus_sl_100k/seed2/model.onnx` | `751e67d53df9` | v2 | race | `2cdc833a7e68` | 80 | 0.0208 | 0.0000 | 0.3320 | 65.0% |
| 14 | 2026-11-28T03:23:07Z | `ml/runs/corpus_sl_100k/diag_A_contact_only/model.onnx` | `74fb60b6dda7` | v2 | contact | `a3382435bb32` | 149 | 0.0072 | 0.0000 | 0.2030 | 80.5% |
| 14 | 2026-11-28T03:23:07Z | `ml/runs/corpus_sl_100k/diag_A_contact_only/model.onnx` | `74fb60b6dda7` | v2 | race | `2cdc833a7e68` | 80 | 0.0140 | 0.0000 | 0.2280 | 63.7% |
| 15 | 2026-11-28T03:38:55Z | `ml/runs/corpus_sl_100k/diag_B_contact_gentle/model.onnx` | `c3e62a70e943` | v2 | contact | `a3382435bb32` | 149 | 0.0094 | 0.0000 | 0.2030 | 73.8% |
| 15 | 2026-11-28T03:38:55Z | `ml/runs/corpus_sl_100k/diag_B_contact_gentle/model.onnx` | `c3e62a70e943` | v2 | race | `2cdc833a7e68` | 80 | 0.0148 | 0.0000 | 0.2370 | 61.3% |
| 16 | 2026-11-28T04:01:28Z | `ml/runs/corpus_sl_100k/mix_seed0/model.onnx` | `1ede0be8c7e0` | v2 | contact | `a3382435bb32` | 149 | 0.0077 | 0.0000 | 0.2030 | 77.9% |
| 16 | 2026-11-28T04:01:28Z | `ml/runs/corpus_sl_100k/mix_seed0/model.onnx` | `1ede0be8c7e0` | v2 | race | `2cdc833a7e68` | 80 | 0.0132 | 0.0000 | 0.2280 | 63.7% |
| 17 | 2026-11-28T04:23:41Z | `ml/runs/corpus_sl_100k/mix_seed1/model.onnx` | `9e7eff58278d` | v2 | contact | `a3382435bb32` | 149 | 0.0106 | 0.0000 | 0.3270 | 77.9% |
| 17 | 2026-11-28T04:23:41Z | `ml/runs/corpus_sl_100k/mix_seed1/model.onnx` | `9e7eff58278d` | v2 | race | `2cdc833a7e68` | 80 | 0.0114 | 0.0000 | 0.2280 | 66.2% |
| 18 | 2026-11-28T04:45:39Z | `ml/runs/corpus_sl_100k/mix_seed2/model.onnx` | `bd1c7df23395` | v2 | contact | `a3382435bb32` | 149 | 0.0098 | 0.0000 | 0.3270 | 77.2% |
| 18 | 2026-11-28T04:45:39Z | `ml/runs/corpus_sl_100k/mix_seed2/model.onnx` | `bd1c7df23395` | v2 | race | `2cdc833a7e68` | 80 | 0.0149 | 0.0000 | 0.2280 | 58.8% |

## Plan kırılımı (son kayıt)

| Set | Plan | n | ER ort. | Maks |
|---|---|---|---|---|
| contact | attacking | 40 | 0.0169 | 0.1940 |
| contact | priming | 40 | 0.0123 | 0.3270 |
| contact | anchoring | 40 | 0.0055 | 0.0770 |
| contact | backgame | 29 | 0.0028 | 0.0500 |
| race | purerace | 40 | 0.0156 | 0.2280 |
| race | racing | 40 | 0.0143 | 0.1740 |

## Model karşılaştırması

| Model | sha256 | contact ER | contact eşleşme | race ER | race eşleşme |
|---|---|---|---|---|---|
| `ml/runs/capacity_rd/large/seed0/model.onnx` | `788ec39ce4ab` | 0.0070 | 77.2% | 0.0122 | 65.0% |
| `ml/runs/corpus_sl_100k/diag_A_contact_only/model.onnx` | `74fb60b6dda7` | 0.0072 | 80.5% | 0.0140 | 63.7% |
| `ml/runs/capacity100k_rd_sweep/xlarge/seed1/model.onnx` | `e7379074a907` | 0.0075 | 80.5% | 0.0151 | 60.0% |
| `ml/runs/corpus_sl_100k/mix_seed0/model.onnx` | `1ede0be8c7e0` | 0.0077 | 77.9% | 0.0132 | 63.7% |
| `ml/runs/capacity100k_rd_sweep/medium/seed1/model.onnx` | `299e2e619e52` | 0.0081 | 77.2% | 0.0140 | 62.5% |
| `ml/runs/capacity30k_rd_sweep/xlarge/seed1/model.onnx` | `0aade041a38e` | 0.0085 | 75.8% | 0.0129 | 63.7% |
| `ml/runs/corpus_sl_100k/diag_B_contact_gentle/model.onnx` | `c3e62a70e943` | 0.0094 | 73.8% | 0.0148 | 61.3% |
| `ml/runs/capacity100k_rd_sweep/xlarge/seed0/model.onnx` | `19091c5bf1a7` | 0.0098 | 76.5% | 0.0226 | 56.2% |
| `ml/runs/corpus_sl_100k/mix_seed2/model.onnx` | `bd1c7df23395` | 0.0098 | 77.2% | 0.0149 | 58.8% |
| `ml/runs/capacity100k_rd_sweep/large/seed1/model.onnx` | `2a2c48ed9499` | 0.0105 | 77.2% | 0.0162 | 58.8% |
| `ml/runs/corpus_sl_100k/mix_seed1/model.onnx` | `9e7eff58278d` | 0.0106 | 77.9% | 0.0114 | 66.2% |
| `ml/runs/k5_dist/model_kl05.onnx` | `9eaa08c0958e` | 0.0189 | 69.8% | 0.0355 | 55.0% |
| `ml/runs/corpus_sl_100k/seed2/model.onnx` | `751e67d53df9` | 0.0269 | 63.1% | 0.0208 | 65.0% |
| `ml/runs/corpus_sl_100k/seed0/model.onnx` | `ea4f1116e279` | 0.0287 | 63.8% | 0.0290 | 63.7% |
| `ml/runs/corpus_sl_100k/seed1/model.onnx` | `b11c863d1a90` | 0.0318 | 63.1% | 0.0313 | 60.0% |
| `ml/runs/stage_d_l2/onnx/model_v30.onnx` | `13c7092eacbf` | 0.0348 | 60.4% | 0.0388 | 57.5% |
| `ml/runs/stage_d_l2/onnx/model_v1.onnx` | `5d2603b4a071` | 0.0512 | 52.3% | 0.0453 | 52.5% |
| `ml/runs/gnubg_distill/model_gnubg.onnx` | `5933669e313a` | 0.0548 | 53.0% | 0.0479 | 51.2% |
