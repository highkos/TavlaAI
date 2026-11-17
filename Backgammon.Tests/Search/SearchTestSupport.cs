using System;
using Backgammon.Core;

namespace Backgammon.Tests
{
    /// <summary>Faz 3 arama testleri için pozisyon kurucuları ve ortak yardımcılar.</summary>
    internal static class SearchTestSupport
    {
        public const float Tolerance = 1e-5f;

        /// <summary>Boş tahta; taşlar çağıran tarafından yerleştirilir.</summary>
        public static BackgammonState Blank(int turn)
        {
            var s = new BackgammonState();
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                s.board[i] = 0;
            }

            s.whiteBorneOff = 0;
            s.blackBorneOff = 0;
            s.turn = (sbyte)turn;
            s.cubeValue = 1;
            s.cubeOwner = 0;
            s.matchLength = 0;
            s.whiteScore = 0;
            s.blackScore = 0;
            s.isCrawfordGame = false;
            s.crawfordPlayed = false;
            s.cubePassed = false;
            s.phase = GamePhase.PreRoll;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return s;
        }

        /// <summary>Zarları ayarlar (phase = Moving) ve hash'i tazeler.</summary>
        public static BackgammonState WithDice(BackgammonState s, int d1, int d2)
        {
            BackgammonEngine.SetDice(s, d1, d2);
            return s;
        }

        /// <summary>Başlangıç dizilimi.</summary>
        public static BackgammonState Starting(int d1 = 3, int d2 = 1)
        {
            var s = new BackgammonState();
            return WithDice(s, d1, d2);
        }

