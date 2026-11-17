using System;
using System.Collections.Generic;
using Backgammon.Core;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 9: taban oyunculara karsi degerlendirme.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Protokol: sabit seed, <c>argmax</c>, her seed icin renkler degistirilerek iki oyun.
    /// Sonuc: oyun basina ortalama puan ± standart hata.
    /// </para>
    /// <para>
    /// Taban oyuncular: <see cref="OpponentKind.Random"/> (rastgele yasal hamle),
    /// <see cref="OpponentKind.Pip"/> (afterstate'i <c>rakipPip - kendiPip</c> degerini
    /// maksimize edecek sekilde secen sezgisel) ve <see cref="OpponentKind.Model"/>
    /// (baska bir ONNX modeli, ornegin onceki checkpoint veya havuz uyesi).
    /// </para>
    /// </remarks>
    public static class EvalBench
    {
        /// <summary>Rakip turu.</summary>
        public enum OpponentKind
        {
            /// <summary>Rastgele yasal hamle.</summary>
            Random = 0,

            /// <summary>Pip farki sezgiseli.</summary>
            Pip = 1,

            /// <summary>Baska bir ONNX modeli (argmax).</summary>
            Model = 2,
        }

        /// <summary>Degerlendirme sonucu.</summary>
        public struct Report
        {
            /// <summary>Oynanan oyun sayisi.</summary>
            public int Games;

            /// <summary>Ogrenenin kazandigi oyun sayisi.</summary>
            public int Wins;

            /// <summary>Ogrenenin kaybettigi oyun sayisi.</summary>
            public int Losses;

            /// <summary>Berabere/aborted oyun sayisi.</summary>
            public int Draws;

            /// <summary>Ogrenen perspektifinden oyun basina ortalama puan.</summary>
            public double MeanPoints;

            /// <summary>Ortalamanin standart hatasi.</summary>
            public double StandardError;

            /// <summary>Ortalamanin %95 guven araliginin alt siniri.</summary>
            public double LowerConfidenceBound
            {
                get { return MeanPoints - 1.96 * StandardError; }
            }

            /// <summary>Ortalamanin %95 guven araliginin ust siniri.</summary>
            public double UpperConfidenceBound
            {
                get { return MeanPoints + 1.96 * StandardError; }
            }

            /// <summary>Kazanma orani (Wins / Games).</summary>
            public double WinRate
            {
                get { return Games > 0 ? (double)Wins / Games : 0.0; }
            }

            /// <summary>Rakip adi (rapor icin).</summary>
            public string OpponentName;
        }

        /// <summary>
        /// Ogrenen ajani <c>RandomBot</c>'a karsi oynatir.
        /// </summary>
        public static Report RunVsRandom(SelfPlayConfig cfg, SelfPlayAgent learner, int games, ulong seed)
        {
            return Run(cfg, learner, OpponentKind.Random, null, games, seed);
        }

        /// <summary>
        /// Ogrenen ajani verilen rakibe karsi oynatir.
        /// </summary>
        /// <param name="cfg">Yapilandirma (dogrulanmis olmali).</param>
        /// <param name="learner">Ogrenen ajan (argmax ile oynar).</param>
        /// <param name="kind">Rakip turu.</param>
        /// <param name="opponent">
        /// <see cref="OpponentKind.Model"/> icin rakip ajan; diger turlerde yok sayilir.
        /// </param>
        /// <param name="games">Oyun sayisi; cift sayi onerilir (renkler dengeli).</param>
        /// <param name="seed">Taban tohum.</param>
        public static Report Run(
            SelfPlayConfig cfg,
            SelfPlayAgent learner,
            OpponentKind kind,
            SelfPlayAgent? opponent,
            int games,
            ulong seed)
        {
            if (cfg == null)
            {
                throw new ArgumentNullException(nameof(cfg));
            }

            if (learner == null)
            {
                throw new ArgumentNullException(nameof(learner));
            }

            if (games <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(games));
            }

            if (kind == OpponentKind.Model && opponent == null)
            {
                throw new ArgumentNullException(nameof(opponent), "Model rakibi icin ajan gerekli.");
            }

            var report = new Report { Games = games, OpponentName = NameOf(kind) };
            var points = new double[games];

            var state = new BackgammonState();
            var moves = new MoveList();
            var afterStates = new AfterStateList();
            var scratch = new BackgammonState();
            EngineSettings es = EngineSettings.Default;

            for (int g = 0; g < games; g++)
            {
                ulong gameSeed = seed + (ulong)g * 0x9E3779B97F4A7C15UL;
                var rng = new Xoshiro256StarStar(gameSeed);
                sbyte learnerSide = (g % 2 == 0) ? (sbyte)1 : (sbyte)-1;

                BackgammonEngine.NewGame(state, MatchSettings.MoneyGame);
                BackgammonEngine.RollOpening(state, rng);

                int ply = 0;
                bool aborted = false;

                while (true)
                {
                    if (ply >= cfg.MaxPlies)
                    {
                        aborted = true;
                        break;
                    }

                    sbyte mover = state.turn;
                    bool learnerTurn = mover == learnerSide;

                    if (learnerTurn)
                    {
                        SearchResult sr = BackgammonSearch.Search(
                            state, learner.Settings, es, learner.Workspace, learner.Evaluator, learner.Evaluator);

                        if (sr.IsPass)
                        {
                            BackgammonEngine.PassTurn(state);
                        }
                        else
                        {
                            MoveSequence best = ArgMaxSequence(sr);
                            BackgammonEngine.ApplyMove(state, best);
                            if (state.phase == GamePhase.GameOver)
                            {
                                break;
                            }

                            BackgammonEngine.EndTurn(state, es);
                        }
                    }
                    else
                    {
                        switch (kind)
                        {
                            case OpponentKind.Random:
                                PlayRandom(state, moves, rng, es);
                                break;
                            case OpponentKind.Pip:
                                PlayPip(state, afterStates, scratch, es);
                                break;
                            case OpponentKind.Model:
                                PlayModel(state, opponent!, es);
                                break;
                            default:
                                throw new ArgumentOutOfRangeException(nameof(kind));
                        }

                        if (state.phase == GamePhase.GameOver)
                        {
                            break;
                        }
                    }

                    ply++;
                    BackgammonEngine.RollDice(state, rng);
                }

                if (aborted)
                {
                    report.Draws++;
                    points[g] = 0.0;
                    continue;
                }

                GameResult result;
                if (!BackgammonEngine.IsGameOver(state, es, out result))
                {
                    report.Draws++;
                    points[g] = 0.0;
                    continue;
                }

                double p = result.Winner == learnerSide ? result.Points : -result.Points;
                points[g] = p;

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
            }

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

            report.MeanPoints = mean;
            report.StandardError = games > 1 ? Math.Sqrt(var / (games - 1) / games) : 0.0;
            return report;
        }

        /// <summary>Rakip turunun rapor adi.</summary>
        public static string NameOf(OpponentKind kind)
        {
            switch (kind)
            {
                case OpponentKind.Random:
                    return "RandomBot";
                case OpponentKind.Pip:
                    return "PipBot";
                case OpponentKind.Model:
                    return "Model";
                default:
                    return "?";
            }
        }

        private static void PlayRandom(BackgammonState state, MoveList moves, Xoshiro256StarStar rng, in EngineSettings es)
        {
            moves.Clear();
            LegalMoveGenerator.GenerateAllLegalMoves(state, moves);

            if (moves.Count == 0)
            {
                BackgammonEngine.PassTurn(state);
                return;
            }

            int pick = (int)(rng.NextUInt() % (uint)moves.Count);
            BackgammonEngine.ApplyMove(state, moves[pick]);

            if (state.phase != GamePhase.GameOver)
            {
                BackgammonEngine.EndTurn(state, es);
            }
        }

        /// <summary>
        /// PipBot: afterstate'i <c>rakipPip - kendiPip</c> degerini maksimize edecek sekilde secer.
        /// Terminal afterstate (tum pullar toplanmis) en yuksek onceligi alir.
        /// </summary>
        private static void PlayPip(
            BackgammonState state,
            AfterStateList afterStates,
            BackgammonState scratch,
            in EngineSettings es)
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

            MoveSequence seq = afterStates.Sequences[bestIndex];
            BackgammonEngine.ApplyMove(state, seq);

            if (state.phase != GamePhase.GameOver)
            {
                BackgammonEngine.EndTurn(state, es);
            }
        }

        private static void PlayModel(BackgammonState state, SelfPlayAgent opponent, in EngineSettings es)
        {
            SearchResult sr = BackgammonSearch.Search(
                state, opponent.Settings, es, opponent.Workspace, opponent.Evaluator, opponent.Evaluator);

            if (sr.IsPass)
            {
                BackgammonEngine.PassTurn(state);
                return;
            }

            MoveSequence best = ArgMaxSequence(sr);
            BackgammonEngine.ApplyMove(state, best);

            if (state.phase != GamePhase.GameOver)
            {
                BackgammonEngine.EndTurn(state, es);
            }
        }

        private static MoveSequence ArgMaxSequence(in SearchResult sr)
        {
            int bestIndex = -1;
            float bestScore = float.NegativeInfinity;

            for (int k = 0; k < sr.CandidateCount; k++)
            {
                RootCandidate c = sr.RootCandidates[k];
                if (c.Kind > 1)
                {
                    continue;
                }

                if (c.Score > bestScore)
                {
                    bestScore = c.Score;
                    bestIndex = k;
                }
            }

            if (bestIndex < 0)
            {
                return default;
            }

            return sr.RootCandidates[bestIndex].Sequence;
        }
    }
}