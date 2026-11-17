"""Faz 6 v3 Bolum 12.6 - Asama F (kup ve mac ustaligi) olcum testleri: 84, 87, 89.

C# tarafindaki davranis testleri (83, 85, 86, 88) `Backgammon.Tests/Cube/CubePowerTests.cs`
icindedir. Burada yalnizca **olcum** testleri bulunur; hepsi onceden uretilmis artefaktlari
okur, boylece test paketi gnubg'ye veya uzun mac simulasyonlarina bagimli olmaz.

Artefaktlar:

    ml/artifacts/stage_f_cube_gnubg.json   -> `ml/cube_bench.py` (gnubg-cli ile)
    ml/artifacts/stage_f_match_gain.json   -> `Backgammon.MatchBench match-gain`

Artefakt yoksa testler `skip` olur (temiz bir checkout'ta uretilmemis olabilir).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import ARTIFACTS

REPO_ROOT = Path(__file__).resolve().parents[2]

CUBE_GNUBG = ARTIFACTS / "stage_f_cube_gnubg.json"
MATCH_GAIN = ARTIFACTS / "stage_f_match_gain.json"

#: Faz 6 v3 §13.3 kabul kapilari.
DOUBLE_AGREEMENT_GATE = 0.75
EQUITY_MEAN_ABS_DIFF_GATE = 1.2063

#: Faz 6 v3 §12.6 Test 87: hedef (kapi degil).
MATCH_AWARE_TARGET = 0.45

#: Test 89: kup agi yalnizca uyum bu esigin altindaysa devreye girer.
CUBE_NET_TRIGGER = 0.75


# --------------------------------------------------------------------------- yardimcilar


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"artefakt yok: {path.name}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    syy = sum((b - my) ** 2 for _, b in pairs)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return sxy / ((sxx ** 0.5) * (syy ** 0.5))


def cube_summary(plies: int = 2, variant: str = "diceAveraged") -> dict:
    """`stage_f_cube_gnubg.json` uzerinden uyum metriklerini yeniden hesaplar.

    `ml/cube_bench.py` ile **ayni** filtre: atlanmis pozisyonlar, gnubg hatasi olan
    pozisyonlar ve `evaluated = false` kayitlar disarida kalir.
    """
    data = _load(CUBE_GNUBG)
    key = f"gnubg{plies}"
    valid = [
        r
        for r in data["cases"]
        if not r.get("skipped")
        and "error" not in r.get(key, {})
        and r.get(key, {}).get("shouldDouble") is not None
        and r.get(variant, {}).get("evaluated", True)
    ]
    n = len(valid)
    assert n > 0, "karsilastirilabilir pozisyon yok"

    both_double = sum(1 for r in valid if r[key]["shouldDouble"] and r[variant]["shouldDouble"])
    both_nodouble = sum(
        1 for r in valid if not r[key]["shouldDouble"] and not r[variant]["shouldDouble"]
    )
    both_take = sum(1 for r in valid if r[key]["shouldTake"] and r[variant]["shouldTake"])
    both_pass = sum(1 for r in valid if not r[key]["shouldTake"] and not r[variant]["shouldTake"])

    pairs = [
        (r[variant]["equityNoDouble"], r[key]["cubelessEquity"])
        for r in valid
        if "cubelessEquity" in r[key]
    ]
    mean_abs = sum(abs(a - b) for a, b in pairs) / len(pairs) if pairs else None

    return {
        "n": n,
        "doubleAgreement": (both_double + both_nodouble) / n,
        "takeAgreement": (both_take + both_pass) / n,
        "equityCorrelation": _pearson(pairs),
        "equityMeanAbsDiff": mean_abs,
        "oursOnlyDouble": sum(
            1 for r in valid if r[variant]["shouldDouble"] and not r[key]["shouldDouble"]
        ),
        "gnubgOnlyDouble": sum(
            1 for r in valid if r[key]["shouldDouble"] and not r[variant]["shouldDouble"]
        ),
    }


# --------------------------------------------------------------------------- Test 84


def test_84_cube_advisor_dice_averaged_is_accurate() -> None:
    """Test 84: zar-ortalamali kup karari gnubg 2-ply ile >= %75 uyusmali.

    Kapi (v3 §13.3): ciftleme uyumu >= 0,75 **ve** ortalama |delta| < 1,2063.
    """
    s = cube_summary(plies=2, variant="diceAveraged")

    assert s["doubleAgreement"] >= DOUBLE_AGREEMENT_GATE, (
        f"ciftleme uyumu {s['doubleAgreement']:.4f} < {DOUBLE_AGREEMENT_GATE} "
        f"(n={s['n']}, bizim-only={s['oursOnlyDouble']}, gnubg-only={s['gnubgOnlyDouble']})"
    )
    assert s["equityMeanAbsDiff"] < EQUITY_MEAN_ABS_DIFF_GATE, (
        f"ortalama |delta| {s['equityMeanAbsDiff']:.4f} >= {EQUITY_MEAN_ABS_DIFF_GATE}"
    )
    assert s["equityCorrelation"] is not None and s["equityCorrelation"] > 0.5, (
        f"equity korelasyonu {s['equityCorrelation']} cok dusuk"
    )

    single = cube_summary(plies=2, variant="singleRecord")
    assert s["doubleAgreement"] > single["doubleAgreement"], (
        f"diceAveraged {s['doubleAgreement']:.4f} <= "
        f"singleRecord {single['doubleAgreement']:.4f}"
    )
    assert s["equityMeanAbsDiff"] < single["equityMeanAbsDiff"], (
        f"diceAveraged |delta| {s['equityMeanAbsDiff']:.4f} >= "
        f"singleRecord {single['equityMeanAbsDiff']:.4f}"
    )


# --------------------------------------------------------------------------- Test 87


def test_87_match_aware_gain_is_measured() -> None:
    """Test 87: 2-away'de mac-farkinda degerlendirme kazanma oranini artirmali.

    Hedef (kapi degil): matchAware kazanma orani >= %45. Ayrica matchAware, ayni
    tohumlarla oynanan matchAware=false hucresinden **daha kotu olmamali**.
    """
    data = _load(MATCH_GAIN)
    cells = {(c["matchLength"], c["matchAware"]): c for c in data["cells"]}

    assert (2, True) in cells, "2-away matchAware hucresi yok"
    aware = cells[(2, True)]
    plain = cells[(2, False)]

    assert aware["games"] >= 400, f"2-away hucresi {aware['games']} oyun (>= 400 beklenir)"
    assert aware["winRate"] >= MATCH_AWARE_TARGET, (
        f"2-away matchAware kazanma orani {aware['winRate']:.4f} < {MATCH_AWARE_TARGET}"
    )
    assert aware["winRate"] >= plain["winRate"] - 2.0 * aware["winRateStdError"], (
        f"matchAware {aware['winRate']:.4f} matchAware=false {plain['winRate']:.4f} "
        f"degerinden anlamli olcude kotu"
    )


# --------------------------------------------------------------------------- Test 89


def test_89_cube_net_only_if_needed() -> None:
    """Test 89: ayri bir kup agi yalnizca uyum esigin altindaysa devreye girer.

    Uyum esigin ustundeyse hicbir kup-agi artefakti bulunmamali; altindaysa
    bulunmali. Bu, "gereksiz karmasiklik ekleme" kuralinin olculebilir hali.
    """
    s = cube_summary(plies=2, variant="diceAveraged")
    needs_cube_net = s["doubleAgreement"] < CUBE_NET_TRIGGER

    cube_net_artifacts = sorted(ARTIFACTS.glob("cube_net*.onnx"))

    if needs_cube_net:
        assert cube_net_artifacts, (
            f"ciftleme uyumu {s['doubleAgreement']:.4f} < {CUBE_NET_TRIGGER}: "
            "kup agi gerekli ama artefakt yok"
        )
    else:
        assert not cube_net_artifacts, (
            f"ciftleme uyumu {s['doubleAgreement']:.4f} >= {CUBE_NET_TRIGGER}: "
            f"kup agi gereksiz, ama bulundu: {[p.name for p in cube_net_artifacts]}"
        )
