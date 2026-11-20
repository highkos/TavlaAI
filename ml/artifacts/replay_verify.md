# K2 - Kayitli oyunlarin yeniden oynatma dogrulamasi

Soru: `_single_step_uses_die` hatasi **uretilmis** veriye sizdi mi?

Kaynak: `runs/stage_d_l2/shards`

| Olcum | Deger |
|---|---|
| Shard | 6 |
| Oyun | 60000 |
| Karar | 3710732 |
| Pas | 442020 |
| Hamle | 3268712 |
| **Pas kaydi var, aday sayisi != 1** | **0** |
| Pas kaydi var, aday sayisi == 1 (beklenen) | 442020 |
| Hamle kaydi var, aday yok | 0 |
| Secilen aday kumesinde degil | 0 / 1805887 |
| Secilen terminal | 60000 |

Pas kararlarinda `candidateTotal` dagilimi: 1 -> 442020

**Karar: KORPUS TEMIZ**

**Yontem.** Her karar icin `candidateTotal` ile `DEC_IS_PASS` bayragi
karsilastirilir. `BackgammonSearch.SearchNode` yasal hamle yokken listeye
bir pas afterstate'i ekledigi icin (`list.AddPass(s)`) pas kararinin
`CandidateCount` degeri **1**'dir; beklenen budur. Hata tetiklendiginde
aday kumesi bosalir ve oyun pas yazar; bu yuzden
`pass_with_candidates > 0` (yani `candidateTotal != 1`) hatanin
**dogrudan** kanitidir. `chosen_not_in_candidates` yalnizca
`logged == candidateTotal` iken denetlenir (dup_cap kesilmis kumelerde
secilen aday loglanmamis olabilir).
