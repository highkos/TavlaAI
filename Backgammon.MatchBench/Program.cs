using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Backgammon.Core;
using Backgammon.Inference;

namespace Backgammon.MatchBench
{
    /// <summary>
    /// Faz 5 §9.2: küp ve maç katmanının ölçüm koşum takımı.
    /// </summary>
    /// <remarks>
    /// <para>Alt komutlar:</para>
    /// <list type="bullet">
    /// <item><c>met</c> — gömülü MET'i gnubg XML'i ile karşılaştırır.</item>
    /// <item><c>cube</c> — verilen pozisyonlar için <see cref="EquityCubeAdvisor"/> kararlarını üretir.</item>
    /// <item><c>match-gain</c> — <see cref="MatchAwareEvaluator"/> açık/kapalı, <c>PipBot</c>'a karşı maç oynatır.</item>
    /// <item><c>crawford</c> — Crawford/post-Crawford küp senaryolarını doğrular.</item>
    /// </list>
    /// </remarks>
    public static class Program
    {
        private const string GnubgMetPath = @"F:\Program Files (x86)\gnubg\met\Rockwell-Kazaross.xml";

        public static int Main(string[] args)
        {
            if (args.Length == 0)
            {
                PrintUsage();
                return 0;
            }

            try
            {
                switch (args[0])
                {
                    case "met":
                        return RunMet(args);
                    case "cube":
                        return RunCube(args);
                    case "match-gain":
                        return RunMatchGain(args);
                    case "crawford":
                        return RunCrawford(args);
                    case "gen-positions":
                        return RunGenPositions(args);
                    case "cube-dice":
                        return RunCubeDice(args);
                    case "probe":
                        return RunProbe(args);
                    case "dump-afterstates":
                        return RunDumpAfterStates(args);
                    case "bench":
                        return RunBench(args);
                    case "decision-latency":
                        return RunDecisionLatency(args);
                    case "--help":
                    case "-h":
                        PrintUsage();
                        return 0;
                    default:
                        Console.Error.WriteLine("Bilinmeyen alt komut: " + args[0]);
                        PrintUsage();
                        return 2;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Hata: " + ex.Message);
                Console.Error.WriteLine(ex.StackTrace);
                return 1;
            }
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Kullanim:");
            Console.WriteLine("  Backgammon.MatchBench met [--xml <yol>] [--out <json>]");
            Console.WriteLine("  Backgammon.MatchBench cube --positions <in.json> --out <out.json> [--model <onnx>] [--dice-averaged 0|1]");
            Console.WriteLine("  Backgammon.MatchBench match-gain --model <onnx> --games 200 --out <json>");
            Console.WriteLine("  Backgammon.MatchBench crawford --out <json>");
            Console.WriteLine("  Backgammon.MatchBench gen-positions --count 200 --out <json> [--seed 1]");
            Console.WriteLine("  Backgammon.MatchBench cube-dice --positions <in.json> --out <out.json> [--model <onnx>]");
            Console.WriteLine("  Backgammon.MatchBench bench --model <onnx> --out <json> [--cuda 0|1] [--buckets 1,8,32,128,512,2048]");
            Console.WriteLine("  Backgammon.MatchBench decision-latency --model <onnx> --out <json> [--depth 2] [--positions 30] [--max-root 4] [--max-inner 4] [--tt-capacity 1048576]");
        }

        // ------------------------------------------------------------------
        // bench — ONNX cikarim hizi (Faz 6 §13.4)
        // ------------------------------------------------------------------

        /// <summary>
        /// Verilen model icin kova basina cikarim hizini olcer (pozisyon/sn).
        /// </summary>
        /// <remarks>
        /// Faz 6 §13.4 performans tablosu "regresyon yok" kapisi ister; Faz 5 sayilari
        /// tek cikti degerli modelle alinmisti. 6 cikti kafasi ayni govdeyi kullandigi
        /// icin hizin degismemesi beklenir, ama bu <b>olculur</b>, varsayilmaz.
        /// </remarks>
        private static int RunBench(string[] args)
        {
            string modelPath = DefaultModelPath();
            string outPath = null;
            bool useCuda = false;
            int[] buckets = { 1, 8, 32, 128, 512, 2048 };

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--cuda" && i + 1 < args.Length)
                {
                    useCuda = args[++i] != "0" && args[i] != "false";
                }
                else if (args[i] == "--buckets" && i + 1 < args.Length)
                {
                    string[] parts = args[++i].Split(',');
                    var parsed = new List<int>(parts.Length);
                    foreach (string p in parts)
                    {
                        parsed.Add(int.Parse(p.Trim(), CultureInfo.InvariantCulture));
                    }

                    buckets = parsed.ToArray();
                }
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;
            options.UseCuda = useCuda;

            int maxBucket = 1;
            foreach (int b in buckets)
            {
                if (b > maxBucket)
                {
                    maxBucket = b;
                }
            }

            AfterStateList list = BuildBenchList(maxBucket);

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath, options);
            using var evaluator = new OnnxPolicyValueEvaluator(handle, options);

            var sb = new StringBuilder();
            sb.Append("{\n  \"model\": ").Append(JsonString(handle.ModelPath));
            sb.Append(",\n  \"outputVersion\": ").Append(handle.OutputVersion);
            sb.Append(",\n  \"provider\": ").Append(JsonString(useCuda ? "cuda" : "cpu"));
            sb.Append(",\n  \"machine\": ").Append(JsonString(Environment.MachineName));
            sb.Append(",\n  \"logicalCores\": ").Append(Environment.ProcessorCount);
            sb.Append(",\n  \"buckets\": [");

            VectorizerScalars scalars = new VectorizerScalars(1, 0, 0, 0, 0, false);
            int written = 0;

            foreach (int bucket in buckets)
            {
                var values = new float[bucket];

                for (int i = 0; i < 5; i++)
                {
                    evaluator.EvaluateBatch(list, 0, bucket, 1, scalars, values);
                }

                int iterations = Math.Max(3, 20000 / bucket);
                long start = System.Diagnostics.Stopwatch.GetTimestamp();
                for (int i = 0; i < iterations; i++)
                {
                    evaluator.EvaluateBatch(list, 0, bucket, 1, scalars, values);
                }

                long elapsed = System.Diagnostics.Stopwatch.GetTimestamp() - start;
                double totalUs = elapsed * 1_000_000.0 / System.Diagnostics.Stopwatch.Frequency;
                double usPerCall = totalUs / iterations;
                double positionsPerSecond = bucket * iterations * 1_000_000.0 / totalUs;

                sb.Append(written == 0 ? "\n" : ",\n");
                sb.Append("    {\"bucket\": ").Append(bucket);
                sb.Append(", \"usPerCall\": ").Append(Num(usPerCall));
                sb.Append(", \"positionsPerSecond\": ").Append(Num(positionsPerSecond));
                sb.Append('}');
                written++;

                Console.WriteLine(string.Format(CultureInfo.InvariantCulture,
                    "bench: kova {0,5}  {1,10:F2} us  {2,12:F0} poz/sn", bucket, usPerCall, positionsPerSecond));
            }

            sb.Append("\n  ]\n}\n");

            if (outPath != null)
            {
                WriteText(outPath, sb.ToString());
                Console.WriteLine("bench: " + outPath);
            }

            return 0;
        }

        // ------------------------------------------------------------------
        // decision-latency — depth N karar suresi (Faz 7 §5.2 bacak b)
        // ------------------------------------------------------------------

