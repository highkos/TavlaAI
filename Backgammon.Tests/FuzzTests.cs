using System;
using System.Collections.Generic;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Aşama E: seed'li fuzz testleri. Bölüm 8 madde 4.
    /// </summary>
    /// <remarks>
    /// Varsayılan oyun sayısı <c>TAVLA_FUZZ_GAMES</c> ortam değişkeniyle ölçeklenir; tam
    /// 1.000.000 oyunluk koşu <see cref="Fuzz_OneMillionGames"/> (Explicit) testidir.
    /// </remarks>
    [TestFixture]
    public class FuzzTests
    {
        private const ulong DefaultSeed = 0x7A5BC0DE12345678UL;
        private const int MaxPliesPerGame = 10000;

        private static int GamesFromEnvironment(int fallback)
        {
            string raw = Environment.GetEnvironmentVariable("TAVLA_FUZZ_GAMES") ?? string.Empty;
            return int.TryParse(raw, out int n) && n > 0 ? n : fallback;
        }

        // ------------------------------------------------------------------
        // Hamle üretimi fuzz
        // ------------------------------------------------------------------

        [Test]
        public void Fuzz_SeededGames_StayConsistent()
        {
            RunMoveFuzz(GamesFromEnvironment(2000), DefaultSeed);
        }

        [Test]
        [Explicit("1.000.000 oyun — uzun sürer. TAVLA_FUZZ_GAMES ile ölçeklenir.")]
        public void Fuzz_OneMillionGames()
        {
            RunMoveFuzz(1_000_000, DefaultSeed);
        }

        /// <summary>
        /// Her turda: <c>GenerateAfterStates</c> ile <c>GenerateAllLegalMoves</c> aynı sayı ve sırada mı,
        /// afterstate hash'leri tekilleştirilmiş mi, <c>ApplyMove</c> sonrası hash/borneOff afterstate ile
        /// birebir mi, <c>ApplyMove</c> → <c>UndoMove</c> özdeşliği sağlanıyor mu, <c>SanityCheck</c> geçiyor mu.
        /// </summary>
        private static void RunMoveFuzz(int games, ulong seed)
        {
            var rng = new Xoshiro256StarStar(seed);
            var s = new BackgammonState();
            var moves = new MoveList();
            var afterStates = new AfterStateList();
            var seen = new HashSet<ulong>();
            var es = EngineSettings.Default;

            long totalPlies = 0;
            long totalSteps = 0;
            long totalAfterStates = 0;
            int maxPlies = 0;

            for (int g = 0; g < games; g++)
            {
                BackgammonEngine.NewGame(s, MatchSettings.MoneyGame);
                BackgammonEngine.RollOpening(s, rng);
                BackgammonEngine.SanityCheck(s);

                int plies = 0;

                while (true)
                {
                    if (++plies > MaxPliesPerGame)
                    {
                        Assert.Fail("Oyun " + g + " (seed " + seed + ") " + MaxPliesPerGame + " turda bitmedi.");
                    }

                    LegalMoveGenerator.GenerateAfterStates(s, es, afterStates);
                    LegalMoveGenerator.GenerateAllLegalMoves(s, moves);

                    Assert.That(moves.Count, Is.EqualTo(afterStates.Count),
                        "Oyun " + g + " tur " + plies + ": GenerateAllLegalMoves ve GenerateAfterStates sayıları farklı.");

                    if (moves.Count == 0)
                    {
                        BackgammonEngine.PassTurn(s);
                        BackgammonEngine.SanityCheck(s);
                        BackgammonEngine.RollDice(s, rng);
                        continue;
                    }

                    // Aynı sıra ve aynı diziler.
                    for (int i = 0; i < moves.Count; i++)
                    {
                        MoveSequence a = moves[i];
                        MoveSequence b = afterStates.Sequences[i];
                        Assert.That(a.Count, Is.EqualTo(b.Count), "Oyun " + g + " tur " + plies + ": dizi uzunluğu farklı (kayıt " + i + ").");

                        for (int k = 0; k < a.Count; k++)
                        {
                            Assert.That(a[k].From, Is.EqualTo(b[k].From));
                            Assert.That(a[k].To, Is.EqualTo(b[k].To));
                            Assert.That(a[k].Die, Is.EqualTo(b[k].Die));
                            Assert.That(a[k].Flags, Is.EqualTo(b[k].Flags));
                        }
                    }

                    // Tekilleştirme: afterstate hash'leri benzersiz olmalı.
                    seen.Clear();
                    for (int i = 0; i < afterStates.Count; i++)
                    {
                        Assert.That(seen.Add(afterStates.Hash[i]), Is.True,
                            "Oyun " + g + " tur " + plies + ": yinelenen afterstate hash'i (kayıt " + i + ").");
                    }

                    totalAfterStates += afterStates.Count;

                    int pick = (int)(rng.NextUInt() % (uint)moves.Count);
                    MoveSequence chosen = moves[pick];

                    ulong beforeHash = s.hash;
                    byte beforeWhite = s.whiteBorneOff;
                    byte beforeBlack = s.blackBorneOff;
                    byte beforeRemaining = s.remainingCount;
                    byte rd0 = s.remainingDice[0];
                    byte rd1 = s.remainingDice[1];
                    byte rd2 = s.remainingDice[2];
                    byte rd3 = s.remainingDice[3];

                    // Apply → Undo özdeşliği (Bölüm 8 madde 3).
                    BackgammonEngine.ApplyMove(s, chosen);
                    BackgammonEngine.UndoMove(s, chosen);

                    Assert.That(s.hash, Is.EqualTo(beforeHash), "Oyun " + g + " tur " + plies + ": Apply→Undo sonrası hash değişti.");
                    Assert.That(s.whiteBorneOff, Is.EqualTo(beforeWhite));
                    Assert.That(s.blackBorneOff, Is.EqualTo(beforeBlack));
                    Assert.That(s.remainingCount, Is.EqualTo(beforeRemaining));
                    Assert.That(s.remainingDice[0], Is.EqualTo(rd0));
                    Assert.That(s.remainingDice[1], Is.EqualTo(rd1));
                    Assert.That(s.remainingDice[2], Is.EqualTo(rd2));
                    Assert.That(s.remainingDice[3], Is.EqualTo(rd3));

                    // Gerçek hamle.
                    BackgammonEngine.ApplyMove(s, chosen);
                    totalSteps += chosen.Count;

                    Assert.That(s.hash, Is.EqualTo(afterStates.Hash[pick]),
                        "Oyun " + g + " tur " + plies + ": ApplyMove hash'i afterstate hash'i ile uyuşmuyor.");
                    Assert.That(s.whiteBorneOff, Is.EqualTo(afterStates.WhiteBorneOff[pick]));
                    Assert.That(s.blackBorneOff, Is.EqualTo(afterStates.BlackBorneOff[pick]));

                    BackgammonEngine.SanityCheck(s);

                    if (s.phase == GamePhase.GameOver)
                    {
                        break;
                    }

                    BackgammonEngine.EndTurn(s, es);
                    BackgammonEngine.SanityCheck(s);
                    BackgammonEngine.RollDice(s, rng);
                }

                GameResult result;
                Assert.That(BackgammonEngine.IsGameOver(s, out result), Is.True, "Oyun " + g + " GameOver fazında ama IsGameOver false.");
                Assert.That(result.Winner, Is.EqualTo(1).Or.EqualTo(-1));

                BackgammonEngine.StartNextGame(s, result);
                BackgammonEngine.SanityCheck(s);

                totalPlies += plies;
                if (plies > maxPlies)
                {
                    maxPlies = plies;
                }
            }

            TestContext.Progress.WriteLine(
                "Fuzz: " + games + " oyun, " + totalPlies + " tur, " + totalSteps + " adım, " +
                totalAfterStates + " afterstate, en uzun oyun " + maxPlies + " tur (seed " + seed + ").");
        }

        // ------------------------------------------------------------------
        // Maç / küp / Crawford fuzz
        // ------------------------------------------------------------------

        [Test]
        public void Fuzz_MatchFlow_CrawfordAndCube()
        {
            RunMatchFuzz(GamesFromEnvironment(300), 0xC0FFEE_5EEDUL);
        }

        /// <summary>
        /// Rastgele maçlar oynar; her oyun sonunda <c>StartNextGame</c> ile skor/Crawford/küp geçişlerini
        /// ilerletir ve Crawford oyununun bir maçta en fazla bir kez oynandığını doğrular.
        /// </summary>
        private static void RunMatchFuzz(int matches, ulong seed)
        {
            var rng = new Xoshiro256StarStar(seed);
            var s = new BackgammonState();
            var moves = new MoveList();
            var es = EngineSettings.Default;

            int crawfordGames = 0;
            int cubeOffers = 0;
            int cubeTakes = 0;
            int cubePasses = 0;

            for (int m = 0; m < matches; m++)
            {
                int matchLength = 1 + (int)(rng.NextUInt() % 9u);
                BackgammonEngine.NewGame(s, new MatchSettings(matchLength));
                BackgammonEngine.RollOpening(s, rng);

                int crawfordThisMatch = 0;
                int gamesThisMatch = 0;

                while (s.phase != GamePhase.GameOver)
                {
                    if (++gamesThisMatch > 200)
                    {
                        Assert.Fail("Maç " + m + " (seed " + seed + ") 200 oyunda bitmedi.");
                    }

                    if (s.isCrawfordGame)
                    {
                        crawfordThisMatch++;
                        Assert.That(s.cubeValue, Is.EqualTo(1), "Crawford oyununda küp 1 olmalı.");
                        Assert.That(s.cubeOwner, Is.EqualTo(0), "Crawford oyununda küp ortada olmalı.");
                    }

                    PlayOneGame(s, rng, moves, es, ref cubeOffers, ref cubeTakes, ref cubePasses, out GameResult result);

                    Assert.That(result.Winner, Is.EqualTo(1).Or.EqualTo(-1));
                    BackgammonEngine.StartNextGame(s, result);
                    BackgammonEngine.SanityCheck(s);
                }

                Assert.That(crawfordThisMatch, Is.LessThanOrEqualTo(1),
                    "Maç " + m + ": Crawford oyunu birden fazla kez oynandı.");
                Assert.That(s.whiteScore >= matchLength || s.blackScore >= matchLength, Is.True,
                    "Maç " + m + ": skor matchLength'e ulaşmadan bitti.");

                crawfordGames += crawfordThisMatch;
            }

            TestContext.Progress.WriteLine(
                "Maç fuzz: " + matches + " maç, " + crawfordGames + " Crawford oyunu, " +
                cubeOffers + " küp teklifi (" + cubeTakes + " kabul, " + cubePasses + " red).");
        }

        /// <summary>Tek bir oyunu rastgele oynar (küp kararları dahil) ve sonucu döndürür.</summary>
        private static void PlayOneGame(
            BackgammonState s,
            IRandom rng,
            MoveList moves,
            in EngineSettings es,
            ref int cubeOffers,
            ref int cubeTakes,
            ref int cubePasses,
            out GameResult result)
        {
            int plies = 0;

            while (true)
            {
                if (++plies > MaxPliesPerGame)
                {
                    Assert.Fail("Oyun " + MaxPliesPerGame + " turda bitmedi.");
                }

                if (s.phase == GamePhase.DetermineFirstPlayer)
                {
                    BackgammonEngine.RollOpening(s, rng);
                    BackgammonEngine.SanityCheck(s);
                }

                if (s.phase == GamePhase.PreRoll && BackgammonEngine.CanOffer(s, es))
                {
                    // Küp teklifi olasılığı düşük tutulur ki maçlar makul sürede bitsin.
                    if (rng.NextUInt() % 8u == 0u)
                    {
                        BackgammonEngine.OfferDouble(s);
                        cubeOffers++;

                        if (rng.NextUInt() % 2u == 0u)
                        {
                            BackgammonEngine.Take(s);
                            cubeTakes++;
                            BackgammonEngine.SanityCheck(s);
                        }
                        else
                        {
                            result = BackgammonEngine.Pass(s);
                            cubePasses++;
                            BackgammonEngine.SanityCheck(s);
                            Assert.That(result.Winner, Is.EqualTo(s.turn));
                            Assert.That(result.Points, Is.EqualTo(1));
                            return;
                        }
                    }
                }

                if (s.phase == GamePhase.PreRoll || s.phase == GamePhase.WaitForRoll)
                {
                    BackgammonEngine.RollDice(s, rng);
                }

                LegalMoveGenerator.GenerateAllLegalMoves(s, moves);

                if (moves.Count == 0)
                {
                    BackgammonEngine.PassTurn(s);
                    BackgammonEngine.SanityCheck(s);
                    continue;
                }

                int pick = (int)(rng.NextUInt() % (uint)moves.Count);
                BackgammonEngine.ApplyMove(s, moves[pick]);
                BackgammonEngine.SanityCheck(s);

                if (s.phase == GamePhase.GameOver)
                {
                    Assert.That(BackgammonEngine.IsGameOver(s, out result), Is.True);
                    return;
                }

                BackgammonEngine.EndTurn(s, es);
                BackgammonEngine.SanityCheck(s);
            }
        }
    }
}
