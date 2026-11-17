using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class BackgammonStateTests
    {
        [Test]
        public void Reset_ProducesStandardStartingPosition()
        {
            var s = new BackgammonState();

            Assert.That(s.board[1], Is.EqualTo(2));
            Assert.That(s.board[12], Is.EqualTo(5));
            Assert.That(s.board[17], Is.EqualTo(3));
            Assert.That(s.board[19], Is.EqualTo(5));

            Assert.That(s.board[24], Is.EqualTo(-2));
            Assert.That(s.board[13], Is.EqualTo(-5));
            Assert.That(s.board[8], Is.EqualTo(-3));
            Assert.That(s.board[6], Is.EqualTo(-5));

            Assert.That(s.board[0], Is.EqualTo(0));
            Assert.That(s.board[25], Is.EqualTo(0));

            Assert.That(s.whiteBorneOff, Is.EqualTo(0));
            Assert.That(s.blackBorneOff, Is.EqualTo(0));
            Assert.That(s.turn, Is.EqualTo(1));
            Assert.That(s.remainingCount, Is.EqualTo(0));
            Assert.That(s.cubeValue, Is.EqualTo(1));
            Assert.That(s.cubeOwner, Is.EqualTo(0));
            Assert.That(s.matchLength, Is.EqualTo(0));
            Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
        }

        [Test]
        public void Reset_CountsFifteenPiecesPerPlayer()
        {
            var s = new BackgammonState();

            Assert.That(s.CountPieces(1), Is.EqualTo(15));
            Assert.That(s.CountPieces(-1), Is.EqualTo(15));
        }

        [Test]
        public void CopyFrom_CopiesAllFieldsAndDoesNotShareBoard()
        {
            var src = new BackgammonState();
            src.board[5] = 4;
            src.whiteBorneOff = 3;
            src.blackBorneOff = 2;
            src.turn = -1;
            src.rolledDice[0] = 3;
            src.rolledDice[1] = 5;
            src.remainingDice[0] = 3;
            src.remainingDice[1] = 5;
            src.remainingCount = 2;
            src.cubeValue = 4;
            src.cubeOwner = -1;
            src.matchLength = 7;
            src.whiteScore = 2;
            src.blackScore = 5;
            src.isCrawfordGame = true;
            src.crawfordPlayed = true;
            src.phase = GamePhase.Moving;
            src.hash = 0xDEADBEEF;

            var dst = new BackgammonState();
            dst.CopyFrom(src);

            Assert.That(dst.board, Is.EqualTo(src.board));
            Assert.That(dst.whiteBorneOff, Is.EqualTo(3));
            Assert.That(dst.blackBorneOff, Is.EqualTo(2));
            Assert.That(dst.turn, Is.EqualTo(-1));
            Assert.That(dst.rolledDice, Is.EqualTo(new byte[] { 3, 5 }));
            Assert.That(dst.remainingDice, Is.EqualTo(new byte[] { 3, 5, 0, 0 }));
            Assert.That(dst.remainingCount, Is.EqualTo(2));
            Assert.That(dst.cubeValue, Is.EqualTo(4));
            Assert.That(dst.cubeOwner, Is.EqualTo(-1));
            Assert.That(dst.matchLength, Is.EqualTo(7));
            Assert.That(dst.whiteScore, Is.EqualTo(2));
            Assert.That(dst.blackScore, Is.EqualTo(5));
            Assert.That(dst.isCrawfordGame, Is.True);
            Assert.That(dst.crawfordPlayed, Is.True);
            Assert.That(dst.phase, Is.EqualTo(GamePhase.Moving));
            Assert.That(dst.hash, Is.EqualTo(0xDEADBEEF));

            // Deep copy: kaynak diziyi değiştirmek hedefi etkilememeli.
            src.board[5] = 0;
            Assert.That(dst.board[5], Is.EqualTo(4));
            Assert.That(ReferenceEquals(src.board, dst.board), Is.False);
        }

        [Test]
        public void Clone_IsIndependent()
        {
            var src = new BackgammonState();
            var clone = src.Clone();

            clone.board[1] = 0;

            Assert.That(src.board[1], Is.EqualTo(2));
            Assert.That(clone.board[1], Is.EqualTo(0));
        }

        [Test]
        public void CopyFrom_Null_Throws()
        {
            var s = new BackgammonState();
            Assert.Throws<ArgumentNullException>(() => s.CopyFrom(null));
        }
    }
}
