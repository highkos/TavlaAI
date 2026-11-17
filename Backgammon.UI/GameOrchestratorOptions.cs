using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 5.3: <see cref="GameOrchestrator"/> yapilandirmasi.
    /// </summary>
    /// <remarks>
    /// <b>Zorunlu:</b> <see cref="Evaluator"/> ve <see cref="Random"/>. Digerleri <c>null</c> olabilir;
    /// <c>null</c> olduklarinda ilgili dekorator zincire <b>girmez</b> (Bolum 2.1: money game'de
    /// <see cref="MatchAwareEvaluator"/> zincire girmez).
    /// </remarks>
    public sealed class GameOrchestratorOptions
    {
        /// <summary>Zorunlu: temel politika/deger degerlendiricisi.</summary>
        public IPolicyValueEvaluator Evaluator;

        /// <summary>Bearoff veritabani; <c>null</c> ise bearoff dekoratoru eklenmez.</summary>
        public BearoffDatabase Bearoff;

        /// <summary>Mac equity tablosu; <c>null</c> ise varsayilan (gomulu) tablo kullanilir.</summary>
        public MatchEquityTable Met;

        /// <summary>Sonuc dagilimi degerlendiricisi; <c>null</c> ise sezgisel uygulama kullanilir.</summary>
        public IOutcomeDistributionEvaluator Distribution;

        /// <summary>Arama ayarlari.</summary>
        public SearchSettings SearchSettings;

        /// <summary>Motor ayarlari.</summary>
        public EngineSettings EngineSettings;

        /// <summary>Zorunlu: determinizm icin enjekte edilen rastgelelik.</summary>
        public IRandom Random;

        /// <summary>Guvenlik siniri: en fazla kac chance katmani. <c>0</c> ise <see cref="SearchWorkspace.MaxSupportedPly"/>.</summary>
        public int MaxPlies;

        /// <summary>Dogrular ve varsayilanlari uygular.</summary>
        public void Validate()
        {
            if (Evaluator == null)
            {
                throw new System.ArgumentNullException(nameof(Evaluator));
            }

            if (Random == null)
            {
                throw new System.ArgumentNullException(nameof(Random));
            }

            if (MaxPlies < 0 || MaxPlies > SearchWorkspace.MaxSupportedPly)
            {
                throw new System.ArgumentOutOfRangeException(nameof(MaxPlies));
            }

            if (SearchSettings.PolicyTemperature <= 0f)
            {
                throw new System.ArgumentOutOfRangeException(nameof(SearchSettings));
            }
        }
    }
}
