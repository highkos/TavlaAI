using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Backgammon.Core;
using Microsoft.ML.OnnxRuntime;

namespace Backgammon.Inference
{
    /// <summary>
    /// Faz 4 v3 Bolum 4.1: ONNX oturumunu tutan, <b>salt-okunur</b> ve <b>is parcacigi guvenli</b> tanitici.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Bir <see cref="OnnxModelHandle"/> birden cok is parcacigi tarafindan paylasilabilir; ancak her
    /// is parcacigi kendi <see cref="OnnxPolicyValueEvaluator"/> ornegini olusturmalidir (tamponlar ve
    /// IoBinding havuzu orada yasar).
    /// </para>
    /// <para>
    /// <b>Surum korumasi:</b> yukleme sirasinda ONNX <c>metadata_props</c> alanlari
    /// <c>feature_version</c> ve <c>vector_size</c>, <see cref="BackgammonVectorizer"/> sabitleriyle
    /// karsilastirilir; uyusmazlikta <see cref="InvalidDataException"/> firlatilir.
    /// </para>
    /// </remarks>
    public sealed class OnnxModelHandle : IDisposable
    {
        /// <summary>ONNX girdi adi (Faz 4 v3 Bolum 3).</summary>
        public const string InputName = "features";

        /// <summary>ONNX deger cikti adi (yalnizca <c>output_version == 1</c>).</summary>
        public const string ValueOutputName = "value";

        /// <summary>
        /// Faz 6 §5.4: 6 cikti li deger basi cikti adi (<c>output_version == 2</c>).
        /// Sekil <c>[B, 6]</c>, sira <c>W, GW, BW, L, GL, BL</c>, <b>dislayici</b>.
        /// </summary>
        public const string ProbsOutputName = "probs";

        /// <summary>Faz 6 §5.1: dislayici sinif sayisi.</summary>
        public const int ProbabilityCount = OutcomeDistribution.ProbabilityCount;

        /// <summary>Faz 6 §5.4: <c>probs</c> sutun sirasi (metadata <c>prob_order</c>).</summary>
        public const string ProbOrder = "W,GW,BW,L,GL,BL";

        /// <summary>Faz 6 §5.4: <c>probs</c> kodlamasi (metadata <c>prob_encoding</c>).</summary>
        public const string ProbEncoding = "exclusive";

        /// <summary>ONNX politika logit cikti adi.</summary>
        public const string PolicyLogitOutputName = "policy_logit";

        /// <summary>
        /// Faz 6 §5.4: bu koprunun destekledigi en buyuk <c>output_version</c>. Deger <b>2</b> =
        /// 6 olasilikli <c>probs</c> + tek <c>policy_logit</c>. <c>output_version == 1</c>
        /// (tek skaler <c>value</c>) <b>aynen</b> calismaya devam eder (geriye donuk uyumluluk).
        /// </summary>
        public const uint SupportedOutputVersion = 2;

        private readonly InferenceSession _session;
        private readonly uint _modelVersion;
        private readonly uint _outputVersion;
        private readonly string _arch;
        private readonly string _trainedBy;
        private readonly string _modelPath;
        private readonly bool _usesCuda;
        private bool _disposed;

        private OnnxModelHandle(InferenceSession session, uint modelVersion, uint outputVersion, string arch,
                                string trainedBy, string modelPath, bool usesCuda)
        {
            _session = session;
            _modelVersion = modelVersion;
            _outputVersion = outputVersion;
            _arch = arch;
            _trainedBy = trainedBy;
            _modelPath = modelPath;
            _usesCuda = usesCuda;
        }

        /// <summary>ONNX metadata <c>model_version</c>. Monoton artan tamsayi.</summary>
        public uint ModelVersion
        {
            get { return _modelVersion; }
        }

        /// <summary>
        /// ONNX metadata <c>output_version</c>. Metadata yoksa <b>1</b> kabul edilir (Faz 4 modelleri
        /// geriye donuk uyumlu kalir).
        /// </summary>
        public uint OutputVersion
        {
            get { return _outputVersion; }
        }

        /// <summary>ONNX metadata <c>arch</c> (or. <c>221-128-64</c>).</summary>
        public string Arch
        {
            get { return _arch; }
        }

        /// <summary>ONNX metadata <c>trained_by</c>.</summary>
        public string TrainedBy
        {
            get { return _trainedBy; }
        }

        /// <summary>Yuklenen dosya yolu (teshis icin).</summary>
        public string ModelPath
        {
            get { return _modelPath; }
        }

