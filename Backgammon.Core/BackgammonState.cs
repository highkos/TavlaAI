using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Tavla pozisyonu ve oyun durumu. Havuzlanabilir, <see cref="CopyFrom"/> destekli.
    /// Bölüm 2.1.
    /// </summary>
    /// <remarks>
    /// Sınıf (struct değil) olmasının nedeni: <c>sbyte[]</c> içeren bir struct kopyalandığında
    /// dizi referansı paylaşılır, yani deep copy oluşmaz. Diziler yapıcıda bir kez ayrılır.
    /// </remarks>
    public sealed class BackgammonState
    {
        public const int BoardSize = 26;
        public const int PiecesPerPlayer = 15;

        /// <summary>
        /// 0 = Beyaz bar (>= 0), 1..24 = haneler, 25 = Siyah bar (&lt;= 0).
        /// Pozitif değer Beyaz, negatif değer Siyah taş sayısıdır.
        /// </summary>
        public readonly sbyte[] board;

        public byte whiteBorneOff;
        public byte blackBorneOff;

        /// <summary>+1 Beyaz, -1 Siyah.</summary>
        public sbyte turn;

        /// <summary>O tur atılan zarlar (atıldığı sırayla).</summary>
        public readonly byte[] rolledDice;

        /// <summary>Kalan zarlar; sıralı (küçükten büyüğe). Dublede 4 slot.</summary>
        public readonly byte[] remainingDice;

        public byte remainingCount;

        public int cubeValue;

        /// <summary>0 ortada, +1 Beyaz, -1 Siyah.</summary>
        public sbyte cubeOwner;

        /// <summary>0 = money game (sınırsız).</summary>
        public int matchLength;

        public int whiteScore;
        public int blackScore;

        public bool isCrawfordGame;
        public bool crawfordPlayed;

        /// <summary>
        /// Oyun küp reddi (Pass) ile mi bitti? Yalnızca <see cref="GamePhase.GameOver"/> ile birlikte
        /// anlamlıdır; tahta terminal olmadığı hâlde oyunun bittiğini bildirir (ASSUMPTIONS.md D-03).
        /// Hash'e girmez.
        /// </summary>
        public bool cubePassed;

        public GamePhase phase;

        /// <summary>Artımlı Zobrist hash. Bölüm 2.1 tanımı.</summary>
        public ulong hash;

        public BackgammonState()
        {
            board = new sbyte[BoardSize];
            rolledDice = new byte[2];
            remainingDice = new byte[4];
            Reset();
        }

        /// <summary>Başlangıç dizilimine ve temiz bir money game durumuna döner.</summary>
        public void Reset()
        {
            Array.Clear(board, 0, BoardSize);

            board[1] = 2;
            board[12] = 5;
            board[17] = 3;
            board[19] = 5;

            board[24] = -2;
            board[13] = -5;
            board[8] = -3;
            board[6] = -5;

            whiteBorneOff = 0;
            blackBorneOff = 0;
            turn = 1;

            rolledDice[0] = 0;
            rolledDice[1] = 0;
            remainingDice[0] = 0;
            remainingDice[1] = 0;
            remainingDice[2] = 0;
            remainingDice[3] = 0;
            remainingCount = 0;

            cubeValue = 1;
            cubeOwner = 0;
            matchLength = 0;
            whiteScore = 0;
            blackScore = 0;
            isCrawfordGame = false;
            crawfordPlayed = false;
            cubePassed = false;
            phase = GamePhase.DetermineFirstPlayer;

            hash = BackgammonEngine.ComputeZobristHash(this);
        }

        /// <summary>Dizi içeriğini kopyalar; allocation yapmaz.</summary>
        public void CopyFrom(BackgammonState other)
        {
            if (other == null)
            {
                throw new ArgumentNullException(nameof(other));
            }

            Array.Copy(other.board, board, BoardSize);

            whiteBorneOff = other.whiteBorneOff;
            blackBorneOff = other.blackBorneOff;
            turn = other.turn;

            rolledDice[0] = other.rolledDice[0];
            rolledDice[1] = other.rolledDice[1];
            remainingDice[0] = other.remainingDice[0];
            remainingDice[1] = other.remainingDice[1];
            remainingDice[2] = other.remainingDice[2];
            remainingDice[3] = other.remainingDice[3];
            remainingCount = other.remainingCount;

            cubeValue = other.cubeValue;
            cubeOwner = other.cubeOwner;
            matchLength = other.matchLength;
            whiteScore = other.whiteScore;
            blackScore = other.blackScore;
            isCrawfordGame = other.isCrawfordGame;
            crawfordPlayed = other.crawfordPlayed;
            cubePassed = other.cubePassed;
            phase = other.phase;
            hash = other.hash;
        }

        /// <summary>Yalnızca test/araç amaçlı; hot path dışında kullanılır.</summary>
        public BackgammonState Clone()
        {
            var copy = new BackgammonState();
            copy.CopyFrom(this);
            return copy;
        }

        /// <summary>Toplam taş sayısı (board + bar + toplanan) — SanityCheck yardımcısı.</summary>
        public int CountPieces(int player)
        {
            int total = player == 1 ? whiteBorneOff : blackBorneOff;
            for (int p = 0; p < BoardSize; p++)
            {
                int v = board[p];
                if (player == 1)
                {
                    if (v > 0)
                    {
                        total += v;
                    }
                }
                else
                {
                    if (v < 0)
                    {
                        total += -v;
                    }
                }
            }

            return total;
        }

        public override string ToString()
        {
            return "turn=" + turn + " phase=" + phase + " off=" + whiteBorneOff + "/" + blackBorneOff +
                   " dice=" + remainingCount + " hash=" + hash.ToString("X16");
        }
    }
}
