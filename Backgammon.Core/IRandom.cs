namespace Backgammon.Core
{
    /// <summary>
    /// Deterministik / kriptografik rastgelelik soyutlaması. Bölüm 3.
    /// </summary>
    public interface IRandom
    {
        uint NextUInt();

        /// <summary>1..6 arası bias'sız zar değeri.</summary>
        int RollDie();
    }
}
