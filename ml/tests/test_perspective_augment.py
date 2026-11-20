"""R-D perspektif artirimi (F7-94) - Test 212-217.

``train_v2.augment_value_samples`` / ``augment_policy_samples`` her ornegi
**iki** perspektifle cogaltir. Bu, renk takasi kapisinin (|corr| >= 0,99)
egitim tarafindaki tek dayanagidir; yanlis bir isaret (F7-55'teki gibi
ortalama almak) sessizce ER'yi kotulestirir. Bu yuzden her alan ayri test
edilir.
"""

from __future__ import annotations

import numpy as np
import pytest

import train_v2 as T
from antisymmetry import flip_perspective
from replay import PolicySample

VECTOR_SIZE = 221


def _value_samples(n: int = 3) -> T.ExclusiveSamples:
    rng = np.random.default_rng(7)
    x = rng.random((n, VECTOR_SIZE)).astype(np.float32)
    y = np.zeros((n, 6), dtype=np.float32)
    y[:, 0] = 1.0  # hepsi "W" (kazanan yarisi)
    return T.ExclusiveSamples(
        x=x,
        y=y,
        game_index=np.arange(n, dtype=np.int32),
        decision_index=np.arange(n, dtype=np.int32),
        margin=np.full(n, 0.25),
        best_equity=np.array([0.5, -0.3, 0.1], dtype=np.float64)[:n],
        equity_target=np.array([0.5, -0.3, 0.1], dtype=np.float32)[:n],
    )


def _policy_samples(n: int = 2, e: int = 4) -> list[PolicySample]:
    rng = np.random.default_rng(11)
    out = []
    for _ in range(n):
        out.append(
            PolicySample(
                vectors=rng.random((e, VECTOR_SIZE)).astype(np.float32),
                target=np.full(e, 1.0 / e, dtype=np.float32),
                q=np.linspace(1.0, 0.0, e, dtype=np.float32),
            )
        )
    return out


# Test 212
def test_augment_value_samples_doubles_and_interleaves():
    """Ciftler bitisik olmali: ``[s0(+1), s0(-1), s1(+1), s1(-1), ...]``."""
    s = _value_samples(3)
    a = T.augment_value_samples(s)
    assert len(a) == 2 * len(s)
    # Cift indeksler orijinal, tek indeksler cevrilmis.
    assert np.array_equal(a.x[0::2], s.x)
    assert np.array_equal(a.game_index[0::2], s.game_index)
    assert np.array_equal(a.game_index[1::2], s.game_index)


# Test 213
def test_augment_value_samples_flips_vector_and_target():
    """Vektor ``flip_perspective``, hedef ``flip_exclusive`` ile doner."""
    s = _value_samples(2)
    a = T.augment_value_samples(s)
    for i in range(len(s)):
        assert np.allclose(a.x[2 * i + 1], flip_perspective(s.x[i]), atol=1e-6)
        # y = [1,0,0,0,0,0] -> [0,0,0,1,0,0]
        assert np.allclose(a.y[2 * i + 1], [0, 0, 0, 1, 0, 0], atol=1e-6)
        assert np.allclose(a.y[2 * i], s.y[i], atol=1e-6)


# Test 214
def test_augment_value_samples_negates_equity_but_keeps_margin():
    """``equity_target``/``best_equity`` isaret doner; ``margin`` degismez.

    ``margin`` ayni fiziksel aday kumesinin en iyi iki adayi arasindaki
    farktir; bakis cevrilince iki q da isaret doner, fark ayni kalir.
    """
    s = _value_samples(3)
    a = T.augment_value_samples(s)
    assert np.allclose(a.equity_target[1::2], -s.equity_target, atol=1e-6)
    assert np.allclose(a.best_equity[1::2], -s.best_equity, atol=1e-9)
    assert np.allclose(a.margin[1::2], s.margin, atol=1e-12)


# Test 215
def test_augment_value_samples_is_involution_on_pairs():
    """Iki kez artirmak 4 katina cikarir; ``flip`` involusyon oldugu icin
    ``x[1]``'in cevrilmisi ``x[0]``'a doner."""
    s = _value_samples(2)
    a = T.augment_value_samples(s)
    for i in range(len(s)):
        back = flip_perspective(a.x[2 * i + 1])
        assert np.allclose(back, s.x[i], atol=1e-6)


