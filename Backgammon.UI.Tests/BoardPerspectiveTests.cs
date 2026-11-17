using System;
using System.Collections.Generic;
using Backgammon.UI;
using NUnit.Framework;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Renk degistirme (bakis acisi) regresyon testleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Istek:</b> "Renk degistir secenegi tercih edildiginde (varsayilan Siyah) Beyaz renk
    /// siyah, siyah renk beyaz olsun; yani taslari oyuncu her iki renkte de ayni yone hareket
    /// etmis olsun."
    /// </para>
    /// <para>
    /// <b>Cozum:</b> motor Beyaz'i <c>1 -&gt; 24</c>, Siyah'i <c>24 -&gt; 1</c> yonunde hareket
    /// ettirir. Oyuncu Beyaz oynarken hane numaralari 180 derece dondurulur
    /// (<see cref="BoardLayout.VisualSlot"/> = <c>25 - hane</c>); boylece oyuncunun ev bolgesi
    /// <b>sag altta</b> kalir ve taslari <b>ayni yone</b> gider. Tahta cercevesi, bar ve tepsi
    /// seridi yer degistirmez.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class BoardPerspectiveTests
    {
        private const float Width = 1920f;
        private const float Height = 1080f;

        // ------------------------------------------------------------------
        // Gorsel yuva eslemesi
        // ------------------------------------------------------------------

        [Test]
        public void VisualSlot_WithoutFlip_EqualsPoint()
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, true, false);

            Assert.That(layout.Flip, Is.False);
            for (int point = 1; point <= BoardLayout.PointCount; point++)
            {
                Assert.That(layout.VisualSlot(point), Is.EqualTo(point),
                            "aynalama kapaliyken gorsel yuva hane numarasina esit olmali: " + point);
            }
        }

        [Test]
        public void VisualSlot_WithFlip_IsMirrored()
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, false, true);

            Assert.That(layout.Flip, Is.True);
            for (int point = 1; point <= BoardLayout.PointCount; point++)
            {
                Assert.That(layout.VisualSlot(point), Is.EqualTo(25 - point),
                            "aynalamada gorsel yuva 25 - hane olmali: " + point);
            }
        }

        [Test]
        public void VisualSlot_IsAPermutation()
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, false, true);
            var seen = new HashSet<int>();

            for (int point = 1; point <= BoardLayout.PointCount; point++)
            {
                Assert.That(seen.Add(layout.VisualSlot(point)), Is.True,
                            "gorsel yuvalar tekrarsiz olmali: " + point);
            }

            Assert.That(seen.Count, Is.EqualTo(BoardLayout.PointCount));
        }

        [Test]
        public void VisualSlot_RejectsOutOfRange()
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, false, true);

            Assert.Throws<ArgumentOutOfRangeException>(() => layout.VisualSlot(0));
            Assert.Throws<ArgumentOutOfRangeException>(() => layout.VisualSlot(25));
        }

        // ------------------------------------------------------------------
        // Yerlesim degismezleri
        // ------------------------------------------------------------------

        [Test]
        public void Flip_KeepsPointRectsDisjointAndInsideBoard()
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, false, true);
            LayoutRect board = layout.Board;

            for (int a = 1; a <= BoardLayout.PointCount; a++)
            {
                LayoutRect ra = layout.PointAt(a);
                Assert.That(ra.X, Is.GreaterThanOrEqualTo(board.X - 0.01f), "hane " + a + " soldan tasdi");
                Assert.That(ra.X + ra.Width, Is.LessThanOrEqualTo(board.X + board.Width + 0.01f),
                            "hane " + a + " sagdan tasdi");
                Assert.That(ra.Y, Is.GreaterThanOrEqualTo(board.Y - 0.01f), "hane " + a + " alttan tasdi");
                Assert.That(ra.Y + ra.Height, Is.LessThanOrEqualTo(board.Y + board.Height + 0.01f),
                            "hane " + a + " ustten tasdi");

                for (int b = a + 1; b <= BoardLayout.PointCount; b++)
                {
                    Assert.That(Overlaps(ra, layout.PointAt(b)), Is.False,
                                "hane " + a + " ile " + b + " kesisiyor");
                }
            }
        }

        [Test]
        public void Flip_KeepsBoardBarAndTrayRectsUnchanged()
        {
            BoardLayout plain = BoardLayout.Calculate(Width, Height, false, false);
            BoardLayout flipped = BoardLayout.Calculate(Width, Height, false, true);

            AssertRectEqual(plain.Board, flipped.Board, "tahta");
            AssertRectEqual(plain.Bar, flipped.Bar, "bar");
            AssertRectEqual(plain.Tray, flipped.Tray, "tepsi seridi");
            AssertRectEqual(plain.WhiteTray, flipped.WhiteTray, "beyaz tepsi");
            AssertRectEqual(plain.BlackTray, flipped.BlackTray, "siyah tepsi");
        }

        [Test]
        public void PointAt_IsIndexedByVisualSlot()
        {
            // Ucgen rengi gorsel yuvaya gore secilir; bu yuzden PointAt ile Points dizisi
            // arasindaki iliski her iki bakis acisinda da tutmali.
            foreach (bool flip in new[] { false, true })
            {
                BoardLayout layout = BoardLayout.Calculate(Width, Height, false, flip);
                for (int point = 1; point <= BoardLayout.PointCount; point++)
                {
                    LayoutRect viaPoint = layout.PointAt(point);
                    LayoutRect viaSlot = layout.Points[layout.VisualSlot(point) - 1];
                    AssertRectEqual(viaPoint, viaSlot, "hane " + point + " (flip=" + flip + ")");
                }
            }
        }

        // ------------------------------------------------------------------
        // Oyuncunun ev bolgesi ve hareket yonu
        // ------------------------------------------------------------------

        [TestCase((sbyte)-1, false, true)]
        [TestCase((sbyte)1, true, false)]
        public void HumanHomeBoard_IsAlwaysBottomRight(sbyte humanColor, bool flip, bool trayBottom)
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, trayBottom, flip);
            float half = layout.Board.Height * 0.5f;

            // Ev bolgesi: Beyaz 19..24, Siyah 1..6.
            int first = humanColor > 0 ? 19 : 1;
            int last = humanColor > 0 ? 24 : 6;

            for (int point = first; point <= last; point++)
            {
                LayoutRect r = layout.PointAt(point);
                Assert.That(r.Y, Is.GreaterThanOrEqualTo(half - 0.01f),
                            "oyuncunun ev bolgesi alt satirda olmali: hane " + point);
                Assert.That(r.X, Is.GreaterThanOrEqualTo(layout.Bar.X + layout.Bar.Width - 0.01f),
                            "oyuncunun ev bolgesi sag yarida olmali: hane " + point);
            }

            // Oyuncunun toplama tepsisi de sag altta olmali.
            LayoutRect tray = humanColor > 0 ? layout.WhiteTray : layout.BlackTray;
            Assert.That(tray.Y, Is.GreaterThanOrEqualTo(half - 0.01f),
                        "oyuncunun tepsisi alt yarida olmali");
        }

        [TestCase((sbyte)-1, false)]
        [TestCase((sbyte)1, true)]
        public void HumanCheckers_MoveInTheSameScreenDirection(sbyte humanColor, bool flip)
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, humanColor < 0, flip);
            int direction = humanColor > 0 ? 1 : -1;

            // Tahta at nalı seklindedir: ust satir sagdan sola, alt satir soldan saga.
            // Bu yuzden "ayni yon" ancak gorsel yuva uzerinden ifade edilebilir:
            // oyuncunun taslari her zaman gorsel yuvayi KUCULTUR (yuva 1 = sag alt).
            for (int die = 1; die <= 6; die++)
            {
                for (int point = 1; point <= BoardLayout.PointCount; point++)
                {
                    int target = point + (die * direction);
                    if (target < 1 || target > BoardLayout.PointCount)
                    {
                        continue;
                    }

                    int fromSlot = layout.VisualSlot(point);
                    int toSlot = layout.VisualSlot(target);
                    Assert.That(toSlot, Is.EqualTo(fromSlot - die),
                                "oyuncunun taslari her zaman tepsiye dogru gitmeli: " +
                                point + " -> " + target + " (zar " + die + ")");
                }
            }
        }

        [TestCase((sbyte)-1, false)]
        [TestCase((sbyte)1, true)]
        public void HumanBearOffTarget_IsBottomRight(sbyte humanColor, bool flip)
        {
            BoardLayout layout = BoardLayout.Calculate(Width, Height, humanColor < 0, flip);
            float half = layout.Board.Height * 0.5f;

            // Beyaz 24'u gecerek, Siyah 1'i gecerek toplar. Toplama hedefi, ev bolgesinin
            // hemen otesindeki gorsel yuvadir.
            int edge = humanColor > 0 ? 24 : 1;
            LayoutRect r = layout.PointAt(edge);

            Assert.That(r.Y, Is.GreaterThanOrEqualTo(half - 0.01f),
                        "toplama kenari alt satirda olmali");
            Assert.That(r.X, Is.GreaterThanOrEqualTo(layout.Bar.X + layout.Bar.Width - 0.01f),
                        "toplama kenari sag yarida olmali");
        }

        [Test]
        public void Flip_IsIndependentOfTrayBottom()
        {
            // Tepsi yarimlari ile hane aynalamasi ayri kararlardir; ikisi de bagimsiz
            // uygulanabilmeli (varsayilan Siyah: tepsi alt, aynalama kapali).
            BoardLayout a = BoardLayout.Calculate(Width, Height, true, false);
            BoardLayout b = BoardLayout.Calculate(Width, Height, false, true);

            Assert.That(a.WhiteTray.Y, Is.LessThan(b.WhiteTray.Y),
                        "tepsi yarimlari takas edilmeli");
            Assert.That(a.PointAt(1).Y, Is.GreaterThan(b.PointAt(1).Y),
                        "hane 1 aynalamada ust satira tasinmali");
        }

        // ------------------------------------------------------------------
        // Yardimcilar
        // ------------------------------------------------------------------

        private static bool Overlaps(LayoutRect a, LayoutRect b)
        {
            const float Epsilon = 0.01f;
            return a.X + Epsilon < b.X + b.Width && b.X + Epsilon < a.X + a.Width &&
                   a.Y + Epsilon < b.Y + b.Height && b.Y + Epsilon < a.Y + a.Height;
        }

        private static void AssertRectEqual(LayoutRect expected, LayoutRect actual, string label)
        {
            Assert.That(actual.X, Is.EqualTo(expected.X).Within(0.01f), label + ": X");
            Assert.That(actual.Y, Is.EqualTo(expected.Y).Within(0.01f), label + ": Y");
            Assert.That(actual.Width, Is.EqualTo(expected.Width).Within(0.01f), label + ": genislik");
            Assert.That(actual.Height, Is.EqualTo(expected.Height).Within(0.01f), label + ": yukseklik");
        }
    }
}
