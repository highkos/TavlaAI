"""Faz 6 Bolum 5.1/5.5: equity ve dislayici<->kumulatif donusum (Python aynasi).

**Tek dogruluk kaynagi C# tarafidir**: ``Backgammon.Core/Match/OutcomeDistribution.cs``
icindeki ``Equity`` ozelligi ve ``FromProbabilities`` fabrikasi. Bu modul egitim
hattinin (kayip, kalibrasyon, teshis) ayni sayilari uretmesini saglar; Test 53
iki tarafin ayni sonucu verdigini dogrular.

Dislayici sinif sirasi (``ml.model.PROB_ORDER``): ``W, GW, BW, L, GL, BL``.

    E = W + 2*GW + 3*BW - (L + 2*GL + 3*BL)          (dislayici, aralik [-3, +3])

Kumulatif karsiligi (C# struct'inin alanlari):

    Win           = W + GW + BW
    WinGammon     = GW + BW
    WinBackgammon = BW
    LoseGammon    = GL + BL
    LoseBackgammon= BL
    E = Win + WinGammon + WinBackgammon - Lose - LoseGammon - LoseBackgammon

Iki ifade cebirsel olarak **aynidir**; Test 53 bunu sayisal olarak dogrular.
"""

from __future__ import annotations

import numpy as np

#: Dislayici sinif sayisi.
PROB_COUNT = 6

#: Dislayici sinif sirasi.
PROB_ORDER = ("W", "GW", "BW", "L", "GL", "BL")

#: Sinif basina carpan (W=+1, GW=+2, BW=+3, L=-1, GL=-2, BL=-3).
EQUITY_WEIGHTS = np.array([1.0, 2.0, 3.0, -1.0, -2.0, -3.0], dtype=np.float64)


def equity_from_exclusive(probs) -> np.ndarray:
    """``probs`` [..., 6] dislayici olasiliklarindan equity uretir.

    Girdi normalize **edilmez**; cagiran normalize etmelidir (bkz.
    :func:`normalize_exclusive`). C# ``FromProbabilities`` normalize eder.
    """
    p = np.asarray(probs, dtype=np.float64)
    if p.shape[-1] != PROB_COUNT:
        raise ValueError(f"son eksen {PROB_COUNT} olmali: {p.shape}")
    return p @ EQUITY_WEIGHTS


def equity_from_cumulative(win, win_gammon, win_backgammon, lose_gammon, lose_backgammon) -> np.ndarray:
    """C# ``OutcomeDistribution.Equity`` ile birebir ayni ifade (kumulatif alanlar)."""
    win = np.asarray(win, dtype=np.float64)
    win_gammon = np.asarray(win_gammon, dtype=np.float64)
    win_backgammon = np.asarray(win_backgammon, dtype=np.float64)
    lose_gammon = np.asarray(lose_gammon, dtype=np.float64)
    lose_backgammon = np.asarray(lose_backgammon, dtype=np.float64)
    lose = 1.0 - win
    return win + win_gammon + win_backgammon - lose - lose_gammon - lose_backgammon


def normalize_exclusive(probs) -> np.ndarray:
    """Satirlari toplam 1 yapar (C# ``FromProbabilities`` ile ayni davranis).

    Toplam 0 ise ``ValueError`` atar (C# tarafinda ``IsValid = false``).
    """
    p = np.asarray(probs, dtype=np.float64)
    if p.shape[-1] != PROB_COUNT:
        raise ValueError(f"son eksen {PROB_COUNT} olmali: {p.shape}")
    total = p.sum(axis=-1, keepdims=True)
    if np.any(total <= 0.0):
        raise ValueError("olasilik toplami 0; dagilim gecersiz")
    return p / total


def to_cumulative(probs) -> dict[str, np.ndarray]:
    """Dislayici [..., 6] -> C# ``OutcomeDistribution`` alanlari (kumulatif)."""
    p = normalize_exclusive(probs)
    w, gw, bw, l, gl, bl = (p[..., i] for i in range(PROB_COUNT))
    win = w + gw + bw
    return {
        "win": win,
        "win_gammon": gw + bw,
        "win_backgammon": bw,
        "lose_gammon": gl + bl,
        "lose_backgammon": bl,
    }