        /// <summary>Orta oyun: her iki renk dağınık, temas var, toplama yok.</summary>
        public static BackgammonState MidGame(int d1 = 3, int d2 = 5)
        {
            var s = Blank(1);
            s.board[1] = 2;
            s.board[6] = 3;
            s.board[12] = 4;
            s.board[17] = 3;
            s.board[20] = 3;

            s.board[24] = -2;
            s.board[19] = -3;
            s.board[13] = -4;
            s.board[8] = -3;
            s.board[5] = -3;

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>Beyaz barda (2 taş), girişler açık.</summary>
        public static BackgammonState WhiteOnBar(int d1 = 2, int d2 = 5)
        {
            var s = Blank(1);
            s.board[0] = 2;
            s.board[6] = 3;
            s.board[12] = 4;
            s.board[17] = 3;
            s.board[20] = 3;

            s.board[24] = -2;
            s.board[19] = -3;
            s.board[13] = -4;
            s.board[8] = -3;
            s.board[5] = -3;

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>Siyah barda (2 taş), girişler açık.</summary>
        public static BackgammonState BlackOnBar(int d1 = 2, int d2 = 5)
        {
            var s = Blank(-1);
            s.board[1] = 2;
            s.board[6] = 3;
            s.board[12] = 4;
            s.board[17] = 3;
            s.board[20] = 3;

            s.board[25] = -2;
            s.board[19] = -3;
            s.board[13] = -4;
            s.board[8] = -3;
            s.board[5] = -3;

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>Bitiş oyunu: her iki renk de evinde, temas yok.</summary>
        public static BackgammonState BearOff(int d1 = 2, int d2 = 5)
        {
            var s = Blank(1);
            s.board[19] = 3;
            s.board[20] = 3;
            s.board[21] = 3;
            s.board[22] = 3;
            s.board[23] = 3;

            s.board[1] = -3;
            s.board[2] = -3;
            s.board[3] = -3;
            s.board[4] = -3;
            s.board[5] = -3;

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>
        /// Her iki taraf da barda ve girişleri kapalı: Beyaz 3 barda + 2'şer taş 19..24,
        /// Siyah 3 barda + 2'şer taş 1..6. Hiçbir taraf giremez; her pas bir ply tüketir.
        /// </summary>
        /// <remarks>
        /// Beyaz 1..6'ya girer (bar indeksi 0, yönü +1), Siyah 19..24'e girer (bar indeksi 25,
        /// yönü -1). Bu yüzden Beyaz'ın girişini kapatmak için Siyah 1..6'yı, Siyah'ın girişini
        /// kapatmak için Beyaz 19..24'ü 2'şer taşla tutmalıdır.
        /// </remarks>
        public static BackgammonState BothBarBlocked(int d1 = 3, int d2 = 4)
        {
            var s = Blank(1);
            s.board[0] = 3;
            for (int p = 19; p <= 24; p++)
            {
                s.board[p] = 2;
            }

            s.board[25] = -3;
            for (int p = 1; p <= 6; p++)
            {
                s.board[p] = -2;
            }

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>
        /// Küçük bitiş pozisyonu: Beyaz 14 toplanmış + 1 taş 12'de; Siyah 14 toplanmış + 1 taş 1'de.
        /// Siyah her zarla toplar → her rakip yanıtı terminal (Single, +1 Siyah için).
        /// </summary>
        public static BackgammonState SingleCheckerEndgame(int d1 = 3, int d2 = 1)
        {
            var s = Blank(1);
            s.board[12] = 1;
            s.whiteBorneOff = 14;

            s.board[1] = -1;
            s.blackBorneOff = 14;

            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>Rastgele geçerli pozisyon (terminal değil) + zarlar.</summary>
        public static BackgammonState RandomPosition(IRandom rng, int d1, int d2)
        {
            var s = new BackgammonState();
            VectorTestSupport.RandomPosition(rng, s);
            s.matchLength = 0;
            s.whiteScore = 0;
            s.blackScore = 0;
            s.isCrawfordGame = false;
            s.cubeValue = 1;
            s.cubeOwner = 0;
            s.hash = BackgammonEngine.ComputeZobristHash(s);
            return WithDice(s, d1, d2);
        }

        /// <summary>Faz 1 <see cref="BackgammonEngine.MirrorTo"/> ile aynalanmış kopya.</summary>
        public static BackgammonState Mirror(BackgammonState s)
        {
            var m = new BackgammonState();
            BackgammonEngine.MirrorTo(s, m);
            return m;
        }

        /// <summary>
        /// Terminal-olmayan kayıtları listenin başına <b>kararlı</b> olarak taşır ve sayısını döner.
        /// </summary>
        public static int PartitionNonTerminal(AfterStateList list)
        {
            int n = list.Count;
            int write = 0;
            for (int i = 0; i < n; i++)
            {
                if (!list.IsTerminal[i])
                {
                    if (i != write)
                    {
                        list.Swap(i, write);
                    }

                    write++;
                }
            }

            return write;
        }

        /// <summary>Değeri <c>[L,U]</c>'a kırpar (arama tarafı, Bölüm 1).</summary>
        public static float Clamp(float v)
        {
            if (v < BackgammonSearch.L)
            {
                return BackgammonSearch.L;
            }

            if (v > BackgammonSearch.U)
            {
                return BackgammonSearch.U;
            }

            return v;
        }

        /// <summary>State'in bit düzeyinde kopyası (hash dahil) — geri yükleme testi için.</summary>
        public static string Fingerprint(BackgammonState s)
        {
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                sb.Append(s.board[i]).Append(',');
            }

            sb.Append('|').Append(s.whiteBorneOff).Append('|').Append(s.blackBorneOff)
              .Append('|').Append(s.turn).Append('|').Append(s.cubeValue).Append('|').Append(s.cubeOwner)
              .Append('|').Append(s.matchLength).Append('|').Append(s.whiteScore).Append('|').Append(s.blackScore)
              .Append('|').Append(s.isCrawfordGame).Append('|').Append(s.crawfordPlayed)
              .Append('|').Append(s.cubePassed).Append('|').Append((byte)s.phase)
              .Append('|').Append(s.remainingCount)
              .Append('|').Append(s.hash.ToString("X16"));
            return sb.ToString();
        }
    }
}