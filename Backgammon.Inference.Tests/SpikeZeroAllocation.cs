using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Microsoft.ML.OnnxRuntime;
using NUnit.Framework;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 4.5: <b>sifir-allocation spike'i</b> (Asama A, zorunlu).
    /// </summary>
    /// <remarks>
    /// <para>
    /// Amac: ONNX Runtime C# API'sinin varsayilan <c>Run</c> yolu cagri basina managed nesne
    /// uretir. <c>OrtIoBinding</c> + onceden baglanmis, sabitlenmis (<c>pinned</c>) tamponlar
    /// uzerinden <c>RunWithBinding</c> ile kova basina isinma sonrasi
    /// <c>GC.GetAllocatedBytesForCurrentThread</c> farkini olcmek.
    /// </para>
    /// <para>
    /// <c>[Explicit]</c>: normal test kosusunda calismaz; rapor uretmek icin acikca cagrilir.
    /// </para>
    /// </remarks>
    [TestFixture]
    [Explicit("Spike: rapor uretir, normal kosuda calismaz.")]
    public sealed class SpikeZeroAllocation
    {
        private static readonly int[] Buckets = { 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048 };
        private const int VectorSize = 221;
        private const int WarmupCalls = 50;
        private const int MeasureCalls = 200;

        private static readonly StringBuilder Sb = new StringBuilder();

        private static void Log(string s)
        {
            Sb.AppendLine(s);
            TestContext.Progress.WriteLine(s);
        }

        private static void Flush()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "spike_report.txt");
            File.WriteAllText(path, Sb.ToString());
            TestContext.Progress.WriteLine("rapor: " + path);
        }

        private static string ModelPath
        {
            get { return Path.Combine(TestContext.CurrentContext.TestDirectory, "Models", "model_v1.onnx"); }
        }

        [Test]
        public void Spike_RunWithBinding_AllocationPerBucket()
        {
            Assert.That(File.Exists(ModelPath), Is.True, "model bulunamadi: " + ModelPath);

            var options = new SessionOptions();
            options.IntraOpNumThreads = 1;
            options.InterOpNumThreads = 1;
            options.EnableCpuMemArena = true;
            options.EnableMemoryPattern = true;

            using var session = new InferenceSession(ModelPath, options);
            using var runOptions = new RunOptions();

            Log("=== Faz 4 v3 Bolum 4.5 sifir-allocation spike ===");
            Log("ORT surumu: " + OrtEnv.Instance().GetVersionString());
            Log("bucket | bytes/call | us/call | calls/s");

            foreach (int bucket in Buckets)
            {
                var r = MeasureBucket(session, runOptions, bucket);
                Log($"{bucket,6} | {r.BytesPerCall,10} | {r.UsPerCall,7:F2} | {1e6 / r.UsPerCall,10:F0}");
            }

            Log("=== end spike ===");
            Flush();
        }

        [Test]
        public void Spike_DefaultRunPath_AllocationPerBucket()
        {
            Assert.That(File.Exists(ModelPath), Is.True, "model bulunamadi: " + ModelPath);

            var options = new SessionOptions();
            options.IntraOpNumThreads = 1;
            options.InterOpNumThreads = 1;

            using var session = new InferenceSession(ModelPath, options);

            Log("=== karsilastirma: varsayilan Run yolu ===");
            Log("bucket | bytes/call | us/call");

            foreach (int bucket in new[] { 1, 64, 2048 })
            {
                float[] input = new float[bucket * VectorSize];
                for (int i = 0; i < input.Length; i++)
                {
                    input[i] = (i % 17) * 0.01f;
                }

                var inputTensor = new Microsoft.ML.OnnxRuntime.Tensors.DenseTensor<float>(input, new[] { bucket, VectorSize });
                var inputs = new List<NamedOnnxValue> { NamedOnnxValue.CreateFromTensor("features", inputTensor) };

                for (int i = 0; i < WarmupCalls; i++)
                {
                    using var warm = session.Run(inputs);
                }

                long before = GC.GetAllocatedBytesForCurrentThread();
                var sw = System.Diagnostics.Stopwatch.StartNew();
                for (int i = 0; i < MeasureCalls; i++)
                {
                    using var res = session.Run(inputs);
                }
                sw.Stop();
                long after = GC.GetAllocatedBytesForCurrentThread();

                double usPerCall = sw.Elapsed.TotalMilliseconds * 1000.0 / MeasureCalls;
                Log($"{bucket,6} | {(after - before) / MeasureCalls,10} | {usPerCall,7:F2}");
            }

            Log("=== end karsilastirma ===");
            Flush();
        }

        private static (int Bucket, long BytesPerCall, double UsPerCall) MeasureBucket(
            InferenceSession session, RunOptions runOptions, int bucket)
        {
            // Sabitlenmis (pinned) tamponlar: GC tarafindan tasinmaz, ORT dogrudan uzerine yazar.
            float[] input = GC.AllocateArray<float>(bucket * VectorSize, pinned: true);
            float[] valueOut = GC.AllocateArray<float>(bucket, pinned: true);
            float[] policyOut = GC.AllocateArray<float>(bucket, pinned: true);

            for (int i = 0; i < input.Length; i++)
            {
                input[i] = (i % 17) * 0.01f;
            }

            // Sekil dizileri onceden olusturulur; CreateTensorValueFromMemory(long[]) her cagrida
            // yeni dizi istemez, ayni diziyi tekrar kullaniyoruz.
            long[] inputShape = { bucket, VectorSize };
            long[] outputShape = { bucket, 1 };

            using var inputValue = OrtValue.CreateTensorValueFromMemory(
                OrtMemoryInfo.DefaultInstance, new Memory<float>(input), inputShape);
            using var valueValue = OrtValue.CreateTensorValueFromMemory(
                OrtMemoryInfo.DefaultInstance, new Memory<float>(valueOut), outputShape);
            using var policyValue = OrtValue.CreateTensorValueFromMemory(
                OrtMemoryInfo.DefaultInstance, new Memory<float>(policyOut), outputShape);

            using var binding = session.CreateIoBinding();
            binding.BindInput("features", inputValue);
            binding.BindOutput("value", valueValue);
            binding.BindOutput("policy_logit", policyValue);

            for (int i = 0; i < WarmupCalls; i++)
            {
                binding.SynchronizeBoundInputs();
                session.RunWithBinding(runOptions, binding);
                binding.SynchronizeBoundOutputs();
            }

            long before = GC.GetAllocatedBytesForCurrentThread();
            var sw = System.Diagnostics.Stopwatch.StartNew();

            for (int i = 0; i < MeasureCalls; i++)
            {
                binding.SynchronizeBoundInputs();
                session.RunWithBinding(runOptions, binding);
                binding.SynchronizeBoundOutputs();
            }

            sw.Stop();
            long after = GC.GetAllocatedBytesForCurrentThread();

            long bytes = after - before;
            double usPerCall = sw.Elapsed.TotalMilliseconds * 1000.0 / MeasureCalls;
            return (bucket, bytes / MeasureCalls, usPerCall);
        }
    }
}