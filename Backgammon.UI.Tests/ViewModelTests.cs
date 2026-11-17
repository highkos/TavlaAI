using System;
using System.Collections.Generic;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>Faz 5 Bolum 8, Test 27-31: saf C# view-model'leri.</summary>
    [TestFixture]
    public sealed class ViewModelTests
    {
        // ------------------------------------------------------------------
        // Test 27
        // ------------------------------------------------------------------

        [Test]
        public void BoardViewModel_ReflectsState()
        {
            var state = UiTestSupport.InitialState();
            var vm = new BoardViewModel();
            int changed = 0;
            vm.Changed += () => changed++;

            vm.Update(state);

            Assert.Multiple(() =>
            {
                Assert.That(changed, Is.EqualTo(1), "Changed bir kez tetiklenmeli");
                Assert.That(BoardViewModel.PointCount, Is.EqualTo(24));
                Assert.That(vm.Points.Length, Is.EqualTo(24));

                // Beyaz: 1'de 2, 12'de 5, 17'de 3, 19'da 5
                AssertPoint(vm, 1, 1, 2);
                AssertPoint(vm, 12, 1, 5);
                AssertPoint(vm, 17, 1, 3);
                AssertPoint(vm, 19, 1, 5);

                // Siyah: 24'te 2, 13'te 5, 8'de 3, 6'da 5
                AssertPoint(vm, 24, -1, 2);
                AssertPoint(vm, 13, -1, 5);
                AssertPoint(vm, 8, -1, 3);
                AssertPoint(vm, 6, -1, 5);

                // Geri kalan 16 hane bos
                int empty = 0;
                for (int p = 1; p <= 24; p++)
                {
                    if (vm.PointAt(p).IsEmpty)
                    {
                        empty++;
                    }
                }

                Assert.That(empty, Is.EqualTo(16));

                Assert.That(vm.WhiteBar.IsEmpty, Is.True);
                Assert.That(vm.BlackBar.IsEmpty, Is.True);
                Assert.That(vm.WhiteBorneOff, Is.EqualTo(0));
                Assert.That(vm.BlackBorneOff, Is.EqualTo(0));
                Assert.That(vm.Turn, Is.EqualTo(state.turn));
                Assert.That(vm.Die1, Is.EqualTo(state.rolledDice[0]));
                Assert.That(vm.Die2, Is.EqualTo(state.rolledDice[1]));
                Assert.That(vm.RemainingCount, Is.EqualTo(state.remainingCount));
                Assert.That(vm.Phase, Is.EqualTo(state.phase));
            });

            // Bar + toplama + zar yansimasi
            var custom = UiTestSupport.InitialState();
            custom.board[0] = 2;    // Beyaz bar
            custom.board[25] = -3;  // Siyah bar
            custom.board[6] = 3;    // 5 -> 3
            custom.whiteBorneOff = 4;
            custom.blackBorneOff = 7;
            custom.turn = -1;
            BackgammonEngine.SetDice(custom, 3, 5);

            vm.Update(custom);

            Assert.Multiple(() =>
            {
                Assert.That(vm.WhiteBar.Owner, Is.EqualTo(1));
                Assert.That(vm.WhiteBar.Count, Is.EqualTo(2));
                Assert.That(vm.BlackBar.Owner, Is.EqualTo(-1));
                Assert.That(vm.BlackBar.Count, Is.EqualTo(3));
                Assert.That(vm.WhiteBorneOff, Is.EqualTo(4));
                Assert.That(vm.BlackBorneOff, Is.EqualTo(7));
                Assert.That(vm.Turn, Is.EqualTo(-1));
                Assert.That(vm.Die1, Is.EqualTo(3));
                Assert.That(vm.Die2, Is.EqualTo(5));
                Assert.That(vm.RemainingCount, Is.EqualTo(2));
                Assert.That(vm.Phase, Is.EqualTo(GamePhase.Moving));
                Assert.That(changed, Is.EqualTo(2));
            });

            Assert.Throws<ArgumentNullException>(() => vm.Update(null));
            Assert.Throws<ArgumentOutOfRangeException>(() => vm.PointAt(0));
            Assert.Throws<ArgumentOutOfRangeException>(() => vm.PointAt(25));
        }

        private static void AssertPoint(BoardViewModel vm, int point, sbyte owner, int count)
        {
            PointView view = vm.PointAt(point);
            Assert.That(view.Owner, Is.EqualTo(owner), "hane " + point + " sahibi");
            Assert.That(view.Count, Is.EqualTo(count), "hane " + point + " tas sayisi");
            Assert.That(view.IsEmpty, Is.False);
        }

        // ------------------------------------------------------------------
        // Test 28
        // ------------------------------------------------------------------

        [Test]
        public void MatchScoreViewModel_CrawfordBadge()
        {
            var vm = new MatchScoreViewModel();
            int changed = 0;
            vm.Changed += () => changed++;

            // 1) Money game
            var money = UiTestSupport.InitialState();
            money.matchLength = 0;
            money.whiteScore = 0;
            money.blackScore = 0;
            money.isCrawfordGame = false;
            vm.Update(money);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsMoneyGame, Is.True);
                Assert.That(vm.MatchLength, Is.EqualTo(0));
                Assert.That(vm.AwayWhite, Is.EqualTo(-1));
                Assert.That(vm.AwayBlack, Is.EqualTo(-1));
                Assert.That(vm.IsCrawford, Is.False);
                Assert.That(vm.IsPostCrawford, Is.False);
            });

            // 2) Normal mac oyunu (5-away mac, 1-1)
            var normal = UiTestSupport.InitialState();
            normal.matchLength = 5;
            normal.whiteScore = 1;
            normal.blackScore = 1;
            normal.isCrawfordGame = false;
            normal.crawfordPlayed = false;
            vm.Update(normal);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsMoneyGame, Is.False);
                Assert.That(vm.MatchLength, Is.EqualTo(5));
                Assert.That(vm.WhiteScore, Is.EqualTo(1));
                Assert.That(vm.BlackScore, Is.EqualTo(1));
                Assert.That(vm.AwayWhite, Is.EqualTo(4));
                Assert.That(vm.AwayBlack, Is.EqualTo(4));
                Assert.That(vm.IsCrawford, Is.False);
                Assert.That(vm.IsPostCrawford, Is.False);
            });

            // 3) Crawford oyunu (5-away mac, 4-2)
            var crawford = UiTestSupport.InitialState();
            crawford.matchLength = 5;
            crawford.whiteScore = 4;
            crawford.blackScore = 2;
            crawford.isCrawfordGame = true;
            crawford.crawfordPlayed = false;
            vm.Update(crawford);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsCrawford, Is.True);
                Assert.That(vm.IsPostCrawford, Is.False);
                Assert.That(vm.AwayWhite, Is.EqualTo(1));
                Assert.That(vm.AwayBlack, Is.EqualTo(3));
            });

            // 4) Post-Crawford (5-away mac, 4-3, Crawford oynanmis)
            var post = UiTestSupport.InitialState();
            post.matchLength = 5;
            post.whiteScore = 4;
            post.blackScore = 3;
            post.isCrawfordGame = false;
            post.crawfordPlayed = true;
            vm.Update(post);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsCrawford, Is.False);
                Assert.That(vm.IsPostCrawford, Is.True);
                Assert.That(vm.AwayWhite, Is.EqualTo(1));
                Assert.That(vm.AwayBlack, Is.EqualTo(2));
                Assert.That(changed, Is.EqualTo(4));
            });

            Assert.Throws<ArgumentNullException>(() => vm.Update(null));
        }

        // ------------------------------------------------------------------
        // Test 29
        // ------------------------------------------------------------------

        [Test]
        public void CubeViewModel_Visibility()
        {
            var vm = new CubeViewModel();
            int changed = 0;
            vm.Changed += () => changed++;

            // 1) Ortada
            var centered = UiTestSupport.InitialState();
            centered.cubeValue = 1;
            centered.cubeOwner = 0;
            centered.isCrawfordGame = false;
            vm.Update(centered);

            Assert.Multiple(() =>
            {
                Assert.That(vm.Visibility, Is.EqualTo(CubeVisibility.Centered));
                Assert.That(vm.Value, Is.EqualTo(1));
                Assert.That(vm.Owner, Is.EqualTo(0));
            });

            // 2) Sahipli
            var owned = UiTestSupport.InitialState();
            owned.cubeValue = 4;
            owned.cubeOwner = 1;
            owned.isCrawfordGame = false;
            vm.Update(owned);

            Assert.Multiple(() =>
            {
                Assert.That(vm.Visibility, Is.EqualTo(CubeVisibility.Owned));
                Assert.That(vm.Value, Is.EqualTo(4));
                Assert.That(vm.Owner, Is.EqualTo(1));
            });

            // 3) Teklif edildi
            var offered = UiTestSupport.InitialState();
            offered.cubeValue = 2;
            offered.cubeOwner = -1;
            offered.isCrawfordGame = false;
            offered.phase = GamePhase.CubeOffered;
            vm.Update(offered);

            Assert.Multiple(() =>
            {
                Assert.That(vm.Visibility, Is.EqualTo(CubeVisibility.Offered));
                Assert.That(vm.Value, Is.EqualTo(2));
                Assert.That(vm.Owner, Is.EqualTo(-1));
                Assert.That(vm.CanOffer, Is.False);
            });

            // 4) Crawford oyununda gizli
            var crawford = UiTestSupport.InitialState();
            crawford.cubeValue = 1;
            crawford.cubeOwner = 0;
            crawford.isCrawfordGame = true;
            vm.Update(crawford);

            Assert.Multiple(() =>
            {
                Assert.That(vm.Visibility, Is.EqualTo(CubeVisibility.Hidden));
                Assert.That(vm.CanOffer, Is.False);
                Assert.That(changed, Is.EqualTo(4));
            });

            Assert.Throws<ArgumentNullException>(() => vm.Update(null));
        }

        // ------------------------------------------------------------------
        // Test 30
        // ------------------------------------------------------------------

        [Test]
        public void MoveInputController_LegalTargets()
        {
            const int PositionCount = 200;
            List<BackgammonState> positions = UiTestSupport.RandomMovingPositions(PositionCount, 0x5EED_0030UL);
            Assert.That(positions.Count, Is.EqualTo(PositionCount), "200 pozisyon uretilemedi");

            var controller = new MoveInputController();
            var moves = new MoveList();
            var stepBuf = new MoveStep[32];
            int comparedPoints = 0;
            int nonEmpty = 0;

            foreach (BackgammonState state in positions)
            {
                controller.Update(state);
                LegalMoveGenerator.GenerateAllLegalMoves(state, moves);

                for (int from = 0; from <= 25; from++)
                {
                    // Bar doluyken yalnizca giris adimlari projekte edilir; aksi halde
                    // "barda tas varken once giris" kurali atlatilabiliyordu.
                    int bar = BackgammonEngine.BarIndex(state.turn);
                    bool mustEnter = state.board[bar] * state.turn > 0;

                    // Beklenti kumesi: guncel durumda gercekten oynanabilen ve maksimum
                    // uzunluktaki bir dizinin basinda yer alan adimlar
                    // (LegalMoveGenerator.GenerateFirstSteps). Uretici ayni son duruma ulasan
                    // dizileri tekillestirdigi icin bir dizinin k > 0 adimi baska bir ara duruma
                    // aittir; o adim guncel durumda yasal olmayabilir (bos hane, bloke hedef,
                    // toplama modu). Bu yuzden adimlar guncel durumdan istenir.
                    var expected = new SortedSet<int>();
                    int stepCount = LegalMoveGenerator.GenerateFirstSteps(state, moves, from, stepBuf);
                    for (int i = 0; i < stepCount; i++)
                    {
                        MoveStep step = stepBuf[i];
                        if (mustEnter && !step.IsFromBar)
                        {
                            continue;
                        }

                        expected.Add(step.To);
                    }

                    IReadOnlyList<int> actual = controller.LegalTargetsFrom(from);
                    comparedPoints++;

                    Assert.That(
                        actual.Count, Is.EqualTo(expected.Count),
                        "hane " + from + " hedef sayisi");

                    int index = 0;
                    foreach (int target in expected)
                    {
                        Assert.That(actual[index], Is.EqualTo(target), "hane " + from + " hedef " + index);
                        index++;
                    }

                    if (expected.Count > 0)
                    {
                        nonEmpty++;
                    }

                    // Secim yolu da ayni sonucu vermeli.
                    controller.SelectPoint(from);
                    Assert.That(
                        controller.LegalTargets.Count, Is.EqualTo(expected.Count),
                        "secim yolu: hane " + from);
                }

                controller.ClearSelection();
                Assert.That(controller.SelectedPoint, Is.EqualTo(MoveInputController.NoSelection));
                Assert.That(controller.LegalTargets.Count, Is.EqualTo(0));
            }

            Assert.That(comparedPoints, Is.EqualTo(PositionCount * 26));
            Assert.That(nonEmpty, Is.GreaterThan(0), "en az bir hane hedef uretmeli");
        }

        [Test]
        public void MoveInputController_PartialMoveAndUndo()
        {
            var state = UiTestSupport.InitialState();
            BackgammonEngine.SetDice(state, 3, 1);

            var controller = new MoveInputController();
            controller.Update(state);

            // Beyaz 19'dan 20'ye (zar 1) veya 22'ye (zar 3) gidebilir (Beyaz 1 -> 24 yonunde ilerler).
            controller.SelectPoint(19);
            IReadOnlyList<int> targets = controller.LegalTargets;
            Assert.That(targets, Is.Not.Empty);
            Assert.That(targets, Does.Contain(20));
            Assert.That(targets, Does.Contain(22));

            Assert.That(controller.TryAddStep(20), Is.True);
            Assert.That(controller.HasPartialMove, Is.True);
            Assert.That(controller.PartialMove.Count, Is.EqualTo(1));
            Assert.That(controller.SelectedPoint, Is.EqualTo(20));

            controller.UndoStep();
            Assert.That(controller.HasPartialMove, Is.False);
            Assert.That(controller.SelectedPoint, Is.EqualTo(19));

            controller.SelectPoint(19);
            Assert.That(controller.TryAddStep(21), Is.False, "21 yasal hedef degil");

            controller.Reset();
            Assert.That(controller.SelectedPoint, Is.EqualTo(MoveInputController.NoSelection));
            Assert.That(controller.HasPartialMove, Is.False);

            Assert.Throws<ArgumentOutOfRangeException>(() => controller.SelectPoint(-2));
            Assert.Throws<ArgumentOutOfRangeException>(() => controller.SelectPoint(26));
            Assert.Throws<ArgumentNullException>(() => controller.Update(null));
        }

        // ------------------------------------------------------------------
        // Test 30b
        // ------------------------------------------------------------------

        [Test]
        public void MoveInputController_PartialMoveContinuesFromNewPosition()
        {
            var state = UiTestSupport.InitialState();
            BackgammonEngine.SetDice(state, 3, 1);

            var controller = new MoveInputController();
            controller.Update(state);

            controller.SelectPoint(19);
            Assert.That(controller.TryAddStep(20), Is.True, "19 -> 20 (zar 1) oynanabilmeli");

            // Bir zari oynadiktan sonra hedefler YENI pozisyondan uretilmelidir.
            // Eski davranista liste taban durumdan geliyordu; 20 bos oldugu icin
            // hedef kalmiyor ve ikinci tiklamada tas hic gitmiyordu.
            Assert.That(controller.SelectedPoint, Is.EqualTo(20));
            IReadOnlyList<int> afterFirst = controller.LegalTargets;
            Assert.That(afterFirst, Is.Not.Empty, "kismi hamleden sonra hedef kalmali");
            Assert.That(afterFirst, Does.Contain(23), "20 -> 23 (kalan zar 3)");
            Assert.That(afterFirst, Does.Not.Contain(20), "ayni hane tekrar hedef olmamali");

            Assert.That(controller.TryAddStep(23), Is.True, "20 -> 23 oynanabilmeli");
            Assert.That(controller.PartialMove.Count, Is.EqualTo(2));

            // Iki adim da gercekten uygulanabilir olmali (motor kabul etmeli).
            BackgammonState probe = state.Clone();
            MoveSequence move = controller.PartialMove;
            Assert.DoesNotThrow(() => BackgammonEngine.ApplyMove(probe, in move));
            Assert.That(probe.board[19], Is.EqualTo(4), "19'da 4 tas kalmali");
            Assert.That(probe.board[20], Is.EqualTo(0), "20 bos kalmali (tas 23'e gecti)");
            Assert.That(probe.board[23], Is.EqualTo(1), "23'te 1 tas olmali");

            // Geri alma taban duruma donmeli.
            controller.UndoStep();
            controller.UndoStep();
            Assert.That(controller.HasPartialMove, Is.False);
            controller.SelectPoint(19);
            Assert.That(controller.LegalTargets, Does.Contain(20));
            Assert.That(controller.LegalTargets, Does.Contain(22));
        }

        // ------------------------------------------------------------------
        // Test 31
        // ------------------------------------------------------------------

        [Test]
        public void AnalysisViewModel_FormatsPositionAnalysis()
        {
            var vm = new AnalysisViewModel();
            int changed = 0;
            vm.Changed += () => changed++;

            var exact = new PositionAnalysis(
                equity: 0.42,
                matchEquity: 0.42,
                matchWinningChance: double.NaN,
                distribution: null,
                fromBearoffDatabase: true,
                isExact: true,
                pipCountActive: 167,
                pipCountOpponent: 158,
                rollsToOffActive: 12,
                rollsToOffOpponent: -1,
                cube: null);

            vm.Update(exact);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsExact, Is.True);
                Assert.That(vm.Badge, Is.EqualTo("Kesin"));
                Assert.That(vm.EquityText, Is.EqualTo("+0,42"), "tr-TR ondalik ayirici virgul olmali");
                Assert.That(vm.MatchEquityText, Is.EqualTo("+0,42"));
                Assert.That(vm.MatchWinningChanceText, Is.EqualTo(AnalysisViewModel.Unknown));
                Assert.That(vm.PipText, Is.EqualTo("167 / 158"));
                Assert.That(vm.RollsToOffActiveText, Is.EqualTo("12"));
                Assert.That(vm.RollsToOffOpponentText, Is.EqualTo(AnalysisViewModel.Unknown));
                Assert.That(vm.GammonText, Is.EqualTo(AnalysisViewModel.Unknown));
                Assert.That(vm.CubeText, Is.EqualTo(AnalysisViewModel.Unknown));
                Assert.That(AnalysisViewModel.Unknown, Is.EqualTo("\u2014"));
                Assert.That(changed, Is.EqualTo(1));
            });

            var estimate = new PositionAnalysis(
                equity: -0.125,
                matchEquity: 0.5,
                matchWinningChance: 0.75,
                distribution: new OutcomeDistribution(0.6f, 0.2f, 0.05f, 0.1f, 0.02f),
                fromBearoffDatabase: false,
                isExact: false,
                pipCountActive: 100,
                pipCountOpponent: 90,
                rollsToOffActive: -1,
                rollsToOffOpponent: -1,
                cube: new CubeDecision(true, false, 0.5, 1.0, 1.0, false, false));

            vm.Update(estimate);

            Assert.Multiple(() =>
            {
                Assert.That(vm.IsExact, Is.False);
                Assert.That(vm.Badge, Is.EqualTo("Tahmin"));
                Assert.That(vm.EquityText, Is.EqualTo("-0,12"), "F2 yuvarlamasi (banker's rounding)");
                Assert.That(vm.MatchEquityText, Is.EqualTo("+0,50"));
                Assert.That(vm.MatchWinningChanceText, Is.EqualTo("75,0%"));
                Assert.That(vm.RollsToOffActiveText, Is.EqualTo(AnalysisViewModel.Unknown));
                Assert.That(vm.GammonText, Is.EqualTo("20,0% / 10,0%"));
                Assert.That(vm.CubeText, Is.EqualTo("Ciftle / Reddet"));
                Assert.That(changed, Is.EqualTo(2));
            });
        }
    }
}
