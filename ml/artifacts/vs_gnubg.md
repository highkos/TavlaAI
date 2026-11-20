# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Yol: `search1`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 6 |
| Kazanma | 868/2000 (0.4340) |
| **ppg** | **-0.1635** |
| ppg %95 GA | [-0.2230; -0.1050] |
| ppg standart hata | 0.0303 |
| Eslestirilmis fark (beyaz+siyah) | -0.3270 |
| Eslestirilmis fark %95 GA | [-0.4420; -0.2120] |
| Oyun basina ply | 55.9 |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

