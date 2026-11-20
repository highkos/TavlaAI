# Faz 7-R - Cikarim aninda antisimetriklestirme

Soru: **renk takasi kusurunu egitmeden, cikarimda duzeltebilir miyiz?**

`e_hat = (f(x,+1) - f(x,-1)) / 2`, politika icin `(logit(+1) - logit(-1)) / 2`.
Iki ileri gecis; bir ONNX cikarimi icin ihmal edilebilir maliyet.

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Hakem: gnubg 2-ply

| Yol | Ham ER | Simetrik ER | Fark | %95 GA | Karar |
|---|---|---|---|---|---|
| `policy` | 0.0396 | 0.0343 | -0.0053 | [-0.0135; +0.0024] | kanitlanmadi |
| `value` | 0.0460 | 0.0402 | -0.0058 | [-0.0156; +0.0031] | kanitlanmadi |

| Ayrinti | Deger |
|---|---|
| Vaka | 500 |
| Argmax degisen vaka | 156 (0.3120) |

