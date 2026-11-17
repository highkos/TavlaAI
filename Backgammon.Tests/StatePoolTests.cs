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
    }
}
