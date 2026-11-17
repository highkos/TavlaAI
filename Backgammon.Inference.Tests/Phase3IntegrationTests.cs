using System;
using Backgammon.Core;
using Backgammon.Tests;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8, Test 16: Faz 3 v7 aramasinin <b>gercek ONNX modeliyle</b> entegrasyonu.
    /// </summary>
    /// <remarks>
    /// Kapsanan Faz 3 v7 testleri: 1 (referans esitligi), 8 (determinizm), 12 (tutarlilik),
    /// 16 (ICombinedBatchEvaluator), 17 (model yeniden yukleme / cache temizligi).
    /// Referans aramasi <c>Backgammon.Tests</c> kaynagindan paylasilir (bkz. csproj).
    /// </remarks>
    [TestFixture]
    public sealed class Phase3IntegrationTests
    {
        /// <summary>
        /// Referans arama farkli batch bilesimleriyle calisir; olculen sapma raporlanir.
        /// Baslangic toleransi Faz 4 v3 Bolum 8 Test 16: 1e-4.
        /// </summary>
        private const float ReferenceTolerance = 1e-4f;

        private static VectorizerScalars MoneyScalars()
        {
            return new VectorizerScalars(1, 0, 0, 0, 0, false);
        }

        private static BackgammonState[] Positions()
        {
            return new[]
            {
                SearchTestSupport.Starting(3, 1),
                SearchTestSupport.MidGame(3, 5),
                SearchTestSupport.WhiteOnBar(2, 5),
                SearchTestSupport.BlackOnBar(2, 5),
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.SingleCheckerEndgame(3, 1),
            };
        }

        // ------------------------------------------------- Faz 3 v7 Test 1 / 16

        [Test]
        public void Test16a_ReferenceEquality_WithRealOnnxModel()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            var reference = new ReferenceSearch();
            var workspace = new SearchWorkspace();
            float maxDelta = 0f;

            foreach (BackgammonState position in Positions())
            {
                foreach (int depth in new[] { 0, 1 })
                {
                    SearchSettings ss = SearchSettings.Reference(depth);
                    float expected = reference.RootValue(position, ss, EngineSettings.Default, evaluator, evaluator);

                    SearchResult actual = BackgammonSearch.Search(
                        position, ss, EngineSettings.Default, workspace, evaluator);

                    float delta = Math.Abs(actual.EvaluationScore - expected);
                    if (delta > maxDelta)
                    {
                        maxDelta = delta;
                    }

                    Assert.That(delta, Is.LessThanOrEqualTo(ReferenceTolerance),
                        "depth=" + depth + " beklenen=" + expected + " gercek=" + actual.EvaluationScore);
                }
            }

            TestContext.Out.WriteLine("Test16a max |delta| = " + maxDelta.ToString("E3"));
        }

        // ------------------------------------------------- Faz 3 v7 Test 8

        [Test]
        public void Test16b_Determinism_RepeatedSearchIsIdentical()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            BackgammonState position = SearchTestSupport.MidGame(3, 5);
            SearchSettings ss = SearchSettings.Reference(1);

            var workspaceA = new SearchWorkspace();
            SearchResult a = BackgammonSearch.Search(position, ss, EngineSettings.Default, workspaceA, evaluator);

            var workspaceB = new SearchWorkspace();
            SearchResult b = BackgammonSearch.Search(position, ss, EngineSettings.Default, workspaceB, evaluator);

            Assert.That(b.EvaluationScore, Is.EqualTo(a.EvaluationScore).Within(1e-6f));
            Assert.That(b.BestSequence.Count, Is.EqualTo(a.BestSequence.Count));
            for (int i = 0; i < a.BestSequence.Count; i++)
            {
                Assert.That(b.BestSequence[i].From, Is.EqualTo(a.BestSequence[i].From));
                Assert.That(b.BestSequence[i].To, Is.EqualTo(a.BestSequence[i].To));
                Assert.That(b.BestSequence[i].Die, Is.EqualTo(a.BestSequence[i].Die));
            }
        }

        // ------------------------------------------------- Faz 3 v7 Test 12

        [Test]
        public void Test16c_Consistency_CombinedEqualsSeparate()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            BackgammonState position = SearchTestSupport.MidGame(3, 5);
            var list = new AfterStateList();
            int nonTerminal = InferenceTestSupport.BuildNonTerminalPrefix(position, list, out _);
            Assert.That(nonTerminal, Is.GreaterThan(1));

            var v1 = new float[nonTerminal];
            var p1 = new float[nonTerminal];
            evaluator.EvaluateBatch(list, 0, nonTerminal, 1, MoneyScalars(), v1);
            evaluator.ScoreBatch(list, 0, nonTerminal, 1, MoneyScalars(), p1);

            var v2 = new float[nonTerminal];
            var p2 = new float[nonTerminal];
            evaluator.EvaluateAndScoreBatch(list, 0, nonTerminal, 1, MoneyScalars(), v2, p2);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(v2[i], Is.EqualTo(v1[i]).Within(1e-6f), "value[" + i + "]");
                Assert.That(p2[i], Is.EqualTo(p1[i]).Within(1e-6f), "priority[" + i + "]");
            }
        }

        // ------------------------------------------------- Faz 3 v7 Test 16

        [Test]
        public void Test16d_CombinedEvaluatorUsedAtRoot()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            BackgammonState position = SearchTestSupport.MidGame(3, 5);

            var ss = new SearchSettings
            {
                DepthPly = 1,
                MaxCandidatesRoot = 4,
                MaxCandidatesInner = 0,
                UsePolicyOrdering = true,
                ExactRootScores = true,
                PolicyTemperature = 0.05f,
            };

            var workspace = new SearchWorkspace();
            SearchResult result = BackgammonSearch.Search(position, ss, EngineSettings.Default, workspace, evaluator);

            Assert.That(result.RootCandidates.Length, Is.GreaterThan(0), "kok adaylari bos");
            Assert.That(result.RootPolicyTarget.Length, Is.EqualTo(result.RootCandidates.Length),
                "politika hedefi uzunlugu aday sayisiyla eslesmeli");

            double sum = 0.0;
            for (int i = 0; i < result.RootCandidates.Length; i++)
            {
                Assert.That(float.IsFinite(result.RootCandidates[i].Score), Is.True);
                if (result.RootCandidates[i].Kind != 2)
                {
                    sum += result.RootPolicyTarget[i];
                }
            }

            Assert.That(sum, Is.EqualTo(1.0).Within(1e-4), "kok politika hedefi toplami 1 degil: " + sum);
        }

        // ------------------------------------------------- Faz 3 v7 Test 17

        [Test]
        public void Test16e_ModelReloadIncreasesVersionAndClearsCache()
        {
            using OnnxModelHandle v1 = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(v1);

            BackgammonState position = SearchTestSupport.MidGame(3, 5);
            // Reference() cache'i kapatir; cache davranisini olcmek icin Default kullanilir.
            SearchSettings ss = SearchSettings.Default;
            var workspace = new SearchWorkspace();

            BackgammonSearch.Search(position, ss, EngineSettings.Default, workspace, evaluator);
            Assert.That(workspace.CacheEntryCount, Is.GreaterThan(0), "cache dolmadi");

            int versionBefore = evaluator.Version;

            string v2Path = System.IO.Path.Combine(
                TestContext.CurrentContext.TestDirectory, "Models", "model_v2.onnx");
            using OnnxModelHandle v2 = OnnxModelHandle.Load(v2Path, OnnxEvaluatorOptions.Default);
            evaluator.SetModel(v2);

            Assert.That(evaluator.Version, Is.GreaterThan(versionBefore), "Version artmadi");

            workspace.Reset();
            Assert.That(workspace.CacheEntryCount, Is.EqualTo(0), "Reset cache'i temizlemedi");

            // Yeni modelle arama hala calisir ve sonludur.
            SearchResult result = BackgammonSearch.Search(position, ss, EngineSettings.Default, workspace, evaluator);
            Assert.That(float.IsFinite(result.EvaluationScore), Is.True);
        }

        [Test]
        public void Test16f_SetModelRejectsNonIncreasingVersion()
        {
            using OnnxModelHandle v1 = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(v1);

            Assert.Throws<ArgumentException>(() => evaluator.SetModel(v1));
        }
    }
}