# Oyun yolu x model ppg matrisi (K5)

Kupsuz para oyunu, eslestirilmis zar + renk takasi, gnubg 0-ply, 2000 oyun (1000 cift), tohum 2026.

| Model | politika-argmax | deger-0-ply | search1 (deger 1-ply) |
|---|---|---|---|
| `stage_d_l2/model_v30` | **-0.4430** [-0.5020; -0.3835] | **-0.4150** [-0.4740; -0.3560] | **-0.1635** [-0.2230; -0.1050] |
| `rd_ctl10k/model_v10` | **-0.4605** [-0.5180; -0.4015] | **-0.4445** [-0.5040; -0.3860] | **-0.1990** [-0.2600; -0.1380] |
| `rd_aug10k/model_v10` | **-0.5160** [-0.5755; -0.4565] | **-0.5570** [-0.6175; -0.4960] | **-0.3240** [-0.3810; -0.2670] |

`value` yolu gnubg 0-ply ile **elma-elmaya** kiyaslanabilen tek yoldur: ikisi de after-state degerlendirmesiyle oynar. `search1` bir ply arar, `policy` deger kafasini hic kullanmaz.

## Bitmeyen oyunlar

`max_plies` doldugunda oyun **0 puan** sayilir. Bu oyunlar ppg'yi asagi ceker; oran yuksekse ppg yorumu temkinli yapilmalidir.

| Model | Yol | Bitmeyen | Oran |
|---|---|---|---|
| `rd_ctl10k/model_v10` | politika-argmax | 1 | 0.0005 |
| `rd_ctl10k/model_v10` | deger-0-ply | 2 | 0.0010 |

## Yol farklari (ayni model, `search1` referans)

| Model | Yol | Fark | 95% GA | z | Anlamli |
|---|---|---|---|---|---|
| `stage_d_l2/model_v30` | politika-argmax | -0.2795 | [-0.3632; -0.1958] | -6.55 | evet |
| `stage_d_l2/model_v30` | deger-0-ply | -0.2515 | [-0.3353; -0.1677] | -5.88 | evet |
| `rd_ctl10k/model_v10` | politika-argmax | -0.2615 | [-0.3466; -0.1764] | -6.02 | evet |
| `rd_ctl10k/model_v10` | deger-0-ply | -0.2455 | [-0.3307; -0.1603] | -5.64 | evet |
| `rd_aug10k/model_v10` | politika-argmax | -0.1920 | [-0.2744; -0.1096] | -4.56 | evet |
| `rd_aug10k/model_v10` | deger-0-ply | -0.2330 | [-0.3164; -0.1496] | -5.48 | evet |

Negatif fark = o yol `search1`'ten daha kotu.

## Model farklari (ayni yol, `stage_d_l2/model_v30` referans)

| Yol | Model | Fark | 95% GA | z | Anlamli |
|---|---|---|---|---|---|
| politika-argmax | `rd_ctl10k/model_v10` | -0.0175 | [-0.1004; +0.0654] | -0.41 | hayir |
| politika-argmax | `rd_aug10k/model_v10` | -0.0730 | [-0.1567; +0.0107] | -1.71 | hayir |
| deger-0-ply | `rd_ctl10k/model_v10` | -0.0295 | [-0.1128; +0.0538] | -0.69 | hayir |
| deger-0-ply | `rd_aug10k/model_v10` | -0.1420 | [-0.2268; -0.0572] | -3.28 | evet |
| search1 (deger 1-ply) | `rd_ctl10k/model_v10` | -0.0355 | [-0.1213; +0.0503] | -0.81 | hayir |
| search1 (deger 1-ply) | `rd_aug10k/model_v10` | -0.1605 | [-0.2429; -0.0781] | -3.82 | evet |

## Uyari

Kosular ayni zar tohumunu (2026) kullanir ama modeller farkli hamle oynadigi icin oyunlar ayrilir; iki ornekli GA bu yuzden yaklasiktir. Her kosunun kendi eslesmis GA'si zar gurultusunu zaten iptal ettigi icin GA oldugundan dar gorunmez.

