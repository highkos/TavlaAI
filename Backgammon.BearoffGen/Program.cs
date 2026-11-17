using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using Backgammon.Core;

namespace Backgammon.BearoffGen
{
    /// <summary>
    /// Faz 5 §3.9: <c>bearoff1_v1.bin</c> üretici CLI.
    /// </summary>
    internal static class Program
    {
        private const string DefaultOutput = "ml/artifacts/bearoff1_v1.bin";
        private const string DefaultMeasureJson = "ml/artifacts/bearoff_measure.json";

        private static int Main(string[] args)
        {
            string output = DefaultOutput;
            string measureJson = DefaultMeasureJson;
            int maxRolls = 12;
            bool gammon = false;
            bool verify = false;
            bool measure = false;

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--out":
                        output = RequireValue(args, ref i);
                        break;
                    case "--measure-json":
                        measureJson = RequireValue(args, ref i);
                        break;
                    case "--max-rolls":
                        maxRolls = int.Parse(RequireValue(args, ref i), CultureInfo.InvariantCulture);
                        break;
                    case "--gammon":
                        gammon = true;
                        break;
                    case "--verify":
                        verify = true;
                        break;
                    case "--measure":
                        measure = true;
                        break;
                    case "--help":
                    case "-h":
                        PrintUsage();
                        return 0;
                    default:
                        Console.Error.WriteLine("Bilinmeyen argüman: " + args[i]);
                        PrintUsage();
                        return 2;
                }
            }

            if (measure)
            {
                return Measure.Run(output, measureJson, maxRolls);
            }

            if (gammon)
            {
                Console.WriteLine(
                    "UYARI: --gammon bu sürümde üretilmez (Faz 5 §3.9 'isteğe bağlıdır'). " +
                    "Format bayrağı 0 kalır; mars olasılıkları 0 kabul edilir.");
            }

            Console.WriteLine("Bearoff CDF tablosu üretiliyor (başlangıç maxRolls = " + maxRolls + ")...");
            BearoffGenerator.Result result = BearoffGenerator.Generate(maxRolls);

            Console.WriteLine("  geçiş tablosu : " + result.TransitionMilliseconds + " ms");
            Console.WriteLine("  DP            : " + result.DynamicProgrammingMilliseconds + " ms");
            Console.WriteLine("  toplam        : " + result.ElapsedMilliseconds + " ms");
            Console.WriteLine("  maxRolls      : " + result.MaxRolls +
                              (result.MaxRollsIncreased ? "  (ARTIRILDI, istenen " + result.InitialMaxRolls + ")" : string.Empty));

            BearoffGenerator.Write(output, result);

            var info = new FileInfo(output);
            Console.WriteLine("  dosya         : " + info.FullName);
            Console.WriteLine("  boyut         : " + info.Length + " bayt (" +
                              (info.Length / 1048576.0).ToString("F2", CultureInfo.InvariantCulture) + " MiB)");

            if (!verify)
            {
                return 0;
            }

            Console.WriteLine();
            Console.WriteLine("Doğrulama (Faz 5 §8 Test 1-5):");
            int failures = Verify(output, result);
            if (failures != 0)
            {
                Console.Error.WriteLine("DOĞRULAMA BAŞARISIZ: " + failures + " kontrol.");
                return 1;
            }

