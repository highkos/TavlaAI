using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Backgammon.Core;
using Backgammon.Inference;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 6 v3 Bolum 12.3 — Asama C (veri motoru) testleri: 60, 61, 62, 65 (C# tarafi), 66.
    /// </summary>
    [TestFixture]
    public sealed class StageCDataEngineTests
    {
        private static string TempDir(string name)
        {
            string dir = Path.Combine(Path.GetTempPath(), "tavla_stagec", name);
            if (Directory.Exists(dir))
            {
                Directory.Delete(dir, recursive: true);
            }

            Directory.CreateDirectory(dir);
            return dir;
        }

        private static SelfPlayConfig MakeConfig(int games, int threads, int dupCap, ulong seed)
        {
            return new SelfPlayConfig
            {
                ModelPath = InferenceTestSupport.ModelPath,
                Games = games,
                Seed = seed,
                Threads = threads,
                OutputDir = Path.Combine(Path.GetTempPath(), "tavla_stagec", "cfg"),
                ShardPrefix = "t",
                DepthPly = 0,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                LogTopCandidates = 4,
                ExplorationPlies = 10,
                SelectionTemperature = 0.05f,
                PolicyTemperature = 1.0f,
                MaxPlies = 500,
                Gzip = false,
                GamesPerShard = 0,
                PoolFraction = 0f,
                MaxBatch = 2048,
                IntraOpThreads = 1,
                UseCuda = false,
                DupCap = dupCap,
            };
        }

        private static List<ShardGame> Play(SelfPlayConfig config)
        {
            OnnxEvaluatorOptions options = config.ToEvaluatorOptions();
            SearchSettings settings = config.ToSearchSettings();

            using OnnxModelHandle model = OnnxModelHandle.Load(config.ModelPath!, options);
            using var learner = new SelfPlayAgent(model, options, settings);
            using var runner = new SelfPlayRunner(config, learner, null, config.Seed);

            var results = new List<ShardGame>(config.Games);
            for (int i = 0; i < config.Games; i++)
            {
                ulong gameId = (ulong)(i + 1);
                runner.ResetSeed(config.Seed + gameId);
                results.Add(runner.PlayGame(gameId, poolGame: false, learnerSide: 0));
            }

            return results;
        }

        private static string[] CommonArgs(string outDir, int games, int threads, ulong seed)
        {
            return new[]
            {
                "--model", InferenceTestSupport.ModelPath,
                "--games", games.ToString(),
                "--seed", seed.ToString(),
                "--threads", threads.ToString(),
                "--depth", "0",
                "--log-top", "4",
                "--exploration", "10",
                "--out", outDir,
                "--prefix", "a",
                "--gzip", "false",
            };
        }

        // ---------------------------------------------------------------- Test 60

        /// <summary>
        /// Test 60: <c>--threads N</c> ciktisi, N ayri <c>--threads 1</c> kosusunun kumesiyle ayni.
        /// </summary>
        /// <remarks>
        /// Oyun tohumu <c>seed(gameIndex) = baseSeed + gameIndex</c> ile is parcacigindan
        /// bagimsiz turetilir (Faz 6 Bolum 7.2); bu yuzden shard baytlari <b>birebir</b> esit olmali.
        /// </remarks>
        [Test]
        public void Test60_SelfPlay_ThreadsAreDeterministic()
        {
            const int Games = 8;
            const ulong Seed = 0x5EEDC0DEUL;

            string dir1 = TempDir("t60_t1");
            string dir4 = TempDir("t60_t4");

            Assert.That(Program.Main(CommonArgs(dir1, Games, 1, Seed)), Is.EqualTo(0), "threads=1 kosusu basarisiz.");
            Assert.That(Program.Main(CommonArgs(dir4, Games, 4, Seed)), Is.EqualTo(0), "threads=4 kosusu basarisiz.");

            string file1 = Path.Combine(dir1, "a_0000.bgsp");
            string file4 = Path.Combine(dir4, "a_0000.bgsp");
            Assert.That(File.Exists(file1), Is.True);
            Assert.That(File.Exists(file4), Is.True);

            byte[] bytes1 = File.ReadAllBytes(file1);
            byte[] bytes4 = File.ReadAllBytes(file4);
            Assert.That(bytes4.Length, Is.EqualTo(bytes1.Length),
                "threads=4 ciktisi threads=1 ile ayni boyutta degil.");
            Assert.That(bytes4, Is.EqualTo(bytes1),
                "threads=4 ciktisi threads=1 ile birebir ayni degil (oyun tohumu is parcacigina bagli).");

            // Oyun kimlikleri de ayni kume olmali.
            List<ShardGame> g1 = ShardReader.ReadFile(file1).Games;
            List<ShardGame> g4 = ShardReader.ReadFile(file4).Games;
            Assert.That(g4.Select(g => g.GameId), Is.EqualTo(g1.Select(g => g.GameId)));
        }

        // ---------------------------------------------------------------- Test 61

        /// <summary>
        /// Test 61: <c>--cuda true --max-batch 2048</c> ile <c>--cuda false</c> olculur, raporlanir ve
        /// <b>hizli olan</b> saglayicinin secili oldugu dogrulanir. Determinizm iddiasi tasimaz
        /// (Faz 6 Bolum 7.3).
        /// </summary>
        /// <remarks>
        /// <para>
        /// Faz 6 v3 Bolum 12.3 "CUDA &gt;= CPU" varsayiyordu. Olcum bu varsayimi <b>curuttu</b>:
        /// ~156 bin parametreli MLP icin cagri basina GPU baslatma maliyeti hesaplamadan buyuktur.
        /// Bu yuzden test "CUDA kazanmali" demiyor; <b>olculen kazananin secili olmasini</b> istiyor.
        /// </para>
        /// <para>
        /// CUDA execution provider yoksa (varsayilan CPU paketi) test <b>Inconclusive</b> olur ve
        /// gerekce yazilir — sessizce gecmez.
        /// </para>
        /// </remarks>
        [Test]
        public void Test61_SelfPlay_GpuBatching_IsFaster()
        {
            const int Games = 20;
            const ulong Seed = 0x6A5UL;

            // Isinma: JIT, ONNX oturumu ve dosya onbellegi ilk olcumu bozmasin.
            MeasureGamesPerSecond(2, Seed, useCuda: false, maxBatch: 2048);

            if (!CudaProviderAvailable())
            {
                double cpuOnly = MeasureGamesPerSecond(Games, Seed, useCuda: false, maxBatch: 2048);
                TestContext.Out.WriteLine("CPU  (max-batch 2048): " + Format(cpuOnly) + " oyun/s");
                Assert.Inconclusive(
                    "CUDA execution provider bu derlemede yok (Microsoft.ML.OnnxRuntime CPU paketi). " +
                    "GPU olcumu icin -p:OnnxRuntimePackage=Microsoft.ML.OnnxRuntime.Gpu ile derleyin " +
                    "(ASSUMPTIONS.md F4-35). CPU olcumu: " + Format(cpuOnly) + " oyun/s.");
            }

            MeasureGamesPerSecond(2, Seed, useCuda: true, maxBatch: 2048);

            // CPU iki kez olculur (CUDA'dan once ve sonra); siralamaya bagli onyargi boyle kirilir.
            double cpuBefore = MeasureGamesPerSecond(Games, Seed, useCuda: false, maxBatch: 2048);
            double cudaGamesPerSecond = MeasureGamesPerSecond(Games, Seed, useCuda: true, maxBatch: 2048);
            double cpuAfter = MeasureGamesPerSecond(Games, Seed, useCuda: false, maxBatch: 2048);
            double cpuGamesPerSecond = Math.Max(cpuBefore, cpuAfter);

            TestContext.Out.WriteLine("CPU  (max-batch 2048): " + Format(cpuGamesPerSecond) +
                " oyun/s (once " + Format(cpuBefore) + ", sonra " + Format(cpuAfter) + ")");
            TestContext.Out.WriteLine("CUDA (max-batch 2048): " + Format(cudaGamesPerSecond) + " oyun/s");

            double ratio = cpuGamesPerSecond > 0.0 ? cudaGamesPerSecond / cpuGamesPerSecond : 0.0;
            TestContext.Out.WriteLine("CUDA/CPU orani: " + Format(ratio) + "x");

            // Karar esigi: CUDA anlamli olcude (>1.2x) hizliysa varsayilan CUDA olmali.
            const double DecisiveMargin = 1.2;
            bool cudaIsDecisivelyFaster = ratio > DecisiveMargin;

            Assert.That(cudaIsDecisivelyFaster, Is.EqualTo(SelfPlayConfig.DefaultUseCuda),
                "Olculen kazanan saglayici ile SelfPlayConfig.DefaultUseCuda uyusmuyor. " +
                "CPU=" + Format(cpuGamesPerSecond) + " oyun/s, CUDA=" + Format(cudaGamesPerSecond) +
                " oyun/s (oran " + Format(ratio) + "x). Karari ml/artifacts/stage_c_gpu_decision.md " +
                "dosyasina yazin ve SelfPlayConfig.DefaultUseCuda sabitini guncelleyin.");
        }

        private static string Format(double value) =>
            value.ToString("F2", System.Globalization.CultureInfo.InvariantCulture);

        private static bool CudaProviderAvailable()
        {
            try
            {
                var options = new OnnxEvaluatorOptions { UseCuda = true };
                using OnnxModelHandle handle = OnnxModelHandle.Load(InferenceTestSupport.ModelPath, options);
                return true;
            }
            catch (Exception)
            {
                return false;
            }
        }

        private static double MeasureGamesPerSecond(int games, ulong seed, bool useCuda, int maxBatch)
        {
            SelfPlayConfig config = MakeConfig(games, 1, 0, seed);
            config.UseCuda = useCuda;
            config.MaxBatch = maxBatch;

            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            Play(config);
            stopwatch.Stop();

            double seconds = stopwatch.Elapsed.TotalSeconds;
            return seconds > 0.0 ? games / seconds : 0.0;
        }

        // ---------------------------------------------------------------- Test 62

        /// <summary>
        /// Test 62: ilk 10 ply'de acilis dagilimi entropisi esigin uzerinde; <c>dup_cap</c> acilisi silmez.
        /// </summary>
        [Test]
        public void Test62_SelfPlay_OpeningDiversity()
        {
            const int Games = 200;
            const ulong Seed = 0x0BE1UL;

            List<ShardGame> noCap = Play(MakeConfig(Games, 1, dupCap: 0, seed: Seed));
            List<ShardGame> withCap = Play(MakeConfig(Games, 1, dupCap: 1, seed: Seed));

            double entropy = OpeningEntropy(noCap);
            TestContext.Out.WriteLine("acilis entropisi: " +
                entropy.ToString("F4", System.Globalization.CultureInfo.InvariantCulture) + " bit");

            // RollOpening 15 farkli sira-disi cift uretir; ust sinir log2(15) = 3.907 bit.
            Assert.That(entropy, Is.GreaterThanOrEqualTo(3.0),
                "Acilis dagilimi entropisi cok dusuk (acilis cesitliligi kaybolmus).");

            int openingNoCap = CountOpeningLearnerDecisions(noCap);
            int openingWithCap = CountOpeningLearnerDecisions(withCap);
            Assert.That(openingNoCap, Is.EqualTo(Games), "Her oyunun acilis karari ogrenen karari olmali.");
            Assert.That(openingWithCap, Is.EqualTo(openingNoCap),
                "dup_cap acilis kararlarini sildi (Faz 6 Bolum 7.5).");
        }

        private static double OpeningEntropy(List<ShardGame> games)
        {
            var counts = new Dictionary<ulong, int>();
            int total = 0;
            foreach (ShardGame game in games)
            {
                if (game.Decisions.Count == 0)
                {
                    continue;
                }

                ShardDecision first = game.Decisions[0];
                if (first.ChosenVector == null)
                {
                    continue;
                }

                ulong key = DupCapFilter.Fingerprint(first.ChosenVector);
                counts.TryGetValue(key, out int c);
                counts[key] = c + 1;
                total++;
            }

            if (total == 0)
            {
                return 0.0;
            }

            double h = 0.0;
            foreach (int c in counts.Values)
            {
                double p = (double)c / total;
                h -= p * Math.Log(p, 2.0);
            }

            return h;
        }

        private static int CountOpeningLearnerDecisions(List<ShardGame> games)
        {
            int n = 0;
            foreach (ShardGame game in games)
            {
                if (game.Decisions.Count > 0 && game.Decisions[0].IsLearner)
                {
                    n++;
                }
            }

            return n;
        }

        // ---------------------------------------------------------------- Test 65

        /// <summary>
        /// Test 65 (C# tarafi): shard v1'de <c>finalProbs</c>/<c>outcomeProbs</c> alani yok;
        /// 6 sinifli hedef <c>winner</c> + <c>resultType</c>'tan turetilir.
        /// </summary>
        [Test]
        public void Test65_Shard_NoOutcomeProbsField()
        {
            string[] forbidden = { "FinalProbs", "OutcomeProbs", "FinalProbabilities", "OutcomeProbabilities" };

            foreach (Type type in new[] { typeof(ShardGame), typeof(ShardDecision) })
            {
                foreach (string name in forbidden)
                {
                    Assert.That(type.GetProperty(name, BindingFlags.Public | BindingFlags.Instance), Is.Null,
                        type.Name + "." + name + " shard v1'de bulunmamali (Faz 6 Bolum 7.1).");
                    Assert.That(type.GetField(name, BindingFlags.Public | BindingFlags.Instance), Is.Null,
                        type.Name + "." + name + " shard v1'de bulunmamali (Faz 6 Bolum 7.1).");
                }
            }

            // winner + resultType -> 6 sinifli tek-sicak hedef turetilebilir olmali.
            List<ShardGame> games = Play(MakeConfig(4, 1, dupCap: 0, seed: 0x65UL));
            Assert.That(games, Is.Not.Empty);

            foreach (ShardGame game in games)
            {
                Assert.That(game.IsAborted, Is.False);
                Assert.That(game.Winner, Is.AnyOf((sbyte)1, (sbyte)-1), "Kazanan +1/-1 olmali.");
                Assert.That(game.ResultType, Is.InRange((byte)1, (byte)3), "resultType 1..3 olmali.");
                Assert.That(game.ResultPoints, Is.EqualTo(game.ResultType),
                    "Kup degeri 1 iken resultPoints == resultType olmali.");
            }

            // Yaz/oku turu: 6 sinifli turetme icin gereken alanlar korunuyor mu?
            string dir = TempDir("t65");
            string path = Path.Combine(dir, "a.bgsp");
            ShardHeader header = ShardHeader.Create(
                (uint)BackgammonVectorizer.FeatureVersion, 1u, 4u);
            ShardWriter.WriteFile(path, header, games, gzip: false);

            List<ShardGame> back = ShardReader.ReadFile(path).Games;
            Assert.That(back, Has.Count.EqualTo(games.Count));
            for (int i = 0; i < games.Count; i++)
            {
                Assert.That(back[i].Winner, Is.EqualTo(games[i].Winner));
                Assert.That(back[i].ResultType, Is.EqualTo(games[i].ResultType));
                Assert.That(back[i].ResultPoints, Is.EqualTo(games[i].ResultPoints));
            }
        }

        // ---------------------------------------------------------------- Test 66

        /// <summary>
        /// Test 66: ayni parmak izi <c>dup_cap</c>'ten fazla gorulurse egitimden cikarilir;
        /// acilis pozisyonu korunur.
        /// </summary>
        [Test]
        public void Test66_DupCap_Works()
        {
            const int Cap = 3;
            const int OpeningPlies = 10;
            const int Decisions = 20;

            var vector = new float[ShardConstants.VectorSize];
            for (int i = 0; i < vector.Length; i++)
            {
                vector[i] = i * 0.5f;
            }

            ShardGame game = MakeSyntheticGame(gameId: 1, decisions: Decisions, vector: vector);
            var games = new List<ShardGame> { game };

            DupCapStats stats = DupCapFilter.Apply(games, Cap, OpeningPlies);

            Assert.That(stats.Cap, Is.EqualTo(Cap));
            Assert.That(stats.OpeningExempt, Is.EqualTo(OpeningPlies), "Ilk 10 ply muaf olmali.");
            Assert.That(stats.Kept, Is.EqualTo(Cap), "Sinir kadar karar tutulmali.");
            Assert.That(stats.Capped, Is.EqualTo(Decisions - OpeningPlies - Cap), "Fazlasi elenmeli.");

            for (int d = 0; d < Decisions; d++)
            {
                ShardDecision decision = game.Decisions[d];
                bool capped = (decision.Flags & ShardDecisionFlags.DupCapped) != 0;

                if (d < OpeningPlies + Cap)
                {
                    Assert.That(capped, Is.False, "ply " + d + " elenmemeliydi.");
                    Assert.That(decision.IsLearner, Is.True, "ply " + d + " ogrenen karari kalmaliydi.");
                    Assert.That(decision.Q, Is.Not.Null, "ply " + d + " aday yuku korunmaliydi.");
                }
                else
                {
                    Assert.That(capped, Is.True, "ply " + d + " elenmeliydi.");
                    Assert.That(decision.IsLearner, Is.False, "elenen karar ogrenen sayilmamali.");
                    Assert.That(decision.Q, Is.Null, "elenen kararin aday yuku atilmali.");
                    Assert.That(decision.PolicyTargetCs, Is.Null);
                    Assert.That(decision.CandidateVectors, Is.Null);
                    Assert.That(decision.ChosenVector, Is.Not.Null,
                        "Elenen karar TD zinciri halkasi olarak kalmali (chosenVector korunur).");
                }
            }

            // Acilis pozisyonu (ply 0) her zaman korunur.
            Assert.That(game.Decisions[0].IsLearner, Is.True, "Acilis pozisyonu asla silinmez.");

            // cap = 0 -> hicbir sey degismez.
            ShardGame untouched = MakeSyntheticGame(gameId: 2, decisions: Decisions, vector: vector);
            DupCapStats off = DupCapFilter.Apply(new List<ShardGame> { untouched }, 0, OpeningPlies);
            Assert.That(off.Capped, Is.EqualTo(0));
            Assert.That(untouched.Decisions.All(d => d.IsLearner), Is.True);

            // Determinizm: oyun sirasi karismis olsa da sonuc ayni olmali (GameId'ye gore siralanir).
            ShardGame a = MakeSyntheticGame(gameId: 10, decisions: Decisions, vector: vector);
            ShardGame b = MakeSyntheticGame(gameId: 11, decisions: Decisions, vector: vector);
            var forward = new List<ShardGame> { a, b };
            DupCapStats s1 = DupCapFilter.Apply(forward, Cap, OpeningPlies);

            ShardGame a2 = MakeSyntheticGame(gameId: 10, decisions: Decisions, vector: vector);
            ShardGame b2 = MakeSyntheticGame(gameId: 11, decisions: Decisions, vector: vector);
            var reversed = new List<ShardGame> { b2, a2 };
            DupCapStats s2 = DupCapFilter.Apply(reversed, Cap, OpeningPlies);

            Assert.That(s2.Capped, Is.EqualTo(s1.Capped), "dup_cap oyun sirasindan bagimsiz olmali.");
            Assert.That(s2.Kept, Is.EqualTo(s1.Kept));
            Assert.That(a2.Decisions.Select(d => d.IsLearner), Is.EqualTo(a.Decisions.Select(d => d.IsLearner)));
            Assert.That(b2.Decisions.Select(d => d.IsLearner), Is.EqualTo(b.Decisions.Select(d => d.IsLearner)));
        }

        private static ShardGame MakeSyntheticGame(ulong gameId, int decisions, float[] vector)
        {
            var game = new ShardGame
            {
                GameId = gameId,
                LearnerSide = 0,
                Winner = 1,
                ResultType = 1,
                ResultPoints = 1,
            };

            for (int d = 0; d < decisions; d++)
            {
                var chosen = new float[vector.Length];
                Array.Copy(vector, chosen, vector.Length);

                game.Decisions.Add(new ShardDecision
                {
                    Mover = (sbyte)(d % 2 == 0 ? 1 : -1),
                    Flags = ShardDecisionFlags.IsLearner,
                    CandidateTotal = 2,
                    SearchValue = 0.1f,
                    ChosenVector = chosen,
                    Q = new[] { 0.1f, 0.05f },
                    PolicyTargetCs = new[] { 0.6f, 0.4f },
                    CandidateVectors = new float[2 * vector.Length],
                });
            }

            return game;
        }
    }
}
