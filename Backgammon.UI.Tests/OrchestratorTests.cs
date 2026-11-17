using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>Faz 5 Bolum 8, Test 32-33: <see cref="GameOrchestrator"/>.</summary>
    [TestFixture]
    public sealed class OrchestratorTests
    {
        private static GameOrchestratorOptions Options(ulong seed, FakeEvaluator evaluator)
        {
            return new GameOrchestratorOptions
            {
                Evaluator = evaluator,
                Bearoff = null,
                Met = null,
                Distribution = null,
                SearchSettings = SearchSettings.Default,
                EngineSettings = EngineSettings.Default,
                Random = new Xoshiro256StarStar(seed),
                MaxPlies = 0
            };
        }

        // ------------------------------------------------------------------
        // Test 32
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_DeterministicSelfPlay()
        {
            const int Games = 50;
            const ulong Seed = 0x7A71A_0032UL;

            List<string> first = PlayGames(Seed, Games);
            List<string> second = PlayGames(Seed, Games);

            Assert.That(first.Count, Is.EqualTo(Games), "50 oyun tamamlanmali");
            Assert.That(second.Count, Is.EqualTo(Games));
            Assert.That(second, Is.EqualTo(first), "ayni seed birebir ayni sonuc dizisini vermeli");

            // Farkli seed farkli dizilim uretmeli (determinizm testinin anlamli oldugunun kaniti).
            List<string> other = PlayGames(Seed + 1, Games);
            Assert.That(other, Is.Not.EqualTo(first), "farkli seed farkli dizilim uretmeli");
        }

        private static List<string> PlayGames(ulong seed, int games)
        {
            var evaluator = new FakeEvaluator();
            GameOrchestratorOptions options = Options(seed, evaluator);
            var log = new List<string>(games);

            using (var orchestrator = new GameOrchestrator(options))
            {
                orchestrator.NewMatch(0, false);

                int guard = 0;
                while (log.Count < games && guard++ < 2000000)
                {
                    if (orchestrator.IsGameOver)
                    {
                        GameResult result = orchestrator.Result;
                        log.Add(result.Winner + "|" + (int)result.ResultType + "|" + result.Points +
                                "|" + orchestrator.State.cubeValue);
                        orchestrator.StartNextGame();
                        continue;
                    }

                    switch (orchestrator.State.phase)
                    {
                        case GamePhase.DetermineFirstPlayer:
                        case GamePhase.PreRoll:
                        case GamePhase.WaitForRoll:
                            orchestrator.RollDice();
                            break;

                        case GamePhase.Moving:
                        {
                            MoveList moves = orchestrator.LegalMoves;
                            if (moves.Count == 0)
                            {
                                orchestrator.EndTurn();
                                break;
                            }

                            int pick = (int)(options.Random.NextUInt() % (uint)moves.Count);
                            orchestrator.ApplyMove(moves[pick]);
                            break;
                        }

                        case GamePhase.CubeOffered:
                            orchestrator.Take();
                            break;

                        default:
                            orchestrator.NewGame();
                            break;
                    }
                }

                Assert.That(guard, Is.LessThan(2000000), "oyun dongusu yakinsamadi");
            }

            return log;
        }

        // ------------------------------------------------------------------
        // Test 33
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_ThinkAsyncCancellation()
        {
            var evaluator = new FakeEvaluator();
            GameOrchestratorOptions options = Options(0x7A71A_0033UL, evaluator);

            using (var orchestrator = new GameOrchestrator(options))
            {
                orchestrator.NewMatch(0, false);
                orchestrator.RollDice();
                while (orchestrator.State.phase != GamePhase.Moving)
                {
                    orchestrator.RollDice();
                }

                // (a) Onceden iptal edilmis token => OperationCanceledException.
                using (var cancelled = new CancellationTokenSource())
                {
                    cancelled.Cancel();
                    Assert.ThrowsAsync<OperationCanceledException>(
                        async () => await orchestrator.ThinkAsync(cancelled.Token).ConfigureAwait(false));
                }

                // (b) Butce asilirsa en iyi hamle yine doner, WasCancelled = true.
                SearchOutcome budgeted = orchestrator
                    .ThinkAsync(CancellationToken.None, TimeSpan.Zero)
                    .GetAwaiter().GetResult();

                Assert.Multiple(() =>
                {
                    Assert.That(budgeted.WasCancelled, Is.True, "sifir butce => WasCancelled");
                    Assert.That(budgeted.IsPass, Is.False);
                    Assert.That(budgeted.CandidateCount, Is.GreaterThan(0));
                });

                // (c) UI is parcacigi bloklanmaz: arama baska bir is parcaciginda calisir.
                int callerThread = Thread.CurrentThread.ManagedThreadId;
                evaluator.LastThreadId = 0;

                SearchOutcome outcome = orchestrator
                    .ThinkAsync(CancellationToken.None)
                    .GetAwaiter().GetResult();

                Assert.Multiple(() =>
                {
                    Assert.That(outcome.WasCancelled, Is.False);
                    Assert.That(outcome.CandidateCount, Is.GreaterThan(0));
                    Assert.That(evaluator.LastThreadId, Is.Not.EqualTo(0), "degerlendirici cagrilmali");
                    Assert.That(evaluator.LastThreadId, Is.Not.EqualTo(callerThread),
                                "arama cagiran is parcaciginda calismamali (UI bloklanmaz)");
                });

                // (d) Ayni anda yalnizca tek arama (Bolum 5.4).
                evaluator.DelayFirstCallMs = 200;
                Task<SearchOutcome> running = orchestrator.ThinkAsync(CancellationToken.None);
                Assert.ThrowsAsync<InvalidOperationException>(
                    async () => await orchestrator.ThinkAsync(CancellationToken.None).ConfigureAwait(false));
                running.GetAwaiter().GetResult();
            }
        }

        [Test]
        public void GameOrchestrator_AnalyzeAndCube()
        {
            var evaluator = new FakeEvaluator();
            GameOrchestratorOptions options = Options(0x7A71A_0034UL, evaluator);

            using (var orchestrator = new GameOrchestrator(options))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);

                PositionAnalysis preRoll = orchestrator.AnalyzeCurrent();
                Assert.Multiple(() =>
                {
                    Assert.That(preRoll.PipCountActive, Is.EqualTo(167));
                    Assert.That(preRoll.PipCountOpponent, Is.EqualTo(167));
                    Assert.That(preRoll.RollsToOffActive, Is.EqualTo(-1), "bearoff DB yok => bilinmiyor");
                    Assert.That(preRoll.RollsToOffOpponent, Is.EqualTo(-1));
                    Assert.That(preRoll.FromBearoffDatabase, Is.False);
                    Assert.That(preRoll.IsExact, Is.False);
                    Assert.That(preRoll.Cube.HasValue, Is.True, "PreRoll + CanOffer => kup karari var");
                });

                AdvanceToMoving(orchestrator);

                PositionAnalysis moving = orchestrator.AnalyzeCurrent();
                Assert.Multiple(() =>
                {
                    Assert.That(moving.Cube.HasValue, Is.False, "Moving fazinda kup karari yok");
                    Assert.That(moving.Distribution.HasValue, Is.True, "sezgisel dagilim uretilmeli");
                    Assert.That(moving.Distribution.GetValueOrDefault().IsValid, Is.True);
                });

                IReadOnlyList<PositionAnalysis> candidates = orchestrator.AnalyzeCandidates();
                Assert.That(candidates.Count, Is.EqualTo(orchestrator.LegalMoves.Count));
                foreach (PositionAnalysis candidate in candidates)
                {
                    Assert.That(candidate.PipCountActive, Is.GreaterThan(0));
                }

                CubeDecision decision = orchestrator.EvaluateCube();
                Assert.That(decision.IsDeadCube, Is.False);
            }
        }

        private static void AdvanceToPreRoll(GameOrchestrator orchestrator)
        {
            int guard = 0;
            while (orchestrator.State.phase != GamePhase.PreRoll && guard++ < 200)
            {
                if (orchestrator.State.phase == GamePhase.Moving)
                {
                    orchestrator.EndTurn();
                }
                else
                {
                    orchestrator.RollDice();
                }
            }

            Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.PreRoll), "PreRoll'a ulasilamadi");
        }

        private static void AdvanceToMoving(GameOrchestrator orchestrator)
        {
            int guard = 0;
            while (orchestrator.State.phase != GamePhase.Moving && guard++ < 200)
            {
                orchestrator.RollDice();
            }

            Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving), "Moving'e ulasilamadi");
        }

        [Test]
        public void GameOrchestrator_ThinkRunsOnCallingThread()
        {
            // Unity/Mono altinda ONNX Runtime'in OrtIoBinding nesnesi is parcacigi guvenli
            // degildir; bu yuzden Unity tarafi Think() ile arama yapan is parcaciginda calisir.
            var evaluator = new FakeEvaluator();
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0033UL, evaluator)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToMoving(orchestrator);

                int callerThread = Thread.CurrentThread.ManagedThreadId;
                SearchOutcome outcome = orchestrator.Think();

                Assert.That(evaluator.LastThreadId, Is.EqualTo(callerThread),
                    "Think() arama yapan is parcaciginda calismali");
                Assert.That(outcome.WasCancelled, Is.False);
                Assert.That(outcome.CandidateCount, Is.GreaterThan(0));
                Assert.That(outcome.BestSequence.IsEmpty, Is.False);
                Assert.That(orchestrator.IsSearching, Is.False);
            }
        }

        [Test]
        public void GameOrchestrator_DisposeAndGuards()
        {
            var evaluator = new FakeEvaluator();
            GameOrchestratorOptions options = Options(0x7A71A_0035UL, evaluator);

            var orchestrator = new GameOrchestrator(options);
            orchestrator.NewMatch(0, false);
            orchestrator.Dispose();
            orchestrator.Dispose();

            Assert.Throws<ObjectDisposedException>(() => orchestrator.RollDice());
            Assert.Throws<ObjectDisposedException>(() => orchestrator.AnalyzeCurrent());
            Assert.Throws<ObjectDisposedException>(() => orchestrator.EvaluateCube());

            Assert.Throws<ArgumentNullException>(() => new GameOrchestrator(null));

            var bad = new GameOrchestratorOptions
            {
                Evaluator = null,
                Random = new Xoshiro256StarStar(1),
                SearchSettings = SearchSettings.Default
            };
            Assert.Throws<ArgumentNullException>(() => new GameOrchestrator(bad));

            var badRandom = new GameOrchestratorOptions
            {
                Evaluator = new FakeEvaluator(),
                Random = null,
                SearchSettings = SearchSettings.Default
            };
            Assert.Throws<ArgumentNullException>(() => new GameOrchestrator(badRandom));

            var badPlies = new GameOrchestratorOptions
            {
                Evaluator = new FakeEvaluator(),
                Random = new Xoshiro256StarStar(1),
                SearchSettings = SearchSettings.Default,
                MaxPlies = SearchWorkspace.MaxSupportedPly + 1
            };
            Assert.Throws<ArgumentOutOfRangeException>(() => new GameOrchestrator(badPlies));
        }
    }
}
