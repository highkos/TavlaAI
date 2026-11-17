using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §3.9: 1 taraflı bearoff CDF tablosunun dinamik programlama ile üretimi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Determinizm:</b> tek iş parçacıklı, sabit sıralı. Aynı girdi ⇒ bit düzeyinde aynı çıktı.
    /// </para>
    /// <para>
    /// <b>Yasal hamleler</b> <see cref="LegalMoveGenerator"/> ile üretilir; burada yeniden yazılmaz.
    /// </para>
    /// <para>
    /// <b>Gammon tablosu</b> bu sürümde üretilmez (Faz 5 §3.9 "isteğe bağlıdır"). Format bayrağı
    /// <c>0</c> kalır, <see cref="BearoffDatabase.HasGammonData"/> <c>false</c> döner ve mars
    /// olasılıkları 0 kabul edilir.
    /// </para>
    /// </remarks>
    public static class BearoffGenerator
    {
        /// <summary>Farklı zar kombinasyonu sayısı (dubllar dahil).</summary>
        public const int DiceCombinations = 21;

        /// <summary>Üretim sonucu.</summary>
        public sealed class Result
        {
            /// <summary>İstenen başlangıç <c>MaxRolls</c>.</summary>
            public int InitialMaxRolls;

            /// <summary>Gerçekte kullanılan <c>MaxRolls</c> (yetersizse artırılmış).</summary>
            public int MaxRolls;

            /// <summary><c>MaxRolls</c> artırıldı mı?</summary>
            public bool MaxRollsIncreased;

            /// <summary>Nicemlenmiş CDF: <c>Positions × (MaxRolls+1)</c>.</summary>
            public ushort[] Cdf;

            /// <summary>
            /// Nicemlenmemiş (çift duyarlıklı) CDF: <c>Positions × (MaxRolls+1)</c>.
            /// Yalnızca <c>keepExactCdf</c> istenirse doldurulur; nicemleme hatası ölçümü içindir.
            /// </summary>
            public double[] ExactCdf;

            /// <summary>Üretim süresi (ms).</summary>
            public long ElapsedMilliseconds;

            /// <summary>Geçiş tablosu kurulum süresi (ms).</summary>
            public long TransitionMilliseconds;

            /// <summary>DP süresi (ms).</summary>
            public long DynamicProgrammingMilliseconds;
        }

        /// <summary>
        /// CDF tablosunu üretir. <paramref name="initialMaxRolls"/> yetersizse tablo tamamlanana
        /// kadar artırılır (sessizce kırpılmaz).
        /// </summary>
        /// <param name="initialMaxRolls">Başlangıç tur sayısı.</param>
        /// <param name="keepExactCdf">
        /// <c>true</c> ise nicemlenmemiş tablo da <see cref="Result.ExactCdf"/> içinde tutulur
        /// (nicemleme hatası ölçümü için; ~10 MB ek bellek).
        /// </param>
        /// <remarks>
        /// <para>
        /// <b>Tek politika ilkesi.</b> Oyuncu her pozisyonda <b>tek</b> bir politika izler:
        /// beklenen tur sayısını (<c>E[T]</c>) en aza indiren hamle. Dağılım bu politika altında
        /// hesaplanır. <c>P(T ≤ k)</c>'yi her <c>k</c> için ayrı ayrı maksimize etmek
        /// (per-k max) <b>yanlıştır</b>: aynı zar atışında farklı <c>k</c> için farklı hamle
        /// seçilemeyeceğinden o CDF hiçbir gerçek politikaya karşılık gelmez. Bu düzeltme
        /// gnubg'nin <c>Bearoff1</c> tablosuyla 1e-5 düzeyinde uyuşur (F5-xx).
        /// </para>
        /// <para>
        /// <b>Determinizm:</b> eşit <c>E[T]</c> değerlerinde en küçük sıra numaralı ardıl seçilir.
        /// </para>
        /// </remarks>
        public static Result Generate(int initialMaxRolls, bool keepExactCdf = false)
        {
            if (initialMaxRolls < 1 || initialMaxRolls > 64)
            {
                throw new ArgumentOutOfRangeException(nameof(initialMaxRolls));
            }

            var stopwatch = Stopwatch.StartNew();
            var result = new Result { InitialMaxRolls = initialMaxRolls };

            int positions = BearoffIndex.Positions;
            int[] start;
            int[] successors;
            BuildTransitions(out start, out successors);
            result.TransitionMilliseconds = stopwatch.ElapsedMilliseconds;

            var dpWatch = Stopwatch.StartNew();

            int[] order = BuildTopologicalOrder();
            double[] expected = ComputeExpectedRolls(start, successors, order);
            int[] policy = SelectPolicy(start, successors, expected);

            var rows = new List<double[]>(65);
            var previous = new double[positions];
            var current = new double[positions];
            var cumulative = new double[positions];
            previous[0] = 1.0;
            rows.Add(new double[positions]); // k = 0 satırı formata göre sıfırdır

            int maxRolls = 0;
            for (int k = 1; k <= 64; k++)
            {
                for (int p = 0; p < positions; p++)
                {
                    if (p == 0)
                    {
                        // "Hepsi toplanmış" yutan durumdur: T = 0 kesindir, bu yüzden
                        // k >= 1 için tam olarak k turda bitme olasılığı sıfırdır.
                        current[p] = 0.0;
                        continue;
                    }

                    double sum = 0.0;
                    int baseIndex = p * DiceCombinations;
                    for (int d = 0; d < DiceCombinations; d++)
                    {
                        sum += DiceWeight(d) * previous[policy[baseIndex + d]];
                    }

                    current[p] = sum / 36.0;
                }

                var row = new double[positions];
                Array.Copy(current, row, positions);
                rows.Add(row);

                for (int p = 0; p < positions; p++)
                {
                    cumulative[p] += row[p];
                }

                var swap = previous;
                previous = current;
                current = swap;

                maxRolls = k;
                if (k >= initialMaxRolls && AllComplete(cumulative))
                {
                    break;
                }
            }

            if (!AllComplete(cumulative))
            {
                throw new InvalidOperationException(
                    "Bearoff DP 64 turda tamamlanmadı; tablo üretilemez.");
            }

            result.DynamicProgrammingMilliseconds = dpWatch.ElapsedMilliseconds;
            result.MaxRolls = maxRolls;
            result.MaxRollsIncreased = maxRolls > initialMaxRolls;

            var cdf = new ushort[(long)positions * (maxRolls + 1)];
            double[] exact = keepExactCdf ? new double[(long)positions * (maxRolls + 1)] : null;
            var running = new double[positions];
            for (int k = 0; k <= maxRolls; k++)
            {
                double[] row = rows[k];
                long offset = (long)k * positions;
                for (int p = 0; p < positions; p++)
                {
                    running[p] += row[p];
                    double value = running[p] > 1.0 ? 1.0 : running[p];
                    cdf[offset + p] = Quantize(value);
                    if (exact != null)
                    {
                        exact[offset + p] = value;
                    }
                }
            }

            // Sıra 0 = "hepsi toplanmış" yutan durumu. Format gereği cdf[0] = 0 kalır;
            // k >= 1 için olasılık 1'dir (pozisyon zaten bitmiştir).
            for (int k = 1; k <= maxRolls; k++)
            {
                long offset = (long)k * positions;
                cdf[offset] = ushort.MaxValue;
                if (exact != null)
                {
                    exact[offset] = 1.0;
                }
            }

            result.Cdf = cdf;
            result.ExactCdf = exact;
            result.ElapsedMilliseconds = stopwatch.ElapsedMilliseconds;
            return result;
        }

        /// <summary>
        /// Sıralamayı pip sayısına göre artan düzende döner. Her hamle pip sayısını kesinlikle
        /// azalttığı için bu sıra topolojiktir.
        /// </summary>
        private static int[] BuildTopologicalOrder()
        {
            int positions = BearoffIndex.Positions;
            var pips = new int[positions];
            Span<byte> counts = stackalloc byte[BearoffIndex.Points];

            for (int p = 0; p < positions; p++)
            {
                BearoffIndex.Unrank(p, counts);
                int total = 0;
                for (int i = 0; i < BearoffIndex.Points; i++)
                {
                    total += (i + 1) * counts[i];
                }

                pips[p] = total;
            }

            var order = new int[positions];
            for (int p = 0; p < positions; p++)
            {
                order[p] = p;
            }

            Array.Sort(order, (a, b) =>
            {
                int cmp = pips[a].CompareTo(pips[b]);
                return cmp != 0 ? cmp : a.CompareTo(b);
            });

            return order;
        }

        /// <summary><c>E[T(c)] = 1 + (1/36) Σ_zar min_hamle E[T(c')]</c>; topolojik sırada.</summary>
        private static double[] ComputeExpectedRolls(int[] start, int[] successors, int[] order)
        {
            int positions = BearoffIndex.Positions;
            var expected = new double[positions];

            for (int oi = 0; oi < order.Length; oi++)
            {
                int p = order[oi];
                if (p == 0)
                {
                    continue;
                }

                double sum = 0.0;
                int baseIndex = p * DiceCombinations;
                for (int d = 0; d < DiceCombinations; d++)
                {
                    int from = start[baseIndex + d];
                    int to = start[baseIndex + d + 1];
                    if (from == to)
                    {
                        throw new InvalidOperationException(
                            "Bearoff pozisyonunda yasal hamle yok (sıra " + p + ", zar " + d + ").");
                    }

                    double best = double.MaxValue;
                    for (int s = from; s < to; s++)
                    {
                        int next = successors[s];
                        if (next == p)
                        {
                            throw new InvalidOperationException(
                                "Bearoff geçişinde kendine döngü (sıra " + p + ").");
                        }

                        double v = expected[next];
                        if (v < best)
                        {
                            best = v;
                        }
                    }

                    sum += DiceWeight(d) * best;
                }

                expected[p] = 1.0 + (sum / 36.0);
            }

            return expected;
        }

        /// <summary>Her (pozisyon, zar) için <c>E[T]</c>'yi en aza indiren ardılı seçer.</summary>
        private static int[] SelectPolicy(int[] start, int[] successors, double[] expected)
        {
            int positions = BearoffIndex.Positions;
            var policy = new int[positions * DiceCombinations];

            for (int p = 1; p < positions; p++)
            {
                int baseIndex = p * DiceCombinations;
                for (int d = 0; d < DiceCombinations; d++)
                {
                    int from = start[baseIndex + d];
                    int to = start[baseIndex + d + 1];
                    int best = successors[from];
                    double bestValue = expected[best];
                    for (int s = from + 1; s < to; s++)
                    {
                        int candidate = successors[s];
                        double value = expected[candidate];
                        if (value < bestValue || (value == bestValue && candidate < best))
                        {
                            best = candidate;
                            bestValue = value;
                        }
                    }

                    policy[baseIndex + d] = best;
                }
            }

            return policy;
        }

        /// <summary>Sonucu <c>bearoff1_v1.bin</c> biçiminde yazar (Faz 5 §3.2).</summary>
        public static void Write(string path, Result result)
        {
            if (path == null)
            {
                throw new ArgumentNullException(nameof(path));
            }

            if (result == null)
            {
                throw new ArgumentNullException(nameof(result));
            }

            int positions = BearoffIndex.Positions;
            int maxRolls = result.MaxRolls;
            int rowBytes = (maxRolls + 1) * 2;
            int payloadBytes = positions * rowBytes;

            var payload = new byte[payloadBytes];
            for (int p = 0; p < positions; p++)
            {
                int rowOffset = p * rowBytes;
                for (int k = 0; k <= maxRolls; k++)
                {
                    ushort u = result.Cdf[((long)k * positions) + p];
                    payload[rowOffset + (k * 2)] = (byte)(u & 0xFF);
                    payload[rowOffset + (k * 2) + 1] = (byte)(u >> 8);
                }
            }

            var header = new byte[BearoffDatabase.HeaderBytes];
            WriteU32(header, 0, BearoffDatabase.Magic);
            header[4] = (byte)(BearoffDatabase.FormatVersion & 0xFF);
            header[5] = (byte)(BearoffDatabase.FormatVersion >> 8);
            header[6] = BearoffIndex.Points;
            header[7] = BearoffIndex.Checkers;
            WriteU32(header, 8, (uint)positions);
            header[12] = (byte)maxRolls;
            header[13] = 0; // gammon tablosu yok
            WriteU32(header, 16, BearoffCrc32.Compute(payload));
            WriteU32(header, 20, (uint)payloadBytes);

            string directory = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            using (var stream = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                stream.Write(header, 0, header.Length);
                stream.Write(payload, 0, payload.Length);
            }
        }

        // ------------------------------------------------------------------
        // Geçiş tablosu
        // ------------------------------------------------------------------

        private static void BuildTransitions(out int[] start, out int[] successors)
        {
            int positions = BearoffIndex.Positions;
            start = new int[(positions * DiceCombinations) + 1];
            var list = new List<int>(positions * 8);

            var state = new BackgammonState();
            state.Reset();
            EngineSettings settings = EngineSettings.Default;
            var afterStates = new AfterStateList(256);
            Span<byte> counts = stackalloc byte[BearoffIndex.Points];
            Span<byte> afterCounts = stackalloc byte[BearoffIndex.Points];

            for (int p = 0; p < positions; p++)
            {
                BearoffIndex.Unrank(p, counts);
                SetBoard(state, counts);

                int baseIndex = p * DiceCombinations;
                for (int d = 0; d < DiceCombinations; d++)
                {
                    start[baseIndex + d] = list.Count;

                    int d1 = DiceFirst(d);
                    int d2 = DiceSecond(d);
                    BackgammonEngine.SetDice(state, d1, d2);
                    LegalMoveGenerator.GenerateAfterStates(state, settings, afterStates);

                    if (afterStates.Count == 0)
                    {
                        // Oynanabilir hamle yok: pas, durum değişmez.
                        list.Add(p);
                    }
                    else
                    {
                        for (int i = 0; i < afterStates.Count; i++)
                        {
                            ReadOnlySpan<sbyte> board = new ReadOnlySpan<sbyte>(
                                afterStates.Boards, i * AfterStateList.BoardSize, AfterStateList.BoardSize);
                            BearoffDatabase.ToCounts(board, 1, afterCounts);
                            list.Add(BearoffIndex.Rank(afterCounts));
                        }
                    }
                }
            }

            start[positions * DiceCombinations] = list.Count;
            successors = list.ToArray();
        }

        private static void SetBoard(BackgammonState state, ReadOnlySpan<byte> counts)
        {
            Array.Clear(state.board, 0, BackgammonState.BoardSize);
            for (int i = 0; i < BearoffIndex.Points; i++)
            {
                state.board[24 - i] = (sbyte)counts[i];
            }

            // Rakip yarışta değil: hamle üretimini etkilememesi için kendi 1-hanesinde toplanır.
            state.board[1] = -15;
            state.whiteBorneOff = 0;
            state.blackBorneOff = 0;
            state.turn = 1;
        }

        private static int DiceFirst(int index)
        {
            return FirstDice[index];
        }

        private static int DiceSecond(int index)
        {
            return SecondDice[index];
        }

        private static int DiceWeight(int index)
        {
            return FirstDice[index] == SecondDice[index] ? 1 : 2;
        }

        private static readonly int[] FirstDice = BuildFirstDice();
        private static readonly int[] SecondDice = BuildSecondDice();

        private static int[] BuildFirstDice()
        {
            var result = new int[DiceCombinations];
            int i = 0;
            for (int a = 1; a <= 6; a++)
            {
                for (int b = a; b <= 6; b++)
                {
                    result[i++] = a;
                }
            }

            return result;
        }

        private static int[] BuildSecondDice()
        {
            var result = new int[DiceCombinations];
            int i = 0;
            for (int a = 1; a <= 6; a++)
            {
                for (int b = a; b <= 6; b++)
                {
                    result[i++] = b;
                }
            }

            return result;
        }

        private static bool AllComplete(double[] values)
        {
            const double Tolerance = 1e-12;
            // i = 0 yutan durumdur (hepsi toplanmış); yakınsama ölçütüne girmez.
            for (int i = 1; i < values.Length; i++)
            {
                if (values[i] < 1.0 - Tolerance)
                {
                    return false;
                }
            }

            return true;
        }

        private static ushort Quantize(double value)
        {
            if (value <= 0.0)
            {
                return 0;
            }

            if (value >= 1.0)
            {
                return 65535;
            }

            return (ushort)Math.Round(value * 65535.0, MidpointRounding.AwayFromZero);
        }

        private static void WriteU32(byte[] buffer, int offset, uint value)
        {
            buffer[offset] = (byte)(value & 0xFF);
            buffer[offset + 1] = (byte)((value >> 8) & 0xFF);
            buffer[offset + 2] = (byte)((value >> 16) & 0xFF);
            buffer[offset + 3] = (byte)((value >> 24) & 0xFF);
        }
    }
}