        internal InferenceSession Session
        {
            get { return _session; }
        }

        /// <summary>
        /// Oturum CUDA EP ile mi olusturuldu? CUDA'da <c>OrtIoBinding.BindInput</c> CPU-&gt;cihaz
        /// kopyasini bind aninda yaptigi icin girdi her cagrida yeniden baglanmalidir (F4-35).
        /// </summary>
        internal bool UsesCuda
        {
            get { return _usesCuda; }
        }

        /// <summary>
        /// Modeli yukler, metadata'yi dogrular ve oturumu hazirlar.
        /// </summary>
        /// <exception cref="ArgumentException">Yol bos veya secenekler gecersiz.</exception>
        /// <exception cref="FileNotFoundException">Dosya yok.</exception>
        /// <exception cref="InvalidDataException">Metadata eksik/uyumsuz veya girdi-cikti sozlesmesi bozuk.</exception>
        public static OnnxModelHandle Load(string modelPath, in OnnxEvaluatorOptions options)
        {
            if (string.IsNullOrEmpty(modelPath))
            {
                throw new ArgumentException("modelPath bos olamaz.", nameof(modelPath));
            }

            if (!File.Exists(modelPath))
            {
                throw new FileNotFoundException("ONNX model dosyasi bulunamadi: " + modelPath, modelPath);
            }

            OnnxEvaluatorOptions opts = options ?? OnnxEvaluatorOptions.Default;
            opts.Validate();

            var sessionOptions = new SessionOptions();
            sessionOptions.IntraOpNumThreads = opts.IntraOpThreads;
            sessionOptions.InterOpNumThreads = opts.InterOpThreads;
            sessionOptions.EnableCpuMemArena = true;
            sessionOptions.EnableMemoryPattern = true;

            if (opts.UseCuda)
            {
                using (var cuda = new OrtCUDAProviderOptions())
                {
                    cuda.UpdateOptions(new Dictionary<string, string>
                    {
                        { "use_tf32", opts.DisableTf32 ? "0" : "1" },
                    });
                    sessionOptions.AppendExecutionProvider_CUDA(cuda);
                }
            }

            InferenceSession session = null;
            try
            {
                session = new InferenceSession(modelPath, sessionOptions);
                Dictionary<string, string> meta = session.ModelMetadata.CustomMetadataMap;

                uint modelVersion = ParseUInt(meta, "model_version");
                uint featureVersion = ParseUInt(meta, "feature_version");
                uint vectorSize = ParseUInt(meta, "vector_size");

                if (featureVersion != (uint)BackgammonVectorizer.FeatureVersion)
                {
                    throw new InvalidDataException(
                        "feature_version uyumsuz: model=" + featureVersion +
                        ", vektorlestirici=" + BackgammonVectorizer.FeatureVersion);
                }

                if (vectorSize != (uint)BackgammonVectorizer.InputVectorSize)
                {
                    throw new InvalidDataException(
                        "vector_size uyumsuz: model=" + vectorSize +
                        ", vektorlestirici=" + BackgammonVectorizer.InputVectorSize);
                }

                uint outputVersion = ParseOptionalUInt(meta, "output_version", 1u);
                if (outputVersion > SupportedOutputVersion)
                {
                    throw new NotSupportedException(
                        "output_version " + outputVersion + " desteklenmiyor; bu kopru en fazla " +
                        SupportedOutputVersion + " destekler (Faz 6 Bolum 5.4).");
                }

                if (outputVersion == 0)
                {
                    throw new InvalidDataException("output_version 0 olamaz (en az 1).");
                }

                if (outputVersion >= 2)
                {
                    ValidateProbabilityMetadata(meta);
                }

                string arch;
                meta.TryGetValue("arch", out arch);
                string trainedBy;
                meta.TryGetValue("trained_by", out trainedBy);

                ValidateIoContract(session, outputVersion);

                return new OnnxModelHandle(session, modelVersion, outputVersion, arch, trainedBy, modelPath,
                                           opts.UseCuda);
            }
            catch
            {
                session?.Dispose();
                throw;
            }
            finally
            {
                sessionOptions.Dispose();
            }
        }

