using System;

namespace Backgammon.UI
{
    /// <summary>Eksen hizali dikdortgen (Unity'den bagimsiz; <c>UnityEngine.Rect</c> kullanilmaz).</summary>
    public readonly struct LayoutRect
    {
        public readonly float X;
        public readonly float Y;
        public readonly float Width;
        public readonly float Height;

        public LayoutRect(float x, float y, float width, float height)
        {
            X = x;
            Y = y;
            Width = width;
            Height = height;
        }

        public float Right
        {
            get { return X + Width; }
        }

        public float Bottom
        {
            get { return Y + Height; }
        }

        public float Area
        {
            get { return Width * Height; }
        }

        /// <summary>Nokta dikdortgenin icinde mi? (sinirlar dahil)</summary>
        public bool Contains(float px, float py)
        {
            return px >= X && px <= Right && py >= Y && py <= Bottom;
        }

        /// <summary>Iki dikdortgen pozitif alanda kesisiyor mu? (kenar temaslari kesisim sayilmaz)</summary>
        public bool Overlaps(in LayoutRect other)
        {
            return X < other.Right && other.X < Right && Y < other.Bottom && other.Y < Bottom;
        }

        public override string ToString()
        {
            return "(" + X.ToString("F1") + "," + Y.ToString("F1") + " " +
                   Width.ToString("F1") + "x" + Height.ToString("F1") + ")";
        }
    }

    /// <summary>
    /// Faz 5 Bolum 6.4: tahta yerlesimi. 24 hane, bar, toplama tepsileri ve kup yuvasi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Yerlesim:</b> genislik 12 hane kolonuna + 1 bar kolonuna + 1 tepsi seridine bolunur;
    /// yukseklik 2 satira. Alt satir haneleri 1..12 (soldan saga 12, 11, ..., 1), ust satir
    /// haneleri 13..24 (soldan saga 13, 14, ..., 24). Bar 6. ve 7. kolon arasindadir.
    /// </para>
    /// <para>
    /// <b>Degismez:</b> 24 hane dikdortgeni <b>birbiriyle kesis mez</b> ve hepsi tahta sinirlari
    /// icindedir (Bolum 8, Test 38).
    /// </para>
    /// <para>
    /// <b>Bakis acisi:</b> <c>flip</c> <c>true</c> iken hane numaralari 180 derece dondurulur
    /// (<c>gorsel yuva = 25 - hane</c>). Boylece oyuncu Beyaz oynarken de kendi ev bolgesi
    /// <b>sag altta</b> kalir ve taslarini Siyah oynarken oldugu gibi <b>ayni yone</b> hareket
    /// ettirir. Tahta cercevesi, bar ve tepsi seridi <b>degismez</b>.
    /// </para>
    /// <para>
    /// <b>Orta bant:</b> ust ve alt ucgenlerin uclari birbirine <b>degmez</b>. Iki satir
    /// arasinda <see cref="CenterGapRatio"/> kadar bos bir bant birakilir
    /// (<see cref="CenterBand"/>). Gercek bir tahtada da ucgen uclari orta cizgide birlesmez;
    /// arada tahta yuzeyi gorunur. Bu bant ileride logo/rozet yerlestirmek icin de kullanilabilir.
    /// </para>
    /// </remarks>
    public sealed class BoardLayout
    {
        /// <summary>Hane sayisi.</summary>
        public const int PointCount = 24;

        /// <summary>
        /// Ust ve alt ucgen uclari arasindaki boslugun tahta yuksekligine orani.
        /// </summary>
        /// <remarks>
        /// <c>0.06</c> secildi: 1080 px yuksekliginde ~65 px, canli oyuncuda (892 px) ~54 px.
        /// Daha kucuk degerde ucgen uclari yeniden "birlesik" gorunur; daha buyuk degerde
        /// haneler kisalir ve 15'lik yiginlar sikisir.
        /// </remarks>
        public const float CenterGapRatio = 0.06f;

        private readonly LayoutRect[] _points = new LayoutRect[PointCount];
        private bool _flip;

        /// <summary>Tum tahta alani.</summary>
        public LayoutRect Board { get; private set; }

        /// <summary>Bar seridi.</summary>
        public LayoutRect Bar { get; private set; }

