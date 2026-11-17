using System;
using System.Collections.Generic;
using System.IO;
using Backgammon.Core;
using Backgammon.SelfPlay;
using NUnit.Framework;

namespace Backgammon.Tests
{
    /// <summary>
    /// Faz 7 §5.4 / Test 100: damıtma shard'ı v1 uyumludur; <c>DEC_DISTILLED = 16</c>
    /// bilinmeyen bayrak olarak yok sayılır.
    /// </summary>
    [TestFixture]
    public sealed class ShardDistillFlagTests
    {
        private const int VectorSize = 221;

        private static ShardHeader Header()
        {
            return ShardHeader.Create(featureVersion: 1, modelVersion: 1, logTopCandidates: 0);
        }

        private static float[] Vector(float seed)
        {
            var v = new float[VectorSize];
            for (int i = 0; i < v.Length; i++)
            {
                v[i] = seed + i * 1e-3f;
            }

            return v;
        }

        private static float[] Concat(float[] a, float[] b)
        {
            var v = new float[a.Length + b.Length];
            Array.Copy(a, 0, v, 0, a.Length);
            Array.Copy(b, 0, v, a.Length, b.Length);
            return v;
        }

        private static ShardGame Game(ShardDecisionFlags flags)
        {
            var game = new ShardGame
            {
                GameId = 42UL,
                LearnerSide = 1,
                Flags = ShardGameFlags.None,
                CubeValue = 1,
                Winner = 1,
                ResultType = 1,
                ResultPoints = 1
            };
            game.Decisions.Add(new ShardDecision
            {
                Mover = 1,
                Flags = flags,
                CandidateTotal = 2,
                SearchValue = 0.25f,
                ChosenVector = Vector(0.5f),
                Q = new[] { 0.25f, 0.1f },
                PolicyTargetCs = new[] { 0.7f, 0.3f },
                CandidateVectors = Concat(Vector(0.5f), Vector(0.6f))
            });
            return game;
        }

        private static List<ShardGame> RoundTrip(ShardDecisionFlags flags, out ShardHeader header)
        {
            string path = Path.Combine(Path.GetTempPath(), "f7_distill_" + Guid.NewGuid().ToString("N") + ".bgsp");
            try
            {
                ShardWriter.WriteFile(path, Header(), new[] { Game(flags) }, gzip: false);
                (ShardHeader h, List<ShardGame> games) = ShardReader.ReadFile(path, gzip: false);
                header = h;
                return games;
            }
            finally
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
        }

        [Test]
        public void Test100_DistilledFlagIsSixteen()
        {
            Assert.That((int)ShardDecisionFlags.Distilled, Is.EqualTo(16));
        }

        [Test]
        public void Test100_DistilledFlagDoesNotCollide()
        {
            int all = (int)ShardDecisionFlags.IsPass
                      | (int)ShardDecisionFlags.IsLearner
                      | (int)ShardDecisionFlags.ChosenIsTerminal
                      | (int)ShardDecisionFlags.DupCapped
                      | (int)ShardDecisionFlags.Distilled;
            Assert.That(all, Is.EqualTo(31), "beş bayrak 0..4 bitlerini kullanmalı");
        }

        [Test]
        public void Test100_DistilledFlagSurvivesRoundTrip()
        {
            List<ShardGame> games = RoundTrip(
                ShardDecisionFlags.IsLearner | ShardDecisionFlags.Distilled, out ShardHeader header);

            Assert.That(header.FormatVersion, Is.EqualTo(1u), "biçim sürümü değişmemeli");
            Assert.That(games.Count, Is.EqualTo(1));
            ShardDecision d = games[0].Decisions[0];
            Assert.That(d.IsDistilled, Is.True);
            Assert.That(d.IsLearner, Is.True);
            Assert.That(d.IsPass, Is.False);
            Assert.That(d.IsDupCapped, Is.False);
        }

        [Test]
        public void Test100_UnknownFlagIsIgnoredByKnownAccessors()
        {
            // Yalnızca 16 yazılmış bir karar: bilinen dört erişimcinin hepsi false olmalı.
            List<ShardGame> games = RoundTrip(ShardDecisionFlags.Distilled, out _);
            ShardDecision d = games[0].Decisions[0];

            Assert.That(d.IsPass, Is.False);
            Assert.That(d.IsLearner, Is.False);
            Assert.That(d.ChosenIsTerminal, Is.False);
            Assert.That(d.IsDupCapped, Is.False);
            Assert.That(d.IsDistilled, Is.True);
        }

        [Test]
        public void Test100_NonDistilledShardIsUnchanged()
        {
            List<ShardGame> games = RoundTrip(ShardDecisionFlags.IsLearner, out _);
            ShardDecision d = games[0].Decisions[0];

            Assert.That(d.IsDistilled, Is.False);
            Assert.That(d.IsLearner, Is.True);
        }

        [Test]
        public void Test100_DistilledShardKeepsQAndSearchValue()
        {
            List<ShardGame> games = RoundTrip(
                ShardDecisionFlags.IsLearner | ShardDecisionFlags.Distilled, out _);
            ShardDecision d = games[0].Decisions[0];

            Assert.That(d.Q, Is.Not.Null);
            Assert.That(d.Q.Length, Is.EqualTo(2));
            Assert.That(d.Q[0], Is.EqualTo(0.25f));
            Assert.That(d.SearchValue, Is.EqualTo(0.25f));
            Assert.That(d.LoggedCount, Is.EqualTo(2));
        }

        [Test]
        public void Test100_DistilledShardKeepsCandidateVectors()
        {
            List<ShardGame> games = RoundTrip(
                ShardDecisionFlags.IsLearner | ShardDecisionFlags.Distilled, out _);
            ShardDecision d = games[0].Decisions[0];

            Assert.That(d.CandidateVectors, Is.Not.Null);
            Assert.That(d.CandidateVectors.Length, Is.EqualTo(2 * VectorSize));
            Assert.That(d.ChosenVector, Is.Not.Null);
            Assert.That(d.ChosenVector.Length, Is.EqualTo(VectorSize));
        }

        [Test]
        public void Test100_DistilledAndDupCappedAreIndependent()
        {
            List<ShardGame> games = RoundTrip(
                ShardDecisionFlags.Distilled | ShardDecisionFlags.DupCapped, out _);
            ShardDecision d = games[0].Decisions[0];

            Assert.That(d.IsDistilled, Is.True);
            Assert.That(d.IsDupCapped, Is.True);
            Assert.That(d.IsLearner, Is.False);
        }
    }
}
