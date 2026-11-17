using System;

namespace Backgammon.Core
{
    /// <summary>Faz 5 §4.4: <see cref="EquityCubeAdvisor"/> yapılandırması.</summary>
    public sealed class CubeAdvisorOptions
    {
        /// <summary>Post-Crawford'da serbest düşüş geçerli mi? (varsayılan <c>true</c>)</summary>
        public bool PostCrawfordFreeDrop = true;

        /// <summary>Çiftleme kararı için eşik payı.</summary>
        public double Epsilon = 1e-9;

        /// <summary>
        /// Faz 6 §10.2: pozisyon 21 zar çifti üzerinden ortalanarak değerlendirilir
        /// (varsayılan <c>true</c>). <c>false</c> → Faz 5 davranışı (tek kayıt).
        /// </summary>
        /// <remarks>
        /// Küp kararı <b>sıra başında</b> verilir; zar henüz atılmamıştır. Tahtayı tek kayıt gibi
        /// değerlendirmek, zar beklentisini yok sayar ve equity'yi sistematik olarak kaydırır
        /// (Faz 5 §9.2: korelasyon −0,0315 → +0,1395). Zar-ortalamalı değerlendirme bunu düzeltir.
        /// Maliyet: 21 zar × ~20 hamle ≈ ~400 değerlendirme; oyun başına ~27 küp kararı.
        /// </remarks>
        public bool DiceAveraged = true;

        /// <summary>Varsayılan yapılandırma.</summary>
        public static CubeAdvisorOptions Default
        {
            get { return new CubeAdvisorOptions(); }
        }
    }

    /// <summary>Faz 5 §4.4: küp kararı.</summary>
    public readonly struct CubeDecision
    {
        /// <summary>Çiftleme teklif edilmeli mi?</summary>
        public readonly bool ShouldDouble;

        /// <summary>Rakip kabul etmeli mi? (rakip perspektifinden)</summary>
        public readonly bool ShouldTake;

        /// <summary>Çiftlemezsen beklenen değer.</summary>
        public readonly double EquityNoDouble;

        /// <summary>Çiftle ve kabul edilirse beklenen değer.</summary>
        public readonly double EquityDoubleTake;

        /// <summary>Çiftle ve reddedilirse beklenen değer.</summary>
        public readonly double EquityDoublePass;

        /// <summary>Çiftlemek fazla iyi mi? (reddedilecek kadar)</summary>
        public readonly bool IsTooGood;

        /// <summary>Küp ölü mü?</summary>
        public readonly bool IsDeadCube;

        public CubeDecision(bool shouldDouble, bool shouldTake, double equityNoDouble,
                            double equityDoubleTake, double equityDoublePass, bool isTooGood, bool isDeadCube)
        {
            ShouldDouble = shouldDouble;
            ShouldTake = shouldTake;
            EquityNoDouble = equityNoDouble;
            EquityDoubleTake = equityDoubleTake;
            EquityDoublePass = equityDoublePass;
            IsTooGood = isTooGood;
            IsDeadCube = isDeadCube;
        }

        public override string ToString()
        {
            return (ShouldDouble ? "DOUBLE" : "no-double") + (ShouldTake ? "/take" : "/pass") +
                   " nd=" + EquityNoDouble.ToString("F4") + " dt=" + EquityDoubleTake.ToString("F4") +
                   " dp=" + EquityDoublePass.ToString("F4") + (IsTooGood ? " too-good" : string.Empty) +
                   (IsDeadCube ? " dead" : string.Empty);
        }
    }

