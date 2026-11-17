using System;
using Backgammon.Core;
using Microsoft.ML.OnnxRuntime;

namespace Backgammon.Inference
{
    /// <summary>
    /// Faz 4 v3 Bolum 4.1: ONNX Runtime uzerinde calisan, ortak govdeli cift basli agin
    /// C# degerlendiricisi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Is parcacigina ozgudur.</b> Girdi/cikti tamponlari, kova (bucket) basina baglamalar
    /// (<c>OrtIoBinding</c>) ve <c>OrtValue</c> tanitaclari bu ornekte yasar. Ayni
    /// <see cref="OnnxModelHandle"/> birden cok ornek tarafindan paylasilabilir.
    /// </para>
    /// <para>
    /// <b>Kirpma YOKTUR.</b> <c>[-3,3]</c>'e kirpma aramanin sorumlulugundadir (Faz 3 v7 Bolum 1,
    /// 3.6, 4.1). Bu sinif yalnizca <c>float.IsFinite</c> kontrolu yapar.
    /// </para>
    /// <para>
    /// <b>Tek calistirma:</b> her cagride ONNX bir kez kosar ve <b>her iki</b> cikti da hesaplanir;
    /// yalnizca istenen cikti doldurulur. <see cref="EvaluateAndScoreBatch"/> yalnizca arayuzdur.
    /// </para>
    /// <para>
    /// <b>Kovalar:</b> <c>1, 2, 4, ..., MaxBatch</c>. Girdi sifir dolgulu kovaya tasinir; yalnizca
    /// ilk <c>count</c> satirin ciktisi kullanilir (MLP satirlari bagimsizdir). Tamponlar ve
    /// baglamalar <b>yapicida bir kez</b> ayrilir; cagri basina managed tahsis yapilmaz.
    /// </para>
    /// </remarks>
    public sealed class OnnxPolicyValueEvaluator : IPolicyValueEvaluator, ICombinedBatchEvaluator,
                                                    IOutcomeDistributionEvaluator, IDisposable
    {
        private const int VectorSize = BackgammonVectorizer.InputVectorSize;

        /// <summary>Tek bir kova: sabitlenmis tamponlar + baglamalar.</summary>
        private sealed class Bucket : IDisposable
        {
            internal readonly int Size;
            internal readonly float[] Input;
            internal readonly float[] ValueOut;
            internal readonly float[] PolicyOut;

            /// <summary>Faz 6 §5.4: <c>probs</c> ciktisi (<c>output_version == 2</c>); aksi halde null.</summary>
            internal readonly float[] ProbsOut;

            internal readonly OrtValue InputValue;
            internal readonly OrtValue ValueValue;
            internal readonly OrtValue PolicyValue;
            internal readonly OrtValue ProbsValue;
            internal readonly OrtIoBinding Binding;

            /// <summary>Son calistirmada yazilan satir sayisi (sifir dolgu bakimi icin).</summary>
            internal int DirtyRows;

            internal Bucket(InferenceSession session, int size, bool withProbs)
            {
                Size = size;
                // netstandard2.1'de GC.AllocateArray yok; ORT, Memory<float>'i OrtValue omru boyunca
                // sabitler (pinler), bu yuzden duz dizi yeterlidir ve cagri basina tahsis olmaz.
                Input = new float[size * VectorSize];
                PolicyOut = new float[size];

                long[] inputShape = { size, VectorSize };
                long[] policyShape = { size, 1 };

                InputValue = OrtValue.CreateTensorValueFromMemory(
                    OrtMemoryInfo.DefaultInstance, new Memory<float>(Input), inputShape);
                PolicyValue = OrtValue.CreateTensorValueFromMemory(
                    OrtMemoryInfo.DefaultInstance, new Memory<float>(PolicyOut), policyShape);

                Binding = session.CreateIoBinding();
                Binding.BindInput(OnnxModelHandle.InputName, InputValue);
                Binding.BindOutput(OnnxModelHandle.PolicyLogitOutputName, PolicyValue);

                if (withProbs)
                {
                    ProbsOut = new float[size * OnnxModelHandle.ProbabilityCount];
                    long[] probsShape = { size, OnnxModelHandle.ProbabilityCount };
                    ProbsValue = OrtValue.CreateTensorValueFromMemory(
                        OrtMemoryInfo.DefaultInstance, new Memory<float>(ProbsOut), probsShape);
                    Binding.BindOutput(OnnxModelHandle.ProbsOutputName, ProbsValue);
                }
                else
                {
                    ValueOut = new float[size];
                    long[] valueShape = { size, 1 };
                    ValueValue = OrtValue.CreateTensorValueFromMemory(
                        OrtMemoryInfo.DefaultInstance, new Memory<float>(ValueOut), valueShape);
                    Binding.BindOutput(OnnxModelHandle.ValueOutputName, ValueValue);
                }
            }

            public void Dispose()
            {
                Binding.Dispose();
                InputValue.Dispose();
                PolicyValue.Dispose();
                ValueValue?.Dispose();
                ProbsValue?.Dispose();
            }
        }

        private OnnxModelHandle _model;
        private readonly RunOptions _runOptions;
        private readonly Bucket[] _buckets;
        private readonly int _maxBatch;
        private bool _withProbs;
        private float[] _logits;
        private bool _disposed;

        /// <summary>Yeni bir degerlendirici olusturur ve kova tamponlarini ayirir.</summary>
        /// <exception cref="ArgumentNullException"><paramref name="model"/> null.</exception>
        public OnnxPolicyValueEvaluator(OnnxModelHandle model)
            : this(model, null)
        {
        }

        /// <summary>Seceneklerle yeni bir degerlendirici olusturur.</summary>
        /// <exception cref="ArgumentNullException"><paramref name="model"/> null.</exception>
        public OnnxPolicyValueEvaluator(OnnxModelHandle model, OnnxEvaluatorOptions options)
        {
            if (model == null)
            {
                throw new ArgumentNullException(nameof(model));
            }

            OnnxEvaluatorOptions opts = options ?? OnnxEvaluatorOptions.Default;
            opts.Validate();

            _model = model;
            _runOptions = new RunOptions();

            int log2 = 0;
            while ((1 << log2) < opts.MaxBatch)
            {
                log2++;
            }

            _maxBatch = 1 << log2;
            _withProbs = model.OutputVersion >= 2;
            _buckets = new Bucket[log2 + 1];
            for (int i = 0; i <= log2; i++)
            {
                _buckets[i] = new Bucket(model.Session, 1 << i, _withProbs);
            }
        }

        /// <summary>Su anki model tanitaci.</summary>
        public OnnxModelHandle Model
        {
            get { return _model; }
        }

        /// <summary>
        /// Modeli degistirir. <b>Yalnizca</b> arama/oyun <b>bostayken</b> cagrilmalidir.
        /// </summary>
        /// <remarks>
        /// Yeni <see cref="OnnxModelHandle.ModelVersion"/> eskisinden <b>buyuk</b> olmalidir.
        /// Cagiran, bu cagridan sonra <see cref="SearchWorkspace.Reset"/> cagirmak
        /// <b>ZORUNDADIR</b> (Faz 3 v7 Bolum 3.5, 4.4, Test 17).
        /// </remarks>
        /// <exception cref="ArgumentNullException"><paramref name="model"/> null.</exception>
        /// <exception cref="ArgumentException">Yeni surum eskisinden buyuk degil.</exception>
        public void SetModel(OnnxModelHandle model)
        {
            if (model == null)
            {
                throw new ArgumentNullException(nameof(model));
            }

            if (_disposed)
            {
                throw new ObjectDisposedException(nameof(OnnxPolicyValueEvaluator));
            }

            if (_model != null && model.ModelVersion <= _model.ModelVersion)
            {
                throw new ArgumentException(
                    "Yeni ModelVersion (" + model.ModelVersion + ") eskisinden (" +
                    _model.ModelVersion + ") buyuk olmalidir.", nameof(model));
            }

            // Kovalar (OrtValue + OrtIoBinding) eski oturuma baglidir; yeni oturumla
            // yeniden kurulmalidir (F4-26).
            bool withProbs = model.OutputVersion >= 2;
            Bucket[] fresh = new Bucket[_buckets.Length];
            try
            {
                for (int i = 0; i < fresh.Length; i++)
                {
                    fresh[i] = new Bucket(model.Session, 1 << i, withProbs);
                }
            }
            catch
            {
                for (int i = 0; i < fresh.Length; i++)
                {
                    fresh[i]?.Dispose();
                }

                throw;
            }

            for (int i = 0; i < _buckets.Length; i++)
            {
                _buckets[i]?.Dispose();
                _buckets[i] = fresh[i];
            }

            _withProbs = withProbs;
            _model = model;
        }

        /// <summary>
        /// <see cref="IPositionEvaluator.Version"/> ve <see cref="IPolicyEvaluator.Version"/>
        /// <b>ayni</b> ozelliktir: <see cref="OnnxModelHandle.ModelVersion"/>.
        /// </summary>
        public int Version
        {
            get { return _model == null ? 0 : unchecked((int)_model.ModelVersion); }
        }

        /// <inheritdoc/>
        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            Validate(list, offset, count, results.Length, "results");
            if (count == 0)
            {
                return;
            }

            Execute(list, count, perspective, scalars, results, true, default, false, default, false);
        }

