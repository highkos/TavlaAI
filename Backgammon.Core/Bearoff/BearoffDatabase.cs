using System;
using System.IO;
using System.IO.MemoryMappedFiles;

namespace Backgammon.Core
{
    /// <summary>
    /// 1 taraflı bearoff veritabanı okuyucusu (Faz 5 §3.2–3.4). Memory-mapped; dosya belleğe
    /// bütünüyle kopyalanmaz.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>İş parçacığı güvenliği:</b> sorgu metotları (<see cref="TryGetCdf"/>, <see cref="TryGetGammon"/>)
    /// örnek başına tek bir okuma tamponu kullanır; bu nedenle <b>tek iş parçacığından</b> çağrılmalıdır.
    /// Arama (Faz 3 v7) tek iş parçacıklıdır. Farklı örnekler birbirinden bağımsızdır.
    /// </para>
    /// <para>
    /// <b>Allocation:</b> <see cref="Open"/> dışında hiçbir metot heap allocation yapmaz.
    /// </para>
    /// </remarks>
    public sealed class BearoffDatabase : IDisposable
    {
        /// <summary>Dosya imzası: "TVB1".</summary>
        public const uint Magic = 0x31425654u; // 'T','V','B','1' küçük-endian

        /// <summary>Desteklenen format sürümü.</summary>
        public const ushort FormatVersion = 1;

        /// <summary>Başlık boyutu (bayt).</summary>
        public const int HeaderBytes = 64;

        private const int FlagGammon = 1;

        private MemoryMappedFile _file;
        private MemoryMappedViewAccessor _view;
        private byte[] _rowScratch;
        private byte[] _gammonScratch;
        private long _cdfOffset;
        private long _gammonOffset;
        private int _maxRolls;
        private bool _hasGammon;
        private int _version;

        private BearoffDatabase()
        {
        }

        /// <summary>Dosyadan açar. Başlık ve CRC doğrulanır; uyuşmazlıkta <see cref="InvalidDataException"/>.</summary>
        public static BearoffDatabase Open(string path)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            if (!File.Exists(path))
            {
                throw new FileNotFoundException("Bearoff veritabanı bulunamadı.", path);
            }

            var db = new BearoffDatabase();
            try
            {
                db._file = MemoryMappedFile.CreateFromFile(
                    path, FileMode.Open, null, 0, MemoryMappedFileAccess.Read);
                db._view = db._file.CreateViewAccessor(0, 0, MemoryMappedFileAccess.Read);
                db.ReadHeader();
                return db;
            }
            catch
            {
                db.Dispose();
                throw;
            }
        }

        /// <summary>Her sorguda <c>false</c> dönen boş veritabanı (testler ve DB yokken).</summary>
        public static BearoffDatabase OpenEmpty()
        {
            return new BearoffDatabase();
        }

        /// <summary>Dosya içeriğinden türetilen sabit sürüm. Boş DB için 0.</summary>
        public int Version
        {
            get { return _version; }
        }

        /// <summary>CDF tablosunun son tur indeksi.</summary>
        public int MaxRolls
        {
            get { return _maxRolls; }
        }

        /// <summary>Gammon tablosu var mı?</summary>
        public bool HasGammonData
        {
            get { return _hasGammon; }
        }

        /// <summary>Pozisyon sayısı (boş DB için 0).</summary>
        public int Positions
        {
            get { return _view == null ? 0 : BearoffIndex.Positions; }
        }

        // ------------------------------------------------------------------
        // Sorgular
        // ------------------------------------------------------------------

