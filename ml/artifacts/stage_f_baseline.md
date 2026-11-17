# Faz 6 Aşama A — ölçüm hattı ve taban kilidi

Bu rapor `ml/er_harness.py` tarafından **üretilir**; hiçbir sayı elle
yazılmamıştır. Faz 6 v3 Bölüm 12.1 (Test 41a–48) ve Bölüm 15 (Aşama A)
kabul kriterlerini karşılar.

## Ölçüm koşulları (Test 48)

| Alan | Değer |
| --- | --- |
| Model | `ml/artifacts/model_stage_d_v10.onnx` |
| gnubg | `F:/Program Files (x86)/gnubg/gnubg-cli.exe` |
| gnubg sürümü | GNU Backgammon 1.08.003-mingw 32-Bit 20240428 |
| gnubg değerlendirme | 2-ply, cubeless, money game |
| Hamle seçimi | politika başı argmax (C# `ArgMaxCandidate` ile aynı) |
| ER tanımı | `E_best − E_model`, aynı değerlendirici |

## 41a — Faz 5 değerinin yeniden üretimi

| Alan | Değer |
| --- | --- |
| Faz 5 `stage_d_er.md` | 0.1941 |
| Bu ölçüm (50 pozisyon) | **0.1941** |
| Fark | -0.0000 |
| Tolerans | ±0.0100 |
| Sonuç | ✅ yeniden üretildi |

Dışarıda kalan vakalar: `bar-closed-white`, `bar-open-white`, `bearoff-exact-white`, `bearoff-overshoot-white`, `bearoff-blocked-white`, `bearoff-exact-black`, `bar-open-black`

## 41b — 200 pozisyonluk referans küme

| Alan | Değer |
| --- | --- |
| Küme sürümü | v1 |
| Pozisyon | 200 |
| Tohum | 20261114 |
| SHA-256 | `ad85265177515b41fb5e95b3904c231966ececd6928db178be0d84473469d072` |

Faz dağılımı (Test 45):

| Faz | Pozisyon | En az |
| --- | --- | --- |
| temas (`contact`) | 39 | 20 ✅ |
| yarış (`race`) | 40 | 20 ✅ |
| bearoff (`bearoff`) | 37 | 20 ✅ |
| bar (`bar`) | 40 | 20 ✅ |
| kapalı tahta (`closed`) | 44 | 20 ✅ |

Bölünme (Test 44, Kural 10):

| Bölünme | Pozisyon |
| --- | --- |
| `cal` | 60 |
| `val` | 70 |
| `test` | 70 |

Notlar: faz hedefleri dolmadı; 4 pozisyon artan adaylardan tamamlandı

### Ölçülen ER (eşik yok — raporlanır)

| Bölünme | Pozisyon | Ortalama ER | Medyan | Maksimum | Std hata | Std sapma | Eşleşme |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cal` | 60 | **0.3013** | 0.2050 | 1.6770 | 0.0440 | 0.3411 | 8.3% |
| `val` | 70 | **0.1898** | 0.1120 | 0.7540 | 0.0230 | 0.1927 | 11.4% |
| `test` | 70 | **0.1815** | 0.1070 | 1.1960 | 0.0283 | 0.2368 | 21.4% |
| `all` | 200 | **0.2203** | 0.1325 | 1.6770 | 0.0187 | 0.2639 | 14.0% |

## 46 — İstatistiksel güç

| Bölünme | n | Std sapma | Std hata | Hedef SE | Gereken n |
| --- | --- | --- | --- | --- | --- |
| `cal` | 60 | 0.3411 | 0.0440 | 0.005 | 4655 |
| `val` | 70 | 0.1927 | 0.0230 | 0.005 | 1487 |
| `test` | 70 | 0.2368 | 0.0283 | 0.005 | 2243 |
| `all` | 200 | 0.2639 | 0.0187 | 0.005 | 2786 |

Hedef SE 0.005; gereken n pilot ölçümden hesaplanır (Bölüm 12.1, Test 46).

## 41c — `OutcomeDistribution` kodlaması

**Sonuç: `cumulative`.**

`Backgammon.Core/Match/OutcomeDistribution.cs` alanları:

* `Win` = P(en az tek kazanır) = `W + GW + BW`
* `WinGammon` = P(en az mars kazanır) = `GW + BW`
* `WinBackgammon` = `BW`
* `Lose` = `1 − Win` (türetilir)
* `LoseGammon`, `LoseBackgammon` aynı kümülatif mantıkla

Yani sınıf **kümülatif** (gnubg geleneği) kodlama kullanır. Faz 6'nın
`FromProbabilities` metodu **dışlayıcı** girdi alır ve sınıf içinde bu
kodlamaya dönüştürür (Bölüm 5.1, Bölüm 5.5).

## 41d — `resultType` `winner`'ı içeriyor mu?

**Sonuç: HAYIR.**

`Backgammon.Core/Enums.cs` `GameResultType` = `{None=0, Single=1, Gammon=2,
Backgammon=3}` — yalnızca **çarpan** bilgisini taşır. `Backgammon.SelfPlay/
SelfPlayRunner.cs` L132–134 `game.Winner` ve `game.ResultType`'ı **ayrı**
alanlara yazar. Bu yüzden 6 sınıflı hedef türetilirken `winner` ayrı alandan
okunur (Bölüm 7.1).

## 41e — Veri hacmi (ölçülmüş)

| Alan | Değer |
| --- | --- |
| Shard dosyası | 1 |
| Oyun | 100 |
| Karar | 9088 |
| Karar/oyun | 90.88 |
| Ham bayt/karar | **3824.2** |
| Disk bayt/karar (gzip) | **128.9** |

Faz 6 v3 Bölüm 7.4, v1'deki "11,5 KB/karar" iddiasını kaldırmıştı; ölçülen değer yukarıdadır.

## 47 — `PHASES.md` §7 taban kilidi

| Ölçüm | `PHASES.md` §7 | Bu ölçüm | Durum |
| --- | --- | --- | --- |
| gnubg ER (2-ply) | 0.1941 | 0.1941 | ✅ |

Diğer §7 satırları (kazanma oranları, kalibrasyon, küp uyumu) bu hattın
kapsamı dışındadır; kendi artefaktlarından doğrulanır.

## 42 / 43 — Determinizm ve gnubg zorunluluğu

* **42:** aynı seed + aynı model + CPU → aynı ER. `ml/tests/test_er_harness.py`
  bunu iki kez ölçerek doğrular.
* **43:** gnubg yoksa `main()` sıfır olmayan çıkış kodu döner ve **hiçbir**
  sayı üretmez (`gnubg_er.main` ile aynı davranış).