        /// <inheritdoc/>
        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            Validate(list, offset, count, priorities.Length, "priorities");
            if (count == 0)
            {
                return;
            }

            Execute(list, count, perspective, scalars, default, false, priorities, true, default, false);
        }

        /// <inheritdoc/>
        public void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                          in VectorizerScalars scalars, Span<float> results, Span<float> priorities)
        {
            Validate(list, offset, count, results.Length, "results");
            if (priorities.Length < count)
            {
                throw new ArgumentException(
                    "priorities en az " + count + " eleman olmali: " + priorities.Length, nameof(priorities));
            }

            if (count == 0)
            {
                return;
            }

            Execute(list, count, perspective, scalars, results, true, priorities, true, default, false);
        }

        /// <summary>
        /// Faz 6 §5.5: 6 olasilikli sonuc dagilimi. Yalnizca <c>output_version &gt;= 2</c>
        /// modellerde desteklenir; v1 modelde <see cref="NotSupportedException"/> atar.
        /// </summary>
        public void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                              in VectorizerScalars scalars, Span<OutcomeDistribution> results)
        {
            Validate(list, offset, count, results.Length, "results");
            if (!_withProbs)
            {
                throw new NotSupportedException(
                    "Sonuc dagilimi yalnizca output_version >= 2 modellerde uretilir; " +
                    "yuklu model output_version " + _model.OutputVersion + ".");
            }

            if (count == 0)
            {
                return;
            }

            Execute(list, count, perspective, scalars, default, false, default, false, results, true);
        }

        private void Validate(AfterStateList list, int offset, int count, int bufferLength, string paramName)
        {
            if (_disposed)
            {
                throw new ObjectDisposedException(nameof(OnnxPolicyValueEvaluator));
            }

            if (list == null)
            {
                throw new ArgumentNullException(nameof(list));
            }

            if (offset != 0)
            {
                throw new ArgumentException("offset su an yalnizca 0 olabilir.", nameof(offset));
            }

            if (count < 0 || count > list.Count)
            {
                throw new ArgumentException(
                    "count 0.." + list.Count + " araliginda olmali: " + count, nameof(count));
            }

            if (bufferLength < count)
            {
                throw new ArgumentException(
                    paramName + " en az " + count + " eleman olmali: " + bufferLength, paramName);
            }
        }

        /// <summary>
        /// Ortak cekirdek: vektorlestir, tek ONNX calistirmasi, istenen ciktilari doldur.
        /// </summary>
        private void Execute(AfterStateList list, int count, int perspective, in VectorizerScalars scalars,
                             Span<float> results, bool wantValues, Span<float> priorities, bool wantPriorities,
                             Span<OutcomeDistribution> distributions, bool wantDistributions)
        {
            bool singleChunk = count <= _maxBatch;
            if (wantPriorities && !singleChunk)
            {
                EnsureLogitCapacity(count);
            }

            int done = 0;
            while (done < count)
            {
                int chunk = count - done;
                if (chunk > _maxBatch)
                {
                    chunk = _maxBatch;
                }

                Bucket bucket = _buckets[Log2Ceil(chunk)];

                // Onceki calistirmadan kalan satirlari sifirla (sifir dolgu degismezi).
                if (bucket.DirtyRows > chunk)
                {
                    Array.Clear(bucket.Input, chunk * VectorSize, (bucket.DirtyRows - chunk) * VectorSize);
                }

                if (singleChunk)
                {
                    BackgammonVectorizer.VectorizeBatch(list, count, perspective, scalars, bucket.Input);
                }
                else
                {
                    for (int i = 0; i < chunk; i++)
                    {
                        int record = done + i;
                        BackgammonVectorizer.Vectorize(
                            list.BoardOf(record), list.WhiteBorneOff[record], list.BlackBorneOff[record],
                            scalars, perspective,
                            new Span<float>(bucket.Input, i * VectorSize, VectorSize));
                    }
                }

                bucket.DirtyRows = chunk;

                // CUDA EP'de OrtIoBinding.BindInput, CPU->cihaz kopyasini BIND ANINDA yapar;
                // SynchronizeBoundInputs bunu tekrar etmez. Bu yuzden girdi tamponu
                // doldurulduktan SONRA yeniden baglanmalidir (F4-35). CPU EP'de kopya
                // olmadigi icin yeniden baglama gereksizdir.
                if (_model.UsesCuda)
                {
                    bucket.Binding.ClearBoundInputs();
                    bucket.Binding.BindInput(OnnxModelHandle.InputName, bucket.InputValue);
                }

                bucket.Binding.SynchronizeBoundInputs();
                _model.Session.RunWithBinding(_runOptions, bucket.Binding);
                bucket.Binding.SynchronizeBoundOutputs();

                if (wantValues)
                {
                    if (_withProbs)
                    {
                        for (int i = 0; i < chunk; i++)
                        {
                            OutcomeDistribution d = ReadDistribution(bucket, i);
                            if (!d.IsValid)
                            {
                                throw new ArgumentException(
                                    "Model gecersiz sonuc dagilimi uretti (index " + (done + i) + ").",
                                    nameof(results));
                            }

                            results[done + i] = (float)d.Equity;
                        }
                    }
                    else
                    {
                        for (int i = 0; i < chunk; i++)
                        {
                            float v = bucket.ValueOut[i];
                            if (!float.IsFinite(v))
                            {
                                throw new ArgumentException(
                                    "Model sonlu olmayan deger uretti (index " + (done + i) + "): " + v,
                                    nameof(results));
                            }

                            results[done + i] = v;
                        }
                    }
                }

                if (wantDistributions)
                {
                    for (int i = 0; i < chunk; i++)
                    {
                        OutcomeDistribution d = ReadDistribution(bucket, i);
                        if (!d.IsValid)
                        {
                            throw new ArgumentException(
                                "Model gecersiz sonuc dagilimi uretti (index " + (done + i) + ").",
                                nameof(distributions));
                        }

                        distributions[done + i] = d;
                    }
                }

                if (wantPriorities)
                {
                    if (singleChunk)
                    {
                        Softmax(bucket.PolicyOut, chunk, priorities);
                    }
                    else
                    {
                        for (int i = 0; i < chunk; i++)
                        {
                            _logits[done + i] = bucket.PolicyOut[i];
                        }
                    }
                }

                done += chunk;
            }

            if (wantPriorities && !singleChunk)
            {
                Softmax(_logits, count, priorities);
            }
        }

        private void EnsureLogitCapacity(int count)
        {
            if (_logits == null || _logits.Length < count)
            {
                _logits = new float[count];
            }
        }

        /// <summary>
        /// Faz 6 §5.5: <c>probs</c> satirini <see cref="OutcomeDistribution"/>'a cevirir.
        /// Sutun sirasi <c>W, GW, BW, L, GL, BL</c> (dislayici).
        /// </summary>
        private static OutcomeDistribution ReadDistribution(Bucket bucket, int row)
        {
            int b = row * OnnxModelHandle.ProbabilityCount;
            float[] p = bucket.ProbsOut;
            return OutcomeDistribution.FromProbabilities(
                p[b], p[b + 1], p[b + 2], p[b + 3], p[b + 4], p[b + 5]);
        }

        private static int Log2Ceil(int n)
        {
            int r = 0;
            while ((1 << r) < n)
            {
                r++;
            }

            return r;
        }

        /// <summary>Grup softmax: <c>priorities[i] = exp(l[i]-max) / sum</c>.</summary>
        private static void Softmax(float[] logits, int count, Span<float> priorities)
        {
            if (count == 1)
            {
                priorities[0] = 1f;
                return;
            }

            float max = logits[0];
            for (int i = 1; i < count; i++)
            {
                if (logits[i] > max)
                {
                    max = logits[i];
                }
            }

            float sum = 0f;
            for (int i = 0; i < count; i++)
            {
                float e = MathF.Exp(logits[i] - max);
                priorities[i] = e;
                sum += e;
            }

            float inv = 1f / sum;
            for (int i = 0; i < count; i++)
            {
                priorities[i] *= inv;
            }
        }

        /// <inheritdoc/>
        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;

            for (int i = 0; i < _buckets.Length; i++)
            {
                _buckets[i]?.Dispose();
            }

            _runOptions.Dispose();
            _model = null;
        }
    }
}