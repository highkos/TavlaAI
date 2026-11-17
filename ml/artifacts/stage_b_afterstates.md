# Faz 5 §9.2 — Model deger kafasi vs gnubg (afterstate)

> **TARIHSEL KAYIT — GECERSIZ (F6-31).** Bu rapordaki sayilar hatali bir olcumden
> gelir: `ml/afterstate_bench.py` tahtayi gnubg'ye aynalanmis olarak veriyordu
> (`row0[i] = board[1+i]`, `row1[i] = -board[24-i]`; dogrusu
> `row0[i] = board[24-i]`, `row1[i] = -board[1+i]`) ve gnubg'nin Python API'si
> bu projede guvenilir degil (F6-28). Guncel kalibrasyon olcumu icin
> `ml/artifacts/stage_h_calibration.md` (gnubg metin protokolu) esas alinir.
> Asagidaki tablo yalnizca Faz 5'in ne raporladigini belgelemek icin korunmustur.

Kaynak: `Backgammon.MatchBench dump-afterstates` (rastgele self-play).
gnubg: `evaluate` (cubeless, 0-ply, deterministic).
Perspektif: her iki tarafta da hamleyi yapan oyuncu.

| Metrik | Deger |
|---|---|
| Karsilastirilan afterstate | 400 |
| Atlanan | 0 |
| Korelasyon (Pearson) | 0.2431 |
| Ortalama mutlak hata (MAE) | 0.8014 |
| Sistematik sapma (bizim - gnubg) | -0.0850 |
| Bizim equity araligi | -2.8050 .. +3.2966 |
| gnubg equity araligi | -0.8207 .. +1.6497 |
| Bizim standart sapma | 1.0320 |
| gnubg standart sapma | 0.3710 |

## Dogrusal kalibrasyon (tani)

`gnubg ~ a * bizim + b` en kucuk kareler fiti:

| Katsayi | Deger |
|---|---|
| a (olcek) | 0.0874 |
| b (kayma) | +0.1589 |
| Kalibrasyon sonrasi MAE | 0.2897 |
| Kalibrasyon sonrasi korelasyon | 0.2431 |

`a < 1` modelin deger kafasinin **asiri dagilmis** (over-dispersed) oldugunu gosterir.

