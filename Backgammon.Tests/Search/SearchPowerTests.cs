using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 6 Aşama E testleri için <see cref="HashEvaluator"/> + <see cref="HashPolicyEvaluator"/>'ı
    /// tek nesnede birleştiren sahte değerlendirici (<see cref="BearoffAwareEvaluator"/> iç
    /// değerlendiricisi <see cref="IPolicyValueEvaluator"/> ister).
    /// </summary>
    internal sealed class HashPolicyValueEvaluator : IPolicyValueEvaluator
    {
        private readonly HashEvaluator _value = new HashEvaluator();
        private readonly HashPolicyEvaluator _policy = new HashPolicyEvaluator();

        public int Version
        {
            get { return _value.Version; }
        }

        public void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                                  in VectorizerScalars scalars, Span<float> results)
        {
            _value.EvaluateBatch(list, offset, count, perspective, scalars, results);
        }

        public void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                               in VectorizerScalars scalars, Span<float> priorities)
        {
            _policy.ScoreBatch(list, offset, count, perspective, scalars, priorities);
        }
    }

    /// <summary>
    /// Faz 6 v3 §12.5 — Aşama E: arama gücü (Test 75–82).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Değişmez kural (v3 §9.5):</b> her optimizasyon <c>Reference(depth)</c> ile <b>birebir aynı</b>
    /// sonucu vermelidir. Fark varsa bu optimizasyon değil <b>hatadır</b>.
    /// </para>
    /// <para>
    /// <b>TT tasarım kararı:</b> yalnızca <b>tam pencerede</b> ve kesme yapılmadan hesaplanmış
    /// (EXACT) değerler saklanır ve yalnızca EXACT isabetler kullanılır. LOWER/UPPER bayrakları
    /// biçim olarak ayrılmıştır ama bu motorda <b>kesme için kullanılmaz</b>: chance katmanı
    /// ağırlıklı ortalama aldığı için sınır değerlerin yukarı propagasyonu güvenli değildir
    /// (ASSUMPTIONS F6-24).
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class SearchPowerTests
    {
        private static readonly EngineSettings Es = EngineSettings.Default;

        private static string _bearoffPath = null!;
        private static BearoffDatabase _database = null!;

        [OneTimeSetUp]
        public void OneTimeSetUp()
        {
            _bearoffPath = Path.Combine(TestContext.CurrentContext.TestDirectory, "bearoff_stage_e_v1.bin");
            BearoffGenerator.Result result = BearoffGenerator.Generate(12);
            BearoffGenerator.Write(_bearoffPath, result);
            _database = BearoffDatabase.Open(_bearoffPath);
        }

        [OneTimeTearDown]
        public void OneTimeTearDown()
        {
            _database?.Dispose();
            _database = null!;

            if (File.Exists(_bearoffPath))
            {
                File.Delete(_bearoffPath);
            }
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static SearchSettings Make(int depth, bool ab, bool star1, bool cache, bool policyOrder,
                                           int maxRoot = 0, int maxInner = 0, bool exact = true,
                                           int ttCapacity = 0, bool bearoffCutoff = false)
        {
            return new SearchSettings
            {
                DepthPly = depth,
                MaxCandidatesRoot = maxRoot,
                MaxCandidatesInner = maxInner,
                UseAlphaBeta = ab,
                UseStar1 = star1,
                UseEvalCache = cache,
                UsePolicyOrdering = policyOrder,
                ExactRootScores = exact,
                PolicyTemperature = 1f,
                TranspositionCapacity = ttCapacity,
                UseBearoffCutoff = bearoffCutoff
            };
        }

        /// <summary>Sabit + rastgele pozisyonlar (Faz 3 testleriyle aynı kaynak).</summary>
        private static List<BackgammonState> BuildPositionSet(IRandom rng, int count)
        {
            var list = new List<BackgammonState>
            {
                SearchTestSupport.Starting(3, 1),
                SearchTestSupport.Starting(6, 6),
                SearchTestSupport.Starting(1, 2),
                SearchTestSupport.MidGame(3, 5),
                SearchTestSupport.MidGame(1, 1),
                SearchTestSupport.MidGame(6, 2),
                SearchTestSupport.WhiteOnBar(2, 5),
                SearchTestSupport.BlackOnBar(2, 5),
                SearchTestSupport.WhiteOnBar(6, 6),
                SearchTestSupport.BlackOnBar(1, 3),
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.BearOff(6, 6),
                SearchTestSupport.BearOff(1, 1),
                SearchTestSupport.SingleCheckerEndgame(3, 1),
                SearchTestSupport.SingleCheckerEndgame(6, 6),
                SearchTestSupport.BothBarBlocked(3, 4)
            };

            while (list.Count < count)
            {
                int d1 = 1 + (int)(rng.NextUInt() % 6u);
                int d2 = 1 + (int)(rng.NextUInt() % 6u);
                var s = SearchTestSupport.RandomPosition(rng, d1, d2);
                if (s.whiteBorneOff >= 15 || s.blackBorneOff >= 15)
                {
                    continue;
                }

                list.Add(s);
            }

            return list;
        }

        /// <summary>Küçük, hızlı bitiş pozisyonları (depth 2 için).</summary>
        private static List<BackgammonState> BuildEndgameSet(IRandom rng, int count)
        {
            var list = new List<BackgammonState>
            {
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.BearOff(6, 6),
                SearchTestSupport.BearOff(1, 1),
                SearchTestSupport.SingleCheckerEndgame(3, 1),
                SearchTestSupport.SingleCheckerEndgame(6, 6)
            };

            while (list.Count < count)
            {
                list.Add(SearchTestSupport.BearOff(1 + (int)(rng.NextUInt() % 6u),
                                                   1 + (int)(rng.NextUInt() % 6u)));
            }

            return list;
        }

        /// <summary>Saf yarış (temas yok) pozisyonları — bearoff kesme için.</summary>
        private static List<BackgammonState> BuildPureRaceSet(IRandom rng, int count)
        {
            var list = new List<BackgammonState>
            {
                SearchTestSupport.BearOff(2, 5),
                SearchTestSupport.BearOff(6, 6),
                SearchTestSupport.BearOff(1, 1),
                SearchTestSupport.BearOff(3, 4)
            };

            while (list.Count < count)
            {
                var s = SearchTestSupport.Blank(1);

                // Beyaz 19..24, Siyah 1..6 — hiç temas yok, iki taraf da tek taraflı bearoff.
                int whiteLeft = 15;
                for (int p = 19; p <= 24 && whiteLeft > 0; p++)
                {
                    int n = Math.Min(whiteLeft, 1 + (int)(rng.NextUInt() % 4u));
                    s.board[p] = (sbyte)n;
                    whiteLeft -= n;
                }

                s.board[24] += (sbyte)whiteLeft;

                int blackLeft = 15;
                for (int p = 1; p <= 6 && blackLeft > 0; p++)
                {
                    int n = Math.Min(blackLeft, 1 + (int)(rng.NextUInt() % 4u));
                    s.board[p] = (sbyte)(-n);
                    blackLeft -= n;
                }

                s.board[1] -= (sbyte)blackLeft;

                s.hash = BackgammonEngine.ComputeZobristHash(s);
                list.Add(SearchTestSupport.WithDice(s, 1 + (int)(rng.NextUInt() % 6u),
                                                       1 + (int)(rng.NextUInt() % 6u)));
            }

            return list;
        }

        private static string SequenceKey(in MoveSequence seq)
        {
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < seq.Count; i++)
            {
                sb.Append(seq[i].From).Append('>').Append(seq[i].To).Append(';');
            }

            return sb.ToString();
        }

        // ==================================================================
        // Test 75 — TT varsayılan olarak KAPALI; Faz 5 davranışı birebir
        // ==================================================================

        [Test]
        public void Test75_Transposition_IsDisabledByDefault()
        {
            SearchSettings d = SearchSettings.Default;
            Assert.That(d.TranspositionCapacity, Is.EqualTo(0), "TranspositionCapacity varsayılanı 0 olmalı");
            Assert.That(d.UseBearoffCutoff, Is.False, "UseBearoffCutoff varsayılanı false olmalı");

            SearchSettings r = SearchSettings.Reference(2);
            Assert.That(r.TranspositionCapacity, Is.EqualTo(0), "Reference TT kapalı olmalı");
            Assert.That(r.UseBearoffCutoff, Is.False, "Reference bearoff kesmesi kapalı olmalı");

            var rng = new Xoshiro256StarStar(0x5EEDE0UL);
            var positions = BuildPositionSet(rng, 24);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var ws = new SearchWorkspace(16);
            var withDefault = Make(1, true, true, true, true, exact: true);
            var withExplicitZero = Make(1, true, true, true, true, exact: true, ttCapacity: 0);

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var a = BackgammonSearch.Search(positions[i], withDefault, Es, ws, value, policy);

                ws.Reset();
                var b = BackgammonSearch.Search(positions[i], withExplicitZero, Es, ws, value, policy);

                Assert.That(b.EvaluationScore, Is.EqualTo(a.EvaluationScore).Within(SearchTestSupport.Tolerance),
                    "TT kapaliyken deger degismemeli (#" + i + ")");
                Assert.That(SequenceKey(b.BestSequence), Is.EqualTo(SequenceKey(a.BestSequence)),
                    "TT kapaliyken hamle degismemeli (#" + i + ")");
                Assert.That(b.TranspositionHits, Is.EqualTo(0), "TT kapaliyken isabet olmamali");
                Assert.That(b.TranspositionStores, Is.EqualTo(0), "TT kapaliyken yazma olmamali");
            }

            Assert.That(ws.TranspositionCapacity, Is.EqualTo(0), "TT kapaliyken ayrilmis kapasite 0 olmali");
        }

        // ==================================================================
        // Test 76 — TT deterministik
        // ==================================================================

        [Test]
        public void Test76_Transposition_IsDeterministic()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE1UL);
            var positions = BuildPositionSet(rng, 20);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var settings = Make(2, true, true, true, true, maxRoot: 4, maxInner: 4, exact: true,
                                ttCapacity: 1 << 12);

            // (a) Aynı workspace, art arda iki kez (TT ikinci turda dolu).
            var ws = new SearchWorkspace(16);
            var first = new float[positions.Count];
            var firstSeq = new string[positions.Count];

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var r = BackgammonSearch.Search(positions[i], settings, Es, ws, value, policy);
                first[i] = r.EvaluationScore;
                firstSeq[i] = SequenceKey(r.BestSequence);
            }

            for (int i = 0; i < positions.Count; i++)
            {
                var r = BackgammonSearch.Search(positions[i], settings, Es, ws, value, policy);
                Assert.That(r.EvaluationScore, Is.EqualTo(first[i]).Within(SearchTestSupport.Tolerance),
                    "TT dolu iken deger degismemeli (#" + i + ")");
                Assert.That(SequenceKey(r.BestSequence), Is.EqualTo(firstSeq[i]),
                    "TT dolu iken hamle degismemeli (#" + i + ")");
            }

            // (b) Taze workspace (TT boş) — aynı sonuç.
            var ws2 = new SearchWorkspace(16);
            for (int i = 0; i < positions.Count; i++)
            {
                ws2.Reset();
                var r = BackgammonSearch.Search(positions[i], settings, Es, ws2, value, policy);
                Assert.That(r.EvaluationScore, Is.EqualTo(first[i]).Within(SearchTestSupport.Tolerance),
                    "Taze TT ayni degeri vermeli (#" + i + ")");
                Assert.That(SequenceKey(r.BestSequence), Is.EqualTo(firstSeq[i]),
                    "Taze TT ayni hamleyi vermeli (#" + i + ")");
            }

            // (c) TT gerçekten kullanıldı mı?
            long hits = 0;
            for (int i = 0; i < positions.Count; i++)
            {
                var r = BackgammonSearch.Search(positions[i], settings, Es, ws, value, policy);
                hits += r.TranspositionHits;
            }

            TestContext.Progress.WriteLine("Test 76 | TT isabet (3. tur) = " + hits);
            Assert.That(hits, Is.GreaterThan(0), "TT en az bir isabet uretmeli (aksi halde test anlamsiz)");
        }

        // ==================================================================
        // Test 77 — Bearoff kesmesi düğüm sayısını düşürür, sonucu değiştirmez
        // ==================================================================

        [Test]
        public void Test77_BearoffCutoff_ReducesNodes()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE2UL);
            var positions = BuildPureRaceSet(rng, 12);

            var inner = new HashPolicyValueEvaluator();
            var bearoff = new BearoffAwareEvaluator(inner, _database, BearoffAwareOptions.Default);
            var policy = new HashPolicyEvaluator();

            var ws = new SearchWorkspace(16);

            var noCut = Make(1, true, true, true, true, maxRoot: 0, maxInner: 0, exact: true,
                             ttCapacity: 0, bearoffCutoff: false);
            var cut = Make(1, true, true, true, true, maxRoot: 0, maxInner: 0, exact: true,
                           ttCapacity: 0, bearoffCutoff: true);

            long nodesNoCut = 0;
            long nodesCut = 0;
            int compared = 0;

            for (int i = 0; i < positions.Count; i++)
            {
                if (!BearoffAwareEvaluator.IsSolvable(positions[i].board))
                {
                    continue;
                }

                ws.Reset();
                var a = BackgammonSearch.Search(positions[i], noCut, Es, ws, bearoff, policy);

                ws.Reset();
                var b = BackgammonSearch.Search(positions[i], cut, Es, ws, bearoff, policy);

                nodesNoCut += a.NodesVisited;
                nodesCut += b.NodesVisited;
                compared++;

                Assert.That(b.EvaluationScore, Is.EqualTo(a.EvaluationScore).Within(SearchTestSupport.Tolerance),
                    "bearoff kesmesi degeri degistirmemeli (#" + i + ")");
                Assert.That(SequenceKey(b.BestSequence), Is.EqualTo(SequenceKey(a.BestSequence)),
                    "bearoff kesmesi hamleyi degistirmemeli (#" + i + ")");
            }

            TestContext.Progress.WriteLine("Test 77 | pozisyon=" + compared +
                                           " | dugum (kesme yok)=" + nodesNoCut +
                                           " | dugum (kesme)=" + nodesCut);

            Assert.That(compared, Is.GreaterThan(0), "en az bir saf bearoff pozisyonu gerekli");
            Assert.That(nodesCut, Is.LessThan(nodesNoCut / 2),
                "bearoff kesmesi dugum sayisini en az yariya indirmeli");
        }

        // ==================================================================
        // Test 78 — TT + aday kısıtı, Reference(depth) ile birebir aynı
        // ==================================================================

        [Test]
        public void Test78_Optimizations_MatchReference()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE3UL);
            var positions = BuildPositionSet(rng, 16);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();
            var reference = new ReferenceSearch();

            var ws = new SearchWorkspace(16);

            // (a) TT açık, aday kısıtı yok → Reference(depth) ile aynı.
            var ttOnly = Make(2, true, true, false, true, exact: true, ttCapacity: 1 << 12);
            var refNoRestrict = Make(2, false, false, false, true, exact: true);

            // (b) TT + aday kısıtı 4/4 → Reference(depth) (aynı kısıtla) ile aynı.
            var ttRestricted = Make(2, true, true, false, true, maxRoot: 4, maxInner: 4, exact: true,
                                    ttCapacity: 1 << 12);
            var refRestricted = Make(2, false, false, false, true, maxRoot: 4, maxInner: 4, exact: true);

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var a = BackgammonSearch.Search(positions[i], ttOnly, Es, ws, value, policy);
                float ra = reference.RootValue(positions[i], refNoRestrict, Es, value, policy, out var seqA);

                Assert.That(a.EvaluationScore, Is.EqualTo(ra).Within(SearchTestSupport.Tolerance),
                    "TT referansla ayni degeri vermeli (#" + i + ")");
                Assert.That(SequenceKey(a.BestSequence), Is.EqualTo(SequenceKey(seqA)),
                    "TT referansla ayni hamleyi vermeli (#" + i + ")");

                ws.Reset();
                var b = BackgammonSearch.Search(positions[i], ttRestricted, Es, ws, value, policy);
                float rb = reference.RootValue(positions[i], refRestricted, Es, value, policy, out var seqB);

                Assert.That(b.EvaluationScore, Is.EqualTo(rb).Within(SearchTestSupport.Tolerance),
                    "TT + aday kisiti referansla ayni degeri vermeli (#" + i + ")");
                Assert.That(SequenceKey(b.BestSequence), Is.EqualTo(SequenceKey(seqB)),
                    "TT + aday kisiti referansla ayni hamleyi vermeli (#" + i + ")");
            }

            // (c) Bearoff kesmesi: saf yarışta kesin değer = Reference(0) değeri.
            var bearoff = new BearoffAwareEvaluator(new HashPolicyValueEvaluator(), _database,
                                                    BearoffAwareOptions.Default);
            var race = BuildPureRaceSet(rng, 8);
            var cut = Make(1, true, true, false, true, maxRoot: 0, maxInner: 0, exact: true,
                           ttCapacity: 0, bearoffCutoff: true);
            var refZero = Make(0, false, false, false, true, exact: true);

            int raceCompared = 0;
            for (int i = 0; i < race.Count; i++)
            {
                if (!BearoffAwareEvaluator.IsSolvable(race[i].board))
                {
                    continue;
                }

                ws.Reset();
                var c = BackgammonSearch.Search(race[i], cut, Es, ws, bearoff, policy);
                float rz = reference.RootValue(race[i], refZero, Es, bearoff, policy, out var seqZ);

                Assert.That(c.EvaluationScore, Is.EqualTo(rz).Within(SearchTestSupport.Tolerance),
                    "bearoff kesmesi kesin degerle ayni olmali (#" + i + ")");
                Assert.That(SequenceKey(c.BestSequence), Is.EqualTo(SequenceKey(seqZ)),
                    "bearoff kesmesi ayni hamleyi secmeli (#" + i + ")");
                raceCompared++;
            }

            Assert.That(raceCompared, Is.GreaterThan(0), "en az bir saf bearoff pozisyonu gerekli");
        }

        // ==================================================================
        // Test 79 — Depth 2 yeterince hızlı (p95 ≤ 2 s/karar)
        // ==================================================================

        [Test]
        public void Test79_Depth2_IsFastEnough()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE4UL);
            var positions = BuildPositionSet(rng, 30);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var ws = new SearchWorkspace(20);
            var settings = Make(2, true, true, true, true, maxRoot: 4, maxInner: 4, exact: true,
                                ttCapacity: 1 << 20);

            // Isınma (JIT + TT ayırma).
            for (int i = 0; i < 4; i++)
            {
                ws.Reset();
                BackgammonSearch.Search(positions[i], settings, Es, ws, value, policy);
            }

            var samples = new double[positions.Count];
            var sw = new Stopwatch();

            for (int i = 0; i < positions.Count; i++)
            {
                sw.Restart();
                BackgammonSearch.Search(positions[i], settings, Es, ws, value, policy);
                sw.Stop();
                samples[i] = sw.Elapsed.TotalSeconds;
            }

            Array.Sort(samples);
            double p50 = samples[(int)(samples.Length * 0.50)];
            double p95 = samples[Math.Min(samples.Length - 1, (int)Math.Ceiling(samples.Length * 0.95) - 1)];
            double mean = samples.Average();

            // Ortalama oyun süresi: ~27 karar/oyun (v3 §9.5).
            double gameSeconds = mean * 27.0;

            TestContext.Progress.WriteLine("Test 79 | depth 2, aday 4/4, TT 2^20 | p50=" +
                                           p50.ToString("F4") + " s | p95=" + p95.ToString("F4") +
                                           " s | ortalama=" + mean.ToString("F4") +
                                           " s/karar | tahmini oyun=" + gameSeconds.ToString("F2") + " s");

            Assert.That(p95, Is.LessThanOrEqualTo(2.0), "p95 karar suresi 2 s'yi asmamali");
            Assert.That(p50, Is.LessThanOrEqualTo(0.15), "p50 karar suresi 0,15 s'yi asmamali");
        }

        // ==================================================================
        // Test 80 — TT açıkken ısınma sonrası sıfır allocation
        // ==================================================================

        [Test]
        public void Test80_Search_ZeroAllocation_WithTT()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE5UL);
            var positions = BuildPositionSet(rng, 200);
            var endgames = BuildEndgameSet(rng, 20);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var ws = new SearchWorkspace(16);
            var settings = new[]
            {
                Make(0, true, true, true, true, exact: true, ttCapacity: 1 << 12),
                Make(1, true, true, true, true, exact: true, ttCapacity: 1 << 12),
                Make(2, true, true, true, true, maxRoot: 4, maxInner: 4, exact: true, ttCapacity: 1 << 12)
            };

            // Isınma: TT dizileri burada ayrılır.
            for (int c = 0; c < settings.Length; c++)
            {
                ws.Reset();
                BackgammonSearch.Search(positions[0], settings[c], Es, ws, value, policy);
            }

            long before = GC.GetAllocatedBytesForCurrentThread();

            for (int i = 0; i < positions.Count; i++)
            {
                for (int c = 0; c < 2; c++)
                {
                    ws.Reset();
                    BackgammonSearch.Search(positions[i], settings[c], Es, ws, value, policy);
                }
            }

            for (int i = 0; i < endgames.Count; i++)
            {
                ws.Reset();
                BackgammonSearch.Search(endgames[i], settings[2], Es, ws, value, policy);
            }

            long after = GC.GetAllocatedBytesForCurrentThread();
            TestContext.Progress.WriteLine("Test 80 | TT acik allocation = " + (after - before) + " bayt");
            Assert.That(after - before, Is.EqualTo(0), "TT acikken arama isinma sonrasi sifir allocation yapmali");
        }

        // ==================================================================
        // Test 81 — Faz 3 arama testleri değişmedi
        // ==================================================================

        [Test]
        public void Test81_Search_ExistingTestsUnchanged()
        {
            // (a) Faz 3 test fikstürü aynı sayıda test içermeli (39).
            MethodInfo[] methods = typeof(SearchTests).GetMethods(BindingFlags.Public | BindingFlags.Instance);
            int testCount = methods.Count(m => m.GetCustomAttributes(typeof(NUnit.Framework.TestAttribute), true).Length > 0);

            TestContext.Progress.WriteLine("Test 81 | SearchTests test sayisi = " + testCount);
            Assert.That(testCount, Is.EqualTo(39), "Faz 3 arama testleri degismemeli (39 test)");

            // (b) SearchSettings.Default Faz 3 değerlerini birebir korumalı.
            SearchSettings d = SearchSettings.Default;
            Assert.That(d.DepthPly, Is.EqualTo(1));
            Assert.That(d.MaxCandidatesRoot, Is.EqualTo(0));
            Assert.That(d.MaxCandidatesInner, Is.EqualTo(0));
            Assert.That(d.UseAlphaBeta, Is.True);
            Assert.That(d.UseStar1, Is.True);
            Assert.That(d.UseEvalCache, Is.True);
            Assert.That(d.UsePolicyOrdering, Is.True);
            Assert.That(d.ExactRootScores, Is.False);
            Assert.That(d.PolicyTemperature, Is.EqualTo(1.0f));

            // (c) Reference(depth) Faz 3 sözleşmesini korumalı.
            for (int depth = 0; depth <= 2; depth++)
            {
                SearchSettings r = SearchSettings.Reference(depth);
                Assert.That(r.DepthPly, Is.EqualTo(depth));
                Assert.That(r.MaxCandidatesRoot, Is.EqualTo(0));
                Assert.That(r.MaxCandidatesInner, Is.EqualTo(0));
                Assert.That(r.UseAlphaBeta, Is.False);
                Assert.That(r.UseStar1, Is.False);
                Assert.That(r.UseEvalCache, Is.False);
                Assert.That(r.UsePolicyOrdering, Is.False);
                Assert.That(r.ExactRootScores, Is.True);
                Assert.That(r.TranspositionCapacity, Is.EqualTo(0));
                Assert.That(r.UseBearoffCutoff, Is.False);
            }

            // (d) Referans eşitliği hâlâ geçerli (Faz 3 Test 1'in özü).
            var rng = new Xoshiro256StarStar(0x5EEDE6UL);
            var positions = BuildPositionSet(rng, 8);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();
            var reference = new ReferenceSearch();
            var ws = new SearchWorkspace(16);

            for (int i = 0; i < positions.Count; i++)
            {
                ws.Reset();
                var a = BackgammonSearch.Search(positions[i], SearchSettings.Reference(1), Es, ws, value, policy);
                float ra = reference.RootValue(positions[i], SearchSettings.Reference(1), Es, value, policy, out var seq);

                Assert.That(a.EvaluationScore, Is.EqualTo(ra).Within(SearchTestSupport.Tolerance),
                    "Faz 3 referans esitligi korunmali (#" + i + ")");
                Assert.That(SequenceKey(a.BestSequence), Is.EqualTo(SequenceKey(seq)),
                    "Faz 3 referans hamlesi korunmali (#" + i + ")");
            }
        }

        // ==================================================================
        // Test 82 — Eval cache / TT ablasyonu
        // ==================================================================

        [Test]
        public void Test82_EvalCache_TT_Ablation()
        {
            var rng = new Xoshiro256StarStar(0x5EEDE7UL);
            var positions = BuildPositionSet(rng, 24);
            var value = new HashEvaluator();
            var policy = new HashPolicyEvaluator();

            var ws = new SearchWorkspace(20);

            var configs = new[]
            {
                ("cache acik, TT kapali", Make(2, true, true, true, true, maxRoot: 4, maxInner: 4, exact: true, ttCapacity: 0)),
                ("ikisi de acik", Make(2, true, true, true, true, maxRoot: 4, maxInner: 4, exact: true, ttCapacity: 1 << 16)),
                ("cache kapali, TT acik", Make(2, true, true, false, true, maxRoot: 4, maxInner: 4, exact: true, ttCapacity: 1 << 16))
            };

            var scores = new float[configs.Length][];
            var calls = new long[configs.Length];
            var nodes = new long[configs.Length];
            var hits = new long[configs.Length];
            var seconds = new double[configs.Length];

            for (int c = 0; c < configs.Length; c++)
            {
                scores[c] = new float[positions.Count];

                // Gerçek kullanım: workspace kararlar arasında YAŞAR (SelfPlayAgent), yalnızca
                // model yeniden yüklenince Reset() çağrılır. Isınma + tek Reset.
                ws.Reset();
                BackgammonSearch.Search(positions[0], configs[c].Item2, Es, ws, value, policy);

                var sw = Stopwatch.StartNew();
                for (int i = 0; i < positions.Count; i++)
                {
                    var r = BackgammonSearch.Search(positions[i], configs[c].Item2, Es, ws, value, policy);
                    scores[c][i] = r.EvaluationScore;
                    calls[c] += r.EvaluatorCalls;
                    nodes[c] += r.NodesVisited;
                    hits[c] += r.TranspositionHits;
                }

                sw.Stop();
                seconds[c] = sw.Elapsed.TotalSeconds;
            }

            for (int c = 0; c < configs.Length; c++)
            {
                TestContext.Progress.WriteLine("Test 82 | " + configs[c].Item1 +
                                               " | degerlendirici=" + calls[c] +
                                               " | dugum=" + nodes[c] +
                                               " | TT isabet=" + hits[c] +
                                               " | sure=" + seconds[c].ToString("F3") + " s");
            }

            // Tüm konfigürasyonlar aynı değeri vermeli (optimizasyon değeri değiştirmez).
            for (int c = 1; c < configs.Length; c++)
            {
                for (int i = 0; i < positions.Count; i++)
                {
                    Assert.That(scores[c][i], Is.EqualTo(scores[0][i]).Within(SearchTestSupport.Tolerance),
                        configs[c].Item1 + " degeri degistirmemeli (#" + i + ")");
                }
            }

            // Ablasyon kararı: TT, cache'e göre ölçülebilir kazanç sağlıyor mu?
            double cacheOnly = seconds[0];
            double both = seconds[1];
            double ttOnly = seconds[2];
            double speedup = cacheOnly / Math.Max(both, 1e-9);

            TestContext.Progress.WriteLine("Test 82 | karar | cache/TT kapali hizlanma = " +
                                           speedup.ToString("F3") + "x | cache kapali/TT acik = " +
                                           (cacheOnly / Math.Max(ttOnly, 1e-9)).ToString("F3") + "x");

            // Karar kaydedilir; kapı değildir (v3 §9.5: "kazanç yoksa sadeleştirilir ve raporlanır").
            Assert.That(both, Is.GreaterThan(0), "olcum gecerli olmali");
        }
    }
}
