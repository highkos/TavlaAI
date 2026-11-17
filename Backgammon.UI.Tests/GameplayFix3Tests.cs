using System;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Ucuncu tur oynanis hatalarinin regresyon testleri (sira kurallari motor seviyesinde).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Hata 6 (yeniden zar):</b> <see cref="GameOrchestrator.RollDice"/> faz denetimi
    /// yapmiyordu; oyuncu <see cref="GamePhase.Moving"/> fazinda "Zar"a basarak istedigi kadar
    /// yeni zar atabiliyordu. Kural artik <see cref="BackgammonEngine.CanRoll"/> icinde tanimli.
    /// </para>
    /// <para>
    /// <b>Hata 3 (kismi zar):</b> <see cref="LegalMoveGenerator"/> yalnizca <b>maksimum
    /// uzunluktaki</b> dizileri uretir. 5-5 atilip yalnizca iki hamle oynanabiliyorsa
    /// <c>remainingCount</c> hicbir zaman sifira inmiyor ve sira kapanmiyordu. Kural artik
    /// <see cref="BackgammonEngine.ShouldEndTurn"/> icinde tanimli.
    /// </para>
    /// <para>
    /// <b>Hata 5 (toplama bitisi):</b> son tas zarlardan biri artarken toplandiginda oyun
    /// bitmiyordu; ayni <see cref="BackgammonEngine.ShouldEndTurn"/> kurali bu durumu da kapatir.
    /// </para>
    /// <para>
    /// <b>Hata 4 (bar onceligi):</b> barda tas varken baska tas oynanamaz; kural
    /// <see cref="LegalMoveGenerator"/> icinde zaten vardi, burada UI'in gordugu projeksiyon
    /// (<see cref="MoveInputController.LegalTargetsFrom"/>) dogrulanir.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix3Tests
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
        // Hata 6: oynanmamis zar varken yeniden zar atilamaz
        // ------------------------------------------------------------------

        [Test]
        public void BackgammonEngine_CanRoll_OnlyAtTurnStart()
        {
            BackgammonState state = UiTestSupport.InitialState();

            Assert.That(BackgammonEngine.CanRoll(state), Is.True,
                        "acilis fazinda zar atilir");

            state.phase = GamePhase.PreRoll;
            Assert.That(BackgammonEngine.CanRoll(state), Is.True, "kup oncesi zar atilir");

            state.phase = GamePhase.WaitForRoll;
            Assert.That(BackgammonEngine.CanRoll(state), Is.True, "sira basinda zar atilir");

            state.phase = GamePhase.Moving;
            Assert.That(BackgammonEngine.CanRoll(state), Is.False,
                        "oynanmamis zar varken yeniden zar atilamaz");

            state.phase = GamePhase.CubeOffered;
            Assert.That(BackgammonEngine.CanRoll(state), Is.False, "kup teklifinde zar atilmaz");

            state.phase = GamePhase.GameOver;
            Assert.That(BackgammonEngine.CanRoll(state), Is.False, "oyun bittiyse zar atilmaz");
        }

        [Test]
        public void GameOrchestrator_RollDice_WhileMoving_IsIgnored()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0061UL)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);
                orchestrator.SetDice(3, 5);

                byte d1 = orchestrator.State.rolledDice[0];
                byte d2 = orchestrator.State.rolledDice[1];
                int remaining = orchestrator.State.remainingCount;

                Assert.That(orchestrator.CanRoll, Is.False, "oynanmamis zar varken atilamaz");

                for (int i = 0; i < 25; i++)
                {
                    orchestrator.RollDice();
                }

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.rolledDice[0], Is.EqualTo(d1),
                                "oynanmamis zar degismemeli");
                    Assert.That(orchestrator.State.rolledDice[1], Is.EqualTo(d2),
                                "oynanmamis zar degismemeli");
                    Assert.That(orchestrator.State.remainingCount, Is.EqualTo(remaining));
                    Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving));
                });
            }
        }

        [Test]
        public void GameOrchestrator_SetDice_WhileMoving_IsIgnored()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0062UL)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);
                orchestrator.SetDice(3, 5);

                orchestrator.SetDice(6, 6);

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.rolledDice[0], Is.EqualTo(3));
                    Assert.That(orchestrator.State.rolledDice[1], Is.EqualTo(5));
                    Assert.That(orchestrator.State.remainingCount, Is.EqualTo(2));
                });
            }
        }

        // ------------------------------------------------------------------
        // Hata 3: kalan zarlar oynanamiyorsa sira kapanir
        // ------------------------------------------------------------------

        [Test]
        public void BackgammonEngine_ShouldEndTurn_Rules()
        {
            BackgammonState state = UiTestSupport.InitialState();
            var moves = new MoveList();

            state.phase = GamePhase.Moving;
            state.remainingCount = 2;
            moves.Clear();
            Assert.That(BackgammonEngine.ShouldEndTurn(state, moves), Is.True,
                        "kalan zarlarla yasal hamle yoksa sira kapanir");

            state.remainingCount = 0;
            Assert.That(BackgammonEngine.ShouldEndTurn(state, moves), Is.True,
                        "kalan zar yoksa sira kapanir");

            state.phase = GamePhase.WaitForRoll;
            Assert.That(BackgammonEngine.ShouldEndTurn(state, moves), Is.False,
                        "Moving disinda sira kapanmaz");
        }

        [Test]
        public void GameOrchestrator_ApplyMove_PartialDice_EndsTurn()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0063UL)))
            {
                orchestrator.NewMatch(0, false);
                BackgammonState state = orchestrator.State;

                // Beyaz: 1'de 1, 2'de 1, 20'de 13 tas. Siyah 8..14'u kapatir.
                // 5-5 atildiginda yalnizca 1->6 ve 2->7 oynanabilir; kalan iki zar bloke.
                var white = new int[25];
                var black = new int[25];
                white[1] = 1;
                white[2] = 1;
                white[20] = 13;
                black[8] = 2;
                black[9] = 2;
                black[10] = 2;
                black[11] = 2;
                black[12] = 2;
                black[13] = 2;
                black[14] = 3;
                UiTestSupport.SetBoard(state, white, black);
                state.turn = 1;
                state.phase = GamePhase.WaitForRoll;

                orchestrator.SetDice(5, 5);

                Assert.That(orchestrator.State.remainingCount, Is.EqualTo(4));
                Assert.That(orchestrator.LegalMoves.Count, Is.GreaterThan(0));

                MoveSequence best = orchestrator.LegalMoves[0];
                Assert.That(best.Count, Is.EqualTo(2),
                            "5-5'te yalnizca iki hamle oynanabiliyor");

                orchestrator.ApplyMove(best);

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.turn, Is.EqualTo(-1),
                                "kalan zarlar oynanamiyorsa sira karsiya gecmeli");
                    Assert.That(orchestrator.State.phase, Is.Not.EqualTo(GamePhase.Moving),
                                "sira kapanmali");
                    Assert.That(orchestrator.State.remainingCount, Is.EqualTo(0));
                });
            }
        }

        [Test]
        public void MoveInputController_CanContinue_FalseWhenDiceBlocked()
        {
            BackgammonState state = UiTestSupport.InitialState();

            var white = new int[25];
            var black = new int[25];
            white[1] = 1;
            white[2] = 1;
            white[20] = 13;
            black[8] = 2;
            black[9] = 2;
            black[10] = 2;
            black[11] = 2;
            black[12] = 2;
            black[13] = 2;
            black[14] = 3;
            UiTestSupport.SetBoard(state, white, black);
            state.turn = 1;
            state.phase = GamePhase.WaitForRoll;
            BackgammonEngine.SetDice(state, 5, 5);

            var input = new MoveInputController();
            input.Update(state);

            input.SelectPoint(1);
            Assert.That(input.TryAddStep(6), Is.True, "1 -> 6 oynanabilmeli");
            Assert.That(input.CanContinue, Is.True, "ikinci zar hala oynanabilir");

            input.SelectPoint(2);
            Assert.That(input.TryAddStep(7), Is.True, "2 -> 7 oynanabilmeli");
            Assert.That(input.CanContinue, Is.False,
                        "kalan iki zar bloke: devam edilemez");
        }

        // ------------------------------------------------------------------
        // Hata 5: son tas toplandiginda oyun biter (zar artmis olsa da)
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_ApplyMove_LastCheckerBorneOff_EndsGame()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0064UL)))
            {
                orchestrator.NewMatch(5, false);
                BackgammonState state = orchestrator.State;

                var white = new int[25];
                var black = new int[25];
                white[24] = 1;
                black[1] = 15;
                UiTestSupport.SetBoard(state, white, black);
                state.whiteBorneOff = 14;
                state.turn = 1;
                state.phase = GamePhase.WaitForRoll;

                orchestrator.SetDice(6, 5);

                Assert.That(orchestrator.State.remainingCount, Is.EqualTo(2));
                Assert.That(orchestrator.LegalMoves.Count, Is.GreaterThan(0));

                MoveSequence best = orchestrator.LegalMoves[0];
                Assert.That(best.Count, Is.EqualTo(1), "tek tas var, tek hamle oynanir");

                orchestrator.ApplyMove(best);

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.whiteBorneOff, Is.EqualTo(15));
                    Assert.That(orchestrator.IsGameOver, Is.True,
                                "son tas toplandi: zar artmis olsa da oyun bitmeli");
                    Assert.That(orchestrator.Result.Winner, Is.EqualTo(1));
                    Assert.That(orchestrator.State.whiteScore, Is.GreaterThan(0),
                                "skor hemen islenmeli");
                });
            }
        }

        // ------------------------------------------------------------------
        // Hata 4: barda tas varken yalnizca bar girisi yasal
        // ------------------------------------------------------------------

        [Test]
        public void MoveInputController_BarPriority_FirstStepMustEnterFromBar()
        {
            BackgammonState state = UiTestSupport.InitialState();

            var white = new int[25];
            var black = new int[25];
            white[1] = 2;
            white[12] = 5;
            white[17] = 3;
            white[19] = 4;
            black[24] = 2;
            black[13] = 5;
            black[8] = 3;
            black[6] = 5;
            UiTestSupport.SetBoard(state, white, black);
            state.board[0] = 1;
            state.turn = 1;
            state.phase = GamePhase.WaitForRoll;
            BackgammonEngine.SetDice(state, 3, 5);

            // Uretici sozlesmesi: barda tas varken her yasal dizi bar girisimiyle baslar.
            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(state, moves);
            Assert.That(moves.Count, Is.GreaterThan(0), "bardan giris yasal olmali");
            for (int i = 0; i < moves.Count; i++)
            {
                Assert.That(moves.Moves[i][0].From, Is.EqualTo(0),
                            "barda tas varken ilk adim bar girisi olmali");
                Assert.That(moves.Moves[i][0].IsFromBar, Is.True);
            }

            var input = new MoveInputController();
            input.Update(state);

            Assert.That(input.LegalTargetsFrom(0), Is.Not.Empty,
                        "bardaki tas icin giris yasal olmali");
            Assert.That(input.LegalTargetsFrom(12), Is.Empty,
                        "barda tas varken ilk adim bardan olmali");
            Assert.That(input.LegalTargetsFrom(19), Is.Empty,
                        "barda tas varken ilk adim bardan olmali");

            // Kural atlatilamamali: 12'yi secip 15'e gitmek reddedilmeli.
            input.SelectPoint(12);
            Assert.That(input.LegalTargets, Is.Empty);
            Assert.That(input.TryAddStep(15), Is.False,
                        "barda tas varken 12 -> 15 oynanamaz");

            // Bardan giris kabul edilmeli.
            input.SelectPoint(0);
            Assert.That(input.TryAddStep(3), Is.True, "bardan 3'e giris yasal olmali");
            Assert.That(input.PartialMove[0].IsFromBar, Is.True,
                        "giris adimi FromBar bayragini tasimali");
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------


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
