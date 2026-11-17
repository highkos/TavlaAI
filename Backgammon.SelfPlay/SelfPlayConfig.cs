using System;
using System.IO;
using System.Text.Json;
using Backgammon.Core;
using Backgammon.Inference;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.1: self-play surucusu yapilandirmasi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Tum alanlar JSON'dan yuklenebilir (buyuk/kucuk harf duyarsiz, yorum ve sondaki virgul
    /// kabul edilir). Verilmeyen alanlar varsayilan degerini korur.
    /// </para>
    /// <para>
    /// <b>Yer tutucu degerler</b> (Bolum 6.6): <see cref="DepthPly"/> = 1,
    /// <see cref="LogTopCandidates"/> = 12, <see cref="ExplorationPlies"/> = 10,
    /// <see cref="SelectionTemperature"/> = 0.05. Bunlar <b>ayarlanmamis</b> degerlerdir.
    /// </para>
    /// </remarks>
    public sealed class SelfPlayConfig
    {
        /// <summary>Ogrenen agin ONNX model yolu (zorunlu).</summary>
        public string? ModelPath { get; set; }

        /// <summary>Havuz rakip modeli; <c>null</c> ise yalnizca oz-oyun.</summary>
        public string? PoolModelPath { get; set; }

        /// <summary>Uretilecek oyun sayisi.</summary>
        public int Games { get; set; } = 100;

        /// <summary>RNG tohumu. Ayni tohum + tek is parcacigi = ayni shard'lar.</summary>
        public ulong Seed { get; set; } = 1UL;

        /// <summary>Is parcacigi sayisi (her biri kendi evaluator/workspace/RNG'sine sahiptir).</summary>
        public int Threads { get; set; } = 1;

        /// <summary>Cikis klasoru.</summary>
        public string OutputDir { get; set; } = ".";

        /// <summary>Shard dosya adi oneki.</summary>
        public string ShardPrefix { get; set; } = "selfplay";

        /// <summary>Chance katmani sayisi (Faz 3 v7 <c>SearchSettings.DepthPly</c>).</summary>
        public int DepthPly { get; set; } = 1;

        /// <summary>
        /// Faz 7 §5.4 / Test 100-101: damitma modu. Varsayilan <c>false</c>.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <c>true</c> iken: (a) arama <see cref="SearchSettings.DistillMode"/> ile calisir ve
        /// <see cref="SearchResult.RootValue"/> doldurulur, (b) ogrenen kararlari
        /// <see cref="ShardDecisionFlags.Distilled"/> ile isaretlenir, (c) <see cref="DepthPly"/>
        /// uretim sinirinin (<see cref="SearchSettings.ProductionDepthPly"/>) <b>uzerine</b>
        /// cikabilir — damitma cevrimdisi bir ogretmendir (F7-15).
        /// </para>
        /// <para>
        /// <b>Shard bicimi degismez:</b> politika hedefi <c>q</c> alaninda, deger hedefi
        /// <c>searchValue</c> alaninda tasinir (F7-16).
        /// </para>
        /// </remarks>
        public bool DistillMode { get; set; }

        /// <summary>Kok aday kisiti (veri uretimi icin onerilen 0).</summary>
        public int MaxCandidatesRoot { get; set; }

        /// <summary>Ic dugum aday kisiti.</summary>
        public int MaxCandidatesInner { get; set; }

        /// <summary>Karar basina loglanan en fazla aday sayisi (0 = tumu).</summary>
        public int LogTopCandidates { get; set; } = 12;

        /// <summary>Kesif (ornekleme) uygulanan ilk karar sayisi.</summary>
        public int ExplorationPlies { get; set; } = 10;

        /// <summary>Kesif sicakligi (yalnizca hamle secimi; politika hedefinden bagimsiz).</summary>
        public float SelectionTemperature { get; set; } = 0.05f;

        /// <summary>C# kok politika hedefi sicakligi (yalnizca capraz dogrulama icin).</summary>
        public float PolicyTemperature { get; set; } = 1.0f;

        /// <summary>Oyun basina en fazla karar; asilirsa oyun <c>aborted</c> isaretlenir.</summary>
        public int MaxPlies { get; set; } = 500;

        /// <summary>Shard'lari gzip'le.</summary>
        public bool Gzip { get; set; }

        /// <summary>Shard basina oyun sayisi (0 = tek shard).</summary>
        public int GamesPerShard { get; set; }

        /// <summary>Havuz rakipli oyun orani (0 = yalnizca oz-oyun).</summary>
        public float PoolFraction { get; set; }

        /// <summary>
        /// Olculmus varsayilan yurutme saglayicisi. Faz 6 Asama C'de CPU ve CUDA
        /// karsilastirildi (bkz. <c>ml/artifacts/stage_c_gpu_decision.md</c>): bu makinede
        /// CPU her derinlikte 3,5-6x daha hizli. Baska donanimda CUDA kazanirsa bu sabit
        /// cevrilir; Test 61 uyusmazligi yakalar.
        /// </summary>
        public const bool DefaultUseCuda = false;

        /// <summary>CUDA execution provider kullan.</summary>
        public bool UseCuda { get; set; } = DefaultUseCuda;

        /// <summary>Tek ONNX calistirmasinda islenecek en buyuk satir sayisi.</summary>
        public int MaxBatch { get; set; } = 2048;

        /// <summary>Intra-op is parcacigi sayisi (determinizm icin 1).</summary>
        public int IntraOpThreads { get; set; } = 1;

        /// <summary>
        /// Ayni afterstate parmak izine sahip kararin en fazla kac kez egitime
        /// tutulacagi (0 = kapali). Faz 6 Bolum 7.5.
        /// </summary>
        /// <remarks>
        /// Tekrarlar oyun sonrasi <b>deterministik</b> bir gecisde ayiklanir
        /// (<see cref="DupCapFilter"/>); boylece <c>--threads</c> sayisi sonucu degistirmez.
        /// Acilis pozisyonu (ply 0) asla elenmez.
        /// </remarks>
        public int DupCap { get; set; } = 3;

        /// <summary>
        /// Sifirdan buyukse self-play yerine <c>RandomBot</c>'a karsi bu kadar oyun oynanir
        /// (Faz 4 v3 Bolum 9, Asama C kabul olcumu).
        /// </summary>
        public int EvalRandomGames { get; set; }

        /// <summary>
        /// Sifirdan buyukse self-play yerine <c>PipBot</c>'a karsi bu kadar oyun oynanir
        /// (Faz 4 v3 Bolum 9, Asama D kabul olcumu).
        /// </summary>
        public int EvalPipGames { get; set; }

        /// <summary>
        /// Sifirdan buyukse self-play yerine <see cref="EvalModelPath"/> modeline karsi bu kadar
        /// oyun oynanir (onceki checkpoint / havuz uyesi karsilastirmasi).
        /// </summary>
        public int EvalModelGames { get; set; }

        /// <summary><see cref="EvalModelGames"/> icin rakip ONNX modeli.</summary>
        public string? EvalModelPath { get; set; }

        /// <summary>
        /// Doluysa degerlendirme raporlari bu yola JSON olarak yazilir (Python ligi okur).
        /// </summary>
        public string? EvalJsonPath { get; set; }

        /// <summary>JSON dosyasindan yapilandirma yukler.</summary>
        public static SelfPlayConfig Load(string path)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("path bos olamaz.", nameof(path));
            }

            string json = File.ReadAllText(path);
            return Parse(json);
        }

        /// <summary>JSON metninden yapilandirma cozer.</summary>
        public static SelfPlayConfig Parse(string json)
        {
            if (json == null)
            {
                throw new ArgumentNullException(nameof(json));
            }

            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            };

            SelfPlayConfig? cfg = JsonSerializer.Deserialize<SelfPlayConfig>(json, options);
            if (cfg == null)
            {
                throw new InvalidDataException("Yapilandirma JSON'u bos.");
            }

            return cfg;
        }

        /// <summary>Alanlari dogrular.</summary>
        public void Validate()
        {
            if (string.IsNullOrEmpty(ModelPath))
            {
                throw new ArgumentException("ModelPath zorunludur.", nameof(ModelPath));
            }

            if (Games < 0)
            {
                throw new ArgumentException("Games negatif olamaz.", nameof(Games));
            }

            if (Threads < 1)
            {
                throw new ArgumentException("Threads >= 1 olmalidir.", nameof(Threads));
            }

            if (DepthPly < 0 || DepthPly > SearchWorkspace.MaxSupportedPly)
            {
                throw new ArgumentException(
                    "DepthPly 0.." + SearchWorkspace.MaxSupportedPly + " araliginda olmalidir.", nameof(DepthPly));
            }

            // F7-09: self-play bir URETIM yoludur; depth 2 butce disidir (p95 4,50 s > 2 s).
            // Daha derin arama yalnizca cevrimdisi damitma hedefi uretiminde mesrudur (F7-15).
            if (DistillMode)
            {
                if (DepthPly <= SearchSettings.ProductionDepthPly)
                {
                    throw new ArgumentException(
                        "DistillMode icin DepthPly > " + SearchSettings.ProductionDepthPly +
                        " olmalidir (damitma, uretimden daha derin bir aramayi taklit eder).",
                        nameof(DepthPly));
                }
            }
            else if (DepthPly > SearchSettings.ProductionDepthPly)
            {
                throw new ArgumentException(
                    "DepthPly en fazla " + SearchSettings.ProductionDepthPly +
                    " olabilir (F7-09: depth 2 p95 4,50 s > 2 s butcesi).", nameof(DepthPly));
            }

            if (MaxCandidatesRoot < 0)
            {
                throw new ArgumentException("MaxCandidatesRoot negatif olamaz.", nameof(MaxCandidatesRoot));
            }

            if (MaxCandidatesInner < 0)
            {
                throw new ArgumentException("MaxCandidatesInner negatif olamaz.", nameof(MaxCandidatesInner));
            }

            if (LogTopCandidates < 0)
            {
                throw new ArgumentException("LogTopCandidates negatif olamaz.", nameof(LogTopCandidates));
            }

            if (ExplorationPlies < 0)
            {
                throw new ArgumentException("ExplorationPlies negatif olamaz.", nameof(ExplorationPlies));
            }

            if (!(SelectionTemperature > 0f))
            {
                throw new ArgumentException("SelectionTemperature > 0 olmalidir.", nameof(SelectionTemperature));
            }

            if (!(PolicyTemperature > 0f))
            {
                throw new ArgumentException("PolicyTemperature > 0 olmalidir.", nameof(PolicyTemperature));
            }

            if (MaxPlies < 1)
            {
                throw new ArgumentException("MaxPlies >= 1 olmalidir.", nameof(MaxPlies));
            }

            if (GamesPerShard < 0)
            {
                throw new ArgumentException("GamesPerShard negatif olamaz.", nameof(GamesPerShard));
            }

            if (PoolFraction < 0f || PoolFraction > 1f)
            {
                throw new ArgumentException("PoolFraction 0..1 araliginda olmalidir.", nameof(PoolFraction));
            }

            if (PoolFraction > 0f && string.IsNullOrEmpty(PoolModelPath))
            {
                throw new ArgumentException(
                    "PoolFraction > 0 iken PoolModelPath zorunludur.", nameof(PoolModelPath));
            }

            if (MaxBatch < 1)
            {
                throw new ArgumentException("MaxBatch >= 1 olmalidir.", nameof(MaxBatch));
            }

            if (IntraOpThreads < 1)
            {
                throw new ArgumentException("IntraOpThreads >= 1 olmalidir.", nameof(IntraOpThreads));
            }

            if (DupCap < 0)
            {
                throw new ArgumentException("DupCap negatif olamaz.", nameof(DupCap));
            }

            if (EvalRandomGames < 0)
            {
                throw new ArgumentException("EvalRandomGames negatif olamaz.", nameof(EvalRandomGames));
            }

            if (EvalPipGames < 0)
            {
                throw new ArgumentException("EvalPipGames negatif olamaz.", nameof(EvalPipGames));
            }

            if (EvalModelGames < 0)
            {
                throw new ArgumentException("EvalModelGames negatif olamaz.", nameof(EvalModelGames));
            }

            if (EvalModelGames > 0 && string.IsNullOrEmpty(EvalModelPath))
            {
                throw new ArgumentException("EvalModelGames > 0 icin EvalModelPath gerekli.", nameof(EvalModelPath));
            }
        }

        /// <summary>
        /// Faz 3 v7 arama ayarlari. Bolum 5.1: <c>ExactRootScores = true</c> (zorunlu),
        /// <c>UsePolicyOrdering = true</c>, <c>MaxCandidatesRoot</c> yapilandirmadan.
        /// </summary>
        public SearchSettings ToSearchSettings()
        {
            return new SearchSettings
            {
                DepthPly = DepthPly,
                MaxCandidatesRoot = MaxCandidatesRoot,
                MaxCandidatesInner = MaxCandidatesInner,
                UseAlphaBeta = true,
                UseStar1 = true,
                UseEvalCache = true,
                UsePolicyOrdering = true,
                ExactRootScores = true,
                PolicyTemperature = PolicyTemperature,
                DistillMode = DistillMode
            };
        }

        /// <summary>ONNX oturum secenekleri.</summary>
        public OnnxEvaluatorOptions ToEvaluatorOptions()
        {
            return new OnnxEvaluatorOptions
            {
                UseCuda = UseCuda,
                IntraOpThreads = IntraOpThreads,
                InterOpThreads = 1,
                MaxBatch = MaxBatch,
                DisableTf32 = true
            };
        }
    }
}