        /// <summary>Toplama tepsisi seridi (Beyaz ve Siyah ayni seritte ust/alt yarim).</summary>
        public LayoutRect Tray { get; private set; }

        /// <summary>Beyaz toplama tepsisi (tepsinin alt yarisi).</summary>
        public LayoutRect WhiteTray { get; private set; }

        /// <summary>Siyah toplama tepsisi (tepsinin ust yarisi).</summary>
        public LayoutRect BlackTray { get; private set; }

        /// <summary>Kup yuvasi (bar'in ust yarisi).</summary>
        public LayoutRect Cube { get; private set; }

        /// <summary>
        /// Ust ve alt ucgen uclari arasindaki bos bandin yuksekligi (piksel).
        /// </summary>
        public float CenterGap { get; private set; }

        /// <summary>
        /// Orta bant: iki hane satiri arasindaki bos alan (tam tahta genisligi).
        /// </summary>
        /// <remarks>
        /// <para>
        /// Bant <b>tam genisliktedir</b>; bar seridi ve tepsi seridi bu bandin uzerinden
        /// gecer (onlar dikey olarak kesintisizdir, gercek tahtada da oyledir). Bu yuzden
        /// bant, logo gibi bir ogenin yerlestirilecegi <b>oyun alani</b> bandidir; bar ve
        /// tepsi zaten kendi dikdortgenlerine sahiptir.
        /// </para>
        /// <para>
        /// Hane dikdortgenleri bu bantla <b>kesismez</b>; ucgen uclari bandin kenarinda
        /// biter.
        /// </para>
        /// </remarks>
        public LayoutRect CenterBand { get; private set; }

        /// <summary>
        /// Hane dikdortgenleri; <c>Points[i]</c> = <b>gorsel yuva</b> <c>i + 1</c>.
        /// </summary>
        /// <remarks>
        /// Dizi <b>gorsel</b> yuvalara gore indekslidir; hane numarasindan dikdortgene gitmek
        /// icin <see cref="PointAt"/> kullanilmalidir (aynalamada ikisi farklidir).
        /// </remarks>
        public LayoutRect[] Points
        {
            get { return _points; }
        }

        /// <summary>Hane numaralari 180 derece donduruldu mu?</summary>
        public bool Flip
        {
            get { return _flip; }
        }

        /// <summary>Hanenin cizildigi gorsel yuva (1..24).</summary>
        /// <remarks>
        /// Aynalama kapaliyken <c>gorsel yuva == hane</c>; acikken <c>gorsel yuva = 25 - hane</c>.
        /// Ucgen rengi bu yuvaya gore secilir, boylece aynalama tahtanin renk desenini bozmaz.
        /// </remarks>
        public int VisualSlot(int point)
        {
            if (point < 1 || point > PointCount)
            {
                throw new ArgumentOutOfRangeException(nameof(point));
            }

            return _flip ? (PointCount + 1 - point) : point;
        }

        /// <summary>Hanenin dikdortgeni (1..24).</summary>
        public LayoutRect PointAt(int point)
        {
            return _points[VisualSlot(point) - 1];
        }

        /// <summary>Verilen en-boy icin yerlesimi hesaplar.</summary>
        public static BoardLayout Calculate(float width, float height)
        {
            return Calculate(width, height, false, false);
        }

        /// <summary>
        /// Verilen en-boy icin yerlesimi hesaplar; <paramref name="humanTrayBottom"/> ile
        /// <b>yalnizca toplama tepsileri</b> yer degistirir.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <b>Neden:</b> oyuncu hangi rengi secerse secsin kendi toplama tepsisi <b>sag altta</b>
        /// olmalidir. Insan Siyah oynarken <see cref="BlackTray"/> alt yariya, <see cref="WhiteTray"/>
        /// ust yariya tasinir.
        /// </para>
        /// <para>
        /// <b>Hane yerlesimi bu parametreden etkilenmez.</b> Yalnizca tepsi yarimlari takas
        /// edilir; hane numaralari ve motor durumu her zaman aynidir.
        /// </para>
        /// </remarks>
        public static BoardLayout Calculate(float width, float height, bool humanTrayBottom)
        {
            return Calculate(width, height, humanTrayBottom, false);
        }

