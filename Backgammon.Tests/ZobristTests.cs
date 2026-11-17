using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class ZobristTests
    {
        [Test]
        public void ComputeZobristHash_IsDeterministic()
        {
            var a = new BackgammonState();
            var b = new BackgammonState();

            Assert.That(BackgammonEngine.ComputeZobristHash(a), Is.EqualTo(BackgammonEngine.ComputeZobristHash(b)));
        }

        [Test]
        public void Reset_InitializesHashToComputedValue()
        {
            var s = new BackgammonState();
            Assert.That(s.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(s)));
        }

        [Test]
        public void Hash_DependsOnTurn()
        {
            var s = new BackgammonState();
            ulong white = BackgammonEngine.ComputeZobristHash(s);

            s.turn = -1;
            ulong black = BackgammonEngine.ComputeZobristHash(s);

            Assert.That(black, Is.Not.EqualTo(white));
        }

        [Test]
        public void Hash_DependsOnCubeValueAndOwner()
        {
            var s = new BackgammonState();
            ulong baseline = BackgammonEngine.ComputeZobristHash(s);

            s.cubeValue = 2;
            ulong doubled = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(doubled, Is.Not.EqualTo(baseline));

            s.cubeValue = 1;
            s.cubeOwner = 1;
            ulong owned = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(owned, Is.Not.EqualTo(baseline));

            s.cubeOwner = -1;
            ulong ownedByBlack = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(ownedByBlack, Is.Not.EqualTo(owned));
        }

        [Test]
        public void Hash_DependsOnBoardAndBorneOff()
        {
            var s = new BackgammonState();
            ulong baseline = BackgammonEngine.ComputeZobristHash(s);

            s.board[1] = 1;
            s.board[2] = 1;
            ulong moved = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(moved, Is.Not.EqualTo(baseline));

            s.board[1] = 2;
            s.board[2] = 0;
            s.whiteBorneOff = 1;
            ulong borneOff = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(borneOff, Is.Not.EqualTo(baseline));
        }

        [Test]
        public void Hash_IgnoresDiceAndPhase()
        {
            var s = new BackgammonState();
            ulong baseline = BackgammonEngine.ComputeZobristHash(s);

            s.rolledDice[0] = 3;
            s.rolledDice[1] = 5;
            s.remainingDice[0] = 3;
            s.remainingDice[1] = 5;
            s.remainingCount = 2;
            s.phase = GamePhase.Moving;

            Assert.That(BackgammonEngine.ComputeZobristHash(s), Is.EqualTo(baseline));
        }

        [Test]
        public void MirrorTo_InitialPositionIsSelfMirrored()
        {
            var src = new BackgammonState();
            var dst = new BackgammonState();

            BackgammonEngine.MirrorTo(src, dst);

            Assert.That(dst.board, Is.EqualTo(src.board));
            Assert.That(dst.turn, Is.EqualTo(-1));
            Assert.That(dst.whiteBorneOff, Is.EqualTo(src.blackBorneOff));
            Assert.That(dst.blackBorneOff, Is.EqualTo(src.whiteBorneOff));
            Assert.That(dst.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(dst)));
        }

        [Test]
        public void MirrorTo_TwiceRestoresOriginal()
        {
            var src = new BackgammonState();
            src.board[1] = 1;
            src.board[2] = 1;
            src.board[20] = 3;
            src.whiteBorneOff = 1;
            src.blackBorneOff = 2;
            src.cubeValue = 4;
            src.cubeOwner = 1;
            src.whiteScore = 3;
            src.blackScore = 1;
            src.hash = BackgammonEngine.ComputeZobristHash(src);

            var mirrored = new BackgammonState();
            var restored = new BackgammonState();

            BackgammonEngine.MirrorTo(src, mirrored);
            BackgammonEngine.MirrorTo(mirrored, restored);

            Assert.That(restored.board, Is.EqualTo(src.board));
            Assert.That(restored.turn, Is.EqualTo(src.turn));
            Assert.That(restored.whiteBorneOff, Is.EqualTo(src.whiteBorneOff));
            Assert.That(restored.blackBorneOff, Is.EqualTo(src.blackBorneOff));
            Assert.That(restored.cubeValue, Is.EqualTo(src.cubeValue));
            Assert.That(restored.cubeOwner, Is.EqualTo(src.cubeOwner));
            Assert.That(restored.whiteScore, Is.EqualTo(src.whiteScore));
            Assert.That(restored.blackScore, Is.EqualTo(src.blackScore));
            Assert.That(restored.hash, Is.EqualTo(src.hash));
        }

        [Test]
        public void MirrorTo_SameInstance_Throws()
        {
            var s = new BackgammonState();
            Assert.Throws<ArgumentException>(() => BackgammonEngine.MirrorTo(s, s));
        }
    }
}
