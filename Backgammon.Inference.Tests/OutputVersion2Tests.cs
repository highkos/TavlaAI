using System;
using System.IO;
using Backgammon.Core;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 6 §12.2 Test 54 / 57 / 58: <c>output_version = 2</c> köprüsü.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Test 54: v2 model yüklenir, <c>probs</c> okunur, <c>E</c> türetilir.
    /// Test 57: v2 yolunda da çağrı başına tahsis 0 (ısınma sonrası).
    /// Test 58: v1 model <b>aynen</b> çalışmaya devam eder (geriye dönük uyumluluk).
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class OutputVersion2Tests
    {
        private static string ModelDir
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models"); }
        }

        private static string V2ModelPath
        {
            get { return Path.Combine(ModelDir, "model_output_version_2.onnx"); }
        }

        private static VectorizerScalars MoneyScalars()
        {
            return new VectorizerScalars(1, 0, 0, 0, 0, false);
        }

        private static AfterStateList BuildList(int minCount, out int nonTerminal)
        {
            var list = new AfterStateList(512);
            nonTerminal = 0;

            var rng = new Xoshiro256StarStar(0x5EEDF6BUL);
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

        // --------------------------------------------------------------- Test 54

        [Test]
        public void Onnx_OutputVersion2_IsAccepted()
        {
            Assert.That(File.Exists(V2ModelPath), Is.True, "v2 fixture yok: " + V2ModelPath);

            using OnnxModelHandle model = OnnxModelHandle.Load(V2ModelPath, OnnxEvaluatorOptions.Default);
            Assert.That(model.OutputVersion, Is.EqualTo(2u));

            using var evaluator = new OnnxPolicyValueEvaluator(model);
            AfterStateList list = BuildList(16, out int nonTerminal);
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(16));

            var distributions = new OutcomeDistribution[nonTerminal];
            var values = new float[nonTerminal];
            VectorizerScalars scalars = MoneyScalars();

            evaluator.EvaluateDistributionBatch(list, 0, nonTerminal, 1, scalars, distributions);
            evaluator.EvaluateBatch(list, 0, nonTerminal, 1, scalars, values);

            for (int i = 0; i < nonTerminal; i++)
            {
                OutcomeDistribution d = distributions[i];
                Assert.That(d.IsValid, Is.True, "index " + i + " geçersiz dağılım");

                double total = d.WinSingle + d.WinGammonOnly + d.WinBackgammonOnly
                             + d.LoseSingle + d.LoseGammonOnly + d.LoseBackgammonOnly;
                Assert.That(total, Is.EqualTo(1.0).Within(1e-4), "index " + i + " toplam 1 olmalı");

                // EvaluateBatch, probs'tan türetilen equity'yi döndürmeli.
                Assert.That(values[i], Is.EqualTo((float)d.Equity).Within(1e-5f),
                    "index " + i + ": value = E(probs)");
                Assert.That(d.Equity, Is.InRange(-3.0, 3.0));
            }
        }

        // --------------------------------------------------------------- Test 57

        [Test]
        public void Onnx_OutputVersion2_ZeroAllocation()
        {
            Assert.That(File.Exists(V2ModelPath), Is.True, "v2 fixture yok: " + V2ModelPath);

            using OnnxModelHandle model = OnnxModelHandle.Load(V2ModelPath, OnnxEvaluatorOptions.Default);
            using var evaluator = new OnnxPolicyValueEvaluator(model);

            AfterStateList list = BuildList(64, out int nonTerminal);
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(64));

            var distributions = new OutcomeDistribution[64];
            var values = new float[64];
            var priorities = new float[64];
            VectorizerScalars scalars = MoneyScalars();

            // Isınma: kova tamponları, ORT oturumu ve JIT yolları ilk çağrılarda kurulur.
            for (int w = 0; w < 5; w++)
            {
                evaluator.EvaluateDistributionBatch(list, 0, 64, 1, scalars, distributions);
                evaluator.EvaluateBatch(list, 0, 64, 1, scalars, values);
                evaluator.ScoreBatch(list, 0, 64, 1, scalars, priorities);
            }

            const int iterations = 20;

            long before = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < iterations; i++)
            {
                evaluator.EvaluateDistributionBatch(list, 0, 64, 1, scalars, distributions);
            }

            long after = GC.GetAllocatedBytesForCurrentThread();
            long bytesPerCall = (after - before) / iterations;

            Assert.That(bytesPerCall, Is.EqualTo(0L),
                "v2 dağılım yolu çağrı başına " + bytesPerCall + " bayt tahsis etti");
        }

        // --------------------------------------------------------------- Test 58

        [Test]
        public void Onnx_OutputVersion1_StillWorks()
        {
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            Assert.That(model.OutputVersion, Is.EqualTo(1u));

            using var evaluator = new OnnxPolicyValueEvaluator(model);
            AfterStateList list = BuildList(16, out int nonTerminal);
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(16));

            var values = new float[nonTerminal];
            var priorities = new float[nonTerminal];
            VectorizerScalars scalars = MoneyScalars();

            evaluator.EvaluateBatch(list, 0, nonTerminal, 1, scalars, values);
            evaluator.ScoreBatch(list, 0, nonTerminal, 1, scalars, priorities);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(float.IsFinite(values[i]), Is.True, "index " + i);
                Assert.That(values[i], Is.InRange(-3f, 3f), "index " + i);
                Assert.That(priorities[i], Is.GreaterThanOrEqualTo(0f), "index " + i);
            }

            // v1 modelde dağılım istenirse açıkça reddedilmeli (sessizce yanlış yorum yok).
            var distributions = new OutcomeDistribution[nonTerminal];
            Assert.Throws<NotSupportedException>(() =>
                evaluator.EvaluateDistributionBatch(list, 0, nonTerminal, 1, scalars, distributions));
        }
    }
}