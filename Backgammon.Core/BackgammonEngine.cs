using System;
using System.Diagnostics;

namespace Backgammon.Core
{
    /// <summary>
    /// Tavla mantık katmanı (static). Bölüm 4.
    /// </summary>
    /// <remarks>
    /// Aşama A: imzalar, koordinat yardımcıları, <see cref="ComputeZobristHash"/>,
    /// <see cref="MirrorTo"/>, <see cref="NewGame"/>, <see cref="SanityCheck"/>.
    /// Aşama B: zar atma, Apply/Undo (adım ve hamle), <see cref="LoadAfterState"/>,
    /// <see cref="EndTurn"/>, <see cref="PassTurn"/>, <see cref="IsGameOver"/>.
    /// Aşama C: <see cref="LegalMoveGenerator"/> ve <see cref="GenerateAfterStates"/>.
    /// Aşama D: küp (<see cref="OfferDouble"/>, <see cref="Take"/>, <see cref="Pass"/>) ve maç akışı
    /// (<see cref="StartNextGame"/>, Crawford).
    /// </remarks>
    public static class BackgammonEngine
    {
        // ------------------------------------------------------------------
        // Bölüm 1: Koordinat sistemi yardımcıları (herkese açık, Faz 2 kullanır)
        // ------------------------------------------------------------------

        /// <summary>Taşın toplama çıkışına uzaklığı. Bar her iki renk için 25 döner.</summary>
        public static int DistanceToOff(int point, int turn)
        {
            return turn == 1 ? 25 - point : point;
        }

        /// <summary>Hane ev alanında mı? Beyaz 19-24, Siyah 1-6.</summary>
        public static bool IsHome(int point, int turn)
        {
            return turn == 1 ? (point >= 19 && point <= 24) : (point >= 1 && point <= 6);
        }

        /// <summary>Oyuncunun bar indeksi. Beyaz 0, Siyah 25.</summary>
        public static int BarIndex(int turn)
        {
            return turn == 1 ? 0 : 25;
        }

        // ------------------------------------------------------------------
        // Bölüm 4.1 / 4.7: sıra kuralları (tek doğruluk kaynağı)
        // ------------------------------------------------------------------

        /// <summary>
        /// Zar atılabilir mi? Bölüm 4.1.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Zar <b>yalnızca</b> sıra başında atılır: açılış (<see cref="GamePhase.DetermineFirstPlayer"/>),
        /// küp teklifi öncesi (<see cref="GamePhase.PreRoll"/>) veya normal sıra başı
        /// (<see cref="GamePhase.WaitForRoll"/>).
        /// </para>
        /// <para>
        /// <b>Neden kural:</b> <see cref="GamePhase.Moving"/> fazında zar atmak oyuncuya
        /// istediği kadar yeniden zar atma hakkı verir; bu tavla kurallarına aykırıdır.
        /// Aynı şekilde <see cref="GamePhase.CubeOffered"/> ve <see cref="GamePhase.GameOver"/>
        /// fazlarında da zar atılamaz.
        /// </para>
        /// </remarks>
        public static bool CanRoll(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            return s.phase == GamePhase.DetermineFirstPlayer ||
                   s.phase == GamePhase.PreRoll ||
                   s.phase == GamePhase.WaitForRoll;
        }

        /// <summary>
        /// Sıra kapanmalı mı? Bölüm 4.7.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Kural: oyuncu zarlarının <b>tamamını</b> oynayamıyorsa oynayabildiği kadarını oynar ve
        /// sıra kapanır. Bu yüzden <see cref="GamePhase.Moving"/> fazında sıra şu iki durumda
        /// kapanır:
        /// </para>
        /// <list type="number">
        /// <item><description>Kalan zar yok (<c>remainingCount == 0</c>).</description></item>
        /// <item><description>
        /// Kalan zarlarla oynanabilecek <b>yasal hamle yok</b> — örneğin 5-5 atıldı ama yalnızca
        /// iki hamle oynanabiliyor; ya da son taş toplandı ve zarlardan biri arttı.
        /// </description></item>
        /// </list>
        /// <para>
        /// <paramref name="legalMoves"/> <b>güncel</b> durumdan üretilmiş olmalıdır
        /// (<see cref="LegalMoveGenerator.GenerateAllLegalMoves"/>).
        /// </para>
        /// </remarks>
        public static bool ShouldEndTurn(BackgammonState s, MoveList legalMoves)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (s.phase != GamePhase.Moving)
            {
                return false;
            }

            if (s.remainingCount == 0)
            {
                return true;
            }

            return legalMoves == null || legalMoves.Count == 0;
        }

        // ------------------------------------------------------------------
        // Bölüm 4: Oyun akışı
        // ------------------------------------------------------------------

