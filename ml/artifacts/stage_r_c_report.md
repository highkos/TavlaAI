# Faz 7-R — Asama R-C raporu (teshis hatti onarimlari)

Tarih: 2026-02-XX · Kapsam: `faz 7 v2.5.md` §4 Asama R-C, maddeler 1-5
Durum: **TAMAM** · Karar bekleyen: yok (R-C icinde esik degisikligi onaya sunuldu, asagida)

---

## 1. Yapilan isler

| Dosya | Durum | Ne |
|---|---|---|
| `ml/pipeline_health.py` | **degisti** | G7 cift tarafli; isaretli terminal; G5 Faz 6 bandi; `scaling_evidence` |
| `ml/learning_curve.py` | **yeni** | Ogrenme egrisi (1x/2x/4x/8x), egim + bootstrap GA, karar |
| `ml/gnubg_distill.py` | **degisti** | `paired_er_test`, `distill_verdict` yeniden yazildi, `veri-yetersiz` |
| `ml/tests/test_stage_r_c.py` | **yeni** | Test 134-138 (48 test) |
| `ml/tests/test_pipeline_health.py` | **degisti** | G5/G7 yeni bandlari, `to_dict` anahtarlari |
| `ml/tests/test_gnubg_distill.py` | **degisti** | Yeni karar semantigi, cikis kodlari 4/5 |
| `ml/tests/test_corpus2.py` | **degisti** | Test numaralari 127-132 -> **128-133** (cakisma duzeltmesi) |
| `ml/artifacts/g7_modes.json` | **yeni** | G7 dort modda olcum |
| `ml/artifacts/pipeline_health_r_c.json` / `.md` | **yeni** | Onarilmis teshis |

### 1.1 Test numarasi cakismasi (duzeltildi)

