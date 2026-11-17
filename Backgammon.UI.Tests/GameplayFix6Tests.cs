using System;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Altinci tur oynanis hatalarinin motor/orkestrator regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <b>Hata:</b> money game'de kup <c>64</c> iken yapilan <c>x128</c> teklifi kabul edilince
    /// oyun <b>kilitleniyordu</b>: ne zar atilabiliyor ne tas oynanabiliyordu. Nedeni
    /// <see cref="MatchState"/> yapicisinin <c>cubeValue &gt; 64</c> icin istisna atmasi ve
    /// <see cref="GameOrchestrator.Refresh"/>'in ilk isi olarak <see cref="MatchState.From"/>
    /// cagirmasiydi. Teklif bir daha <c>Refresh</c> tamamlanamadigi icin tum gorunumler bayat
    /// kaliyordu.
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix6Tests
    {
        // ------------------------------------------------------------------
        // Hata: x128 teklifi oyunu kilitlememeli
        // ------------------------------------------------------------------

        [Test]
        public void CanOffer_AtMaxCubeValue_IsFalse()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0001UL)))
            {
                orchestrator.NewMatch(0, false);

                BackgammonState state = orchestrator.State;
                state.cubeValue = MatchState.MoneyGameMaxCube;
                state.cubeOwner = 0;
                state.turn = 1;
                state.phase = GamePhase.PreRoll;
                state.hash = BackgammonEngine.ComputeZobristHash(state);

                Assert.That(BackgammonEngine.CanOffer(state), Is.False,
                            "kup ust sinirda iken teklif edilememeli");
            }
        }

        [Test]
        public void TryOfferDouble_AtMaxCubeValue_IsRefused_AndGameStaysPlayable()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0002UL)))
            {
                orchestrator.NewMatch(0, false);

                BackgammonState state = orchestrator.State;
                state.cubeValue = MatchState.MoneyGameMaxCube;
                state.cubeOwner = 0;
                state.turn = 1;
                state.phase = GamePhase.PreRoll;
                state.hash = BackgammonEngine.ComputeZobristHash(state);

                Assert.That(orchestrator.TryOfferDouble(), Is.False, "teklif reddedilmeli");
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.PreRoll),
                            "faz degismemeli (CubeOffered'a gecmemeli)");
                Assert.That(orchestrator.State.cubeValue, Is.EqualTo(MatchState.MoneyGameMaxCube),
                            "kup degeri degismemeli");

                // Kilitlenme belirtisi: Refresh() icindeki MatchState.From() istisna atardi.
                Assert.DoesNotThrow(() => orchestrator.AnalyzeCurrent(),
                                    "kup ust sinirda iken Refresh/Analyze istisna atmamali");
            }
        }

        [Test]
        public void DoublingUpToMaxCube_KeepsStateValid_AndStopsAtMax()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0003UL)))
            {
                orchestrator.NewMatch(0, false);

                int value = 1;
                while (value < MatchState.MoneyGameMaxCube)
                {
                    BackgammonState state = orchestrator.State;
                    state.cubeValue = value;
                    state.cubeOwner = 0;
                    state.turn = 1;
                    state.phase = GamePhase.PreRoll;
                    state.hash = BackgammonEngine.ComputeZobristHash(state);

                    Assert.That(orchestrator.TryOfferDouble(), Is.True,
                                "kup " + value + " iken teklif edilebilmeli");
                    Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.CubeOffered));

                    // Kabul: kup ikiye katlanir; Refresh() istisna atmamali.
                    Assert.DoesNotThrow(() => orchestrator.Take(),
                                        "kup " + value + " kabulunde Refresh istisna atmamali");
                    Assert.That(orchestrator.State.cubeValue, Is.EqualTo(value * 2));

                    value *= 2;
                }

                Assert.That(orchestrator.State.cubeValue, Is.EqualTo(MatchState.MoneyGameMaxCube));

                // Ust sinirda teklif reddedilir; oyun oynanabilir kalir.
                BackgammonState top = orchestrator.State;
                top.cubeOwner = 0;
                top.turn = 1;
                top.phase = GamePhase.PreRoll;
                top.hash = BackgammonEngine.ComputeZobristHash(top);

                Assert.That(orchestrator.TryOfferDouble(), Is.False);
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.PreRoll));
                Assert.DoesNotThrow(() => orchestrator.RollDice(), "zar atilabilmeli");
                Assert.That(orchestrator.State.phase, Is.EqualTo(GamePhase.Moving));
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

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
    }
}
