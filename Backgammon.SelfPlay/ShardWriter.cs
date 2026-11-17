using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

namespace Backgammon.SelfPlay
{
    /// <summary>
    /// Faz 4 v3 Bolum 5.4: shard yazici (little-endian ikili, istege bagli gzip).
    /// </summary>
    /// <remarks>
    /// <para>
    /// Bicim: 32 baytlik <see cref="ShardHeader"/>, ardindan ardisik oyun kayitlari.
    /// </para>
    /// <para>
    /// <b>Dogrulama:</b> her karar kaydinin <c>Q</c>, <c>PolicyTargetCs</c> ve
    /// <c>CandidateVectors</c> uzunluklari tutarli olmalidir; <c>ChosenIsTerminal</c> bayragi ile
    /// <c>ChosenVector</c> varligi celismemelidir.
    /// </para>
    /// </remarks>
    public static class ShardWriter
    {
        /// <summary>Shard'i verilen akisa yazar.</summary>
        /// <exception cref="ArgumentNullException">Argumanlardan biri null.</exception>
        /// <exception cref="ArgumentException">Karar kaydi tutarsiz.</exception>
        public static void Write(Stream stream, in ShardHeader header, IEnumerable<ShardGame> games)
        {
            if (stream == null)
            {
                throw new ArgumentNullException(nameof(stream));
            }

            if (games == null)
            {
                throw new ArgumentNullException(nameof(games));
            }

            header.WriteTo(stream);

            foreach (ShardGame game in games)
            {
                WriteGame(stream, game);
            }

            stream.Flush();
        }

        /// <summary>Shard'i dosyaya yazar; <paramref name="gzip"/> ise gzip'ler.</summary>
        public static void WriteFile(string path, in ShardHeader header, IEnumerable<ShardGame> games, bool gzip)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("path bos olamaz.", nameof(path));
            }

            string? dir = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            using FileStream file = File.Create(path);
            // Faz 6 Asama D: 2 000 oyunluk shard ~2,5 GB ham veri uretir. Tamponsuz
            // FileStream + tek tek WriteByte cagrilari bu hacimde dakikalarca surer;
            // 64 KB'lik tampon ve toplu float yazimi (WriteFloats) bunu ~100x kisaltir.
            using var buffered = new BufferedStream(file, 1 << 16);
            if (gzip)
            {
                using var gz = new GZipStream(buffered, CompressionLevel.Optimal, leaveOpen: true);
                Write(gz, header, games);
            }
            else
            {
                Write(buffered, header, games);
            }
        }

        private static void WriteGame(Stream stream, ShardGame game)
        {
            if (game == null)
            {
                throw new ArgumentNullException(nameof(game));
            }

            WriteU64(stream, game.GameId);
            stream.WriteByte(unchecked((byte)game.LearnerSide));
            stream.WriteByte((byte)game.Flags);
            WriteI32(stream, game.CubeValue);
            WriteU32(stream, (uint)game.Decisions.Count);

            for (int i = 0; i < game.Decisions.Count; i++)
            {
                WriteDecision(stream, game.Decisions[i], i);
            }

            stream.WriteByte(unchecked((byte)game.Winner));
            stream.WriteByte(game.ResultType);
            stream.WriteByte(game.ResultPoints);
        }

        private static void WriteDecision(Stream stream, ShardDecision decision, int index)
        {
            if (decision == null)
            {
                throw new ArgumentNullException(nameof(decision));
            }

            int logged = decision.LoggedCount;
            bool terminal = decision.ChosenIsTerminal;

            if (terminal && decision.ChosenVector != null)
            {
                throw new ArgumentException(
                    "Karar " + index + ": ChosenIsTerminal=1 iken ChosenVector yazilmamali.");
            }

            if (!terminal && (decision.ChosenVector == null || decision.ChosenVector.Length != ShardConstants.VectorSize))
            {
                throw new ArgumentException(
                    "Karar " + index + ": ChosenVector " + ShardConstants.VectorSize + " elemanli olmali.");
            }

            if (logged > 0)
            {
                if (decision.PolicyTargetCs == null || decision.PolicyTargetCs.Length != logged)
                {
                    throw new ArgumentException("Karar " + index + ": PolicyTargetCs uzunlugu Q ile ayni olmali.");
                }

                if (decision.CandidateVectors == null || decision.CandidateVectors.Length != logged * ShardConstants.VectorSize)
                {
                    throw new ArgumentException(
                        "Karar " + index + ": CandidateVectors " + (logged * ShardConstants.VectorSize) + " elemanli olmali.");
                }
            }

            if (logged > ushort.MaxValue)
            {
                throw new ArgumentException("Karar " + index + ": loggedCount u16'ya sigmiyor.");
            }

            stream.WriteByte(unchecked((byte)decision.Mover));
            stream.WriteByte((byte)decision.Flags);
            WriteU16(stream, decision.CandidateTotal);
            WriteU16(stream, (ushort)logged);
            WriteF32(stream, decision.SearchValue);

            if (!terminal)
            {
                WriteFloats(stream, decision.ChosenVector!, ShardConstants.VectorSize);
            }

            if (logged > 0)
            {
                WriteFloats(stream, decision.Q!, logged);
                WriteFloats(stream, decision.PolicyTargetCs!, logged);
                WriteFloats(stream, decision.CandidateVectors!, logged * ShardConstants.VectorSize);
            }
        }

        internal static void WriteU16(Stream stream, ushort value)
        {
            stream.WriteByte((byte)value);
            stream.WriteByte((byte)(value >> 8));
        }

        internal static void WriteU32(Stream stream, uint value)
        {
            stream.WriteByte((byte)value);
            stream.WriteByte((byte)(value >> 8));
            stream.WriteByte((byte)(value >> 16));
            stream.WriteByte((byte)(value >> 24));
        }

        internal static void WriteI32(Stream stream, int value)
        {
            WriteU32(stream, unchecked((uint)value));
        }

        internal static void WriteU64(Stream stream, ulong value)
        {
            WriteU32(stream, (uint)value);
            WriteU32(stream, (uint)(value >> 32));
        }

        internal static void WriteF32(Stream stream, float value)
        {
            WriteU32(stream, BitConverter.SingleToUInt32Bits(value));
        }

        internal static void WriteFloats(Stream stream, float[] values, int count)
        {
            if (count <= 0)
            {
                return;
            }

            // Tek bir toplu yazim: float basina 4 WriteByte cagrisi, 2 000 oyunluk
            // shard'da ~2,5 milyar cagriya donusuyordu (bkz. WriteFile notu).
            byte[] buffer = new byte[count * 4];
            for (int i = 0; i < count; i++)
            {
                uint bits = BitConverter.SingleToUInt32Bits(values[i]);
                int o = i * 4;
                buffer[o] = (byte)bits;
                buffer[o + 1] = (byte)(bits >> 8);
                buffer[o + 2] = (byte)(bits >> 16);
                buffer[o + 3] = (byte)(bits >> 24);
            }

            stream.Write(buffer, 0, buffer.Length);
        }
    }
}