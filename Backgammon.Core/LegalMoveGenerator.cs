using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Yasal hamle üretici (arama ve filtre katmanı). Bölüm 5.
    /// </summary>
    /// <remarks>
    /// DFS ile <c>remainingDice</c> üzerinde dallanır; state kopyalanmaz
    /// (<see cref="BackgammonEngine.ApplyStep"/> → özyineleme → <see cref="BackgammonEngine.UndoStep"/>).
    /// Tek geçişlidir: DFS sırasında en uzun diziler <see cref="ThreadStaticAttribute"/> bir buffer'a
    /// toplanır (daha derin bir dizi bulunursa buffer sıfırlanır), ardından hash tabanlı tekilleştirme
    /// uygulanır. Buffer taşarsa davranış aynı kalmak üzere iki geçişli yola düşülür.
    /// Scratch buffer'lar <see cref="ThreadStaticAttribute"/>'tır: her thread kendi buffer'ını kullanır.
    /// </remarks>
    public static class LegalMoveGenerator
    {
        /// <summary>Bir zar için üretilebilecek en fazla adım (15 hane + bar).</summary>
        private const int MaxStepsPerDie = 24;

        private const int DedupBits = 14;
        private const int DedupSize = 1 << DedupBits;
        private const int DedupMask = DedupSize - 1;

        /// <summary>
        /// Tek geçişli toplama buffer'ı. Taşarsa iki geçişli güvenli yola düşülür
        /// (bkz. <see cref="GenerateAllLegalMoves"/>).
        /// </summary>
        private const int SeqBufCapacity = 1 << 16;

        [ThreadStatic] private static MoveStep[][] _stepBuf;
        [ThreadStatic] private static ulong[] _dedupHash;
        [ThreadStatic] private static int[] _dedupIndex;
        [ThreadStatic] private static int[] _dedupGen;
        [ThreadStatic] private static int _gen;
        [ThreadStatic] private static MoveList _scratchMoves;
        [ThreadStatic] private static MoveSequence[] _seqBuf;
        [ThreadStatic] private static ulong[] _seqHashBuf;
        [ThreadStatic] private static BackgammonState _probeState;

        // ------------------------------------------------------------------
        // Genel API
        // ------------------------------------------------------------------

        /// <summary>
        /// Giriş katmanı için: güncel durumda <paramref name="fromPoint"/> hanesinden
        /// oynanabilecek <b>ilk</b> adımlar. Maksimum uzunluk ve büyük zar kuralı uygulanır;
        /// tekilleştirme yapılmaz.
        /// </summary>
        /// <param name="s">Güncel durum.</param>
        /// <param name="maxLengthMoves">
        /// <paramref name="s"/> için <see cref="GenerateAllLegalMoves"/> ile üretilmiş liste.
        /// </param>
        /// <param name="fromPoint">Kaynak hane (bar için 0 / 25).</param>
        /// <param name="buffer">Çıktı tamponu.</param>
        /// <returns><paramref name="buffer"/> içine yazılan adım sayısı.</returns>
        /// <remarks>
        /// <para>
        /// <see cref="GenerateAllLegalMoves"/> yalnızca <b>maksimum uzunluktaki</b> dizileri ve
        /// aynı son duruma ulaşan dizilerden yalnızca birini üretir. Bu yüzden bazı <b>ilk</b>
        /// adımlar o listede hiç görünmez (örneğin 3-1'de <c>19 -&gt; 22</c>, çünkü
        /// <c>19 -&gt; 20 -&gt; 23</c> aynı son duruma ulaşır).
        /// </para>
        /// <para>
        /// Bu yüzden adımlar <b>güncel durumdan</b> üretilir
        /// (<see cref="GenerateStepsFrom"/>) ve ardından "bu adımdan sonra hâlâ
        /// <c>maxCount - 1</c> adım oynanabiliyor mu?" süzgecinden geçirilir. Böylece hem kapsam
        /// tam olur hem de bayraklar (<see cref="MoveFlags.Hit"/>, <see cref="MoveFlags.BearOff"/>)
        /// güncel duruma göre doğru kalır.
        /// </para>
        /// </remarks>
        public static int GenerateFirstSteps(
            BackgammonState s, MoveList maxLengthMoves, int fromPoint, MoveStep[] buffer)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (maxLengthMoves == null)
            {
                throw new ArgumentNullException(nameof(maxLengthMoves));
            }

            if (buffer == null)
            {
                throw new ArgumentNullException(nameof(buffer));
            }

            int n = GenerateStepsFrom(s, fromPoint, buffer);
            if (n == 0)
            {
                return 0;
            }

            int maxCount = maxLengthMoves.Count > 0 ? maxLengthMoves.Moves[0].Count : 0;
            if (maxCount == 0)
            {
                return 0;
            }

            int restrictDie = ResolveBigDieRestriction(s, maxCount);

            BackgammonState probe = ProbeState;
            int kept = 0;
            for (int i = 0; i < n; i++)
            {
                MoveStep step = buffer[i];

                if (restrictDie != 0 && step.Die != restrictDie)
                {
                    continue;
                }

                probe.CopyFrom(s);
                BackgammonEngine.ApplyStep(probe, step);
                int rest = MaxSequenceLength(probe, restrictDie, 1);

                if (1 + rest == maxCount)
                {
                    buffer[kept++] = step;
                }
            }

            return kept;
        }

        /// <summary>
        /// <paramref name="s"/> durumundan itibaren oynanabilecek en uzun adım dizisinin uzunluğu.
        /// <paramref name="restrictDie"/> sıfırdan farklıysa yalnızca o zar kullanılabilir.
        /// </summary>
        private static int MaxSequenceLength(BackgammonState s, int restrictDie, int depth)
        {
            if (s.remainingCount == 0 || depth > MoveSequence.MaxSteps)
            {
                return 0;
            }

            int best = 0;
            MoveStep[] buf = StepBuf[depth];
            byte prev = 0;

            for (int i = 0; i < s.remainingCount; i++)
            {
                byte die = s.remainingDice[i];

                if (i > 0 && die == prev)
                {
                    continue;
                }

                prev = die;

                if (restrictDie != 0 && die != restrictDie)
                {
                    continue;
                }

                int n = GenerateSteps(s, die, buf);
                for (int k = 0; k < n; k++)
                {
                    MoveStep step = buf[k];
                    BackgammonEngine.ApplyStep(s, step);
                    int len = 1 + MaxSequenceLength(s, restrictDie, depth + 1);
                    BackgammonEngine.UndoStep(s, step);

                    if (len > best)
                    {
                        best = len;
                    }
                }
            }

            return best;
        }

        /// <summary>
        /// Verilen durumda <paramref name="fromPoint"/> hanesinden <b>tek adımda</b> gidilebilen
        /// tüm adımları (kalan zarların her biri için) üretir. Tekilleştirme yapmaz.
        /// </summary>
        /// <returns><paramref name="buffer"/> içine yazılan adım sayısı.</returns>
        /// <remarks>
        /// <para>
        /// <see cref="GenerateAllLegalMoves"/> yalnızca <b>maksimum uzunluktaki</b> dizileri ve
        /// aynı son duruma ulaşan dizilerden yalnızca birini üretir. Bu yüzden bazı <b>ilk</b>
        /// adımlar o listede hiç görünmez. Giriş katmanı (seçili taşın hedefleri, tıklanan adımın
        /// bayrakları) bu yüzden adımları doğrudan <b>güncel durumdan</b> ister.
        /// </para>
        /// <para>
        /// Dönen adımların <see cref="MoveFlags.Hit"/>, <see cref="MoveFlags.BearOff"/> ve
        /// <see cref="MoveFlags.FromBar"/> bayrakları güncel duruma göredir; başka bir ara
        /// durumdan kopyalanmış bayat bayrak taşımazlar.
        /// </para>
        /// </remarks>
        public static int GenerateStepsFrom(BackgammonState s, int fromPoint, MoveStep[] buffer)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (buffer == null)
            {
                throw new ArgumentNullException(nameof(buffer));
            }

            int n = 0;
            MoveStep[] buf = StepBuf[0];
            for (int d = 0; d < s.remainingCount; d++)
            {
                int die = s.remainingDice[d];
                if (die <= 0)
                {
                    continue;
                }

                int count = GenerateSteps(s, die, buf);
                for (int i = 0; i < count; i++)
                {
                    if (buf[i].From != fromPoint)
                    {
                        continue;
                    }

                    if (n >= buffer.Length)
                    {
                        return n;
                    }

                    buffer[n++] = buf[i];
                }
            }

            return n;
        }

        /// <summary>
        /// Tüm yasal, tekilleştirilmiş hamleleri <paramref name="output"/> içine yazar.
        /// Boş çıktı = oynanabilir hamle yok (pas).
        /// </summary>
        public static void GenerateAllLegalMoves(BackgammonState s, MoveList output)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (output == null)
            {
                throw new ArgumentNullException(nameof(output));
            }

            output.Clear();

            if (s.remainingCount == 0)
            {
                return;
            }

            MoveSequence[] seqBuf = SeqBuf;
            ulong[] hashBuf = SeqHashBuf;

            int maxCount = 0;
            int count = 0;
            bool overflow = false;
            MoveSequence current = default(MoveSequence);

            Collect(s, 0, ref maxCount, ref current, seqBuf, hashBuf, ref count, ref overflow);

            if (maxCount == 0)
            {
                return;
            }

            int restrictDie = ResolveBigDieRestriction(s, maxCount);

            BeginDedup();

            if (overflow)
            {
                // Toplama buffer'ı taştı: iki geçişli güvenli yola dön (davranış aynı).
                current = default(MoveSequence);
                Emit(s, 0, maxCount, restrictDie, ref current, output);
                return;
            }

            for (int i = 0; i < count; i++)
            {
                MoveSequence seq = seqBuf[i];

                if (seq.Count != maxCount)
                {
                    continue;
                }

                // restrictDie yalnızca maxCount == 1 iken sıfırdan farklıdır.
                if (restrictDie != 0 && seq[0].Die != restrictDie)
                {
                    continue;
                }

                Record(hashBuf[i], ref seq, output);
            }
        }

        /// <summary>
        /// <see cref="GenerateAllLegalMoves"/> ile aynı tekilleştirilmiş küme ve sırada
        /// afterstate kayıtlarını üretir. Pas durumunda boş bırakır (çağıran
        /// <see cref="AfterStateList.AddPass"/> kullanır).
        /// </summary>
        public static void GenerateAfterStates(BackgammonState s, in EngineSettings es, AfterStateList output)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (output == null)
            {
                throw new ArgumentNullException(nameof(output));
            }

            output.Clear();

            MoveList moves = ScratchMoves;
            GenerateAllLegalMoves(s, moves);

            for (int i = 0; i < moves.Count; i++)
            {
                MoveSequence seq = moves.Moves[i];

                // ApplyMove/UndoMove yerine adım döngüsü: burada faz geçişi gerekmez
                // (IsTerminal borneOff'tan hesaplanır), böylece hamle başına IsGameOver atlanır.
                for (int k = 0; k < seq.Count; k++)
                {
                    BackgammonEngine.ApplyStep(s, seq[k]);
                }

                int index = output.Add(s, seq);

                if (output.IsTerminal[index])
                {
                    GameResult result;
                    BackgammonEngine.IsGameOver(s, es, out result);
                    output.ResultType[index] = (byte)result.ResultType;
                    output.ResultPoints[index] = (byte)result.Points;
                }

                for (int k = seq.Count - 1; k >= 0; k--)
                {
                    BackgammonEngine.UndoStep(s, seq[k]);
                }
            }
        }

        // ------------------------------------------------------------------
        // 1. geçiş: topla (maksimum adım sayısı + o uzunluktaki diziler)
        // ------------------------------------------------------------------

        /// <summary>
        /// DFS ile tüm dizileri gezer. Maksimum derinlik büyüdükçe daha önce toplananlar
        /// atılır (<c>count = 0</c>), böylece sonuçta yalnızca en uzun diziler kalır.
        /// Tekilleştirme burada yapılmaz; <see cref="Record"/> sonradan uygulanır.
        /// </summary>
        private static void Collect(
            BackgammonState s,
            int depth,
            ref int maxCount,
            ref MoveSequence current,
            MoveSequence[] seqBuf,
            ulong[] hashBuf,
            ref int count,
            ref bool overflow)
        {
            if (depth > maxCount)
            {
                maxCount = depth;
                count = 0;
            }

            bool extended = false;

            if (s.remainingCount > 0)
            {
                MoveStep[] buf = StepBuf[depth];
                byte prev = 0;

                for (int i = 0; i < s.remainingCount; i++)
                {
                    byte die = s.remainingDice[i];

                    if (i > 0 && die == prev)
                    {
                        continue;
                    }

                    prev = die;

                    int n = GenerateSteps(s, die, buf);
                    for (int k = 0; k < n; k++)
                    {
                        MoveStep step = buf[k];
                        BackgammonEngine.ApplyStep(s, step);
                        current.Add(step);
                        Collect(s, depth + 1, ref maxCount, ref current, seqBuf, hashBuf, ref count, ref overflow);
                        current.Count--;
                        BackgammonEngine.UndoStep(s, step);
                        extended = true;
                    }
                }
            }

            if (extended || depth != maxCount)
            {
                return;
            }

            if (count >= seqBuf.Length)
            {
                overflow = true;
                return;
            }

            seqBuf[count] = current;
            hashBuf[count] = s.hash;
            count++;
        }

        // ------------------------------------------------------------------
        // 2. geçiş: yalnızca maxCount uzunluğundaki dizileri yaz
        // ------------------------------------------------------------------

        private static void Emit(BackgammonState s, int depth, int maxCount, int restrictDie, ref MoveSequence current, MoveList output)
        {
            if (depth == maxCount)
            {
                Record(s.hash, ref current, output);
                return;
            }

            if (s.remainingCount == 0)
            {
                return;
            }

            MoveStep[] buf = StepBuf[depth];
            byte prev = 0;

            for (int i = 0; i < s.remainingCount; i++)
            {
                byte die = s.remainingDice[i];

                if (i > 0 && die == prev)
                {
                    continue;
                }

                prev = die;

                if (restrictDie != 0 && die != restrictDie)
                {
                    continue;
                }

                int n = GenerateSteps(s, die, buf);
                for (int k = 0; k < n; k++)
                {
                    MoveStep step = buf[k];
                    BackgammonEngine.ApplyStep(s, step);
                    current.Add(step);
                    Emit(s, depth + 1, maxCount, restrictDie, ref current, output);
                    current.Count--;
                    BackgammonEngine.UndoStep(s, step);
                }
            }
        }

        /// <summary>
        /// Bölüm 5.1 madde 2 (büyük zar kuralı): yalnızca tek zar oynanabiliyorsa büyük zar
        /// zorunludur. Büyük zar hiç oynanamıyorsa kısıtlama yoktur (küçük zar oynanır).
        /// </summary>
        private static int ResolveBigDieRestriction(BackgammonState s, int maxCount)
        {
            if (maxCount != 1 || s.remainingCount != 2)
            {
                return 0;
            }

            if (s.remainingDice[0] == s.remainingDice[1])
            {
                return 0;
            }

            int higher = s.remainingDice[1];
            return GenerateSteps(s, higher, StepBuf[0]) > 0 ? higher : 0;
        }

        // ------------------------------------------------------------------
        // Tek adım üretimi (Bölüm 5.2 / 5.3)
        // ------------------------------------------------------------------

        private static int GenerateSteps(BackgammonState s, int die, MoveStep[] buf)
        {
            int turn = s.turn;
            int n = 0;
            int bar = BackgammonEngine.BarIndex(turn);

            // Bar önceliği: barda taş varsa yalnızca giriş üretilir.
            if (s.board[bar] * turn > 0)
            {
                int entry = bar + die * turn;
                if (entry >= 1 && entry <= 24 && CanLand(s, entry, turn))
                {
                    MoveFlags flags = MoveFlags.FromBar;
                    if (IsBlot(s, entry, turn))
                    {
                        flags |= MoveFlags.Hit;
                    }

                    buf[n++] = new MoveStep((byte)bar, (byte)entry, (byte)die, flags);
                }

                return n;
            }

            bool bearOffMode = IsBearOffMode(s, turn);
            byte offTarget = (byte)(turn == 1 ? 25 : 0);

            for (int p = 1; p <= 24; p++)
            {
                if (s.board[p] * turn <= 0)
                {
                    continue;
                }

                if (bearOffMode)
                {
                    int dist = BackgammonEngine.DistanceToOff(p, turn);
                    if (dist <= die && (dist == die || !HasPieceFurtherBack(s, p, turn)))
                    {
                        buf[n++] = new MoveStep((byte)p, offTarget, (byte)die, MoveFlags.BearOff);
                        continue;
                    }
                }

                int to = p + die * turn;
                if (to >= 1 && to <= 24 && CanLand(s, to, turn))
                {
                    MoveFlags flags = 0;
                    if (IsBlot(s, to, turn))
                    {
                        flags = MoveFlags.Hit;
                    }

                    buf[n++] = new MoveStep((byte)p, (byte)to, (byte)die, flags);
                }
            }

            return n;
        }

        /// <summary>Hedef hane yasal mı? Rakibin ≥2 taşı varsa bloke.</summary>
        private static bool CanLand(BackgammonState s, int to, int turn)
        {
            int v = s.board[to];
            return turn == 1 ? v >= -1 : v <= 1;
        }

        /// <summary>Hedefte tam 1 rakip taşı var mı (vurulabilir blot)?</summary>
        private static bool IsBlot(BackgammonState s, int to, int turn)
        {
            return turn == 1 ? s.board[to] == -1 : s.board[to] == 1;
        }

        /// <summary>Toplama modu: bar boş ve ev dışında kendi taşı yok.</summary>
        private static bool IsBearOffMode(BackgammonState s, int turn)
        {
            if (s.board[BackgammonEngine.BarIndex(turn)] * turn > 0)
            {
                return false;
            }

            if (turn == 1)
            {
                for (int p = 1; p <= 18; p++)
                {
                    if (s.board[p] > 0)
                    {
                        return false;
                    }
                }
            }
            else
            {
                for (int p = 7; p <= 24; p++)
                {
                    if (s.board[p] < 0)
                    {
                        return false;
                    }
                }
            }

            return true;
        }

        /// <summary><paramref name="p"/>'den daha geride (çıkışa daha uzak) kendi taşı var mı?</summary>
        private static bool HasPieceFurtherBack(BackgammonState s, int p, int turn)
        {
            if (turn == 1)
            {
                for (int q = 1; q < p; q++)
                {
                    if (s.board[q] > 0)
                    {
                        return true;
                    }
                }
            }
            else
            {
                for (int q = p + 1; q <= 24; q++)
                {
                    if (s.board[q] < 0)
                    {
                        return true;
                    }
                }
            }

            return false;
        }

        // ------------------------------------------------------------------
        // Tekilleştirme (Bölüm 5.1 madde 3)
        // ------------------------------------------------------------------

        private static void BeginDedup()
        {
            if (_dedupGen == null)
            {
                _dedupGen = new int[DedupSize];
                _dedupHash = new ulong[DedupSize];
                _dedupIndex = new int[DedupSize];
                _gen = 0;
            }

            _gen++;
            if (_gen == 0)
            {
                Array.Clear(_dedupGen, 0, DedupSize);
                _gen = 1;
            }
        }

        private static void Record(ulong hash, ref MoveSequence seq, MoveList output)
        {
            int slot = (int)(hash & DedupMask);

            while (true)
            {
                if (_dedupGen[slot] != _gen)
                {
                    _dedupGen[slot] = _gen;
                    _dedupHash[slot] = hash;
                    output.Add(seq);
                    _dedupIndex[slot] = output.Count;
                    return;
                }

                if (_dedupHash[slot] == hash)
                {
                    int existing = _dedupIndex[slot] - 1;
                    if (IsCanonicallyBefore(seq, output.Moves[existing]))
                    {
                        output.Moves[existing] = seq;
                    }

                    return;
                }

                slot = (slot + 1) & DedupMask;
            }
        }

        /// <summary>
        /// Kanonik dizi seçimi: adımlar (From, To, Die) sözlük sırasına göre karşılaştırılır.
        /// Deterministik olduğu için aynı girdi her zaman aynı diziyi üretir.
        /// </summary>
        private static bool IsCanonicallyBefore(in MoveSequence a, in MoveSequence b)
        {
            int n = a.Count < b.Count ? a.Count : b.Count;

            for (int i = 0; i < n; i++)
            {
                MoveStep sa = a[i];
                MoveStep sb = b[i];

                if (sa.From != sb.From)
                {
                    return sa.From < sb.From;
                }

                if (sa.To != sb.To)
                {
                    return sa.To < sb.To;
                }

                if (sa.Die != sb.Die)
                {
                    return sa.Die < sb.Die;
                }
            }

            return a.Count < b.Count;
        }

        // ------------------------------------------------------------------
        // Scratch buffer'lar
        // ------------------------------------------------------------------

        private static MoveStep[][] StepBuf
        {
            get
            {
                if (_stepBuf == null)
                {
                    var buf = new MoveStep[MoveSequence.MaxSteps + 1][];
                    for (int i = 0; i < buf.Length; i++)
                    {
                        buf[i] = new MoveStep[MaxStepsPerDie];
                    }

                    _stepBuf = buf;
                }

                return _stepBuf;
            }
        }

        private static MoveList ScratchMoves
        {
            get
            {
                if (_scratchMoves == null)
                {
                    _scratchMoves = new MoveList();
                }

                return _scratchMoves;
            }
        }

        /// <summary>
        /// <see cref="GenerateFirstSteps"/> için kopya durum. Çağıranın durumu asla
        /// değiştirilmez.
        /// </summary>
        private static BackgammonState ProbeState
        {
            get
            {
                if (_probeState == null)
                {
                    _probeState = new BackgammonState();
                }

                return _probeState;
            }
        }

        private static MoveSequence[] SeqBuf
        {
            get
            {
                if (_seqBuf == null)
                {
                    _seqBuf = new MoveSequence[SeqBufCapacity];
                }

                return _seqBuf;
            }
        }

        private static ulong[] SeqHashBuf
        {
            get
            {
                if (_seqHashBuf == null)
                {
                    _seqHashBuf = new ulong[SeqBufCapacity];
                }

                return _seqHashBuf;
            }
        }
    }
}
