using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 5 §4.1: maç/küp bağlamının değişmez görünümü. <see cref="BackgammonState"/>'ten türetilir.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <see cref="CrawfordPlayed"/> alanı spesifikasyondaki alan listesine <b>eklenmiştir</b>:
    /// §4.1'in <see cref="IsPostCrawford"/> tanımı <c>crawfordPlayed &amp;&amp; !isCrawfordGame</c>
    /// diyor ama alan listesinde <c>crawfordPlayed</c> yok. Alanı eklemek, skordan türetmeye
    /// kıyasla daha doğrudan ve hatasızdır.
    /// </para>
    /// <para>
    /// <b>Spesifikasyondan bilinçli sapma (raporlandı):</b> §4.1 <see cref="IsDeadCube"/> için
    /// <c>CubeValue * 2 &gt; max(awayA, awayB)</c> diyor. Bu, küp <b>canlıyken</b> ölü damgası
    /// vurur: 3-away/3-away maçta küp 2 iken <c>2*2 = 4 &gt; 3</c> "ölü" der, oysa 2→4 çiftlemesi
    /// maçı bitiren <b>en değerli</b> çiftlemedir. Doğru tanım, küpün zaten maçı bitiren değere
    /// ulaşmış olmasıdır: <c>CubeValue &gt;= max(awayA, awayB)</c>. Bu uygulanmıştır.
    /// </para>
    /// </remarks>
    public readonly struct MatchState : IEquatable<MatchState>
    {
        /// <summary>Money game'de küpün üst sınırı.</summary>
        public const int MoneyGameMaxCube = 64;

        /// <summary>Maç uzunluğu (puan). <c>0</c> = money game.</summary>
        public readonly int MatchLength;

        /// <summary>Beyazın skoru.</summary>
        public readonly int WhiteScore;

        /// <summary>Siyahın skoru.</summary>
        public readonly int BlackScore;

        /// <summary>Küp değeri: 1, 2, 4, ..., 64.</summary>
        public readonly int CubeValue;

        /// <summary>Küp sahibi: <c>0</c> ortada, <c>+1</c> Beyaz, <c>-1</c> Siyah.</summary>
        public readonly sbyte CubeOwner;

        /// <summary>Bu oyun Crawford oyunu mu?</summary>
        public readonly bool IsCrawford;

        /// <summary>Crawford oyunu oynandı mı? (post-Crawford tespiti için)</summary>
        public readonly bool CrawfordPlayed;

        public MatchState(int matchLength, int whiteScore, int blackScore, int cubeValue, sbyte cubeOwner,
                          bool isCrawford, bool crawfordPlayed)
        {
            if (matchLength < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(matchLength));
            }

            if (whiteScore < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(whiteScore));
            }

            if (blackScore < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(blackScore));
            }

            if (cubeValue < 1 || cubeValue > MoneyGameMaxCube || (cubeValue & (cubeValue - 1)) != 0)
            {
                throw new ArgumentOutOfRangeException(nameof(cubeValue), "Küp değeri 2'nin kuvveti olmalı (1..64).");
            }

            if (cubeOwner < -1 || cubeOwner > 1)
            {
                throw new ArgumentOutOfRangeException(nameof(cubeOwner));
            }

            MatchLength = matchLength;
            WhiteScore = whiteScore;
            BlackScore = blackScore;
            CubeValue = cubeValue;
            CubeOwner = cubeOwner;
            IsCrawford = isCrawford;
            CrawfordPlayed = crawfordPlayed;
        }

        /// <summary>Money game bağlamı: küp ortada, değer 1.</summary>
        public static MatchState MoneyGame
        {
            get { return new MatchState(0, 0, 0, 1, 0, false, false); }
        }

        /// <summary><see cref="BackgammonState"/>'ten bağlamı türetir.</summary>
        public static MatchState From(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            return new MatchState(state.matchLength, state.whiteScore, state.blackScore, state.cubeValue,
                                  state.cubeOwner, state.isCrawfordGame, state.crawfordPlayed);
        }

        /// <summary>Maç uzunluğu 0 mı?</summary>
        public bool IsMoneyGame
        {
            get { return MatchLength == 0; }
        }

        /// <summary>Oyuncunun maçı bitirmek için kaç puana ihtiyacı var. Money game'de <see cref="int.MaxValue"/>.</summary>
        public int AwayScore(int player)
        {
            if (IsMoneyGame)
            {
                return int.MaxValue;
            }

            return MatchLength - ScoreOf(player);
        }

        /// <summary>Oyuncunun skoru.</summary>
        public int ScoreOf(int player)
        {
            return player > 0 ? WhiteScore : BlackScore;
        }

        /// <summary>Crawford oyunu mu? (money game'de daima <c>false</c>)</summary>
        public bool IsCrawfordGame
        {
            get { return !IsMoneyGame && IsCrawford; }
        }

        /// <summary>Post-Crawford mı? (Crawford oyunu oynandı ve bu oyun Crawford değil)</summary>
        public bool IsPostCrawford
        {
            get { return !IsMoneyGame && !IsCrawford && CrawfordPlayed; }
        }

        /// <summary>
        /// Küp ölü mü? Küp zaten maçı bitiren değere ulaştıysa çiftlemek hiçbir şey kazandırmaz.
        /// </summary>
        public bool IsDeadCube
        {
            get
            {
                if (IsMoneyGame)
                {
                    return false;
                }

                int awayWhite = AwayScore(1);
                int awayBlack = AwayScore(-1);
                if (awayWhite <= 0 || awayBlack <= 0)
                {
                    return true;
                }

                return CubeValue >= (awayWhite > awayBlack ? awayWhite : awayBlack);
            }
        }

        /// <summary>
        /// Bu maçta ulaşılabilen en büyük küp değeri: <c>max(away)</c>'den büyük olmayan en büyük 2'nin kuvveti.
        /// Money game'de <see cref="MoneyGameMaxCube"/>.
        /// </summary>
        public int MaxCubeValue
        {
            get
            {
                if (IsMoneyGame)
                {
                    return MoneyGameMaxCube;
                }

                int awayWhite = AwayScore(1);
                int awayBlack = AwayScore(-1);
                int limit = awayWhite > awayBlack ? awayWhite : awayBlack;
                if (limit <= 1)
                {
                    return 1;
                }

                int value = 1;
                while (value * 2 <= limit && value < MoneyGameMaxCube)
                {
                    value *= 2;
                }

                return value;
            }
        }

        /// <summary>Değerlendirici <c>Version</c> bileşimi için kararlı karma.</summary>
        public int Hash
        {
            get
            {
                unchecked
                {
                    uint h = 2166136261u;
                    h = (h ^ (uint)MatchLength) * 16777619u;
                    h = (h ^ (uint)WhiteScore) * 16777619u;
                    h = (h ^ (uint)BlackScore) * 16777619u;
                    h = (h ^ (uint)CubeValue) * 16777619u;
                    h = (h ^ (uint)(byte)CubeOwner) * 16777619u;
                    h = (h ^ (IsCrawford ? 1u : 0u)) * 16777619u;
                    h = (h ^ (CrawfordPlayed ? 1u : 0u)) * 16777619u;
                    return (int)(h & 0x7FFFFFFFu);
                }
            }
        }

        public bool Equals(MatchState other)
        {
            return MatchLength == other.MatchLength
                && WhiteScore == other.WhiteScore
                && BlackScore == other.BlackScore
                && CubeValue == other.CubeValue
                && CubeOwner == other.CubeOwner
                && IsCrawford == other.IsCrawford
                && CrawfordPlayed == other.CrawfordPlayed;
        }

        public override bool Equals(object obj)
        {
            return obj is MatchState other && Equals(other);
        }

        public override int GetHashCode()
        {
            return Hash;
        }

        public static bool operator ==(MatchState left, MatchState right)
        {
            return left.Equals(right);
        }

        public static bool operator !=(MatchState left, MatchState right)
        {
            return !left.Equals(right);
        }

        public override string ToString()
        {
            if (IsMoneyGame)
            {
                return "money cube=" + CubeValue + " owner=" + CubeOwner;
            }

            return MatchLength + "pt " + WhiteScore + "-" + BlackScore + " cube=" + CubeValue +
                   " owner=" + CubeOwner + (IsCrawfordGame ? " crawford" : IsPostCrawford ? " post-crawford" : string.Empty);
        }
    }
}
