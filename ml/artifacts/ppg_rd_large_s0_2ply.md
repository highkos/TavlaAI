# Faz 7-R - Model vs gnubg 2-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\capacity_rd\large\seed0\model.onnx`
Yol: `search1`
gnubg: **2-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 10 |
| Kazanma | 839/2000 (0.4195) |
| **ppg** | **-0.2445** |
| ppg %95 GA | [-0.3055; -0.1835] |
| ppg standart hata | 0.0310 |
| Eslestirilmis fark (beyaz+siyah) | -0.4890 |
| Eslestirilmis fark %95 GA | [-0.5990; -0.3770] |
| Oyun basina ply | 55.9 |
| Bitmeyen oyun | 0 (0.0000) |

**Yorum.** ppg > 0 ise model gnubg 2-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

