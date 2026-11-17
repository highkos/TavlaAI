using System;
using System.Security.Cryptography;

namespace Backgammon.Core
{
    /// <summary>
    /// Kriptografik rastgelelik. <c>PlayerVSInference</c> modu için isteğe bağlı.
    /// Bayt buffer'ı toplu doldurulur; zar başına allocation yapılmaz. Bölüm 3.
    /// </summary>
    public sealed class CryptoRandom : IRandom, IDisposable
    {
        private const int BufferSize = 256;

        private readonly RandomNumberGenerator _rng;
        private readonly byte[] _buffer;
        private int _index;

        public CryptoRandom()
        {
            _rng = RandomNumberGenerator.Create();
            _buffer = new byte[BufferSize];
            _index = BufferSize;
        }

        public uint NextUInt()
        {
            if (_index + 4 > BufferSize)
            {
                _rng.GetBytes(_buffer, 0, BufferSize);
                _index = 0;
            }

            uint value = (uint)(_buffer[_index]
                                | (_buffer[_index + 1] << 8)
                                | (_buffer[_index + 2] << 16)
                                | (_buffer[_index + 3] << 24));

            _index += 4;
            return value;
        }

        public int RollDie()
        {
            const uint Limit = uint.MaxValue - (uint.MaxValue % 6U);

            uint x;
            do
            {
                x = NextUInt();
            }
            while (x >= Limit);

            return (int)(x % 6U) + 1;
        }

        public void Dispose()
        {
            _rng.Dispose();
        }
    }
}
