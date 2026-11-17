using System;
using System.IO;
using Backgammon.Inference;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 5 Bolum 5.5 / Bolum 8 Test 36 + Faz 6 Bolum 5.4: <c>output_version</c> sozlesmesi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Metadata <b>yoksa</b> 1 varsayilir (Faz 4 modelleri geriye uyumlu). Metadata
    /// <b>1</b> ise kabul edilir. <b>2</b> ise 6 olasilikli <c>probs</c> sozlesmesi beklenir.
    /// <b>2'den buyukse</b> <see cref="NotSupportedException"/> atilir; boylece ileride
    /// eklenecek bir cikti sozlesmesi eski kopruyle sessizce yanlis yorumlanmaz.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class OutputVersionTests
    {
        private static string ModelDir
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models"); }
        }

        [Test]
        public void SupportedOutputVersion_IsTwo()
        {
            Assert.That(OnnxModelHandle.SupportedOutputVersion, Is.EqualTo(2u));
        }

        [Test]
        public void MissingMetadata_DefaultsToOne()
        {
            // model_v1.onnx Faz 4'te uretildi; output_version metadata'si yok.
            using (OnnxModelHandle handle = OnnxModelHandle.Load(
                       Path.Combine(ModelDir, "model_v1.onnx"), OnnxEvaluatorOptions.Default))
            {
                Assert.That(handle.OutputVersion, Is.EqualTo(1u));
            }
        }

        [Test]
        public void ExplicitVersionOne_IsAccepted()
        {
            using (OnnxModelHandle handle = OnnxModelHandle.Load(
                       Path.Combine(ModelDir, "model_output_version_1.onnx"), OnnxEvaluatorOptions.Default))
            {
                Assert.That(handle.OutputVersion, Is.EqualTo(1u));
            }
        }

        [Test]
        public void FutureVersion_Throws()
        {
            var ex = Assert.Throws<NotSupportedException>(() =>
                OnnxModelHandle.Load(Path.Combine(ModelDir, "model_bad_output_version.onnx"),
                                     OnnxEvaluatorOptions.Default));

            Assert.That(ex.Message, Does.Contain("output_version"));
            Assert.That(ex.Message, Does.Contain("2"));
        }
    }
}
