using System;

namespace Backgammon.Core
{
    /// <summary>Faz 3 v7 Bölüm 2: zar kümesi türü.</summary>
    public enum RollSetKind : byte
    {
        /// <summary>21 zar (6 çift + 15 çift olmayan), toplam ağırlık 36.</summary>
        Normal = 0,

        /// <summary>15 çift olmayan kombinasyon (açılış), her biri ağırlık 1, toplam 15.</summary>
        Opening = 1
    }

    /// <summary>
    /// Faz 3 v7 Bölüm 2: sabit sıralı zar tabloları. Sıra <b>sabittir ve belgelenmiştir</b> —
    /// float sonuçların referansla birebir eşleşmesi için zorunludur.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Normal sıra:</b> <c>lo = 1..6</c>, her <c>lo</c> için <c>hi = lo..6</c>. Yani
    /// (1,1),(1,2),...,(1,6),(2,2),...,(6,6) — 21 giriş.
    /// </para>
    /// <para>
    /// <b>Ağırlıklar:</b> çift (hi == lo) → 1, çift olmayan → 2. Toplam 6·1 + 15·2 = 36.
    /// Ağırlıklar <c>int</c> tutulur; tek bölme (<c>/36f</c>) en sonda yapılır.
    /// </para>
    /// <para>
    /// <b>Açılış sırası:</b> aynı sıradan çiftler çıkarılmış hâli — 15 giriş, her biri ağırlık 1.
    /// Çiftler açılış zarında yeniden atıldığı için yoktur.
    /// </para>
    /// <para>
    /// <c>RemainingWeightAfter[i]</c> = <c>i</c>'den <b>sonraki</b> zarların ağırlık toplamı
    /// (Star1 için, Bölüm 3.2).
    /// </para>
    /// </remarks>
    public static class RollSet
    {
        public const int NormalCount = 21;
        public const int OpeningCount = 15;
        public const int NormalWeightTotal = 36;
        public const int OpeningWeightTotal = 15;

        /// <summary>Normal kümede küçük zar (lo).</summary>
        public static readonly byte[] NormalDie1;

        /// <summary>Normal kümede büyük zar (hi).</summary>
        public static readonly byte[] NormalDie2;

        /// <summary>Normal kümede ağırlık (1 veya 2).</summary>
        public static readonly byte[] NormalWeight;

        /// <summary>Normal kümede <c>i</c>'den sonraki ağırlık toplamı.</summary>
        public static readonly byte[] NormalRemainingWeightAfter;

        /// <summary>Açılış kümesinde küçük zar (lo).</summary>
        public static readonly byte[] OpeningDie1;

        /// <summary>Açılış kümesinde büyük zar (hi).</summary>
        public static readonly byte[] OpeningDie2;

        /// <summary>Açılış kümesinde ağırlık (her zaman 1).</summary>
        public static readonly byte[] OpeningWeight;

        /// <summary>Açılış kümesinde <c>i</c>'den sonraki ağırlık toplamı.</summary>
        public static readonly byte[] OpeningRemainingWeightAfter;

        static RollSet()
        {
            NormalDie1 = new byte[NormalCount];
            NormalDie2 = new byte[NormalCount];
            NormalWeight = new byte[NormalCount];
            NormalRemainingWeightAfter = new byte[NormalCount];

            int index = 0;
            for (int lo = 1; lo <= 6; lo++)
            {
                for (int hi = lo; hi <= 6; hi++)
                {
                    NormalDie1[index] = (byte)lo;
                    NormalDie2[index] = (byte)hi;
                    NormalWeight[index] = (byte)(hi == lo ? 1 : 2);
                    index++;
                }
            }

            if (index != NormalCount)
            {
                throw new InvalidOperationException("RollSet.Normal tablosu " + NormalCount + " giriş olmalı: " + index);
            }

            int running = 0;
            for (int i = NormalCount - 1; i >= 0; i--)
            {
                NormalRemainingWeightAfter[i] = (byte)running;
                running += NormalWeight[i];
            }

            if (running != NormalWeightTotal)
            {
                throw new InvalidOperationException("RollSet.Normal ağırlık toplamı " + NormalWeightTotal + " olmalı: " + running);
            }

            OpeningDie1 = new byte[OpeningCount];
            OpeningDie2 = new byte[OpeningCount];
            OpeningWeight = new byte[OpeningCount];
            OpeningRemainingWeightAfter = new byte[OpeningCount];

            index = 0;
            for (int lo = 1; lo <= 6; lo++)
            {
                for (int hi = lo; hi <= 6; hi++)
                {
                    if (hi == lo)
                    {
                        continue;
                    }

                    OpeningDie1[index] = (byte)lo;
                    OpeningDie2[index] = (byte)hi;
                    OpeningWeight[index] = 1;
                    index++;
                }
            }

            if (index != OpeningCount)
            {
                throw new InvalidOperationException("RollSet.Opening tablosu " + OpeningCount + " giriş olmalı: " + index);
            }

            running = 0;
            for (int i = OpeningCount - 1; i >= 0; i--)
            {
                OpeningRemainingWeightAfter[i] = (byte)running;
                running += OpeningWeight[i];
            }

            if (running != OpeningWeightTotal)
            {
                throw new InvalidOperationException("RollSet.Opening ağırlık toplamı " + OpeningWeightTotal + " olmalı: " + running);
            }
        }

        /// <summary>Küme türüne göre giriş sayısı.</summary>
        public static int CountOf(RollSetKind kind)
        {
            return kind == RollSetKind.Opening ? OpeningCount : NormalCount;
        }

        /// <summary>Küme türüne göre ağırlık toplamı.</summary>
        public static int WeightTotalOf(RollSetKind kind)
        {
            return kind == RollSetKind.Opening ? OpeningWeightTotal : NormalWeightTotal;
        }
    }
}