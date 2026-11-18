using Backgammon.Core;

namespace Backgammon.Tests
{
    [TestFixture]
    public class MoveStructureTests
    {
        [Test]
        public void MoveStep_FlagHelpers()
        {
            var hit = new MoveStep(6, 5, 1, MoveFlags.Hit);
            Assert.That(hit.IsHit, Is.True);
            Assert.That(hit.IsBearOff, Is.False);
            Assert.That(hit.IsFromBar, Is.False);

            var bearOff = new MoveStep(22, 25, 3, MoveFlags.BearOff);
            Assert.That(bearOff.IsBearOff, Is.True);
            Assert.That(bearOff.IsHit, Is.False);

            var fromBar = new MoveStep(0, 4, 4, MoveFlags.FromBar);
            Assert.That(fromBar.IsFromBar, Is.True);
        }

        [Test]
        public void MoveSequence_AddAndIndexer()
        {
            var seq = default(MoveSequence);
            Assert.That(seq.Count, Is.EqualTo(0));
            Assert.That(seq.IsEmpty, Is.True);

            seq.Add(new MoveStep(1, 4, 3, MoveFlags.None));
            seq.Add(new MoveStep(4, 8, 4, MoveFlags.None));

            Assert.That(seq.Count, Is.EqualTo(2));
            Assert.That(seq[0].From, Is.EqualTo(1));
            Assert.That(seq[1].To, Is.EqualTo(8));

            seq[1] = new MoveStep(4, 9, 5, MoveFlags.None);
            Assert.That(seq[1].To, Is.EqualTo(9));
        }

        [Test]
        public void MoveSequence_AddBeyondFour_Throws()
        {
            var seq = default(MoveSequence);
            for (int i = 0; i < 4; i++)
            {
                seq.Add(new MoveStep(1, 2, 1, MoveFlags.None));
            }

            Assert.Throws<InvalidOperationException>(() => seq.Add(new MoveStep(1, 2, 1, MoveFlags.None)));
        }

        [Test]
        public void MoveSequence_IndexerOutOfRange_Throws()
        {
            var seq = default(MoveSequence);
            Assert.Throws<IndexOutOfRangeException>(() => { var _ = seq[4]; });
        }

        [Test]
        public void MoveSequence_Clear_ResetsCount()
        {
            var seq = default(MoveSequence);
            seq.Add(new MoveStep(1, 2, 1, MoveFlags.None));
            seq.Clear();

            Assert.That(seq.Count, Is.EqualTo(0));
            Assert.That(seq.IsEmpty, Is.True);
        }

        [Test]
        public void MoveList_AddAndClear()
        {
            var list = new MoveList(4);
            Assert.That(list.Capacity, Is.EqualTo(4));
            Assert.That(list.Count, Is.EqualTo(0));

            var seq = default(MoveSequence);
            seq.Add(new MoveStep(1, 2, 1, MoveFlags.None));
            list.Add(seq);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list[0].Count, Is.EqualTo(1));

            list.Clear();
            Assert.That(list.Count, Is.EqualTo(0));
        }

        [Test]
        public void MoveList_DefaultCapacity_Is4096()
        {
            var list = new MoveList();
            Assert.That(list.Capacity, Is.EqualTo(MoveList.DefaultCapacity));
            Assert.That(MoveList.DefaultCapacity, Is.EqualTo(4096));
            Assert.That(MoveList.DefaultCapacity, Is.EqualTo(AfterStateList.DefaultCapacity));
        }

        [Test]
        public void SequenceBuffer_CoversAfterStateListCapacity()
        {
            // F7-29: seq buffer, afterstate listesinden küçük olmamalı. Küçük olsaydı
            // GenerateAfterStates liste hâlâ yer varken buffer'da taşardı.
            Assert.That(LegalMoveGenerator.SequenceBufferCapacity,
                        Is.GreaterThanOrEqualTo(AfterStateList.DefaultCapacity));
        }

        [Test]
        public void StepBuffer_DepthBound_MatchesMaxSteps()
        {
            // F7-37: StepBuf indeksi 0..MaxSteps. 1-1 dublesi 4 adıma kadar çıkar;
            // bu sınırda taşma olmamalı.
            Assert.That(MoveSequence.MaxSteps, Is.EqualTo(4));

            var s = new BackgammonState();
            s.Reset();
            BackgammonEngine.SetDice(s, 1, 1);

            var list = new AfterStateList();
            Assert.DoesNotThrow(() => LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list));
            Assert.That(list.Count, Is.GreaterThan(0));

            for (int i = 0; i < list.Count; i++)
            {
                Assert.That(list.Sequences[i].Count, Is.LessThanOrEqualTo(MoveSequence.MaxSteps));
            }
        }

        [Test]
        public void MoveList_Overflow_Throws()
        {
            var list = new MoveList(1);
            list.Add(default(MoveSequence));

            Assert.Throws<InvalidOperationException>(() => list.Add(default(MoveSequence)));
        }
    }
}