R-B'de `test_corpus2.py` Test 127-132 olarak numaralandi. Ancak
`ml/tests/test_gnubg_distill.py` **zaten** "Test 127" basligini tasiyor
(`f8b9917`'de eklendi). Yani R-B'de son test numarasi 127 degil **127**'ydi ve
R-T1 = **128** olmaliydi. Duzeltildi: `test_corpus2.py` -> Test 128-133,
R-C testleri -> Test 134-138.

---

## 2. R-C madde 1 — G7 iki modda, iki tarafli

### 2.1 Mekanizma (R-08, kanitlandi)

`ml/replay.py:terminal_value` **isaretsiz** buyukluk dondurur
(`resultPoints / cubeValue`, F6-07). `ml/td_lambda.py:td_lambda_targets` ise
**isaretli** hedef uretir (mover perspektifi, her adimda isaret doner).
`spread_from_shards` bu iki farkli buyuklugu karsilastiriyordu.

lam = 1'de hedef tam olarak `(-1)^(T-1-t) * z`'dir. Isaretsiz `z` ile
karsilastirilirsa:

```
std(hedef) = sqrt(E[z^2])          std(terminal) = std(z)
oran = sqrt(1 + (mean(z)/std(z))^2) > 1     -- YAPISAL
```

Yani 3,0227 bir "cokme" degil, bir **birim uyusmazligi**ydi.

### 2.2 Duzeltme

`pipeline_health.signed_terminal_series(z, decision_indices, n_decisions)`
eklendi; `spread_from_shards` artik isaretli terminal kullanir. Eski (hatali)
karsilastirma `legacyRatio` alaninda **kayit icin** tutulur.

### 2.3 Olcum — dort mod

Shard: `ml/runs/stage_d_l2/shards/it1/it1_0000.bgsp.gz` (627 737 ornek),
model: `ckpt_v15.pt`.

| Mod | Oran (isaretli) | Eski oran (isaretsiz) | Hedef std | Terminal std | Sonuc |
|---|---|---|---|---|---|
| lam=1, model **yok** | **1,000000** | 2,8781 | 1,4839 | 1,4839 | GECTI |
| lam=1, model **var** | **1,000000** | 2,8781 | 1,4839 | 1,4839 | GECTI |
| lam=0,7, model **yok** | 0,176031 | 0,5066 | 0,2612 | 1,4839 | **DUSTU** (gercek cokme) |
| lam=0,7, model **var** | 0,682135 | 1,9633 | 1,0122 | 1,4839 | GECTI |

**Okuma:**

* lam=1'de oran **tam olarak 1** — hedefler terminal degerlerin kopyasidir.
  Bu, R-T8'in (Test 135) dogrulamasidir.
* lam=0,7 + model yok: hedefler `-(0,3*0 + 0,7*y_next)` ile sifira coker ->
  oran 0,176. Kapi bunu **dogru** yakalar.
* lam=0,7 + model var: model `V_hat` hedefleri tasir -> oran 0,682, bantta.
* Eski (isaretsiz) olcum her satirda **sismis**; 3,0227'nin kaynagi budur.

### 2.4 Yeni bant

`TARGET_STD_RATIO_MIN = 0,5`, `TARGET_STD_RATIO_MAX = 1,5` (kapali aralik).
Etiket: `Hedef sacilimi [0,5; 1,5]`.

> **ONAY GEREKIYOR (Kural 2):** ust sinir 1,5 yeni bir esiktir. Gerekce:
> TD(lam) hedefleri terminal degerlerin yumusatilmis halidir, bu yuzden
> oran <= 1 beklenir; 1,5 ustu, hedeflerin terminal degerlerden **daha genis**
> oldugu anlamina gelir ve bu ancak bir birim/isaret hatasiyla olusur.
> Onaylanmazsa kapi tek tarafli (>= 0,5) kalir; o durumda 3,0227 gibi bir
> deger yine **gizlenir**.

---

## 3. R-C madde 2 — G5 onaylanmis banda dondu

`Faz 6 v3.md` §6.3 ve §13.2: **`0,7 <= oran <= 1,4`**. Kodda `0,85-1,15`
vardi; bu bandin **hicbir belgede gerekcesi yok** (R-09).

| Bant | 1,3371 | 2,78 (Faz 5) |
|---|---|---|
| Faz 6: [0,7; 1,4] | **GECTI** | DUSTU |
| Faz 7 siki: [0,85; 1,15] | DUSTU | DUSTU |

Karar: **Faz 6 bandi geri getirildi**; siki bandin sonucu `note` alaninda
raporlanir (`siki bant [0,85; 1,15] ile: DUSTU`). Iki bant da her raporda
gorunur.

---

## 4. R-C madde 3 — `distill_verdict` yeniden yazildi

### 4.1 Eski hata (R-07)

```python
if er_after <= target:          # <-- NOKTa TAHMINI, GA yok
    return VERDICT_PIPELINE
...
return VERDICT_CAPACITY         # <-- etiketler ise yaramadi => kapasite (?)
```

Iki kusur: (a) nokta tahmini kanit sayiliyordu (Kural 3 ihlali);
(b) "etiketler ise yaramadi" -> "dar bogaz kapasite" cikarimi **mantiksal
olarak gecersiz** (olumsuzluktan olumlu iddia).

### 4.2 Yeni sozlesme

`paired_er_test(before, after)` — eslesmis fark **ve** `er_after`in mutlak
bootstrap %95 GA'si (20 000 yeniden ornekleme).

`distill_verdict(er_before, er_after, *, target, min_gain, paired, required_n)`:

| Kosul | Etiket |
|---|---|
| olcum eksik / sonlu degil | `bilinmiyor` |
| `paired` yok | `belirsiz` |
| `n < required_n` | **`veri-yetersiz`** (yeni) |
| `paired.ciHighAfter <= target` | `pipeline` |
| GA sifiri disliyor **ve** `meanDiff > 0` | `kismi` |
| aksi halde | `belirsiz` |

`VERDICT_CAPACITY` **artik uretilmez**; sabit yalnizca eski artifact'lari
okumak icin durur ve metni "Kaldirildi" diye baslar.

CLI cikis kodlari: 0 `pipeline`/`kismi`, 3 `bilinmiyor`, 4 `belirsiz`,
**5 `veri-yetersiz`**.

---

## 5. R-C madde 4 — `ml/learning_curve.py`

Ayni hat, ayni tohum, **yalnizca veri hacmi** degisir: N, 2N, 4N, 8N.

Her noktada: ER (uc yol), kalibrasyon egimi/MAE, **in-sample** ve **held-out**
kayip (ayri alanlar — Kural 5).

Egim: ER'nin `log2(veri)` basina degisimi, OLS. GA **pozisyon duzeyinde**
yeniden ornekleme ile (20 000). Karar:

| Kosul | Karar |
|---|---|
| `gainCiLow >= eps` | `olcek` |
| `gainCiHigh < eps` | `pipeline` |
| aksi halde | `belirsiz` |

`gain = -slope` (pozitif = veri arttikca ER dusuyor). `eps = 0,005`.

`CurveReport.scaling_summary()` dogrudan
`pipeline_health.diagnose(scaling=...)`e beslenir; `scaling_evidence`
`yok | egim<eps | egim>=eps` uretir.

> **Not (durustluk):** gercek egitim hatti bu modula **henuz baglanmadi**.
> `main()` bilerek `SystemExit` atar. Gercek kosum R-D'de (ayni hat, ayni
> tohum) yapilacak; o zamana kadar `scaling_evidence = yok`.

