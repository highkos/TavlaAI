# Faz 7-S2 — `medium` / `large` / `xlarge` çok tohumlu karşılaştırma (düzeltilmiş)

> **Bu rapor v1'i geçersiz kılar.** v1 taraması yanlış tarifle koşulmuştu:
> `policy-temperature 0,0` (R-D tarifi `0,1`) ve R-D etiketli olmayan veri
> kümesi (`capacity30k` yerine `capacity30k_rd`). v1'in `xlarge` sayıları bu
> yüzden hem R-D modeliyle hem de kendi `large`'ı ile karşılaştırılamazdı.

## 1. Yöntem

| Kalem | Değer |
|---|---|
| Veri | `ml/runs/capacity30k_rd/policy_30k_rd.npz` |
| Pozisyon / aday | 30.006 / 664.778 |
| Etiket | gnubg 2-ply, cubeless equity |
| Profil × tohum | 3 × 3 = 9 model |
| Adım / batch / lr | 5000 / 64 / 1e-3 cosine (son oran 0,1) |
| wd / patience / eval | 1e-4 / 6 / 500 |
| value / dist / rank ağırlığı | 0,5 / 0,5 / **0,0** |
| **policy-temperature** | **0,1** (liste tabanlı KL — R-D tarifi) |
| Ölçüm | gnubg 2-ply hakem, **300 vaka, `--stride 3`** |
| Faz dağılımı | contact 200 / bar 84 / race 16 (ağırlık 0,556 / 0,371 / 0,073) |

`--limit` tek başına faz yanlıdır (korpus contact → bar → race sırasında);
`--stride` bu yüzden zorunlu. `capacity_train.py`'nin `run`/`sweep` alt
komutlarına `--stride` ve `--timeout` bu iş için eklendi (testler 336–337).

## 2. Yeniden üretilebilirlik kontrolü

Yeni taramanın `large/seed0`'ı, mevcut R-D `large/seed0` modeliyle **bit-bit
aynı**:

| Ölçüt | R-D `large/seed0` | Yeni `large/seed0` |
|---|---|---|
| `valTop1` | 0,8223925358213928 | 0,8223925358213928 |
| `valValueMse` | 0,013814481634426935 | 0,013814481634426935 |
| politika ER | 0,011117 | 0,011117 |
| değer ER | 0,017263 | 0,017263 |
| search1 ER | 0,013930 | 0,013930 |

Bu, hem tarifin doğru olduğunu hem de mevcut ppg tabanının
(`−0,2445 [−0,3055; −0,1835]`) doğrudan karşılaştırılabilir olduğunu
kanıtlar.

## 3. Tohum bazında sonuçlar

| Profil | Tohum | Parametre | `valTop1` | Politika ER | Değer ER | search1 ER | corr |
|---|---|---|---|---|---|---|---|
| `medium` | 0 | 156.423 | 0,8157 | 0,011880 | 0,018250 | 0,015450 | −0,9436 |
| `medium` | 1 | 156.423 | 0,8107 | 0,012383 | 0,018237 | 0,014363 | −0,9456 |
| `medium` | 2 | 156.423 | 0,8124 | 0,013957 | 0,021637 | 0,013373 | −0,9476 |
| `large` | 0 | 642.567 | 0,8224 | 0,011117 | 0,017263 | 0,013930 | −0,9464 |
| `large` | 1 | 642.567 | 0,8181 | 0,012900 | 0,018637 | 0,013950 | −0,9482 |
| `large` | 2 | 642.567 | 0,8197 | 0,013517 | 0,019777 | 0,015240 | −0,9502 |
| `xlarge` | 0 | 1.805.319 | **0,8294** | 0,012730 | 0,017977 | 0,013533 | −0,9442 |
| `xlarge` | 1 | 1.805.319 | 0,8237 | 0,011013 | 0,018550 | 0,013550 | −0,9487 |
| `xlarge` | 2 | 1.805.319 | 0,8247 | 0,012907 | 0,017933 | 0,014493 | −0,9464 |

## 4. Profil özeti (3 tohum, ortalama ± sd)

| Profil | Parametre | Politika ER | Değer ER | search1 ER | `valTop1` |
|---|---|---|---|---|---|
| `medium` | 156.423 | 0,012740 ± 0,001084 | 0,019375 ± 0,001959 | 0,014395 ± 0,001039 | 0,8130 |
| `large` | 642.567 | 0,012511 ± 0,001246 | 0,018559 ± 0,001259 | 0,014373 ± 0,000751 | 0,8201 |
| `xlarge` | 1.805.319 | 0,012217 ± 0,001046 | 0,018153 ± 0,000344 | 0,013859 ± 0,000549 | 0,8259 |

Sıralama üç yolda da `medium` > `large` > `xlarge` (ER düşük = iyi) **ama
farklar tohum gürültüsünün içinde**: profiller arası fark %1–6, tohumlar arası
sd %8–15.

## 5. Eşleşmiş bootstrap (10.000 yeniden örnekleme, pozisyon eşleşmiş)

