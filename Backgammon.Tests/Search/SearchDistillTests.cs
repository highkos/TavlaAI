using System;
using System.Collections.Generic;
using Backgammon.Core;
using NUnit.Framework;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 7 §5.4 / Test 99: <see cref="SearchSettings.DistillMode"/> kök değeri ve en iyi
    /// hamleyi dışa verir.
    /// </summary>
    [TestFixture]
    public sealed class SearchDistillTests
    {
        /// <summary>Deterministik, geçerli 6 çıktılı dağılım üreten değerlendirici.</summary>
        private sealed class DistributionEvaluator : IPositionEvaluator, IOutcomeDistributionEvaluator
        {
            public int Version { get; set; }

            public int DistributionCalls;

            public int DistributionPositions;

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = 0; i < count; i++)
                {
                    ReadOnlySpan<sbyte> board = list.BoardOf(i);
                    int active = BackgammonVectorizer.CalculatePipCount(board, perspective);
                    int opp = BackgammonVectorizer.CalculatePipCount(board, -perspective);
                    int diff = opp - active;
                    results[i] = 3f * diff / (Math.Abs(diff) + 50f);
                }
            }

            public void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                                  in VectorizerScalars scalars, Span<OutcomeDistribution> results)
            {
                DistributionCalls++;
                DistributionPositions += count;

                for (int i = 0; i < count; i++)
                {
                    ReadOnlySpan<sbyte> board = list.BoardOf(i);
                    int active = BackgammonVectorizer.CalculatePipCount(board, perspective);
                    int opp = BackgammonVectorizer.CalculatePipCount(board, -perspective);
                    int diff = opp - active;
                    float win = 1f / (1f + (float)Math.Exp(-diff / 20.0));
                    float gammon = 0.1f * win;
                    float backgammon = 0.02f * win;
                    float loseGammon = 0.1f * (1f - win);
                    float loseBackgammon = 0.02f * (1f - win);
                    results[i] = OutcomeDistribution.FromProbabilities(
                        win, gammon, backgammon, 1f - win, loseGammon, loseBackgammon);
                }
            }
        }

        /// <summary>Dağılım arayüzünü uygulamayan değerlendirici.</summary>
        private sealed class EquityOnlyEvaluator : IPositionEvaluator
        {
            public int Version { get; set; }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = 0; i < count; i++)
                {
                    results[i] = 0f;
                }
            }
        }

        private static SearchSettings Make(bool distill, int depth = 1)
        {
            return new SearchSettings
            {
                DepthPly = depth,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                UseAlphaBeta = true,
                UseStar1 = true,
                UseEvalCache = true,
                UsePolicyOrdering = false,
                ExactRootScores = true,
                PolicyTemperature = 1f,
                TranspositionCapacity = 0,
                UseBearoffCutoff = false,
                DistillMode = distill
            };
        }

        private static List<BackgammonState> Positions()
        {
            return new List<BackgammonState>
            {
                SearchTestSupport.Starting(3, 1),
                SearchTestSupport.Starting(6, 5),
                SearchTestSupport.Starting(2, 2)
            };
        }

        [Test]
        public void Test99_DistillModeIsOffByDefault()
        {
            Assert.That(SearchSettings.Default.DistillMode, Is.False);
            Assert.That(SearchSettings.Reference(2).DistillMode, Is.False);
        }

        [Test]
        public void Test99_DistillModeFillsRootValue()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;
            SearchSettings ss = Make(distill: true);

            foreach (BackgammonState state in Positions())
            {
                SearchResult result = BackgammonSearch.Search(state, ss, es, ws, evaluator);
                Assert.That(result.IsPass, Is.False);
                Assert.That(result.RootValue.HasValue, Is.True, "DistillMode kök değeri doldurmalı");
                Assert.That(result.RootValue.Value.IsValid, Is.True);
            }
        }

        [Test]
        public void Test99_DistillModeOffLeavesRootValueNull()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;
            SearchSettings ss = Make(distill: false);

            foreach (BackgammonState state in Positions())
            {
                SearchResult result = BackgammonSearch.Search(state, ss, es, ws, evaluator);
                Assert.That(result.RootValue.HasValue, Is.False);
            }
        }

        [Test]
        public void Test99_DistillModeDoesNotChangeBestMoveOrScore()
        {
            var es = EngineSettings.Default;

            foreach (BackgammonState state in Positions())
            {
                var onEvaluator = new DistributionEvaluator();
                var offEvaluator = new DistributionEvaluator();
                var onWs = new SearchWorkspace();
                var offWs = new SearchWorkspace();

                SearchResult on = BackgammonSearch.Search(state, Make(distill: true), es, onWs, onEvaluator);
                SearchResult off = BackgammonSearch.Search(state, Make(distill: false), es, offWs, offEvaluator);

                Assert.That(on.EvaluationScore, Is.EqualTo(off.EvaluationScore));
                Assert.That(on.BestSequence.Count, Is.EqualTo(off.BestSequence.Count));
                Assert.That(on.CandidateCount, Is.EqualTo(off.CandidateCount));
            }
        }

        [Test]
        public void Test99_DistillModeCostsExactlyOneDistributionCall()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;

            BackgammonSearch.Search(Positions()[0], Make(distill: true), es, ws, evaluator);

            Assert.That(evaluator.DistributionCalls, Is.EqualTo(1), "kök değeri tek çağrı olmalı");
            Assert.That(evaluator.DistributionPositions, Is.EqualTo(1), "tek kayıt değerlendirilmeli");
        }

        [Test]
        public void Test99_RootValueIsNormalised()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;

            SearchResult result = BackgammonSearch.Search(Positions()[0], Make(distill: true), es, ws, evaluator);
            Assert.That(result.RootValue.HasValue, Is.True, "damıtma modunda kök değer dolu olmalı");
            OutcomeDistribution d = result.RootValue.GetValueOrDefault();

            float sum = d.WinSingle + d.WinGammonOnly + d.WinBackgammonOnly
                        + d.LoseSingle + d.LoseGammonOnly + d.LoseBackgammonOnly;
            Assert.That(sum, Is.EqualTo(1f).Within(1e-5f));
        }

        [Test]
        public void Test99_RootValueEquityIsInRange()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;

            foreach (BackgammonState state in Positions())
            {
                SearchResult result = BackgammonSearch.Search(state, Make(distill: true), es, ws, evaluator);
                Assert.That(result.RootValue.HasValue, Is.True, "damıtma modunda kök değer dolu olmalı");
                double equity = result.RootValue.GetValueOrDefault().Equity;
                Assert.That(equity, Is.GreaterThanOrEqualTo(-3.0).And.LessThanOrEqualTo(3.0));
            }
        }

        [Test]
        public void Test99_EvaluatorWithoutDistributionLeavesRootValueNull()
        {
            var evaluator = new EquityOnlyEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;

            SearchResult result = BackgammonSearch.Search(Positions()[0], Make(distill: true), es, ws, evaluator);

            Assert.That(result.RootValue.HasValue, Is.False, "dağılım arayüzü yoksa kök değer null");
            Assert.That(result.BestSequence.Count, Is.GreaterThan(0), "arama yine de çalışmalı");
        }

        [Test]
        public void Test99_DistillModeIsDeterministic()
        {
            var es = EngineSettings.Default;

            foreach (BackgammonState state in Positions())
            {
                var a = new DistributionEvaluator();
                var b = new DistributionEvaluator();
                SearchResult ra = BackgammonSearch.Search(state, Make(distill: true), es, new SearchWorkspace(), a);
                SearchResult rb = BackgammonSearch.Search(state, Make(distill: true), es, new SearchWorkspace(), b);

                Assert.That(ra.RootValue.HasValue, Is.True);
                Assert.That(rb.RootValue.HasValue, Is.True);
                Assert.That(ra.RootValue.GetValueOrDefault().Win, Is.EqualTo(rb.RootValue.GetValueOrDefault().Win));
                Assert.That(ra.RootValue.GetValueOrDefault().LoseGammon, Is.EqualTo(rb.RootValue.GetValueOrDefault().LoseGammon));
                Assert.That(ra.EvaluationScore, Is.EqualTo(rb.EvaluationScore));
            }
        }

        [Test]
        public void Test99_DistillModeWorksAtDepthTwo()
        {
            var evaluator = new DistributionEvaluator();
            var ws = new SearchWorkspace();
            var es = EngineSettings.Default;

            SearchResult result = BackgammonSearch.Search(
                Positions()[0], Make(distill: true, depth: 2), es, ws, evaluator);

            Assert.That(result.RootValue.HasValue, Is.True);
            Assert.That(evaluator.DistributionCalls, Is.EqualTo(1));
        }
    }
}
