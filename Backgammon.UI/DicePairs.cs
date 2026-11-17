namespace Backgammon.UI
{
    /// <summary>
    /// 21 siralanmamis zar cifti (Bolum 3.9 ile ayni numaralandirma) ve agirliklari.
    /// </summary>
    /// <remarks>
    /// Dublede tek cift (agirlik 1), digerlerinde iki siralama (agirlik 2); toplam agirlik 36'dir.
    /// </remarks>
    internal static class DicePairs
    {
        public const int Count = 21;

        public static readonly int[] First;
        public static readonly int[] Second;
        public static readonly int[] Weight;

        static DicePairs()
        {
            First = new int[Count];
            Second = new int[Count];
            Weight = new int[Count];

            int index = 0;
            for (int d1 = 1; d1 <= 6; d1++)
            {
                for (int d2 = d1; d2 <= 6; d2++)
                {
                    First[index] = d1;
                    Second[index] = d2;
                    Weight[index] = d1 == d2 ? 1 : 2;
                    index++;
                }
            }
        }
    }
}
