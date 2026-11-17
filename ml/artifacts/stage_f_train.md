# Faz 6 — Aşama D: ölçekli eğitim raporu

**Kapsam (Faz 6 v3 §8, §12.4):** 6 çıktılı kafayla **vektör TD(λ)** eğitim döngüsü,
kapasite/AMP kararlarının ölçülmesi, determinizm ve devam-ettirme garantileri, ve
L0/L1/L2/L3 eğitim merdiveninin **ölçülen** sonuçları.

**Kabul kriteri (v3 §12.4, v3-DÜZELTME satır 802–804):** ER < 0,02 bir **kapı değil,
hedeftir**. Aşama D kabulü: "L1/L2/L3 hedefleri raporlanır; ulaşılan/ulaşılamayan
değerler `stage_f_train.md`'ye yazılır; sapma analizi yapılır." Bu belge tam olarak
bunu yapar.

| Kabul maddesi | Durum | Kanıt |
|---|---|---|
| Vektör TD(λ) döngüsü çalışır | ✅ | §2, Test 71a/72 |
| Kapasite kazancı ölçülür (Test 68) | ✅ | §9.1 — `medium` seçildi |
| AMP kazancı ölçülür (Test 70) | ✅ | §10.1 — FP32 seçildi |
| Eğitim CPU'da bit düzeyinde tekrarlanabilir (Test 71a) | ✅ | §10 |
| Checkpoint devam ettirme birebir (Test 72) | ✅ | §10 |
| En iyi model VAL-ER ile seçilir (Test 73) | ✅ | §10 |
| TEST-ER erişimi loglanır (Test 74) | ✅ | §10 |
| L0 koşusu | ✅ | §4 — TEST-ER **0,1429** |
| L1 koşusu | ✅ | §5 — TEST-ER **0,0708** (hedef < 0,10 ✅) |
| L2 koşusu | ✅ | §6 — TEST-ER **0,0490** (hedef < 0,05 ✅, ama VAL-ER kazancı anlamsız) |
| L3 koşusu | ⏭️ | §7 — hesap bütçesi; maliyet tahmini verildi |
| Sapma analizi | ✅ | §9 |

---

## 1. Ne inşa edildi

| Dosya | Görev |
|---|---|
| `ml/train_v2.py` | 6 çıktılı kafayla vektör TD(λ) eğitim döngüsü (~1 230 satır) |
| `ml/tests/test_stage_d.py` | Test 68, 69, 70, 71a, 71b, 72, 73, 74 + 3 birim testi |
| `ml/replay.py` | `non_terminal_vectors` takma adı (vektör zinciri için) |
| `ml/gnubg_er.py` | `OnnxScorer` `output_version = 2` desteği (`probs` çıktısı) |
| `ml/config.yaml` | `train.lam` 0,7 → **1,0** (F6-19) |
| `Backgammon.SelfPlay/ShardWriter.cs` | Toplu float yazımı (F6-21) |
| `ml/tests/conftest.py` | `slow` işaretçisi kaydı |

`train_v2.py` Faz 4'ün `train.py`'sini **değiştirmez**; self-play'i ondan devralır
(`run_selfplay`) ve yalnızca değer kafası, hedef zinciri ve ölçüm katmanını yeniler.
Böylece Faz 4'ün skaler döngüsü bozulmadan kalır.

### 1.1 CLI

```
--config --out --profile --iterations --games --steps --depth --max-root --max-inner
--selfplay-threads --device --amp --seed --lam --lr --c-policy --c-cal
--resume --init-from --buffer-games --no-selfplay --shard-dir
--val-er-every --val-er-cases --val-er-plies --test-er --test-er-cases
--torch-threads --probe-size --probe-policy-size --no-deterministic --quiet
```

### 1.2 Çıktılar

`metrics.jsonl` (iterasyon başına bir JSON satırı, `sort_keys=True`, NaN/Inf → `null`),
`timings.jsonl`, `best.json`, `test_access.log` (yalnızca ekleme; `label: primary |
exploratory`), `train_report.json`, `probe.npz`, `onnx/model_v{N}.onnx`,
`checkpoints/ckpt_v{N}.pt`, `shards/it{N}/`.

