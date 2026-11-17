using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Oyun sonucunun skora islenmesi (<see cref="BackgammonEngine.ApplyResult"/>), yeni oyun
    /// hazirligi (<see cref="BackgammonEngine.PrepareNextGame"/>) ve zar geri alma
    /// (<see cref="BackgammonEngine.RevertRoll"/>) testleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Neden ayri metotlar?</b> UI, oyun bittiginde skoru <b>hemen</b> gostermeli, tahta ise
    /// son pozisyonda kalmali. Tek bir <c>StartNextGame</c> bunu yapamadigi icin sonuc isleme
    /// (<see cref="BackgammonEngine.ApplyResult"/>) ile tahta sifirlama
    /// (<see cref="BackgammonEngine.PrepareNextGame"/>) ayrildi. Bu testler iki adimin
    /// <b>tek</b> kez ve dogru sirayla uygulandigini dogrular.
    /// </para>
    /// <para>
    /// <b>RevertRoll:</b> kup kural geregi zar atmadan once teklif edilir. Oyuncu zar atip henuz
    /// tas oynamadiysa teklif penceresi yeniden acilir; bu metot o pencereyi acar.
    /// </para>
    /// </remarks>
    [TestFixture]
    public class MatchFlowSplitTests
    {
        private static BackgammonState NewMatch(int matchLength)
        {
            var s = new BackgammonState();
            BackgammonEngine.NewGame(s, new MatchSettings(matchLength));
            return s;
        }

        // ------------------------------------------------------------------
        // ApplyResult
        // ------------------------------------------------------------------

        [Test]
        public void ApplyResult_AddsPointsTimesCubeValue()
        {
            BackgammonState s = NewMatch(5);
            s.cubeValue = 2;
            s.whiteScore = 0;
            s.blackScore = 0;

            bool matchOver = BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            Assert.Multiple(() =>
            {
                Assert.That(matchOver, Is.False, "mac 5 sayi, 2 sayi maci bitirmez");
                Assert.That(s.whiteScore, Is.EqualTo(2), "1 puan x kup 2 = 2");
                Assert.That(s.blackScore, Is.EqualTo(0));
            });
        }

        [Test]
        public void ApplyResult_GammonMultipliesPoints()
        {
            BackgammonState s = NewMatch(10);
            s.cubeValue = 4;

            BackgammonEngine.ApplyResult(s, new GameResult(-1, GameResultType.Gammon, 2));

            Assert.That(s.blackScore, Is.EqualTo(8), "2 puan x kup 4 = 8");
            Assert.That(s.whiteScore, Is.EqualTo(0));
        }

        [Test]
        public void ApplyResult_ReachingMatchLength_ReturnsTrue()
        {
            BackgammonState s = NewMatch(3);
            s.whiteScore = 2;

            bool matchOver = BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            Assert.Multiple(() =>
            {
                Assert.That(matchOver, Is.True);
                Assert.That(s.whiteScore, Is.EqualTo(3));
            });
        }

        [Test]
        public void ApplyResult_MoneyGame_NeverEndsMatch()
        {
            BackgammonState s = NewMatch(0);
            s.whiteScore = 0;

            bool matchOver = BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Backgammon, 3));

            Assert.Multiple(() =>
            {
                Assert.That(matchOver, Is.False, "money game'de mac bitmez");
                Assert.That(s.whiteScore, Is.EqualTo(3));
            });
        }

        [Test]
        public void ApplyResult_CrawfordGame_MarksPlayed()
        {
            BackgammonState s = NewMatch(5);
            s.isCrawfordGame = true;
            s.crawfordPlayed = false;

            BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            Assert.Multiple(() =>
            {
                Assert.That(s.isCrawfordGame, Is.False, "Crawford oyunu oynandi");
                Assert.That(s.crawfordPlayed, Is.True);
            });
        }

        [Test]
        public void ApplyResult_InvalidWinner_Throws()
        {
            BackgammonState s = NewMatch(5);
            Assert.Throws<ArgumentException>(
                () => BackgammonEngine.ApplyResult(s, new GameResult(0, GameResultType.Single, 1)));
        }

        // ------------------------------------------------------------------
        // PrepareNextGame
        // ------------------------------------------------------------------

        [Test]
        public void PrepareNextGame_ResetsBoardAndKeepsScore()
        {
            BackgammonState s = NewMatch(5);
            s.cubeValue = 2;
            BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            BackgammonEngine.PrepareNextGame(s);

            Assert.Multiple(() =>
            {
                Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
                Assert.That(s.whiteScore, Is.EqualTo(2), "skor korunmali");
                Assert.That(s.cubeValue, Is.EqualTo(1), "kup 1'e donmeli");
                Assert.That(s.cubeOwner, Is.EqualTo(0), "kup ortaya donmeli");
                Assert.That(s.board[1], Is.EqualTo(2), "baslangic dizilimi kurulmali");
                Assert.That(s.board[24], Is.EqualTo(-2));
                Assert.That(s.whiteBorneOff, Is.EqualTo(0));
                Assert.That(s.blackBorneOff, Is.EqualTo(0));
            });
        }

        [Test]
        public void PrepareNextGame_MatchOver_KeepsGameOver()
        {
            BackgammonState s = NewMatch(1);
            BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            BackgammonEngine.PrepareNextGame(s);

            Assert.Multiple(() =>
            {
                Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver), "mac bitti, yeni oyun kurulmaz");
                Assert.That(s.whiteScore, Is.EqualTo(1));
            });
        }

        [Test]
        public void PrepareNextGame_SetsCrawfordAtMatchPoint()
        {
            BackgammonState s = NewMatch(3);
            s.whiteScore = 1;
            BackgammonEngine.ApplyResult(s, new GameResult(1, GameResultType.Single, 1));

            BackgammonEngine.PrepareNextGame(s);

            Assert.Multiple(() =>
            {
                Assert.That(s.whiteScore, Is.EqualTo(2));
                Assert.That(s.isCrawfordGame, Is.True, "mac puanina 1 kala Crawford oynanir");
                Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
            });
        }

        [Test]
        public void StartNextGame_AppliesResultOnceAndResets()
        {
            BackgammonState s = NewMatch(5);
            s.cubeValue = 2;

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.Multiple(() =>
            {
                Assert.That(s.whiteScore, Is.EqualTo(2), "sonuc bir kez islenmeli");
                Assert.That(s.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer));
                Assert.That(s.board[1], Is.EqualTo(2));
            });
        }

        [Test]
        public void StartNextGame_MatchOver_StaysGameOver()
        {
            BackgammonState s = NewMatch(1);

            BackgammonEngine.StartNextGame(s, new GameResult(1, GameResultType.Single, 1));

            Assert.Multiple(() =>
            {
                Assert.That(s.phase, Is.EqualTo(GamePhase.GameOver));
                Assert.That(s.whiteScore, Is.EqualTo(1));
            });
        }

        // ------------------------------------------------------------------
        // RevertRoll
        // ------------------------------------------------------------------

        [Test]
        public void RevertRoll_UnplayedRoll_ReturnsToPreRoll()
        {
            BackgammonState s = NewMatch(0);
            s.phase = GamePhase.PreRoll;
            BackgammonEngine.SetDice(s, 3, 5);

            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
            Assert.That(s.remainingCount, Is.EqualTo(2));

            bool reverted = BackgammonEngine.RevertRoll(s, EngineSettings.Default);

            Assert.Multiple(() =>
            {
                Assert.That(reverted, Is.True);
                Assert.That(s.phase, Is.EqualTo(GamePhase.PreRoll));
                Assert.That(s.remainingCount, Is.EqualTo(0));
                Assert.That(s.rolledDice[0], Is.EqualTo(0));
                Assert.That(s.rolledDice[1], Is.EqualTo(0));
            });
        }

        [Test]
        public void RevertRoll_DoubleUnplayedRoll_ReturnsToPreRoll()
        {
            BackgammonState s = NewMatch(0);
            s.phase = GamePhase.PreRoll;
            BackgammonEngine.SetDice(s, 4, 4);

            Assert.That(s.remainingCount, Is.EqualTo(4));
            Assert.That(BackgammonEngine.RevertRoll(s, EngineSettings.Default), Is.True);
            Assert.That(s.phase, Is.EqualTo(GamePhase.PreRoll));
        }

        [Test]
        public void RevertRoll_AfterCheckerPlayed_ReturnsFalse()
        {
            BackgammonState s = NewMatch(0);
            s.phase = GamePhase.PreRoll;
            BackgammonEngine.SetDice(s, 3, 5);
            BackgammonEngine.ApplyStep(s, new MoveStep(1, 4, 3, MoveFlags.None));

            Assert.That(s.remainingCount, Is.EqualTo(1));
            Assert.That(BackgammonEngine.RevertRoll(s, EngineSettings.Default), Is.False,
                "tas oynandiktan sonra zar geri alinamaz");
            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
        }

        [Test]
        public void RevertRoll_NotMoving_ReturnsFalse()
        {
            BackgammonState s = NewMatch(0);
            s.phase = GamePhase.PreRoll;

            Assert.That(BackgammonEngine.RevertRoll(s, EngineSettings.Default), Is.False);
            Assert.That(s.phase, Is.EqualTo(GamePhase.PreRoll));
        }

        [Test]
        public void RevertRoll_CrawfordGame_ReturnsFalse()
        {
            BackgammonState s = NewMatch(5);
            s.isCrawfordGame = true;
            s.phase = GamePhase.PreRoll;
            BackgammonEngine.SetDice(s, 3, 5);

            Assert.That(BackgammonEngine.RevertRoll(s, EngineSettings.Default), Is.False,
                "Crawford oyununda kup teklif edilemez");
            Assert.That(s.phase, Is.EqualTo(GamePhase.Moving));
        }
    }
}
