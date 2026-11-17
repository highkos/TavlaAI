using System;
using System.Collections.Generic;
using System.IO;
using Backgammon.Core;
using Backgammon.Inference;
using Backgammon.SelfPlay;
using NUnit.Framework;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 7 §5.4 / Test 101: damıtma hedefleri <b>deterministik</b> — aynı seed → aynı shard.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Damıtma modu (<see cref="SelfPlayConfig.DistillMode"/>) üretim sınırının üzerine çıkar
    /// (F7-15) ve öğrenen kararlarını <see cref="ShardDecisionFlags.Distilled"/> ile işaretler.
    /// Hedefler shard biçimi değişmeden taşınır: politika <c>q</c>, değer <c>searchValue</c>
    /// (F7-16).
    /// </para>
    /// <para>
    /// Determinizm, <see cref="SelfPlayRunner.ResetSeed"/> ile oyun başına tohum kurulduğu için
    /// iş parçacığı sayısından bağımsızdır (Faz 6 §7.2 / Test 60).
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class DistillDeterminismTests
    {
        private const int DistillDepth = 2;

        private static SelfPlayConfig MakeConfig(bool distill, int depth, ulong seed, int maxPlies)
        {
            return new SelfPlayConfig
            {
                ModelPath = InferenceTestSupport.V2ModelPath,
                Games = 1,
                Seed = seed,
                Threads = 1,
                OutputDir = Path.Combine(Path.GetTempPath(), "tavla_distill_test"),
                ShardPrefix = "t101",
                DepthPly = depth,
                MaxCandidatesRoot = 2,
                MaxCandidatesInner = 2,
                LogTopCandidates = 4,
                ExplorationPlies = 0,
                SelectionTemperature = 0.05f,
                PolicyTemperature = 1.0f,
                MaxPlies = maxPlies,
                Gzip = false,
                GamesPerShard = 0,
                MaxBatch = 2048,
                IntraOpThreads = 1,
                UseCuda = false,
                DupCap = 0,
                DistillMode = distill
            };
        }

        private static List<ShardGame> Play(SelfPlayConfig config, int games)
        {
            OnnxEvaluatorOptions options = config.ToEvaluatorOptions();
            SearchSettings settings = config.ToSearchSettings();

            using OnnxModelHandle model = OnnxModelHandle.Load(config.ModelPath!, options);
            using var learner = new SelfPlayAgent(model, options, settings);
            using var runner = new SelfPlayRunner(config, learner, null, config.Seed);

            var results = new List<ShardGame>(games);
            for (int i = 0; i < games; i++)
            {
                results.Add(runner.PlayGame((ulong)(i + 1), poolGame: false, learnerSide: 0));
            }

            return results;
        }

        private static byte[] ShardBytes(SelfPlayConfig config, List<ShardGame> games)
        {
            ShardHeader header = ShardHeader.Create(
                (uint)BackgammonVectorizer.FeatureVersion, 1u, (uint)config.LogTopCandidates);

            string path = Path.Combine(
                Path.GetTempPath(), "f7_t101_" + Guid.NewGuid().ToString("N") + ShardConstants.Extension);
            try
            {
                ShardWriter.WriteFile(path, header, games, gzip: false);
                return File.ReadAllBytes(path);
            }
            finally
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
        }

        [Test]
        public void Test101_SameSeedProducesIdenticalShardBytes()
        {
            SelfPlayConfig config = MakeConfig(distill: true, DistillDepth, seed: 0xD1571111UL, maxPlies: 3);

            byte[] first = ShardBytes(config, Play(config, 1));
            byte[] second = ShardBytes(config, Play(config, 1));

            Assert.That(first.Length, Is.GreaterThan(0), "shard boş olmamalı");
            Assert.That(second, Is.EqualTo(first), "aynı seed → aynı shard baytları");
        }

        [Test]
        public void Test101_DifferentSeedProducesDifferentShardBytes()
        {
            SelfPlayConfig a = MakeConfig(distill: true, DistillDepth, seed: 0xD1570001UL, maxPlies: 3);
            SelfPlayConfig b = MakeConfig(distill: true, DistillDepth, seed: 0xD1570002UL, maxPlies: 3);

            byte[] first = ShardBytes(a, Play(a, 1));
            byte[] second = ShardBytes(b, Play(b, 1));

            Assert.That(second, Is.Not.EqualTo(first), "farklı seed farklı shard üretmeli");
        }

        [Test]
        public void Test101_DistillModeMarksEveryLearnerDecision()
        {
            SelfPlayConfig config = MakeConfig(distill: true, DistillDepth, seed: 0xD1572222UL, maxPlies: 3);
            List<ShardGame> games = Play(config, 1);

            Assert.That(games, Has.Count.EqualTo(1));
            Assert.That(games[0].Decisions, Is.Not.Empty);

            int learner = 0;
            foreach (ShardDecision d in games[0].Decisions)
            {
                if (d.IsLearner)
                {
                    learner++;
                    Assert.That(d.IsDistilled, Is.True, "öğrenen kararı damıtılmış olmalı");
                }
                else
                {
                    Assert.That(d.IsDistilled, Is.False, "öğrenmeyen karar damıtılmış olmamalı");
                }
            }

            Assert.That(learner, Is.GreaterThan(0), "en az bir öğrenen kararı olmalı");
        }

        [Test]
        public void Test101_NonDistillModeLeavesFlagClear()
        {
            SelfPlayConfig config = MakeConfig(distill: false, depth: 1, seed: 0xD1573333UL, maxPlies: 3);
            List<ShardGame> games = Play(config, 1);

            foreach (ShardDecision d in games[0].Decisions)
            {
                Assert.That(d.IsDistilled, Is.False);
            }
        }

        [Test]
        public void Test101_DistillModeDoesNotChangeSearchResult()
        {
            // Damıtma modu yalnızca kökte bir ek dağılım çağrısı yapar; arama değerleri değişmez.
            SelfPlayConfig plain = MakeConfig(distill: false, depth: 1, seed: 0xD1574444UL, maxPlies: 3);
            SelfPlayConfig distill = MakeConfig(distill: true, depth: 1, seed: 0xD1574444UL, maxPlies: 3);

            // DistillMode depth 1'i reddeder; arama ayarlarını doğrudan karşılaştırıyoruz.
            SearchSettings a = plain.ToSearchSettings();
            SearchSettings b = distill.ToSearchSettings();
            b.DepthPly = a.DepthPly;

            using OnnxModelHandle model = OnnxModelHandle.Load(plain.ModelPath!, plain.ToEvaluatorOptions());
            using var agentA = new SelfPlayAgent(model, plain.ToEvaluatorOptions(), a);
            using var agentB = new SelfPlayAgent(model, plain.ToEvaluatorOptions(), b);

            BackgammonState state = InferenceTestSupport.NewPosition(3, 5);
            SearchResult ra = BackgammonSearch.Search(
                state, agentA.Settings, EngineSettings.Default, agentA.Workspace, agentA.Evaluator, agentA.Evaluator);
            SearchResult rb = BackgammonSearch.Search(
                state, agentB.Settings, EngineSettings.Default, agentB.Workspace, agentB.Evaluator, agentB.Evaluator);

            Assert.That(rb.EvaluationScore, Is.EqualTo(ra.EvaluationScore), "kök değeri değişmemeli");
            Assert.That(rb.CandidateCount, Is.EqualTo(ra.CandidateCount), "aday sayısı değişmemeli");
            Assert.That(rb.BestSequence, Is.EqualTo(ra.BestSequence), "en iyi hamle değişmemeli");
            Assert.That(ra.RootValue.HasValue, Is.False, "damıtma kapalıyken kök değeri yok");
            Assert.That(rb.RootValue.HasValue, Is.True, "damıtma açıkken kök değeri dolu");
        }

        [Test]
        public void Test101_DistillModeRequiresDeeperThanProduction()
        {
            SelfPlayConfig config = MakeConfig(distill: true, depth: 1, seed: 1UL, maxPlies: 3);
            Assert.That(
                () => config.Validate(),
                Throws.TypeOf<ArgumentException>().With.Message.Contains("DistillMode"));
        }

        [Test]
        public void Test101_NonDistillModeRejectsDepthAboveProduction()
        {
            SelfPlayConfig config = MakeConfig(distill: false, depth: DistillDepth, seed: 1UL, maxPlies: 3);
            Assert.That(
                () => config.Validate(),
                Throws.TypeOf<ArgumentException>().With.Message.Contains("F7-09"));
        }

        [Test]
        public void Test101_DistillModeAllowsDepthAboveProduction()
        {
            SelfPlayConfig config = MakeConfig(distill: true, depth: DistillDepth, seed: 1UL, maxPlies: 3);
            Assert.That(() => config.Validate(), Throws.Nothing);
            Assert.That(config.ToSearchSettings().DistillMode, Is.True);
            Assert.That(config.ToSearchSettings().DepthPly, Is.EqualTo(DistillDepth));
        }

        [Test]
        public void Test101_DistillShardRoundTripsThroughReader()
        {
            SelfPlayConfig config = MakeConfig(distill: true, DistillDepth, seed: 0xD1575555UL, maxPlies: 3);
            List<ShardGame> games = Play(config, 1);

            ShardHeader header = ShardHeader.Create(
                (uint)BackgammonVectorizer.FeatureVersion, 1u, (uint)config.LogTopCandidates);
            string path = Path.Combine(
                Path.GetTempPath(), "f7_t101_rt_" + Guid.NewGuid().ToString("N") + ShardConstants.Extension);
            try
            {
                ShardWriter.WriteFile(path, header, games, gzip: false);
                (ShardHeader readHeader, List<ShardGame> read) = ShardReader.ReadFile(path, gzip: false);

                Assert.That(readHeader.FormatVersion, Is.EqualTo(1u), "biçim sürümü 1 kalmalı");
                Assert.That(read, Has.Count.EqualTo(1));
                Assert.That(read[0].Decisions.Count, Is.EqualTo(games[0].Decisions.Count));

                for (int i = 0; i < read[0].Decisions.Count; i++)
                {
                    Assert.That(
                        read[0].Decisions[i].IsDistilled,
                        Is.EqualTo(games[0].Decisions[i].IsDistilled),
                        "karar " + i + " damıtma bayrağı korunmalı");
                }
            }
            finally
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
        }
    }
}
