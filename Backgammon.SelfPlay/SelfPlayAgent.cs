using System;
using Backgammon.Core;
using Backgammon.Inference;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.1: tek bir oyuncu ajaninin arama kaynaklari.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Her ajan kendi <see cref="SearchWorkspace"/> ve <see cref="OnnxPolicyValueEvaluator"/>
    /// ornegine sahiptir; <see cref="OnnxModelHandle"/> ise is parcaciklari arasinda
    /// <b>paylasilir</b> (Faz 4 v3 Bolum 4.4, Test 14).
    /// </para>
    /// <para>
    /// Oz-oyunda iki taraf da ayni ajani kullanir (tek evaluator, tek workspace). Havuz
    /// rakipli oyunda iki ayri ajan vardir; havuz ajani <c>IsLearner = 0</c> kararlar uretir.
    /// </para>
    /// </remarks>
    public sealed class SelfPlayAgent : IDisposable
    {
        private readonly OnnxPolicyValueEvaluator _evaluator;

        /// <summary>Yeni bir ajan olusturur.</summary>
        /// <param name="model">Paylasilan model tanitici.</param>
        /// <param name="options">ONNX oturum secenekleri.</param>
        /// <param name="settings">Arama ayarlari.</param>
        public SelfPlayAgent(OnnxModelHandle model, OnnxEvaluatorOptions options, in SearchSettings settings)
        {
            if (model == null)
            {
                throw new ArgumentNullException(nameof(model));
            }

            if (options == null)
            {
                throw new ArgumentNullException(nameof(options));
            }

            _evaluator = new OnnxPolicyValueEvaluator(model, options);
            Workspace = new SearchWorkspace();
            Settings = settings;
        }

        /// <summary>Arama calisma alani.</summary>
        public SearchWorkspace Workspace { get; }

        /// <summary>Arama ayarlari.</summary>
        public SearchSettings Settings { get; set; }

        /// <summary>Deger/politika degerlendiricisi.</summary>
        public OnnxPolicyValueEvaluator Evaluator
        {
            get { return _evaluator; }
        }

        /// <summary>Model surumu (shard basligi icin).</summary>
        public uint ModelVersion
        {
            get { return _evaluator.Model.ModelVersion; }
        }

        /// <inheritdoc/>
        public void Dispose()
        {
            _evaluator.Dispose();
        }
    }
}