        /// <summary>
        /// Gercek ONNX modeliyle depth N karar suresini olcer (p50 / p95 / ortalama).
        /// </summary>
        /// <remarks>
        /// <para>
        /// Faz 7 §5.2 karar kuralinin (b) bacagi "large depth 2 p95 &lt;= 2 s/karar" der.
        /// Faz 6 Test 79 bu esigi <b>sentetik</b> <c>HashEvaluator</c> ile olctu; gercek
        /// modelin maliyeti farklidir (ONNX cikarimi + politika siralama). Bu komut
        /// esigi <b>gercek modelle</b> olcer.
        /// </para>
        /// <para>
        /// Pozisyonlar <see cref="BuildBenchList"/> ile ayni sekilde uretilir: rastgele
        /// oynanan oyunlardan terminal olmayan afterstate'ler. Her pozisyon icin zar
        /// atilir ve kok aramasi bir kez calistirilir; ilk 4 arama isinma sayilir.
        /// </para>
        /// </remarks>
        private static int RunDecisionLatency(string[] args)
        {
            string modelPath = DefaultModelPath();
            string outPath = null;
            bool useCuda = false;
            // F7-09: uretim derinligi 1'dir. Depth 2 yalnizca olcum amaciyla acikca istenir.
            int depth = SearchSettings.ProductionDepthPly;
            int positions = 30;
            int maxRoot = 4;
            int maxInner = 4;
            int cacheBits = 20;
            int ttCapacity = 1 << 20;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--cuda" && i + 1 < args.Length)
                {
                    useCuda = args[++i] != "0" && args[i] != "false";
                }
                else if (args[i] == "--depth" && i + 1 < args.Length)
                {
                    depth = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--positions" && i + 1 < args.Length)
                {
                    positions = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--max-root" && i + 1 < args.Length)
                {
                    maxRoot = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--max-inner" && i + 1 < args.Length)
                {
                    maxInner = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--cache-bits" && i + 1 < args.Length)
                {
                    cacheBits = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--tt-capacity" && i + 1 < args.Length)
                {
                    ttCapacity = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
            }

            if (positions < 5)
            {
                throw new ArgumentException("--positions en az 5 olmali.");
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;
            options.UseCuda = useCuda;

            var settings = new SearchSettings
            {
                DepthPly = depth,
                MaxCandidatesRoot = maxRoot,
                MaxCandidatesInner = maxInner,
                UseAlphaBeta = true,
                UseStar1 = true,
                UseEvalCache = true,
                UsePolicyOrdering = true,
                ExactRootScores = true,
                PolicyTemperature = 1.0f,
                TranspositionCapacity = ttCapacity,
            };

            var rng = new Xoshiro256StarStar(0x5EEDE4UL);
            var states = BuildDecisionStates(rng, positions);
            var ws = new SearchWorkspace(cacheBits);

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath, options);
            using var evaluator = new OnnxPolicyValueEvaluator(handle, options);

            int warmup = Math.Min(4, states.Count);
            for (int i = 0; i < warmup; i++)
            {
                ws.Reset();
                BackgammonSearch.Search(states[i], settings, EngineSettings.Default, ws, evaluator, evaluator);
            }

            var samples = new double[states.Count];
            long evaluatorCalls = 0;
            long policyCalls = 0;
            long nodesVisited = 0;
            var sw = new System.Diagnostics.Stopwatch();
            for (int i = 0; i < states.Count; i++)
            {
                ws.Reset();
                sw.Restart();
                SearchResult sr = BackgammonSearch.Search(
                    states[i], settings, EngineSettings.Default, ws, evaluator, evaluator);
                sw.Stop();
                samples[i] = sw.Elapsed.TotalSeconds;
                evaluatorCalls += sr.EvaluatorCalls;
                policyCalls += sr.PolicyCalls;
                nodesVisited += sr.NodesVisited;
            }

            Array.Sort(samples);
            double p50 = samples[(int)(samples.Length * 0.50)];
            double p95 = samples[Math.Min(samples.Length - 1, (int)Math.Ceiling(samples.Length * 0.95) - 1)];
            double mean = 0.0;
            for (int i = 0; i < samples.Length; i++)
            {
                mean += samples[i];
            }

            mean /= samples.Length;

            var sb = new StringBuilder();
            sb.Append("{\n  \"model\": ").Append(JsonString(handle.ModelPath));
            sb.Append(",\n  \"outputVersion\": ").Append(handle.OutputVersion);
            sb.Append(",\n  \"provider\": ").Append(JsonString(useCuda ? "cuda" : "cpu"));
            sb.Append(",\n  \"depth\": ").Append(depth);
            sb.Append(",\n  \"positions\": ").Append(states.Count);
            sb.Append(",\n  \"maxRoot\": ").Append(maxRoot);
            sb.Append(",\n  \"maxInner\": ").Append(maxInner);
            sb.Append(",\n  \"cacheBits\": ").Append(cacheBits);
            sb.Append(",\n  \"ttCapacity\": ").Append(ttCapacity);
            sb.Append(",\n  \"evaluatorCalls\": ").Append(evaluatorCalls);
            sb.Append(",\n  \"policyCalls\": ").Append(policyCalls);
            sb.Append(",\n  \"nodesVisited\": ").Append(nodesVisited);
            sb.Append(",\n  \"p50Seconds\": ").Append(Num(p50));
            sb.Append(",\n  \"p95Seconds\": ").Append(Num(p95));
            sb.Append(",\n  \"meanSeconds\": ").Append(Num(mean));
            sb.Append(",\n  \"minSeconds\": ").Append(Num(samples[0]));
            sb.Append(",\n  \"maxSeconds\": ").Append(Num(samples[samples.Length - 1]));
            sb.Append("\n}\n");

            Console.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "decision-latency: depth {0}, {1} pozisyon | p50={2:F4} s | p95={3:F4} s | ortalama={4:F4} s | " +
                "eval cagrisi={5} | politika cagrisi={6} | dugum={7}",
                depth, states.Count, p50, p95, mean, evaluatorCalls, policyCalls, nodesVisited));

            if (outPath != null)
            {
                WriteText(outPath, sb.ToString());
                Console.WriteLine("decision-latency: " + outPath);
            }

            return 0;
        }

        /// <summary>Karar suresi olcumu icin zar atilmis, oyunu bitmemis pozisyonlar uretir.</summary>
        private static List<BackgammonState> BuildDecisionStates(Xoshiro256StarStar rng, int count)
        {
            var states = new List<BackgammonState>(count);
            var state = new BackgammonState();
            var scratch = new AfterStateList();

            while (states.Count < count)
            {
                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);
                int plies = 0;
                while (plies < 200 && states.Count < count)
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

                    var copy = new BackgammonState();
                    copy.CopyFrom(state);
                    states.Add(copy);

                    int pick = (int)(rng.NextUInt() % (uint)scratch.Count);
                    BackgammonEngine.ApplyMove(state, scratch.Sequences[pick]);
                    if (!BackgammonEngine.IsGameOver(state, out result))
                    {
                        BackgammonEngine.EndTurn(state);
                    }

                    plies++;
                }
            }

            return states;
        }

        /// <summary>Olcum icin gercekci afterstate listesi uretir (terminal olmayan).</summary>
        private static AfterStateList BuildBenchList(int minCount)
        {
            // F7-34: sabit 4096 yerine varsayilan kapasite; tek dogru kaynak AfterStateList.
            var list = new AfterStateList();
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

        // ------------------------------------------------------------------
        // met
        // ------------------------------------------------------------------

        private static int RunMet(string[] args)
        {
            string xmlPath = GnubgMetPath;
            string outPath = null;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--xml" && i + 1 < args.Length)
                {
                    xmlPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
            }

            MatchEquityTable met = MatchEquityTable.Default;
            int n = met.MaxMatchLength;

            double worst = 0.0;
            int worstA = 0;
            int worstB = 0;
            int compared = 0;

            if (File.Exists(xmlPath))
            {
                double[,] xml = ReadGnubgMet(xmlPath);
                int xmlN = xml.GetLength(0);

                for (int a = 1; a <= n && a <= xmlN; a++)
                {
                    for (int b = 1; b <= n && b <= xmlN; b++)
                    {
                        double delta = Math.Abs(met.MatchWinningChance(a, b) - xml[a - 1, b - 1]);
                        compared++;
                        if (delta > worst)
                        {
                            worst = delta;
                            worstA = a;
                            worstB = b;
                        }
                    }
                }
            }
            else
            {
                Console.WriteLine("UYARI: gnubg MET XML bulunamadi: " + xmlPath);
            }

            Console.WriteLine("MET: maxMatchLength = " + n + ", karsilastirilan hucre = " + compared);
            Console.WriteLine("MET: maksimum |delta| = " + worst.ToString("E3", CultureInfo.InvariantCulture) +
                              " (a=" + worstA + ", b=" + worstB + ")");

            if (outPath != null)
            {
                var sb = new StringBuilder();
                sb.Append("{\n  \"maxMatchLength\": ").Append(n);
                sb.Append(",\n  \"comparedCells\": ").Append(compared);
                sb.Append(",\n  \"maxAbsDelta\": ").Append(Num(worst));
                sb.Append(",\n  \"worstCell\": [").Append(worstA).Append(", ").Append(worstB).Append(']');
                sb.Append("\n}\n");
                WriteText(outPath, sb.ToString());
            }

            return worst <= 1e-12 ? 0 : 1;
        }

        private static double[,] ReadGnubgMet(string path)
        {
            XDocument doc = XDocument.Load(path);
            XElement table = null;
            foreach (XElement e in doc.Descendants())
            {
                if (e.Name.LocalName == "pre-crawford-table")
                {
                    table = e;
                    break;
                }
            }

            if (table == null)
            {
                throw new InvalidDataException("pre-crawford-table bulunamadi: " + path);
            }

            var rows = new List<double[]>();
            foreach (XElement row in table.Elements())
            {
                if (row.Name.LocalName != "row")
                {
                    continue;
                }

                var values = new List<double>();
                foreach (XElement cell in row.Elements())
                {
                    if (cell.Name.LocalName == "me")
                    {
                        values.Add(double.Parse(cell.Value.Trim(), CultureInfo.InvariantCulture));
                    }
                }

                rows.Add(values.ToArray());
            }

            int n = rows.Count;
            var result = new double[n, n];
            for (int a = 0; a < n; a++)
            {
                for (int b = 0; b < n; b++)
                {
                    result[a, b] = rows[a][b];
                }
            }

            return result;
        }

        // ------------------------------------------------------------------
        // cube
        // ------------------------------------------------------------------

        private static int RunCube(string[] args)
        {
            string positionsPath = null;
            string outPath = null;
            string modelPath = null;
            bool diceAveraged = true;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--positions" && i + 1 < args.Length)
                {
                    positionsPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
                else if (args[i] == "--dice-averaged" && i + 1 < args.Length)
                {
                    diceAveraged = args[++i] != "0" && args[i] != "false";
                }
            }

            if (positionsPath == null || outPath == null)
            {
                Console.Error.WriteLine("cube: --positions ve --out zorunlu.");
                return 2;
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath ?? DefaultModelPath(), options);
            using var inner = new OnnxPolicyValueEvaluator(handle, options);

            // Faz 6 §10.3: 6 çıktılı kafa varsa dağılımı doğrudan ağdan al; yoksa sezgisel
            // türetme (Faz 5 davranışı) kullanılır.
            IOutcomeDistributionEvaluator distribution = handle.OutputVersion >= 2
                ? (IOutcomeDistributionEvaluator)inner
                : new HeuristicOutcomeDistributionEvaluator(inner);

            var advisor = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution,
                                                new CubeAdvisorOptions { DiceAveraged = diceAveraged });

            using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(positionsPath));
            JsonElement cases = doc.RootElement.GetProperty("cases");

            var sb = new StringBuilder();
            sb.Append("{\n  \"model\": ").Append(JsonString(handle.ModelPath));
            sb.Append(",\n  \"cases\": [");

            int index = 0;
            int doubles = 0;
            int takes = 0;

            foreach (JsonElement c in cases.EnumerateArray())
            {
                BackgammonState state = StateFromJson(c);
                CubeDecision d = advisor.Decide(state, state.turn);

                // Erken cikis (teklif edilemez / Crawford / olu kup) gercek degerlendirme yapmaz.
                bool evaluated = state.phase == GamePhase.PreRoll && BackgammonEngine.CanOffer(state) &&
                                 !MatchState.From(state).IsCrawfordGame && !MatchState.From(state).IsDeadCube;

                if (d.ShouldDouble)
                {
                    doubles++;
                }

                if (d.ShouldTake)
                {
                    takes++;
                }

                sb.Append(index == 0 ? "\n" : ",\n");
                sb.Append("    {\"name\": ").Append(JsonString(c.GetProperty("name").GetString()));
                sb.Append(", \"shouldDouble\": ").Append(d.ShouldDouble ? "true" : "false");
                sb.Append(", \"shouldTake\": ").Append(d.ShouldTake ? "true" : "false");
                sb.Append(", \"isTooGood\": ").Append(d.IsTooGood ? "true" : "false");
                sb.Append(", \"isDeadCube\": ").Append(d.IsDeadCube ? "true" : "false");
                sb.Append(", \"evaluated\": ").Append(evaluated ? "true" : "false");
                sb.Append(", \"equityNoDouble\": ").Append(Num(d.EquityNoDouble));
                sb.Append(", \"equityDoubleTake\": ").Append(Num(d.EquityDoubleTake));
                sb.Append(", \"equityDoublePass\": ").Append(Num(d.EquityDoublePass));
                sb.Append('}');
                index++;
            }

            sb.Append("\n  ],\n  \"count\": ").Append(index);
            sb.Append(",\n  \"doubleCount\": ").Append(doubles);
            sb.Append(",\n  \"takeCount\": ").Append(takes);
            sb.Append("\n}\n");

            WriteText(outPath, sb.ToString());
            Console.WriteLine("cube: " + index + " pozisyon, " + doubles + " ciftle, " + takes + " kabul.");
            return 0;
        }

