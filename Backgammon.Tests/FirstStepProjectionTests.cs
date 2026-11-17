using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// <see cref="LegalMoveGenerator.GenerateStepsFrom"/> ve
    /// <see cref="LegalMoveGenerator.GenerateFirstSteps"/> için bağımsız (kaba kuvvet) kıyaslama.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Giriş katmanı (seçili taşın hedefleri, tıklanan adımın bayrakları) adımları
    /// <see cref="LegalMoveGenerator.GenerateAllLegalMoves"/> çıktısından <b>kopyalayamaz</b>:
    /// üretici aynı son duruma ulaşan dizileri tekilleştirdiği için bir dizinin <c>k &gt; 0</c>
    /// adımı başka bir ara duruma aittir. O adımın bayrakları (özellikle
    /// <see cref="MoveFlags.Hit"/>) güncel duruma göre bayat olabilir ve uygulandığında taş
    /// silebilir.
    /// </para>
    /// <para>
    /// Buradaki beklenti kümesi tamamen bağımsız bir kaba kuvvet aramasıyla kurulur: tüm adım
    /// dizileri numaralandırılır, en uzun uzunluk bulunur ve o uzunluktaki dizilerin ilk adımları
    /// toplanır.
    /// </para>
    /// </remarks>
    [TestFixture]
    public class FirstStepProjectionTests
    {
        // ------------------------------------------------------------------
        // Bağımsız kaba kuvvet oracle
        // ------------------------------------------------------------------

        /// <summary>
        /// <paramref name="s"/> durumundan oynanabilecek en uzun adım dizisinin uzunluğu.
        /// </summary>
        private static int BruteForceMaxLength(BackgammonState s)
        {
            if (s.remainingCount == 0)
            {
                return 0;
            }

            int best = 0;
            byte prev = 0;

            for (int i = 0; i < s.remainingCount; i++)
            {
                byte die = s.remainingDice[i];
                if (i > 0 && die == prev)
                {
                    continue;
                }

                prev = die;

                foreach (MoveStep step in AllStepsForDie(s, die))
                {
                    BackgammonEngine.ApplyStep(s, step);
                    int len = 1 + BruteForceMaxLength(s);
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
        /// <paramref name="die"/> zarıyla güncel durumda oynanabilecek tüm tek adımlar.
        /// </summary>
        private static List<MoveStep> AllStepsForDie(BackgammonState s, int die)
        {
            var result = new List<MoveStep>();
            var buf = new MoveStep[64];

            for (int from = 0; from <= 25; from++)
            {
                int n = LegalMoveGenerator.GenerateStepsFrom(s, from, buf);
                for (int i = 0; i < n; i++)
                {
                    if (buf[i].Die == die)
                    {
                        result.Add(buf[i]);
                    }
                }
            }

            return result;
        }

        /// <summary>
        /// Bağımsız beklenti: güncel durumda <paramref name="fromPoint"/> hanesinden oynanabilen ve
        /// en uzun dizinin başında yer alan adımların hedefleri.
        /// </summary>
        private static SortedSet<int> BruteForceFirstTargets(BackgammonState s, int fromPoint)
        {
            var targets = new SortedSet<int>();
            int maxLength = BruteForceMaxLength(s);
            if (maxLength == 0)
            {
                return targets;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            foreach (MoveStep step in AllStepsForDie(s, 0))
            {
                _ = step;
            }

            for (int i = 0; i < s.remainingCount; i++)
            {
                foreach (MoveStep step in AllStepsForDie(s, s.remainingDice[i]))
                {
                    if (step.From != fromPoint)
                    {
                        continue;
                    }

                    BackgammonEngine.ApplyStep(s, step);
                    int rest = BruteForceMaxLength(s);
                    BackgammonEngine.UndoStep(s, step);

                    if (1 + rest == maxLength)
                    {
                        targets.Add(step.To);
                    }
                }
            }

            return targets;
        }

        // ------------------------------------------------------------------
        // Testler
        // ------------------------------------------------------------------

        [Test]
        public void StepsFrom_EmptyPoint_YieldsNothing()
        {
            BackgammonState s = InitialState();
            BackgammonEngine.SetDice(s, 3, 1);

            var buf = new MoveStep[32];
            for (int p = 0; p <= 25; p++)
            {
                bool owns = s.board[p] * s.turn > 0;
                int n = LegalMoveGenerator.GenerateStepsFrom(s, p, buf);
                if (!owns)
                {
                    Assert.That(n, Is.EqualTo(0), "bos hane " + p + " adim uretmemeli");
                }
            }
        }

        [Test]
        public void StepsFrom_EveryStepIsApplicableAndConservesCheckers()
        {
            List<BackgammonState> positions = RandomPositions(40, 0x5EED_00A1UL);
            var buf = new MoveStep[32];

            foreach (BackgammonState state in positions)
            {
                for (int from = 0; from <= 25; from++)
                {
                    int n = LegalMoveGenerator.GenerateStepsFrom(state, from, buf);
                    for (int i = 0; i < n; i++)
                    {
                        MoveStep step = buf[i];

                        var probe = new BackgammonState();
                        probe.CopyFrom(state);
                        BackgammonEngine.ApplyStep(probe, step);

                        Assert.That(
                            CountPieces(probe, 1), Is.EqualTo(15),
                            "beyaz tas sayisi korunmadi: " + step);
                        Assert.That(
                            CountPieces(probe, -1), Is.EqualTo(15),
                            "siyah tas sayisi korunmadi: " + step);
                    }
                }
            }
        }

        [Test]
        public void FirstSteps_MatchBruteForceOracle()
        {
            List<BackgammonState> positions = RandomPositions(25, 0x5EED_00A2UL);
            var moves = new MoveList();
            var buf = new MoveStep[32];

            foreach (BackgammonState state in positions)
            {
                LegalMoveGenerator.GenerateAllLegalMoves(state, moves);

                for (int from = 0; from <= 25; from++)
                {
                    SortedSet<int> expected = BruteForceFirstTargets(state, from);

                    var actual = new SortedSet<int>();
                    int n = LegalMoveGenerator.GenerateFirstSteps(state, moves, from, buf);
                    for (int i = 0; i < n; i++)
                    {
                        actual.Add(buf[i].To);
                    }

                    Assert.That(
                        string.Join(",", actual), Is.EqualTo(string.Join(",", expected)),
                        "hane " + from + " hedefleri");
                }
            }
        }

        [Test]
        public void FirstSteps_IncludeDedupedAwayFirstMove()
        {
            // 3-1 açılışında 19 -> 22 (zar 3) ile 19 -> 20 -> 23 aynı son duruma ulaşır; üretici
            // bunlardan yalnızca birini tutar. Oyuncu yine de 3'ü önce oynayabilmelidir.
            BackgammonState s = InitialState();
            BackgammonEngine.SetDice(s, 3, 1);

            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(s, moves);

            var buf = new MoveStep[32];
            int n = LegalMoveGenerator.GenerateFirstSteps(s, moves, 19, buf);

            var targets = new List<int>();
            for (int i = 0; i < n; i++)
            {
                targets.Add(buf[i].To);
            }

            Assert.That(targets, Does.Contain(20), "19 -> 20 (zar 1) sunulmali");
            Assert.That(targets, Does.Contain(22), "19 -> 22 (zar 3) sunulmali");
        }

        [Test]
        public void FirstSteps_RespectBarPriority()
        {
            BackgammonState s = Custom(
                1, 0, 0,
                (0, 1), (6, 2), (8, 2), (13, 5), (24, 5));
            BackgammonEngine.SetDice(s, 3, 1);

            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(s, moves);

            var buf = new MoveStep[32];
            for (int from = 1; from <= 24; from++)
            {
                int n = LegalMoveGenerator.GenerateFirstSteps(s, moves, from, buf);
                Assert.That(n, Is.EqualTo(0), "barda tas varken " + from + " adim uretmemeli");
            }

            int barSteps = LegalMoveGenerator.GenerateFirstSteps(s, moves, 0, buf);
            Assert.That(barSteps, Is.GreaterThan(0), "bar girisleri sunulmali");
            for (int i = 0; i < barSteps; i++)
            {
                Assert.That(buf[i].IsFromBar, Is.True, "yalnizca bar girisi");
            }
        }

        [Test]
        public void FirstSteps_RespectBigDieRestriction()
        {
            // Yalnızca tek zar oynanabiliyorsa büyük zar zorunludur (Bölüm 5.1 madde 2).
            // Siyah (turn = -1): 20'de 1, 1'de 14 taş. Zar 6 ve 2. Beyaz 12'yi kapatmıştır.
            //   - 20 -> 14 (zar 6) oynanır, ardından 14 -> 12 bloke.
            //   - 20 -> 18 (zar 2) oynanır, ardından 18 -> 12 bloke.
            // Yani en uzun dizi 1 adımdır ve zarlar farklıdır => büyük zar (6) zorunludur.
            BackgammonState s = Custom(
                -1, 0, 0,
                (12, 2), (19, 13),
                (20, -1), (1, -14));
            BackgammonEngine.SetDice(s, 6, 2);

            var moves = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(s, moves);
            Assert.That(moves.Count, Is.GreaterThan(0), "en az bir yasal hamle olmali");
            Assert.That(moves.Moves[0].Count, Is.EqualTo(1), "en uzun dizi 1 adim olmali");

            var buf = new MoveStep[32];
            int n = LegalMoveGenerator.GenerateFirstSteps(s, moves, 20, buf);
            Assert.That(n, Is.EqualTo(1), "20 hanesinden tek adim");
            Assert.That(buf[0].To, Is.EqualTo(14), "kucuk zar (2) sunulmamali");
            Assert.That(buf[0].Die, Is.EqualTo(6), "buyuk zar (6) zorunlu");
        }

        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static BackgammonState InitialState()
        {
            var s = new BackgammonState();
            s.Reset();
            s.turn = 1;
            s.phase = GamePhase.Moving;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        private static BackgammonState Custom(int turn, int whiteOff, int blackOff, params (int point, int value)[] pieces)
        {
            var s = new BackgammonState();
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            foreach (var (point, value) in pieces)
            {
                s.board[point] = (sbyte)value;
            }

            s.whiteBorneOff = (byte)whiteOff;
            s.blackBorneOff = (byte)blackOff;
            s.turn = (sbyte)turn;
            s.phase = GamePhase.Moving;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        private static int CountPieces(BackgammonState s, int player)
        {
            int total = player == 1 ? s.whiteBorneOff : s.blackBorneOff;
            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                int v = s.board[p];
                if (player == 1 ? v > 0 : v < 0)
                {
                    total += Math.Abs(v);
                }
            }

            return total;
        }

        /// <summary>
        /// Rastgele oynanmış oyunlardan <paramref name="count"/> adet "sıra oyuncuda, zar atılmış"
        /// pozisyon üretir.
        /// </summary>
        private static List<BackgammonState> RandomPositions(int count, ulong seed)
        {
            var result = new List<BackgammonState>();
            var rng = new Xoshiro256StarStar(seed);
            var moves = new MoveList();

            while (result.Count < count)
            {
                var s = new BackgammonState();
                s.Reset();
                s.phase = GamePhase.Moving;
                s.turn = 1;
                s.hash = BackgammonEngine.ComputeZobristHash(s);

                for (int step = 0; step < 200 && result.Count < count; step++)
                {
                    int d1 = 1 + (int)(rng.NextUInt() % 6U);
                    int d2 = 1 + (int)(rng.NextUInt() % 6U);
                    BackgammonEngine.SetDice(s, d1, d2);

                    result.Add(Clone(s));

                    LegalMoveGenerator.GenerateAllLegalMoves(s, moves);
                    if (moves.Count == 0)
                    {
                        break;
                    }

                    MoveSequence pick = moves.Moves[(int)(rng.NextUInt() % (uint)moves.Count)];
                    BackgammonEngine.ApplyMove(s, in pick);

                    if (s.whiteBorneOff == 15 || s.blackBorneOff == 15)
                    {
                        break;
                    }

                    s.turn = (sbyte)-s.turn;
                    s.phase = GamePhase.Moving;
                    s.hash = BackgammonEngine.ComputeZobristHash(s);
                }
            }

            return result;
        }

        private static BackgammonState Clone(BackgammonState s)
        {
            var copy = new BackgammonState();
            copy.CopyFrom(s);
            return copy;
        }
    }
}