    /// <summary>
    /// Faz 5 §4.4: MET + 6'lı dağılım üzerinden <b>kapalı biçimde</b> küp kararı veren danışman.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Küp kararı ağın <b>dışındadır</b>: hamle seçiminden farklı olarak, maç skoru ve mars
    /// ağırlıkları <c>argmax</c>'ı gerçekten değiştirir. Bu yüzden burada tam MET aritmetiği kullanılır.
    /// </para>
    /// <para>
    /// <b>Pozisyon değerlendirmesi (yaklaşım):</b> <see cref="BackgammonState"/> bir <b>pre-roll</b>
    /// pozisyondur; <see cref="IPositionEvaluator"/> ise afterstate değerlendirir. Danışman, mevcut
    /// tahtayı <b>tek kayıtlık</b> bir afterstate gibi değerlendirir (zar beklentisi alınmaz). Bu,
    /// §4.4 adım 4–5'in "tek kayıt" ifadesiyle uyumludur ve küp kararı için yeterli hassasiyettedir;
    /// tam zar-beklentili değerlendirme Faz 6'nın konusudur.
    /// </para>
    /// <para>
    /// <b>Kırpma:</b> danışman equity'yi <c>[−3, 3]</c>'e kırpar. Bu, F4-02'nin "değerlendirici
    /// kırpmaz" kuralını <b>ihlal etmez</b> — danışman bir değerlendirici değildir.
    /// </para>
    /// </remarks>
    public sealed class EquityCubeAdvisor : ICubeEvaluator
    {
        /// <summary>
        /// Money game çiftleme <b>ve</b> kabul noktası: <c>2E = 1</c> ⇒ <c>E = 0.5</c>.
        /// </summary>
        /// <remarks>
        /// Teklif eden <c>2E &gt; E</c> olduğu için <c>E &gt; 0.5</c>'te çiftler; rakip ise
        /// <c>−2E ≥ −1</c> ⇒ <c>E ≤ 0.5</c> olduğunda kabul eder. İki karar da <b>aynı</b>
        /// eşikten türetilir (§4.4 adım 8–9).
        /// </remarks>
        public const double MoneyDoublePoint = 0.5;

        /// <summary>Money game "çok iyi" noktası: <c>E &gt; 1</c> ⇒ çiftle ama rakip reddeder.</summary>
        public const double MoneyTooGoodPoint = 1.0;

        /// <summary>
        /// Faz 6 §10.2: 21 ayrık zar çiftinin birinci zarı. Dubleler bir kez, diğerleri bir kez
        /// listelenir; ağırlık <see cref="DiceWeight"/> ile verilir.
        /// </summary>
        private static readonly int[] DiceFirst =
        {
            1, 1, 1, 1, 1, 1,
            2, 2, 2, 2, 2,
            3, 3, 3, 3,
            4, 4, 4,
            5, 5,
            6,
        };

        /// <summary>Faz 6 §10.2: 21 ayrık zar çiftinin ikinci zarı.</summary>
        private static readonly int[] DiceSecond =
        {
            1, 2, 3, 4, 5, 6,
            2, 3, 4, 5, 6,
            3, 4, 5, 6,
            4, 5, 6,
            5, 6,
            6,
        };

        private readonly IPositionEvaluator _evaluator;
        private readonly MatchEquityTable _met;
        private readonly IOutcomeDistributionEvaluator _distribution;
        private readonly CubeAdvisorOptions _options;
        private readonly int _version;

        public EquityCubeAdvisor(IPositionEvaluator evaluator, MatchEquityTable met,
                                 IOutcomeDistributionEvaluator distribution, CubeAdvisorOptions options)
        {
            if (evaluator == null)
            {
                throw new ArgumentNullException(nameof(evaluator));
            }

            if (met == null)
            {
                throw new ArgumentNullException(nameof(met));
            }

            if (distribution == null)
            {
                throw new ArgumentNullException(nameof(distribution));
            }

            _evaluator = evaluator;
            _met = met;
            _distribution = distribution;
            _options = options ?? CubeAdvisorOptions.Default;

            unchecked
            {
                _version = (int)(((uint)evaluator.Version * 31u) + ((uint)met.Version * 17u) +
                                 ((uint)distribution.Version * 7u));
            }
        }

        /// <summary>Bileşen sürümlerinden türetilen sürüm.</summary>
        public int Version
        {
            get { return _version; }
        }

        public bool ShouldDouble(BackgammonState state)
        {
            return Decide(state, state == null ? 1 : state.turn).ShouldDouble;
        }

