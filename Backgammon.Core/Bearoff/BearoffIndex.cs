using System;

namespace Backgammon.Core
{
    /// <summary>
    /// 1 taraflı bearoff indeks şeması (Faz 5 §3.3). Koleks (colex) düzeni.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Bir tarafın pozisyonu <c>c[0..5]</c> ile temsil edilir: <c>c[i]</c> = <c>i+1</c> numaralı
    /// hanedeki taş sayısı (1-hane = toplanmaya en yakın). Toplanmış taş sayısı
    /// <c>15 − Σ c[0..5]</c> olduğundan ayrıca saklanmaz. Bu, 15'in 7 parçaya bileşimidir;
    /// sayısı <c>C(21,6) = 54264</c>'tür.
    /// </para>
    /// <para>
    /// <c>S_i = Σ_{j≤i} c[j]</c>, <c>T_i = S_i + i</c> olsun. <c>T_0 &lt; T_1 &lt; … &lt; T_5</c> ve
    /// <c>T_i ∈ [0, 20]</c> olduğundan <c>{T_i}</c> 21 elemanlı kümenin 6'lı alt kümesidir.
    /// <c>rank = Σ_{i=0..5} C(T_i, i+1)</c> bu alt kümenin <b>koleks sırasıdır</b>; dolayısıyla
    /// eşleme <c>[0, 54264)</c> üzerine birebirdir.
    /// </para>
    /// <para>
    /// Doğrulama: hepsi toplanmış ⇒ <c>T = {0,1,2,3,4,5}</c> ⇒ <c>rank = 0</c>.
    /// Hepsi 1-hanede ⇒ <c>T = {15,16,17,18,19,20}</c> ⇒ <c>rank = 54263</c>.
    /// </para>
    /// </remarks>
    public static class BearoffIndex
    {
        /// <summary>Ev bölgesindeki hane sayısı.</summary>
        public const int Points = 6;

        /// <summary>Oyuncu başına taş sayısı.</summary>
        public const int Checkers = 15;

        /// <summary>1 taraflı indeks uzayının boyutu: <c>C(21,6)</c>.</summary>
        public const int Positions = 54264;

        private const int BinomMaxN = 21;
        private const int BinomMaxK = 7;

        private static readonly int[] Binom = BuildBinom();

        private static int[] BuildBinom()
        {
            var table = new int[(BinomMaxN + 1) * BinomMaxK];
            for (int n = 0; n <= BinomMaxN; n++)
            {
                table[n * BinomMaxK] = 1;
                for (int k = 1; k < BinomMaxK; k++)
                {
                    int left = k <= n ? table[(n - 1) * BinomMaxK + (k - 1)] : 0;
                    int right = k <= n - 1 ? table[(n - 1) * BinomMaxK + k] : 0;
                    table[n * BinomMaxK + k] = left + right;
                }
            }

            return table;
        }

        /// <summary>Binom katsayısı <c>C(n, k)</c>; <c>n &gt; 21</c> veya <c>k &gt; 6</c> için 0.</summary>
        public static int Choose(int n, int k)
        {
            if (n < 0 || k < 0 || k > 6 || n > BinomMaxN)
            {
                return 0;
            }

            return Binom[n * BinomMaxK + k];
        }

        /// <summary><c>counts[0..5]</c> pozisyonunun indeksini döner.</summary>
        public static int Rank(ReadOnlySpan<byte> counts)
        {
            if (counts.Length < Points)
            {
                throw new ArgumentException("counts en az 6 eleman içermeli.", nameof(counts));
            }

            int sum = 0;
            int rank = 0;
            for (int i = 0; i < Points; i++)
            {
                sum += counts[i];
                rank += Choose(sum + i, i + 1);
            }

            if (sum > Checkers)
            {
                throw new ArgumentException("Toplam taş sayısı 15'i aşamaz: " + sum, nameof(counts));
            }

            return rank;
        }

        /// <summary><paramref name="index"/>'in <c>counts[0..5]</c> temsilini yazar.</summary>
        public static void Unrank(int index, Span<byte> counts)
        {
            if (counts.Length < Points)
            {
                throw new ArgumentException("counts en az 6 eleman içermeli.", nameof(counts));
            }

            if ((uint)index >= (uint)Positions)
            {
                throw new ArgumentOutOfRangeException(nameof(index));
            }

            int remaining = index;
            int upper = BinomMaxN; // T_6 = 21 (dış sınır)
            Span<int> t = stackalloc int[Points];

            for (int i = Points - 1; i >= 0; i--)
            {
                int k = i + 1;
                int best = i; // T_i >= i
                for (int candidate = upper - 1; candidate >= i; candidate--)
                {
                    if (Choose(candidate, k) <= remaining)
                    {
                        best = candidate;
                        break;
                    }
                }

                t[i] = best;
                remaining -= Choose(best, k);
                upper = best;
            }

            int previousSum = 0;
            for (int i = 0; i < Points; i++)
            {
                int sum = t[i] - i;
                counts[i] = (byte)(sum - previousSum);
                previousSum = sum;
            }
        }
    }
}
