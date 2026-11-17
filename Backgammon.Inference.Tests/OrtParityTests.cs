using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 8, Test 9 / 10 / 13: ORT paritesi, dinamik batch ve determinizm.
    /// </summary>
    /// <remarks>
    /// Bu testler <see cref="OnnxModelHandle"/>'i <b>kullanmaz</b>; ham ORT oturumu ile bagimsiz
    /// dogrulama yapar. Degerlendirici sozlesmesi <c>EvaluatorContractTests</c> icindedir.
    /// </remarks>
    [TestFixture]
    public sealed class OrtParityTests
    {
        private const float Tolerance = 1e-5f;

        private static InferenceSession OpenSession()
        {
            var options = new SessionOptions
            {
                IntraOpNumThreads = 1,
                InterOpNumThreads = 1,
            };
            return new InferenceSession(InferenceTestSupport.ModelPath, options);
        }

        private static (float[] Value, float[] Policy) Run(InferenceSession session, float[] flat, int rows)
        {
            var tensor = new DenseTensor<float>(flat, new[] { rows, Backgammon.Core.BackgammonVectorizer.InputVectorSize });
            var inputs = new List<NamedOnnxValue>
            {
                NamedOnnxValue.CreateFromTensor(OnnxModelHandle.InputName, tensor),
            };

            using IDisposableReadOnlyCollection<DisposableNamedOnnxValue> results = session.Run(inputs);
            float[] value = null!;
            float[] policy = null!;
            foreach (DisposableNamedOnnxValue r in results)
            {
                if (r.Name == OnnxModelHandle.ValueOutputName)
                {
                    value = ToArray(r);
                }
                else if (r.Name == OnnxModelHandle.PolicyLogitOutputName)
                {
                    policy = ToArray(r);
                }
            }

            Assert.That(value, Is.Not.Null, "value ciktisi yok");
            Assert.That(policy, Is.Not.Null, "policy_logit ciktisi yok");
            return (value, policy);
        }

        private static float[] ToArray(DisposableNamedOnnxValue value)
        {
            var tensor = value.AsTensor<float>();
            var result = new float[tensor.Length];
            int i = 0;
            foreach (float f in tensor)
            {
                result[i++] = f;
            }

            return result;
        }

        [Test]
        public void Test09_ParityCasesMatchOrt()
        {
            Dictionary<string, object> payload = InferenceTestSupport.ReadJsonObject(InferenceTestSupport.ParityPath);
            Assert.That(Convert.ToInt32(payload["featureVersion"]), Is.EqualTo(1));
            Assert.That(Convert.ToInt32(payload["vectorSize"]), Is.EqualTo(221));
            Assert.That(Convert.ToDouble(payload["tolerance"]), Is.EqualTo(1e-5).Within(1e-12));

            var records = (List<object>)payload["records"];
            Assert.That(records.Count, Is.GreaterThan(0));

            int rows = records.Count;
            var flat = new float[rows * 221];
            for (int r = 0; r < rows; r++)
            {
                var rec = (Dictionary<string, object>)records[r];
                float[] vec = InferenceTestSupport.HexToVector((string)rec["vectorHex"]);
                Assert.That(vec.Length, Is.EqualTo(221));
                Array.Copy(vec, 0, flat, r * 221, 221);
            }

            using InferenceSession session = OpenSession();
            (float[] value, float[] policy) = Run(session, flat, rows);

            float maxDv = 0f;
            float maxDp = 0f;
            for (int r = 0; r < rows; r++)
            {
                var rec = (Dictionary<string, object>)records[r];
                float expectedValue = InferenceTestSupport.HexToFloat((string)rec["expectedValueHex"]);
                float expectedPolicy = InferenceTestSupport.HexToFloat((string)rec["expectedPolicyLogitHex"]);
                maxDv = Math.Max(maxDv, Math.Abs(value[r] - expectedValue));
                maxDp = Math.Max(maxDp, Math.Abs(policy[r] - expectedPolicy));
            }

            Assert.That(maxDv, Is.LessThanOrEqualTo(Tolerance), "max|dvalue| = " + maxDv);
            Assert.That(maxDp, Is.LessThanOrEqualTo(Tolerance), "max|dpolicy| = " + maxDp);
        }

        [Test]
        public void Test09b_GoldenInputsMatchPythonOrt()
        {
            Assert.That(File.Exists(InferenceTestSupport.GoldenOutputsPath), Is.True,
                "golden_outputs.json yok; ml/gen_golden_outputs.py calistirilmali.");

            Dictionary<string, object> payload = InferenceTestSupport.ReadJsonObject(InferenceTestSupport.GoldenOutputsPath);
            var records = (List<object>)payload["records"];
            Assert.That(records.Count, Is.EqualTo(500));

            string goldenPath = Path.Combine(
                InferenceTestSupport.RepoRoot(), "Backgammon.Tests", "ReferenceData", "vector_golden.json");
            Dictionary<string, object> golden = InferenceTestSupport.ReadJsonObject(goldenPath);
            var goldenRecords = (List<object>)golden["records"];
            Assert.That(goldenRecords.Count, Is.EqualTo(records.Count));

            int rows = records.Count;
            var flat = new float[rows * 221];
            for (int r = 0; r < rows; r++)
            {
                var rec = (Dictionary<string, object>)goldenRecords[r];
                float[] vec = InferenceTestSupport.HexToVector((string)rec["vectorHex"]);
                Array.Copy(vec, 0, flat, r * 221, 221);
            }

            using InferenceSession session = OpenSession();
            (float[] value, float[] policy) = Run(session, flat, rows);

            float maxDv = 0f;
            float maxDp = 0f;
            for (int r = 0; r < rows; r++)
            {
                var rec = (Dictionary<string, object>)records[r];
                maxDv = Math.Max(maxDv, Math.Abs(value[r] - InferenceTestSupport.HexToFloat((string)rec["valueHex"])));
                maxDp = Math.Max(maxDp, Math.Abs(policy[r] - InferenceTestSupport.HexToFloat((string)rec["policyLogitHex"])));
            }

            Assert.That(maxDv, Is.LessThanOrEqualTo(Tolerance), "max|dvalue| = " + maxDv);
            Assert.That(maxDp, Is.LessThanOrEqualTo(Tolerance), "max|dpolicy| = " + maxDp);
        }

        [Test]
        public void Test10_DynamicBatchAxis()
        {
            using InferenceSession session = OpenSession();
            var rng = new Random(12345);
            var full = new float[2048 * 221];
            for (int i = 0; i < full.Length; i++)
            {
                full[i] = (float)((rng.NextDouble() * 2.0) - 1.0);
            }

            (float[] refValue, float[] refPolicy) = Run(session, full, 2048);

            foreach (int rows in new[] { 1, 2, 3, 13, 64, 2048 })
            {
                var slice = new float[rows * 221];
                Array.Copy(full, 0, slice, 0, slice.Length);
                (float[] value, float[] policy) = Run(session, slice, rows);

                float maxDv = 0f;
                float maxDp = 0f;
                for (int r = 0; r < rows; r++)
                {
                    maxDv = Math.Max(maxDv, Math.Abs(value[r] - refValue[r]));
                    maxDp = Math.Max(maxDp, Math.Abs(policy[r] - refPolicy[r]));
                }

                Assert.That(maxDv, Is.LessThanOrEqualTo(Tolerance), "rows=" + rows + " max|dvalue|=" + maxDv);
                Assert.That(maxDp, Is.LessThanOrEqualTo(Tolerance), "rows=" + rows + " max|dpolicy|=" + maxDp);
            }
        }

        [Test]
        public void Test13_Determinism_SameInputSameOutput()
        {
            using InferenceSession session = OpenSession();
            var rng = new Random(777);
            var flat = new float[64 * 221];
            for (int i = 0; i < flat.Length; i++)
            {
                flat[i] = (float)((rng.NextDouble() * 2.0) - 1.0);
            }

            (float[] v1, float[] p1) = Run(session, flat, 64);
            (float[] v2, float[] p2) = Run(session, flat, 64);

            for (int i = 0; i < 64; i++)
            {
                Assert.That(BitConverter.SingleToUInt32Bits(v1[i]), Is.EqualTo(BitConverter.SingleToUInt32Bits(v2[i])),
                    "value[" + i + "] bit duzeyinde ayni degil");
                Assert.That(BitConverter.SingleToUInt32Bits(p1[i]), Is.EqualTo(BitConverter.SingleToUInt32Bits(p2[i])),
                    "policy[" + i + "] bit duzeyinde ayni degil");
            }
        }

        [Test]
        public void Test13b_Determinism_AcrossSessions()
        {
            var rng = new Random(4242);
            var flat = new float[32 * 221];
            for (int i = 0; i < flat.Length; i++)
            {
                flat[i] = (float)((rng.NextDouble() * 2.0) - 1.0);
            }

            float[] v1;
            float[] p1;
            using (InferenceSession s1 = OpenSession())
            {
                (v1, p1) = Run(s1, flat, 32);
            }

            float[] v2;
            float[] p2;
            using (InferenceSession s2 = OpenSession())
            {
                (v2, p2) = Run(s2, flat, 32);
            }

            for (int i = 0; i < 32; i++)
            {
                Assert.That(v1[i], Is.EqualTo(v2[i]).Within(0f), "value[" + i + "] oturumlar arasi farkli");
                Assert.That(p1[i], Is.EqualTo(p2[i]).Within(0f), "policy[" + i + "] oturumlar arasi farkli");
            }
        }

        [Test]
        public void Test13c_BatchCompositionInvariance()
        {
            using InferenceSession session = OpenSession();
            var rng = new Random(2024);
            var flat = new float[128 * 221];
            for (int i = 0; i < flat.Length; i++)
            {
                flat[i] = (float)((rng.NextDouble() * 2.0) - 1.0);
            }

            (float[] refValue, float[] refPolicy) = Run(session, flat, 128);

            // Tek satirlik calistirmalar, 128'lik calistirmayla ayni sonucu vermeli.
            for (int r = 0; r < 128; r += 17)
            {
                var one = new float[221];
                Array.Copy(flat, r * 221, one, 0, 221);
                (float[] value, float[] policy) = Run(session, one, 1);
                Assert.That(value[0], Is.EqualTo(refValue[r]).Within(Tolerance), "satir " + r);
                Assert.That(policy[0], Is.EqualTo(refPolicy[r]).Within(Tolerance), "satir " + r);
            }
        }
    }
}