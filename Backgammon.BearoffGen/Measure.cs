using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using Backgammon.Core;

namespace Backgammon.BearoffGen
{
    /// <summary>
    /// Faz 5 §9.1: bearoff ölçüm tablosunu <b>gerçekten</b> doldurur.
    /// </summary>
    /// <remarks>
    /// Hiçbir değer uydurulmaz. Ölçülemeyen satır (gnubg uyumu) ayrı bir Python adımına
    /// devredilir ve JSON olarak dışa aktarılır.
    /// </remarks>
    internal static class Measure
    {
        private const int QuantizationSamples = 10000;
        private const int SelfPlaySamples = 10000;
        private const int GnubgSamples = 200;
        private const int DecoratorIterations = 20000;
        private const int DepthIterations = 200;

        public static int Run(string dbPath, string jsonPath, int initialMaxRolls)
        {
            Console.WriteLine("Ölçüm başlıyor (Faz 5 §9.1)...");
            Console.WriteLine();

            BearoffGenerator.Result result = BearoffGenerator.Generate(initialMaxRolls, keepExactCdf: true);
            BearoffGenerator.Write(dbPath, result);

            var info = new FileInfo(dbPath);
            Console.WriteLine("1) DB dosya boyutu        : " + info.Length + " bayt (" +
                              (info.Length / 1048576.0).ToString("F2", CultureInfo.InvariantCulture) + " MiB)");
            Console.WriteLine("2) Üretim süresi          : " +
                              (result.ElapsedMilliseconds / 1000.0).ToString("F2", CultureInfo.InvariantCulture) +
                              " s (geçiş " + result.TransitionMilliseconds + " ms + DP " +
                              result.DynamicProgrammingMilliseconds + " ms)");
            Console.WriteLine("   MaxRolls               : " + result.MaxRolls +
                              (result.MaxRollsIncreased ? " (istenen " + result.InitialMaxRolls + " yetersizdi)" : string.Empty));
            Console.WriteLine("   Gammon tablosu         : yok (bayrak 0)");
            Console.WriteLine();

            using (BearoffDatabase db = BearoffDatabase.Open(dbPath))
            {
                QuantizationError(db, result);
                Console.WriteLine();
                HitRate();
                Console.WriteLine();
                DecoratorOverhead(db);
                Console.WriteLine();
                DepthShortcut(db);
                Console.WriteLine();
                WriteGnubgReference(db, jsonPath);
            }

            Console.WriteLine();
            Console.WriteLine("Ölçüm tamamlandı.");
            return 0;
        }

        // ------------------------------------------------------------------
        // 3) Nicemleme hatası
        // ------------------------------------------------------------------

        private static void QuantizationError(BearoffDatabase db, BearoffGenerator.Result result)
        {
            var rng = new XorShift(20240501u);
            var counts = new byte[BearoffIndex.Points];
            var board = new sbyte[BackgammonState.BoardSize];
            var cdf = new float[db.MaxRolls + 1];
            int positions = BearoffIndex.Positions;

            double max = 0.0;
            double sum = 0.0;
            long samples = 0;

            for (int n = 0; n < QuantizationSamples; n++)
            {
                RandomCounts(rng, counts);
                BuildBoard(counts, board);
                if (!db.TryGetCdf(board, 1, cdf))
                {
                    continue;
                }

                int rank = BearoffIndex.Rank(counts);
                for (int k = 0; k <= db.MaxRolls; k++)
                {
                    double exact = result.ExactCdf[((long)k * positions) + rank];
                    double diff = Math.Abs(exact - cdf[k]);
                    if (diff > max)
                    {
                        max = diff;
                    }

                    sum += diff;
                    samples++;
                }
            }

            double mean = samples == 0 ? 0.0 : sum / samples;
            Console.WriteLine("3) Nicemleme hatası       : maks " + max.ToString("E3", CultureInfo.InvariantCulture) +
                              "  ortalama " + mean.ToString("E3", CultureInfo.InvariantCulture) +
                              "  (" + QuantizationSamples + " pozisyon, " + samples + " örnek)");
            Console.WriteLine("   Kuramsal üst sınır     : " + (0.5 / 65535.0).ToString("E3", CultureInfo.InvariantCulture) +
                              " (uint16 nicemleme) + float okuma yuvarlaması");
        }

        // ------------------------------------------------------------------
        // 4) İsabet oranı
        // ------------------------------------------------------------------

