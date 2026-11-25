# EVREN (GPU) calisma kilavuzu

Bu belge, egitimi **ucretli** EVREN GPU platformunda calistirmak icin gereken
adimlari, dogrulama kapilarini ve kesintiye dayaniklilik kurallarini tanimlar.
Amac: GPU saatini **hatasiz** harcamak. Her komut kopyala-yapistir calisir.

Ilgili kararlar: `ASSUMPTIONS.md` F7-116 (mimari antisimetri), F7-117 (ayri kup
agi), F7-118 (egitim denetim noktasi), F7-119 (on-kontrol).

---

## 0. Altin kurallar

1. **On-kontrol gecmeden egitim baslatilmaz.** `ml/preflight.py --gpu` cikis
   kodu `0` olmali. Bu betik modeli kurar, ileri gecis yapar, ONNX yazar,
   ONNX Runtime ile pariteyi ve antisimetriyi dogrular. "Egitim basladi, 3 saat
   sonra ihracatta patladi" durumunu onler.
2. **Her uzun kosu denetim noktali.** Egitim: `--checkpoint-every`. ppg:
   `--checkpoint`. Kesinti sonrasi ayni komut `--resume` ile tekrar calistirilir;
   tamamlanan is yeniden yapilmaz.
3. **`$ErrorActionPreference = "Stop"` kullanma.** PowerShell'de yerel bir
   komutun **stderr** ciktisi sonlandirici hata sayilir. `vs_gnubg.py` ilerlemeyi
   stderr'e yazar; bu ayar iki kosuyu sessizce oldurdu (F7-118). Sarmalayici
   betiklerde `"Continue"` kullan ve ciktiyi `*>> $log` ile dosyaya yonlendir.
4. **Tek tohum karar icin yetmez.** En az 5 tohum; karar tohum-ortalamasi ve
   eslestirilmis bootstrap ile verilir (R-E kurali).
5. **`ml/runs/` git'e girmez.** Kalici olmasi gereken raporlar
   `ml/artifacts/` altina yazilir.

---

## 1. Ortam kurulumu (tek sefer)

```bash
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
python -m pip install numpy onnx onnxruntime-gpu
```

`onnxruntime-gpu`, `onnxruntime` ile **ayni** ortamda bulunmamali; varsa once
`python -m pip uninstall -y onnxruntime` calistir.

gnubg yalnizca ppg olcumu ve etiketleme icin gerekir. Egitim ve ONNX ihracati
gnubg'siz calisir; bu yuzden on-kontrolde gnubg **WARN**'dir, **FAIL** degil.

---

## 2. On-kontrol

```bash
python ml/preflight.py --gpu \
  --data   ml/runs/capacity30k_rd/policy_30k_rd.npz \
  --corpus ml/artifacts/reference_corpus_v2.json \
  --out-dir ml/runs \
  --json   ml/artifacts/preflight_evren.json \
  --markdown ml/artifacts/preflight_evren.md
```

Beklenen: `sonuc: HAZIR`, cikis kodu `0`. Kontroller:

| kontrol | anlami |
| --- | --- |
| `python` | >= 3.10 |
| `paket:*` | numpy, torch, onnx, onnxruntime ice aktarilabilir |
| `torch:cuda-derlemesi` | torch CUDA ile derlenmis |
| `torch:cuda` | en az bir GPU gorunuyor |
| `torch:gpu-matmul` | gercek GPU matmul calisiyor (sadece `is_available` yetmez) |
| `onnxruntime:gpu` | `CUDAExecutionProvider` var |
| `gnubg` | WARN: yoksa ppg olculemez |
| `veri:*` | girdi dosyalari mevcut |
| `disk` | >= 5 GB bos |
| `yazma-izni` | cikti klasorune yazilabiliyor |
| `boru-hatti:ileri` | model kuruldu, sekiller dogru |
| `boru-hatti:antisimetri` | `|f(x)+f(Tx)| < 1e-4` |
| `boru-hatti:onnx` | ONNX paritesi `< 1e-5` |

`--gpu` verilmezse CUDA kontrolleri **WARN** olur; yerel CPU kosulari icin
kullanilir.

---

## 3. Egitim (denetim noktali)

### 3.1 Tek profil, tek tohum

```bash
python ml/capacity_train.py run \
  --data ml/runs/capacity30k_rd/policy_30k_rd.npz \
  --profile xlarge \
  --symmetry --symmetry-mode higgins \
  --steps 4000 --batch 256 --lr 1e-3 \
  --lr-schedule cosine --lr-final-ratio 0.1 \
  --weight-decay 1e-4 --val-fraction 0.1 --patience 5 --eval-every 500 \
  --policy-temperature 0.5 \
  --checkpoint-every 250 \
  --device cuda \
  --out-dir ml/runs/evren/xlarge/seed0 \
  --measure
```

