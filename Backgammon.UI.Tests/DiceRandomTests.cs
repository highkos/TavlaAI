using System;
using System.Collections.Generic;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Zar rastgeleligi regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <b>Hata:</b> canli oyunda <see cref="GameOrchestratorOptions.Random"/> sabit bir tohumla
    /// (<c>0x7A71A_0005</c>) olusturuluyordu. Bu yuzden her uygulama acilisinda <b>ayni</b> zar
    /// dizisi geliyordu (ornegin once <c>5-2</c>, sonra <c>6-6</c>). Motor deterministiktir ve
    /// tohumu disaridan alir; dogru davranis, host'un tohumu isletim sisteminden uretmesidir.
    /// </remarks>
    [TestFixture]
    public sealed class DiceRandomTests
    {
        [Test]
        public void NewSeed_ProducesDifferentValues()
        {
            var seeds = new HashSet<ulong>();
            for (int i = 0; i < 32; i++)
            {
                seeds.Add(DiceRandom.NewSeed());
            }

            Assert.That(seeds.Count, Is.GreaterThan(30),
                        "32 cagrida en az 31 farkli tohum beklenir; sabit tohum tek eleman verir");
        }

        [Test]
        public void Create_ProducesDifferentDiceSequences()
        {
            string first = Sequence(DiceRandom.Create());
            string second = Sequence(DiceRandom.Create());

            Assert.That(first, Is.Not.EqualTo(second),
                        "iki ayri uretec ayni zar dizisini vermemeli");
        }

        [Test]
        public void Create_ProducesAllSixFaces()
        {
            Xoshiro256StarStar random = DiceRandom.Create();
            var seen = new bool[7];

            for (int i = 0; i < 600; i++)
            {
                int die = random.RollDie();
                Assert.That(die, Is.InRange(1, 6));
                seen[die] = true;
            }

            for (int face = 1; face <= 6; face++)
            {
                Assert.That(seen[face], Is.True, "yuz " + face + " hic gelmedi");
            }
        }

        [Test]
        public void FixedSeed_IsStillReproducible()
        {
            // Determinizm sozlesmesi bozulmamali: ayni tohum ayni diziyi verir.
            string first = Sequence(new Xoshiro256StarStar(0x7A71A_0005UL));
            string second = Sequence(new Xoshiro256StarStar(0x7A71A_0005UL));

            Assert.That(first, Is.EqualTo(second));
        }

        private static string Sequence(IRandom random)
        {
            var parts = new string[24];
            for (int i = 0; i < parts.Length; i++)
            {
                parts[i] = random.RollDie().ToString();
            }

            return string.Join("-", parts);
        }
    }
}
