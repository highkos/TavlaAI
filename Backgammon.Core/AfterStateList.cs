using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Bir hamle sonrası pozisyonları (afterstate) hafif kayıtlar olarak tutan, önceden ayrılmış
    /// SoA (structure of arrays) buffer'ı. Faz 2 (vektörleştirme) ve Faz 3 (arama, kök politika
    /// hedefi) doğrudan bunu kullanır. Bölüm 2.3b.
    /// </summary>
    public sealed class AfterStateList
    {
        public const int BoardSize = 26;

        /// <summary>
        /// Ölçülen en yüksek afterstate sayısı (F7-26). 1-1 dublesinde <b>2139</b>; 200 000
        /// rastgele pozisyonda en fazla 576. Tepe-tırmanma aramasıyla bulundu, teorik üst sınır
        /// değildir. Eski varsayılan kapasite (2048) bu yasal pozisyonda <b>aşılıyordu</b>.
        /// </summary>
        public const int MeasuredMaxAfterStates = 2139;

        /// <summary>
        /// Varsayılan kapasite. Ölçülen üst sınırın (<see cref="MeasuredMaxAfterStates"/>) yaklaşık
        /// 1,9 katı; eski değer 2048 idi ve ölçülen en kötü pozisyonda taşıyordu (F7-26).
        /// </summary>
        public const int DefaultCapacity = 4096;

        /// <summary>Capacity * 26. Kayıt i: [i*26 .. i*26+25].</summary>
        public readonly sbyte[] Boards;

        public readonly byte[] WhiteBorneOff;
        public readonly byte[] BlackBorneOff;

        /// <summary>Afterstate hash'i (Bölüm 2.1 tanımı, turn = hamleyi yapan).</summary>
        public readonly ulong[] Hash;

        /// <summary>Bu pozisyona götüren (kanonik) hamle dizisi.</summary>
        public readonly MoveSequence[] Sequences;

        /// <summary>WhiteBorneOff == 15 || BlackBorneOff == 15.</summary>
        public readonly bool[] IsTerminal;

        /// <summary>0 = terminal değil, 1 = Single, 2 = Gammon, 3 = Backgammon.</summary>
        public readonly byte[] ResultType;

        /// <summary>0 = terminal değil, aksi halde 1/2/3 (Jacoby uygulanmış, cubeValue hariç).</summary>
        public readonly byte[] ResultPoints;

        public int Count { get; private set; }

        public int Capacity { get; }

        public AfterStateList()
            : this(DefaultCapacity)
        {
        }

        public AfterStateList(int capacity)
        {
            if (capacity <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity));
            }

            Capacity = capacity;
            Boards = new sbyte[capacity * BoardSize];
            WhiteBorneOff = new byte[capacity];
            BlackBorneOff = new byte[capacity];
            Hash = new ulong[capacity];
            Sequences = new MoveSequence[capacity];
            IsTerminal = new bool[capacity];
            ResultType = new byte[capacity];
            ResultPoints = new byte[capacity];
        }

        public void Clear()
        {
            Count = 0;
        }

        /// <summary>
        /// Artımlı hash'in tahtayla tutarlı olduğunu doğrular. Yalnızca Debug derlemelerinde
        /// çağrılır; Release'de çağrı tamamen kaldırılır (sıfır maliyet).
        /// </summary>
        [System.Diagnostics.Conditional("DEBUG")]
        private static void VerifyHash(BackgammonState s)
        {
            ulong recomputed = BackgammonEngine.ComputeZobristHash(s);
            if (s.hash != recomputed)
            {
                throw new InvalidOperationException(
                    "AddPass: state.hash tutarsız (state.hash=" + s.hash.ToString("X16") +
                    " recomputed=" + recomputed.ToString("X16") + ").");
            }
        }

        public ReadOnlySpan<sbyte> BoardOf(int i)
        {
            if ((uint)i >= (uint)Count)
            {
                throw new ArgumentOutOfRangeException(nameof(i));
            }

            return new ReadOnlySpan<sbyte>(Boards, i * BoardSize, BoardSize);
        }

        /// <summary>
        /// "Pas afterstate'i": pozisyon aynı, turn = s.turn, Sequence.Count = 0, hash s.hash'e eşit.
        /// Pas'ta oyun bitemez; bu yüzden IsTerminal = false, ResultType = 0, ResultPoints = 0.
        /// </summary>
        /// <remarks>
        /// Hash doğrudan kopyalanır (artımlı hash sözleşmesi). Bayat bir hash transpozisyon
        /// tablosunda yanlış eşleşmeye yol açacağı için Debug derlemelerinde doğrulanır (F7-27).
        /// </remarks>
        public void AddPass(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            VerifyHash(s);

            if (Count >= Capacity)
            {
                throw new InvalidOperationException("AfterStateList kapasitesi aşıldı (" + Capacity + ").");
            }

            int i = Count;
            int offset = i * BoardSize;
            Array.Copy(s.board, 0, Boards, offset, BoardSize);

            WhiteBorneOff[i] = s.whiteBorneOff;
            BlackBorneOff[i] = s.blackBorneOff;
            Hash[i] = s.hash;

            var seq = default(MoveSequence);
            seq.Clear();
            Sequences[i] = seq;

            IsTerminal[i] = false;
            ResultType[i] = 0;
            ResultPoints[i] = 0;

            Count++;
        }

        /// <summary>
        /// Bir hamle sonrası pozisyonu kaydeder ve kaydın indeksini döner. <c>IsTerminal</c>
        /// otomatik hesaplanır; <c>ResultType</c>/<c>ResultPoints</c> çağıran tarafından
        /// doldurulur (bkz. <see cref="LegalMoveGenerator.GenerateAfterStates"/>).
        /// </summary>
        public int Add(BackgammonState s, in MoveSequence seq)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (Count >= Capacity)
            {
                throw new InvalidOperationException("AfterStateList kapasitesi aşıldı (" + Capacity + ").");
            }

            int i = Count;
            int offset = i * BoardSize;
            Array.Copy(s.board, 0, Boards, offset, BoardSize);

            WhiteBorneOff[i] = s.whiteBorneOff;
            BlackBorneOff[i] = s.blackBorneOff;
            Hash[i] = s.hash;
            Sequences[i] = seq;

            IsTerminal[i] = s.whiteBorneOff == BackgammonState.PiecesPerPlayer ||
                            s.blackBorneOff == BackgammonState.PiecesPerPlayer;
            ResultType[i] = 0;
            ResultPoints[i] = 0;

            Count++;
            return i;
        }

        /// <summary>TÜM alanları birlikte takas eder (kararlı bölümleme için).</summary>
        /// <remarks>
        /// <para>
        /// Kayıtlar <b>paralel dizilerde</b> tutulur (<see cref="Boards"/>, <see cref="WhiteBorneOff"/>,
        /// <see cref="BlackBorneOff"/>, <see cref="Hash"/>, <see cref="Sequences"/>, <see cref="IsTerminal"/>,
        /// <see cref="ResultType"/>, <see cref="ResultPoints"/>). Bu yüzden takas <b>hepsinde</b>
        /// birlikte yapılmalıdır; biri atlanırsa kayıtlar birbirine karışır (F7-36).
        /// </para>
        /// <para>
        /// <see cref="BoardOf"/> yalnızca <b>okuma</b> içindir (<see cref="ReadOnlySpan{T}"/> döner).
        /// Tahta yazmak gerekiyorsa <see cref="Boards"/> doğrudan kullanılmalıdır; aksi halde
        /// bu metot ile <see cref="BoardOf"/> arasındaki sözleşme bozulur.
        /// </para>
        /// </remarks>
        public void Swap(int i, int j)
        {
            if ((uint)i >= (uint)Count)
            {
                throw new ArgumentOutOfRangeException(nameof(i));
            }

            if ((uint)j >= (uint)Count)
            {
                throw new ArgumentOutOfRangeException(nameof(j));
            }

            if (i == j)
            {
                return;
            }

            int oi = i * BoardSize;
            int oj = j * BoardSize;
            for (int k = 0; k < BoardSize; k++)
            {
                sbyte tmpBoard = Boards[oi + k];
                Boards[oi + k] = Boards[oj + k];
                Boards[oj + k] = tmpBoard;
            }

            byte tmp = WhiteBorneOff[i];
            WhiteBorneOff[i] = WhiteBorneOff[j];
            WhiteBorneOff[j] = tmp;

            tmp = BlackBorneOff[i];
            BlackBorneOff[i] = BlackBorneOff[j];
            BlackBorneOff[j] = tmp;

            ulong tmpHash = Hash[i];
            Hash[i] = Hash[j];
            Hash[j] = tmpHash;

            MoveSequence tmpSeq = Sequences[i];
            Sequences[i] = Sequences[j];
            Sequences[j] = tmpSeq;

            bool tmpTerminal = IsTerminal[i];
            IsTerminal[i] = IsTerminal[j];
            IsTerminal[j] = tmpTerminal;

            tmp = ResultType[i];
            ResultType[i] = ResultType[j];
            ResultType[j] = tmp;

            tmp = ResultPoints[i];
            ResultPoints[i] = ResultPoints[j];
            ResultPoints[j] = tmp;
        }
    }
}
