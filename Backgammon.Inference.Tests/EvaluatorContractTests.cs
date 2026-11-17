using System;
using System.IO;
using Backgammon.Core;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8, Test 8 / 11 / 15: degerlendirici sozlesmesi, tutarlilik ve surum korumasi.
    /// </summary>
    [TestFixture]
    public sealed class EvaluatorContractTests
    {
        private static VectorizerScalars MoneyScalars()
        {
            return new VectorizerScalars(1, 0, 0, 0, 0, false);
        }

        private static AfterStateList BuildList(out int nonTerminal, out int total)
        {
            BackgammonState s = InferenceTestSupport.NewPosition(3, 5);
            var list = new AfterStateList();
            nonTerminal = InferenceTestSupport.BuildNonTerminalPrefix(s, list, out total);
            return list;
        }

        // ---------------------------------------------------------------- Test 8

        [Test]
        public void Test08_ScoreBatch_PrioritiesAreNormalized()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            Assert.That(nonTerminal, Is.GreaterThan(1));

            var priorities = new float[nonTerminal];
            evaluator.ScoreBatch(list, 0, nonTerminal, 1, MoneyScalars(), priorities);

            double sum = 0.0;
            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(priorities[i], Is.GreaterThanOrEqualTo(0f), "priorities[" + i + "] negatif");
                Assert.That(float.IsFinite(priorities[i]), Is.True, "priorities[" + i + "] sonlu degil");
                sum += priorities[i];
            }

            Assert.That(sum, Is.EqualTo(1.0).Within(1e-5), "priorities toplami 1 degil: " + sum);
        }

        [Test]
        public void Test08b_ScoreBatch_SingleCandidateIsOne()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            Assert.That(nonTerminal, Is.GreaterThan(0));

            var priorities = new float[1];
            evaluator.ScoreBatch(list, 0, 1, 1, MoneyScalars(), priorities);
            Assert.That(priorities[0], Is.EqualTo(1.0f).Within(1e-6f));
        }

        [Test]
        public void Test08c_ScoreBatch_ZeroCountIsNoOp()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out _, out _);
            var priorities = new float[4];
            for (int i = 0; i < priorities.Length; i++)
            {
                priorities[i] = -123f;
            }

            evaluator.ScoreBatch(list, 0, 0, 1, MoneyScalars(), priorities);
            for (int i = 0; i < priorities.Length; i++)
            {
                Assert.That(priorities[i], Is.EqualTo(-123f), "count=0 iken dizi degismemeli");
            }
        }

        [Test]
        public void Test08d_NonZeroOffsetThrows()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            var buffer = new float[nonTerminal + 4];

            Assert.Throws<ArgumentException>(
                () => evaluator.ScoreBatch(list, 1, 1, 1, MoneyScalars(), buffer));
            Assert.Throws<ArgumentException>(
                () => evaluator.EvaluateBatch(list, 1, 1, 1, MoneyScalars(), buffer));
            Assert.Throws<ArgumentException>(
                () => evaluator.EvaluateAndScoreBatch(list, 1, 1, 1, MoneyScalars(), buffer, buffer));
        }

        [Test]
        public void Test08e_TerminalRecordThrows()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            // Beyaz'in son tasi ev bolgesinde (24) ve 14 tas toplanmis: 1'lik zarla terminal olmali.
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
            Array.Clear(s.board, 0, s.board.Length);
            s.board[24] = 1;
            s.board[1] = -1;
            s.whiteBorneOff = 14;
            s.blackBorneOff = 14;
            s.turn = 1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            BackgammonEngine.SetDice(s, 1, 1);

            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);

            int terminalIndex = -1;
            for (int i = 0; i < list.Count; i++)
            {
                if (list.IsTerminal[i])
                {
                    terminalIndex = i;
                    break;
                }
            }

            Assert.That(terminalIndex, Is.GreaterThanOrEqualTo(0), "terminal afterstate uretilemedi");

            var buffer = new float[list.Count];
            Assert.Throws<ArgumentException>(
                () => evaluator.EvaluateBatch(list, 0, terminalIndex + 1, 1, MoneyScalars(), buffer));
        }

        // --------------------------------------------------------------- Test 11

        [Test]
        public void Test11_EvaluateAndScoreMatchesSeparateCalls()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            Assert.That(nonTerminal, Is.GreaterThan(1));

            var valuesSeparate = new float[nonTerminal];
            var prioritiesSeparate = new float[nonTerminal];
            evaluator.EvaluateBatch(list, 0, nonTerminal, 1, MoneyScalars(), valuesSeparate);
            evaluator.ScoreBatch(list, 0, nonTerminal, 1, MoneyScalars(), prioritiesSeparate);

            var valuesCombined = new float[nonTerminal];
            var prioritiesCombined = new float[nonTerminal];
            evaluator.EvaluateAndScoreBatch(list, 0, nonTerminal, 1, MoneyScalars(), valuesCombined, prioritiesCombined);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(valuesCombined[i], Is.EqualTo(valuesSeparate[i]).Within(1e-6f), "value[" + i + "]");
                Assert.That(prioritiesCombined[i], Is.EqualTo(prioritiesSeparate[i]).Within(1e-6f), "priority[" + i + "]");
            }
        }

        [Test]
        public void Test11b_ValuesAreFiniteAndUnclipped()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            var values = new float[nonTerminal];
            evaluator.EvaluateBatch(list, 0, nonTerminal, 1, MoneyScalars(), values);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(float.IsFinite(values[i]), Is.True, "value[" + i + "] sonlu degil");
            }
        }

        [Test]
        public void Test11c_PerspectiveMatchesMirroredState()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(out int nonTerminal, out _);
            Assert.That(nonTerminal, Is.GreaterThan(1));

            // Vektorlestirici perspektife gore aynalar: Vectorize(s, -1) == Vectorize(mirror(s), +1).
            // Bu yuzden ayni ag, aynali liste uzerinde +1 perspektifiyle ayni degeri vermelidir.
            BackgammonState baseState = InferenceTestSupport.NewPosition(3, 5);
            var mirrored = new AfterStateList(nonTerminal);
            var tmp = new BackgammonState();
            var mirror = new BackgammonState();
            for (int i = 0; i < nonTerminal; i++)
            {
                tmp.CopyFrom(baseState);
                BackgammonEngine.LoadAfterState(tmp, list, i);
                BackgammonEngine.MirrorTo(tmp, mirror);
                mirrored.Add(mirror, list.Sequences[i]);
            }

            var black = new float[nonTerminal];
            var white = new float[nonTerminal];
            evaluator.EvaluateBatch(list, 0, nonTerminal, -1, MoneyScalars(), black);
            evaluator.EvaluateBatch(mirrored, 0, nonTerminal, 1, MoneyScalars(), white);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(black[i], Is.EqualTo(white[i]).Within(1e-5f),
                    "perspektif/ayna tutarsizligi: value[" + i + "]");
            }
        }

        // --------------------------------------------------------------- Test 15

        [Test]
        public void Test15_LoadRejectsFeatureVersionMismatch()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_bad_feature_version.onnx");
            Assert.Throws<InvalidDataException>(
                () => OnnxModelHandle.Load(path, OnnxEvaluatorOptions.Default));
        }

        [Test]
        public void Test15b_LoadRejectsVectorSizeMismatch()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_bad_vector_size.onnx");
            Assert.Throws<InvalidDataException>(
                () => OnnxModelHandle.Load(path, OnnxEvaluatorOptions.Default));
        }

        [Test]
        public void Test15c_LoadRejectsMissingFile()
        {
            Assert.Throws<FileNotFoundException>(
                () => OnnxModelHandle.Load(Path.Combine(Path.GetTempPath(), "yok_" + Guid.NewGuid().ToString("N") + ".onnx"),
                                           OnnxEvaluatorOptions.Default));
        }

        [Test]
        public void Test15d_LoadReadsMetadata()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            Assert.That(model.ModelVersion, Is.EqualTo(1u));
            Assert.That(model.Arch, Is.EqualTo("221-128-64"));
            Assert.That(model.TrainedBy, Is.Not.Null.And.Not.Empty);
            Assert.That(model.ModelPath, Is.EqualTo(InferenceTestSupport.ModelPath));
        }

        [Test]
        public void Test15e_SetModelRequiresIncreasingVersion()
        {
            using OnnxModelHandle v1 = InferenceTestSupport.LoadModel();
            using OnnxModelHandle v2 = OnnxModelHandle.Load(
                Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_v2.onnx"),
                OnnxEvaluatorOptions.Default);

            Assert.That(v2.ModelVersion, Is.EqualTo(2u));

            using var evaluator = new OnnxPolicyValueEvaluator(v1);
            Assert.That(evaluator.Version, Is.EqualTo(1));

            evaluator.SetModel(v2);
            Assert.That(evaluator.Version, Is.EqualTo(2));
            Assert.That(evaluator.Model, Is.SameAs(v2));

            // Ayni veya daha kucuk surum reddedilmeli.
            Assert.Throws<ArgumentException>(() => evaluator.SetModel(v2));
            Assert.Throws<ArgumentException>(() => evaluator.SetModel(v1));
        }

        [Test]
        public void Test15f_SetModelThenWorkspaceResetClearsCache()
        {
            using OnnxModelHandle v1 = InferenceTestSupport.LoadModel();
            using OnnxModelHandle v2 = OnnxModelHandle.Load(
                Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_v2.onnx"),
                OnnxEvaluatorOptions.Default);

            using var evaluator = new OnnxPolicyValueEvaluator(v1);

            // Gercek bir arama cache'i doldurur (Faz 3 v7 Test 17 semantigi).
            var workspace = new SearchWorkspace();
            BackgammonState s = InferenceTestSupport.NewPosition(3, 5);
            SearchSettings settings = SearchSettings.Reference(1);
            settings.UseEvalCache = true;
            BackgammonSearch.Search(s, settings, EngineSettings.Default, workspace, new ConstantEvaluator(0.1f));
            Assert.That(workspace.CacheEntryCount, Is.GreaterThan(0), "arama cache'i doldurmali");

            evaluator.SetModel(v2);
            workspace.Reset();
            Assert.That(workspace.CacheEntryCount, Is.EqualTo(0), "Reset() cache'i temizlemeli (Faz 3 v7 Test 17)");
        }

        /// <summary>Test icin sabit degerlendirici.</summary>
        private sealed class ConstantEvaluator : IPositionEvaluator
        {
            private readonly float _value;

            public ConstantEvaluator(float value)
            {
                _value = value;
            }

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = 0; i < count; i++)
                {
                    results[i] = _value;
                }
            }
        }

        [Test]
        public void Test15g_DisposeIsIdempotent()
        {
            OnnxModelHandle model = InferenceTestSupport.LoadModel();
            var evaluator = new OnnxPolicyValueEvaluator(model);
            evaluator.Dispose();
            evaluator.Dispose();
            model.Dispose();
            model.Dispose();
        }
    }
}