        private static BackgammonState StateFromJson(JsonElement c)
        {
            var state = new BackgammonState();
            state.Reset();

            JsonElement board = c.GetProperty("board");
            int i = 0;
            foreach (JsonElement v in board.EnumerateArray())
            {
                state.board[i++] = (sbyte)v.GetInt32();
            }

            state.turn = (sbyte)c.GetProperty("turn").GetInt32();
            state.whiteBorneOff = (byte)c.GetProperty("whiteOff").GetInt32();
            state.blackBorneOff = (byte)c.GetProperty("blackOff").GetInt32();
            state.cubeValue = c.TryGetProperty("cubeValue", out JsonElement cv) ? cv.GetInt32() : 1;
            state.cubeOwner = c.TryGetProperty("cubeOwner", out JsonElement co) ? (sbyte)co.GetInt32() : (sbyte)0;
            state.matchLength = c.TryGetProperty("matchLength", out JsonElement ml) ? ml.GetInt32() : 0;
            state.whiteScore = c.TryGetProperty("whiteScore", out JsonElement ws) ? ws.GetInt32() : 0;
            state.blackScore = c.TryGetProperty("blackScore", out JsonElement bs) ? bs.GetInt32() : 0;
            state.isCrawfordGame = c.TryGetProperty("isCrawfordGame", out JsonElement ic) && ic.GetBoolean();
            state.crawfordPlayed = c.TryGetProperty("crawfordPlayed", out JsonElement cp) && cp.GetBoolean();
            state.phase = c.TryGetProperty("phase", out JsonElement ph) ? ParsePhase(ph) : GamePhase.PreRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);
            return state;
        }

