using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Faz 2 v4 Bölüm 4: vektörleştirmenin board disi skaler girdileri.
    /// </summary>
    /// <remarks>
    /// v4 degisikligi: <c>WhiteBorneOff</c>/<c>BlackBorneOff</c> alanlari KALDIRILDI.
    /// <see cref="BackgammonVectorizer.Vectorize(BackgammonState,int,Span{float})"/> borneOff'lari
    /// state'ten, hafif asiri yükleme parametrelerden, <c>VectorizeBatch</c> listeden okur.
    /// Böylece yanlis kullanim imkansizdir.
    /// </remarks>
    public readonly struct VectorizerScalars
    {
        /// <summary>Küp degeri (2'nin kuvveti: 1, 2, 4, ...).</summary>
        public readonly int CubeValue;

        /// <summary>0 ortada, +1 Beyaz, -1 Siyah.</summary>
        public readonly int CubeOwner;

        /// <summary>0 = money game.</summary>
        public readonly int MatchLength;

        public readonly int WhiteScore;
        public readonly int BlackScore;

        /// <summary>Yalnizca Crawford oyununun kendisini isaretler (post-Crawford degil).</summary>
        public readonly bool IsCrawfordGame;

        public VectorizerScalars(int cubeValue, int cubeOwner, int matchLength,
                                 int whiteScore, int blackScore, bool isCrawfordGame)
        {
            CubeValue = cubeValue;
            CubeOwner = cubeOwner;
            MatchLength = matchLength;
            WhiteScore = whiteScore;
            BlackScore = blackScore;
            IsCrawfordGame = isCrawfordGame;
        }

        /// <summary>State'ten 6 skaler alani okur (Faz 3 v4 de kullanir).</summary>
        public static VectorizerScalars From(BackgammonState state)
        {
            if (state == null)
            {
                throw new ArgumentNullException(nameof(state));
            }

            return new VectorizerScalars(
                state.cubeValue,
                state.cubeOwner,
                state.matchLength,
                state.whiteScore,
                state.blackScore,
                state.isCrawfordGame);
        }
    }
}