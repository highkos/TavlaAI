# Faz 7-R - gnubg ER merdiveni

Soru: **model merdivende nerede?** Ayni korpusta gnubg'nin kendi
0/1-ply ER'si, 2-ply hakeme gore; 2/3/4-ply satirlari olculemez.

Korpus: `ml/artifacts/reference_corpus_v2.json`
Hakem: gnubg **2-ply**

| Oyuncu | n | ER | %95 GA | sigma | Tam eslesme |
|---|---|---|---|---|---|
| gnubg 0-ply | 300 | **0.0062** | [0.0040; 0.0088] | 0.0212 | 0.8067 |
| gnubg 1-ply | 300 | **0.0044** | [0.0029; 0.0063] | 0.0153 | 0.7833 |
| gnubg 2-ply | - | **olculemez** | - | - | - |
| gnubg 3-ply | - | **olculemez** | - | - | - |
| gnubg 4-ply | - | **olculemez** | - | - | - |
| **model** `capacity_re/medium/seed0:policy` | 300 | **0.0189** | [0.0133; 0.0255] | 0.0546 | - |
| **model** `capacity_re/medium/seed0:search1` | 300 | **0.0238** | [0.0177; 0.0305] | 0.0562 | - |
| **model** `capacity_re/medium/seed0:value` | 300 | **0.0367** | [0.0256; 0.0497] | 0.1063 | - |
| **model** `capacity_re/large/seed0:policy` | 300 | **0.0172** | [0.0119; 0.0235] | 0.0524 | - |
| **model** `capacity_re/large/seed0:search1` | 300 | **0.0231** | [0.0179; 0.0288] | 0.0485 | - |
| **model** `capacity_re/large/seed0:value` | 300 | **0.0318** | [0.0217; 0.0442] | 0.0995 | - |
| **model** `capacity_rd/large/seed0:policy` | 300 | **0.0111** | [0.0077; 0.0152] | 0.0334 | - |
| **model** `capacity_rd/large/seed0:search1` | 300 | **0.0139** | [0.0101; 0.0185] | 0.0375 | - |
| **model** `capacity_rd/large/seed0:value` | 300 | **0.0173** | [0.0105; 0.0264] | 0.0711 | - |

## Notlar

- Hakem kendi kendini olcemez: oyuncu derinligi < hakem derinligi olmali.
- ER tanimi `gnubg_er.measure_position` ile ayni: max(ref) - ref[argmax_P].
- Ayni korpus, ayni hakem: model ER'si ile dogrudan karsilastirilabilir.
- Model satirlari `ml/artifacts/er_paths_v2.json`'dan okunur; burada yeniden olculmez (tek kaynak).

