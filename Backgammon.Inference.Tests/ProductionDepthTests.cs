using System;
using Backgammon.Core;
using Backgammon.SelfPlay;

namespace Backgammon.Inference.Tests
{
    /// <summary>
    /// Faz 7 F7-09 - depth 2 uretimden cikarildi.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Gercek ONNX modeliyle olculen karar gecikmesi: depth 1 p95 <b>0,0902 s</b>,
    /// depth 2 p95 <b>4,4972 s</b> (medium) / <b>13,6816 s</b> (large). Butce 2 s.
    /// Maliyet ONNX <b>cagri sayisiyla</b> dogrusaldir: depth 2, 84x84 = 7 056 yaprak
    /// sans dugumu uretir. Bu yuzden uretim derinligi <b>1</b>'dir.
    /// </para>
    /// <para>
    /// Bu testler, uretim yollarindan (self-play, UI) depth 2'nin <b>sessizce</b>
    /// acilamamasini garanti eder. Depth 2 yalnizca cevrimdisi damıtma ogretmeni
    /// uretiminde mesrudur ve orada <see cref="SearchSettings.Reference"/> ile kurulur.
    /// </para>
    /// </remarks>
    [TestFixture]
    public sealed class ProductionDepthTests
    {
        /// <summary>F7-09: uretim derinligi sabiti 1'dir.</summary>
        [Test]
        public void ProductionDepthIsOne()
        {
            Assert.That(SearchSettings.ProductionDepthPly, Is.EqualTo(1),
                "F7-09: depth 2 p95 4,50 s > 2 s butcesi; uretim derinligi 1.");
        }

        /// <summary>F7-09: <see cref="SearchSettings.Default"/> uretimde kullanilabilir.</summary>
        [Test]
        public void DefaultSettingsAreProductionViable()
        {
            SearchSettings settings = SearchSettings.Default;
            Assert.That(settings.DepthPly, Is.EqualTo(SearchSettings.ProductionDepthPly));
            Assert.That(settings.IsProductionViable, Is.True);
            Assert.DoesNotThrow(() => settings.EnsureProductionViable("test"));
        }

        /// <summary>F7-09: depth 2 uretimde kullanilamaz ve acikca reddedilir.</summary>
        [Test]
        public void DepthTwoIsNotProductionViable()
        {
            SearchSettings settings = SearchSettings.Default;
            settings.DepthPly = 2;

            Assert.That(settings.IsProductionViable, Is.False);
            Assert.Throws<ArgumentOutOfRangeException>(
                () => settings.EnsureProductionViable("self-play"));
        }

        /// <summary>F7-09: depth 0 (statik) uretimde kullanilabilir.</summary>
        [Test]
        public void DepthZeroIsProductionViable()
        {
            SearchSettings settings = SearchSettings.Default;
            settings.DepthPly = 0;
            Assert.That(settings.IsProductionViable, Is.True);
        }

        /// <summary>F7-09: negatif derinlik uretimde kullanilamaz.</summary>
        [Test]
        public void NegativeDepthIsNotProductionViable()
        {
            SearchSettings settings = SearchSettings.Default;
            settings.DepthPly = -1;
            Assert.That(settings.IsProductionViable, Is.False);
        }

        /// <summary>F7-09: <see cref="SearchSettings.Reference"/> cevrimdisi derinlikleri kurar.</summary>
        [Test]
        public void ReferenceSettingsCanExceedProductionDepth()
        {
            // Referans ayarlari cevrimdisi olcum icindir; uretim kapisi bunlara uygulanmaz.
            SearchSettings reference = SearchSettings.Reference(3);
            Assert.That(reference.DepthPly, Is.EqualTo(3));
            Assert.That(reference.IsProductionViable, Is.False,
                "Reference(3) uretimde kullanilamaz olmali (kapi dogru calisiyor).");
        }

        /// <summary>F7-09: self-play varsayilan derinligi uretim sinirinda.</summary>
        [Test]
        public void SelfPlayConfigDefaultDepthIsProductionDepth()
        {
            SelfPlayConfig config = MakeConfig();
            Assert.That(config.DepthPly, Is.EqualTo(SearchSettings.ProductionDepthPly));
            Assert.DoesNotThrow(config.Validate);
        }

        /// <summary>F7-09: self-play depth 2'yi reddeder.</summary>
        [Test]
        public void SelfPlayConfigRejectsDepthTwo()
        {
            SelfPlayConfig config = MakeConfig();
            config.DepthPly = 2;
            ArgumentException error = Assert.Throws<ArgumentException>(config.Validate);
            Assert.That(error.Message, Does.Contain("F7-09"));
        }

        /// <summary>F7-09: self-play depth 1'i kabul eder.</summary>
        [Test]
        public void SelfPlayConfigAcceptsDepthOne()
        {
            SelfPlayConfig config = MakeConfig();
            config.DepthPly = 1;
            Assert.DoesNotThrow(config.Validate);
        }

        /// <summary>F7-09: self-play depth 0'i kabul eder.</summary>
        [Test]
        public void SelfPlayConfigAcceptsDepthZero()
        {
            SelfPlayConfig config = MakeConfig();
            config.DepthPly = 0;
            Assert.DoesNotThrow(config.Validate);
        }

        /// <summary>Dogrulamanin onceki adimlarini gecen asgari yapilandirma.</summary>
        private static SelfPlayConfig MakeConfig()
        {
            return new SelfPlayConfig { ModelPath = "model.onnx" };
        }
    }
}
