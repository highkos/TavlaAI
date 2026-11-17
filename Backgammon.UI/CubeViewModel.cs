using System;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>Kup widget'inin gorunurluk durumu.</summary>
    public enum CubeVisibility
    {
        /// <summary>Gizli (Crawford oyunu veya oyun baslamadi).</summary>
        Hidden = 0,

        /// <summary>Ortada (sahipsiz).</summary>
        Centered = 1,

        /// <summary>Bir oyuncuya ait.</summary>
        Owned = 2,

        /// <summary>Teklif edildi (kabul/red bekliyor).</summary>
        Offered = 3
    }

    /// <summary>
    /// Faz 5 Bolum 6.2 / 6.6: kup widget'inin saf C# gorunumu.
    /// </summary>
    /// <remarks>
    /// <b>Crawford oyununda kup gizlidir</b> (Bolum 4.5: Crawford oyununda kup kullanilmaz).
    /// </remarks>
    public sealed class CubeViewModel
    {
        /// <summary>Gorunurluk durumu.</summary>
        public CubeVisibility Visibility { get; private set; }

        /// <summary>Kup degeri (1, 2, 4, ... 64).</summary>
        public int Value { get; private set; }

        /// <summary>Kup sahibi: <c>0</c> ortada, <c>+1</c> Beyaz, <c>-1</c> Siyah.</summary>
        public sbyte Owner { get; private set; }

        /// <summary>Kup teklif edilebilir mi? (yalnizca <see cref="CubeVisibility.Centered"/> veya <see cref="CubeVisibility.Owned"/> iken anlamli)</summary>
        public bool CanOffer { get; private set; }

        /// <summary>
        /// Ekranda gosterilecek deger.
        /// </summary>
        /// <remarks>
        /// Teklif <b>beklerken</b> kup henuz ikiye katlanmaz (<see cref="Value"/> degismez), ancak
        /// oyuncunun kabul ettiginde oynanacak deger budur. Bu yuzden teklif fazinda
        /// <c>Value * 2</c> gosterilir; aksi halde teklif "carpan 1" gibi gorunur.
        /// </remarks>
        public int DisplayValue
        {
            get { return Visibility == CubeVisibility.Offered ? Value * 2 : Value; }
        }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary><see cref="BackgammonState"/>'ten gorunumu turetir.</summary>
        public void Update(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            Value = state.cubeValue;
            Owner = state.cubeOwner;

            if (state.isCrawfordGame)
            {
                Visibility = CubeVisibility.Hidden;
                CanOffer = false;
            }
            else if (state.phase == GamePhase.CubeOffered)
            {
                Visibility = CubeVisibility.Offered;
                CanOffer = false;
            }
            else if (state.cubeOwner == 0)
            {
                Visibility = CubeVisibility.Centered;
                CanOffer = BackgammonEngine.CanOffer(state);
            }
            else
            {
                Visibility = CubeVisibility.Owned;
                CanOffer = BackgammonEngine.CanOffer(state);
            }

            Changed?.Invoke();
        }
    }
}
