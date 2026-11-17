using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 2 v4: Faz 1 motorunun ham durumunu 221 elemanli sabit <c>float</c> vektörüne dönüstürür.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Hot path sözlesmesi: <see cref="Vectorize(BackgammonState,int,Span{float})"/> icinde
    /// <c>new</c>, LINQ, lambda, string islemi veya döngü icinde nesne türetimi YASAKTIR.
    /// Cikti cagiranin verdigi <see cref="Span{T}"/> üzerine yazilir; steady-state'te 0 byte tahsis.
    /// </para>
    /// <para>
    /// Vektör <b>zar atilmamis (pre-roll)</b> pozisyonu temsil eder: <c>rolledDice</c> ve
    /// <c>remainingDice</c> okunmaz. Terminal pozisyonlar (<c>borneOff == 15</c>) ve mac bitmis
    /// pozisyonlar (<c>away &lt;= 0</c>) vektörlestirilmez; <see cref="ArgumentException"/> atilir.
    /// </para>
    /// <para>
    /// .NET Standard 2.1 uyumu: <c>BitOperations</c> ve <c>Math.Log2</c> KULLANILMAZ.
    /// </para>
    /// </remarks>
    public static class BackgammonVectorizer
    {
        /// <summary>Vektör semasinin sürümü. Sema degisirse artirilir.</summary>
        public const int FeatureVersion = 1;

        /// <summary>Giris vektörünün eleman sayisi (<see cref="VectorLayout.TotalSize"/> ile ayni).</summary>
        public const int InputVectorSize = VectorLayout.TotalSize;

        /// <summary>Pip normalizasyon böleni (baslangic pozisyonu pip sayisi).</summary>
        public const float PipDivisor = 167f;

        // ------------------------------------------------------------------
        // Ana giris noktalari
        // ------------------------------------------------------------------

        /// <summary>
        /// State'i vektörlestirir. <paramref name="output"/> en az 221 uzunlukta olmali; ilk 221
        /// elemanin TAMAMI yazilir (kirli buffer'a güvenilmez).
        /// </summary>
        /// <exception cref="ArgumentException">
        /// <paramref name="output"/> 221'den kisa; <paramref name="perspective"/> ±1 degil;
        /// oyun bitmis (<c>borneOff == 15</c>) veya mac bitmis (<c>away &lt;= 0</c>).
        /// </exception>
        public static void Vectorize(BackgammonState state, int perspective, Span<float> output)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            ValidateOutput(output, nameof(output));
            ValidatePerspective(perspective, nameof(perspective));
            ValidateNotTerminal(state.whiteBorneOff, state.blackBorneOff, state.matchLength,
                                state.whiteScore, state.blackScore);

            VectorizeCore(state.board, state.whiteBorneOff, state.blackBorneOff,
                          VectorizerScalars.From(state), perspective, output);
        }

        /// <summary>
        /// Hafif giris: <see cref="BackgammonState"/> nesnesi kurmadan calisir.
        /// <paramref name="board"/> 26 elemanli (Bölüm 1 düzeni); borneOff'lar ayri parametrelerden.
        /// </summary>
        public static void Vectorize(ReadOnlySpan<sbyte> board, int whiteBorneOff, int blackBorneOff,
                                     in VectorizerScalars scalars, int perspective, Span<float> output)
        {
            ValidateBoard(board, nameof(board));
            ValidateOutput(output, nameof(output));
            ValidatePerspective(perspective, nameof(perspective));
            ValidateNotTerminal(whiteBorneOff, blackBorneOff, scalars.MatchLength,
                                scalars.WhiteScore, scalars.BlackScore);

            VectorizeCore(board, whiteBorneOff, blackBorneOff, scalars, perspective, output);
        }

        /// <summary>
        /// <see cref="AfterStateList"/>'in ilk <paramref name="count"/> kaydini tek bitisik buffer'a
        /// yazar: satir <c>i</c> = <c>output.Slice(i * 221, 221)</c>.
        /// </summary>
        /// <remarks>
        /// Her kaydin board'u ve <c>WhiteBorneOff</c>/<c>BlackBorneOff</c>'u LISTEDEN okunur.
        /// <c>ResultType</c>/<c>ResultPoints</c> vektörlestirilmez.
        /// </remarks>
        /// <exception cref="ArgumentException">
        /// <paramref name="count"/> negatif veya <c>list.Count</c>'tan büyük; <paramref name="output"/>
        /// <c>count * 221</c>'den kisa; herhangi bir kayit terminal (<c>IsTerminal[i] == true</c>);
        /// mac bitmis.
        /// </exception>
        public static void VectorizeBatch(AfterStateList list, int count, int perspective,
                                          in VectorizerScalars scalars, Span<float> output)
        {
            if (list == null)
            {
                throw new ArgumentNullException(nameof(list));
            }

            if (count < 0 || count > list.Count)
            {
                throw new ArgumentException("count 0.." + list.Count + " araliginda olmali: " + count, nameof(count));
            }

            ValidatePerspective(perspective, nameof(perspective));

            if (output.Length < count * InputVectorSize)
            {
                throw new ArgumentException(
                    "output en az " + (count * InputVectorSize) + " eleman olmali: " + output.Length, nameof(output));
            }

            ValidateNotTerminal(0, 0, scalars.MatchLength, scalars.WhiteScore, scalars.BlackScore);

            for (int i = 0; i < count; i++)
            {
                if (list.IsTerminal[i] ||
                    list.WhiteBorneOff[i] >= BackgammonState.PiecesPerPlayer ||
                    list.BlackBorneOff[i] >= BackgammonState.PiecesPerPlayer)
                {
                    throw new ArgumentException(
                        "Terminal kayit vektörlestirilemez (kayit " + i + ").", nameof(list));
                }
            }

            for (int i = 0; i < count; i++)
            {
                VectorizeCore(list.BoardOf(i), list.WhiteBorneOff[i], list.BlackBorneOff[i],
                              scalars, perspective, output.Slice(i * InputVectorSize, InputVectorSize));
            }
        }

        // ------------------------------------------------------------------
        // Yardimci fonksiyonlar (Aşama B)
        // ------------------------------------------------------------------

        /// <summary>Oyuncunun pip sayisi; bar tasi 25 sayilir.</summary>
        /// <remarks>Baslangic pozisyonu 167, en kötü durum (15 tas barda) 375.</remarks>
        public static int CalculatePipCount(ReadOnlySpan<sbyte> board, int player)
        {
            ValidateBoard(board, nameof(board));
            ValidatePlayer(player, nameof(player));

            int total = 0;
            for (int point = 1; point <= 24; point++)
            {
                int n = CountOf(board[point], player);
                if (n != 0)
                {
                    total += n * BackgammonEngine.DistanceToOff(point, player);
                }
            }

            int bar = CountOf(board[BackgammonEngine.BarIndex(player)], player);
            if (bar != 0)
            {
                total += bar * 25;
            }

            return total;
        }

        /// <summary>Oyuncunun kacak tas sayisi (Bölüm 3.3).</summary>
        /// <remarks>
        /// Kacak = <c>j &lt; jOppMin</c> olan tahtadaki tas. Bar ve toplanmis taslar sayilmaz.
        /// Rakip barda tas varsa <c>jOppMin = 0</c>; rakip tamamen toplanmissa <c>jOppMin = +inf</c>.
        /// </remarks>
        public static int GetEscapedCheckersCount(ReadOnlySpan<sbyte> board, int player)
        {
            ValidateBoard(board, nameof(board));
            ValidatePlayer(player, nameof(player));

            int jOppMin = ComputeOpponentMinJ(board, player);
            if (jOppMin <= 0)
            {
                return 0;
            }

            int count = 0;
            for (int point = 1; point <= 24; point++)
            {
                int n = CountOf(board[point], player);
                if (n != 0 && BackgammonEngine.DistanceToOff(point, player) < jOppMin)
                {
                    count += n;
                }
            }

            return count;
        }

        /// <summary>Temas var mi (Bölüm 3.4). Perspektiften bagimsiz, simetrik.</summary>
        /// <remarks>
        /// <c>aktifMaxJ &gt; jOppMin</c>. <c>+1</c> perspektifiyle hesaplamak yeterlidir: aynalama
        /// altinda kosul <c>maxSiyah &gt; minBeyaz</c> bicimine indirgenir ve iki perspektifte aynidir.
        /// </remarks>
        public static bool IsContact(ReadOnlySpan<sbyte> board)
        {
            ValidateBoard(board, nameof(board));

            return ComputeActiveMaxJ(board, 1) > ComputeOpponentMinJ(board, 1);
        }

        public static int CalculatePipCount(BackgammonState state, int player)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            return CalculatePipCount(state.board, player);
        }

        public static int GetEscapedCheckersCount(BackgammonState state, int player)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            return GetEscapedCheckersCount(state.board, player);
        }

        public static bool IsContact(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            return IsContact(state.board);
        }

        // ------------------------------------------------------------------
        // Dogrulama (Aşama A iskeleti — Bölüm 4.1)
        // ------------------------------------------------------------------

        private static void ValidateOutput(Span<float> output, string name)
        {
            if (output.Length < InputVectorSize)
            {
                throw new ArgumentException(
                    "output en az " + InputVectorSize + " eleman olmali: " + output.Length, name);
            }
        }

        private static void ValidateBoard(ReadOnlySpan<sbyte> board, string name)
        {
            if (board.Length < BackgammonState.BoardSize)
            {
                throw new ArgumentException(
                    "board en az " + BackgammonState.BoardSize + " eleman olmali: " + board.Length, name);
            }
        }

        private static void ValidatePerspective(int perspective, string name)
        {
            if (perspective != 1 && perspective != -1)
            {
                throw new ArgumentException("perspective +1 veya -1 olmali: " + perspective, name);
            }
        }

        private static void ValidatePlayer(int player, string name)
        {
            if (player != 1 && player != -1)
            {
                throw new ArgumentException("player +1 veya -1 olmali: " + player, name);
            }
        }

        /// <summary>Bölüm 4.1: terminal ve mac bitisi reddi.</summary>
        private static void ValidateNotTerminal(int whiteBorneOff, int blackBorneOff,
                                                int matchLength, int whiteScore, int blackScore)
        {
            if (whiteBorneOff >= BackgammonState.PiecesPerPlayer ||
                blackBorneOff >= BackgammonState.PiecesPerPlayer)
            {
                throw new ArgumentException(
                    "Terminal pozisyon vektörlestirilemez (borneOff = " + whiteBorneOff + "/" + blackBorneOff + ").");
            }

            if (matchLength > 0)
            {
                int whiteAway = matchLength - whiteScore;
                int blackAway = matchLength - blackScore;
                if (whiteAway <= 0 || blackAway <= 0)
                {
                    throw new ArgumentException(
                        "Mac bitmis pozisyon vektörlestirilemez (away = " + whiteAway + "/" + blackAway + ").");
                }
            }
        }

        // ------------------------------------------------------------------
        // Cekirdek (Aşama B/C)
        // ------------------------------------------------------------------

        private static void VectorizeCore(ReadOnlySpan<sbyte> board, int whiteBorneOff, int blackBorneOff,
                                          in VectorizerScalars scalars, int perspective, Span<float> output)
        {
            // Hane bloklari 0-191.
            for (int point = 1; point <= 24; point++)
            {
                int v = board[point];
                int activeN = perspective > 0 ? (v > 0 ? v : 0) : (v < 0 ? -v : 0);
                int oppN = perspective > 0 ? (v < 0 ? -v : 0) : (v > 0 ? v : 0);
                int j = BackgammonEngine.DistanceToOff(point, perspective);

                WritePointBlock(output, VectorLayout.ActiveOffset + VectorLayout.PointBlockSize * (j - 1), activeN);
                WritePointBlock(output, VectorLayout.OppOffset + VectorLayout.PointBlockSize * (j - 1), oppN);
            }

            // Sistem nöronlari 192-220.
            int activeBar = CountOf(board[BackgammonEngine.BarIndex(perspective)], perspective);
            int oppBar = CountOf(board[BackgammonEngine.BarIndex(-perspective)], -perspective);

            output[VectorLayout.ActiveBar] = activeBar / 2f;
            output[VectorLayout.OppBar] = oppBar / 2f;
            output[VectorLayout.ActiveOff] = (perspective > 0 ? whiteBorneOff : blackBorneOff) / 15f;
            output[VectorLayout.OppOff] = (perspective > 0 ? blackBorneOff : whiteBorneOff) / 15f;
            output[VectorLayout.CubeOwner] = scalars.CubeOwner * perspective;
            output[VectorLayout.CubeValue] = CubeValueNeuron(scalars.CubeValue);
            output[VectorLayout.IsMoneyGame] = scalars.MatchLength == 0 ? 1f : 0f;
            output[VectorLayout.IsCrawford] = scalars.IsCrawfordGame ? 1f : 0f;
            output[VectorLayout.ActivePip] = CalculatePipCount(board, perspective) / PipDivisor;
            output[VectorLayout.OppPip] = CalculatePipCount(board, -perspective) / PipDivisor;
            output[VectorLayout.ActiveEscaped] = GetEscapedCheckersCount(board, perspective) / 15f;
            output[VectorLayout.OppEscaped] = GetEscapedCheckersCount(board, -perspective) / 15f;
            output[VectorLayout.IsContact] = IsContact(board) ? 1f : 0f;

            for (int i = 0; i < VectorLayout.AwayBuckets; i++)
            {
                output[VectorLayout.ActiveAwayOffset + i] = 0f;
                output[VectorLayout.OppAwayOffset + i] = 0f;
            }

            if (scalars.MatchLength > 0)
            {
                int activeAway = scalars.MatchLength - (perspective > 0 ? scalars.WhiteScore : scalars.BlackScore);
                int oppAway = scalars.MatchLength - (perspective > 0 ? scalars.BlackScore : scalars.WhiteScore);
                output[VectorLayout.ActiveAwayOffset + AwayBucket(activeAway)] = 1f;
                output[VectorLayout.OppAwayOffset + AwayBucket(oppAway)] = 1f;
            }
        }

        /// <summary>Bölüm 2: <c>min(log2(cubeValue) / 6, 1)</c>. <c>cubeValue</c> 2'nin kuvvetidir.</summary>
        private static float CubeValueNeuron(int cubeValue)
        {
            if (cubeValue <= 1)
            {
                return 0f;
            }

            int log2 = 0;
            int power = 1;
            while (power < cubeValue)
            {
                power <<= 1;
                log2++;
            }

            float value = log2 / 6f;
            return value > 1f ? 1f : value;
        }

        /// <summary>Bölüm 2: <c>away</c> degerinin tek-sicak kova indeksi (0..7).</summary>
        private static int AwayBucket(int away)
        {
            return (away < VectorLayout.AwayBuckets ? away : VectorLayout.AwayBuckets) - 1;
        }

        /// <summary>Bölüm 2: bir hanenin 4 nöronu (blot, kapi, 3+, yogunluk).</summary>
        private static void WritePointBlock(Span<float> output, int offset, int n)
        {
            output[offset + VectorLayout.Blot] = n == 1 ? 1f : 0f;
            output[offset + VectorLayout.Gate] = n >= 2 ? 1f : 0f;
            output[offset + VectorLayout.ThreePlus] = n >= 3 ? 1f : 0f;
            output[offset + VectorLayout.Density] = n > 3 ? (n - 3) / 2f : 0f;
        }

        /// <summary>Bir hanedeki tas sayisinin isaretli degerden cikarilmasi.</summary>
        private static int CountOf(sbyte value, int player)
        {
            if (player > 0)
            {
                return value > 0 ? value : 0;
            }

            return value < 0 ? -value : 0;
        }

        /// <summary>Bölüm 3.2: <c>aktifMaxJ</c>. Barda tas varsa 25, tahtada tas yoksa 0.</summary>
        private static int ComputeActiveMaxJ(ReadOnlySpan<sbyte> board, int player)
        {
            if (CountOf(board[BackgammonEngine.BarIndex(player)], player) > 0)
            {
                return 25;
            }

            int maxJ = 0;
            for (int point = 1; point <= 24; point++)
            {
                if (CountOf(board[point], player) > 0)
                {
                    int j = BackgammonEngine.DistanceToOff(point, player);
                    if (j > maxJ)
                    {
                        maxJ = j;
                    }
                }
            }

            return maxJ;
        }

        /// <summary>
        /// Bölüm 3.1: <c>jOppMin</c>. Rakip barda tas varsa 0; tahtada hic tasi yoksa
        /// (tamamen toplanmis) <see cref="int.MaxValue"/>; aksi halde en kücük <c>j</c>.
        /// </summary>
        private static int ComputeOpponentMinJ(ReadOnlySpan<sbyte> board, int player)
        {
            int opponent = -player;

            if (CountOf(board[BackgammonEngine.BarIndex(opponent)], opponent) > 0)
            {
                return 0;
            }

            int minJ = int.MaxValue;
            for (int point = 1; point <= 24; point++)
            {
                if (CountOf(board[point], opponent) > 0)
                {
                    int j = BackgammonEngine.DistanceToOff(point, player);
                    if (j < minJ)
                    {
                        minJ = j;
                    }
                }
            }

            return minJ;
        }
    }
}