---

## 2. Vektör TD(λ): işaret çevrimi yerine sınıf-yarısı takası (F6-17)

Faz 4'ün skaler zinciri `y[t] = -((1-λ)·V[t+1] + λ·y[t+1])` idi. Altı sınıflı dağılımda
"`-V`"nin karşılığı **işaret çevrimi değil**, sınıf yarılarının takasıdır:

```
flip([W, GW, BW, L, GL, BL]) = [L, GL, BL, W, GW, BW]
y[n-1] = flip(z_terminal)
y[t]   = flip((1-λ)·p̂[t+1] + λ·y[t+1])
```

`flip` bir **involusyondur** (`flip(flip(p)) == p`). Bu yüzden `λ = 1,0`'da zincir
`flip^k(z)`'ye indirgenir ve `flip² = id` olduğu için sonuç **tam olarak** oyuncu bakış
açısından tek-sıcak Monte Carlo hedefidir. F6-07'deki işaret hatasının vektör karşılığı
böylece **yapısal olarak imkânsız** hâle gelir: `flip` uygulanmazsa `λ = 1,0` hedefi
rakip bakış açısından yazılır ve `test_vector_td_lambda_one_equals_monte_carlo` kırmızı
olur. Altı `(winner, result_type)` kombinasyonunun tamamı doğrulanmıştır.

**Hız notu.** `λ ≥ 1,0` iken `build_exclusive_samples` ileri geçişi **tamamen atlar**
(zincir ağa bağlı değildir). L0/L1/L2'nin tamamı `λ = 1,0` ile koştuğu için bu, hedef
üretimini iterasyon başına belirgin biçimde kısaltır.

---

## 3. İki probe: TD probe ve ağdan bağımsız MC probe (F6-19)

| Probe | Hedefler | Ne ölçer | `--resume` |
|---|---|---|---|
| `probe_value` (TD) | 1. iterasyonun **zayıf** modelinden dondurulmuş | "ilk modelden ne kadar uzaklaştık" | `probe.npz` |
| `probe_mc` (MC) | `λ = 1,0`, **ağdan bağımsız** tek-sıcak | gerçek öğrenme eğrisi | `probe.npz` |

