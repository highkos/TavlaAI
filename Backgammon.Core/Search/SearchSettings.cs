namespace Backgammon.Core
{
    /// <summary>
    /// Faz 3 v7 Bölüm 4.2: arama ayarları.
    /// </summary>
    /// <remarks>
    /// <see cref="Default"/> değerleri <b>YER TUTUCUDUR, GÜÇ AYARI DEĞİLDİR</b> (Bölüm 10).
    /// Gerçek seçim, ağ hazır olduktan sonra Faz 4'te sabit seed'li kıyaslamalarla yapılacaktır.
    /// </remarks>
    public struct SearchSettings
    {
        /// <summary>
        /// Faz 7 §5.2 / F7-09: <b>üretimde</b> kullanılabilir en yüksek arama derinliği.
        /// </summary>
        /// <remarks>
        /// Gerçek ONNX modeliyle depth 2 p95 <b>4,50 s</b> (medium) / <b>13,68 s</b> (large)
        /// ölçüldü; bütçe 2 s. Maliyet ONNX <b>çağrı sayısıyla</b> doğrusaldır (depth 2 =
        /// 84×84 = 7 056 yaprak şans düğümü). Depth 1 p95 0,09 s'dir (bütçenin %4,5'i).
        /// Depth 2 yalnızca <b>çevrimdışı</b> (damıtma öğretmeni) kullanılabilir.
        /// </remarks>
        public const int ProductionDepthPly = 1;

        /// <summary>Chance (zar) katmanı sayısı. 0..<see cref="SearchWorkspace.MaxSupportedPly"/>.</summary>
        public int DepthPly;

        /// <summary>
        /// Bu ayarlar üretimde kullanılabilir mi (F7-09)?
        /// </summary>
        /// <remarks>
        /// <c>DepthPly &lt;= <see cref="ProductionDepthPly"/></c> olmalıdır. Daha derin arama
        /// yalnızca çevrimdışı damıtma hedefi üretiminde meşrudur ve üretim yollarından
        /// (<c>Backgammon.UI</c>, <c>Backgammon.SelfPlay</c>) çağrılmamalıdır.
        /// </remarks>
        public bool IsProductionViable
        {
            get { return DepthPly >= 0 && DepthPly <= ProductionDepthPly; }
        }

        /// <summary>
        /// Üretim dışı derinlikte <see cref="System.ArgumentOutOfRangeException"/> atar.
        /// </summary>
        /// <param name="what">Hata iletisinde görünecek çağrı adı.</param>
        public void EnsureProductionViable(string what)
        {
            if (!IsProductionViable)
            {
                throw new System.ArgumentOutOfRangeException(
                    nameof(DepthPly),
                    DepthPly,
                    (what ?? "arama") + ": üretimde en fazla depth " + ProductionDepthPly +
                    " kullanılabilir (F7-09: depth 2 p95 4,50 s > 2 s bütçesi).");
            }
        }

        /// <summary>0 = kısıtsız; aksi halde kökte politika sırasına göre ilk K aday derin aranır.</summary>
        public int MaxCandidatesRoot;

        /// <summary>0 = kısıtsız; aksi halde iç düğümlerde politika sırasına göre ilk K aday.</summary>
        public int MaxCandidatesInner;

        /// <summary>Alfa-beta budaması. Referans testi için kapatılabilir.</summary>
        public bool UseAlphaBeta;

        /// <summary>Star1 (chance düğümü budaması).</summary>
        public bool UseStar1;

        /// <summary>Değerlendirme önbelleği (transposition / eval cache).</summary>
        public bool UseEvalCache;

        /// <summary>false ise statik değer sıralamasına düşülür.</summary>
        public bool UsePolicyOrdering;

        /// <summary>true: kökte tüm adaylar tam pencereyle aranır (eğitimde ZORUNLU).</summary>
        public bool ExactRootScores;

        /// <summary>Kök politika hedefi için softmax sıcaklığı. <c>&lt;= 0</c> → <c>ArgumentException</c>.</summary>
        public float PolicyTemperature;

        /// <summary>
        /// Faz 6 §9.2: transposition table kapasitesi (girdi sayısı). <b>0 = kapalı</b> — Faz 5
        /// davranışı birebir korunur (Test 75).
        /// </summary>
        /// <remarks>
        /// Yalnızca <b>kesin</b> (tam pencerede hesaplanmış) değerler saklanır ve yalnızca kesin
        /// isabetler kullanılır; bu yüzden TT sonucu <b>değiştirmez</b> (Test 78).
        /// </remarks>
        public int TranspositionCapacity;

        /// <summary>
        /// Faz 6 §9.2: saf bearoff bölgesinde aramayı kes (kesin DB varsa). Varsayılan <c>false</c>.
        /// </summary>
        /// <remarks>
        /// Yalnızca değerlendirici <see cref="IExactValueEvaluator"/> uyguluyorsa ve pozisyon için
        /// <b>kesin</b> değer verebiliyorsa etkilidir. Saf yarışta kesin değer, her derinlikteki
        /// arama sonucuna eşit olduğu için sonuç değişmez (Test 77, Test 78).
        /// </remarks>
        public bool UseBearoffCutoff;

        /// <summary>
        /// Faz 7 §5.4 / Test 99: arama damıtma modu. Varsayılan <c>false</c>.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <c>true</c> iken <see cref="SearchResult.RootValue"/> doldurulur: seçilen en iyi
        /// afterstate'in <b>6 çıktılı sonuç dağılımı</b>. Bu, damıtmanın <b>değer hedefidir</b>;
        /// <see cref="SearchResult.BestSequence"/> ise <b>politika hedefidir</b>.
        /// </para>
        /// <para>
        /// <b>Maliyet:</b> bir ek değerlendirici çağrısı (yalnızca kökte, yalnızca bir kayıt).
        /// Bu yüzden varsayılan <c>false</c>'tur ve üretim yollarında açılmaz.
        /// </para>
        /// <para>
        /// Değerlendirici <see cref="IOutcomeDistributionEvaluator"/> uygulamıyorsa
        /// <see cref="SearchResult.RootValue"/> <c>null</c> kalır; arama <b>hata vermez</b>
        /// (damıtma hedefi üretilemez, bu çağıranın sorunudur).
        /// </para>
        /// <para>
        /// <b>v1 model:</b> <c>output_version &lt; 2</c> model dağılım üretemediği için
        /// <see cref="System.NotSupportedException"/> atar. Bu bilinçlidir — damıtma sessizce
        /// değer hedefsiz bırakılmaz.
        /// </para>
        /// </remarks>
        public bool DistillMode;

        /// <summary>Yer tutucu varsayılanlar (Bölüm 10).</summary>
        public static SearchSettings Default
        {
            get
            {
                return new SearchSettings
                {
                    DepthPly = 1,
                    MaxCandidatesRoot = 0,
                    MaxCandidatesInner = 0,
                    UseAlphaBeta = true,
                    UseStar1 = true,
                    UseEvalCache = true,
                    UsePolicyOrdering = true,
                    ExactRootScores = false,
                    PolicyTemperature = 1.0f,
                    TranspositionCapacity = 0,
                    UseBearoffCutoff = false,
                    DistillMode = false
                };
            }
        }

        /// <summary>Budamasız, cache'siz, politika sıralamasız referans ayarları.</summary>
        public static SearchSettings Reference(int depthPly)
        {
            return new SearchSettings
            {
                DepthPly = depthPly,
                MaxCandidatesRoot = 0,
                MaxCandidatesInner = 0,
                UseAlphaBeta = false,
                UseStar1 = false,
                UseEvalCache = false,
                UsePolicyOrdering = false,
                ExactRootScores = true,
                PolicyTemperature = 1.0f,
                TranspositionCapacity = 0,
                UseBearoffCutoff = false,
                DistillMode = false
            };
        }
    }
}