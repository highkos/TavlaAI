# EVREN on-kontrolu (F7-119)

- surum: 1
- GPU zorunlu: hayir
- cihaz: `cpu`
- sonuc: **HAZIR**
- sure: 44.88 s

| kontrol | durum | ayrinti |
| --- | --- | --- |
| `python` | PASS | 3.10.11 (gerekli >= 3.10) |
| `paket:numpy` | PASS | 2.2.6 |
| `paket:torch` | PASS | 2.5.1+cu121 |
| `paket:onnx` | PASS | 1.23.2 |
| `paket:onnxruntime` | PASS | 1.23.2 |
| `torch:cuda-derlemesi` | PASS | cuda=12.1 |
| `torch:cuda` | PASS | kullanilabilir=True, aygit=1, ad=NVIDIA GeForce GTX 1650, bellek=4.0 GB |
| `torch:gpu-matmul` | PASS | ok |
| `onnxruntime:cpu` | PASS | AzureExecutionProvider,CPUExecutionProvider |
| `onnxruntime:gpu` | PASS | CUDAExecutionProvider=False |
| `gnubg` | PASS | F:\Program Files (x86)\gnubg\gnubg-cli.exe |
| `veri:egitim` | PASS | policy_30k_rd.npz (12.6 MB) |
| `veri:korpus` | PASS | reference_corpus_v2.json (16.3 MB) |
| `model:ppg` | PASS | model.onnx (6.9 MB) |
| `disk` | PASS | bos=415.2 GB |
| `yazma-izni` | PASS | ml\runs |
| `boru-hatti:ileri` | PASS | probs=(4, 6) logits=(4, 1) params=27235 |
| `boru-hatti:antisimetri` | PASS | |f(x)+f(Tx)|=4.47e-08 |
| `boru-hatti:onnx` | PASS | delta=1.79e-07, cikti=2 |
