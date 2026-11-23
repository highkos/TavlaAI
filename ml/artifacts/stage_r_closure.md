# Faz 7-R — Kapanış Raporu

**Tarih:** 2026-02-19
**Kapsam:** `faz 7 v2.5.md` §4 Aşama R-A … R-F, §5 test tablosu R-T1 … R-T37, §6 kabul kriterleri.
**Sonuç:** Altı aşamanın **altısı da kapandı**; R-T1 … R-T37'nin tamamı yeşil.
Sayısal ER hedefi **kapı değildir** (§6 notu) — kapı ölçümün geçerliliğidir ve
bu rapordaki üç satır ölçümü geçerli kılar, hedefi karşılamaz.

---

## 1. Aşama kapıları

| Aşama | Kapı | Durum | Kanıt |
|---|---|---|---|
| **R-A** | Belge çelişkisi yok; B3 askıda; hedef ikiye ayrıldı | ✅ | `PHASES.md` §35, `ASSUMPTIONS.md` F7-80…F7-83 |
| **R-B** | Korpus v2 ≥ 1000, temas ≥ %60, oyun bazlı bölünme, sızıntı = ∅; ER üç yolda | ✅ | `ml/artifacts/stage_r_b_report.md`; `test_corpus2.py` (17 test) |
| **R-C** | G7 anomalisi açıklandı; verdict mantığı düzeltildi; öğrenme eğrisi aracı çalışıyor | ✅ | `ml/artifacts/stage_r_c_report.md`; `test_stage_r_c.py` |
| **R-D** | Damıtma held-out, eşleştirilmiş, bootstrap GA ile **üç durumlu** karar | ✅ | `PHASES.md` §39, F7-110; `ml/runs/capacity_rd/large/seed{0..4}` |
| **R-E** | `large` kararı kapasite deneyinden, ≥ 3 seed | ✅ | `ml/artifacts/stage_r_e_report.{json,md}`; `PHASES.md` §40, F7-111 |
| **R-F** | Ölçülmüş ply merdiveni; eşdeğerlik testi; üç satırlık nihai rapor | ✅ | `ml/artifacts/stage_r_f_report.{json,md}`, `gnubg_ladder*.{json,md}`, `gnubg_rollout.{json,md}`; `test_stage_r_f.py` |

---

## 2. Test kapsama haritası (R-T1 … R-T37)

Spec kimlikleri **CamelCase**, projedeki test adları **snake_case**'tir; eşleme
aşağıdadır. Hepsi yeşil.

| Kimlik | Spec adı | Test |
|---|---|---|
| R-T1 | `Corpus2_SplitIsByGame` | `test_corpus2.py::test_corpus2_split_is_by_game` |
| R-T2 | `Corpus2_NoLeakFromTraining` | `test_corpus2.py::test_corpus2_no_leak_from_training` |
| R-T3 | `Corpus2_ContactShare` | `test_corpus2.py::test_corpus2_contact_share` |
| R-T4 | `ER_ReportsThreePaths` | `test_corpus2.py::test_er_reports_three_paths` |
| R-T5 | `ER_Bootstrap_CI` | `test_corpus2.py::test_er_bootstrap_ci` |
| R-T6 | `Power_UsesSigmaUpperBound` | `test_corpus2.py::test_power_uses_sigma_upper_bound` |
| R-T7 | `G7_TwoSided` | `test_stage_r_c.py` |
| R-T8 | `G7_Lambda1_RatioIsOne` | `test_stage_r_c.py` |
| R-T9 | `Verdict_PairedFirst` | `test_stage_r_c.py` |
| R-T10 | `Verdict_NoCapacityInference` | `test_stage_r_c.py` |
| R-T11 | `LearningCurve_Runs` | `test_stage_r_c.py` |
| R-T12 | `Distill_InputIsAfterState` | `test_gnubg_distill.py::test_127j_afterstate_case_*` |
| R-T13 | `Distill_UsesAllCandidateEquities` | `test_gnubg_distill.py::test_127j_policy_dataset_candidates` |
| R-T14 | `Distill_MaskedCandidatesNotNegative` | `test_gnubg_distill.py::test_127l_unlabelled_candidates_are_not_counted_negative` |
| R-T15 | `Distill_HeldOutOnly` | `test_gnubg_distill.py::test_127b_verdict_*` |
| R-T16 | `Distill_EpochMatched` | `test_curve_pool.py::test_175_curve_pool_train_fn_contract` (`epochs=1` notu) |
| R-T17 | `Distill_FineTuneVsScratch` | `test_distill_compare.py` (33 test) |
| R-T18 | `Distill_PairedBootstrapVerdict` | `test_gnubg_distill.py::test_127l_verdict_*` |
| R-T19 | `Ladder_Measured` | `test_stage_r_f.py::test_r_t19_ladder_measured` |
| R-T20 | `Ladder_NoSelfReferee` | `test_stage_r_f.py::test_r_t20_ladder_no_self_referee` |
| R-T21 | `Equivalence_Test` | `test_stage_r_f.py::test_r_t21_equivalence_test_direction` |
| R-T22 | `Final_Report_ThreeLines` | `test_stage_r_f.py::test_r_t22_final_report_three_lines` |
| R-T32 | `Antisymmetry_Mirror` | `test_antisymmetry.py::test_158_antisymmetry_mirror_board` |
| R-T33 | `Antisymmetry_Gate` | `test_antisymmetry.py::test_164_antisymmetry_report_gate` |
| R-T34 | `CurvePool_Split` | `test_learning_curve_cluster.py::test_182_cluster_means_groups_by_game` + `test_curve_pool.py::test_168_curve_pool_accessors` |
| R-T35 | `Curve_ClusterBootstrap` | `test_learning_curve_cluster.py::test_184_fit_log_slope_clustered_wider` |
| R-T36 | `Search1_Parity` | `test_search1_parity.py` |
| R-T37 | `Verdict_Labels` | `test_gnubg_distill.py::test_127a_verdict_labels_are_distinct` |