| Karşılaştırma | Yol | Göreli | GA | p | Anlamlı |
|---|---|---|---|---|---|
| `medium`→`large` | politika | −%1,8 | [−0,00126; +0,00081] | 0,6404 | ❌ |
| `medium`→`large` | değer | −%4,2 | [−0,00204; +0,00039] | 0,1880 | ❌ |
| `medium`→`large` | search1 | −%0,2 | [−0,00147; +0,00159] | 0,9318 | ❌ |
| `medium`→`xlarge` | politika | −%4,1 | [−0,00197; +0,00090] | 0,4600 | ❌ |
| `medium`→`xlarge` | değer | −%6,3 | [−0,00414; +0,00099] | 0,3564 | ❌ |
| `medium`→`xlarge` | search1 | −%3,7 | [−0,00201; +0,00091] | 0,4626 | ❌ |
| `large`→`xlarge` | politika | −%2,4 | [−0,00138; +0,00074] | 0,6054 | ❌ |
| `large`→`xlarge` | değer | −%2,2 | [−0,00328; +0,00169] | 0,8206 | ❌ |
| `large`→`xlarge` | search1 | −%3,6 | [−0,00164; +0,00062] | 0,3696 | ❌ |

**Dokuz karşılaştırmanın hiçbiri anlamlı değil.** Doğru tarifle kapasite
farkı **ölçülemiyor**.

> v1'de `medium`→`xlarge` için `value` p=0,0092 ve `search1` p=0,0114
> "anlamlı" çıkmıştı. O fark tarifin kendisinden geliyordu: `xlarge`
> `policy-temperature 0,0` ile eğitilince politika kafası zayıf kalıyor,
> `search1` de onu miras alıyordu. R-D tarifiyle fark kayboldu.

## 6. Karar gecikmesi (C# `MatchBench decision-latency`, 30 pozisyon, CPU)

| Profil | depth 1 p95 | depth 2 p95 |
|---|---|---|
| `medium` | 0,0667 s | 8,4087 s |
| `large` | 0,2183 s | 11,5479 s |
| `xlarge` | 0,5746 s | 32,0165 s |

## 7. Karar

**Test 96 iki bacak ister:** (a) göreli değer-ER kazancı ≥ %15 **ve**
(b) depth 2 p95 ≤ 2,0 s.

- (a): `medium`→`large` −%4,2, `medium`→`xlarge` −%6,3 → **ikisi de düştü**.
- (b): `medium` (8,41 s) dahil **hiçbir profil geçmedi**.

| Kalem | Sonuç |
|---|---|
| Katı kazanan | **yok** |
| Üretim varsayılanı | **`medium`** (değişmiyor) |
| Doğruluk kazananı | `xlarge` (üç yolda da en düşük ER, en yüksek `valTop1`) — ama fark anlamsız |
| ppg modeli | `ml/runs/capacity30k_rd_sweep/xlarge/seed0/model.onnx` |

**Yorum.** 156k → 1,8M parametre (11,5×) karşılığında ölçülebilir bir kazanç
yok. Bu "kapasite ölçeklemesi para etmiyor" değil, "**30 bin pozisyonda** para
etmiyor" demektir: 30k pozisyon 1,8M parametreyi doyurmuyor. Kapasiteyi
büyütmenin önkoşulu veriyi büyütmektir.

**ppg modeli seçimi.** `xlarge/seed0`, dokuz modelin en yüksek
**eğitim-zamanı** `valTop1`'ine sahip (0,8294). Bu ölçüt ER sonuçları
görülmeden uygulanabilir; ER'a göre tohum seçmek seçim yanlılığı olurdu
(tohum bazında ER farkları zaten gürültü içinde).

## 8. Antisimetri

Dokuz modelin hepsi −0,9502…−0,9436 aralığında; eşik |corr| ≥ 0,99.
**Kapasite bu kusuru düzeltmiyor.** Kusur mimaride, kapasitede değil.

## 9. ppg ölçümü

| Kalem | Değer |
|---|---|
| Model | `ml/runs/capacity30k_rd_sweep/xlarge/seed0/model.onnx` |
| Yol | `search1` |
| Rakip | gnubg 2-ply |
| Oyun | 4400 (2200 eşleşmiş çift), 10 işçi, tohum 2026 |
| Gerekli oyun (m = 0,1115) | 4337 → **karşılandı** |
| Taban (R-D `large/seed0`) | ppg −0,2445 [−0,3055; −0,1835], `daha-kotu` |

Sonuç koşu bitince bu bölüme işlenecek.

## 10. Açık maddeler

1. **depth 2 bütçesi.** 2,0 s sınırı bu donanımda hiçbir profilde
   sağlanmıyor. Bütçe mi gevşetilecek, yoksa depth 2 için ayrı bir donanım
   hedefi mi tanımlanacak?
2. **Antisimetri.** Kapasite çözmedi; çıkarım anı antisimetrikleştirmesi
   (ê(x) = (f(x,+1) − f(x,−1))/2) hâlâ masada.
3. **Veri ölçeği.** Kapasitenin para etmesi için 30k'nın üstüne çıkmak
   gerekiyor; hedef pozisyon sayısı belirlenmeli.
4. **`medium` üretim varsayılanı** doğruluk açısından `xlarge`'ın %6 gerisinde
   ama 8,7× hızlı (depth 1: 0,067 s vs 0,575 s). Ürün için doğru tercih bu.
