using System;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Ikinci tur oynanis hatalarinin regresyon testleri (mac skoru, kup degeri, renk, bloke zar).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Hata 1:</b> cok sayili macta "Yeni oyun" <see cref="BackgammonEngine.NewGame"/> cagiriyordu;
    /// bu metot <see cref="BackgammonState.Reset"/> uzerinden skoru <c>0-0</c> yapiyordu. Artik
    /// skoru koruyan <see cref="BackgammonEngine.PrepareNextGame"/> kullanilir.
    /// </para>
    /// <para>
    /// <b>Hata 2:</b> kup teklif edilirken <see cref="BackgammonState.cubeValue"/> henuz
    /// katlanmadigi icin ekranda "1" gorunuyordu; <see cref="CubeViewModel.DisplayValue"/> teklif
    /// fazinda <c>Value * 2</c> dondurur.
    /// </para>
    /// <para>
    /// <b>Hata 6:</b> oyuncu Siyah oynarken toplama tepsisi sag ustte kaliyordu;
    /// <see cref="BoardLayout.Calculate(float, float, bool)"/> dikey aynalama ile tepsileri
    /// degistirir.
    /// </para>
    /// <para>
    /// <b>Hata 4:</b> zar bloke oldugunda sira gecmiyordu; <see cref="GameOrchestrator.HasLegalMoves"/>
    /// bu durumu bildirir.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix2Tests
    {
        private static GameOrchestratorOptions Options(ulong seed)
        {
            return new GameOrchestratorOptions
            {
                Evaluator = new FakeEvaluator(),
                Bearoff = null,
                Met = null,
                Distribution = null,
                SearchSettings = SearchSettings.Default,
                EngineSettings = EngineSettings.Default,
                Random = new Xoshiro256StarStar(seed),
                MaxPlies = 0
            };
        }

        // ------------------------------------------------------------------
        // Hata 1: cok sayili macta "Yeni oyun" skoru silmemeli
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_NewGame_PreservesMatchScore()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0051UL)))
            {
                orchestrator.NewMatch(5, false);
                AdvanceToPreRoll(orchestrator);

                Assert.That(orchestrator.TryOfferDouble(), Is.True);
                orchestrator.Pass();

                int scored = orchestrator.State.whiteScore + orchestrator.State.blackScore;
                Assert.That(scored, Is.EqualTo(1), "kup reddi 1 sayi kazandirmali");

                orchestrator.NewGame();

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.whiteScore + orchestrator.State.blackScore,
                                Is.EqualTo(scored), "Yeni oyun skoru silmemeli");
                    Assert.That(orchestrator.State.matchLength, Is.EqualTo(5), "mac uzunlugu korunmali");
                    Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.DetermineFirstPlayer),
                                "yeni oyun acilis fazinda baslamali");
                    Assert.That(orchestrator.IsGameOver, Is.False);
                });
            }
        }

        [Test]
        public void GameOrchestrator_NewGame_AfterMatchOver_StartsFreshMatch()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0052UL)))
            {
                orchestrator.NewMatch(2, false);
                AdvanceToPreRoll(orchestrator);
                Assert.That(orchestrator.TryOfferDouble(), Is.True);
                orchestrator.Pass();

                Assert.That(orchestrator.State.whiteScore + orchestrator.State.blackScore,
                            Is.EqualTo(1), "ilk oyun 1 sayi");

                // Mac 2 sayilik: skoru hedefe tasiyarak "mac bitti" durumunu kur.
                // (Ikinci oyun Crawford olacagi icin kup orada olu; bu yuzden skor
                // dogrudan hedefe tasinir.)
                orchestrator.State.whiteScore = 2;

                orchestrator.NewGame();

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.whiteScore + orchestrator.State.blackScore,
                                Is.EqualTo(0), "mac bittiyse yeni mac sifirdan baslamali");
                    Assert.That(orchestrator.State.matchLength, Is.EqualTo(2));
                    Assert.That(orchestrator.IsGameOver, Is.False);
                });
            }
        }

        // ------------------------------------------------------------------
        // Hata 2: teklif fazinda kup katlanmis degeri gostermeli
        // ------------------------------------------------------------------

        [Test]
        public void CubeViewModel_Offered_ShowsDoubledValue()
        {
            var state = UiTestSupport.InitialState();
            state.matchLength = 5;
            state.cubeValue = 1;
            state.cubeOwner = 0;
            state.turn = 1;
            state.phase = GamePhase.PreRoll;

            Assert.That(BackgammonEngine.CanOffer(state, EngineSettings.Default), Is.True);
            BackgammonEngine.OfferDouble(state);

            var model = new CubeViewModel();
            model.Update(state);

            Assert.Multiple(() =>
            {
                Assert.That(model.Visibility, Is.EqualTo(CubeVisibility.Offered));
                Assert.That(model.Value, Is.EqualTo(1), "motor degeri teklif sirasinda degismez");
                Assert.That(model.DisplayValue, Is.EqualTo(2),
                            "teklif ekranda katlanmis degeri gostermeli");
            });
        }

        [Test]
        public void CubeViewModel_Taken_ShowsDoubledValue()
        {
            var state = UiTestSupport.InitialState();
            state.matchLength = 5;
            state.cubeValue = 1;
            state.cubeOwner = 0;
            state.turn = 1;
            state.phase = GamePhase.PreRoll;

            BackgammonEngine.OfferDouble(state);
            BackgammonEngine.Take(state);

            var model = new CubeViewModel();
            model.Update(state);

            Assert.Multiple(() =>
            {
                Assert.That(model.Value, Is.EqualTo(2), "kabul edilince kup 2 olmali");
                Assert.That(model.DisplayValue, Is.EqualTo(2));
                Assert.That(model.Owner, Is.EqualTo(-1), "kup teklif edene gecmeli");
            });
        }

        // ------------------------------------------------------------------
        // Hata 6: toplama tepsisi her renkte sag altta
        // ------------------------------------------------------------------

        [Test]
        public void BoardLayout_Default_WhiteTrayBottomRight()
        {
            BoardLayout layout = BoardLayout.Calculate(1000f, 500f);

            Assert.Multiple(() =>
            {
                Assert.That(layout.WhiteTray.Y, Is.EqualTo(250f), "Beyaz tepsi alt yarida");
                Assert.That(layout.BlackTray.Y, Is.EqualTo(0f), "Siyah tepsi ust yarida");
                Assert.That(layout.WhiteTray.X, Is.GreaterThan(800f), "tepsiler sagda");

                // Hane 1 alt satirda, hane 24 ust satirda. Orta bant eklendigi icin
                // satirlar tam yaridan baslamaz; olcut bantin hangi tarafinda oldugudur.
                Assert.That(layout.PointAt(1).Y, Is.GreaterThanOrEqualTo(layout.CenterBand.Bottom),
                            "hane 1 alt satirda");
                Assert.That(layout.PointAt(24).Bottom, Is.LessThanOrEqualTo(layout.CenterBand.Y),
                            "hane 24 ust satirda");
            });
        }

        [Test]
        public void BoardLayout_HumanTrayBottom_BlackTrayBottomRight()
        {
            BoardLayout layout = BoardLayout.Calculate(1000f, 500f, true);

            Assert.Multiple(() =>
            {
                Assert.That(layout.BlackTray.Y, Is.EqualTo(250f),
                            "Siyah oynarken Siyah tepsi alt yarida olmali");
                Assert.That(layout.WhiteTray.Y, Is.EqualTo(0f));
                Assert.That(layout.BlackTray.X, Is.GreaterThan(800f), "tepsiler sagda");

                // Hane yerlesimi renkten BAGIMSIZ olmali: tahta yer degistirmemeli.
                Assert.That(layout.PointAt(1).Y, Is.GreaterThanOrEqualTo(layout.CenterBand.Bottom),
                            "hane 1 alt satirda kalmali");
                Assert.That(layout.PointAt(24).Bottom, Is.LessThanOrEqualTo(layout.CenterBand.Y),
                            "hane 24 ust satirda kalmali");
            });
        }

        [Test]
        public void BoardLayout_HumanTrayBottom_KeepsPointsDisjoint()
        {
            BoardLayout layout = BoardLayout.Calculate(1000f, 500f, true);

            for (int a = 1; a <= BoardLayout.PointCount; a++)
            {
                for (int b = a + 1; b <= BoardLayout.PointCount; b++)
                {
                    Assert.That(layout.PointAt(a).Overlaps(layout.PointAt(b)), Is.False,
                                "hane " + a + " ile " + b + " kesis memeli");
                }
            }
        }

        // ------------------------------------------------------------------
        // Hata 4: bloke zar -> yasal hamle yok
        // ------------------------------------------------------------------

        [Test]
        public void GameOrchestrator_HasLegalMoves_FalseWhenBlocked()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0053UL)))
            {
                orchestrator.NewMatch(0, false);

                BackgammonState state = orchestrator.State;
                var white = new int[25];
                var black = new int[25];
                white[1] = 15;
                black[2] = 2;
                black[3] = 2;
                black[4] = 2;
                black[5] = 2;
                black[6] = 2;
                black[7] = 2;
                black[8] = 3;
                UiTestSupport.SetBoard(state, white, black);
                state.turn = 1;
                state.phase = GamePhase.WaitForRoll;

                // Beyaz 1-2 atar: 1 -> 2 ve 1 -> 3 ikisi de Siyah tarafindan bloke.
                orchestrator.SetDice(1, 2);

                Assert.Multiple(() =>
                {
                    Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving));
                    Assert.That(orchestrator.HasLegalMoves, Is.False, "bloke zarda yasal hamle olmamali");
                });
            }
        }

        [Test]
        public void GameOrchestrator_HasLegalMoves_TrueInOpeningPosition()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x7A71A_0054UL)))
            {
                orchestrator.NewMatch(0, false);
                AdvanceToPreRoll(orchestrator);
                orchestrator.RollDice();

                Assert.That(orchestrator.HasLegalMoves, Is.True,
                            "acilis pozisyonunda her zaman yasal hamle vardir");
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        private static void AdvanceToPreRoll(GameOrchestrator orchestrator)
        {
            int guard = 0;
            while (orchestrator.State.phase != GamePhase.PreRoll && guard++ < 200)
            {
                if (orchestrator.State.phase == GamePhase.Moving)
                {
                    orchestrator.EndTurn();
                }
                else
                {
                    orchestrator.RollDice();
                }
            }

            Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.PreRoll), "PreRoll'a ulasilamadi");
        }
    }
}
