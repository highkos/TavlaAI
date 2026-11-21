# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\rd_aug10k\onnx\model_v10.onnx`
Yol: `value`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 2 |
| Kazanma | 630/2000 (0.3150) |
| **ppg** | **-0.5570** |
| ppg %95 GA | [-0.6175; -0.4960] |
| ppg standart hata | 0.0310 |
| Eslestirilmis fark (beyaz+siyah) | -1.1140 |
| Eslestirilmis fark %95 GA | [-1.2300; -0.9960] |
| Oyun basina ply | 58.0 |
| Bitmeyen oyun | 0 (0.0000) |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

