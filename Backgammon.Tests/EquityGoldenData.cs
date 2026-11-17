using System;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 7 Bölüm 9.9 (Test 122, 123): C#/Python equity paritesinin **tek doğruluk
    /// kaynağı** olan altın dosyanın üreticisi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Sorun.</b> Test 53 (Faz 6) Python formülünü elle yazılmış bir beklentiyle
    /// karşılaştırıyordu; C# tarafı ayrı bir testle kendi beklentisiyle. İki taraf
    /// <b>hiçbir zaman aynı girdiyi görmez</b>. Formül iki tarafta birlikte değişirse
    /// hiçbir test kırmızı yanmaz (F6-31/F6-32 sınıfı sessiz hata).
    /// </para>
    /// <para>
    /// <b>Çözüm.</b> Tek altın dosya, iki tüketici. <c>vector_golden.json</c> deseninin
    /// aynısı; tek fark, equity <c>double</c> olduğu için bit deseninin <b>16</b> haneli
    /// olması (<c>BitConverter.DoubleToUInt64Bits</c>).
    /// </para>
    /// <para>
    /// <b>Neden <c>exclusiveHex</c> de var.</b> <see cref="OutcomeDistribution"/> iç
    /// alanları <c>float</c>'tır; <c>Equity</c> ise <c>double</c> döner. Ondalık yazım
    /// yuvarlama kaybı riski taşıdığı için girdi ve çıktı float'ları da 8 haneli onaltılık
    /// bit deseni olarak yazılır. Python tarafı girdiyi <b>bit düzeyinde</b> okur ve aynı
    /// float32 boru hattını çalıştırır; böylece <c>atol = 0</c> mümkün olur.
    /// </para>
    /// <para>
    /// <b>Kayıt grupları (toplam 300).</b>
    /// <list type="table">
    /// <item><term>unit (6)</term><description>Birim vektörler; <c>E</c> tam olarak ±1, ±2, ±3.</description></item>
    /// <item><term>random (250)</term><description>Rastgele normalize vektörler.</description></item>
    /// <item><term>boundary (20)</term><description>Kütlesi tek sınıfta toplanmış vektörler + 2 tam eşitlik.</description></item>
    /// <item><term>unnormalized (20)</term><description>Toplamı 1 olmayan vektörler; <c>FromProbabilities</c> normalize eder.</description></item>
    /// <item><term>invalid (4)</term><description>Toplam 0, negatif, NaN, +Inf → <c>IsValid == false</c>.</description></item>
    /// </list>
    /// </para>
    /// </remarks>
    internal static class EquityGoldenData
    {
        public const string RelativePath = "ReferenceData/equity_golden.json";
        public const int SchemaVersion = 1;
        public const int DefaultRecordCount = 300;
        public const ulong DefaultSeed = 0x7E9_1_7_2026UL;
        public const string GeneratedBy = "Faz 7 Asama A test suite";

        public const int UnitCount = 6;
        public const int RandomCount = 250;
        public const int BoundaryCount = 20;
        public const int UnnormalizedCount = 20;
        public const int InvalidCount = 4;

        public static readonly string[] ProbOrder = { "W", "GW", "BW", "L", "GL", "BL" };

        public static readonly double[] EquityWeights = { 1.0, 2.0, 3.0, -1.0, -2.0, -3.0 };

        public static string Build(ulong seed)
        {
            var rng = new Xoshiro256StarStar(seed);

            using (var ms = new MemoryStream())
            {
                using (var w = new Utf8JsonWriter(ms, new JsonWriterOptions { Indented = true }))
                {
                    w.WriteStartObject();
                    w.WriteNumber("schemaVersion", SchemaVersion);
                    w.WriteString("generatedBy", GeneratedBy);
                    w.WriteNumber("recordCount", DefaultRecordCount);

                    w.WriteStartArray("probOrder");
                    foreach (string name in ProbOrder)
                    {
                        w.WriteStringValue(name);
                    }

                    w.WriteEndArray();

                    w.WriteStartArray("equityWeights");
                    foreach (double weight in EquityWeights)
                    {
                        w.WriteNumberValue(weight);
                    }

                    w.WriteEndArray();

                    w.WriteStartArray("records");

                    WriteUnitRecords(w);
                    WriteRandomRecords(w, rng);
                    WriteBoundaryRecords(w);
                    WriteUnnormalizedRecords(w, rng);
                    WriteInvalidRecords(w);

                    w.WriteEndArray();
                    w.WriteEndObject();
                }

                return Encoding.UTF8.GetString(ms.ToArray());
            }
        }

        private static void WriteUnitRecords(Utf8JsonWriter w)
        {
            for (int i = 0; i < UnitCount; i++)
            {
                var p = new float[6];
                p[i] = 1f;
                WriteRecord(w, "unit", i, p);
            }
        }

        private static void WriteRandomRecords(Utf8JsonWriter w, Xoshiro256StarStar rng)
        {
            for (int i = 0; i < RandomCount; i++)
            {
                var raw = new double[6];
                double sum = 0.0;
                for (int k = 0; k < 6; k++)
                {
                    raw[k] = NextDouble(rng);
                    sum += raw[k];
                }

                var p = new float[6];
                for (int k = 0; k < 6; k++)
                {
                    p[k] = (float)(raw[k] / sum);
                }

                WriteRecord(w, "random", i, p);
            }
        }

        private static void WriteBoundaryRecords(Utf8JsonWriter w)
        {
            double[] deltas = { 0.0, 1e-6, 0.05 };
            int index = 0;
            for (int c = 0; c < 6; c++)
            {
                foreach (double d in deltas)
                {
                    var p = new float[6];
                    for (int k = 0; k < 6; k++)
                    {
                        p[k] = k == c ? (float)(1.0 - 5.0 * d) : (float)d;
                    }

                    WriteRecord(w, "boundary", index++, p);
                }
            }

            WriteRecord(w, "boundary", index++, new float[] { 0.25f, 0.25f, 0.25f, 0.25f, 0f, 0f });
            WriteRecord(w, "boundary", index, new float[] { 0f, 0f, 0f, 0.5f, 0.25f, 0.25f });
        }

        private static void WriteUnnormalizedRecords(Utf8JsonWriter w, Xoshiro256StarStar rng)
        {
            double[] scales = { 0.25, 7.5, 100.0, 1e-3, 1e3 };
            int index = 0;
            for (int i = 0; i < 4; i++)
            {
                var raw = new double[6];
                for (int k = 0; k < 6; k++)
                {
                    raw[k] = NextDouble(rng);
                }

                foreach (double scale in scales)
                {
                    var p = new float[6];
                    for (int k = 0; k < 6; k++)
                    {
                        p[k] = (float)(raw[k] * scale);
                    }

                    WriteRecord(w, "unnormalized", index++, p);
                }
            }
        }

        private static void WriteInvalidRecords(Utf8JsonWriter w)
        {
            WriteRecord(w, "invalid", 0, new float[] { 0f, 0f, 0f, 0f, 0f, 0f });
            WriteRecord(w, "invalid", 1, new float[] { -0.1f, 0.4f, 0.1f, 0.2f, 0.1f, 0.1f });
            WriteRecord(w, "invalid", 2, new float[] { float.NaN, 0.2f, 0.2f, 0.2f, 0.2f, 0.2f });
            WriteRecord(w, "invalid", 3, new float[] { float.PositiveInfinity, 0.2f, 0.2f, 0.2f, 0.2f, 0.2f });
        }

        private static void WriteRecord(Utf8JsonWriter w, string group, int index, float[] p)
        {
            OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                p[0], p[1], p[2], p[3], p[4], p[5]);

            w.WriteStartObject();
            w.WriteString("group", group);
            w.WriteNumber("index", index);

            w.WriteStartArray("exclusive");
            foreach (float v in p)
            {
                if (float.IsNaN(v) || float.IsInfinity(v))
                {
                    w.WriteNullValue();
                }
                else
                {
                    w.WriteNumberValue(v);
                }
            }

            w.WriteEndArray();

            w.WriteStartArray("exclusiveHex");
            foreach (float v in p)
            {
                w.WriteStringValue(HexOfFloat(v));
            }

            w.WriteEndArray();

            w.WriteStartObject("cumulative");
            w.WriteNumber("win", d.Win);
            w.WriteNumber("winGammon", d.WinGammon);
            w.WriteNumber("winBackgammon", d.WinBackgammon);
            w.WriteNumber("loseGammon", d.LoseGammon);
            w.WriteNumber("loseBackgammon", d.LoseBackgammon);
            w.WriteEndObject();

            w.WriteStartObject("cumulativeHex");
            w.WriteString("win", HexOfFloat(d.Win));
            w.WriteString("winGammon", HexOfFloat(d.WinGammon));
            w.WriteString("winBackgammon", HexOfFloat(d.WinBackgammon));
            w.WriteString("loseGammon", HexOfFloat(d.LoseGammon));
            w.WriteString("loseBackgammon", HexOfFloat(d.LoseBackgammon));
            w.WriteEndObject();

            w.WriteNumber("equity", d.Equity);
            w.WriteString("equityHex", HexOfDouble(d.Equity));
            w.WriteBoolean("isValid", d.IsValid);

            w.WriteEndObject();
        }

        public static string HexOfDouble(double v)
        {
            return BitConverter.DoubleToUInt64Bits(v).ToString("x16", CultureInfo.InvariantCulture);
        }

        public static string HexOfFloat(float v)
        {
            return BitConverter.SingleToUInt32Bits(v).ToString("x8", CultureInfo.InvariantCulture);
        }

        public static float FloatFromHex(string hex)
        {
            return BitConverter.UInt32BitsToSingle(
                uint.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture));
        }

        public static double DoubleFromHex(string hex)
        {
            return BitConverter.UInt64BitsToDouble(
                ulong.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture));
        }

        private static double NextDouble(Xoshiro256StarStar rng)
        {
            ulong hi = rng.NextUInt();
            ulong lo = rng.NextUInt();
            return ((hi << 32) | lo) / 18446744073709551616.0;
        }

        public static void Write(string path, ulong seed)
        {
            string? dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            File.WriteAllText(path, Build(seed), new UTF8Encoding(false));
        }
    }
}