        /// <summary>
        /// <paramref name="player"/> tarafı 1 taraflı bearoff mı? Tüm taşları kendi ev bölgesindeki
        /// 1..6 hanesinde veya toplanmışsa <c>true</c>. Bar'da taş varsa <c>false</c>.
        /// </summary>
        /// <remarks>
        /// Rakibin <b>ev bölgesinde</b> taşı olmamalıdır: orada taş varsa pozisyon temastır ve
        /// tek taraflı bearoff tablosu geçersizdir. Ayrıca <see cref="ToCounts"/> ev bölgesini
        /// <c>byte</c>'a çevirdiği için negatif değerler sessizce bozulurdu.
        /// </remarks>
        public static bool IsOneSidedBearoff(ReadOnlySpan<sbyte> board, int player)
        {
            if (board.Length < BackgammonState.BoardSize)
            {
                throw new ArgumentException("board en az 26 eleman içermeli.", nameof(board));
            }

            if (player == 1)
            {
                if (board[0] != 0)
                {
                    return false;
                }

                for (int p = 1; p <= 18; p++)
                {
                    if (board[p] > 0)
                    {
                        return false;
                    }
                }

                for (int p = 19; p <= 24; p++)
                {
                    if (board[p] < 0)
                    {
                        return false;
                    }
                }

                return true;
            }

            if (player == -1)
            {
                if (board[25] != 0)
                {
                    return false;
                }

                for (int p = 7; p <= 24; p++)
                {
                    if (board[p] < 0)
                    {
                        return false;
                    }
                }

                for (int p = 1; p <= 6; p++)
                {
                    if (board[p] > 0)
                    {
                        return false;
                    }
                }

                return true;
            }

            throw new ArgumentException("player +1 veya -1 olmalı.", nameof(player));
        }

