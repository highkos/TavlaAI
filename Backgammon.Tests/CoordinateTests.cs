using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class CoordinateTests
    {
        [Test]
        public void DistanceToOff_White()
        {
            Assert.That(BackgammonEngine.DistanceToOff(24, 1), Is.EqualTo(1));
            Assert.That(BackgammonEngine.DistanceToOff(19, 1), Is.EqualTo(6));
            Assert.That(BackgammonEngine.DistanceToOff(0, 1), Is.EqualTo(25));
        }

        [Test]
        public void DistanceToOff_Black()
        {
            Assert.That(BackgammonEngine.DistanceToOff(1, -1), Is.EqualTo(1));
            Assert.That(BackgammonEngine.DistanceToOff(6, -1), Is.EqualTo(6));
            Assert.That(BackgammonEngine.DistanceToOff(25, -1), Is.EqualTo(25));
        }

        [Test]
        public void IsHome_White()
        {
            Assert.That(BackgammonEngine.IsHome(19, 1), Is.True);
            Assert.That(BackgammonEngine.IsHome(24, 1), Is.True);
            Assert.That(BackgammonEngine.IsHome(18, 1), Is.False);
            Assert.That(BackgammonEngine.IsHome(1, 1), Is.False);
        }

        [Test]
        public void IsHome_Black()
        {
            Assert.That(BackgammonEngine.IsHome(1, -1), Is.True);
            Assert.That(BackgammonEngine.IsHome(6, -1), Is.True);
            Assert.That(BackgammonEngine.IsHome(7, -1), Is.False);
            Assert.That(BackgammonEngine.IsHome(24, -1), Is.False);
        }

        [Test]
        public void BarIndex_BothColors()
        {
            Assert.That(BackgammonEngine.BarIndex(1), Is.EqualTo(0));
            Assert.That(BackgammonEngine.BarIndex(-1), Is.EqualTo(25));
        }
    }
}