            Console.WriteLine("Tüm doğrulamalar geçti.");
            return 0;
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Kullanım: Backgammon.BearoffGen [--out <yol>] [--max-rolls <n>] [--gammon] [--verify] [--measure]");
            Console.WriteLine("  --out           çıktı dosyası (varsayılan " + DefaultOutput + ")");
            Console.WriteLine("  --max-rolls     başlangıç tur sayısı (varsayılan 12; yetersizse artırılır)");
            Console.WriteLine("  --gammon        mars tablosu (bu sürümde üretilmez, uyarı verir)");
            Console.WriteLine("  --verify        üretim sonrası Test 1-5'i çalıştırır");
            Console.WriteLine("  --measure       Faz 5 §9.1 ölçüm tablosunu doldurur");
            Console.WriteLine("  --measure-json  gnubg referans JSON yolu (varsayılan " + DefaultMeasureJson + ")");
        }

        private static string RequireValue(string[] args, ref int index)
        {
            if (index + 1 >= args.Length)
            {
                throw new ArgumentException(args[index] + " bir değer gerektirir.");
            }

            index++;
            return args[index];
        }

        // ------------------------------------------------------------------
        // Doğrulama
        // ------------------------------------------------------------------

        private static int Verify(string path, BearoffGenerator.Result result)
        {
            int failures = 0;
            failures += VerifyIndexRoundTrip();
            failures += VerifyIndexBoundaries();
            failures += VerifyHeaderValidation(path);
            failures += VerifyMonotoneCdf(path);
            failures += VerifyKnownPositions(path);
            return failures;
        }

        private static int VerifyIndexRoundTrip()
        {
            var counts = new byte[BearoffIndex.Points];
            var back = new byte[BearoffIndex.Points];
            var seen = new bool[BearoffIndex.Positions];
            int failures = 0;

            for (int rank = 0; rank < BearoffIndex.Positions; rank++)
            {
                BearoffIndex.Unrank(rank, back);
                int again = BearoffIndex.Rank(back);
                if (again != rank)
                {
                    failures++;
                }

                if (seen[again])
                {
                    failures++;
                }

                seen[again] = true;
            }

            Report("Test 1  BearoffIndex_RoundTrip", failures == 0);
            return failures;
        }

        private static int VerifyIndexBoundaries()
        {
            int failures = 0;
            var counts = new byte[BearoffIndex.Points];

            if (BearoffIndex.Rank(counts) != 0)
            {
                failures++;
            }

            counts[0] = 15;
            if (BearoffIndex.Rank(counts) != BearoffIndex.Positions - 1)
            {
                failures++;
            }

            Report("Test 2  BearoffIndex_Boundaries", failures == 0);
            return failures;
        }

        private static int VerifyHeaderValidation(string path)
        {
            int failures = 0;
            string temp = Path.Combine(Path.GetTempPath(), "bearoff_verify_" + Guid.NewGuid().ToString("N") + ".bin");

            try
            {
                byte[] original = File.ReadAllBytes(path);

                failures += ExpectInvalid(original, 0, (byte)0xFF, temp);   // magic
                failures += ExpectInvalid(original, 4, (byte)0x02, temp);   // version
                failures += ExpectInvalid(original, 6, (byte)0x07, temp);   // points
                failures += ExpectInvalid(original, 7, (byte)0x0E, temp);   // checkers
                failures += ExpectInvalid(original, 8, (byte)0x01, temp);   // positions
                failures += ExpectInvalid(original, 20, (byte)0x01, temp);  // payloadBytes
                failures += ExpectInvalid(original, 16, (byte)0x01, temp);  // payloadCrc32
            }
            finally
            {
                if (File.Exists(temp))
                {
                    File.Delete(temp);
                }
            }

            Report("Test 3  BearoffDatabase_HeaderValidation", failures == 0);
            return failures;
        }

        private static int ExpectInvalid(byte[] original, int offset, byte value, string temp)
        {
            var copy = (byte[])original.Clone();
            copy[offset] = (byte)(copy[offset] ^ value);
            File.WriteAllBytes(temp, copy);

            try
            {
                using (BearoffDatabase db = BearoffDatabase.Open(temp))
                {
                    return 1;
                }
            }
            catch (InvalidDataException)
            {
                return 0;
            }
            catch (Exception)
            {
                return 1;
            }
        }

        private static int VerifyMonotoneCdf(string path)
        {
            int failures = 0;
            using (BearoffDatabase db = BearoffDatabase.Open(path))
            {
                var counts = new byte[BearoffIndex.Points];
                var board = new sbyte[BackgammonState.BoardSize];
                var cdf = new float[db.MaxRolls + 1];
                const float Tolerance = 1.0f / 65535.0f;

                for (int rank = 0; rank < BearoffIndex.Positions; rank++)
                {
                    BearoffIndex.Unrank(rank, counts);
                    BuildBoard(counts, board);

                    if (!db.TryGetCdf(board, 1, cdf))
                    {
                        failures++;
                        continue;
                    }

                    if (cdf[0] != 0f)
                    {
                        failures++;
                    }

                    for (int k = 1; k <= db.MaxRolls; k++)
                    {
                        if (cdf[k] < cdf[k - 1] - Tolerance)
                        {
                            failures++;
                            break;
                        }
                    }

                    if (Math.Abs(cdf[db.MaxRolls] - 1f) > Tolerance)
                    {
                        failures++;
                    }
                }
            }

            Report("Test 4  BearoffDatabase_MonotoneCdf", failures == 0);
            return failures;
        }

        private static int VerifyKnownPositions(string path)
        {
            int failures = 0;
            using (BearoffDatabase db = BearoffDatabase.Open(path))
            {
                var cdf = new float[db.MaxRolls + 1];
                const float Tolerance = 2.0f / 65535.0f;

                // Değerler bağımsız Python referansından (ml/bearoff_ref.py --dump-known) alınmıştır.
                // 1 taş, 1-hane: her zar toplar.
                failures += ExpectCdf(db, new byte[] { 1, 0, 0, 0, 0, 0 }, 1, 1.0, cdf, Tolerance);

                // 1 taş, 6-hane: 27/36 (tek zar ≥6 veya iki zarın toplamı ≥6).
                failures += ExpectCdf(db, new byte[] { 0, 0, 0, 0, 0, 1 }, 1, 27.0 / 36.0, cdf, Tolerance);

                // 2 taş, 6-hane: 4/36 (yalnızca (2,2), (3,3), (1,5)).
                failures += ExpectCdf(db, new byte[] { 0, 0, 0, 0, 0, 2 }, 1, 4.0 / 36.0, cdf, Tolerance);
                failures += ExpectCdf(db, new byte[] { 0, 0, 0, 0, 0, 2 }, 2, 0.782407, cdf, Tolerance);

                // 2 taş, 1-hane: her iki zar da toplar.
                failures += ExpectCdf(db, new byte[] { 2, 0, 0, 0, 0, 0 }, 1, 1.0, cdf, Tolerance);

                // 15 taş, 1-hane: tek turda imkânsız (en fazla 4 taş).
                failures += ExpectCdf(db, new byte[] { 15, 0, 0, 0, 0, 0 }, 1, 0.0, cdf, Tolerance);
                failures += ExpectCdf(db, new byte[] { 15, 0, 0, 0, 0, 0 }, 4, 0.000772, cdf, Tolerance);

                // 15 taş, 6-hane: tek turda imkânsız.
                failures += ExpectCdf(db, new byte[] { 0, 0, 0, 0, 0, 15 }, 1, 0.0, cdf, Tolerance);
                failures += ExpectCdf(db, new byte[] { 0, 0, 0, 0, 0, 15 }, 6, 0.000284, cdf, Tolerance);
            }

            Report("Test 5  BearoffDatabase_KnownPositions", failures == 0);
            return failures;
        }

        private static int ExpectCdf(BearoffDatabase db, byte[] counts, int k, double expected,
                                     float[] cdf, float tolerance)
        {
            var board = new sbyte[BackgammonState.BoardSize];
            BuildBoard(counts, board);
            if (!db.TryGetCdf(board, 1, cdf))
            {
                Console.WriteLine("    TryGetCdf false: " + string.Join(",", counts));
                return 1;
            }

            if (Math.Abs(cdf[k] - expected) > tolerance)
            {
                Console.WriteLine("    cdf[" + k + "] = " + cdf[k].ToString("F6", CultureInfo.InvariantCulture) +
                                  " beklenen " + expected.ToString("F6", CultureInfo.InvariantCulture) +
                                  "  counts=" + string.Join(",", counts));
                return 1;
            }

            return 0;
        }

        private static void BuildBoard(byte[] counts, sbyte[] board)
        {
            Array.Clear(board, 0, board.Length);
            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                board[24 - i] = (sbyte)counts[i];
            }

            board[1] = -15;
        }

        private static void Report(string name, bool ok)
        {
            Console.WriteLine("  " + (ok ? "PASS" : "FAIL") + "  " + name);
        }
    }
}
