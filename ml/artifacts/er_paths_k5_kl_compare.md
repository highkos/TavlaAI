# ER karsilastirmasi -- KL=0 (kontrol) vs KL=0,5 (tedavi)

| | Model |
|---|---|
| KL=0 (kontrol) | `ml\runs\k5_dist\model_kl0.onnx` |
| KL=0,5 (tedavi) | `ml\runs\k5_dist\model_kl05.onnx` |

Korpus `v2`, bolum `all`, hakem 2-ply, vaka **1000**.

| Yol | KL=0 (kontrol) | KL=0,5 (tedavi) | Fark | z | Anlamli |
|---|---|---|---|---|---|
| `policy` | 0.025966 | 0.026273 | +0.000307 | +0.10 | hayir |
| `value` | 0.044881 | 0.044475 | -0.000406 | -0.09 | hayir |
| `search1` | 0.022617 | 0.021507 | -0.001110 | -0.50 | hayir |

Iki ornekli z (eslesmis degil): `er_paths` JSON'u pozisyon basina kaybi saklamaz. Esik |z| >= 1.96.

**Hicbir yol anlamli degismedi.** Bu, degisikligin olculebilir bir etkisi olmadigi anlamina gelir; sifir etki kaniti degil, guc siniridir.

