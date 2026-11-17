namespace Backgammon.Core
{
    /// <summary>
    /// Faz 2 v4 Bölüm 2: 221 elemanlı giriş vektörünün nöron haritası.
    /// Sihirli sayı kullanılmaz; tüm indeksler buradan okunur.
    /// </summary>
    public static class VectorLayout
    {
        /// <summary>Fiziksel hane sayısı.</summary>
        public const int Points = 24;

        /// <summary>Hane başına nöron sayısı (blot, kapi, 3+, yogunluk).</summary>
        public const int PointBlockSize = 4;

        /// <summary>Aktif oyuncunun hane blogu baslangici (nöron 000-095).</summary>
        public const int ActiveOffset = 0;

        /// <summary>Rakibin hane blogu baslangici (nöron 096-191).</summary>
        public const int OppOffset = 96;

        public const int ActiveBar = 192;
        public const int OppBar = 193;
        public const int ActiveOff = 194;
        public const int OppOff = 195;
        public const int CubeOwner = 196;
        public const int CubeValue = 197;
        public const int IsMoneyGame = 198;
        public const int IsCrawford = 199;
        public const int ActivePip = 200;
        public const int OppPip = 201;
        public const int ActiveEscaped = 202;
        public const int OppEscaped = 203;
        public const int IsContact = 204;

        /// <summary>Aktif oyuncunun "away" one-hot blogu (nöron 205-212).</summary>
        public const int ActiveAwayOffset = 205;

        /// <summary>Rakibin "away" one-hot blogu (nöron 213-220).</summary>
        public const int OppAwayOffset = 213;

        /// <summary>"8+ away" kovasi dahil kova sayisi.</summary>
        public const int AwayBuckets = 8;

        /// <summary>Vektörün toplam eleman sayisi.</summary>
        public const int TotalSize = 221;

        // Hane blogu icindeki alt indeksler (k).
        public const int Blot = 0;
        public const int Gate = 1;
        public const int ThreePlus = 2;
        public const int Density = 3;

        /// <summary>Aktif blogun (j, k) nöron indeksi. j = 1..24.</summary>
        public static int ActivePointIndex(int j, int k)
        {
            return ActiveOffset + PointBlockSize * (j - 1) + k;
        }

        /// <summary>Rakip blogun (j, k) nöron indeksi. j = 1..24.</summary>
        public static int OppPointIndex(int j, int k)
        {
            return OppOffset + PointBlockSize * (j - 1) + k;
        }
    }
}