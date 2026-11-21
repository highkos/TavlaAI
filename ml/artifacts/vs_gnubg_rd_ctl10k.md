# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\rd_ctl10k\onnx\model_v10.onnx`
Yol: `search1`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 3 |
| Kazanma | 864/2000 (0.4320) |
| **ppg** | **-0.1990** |
| ppg %95 GA | [-0.2600; -0.1380] |
| ppg standart hata | 0.0315 |
| Eslestirilmis fark (beyaz+siyah) | -0.3980 |
| Eslestirilmis fark %95 GA | [-0.5160; -0.2770] |
| Oyun basina ply | 57.1 |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

