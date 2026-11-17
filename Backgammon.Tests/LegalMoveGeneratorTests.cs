using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Aşama C: yasal hamle üretimi, tekilleştirme, afterstate listesi.</summary>
    [TestFixture]
    public class LegalMoveGeneratorTests
    {
        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

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
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        private static MoveList Generate(BackgammonState s)
        {
            var list = new MoveList();
            LegalMoveGenerator.GenerateAllLegalMoves(s, list);
            return list;
        }

        private static void AssertAllSameLength(MoveList list, int expected)
        {
            for (int i = 0; i < list.Count; i++)
            {
                Assert.That(list.Moves[i].Count, Is.EqualTo(expected), "Hamle #" + i + " uzunluğu: " + list.Moves[i]);
            }
        }

        private static bool ContainsStep(MoveList list, byte from, byte to, byte die, MoveFlags required)
        {
            for (int i = 0; i < list.Count; i++)
            {
                MoveSequence seq = list.Moves[i];
                for (int k = 0; k < seq.Count; k++)
                {
                    MoveStep st = seq[k];
                    if (st.From == from && st.To == to && st.Die == die && (st.Flags & (byte)required) == (byte)required)
                    {
                        return true;
                    }
                }
            }

            return false;
        }

        // ------------------------------------------------------------------
        // Bölüm 8.1: elle yazılmış uç durumlar
        // ------------------------------------------------------------------

        /// <summary>
        /// Beyazın barında 1 taş var, Siyah 1-6 hanelerinin hepsini 2'şer taşla kapatmış.
        /// Hiçbir giriş yasal değil ⇒ boş liste (pas).
        /// </summary>
        [Test]
        public void BarEntry_AllSixBlocked_ReturnsEmpty()
        {
            var s = Custom(1, 0, 0,
                (0, 1), (12, 14),
                (1, -2), (2, -2), (3, -2), (4, -2), (5, -2), (6, -2), (24, -3));

            BackgammonEngine.SetDice(s, 3, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(0));
        }

        /// <summary>
        /// Beyazın barında taş varken üretilen her hamlenin ilk adımı bardan giriş olmalı
        /// (bar önceliği, Bölüm 5.2).
        /// </summary>
        [Test]
        public void BarEntry_BarPriority_AllMovesStartFromBar()
        {
            var s = Custom(1, 0, 0,
                (0, 1), (12, 14),
                (1, -2), (2, -2), (3, -2), (4, -2), (24, -7));

            BackgammonEngine.SetDice(s, 5, 6);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.GreaterThan(0));
            for (int i = 0; i < list.Count; i++)
            {
                Assert.That(list.Moves[i][0].IsFromBar, Is.True, "Hamle #" + i + " bardan başlamıyor: " + list.Moves[i]);
            }
        }

        /// <summary>
        /// Büyük zar kuralı: 3 ve 5 tek tek oynanabiliyor (1→4, 1→6) ama birlikte oynanamıyor
        /// (9 hanesi bloke). Yalnızca büyük zar (5) kalmalı ⇒ tek hamle: 1→6.
        /// </summary>
        [Test]
        public void BigDieRule_OnlyHigherDieRemains()
        {
            var s = Custom(1, 14, 0,
                (1, 1),
                (9, -2), (20, -13));

            BackgammonEngine.SetDice(s, 3, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(1));
            Assert.That(list.Moves[0][0].From, Is.EqualTo(1));
            Assert.That(list.Moves[0][0].To, Is.EqualTo(6));
            Assert.That(list.Moves[0][0].Die, Is.EqualTo(5));
        }

        /// <summary>
        /// Maksimum zar kuralı: 3 önce oynanamıyor (4 bloke), 5 önce oynanabiliyor ve ardından 3
        /// de oynanabiliyor. Tek zarlı diziler elenmeli ⇒ tüm hamleler 2 adım.
        /// </summary>
        [Test]
        public void MaxDiceRule_ShorterSequencesEliminated()
        {
            var s = Custom(1, 0, 0,
                (1, 1), (12, 14),
                (2, -2), (3, -2), (4, -2), (5, -2), (7, -2), (8, -2), (10, -3));

            BackgammonEngine.SetDice(s, 3, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.GreaterThan(0));
            AssertAllSameLength(list, 2);
            Assert.That(ContainsStep(list, 1, 6, 5, 0), Is.True, "1→6 (5) adımı bulunamadı.");
            Assert.That(ContainsStep(list, 6, 9, 3, 0), Is.True, "6→9 (3) adımı bulunamadı.");
        }

        /// <summary>
        /// Dublede 4 adım da oynanabiliyorsa yalnızca 4 adımlık diziler kalır.
        /// </summary>
        [Test]
        public void Doubles_AllFourStepsPlayed()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 4, 4);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.GreaterThan(0));
            AssertAllSameLength(list, 4);
        }

        /// <summary>
        /// Dublede yalnızca 22 hanesinden toplama yasal (23 ve 24 daha geride taş olduğu için
        /// toplanamaz, iç hamle de tahtadan çıkar). 4 kez 22→off ⇒ tek hamle, 4 adım.
        /// </summary>
        [Test]
        public void Doubles_BearOffOnlyFromFurthestBack()
        {
            var s = Custom(1, 0, 0,
                (24, 1), (23, 1), (22, 13),
                (1, -15));

            BackgammonEngine.SetDice(s, 6, 6);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(4));
            for (int k = 0; k < 4; k++)
            {
                Assert.That(list.Moves[0][k].IsBearOff, Is.True);
                Assert.That(list.Moves[0][k].From, Is.EqualTo(22));
                Assert.That(list.Moves[0][k].To, Is.EqualTo(25));
            }
        }

        /// <summary>
        /// Tam zarla toplama: 24 (mesafe 1) 1 zarla toplanır. 19 (mesafe 6) iç hamle yapar.
        /// Üç farklı sonuç pozisyonu ⇒ 3 tekil hamle (hepsi 2 adım).
        /// </summary>
        [Test]
        public void BearOff_ExactDie_AndInnerMove()
        {
            var s = Custom(1, 0, 0,
                (24, 1), (19, 14),
                (1, -15));

            BackgammonEngine.SetDice(s, 1, 2);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(3));
            AssertAllSameLength(list, 2);
            Assert.That(ContainsStep(list, 24, 25, 1, MoveFlags.BearOff), Is.True, "24→off (1) bulunamadı.");
        }

        /// <summary>
        /// Zar &gt; en gerideki taşın mesafesi: 22 (mesafe 3) 5 zarla toplanır çünkü daha geride
        /// taş yok. Ardından 24 (mesafe 1) 6 zarla toplanır.
        /// </summary>
        [Test]
        public void BearOff_DieGreaterThanDistance_AllowedWhenFurthestBack()
        {
            var s = Custom(1, 0, 0,
                (22, 1), (24, 14),
                (1, -15));

            BackgammonEngine.SetDice(s, 5, 6);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(2));
            Assert.That(ContainsStep(list, 22, 25, 5, MoveFlags.BearOff), Is.True, "22→off (5) bulunamadı.");
            Assert.That(ContainsStep(list, 24, 25, 6, MoveFlags.BearOff), Is.True, "24→off (6) bulunamadı.");
        }

        /// <summary>
        /// Geride taş varken büyük zarla toplama yasak: 22 (mesafe 3) 5 zarla toplanamaz,
        /// 19 (mesafe 6) iç hamle yapar ⇒ tek adımlı diziler.
        /// </summary>
        [Test]
        public void BearOff_BlockedWhenPieceFurtherBack()
        {
            var s = Custom(1, 0, 0,
                (22, 1), (19, 14),
                (1, -15));

            BackgammonEngine.SetDice(s, 5, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.GreaterThan(0));
            for (int i = 0; i < list.Count; i++)
            {
                MoveSequence seq = list.Moves[i];
                for (int k = 0; k < seq.Count; k++)
                {
                    Assert.That(seq[k].From == 22 && seq[k].IsBearOff, Is.False, "22 geride taş varken toplanamaz.");
                }
            }
        }

        /// <summary>Siyah için aynı toplama senaryosu (aynalanmış).</summary>
        [Test]
        public void BearOff_Black_ExactDie()
        {
            var s = Custom(-1, 0, 0,
                (1, -1), (6, -14),
                (24, 15));

            BackgammonEngine.SetDice(s, 1, 2);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(3));
            AssertAllSameLength(list, 2);
            Assert.That(ContainsStep(list, 1, 0, 1, MoveFlags.BearOff), Is.True, "1→off (1) bulunamadı.");
        }

        /// <summary>
        /// Boş hane + geride taş var ⇒ iç hamle zorunlu. Beyazın 19'unda 1, 24'ünde 14 taş var.
        /// 24 (mesafe 1) 1 zarla toplanabilir görünse de 19 daha geride olduğu için toplanamaz;
        /// ilk adım her zaman 19'dan bir iç hamle olmalı.
        /// </summary>
        [Test]
        public void BearOff_EmptyPointWithPieceFurtherBack_ForcesInnerMove()
        {
            var s = Custom(1, 0, 0,
                (19, 1), (24, 14),
                (1, -15));

            BackgammonEngine.SetDice(s, 1, 2);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.GreaterThan(0));
            for (int i = 0; i < list.Count; i++)
            {
                MoveStep first = list.Moves[i][0];
                Assert.That(first.From, Is.EqualTo(19), "Hamle #" + i + " iç hamleyle başlamıyor: " + list.Moves[i]);
                Assert.That(first.IsBearOff, Is.False, "19 geride taş varken 24 toplanamaz.");
            }
        }

        /// <summary>
        /// Toplama modu hamle içinde <b>açılır</b>: 18'deki son ev dışı taş eve girince toplama
        /// yasal hâle gelir. 19 bloke olduğu için tek yol 18→24 (6) ardından 24→off (1).
        /// </summary>
        [Test]
        public void BearOffMode_OpensMidMove_WhenLastPieceEntersHome()
        {
            var s = Custom(1, 14, 0,
                (18, 1),
                (19, -2), (1, -13));

            BackgammonEngine.SetDice(s, 6, 1);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(2));
            Assert.That(ContainsStep(list, 24, 25, 1, MoveFlags.BearOff), Is.True,
                "18→24 sonrası 24→off (1) bulunamadı — toplama modu açılmamış.");
        }

        /// <summary>
        /// Toplama sırasında vurulma: Siyah tüm taşları 1-6'da (toplama modunda). Beyaz 2'deki
        /// taşıyla 5'teki Siyah blotunu vurur ⇒ Siyah bara gider ve toplama modu kapanır; Siyah'ın
        /// üretilen tüm hamleleri bardan giriş olmalı.
        /// </summary>
        [Test]
        public void BearOffMode_ClosesAfterHit_OpponentOnBar()
        {
            var s = Custom(1, 14, 0,
                (2, 1),
                (1, -6), (3, -3), (4, -3), (5, -1), (6, -2));

            BackgammonEngine.SetDice(s, 3, 1);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(ContainsStep(list, 2, 5, 3, MoveFlags.Hit), Is.True, "2→5 (3) vuruşu bulunamadı.");

            BackgammonEngine.ApplyMove(s, list.Moves[0]);
            BackgammonEngine.EndTurn(s, EngineSettings.Default);
            BackgammonEngine.SetDice(s, 3, 1);

            Assert.That(s.board[25], Is.EqualTo(-1), "Vurulan Siyah taşı bara gitmeli.");
            Assert.That(s.turn, Is.EqualTo(-1));

            MoveList blackMoves = Generate(s);
            Assert.That(blackMoves.Count, Is.GreaterThan(0));
            for (int i = 0; i < blackMoves.Count; i++)
            {
                Assert.That(blackMoves.Moves[i][0].IsFromBar, Is.True,
                    "Siyah'ın hamlesi bardan başlamıyor: " + blackMoves.Moves[i]);
                Assert.That(blackMoves.Moves[i][0].IsBearOff, Is.False, "Barda taş varken toplama yasak.");
            }
        }

        /// <summary>Siyah için bar senaryosu (aynalanmış): 19-24 kapalı ⇒ pas.</summary>
        [Test]
        public void BarEntry_Black_AllSixBlocked_ReturnsEmpty()
        {
            var s = Custom(-1, 0, 0,
                (25, -1), (13, -14),
                (19, 2), (20, 2), (21, 2), (22, 2), (23, 2), (24, 2), (1, 3));

            BackgammonEngine.SetDice(s, 3, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(0));
        }

        /// <summary>Siyah için büyük zar kuralı (aynalanmış): yalnızca 24→19 (5) kalmalı.</summary>
        [Test]
        public void BigDieRule_Black_OnlyHigherDieRemains()
        {
            var s = Custom(-1, 0, 14,
                (24, -1),
                (16, 2), (5, 13));

            BackgammonEngine.SetDice(s, 3, 5);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(1));
            Assert.That(list.Moves[0][0].From, Is.EqualTo(24));
            Assert.That(list.Moves[0][0].To, Is.EqualTo(19));
            Assert.That(list.Moves[0][0].Die, Is.EqualTo(5));
        }

        // ------------------------------------------------------------------
        // Bölüm 8.1: dublede 4 / 3 / 2 / 1 adım senaryoları
        // ------------------------------------------------------------------

        /// <summary>
        /// Dublede 3 adım: 1'deki tek taş 4'lük zarla 1→5→9→13 ilerler, 13→17 bloke.
        /// 4 zarın yalnızca 3'ü oynanabilir ⇒ tek hamle, 3 adım.
        /// </summary>
        [Test]
        public void Doubles_ThreeStepsPlayed()
        {
            var s = Custom(1, 14, 0,
                (1, 1),
                (17, -2), (18, -2), (19, -2), (20, -2), (21, -2), (22, -5));

            BackgammonEngine.SetDice(s, 4, 4);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(3));
        }

        /// <summary>Dublede 2 adım: 13 de bloke ⇒ 1→5→9, 9→13 oynanamaz.</summary>
        [Test]
        public void Doubles_TwoStepsPlayed()
        {
            var s = Custom(1, 14, 0,
                (1, 1),
                (13, -2), (17, -2), (18, -2), (19, -2), (20, -2), (21, -2), (22, -3));

            BackgammonEngine.SetDice(s, 4, 4);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(2));
        }

        /// <summary>Dublede 1 adım: 9 da bloke ⇒ yalnızca 1→5.</summary>
        [Test]
        public void Doubles_OneStepPlayed()
        {
            var s = Custom(1, 14, 0,
                (1, 1),
                (9, -2), (13, -2), (17, -2), (18, -2), (19, -2), (20, -2), (21, -3));

            BackgammonEngine.SetDice(s, 4, 4);
            MoveList list = Generate(s);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.Moves[0].Count, Is.EqualTo(1));
            Assert.That(list.Moves[0][0].From, Is.EqualTo(1));
            Assert.That(list.Moves[0][0].To, Is.EqualTo(5));
        }

        // ------------------------------------------------------------------
        // Bölüm 8.2: simetri
        // ------------------------------------------------------------------

        [Test]
        public void Symmetry_MirroredPositionProducesMirroredAfterStates()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            var m = new BackgammonState();
            BackgammonEngine.MirrorTo(s, m);

            var es = EngineSettings.Default;
            var a = new AfterStateList(4096);
            var b = new AfterStateList(4096);

            LegalMoveGenerator.GenerateAfterStates(s, es, a);
            LegalMoveGenerator.GenerateAfterStates(m, es, b);

            Assert.That(a.Count, Is.EqualTo(b.Count), "Aynalanmış pozisyon farklı sayıda hamle üretti.");

            var mirrored = new HashSet<ulong>();
            var tmp = new BackgammonState();
            var tmpMirror = new BackgammonState();

            for (int i = 0; i < a.Count; i++)
            {
                tmp.CopyFrom(s);
                BackgammonEngine.LoadAfterState(tmp, a, i);
                BackgammonEngine.MirrorTo(tmp, tmpMirror);
                mirrored.Add(tmpMirror.hash);
            }

            var direct = new HashSet<ulong>();
            for (int i = 0; i < b.Count; i++)
            {
                direct.Add(b.Hash[i]);
            }

            Assert.That(mirrored.SetEquals(direct), Is.True, "Aynalanmış afterstate kümeleri eşleşmiyor.");
        }

        // ------------------------------------------------------------------
        // Bölüm 8.3: Apply → Undo özdeşliği (her yasal hamle için)
        // ------------------------------------------------------------------

        [Test]
        public void ApplyUndo_IdentityForEveryLegalMove()
        {
            var positions = new[]
            {
                new BackgammonState(),
                Custom(1, 0, 0, (24, 1), (19, 14), (1, -15)),
                Custom(1, 0, 0, (22, 1), (19, 14), (1, -15)),
                Custom(1, 0, 0, (0, 1), (12, 14), (1, -2), (2, -2), (3, -2), (4, -2), (24, -7)),
                Custom(-1, 0, 0, (1, 1), (6, 14), (24, 15)),
            };

            var dice = new[] { (3, 5), (1, 2), (5, 6), (4, 4), (6, 6) };

            foreach (var start in positions)
            {
                foreach (var (d1, d2) in dice)
                {
                    var s = start.Clone();
                    BackgammonEngine.SetDice(s, d1, d2);

                    MoveList list = Generate(s);
                    var before = s.Clone();

                    for (int i = 0; i < list.Count; i++)
                    {
                        MoveSequence seq = list.Moves[i];

                        BackgammonEngine.ApplyMove(s, seq);
                        Assert.That(s.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(s)), "ApplyMove sonrası hash tutarsız.");
                        BackgammonEngine.UndoMove(s, seq);

                        Assert.That(s.board, Is.EqualTo(before.board), "board geri dönmedi: " + seq);
                        Assert.That(s.whiteBorneOff, Is.EqualTo(before.whiteBorneOff));
                        Assert.That(s.blackBorneOff, Is.EqualTo(before.blackBorneOff));
                        Assert.That(s.remainingCount, Is.EqualTo(before.remainingCount));
                        Assert.That(s.remainingDice, Is.EqualTo(before.remainingDice));
                        Assert.That(s.hash, Is.EqualTo(before.hash), "hash geri dönmedi: " + seq);
                    }
                }
            }
        }

        // ------------------------------------------------------------------
        // Bölüm 8: AfterStateList tutarlılığı
        // ------------------------------------------------------------------

        [Test]
        public void GenerateAfterStates_MatchesGenerateAllLegalMoves()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            MoveList moves = Generate(s);

            var list = new AfterStateList(4096);
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);

            Assert.That(list.Count, Is.EqualTo(moves.Count));

            for (int i = 0; i < moves.Count; i++)
            {
                Assert.That(list.Sequences[i].Count, Is.EqualTo(moves.Moves[i].Count));
                for (int k = 0; k < moves.Moves[i].Count; k++)
                {
                    Assert.That(list.Sequences[i][k].From, Is.EqualTo(moves.Moves[i][k].From));
                    Assert.That(list.Sequences[i][k].To, Is.EqualTo(moves.Moves[i][k].To));
                    Assert.That(list.Sequences[i][k].Die, Is.EqualTo(moves.Moves[i][k].Die));
                    Assert.That(list.Sequences[i][k].Flags, Is.EqualTo(moves.Moves[i][k].Flags));
                }
            }
        }

        [Test]
        public void GenerateAfterStates_HashAndTerminalFlagsConsistent()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 6, 6);

            var list = new AfterStateList(4096);
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);

            Assert.That(list.Count, Is.GreaterThan(0));

            var tmp = new BackgammonState();
            for (int i = 0; i < list.Count; i++)
            {
                tmp.CopyFrom(s);
                BackgammonEngine.LoadAfterState(tmp, list, i);

                Assert.That(tmp.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(tmp)), "Kayıt #" + i + " hash tutarsız.");
                Assert.That(list.Hash[i], Is.EqualTo(tmp.hash));

                bool terminal = list.WhiteBorneOff[i] == BackgammonState.PiecesPerPlayer ||
                                list.BlackBorneOff[i] == BackgammonState.PiecesPerPlayer;
                Assert.That(list.IsTerminal[i], Is.EqualTo(terminal));

                if (terminal)
                {
                    Assert.That(list.ResultType[i], Is.InRange((byte)1, (byte)3));
                    Assert.That(list.ResultPoints[i], Is.InRange((byte)1, (byte)3));
                }
                else
                {
                    Assert.That(list.ResultType[i], Is.EqualTo(0));
                    Assert.That(list.ResultPoints[i], Is.EqualTo(0));
                }
            }
        }

        [Test]
        public void GenerateAfterStates_TerminalGammon()
        {
            var s = Custom(1, 14, 0, (24, 1), (1, -15));
            BackgammonEngine.SetDice(s, 1, 1);

            var list = new AfterStateList(64);
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.IsTerminal[0], Is.True);
            Assert.That(list.ResultType[0], Is.EqualTo((byte)GameResultType.Gammon));
            Assert.That(list.ResultPoints[0], Is.EqualTo(2));
        }

        [Test]
        public void GenerateAfterStates_TerminalGammon_JacobyReducesToSingle()
        {
            var s = Custom(1, 14, 0, (24, 1), (1, -15));
            BackgammonEngine.SetDice(s, 1, 1);

            var es = EngineSettings.Default;
            es.EnableJacoby = true;

            var list = new AfterStateList(64);
            LegalMoveGenerator.GenerateAfterStates(s, es, list);

            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list.IsTerminal[0], Is.True);
            Assert.That(list.ResultType[0], Is.EqualTo((byte)GameResultType.Single));
            Assert.That(list.ResultPoints[0], Is.EqualTo(1));
        }

        [Test]
        public void GenerateAfterStates_Pass_LeavesEmpty()
        {
            var s = Custom(1, 0, 0,
                (0, 1), (12, 14),
                (1, -2), (2, -2), (3, -2), (4, -2), (5, -2), (6, -2), (24, -3));

            BackgammonEngine.SetDice(s, 3, 5);

            var list = new AfterStateList(64);
            LegalMoveGenerator.GenerateAfterStates(s, EngineSettings.Default, list);

            Assert.That(list.Count, Is.EqualTo(0));
        }

        // ------------------------------------------------------------------
        // Determinizm
        // ------------------------------------------------------------------

        [Test]
        public void Generate_IsDeterministic()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 6, 6);

            MoveList first = Generate(s);
            MoveList second = Generate(s);

            Assert.That(second.Count, Is.EqualTo(first.Count));
            for (int i = 0; i < first.Count; i++)
            {
                Assert.That(second.Moves[i].Count, Is.EqualTo(first.Moves[i].Count));
                for (int k = 0; k < first.Moves[i].Count; k++)
                {
                    Assert.That(second.Moves[i][k].From, Is.EqualTo(first.Moves[i][k].From));
                    Assert.That(second.Moves[i][k].To, Is.EqualTo(first.Moves[i][k].To));
                    Assert.That(second.Moves[i][k].Die, Is.EqualTo(first.Moves[i][k].Die));
                }
            }
        }

        [Test]
        public void Generate_NoDice_ReturnsEmpty()
        {
            var s = new BackgammonState();
            MoveList list = Generate(s);
            Assert.That(list.Count, Is.EqualTo(0));
        }

        [Test]
        public void Generate_LeavesStateUnchanged()
        {
            var s = new BackgammonState();
            BackgammonEngine.SetDice(s, 3, 5);

            var before = s.Clone();
            Generate(s);

            Assert.That(s.board, Is.EqualTo(before.board));
            Assert.That(s.remainingCount, Is.EqualTo(before.remainingCount));
            Assert.That(s.remainingDice, Is.EqualTo(before.remainingDice));
            Assert.That(s.hash, Is.EqualTo(before.hash));
        }

        // ------------------------------------------------------------------
        // Kaba kuvvet referans karşılaştırması (Bölüm 8.1)
        // ------------------------------------------------------------------

        /// <summary>
        /// Bağımsız (kaba kuvvet) bir üretici ile <see cref="LegalMoveGenerator"/> aynı
        /// sonuç pozisyonu kümesini üretmeli. Rastgele oynanan oyunlardan toplanan
        /// pozisyonlarda karşılaştırılır.
        /// </summary>
        [Test]
        public void Generate_MatchesBruteForceReference_OnRandomPositions()
        {
            var rng = new Xoshiro256StarStar(0x5EED1234UL);
            int compared = 0;

            for (int game = 0; game < 40; game++)
            {
                var s = new BackgammonState();

                for (int ply = 0; ply < 60; ply++)
                {
                    int d1 = rng.RollDie();
                    int d2 = rng.RollDie();
                    BackgammonEngine.SetDice(s, d1, d2);

                    var expected = ReferenceAfterStateKeys(s);
                    var actual = GeneratedAfterStateKeys(s);

                    Assert.That(actual.SetEquals(expected), Is.True,
                        "Oyun " + game + " adım " + ply + " (zar " + d1 + "," + d2 + "): üretici referansla uyuşmuyor. " +
                        "Eksik=" + expected.Count + " Fazla=" + actual.Count);

                    compared++;

                    MoveList list = Generate(s);
                    if (list.Count == 0)
                    {
                        s.turn = (sbyte)-s.turn;
                        s.remainingCount = 0;
                        s.hash = BackgammonEngine.ComputeZobristHash(s);
                        continue;
                    }

                    MoveSequence pick = list.Moves[rng.NextUInt() % (uint)list.Count];
                    BackgammonEngine.ApplyMove(s, pick);

                    if (s.whiteBorneOff == BackgammonState.PiecesPerPlayer ||
                        s.blackBorneOff == BackgammonState.PiecesPerPlayer)
                    {
                        break;
                    }

                    s.turn = (sbyte)-s.turn;
                    s.remainingCount = 0;
                    s.hash = BackgammonEngine.ComputeZobristHash(s);
                }
            }

            Assert.That(compared, Is.GreaterThan(1000), "Yeterli sayıda pozisyon karşılaştırılmadı.");
        }

        private static HashSet<string> GeneratedAfterStateKeys(BackgammonState s)
        {
            MoveList list = Generate(s);
            var keys = new HashSet<string>();

            for (int i = 0; i < list.Count; i++)
            {
                var clone = s.Clone();
                BackgammonEngine.ApplyMove(clone, list.Moves[i]);
                keys.Add(BoardKeyOf(clone));
            }

            return keys;
        }

        private static HashSet<string> ReferenceAfterStateKeys(BackgammonState s)
        {
            var all = new List<List<MoveStep>>();
            int max = 0;
            ReferenceCollect(s, new List<MoveStep>(), all, ref max);

            var keys = new HashSet<string>();
            if (max == 0)
            {
                return keys;
            }

            for (int i = 0; i < all.Count; i++)
            {
                List<MoveStep> seq = all[i];
                if (seq.Count != max)
                {
                    continue;
                }

                var clone = s.Clone();
                for (int k = 0; k < seq.Count; k++)
                {
                    BackgammonEngine.ApplyStep(clone, seq[k]);
                }

                keys.Add(BoardKeyOf(clone));
            }

            return keys;
        }

        private static void ReferenceCollect(BackgammonState s, List<MoveStep> cur, List<List<MoveStep>> all, ref int max)
        {
            all.Add(new List<MoveStep>(cur));

            if (cur.Count > max)
            {
                max = cur.Count;
            }

            if (s.remainingCount == 0)
            {
                return;
            }

            int lastDie = -1;
            for (int i = 0; i < s.remainingCount; i++)
            {
                int die = s.remainingDice[i];
                if (die == lastDie)
                {
                    continue;
                }

                lastDie = die;

                List<MoveStep> steps = ReferenceSteps(s, die);
                for (int k = 0; k < steps.Count; k++)
                {
                    MoveStep st = steps[k];
                    BackgammonEngine.ApplyStep(s, st);
                    cur.Add(st);
                    ReferenceCollect(s, cur, all, ref max);
                    cur.RemoveAt(cur.Count - 1);
                    BackgammonEngine.UndoStep(s, st);
                }
            }
        }

        /// <summary>Kaba kuvvet adım üretimi — <see cref="LegalMoveGenerator"/>'dan bağımsız yazılmıştır.</summary>
        private static List<MoveStep> ReferenceSteps(BackgammonState s, int die)
        {
            var result = new List<MoveStep>();
            int turn = s.turn;
            int bar = turn == 1 ? 0 : 25;

            if (s.board[bar] * turn > 0)
            {
                int entry = bar + (die * turn);
                if (entry >= 1 && entry <= 24 && ReferenceCanLand(s, entry, turn))
                {
                    MoveFlags flags = MoveFlags.FromBar;
                    if (s.board[entry] == -turn)
                    {
                        flags |= MoveFlags.Hit;
                    }

                    result.Add(new MoveStep((byte)bar, (byte)entry, (byte)die, flags));
                }

                return result;
            }

            bool bearOffMode = ReferenceBearOffMode(s, turn);
            byte offTarget = (byte)(turn == 1 ? 25 : 0);

            for (int p = 1; p <= 24; p++)
            {
                if (s.board[p] * turn <= 0)
                {
                    continue;
                }

                if (bearOffMode)
                {
                    int dist = turn == 1 ? 25 - p : p;
                    if (dist <= die && (dist == die || !ReferenceFurtherBack(s, p, turn)))
                    {
                        result.Add(new MoveStep((byte)p, offTarget, (byte)die, MoveFlags.BearOff));
                        continue;
                    }
                }

                int to = p + (die * turn);
                if (to >= 1 && to <= 24 && ReferenceCanLand(s, to, turn))
                {
                    MoveFlags flags = s.board[to] == -turn ? MoveFlags.Hit : (MoveFlags)0;
                    result.Add(new MoveStep((byte)p, (byte)to, (byte)die, flags));
                }
            }

            return result;
        }

        private static bool ReferenceCanLand(BackgammonState s, int to, int turn)
        {
            return turn == 1 ? s.board[to] >= -1 : s.board[to] <= 1;
        }

        private static bool ReferenceBearOffMode(BackgammonState s, int turn)
        {
            if (s.board[turn == 1 ? 0 : 25] * turn > 0)
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

        private static bool ReferenceFurtherBack(BackgammonState s, int p, int turn)
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

        private static string BoardKeyOf(BackgammonState s)
        {
            var sb = new System.Text.StringBuilder(64);
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                sb.Append(s.board[i]).Append(',');
            }

            sb.Append('|').Append(s.whiteBorneOff).Append('|').Append(s.blackBorneOff);
            return sb.ToString();
        }
    }
}