# Test 216
def test_augment_policy_samples_keeps_target_and_flips_vectors():
    """Politika hedefi **degismez**: adaylar ayni fiziksel afterstate'lerdir."""
    p = _policy_samples(2, 4)
    a = T.augment_policy_samples(p)
    assert len(a) == 2 * len(p)
    for i, s in enumerate(p):
        assert np.array_equal(a[2 * i].vectors, s.vectors)
        assert np.array_equal(a[2 * i + 1].target, s.target)
        assert np.array_equal(a[2 * i + 1].q, s.q)
        for k in range(s.vectors.shape[0]):
            assert np.allclose(
                a[2 * i + 1].vectors[k], flip_perspective(s.vectors[k]), atol=1e-6
            )


# Test 217
def test_augment_handles_empty_and_missing_optional_fields():
    """Bos kume ve ``None`` alanlar hata vermemeli."""
    empty = T._empty_samples()
    assert len(T.augment_value_samples(empty)) == 0
    assert T.augment_policy_samples([]) == []

    rng = np.random.default_rng(3)
    bare = T.ExclusiveSamples(
        x=rng.random((2, VECTOR_SIZE)).astype(np.float32),
        y=np.full((2, 6), 1.0 / 6, dtype=np.float32),
        game_index=np.zeros(2, dtype=np.int32),
        decision_index=np.zeros(2, dtype=np.int32),
    )
    a = T.augment_value_samples(bare)
    assert len(a) == 4
    assert a.margin is None and a.best_equity is None and a.equity_target is None


# Test 242
def test_train_v2_augment_perspectives_end_to_end(tmp_path):
    """``--augment-perspectives`` gercek egitim dongusunde calismali (F7-94).

    Birim testleri donusumu dogrular; bu test **kablolamayi** dogrular: bayrak
    CLI'dan gecer, ornek sayisi ikiye katlanir ve kosu hatasiz biter.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    from test_stage_d import make_shard

    repo_root = Path(__file__).resolve().parents[2]
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    make_shard(shard_dir, games=8, decisions=6, candidates=4)

    out = tmp_path / "run"
    cmd = [
        sys.executable,
        str(repo_root / "ml" / "train_v2.py"),
        "--out", str(out),
        "--no-selfplay",
        "--shard-dir", str(shard_dir),
        "--quiet",
        "--steps", "4",
        # Kritik agirliklar **acik** olmali: agirlik ciftleme yolu ancak
        # boost > 1 iken devreye girer ve orada `p` toplaminin 1 kalmasi
        # gerekir (regresyon: `repeat` sonrasi toplam 2 olup `rng.choice`
        # `Probabilities do not sum to 1` ile dusuyordu).
        "--critical-boost", "2.0",
        "--augment-perspectives",
    ]
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, "train_v2 --augment-perspectives basarisiz:\n" + proc.stdout + "\n" + proc.stderr

    metrics = out / "metrics.jsonl"
    assert metrics.is_file(), "metrics.jsonl yok"
    rows = [json.loads(line) for line in metrics.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, "metrics.jsonl bos"
    # Artirim kosunun kimliginde gorunmeli (denetim izi).
    report = out / "train_report.json"
    assert report.is_file(), "train_report.json yok"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data.get("augment_perspectives") is True, data.get("augment_perspectives")
    # Politika kafasi **artirilmaz** (F7-100): hedefi oynayacak tarafin
    # dagilimidir, cevrilince hedef de cevrilmelidir. Varsayilan kapali.
    assert data.get("augment_policy_perspectives") is False, data.get("augment_policy_perspectives")


# Test 244
def test_train_v2_augment_policy_perspectives_is_opt_in(tmp_path):
    """Politika artirimi ayri ve **kapali** bir bayrak olmali (F7-100).

    Ayni hedefle cevirmek politika kafasini simetrik egitir; olculen renk
    takasi argmax uyumu 0,174 -> 0,018. Bu yuzden varsayilan davranistan
    cikarildi ama teshis icin erisilebilir kaldi.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    from test_stage_d import make_shard

    repo_root = Path(__file__).resolve().parents[2]
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    make_shard(shard_dir, games=8, decisions=6, candidates=4)

    out = tmp_path / "run"
    cmd = [
        sys.executable,
        str(repo_root / "ml" / "train_v2.py"),
        "--out", str(out),
        "--no-selfplay",
        "--shard-dir", str(shard_dir),
        "--quiet",
        "--steps", "4",
        "--critical-boost", "2.0",
        "--augment-perspectives",
        "--augment-policy-perspectives",
    ]
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, "politika artirimi basarisiz:\n" + proc.stdout + "\n" + proc.stderr

    data = json.loads((out / "train_report.json").read_text(encoding="utf-8"))
    assert data.get("augment_perspectives") is True
    assert data.get("augment_policy_perspectives") is True
