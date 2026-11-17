using System;
using System.Collections.Generic;
using System.IO;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8, Test 4 (capraz dil yari): C# yazici -> Python okuyucu.
    /// </summary>
    /// <remarks>
    /// Bu test <c>ml/artifacts/csharp_shard.bgsp</c> dosyasini uretir; Python tarafi
    /// (<c>ml/tests/test_shards.py::test_reads_csharp_written_shard</c> ve
    /// <c>test_tau_crosscheck.py</c>) bu dosyayi okuyup bit duzeyinde dogrular.
    /// </remarks>
    [TestFixture]
    public sealed class ShardCrossLanguageTests
    {
        public const uint FixtureModelVersion = 77;
        public const uint FixtureLogTopCandidates = 12;
        public const float FixtureTau = 0.05f;

        private static string FixturePath
        {
            get { return Path.Combine(InferenceTestSupport.MlArtifactsDir, "csharp_shard.bgsp"); }
        }

        [Test]
        public void Shard_CrossLanguageFixture()
        {
            ShardHeader header = ShardHeader.Create(
                (uint)Backgammon.Core.BackgammonVectorizer.FeatureVersion,
                FixtureModelVersion,
                FixtureLogTopCandidates);

            List<ShardGame> games = BuildFixtureGames();
            ShardWriter.WriteFile(FixturePath, header, games, gzip: false);

            Assert.That(File.Exists(FixturePath), Is.True);

            // Kendi okuyucumuzla geri okuyup tutarliligi dogrula.
            var (readHeader, roundTrip) = ShardReader.ReadFile(FixturePath);
            Assert.That(readHeader.ModelVersion, Is.EqualTo(FixtureModelVersion));
            Assert.That(readHeader.LogTopCandidates, Is.EqualTo(FixtureLogTopCandidates));
            Assert.That(roundTrip.Count, Is.EqualTo(games.Count));
            Assert.That(roundTrip[0].Decisions.Count, Is.EqualTo(2));
            Assert.That(roundTrip[0].Decisions[0].LoggedCount, Is.EqualTo(2));
            Assert.That(roundTrip[0].Decisions[1].ChosenIsTerminal, Is.True);
            Assert.That(roundTrip[1].IsAborted, Is.True);
        }

        [Test]
        public void Shard_GzipRoundTrip()
        {
            string path = Path.Combine(Path.GetTempPath(), "tavla_shard_" + Guid.NewGuid().ToString("N") + ".bgsp.gz");
            try
            {
                ShardHeader header = ShardHeader.Create(1, 5, 0);
                ShardWriter.WriteFile(path, header, BuildFixtureGames(), gzip: true);
                var (_, games) = ShardReader.ReadFile(path);
                Assert.That(games.Count, Is.EqualTo(3));
                Assert.That(games[0].Decisions[0].Q![0], Is.EqualTo(0.5f));
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
        public void Shard_RejectsInconsistentDecision()
        {
            var game = new ShardGame { GameId = 1, CubeValue = 1 };
            game.Decisions.Add(new ShardDecision
            {
                Mover = 1,
                Flags = ShardDecisionFlags.IsLearner,
                CandidateTotal = 1,
                ChosenVector = null, // terminal degil ama vektor yok
            });

            string path = Path.Combine(Path.GetTempPath(), "tavla_bad_" + Guid.NewGuid().ToString("N") + ".bgsp");
            try
            {
                Assert.Throws<ArgumentException>(
                    () => ShardWriter.WriteFile(path, ShardHeader.Create(1, 1, 0), new[] { game }, gzip: false));
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
        public void Shard_RejectsBadMagic()
        {
            string path = Path.Combine(Path.GetTempPath(), "tavla_magic_" + Guid.NewGuid().ToString("N") + ".bgsp");
            try
            {
                var bytes = new byte[32];
                bytes[0] = (byte)'X';
                File.WriteAllBytes(path, bytes);
                Assert.Throws<InvalidDataException>(() => ShardReader.ReadFile(path));
            }
            finally
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
        }

        private static List<ShardGame> BuildFixtureGames()
        {
            var games = new List<ShardGame>();

            // Oyun 0: iki karar; ilki ogrenen + loglanmis, ikincisi terminal.
            var g0 = new ShardGame
            {
                GameId = 1,
                LearnerSide = 1,
                Flags = ShardGameFlags.None,
                CubeValue = 1,
                Winner = 1,
                ResultType = 2,
                ResultPoints = 2,
            };

            var chosen = new float[ShardConstants.VectorSize];
            for (int j = 0; j < chosen.Length; j++)
            {
                chosen[j] = j * 0.25f;
            }

            var candVectors = new float[2 * ShardConstants.VectorSize];
            for (int k = 0; k < 2; k++)
            {
                for (int j = 0; j < ShardConstants.VectorSize; j++)
                {
                    candVectors[(k * ShardConstants.VectorSize) + j] = (k * 0.5f) + (j * 0.25f);
                }
            }

            float[] q = { 0.5f, 0.4f };
            g0.Decisions.Add(new ShardDecision
            {
                Mover = 1,
                Flags = ShardDecisionFlags.IsLearner,
                CandidateTotal = 5,
                SearchValue = 0.25f,
                ChosenVector = chosen,
                Q = q,
                PolicyTargetCs = Softmax(q, FixtureTau),
                CandidateVectors = candVectors,
            });

            g0.Decisions.Add(new ShardDecision
            {
                Mover = -1,
                Flags = ShardDecisionFlags.IsLearner | ShardDecisionFlags.ChosenIsTerminal,
                CandidateTotal = 1,
                SearchValue = -2.0f,
            });

            games.Add(g0);

            // Oyun 1: iptal edilmis (egitimde kullanilmaz).
            var g1 = new ShardGame
            {
                GameId = 2,
                LearnerSide = 0,
                Flags = ShardGameFlags.Aborted,
                CubeValue = 1,
                Winner = 0,
                ResultType = 0,
                ResultPoints = 0,
            };
            g1.Decisions.Add(new ShardDecision
            {
                Mover = 1,
                Flags = ShardDecisionFlags.IsLearner | ShardDecisionFlags.IsPass,
                CandidateTotal = 0,
                SearchValue = 0.0f,
                ChosenVector = new float[ShardConstants.VectorSize],
            });
            games.Add(g1);

            // Oyun 2: havuz rakibi (IsLearner = 0) karari iceren oyun.
            var g2 = new ShardGame
            {
                GameId = 3,
                LearnerSide = -1,
                Flags = ShardGameFlags.None,
                CubeValue = 2,
                Winner = -1,
                ResultType = 1,
                ResultPoints = 1,
            };
            g2.Decisions.Add(new ShardDecision
            {
                Mover = 1,
                Flags = ShardDecisionFlags.None,
                CandidateTotal = 3,
                SearchValue = -0.75f,
                ChosenVector = new float[ShardConstants.VectorSize],
            });
            g2.Decisions.Add(new ShardDecision
            {
                Mover = -1,
                Flags = ShardDecisionFlags.IsLearner | ShardDecisionFlags.ChosenIsTerminal,
                CandidateTotal = 1,
                SearchValue = 1.0f,
            });
            games.Add(g2);

            return games;
        }

        /// <summary>C# <c>BuildRootPolicyTarget</c> ile ayni softmax (tau uygulanmis).</summary>
        private static float[] Softmax(float[] q, float tau)
        {
            var result = new float[q.Length];
            float max = float.NegativeInfinity;
            for (int i = 0; i < q.Length; i++)
            {
                float scaled = q[i] / tau;
                if (scaled > max)
                {
                    max = scaled;
                }
            }

            double sum = 0.0;
            for (int i = 0; i < q.Length; i++)
            {
                double e = Math.Exp((q[i] / tau) - max);
                result[i] = (float)e;
                sum += e;
            }

            for (int i = 0; i < q.Length; i++)
            {
                result[i] = (float)(result[i] / sum);
            }

            return result;
        }
    }
}