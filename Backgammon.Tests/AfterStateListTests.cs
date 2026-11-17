using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class AfterStateListTests
    {
        [Test]
        public void DefaultCapacity_Is2048()
        {
            var list = new AfterStateList();
            Assert.That(list.Capacity, Is.EqualTo(AfterStateList.DefaultCapacity));
            Assert.That(AfterStateList.DefaultCapacity, Is.EqualTo(2048));
        }

        [Test]
        public void AddPass_CopiesPositionAndClearsSequence()
        {
            var s = new BackgammonState();
            s.board[3] = 1;
            s.board[1] = 1;
            s.whiteBorneOff = 1;
            s.turn = -1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            var list = new AfterStateList(4);
            list.AddPass(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.BoardOf(0).ToArray(), Is.EqualTo(s.board));
            Assert.That(list.WhiteBorneOff[0], Is.EqualTo(1));
            Assert.That(list.BlackBorneOff[0], Is.EqualTo(0));
            Assert.That(list.Hash[0], Is.EqualTo(s.hash));
            Assert.That(list.Sequences[0].Count, Is.EqualTo(0));
            Assert.That(list.IsTerminal[0], Is.False);
            Assert.That(list.ResultType[0], Is.EqualTo(0));
            Assert.That(list.ResultPoints[0], Is.EqualTo(0));
        }

        [Test]
        public void AddPass_Overflow_Throws()
        {
            var list = new AfterStateList(1);
            list.AddPass(new BackgammonState());

            Assert.Throws<InvalidOperationException>(() => list.AddPass(new BackgammonState()));
        }

        [Test]
        public void BoardOf_OutOfRange_Throws()
        {
            var list = new AfterStateList(2);
            Assert.Throws<ArgumentOutOfRangeException>(() => { var _ = list.BoardOf(0); });
        }

        [Test]
        public void Swap_SwapsAllFields()
        {
            var a = new BackgammonState();
            a.board[1] = 1;
            a.board[2] = 1;
            a.whiteBorneOff = 1;
            a.hash = 0x1111;

            var b = new BackgammonState();
            b.board[1] = 0;
            b.board[2] = 0;
            b.board[3] = 2;
            b.blackBorneOff = 2;
            b.hash = 0x2222;

            var list = new AfterStateList(2);
            list.AddPass(a);
            list.AddPass(b);

            var seq = default(MoveSequence);
            seq.Add(new MoveStep(1, 2, 1, MoveFlags.None));
            list.Sequences[0] = seq;
            list.IsTerminal[0] = true;
            list.ResultType[0] = 2;
            list.ResultPoints[0] = 2;

            list.Swap(0, 1);

            Assert.That(list.BoardOf(0).ToArray(), Is.EqualTo(b.board));
            Assert.That(list.BoardOf(1).ToArray(), Is.EqualTo(a.board));
            Assert.That(list.WhiteBorneOff[0], Is.EqualTo(0));
            Assert.That(list.WhiteBorneOff[1], Is.EqualTo(1));
            Assert.That(list.BlackBorneOff[0], Is.EqualTo(2));
            Assert.That(list.BlackBorneOff[1], Is.EqualTo(0));
            Assert.That(list.Hash[0], Is.EqualTo(0x2222));
            Assert.That(list.Hash[1], Is.EqualTo(0x1111));
            Assert.That(list.Sequences[0].Count, Is.EqualTo(0));
            Assert.That(list.Sequences[1].Count, Is.EqualTo(1));
            Assert.That(list.IsTerminal[0], Is.False);
            Assert.That(list.IsTerminal[1], Is.True);
            Assert.That(list.ResultType[0], Is.EqualTo(0));
            Assert.That(list.ResultType[1], Is.EqualTo(2));
            Assert.That(list.ResultPoints[0], Is.EqualTo(0));
            Assert.That(list.ResultPoints[1], Is.EqualTo(2));
        }

        [Test]
        public void Swap_SameIndex_IsNoOp()
        {
            var list = new AfterStateList(2);
            list.AddPass(new BackgammonState());
            list.Swap(0, 0);
            Assert.That(list.Count, Is.EqualTo(1));
        }

        [Test]
        public void Clear_ResetsCount()
        {
            var list = new AfterStateList(2);
            list.AddPass(new BackgammonState());
            list.Clear();
            Assert.That(list.Count, Is.EqualTo(0));
        }
    }
}