def from_cumulative(win, win_gammon, win_backgammon, lose_gammon, lose_backgammon) -> np.ndarray:
    """Kumulatif alanlar -> dislayici [..., 6] (``to_cumulative`` tersi)."""
    win = np.asarray(win, dtype=np.float64)
    win_gammon = np.asarray(win_gammon, dtype=np.float64)
    win_backgammon = np.asarray(win_backgammon, dtype=np.float64)
    lose_gammon = np.asarray(lose_gammon, dtype=np.float64)
    lose_backgammon = np.asarray(lose_backgammon, dtype=np.float64)
    lose = 1.0 - win
    return np.stack(
        [
            win - win_gammon,
            win_gammon - win_backgammon,
            win_backgammon,
            lose - lose_gammon,
            lose_gammon - lose_backgammon,
            lose_backgammon,
        ],
        axis=-1,
    )


def one_hot_exclusive(winner: int, result_type: int, perspective: int) -> np.ndarray:
    """Tek oyun sonucundan dislayici 6'li hedef (Faz 6 Bolum 8.3).

    ``winner``      : +1 beyaz, -1 siyah (``GameResult.Winner``).
    ``result_type`` : 1 Single, 2 Gammon, 3 Backgammon (``GameResultType``).
    ``perspective`` : +1 / -1; hedef bu bakis acisindan yazilir.

    Oyuncu kazandiysa ilk uc sutun (W/GW/BW), kaybettiysa son uc sutun (L/GL/BL).
    """
    if winner not in (1, -1):
        raise ValueError(f"winner +1 veya -1 olmali: {winner}")
    if perspective not in (1, -1):
        raise ValueError(f"perspective +1 veya -1 olmali: {perspective}")
    if result_type not in (1, 2, 3):
        raise ValueError(f"result_type 1..3 olmali: {result_type}")

    out = np.zeros(PROB_COUNT, dtype=np.float64)
    offset = 0 if winner == perspective else 3
    out[offset + (result_type - 1)] = 1.0
    return out

# ---------------------------------------------------------------------------
# Faz 7 Bolum 9.9: float32 birebir ayna (C# OutcomeDistribution ile bit duzeyi)
# ---------------------------------------------------------------------------
#
# Yukaridaki fonksiyonlar **float64** ile calisir (egitim hatti icin dogru secim).
# C# ``OutcomeDistribution`` ise alanlarini **float32** tutar ve ``FromProbabilities``
# icinde float32 yuvarlamasi yapar. Bu yuzden float64 ifade ile C# sonucu son
# bitlerde ayrisir; ``equity_golden.json`` paritesi (Test 122) **sifir tolerans**
# istedigi icin asagidaki float32 aynasi gereklidir.
#
# Kural: bu blok C# kodunun **birebir** kopyasidir. C# degisirse burasi da degisir
# ve ``ml/tests/test_equity_parity.py`` kirmizi yanar.


def _as_f32(probs) -> np.ndarray:
    """Girdiyi float32'ye indirger ve sekli dogrular."""
    p = np.asarray(probs, dtype=np.float32)
    if p.shape[-1] != PROB_COUNT:
        raise ValueError(f"son eksen {PROB_COUNT} olmali: {p.shape}")
    return p


def _clamp_f32(value, lo, hi) -> np.ndarray:
    """C# ``Clamp``: ``value < lo ? lo : (value > hi ? hi : value)`` (float32)."""
    v = np.asarray(value, dtype=np.float32)
    lo = np.float32(lo)
    hi = np.float32(hi)
    return np.where(v < lo, lo, np.where(v > hi, hi, v)).astype(np.float32)


