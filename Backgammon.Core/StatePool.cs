using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Basit state havuzu. Thread-safe DEĞİLDİR; her thread kendi havuzunu oluşturur.
    /// Bölüm 2.6.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Havuz, sahip olduğu <see cref="BackgammonState"/> örneklerini <b>asla değiştirmez</b>:
    /// boş yuvalar bir indeks yığınında tutulur, böylece yabancı bir state iade edildiğinde
    /// havuzun kendi örneği kaybolmaz (F7-25).
    /// </para>
    /// <para>
    /// <see cref="Return"/> state'i <see cref="BackgammonState.Reset"/> ile başlangıç durumuna
    /// döndürür. Böylece bir sonraki <see cref="Rent"/> bayat veri sızdırmaz: çağıran yalnızca
    /// birkaç alanı yazsa bile kalan alanlar tanımlı bir tabana sahiptir (F7-25).
    /// </para>
    /// <para>
    /// Sahiplik denetimi <see cref="Array.IndexOf{T}(T[],T)"/> ile yapılır; maliyeti
    /// O(kapasite)'dir. Havuzlar küçük tutulur (tipik olarak 1-4 state), bu yüzden bu maliyet
    /// önemsizdir ve <b>hiç allocation yapmaz</b>.
    /// </para>
    /// </remarks>
    public sealed class StatePool
    {
        private readonly BackgammonState[] _states;

        /// <summary>Boş yuvaların indeks yığını. <c>_free[0.._freeCount-1]</c> geçerlidir.</summary>
        private readonly int[] _free;

        /// <summary>Yuva kirada mı? Çift iadeyi tespit etmek için.</summary>
        private readonly bool[] _rented;

        private int _freeCount;

        public StatePool(int capacity)
        {
            if (capacity <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity));
            }

            _states = new BackgammonState[capacity];
            _free = new int[capacity];
            _rented = new bool[capacity];

            for (int i = 0; i < capacity; i++)
            {
                _states[i] = new BackgammonState();
                _free[i] = i;
            }

            _freeCount = capacity;
        }

        public int Capacity => _states.Length;

        public int Available => _freeCount;

        /// <summary>Havuzdan bir state alır. Havuz boşsa hata verir (kapasite yetersiz).</summary>
        public BackgammonState Rent()
        {
            if (_freeCount == 0)
            {
                throw new InvalidOperationException("StatePool boş: kapasite yetersiz.");
            }

            int index = _free[--_freeCount];
            _rented[index] = true;
            return _states[index];
        }

        /// <summary>
        /// State'i havuza geri verir ve <see cref="BackgammonState.Reset"/> ile temizler.
        /// </summary>
        /// <exception cref="ArgumentNullException"><paramref name="s"/> null ise.</exception>
        /// <exception cref="InvalidOperationException">
        /// <paramref name="s"/> bu havuza ait değilse veya zaten iade edilmişse.
        /// </exception>
        public void Return(BackgammonState s)
        {
            if (s == null)
            {
                throw new ArgumentNullException(nameof(s));
            }

            int index = Array.IndexOf(_states, s);
            if (index < 0)
            {
                throw new InvalidOperationException("StatePool: state bu havuza ait değil.");
            }

            if (!_rented[index])
            {
                throw new InvalidOperationException("StatePool: state zaten iade edilmiş (çift iade).");
            }

            s.Reset();
            _rented[index] = false;
            _free[_freeCount++] = index;
        }
    }
}
