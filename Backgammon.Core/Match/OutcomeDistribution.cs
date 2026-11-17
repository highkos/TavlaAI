using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.3: koşulsuz (unconditional) oyun sonucu olasılıkları. gnubg çıktı düzeniyle aynı:
    /// mars/backgammon olasılıkları <b>kümülatiftir</b> (P(kazanır <b>ve</b> mars)).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Faz 6 §5.1/§5.5:</b> ağ çıktısı <b>dışlayıcı</b> 6 sınıftır
    /// (<c>W, GW, BW, L, GL, BL</c>, toplam 1). <see cref="FromProbabilities"/> bu dışlayıcı
    /// vektörü sınıfın <b>kümülatif</b> kodlamasına dönüştürür. Dönüşüm:
    /// <c>Win = W+GW+BW</c>, <c>WinGammon = GW+BW</c>, <c>WinBackgammon = BW</c>,
    /// <c>LoseGammon = GL+BL</c>, <c>LoseBackgammon = BL</c>.
    /// </para>
    /// <para>
    /// <b>Equity tek doğruluk kaynağıdır</b> (<see cref="Equity"/>). Kümülatif biçimde
    /// <c>Win + WinGammon + WinBackgammon − Lose − LoseGammon − LoseBackgammon</c> yazılan bu
    /// ifade, dışlayıcı biçimde <c>W + 2·GW + 3·BW − (L + 2·GL + 3·BL)</c> ile
    /// <b>matematiksel olarak aynıdır</b> (Faz 6 Test 49/53).
    /// </para>
    /// </remarks>
    public readonly struct OutcomeDistribution
    {
        /// <summary>Dışlayıcı sınıf sayısı (Faz 6 §5.1).</summary>
        public const int ProbabilityCount = 6;

        /// <summary>P(kazanır).</summary>
        public readonly float Win;

        /// <summary>P(kazanır ve mars).</summary>
        public readonly float WinGammon;

        /// <summary>P(kazanır ve backgammon).</summary>
        public readonly float WinBackgammon;

        /// <summary>P(kaybeder ve mars).</summary>
        public readonly float LoseGammon;

        /// <summary>P(kaybeder ve backgammon).</summary>
        public readonly float LoseBackgammon;

        /// <summary>
        /// <see cref="FromProbabilities"/> geçersiz girdi gördüyse <c>false</c>. Doğrudan kurulan
        /// örneklerde daima <c>true</c>'dur (Faz 6 §5.5).
        /// </summary>
        private readonly bool _constructed;

        public OutcomeDistribution(float win, float winGammon, float winBackgammon,
                                   float loseGammon, float loseBackgammon)
            : this(win, winGammon, winBackgammon, loseGammon, loseBackgammon, true)
        {
        }

        private OutcomeDistribution(float win, float winGammon, float winBackgammon,
                                    float loseGammon, float loseBackgammon, bool constructed)
        {
            Win = win;
            WinGammon = winGammon;
            WinBackgammon = winBackgammon;
            LoseGammon = loseGammon;
            LoseBackgammon = loseBackgammon;
            _constructed = constructed;
        }

        /// <summary>
        /// Faz 6 §5.5: ağ çıktısından (6 float, gnubg sırası: <c>W, GW, BW, L, GL, BL</c>,
        /// <b>dışlayıcı</b>) kurulum.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Toplam 1 değilse <b>normalize eder</b>. <b>Monotonluk zorlamaz</b>: dışlayıcı sınıflar
        /// arasında <c>W ≥ GW ≥ BW</c> gibi bir zorunlu sıralama yoktur (bir oyuncu çoğu zaman tek
        /// kazanırken mars da kazanabilir). Kümülatif değişmezler dönüşümden <b>kendiliğinden</b>
        /// sağlanır.
        /// </para>
        /// <para>
        /// Geçersiz girdi (negatif, NaN, sonsuz veya toplam 0) → <see cref="IsValid"/> <c>false</c>
        /// döner. Çağıran (arama/değerlendirici) bunu kontrol edip yedek yola düşmelidir.
        /// </para>
        /// </remarks>
        public static OutcomeDistribution FromProbabilities(
            float w, float gw, float bw, float l, float gl, float bl)
        {
            if (!IsFinite(w) || !IsFinite(gw) || !IsFinite(bw)
                || !IsFinite(l) || !IsFinite(gl) || !IsFinite(bl))
            {
                return Invalid;
            }

            if (w < 0f || gw < 0f || bw < 0f || l < 0f || gl < 0f || bl < 0f)
            {
                return Invalid;
            }

            double sum = (double)w + gw + bw + l + gl + bl;
            if (sum <= 0.0)
            {
                return Invalid;
            }

            double inv = 1.0 / sum;
            float nw = (float)(w * inv);
            float ngw = (float)(gw * inv);
            float nbw = (float)(bw * inv);
            float ngl = (float)(gl * inv);
            float nbl = (float)(bl * inv);

            // Kümülatif dönüşüm. Kırpma yalnızca float yuvarlama hijyenidir (ör. 0.1+0.2+0.7
            // float'ta 1'den 1 ulp sapabilir); dışlayıcı değerler DEĞİŞTİRİLMEZ.
            float win = Clamp01(nw + ngw + nbw);
            float winGammon = Clamp(ngw + nbw, 0f, win);
            float winBackgammon = Clamp(nbw, 0f, winGammon);
            float lose = 1f - win;
            float loseGammon = Clamp(ngl + nbl, 0f, lose);
            float loseBackgammon = Clamp(nbl, 0f, loseGammon);

            return new OutcomeDistribution(win, winGammon, winBackgammon,
                                           loseGammon, loseBackgammon, true);
        }

        /// <summary>Geçersiz dağılım (<see cref="IsValid"/> <c>false</c>).</summary>
        public static OutcomeDistribution Invalid
        {
            get { return new OutcomeDistribution(0f, 0f, 0f, 0f, 0f, false); }
        }

        /// <summary>P(kazanır, tek) = <c>Win − WinGammon</c> (dışlayıcı).</summary>
        public float WinSingle
        {
            get { return Win - WinGammon; }
        }

        /// <summary>P(kazanır, mars) = <c>WinGammon − WinBackgammon</c> (dışlayıcı).</summary>
        public float WinGammonOnly
        {
            get { return WinGammon - WinBackgammon; }
        }

        /// <summary>P(kazanır, backgammon) = <c>WinBackgammon</c> (dışlayıcı).</summary>
        public float WinBackgammonOnly
        {
            get { return WinBackgammon; }
        }

        /// <summary>P(kaybeder, tek) = <c>Lose − LoseGammon</c> (dışlayıcı).</summary>
        public float LoseSingle
        {
            get { return Lose - LoseGammon; }
        }

        /// <summary>P(kaybeder, mars) = <c>LoseGammon − LoseBackgammon</c> (dışlayıcı).</summary>
        public float LoseGammonOnly
        {
            get { return LoseGammon - LoseBackgammon; }
        }

        /// <summary>P(kaybeder, backgammon) = <c>LoseBackgammon</c> (dışlayıcı).</summary>
        public float LoseBackgammonOnly
        {
            get { return LoseBackgammon; }
        }

        /// <summary>P(kaybeder) = 1 − P(kazanır).</summary>
        public float Lose
        {
            get { return 1f - Win; }
        }

        /// <summary>
        /// Faz 6 §10.2: perspektifi ters çevirir — <c>W↔L</c>, <c>GW↔GL</c>, <c>BW↔BL</c>.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Rakibin dağılımından bizim dağılımımızı üretir. <see cref="Equity"/> işaret değiştirir
        /// (<c>flip(d).Equity ≈ -d.Equity</c>) ve <c>flip(flip(d)) ≈ d</c> (bir involüsyon).
        /// Geçersiz dağılım geçersiz kalır.
        /// </para>
        /// <para>
        /// <b>F7-05:</b> eşitlikler <b>bit düzeyinde değil</b>, float32 yuvarlaması
        /// mertebesindedir. Sebep: <see cref="FromProbabilities"/> dışlayıcı sınıfları
        /// yeniden normalize eder (<c>inv = 1/sum</c>) ve <c>sum</c> float32'de tam 1
        /// olmayabilir; her çarpım bir ulp yuvarlama ekler. Ölçülen üst sınır
        /// <c>1,4e-7</c> (300 kayıtlık <c>equity_golden.json</c>), yani backgammon
        /// equity çözünürlüğünün (<c>1e-4</c>) çok altında. Testler bu yüzden
        /// <c>1e-6</c> tolerans kullanır (<c>EquityGoldenTests.EquityFlip_IsInvolution</c>,
        /// <c>ml/tests/test_equity_parity.py</c>).
        /// </para>
        /// <para>
        /// <b>Neden <see cref="FromProbabilities"/>:</b> <c>Lose</c> türetilmiş bir alandır
        /// (<c>1 − Win</c>); doğrudan alan kopyalamak float yuvarlamasında
        /// <c>LoseGammon &gt; Lose</c> gibi 1-ulp ihlalleri üretebilir. Dışlayıcı sınıflar
        /// üzerinden yeniden kurmak kırpmayı ve normalizasyonu garanti eder.
        /// </para>
        /// </remarks>
        public OutcomeDistribution Flip()
        {
            if (!_constructed)
            {
                return Invalid;
            }

            return FromProbabilities(
                LoseSingle, LoseGammonOnly, LoseBackgammonOnly,
                WinSingle, WinGammonOnly, WinBackgammonOnly);
        }

        /// <summary>
        /// Küpsüz para equity'si: <c>W + WG + WBG − L − LG − LBG</c> (kümülatif).
        /// Dışlayıcı biçimde <c>W + 2·GW + 3·BW − (L + 2·GL + 3·BL)</c> ile aynıdır; aralık
        /// <c>[−3, +3]</c>. <b>Tek doğruluk kaynağıdır</b> — Faz 6 bu özelliği yeniden yazmaz.
        /// </summary>
        /// <remarks>
        /// Geçersiz dağılımda (<see cref="IsValid"/> <c>false</c>) <b>0</b> döner: çağıran
        /// <see cref="IsValid"/>'i kontrol etmese bile nötr bir değer görür (yanıltıcı −1 değil).
        /// </remarks>
        public double Equity
        {
            get
            {
                if (!_constructed)
                {
                    return 0.0;
                }

                return (double)Win + WinGammon + WinBackgammon
                     - Lose - LoseGammon - LoseBackgammon;
            }
        }

        /// <summary>§4.3 değişmezleri sağlanıyor mu?</summary>
        public bool IsValid
        {
            get
            {
                if (!_constructed)
                {
                    return false;
                }

                if (!IsFinite(Win) || !IsFinite(WinGammon) || !IsFinite(WinBackgammon)
                    || !IsFinite(LoseGammon) || !IsFinite(LoseBackgammon))
                {
                    return false;
                }

                if (Win < 0f || Win > 1f)
                {
                    return false;
                }

                if (WinBackgammon < 0f || WinBackgammon > WinGammon || WinGammon > Win)
                {
                    return false;
                }

                float lose = Lose;
                if (LoseBackgammon < 0f || LoseBackgammon > LoseGammon || LoseGammon > lose)
                {
                    return false;
                }

                double equity = Equity;
                return equity >= -3.0 && equity <= 3.0;
            }
        }

        private static bool IsFinite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }

        private static float Clamp01(float value)
        {
            return Clamp(value, 0f, 1f);
        }

        private static float Clamp(float value, float min, float max)
        {
            if (value < min)
            {
                return min;
            }

            return value > max ? max : value;
        }

        public override string ToString()
        {
            return "W=" + Win.ToString("F4") + " WG=" + WinGammon.ToString("F4") +
                   " WBG=" + WinBackgammon.ToString("F4") + " LG=" + LoseGammon.ToString("F4") +
                   " LBG=" + LoseBackgammon.ToString("F4");
        }
    }

    /// <summary>
    /// Faz 5 §4.3: 6'lı sonuç dağılımı üreten değerlendirici.
    /// Faz 5'te yalnızca tanım + sezgisel uygulama; ağ tabanlı uygulama Faz 6.
    /// </summary>
    public interface IOutcomeDistributionEvaluator
    {
        void EvaluateDistributionBatch(AfterStateList list, int offset, int count, int perspective,
                                       in VectorizerScalars scalars, Span<OutcomeDistribution> results);

        int Version { get; }
    }
}