        private static void HitRate()
        {
            var rng = new XorShift(777u);
            var state = new BackgammonState();
            var afterStates = new AfterStateList(AfterStateList.DefaultCapacity);
            EngineSettings settings = EngineSettings.Default;
            MatchSettings match = MatchSettings.MoneyGame;

            int sampled = 0;
            int hits = 0;
            int games = 0;

            while (sampled < SelfPlaySamples && games < 4000)
            {
                BackgammonEngine.NewGame(state, match);
                BackgammonEngine.RollOpening(state, rng);
                games++;

                int plies = 0;
                while (plies < 400)
                {
                    if (BackgammonEngine.IsGameOver(state, out GameResult _))
                    {
                        break;
                    }

                    if (state.remainingCount == 0)
                    {
                        BackgammonEngine.RollDice(state, rng);
                    }

                    if (sampled < SelfPlaySamples)
                    {
                        sampled++;
                        if (BearoffDatabase.IsOneSidedBearoff(state.board, state.turn))
                        {
                            hits++;
                        }
                    }

                    LegalMoveGenerator.GenerateAfterStates(state, settings, afterStates);
                    if (afterStates.Count == 0)
                    {
                        BackgammonEngine.PassTurn(state);
                    }
                    else
                    {
                        int pick = (int)(rng.NextUInt() % (uint)afterStates.Count);
                        BackgammonEngine.LoadAfterState(state, afterStates, pick);
                        BackgammonEngine.EndTurn(state, settings);
                    }

                    plies++;
                }
            }

            double percent = sampled == 0 ? 0.0 : (100.0 * hits) / sampled;
            Console.WriteLine("4) İsabet oranı           : " + percent.ToString("F2", CultureInfo.InvariantCulture) +
                              "%  (" + hits + "/" + sampled + " rastgele self-play pozisyonu, " + games + " oyun)");
        }

        // ------------------------------------------------------------------
        // 5) Dekoratör ek yükü ve allocation
        // ------------------------------------------------------------------

        private static void DecoratorOverhead(BearoffDatabase db)
        {
            var rng = new XorShift(4242u);
            var list = new AfterStateList(64);
            var state = new BackgammonState();
            var scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);
            var results = new float[64];

            // Karışık parti: yarısı bearoff, yarısı değil.
            for (int i = 0; i < 32; i++)
            {
                RandomCounts(rng, out byte[] white, out byte[] black);
                BuildBoard(white, black, state.board);
                state.turn = 1;
                state.whiteBorneOff = 0;
                state.blackBorneOff = 0;
                list.Add(state, default);
            }

            for (int i = 0; i < 32; i++)
            {
                Array.Clear(state.board, 0, BackgammonState.BoardSize);
                state.board[24] = 2;
                state.board[13] = 5;
                state.board[8] = 5;
                state.board[6] = 3;
                state.board[1] = -2;
                state.board[12] = -5;
                state.board[17] = -5;
                state.board[19] = -3;
                state.turn = 1;
                list.Add(state, default);
            }

            var inner = new NullInnerEvaluator();
            var onOptions = BearoffAwareOptions.Default;
            var offOptions = new BearoffAwareOptions { SkipInnerForPureBearoffBatches = true, DisableBearoff = true };
            var on = new BearoffAwareEvaluator(inner, db, onOptions);
            var off = new BearoffAwareEvaluator(inner, db, offOptions);

            int count = list.Count;

            // Isınma
            for (int i = 0; i < 200; i++)
            {
                on.EvaluateBatch(list, 0, count, 1, scalars, results);
                off.EvaluateBatch(list, 0, count, 1, scalars, results);
            }

            double onUs = TimePerCall(on, list, count, scalars, results);
            double offUs = TimePerCall(off, list, count, scalars, results);

            long onBytes = BytesPerCall(on, list, count, scalars, results);
            long offBytes = BytesPerCall(off, list, count, scalars, results);

            Console.WriteLine("5) Dekoratör ek yükü      : DB açık " + onUs.ToString("F3", CultureInfo.InvariantCulture) +
                              " µs/çağrı, DB kapalı " + offUs.ToString("F3", CultureInfo.InvariantCulture) +
                              " µs/çağrı, oran " + (offUs <= 0 ? 0.0 : onUs / offUs).ToString("F2", CultureInfo.InvariantCulture) +
                              "  (" + count + " kayıt/çağrı, " + DecoratorIterations + " çağrı)");
            Console.WriteLine("6) Dekoratör allocation   : DB açık " + onBytes + " bayt/çağrı, DB kapalı " +
                              offBytes + " bayt/çağrı (hedef 0)");
        }

        private static double TimePerCall(BearoffAwareEvaluator evaluator, AfterStateList list, int count,
                                          VectorizerScalars scalars, float[] results)
        {
            var watch = Stopwatch.StartNew();
            for (int i = 0; i < DecoratorIterations; i++)
            {
                evaluator.EvaluateBatch(list, 0, count, 1, scalars, results);
            }

            watch.Stop();
            return (watch.Elapsed.TotalMilliseconds * 1000.0) / DecoratorIterations;
        }

