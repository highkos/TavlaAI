using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.6: <c>E → ME</c> dönüşümü yapan <b>maç-duyarlı</b> dekoratör.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Problem:</b> ağ tek skaler küpsüz equity üretir. <c>argmax E</c> ile <c>argmax MWC</c>
    /// aynı değildir, çünkü marsların maç skorundaki ağırlığı skora göre değişir
    /// (2-away/2-away'de mars maçı bitirir, 5-away/5-away'de bitirmez).
    /// </para>
    /// <para>
    /// <b>Çözüm:</b> <c>ME = 2·MWC − 1</c> <b>antisimetriktir</b>, bu yüzden Faz 3 v7'nin
    /// negamax'ı (<c>q_r = −V(çocuk)</c>) <b>değişmeden</b> çalışır. Ham <c>MWC</c> kullanmak
    /// negamax'ı bozar (simetri kaybolur) — bu yüzden asla ham MWC döndürülmez.
    /// </para>
    /// <para>
    /// <b>Sınır (dürüstçe):</b> bu <b>yaklaşık</b> maç-duyarlılığıdır. Kesin çözüm, ağın 6 çıktılı
    /// değer başı üretmesidir (Faz 6). Kalite, <see cref="HeuristicOutcomeDistribution"/>'ın
    /// kalitesine doğrudan bağlıdır.
    /// </para>
    /// </remarks>
    public sealed class MatchAwareEvaluator : IPositionEvaluator, IPolicyEvaluator, ICombinedBatchEvaluator
    {
        private readonly IPolicyValueEvaluator _inner;
        private readonly MatchEquityTable _met;
        private readonly IOutcomeDistributionEvaluator _distribution;
        private readonly MatchState _match;
        private readonly int _version;

        public MatchAwareEvaluator(IPolicyValueEvaluator inner, MatchEquityTable met,
                                   IOutcomeDistributionEvaluator distribution, MatchState match)
        {
            if (inner == null)
            {
                throw new ArgumentNullException(nameof(inner));
            }

            if (met == null)
            {
                throw new ArgumentNullException(nameof(met));
            }

            if (distribution == null)
            {
                throw new ArgumentNullException(nameof(distribution));
            }

            _inner = inner;
            _met = met;
            _distribution = distribution;
            _match = match;

            unchecked
            {
                _version = (int)(((uint)((IPositionEvaluator)inner).Version * 31u) +
                                 ((uint)met.Version * 17u) +
                                 ((uint)distribution.Version * 7u) +
                                 (uint)match.Hash);
            }
        }

        /// <summary>İç model, MET, dağılım ve <b>maç durumu</b> sürümlerinin bileşimi.</summary>
        public int Version
        {
            get { return _version; }
        }

        /// <summary>Dönüşümün uygulandığı maç bağlamı.</summary>
        public MatchState Match
        {
            get { return _match; }
        }

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);

            if (_match.IsMoneyGame)
            {
                return;
            }

            Span<OutcomeDistribution> buffer = count <= 256
                ? stackalloc OutcomeDistribution[count]
                : new OutcomeDistribution[count];

            _distribution.EvaluateDistributionBatch(list, offset, count, perspective, scalars, buffer);

            int awayMover = _match.AwayScore(perspective);
            int awayOpponent = _match.AwayScore(-perspective);

            for (int i = 0; i < count; i++)
            {
                double mwc = MatchWinningChance(buffer[i], awayMover, awayOpponent);
                results[offset + i] = (float)((2.0 * mwc) - 1.0);
            }
        }

        /// <summary>Tam devir: politika sıralaması <c>E</c>'ye göre yapılır (bilinçli yaklaşım).</summary>
        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }

        public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                          in VectorizerScalars scalars, Span<float> values, Span<float> priorities)
        {
            ICombinedBatchEvaluator combined = _inner as ICombinedBatchEvaluator;
            if (combined != null)
            {
                combined.EvaluateAndScoreBatch(list, offset, count, perspective, scalars, values, priorities);
            }
            else
            {
                _inner.EvaluateBatch(list, offset, count, perspective, scalars, values);
                _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
            }

            if (_match.IsMoneyGame)
            {
                return;
            }

            Span<OutcomeDistribution> buffer = count <= 256
                ? stackalloc OutcomeDistribution[count]
                : new OutcomeDistribution[count];

            _distribution.EvaluateDistributionBatch(list, offset, count, perspective, scalars, buffer);

            int awayMover = _match.AwayScore(perspective);
            int awayOpponent = _match.AwayScore(-perspective);

            for (int i = 0; i < count; i++)
            {
                double mwc = MatchWinningChance(buffer[i], awayMover, awayOpponent);
                values[offset + i] = (float)((2.0 * mwc) - 1.0);
            }
        }

        private double MatchWinningChance(OutcomeDistribution dist, int awayMover, int awayOpponent)
        {
            double winSingle = dist.Win - dist.WinGammon;
            double winGammon = dist.WinGammon - dist.WinBackgammon;
            double winBackgammon = dist.WinBackgammon;

            double lose = dist.Lose;
            double loseSingle = lose - dist.LoseGammon;
            double loseGammon = dist.LoseGammon - dist.LoseBackgammon;
            double loseBackgammon = dist.LoseBackgammon;

            double mwc = 0.0;
            mwc += winSingle * Chance(awayMover - 1, awayOpponent);
            mwc += winGammon * Chance(awayMover - 2, awayOpponent);
            mwc += winBackgammon * Chance(awayMover - 3, awayOpponent);
            mwc += loseSingle * Chance(awayMover, awayOpponent - 1);
            mwc += loseGammon * Chance(awayMover, awayOpponent - 2);
            mwc += loseBackgammon * Chance(awayMover, awayOpponent - 3);
            return mwc;
        }

        private double Chance(int awayMover, int awayOpponent)
        {
            if (awayMover <= 0)
            {
                return 1.0;
            }

            if (awayOpponent <= 0)
            {
                return 0.0;
            }

            if (awayMover > _met.MaxMatchLength || awayOpponent > _met.MaxMatchLength)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(awayMover),
                    "MET en fazla " + _met.MaxMatchLength + " puanlık maçı destekler.");
            }

            return _met.MatchWinningChance(awayMover, awayOpponent);
        }
    }
}
