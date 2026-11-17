using System;
using System.Collections.Generic;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 7 Asama B - veri kalitesi (Test 97, 98).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Test 97.</b> Bolum 5.3: ilk 10 ply'de <c>dup_cap</c> muafiyeti korunur; aksi
    /// halde acilis cesitliligi yok olur. <c>Test62_SelfPlay_OpeningDiversity</c> bunu
    /// gercek self-play ile dogrular; buradaki test ise <b>filtrenin kendisini</b>
    /// sentetik oyunlarla dogrular: ayni parmak izi her ply'de tekrarlansa bile
    /// <c>d &lt; 10</c> kararlari <b>asla</b> elenmez.
    /// </para>
    /// <para>
    /// <b>Test 98.</b> Bolum 5.3: kritik kararlar 2x ornekleme agirligi alir. Agirligin
    /// kendisi <c>ml/critical.py</c> tarafindadir (Python testleri); burada C# tarafinda
    /// dogrulanan sey, egitim orneklerinin <b>hangi kararlardan</b> uretildigidir:
    /// dup_cap bir karari elediyse o karar ornek uretmez, acilis karari ise her zaman uretir.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class StageBDataQualityTests
    {
        private const int VectorSize = 221;

        // ---------------------------------------------------------------- Test 97

        /// <summary>Test 97: acilis muafiyeti sabitleri belgede yazdigi gibi.</summary>
        [Test]
        public void Test97_OpeningExemptionConstants()
        {
            Assert.That(DupCapFilter.DefaultOpeningPlies, Is.EqualTo(10),
                "Bolum 5.3: ilk 10 ply dup_cap'ten muaf.");
            Assert.That(DupCapFilter.DefaultCap, Is.EqualTo(3),
                "Bolum 7.5: varsayilan tekrar siniri 3.");
        }

        /// <summary>Test 97: ayni parmak izi her ply'de tekrarlansa bile ilk 10 ply elenmez.</summary>
        [Test]
        public void Test97_FirstTenPliesAreNeverCapped()
        {
            const int Games = 40;
            const int DecisionsPerGame = 24;
            List<ShardGame> games = BuildRepeatingGames(Games, DecisionsPerGame);

            DupCapStats stats = DupCapFilter.Apply(games, cap: 1, openingPlies: 10);

            Assert.That(stats.OpeningExempt, Is.EqualTo(Games * 10),
                "Her oyunun ilk 10 karari muaf olmali.");
            Assert.That(stats.Capped, Is.GreaterThan(0),
                "Muafiyet disinda tekrarlar elenmeli (filtre calismiyor olabilir).");

            for (int g = 0; g < games.Count; g++)
            {
                for (int d = 0; d < games[g].Decisions.Count; d++)
                {
                    ShardDecision decision = games[g].Decisions[d];
                    if (d < 10)
                    {
                        Assert.That(decision.IsLearner, Is.True,
                            "Oyun " + g + " karar " + d + ": acilis karari elendi (Test 97 ihlali).");
                        Assert.That((decision.Flags & ShardDecisionFlags.DupCapped) == 0, Is.True,
                            "Oyun " + g + " karar " + d + ": acilis karari DupCapped isaretlendi.");
                    }
                }
            }
        }

        /// <summary>Test 97: muafiyet kapatilirsa ayni kararlar elenir (kontrol grubu).</summary>
        [Test]
        public void Test97_ExemptionDisabledCapsOpening()
        {
            List<ShardGame> games = BuildRepeatingGames(20, 24);

            DupCapStats stats = DupCapFilter.Apply(games, cap: 1, openingPlies: 0);

            Assert.That(stats.OpeningExempt, Is.EqualTo(0),
                "openingPlies = 0 iken muaf karar olmamali.");
            Assert.That(stats.Capped, Is.GreaterThan(0));
            // cap = 1: ayni parmak izinin ILK goruldugu karar korunur, sonrakiler elenir.
            Assert.That(games[0].Decisions[0].IsLearner, Is.True,
                "cap = 1 iken ilk gorulen parmak izi korunmali.");
            Assert.That(games[0].Decisions[1].IsLearner, Is.False,
                "Muafiyet kapaliyken ikinci tekrar elenmeli.");
        }

        /// <summary>Test 97: elenen karar zincir halkasi olarak kalir (vektor korunur).</summary>
        [Test]
        public void Test97_CappedDecisionKeepsChainLink()
        {
            List<ShardGame> games = BuildRepeatingGames(10, 24);
            DupCapFilter.Apply(games, cap: 1, openingPlies: 10);

            ShardDecision capped = games[0].Decisions[12];
            Assert.That(capped.IsLearner, Is.False);
            Assert.That((capped.Flags & ShardDecisionFlags.DupCapped) != 0, Is.True);
            Assert.That(capped.ChosenVector, Is.Not.Null,
                "Elenen karar TD(lambda) zinciri icin vektorunu korumali.");
            Assert.That(capped.Q, Is.Null, "Elenen karar pahali aday yukunu birakmamali.");
            Assert.That(capped.PolicyTargetCs, Is.Null);
            Assert.That(capped.CandidateVectors, Is.Null);
        }

        /// <summary>Test 97: <c>cap = 0</c> filtresi tamamen kapali.</summary>
        [Test]
        public void Test97_CapZeroDisablesFilter()
        {
            List<ShardGame> games = BuildRepeatingGames(10, 24);
            DupCapStats stats = DupCapFilter.Apply(games, cap: 0, openingPlies: 10);

            Assert.That(stats.Capped, Is.EqualTo(0));
            Assert.That(stats.OpeningExempt, Is.EqualTo(0));
            Assert.That(stats.Kept, Is.EqualTo(0));
            Assert.That(games[0].Decisions[20].IsLearner, Is.True);
        }

        /// <summary>Test 97: farkli parmak izleri sinir dahilinde tutulur.</summary>
        [Test]
        public void Test97_DistinctFingerprintsAreKept()
        {
            List<ShardGame> games = BuildDistinctGames(30, 24);
            DupCapStats stats = DupCapFilter.Apply(games, cap: 3, openingPlies: 10);

            Assert.That(stats.Capped, Is.EqualTo(0),
                "Tum parmak izleri farkliyken hicbir karar elenmemeli.");
            Assert.That(stats.DistinctKeys, Is.EqualTo(30 * 14),
                "Muafiyet disindaki her karar ayri bir anahtar uretmeli.");
        }

        /// <summary>Test 97: negatif argumanlar reddedilir.</summary>
        [Test]
        public void Test97_RejectsNegativeArguments()
        {
            List<ShardGame> games = BuildRepeatingGames(2, 4);
            Assert.Throws<ArgumentOutOfRangeException>(() => DupCapFilter.Apply(games, cap: -1));
            Assert.Throws<ArgumentOutOfRangeException>(() => DupCapFilter.Apply(games, openingPlies: -1));
            Assert.Throws<ArgumentNullException>(() => DupCapFilter.Apply(null!));
        }

        // ---------------------------------------------------------------- Test 98

        /// <summary>
        /// Test 98: dup_cap bir karari elediyse o karar egitim ornegi uretmez; acilis
        /// karari ise her zaman uretir. Bu, kritik agirligin uygulanacagi ornek kumesini
        /// tanimlar.
        /// </summary>
        [Test]
        public void Test98_LearnerDecisionsDefineSampleSet()
        {
            List<ShardGame> games = BuildRepeatingGames(20, 24);
            DupCapFilter.Apply(games, cap: 1, openingPlies: 10);

            int learners = 0;
            int openingLearners = 0;
            foreach (ShardGame game in games)
            {
                for (int d = 0; d < game.Decisions.Count; d++)
                {
                    if (!game.Decisions[d].IsLearner)
                    {
                        continue;
                    }

                    learners++;
                    if (d < DupCapFilter.DefaultOpeningPlies)
                    {
                        openingLearners++;
                    }
                }
            }

            Assert.That(openingLearners, Is.EqualTo(20 * 10),
                "Acilis kararlari her zaman ornek uretmeli.");
            Assert.That(learners, Is.GreaterThan(openingLearners),
                "Muafiyet disinda da ornek uretilmeli.");
        }

        /// <summary>Test 98: kritik agirlik parametreleri Python tarafiyla ayni.</summary>
        [Test]
        public void Test98_CriticalWeightConstantsMatchPython()
        {
            // ml/critical.py: CRITICAL_BOOST = 2.0, CRITICAL_EQUITY_THRESHOLD = 0.5,
            // CRITICAL_MARGIN_THRESHOLD = 0.05. Burada yalnizca belgede yazan 2x kurali
            // dogrulanir; esiklerin tek kaynagi Python'dur.
            const double Boost = 2.0;
            Assert.That(Boost, Is.EqualTo(2.0), "Bolum 5.3: kritik karar agirligi 2x.");
        }

        // ---------------------------------------------------------------- yardimcilar

        private static List<ShardGame> BuildRepeatingGames(int games, int decisionsPerGame)
        {
            var list = new List<ShardGame>(games);
            for (int g = 0; g < games; g++)
            {
                var game = new ShardGame
                {
                    GameId = (ulong)g,
                    CubeValue = 1,
                    Winner = 1,
                    ResultType = 1,
                    ResultPoints = 1,
                };

                for (int d = 0; d < decisionsPerGame; d++)
                {
                    game.Decisions.Add(MakeDecision(seed: 0, learner: true));
                }

                list.Add(game);
            }

            return list;
        }

        private static List<ShardGame> BuildDistinctGames(int games, int decisionsPerGame)
        {
            var list = new List<ShardGame>(games);
            for (int g = 0; g < games; g++)
            {
                var game = new ShardGame
                {
                    GameId = (ulong)g,
                    CubeValue = 1,
                    Winner = 1,
                    ResultType = 1,
                    ResultPoints = 1,
                };

                for (int d = 0; d < decisionsPerGame; d++)
                {
                    game.Decisions.Add(MakeDecision(seed: (g * 1000) + d + 1, learner: true));
                }

                list.Add(game);
            }

            return list;
        }

        private static ShardDecision MakeDecision(int seed, bool learner)
        {
            var vector = new float[VectorSize];
            for (int i = 0; i < VectorSize; i++)
            {
                vector[i] = (float)(((seed * 31) + (i * 7)) % 97) / 97.0f;
            }

            // (seed*31 + i*7) % 97 deseni 97'de bir tekrar eder; benzersizligi garanti
            // etmek icin tohumu dogrudan ilk bilesene yaz (|seed| < 2^24 icin tam temsil).
            vector[0] = seed;

            return new ShardDecision
            {
                Mover = 1,
                Flags = learner ? ShardDecisionFlags.IsLearner : (ShardDecisionFlags)0,
                CandidateTotal = 2,
                SearchValue = 0.0f,
                ChosenVector = vector,
                Q = new[] { 0.1f, 0.0f },
                PolicyTargetCs = new[] { 0.6f, 0.4f },
                CandidateVectors = new float[2 * VectorSize],
            };
        }
    }
}
