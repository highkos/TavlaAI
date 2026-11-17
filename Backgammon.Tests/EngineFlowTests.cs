using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Aşama B: oyun akışı, Apply/Undo, hash tutarlılığı, oyun sonu.</summary>
    [TestFixture]
    public class EngineFlowTests
    {
        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private sealed class SequenceRandom : IRandom
        {
            private readonly int[] _values;
            private int _index;

            public SequenceRandom(params int[] values)
            {
                _values = values;
            }

            public uint NextUInt()
            {
                return (uint)RollDie();
            }

            public int RollDie()
            {
                if (_index >= _values.Length)
                {
                    throw new InvalidOperationException("SequenceRandom tükendi.");
                }

                return _values[_index++];
            }
        }

        private static void AssertHashConsistent(BackgammonState s)
        {
            Assert.That(s.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(s)), "Artımlı hash tam hash ile uyuşmuyor.");
        }

        /// <summary>Tahtayı sıfırlar ve verilen taşları yerleştirir; hash'i yeniden hesaplar.</summary>
        private static BackgammonState Custom(int turn, int whiteOff, int blackOff, params (int point, int value)[] pieces)
        {
            var s = new BackgammonState();
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            foreach (var (point, value) in pieces)
            {
                s.board[point] = (sbyte)value;
            }

            s.whiteBorneOff = (byte)whiteOff;
            s.blackBorneOff = (byte)blackOff;
            s.turn = (sbyte)turn;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        // ------------------------------------------------------------------
        // SetDice / RollDice / RollOpening
        // ------------------------------------------------------------------

        [Test]
        public void SetDice_NonDouble_SortsRemaining()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 5, 2);

            Assert.That(s.rolledDice[0], Is.EqualTo(5));
            Assert.That(s.rolledDice[1], Is.EqualTo(2));
            Assert.That(s.remainingCount, Is.EqualTo(2));
            Assert.That(s.remainingDice[0], Is.EqualTo(2));
            Assert.That(s.remainingDice[1], Is.EqualTo(5));
            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
        }

        [Test]
        public void SetDice_Double_FillsFourSlots()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 4, 4);

            Assert.That(s.remainingCount, Is.EqualTo(4));
            for (int i = 0; i < 4; i++)
            {
                Assert.That(s.remainingDice[i], Is.EqualTo(4));
            }
        }

        [Test]
        public void SetDice_OutOfRange_Throws()
        {
            var s = new BackgammonState();
            Assert.Throws<ArgumentException>(() => BackgammonEngine.SetDice(s, 0, 3));
            Assert.Throws<ArgumentException>(() => BackgammonEngine.SetDice(s, 3, 7));
        }

        [Test]
        public void RollDice_UsesRandom()
        {
            var s = new BackgammonState();
            BackgammonEngine.RollDice(s, new SequenceRandom(6, 1));

            Assert.That(s.rolledDice[0], Is.EqualTo(6));
            Assert.That(s.rolledDice[1], Is.EqualTo(1));
            Assert.That(s.remainingCount, Is.EqualTo(2));
        }

        [Test]
        public void RollOpening_RerollsOnTie_AndHigherDieStarts()
        {
            var s = new BackgammonState();
            BackgammonEngine.RollOpening(s, new SequenceRandom(3, 3, 5, 2));

            Assert.That(s.turn, Is.EqualTo(1));
            Assert.That(s.rolledDice[0], Is.EqualTo(5));
            Assert.That(s.rolledDice[1], Is.EqualTo(2));
            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
            AssertHashConsistent(s);
        }

        [Test]
        public void RollOpening_BlackCanStart()
        {
            var s = new BackgammonState();
            BackgammonEngine.RollOpening(s, new SequenceRandom(2, 6));

            Assert.That(s.turn, Is.EqualTo(-1));
            AssertHashConsistent(s);
        }

        // ------------------------------------------------------------------
        // ApplyStep / UndoStep
        // ------------------------------------------------------------------

        [Test]
        public void ApplyStep_SimpleMove_UpdatesBoardAndHash()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            var step = new MoveStep(1, 4, 3, 0);
            BackgammonEngine.ApplyStep(s, step);

            Assert.That(s.board[1], Is.EqualTo(1));
            Assert.That(s.board[4], Is.EqualTo(1));
            Assert.That(s.remainingCount, Is.EqualTo(1));
            Assert.That(s.remainingDice[0], Is.EqualTo(5));
            AssertHashConsistent(s);
        }

        [Test]
        public void ApplyStep_Hit_SendsOpponentToBar()
        {
            var s = Custom(1, 0, 0, (1, 2), (4, -1), (6, -5), (8, -3), (13, -5), (24, -1));
            BackgammonEngine.SetDice(s, 3, 5);

            var step = new MoveStep(1, 4, 3, MoveFlags.Hit);
            BackgammonEngine.ApplyStep(s, step);

            Assert.That(s.board[1], Is.EqualTo(1));
            Assert.That(s.board[4], Is.EqualTo(1));
            Assert.That(s.board[25], Is.EqualTo(-1));
            AssertHashConsistent(s);
        }

        [Test]
        public void ApplyStep_BearOff_IncrementsBorneOff()
        {
            var s = Custom(1, 14, 0, (24, 1), (1, -15));
            BackgammonEngine.SetDice(s, 1, 2);

            var step = new MoveStep(24, 25, 1, MoveFlags.BearOff);
            BackgammonEngine.ApplyStep(s, step);

            Assert.That(s.board[24], Is.EqualTo(0));
            Assert.That(s.whiteBorneOff, Is.EqualTo(15));
            AssertHashConsistent(s);
        }

        [Test]
        public void ApplyStep_FromBar_EntersBoard()
        {
            var s = Custom(1, 0, 0, (0, 1), (1, 1), (12, 5), (17, 3), (19, 5), (24, -2), (13, -5), (8, -3), (6, -5));
            BackgammonEngine.SetDice(s, 3, 5);

            var step = new MoveStep(0, 3, 3, MoveFlags.FromBar);
            BackgammonEngine.ApplyStep(s, step);

            Assert.That(s.board[0], Is.EqualTo(0));
            Assert.That(s.board[3], Is.EqualTo(1));
            AssertHashConsistent(s);
        }

        [Test]
        public void ApplyStep_MissingDie_Throws()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            var step = new MoveStep(1, 7, 4, 0);
            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.ApplyStep(s, step));
        }

        [Test]
        public void UndoStep_RestoresStateExactly()
        {
            var s = Custom(1, 0, 0, (1, 2), (4, -1), (6, -5), (8, -3), (13, -5), (24, -1));
            BackgammonEngine.SetDice(s, 3, 5);

            var before = s.Clone();
            var step = new MoveStep(1, 4, 3, MoveFlags.Hit);

            BackgammonEngine.ApplyStep(s, step);
            BackgammonEngine.UndoStep(s, step);

            Assert.That(s.board, Is.EqualTo(before.board));
            Assert.That(s.whiteBorneOff, Is.EqualTo(before.whiteBorneOff));
            Assert.That(s.blackBorneOff, Is.EqualTo(before.blackBorneOff));
            Assert.That(s.remainingCount, Is.EqualTo(before.remainingCount));
            Assert.That(s.remainingDice, Is.EqualTo(before.remainingDice));
            Assert.That(s.hash, Is.EqualTo(before.hash));
        }

        [Test]
        public void UndoStep_BearOff_RestoresPiece()
        {
            var s = Custom(1, 14, 0, (24, 1), (1, -15));
            BackgammonEngine.SetDice(s, 1, 2);

            var before = s.Clone();
            var step = new MoveStep(24, 25, 1, MoveFlags.BearOff);

            BackgammonEngine.ApplyStep(s, step);
            BackgammonEngine.UndoStep(s, step);

            Assert.That(s.board[24], Is.EqualTo(1));
            Assert.That(s.whiteBorneOff, Is.EqualTo(14));
            Assert.That(s.hash, Is.EqualTo(before.hash));
        }

        // ------------------------------------------------------------------
        // ApplyMove / UndoMove
        // ------------------------------------------------------------------

        [Test]
        public void ApplyMove_ThenUndoMove_IsIdentity()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            var before = s.Clone();

            var seq = new MoveSequence();
            seq.Add(new MoveStep(1, 4, 3, 0));
            seq.Add(new MoveStep(12, 17, 5, 0));

            BackgammonEngine.ApplyMove(s, seq);
            AssertHashConsistent(s);

            BackgammonEngine.UndoMove(s, seq);

            Assert.That(s.board, Is.EqualTo(before.board));
            Assert.That(s.remainingCount, Is.EqualTo(before.remainingCount));
            Assert.That(s.remainingDice, Is.EqualTo(before.remainingDice));
            Assert.That(s.hash, Is.EqualTo(before.hash));
            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
        }

        [Test]
        public void ApplyMove_LastPieceBorneOff_SetsGameOver()
        {
            var s = Custom(1, 14, 0, (24, 1), (1, -15));
            BackgammonEngine.SetDice(s, 1, 1);

            var seq = new MoveSequence();
            seq.Add(new MoveStep(24, 25, 1, MoveFlags.BearOff));

            BackgammonEngine.ApplyMove(s, seq);

            Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver));
            AssertHashConsistent(s);
        }

        // ------------------------------------------------------------------
        // LoadAfterState
        // ------------------------------------------------------------------

        [Test]
        public void LoadAfterState_CopiesBoardAndHash()
        {
            var src = new BackgammonState();
            BackgammonEngine.SetDice(src, 3, 5);
            BackgammonEngine.ApplyStep(src, new MoveStep(1, 4, 3, 0));

            var list = new AfterStateList(4);
            list.AddPass(src);

            var dst = new BackgammonState();
            dst.turn = src.turn;
            BackgammonEngine.LoadAfterState(dst, list, 0);

            Assert.That(dst.board, Is.EqualTo(src.board));
            Assert.That(dst.whiteBorneOff, Is.EqualTo(src.whiteBorneOff));
            Assert.That(dst.blackBorneOff, Is.EqualTo(src.blackBorneOff));
            Assert.That(dst.hash, Is.EqualTo(src.hash));
            Assert.That(dst.remainingCount, Is.EqualTo(0));
            Assert.That(dst.phase, Is.EqualTo(GamePhase.Moving));
            Assert.That(dst.turn, Is.EqualTo(src.turn));
            AssertHashConsistent(dst);
        }

        [Test]
        public void LoadAfterState_OutOfRange_Throws()
        {
            var list = new AfterStateList(4);
            var dst = new BackgammonState();

            Assert.Throws<ArgumentOutOfRangeException>(() => BackgammonEngine.LoadAfterState(dst, list, 0));
        }

        // ------------------------------------------------------------------
        // EndTurn / PassTurn
        // ------------------------------------------------------------------

        [Test]
        public void EndTurn_FlipsTurnAndClearsDice()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            BackgammonEngine.EndTurn(s);

            Assert.That(s.turn, Is.EqualTo(-1));
            Assert.That(s.remainingCount, Is.EqualTo(0));
            Assert.That(s.rolledDice[0], Is.EqualTo(0));
            Assert.That(s.rolledDice[1], Is.EqualTo(0));
            Assert.That(s.phase, Is.EqualTo(GamePhase.PreRoll));
            AssertHashConsistent(s);
        }

        [Test]
        public void EndTurn_Twice_ReturnsToOriginalTurnAndHash()
        {
            var s = new BackgammonState();
            ulong original = s.hash;

            BackgammonEngine.EndTurn(s);
            BackgammonEngine.EndTurn(s);

            Assert.That(s.turn, Is.EqualTo(1));
            Assert.That(s.hash, Is.EqualTo(original));
        }

        [Test]
        public void PassTurn_ClearsDiceAndEndsTurn()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            BackgammonEngine.PassTurn(s);

            Assert.That(s.turn, Is.EqualTo(-1));
            Assert.That(s.remainingCount, Is.EqualTo(0));
            AssertHashConsistent(s);
        }

        // ------------------------------------------------------------------
        // IsGameOver
        // ------------------------------------------------------------------

        [Test]
        public void IsGameOver_NotOver_ReturnsFalse()
        {
            var s = new BackgammonState();
            Assert.That(BackgammonEngine.IsGameOver(s, out _), Is.False);
        }

        [Test]
        public void IsGameOver_Single_WhenLoserBoreOffSome()
        {
            var s = Custom(1, 15, 1, (1, -14));
            Assert.That(BackgammonEngine.IsGameOver(s, out var r), Is.True);
            Assert.That(r.Winner, Is.EqualTo(1));
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Single));
            Assert.That(r.Points, Is.EqualTo(1));
        }

        [Test]
        public void IsGameOver_Gammon_WhenLoserHasNoPieceInWinnerHome()
        {
            var s = Custom(1, 15, 0, (1, -10), (7, -5));
            Assert.That(BackgammonEngine.IsGameOver(s, out var r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Gammon));
            Assert.That(r.Points, Is.EqualTo(2));
        }

        [Test]
        public void IsGameOver_Backgammon_WhenLoserOnBar()
        {
            var s = Custom(1, 15, 0, (1, -10), (25, -5));
            Assert.That(BackgammonEngine.IsGameOver(s, out var r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Backgammon));
            Assert.That(r.Points, Is.EqualTo(3));
        }

        [Test]
        public void IsGameOver_Backgammon_WhenLoserInWinnerHome()
        {
            var s = Custom(1, 15, 0, (1, -10), (20, -5));
            Assert.That(BackgammonEngine.IsGameOver(s, out var r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Backgammon));
        }

        [Test]
        public void IsGameOver_Jacoby_ReducesToSingle()
        {
            var s = Custom(1, 15, 0, (1, -10), (7, -5));
            var es = EngineSettings.Default;
            es.EnableJacoby = true;

            Assert.That(BackgammonEngine.IsGameOver(s, es, out var r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Single));
            Assert.That(r.Points, Is.EqualTo(1));
        }

        [Test]
        public void IsGameOver_Jacoby_NotAppliedWhenCubeOwned()
        {
            var s = Custom(1, 15, 0, (1, -10), (7, -5));
            s.cubeOwner = 1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            var es = EngineSettings.Default;
            es.EnableJacoby = true;

            Assert.That(BackgammonEngine.IsGameOver(s, es, out var r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Gammon));
        }

        [Test]
        public void IsGameOver_BlackWins()
        {
            var s = Custom(-1, 0, 15, (1, 15));
            Assert.That(BackgammonEngine.IsGameOver(s, out var r), Is.True);
            Assert.That(r.Winner, Is.EqualTo(-1));
        }
    }
}