def normalize_exclusive_f32(probs) -> np.ndarray:
    """C# ``FromProbabilities`` normalize adimi, **bit duzeyinde** ayni.

    Toplam float64'te, carpim float64'te, sonuc float32'ye yuvarlanir (C#
    ``(float)(w * inv)``). Gecersiz girdi (NaN/Inf, negatif, toplam <= 0)
    ``ValueError`` atar; C# tarafinda karsiligi ``IsValid == false``.
    """
    p = _as_f32(probs)
    if not np.all(np.isfinite(p)):
        raise ValueError("NaN/Inf; dagilim gecersiz")
    if np.any(p < np.float32(0.0)):
        raise ValueError("negatif olasilik; dagilim gecersiz")
    p64 = p.astype(np.float64)
    total = p64[..., 0] + p64[..., 1] + p64[..., 2] + p64[..., 3] + p64[..., 4] + p64[..., 5]
    if np.any(total <= 0.0):
        raise ValueError("olasilik toplami 0; dagilim gecersiz")
    inv = 1.0 / total
    return (p64 * inv[..., None]).astype(np.float32)


def to_cumulative_f32(probs) -> dict[str, np.ndarray]:
    """Dislayici [..., 6] -> C# ``OutcomeDistribution`` alanlari (float32, kirpma dahil)."""
    n = normalize_exclusive_f32(probs)
    nw, ngw, nbw = n[..., 0], n[..., 1], n[..., 2]
    ngl, nbl = n[..., 4], n[..., 5]
    win = _clamp_f32((nw + ngw) + nbw, 0.0, 1.0)
    win_gammon = _clamp_f32(ngw + nbw, 0.0, win)
    win_backgammon = _clamp_f32(nbw, 0.0, win_gammon)
    lose = np.float32(1.0) - win
    lose_gammon = _clamp_f32(ngl + nbl, 0.0, lose)
    lose_backgammon = _clamp_f32(nbl, 0.0, lose_gammon)
    return {
        "win": win,
        "win_gammon": win_gammon,
        "win_backgammon": win_backgammon,
        "lose_gammon": lose_gammon,
        "lose_backgammon": lose_backgammon,
    }


def equity_from_cumulative_f32(win, win_gammon, win_backgammon, lose_gammon, lose_backgammon) -> np.ndarray:
    """C# ``Equity`` ozelligi, **bit duzeyinde** ayni (float32 alanlar, float64 toplam)."""
    win = np.asarray(win, dtype=np.float32)
    win_gammon = np.asarray(win_gammon, dtype=np.float32)
    win_backgammon = np.asarray(win_backgammon, dtype=np.float32)
    lose_gammon = np.asarray(lose_gammon, dtype=np.float32)
    lose_backgammon = np.asarray(lose_backgammon, dtype=np.float32)
    lose = np.float32(1.0) - win
    return (
        (
            (
                (win.astype(np.float64) + win_gammon.astype(np.float64))
                + win_backgammon.astype(np.float64)
            )
            - lose.astype(np.float64)
        )
        - lose_gammon.astype(np.float64)
    ) - lose_backgammon.astype(np.float64)


def equity_from_exclusive_f32(probs) -> np.ndarray:
    """Dislayici [..., 6] -> equity, C# yoluyla (normalize + kumulatif + toplam)."""
    c = to_cumulative_f32(probs)
    return equity_from_cumulative_f32(
        c["win"], c["win_gammon"], c["win_backgammon"], c["lose_gammon"], c["lose_backgammon"]
    )


def flip_f32(probs) -> np.ndarray:
    """C# ``Flip()`` aynasi: dislayici [..., 6] -> karsi perspektif dislayici (float32).

    C# ``Flip`` dislayici siniflari yeniden kurar ve ``FromProbabilities``'a verir;
    bu yuzden sonuc **yeniden normalize edilir** ve float32 yuvarlamasi birikir.
    """
    c = to_cumulative_f32(probs)
    win, win_gammon, win_backgammon = c["win"], c["win_gammon"], c["win_backgammon"]
    lose_gammon, lose_backgammon = c["lose_gammon"], c["lose_backgammon"]
    lose = np.float32(1.0) - win
    raw = np.stack(
        [
            lose - lose_gammon,
            lose_gammon - lose_backgammon,
            lose_backgammon,
            win - win_gammon,
            win_gammon - win_backgammon,
            win_backgammon,
        ],
        axis=-1,
    ).astype(np.float32)
    return normalize_exclusive_f32(raw)