        /// <summary>
        /// Verilen en-boy icin yerlesimi hesaplar; <paramref name="humanTrayBottom"/> tepsi
        /// yarimlarini, <paramref name="flip"/> hane numaralarinin yonunu belirler.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <b>Neden <paramref name="flip"/>:</b> motor Beyaz'i <c>1 -&gt; 24</c>, Siyah'i
        /// <c>24 -&gt; 1</c> yonunde hareket ettirir. Oyuncu Beyaz oynadiginda tahta
        /// dondurulmezse kendi taslari <b>ters yone</b> gidiyor gibi gorunur. <c>flip</c>
        /// acikken hane <c>p</c> gorsel yuvaya <c>25 - p</c> cizilir; boylece oyuncunun ev
        /// bolgesi ve hareket yonu her iki renkte de <b>ayni</b> kalir.
        /// </para>
        /// <para>
        /// <b>Degismez:</b> tahta cercevesi, bar seridi ve tepsi seridi aynalama ile
        /// <b>yer degistirmez</b>; yalnizca hane numaralari dondurulur.
        /// </para>
        /// </remarks>
        public static BoardLayout Calculate(float width, float height, bool humanTrayBottom,
                                           bool flip)
        {
            if (!(width > 0f))
            {
                throw new ArgumentOutOfRangeException(nameof(width));
            }

            if (!(height > 0f))
            {
                throw new ArgumentOutOfRangeException(nameof(height));
            }

            var layout = new BoardLayout();
            layout._flip = flip;
            layout.Board = new LayoutRect(0f, 0f, width, height);

            float trayWidth = width * 0.08f;
            float playWidth = width - trayWidth;
            float barWidth = playWidth * 0.06f;
            float columnWidth = (playWidth - barWidth) / 12f;
            float rowHeight = height * 0.5f;

            // Komsu hanelerin kenarlari **ayni ifadeden** turetilir. Aksi halde
            // (c + 1) * columnWidth ile c * columnWidth + columnWidth kayan noktada
            // birbirini tutmaz ve dikdortgenler 1e-13 mertebesinde ust uste biner
            // (Bolum 8, Test 38 bunu yakalar).
            float barLeft = 6f * columnWidth;
            float rightGroupLeft = barLeft + barWidth;
            float playRight = rightGroupLeft + (6f * columnWidth);

            layout.Tray = new LayoutRect(playRight, 0f, width - playRight, height);
            layout.WhiteTray = new LayoutRect(playRight, humanTrayBottom ? 0f : rowHeight,
                                              width - playRight, rowHeight);
            layout.BlackTray = new LayoutRect(playRight, humanTrayBottom ? rowHeight : 0f,
                                              width - playRight, rowHeight);
            layout.Bar = new LayoutRect(barLeft, 0f, barWidth, height);
            layout.Cube = new LayoutRect(barLeft, 0f, barWidth, rowHeight);

            // Orta bant: ust ve alt ucgen uclari arasinda bos alan. Iki satirin yuksekligi
            // bu bandin yarisi kadar kisaltilir; boylece ucgen uclari orta cizgide birlesmez.
            float centerGap = height * CenterGapRatio;
            float gapHalf = centerGap * 0.5f;
            float pointHeight = rowHeight - gapHalf;
            layout.CenterGap = centerGap;
            layout.CenterBand = new LayoutRect(0f, rowHeight - gapHalf, width, centerGap);

            for (int column = 0; column < 12; column++)
            {
                float baseX = column < 6 ? 0f : rightGroupLeft;
                int local = column < 6 ? column : column - 6;
                float left = baseX + (local * columnWidth);
                float right = baseX + ((local + 1) * columnWidth);
                float cellWidth = right - left;

                // Alt satir: hane 12 -> kolon 0, hane 1 -> kolon 11. Ucgen yukari bakar,
                // ucu orta bandin alt kenarinda durur.
                int bottomPoint = 12 - column;
                layout._points[bottomPoint - 1] = new LayoutRect(left, rowHeight + gapHalf,
                                                                 cellWidth, pointHeight);

                // Ust satir: hane 13 -> kolon 0, hane 24 -> kolon 11. Ucgen asagi bakar,
                // ucu orta bandin ust kenarinda durur.
                int topPoint = 13 + column;
                layout._points[topPoint - 1] = new LayoutRect(left, 0f, cellWidth, pointHeight);
            }

            return layout;
        }
    }
}
