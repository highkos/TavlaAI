using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 3 v7: politika yönlendirmeli expectiminimax arama motoru.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Değer sözleşmesi (Bölüm 1):</b> küpsüz (cubeless) para equity'si, küp değeri 1'e normalize,
    /// aralık <c>[L, U] = [-3, +3]</c>. Her değer <b>bir oyuncunun</b> gözünden verilir; hamleyi yapan
    /// oyuncuya <c>mover</c> denir. <b>Negamax:</b> çocuğun değeri üst düğüme <c>-v</c> olarak döner.
    /// </para>
    /// <para>
    /// <b>Ply (Bölüm 2):</b> <c>depthPly</c> = chance (zar) katmanı sayısı. 0-ply: afterstate'ler
    /// doğrudan değerlendirilir. 1-ply: her aday için rakibin 21 zarı üzerinden ağırlıklı ortalama.
    /// </para>
    /// <para>
    /// <b>Kırpma sahipliği (Bölüm 1, 4.1):</b> değerlendirici <c>[-3,3]</c>'e kırpmaz; kırpma
    /// <b>aramanın</b> sorumluluğundadır. Böylece <c>ReferenceSearch</c> ile bu arama <b>aynı sayıda</b>
    /// kırpma uygular (Test 1).
    /// </para>
    /// <para>
    /// <b>Düğüm yerleşimi (Bölüm 6):</b> <c>node = 2·(DepthPly − d)</c> max düğümü, <c>node + 1</c>
    /// chance düğümünün çalışma state'i. <c>DepthPly ≤ 4</c> için en büyük indeks 8 &lt;
    /// <see cref="SearchWorkspace.MaxNodes"/>.
    /// </para>
    /// </remarks>
    public static class BackgammonSearch
    {
        /// <summary>Değer aralığının alt sınırı.</summary>
        public const float L = -3f;

        /// <summary>Değer aralığının üst sınırı.</summary>
        public const float U = 3f;

        /// <summary>
        /// Kök araması. Önkoşul: <c>state.phase == Moving</c>, zarlar atılmış
        /// (<c>remainingCount &gt; 0</c>), oyun bitmemiş. <c>state</c> <b>değişmez</b> (hash dahil).
        /// </summary>
        public static SearchResult Search(BackgammonState state, in SearchSettings ss, in EngineSettings es,
                                          SearchWorkspace ws, IPositionEvaluator evaluator,
                                          IPolicyEvaluator policyEvaluator)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            if (ws == null)
            {
                throw new ArgumentNullException(nameof(ws));
            }

            if (evaluator == null)
            {
                throw new ArgumentNullException(nameof(evaluator));
            }

            if (ss.DepthPly < 0 || ss.DepthPly > SearchWorkspace.MaxSupportedPly)
            {
                throw new ArgumentException(
                    "DepthPly 0.." + SearchWorkspace.MaxSupportedPly + " aralığında olmalı: " + ss.DepthPly, nameof(ss));
            }

            if (ss.MaxCandidatesRoot < 0)
            {
                throw new ArgumentException("MaxCandidatesRoot negatif olamaz: " + ss.MaxCandidatesRoot, nameof(ss));
            }

            if (ss.MaxCandidatesInner < 0)
            {
                throw new ArgumentException("MaxCandidatesInner negatif olamaz: " + ss.MaxCandidatesInner, nameof(ss));
            }

            if (!(ss.PolicyTemperature > 0f))
            {
                throw new ArgumentException("PolicyTemperature > 0 olmalı: " + ss.PolicyTemperature, nameof(ss));
            }

            bool usePolicy = ss.UsePolicyOrdering && policyEvaluator != null;
            ICombinedBatchEvaluator combined = usePolicy ? evaluator as ICombinedBatchEvaluator : null;
            IExactValueEvaluator exactEvaluator = ss.UseBearoffCutoff ? evaluator as IExactValueEvaluator : null;

            ws.BeginSearch();
            ws.EnsureCacheConsistent(evaluator.Version, SettingsSignature(ss));
            ws.EnsureTransposition(ss.TranspositionCapacity);

            int bestIndex;
            bool isPass;
            float value = SearchNode(state, ss.DepthPly, 0, true, L, U, ss, es, ws, evaluator,
                                     policyEvaluator, combined, usePolicy, exactEvaluator,
                                     out bestIndex, out isPass);

            AfterStateList rootList = ws.ListAt(0);
            int candidateCount = rootList.Count;

            MoveSequence bestSequence = default;
            if (!isPass && bestIndex >= 0)
            {
                bestSequence = rootList.Sequences[bestIndex];
            }

            int policyTargetCount = 0;
            if (ss.ExactRootScores && !isPass)
            {
                policyTargetCount = BuildRootPolicyTarget(candidateCount, ss.PolicyTemperature, ws);
            }

            ws.SetRootCounts(candidateCount, policyTargetCount);

            // Faz 7 §5.4 / Test 99: damitma modunda kok deger hedefi (6 cikti).
            OutcomeDistribution? rootValue = null;
            if (ss.DistillMode && !isPass && bestIndex >= 0)
            {
                rootValue = RootValueOf(rootList, bestIndex, state.turn, VectorizerScalars.From(state), evaluator);
            }

            return new SearchResult
            {
                BestSequence = bestSequence,
                EvaluationScore = value,
                IsPass = isPass,
                CandidateCount = candidateCount,
                EvaluatorCalls = ws.EvaluatorCalls,
                PolicyCalls = ws.PolicyCalls,
                NodesVisited = ws.NodesVisited,
                TranspositionHits = ws.TranspositionHits,
                TranspositionStores = ws.TranspositionStores,
                RootCandidates = ws.RootCandidates,
                RootPolicyTarget = ws.RootPolicyTarget,
                RootValue = rootValue
            };
        }

        /// <summary>
        /// Faz 7 §5.4: secilen kok afterstate'in 6 ciktili sonuc dagilimi.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <b>Terminal afterstate</b> icin dagilim <b>oyun kuralindan</b> gelir (nokta kutlesi);
        /// agdan istenmez. Terminal olmayan icin <see cref="IOutcomeDistributionEvaluator"/>
        /// kullanilir; degerlendirici bu arayuzu uygulamiyorsa <c>null</c> doner.
        /// </para>
        /// <para>
        /// <b>Perspektif:</b> dagilim <b>mover</b> (<c>turn</c>) perspektifindendir; bu, arama
        /// degerinin perspektifiyle aynidir.
        /// </para>
        /// <para>
        /// <b>Offset kisiti:</b> <see cref="IOutcomeDistributionEvaluator.EvaluateDistributionBatch"/>
        /// su an yalnizca <c>offset = 0</c> destekler. Bu yuzden secilen afterstate gecici olarak
        /// 0. siraya alinir ve cagri sonrasi <b>geri konur</b>; boylece ayirma yapilmaz ve kok
        /// aday listesi degismez.
        /// </para>
        /// <para>
        /// <b>v1 model:</b> <c>output_version &lt; 2</c> model dagilim uretemedigi icin
        /// <see cref="System.NotSupportedException"/> atar. Bu <b>bilinclidir</b>: damitma
        /// sessizce deger hedefsiz birakilmaz.
        /// </para>
        /// </remarks>
        private static OutcomeDistribution? RootValueOf(
            AfterStateList list, int index, int turn, in VectorizerScalars scalars, IPositionEvaluator evaluator)
        {
            if (list.IsTerminal[index])
            {
                return TerminalDistribution(list.ResultType[index], list.ResultPoints[index]);
            }

            IOutcomeDistributionEvaluator distribution = evaluator as IOutcomeDistributionEvaluator;
            if (distribution == null)
            {
                return null;
            }

            // Skalerler kup/mac bilgisidir; kok afterstate'lerin hepsi icin aynidir.
            Span<OutcomeDistribution> buffer = stackalloc OutcomeDistribution[1];
            bool moved = index != 0;
            if (moved)
            {
                list.Swap(0, index);
            }

            try
            {
                distribution.EvaluateDistributionBatch(list, 0, 1, turn, scalars, buffer);
            }
            finally
            {
                if (moved)
                {
                    list.Swap(0, index);
                }
            }

            return buffer[0].IsValid ? buffer[0] : (OutcomeDistribution?)null;
        }

        /// <summary>
        /// Faz 7 §5.4: terminal afterstate icin nokta kutlesi dagilimi.
        /// </summary>
        /// <remarks>
        /// <c>ResultType</c>: 1 = tek, 2 = mars, 3 = backgammon. <c>ResultPoints</c> isaretlidir
        /// (mover kazandiysa pozitif). Gecersiz tur icin <c>null</c>.
        /// </remarks>
        private static OutcomeDistribution? TerminalDistribution(byte resultType, byte resultPoints)
        {
            bool win = resultPoints > 0;
            switch (resultType)
            {
                case 1:
                    return win
                        ? new OutcomeDistribution(1f, 0f, 0f, 0f, 0f)
                        : new OutcomeDistribution(0f, 0f, 0f, 0f, 0f);
                case 2:
                    return win
                        ? new OutcomeDistribution(0f, 1f, 0f, 0f, 0f)
                        : new OutcomeDistribution(0f, 0f, 0f, 1f, 0f);
                case 3:
                    return win
                        ? new OutcomeDistribution(0f, 0f, 1f, 0f, 0f)
                        : new OutcomeDistribution(0f, 0f, 0f, 0f, 1f);
                default:
                    return null;
            }
        }

        /// <summary>Kolaylık aşırı yükleme (<c>policyEvaluator = null</c>).</summary>
        public static SearchResult Search(BackgammonState state, in SearchSettings ss, in EngineSettings es,
                                          SearchWorkspace ws, IPositionEvaluator evaluator)
        {
            return Search(state, ss, es, ws, evaluator, null);
        }

        /// <summary>
        /// Zar atılmadan önceki pozisyonun beklenen değeri (analiz aracı; ağaç içinde kullanılmaz).
        /// Politikayı <b>kullanmaz</b> (chance düğümü, aday yok).
        /// </summary>
        /// <remarks>
        /// <c>DepthPly</c> toplam chance katmanı sayısıdır; bu çağrı ilk katmanı (atılacak zar)
        /// tüketir, dolayısıyla alt arama <c>DepthPly − 1</c> ile yapılır. <c>DepthPly == 0</c>
        /// anlamsızdır (zar katmanı yok) ve <c>ArgumentException</c> atar.
        /// </remarks>
        public static float AnalyzePreRoll(BackgammonState state, RollSetKind set, in SearchSettings ss,
                                           in EngineSettings es, SearchWorkspace ws, IPositionEvaluator evaluator)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            if (ws == null)
            {
                throw new ArgumentNullException(nameof(ws));
            }

            if (evaluator == null)
            {
                throw new ArgumentNullException(nameof(evaluator));
            }

            if (ss.DepthPly < 1 || ss.DepthPly > SearchWorkspace.MaxSupportedPly)
            {
                throw new ArgumentException(
                    "AnalyzePreRoll için DepthPly 1.." + SearchWorkspace.MaxSupportedPly + " olmalı: " + ss.DepthPly,
                    nameof(ss));
            }

            ws.BeginSearch();
            ws.EnsureCacheConsistent(evaluator.Version, SettingsSignature(ss));
            ws.EnsureTransposition(ss.TranspositionCapacity);

            IExactValueEvaluator exactEvaluator = ss.UseBearoffCutoff ? evaluator as IExactValueEvaluator : null;

            int count = RollSet.CountOf(set);
            int total = RollSet.WeightTotalOf(set);
            byte[] die1 = set == RollSetKind.Opening ? RollSet.OpeningDie1 : RollSet.NormalDie1;
            byte[] die2 = set == RollSetKind.Opening ? RollSet.OpeningDie2 : RollSet.NormalDie2;
            byte[] weight = set == RollSetKind.Opening ? RollSet.OpeningWeight : RollSet.NormalWeight;

            BackgammonState child = ws.StateAt(1);
            float sum = 0f;

            for (int r = 0; r < count; r++)
            {
                child.CopyFrom(state);
                BackgammonEngine.SetDice(child, die1[r], die2[r]);

                int bestIndex;
                bool isPass;
                float v = SearchNode(child, ss.DepthPly - 1, 0, false, L, U, ss, es, ws, evaluator,
                                     null, null, false, exactEvaluator, out bestIndex, out isPass);
                sum += weight[r] * v;
            }

            return sum / total;
        }

        // ------------------------------------------------------------------
        // Ağaç
        // ------------------------------------------------------------------

        private static float SearchNode(BackgammonState s, int d, int node, bool isRoot,
                                        float alpha, float beta,
                                        in SearchSettings ss, in EngineSettings es, SearchWorkspace ws,
                                        IPositionEvaluator evaluator, IPolicyEvaluator policy,
                                        ICombinedBatchEvaluator combined, bool usePolicy,
                                        IExactValueEvaluator exactEvaluator,
                                        out int bestIndex, out bool isPass)
        {
            ws.NodesVisited++;

            // Faz 6 §9.4: saf bearoff'ta kesin değer varsa derinliği 0'a indir. Sonuç değişmez
            // (saf yarışta kesin değer her derinlikteki arama sonucuna eşittir).
            if (d > 0 && exactEvaluator != null && exactEvaluator.IsExactFor(s.board))
            {
                d = 0;
            }

            // Faz 6 §9.3: transposition table. Kökte kullanılmaz (RootCandidates doldurulmalı).
            bool useTt = ss.TranspositionCapacity > 0 && !isRoot && d >= 1;
            ulong ttKey = 0UL;
            if (useTt)
            {
                ttKey = TranspositionKey(s, d);
                float ttScore;
                if (ws.TryGetTransposition(ttKey, d, out ttScore))
                {
                    ws.TranspositionHits++;
                    bestIndex = -1;
                    isPass = false;
                    return ttScore;
                }
            }

            AfterStateList list = ws.ListAt(node);
            list.Clear();
            LegalMoveGenerator.GenerateAfterStates(s, es, list);

            isPass = list.Count == 0;
            if (isPass)
            {
                list.AddPass(s);
            }

            int nonTerminal = PartitionNonTerminal(list);
            int n = list.Count;
            VectorizerScalars scalars = VectorizerScalars.From(s);

            float[] staticScores = ws.StaticScoresAt(node);
            float[] policyScores = ws.PolicyScoresAt(node);
            int[] order = ws.CandidateOrderAt(node);
            byte[] kinds = ws.KindsAt(node);

            int maxCandidates = isRoot ? ss.MaxCandidatesRoot : ss.MaxCandidatesInner;
            bool needOrder = isRoot || d >= 1 || maxCandidates > 0;

            bool needStatic = nonTerminal > 0 && (d == 0 || (isRoot && maxCandidates > 0));
            bool wantPolicy = needOrder && usePolicy && nonTerminal > 1;
            bool policyUsable = false;

            if (wantPolicy && needStatic && isRoot && maxCandidates > 0 && combined != null)
            {
                var values = new Span<float>(staticScores, 0, nonTerminal);
                var priorities = new Span<float>(policyScores, 0, nonTerminal);
                combined.EvaluateAndScoreBatch(list, 0, nonTerminal, s.turn, scalars, values, priorities);
                ws.EvaluatorCalls++;
                ClampInPlace(staticScores, nonTerminal);
                policyUsable = ClampPriorities(policyScores, nonTerminal);
            }
            else
            {
                if (wantPolicy)
                {
                    policy.ScoreBatch(list, 0, nonTerminal, s.turn, scalars,
                                      new Span<float>(policyScores, 0, nonTerminal));
                    ws.PolicyCalls++;
                    policyUsable = ClampPriorities(policyScores, nonTerminal);
                }

                if (nonTerminal > 0 && (needStatic || (needOrder && !policyUsable)))
                {
                    evaluator.EvaluateBatch(list, 0, nonTerminal, s.turn, scalars,
                                            new Span<float>(staticScores, 0, nonTerminal));
                    ws.EvaluatorCalls++;
                    ClampInPlace(staticScores, nonTerminal);
                }
            }

            // Depth 0 önbelleği (Bölüm 3.5): Eval0 sonuçları da kesindir ve önbelleğe yazılır.
            // Toplu çağrı bölünemediği için tüm kayıtlar değerlendirilir; isabet edenler
            // önbellekteki değerle değiştirilir (değer özdeştir, sıralama değişmez).
            if (ss.UseEvalCache && d == 0 && nonTerminal > 0 && needStatic)
            {
                for (int i = 0; i < nonTerminal; i++)
                {
                    ulong key = list.Hash[i];
                    float cached;
                    if (ws.TryGetCached(key, out cached))
                    {
                        staticScores[i] = cached;
                    }
                    else
                    {
                        ws.StoreCached(key, staticScores[i]);
                    }
                }
            }

            if (needOrder)
            {
                float[] sortScores = policyUsable ? policyScores : staticScores;
                for (int i = nonTerminal; i < n; i++)
                {
                    sortScores[i] = list.ResultPoints[i];
                }

                BuildOrder(nonTerminal, n, policyUsable, sortScores, order, kinds, maxCandidates);
            }
            else
            {
                for (int i = 0; i < n; i++)
                {
                    order[i] = i;
                    kinds[i] = list.IsTerminal[i] ? (byte)0 : (byte)1;
                }
            }

            float best = float.NegativeInfinity;
            bestIndex = -1;
            float cubeValue = s.cubeValue;
            bool broke = false;

            // Kökte ExactRootScores = true iken her aday tam pencerede aranır ve kesme yapılmaz
            // (Bölüm 4.5): politika hedefi için tüm kesin Q değerleri gerekir.
            bool prune = ss.UseAlphaBeta && !(isRoot && ss.ExactRootScores);

            // Kökte erken kesme yapılmaz: RootCandidates tüm adaylar için dolu kalmalıdır.
            bool canBreak = prune && !isRoot;

            for (int k = 0; k < n; k++)
            {
                int i = order[k];
                byte kind = kinds[i];

                float q;
                if (kind == 2)
                {
                    q = staticScores[i];
                }
                else if (list.IsTerminal[i])
                {
                    q = list.ResultPoints[i] / cubeValue;
                }
                else if (d == 0)
                {
                    q = staticScores[i];
                }
                else
                {
                    float childAlpha = L;
                    float childBeta = U;
                    if (prune)
                    {
                        childAlpha = best > alpha ? best : alpha;
                        childBeta = beta;
                    }

                    // Eval cache (Bölüm 3.5): anahtar = afterstate hash'i ^ depth. Yalnızca
                    // KESİN Q yazılır; budanmış (sınır) değerler asla yazılmaz.
                    bool exactWindow = !prune || (childAlpha <= L && childBeta >= U);
                    ulong key = list.Hash[i] ^ (ulong)d;
                    float cached;

                    if (ss.UseEvalCache && ws.TryGetCached(key, out cached))
                    {
                        q = cached;
                    }
                    else
                    {
                        q = ChanceNode(s, list, i, d, node, childAlpha, childBeta, ss, es, ws, evaluator, policy,
                                       combined, usePolicy, exactEvaluator);

                        if (ss.UseEvalCache && exactWindow)
                        {
                            ws.StoreCached(key, q);
                        }
                    }
                }

                if (isRoot)
                {
                    ws.RootCandidateBuffer[k] = new RootCandidate(list.Sequences[i], q, 0f, kind);
                }

                if (kind != 2 && q > best)
                {
                    best = q;
                    bestIndex = i;
                }

                if (canBreak && best >= beta)
                {
                    broke = true;
                    break;
                }
            }

            // Faz 6 §9.3: yalnızca TAM pencerede ve kesme yapılmadan hesaplanmış değerler kesindir.
            if (useTt && !broke && (!prune || (alpha <= L && beta >= U)))
            {
                ws.StoreTransposition(ttKey, d, best, SearchWorkspace.TtExact);
                ws.TranspositionStores++;
            }

            return best;
        }

        /// <summary>
        /// Chance düğümü: 21 zar üzerinden ağırlıklı ortalama (Bölüm 2, 3.2).
        /// </summary>
        /// <remarks>
        /// <para>
        /// <c>Q = Σ w_r · q_r / 36</c>, burada <c>q_r = −V(çocuk)</c> (negamax). Dönen değer
        /// <b>yalnızca</b> <c>(alpha, beta)</c> penceresinin içindeyse kesindir; dışındaysa sınırdır.
        /// </para>
        /// <para>
        /// <b>Star1</b> (<c>UseStar1 = true</c>): <c>q_r ∈ [L, U]</c> olduğu için kalan zarların
        /// katkısı <c>[R·L, R·U]</c> aralığındadır. <c>A = (36α − S − R·U)/w</c> ve
        /// <c>B = (36β − S − R·L)/w</c> ile erken çıkış yapılır. <c>UseStar1 = false</c> iken
        /// çocuklara tam pencere verilir ve 21 zarın tamamı işlenir.
        /// </para>
        /// </remarks>
        private static float ChanceNode(BackgammonState s, AfterStateList list, int i, int d, int node,
                                        float alpha, float beta,
                                        in SearchSettings ss, in EngineSettings es, SearchWorkspace ws,
                                        IPositionEvaluator evaluator, IPolicyEvaluator policy,
                                        ICombinedBatchEvaluator combined, bool usePolicy,
                                        IExactValueEvaluator exactEvaluator)
        {
            BackgammonState child = ws.StateAt(node + 1);
            bool useStar1 = ss.UseStar1;
            float sum = 0f;

            for (int r = 0; r < RollSet.NormalCount; r++)
            {
                int w = RollSet.NormalWeight[r];
                int remaining = RollSet.NormalRemainingWeightAfter[r];

                float a = 0f;
                float b = 0f;
                float childAlpha = L;
                float childBeta = U;

                if (useStar1)
                {
                    a = (36f * alpha - sum - remaining * U) / w;
                    b = (36f * beta - sum - remaining * L) / w;

                    if (a >= U)
                    {
                        return (sum + (w + remaining) * U) / 36f;
                    }

                    if (b <= L)
                    {
                        return (sum + (w + remaining) * L) / 36f;
                    }

                    childAlpha = -Math.Min(b, U);
                    childBeta = -Math.Max(a, L);
                }

                child.CopyFrom(s);
                BackgammonEngine.LoadAfterState(child, list, i);
                BackgammonEngine.EndTurn(child, es);
                BackgammonEngine.SetDice(child, RollSet.NormalDie1[r], RollSet.NormalDie2[r]);

                int childBest;
                bool childPass;
                float v = SearchNode(child, d - 1, node + 2, false, childAlpha, childBeta, ss, es, ws, evaluator,
                                     policy, combined, usePolicy, exactEvaluator, out childBest, out childPass);
                float q = -v;

                if (useStar1)
                {
                    if (q <= a)
                    {
                        return (sum + w * q + remaining * U) / 36f;
                    }

                    if (q >= b)
                    {
                        return (sum + w * q + remaining * L) / 36f;
                    }
                }

                sum += w * q;
            }

            return sum / 36f;
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        /// <summary>Terminal-olmayan kayıtları listenin başına <b>kararlı</b> olarak taşır.</summary>
        private static int PartitionNonTerminal(AfterStateList list)
        {
            int n = list.Count;
            int write = 0;
            for (int i = 0; i < n; i++)
            {
                if (!list.IsTerminal[i])
                {
                    if (i != write)
                    {
                        list.Swap(i, write);
                    }

                    write++;
                }
            }

            return write;
        }

        private static void ClampInPlace(float[] values, int count)
        {
            for (int i = 0; i < count; i++)
            {
                float v = values[i];
                if (!float.IsFinite(v))
                {
                    throw new ArgumentException("Değerlendirici sonlu olmayan değer döndürdü: " + v);
                }

                if (v < L)
                {
                    v = L;
                }
                else if (v > U)
                {
                    v = U;
                }

                values[i] = v;
            }
        }

        /// <summary>
        /// Negatifleri 0'a kırpar (Bölüm 4.3: politika ağı kendi softmax'ını uygular, arama
        /// <b>ek normalizasyon yapmaz</b>). Toplam 0 ise <c>false</c> → statik sıralamaya düşülür.
        /// </summary>
        private static bool ClampPriorities(float[] priorities, int count)
        {
            float sum = 0f;
            for (int i = 0; i < count; i++)
            {
                float p = priorities[i];
                if (!float.IsFinite(p))
                {
                    throw new ArgumentException("Politika değerlendiricisi sonlu olmayan öncelik döndürdü: " + p);
                }

                if (p < 0f)
                {
                    p = 0f;
                }

                priorities[i] = p;
                sum += p;
            }

            return sum > 0f;
        }

        /// <summary>
        /// Aday sırasını ve <c>Kind</c> etiketlerini üretir (Bölüm 3.3 / 3.4).
        /// Politika yolunda terminal-olmayanlar başta, statik yolda terminal adaylar başta.
        /// </summary>
        private static void BuildOrder(int nonTerminal, int n, bool usePolicy, float[] sortScores,
                                       int[] order, byte[] kinds, int maxCandidates)
        {
            int pos = 0;
            int nonTermStart;

            if (usePolicy)
            {
                nonTermStart = 0;
                for (int i = 0; i < nonTerminal; i++)
                {
                    order[pos++] = i;
                }

                StableSortDescending(order, 0, nonTerminal, sortScores);

                for (int i = nonTerminal; i < n; i++)
                {
                    order[pos++] = i;
                }

                StableSortDescending(order, nonTerminal, n, sortScores);
            }
            else
            {
                for (int i = nonTerminal; i < n; i++)
                {
                    order[pos++] = i;
                }

                StableSortDescending(order, 0, n - nonTerminal, sortScores);

                nonTermStart = n - nonTerminal;
                for (int i = 0; i < nonTerminal; i++)
                {
                    order[pos++] = i;
                }

                StableSortDescending(order, nonTermStart, n, sortScores);
            }

            for (int i = 0; i < n; i++)
            {
                kinds[i] = 0;
            }

            for (int k = 0; k < nonTerminal; k++)
            {
                kinds[order[nonTermStart + k]] = maxCandidates > 0 && k >= maxCandidates ? (byte)2 : (byte)1;
            }
        }

        /// <summary>Azalan, <b>kararlı</b> sıralama (eşitlikte düşük indeks önce).</summary>
        private static void StableSortDescending(int[] order, int start, int end, float[] scores)
        {
            for (int i = start + 1; i < end; i++)
            {
                int key = order[i];
                float keyScore = scores[key];
                int j = i - 1;
                while (j >= start && scores[order[j]] < keyScore)
                {
                    order[j + 1] = order[j];
                    j--;
                }

                order[j + 1] = key;
            }
        }

        /// <summary>
        /// Kök politika hedefini <c>softmax(Q / τ)</c> ile doldurur (Bölüm 3.6, 4.3).
        /// <c>Kind = 2</c> adaylar 0 alır ve softmax'a girmez. Dönen değer hedef uzunluğudur.
        /// </summary>
        private static int BuildRootPolicyTarget(int count, float tau, SearchWorkspace ws)
        {
            RootCandidate[] candidates = ws.RootCandidateBuffer;
            float[] target = ws.RootPolicyTargetBuffer;

            float maxQ = float.NegativeInfinity;
            for (int k = 0; k < count; k++)
            {
                if (candidates[k].Kind != 2 && candidates[k].Score > maxQ)
                {
                    maxQ = candidates[k].Score;
                }
            }

            float sum = 0f;
            for (int k = 0; k < count; k++)
            {
                if (candidates[k].Kind == 2)
                {
                    target[k] = 0f;
                    continue;
                }

                float e = (float)Math.Exp((candidates[k].Score - maxQ) / tau);
                target[k] = e;
                sum += e;
            }

            if (!(sum > 0f))
            {
                return 0;
            }

            for (int k = 0; k < count; k++)
            {
                float p = target[k] / sum;
                target[k] = p;
                RootCandidate c = candidates[k];
                candidates[k] = new RootCandidate(c.Sequence, c.Score, p, c.Kind);
            }

            return count;
        }

        /// <summary>Cache'i etkileyen ayarların imzası (Bölüm 3.5).</summary>
        private static int SettingsSignature(in SearchSettings ss)
        {
            int signature = ss.MaxCandidatesInner * 2;
            if (ss.UsePolicyOrdering)
            {
                signature |= 1;
            }

            return signature;
        }

        /// <summary>
        /// Faz 6 §9.3: transposition anahtarı = Zobrist hash + derinlik + kalan zar maskesi.
        /// </summary>
        /// <remarks>
        /// Zobrist hash <b>zarları içermez</b> (<see cref="Zobrist"/>), bu yüzden kalan zarlar
        /// ayrıca karıştırılır. Aksi halde aynı tahtaya farklı kalan zarlarla ulaşan iki düğüm
        /// aynı anahtarı üretir ve <b>yanlış</b> değer döner.
        /// </remarks>
        private static ulong TranspositionKey(BackgammonState s, int d)
        {
            ulong dice = (ulong)s.remainingCount;
            for (int i = 0; i < s.remainingCount; i++)
            {
                dice = (dice * 7UL) + s.remainingDice[i];
            }

            return s.hash
                   ^ ((ulong)(uint)d * 0x9E3779B97F4A7C15UL)
                   ^ (dice * 0xC2B2AE3D27D4EB4FUL);
        }
    }
}