# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Yol: `policy`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 2 |
| Kazanma | 682/2000 (0.3410) |
| **ppg** | **-0.4430** |
| ppg %95 GA | [-0.5020; -0.3835] |
| ppg standart hata | 0.0300 |
| Eslestirilmis fark (beyaz+siyah) | -0.8860 |
| Eslestirilmis fark %95 GA | [-0.9990; -0.7720] |
| Oyun basina ply | 56.2 |
| Bitmeyen oyun | 0 (0.0000) |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

