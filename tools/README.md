# tools/ — uzak eğitim işçisi

Yerel makine tam kapasiteyle çalışırken, kiralık sunucunun CPU'sunu adil
kullanım sınırının altında tutarak ikinci bir işçi olarak kullanmak için
üç betik.

| Betik | Nerede çalışır | Ne yapar |
|---|---|---|
| `CpuCap.ps1` | her iki makine | Bir komutu sert CPU tavanlı bir Job Object içinde çalıştırır |
| `RemoteAgent.ps1` | uzak sunucu (servis) | `queue/` klasörünü yoklar, gelen işleri tavan altında çalıştırır |
| `RemoteJob.ps1` | yerel makine | Uzak sunucuya iş gönderir, günlüğü ve çıktıları geri toplar |

## Neden bu mimari

Uzak sunucu **3 vCPU, 4 GB RAM, GPU yok**. Model eğitimini hızlandırmaz:
CPU-only torch, yereldeki CUDA GPU'nun yanında yuvarlama hatasıdır. Uzak
sunucunun gerçek değeri, **yerel makineyle hiç rekabet etmeyen ayrı bir
makine** olmasıdır. Oraya GPU eğitimi değil, CPU'ya bağlı ve utandırıcı
derecede paralel işler verilir:

- gnubg 2-ply etiketleme (damıtma korpusu)
- gnubg ER ölçümü
- ONNX çıkarımı / toplu değerlendirme

Yerel makine tavanlanmaz; eğitim doğrudan tam kapasiteyle koşar.

## CPU tavanı kalibrasyonu

Tavan çekirdek tarafından uygulanır (`JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP`),
anketle değil. Çocuk süreç `CREATE_SUSPENDED` ile doğar, iş nesnesine atanır,
sonra devam ettirilir; böylece torun süreçler tavanın dışına kaçamaz.

Windows istenen oranı düşük değerlerde yaklaşık **%14 aşıyor**. 3 vCPU'luk
uzak sunucuda ölçüldü (iş nesnesi muhasebesi, 10 sn, 12 iş parçacığı):

| İstenen | Ölçülen çekirdek | Gerçekleşen |
|---:|---:|---:|
| 10 | 0,35 | %11,7 |
| 20 | 0,69 | %23,1 |
| 22 | 0,75 | %25,1 |
| 25 | 0,85 | %28,4 |
| 50 | 1,67 | %55,9 |
| 100 | 2,99 | %100 |

Bu yüzden **varsayılan 20**, 25 değil: %25'lik adil kullanım tavanının
altında kalır. Yerel makinede aynı betik 12 mantıksal CPU'da 11,61 → 3,08
çekirdek verdi (tavansız → %25 istek).

## Kurulum (uzak sunucu)

Tek seferlik. `C:\bgwork` altında:

```
CpuCap.ps1          tavan başlatıcı
RemoteAgent.ps1     kuyruk işçisi
python\             Python 3.10.11 embeddable + numpy + onnxruntime
  sitecustomize.py  PYTHONPATH'i geri kazandırır (aşağıya bak)
gnubg\              gnubg-cli.exe ve veri dosyaları (138 dosya, 65 MB)
queue\ done\ logs\ archive\
```

Agent, `nssm` ile `TavlaAgent` servisi olarak kurulur ve otomatik başlar.
Durumu `C:\bgwork\agent.status` dosyasındadır (pid, state, son güncelleme).

### Gömülü Python ve `sitecustomize.py`

Embeddable Python dağıtımı bir `python310._pth` dosyasıyla gelir. Böyle bir
dosya varken CPython **`sys.path[0]` eklemez ve `PYTHONPATH`/`PYTHONHOME`
değişkenlerini yok sayar**. Bu yüzden `gnubg_er.py` gibi yanındaki `equity.py`
dosyasını içe aktaran çok dosyalı işler `ModuleNotFoundError` veriyordu.

Çözüm uzak kuruluma özgüdür, depoya yayılmaz: `python\sitecustomize.py`
`PYTHONPATH`'i okuyup `sys.path`'e geri ekler. `site` hâlâ içe aktarıldığı
için bu dosya otomatik yüklenir. `RemoteJob.ps1` de `PYTHONPATH`'i varsayılan
olarak iş klasörüne ayarlar, böylece ek parametre gerekmez.

### gnubg oyuncu adları