        public bool ShouldTake(BackgammonState state)
        {
            return Decide(state, state == null ? 1 : state.turn).ShouldTake;
        }

        /// <summary>Küp kararını hesaplar.</summary>
        public CubeDecision Decide(BackgammonState state, int perspective)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            if (perspective != 1 && perspective != -1)
            {
                throw new ArgumentOutOfRangeException(nameof(perspective));
            }

            MatchState match = MatchState.From(state);
            bool dead = match.IsDeadCube;

            // 1-3) Teklif edilebilirlik.
            if (state.phase != GamePhase.PreRoll || !BackgammonEngine.CanOffer(state))
            {
                return new CubeDecision(false, true, 0.0, 0.0, 0.0, false, dead);
            }

            if (match.IsCrawfordGame || dead)
            {
                return new CubeDecision(false, true, 0.0, 0.0, 0.0, false, dead);
            }

            // 4-5) Pozisyon ve dağılım.
            double equity = EvaluateEquity(state, perspective, out OutcomeDistribution dist);

            if (match.IsMoneyGame)
            {
                return DecideMoneyGame(equity, dead);
            }

            // 6-8) Maç: MET aritmetiği.
            int awayMover = match.AwayScore(perspective);
            int awayOpponent = match.AwayScore(-perspective);

            double noDouble = ScenarioValue(match, dist, awayMover, awayOpponent, 1);
            double doubleTake = ScenarioValue(match, dist, awayMover, awayOpponent, 2);
            double doublePass = PassValue(match, awayMover, awayOpponent);

            // Rakip kendi equity'sini maksimize eder, yani bizim equity'yi MINIMIZE eder:
            // kabul ederse `doubleTake`, reddederse `doublePass` gerceklesir. Bu yuzden
            // cifttikten sonraki equity `min(doubleTake, doublePass)`'tir (F6-30).
            // `max` kullanmak rakibin isbirligi yaptigini varsayar ve negatif equity'li
            // pozisyonlarda bile "ciftle" der (olculdu: 32 yanlis ciftlemenin 19'u).
            double doubleValue = Math.Min(doubleTake, doublePass);

            // "Cok iyi": rakip kabul eder ama oynamak cifttikten de iyidir.
            bool tooGood = doublePass > doubleTake && noDouble > doubleTake;
            bool shouldDouble = doubleValue > noDouble + _options.Epsilon;

            // Rakip perspektifinden kabul kararı.
            double opponentTake = -doubleTake;
            double opponentPass = -doublePass;
            if (match.IsPostCrawford && _options.PostCrawfordFreeDrop)
            {
                // Serbest düşüş: reddetmenin maç skoru maliyeti yok.
                opponentPass = 0.0;
            }

            bool shouldTake = opponentTake >= opponentPass - _options.Epsilon;

            return new CubeDecision(shouldDouble, shouldTake, noDouble, doubleTake, doublePass, tooGood, dead);
        }

        /// <summary>
        /// Money game küp kararı: klasik <b>canlı küp</b> eşikleri.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Ham aritmetik (<c>max(2E, 1) &gt; E</c>) her zaman "çiftle" der, çünkü <b>yeniden
        /// çiftleme (recube) hakkını</b> hesaba katmaz. §4.4 adım 9'un belirttiği klasik eşikler
        /// bu yüzden kullanılır.
        /// </para>
        /// <para>
        /// Eşikler tek bir yerden türetilir: <c>E_doubleTake = 2E</c> ve <c>E_doublePass = 1</c>.
        /// Teklif eden <c>max(2E, 1) &gt; E</c> olduğunda çiftler ⇒ <c>E &gt; 0.5</c>. Rakip
        /// <c>−2E ≥ −1</c> olduğunda kabul eder ⇒ <c>E ≤ 0.5</c>. <c>E &gt; 1</c> ise teklif eden
        /// için "çok iyi"dir (çiftle, rakip reddeder).
        /// </para>
        /// </remarks>
        private CubeDecision DecideMoneyGame(double equity, bool dead)
        {
            double noDouble = equity;
            double doubleTake = 2.0 * equity;
            double doublePass = 1.0;

            bool tooGood = equity > MoneyTooGoodPoint;
            bool shouldDouble = equity > MoneyDoublePoint + _options.Epsilon;
            bool shouldTake = equity < MoneyDoublePoint - _options.Epsilon;

            return new CubeDecision(shouldDouble, shouldTake, noDouble, doubleTake, doublePass, tooGood, dead);
        }

