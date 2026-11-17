using System;

namespace Backgammon.Inference
{
    /// <summary>
    /// Faz 4 v3 Bolum 4.1: ONNX Runtime oturum/calistirma secenekleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <see cref="MaxBatch"/> varsayilani <c>2048</c>, Faz 1 v4 <c>AfterStateList.Capacity</c> ile
    /// uyumludur. Faz 1 fuzz testi kapasiteyi artirirsa (or. 4096) bu deger de artirilmalidir.
    /// </para>
    /// <para>
    /// <see cref="IntraOpThreads"/> = 1 ve <see cref="InterOpThreads"/> = 1 <b>determinizm</b> icin
    /// sabitlenmistir; paralellik is parcacigi basina ayri <c>OnnxPolicyValueEvaluator</c> ornegiyle
    /// saglanir (Faz 3 v7 thread-basi <c>SearchWorkspace</c> modeli).
    /// </para>
    /// </remarks>
    public sealed class OnnxEvaluatorOptions
    {
        /// <summary>CUDA execution provider kullan. Varsayilan <c>false</c> (CPU).</summary>
        public bool UseCuda = false;

        /// <summary>Intra-op is parcacigi sayisi. Determinizm icin 1.</summary>
        public int IntraOpThreads = 1;

        /// <summary>Inter-op is parcacigi sayisi. Determinizm icin 1.</summary>
        public int InterOpThreads = 1;

        /// <summary>
        /// Tek bir ONNX calistirmasinda islenebilecek en buyuk satir sayisi. Daha buyuk
        /// <c>count</c> degerleri parcalara (chunk) bolunur.
        /// </summary>
        public int MaxBatch = 2048;

        /// <summary>CUDA'da TF32'yi kapat (sayisal determinizm icin).</summary>
        public bool DisableTf32 = true;

        /// <summary>Varsayilan secenekler.</summary>
        public static OnnxEvaluatorOptions Default
        {
            get { return new OnnxEvaluatorOptions(); }
        }

        internal void Validate()
        {
            if (IntraOpThreads < 1)
            {
                throw new ArgumentException("IntraOpThreads >= 1 olmalidir.", nameof(IntraOpThreads));
            }

            if (InterOpThreads < 1)
            {
                throw new ArgumentException("InterOpThreads >= 1 olmalidir.", nameof(InterOpThreads));
            }

            if (MaxBatch < 1)
            {
                throw new ArgumentException("MaxBatch >= 1 olmalidir.", nameof(MaxBatch));
            }
        }
    }
}