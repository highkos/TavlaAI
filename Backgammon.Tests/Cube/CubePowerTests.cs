using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 6 §12.6 Test 83–89: küp ve maç ustalığı.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Test 84, 87 ve 89 ölçüm testleridir (gnubg / self-play) ve <c>ml/tests/test_stage_f.py</c>
    /// içinde yaşar. Bu dosya deterministik C# testlerini (83, 85, 86, 88) barındırır.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class CubePowerTests
    {
        private const string GnubgMetPath = @"F:\Program Files (x86)\gnubg\met\Rockwell-Kazaross.xml";

        // ------------------------------------------------------------------
        // Test 83 — CubeAdvisor_DiceAveraged_IsDefault
        // ------------------------------------------------------------------

        [Test]
        public void Test83_DiceAveraged_IsDefault()
        {
            Assert.That(CubeAdvisorOptions.Default.DiceAveraged, Is.True,
                        "DiceAveraged varsayılan olarak açık olmalı (v3 §10.2)");
            Assert.That(new CubeAdvisorOptions().DiceAveraged, Is.True);

            // Faz 5 davranışı korunur: PostCrawfordFreeDrop varsayılanı değişmedi.
            Assert.That(CubeAdvisorOptions.Default.PostCrawfordFreeDrop, Is.True);

            var evaluator = new PipEvaluator();
            var distribution = new HeuristicOutcomeDistributionEvaluator(evaluator);
            BackgammonState state = MoneyPreRoll();

            var single = new EquityCubeAdvisor(evaluator, MatchEquityTable.Default, distribution,
                                               new CubeAdvisorOptions { DiceAveraged = false });
            var averaged = new EquityCubeAdvisor(evaluator, MatchEquityTable.Default, distribution,
                                                 new CubeAdvisorOptions { DiceAveraged = true });

            CubeDecision singleDecision = single.Decide(state, 1);
            CubeDecision averagedDecision = averaged.Decide(state, 1);

            // (a) DiceAveraged = false → Faz 5 tek-kayıt davranışı BİREBİR.
            double expected = SingleRecordEquity(state, evaluator, 1);
            Assert.That(singleDecision.EquityNoDouble, Is.EqualTo(expected).Within(1e-9),
                        "DiceAveraged=false tek-kayıt değerlendirmesini birebir vermeli");

            // (b) DiceAveraged = true → zar beklentisi alınır, sonuç değişir.
            Assert.That(averagedDecision.EquityNoDouble, Is.Not.EqualTo(singleDecision.EquityNoDouble).Within(1e-9),
                        "zar-ortalamalı değerlendirme tek-kayıttan farklı olmalı");

            // (c) Zar-ortalamalı değer, 21 zar çiftinin ağırlıklı ortalamasıyla aynı olmalı.
            double manual = ManualDiceAverage(state, evaluator, 1);
            Assert.That(averagedDecision.EquityNoDouble, Is.EqualTo(manual).Within(1e-9),
                        "zar-ortalamalı equity 21 çiftin ağırlıklı ortalaması olmalı");

            TestContext.Progress.WriteLine(
                "Test 83 | tek-kayıt=" + singleDecision.EquityNoDouble.ToString("F6", CultureInfo.InvariantCulture) +
                " | zar-ortalamalı=" + averagedDecision.EquityNoDouble.ToString("F6", CultureInfo.InvariantCulture));
        }

        // ------------------------------------------------------------------
        // Test 85 — Crawford_Scenarios_AreCorrect
        // ------------------------------------------------------------------

        [Test]
        public void Test85_Crawford_Scenarios_AreCorrect()
        {
            var evaluator = new PipEvaluator();
            var distribution = new HeuristicOutcomeDistributionEvaluator(evaluator);
            var advisor = new EquityCubeAdvisor(evaluator, MatchEquityTable.Default, distribution,
                                                CubeAdvisorOptions.Default);

            // (a) Crawford oyununda küp YOK — her skorda, her küp değerinde.
            for (int score = 0; score < 10; score++)
            {
                BackgammonState state = MoneyPreRoll();
                state.matchLength = 11;
                state.whiteScore = 10;
                state.blackScore = score;
                state.isCrawfordGame = true;
                state.cubeValue = 1;
                state.cubeOwner = 0;

                Assert.That(MatchState.From(state).IsCrawfordGame, Is.True);
                Assert.That(BackgammonEngine.CanOffer(state), Is.False,
                            "Crawford'da CanOffer false olmalı (skor " + score + ")");
                Assert.That(advisor.Decide(state, 1).ShouldDouble, Is.False,
                            "Crawford'da çiftleme yok (skor " + score + ")");
            }

            // (b) Crawford oyunu maçta TAM BİR kez oynanır.
            int crawfordGames = 0;
            BackgammonState match = MoneyPreRoll();
            match.matchLength = 5;
            match.whiteScore = 0;
            match.blackScore = 0;
            match.cubeValue = 1;
            match.cubeOwner = 0;

            for (int game = 0; game < 12; game++)
            {
                if (MatchState.From(match).IsCrawfordGame)
                {
                    crawfordGames++;
                }

                // Crawford oyununu Beyaz kazanır (1 puan), diğerlerini sırayla.
                var result = new GameResult(1, GameResultType.Single, 1);
                BackgammonEngine.StartNextGame(match, result);
                if (match.phase == GamePhase.GameOver)
                {
                    break;
                }
            }

            Assert.That(crawfordGames, Is.EqualTo(1), "Crawford oyunu tam bir kez oynanmalı");

            // (c) Post-Crawford: küp CANLI (serbest düşüş), Crawford'da olduğu gibi kilitli değil.
            BackgammonState post = MoneyPreRoll();
            post.matchLength = 5;
            post.whiteScore = 4;
            post.blackScore = 1;
            post.isCrawfordGame = false;
            post.crawfordPlayed = true;
            post.cubeValue = 1;
            post.cubeOwner = 0;
            post.turn = -1;

            MatchState postMatch = MatchState.From(post);
            Assert.That(postMatch.IsPostCrawford, Is.True);
            Assert.That(postMatch.IsCrawfordGame, Is.False);
            Assert.That(BackgammonEngine.CanOffer(post), Is.True,
                        "post-Crawford'da küp serbest olmalı (v1 hatası düzeltildi)");

            // (d) Serbest düşüş kabul kararını değiştirir (ret değeri 0 kabul edilir).
            var postEvaluator = new FixedEvaluator(-0.3);
            var postDistribution = new HeuristicOutcomeDistributionEvaluator(postEvaluator);
            var freeDrop = new EquityCubeAdvisor(postEvaluator, MatchEquityTable.Default, postDistribution,
                                                 new CubeAdvisorOptions { PostCrawfordFreeDrop = true });
            var noFreeDrop = new EquityCubeAdvisor(postEvaluator, MatchEquityTable.Default, postDistribution,
                                                   new CubeAdvisorOptions { PostCrawfordFreeDrop = false });

            CubeDecision withFree = freeDrop.Decide(post, -1);
            CubeDecision withoutFree = noFreeDrop.Decide(post, -1);
            Assert.That(withFree.ShouldTake, Is.Not.EqualTo(withoutFree.ShouldTake),
                        "serbest düşüş kabul kararını değiştirmeli");

            TestContext.Progress.WriteLine(
                "Test 85 | Crawford oyunu=" + crawfordGames + " | post-Crawford CanOffer=true" +
                " | serbest düşüş kabul=" + withFree.ShouldTake + " vs " + withoutFree.ShouldTake);
        }

        // ------------------------------------------------------------------
        // Test 86 — CubeDecision_UsesAllSixProbs
        // ------------------------------------------------------------------

        [Test]
        public void Test86_CubeDecision_UsesAllSixProbs()
        {
            // (a) Aynı equity, farklı mars yapısı → farklı MWC. Tek E'ye indirgeme olsaydı
            //     iki dağılım aynı kararı verirdi.
            var flat = OutcomeDistribution.FromProbabilities(0.5f, 0f, 0f, 0.5f, 0f, 0f);
            var gammonRich = OutcomeDistribution.FromProbabilities(0.4f, 0.1f, 0f, 0.6f, 0f, 0f);

            Assert.That(flat.Equity, Is.EqualTo(0.0).Within(1e-6), "düz dağılımın equity'si 0");
            Assert.That(gammonRich.Equity, Is.EqualTo(0.0).Within(1e-6), "marslı dağılımın equity'si de 0");

            double mwcFlat = MatchWinningChance(flat, 3, 3);
            double mwcGammon = MatchWinningChance(gammonRich, 3, 3);
            Assert.That(mwcGammon, Is.Not.EqualTo(mwcFlat).Within(1e-9),
                        "mars bilgisi MWC'yi değiştirmeli — tek E'ye indirgenmemeli");

            // (b) cubeValue çarpımı: reddedilirse teklif eden cubeValue puan kazanır.
            double passCube1 = PassValue(1, 3, 3);
            double passCube2 = PassValue(2, 3, 3);
            Assert.That(passCube2, Is.Not.EqualTo(passCube1).Within(1e-9),
                        "cubeValue reddetme değerini değiştirmeli");

            // (c) Küp sahipliği: sahip olmayan teklif edemez.
            BackgammonState owned = MoneyPreRoll();
            owned.cubeValue = 2;
            owned.cubeOwner = -1;
            Assert.That(BackgammonEngine.CanOffer(owned), Is.False, "küp rakipteyse teklif yok");

            owned.cubeOwner = 1;
            Assert.That(BackgammonEngine.CanOffer(owned), Is.True, "küp kendisindeyse teklif serbest");

            owned.cubeOwner = 0;
            Assert.That(BackgammonEngine.CanOffer(owned), Is.True, "küp ortadaysa teklif serbest");

            // (d) Nötr skaler: skor farkı 0 → MWC 0,5 → equity 0.
            var symmetric = OutcomeDistribution.FromProbabilities(0.5f, 0f, 0f, 0.5f, 0f, 0f);
            double neutral = MatchWinningChance(symmetric, 5, 5);
            Assert.That(neutral, Is.EqualTo(0.5).Within(1e-9), "eşit skorda MWC 0,5 olmalı");
            Assert.That((2.0 * neutral) - 1.0, Is.EqualTo(0.0).Within(1e-9), "nötr skaler 0 olmalı");

            // (e) Danışman gerçekten 6 olasılığı kullanıyor: aynı equity'li iki dağılım
            //     farklı karar üretmeli (DiceAveraged kapalı, tek kayıt).
            var flatAdvisor = new EquityCubeAdvisor(new FixedEvaluator(0.0), MatchEquityTable.Default,
                                                    new FixedDistribution(flat),
                                                    new CubeAdvisorOptions { DiceAveraged = false });
            var gammonAdvisor = new EquityCubeAdvisor(new FixedEvaluator(0.0), MatchEquityTable.Default,
                                                      new FixedDistribution(gammonRich),
                                                      new CubeAdvisorOptions { DiceAveraged = false });

            BackgammonState match = MoneyPreRoll();
            match.matchLength = 3;
            match.whiteScore = 0;
            match.blackScore = 0;
            match.cubeValue = 1;
            match.cubeOwner = 0;

            CubeDecision flatDecision = flatAdvisor.Decide(match, 1);
            CubeDecision gammonDecision = gammonAdvisor.Decide(match, 1);

            // Kontrol: ham equity (money game'de EquityNoDouble) iki dağılımda da 0.
            BackgammonState money = MoneyPreRoll();
            Assert.That(flatAdvisor.Decide(money, 1).EquityNoDouble, Is.EqualTo(0.0).Within(1e-9));
            Assert.That(gammonAdvisor.Decide(money, 1).EquityNoDouble, Is.EqualTo(0.0).Within(1e-9));

            Assert.That(gammonDecision.EquityDoubleTake, Is.Not.EqualTo(flatDecision.EquityDoubleTake).Within(1e-9),
                        "mars bilgisi çiftle-kabul değerini değiştirmeli");

            TestContext.Progress.WriteLine(
                "Test 86 | MWC düz=" + mwcFlat.ToString("F6", CultureInfo.InvariantCulture) +
                " | MWC marslı=" + mwcGammon.ToString("F6", CultureInfo.InvariantCulture) +
                " | pass cube1=" + passCube1.ToString("F6", CultureInfo.InvariantCulture) +
                " cube2=" + passCube2.ToString("F6", CultureInfo.InvariantCulture));
        }

        // ------------------------------------------------------------------
        // Test 88 — Met_StillMatchesGnubg
        // ------------------------------------------------------------------

        [Test]
        public void Test88_Met_StillMatchesGnubg()
        {
            if (!File.Exists(GnubgMetPath))
            {
                Assert.Ignore("gnubg MET dosyası yok: " + GnubgMetPath);
            }

            List<List<double>> xml = ParseGnubgMet(GnubgMetPath);
            Assert.That(xml.Count, Is.EqualTo(25), "gnubg MET 25x25 olmalı");

            MatchEquityTable met = MatchEquityTable.Default;
            double maxDiff = 0.0;
            int cells = 0;
            int worstA = 0;
            int worstB = 0;

            for (int a = 1; a <= 25; a++)
            {
                for (int b = 1; b <= 25; b++)
                {
                    double expected = xml[a - 1][b - 1];
                    double actual = met.MatchWinningChance(a, b);
                    double diff = Math.Abs(expected - actual);
                    cells++;
                    if (diff > maxDiff)
                    {
                        maxDiff = diff;
                        worstA = a;
                        worstB = b;
                    }
                }
            }

            Assert.That(cells, Is.EqualTo(625), "25×25 = 625 hücre karşılaştırılmalı");
            TestContext.Progress.WriteLine(
                "Test 88 | hücre=" + cells + " | maksimum |Δ| = " +
                maxDiff.ToString("E3", CultureInfo.InvariantCulture) + " (" + worstA + "," + worstB + ")");
            Assert.That(maxDiff, Is.EqualTo(0.0).Within(1e-12),
                        "gömülü MET gnubg ile birebir kalmalı (Faz 5 korunur)");
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        /// <summary>Faz 5 tek-kayıt değerlendirmesi: tahtayı doğrudan değerlendirir.</summary>
        private static double SingleRecordEquity(BackgammonState state, IPolicyValueEvaluator evaluator, int perspective)
        {
            var list = new AfterStateList(1);
            list.Add(state, default);
            var scalars = VectorizerScalars.From(state);
            var values = new float[1];
            evaluator.EvaluateBatch(list, 0, 1, perspective, scalars, values);
            double e = values[0];
            return e > 3.0 ? 3.0 : e < -3.0 ? -3.0 : e;
        }

        /// <summary>21 zar çiftinin ağırlıklı ortalaması (bağımsız referans hesabı).</summary>
        private static double ManualDiceAverage(BackgammonState state, IPolicyValueEvaluator evaluator, int perspective)
        {
            int[] first = { 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 6 };
            int[] second = { 1, 2, 3, 4, 5, 6, 2, 3, 4, 5, 6, 3, 4, 5, 6, 4, 5, 6, 5, 6, 6 };

            var scratch = state.Clone();
            var list = new AfterStateList(2048);
            var scalars = VectorizerScalars.From(state);
            var values = new float[2048];
            EngineSettings es = EngineSettings.Default;

            double total = 0.0;
            int weightSum = 0;

            for (int c = 0; c < first.Length; c++)
            {
                int weight = first[c] == second[c] ? 1 : 2;
                scratch.CopyFrom(state);
                BackgammonEngine.SetDice(scratch, first[c], second[c]);
                LegalMoveGenerator.GenerateAfterStates(scratch, es, list);
                if (list.Count == 0)
                {
                    list.AddPass(scratch);
                }

                int n = list.Count;
                evaluator.EvaluateBatch(list, 0, n, perspective, scalars, values.AsSpan(0, n));

                double best = double.NegativeInfinity;
                for (int i = 0; i < n; i++)
                {
                    double v = list.IsTerminal[i]
                        ? list.ResultPoints[i] / (double)scratch.cubeValue
                        : values[i];
                    if (v > best)
                    {
                        best = v;
                    }
                }

                total += weight * best;
                weightSum += weight;
            }

            double e = total / weightSum;
            return e > 3.0 ? 3.0 : e < -3.0 ? -3.0 : e;
        }

        /// <summary>6 olasılıktan MWC (kümülatif dağılım, gnubg düzeni).</summary>
        private static double MatchWinningChance(OutcomeDistribution dist, int awayMover, int awayOpponent)
        {
            MatchEquityTable met = MatchEquityTable.Default;

            double winSingle = dist.Win - dist.WinGammon;
            double winGammon = dist.WinGammon - dist.WinBackgammon;
            double winBackgammon = dist.WinBackgammon;
            double lose = dist.Lose;
            double loseSingle = lose - dist.LoseGammon;
            double loseGammon = dist.LoseGammon - dist.LoseBackgammon;
            double loseBackgammon = dist.LoseBackgammon;

            double mwc = 0.0;
            mwc += winSingle * Chance(met, awayMover - 1, awayOpponent);
            mwc += winGammon * Chance(met, awayMover - 2, awayOpponent);
            mwc += winBackgammon * Chance(met, awayMover - 3, awayOpponent);
            mwc += loseSingle * Chance(met, awayMover, awayOpponent - 1);
            mwc += loseGammon * Chance(met, awayMover, awayOpponent - 2);
            mwc += loseBackgammon * Chance(met, awayMover, awayOpponent - 3);
            return mwc;
        }

        private static double Chance(MatchEquityTable met, int awayMover, int awayOpponent)
        {
            if (awayMover <= 0)
            {
                return 1.0;
            }

            if (awayOpponent <= 0)
            {
                return 0.0;
            }

            return met.MatchWinningChance(awayMover, awayOpponent);
        }

        /// <summary>Reddedilirse teklif eden <c>cubeValue</c> puan kazanır.</summary>
        private static double PassValue(int cubeValue, int awayMover, int awayOpponent)
        {
            MatchEquityTable met = MatchEquityTable.Default;
            return (2.0 * Chance(met, awayMover - cubeValue, awayOpponent)) - 1.0;
        }

        private static BackgammonState MoneyPreRoll()
        {
            var state = new BackgammonState();
            state.Reset();
            state.matchLength = 0;
            state.whiteScore = 0;
            state.blackScore = 0;
            state.cubeValue = 1;
            state.cubeOwner = 0;
            state.isCrawfordGame = false;
            state.crawfordPlayed = false;
            state.cubePassed = false;
            state.turn = 1;
            state.phase = GamePhase.PreRoll;
            return state;
        }

        private static List<List<double>> ParseGnubgMet(string path)
        {
            string raw = File.ReadAllText(path);
            Match block = Regex.Match(raw, "<pre-crawford-table[^>]*>(.*?)</pre-crawford-table>", RegexOptions.Singleline);
            Assert.That(block.Success, Is.True, "pre-crawford-table bulunamadı");

            var rows = new List<List<double>>();
            foreach (Match row in Regex.Matches(block.Groups[1].Value, "<row>(.*?)</row>", RegexOptions.Singleline))
            {
                var values = new List<double>();
                foreach (Match me in Regex.Matches(row.Groups[1].Value, "<me>([-0-9.eE+]+)</me>"))
                {
                    values.Add(double.Parse(me.Groups[1].Value, CultureInfo.InvariantCulture));
                }

                rows.Add(values);
            }

            return rows;
        }

        /// <summary>Tahtaya duyarlı deterministik değerlendirici: pip farkı / 50, [−3, 3].</summary>
        private sealed class PipEvaluator : IPolicyValueEvaluator
        {
            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = 0; i < count; i++)
                {
                    ReadOnlySpan<sbyte> board = list.BoardOf(offset + i);
                    int diff = HeuristicOutcomeDistributionEvaluator.PipDifference(board, perspective);
                    // PipDifference = (bizim pip) − (rakip pip); az pip iyidir ⇒ işaret ters.
                    double e = -diff / 50.0;
                    if (e > 3.0)
                    {
                        e = 3.0;
                    }
                    else if (e < -3.0)
                    {
                        e = -3.0;
                    }

                    results[offset + i] = (float)e;
                }
            }

            public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> priorities)
            {
                float value = count == 0 ? 0f : 1f / count;
                for (int i = 0; i < count; i++)
                {
                    priorities[offset + i] = value;
                }
            }
        }

        private sealed class FixedEvaluator : IPolicyValueEvaluator
        {
            private readonly float _equity;

            public FixedEvaluator(double equity)
            {
                _equity = (float)equity;
            }

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                float value = perspective > 0 ? _equity : -_equity;
                for (int i = 0; i < count; i++)
                {
                    results[offset + i] = value;
                }
            }

            public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> priorities)
            {
                float value = count == 0 ? 0f : 1f / count;
                for (int i = 0; i < count; i++)
                {
                    priorities[offset + i] = value;
                }
            }
        }

        private sealed class FixedDistribution : IOutcomeDistributionEvaluator
        {
            private readonly OutcomeDistribution _distribution;

            public FixedDistribution(OutcomeDistribution distribution)
            {
                _distribution = distribution;
            }

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                                  in VectorizerScalars scalars, Span<OutcomeDistribution> results)
            {
                for (int i = 0; i < count; i++)
                {
                    results[offset + i] = _distribution;
                }
            }
        }
    }
}
