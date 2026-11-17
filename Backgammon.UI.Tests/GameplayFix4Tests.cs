using System;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Dorduncu tur oynanis hatalarinin motor/yerlesim regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Hata 1:</b> Ev bolgesinde (toplama bolgesi) vurulan tas <b>silinmemeli</b>; rakip barina
    /// gitmeli ve toplam tas sayisi <c>15 + 15</c> kalmali. Bu test her iki renk icin de calisir.
    /// </para>
    /// <para>
    /// <b>Hata 2:</b> Oyun bittikten sonra <see cref="BackgammonEngine.EndTurn"/> sirayi
    /// <b>cevirmemeli</b>; aksi halde yapay zeka kazanilmis oyunda hamle yapar.
    /// </para>
    /// <para>
    /// <b>Hata 3:</b> Insan hangi rengi secerse secsin kendi toplama tepsisi <b>sag altta</b>
    /// olmali; hane dikdortgenleri renkten <b>bagimsiz</b> kalmali.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix4Tests
    {
        // ------------------------------------------------------------------
        // Hata 1: vurulan tas silinmemeli
        // ------------------------------------------------------------------

        [TestCase((sbyte)1)]
        [TestCase((sbyte)-1)]
        public void BackgammonEngine_HitInBearOffArea_MovesCheckerToOpponentBar(sbyte turn)
        {
            BackgammonState state = new BackgammonState();
            state.Reset();
            ClearBoard(state);

            int from = turn > 0 ? 19 : 6;
            int blot = turn > 0 ? 21 : 4;
            int stack = turn > 0 ? 12 : 13;
            int oppStack = turn > 0 ? 24 : 1;

            state.board[from] = turn;
            state.board[stack] = (sbyte)(turn * 14);
            state.board[blot] = (sbyte)-turn;
            state.board[oppStack] = (sbyte)(-turn * 14);
            state.turn = turn;
            state.phase = GamePhase.WaitForRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            BackgammonEngine.SetDice(state, 2, 2);

            var move = new MoveSequence();
            move.Add(new MoveStep((byte)from, (byte)blot, 2, MoveFlags.Hit));
            BackgammonEngine.ApplyMove(state, move);

            Assert.That(state.board[blot], Is.EqualTo(turn), "vuran tas hedefte kalmali");
            Assert.That(state.board[BackgammonEngine.BarIndex((sbyte)-turn)], Is.EqualTo((sbyte)-turn),
                        "vurulan tas rakip barina gitmeli");
            Assert.That(state.CountPieces(1), Is.EqualTo(15), "Beyaz tas sayisi korunmali");
            Assert.That(state.CountPieces(-1), Is.EqualTo(15), "Siyah tas sayisi korunmali");
            Assert.That(state.whiteBorneOff, Is.EqualTo(0), "vurma toplama sayacini degistirmemeli");
            Assert.That(state.blackBorneOff, Is.EqualTo(0), "vurma toplama sayacini degistirmemeli");
        }

        [TestCase((sbyte)1)]
        [TestCase((sbyte)-1)]
        public void LegalMoveGenerator_HitInBearOffArea_IsGenerated(sbyte turn)
        {
            BackgammonState state = new BackgammonState();
            state.Reset();
            ClearBoard(state);

            int from = turn > 0 ? 19 : 6;
            int blot = turn > 0 ? 21 : 4;
            int stack = turn > 0 ? 12 : 13;
            int oppStack = turn > 0 ? 24 : 1;

            state.board[from] = turn;
            state.board[stack] = (sbyte)(turn * 14);
            state.board[blot] = (sbyte)-turn;
            state.board[oppStack] = (sbyte)(-turn * 14);
            state.turn = turn;
            state.phase = GamePhase.WaitForRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            BackgammonEngine.SetDice(state, 2, 2);

            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(state, moves);

            bool found = false;
            for (int i = 0; i < moves.Count; i++)
            {
                MoveSequence sequence = moves[i];
                for (int j = 0; j < sequence.Count; j++)
                {
                    MoveStep step = sequence[j];
                    if (step.From == from && step.To == blot && step.IsHit)
                    {
                        found = true;
                    }
                }
            }

            Assert.That(found, Is.True, "ev bolgesindeki blot'u vuran hamle uretilmeli");
        }

        // ------------------------------------------------------------------
        // Hata 2: oyun bittikten sonra sira cevrilmemeli
        // ------------------------------------------------------------------

        [Test]
        public void BackgammonEngine_EndTurn_AfterGameOver_DoesNotFlipTurn()
        {
            BackgammonState state = new BackgammonState();
            state.Reset();
            ClearBoard(state);

            state.board[1] = -1;
            state.board[24] = 15;
            state.blackBorneOff = 14;
            state.turn = -1;
            state.phase = GamePhase.WaitForRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            BackgammonEngine.SetDice(state, 1, 1);

            var move = new MoveSequence();
            move.Add(new MoveStep(1, 0, 1, MoveFlags.BearOff));
            BackgammonEngine.ApplyMove(state, move);

            Assert.That(state.phase, Is.EqualTo(GamePhase.GameOver), "faz GameOver olmali");
            Assert.That(state.blackBorneOff, Is.EqualTo(15));

            BackgammonEngine.EndTurn(state);

            Assert.That(state.turn, Is.EqualTo((sbyte)-1), "oyun bittikten sonra sira degismemeli");
            Assert.That(state.phase, Is.EqualTo(GamePhase.GameOver), "faz GameOver kalmali");
        }

        [Test]
        public void GameOrchestrator_AfterHumanWin_ScoreAppliedOnce_AndNoFurtherMoves()
        {
            var orchestrator = new GameOrchestrator(Options(0x4F14UL));
            orchestrator.NewMatch(0, false);

            BackgammonState state = orchestrator.State;
            ClearBoard(state);
            state.board[1] = -1;
            state.board[24] = 15;
            state.blackBorneOff = 14;
            state.turn = -1;
            state.phase = GamePhase.WaitForRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            orchestrator.SetDice(1, 1);

            var move = new MoveSequence();
            move.Add(new MoveStep(1, 0, 1, MoveFlags.BearOff));
            orchestrator.ApplyMove(move);

            Assert.That(orchestrator.IsGameOver, Is.True, "oyun bitmis olmali");
            Assert.That(orchestrator.State.blackScore, Is.GreaterThan(0), "skor guncellenmeli");

            int score = orchestrator.State.blackScore;
            sbyte turn = orchestrator.State.turn;

            // Oyun bittikten sonra gelen cagrilar durumu degistirmemeli.
            orchestrator.EndTurn();
            orchestrator.RollDice();

            Assert.That(orchestrator.State.blackScore, Is.EqualTo(score), "skor cift sayilmamali");
            Assert.That(orchestrator.State.turn, Is.EqualTo(turn), "sira degismemeli");
            Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.GameOver), "faz GameOver kalmali");
        }

        // ------------------------------------------------------------------
        // Hata 3: toplama tepsisi her renkte sag altta
        // ------------------------------------------------------------------

        [Test]
        public void BoardLayout_HumanTray_IsAlwaysBottomRight()
        {
            const float width = 1920f;
            const float height = 1080f;

            BoardLayout blackBottom = BoardLayout.Calculate(width, height, true);
            BoardLayout whiteBottom = BoardLayout.Calculate(width, height, false);

            // Siyah alt yarida: Siyah tepsisi alt, Beyaz tepsisi ust.
            Assert.That(blackBottom.BlackTray.Y, Is.GreaterThan(blackBottom.WhiteTray.Y),
                        "Siyah oynarken Siyah tepsisi alt yarida olmali");
            Assert.That(whiteBottom.WhiteTray.Y, Is.GreaterThan(whiteBottom.BlackTray.Y),
                        "Beyaz oynarken Beyaz tepsisi alt yarida olmali");

            // Tepsiler her zaman sag tarafta.
            Assert.That(blackBottom.BlackTray.X, Is.GreaterThan(blackBottom.Bar.X));
            Assert.That(whiteBottom.WhiteTray.X, Is.GreaterThan(whiteBottom.Bar.X));
            Assert.That(blackBottom.BlackTray.X + blackBottom.BlackTray.Width,
                        Is.EqualTo(width).Within(0.01f), "tepsi sag kenara dayanmali");
        }

        [Test]
        public void BoardLayout_PointRects_AreIndependentOfPlayerColor()
        {
            BoardLayout blackBottom = BoardLayout.Calculate(1920f, 1080f, true);
            BoardLayout whiteBottom = BoardLayout.Calculate(1920f, 1080f, false);

            for (int point = 1; point <= BoardLayout.PointCount; point++)
            {
                LayoutRect a = blackBottom.PointAt(point);
                LayoutRect b = whiteBottom.PointAt(point);
                string label = "hane " + point;

                Assert.That(a.X, Is.EqualTo(b.X).Within(0.0001f), label + " X degismemeli");
                Assert.That(a.Y, Is.EqualTo(b.Y).Within(0.0001f), label + " Y degismemeli");
                Assert.That(a.Width, Is.EqualTo(b.Width).Within(0.0001f), label + " genisligi degismemeli");
                Assert.That(a.Height, Is.EqualTo(b.Height).Within(0.0001f), label + " yuksekligi degismemeli");
            }
        }

        [Test]
        public void BoardLayout_Point1_IsBottomRight_Point24_IsTopRight()
        {
            BoardLayout layout = BoardLayout.Calculate(1920f, 1080f, true);

            LayoutRect point1 = layout.PointAt(1);
            LayoutRect point24 = layout.PointAt(24);

            Assert.That(point1.Y, Is.GreaterThan(point24.Y), "hane 1 alt satirda olmali");
            Assert.That(point1.Right, Is.EqualTo(layout.Tray.X).Within(0.01f),
                        "hane 1 oyun alaninin sag kenarinda olmali");
            Assert.That(point24.Right, Is.EqualTo(layout.Tray.X).Within(0.01f),
                        "hane 24 oyun alaninin sag kenarinda olmali");

            for (int point = 2; point <= 12; point++)
            {
                Assert.That(layout.PointAt(point).X, Is.LessThan(point1.X),
                            "hane 1 alt satirin en sagi olmali");
            }

            for (int point = 13; point <= 23; point++)
            {
                Assert.That(layout.PointAt(point).X, Is.LessThan(point24.X),
                            "hane 24 ust satirin en sagi olmali");
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        private static void ClearBoard(BackgammonState state)
        {
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                state.board[i] = 0;
            }

            state.whiteBorneOff = 0;
            state.blackBorneOff = 0;
        }

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
    }
}
