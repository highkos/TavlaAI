# Antisimetri kapisi -- havuz uzerinde (K1)

Havuz: `ml/artifacts/curve_pool_400.npz`

`antisymmetry.py measure` korpus v2'yi kullanir; o korpus tam olarak
1000 vakadir, dolayisiyla K1'in istedigi n >= 1245 oradan
karsilanamaz. Bu tablo ayni istatistikleri 400 oyunluk havuzun
held-out kumesinde hesaplar.

| Model | Pozisyon | Afterstate | corr | meanAbsSum | argmax | ER(+1) | ER(-1) | Fark | 95% GA |
|---|---|---|---|---|---|---|---|---|---|
| `stage_d_l2/model_v30.onnx` | 2667 | 50727 | -0.9100 | 0.4340 | 0.362 | 0.0287 | 0.0815 | -0.0527 | [-0.0582; -0.0474] |
| `rd_ctl10k/model_v10.onnx` | 2667 | 50727 | -0.8967 | 0.4247 | 0.327 | 0.0302 | 0.0929 | -0.0627 | [-0.0687; -0.0569] |
| `rd_aug10k/model_v10.onnx` | 2667 | 50727 | -0.9641 | 0.1479 | 0.438 | 0.0387 | 0.0499 | -0.0112 | [-0.0151; -0.0078] |

Kapi esigi `|corr| >= 0.99` bu mimariyle ulasilabilir degil; kapi bir **teshis**tir (F7-104). Karar tek bakisli ER ve ppg ile verilir.