        /// <summary>
        /// JSON'daki <c>phase</c> alanını çözer. Hem sayı (0..5) hem de
        /// <see cref="GamePhase"/> adı (ör. <c>"Moving"</c>) kabul edilir; büyük/küçük harf duyarsızdır.
        /// </summary>
        private static GamePhase ParsePhase(JsonElement e)
        {
            if (e.ValueKind == JsonValueKind.Number)
            {
                int v = e.GetInt32();
                if (v < 0 || v > (int)GamePhase.GameOver)
                {
                    throw new FormatException("phase aralık dışı: " + v);
                }

                return (GamePhase)v;
            }

            string name = e.GetString();
            if (Enum.TryParse(name, ignoreCase: true, out GamePhase parsed) &&
                Enum.IsDefined(typeof(GamePhase), parsed))
            {
                return parsed;
            }

            throw new FormatException("phase çözümlenemedi: " + name);
        }

        // ------------------------------------------------------------------
        // match-gain
        // ------------------------------------------------------------------

        private static int RunMatchGain(string[] args)
        {
            string modelPath = DefaultModelPath();
            string outPath = null;
            int games = 200;
            int depth = 0;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--games" && i + 1 < args.Length)
                {
                    games = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--depth" && i + 1 < args.Length)
                {
                    depth = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath, options);
            using var inner = new OnnxPolicyValueEvaluator(handle, options);

            // Faz 6 §10.3: 6 çıktılı kafa varsa dağılımı doğrudan ağdan al (Faz 6 küp
            // kararı bu dağılıma dayanır); yoksa sezgisel türetme (Faz 5 davranışı).
            IOutcomeDistributionEvaluator distribution = handle.OutputVersion >= 2
                ? (IOutcomeDistributionEvaluator)inner
                : new HeuristicOutcomeDistributionEvaluator(inner);
            MatchEquityTable met = MatchEquityTable.Default;

            int[] lengths = { 2, 4, 5 };
            var sb = new StringBuilder();
            sb.Append("{\n  \"model\": ").Append(JsonString(handle.ModelPath));
            sb.Append(",\n  \"gamesPerCell\": ").Append(games);
            sb.Append(",\n  \"depthPly\": ").Append(depth);
            sb.Append(",\n  \"cells\": [");

            bool first = true;
            foreach (int length in lengths)
            {
                foreach (bool aware in new[] { false, true })
                {
                    MatchReport r = PlayMatchSeries(inner, distribution, met, length, aware, games, depth);

                    sb.Append(first ? "\n" : ",\n");
                    first = false;
                    sb.Append("    {\"matchLength\": ").Append(length);
                    sb.Append(", \"matchAware\": ").Append(aware ? "true" : "false");
                    sb.Append(", \"games\": ").Append(r.Games);
                    sb.Append(", \"wins\": ").Append(r.Wins);
                    sb.Append(", \"losses\": ").Append(r.Losses);
                    sb.Append(", \"draws\": ").Append(r.Draws);
                    sb.Append(", \"winRate\": ").Append(Num(r.WinRate));
                    sb.Append(", \"winRateStdError\": ").Append(Num(r.WinRateStdError));
                    sb.Append(", \"meanMatchPoints\": ").Append(Num(r.MeanMatchPoints));
                    sb.Append(", \"meanMatchPointsStdError\": ").Append(Num(r.MeanMatchPointsStdError));
                    sb.Append(", \"cubeDoubles\": ").Append(r.CubeDoubles);
                    sb.Append(", \"cubePasses\": ").Append(r.CubePasses);
                    sb.Append('}');

                    Console.WriteLine(length + "-away, matchAware=" + aware + ": " +
                                      r.Wins + "/" + r.Games + " (" + (100.0 * r.WinRate).ToString("F2") +
                                      "%), puan/maç = " + r.MeanMatchPoints.ToString("F4") +
                                      " ± " + r.MeanMatchPointsStdError.ToString("F4"));
                }
            }

            sb.Append("\n  ]\n}\n");

            if (outPath != null)
            {
                WriteText(outPath, sb.ToString());
            }

            return 0;
        }

        private struct MatchReport
        {
            public int Games;
            public int Wins;
            public int Losses;
            public int Draws;
            public double WinRate;
            public double WinRateStdError;
            public double MeanMatchPoints;
            public double MeanMatchPointsStdError;
            public int CubeDoubles;
            public int CubePasses;
        }

        private static MatchReport PlayMatchSeries(IPolicyValueEvaluator inner,
                                                   IOutcomeDistributionEvaluator distribution,
                                                   MatchEquityTable met, int matchLength, bool aware,
                                                   int games, int depth)
        {
            var report = new MatchReport { Games = games };
            var points = new double[games];
            var wins = new int[games];

            var state = new BackgammonState();
            var afterStates = new AfterStateList();
            var workspace = new SearchWorkspace();
            EngineSettings es = EngineSettings.Default;
            var ss = new SearchSettings
            {
                DepthPly = depth,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                UseAlphaBeta = true,
                UseStar1 = true,
                UseEvalCache = false,
                UsePolicyOrdering = false,
                ExactRootScores = false,
                PolicyTemperature = 1f,
            };

            for (int g = 0; g < games; g++)
            {
                ulong gameSeed = 0x5EED0000UL + (ulong)g * 0x9E3779B97F4A7C15UL;
                var rng = new Xoshiro256StarStar(gameSeed);
                sbyte learnerSide = (g % 2 == 0) ? (sbyte)1 : (sbyte)-1;

                BackgammonEngine.NewGame(state, new MatchSettings(matchLength));
                BackgammonEngine.RollOpening(state, rng);

                int doubles = 0;
                int passes = 0;
                int plies = 0;
                bool cubePassed = false;

                while (state.phase != GamePhase.GameOver && plies < 20000)
                {
                    MatchState match = MatchState.From(state);
                    IPositionEvaluator positionEvaluator;
                    IPolicyEvaluator policyEvaluator;
                    if (aware)
                    {
                        var matchAware = new MatchAwareEvaluator(inner, met, distribution, match);
                        positionEvaluator = matchAware;
                        policyEvaluator = matchAware;
                    }
                    else
                    {
                        positionEvaluator = inner;
                        policyEvaluator = inner;
                    }

                    if (state.phase == GamePhase.PreRoll && BackgammonEngine.CanOffer(state))
                    {
                        var advisor = new EquityCubeAdvisor(positionEvaluator, met, distribution,
                                                            CubeAdvisorOptions.Default);
                        CubeDecision d = advisor.Decide(state, state.turn);
                        if (d.ShouldDouble)
                        {
                            doubles++;
                            BackgammonEngine.OfferDouble(state);
                            if (d.ShouldTake)
                            {
                                BackgammonEngine.Take(state);
                            }
                            else
                            {
                                passes++;
                                BackgammonEngine.Pass(state);
                                cubePassed = true;
                            }
                        }
                    }

                    if (state.phase == GamePhase.GameOver)
                    {
                        break;
                    }

                    if (state.phase == GamePhase.PreRoll || state.phase == GamePhase.WaitForRoll)
                    {
                        BackgammonEngine.RollDice(state, rng);
                    }

                    if (state.phase != GamePhase.Moving)
                    {
                        plies++;
                        continue;
                    }

                    sbyte mover = state.turn;
                    if (mover == learnerSide)
                    {
                        SearchResult sr = BackgammonSearch.Search(state, ss, es, workspace, positionEvaluator,
                                                                   policyEvaluator);
                        if (sr.IsPass)
                        {
                            BackgammonEngine.PassTurn(state);
                        }
                        else
                        {
                            BackgammonEngine.ApplyMove(state, sr.BestSequence);
                            if (state.phase != GamePhase.GameOver)
                            {
                                BackgammonEngine.EndTurn(state, es);
                            }
                        }
                    }
                    else
                    {
                        PlayPip(state, afterStates, es);
                    }

                    plies++;
                }

                GameResult result;
                if (cubePassed)
                {
                    // Kup reddi: teklif eden oyuncu 1 puan kazanir (mars yok).
                    result = new GameResult(state.turn, GameResultType.Single, 1);
                }
                else if (!BackgammonEngine.IsGameOver(state, es, out result))
                {
                    report.Draws++;
                    points[g] = 0.0;
                    continue;
                }

                double p = result.Winner == learnerSide ? result.Points : -result.Points;
                points[g] = p;
                wins[g] = result.Winner == learnerSide ? 1 : 0;

                if (p > 0)
                {
                    report.Wins++;
                }
                else if (p < 0)
                {
                    report.Losses++;
                }
                else
                {
                    report.Draws++;
                }

                report.CubeDoubles += doubles;
                report.CubePasses += passes;
            }

            report.WinRate = (double)report.Wins / games;
            report.WinRateStdError = Math.Sqrt(report.WinRate * (1.0 - report.WinRate) / games);

            double sum = 0.0;
            for (int i = 0; i < games; i++)
            {
                sum += points[i];
            }

            double mean = sum / games;
            double var = 0.0;
            for (int i = 0; i < games; i++)
            {
                double d = points[i] - mean;
                var += d * d;
            }

            report.MeanMatchPoints = mean;
            report.MeanMatchPointsStdError = games > 1 ? Math.Sqrt(var / (games - 1) / games) : 0.0;
            return report;
        }

        private static void PlayPip(BackgammonState state, AfterStateList afterStates, in EngineSettings es)
        {
            afterStates.Clear();
            LegalMoveGenerator.GenerateAfterStates(state, es, afterStates);

            if (afterStates.Count == 0)
            {
                BackgammonEngine.PassTurn(state);
                return;
            }

            sbyte mover = state.turn;
            int bestIndex = -1;
            int bestScore = int.MinValue;

            for (int i = 0; i < afterStates.Count; i++)
            {
                int score;
                if (afterStates.IsTerminal[i])
                {
                    score = int.MaxValue;
                }
                else
                {
                    ReadOnlySpan<sbyte> board = afterStates.BoardOf(i);
                    int own = BackgammonVectorizer.CalculatePipCount(board, mover);
                    int opp = BackgammonVectorizer.CalculatePipCount(board, -mover);
                    score = opp - own;
                }

                if (score > bestScore)
                {
                    bestScore = score;
                    bestIndex = i;
                }
            }

            BackgammonEngine.ApplyMove(state, afterStates.Sequences[bestIndex]);
            if (state.phase != GamePhase.GameOver)
            {
                BackgammonEngine.EndTurn(state, es);
            }
        }

        private static double SingleEquity(BackgammonState state, IPolicyValueEvaluator evaluator,
                                           in VectorizerScalars scalars, sbyte perspective)
        {
            var list = new AfterStateList(1);
            list.Add(state, default(MoveSequence));
            Span<float> values = stackalloc float[1];
            evaluator.EvaluateBatch(list, 0, 1, perspective, scalars, values);
            return values[0];
        }

        // ------------------------------------------------------------------
        // dump-afterstates
        // ------------------------------------------------------------------

        /// <summary>
        /// Rastgele oyunlardan afterstate'ler uretir, modelin degerini ve tahtayi yazar.
        /// Amac: modelin deger kafasini gnubg ile <b>dogrudan</b> karsilastirmak
        /// (pre-roll yaklasimi devrede degil).
        /// </summary>
        private static int RunDumpAfterStates(string[] args)
        {
            string outPath = null;
            string modelPath = null;
            int count = 400;
            ulong seed = 99UL;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
                else if (args[i] == "--count" && i + 1 < args.Length)
                {
                    count = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--seed" && i + 1 < args.Length)
                {
                    seed = ulong.Parse(args[++i], CultureInfo.InvariantCulture);
                }
            }

            if (outPath == null)
            {
                Console.Error.WriteLine("dump-afterstates: --out zorunlu.");
                return 2;
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath ?? DefaultModelPath(), options);
            using var inner = new OnnxPolicyValueEvaluator(handle, options);

            var rng = new Xoshiro256StarStar(seed);
            var state = new BackgammonState();
            var moves = new MoveList();
            var afterStates = new AfterStateList();
            EngineSettings es = EngineSettings.Default;

            var sb = new StringBuilder();
            sb.Append("{\n  \"cases\": [");
            int written = 0;
            int guard = 0;

            while (written < count && guard < 200000)
            {
                guard++;
                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);
                BackgammonEngine.RollOpening(state, rng);

                int plies = 0;
                while (state.phase != GamePhase.GameOver && plies < 300 && written < count)
                {
                    if (state.phase == GamePhase.PreRoll)
                    {
                        BackgammonEngine.RollDice(state, rng);
                    }

                    if (state.phase != GamePhase.Moving)
                    {
                        plies++;
                        continue;
                    }

                    afterStates.Clear();
                    LegalMoveGenerator.GenerateAfterStates(state, es, afterStates);

                    if (afterStates.Count > 0 && (rng.NextUInt() % 100u) < 25u)
                    {
                        sbyte perspective = state.turn;
                        var scalars = VectorizerScalars.From(state);
                        float[] valueBuffer = new float[afterStates.Count];
                        inner.EvaluateBatch(afterStates, 0, afterStates.Count, perspective, scalars, valueBuffer);

                        for (int i = 0; i < afterStates.Count && written < count; i++)
                        {
                            if (afterStates.IsTerminal[i])
                            {
                                continue;
                            }

                            sb.Append(written == 0 ? "\n" : ",\n");
                            sb.Append("    {\"name\": \"a").Append(written).Append('"');
                            sb.Append(", \"board\": [");
                            ReadOnlySpan<sbyte> b = afterStates.BoardOf(i);
                            for (int k = 0; k < b.Length; k++)
                            {
                                if (k > 0)
                                {
                                    sb.Append(", ");
                                }

                                sb.Append(b[k].ToString(CultureInfo.InvariantCulture));
                            }

                            sb.Append(']');
                            sb.Append(", \"whiteOff\": ").Append(afterStates.WhiteBorneOff[i]);
                            sb.Append(", \"blackOff\": ").Append(afterStates.BlackBorneOff[i]);
                            sb.Append(", \"perspective\": ").Append(perspective);
                            sb.Append(", \"ourValue\": ").Append(Num(valueBuffer[i]));
                            sb.Append('}');
                            written++;
                        }
                    }

                    moves.Clear();
                    LegalMoveGenerator.GenerateAllLegalMoves(state, moves);
                    if (moves.Count == 0)
                    {
                        BackgammonEngine.PassTurn(state);
                    }
                    else
                    {
                        int pick = (int)(rng.NextUInt() % (uint)moves.Count);
                        BackgammonEngine.ApplyMove(state, moves[pick]);
                        if (state.phase != GamePhase.GameOver)
                        {
                            BackgammonEngine.EndTurn(state, es);
                        }
                    }

                    plies++;
                }
            }

            sb.Append("\n  ],\n  \"count\": ").Append(written).Append("\n}\n");
            WriteText(outPath, sb.ToString());
            Console.WriteLine("dump-afterstates: " + written + " kayit -> " + outPath);
            return 0;
        }