---

## 3. Üç satırlık nihai cevap

| # | Satır | Ölçüm | Bütçe | Sonuç |
|---|---|---|---|---|
| 1 | **Hamle kalitesi** | politika ER **0,0111** [0,0077; 0,0152], search1 **0,0139** [0,0101; 0,0185] | ER ≤ gnubg 2-ply seviyesi (taban 0,0013) | ❌ Model **gnubg 0-ply seviyesinde** (0,0062) |
| 2 | **Küp** | küp ER **0,0821** (3 tohum, 400 vaka) | küp ER ≤ 0,02 | ❌ Hedefin **4,1 katı** |
| 3 | **Oyun gücü** | ppg **−0,2445** [−0,3055; −0,1835] (2000 oyun) | `H0: ppg_fark ≤ −m`, m = 0,1115 | ❌ **`daha-kotu`** |

**Tutarlılık.** gnubg 0-ply vs 2-ply = −0,2229 ppg; modelimiz = −0,2445 ppg.
İki bağımsız ölçüm (ER merdiveni ve ppg) aynı yeri gösteriyor — ölçüm zinciri
kendini doğruluyor.

---

## 4. Faz 7-R'nin üç kalıcı bulgusu

1. **`search1` politikadan kötü** (0,0139 vs 0,0111). Değer kafası en zayıf yol
   (ER 0,0173) ve depth-1 arama onu miras alıyor. **Arama, politika zayıf
   olduğu için değil, değer kafası zayıf olduğu için kaybettiriyor.**
2. **Hamle kalitesi kazancı küp kararına transfer olmuyor.** medium → large
   politika −%19,9 (p = 0,0250) ama küp ER 0,0741 → 0,0718 (p ≥ 0,32).
3. **Antisimetri kapısı düşüyor** (|corr| ≥ 0,99 hedefi; ölçülen −0,9464 …
   −0,9562). Çıkarım anı antisimetrikleştirmesi **kaybettiriyor**
   (politika ER 0,038488 → 0,048880). `--augment-perspectives` varsayılan
   **kapalı** kalır (§36.22).

---

## 5. Karar bekleyen açık maddeler

| # | Madde | Neden bekliyor |
|---|---|---|
| 1 | **Değer kafası hedefi** | Ölçüm artık gerekçeyi veriyor: değer kafası en zayıf yol ve `search1`'i kırıyor. 6 sınıflı dağılım etiketi `hint` yolundan **ek maliyetsiz** alınabiliyor (F7-114). Yöntem seçimi kullanıcıya ait. |
| 2 | **Küp ER hedefi 0,02** | Hedefin 4,1 katı uzaktayız ve hiçbir kapasite/veri değişikliği iyileştirmedi. Hedef gözden geçirilmeli mi? |
| 3 | **`m = 0,1115` yalnızca money** | Maç hücreleri (5 ve 9 puan) ayrı raporlanmadı. |
| 4 | **İstatistiksel güç borcu %46** | m = 0,1115 için gereken 4337 oyun; koşulan 2000. |
| 5 | **gnubg GPL lisansı** | Ürün dağıtımı öncesi hukuki görüş gerekir (R-Q1, §36.10/5). Ajan yalnızca durumu raporlar. |
| 6 | **R-Q5 (G7 λ / terminal birimi)** | Kısmen yanıtlandı: birim uyumsuzluğu kanıtlandı ve düzeltildi; λ seçimi belgelenmedi. |

**Kapanan açık soru.** R-Q2 (§43, F7-114): `hint` altı olasılığı **zaten
veriyor**; `parse_hint` artık ayrıştırıyor.

---

## 6. Ölçüm çözünürlüğü tabanı

| Hakem | 0-ply | 1-ply | 2-ply | 3-ply | n |
|---|---|---|---|---|---|
| `hint` @ 3-ply | 0,0063 | 0,0027 | 0,0013 | — | 40 |
| `hint` @ 4-ply | 0,0049 | 0,0040 | 0,0006 | 0,0002 | 20 |

**Taban = 0,0006 … 0,0013.** 4-ply'ın kendi ER'si **ölçülemez**: gnubg
`eval` 2-ply'den derin sütun üretmiyor ve `rollout` bu derlemede equity
yazdırmıyor (beş bağımsız prob; `ml/artifacts/gnubg_rollout.md`). Bu yüzden
"gnubg 4-ply'a göre eşdeğer" **denmez**; "eşdeğerlik kanıtlanmadı" denir.

---

## 7. Araçlar

`ml/gnubg_ladder.py` (`--deep`, `--deep-referee-plies`, `--deep-player-plies`,
`--deep-limit`, `--models-only`, `--model-er`), `ml/gnubg_rollout.py`,
`ml/vs_gnubg.py`, `ml/ppg_measure.py` (`equivalence_verdict`,
`required_games`), `ml/gnubg_er.py` (`HintMove.probs`).

**Test sayısı:** 1508 (pytest) / 1993 (toplam).
