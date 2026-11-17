using System;
using Backgammon.Core;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5: tek is parcacigi icin self-play oyun dongusu ve karar kaydi uretimi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Oyun dongusu (Bolum 5.1):</b> yalnizca Faz 1/3 API'leri kullanilir:
    /// <c>NewGame</c> → <c>RollOpening</c> → her turda <c>RollDice</c> → <c>Search</c> →
    /// hamle secimi → <c>ApplyMove</c> → <c>IsGameOver</c>/<c>EndTurn</c> (yasal hamle yoksa
    /// <c>PassTurn</c>). <c>max_plies</c> asilirsa oyun <c>aborted</c> isaretlenir.
    /// </para>
    /// <para>
    /// <b>Karar basina veri (Bolum 5.2):</b> her aday icin durum bir scratch state'e kopyalanir,
    /// <c>ApplyMove(candidate.Sequence)</c> uygulanir (<b><c>EndTurn</c> CAGRILMAZ</b>) ve
    /// <c>Vectorize(scratch, mover, buffer)</c> cagrilir. Terminal adaylar vektorlestirilmez.
    /// </para>
    /// <para>
    /// <b>Hamle secimi (Bolum 5.3):</b> ilk <c>ExplorationPlies</c> kararda
    /// <c>softmax(Q / selectionTemperature)</c> dagilimindan ornekleme, sonrasinda <c>argmax(Q)</c>.
    /// Her ikisi de yalnizca <c>Kind ∈ {0,1}</c> adaylar uzerinde calisir.
    /// </para>
    /// <para>
    /// <b>Loglanan adaylar (Bolum 5.4):</b> yalnizca <c>Kind == 1</c> adaylar, <c>Q</c>'ya gore
    /// azalan, en fazla <c>logTopCandidates</c> tane. Havuz rakiplerinin kararlarinda
    /// (<c>IsLearner = 0</c>) yalnizca <c>chosenVector</c> yazilir.
    /// </para>
    /// </remarks>
    public sealed class SelfPlayRunner : IDisposable
    {
        private readonly SelfPlayConfig _cfg;
        private readonly SelfPlayAgent _learner;
        private readonly SelfPlayAgent? _pool;
        private readonly EngineSettings _engineSettings;
        private Xoshiro256StarStar _rng;

        private readonly BackgammonState _state = new BackgammonState();
        private readonly BackgammonState _scratch = new BackgammonState();

        private readonly float[] _chosenVector = new float[BackgammonVectorizer.InputVectorSize];
        private readonly float[] _candidateVector = new float[BackgammonVectorizer.InputVectorSize];

        private float[] _q = new float[AfterStateList.DefaultCapacity];
        private float[] _pi = new float[AfterStateList.DefaultCapacity];
        private float[] _weight = new float[AfterStateList.DefaultCapacity];
        private byte[] _kind = new byte[AfterStateList.DefaultCapacity];
        private int[] _order = new int[AfterStateList.DefaultCapacity];

        /// <summary>Yeni bir kosucu olusturur.</summary>
        /// <param name="config">Yapilandirma (dogrulanmis olmali).</param>
        /// <param name="learner">Ogrenen ajan.</param>
        /// <param name="pool">Havuz rakip ajani; <c>null</c> ise yalnizca oz-oyun.</param>
        /// <param name="seed">Bu is parcaciginin RNG tohumu.</param>
        public SelfPlayRunner(SelfPlayConfig config, SelfPlayAgent learner, SelfPlayAgent? pool, ulong seed)
        {
            if (config == null)
            {
                throw new ArgumentNullException(nameof(config));
            }

            if (learner == null)
            {
                throw new ArgumentNullException(nameof(learner));
            }

            _cfg = config;
            _learner = learner;
            _pool = pool;
            _engineSettings = EngineSettings.Default;
            _rng = new Xoshiro256StarStar(seed);
        }

        /// <summary>Ogrenen ajanin model surumu.</summary>
        public uint ModelVersion
        {
            get { return _learner.ModelVersion; }
        }

        /// <summary>
        /// RNG'yi oyun basina tohumla yeniden kurar (Faz 6 Bolum 7.2).
        /// </summary>
        /// <remarks>
        /// <c>seed(gameIndex) = baseSeed + gameIndex</c> oldugu icin ayni oyun, is parcacigi
        /// sayisindan bagimsiz olarak ayni zarlari alir; <c>--threads N</c> ciktisi
        /// <c>--threads 1</c> ile ayni olur (Test 60).
        /// </remarks>
        public void ResetSeed(ulong seed)
        {
            _rng = new Xoshiro256StarStar(seed);
        }

        /// <summary>
        /// Tek bir oyun oynar ve karar kayitlarini dondurur.
        /// </summary>
        /// <param name="gameId">Oyun kimligi.</param>
        /// <param name="poolGame">Havuz rakipli oyun mu?</param>
        /// <param name="learnerSide">Havuz oyununda ogrenen rengi (+1/-1); oz-oyunda yok sayilir.</param>
        public ShardGame PlayGame(ulong gameId, bool poolGame, sbyte learnerSide)
        {
            var game = new ShardGame
            {
                GameId = gameId,
                LearnerSide = poolGame ? learnerSide : (sbyte)0,
                CubeValue = 1
            };

            BackgammonEngine.NewGame(_state, MatchSettings.MoneyGame);
            BackgammonEngine.RollOpening(_state, _rng);

            int ply = 0;
            while (true)
            {
                if (ply >= _cfg.MaxPlies)
                {
                    game.Flags |= ShardGameFlags.Aborted;
                    game.Winner = 0;
                    game.ResultType = 0;
                    game.ResultPoints = 0;
                    return game;
                }

                sbyte mover = _state.turn;
                bool isLearner = !poolGame || mover == learnerSide;
                SelfPlayAgent agent = isLearner ? _learner : _pool!;

                MoveSequence chosen;
                bool isPass;
                ShardDecision decision = Decide(agent, mover, isLearner, ply, out chosen, out isPass);
                game.Decisions.Add(decision);

                if (isPass)
                {
                    BackgammonEngine.PassTurn(_state);
                }
                else
                {
                    BackgammonEngine.ApplyMove(_state, chosen);
                    if (_state.phase == GamePhase.GameOver)
                    {
                        GameResult result;
                        BackgammonEngine.IsGameOver(_state, _engineSettings, out result);
                        game.Winner = result.Winner;
                        game.ResultType = (byte)result.ResultType;
                        game.ResultPoints = (byte)result.Points;
                        return game;
                    }

                    BackgammonEngine.EndTurn(_state, _engineSettings);
                }

                ply++;
                BackgammonEngine.RollDice(_state, _rng);
            }
        }

        private ShardDecision Decide(SelfPlayAgent agent, sbyte mover, bool isLearner, int ply,
                                     out MoveSequence chosen, out bool isPass)
        {
            SearchResult sr = BackgammonSearch.Search(_state, agent.Settings, _engineSettings,
                                                      agent.Workspace, agent.Evaluator, agent.Evaluator);

            int count = sr.CandidateCount;
            EnsureCapacity(count);

            for (int k = 0; k < count; k++)
            {
                RootCandidate c = sr.RootCandidates[k];
                _q[k] = c.Score;
                _pi[k] = c.PolicyTarget;
                _kind[k] = c.Kind;
            }

            isPass = sr.IsPass;

            var decision = new ShardDecision
            {
                Mover = mover,
                CandidateTotal = (ushort)count,
                SearchValue = sr.EvaluationScore
            };

            if (isLearner)
            {
                decision.Flags |= ShardDecisionFlags.IsLearner;
            }

            // Faz 7 §5.4 / Test 100-101: damitma ogretmeni karari. Deger hedefi
            // ``SearchValue`` (ogretmenin kok degeri), politika hedefi ``q`` alanidir.
            if (isLearner && _cfg.DistillMode)
            {
                decision.Flags |= ShardDecisionFlags.Distilled;
            }

            if (isPass)
            {
                decision.Flags |= ShardDecisionFlags.IsPass;
            }

            int chosenIndex = -1;
            if (!isPass && count > 0)
            {
                chosenIndex = ply < _cfg.ExplorationPlies ? SampleCandidate(count) : ArgMaxCandidate(count);
            }

            chosen = default(MoveSequence);
            if (chosenIndex >= 0)
            {
                chosen = sr.RootCandidates[chosenIndex].Sequence;
            }

            if (isPass || chosenIndex < 0)
            {
                // Pas: afterstate = mevcut pozisyon (mover perspektifi). Faz 1 v4 AddPass ile ayni.
                BackgammonVectorizer.Vectorize(_state, mover, _chosenVector);
                decision.ChosenVector = CopyOf(_chosenVector);
            }
            else if (_kind[chosenIndex] == 0)
            {
                decision.Flags |= ShardDecisionFlags.ChosenIsTerminal;
            }
            else
            {
                VectorizeAfterMove(chosen, mover, _chosenVector);
                decision.ChosenVector = CopyOf(_chosenVector);
            }

            if (isLearner && !isPass)
            {
                FillLoggedCandidates(decision, sr.RootCandidates, count, mover);
            }

            return decision;
        }

        private void FillLoggedCandidates(ShardDecision decision, ReadOnlySpan<RootCandidate> candidates,
                                          int count, int mover)
        {
            int m = 0;
            for (int k = 0; k < count; k++)
            {
                if (_kind[k] == 1)
                {
                    _order[m++] = k;
                }
            }

            if (m == 0)
            {
                return;
            }

            StableSortDescending(_order, m);

            int logged = _cfg.LogTopCandidates > 0 ? Math.Min(_cfg.LogTopCandidates, m) : m;
            int vectorSize = BackgammonVectorizer.InputVectorSize;

            var q = new float[logged];
            var pi = new float[logged];
            var vectors = new float[logged * vectorSize];

            for (int j = 0; j < logged; j++)
            {
                int k = _order[j];
                q[j] = _q[k];
                pi[j] = _pi[k];
                VectorizeAfterMove(candidates[k].Sequence, mover, _candidateVector);
                Array.Copy(_candidateVector, 0, vectors, j * vectorSize, vectorSize);
            }

            decision.Q = q;
            decision.PolicyTargetCs = pi;
            decision.CandidateVectors = vectors;
        }

        private void VectorizeAfterMove(in MoveSequence sequence, int mover, float[] destination)
        {
            _scratch.CopyFrom(_state);
            BackgammonEngine.ApplyMove(_scratch, sequence);
            BackgammonVectorizer.Vectorize(_scratch, mover, destination);
        }

        private int ArgMaxCandidate(int count)
        {
            int best = -1;
            float bestQ = float.NegativeInfinity;
            for (int k = 0; k < count; k++)
            {
                if (_kind[k] == 2)
                {
                    continue;
                }

                if (_q[k] > bestQ)
                {
                    bestQ = _q[k];
                    best = k;
                }
            }

            return best;
        }

        private int SampleCandidate(int count)
        {
            float maxQ = float.NegativeInfinity;
            for (int k = 0; k < count; k++)
            {
                if (_kind[k] != 2 && _q[k] > maxQ)
                {
                    maxQ = _q[k];
                }
            }

            if (float.IsNegativeInfinity(maxQ))
            {
                return -1;
            }

            float inverseTemperature = 1f / _cfg.SelectionTemperature;
            double sum = 0.0;
            for (int k = 0; k < count; k++)
            {
                if (_kind[k] == 2)
                {
                    _weight[k] = 0f;
                    continue;
                }

                float w = (float)Math.Exp((_q[k] - maxQ) * inverseTemperature);
                _weight[k] = w;
                sum += w;
            }

            if (!(sum > 0.0))
            {
                return ArgMaxCandidate(count);
            }

            double target = NextDouble() * sum;
            double accumulated = 0.0;
            for (int k = 0; k < count; k++)
            {
                if (_weight[k] <= 0f)
                {
                    continue;
                }

                accumulated += _weight[k];
                if (target < accumulated)
                {
                    return k;
                }
            }

            return ArgMaxCandidate(count);
        }

        private void StableSortDescending(int[] indices, int n)
        {
            for (int i = 1; i < n; i++)
            {
                int value = indices[i];
                float key = _q[value];
                int j = i - 1;
                while (j >= 0 && _q[indices[j]] < key)
                {
                    indices[j + 1] = indices[j];
                    j--;
                }

                indices[j + 1] = value;
            }
        }

        private double NextDouble()
        {
            ulong high = _rng.NextUInt();
            ulong low = _rng.NextUInt();
            ulong bits = ((high << 32) | low) >> 11;
            return bits * (1.0 / 9007199254740992.0);
        }

        private void EnsureCapacity(int count)
        {
            if (count <= _q.Length)
            {
                return;
            }

            int capacity = _q.Length;
            while (capacity < count)
            {
                capacity *= 2;
            }

            _q = new float[capacity];
            _pi = new float[capacity];
            _weight = new float[capacity];
            _kind = new byte[capacity];
            _order = new int[capacity];
        }

        private static float[] CopyOf(float[] source)
        {
            var copy = new float[source.Length];
            Array.Copy(source, copy, source.Length);
            return copy;
        }

        /// <inheritdoc/>
        public void Dispose()
        {
        }
    }
}
