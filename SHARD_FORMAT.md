# Shard Biçimi (v1) — Faz 4 v3 §5.4

Self-play verisi **ikili (little-endian)** shard dosyalarında saklanır. Aynı şemayı C# yazar
(`Backgammon.SelfPlay.ShardWriter`) ve Python okur (`ml/shards.py`). Şema **tek doğruluk
kaynağıdır**; iki taraf da `featureVersion` ve `vectorSize` alanlarını doğrulamak zorundadır.

> Bu biçimin dört faz içindeki yeri ve ölçüm sonuçları için `PHASES.md` §5.6; tasarım
> gerekçeleri için `ARCHITECTURE.md` §32 kullanılır.

| Konu | Değer |
|---|---|
| Uzantı | `*.bgsp` (ham), `*.bgsp.gz` (gzip) |
| Bayt sırası | little-endian |
| `magic` | `"BGSP"` (4 bayt) |
| `formatVersion` | `1` |
| `vectorSize` | `221` (Faz 2 v4) |
| Başlık boyutu | 32 bayt |

---

## 1. Dosya başlığı (32 bayt)

| # | Alan | Tip | Açıklama |
|---|---|---|---|
| 0 | `magic` | `u8[4]` | `"BGSP"` |
| 4 | `formatVersion` | `u32` | `1` |
| 8 | `featureVersion` | `u32` | Faz 2 v4 `BackgammonVectorizer.FeatureVersion` |
| 12 | `vectorSize` | `u32` | `221` |
| 16 | `modelVersion` | `u32` | Veriyi üreten modelin `model_version`'ı |
| 20 | `logTopCandidates` | `u32` | `M`; karar başına loglanan en fazla aday (0 = tümü) |
| 24 | `flags` | `u32` | Ayrılmış (şimdilik 0) |
| 28 | `reserved` | `u32` | Ayrılmış (şimdilik 0) |

**Doğrulama:** `magic != "BGSP"` → hata. `formatVersion != 1` → hata. `vectorSize != 221` → hata.
`featureVersion` model metadata'sındaki `feature_version` ile eşleşmezse **eğitim başlamaz**.

---

## 2. Oyun kaydı (ardışık, dosya sonuna kadar)

| # | Alan | Tip | Açıklama |
|---|---|---|---|
| 0 | `gameId` | `u64` | |
| 8 | `learnerSide` | `i8` | `0` = iki taraf da öğrenen; `+1`/`-1` = yalnızca o renk öğrenen |
| 9 | `flags` | `u8` | bit0: `aborted` (eğitimde kullanılmaz) |
| 10 | `cubeValue` | `i32` | self-play'de `1` |
| 14 | `decisionCount` | `u32` | |
| 18 | `decisions[]` | Karar kaydı × `decisionCount` | |
| … | `winner` | `i8` | `+1`/`-1`; `aborted` ise `0` |
| … | `resultType` | `u8` | `1` Single / `2` Gammon / `3` Backgammon |
| … | `resultPoints` | `u8` | mars çarpanı `1/2/3` (**`cubeValue` hariç**, Faz 1 v4 sözleşmesi) |

---

## 3. Karar kaydı (değişken uzunlukta)

| # | Alan | Tip | Açıklama |
|---|---|---|---|
| 0 | `mover` | `i8` | Hamleyi yapan (`+1`/`-1`) |
| 1 | `flags` | `u8` | bit0 `IsPass`, bit1 `IsLearner`, bit2 `ChosenIsTerminal`, bit3 `DupCapped` |
| 2 | `candidateTotal` | `u16` | `SearchResult.RootCandidates.Length` |
| 4 | `loggedCount` | `u16` | `M_i`; yalnızca `IsLearner` ise `> 0` |
| 6 | `searchValue` | `f32` | `SearchResult.EvaluationScore` |
| 10 | `chosenVector` | `f32[221]` | **yalnızca `ChosenIsTerminal = 0` ise** |
| … | `Q[loggedCount]` | `f32[]` | Loglanan adayların `RootCandidate.Score` |
| … | `policyTargetCs[loggedCount]` | `f32[]` | C#'ın `RootCandidate.PolicyTarget`'ı (çapraz doğrulama). **Toplamı ≤ 1'dir**: değerler tüm `Kind ∈ {0,1}` adayları üzerinden alınmış softmax'ın, `logTopCandidates` ile kırpılmış alt kümesidir. Python tarafı `E` üzerinde yeniden normalize eder (Faz 4 v3 §6.3). |
| … | `candVectors[loggedCount][221]` | `f32[]` | Loglanan adayların vektörleri (aynı sırada) |

