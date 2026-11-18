using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Önceden ayrılmış hamle buffer'ı. Üretici bunu doldurur, her çağrıda yeni liste döndürmez.
    /// Bölüm 2.3.
    /// </summary>
    public sealed class MoveList
    {
        /// <summary>
        /// Varsayılan kapasite. Tekilleştirilmiş hamle sayısı afterstate sayısına eşit olduğu için
        /// <see cref="AfterStateList.DefaultCapacity"/> ile aynı tutulur (F7-26).
        /// </summary>
        public const int DefaultCapacity = AfterStateList.DefaultCapacity;

        public readonly MoveSequence[] Moves;

        public int Count;

        public MoveList()
            : this(DefaultCapacity)
        {
        }

        public MoveList(int capacity)
        {
            if (capacity <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity));
            }

            Moves = new MoveSequence[capacity];
        }

        public int Capacity => Moves.Length;

        public void Clear()
        {
            Count = 0;
        }

        public void Add(in MoveSequence sequence)
        {
            if (Count >= Moves.Length)
            {
                throw new InvalidOperationException("MoveList kapasitesi aşıldı (" + Moves.Length + ").");
            }

            Moves[Count] = sequence;
            Count++;
        }

        public MoveSequence this[int index]
        {
            get
            {
                if ((uint)index >= (uint)Count)
                {
                    throw new ArgumentOutOfRangeException(nameof(index));
                }

                return Moves[index];
            }
        }
    }
}
