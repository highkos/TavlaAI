using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 3 v7 Bölüm 4.2: kök adayı. <see cref="SearchResult.RootCandidates"/> içinde döner.
    /// </summary>
    public readonly struct RootCandidate
    {
        /// <summary>Bu adaya götüren kanonik hamle dizisi (pas için <c>Count == 0</c>).</summary>
        public readonly MoveSequence Sequence;

        /// <summary>
        /// Tam değer (<see cref="Kind"/> 0 veya 1) ya da statik değer (<see cref="Kind"/> 2).
        /// Mover perspektifinden, küpsüz equity, <c>[-3,3]</c>.
        /// </summary>
        public readonly float Score;

        /// <summary>Kök politika hedefi π. <see cref="Kind"/> 2 ise 0.</summary>
        public readonly float PolicyTarget;

        /// <summary>0 = terminal, 1 = derin arandı (tam değer), 2 = yalnızca politika/statik (kısıt dışı).</summary>
        public readonly byte Kind;

        public RootCandidate(MoveSequence sequence, float score, float policyTarget, byte kind)
        {
            Sequence = sequence;
            Score = score;
            PolicyTarget = policyTarget;
            Kind = kind;
        }

        public override string ToString()
        {
            return "kind=" + Kind + " score=" + Score.ToString("F6") + " pi=" + PolicyTarget.ToString("F6") +
                   " seq=" + Sequence;
        }
    }

    /// <summary>
    /// Faz 3 v7 Bölüm 4.2: arama sonucu.
    /// </summary>
    /// <remarks>
    /// <b><c>ref struct</c> olmasının nedeni:</b> <see cref="RootCandidates"/> ve
    /// <see cref="RootPolicyTarget"/> <see cref="ReadOnlySpan{T}"/> döndürür; <c>ref struct</c>
    /// alanları yalnızca başka bir <c>ref struct</c> içinde tutulabilir. Bu aynı zamanda
    /// sıfır-allocation hedefiyle uyumludur (span'ler workspace'e işaret eder, kopya yoktur).
    /// </remarks>
    public ref struct SearchResult
    {
        /// <summary>Seçilen en iyi hamle dizisi. Pas ise <c>Count == 0</c>.</summary>
        public MoveSequence BestSequence;

        /// <summary>Mover equity, küpsüz, <c>[-3,3]</c>.</summary>
        public float EvaluationScore;

        /// <summary>Yasal hamle yok (<c>BestSequence.Count == 0</c>).</summary>
        public bool IsPass;

        /// <summary>Kök aday sayısı.</summary>
        public int CandidateCount;

        /// <summary>Değerlendirici çalıştırma sayısı (birleşik çağrı 1 sayılır).</summary>
        public long EvaluatorCalls;

        /// <summary>Politika çalıştırma sayısı.</summary>
        public long PolicyCalls;

        /// <summary>Ziyaret edilen düğüm sayısı.</summary>
        public long NodesVisited;

        /// <summary>Faz 6 §9.3: transposition table kesin isabet sayısı.</summary>
        public long TranspositionHits;

        /// <summary>Faz 6 §9.3: transposition table yazma sayısı.</summary>
        public long TranspositionStores;

        /// <summary>
        /// Kök adayları (workspace'ten). <see cref="SearchSettings.ExactRootScores"/> ile
        /// ilişkisiz olarak doldurulur; sıra deterministiktir.
        /// </summary>
        public ReadOnlySpan<RootCandidate> RootCandidates;

        /// <summary>
        /// Kök politika hedefi (workspace'ten, <see cref="RootCandidates"/> ile aynı indeks).
        /// <see cref="SearchSettings.ExactRootScores"/> <c>false</c> iken <b>boş</b>
        /// (<c>Length == 0</c>; <c>null</c> değil — <see cref="ReadOnlySpan{T}"/> null olamaz).
        /// </summary>
        public ReadOnlySpan<float> RootPolicyTarget;

        /// <summary>
        /// Faz 7 §5.4 / Test 99: damıtmanın <b>değer hedefi</b> — seçilen en iyi afterstate'in
        /// 6 çıktılı sonuç dağılımı.
        /// </summary>
        /// <remarks>
        /// Yalnızca <see cref="SearchSettings.DistillMode"/> <c>true</c> <b>ve</b> değerlendirici
        /// <see cref="IOutcomeDistributionEvaluator"/> uyguluyorsa doldurulur; aksi halde
        /// <c>null</c>. Pas (terminal) durumunda da <c>null</c>'dır: terminal sonuç dağılımı
        /// ağdan değil <b>oyun kuralından</b> gelir.
        /// </remarks>
        public OutcomeDistribution? RootValue;
    }
}