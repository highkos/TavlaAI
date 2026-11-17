using System;
using Backgammon.Core;

namespace Backgammon.UI
{
    /// <summary>
    /// Faz 5 Bolum 6.2 / 6.7: mac skoru, Crawford rozeti ve mac uzunlugu gorunumu.
    /// </summary>
    public sealed class MatchScoreViewModel
    {
        /// <summary>Beyazin skoru.</summary>
        public int WhiteScore { get; private set; }

        /// <summary>Siyazin skoru.</summary>
        public int BlackScore { get; private set; }

        /// <summary>Mac uzunlugu; <c>0</c> = money game.</summary>
        public int MatchLength { get; private set; }

        /// <summary>Beyazin maci bitirmek icin ihtiyaci olan puan; money game'de <c>-1</c>.</summary>
        public int AwayWhite { get; private set; }

        /// <summary>Siyazin maci bitirmek icin ihtiyaci olan puan; money game'de <c>-1</c>.</summary>
        public int AwayBlack { get; private set; }

        /// <summary>Bu oyun Crawford oyunu mu?</summary>
        public bool IsCrawford { get; private set; }

        /// <summary>Post-Crawford mi?</summary>
        public bool IsPostCrawford { get; private set; }

        /// <summary>Money game mi?</summary>
        public bool IsMoneyGame { get; private set; }

        /// <summary>Durum degisti.</summary>
        public event Action Changed;

        /// <summary><see cref="BackgammonState"/>'ten gorunumu turetir.</summary>
        public void Update(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            MatchState match = MatchState.From(state);

            WhiteScore = match.WhiteScore;
            BlackScore = match.BlackScore;
            MatchLength = match.MatchLength;
            IsMoneyGame = match.IsMoneyGame;
            AwayWhite = match.IsMoneyGame ? -1 : match.AwayScore(1);
            AwayBlack = match.IsMoneyGame ? -1 : match.AwayScore(-1);
            IsCrawford = match.IsCrawfordGame;
            IsPostCrawford = match.IsPostCrawford;

            Changed?.Invoke();
        }
    }
}
