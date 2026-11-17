using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 2 v4 Bölüm 5: <see cref="BackgammonVectorizer"/> testleri (madde 1-12).
    /// TDD: bu dosya Aşama A'da yazılır ve uygulama tamamlanana kadar kırmızıdır.
    /// </summary>
    [TestFixture]
    public class VectorizerTests
    {
        private const int N = BackgammonVectorizer.InputVectorSize;

        // ==================================================================
        // Madde 1: altın vektör (başlangıç pozisyonu)
        // ==================================================================

        [Test]
        public void Golden_StartingPosition_WhitePerspective()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);

            float[] v = VectorTestSupport.Vec(s, 1);

            // Aktif blok (Beyaz taşları), j = DistanceToOff(point, +1) = 25 - point.
            VectorTestSupport.AssertBlockOnly(v, VectorLayout.ActiveOffset,
                (24, 2), (13, 5), (8, 3), (6, 5));

            // Rakip blok (Siyah taşları, AYNI çerçeve ve aynı j).
            VectorTestSupport.AssertBlockOnly(v, VectorLayout.OppOffset,
                (1, 2), (12, 5), (17, 3), (19, 5));

            Assert.That(v[VectorLayout.ActiveBar], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.OppBar], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.ActiveOff], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.OppOff], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.CubeOwner], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.CubeValue], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.IsMoneyGame], Is.EqualTo(1f));
            Assert.That(v[VectorLayout.IsCrawford], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.ActivePip], Is.EqualTo(1f));
            Assert.That(v[VectorLayout.OppPip], Is.EqualTo(1f));
            Assert.That(v[VectorLayout.ActiveEscaped], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.OppEscaped], Is.EqualTo(0f));
            Assert.That(v[VectorLayout.IsContact], Is.EqualTo(1f));

            for (int i = 0; i < VectorLayout.AwayBuckets; i++)
            {
                Assert.That(v[VectorLayout.ActiveAwayOffset + i], Is.EqualTo(0f), "ActiveAway[" + i + "]");
                Assert.That(v[VectorLayout.OppAwayOffset + i], Is.EqualTo(0f), "OppAway[" + i + "]");
            }
        }

        /// <summary>Başlangıç pozisyonu aynalama altında simetrik olduğu için sonuç birebir aynı olmalı.</summary>
        [Test]
        public void Golden_StartingPosition_BlackPerspectiveIsIdentical()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);

            VectorTestSupport.AssertBitEqual(
                VectorTestSupport.Vec(s, 1),
                VectorTestSupport.Vec(s, -1),
                "başlangıç pozisyonu perspektif simetrisi");
        }

        // ==================================================================
        // Madde 2: ayna özdeşliği
        // ==================================================================

        [Test]
        public void Mirror_Identity_OnRandomPositions()
        {
            var rng = new Xoshiro256StarStar(0xA11CE5EEDUL);
            var s = new BackgammonState();
            var m = new BackgammonState();

            for (int i = 0; i < 2000; i++)
            {
                VectorTestSupport.RandomPosition(rng, s);
                BackgammonEngine.MirrorTo(s, m);

                VectorTestSupport.AssertBitEqual(
                    VectorTestSupport.Vec(s, 1), VectorTestSupport.Vec(m, -1), "i=" + i + " p=+1");
                VectorTestSupport.AssertBitEqual(
                    VectorTestSupport.Vec(s, -1), VectorTestSupport.Vec(m, 1), "i=" + i + " p=-1");

                VectorTestSupport.AssertBitEqual(
                    VectorTestSupport.Vec(s, s.turn), VectorTestSupport.Vec(m, m.turn), "i=" + i + " p=turn");
            }
        }

        // ==================================================================
        // Madde 3: perspektif değişimi
        // ==================================================================

        [Test]
        public void PerspectiveSwap_ActiveAndOpponentBlocksMirror()
        {
            var rng = new Xoshiro256StarStar(0x5EE5AADUL);
            var s = new BackgammonState();

            for (int iter = 0; iter < 500; iter++)
            {
                VectorTestSupport.RandomPosition(rng, s);

                float[] a = VectorTestSupport.Vec(s, 1);
                float[] b = VectorTestSupport.Vec(s, -1);

                // Vec(s,-p).Active[j'] == Vec(s,p).Opp[25 - j']
                for (int j = 1; j <= VectorLayout.Points; j++)
                {
                    int jj = 25 - j;
                    for (int k = 0; k < VectorLayout.PointBlockSize; k++)
                    {
                        Assert.That(b[VectorLayout.ActivePointIndex(j, k)],
                            Is.EqualTo(a[VectorLayout.OppPointIndex(jj, k)]),
                            "iter " + iter + " j=" + j + " k=" + k);
                        Assert.That(b[VectorLayout.OppPointIndex(j, k)],
                            Is.EqualTo(a[VectorLayout.ActivePointIndex(jj, k)]),
                            "iter " + iter + " opp j=" + j + " k=" + k);
                    }
                }

                Assert.That(b[VectorLayout.ActiveBar], Is.EqualTo(a[VectorLayout.OppBar]));
                Assert.That(b[VectorLayout.OppBar], Is.EqualTo(a[VectorLayout.ActiveBar]));
                Assert.That(b[VectorLayout.ActiveOff], Is.EqualTo(a[VectorLayout.OppOff]));
                Assert.That(b[VectorLayout.OppOff], Is.EqualTo(a[VectorLayout.ActiveOff]));
                Assert.That(b[VectorLayout.ActivePip], Is.EqualTo(a[VectorLayout.OppPip]));
                Assert.That(b[VectorLayout.OppPip], Is.EqualTo(a[VectorLayout.ActivePip]));
                Assert.That(b[VectorLayout.ActiveEscaped], Is.EqualTo(a[VectorLayout.OppEscaped]));
                Assert.That(b[VectorLayout.OppEscaped], Is.EqualTo(a[VectorLayout.ActiveEscaped]));

                Assert.That(b[VectorLayout.CubeOwner], Is.EqualTo(-a[VectorLayout.CubeOwner]));
                Assert.That(b[VectorLayout.CubeValue], Is.EqualTo(a[VectorLayout.CubeValue]));
                Assert.That(b[VectorLayout.IsMoneyGame], Is.EqualTo(a[VectorLayout.IsMoneyGame]));
                Assert.That(b[VectorLayout.IsCrawford], Is.EqualTo(a[VectorLayout.IsCrawford]));
                Assert.That(b[VectorLayout.IsContact], Is.EqualTo(a[VectorLayout.IsContact]));

                for (int i = 0; i < VectorLayout.AwayBuckets; i++)
                {
                    Assert.That(b[VectorLayout.ActiveAwayOffset + i], Is.EqualTo(a[VectorLayout.OppAwayOffset + i]));
                    Assert.That(b[VectorLayout.OppAwayOffset + i], Is.EqualTo(a[VectorLayout.ActiveAwayOffset + i]));
                }
            }
        }        // ==================================================================
        // Madde 4: kesin değer / sınır testi (kırpmasız)
        // ==================================================================

        [Test]
        public void ExactValues_BarDensityPipCubeAway()
        {
            // Barda 3 taş -> 1.5
            var bar3 = VectorTestSupport.Custom(1, 0, 0, (0, 3), (12, 12), (1, -15));
            Assert.That(VectorTestSupport.Vec(bar3, 1)[VectorLayout.ActiveBar], Is.EqualTo(1.5f));

            // Barda 15 taş -> 7.5, pip = 375/167
            var bar15 = VectorTestSupport.Custom(1, 0, 0, (0, 15), (1, -15));
            float[] v15 = VectorTestSupport.Vec(bar15, 1);
            Assert.That(v15[VectorLayout.ActiveBar], Is.EqualTo(7.5f));
            Assert.That(v15[VectorLayout.ActivePip], Is.EqualTo(375f / 167f));

            // Hanede 8 taş -> yoğunluk 2.5
            var p8 = VectorTestSupport.Custom(1, 0, 0, (12, 8), (1, -15));
            VectorTestSupport.AssertPoint(VectorTestSupport.Vec(p8, 1), VectorLayout.ActiveOffset, 13, 8);

            // Hanede 15 taş -> yoğunluk 6.0
            var p15 = VectorTestSupport.Custom(1, 0, 0, (12, 15), (1, -15));
            VectorTestSupport.AssertPoint(VectorTestSupport.Vec(p15, 1), VectorLayout.ActiveOffset, 13, 15);

            // cubeValue = 128 -> CubeValue = 1.0 (doygunluk)
            var cube = new BackgammonState();
            cube.cubeValue = 128;
            cube.cubeOwner = 1;
            Assert.That(VectorTestSupport.Vec(cube, 1)[VectorLayout.CubeValue], Is.EqualTo(1f));
            Assert.That(VectorTestSupport.Vec(cube, 1)[VectorLayout.CubeOwner], Is.EqualTo(1f));
            Assert.That(VectorTestSupport.Vec(cube, -1)[VectorLayout.CubeOwner], Is.EqualTo(-1f));

            // away = 20 -> ActiveAway[7] = 1
            var away = new BackgammonState();
            away.matchLength = 25;
            away.whiteScore = 5;
            away.blackScore = 0;
            float[] va = VectorTestSupport.Vec(away, 1);
            Assert.That(va[VectorLayout.IsMoneyGame], Is.EqualTo(0f));
            for (int i = 0; i < VectorLayout.AwayBuckets; i++)
            {
                Assert.That(va[VectorLayout.ActiveAwayOffset + i], Is.EqualTo(i == 7 ? 1f : 0f), "ActiveAway[" + i + "]");
            }

            // away = 1 -> ActiveAway[0] = 1
            var away1 = new BackgammonState();
            away1.matchLength = 5;
            away1.whiteScore = 4;
            away1.blackScore = 0;
            float[] va1 = VectorTestSupport.Vec(away1, 1);
            Assert.That(va1[VectorLayout.ActiveAwayOffset + 0], Is.EqualTo(1f));
            Assert.That(va1[VectorLayout.OppAwayOffset + 4], Is.EqualTo(1f), "rakip away = 5 -> kova 4");
        }

        [Test]
        public void NoNaNOrInfinity_OnRandomPositions()
        {
            var rng = new Xoshiro256StarStar(0x0BADF00DUL);
            var s = new BackgammonState();
            var buf = new float[N];

            for (int i = 0; i < 2000; i++)
            {
                VectorTestSupport.RandomPosition(rng, s);
                BackgammonVectorizer.Vectorize(s, 1, buf);
                for (int k = 0; k < N; k++)
                {
                    Assert.That(float.IsFinite(buf[k]), Is.True, "i=" + i + " nöron " + k + " = " + buf[k]);
                }
            }
        }

        // ==================================================================
        // Madde 5: kayıpsız geri çözme
        // ==================================================================

        [Test]
        public void RoundTrip_Lossless_OnRandomPositions()
        {
            var rng = new Xoshiro256StarStar(0x10FF1E55UL);
            var s = new BackgammonState();
            var buf = new float[N];

            for (int i = 0; i < 100000; i++)
            {
                VectorTestSupport.RandomPosition(rng, s);
                int perspective = (rng.NextUInt() & 1u) == 0u ? 1 : -1;

                BackgammonVectorizer.Vectorize(s, perspective, buf);
                sbyte[] decoded = VectorTestSupport.DecodeBoard(buf, perspective, out int wOff, out int bOff);

                for (int p = 0; p < BackgammonState.BoardSize; p++)
                {
                    Assert.That(decoded[p], Is.EqualTo(s.board[p]),
                        "i=" + i + " p=" + perspective + " hane " + p);
                }

                Assert.That(wOff, Is.EqualTo((int)s.whiteBorneOff), "i=" + i + " whiteBorneOff");
                Assert.That(bOff, Is.EqualTo((int)s.blackBorneOff), "i=" + i + " blackBorneOff");
            }
        }

        // ==================================================================
        // Madde 6: kirli buffer
        // ==================================================================

        [Test]
        public void DirtyBuffer_All221Written_AndTailUntouched()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);

            var buf = new float[N + 10];
            for (int i = 0; i < buf.Length; i++)
            {
                buf[i] = float.NaN;
            }

            BackgammonVectorizer.Vectorize(s, 1, buf.AsSpan(0, N));

            for (int i = 0; i < N; i++)
            {
                Assert.That(float.IsFinite(buf[i]), Is.True, "nöron " + i + " yazılmamış");
            }

            for (int i = N; i < buf.Length; i++)
            {
                Assert.That(float.IsNaN(buf[i]), Is.True, "kuyruk elemanı " + i + " değiştirilmiş");
            }
        }

        [Test]
        public void ShortBuffer_Throws()
        {
            var s = new BackgammonState();
            Assert.Throws<ArgumentException>(() => BackgammonVectorizer.Vectorize(s, 1, new float[N - 1]));
            Assert.Throws<ArgumentException>(() => BackgammonVectorizer.Vectorize(s, 1, Array.Empty<float>()));
        }        // ==================================================================
        // Madde 7: yardımcı fonksiyonlar
        // ==================================================================

        [Test]
        public void PipCount_MatchesDefinition()
        {
            var start = new BackgammonState();
            Assert.That(BackgammonVectorizer.CalculatePipCount(start, 1), Is.EqualTo(167));
            Assert.That(BackgammonVectorizer.CalculatePipCount(start, -1), Is.EqualTo(167));

            // Bar taşı = 25.
            var bar = VectorTestSupport.Custom(1, 0, 0, (0, 15), (1, -15));
            Assert.That(BackgammonVectorizer.CalculatePipCount(bar, 1), Is.EqualTo(375));
            Assert.That(BackgammonVectorizer.CalculatePipCount(bar, -1), Is.EqualTo(15 * 1));

            // Siyah için aynalanmış.
            var black = VectorTestSupport.Custom(-1, 0, 0, (25, -15), (1, 15));
            Assert.That(BackgammonVectorizer.CalculatePipCount(black, -1), Is.EqualTo(375));
            Assert.That(BackgammonVectorizer.CalculatePipCount(black, 1), Is.EqualTo(15 * 24));
        }

        [Test]
        public void EscapedCheckers_MatchesDefinition()
        {
            // Saf yarış: Beyaz 19,20,21'de; Siyah 1,2,3'te. Karşılıklı geçiş tamamlanmış.
            var race = VectorTestSupport.Custom(1, 0, 0,
                (19, 5), (20, 5), (21, 5),
                (1, -5), (2, -5), (3, -5));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(race, 1), Is.EqualTo(15));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(race, -1), Is.EqualTo(15));

            // Rakip barda taş varsa jOppMin = 0 -> kaçak 0.
            var oppBar = VectorTestSupport.Custom(1, 0, 0, (19, 15), (25, -15));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(oppBar, 1), Is.EqualTo(0));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(oppBar, -1), Is.EqualTo(0));

            // Rakip tamamen toplanmışsa jOppMin = +inf -> tahtadaki tüm taşlar kaçak.
            var oppOff = VectorTestSupport.Custom(1, 0, 15, (19, 5), (20, 5), (21, 5));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(oppOff, 1), Is.EqualTo(15));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(oppOff, -1), Is.EqualTo(0));

            // Kısmi: Beyaz 24'te 1 (j=1), 1'de 14 (j=24); Siyah 12'de 15 (j=13).
            var partial = VectorTestSupport.Custom(1, 0, 0, (24, 1), (1, 14), (12, -15));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(partial, 1), Is.EqualTo(1));
            Assert.That(BackgammonVectorizer.GetEscapedCheckersCount(partial, -1), Is.EqualTo(0));
        }

        [Test]
        public void IsContact_MatchesDefinition()
        {
            var race = VectorTestSupport.Custom(1, 0, 0,
                (19, 5), (20, 5), (21, 5),
                (1, -5), (2, -5), (3, -5));
            Assert.That(BackgammonVectorizer.IsContact(race), Is.False);

            var oppBar = VectorTestSupport.Custom(1, 0, 0, (19, 15), (25, -15));
            Assert.That(BackgammonVectorizer.IsContact(oppBar), Is.True);

            var oppOff = VectorTestSupport.Custom(1, 0, 15, (19, 5), (20, 5), (21, 5));
            Assert.That(BackgammonVectorizer.IsContact(oppOff), Is.False);

            var start = new BackgammonState();
            Assert.That(BackgammonVectorizer.IsContact(start), Is.True);

            var m = new BackgammonState();
            BackgammonEngine.MirrorTo(race, m);
            Assert.That(BackgammonVectorizer.IsContact(m), Is.EqualTo(BackgammonVectorizer.IsContact(race)));
        }

        // ==================================================================
        // Madde 8: toplu giriş (Faz 1 v4 entegrasyonu)
        // ==================================================================

        [Test]
        public void Batch_MatchesPerRecordVectorize()
        {
            var rng = new Xoshiro256StarStar(0xBA7C45EEDUL);
            var s = new BackgammonState();
            var list = new AfterStateList();
            var es = EngineSettings.Default;
            var loaded = new BackgammonState();
            var single = new float[N];

            int checkedRecords = 0;

            for (int iter = 0; iter < 300; iter++)
            {
                VectorTestSupport.RandomPosition(rng, s);
                BackgammonEngine.SetDice(s, 1 + (int)(rng.NextUInt() % 6u), 1 + (int)(rng.NextUInt() % 6u));
                LegalMoveGenerator.GenerateAfterStates(s, es, list);

                if (list.Count == 0)
                {
                    continue;
                }

                int nonTerminal = PartitionNonTerminal(list);
                if (nonTerminal == 0)
                {
                    continue;
                }

                var scalars = VectorizerScalars.From(s);
                var batch = new float[nonTerminal * N];
                BackgammonVectorizer.VectorizeBatch(list, nonTerminal, s.turn, scalars, batch);

                for (int i = 0; i < nonTerminal; i++)
                {
                    loaded.CopyFrom(s);
                    BackgammonEngine.LoadAfterState(loaded, list, i);

                    // Kritik sıra (E5): LoadAfterState sonrası EndTurn ÇAĞRILMAZ.
                    BackgammonVectorizer.Vectorize(loaded, s.turn, single);

                    for (int k = 0; k < N; k++)
                    {
                        Assert.That(BitConverter.SingleToUInt32Bits(batch[i * N + k]),
                            Is.EqualTo(BitConverter.SingleToUInt32Bits(single[k])),
                            "iter " + iter + " kayıt " + i + " nöron " + k);
                    }

                    checkedRecords++;
                }
            }

            Assert.That(checkedRecords, Is.GreaterThan(1000), "karşılaştırılan kayıt sayısı");
        }

        [Test]
        public void Batch_TerminalRecord_Throws()
        {
            var list = new AfterStateList();
            var terminal = new BackgammonState();
            terminal.whiteBorneOff = 15;
            list.Add(terminal, default);

            var scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);
            Assert.Throws<ArgumentException>(
                () => BackgammonVectorizer.VectorizeBatch(list, 1, 1, scalars, new float[N]));
        }

        [Test]
        public void ScalarsFrom_MatchesState()
        {
            var s = new BackgammonState();
            s.cubeValue = 8;
            s.cubeOwner = -1;
            s.matchLength = 7;
            s.whiteScore = 3;
            s.blackScore = 5;
            s.isCrawfordGame = true;

            VectorizerScalars sc = VectorizerScalars.From(s);
            Assert.That(sc.CubeValue, Is.EqualTo(8));
            Assert.That(sc.CubeOwner, Is.EqualTo(-1));
            Assert.That(sc.MatchLength, Is.EqualTo(7));
            Assert.That(sc.WhiteScore, Is.EqualTo(3));
            Assert.That(sc.BlackScore, Is.EqualTo(5));
            Assert.That(sc.IsCrawfordGame, Is.True);
        }

        private static int PartitionNonTerminal(AfterStateList list)
        {
            int nonTerminal = 0;
            for (int i = 0; i < list.Count; i++)
            {
                if (!list.IsTerminal[i])
                {
                    if (nonTerminal != i)
                    {
                        list.Swap(nonTerminal, i);
                    }

                    nonTerminal++;
                }
            }

            return nonTerminal;
        }        // ==================================================================
        // Madde 9: terminal ve maç bitişi reddi
        // ==================================================================

        [Test]
        public void Terminal_Rejected_AllOverloads()
        {
            var s = VectorTestSupport.Custom(1, 15, 0, (1, -15));
            Assert.Throws<ArgumentException>(() => BackgammonVectorizer.Vectorize(s, 1, new float[N]));

            var board = new sbyte[BackgammonState.BoardSize];
            board[1] = 15;
            board[25] = -15;
            var sc = new VectorizerScalars(1, 0, 0, 0, 0, false);
            Assert.Throws<ArgumentException>(
                () => BackgammonVectorizer.Vectorize(board, 15, 0, sc, 1, new float[N]));
            Assert.Throws<ArgumentException>(
                () => BackgammonVectorizer.Vectorize(board, 0, 15, sc, 1, new float[N]));
        }

        [Test]
        public void MatchOver_Rejected()
        {
            var s = new BackgammonState();
            s.matchLength = 5;
            s.whiteScore = 5;
            s.blackScore = 0;
            Assert.Throws<ArgumentException>(() => BackgammonVectorizer.Vectorize(s, 1, new float[N]));

            var board = new sbyte[BackgammonState.BoardSize];
            board[1] = 15;
            board[25] = -15;
            Assert.Throws<ArgumentException>(
                () => BackgammonVectorizer.Vectorize(board, 0, 0, new VectorizerScalars(1, 0, 5, 5, 0, false), 1, new float[N]));
            Assert.Throws<ArgumentException>(
                () => BackgammonVectorizer.Vectorize(board, 0, 0, new VectorizerScalars(1, 0, 5, 0, 5, false), 1, new float[N]));
        }

        [Test]
        public void MoneyGame_NotRejected()
        {
            var s = new BackgammonState();
            s.matchLength = 0;
            s.whiteScore = 0;
            s.blackScore = 0;
            Assert.DoesNotThrow(() => BackgammonVectorizer.Vectorize(s, 1, new float[N]));
        }

        // ==================================================================
        // Madde 10: allocation
        // ==================================================================

        [Test]
        public void Allocation_ZeroBytes()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
            var buf = new float[N];
            var sc = VectorizerScalars.From(s);

            var list = new AfterStateList();
            BackgammonEngine.SetDice(s, 3, 5);
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);
            int nonTerminal = PartitionNonTerminal(list);
            Assert.That(nonTerminal, Is.GreaterThan(0));
            var batch = new float[nonTerminal * N];

            for (int i = 0; i < 20000; i++)
            {
                BackgammonVectorizer.Vectorize(s, 1, buf);
                BackgammonVectorizer.Vectorize(s.board, s.whiteBorneOff, s.blackBorneOff, sc, 1, buf);
                BackgammonVectorizer.VectorizeBatch(list, nonTerminal, 1, sc, batch);
            }

            long before = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < 10000; i++)
            {
                BackgammonVectorizer.Vectorize(s, 1, buf);
            }

            long afterState = GC.GetAllocatedBytesForCurrentThread();

            long beforeLight = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < 10000; i++)
            {
                BackgammonVectorizer.Vectorize(s.board, s.whiteBorneOff, s.blackBorneOff, sc, 1, buf);
            }

            long afterLight = GC.GetAllocatedBytesForCurrentThread();

            long beforeBatch = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < 10000; i++)
            {
                BackgammonVectorizer.VectorizeBatch(list, nonTerminal, 1, sc, batch);
            }

            long afterBatch = GC.GetAllocatedBytesForCurrentThread();

            Assert.That(afterState - before, Is.EqualTo(0), "Vectorize(state) allocation");
            Assert.That(afterLight - beforeLight, Is.EqualTo(0), "Vectorize(board) allocation");
            Assert.That(afterBatch - beforeBatch, Is.EqualTo(0), "VectorizeBatch allocation");
        }

        // ==================================================================
        // Madde 11: çapraz dil altın JSON
        // ==================================================================

        [Test]
        public void CrossLanguageGolden_FileMatches()
        {
            string path = Path.Combine(AppContext.BaseDirectory, VectorGoldenData.RelativePath);
            Assert.That(File.Exists(path), Is.True,
                "Altın dosya yok: " + path + " - VectorGoldenData.Write ile üretin.");

            using (JsonDocument doc = JsonDocument.Parse(File.ReadAllText(path)))
            {
                JsonElement root = doc.RootElement;
                Assert.That(root.GetProperty("featureVersion").GetInt32(),
                    Is.EqualTo(BackgammonVectorizer.FeatureVersion));
                Assert.That(root.GetProperty("vectorSize").GetInt32(),
                    Is.EqualTo(BackgammonVectorizer.InputVectorSize));

                JsonElement records = root.GetProperty("records");
                Assert.That(records.GetArrayLength(), Is.GreaterThanOrEqualTo(500));

                var board = new sbyte[BackgammonState.BoardSize];
                var buf = new float[N];
                int index = 0;

                foreach (JsonElement rec in records.EnumerateArray())
                {
                    JsonElement b = rec.GetProperty("board");
                    for (int p = 0; p < BackgammonState.BoardSize; p++)
                    {
                        board[p] = (sbyte)b[p].GetInt32();
                    }

                    var sc = new VectorizerScalars(
                        rec.GetProperty("cubeValue").GetInt32(),
                        rec.GetProperty("cubeOwner").GetInt32(),
                        rec.GetProperty("matchLength").GetInt32(),
                        rec.GetProperty("whiteScore").GetInt32(),
                        rec.GetProperty("blackScore").GetInt32(),
                        rec.GetProperty("isCrawfordGame").GetBoolean());

                    int perspective = rec.GetProperty("perspective").GetInt32();
                    BackgammonVectorizer.Vectorize(board, rec.GetProperty("whiteBorneOff").GetInt32(),
                        rec.GetProperty("blackBorneOff").GetInt32(), sc, perspective, buf);

                    string expected = rec.GetProperty("vectorHex").GetString()!;
                    string actual = VectorGoldenData.HexOf(buf);
                    Assert.That(actual, Is.EqualTo(expected), "kayıt " + index);
                    index++;
                }
            }
        }

        [Test]
        [Explicit("Altın JSON dosyasını yeniden üretir.")]
        public void GenerateCrossLanguageGolden()
        {
            string path = Path.Combine(AppContext.BaseDirectory, VectorGoldenData.RelativePath);
            VectorGoldenData.Write(path, VectorGoldenData.DefaultRecordCount, VectorGoldenData.DefaultSeed);
            TestContext.Progress.WriteLine("Yazıldı: " + path);
        }

        // ==================================================================
        // Madde 12: performans
        // ==================================================================

        [Test]
        public void Performance_VectorizeThroughput()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
            var buf = new float[N];

            for (int i = 0; i < 200000; i++)
            {
                BackgammonVectorizer.Vectorize(s, 1, buf);
            }

            const int iterations = 2000000;
            var sw = Stopwatch.StartNew();
            for (int i = 0; i < iterations; i++)
            {
                BackgammonVectorizer.Vectorize(s, 1, buf);
            }

            sw.Stop();
            double perSecond = iterations / sw.Elapsed.TotalSeconds;
            TestContext.Progress.WriteLine("Vectorize: " + perSecond.ToString("N0", CultureInfo.InvariantCulture) +
                                           " çağrı/sn (" + (sw.Elapsed.TotalMilliseconds * 1000.0 / iterations).ToString("F3") + " us)");
            AssertThroughput(perSecond, 2000000.0, "Vectorize");
        }

        [Test]
        public void Performance_VectorizeBatchThroughput()
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
            BackgammonEngine.SetDice(s, 3, 5);

            var list = new AfterStateList();
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);
            int nonTerminal = PartitionNonTerminal(list);
            Assert.That(nonTerminal, Is.GreaterThan(0));

            var sc = VectorizerScalars.From(s);
            var batch = new float[nonTerminal * N];

            for (int i = 0; i < 20000; i++)
            {
                BackgammonVectorizer.VectorizeBatch(list, nonTerminal, 1, sc, batch);
            }

            const int iterations = 200000;
            var sw = Stopwatch.StartNew();
            for (int i = 0; i < iterations; i++)
            {
                BackgammonVectorizer.VectorizeBatch(list, nonTerminal, 1, sc, batch);
            }

            sw.Stop();
            double recordsPerSecond = (double)iterations * nonTerminal / sw.Elapsed.TotalSeconds;
            TestContext.Progress.WriteLine("VectorizeBatch: " + recordsPerSecond.ToString("N0", CultureInfo.InvariantCulture) +
                                           " kayıt/sn (" + nonTerminal + " kayıt/çağrı)");
            AssertThroughput(recordsPerSecond, 2000000.0, "VectorizeBatch");
        }

        private static void AssertThroughput(double measured, double target, string what)
        {
#if DEBUG
            TestContext.Progress.WriteLine("[Debug] " + what + " eşiği atlandı (ölçülen " +
                                           measured.ToString("N0", CultureInfo.InvariantCulture) + ").");
#else
            Assert.That(measured, Is.GreaterThanOrEqualTo(target),
                what + " hedefin altında: " + measured.ToString("N0", CultureInfo.InvariantCulture) +
                " < " + target.ToString("N0", CultureInfo.InvariantCulture));
#endif
        }
    }
}