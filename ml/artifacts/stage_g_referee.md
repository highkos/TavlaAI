# Faz 7 Asama A - Derin hakem (`hint` protokolu) raporu

**Tarih:** 2026-07-17
**Kapsam:** `faz 7.md` Bolum 4.2 (Test 91, 92), Bolum 9.1, Bolum 10.6 (Asama A kabul).
**Modul:** `ml/gnubg_hint.py` (759 satir), `ml/tests/test_gnubg_hint.py` (68 test).
**gnubg:** `GNU Backgammon 1.08.003-mingw 32-Bit 20240428`.

Bu rapor, Faz 6'nin **olcemedigi** seyi olcer: 3-ply ve 4-ply ER. Faz 6'nin
"3-ply" olcumu aslinda 0-ply idi (F6-32); `eval` komutu 2-ply'dan derine inemez.
Derin hakem icin gnubg'nin `hint` protokolu gerekir - ve `hint` protokolu
**uc sessiz tuzak** icerir. Ucu de olculdu, ucu de kapatildi.

---

## 1. F7-01 - `hint` hamle filtresi derin degerlendirmeyi sessizce budar

`hint` `plies` ayarina **uyar**, ama once gnubg'nin **hamle filtresini** uygular,
sonra yalnizca hayatta kalanlari istenen derinlikte degerlendirir. Varsayilan
filtre (`show evaluation`):

```
Move filter for 3 ply:
  keep the first 0 0-ply moves and up to 8 more moves within equity 0,16
  Skip pruning for 1-ply moves.
  keep the first 0 2-ply moves and up to 2 more moves within equity 0,04
```

Yani `plies=3` iken **~2 hamle** gercekten 3-ply alir; geri kalan `2-ply` (veya
`0-ply`) etiketiyle basilir. Kanit (`f6-000`, `plies=3`, filtre genisletilmemis):

```
1. Cubeless 2-ply 13/5*(2) Eq.: +0,253
3. Cubeless 0-ply 13/5*/1 6/2 Eq.: +0,082
```

Faz 6 bunu fark etmedi cunku `f6-006`'da en iyi hamle tesadufen terfi etmisti.

**Duzeltme.** `set evaluation movefilter <plies> <level> 1000 0 0.0` komutu
**`level = 0 .. plies-1` araliginin tamami** icin verilir. Kritik ayrinti:
yalnizca `0 .. plies-2` genisletmek son seviyeyi kapali birakir ve hamleler yine
`plies-1` derinliginde doner.

| `plies` | genisletilen seviyeler | gorulen derinlikler | sure (`f6-000`) |
|---|---|---|---|
| 3 | [0] | {2} | 0,4 s |
| 3 | [0,1] | {2} | 0,4 s |
| 3 | **[0,1,2]** | **{3}** | 2,5 s |
| 4 | [0,1,2] | **{4}** | 48,8 s |
| 4 | **[0,1,2,3]** | **{4}** | 51,1 s |

Sozdizimi notlari: komut `set evaluation movefilter` ( `set evaluation chequerplay
movefilter` **degil** - "Unknown keyword `movefilter'"); ply argumani ciplak tam
sayi (`3`, `4`), `3ply` degil; seviye argumani zorunlu; esik `0.0`, `0.000` veya
`0` kabul edilir.

**Koruma.** `HintReferee._preamble()` filtreyi genisletir;
`verify_uniform_depth(text, plies)` her pozisyonda **butun** hamlelerin istenen
derinlikte oldugunu dogrular ve aksi halde `HintMappingError` firlatir. Sessiz
budama artik imkansiz.

---

## 2. F7-02 - Hamle notasyonu **siranin oyuncusunun** bakis acisindadir

X (siyah, `turn = -1`) mutlak hane numaralarini kullanir; O (beyaz, `turn = +1`)
**aynalanmis** numaralari (`p -> 25 - p`). 40 korpus vakasinda olculdu:

| `turn` | ozdes esleme | aynalanmis esleme |
|---|---|---|
| -1 | 10/10 | 0/10 |
| +1 | 0/10 | 10/10 |

Bu yuzden `_point()` `value if turn == -1 else 25 - value` doner. Ayrica cok
adimli hamlede ara haneler **vurus isaretini** tasir (`"13/5*/1"` -> `5*` hem
inis hem kalkis), bu yuzden `parts[i].rstrip("*")` zorunludur.

---

## 3. F7-03 - `hint` en fazla 10 hamle basar

`f6-001`'in 43 yasal afterstate'i var; `hint` 10 hamle dondurur. Yani modelin
secdigi afterstate **her zaman listede degildir**: olculen **39/200 = %19,5**.

**Tasarim karari.**

| `plies` | Yol | Kapsama |
|---|---|---|
| <= 2 | modelin afterstate'i dogrudan `eval` ile degerlendirilir | **%100** |
| >= 3 | `eval` derine inemez (F6-32) -> pozisyon **sansurlu** isaretlenir, yalnizca **alt sinir** raporlanir (`best - worst_listed`) | <= %80,5 |

Kapsama birinci sinif metrik oldu (`coverage`, `coveredCount`, `censoredCount`,
`meanLowerBound`). Sampiyon iddiasi **kapsama >= %99** ister (kapi F-A9).

---

## 4. F7-04 - `hint@2` ile `eval@2` ayni sey degildir

