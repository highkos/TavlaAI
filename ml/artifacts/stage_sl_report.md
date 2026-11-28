# F8-03 — gnubg korpustan SL (Görev 3 / Adım B)

Tarih: 2026-11-28 · Panel: `ml/artifacts/benchmark_sets.json` (229 vaka,
gnubg 2-ply, `policy` ölçütü) · Karar kuralı koşudan **önce** sabitlendi.

## 1. Ne yapıldı

`ml/gnubg_distill.py` içine `corpus-sl` modu eklendi: korpus dizinini
(`contact.npz` / `race.npz` / `all.npz` + `manifest.json`) okur, her Net'i
kendi epoch/alpha takvimiyle eğitir, `--init-from` ile warm-start zorunlu
tutar (G2). Mevcut `train-policy` damıtma modu **değişmedi**.

## 2. Sapma — gnubg `.bm` dosyaları yok

bgsage `contact.bm` / `race.bm` kullanıyor. Bu dosyalar:

- `www.gnubg.org` / `gnubg.org` — bağlantı reddedildi (443) / zaman aşımı (80)
- `ftp.gnu.org/gnu/gnubg/`, `ftpmirror.gnu.org/gnu/gnubg/` — yalnız kurulum
  paketi ve kaynak arşivi, **eğitim veritabanı yok**
- `mormegil-cz/gnubg` — `.bm` / `.nn` / eğitim dosyası yok
- GitHub kod araması `contact-train.bm` — 0 sonuç

Yerine depodaki kendi 100k gnubg-2-ply etiketli korpusu kullanıldı
(`ml/runs/capacity100k_rd/policy_100k_rd.npz`, 100.030 pozisyon).

## 3. Korpus dağılımı — kritik bulgu

`IS_CONTACT` (indeks 204) ile ayrıldı:

| Net | Pozisyon | Aday | Pay |
|---|---|---|---|
| `contact` | 98.199 | 2.214.931 | **%98,2** |
| `race` | 1.831 | 24.322 | **%1,8** |

`random_positions(max_plies=40)` neredeyse hiç yarış pozisyonu üretmiyor.
Ölçülen yarış verimi: `max_plies=40` → 2/400, `60` → 6/400, `80` → 40/400,
`100` → 30/400. **Yarış Net'i veri açlığı çekiyor**; sonraki korpus üretimi
`max_plies≈80` veya ayrı yarış üreteci kullanmalı.

## 4. Ölçüm — 3 tohum × 2 düzen

Tarif Faz 7 tabanıyla eşleştirildi: `batch 64`, `value-weight 0,5`,
`dist-weight 0,5`, `policy-temperature 0,1`, `weight-decay 1e-4`,
`val-fraction 0,05`, `eval-every 400`, warm-start
`capacity_rd/large/seed0/checkpoint.pt`.

| Model | contact ER | contact eşleşme | race ER | race eşleşme |
|---|---|---|---|---|
| **Taban** `capacity_rd/large/seed0` | **0,0070** | 77,2% | **0,0122** | 65,0% |
| SL sıralı seed0 | 0,028705 | 63,8% | 0,02895 | 63,8% |
| SL sıralı seed1 | 0,031819 | 63,1% | 0,03130 | 60,0% |
| SL sıralı seed2 | 0,026899 | 63,1% | 0,02075 | 65,0% |
| **SL serpiştirilmiş seed0** | 0,007678 | **77,9%** | 0,01315 | 63,8% |
| **SL serpiştirilmiş seed1** | 0,010624 | **77,9%** | **0,011362** | **66,3%** |
| **SL serpiştirilmiş seed2** | 0,009832 | 77,2% | 0,01495 | 58,8% |
| Teşhis A — yalnız contact, 2 epoch | 0,007248 | **80,5%** | 0,013962 | 63,8% |
| Teşhis B — yalnız contact, 1 epoch yumuşak | 0,009376 | 73,8% | 0,01480 | 61,3% |

Ortalamalar: sıralı contact ER **0,02914** (tabanın 4,2 katı kötü),
serpiştirilmiş **0,009378** (tabanın 1,34 katı kötü).

## 5. Bulgular

