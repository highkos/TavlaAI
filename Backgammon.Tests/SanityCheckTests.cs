using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class SanityCheckTests
    {
        [Test]
        public void InitialPosition_Passes()
        {
            var s = new BackgammonState();
            Assert.DoesNotThrow(() => BackgammonEngine.SanityCheck(s));
        }

#if DEBUG
        [Test]
        public void WrongPieceCount_Throws()
        {
            var s = new BackgammonState();
            s.board[1] = 1;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(s));
        }

        [Test]
        public void HashMismatch_Throws()
        {
            var s = new BackgammonState();
            s.hash ^= 0x1UL;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(s));
        }

        [Test]
        public void NegativeWhiteBar_Throws()
        {
            var s = new BackgammonState();
            s.board[0] = -1;
            s.board[1] = 3;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(s));
        }

        [Test]
        public void GameOverWithoutBorneOff_Throws()
        {
            var s = new BackgammonState();
            s.phase = GamePhase.GameOver;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(s));
        }

        [Test]
        public void AfterStateList_TerminalFlagMismatch_Throws()
        {
            var list = new AfterStateList(1);
            list.AddPass(new BackgammonState());
            list.IsTerminal[0] = true;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(list));
        }

        [Test]
        public void AfterStateList_NonTerminalWithResult_Throws()
        {
            var list = new AfterStateList(1);
            list.AddPass(new BackgammonState());
            list.ResultType[0] = 1;
            list.ResultPoints[0] = 1;

            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.SanityCheck(list));
        }
#endif
    }
}
