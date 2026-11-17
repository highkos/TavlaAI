using System;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// <see cref="IPositionEvaluator"/> + <see cref="IPolicyEvaluator"/> ciftini
    /// <see cref="IPolicyValueEvaluator"/> olarak sunan ince adaptor.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Neden gerekli:</b> Bolum 2.1 zincir sirasi <c>MatchAwareEvaluator</c> (dis) -&gt;
    /// <c>BearoffAwareEvaluator</c> (ic) seklindedir. <see cref="MatchAwareEvaluator"/> yapicisi
    /// <see cref="IPolicyValueEvaluator"/> ister; <see cref="BearoffAwareEvaluator"/> ise Bolum 2.3
    /// uyarinca yalnizca <see cref="IPositionEvaluator"/>, <see cref="IPolicyEvaluator"/> ve
    /// <see cref="ICombinedBatchEvaluator"/> uygular. Bu adaptor, <b>Core'a dokunmadan</b> kopruyu kurar.
    /// </para>
    /// <para>Durum tutmaz; tum cagrilar dogrudan ic nesnelere iletilir.</para>
    /// </remarks>
    internal sealed class PolicyValueAdapter : IPolicyValueEvaluator
    {
        private readonly IPositionEvaluator _position;
        private readonly IPolicyEvaluator _policy;

        public PolicyValueAdapter(IPositionEvaluator position, IPolicyEvaluator policy)
        {
            if (position == null)
            {
                throw new ArgumentNullException(nameof(position));
            }

            if (policy == null)
            {
                throw new ArgumentNullException(nameof(policy));
            }

            _position = position;
            _policy = policy;
        }

        public int Version
        {
            get { return _position.Version; }
        }

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            _position.EvaluateBatch(list, offset, count, perspective, scalars, results);
        }

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> results)
        {
            _policy.ScoreBatch(list, offset, count, perspective, scalars, results);
        }
    }
}