1. **Sıralı düzen felaket unutmaya yol açıyor.** `contact` 0,0072'den
   0,0287'ye çıkıyor — 4 kat bozulma. Neden: tek paylaşılan ağda 1.831
   pozisyonluk `race` fazı, 98.199 pozisyonluk `contact` bilgisini eziyor.
   bgsage'in *ayrı* Net'leri olduğu için orada bu sorun yok; bizim tek
   ağımızda müfredat sırası yanlış desen.
2. **Serpiştirme (`--mix`) unutmayı çözüyor.** Her epoch içinde Net'ler
   küçükten büyüğe eğitilir, epoch daima en büyük Net ile kapanır. Contact ER
   0,0287 → 0,0077 (seed0), eşleşme %63,8 → %77,9. Bu, F8-03'ün kalıcı
   teknik kazanımı.
3. **Ama SL tabanı geçmiyor.** Serpiştirilmiş ortalaması contact ER'de
   tabanın %34 üstünde; eşleşme oranında eşit (%77,9 vs %77,2). Race'te
   seed1 hafif iyi (0,0114 vs 0,0122), seed2 belirgin kötü (0,0150).
   **İstatistiksel olarak fark yok.**
4. **Yalnız-contact teşhisi (A) tabanla eşit.** 0,007248 vs 0,0070 ER ama
   eşleşme %80,5 vs %77,2 — yani korpus SL'i *politika eşleşmesini* artırıyor,
   *equity kaybını* azaltmıyor. Bu ikisinin ayrışması, korpusun kendisinin
   bilgi tavanının taban modelin seviyesinde olduğunun kanıtı.
5. **Daha yumuşak tarif (B) daha kötü.** 1 epoch × 3e-4 → 0,009376. Yani
   sorun "fazla eğitim" değil; korpusta tabanın ötesinde öğrenilecek sinyal
   yok.

## 6. Karar

**Görev 3 / Adım B kabul edilmez — taban model korunur.** `DEFAULT_MODEL`
F8-02'de `capacity_rd/large/seed0`'a çekilmişti; öyle kalıyor.

Gerekçe: karar kuralı "contact ER'de tabandan anlamlı iyi" idi; serpiştirilmiş
SL bunu sağlamıyor (0,0094 vs 0,0070). Buna karşılık `--mix` düzeltmesi
korunuyor çünkü sıralı düzeni 4 kat bozuk bırakıyordu.

**Sonraki kaldıraç nereye kaymalı.** Bu sonuç üç şeyi eliyor: (a) daha fazla
SL epoch'u, (b) daha yumuşak LR, (c) mevcut 100k korpusunda farklı Net
sırası. Kalan kaldıraçlar: **korpus çeşitliliği** (yarış pozisyonları,
`max_plies≈80`), **etiket derinliği** (2-ply → 3-ply), **mimari** (HigginsNet
antisimetrisi zaten çözüldü; kapasite değil veri sınırlıyor).

## 7. Doğrulama

- `ml/tests/test_gnubg_distill.py` — **28 F8-03 testi** (BOM'lu bildirim,
  Net filtresi, `all.npz` bölme, warm-start ağırlık transferi, şekil uyuşmazlığı
  reddi, F7-126 maskeleme sözleşmesi, `--mix` serpiştirme sırası), hepsi yeşil.
- Damıtma paketi toplamı: **241 test** yeşil.
- Tüm Python paketi: **1659 test** toplandı.
- Koşu süreleri: eğitim ~13 dk/tohum, panel ~9,5 dk/model.

## 8. Artefaktlar

- `ml/runs/corpus_sl_100k/` — korpus (`contact.npz`, `race.npz`,
  `manifest.json`), `run_sl.ps1`, `run_sl_mix.ps1`, `run_panel.ps1`,
  `run_diag.ps1` (gitignore'da).
- `ml/artifacts/model_benchmarks.json` / `.md` — 6 yeni panel kaydı
  (3 sıralı + 3 serpiştirilmiş) + 2 teşhis kaydı.
- Gerekçe: `ASSUMPTIONS.md` F8-03, `PHASES.md` §53, `ARCHITECTURE.md` §60.
