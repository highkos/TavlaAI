namespace Backgammon.Core
{
    /// <summary>
    /// Oyun akışının bulunduğu aşama. Bölüm 2.1.
    /// </summary>
    public enum GamePhase : byte
    {
        /// <summary>Açılış zarı atılıyor; ilk oyuncu belirleniyor.</summary>
        DetermineFirstPlayer = 0,

        /// <summary>Sıra başı: küp teklif edilebilir ya da zar atılabilir.</summary>
        PreRoll = 1,

        /// <summary>Küp teklif edildi, cevap bekleniyor.</summary>
        CubeOffered = 2,

        /// <summary>Küp teklif edilemiyor; yalnızca zar atılabilir.</summary>
        WaitForRoll = 3,

        /// <summary>Zarlar atıldı, hamle oynanıyor.</summary>
        Moving = 4,

        /// <summary>Oyun bitti (bir taraf 15 taş topladı).</summary>
        GameOver = 5
    }

    /// <summary>
    /// Motorun çalışma modu. Bölüm 2.5.
    /// </summary>
    public enum EngineMode : byte
    {
        AITraining = 0,
        PlayerVSInference = 1,
        Analysis = 2
    }

    /// <summary>
    /// Oyun sonucu tipi. <see cref="AfterStateList.ResultType"/> alanında 0/1/2/3 olarak saklanır.
    /// </summary>
    public enum GameResultType : byte
    {
        /// <summary>Oyun bitmedi.</summary>
        None = 0,

        /// <summary>Kaybeden en az bir taş topladı; çarpan 1.</summary>
        Single = 1,

        /// <summary>Kaybeden hiç taş toplamadı; çarpan 2.</summary>
        Gammon = 2,

        /// <summary>Gammon + kaybedenin barında veya kazananın evinde taşı var; çarpan 3.</summary>
        Backgammon = 3
    }

    /// <summary>
    /// <see cref="MoveStep.Flags"/> bit maskesi. Bölüm 2.2.
    /// </summary>
    [System.Flags]
    public enum MoveFlags : byte
    {
        None = 0,

        /// <summary>Rakibin tam 1 taşı vuruldu.</summary>
        Hit = 1,

        /// <summary>Taş toplandı (To = Beyaz 25, Siyah 0).</summary>
        BearOff = 2,

        /// <summary>Hamle bardan yapıldı (From = BarIndex(turn)).</summary>
        FromBar = 4
    }
}