        private static uint ParseUInt(Dictionary<string, string> meta, string key)
        {
            string raw;
            if (!meta.TryGetValue(key, out raw) || string.IsNullOrEmpty(raw))
            {
                throw new InvalidDataException("ONNX metadata '" + key + "' eksik.");
            }

            uint value;
            if (!uint.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
            {
                throw new InvalidDataException("ONNX metadata '" + key + "' tamsayi degil: " + raw);
            }

            return value;
        }

        /// <summary>
        /// Metadata anahtari <b>istege bagli</b> ise <paramref name="fallback"/> doner; anahtar varsa
        /// <see cref="ParseUInt"/> gibi davranir (bozuk deger yine <see cref="InvalidDataException"/> atar).
        /// </summary>
        private static uint ParseOptionalUInt(Dictionary<string, string> meta, string key, uint fallback)
        {
            string raw;
            if (!meta.TryGetValue(key, out raw) || string.IsNullOrEmpty(raw))
            {
                return fallback;
            }

            return ParseUInt(meta, key);
        }

        /// <summary>
        /// Faz 6 §5.4: <c>output_version &gt;= 2</c> modelleri <c>prob_order</c> ve
        /// <c>prob_encoding</c> metadata'sini <b>bildirmek zorundadir</b>; aksi halde 6 cikti
        /// sessizce yanlis yorumlanabilir.
        /// </summary>
        private static void ValidateProbabilityMetadata(Dictionary<string, string> meta)
        {
            string order;
            if (!meta.TryGetValue("prob_order", out order) || order != ProbOrder)
            {
                throw new InvalidDataException(
                    "ONNX metadata 'prob_order' beklenen degerle uyusmuyor: '" + (order ?? "<yok>") +
                    "' (beklenen '" + ProbOrder + "').");
            }

            string encoding;
            if (!meta.TryGetValue("prob_encoding", out encoding) || encoding != ProbEncoding)
            {
                throw new InvalidDataException(
                    "ONNX metadata 'prob_encoding' beklenen degerle uyusmuyor: '" +
                    (encoding ?? "<yok>") + "' (beklenen '" + ProbEncoding + "').");
            }
        }

        private static void ValidateIoContract(InferenceSession session, uint outputVersion)
        {
            NodeMetadata input;
            if (!session.InputMetadata.TryGetValue(InputName, out input))
            {
                throw new InvalidDataException("ONNX girdisi '" + InputName + "' bulunamadi.");
            }

            int[] inDims = input.Dimensions;
            if (inDims == null || inDims.Length != 2 || inDims[1] != BackgammonVectorizer.InputVectorSize)
            {
                throw new InvalidDataException(
                    "ONNX girdi sekli [B," + BackgammonVectorizer.InputVectorSize + "] olmali.");
            }

            if (inDims[0] > 0)
            {
                throw new InvalidDataException("ONNX girdi batch ekseni dinamik degil (sabit " + inDims[0] + ").");
            }

            NodeMetadata policy;
            if (!session.OutputMetadata.TryGetValue(PolicyLogitOutputName, out policy))
            {
                throw new InvalidDataException("ONNX ciktisi '" + PolicyLogitOutputName + "' bulunamadi.");
            }

            int[] policyDims = policy.Dimensions;
            if (policyDims == null || policyDims.Length != 2 || policyDims[1] != 1)
            {
                throw new InvalidDataException("ONNX ciktisi 'policy_logit' sekli [B,1] olmali.");
            }

            if (outputVersion >= 2)
            {
                NodeMetadata probs;
                if (!session.OutputMetadata.TryGetValue(ProbsOutputName, out probs))
                {
                    throw new InvalidDataException("ONNX ciktisi '" + ProbsOutputName + "' bulunamadi.");
                }

                int[] probsDims = probs.Dimensions;
                if (probsDims == null || probsDims.Length != 2 || probsDims[1] != ProbabilityCount)
                {
                    throw new InvalidDataException(
                        "ONNX ciktisi 'probs' sekli [B," + ProbabilityCount + "] olmali.");
                }

                if (probsDims[0] > 0)
                {
                    throw new InvalidDataException(
                        "ONNX ciktisi 'probs' batch ekseni dinamik degil (sabit " + probsDims[0] + ").");
                }

                return;
            }

            NodeMetadata value;
            if (!session.OutputMetadata.TryGetValue(ValueOutputName, out value))
            {
                throw new InvalidDataException("ONNX ciktisi '" + ValueOutputName + "' bulunamadi.");
            }

            int[] valueDims = value.Dimensions;
            if (valueDims == null || valueDims.Length != 2 || valueDims[1] != 1)
            {
                throw new InvalidDataException("ONNX ciktisi 'value' sekli [B,1] olmali.");
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
            _session.Dispose();
        }
    }
}