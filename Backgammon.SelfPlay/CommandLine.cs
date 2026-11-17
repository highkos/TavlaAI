using System;
using System.Collections.Generic;
using System.Globalization;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.1: komut satiri ayristiricisi.
    /// </summary>
    /// <remarks>
    /// Iki kullanim bicimi desteklenir: <c>--config cfg.json</c> (JSON yapilandirma) ve tek tek
    /// bayraklar. Bayraklar JSON'un uzerine yazar. <c>--help</c> yalnizca kullanimi yazdirir.
    /// </remarks>
    public static class CommandLine
    {
        /// <summary>Argumanlari yapilandirmaya cevirir; <c>--help</c> ise <c>null</c> doner.</summary>
        public static SelfPlayConfig? Parse(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return null;
            }

            SelfPlayConfig? config = null;
            var overrides = new List<KeyValuePair<string, string>>();

            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                if (arg == "--help" || arg == "-h" || arg == "/?")
                {
                    return null;
                }

                if (arg == "--config")
                {
                    config = SelfPlayConfig.Load(RequireValue(args, ref i, arg));
                    continue;
                }

                if (!arg.StartsWith("--", StringComparison.Ordinal))
                {
                    throw new ArgumentException("Bilinmeyen arguman: " + arg);
                }

                string name = arg.Substring(2);
                string value = "true";
                int equals = name.IndexOf('=');
                if (equals >= 0)
                {
                    value = name.Substring(equals + 1);
                    name = name.Substring(0, equals);
                }
                else if (i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal))
                {
                    value = args[++i];
                }

                overrides.Add(new KeyValuePair<string, string>(name, value));
            }

            config = config ?? new SelfPlayConfig();

            for (int i = 0; i < overrides.Count; i++)
            {
                Apply(config, overrides[i].Key, overrides[i].Value);
            }

            return config;
        }

        private static string RequireValue(string[] args, ref int index, string name)
        {
            if (index + 1 >= args.Length)
            {
                throw new ArgumentException(name + " icin deger gerekli.");
            }

            return args[++index];
        }

        private static void Apply(SelfPlayConfig config, string name, string value)
        {
            switch (name.ToLowerInvariant())
            {
                case "model":
                    config.ModelPath = value;
                    break;
                case "pool-model":
                    config.PoolModelPath = value;
                    break;
                case "games":
                    config.Games = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "seed":
                    config.Seed = ulong.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "threads":
                    config.Threads = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "out":
                    config.OutputDir = value;
                    break;
                case "prefix":
                    config.ShardPrefix = value;
                    break;
                case "depth":
                    config.DepthPly = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "max-root":
                    config.MaxCandidatesRoot = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "max-inner":
                    config.MaxCandidatesInner = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "log-top":
                    config.LogTopCandidates = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "exploration":
                    config.ExplorationPlies = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "sel-temp":
                    config.SelectionTemperature = float.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "policy-temp":
                    config.PolicyTemperature = float.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "max-plies":
                    config.MaxPlies = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "games-per-shard":
                    config.GamesPerShard = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "pool-fraction":
                    config.PoolFraction = float.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "max-batch":
                    config.MaxBatch = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "intra-op":
                    config.IntraOpThreads = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "dup-cap":
                    config.DupCap = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "distill":
                    config.DistillMode = ParseBool(value);
                    break;
                case "gzip":
                    config.Gzip = ParseBool(value);
                    break;
                case "cuda":
                    config.UseCuda = ParseBool(value);
                    break;
                case "eval-random":
                    config.EvalRandomGames = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "eval-pip":
                    config.EvalPipGames = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "eval-model":
                    config.EvalModelGames = int.Parse(value, CultureInfo.InvariantCulture);
                    break;
                case "eval-model-path":
                    config.EvalModelPath = value;
                    break;
                case "eval-json":
                    config.EvalJsonPath = value;
                    break;
                default:
                    throw new ArgumentException("Bilinmeyen secenek: --" + name);
            }
        }

        private static bool ParseBool(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return true;
            }

            switch (value.ToLowerInvariant())
            {
                case "1":
                case "true":
                case "yes":
                case "on":
                    return true;
                case "0":
                case "false":
                case "no":
                case "off":
                    return false;
                default:
                    throw new ArgumentException("Gecersiz mantiksal deger: " + value);
            }
        }

        /// <summary>Kullanim metnini yazar.</summary>
        public static void PrintUsage()
        {
            Console.WriteLine("Kullanim:");
            Console.WriteLine("  Backgammon.SelfPlay --config <cfg.json> [secenekler]");
            Console.WriteLine("  Backgammon.SelfPlay --model <model.onnx> --games N --seed S --threads T --out DIR");
            Console.WriteLine();
            Console.WriteLine("Secenekler:");
            Console.WriteLine("  --model <path>          Ogrenen ONNX modeli (zorunlu)");
            Console.WriteLine("  --pool-model <path>     Havuz rakip modeli");
            Console.WriteLine("  --pool-fraction <f>     Havuz rakipli oyun orani (0..1)");
            Console.WriteLine("  --games <n>             Oyun sayisi (varsayilan 100)");
            Console.WriteLine("  --seed <u64>            RNG tohumu (varsayilan 1)");
            Console.WriteLine("  --threads <n>           Is parcacigi sayisi (varsayilan 1)");
            Console.WriteLine("  --out <dir>             Cikis klasoru");
            Console.WriteLine("  --prefix <name>         Shard dosya oneki (varsayilan selfplay)");
            Console.WriteLine("  --depth <n>             DepthPly (varsayilan 1)");
            Console.WriteLine("  --max-root <n>          MaxCandidatesRoot (varsayilan 0)");
            Console.WriteLine("  --max-inner <n>         MaxCandidatesInner (varsayilan 0)");
            Console.WriteLine("  --log-top <n>           logTopCandidates (varsayilan 12, 0 = tumu)");
            Console.WriteLine("  --exploration <n>       Kesif karar sayisi (varsayilan 10)");
            Console.WriteLine("  --sel-temp <f>          Kesif sicakligi (varsayilan 0.05)");
            Console.WriteLine("  --policy-temp <f>       C# politika hedefi sicakligi (varsayilan 1.0)");
            Console.WriteLine("  --max-plies <n>         Oyun basina en fazla karar (varsayilan 500)");
            Console.WriteLine("  --games-per-shard <n>   Shard basina oyun (0 = tek shard)");
            Console.WriteLine("  --max-batch <n>         ONNX MaxBatch (varsayilan 2048)");
            Console.WriteLine("  --intra-op <n>          ONNX intra-op is parcacigi (varsayilan 1)");
            Console.WriteLine("  --dup-cap <n>           Ayni afterstate en fazla n kez egitilir (varsayilan 3, 0 = kapali)");
            Console.WriteLine("  --distill               Damitma modu: DEC_DISTILLED=16, DepthPly > 1 serbest (Faz 7 §5.4)");
            Console.WriteLine("  --gzip                  Shard'lari gzip'le");
            Console.WriteLine("  --cuda                  CUDA execution provider kullan");
            Console.WriteLine("  --eval-random <n>       Self-play yerine RandomBot'a karsi n oyun oyna");
            Console.WriteLine("  --eval-pip <n>          Self-play yerine PipBot'a karsi n oyun oyna");
            Console.WriteLine("  --eval-model <n>        Self-play yerine baska bir modele karsi n oyun oyna");
            Console.WriteLine("  --eval-model-path <p>   --eval-model icin rakip ONNX modeli");
            Console.WriteLine("  --eval-json <path>      Degerlendirme raporunu JSON olarak yaz");
        }
    }
}