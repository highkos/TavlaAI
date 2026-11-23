# Faz 7-R - derin hakem (`hint`) ER merdiveni

Soru: **2-ply hakemin kendi ER'si ne kadar?** gnubg'nin 0/1/2/3-ply
degerlendirmesi, **4-ply `hint`** hakemine gore (R-F madde 1).

| Alan | Deger |
|---|---|
| Hakem | gnubg `hint`, 4-ply (filtre acik) |
| Pozisyon | 20 |
| Eslesme hatasi | 0 |

| Oyuncu | n | Kapsama | Sansurlu | ER | %95 GA | sigma | Tam eslesme |
|---|---|---|---|---|---|---|---|
| gnubg 0-ply | 20 | 100.0% | 0 | **0.0049** | [0.0002; 0.0112] | 0.0130 | 0.8000 |
| gnubg 1-ply | 20 | 100.0% | 0 | **0.0040** | [0.0000; 0.0092] | 0.0108 | 0.8500 |
| gnubg 2-ply | 20 | 100.0% | 0 | **0.0006** | [0.0000; 0.0016] | 0.0021 | 0.9000 |
| gnubg 3-ply | 20 | 100.0% | 0 | **0.0002** | [0.0000; 0.0006] | 0.0009 | 0.9500 |

> **Yontem notu (F7-04):** 2-ply degerleri gnubg `eval` ile, 3-ply ve 4-ply degerleri gnubg `hint` ile olculur (F7-04). Iki protokol ayni pozisyonda birebir ayni sonucu vermez; 2/3 sinirindaki merdiven adimi elma-elmadir degildir.

**ER cozunurluk tabani.** 2-ply hakemin 4-ply hakeme gore ER'si, olculen model ER'lerinin altinda kalan gurultu tabanidir: bundan kucuk farklar yontem gurultusudur.

