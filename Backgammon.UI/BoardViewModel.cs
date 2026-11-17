using System;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>Bir hanenin gorunumu: sahibi ve tas sayisi.</summary>
    public readonly struct PointView
    {
        /// <summary><c>+1</c> Beyaz, <c>-1</c> Siyah, <c>0</c> bos.</summary>
        public readonly sbyte Owner;

        /// <summary>Tas sayisi (0 ise bos).</summary>
        public readonly int Count;

        public PointView(sbyte owner, int count)
        {
            Owner = owner;
            Count = count;
        }

        public bool IsEmpty
        {
            get { return Count == 0; }
        }

        public override string ToString()
        {
            return Owner + "x" + Count;
        }
    }

    /// <summary>
    /// Faz 5 Bolum 6.2: tahtanin saf C# gorunumu. <see cref="BackgammonState"/>'i birebir yansitir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Unity yok, <c>INotifyPropertyChanged</c> yok.</b> Degisim bildirimi <see cref="Changed"/>
    /// ile yapilir; MonoBehaviour abone olur ve kare basina bir kez okur (Bolum 6.2 kurali).
    /// </para>
    /// <para>
    /// <see cref="Points"/>[i] tahta hanesi <c>i + 1</c>'e karsilik gelir (0 tabanli dizi, 1 tabanli
    /// hane). Bar ve toplama ayri alanlardadir.
    /// </para>
    /// </remarks>
    public sealed class BoardViewModel
    {
        /// <summary>Oyun hanesi sayisi (bar ve toplama haric).</summary>
        public const int PointCount = 24;

        private readonly PointView[] _points = new PointView[PointCount];

        /// <summary>Hane gorunumleri; <c>Points[i]</c> = tahta hanesi <c>i + 1</c>.</summary>
        public PointView[] Points
        {
            get { return _points; }
        }

        /// <summary>Beyaz bar (tahta 0).</summary>
        public PointView WhiteBar { get; private set; }

        /// <summary>Siyah bar (tahta 25).</summary>
        public PointView BlackBar { get; private set; }

        /// <summary>Beyazin topladigi tas sayisi.</summary>
        public int WhiteBorneOff { get; private set; }

        /// <summary>Siyazin topladigi tas sayisi.</summary>
        public int BlackBorneOff { get; private set; }

        /// <summary>Siradaki oyuncu: <c>+1</c> Beyaz, <c>-1</c> Siyah.</summary>
        public sbyte Turn { get; private set; }

        /// <summary>Bu tur atilan ilk zar (0 = atilmadi).</summary>
        public byte Die1 { get; private set; }

        /// <summary>Bu tur atilan ikinci zar (0 = atilmadi).</summary>
        public byte Die2 { get; private set; }

        /// <summary>Kalan zar sayisi (0..4).</summary>
        public byte RemainingCount { get; private set; }

        /// <summary>Oyun fazi.</summary>
        public GamePhase Phase { get; private set; }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary>Hanenin gorunumu (1..24).</summary>
        public PointView PointAt(int point)
        {
            if (point < 1 || point > PointCount)
            {
                throw new ArgumentOutOfRangeException(nameof(point));
            }

            return _points[point - 1];
        }

        /// <summary><see cref="BackgammonState"/>'ten tum alanlari kopyalar.</summary>
        public void Update(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            for (int p = 1; p <= PointCount; p++)
            {
                int v = state.board[p];
                _points[p - 1] = v > 0
                    ? new PointView(1, v)
                    : v < 0 ? new PointView(-1, -v) : new PointView(0, 0);
            }

            int whiteBar = state.board[0];
            WhiteBar = whiteBar > 0 ? new PointView(1, whiteBar) : new PointView(0, 0);

            int blackBar = state.board[25];
            BlackBar = blackBar < 0 ? new PointView(-1, -blackBar) : new PointView(0, 0);

            WhiteBorneOff = state.whiteBorneOff;
            BlackBorneOff = state.blackBorneOff;
            Turn = state.turn;
            Die1 = state.rolledDice[0];
            Die2 = state.rolledDice[1];
            RemainingCount = state.remainingCount;
            Phase = state.phase;

            Changed?.Invoke();
        }
    }
}
