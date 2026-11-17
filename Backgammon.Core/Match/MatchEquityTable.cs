using System;
using System.Globalization;
using System.IO;
using System.Reflection;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.2: maç kazanma olasılığı (MWC) tablosu. <c>away ∈ [0, MaxMatchLength]</c>.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Veri kaynağı: gnubg 1.08.003 <c>met/Rockwell-Kazaross.xml</c>, <c>ml/extract_met.py</c> ile
    /// çıkarılıp <c>Match/met_rk.json</c> olarak <b>gömülü kaynak</b> hâline getirilmiştir.
    /// </para>
    /// <para>
    /// <b>Neden <c>System.Text.Json</c> yok?</b> <c>Backgammon.Core</c> <c>netstandard2.1</c>'dir ve
    /// Unity eklentisi olarak <b>tek DLL</b> hâlinde kopyalanır (Faz 5 §6). Dış JSON bağımlılığı
    /// Unity tarafını kırar. Bu yüzden gömülü kaynak, <b>yalnızca kendi ürettiğimiz biçimi</b> kabul
    /// eden küçük ve katı bir tarayıcı ile okunur; biçim bozulursa <see cref="InvalidDataException"/>.
    /// </para>
    /// </remarks>
    public sealed class MatchEquityTable
    {
        /// <summary>Varsayılan en büyük maç uzunluğu (gnubg RK MET 25 puana kadar).</summary>
        public const int DefaultMaxMatchLength = 25;

        private const string ResourceName = "Backgammon.Core.Match.met_rk.json";

        private readonly double[] _table;
        private readonly int _size;

        private static MatchEquityTable _default;

        /// <summary>Gömülü Rockwell-Kazaross tablosu (tembel, tek örnek).</summary>
        public static MatchEquityTable Default
        {
            get
            {
                MatchEquityTable table = _default;
                if (table == null)
                {
                    table = new MatchEquityTable(DefaultMaxMatchLength);
                    _default = table;
                }

                return table;
            }
        }

        /// <summary>Gömülü tablodan, en fazla <paramref name="maxMatchLength"/> puanlık maçlar için yükler.</summary>
        public MatchEquityTable(int maxMatchLength = DefaultMaxMatchLength)
        {
            if (maxMatchLength < 1)
            {
                throw new ArgumentOutOfRangeException(nameof(maxMatchLength));
            }

            double[] full;
            int fullLength;
            LoadEmbedded(out full, out fullLength);

            if (maxMatchLength > fullLength)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(maxMatchLength), "Gömülü MET en fazla " + fullLength + " puan destekler.");
            }

            _size = maxMatchLength + 1;
            _table = new double[_size * _size];
            for (int a = 0; a < _size; a++)
            {
                Array.Copy(full, a * (fullLength + 1), _table, a * _size, _size);
            }

            MaxMatchLength = maxMatchLength;
            Version = ComputeVersion(_table, _size);
        }

        /// <summary>Testler için: hazır tablodan oluşturur. <c>table[a * size + b] = MWC(a, b)</c>.</summary>
        public MatchEquityTable(double[] table, int maxMatchLength)
        {
            if (table == null)
            {
                throw new ArgumentNullException(nameof(table));
            }

            if (maxMatchLength < 1)
            {
                throw new ArgumentOutOfRangeException(nameof(maxMatchLength));
            }

            _size = maxMatchLength + 1;
            if (table.Length != _size * _size)
            {
                throw new ArgumentException("Tablo boyutu " + (_size * _size) + " olmalı.", nameof(table));
            }

            _table = (double[])table.Clone();
            MaxMatchLength = maxMatchLength;
            Version = ComputeVersion(_table, _size);
        }

        /// <summary>Desteklenen en büyük maç uzunluğu.</summary>
        public int MaxMatchLength { get; private set; }

        /// <summary>Tablo içeriğinden türetilen sürüm.</summary>
        public int Version { get; private set; }

        /// <summary>
        /// <paramref name="awayA"/> away olan oyuncunun maçı kazanma olasılığı.
        /// </summary>
        public double MatchWinningChance(int awayA, int awayB)
        {
            if (awayA < 0 || awayA > MaxMatchLength)
            {
                throw new ArgumentOutOfRangeException(nameof(awayA));
            }

            if (awayB < 0 || awayB > MaxMatchLength)
            {
                throw new ArgumentOutOfRangeException(nameof(awayB));
            }

            if (awayA == 0 && awayB == 0)
            {
                throw new ArgumentException("MWC(0, 0) tanımsızdır.");
            }

            return _table[(awayA * _size) + awayB];
        }

        /// <summary>Antisimetrik maç equity'si: <c>ME = 2·MWC − 1 ∈ [−1, +1]</c>.</summary>
        public double MatchEquity(int awayA, int awayB)
        {
            return (2.0 * MatchWinningChance(awayA, awayB)) - 1.0;
        }

        private static int ComputeVersion(double[] table, int size)
        {
            unchecked
            {
                uint h = 2166136261u;
                h = (h ^ (uint)size) * 16777619u;
                for (int i = 0; i < table.Length; i++)
                {
                    long bits = BitConverter.DoubleToInt64Bits(table[i]);
                    h = (h ^ (uint)bits) * 16777619u;
                    h = (h ^ (uint)(bits >> 32)) * 16777619u;
                }

                return (int)(h & 0x7FFFFFFFu);
            }
        }

        private static void LoadEmbedded(out double[] table, out int maxMatchLength)
        {
            Assembly assembly = typeof(MatchEquityTable).GetTypeInfo().Assembly;
            using (Stream stream = assembly.GetManifestResourceStream(ResourceName))
            {
                if (stream == null)
                {
                    throw new InvalidDataException("Gömülü MET kaynağı bulunamadı: " + ResourceName);
                }

                using (var reader = new StreamReader(stream))
                {
                    Parse(reader.ReadToEnd(), out table, out maxMatchLength);
                }
            }
        }

        /// <summary>
        /// <c>met_rk.json</c> biçimini okur. Yalnızca <c>maxMatchLength</c> tamsayısını ve
        /// <c>table</c> dizisindeki sayıları sırayla toplar; başka hiçbir alan yorumlanmaz.
        /// </summary>
        internal static void Parse(string json, out double[] table, out int maxMatchLength)
        {
            if (json == null)
            {
                throw new ArgumentNullException(nameof(json));
            }

            maxMatchLength = ReadIntField(json, "maxMatchLength");
            if (maxMatchLength < 1 || maxMatchLength > 64)
            {
                throw new InvalidDataException("maxMatchLength aralık dışı: " + maxMatchLength);
            }

            int start = IndexOfField(json, "table");
            int open = json.IndexOf('[', start);
            if (open < 0)
            {
                throw new InvalidDataException("MET 'table' dizisi bulunamadı.");
            }

            int expected = (maxMatchLength + 1) * (maxMatchLength + 1);
            table = new double[expected];
            int count = 0;
            int i = open + 1;
            while (i < json.Length)
            {
                char c = json[i];
                if (c == ']' && count >= expected)
                {
                    break;
                }

                if (c == '-' || c == '+' || c == '.' || (c >= '0' && c <= '9'))
                {
                    int end = i;
                    while (end < json.Length)
                    {
                        char d = json[end];
                        if (d == '-' || d == '+' || d == '.' || d == 'e' || d == 'E' || (d >= '0' && d <= '9'))
                        {
                            end++;
                        }
                        else
                        {
                            break;
                        }
                    }

                    if (count >= expected)
                    {
                        throw new InvalidDataException("MET tablosunda fazla sayı var.");
                    }

                    if (!double.TryParse(json.Substring(i, end - i), NumberStyles.Float,
                                         CultureInfo.InvariantCulture, out table[count]))
                    {
                        throw new InvalidDataException("MET tablosunda sayı okunamadı.");
                    }

                    count++;
                    i = end;
                    continue;
                }

                i++;
            }

            if (count != expected)
            {
                throw new InvalidDataException(
                    "MET tablosunda " + expected + " sayı bekleniyordu, " + count + " bulundu.");
            }
        }

        private static int IndexOfField(string json, string name)
        {
            int index = json.IndexOf("\"" + name + "\"", StringComparison.Ordinal);
            if (index < 0)
            {
                throw new InvalidDataException("MET alanı bulunamadı: " + name);
            }

            return index;
        }

        private static int ReadIntField(string json, string name)
        {
            int index = IndexOfField(json, name);
            int colon = json.IndexOf(':', index);
            if (colon < 0)
            {
                throw new InvalidDataException("MET alanı değeri yok: " + name);
            }

            int i = colon + 1;
            while (i < json.Length && (json[i] == ' ' || json[i] == '\t' || json[i] == '\r' || json[i] == '\n'))
            {
                i++;
            }

            int start = i;
            if (i < json.Length && (json[i] == '-' || json[i] == '+'))
            {
                i++;
            }

            int digits = i;
            while (i < json.Length && json[i] >= '0' && json[i] <= '9')
            {
                i++;
            }

            if (i == digits)
            {
                throw new InvalidDataException("MET alanı tamsayı değil: " + name);
            }

            return int.Parse(json.Substring(start, i - start), NumberStyles.Integer, CultureInfo.InvariantCulture);
        }
    }
}
