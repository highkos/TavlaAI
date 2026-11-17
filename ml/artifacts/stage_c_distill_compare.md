# Faz 7 Asama C - Test 102: damitma kazanci

Kapi: damitilmis model, kontrol modelinden VAL-ER'de **>= %25** daha iyi.

| Olcum | Kontrol | Damitilmis |
|---|---|---|
| Model | `ml/runs/stage_c_control_train/onnx/model_v2_trained.onnx` | `ml/runs/stage_c_distill_train/onnx/model_v2_trained.onnx` |
| Pozisyon | 70 | 70 |
| VAL-ER | 0,0883 | 0,0602 |
| SE | 0,0153 | 0,0120 |

| Kazanc | Deger |
|---|---|
| Nokta tahmini | 0,3182 |
| Standart hata | 0,1803 |
| %95 GA | [-0,0351; 0,6715] |
| Esik | 0,25 |
| Kapi | BASARISIZ |
| Sert kapi (alt sinir >= esik) | BASARISIZ |

**Karar:** basarisiz: kazanc 0.3182 >= esik 0.25 ama alt sinir -0.0351 <= 0 (iyilesme sifirdan ayrilmiyor)
