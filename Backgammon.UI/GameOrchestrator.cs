using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 5.3: oyun akisini, degerlendirici zincirini ve asenkron aramayi yoneten
    /// <b>Unity'siz</b> orkestrator.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Zincir (Bolum 2.1):</b> <c>MatchAwareEvaluator</c> (dis) -&gt; <c>BearoffAwareEvaluator</c>
    /// (ic) -&gt; <see cref="GameOrchestratorOptions.Evaluator"/>. Money game'de
    /// <c>MatchAwareEvaluator</c> zincire <b>girmez</b>; Faz 4 davranisi bit duzeyinde korunur.
    /// </para>
    /// <para>
    /// <b>Es zamanlilik:</b> ayni anda <b>tek</b> arama. Ikinci cagri
    /// <see cref="InvalidOperationException"/> atar (Bolum 5.4).
    /// </para>
    /// <para>
    /// <b>Iptal (durust sinir):</b> <see cref="BackgammonSearch"/> iptal kancasi <b>sunmaz</b> ve
    /// Bolum 0 kural 2 uyarinca degistirilemez. Bu yuzden iptal yalnizca arama <b>baslamadan once</b>
    /// etkilidir (<see cref="OperationCanceledException"/>); arama sirasinda gelen iptal, arama
    /// tamamlandiktan sonra <see cref="SearchOutcome.WasCancelled"/> ile <b>bildirilir</b> ve en iyi
    /// hamle yine dondurulur. Dusunme butcesi de ayni sekilde <b>tavsiye</b> niteligindedir.
    /// </para>
    /// </remarks>
    public sealed class GameOrchestrator : IDisposable
    {
        private readonly GameOrchestratorOptions _options;
        private readonly BackgammonState _state;
        private readonly BackgammonState _scratch;
        private readonly SearchWorkspace _workspace;
        private readonly SearchWorkspace _analysisWorkspace;
        private readonly MoveList _legalMoves;
        private readonly AfterStateList _afterStates;
        private readonly AfterStateList _nonTerminal;
        private readonly SemaphoreSlim _searchGate;
        private PositionAnalysis _lastAnalysis;
        private CubeDecision? _lastCubeDecision;
        private volatile bool _searchActive;
        private readonly List<PositionAnalysis> _candidates;
        private readonly float[] _equityBuffer;
        private readonly OutcomeDistribution[] _distributionBuffer;

        private IPositionEvaluator _positionEvaluator;
        private IPolicyEvaluator _policyEvaluator;
        private IPositionEvaluator _moneyEvaluator;
        private IOutcomeDistributionEvaluator _distribution;
        private EquityCubeAdvisor _cubeAdvisor;
        private int _chainKey;
        private bool _chainReady;

        private float[] _cdfBuffer;
        private GameResult _result;
        private bool _isGameOver;
        private bool _resultApplied;
        private bool _pendingOpponentTake;
        private bool _disposed;

        public GameOrchestrator(GameOrchestratorOptions options)
        {
            if (options == null)
            {
                throw new ArgumentNullException(nameof(options));
            }

            options.Validate();

            _options = options;
            _state = new BackgammonState();
            _scratch = new BackgammonState();
            _workspace = new SearchWorkspace();
            _analysisWorkspace = new SearchWorkspace(16);
            _legalMoves = new MoveList();
            _afterStates = new AfterStateList();
            _nonTerminal = new AfterStateList();
            _searchGate = new SemaphoreSlim(1, 1);
            _candidates = new List<PositionAnalysis>(64);
            _equityBuffer = new float[AfterStateList.DefaultCapacity];
            _distributionBuffer = new OutcomeDistribution[AfterStateList.DefaultCapacity];

            BackgammonEngine.NewGame(_state, MatchSettings.MoneyGame);
            Refresh();
        }

        /// <summary>
        /// Su anda bir arama calisiyor mu?
        /// </summary>
        /// <remarks>
        /// <b>Neden onemli:</b> <c>OrtIoBinding</c> is parcacigi guvenli <b>degildir</b>. Arama arka
        /// planda calisirken ana is parcacigindan degerlendirici cagirmak Unity/Mono altinda
        /// erisim ihlaline (0xC0000005) yol acar. Bu yuzden <see cref="AnalyzeCurrent"/>,
        /// <see cref="AnalyzeCandidates"/> ve <see cref="EvaluateCube"/> arama surerken
        /// <b>onbellekteki</b> sonucu doner.
        /// </remarks>
        public bool IsSearching
        {
            get { return _searchActive; }
        }

        /// <summary>Kurulum secenekleri (ayar paneli tarafindan guncellenebilir).</summary>
        public GameOrchestratorOptions Options
        {
            get { return _options; }
        }

        /// <summary>Oyun durumu (canli; dogrudan degistirilmemelidir).</summary>
        public BackgammonState State
        {
            get { return _state; }
        }

        /// <summary>Mac baglami.</summary>
        public MatchState Match
        {
            get { return MatchState.From(_state); }
        }

        /// <summary>Oyun bitti mi? (kup reddi dahil)</summary>
        public bool IsGameOver
        {
            get { return _isGameOver; }
        }

        /// <summary>Oyun sonucu; <see cref="IsGameOver"/> <c>false</c> ise gecersizdir.</summary>
        public GameResult Result
        {
            get { return _result; }
        }

        /// <summary>Gecerli yasal hamleler (yeniden uretilir; dogrudan degistirilmemelidir).</summary>
        public MoveList LegalMoves
        {
            get { return _legalMoves; }
        }

        /// <summary>
        /// Sirada oynanacak yasal hamle var mi?
        /// </summary>
        /// <remarks>
        /// <c>false</c> ise zar <b>bloke</b> demektir: kural geregi sira karsiya gecer
        /// (<see cref="BackgammonEngine.PassTurn"/>). Yalnizca <see cref="GamePhase.Moving"/>
        /// fazinda anlamlidir.
        /// </remarks>
        public bool HasLegalMoves
        {
            get { return _legalMoves.Count > 0; }
        }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary>Yeni mac baslatir.</summary>
        public void NewMatch(int matchLength, bool enableJacoby)
        {
            ThrowIfDisposed();
            _options.EngineSettings.EnableJacoby = enableJacoby;
            BackgammonEngine.NewGame(_state, new MatchSettings(matchLength));
            _isGameOver = false;
            _result = default(GameResult);
            _resultApplied = false;
            InvalidateChain();
            Refresh();
        }

        /// <summary>
        /// Ayni mac uzunlugunda yeni oyun kurar; <b>mac skoru korunur</b>.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <see cref="BackgammonEngine.NewGame"/> tahtayi <see cref="BackgammonState.Reset"/> ile
        /// sifirlar ve bu da skoru <c>0-0</c> yapar. Cok sayili bir macta "Yeni oyun" skoru
        /// silmemelidir; bu yuzden skoru koruyan <see cref="BackgammonEngine.PrepareNextGame"/>
        /// kullanilir (Bolum 4.9).
        /// </para>
        /// <para>
        /// Mac zaten bitmisse (skor hedefe ulastiysa) yeni bir mac baslatilir; aksi halde
        /// oyuncu "Yeni oyun" ile ilerleyemezdi.
        /// </para>
        /// </remarks>
        public void NewGame()
        {
            ThrowIfDisposed();

            if (_state.matchLength > 0 &&
                (_state.whiteScore >= _state.matchLength || _state.blackScore >= _state.matchLength))
            {
                NewMatch(_state.matchLength, _options.EngineSettings.EnableJacoby);
                return;
            }

            if (_isGameOver && !_resultApplied)
            {
                BackgammonEngine.ApplyResult(_state, _result);
                _resultApplied = true;
            }

            BackgammonEngine.PrepareNextGame(_state);
            _isGameOver = _state.phase == GamePhase.GameOver;
            _result = default(GameResult);
            _resultApplied = false;
            InvalidateChain();
            Refresh();
        }

        /// <summary>
        /// Zar atilabilir mi? (<see cref="BackgammonEngine.CanRoll"/>)
        /// </summary>
        /// <remarks>
        /// <c>false</c> ise "Zar" dugmesi etkisizdir: oyuncu <see cref="GamePhase.Moving"/> fazinda
        /// yeniden zar atarak kural disi yeni zar hakki elde edemez.
        /// </remarks>
        public bool CanRoll
        {
            get { return BackgammonEngine.CanRoll(_state); }
        }

        /// <summary>
        /// Disaridan gelen (ornegin sunucudan) bir pozisyonu yukler ve gorunumu tazeler.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Cevrimici modda otorite sunucudadir: sunucu anlik goruntusu bu metotla yerel
        /// duruma aktarilir, boylece yasal hamle uretimi, analiz ve giris denetleyicisi
        /// <b>ayni</b> motoru kullanmaya devam eder. Kural kodu ikinci kez yazilmaz.
        /// </para>
        /// <para>
        /// <paramref name="source"/> kopyalanir; cagiran taraf kendi nesnesini serbestce
        /// kullanmaya devam edebilir. Arama onbellegi gecersiz kilinir.
        /// </para>
        /// </remarks>
        public void LoadState(BackgammonState source)
        {
            ThrowIfDisposed();
            if (source == null)
            {
                throw new ArgumentNullException(nameof(source));
            }

            _state.CopyFrom(source);
            _isGameOver = _state.phase == GamePhase.GameOver;
            _result = default(GameResult);
            _resultApplied = false;
            _pendingOpponentTake = false;
            InvalidateChain();
            Refresh();
        }

        /// <summary>
        /// Zar atar (acilis fazinda <see cref="BackgammonEngine.RollOpening"/>).
        /// </summary>
        /// <remarks>
        /// Kural <see cref="BackgammonEngine.CanRoll"/> ile <b>motorda</b> tanimlidir; zar yalnizca
        /// sira basinda atilir. Oynanmamis zar varken tekrar atmak yok sayilir.
        /// </remarks>
        public void RollDice()
        {
            ThrowIfDisposed();
            if (!BackgammonEngine.CanRoll(_state))
            {
                return;
            }

            if (_state.phase == GamePhase.DetermineFirstPlayer)
            {
                BackgammonEngine.RollOpening(_state, _options.Random);
            }
            else
            {
                BackgammonEngine.RollDice(_state, _options.Random);
            }

            Refresh();
        }

        /// <summary>Zarlari RNG kullanmadan ayarlar (test/UI icin).</summary>
        /// <remarks>Zar yalnizca sira basinda ayarlanabilir (<see cref="BackgammonEngine.CanRoll"/>).</remarks>
        public void SetDice(int d1, int d2)
        {
            ThrowIfDisposed();
            if (!BackgammonEngine.CanRoll(_state))
            {
                return;
            }

            BackgammonEngine.SetDice(_state, d1, d2);
            Refresh();
        }

        /// <summary>
        /// Hamleyi uygular; kalan zarlar oynanamiyorsa turu kapatir.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Kural <see cref="BackgammonEngine.ShouldEndTurn"/> ile <b>motorda</b> tanimlidir: oyuncu
        /// zarlarin tamamini oynayamiyorsa oynayabildigi kadarini oynar ve sira kapanir.
        /// </para>
        /// <para>
        /// <b>Neden gerekli:</b> <see cref="LegalMoveGenerator"/> yalnizca <b>maksimum uzunluktaki</b>
        /// dizileri uretir. 5-5 atilip yalnizca iki hamle oynanabiliyorsa kalan iki zar icin yasal
        /// hamle yoktur; eski kod <c>remainingCount == 0</c> sartini aradigi icin sira hic
        /// kapanmiyor ve oyuncu kilitleniyordu. Ayni sekilde son tas zarlardan biri artarken
        /// toplandiginda oyun bitmiyordu.
        /// </para>
        /// </remarks>
        public void ApplyMove(in MoveSequence move)
        {
            ThrowIfDisposed();

            // Savunma katmani: bayat bayrakli bir adim (ornegin hedefte artik rakip tas yokken
            // "vurus" bayragi) tas silebilir. Gercek durumu bozmadan once derin kopya uzerinde
            // deneyip tas sayisinin korundugunu dogrulariz; korunmuyorsa hamle reddedilir.
            int whiteBefore = CountCheckers(_state, 1);
            int blackBefore = CountCheckers(_state, -1);
            BackgammonState probe = _state.Clone();
            BackgammonEngine.ApplyMove(probe, move);
            if (CountCheckers(probe, 1) != whiteBefore || CountCheckers(probe, -1) != blackBefore)
            {
                System.Diagnostics.Debug.Assert(false, "ApplyMove: tas sayisi korunmadi; hamle reddedildi.");
                return;
            }

            BackgammonEngine.ApplyMove(_state, move);

            if (_state.phase == GamePhase.Moving)
            {
                LegalMoveGenerator.GenerateAllLegalMoves(_state, _legalMoves);
                if (BackgammonEngine.ShouldEndTurn(_state, _legalMoves))
                {
                    BackgammonEngine.EndTurn(_state, _options.EngineSettings);
                }
            }

            Refresh();
        }

        /// <summary>Bir oyuncunun tahtadaki + toplanmis tas sayisi.</summary>
        private static int CountCheckers(BackgammonState s, int player)
        {
            int total = player > 0 ? s.whiteBorneOff : s.blackBorneOff;
            for (int p = 0; p < BackgammonState.BoardSize; p++)
            {
                int v = s.board[p];
                if (player > 0 ? v > 0 : v < 0)
                {
                    total += v > 0 ? v : -v;
                }
            }

            return total;
        }

        /// <summary>Turu kapatir.</summary>
        public void EndTurn()
        {
            ThrowIfDisposed();
            BackgammonEngine.EndTurn(_state, _options.EngineSettings);
            Refresh();
        }

        /// <summary>Kup teklif eder.</summary>
        public void OfferDouble()
        {
            ThrowIfDisposed();
            BackgammonEngine.OfferDouble(_state);
            Refresh();
        }

        /// <summary>
        /// Rakibin (yapay zekanin) bu teklife verecegi yanit; <see cref="TryOfferDouble"/> ile
        /// teklif edildikten sonra gecerlidir.
        /// </summary>
        /// <remarks>
        /// <see cref="EquityCubeAdvisor.Decide"/> yalnizca <see cref="GamePhase.PreRoll"/> fazinda
        /// gercek karar uretir. Teklif edildikten sonra faz <see cref="GamePhase.CubeOffered"/>
        /// oldugu icin yanit <b>tekliften once</b> hesaplanip saklanir.
        /// </remarks>
        public bool PendingOpponentTake
        {
            get { return _pendingOpponentTake; }
        }

        /// <summary>
        /// Kup teklif eder; gerekirse once atilmis ama oynanmamis zari geri alir.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Kural geregi kup zar atmadan once teklif edilir. Oyuncu zar attiktan sonra henuz tas
        /// oynamadiysa <see cref="BackgammonEngine.RevertRoll"/> ile zar geri alinir ve teklif
        /// kabul edilir; boylece "Kup" dugmesi sessizce hicbir sey yapmaz durumuna dusmez.
        /// </para>
        /// <para>
        /// Teklif edilemiyorsa hicbir sey degismez ve <c>false</c> doner.
        /// </para>
        /// </remarks>
        public bool TryOfferDouble()
        {
            ThrowIfDisposed();

            if (!BackgammonEngine.CanOffer(_state, _options.EngineSettings))
            {
                if (!BackgammonEngine.RevertRoll(_state, _options.EngineSettings))
                {
                    return false;
                }
            }

            if (!BackgammonEngine.CanOffer(_state, _options.EngineSettings))
            {
                Refresh();
                return false;
            }

            EnsureChain();
            _pendingOpponentTake = _cubeAdvisor.Decide(_state, _state.turn).ShouldTake;
            BackgammonEngine.OfferDouble(_state);
            Refresh();
            return true;
        }

        /// <summary>Kup teklifini kabul eder.</summary>
        /// <remarks>
        /// <see cref="GamePhase.CubeOffered"/> disinda cagrilirsa hicbir sey yapmaz. Bu koruma
        /// onemlidir: kup ust sinirda (<c>64</c>) iken ikiye katlama <see cref="MatchState"/>
        /// araligini asar ve <see cref="Refresh"/> istisna atarak oyunu kilitlerdi.
        /// </remarks>
        public void Take()
        {
            ThrowIfDisposed();
            if (_state.phase != GamePhase.CubeOffered)
            {
                return;
            }

            BackgammonEngine.Take(_state);
            Refresh();
        }

        /// <summary>Kup teklifini reddeder; oyun biter.</summary>
        public void Pass()
        {
            ThrowIfDisposed();
            if (_state.phase != GamePhase.CubeOffered)
            {
                return;
            }

            _result = BackgammonEngine.Pass(_state);
            _isGameOver = true;
            Refresh();
        }

        /// <summary>Biten oyunu skora isler ve yeni oyun kurar.</summary>
        public void StartNextGame()
        {
            ThrowIfDisposed();
            if (!_isGameOver)
            {
                throw new InvalidOperationException("Oyun bitmedi.");
            }

            if (!_resultApplied)
            {
                BackgammonEngine.ApplyResult(_state, _result);
                _resultApplied = true;
            }

            BackgammonEngine.PrepareNextGame(_state);
            _isGameOver = _state.phase == GamePhase.GameOver;
            if (!_isGameOver)
            {
                _result = default(GameResult);
                _resultApplied = false;
            }

            InvalidateChain();
            Refresh();
        }

        /// <summary>Kup kararini hesaplar (arama surerken onbellekten doner).</summary>
        public CubeDecision EvaluateCube()
        {
            ThrowIfDisposed();
            if (!_searchGate.Wait(0))
            {
                return _lastCubeDecision ?? default(CubeDecision);
            }

            try
            {
                CubeDecision decision = ComputeCubeDecision();
                _lastCubeDecision = decision;
                return decision;
            }
            finally
            {
                _searchGate.Release();
            }
        }

        private CubeDecision ComputeCubeDecision()
        {
            EnsureChain();
            return _cubeAdvisor.Decide(_state, _state.turn);
        }

        /// <summary>Mevcut pozisyonun analizi (arama surerken onbellekten doner).</summary>
        public PositionAnalysis AnalyzeCurrent()
        {
            ThrowIfDisposed();
            if (!_searchGate.Wait(0))
            {
                return _lastAnalysis;
            }

            try
            {
                PositionAnalysis analysis = ComputeCurrentAnalysis();
                _lastAnalysis = analysis;
                return analysis;
            }
            finally
            {
                _searchGate.Release();
            }
        }

        private PositionAnalysis ComputeCurrentAnalysis()
        {
            EnsureChain();

            int perspective = _state.turn;
            double equity;
            bool exact = false;
            bool fromBearoff = false;

            // Online states can arrive with a terminal board while the phase still
            // says Moving/WaitForRoll (the winning move was applied, the next game
            // has not started yet). Detect that here so the evaluators never see a
            // terminal position (Bolum 2.2: terminal kayitlar vektorlestirilemez).
            bool gameOver = _isGameOver;
            GameResult result = _result;
            if (!gameOver && BackgammonEngine.IsGameOver(_state, _options.EngineSettings, out GameResult terminal))
            {
                gameOver = true;
                result = terminal;
            }

            if (gameOver)
            {
                int points = result.Points;
                equity = result.Winner == perspective ? points : -points;
                exact = true;
            }
            else if (_state.phase == GamePhase.Moving || _state.phase == GamePhase.PreRoll ||
                     _state.phase == GamePhase.WaitForRoll)
            {
                equity = EvaluatePosition(_moneyEvaluator, _state, perspective);
                fromBearoff = IsBearoffExact(_state);
                exact = fromBearoff;
            }
            else
            {
                equity = 0.0;
            }

            MatchState match = MatchState.From(_state);
            double matchEquity = equity;
            double mwc = double.NaN;
            if (!match.IsMoneyGame && _options.Met != null)
            {
                matchEquity = gameOver ? equity : EvaluatePosition(_positionEvaluator, _state, perspective);
                mwc = (matchEquity + 1.0) * 0.5;
            }

            OutcomeDistribution? distribution = null;
            if (!gameOver && _distribution != null &&
                (_state.phase == GamePhase.Moving || _state.phase == GamePhase.PreRoll ||
                 _state.phase == GamePhase.WaitForRoll))
            {
                distribution = EvaluateDistribution(_state, perspective);
            }

            CubeDecision? cube = null;
            if (!gameOver && _state.phase == GamePhase.PreRoll &&
                BackgammonEngine.CanOffer(_state, _options.EngineSettings))
            {
                cube = _cubeAdvisor.Decide(_state, perspective);
            }

            return new PositionAnalysis(
                equity, matchEquity, mwc, distribution, fromBearoff, exact,
                PipCount(_state, perspective), PipCount(_state, -perspective),
                RollsToOff(_state, perspective), RollsToOff(_state, -perspective), cube);
        }

        /// <summary>
        /// Her yasal hamle icin <see cref="PositionAnalysis"/> uretir (UI "hamle ipuclari").
        /// </summary>
        /// <remarks>
        /// <b>Allocation yapar</b> (UI yolu, hot path degil). Terminal afterstate'ler
        /// degerlendiriciye <b>gonderilmez</b> (Bolum 2.2); onlarin equity'si sonuc puanindan gelir.
        /// </remarks>
        public IReadOnlyList<PositionAnalysis> AnalyzeCandidates()
        {
            ThrowIfDisposed();
            if (!_searchGate.Wait(0))
            {
                return Array.Empty<PositionAnalysis>();
            }

            try
            {
                return ComputeCandidates();
            }
            finally
            {
                _searchGate.Release();
            }
        }

        private IReadOnlyList<PositionAnalysis> ComputeCandidates()
        {
            EnsureChain();
            _candidates.Clear();

            if (_state.phase != GamePhase.Moving || _state.remainingCount == 0)
            {
                return _candidates;
            }

            LegalMoveGenerator.GenerateAfterStates(_state, _options.EngineSettings, _afterStates);
            int count = _afterStates.Count;
            if (count == 0)
            {
                return _candidates;
            }

            int perspective = _state.turn;
            VectorizerScalars scalars = VectorizerScalars.From(_state);

            _nonTerminal.Clear();
            _scratch.CopyFrom(_state);
            for (int i = 0; i < count; i++)
            {
                if (_afterStates.IsTerminal[i])
                {
                    continue;
                }

                BackgammonEngine.LoadAfterState(_scratch, _afterStates, i);
                _nonTerminal.Add(_scratch, _afterStates.Sequences[i]);
            }

            int nonTerminalCount = _nonTerminal.Count;
            if (nonTerminalCount > 0)
            {
                _positionEvaluator.EvaluateBatch(_nonTerminal, 0, nonTerminalCount, perspective, scalars,
                                                 new Span<float>(_equityBuffer, 0, nonTerminalCount));
            }

            int evaluated = 0;
            for (int i = 0; i < count; i++)
            {
                double equity;
                bool exact;
                if (_afterStates.IsTerminal[i])
                {
                    int points = _afterStates.ResultPoints[i];
                    bool moverWon = _afterStates.WhiteBorneOff[i] == BackgammonState.PiecesPerPlayer
                        ? perspective > 0
                        : perspective < 0;
                    equity = moverWon ? points : -points;
                    exact = true;
                }
                else
                {
                    equity = _equityBuffer[evaluated];
                    evaluated++;
                    exact = IsBearoffExact(_afterStates.Boards, i);
                }

                _candidates.Add(new PositionAnalysis(
                    equity, equity, double.NaN, null, exact, exact,
                    PipCount(_afterStates.Boards, i, perspective),
                    PipCount(_afterStates.Boards, i, -perspective),
                    -1, -1, null));
            }

            return _candidates;
        }

        /// <summary>
        /// Arama yapan is parcaciginda <b>senkron</b> arama.
        /// </summary>
        /// <remarks>
        /// <para>
        /// <b>Neden var:</b> Unity/Mono altinda ONNX Runtime'in <c>OrtIoBinding</c> nesnesi is
        /// parcacigi guvenli degildir; gercek kare dongusu icinde arka plan is parcaciginda
        /// calistirildiginda <c>SynchronizeBoundInputs</c> erisim ihlali (0xC0000005) uretir.
        /// Bu yuzden Unity tarafi aramayi <b>ana is parcaciginda</b> calistirir.
        /// </para>
        /// <para>
        /// <see cref="ThinkAsync"/> Unity'den bagimsiz katmanda (ve testlerde) aynen gecerlidir.
        /// </para>
        /// </remarks>
        public SearchOutcome Think()
        {
            ThrowIfDisposed();

            if (!_searchGate.Wait(0))
            {
                throw new InvalidOperationException(
                    "Ayni anda yalnizca tek arama calisabilir (Faz 5 Bolum 5.4).");
            }

            try
            {
                _searchActive = true;
                return RunSearch(CancellationToken.None, Timeout.InfiniteTimeSpan);
            }
            finally
            {
                _searchActive = false;
                _searchGate.Release();
            }
        }

        /// <summary>Asenkron arama (sinirsiz butce).</summary>
        public Task<SearchOutcome> ThinkAsync(CancellationToken ct)
        {
            return ThinkAsync(ct, Timeout.InfiniteTimeSpan);
        }

        /// <summary>
        /// Asenkron arama. <paramref name="budget"/> <b>tavsiye</b> niteligindedir: asildiginda
        /// <see cref="SearchOutcome.WasCancelled"/> <c>true</c> olur ve en iyi hamle yine doner.
        /// </summary>
        public async Task<SearchOutcome> ThinkAsync(CancellationToken ct, TimeSpan budget)
        {
            ThrowIfDisposed();

            if (!_searchGate.Wait(0))
            {
                throw new InvalidOperationException(
                    "Ayni anda yalnizca tek arama calisabilir (Faz 5 Bolum 5.4).");
            }

            try
            {
                if (ct.IsCancellationRequested)
                {
                    throw new OperationCanceledException(ct);
                }

                _searchActive = true;
                return await Task.Run(() => RunSearch(ct, budget)).ConfigureAwait(false);
            }
            finally
            {
                _searchActive = false;
                _searchGate.Release();
            }
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            _searchGate.Dispose();
        }

        // ------------------------------------------------------------------
        // Ic yardimcilar
        // ------------------------------------------------------------------

        private SearchOutcome RunSearch(CancellationToken ct, TimeSpan budget)
        {
            EnsureChain();

            if (_state.phase != GamePhase.Moving || _state.remainingCount == 0)
            {
                return new SearchOutcome(default(MoveSequence), 0f, true, 0, 0, 0, 0,
                                         Array.Empty<RootCandidate>(), false);
            }

            SearchSettings settings = _options.SearchSettings;
            if (_options.MaxPlies > 0 && settings.DepthPly > _options.MaxPlies)
            {
                settings.DepthPly = _options.MaxPlies;
            }

            long startTicks = Stopwatch.GetTimestamp();
            SearchResult result = BackgammonSearch.Search(_state, settings, _options.EngineSettings, _workspace,
                                                          _positionEvaluator, _policyEvaluator);
            double elapsedMs = (Stopwatch.GetTimestamp() - startTicks) * 1000.0 / Stopwatch.Frequency;

            bool cancelled = ct.IsCancellationRequested;
            if (budget != Timeout.InfiniteTimeSpan && elapsedMs > budget.TotalMilliseconds)
            {
                cancelled = true;
            }

            var candidates = new RootCandidate[result.RootCandidates.Length];
            result.RootCandidates.CopyTo(candidates);

            return new SearchOutcome(result.BestSequence, result.EvaluationScore, result.IsPass,
                                     result.CandidateCount, result.EvaluatorCalls, result.PolicyCalls,
                                     result.NodesVisited, candidates, cancelled);
        }

        private double EvaluatePosition(IPositionEvaluator evaluator, BackgammonState state, int perspective)
        {
            // Defense in depth: a terminal position must never reach the search
            // (the vectorizer rejects terminal records by design).
            if (BackgammonEngine.IsGameOver(state, _options.EngineSettings, out GameResult terminal))
            {
                return terminal.Winner == perspective ? terminal.Points : -terminal.Points;
            }

            if (state.phase == GamePhase.Moving && state.remainingCount > 0)
            {
                return SearchEquity(evaluator, state);
            }

            if (state.phase != GamePhase.PreRoll && state.phase != GamePhase.WaitForRoll)
            {
                return 0.0;
            }

            double sum = 0.0;
            double weight = 0.0;
            for (int i = 0; i < DicePairs.Count; i++)
            {
                _scratch.CopyFrom(state);
                BackgammonEngine.SetDice(_scratch, DicePairs.First[i], DicePairs.Second[i]);
                sum += DicePairs.Weight[i] * SearchEquity(evaluator, _scratch);
                weight += DicePairs.Weight[i];
            }

            return weight > 0.0 ? sum / weight : 0.0;
        }

        private float SearchEquity(IPositionEvaluator evaluator, BackgammonState state)
        {
            SearchSettings settings = _options.SearchSettings;
            settings.DepthPly = 0;
            settings.UseEvalCache = false;
            settings.UsePolicyOrdering = false;
            settings.ExactRootScores = false;

            SearchResult result = BackgammonSearch.Search(state, settings, _options.EngineSettings,
                                                          _analysisWorkspace, evaluator, null);
            return result.EvaluationScore;
        }

        private OutcomeDistribution? EvaluateDistribution(BackgammonState state, int perspective)
        {
            if (state.phase == GamePhase.Moving && state.remainingCount > 0)
            {
                return BestDistribution(state, perspective);
            }

            if (state.phase != GamePhase.PreRoll && state.phase != GamePhase.WaitForRoll)
            {
                return null;
            }

            double win = 0.0;
            double winGammon = 0.0;
            double winBackgammon = 0.0;
            double loseGammon = 0.0;
            double loseBackgammon = 0.0;
            double weight = 0.0;

            for (int i = 0; i < DicePairs.Count; i++)
            {
                _scratch.CopyFrom(state);
                BackgammonEngine.SetDice(_scratch, DicePairs.First[i], DicePairs.Second[i]);
                OutcomeDistribution? d = BestDistribution(_scratch, perspective);
                if (!d.HasValue)
                {
                    continue;
                }

                double w = DicePairs.Weight[i];
                win += w * d.Value.Win;
                winGammon += w * d.Value.WinGammon;
                winBackgammon += w * d.Value.WinBackgammon;
                loseGammon += w * d.Value.LoseGammon;
                loseBackgammon += w * d.Value.LoseBackgammon;
                weight += w;
            }

            if (weight <= 0.0)
            {
                return null;
            }

            return new OutcomeDistribution(
                (float)(win / weight), (float)(winGammon / weight), (float)(winBackgammon / weight),
                (float)(loseGammon / weight), (float)(loseBackgammon / weight));
        }

        private OutcomeDistribution? BestDistribution(BackgammonState state, int perspective)
        {
            LegalMoveGenerator.GenerateAfterStates(state, _options.EngineSettings, _afterStates);
            int count = _afterStates.Count;
            if (count == 0)
            {
                return null;
            }

            VectorizerScalars scalars = VectorizerScalars.From(state);

            _nonTerminal.Clear();
            _scratch.CopyFrom(state);
            for (int i = 0; i < count; i++)
            {
                if (_afterStates.IsTerminal[i])
                {
                    continue;
                }

                BackgammonEngine.LoadAfterState(_scratch, _afterStates, i);
                _nonTerminal.Add(_scratch, _afterStates.Sequences[i]);
            }

            int nonTerminalCount = _nonTerminal.Count;
            if (nonTerminalCount == 0)
            {
                return null;
            }

            _distribution.EvaluateDistributionBatch(_nonTerminal, 0, nonTerminalCount, perspective, scalars,
                                                    new Span<OutcomeDistribution>(_distributionBuffer, 0,
                                                                                  nonTerminalCount));

            int best = 0;
            double bestEquity = double.NegativeInfinity;
            for (int i = 0; i < nonTerminalCount; i++)
            {
                double equity = _distributionBuffer[i].Equity;
                if (equity > bestEquity)
                {
                    bestEquity = equity;
                    best = i;
                }
            }

            return _distributionBuffer[best];
        }

        private bool IsBearoffExact(BackgammonState state)
        {
            return _options.Bearoff != null && BearoffAwareEvaluator.IsSolvable(state.board);
        }

        private bool IsBearoffExact(sbyte[] boards, int index)
        {
            if (_options.Bearoff == null)
            {
                return false;
            }

            var board = new ReadOnlySpan<sbyte>(boards, index * AfterStateList.BoardSize,
                                                AfterStateList.BoardSize);
            return BearoffAwareEvaluator.IsSolvable(board);
        }

        private int RollsToOff(BackgammonState state, int player)
        {
            if (_options.Bearoff == null)
            {
                return -1;
            }

            if (!BearoffDatabase.IsOneSidedBearoff(state.board, player))
            {
                return -1;
            }

            int maxRolls = _options.Bearoff.MaxRolls;
            if (_cdfBuffer == null || _cdfBuffer.Length < maxRolls + 1)
            {
                _cdfBuffer = new float[maxRolls + 1];
            }

            var cdf = new Span<float>(_cdfBuffer, 0, maxRolls + 1);
            if (!_options.Bearoff.TryGetCdf(state.board, player, cdf))
            {
                return -1;
            }

            double expected = 0.0;
            for (int k = 0; k < maxRolls; k++)
            {
                expected += 1.0 - cdf[k];
            }

            return (int)Math.Round(expected, MidpointRounding.AwayFromZero);
        }

        private static int PipCount(BackgammonState state, int player)
        {
            return PipCount(state.board, player);
        }

        private static int PipCount(sbyte[] boards, int index, int player)
        {
            var board = new ReadOnlySpan<sbyte>(boards, index * AfterStateList.BoardSize,
                                                AfterStateList.BoardSize);
            return PipCount(board, player);
        }

        private static int PipCount(ReadOnlySpan<sbyte> board, int player)
        {
            int total = 0;
            for (int p = 1; p <= 24; p++)
            {
                int v = board[p];
                if (player > 0)
                {
                    if (v > 0)
                    {
                        total += v * (25 - p);
                    }
                }
                else
                {
                    if (v < 0)
                    {
                        total += -v * p;
                    }
                }
            }

            int bar = board[BackgammonEngine.BarIndex(player)];
            total += (player > 0 ? bar : -bar) * 25;
            return total;
        }

        private void InvalidateChain()
        {
            _chainReady = false;
        }

        private void EnsureChain()
        {
            MatchState match = MatchState.From(_state);
            int key;
            unchecked
            {
                key = ((IPositionEvaluator)_options.Evaluator).Version * 31;
                key += (_options.Bearoff != null ? _options.Bearoff.Version : 0) * 17;
                key += (_options.Met != null ? _options.Met.Version : 0) * 7;
                key += (_options.Distribution != null ? _options.Distribution.Version : 0) * 3;
                key += match.Hash;
            }

            if (_chainReady && key == _chainKey)
            {
                return;
            }

            IPolicyValueEvaluator baseEvaluator = _options.Evaluator;
            IPositionEvaluator money = baseEvaluator;
            IPolicyEvaluator moneyPolicy = baseEvaluator;

            if (_options.Bearoff != null)
            {
                var bearoff = new BearoffAwareEvaluator(baseEvaluator, _options.Bearoff,
                                                        BearoffAwareOptions.Default);
                money = bearoff;
                moneyPolicy = bearoff;
            }

            _moneyEvaluator = money;
            _distribution = _options.Distribution ?? new HeuristicOutcomeDistributionEvaluator(money);

            IPositionEvaluator outer = money;
            IPolicyEvaluator outerPolicy = moneyPolicy;

            if (!match.IsMoneyGame && _options.Met != null)
            {
                var adapter = new PolicyValueAdapter(money, moneyPolicy);
                var matchAware = new MatchAwareEvaluator(adapter, _options.Met, _distribution, match);
                outer = matchAware;
                outerPolicy = matchAware;
            }

            _positionEvaluator = outer;
            _policyEvaluator = outerPolicy;
            _cubeAdvisor = new EquityCubeAdvisor(money, _options.Met ?? MatchEquityTable.Default,
                                                 _distribution, CubeAdvisorOptions.Default);
            _chainKey = key;
            _chainReady = true;

            // Bolum 2.2: Version degisince SearchWorkspace.Reset() zorunludur.
            _workspace.Reset();
            _analysisWorkspace.Reset();
        }

        private void Refresh()
        {
            EnsureChain();
            LegalMoveGenerator.GenerateAllLegalMoves(_state, _legalMoves);

            GameResult result;
            if (BackgammonEngine.IsGameOver(_state, _options.EngineSettings, out result))
            {
                _isGameOver = true;
                _result = result;
            }
            else if (_state.cubePassed)
            {
                _isGameOver = true;
                _result = new GameResult(_state.turn, GameResultType.Single, 1);
            }
            else
            {
                _isGameOver = false;
                _result = default(GameResult);
                _resultApplied = false;
            }

            // Oyun biter bitmez sonuc skora islenir: skor etiketi aninda guncellenir,
            // tahta ise son pozisyonda kalir (yeni oyun "Yeni oyun" ile kurulur).
            if (_isGameOver && !_resultApplied)
            {
                BackgammonEngine.ApplyResult(_state, _result);
                _resultApplied = true;
            }

            Changed?.Invoke();
        }

        private void ThrowIfDisposed()
        {
            if (_disposed)
            {
                throw new ObjectDisposedException(nameof(GameOrchestrator));
            }
        }
    }
}
