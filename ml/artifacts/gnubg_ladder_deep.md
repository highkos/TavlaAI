# Faz 7-R - derin hakem (`hint`) ER merdiveni

Soru: **2-ply hakemin kendi ER'si ne kadar?** gnubg'nin 0/1/2/3-ply
degerlendirmesi, **3-ply `hint`** hakemine gore (R-F madde 1).

| Alan | Deger |
|---|---|
| Hakem | gnubg `hint`, 3-ply (filtre acik) |
| Pozisyon | 40 |
| Eslesme hatasi | 0 |

| Oyuncu | n | Kapsama | Sansurlu | ER | %95 GA | sigma | Tam eslesme |
|---|---|---|---|---|---|---|---|
| gnubg 0-ply | 40 | 100.0% | 0 | **0.0063** | [0.0010; 0.0135] | 0.0207 | 0.7750 |
| gnubg 1-ply | 40 | 100.0% | 0 | **0.0027** | [0.0005; 0.0057] | 0.0084 | 0.8250 |
| gnubg 2-ply | 40 | 100.0% | 0 | **0.0013** | [0.0003; 0.0027] | 0.0039 | 0.8250 |

> **Yontem notu (F7-04):** 2-ply degerleri gnubg `eval` ile, 3-ply ve 4-ply degerleri gnubg `hint` ile olculur (F7-04). Iki protokol ayni pozisyonda birebir ayni sonucu vermez; 2/3 sinirindaki merdiven adimi elma-elmadir degildir.

**ER cozunurluk tabani.** 2-ply hakemin 3-ply hakeme gore ER'si, olculen model ER'lerinin altinda kalan gurultu tabanidir: bundan kucuk farklar yontem gurultusudur.