Kesinti olursa **ayni komut** + `--resume`:

```bash
python ml/capacity_train.py run ... --resume
```

`--resume`, `<out-dir>/train_checkpoint.pt` dosyasini okur ve **kaldigi
adimdan** devam eder: agirliklar, Adam durumu, scheduler, gecmis, en iyi durum
ve torch RNG durumu geri yuklenir. Denetim noktasi atomik yazilir
(`.tmp` + `os.replace`), yani yarim dosya kalmaz.

`--checkpoint-every 0` (varsayilan) denetim noktasini **tamamen** kapatir.

### 3.2 Cok tohumlu tarama

```bash
python ml/capacity_train.py sweep \
  --data ml/runs/capacity30k_rd/policy_30k_rd.npz \
  --profile xlarge --symmetry --symmetry-mode higgins \
  --seeds 0,1,2,3,4 \
  --steps 4000 --batch 256 --lr 1e-3 \
  --lr-schedule cosine --weight-decay 1e-4 \
  --policy-temperature 0.5 \
  --checkpoint-every 250 --resume \
  --device cuda \
  --out-dir ml/runs/evren/xlarge \
  --json ml/artifacts/evren_xlarge_sweep.json
```

`--skip-existing` eklersen tamamlanmis tohumlar atlanir (profil duzeyinde
devam). `--resume` ile birlikte kullan: once yarim kalan tohum kaldigi yerden
biter, sonra tamamlanmislar atlanir.

### 3.3 Karsilastirma

```bash
python ml/capacity_train.py compare \
  --control   ml/runs/evren/medium/sweep.json \
  --treatment ml/runs/evren/xlarge/sweep.json \
  --resamples 10000 \
  --json ml/artifacts/evren_medium_vs_xlarge.json \
  --markdown ml/artifacts/evren_medium_vs_xlarge.md
```

Karar kurali: eslestirilmis bootstrap `p < 0.05` **ve** goreli kazanc
`CAPACITY_GAIN_THRESHOLD = 0.15` esigini asmali. Aksi halde "fark yok" denir ve
varsayilan profil degismez.

---

## 4. Antisimetri kapisi

Her profilden sonra:

```bash
python ml/antisymmetry.py measure \
  --model ml/runs/evren/xlarge/seed0/model.onnx \
  --corpus ml/artifacts/reference_corpus_v2.json \
  --json ml/runs/evren/xlarge/seed0/antisymmetry.json
```

`--symmetry` ile egitilen modellerde `corr = -1.0000` ve `ER farki = 0.0000`
**tanim geregi** cikar (F7-116, F7-120). Cikmiyorsa ihracat zincirinde bir sorun
var demektir; egitime devam etme.

**Iki kurulum var.** `--symmetry-mode higgins` (onerilen) duz govdeyi iki
bakistan degerlendirip ciktiyi izdusurur: tam antisimetri **ve** duz modelle
ayni ifade gucu (olculen valTop1 0,7791 vs 0,7827). `--symmetry-mode basis` 
`V-`/`V+` izdusumleriyle tek gecis kullanir: parametre tasarrufu ama tek kol
cift ozelliklerden koptugu icin valTop1 0,6614'e duser. Varsayilan `basis`;
EVREN kosularinda `higgins` kullan.

---

## 5. ppg olcumu (gnubg 2-ply)

```bash
python ml/vs_gnubg.py \
  --model ml/runs/evren/xlarge/seed0/model.onnx \
  --path search1 --gnubg-plies 2 \
  --games 4400 --workers 10 --seed 2026 \
  --checkpoint ml/runs/evren/ppg_xlarge.ckpt.jsonl \
  --json ml/artifacts/ppg_evren_xlarge.json \
  --markdown ml/artifacts/ppg_evren_xlarge.md
```

Kesinti olursa ayni komut; `--checkpoint` sayesinde tamamlanan ciftler
atlanir. `--restart` denetim noktasini **siler** ve sifirdan baslar.

Denetim noktasi anahtari `{surum, model, path, gnubgPlies, seed, maxPlies}`.
Anahtar uyusmazsa betik **hata verir** — iki farkli kosunun sonuclari sessizce
karismaz.

---

## 6. Kup agi (F7-117)

```bash
# 1) Etiketle (gnubg gerekir; paralel)
python ml/cube_net.py label \
  --corpus ml/artifacts/reference_corpus_v2.json \
  --limit 1000 --workers 8 \
  --out ml/runs/cube/labels.json

# 2) Egit
python ml/cube_net.py train \
  --labels ml/runs/cube/labels.json \
  --steps 8000 --hidden 256,256,128 --device cuda \
  --out-dir ml/runs/cube

# 3) Olc
python ml/cube_net.py measure \
  --model ml/runs/cube/model.onnx \
  --labels ml/runs/cube/labels.json
```