        private static long BytesPerCall(BearoffAwareEvaluator evaluator, AfterStateList list, int count,
                                         VectorizerScalars scalars, float[] results)
        {
            long before = GC.GetAllocatedBytesForCurrentThread();
            for (int i = 0; i < DecoratorIterations; i++)
            {
                evaluator.EvaluateBatch(list, 0, count, 1, scalars, results);
            }

            long after = GC.GetAllocatedBytesForCurrentThread();
            return (after - before) / DecoratorIterations;
        }

        // ------------------------------------------------------------------
        // 7) Depth-0 kısayolu
        // ------------------------------------------------------------------

        private static void DepthShortcut(BearoffDatabase db)
        {
            var rng = new XorShift(31337u);
            var state = new BackgammonState();
            var workspace = new SearchWorkspace();
            var inner = new NullInnerEvaluator();
            var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
            EngineSettings engine = EngineSettings.Default;

            var depth1 = SearchSettings.Default;
            depth1.DepthPly = 1;
            var depth0 = SearchSettings.Default;
            depth0.DepthPly = 0;

            double ms1 = 0.0;
            double ms0 = 0.0;
            int measured = 0;

            for (int n = 0; n < DepthIterations; n++)
            {
                RandomCounts(rng, out byte[] white, out byte[] black);
                BuildBoard(white, black, state.board);
                state.turn = 1;
                state.whiteBorneOff = 0;
                state.blackBorneOff = 0;
                state.remainingCount = 0;
                BackgammonEngine.SetDice(state, 3, 5);

                if (!BearoffAwareEvaluator.IsSolvable(state.board))
                {
                    continue;
                }

                workspace.Reset();
                var watch = Stopwatch.StartNew();
                BackgammonSearch.Search(state, depth1, engine, workspace, evaluator, evaluator);
                watch.Stop();
                ms1 += watch.Elapsed.TotalMilliseconds;

                workspace.Reset();
                watch.Restart();
                BackgammonSearch.Search(state, depth0, engine, workspace, evaluator, evaluator);
                watch.Stop();
                ms0 += watch.Elapsed.TotalMilliseconds;

                measured++;
            }

            if (measured == 0)
            {
                Console.WriteLine("7) Depth-0 kısayolu       : ölçülemedi (bearoff pozisyonu üretilemedi)");
                return;
            }

            double avg1 = ms1 / measured;
            double avg0 = ms0 / measured;
            Console.WriteLine("7) Depth-0 kısayolu       : DepthPly=1 " + avg1.ToString("F3", CultureInfo.InvariantCulture) +
                              " ms/karar, DepthPly=0 " + avg0.ToString("F3", CultureInfo.InvariantCulture) +
                              " ms/karar, kazanç " + (avg0 <= 0 ? 0.0 : avg1 / avg0).ToString("F2", CultureInfo.InvariantCulture) +
                              "×  (" + measured + " pozisyon)");
        }

        // ------------------------------------------------------------------
        // 8) gnubg referansı
        // ------------------------------------------------------------------

        private static void WriteGnubgReference(BearoffDatabase db, string jsonPath)
        {
            var rng = new XorShift(90210u);
            var state = new BackgammonState();
            var list = new AfterStateList(4);
            var scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);
            var results = new float[4];
            var inner = new NullInnerEvaluator();
            var evaluator = new BearoffAwareEvaluator(inner, db, BearoffAwareOptions.Default);
            var cdf = new float[db.MaxRolls + 1];

            var builder = new StringBuilder();
            builder.Append("{\n  \"maxRolls\": ").Append(db.MaxRolls).Append(",\n  \"positions\": [\n");

            int written = 0;
            int guard = 0;
            while (written < GnubgSamples && guard < GnubgSamples * 200)
            {
                guard++;
                RandomCounts(rng, out byte[] white, out byte[] black);
                BuildBoard(white, black, state.board);
                state.turn = 1;
                state.whiteBorneOff = 0;
                state.blackBorneOff = 0;

                if (!BearoffAwareEvaluator.IsSolvable(state.board))
                {
                    continue;
                }

                list.Clear();
                list.Add(state, default);
                evaluator.EvaluateBatch(list, 0, 1, -1, scalars, results);

                // perspective = -1 ⇒ sonuç Siyah'ın equity'si; Beyaz (sırada) için işaret ters.
                double whiteEquity = -results[0];

                if (written > 0)
                {
                    builder.Append(",\n");
                }

                builder.Append("    {\"board\": [");
                for (int i = 0; i < BackgammonState.BoardSize; i++)
                {
                    if (i > 0)
                    {
                        builder.Append(", ");
                    }

                    builder.Append(state.board[i].ToString(CultureInfo.InvariantCulture));
                }

                builder.Append("], \"turn\": 1, \"whiteEquity\": ");
                builder.Append(whiteEquity.ToString("R", CultureInfo.InvariantCulture));
                builder.Append(", \"whiteCounts\": [");
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    if (i > 0)
                    {
                        builder.Append(", ");
                    }

                    builder.Append(white[i].ToString(CultureInfo.InvariantCulture));
                }

