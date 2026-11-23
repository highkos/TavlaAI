# Faz 7-R - gnubg rollout hakemi (R-F madde 2)

| Alan | Deger |
|---|---|
| gnubg | `F:\Program Files (x86)\gnubg\gnubg-cli.exe` |
| Istenen deneme | 1296 |
| Denenen deneme | 36 |
| `Rollout done` satiri | var |
| Equity okundu | **hayir** |
| Pozisyon | 200 |
| Aday/pozisyon | 2 |
| Durum | **olculemez** |

**Gerekce.** gnubg 1.08.003-mingw 'rollout' komutu calisir ama equity basmaz; 'eval' rollout sonucunu dondurmez; Python API'sinde rollout fonksiyonu yoktur. R-F madde 2 uyarinca satir 'olculemez' isaretlendi.

**Yerine koyulan olcum.** ER cozunurluk tabaninin olculebilir karsiligi: 2-ply hakemin 4-ply `hint` hakemine gore ER'si (R-F madde 1).

## Notlar

- Rollout sonucu okunamadigi icin sifir uydurulmadi (Kural 6).
- Maliyet: 36 deneme ~30 s (0-ply chequerplay, yogun CPU); 1296 deneme ~18 dk; 200 pozisyon x 2 aday = 400 rollout -> ~120 saat tek cekirdek.
- Ayni buyukluk `gnubg_ladder.py --deep` ile olculur.

