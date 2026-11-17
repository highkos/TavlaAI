# Faz 6 Bolum 13.2 - Deger kafasi kalibrasyonu (olculmus)

Kaynak: `stage_h_afterstates.json` (rastgele self-play afterstate'leri).
Model: `ml/runs/stage_d_l2/onnx/model_v30.onnx`.
gnubg: metin protokolu, `eval` 0-ply, cubeless (`ml/gnubg_er.py::GnubgSession`).
Perspektif: her afterstate hamleyi yapanin bakis acisindan (F6-29 sozlesmesi).

| Metrik | Faz 5 | Faz 6 (olculen) | Hedef | Kapi |
|---|---|---|---|---|
| Egim | 0,0874 | **0,6601** | 0,85 - 1,15 | **KALDI** |
| Korelasyon | +0,2431 | **+0,8989** | >= 0,75 | gecti |
| MAE | 0,8014 | **0,2755** | <= 0,15 | **KALDI** |
| Std orani | 2,78 | **1,3617** | 0,7 - 1,4 | gecti |

## Destekleyici olcumler

| Metrik | Deger |
|---|---|
| Karsilastirilan afterstate | 400 |
| Atlanan | 0 |
| Sistematik sapma (bizim - gnubg) | -0,1547 |
| Bizim equity araligi | -1,6907 .. +1,9094 |
| gnubg equity araligi | -1,3710 .. +1,8310 |
| Bizim standart sapma | 0,7350 |
| gnubg standart sapma | 0,5398 |
| Dogrusal fit `gnubg ~ a*bizim + b` | a = 0,6601, b = +0,1350 |
| Kalibrasyon sonrasi MAE | 0,1927 |

## Yorum

Kapi disinda kalan metrikler: **egim, MAE**.

Faz 5'e gore degisim: egim 0,0874 -> 0,6601, korelasyon +0,2431 -> +0,8989,
MAE 0,8014 -> 0,2755, std orani 2,78 -> 1,3617.

**Not (F6-31).** Faz 5'in kalibrasyon olcumu (`ml/afterstate_bench.py`) tahtayi
gnubg Python API'sine **aynalanmis** veriyordu: `row0[i] = board[1+i]` ve
`row1[i] = -board[24-i]`, dogrusu `row0[i] = board[24-i]` ve
`row1[i] = -board[1+i]`. Aynali tahta baska bir pozisyondur, bu yuzden
Faz 5'in 0,0874 egimi ve +0,2431 korelasyonu **olcum hatasiydi**,
modelin gercek kalibrasyonu degildi. Ayrintilar: `ASSUMPTIONS.md` F6-31.

