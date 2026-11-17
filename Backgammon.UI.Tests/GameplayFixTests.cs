using System;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Oynanis hatalarinin regresyon testleri (vurma/bara girme, toplama, skor, kup).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Hata 1-2:</b> <see cref="MoveInputController.TryAddStep"/> adimi elle kurdugunda
    /// <see cref="MoveFlags.Hit"/> kayboluyordu; <see cref="BackgammonEngine.ApplyStep"/> kirilan
    /// tasi bara yalnizca bu bayrakla gonderdigi icin rakip tasi tahtadan siliniyor ve bara
    /// girmesi gereken tas hic olusmuyordu.
    /// </para>
    /// <para>
    /// <b>Hata 4:</b> oyun bittiginde sonuc skora islenmiyordu; skor etiketi degismiyordu.
    /// </para>
    /// <para>
    /// <b>Hata 6:</b> "Kup" dugmesi yalnizca <see cref="GamePhase.PreRoll"/> fazinda calisiyordu;
    /// oyuncu zar attiktan sonra teklif sessizce yutuluyordu.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFixTests
    {
        private static GameOrchestratorOptions Options(ulong seed)
        {
            return new GameOrchestratorOptions
            {
                Evaluator = new FakeEvaluator(),
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
        // Hata 1 + 2: vurma bayragi korunmali, tas bara gitmeli
        // ------------------------------------------------------------------

        [Test]
        public void MoveInputController_TryAddStep_PreservesHitFlag()
        {
            var state = UiTestSupport.InitialState();
            var white = new int[25];
            var black = new int[25];
            white[1] = 1;
            white[2] = 14;
            black[4] = 1;
            black[6] = 14;
            UiTestSupport.SetBoard(state, white, black);
            BackgammonEngine.SetDice(state, 3, 5);

            var controller = new MoveInputController();
            controller.Update(state);
            controller.SelectPoint(1);

            Assert.That(controller.LegalTargets, Does.Contain(4), "1 -> 4 (zar 3) yasal olmali");

            Assert.That(controller.TryAddStep(4), Is.True);
            Assert.That(controller.PartialMove.Count, Is.EqualTo(1));
            Assert.That(controller.PartialMove[0].IsHit, Is.True,
                "vurma adimi Hit bayragini tasimali");
            Assert.That(controller.PartialMove[0].Die, Is.EqualTo(3));
        }

        [Test]
        public void MoveInputController_HitStep_SendsOpponentToBar()
        {
            var state = UiTestSupport.InitialState();
            var white = new int[25];
            var black = new int[25];
            white[1] = 1;
            white[2] = 14;
            black[4] = 1;
            black[6] = 14;
            UiTestSupport.SetBoard(state, white, black);
            BackgammonEngine.SetDice(state, 3, 5);

            var controller = new MoveInputController();
            controller.Update(state);
            controller.SelectPoint(1);
            Assert.That(controller.TryAddStep(4), Is.True);

            BackgammonState after = state.Clone();
            MoveSequence partial = controller.PartialMove;
            BackgammonEngine.ApplyMove(after, in partial);

            Assert.Multiple(() =>
            {
                Assert.That(after.board[4], Is.EqualTo(1), "vuran tas hedefte kalmali");
                Assert.That(after.board[25], Is.EqualTo(-1), "kirilan tas Siyah barina gitmeli");
                Assert.That(TotalCheckers(after), Is.EqualTo(30), "tas sayisi korunmali");
            });
        }

        [Test]
        public void MoveInputController_TryAddStep_PreservesBearOffFlag()
        {
            var state = UiTestSupport.InitialState();
            var white = new int[25];
            var black = new int[25];
            white[24] = 15;
            black[1] = 15;
            UiTestSupport.SetBoard(state, white, black);
            BackgammonEngine.SetDice(state, 1, 1);

            var controller = new MoveInputController();
            controller.Update(state);
            controller.SelectPoint(24);

            Assert.That(controller.LegalTargets, Does.Contain(25), "24 -> 25 toplama yasal olmali");
            Assert.That(controller.TryAddStep(25), Is.True);
            Assert.That(controller.PartialMove[0].IsBearOff, Is.True,
                "toplama adimi BearOff bayragini tasimali");

            BackgammonState after = state.Clone();
            MoveSequence partial = controller.PartialMove;
            BackgammonEngine.ApplyMove(after, in partial);

            Assert.Multiple(() =>
            {
                Assert.That(after.whiteBorneOff, Is.EqualTo(1), "toplanan tas sayaci artmali");
                Assert.That(after.board[24], Is.EqualTo(14));
                Assert.That(TotalCheckers(after), Is.EqualTo(30));
            });
        }

        // ------------------------------------------------------------------
        // Hata 4: oyun sonucu skora hemen islenmeli
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_AppliesScoreImmediatelyAtGameEnd()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0041UL)))
            {
                // 1 sayilik macta kup "olu"dur (CanOfferAtTurnStart false) ve faz PreRoll'a
                // hic gelmez; bu yuzden 2 sayilik mac kullanilir.
                orchestrator.NewMatch(2, false);
                AdvanceToPreRoll(orchestrator);

                Assert.That(orchestrator.TryOfferDouble(), Is.True, "kup teklif edilebilmeli");
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.CubeOffered));

                orchestrator.Pass();

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.IsGameOver, Is.True);
                    Assert.That(orchestrator.State.whiteScore + orchestrator.State.blackScore,
                                Is.EqualTo(1), "sonuc skora hemen islenmeli");
                });
            }
        }

        [Test]
        public void GameOrchestrator_StartNextGame_DoesNotDoubleCountScore()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0042UL)))
            {
                orchestrator.NewMatch(5, false);
                AdvanceToPreRoll(orchestrator);
                Assert.That(orchestrator.TryOfferDouble(), Is.True);
                orchestrator.Pass();

                int afterPass = orchestrator.State.whiteScore + orchestrator.State.blackScore;
                Assert.That(afterPass, Is.EqualTo(1));

                orchestrator.StartNextGame();

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.IsGameOver, Is.False, "mac bitmedi, yeni oyun kurulmali");
                    Assert.That(orchestrator.State.whiteScore + orchestrator.State.blackScore,
                                Is.EqualTo(afterPass), "skor iki kez sayilmamali");
                });
            }
        }

        // ------------------------------------------------------------------
        // Hata 6: zar atildiktan sonra da kup teklif edilebilmeli
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_TryOfferDouble_RevertsUnplayedRoll()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0043UL)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);

                orchestrator.RollDice();
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving),
                            "zar atildi, faz Moving olmali");
                Assert.That(orchestrator.State.remainingCount, Is.GreaterThan(0));

                Assert.That(orchestrator.TryOfferDouble(), Is.True,
                            "oynanmamis zar geri alinip teklif edilebilmeli");
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.CubeOffered));
                Assert.That(orchestrator.State.remainingCount, Is.EqualTo(0),
                            "teklif icin zar geri alinmis olmali");
            }
        }

        [Test]
        public void GameOrchestrator_TryOfferDouble_RejectsAfterCheckerPlayed()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0044UL)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);
                orchestrator.RollDice();

                MoveList moves = orchestrator.LegalMoves;
                Assert.That(moves.Count, Is.GreaterThan(0));
                orchestrator.ApplyMove(moves[0]);

                if (orchestrator.State.phase != GamePhase.Moving)
                {
                    Assert.Pass("Tur kapandi; teklif penceresi zaten gecmis.");
                }

                Assert.That(orchestrator.TryOfferDouble(), Is.False,
                            "tas oynandiktan sonra teklif edilememeli");
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving));
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        private static int TotalCheckers(BackgammonState s)
        {
            int total = s.whiteBorneOff + s.blackBorneOff;
            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                total += Math.Abs((int)s.board[p]);
            }

            return total;
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
    }
}
