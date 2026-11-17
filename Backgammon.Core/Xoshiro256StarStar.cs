namespace Backgammon.Core
{
    /// <summary>
    /// Xoshiro256** üreteci. Seed'lenebilir, thread başına bir instance, tekrarlanabilir.
    /// Bölüm 3.
    /// </summary>
    public sealed class Xoshiro256StarStar : IRandom
    {
        private ulong _s0;
        private ulong _s1;
        private ulong _s2;
        private ulong _s3;

        public Xoshiro256StarStar(ulong seed)
        {
            ulong state = seed;
            _s0 = SplitMix64(ref state);
            _s1 = SplitMix64(ref state);
            _s2 = SplitMix64(ref state);
            _s3 = SplitMix64(ref state);

            // Tümü sıfır durum geçersizdir; pratikte imkânsız ama garantiye alalım.
            if ((_s0 | _s1 | _s2 | _s3) == 0)
            {
                _s0 = 1;
            }
        }

        public uint NextUInt()
        {
            ulong result = RotateLeft(_s1 * 5UL, 7) * 9UL;

            ulong t = _s1 << 17;
            _s2 ^= _s0;
            _s3 ^= _s1;
            _s1 ^= _s2;
            _s0 ^= _s3;
            _s2 ^= t;
            _s3 = RotateLeft(_s3, 45);

            return (uint)(result >> 32);
        }

        public int RollDie()
        {
            // Rejection sampling: 2^32'yi 6'ya tam bölünebilen aralığa kırp.
            const uint Limit = uint.MaxValue - (uint.MaxValue % 6U);

            uint x;
            do
            {
                x = NextUInt();
            }
            while (x >= Limit);

            return (int)(x % 6U) + 1;
        }

        private static ulong RotateLeft(ulong x, int k)
        {
            return (x << k) | (x >> (64 - k));
        }

        private static ulong SplitMix64(ref ulong state)
        {
            state += 0x9E3779B97F4A7C15UL;
            ulong z = state;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }
    }
}
