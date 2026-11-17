using System;

namespace Backgammon.Core
{
    /// <summary>
    /// Motor davranış ayarları. Bölüm 2.5.
    /// </summary>
    public struct EngineSettings
    {
        public EngineMode CurrentMode;

        /// <summary>Tekilleştirilmiş havuzda tek pozisyon kalırsa otomatik oynar.</summary>
        public bool AutoExecuteSingleMoves;

        /// <summary>Sıra geçince zarı otomatik atar.</summary>
        public bool AutoRollDice;

        /// <summary>Hamle onayından önce adım adım geri almaya izin verir (AITraining'de yok sayılır).</summary>
        public bool EnableUndo;

        /// <summary>Money game'de Jacoby kuralı (varsayılan: kapalı).</summary>
        public bool EnableJacoby;

        /// <summary>Ölü küp tekliflerini yasakla (varsayılan: açık).</summary>
        public bool DisallowDeadCube;

        public static EngineSettings Default
        {
            get
            {
                return new EngineSettings
                {
                    CurrentMode = EngineMode.AITraining,
                    AutoExecuteSingleMoves = true,
                    AutoRollDice = true,
                    EnableUndo = false,
                    EnableJacoby = false,
                    DisallowDeadCube = true
                };
            }
        }
    }

    /// <summary>
    /// Maç ayarları. Bölüm 2.5.
    /// </summary>
    public struct MatchSettings
    {
        /// <summary>0 = money game (sınırsız).</summary>
        public int MatchLength;

        public MatchSettings(int matchLength)
        {
            if (matchLength < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(matchLength));
            }

            MatchLength = matchLength;
        }

        public static MatchSettings MoneyGame => new MatchSettings(0);
    }
}
