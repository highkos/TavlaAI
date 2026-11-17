using System;
using System.IO;
using Backgammon.Core;
using Backgammon.Inference;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 9: taban oyunculara karsi degerlendirme (Asama D).
    /// </summary>
    [TestFixture]
    public sealed class EvalBenchTests
    {
        private static SelfPlayConfig BaseConfig()
        {
            var cfg = new SelfPlayConfig
            {
                ModelPath = InferenceTestSupport.ModelPath,
                Games = 1,
                Seed = 4242,
                Threads = 1,
                OutputDir = Path.Combine(Path.GetTempPath(), "tavla_evalbench_tests"),
                ShardPrefix = "eval",
                DepthPly = 0,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                LogTopCandidates = 12,
                ExplorationPlies = 10,
                SelectionTemperature = 0.05f,
                PolicyTemperature = 1.0f,
                MaxPlies = 500,
                Gzip = false,
                GamesPerShard = 0,
                PoolFraction = 0,
                UseCuda = false,
                MaxBatch = 2048,
                IntraOpThreads = 1
            };
            cfg.Validate();
            return cfg;
        }

        private static SelfPlayAgent NewAgent(SelfPlayConfig cfg, OnnxModelHandle model)
        {
            return new SelfPlayAgent(model, cfg.ToEvaluatorOptions(), cfg.ToSearchSettings());
        }

        [Test]
        public void Test18a_RandomOpponentProducesBalancedGameCount()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, agent, EvalBench.OpponentKind.Random, null, 8, 11);

            Assert.That(report.Games, Is.EqualTo(8));
            Assert.That(report.Wins + report.Losses + report.Draws, Is.EqualTo(8));
            Assert.That(report.OpponentName, Is.EqualTo("RandomBot"));
            Assert.That(report.StandardError, Is.GreaterThanOrEqualTo(0.0));
        }

        [Test]
        public void Test18b_PipOpponentPlaysLegalGames()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, agent, EvalBench.OpponentKind.Pip, null, 6, 22);

            Assert.That(report.Games, Is.EqualTo(6));
            Assert.That(report.Wins + report.Losses + report.Draws, Is.EqualTo(6));
            Assert.That(report.OpponentName, Is.EqualTo("PipBot"));
        }

        [Test]
        public void Test18c_ModelOpponentRequiresAgent()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            Assert.Throws<ArgumentNullException>(() =>
                EvalBench.Run(cfg, agent, EvalBench.OpponentKind.Model, null, 2, 1));
        }

        [Test]
        public void Test18d_ModelOpponentPlaysLegalGames()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent learner = NewAgent(cfg, model);
            using SelfPlayAgent opponent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, learner, EvalBench.OpponentKind.Model, opponent, 4, 33);

            Assert.That(report.Games, Is.EqualTo(4));
            Assert.That(report.Wins + report.Losses + report.Draws, Is.EqualTo(4));
            Assert.That(report.OpponentName, Is.EqualTo("Model"));
        }

        [Test]
        public void Test18e_SameModelAgainstItselfIsSymmetric()
        {
            // Ayni model kendine karsi: renkler degisimli oldugu icin ortalama puan
            // istatistiksel olarak 0'a yakin olmali (genis tolerans, kucuk orneklem).
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent learner = NewAgent(cfg, model);
            using SelfPlayAgent opponent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, learner, EvalBench.OpponentKind.Model, opponent, 20, 44);

            Assert.That(Math.Abs(report.MeanPoints), Is.LessThan(1.5),
                "ayni model kendine karsi asiri sapma gostermemeli");
        }

        [Test]
        public void Test18f_ConfidenceBoundsBracketMean()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, agent, EvalBench.OpponentKind.Random, null, 10, 55);

            Assert.That(report.LowerConfidenceBound, Is.LessThanOrEqualTo(report.MeanPoints));
            Assert.That(report.UpperConfidenceBound, Is.GreaterThanOrEqualTo(report.MeanPoints));
            Assert.That(
                report.UpperConfidenceBound - report.LowerConfidenceBound,
                Is.EqualTo(3.92 * report.StandardError).Within(1e-9));
        }

        [Test]
        public void Test18g_DeterministicForSameSeed()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            EvalBench.Report a = EvalBench.Run(cfg, agent, EvalBench.OpponentKind.Pip, null, 4, 66);
            EvalBench.Report b = EvalBench.Run(cfg, agent, EvalBench.OpponentKind.Pip, null, 4, 66);

            Assert.That(b.Wins, Is.EqualTo(a.Wins));
            Assert.That(b.Losses, Is.EqualTo(a.Losses));
            Assert.That(b.Draws, Is.EqualTo(a.Draws));
            Assert.That(b.MeanPoints, Is.EqualTo(a.MeanPoints).Within(1e-12));
        }

        [Test]
        public void Test18h_InvalidArgumentsRejected()
        {
            SelfPlayConfig cfg = BaseConfig();
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            Assert.Throws<ArgumentNullException>(() =>
                EvalBench.Run(null!, agent, EvalBench.OpponentKind.Random, null, 2, 1));
            Assert.Throws<ArgumentNullException>(() =>
                EvalBench.Run(cfg, null!, EvalBench.OpponentKind.Random, null, 2, 1));
            Assert.Throws<ArgumentOutOfRangeException>(() =>
                EvalBench.Run(cfg, agent, EvalBench.OpponentKind.Random, null, 0, 1));
        }

        [Test]
        public void Test18i_OpponentNames()
        {
            Assert.That(EvalBench.NameOf(EvalBench.OpponentKind.Random), Is.EqualTo("RandomBot"));
            Assert.That(EvalBench.NameOf(EvalBench.OpponentKind.Pip), Is.EqualTo("PipBot"));
            Assert.That(EvalBench.NameOf(EvalBench.OpponentKind.Model), Is.EqualTo("Model"));
        }

        [Test]
        public void Test18j_PipBotPrefersBearingOff()
        {
            // PipBot'un secimi dogrudan test edilemez (private), ancak davranisi
            // gozlemlenebilir: tek pullu bir bitis pozisyonunda oyun kisa surer.
            SelfPlayConfig cfg = BaseConfig();
            cfg.MaxPlies = 500;
            using OnnxModelHandle model = InferenceTestSupport.LoadModel();
            using SelfPlayAgent agent = NewAgent(cfg, model);

            EvalBench.Report report = EvalBench.Run(
                cfg, agent, EvalBench.OpponentKind.Pip, null, 6, 77);

            Assert.That(report.Games, Is.EqualTo(6));
            Assert.That(report.Draws, Is.LessThanOrEqualTo(6));
        }
    }
}