# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\rd_aug10k\onnx\model_v10.onnx`
Yol: `policy`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 2 |
| Kazanma | 644/2000 (0.3220) |
| **ppg** | **-0.5160** |
| ppg %95 GA | [-0.5755; -0.4565] |
| ppg standart hata | 0.0304 |
| Eslestirilmis fark (beyaz+siyah) | -1.0320 |
| Eslestirilmis fark %95 GA | [-1.1450; -0.9150] |
| Oyun basina ply | 57.1 |
| Bitmeyen oyun | 0 (0.0000) |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

