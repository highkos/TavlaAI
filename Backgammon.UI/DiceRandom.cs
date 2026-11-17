using System;
using System.Security.Cryptography;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Canli oynanis icin rastgele zar kaynagi uretir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Motor deterministiktir ve rastgeleligi <see cref="IRandom"/> olarak <b>disaridan</b> alir
    /// (Bolum 3). Testler kendi sabit tohumlarini enjekte etmeye devam eder; bu yardimci yalnizca
    /// <b>host</b> tarafinda, yani gercek oyunda kullanilir.
    /// </para>
    /// <para>
    /// Tohum isletim sisteminin kriptografik kaynagindan alinir. Sabit bir tohum kullanildiginda
    /// her uygulama acilisinda ayni zar dizisi gelir (ornegin once <c>5-2</c>, sonra <c>6-6</c>);
    /// bu, oyunu tekrar oynanabilir olmaktan cikarir.
    /// </para>
    /// </remarks>
    public static class DiceRandom
    {
        /// <summary>Her cagrida yeni, tahmin edilemez tohumla bir uretec dondurur.</summary>
        public static Xoshiro256StarStar Create()
        {
            return new Xoshiro256StarStar(NewSeed());
        }

        /// <summary>Isletim sisteminden 64 bit tohum uretir.</summary>
        public static ulong NewSeed()
        {
            var buffer = new byte[8];

            try
            {
                using (RandomNumberGenerator rng = RandomNumberGenerator.Create())
                {
                    rng.GetBytes(buffer);
                }

                ulong seed = 0;
                for (int i = 0; i < buffer.Length; i++)
                {
                    seed |= (ulong)buffer[i] << (i * 8);
                }

                return seed;
            }
            catch (PlatformNotSupportedException)
            {
                return FallbackSeed();
            }
            catch (CryptographicException)
            {
                return FallbackSeed();
            }
        }

        /// <summary>Kriptografik kaynak yoksa zamana ve <see cref="Guid"/>'e duser.</summary>
        private static ulong FallbackSeed()
        {
            ulong seed = (ulong)DateTime.UtcNow.Ticks;
            seed ^= (ulong)(uint)Guid.NewGuid().GetHashCode() << 32;
            seed ^= (ulong)(uint)Environment.TickCount;
            return seed;
        }
    }
}
