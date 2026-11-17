using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 3 v7 Bölüm 8: zorunlu testler (17 madde). Aşama A'da <b>kırmızı</b> yazılır.
    /// </summary>
    [TestFixture]
    public class SearchTests
    {
        private static readonly EngineSettings Es = EngineSettings.Default;

        private static SearchSettings MakeSettings(int depth, bool ab, bool star1, bool cache, bool policyOrder,
                                                   int maxRoot = 0, int maxInner = 0, bool exact = true,
                                                   float tau = 1f)
        {
            return new SearchSettings
            {
                DepthPly = depth,
                MaxCandidatesRoot = maxRoot,
                MaxCandidatesInner = maxInner,
                UseAlphaBeta = ab,
                UseStar1 = star1,
                UseEvalCache = cache,
                UsePolicyOrdering = policyOrder,
                ExactRootScores = exact,
                PolicyTemperature = tau
            };
        }

        /// <summary>Sabit pozisyonlar + rastgele pozisyonlar (toplam <paramref name="count"/>).</summary>
        private static List<BackgammonState> BuildPositionSet(IRandom rng, int count)
        {
            var list = new List<BackgammonState>
            {
                SearchTestSupport.Starting(3, 1),
                SearchTestSupport.Starting(6, 6),
                SearchTestSupport.Starting(1, 2),
                SearchTestSupport.MidGame(3, 5),
                SearchTestSupport.MidGame(1, 1),
                SearchTestSupport.MidGame(6, 2),
                SearchTestSupport.WhiteOnBar(2, 5),
                SearchTestSupport.BlackOnBar(2, 5),
                SearchTestSupport.WhiteOnBar(6, 6),
                SearchTestSupport.BlackOnBar(1, 3),
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.BearOff(6, 6),
                SearchTestSupport.BearOff(1, 1),
                SearchTestSupport.SingleCheckerEndgame(3, 1),
                SearchTestSupport.SingleCheckerEndgame(6, 6),
                SearchTestSupport.BothBarBlocked(3, 4)
            };

            while (list.Count < count)
            {
                int d1 = 1 + (int)(rng.NextUInt() % 6u);
                int d2 = 1 + (int)(rng.NextUInt() % 6u);
                var s = SearchTestSupport.RandomPosition(rng, d1, d2);
                if (s.whiteBorneOff >= 15 || s.blackBorneOff >= 15)
                {
                    continue;
                }

                list.Add(s);
            }

            return list;
        }

        /// <summary>Küçük, hızlı bitiş pozisyonları (depth 2 için).</summary>
        private static List<BackgammonState> BuildEndgameSet(IRandom rng, int count)
        {
            var list = new List<BackgammonState>
            {
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.BearOff(6, 6),
                SearchTestSupport.BearOff(1, 1),
                SearchTestSupport.SingleCheckerEndgame(3, 1),
                SearchTestSupport.SingleCheckerEndgame(6, 6)
            };

            while (list.Count < count)
            {
                var s = SearchTestSupport.BearOff(1 + (int)(rng.NextUInt() % 6u), 1 + (int)(rng.NextUInt() % 6u));
                list.Add(s);
            }

            return list;
        }

        // ==================================================================
        // Test 1 — Referans eşitliği (en kritik)
        // ==================================================================

        [Test]
        public void Test01_ReferenceEquality()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF3UL);
            var reference = new ReferenceSearch();
            var ws = new SearchWorkspace(16);
            var positions = BuildPositionSet(rng, 500);

            var pairs = new (IPositionEvaluator Value, IPolicyEvaluator Policy)[]
            {
                (new HashEvaluator(), new HashPolicyEvaluator()),
                (new PipDiffEvaluator(), new ConstantPolicyEvaluator())
            };

            int comparisons = 0;
            int index = 0;

            foreach (var pair in pairs)
            {
                foreach (var pos in positions)
                {
                    index++;
                    foreach (int depth in new[] { 0, 1 })
                    {
                        var refSettings = SearchSettings.Reference(depth);
                        float expected = reference.RootValue(pos, refSettings, Es, pair.Value, pair.Policy);

                        foreach (bool ab in new[] { false, true })
                        {
                            foreach (bool star1 in new[] { false, true })
                            {
                                foreach (bool cache in new[] { false, true })
                                {
                                    foreach (bool policyOrder in new[] { false, true })
                                    {
                                        var ss = MakeSettings(depth, ab, star1, cache, policyOrder);
                                        ws.Reset();
                                        var result = BackgammonSearch.Search(pos, ss, Es, ws, pair.Value, pair.Policy);

                                        Assert.That(result.EvaluationScore,
                                            Is.EqualTo(expected).Within(SearchTestSupport.Tolerance),
                                            "pozisyon #" + index + " depth=" + depth + " ab=" + ab +
                                            " star1=" + star1 + " cache=" + cache + " policy=" + policyOrder);
                                        comparisons++;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            TestContext.Progress.WriteLine("Test 1: " + comparisons + " karsilastirma, " + positions.Count + " pozisyon.");
        }

        [Test]
        public void Test01b_ReferenceEquality_RestrictedCandidates()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF4UL);
            var reference = new ReferenceSearch();
            var ws = new SearchWorkspace(16);
            var positions = BuildPositionSet(rng, 60);

            var pairs = new (IPositionEvaluator Value, IPolicyEvaluator Policy)[]
            {
                (new HashEvaluator(), new HashPolicyEvaluator()),
                (new PipDiffEvaluator(), new ConstantPolicyEvaluator())
            };

            int comparisons = 0;
            int index = 0;

            foreach (var pair in pairs)
            {
                foreach (var pos in positions)
                {
                    index++;
                    foreach (int depth in new[] { 0, 1 })
                    {
                        foreach (int maxCand in new[] { 3, 4 })
                        {
                            foreach (bool ab in new[] { false, true })
                            {
                                foreach (bool star1 in new[] { false, true })
                                {
                                    foreach (bool cache in new[] { false, true })
                                    {
                                        foreach (bool policyOrder in new[] { false, true })
                                        {
                                            // Kısıtlı adaylarda sıralama değeri etkiler; referans da
                                            // aynı sıralama modunu kullanmalı.
                                            var refSettings = SearchSettings.Reference(depth);
                                            refSettings.MaxCandidatesRoot = maxCand;
                                            refSettings.MaxCandidatesInner = maxCand;
                                            refSettings.UsePolicyOrdering = policyOrder;
                                            float expected = reference.RootValue(pos, refSettings, Es, pair.Value, pair.Policy);

                                            var ss = MakeSettings(depth, ab, star1, cache, policyOrder,
                                                                  maxCand, maxCand);
                                            ws.Reset();
                                            var result = BackgammonSearch.Search(pos, ss, Es, ws, pair.Value, pair.Policy);

                                            Assert.That(result.EvaluationScore,
                                                Is.EqualTo(expected).Within(SearchTestSupport.Tolerance),
                                                "pozisyon #" + index + " depth=" + depth + " K=" + maxCand +
                                                " ab=" + ab + " star1=" + star1 + " cache=" + cache +
                                                " policy=" + policyOrder);
                                            comparisons++;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            TestContext.Progress.WriteLine("Test 1b: " + comparisons + " karsilastirma (kisitli).");
        }

        [Test]
        public void Test01c_ReferenceEquality_Depth2()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF5UL);
            var reference = new ReferenceSearch();
            var ws = new SearchWorkspace(16);
            var positions = BuildEndgameSet(rng, 20);

            var pairs = new (IPositionEvaluator Value, IPolicyEvaluator Policy)[]
            {
                (new HashEvaluator(), new HashPolicyEvaluator()),
                (new PipDiffEvaluator(), new ConstantPolicyEvaluator())
            };

            int comparisons = 0;
            int index = 0;

            foreach (var pair in pairs)
            {
                foreach (var pos in positions)
                {
                    index++;
                    foreach (bool ab in new[] { false, true })
                    {
                        foreach (bool star1 in new[] { false, true })
                        {
                            foreach (bool cache in new[] { false, true })
                            {
                                foreach (bool policyOrder in new[] { false, true })
                                {
                                    var refSettings = SearchSettings.Reference(2);
                                    refSettings.UsePolicyOrdering = policyOrder;
                                    float expected = reference.RootValue(pos, refSettings, Es, pair.Value, pair.Policy);

                                    var ss = MakeSettings(2, ab, star1, cache, policyOrder);
                                    ws.Reset();
                                    var result = BackgammonSearch.Search(pos, ss, Es, ws, pair.Value, pair.Policy);

                                    Assert.That(result.EvaluationScore,
                                        Is.EqualTo(expected).Within(SearchTestSupport.Tolerance),
                                        "pozisyon #" + index + " depth=2 ab=" + ab + " star1=" + star1 +
                                        " cache=" + cache + " policy=" + policyOrder);
                                    comparisons++;
                                }
                            }
                        }
                    }
                }
            }

            TestContext.Progress.WriteLine("Test 1c: " + comparisons + " karsilastirma (depth 2).");
        }

        // ==================================================================
        // Test 2 — Ayna simetrisi
        // ==================================================================

        [Test]
        public void Test02_MirrorSymmetry()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF6UL);
            var ws = new SearchWorkspace(16);
            var positions = BuildPositionSet(rng, 120);

            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                var mirrored = SearchTestSupport.Mirror(pos);

                foreach (int depth in new[] { 0, 1 })
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);

                    ws.Reset();
                    var a = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
                    float va = a.EvaluationScore;

                    ws.Reset();
                    var b = BackgammonSearch.Search(mirrored, ss, Es, ws, value, policy);
                    float vb = b.EvaluationScore;

                    Assert.That(va, Is.EqualTo(vb).Within(SearchTestSupport.Tolerance),
                        "ayna degeri pozisyon #" + index + " depth=" + depth);
                }
            }
        }
        // ==================================================================
        // Test 3 — Ply semantigi (Bolum 2)
        // ==================================================================

        [Test]
        public void Test03a_PlySemantics_Depth0_IsArgmaxOfEval0()
        {
            var pos = SearchTestSupport.BearOff(2, 5);

            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(pos, Es, list);
            Assert.That(list.Count, Is.GreaterThan(1), "pozisyon yeterli aday uretmeli");

            var table = new Dictionary<ulong, float>();
            for (int i = 0; i < list.Count; i++)
            {
                if (list.IsTerminal[i])
                {
                    continue;
                }

                table[list.Hash[i]] = ((i * 37) % 100) / 100f - 0.5f;
            }

            float expected = float.NegativeInfinity;
            for (int i = 0; i < list.Count; i++)
            {
                float v = list.IsTerminal[i]
                    ? list.ResultPoints[i] / (float)pos.cubeValue
                    : table[list.Hash[i]];
                if (v > expected)
                {
                    expected = v;
                }
            }

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new TableEvaluator(table), new ConstantPolicyEvaluator());

            Assert.That(result.IsPass, Is.False);
            Assert.That(result.EvaluationScore, Is.EqualTo(expected).Within(SearchTestSupport.Tolerance));
        }

        [Test]
        public void Test03b_PlySemantics_Depth1_HandComputed()
        {
            // Beyaz 12'den oynar (toplayamaz) -> Siyah her zarla toplar -> her yanit terminal (+1 Siyah).
            var pos = SearchTestSupport.SingleCheckerEndgame(3, 1);

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(1, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new PipDiffEvaluator(), new ConstantPolicyEvaluator());

            Assert.That(result.IsPass, Is.False);
            Assert.That(result.EvaluationScore, Is.EqualTo(-1f).Within(SearchTestSupport.Tolerance));
        }

        // ==================================================================
        // Test 4 — Zar kumesi agirliklari (Bolum 2)
        // ==================================================================

        [Test]
        public void Test04_RollSetWeights()
        {
            Assert.That(RollSet.NormalCount, Is.EqualTo(21));
            Assert.That(RollSet.OpeningCount, Is.EqualTo(15));
            Assert.That(RollSet.NormalWeightTotal, Is.EqualTo(36));
            Assert.That(RollSet.OpeningWeightTotal, Is.EqualTo(15));

            int sum = 0;
            int doubles = 0;
            int nonDoubles = 0;

            for (int i = 0; i < RollSet.NormalCount; i++)
            {
                int d1 = RollSet.NormalDie1[i];
                int d2 = RollSet.NormalDie2[i];
                Assert.That(d1, Is.InRange(1, 6));
                Assert.That(d2, Is.InRange(d1, 6), "sira lo<=hi olmali (i=" + i + ")");

                int w = RollSet.NormalWeight[i];
                if (d1 == d2)
                {
                    Assert.That(w, Is.EqualTo(1), "cift zar agirligi 1 olmali (i=" + i + ")");
                    doubles++;
                }
                else
                {
                    Assert.That(w, Is.EqualTo(2), "cift olmayan zar agirligi 2 olmali (i=" + i + ")");
                    nonDoubles++;
                }

                sum += w;
            }

            Assert.That(sum, Is.EqualTo(36));
            Assert.That(doubles, Is.EqualTo(6));
            Assert.That(nonDoubles, Is.EqualTo(15));

            for (int i = 0; i < RollSet.NormalCount; i++)
            {
                int tail = 0;
                for (int k = i + 1; k < RollSet.NormalCount; k++)
                {
                    tail += RollSet.NormalWeight[k];
                }

                Assert.That(RollSet.NormalRemainingWeightAfter[i], Is.EqualTo(tail),
                    "NormalRemainingWeightAfter[" + i + "]");
            }

            int osum = 0;
            for (int i = 0; i < RollSet.OpeningCount; i++)
            {
                int d1 = RollSet.OpeningDie1[i];
                int d2 = RollSet.OpeningDie2[i];
                Assert.That(d1, Is.InRange(1, 6));
                Assert.That(d2, Is.InRange(d1, 6));
                Assert.That(d1, Is.Not.EqualTo(d2), "acilis setinde cift zar olmamali (i=" + i + ")");
                Assert.That(RollSet.OpeningWeight[i], Is.EqualTo(1));
                osum += RollSet.OpeningWeight[i];
            }

            Assert.That(osum, Is.EqualTo(15));

            for (int i = 0; i < RollSet.OpeningCount; i++)
            {
                int tail = 0;
                for (int k = i + 1; k < RollSet.OpeningCount; k++)
                {
                    tail += RollSet.OpeningWeight[k];
                }

                Assert.That(RollSet.OpeningRemainingWeightAfter[i], Is.EqualTo(tail),
                    "OpeningRemainingWeightAfter[" + i + "]");
            }

            Assert.That(RollSet.CountOf(RollSetKind.Normal), Is.EqualTo(21));
            Assert.That(RollSet.CountOf(RollSetKind.Opening), Is.EqualTo(15));
            Assert.That(RollSet.WeightTotalOf(RollSetKind.Normal), Is.EqualTo(36));
            Assert.That(RollSet.WeightTotalOf(RollSetKind.Opening), Is.EqualTo(15));
        }
        // ==================================================================
        // Test 5 — Terminal kisayolu ve degeri (Bolum 1, 2.3b)
        // ==================================================================

        /// <summary>Beyaz 24'te tek tas + <paramref name="whiteOff"/> toplamis; Siyah verilen hanelerde.</summary>
        private static BackgammonState TerminalPosition(int whiteOff, int blackOff, int[] blackPoints, int[] blackCounts)
        {
            var s = SearchTestSupport.Blank(1);
            s.board[24] = 1;
            s.whiteBorneOff = (byte)whiteOff;
            s.blackBorneOff = (byte)blackOff;

            for (int i = 0; i < blackPoints.Length; i++)
            {
                s.board[blackPoints[i]] = (sbyte)(-blackCounts[i]);
            }

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return SearchTestSupport.WithDice(s, 1, 1);
        }

        private static float TerminalOnlyValue(BackgammonState pos, bool jacoby)
        {
            var es = EngineSettings.Default;
            es.EnableJacoby = jacoby;

            // Bos tablo: arama terminali degerlendirmeye kalkarsa patlar.
            var value = new TableEvaluator(new Dictionary<ulong, float>());
            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, es, ws, value, new ConstantPolicyEvaluator());
            return result.EvaluationScore;
        }

        [Test]
        public void Test05a_TerminalBypassesEvaluator()
        {
            // Beyaz 13 toplamis + 24 ve 23'te birer tas; zarlar (1,2).
            //   24->off, 23->off  => terminal (Gammon, 2 puan)
            //   24->off, 23->24   => terminal degil
            var pos = SearchTestSupport.Blank(1);
            pos.board[24] = 1;
            pos.board[23] = 1;
            pos.whiteBorneOff = 13;
            pos.board[6] = -5;
            pos.board[8] = -5;
            pos.board[13] = -5;
            pos.hash = BackgammonEngine.ComputeZobristHash(pos);
            SearchTestSupport.WithDice(pos, 1, 2);

            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(pos, Es, list);

            int terminal = -1;
            int nonTerminal = -1;
            for (int i = 0; i < list.Count; i++)
            {
                if (list.IsTerminal[i])
                {
                    terminal = i;
                }
                else
                {
                    nonTerminal = i;
                }
            }

            Assert.That(terminal, Is.GreaterThanOrEqualTo(0), "terminal afterstate bekleniyordu");
            Assert.That(nonTerminal, Is.GreaterThanOrEqualTo(0), "terminal olmayan afterstate bekleniyordu");
            Assert.That(list.ResultType[terminal], Is.EqualTo((byte)GameResultType.Gammon));
            Assert.That(list.ResultPoints[terminal], Is.EqualTo(2));

            var table = new Dictionary<ulong, float> { { list.Hash[nonTerminal], -2.9f } };

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new TableEvaluator(table), new ConstantPolicyEvaluator());

            Assert.That(result.EvaluationScore, Is.EqualTo(2f).Within(SearchTestSupport.Tolerance),
                "terminal deger ResultPoints/cubeValue'den gelmeli");
            Assert.That(result.BestSequence.Count, Is.EqualTo(2));
        }

        [Test]
        public void Test05b_TerminalValue_Single()
        {
            var pos = TerminalPosition(14, 14, new[] { 1 }, new[] { 1 });
            Assert.That(TerminalOnlyValue(pos, false), Is.EqualTo(1f).Within(SearchTestSupport.Tolerance));
        }

        [Test]
        public void Test05c_TerminalValue_Gammon()
        {
            var pos = TerminalPosition(14, 0, new[] { 6, 8, 13 }, new[] { 5, 5, 5 });
            Assert.That(TerminalOnlyValue(pos, false), Is.EqualTo(2f).Within(SearchTestSupport.Tolerance));
        }

        [Test]
        public void Test05d_TerminalValue_Backgammon()
        {
            var pos = TerminalPosition(14, 0, new[] { 6, 8, 20 }, new[] { 5, 5, 5 });
            Assert.That(TerminalOnlyValue(pos, false), Is.EqualTo(3f).Within(SearchTestSupport.Tolerance));
        }

        [Test]
        public void Test05e_TerminalValue_Jacoby()
        {
            var pos = TerminalPosition(14, 0, new[] { 6, 8, 13 }, new[] { 5, 5, 5 });
            Assert.That(TerminalOnlyValue(pos, true), Is.EqualTo(1f).Within(SearchTestSupport.Tolerance),
                "Jacoby acikken Gammon 1 puana duser");
        }

        [Test]
        public void Test05f_TerminalOnly_NoEvaluatorCalls()
        {
            var pos = TerminalPosition(14, 0, new[] { 6, 8, 13 }, new[] { 5, 5, 5 });

            var value = new CountingEvaluator(new TableEvaluator(new Dictionary<ulong, float>()));
            var policy = new CountingPolicyEvaluator(new ConstantPolicyEvaluator());

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, false, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);

            Assert.That(result.EvaluationScore, Is.EqualTo(2f).Within(SearchTestSupport.Tolerance));
            Assert.That(value.Calls, Is.EqualTo(0), "terminal dalda degerlendirici cagrilmamali");
            Assert.That(policy.Calls, Is.EqualTo(0), "terminal dalda politika cagrilmamali");
        }

        [Test]
        public void Test05g_TerminalPartitioning_AllowsVectorizeBatch()
        {
            // VectorizeBatch terminal kayitlarda ArgumentException atar; arama bolumlemeyi
            // dogru yapiyorsa HashEvaluator sorunsuz calisir.
            var pos = SearchTestSupport.Blank(1);
            pos.board[24] = 1;
            pos.board[23] = 1;
            pos.whiteBorneOff = 13;
            pos.board[6] = -5;
            pos.board[8] = -5;
            pos.board[13] = -5;
            pos.hash = BackgammonEngine.ComputeZobristHash(pos);
            SearchTestSupport.WithDice(pos, 1, 2);

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new HashEvaluator(), new HashPolicyEvaluator());

            Assert.That(result.EvaluationScore, Is.EqualTo(2f).Within(SearchTestSupport.Tolerance));
        }

        // ==================================================================
        // Test 6 — State geri yukleme (Bolum 7)
        // ==================================================================

        [Test]
        public void Test06_StateRestored()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF7UL);
            var positions = BuildPositionSet(rng, 40);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                string before = SearchTestSupport.Fingerprint(pos);

                foreach (int depth in new[] { 0, 1 })
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);
                    ws.Reset();
                    BackgammonSearch.Search(pos, ss, Es, ws, value, policy);

                    Assert.That(SearchTestSupport.Fingerprint(pos), Is.EqualTo(before),
                        "state degismemeli: pozisyon #" + index + " depth=" + depth);
                }
            }
        }

        // ==================================================================
        // Test 7 — Pas (Bolum 2, 4.5)
        // ==================================================================

        [Test]
        public void Test07a_Pass_EvaluatesPassAfterState()
        {
            var pos = SearchTestSupport.BothBarBlocked(3, 4);

            // Pas afterstate'i = pozisyon DEĞİŞMEZ (turn = mover, hash = pos.hash). Bu, chance
            // düğümünün LoadAfterState + EndTurn zincirinin doğru hash üretmesi için zorunludur.
            var table = new Dictionary<ulong, float> { { pos.hash, 1.234f } };

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new TableEvaluator(table), new ConstantPolicyEvaluator());

            Assert.That(result.IsPass, Is.True);
            Assert.That(result.BestSequence.IsEmpty, Is.True);
            Assert.That(result.EvaluationScore, Is.EqualTo(1.234f).Within(SearchTestSupport.Tolerance),
                "pas afterstate'i (pozisyon degismez, mover perspektifi) degerlendirilmeli");
        }

        [Test]
        public void Test07b_Pass_NoLegalMoves()
        {
            var pos = SearchTestSupport.BothBarBlocked(3, 4);

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new PipDiffEvaluator(), new ConstantPolicyEvaluator());

            Assert.That(result.IsPass, Is.True);
            Assert.That(result.BestSequence.IsEmpty, Is.True);
            Assert.That(result.CandidateCount, Is.EqualTo(1), "pas tek adaydir");
        }

        [Test]
        public void Test07c_PassChain_TerminatesAtAllDepths()
        {
            var white = SearchTestSupport.BothBarBlocked(3, 4);
            var black = SearchTestSupport.Mirror(white);

            var ws = new SearchWorkspace(16);
            var value = new PipDiffEvaluator();

            foreach (var pos in new[] { white, black })
            {
                for (int depth = 0; depth <= SearchWorkspace.MaxSupportedPly; depth++)
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);
                    ws.Reset();
                    var result = BackgammonSearch.Search(pos, ss, Es, ws, value, new ConstantPolicyEvaluator());

                    Assert.That(result.IsPass, Is.True, "depth=" + depth);
                    Assert.That(float.IsFinite(result.EvaluationScore), Is.True, "depth=" + depth);
                    Assert.That(result.EvaluationScore, Is.InRange(BackgammonSearch.L, BackgammonSearch.U), "depth=" + depth);
                    Assert.That(result.EvaluationScore, Is.EqualTo(0f).Within(1e-4f),
                        "simetrik pozisyon -> 0 (depth=" + depth + ")");
                }
            }
        }
        // ==================================================================
        // Test 8 — Determinizm (Bolum 7)
        // ==================================================================

        [Test]
        public void Test08a_Determinism_Repeat()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF8UL);
            var positions = BuildPositionSet(rng, 30);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                foreach (int depth in new[] { 0, 1 })
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);

                    ws.Reset();
                    var a = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
                    float va = a.EvaluationScore;
                    string sa = a.BestSequence.ToString();

                    ws.Reset();
                    var b = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
                    float vb = b.EvaluationScore;
                    string sb = b.BestSequence.ToString();

                    Assert.That(vb, Is.EqualTo(va), "tekrar ayni deger: #" + index + " depth=" + depth);
                    Assert.That(sb, Is.EqualTo(sa), "tekrar ayni hamle: #" + index + " depth=" + depth);
                }
            }
        }

        [Test]
        public void Test08b_Determinism_Threads()
        {
            var rng = new Xoshiro256StarStar(0x5EEDF9UL);
            var positions = BuildPositionSet(rng, 12);
            var ss = MakeSettings(1, true, true, true, true, exact: true);

            var expected = new float[positions.Count];
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var r = BackgammonSearch.Search(positions[i], ss, Es, ws, value, policy);
                expected[i] = r.EvaluationScore;
            }

            var actual = new float[positions.Count];
            var threads = new Thread[4];
            for (int t = 0; t < threads.Length; t++)
            {
                int tid = t;
                threads[t] = new Thread(() =>
                {
                    var localWs = new SearchWorkspace(16);
                    var localValue = new HashEvaluator();
                    var localPolicy = new HashPolicyEvaluator();

                    for (int i = tid; i < positions.Count; i += 4)
                    {
                        localWs.Reset();
                        var r = BackgammonSearch.Search(positions[i], ss, Es, localWs, localValue, localPolicy);
                        actual[i] = r.EvaluationScore;
                    }
                });
                threads[t].Start();
            }

            for (int t = 0; t < threads.Length; t++)
            {
                threads[t].Join();
            }

            for (int i = 0; i < positions.Count; i++)
            {
                Assert.That(actual[i], Is.EqualTo(expected[i]), "thread sonucu ayni olmali: #" + i);
            }
        }

        [Test]
        public void Test08c_Determinism_CacheOnOff()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFAUL);
            var positions = BuildPositionSet(rng, 30);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                foreach (int depth in new[] { 0, 1 })
                {
                    ws.Reset();
                    var a = BackgammonSearch.Search(pos, MakeSettings(depth, true, true, false, true, exact: true),
                        Es, ws, value, policy);
                    float va = a.EvaluationScore;

                    ws.Reset();
                    var b = BackgammonSearch.Search(pos, MakeSettings(depth, true, true, true, true, exact: true),
                        Es, ws, value, policy);
                    float vb = b.EvaluationScore;

                    Assert.That(vb, Is.EqualTo(va), "cache degeri degistirmemeli: #" + index + " depth=" + depth);
                }
            }
        }

        [Test]
        public void Test08d_Determinism_PolicyOrderingOnOff()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFBUL);
            var positions = BuildPositionSet(rng, 30);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                foreach (int depth in new[] { 0, 1 })
                {
                    ws.Reset();
                    var a = BackgammonSearch.Search(pos, MakeSettings(depth, true, true, true, false, exact: true),
                        Es, ws, value, policy);
                    float va = a.EvaluationScore;

                    ws.Reset();
                    var b = BackgammonSearch.Search(pos, MakeSettings(depth, true, true, true, true, exact: true),
                        Es, ws, value, policy);
                    float vb = b.EvaluationScore;

                    Assert.That(vb, Is.EqualTo(va), "politika siralamasi degeri degistirmemeli: #" + index + " depth=" + depth);
                }
            }
        }

        [Test]
        public void Test08e_PolicyVersion_DoesNotClearCache()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFCUL);
            var positions = BuildPositionSet(rng, 10);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();
            var ss = MakeSettings(1, true, true, true, true, exact: true);

            ws.Reset();
            float first = 0f;
            for (int i = 0; i < positions.Count; i++)
            {
                var r = BackgammonSearch.Search(positions[i], ss, Es, ws, value, policy);
                first = r.EvaluationScore;
            }

            int entriesBefore = ws.CacheEntryCount;
            Assert.That(entriesBefore, Is.GreaterThan(0), "cache dolmus olmali");

            policy.Version = 7;

            float second = 0f;
            for (int i = 0; i < positions.Count; i++)
            {
                var r = BackgammonSearch.Search(positions[i], ss, Es, ws, value, policy);
                second = r.EvaluationScore;
            }

            Assert.That(ws.CacheEntryCount, Is.EqualTo(entriesBefore),
                "politika Version degisimi cache'i temizlememeli (Bolum 3.5)");
            Assert.That(second, Is.EqualTo(first), "politika Version degeri degistirmemeli");
        }

        // ==================================================================
        // Test 9 — Budama verimliligi (Bolum 3)
        // ==================================================================

        [Test]
        public void Test09_PruningEfficiency()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFDUL);
            var positions = BuildEndgameSet(rng, 8);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var names = new[]
            {
                "duz (AB/Star1/cache/politika yok)",
                "+ AB",
                "+ AB + Star1",
                "+ AB + Star1 + cache",
                "+ AB + Star1 + cache + politika"
            };

            var settings = new[]
            {
                MakeSettings(1, false, false, false, false, exact: true),
                MakeSettings(1, true, false, false, false, exact: true),
                MakeSettings(1, true, true, false, false, exact: true),
                MakeSettings(1, true, true, true, false, exact: true),
                MakeSettings(1, true, true, true, true, exact: true)
            };

            var baseline = new float[positions.Count];
            var calls = new long[settings.Length];
            var nodes = new long[settings.Length];

            for (int c = 0; c < settings.Length; c++)
            {
                for (int i = 0; i < positions.Count; i++)
                {
                    ws.Reset();
                    var r = BackgammonSearch.Search(positions[i], settings[c], Es, ws, value, policy);
                    calls[c] += r.EvaluatorCalls;
                    nodes[c] += r.NodesVisited;

                    if (c == 0)
                    {
                        baseline[i] = r.EvaluationScore;
                    }
                    else
                    {
                        Assert.That(r.EvaluationScore, Is.EqualTo(baseline[i]).Within(SearchTestSupport.Tolerance),
                            names[c] + " degeri degistirmemeli (#" + i + ")");
                    }
                }
            }

            for (int c = 0; c < settings.Length; c++)
            {
                TestContext.Progress.WriteLine("Test 9 | " + names[c] + " | degerlendirici cagrisi=" + calls[c] +
                                               " | dugum=" + nodes[c]);
            }

            Assert.That(calls[1], Is.LessThanOrEqualTo(calls[0]), "alpha-beta cagri sayisini artirmamali");
            Assert.That(calls[2], Is.LessThanOrEqualTo(calls[1]), "Star1 cagri sayisini artirmamali");

            // Dusmanca politika siralamasi da dogru degeri vermeli.
            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var r = BackgammonSearch.Search(positions[i], settings[4], Es, ws, value, new AdversarialPolicyEvaluator());
                Assert.That(r.EvaluationScore, Is.EqualTo(baseline[i]).Within(SearchTestSupport.Tolerance),
                    "dusmanca politika siralamasi degeri degistirmemeli (#" + i + ")");
            }
        }

        // ==================================================================
        // Test 10 — Sifir allocation (Bolum 6, 7)
        // ==================================================================

        [Test]
        public void Test10_ZeroAllocation()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFEUL);
            var positions = BuildPositionSet(rng, 1000);
            var endgames = BuildEndgameSet(rng, 60);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var settings = new[]
            {
                MakeSettings(0, true, true, true, true, exact: true),
                MakeSettings(1, true, true, true, true, exact: true),
                MakeSettings(2, true, true, true, true, exact: true)
            };

            for (int c = 0; c < settings.Length; c++)
            {
                ws.Reset();
                BackgammonSearch.Search(positions[0], settings[c], Es, ws, value, policy);
            }

            long before = GC.GetAllocatedBytesForCurrentThread();

            for (int i = 0; i < positions.Count; i++)
            {
                for (int c = 0; c < 2; c++)
                {
                    ws.Reset();
                    BackgammonSearch.Search(positions[i], settings[c], Es, ws, value, policy);
                }
            }

            // Depth 2 yalnızca küçük bitiş pozisyonlarında (aksi hâlde test süresi patlar).
            for (int i = 0; i < endgames.Count; i++)
            {
                ws.Reset();
                BackgammonSearch.Search(endgames[i], settings[2], Es, ws, value, policy);
            }

            long after = GC.GetAllocatedBytesForCurrentThread();
            TestContext.Progress.WriteLine("Test 10 | allocation = " + (after - before) + " bayt");
            Assert.That(after - before, Is.EqualTo(0), "arama isinma sonrasi sifir allocation yapmali");
        }

        // ==================================================================
        // Test 11 — Pencere saglamligi (Bolum 3.1, 3.2)
        // ==================================================================

        [Test]
        public void Test11_WindowRobustness()
        {
            var rng = new Xoshiro256StarStar(0x5EEDFFUL);
            var positions = BuildPositionSet(rng, 20);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                for (int depth = 0; depth <= 2; depth++)
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);
                    ws.Reset();
                    var result = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);

                    Assert.That(float.IsFinite(result.EvaluationScore), Is.True, "#" + index + " depth=" + depth);
                    Assert.That(result.EvaluationScore, Is.InRange(BackgammonSearch.L, BackgammonSearch.U),
                        "#" + index + " depth=" + depth);
                }
            }
        }

        // ==================================================================
        // Test 12 — Faz 1 / Faz 2 entegrasyonu (Bolum 5)
        // ==================================================================

        [Test]
        public void Test12_Phase1Phase2Integration()
        {
            var rng = new Xoshiro256StarStar(0x5EEE00UL);
            var positions = BuildPositionSet(rng, 30);

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                var list = new AfterStateList();
                LegalMoveGenerator.GenerateAfterStates(pos, Es, list);
                if (list.Count == 0)
                {
                    list.AddPass(pos);
                }

                int nonTerminal = SearchTestSupport.PartitionNonTerminal(list);
                var dst = pos.Clone();

                for (int i = 0; i < list.Count; i++)
                {
                    BackgammonEngine.LoadAfterState(dst, list, i);
                    Assert.That(dst.turn, Is.EqualTo(pos.turn), "LoadAfterState turn'u degistirmemeli (#" + index + ")");
                    Assert.That(dst.whiteBorneOff, Is.EqualTo(list.WhiteBorneOff[i]));
                    Assert.That(dst.blackBorneOff, Is.EqualTo(list.BlackBorneOff[i]));
                    Assert.That(dst.hash, Is.EqualTo(list.Hash[i]));
                    Assert.That(dst.remainingCount, Is.EqualTo(0));
                    Assert.That(dst.phase, Is.EqualTo(GamePhase.Moving));
                }

                for (int i = 0; i < list.Count; i++)
                {
                    if (!list.IsTerminal[i])
                    {
                        Assert.That(list.ResultType[i], Is.EqualTo(0), "#" + index + " i=" + i);
                        Assert.That(list.ResultPoints[i], Is.EqualTo(0), "#" + index + " i=" + i);
                        continue;
                    }

                    BackgammonEngine.LoadAfterState(dst, list, i);
                    GameResult gr;
                    Assert.That(BackgammonEngine.IsGameOver(dst, Es, out gr), Is.True);
                    Assert.That(list.ResultType[i], Is.EqualTo((byte)gr.ResultType), "#" + index + " i=" + i);
                    Assert.That(list.ResultPoints[i], Is.EqualTo((byte)gr.Points), "#" + index + " i=" + i);
                }

                if (nonTerminal > 0)
                {
                    var scalars = VectorizerScalars.From(pos);
                    var vectors = new float[nonTerminal * BackgammonVectorizer.InputVectorSize];
                    BackgammonVectorizer.VectorizeBatch(list, nonTerminal, pos.turn, scalars, vectors);

                    var single = new float[BackgammonVectorizer.InputVectorSize];
                    for (int i = 0; i < nonTerminal; i++)
                    {
                        BackgammonVectorizer.Vectorize(list.BoardOf(i), list.WhiteBorneOff[i], list.BlackBorneOff[i],
                                                       scalars, pos.turn, single);
                        for (int k = 0; k < single.Length; k++)
                        {
                            Assert.That(vectors[i * BackgammonVectorizer.InputVectorSize + k], Is.EqualTo(single[k]),
                                "batch/tek vektor ayni olmali (#" + index + ", i=" + i + ", k=" + k + ")");
                        }
                    }
                }
            }
        }
        // ==================================================================
        // Test 13 — Kok politika hedefi (Bolum 3.6)
        // ==================================================================

        [Test]
        public void Test13a_PolicyTarget_Properties()
        {
            var rng = new Xoshiro256StarStar(0x5EEE01UL);
            var positions = BuildPositionSet(rng, 30);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                foreach (int depth in new[] { 0, 1 })
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);
                    ws.Reset();
                    var result = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);

                    if (result.IsPass)
                    {
                        Assert.That(result.RootPolicyTarget.Length, Is.EqualTo(0),
                            "pas durumunda RootPolicyTarget bos olmali (#" + index + ")");
                        continue;
                    }

                    Assert.That(result.RootPolicyTarget.Length, Is.EqualTo(result.RootCandidates.Length),
                        "#" + index + " depth=" + depth);

                    float sum = 0f;
                    for (int i = 0; i < result.RootCandidates.Length; i++)
                    {
                        float p = result.RootPolicyTarget[i];
                        Assert.That(p, Is.InRange(0f, 1f), "#" + index + " i=" + i);
                        if (result.RootCandidates[i].Kind == 2)
                        {
                            Assert.That(p, Is.EqualTo(0f), "Kind=2 -> pi=0 (#" + index + " i=" + i + ")");
                        }
                        else
                        {
                            Assert.That(p, Is.GreaterThan(0f), "Kind 0/1 -> pi>0 (#" + index + " i=" + i + ")");
                        }

                        sum += p;
                    }

                    Assert.That(sum, Is.EqualTo(1f).Within(1e-5f),
                        "toplam 1 olmali (#" + index + " depth=" + depth + ")");
                }
            }
        }

        [Test]
        public void Test13b_PolicyTarget_HandComputedSoftmax()
        {
            var pos = SearchTestSupport.BearOff(2, 5);

            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(pos, Es, list);
            Assert.That(list.Count, Is.GreaterThan(1));

            var table = new Dictionary<ulong, float>();
            for (int i = 0; i < list.Count; i++)
            {
                table[list.Hash[i]] = (i % 5) * 0.3f - 0.6f;
            }

            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true, tau: 1f);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new TableEvaluator(table), new ConstantPolicyEvaluator());

            int n = result.RootCandidates.Length;
            Assert.That(n, Is.EqualTo(list.Count));

            float max = float.NegativeInfinity;
            for (int i = 0; i < n; i++)
            {
                if (result.RootCandidates[i].Score > max)
                {
                    max = result.RootCandidates[i].Score;
                }
            }

            float denom = 0f;
            for (int i = 0; i < n; i++)
            {
                denom += (float)Math.Exp((result.RootCandidates[i].Score - max) / 1f);
            }

            for (int i = 0; i < n; i++)
            {
                float expected = (float)Math.Exp((result.RootCandidates[i].Score - max) / 1f) / denom;
                Assert.That(result.RootPolicyTarget[i], Is.EqualTo(expected).Within(1e-5f), "i=" + i);
            }
        }

        [Test]
        public void Test13c_PolicyTarget_Temperature()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            ws.Reset();
            var hot = BackgammonSearch.Search(pos, MakeSettings(0, true, true, true, true, exact: true, tau: 1f),
                Es, ws, value, policy);
            var hotTarget = new float[hot.RootPolicyTarget.Length];
            hot.RootPolicyTarget.CopyTo(hotTarget);

            ws.Reset();
            var cold = BackgammonSearch.Search(pos, MakeSettings(0, true, true, true, true, exact: true, tau: 0.1f),
                Es, ws, value, policy);
            var coldTarget = new float[cold.RootPolicyTarget.Length];
            cold.RootPolicyTarget.CopyTo(coldTarget);

            Assert.That(coldTarget.Length, Is.EqualTo(hotTarget.Length));

            bool differs = false;
            for (int i = 0; i < hotTarget.Length; i++)
            {
                if (Math.Abs(hotTarget[i] - coldTarget[i]) > 1e-4f)
                {
                    differs = true;
                }
            }

            Assert.That(differs, Is.True, "tau degisince hedef degismeli");
        }

        [Test]
        public void Test13d_PolicyTarget_EmptyWhenNotExact()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: false);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new HashEvaluator(), new HashPolicyEvaluator());

            Assert.That(result.RootPolicyTarget.Length, Is.EqualTo(0),
                "ExactRootScores=false -> bos span (null degil)");
        }

        [Test]
        public void Test13e_PolicyTarget_RestrictedCandidates()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, maxRoot: 3, exact: true);
            var result = BackgammonSearch.Search(pos, ss, Es, ws, new HashEvaluator(), new HashPolicyEvaluator());

            Assert.That(result.RootCandidates.Length, Is.GreaterThan(3));

            float deep = 0f;
            float skipped = 0f;
            int deepCount = 0;
            for (int i = 0; i < result.RootCandidates.Length; i++)
            {
                if (result.RootCandidates[i].Kind == 2)
                {
                    skipped += result.RootPolicyTarget[i];
                }
                else
                {
                    deep += result.RootPolicyTarget[i];
                    deepCount++;
                }
            }

            Assert.That(deepCount, Is.EqualTo(3));
            Assert.That(skipped, Is.EqualTo(0f));
            Assert.That(deep, Is.EqualTo(1f).Within(1e-5f));
        }

        // ==================================================================
        // Test 14 — Politika siralamasi determinizmi (Bolum 3.3, 7)
        // ==================================================================

        [Test]
        public void Test14_PolicyOrdering_Deterministic()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(0, true, true, true, true, exact: true);
            var value = new HashEvaluator();

            ws.Reset();
            var a = BackgammonSearch.Search(pos, ss, Es, ws, value, new HashPolicyEvaluator());
            var seqA = new string[a.RootCandidates.Length];
            for (int i = 0; i < seqA.Length; i++)
            {
                seqA[i] = a.RootCandidates[i].Sequence.ToString();
            }

            ws.Reset();
            var b = BackgammonSearch.Search(pos, ss, Es, ws, value, new HashPolicyEvaluator());
            var seqB = new string[b.RootCandidates.Length];
            for (int i = 0; i < seqB.Length; i++)
            {
                seqB[i] = b.RootCandidates[i].Sequence.ToString();
            }

            Assert.That(seqB, Is.EqualTo(seqA), "ayni oncelikler -> ayni sira");

            ws.Reset();
            var c = BackgammonSearch.Search(pos, ss, Es, ws, value, new ConstantPolicyEvaluator());
            Assert.That(c.RootCandidates.Length, Is.EqualTo(a.RootCandidates.Length));
            Assert.That(c.EvaluationScore, Is.EqualTo(a.EvaluationScore).Within(SearchTestSupport.Tolerance));

            ws.Reset();
            var d = BackgammonSearch.Search(pos, ss, Es, ws, value, new NegativePolicyEvaluator());
            Assert.That(d.EvaluationScore, Is.EqualTo(a.EvaluationScore).Within(SearchTestSupport.Tolerance),
                "negatif oncelikler 0'a kirpilmali, patlamamali");
        }

        // ==================================================================
        // Test 15 — Performans raporu (Bolum 8)
        // ==================================================================

        [Test]
        public void Test15_PerformanceReport()
        {
            var rng = new Xoshiro256StarStar(0x5EEE02UL);
            var positions = BuildEndgameSet(rng, 20);
            var ws = new SearchWorkspace(20);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            foreach (int depth in new[] { 1, 2 })
            {
                var ss = MakeSettings(depth, true, true, true, true, exact: true);

                for (int i = 0; i < 3; i++)
                {
                    ws.Reset();
                    BackgammonSearch.Search(positions[i], ss, Es, ws, value, policy);
                }

                var sw = Stopwatch.StartNew();
                long calls = 0;
                long policyCalls = 0;
                long nodes = 0;
                for (int i = 0; i < positions.Count; i++)
                {
                    ws.Reset();
                    var r = BackgammonSearch.Search(positions[i], ss, Es, ws, value, policy);
                    calls += r.EvaluatorCalls;
                    policyCalls += r.PolicyCalls;
                    nodes += r.NodesVisited;
                }

                sw.Stop();
                double seconds = sw.Elapsed.TotalSeconds;
                TestContext.Progress.WriteLine("Test 15 | depth=" + depth +
                                               " | " + (sw.Elapsed.TotalMilliseconds / positions.Count).ToString("F3") + " ms/pozisyon" +
                                               " | dugum/sn=" + (long)(nodes / seconds) +
                                               " | degerlendirici/sn=" + (long)(calls / seconds) +
                                               " | politika/sn=" + (long)(policyCalls / seconds));
            }

            // Politika siralamasinin hiz farki (depth 1).
            var ssOn = MakeSettings(1, true, true, true, true, exact: true);
            var ssOff = MakeSettings(1, true, true, true, false, exact: true);

            long nodesOn = 0;
            long nodesOff = 0;

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                nodesOn += BackgammonSearch.Search(positions[i], ssOn, Es, ws, value, policy).NodesVisited;

                ws.Reset();
                nodesOff += BackgammonSearch.Search(positions[i], ssOff, Es, ws, value, policy).NodesVisited;
            }

            TestContext.Progress.WriteLine("Test 15 | politika siralamasi: dugum acik=" + nodesOn +
                                           " kapali=" + nodesOff);
        }

        // ==================================================================
        // Test 16 — ICombinedBatchEvaluator (Bolum 3.3 adim 5)
        // ==================================================================

        [Test]
        public void Test16a_Combined_SameValueAsSeparate()
        {
            var rng = new Xoshiro256StarStar(0x5EEE03UL);
            var positions = BuildPositionSet(rng, 20);
            var ws = new SearchWorkspace(16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            int index = 0;
            foreach (var pos in positions)
            {
                index++;
                foreach (int depth in new[] { 0, 1 })
                {
                    var ss = MakeSettings(depth, true, true, true, true, exact: true);

                    ws.Reset();
                    var a = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
                    float va = a.EvaluationScore;
                    string sa = a.BestSequence.ToString();

                    ws.Reset();
                    var combined = new CombinedSpyEvaluator(new HashEvaluator(), new HashPolicyEvaluator());
                    var b = BackgammonSearch.Search(pos, ss, Es, ws, combined, combined);
                    float vb = b.EvaluationScore;
                    string sb = b.BestSequence.ToString();

                    Assert.That(vb, Is.EqualTo(va), "birlesik ayni deger (#" + index + " depth=" + depth + ")");
                    Assert.That(sb, Is.EqualTo(sa), "birlesik ayni hamle (#" + index + " depth=" + depth + ")");
                }
            }
        }

        [Test]
        public void Test16b_Combined_UsedAtRootWhenRestricted()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);

            var restricted = MakeSettings(1, true, true, true, true, maxRoot: 4, exact: true);
            var unrestricted = MakeSettings(1, true, true, true, true, maxRoot: 0, exact: true);

            ws.Reset();
            var spyA = new CombinedSpyEvaluator(new HashEvaluator(), new HashPolicyEvaluator());
            var a = BackgammonSearch.Search(pos, restricted, Es, ws, spyA, spyA);
            float va = a.EvaluationScore;
            long runsA = a.EvaluatorCalls + a.PolicyCalls;

            ws.Reset();
            var spyB = new CombinedSpyEvaluator(new HashEvaluator(), new HashPolicyEvaluator());
            var b = BackgammonSearch.Search(pos, unrestricted, Es, ws, spyB, spyB);
            float vb = b.EvaluationScore;
            long runsB = b.EvaluatorCalls + b.PolicyCalls;

            TestContext.Progress.WriteLine("Test 16b | kisitli: birlesik=" + spyA.CombinedCalls +
                                           " calistirma=" + runsA +
                                           " | kisitsiz: birlesik=" + spyB.CombinedCalls + " calistirma=" + runsB);

            Assert.That(spyA.CombinedCalls, Is.GreaterThanOrEqualTo(1),
                "MaxCandidatesRoot > 0 iken kokte EvaluateAndScoreBatch kullanilmali");
            Assert.That(spyB.CombinedCalls, Is.EqualTo(0),
                "MaxCandidatesRoot = 0 iken birlesik cagri gerekmez");
            Assert.That(float.IsFinite(va), Is.True);
            Assert.That(float.IsFinite(vb), Is.True);
        }

        [Test]
        public void Test16c_Combined_CallSites()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var ws = new SearchWorkspace(16);
            var ss = MakeSettings(1, true, true, true, true, maxRoot: 0, exact: true);

            var spy = new CombinedSpyEvaluator(new HashEvaluator(), new HashPolicyEvaluator());
            ws.Reset();
            BackgammonSearch.Search(pos, ss, Es, ws, spy, spy);

            TestContext.Progress.WriteLine("Test 16c | EvaluateBatch=" + spy.EvaluateCalls +
                                           " ScoreBatch=" + spy.ScoreCalls +
                                           " Combined=" + spy.CombinedCalls);

            Assert.That(spy.CombinedCalls, Is.EqualTo(0), "kisitsiz kokte birlesik cagri yok");
            Assert.That(spy.EvaluateCalls, Is.GreaterThan(0), "yapraklarda EvaluateBatch cagrilmali");
            Assert.That(spy.ScoreCalls, Is.GreaterThan(0), "ic max dugumlerinde ScoreBatch cagrilmali");
        }

        [Test]
        public void Test16d_Combined_OutputsIdentical()
        {
            var pos = SearchTestSupport.BearOff(2, 5);
            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(pos, Es, list);
            int nonTerminal = SearchTestSupport.PartitionNonTerminal(list);
            Assert.That(nonTerminal, Is.GreaterThan(1));

            var scalars = VectorizerScalars.From(pos);
            var spy = new CombinedSpyEvaluator(new HashEvaluator(), new HashPolicyEvaluator());

            var combinedValues = new float[nonTerminal];
            var combinedPriorities = new float[nonTerminal];
            spy.EvaluateAndScoreBatch(list, 0, nonTerminal, pos.turn, scalars, combinedValues, combinedPriorities);

            var separateValues = new float[nonTerminal];
            var separatePriorities = new float[nonTerminal];
            spy.EvaluateBatch(list, 0, nonTerminal, pos.turn, scalars, separateValues);
            spy.ScoreBatch(list, 0, nonTerminal, pos.turn, scalars, separatePriorities);

            for (int i = 0; i < nonTerminal; i++)
            {
                Assert.That(combinedValues[i], Is.EqualTo(separateValues[i]), "results ozdes (i=" + i + ")");
                Assert.That(combinedPriorities[i], Is.EqualTo(separatePriorities[i]), "priorities ozdes (i=" + i + ")");
            }
        }

        // Test 16(f): ICombinedBatchEvaluator IPositionEvaluator'dan MIRAS ALMAZ; yalnizca onu
        // uygulayan bir sinif Search'e gecirilemez (derleme hatasi). Bu, Search'in
        // IPositionEvaluator parametresiyle derleme zamaninda zorlanir; ayri bir calistirma
        // testi gerekmez.

        // ==================================================================
        // Test 17 — Model yeniden yukleme (Bolum 3.5, 4.4)
        // ==================================================================

        [Test]
        public void Test17_ModelReload()
        {
            var pos = SearchTestSupport.MidGame(3, 5);
            var ws = new SearchWorkspace(16);
            var value = new VersionedEvaluator(new HashEvaluator());
            var policy = new HashPolicyEvaluator();
            var ss = MakeSettings(1, true, true, true, true, exact: true);

            ws.Reset();
            var r0 = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
            float v0 = r0.EvaluationScore;
            Assert.That(ws.CacheEntryCount, Is.GreaterThan(0), "cache dolmus olmali");

            value.Version = 1;

            var r1 = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
            float v1 = r1.EvaluationScore;
            Assert.That(v1, Is.Not.EqualTo(v0),
                "Version degisimi cache'i temizlemeli; eski Q degerleri sizmamali");

            ws.Reset();
            var r2 = BackgammonSearch.Search(pos, ss, Es, ws, value, policy);
            Assert.That(r2.EvaluationScore, Is.EqualTo(v1), "Reset() sonrasi ayni sonuc");
        }
    }
}