        /// <summary>Mevcut tahtayı değerlendirir ve 6'lı dağılımı üretir.</summary>
        /// <remarks>
        /// <see cref="CubeAdvisorOptions.DiceAveraged"/> açıksa 21 zar çifti üzerinden ortalama
        /// alınır (Faz 6 §10.2); kapalıysa Faz 5'in tek-kayıt davranışı birebir korunur.
        /// </remarks>
        private double EvaluateEquity(BackgammonState state, int perspective, out OutcomeDistribution dist)
        {
            if (!_options.DiceAveraged)
            {
                return EvaluateSingleRecord(state, perspective, out dist);
            }

            return EvaluateDiceAveraged(state, perspective, out dist);
        }

        /// <summary>Faz 5 davranışı: tahtayı tek kayıt gibi değerlendirir (zar beklentisi yok).</summary>
        private double EvaluateSingleRecord(BackgammonState state, int perspective, out OutcomeDistribution dist)
        {
            var list = new AfterStateList(1);
            list.Add(state, default);

            var scalars = VectorizerScalars.From(state);
            Span<float> values = stackalloc float[1];
            _evaluator.EvaluateBatch(list, 0, 1, perspective, scalars, values);

            double equity = values[0];
            if (double.IsNaN(equity) || double.IsInfinity(equity))
            {
                throw new InvalidOperationException("Değerlendirici sonlu olmayan equity döndürdü.");
            }

            if (equity > 3.0)
            {
                equity = 3.0;
            }
            else if (equity < -3.0)
            {
                equity = -3.0;
            }

            Span<OutcomeDistribution> buffer = stackalloc OutcomeDistribution[1];
            _distribution.EvaluateDistributionBatch(list, 0, 1, perspective, scalars, buffer);
            dist = buffer[0];

            if (!dist.IsValid)
            {
                throw new InvalidOperationException("Dağılım değerlendiricisi geçersiz dağılım döndürdü.");
            }

            return equity;
        }

