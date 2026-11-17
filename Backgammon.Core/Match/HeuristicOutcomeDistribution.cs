using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.3: tek skaler equity'den 6'lı sonuç dağılımı türeten <b>sezgisel</b> model.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Ağ bugün tek skaler equity üretir (<c>ml/model.py</c>, <c>value_head = Linear(h2, 1)</c>).
    /// Tek skalerden 6'lı dağılım <b>bilgi olarak</b> türetilemez; bu yüzden açık bir model
    /// varsayımı yapılır. Faz 6'da ağın 6 çıktılı değer başı bunu değiştirecek; arayüz
    /// (<see cref="IOutcomeDistributionEvaluator"/>) tam bunun için şimdi tanımlıdır.
    /// </para>
    /// <para><b>Model (kesin):</b></para>
    /// <list type="number">
    /// <item><c>W(e) = 0.5 + 0.5 · tanh(k·e) / tanh(3k)</c>, <c>k = 1.1</c>.
    ///   <c>W(0) = 0.5</c>, <c>W(±3) = 1/0</c>, kesin artan, sürekli.</item>
    /// <item><c>L(e) = 1 − W(e)</c>.</item>
    /// <item><c>q = ln(g) / ln(0.5)</c>; <c>g</c> = temas varsa <c>0.20</c>, saf yarışta <c>0.05</c>
    ///   (yer tutucu, §9.2'de kalibre edilir). <c>g</c>, <c>pipDifference</c> ile
    ///   <c>g · (1 + clamp(pip/200, −0.5, +0.5))</c> olarak ölçeklenir.</item>
    /// <item><c>WinGammon = W^(1+q)</c>, <c>LoseGammon = L^(1+q)</c>. Böylece
    ///   <c>e = 0 ⇒ WinGammon = LoseGammon</c> (simetri) ve <c>e = 3 ⇒ WinGammon = 1</c>.</item>
    /// <item><c>WinBackgammon = WinGammon²</c>, <c>LoseBackgammon = LoseGammon²</c>.
    ///   <c>e = +3 ⇒ WinBackgammon = 1</c> seçildi (gerekçe: equity +3 yalnızca kesin backgammon
    ///   ile mümkündür; §4.3 iki seçeneğe de izin verir).</item>
    /// <item><c>isContact == false</c> ⇒ <c>WinBackgammon = LoseBackgammon = 0</c> <b>zorunlu</b>.</item>
    /// </list>
    /// <para>
    /// Monotonluk: <c>W</c> artan ⇒ <c>W^(1+q)</c> artan ⇒ <c>WinGammon</c> azalmaz;
    /// <c>L</c> azalan ⇒ <c>LoseGammon</c> artmaz. Deterministik ve allocation'sız.
    /// </para>
    /// </remarks>
    public static class HeuristicOutcomeDistribution
    {
        /// <summary>Win eğrisinin dikliği.</summary>
        public const double WinSlope = 1.1;

        /// <summary>Temasta mars oranı (yer tutucu).</summary>
        public const double ContactGammonRate = 0.20;

        /// <summary>Saf yarışta mars oranı (yer tutucu).</summary>
        public const double RaceGammonRate = 0.05;

        private static readonly double TanhThreeK = Math.Tanh(3.0 * WinSlope);

        /// <summary>Skaler equity'den 6'lı dağılım türetir. Deterministik, allocation yapmaz.</summary>
        public static OutcomeDistribution FromEquity(double equity, bool isContact, int pipDifference)
        {
            if (double.IsNaN(equity))
            {
                throw new ArgumentOutOfRangeException(nameof(equity));
            }

            double e = equity;
            if (e > 3.0)
            {
                e = 3.0;
            }
            else if (e < -3.0)
            {
                e = -3.0;
            }

            double win = 0.5 + (0.5 * Math.Tanh(WinSlope * e) / TanhThreeK);
            if (win < 0.0)
            {
                win = 0.0;
            }
            else if (win > 1.0)
            {
                win = 1.0;
            }

            double lose = 1.0 - win;

            double rate = isContact ? ContactGammonRate : RaceGammonRate;
            // |pipDifference| kullanilir: aksi halde perspektif degisince mars orani degisir ve
            // MatchAwareEvaluator'un antisimetrisi (Test 23) bozulur.
            double scaled = Math.Abs(pipDifference) / 200.0;
            if (scaled > 0.5)
            {
                scaled = 0.5;
            }
            else if (scaled < -0.5)
            {
                scaled = -0.5;
            }

            rate *= 1.0 + scaled;
            if (rate < 1e-6)
            {
                rate = 1e-6;
            }
            else if (rate > 0.999)
            {
                rate = 0.999;
            }

            double q = Math.Log(rate) / Math.Log(0.5);
            double winGammon = Math.Pow(win, 1.0 + q);
            double loseGammon = Math.Pow(lose, 1.0 + q);

            double winBackgammon = isContact ? winGammon * winGammon : 0.0;
            double loseBackgammon = isContact ? loseGammon * loseGammon : 0.0;

            return new OutcomeDistribution(
                (float)win,
                (float)winGammon,
                (float)winBackgammon,
                (float)loseGammon,
                (float)loseBackgammon);
        }
    }
}
