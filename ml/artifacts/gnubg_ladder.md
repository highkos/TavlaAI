# Faz 7-R - gnubg ER merdiveni

Soru: **model merdivende nerede?** Ayni korpusta gnubg'nin kendi
0/1-ply ER'si, 2-ply hakeme gore.

Korpus: `ml/artifacts/reference_corpus_v2.json`
Hakem: gnubg **2-ply**

| Oyuncu | n | ER | %95 GA | sigma | Tam eslesme |
|---|---|---|---|---|---|
| gnubg 0-ply | 500 | **0.0044** | [0.0032; 0.0058] | 0.0150 | 0.8180 |
| gnubg 1-ply | 500 | **0.0026** | [0.0018; 0.0035] | 0.0097 | 0.8360 |
| gnubg 2-ply | - | **olculemez** | - | - | - |
| **model** `policy` | 1000 | **0.0402** | [0.0350; 0.0457] | 0.0867 | - |
| **model** `search1` | 1000 | **0.0209** | [0.0181; 0.0240] | 0.0473 | - |
| **model** `value` | 1000 | **0.0442** | [0.0384; 0.0504] | 0.0957 | - |

## Notlar

- Hakem kendi kendini olcemez: oyuncu derinligi < hakem derinligi olmali.
- ER tanimi `gnubg_er.measure_position` ile ayni: max(ref) - ref[argmax_P].
- Ayni korpus, ayni hakem: model ER'si ile dogrudan karsilastirilabilir.
- Model satirlari `ml/artifacts/er_paths_v2.json`'dan okunur; burada yeniden olculmez (tek kaynak).

