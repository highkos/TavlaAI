namespace Backgammon.Core
{
    /// <summary>
    /// Zobrist anahtar tabloları. Bölüm 2.1 / 4.3.
    /// </summary>
    /// <remarks>
    /// Tablolar düz (flat) dizilerdir; hot path'te ek bir referans takibi yapılmaz.
    /// Tüm anahtarlar sabit bir SplitMix64 seed'inden deterministik olarak üretilir; böylece
    /// hash değerleri platformdan ve çalıştırmadan bağımsızdır.
    /// </remarks>
    internal static class Zobrist
    {
        public const int BoardValueMin = -15;
        public const int BoardValueMax = 15;
        public const int BoardValueCount = BoardValueMax - BoardValueMin + 1;

        public const int BorneOffCount = 16;
        public const int CubeExponentCount = 32;
        public const int CubeOwnerCount = 3;

        private const ulong Seed = 0x9E3779B97F4A7C15UL;

        /// <summary>[point * BoardValueCount + (value - BoardValueMin)]</summary>
        private static readonly ulong[] BoardKeys;

        private static readonly ulong[] WhiteOffKeys;
        private static readonly ulong[] BlackOffKeys;
        private static readonly ulong[] CubeValueKeys;
        private static readonly ulong[] CubeOwnerKeys;

        public static readonly ulong TurnKey;

        static Zobrist()
        {
            ulong state = Seed;

            BoardKeys = new ulong[BackgammonState.BoardSize * BoardValueCount];
            for (int i = 0; i < BoardKeys.Length; i++)
            {
                BoardKeys[i] = Next(ref state);
            }

            WhiteOffKeys = new ulong[BorneOffCount];
            for (int i = 0; i < WhiteOffKeys.Length; i++)
            {
                WhiteOffKeys[i] = Next(ref state);
            }

            BlackOffKeys = new ulong[BorneOffCount];
            for (int i = 0; i < BlackOffKeys.Length; i++)
            {
                BlackOffKeys[i] = Next(ref state);
            }

            CubeValueKeys = new ulong[CubeExponentCount];
            for (int i = 0; i < CubeValueKeys.Length; i++)
            {
                CubeValueKeys[i] = Next(ref state);
            }

            CubeOwnerKeys = new ulong[CubeOwnerCount];
            for (int i = 0; i < CubeOwnerKeys.Length; i++)
            {
                CubeOwnerKeys[i] = Next(ref state);
            }

            TurnKey = Next(ref state);
        }

        public static ulong BoardKey(int point, int value)
        {
            return BoardKeys[(point * BoardValueCount) + (value - BoardValueMin)];
        }

        public static ulong WhiteOffKey(int borneOff)
        {
            return WhiteOffKeys[borneOff];
        }

        public static ulong BlackOffKey(int borneOff)
        {
            return BlackOffKeys[borneOff];
        }

        public static ulong CubeValueKey(int cubeValue)
        {
            return CubeValueKeys[Log2(cubeValue)];
        }

        public static ulong CubeOwnerKey(int cubeOwner)
        {
            return CubeOwnerKeys[cubeOwner + 1];
        }

        /// <summary>2'nin kuvveti olan değerin üssü (1 -> 0, 2 -> 1, 4 -> 2 ...).</summary>
        public static int Log2(int value)
        {
            int exponent = 0;
            int v = value;
            while ((v >>= 1) != 0)
            {
                exponent++;
            }

            return exponent;
        }

        private static ulong Next(ref ulong state)
        {
            state += Seed;
            ulong z = state;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }
    }
}
