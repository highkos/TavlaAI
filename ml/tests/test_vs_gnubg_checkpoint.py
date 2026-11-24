"""F7-116: ppg kosusunun denetim noktasi (checkpoint) davranisi (Test 338-341).

Uzun ppg kosulari saatler surer ve tek bir surec cokmesi tum olcumu
kaybettirir. Bu yuzden her **cift** tamamlandiginda sonuc JSONL olarak
diske yazilir ve kosu kaldigi yerden devam eder. Bu dosya, devam
mantiginin sessiz bozulmalara karsi korumali oldugunu dogrular:

* imza (model/yol/ply/tohum) uyusmazsa kosu **hata verir**, karistirmaz;
* yarim yazilmis son satir atlanir ve o cift yeniden oynanir;
* devam eden kosu, sifirdan kosuyla **birebir ayni** sonucu verir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ML = HERE.parent
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

import vs_gnubg  # noqa: E402


def _key(**overrides):
    base = {
        "model_path": Path("m.onnx"),
        "path": "search1",
        "gnubg_plies": 2,
        "seed": 2026,
        "max_plies": 200,
    }
    base.update(overrides)
    return vs_gnubg._checkpoint_key(**base)


def test_338_checkpoint_key_covers_run_identity():
    """Imza, kosuyu belirleyen **tum** alanlari ve bicim surumunu tasir."""
    key = _key()
    assert key["checkpointVersion"] == vs_gnubg.CHECKPOINT_VERSION
    assert key["model"] == "m.onnx"
    assert key["path"] == "search1"
    assert key["gnubgPlies"] == 2
    assert key["seed"] == 2026
    assert key["maxPlies"] == 200
    # Farkli her alan farkli imza uretmeli.
    assert _key(seed=1) != key
    assert _key(path="policy") != key
    assert _key(gnubg_plies=0) != key
    assert _key(max_plies=100) != key
    assert _key(model_path=Path("n.onnx")) != key


def test_339_load_checkpoint_skips_truncated_tail(tmp_path):
    """Yarim yazilmis son satir atlanir; tamamlanan ciftler korunur."""
    path = tmp_path / "ckpt.jsonl"
    key = _key()
    good = {
        "key": key,
        "pair": 0,
        "scores": [1.0, -2.0],
        "plies": [40, 55],
        "finished": [True, True],
    }
    path.write_text(
        json.dumps(good) + "\n" + '{"key": {"checkpointVersion": 1}, "pair": 1, "sco',
        encoding="utf-8",
    )
    done = vs_gnubg._load_checkpoint(path, key)
    assert list(done) == [0]
    assert done[0] == ([1.0, -2.0], [40, 55], [True, True])


def test_340_load_checkpoint_rejects_foreign_run(tmp_path):
    """Baska bir kosunun kayitlari sessizce karistirilmaz: hata verilir."""
    path = tmp_path / "ckpt.jsonl"
    record = {
        "key": _key(seed=7),
        "pair": 0,
        "scores": [0.0, 0.0],
        "plies": [1, 1],
        "finished": [True, True],
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(vs_gnubg.MatchError):
        vs_gnubg._load_checkpoint(path, _key())


def test_341_run_match_resumes_from_checkpoint(tmp_path, monkeypatch):
    """Devam eden kosu, sifirdan kosuyla ayni sonucu verir ve isi tekrarlamaz."""
    calls: list[int] = []

    def fake_play_pair(task, our_choose, gnubg_choose, max_plies):
        pair, _seed = task
        calls.append(pair)
        return ([float(pair), -float(pair)], [10, 10], [True, True])

    class _DummySession:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

    class _DummyScorer:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(vs_gnubg, "_play_pair", fake_play_pair)
    monkeypatch.setattr(vs_gnubg.gnubg_er, "GnubgSession", _DummySession)
    monkeypatch.setattr(vs_gnubg.gnubg_er, "OnnxScorer", _DummyScorer)
    monkeypatch.setattr(vs_gnubg, "_our_chooser", lambda scorer, path: (lambda case: 0))
    monkeypatch.setattr(vs_gnubg, "_gnubg_chooser", lambda session, plies: (lambda case: 0))

    ckpt = tmp_path / "ckpt.jsonl"
    common = dict(
        model_path=Path("m.onnx"),
        games=6,
        path="search1",
        gnubg_plies=2,
        seed=2026,
        workers=1,
        checkpoint=ckpt,
    )

    first = vs_gnubg.run_match(**common)
    assert calls == [0, 1, 2]
    assert first["resumedPairs"] == 0
    assert first["pairs"] == 3

    calls.clear()
    second = vs_gnubg.run_match(**common)
    assert calls == []
    assert second["resumedPairs"] == 3
    assert second["ppg"] == pytest.approx(first["ppg"])
    assert second["wins"] == first["wins"]
    assert second["pairedDiffMean"] == pytest.approx(first["pairedDiffMean"])

    calls.clear()
    third = vs_gnubg.run_match(**{**common, "restart": True})
    assert calls == [0, 1, 2]
    assert third["resumedPairs"] == 0
    assert third["ppg"] == pytest.approx(first["ppg"])
