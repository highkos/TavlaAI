using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Threading.Tasks;
using Backgammon.Core;
using Backgammon.Inference;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.1: self-play surucusu (konsol uygulamasi).
    /// </summary>
    /// <remarks>
    /// <para>
    /// Kullanim: <c>Backgammon.SelfPlay --config cfg.json</c> veya tek tek bayraklar
    /// (<c>--model</c>, <c>--games</c>, <c>--seed</c>, <c>--threads</c>, <c>--out</c>, ...).
    /// </para>
    /// <para>
    /// <b>Determinizm (Faz 6 Bolum 7.2):</b> her oyunun tohumu
    /// <c>seed(gameIndex) = baseSeed + gameIndex</c> ile <b>is parcacigindan bagimsiz</b>
    /// turetilir. Bu yuzden <c>--threads N</c> ciktisi, N ayri <c>--threads 1</c> kosusunun
    /// kumesiyle aynidir (Test 60). Havuz oyunu karari da oyun tohumundan turetilir.
    /// </para>
    /// </remarks>
    public static class Program
    {
        private const ulong ScheduleSeedSalt = 0x9E3779B97F4A7C15UL;

        /// <summary>Giris noktasi.</summary>
        public static int Main(string[] args)
        {
            SelfPlayConfig? config;
            try
            {
                config = CommandLine.Parse(args);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Arguman hatasi: " + ex.Message);
                CommandLine.PrintUsage();
                return 2;
            }

            if (config == null)
            {
                CommandLine.PrintUsage();
                return 0;
            }

            try
            {
                config.Validate();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Yapilandirma hatasi: " + ex.Message);
                return 2;
            }

            try
            {
                return Run(config);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Self-play hatasi: " + ex);
                return 1;
            }
        }

        private static int Run(SelfPlayConfig config)
        {
            OnnxEvaluatorOptions options = config.ToEvaluatorOptions();
            SearchSettings settings = config.ToSearchSettings();

            using OnnxModelHandle learnerModel = OnnxModelHandle.Load(config.ModelPath!, options);
            using OnnxModelHandle? poolModel = string.IsNullOrEmpty(config.PoolModelPath)
                ? null
                : OnnxModelHandle.Load(config.PoolModelPath!, options);

            if (config.PoolFraction > 0f && poolModel == null)
            {
                throw new InvalidOperationException("PoolFraction > 0 fakat havuz modeli yuklenemedi.");
            }

            if (config.EvalRandomGames > 0 || config.EvalPipGames > 0 || config.EvalModelGames > 0)
            {
                using var evalAgent = new SelfPlayAgent(learnerModel, options, settings);
                return RunEval(config, evalAgent, options, settings);
            }

            Directory.CreateDirectory(config.OutputDir);

            int games = config.Games;
            int threads = Math.Max(1, Math.Min(config.Threads, Math.Max(1, games)));
            var results = new ShardGame[games];

            var stopwatch = Stopwatch.StartNew();

            if (threads == 1)
            {
                using var learner = new SelfPlayAgent(learnerModel, options, settings);
                using SelfPlayAgent? pool = poolModel == null ? null : new SelfPlayAgent(poolModel, options, settings);
                using var runner = new SelfPlayRunner(config, learner, pool, config.Seed);

                for (int i = 0; i < games; i++)
                {
                    results[i] = PlayOne(runner, config, (ulong)(i + 1));
                }
            }
            else
            {
                var exceptions = new List<Exception>();
                Parallel.For(0, threads, threadIndex =>
                {
                    try
                    {
                        using var learner = new SelfPlayAgent(learnerModel, options, settings);
                        using SelfPlayAgent? pool = poolModel == null ? null : new SelfPlayAgent(poolModel, options, settings);
                        using var runner = new SelfPlayRunner(config, learner, pool, config.Seed);

                        for (int i = threadIndex; i < games; i += threads)
                        {
                            results[i] = PlayOne(runner, config, (ulong)(i + 1));
                        }
                    }
                    catch (Exception ex)
                    {
                        lock (exceptions)
                        {
                            exceptions.Add(ex);
                        }
                    }
                });

                if (exceptions.Count > 0)
                {
                    throw new AggregateException("Is parcaciklarindan hata geldi.", exceptions);
                }
            }

            stopwatch.Stop();

            var gamesList = new List<ShardGame>(games);
            for (int i = 0; i < games; i++)
            {
                if (results[i] != null)
                {
                    gamesList.Add(results[i]);
                }
            }

            // Faz 6 Bolum 7.5: tekrar ayiklama, tum oyunlar toplandiktan sonra tek gecisde.
            DupCapStats dupCap = DupCapFilter.Apply(gamesList, config.DupCap);

            long bytes = WriteShards(config, gamesList, learnerModel.ModelVersion);

            Report(config, gamesList, bytes, stopwatch.Elapsed, dupCap);
            return 0;
        }
        /// <summary>
        /// Tek bir oyunu, oyun kimliginden turetilen tohumla oynar (Faz 6 Bolum 7.2).
        /// </summary>
        private static ShardGame PlayOne(SelfPlayRunner runner, SelfPlayConfig config, ulong gameId)
        {
            ulong gameSeed = config.Seed + gameId;
            runner.ResetSeed(gameSeed);

            bool poolGame = false;
            sbyte learnerSide = 0;

            if (config.PoolFraction > 0f)
            {
                // Havuz karari ayri bir RNG'den alinir; oyun RNG akisini etkilemez.
                var schedule = new Xoshiro256StarStar(gameSeed ^ ScheduleSeedSalt);
                double draw = (schedule.NextUInt() >> 8) * (1.0 / 16777216.0);
                if (draw < config.PoolFraction)
                {
                    poolGame = true;
                    learnerSide = (schedule.NextUInt() & 1u) == 0u ? (sbyte)1 : (sbyte)-1;
                }
            }

            return runner.PlayGame(gameId, poolGame, learnerSide);
        }

        private static int RunEval(
            SelfPlayConfig config,
            SelfPlayAgent agent,
            OnnxEvaluatorOptions options,
            SearchSettings settings)
        {
            Console.WriteLine("=== Backgammon.SelfPlay — taban oyuncu degerlendirmesi (Faz 4 v3 Bolum 9) ===");
            Console.WriteLine("model            : " + config.ModelPath);
            Console.WriteLine("seed             : " + config.Seed);
            Console.WriteLine("depth / maxInner : " + config.DepthPly + " / " + config.MaxCandidatesInner);

            int exitCode = 0;
            var reports = new List<EvalBench.Report>();

            if (config.EvalRandomGames > 0)
            {
                exitCode |= RunOne(config, agent, EvalBench.OpponentKind.Random, null, config.EvalRandomGames, reports);
            }

            if (config.EvalPipGames > 0)
            {
                exitCode |= RunOne(config, agent, EvalBench.OpponentKind.Pip, null, config.EvalPipGames, reports);
            }

            if (config.EvalModelGames > 0)
            {
                using OnnxModelHandle opponentModel = OnnxModelHandle.Load(config.EvalModelPath!, options);
                using var opponent = new SelfPlayAgent(opponentModel, options, settings);
                exitCode |= RunOne(config, agent, EvalBench.OpponentKind.Model, opponent, config.EvalModelGames, reports);
            }

            if (!string.IsNullOrEmpty(config.EvalJsonPath))
            {
                WriteEvalJson(config, reports);
            }

            return exitCode;
        }

        private static void WriteEvalJson(SelfPlayConfig config, List<EvalBench.Report> reports)
        {
            string? dir = Path.GetDirectoryName(Path.GetFullPath(config.EvalJsonPath!));
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            var sb = new System.Text.StringBuilder();
            sb.Append("{\n");
            sb.Append("  \"model\": ");
            sb.Append(JsonString(config.ModelPath));
            sb.Append(",\n  \"seed\": ");
            sb.Append(config.Seed.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\n  \"depthPly\": ");
            sb.Append(config.DepthPly.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\n  \"maxCandidatesRoot\": ");
            sb.Append(config.MaxCandidatesRoot.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\n  \"maxCandidatesInner\": ");
            sb.Append(config.MaxCandidatesInner.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\n  \"reports\": [");

            for (int i = 0; i < reports.Count; i++)
            {
                EvalBench.Report r = reports[i];
                sb.Append(i == 0 ? "\n" : ",\n");
                sb.Append("    {\"opponent\": ");
                sb.Append(JsonString(r.OpponentName));
                sb.Append(", \"games\": ");
                sb.Append(r.Games.ToString(CultureInfo.InvariantCulture));
                sb.Append(", \"wins\": ");
                sb.Append(r.Wins.ToString(CultureInfo.InvariantCulture));
                sb.Append(", \"losses\": ");
                sb.Append(r.Losses.ToString(CultureInfo.InvariantCulture));
                sb.Append(", \"draws\": ");
                sb.Append(r.Draws.ToString(CultureInfo.InvariantCulture));
                sb.Append(", \"winRate\": ");
                sb.Append(r.WinRate.ToString("R", CultureInfo.InvariantCulture));
                sb.Append(", \"meanPoints\": ");
                sb.Append(r.MeanPoints.ToString("R", CultureInfo.InvariantCulture));
                sb.Append(", \"standardError\": ");
                sb.Append(r.StandardError.ToString("R", CultureInfo.InvariantCulture));
                sb.Append(", \"lowerConfidenceBound\": ");
                sb.Append(r.LowerConfidenceBound.ToString("R", CultureInfo.InvariantCulture));
                sb.Append(", \"upperConfidenceBound\": ");
                sb.Append(r.UpperConfidenceBound.ToString("R", CultureInfo.InvariantCulture));
                sb.Append('}');
            }

            sb.Append("\n  ]\n}\n");
            File.WriteAllText(config.EvalJsonPath!, sb.ToString(), new System.Text.UTF8Encoding(false));
        }

        private static string JsonString(string? value)
        {
            if (value == null)
            {
                return "null";
            }

            var sb = new System.Text.StringBuilder(value.Length + 2);
            sb.Append('"');
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
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
                        if (c < ' ')
                        {
                            sb.Append("\\u");
                            sb.Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            sb.Append(c);
                        }

                        break;
                }
            }

            sb.Append('"');
            return sb.ToString();
        }

        private static int RunOne(
            SelfPlayConfig config,
            SelfPlayAgent agent,
            EvalBench.OpponentKind kind,
            SelfPlayAgent? opponent,
            int games,
            List<EvalBench.Report> reports)
        {
            string name = kind == EvalBench.OpponentKind.Model
                ? "Model (" + Path.GetFileName(config.EvalModelPath) + ")"
                : EvalBench.NameOf(kind);

            Console.WriteLine();
            Console.WriteLine("--- rakip: " + name + " ---");
            Console.WriteLine("games            : " + games);

            var stopwatch = Stopwatch.StartNew();
            EvalBench.Report report = EvalBench.Run(config, agent, kind, opponent, games, config.Seed);
            stopwatch.Stop();
            reports.Add(report);

            Console.WriteLine("wins / losses    : " + report.Wins + " / " + report.Losses +
                              " (draws " + report.Draws + ")");
            Console.WriteLine("win rate         : " +
                              (report.WinRate * 100.0).ToString("F2", CultureInfo.InvariantCulture) + " %");
            Console.WriteLine("mean points      : " +
                              report.MeanPoints.ToString("F4", CultureInfo.InvariantCulture) + " +/- " +
                              report.StandardError.ToString("F4", CultureInfo.InvariantCulture));
            Console.WriteLine("95% CI           : [" +
                              report.LowerConfidenceBound.ToString("F4", CultureInfo.InvariantCulture) + ", " +
                              report.UpperConfidenceBound.ToString("F4", CultureInfo.InvariantCulture) + "]");
            Console.WriteLine("elapsed          : " +
                              stopwatch.Elapsed.TotalSeconds.ToString("F2", CultureInfo.InvariantCulture) + " s");
            return 0;
        }

        private static long WriteShards(SelfPlayConfig config, List<ShardGame> games, uint modelVersion)
        {
            ShardHeader header = ShardHeader.Create(
                (uint)BackgammonVectorizer.FeatureVersion,
                modelVersion,
                (uint)config.LogTopCandidates);

            string extension = config.Gzip ? ShardConstants.GzipExtension : ShardConstants.Extension;
            int perShard = config.GamesPerShard > 0 ? config.GamesPerShard : Math.Max(1, games.Count);
            long totalBytes = 0;
            int shardIndex = 0;

            for (int start = 0; start < games.Count; start += perShard)
            {
                int count = Math.Min(perShard, games.Count - start);
                var slice = new List<ShardGame>(count);
                for (int i = 0; i < count; i++)
                {
                    slice.Add(games[start + i]);
                }

                string path = Path.Combine(
                    config.OutputDir,
                    config.ShardPrefix + "_" + shardIndex.ToString("D4", CultureInfo.InvariantCulture) + extension);

                ShardWriter.WriteFile(path, header, slice, config.Gzip);
                totalBytes += new FileInfo(path).Length;
                shardIndex++;
            }

            return totalBytes;
        }

        private static void Report(SelfPlayConfig config, List<ShardGame> games, long bytes, TimeSpan elapsed,
                                  DupCapStats dupCap)
        {
            int aborted = 0;
            int poolGames = 0;
            long decisions = 0;
            long learnerDecisions = 0;
            long loggedCandidates = 0;
            long passes = 0;

            for (int i = 0; i < games.Count; i++)
            {
                ShardGame game = games[i];
                if (game.IsAborted)
                {
                    aborted++;
                }

                if (game.LearnerSide != 0)
                {
                    poolGames++;
                }

                for (int d = 0; d < game.Decisions.Count; d++)
                {
                    ShardDecision decision = game.Decisions[d];
                    decisions++;
                    if (decision.IsLearner)
                    {
                        learnerDecisions++;
                    }

                    if (decision.IsPass)
                    {
                        passes++;
                    }

                    loggedCandidates += decision.LoggedCount;
                }
            }

            double seconds = elapsed.TotalSeconds;
            double gamesPerSecond = seconds > 0.0 ? games.Count / seconds : 0.0;
            double bytesPerGame = games.Count > 0 ? (double)bytes / games.Count : 0.0;

            Console.WriteLine("=== Backgammon.SelfPlay (Faz 4 v3 Bolum 5) ===");
            Console.WriteLine("model            : " + config.ModelPath);
            Console.WriteLine("pool model       : " + (string.IsNullOrEmpty(config.PoolModelPath) ? "(yok)" : config.PoolModelPath));
            Console.WriteLine("seed / threads   : " + config.Seed + " / " + config.Threads);
            Console.WriteLine("depth / maxInner : " + config.DepthPly + " / " + config.MaxCandidatesInner);
            Console.WriteLine("distill mode     : " + (config.DistillMode ? "acik (DEC_DISTILLED=16)" : "kapali"));
            Console.WriteLine("logTopCandidates : " + config.LogTopCandidates);
            Console.WriteLine("exploration      : " + config.ExplorationPlies + " ply @ T=" +
                              config.SelectionTemperature.ToString("G6", CultureInfo.InvariantCulture));
            Console.WriteLine("games            : " + games.Count + " (aborted " + aborted + ", pool " + poolGames + ")");
            Console.WriteLine("decisions        : " + decisions + " (learner " + learnerDecisions + ", pass " + passes + ")");
            Console.WriteLine("logged candidates: " + loggedCandidates);
            Console.WriteLine("dup_cap          : " + (dupCap.Cap == 0
                ? "kapali"
                : "cap=" + dupCap.Cap + " (elenen " + dupCap.Capped + ", tutulan " + dupCap.Kept +
                  ", acilis muaf " + dupCap.OpeningExempt + ", farkli " + dupCap.DistinctKeys + ")"));
            Console.WriteLine("shard bytes      : " + bytes + " (" +
                              bytesPerGame.ToString("F1", CultureInfo.InvariantCulture) + " B/oyun)");
            Console.WriteLine("elapsed          : " + seconds.ToString("F2", CultureInfo.InvariantCulture) + " s (" +
                              gamesPerSecond.ToString("F2", CultureInfo.InvariantCulture) + " oyun/s)");
            Console.WriteLine("disk write rate  : " +
                              (seconds > 0.0 ? (bytes / seconds / (1024.0 * 1024.0)) : 0.0)
                                  .ToString("F2", CultureInfo.InvariantCulture) + " MB/s");
            Console.WriteLine("peak memory      : " +
                              (Process.GetCurrentProcess().PeakWorkingSet64 / (1024L * 1024L)) + " MB");
        }
    }
}