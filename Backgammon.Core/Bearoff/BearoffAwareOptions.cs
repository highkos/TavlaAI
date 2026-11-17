using System;

namespace Backgammon.Core
{
    /// <summary>Faz 5 §3.5: <see cref="BearoffAwareEvaluator"/> davranış ayarları.</summary>
    public sealed class BearoffAwareOptions
    {
        /// <summary>Tüm kayıtlar bearoff ise iç değerlendirici hiç çağrılmasın. Varsayılan: <c>true</c>.</summary>
        public bool SkipInnerForPureBearoffBatches;

        /// <summary>Bearoff çözümü kapalı (A/B karşılaştırması için). Varsayılan: <c>false</c>.</summary>
        public bool DisableBearoff;

        /// <summary>Varsayılan ayarlar: <c>SkipInnerForPureBearoffBatches = true</c>, <c>DisableBearoff = false</c>.</summary>
        public static BearoffAwareOptions Default
        {
            get
            {
                return new BearoffAwareOptions
                {
                    SkipInnerForPureBearoffBatches = true,
                    DisableBearoff = false
                };
            }
        }
    }
}
