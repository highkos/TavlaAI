using System;
using System.Collections.Generic;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Vurma sonrasi tas sayisi regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <b>Hata:</b> Siyah 6-4 atip 8 ve 6'dan 2'ye gelerek Beyaz'in 2'deki tek tasini vurdugunda
    /// Siyah 14 tasla kaliyordu; 2'de tek Siyah tas gorunuyor ve bar bos kaliyordu.
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix9Tests
    {
        /// <summary>
        /// Siyah: 24x5, 20x3, 13x5, 8x1, 6x1. Beyaz: 19x2, 17x5, 12x5, 2x1, 1x2.
        /// </summary>
        private static BackgammonState HitTwicePosition()
        {
            var white = new int[25];
            var black = new int[25];

            black[24] = 5;
            black[20] = 3;
            black[13] = 5;
            black[8] = 1;
            black[6] = 1;

            white[19] = 2;
            white[17] = 5;
            white[12] = 5;
            white[2] = 1;
            white[1] = 2;

            var state = new BackgammonState();
            state.Reset();
            UiTestSupport.SetBoard(state, white, black);
            state.turn = -1;
            state.phase = GamePhase.Moving;
            state.rolledDice[0] = 6;
            state.rolledDice[1] = 4;
            state.remainingDice[0] = 6;
            state.remainingDice[1] = 4;
            state.remainingCount = 2;
            state.hash = BackgammonEngine.ComputeZobristHash(state);
            return state;
        }

        private static int Count(BackgammonState s, int player)
        {
            int total = 0;
            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                int v = s.board[p];
                if (player > 0 ? v > 0 : v < 0)
                {
                    total += Math.Abs(v);
                }
            }

            total += player > 0 ? s.whiteBorneOff : s.blackBorneOff;
            return total;
        }

        [Test]
        public void Position_IsValid()
        {
            BackgammonState s = HitTwicePosition();
            Assert.That(Count(s, -1), Is.EqualTo(15), "siyah 15 tas");
            Assert.That(Count(s, 1), Is.EqualTo(15), "beyaz 15 tas");
            Assert.That(s.board[2], Is.EqualTo(1), "2'de tek beyaz (blot)");
        }

        [Test]
        public void Engine_ApplyMove_HitThenStack_KeepsFifteenEach()
        {
            BackgammonState s = HitTwicePosition();
            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(s, moves);

            MoveSequence target = default(MoveSequence);
            bool found = false;
            for (int i = 0; i < moves.Count; i++)
            {
                MoveSequence seq = moves.Moves[i];
                if (seq.Count != 2)
                {
                    continue;
                }

                bool a = seq[0].From == 8 && seq[0].To == 2;
                bool b = seq[1].From == 6 && seq[1].To == 2;
                bool c = seq[0].From == 6 && seq[0].To == 2;
                bool d = seq[1].From == 8 && seq[1].To == 2;
                if ((a && b) || (c && d))
                {
                    target = seq;
                    found = true;
                    break;
                }
            }

            Assert.That(found, Is.True, "8->2 ve 6->2 dizisi uretilmeli");

            BackgammonEngine.ApplyMove(s, target);

            Assert.That(Count(s, -1), Is.EqualTo(15), "siyah 15 tas kalmali");
            Assert.That(Count(s, 1), Is.EqualTo(15), "beyaz 15 tas kalmali");
            Assert.That(s.board[2], Is.EqualTo(-2), "2'de iki siyah tas olmali");
            Assert.That(s.board[0], Is.EqualTo(1), "beyaz bara gitmeli");
            Assert.That(s.board[8], Is.EqualTo(0), "8 bos olmali");
            Assert.That(s.board[6], Is.EqualTo(0), "6 bos olmali");
        }

        [Test]
        public void InputController_HitThenStack_KeepsFifteenEach()
        {
            BackgammonState s = HitTwicePosition();
            var input = new MoveInputController();
            input.Update(s);

            input.SelectPoint(8);
            Assert.That(input.LegalTargets, Does.Contain(2), "8'den 2'ye gidilebilmeli");
            Assert.That(input.TryAddStep(2), Is.True, "8->2 eklenmeli");

            input.SelectPoint(6);
            Assert.That(input.LegalTargets, Does.Contain(2), "6'dan 2'ye gidilebilmeli");
            Assert.That(input.TryAddStep(2), Is.True, "6->2 eklenmeli");

            MoveSequence move = input.PartialMove;
            Assert.That(move.Count, Is.EqualTo(2));

            BackgammonEngine.ApplyMove(s, move);

            Assert.That(Count(s, -1), Is.EqualTo(15), "siyah 15 tas kalmali");
            Assert.That(Count(s, 1), Is.EqualTo(15), "beyaz 15 tas kalmali");
            Assert.That(s.board[2], Is.EqualTo(-2), "2'de iki siyah tas olmali");
            Assert.That(s.board[0], Is.EqualTo(1), "beyaz bara gitmeli");
        }

        [Test]
        public void InputController_ReverseOrder_KeepsFifteenEach()
        {
            BackgammonState s = HitTwicePosition();
            var input = new MoveInputController();
            input.Update(s);

            input.SelectPoint(6);
            Assert.That(input.TryAddStep(2), Is.True, "6->2 eklenmeli");

            input.SelectPoint(8);
            Assert.That(input.TryAddStep(2), Is.True, "8->2 eklenmeli");

            MoveSequence move = input.PartialMove;
            BackgammonEngine.ApplyMove(s, move);

            Assert.That(Count(s, -1), Is.EqualTo(15), "siyah 15 tas kalmali");
            Assert.That(Count(s, 1), Is.EqualTo(15), "beyaz 15 tas kalmali");
            Assert.That(s.board[2], Is.EqualTo(-2));
            Assert.That(s.board[0], Is.EqualTo(1));
        }

        /// <summary>
        /// Her yasal hamleden sonra iki taraf da tam 15 tas tasimalidir.
        /// </summary>
        [Test]
        public void EveryLegalMove_ConservesCheckers()
        {
            List<BackgammonState> positions = UiTestSupport.RandomMovingPositions(40, 0x9F17_0001UL);
            var moves = new MoveList();

            for (int i = 0; i < positions.Count; i++)
            {
                BackgammonState baseState = positions[i];
                LegalMoveGenerator.GenerateAllLegalMoves(baseState, moves);

                for (int m = 0; m < moves.Count; m++)
                {
                    BackgammonState probe = baseState.Clone();
                    BackgammonEngine.ApplyMove(probe, moves.Moves[m]);

                    Assert.That(Count(probe, 1), Is.EqualTo(15),
                                "beyaz tas sayisi korunmali (pozisyon " + i + ", hamle " + m + ")");
                    Assert.That(Count(probe, -1), Is.EqualTo(15),
                                "siyah tas sayisi korunmali (pozisyon " + i + ", hamle " + m + ")");
                }
            }
        }

        /// <summary>
        /// <see cref="MoveInputController"/> uzerinden kurulan <b>her</b> kismi hamle motor
        /// tarafindan kabul edilmeli ve tas sayisini korumalidir.
        /// </summary>
        /// <remarks>
        /// Bu test, "bayat vurus bayragi" sinifindaki tum hatalari yakalar: projeksiyon
        /// ureticinin baska bir ara durumdan urettigi adimi kopyalarsa tas sayisi bozulur.
        /// </remarks>
        [Test]
        public void InputController_EveryProjectedStep_ConservesCheckers()
        {
            List<BackgammonState> positions = UiTestSupport.RandomMovingPositions(8, 0x9F17_0002UL);
            var input = new MoveInputController();

            for (int i = 0; i < positions.Count; i++)
            {
                BackgammonState baseState = positions[i];

                for (int from = 0; from <= 25; from++)
                {
                    input.Reset();
                    input.Update(baseState);
                    input.SelectPoint(from);

                    var targets = new List<int>(input.LegalTargets);
                    for (int t = 0; t < targets.Count; t++)
                    {
                        input.Reset();
                        input.Update(baseState);
                        input.SelectPoint(from);
                        if (!input.TryAddStep(targets[t]))
                        {
                            continue;
                        }

                        BackgammonState probe = baseState.Clone();
                        MoveSequence move = input.PartialMove;
                        Assert.DoesNotThrow(
                            () => BackgammonEngine.ApplyMove(probe, in move),
                            "projeksiyon motor tarafindan kabul edilmeli (pozisyon " + i
                            + ", " + from + "->" + targets[t] + ")");
                        Assert.That(Count(probe, 1), Is.EqualTo(15),
                                    "beyaz tas sayisi korunmali (pozisyon " + i
                                    + ", " + from + "->" + targets[t] + ")");
                        Assert.That(Count(probe, -1), Is.EqualTo(15),
                                    "siyah tas sayisi korunmali (pozisyon " + i
                                    + ", " + from + "->" + targets[t] + ")");
                    }
                }
            }
        }
    }
}
