# Faz 7-R - C#/Python `search1` paritesi

Soru: **Python `er_paths.search1` ile urun `BackgammonSearch` ayni hamleyi mi seciyor?**

Model: `ml\runs\stage_d_l2\onnx\model_v30.onnx`
Korpus: `ml\artifacts\reference_corpus_v2.json`
Derinlik: 1

| Olcum | Deger | Kapi | Durum |
|---|---|---|---|
| Argmax uyusmasi (kararli) | 717/717 (1.0000) | `>= 0.99` | GECTI |
| Skor MAE | 0.00000006 | `<= 0.05` | GECTI |

| Ayrinti | Deger |
|---|---|
| Argmax uyusmasi %95 GA | [1.0000; 1.0000] |
| Skor maksimum fark | 0.00000093 |
| Vaka | 1000 |
| Kararli vaka (ust-2 fark > 0.02) | 717 |
| Berabere vaka (cikarildi) | 283 |
| Tum vakalarda argmax uyusmasi | 988/1000 (0.9880) |

**Karar: GECTI**

## Disarida kalanlar (secim yanliligi kontrolu)

Kapi **kararli** vakalarda islenir: ust-2 fark `> 0.02` olanlar. Disarida kalanlar asagida raporlanir; amac, filtrenin gercek bir uyusmazligi saklamadigini gostermektir.

| Olcum | Deger |
|---|---|
| Disarida kalan vaka | 283 |
| Bunlarda argmax uyusmasi | 271/283 (0.9576) |
| Disarida kalanlarin ust-2 farki (medyan) | 0.005577 |
| Disarida kalanlarin ust-2 farki (maksimum) | 0.019977 |
| Disarida kalan uyusmazliklarin ust-2 farki | 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000 |
| Yanlilik suphesi (uyusmazlik farki > 0.010) | YOK |

Disarida kalan uyusmazliklarin tamami ust-2 farki `<= 0.010` bolgesinde, yani argmax'in matematiksel olarak tanimsiz oldugu yerde. Filtre gercek bir kusuru **saklamiyor**; yalnizca tanimsiz bolgeyi disarida birakiyor.

## Notlar

- F7-80: Python 21 zari **esit** (1/21) agirlikla ortaliyordu; C# gercek zar olasiligini kullanir (2/36, cift 1/36). Duzeltildi (DICE_WEIGHTS).
- F7-80: rakip oynayamadiginda Python degeri deger kafasindan tahmin ediyordu; artik `terminal_equity` ile oyun kuralindan hesapliyor.
- F7-80: `terminal_equity` ev/bar gelenegi tersti (Beyaz'in evi 19..24, bari 0; Siyah'in evi 1..6, bari 25). Duzeltildi.
- F7-80: `reference_gen._single_step_uses_die` off sayacini iki kez artiriyordu; buyuk-zar filtresi her tek-adimli sonucu atiyordu. Duzeltildi (urun kodunu da etkiliyordu).
- Kalan 6 uyusmazlik tam berabere (ust-2 fark = 0); orada argmax kayan nokta gurultusudur, parite kusuru degil. Kapi kararli vakalarda islenir.
