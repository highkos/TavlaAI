using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 3 v7 Bölüm 6: aramanın tüm geçici verisini barındıran, <b>bir kez ayrılan</b> çalışma alanı.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Thread başına bir adet.</b> Thread'ler arasında paylaşılmaz. Isınma sonrası <c>Search</c>
    /// ve tüm özyinelemeli dalları <b>hiç allocation yapmaz</b>; tüm geçici veri burada yaşar.
    /// </para>
    /// <para>
    /// <b>Ply başına kopya:</b> her düğüm için ayrı <see cref="BackgammonState"/>,
    /// <see cref="AfterStateList"/>, skor/öncelik/sıra tamponları önceden ayrılır. 26 baytlık board
    /// kopyası ucuzdur ve undo'ya göre hata riski düşüktür.
    /// </para>
    /// <para>
    /// <b><see cref="Reset"/> sözleşmesi:</b> istatistikleri <b>ve cache'i kesinlikle</b> temizler.
    /// Model yeniden yükleme (<c>SetModel</c>, Faz 4) sonrası çağıran <b>zorunludur</b>
    /// <c>Reset()</c> çağırmaya. Aksi halde eski modelin <c>Q</c> değerleri yeni modelle karışır ve
    /// <b>sessiz hata</b> oluşur (Bölüm 3.5, 4.4; Test 17).
    /// </para>
    /// </remarks>
    public sealed class SearchWorkspace
    {
        /// <summary>Desteklenen en yüksek chance katmanı sayısı.</summary>
        public const int MaxSupportedPly = 4;

        /// <summary>Özyineleme için gereken düğüm sayısı: <c>2·MaxSupportedPly + 2</c>.</summary>
        public const int MaxNodes = 2 * MaxSupportedPly + 2;

        /// <summary>Varsayılan cache bit sayısı (2^20 giriş).</summary>
        public const int DefaultCacheBits = 20;

        private readonly BackgammonState[] _states;
        private readonly AfterStateList[] _lists;
        private readonly float[][] _staticScores;
        private readonly float[][] _policyScores;
        private readonly int[][] _candidateOrder;
        private readonly byte[][] _kinds;

        private readonly RootCandidate[] _rootCandidates;
        private readonly float[] _rootPolicyTarget;

        private readonly ulong[] _cacheKey;
        private readonly float[] _cacheValue;
        private readonly bool[] _cacheValid;
        private readonly int _cacheMask;

        // Faz 6 §9.3: transposition table. Tembel ayrılır (kapasite 0 = kapalı).
        private ulong[] _ttKey;
        private float[] _ttScore;
        private byte[] _ttDepth;
        private byte[] _ttFlag;
        private int _ttMask;
        private int _ttCapacity;

        private int _rootCandidateCount;
        private int _rootPolicyTargetCount;

        private int _lastEvaluatorVersion;
        private int _lastSettingsSignature;
        private bool _cachePrimed;

        public SearchWorkspace()
            : this(DefaultCacheBits)
        {
        }

        public SearchWorkspace(int cacheBits)
        {
            if (cacheBits < 1 || cacheBits > 26)
            {
                throw new ArgumentOutOfRangeException(nameof(cacheBits), "cacheBits 1..26 aralığında olmalı: " + cacheBits);
            }

            CacheBits = cacheBits;
            _cacheMask = (1 << cacheBits) - 1;

            _states = new BackgammonState[MaxNodes];
            _lists = new AfterStateList[MaxNodes];
            _staticScores = new float[MaxNodes][];
            _policyScores = new float[MaxNodes][];
            _candidateOrder = new int[MaxNodes][];
            _kinds = new byte[MaxNodes][];

            for (int i = 0; i < MaxNodes; i++)
            {
                _states[i] = new BackgammonState();
                _lists[i] = new AfterStateList();
                _staticScores[i] = new float[AfterStateList.DefaultCapacity];
                _policyScores[i] = new float[AfterStateList.DefaultCapacity];
                _candidateOrder[i] = new int[AfterStateList.DefaultCapacity];
                _kinds[i] = new byte[AfterStateList.DefaultCapacity];
            }

            _rootCandidates = new RootCandidate[AfterStateList.DefaultCapacity];
            _rootPolicyTarget = new float[AfterStateList.DefaultCapacity];

            _cacheKey = new ulong[1 << cacheBits];
            _cacheValue = new float[1 << cacheBits];
            _cacheValid = new bool[1 << cacheBits];

            Reset();
        }

        /// <summary>Cache bit sayısı (giriş sayısı <c>2^CacheBits</c>).</summary>
        public int CacheBits { get; }

        /// <summary>Cache giriş sayısı.</summary>
        public int CacheCapacity
        {
            get { return 1 << CacheBits; }
        }

        /// <summary>Kök adayları (yalnızca son aramanın geçerli kısmı).</summary>
        public ReadOnlySpan<RootCandidate> RootCandidates
        {
            get { return new ReadOnlySpan<RootCandidate>(_rootCandidates, 0, _rootCandidateCount); }
        }

        /// <summary>Kök politika hedefi (yalnızca son aramanın geçerli kısmı).</summary>
        public ReadOnlySpan<float> RootPolicyTarget
        {
            get { return new ReadOnlySpan<float>(_rootPolicyTarget, 0, _rootPolicyTargetCount); }
        }

        /// <summary>Son aramanın kök aday sayısı.</summary>
        public int RootCandidateCount
        {
            get { return _rootCandidateCount; }
        }

        /// <summary>Son aramanın kök politika hedefi uzunluğu.</summary>
        public int RootPolicyTargetCount
        {
            get { return _rootPolicyTargetCount; }
        }

        /// <summary>Cache'te geçerli giriş sayısı (tanı/benchmark amaçlı).</summary>
        public int CacheEntryCount
        {
            get
            {
                int n = 0;
                for (int i = 0; i < _cacheValid.Length; i++)
                {
                    if (_cacheValid[i])
                    {
                        n++;
                    }
                }

                return n;
            }
        }

        /// <summary>
        /// İstatistikleri <b>ve cache'i kesinlikle</b> temizler. Model yeniden yükleme sonrası
        /// çağıran zorunludur (Bölüm 3.5, 4.4).
        /// </summary>
        public void Reset()
        {
            _rootCandidateCount = 0;
            _rootPolicyTargetCount = 0;
            _cachePrimed = false;
            _lastEvaluatorVersion = 0;
            _lastSettingsSignature = 0;
            ClearCache();
            ClearTransposition();
        }

        /// <summary>Cache'i temizler; istatistikleri korur.</summary>
        public void ClearCache()
        {
            Array.Clear(_cacheValid, 0, _cacheValid.Length);
            Array.Clear(_cacheKey, 0, _cacheKey.Length);
            Array.Clear(_cacheValue, 0, _cacheValue.Length);
        }

        /// <summary>Faz 6 §9.3: transposition table'ı temizler (ayrılmışsa).</summary>
        public void ClearTransposition()
        {
            if (_ttCapacity == 0)
            {
                return;
            }

            Array.Clear(_ttKey, 0, _ttKey.Length);
            Array.Clear(_ttScore, 0, _ttScore.Length);
            Array.Clear(_ttFlag, 0, _ttFlag.Length);

            // Derinlik 0xFF = boş yuva (geçerli derinlik 0..MaxSupportedPly).
            for (int i = 0; i < _ttDepth.Length; i++)
            {
                _ttDepth[i] = TtEmptyDepth;
            }
        }

        // ------------------------------------------------------------------
        // Arama tarafından kullanılan iç erişimciler (Aşama B/C/D)
        // ------------------------------------------------------------------

        internal BackgammonState StateAt(int node)
        {
            return _states[node];
        }

        internal AfterStateList ListAt(int node)
        {
            return _lists[node];
        }

        internal float[] StaticScoresAt(int node)
        {
            return _staticScores[node];
        }

        internal float[] PolicyScoresAt(int node)
        {
            return _policyScores[node];
        }

        internal int[] CandidateOrderAt(int node)
        {
            return _candidateOrder[node];
        }

        internal byte[] KindsAt(int node)
        {
            return _kinds[node];
        }

        /// <summary>Son aramanın değerlendirici çalıştırma sayısı.</summary>
        internal long EvaluatorCalls;

        /// <summary>Son aramanın politika çalıştırma sayısı.</summary>
        internal long PolicyCalls;

        /// <summary>Son aramanın ziyaret ettiği düğüm sayısı.</summary>
        internal long NodesVisited;

        /// <summary>
        /// Yeni bir arama için istatistikleri ve kök tamponlarını sıfırlar; <b>cache'i korur</b>.
        /// <see cref="Reset"/>'ten farkı budur (Bölüm 3.5: cache yalnızca model/ayar değişiminde
        /// veya açık <see cref="Reset"/> ile temizlenir).
        /// </summary>
        internal void BeginSearch()
        {
            _rootCandidateCount = 0;
            _rootPolicyTargetCount = 0;
            EvaluatorCalls = 0;
            PolicyCalls = 0;
            NodesVisited = 0;
            TranspositionHits = 0;
            TranspositionStores = 0;
        }

        internal RootCandidate[] RootCandidateBuffer
        {
            get { return _rootCandidates; }
        }

        internal float[] RootPolicyTargetBuffer
        {
            get { return _rootPolicyTarget; }
        }

        internal void SetRootCounts(int candidateCount, int policyTargetCount)
        {
            _rootCandidateCount = candidateCount;
            _rootPolicyTargetCount = policyTargetCount;
        }

        /// <summary>
        /// Değerlendirici <c>Version</c>'ı veya değeri etkileyen ayarlar değiştiyse cache'i temizler.
        /// Politika <c>Version</c>'ı <b>asla</b> buraya girmez (Bölüm 3.5).
        /// </summary>
        internal void EnsureCacheConsistent(int evaluatorVersion, int settingsSignature)
        {
            if (!_cachePrimed)
            {
                _cachePrimed = true;
                _lastEvaluatorVersion = evaluatorVersion;
                _lastSettingsSignature = settingsSignature;
                return;
            }

            if (_lastEvaluatorVersion != evaluatorVersion || _lastSettingsSignature != settingsSignature)
            {
                _lastEvaluatorVersion = evaluatorVersion;
                _lastSettingsSignature = settingsSignature;
                ClearCache();
                ClearTransposition();
            }
        }

        internal bool TryGetCached(ulong key, out float value)
        {
            int slot = (int)(key & (ulong)_cacheMask);
            if (_cacheValid[slot] && _cacheKey[slot] == key)
            {
                value = _cacheValue[slot];
                return true;
            }

            value = 0f;
            return false;
        }

        internal void StoreCached(ulong key, float value)
        {
            int slot = (int)(key & (ulong)_cacheMask);
            _cacheKey[slot] = key;
            _cacheValue[slot] = value;
            _cacheValid[slot] = true;
        }

        // ------------------------------------------------------------------
        // Faz 6 §9.3: transposition table
        // ------------------------------------------------------------------

        /// <summary>TT bayrakları (Bölüm 9.3).</summary>
        internal const byte TtExact = 0;

        /// <summary>Alt sınır (bu fazda <b>yalnızca</b> biçim olarak saklanır, kesme için kullanılmaz).</summary>
        internal const byte TtLower = 1;

        /// <summary>Üst sınır (bu fazda <b>yalnızca</b> biçim olarak saklanır, kesme için kullanılmaz).</summary>
        internal const byte TtUpper = 2;

        /// <summary>Boş yuva işareti (geçerli derinlik 0..<see cref="MaxSupportedPly"/>).</summary>
        internal const byte TtEmptyDepth = 0xFF;

        /// <summary>Ayrılmış TT kapasitesi (0 = kapalı).</summary>
        public int TranspositionCapacity
        {
            get { return _ttCapacity; }
        }

        /// <summary>TT'de geçerli giriş sayısı (tanı/benchmark amaçlı).</summary>
        public int TranspositionEntryCount
        {
            get
            {
                if (_ttCapacity == 0)
                {
                    return 0;
                }

                int n = 0;
                for (int i = 0; i < _ttDepth.Length; i++)
                {
                    if (_ttDepth[i] != TtEmptyDepth)
                    {
                        n++;
                    }
                }

                return n;
            }
        }

        /// <summary>Son aramanın TT isabet sayısı.</summary>
        internal long TranspositionHits;

        /// <summary>Son aramanın TT yazma sayısı.</summary>
        internal long TranspositionStores;

        /// <summary>
        /// TT'yi istenen kapasiteye hazırlar. Kapasite değişmediyse <b>hiçbir şey yapmaz</b>
        /// (ısınma sonrası sıfır allocation, Test 80). Kapasite 0 ise TT kapalıdır.
        /// </summary>
        /// <returns>TT etkin mi?</returns>
        internal bool EnsureTransposition(int capacity)
        {
            if (capacity <= 0)
            {
                _ttCapacity = 0;
                return false;
            }

            if (_ttCapacity == capacity)
            {
                return true;
            }

            if (capacity > (1 << 26))
            {
                throw new ArgumentOutOfRangeException(nameof(capacity), "TranspositionCapacity en fazla 2^26 olabilir: " + capacity);
            }

            if ((capacity & (capacity - 1)) != 0)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity), "TranspositionCapacity 2'nin kuvveti olmalı: " + capacity);
            }

            _ttKey = new ulong[capacity];
            _ttScore = new float[capacity];
            _ttDepth = new byte[capacity];
            _ttFlag = new byte[capacity];
            _ttMask = capacity - 1;
            _ttCapacity = capacity;
            ClearTransposition();
            return true;
        }

        /// <summary>
        /// Kesin değer isabeti arar. Yalnızca <b>aynı anahtar</b>, <b>yeterli derinlik</b> ve
        /// <b>EXACT</b> bayrağı olan girişler döner; sınır girişleri bu fazda kullanılmaz.
        /// </summary>
        internal bool TryGetTransposition(ulong key, int depth, out float score)
        {
            if (_ttCapacity == 0)
            {
                score = 0f;
                return false;
            }

            int slot = (int)(key & (ulong)_ttMask);
            if (_ttDepth[slot] != TtEmptyDepth && _ttFlag[slot] == TtExact && _ttKey[slot] == key
                && _ttDepth[slot] >= depth)
            {
                score = _ttScore[slot];
                return true;
            }

            score = 0f;
            return false;
        }

        /// <summary>TT'ye giriş yazar (doğrudan eşleme; çakışmada üzerine yazılır).</summary>
        internal void StoreTransposition(ulong key, int depth, float score, byte flag)
        {
            if (_ttCapacity == 0)
            {
                return;
            }

            int slot = (int)(key & (ulong)_ttMask);
            _ttKey[slot] = key;
            _ttScore[slot] = score;
            _ttDepth[slot] = (byte)depth;
            _ttFlag[slot] = flag;
        }
    }
}