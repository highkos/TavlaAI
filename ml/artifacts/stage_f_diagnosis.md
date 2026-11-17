# Faz 6 — Aşama B: D1–D3 kalibrasyon teşhisi

Bu rapor `ml/diagnose.py` tarafından üretilir; elle düzenlenmez.

## Girdi

- Kullanılabilir oyun sayısı: **983**
- Eğitim bütçesi: **300** adım (tüm koşularda sabit)
- CAL / VAL oyun sayısı: **100** / **100**
- Tohum: **20261114**

## Faz 5 taban çizgisi (karşılaştırma)

| Metrik | Faz 5 | Kabul |
|---|---|---|
| Eğim | 0.2431 | 0.85 – 1.15 |
| Korelasyon | 0.2431 | ≥ 0.75 |
| MAE | 0.8014 | ≤ 0.15 |
| Std oranı | 2.78 | 0.7 – 1.4 |

## D1 — Eğitim ölçeği

Aynı mimari ve hedefle artan oyun sayısı. Eğri hâlâ iniyorsa sorun ölçektir.

| Koşu | Oyun | λ | Kafa | Örnek | Değer kaybı | L_cal | Eğim | Korelasyon | MAE | Std oranı | Kalibre |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `D1-125` | 125 | 1 | six | 20916 | 1.9057 | 2.8324 | 0.6208 | 0.5662 | 1.2327 | 0.91 | ❌ |
| `D1-250` | 250 | 1 | six | 36083 | 1.3425 | 1.2323 | 0.9190 | 0.7648 | 0.8487 | 0.83 | ❌ |
| `D1-500` | 500 | 1 | six | 60620 | 1.1070 | 1.3068 | 0.9851 | 0.8166 | 0.8052 | 0.83 | ❌ |

## D2 — Hedef tanımı

`λ = 1.0` (saf Monte Carlo) vs `λ = 0.7` (TD). TD hedefi başlangıçta yanlıdır. Kıyas adil olsun diye **skaler** kafa kullanılır: TD-λ skaler bir hedef üretir. `λ < 1` hedefleri, `λ = 1.0` ile eğitilmiş bir bootstrap ağının tahminleriyle kurulur.

| Koşu | Oyun | λ | Kafa | Örnek | Değer kaybı | L_cal | Eğim | Korelasyon | MAE | Std oranı | Kalibre |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `D2-lam1` | 783 | 1 | scalar | 87628 | 1.7086 | 1.7086 | 1.0424 | 0.7757 | 0.9734 | 0.74 | ❌ |
| `D2-lam0.7` | 783 | 0.7 | scalar | 87628 | 1.6997 | 1.6997 | 1.0490 | 0.7773 | 0.9707 | 0.74 | ❌ |

## D3 — Kafa yapısı

Tek skaler değer kafası vs 6 çıktılı dışlayıcı olasılık kafası.

| Koşu | Oyun | λ | Kafa | Örnek | Değer kaybı | L_cal | Eğim | Korelasyon | MAE | Std oranı | Kalibre |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `D3-scalar` | 783 | 1 | scalar | 87628 | 1.7086 | 1.7086 | 1.0424 | 0.7757 | 0.9734 | 0.74 | ❌ |
| `D3-six` | 783 | 1 | six | 87628 | 1.1953 | 1.7049 | 1.0243 | 0.7759 | 0.9362 | 0.76 | ❌ |

## Karar

| Teşhis | İşaretli | Eylem |
|---|---|---|
| D1 — eğitim ölçeği | ✅ evet | Veri ölçeğini büyüt (Aşama C) |
| D2 — hedef tanımı | ❌ hayır | `λ` birincil neden değil |
| D3 — kafa yapısı | ✅ evet | 6 çıktılı kafa + `L_cal` |

Uygulanan sıra (Faz 6 §6.2): 6 çıktılı kafa → `L_cal` → logit sıcaklık → isotonic.

## Sınırlar

- Mevcut veri **983** oyun; D1'in 5 000 / 10 000 noktaları bu veriyle
  ölçülemez. Ölçülebilen en büyük nokta raporlanmıştır; daha büyük ölçek
  Aşama C'de yeni self-play verisiyle ölçülmelidir.
- Eğitim bütçesi sabit ve küçüktür: amaç **kıyas**, mutlak başarı değildir.
- ER ölçümü bu raporun kapsamı dışındadır; `ml/er_harness.py` ile ayrıca yapılır.

