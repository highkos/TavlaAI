# Faz 7-R / R-F — Final kanıt tanımı

**Tarih.** 2026-02. **Durum.** Tamamlandı. **Etiket.** `eşdeğerlik kanıtlanmadı`.

Bu rapor Faz 7 v2.5 §4 R-F maddelerinin çıktısıdır. Nihai iddia **üç ayrı
satırdır** ve satırlar **toplanmaz** (madde 4).

---

## Üç satırlık nihai rapor

| # | Satır | Ölçüm | Hedef | Sonuç |
|---|---|---|---|---|
| 1 | **Hamle kalitesi** | politika ER **0,0111** [0,0077; 0,0152], search1 **0,0139** [0,0101; 0,0185] (gnubg 2-ply hakem, 300 pozisyon) | gnubg 2-ply seviyesi | ❌ **Eşdeğer değil.** gnubg 0-ply 0,0062, gnubg 1-ply 0,0044 → model **gnubg 0-ply seviyesinde** |
| 2 | **Küp** | küp ER **0,0821** (3 tohum, 400 vaka) | 0,02 | ❌ **Karşılanmadı.** Hedefin **4,1 katı** |
| 3 | **Oyun gücü** | ppg **−0,2445** [−0,3055; −0,1835] (gnubg 2-ply'a karşı, 2000 oyun) | `H0: ppg_fark ≤ −m`, m = 0,1115 | ❌ **Eşdeğerlik kanıtlanmadı.** Üst sınır −0,1835 < −0,1115 → **daha kötü** |

**Rapor dili (madde 5).** "gnubg 4-ply'a göre eşdeğer" **denmez**;
"eşdeğerlik kanıtlanmadı" denir. "İnsan şampiyonu yendik" **denmez**.

---

## Madde 1 — Referans zinciri (tahmin değil, ölçüm)

Hakem kendi kendini ölçemez. İki derin hakem kullanıldı; 4-ply'ın kendi ER'si
**ölçülemez** (5-ply/rollout bu makinede yok).

### 1a. gnubg `hint` 3-ply hakem (40 pozisyon, kapsama %100)

| Oyuncu | ER | %95 GA | σ | Tam eşleşme |
|---|---|---|---|---|
| gnubg 0-ply | 0,0063 | [0,0010; 0,0135] | 0,0207 | 0,7750 |
| gnubg 1-ply | 0,0027 | [0,0005; 0,0057] | 0,0084 | 0,8250 |
| gnubg 2-ply | **0,0013** | [0,0003; 0,0027] | 0,0039 | 0,8250 |

### 1b. gnubg `hint` 4-ply hakem (20 pozisyon, kapsama %100)

| Oyuncu | ER | %95 GA | σ | Tam eşleşme |
|---|---|---|---|---|
| gnubg 0-ply | 0,0049 | [0,0002; 0,0112] | 0,0130 | 0,8000 |
| gnubg 1-ply | 0,0040 | [0,0000; 0,0092] | 0,0108 | 0,8500 |
| gnubg 2-ply | **0,0006** | [0,0000; 0,0016] | 0,0021 | 0,9000 |
| gnubg 3-ply | **0,0002** | [0,0000; 0,0006] | 0,0009 | 0,9500 |
| gnubg 4-ply | **ölçülemez** | — | — | — |

**ER çözünürlük tabanı: 0,0006–0,0013.** Bundan küçük farklar yöntem
gürültüsüdür. Modelin en iyi yolu (0,0111) tabanın **~9–18 katı**; yani
modelin ER'si gerçek sinyal, gürültü değil.

### 1c. Modelin merdivendeki yeri (gnubg 2-ply hakem, 300 pozisyon)

| Oyuncu | ER | %95 GA | σ |
|---|---|---|---|
| gnubg 0-ply | **0,0062** | [0,0040; 0,0088] | 0,0212 |
| gnubg 1-ply | **0,0044** | [0,0029; 0,0063] | 0,0153 |
| R-D `large` politika | 0,0111 | [0,0077; 0,0152] | 0,0334 |
| R-D `large` search1 | 0,0139 | [0,0101; 0,0185] | 0,0375 |
| R-D `large` değer | 0,0173 | [0,0105; 0,0264] | 0,0711 |
| R-E `large` politika | 0,0172 | [0,0119; 0,0235] | 0,0524 |
| R-E `medium` politika | 0,0189 | [0,0133; 0,0255] | 0,0546 |

**Bulgu.** Model **gnubg 0-ply'ın altında** (0,0111 vs 0,0062) ve gnubg
1-ply'ın belirgin altında. R-D kazancı gerçek (−%41 politika) ama seviye
hâlâ gnubg 0-ply'ın gerisinde.

**Bulgu (yeni).** `search1` (0,0139) **politikadan kötü** (0,0111). Sebep
değer kafası: değer ER'si 0,0173, yani en zayıf yol, ve `search1` derinlik-1
değerlendirmesini ondan alıyor. **Arama, zayıf değer kafası yüzünden
politikayı bozuyor.** Bu, R-D sonrası en önemli açık madde.

---

## Madde 2 — Rollout alt kümesi: **ölçülemez**

gnubg 1.08.003-mingw'de `rollout` komutu çalışır ve `Rollout done. Printing
final results.` basar ama **equity satırı basmaz**. Beş bağımsız deneme:

1. `rollout` + `-t` → equity yok
2. `rollout` + `-t -d` → equity yok
3. `rollout` + `-c` / `-p` → equity yok
4. `set rollout cubeful off` + `set cube use off` → equity yok
5. `set rollout trials 36` + `set rollout chequerplay plies 0` → equity yok

Ek olarak: `rollout` sonrası `eval` **statik** değerlendirmeyi döndürür;
gnubg Python API'sinde (`-p`) `rolloutcontext` var ama **`rollout` fonksiyonu
yok**; `gnubg-cli.exe --help` rollout seçeneği listelemez.

**Maliyet (ölçüldü).** 36 deneme ≈ 30 s (0-ply chequerplay, yüklü CPU) →
1296 deneme ≈ 18 dk → 200 pozisyon × 2 aday = 400 rollout ≈ **120 saat tek
çekirdek**. Ölçülemez olduğu için bu maliyet **ödenmedi**.

**Kural 6 uyarınca sıfır uydurulmadı.** Satır `ölçülemez` işaretlendi ve
yerine **ölçülebilir** karşılık kondu: madde 1'in ER çözünürlük tabanı
(0,0006–0,0013). Araç: `ml/gnubg_rollout.py` →
`ml/artifacts/gnubg_rollout.{json,md}`.

---

## Madde 3 — Oyun gücü (ppg)

Eşleştirilmiş zar + renk takası, küpsüz para oyunu, 10 paralel süreç.

| Ölçüm | Değer |
|---|---|
| Model | `ml/runs/capacity_rd/large/seed0/model.onnx`, yol `search1` |
| Rakip | gnubg **2-ply** |
| Oyun | 2000 (1000 çift) |
| Kazanma | 839/2000 = **0,4195** |
| **ppg** | **−0,2445** |
| ppg %95 GA | **[−0,3055; −0,1835]** |
| ppg standart hata | 0,0310 |
| Eşleştirilmiş fark | −0,4890 [−0,5990; −0,3770] |
| Oyun başına ply | 55,9 |
| Bitmeyen oyun | 0 |
| Süre | ~3 sa 20 dk |

**İddia testi.** `H0: ppg_fark ≤ −m`, m = **0,1115** (F7-79: gnubg 0-ply vs
2-ply = −0,2229 ppg'nin yarısı). GA'nın **üst** sınırı −0,1835, yani
−m = −0,1115'in **altında**. Sonuç: **eşdeğerlik kanıtlanmadı**; model
gnubg 2-ply'dan m'den fazla kötü.

**Güç borcu.** m = 0,1115 ve σ = 2,9960 için gereken oyun **4337**; koşulan
**2000** → güç borcu **%46**. Yine de GA sıfırı ve −m'i dışladığı için
"eşdeğer değil" hükmü sağlam; "ne kadar kötü" tahmini ±0,06 ppg
belirsizlikle okunmalı.

**Tutarlılık kontrolü (önemli).** gnubg 0-ply, gnubg 2-ply'a karşı
**−0,2229 ppg**; modelimiz **−0,2445 ppg**. İki bağımsız ölçüm (ER merdiveni
ve ppg) **aynı yeri** gösteriyor: model **gnubg 0-ply seviyesinde, biraz
altında**. Bu, ölçüm zincirinin kendi kendini doğrulamasıdır.

---

## Madde 4 — Küp ayrı satır

Küp ER'si hamle ER'si ile **toplanmaz** (madde 4). R-E raporundan:

| Koşu | Küp ER | Hedef | Oran |
|---|---|---|---|
| R-E `medium` (3 tohum) | 0,0741 | 0,02 | 3,7× |
| R-E `large` (3 tohum) | 0,0718 | 0,02 | 3,6× |
| R-D `large` (3 tohum) | **0,0821** | 0,02 | **4,1×** |

Eşleştirilmiş bootstrap'ların hiçbiri anlamlı değil (p ≥ 0,32). **Hamle
kalitesi kazancı küp kararına transfer olmuyor.** Küp, R-F'nin karşılanmayan
tek satırı değil — hamle kalitesi de karşılanmadı — ama küp **hiç**
iyileşmedi.

---

## Madde 5 — Rapor dili

- ✅ "gnubg 2-ply'a göre **eşdeğerlik kanıtlanmadı** (m = 0,1115, %95)"
- ✅ "hamle kalitesi gnubg 0-ply seviyesinde"
- ✅ "küp ER'si hedefin 4,1 katında"
- ❌ "gnubg 4-ply'a göre eşdeğer"
- ❌ "insan şampiyonu yendik"

---

## Araç ve artefaktlar

| Artefakt | İçerik |
|---|---|
| `ml/artifacts/gnubg_ladder.{json,md}` | 0/1-ply vs 2-ply hakem + model satırları (ladderVersion 2) |
| `ml/artifacts/gnubg_ladder_deep.{json,md}` | 0/1/2-ply vs `hint`@3, 40 pozisyon |
| `ml/artifacts/gnubg_ladder_deep4.{json,md}` | 0/1/2/3-ply vs `hint`@4, 20 pozisyon |
| `ml/artifacts/gnubg_rollout.{json,md}` | rollout ölçülemezlik kanıtı + maliyet |
| `ml/artifacts/ppg_rd_large_s0_2ply.{json,md}` | 2000 oyunluk ppg |
| `ml/artifacts/stage_r_e_report.{json,md}` | R-E (kapasite + küp) |
| `ml/gnubg_ladder.py` | `--deep`, `--deep-referee-plies`, `--models-only`, `--model-er` |
| `ml/gnubg_rollout.py` | rollout ölçülemezlik probu |
| `ml/vs_gnubg.py` | ppg maçı (başlık artık `--gnubg-plies`'i yansıtır) |

---

## Açık maddeler

1. **`search1` politikadan kötü** (0,0139 vs 0,0111). Değer kafası en zayıf
   yol (0,0173) ve arama onu miras alıyor. Değer hedefi değişikliği
   tartışması (kullanıcı kararı bekliyor) artık **ölçülmüş** bir gerekçeye
   sahip.
2. **Küp ER'si hiç iyileşmedi**; hamle kalitesi ile küp kararı arasındaki bağ
   kurulmadı.
3. **ppg güç borcu %46** (2000 / 4337).
4. **4-ply'ın kendi ER'si ölçülemedi** (5-ply/rollout yok).
5. **gnubg GPL lisansı** ürün dağıtımı öncesi çözülmedi (PHASES §36.10/5).
6. **`m = 0,1115` yalnızca money**; maç hücreleri (5 ve 9 puan) ayrı
   raporlanmadı.