        /// <summary>
        /// Ham pozisyonu <c>counts[0..5]</c> biçimine çevirir (1-hane = toplanmaya en yakın).
        /// Çağıran <see cref="IsOneSidedBearoff"/> ile doğrulamalıdır.
        /// </summary>
        public static void ToCounts(ReadOnlySpan<sbyte> board, int player, Span<byte> counts)
        {
            if (counts.Length < BearoffIndex.Points)
            {
                throw new ArgumentException("counts en az 6 eleman içermeli.", nameof(counts));
            }

            if (player == 1)
            {
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    counts[i] = (byte)board[24 - i];
                }
            }
            else if (player == -1)
            {
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    counts[i] = (byte)(-board[i + 1]);
                }
            }
            else
            {
                throw new ArgumentException("player +1 veya -1 olmalı.", nameof(player));
            }
        }

        /// <summary>
        /// Kümülatif dağılım: <c>cdf[k] = P(en fazla k turda toplar)</c>, <c>k = 0..MaxRolls</c>.
        /// Pozisyon 1 taraflı bearoff değilse veya DB boşsa <c>false</c>.
        /// </summary>
        public bool TryGetCdf(ReadOnlySpan<sbyte> board, int player, Span<float> cdf)
        {
            if (_view == null)
            {
                return false;
            }

            if (cdf.Length < _maxRolls + 1)
            {
                throw new ArgumentException("cdf en az MaxRolls+1 eleman içermeli.", nameof(cdf));
            }

            if (!IsOneSidedBearoff(board, player))
            {
                return false;
            }

            Span<byte> counts = stackalloc byte[BearoffIndex.Points];
            ToCounts(board, player, counts);
            int rank = BearoffIndex.Rank(counts);

            int rowBytes = (_maxRolls + 1) * 2;
            _view.ReadArray(_cdfOffset + (long)rank * rowBytes, _rowScratch, 0, rowBytes);

            const float scale = 1f / 65535f;
            for (int k = 0; k <= _maxRolls; k++)
            {
                int u = _rowScratch[k * 2] | (_rowScratch[(k * 2) + 1] << 8);
                cdf[k] = u * scale;
            }

            return true;
        }

        /// <summary>
        /// Mars olasılıkları. Gammon tablosu yoksa <c>false</c>.
        /// </summary>
        public bool TryGetGammon(ReadOnlySpan<sbyte> board, int player,
                                 out float gammonWin, out float gammonLoss)
        {
            gammonWin = 0f;
            gammonLoss = 0f;

            if (_view == null || !_hasGammon)
            {
                return false;
            }

            if (!IsOneSidedBearoff(board, player))
            {
                return false;
            }

            Span<byte> counts = stackalloc byte[BearoffIndex.Points];
            ToCounts(board, player, counts);
            int rank = BearoffIndex.Rank(counts);

            _view.ReadArray(_gammonOffset + (long)rank * 4, _gammonScratch, 0, 4);

            const float scale = 1f / 65535f;
            gammonWin = (_gammonScratch[0] | (_gammonScratch[1] << 8)) * scale;
            gammonLoss = (_gammonScratch[2] | (_gammonScratch[3] << 8)) * scale;
            return true;
        }

        public void Dispose()
        {
            _view?.Dispose();
            _view = null;
            _file?.Dispose();
            _file = null;
            _rowScratch = null;
            _gammonScratch = null;
            _version = 0;
        }

        // ------------------------------------------------------------------
        // Başlık
        // ------------------------------------------------------------------

        private void ReadHeader()
        {
            long length = _view.Capacity;
            if (length < HeaderBytes)
            {
                throw new InvalidDataException("Bearoff dosyası başlık için çok kısa: " + length + " bayt.");
            }

            var header = new byte[HeaderBytes];
            _view.ReadArray(0, header, 0, HeaderBytes);

            uint magic = ReadU32(header, 0);
            if (magic != Magic)
            {
                throw new InvalidDataException("Bearoff magic uyuşmuyor: 0x" + magic.ToString("X8"));
            }

            ushort version = (ushort)(header[4] | (header[5] << 8));
            if (version != FormatVersion)
            {
                throw new InvalidDataException("Desteklenmeyen bearoff format sürümü: " + version);
            }

            if (header[6] != BearoffIndex.Points)
            {
                throw new InvalidDataException("points uyuşmuyor: " + header[6]);
            }

            if (header[7] != BearoffIndex.Checkers)
            {
                throw new InvalidDataException("checkers uyuşmuyor: " + header[7]);
            }

            uint positions = ReadU32(header, 8);
            if (positions != BearoffIndex.Positions)
            {
                throw new InvalidDataException("positions uyuşmuyor: " + positions);
            }

            int maxRolls = header[12];
            if (maxRolls < 1 || maxRolls > 64)
            {
                throw new InvalidDataException("maxRolls aralık dışı: " + maxRolls);
            }

            byte flags = header[13];
            bool hasGammon = (flags & FlagGammon) != 0;

            uint crc = ReadU32(header, 16);
            uint payloadBytes = ReadU32(header, 20);

            long expected = (long)BearoffIndex.Positions * (maxRolls + 1) * 2;
            if (hasGammon)
            {
                expected += (long)BearoffIndex.Positions * 2 * 2;
            }

            if (payloadBytes != expected)
            {
                throw new InvalidDataException(
                    "payloadBytes uyuşmuyor: " + payloadBytes + " (beklenen " + expected + ").");
            }

            if (length < HeaderBytes + payloadBytes)
            {
                throw new InvalidDataException(
                    "Dosya payload için çok kısa: " + length + " < " + (HeaderBytes + payloadBytes) + ".");
            }

            // CRC, payload'ın tamamı belleğe alınmadan parça parça hesaplanır (Faz 6'daki büyük
            // dosyalar için de aynı yol kullanılacak).
            const int ChunkBytes = 1 << 16;
            var chunk = new byte[ChunkBytes];
            uint state = BearoffCrc32.Begin();
            long remaining = payloadBytes;
            long position = HeaderBytes;
            while (remaining > 0)
            {
                int take = (int)(remaining < ChunkBytes ? remaining : ChunkBytes);
                _view.ReadArray(position, chunk, 0, take);
                state = BearoffCrc32.Update(state, new ReadOnlySpan<byte>(chunk, 0, take));
                position += take;
                remaining -= take;
            }

            uint actual = BearoffCrc32.End(state);
            if (actual != crc)
            {
                throw new InvalidDataException(
                    "payloadCrc32 uyuşmuyor: 0x" + actual.ToString("X8") + " != 0x" + crc.ToString("X8"));
            }

            _maxRolls = maxRolls;
            _hasGammon = hasGammon;
            _cdfOffset = HeaderBytes;
            _gammonOffset = HeaderBytes + ((long)BearoffIndex.Positions * (maxRolls + 1) * 2);
            _rowScratch = new byte[(maxRolls + 1) * 2];
            _gammonScratch = new byte[4];
            _version = unchecked((int)(crc ^ (positions * 2654435761u)));
        }

        private static uint ReadU32(byte[] buffer, int offset)
        {
            return (uint)(buffer[offset] |
                          (buffer[offset + 1] << 8) |
                          (buffer[offset + 2] << 16) |
                          (buffer[offset + 3] << 24));
        }
    }
}
