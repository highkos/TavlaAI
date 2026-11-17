using System;
using System.IO;
using System.Text;

namespace Backgammon.SelfPlay
{
    /// <summary>Faz 4 v3 Bolum 5.4: shard ikili bicimi sabitleri.</summary>
    public static class ShardConstants
    {
        /// <summary>Dosya sihirli sayisi: <c>"BGSP"</c>.</summary>
        public static readonly byte[] Magic = { (byte)'B', (byte)'G', (byte)'S', (byte)'P' };

        /// <summary>Bicim surumu.</summary>
        public const uint FormatVersion = 1;

        /// <summary>Baslik boyutu (bayt).</summary>
        public const int HeaderSize = 32;

        /// <summary>Vektor boyutu (Faz 2 v4).</summary>
        public const int VectorSize = 221;

        /// <summary>Ham dosya uzantisi.</summary>
        public const string Extension = ".bgsp";

        /// <summary>Gzip'li dosya uzantisi.</summary>
        public const string GzipExtension = ".bgsp.gz";
    }

    /// <summary>Oyun kaydi <c>flags</c> bitleri.</summary>
    [Flags]
    public enum ShardGameFlags : byte
    {
        /// <summary>Bayrak yok.</summary>
        None = 0,

        /// <summary>Oyun <c>max_plies</c> nedeniyle kesildi; egitimde kullanilmaz.</summary>
        Aborted = 1,
    }

    /// <summary>Karar kaydi <c>flags</c> bitleri.</summary>
    [Flags]
    public enum ShardDecisionFlags : byte
    {
        /// <summary>Bayrak yok.</summary>
        None = 0,

        /// <summary>Yasal hamle yoktu; karar bir "pas" afterstate'idir.</summary>
        IsPass = 1,

        /// <summary>Bu karari ogrenen ag verdi (deger/politika kaybi hesaplanir).</summary>
        IsLearner = 2,

        /// <summary>Secilen aday terminal (vektor yazilmaz).</summary>
        ChosenIsTerminal = 4,

        /// <summary>
        /// Faz 6 Bolum 7.5: karar <c>dup_cap</c> nedeniyle egitimden cikarildi.
        /// <see cref="IsLearner"/> temizlenir; karar yalnizca TD zinciri halkasi olarak kalir.
        /// </summary>
        DupCapped = 8,

        /// <summary>
        /// Faz 7 Bolum 5.4 / Test 100: karar bir <b>damitma</b> ogretmeninden geldi.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <c>q</c> alani ogretmen aramasinin aday equity'lerini tasir; <c>searchValue</c>
        /// ogretmenin kok degeridir. <b>Bicim degismez</b>: v1 okuyucusu bu biti
        /// <b>bilinmeyen bayrak</b> olarak yok sayar (Test 100).
        /// </para>
        /// <para>
        /// <see cref="IsLearner"/> ile <b>birlikte</b> kullanilir: damitma karari hem
        /// ogrenilen hem damitilmis olabilir.
        /// </para>
        /// </remarks>
        Distilled = 16,
    }

    /// <summary>Faz 4 v3 Bolum 5.4: 32 baytlik dosya basligi.</summary>
    public struct ShardHeader
    {
        /// <summary>Bicim surumu.</summary>
        public uint FormatVersion;

        /// <summary>Faz 2 v4 <c>FeatureVersion</c>.</summary>
        public uint FeatureVersion;

        /// <summary>Vektor boyutu (221).</summary>
        public uint VectorSize;

        /// <summary>Model surumu.</summary>
        public uint ModelVersion;

        /// <summary>Karar basina loglanan en fazla aday sayisi (0 = tumu).</summary>
        public uint LogTopCandidates;

        /// <summary>Ayrilmis bayraklar.</summary>
        public uint Flags;

        /// <summary>Ayrilmis alan.</summary>
        public uint Reserved;

        /// <summary>Varsayilan baslik.</summary>
        public static ShardHeader Create(uint featureVersion, uint modelVersion, uint logTopCandidates)
        {
            return new ShardHeader
            {
                FormatVersion = ShardConstants.FormatVersion,
                FeatureVersion = featureVersion,
                VectorSize = ShardConstants.VectorSize,
                ModelVersion = modelVersion,
                LogTopCandidates = logTopCandidates,
                Flags = 0,
                Reserved = 0,
            };
        }

        /// <summary>Basligi akisa yazar (little-endian, 32 bayt).</summary>
        public void WriteTo(Stream stream)
        {
            if (stream == null)
            {
                throw new ArgumentNullException(nameof(stream));
            }

            stream.Write(ShardConstants.Magic, 0, ShardConstants.Magic.Length);
            WriteU32(stream, FormatVersion);
            WriteU32(stream, FeatureVersion);
            WriteU32(stream, VectorSize);
            WriteU32(stream, ModelVersion);
            WriteU32(stream, LogTopCandidates);
            WriteU32(stream, Flags);
            WriteU32(stream, Reserved);
        }

        /// <summary>Basligi akistan okur ve dogrular.</summary>
        /// <exception cref="InvalidDataException">Sihirli sayi, surum veya vektor boyutu uyumsuz.</exception>
        public static ShardHeader ReadFrom(Stream stream)
        {
            if (stream == null)
            {
                throw new ArgumentNullException(nameof(stream));
            }

            byte[] magic = new byte[4];
            ReadExactly(stream, magic, 0, 4);
            for (int i = 0; i < 4; i++)
            {
                if (magic[i] != ShardConstants.Magic[i])
                {
                    throw new InvalidDataException("Shard sihirli sayisi 'BGSP' degil.");
                }
            }

            var header = new ShardHeader
            {
                FormatVersion = ReadU32(stream),
                FeatureVersion = ReadU32(stream),
                VectorSize = ReadU32(stream),
                ModelVersion = ReadU32(stream),
                LogTopCandidates = ReadU32(stream),
                Flags = ReadU32(stream),
                Reserved = ReadU32(stream),
            };

            if (header.FormatVersion != ShardConstants.FormatVersion)
            {
                throw new InvalidDataException(
                    "Shard formatVersion desteklenmiyor: " + header.FormatVersion);
            }

            if (header.VectorSize != ShardConstants.VectorSize)
            {
                throw new InvalidDataException(
                    "Shard vectorSize uyumsuz: " + header.VectorSize);
            }

            return header;
        }

        internal static void WriteU32(Stream stream, uint value)
        {
            stream.WriteByte((byte)value);
            stream.WriteByte((byte)(value >> 8));
            stream.WriteByte((byte)(value >> 16));
            stream.WriteByte((byte)(value >> 24));
        }

        internal static uint ReadU32(Stream stream)
        {
            int b0 = stream.ReadByte();
            int b1 = stream.ReadByte();
            int b2 = stream.ReadByte();
            int b3 = stream.ReadByte();
            if (b3 < 0)
            {
                throw new EndOfStreamException("Shard beklenmedik sekilde bitti.");
            }

            return (uint)(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24));
        }

        internal static void ReadExactly(Stream stream, byte[] buffer, int offset, int count)
        {
            int read = 0;
            while (read < count)
            {
                int n = stream.Read(buffer, offset + read, count - read);
                if (n <= 0)
                {
                    throw new EndOfStreamException("Shard beklenmedik sekilde bitti.");
                }

                read += n;
            }
        }
    }
}