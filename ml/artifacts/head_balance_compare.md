# Kafa dengesi -- modeller arasi (K5)

| Model | Politika CE | Deger MSE | ||g_politika|| | ||g_deger|| | Oran | Deger payi |
|---|---|---|---|---|---|---|
| `ml/runs/stage_d_l2/checkpoints/ckpt_v30.pt` | 1.3943 | 0.1709 | 1.3514 | 0.9144 | 1.48 | 40.4% |
| `ml/runs/rd_ctl10k/checkpoints/ckpt_v10.pt` | 1.4699 | 0.1697 | 1.0778 | 0.9033 | 1.19 | 45.6% |
| `ml/runs/rd_aug10k/checkpoints/ckpt_v10.pt` | 1.5659 | 0.1200 | 1.4183 | 0.4263 | 3.33 | 23.1% |

Deger payi araligi: **23.1% -- 45.6%**.

Deger payi dusuk olan model, deger kafasinin govdeyi daha az yonlendirdigi modeldir. R-F'de `value` ve `search1` ppg'si en kotu olan modelin payi en dusuktur; yani perspektif artirimi **deger kafasini** vurmustur.