        // ------------------------------------------------------------------
        // probe
        // ------------------------------------------------------------------

        private static int RunProbe(string[] args)
        {
            string modelPath = DefaultModelPath();
            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath, options);
            using var inner = new OnnxPolicyValueEvaluator(handle, options);
            Console.WriteLine("model: " + handle.ModelPath);

            var start = new BackgammonState();
            start.Reset();
            start.turn = 1;
            start.phase = GamePhase.PreRoll;
            start.hash = BackgammonEngine.ComputeZobristHash(start);

            Console.WriteLine("baslangic, Beyaz oynayacak:");
            Console.WriteLine("  tek-kayit  E(+1) = " + SingleEquity(start, inner, VectorizerScalars.From(start), 1).ToString("F6"));
            Console.WriteLine("  tek-kayit  E(-1) = " + SingleEquity(start, inner, VectorizerScalars.From(start), -1).ToString("F6"));
            Console.WriteLine("  zar-ort.   E(+1) = " + DiceAveragedEquity(start, inner).ToString("F6"));

            var vp = new float[BackgammonVectorizer.InputVectorSize];
            var vn = new float[BackgammonVectorizer.InputVectorSize];
            BackgammonVectorizer.Vectorize(start, 1, vp);
            BackgammonVectorizer.Vectorize(start, -1, vn);
            int diff = 0;
            for (int i = 0; i < vp.Length; i++)
            {
                if (Math.Abs(vp[i] - vn[i]) > 1e-6f)
                {
                    diff++;
                }
            }

