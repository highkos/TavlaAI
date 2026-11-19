# Faz 7-R - C#/Python `search1` paritesi

Soru: **Python `er_paths.search1` ile urun `BackgammonSearch` ayni hamleyi mi seciyor?**

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Korpus: `ml\artifacts\reference_corpus_v2.json`
Derinlik: 1

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| Argmax uyusmasi (kararli) | 357/357 (1.0000) | `>= 0.99` | GECTI |
| Skor MAE | 0.00000005 | `<= 0.05` | GECTI |

| Ayrinti | Deger |
|---|---|
| Argmax uyusmasi %95 GA | [1.0000; 1.0000] |
| Skor maksimum fark | 0.00000075 |
| Vaka | 500 |
| Kararli vaka (ust-2 fark > 0.02) | 357 |
| Berabere vaka (cikarildi) | 143 |
| Tum vakalarda argmax uyusmasi | 494/500 (0.9880) |

**Karar: GECTI**

## Notlar

- F7-80: Python 21 zari **esit** (1/21) agirlikla ortaliyordu; C# gercek zar olasiligini kullanir (2/36, cift 1/36). Duzeltildi (DICE_WEIGHTS).
- F7-80: rakip oynayamadiginda Python degeri deger kafasindan tahmin ediyordu; artik `terminal_equity` ile oyun kuralindan hesapliyor.
- F7-80: `terminal_equity` ev/bar gelenegi tersti (Beyaz'in evi 19..24, bari 0; Siyah'in evi 1..6, bari 25). Duzeltildi.
- F7-80: `reference_gen._single_step_uses_die` off sayacini iki kez artiriyordu; buyuk-zar filtresi her tek-adimli sonucu atiyordu. Duzeltildi (urun kodunu da etkiliyordu).
- Kalan 6 uyusmazlik tam berabere (ust-2 fark = 0); orada argmax kayan nokta gurultusudur, parite kusuru degil. Kapi kararli vakalarda islenir.
