# Faz 4 v3 — Aşama C kabul raporu

Ölçüm tarihi: yerel makine `DESKTOP-2T0QNN5` (NVIDIA GTX 1650 4 GB, 12 mantıksal çekirdek).
Eğitim cihazı: CUDA (PyTorch 2.5.1+cu121). Çıkarım: ONNX Runtime 1.23.2 CPU EP.

## 1. Smoke eğitimi (spesifikasyon Bölüm 9, Aşama C)

Komut:

```
python ml/train.py --out ml/runs/stage_c_accept --iterations 10 --games 100 \
    --steps 200 --depth 0 --device cuda --eval-random 200 --seed 20260214 --lam 1.0
```

10 iterasyon x 100 oyun = **1000 oyun**, iterasyon başına 200 eğitim adımı (toplam 2000 adım).

| Ölçüm | Değer |
|---|---|
| Toplam süre | 308 s (self-play + hedefler + eğitim + ölçüm) |
| Oyun başına self-play süresi (depth 0) | ~0,25 s |
| Değer örnekleri (son iterasyon) | 98 658 |
| Politika kararları (son iterasyon) | 83 835 (eğitime giren: 63 405) |
| Gradyan normu (son iterasyon ort. / maks.) | 2,42 / 4,62 — **sonlu** |
| NaN / Inf | **yok** |

### Kabul kriterleri

| Kriter | Sonuç |
|---|---|
| 1000 oyunluk smoke tamamlandı | **EVET** |
| Kayıplar ve gradyanlar sonlu | **EVET** |
| Değer kaybı 0. adıma göre düşer | **EVET** — sabit, ağdan bağımsız MC hedefinde 1,9153 -> 1,5629 (**-18,4 %**) |
| Politika kaybı düzgün bazın (`log|E|`) altına iner | **EVET** — 1,8513 < 2,1264 (son iterasyon) |
| Hedef entropisi / `log|E|` oranı raporlanır | **EVET** — 0,9984 -> **0,3934** |
| `RandomBot`'a karşı kazanma oranı raporlanır | **EVET** — **%64,25** (400 oyun, ±%2,4) |

## 2. `RandomBot` karşılaştırması (400 oyun, seed 424242, depth 0, argmax)

Protokol: sabit seed, `argmax`, renkler değişimli (200 oyun her renkten).

| Model | lambda | c_policy | Kazanma | Oyun başına puan |
|---|---|---|---|---|
| Eğitilmemiş ağ (`model_v1`) | — | — | %53,00 | +0,165 ± 0,102 |
| 10 iterasyon, kapı 0,99 | 0,7 | 1,0 | %40,25 | -0,435 ± 0,100 |
| 5 iterasyon, kapı yok | 0,7 | 0,0 | %57,50 | +0,345 ± 0,115 |
| **10 iterasyon, kapı 0,99** | **1,0** | **1,0** | **%64,25** | **+0,678 ± 0,092** |

Eşikler (örneğin "RandomBot'u %X yenmeli") spesifikasyon gereği **ilk ölçümden sonra**
belirlenir; bu raporda uydurma eşik yoktur. Öneri: Aşama D'de 20 000 oyunluk gerçek
eğitimde `RandomBot` eşiği %75, `PipBot` eşiği %55 olarak tartışılabilir.

## 3. Bulgular (ölçülmüş, tahmin değil)

### 3.1 `lambda = 0,7` + `gamma = 1` uzun oyunlarda hedefleri sıfıra çökertiyor

Spesifikasyon Bölüm 6.2 geriye doğru özyinelemesi

```
y[T-2] = -z
y[t]   = -((1-lambda) * V_hat[t+1] + lambda * y[t+1])
```

`gamma = 1` ve ödül yalnızca oyun sonunda olduğu için terimler `lambda^k` ile sönüyor.
~100 kararlık bir oyunda `0,7^20 ~ 8e-4`; yani ilk ~80 kararın hedefi ~0. Ağ "her şeye 0
tahmin et" çözümüne yakınsıyor ve gerçek equity öğrenilmiyor.

Ölçüm: `lambda = 0,7` ile MC hedefinde değer kaybı 2,9373 -> 2,8811 (**-1,9 %**),
`lambda = 1,0` ile 1,9153 -> 1,5629 (**-18,4 %**). Aynı şekilde `RandomBot` kazanma oranı
%40,25'e karşı %64,25.

**Öneri:** kısa/orta koşullarda `lambda = 1,0` (Monte Carlo) kullan; uzun koşullarda
`lambda` değeri `gamma` ile birlikte yeniden değerlendirilmeli (örneğin `gamma < 1`).

### 3.2 Düzgüne yakın politika hedefleri değer fonksiyonunu bozuyor

Eğitilmemiş ağın `Q` değerleri ~±0,04 aralığında olduğu için `softmax(Q / 0,05)` neredeyse
düzgün çıkıyor (`H/log|E| = 0,998`). Bu durumda politika gradyanı bilgi taşımaz, ama
`c_policy = 1,0` ile büyüklüğü değer gradyanından ~20 kat fazladır (kayıp 2,17'ye karşı 0,02).

Ölçüm (`lambda = 0,7`, 5 iterasyon): `c_policy = 1,0` -> %21,5 kazanma; `c_policy = 0` -> %58,0.

**Uygulanan koruma:** `train.policy_min_sharpness` (varsayılan 0,99). Hedef entropisi
`log|E|`'ye bu eşikten daha yakınsa karar eğitimden elenir. Raporlama yine **tüm** uygun
kararlar üzerinden yapılır (spesifikasyonun "düzgün hedef kontrolü" maddesi). Eşik
`1,0` yapılarak kapatılabilir. Bkz. `ASSUMPTIONS.md` F4-40.

### 3.3 Shard boyutu ve hız (ölçülen)

| Ayar | Karar başına ham | Oyun başına (depth 0) | Oyun/s (tek iş parçacığı) |
|---|---|---|---|
| depth 0, `logTop=12`, gzip yok | ~1,0 KB | ~885 KB | ~14-36 |
| depth 1, `logTop=12`, gzip | ~0,14 KB | ~94 KB | ~0,05 |

Spesifikasyonun ~11 KB/karar tahmini, `logTopCandidates = 12` ve 221 float vektör
(884 B/aday) ile uyumlu değil; gerçek değer ~1 KB/karar. Fark, tahminin vektör
boyutunu hesaba katmamasından kaynaklanıyor.

## 4. Tekrarlanabilirlik

* Aynı seed + `--threads 1` => **birebir aynı shard'lar** (SHA256 ile doğrulandı).
* `--threads > 1` deterministik değildir (iş parçacığı başına ayrı RNG) — spesifikasyon
  Bölüm 5.1 yalnızca tek iş parçacığı için determinizm ister.
* Eğitim döngüsü `torch.manual_seed(seed)` + `np.random.default_rng(seed)` kullanır.