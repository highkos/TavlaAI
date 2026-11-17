using System;
using System.Collections.Generic;
using System.IO;
using Backgammon.Core;
using Backgammon.Inference;

namespace Backgammon.Inference.Tests
{
    /// <summary>Faz 4 v3 Asama A: test yardimcilari.</summary>
    internal static class InferenceTestSupport
    {
        public const string ModelFileName = "model_v1.onnx";
        public const string ParityFileName = "model_v1.onnx.parity.json";
        public const string GoldenOutputsFileName = "golden_outputs.json";

        /// <summary>Test cikti dizinindeki model yolu.</summary>
        public static string ModelPath
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", ModelFileName); }
        }

        /// <summary>
        /// <c>output_version = 2</c> test modeli (6 cikti dagilimi uretir).
        /// Faz 7 §5.4 damitma testleri bunu kullanir.
        /// </summary>
        public static string V2ModelPath
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_output_version_2.onnx"); }
        }

        public static string ParityPath
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", ParityFileName); }
        }

        public static string GoldenOutputsPath
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", GoldenOutputsFileName); }
        }

        /// <summary>Depo kokunu bulur (TavlaAI_Project.slnx iceren dizin).</summary>
        public static string RepoRoot()
        {
            var dir = new DirectoryInfo(TestContext.CurrentContext.TestDirectory);
            while (dir != null)
            {
                if (File.Exists(Path.Combine(dir.FullName, "TavlaAI_Project.slnx")))
                {
                    return dir.FullName;
                }

                dir = dir.Parent;
            }

            throw new DirectoryNotFoundException("Depo koku bulunamadi (TavlaAI_Project.slnx).");
        }

        public static string MlArtifactsDir
        {
            get { return Path.Combine(RepoRoot(), "ml", "artifacts"); }
        }

        public static OnnxModelHandle LoadModel()
        {
            return OnnxModelHandle.Load(ModelPath, OnnxEvaluatorOptions.Default);
        }

        /// <summary>Para oyunu baslangic pozisyonu + verilen zarlar.</summary>
        public static BackgammonState NewPosition(int d1, int d2, int turn = 1)
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
            s.turn = (sbyte)turn;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            BackgammonEngine.SetDice(s, d1, d2);
            return s;
        }

        /// <summary>
        /// Afterstate listesini uretir ve terminal-olmayanlari basa bolumler.
        /// </summary>
        /// <returns>Terminal-olmayan kayit sayisi.</returns>
        public static int BuildNonTerminalPrefix(BackgammonState s, AfterStateList list, out int total)
        {
            list.Clear();
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);
            total = list.Count;

            int nonTerminal = 0;
            for (int i = 0; i < list.Count; i++)
            {
                if (!list.IsTerminal[i])
                {
                    if (i != nonTerminal)
                    {
                        list.Swap(i, nonTerminal);
                    }

                    nonTerminal++;
                }
            }

            return nonTerminal;
        }

        /// <summary>Deterministik, gercekci bir vektor uretir (vektorlestirici uzerinden).</summary>
        public static void VectorizeAt(AfterStateList list, int index, int perspective, Span<float> dst)
        {
            var scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);

            BackgammonVectorizer.Vectorize(
                list.BoardOf(index),
                list.WhiteBorneOff[index],
                list.BlackBorneOff[index],
                in scalars,
                perspective,
                dst);
        }

        /// <summary>float32 bit desenini 8 haneli hex olarak yazar (parite dosyasi bicimi).</summary>
        public static string FloatToHex(float value)
        {
            return BitConverter.SingleToUInt32Bits(value).ToString("x8");
        }

        public static float HexToFloat(string hex)
        {
            return BitConverter.UInt32BitsToSingle(Convert.ToUInt32(hex, 16));
        }

        public static float[] HexToVector(string hex)
        {
            string[] parts = hex.Split(',');
            var result = new float[parts.Length];
            for (int i = 0; i < parts.Length; i++)
            {
                result[i] = HexToFloat(parts[i]);
            }

            return result;
        }

        /// <summary>Basit JSON okuyucu (yalnizca testler icin; System.Text.Json bagimliligi yok).</summary>
        public static Dictionary<string, object> ReadJsonObject(string path)
        {
            using var doc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(path));
            return (Dictionary<string, object>)ToPlain(doc.RootElement)!;
        }

        private static object? ToPlain(System.Text.Json.JsonElement e)
        {
            switch (e.ValueKind)
            {
                case System.Text.Json.JsonValueKind.Object:
                    var map = new Dictionary<string, object>(StringComparer.Ordinal);
                    foreach (var p in e.EnumerateObject())
                    {
                        map[p.Name] = ToPlain(p.Value)!;
                    }

                    return map;
                case System.Text.Json.JsonValueKind.Array:
                    var list = new List<object>();
                    foreach (var item in e.EnumerateArray())
                    {
                        list.Add(ToPlain(item)!);
                    }

                    return list;
                case System.Text.Json.JsonValueKind.String:
                    return e.GetString()!;
                case System.Text.Json.JsonValueKind.Number:
                    return e.GetDouble();
                case System.Text.Json.JsonValueKind.True:
                    return true;
                case System.Text.Json.JsonValueKind.False:
                    return false;
                default:
                    return null;
            }
        }
    }
}