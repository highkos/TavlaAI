using System;
using System.Collections.Generic;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 6 Bolum 7.5: tekrar ayiklama (dup_cap) — oyun sonrasi deterministik gecis.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Neden oyun sonrasi?</b> Tekrar sayaci global bir durumdur; is parcaciklarina
    /// dagitilirsa <c>--threads N</c> ciktisi <c>--threads 1</c>'den farkli olur ve Test 60
    /// (determinizm) kirilir. Bu yuzden ayiklama, tum oyunlar toplandiktan sonra
    /// <see cref="ShardGame.GameId"/> sirasina gore tek gecisde yapilir.
    /// </para>
    /// <para>
    /// <b>Neden karar silinmiyor?</b> TD(lambda) zinciri <b>tum</b> kararlarin
    /// <c>chosenVector</c>'une ihtiyac duyar (bkz. <c>ml/td_lambda.py</c>); bir karari
    /// silmek zinciri koparir ve isaret cevrimini bozar. Bu yuzden dup_cap karari
    /// <b>egitimden cikarir</b>: <see cref="ShardDecisionFlags.IsLearner"/> temizlenir,
    /// <see cref="ShardDecisionFlags.DupCapped"/> isaretlenir ve pahali aday yuku
    /// (<c>Q</c>, <c>PolicyTargetCs</c>, <c>CandidateVectors</c>) atilir. Karar yalnizca
    /// zincir halkasi olarak kalir.
    /// </para>
    /// <para>
    /// <b>Parmak izi.</b> Shard v1 karar oncesi pozisyonun Zobrist hash'ini saklamaz
    /// (bicim degismez). Bunun yerine secilen afterstate vektorunun 64 bitlik FNV-1a
    /// ozeti kullanilir; deger kafasi zaten bu vektor uzerinde egitildigi icin tekrar
    /// tanimi tam olarak egitim ornegine karsilik gelir.
    /// </para>
    /// <para>
    /// <b>Acilis korumasi.</b> Ilk <see cref="DefaultOpeningPlies"/> ply'deki kararlar
    /// asla elenmez; aksi halde acilis cesitliligi (Test 62) yok olurdu.
    /// </para>
    /// </remarks>
    public static class DupCapFilter
    {
        /// <summary>Varsayilan tekrar siniri (Faz 6 Bolum 7.5).</summary>
        public const int DefaultCap = 3;

        /// <summary>Dup_cap'ten muaf tutulan ilk ply sayisi (acilis cesitliligi).</summary>
        public const int DefaultOpeningPlies = 10;

        private const ulong FnvOffsetBasis = 0xCBF29CE484222325UL;
        private const ulong FnvPrime = 0x100000001B3UL;

        /// <summary>
        /// Oyunlari yerinde ayiklar ve istatistik dondurur.
        /// </summary>
        /// <param name="games">Oyunlar; <see cref="ShardGame.GameId"/> sirasina gore islenir.</param>
        /// <param name="cap">Ayni parmak izinin en fazla kac kez tutulacagi (0 = kapali).</param>
        /// <param name="openingPlies">Muaf ilk ply sayisi.</param>
        public static DupCapStats Apply(
            IReadOnlyList<ShardGame> games,
            int cap = DefaultCap,
            int openingPlies = DefaultOpeningPlies)
        {
            if (games == null)
            {
                throw new ArgumentNullException(nameof(games));
            }

            if (cap < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(cap), "cap negatif olamaz.");
            }

            if (openingPlies < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(openingPlies), "openingPlies negatif olamaz.");
            }

            var stats = new DupCapStats { Cap = cap, OpeningPlies = openingPlies };
            if (cap == 0)
            {
                return stats;
            }

            var order = new int[games.Count];
            for (int i = 0; i < order.Length; i++)
            {
                order[i] = i;
            }

            Array.Sort(order, (a, b) => games[a].GameId.CompareTo(games[b].GameId));

            var seen = new Dictionary<ulong, int>();
            for (int oi = 0; oi < order.Length; oi++)
            {
                ShardGame game = games[order[oi]];
                for (int d = 0; d < game.Decisions.Count; d++)
                {
                    ShardDecision decision = game.Decisions[d];
                    if (!decision.IsLearner || decision.ChosenVector == null)
                    {
                        continue;
                    }

                    if (d < openingPlies)
                    {
                        stats.OpeningExempt++;
                        continue;
                    }

                    ulong key = Fingerprint(decision.ChosenVector);
                    seen.TryGetValue(key, out int count);
                    if (count >= cap)
                    {
                        decision.Flags &= ~ShardDecisionFlags.IsLearner;
                        decision.Flags |= ShardDecisionFlags.DupCapped;
                        decision.Q = null;
                        decision.PolicyTargetCs = null;
                        decision.CandidateVectors = null;
                        stats.Capped++;
                        continue;
                    }

                    seen[key] = count + 1;
                    stats.Kept++;
                }
            }

            stats.DistinctKeys = seen.Count;
            return stats;
        }

        /// <summary>Afterstate vektorunun 64 bitlik FNV-1a ozeti (float32 baytlari uzerinden).</summary>
        public static ulong Fingerprint(float[] vector)
        {
            if (vector == null)
            {
                throw new ArgumentNullException(nameof(vector));
            }

            ulong h = FnvOffsetBasis;
            for (int i = 0; i < vector.Length; i++)
            {
                uint bits = BitConverter.SingleToUInt32Bits(vector[i]);
                for (int b = 0; b < 4; b++)
                {
                    h ^= (byte)(bits >> (b * 8));
                    h *= FnvPrime;
                }
            }

            return h;
        }
    }

    /// <summary><see cref="DupCapFilter.Apply"/> sonucu.</summary>
    public struct DupCapStats
    {
        /// <summary>Uygulanan sinir (0 = kapali).</summary>
        public int Cap;

        /// <summary>Muaf tutulan ilk ply sayisi.</summary>
        public int OpeningPlies;

        /// <summary>Egitimden cikarilan karar sayisi.</summary>
        public int Capped;

        /// <summary>Sinir icinde kalan karar sayisi.</summary>
        public int Kept;

        /// <summary>Acilis muafiyetiyle korunan karar sayisi.</summary>
        public int OpeningExempt;

        /// <summary>Gorulen farkli parmak izi sayisi.</summary>
        public int DistinctKeys;
    }
}
