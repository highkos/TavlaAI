using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 3 v7 Bölüm 4.1: afterstate değerlendiricisi. Faz 4'te sinir ağı, Faz 3'te test sahteleri.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <c>list[offset .. offset+count)</c> aralığındaki afterstate'leri <b>mover</b> perspektifinden
    /// değerlendirir. Kayıtlar <b>terminal DEĞİLDİR</b> (arama <see cref="AfterStateList.Swap"/> ile
    /// böler). <c>results[i]</c> küpsüz equity'dir; <b>kırpılmamış</b> olabilir.
    /// </para>
    /// <para>
    /// <b>Kırpma sahipliği:</b> <c>[-3,3]</c>'e kırpma <b>aramanın</b> sorumluluğundadır. Implementasyon
    /// yalnızca savunmacı <c>float.IsFinite</c> kontrolü yapar (NaN/Infinity → hata). Bu ayrım,
    /// <c>ReferenceSearch</c> ile gerçek aramanın <b>aynı kırpma sayısını</b> uygulamasını garanti eder.
    /// </para>
    /// <para>
    /// Gerçek bir ağ, Faz 2 v4 <see cref="BackgammonVectorizer.VectorizeBatch"/> fonksiyonunu kullanır.
    /// <c>VectorizeBatch</c> terminal kayıt görürse <see cref="ArgumentException"/> atar; çağıran
    /// terminal-olmayanları başa bölümlemekle yükümlüdür.
    /// </para>
    /// <para>
    /// <b>Allocation yapmamalıdır.</b> <c>offset</c> şu an yalnızca <c>0</c> olabilir
    /// (<see cref="ArgumentException"/> aksi halde); <c>VectorizeBatch</c> offset almaz.
    /// </para>
    /// </remarks>
    public interface IPositionEvaluator
    {
        /// <summary>Terminal olmayan afterstate'leri mover perspektifinden değerlendirir.</summary>
        /// <param name="list">Afterstate listesi (terminal-olmayanlar başta).</param>
        /// <param name="offset">Şu an yalnızca 0 desteklenir.</param>
        /// <param name="count">Değerlendirilecek kayıt sayısı.</param>
        /// <param name="perspective">+1 Beyaz, -1 Siyah (mover).</param>
        /// <param name="scalars">Faz 2 v4 skalerleri (6 alan).</param>
        /// <param name="results">Çıktı; <c>results.Length &gt;= count</c>. Kırpılmamış.</param>
        void EvaluateBatch(AfterStateList list, int offset, int count, int perspective,
                           in VectorizerScalars scalars, Span<float> results);

        /// <summary>Değiştiğinde arama cache'i temizlenir.</summary>
        int Version { get; }
    }

    /// <summary>
    /// Faz 3 v7 Bölüm 4.1: hamle önceliği (politika) üreticisi.
    /// </summary>
    /// <remarks>
    /// <c>priorities[i] ∈ [0,1]</c>, toplam 1'e normalize (politika ağının softmax'ı).
    /// Terminal kayıtlar bu çağrıya <b>hiç gitmez</b>. <see cref="Version"/> cache'i
    /// <b>etkilemez</b> (politika yalnızca sırayı değiştirir, <c>Q</c> değerini değil).
    /// </remarks>
    public interface IPolicyEvaluator
    {
        /// <summary>Terminal olmayan afterstate'ler için hamle önceliği üretir.</summary>
        void ScoreBatch(AfterStateList list, int offset, int count, int perspective,
                        in VectorizerScalars scalars, Span<float> priorities);

        /// <summary>Politika sürümü. Cache anahtarına <b>girmez</b>.</summary>
        int Version { get; }
    }

    /// <summary>
    /// Faz 4'te tercih edilen birleşik arayüz (tek ortak gövdeli ağ). Faz 3 her ikisini de kabul eder.
    /// </summary>
    public interface IPolicyValueEvaluator : IPositionEvaluator, IPolicyEvaluator
    {
    }

    /// <summary>
    /// Faz 3 v7 Bölüm 3.3 adım 5: opsiyonel birleşik toplu çağrı. Aynı aday kümesi için değer ve
    /// politikayı <b>tek çalıştırmayla</b> üretir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b><see cref="IPositionEvaluator"/>'DAN MİRAS ALMAZ.</b> Bir sınıfın bunu kullanabilmesi için
    /// <see cref="IPositionEvaluator"/>'ı da uygulaması gerekir (<c>Search</c> <see cref="IPositionEvaluator"/>
    /// parametresi alır). Faz 4'teki <c>OnnxPolicyValueEvaluator</c> her ikisini de uygular.
    /// </para>
    /// <para>
    /// Arama <c>evaluator is ICombinedBatchEvaluator</c> kontrolünü <b>arama başında BİR KEZ</b> yapar.
    /// Çağrı noktaları sabittir: kökte (<c>MaxCandidatesRoot &gt; 0</c> iken) bu metot; yapraklarda
    /// yalnızca <see cref="IPositionEvaluator.EvaluateBatch"/>; iç max düğümlerinde yalnızca
    /// <see cref="IPolicyEvaluator.ScoreBatch"/>.
    /// </para>
    /// <para>
    /// Sonuçlar, ayrı <c>EvaluateBatch</c> ve <c>ScoreBatch</c> çağrılarıyla <b>özdeş</b> olmak
    /// zorundadır. <c>results</c> kırpılmamıştır (kırpma aramanın işi).
    /// </para>
    /// </remarks>
    public interface ICombinedBatchEvaluator
    {
        /// <summary>Değer ve politikayı tek çalıştırmada üretir.</summary>
        void EvaluateAndScoreBatch(AfterStateList list, int offset, int count, int perspective,
                                   in VectorizerScalars scalars, Span<float> results, Span<float> priorities);
    }

    /// <summary>
    /// Faz 6 §9.4: değerlendiricinin belirli bir pozisyon için <b>kesin</b> (arama gerektirmeyen)
    /// değer verebildiğini bildiren opsiyonel arayüz.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <see cref="SearchSettings.UseBearoffCutoff"/> yalnızca bu arayüzü uygulayan değerlendiricilerle
    /// etkilidir. Arama, <see cref="IsExactFor"/> <c>true</c> dönen bir düğümde derinliği 0'a indirir;
    /// bu, sonucu <b>değiştirmez</b> çünkü kesin değer her derinlikteki arama sonucuna eşittir
    /// (saf yarışta optimal oyun zaten DB'de çözülmüştür).
    /// </para>
    /// <para>
    /// <b>Decorator kuralı:</b> bir değerlendiriciyi saran sınıf, iç değerlendirici bu arayüzü
    /// uyguluyorsa <b>aynı yanıtı iletmelidir</b>; aksi halde kesme sessizce devre dışı kalır.
    /// </para>
    /// </remarks>
    public interface IExactValueEvaluator
    {
        /// <summary>
        /// <paramref name="board"/> için arama yapmadan kesin equity verebiliyor mu?
        /// </summary>
        /// <param name="board">26 haneli tahta (<see cref="BackgammonState.board"/> biçimi).</param>
        bool IsExactFor(ReadOnlySpan<sbyte> board);
    }

    /// <summary>
    /// Faz 3'te kullanılmaz; yalnızca arayüz (Faz 4b'te doldurulacak). Bölüm 4.1.
    /// </summary>
    public interface ICubeEvaluator
    {
        bool ShouldDouble(BackgammonState state);

        bool ShouldTake(BackgammonState state);
    }

    /// <summary>Hiç küp teklif etmeyen, her teklifi kabul eden sahte değerlendirici.</summary>
    public sealed class NullCubeEvaluator : ICubeEvaluator
    {
        public static readonly NullCubeEvaluator Instance = new NullCubeEvaluator();

        public bool ShouldDouble(BackgammonState state)
        {
            return false;
        }

        public bool ShouldTake(BackgammonState state)
        {
            return true;
        }
    }

    /// <summary>
    /// Faz 4b'te küp politikası için ek arayüz (bu fazda yalnızca tanım). Bölüm 4.1.
    /// </summary>
    public interface ICubePolicyEvaluator
    {
        /// <summary>
        /// <paramref name="state"/>: küp teklifi öncesi pozisyon (<c>phase = PreRoll</c>).
        /// <paramref name="outputs"/>: <c>[double, take, pass, no-double]</c> olasılıkları (toplam 1).
        /// </summary>
        void ScoreCube(BackgammonState state, int perspective, Span<float> outputs);

        int Version { get; }
    }

    /// <summary>Tüm olasılıkları 0.25 veren sahte küp politikası.</summary>
    public sealed class NullCubePolicyEvaluator : ICubePolicyEvaluator
    {
        public static readonly NullCubePolicyEvaluator Instance = new NullCubePolicyEvaluator();

        public void ScoreCube(BackgammonState state, int perspective, Span<float> outputs)
        {
            for (int i = 0; i < outputs.Length; i++)
            {
                outputs[i] = 0.25f;
            }
        }

        public int Version
        {
            get { return 0; }
        }
    }
}