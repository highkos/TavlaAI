# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Yol: `policy`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 20 (10 cift) |
| Kazanma | 11/20 (0.5500) |
| **ppg** | **+0.2000** |
| ppg %95 GA | [-0.3500; +0.7500] |
| ppg standart hata | 0.2865 |
| Eslestirilmis fark (beyaz+siyah) | +0.4000 |
| Eslestirilmis fark %95 GA | [-0.4000; +1.1000] |
| Oyun basina ply | 60.8 |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

