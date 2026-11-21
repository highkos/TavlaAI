# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\rd_aug10k\onnx\model_v10.onnx`
Yol: `search1`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 3 |
| Kazanma | 753/2000 (0.3765) |
| **ppg** | **-0.3240** |
| ppg %95 GA | [-0.3810; -0.2670] |
| ppg standart hata | 0.0291 |
| Eslestirilmis fark (beyaz+siyah) | -0.6480 |
| Eslestirilmis fark %95 GA | [-0.7600; -0.5330] |
| Oyun basina ply | 54.5 |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

