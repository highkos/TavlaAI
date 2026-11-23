# Faz 7-R — Aşama R-E: kapasite ve öğretmen yeniden testi

**Soru.** `large`, `medium`'a göre hamle kalitesinde gerçekten daha iyi mi —
aynı veri, aynı adım, aynı tohum setiyle, eşleştirilmiş test ve bootstrap GA
ile? Ve bu kazanç **küp kararına** yansıyor mu?

**Kurulum.** Korpus `ml/artifacts/reference_corpus_v2.json`, `--stride 3
--limit 300` (faz temsili: bar 84 / contact 200 / race 16), gnubg 2-ply hakem,
3 tohum (0, 1, 2), eşleştirilmiş bootstrap 2000 yeniden örnekleme.
Δ_min = **%15** göreli (`CAPACITY_GAIN_THRESHOLD`).

## 1. Hamle ER'si

| koşu | politika | değer | search1 |
|---|---|---|---|
| `medium` (3 tohum) | 0,020402 | 0,034547 | 0,021723 |
| `large` (3 tohum) | 0,016347 | 0,031123 | 0,023166 |
| **R-D `large`** (5 tohum) | **0,012408** | **0,019507** | **0,014360** |

### `medium` → `large` (aynı veri, aynı kayıp)

| yol | fark | %95 GA | göreli | p | anlamlı | Δ ≥ Δ_min |
|---|---|---|---|---|---|---|
| politika | −0,004056 | [−0,009667; −0,000293] | **−19,9%** | 0,0250 | evet | **evet** |
| değer | −0,003423 | [−0,006753; −0,000223] | −9,9% | 0,0390 | evet | hayır |
| search1 | +0,001442 | [−0,001374; +0,003934] | +6,6% | 0,2760 | **hayır** | hayır |

### `large` (R-E) → `large` (R-D, liste kaybı)

| yol | fark | %95 GA | göreli | p | anlamlı |
|---|---|---|---|---|---|
| politika | −0,003836 | [−0,006440; −0,001218] | **−23,5%** | 0,0030 | evet |
| değer | −0,012564 | [−0,021140; −0,006560] | **−40,4%** | 0,0000 | evet |
| search1 | −0,008792 | [−0,011966; −0,005593] | **−38,0%** | 0,0000 | evet |

## 2. Küp ER'si (R-E madde 4)

Korpus `ml/artifacts/cube_corpus.json` (400 vaka, para + 5 ve 9 puan, Crawford
hariç), gnubg 2-ply cubeful referans, 3 tohum. Hedef **0,02**.

| koşu | tohum 0 | tohum 1 | tohum 2 | ortalama | sd |
|---|---|---|---|---|---|
| `medium` | 0,0753 | 0,0698 | 0,0772 | **0,0741** | 0,0038 |
| `large` | 0,0782 | 0,0576 | 0,0797 | **0,0718** | 0,0124 |
| R-D `large` | 0,0855 | 0,0898 | 0,0710 | **0,0821** | 0,0099 |

| karşılaştırma | fark | %95 GA | p | anlamlı |
|---|---|---|---|---|
| `medium` → `large` | −0,0022 | [−0,0129; +0,0061] | 0,6230 | hayır |
| `large` → R-D `large` | +0,0102 | [−0,0092; +0,0343] | 0,3810 | hayır |
| `medium` → R-D `large` | +0,0080 | [−0,0079; +0,0265] | 0,3250 | hayır |

**Kritik bulgu.** Liste kaybı hamle ER'sini üç yolda da %23–40 düşürdü ama
küp ER'sini **anlamlı şekilde değiştirmedi** (+0,0102, p = 0,38). Yani hamle
kalitesi kazancı küp kararına **transfer olmuyor**. Küp ER'si hedefin
3,6–4,1 katında (0,072–0,082 vs 0,02) ve R-C'de ölçülen 0,0642'den de kötü.

## 3. Gecikme bütçesi

Bütçe: depth-2 p95 ≤ 2 s (Faz 7 §5.2 bacak b). Üretim derinliği **depth 1**
(F7-09). 30 pozisyon, CPU:

| koşu | p50 | p95 | ortalama | bütçenin %'si |
|---|---|---|---|---|
| `medium` | 0,0175 s | **0,0626 s** | 0,0239 s | %3,1 |
| `large` | 0,0610 s | **0,2062 s** | 0,0714 s | %10,3 |
| R-D `large` | 0,0570 s | **0,2042 s** | 0,0744 s | %10,2 |

`large` bütçenin onda birinde. **B3 gerekçesiyle çelişki:** B3 (R-01)
`medium`'u seçti çünkü `large` depth-2 p95 = 13,68 s > 2 s. Ama üretim
depth-1'de çalışıyor ve orada `large` p95 0,2042 s. Yani B3'ün `large`'ı eleme
gerekçesi **üretimde kullanılmayan bir derinliğe** dayanıyordu.

## 4. Karar

**Etiket: `kanıtlanmadı`** (üç yolun üçü birden sağlanmadı; `yanlışlandı`
değil). Seçilen profil: **`large`**.

* Politika: Δ = −19,9% ≥ Δ_min ve GA alt sınırı < 0 → **sağlandı**.
* Değer: anlamlı (−9,9%, p = 0,039) ama Δ_min'in altında → sağlanmadı.
* search1: anlamlı değil (+6,6%, GA sıfırı içeriyor) → sağlanmadı.
* Gecikme: depth-1 p95 0,2042 s ≤ 2 s → **sağlandı**.

`large` yine de seçilir: politika yolunda kanıtlanmış üstünlük var, gecikme
bütçenin %10'unda, ve R-D ile birlikte üç yolun üçünde de anlamlı kazanç
sağlıyor. Ama "kapasite tek başına üç yolda kanıtlandı" **denmez**.

## 5. Açık kalan

* Küp ER'si hiçbir profilde hedefe yaklaşmıyor; hamle kalitesi ile küp
  kararı arasındaki bağ **kurulmadı**. R-F'de ayrı satır olarak raporlanır.
* `xlarge` R-E'ye hiç girmedi (R-D'de de denenmedi).
* ER 300 vaka; `race` fazında 16 vaka.
* ppg ölçümü bu raporun dışında (R-F madde 3).