---

## 6. R-C madde 5 — `scaling_evidence` alani

`HealthReport.scaling_evidence` + `scaling_note` + `to_dict()["scalingEvidence"]`.
CLI: `--scaling <json>`.

`yok` **"olcek ise yaramaz" demek degildir**; "olculmedi" demektir. Markdown
raporu bunu acikca yazar.

---

## 7. Onarilmis teshis

`ml/artifacts/pipeline_health_r_c.json`:

| Kapi | Etiket | Deger | Sonuc | Once |
|---|---|---|---|---|
| G1 | PipBot kazanma orani >= 0,90 | 0,9950 | GECTI | GECTI |
| G2 | Kalibrasyon egimi [0,85; 1,15] | 0,6743 | **DUSTU** | DUSTU |
| G3 | Kalibrasyon MAE < 0,15 | 0,2683 | **DUSTU** | DUSTU |
| G4 | Korelasyon > 0,90 | 0,9016 | GECTI | GECTI |
| G5 | Std orani [0,7; 1,4] (Faz 6) | 1,3371 | **GECTI** | DUSTU (yanlis bant) |
| G6 | 2-ply ER < 0,02 | 0,0740 | **DUSTU** | DUSTU |
| G7 | Hedef sacilimi [0,5; 1,5] | 1,0000 | **GECTI** | GECTI (yanlis olcum) |

Teshis: **`pipeline`** (degismedi), ama artik **uc** gercek ariza var:
kalibrasyon egimi, kalibrasyon MAE, ER. Onceki raporda G5 ve G7 de "dusen"
gorunuyordu; ikisi de **olcum hatasiydi**, gercek ariza degil.

---

## 8. Testler

| Test | Ad | Dosya | Durum |
|---|---|---|---|
| 134 | `G7_TwoSided` (+ G5 Faz 6 bandi) | `test_stage_r_c.py` | YESIL |
| 135 | `G7_Lambda1_RatioIsOne` | `test_stage_r_c.py` | YESIL |
| 136 | `Verdict_PairedFirst` | `test_stage_r_c.py` | YESIL |
| 137 | `Verdict_NoCapacityInference` | `test_stage_r_c.py` | YESIL |
| 138 | `LearningCurve_Runs` | `test_stage_r_c.py` | YESIL |

`pytest ml/tests` -> **1219 passed, 3 skipped** (1222 toplandi; R-B'de 1159).

---

## 9. Acik noktalar

1. **G7 ust siniri (1,5) onay bekliyor** (Kural 2).
2. **Gercek ogrenme egrisi kosulmadi.** `learning_curve` altyapisi hazir ama
   egitim hatti R-D'de baglanacak. O zamana kadar `scaling_evidence = yok`.
3. **`er_paths.search1` Python, C# `BackgammonSearch` degil** — parite
   kanitlanmadi (R-B'den devir).
4. **`er_paths.terminal_equity`** (gammon/backgammon) C# `IsGameOver` ile
   dogrulanmadi.
5. **R-02 (deger damitma hatti yanlis tasarim)** R-D'de duzeltilecek; bu
   yuzden `distill_verdict` su an yalnizca **politika** kolu icin anlamli.
6. **R-03/R-06 (in-sample metrikler)** R-D'de held-out'a tasinacak.
7. **R-17 (maskelenmemis adaylar)** R-D'de maskeleme ile cozulecek.
8. **F7-55 (model antisimetrik degil)** R-D'de girdi-vektoru perspektif
   artirmasi ile cozulecek.
9. **R-Q1 (GPL)**, **R-Q2 (hint 6 olasiligi)**, **R-Q5 (G7 lam/terminal
   birimi)** hala acik. R-Q5 bu asamada **kismen** yanitlandi: birim
   uyusmazligi kanitlandi ve duzeltildi; hangi lam'in kullanildigi hala
   belirsiz (varsayilan 1,0).
10. **`degisenler.zip`** hala izlenmiyor; silinmeli veya `.gitignore`'a
    eklenmeli.

---

## 10. Sonraki asama

**R-D — gnubg ogretmen hatti yeniden tasarimi.** Onkosul: bu raporun onayi.
R-D'de yapilacaklar: tek ornek = pozisyon + **tum** etiketli adaylar; liste
tabanli politika kaybi (KL, maskeleme, T VAL'de); deger kaybi yalnizca
afterstate vektorlerinde; eski (yanlis) deger hatti kaldirilir; oyun bazli
bolunme; held-out raporlama; sabit-epoch/degisken-veri deneyi; fine-tune vs
sifirdan; erken durdurma.
