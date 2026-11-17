using System;

namespace Backgammon.Core
{
    /// <summary>
    /// CRC-32/ISO-HDLC (yansıtılmış, polinom 0xEDB88320, ilk değer 0xFFFFFFFF, son XOR 0xFFFFFFFF).
    /// Faz 5 §3.2: <c>bearoff1_v1.bin</c> payload bütünlük denetimi.
    /// </summary>
    public static class BearoffCrc32
    {
        private static readonly uint[] Table = BuildTable();

        private static uint[] BuildTable()
        {
            var table = new uint[256];
            for (uint i = 0; i < 256; i++)
            {
                uint c = i;
                for (int k = 0; k < 8; k++)
                {
                    c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
                }

                table[i] = c;
            }

            return table;
        }

        /// <summary>Artımlı hesap için başlangıç durumu.</summary>
        public static uint Begin()
        {
            return 0xFFFFFFFFu;
        }

        /// <summary>Artımlı hesaba bir parça ekler.</summary>
        public static uint Update(uint state, ReadOnlySpan<byte> data)
        {
            uint crc = state;
            for (int i = 0; i < data.Length; i++)
            {
                crc = Table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
            }

            return crc;
        }

        /// <summary>Artımlı hesabı bitirir.</summary>
        public static uint End(uint state)
        {
            return state ^ 0xFFFFFFFFu;
        }

        /// <summary><paramref name="data"/> üzerinde CRC-32 hesaplar.</summary>
        public static uint Compute(ReadOnlySpan<byte> data)
        {
            return End(Update(Begin(), data));
        }
    }
}
