# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Yol: `value`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 2 |
| Kazanma | 701/2000 (0.3505) |
| **ppg** | **-0.4150** |
| ppg %95 GA | [-0.4740; -0.3560] |
| ppg standart hata | 0.0302 |
| Eslestirilmis fark (beyaz+siyah) | -0.8300 |
| Eslestirilmis fark %95 GA | [-0.9430; -0.7160] |
| Oyun basina ply | 56.4 |
| Bitmeyen oyun | 0 (0.0000) |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

