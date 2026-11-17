using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §3.5: bearoff veritabanını arama ile sinir ağı arasına <b>decorator</b> olarak yerleştiren
    /// değerlendirici. Bearoff'ta çözülebilen kayıtların equity'sini <b>tam</b> değerle değiştirir;
    /// diğer kayıtlar iç değerlendiriciden geldiği gibi kalır.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Strateji: "overwrite".</b> Toplu çağrı bölümlenmez, <see cref="AfterStateList"/> API'si
    /// değiştirilmez. İç değerlendirici tüm aralık için bir kez çağrılır, sonra bearoff kayıtları
    /// üzerine yazılır. <see cref="BearoffAwareOptions.SkipInnerForPureBearoffBatches"/> açıkken ve
    /// aralıktaki tüm kayıtlar çözülebilirse iç çağrı tamamen atlanır.
    /// </para>
    /// <para>
    /// <b><see cref="ScoreBatch"/> tam geçişlidir.</b> Politika yalnızca sıralamayı etkiler; bearoff
    /// equity'sini logit ölçeğine karıştırmak grup softmax'ını bozar.
    /// </para>
    /// <para>
    /// <b>Kırpma yapılmaz.</b> <c>[-3,3]</c> kırpması aramanın sorumluluğundadır (F4-02). Yalnızca
    /// savunmacı <c>float.IsFinite</c> kontrolü vardır.
    /// </para>
    /// <para>
    /// <b>Allocation:</b> <see cref="EvaluateBatch"/> ısınma sonrası heap allocation yapmaz.
    /// </para>
    /// </remarks>
    public sealed class BearoffAwareEvaluator : IPositionEvaluator, IPolicyEvaluator, ICombinedBatchEvaluator,
                                                IExactValueEvaluator
    {
        private readonly IPolicyValueEvaluator _inner;
        private readonly BearoffDatabase _database;
        private readonly BearoffAwareOptions _options;
        private readonly float[] _cdfOnRoll;
        private readonly float[] _cdfOpponent;
        private readonly int _version;

        public BearoffAwareEvaluator(IPolicyValueEvaluator inner, BearoffDatabase database,
                                     BearoffAwareOptions options)
        {
            if (inner == null)
            {
                throw new ArgumentNullException(nameof(inner));
            }

            if (database == null)
            {
                throw new ArgumentNullException(nameof(database));
            }

            _inner = inner;
            _database = database;
            _options = options ?? BearoffAwareOptions.Default;

            int rowLength = database.MaxRolls + 1;
            _cdfOnRoll = new float[rowLength];
            _cdfOpponent = new float[rowLength];
            _version = unchecked((((IPositionEvaluator)inner).Version * 31) + database.Version);
        }

        /// <summary>İç değerlendirici.</summary>
        public IPolicyValueEvaluator Inner
        {
            get { return _inner; }
        }

        /// <summary>Kullanılan veritabanı.</summary>
        public BearoffDatabase Database
        {
            get { return _database; }
        }

        /// <summary>Bearoff çözümü bu yapılandırmada etkin mi?</summary>
        public bool IsBearoffActive
        {
            get { return !_options.DisableBearoff && _database.MaxRolls > 0; }
        }

        /// <summary>İç model sürümü ile DB sürümünün bileşimi.</summary>
        public int Version
        {
            get { return _version; }
        }

        /// <summary>
        /// Faz 6 §9.4: bu pozisyon için arama yapmadan <b>kesin</b> equity verilebiliyor mu?
        /// </summary>
        /// <remarks>
        /// Bearoff etkin değilse veya iki taraf da tek taraflı bearoff değilse <c>false</c>.
        /// Saf yarışta kesin değer her derinlikteki arama sonucuna eşit olduğu için
        /// <see cref="SearchSettings.UseBearoffCutoff"/> sonucu değiştirmez.
        /// </remarks>
        public bool IsExactFor(ReadOnlySpan<sbyte> board)
        {
            return IsBearoffActive && IsSolvable(board);
        }

        // ------------------------------------------------------------------
        // IPositionEvaluator
        // ------------------------------------------------------------------

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            Validate(list, offset, count, results);
            if (count == 0)
            {
                return;
            }

            if (!IsBearoffActive)
            {
                _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);
                return;
            }

            bool allSolvable = _options.SkipInnerForPureBearoffBatches
                               && AllSolvable(list, offset, count);

            if (!allSolvable)
            {
                _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);
            }

            int end = offset + count;
            for (int i = offset; i < end; i++)
            {
                if (TryExactEquity(list, i, perspective, out float equity))
                {
                    results[i] = equity;
                }
            }
        }

        // ------------------------------------------------------------------
        // IPolicyEvaluator — tam geçiş
        // ------------------------------------------------------------------

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }

        // ------------------------------------------------------------------
        // ICombinedBatchEvaluator
        // ------------------------------------------------------------------

        public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                          in VectorizerScalars scalars, Span<float> results,
                                          Span<float> priorities)
        {
            Validate(list, offset, count, results);
            if (count == 0)
            {
                return;
            }

            if (!IsBearoffActive || !AnySolvable(list, offset, count))
            {
                if (_inner is ICombinedBatchEvaluator combined)
                {
                    combined.EvaluateAndScoreBatch(list, offset, count, perspective, scalars, results, priorities);
                }
                else
                {
                    _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);
                    _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
                }

                return;
            }

            // Öncelikler tüm aday kümesi üzerinde normalize edilmeli; bu yüzden iki ayrı çağrı.
            EvaluateBatch(list, offset, count, perspective, scalars, results);
            _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }

        // ------------------------------------------------------------------
        // Bearoff çözümü
        // ------------------------------------------------------------------

        /// <summary>İki taraf da 1 taraflı bearoff ise oyun saf yarıştır ve tam çözülebilir.</summary>
        public static bool IsSolvable(ReadOnlySpan<sbyte> board)
        {
            return BearoffDatabase.IsOneSidedBearoff(board, 1)
                   && BearoffDatabase.IsOneSidedBearoff(board, -1);
        }

        private bool AllSolvable(AfterStateList list, int offset, int count)
        {
            int end = offset + count;
            for (int i = offset; i < end; i++)
            {
                if (!IsSolvable(BoardOf(list, i)))
                {
                    return false;
                }
            }

            return true;
        }

        private bool AnySolvable(AfterStateList list, int offset, int count)
        {
            int end = offset + count;
            for (int i = offset; i < end; i++)
            {
                if (IsSolvable(BoardOf(list, i)))
                {
                    return true;
                }
            }

            return false;
        }

        private static ReadOnlySpan<sbyte> BoardOf(AfterStateList list, int index)
        {
            return new ReadOnlySpan<sbyte>(list.Boards, index * AfterStateList.BoardSize,
                                           AfterStateList.BoardSize);
        }

        /// <summary>
        /// Faz 5 §3.7: saf yarış için tam equity. <paramref name="perspective"/> hamleyi yapan taraf;
        /// afterstate'te sırada olan taraf <c>-perspective</c>'tir.
        /// </summary>
        /// <remarks>
        /// Sırada olan <c>A</c>, rakip <c>B</c>. <c>A</c> önce oynar; <c>A</c> k. turunda toplarsa
        /// <c>B</c> yalnızca <c>k-1</c> tur atmış olur, dolayısıyla
        /// <c>P(A kazanır) = Σ_k pA[k] · (1 − cdfB[k−1])</c>.
        /// </remarks>
        private bool TryExactEquity(AfterStateList list, int index, int perspective, out float equity)
        {
            equity = 0f;

            ReadOnlySpan<sbyte> board = BoardOf(list, index);
            if (!IsSolvable(board))
            {
                return false;
            }

            int onRoll = -perspective;
            if (!_database.TryGetCdf(board, onRoll, _cdfOnRoll))
            {
                return false;
            }

            if (!_database.TryGetCdf(board, perspective, _cdfOpponent))
            {
                return false;
            }

            int maxRolls = _database.MaxRolls;
            float onRollWins = 0f;
            float previous = 0f;
            for (int k = 1; k <= maxRolls; k++)
            {
                float current = _cdfOnRoll[k];
                float p = current - previous;
                previous = current;
                if (p <= 0f)
                {
                    continue;
                }

                onRollWins += p * (1f - _cdfOpponent[k - 1]);
            }

            if (onRollWins < 0f)
            {
                onRollWins = 0f;
            }
            else if (onRollWins > 1f)
            {
                onRollWins = 1f;
            }

            // Mars/bacgammon saf yarışta imkânsızdır; E = P(win) − P(lose).
            equity = 1f - (2f * onRollWins);

            if (!float.IsFinite(equity))
            {
                throw new InvalidOperationException(
                    "Bearoff veritabanı sonlu olmayan equity üretti: " + equity);
            }

            return true;
        }

        // ------------------------------------------------------------------
        // Sözleşme denetimleri
        // ------------------------------------------------------------------

        private static void Validate(AfterStateList list, int offset, int count, Span<float> results)
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
                throw new ArgumentException("results en az count eleman içermeli.", nameof(results));
            }

            for (int i = offset; i < offset + count; i++)
            {
                if (list.IsTerminal[i])
                {
                    throw new ArgumentException(
                        "Terminal kayıt değerlendiriciye gönderilemez (indeks " + i + ").", nameof(list));
                }
            }
        }
    }
}
