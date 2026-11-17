using System;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 2 v4 Bölüm 5 madde 11: çapraz dil altın JSON'unun üretim betiği.
    /// </summary>
    /// <remarks>
    /// Şema (FeatureVersion = 1):
    /// <code>
    /// {
    ///   "featureVersion": 1,
    ///   "vectorSize": 221,
    ///   "generatedBy": "Faz 2 v4 test suite",
    ///   "records": [
    ///     { "board": [26 int], "whiteBorneOff": int, "blackBorneOff": int,
    ///       "cubeValue": int, "cubeOwner": int, "matchLength": int,
    ///       "whiteScore": int, "blackScore": int, "isCrawfordGame": bool,
    ///       "perspective": int, "vectorHex": "221 uint32 hex, virgülle ayrılmış" }
    ///   ]
    /// }
    /// </code>
    /// <c>vectorHex</c> her elemanı 8 haneli küçük harf onaltılık <c>uint32</c> bit desenidir
    /// (<c>BitConverter.SingleToUInt32Bits</c>). Faz 4'teki Python (numpy float32) tarafı aynı
    /// dosyayla birebir eşleşmeyi doğrular.
    /// </remarks>
    internal static class VectorGoldenData
    {
        public const string RelativePath = "ReferenceData/vector_golden.json";
        public const int DefaultRecordCount = 500;
        public const ulong DefaultSeed = 0x2F2600D_5EEDUL;

        public static string Build(int recordCount, ulong seed)
        {
            var rng = new Xoshiro256StarStar(seed);
            var s = new BackgammonState();
            var buf = new float[VectorTestSupport.N];

            using (var ms = new MemoryStream())
            {
                using (var w = new Utf8JsonWriter(ms, new JsonWriterOptions { Indented = true }))
                {
                    w.WriteStartObject();
                    w.WriteNumber("featureVersion", BackgammonVectorizer.FeatureVersion);
                    w.WriteNumber("vectorSize", BackgammonVectorizer.InputVectorSize);
                    w.WriteString("generatedBy", "Faz 2 v4 test suite");
                    w.WriteStartArray("records");

                    for (int i = 0; i < recordCount; i++)
                    {
                        VectorTestSupport.RandomPosition(rng, s);
                        int perspective = (rng.NextUInt() & 1u) == 0u ? 1 : -1;
                        BackgammonVectorizer.Vectorize(s, perspective, buf);

                        w.WriteStartObject();

                        w.WriteStartArray("board");
                        for (int p = 0; p < BackgammonState.BoardSize; p++)
                        {
                            w.WriteNumberValue(s.board[p]);
                        }

                        w.WriteEndArray();

                        w.WriteNumber("whiteBorneOff", s.whiteBorneOff);
                        w.WriteNumber("blackBorneOff", s.blackBorneOff);
                        w.WriteNumber("cubeValue", s.cubeValue);
                        w.WriteNumber("cubeOwner", s.cubeOwner);
                        w.WriteNumber("matchLength", s.matchLength);
                        w.WriteNumber("whiteScore", s.whiteScore);
                        w.WriteNumber("blackScore", s.blackScore);
                        w.WriteBoolean("isCrawfordGame", s.isCrawfordGame);
                        w.WriteNumber("perspective", perspective);
                        w.WriteString("vectorHex", HexOf(buf));

                        w.WriteEndObject();
                    }

                    w.WriteEndArray();
                    w.WriteEndObject();
                }

                return Encoding.UTF8.GetString(ms.ToArray());
            }
        }

        public static string HexOf(float[] v)
        {
            var sb = new StringBuilder(v.Length * 9);
            for (int i = 0; i < v.Length; i++)
            {
                if (i > 0)
                {
                    sb.Append(',');
                }

                sb.Append(BitConverter.SingleToUInt32Bits(v[i]).ToString("x8", CultureInfo.InvariantCulture));
            }

            return sb.ToString();
        }

        public static void Write(string path, int recordCount, ulong seed)
        {
            string? dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            File.WriteAllText(path, Build(recordCount, seed), new UTF8Encoding(false));
        }
    }
}