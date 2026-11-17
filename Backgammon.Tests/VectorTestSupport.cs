using System;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Faz 2 vektörleştirici testleri için ortak yardımcılar.</summary>
    internal static class VectorTestSupport
    {
        public const int N = BackgammonVectorizer.InputVectorSize;

        public static BackgammonState Custom(int turn, int whiteOff, int blackOff,
                                             params (int point, int value)[] pieces)
        {
            var s = new BackgammonState();
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            foreach (var (point, value) in pieces)
            {
                s.board[point] = (sbyte)value;
            }

            s.whiteBorneOff = (byte)whiteOff;
            s.blackBorneOff = (byte)blackOff;
            s.turn = (sbyte)turn;
            s.phase = GamePhase.PreRoll;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        /// <summary>
        /// Geçerli (15 taş/oyuncu), terminal olmayan, maç bitmemiş rastgele pozisyon üretir.
        /// Bar, toplanan, küp, skor ve Crawford rastgeleleştirilir.
        /// </summary>
        public static void RandomPosition(IRandom rng, BackgammonState s)
        {
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            int wOff = (int)(rng.NextUInt() % 15u);
            int bOff = (int)(rng.NextUInt() % 15u);
            s.whiteBorneOff = (byte)wOff;
            s.blackBorneOff = (byte)bOff;

            Distribute(rng, s.board, 1, 15 - wOff);
            Distribute(rng, s.board, -1, 15 - bOff);

            s.turn = (rng.NextUInt() & 1u) == 0u ? (sbyte)1 : (sbyte)-1;
            s.cubeValue = 1 << (int)(rng.NextUInt() % 7u);
            s.cubeOwner = (sbyte)((int)(rng.NextUInt() % 3u) - 1);

            if (rng.NextUInt() % 3u == 0u)
            {
                s.matchLength = 0;
                s.whiteScore = 0;
                s.blackScore = 0;
                s.isCrawfordGame = false;
            }
            else
            {
                s.matchLength = 1 + (int)(rng.NextUInt() % 25u);
                s.whiteScore = (int)(rng.NextUInt() % (uint)s.matchLength);
                s.blackScore = (int)(rng.NextUInt() % (uint)s.matchLength);
                s.isCrawfordGame = rng.NextUInt() % 4u == 0u;
                if (s.isCrawfordGame)
                {
                    s.cubeValue = 1;
                    s.cubeOwner = 0;
                }
            }

            s.crawfordPlayed = false;
            s.cubePassed = false;
            s.phase = GamePhase.PreRoll;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
        }

        /// <summary>Taşları bar (0 veya 25) ve 1..24 hanelerine rastgele dağıtır.</summary>
        public static void Distribute(IRandom rng, sbyte[] board, int sign, int count)
        {
            int lo = sign > 0 ? 0 : 1;
            int hi = sign > 0 ? 24 : 25;
            int span = hi - lo + 1;

            for (int i = 0; i < count; i++)
            {
                int slot = lo + (int)(rng.NextUInt() % (uint)span);
                board[slot] = (sbyte)(board[slot] + sign);
            }
        }

        public static float[] Vec(BackgammonState s, int perspective)
        {
            var v = new float[N];
            BackgammonVectorizer.Vectorize(s, perspective, v);
            return v;
        }

        public static float[] VecBoard(sbyte[] board, int wOff, int bOff,
                                       in VectorizerScalars sc, int perspective)
        {
            var v = new float[N];
            BackgammonVectorizer.Vectorize(board, wOff, bOff, sc, perspective, v);
            return v;
        }

        public static uint[] Bits(float[] v)
        {
            var b = new uint[v.Length];
            for (int i = 0; i < v.Length; i++)
            {
                b[i] = BitConverter.SingleToUInt32Bits(v[i]);
            }

            return b;
        }

        public static void AssertBitEqual(float[] a, float[] b, string message = "")
        {
            Assert.That(a.Length, Is.EqualTo(b.Length), message + " uzunluk");
            for (int i = 0; i < a.Length; i++)
            {
                uint ba = BitConverter.SingleToUInt32Bits(a[i]);
                uint bb = BitConverter.SingleToUInt32Bits(b[i]);
                if (ba != bb)
                {
                    Assert.Fail(message + " nöron " + i + ": " + a[i].ToString("R") + " (0x" + ba.ToString("x8") +
                                ") != " + b[i].ToString("R") + " (0x" + bb.ToString("x8") + ")");
                }
            }
        }

        public static void AssertPoint(float[] v, int blockOffset, int j, int n)
        {
            int b = blockOffset + VectorLayout.PointBlockSize * (j - 1);
            Assert.That(v[b + VectorLayout.Blot], Is.EqualTo(n == 1 ? 1f : 0f), "blot j=" + j);
            Assert.That(v[b + VectorLayout.Gate], Is.EqualTo(n >= 2 ? 1f : 0f), "kapi j=" + j);
            Assert.That(v[b + VectorLayout.ThreePlus], Is.EqualTo(n >= 3 ? 1f : 0f), "3+ j=" + j);
            Assert.That(v[b + VectorLayout.Density], Is.EqualTo(n > 3 ? (n - 3) / 2f : 0f), "yogunluk j=" + j);
        }

        /// <summary>Bloktaki tüm nöronları doğrular: yalnızca verilen (j, n) çiftleri dolu olmalı.</summary>
        public static void AssertBlockOnly(float[] v, int blockOffset, params (int j, int n)[] points)
        {
            var expected = new float[VectorLayout.Points * VectorLayout.PointBlockSize];
            foreach (var (j, n) in points)
            {
                int b = VectorLayout.PointBlockSize * (j - 1);
                expected[b + VectorLayout.Blot] = n == 1 ? 1f : 0f;
                expected[b + VectorLayout.Gate] = n >= 2 ? 1f : 0f;
                expected[b + VectorLayout.ThreePlus] = n >= 3 ? 1f : 0f;
                expected[b + VectorLayout.Density] = n > 3 ? (n - 3) / 2f : 0f;
            }

            for (int i = 0; i < expected.Length; i++)
            {
                Assert.That(v[blockOffset + i], Is.EqualTo(expected[i]),
                    "blok " + blockOffset + " nöron " + i + " (j=" + (i / 4 + 1) + ", k=" + (i % 4) + ")");
            }
        }

        /// <summary>Vektörden board'u ve borneOff'ları kayıpsız geri kurar (Bölüm 5 madde 5).</summary>
        public static sbyte[] DecodeBoard(float[] v, int perspective, out int whiteOff, out int blackOff)
        {
            var board = new sbyte[BackgammonState.BoardSize];

            int activeBar = (int)MathF.Round(v[VectorLayout.ActiveBar] * 2f);
            int oppBar = (int)MathF.Round(v[VectorLayout.OppBar] * 2f);
            int activeOff = (int)MathF.Round(v[VectorLayout.ActiveOff] * 15f);
            int oppOff = (int)MathF.Round(v[VectorLayout.OppOff] * 15f);

            board[BackgammonEngine.BarIndex(perspective)] = (sbyte)(perspective * activeBar);
            board[BackgammonEngine.BarIndex(-perspective)] = (sbyte)(-perspective * oppBar);

            for (int point = 1; point <= 24; point++)
            {
                int j = BackgammonEngine.DistanceToOff(point, perspective);
                int ab = VectorLayout.ActiveOffset + VectorLayout.PointBlockSize * (j - 1);
                int ob = VectorLayout.OppOffset + VectorLayout.PointBlockSize * (j - 1);

                int activeN = DecodeCount(v[ab + VectorLayout.Blot], v[ab + VectorLayout.Gate],
                                          v[ab + VectorLayout.ThreePlus], v[ab + VectorLayout.Density]);
                int oppN = DecodeCount(v[ob + VectorLayout.Blot], v[ob + VectorLayout.Gate],
                                       v[ob + VectorLayout.ThreePlus], v[ob + VectorLayout.Density]);

                board[point] = (sbyte)(perspective * (activeN - oppN));
            }

            if (perspective == 1)
            {
                whiteOff = activeOff;
                blackOff = oppOff;
            }
            else
            {
                whiteOff = oppOff;
                blackOff = activeOff;
            }

            return board;
        }

        public static int DecodeCount(float f0, float f1, float f2, float f3)
        {
            if (f0 == 1f)
            {
                return 1;
            }

            if (f1 == 0f)
            {
                return 0;
            }

            if (f2 == 0f)
            {
                return 2;
            }

            if (f3 == 0f)
            {
                return 3;
            }

            return 3 + (int)MathF.Round(2f * f3);
        }
    }
}