# Renk takasi antisimetrisi: uc kurulumun karsilastirmasi (F7-120)

Renk takasi `T = flip_perspective` girdi uzerinde bir girisimdir. Antisimetri
`f(Tx) = -f(x)` demektir; **negasyon** altinda teklik (`f(-x) = -f(x)`) yetmez,
cunku `Tx != -x`.

## 1. Teshis (1500 adim, medium, tohum 0)

| Varyant | Parametre | valTop1 | valValueMse |
|---|---:|---:|---:|
| `plain` | 156 423 | 0.7827 | 0.01686 |
| `sym-qminus-ew32` | 131 619 | 0.6614 | 0.05851 |
| `sym-qminus-ew128` | 158 211 | 0.6668 | 0.05649 |
| `sym-full-ew32` | 160 291 | 0.7527 | 0.02737 |
| `sym-full-ew128` | 186 883 | 0.7468 | 0.02904 |
| `higgins` | 156 423 | 0.7791 | 0.02607 |

Cift kolu genisletmek (ew32 -> ew128) hicbir sey kazandirmiyor; tek kolu tam
girdiye baglamak 0,09 valTop1 geri getiriyor. Yani darboğaz `Q_minus`
izdusumunun kendisi: tek kol cift ozelliklerden (pip, temas, mac skoru)
tamamen kopuyor ve `pip_farki x temas` gibi tek etkilesimleri kuramiyor.

`sym-full` (tek kol tam 221 boyutlu girdide) **yanlis matematiktir**: olcum
`net(x) + net(-x) = 0.0` ama `net(x) + net(Tx) = 1.0369` verir. Bu yuzden
kaldirildi.

## 2. Tam recete (5000 adim, medium, tohum 0)

| Kurulum | Parametre | valTop1 | valValueMse | ER politika | ER deger | ER search1 | antisimetri `corr` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `plain` | 156 423 | 0.8157 | 0.01329 | 0.01188 | 0.01825 | 0.01545 | -0.9436 ❌ |
| `basis` | 131 619 | 0.7001 | 0.04624 | — | — | — | -1.0000 ✅ |
| `higgins` | 156 423 | 0.7994 | 0.02299 | 0.01726 | 0.02678 | 0.01523 | -1.0000 ✅ |

## 3. Sonuc

`higgins` **antisimetri kapisini gecen tek yuksek-dogruluklu** kurulumdur.
`plain` kapıyı dusurur (-0,9436); `basis` gecer ama valTop1'de 0,1156
kaybeder. `higgins` o kaybin 0,0993'unu geri kazanir ve **uretim yolu olan
search1 ER'sinde duz modelden hafifce iyidir** (0,01523 vs 0,01545).

Politika ve deger ER'lerinin bir miktar yukselmesi beklenen bir sonuctur:
hedefin cift bileseni atildigi icin 0-ply argmax daha az keskinlesir; buna
karsilik 1-ply arama bu kaybi telafi eder. Uretimde oynanan yol search1'dir.

## 4. Maliyet

`HigginsNet` iki ileri gecis yapar (duz govde iki bakistan degerlendirilir).
ONNX cikariminda bu ihmal edilebilir; C# sozlesmesi degismez (ayni iki cikti,
ayni adlar, `output_version = 2`). ONNX paritesi: `maxAbsDeltaValue = 8,94e-08`,
`maxAbsDeltaPolicyLogit = 4,47e-08`.
