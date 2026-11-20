# Faz 7-R - Cikarim aninda antisimetriklestirme

Soru: **renk takasi kusurunu egitmeden, cikarimda duzeltebilir miyiz?**

`e_hat = (f(x,+1) - f(x,-1)) / 2`, politika icin `(logit(+1) - logit(-1)) / 2`.
Iki ileri gecis; bir ONNX cikarimi icin ihmal edilebilir maliyet.

Model: `ml\runs\rd_aug10k\onnx\model_v10.onnx`
Hakem: gnubg 2-ply

| Yol | Ham ER | Simetrik ER | Fark | %95 GA | Karar |
|---|---|---|---|---|---|
| `policy` | 0.0485 | 0.0457 | -0.0028 | [-0.0083; +0.0028] | kanitlanmadi |
| `value` | 0.0627 | 0.0573 | -0.0054 | [-0.0123; +0.0013] | kanitlanmadi |

| Ayrinti | Deger |
|---|---|
| Vaka | 1000 |
| Argmax degisen vaka | 317 (0.3170) |

