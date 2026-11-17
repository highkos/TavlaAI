using System;
using System.Globalization;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 6.2 / 6.9: <see cref="PositionAnalysis"/>'i goruntuleme metinlerine cevirir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>tr-TR bicimi:</b> ondalik ayirici <b>virguldur</b> (Bolum 8, Test 31). Bicimlendirme
    /// <see cref="CultureInfo.GetCultureInfo(string)"/> ile sabitlenir; is parcacigi kulturunden
    /// bagimsizdir.
    /// </para>
    /// <para>
    /// Bilinmeyen degerler (<c>-1</c>) <b>em dash</b> (<c>U+2014</c>) olarak gosterilir.
    /// </para>
    /// </remarks>
    public sealed class AnalysisViewModel
    {
        /// <summary>Bilinmeyen deger icin gosterim.</summary>
        public const string Unknown = "\u2014";

        private static readonly CultureInfo Tr = CultureInfo.GetCultureInfo("tr-TR");

        /// <summary>Kupsuz money equity metni (or. <c>"+0,42"</c>).</summary>
        public string EquityText { get; private set; }

        /// <summary>Mac equity metni.</summary>
        public string MatchEquityText { get; private set; }

        /// <summary>Maci kazanma olasiligi metni (yuzde); money game'de <see cref="Unknown"/>.</summary>
        public string MatchWinningChanceText { get; private set; }

        /// <summary>Rozet metni: <c>"Kesin"</c> veya <c>"Tahmin"</c>.</summary>
        public string Badge { get; private set; }

        /// <summary>Deger kesin mi?</summary>
        public bool IsExact { get; private set; }

        /// <summary>Pip metni (or. <c>"167 / 158"</c>).</summary>
        public string PipText { get; private set; }

        /// <summary>Siradaki oyuncunun toplama turu metni.</summary>
        public string RollsToOffActiveText { get; private set; }

        /// <summary>Rakibin toplama turu metni.</summary>
        public string RollsToOffOpponentText { get; private set; }

        /// <summary>Mars olasiligi metni (kazanma / kaybetme); dagilim yoksa <see cref="Unknown"/>.</summary>
        public string GammonText { get; private set; }

        /// <summary>Kup karari metni; kup baglami yoksa <see cref="Unknown"/>.</summary>
        public string CubeText { get; private set; }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary>Analizi bicimlendirir.</summary>
        public void Update(in PositionAnalysis analysis)
        {
            EquityText = Signed(analysis.Equity);
            MatchEquityText = Signed(analysis.MatchEquity);

            MatchWinningChanceText = double.IsNaN(analysis.MatchWinningChance)
                ? Unknown
                : (analysis.MatchWinningChance * 100.0).ToString("F1", Tr) + "%";

            IsExact = analysis.IsExact;
            Badge = analysis.IsExact ? "Kesin" : "Tahmin";

            PipText = analysis.PipCountActive.ToString(Tr) + " / " + analysis.PipCountOpponent.ToString(Tr);

            RollsToOffActiveText = Rolls(analysis.RollsToOffActive);
            RollsToOffOpponentText = Rolls(analysis.RollsToOffOpponent);

            if (analysis.Distribution.HasValue)
            {
                OutcomeDistribution d = analysis.Distribution.Value;
                GammonText = (d.WinGammon * 100.0).ToString("F1", Tr) + "% / " +
                             (d.LoseGammon * 100.0).ToString("F1", Tr) + "%";
            }
            else
            {
                GammonText = Unknown;
            }

            if (analysis.Cube.HasValue)
            {
                CubeDecision c = analysis.Cube.Value;
                CubeText = (c.ShouldDouble ? "Ciftle" : "Ciftleme") + " / " +
                           (c.ShouldTake ? "Kabul" : "Reddet");
            }
            else
            {
                CubeText = Unknown;
            }

            Changed?.Invoke();
        }

        private static string Signed(double value)
        {
            string text = value.ToString("F2", Tr);
            return value > 0.0 ? "+" + text : text;
        }

        private static string Rolls(int value)
        {
            return value < 0 ? Unknown : value.ToString(Tr);
        }
    }
}