        /// <summary>
        /// Faz 6 §10.2: 21 zar çifti üzerinden zar-ortalamalı değerlendirme.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Her zar çifti için yasal hamleler üretilir, hepsi değerlendirilir ve <b>equity'yi
        /// maksimize eden</b> hamle seçilir. Seçilen hamlenin equity'si ve 6'lı dağılımı zar
        /// olasılığıyla ağırlıklandırılarak toplanır (duble 1/36, diğerleri 2/36).
        /// </para>
        /// <para>
        /// <b>Dağılım kümülatiftir</b> (<see cref="OutcomeDistribution"/> gnubg düzeni); ağırlıklı
        /// toplamlar kümülatif olarak biriktirilir ve <see cref="OutcomeDistribution.FromProbabilities"/>
        /// dışlayıcı vektörü beklediği için sonda dönüştürülür.
        /// </para>
        /// <para>
        /// <b>Terminal afterstate</b> (oyun bitti): equity <c>ResultPoints / cubeValue</c>, dağılım
        /// tek-sınıf (W/GW/BW). Değerlendirici çağrısı yine yapılır ama sonucu kullanılmaz.
        /// </para>
        /// <para>
        /// <b>Pas</b> (yasal hamle yok): pozisyon değişmez, sıra rakibe geçer. Değerlendirici sıra
        /// bilgisini görmediği için pas afterstate'i tahtanın kendi değerini verir — Faz 5'in
        /// tek-kayıt yaklaşımıyla aynı sınırdadır.
        /// </para>
        /// </remarks>
        private double EvaluateDiceAveraged(BackgammonState state, int perspective, out OutcomeDistribution dist)
        {
            const int Capacity = 2048;

            BackgammonState scratch = state.Clone();
            var list = new AfterStateList(Capacity);
            var scalars = VectorizerScalars.From(state);
            EngineSettings es = EngineSettings.Default;

            var values = new float[Capacity];
            var dists = new OutcomeDistribution[Capacity];

            double equitySum = 0.0;
            double cumWin = 0.0;
            double cumWinGammon = 0.0;
            double cumWinBackgammon = 0.0;
            double cumLoseGammon = 0.0;
            double cumLoseBackgammon = 0.0;
            int weightSum = 0;

            for (int c = 0; c < DiceFirst.Length; c++)
            {
                int d1 = DiceFirst[c];
                int d2 = DiceSecond[c];
                int weight = d1 == d2 ? 1 : 2;

                scratch.CopyFrom(state);
                BackgammonEngine.SetDice(scratch, d1, d2);
                LegalMoveGenerator.GenerateAfterStates(scratch, es, list);

                if (list.Count == 0)
                {
                    list.AddPass(scratch);
                }

                int n = list.Count;

                // Terminal kayıtlar değerlendiriciye VERİLEMEZ (vektörleştirilemez). Bu yüzden
                // listeyi yerinde bölümleriz: [0, m) terminal olmayan, [m, n) terminal.
                int m = n;
                for (int i = 0; i < m;)
                {
                    if (list.IsTerminal[i])
                    {
                        m--;
                        if (i != m)
                        {
                            list.Swap(i, m);
                        }
                    }
                    else
                    {
                        i++;
                    }
                }

                if (m > 0)
                {
                    // Faz 6 Asama F (F6-29): model, afterstate'i **hamleyi yapan** oyuncunun
                    // perspektifinden degerlendirir. Kanit: ShardWriter her karar icin
                    // `VectorizeAfterMove(..., mover, ...)` yazar ve `ml/gnubg_er.py`
                    // `score_afterstates` afterstate'leri `perspective=turn` (mover) ile
                    // vektorlestirir; ER 0,06 bu yonde olculur. Bu yuzden afterstate'ler
                    // `perspective` ile degerlendirilir ve isaret CEVRILMEZ.
                    _evaluator.EvaluateBatch(list, 0, m, perspective, scalars, values.AsSpan(0, m));
                    _distribution.EvaluateDistributionBatch(list, 0, m, perspective, scalars, dists.AsSpan(0, m));
                }

                int best = -1;
                double bestValue = double.NegativeInfinity;
                for (int i = 0; i < m; i++)
                {
                    double v = values[i];
                    if (double.IsNaN(v) || double.IsInfinity(v))
                    {
                        throw new InvalidOperationException("Değerlendirici sonlu olmayan equity döndürdü.");
                    }

                    if (v > bestValue)
                    {
                        bestValue = v;
                        best = i;
                    }
                }

                for (int i = m; i < n; i++)
                {
                    double v = list.ResultPoints[i] / (double)scratch.cubeValue;
                    if (v > bestValue)
                    {
                        bestValue = v;
                        best = i;
                    }
                }

                if (best < 0)
                {
                    throw new InvalidOperationException("Zar çifti için hiç afterstate üretilemedi.");
                }

                equitySum += weight * bestValue;
                weightSum += weight;

                if (best >= m)
                {
                    // Terminal: sıra sahibi tüm taşlarını topladı ⇒ kazandı. ResultType 1/2/3.
                    int resultType = list.ResultType[best];
                    if (resultType == 1)
                    {
                        cumWin += weight;
                    }
                    else if (resultType == 2)
                    {
                        cumWinGammon += weight;
                    }
                    else
                    {
                        cumWinBackgammon += weight;
                    }
                }
                else
                {
                    OutcomeDistribution d = dists[best];
                    if (!d.IsValid)
                    {
                        throw new InvalidOperationException("Dağılım değerlendiricisi geçersiz dağılım döndürdü.");
                    }

                    cumWin += weight * d.Win;
                    cumWinGammon += weight * d.WinGammon;
                    cumWinBackgammon += weight * d.WinBackgammon;
                    cumLoseGammon += weight * d.LoseGammon;
                    cumLoseBackgammon += weight * d.LoseBackgammon;
                }
            }

            double inv = 1.0 / weightSum;

            double equity = equitySum * inv;
            if (equity > 3.0)
            {
                equity = 3.0;
            }
            else if (equity < -3.0)
            {
                equity = -3.0;
            }

            // Kümülatif → dışlayıcı. Kırpma yalnızca float yuvarlama hijyenidir.
            double w = Math.Max(0.0, (cumWin - cumWinGammon) * inv);
            double gw = Math.Max(0.0, (cumWinGammon - cumWinBackgammon) * inv);
            double bw = Math.Max(0.0, cumWinBackgammon * inv);
            double l = Math.Max(0.0, (weightSum - cumWin) * inv);
            double gl = Math.Max(0.0, (cumLoseGammon - cumLoseBackgammon) * inv);
            double bl = Math.Max(0.0, cumLoseBackgammon * inv);

            dist = OutcomeDistribution.FromProbabilities(
                (float)w, (float)gw, (float)bw, (float)l, (float)gl, (float)bl);

            if (!dist.IsValid)
            {
                throw new InvalidOperationException("Zar-ortalamalı dağılım geçersiz.");
            }

            return equity;
        }

