using System;
using System.Collections.Generic;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Pürüzsüz, perspektife duyarlı pip-farkı hevristiği. <b>Kırpma yapmaz</b> (arama kırpar).
    /// </summary>
    /// <remarks>
    /// <c>3·d / (|d| + 50)</c> — <c>d = pipRakip − pipAktif</c>. Sonuç <c>(-3, 3)</c> aralığında
    /// pürüzsüz ve süreklidir; hiçbir yerde <c>clamp</c> yoktur.
    /// </remarks>
    internal sealed class PipDiffEvaluator : IPositionEvaluator
    {
        public int Version { get; set; }

        public int Calls;

        public int Positions;

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            if (offset != 0)
            {
                throw new ArgumentException("offset yalnızca 0 olabilir: " + offset, nameof(offset));
            }

            Calls++;
            Positions += count;

            for (int i = 0; i < count; i++)
            {
                ReadOnlySpan<sbyte> board = list.BoardOf(i);
                int active = BackgammonVectorizer.CalculatePipCount(board, perspective);
                int opp = BackgammonVectorizer.CalculatePipCount(board, -perspective);
                int diff = opp - active;
                results[i] = 3f * diff / (Math.Abs(diff) + 50f);
            }
        }
    }

    /// <summary>
    /// Faz 2 v4 <see cref="BackgammonVectorizer.VectorizeBatch"/> çıktısının bit desenlerinden
    /// deterministik, ayna-değişmez, <c>[-3,3]</c> değer üretir. <b>Kırpma yapmaz.</b>
    /// </summary>
    internal sealed class HashEvaluator : IPositionEvaluator
    {
        private readonly float[] _vectors =
            new float[AfterStateList.DefaultCapacity * BackgammonVectorizer.InputVectorSize];

        public int Version { get; set; }

        public int Calls;

        public int Positions;

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            if (offset != 0)
            {
                throw new ArgumentException("offset yalnızca 0 olabilir: " + offset, nameof(offset));
            }

            Calls++;
            Positions += count;

            var buffer = new Span<float>(_vectors, 0, count * BackgammonVectorizer.InputVectorSize);
            BackgammonVectorizer.VectorizeBatch(list, count, perspective, scalars, buffer);

            for (int i = 0; i < count; i++)
            {
                ulong h = HashOf(buffer.Slice(i * BackgammonVectorizer.InputVectorSize,
                                              BackgammonVectorizer.InputVectorSize));
                results[i] = (h % 6000001UL) / 1000000f - 3f;
            }
        }

        /// <summary>FNV-1a 64; vektörün bit desenleri üzerinde.</summary>
        internal static ulong HashOf(ReadOnlySpan<float> vector)
        {
            ulong h = 14695981039346656037UL;
            for (int i = 0; i < vector.Length; i++)
            {
                uint bits = BitConverter.SingleToUInt32Bits(vector[i]);
                h ^= bits;
                h *= 1099511628211UL;
            }

            return h;
        }
    }

    /// <summary>
    /// Aynı hash'ten türetilmiş pozitif <c>priorities</c> üretir (deterministik, allocation'sız,
    /// ayna-değişmez). Sıralamayı zorlar.
    /// </summary>
    internal sealed class HashPolicyEvaluator : IPolicyEvaluator
    {
        private readonly float[] _vectors =
            new float[AfterStateList.DefaultCapacity * BackgammonVectorizer.InputVectorSize];

        public int Version { get; set; }

        public int Calls;

        public int Positions;

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            if (offset != 0)
            {
                throw new ArgumentException("offset yalnızca 0 olabilir: " + offset, nameof(offset));
            }

            Calls++;
            Positions += count;

            if (count == 0)
            {
                return;
            }

            var buffer = new Span<float>(_vectors, 0, count * BackgammonVectorizer.InputVectorSize);
            BackgammonVectorizer.VectorizeBatch(list, count, perspective, scalars, buffer);

            float sum = 0f;
            for (int i = 0; i < count; i++)
            {
                ulong h = HashEvaluator.HashOf(buffer.Slice(i * BackgammonVectorizer.InputVectorSize,
                                                           BackgammonVectorizer.InputVectorSize));
                float w = 1f + (h % 1000UL);
                priorities[i] = w;
                sum += w;
            }

            for (int i = 0; i < count; i++)
            {
                priorities[i] /= sum;
            }
        }
    }

    /// <summary>Elle verilen (hash → değer) tablosu; tablo dışı için hata. <b>Kırpma yapmaz.</b></summary>
    internal sealed class TableEvaluator : IPositionEvaluator
    {
        private readonly Dictionary<ulong, float> _table;

        public TableEvaluator(Dictionary<ulong, float> table)
        {
            _table = table ?? throw new ArgumentNullException(nameof(table));
        }

        public int Version { get; set; }

        public int Calls;

        public int Positions;

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            if (offset != 0)
            {
                throw new ArgumentException("offset yalnızca 0 olabilir: " + offset, nameof(offset));
            }

            Calls++;
            Positions += count;

            for (int i = 0; i < count; i++)
            {
                ulong h = list.Hash[i];
                if (!_table.TryGetValue(h, out float v))
                {
                    throw new InvalidOperationException("TableEvaluator: tablo dışı hash 0x" + h.ToString("X16"));
                }

                results[i] = v;
            }
        }
    }

    /// <summary>Çağrı ve pozisyon sayan sarmalayıcı.</summary>
    internal sealed class CountingEvaluator : IPositionEvaluator
    {
        private readonly IPositionEvaluator _inner;

        public CountingEvaluator(IPositionEvaluator inner)
        {
            _inner = inner ?? throw new ArgumentNullException(nameof(inner));
        }

        public int Calls;

        public int Positions;

        public int Version
        {
            get { return _inner.Version; }
        }

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            Calls++;
            Positions += count;
            _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);
        }
    }

    /// <summary>Politika çağrılarını sayan sarmalayıcı.</summary>
    internal sealed class CountingPolicyEvaluator : IPolicyEvaluator
    {
        private readonly IPolicyEvaluator _inner;

        public CountingPolicyEvaluator(IPolicyEvaluator inner)
        {
            _inner = inner ?? throw new ArgumentNullException(nameof(inner));
        }

        public int Calls;

        public int Positions;

        public int Version
        {
            get { return _inner.Version; }
        }

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            Calls++;
            Positions += count;
            _inner.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }
    }

    /// <summary>Tüm <c>priorities = 1/count</c>; sıralama indeks sırasına düşer.</summary>
    internal sealed class ConstantPolicyEvaluator : IPolicyEvaluator
    {
        public int Version { get; set; }

        public int Calls;

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            Calls++;
            float p = count > 0 ? 1f / count : 0f;
            for (int i = 0; i < count; i++)
            {
                priorities[i] = p;
            }
        }
    }

    /// <summary><c>priorities</c>'i ters sırayla üretir (en kötü aday önce).</summary>
    internal sealed class AdversarialPolicyEvaluator : IPolicyEvaluator
    {
        public int Version { get; set; }

        public int Calls;

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            Calls++;
            if (count == 0)
            {
                return;
            }

            float denom = count * (count + 1) * 0.5f;
            for (int i = 0; i < count; i++)
            {
                priorities[i] = (count - i) / denom;
            }
        }
    }

    /// <summary>
    /// <see cref="ICombinedBatchEvaluator"/> çağrılarını sayar ve ayrı çağrılarla aynı sonucu
    /// ürettiğini doğrular (Test 16).
    /// </summary>
    internal sealed class CombinedSpyEvaluator : IPositionEvaluator, IPolicyEvaluator, ICombinedBatchEvaluator
    {
        private readonly IPositionEvaluator _value;
        private readonly IPolicyEvaluator _policy;

        public CombinedSpyEvaluator(IPositionEvaluator value, IPolicyEvaluator policy)
        {
            _value = value ?? throw new ArgumentNullException(nameof(value));
            _policy = policy ?? throw new ArgumentNullException(nameof(policy));
        }

        public int CombinedCalls;

        public int EvaluateCalls;

        public int ScoreCalls;

        public int Version
        {
            get { return _value.Version; }
        }

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            EvaluateCalls++;
            _value.EvaluateBatch(list, offset, count, perspective, scalars, results);
        }

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            ScoreCalls++;
            _policy.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }

        public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                          in VectorizerScalars scalars, Span<float> results, Span<float> priorities)
        {
            CombinedCalls++;
            _value.EvaluateBatch(list, offset, count, perspective, scalars, results);
            _policy.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }
    }

    /// <summary><c>priorities</c>'i negatif uretir (0'a kirpilma testi, Test 14).</summary>
    internal sealed class NegativePolicyEvaluator : IPolicyEvaluator
    {
        public int Version { get; set; }

        public int Calls;

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            Calls++;
            for (int i = 0; i < count; i++)
            {
                priorities[i] = -1f - i;
            }
        }
    }

    /// <summary>
    /// <see cref="Version"/> degistikce degeri kayan sarmalayici (Test 17: model yeniden yukleme).
    /// </summary>
    internal sealed class VersionedEvaluator : IPositionEvaluator
    {
        private readonly IPositionEvaluator _inner;

        public VersionedEvaluator(IPositionEvaluator inner)
        {
            _inner = inner ?? throw new ArgumentNullException(nameof(inner));
        }

        public int Version { get; set; }

        public int Calls;

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            Calls++;
            _inner.EvaluateBatch(list, offset, count, perspective, scalars, results);

            float delta = Version * 0.5f;
            for (int i = 0; i < count; i++)
            {
                results[i] += delta;
            }
        }
    }
}