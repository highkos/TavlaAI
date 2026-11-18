using System;
using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class StatePoolTests
    {
        [Test]
        public void Rent_ReturnsDistinctStates()
        {
            var pool = new StatePool(2);

            var a = pool.Rent();
            var b = pool.Rent();

            Assert.That(a, Is.Not.Null);
            Assert.That(b, Is.Not.Null);
            Assert.That(ReferenceEquals(a, b), Is.False);
            Assert.That(pool.Available, Is.EqualTo(0));
        }

        [Test]
        public void Rent_WhenEmpty_Throws()
        {
            var pool = new StatePool(1);
            pool.Rent();

            Assert.Throws<InvalidOperationException>(() => pool.Rent());
        }

        [Test]
        public void Return_MakesStateAvailableAgain()
        {
            var pool = new StatePool(1);
            var a = pool.Rent();
            pool.Return(a);

            Assert.That(pool.Available, Is.EqualTo(1));
            Assert.That(ReferenceEquals(pool.Rent(), a), Is.True);
        }

        [Test]
        public void Return_Null_Throws()
        {
            var pool = new StatePool(1);
            Assert.Throws<ArgumentNullException>(() => pool.Return(null));
        }

        [Test]
        public void Constructor_InvalidCapacity_Throws()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new StatePool(0));
        }

        // ---------------- HATA 1: Return sifirlamali ----------------

        [Test]
        public void Return_ResetsStateToStartPosition()
        {
            var pool = new StatePool(1);
            var a = pool.Rent();

            // Kirlet: taslari ve skorlari degistir.
            Array.Clear(a.board, 0, BackgammonState.BoardSize);
            a.board[3] = 7;
            a.whiteBorneOff = 9;
            a.blackBorneOff = 4;
            a.turn = -1;
            a.cubeValue = 8;
            a.cubeOwner = -1;
            a.matchLength = 7;
            a.whiteScore = 3;
            a.blackScore = 5;
            a.isCrawfordGame = true;
            a.crawfordPlayed = true;
            a.cubePassed = true;
            a.phase = GamePhase.GameOver;
            a.remainingCount = 2;
            a.remainingDice[0] = 6;
            a.remainingDice[1] = 5;
            a.hash = 0xDEADBEEFUL;

            pool.Return(a);
            var again = pool.Rent();

            Assert.That(ReferenceEquals(again, a), Is.True, "ayni ornek donmeli");
            Assert.That(again.board[3], Is.EqualTo(0), "board sifirlanmali");
            Assert.That(again.board[1], Is.EqualTo(2), "baslangic dizilimi");
            Assert.That(again.board[24], Is.EqualTo(-2), "baslangic dizilimi");
            Assert.That(again.whiteBorneOff, Is.EqualTo(0));
            Assert.That(again.blackBorneOff, Is.EqualTo(0));
            Assert.That(again.turn, Is.EqualTo(1));
            Assert.That(again.cubeValue, Is.EqualTo(1));
            Assert.That(again.cubeOwner, Is.EqualTo(0));
            Assert.That(again.matchLength, Is.EqualTo(0));
            Assert.That(again.whiteScore, Is.EqualTo(0));
            Assert.That(again.blackScore, Is.EqualTo(0));
            Assert.That(again.isCrawfordGame, Is.False);
            Assert.That(again.crawfordPlayed, Is.False);
            Assert.That(again.cubePassed, Is.False);
            Assert.That(again.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
            Assert.That(again.remainingCount, Is.EqualTo(0));
            Assert.That(again.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(again)),
                        "hash sifirlanmis tahtayla tutarli olmali");
        }

        [Test]
        public void Return_ThenRent_DoesNotLeakStaleData()
        {
            var pool = new StatePool(2);
            var a = pool.Rent();
            a.board[5] = 11;
            a.whiteBorneOff = 3;
            pool.Return(a);

            var b = pool.Rent();
            Assert.That(b.board[5], Is.EqualTo(0));
            Assert.That(b.whiteBorneOff, Is.EqualTo(0));
        }

        // ---------------- HATA 2: yabanci / cift iade ----------------

        [Test]
        public void Return_ForeignState_Throws()
        {
            var pool = new StatePool(2);
            pool.Rent();
            var foreign = new BackgammonState();

            var ex = Assert.Throws<InvalidOperationException>(() => pool.Return(foreign));
            Assert.That(ex.Message, Does.Contain("ait degil").IgnoreCase.Or.Contain("ait değil"));
        }

        [Test]
        public void Return_ForeignState_DoesNotCorruptPool()
        {
            var pool = new StatePool(2);
            var a = pool.Rent();
            var b = pool.Rent();
            var foreign = new BackgammonState();

            Assert.Throws<InvalidOperationException>(() => pool.Return(foreign));

            // Havuz bozulmamali: iki state de hala iade edilebilir olmali.
            pool.Return(a);
            pool.Return(b);
            Assert.That(pool.Available, Is.EqualTo(2));
            Assert.That(ReferenceEquals(pool.Rent(), b), Is.True);
            Assert.That(ReferenceEquals(pool.Rent(), a), Is.True);
        }

        [Test]
        public void Return_Twice_Throws()
        {
            var pool = new StatePool(1);
            var a = pool.Rent();
            pool.Return(a);

            Assert.Throws<InvalidOperationException>(() => pool.Return(a));
        }

        [Test]
        public void Return_Twice_DoesNotInflateAvailable()
        {
            var pool = new StatePool(1);
            var a = pool.Rent();
            pool.Return(a);
            Assert.Throws<InvalidOperationException>(() => pool.Return(a));

            Assert.That(pool.Available, Is.EqualTo(1));
        }

        [Test]
        public void RentReturn_Cycle_KeepsCapacityStable()
        {
            var pool = new StatePool(3);
            for (int i = 0; i < 1000; i++)
            {
                var s = pool.Rent();
                s.board[0] = (sbyte)(i % 5);
                pool.Return(s);
            }

            Assert.That(pool.Available, Is.EqualTo(3));
            Assert.That(pool.Capacity, Is.EqualTo(3));
        }
    }
}
