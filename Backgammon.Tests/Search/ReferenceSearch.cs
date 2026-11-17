using System;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 3 v7 Bölüm 8 Test 1: <b>referans arama</b>. Budamasız, cache'siz, sade; aynı aday seçim
    /// kuralı, aynı zar sırası, <b>tek kırpma</b>, aynı politika sıralaması, aynı terminal
    /// <c>ResultPoints / cubeValue</c> değeri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Allocation serbesttir (yalnızca test projesinde). Yine de ply başına havuz kullanılır:
    /// <c>_lists[depth]</c> ve <c>_states[depth]</c>. Bu, özyineleme sırasında üst düğümün
    /// listesinin bozulmamasını garanti eder (alt düğümler farklı indeks kullanır).
    /// </para>
    /// <para>
    /// <b>Kırpma:</b> yalnızca <see cref="IPositionEvaluator.EvaluateBatch"/> çıktısında, tek yerde
    /// (<see cref="SearchTestSupport.Clamp"/>). Değerlendiriciler kırpmaz.
    /// </para>
    /// </remarks>
    internal sealed class ReferenceSearch
    {
        private readonly AfterStateList[] _lists;
        private readonly BackgammonState[] _states;

        public ReferenceSearch()
        {
            int n = SearchWorkspace.MaxSupportedPly + 1;
            _lists = new AfterStateList[n];
            _states = new BackgammonState[n];
            for (int i = 0; i < n; i++)
            {
                _lists[i] = new AfterStateList();
                _states[i] = new BackgammonState();
            }
        }

        /// <summary>Kök değeri ve en iyi hamle dizisini döner.</summary>
        public float RootValue(BackgammonState state, in SearchSettings ss, in EngineSettings es,
                               IPositionEvaluator evaluator, IPolicyEvaluator policy,
                               out MoveSequence bestSequence)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            if (ss.DepthPly < 0 || ss.DepthPly > SearchWorkspace.MaxSupportedPly)
            {
                throw new ArgumentException("DepthPly 0.." + SearchWorkspace.MaxSupportedPly + " olmalı: " + ss.DepthPly);
            }

            return SearchNode(state, ss.DepthPly, true, es, evaluator, policy, ss, out bestSequence);
        }

        /// <summary>Kök değeri (hamle dizisi ilgilenilmiyorsa).</summary>
        public float RootValue(BackgammonState state, in SearchSettings ss, in EngineSettings es,
                               IPositionEvaluator evaluator, IPolicyEvaluator policy)
        {
            return RootValue(state, ss, es, evaluator, policy, out _);
        }

        private float SearchNode(BackgammonState s, int depth, bool isRoot, in EngineSettings es,
                                 IPositionEvaluator evaluator, IPolicyEvaluator policy,
                                 in SearchSettings ss, out MoveSequence bestSequence)
        {
            AfterStateList list = _lists[depth];
            list.Clear();

            LegalMoveGenerator.GenerateAfterStates(s, es, list);
            if (list.Count == 0)
            {
                list.AddPass(s);
            }

            int nonTerminal = SearchTestSupport.PartitionNonTerminal(list);
            var scalars = VectorizerScalars.From(s);

            int n = list.Count;
            var order = new int[n];
            var kinds = new byte[n];

            float[]? leafValues = null;
            if (depth == 0 && nonTerminal > 0)
            {
                leafValues = new float[nonTerminal];
                evaluator.EvaluateBatch(list, 0, nonTerminal, s.turn, scalars, leafValues);
                for (int i = 0; i < nonTerminal; i++)
                {
                    leafValues[i] = SearchTestSupport.Clamp(leafValues[i]);
                }
            }

            BuildOrder(list, nonTerminal, s.turn, scalars, evaluator, policy, ss, isRoot, order, kinds, leafValues);

            float best = float.NegativeInfinity;
            bestSequence = default;

            for (int k = 0; k < n; k++)
            {
                int i = order[k];
                if (kinds[i] == 2)
                {
                    continue;
                }

                float q;
                if (list.IsTerminal[i])
                {
                    q = list.ResultPoints[i] / (float)s.cubeValue;
                }
                else if (depth == 0)
                {
                    q = leafValues![i];
                }
                else
                {
                    q = ChanceNode(s, list, i, depth, es, evaluator, policy, ss);
                }

                if (q > best)
                {
                    best = q;
                    bestSequence = list.Sequences[i];
                }
            }

            return best;
        }

        private float ChanceNode(BackgammonState s, AfterStateList list, int i, int depth,
                                 in EngineSettings es, IPositionEvaluator evaluator,
                                 IPolicyEvaluator policy, in SearchSettings ss)
        {
            BackgammonState child = _states[depth];
            float sum = 0f;

            for (int r = 0; r < RollSet.NormalCount; r++)
            {
                child.CopyFrom(s);
                BackgammonEngine.LoadAfterState(child, list, i);
                BackgammonEngine.EndTurn(child, es);
                BackgammonEngine.SetDice(child, RollSet.NormalDie1[r], RollSet.NormalDie2[r]);

                float v = SearchNode(child, depth - 1, false, es, evaluator, policy, ss, out _);
                sum += RollSet.NormalWeight[r] * (-v);
            }

            return sum / 36f;
        }

        private static void BuildOrder(AfterStateList list, int nonTerminal, int perspective,
                                       in VectorizerScalars scalars, IPositionEvaluator evaluator,
                                       IPolicyEvaluator policy, in SearchSettings ss, bool isRoot,
                                       int[] order, byte[] kinds, float[]? leafValues)
        {
            int n = list.Count;
            int maxCandidates = isRoot ? ss.MaxCandidatesRoot : ss.MaxCandidatesInner;
            bool usePolicy = ss.UsePolicyOrdering && policy != null;

            var sortScores = new float[n];

            if (nonTerminal > 1)
            {
                if (usePolicy)
                {
                    var prio = new float[nonTerminal];
                    policy!.ScoreBatch(list, 0, nonTerminal, perspective, scalars, prio);
                    for (int i = 0; i < nonTerminal; i++)
                    {
                        sortScores[i] = prio[i] < 0f ? 0f : prio[i];
                    }
                }
                else if (leafValues != null)
                {
                    for (int i = 0; i < nonTerminal; i++)
                    {
                        sortScores[i] = leafValues![i];
                    }
                }
                else
                {
                    var vals = new float[nonTerminal];
                    evaluator.EvaluateBatch(list, 0, nonTerminal, perspective, scalars, vals);
                    for (int i = 0; i < nonTerminal; i++)
                    {
                        sortScores[i] = SearchTestSupport.Clamp(vals[i]);
                    }
                }
            }

            for (int i = nonTerminal; i < n; i++)
            {
                sortScores[i] = list.ResultPoints[i];
            }

            var nonTermIdx = new int[nonTerminal];
            for (int i = 0; i < nonTerminal; i++)
            {
                nonTermIdx[i] = i;
            }

            StableSortDescending(nonTermIdx, sortScores);

            int termCount = n - nonTerminal;
            var termIdx = new int[termCount];
            for (int i = 0; i < termCount; i++)
            {
                termIdx[i] = nonTerminal + i;
            }

            StableSortDescending(termIdx, sortScores);

            int pos = 0;
            if (usePolicy)
            {
                for (int k = 0; k < nonTerminal; k++)
                {
                    order[pos++] = nonTermIdx[k];
                }

                for (int k = 0; k < termCount; k++)
                {
                    order[pos++] = termIdx[k];
                }
            }
            else
            {
                for (int k = 0; k < termCount; k++)
                {
                    order[pos++] = termIdx[k];
                }

                for (int k = 0; k < nonTerminal; k++)
                {
                    order[pos++] = nonTermIdx[k];
                }
            }

            for (int i = 0; i < n; i++)
            {
                kinds[i] = 0;
            }

            for (int k = 0; k < nonTerminal; k++)
            {
                kinds[nonTermIdx[k]] = maxCandidates > 0 && k >= maxCandidates ? (byte)2 : (byte)1;
            }
        }

        /// <summary>Azalan, <b>kararlı</b> sıralama (eşitlikte düşük indeks önce).</summary>
        private static void StableSortDescending(int[] idx, float[] scores)
        {
            for (int i = 1; i < idx.Length; i++)
            {
                int key = idx[i];
                float keyScore = scores[key];
                int j = i - 1;
                while (j >= 0 && scores[idx[j]] < keyScore)
                {
                    idx[j + 1] = idx[j];
                    j--;
                }

                idx[j + 1] = key;
            }
        }
    }
}