            Console.WriteLine("  vektor farkli eleman sayisi (+1 vs -1): " + diff + " / " + vp.Length);
            Console.WriteLine("  vp[0..5] = " + vp[0].ToString("F2") + " " + vp[1].ToString("F2") + " " +
                              vp[2].ToString("F2") + " " + vp[3].ToString("F2") + " " + vp[4].ToString("F2") + " " +
                              vp[5].ToString("F2"));
            Console.WriteLine("  vn[0..5] = " + vn[0].ToString("F2") + " " + vn[1].ToString("F2") + " " +
                              vn[2].ToString("F2") + " " + vn[3].ToString("F2") + " " + vn[4].ToString("F2") + " " +
                              vn[5].ToString("F2"));

            // Asimetrik pozisyon: Beyaz tum pullari 24-noktasinda (kendi 1-hanesi),
            // Siyah tum pullari 1-noktasinda (kendi 24-hanesi). Beyaz kesin kazanir.
            var won = new BackgammonState();
            won.Reset();
            won.board[24] = 15;
            won.board[1] = -15;
            won.turn = 1;
            won.phase = GamePhase.PreRoll;
            won.hash = BackgammonEngine.ComputeZobristHash(won);
            Console.WriteLine("Beyaz 15/24 vs Siyah 15/1 (Beyaz kesin kazanir):");
            Console.WriteLine("  tek-kayit  E(+1) = " + SingleEquity(won, inner, VectorizerScalars.From(won), 1).ToString("F6"));
            Console.WriteLine("  tek-kayit  E(-1) = " + SingleEquity(won, inner, VectorizerScalars.From(won), -1).ToString("F6"));
            Console.WriteLine("  zar-ort.   E(+1) = " + DiceAveragedEquity(won, inner).ToString("F6"));

            // Ters cevrilmis: Siyah kesin kazanir.
            var lost = new BackgammonState();
            lost.Reset();
            lost.board[1] = 15;
            lost.board[24] = -15;
            lost.turn = 1;
            lost.phase = GamePhase.PreRoll;
            lost.hash = BackgammonEngine.ComputeZobristHash(lost);
            Console.WriteLine("Beyaz 15/1 vs Siyah 15/24 (Siyah kesin kazanir):");
            Console.WriteLine("  tek-kayit  E(+1) = " + SingleEquity(lost, inner, VectorizerScalars.From(lost), 1).ToString("F6"));
            Console.WriteLine("  zar-ort.   E(+1) = " + DiceAveragedEquity(lost, inner).ToString("F6"));

