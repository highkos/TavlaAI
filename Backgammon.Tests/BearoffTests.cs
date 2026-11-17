using System;
using System.Collections.Generic;
using System.IO;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 5 §8 Test 1–13: bearoff indeksi, veritabanı okuyucusu ve decorator değerlendirici.
    /// </summary>
    [TestFixture]
    public sealed class BearoffTests
    {
        private static readonly string ArtifactPath = Path.Combine(
            TestContext.CurrentContext.TestDirectory, "bearoff1_v1.bin");

        private static BearoffDatabase _database = null!;

        [OneTimeSetUp]
        public void OneTimeSetUp()
        {
            // Testler gerçek üretilmiş tabloyu kullanır; üretim ~6 s sürer.
            BearoffGenerator.Result result = BearoffGenerator.Generate(12);
            BearoffGenerator.Write(ArtifactPath, result);
            _database = BearoffDatabase.Open(ArtifactPath);
        }

        [OneTimeTearDown]
        public void OneTimeTearDown()
        {
            _database?.Dispose();
            _database = null!;

            if (File.Exists(ArtifactPath))
            {
                File.Delete(ArtifactPath);
            }
        }

        // ------------------------------------------------------------------
        // Test 1
        // ------------------------------------------------------------------

        [Test]
        public void BearoffIndex_RoundTrip()
        {
            var counts = new byte[BearoffIndex.Points];
            var back = new byte[BearoffIndex.Points];
            var seen = new bool[BearoffIndex.Positions];

            for (int rank = 0; rank < BearoffIndex.Positions; rank++)
            {
                BearoffIndex.Unrank(rank, back);

                int sum = 0;
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    sum += back[i];
                }

                Assert.That(sum, Is.LessThanOrEqualTo(BearoffIndex.Checkers),
                    "Unrank 15'ten fazla taş üretti (rank " + rank + ").");

                int again = BearoffIndex.Rank(back);
                Assert.That(again, Is.EqualTo(rank), "Round-trip başarısız (rank " + rank + ").");
                Assert.That(seen[again], Is.False, "Rank tekrar etti: " + again);
                seen[again] = true;
            }

            Assert.That(Array.TrueForAll(seen, v => v), Is.True, "Tüm rank'ler kapsanmadı.");
            Assert.That(BearoffIndex.Rank(counts), Is.EqualTo(0));
        }

        // ------------------------------------------------------------------
        // Test 2
        // ------------------------------------------------------------------

        [Test]
        public void BearoffIndex_Boundaries()
        {
            var counts = new byte[BearoffIndex.Points];

            // Hepsi toplanmış ⇒ 0.
            Assert.That(BearoffIndex.Rank(counts), Is.EqualTo(0));

            // Hepsi 1-hanede ⇒ 54263.
            counts[0] = 15;
            Assert.That(BearoffIndex.Rank(counts), Is.EqualTo(BearoffIndex.Positions - 1));

            // Elle hesaplanmış ara değerler: rank = Σ C(S_i + i, i + 1).
            Assert.That(BearoffIndex.Rank(new byte[] { 1, 0, 0, 0, 0, 0 }), Is.EqualTo(6));
            Assert.That(BearoffIndex.Rank(new byte[] { 0, 1, 0, 0, 0, 0 }), Is.EqualTo(5));
            Assert.That(BearoffIndex.Rank(new byte[] { 0, 0, 1, 0, 0, 0 }), Is.EqualTo(4));
            Assert.That(BearoffIndex.Rank(new byte[] { 0, 0, 0, 0, 0, 1 }), Is.EqualTo(1));
            Assert.That(BearoffIndex.Rank(new byte[] { 2, 0, 0, 0, 0, 0 }), Is.EqualTo(27));

            // Unrank sınırları.
            var back = new byte[BearoffIndex.Points];
            BearoffIndex.Unrank(0, back);
            Assert.That(back, Is.EqualTo(new byte[BearoffIndex.Points]));

            BearoffIndex.Unrank(BearoffIndex.Positions - 1, back);
            Assert.That(back[0], Is.EqualTo(15));
            Assert.That(back[1], Is.EqualTo(0));
        }

        // ------------------------------------------------------------------
        // Test 3
        // ------------------------------------------------------------------

        [Test]
        public void BearoffDatabase_HeaderValidation()
        {
            byte[] original = File.ReadAllBytes(ArtifactPath);
            string temp = Path.Combine(Path.GetTempPath(), "bearoff_hdr_" + Guid.NewGuid().ToString("N") + ".bin");

            try
            {
                AssertCorrupt(original, 0, 0xFF, temp, "magic");
                AssertCorrupt(original, 4, 0x02, temp, "version");
                AssertCorrupt(original, 6, 0x07, temp, "points");
                AssertCorrupt(original, 7, 0x0E, temp, "checkers");
                AssertCorrupt(original, 8, 0x01, temp, "positions");
                AssertCorrupt(original, 20, 0x01, temp, "payloadBytes");
                AssertCorrupt(original, 16, 0x01, temp, "payloadCrc32");
            }
            finally
            {
                if (File.Exists(temp))
                {
                    File.Delete(temp);
                }
            }
        }

        private static void AssertCorrupt(byte[] original, int offset, byte mask, string temp, string field)
        {
            var copy = (byte[])original.Clone();
            copy[offset] = (byte)(copy[offset] ^ mask);
            File.WriteAllBytes(temp, copy);

            Assert.Throws<InvalidDataException>(() =>
            {
                using (BearoffDatabase.Open(temp))
                {
                }
            }, field + " bozulması InvalidDataException üretmedi.");
        }

        // ------------------------------------------------------------------
        // Test 4
        // ------------------------------------------------------------------

        [Test]
        public void BearoffDatabase_MonotoneCdf()
        {
            const float Tolerance = 1f / 65535f;
            var counts = new byte[BearoffIndex.Points];
            var board = new sbyte[BackgammonState.BoardSize];
            var cdf = new float[_database.MaxRolls + 1];

            for (int rank = 0; rank < BearoffIndex.Positions; rank++)
            {
                BearoffIndex.Unrank(rank, counts);
                BuildBoard(counts, board);

                Assert.That(_database.TryGetCdf(board, 1, cdf), Is.True, "rank " + rank);
                Assert.That(cdf[0], Is.EqualTo(0f), "cdf[0] sıfır değil (rank " + rank + ").");

                for (int k = 1; k <= _database.MaxRolls; k++)
                {
                    Assert.That(cdf[k], Is.GreaterThanOrEqualTo(cdf[k - 1] - Tolerance),
                        "cdf monoton değil (rank " + rank + ", k " + k + ").");
                }

                Assert.That(cdf[_database.MaxRolls], Is.EqualTo(1f).Within(Tolerance),
                    "cdf[MaxRolls] 1 değil (rank " + rank + ").");
            }
        }

        // ------------------------------------------------------------------
        // Test 5
        // ------------------------------------------------------------------

        [Test]
        public void BearoffDatabase_KnownPositions()
        {
            const float Tolerance = 2f / 65535f;
            var cdf = new float[_database.MaxRolls + 1];

            // Değerler bağımsız Python referansından (ml/bearoff_ref.py --dump-known).
            AssertCdf(new byte[] { 1, 0, 0, 0, 0, 0 }, 1, 1.0, cdf, Tolerance);
            AssertCdf(new byte[] { 0, 0, 0, 0, 0, 1 }, 1, 27.0 / 36.0, cdf, Tolerance);
            AssertCdf(new byte[] { 0, 0, 0, 0, 0, 2 }, 1, 4.0 / 36.0, cdf, Tolerance);
            AssertCdf(new byte[] { 0, 0, 0, 0, 0, 2 }, 2, 0.782407, cdf, Tolerance);
            AssertCdf(new byte[] { 2, 0, 0, 0, 0, 0 }, 1, 1.0, cdf, Tolerance);
            AssertCdf(new byte[] { 15, 0, 0, 0, 0, 0 }, 1, 0.0, cdf, Tolerance);
            AssertCdf(new byte[] { 15, 0, 0, 0, 0, 0 }, 4, 0.000772, cdf, Tolerance);
            AssertCdf(new byte[] { 0, 0, 0, 0, 0, 15 }, 1, 0.0, cdf, Tolerance);
            AssertCdf(new byte[] { 0, 0, 0, 0, 0, 15 }, 6, 0.000284, cdf, Tolerance);
        }

        private static void AssertCdf(byte[] counts, int k, double expected, float[] cdf, float tolerance)
        {
            var board = new sbyte[BackgammonState.BoardSize];
            BuildBoard(counts, board);

            Assert.That(_database.TryGetCdf(board, 1, cdf), Is.True);
            Assert.That(cdf[k], Is.EqualTo((float)expected).Within(tolerance),
                "cdf[" + k + "] counts=" + string.Join(",", counts));
        }

        // ------------------------------------------------------------------
        // Test 6
        // ------------------------------------------------------------------

        [Test]
        public void BearoffDatabase_NoAllocation()
        {
            var counts = new byte[] { 3, 2, 1, 4, 0, 5 };
            var board = new sbyte[BackgammonState.BoardSize];
            BuildBoard(counts, board);
            var cdf = new float[_database.MaxRolls + 1];

            for (int i = 0; i < 100; i++)
            {
                _database.TryGetCdf(board, 1, cdf);
            }

            long before = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < 1000; i++)
            {
                _database.TryGetCdf(board, 1, cdf);
            }

            long after = GC.GetAllocatedBytesForCurrentThread();
            Assert.That(after - before, Is.EqualTo(0), "TryGetCdf allocation yaptı.");
        }

        // ------------------------------------------------------------------
        // Test 6b
        // ------------------------------------------------------------------

        [Test]
        public void BearoffDatabase_RejectsContactPositions()
        {
            var cdf = new float[_database.MaxRolls + 1];
            var board = new sbyte[BackgammonState.BoardSize];

            // Beyaz tamamen ev bolgesinde, siyah da ayni bolgede => temas, tablo gecersiz.
            BuildBoard(new byte[] { 5, 5, 5, 0, 0, 0 }, board);
            board[1] = 0;
            board[19] = -3;
            board[2] = -12;

            Assert.That(BearoffDatabase.IsOneSidedBearoff(board, 1), Is.False,
                "rakip ev bolgesinde tas varken tek tarafli bearoff kabul edilmemeli.");
            Assert.That(_database.TryGetCdf(board, 1, cdf), Is.False);
            Assert.That(_database.TryGetGammon(board, 1, out _, out _), Is.False);

            // Ayni pozisyon siyah icin de gecersiz (beyaz 1..6'da).
            Assert.That(BearoffDatabase.IsOneSidedBearoff(board, -1), Is.False);

            // Rakip disarida ise gecerli.
            board[19] = 0;
            board[2] = -15;
            Assert.That(BearoffDatabase.IsOneSidedBearoff(board, 1), Is.True);
            Assert.That(_database.TryGetCdf(board, 1, cdf), Is.True);
        }

        // ------------------------------------------------------------------
        // Test 7
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_OverwritesBearoffResults()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
                var list = new AfterStateList(8);

                // Kayıt 0: Beyaz 1 taş 1-hanede (14 toplanmış), Siyah 15 taş 1-hanede.
                // Sırada Siyah; Beyaz her zarla toplar ⇒ kesin kazanç.
                AddBoard(list, new byte[] { 1, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 });

                // Kayıt 1: tersi ⇒ kesin kayıp.
                AddBoard(list, new byte[] { 15, 0, 0, 0, 0, 0 }, new byte[] { 1, 0, 0, 0, 0, 0 });

                // Kayıt 2: Beyaz'ın 12-hanede taşı var ⇒ 1 taraflı bearoff değil, iç değer korunur.
                AddBoard(list, new byte[] { 0, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 }, 12);

                var results = new float[list.Count];
                evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), results);

                Assert.That(inner.EvaluateCalls, Is.EqualTo(1), "İç değerlendirici bir kez çağrılmalı.");

                Assert.That(results[0], Is.EqualTo(1f).Within(1e-4f), "Kayıt 0 kesin kazanç olmalı.");
                Assert.That(results[1], Is.EqualTo(-1f).Within(1e-4f), "Kayıt 1 kesin kayıp olmalı.");

                var innerOnly = new float[list.Count];
                inner.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), innerOnly);
                Assert.That(BitConverter.SingleToInt32Bits(results[2]),
                    Is.EqualTo(BitConverter.SingleToInt32Bits(innerOnly[2])),
                    "Bearoff olmayan kayıt iç değerlendiriciden gelmeli.");
            }
        }

        // ------------------------------------------------------------------
        // Test 8
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_PureBearoffSkipsInner()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var options = new BearoffAwareOptions
                {
                    SkipInnerForPureBearoffBatches = true,
                    DisableBearoff = false
                };

                var evaluator = new BearoffAwareEvaluator(inner, db, options);
                var list = new AfterStateList(4);
                AddBoard(list, new byte[] { 1, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 });
                AddBoard(list, new byte[] { 15, 0, 0, 0, 0, 0 }, new byte[] { 1, 0, 0, 0, 0, 0 });

                var results = new float[list.Count];
                evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), results);

                Assert.That(inner.EvaluateCalls, Is.EqualTo(0), "Saf bearoff partisinde iç çağrı olmamalı.");
                Assert.That(results[0], Is.EqualTo(1f).Within(1e-4f));
                Assert.That(results[1], Is.EqualTo(-1f).Within(1e-4f));
            }
        }

        // ------------------------------------------------------------------
        // Test 9
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_DisableIsIdentity()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var options = new BearoffAwareOptions
                {
                    SkipInnerForPureBearoffBatches = true,
                    DisableBearoff = true
                };

                var evaluator = new BearoffAwareEvaluator(inner, db, options);
                var list = new AfterStateList(4);
                AddBoard(list, new byte[] { 1, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 });
                AddBoard(list, new byte[] { 15, 0, 0, 0, 0, 0 }, new byte[] { 1, 0, 0, 0, 0, 0 });

                var expected = new float[list.Count];
                inner.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), expected);

                var actual = new float[list.Count];
                evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), actual);

                for (int i = 0; i < list.Count; i++)
                {
                    Assert.That(BitConverter.SingleToInt32Bits(actual[i]),
                        Is.EqualTo(BitConverter.SingleToInt32Bits(expected[i])),
                        "DisableBearoff bit düzeyinde aynı olmalı (kayıt " + i + ").");
                }
            }
        }

        // ------------------------------------------------------------------
        // Test 10
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_VersionComposition()
        {
            var innerA = new FakeEvaluator { VersionValue = 7 };
            var innerB = new FakeEvaluator { VersionValue = 8 };

            using (var dbA = BearoffDatabase.Open(ArtifactPath))
            using (var dbB = BearoffDatabase.OpenEmpty())
            {
                var a = new BearoffAwareEvaluator(innerA, dbA, BearoffAwareOptions.Default);
                var b = new BearoffAwareEvaluator(innerB, dbA, BearoffAwareOptions.Default);
                var c = new BearoffAwareEvaluator(innerA, dbB, BearoffAwareOptions.Default);

                Assert.That(a.Version, Is.Not.EqualTo(b.Version), "Farklı iç model ⇒ farklı Version.");
                Assert.That(a.Version, Is.Not.EqualTo(c.Version), "Farklı DB ⇒ farklı Version.");
                Assert.That(dbA.Version, Is.Not.EqualTo(0));
                Assert.That(dbB.Version, Is.EqualTo(0));
            }
        }

        // ------------------------------------------------------------------
        // Test 11
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_ZeroAllocation()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
                var list = new AfterStateList(4);
                AddBoard(list, new byte[] { 1, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 });
                AddBoard(list, new byte[] { 15, 0, 0, 0, 0, 0 }, new byte[] { 1, 0, 0, 0, 0, 0 });
                var results = new float[list.Count];

                for (int i = 0; i < 100; i++)
                {
                    evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), results);
                }

                long before = GC.GetAllocatedBytesForCurrentThread();
                for (int i = 0; i < 1000; i++)
                {
                    evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), results);
                }

                long after = GC.GetAllocatedBytesForCurrentThread();
                Assert.That(after - before, Is.EqualTo(0), "EvaluateBatch allocation yaptı.");
            }
        }

        // ------------------------------------------------------------------
        // Test 12
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_ContractViolations()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
                var list = new AfterStateList(4);
                AddBoard(list, new byte[] { 1, 0, 0, 0, 0, 0 }, new byte[] { 15, 0, 0, 0, 0, 0 });
                var results = new float[4];

                Assert.Throws<ArgumentException>(() =>
                    evaluator.EvaluateBatch(list, 1, 1, 1, default(VectorizerScalars), results));

                // count == 0 ⇒ sessizce döner.
                Assert.DoesNotThrow(() =>
                    evaluator.EvaluateBatch(list, 0, 0, 1, default(VectorizerScalars), results));

                // Terminal kayıt ⇒ ArgumentException.
                var terminal = new AfterStateList(2);
                AddTerminal(terminal);
                Assert.Throws<ArgumentException>(() =>
                    evaluator.EvaluateBatch(terminal, 0, 1, 1, default(VectorizerScalars), results));
            }
        }

        // ------------------------------------------------------------------
        // Test 13
        // ------------------------------------------------------------------

        [Test]
        public void BearoffAwareEvaluator_Determinism()
        {
            var inner = new FakeEvaluator();
            using (var db = BearoffDatabase.Open(ArtifactPath))
            {
                var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
                var list = new AfterStateList(4);
                AddBoard(list, new byte[] { 3, 1, 0, 2, 0, 9 }, new byte[] { 0, 0, 1, 0, 0, 14 });
                AddBoard(list, new byte[] { 15, 0, 0, 0, 0, 0 }, new byte[] { 1, 0, 0, 0, 0, 0 });

                var first = new float[list.Count];
                var second = new float[list.Count];
                evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), first);
                evaluator.EvaluateBatch(list, 0, list.Count, 1, default(VectorizerScalars), second);

                for (int i = 0; i < list.Count; i++)
                {
                    Assert.That(BitConverter.SingleToInt32Bits(second[i]),
                        Is.EqualTo(BitConverter.SingleToInt32Bits(first[i])));
                }
            }
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static void BuildBoard(byte[] counts, sbyte[] board)
        {
            Array.Clear(board, 0, board.Length);
            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                board[24 - i] = (sbyte)counts[i];
            }

            board[1] = -15;
        }

        private static void AddBoard(AfterStateList list, byte[] whiteCounts, byte[] blackCounts,
                                     int whiteExtraPoint = 0)
        {
            var state = new BackgammonState();
            state.Reset();
            Array.Clear(state.board, 0, BackgammonState.BoardSize);

            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                state.board[24 - i] = (sbyte)whiteCounts[i];
                state.board[i + 1] = (sbyte)(-blackCounts[i]);
            }

            if (whiteExtraPoint != 0)
            {
                state.board[whiteExtraPoint] = 1;
            }

            state.turn = 1;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            var seq = default(MoveSequence);
            seq.Clear();
            list.Add(state, seq);
        }

        private static void AddTerminal(AfterStateList list)
        {
            var state = new BackgammonState();
            state.Reset();
            Array.Clear(state.board, 0, BackgammonState.BoardSize);
            state.whiteBorneOff = BackgammonState.PiecesPerPlayer;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            var seq = default(MoveSequence);
            seq.Clear();
            list.Add(state, seq);
        }

        /// <summary>Deterministik sahte değerlendirici; çağrı sayısını izler.</summary>
        private sealed class FakeEvaluator : IPolicyValueEvaluator, ICombinedBatchEvaluator
        {
            public int EvaluateCalls;
            public int ScoreCalls;
            public int VersionValue = 1;

            public int Version
            {
                get { return VersionValue; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                EvaluateCalls++;
                for (int i = offset; i < offset + count; i++)
                {
                    results[i] = Pseudo(list, i, perspective);
                }
            }

            public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> priorities)
            {
                ScoreCalls++;
                float total = 0f;
                for (int i = offset; i < offset + count; i++)
                {
                    priorities[i] = 1f + (i * 0.5f);
                    total += priorities[i];
                }

                for (int i = offset; i < offset + count; i++)
                {
                    priorities[i] /= total;
                }
            }

            public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                              in VectorizerScalars scalars, Span<float> results,
                                              Span<float> priorities)
            {
                EvaluateBatch(list, offset, count, perspective, scalars, results);
                ScoreBatch(list, offset, count, perspective, scalars, priorities);
            }

            private static float Pseudo(AfterStateList list, int index, int perspective)
            {
                int sum = 0;
                int offset = index * AfterStateList.BoardSize;
                for (int k = 0; k < AfterStateList.BoardSize; k++)
                {
                    sum += list.Boards[offset + k] * (k + 1);
                }

                return ((sum * perspective) % 100) / 100f;
            }
        }
    }
}