Kup agi **pre-roll** pozisyonu gorur; zar beklentisi agin icinde ogrenilir.
Cikti uc cubeful equity'dir (`noDouble`, `doublePass`, `doubleTake`) ve
`f(Tx) = -f(x)` **tanim geregi** saglanir. Karar: ciftleme degeri
`min(doublePass, doubleTake)` (rakip en kotu cevabi secer).

---

## 7. Maliyet kontrolu

| is | yaklasik GPU saati | not |
| --- | --- | --- |
| on-kontrol | < 0.05 | her zaman once |
| tek profil, 30k pozisyon, 4000 adim | 0.1–0.3 | xlarge, batch 256 |
| 5 tohumlu tarama | 0.5–1.5 | `--skip-existing --resume` |
| 100k pozisyon, 5 tohum | 2–5 | veri uretimi CPU'da |
| ppg 4400 oyun | 0 (CPU) | gnubg CPU'da calisir |

Kural: **veri uretimi ve ppg CPU'da**, yalnizca **egitim** GPU'da. GPU'yu
gnubg icin harcama.

---

## 8. Ariza giderme

| belirti | neden | cozum |
| --- | --- | --- |
| kosu sessizce duruyor, log bos | `$ErrorActionPreference = "Stop"` + stderr | `"Continue"` + `*>> $log` |
| `CUDAExecutionProvider` yok | `onnxruntime` (CPU) kurulu | `pip uninstall onnxruntime` + `onnxruntime-gpu` |
| `torch.cuda.is_available()` False | CPU tekerlegi kurulu | cu121 indeksinden yeniden kur |
| ONNX paritesi > 1e-5 | model `eval()` degil | `export_profile` bunu yapar; elle ihracatta `model.eval()` |
| antisimetri kapisi dusuk | `--symmetry` unutulmus | bayragi ekle; artirimla duzeltmeye calisma |
| `resume` sifirdan basladi | `train_checkpoint.pt` yok | `--checkpoint-every > 0` ile baslat |
| ppg `MatchError: denetim noktasi baska kosuya ait` | farkli model/seed | `--restart` veya yeni `--checkpoint` yolu |

---

## 9. 100k veri ile xlarge tekrar denemesi (hazir kosu plani)

Bu bolum, "xlarge ppg'de medium'dan iyi cikmadi" dalinin hazir planidir.
Yerel makinede 30k pozisyonla xlarge ile medium arasinda anlamli fark
cikmadi (en kucuk p = 0.1880). Veri eksikligi en olasi nedendir; bu yuzden
veri 100k'ya cikarilip xlarge tekrar denenir.

### 9.1 Veri uretimi (CPU, GPU harcamaz)

Etiketleme CPU'da ve gnubg ile yapilir; GPU'yu buna harcama. Betik hazir:

```powershell
# 24 dilim x 4168 pozisyon = 100 032 pozisyon, gnubg 2-ply, --dists acik
powershell -NoProfile -ExecutionPolicy Bypass -File ml\runs\capacity100k_rd\run_label.ps1
```

Cikti: `ml\runs\capacity100k_rd\policy_100k_rd.npz` + `merge.json`.
`merge.json` icindeki `stats.count` ~100 032 olmali; `hasDist` ve
`hasCandEquity` `true` olmali. Degilse egitime baslama.

**Betik dilim duzeyinde devam edebilir.** 24 dilim 12'serli iki dalgada
kosar; var olan `shard_<k>.npz` atlanir. Bir cokuste en fazla bir dalga
(~3 saat) kaybedilir; ayni komutu yeniden calistirmak yeterlidir. Ilerleme
`ml\runs\capacity100k_rd\supervisor.log` dosyasina yazilir.

Yerel sure: 30k icin ~2.5 saat idi (9 dilim), 100k icin ~6-7 saat
(24 dilim, 12 paralel, 12 mantiksal cekirdek).

### 9.2 Egitim (GPU)

`sweep` **tek** `--profile` alir (virgullu liste yok). Uc profil icin uc kez
kos; her biri kendi klasorune yazar.