            return 0;
        }

        // ------------------------------------------------------------------
        // cube-dice
        // ------------------------------------------------------------------

        /// <summary>
        /// Pre-roll pozisyonu icin <b>zar beklentili</b> equity: 21 zar kombinasyonunun
        /// en iyi afterstate degerinin agirlikli ortalamasi. §4.4'teki "tek kayit" yaklasiminin
        /// aksine, modeli egitildigi dagilima yakin besler.
        /// </summary>
        private static int RunCubeDice(string[] args)
        {
            string positionsPath = null;
            string outPath = null;
            string modelPath = null;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--positions" && i + 1 < args.Length)
                {
                    positionsPath = args[++i];
                }
                else if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
            }

            if (positionsPath == null || outPath == null)
            {
                Console.Error.WriteLine("cube-dice: --positions ve --out zorunlu.");
                return 2;
            }

            OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
            options.IntraOpThreads = 1;
            options.InterOpThreads = 1;

            using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath ?? DefaultModelPath(), options);
            using var inner = new OnnxPolicyValueEvaluator(handle, options);

            using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(positionsPath));
            JsonElement cases = doc.RootElement.GetProperty("cases");

            var sb = new StringBuilder();
            sb.Append("{\n  \"model\": ").Append(JsonString(handle.ModelPath));
            sb.Append(",\n  \"cases\": [");

            int index = 0;
            foreach (JsonElement c in cases.EnumerateArray())
            {
                BackgammonState state = StateFromJson(c);
                double equity = DiceAveragedEquity(state, inner);

                sb.Append(index == 0 ? "\n" : ",\n");
                sb.Append("    {\"name\": ").Append(JsonString(c.GetProperty("name").GetString()));
                sb.Append(", \"equityDiceAvg\": ").Append(Num(equity));
                sb.Append('}');
                index++;
            }

            sb.Append("\n  ],\n  \"count\": ").Append(index).Append("\n}\n");
            WriteText(outPath, sb.ToString());
            Console.WriteLine("cube-dice: " + index + " pozisyon.");
            return 0;
        }

        private static readonly int[] FirstDice = { 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 6 };
        private static readonly int[] SecondDice = { 1, 2, 3, 4, 5, 6, 2, 3, 4, 5, 6, 3, 4, 5, 6, 4, 5, 6, 5, 6, 6 };

        [ThreadStatic] private static SearchWorkspace _diceAvgWorkspace;
        [ThreadStatic] private static BackgammonState _diceAvgScratch;

        private static double DiceAveragedEquity(BackgammonState state, IPolicyValueEvaluator evaluator)
        {
            // F7-31: workspace ve scratch state yeniden kullanilir; her cagride yeniden
            // ayirmak gereksiz allocation uretiyordu. Her arama oncesi Reset() cagrilir.
            BackgammonState scratch = _diceAvgScratch ??= new BackgammonState();
            SearchWorkspace workspace = _diceAvgWorkspace ??= new SearchWorkspace();
            EngineSettings es = EngineSettings.Default;
            var ss = new SearchSettings
            {
                DepthPly = 0,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                UseAlphaBeta = true,
                UseStar1 = true,
                UseEvalCache = false,
                UsePolicyOrdering = false,
                ExactRootScores = false,
                PolicyTemperature = 1f,
            };

            double total = 0.0;
            int weightSum = 0;

            for (int d = 0; d < 21; d++)
            {
                int d1 = FirstDice[d];
                int d2 = SecondDice[d];
                int weight = d1 == d2 ? 1 : 2;

                scratch.CopyFrom(state);
                BackgammonEngine.SetDice(scratch, d1, d2);

                // DepthPly = 0: afterstate'ler degerlendirilir, terminal kayitlar ve pas
                // arama tarafindan ele alinir.
                workspace.Reset();
                SearchResult sr = BackgammonSearch.Search(scratch, ss, es, workspace, evaluator);
                total += weight * sr.EvaluationScore;
                weightSum += weight;
            }

            return total / weightSum;
        }

        // ------------------------------------------------------------------
        // gen-positions
        // ------------------------------------------------------------------

        private static int RunGenPositions(string[] args)
        {
            string outPath = null;
            int count = 200;
            ulong seed = 1UL;

            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--count" && i + 1 < args.Length)
                {
                    count = int.Parse(args[++i], CultureInfo.InvariantCulture);
                }
                else if (args[i] == "--seed" && i + 1 < args.Length)
                {
                    seed = ulong.Parse(args[++i], CultureInfo.InvariantCulture);
                }
            }

            if (outPath == null)
            {
                Console.Error.WriteLine("gen-positions: --out zorunlu.");
                return 2;
            }

            var rng = new Xoshiro256StarStar(seed);
            var state = new BackgammonState();
            var moves = new MoveList();
            EngineSettings es = EngineSettings.Default;

            var boards = new List<(sbyte[] Board, byte WhiteOff, byte BlackOff, sbyte Turn)>();
            int guard = 0;

            while (boards.Count < count && guard < 200000)
            {
                guard++;
                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);
                BackgammonEngine.RollOpening(state, rng);

                int plies = 0;
                while (state.phase != GamePhase.GameOver && plies < 400)
                {
                    if (state.phase == GamePhase.PreRoll)
                    {
                        BackgammonEngine.RollDice(state, rng);
                    }

                    if (state.phase != GamePhase.Moving)
                    {
                        plies++;
                        continue;
                    }

                    if (boards.Count < count && (rng.NextUInt() % 100u) < 12u)
                    {
                        var copy = new sbyte[BackgammonState.BoardSize];
                        Array.Copy(state.board, copy, copy.Length);
                        boards.Add((copy, state.whiteBorneOff, state.blackBorneOff, state.turn));
                    }

                    moves.Clear();
                    LegalMoveGenerator.GenerateAllLegalMoves(state, moves);
                    if (moves.Count == 0)
                    {
                        BackgammonEngine.PassTurn(state);
                    }
                    else
                    {
                        int pick = (int)(rng.NextUInt() % (uint)moves.Count);
                        BackgammonEngine.ApplyMove(state, moves[pick]);
                        if (state.phase != GamePhase.GameOver)
                        {
                            BackgammonEngine.EndTurn(state, es);
                        }
                    }

                    plies++;
                }
            }

            var sb = new StringBuilder();
            sb.Append("{\n  \"seed\": ").Append(seed);
            sb.Append(",\n  \"cases\": [");

            for (int i = 0; i < boards.Count; i++)
            {
                var b = boards[i];

                // Her tahta icin iki baglam: money game ve rastgele bir mac skoru.
                for (int variant = 0; variant < 2; variant++)
                {
                    int matchLength = 0;
                    int whiteScore = 0;
                    int blackScore = 0;
                    int cubeValue = 1;
                    sbyte cubeOwner = 0;
                    bool crawford = false;
                    bool crawfordPlayed = false;

                    if (variant == 1)
                    {
                        matchLength = 2 + (int)(rng.NextUInt() % 6u);
                        whiteScore = (int)(rng.NextUInt() % (uint)matchLength);
                        blackScore = (int)(rng.NextUInt() % (uint)matchLength);
                        if (whiteScore >= matchLength)
                        {
                            whiteScore = matchLength - 1;
                        }

                        if (blackScore >= matchLength)
                        {
                            blackScore = matchLength - 1;
                        }

                        cubeValue = 1 << (int)(rng.NextUInt() % 3u);
                        cubeOwner = (sbyte)((int)(rng.NextUInt() % 3u) - 1);
                        if (cubeOwner == 0)
                        {
                            cubeOwner = 0;
                        }

                        crawford = matchLength >= 2 && !crawfordPlayed &&
                                   (whiteScore == matchLength - 1 || blackScore == matchLength - 1);
                    }

                    sb.Append(i == 0 && variant == 0 ? "\n" : ",\n");
                    sb.Append("    {\"name\": \"p").Append(i).Append(variant == 0 ? "-money" : "-match").Append('"');
                    sb.Append(", \"board\": [");
                    for (int k = 0; k < b.Board.Length; k++)
                    {
                        if (k > 0)
                        {
                            sb.Append(", ");
                        }

                        sb.Append(b.Board[k].ToString(CultureInfo.InvariantCulture));
                    }

                    sb.Append(']');
                    sb.Append(", \"turn\": ").Append(b.Turn);
                    sb.Append(", \"whiteOff\": ").Append(b.WhiteOff);
                    sb.Append(", \"blackOff\": ").Append(b.BlackOff);
                    sb.Append(", \"cubeValue\": ").Append(cubeValue);
                    sb.Append(", \"cubeOwner\": ").Append(cubeOwner);
                    sb.Append(", \"matchLength\": ").Append(matchLength);
                    sb.Append(", \"whiteScore\": ").Append(whiteScore);
                    sb.Append(", \"blackScore\": ").Append(blackScore);
                    sb.Append(", \"isCrawfordGame\": ").Append(crawford ? "true" : "false");
                    sb.Append(", \"crawfordPlayed\": ").Append(crawfordPlayed ? "true" : "false");
                    sb.Append('}');
                }
            }

            sb.Append("\n  ],\n  \"count\": ").Append(boards.Count * 2).Append("\n}\n");
            WriteText(outPath, sb.ToString());
            Console.WriteLine("gen-positions: " + (boards.Count * 2) + " pozisyon yazildi -> " + outPath);
            return 0;
        }

        // ------------------------------------------------------------------
        // crawford
        // ------------------------------------------------------------------

        private static int RunCrawford(string[] args)
        {
            string outPath = null;
            string modelPath = null;
            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--out" && i + 1 < args.Length)
                {
                    outPath = args[++i];
                }
                else if (args[i] == "--model" && i + 1 < args.Length)
                {
                    modelPath = args[++i];
                }
            }

            var scenarios = new List<(string Name, int MatchLength, int White, int Black, bool Crawford,
                                      bool CrawfordPlayed, int CubeValue, sbyte CubeOwner, sbyte Turn,
                                      float Equity, bool ExpectDouble, bool ExpectTake)>();

            // Crawford oyunu: küp kullanılmaz.
            scenarios.Add(("crawford-no-cube", 5, 4, 0, true, false, 1, 0, 1, 0.9f, false, true));
            scenarios.Add(("crawford-no-cube-black", 5, 0, 4, true, false, 1, 0, -1, 0.9f, false, true));

            // Post-Crawford, 1-away olan taraf teklif edemez (çiftlemek ona hiçbir şey kazandırmaz).
            scenarios.Add(("one-away-cannot-double", 5, 4, 1, false, true, 1, 0, 1, 0.9f, false, true));

            // Post-Crawford, teklif eden 4-away olan taraf.
            scenarios.Add(("post-crawford-free-drop", 5, 4, 1, false, true, 1, 0, -1, 0.9f, true, true));

            // Normal maç oyunu: 5-away/5-away, E = 0.3 ⇒ çiftle, rakip reddeder.
            //
            // F7-72: bu senaryo eskiden E = 0.9 kullanıyordu ve "çiftle" bekliyordu.
            // 5-away/5-away'de E = 0.9 **"çiftlemek için fazla iyi"** bir pozisyondur:
            // rakip serbestçe reddeder, teklif eden 1 puan alır (MWC 0,607) ama oynamaya
            // devam etse marslarla 0,692 MWC'ye ulaşır. Doğru cevap **çiftlememek**tir.
            // Ölçüldü: E = 0.3'te çiftle/reddet, E = 0.9'da çiftleme.
            scenarios.Add(("normal-double-pass", 5, 0, 0, false, false, 1, 0, 1, 0.3f, true, false));

            // F7-72: "çiftlemek için fazla iyi" — çiftleme, rakip reddeder ama oynamak daha iyi.
            scenarios.Add(("too-good-to-double", 5, 0, 0, false, false, 1, 0, 1, 0.9f, false, false));

            // 1-away olan taraf teklif edemez: çiftlemek ona hiçbir şey kazandırmaz.
            // F7-72: senaryo adı "dead-cube" idi ama `IsDeadCube` (CubeValue >= max(away))
            // burada false döner; yanıltıcı ad düzeltildi.
            scenarios.Add(("one-away-no-double", 3, 2, 0, false, true, 1, 0, 1, 0.9f, false, true));

            var sb = new StringBuilder();
            sb.Append("{\n  \"scenarios\": [");

            int correct = 0;
            int index = 0;

            foreach (var s in scenarios)
            {
                var inner = new ConstantEvaluator(s.Equity);
                var distribution = new HeuristicOutcomeDistributionEvaluator(inner);
                var advisor = new EquityCubeAdvisor(inner, MatchEquityTable.Default, distribution,
                                                    CubeAdvisorOptions.Default);

                CubeDecision d = DecideCrawford(advisor, s.MatchLength, s.White, s.Black, s.Crawford,
                                                s.CrawfordPlayed, s.CubeValue, s.CubeOwner, s.Turn);
                bool ok = d.ShouldDouble == s.ExpectDouble && d.ShouldTake == s.ExpectTake;
                if (ok)
                {
                    correct++;
                }

                sb.Append(index == 0 ? "\n" : ",\n");
                sb.Append("    {\"name\": ").Append(JsonString(s.Name));
                sb.Append(", \"shouldDouble\": ").Append(d.ShouldDouble ? "true" : "false");
                sb.Append(", \"shouldTake\": ").Append(d.ShouldTake ? "true" : "false");
                sb.Append(", \"isDeadCube\": ").Append(d.IsDeadCube ? "true" : "false");
                sb.Append(", \"isTooGood\": ").Append(d.IsTooGood ? "true" : "false");
                sb.Append(", \"equity\": ").Append(s.Equity.ToString("F2", CultureInfo.InvariantCulture));
                sb.Append(", \"equityNoDouble\": ").Append(d.EquityNoDouble.ToString("F6", CultureInfo.InvariantCulture));
                sb.Append(", \"equityDoubleTake\": ").Append(d.EquityDoubleTake.ToString("F6", CultureInfo.InvariantCulture));
                sb.Append(", \"equityDoublePass\": ").Append(d.EquityDoublePass.ToString("F6", CultureInfo.InvariantCulture));
                sb.Append(", \"expectedDouble\": ").Append(s.ExpectDouble ? "true" : "false");
                sb.Append(", \"expectedTake\": ").Append(s.ExpectTake ? "true" : "false");
                sb.Append(", \"correct\": ").Append(ok ? "true" : "false");
                sb.Append('}');
                index++;
            }

            sb.Append("\n  ],\n  \"total\": ").Append(index);
            sb.Append(",\n  \"correct\": ").Append(correct);

            // F7-35: senaryolar sabit 0,9 equity ile deterministik kural testidir. Ayni
            // senaryolar gercek modelle de kosulur; kural karari modelden bagimsiz olmali.
            int modelCorrect = -1;
            if (modelPath != null)
            {
                OnnxEvaluatorOptions options = OnnxEvaluatorOptions.Default;
                using OnnxModelHandle handle = OnnxModelHandle.Load(modelPath, options);
                using var evaluator = new OnnxPolicyValueEvaluator(handle, options);
                {
                    var modelDistribution = new HeuristicOutcomeDistributionEvaluator(evaluator);
                    var modelAdvisor = new EquityCubeAdvisor(evaluator, MatchEquityTable.Default,
                                                             modelDistribution, CubeAdvisorOptions.Default);

                    sb.Append(",\n  \"modelPath\": ").Append(JsonString(modelPath));
                    sb.Append(",\n  \"modelScenarios\": [");

                    modelCorrect = 0;
                    int mi = 0;
                    foreach (var s in scenarios)
                    {
                        CubeDecision d = DecideCrawford(modelAdvisor, s.MatchLength, s.White, s.Black,
                                                        s.Crawford, s.CrawfordPlayed, s.CubeValue,
                                                        s.CubeOwner, s.Turn);
                        bool ok = d.ShouldDouble == s.ExpectDouble && d.ShouldTake == s.ExpectTake;
                        if (ok)
                        {
                            modelCorrect++;
                        }

                        sb.Append(mi == 0 ? "\n" : ",\n");
                        sb.Append("    {\"name\": ").Append(JsonString(s.Name));
                        sb.Append(", \"shouldDouble\": ").Append(d.ShouldDouble ? "true" : "false");
                        sb.Append(", \"shouldTake\": ").Append(d.ShouldTake ? "true" : "false");
                        sb.Append(", \"correct\": ").Append(ok ? "true" : "false");
                        sb.Append('}');
                        mi++;
                    }

                    sb.Append("\n  ],\n  \"modelCorrect\": ").Append(modelCorrect);
                }
            }

            sb.Append("\n}\n");

            if (outPath != null)
            {
                WriteText(outPath, sb.ToString());
            }

            Console.WriteLine("crawford: " + correct + "/" + index + " dogru.");
            if (modelCorrect >= 0)
            {
                Console.WriteLine("crawford (model): " + modelCorrect + "/" + index + " dogru.");
            }

            return correct == index ? 0 : 1;
        }

        private static CubeDecision DecideCrawford(EquityCubeAdvisor advisor, int matchLength, int white,
                                                   int black, bool crawford, bool crawfordPlayed,
                                                   int cubeValue, sbyte cubeOwner, sbyte turn)
        {
            var state = new BackgammonState();
            state.Reset();
            state.matchLength = matchLength;
            state.whiteScore = white;
            state.blackScore = black;
            state.isCrawfordGame = crawford;
            state.crawfordPlayed = crawfordPlayed;
            state.cubeValue = (byte)cubeValue;
            state.cubeOwner = cubeOwner;
            state.turn = turn;
            state.phase = GamePhase.PreRoll;
            state.hash = BackgammonEngine.ComputeZobristHash(state);

            return advisor.Decide(state, turn);
        }

        private sealed class ConstantEvaluator : IPolicyValueEvaluator
        {
            private readonly float _equity;

            public ConstantEvaluator(float equity)
            {
                _equity = equity;
            }

            public int Version
            {
                get { return 1; }
            }

            public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                      in VectorizerScalars scalars, Span<float> results)
            {
                float value = perspective > 0 ? _equity : -_equity;
                for (int i = 0; i < count; i++)
                {
                    results[offset + i] = value;
                }
            }

            public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> priorities)
            {
                for (int i = 0; i < count; i++)
                {
                    priorities[offset + i] = 0f;
                }
            }
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static string DefaultModelPath()
        {
            // Faz 6: Aşama D'nin en iyi modeli (VAL-ER ile secilmis). Yoksa Faz 5 modeli.
            string stageD = Path.Combine("ml", "runs", "stage_d_l2", "onnx", "model_v15.onnx");
            if (File.Exists(stageD))
            {
                return stageD;
            }

            // Egitilmis model; `ml/artifacts/model_v2.onnx` yalnizca test fiksturudur.
            string trained = Path.Combine("ml", "runs", "stage_d", "onnx", "model_v5.onnx");
            if (File.Exists(trained))
            {
                return trained;
            }

            // F7-30: fikstur modeli egitilmemistir; sessizce kullanmak yanlis olcume yol acar.
            string fixture = Path.Combine("ml", "artifacts", "model_v2.onnx");
            Console.Error.WriteLine(
                "UYARI: egitilmis model bulunamadi; test fiksturu kullaniliyor: " + fixture);
            Console.Error.WriteLine(
                "UYARI: bu modelin gucu olculmemistir, sonuclar olcum olarak kullanilamaz (F7-30).");
            return fixture;
        }

        private static string Num(double value)
        {
            return value.ToString("R", CultureInfo.InvariantCulture);
        }

        private static string JsonString(string value)
        {
            if (value == null)
            {
                return "null";
            }

            var sb = new StringBuilder(value.Length + 2);
            sb.Append('"');
            foreach (char c in value)
            {
                switch (c)
                {
                    case '"':
                        sb.Append("\\\"");
                        break;
                    case '\\':
                        sb.Append("\\\\");
                        break;
                    case '\n':
                        sb.Append("\\n");
                        break;
                    case '\r':
                        sb.Append("\\r");
                        break;
                    case '\t':
                        sb.Append("\\t");
                        break;
                    default:
                        sb.Append(c);
                        break;
                }
            }

            sb.Append('"');
            return sb.ToString();
        }

        private static void WriteText(string path, string text)
        {
            string dir = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            File.WriteAllText(path, text, new UTF8Encoding(false));
        }
    }
}