        /// <summary>
        /// <paramref name="multiplier"/> ile ölçeklenmiş oyun sonucunun beklenen değeri.
        /// Money game'de equity, maçta MWC (sonra <c>2·MWC − 1</c>).
        /// </summary>
        private double ScenarioValue(MatchState match, OutcomeDistribution dist,
                                     int awayMover, int awayOpponent, int multiplier)
        {
            if (match.IsMoneyGame)
            {
                return dist.Equity * multiplier;
            }

            // Mars/backgammon olasılıkları KÜMÜLATİFTİR (gnubg düzeni): tek/çift/üç puanlık
            // sonuçların olasılıkları farklarla elde edilir, aksi hâlde çift sayım olur.
            double winSingle = dist.Win - dist.WinGammon;
            double winGammon = dist.WinGammon - dist.WinBackgammon;
            double winBackgammon = dist.WinBackgammon;

            double lose = dist.Lose;
            double loseSingle = lose - dist.LoseGammon;
            double loseGammon = dist.LoseGammon - dist.LoseBackgammon;
            double loseBackgammon = dist.LoseBackgammon;

            double mwc = 0.0;
            mwc += winSingle * WinChance(match, awayMover - multiplier, awayOpponent);
            mwc += winGammon * WinChance(match, awayMover - (2 * multiplier), awayOpponent);
            mwc += winBackgammon * WinChance(match, awayMover - (3 * multiplier), awayOpponent);
            mwc += loseSingle * WinChance(match, awayMover, awayOpponent - multiplier);
            mwc += loseGammon * WinChance(match, awayMover, awayOpponent - (2 * multiplier));
            mwc += loseBackgammon * WinChance(match, awayMover, awayOpponent - (3 * multiplier));

            return (2.0 * mwc) - 1.0;
        }

        /// <summary>Rakip reddederse teklif eden <c>cubeValue</c> puan kazanır.</summary>
        private double PassValue(MatchState match, int awayMover, int awayOpponent)
        {
            if (match.IsMoneyGame)
            {
                return 1.0;
            }

            return (2.0 * WinChance(match, awayMover - match.CubeValue, awayOpponent)) - 1.0;
        }

        private double WinChance(MatchState match, int awayMover, int awayOpponent)
        {
            if (awayMover <= 0)
            {
                return 1.0;
            }

            if (awayOpponent <= 0)
            {
                return 0.0;
            }

            if (awayMover > _met.MaxMatchLength || awayOpponent > _met.MaxMatchLength)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(awayMover),
                    "MET en fazla " + _met.MaxMatchLength + " puanlık maçı destekler.");
            }

            return _met.MatchWinningChance(awayMover, awayOpponent);
        }
    }
}