```powershell
$common = @(
  'ml\capacity_train.py','sweep',
  '--data','ml\runs\capacity100k_rd\policy_100k_rd.npz',
  '--seeds','0,1,2,3,4',
  '--steps','5000','--lr','1e-3','--batch','256',
  '--value-weight','0.5','--dist-weight','0.5','--policy-temperature','0.1',
  '--weight-decay','1e-4','--lr-schedule','cosine','--lr-final-ratio','0.1',
  '--symmetry','--symmetry-mode','higgins',
  '--checkpoint-every','500','--skip-existing',
  '--measure','--corpus','ml\artifacts\reference_corpus_v2.json',
  '--stride','3','--limit','300',
  '--sym-stride','10','--sym-limit','120',
  '--measure-timeout','3600'
)
foreach ($p in 'medium','large','xlarge') {
  python @common --profile $p --out-dir "ml\runs\capacity100k_rd_sweep\$p"
}
```

Notlar:

* `--batch 256` GPU icin; yerelde 64 kullaniliyordu. Ayni `--lr` ile
  karsilastirma yapma — batch degisince etkin ogrenme orani degisir. Ya
  `--batch 64` ile devam et ya da 100k kosusunun **tamamini** 256 ile yap.
* `--symmetry-mode higgins` zorunlu: `basis` valTop1'de 0.10+ kaybediyor,
  duz model ise antisimetri kapisini dusuruyor (F7-120).
* `--skip-existing` + `--checkpoint-every 500` ile kesilen kosu kaldigi
  yerden devam eder. GPU saati parayla alindigi icin bu iki bayrak acik.
* `--sym-stride 10 --sym-limit 120` (F7-121): antisimetri kapisi gnubg
  2-ply'da vaka basina ~9.5 s surer. `--stride 3 --limit 300` ile 100 vaka
  = ~16 dk **tohum basina**, 15 kosu = ~4 saat. Kapi icin 12 vaka yeterli
  (corr tam -1.0000 cikiyor), bu yuzden ayri ve kucuk orneklem kullanilir.
* `--measure-timeout 3600` (F7-121): her olcum alt sureci icin 1 saat ust
  sinir. Takilan bir gnubg artik taramayi sure boyunca kilitleyemez; asimda
  alt surec 124 ile doner ve `antisymmetryExit`/`erExit` alaninda gorunur.

### 9.3 Karar kurali (kosudan ONCE sabitlenir)

1. Tohum bazinda `valTop1` ile **en iyi xlarge tohumunu** sec (ER'ye bakmadan).
   Bu, tohum secme yanliligini onler.
2. O modelle ppg olc (asagidaki komut). `m = 0.1115` ppg esigi gecerlidir.
3. Karar:
   * ppg farki CI'si `-m` uzerindeyse → xlarge'a gec.
   * CI `-m` ile `+m` arasindaysa → esdeger; **medium'da kal** (daha ucuz).
   * CI `+m` altindaysa → xlarge daha kotu; medium'da kal, veri buyutmeyi durdur.

Uc adim `ml\stage_100k.py` ile yapilir; karar kurali koda gomuludur.

```powershell
# 1) veri hazir mi (pozisyon sayisi offsets'ten okunur, x aday dizisidir)
python ml\stage_100k.py check --data ml\runs\capacity100k_rd\policy_100k_rd.npz

# 2) tohum sec — YALNIZCA valTop1, ER'ye bakilmaz
python ml\stage_100k.py select `
  --sweep ml\runs\capacity100k_rd_sweep\xlarge\sweep.json `
  --out ml\runs\capacity100k_rd_sweep\selection.json

# 3) ppg olc (secim.json'daki tohumu --model yoluna koy)
python ml\vs_gnubg.py `
  --model ml\runs\capacity100k_rd_sweep\xlarge\seed0\model.onnx `
  --path search1 --gnubg-plies 2 --games 4400 --workers 10 `
  --seed 2026 --checkpoint ml\runs\capacity100k_rd_sweep\ppg_xlarge.ckpt.jsonl `
  --out ml\artifacts\ppg_xlarge_100k_s0_2ply.json

# 4) karar + rapor
python ml\stage_100k.py report `
  --ppg ml\artifacts\ppg_xlarge_100k_s0_2ply.json `
  --baseline ml\artifacts\ppg_rd_large_s0_2ply.json `
  --selection ml\runs\capacity100k_rd_sweep\selection.json `
  --out-json ml\artifacts\ppg_xlarge_100k.json `
  --out-md ml\artifacts\stage_100k_report.md
```

`check` **1** ile cikarsa egitime baslama. `report` cikisi
`ml\artifacts\stage_100k_report.md` dosyasidir; `verdict` alani karar agaci
dalini da yazar.

### 9.4 GPU maliyet beklentisi

| is | GPU saati |
| --- | --- |
| 3 profil x 5 tohum x 5000 adim, 100k veri | 2–5 |
| on-kontrol | < 0.05 |
| ppg 4400 oyun | 0 (CPU) |

Once **on-kontrol** calistir (`python ml\preflight.py --require-gpu ...`);
`HAZIR` cikmadan ucretli GPU'yu baslatma.