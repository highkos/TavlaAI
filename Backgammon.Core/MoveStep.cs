namespace Backgammon.Core
{
    /// <summary>
    /// Tek bir taş hareketi. Sabit boyutlu, dizi/liste içermez. Bölüm 2.2.
    /// </summary>
    public struct MoveStep
    {
        /// <summary>Kaynak hane. Bar için 0 (Beyaz) veya 25 (Siyah).</summary>
        public byte From;

        /// <summary>Hedef hane. Taş toplamada Beyaz 25, Siyah 0 (board'a erişilmez).</summary>
        public byte To;

        /// <summary>Kullanılan zar (1..6).</summary>
        public byte Die;

        /// <summary><see cref="MoveFlags"/> bit maskesi.</summary>
        public byte Flags;

        public MoveStep(byte from, byte to, byte die, MoveFlags flags)
        {
            From = from;
            To = to;
            Die = die;
            Flags = (byte)flags;
        }

        public bool IsHit => (Flags & (byte)MoveFlags.Hit) != 0;

        public bool IsBearOff => (Flags & (byte)MoveFlags.BearOff) != 0;

        public bool IsFromBar => (Flags & (byte)MoveFlags.FromBar) != 0;

        public override string ToString()
        {
            return From + "->" + To + " (" + Die + ") flags=" + Flags;
        }
    }
}
