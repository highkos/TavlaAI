# Faz 7-R - Model vs gnubg 2-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\capacity100k_rd_sweep\xlarge\seed1\model.onnx`
Yol: `search1`
gnubg: **2-ply**

| Olcum | Deger |
|---|---|
| Oyun | 4400 (2200 cift) |
| Paralel surec | 10 |
| Kazanma | 1911/4400 (0.4343) |
| **ppg** | **-0.1709** |
| ppg %95 GA | [-0.2091; -0.1323] |
| ppg standart hata | 0.0197 |
| Eslestirilmis fark (beyaz+siyah) | -0.3418 |
| Eslestirilmis fark %95 GA | [-0.4141; -0.2691] |
| Oyun basina ply | 54.1 |
| Bitmeyen oyun | 0 (0.0000) |
| Denetim noktasindan gelen cift | 0 |

**Yorum.** ppg > 0 ise model gnubg 2-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

