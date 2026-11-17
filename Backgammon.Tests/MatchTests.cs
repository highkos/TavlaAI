using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Faz 5 §8 Test 14–26: maç ve küp katmanı.</summary>
    [TestFixture]
    public sealed class MatchTests
    {
        private const string GnubgMetPath = @"F:\Program Files (x86)\gnubg\met\Rockwell-Kazaross.xml";

        // ------------------------------------------------------------------
        // Test 14
        // ------------------------------------------------------------------

        [Test]
        public void MatchEquityTable_Invariants()
        {
            MatchEquityTable met = MatchEquityTable.Default;
            int n = met.MaxMatchLength;
            Assert.That(n, Is.EqualTo(25));

            // 1) Sınırlar.
            for (int b = 1; b <= n; b++)
            {
                Assert.That(met.MatchWinningChance(0, b), Is.EqualTo(1.0).Within(0.0), "MWC(0," + b + ")");
            }

            for (int a = 1; a <= n; a++)
            {
                Assert.That(met.MatchWinningChance(a, 0), Is.EqualTo(0.0).Within(0.0), "MWC(" + a + ",0)");
            }

            Assert.Throws<ArgumentException>(() => met.MatchWinningChance(0, 0));

            // 2) Simetri, 4) köşegen, 5) ME antisimetrisi, 6) aralık ve sonluluk.
            for (int a = 1; a <= n; a++)
            {
                for (int b = 1; b <= n; b++)
                {
                    double mwc = met.MatchWinningChance(a, b);
                    Assert.That(mwc, Is.GreaterThanOrEqualTo(0.0).And.LessThanOrEqualTo(1.0), "aralık (" + a + "," + b + ")");
                    Assert.That(double.IsNaN(mwc) || double.IsInfinity(mwc), Is.False, "sonlu (" + a + "," + b + ")");

                    double mirror = met.MatchWinningChance(b, a);
                    Assert.That(mwc + mirror, Is.EqualTo(1.0).Within(1e-9), "simetri (" + a + "," + b + ")");

                    Assert.That(met.MatchEquity(a, b), Is.EqualTo(-met.MatchEquity(b, a)).Within(1e-12),
                                "ME antisimetri (" + a + "," + b + ")");
                }

                Assert.That(met.MatchWinningChance(a, a), Is.EqualTo(0.5).Within(1e-9), "köşegen " + a);
            }

            // 3) Monotonluk: a artınca kesin azalır, b artınca kesin artar.
            for (int a = 1; a < n; a++)
            {
                for (int b = 1; b <= n; b++)
                {
                    Assert.That(met.MatchWinningChance(a + 1, b), Is.LessThan(met.MatchWinningChance(a, b)),
                                "monoton a (" + a + "," + b + ")");
                }
            }

            for (int a = 1; a <= n; a++)
            {
                for (int b = 1; b < n; b++)
                {
                    Assert.That(met.MatchWinningChance(a, b + 1), Is.GreaterThan(met.MatchWinningChance(a, b)),
                                "monoton b (" + a + "," + b + ")");
                }
            }
        }

        // ------------------------------------------------------------------
        // Test 15
        // ------------------------------------------------------------------

        [Test]
        public void MatchEquityTable_MatchesGnubg()
        {
            if (!File.Exists(GnubgMetPath))
            {
                Assert.Ignore("gnubg MET dosyası yok: " + GnubgMetPath);
            }

            List<List<double>> xml = ParseGnubgMet(GnubgMetPath);
            Assert.That(xml.Count, Is.EqualTo(25), "gnubg MET 25x25 olmalı");

            MatchEquityTable met = MatchEquityTable.Default;
            double maxDiff = 0.0;
            int worstA = 0;
            int worstB = 0;

            for (int a = 1; a <= 25; a++)
            {
                for (int b = 1; b <= 25; b++)
                {
                    double expected = xml[a - 1][b - 1];
                    double actual = met.MatchWinningChance(a, b);
                    double diff = Math.Abs(expected - actual);
                    if (diff > maxDiff)
                    {
                        maxDiff = diff;
                        worstA = a;
                        worstB = b;
                    }
                }
            }

            TestContext.Out.WriteLine("gnubg MET ile maksimum |Δ| = " + maxDiff.ToString("E3", CultureInfo.InvariantCulture) +
                                      " (" + worstA + "," + worstB + ")");
            Assert.That(maxDiff, Is.EqualTo(0.0).Within(1e-12), "gömülü MET gnubg ile birebir olmalı");
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

        // ------------------------------------------------------------------
        // Test 16
        // ------------------------------------------------------------------

        [Test]
        public void MatchState_Derivations()
        {
            // 1) Money game.
            MatchState money = MatchState.MoneyGame;
            Assert.That(money.IsMoneyGame, Is.True);
            Assert.That(money.AwayScore(1), Is.EqualTo(int.MaxValue));
            Assert.That(money.AwayScore(-1), Is.EqualTo(int.MaxValue));
            Assert.That(money.MaxCubeValue, Is.EqualTo(64));
            Assert.That(money.IsDeadCube, Is.False);
            Assert.That(money.IsCrawfordGame, Is.False);
            Assert.That(money.IsPostCrawford, Is.False);

            // 2) 5 puanlık maç, 0-0, küp 1.
            MatchState m2 = new MatchState(5, 0, 0, 1, 0, false, false);
            Assert.That(m2.AwayScore(1), Is.EqualTo(5));
            Assert.That(m2.AwayScore(-1), Is.EqualTo(5));
            Assert.That(m2.IsDeadCube, Is.False);
            Assert.That(m2.MaxCubeValue, Is.EqualTo(4));

            // 3) 5 puanlık maç, 4-0, küp 1: Beyaz 1 away, küp canlı (Siyah için anlamlı).
            MatchState m3 = new MatchState(5, 4, 0, 1, 0, false, false);
            Assert.That(m3.AwayScore(1), Is.EqualTo(1));
            Assert.That(m3.AwayScore(-1), Is.EqualTo(5));
            Assert.That(m3.IsDeadCube, Is.False);
            Assert.That(m3.MaxCubeValue, Is.EqualTo(4));

            // 4) 5 puanlık maç, 4-4, küp 1: her iki taraf 1 away ⇒ küp ölü.
            MatchState m4 = new MatchState(5, 4, 4, 1, 0, false, false);
            Assert.That(m4.IsDeadCube, Is.True);
            Assert.That(m4.MaxCubeValue, Is.EqualTo(1));

            // 5) 5 puanlık maç, 4-4, küp 2: ölü.
            Assert.That(new MatchState(5, 4, 4, 2, 0, false, false).IsDeadCube, Is.True);

            // 6) 3 puanlık maç, 0-0, küp 2: canlı (2→4 maçı bitirir, anlamlı).
            MatchState m6 = new MatchState(3, 0, 0, 2, 0, false, false);
            Assert.That(m6.IsDeadCube, Is.False);
            Assert.That(m6.MaxCubeValue, Is.EqualTo(2));

            // 7) 3 puanlık maç, 0-0, küp 4: ölü.
            Assert.That(new MatchState(3, 0, 0, 4, 0, false, false).IsDeadCube, Is.True);

            // 8) Crawford oyunu: 5 puanlık maç, 4-0.
            MatchState m8 = new MatchState(5, 4, 0, 1, 0, true, false);
            Assert.That(m8.IsCrawfordGame, Is.True);
            Assert.That(m8.IsPostCrawford, Is.False);

            // 9) Post-Crawford: 5 puanlık maç, 4-1, Crawford oynandı.
            MatchState m9 = new MatchState(5, 4, 1, 1, 0, false, true);
            Assert.That(m9.IsCrawfordGame, Is.False);
            Assert.That(m9.IsPostCrawford, Is.True);

            // 10) 2 puanlık maç, 0-0: ulaşılabilen en büyük küp 2.
            MatchState m10 = new MatchState(2, 0, 0, 1, 0, false, false);
            Assert.That(m10.MaxCubeValue, Is.EqualTo(2));
            Assert.That(m10.IsDeadCube, Is.False);

            // Ek: BackgammonState'ten türetme.
            var state = new BackgammonState();
            state.matchLength = 7;
            state.whiteScore = 3;
            state.blackScore = 1;
            state.cubeValue = 2;
            state.cubeOwner = -1;
            state.isCrawfordGame = false;
            state.crawfordPlayed = true;
            MatchState from = MatchState.From(state);
            Assert.That(from.MatchLength, Is.EqualTo(7));
            Assert.That(from.AwayScore(1), Is.EqualTo(4));
            Assert.That(from.AwayScore(-1), Is.EqualTo(6));
            Assert.That(from.CubeOwner, Is.EqualTo(-1));
            Assert.That(from.IsPostCrawford, Is.True);
        }

        // ------------------------------------------------------------------
        // Test 17
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_Invariants()
        {
            var samples = new[]
            {
                new OutcomeDistribution(0.5f, 0f, 0f, 0f, 0f),
                new OutcomeDistribution(0.6f, 0.2f, 0.05f, 0.1f, 0.02f),
                new OutcomeDistribution(1f, 1f, 1f, 0f, 0f),
                new OutcomeDistribution(0f, 0f, 0f, 1f, 1f),
                new OutcomeDistribution(0.75f, 0.25f, 0f, 0.25f, 0f),
            };

            foreach (OutcomeDistribution d in samples)
            {
                Assert.That(d.IsValid, Is.True, d.ToString());
                Assert.That(d.Win + d.Lose, Is.EqualTo(1f).Within(1e-6f));
                Assert.That(d.WinBackgammon, Is.LessThanOrEqualTo(d.WinGammon));
                Assert.That(d.WinGammon, Is.LessThanOrEqualTo(d.Win));
                Assert.That(d.LoseBackgammon, Is.LessThanOrEqualTo(d.LoseGammon));
                Assert.That(d.LoseGammon, Is.LessThanOrEqualTo(d.Lose));
                Assert.That(d.Equity, Is.GreaterThanOrEqualTo(-3.0).And.LessThanOrEqualTo(3.0));
            }

            // Elle hesaplanmış equity örnekleri.
            Assert.That(samples[0].Equity, Is.EqualTo(0.0).Within(1e-6));
            Assert.That(samples[1].Equity, Is.EqualTo(0.33).Within(1e-6));
            Assert.That(samples[2].Equity, Is.EqualTo(3.0).Within(1e-6));
            Assert.That(samples[3].Equity, Is.EqualTo(-3.0).Within(1e-6));
            Assert.That(samples[4].Equity, Is.EqualTo(0.5).Within(1e-6));

            // Geçersiz örnekler.
            Assert.That(new OutcomeDistribution(0.5f, 0.6f, 0f, 0f, 0f).IsValid, Is.False, "WG > W");
            Assert.That(new OutcomeDistribution(0.5f, 0.2f, 0.3f, 0f, 0f).IsValid, Is.False, "WBG > WG");
            Assert.That(new OutcomeDistribution(1.5f, 0f, 0f, 0f, 0f).IsValid, Is.False, "W > 1");
            Assert.That(new OutcomeDistribution(float.NaN, 0f, 0f, 0f, 0f).IsValid, Is.False, "NaN");
        }

        // ------------------------------------------------------------------
        // Test 18
        // ------------------------------------------------------------------

        [Test]
        public void HeuristicOutcomeDistribution_Invariants()
        {
            const int steps = 600;
            const double lo = -3.0;
            const double hi = 3.0;

            foreach (bool contact in new[] { true, false })
            {
                OutcomeDistribution previous = HeuristicOutcomeDistribution.FromEquity(lo, contact, 0);
                Assert.That(previous.IsValid, Is.True, "başlangıç geçerli");

                for (int i = 1; i <= steps; i++)
                {
                    double e = lo + ((hi - lo) * i / steps);
                    OutcomeDistribution current = HeuristicOutcomeDistribution.FromEquity(e, contact, 0);
                    Assert.That(current.IsValid, Is.True, "geçerli e=" + e);

                    Assert.That(current.Win, Is.GreaterThan(previous.Win), "Win artan e=" + e);
                    Assert.That(current.WinGammon, Is.GreaterThanOrEqualTo(previous.WinGammon), "WG azalmaz e=" + e);
                    Assert.That(current.WinBackgammon, Is.GreaterThanOrEqualTo(previous.WinBackgammon), "WBG azalmaz e=" + e);
                    Assert.That(current.LoseGammon, Is.LessThanOrEqualTo(previous.LoseGammon), "LG artmaz e=" + e);
                    Assert.That(current.LoseBackgammon, Is.LessThanOrEqualTo(previous.LoseBackgammon), "LBG artmaz e=" + e);

                    // Süreklilik: ardışık adımlar arasındaki fark küçük.
                    Assert.That(Math.Abs(current.Win - previous.Win), Is.LessThan(0.02), "süreklilik e=" + e);

                    previous = current;
                }
            }

            // Süreklilik: e = 0 civarında sıçrama yok.
            OutcomeDistribution below = HeuristicOutcomeDistribution.FromEquity(-1e-6, true, 0);
            OutcomeDistribution above = HeuristicOutcomeDistribution.FromEquity(1e-6, true, 0);
            Assert.That(Math.Abs(above.Win - below.Win), Is.LessThan(1e-5), "e=0 süreklilik");

            // Simetri: e = 0 ⇒ Win = 0.5, WG = LG, WBG = LBG.
            OutcomeDistribution zero = HeuristicOutcomeDistribution.FromEquity(0.0, true, 0);
            Assert.That(zero.Win, Is.EqualTo(0.5f).Within(1e-6f));
            Assert.That(zero.WinGammon, Is.EqualTo(zero.LoseGammon).Within(1e-6f));
            Assert.That(zero.WinBackgammon, Is.EqualTo(zero.LoseBackgammon).Within(1e-6f));

            // Uçlar (temas).
            OutcomeDistribution top = HeuristicOutcomeDistribution.FromEquity(3.0, true, 0);
            Assert.That(top.Win, Is.EqualTo(1f).Within(1e-6f));
            Assert.That(top.WinGammon, Is.EqualTo(1f).Within(1e-6f));
            Assert.That(top.WinBackgammon, Is.EqualTo(1f).Within(1e-6f));
            Assert.That(top.LoseGammon, Is.EqualTo(0f).Within(1e-6f));

            OutcomeDistribution bottom = HeuristicOutcomeDistribution.FromEquity(-3.0, true, 0);
            Assert.That(bottom.Win, Is.EqualTo(0f).Within(1e-6f));
            Assert.That(bottom.LoseGammon, Is.EqualTo(1f).Within(1e-6f));
            Assert.That(bottom.LoseBackgammon, Is.EqualTo(1f).Within(1e-6f));

            // Saf yarışta backgammon zorunlu olarak 0.
            for (int i = 0; i <= steps; i++)
            {
                double e = lo + ((hi - lo) * i / steps);
                OutcomeDistribution race = HeuristicOutcomeDistribution.FromEquity(e, false, 0);
                Assert.That(race.WinBackgammon, Is.EqualTo(0f), "yarış WBG=0 e=" + e);
                Assert.That(race.LoseBackgammon, Is.EqualTo(0f), "yarış LBG=0 e=" + e);
            }

            // Determinizm.
            OutcomeDistribution a1 = HeuristicOutcomeDistribution.FromEquity(0.42, true, 17);
            OutcomeDistribution a2 = HeuristicOutcomeDistribution.FromEquity(0.42, true, 17);
            Assert.That(a1.Win, Is.EqualTo(a2.Win));
            Assert.That(a1.WinGammon, Is.EqualTo(a2.WinGammon));
            Assert.That(a1.LoseGammon, Is.EqualTo(a2.LoseGammon));
        }

        // ------------------------------------------------------------------
        // Test 19
        // ------------------------------------------------------------------

        [Test]
        public void EquityCubeAdvisor_MoneyGameThresholds()
        {
            Assert.That(EquityCubeAdvisor.MoneyDoublePoint, Is.EqualTo(0.5));
            Assert.That(EquityCubeAdvisor.MoneyTooGoodPoint, Is.EqualTo(1.0));

            CubeDecision e2 = DecideMoney(2.0);
            Assert.That(e2.ShouldDouble, Is.True, "E=2 çiftle");
            Assert.That(e2.ShouldTake, Is.False, "E=2 rakip reddeder");
            Assert.That(e2.IsTooGood, Is.True, "E=2 çok iyi");

            CubeDecision e1 = DecideMoney(1.0);
            Assert.That(e1.ShouldDouble, Is.True, "E=1 çiftle");
            Assert.That(e1.ShouldTake, Is.False, "E=1 rakip reddeder");

            // E = 0.6 > 0.5 ⇒ çiftle; rakip −2E = −1.2 < −1 ⇒ reddeder.
            CubeDecision e06 = DecideMoney(0.6);
            Assert.That(e06.ShouldDouble, Is.True, "E=0.6 çiftle");
            Assert.That(e06.ShouldTake, Is.False, "E=0.6 rakip reddeder");
            Assert.That(e06.IsTooGood, Is.False);

            // E = 0.4 < 0.5 ⇒ çiftleme; rakip −2E = −0.8 > −1 ⇒ kabul eder.
            CubeDecision e04 = DecideMoney(0.4);
            Assert.That(e04.ShouldDouble, Is.False, "E=0.4 çiftleme");
            Assert.That(e04.ShouldTake, Is.True, "E=0.4 rakip kabul eder");
            Assert.That(e04.IsTooGood, Is.False);

            CubeDecision e03 = DecideMoney(0.3);
            Assert.That(e03.ShouldDouble, Is.False, "E=0.3 çiftleme");
            Assert.That(e03.IsTooGood, Is.False);

            // Eşikler formülden türetilir: E_doubleTake = 2E, E_doublePass = 1.
            Assert.That(e06.EquityNoDouble, Is.EqualTo(0.6).Within(1e-6));
            Assert.That(e06.EquityDoubleTake, Is.EqualTo(1.2).Within(1e-6));
            Assert.That(e06.EquityDoublePass, Is.EqualTo(1.0).Within(1e-6));
        }

        private static CubeDecision DecideMoney(double equity)
        {
            var inner = new FixedEvaluator(equity);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
            var advisor = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution, CubeAdvisorOptions.Default);

            BackgammonState state = MoneyPreRoll();
            return advisor.Decide(state, 1);
        }

        // ------------------------------------------------------------------
        // Test 20
        // ------------------------------------------------------------------

        [Test]
        public void EquityCubeAdvisor_CrawfordNoCube()
        {
            var inner = new FixedEvaluator(2.5);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
            var advisor = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution, CubeAdvisorOptions.Default);

            for (int score = 0; score < 10; score++)
            {
                BackgammonState state = MoneyPreRoll();
                state.matchLength = 11;
                state.whiteScore = 10;
                state.blackScore = score;
                state.isCrawfordGame = true;
                state.cubeValue = 1;
                state.cubeOwner = 0;

                CubeDecision decision = advisor.Decide(state, 1);
                Assert.That(decision.ShouldDouble, Is.False, "Crawford'da küp yok (skor " + score + ")");
                Assert.That(advisor.ShouldDouble(state), Is.False);
            }
        }

        // ------------------------------------------------------------------
        // Test 21
        // ------------------------------------------------------------------

        [Test]
        public void EquityCubeAdvisor_DeadCube()
        {
            var inner = new FixedEvaluator(2.5);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
            var advisor = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution, CubeAdvisorOptions.Default);

            // 5 puanlık maç, 4-4, küp 1 ⇒ ölü küp.
            BackgammonState state = MoneyPreRoll();
            state.matchLength = 5;
            state.whiteScore = 4;
            state.blackScore = 4;
            state.cubeValue = 1;
            state.cubeOwner = 0;

            CubeDecision decision = advisor.Decide(state, 1);
            Assert.That(decision.IsDeadCube, Is.True);
            Assert.That(decision.ShouldDouble, Is.False, "ölü küpte çiftleme yok");
            Assert.That(advisor.ShouldDouble(state), Is.False);

            // 3 puanlık maç, 0-0, küp 4 ⇒ ölü.
            BackgammonState state2 = MoneyPreRoll();
            state2.matchLength = 3;
            state2.cubeValue = 4;
            state2.cubeOwner = 0;
            Assert.That(advisor.Decide(state2, 1).ShouldDouble, Is.False);
        }

        // ------------------------------------------------------------------
        // Test 22
        // ------------------------------------------------------------------

        [Test]
        public void EquityCubeAdvisor_PostCrawfordFreeDrop()
        {
            // Post-Crawford: 5 puanlık maç, 4-1, Crawford oynandı, küp var.
            // Sıra Siyah'ta (1 puan, 4 away): 1 away olan Beyaz "ölü küp" kuralı yüzünden
            // teklif edemez, bu yüzden teklif eden Siyah'tır.
            var inner = new FixedEvaluator(-0.3);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);

            BackgammonState state = MoneyPreRoll();
            state.matchLength = 5;
            state.whiteScore = 4;
            state.blackScore = 1;
            state.isCrawfordGame = false;
            state.crawfordPlayed = true;
            state.cubeValue = 1;
            state.cubeOwner = 0;
            state.turn = -1;

            var freeDrop = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution,
                                                 new CubeAdvisorOptions { PostCrawfordFreeDrop = true });
            var noFreeDrop = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution,
                                                   new CubeAdvisorOptions { PostCrawfordFreeDrop = false });

            CubeDecision withFree = freeDrop.Decide(state, -1);
            CubeDecision withoutFree = noFreeDrop.Decide(state, -1);

            Assert.That(MatchState.From(state).IsPostCrawford, Is.True);
            Assert.That(withFree.ShouldDouble, Is.True, "post-Crawford'da çiftleme serbest");

            // Serbest düşüş, rakibin RET değerini 0 kabul eder (§4.4 adım 8). Bu, normalde
            // reddetmenin rakibin lehine olduğu durumda kabul eşiğini DEĞİŞTİRİR.
            Assert.That(withFree.ShouldTake, Is.Not.EqualTo(withoutFree.ShouldTake),
                        "serbest düşüş kabul kararını değiştirmeli");
            Assert.That(withFree.ShouldTake, Is.True, "serbest düşüşte ret değeri 0 ⇒ kabul");
            Assert.That(withoutFree.ShouldTake, Is.False, "serbest düşüş yoksa ret değeri pozitif ⇒ ret");
        }

        // ------------------------------------------------------------------
        // Test 23
        // ------------------------------------------------------------------

        [Test]
        public void MatchAwareEvaluator_Antisymmetry()
        {
            var rng = new Random(20260510);
            var inner = new FixedEvaluator(0.0);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
            var match = new MatchState(7, 2, 3, 2, 0, false, false);

            var evaluator = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution, match);

            var list = new AfterStateList(1);
            var scalars = new VectorizerScalars(2, 0, 7, 2, 3, false);
            var results = new float[1];

            for (int i = 0; i < 100; i++)
            {
                double equity = (rng.NextDouble() * 6.0) - 3.0;
                inner.Equity = (float)equity;

                BackgammonState state = RandomBoard(rng);
                list.Clear();
                list.Add(state, default);

                evaluator.EvaluateBatch(list, 0, 1, 1, scalars, results);
                float white = results[0];

                evaluator.EvaluateBatch(list, 0, 1, -1, scalars, results);
                float black = results[0];

                Assert.That(white, Is.EqualTo(-black).Within(1e-6f), "ME antisimetri #" + i);
                Assert.That(white, Is.GreaterThanOrEqualTo(-1f).And.LessThanOrEqualTo(1f), "ME aralık #" + i);
            }
        }

        // ------------------------------------------------------------------
        // Test 24
        // ------------------------------------------------------------------

        [Test]
        public void MatchAwareEvaluator_ChangesArgmax()
        {
            // 2-away/2-away: mars maçı bitirir. Yapay iki aday:
            //   A: yüksek equity, mars yok  (E = 0.80)
            //   B: düşük equity, mars var   (E = 0.55)
            // Küpsüz argmax A'dır. Maçta B marsla maçı bitirir ⇒ argmax B olmalı.
            var inner = new ScriptedEvaluator();
            var distribution = new ScriptedDistribution();
            var match = new MatchState(2, 0, 0, 1, 0, false, false);

            var evaluator = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution, match);

            var list = new AfterStateList(2);
            var state = new BackgammonState();
            state.turn = 1;
            list.Add(state, default);
            list.Add(state, default);

            var scalars = new VectorizerScalars(1, 0, 2, 0, 0, false);
            var results = new float[2];

            inner.Equities = new[] { 0.80f, 0.55f };
            distribution.Distributions = new[]
            {
                // E = 0.90 - 0.10 = 0.80
                new OutcomeDistribution(0.90f, 0.00f, 0.00f, 0.10f, 0.00f),
                // E = 0.70 + 0.35 - 0.30 - 0.20 = 0.55
                new OutcomeDistribution(0.70f, 0.35f, 0.00f, 0.20f, 0.00f),
            };

            evaluator.EvaluateBatch(list, 0, 2, 1, scalars, results);

            // Küpsüz argmax: A (0.80 > 0.55).
            Assert.That(inner.Equities[0], Is.GreaterThan(inner.Equities[1]));

            // Maçta (2-away/2-away):
            //   A ⇒ 0.90·MWC(1,2) = 0.90·0.676888 = 0.609199 ⇒ ME = 0.218398
            //   B ⇒ 0.35·MWC(1,2) + 0.35·MWC(0,2) + 0.10·MWC(2,1) = 0.619222 ⇒ ME = 0.238444
            Assert.That(results[0], Is.EqualTo(0.218398).Within(1e-4), "A maç equity'si");
            Assert.That(results[1], Is.EqualTo(0.238444).Within(1e-4), "B maç equity'si");
            Assert.That(results[1], Is.GreaterThan(results[0]), "argmax değişti: B seçilmeli");
        }

        // ------------------------------------------------------------------
        // Test 25
        // ------------------------------------------------------------------

        [Test]
        public void MatchAwareEvaluator_MoneyGamePassthrough()
        {
            var rng = new Random(777);
            var inner = new FixedEvaluator(0.0);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
            var evaluator = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution, MatchState.MoneyGame);

            var list = new AfterStateList(8);
            var scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);
            var results = new float[8];
            var expected = new float[8];

            for (int i = 0; i < 8; i++)
            {
                list.Add(RandomBoard(rng), default);
            }

            for (int round = 0; round < 8; round++)
            {
                inner.Equity = (float)((rng.NextDouble() * 6.0) - 3.0);
                evaluator.EvaluateBatch(list, 0, 8, 1, scalars, results);
                for (int i = 0; i < 8; i++)
                {
                    Assert.That(results[i], Is.EqualTo(inner.Equity), "money game tam devir #" + round + "/" + i);
                }
            }
        }

        // ------------------------------------------------------------------
        // Test 26
        // ------------------------------------------------------------------

        [Test]
        public void MatchAwareEvaluator_VersionIncludesMatch()
        {
            var inner = new FixedEvaluator(0.5);
            var distribution = new HeuristicOutcomeDistributionEvaluator(inner);

            var a = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution,
                                            new MatchState(7, 0, 0, 1, 0, false, false));
            var b = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution,
                                            new MatchState(7, 1, 0, 1, 0, false, false));
            var c = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution,
                                            new MatchState(7, 0, 0, 2, 0, false, false));
            var d = new MatchAwareEvaluator(inner, MatchEquityTable.Default, distribution,
                                            new MatchState(7, 0, 0, 1, 0, false, false));

            Assert.That(a.Version, Is.Not.EqualTo(b.Version), "skor değişince sürüm değişir");
            Assert.That(a.Version, Is.Not.EqualTo(c.Version), "küp değeri değişince sürüm değişir");
            Assert.That(a.Version, Is.EqualTo(d.Version), "aynı bağlam ⇒ aynı sürüm");

            // Farklı iç model ⇒ farklı sürüm.
            var other = new FixedEvaluator(0.5) { VersionOverride = 99 };
            var e = new MatchAwareEvaluator(other, MatchEquityTable.Default,
                                            new HeuristicOutcomeDistributionEvaluator(other),
                                            new MatchState(7, 0, 0, 1, 0, false, false));
            Assert.That(e.Version, Is.Not.EqualTo(a.Version), "iç model değişince sürüm değişir");
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

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

        private static BackgammonState RandomBoard(Random rng)
        {
            var state = new BackgammonState();
            state.Reset();
            state.turn = 1;
            state.phase = GamePhase.Moving;

            Array.Clear(state.board, 0, BackgammonState.BoardSize);
            int white = 15;
            int black = 15;
            while (white > 0)
            {
                int p = rng.Next(1, 25);
                if (state.board[p] < 0)
                {
                    continue;
                }

                state.board[p]++;
                white--;
            }

            while (black > 0)
            {
                int p = rng.Next(1, 25);
                if (state.board[p] > 0)
                {
                    continue;
                }

                state.board[p]--;
                black--;
            }

            return state;
        }

        private sealed class FixedEvaluator : IPolicyValueEvaluator
        {
            public FixedEvaluator(double equity)
            {
                Equity = (float)equity;
            }

            public float Equity;

            public int VersionOverride = 1;

            public int Version
            {
                get { return VersionOverride; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                float value = perspective > 0 ? Equity : -Equity;
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

        private sealed class ScriptedEvaluator : IPolicyValueEvaluator
        {
            public float[] Equities = new float[0];

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = 0; i < count; i++)
                {
                    results[offset + i] = Equities[i];
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

        private sealed class ScriptedDistribution : IOutcomeDistributionEvaluator
        {
            public OutcomeDistribution[] Distributions = new OutcomeDistribution[0];

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                                  in VectorizerScalars scalars, Span<OutcomeDistribution> results)
            {
                for (int i = 0; i < count; i++)
                {
                    results[offset + i] = Distributions[i];
                }
            }
        }
    }
}
