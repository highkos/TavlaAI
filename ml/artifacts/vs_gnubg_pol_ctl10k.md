# Faz 7-R - Model vs gnubg 0-ply (kupsuz para oyunu)

R-D oncesi **taban**. Eslestirilmis zar + renk takasi: ayni zar dizisi
bir kez biz beyaz, bir kez biz siyah oynanir; zar sansi iki kolda aynidir.

Model: `ml\runs\rd_ctl10k\onnx\model_v10.onnx`
Yol: `policy`
gnubg: **0-ply**

| Olcum | Deger |
|---|---|
| Oyun | 2000 (1000 cift) |
| Paralel surec | 2 |
| Kazanma | 664/2000 (0.3320) |
| **ppg** | **-0.4605** |
| ppg %95 GA | [-0.5180; -0.4015] |
| ppg standart hata | 0.0298 |
| Eslestirilmis fark (beyaz+siyah) | -0.9210 |
| Eslestirilmis fark %95 GA | [-1.0360; -0.8030] |
| Oyun basina ply | 56.0 |
| Bitmeyen oyun | 1 (0.0005) |

**Yorum.** ppg > 0 ise model gnubg 0-ply'i yeniyor demektir. Eslestirilmis fark, ayni zar dizisinin iki renginin toplamidir; zar gurultusunu iptal ettigi icin **daha dar** bir GA verir.

**Bitmeyen oyunlar.** `max_plies` doldugunda oyun **0 puan** sayilir (biz kazanamadik) ve yukarida ayrica raporlanir. Bu, tek kafali yollarin (`policy`, `value`) donguye girebildigini gosterir; `search1` kosularinda gorulmedi.

