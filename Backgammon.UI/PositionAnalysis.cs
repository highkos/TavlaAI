using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 5.1: analiz panelinin ve UI'in gordugu <b>tek</b> veri yapisi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Kural:</b> UI <b>asla</b> <see cref="IPositionEvaluator"/>'i dogrudan cagirmaz; yalnizca
    /// <see cref="PositionAnalysis"/> tuketir. Boylece Faz 6'da 6 cikti li deger basi geldiginde UI
    /// kodu degismez; yalnizca <see cref="Distribution"/> alani <c>null</c> olmaktan cikar.
    /// </para>
    /// <para>
    /// <b>Spesifikasyondan sapma (raporlandi):</b> Bolum 5.1 alanlari <c>readonly</c> olarak listeler
    /// ama yapici vermez. Burada tum alanlari dolduran tek bir yapici eklenmistir; aksi halde
    /// <c>readonly struct</c> disaridan doldurulamaz.
    /// </para>
    /// </remarks>
    public readonly struct PositionAnalysis
    {
        /// <summary>Kupsuz money equity, <c>[-3,3]</c>.</summary>
        public readonly double Equity;

        /// <summary><c>ME = 2*MWC - 1</c>; money game'de <see cref="Equity"/>'ye esittir.</summary>
        public readonly double MatchEquity;

        /// <summary>Maci kazanma olasiligi; money game'de <see cref="double.NaN"/>.</summary>
        public readonly double MatchWinningChance;

        /// <summary>6'li sonuc dagilimi; <c>null</c> ise dagilim yok.</summary>
        public readonly OutcomeDistribution? Distribution;

        /// <summary>Deger bearoff veritabanindan mi geldi?</summary>
        public readonly bool FromBearoffDatabase;

        /// <summary>Deger kesin mi? (bearoff DB veya terminal pozisyon)</summary>
        public readonly bool IsExact;

        /// <summary>Siradaki oyuncunun pip sayisi.</summary>
        public readonly int PipCountActive;

        /// <summary>Rakibin pip sayisi.</summary>
        public readonly int PipCountOpponent;

        /// <summary>Siradaki oyuncunun toplamak icin beklenen tur sayisi; <c>-1</c> = bilinmiyor.</summary>
        public readonly int RollsToOffActive;

        /// <summary>Rakibin toplamak icin beklenen tur sayisi; <c>-1</c> = bilinmiyor.</summary>
        public readonly int RollsToOffOpponent;

        /// <summary>Kup karari; <c>null</c> ise kup baglami yok.</summary>
        public readonly CubeDecision? Cube;

        public PositionAnalysis(double equity, double matchEquity, double matchWinningChance,
                                OutcomeDistribution? distribution, bool fromBearoffDatabase, bool isExact,
                                int pipCountActive, int pipCountOpponent, int rollsToOffActive,
                                int rollsToOffOpponent, CubeDecision? cube)
        {
            Equity = equity;
            MatchEquity = matchEquity;
            MatchWinningChance = matchWinningChance;
            Distribution = distribution;
            FromBearoffDatabase = fromBearoffDatabase;
            IsExact = isExact;
            PipCountActive = pipCountActive;
            PipCountOpponent = pipCountOpponent;
            RollsToOffActive = rollsToOffActive;
            RollsToOffOpponent = rollsToOffOpponent;
            Cube = cube;
        }

        public override string ToString()
        {
            return "E=" + Equity.ToString("F4") + " ME=" + MatchEquity.ToString("F4") +
                   (IsExact ? " exact" : " estimate");
        }
    }
}
