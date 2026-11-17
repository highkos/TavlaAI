using System;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Orta bant (ust ve alt ucgen uclari arasindaki bosluk) regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Istek:</b> "Tavla tahtasindaki asagidaki ucgenin uc noktasi ile yukaridaki ucgenin
    /// uc noktalari birbirine cok yakin; gercek bir tavla tahtasinda ust ucgen ile alt ucgen
    /// arasinda bir miktar mesafe olmali. (Belki ileride logo vs koyabilirim orta alana.)"
    /// </para>
    /// <para>
    /// <b>Cozum:</b> <see cref="BoardLayout"/> iki hane satirini tahta yuksekliginin
    /// <see cref="BoardLayout.CenterGapRatio"/> kadari kadar birbirinden ayirir. Ucgen uclari
    /// orta cizgide birlesmez; arada tahta yuzeyi gorunur (<see cref="BoardLayout.CenterBand"/>).
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class BoardCenterGapTests
    {
        private static readonly float[][] Sizes =
        {
            new[] { 1920f, 1080f },
            new[] { 1600f, 1200f },
            new[] { 2560f, 1080f },
            new[] { 1280f, 720f },
            new[] { 1000f, 500f },
            new[] { 1622f, 892f },
        };

        // ------------------------------------------------------------------
        // Bosluk var mi?
        // ------------------------------------------------------------------

        [Test]
        public void CenterGap_IsPositive_ForEveryAspectRatio()
        {
            for (int i = 0; i < Sizes.Length; i++)
            {
                float width = Sizes[i][0];
                float height = Sizes[i][1];
                BoardLayout layout = BoardLayout.Calculate(width, height);

                Assert.That(layout.CenterGap, Is.GreaterThan(0f),
                            "orta bant pozitif olmali: " + width + "x" + height);
                Assert.That(layout.CenterGap, Is.EqualTo(height * BoardLayout.CenterGapRatio).Within(0.01f),
                            "orta bant tahta yuksekligiyle orantili olmali: " + width + "x" + height);
            }
        }

        [Test]
        public void CenterGap_IsProportionalToHeight_NotWidth()
        {
            BoardLayout wide = BoardLayout.Calculate(2560f, 1080f);
            BoardLayout narrow = BoardLayout.Calculate(1280f, 1080f);

            Assert.That(wide.CenterGap, Is.EqualTo(narrow.CenterGap).Within(0.0001f),
                        "ayni yukseklikte genislik degisince bant degismemeli");
        }

        // ------------------------------------------------------------------
        // Ucgen uclari birlesmiyor
        // ------------------------------------------------------------------

        [Test]
        public void TopAndBottomPointRects_AreSeparatedByTheGap()
        {
            for (int i = 0; i < Sizes.Length; i++)
            {
                float width = Sizes[i][0];
                float height = Sizes[i][1];
                BoardLayout layout = BoardLayout.Calculate(width, height);
                string label = width + "x" + height;

                for (int point = 1; point <= BoardLayout.PointCount; point++)
                {
                    LayoutRect rect = layout.PointAt(point);
                    bool topRow = rect.Y < height * 0.5f;

                    if (topRow)
                    {
                        // Ust satir: ucgen asagi bakar, ucu bandin UST kenarinda biter.
                        Assert.That(rect.Bottom, Is.LessThanOrEqualTo(layout.CenterBand.Y + 0.01f),
                                    label + " hane " + point + " orta banda girmemeli");
                    }
                    else
                    {
                        // Alt satir: ucgen yukari bakar, ucu bandin ALT kenarinda biter.
                        Assert.That(rect.Y, Is.GreaterThanOrEqualTo(layout.CenterBand.Bottom - 0.01f),
                                    label + " hane " + point + " orta banda girmemeli");
                    }
                }
            }
        }

        [Test]
        public void CenterBand_MatchesTheGapBetweenTheRows()
        {
            BoardLayout layout = BoardLayout.Calculate(1920f, 1080f);

            // Ust satirin en alt kenari ile alt satirin en ust kenari arasindaki mesafe
            // tam olarak bant yuksekligi olmali.
            float topRowBottom = 0f;
            float bottomRowTop = float.MaxValue;
            for (int point = 1; point <= BoardLayout.PointCount; point++)
            {
                LayoutRect rect = layout.PointAt(point);
                if (rect.Y < layout.Board.Height * 0.5f)
                {
                    topRowBottom = Math.Max(topRowBottom, rect.Bottom);
                }
                else
                {
                    bottomRowTop = Math.Min(bottomRowTop, rect.Y);
                }
            }

            Assert.That(bottomRowTop - topRowBottom, Is.EqualTo(layout.CenterGap).Within(0.01f),
                        "satirlar arasi bosluk bant yuksekligine esit olmali");
            Assert.That(layout.CenterBand.Y, Is.EqualTo(topRowBottom).Within(0.01f),
                        "bant ust satirin bittigi yerde baslamali");
            Assert.That(layout.CenterBand.Bottom, Is.EqualTo(bottomRowTop).Within(0.01f),
                        "bant alt satirin basladigi yerde bitmeli");
        }

        [Test]
        public void CenterBand_SpansTheFullBoardWidth()
        {
            BoardLayout layout = BoardLayout.Calculate(1920f, 1080f);

            Assert.That(layout.CenterBand.X, Is.EqualTo(layout.Board.X).Within(0.01f));
            Assert.That(layout.CenterBand.Width, Is.EqualTo(layout.Board.Width).Within(0.01f));
            Assert.That(layout.CenterBand.Height, Is.EqualTo(layout.CenterGap).Within(0.01f));
        }

        [Test]
        public void CenterBand_DoesNotOverlapAnyPoint()
        {
            for (int i = 0; i < Sizes.Length; i++)
            {
                float width = Sizes[i][0];
                float height = Sizes[i][1];
                BoardLayout layout = BoardLayout.Calculate(width, height);

                for (int point = 1; point <= BoardLayout.PointCount; point++)
                {
                    Assert.That(layout.PointAt(point).Overlaps(layout.CenterBand), Is.False,
                                width + "x" + height + " hane " + point + " orta bantla kesisiyor");
                }
            }
        }

        // ------------------------------------------------------------------
        // Bozulmayanlar
        // ------------------------------------------------------------------

        [Test]
        public void CenterGap_IsIndependentOfFlipAndTrayBottom()
        {
            BoardLayout plain = BoardLayout.Calculate(1920f, 1080f, false, false);
            BoardLayout flipped = BoardLayout.Calculate(1920f, 1080f, true, true);

            Assert.That(flipped.CenterGap, Is.EqualTo(plain.CenterGap).Within(0.0001f),
                        "aynalama bant yuksekligini degistirmemeli");
            Assert.That(flipped.CenterBand.Y, Is.EqualTo(plain.CenterBand.Y).Within(0.0001f),
                        "aynalama bant konumunu degistirmemeli");
        }

        [Test]
        public void CenterGap_KeepsBarAndTrayFullHeight()
        {
            BoardLayout layout = BoardLayout.Calculate(1920f, 1080f);

            // Bar ve tepsi dikey olarak kesintisizdir; orta bant onlari bolmez.
            Assert.That(layout.Bar.Y, Is.EqualTo(0f).Within(0.01f), "bar ustten baslamali");
            Assert.That(layout.Bar.Height, Is.EqualTo(layout.Board.Height).Within(0.01f),
                        "bar tam yukseklikte olmali");
            Assert.That(layout.Tray.Y, Is.EqualTo(0f).Within(0.01f), "tepsi ustten baslamali");
            Assert.That(layout.Tray.Height, Is.EqualTo(layout.Board.Height).Within(0.01f),
                        "tepsi tam yukseklikte olmali");
        }

        [Test]
        public void CenterGap_KeepsPointRectsDisjointAndInsideBoard()
        {
            for (int i = 0; i < Sizes.Length; i++)
            {
                float width = Sizes[i][0];
                float height = Sizes[i][1];
                BoardLayout layout = BoardLayout.Calculate(width, height, true, true);
                string label = width + "x" + height;

                for (int a = 1; a <= BoardLayout.PointCount; a++)
                {
                    LayoutRect ra = layout.PointAt(a);
                    Assert.That(ra.Width, Is.GreaterThan(0f), label + " hane " + a + " genislik");
                    Assert.That(ra.Height, Is.GreaterThan(0f), label + " hane " + a + " yukseklik");
                    Assert.That(ra.Y, Is.GreaterThanOrEqualTo(-0.01f), label + " hane " + a + " ust sinir");
                    Assert.That(ra.Bottom, Is.LessThanOrEqualTo(height + 0.01f),
                                label + " hane " + a + " alt sinir");

                    for (int b = a + 1; b <= BoardLayout.PointCount; b++)
                    {
                        Assert.That(ra.Overlaps(layout.PointAt(b)), Is.False,
                                    label + " hane " + a + " ile " + b + " kesisiyor");
                    }
                }
            }
        }

        [Test]
        public void CenterGap_LeavesEnoughRoomForFifteenCheckers()
        {
            // Bir hanede en fazla 15 pul olabilir. Bosluk haneyi kisalttigi icin pul boyutu
            // ve yigin adimi hala 15 pulu sigdirmali (BoardView ile ayni formul).
            for (int i = 0; i < Sizes.Length; i++)
            {
                float width = Sizes[i][0];
                float height = Sizes[i][1];
                BoardLayout layout = BoardLayout.Calculate(width, height);
                LayoutRect rect = layout.PointAt(1);

                float size = Math.Min(rect.Width, rect.Height / 6f) * 0.92f;
                float step = Math.Min(size, (rect.Height - size) / 14f);
                float stack = (14f * step) + size;

                Assert.That(size, Is.GreaterThan(0f), width + "x" + height + " pul boyutu");
                Assert.That(stack, Is.LessThanOrEqualTo(rect.Height + 0.01f),
                            width + "x" + height + " 15 pul haneye sigmali");
            }
        }
    }
}
