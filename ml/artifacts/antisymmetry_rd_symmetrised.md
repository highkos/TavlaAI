# Faz 7-R - Cikarim aninda antisimetriklestirme

Soru: **renk takasi kusurunu egitmeden, cikarimda duzeltebilir miyiz?**

`e_hat = (f(x,+1) - f(x,-1)) / 2`, politika icin `(logit(+1) - logit(-1)) / 2`.
Iki ileri gecis; bir ONNX cikarimi icin ihmal edilebilir maliyet.

Model: `runs\stage_rd\onnx\model_v10.onnx`
Hakem: gnubg 2-ply

| Yol | Ham ER | Simetrik ER | Fark | %95 GA | Karar |
|---|---|---|---|---|---|
| `policy` | 0.0385 | 0.0489 | +0.0104 | [+0.0051; +0.0157] | kanitlanmadi |
| `value` | 0.2004 | 0.1910 | -0.0094 | [-0.0224; +0.0039] | kanitlanmadi |

| Ayrinti | Deger |
|---|---|
| Vaka | 1000 |
| Argmax degisen vaka | 351 (0.3510) |