### 3.1 Loglanan adaylar

* Yalnızca **`Kind == 1`** (derin aranmış) adaylar loglanır.
* `Q`'ya göre **azalan** sıralı; en fazla `logTopCandidates` tane (0 = tümü).
* Terminal (`Kind = 0`) ve `Kind = 2` adaylar **loglanmaz**; yalnızca `candidateTotal`'a dahildir.
* Havuz rakibinin kararlarında (`IsLearner = 0`) yalnızca `chosenVector` yazılır; aday verisi yazılmaz
  (`loggedCount = 0`). Bu kararlar TD zincirinin bootstrap'i için gereklidir.

### 3.2 Tutarlılık kuralları (yazıcı doğrular)

1. `ChosenIsTerminal = 1` ⇒ `chosenVector` **yazılmaz**.
2. `ChosenIsTerminal = 0` ⇒ `chosenVector.Length == 221`.
3. `loggedCount > 0` ⇒ `Q.Length == policyTargetCs.Length == loggedCount` ve
   `candVectors.Length == loggedCount * 221`.
4. `loggedCount <= candidateTotal`.
5. `loggedCount <= ushort.MaxValue`.
6. `DupCapped = 1` ⇒ `IsLearner = 0` ve `loggedCount = 0`.

### 3.3 `DupCapped` (bit3)

Aynı afterstate'in sınırsız tekrarını engellemek için Faz 6 Aşama C'de eklendi
(`Backgammon.SelfPlay/DupCapFilter.cs`). **Eklemeli** bir bayraktır: `formatVersion`
**1** kalır, eski okuyucular bilinmeyen biti yok sayar.

* Karar **silinmez**; yalnızca öğrenen kümesinden çıkarılır. TD(λ) zinciri her kararın
  `chosenVector`'üne ihtiyaç duyduğu için `chosenVector` **korunur**.
* `IsLearner` temizlenir, `Q` / `policyTargetCs` / `candVectors` **yazılmaz**
  (`loggedCount = 0`).
* Parmak izi `chosenVector`'ün `f32` baytları üzerinde FNV-1a 64'tür; shard v1 karar
  öncesi Zobrist hash'ini saklamadığı için biçim değiştirilmeden bu yol seçildi.
* Her oyunun ilk 10 kararı muaftır (açılış çeşitliliği korunur).
* Python tarafı: `ml/shards.py` → `DEC_DUP_CAPPED = 8`, `DecisionRecord.is_dup_capped`.

---

## 4. Boyut tahmini

`logTopCandidates = 12` ile karar başına yaklaşık:

```
10 (sabit alanlar) + 221*4 (chosenVector) + 12*(4 + 4 + 221*4)  ≈  11 500 bayt
```

gzip ile belirgin düşer (vektörler yüksek entropili olduğundan oran ~1.5–2× beklenir; **ölçülecek**).

---

## 5. C# ↔ Python eşleşmesi

| Kavram | C# | Python |
|---|---|---|
| Başlık | `ShardHeader` | `ShardHeader` (dataclass) |
| Oyun | `ShardGame` | `GameRecord` |
| Karar | `ShardDecision` | `DecisionRecord` |
| Bayraklar | `ShardGameFlags`, `ShardDecisionFlags` | `GAME_FLAG_ABORTED`, `DEC_IS_PASS`, `DEC_DUP_CAPPED`, … |
| Yazıcı | `ShardWriter.WriteFile` | `write_shard` (test amaçlı) |
| Okuyucu | `ShardReader.ReadFile` | `read_shard` |

**Vektörler bit düzeyinde korunur** (`f32` ham IEEE-754). Python tarafı `numpy.float32` ile
`frombuffer` kullanır; hiçbir dönüşüm yapılmaz.