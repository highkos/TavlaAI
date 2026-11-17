namespace Backgammon.Core
{
    /// <summary>
    /// Oyun sonucu. Bölüm 2.4.
    /// </summary>
    /// <remarks>
    /// <see cref="Points"/> yalnızca mars çarpanını (1/2/3) taşır; <c>cubeValue</c> çarpanı
    /// burada UYGULANMAZ (Faz 3 <c>Points / cubeValue</c> uygular).
    /// </remarks>
    public struct GameResult
    {
        /// <summary>+1 Beyaz kazandı, -1 Siyah kazandı, 0 geçersiz/oyun bitmedi.</summary>
        public sbyte Winner;

        public GameResultType ResultType;

        /// <summary>Mars çarpanı: 1 (Single), 2 (Gammon), 3 (Backgammon). cubeValue hariç.</summary>
        public int Points;

        public GameResult(sbyte winner, GameResultType resultType, int points)
        {
            Winner = winner;
            ResultType = resultType;
            Points = points;
        }

        public bool IsValid => Winner != 0;

        public override string ToString()
        {
            return "winner=" + Winner + " type=" + ResultType + " points=" + Points;
        }
    }
}
