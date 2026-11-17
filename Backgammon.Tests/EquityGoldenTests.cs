using System;
using System.IO;
using System.Text.Json;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 7 Bölüm 9.9: C#/Python equity paritesi (Test 122, 123).
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>Test 122 — <c>EquityFormula_SharedGolden</c>.</b> C# ve Python test paketleri
    /// <b>aynı</b> <c>equity_golden.json</c> dosyasını okur ve her kayıtta <c>equityHex</c>
    /// ile <b>bit düzeyinde</b> eşleşme arar. Kayan nokta toleransı <b>kabul edilmez</b>;
    /// fark varsa iki taraf farklı formül kullanıyor demektir.
    /// </para>
    /// <para>
    /// <b>Test 123 — <c>EquityGolden_NotStale</c>.</b> Altın dosyanın <c>equityWeights</c>
    /// alanı <see cref="OutcomeDistribution"/> ile aynı olmalı, <c>generatedBy</c> Faz 7'yi
    /// göstermeli ve kayıt sayısı 300 olmalı. Amaç: formül değişip altın dosya yeniden
    /// üretilmezse test <b>kırmızı</b> yansın.
    /// </para>
    /// </remarks>
    [TestFixture]
    public class EquityGoldenTests
    {
        private static string GoldenPath()
        {
            return Path.Combine(AppContext.BaseDirectory, EquityGoldenData.RelativePath);
        }

        private static JsonDocument LoadGolden()
        {
            string path = GoldenPath();
            Assert.That(File.Exists(path), Is.True,
                "Altın dosya yok: " + path + " - EquityGoldenData.Write ile üretin.");
            return JsonDocument.Parse(File.ReadAllText(path));
        }

        // ==================================================================
        // Test 122
        // ==================================================================

        [Test]
        public void EquityFormula_SharedGolden()
        {
            using (JsonDocument doc = LoadGolden())
            {
                JsonElement root = doc.RootElement;
                JsonElement records = root.GetProperty("records");
                Assert.That(records.GetArrayLength(), Is.EqualTo(EquityGoldenData.DefaultRecordCount));

                int index = 0;
                foreach (JsonElement rec in records.EnumerateArray())
                {
                    JsonElement hex = rec.GetProperty("exclusiveHex");
                    var p = new float[6];
                    for (int k = 0; k < 6; k++)
                    {
                        p[k] = EquityGoldenData.FloatFromHex(hex[k].GetString()!);
                    }

                    OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                        p[0], p[1], p[2], p[3], p[4], p[5]);

                    string label = rec.GetProperty("group").GetString() + "/" + index;

                    JsonElement cumHex = rec.GetProperty("cumulativeHex");
                    Assert.That(EquityGoldenData.HexOfFloat(d.Win),
                        Is.EqualTo(cumHex.GetProperty("win").GetString()), label + " win");
                    Assert.That(EquityGoldenData.HexOfFloat(d.WinGammon),
                        Is.EqualTo(cumHex.GetProperty("winGammon").GetString()), label + " winGammon");
                    Assert.That(EquityGoldenData.HexOfFloat(d.WinBackgammon),
                        Is.EqualTo(cumHex.GetProperty("winBackgammon").GetString()), label + " winBackgammon");
                    Assert.That(EquityGoldenData.HexOfFloat(d.LoseGammon),
                        Is.EqualTo(cumHex.GetProperty("loseGammon").GetString()), label + " loseGammon");
                    Assert.That(EquityGoldenData.HexOfFloat(d.LoseBackgammon),
                        Is.EqualTo(cumHex.GetProperty("loseBackgammon").GetString()), label + " loseBackgammon");

                    Assert.That(EquityGoldenData.HexOfDouble(d.Equity),
                        Is.EqualTo(rec.GetProperty("equityHex").GetString()), label + " equity");
                    Assert.That(d.IsValid, Is.EqualTo(rec.GetProperty("isValid").GetBoolean()), label + " isValid");

                    index++;
                }
            }
        }

        [Test]
        public void EquityFormula_UnitVectorsGiveExactWeights()
        {
            using (JsonDocument doc = LoadGolden())
            {
                int seen = 0;
                foreach (JsonElement rec in doc.RootElement.GetProperty("records").EnumerateArray())
                {
                    if (rec.GetProperty("group").GetString() != "unit")
                    {
                        continue;
                    }

                    int i = rec.GetProperty("index").GetInt32();
                    double equity = EquityGoldenData.DoubleFromHex(rec.GetProperty("equityHex").GetString()!);
                    Assert.That(equity, Is.EqualTo(EquityGoldenData.EquityWeights[i]), "birim vektor " + i);
                    seen++;
                }

                Assert.That(seen, Is.EqualTo(EquityGoldenData.UnitCount));
            }
        }

        [Test]
        public void EquityFormula_InvalidRecordsAreInvalid()
        {
            using (JsonDocument doc = LoadGolden())
            {
                int seen = 0;
                foreach (JsonElement rec in doc.RootElement.GetProperty("records").EnumerateArray())
                {
                    if (rec.GetProperty("group").GetString() != "invalid")
                    {
                        continue;
                    }

                    Assert.That(rec.GetProperty("isValid").GetBoolean(), Is.False, "gecersiz kayit");
                    Assert.That(rec.GetProperty("equityHex").GetString(),
                        Is.EqualTo("0000000000000000"), "gecersiz kayitta equity 0 olmali");
                    seen++;
                }

                Assert.That(seen, Is.EqualTo(EquityGoldenData.InvalidCount));
            }
        }

        // ==================================================================
        // Test 123
        // ==================================================================

        [Test]
        public void EquityGolden_NotStale()
        {
            using (JsonDocument doc = LoadGolden())
            {
                JsonElement root = doc.RootElement;

                Assert.That(root.GetProperty("schemaVersion").GetInt32(),
                    Is.EqualTo(EquityGoldenData.SchemaVersion));

                string generatedBy = root.GetProperty("generatedBy").GetString()!;
                Assert.That(generatedBy, Does.Contain("Faz 7"),
                    "altin dosya Faz 7 tarafindan uretilmemis: " + generatedBy);

                Assert.That(root.GetProperty("recordCount").GetInt32(),
                    Is.EqualTo(EquityGoldenData.DefaultRecordCount));
                Assert.That(root.GetProperty("records").GetArrayLength(),
                    Is.EqualTo(EquityGoldenData.DefaultRecordCount));

                JsonElement order = root.GetProperty("probOrder");
                Assert.That(order.GetArrayLength(), Is.EqualTo(EquityGoldenData.ProbOrder.Length));
                for (int i = 0; i < EquityGoldenData.ProbOrder.Length; i++)
                {
                    Assert.That(order[i].GetString(), Is.EqualTo(EquityGoldenData.ProbOrder[i]), "probOrder " + i);
                }

                JsonElement weights = root.GetProperty("equityWeights");
                Assert.That(weights.GetArrayLength(), Is.EqualTo(EquityGoldenData.EquityWeights.Length));
                for (int i = 0; i < EquityGoldenData.EquityWeights.Length; i++)
                {
                    Assert.That(weights[i].GetDouble(), Is.EqualTo(EquityGoldenData.EquityWeights[i]),
                        "equityWeights " + i);
                }
            }
        }

        [Test]
        public void EquityGolden_GroupCountsMatchConstants()
        {
            using (JsonDocument doc = LoadGolden())
            {
                int unit = 0, random = 0, boundary = 0, unnormalized = 0, invalid = 0;
                foreach (JsonElement rec in doc.RootElement.GetProperty("records").EnumerateArray())
                {
                    switch (rec.GetProperty("group").GetString())
                    {
                        case "unit": unit++; break;
                        case "random": random++; break;
                        case "boundary": boundary++; break;
                        case "unnormalized": unnormalized++; break;
                        case "invalid": invalid++; break;
                        default: Assert.Fail("bilinmeyen grup"); break;
                    }
                }

                Assert.That(unit, Is.EqualTo(EquityGoldenData.UnitCount));
                Assert.That(random, Is.EqualTo(EquityGoldenData.RandomCount));
                Assert.That(boundary, Is.EqualTo(EquityGoldenData.BoundaryCount));
                Assert.That(unnormalized, Is.EqualTo(EquityGoldenData.UnnormalizedCount));
                Assert.That(invalid, Is.EqualTo(EquityGoldenData.InvalidCount));
            }
        }

        // ==================================================================
        // flip involüsyonu (grup 6)
        // ==================================================================

        /// <summary>
        /// F7-05: <c>Flip()</c> dışlayıcı sınıflar üzerinden <c>FromProbabilities</c> ile
        /// yeniden kurar; bu yüzden <c>flip(d).Equity == -d.Equity</c> ve
        /// <c>flip(flip(d)) == d</c> <b>bit düzeyinde değil</b>, float32 yuvarlaması
        /// mertebesinde (ölçülen üst sınır 1,4e-7) sağlanır. Tolerans bu yüzden 1e-6'dır;
        /// backgammon equity çözünürlüğünün (1e-4) çok altındadır.
        /// </summary>
        private const double FlipTolerance = 1e-6;

        [Test]
        public void EquityFlip_IsInvolution()
        {
            using (JsonDocument doc = LoadGolden())
            {
                int checkedCount = 0;
                double maxEquityDeviation = 0.0;
                double maxFieldDeviation = 0.0;

                foreach (JsonElement rec in doc.RootElement.GetProperty("records").EnumerateArray())
                {
                    if (!rec.GetProperty("isValid").GetBoolean())
                    {
                        continue;
                    }

                    JsonElement hex = rec.GetProperty("exclusiveHex");
                    var p = new float[6];
                    for (int k = 0; k < 6; k++)
                    {
                        p[k] = EquityGoldenData.FloatFromHex(hex[k].GetString()!);
                    }

                    OutcomeDistribution d = OutcomeDistribution.FromProbabilities(
                        p[0], p[1], p[2], p[3], p[4], p[5]);
                    OutcomeDistribution flipped = d.Flip();
                    OutcomeDistribution twice = flipped.Flip();

                    Assert.That(flipped.IsValid, Is.True, "flip gecersiz oldu");
                    Assert.That(twice.IsValid, Is.True, "flip(flip) gecersiz oldu");

                    double equityDeviation = Math.Abs(flipped.Equity + d.Equity);
                    maxEquityDeviation = Math.Max(maxEquityDeviation, equityDeviation);
                    Assert.That(equityDeviation, Is.LessThanOrEqualTo(FlipTolerance),
                        "flip equity isareti (kayit " + rec.GetProperty("index").GetInt32() + ")");

                    maxFieldDeviation = Math.Max(maxFieldDeviation,
                        Math.Abs((double)twice.Win - d.Win));
                    maxFieldDeviation = Math.Max(maxFieldDeviation,
                        Math.Abs((double)twice.WinGammon - d.WinGammon));
                    maxFieldDeviation = Math.Max(maxFieldDeviation,
                        Math.Abs((double)twice.WinBackgammon - d.WinBackgammon));
                    maxFieldDeviation = Math.Max(maxFieldDeviation,
                        Math.Abs((double)twice.LoseGammon - d.LoseGammon));
                    maxFieldDeviation = Math.Max(maxFieldDeviation,
                        Math.Abs((double)twice.LoseBackgammon - d.LoseBackgammon));

                    Assert.That(Math.Abs((double)twice.Win - d.Win),
                        Is.LessThanOrEqualTo(FlipTolerance), "flip(flip) win");
                    Assert.That(Math.Abs((double)twice.WinGammon - d.WinGammon),
                        Is.LessThanOrEqualTo(FlipTolerance), "flip(flip) winGammon");
                    Assert.That(Math.Abs((double)twice.WinBackgammon - d.WinBackgammon),
                        Is.LessThanOrEqualTo(FlipTolerance), "flip(flip) winBackgammon");
                    Assert.That(Math.Abs((double)twice.LoseGammon - d.LoseGammon),
                        Is.LessThanOrEqualTo(FlipTolerance), "flip(flip) loseGammon");
                    Assert.That(Math.Abs((double)twice.LoseBackgammon - d.LoseBackgammon),
                        Is.LessThanOrEqualTo(FlipTolerance), "flip(flip) loseBackgammon");

                    checkedCount++;
                }

                Assert.That(checkedCount, Is.GreaterThan(0));
                Assert.That(maxEquityDeviation, Is.LessThanOrEqualTo(FlipTolerance),
                    "olculen en buyuk equity sapmasi");
                Assert.That(maxFieldDeviation, Is.LessThanOrEqualTo(FlipTolerance),
                    "olculen en buyuk alan sapmasi");
            }
        }

        [Test]
        public void EquityFlip_InvalidStaysInvalid()
        {
            OutcomeDistribution flipped = OutcomeDistribution.Invalid.Flip();
            Assert.That(flipped.IsValid, Is.False);
            Assert.That(flipped.Equity, Is.EqualTo(0.0));
        }

        // ==================================================================
        // Üretici
        // ==================================================================

        [Test]
        [Explicit("Altın JSON dosyasını yeniden üretir.")]
        public void GenerateEquityGolden()
        {
            string path = GoldenPath();
            EquityGoldenData.Write(path, EquityGoldenData.DefaultSeed);
            TestContext.Progress.WriteLine("Yazıldı: " + path);
        }
    }
}
