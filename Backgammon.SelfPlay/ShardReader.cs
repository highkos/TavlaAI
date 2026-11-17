using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.4: shard okuyucu (C# tarafi; Python okuyucusu <c>ml/shards.py</c>).
    /// </summary>
    public static class ShardReader
    {
        /// <summary>Dosyayi okur; <c>.gz</c> uzantisi veya <paramref name="gzip"/> ile gzip acar.</summary>
        public static (ShardHeader Header, List<ShardGame> Games) ReadFile(string path, bool? gzip = null)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("path bos olamaz.", nameof(path));
            }

            bool useGzip = gzip ?? path.EndsWith(ShardConstants.GzipExtension, StringComparison.OrdinalIgnoreCase);

            using FileStream file = File.OpenRead(path);
            if (useGzip)
            {
                using var gz = new GZipStream(file, CompressionMode.Decompress, leaveOpen: true);
                return Read(gz);
            }

            return Read(file);
        }

        /// <summary>Shard'i akistan okur.</summary>
        public static (ShardHeader Header, List<ShardGame> Games) Read(Stream stream)
        {
            if (stream == null)
            {
                throw new ArgumentNullException(nameof(stream));
            }

            ShardHeader header = ShardHeader.ReadFrom(stream);
            var games = new List<ShardGame>();

            while (true)
            {
                int first = stream.ReadByte();
                if (first < 0)
                {
                    break;
                }

                games.Add(ReadGame(stream, (byte)first));
            }

            return (header, games);
        }

        private static ShardGame ReadGame(Stream stream, byte firstByteOfGameId)
        {
            var game = new ShardGame
            {
                GameId = ReadU64WithFirstByte(stream, firstByteOfGameId),
                LearnerSide = unchecked((sbyte)ReadByte(stream)),
                Flags = (ShardGameFlags)ReadByte(stream),
                CubeValue = ReadI32(stream),
            };

            uint decisionCount = ReadU32(stream);
            for (uint i = 0; i < decisionCount; i++)
            {
                game.Decisions.Add(ReadDecision(stream));
            }

            game.Winner = unchecked((sbyte)ReadByte(stream));
            game.ResultType = ReadByte(stream);
            game.ResultPoints = ReadByte(stream);
            return game;
        }

        private static ShardDecision ReadDecision(Stream stream)
        {
            var decision = new ShardDecision
            {
                Mover = unchecked((sbyte)ReadByte(stream)),
                Flags = (ShardDecisionFlags)ReadByte(stream),
                CandidateTotal = ReadU16(stream),
            };

            int logged = ReadU16(stream);
            decision.SearchValue = ReadF32(stream);

            if (!decision.ChosenIsTerminal)
            {
                decision.ChosenVector = ReadFloats(stream, ShardConstants.VectorSize);
            }

            if (logged > 0)
            {
                decision.Q = ReadFloats(stream, logged);
                decision.PolicyTargetCs = ReadFloats(stream, logged);
                decision.CandidateVectors = ReadFloats(stream, logged * ShardConstants.VectorSize);
            }

            return decision;
        }

        private static ulong ReadU64WithFirstByte(Stream stream, byte first)
        {
            uint low = (uint)(first | (ReadByte(stream) << 8) | (ReadByte(stream) << 16) | (ReadByte(stream) << 24));
            uint high = ReadU32(stream);
            return low | ((ulong)high << 32);
        }

        private static byte ReadByte(Stream stream)
        {
            int b = stream.ReadByte();
            if (b < 0)
            {
                throw new EndOfStreamException("Shard beklenmedik sekilde bitti.");
            }

            return (byte)b;
        }

        private static ushort ReadU16(Stream stream)
        {
            int b0 = ReadByte(stream);
            int b1 = ReadByte(stream);
            return (ushort)(b0 | (b1 << 8));
        }

        private static uint ReadU32(Stream stream)
        {
            uint b0 = ReadByte(stream);
            uint b1 = ReadByte(stream);
            uint b2 = ReadByte(stream);
            uint b3 = ReadByte(stream);
            return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24);
        }

        private static int ReadI32(Stream stream)
        {
            return unchecked((int)ReadU32(stream));
        }

        private static float ReadF32(Stream stream)
        {
            return BitConverter.UInt32BitsToSingle(ReadU32(stream));
        }

        private static float[] ReadFloats(Stream stream, int count)
        {
            var values = new float[count];
            for (int i = 0; i < count; i++)
            {
                values[i] = ReadF32(stream);
            }

            return values;
        }
    }
}