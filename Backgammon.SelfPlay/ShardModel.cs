using System;
using System.Collections.Generic;

namespace Backgammon.SelfPlay
{
    /// <summary>Faz 4 v3 Bolum 5.4: tek bir karar kaydi (bellek ici model).</summary>
    public sealed class ShardDecision
    {
        /// <summary>Hamleyi yapan taraf (+1 / -1).</summary>
        public sbyte Mover;

        /// <summary>Karar bayraklari.</summary>
        public ShardDecisionFlags Flags;

        /// <summary><c>SearchResult.RootCandidates.Length</c>.</summary>
        public ushort CandidateTotal;

        /// <summary><c>SearchResult.EvaluationScore</c>.</summary>
        public float SearchValue;

        /// <summary>Secilen afterstate vektoru (221). Terminal ise <c>null</c>.</summary>
        public float[]? ChosenVector;

        /// <summary>Loglanan adaylarin <c>Q</c> degerleri.</summary>
        public float[]? Q;

        /// <summary>Loglanan adaylarin C# <c>PolicyTarget</c> degerleri (capraz dogrulama).</summary>
        public float[]? PolicyTargetCs;

        /// <summary>Loglanan adaylarin vektorleri, <c>loggedCount * 221</c> uzunlugunda.</summary>
        public float[]? CandidateVectors;

        /// <summary>Loglanan aday sayisi.</summary>
        public int LoggedCount
        {
            get { return Q == null ? 0 : Q.Length; }
        }

        /// <summary>Secilen aday terminal mi?</summary>
        public bool ChosenIsTerminal
        {
            get { return (Flags & ShardDecisionFlags.ChosenIsTerminal) != 0; }
        }

        /// <summary>Bu karari ogrenen ag mi verdi?</summary>
        public bool IsLearner
        {
            get { return (Flags & ShardDecisionFlags.IsLearner) != 0; }
        }

        /// <summary>Yasal hamle yoktu (pas).</summary>
        public bool IsPass
        {
            get { return (Flags & ShardDecisionFlags.IsPass) != 0; }
        }

        /// <summary>
        /// Faz 7 Bolum 5.4 / Test 100: karar bir damitma ogretmeninden geldi.
        /// </summary>
        public bool IsDistilled
        {
            get { return (Flags & ShardDecisionFlags.Distilled) != 0; }
        }

        /// <summary>Faz 6 Bolum 7.5: karar <c>dup_cap</c> nedeniyle egitimden cikarildi.</summary>
        public bool IsDupCapped
        {
            get { return (Flags & ShardDecisionFlags.DupCapped) != 0; }
        }
    }

    /// <summary>Faz 4 v3 Bolum 5.4: tek bir oyun kaydi (bellek ici model).</summary>
    public sealed class ShardGame
    {
        /// <summary>Oyun kimligi.</summary>
        public ulong GameId;

        /// <summary>0 = iki taraf da ogrenen; +1/-1 = yalnizca o renk ogrenen.</summary>
        public sbyte LearnerSide;

        /// <summary>Oyun bayraklari.</summary>
        public ShardGameFlags Flags;

        /// <summary>Kup degeri (self-play'de 1).</summary>
        public int CubeValue = 1;

        /// <summary>Kararlar (sirayla).</summary>
        public List<ShardDecision> Decisions = new List<ShardDecision>();

        /// <summary>Kazanan (+1/-1); iptal edilen oyunda 0.</summary>
        public sbyte Winner;

        /// <summary>1 Single / 2 Gammon / 3 Backgammon.</summary>
        public byte ResultType;

        /// <summary>Mars carpani 1/2/3 (<c>cubeValue</c> haric).</summary>
        public byte ResultPoints;

        /// <summary>Oyun <c>max_plies</c> nedeniyle kesildi mi?</summary>
        public bool IsAborted
        {
            get { return (Flags & ShardGameFlags.Aborted) != 0; }
        }
    }
}