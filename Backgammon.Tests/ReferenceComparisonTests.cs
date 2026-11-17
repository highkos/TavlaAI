using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>
    /// Bölüm 8 madde 5: perft benzeri referans karşılaştırması.
    /// </summary>
    /// <remarks>
    /// gnubg bu makinede kurulu olmadığı için (bkz. ASSUMPTIONS.md E-01) referans veri
    /// <c>tools/reference_gen.py</c> içindeki BAĞIMSIZ Python uygulamasıyla üretilmiştir.
    /// Veri <c>ReferenceData/reference_positions.json</c> dosyasındadır ve elle düzenlenmemiştir.
    /// </remarks>
    [TestFixture]
    public class ReferenceComparisonTests
    {
        private const string RelativePath = "ReferenceData/reference_positions.json";

        private static JsonDocument LoadDocument()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, RelativePath);

            Assert.That(File.Exists(path), Is.True, "Referans veri dosyası bulunamadı: " + path);

            return JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
        }

        [Test]
        public void ReferenceData_HasAtLeastFiftyCases()
        {
            using (JsonDocument doc = LoadDocument())
            {
                int count = doc.RootElement.GetProperty("cases").GetArrayLength();
                TestContext.Progress.WriteLine("Referans vaka sayısı: " + count + ".");
                Assert.That(count, Is.GreaterThanOrEqualTo(50), "Bölüm 8 madde 5 en az 50 pozisyon ister.");
            }
        }

        [Test]
        public void Generate_MatchesIndependentReference()
        {
            using (JsonDocument doc = LoadDocument())
            {
                JsonElement cases = doc.RootElement.GetProperty("cases");
                var moves = new MoveList();
                var afterStates = new AfterStateList();
                var es = EngineSettings.Default;
                var s = new BackgammonState();

                int compared = 0;
                int totalAfterStates = 0;

                foreach (JsonElement c in cases.EnumerateArray())
                {
                    string name = c.GetProperty("name").GetString() ?? "?";

                    LoadCase(s, c);

                    LegalMoveGenerator.GenerateAllLegalMoves(s, moves);
                    int expectedMax = c.GetProperty("maxSteps").GetInt32();

                    int actualMax = moves.Count == 0 ? 0 : moves[0].Count;
                    Assert.That(actualMax, Is.EqualTo(expectedMax),
                        name + ": maksimum adım sayısı uyuşmuyor.");

                    for (int i = 1; i < moves.Count; i++)
                    {
                        Assert.That(moves[i].Count, Is.EqualTo(actualMax),
                            name + ": tüm diziler aynı uzunlukta olmalı.");
                    }

                    LegalMoveGenerator.GenerateAfterStates(s, es, afterStates);

                    Assert.That(afterStates.Count, Is.EqualTo(moves.Count),
                        name + ": GenerateAfterStates ve GenerateAllLegalMoves sayıları farklı.");

                    var expected = new HashSet<string>(StringComparer.Ordinal);
                    foreach (JsonElement a in c.GetProperty("afterStates").EnumerateArray())
                    {
                        expected.Add(KeyOf(a.GetProperty("board"), a.GetProperty("whiteOff").GetInt32(),
                            a.GetProperty("blackOff").GetInt32()));
                    }

                    var actual = new HashSet<string>(StringComparer.Ordinal);
                    for (int i = 0; i < afterStates.Count; i++)
                    {
                        actual.Add(KeyOf(afterStates.BoardOf(i), afterStates.WhiteBorneOff[i],
                            afterStates.BlackBorneOff[i]));
                    }

                    Assert.That(actual.Count, Is.EqualTo(expected.Count),
                        name + ": sonuç pozisyonu sayısı uyuşmuyor (beklenen " + expected.Count +
                        ", üretilen " + actual.Count + ").");

                    foreach (string key in expected)
                    {
                        Assert.That(actual.Contains(key), Is.True,
                            name + ": referansta olup motorda olmayan sonuç pozisyonu: " + key);
                    }

                    foreach (string key in actual)
                    {
                        Assert.That(expected.Contains(key), Is.True,
                            name + ": motorda olup referansta olmayan sonuç pozisyonu: " + key);
                    }

                    compared++;
                    totalAfterStates += expected.Count;
                }

                TestContext.Progress.WriteLine(
                    "Referans karşılaştırması: " + compared + " pozisyon, " + totalAfterStates + " sonuç pozisyonu eşleşti.");
                Assert.That(compared, Is.GreaterThanOrEqualTo(50));
            }
        }

        private static void LoadCase(BackgammonState s, JsonElement c)
        {
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            int index = 0;
            foreach (JsonElement v in c.GetProperty("board").EnumerateArray())
            {
                s.board[index++] = (sbyte)v.GetInt32();
            }

            s.whiteBorneOff = (byte)c.GetProperty("whiteOff").GetInt32();
            s.blackBorneOff = (byte)c.GetProperty("blackOff").GetInt32();
            s.turn = (sbyte)c.GetProperty("turn").GetInt32();

            s.cubeValue = 1;
            s.cubeOwner = 0;
            s.matchLength = 0;
            s.whiteScore = 0;
            s.blackScore = 0;
            s.isCrawfordGame = false;
            s.crawfordPlayed = false;
            s.cubePassed = false;
            s.phase = GamePhase.Moving;

            s.hash = BackgammonEngine.ComputeZobristHash(s);

            JsonElement dice = c.GetProperty("dice");
            BackgammonEngine.SetDice(s, dice[0].GetInt32(), dice[1].GetInt32());
        }

        private static string KeyOf(ReadOnlySpan<sbyte> board, int whiteOff, int blackOff)
        {
            var sb = new StringBuilder(96);

            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                if (i > 0)
                {
                    sb.Append(',');
                }

                sb.Append(board[i]);
            }

            sb.Append('|').Append(whiteOff).Append('|').Append(blackOff);
            return sb.ToString();
        }

        private static string KeyOf(JsonElement board, int whiteOff, int blackOff)
        {
            var sb = new StringBuilder(96);
            bool first = true;

            foreach (JsonElement v in board.EnumerateArray())
            {
                if (!first)
                {
                    sb.Append(',');
                }

                first = false;
                sb.Append(v.GetInt32());
            }

            sb.Append('|').Append(whiteOff).Append('|').Append(blackOff);
            return sb.ToString();
        }
    }
}
