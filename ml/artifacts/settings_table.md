# Faz 3 arama ayarı ölçüm tablosu

Model: `ml\artifacts\model_stage_c.onnx` — seed 1.

| Ayar | DepthPly | MaxRoot / Inner | Oyun/s | s/oyun | B/oyun | Oyun | PipBot kazanma | Ortalama puan | 95% GA |
|---|---|---|---|---|---|---|---|---|---|
| depth 0, kısıtsız | 0 | 0 / 0 | 62.37 | 0.016 | 1131815 | 100 | 13.00 % | -1.0000 ± 0.1639 | [-1.3213, -0.6787] |
| depth 0, kısıtlı (4/4) | 0 | 4 / 4 | 87.32 | 0.011 | 293877 | 100 | 9.00 % | -1.0000 ± 0.1484 | [-1.2908, -0.7092] |
| depth 1, kısıtsız | 1 | 0 / 0 | 0.59 | 1.695 | 1637306 | 20 | 30.00 % | -0.2500 ± 0.4284 | [-1.0897, +0.5897] |
| depth 1, kısıtlı (4/4) | 1 | 4 / 4 | 2.17 | 0.461 | 304375 | 20 | 45.00 % | +0.0000 ± 0.4588 | [-0.8993, +0.8993] |
| depth 2, kısıtsız | 2 | 0 / 0 | zaman aşımı | > 600 | - | 0 | - | - | - |
| depth 2, kısıtlı (4/4) | 2 | 4 / 4 | 0.02 | 50.000 | 481997 | 2 | 0.00 % | -1.5000 ± 1.5000 | [-4.4400, +1.4400] |

Notlar:

* `Oyun/s` tek iş parçacığı, `--log-top 0` (tüm adaylar loglanır) ile ölçülmüştür;
  gerçek eğitimde `logTopCandidates = 12` kullanılır ve shard yazımı daha ucuzdur.
* `PipBot` sezgisel bir tabandır (afterstate'te `rakipPip - kendiPip` maksimizasyonu);
  uzun oyunlara eğilimlidir, bu yüzden `max_plies = 500` ile bazı oyunlar abort olur.
* Güç farkı ölçümünün standart hatası tabloda verilmiştir; küçük farklar anlamlı değildir.
* Derinlik 2 tek oyun başına ~76 s sürdüğü için örneklem küçüktür (bkz. `Oyun` sütunu);
  derinlik 2 satırlarındaki güç farkı **istatistiksel olarak anlamsızdır**, yalnızca
  maliyet ölçümü olarak okunmalıdır.
