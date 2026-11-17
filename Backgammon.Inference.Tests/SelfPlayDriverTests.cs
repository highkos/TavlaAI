using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Backgammon.Core;
using Backgammon.Inference;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8 Test 17: self-play surucusu.
    /// <c>max_plies</c> ile abort, havuz rakipli oyunda <c>IsLearner</c> bayraklari,
    /// <c>resultType</c>/<c>resultPoints</c> tutarliligi ve <c>cubeValue == 1</c> degismezi.
    /// </summary>
    [TestFixture]
    public sealed class SelfPlayDriverTests
    {
        private static SelfPlayConfig MakeConfig(int games, int maxPlies, int logTop, float poolFraction)
        {
            return new SelfPlayConfig
            {
                ModelPath = InferenceTestSupport.ModelPath,
                Games = games,
                Seed = 0x5EEDF00DUL,
                Threads = 1,
                OutputDir = Path.Combine(Path.GetTempPath(), "tavla_selfplay_test"),
                ShardPrefix = "t17",
                DepthPly = 0,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                LogTopCandidates = logTop,
                ExplorationPlies = 4,
                SelectionTemperature = 0.05f,
                PolicyTemperature = 1.0f,
                MaxPlies = maxPlies,
                Gzip = false,
                GamesPerShard = 0,
                PoolFraction = poolFraction,
                MaxBatch = 2048,
                IntraOpThreads = 1,
                UseCuda = false,
            };
        }

        private static List<ShardGame> Play(SelfPlayConfig config, int games, bool poolGame, sbyte learnerSide)
        {
            OnnxEvaluatorOptions options = config.ToEvaluatorOptions();
            SearchSettings settings = config.ToSearchSettings();

            using OnnxModelHandle model = OnnxModelHandle.Load(config.ModelPath!, options);
            using var learner = new SelfPlayAgent(model, options, settings);
            using SelfPlayAgent? pool = poolGame ? new SelfPlayAgent(model, options, settings) : null;
            using var runner = new SelfPlayRunner(config, learner, pool, config.Seed);

            var results = new List<ShardGame>(games);
            for (int i = 0; i < games; i++)
            {
                results.Add(runner.PlayGame((ulong)(i + 1), poolGame, learnerSide));
            }

            return results;
        }

        [Test]
        public void Test17a_MaxPliesAbortsGame()
        {
            SelfPlayConfig config = MakeConfig(1, maxPlies: 2, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 1, poolGame: false, learnerSide: 0);

            Assert.That(games, Has.Count.EqualTo(1));
            Assert.That(games[0].IsAborted, Is.True, "MaxPlies=2 ile oyun abort edilmeliydi.");
            Assert.That(games[0].Decisions.Count, Is.LessThanOrEqualTo(2));
        }

        [Test]
        public void Test17b_CompletedGameHasTerminalLastDecision()
        {
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 2, poolGame: false, learnerSide: 0);

            foreach (ShardGame g in games)
            {
                Assert.That(g.IsAborted, Is.False, "500 ply sinirinda abort beklenmiyordu.");
                Assert.That(g.Decisions, Is.Not.Empty);

                ShardDecision last = g.Decisions[g.Decisions.Count - 1];
                Assert.That(last.ChosenIsTerminal, Is.True, "Son karar terminal olmali.");
                Assert.That(last.ChosenVector, Is.Null, "Terminal kararin vektoru olmamali.");
                Assert.That(last.LoggedCount, Is.EqualTo(0), "Terminal kararda aday loglanmaz.");
            }
        }

        [Test]
        public void Test17c_ResultTypeAndPointsAreConsistent()
        {
            SelfPlayConfig config = MakeConfig(4, maxPlies: 500, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 4, poolGame: false, learnerSide: 0);

            foreach (ShardGame g in games)
            {
                if (g.IsAborted)
                {
                    continue;
                }

                Assert.That(g.Winner, Is.AnyOf(1, -1), "Kazanan +1 veya -1 olmali.");
                Assert.That(g.ResultType, Is.InRange(1, 3), "resultType 1..3 olmali.");

                // cubeValue = 1 ve Jacoby kapali => resultPoints == resultType (Faz 1 GameResult.Points).
                Assert.That(g.ResultPoints, Is.EqualTo(g.ResultType),
                    "cubeValue=1 iken resultPoints resultType'a esit olmali.");
            }
        }

        [Test]
        public void Test17d_CubeValueIsAlwaysOne()
        {
            SelfPlayConfig config = MakeConfig(3, maxPlies: 500, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 3, poolGame: false, learnerSide: 0);

            foreach (ShardGame g in games)
            {
                Assert.That(g.CubeValue, Is.EqualTo(1), "Faz 4 kup kullanmaz; cubeValue her zaman 1.");
            }
        }

        [Test]
        public void Test17e_PoolGameLearnerFlags()
        {
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: 4, poolFraction: 1f);
            List<ShardGame> games = Play(config, 2, poolGame: true, learnerSide: 1);

            foreach (ShardGame g in games)
            {
                Assert.That(g.LearnerSide, Is.EqualTo(1), "Havuz oyununda learnerSide verilen deger olmali.");

                bool sawLearner = false;
                bool sawOpponent = false;

                foreach (ShardDecision d in g.Decisions)
                {
                    bool expectedLearner = d.Mover == g.LearnerSide;
                    Assert.That(d.IsLearner, Is.EqualTo(expectedLearner),
                        "IsLearner, mover == learnerSide ile tutarli olmali.");

                    if (d.IsLearner)
                    {
                        sawLearner = true;
                    }
                    else
                    {
                        sawOpponent = true;
                        Assert.That(d.LoggedCount, Is.EqualTo(0),
                            "Rakip kararlarinda aday loglanmaz.");
                        Assert.That(d.Q, Is.Null);
                        Assert.That(d.PolicyTargetCs, Is.Null);
                    }
                }

                Assert.That(sawLearner, Is.True, "Havuz oyununda ogrenen karari bulunmali.");
                Assert.That(sawOpponent, Is.True, "Havuz oyununda rakip karari bulunmali.");
            }
        }

        [Test]
        public void Test17f_SelfPlayDecisionsAreAllLearner()
        {
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 2, poolGame: false, learnerSide: 0);

            foreach (ShardGame g in games)
            {
                Assert.That(g.LearnerSide, Is.EqualTo(0), "Oz-oyunda learnerSide 0 (iki taraf da ogrenir).");
                foreach (ShardDecision d in g.Decisions)
                {
                    Assert.That(d.IsLearner, Is.True, "Oz-oyunda her karar ogrenendir.");
                }
            }
        }

        [Test]
        public void Test17g_LoggedCandidatesRespectLogTop()
        {
            const int logTop = 3;
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: logTop, poolFraction: 0f);
            List<ShardGame> games = Play(config, 2, poolGame: false, learnerSide: 0);

            foreach (ShardGame g in games)
            {
                foreach (ShardDecision d in g.Decisions)
                {
                    Assert.That(d.LoggedCount, Is.LessThanOrEqualTo(logTop));
                    Assert.That(d.LoggedCount, Is.LessThanOrEqualTo(d.CandidateTotal));

                    if (d.LoggedCount > 0)
                    {
                        Assert.That(d.Q, Is.Not.Null);
                        Assert.That(d.PolicyTargetCs, Is.Not.Null);
                        Assert.That(d.CandidateVectors, Is.Not.Null);
                        Assert.That(d.CandidateVectors!.Length, Is.EqualTo(d.LoggedCount * ShardConstants.VectorSize));

                        // Q azalan sirali (Bolum 5.2)
                        for (int k = 1; k < d.LoggedCount; k++)
                        {
                            Assert.That(d.Q![k], Is.LessThanOrEqualTo(d.Q[k - 1] + 1e-6f));
                        }

                        // policyTargetCs, TUM Kind in {0,1} adaylari uzerinden softmax'in
                        // loglanan alt kumesidir; bu yuzden toplami <= 1'dir (logTopCandidates
                        // ile kirpilir). Python tarafi (Bolum 6.3) E uzerinde yeniden normalize eder.
                        float sum = 0f;
                        for (int k = 0; k < d.LoggedCount; k++)
                        {
                            float p = d.PolicyTargetCs![k];
                            Assert.That(p, Is.GreaterThanOrEqualTo(0f));
                            sum += p;
                        }

                        Assert.That(sum, Is.GreaterThan(0f));
                        Assert.That(sum, Is.LessThanOrEqualTo(1f + 1e-4f));

                        // Q azalan oldugu icin softmax hedefleri de azalan olmali.
                        for (int k = 1; k < d.LoggedCount; k++)
                        {
                            Assert.That(d.PolicyTargetCs![k], Is.LessThanOrEqualTo(d.PolicyTargetCs[k - 1] + 1e-6f));
                        }
                    }
                }
            }
        }

        [Test]
        public void Test17h_SingleThreadIsDeterministic()
        {
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: 4, poolFraction: 0f);

            List<ShardGame> a = Play(config, 2, poolGame: false, learnerSide: 0);
            List<ShardGame> b = Play(config, 2, poolGame: false, learnerSide: 0);

            Assert.That(a.Count, Is.EqualTo(b.Count));
            for (int i = 0; i < a.Count; i++)
            {
                Assert.That(a[i].Decisions.Count, Is.EqualTo(b[i].Decisions.Count));
                Assert.That(a[i].Winner, Is.EqualTo(b[i].Winner));
                Assert.That(a[i].ResultPoints, Is.EqualTo(b[i].ResultPoints));

                for (int k = 0; k < a[i].Decisions.Count; k++)
                {
                    ShardDecision da = a[i].Decisions[k];
                    ShardDecision db = b[i].Decisions[k];
                    Assert.That(da.Mover, Is.EqualTo(db.Mover));
                    Assert.That(da.Flags, Is.EqualTo(db.Flags));
                    Assert.That(da.SearchValue, Is.EqualTo(db.SearchValue));
                    Assert.That(da.LoggedCount, Is.EqualTo(db.LoggedCount));

                    if (da.ChosenVector != null)
                    {
                        Assert.That(da.ChosenVector, Is.EqualTo(db.ChosenVector));
                    }
                }
            }
        }

        [Test]
        public void Test17i_ShardRoundTripPreservesGames()
        {
            SelfPlayConfig config = MakeConfig(2, maxPlies: 500, logTop: 4, poolFraction: 0f);
            List<ShardGame> games = Play(config, 2, poolGame: false, learnerSide: 0);

            string dir = Path.Combine(Path.GetTempPath(), "tavla_selfplay_rt_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, "t17.bgsp");

            try
            {
                ShardHeader header = ShardHeader.Create(
                    (uint)BackgammonVectorizer.FeatureVersion, 1u, 4u);
                ShardWriter.WriteFile(path, header, games, gzip: false);

                (ShardHeader readHeader, List<ShardGame> readGames) = ShardReader.ReadFile(path);

                Assert.That(readHeader.FormatVersion, Is.EqualTo(ShardConstants.FormatVersion));
                Assert.That(readHeader.VectorSize, Is.EqualTo(ShardConstants.VectorSize));
                Assert.That(readGames, Has.Count.EqualTo(games.Count));

                for (int i = 0; i < games.Count; i++)
                {
                    Assert.That(readGames[i].GameId, Is.EqualTo(games[i].GameId));
                    Assert.That(readGames[i].Winner, Is.EqualTo(games[i].Winner));
                    Assert.That(readGames[i].ResultType, Is.EqualTo(games[i].ResultType));
                    Assert.That(readGames[i].ResultPoints, Is.EqualTo(games[i].ResultPoints));
                    Assert.That(readGames[i].Decisions.Count, Is.EqualTo(games[i].Decisions.Count));

                    for (int k = 0; k < games[i].Decisions.Count; k++)
                    {
                        ShardDecision src = games[i].Decisions[k];
                        ShardDecision dst = readGames[i].Decisions[k];
                        Assert.That(dst.Mover, Is.EqualTo(src.Mover));
                        Assert.That(dst.Flags, Is.EqualTo(src.Flags));
                        Assert.That(dst.CandidateTotal, Is.EqualTo(src.CandidateTotal));
                        Assert.That(dst.SearchValue, Is.EqualTo(src.SearchValue));
                        Assert.That(dst.LoggedCount, Is.EqualTo(src.LoggedCount));

                        if (src.ChosenVector != null)
                        {
                            Assert.That(dst.ChosenVector, Is.EqualTo(src.ChosenVector));
                        }

                        if (src.Q != null)
                        {
                            Assert.That(dst.Q, Is.EqualTo(src.Q));
                            Assert.That(dst.PolicyTargetCs, Is.EqualTo(src.PolicyTargetCs));
                            Assert.That(dst.CandidateVectors, Is.EqualTo(src.CandidateVectors));
                        }
                    }
                }
            }
            finally
            {
                try
                {
                    Directory.Delete(dir, recursive: true);
                }
                catch (IOException)
                {
                }
            }
        }
    }
}