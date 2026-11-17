using System;
using Backgammon.Core;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Cevrimici terminal tahta regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <b>Hata:</b> cevrimici maçta kazanan hamle uygulandiginda sunucu, yeni oyun
    /// baslamadan once tahtayi <c>Phase=Playing</c> ve artan zarlarla yayinliyordu.
    /// Istemci bu anlik goruntuyu <c>phase=Moving</c> + kalan zar olarak yukluyor,
    /// <see cref="GameOrchestrator.AnalyzeCurrent"/> ise terminal tahtayi aramaya
    /// sokuyordu; vektorlestirici terminal kayitlari tasarisindan reddettigi icin
    /// (<c>ArgumentException: Terminal kayit vektörleştirilemez</c>) oyun kilitleniyordu.
    /// </remarks>
    [TestFixture]
    public sealed class GameplayFix10Tests
    {
        // ------------------------------------------------------------------
        // Hata: terminal tahta + kalan zar -> analiz istisna atmamali
        // ------------------------------------------------------------------

        [Test]
        public void AnalyzeCurrent_TerminalBoardWithRemainingDice_DoesNotReachTheEvaluators()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0100UL)))
            {
                orchestrator.NewMatch(5, false);

                BackgammonState terminal = TerminalState(winnerBorneOff: 15, loserPoint: 24);
                BackgammonEngine.SetDice(terminal, 6, 5);
                terminal.hash = BackgammonEngine.ComputeZobristHash(terminal);

                orchestrator.LoadState(terminal);

                Assert.That(orchestrator.IsGameOver, Is.True,
                            "tum taslar toplanmis tahta terminal olmali");
                Assert.That(orchestrator.State.remainingCount, Is.EqualTo(2),
                            "cevrimici anlik goruntu kalan zarlari tasiyabilir");

                PositionAnalysis analysis = default;
                Assert.DoesNotThrow(() => analysis = orchestrator.AnalyzeCurrent(),
                                    "terminal tahta aramaya gonderilmemeli (Bolum 2.2)");
                Assert.That(analysis.Equity, Is.GreaterThan(0.0),
                            "kazanan perspektifinden equity pozitif olmali");
                Assert.That(analysis.IsExact, Is.True,
                            "terminal pozisyonun degeri kesin olmali");
            }
        }

        [Test]
        public void AnalyzeCurrent_TerminalBoardInWaitForRoll_DoesNotReachTheEvaluators()
        {
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0101UL)))
            {
                orchestrator.NewMatch(5, false);

                BackgammonState terminal = TerminalState(winnerBorneOff: 15, loserPoint: 24);
                terminal.phase = GamePhase.WaitForRoll;
                terminal.remainingCount = 0;
                terminal.hash = BackgammonEngine.ComputeZobristHash(terminal);

                orchestrator.LoadState(terminal);

                PositionAnalysis analysis = default;
                Assert.DoesNotThrow(() => analysis = orchestrator.AnalyzeCurrent(),
                                    "WaitForRoll rollout'u terminal tahtaya inmemeli");
                Assert.That(analysis.Equity, Is.GreaterThan(0.0));
            }
        }

        [Test]
        public void AnalyzeCurrent_TerminalBoard_MatchEquityDoesNotSearch()
        {
            // Mac oyunu + MET: matchEquity dallari terminal tahtada arama yapmamali.
            using (var orchestrator = new GameOrchestrator(Options(0x6A17_0102UL)))
            {
                orchestrator.NewMatch(5, false);

                BackgammonState terminal = TerminalState(winnerBorneOff: 15, loserPoint: 24);
                BackgammonEngine.SetDice(terminal, 6, 5);
                terminal.hash = BackgammonEngine.ComputeZobristHash(terminal);

                orchestrator.LoadState(terminal);

                PositionAnalysis analysis = default;
                Assert.DoesNotThrow(() => analysis = orchestrator.AnalyzeCurrent());
                Assert.That(analysis.MatchEquity, Is.GreaterThan(0.0),
                            "kazanan perspektifinden mac equity'si pozitif olmali");
                Assert.That(double.IsNaN(analysis.MatchWinningChance), Is.False);
            }
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        /// <summary>Beyazin tum taslarini toplamis, siyahin hala tahtada oldugu terminal durum.</summary>
        private static BackgammonState TerminalState(int winnerBorneOff, int loserPoint)
        {
            var state = UiTestSupport.InitialState();

            var white = new int[25];
            var black = new int[25];
            black[loserPoint] = 15;
            UiTestSupport.SetBoard(state, white, black);

            state.whiteBorneOff = (byte)winnerBorneOff;
            state.matchLength = 5;
            state.turn = 1;
            return state;
        }

        private static GameOrchestratorOptions Options(ulong seed)
        {
            return new GameOrchestratorOptions
            {
                Evaluator = new FakeEvaluator(),
                Bearoff = null,
                Met = MatchEquityTable.Default,
                Distribution = null,
                SearchSettings = SearchSettings.Default,
                EngineSettings = EngineSettings.Default,
                Random = new Xoshiro256StarStar(seed),
                MaxPlies = 0
            };
        }
    }
}
