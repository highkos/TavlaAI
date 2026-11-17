using System;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Besinci tur oynanis hatalarinin motor/orkestrator regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Hata 1:</b> Siyah oynarken toplama bolgesine yakin bir Beyaz tas vuruldugunda Siyah
    /// tas sayisi <c>14</c>'e dusuyordu. Tas sayisi <b>her</b> hamleden sonra <c>15 + 15</c>
    /// kalmali; bar sayaclari isaret olarak tutarli olmali (<c>board[0] &gt;= 0</c>,
    /// <c>board[25] &lt;= 0</c>).
    /// </para>
    /// <para>
    /// <b>Neden rastgele oyun (fuzz):</b> hata yalnizca belirli bir hamle dizisinde ortaya
    /// cikiyorsa elle kurulmus tek bir pozisyon onu yakalamaz. Bu test orkestrator uzerinden
    /// (UI'in kullandigi yol) binlerce hamle oynar ve her hamleden sonra tas sayimini dogrular.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix5Tests
    {
        // ------------------------------------------------------------------
        // Hata 1: rastgele oyunlarda tas sayisi korunmali
        // ------------------------------------------------------------------

        [Test]
        public void Orchestrator_RandomGames_NeverLoseCheckers()
        {
            var rng = new Xoshiro256StarStar(0x5A17_0001UL);

            using (var orchestrator = new GameOrchestrator(Options(0x5A17_0002UL)))
            {
                orchestrator.NewMatch(0, false);

                int moves = 0;
                for (int game = 0; game < 25; game++)
                {
                    int guard = 0;
                    while (!orchestrator.IsGameOver && guard++ < 5000)
                    {
                        BackgammonState state = orchestrator.State;

                        if (state.phase == GamePhase.DetermineFirstPlayer ||
                            state.phase == GamePhase.PreRoll ||
                            state.phase == GamePhase.WaitForRoll)
                        {
                            orchestrator.RollDice();
                            continue;
                        }

                        if (state.phase != GamePhase.Moving)
                        {
                            break;
                        }

                        if (orchestrator.LegalMoves.Count == 0)
                        {
                            orchestrator.EndTurn();
                            continue;
                        }

                        int pick = (int)(rng.NextUInt() % (uint)orchestrator.LegalMoves.Count);
                        orchestrator.ApplyMove(orchestrator.LegalMoves[pick]);
                        moves++;

                        AssertCounts(orchestrator.State, moves);

                        // UI her karede AnalyzeCurrent() cagirir; arama durumu bozmamali.
                        orchestrator.AnalyzeCurrent();
                        AssertCounts(orchestrator.State, moves);
                    }

                    Assert.That(orchestrator.IsGameOver, Is.True,
                                "oyun " + game + " makul hamle sayisinda bitmeli (faz=" +
                                orchestrator.State.phase + " sira=" + orchestrator.State.turn +
                                " kalanZar=" + orchestrator.State.remainingCount +
                                " beyazOff=" + orchestrator.State.whiteBorneOff +
                                " siyahOff=" + orchestrator.State.blackBorneOff +
                                " yasal=" + orchestrator.LegalMoves.Count + ")");
                    orchestrator.NewMatch(0, false);
                }

                Assert.That(moves, Is.GreaterThan(1000), "fuzz yeterli hamle oynamali");
            }
        }

        // ------------------------------------------------------------------
        // Hata 1 (hedefli): ev bolgesinde vurma, her iki renk
        // ------------------------------------------------------------------

        [TestCase((sbyte)-1)]
        [TestCase((sbyte)1)]
        public void Orchestrator_HitNearBearOff_KeepsFifteenCheckers(sbyte turn)
        {
            using (var orchestrator = new GameOrchestrator(Options(0x5A17_0003UL)))
            {
                orchestrator.NewMatch(0, false);

                BackgammonState state = orchestrator.State;
                ClearBoard(state);

                // Vuran taraf ev bolgesinde (toplama bolgesine yakin), rakip blot orada.
                int from = turn > 0 ? 19 : 6;
                int blot = turn > 0 ? 21 : 4;
                int stack = turn > 0 ? 24 : 1;
                int oppStack = turn > 0 ? 1 : 24;

                state.board[from] = turn;
                state.board[stack] = (sbyte)(turn * 14);
                state.board[blot] = (sbyte)-turn;
                state.board[oppStack] = (sbyte)(-turn * 14);
                state.turn = turn;
                state.phase = GamePhase.WaitForRoll;
                state.hash = BackgammonEngine.ComputeZobristHash(state);

                orchestrator.SetDice(2, 2);
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving));

                var move = new MoveSequence();
                move.Add(new MoveStep((byte)from, (byte)blot, 2, MoveFlags.Hit));
                orchestrator.ApplyMove(move);

                AssertCounts(orchestrator.State, 1);
                Assert.That(orchestrator.State.board[blot], Is.EqualTo(turn), "vuran tas hedefte kalmali");
                Assert.That(orchestrator.State.board[BackgammonEngine.BarIndex((sbyte)-turn)],
                            Is.EqualTo((sbyte)-turn), "vurulan tas rakip barina gitmeli");
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        private static void AssertCounts(BackgammonState state, int moveIndex)
        {
            string where = "hamle #" + moveIndex;

            Assert.That(state.CountPieces(1), Is.EqualTo(15), "Beyaz tas sayisi korunmali (" + where + ")");
            Assert.That(state.CountPieces(-1), Is.EqualTo(15), "Siyah tas sayisi korunmali (" + where + ")");

            // Bar sayaclari isaret olarak tutarli olmali: Beyaz bar >= 0, Siyah bar <= 0.
            Assert.That(state.board[0], Is.GreaterThanOrEqualTo((sbyte)0),
                        "Beyaz bar negatif olamaz (" + where + ")");
            Assert.That(state.board[25], Is.LessThanOrEqualTo((sbyte)0),
                        "Siyah bar pozitif olamaz (" + where + ")");

            int onBoard = 0;
            for (int p = 1; p <= 24; p++)
            {
                onBoard += Math.Abs((int)state.board[p]);
            }

            Assert.That(onBoard + state.board[0] + (-state.board[25]) +
                        state.whiteBorneOff + state.blackBorneOff,
                        Is.EqualTo(30), "toplam tas sayisi 30 kalmali (" + where + ")");
        }

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
