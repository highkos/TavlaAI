using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Bir turda oynanan tam hamle dizisi (en fazla 4 adım). Sabit boyutlu struct. Bölüm 2.2.
    /// </summary>
    public struct MoveSequence
    {
        public const int MaxSteps = 4;

        public byte Count;
        public MoveStep S0;
        public MoveStep S1;
        public MoveStep S2;
        public MoveStep S3;

        public bool IsEmpty => Count == 0;

        public MoveStep this[int index]
        {
            get
            {
                switch (index)
                {
                    case 0: return S0;
                    case 1: return S1;
                    case 2: return S2;
                    case 3: return S3;
                    default: throw new IndexOutOfRangeException("MoveSequence adım indeksi 0..3 olmalıdır.");
                }
            }
            set
            {
                switch (index)
                {
                    case 0: S0 = value; break;
                    case 1: S1 = value; break;
                    case 2: S2 = value; break;
                    case 3: S3 = value; break;
                    default: throw new IndexOutOfRangeException("MoveSequence adım indeksi 0..3 olmalıdır.");
                }
            }
        }

        public void Clear()
        {
            Count = 0;
            S0 = default;
            S1 = default;
            S2 = default;
            S3 = default;
        }

        public void Add(in MoveStep step)
        {
            if (Count >= MaxSteps)
            {
                throw new InvalidOperationException("MoveSequence en fazla 4 adım tutabilir.");
            }

            this[Count] = step;
            Count++;
        }

        public override string ToString()
        {
            if (Count == 0)
            {
                return "(pass)";
            }

            var parts = new string[Count];
            for (int i = 0; i < Count; i++)
            {
                parts[i] = this[i].ToString();
            }

            return string.Join(" | ", parts);
        }
    }
}
