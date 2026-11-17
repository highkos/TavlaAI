using System;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 6 §12.2 Test 49–52: dışlayıcı 6 sınıflı sonuç dağılımı.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Ağ çıktısı <b>dışlayıcı</b> 6 sınıftır (<c>W, GW, BW, L, GL, BL</c>, toplam 1).
    /// <see cref="OutcomeDistribution"/> ise <b>kümülatif</b> alanlar taşır;
    /// <see cref="OutcomeDistribution.FromProbabilities"/> dönüşümü yapar.
    /// </para>
    /// <para>
    /// <b>Tek doğruluk kaynağı</b> <see cref="OutcomeDistribution.Equity"/>'dir; bu testler
    /// dışlayıcı formülün <c>W + 2·GW + 3·BW − (L + 2·GL + 3·BL)</c> ile aynı sonucu
    /// verdiğini doğrular.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class OutcomeDistributionV2Tests
    {
        private const double Tolerance = 1e-6;

        // ------------------------------------------------------------------
        // Test 49
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_EquityFormula_Exclusive()
        {
            // Dışlayıcı birim vektörler: E tam olarak +3, +2, +1, -1, -2, -3 olmalı.
            double[] expected = { 1.0, 2.0, 3.0, -1.0, -2.0, -3.0 };
            string[] names = { "W", "GW", "BW", "L", "GL", "BL" };

            for (int i = 0; i < 6; i++)
            {
                float[] p = new float[6];
                p[i] = 1f;

                OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                    p[0], p[1], p[2], p[3], p[4], p[5]);

                Assert.That(d.IsValid, Is.True, names[i] + " birim vektörü geçerli olmalı");
                Assert.That(d.Equity, Is.EqualTo(expected[i]).Within(Tolerance),
                    names[i] + " birim vektöründe E = " + expected[i]);
            }

            // Karışık bir dağılımda dışlayıcı formül ile Equity aynı olmalı.
            float w = 0.40f, gw = 0.15f, bw = 0.05f, l = 0.30f, gl = 0.08f, bl = 0.02f;
            double exclusive = w + 2.0 * gw + 3.0 * bw - (l + 2.0 * gl + 3.0 * bl);

            OutcomeDistribution mixed = OutcomeDistribution.FromProbabilities(w, gw, bw, l, gl, bl);
            Assert.That(mixed.IsValid, Is.True);
            Assert.That(mixed.Equity, Is.EqualTo(exclusive).Within(Tolerance),
                "E = W + 2·GW + 3·BW − (L + 2·GL + 3·BL)");
        }

        // ------------------------------------------------------------------
        // Test 50
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_IsAntisymmetric()
        {
            float w = 0.40f, gw = 0.15f, bw = 0.05f, l = 0.30f, gl = 0.08f, bl = 0.02f;

            OutcomeDistribution white = OutcomeDistribution.FromProbabilities(w, gw, bw, l, gl, bl);
            // Oyuncu değişince kazanma/kaybetme sınıfları yer değiştirir.
            OutcomeDistribution black = OutcomeDistribution.FromProbabilities(l, gl, bl, w, gw, bw);

            Assert.That(white.IsValid, Is.True);
            Assert.That(black.IsValid, Is.True);

            Assert.That(black.Equity, Is.EqualTo(-white.Equity).Within(Tolerance),
                "E(-p) = -E(p)");

            Assert.That(black.Win, Is.EqualTo(white.Lose).Within(1e-6f), "W ↔ L");
            Assert.That(black.WinGammon, Is.EqualTo(white.LoseGammon).Within(1e-6f), "WG ↔ LG");
            Assert.That(black.WinBackgammon, Is.EqualTo(white.LoseBackgammon).Within(1e-6f), "WBG ↔ LBG");
            Assert.That(black.LoseGammon, Is.EqualTo(white.WinGammon).Within(1e-6f), "LG ↔ WG");
            Assert.That(black.LoseBackgammon, Is.EqualTo(white.WinBackgammon).Within(1e-6f), "LBG ↔ WBG");
        }

        // ------------------------------------------------------------------
        // Test 51
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_FromProbabilities_Normalizes()
        {
            // Toplam 2 olan bir vektör: normalize edilince toplam 1 olmalı.
            OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                0.80f, 0.30f, 0.10f, 0.60f, 0.16f, 0.04f);

            Assert.That(d.IsValid, Is.True);

            double total = d.WinSingle + d.WinGammonOnly + d.WinBackgammonOnly
                         + d.LoseSingle + d.LoseGammonOnly + d.LoseBackgammonOnly;
            Assert.That(total, Is.EqualTo(1.0).Within(1e-5), "dışlayıcı toplam 1 olmalı");

            // Normalize edilmiş değerler beklenen oranlarla aynı olmalı.
            Assert.That(d.WinSingle, Is.EqualTo(0.40f).Within(1e-5f), "W = 0.80/2");
            Assert.That(d.WinGammonOnly, Is.EqualTo(0.15f).Within(1e-5f), "GW = 0.30/2");
            Assert.That(d.WinBackgammonOnly, Is.EqualTo(0.05f).Within(1e-5f), "BW = 0.10/2");
            Assert.That(d.LoseSingle, Is.EqualTo(0.30f).Within(1e-5f), "L = 0.60/2");
            Assert.That(d.LoseGammonOnly, Is.EqualTo(0.08f).Within(1e-5f), "GL = 0.16/2");
            Assert.That(d.LoseBackgammonOnly, Is.EqualTo(0.02f).Within(1e-5f), "BL = 0.04/2");

            // Zaten toplam 1 olan vektör değişmemeli.
            OutcomeDistribution unit = OutcomeDistribution.FromProbabilities(
                0.40f, 0.15f, 0.05f, 0.30f, 0.08f, 0.02f);
            Assert.That(unit.WinSingle, Is.EqualTo(0.40f).Within(1e-6f));
            Assert.That(unit.Equity, Is.EqualTo(d.Equity).Within(1e-6));
        }

        // ------------------------------------------------------------------
        // Test 52
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_FromProbabilities_NoMonotonicityForcing()
        {
            // Dışlayıcı sınıflarda W >= GW >= BW zorunluluğu YOKTUR: bir oyuncu çoğu zaman
            // tek kazanırken mars da kazanabilir. GW > W olan bir vektör geçerli olmalı.
            OutcomeDistribution skewed = OutcomeDistribution.FromProbabilities(
                0.20f, 0.35f, 0.05f, 0.30f, 0.08f, 0.02f);

            Assert.That(skewed.IsValid, Is.True, "monotonluk zorlanmamalı");
            Assert.That(skewed.WinGammonOnly, Is.EqualTo(0.35f).Within(1e-6f),
                "GW değeri kırpılmamalı");

            // Geçersiz girdiler IsValid = false döndürmeli (istisna değil).
            Assert.That(OutcomeDistribution.FromProbabilities(
                -0.1f, 0.2f, 0.1f, 0.4f, 0.1f, 0.1f).IsValid, Is.False, "negatif bileşen");
            Assert.That(OutcomeDistribution.FromProbabilities(
                float.NaN, 0.2f, 0.1f, 0.4f, 0.1f, 0.1f).IsValid, Is.False, "NaN");
            Assert.That(OutcomeDistribution.FromProbabilities(
                float.PositiveInfinity, 0f, 0f, 0f, 0f, 0f).IsValid, Is.False, "sonsuz");
            Assert.That(OutcomeDistribution.FromProbabilities(
                0f, 0f, 0f, 0f, 0f, 0f).IsValid, Is.False, "toplam 0");

            // Geçersiz örnekte Equity 0 ve alanlar 0 olmalı (çağıran yedek yola düşebilsin).
            OutcomeDistribution invalid = OutcomeDistribution.FromProbabilities(
                0f, 0f, 0f, 0f, 0f, 0f);
            Assert.That(invalid.Equity, Is.EqualTo(0.0).Within(Tolerance));
            Assert.That(invalid.Win, Is.EqualTo(0f));
        }

        // ------------------------------------------------------------------
        // Ek: dönüşüm değişmezleri
        // ------------------------------------------------------------------

        [Test]
        public void OutcomeDistribution_FromProbabilities_CumulativeInvariants()
        {
            var rng = new Random(20261114);
            for (int trial = 0; trial < 200; trial++)
            {
                float[] p = new float[6];
                float sum = 0f;
                for (int i = 0; i < 6; i++)
                {
                    p[i] = (float)rng.NextDouble();
                    sum += p[i];
                }

                if (sum <= 0f)
                {
                    continue;
                }

                OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                    p[0], p[1], p[2], p[3], p[4], p[5]);

                Assert.That(d.IsValid, Is.True, "rastgele dağılım geçerli olmalı (trial " + trial + ")");
                Assert.That(d.WinBackgammon, Is.LessThanOrEqualTo(d.WinGammon + 1e-6f));
                Assert.That(d.WinGammon, Is.LessThanOrEqualTo(d.Win + 1e-6f));
                Assert.That(d.LoseBackgammon, Is.LessThanOrEqualTo(d.LoseGammon + 1e-6f));
                Assert.That(d.LoseGammon, Is.LessThanOrEqualTo(d.Lose + 1e-6f));
                Assert.That(d.Equity, Is.InRange(-3.0, 3.0));
            }
        }
    }
}