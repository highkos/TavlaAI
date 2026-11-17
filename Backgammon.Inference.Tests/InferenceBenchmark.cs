using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using Backgammon.Core;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 4 v3 Bolum 4.6: CPU vs CUDA cikarim olcumu.
    /// </summary>
    /// <remarks>
    /// Bu testler <see cref="ExplicitAttribute"/>'tir; normal kosuda calismaz.
    /// Calistirmak icin: <c>dotnet test -- NUnit.ExplicitMode=None</c>.
    /// Rapor <c>ml/artifacts/inference_benchmark.txt</c> dosyasina yazilir.
    /// </remarks>
    [TestFixture]
    [Explicit("Faz 4 v3 Bolum 4.6 olcum testi; elle calistirilir.")]
    public sealed class InferenceBenchmark
    {
        private static readonly int[] Buckets = { 1, 8, 32, 128, 512, 2048 };

        private static VectorizerScalars MoneyScalars()
        {
            return new VectorizerScalars(1, 0, 0, 0, 0, false);
        }

        private static AfterStateList BuildList(int minCount)
        {
            var list = new AfterStateList(4096);
            var rng = new Xoshiro256StarStar(0x5EED1234UL);
            var state = new BackgammonState();
            var scratch = new AfterStateList();
            var tmp = new BackgammonState();
            int nonTerminal = 0;

            while (nonTerminal < minCount)
            {
                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);
                int plies = 0;
                while (plies < 200 && nonTerminal < minCount)
                {
                    GameResult result;
                    if (BackgammonEngine.IsGameOver(state, out result))
                    {
                        break;
                    }

                    BackgammonEngine.RollDice(state, rng);
                    scratch.Clear();
                    LegalMoveGenerator.GenerateAfterStates(state, EngineSettings.Default, scratch);
                    if (scratch.Count == 0)
                    {
                        BackgammonEngine.PassTurn(state);
                        plies++;
                        continue;
                    }

                    for (int i = 0; i < scratch.Count && nonTerminal < minCount; i++)
                    {
                        if (scratch.IsTerminal[i])
                        {
                            continue;
                        }

                        tmp.CopyFrom(state);
                        BackgammonEngine.LoadAfterState(tmp, scratch, i);
                        list.Add(tmp, scratch.Sequences[i]);
                        nonTerminal++;
                    }

                    int pick = (int)(rng.NextUInt() % (uint)scratch.Count);
                    BackgammonEngine.ApplyMove(state, scratch.Sequences[pick]);
                    if (!BackgammonEngine.IsGameOver(state, out result))
                    {
                        BackgammonEngine.EndTurn(state);
                    }

                    plies++;
                }
            }

            return list;
        }

        private static void Measure(OnnxPolicyValueEvaluator evaluator, AfterStateList list, int bucket,
                                    out double usPerCall, out double positionsPerSecond)
        {
            var values = new float[bucket];
            VectorizerScalars scalars = MoneyScalars();

            for (int i = 0; i < 5; i++)
            {
                evaluator.EvaluateBatch(list, 0, bucket, 1, scalars, values);
            }

            int iterations = Math.Max(3, 20000 / bucket);
            long start = Stopwatch.GetTimestamp();
            for (int i = 0; i < iterations; i++)
            {
                evaluator.EvaluateBatch(list, 0, bucket, 1, scalars, values);
            }

            long elapsed = Stopwatch.GetTimestamp() - start;
            double totalUs = elapsed * 1_000_000.0 / Stopwatch.Frequency;
            usPerCall = totalUs / iterations;
            positionsPerSecond = bucket * iterations * 1_000_000.0 / totalUs;
        }

        [Test]
        public void Bench_CpuVsCuda()
        {
            AfterStateList list = BuildList(2048);
            var report = new StringBuilder();
            report.AppendLine("Faz 4 v3 Bolum 4.6 - Cikarim olcumu");
            report.AppendLine("ORT surumu: " + Microsoft.ML.OnnxRuntime.OrtEnv.Instance().GetVersionString());
            report.AppendLine("Model: " + InferenceTestSupport.ModelPath);
            report.AppendLine("Makine: " + Environment.MachineName + ", " + Environment.ProcessorCount + " mantiksal cekirdek");
            report.AppendLine();

            // ---------------- CPU (1 intra-op is parcacigi) ----------------
            report.AppendLine("[CPUExecutionProvider, IntraOpThreads=1, InterOpThreads=1]");
            report.AppendLine("bucket;usPerCall;positionsPerSecond");
            using (OnnxModelHandle model = OnnxModelHandle.Load(InferenceTestSupport.ModelPath, OnnxEvaluatorOptions.Default))
            using (var evaluator = new OnnxPolicyValueEvaluator(model))
            {
                foreach (int bucket in Buckets)
                {
                    double us;
                    double pps;
                    Measure(evaluator, list, bucket, out us, out pps);
                    report.AppendLine(bucket + ";" + us.ToString("F2") + ";" + pps.ToString("F0"));
                }
            }

            report.AppendLine();

            // ---------------- CUDA ----------------
            report.AppendLine("[CUDAExecutionProvider]");
            var cudaOptions = new OnnxEvaluatorOptions
            {
                UseCuda = true,
                IntraOpThreads = 1,
                InterOpThreads = 1,
                MaxBatch = 2048,
                DisableTf32 = true,
            };

            try
            {
                using OnnxModelHandle cudaModel = OnnxModelHandle.Load(InferenceTestSupport.ModelPath, cudaOptions);
                using var cudaEvaluator = new OnnxPolicyValueEvaluator(cudaModel, cudaOptions);
                report.AppendLine("bucket;usPerCall;positionsPerSecond");
                foreach (int bucket in Buckets)
                {
                    double us;
                    double pps;
                    Measure(cudaEvaluator, list, bucket, out us, out pps);
                    report.AppendLine(bucket + ";" + us.ToString("F2") + ";" + pps.ToString("F0"));
                }

                report.AppendLine();
                report.AppendLine("[CPU vs CUDA cikti paritesi]");
                report.AppendLine("bucket;maxAbsDeltaValue;maxAbsDeltaPriority");
                using (OnnxModelHandle cpuModel = OnnxModelHandle.Load(InferenceTestSupport.ModelPath, OnnxEvaluatorOptions.Default))
                using (var cpuEvaluator = new OnnxPolicyValueEvaluator(cpuModel))
                {
                    foreach (int bucket in Buckets)
                    {
                        var cpuValues = new float[bucket];
                        var cudaValues = new float[bucket];
                        var cpuPriorities = new float[bucket];
                        var cudaPriorities = new float[bucket];

                        cpuEvaluator.EvaluateAndScoreBatch(list, 0, bucket, 1, MoneyScalars(), cpuValues, cpuPriorities);
                        cudaEvaluator.EvaluateAndScoreBatch(list, 0, bucket, 1, MoneyScalars(), cudaValues, cudaPriorities);

                        float maxValueDelta = 0f;
                        float maxPriorityDelta = 0f;
                        for (int i = 0; i < bucket; i++)
                        {
                            maxValueDelta = Math.Max(maxValueDelta, Math.Abs(cpuValues[i] - cudaValues[i]));
                            maxPriorityDelta = Math.Max(maxPriorityDelta, Math.Abs(cpuPriorities[i] - cudaPriorities[i]));
                        }

                        report.AppendLine(bucket + ";" + maxValueDelta.ToString("E3") + ";" + maxPriorityDelta.ToString("E3"));

                        Assert.That(maxValueDelta, Is.LessThanOrEqualTo(1e-4f),
                            "bucket=" + bucket + " value paritesi bozuk: " + maxValueDelta);
                        Assert.That(maxPriorityDelta, Is.LessThanOrEqualTo(1e-4f),
                            "bucket=" + bucket + " priority paritesi bozuk: " + maxPriorityDelta);
                    }
                }
            }
            catch (Exception ex)
            {
                report.AppendLine("OLCULEMEDI: CUDA Execution Provider bu makinede kullanilamiyor.");
                report.AppendLine("Sebep: " + ex.GetType().Name + ": " + ex.Message);
                report.AppendLine("Not: uydurma deger yazilmaz (Faz 1 kurali).");
            }

            report.AppendLine();
            report.AppendLine("Karar kurali (Faz 4 v3 Bolum 4.6):");
            report.AppendLine("- Self-play tek surec, kucuk/orta batch (<= 2048) ile calisir; CPU EP yeterlidir.");
            report.AppendLine("- GPU yalnizca cok oyunculu toplu cikarim sunucusunda anlamli olur; kapsam disi (Bolum 10).");
            report.AppendLine("- CUDA EP kurulu degilse GPU olcumu yapilmaz ve rapor bunu acikca belirtir.");
            report.AppendLine("- Kucuk batch'lerde (<= 128) GPU, cekirdek baslatma gecikmesi (~170 us) nedeniyle");
            report.AppendLine("  CPU'dan yavastir; GPU ancak buyuk batch'lerde one gecer (kesisme noktasi olculur).");

            string text = report.ToString();
            TestContext.Out.WriteLine(text);

            string outDir = Path.Combine(InferenceTestSupport.RepoRoot(), "ml", "artifacts");
            Directory.CreateDirectory(outDir);
            File.WriteAllText(Path.Combine(outDir, "inference_benchmark.txt"), text, new UTF8Encoding(false));
        }
    }
}