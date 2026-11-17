using System;
using System.Threading.Tasks;
using Backgammon.Core;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8, Test 12 / 14: kova basina allocation ve is parcacigi guvenligi.
    /// </summary>
    [TestFixture]
    public sealed class ConcurrencyAndAllocationTests
    {
        private static readonly int[] Buckets = { 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048 };

        private static VectorizerScalars MoneyScalars()
        {
            return new VectorizerScalars(1, 0, 0, 0, 0, false);
        }

        /// <summary>
        /// Rastgele oyunlar oynayarak en az <paramref name="minCount"/> terminal-olmayan
        /// afterstate toplar (kova 2048'e kadar olcmek icin yeterli cesitlilik).
        /// </summary>
        private static AfterStateList BuildLargeList(int minCount, out int nonTerminal)
        {
            var list = new AfterStateList(4096);
            nonTerminal = 0;

            var rng = new Xoshiro256StarStar(0x5EED1234UL);
            var state = new BackgammonState();
            var scratch = new AfterStateList();
            var tmp = new BackgammonState();

            while (nonTerminal < minCount)
            {
                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);

                int plies = 0;
                while (plies < 200 && nonTerminal < minCount)
                {
                    GameResult result;
                    if (BackgammonEngine.IsGameOver(state, out result))
                    {
                        break;
                    }

                    BackgammonEngine.RollDice(state, rng);
                    scratch.Clear();
                    LegalMoveGenerator.GenerateAfterStates(state, EngineSettings.Default, scratch);

                    if (scratch.Count == 0)
                    {
                        BackgammonEngine.PassTurn(state);
                        plies++;
                        continue;
                    }

                    for (int i = 0; i < scratch.Count && nonTerminal < minCount; i++)
                    {
                        if (scratch.IsTerminal[i])
                        {
                            continue;
                        }

                        tmp.CopyFrom(state);
                        BackgammonEngine.LoadAfterState(tmp, scratch, i);
                        list.Add(tmp, scratch.Sequences[i]);
                        nonTerminal++;
                    }

                    int pick = (int)(rng.NextUInt() % (uint)scratch.Count);
                    BackgammonEngine.ApplyMove(state, scratch.Sequences[pick]);
                    if (!BackgammonEngine.IsGameOver(state, out result))
                    {
                        BackgammonEngine.EndTurn(state);
                    }

                    plies++;
                }
            }

            return list;
        }

        // --------------------------------------------------------------- Test 12

        [Test]
        public void Test12_AllocationPerBucket_IsZero()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildLargeList(2048, out int nonTerminal);
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(2048), "yeterli afterstate uretilemedi");

            var values = new float[2048];
            var priorities = new float[2048];
            VectorizerScalars scalars = MoneyScalars();

            for (int w = 0; w < 3; w++)
            {
                evaluator.EvaluateBatch(list, 0, 8, 1, scalars, values);
                evaluator.ScoreBatch(list, 0, 8, 1, scalars, priorities);
            }

            var report = new System.Text.StringBuilder();
            report.AppendLine("bucket;bytesPerCall;usPerCall");

            foreach (int bucket in Buckets)
            {
                if (bucket > nonTerminal)
                {
                    break;
                }

                long before = GC.GetAllocatedBytesForCurrentThread();
                long start = System.Diagnostics.Stopwatch.GetTimestamp();
                const int iterations = 20;
                for (int i = 0; i < iterations; i++)
                {
                    evaluator.EvaluateBatch(list, 0, bucket, 1, scalars, values);
                }

                long elapsed = System.Diagnostics.Stopwatch.GetTimestamp() - start;
                long after = GC.GetAllocatedBytesForCurrentThread();

                long bytesPerCall = (after - before) / iterations;
                double usPerCall = (elapsed * 1_000_000.0) / System.Diagnostics.Stopwatch.Frequency / iterations;
                report.AppendLine(bucket + ";" + bytesPerCall + ";" + usPerCall.ToString("F2"));

                Assert.That(bytesPerCall, Is.EqualTo(0L), "bucket=" + bucket + " allocation=" + bytesPerCall + " bayt");
            }

            TestContext.Out.WriteLine(report.ToString());
        }

        // --------------------------------------------------------------- Test 14

        [Test]
        public void Test14_SharedModelAcrossThreads_MatchesSingleThreaded()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();

            AfterStateList list = BuildLargeList(256, out int nonTerminal);
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(256));

            const int count = 256;
            var expected = new float[count];
            var expectedPriorities = new float[count];
            using (var single = new OnnxPolicyValueEvaluator(model))
            {
                single.EvaluateBatch(list, 0, count, 1, MoneyScalars(), expected);
                single.ScoreBatch(list, 0, count, 1, MoneyScalars(), expectedPriorities);
            }

            const int threadCount = 4;
            var results = new float[threadCount][];
            var priorities = new float[threadCount][];

            Parallel.For(0, threadCount, t =>
            {
                using var evaluator = new OnnxPolicyValueEvaluator(model);
                var values = new float[count];
                var prio = new float[count];
                evaluator.EvaluateBatch(list, 0, count, 1, MoneyScalars(), values);
                evaluator.ScoreBatch(list, 0, count, 1, MoneyScalars(), prio);
                results[t] = values;
                priorities[t] = prio;
            });

            for (int t = 0; t < threadCount; t++)
            {
                for (int i = 0; i < count; i++)
                {
                    Assert.That(results[t][i], Is.EqualTo(expected[i]).Within(1e-6f),
                        "thread " + t + " value[" + i + "]");
                    Assert.That(priorities[t][i], Is.EqualTo(expectedPriorities[i]).Within(1e-6f),
                        "thread " + t + " priority[" + i + "]");
                }
            }
        }

        [Test]
        public void Test14b_ConcurrentSearchesAreDeterministic()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();

            var scores = new float[4];
            Parallel.For(0, 4, t =>
            {
                using var evaluator = new OnnxPolicyValueEvaluator(model);
                var workspace = new SearchWorkspace();
                BackgammonState s = InferenceTestSupport.NewPosition(3, 5);
                SearchSettings settings = SearchSettings.Reference(1);
                SearchResult result = BackgammonSearch.Search(s, settings, EngineSettings.Default, workspace, evaluator);
                scores[t] = result.EvaluationScore;
            });

            for (int t = 1; t < scores.Length; t++)
            {
                Assert.That(scores[t], Is.EqualTo(scores[0]).Within(1e-6f),
                    "paralel arama sonucu farkli: " + scores[t] + " vs " + scores[0]);
            }
        }
    }
}