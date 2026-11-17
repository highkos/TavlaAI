using System;
using System.Collections.Generic;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 6.2 / 6.8: hamle girisinin saf C# durumu (secili tas, yasal hedefler, kismi hamle,
    /// geri alma).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Tek dogruluk kaynagi <see cref="LegalMoveGenerator"/>'dir.</b> Bu sinif kurallari
    /// yeniden uygulamaz; yalnizca uretecin ciktisini secili tas etrafinda <b>projekte eder</b>.
    /// Boylece Faz 1 kurallariyla ayrisma riski yoktur.
    /// </para>
    /// <para>
    /// <see cref="LegalTargets"/> = secili taştan <b>tek adımda</b> gidilebilen ve en az bir yasal
    /// (maksimum uzunlukta) dizide gecen hedeflerin <b>tekilleştirilmiş, artan</b> kumesi.
    /// </para>
    /// <para>
    /// <b>Bar önceliği burada da uygulanır.</b> <see cref="LegalMoveGenerator"/> barda taş varken
    /// yalnızca giriş adımlarını üretir; ancak projeksiyon dizinin <b>tüm</b> adımlarını taradığı
    /// için barda taş varken <c>12 -&gt; 15</c> gibi bir <b>ikinci</b> adım hedef olarak
    /// görünebiliyordu. Oyuncu bunu seçince "önce bardan giriş" kuralı çiğneniyordu. Bu yüzden
    /// bar dolu iken yalnızca <see cref="MoveStep.IsFromBar"/> adımları projekte edilir.
    /// </para>
    /// <para>
    /// <b>Adımlar güncel durumdan istenir.</b> <see cref="LegalMoveGenerator.GenerateAllLegalMoves"/>
    /// yalnızca maksimum uzunluktaki dizileri ve aynı son duruma ulaşan dizilerden yalnızca birini
    /// üretir; bu yüzden bazı <b>ilk</b> adımlar o listede hiç görünmez. Projeksiyon bu yüzden
    /// hedefleri ve adım bayraklarını <see cref="LegalMoveGenerator.GenerateStepsFrom"/> ile
    /// doğrudan güncel durumdan alır.
    /// </para>
    /// <para>
    /// <b>Eski hata:</b> projeksiyon dizilerin <b>tüm</b> adımlarını tarayıp ilk eşleşen
    /// <c>(From, To)</c> çiftini kopyalıyordu. <c>k &gt; 0</c> adımları <b>başka</b> bir ara
    /// durumdan üretildiği için bayrakları bayattı: 6-4 atıp 6 -&gt; 2 ile vurduktan sonra
    /// 8 -&gt; 2 adımı "vuruş" bayrağıyla uygulanıyor, hedefte rakip taş olmadığı için
    /// <see cref="BackgammonEngine.ApplyStep"/> kendi taşını yazarken rakibin taşını siliyordu
    /// ("vurunca taş eksiliyor" hatası). Aynı şekilde boş hanelerden de hedef üretilebiliyordu.
    /// </para>
    /// </remarks>
    public sealed class MoveInputController
    {
        private readonly MoveList _moves = new MoveList();
        private readonly BackgammonState _baseState = new BackgammonState();
        private readonly BackgammonState _scratch = new BackgammonState();
        private readonly List<int> _targets = new List<int>(8);
        private readonly List<int> _targetScratch = new List<int>(8);
        private readonly List<int> _fromTargets = new List<int>(8);
        private readonly MoveStep[] _stepBuf = new MoveStep[32];
        private bool _mustEnterFromBar;

        /// <summary>Secim yok sentinel degeri.</summary>
        public const int NoSelection = -1;

        /// <summary>
        /// Secili hane; <see cref="NoSelection"/> = secim yok. Bar icin <c>0</c> (Beyaz) /
        /// <c>25</c> (Siyah) kullanilir.
        /// </summary>
        public int SelectedPoint { get; private set; } = NoSelection;

        /// <summary>Secili taştan gidilebilen hedefler (artan, tekilleştirilmiş).</summary>
        public IReadOnlyList<int> LegalTargets
        {
            get { return _targets; }
        }

        /// <summary>Kismi hamle (henuz uygulanmamis adimlar).</summary>
        public MoveSequence PartialMove { get; private set; }

        /// <summary>Kismi hamle var mi?</summary>
        public bool HasPartialMove
        {
            get { return PartialMove.Count > 0; }
        }

        /// <summary>
        /// Kismi hamleye <b>devam edilebilir</b> mi? (kalan zarlarla yasal hamle var mi?)
        /// </summary>
        /// <remarks>
        /// <para>
        /// <see cref="LegalMoveGenerator"/> yalnizca maksimum uzunluktaki dizileri uretir; bu yuzden
        /// liste bos ise kalan zarlar <b>oynanamaz</b> demektir.
        /// </para>
        /// <para>
        /// <b>Neden gerekli:</b> 5-5 atilip yalnizca iki hamle oynanabiliyorsa
        /// <see cref="PartialMove"/>.Count (2) hicbir zaman <c>remainingCount</c> (4) degerine
        /// ulasmaz. Cagiran taraf bu bayrak <c>false</c> oldugunda kismi hamleyi uygulamali ve
        /// sirayi kapatmalidir; aksi halde oyuncu kilitlenir.
        /// </para>
        /// </remarks>
        public bool CanContinue
        {
            get { return _moves.Count > 0; }
        }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary>Yasal hamleleri yeniden uretir ve hedef kumesini gunceller.</summary>
        public void Update(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            _baseState.CopyFrom(state);
            Regenerate();
            RebuildTargets();
            Changed?.Invoke();
        }

        /// <summary>Bir hane secer (veya <see cref="NoSelection"/> ile secimi kaldirir).</summary>
        public void SelectPoint(int point)
        {
            if (point < NoSelection || point > 25)
            {
                throw new ArgumentOutOfRangeException(nameof(point));
            }

            SelectedPoint = point;
            RebuildTargets();
            Changed?.Invoke();
        }

        /// <summary>Secimi kaldirir.</summary>
        public void ClearSelection()
        {
            SelectPoint(NoSelection);
        }

        /// <summary>
        /// Verilen haneden <b>tek adimda</b> gidilebilen yasal hedefler (Bolum 6.8).
        /// Secimi <b>degistirmez</b>; <see cref="LegalTargets"/> ile ayni kaynaktan turetilir.
        /// </summary>
        public IReadOnlyList<int> LegalTargetsFrom(int fromPoint)
        {
            _fromTargets.Clear();
            if (fromPoint < 0 || fromPoint > 25)
            {
                return _fromTargets;
            }

            CollectTargets(fromPoint, _fromTargets);
            return _fromTargets;
        }

        /// <summary>
        /// Kismi hamleye bir adim ekler. Hedef <see cref="LegalTargets"/> icinde degilse <c>false</c>.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Adim <b>ureticinin urettigi gercek <see cref="MoveStep"/>'ten kopyalanir</b>; elle
        /// kurulmaz. Elle kurmak <see cref="MoveFlags.Hit"/>, <see cref="MoveFlags.BearOff"/> ve
        /// <see cref="MoveFlags.FromBar"/> bayraklarini kaybettirir.
        /// </para>
        /// <para>
        /// <b>Neden onemli:</b> <see cref="BackgammonEngine.ApplyStep"/> kirilan tasi bara
        /// <b>yalnizca</b> <see cref="MoveStep.IsHit"/> bayragina bakarak gonderir. Bayraksiz
        /// adimda rakip tasi tahtadan silinir ("vurdugumda tas kayboluyor" hatasi) ve bara
        /// girmesi gereken tas hic olusmadigi icin rakip bardan iceri giremez.
        /// </para>
        /// </remarks>
        public bool TryAddStep(int toPoint)
        {
            if (SelectedPoint == NoSelection || !_targets.Contains(toPoint))
            {
                return false;
            }

            MoveStep step;
            if (!TryFindStep(SelectedPoint, toPoint, out step))
            {
                return false;
            }

            // MoveSequence bir struct'tir; property uzerinden cagirmak kopyayi degistirir.
            MoveSequence partial = PartialMove;
            partial.Add(step);
            PartialMove = partial;

            SelectedPoint = toPoint;
            Regenerate();
            RebuildTargets();
            Changed?.Invoke();
            return true;
        }

        /// <summary>Son adimi geri alir.</summary>
        public void UndoStep()
        {
            if (PartialMove.Count == 0)
            {
                return;
            }

            MoveStep last = PartialMove[PartialMove.Count - 1];
            var trimmed = default(MoveSequence);
            trimmed.Clear();
            for (int i = 0; i < PartialMove.Count - 1; i++)
            {
                trimmed.Add(PartialMove[i]);
            }

            PartialMove = trimmed;
            SelectedPoint = last.From;
            Regenerate();
            RebuildTargets();
            Changed?.Invoke();
        }

        /// <summary>Kismi hamleyi ve secimi temizler.</summary>
        public void Reset()
        {
            PartialMove = default(MoveSequence);
            SelectedPoint = NoSelection;
            _targets.Clear();
            Regenerate();
            Changed?.Invoke();
        }

        /// <summary>
        /// Yasal hamle listesini <b>kismi hamle uygulanmis</b> durumdan yeniden uretir.
        /// </summary>
        /// <remarks>
        /// <para>
        /// Kismi hamle bir <b>onek</b>tir: oyuncu bir zari oynadiginda kalan zarlar
        /// <b>yeni</b> pozisyondan hesaplanmalidir. Aksi hâlde ikinci tiklamada
        /// birinci adimin hedefi tekrar kaynak sanilir ve gecersiz bir dizi olusur
        /// ("tas gitmiyor" hatasi).
        /// </para>
        /// <para>
        /// <see cref="BackgammonState"/> bir siniftir; <see cref="_scratch"/> uzerinde
        /// calisilir, <see cref="_baseState"/> bozulmaz.
        /// </para>
        /// </remarks>
        private void Regenerate()
        {
            _scratch.CopyFrom(_baseState);

            if (PartialMove.Count > 0)
            {
                MoveSequence partial = PartialMove;
                try
                {
                    BackgammonEngine.ApplyMove(_scratch, in partial);
                }
                catch (InvalidOperationException)
                {
                    // Kismi hamle artik uygulanamiyor (bayat): temizle ve taban duruma don.
                    PartialMove = default(MoveSequence);
                    _scratch.CopyFrom(_baseState);
                }
            }

            int bar = BackgammonEngine.BarIndex(_scratch.turn);
            _mustEnterFromBar = _scratch.board[bar] * _scratch.turn > 0;

            LegalMoveGenerator.GenerateAllLegalMoves(_scratch, _moves);
        }

        private void RebuildTargets()
        {
            _targets.Clear();
            if (SelectedPoint == NoSelection)
            {
                return;
            }

            CollectTargets(SelectedPoint, _targetScratch);
            for (int i = 0; i < _targetScratch.Count; i++)
            {
                _targets.Add(_targetScratch[i]);
            }
        }

        /// <summary>
        /// <paramref name="fromPoint"/> hanesinden <b>tek adimda</b> gidilebilen hedefleri toplar
        /// (artan, tekillestirilmis).
        /// </summary>
        /// <remarks>
        /// Adimlar <see cref="LegalMoveGenerator.GenerateFirstSteps"/> ile <b>guncel durumdan</b>
        /// uretilir; boylece bos hanelerden hedef uretilmez, bayraklar bayat olmaz ve maksimum
        /// uzunluk / buyuk zar kurali korunur.
        /// </remarks>
        private void CollectTargets(int fromPoint, List<int> into)
        {
            into.Clear();
            int n = LegalMoveGenerator.GenerateFirstSteps(_scratch, _moves, fromPoint, _stepBuf);
            for (int i = 0; i < n; i++)
            {
                MoveStep step = _stepBuf[i];
                if (_mustEnterFromBar && !step.IsFromBar)
                {
                    continue;
                }

                if (!into.Contains(step.To))
                {
                    into.Add(step.To);
                }
            }

            into.Sort();
        }

        /// <summary>
        /// <paramref name="fromPoint"/> -&gt; <paramref name="toPoint"/> adimini <b>guncel
        /// durumdan</b> uretilen adimlar arasindan bulur.
        /// </summary>
        /// <remarks>
        /// Donen <see cref="MoveStep"/> gercek uretici ciktisidir; <see cref="MoveFlags.Hit"/>,
        /// <see cref="MoveFlags.BearOff"/> ve <see cref="MoveFlags.FromBar"/> bayraklari guncel
        /// duruma gore dogrudur. Ayni hedefe birden fazla zarla gidilebiliyorsa (tas toplama)
        /// kucuk zar tercih edilir: <c>remainingDice</c> artan sirali oldugu icin ilk eslesme
        /// en kucuk zardir.
        /// </remarks>
        private bool TryFindStep(int fromPoint, int toPoint, out MoveStep step)
        {
            int n = LegalMoveGenerator.GenerateFirstSteps(_scratch, _moves, fromPoint, _stepBuf);
            for (int i = 0; i < n; i++)
            {
                MoveStep candidate = _stepBuf[i];
                if (_mustEnterFromBar && !candidate.IsFromBar)
                {
                    continue;
                }

                if (candidate.To == toPoint)
                {
                    step = candidate;
                    return true;
                }
            }

            step = default(MoveStep);
            return false;
        }
    }
}
