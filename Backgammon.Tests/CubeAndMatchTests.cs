using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Aşama D: küp (teklif/kabul/red), ölü küp, Crawford, maç akışı.</summary>
    [TestFixture]
    public class CubeAndMatchTests
    {
        // ------------------------------------------------------------------
        // Yardımcılar
        // ------------------------------------------------------------------

        private static void AssertHashConsistent(BackgammonState s)
        {
            Assert.That(s.hash, Is.EqualTo(BackgammonEngine.ComputeZobristHash(s)), "Artımlı hash tam hash ile uyuşmuyor.");
        }

        /// <summary>Yeni maç kurar ve fazı <see cref="GamePhase.PreRoll"/>'a çeker (küp teklifi için).</summary>
        private static BackgammonState NewMatch(int matchLength)
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, new MatchSettings(matchLength));
            s.phase = GamePhase.PreRoll;
            return s;
        }

        private static EngineSettings DeadCubeAllowed()
        {
            var es = EngineSettings.Default;
            es.DisallowDeadCube = false;
            return es;
        }

        // ------------------------------------------------------------------
        // CanOffer
        // ------------------------------------------------------------------

        [Test]
        public void CanOffer_True_AtPreRollWithCenteredCube()
        {
            var s = NewMatch(0);
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
        }

        [Test]
        public void CanOffer_False_WhenPhaseIsNotPreRoll()
        {
            var s = NewMatch(0);
            s.phase = GamePhase.WaitForRoll;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);

            s.phase = GamePhase.Moving;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);

            s.phase = GamePhase.CubeOffered;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);
        }

        [Test]
        public void CanOffer_False_WhenCubeOwnedByOpponent()
        {
            var s = NewMatch(0);
            s.turn = 1;
            s.cubeOwner = -1;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);
        }

        [Test]
        public void CanOffer_True_WhenCubeOwnedBySelf()
        {
            var s = NewMatch(0);
            s.turn = 1;
            s.cubeOwner = 1;
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
        }

        [Test]
        public void CanOffer_False_InCrawfordGame()
        {
            var s = NewMatch(5);
            s.isCrawfordGame = true;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);
        }

        [Test]
        public void CanOffer_False_WhenDeadCube()
        {
            // matchLength 5, teklif eden 4 puanda, küp 1 => 1 >= 5 - 4 = 1 => ölü küp.
            var s = NewMatch(5);
            s.turn = 1;
            s.whiteScore = 4;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);
        }

        [Test]
        public void CanOffer_True_WhenDeadCubeRuleDisabled()
        {
            var s = NewMatch(5);
            s.turn = 1;
            s.whiteScore = 4;
            Assert.That(BackgammonEngine.CanOffer(s, DeadCubeAllowed()), Is.True);
        }

        [Test]
        public void CanOffer_True_WhenCubeBelowDeadCubeThreshold()
        {
            // matchLength 5, teklif eden 3 puanda, küp 1 => 1 >= 2 değil => teklif serbest.
            var s = NewMatch(5);
            s.turn = 1;
            s.whiteScore = 3;
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
        }

        [Test]
        public void CanOffer_DeadCubeRuleIgnoredInMoneyGame()
        {
            var s = NewMatch(0);
            s.turn = 1;
            s.whiteScore = 100;
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
        }

        // ------------------------------------------------------------------
        // OfferDouble
        // ------------------------------------------------------------------

        [Test]
        public void OfferDouble_SetsCubeOfferedPhase()
        {
            var s = NewMatch(0);
            BackgammonEngine.OfferDouble(s);

            Assert.That(s.phase, Is.EqualTo(GamePhase.CubeOffered));
            Assert.That(s.cubeValue, Is.EqualTo(1), "Teklif küp değerini değiştirmemeli.");
            Assert.That(s.cubeOwner, Is.EqualTo(0));
            AssertHashConsistent(s);
        }

        [Test]
        public void OfferDouble_Throws_WhenNotAllowed()
        {
            var s = NewMatch(0);
            s.phase = GamePhase.Moving;
            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.OfferDouble(s));
        }

        [Test]
        public void OfferDouble_Throws_InCrawfordGame()
        {
            var s = NewMatch(5);
            s.isCrawfordGame = true;
            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.OfferDouble(s));
        }

        // ------------------------------------------------------------------
        // Take
        // ------------------------------------------------------------------

        [Test]
        public void Take_DoublesCubeAndGivesOwnershipToTaker()
        {
            var s = NewMatch(0);
            s.turn = 1;

            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Take(s);

            Assert.That(s.cubeValue, Is.EqualTo(2));
            Assert.That(s.cubeOwner, Is.EqualTo(-1), "Küp sahibi alan oyuncu (teklif edenin rakibi) olmalı.");
            Assert.That(s.phase, Is.EqualTo(GamePhase.WaitForRoll), "Teklif eden oyuncu zar atmalı.");
            AssertHashConsistent(s);
        }

        [Test]
        public void Take_RepeatedDoubles_KeepCubePowerOfTwo()
        {
            var s = NewMatch(0);

            s.turn = 1;
            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Take(s);
            Assert.That(s.cubeValue, Is.EqualTo(2));

            // Küp artık Siyah'ta; Beyaz teklif edemez.
            s.turn = 1;
            s.phase = GamePhase.PreRoll;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);

            // Siyah teklif edebilir.
            s.turn = -1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Take(s);

            Assert.That(s.cubeValue, Is.EqualTo(4));
            Assert.That(s.cubeOwner, Is.EqualTo(1));
            AssertHashConsistent(s);
        }

        [Test]
        public void Take_ThenEndTurn_OnlyCubeOwnerMayOffer()
        {
            var s = NewMatch(0);
            s.turn = 1;

            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Take(s);

            // Küpü alan Siyah'tır; teklif eden Beyaz küpü bir daha teklif edemez.
            s.phase = GamePhase.PreRoll;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);

            BackgammonEngine.EndTurn(s);

            Assert.That(s.turn, Is.EqualTo(-1));
            Assert.That(s.phase, Is.EqualTo(GamePhase.PreRoll), "Küp Siyah'ta olduğu için Siyah teklif edebilir.");
            Assert.That(BackgammonEngine.CanOffer(s), Is.True);
        }

        // ------------------------------------------------------------------
        // Pass
        // ------------------------------------------------------------------

        [Test]
        public void Pass_ReturnsSingleWinForOfferer()
        {
            var s = NewMatch(0);
            s.turn = 1;

            BackgammonEngine.OfferDouble(s);
            GameResult r = BackgammonEngine.Pass(s);

            Assert.That(r.Winner, Is.EqualTo(1));
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Single));
            Assert.That(r.Points, Is.EqualTo(1), "Points mars çarpanıdır; cubeValue hariç.");
        }

        [Test]
        public void Pass_DoesNotChangeCubeValue()
        {
            var s = NewMatch(0);
            s.turn = 1;
            s.cubeValue = 4;
            s.cubeOwner = 1;

            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Pass(s);

            Assert.That(s.cubeValue, Is.EqualTo(4), "Reddedilen teklif küpü büyütmemeli.");
            Assert.That(s.cubeOwner, Is.EqualTo(1));
        }

        [Test]
        public void Pass_SetsGameOverAndCubePassed()
        {
            var s = NewMatch(0);
            s.turn = -1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Pass(s);

            Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver));
            Assert.That(s.cubePassed, Is.True);
            AssertHashConsistent(s);
            BackgammonEngine.SanityCheck(s);
        }

        [Test]
        public void Pass_ThenStartNextGame_AddsCubeValueToScore()
        {
            var s = NewMatch(0);
            s.turn = 1;
            s.cubeValue = 4;
            s.cubeOwner = 1;

            BackgammonEngine.OfferDouble(s);
            GameResult r = BackgammonEngine.Pass(s);
            BackgammonEngine.StartNextGame(s, r);

            Assert.That(s.whiteScore, Is.EqualTo(4), "Skor = Points (1) * cubeValue (4).");
            Assert.That(s.blackScore, Is.EqualTo(0));
            Assert.That(s.cubePassed, Is.False, "Yeni oyun cubePassed bayrağını temizlemeli.");
        }

        // ------------------------------------------------------------------
        // StartNextGame
        // ------------------------------------------------------------------

        [Test]
        public void StartNextGame_AppliesCubeValueToScore()
        {
            var s = NewMatch(0);
            s.cubeValue = 2;
            s.cubeOwner = -1;

            BackgammonEngine.StartNextGame(s, new GameResult(-1, GameResultType.Gammon, 2));

            Assert.That(s.blackScore, Is.EqualTo(4), "Skor = Points (2) * cubeValue (2).");
            Assert.That(s.whiteScore, Is.EqualTo(0));
        }

        [Test]
        public void StartNextGame_ResetsBoardAndCube()
        {
            var s = NewMatch(0);
            s.board[1] = 0;
            s.board[6] = 0;
            s.whiteBorneOff = 15;
            s.cubeValue = 8;
            s.cubeOwner = 1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.whiteBorneOff, Is.EqualTo(0));
            Assert.That(s.blackBorneOff, Is.EqualTo(0));
            Assert.That(s.board[1], Is.EqualTo(2));
            Assert.That(s.board[12], Is.EqualTo(5));
            Assert.That(s.board[17], Is.EqualTo(3));
            Assert.That(s.board[19], Is.EqualTo(5));
            Assert.That(s.board[24], Is.EqualTo(-2));
            Assert.That(s.board[13], Is.EqualTo(-5));
            Assert.That(s.board[8], Is.EqualTo(-3));
            Assert.That(s.board[6], Is.EqualTo(-5));
            Assert.That(s.cubeValue, Is.EqualTo(1));
            Assert.That(s.cubeOwner, Is.EqualTo(0));
            Assert.That(s.turn, Is.EqualTo(1));
            Assert.That(s.remainingCount, Is.EqualTo(0));
            Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
            AssertHashConsistent(s);
            BackgammonEngine.SanityCheck(s);
        }

        [Test]
        public void StartNextGame_KeepsScoresAndMatchLength()
        {
            var s = NewMatch(7);
            s.whiteScore = 2;
            s.blackScore = 3;

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.matchLength, Is.EqualTo(7));
            Assert.That(s.whiteScore, Is.EqualTo(3));
            Assert.That(s.blackScore, Is.EqualTo(3));
        }

        [Test]
        public void StartNextGame_MatchEnd_KeepsBoardAndGameOver()
        {
            var s = NewMatch(1);
            s.whiteBorneOff = 15;
            s.board[1] = 0;
            s.board[12] = 0;
            s.board[17] = 0;
            s.board[19] = 0;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.whiteScore, Is.EqualTo(1));
            Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver));
            Assert.That(s.whiteBorneOff, Is.EqualTo(15), "Maç bitince tahta sıfırlanmamalı.");
            AssertHashConsistent(s);
        }

        [Test]
        public void StartNextGame_InvalidWinner_Throws()
        {
            var s = NewMatch(0);
            Assert.Throws<ArgumentException>(() => BackgammonEngine.StartNextGame(s, default(GameResult)));
        }

        [Test]
        public void StartNextGame_MoneyGame_NeverEnds()
        {
            var s = NewMatch(0);
            s.whiteScore = 1000;

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
            Assert.That(s.whiteScore, Is.EqualTo(1001));
        }

        // ------------------------------------------------------------------
        // Crawford
        // ------------------------------------------------------------------

        [Test]
        public void Crawford_TriggeredAtMatchPointMinusOne()
        {
            var s = NewMatch(5);
            s.whiteScore = 3;

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.whiteScore, Is.EqualTo(4));
            Assert.That(s.isCrawfordGame, Is.True);
            Assert.That(s.crawfordPlayed, Is.False);
            Assert.That(s.cubeValue, Is.EqualTo(1));
            Assert.That(s.cubeOwner, Is.EqualTo(0));
            BackgammonEngine.SanityCheck(s);
        }

        [Test]
        public void Crawford_TriggeredForBlackToo()
        {
            var s = NewMatch(5);
            s.blackScore = 3;

            BackgammonEngine.StartNextGame(s, new GameResult(-1, GameResultType.Single, 1));

            Assert.That(s.blackScore, Is.EqualTo(4));
            Assert.That(s.isCrawfordGame, Is.True);
        }

        [Test]
        public void Crawford_NotTriggeredForMatchLengthOne()
        {
            var s = NewMatch(1);

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.isCrawfordGame, Is.False);
            Assert.That(s.crawfordPlayed, Is.False);
            Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver), "matchLength 1'de ilk galibiyet maçı bitirir.");
        }

        [Test]
        public void Crawford_NotTriggeredInMoneyGame()
        {
            var s = NewMatch(0);
            s.whiteScore = 3;

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.isCrawfordGame, Is.False);
        }

        [Test]
        public void Crawford_PlayedOnceOnly()
        {
            var s = NewMatch(5);
            s.whiteScore = 3;

            // 4-0: Crawford oyunu başlar.
            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));
            Assert.That(s.isCrawfordGame, Is.True);

            // Crawford oyununu Siyah kazanır: 4-1, Crawford biter.
            BackgammonEngine.StartNextGame(s, new GameResult(-1, GameResultType.Single, 1));
            Assert.That(s.isCrawfordGame, Is.False);
            Assert.That(s.crawfordPlayed, Is.True);
            Assert.That(s.whiteScore, Is.EqualTo(4));
            Assert.That(s.blackScore, Is.EqualTo(1));

            // Skor yine matchLength - 1'de ama Crawford bir daha oynanmaz.
            BackgammonEngine.StartNextGame(s, new GameResult(-1, GameResultType.Single, 1));
            Assert.That(s.isCrawfordGame, Is.False);
            Assert.That(s.blackScore, Is.EqualTo(2));
        }

        [Test]
        public void Crawford_NoCubeInCrawfordGame()
        {
            var s = NewMatch(5);
            s.whiteScore = 3;
            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.That(s.isCrawfordGame, Is.True);
            s.phase = GamePhase.PreRoll;
            Assert.That(BackgammonEngine.CanOffer(s), Is.False);
            Assert.Throws<InvalidOperationException>(() => BackgammonEngine.OfferDouble(s));
        }

        [Test]
        public void FullMatch_CrawfordAppearsExactlyOnce()
        {
            var s = NewMatch(5);
            int crawfordGames = 0;
            int games = 0;

            // Sırayla tek puanlık galibiyetler: Beyaz, Siyah, Beyaz, Siyah, ...
            while (s.phase != GamePhase.GameOver && games < 50)
            {
                if (s.isCrawfordGame)
                {
                    crawfordGames++;
                }

                sbyte winner = (sbyte)(games % 2 == 0 ? 1 : -1);
                BackgammonEngine.StartNextGame(s, new GameResult(winner, GameResultType.Single, 1));
                games++;
            }

            Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver), "Maç bitmeliydi.");
            Assert.That(crawfordGames, Is.EqualTo(1), "Crawford oyunu tam olarak bir kez oynanmalı.");
            Assert.That(s.whiteScore >= 5 || s.blackScore >= 5, Is.True);
        }

        // ------------------------------------------------------------------
        // Küp + oyun sonu entegrasyonu
        // ------------------------------------------------------------------

        [Test]
        public void Take_ThenGameEnd_ScoreUsesDoubledCube()
        {
            var s = NewMatch(0);
            s.turn = 1;

            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Take(s);
            Assert.That(s.cubeValue, Is.EqualTo(2));

            // Beyaz 15 taş topladı, Siyah hiç toplamadı ve rakip evinde taşı yok => Gammon.
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            s.whiteBorneOff = 15;
            s.board[1] = -15;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            GameResult r;
            Assert.That(BackgammonEngine.IsGameOver(s, out r), Is.True);
            Assert.That(r.ResultType, Is.EqualTo(GameResultType.Gammon));
            Assert.That(r.Points, Is.EqualTo(2));

            BackgammonEngine.StartNextGame(s, r);

            Assert.That(s.whiteScore, Is.EqualTo(4), "Skor = Points (2) * cubeValue (2).");
            Assert.That(s.cubeValue, Is.EqualTo(1));
            Assert.That(s.cubeOwner, Is.EqualTo(0));
        }

        [Test]
        public void CubeOperations_KeepHashIncremental()
        {
            var s = NewMatch(0);
            s.turn = -1;
            s.cubeValue = 2;
            s.cubeOwner = -1;
            s.hash = BackgammonEngine.ComputeZobristHash(s);

            BackgammonEngine.OfferDouble(s);
            AssertHashConsistent(s);

            BackgammonEngine.Take(s);
            AssertHashConsistent(s);

            s.turn = 1;
            s.phase = GamePhase.PreRoll;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            BackgammonEngine.OfferDouble(s);
            BackgammonEngine.Pass(s);
            AssertHashConsistent(s);
        }
    }
}