                builder.Append("], \"blackCounts\": [");
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    if (i > 0)
                    {
                        builder.Append(", ");
                    }

                    builder.Append(black[i].ToString(CultureInfo.InvariantCulture));
                }

                // Sırada olan (Beyaz) için tam "k turda toplar" dağılımı: gnubg'nin
                // ``Evaluator: Bearoff1`` tablosuyla doğrudan karşılaştırılır.
                db.TryGetCdf(state.board, 1, cdf);
                builder.Append("], \"whiteDistribution\": [");
                float previous = 0f;
                for (int k = 1; k <= db.MaxRolls; k++)
                {
                    if (k > 1)
                    {
                        builder.Append(", ");
                    }

                    float p = cdf[k] - previous;
                    previous = cdf[k];
                    builder.Append(p.ToString("R", CultureInfo.InvariantCulture));
                }

                builder.Append("]}");
                written++;
            }

            builder.Append("\n  ]\n}\n");

            string directory = Path.GetDirectoryName(Path.GetFullPath(jsonPath)) ?? string.Empty;
            if (directory.Length != 0 && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            File.WriteAllText(jsonPath, builder.ToString(), new UTF8Encoding(false));
            Console.WriteLine("8) gnubg referansı        : " + written + " pozisyon yazıldı -> " + jsonPath);
            Console.WriteLine("   Karşılaştırma          : python ml/bearoff_gnubg.py --in " + jsonPath);
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static void RandomCounts(XorShift rng, byte[] counts)
        {
            RandomCounts(rng, out byte[] white, out byte[] _);
            Array.Copy(white, counts, BearoffIndex.Points);
        }

        private static void RandomCounts(XorShift rng, out byte[] white, out byte[] black)
        {
            white = new byte[BearoffIndex.Points];
            black = new byte[BearoffIndex.Points];
            Distribute(rng, white);
            Distribute(rng, black);
        }

        private static void Distribute(XorShift rng, byte[] counts)
        {
            int remaining = BearoffIndex.Checkers;
            for (int i = 0; i < BearoffIndex.Points - 1; i++)
            {
                int max = remaining;
                int take = (int)(rng.NextUInt() % (uint)(max + 1));
                counts[i] = (byte)take;
                remaining -= take;
            }

            counts[BearoffIndex.Points - 1] = (byte)remaining;
        }

        private static void BuildBoard(byte[] whiteCounts, sbyte[] board)
        {
            Array.Clear(board, 0, board.Length);
            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                board[24 - i] = (sbyte)whiteCounts[i];
            }

            board[1] = -15;
        }

        private static void BuildBoard(byte[] whiteCounts, byte[] blackCounts, sbyte[] board)
        {
            Array.Clear(board, 0, board.Length);
            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                board[24 - i] = (sbyte)whiteCounts[i];
                board[i + 1] = (sbyte)(-blackCounts[i]);
            }
        }

        /// <summary>Deterministik xorshift32 — ölçümler tekrarlanabilir olsun diye.</summary>
        private sealed class XorShift : IRandom
        {
            private uint _state;

            public XorShift(uint seed)
            {
                _state = seed == 0 ? 0x9E3779B9u : seed;
            }

            public uint NextUInt()
            {
                uint x = _state;
                x ^= x << 13;
                x ^= x >> 17;
                x ^= x << 5;
                _state = x;
                return x;
            }

            public int RollDie()
            {
                return (int)(NextUInt() % 6u) + 1;
            }
        }

        /// <summary>Ölçüm için sıfır döndüren iç değerlendirici (dekoratörün kendi maliyetini ayırır).</summary>
        private sealed class NullInnerEvaluator : IPolicyValueEvaluator, ICombinedBatchEvaluator
        {
            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                for (int i = offset; i < offset + count; i++)
                {
                    results[i] = 0f;
                }
            }

            public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> priorities)
            {
                for (int i = offset; i < offset + count; i++)
                {
                    priorities[i] = 0f;
                }
            }

            public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                              in VectorizerScalars scalars, Span<float> results,
                                              Span<float> priorities)
            {
                EvaluateBatch(list, offset, count, perspective, scalars, results);
                ScoreBatch(list, offset, count, perspective, scalars, priorities);
            }
        }
    }
}