        public static void NewGame(BackgammonState s, MatchSettings m)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            s.Reset();
            s.matchLength = m.MatchLength;
            s.phase = GamePhase.DetermineFirstPlayer;
            s.hash = ComputeZobristHash(s);
        }

        /// <summary>
        /// Açılış: her oyuncu tek zar atar, eşitse tekrar atılır. Büyük zarı atan başlar ve ilk
        /// hamleyi bu iki zarla oynar. Bölüm 4.1.
        /// </summary>
        public static void RollOpening(BackgammonState s, IRandom rng)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (rng == null)
            {
                throw new ArgumentNullException(nameof(rng));
            }

            int d1;
            int d2;
            do
            {
                d1 = rng.RollDie();
                d2 = rng.RollDie();
            }
            while (d1 == d2);

            s.turn = (sbyte)(d1 > d2 ? 1 : -1);
            s.hash = ComputeZobristHash(s);

            SetDice(s, d1, d2);
        }

        public static void RollDice(BackgammonState s, IRandom rng)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (rng == null)
            {
                throw new ArgumentNullException(nameof(rng));
            }

            SetDice(s, rng.RollDie(), rng.RollDie());
        }

        /// <summary>
        /// Zarları RNG kullanmadan ayarlar. <c>remainingDice</c> sıralı doldurulur; dublede 4 slot.
        /// Bölüm 4.2.
        /// </summary>
        public static void SetDice(BackgammonState s, int d1, int d2)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (d1 < 1 || d1 > 6)
            {
                throw new ArgumentException("Zar 1..6 aralığında olmalı: " + d1, nameof(d1));
            }

            if (d2 < 1 || d2 > 6)
            {
                throw new ArgumentException("Zar 1..6 aralığında olmalı: " + d2, nameof(d2));
            }

            s.rolledDice[0] = (byte)d1;
            s.rolledDice[1] = (byte)d2;

            if (d1 == d2)
            {
                s.remainingDice[0] = (byte)d1;
                s.remainingDice[1] = (byte)d1;
                s.remainingDice[2] = (byte)d1;
                s.remainingDice[3] = (byte)d1;
                s.remainingCount = 4;
            }
            else
            {
                s.remainingDice[0] = (byte)(d1 < d2 ? d1 : d2);
                s.remainingDice[1] = (byte)(d1 < d2 ? d2 : d1);
                s.remainingDice[2] = 0;
                s.remainingDice[3] = 0;
                s.remainingCount = 2;
            }

            s.phase = GamePhase.Moving;
        }

        /// <summary>
        /// Tek adımı yerinde uygular; hash artımlı güncellenir. Bölüm 4.3 sözde kodu.
        /// </summary>
        public static void ApplyStep(BackgammonState s, in MoveStep step)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            int turn = s.turn;
            int die = step.Die;

            DebugAssert(!(step.IsHit && step.IsBearOff), "Bir adım hem Hit hem BearOff olamaz.");
            DebugAssert(!step.IsFromBar || step.From == BarIndex(turn), "FromBar adımında From = BarIndex(turn) olmalı.");
            DebugAssert(!step.IsBearOff || step.To == (turn == 1 ? 25 : 0), "BearOff adımında To = 25 (Beyaz) / 0 (Siyah) olmalı.");

            // Vuruş bayrağı hedefte TAM OLARAK bir rakip taş olduğunu garanti eder. Bayrak
            // bayatsa (başka bir ara durumdan kopyalanmışsa) hedefteki rakip taş silinir ve
            // taş sayısı bozulur ("vurduğumda taşım eksiliyor" hatası). Bu yüzden burada
            // durum ile bayrak tutarlılığı doğrulanır.
            DebugAssert(!step.IsHit || s.board[step.To] == -turn, "Hit adımında hedefte tam olarak bir rakip taş olmalı.");

            // 1) Zar tüketimi (remainingDice sıralı; ilk eşleşen slot)
            int slot = FindFirstSlotWithValue(s.remainingDice, s.remainingCount, die);
            if (slot < 0)
            {
                throw new InvalidOperationException("ApplyStep: " + die + " değerinde kalan zar yok.");
            }

            RemoveSlot(s.remainingDice, ref s.remainingCount, slot);

            // 2) Kaynak haneden taşı çıkar
            int from = step.IsFromBar ? BarIndex(turn) : step.From;

            s.hash ^= Zobrist.BoardKey(from, s.board[from]);
            s.board[from] -= (sbyte)turn;
            s.hash ^= Zobrist.BoardKey(from, s.board[from]);

            // 3) Taş toplama
            if (step.IsBearOff)
            {
                if (turn == 1)
                {
                    s.hash ^= Zobrist.WhiteOffKey(s.whiteBorneOff);
                    s.whiteBorneOff++;
                    s.hash ^= Zobrist.WhiteOffKey(s.whiteBorneOff);
                }
                else
                {
                    s.hash ^= Zobrist.BlackOffKey(s.blackBorneOff);
                    s.blackBorneOff++;
                    s.hash ^= Zobrist.BlackOffKey(s.blackBorneOff);
                }

                return;
            }

            // 4) Vurulma
            if (step.IsHit)
            {
                int opp = -turn;
                int oppBar = BarIndex(opp);

                s.hash ^= Zobrist.BoardKey(oppBar, s.board[oppBar]);
                s.board[oppBar] += (sbyte)opp;
                s.hash ^= Zobrist.BoardKey(oppBar, s.board[oppBar]);

                s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
                s.board[step.To] = 0;
                s.hash ^= Zobrist.BoardKey(step.To, 0);
            }

            // 5) Hedef haneye kendi taşını koy
            s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
            s.board[step.To] += (sbyte)turn;
            s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
        }

        /// <summary>
        /// <see cref="ApplyStep"/>'in tam tersi. Bölüm 4.4 sözde kodu.
        /// </summary>
        public static void UndoStep(BackgammonState s, in MoveStep step)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            int turn = s.turn;
            int die = step.Die;

            DebugAssert(s.remainingCount < 4, "UndoStep: remainingCount 4 iken geri alınamaz.");

            // 1) Hedef haneden taşı geri al (veya borneOff'u azalt)
            if (step.IsBearOff)
            {
                if (turn == 1)
                {
                    s.hash ^= Zobrist.WhiteOffKey(s.whiteBorneOff);
                    s.whiteBorneOff--;
                    s.hash ^= Zobrist.WhiteOffKey(s.whiteBorneOff);
                }
                else
                {
                    s.hash ^= Zobrist.BlackOffKey(s.blackBorneOff);
                    s.blackBorneOff--;
                    s.hash ^= Zobrist.BlackOffKey(s.blackBorneOff);
                }
            }
            else
            {
                // 2) Hedef haneden kendi taşını çıkar
                s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
                s.board[step.To] -= (sbyte)turn;
                s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);

                // 3) Vurulma varsa rakip taşı bardan geri koy
                if (step.IsHit)
                {
                    int opp = -turn;
                    int oppBar = BarIndex(opp);

                    s.hash ^= Zobrist.BoardKey(oppBar, s.board[oppBar]);
                    s.board[oppBar] -= (sbyte)opp;
                    s.hash ^= Zobrist.BoardKey(oppBar, s.board[oppBar]);

                    s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
                    s.board[step.To] = (sbyte)opp;
                    s.hash ^= Zobrist.BoardKey(step.To, s.board[step.To]);
                }
            }

            // 4) Kaynak haneye taşı geri koy (veya bara)
            int from = step.IsFromBar ? BarIndex(turn) : step.From;

            s.hash ^= Zobrist.BoardKey(from, s.board[from]);
            s.board[from] += (sbyte)turn;
            s.hash ^= Zobrist.BoardKey(from, s.board[from]);

            // 5) Zarı geri aç ve sıralı tut
            s.remainingDice[s.remainingCount] = (byte)die;
            s.remainingCount++;
            SortRemainingDice(s.remainingDice, s.remainingCount);
        }

        /// <summary>
        /// Adımları sırayla uygular. Oyun bittiyse <c>phase = GameOver</c> yapar; bu geçişin tek
        /// yeri burasıdır (Bölüm 4.6).
        /// </summary>
        public static void ApplyMove(BackgammonState s, in MoveSequence seq)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            for (int i = 0; i < seq.Count; i++)
            {
                ApplyStep(s, seq[i]);
            }

            GameResult result;
            if (IsGameOver(s, out result))
            {
                s.phase = GamePhase.GameOver;
            }
        }

        /// <summary>Adımları TERS sırayla geri alır ve kalan zarları geri yükler.</summary>
        public static void UndoMove(BackgammonState s, in MoveSequence seq)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            for (int i = seq.Count - 1; i >= 0; i--)
            {
                UndoStep(s, seq[i]);
            }

            s.phase = GamePhase.Moving;
        }

        /// <summary>
        /// Afterstate kaydını <paramref name="dst"/> üzerine yükler. Önkoşul: <c>dst.turn</c>
        /// hamleyi yapan oyuncudur. <c>phase = GameOver</c> YAPMAZ. Bölüm 4.5.
        /// </summary>
        public static void LoadAfterState(BackgammonState dst, AfterStateList list, int index)
        {
            if (dst == null)
            {
                throw new ArgumentNullException(nameof(dst));
            }

            if (list == null)
            {
                throw new ArgumentNullException(nameof(list));
            }

            if ((uint)index >= (uint)list.Count)
            {
                throw new ArgumentOutOfRangeException(nameof(index));
            }

            int offset = index * AfterStateList.BoardSize;
            Array.Copy(list.Boards, offset, dst.board, 0, AfterStateList.BoardSize);

            dst.whiteBorneOff = list.WhiteBorneOff[index];
            dst.blackBorneOff = list.BlackBorneOff[index];
            dst.hash = list.Hash[index];

            dst.remainingDice[0] = 0;
            dst.remainingDice[1] = 0;
            dst.remainingDice[2] = 0;
            dst.remainingDice[3] = 0;
            dst.remainingCount = 0;

            dst.phase = GamePhase.Moving;
        }

        /// <summary>Turu kapatır: turn çevrilir, zarlar temizlenir, faz güncellenir. Bölüm 4.6.</summary>
        public static void EndTurn(BackgammonState s)
        {
            EndTurn(s, EngineSettings.Default);
        }

        public static void EndTurn(BackgammonState s, in EngineSettings es)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            // Oyun bittiyse sira cevrilmez. Aksi halde "turu bitir" dugmesi fazi
            // GameOver'dan cikarip rakibe hamle hakki veriyordu.
            //
            // Yalnizca faz kontrol edilir; `whiteBorneOff >= 15` gibi bir kosul EKLENMEZ.
            // Arama `LoadAfterState` + `EndTurn` zincirini kullanir ve orada faz bilincli
            // olarak `Moving` birakilir (bkz. LoadAfterState); tas sayacina bakmak aramanin
            // bakis acisini bozardi.
            if (s.phase == GamePhase.GameOver)
            {
                return;
            }

            s.turn = (sbyte)(-s.turn);
            s.hash ^= Zobrist.TurnKey;

            s.rolledDice[0] = 0;
            s.rolledDice[1] = 0;
            s.remainingDice[0] = 0;
            s.remainingDice[1] = 0;
            s.remainingDice[2] = 0;
            s.remainingDice[3] = 0;
            s.remainingCount = 0;

            s.phase = CanOfferAtTurnStart(s, es) ? GamePhase.PreRoll : GamePhase.WaitForRoll;
        }

        /// <summary>
        /// Atılmış ama <b>hiç taş oynanmamış</b> zarları geri alır ve fazı yeniden küp teklifine
        /// uygun hâle getirir. Bölüm 4.9.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Kural gereği küp <b>zar atmadan önce</b> teklif edilir. Oyuncu zarı attıktan sonra
        /// henüz taş oynamadıysa teklif hakkını kaybetmiş sayılmamalıdır; bu metot o pencereyi
        /// yeniden açar.
        /// </para>
        /// <para>
        /// Hiçbir şey değiştirilmez (ve <c>false</c> döner) eğer: faz <see cref="GamePhase.Moving"/>
        /// değilse, en az bir taş oynanmışsa veya küp zaten teklif edilemiyorsa.
        /// </para>
        /// </remarks>
        public static bool RevertRoll(BackgammonState s, in EngineSettings es)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (s.phase != GamePhase.Moving)
            {
                return false;
            }

            int rolled = s.rolledDice[0] == s.rolledDice[1] ? 4 : 2;
            if (s.remainingCount != rolled)
            {
                return false;
            }

            if (!CanOfferAtTurnStart(s, es))
            {
                return false;
            }

            s.rolledDice[0] = 0;
            s.rolledDice[1] = 0;
            s.remainingDice[0] = 0;
            s.remainingDice[1] = 0;
            s.remainingDice[2] = 0;
            s.remainingDice[3] = 0;
            s.remainingCount = 0;
            s.phase = GamePhase.PreRoll;
            return true;
        }

        /// <summary>Yasal hamle yoksa turu kapatır. Bölüm 4.7.</summary>
        public static void PassTurn(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            DebugAssert(s.phase == GamePhase.Moving, "PassTurn yalnızca Moving fazında çağrılabilir.");

            s.remainingCount = 0;
            s.rolledDice[0] = 0;
            s.rolledDice[1] = 0;

            EndTurn(s);
        }

        /// <summary>Oyun sonu ve mars kuralları. Bölüm 4.8. Jacoby uygulanmaz.</summary>
        public static bool IsGameOver(BackgammonState s, out GameResult result)
        {
            return IsGameOver(s, default(EngineSettings), out result);
        }

        /// <summary>
        /// Jacoby kuralını uygulayan aşırı yükleme. <see cref="AfterStateList.ResultPoints"/> bu
        /// sürümle doldurulur (Bölüm 2.3b / 4.8).
        /// </summary>
        public static bool IsGameOver(BackgammonState s, in EngineSettings es, out GameResult result)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            int winner = 0;
            if (s.whiteBorneOff == BackgammonState.PiecesPerPlayer)
            {
                winner = 1;
            }
            else if (s.blackBorneOff == BackgammonState.PiecesPerPlayer)
            {
                winner = -1;
            }

            if (winner == 0)
            {
                result = default(GameResult);
                return false;
            }

            int loser = -winner;
            int loserBorneOff = loser == 1 ? s.whiteBorneOff : s.blackBorneOff;

            GameResultType type;
            int points;

            if (loserBorneOff > 0)
            {
                type = GameResultType.Single;
                points = 1;
            }
            else
            {
                int loserBar = s.board[BarIndex(loser)];
                bool onBar = loser == 1 ? loserBar > 0 : loserBar < 0;

                bool inWinnerHome = false;
                for (int p = 1; p <= 24; p++)
                {
                    int v = s.board[p];
                    bool isLoserPiece = loser == 1 ? v > 0 : v < 0;
                    if (isLoserPiece && IsHome(p, winner))
                    {
                        inWinnerHome = true;
                        break;
                    }
                }

                if (onBar || inWinnerHome)
                {
                    type = GameResultType.Backgammon;
                    points = 3;
                }
                else
                {
                    type = GameResultType.Gammon;
                    points = 2;
                }
            }

            if (es.EnableJacoby && s.matchLength == 0 && s.cubeOwner == 0 && points > 1)
            {
                type = GameResultType.Single;
                points = 1;
            }

            result = new GameResult((sbyte)winner, type, points);
            return true;
        }

        // ------------------------------------------------------------------
        // Bölüm 2.1 / 6: Hash
        // ------------------------------------------------------------------

        /// <summary>
        /// Hash'i sıfırdan hesaplar. Yalnızca SanityCheck ve testlerde kullanılır; hot path'te
        /// <see cref="BackgammonState.hash"/> (artımlı) kullanılır.
        /// </summary>
        public static ulong ComputeZobristHash(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            ulong h = 0;

            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                h ^= Zobrist.BoardKey(p, s.board[p]);
            }

            h ^= Zobrist.WhiteOffKey(s.whiteBorneOff);
            h ^= Zobrist.BlackOffKey(s.blackBorneOff);

            if (s.turn < 0)
            {
                h ^= Zobrist.TurnKey;
            }

            h ^= Zobrist.CubeValueKey(s.cubeValue);
            h ^= Zobrist.CubeOwnerKey(s.cubeOwner);

            return h;
        }

        // ------------------------------------------------------------------
        // Bölüm 6: Simetri
        // ------------------------------------------------------------------

        /// <summary>
        /// "Sıradaki oyuncu hep +1" perspektifine aynalar. Hash yeniden hesaplanır (hot path değil).
        /// </summary>
        public static void MirrorTo(BackgammonState src, BackgammonState dst)
        {
            if (src == null)
            {
                throw new ArgumentNullException(nameof(src));
            }

            if (dst == null)
            {
                throw new ArgumentNullException(nameof(dst));
            }

            if (ReferenceEquals(src, dst))
            {
                throw new ArgumentException("src ve dst aynı nesne olamaz.", nameof(dst));
            }

            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                dst.board[i] = (sbyte)(-src.board[BackgammonState.BoardSize - 1 - i]);
            }

            dst.whiteBorneOff = src.blackBorneOff;
            dst.blackBorneOff = src.whiteBorneOff;
            dst.turn = (sbyte)(-src.turn);

            dst.rolledDice[0] = src.rolledDice[0];
            dst.rolledDice[1] = src.rolledDice[1];
            dst.remainingDice[0] = src.remainingDice[0];
            dst.remainingDice[1] = src.remainingDice[1];
            dst.remainingDice[2] = src.remainingDice[2];
            dst.remainingDice[3] = src.remainingDice[3];
            dst.remainingCount = src.remainingCount;

            dst.cubeValue = src.cubeValue;
            dst.cubeOwner = (sbyte)(-src.cubeOwner);
            dst.matchLength = src.matchLength;
            dst.whiteScore = src.blackScore;
            dst.blackScore = src.whiteScore;
            dst.isCrawfordGame = src.isCrawfordGame;
            dst.crawfordPlayed = src.crawfordPlayed;
            dst.cubePassed = src.cubePassed;
            dst.phase = src.phase;

            dst.hash = ComputeZobristHash(dst);
        }

        // ------------------------------------------------------------------
        // Bölüm 4.9: Küp
        // ------------------------------------------------------------------

        /// <summary>Küp teklif edilebilir mi? Bölüm 4.9. <see cref="EngineSettings.Default"/> kullanır.</summary>
        public static bool CanOffer(BackgammonState s)
        {
            return CanOffer(s, EngineSettings.Default);
        }

        public static bool CanOffer(BackgammonState s, in EngineSettings es)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (s.phase != GamePhase.PreRoll)
            {
                return false;
            }

            return CanOfferAtTurnStart(s, es);
        }

        /// <summary>
        /// Faz kontrolünü atlayan küp uygunluk kontrolü. <see cref="EndTurn"/> tarafından, yeni fazı
        /// belirlemek için kullanılır (o anda <c>phase</c> henüz <c>PreRoll</c> değildir).
        /// </summary>
        private static bool CanOfferAtTurnStart(BackgammonState s, in EngineSettings es)
        {
            if (s.isCrawfordGame)
            {
                return false;
            }

            if (s.cubeOwner != 0 && s.cubeOwner != s.turn)
            {
                return false;
            }

            // Küp üst sınırı: ikiye katlama MatchState'in kabul ettiği aralığı aşamaz.
            // Money game'de ölü küp kontrolü devre dışı olduğu için küp 64'ten 128'e
            // çıkabiliyordu; Take() sonrası MatchState.From() istisna atıp oyunu
            // kilitliyordu (ne zar ne hamle). Bu kontrol o yolu kapatır.
            if (s.cubeValue >= MatchState.MoneyGameMaxCube)
            {
                return false;
            }

            if (es.DisallowDeadCube && s.matchLength > 0)
            {
                int offererScore = s.turn == 1 ? s.whiteScore : s.blackScore;
                if (s.cubeValue >= s.matchLength - offererScore)
                {
                    return false;
                }
            }

            return true;
        }

        /// <summary>
        /// Küp teklif eder: faz <see cref="GamePhase.CubeOffered"/> olur, küp değeri henüz değişmez.
        /// Önkoşul: <see cref="CanOffer(BackgammonState)"/>. Bölüm 4.9.
        /// </summary>
        public static void OfferDouble(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (!CanOffer(s))
            {
                throw new InvalidOperationException("Küp teklif edilemez (CanOffer false).");
            }

            s.phase = GamePhase.CubeOffered;
        }

        /// <summary>
        /// Rakip küpü kabul eder: küp ikiye katlanır ve sahibi alan oyuncu (teklif edenin rakibi) olur.
        /// Teklif eden oyuncu zar atmaya devam eder. Bölüm 4.9.
        /// </summary>
        public static void Take(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            DebugAssert(s.phase == GamePhase.CubeOffered, "Take yalnızca CubeOffered fazında çağrılabilir.");

            s.hash ^= Zobrist.CubeValueKey(s.cubeValue);
            s.hash ^= Zobrist.CubeOwnerKey(s.cubeOwner);

            s.cubeValue *= 2;
            s.cubeOwner = (sbyte)(-s.turn);

            s.hash ^= Zobrist.CubeValueKey(s.cubeValue);
            s.hash ^= Zobrist.CubeOwnerKey(s.cubeOwner);

            s.phase = GamePhase.WaitForRoll;
        }

        /// <summary>
        /// Rakip küpü reddeder: teklif eden oyuncu oyunu kazanır. Bölüm 4.9.
        /// </summary>
        /// <remarks>
        /// Dönen <see cref="GameResult.Points"/> mars çarpanıdır (her zaman 1, çünkü küp reddinde mars
        /// yoktur); gerçek skor <c>Points * cubeValue</c> ile <see cref="StartNextGame"/> içinde uygulanır.
        /// Küp değeri değişmez (teklif kabul edilmedi). Faz <see cref="GamePhase.GameOver"/> olur ve
        /// <see cref="BackgammonState.cubePassed"/> işaretlenir (ASSUMPTIONS.md D-03).
        /// </remarks>
        public static GameResult Pass(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            DebugAssert(s.phase == GamePhase.CubeOffered, "Pass yalnızca CubeOffered fazında çağrılabilir.");

            var result = new GameResult(s.turn, GameResultType.Single, 1);

            s.cubePassed = true;
            s.phase = GamePhase.GameOver;

            return result;
        }

        /// <summary>
        /// Biten oyunun sonucunu skora işler, maç/Crawford durumunu günceller ve yeni oyunu kurar.
        /// Bölüm 4.9.
        /// </summary>
        /// <remarks>
        /// Skor artışı <c>last.Points * s.cubeValue</c>'dir (Points mars çarpanı, cubeValue ayrı).
        /// Maç bittiyse tahta sıfırlanmaz ve faz <see cref="GamePhase.GameOver"/> kalır.
        /// Aksi hâlde tahta başlangıç dizilimine döner, küp 1'e ve ortaya sıfırlanır, faz
        /// <see cref="GamePhase.DetermineFirstPlayer"/> olur.
        /// </remarks>
        public static void StartNextGame(BackgammonState s, in GameResult last)
        {
            if (ApplyResult(s, in last))
            {
                s.phase = GamePhase.GameOver;
                return;
            }

            PrepareNextGame(s);
        }

        /// <summary>
        /// Biten oyunun sonucunu <b>skora işler</b>; tahtayı sıfırlamaz. Bölüm 4.9.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Skor artışı <c>last.Points * s.cubeValue</c>'dir. Crawford bayrakları da burada
        /// güncellenir: oynanan Crawford oyunu bir daha oynanmaz.
        /// </para>
        /// <para>
        /// <b>Neden ayrı:</b> UI, oyun bittiğinde skoru <b>hemen</b> göstermelidir; tahta ise
        /// son pozisyonda kalmalıdır. <see cref="StartNextGame"/> bu metodu çağırıp tahtayı
        /// sıfırlar; iki adım ayrıldığında çift sayım riski kalmaz.
        /// </para>
        /// </remarks>
        /// <returns>Maç bitti mi? (<c>true</c> ise yeni oyun kurulmaz.)</returns>
        public static bool ApplyResult(BackgammonState s, in GameResult last)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (last.Winner != 1 && last.Winner != -1)
            {
                throw new ArgumentException("Geçersiz GameResult: Winner +1 veya -1 olmalı.", nameof(last));
            }

            int points = last.Points * s.cubeValue;
            if (last.Winner == 1)
            {
                s.whiteScore += points;
            }
            else
            {
                s.blackScore += points;
            }

            // Crawford oyunu oynandıysa bir daha oynanmaz.
            if (s.isCrawfordGame)
            {
                s.isCrawfordGame = false;
                s.crawfordPlayed = true;
            }

            return s.matchLength > 0 && (s.whiteScore >= s.matchLength || s.blackScore >= s.matchLength);
        }

        /// <summary>
        /// Sonucu <b>zaten işlenmiş</b> oyunda tahtayı yeni oyuna hazırlar. Bölüm 4.9.
        /// </summary>
        /// <remarks>
        /// Maç bittiyse tahta sıfırlanmaz ve faz <see cref="GamePhase.GameOver"/> kalır.
        /// Aksi hâlde Crawford bayrağı güncellenir, tahta başlangıç dizilimine döner, küp 1'e ve
        /// ortaya sıfırlanır, faz <see cref="GamePhase.DetermineFirstPlayer"/> olur.
        /// </remarks>
        public static void PrepareNextGame(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (s.matchLength > 0 && (s.whiteScore >= s.matchLength || s.blackScore >= s.matchLength))
            {
                s.phase = GamePhase.GameOver;
                return;
            }

            if (s.matchLength >= 2 && !s.crawfordPlayed &&
                (s.whiteScore == s.matchLength - 1 || s.blackScore == s.matchLength - 1))
            {
                s.isCrawfordGame = true;
            }

            ResetBoardForNextGame(s);
        }

        /// <summary>
        /// Tahtayı başlangıç dizilimine döndürür; maç skoru ve Crawford bayrakları korunur.
        /// </summary>
        private static void ResetBoardForNextGame(BackgammonState s)
        {
            int matchLength = s.matchLength;
            int whiteScore = s.whiteScore;
            int blackScore = s.blackScore;
            bool isCrawfordGame = s.isCrawfordGame;
            bool crawfordPlayed = s.crawfordPlayed;

            s.Reset();

            s.matchLength = matchLength;
            s.whiteScore = whiteScore;
            s.blackScore = blackScore;
            s.isCrawfordGame = isCrawfordGame;
            s.crawfordPlayed = crawfordPlayed;
        }

        // ------------------------------------------------------------------
        // Özel yardımcılar
        // ------------------------------------------------------------------

        private static int FindFirstSlotWithValue(byte[] dice, int count, int die)
        {
            for (int i = 0; i < count; i++)
            {
                if (dice[i] == die)
                {
                    return i;
                }
            }

            return -1;
        }

        private static void RemoveSlot(byte[] dice, ref byte count, int index)
        {
            for (int i = index; i < count - 1; i++)
            {
                dice[i] = dice[i + 1];
            }

            count--;
            dice[count] = 0;
        }

        private static void SortRemainingDice(byte[] dice, int count)
        {
            for (int i = 1; i < count; i++)
            {
                byte key = dice[i];
                int j = i - 1;
                while (j >= 0 && dice[j] > key)
                {
                    dice[j + 1] = dice[j];
                    j--;
                }

                dice[j + 1] = key;
            }
        }

        /// <summary>
        /// Debug-only assert. .NET Core'da <see cref="Debug.Assert(bool)"/> hatası süreci
        /// sonlandırabildiği için yakalanabilir bir istisna fırlatır (bkz. ASSUMPTIONS.md B-09).
        /// </summary>
        [Conditional("DEBUG")]
        private static void DebugAssert(bool condition, string message)
        {
            if (!condition)
            {
                throw new InvalidOperationException("Assert: " + message);
            }
        }

        // ------------------------------------------------------------------
        // Bölüm 8: SanityCheck (yalnızca Debug)
        // ------------------------------------------------------------------

        [Conditional("DEBUG")]
        public static void SanityCheck(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (s.turn != 1 && s.turn != -1)
            {
                Fail("turn +1 veya -1 olmalı: " + s.turn);
            }

            // 1) Taş sayıları ve 2) bar işaretleri / hane aralığı
            int white = s.whiteBorneOff;
            int black = s.blackBorneOff;

            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                int v = s.board[p];

                if (p == 0)
                {
                    if (v < 0)
                    {
                        Fail("board[0] (Beyaz bar) negatif olamaz: " + v);
                    }

                    white += v;
                }
                else if (p == 25)
                {
                    if (v > 0)
                    {
                        Fail("board[25] (Siyah bar) pozitif olamaz: " + v);
                    }

                    black += -v;
                }
                else
                {
                    if (v < -15 || v > 15)
                    {
                        Fail("board[" + p + "] aralık dışı: " + v);
                    }

                    if (v > 0)
                    {
                        white += v;
                    }
                    else
                    {
                        black += -v;
                    }
                }
            }

            if (white != BackgammonState.PiecesPerPlayer)
            {
                Fail("Beyaz taş sayısı 15 değil: " + white);
            }

            if (black != BackgammonState.PiecesPerPlayer)
            {
                Fail("Siyah taş sayısı 15 değil: " + black);
            }

            // 3) Zarlar
            int rolledCount = RolledDiceCount(s);
            if (s.remainingCount > rolledCount)
            {
                Fail("remainingCount (" + s.remainingCount + ") atılan zar sayısından (" + rolledCount + ") büyük.");
            }

            for (int i = 0; i < s.remainingCount; i++)
            {
                byte d = s.remainingDice[i];
                if (d < 1 || d > 6)
                {
                    Fail("remainingDice[" + i + "] 1..6 dışında: " + d);
                }

                if (i > 0 && s.remainingDice[i - 1] > d)
                {
                    Fail("remainingDice sıralı değil.");
                }
            }

            for (int d = 1; d <= 6; d++)
            {
                if (CountRemaining(s, d) > CountRolled(s, d))
                {
                    Fail("remainingDice, rolledDice'ın alt kümesi değil (zar " + d + ").");
                }
            }

            // 4) Küp ve Crawford
            if (s.cubeValue <= 0 || (s.cubeValue & (s.cubeValue - 1)) != 0)
            {
                Fail("cubeValue 2'nin kuvveti olmalı: " + s.cubeValue);
            }

            if (Zobrist.Log2(s.cubeValue) >= Zobrist.CubeExponentCount)
            {
                Fail("cubeValue Zobrist tablosu aralığı dışında: " + s.cubeValue);
            }

            if (s.cubeOwner < -1 || s.cubeOwner > 1)
            {
                Fail("cubeOwner -1/0/+1 olmalı: " + s.cubeOwner);
            }

            if (s.isCrawfordGame && (s.cubeValue != 1 || s.cubeOwner != 0))
            {
                Fail("Crawford oyununda küp 1 ve ortada olmalı.");
            }

            // 5) GameOver tutarlılığı. Küp reddi (Pass) ile biten oyunda tahta terminal değildir;
            //    bu durum cubePassed ile işaretlenir (ASSUMPTIONS.md D-03).
            if (s.phase == GamePhase.GameOver &&
                !s.cubePassed &&
                s.whiteBorneOff != BackgammonState.PiecesPerPlayer &&
                s.blackBorneOff != BackgammonState.PiecesPerPlayer)
            {
                Fail("phase == GameOver ama hiçbir taraf 15 taş toplamadı.");
            }

            // 7) Artımlı hash, tam yeniden hesaplamayla eşit olmalı
            ulong recomputed = ComputeZobristHash(s);
            if (s.hash != recomputed)
            {
                Fail("hash tutarsız: state.hash=" + s.hash.ToString("X16") + " recomputed=" + recomputed.ToString("X16"));
            }
        }

        /// <summary>Bölüm 8 madde 8: AfterStateList tutarlılığı (yalnızca Debug).</summary>
        [Conditional("DEBUG")]
        public static void SanityCheck(AfterStateList list)
        {
            if (list == null)
            {
                throw new ArgumentNullException(nameof(list));
            }

            for (int i = 0; i < list.Count; i++)
            {
                bool terminal = list.WhiteBorneOff[i] == BackgammonState.PiecesPerPlayer ||
                                list.BlackBorneOff[i] == BackgammonState.PiecesPerPlayer;

                if (list.IsTerminal[i] != terminal)
                {
                    Fail("AfterStateList[" + i + "]: IsTerminal borneOff ile tutarsız.");
                }

                if (terminal)
                {
                    if (list.ResultType[i] < 1 || list.ResultType[i] > 3)
                    {
                        Fail("AfterStateList[" + i + "]: terminal kayıtta ResultType 1..3 olmalı: " + list.ResultType[i]);
                    }

                    if (list.ResultPoints[i] < 1 || list.ResultPoints[i] > 3)
                    {
                        Fail("AfterStateList[" + i + "]: terminal kayıtta ResultPoints 1..3 olmalı: " + list.ResultPoints[i]);
                    }
                }
                else
                {
                    if (list.ResultType[i] != 0 || list.ResultPoints[i] != 0)
                    {
                        Fail("AfterStateList[" + i + "]: terminal olmayan kayıtta ResultType/ResultPoints 0 olmalı.");
                    }
                }
            }
        }

        private static int RolledDiceCount(BackgammonState s)
        {
            if (s.rolledDice[0] == 0 && s.rolledDice[1] == 0)
            {
                return 0;
            }

            return s.rolledDice[0] == s.rolledDice[1] ? 4 : 2;
        }

        private static int CountRolled(BackgammonState s, int die)
        {
            int count = 0;
            if (s.rolledDice[0] == die)
            {
                count++;
            }

            if (s.rolledDice[1] == die)
            {
                count++;
            }

            if (s.rolledDice[0] == s.rolledDice[1] && s.rolledDice[0] == die)
            {
                count += 2;
            }

            return count;
        }

        private static int CountRemaining(BackgammonState s, int die)
        {
            int count = 0;
            for (int i = 0; i < s.remainingCount; i++)
            {
                if (s.remainingDice[i] == die)
                {
                    count++;
                }
            }

            return count;
        }

        private static void Fail(string message)
        {
            throw new InvalidOperationException("SanityCheck: " + message);
        }
    }
}
