# GNU Backgammon equity kaybı (ER) ölçümü

Faz 4 v3 Bölüm 9 (Aşama D) kabul kriteri: referans pozisyonlarda pozisyon
başına equity kaybı ölçümü. Değerler **gerçek gnubg çağrılarından** üretilmiştir;
hiçbir sayı elle yazılmamıştır.

| Alan | Değer |
| --- | --- |
| Model | `ml/runs/stage_d/onnx/model_v10.onnx` |
| gnubg | `F:/Program Files (x86)/gnubg/gnubg-cli.exe` |
| gnubg sürümü | GNU Backgammon 1.08.003-mingw 32-Bit 20240428 |
| gnubg değerlendirme | 2-ply, cubeless, money game |
| Hamle seçimi | politika başı argmax (C# `ArgMaxCandidate` ile aynı) |
| Referans vaka | 57 (kullanılabilir 50) |
| Dışarıda kalan | `bar-closed-white`, `bar-open-white`, `bearoff-exact-white`, `bearoff-overshoot-white`, `bearoff-blocked-white`, `bearoff-exact-black`, `bar-open-black` |

## Yöntem

1. Pozisyon `set board simple` ile gnubg'ye yüklenir. gnubg geçersiz tahtayı
   sessizce reddettiği için `show pipcount` çıktısı Python'da hesaplanan pip
   sayılarıyla karşılaştırılır; uyuşmazsa vaka atılır.
2. Modelin `afterStates` listesi 221 elemanlı vektöre çevrilip ONNX modeline
   verilir; `argmax` modelin hamlesini verir (`--criterion policy`).
3. **Tüm** afterstate'ler tek bir gnubg sürecinde, sıra rakibe verilerek ve
   2-ply cubeless `eval` ile değerlendirilir; işaret çevrilerek hamleyi yapanın
   equity'si bulunur.
4. `E_best = max(afterstate equity'leri)`, `E_model = modelin seçtiği afterstate`.
5. `ER = E_best - E_model` (pozitif = model kaybı).

`E_best` ve `E_model` **aynı değerlendiriciyle** (aynı ply, aynı cubeless mod)
üretildiği için ER tutarlıdır. gnubg'nin kendi `hint` sıralaması yalnızca
bilgi amaçlı kaydedilir: gnubg-cli'de `hint` her zaman 0-ply çalışır
(`set evaluation chequerplay evaluation plies` sadece `eval`'i etkiler).

Tahta dönüşümü: gnubg'de **X = Siyah** (24->1 oynar, evi 1-6) ve **O = Beyaz**
olduğu için `simple[0] = -board[25]`, `simple[i] = -board[i]`, `simple[25] = board[0]`.
Başlangıç pozisyonu `4HPwATDgc/ABMA` position ID'sini ve 167/167 pip verir.

## Özet

| Metrik | Değer |
| --- | --- |
| Pozisyon | 50 |
| Ortalama ER | 0.1941 |
| Medyan ER | 0.1410 |
| Maksimum ER | 0.5600 |
| gnubg ile aynı hamle | 32.0% |

## Pozisyon bazında

| # | Pozisyon | Zar | Aday | gnubg en iyi # | E_best | E_model | ER | Aynı |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `big-die-white` | 3-5 | 1 | 0 | +1.8950 | +1.8950 | +0.0000 | evet |
| 2 | `double-4-steps-white` | 2-2 | 75 | 52 | +0.2540 | -0.0450 | +0.2990 | hayır |
| 3 | `start-6-6` | 6-6 | 11 | 0 | +0.3920 | -0.1520 | +0.5440 | hayır |
| 4 | `start-3-1` | 1-3 | 16 | 11 | +0.1590 | -0.1460 | +0.3050 | hayır |
| 5 | `start-5-5` | 5-5 | 4 | 2 | +0.1440 | -0.1240 | +0.2680 | hayır |
| 6 | `random-000` | 1-1 | 42 | 30 | +0.2350 | -0.2110 | +0.4460 | hayır |
| 7 | `random-001` | 1-4 | 26 | 7 | +0.2100 | -0.3110 | +0.5210 | hayır |
| 8 | `random-002` | 2-6 | 1 | 0 | -0.4370 | -0.4370 | +0.0000 | evet |
| 9 | `random-003` | 5-6 | 1 | 0 | -0.3990 | -0.3990 | +0.0000 | evet |
| 10 | `random-004` | 2-4 | 24 | 6 | +0.2160 | +0.1160 | +0.1000 | hayır |
| 11 | `random-005` | 1-6 | 9 | 2 | -0.2170 | -0.3430 | +0.1260 | hayır |
| 12 | `random-006` | 3-5 | 36 | 19 | +0.2860 | +0.2830 | +0.0030 | hayır |
| 13 | `random-007` | 5-6 | 4 | 0 | -0.1040 | -0.2650 | +0.1610 | hayır |
| 14 | `random-008` | 2-3 | 28 | 13 | -0.0360 | -0.1920 | +0.1560 | hayır |
| 15 | `random-009` | 3-5 | 1 | 0 | +0.2560 | +0.2560 | +0.0000 | evet |
| 16 | `random-010` | 4-5 | 31 | 15 | +0.4310 | +0.1370 | +0.2940 | hayır |
| 17 | `random-011` | 3-5 | 26 | 6 | -0.1610 | -0.5940 | +0.4330 | hayır |
| 18 | `random-012` | 2-6 | 1 | 0 | +0.3970 | +0.3970 | +0.0000 | evet |
| 19 | `random-013` | 1-3 | 6 | 5 | -0.0730 | -0.0730 | +0.0000 | evet |
| 20 | `random-014` | 1-2 | 1 | 0 | +0.3990 | +0.3990 | +0.0000 | evet |
| 21 | `random-015` | 1-5 | 5 | 2 | -0.1150 | -0.1570 | +0.0420 | hayır |
| 22 | `random-016` | 5-6 | 1 | 0 | +0.2640 | +0.2640 | +0.0000 | evet |
| 23 | `random-017` | 2-3 | 26 | 24 | -0.1460 | -0.2660 | +0.1200 | hayır |
| 24 | `random-018` | 2-5 | 45 | 19 | +0.9390 | +0.4970 | +0.4420 | hayır |
| 25 | `random-019` | 1-5 | 6 | 1 | +0.3190 | -0.0880 | +0.4070 | hayır |
| 26 | `random-020` | 1-2 | 41 | 1 | +0.6600 | +0.2840 | +0.3760 | hayır |
| 27 | `random-021` | 3-4 | 17 | 14 | -0.1540 | -0.6590 | +0.5050 | hayır |
| 28 | `random-022` | 2-4 | 8 | 2 | +0.7600 | +0.7600 | +0.0000 | evet |
| 29 | `random-023` | 1-5 | 17 | 6 | +0.6030 | +0.6010 | +0.0020 | hayır |
| 30 | `random-024` | 1-2 | 10 | 7 | +0.0790 | +0.0790 | +0.0000 | evet |
| 31 | `random-025` | 1-5 | 1 | 0 | +0.4540 | +0.4540 | +0.0000 | evet |
| 32 | `random-026` | 3-4 | 7 | 2 | -0.3710 | -0.3710 | +0.0000 | evet |
| 33 | `random-027` | 3-6 | 15 | 14 | +0.9880 | +0.5070 | +0.4810 | hayır |
| 34 | `random-028` | 2-6 | 3 | 2 | -0.5760 | -0.8880 | +0.3120 | hayır |
| 35 | `random-029` | 3-5 | 16 | 2 | -0.3850 | -0.3850 | +0.0000 | evet |
| 36 | `random-030` | 3-5 | 32 | 19 | +0.9820 | +0.9820 | +0.0000 | evet |
| 37 | `random-031` | 1-2 | 49 | 32 | +0.9970 | +0.7530 | +0.2440 | hayır |
| 38 | `random-032` | 2-6 | 4 | 0 | -0.0260 | -0.0260 | +0.0000 | evet |
| 39 | `random-033` | 1-5 | 20 | 2 | -0.5570 | -0.8960 | +0.3390 | hayır |
| 40 | `random-034` | 1-3 | 42 | 41 | +0.7180 | +0.3810 | +0.3370 | hayır |
| 41 | `random-035` | 3-5 | 4 | 2 | -0.1060 | -0.2320 | +0.1260 | hayır |
| 42 | `random-036` | 3-5 | 41 | 12 | +0.3200 | -0.0300 | +0.3500 | hayır |
| 43 | `random-037` | 3-3 | 5 | 1 | +0.3540 | +0.0180 | +0.3360 | hayır |
| 44 | `random-038` | 1-6 | 8 | 0 | +0.0240 | -0.0500 | +0.0740 | hayır |
| 45 | `random-039` | 4-4 | 17 | 12 | +0.3150 | -0.2450 | +0.5600 | hayır |
| 46 | `random-040` | 2-4 | 1 | 0 | -0.2900 | -0.2900 | +0.0000 | evet |
| 47 | `random-041` | 2-6 | 20 | 0 | +0.1110 | -0.1210 | +0.2320 | hayır |
| 48 | `random-042` | 4-5 | 8 | 4 | -0.1600 | -0.2320 | +0.0720 | hayır |
| 49 | `random-043` | 3-4 | 30 | 17 | -0.0790 | -0.4490 | +0.3700 | hayır |
| 50 | `random-044` | 4-4 | 77 | 74 | +0.5350 | +0.2130 | +0.3220 | hayır |

## Notlar ve sınırlamalar

- gnubg değerlendirmesi **cubeless money game** ve 2-ply'dir; küp kararları
  ölçüme dahil değildir.
- Hamle seçimi **0-ply**'dir (arama yok). C#'taki `BackgammonSearch` 1-ply
  arama yaptığı için gerçek oyun gücü bu ölçümden daha iyi olabilir; yani ER
  bir **üst sınır** olarak okunmalıdır.
- gnubg `hint` listesi budanır (varsayılan 10 hamle) ve **0-ply**'dir; bu yüzden
  ER referansı için kullanılmaz, yalnızca `gnubgHintMove` alanında saklanır.
- 15/15 taş içermeyen veya `afterStates` listesi boş olan el yapımı referans
  vakaları ölçüm dışıdır; adları yukarıda listelenmiştir.