`gnubg_er.py` pip satırını `MONSTER`/`gnubg` adlarıyla eşleştirir. gnubg bu
adları `~/.gnubg/gnubgautorc` dosyasından okur; dosya yoksa insan oyuncu
işletim sistemi kullanıcı adını alır (uzak sunucuda `SYSTEM`) ve ölçüm
başarısız olur. Bu yüzden `_settings()` artık `set player 0 name gnubg` ve
`set player 1 name MONSTER` komutlarını da gönderir; adlar konumdan bağımsız
eşleştirildiği için zaten doğru olan kurulumlarda etkisizdir.

## Yerel/uzak parite

`model_v30.onnx`, `reference_positions.json`, `--plies 0 --criterion value`,
20 pozisyon:

| | Yerel | Uzak |
|---|---:|---:|
| Ortalama ER | 0,00645 | 0,00650 |
| Maksimum ER | 0,0720 | 0,0720 |
| Tam eşleşme | %75 | %75 |
| `modelValue` farkı | — | 20/20 bit-bit aynı |

Tek fark `double-4-steps-white` pozisyonunda gnubg'nin **kendi** 0-ply
değeri: 0,240 vs 0,241. Olasılık satırı (`0.578 0.190 0.014 - 0.422 0.116
0.004`) iki tarafta da aynı; fark 4. ondalıkta. Aynı ikili dosyalar ve aynı
veri dosyaları (MD5 eşit) kullanıldığı, `gnubgautorc` kopyalanması sonucu
değiştirmediği için geriye kalan tek açıklama gnubg'nin SIMD kod yolu
seçimidir (sanal CPU farklı CPUID bildiriyor). 0,00005'lik ortalama fark
ölçüm gürültüsünün altında; uzak ölçümler yerel ile değiştirilebilir.

## Kullanım

Kimlik bilgileri ortam değişkenlerinden okunur, betiğe yazılmaz:

```powershell
$env:TAVLAI_REMOTE_HOST = '192.227.177.143'
$env:TAVLAI_REMOTE_USER = 'Administrator'
$env:TAVLAI_REMOTE_PASS = '...'
```

İş gönder:

```powershell
.\tools\RemoteJob.ps1 -Name label-0001 `
	-CommandLine 'C:\bgwork\python\python.exe gnubg_er.py --in in.json --out out.json' `
	-Upload 'ml\artifacts\label_in.json' `
	-Download 'out.json'
```

Günlük ve indirilen dosyalar `ml\runs\remote\<Name>\` altına düşer
(`ml/runs/` zaten `.gitignore` içinde).

İş başına ortam değişkeni gerekirse `-Env` verilir (varsayılan:
`PYTHONPATH` = iş klasörü):

```powershell
.\tools\RemoteJob.ps1 -Name hint-0001 -CommandLine '...' `
	-Env @{ HOME = 'C:\bgwork\home' }
```

`-Env` bir hashtable olduğu için betik **ayrı bir `powershell.exe -File`
süreciyle değil, doğrudan** çağrılmalıdır; `-File` üzerinden tüm argümanlar
metne dönüşür.

Yerel eğitim tavanlanmaz, paralel koşabilir:

```powershell
python ml\train_v2.py --steps 20000 ...
```

## Sınırlar

- Uzak sunucu **paylaşımlı bir barındırma kutusu**: IIS, MSSQL, MailEnable ve
  `Backgammon.Server` çalışıyor. 4 GB RAM'in ~2,3 GB'ı boş. Ağır iş
  göndermeden önce boş belleği kontrol et.
- Uzak sunucuda **GPU yok**; torch CPU-only kurulmadı. Oraya yalnızca
  numpy/onnxruntime/gnubg işleri gider.
- `sc.exe \\host` ve SMB `C$` dışında kanal yok: WinRM (5985/5986) kapalı,
  `schtasks /s` desteklenmiyor, WMI/DCOM kapalı.
- Servis olarak başlatılan `cmd.exe` içinden dış süreçlerin `>` / `>>`
  yönlendirmesi çıktı yakalamıyor. Bu yüzden `CpuCap.ps1 -LogPath`
  kullanılır; agent her işi böyle çalıştırır.
- gnubg kopyası tam kurulum değil: `locale doc fonts icons pixmaps sounds
  textures scripts PythonLib man Shaders` klasörleri ve `unins000.*`
  dışarıda bırakıldı. Bu yüzden gnubg "sound file ... doesn't exist"
  uyarıları basar; değerlendirmeyi etkilemez.
- `-CommandLine` içinde **iç içe tırnak kullanma**. `python.exe -c "..."` gibi
  bir komut satırı `CpuCap.ps1` üzerinden geçerken bozulur ve iş sessizce
  `exit=1` ile biter. Çok satırlı Python için betiği `-Upload` ile gönder ve
  `python.exe betik.py` olarak çağır.
