using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Basit state havuzu. Thread-safe DEĞİLDİR; her thread kendi havuzunu oluşturur.
    /// Bölüm 2.6.
    /// </summary>
    public sealed class StatePool
    {
        private readonly BackgammonState[] _states;
        private int _available;

        public StatePool(int capacity)
        {
            if (capacity <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity));
            }

            _states = new BackgammonState[capacity];
            for (int i = 0; i < capacity; i++)
            {
                _states[i] = new BackgammonState();
            }

            _available = capacity;
        }

        public int Capacity => _states.Length;

        public int Available => _available;

        /// <summary>Havuzdan bir state alır. Havuz boşsa hata verir (kapasite yetersiz).</summary>
        public BackgammonState Rent()
        {
            if (_available == 0)
            {
                throw new InvalidOperationException("StatePool boş: kapasite yetersiz.");
            }

            _available--;
            return _states[_available];
        }

        public void Return(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            if (_available >= _states.Length)
            {
                throw new InvalidOperationException("StatePool kapasitesi aşıldı: state bu havuza ait değil.");
            }

            _states[_available] = s;
            _available++;
        }
    }
}