10 pozisyonda olculdu: **6 ozdes, 4 farkli**, fark **0,118**'e kadar
(`f6-161`: hint@2 -0,8920 / eval@2 -1,0100; `f6-185`: hint@2 -1,7070 /
eval@2 -1,6130). Merdiven adimlari ayni mertebede (ortalama |h2-h1| = 0,1342,
|h3-h2| = 0,1069, oran 1,26x), yani bu **volatil pozisyonlarda normal arama
gurultusu**, kusur degil. Karar verici prob: `hint@2`'nin en iyi hamlesini
uygulayip o afterstate'i `eval` ile olcmek `hint@2`'nin bildirdiginden farkli
sayi verir; `set evaluation chequerplay evaluation prune on|off` bunlari
uzlastirmaz.

**Karar.**

| `plies` | Hakem | Gerekce |
|---|---|---|
| 0, 1, 2 | **`eval`** | Faz 6 ile karsilastirilabilir; standart gnubg |
| 3, 4 | **`hint`** | `eval` derine inemez |

`hint@2` **asla** hakem olarak kullanilmaz. Sonuc: 2 -> 3-ply gecisi bir
**yontem degisikligidir**, elma-elmadir degil. Her rapor `methodNote` /
`LADDER_METHOD_NOTE` alanini tasir.

---

## 5. Olculen birim maliyetler (filtre genisletilmis)

| Yol | 8-20 pozisyon | 200 pozisyon | 1 670 pozisyon |
|---|---|---|---|
| `eval@2` (butun afterstate'ler) | - | **1,26 s/poz** -> ~252 s (4,2 dk) | ~35 dk |
| `hint@2` | - | **0,48 s/poz** -> ~1,6 dk | ~13 dk |
| `hint@3` | - | **4,21 s/poz** -> ~14 dk | **~2,0 saat** |
| `hint@4` | - | **62,57 s/poz** -> ~3,5 saat | **~29 saat** |

**F7-07 - bu tablo `contact` pozisyonlarini temsil etmiyor.** 60 pozisyonluk CAL
kumesinde 4-ply `hint` kosuldugunda 14 pozisyon 2 412,9 s'de bitti
(**172 s/pozisyon**) ve 15. pozisyon (`f6-040`) **900 s** zaman asimina carpti.
Yukaridaki 62,57 s/pozisyon degeri `closed`/`race` agirlikli 8-20 pozisyonluk bir
orneklemden geliyor. Gercek maliyet:

| Pozisyon tipi | 4-ply `hint` |
|---|---|
| `closed` / `race` | 19-63 s |
| `contact` (ortalama) | **172 s** |
| `f6-040` (en yogun) | **> 900 s** |

1 670 pozisyon 4-ply = 1 670 x 172 s = **~80 saat** (en kotu durumda 418 saat).
40 saat tavanini (Bolum 4.5.3) **asiyor**. Bu yuzden insan merdiveni
3-ply hakemle olculdu (`ml/artifacts/stage_a_ladder.md`); 4. basamak
`source = "unmeasured"` olarak raporlandi - uydurma sayi uretilmedi.

---

## 6. Uctan uca dogrulama - 200 pozisyon, 2-ply

`ml/artifacts/stage_a_hint_2ply.json`, model `ml/runs/stage_d_l2/onnx/model_v30.onnx`:

| Alan | Deger |
|---|---|
| Pozisyon | 200 |
| Ortalama ER | **0,07477** |
| Standart sapma | 0,109835 |
| Standart hata | 0,007767 |
| Medyan | 0,017 |
| Maksimum | 0,479 |
| Tam eslesme | %37,0 |
| **Kapsama** | **%100** (200/200) |
| Sansurlu | 0 |
| **Esleme hatasi** | **0** |
| Kaynak | `hint` 161 / `eval` 39 / `censored` 0 |
| Sure | 146,5 s (**0,73 s/pozisyon**) |

Faz 6 `stage_h_er_2ply.json` (ortalama 0,07397, sigma 0,109072) ile
karsilastirma: ortalama |fark| **0,0043**, en buyuk fark **0,108** (`f6-168`),
sonra `f6-185` (0,094), `f6-161` (0,092). Iki bagimsiz uygulama ayni sayiyi
veriyor - **esleme 200/200 kuruldu** (Test 92).

---

## 7. Asama A kabul durumu (Bolum 10.6)

| Kriter | Durum |
|---|---|
| Test 90 - hakem derinligi sozlesmesi | GECTI |
| Test 91 - `hint` `plies` ayarina uyar (2/3/4 farkli equity) | GECTI |
| Test 92 - hamle -> afterstate eslemesi 200/200 | GECTI (0 hata) |
| `hint` 3-ply ve 4-ply veriyor | GECTI (filtre genisletilmis) |
| `methodNote` her raporda | GECTI |

**Acik risk.** 3-ply/4-ply'da kapsama %80,5'i gecemez (F7-03): modelin hamlesi
`hint` ilk-10 listesinde olmadiginda pozisyon yalnizca **alt sinirla**
raporlanabilir. Kapi F-A9 (kapsama >= %99) bu tasarimla **4-ply'da tutmaz**.
Karar Asama H'de verilecek: (a) alt sinir temelli iddia, veya (b) keyfi bir
afterstate'i 3/4-ply'da olcmenin bir yolunu bulmak. 21-zarli rekursiyon denendi
ve dogrudan `eval` ile -0,007 ile -0,028 arasi uyusmuyor - **kesin degil**.
