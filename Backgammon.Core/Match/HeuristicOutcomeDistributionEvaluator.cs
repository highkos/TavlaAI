using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.3: <see cref="HeuristicOutcomeDistribution"/>'ı <see cref="IOutcomeDistributionEvaluator"/>
    /// olarak sunan sarmalayıcı. İç değerlendiricinin skaler equity'sini 6'lı dağılıma çevirir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Temas bilgisi ve pip farkı tahtadan <b>türetilir</b> (bkz. <see cref="IsPureRace"/>,
    /// <see cref="PipDifference"/>). Deterministik ve allocation'sızdır.
    /// </para>
    /// <para>
    /// Faz 6'da bu sınıfın yerini ağın 6 çıktılı değer başı alacak; arayüz değişmeyecek.
    /// </para>
    /// </remarks>
    public sealed class HeuristicOutcomeDistributionEvaluator : IOutcomeDistributionEvaluator
    {
        private readonly IPositionEvaluator _inner;
        private readonly int _version;

        public HeuristicOutcomeDistributionEvaluator(IPositionEvaluator inner)
        {
            if (inner == null)
            {
                throw new ArgumentNullException(nameof(inner));
            }

            _inner = inner;
            unchecked
            {
                _version = (int)(((uint)inner.Version * 131u) + 0x5EEDu);
            }
        }

        public int Version
        {
            get { return _version; }
        }

        public void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                              in VectorizerScalars scalars, Span<OutcomeDistribution> results)
        {
            if (list == null)
            {
                throw new ArgumentNullException(nameof(list));
            }

            if (offset != 0)
            {
                throw new ArgumentException("offset şu an yalnızca 0 olabilir.", nameof(offset));
            }

            if (count < 0 || count > list.Count)
            {
                throw new ArgumentOutOfRangeException(nameof(count));
            }

            if (results.Length < count)
            {
                throw new ArgumentException("results.Length >= count olmalı.", nameof(results));
            }

            if (count == 0)
            {
                return;
            }

            Span<float> equities = count <= 256 ? stackalloc float[count] : new float[count];
            _inner.EvaluateBatch(list, offset, count, perspective, scalars, equities);

            for (int i = 0; i < count; i++)
            {
                ReadOnlySpan<sbyte> board = list.BoardOf(i);
                bool contact = !IsPureRace(board);
                int pip = PipDifference(board, perspective);
                results[i] = HeuristicOutcomeDistribution.FromEquity(equities[i], contact, pip);
            }
        }

        /// <summary>
        /// Saf yarış mı? Beyazın en gerideki taşı, Siyahın en ilerideki taşından öndeyse temas yoktur.
        /// Bar'da taş varsa daima temas vardır.
        /// </summary>
        public static bool IsPureRace(ReadOnlySpan<sbyte> board)
        {
            if (board[0] != 0 || board[25] != 0)
            {
                return false;
            }

            int whiteRearmost = 0;
            int blackRearmost = 26;
            for (int p = 1; p <= 24; p++)
            {
                sbyte v = board[p];
                if (v > 0 && p > whiteRearmost)
                {
                    whiteRearmost = p;
                }

                if (v < 0 && p < blackRearmost)
                {
                    blackRearmost = p;
                }
            }

            if (whiteRearmost == 0 || blackRearmost == 26)
            {
                return true;
            }

            return whiteRearmost < blackRearmost;
        }

        /// <summary>Beyaz pip sayısı eksi Siyah pip sayısı (Beyaz perspektifinden pozitif = Beyaz önde).</summary>
        public static int PipDifference(ReadOnlySpan<sbyte> board, int perspective)
        {
            int white = 0;
            int black = 0;
            for (int p = 1; p <= 24; p++)
            {
                sbyte v = board[p];
                if (v > 0)
                {
                    white += v * (25 - p);
                }
                else if (v < 0)
                {
                    black += -v * p;
                }
            }

            white += board[0] * 25;
            black += -board[25] * 25;

            int diff = white - black;
            return perspective > 0 ? diff : -diff;
        }
    }
}
