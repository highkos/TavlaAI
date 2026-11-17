using System;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 5.3: <see cref="GameOrchestrator.ThinkAsync"/> sonucu.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Spesifikasyondan sapma (raporlandi):</b> Bolum 5.3 <c>Task&lt;SearchResult&gt;</c> der ama
    /// <see cref="SearchResult"/> bir <c>ref struct</c>'tir; C# <c>ref struct</c>'larin
    /// <c>Task&lt;T&gt;</c> tip argumani olmasina izin vermez (CS0306). Bu yuzden ayni alanlari
    /// tasiyan, <b>normal</b> bir struct olan <see cref="SearchOutcome"/> tanimlanmistir. Alan
    /// adlari ve anlamlari <see cref="SearchResult"/> ile birebirdir; <see cref="RootCandidates"/>
    /// span yerine <b>kopyalanmis dizi</b>dir (workspace arama bitince yeniden kullanilir).
    /// </para>
    /// </remarks>
    public readonly struct SearchOutcome
    {
        /// <summary>Secilen en iyi hamle dizisi. Pas ise <c>Count == 0</c>.</summary>
        public readonly MoveSequence BestSequence;

        /// <summary>Mover equity, kupsuz, <c>[-3,3]</c>.</summary>
        public readonly float EvaluationScore;

        /// <summary>Yasal hamle yok (<c>BestSequence.Count == 0</c>).</summary>
        public readonly bool IsPass;

        /// <summary>Kok aday sayisi.</summary>
        public readonly int CandidateCount;

        /// <summary>Degerlendirici calistirma sayisi.</summary>
        public readonly long EvaluatorCalls;

        /// <summary>Politika calistirma sayisi.</summary>
        public readonly long PolicyCalls;

        /// <summary>Ziyaret edilen dugum sayisi.</summary>
        public readonly long NodesVisited;

        /// <summary>Kok adaylari (kopya; bos dizi olabilir).</summary>
        public readonly RootCandidate[] RootCandidates;

        /// <summary>
        /// Arama iptal edildi mi? <c>true</c> ise <see cref="BestSequence"/> yine de gecerlidir
        /// (Bolum 5.4: iptal edilen arama en iyi hamleyi dondurur).
        /// </summary>
        public readonly bool WasCancelled;

        public SearchOutcome(MoveSequence bestSequence, float evaluationScore, bool isPass, int candidateCount,
                             long evaluatorCalls, long policyCalls, long nodesVisited,
                             RootCandidate[] rootCandidates, bool wasCancelled)
        {
            BestSequence = bestSequence;
            EvaluationScore = evaluationScore;
            IsPass = isPass;
            CandidateCount = candidateCount;
            EvaluatorCalls = evaluatorCalls;
            PolicyCalls = policyCalls;
            NodesVisited = nodesVisited;
            RootCandidates = rootCandidates ?? Array.Empty<RootCandidate>();
            WasCancelled = wasCancelled;
        }

        public override string ToString()
        {
            return "E=" + EvaluationScore.ToString("F4") + " candidates=" + CandidateCount +
                   (IsPass ? " pass" : " seq=" + BestSequence) + (WasCancelled ? " cancelled" : string.Empty);
        }
    }
}