Dondurulmuş TD probe'un hedefleri modelden geldiği için model ilerledikçe **yanıltıcı
biçimde kötüleşir** (L0'da `probe_ce` 1,1991 → 1,0451 görünür ama `probe_policy_loss`
2,2792 → 3,6167'ye çıkar). Faz 4 bu sorunu `probe_mc` ile çözmüştü; `train_v2.py`'nin
ilk sürümünde bu alan eksikti ve L0'un ilk koşusunda `probe_ce`'nin 1,66 → 1,76
kötüleşmesi yanlış yorumlanmaya açıktı. MC probe eklendi.

> **Dürüst sınır.** MC probe'un **hedefleri** ağdan bağımsızdır ama **durum dağılımı**
> değildir: 1. iterasyonun buffer'ından örneklenir. Model kendi dağılımını değiştirdikçe
> (oyunlar kısalır, pozisyonlar farklılaşır) sabit probe kümesi dağılım-dışı kalır. L1'de
> bu etki görünür: `probe_mc_ce` 0,9726 → 1,0276 **kötüleşirken** VAL-ER 0,0877 → 0,0658
> **iyileşti**. İkisi çelişmez; farklı soruları yanıtlarlar. Gerçek kalite ölçüsü
> VAL-ER/TEST-ER'dir (gnubg, sabit 200 pozisyonluk korpus).

---

## 4. L0 — harness doğrulaması

**Tarif.** 20 iterasyon × 500 oyun, `small` (37 127 parametre), `depth 0`, CPU, seed 1,
`λ = 1,0`, 200 adım/iterasyon. **Süre 2 062 s (34,4 dk).**

| Metrik | İlk | Son |
|---|---|---|
| buffer CE | 1,1958 | **1,0197** |
| buffer equity MAE | 1,2476 | **0,9018** |
| buffer kalibrasyon eğimi | 0,99997 | 1,0076 |
| buffer politika kaybı | 2,2937 | **1,6114** |
| düzgün politika bazı | 2,2939 | 2,0497 |
| buffer hedef entropi oranı | 0,9990 | 0,5599 |
| MC CE | 1,1901 | **1,0387** |
| MC equity MAE | 1,2379 | 1,0685 |
| MC kalibrasyon eğimi | 1,0084 | 1,0247 |

| VAL-ER | it5 | it10 | it15 | it20 |
|---|---|---|---|---|
| 20 pozisyon | 0,2425 | 0,2738 | 0,1611 | **0,1550** |

**TEST-ER: 0,1429** (20 pozisyon, `primary`, tek erişim).

**Yorum.** L0 bir **harness doğrulamasıdır**, güç iddiası değil: `small` profil ve
500 oyun/iterasyon kasıtlı olarak küçüktür. Yine de Faz 5 taban çizgisini (ER 0,1941)
**%26** geçer — yani 6 çıktılı kafa + vektör TD(λ) + işaret hatası düzeltmesi (F6-07)
tek başına ölçülebilir kazanç üretir. Kalibrasyon eğimi 1,0000 → 1,0076: model
**aşırı güvenli değil**, bu Faz 5'in 2,78 std-oranıyla taban tabana zıttır.

---

## 5. L1 — `medium`, ısıtmalı

**Tarif.** 30 iterasyon × 2 000 oyun, `medium` (156 423 parametre), `depth 0`, CPU,
seed 7, `λ = 1,0`, 300 adım/iterasyon, 4 self-play iş parçacığı,
`--buffer-games 12000`, `--init-from ml/runs/stage_d_boot/checkpoints/ckpt_v3.pt`.
**Süre 3 660 s (61,0 dk).**

| Metrik | İlk | Son |
|---|---|---|
| buffer CE | 0,9700 | **0,9350** |
| buffer equity MAE | 0,8813 | **0,8236** |
| buffer kalibrasyon eğimi | 1,0205 | **1,0015** |
| buffer politika kaybı | 1,1343 | 1,1545 |
| düzgün politika bazı | 2,0521 | 2,0628 |
| buffer hedef entropi oranı | 0,5309 | 0,5052 |
| MC CE | 0,9726 | 1,0276 |
| MC equity MAE | 0,8922 | 0,9172 |
| MC kalibrasyon eğimi | 1,0119 | 0,9965 |

| VAL-ER | it5 | it10 | it15 | it20 | it25 | it30 |
|---|---|---|---|---|---|---|
| 40 pozisyon | 0,0877 | 0,1000 | 0,0828 | 0,0943 | 0,0706 | **0,0658** |
| standart hata | 0,0221 | 0,0321 | 0,0195 | 0,0200 | 0,0169 | 0,0169 |

**TEST-ER: 0,0708** (40 pozisyon, `primary`, tek erişim).

**Yorum.** L1 hedefi ER < 0,10 idi; **ulaşıldı** (VAL-ER 0,0658, TEST-ER 0,0708).
Faz 5 taban çizgisine göre **2,74×** iyileşme. Kalibrasyon eğimi 1,0015 — neredeyse
kusursuz. Politika kaybı 1,1343 → 1,1545 **hafif kötüleşti**; sebep §9.4'te.

**Ölçüm gürültüsü uyarısı.** 40 pozisyonun standart hatası **0,017–0,032**'dir; bu
yüzden it5 → it30 düşüşü (0,0877 → 0,0658) **tek başına** anlamlı değildir. Anlamlı
olan, L1'in Faz 5 tabanından (0,1941) **çok** uzakta olmasıdır — o fark 4 standart
hatanın üzerindedir. L1 ile L2 arasındaki fark ise bu eşiğin altındadır (§6).

**Isınma zorunluluğu (F6-20).** İlk L1 denemesi sıfırdan rastgele ağırlıkla koşuldu ve
2 000 oyunun **1 584'ü (%79,2)** `--max-plies 500` sınırında iptal oldu: eğitilmemiş
politika neredeyse sabit olduğu için ajan hep aynı adayı seçiyor, oyun ilerlemiyordu.
Isınma sonrası iptal **0**, karar/oyun 454,8 → 65,7, shard 251 MB → 26,9 MB, tepe
bellek 8,5 GB → 1,1 GB. Bu yüzden `--init-from` kural hâline getirildi.

---

## 6. L2 — `medium`, 10⁴ oyun/iterasyon

**Tarif.** 30 iterasyon × 10 000 oyun, `medium`, `depth 0`, CPU, seed 11, `λ = 1,0`,
300 adım/iterasyon, 4 self-play iş parçacığı, `--buffer-games 20000`,
`--init-from ml/runs/stage_d_l1/checkpoints/ckpt_v30.pt`.
**Süre 11 761 s (196,0 dk)**, iterasyon başına ortalama **392,0 s**
(75,0 s self-play + 50,5 s hedef + 26,8 s eğitim + ~240 s ölçüm/kayıt/ONNX).
Süreye 20. iterasyondan sonraki oturum kesintisinden dönüş için harcanan
~40 dk'lık tampon yeniden kurma da dâhildir (§6.1).

| Metrik | İlk (it1) | Son (it30) |
|---|---|---|
| buffer CE | 0,9690 | **0,9182** |
| buffer equity MAE | 0,8562 | **0,8093** |
| buffer kalibrasyon eğimi | 0,9992 | **0,9851** |
| buffer politika kaybı | 1,1161 | 1,0928 |
| düzgün politika bazı | 2,0723 | 2,0697 |
| MC CE | 0,9787 | 0,9892 |
| MC equity MAE | 0,8627 | 0,8590 |

| VAL-ER | it5 | it10 | it15 | it20 | it25 | it30 |
|---|---|---|---|---|---|---|
| 40 pozisyon | 0,0755 | 0,0744 | **0,0619** | 0,0669 | 0,0792 | 0,0678 |
| standart hata | 0,0195 | 0,0200 | 0,0160 | 0,0184 | 0,0194 | 0,0175 |

**En iyi model (VAL-ER):** `ckpt_v15.pt`, VAL-ER **0,0619** (`best.json`).

**TEST-ER: 0,0490** (40 pozisyon, `primary`, tek erişim, `model_v30`).

**Yorum — dikkatli okunmalı.** İki sayı iki farklı modeli anlatır:

* TEST-ER **0,0490**, koşunun **son** modeli (`model_v30`, VAL-ER 0,0678) üzerinde
  ölçüldü — `train_v2.py` TEST-ER'i her zaman son checkpoint'te ölçer (§1.2).
  Bu değer < 0,05 hedefinin **altındadır**.
* VAL-ER eğrisi ise **tekdüze değildir**: 0,0755 → 0,0744 → 0,0619 → 0,0669 →
  0,0792 → 0,0678. 40 pozisyonun standart hatası **0,016–0,020** olduğu için bu
  salınımın tamamı **gürültü**dür. L1'in VAL-ER'i 0,0658 idi; L2'nin en iyisi 0,0619.
  Fark **0,0039**, yani standart hatanın **~0,2 katı** — **istatistiksel olarak
  anlamsız**.

**Dolayısıyla dürüst sonuç:** L2, oyun/iterasyon sayısını L1'e göre **5×** artırmasına
rağmen ER'de **ölçülebilir bir kazanç üretmedi**. ER ~0,06–0,07 bandında
**plato** yapmıştır. TEST-ER'in 0,05 altına düşmesi bu platonun çürütülmesi değildir;
40 pozisyonluk test kümesinin çözünürlüğü (SE ≈ 0,017) 0,01 mertebesindeki farkları
ayırt edemez. Sapma analizi §9.1'de.

### 6.1 Devam ettirme maliyeti (ölçülen)

L2, 20. iterasyonda bir oturum kesintisiyle durdu ve `--resume` ile sürdürüldü.
Devam yolu, `buffer_shard_dirs` içindeki **20 shard dizinini** (20 × 10 000 oyun,
~2,4 GB gzip) baştan okuyup tamponu yeniden kurar. Bu **~40 dk** sürdü ve
`ReplayBuffer.add_shard_dir`'ın `max_games` sınırını **okuma sırasında**
uygulamamasından kaynaklanır: 200 000 oyunun tamamı ayrıştırılır, sonra FIFO
kırpılır. Sonuç **doğru** (Test 72 birebir devamı doğrular) ama **pahalıdır**.
İyileştirme önerisi Aşama E'ye bırakılmıştır: devam yolunda yalnızca son `N`
shard dizinini okumak (FIFO sırası zaten kronolojiktir).

---

## 7. L3 — koşulmadı

**Tarif (v3 §8.4).** 10⁵ oyun/iterasyon × 50 iterasyon, `medium`, hedef ER < 0,02.

**Maliyet tahmini (ölçülen hızdan).** L2'de iterasyon başına 10 000 oyun **392,0 s**
(75,0 s self-play + 50,5 s hedef + 26,8 s eğitim + ~240 s ölçüm/kayıt/ONNX).
10⁵ oyun/iterasyon ≈ **2 900 s/iterasyon** (self-play 750 s, hedef 505 s, eğitim 27 s,
ölçüm ~1 600 s). 50 iterasyon ≈ **40 saat** kesintisiz CPU. Bu, tek oturumluk bir bütçe
değildir; Ek A (Evren/H200) açıldığında Track H'ye devredilecek ilk iştir.

**L3'ün tarifi değişmelidir.** L2'nin ölçülmüş sonucu (§6) şunu söyler: **yalnızca
ovun sayısını artırmak ER'yi düşürmüyor.** Bu yüzden L3, v3 §8.4'teki gibi sadece
10⁵ oyun/iterasyon değil, aynı anda **`depth 1` veri üretimi** ve **daha büyük
VAL/TEST kümeleri** (en az 200 pozisyon, SE ≈ 0,008) kullanmalıdır. Aksi hâlde
40 saatlik bütçe, ölçülemeyen bir fark üretir. Gerekçe §9.1'de.

---

## 8. Hedef vs ulaşılan

| Koşu | Profil | Oyun/iter | İter | Süre | Hedef ER | VAL-ER | TEST-ER | Durum |
|---|---|---|---|---|---|---|---|---|
| L0 | `small` | 500 | 20 | 34,4 dk | — (harness) | 0,1550 | **0,1429** | ✅ |
| L1 | `medium` | 2 000 | 30 | 61,0 dk | < 0,10 | 0,0658 | **0,0708** | ✅ |
| L2 | `medium` | 10 000 | 30 | 196,0 dk | < 0,05 | 0,0619 | **0,0490** | ⚠️ TEST ✅ / VAL-ER kazancı anlamsız |
| L3 | `medium` | 100 000 | 50 | ~40 sa (tahmin) | < 0,02 | — | — | ⏭️ koşulmadı |
| Faz 5 taban | — | — | — | — | — | — | 0,1941 | — |

**Toplam iyileşme (L2 vs Faz 5):** 0,1941 → 0,0490 = **3,96×** (TEST-ER);
VAL-ER üzerinden 0,1941 → 0,0619 = **3,14×**.

**Ölçüm çözünürlüğü uyarısı.** L1 ve L2'nin VAL-ER'leri 40 pozisyon üzerinde
ölçüldü; standart hata **0,016–0,020**'dir. Yani bu tablodaki 0,0658 ile 0,0619
arasındaki fark **ölçülemez**. L1 → L2 geçişinin "kazanç" olarak okunmaması
gerekir; tek söylenebilecek şey **plato**dur.

---

## 9. Sapma analizi

### 9.1 ER neden ~0,06'da plato yapıyor

Dört aday sebep ölçüldü:

1. **Kapasite değil.** Test 68 aynı veriyle `medium` (ER 0,3535 ± 0,0712) ve `large`
   (ER 0,2651 ± 0,0594) profillerini karşılaştırdı. Fark **0,0884**, eşik **0,0927**
   (`1,0·√(se²+se²)`) — yani kazanç **istatistiksel olarak anlamlı değil**. Karar:
   `medium` kalır. `large`'a geçmek platoyu kırmaz.
2. **Veri hacmi (bu turda ölçüldü ve elendi).** L1 → L2 oyun/iterasyon **5×** arttı
   (2 000 → 10 000), tampon 12 000 → 20 000 oyuna çıktı, toplam deneyim
   ~60 000 → ~300 000 oyuna ulaştı. Buna rağmen VAL-ER **0,0658 → 0,0619** (fark
   standart hatanın 0,2 katı). Yani **bu ölçekte hacim artık kaldıraç değildir.**
   Bu, v3 §8.4'ün "daha çok oyun → daha iyi ER" varsayımının **ölçümle
   çürütüldüğü** noktadır ve Aşama D'nin en önemli bulgusudur.
3. **Öğretmen kalitesi (asıl darboğaz).** Politika `--sel-temp 0,05` ile üretilen
   **kendi** aramasını taklit eder; arama `depth 0` olduğu için öğretmen de zayıftır.
   `buffer_policy_loss` L1'de 1,1343 → 1,1545, L2'de 1,1161 → 1,0928; düzgün baz
   ~2,07, yani politika bazın **%47 altında** ama **durgun**. Değer kafası da aynı
   öğretmenden beslenir: `buffer_ce` 0,9690 → 0,9182 ile iyileşirken VAL-ER
   düşmüyor — bu, **eğitim hedefinin kendisinin** doğruluk sınırı olduğunun
   işaretidir. `depth 1` veri üretimi Aşama C §15.6'da **56× yavaş** ölçüldü
   (1,52 vs 85,91 oyun/sn); bu yüzden L3'ün bütçesi `depth 1`'e ayrılmalıdır.
4. **Ölçüm çözünürlüğü.** 40 pozisyonluk VAL/TEST kümeleri SE ≈ 0,017–0,020 verir.
   0,01 mertebesindeki gerçek iyileşmeler bu kümeyle **görülemez**. L3 en az
   200 pozisyon (SE ≈ 0,008) kullanmalıdır; aksi hâlde 40 saatlik koşu
   ölçülemeyen bir fark üretir.

### 9.2 v3 §8.4 tarifinden bilinçli sapmalar

| v3 §8.4 | Uygulanan | Gerekçe |
|---|---|---|
| L1: 10⁴ oyun/iter, 30 iter, sıfırdan | 2 000 oyun/iter, 30 iter, **ısıtmalı** | F6-20: sıfırdan `medium` %79 iptal oyun üretir; veri boşa gider |
| L2: 5×10⁴ oyun/iter, 50 iter | 10⁴ oyun/iter, 30 iter | Hesap bütçesi: 5×10⁴ × 50 ≈ 40 sa; 10⁴ × 30 = 3,3 sa |
| L3: 10⁵ oyun/iter, 50 iter | koşulmadı | Aynı bütçe; Ek A (H200) açıldığında ilk iş |
| `depth 1` veri üretimi | `depth 0` | `depth 1` self-play 56× yavaş (Aşama C §15.6: 1,52 vs 85,91 oyun/sn) |

**Ortak sonuç.** Dört sapmanın tamamı **hesap bütçesi** kaynaklıdır, tasarım kaynaklı
değil. Hiçbiri ölçüm iddiasını zayıflatmaz: her koşu kendi tarifini `train_report.json`
içinde saklar ve `metrics.jsonl` ile yeniden üretilebilir.

### 9.3 MC probe'un kötüleşmesi

§3'te açıklandı: MC probe'un **durum dağılımı** 1. iterasyonda donar. L1/L2'de model
kendi dağılımını değiştirdikçe sabit probe dağılım-dışı kalır ve CE artar. Bu bir
**regresyon değildir**; VAL-ER aynı dönemde düşmektedir. Gelecekte MC probe'un her
5 iterasyonda yeniden örneklenmesi (ve eski probe'un korunması) düşünülebilir — bu
Aşama E'nin konusudur.

### 9.4 Politika kaybının L1'de artması

L1'de `buffer_policy_loss` 1,1343 → 1,1545 arttı. Sebep: ısınma modeli
(`stage_d_boot`) 3 iterasyonluk çok kısa bir koşudur ve politika hedefleri o modelin
**kendi** aramasından gelir. L1 ilerledikçe arama güçlenir, hedefler **keskinleşir**
(entropi oranı 0,5309 → 0,5052) ve taklit etmesi zorlaşır. L2'de aynı metrik 1,1545 →
1,0928 ile **düzelir** — yani L1'deki artış geçici bir ısınma artefaktıdır.

---

## 10. Testler

| # | Test | Tür | Durum |
|---|---|---|---|
| 68 | `Capacity_Gain_IsMeasured` | pytest | ✅ `medium` seçildi (fark 0,0884 < eşik 0,0927) |
| 69 | `TrackH_H0_Parity` | pytest | ⏭️ Ek A kapısı açılmadı (F6-18) |
| 70 | `Amp_IsMeasured` | pytest | ✅ FP32 seçildi (hız 0,16×, yani AMP 6,2× **yavaş**) |
| 71a | `Training_IsReproducible_CPU` | pytest | ✅ `metrics.jsonl` bit düzeyinde aynı |
| 71b | `Training_IsReproducible_GPU` | pytest | ✅ tolerans içinde (CUDA varsa) |
| 72 | `Checkpoint_Resume_IsExact` | pytest | ✅ kesintisiz koşuyla aynı |
| 73 | `BestModel_SelectedByValEr` | pytest | ✅ `best.json` VAL-ER ile seçilir |
| 74 | `TestAccess_IsLogged` | pytest | ✅ `test_access.log`, 2. erişim `exploratory` |
| — | `test_vector_td_lambda_one_equals_monte_carlo` | pytest | ✅ |
| — | `test_flip_is_involution` | pytest | ✅ |
| — | `test_td_lambda_zero_uses_next_state` | pytest | ✅ |

**Birleşik test durumu:** `ml/tests` **219/219** (3 yavaş/koşullu test atlanır),
`Backgammon.Tests` **256/256**, `Backgammon.Inference.Tests` **64/64**,
`Backgammon.UI.Tests` **85/85**.

### 10.1 AMP neden FP32 kaldı

`--amp` CPU'da **6,2× yavaş** (2,61 s → 16,19 s, 2 iterasyon × 8 adım). Sebep: CPU'da
`torch.autocast` `bfloat16`'ya düşer ve bu makinenin (i7-9750H, Coffee Lake) AVX-512
BF16 desteği yoktur; her çarpma yazılım emülasyonuna gider. Kayıp farkı ihmal edilebilir
(ΔCE 0,00085) ama hız kazancı **negatif**. Karar: **FP32**. GPU'da (SM ≥ 8.0) AMP
yeniden ölçülmelidir; `decide_amp` bunu otomatik yapar.

---

## 11. Yeniden üretim

```bash
# L0 — harness dogrulamasi (34 dk)
python ml/train_v2.py --out ml/runs/stage_d_l0 --profile small \
	--iterations 20 --games 500 --steps 200 --depth 0 --device cpu --seed 1 \
	--val-er-every 5 --val-er-cases 20 --test-er --test-er-cases 20

# L1 — isitmali medium (61 dk)
python ml/train_v2.py --out ml/runs/stage_d_boot --profile medium \
	--iterations 3 --games 500 --steps 500 --depth 0 --device cpu --seed 3 \
	--no-selfplay --shard-dir ml/runs/stage_d_l0/shards
python ml/train_v2.py --out ml/runs/stage_d_l1 --profile medium \
	--iterations 30 --games 2000 --steps 300 --depth 0 --device cpu --seed 7 \
	--selfplay-threads 4 --buffer-games 12000 \
	--init-from ml/runs/stage_d_boot/checkpoints/ckpt_v3.pt \
	--val-er-every 5 --val-er-cases 40 --test-er --test-er-cases 40

# L2 — 10^4 oyun/iterasyon (196 dk)
python ml/train_v2.py --out ml/runs/stage_d_l2 --profile medium \
	--iterations 30 --games 10000 --steps 300 --depth 0 --device cpu --seed 11 \
	--selfplay-threads 4 --buffer-games 20000 \
	--init-from ml/runs/stage_d_l1/checkpoints/ckpt_v30.pt \
	--val-er-every 5 --val-er-cases 40 --test-er --test-er-cases 40

# Testler
python -m pytest ml/tests/test_stage_d.py -q
```

**Not.** `ml/runs/` depoya işlenmez; yukarıdaki komutlar çıktıları yeniden üretir.
Tüm koşular `--device cpu` kullanır: CUDA bu model boyutunda **4,1× yavaştır**
(Aşama C §15.6, F6-16).
