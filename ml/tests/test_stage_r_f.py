"""R-F kabul testleri: R-T19 ... R-T22 (Faz 7 v2.5 §5).

R-F'nin kabul olcutu "Test R-T19...R-T22 yesil"dir. Bu dosya o dort testi
tek yerde, spec'teki adlariyla tutar; ``test_gnubg_ladder.py`` ve
``test_gnubg_rollout.py`` ilgili modullerin birim testleridir.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import ppg_measure  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
LADDER = ARTIFACTS / "gnubg_ladder.json"
DEEP_LADDERS = (
    ARTIFACTS / "gnubg_ladder_deep.json",
    ARTIFACTS / "gnubg_ladder_deep4.json",
)
REPORT = ARTIFACTS / "stage_r_f_report.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# R-T19 Ladder_Measured
# ----------------------------------------------------------------------


def test_r_t19_ladder_measured() -> None:
    """Her basamak ya olculmus ya da **gerekcesiyle** olculemez olmali."""
    data = _load(LADDER)
    assert data["ladderVersion"] >= 2
    rungs = data["rungs"]
    assert rungs, "merdiven bos olamaz"

    measured = [r for r in rungs if r["measurable"]]
    unmeasurable = [r for r in rungs if not r["measurable"]]
    assert measured, "en az bir basamak olculmus olmali"
    assert unmeasurable, "2-ply ve otesi olculemez olarak isaretlenmeli"

    for rung in measured:
        assert rung["count"] > 0
        assert rung["mean"] is not None and math.isfinite(rung["mean"])
        assert rung["sigma"] is not None and rung["sigma"] > 0.0
        assert rung["ciLow"] <= rung["mean"] <= rung["ciHigh"]
        assert rung["ciLow"] >= 0.0
        assert 0.0 <= rung["exactMatchRate"] <= 1.0

    for rung in unmeasurable:
        assert rung["mean"] is None
        assert rung["ciLow"] is None and rung["ciHigh"] is None
        assert rung.get("reason"), "olculemez basamak gerekce tasimali"

    # Cozunurluk tabani: olculen en kucuk ER, olcumun alt sinirini verir.
    floor = min(r["mean"] for r in measured)
    assert 0.0 < floor < 0.01


# ----------------------------------------------------------------------
# R-T20 Ladder_NoSelfReferee
# ----------------------------------------------------------------------


@pytest.mark.parametrize("path", (LADDER,) + DEEP_LADDERS, ids=lambda p: p.name)
def test_r_t20_ladder_no_self_referee(path: Path) -> None:
    """Hakem kendi kendini olcemez: ``playerPlies < refereePlies``."""
    data = _load(path)
    for rung in data["rungs"]:
        player = rung["playerPlies"]
        referee = rung["refereePlies"]
        if rung["measurable"]:
            assert player < referee, (
                "%s: %d-ply oyuncu %d-ply hakemle olculemez"
                % (path.name, player, referee)
            )
        else:
            assert player >= referee
            assert rung.get("reason")


# ----------------------------------------------------------------------
# R-T21 Equivalence_Test
# ----------------------------------------------------------------------


def test_r_t21_equivalence_test_direction() -> None:
    """``H0: ppg_fark <= -m`` dogru yonde calismali (sentetik oyunlar)."""
    margin = 0.1115

    # Fark marjdan kucuk ve GA -m'in ustunde -> H0 reddedilir.
    assert ppg_measure.equivalence_verdict(-0.05, -0.10, 0.00, margin) == "esdeger"
    assert ppg_measure.equivalence_verdict(0.20, 0.10, 0.30, margin) == "esdeger"

    # Fark marjdan buyuk ve GA -m'in altinda -> kotuluk kanitlandi.
    assert (
        ppg_measure.equivalence_verdict(-0.2445, -0.3055, -0.1835, margin)
        == "daha-kotu"
    )

    # GA esigi kesiyor -> gucsuz.
    assert (
        ppg_measure.equivalence_verdict(-0.10, -0.30, 0.10, margin)
        == "esdegerlik-kanitlanmadi"
    )

    # Sinirda: alt sinir tam -m ise esik dislanmaz.
    assert (
        ppg_measure.equivalence_verdict(-0.05, -margin, 0.00, margin)
        == "esdegerlik-kanitlanmadi"
    )

    assert set(ppg_measure.EQUIVALENCE_LABELS) == {
        "esdeger",
        "esdegerlik-kanitlanmadi",
        "daha-kotu",
    }


def test_r_t21_equivalence_test_rejects_bad_input() -> None:
    with pytest.raises(ppg_measure.PpgError):
        ppg_measure.equivalence_verdict(-0.1, -0.2, 0.0, 0.0)
    with pytest.raises(ppg_measure.PpgError):
        ppg_measure.equivalence_verdict(-0.5, -0.2, 0.0, 0.1115)


def test_r_t21_required_games_matches_spec() -> None:
    """Onaylanmis 4337 ile standart formül ayni buyuklukte olmali."""
    computed = ppg_measure.required_games(0.1115, 2.9960)
    assert abs(computed - 4337) / 4337 < 0.05
    assert ppg_measure.required_games(0.2, 2.9960) < computed


# ----------------------------------------------------------------------
# R-T22 Final_Report_ThreeLines
# ----------------------------------------------------------------------


def test_r_t22_final_report_three_lines() -> None:
    """Nihai rapor **tam olarak uc satir**, her biri butce + sure tasir."""
    report = _load(REPORT)
    lines = report["lines"]
    assert list(lines) == ["moveQuality", "cube", "gameStrength"]

    for name, line in lines.items():
        assert line.get("budget"), "%s: butce yazilmali" % name
        assert isinstance(line.get("elapsedSeconds"), int)
        assert line["elapsedSeconds"] > 0
        assert line.get("verdictLabel") in ppg_measure.EQUIVALENCE_LABELS or (
            line.get("verdictLabel") is None
        )

    assert report["elapsedSecondsTotal"] == sum(
        line["elapsedSeconds"] for line in lines.values()
    )

    # Oyun gucu satiri, yardimcinin verdict'i ile ayni olmali.
    gs = lines["gameStrength"]
    assert gs["verdictLabel"] == ppg_measure.equivalence_verdict(
        gs["ppg"], gs["ppgCiLow"], gs["ppgCiHigh"], report["equivalenceMarginPpg"]
    )
    assert gs["verdictLabel"] == "daha-kotu"

    # Uc satirin hicbiri butcesini karsilamadi; rapor bunu acikca soylemeli.
    assert report["verdict"] in {"karşılanmadı", "karsilanmadi"}
    assert report["requiredGames"] == 4337
    assert gs["requiredGamesFormula"] == ppg_measure.required_games(
        report["equivalenceMarginPpg"], report["ppgSigma"]
    )
