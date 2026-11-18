# Kup karari ER'si

**Tanim.** gnubg `eval` uc *cubeful* equity verir (ciftleme /
ciftle+red / ciftle+kabul). Bizim danisman iki eylemden birini secer:
ciftleme -> `noDouble`; ciftle -> `min(doublePass, doubleTake)`
(rakip bizim equity'mizi minimize eder). **Kup ER'si** =
`max(noDouble, min(doublePass, doubleTake)) - secilen`.

**Referans sozlesmesi.** gnubg `eval`, 2-ply, cubeful on,
kup acik; `Cubeful equities` blogu ve `Proper cube action` satiri.

## Ozet

| Olcum | Deger |
|---|---|
| Pozisyon | 400 |
| **Kup ER'si (ortalama)** | **0,0642** |
| sigma | 0,1894 |
| Standart hata | 0,0095 |
| %95 GA | [0,0469; 0,0837] |
| Ciftleme uyumu | 300/400 (0,7500) |
| Kabul/red uyumu | 64/76 (0,8421) |
| Hedef | < 0,0200 |

## Karisiklik matrisi (ciftleme)

| gnubg \ biz | Ciftleme yok | Ciftle |
|---|---|---|
| **Ciftleme yok** | 242 | 82 |
| **Ciftle** | 18 | 58 |

## Mac baglamina gore

| Baglam | n | Kup ER'si | Uyum |
|---|---|---|---|
| `match5` | 200 | 0,0860 | 0,7450 |
| `match9` | 100 | 0,0564 | 0,7000 |
| `money` | 100 | 0,0284 | 0,8100 |

## Kup sahipligine gore

| Sahip | n | Kup ER'si | Uyum |
|---|---|---|---|
| `centre` | 200 | 0,0575 | 0,7800 |
| `ours` | 200 | 0,0709 | 0,7200 |

## Gereken n (sigma ust sinirindan)

| Fark | sigma (ust) | Gereken n | Mevcut n | Yeterli |
|---|---|---|---|---|
| 0,01 | 0,2367 | 1517 | 400 | **hayir** |
| 0,02 | 0,2367 | 380 | 400 | evet |

## Kapsam notu

Bu olcum **kup kararini** olcer, hamle secimini degil. Hamle ER'si
`ml/er_paths.py` ile ayri raporlanir. Ikisi toplanmaz; dunya
sampiyonu iddiasi **ikisini birden** gerektirir.
