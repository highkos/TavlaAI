"""Faz 6 v3 Bolum 12.3 - Asama C (veri motoru) Python testleri: 63, 64, 65, 67.

C# tarafindaki karsiliklari ``Backgammon.Inference.Tests/StageCDataEngineTests.cs``
(Test 60, 61, 62, 65, 66) icindedir.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

import equity
import shards
import targets
from conftest import ARTIFACTS

REPO_ROOT = Path(__file__).resolve().parents[2]
SELFPLAY_PROJECT = REPO_ROOT / "Backgammon.SelfPlay" / "Backgammon.SelfPlay.csproj"
STAGE_D_SHARDS = REPO_ROOT / "ml" / "runs" / "stage_d" / "shards"
CSHARP_SHARD = ARTIFACTS / "csharp_shard.bgsp"
MODEL = ARTIFACTS / "model_stage_d_v10.onnx"


# --------------------------------------------------------------------------- yardimcilar


def _selfplay_exe() -> Path:
    """``Backgammon.SelfPlay`` calistirilabilir dosyasini bulur; yoksa derler."""
    base = REPO_ROOT / "Backgammon.SelfPlay" / "bin" / "Release" / "net10.0"
    name = "Backgammon.SelfPlay.exe" if sys.platform == "win32" else "Backgammon.SelfPlay"
    exe = base / name
    if exe.is_file():
        return exe

    subprocess.run(
        ["dotnet", "build", str(SELFPLAY_PROJECT), "-c", "Release", "--nologo", "-v", "q"],
        check=True,
        capture_output=True,
        text=True,
    )
    if not exe.is_file():
        pytest.skip(f"Backgammon.SelfPlay derlendi ama calistirilabilir bulunamadi: {exe}")
    return exe


def _run_selfplay(games: int, threads: int, out_dir: Path, seed: int = 7) -> str:
    exe = _selfplay_exe()
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(exe),
        "--model", str(MODEL),
        "--games", str(games),
        "--seed", str(seed),
        "--threads", str(threads),
        "--depth", "0",
        "--log-top", "4",
        "--exploration", "10",
        "--out", str(out_dir),
        "--prefix", "a",
        "--gzip", "false",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, f"self-play basarisiz (threads={threads}):\n{proc.stdout}\n{proc.stderr}"
    return proc.stdout


def _parse(stdout: str, pattern: str) -> float:
    match = re.search(pattern, stdout)
    assert match, f"cikti satiri bulunamadi: {pattern!r}\n{stdout}"
    return float(match.group(1))


# --------------------------------------------------------------------------- Test 63


def test_63_shard_v1_is_still_readable() -> None:
    """Test 63: Faz 4/5 shard'lari (v1) okunur; winner/resultType -> 6 sinifli hedef dogru turetilir."""
    # (a) Her zaman mevcut olan eski C# shard'i (Faz 4'te yazildi).
    assert CSHARP_SHARD.is_file(), f"eski C# shard'i yok: {CSHARP_SHARD}"
    header, games = shards.read_shard(CSHARP_SHARD)
    assert header.format_version == shards.FORMAT_VERSION == 1
    assert header.vector_size == shards.VECTOR_SIZE == 221
    assert games, "eski shard hic oyun icermiyor"

    for game in games:
        if game.is_aborted:
            continue
        targets.validate_result(game.winner, game.result_type)
        for dec in game.decisions:
            if not dec.is_learner or dec.chosen_is_terminal:
                continue
            one_hot = targets.exclusive_target(game.winner, game.result_type, dec.mover)
            assert one_hot.shape == (equity.PROB_COUNT,)
            assert one_hot.sum() == pytest.approx(1.0)
            assert np.count_nonzero(one_hot) == 1, "6 sinifli hedef tek-sicak olmali"
            # Kazanan bakis acisindan equity isareti kazananin lehine olmali.
            e = targets.target_equity(game.winner, game.result_type, dec.mover)
            assert e == pytest.approx(float(game.result_type) * (1 if game.winner == dec.mover else -1))

    # (b) Varsa Faz 4/5 uretim shard'lari da okunmali.
    if not STAGE_D_SHARDS.is_dir():
        pytest.skip("ml/runs/stage_d/shards yok (uretim verisi temizlenmis); eski C# shard'i dogrulandi")

    files = sorted(STAGE_D_SHARDS.rglob("*.bgsp.gz"))
    assert files, "stage_d shard dizini bos"

    total_games = 0
    usable = 0
    for path in files:
        h, gs = shards.read_shard(path)
        assert h.format_version == 1
        assert h.vector_size == 221
        total_games += len(gs)
        for game in gs:
            if game.is_aborted:
                continue
            usable += 1
            targets.validate_result(game.winner, game.result_type)
            assert game.result_points == game.result_type, "kup 1 iken resultPoints == resultType olmali"

    assert total_games > 0
    assert usable > 0, "kullanilabilir (aborted olmayan) oyun yok"


# --------------------------------------------------------------------------- Test 64


def test_64_selfplay_linux_publish_runs(tmp_path: Path) -> None:
    """Test 64: ``dotnet publish -r linux-x64 --self-contained`` ciktisi calisir."""
    out_dir = tmp_path / "linux-x64"
    proc = subprocess.run(
        [
            "dotnet", "publish", str(SELFPLAY_PROJECT),
            "-c", "Release",
            "-r", "linux-x64",
            "--self-contained", "true",
            "-o", str(out_dir),
            "--nologo", "-v", "q",
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, f"linux-x64 yayini basarisiz:\n{proc.stdout}\n{proc.stderr}"

    binary = out_dir / "Backgammon.SelfPlay"
    assert binary.is_file(), "linux-x64 yayininda Backgammon.SelfPlay yok"
    assert binary.read_bytes()[:4] == b"\x7fELF", "yayin ciktisi ELF degil"

    # Calistirma icin bir Linux ortami gerekir.
    runner = _linux_runner(out_dir)
    if runner is None:
        pytest.skip(
            "linux-x64 yayini uretildi ve ELF dogrulandi, ancak bu makinede WSL/Docker yok; "
            "calistirma adimi atlandi (ASSUMPTIONS.md F6-15)."
        )

    shutil.copy2(MODEL, out_dir / MODEL.name)
    cmd = runner + [
        "./Backgammon.SelfPlay",
        "--model", MODEL.name,
        "--games", "2",
        "--seed", "1",
        "--threads", "1",
        "--depth", "0",
        "--out", ".",
        "--prefix", "a",
        "--gzip", "false",
    ]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(out_dir))
    assert run.returncode == 0, f"linux-x64 ciktisi calismadi:\n{run.stdout}\n{run.stderr}"
    assert "oyun/s" in run.stdout


def _linux_runner(out_dir: Path) -> list[str] | None:
    """Linux ikilisini calistirabilecek bir komut on eki dondurur (WSL/Docker), yoksa ``None``."""
    wsl = shutil.which("wsl")
    if wsl:
        probe = subprocess.run([wsl, "-l", "-q"], capture_output=True, text=True)
        if probe.returncode == 0 and probe.stdout.strip():
            return [wsl, "-e"]

    docker = shutil.which("docker")
    if docker:
        probe = subprocess.run([docker, "info"], capture_output=True, text=True)
        if probe.returncode == 0:
            return [
                docker, "run", "--rm",
                "-v", f"{out_dir.as_posix()}:/app",
                "-w", "/app",
                "mcr.microsoft.com/dotnet/runtime:10.0",
            ]

    return None


# --------------------------------------------------------------------------- Test 65


def test_65_shard_has_no_outcome_probs_field() -> None:
    """Test 65 (Python tarafi): shard v1'de finalProbs/outcomeProbs yok; turetme dogru calisir."""
    forbidden = ("final_probs", "outcome_probs", "final_probabilities", "outcome_probabilities")
    for cls in (shards.GameRecord, shards.DecisionRecord):
        for name in forbidden:
            assert not hasattr(cls, name), f"{cls.__name__}.{name} shard v1'de bulunmamali (Faz 6 Bolum 7.1)"

    # 6 sinifli hedef yalnizca winner + resultType'tan turetilmeli.
    for winner in (1, -1):
        for result_type in (1, 2, 3):
            for perspective in (1, -1):
                one_hot = targets.exclusive_target(winner, result_type, perspective)
                assert one_hot.shape == (6,)
                assert one_hot.sum() == pytest.approx(1.0)
                assert np.count_nonzero(one_hot) == 1
                expected_index = (0 if winner == perspective else 3) + (result_type - 1)
                assert int(np.argmax(one_hot)) == expected_index

    # Gidis-donus: yazilan shard'da bu alanlar hic yok ve turetme ayni sonucu veriyor.
    header = shards.ShardHeader(feature_version=1, model_version=1, log_top_candidates=0)
    game = shards.GameRecord(
        game_id=1,
        learner_side=0,
        flags=0,
        cube_value=1,
        winner=-1,
        result_type=2,
        result_points=2,
    )
    game.decisions.append(
        shards.DecisionRecord(
            mover=1,
            flags=shards.DEC_IS_LEARNER,
            candidate_total=1,
            search_value=0.0,
            chosen_vector=np.zeros(221, dtype=np.float32),
        )
    )
    game.decisions.append(
        shards.DecisionRecord(
            mover=-1,
            flags=shards.DEC_IS_LEARNER | shards.DEC_CHOSEN_IS_TERMINAL,
            candidate_total=0,
            search_value=0.0,
        )
    )

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "t65.bgsp"
        shards.write_shard(path, header, [game])
        _, back = shards.read_shard(path)

    assert len(back) == 1
    assert back[0].winner == -1
    assert back[0].result_type == 2
    # Siyah (mover=-1) kazandi -> siyahin bakis acisindan GW.
    assert int(np.argmax(targets.exclusive_target(back[0].winner, back[0].result_type, -1))) == 1
    # Beyaz kaybetti -> beyazin bakis acisindan GL.
    assert int(np.argmax(targets.exclusive_target(back[0].winner, back[0].result_type, 1))) == 4


# --------------------------------------------------------------------------- Test 67


def test_67_selfplay_throughput_is_measured(tmp_path: Path) -> None:
    """Test 67: oyun/sn (thread 1/6/12), bellek tepe noktasi ve disk yazma hizi olculur."""
    if not MODEL.is_file():
        pytest.skip(f"model yok: {MODEL}")

    const_games = 60
    rows: list[tuple[int, float, int, float]] = []

    for threads in (1, 6, 12):
        stdout = _run_selfplay(const_games, threads, tmp_path / f"t{threads}")
        games_per_second = _parse(stdout, r"\(([\d.]+) oyun/s\)")
        peak_mb = int(_parse(stdout, r"peak memory\s*:\s*(\d+) MB"))
        write_mb_s = _parse(stdout, r"disk write rate\s*:\s*([\d.]+) MB/s")

        assert games_per_second > 0.0
        assert peak_mb > 0
        assert write_mb_s > 0.0
        rows.append((threads, games_per_second, peak_mb, write_mb_s))

    # Rapor: ml/runs/ (kalici olmayan kosu ciktilari).
    report_dir = REPO_ROOT / "ml" / "runs" / "stage_c"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Asama C - veri motoru olcumu (Test 67)",
        "",
        f"Oyun sayisi: {const_games} / kosu, model: `{MODEL.name}`, depth 0, log-top 4.",
        "",
        "| thread | oyun/sn | tepe bellek (MB) | disk yazma (MB/s) |",
        "|---|---|---|---|",
    ]
    for threads, gps, peak, write in rows:
        lines.append(f"| {threads} | {gps:.2f} | {peak} | {write:.2f} |")
    lines.append("")
    (report_dir / "throughput.md").write_text("\n".join(lines), encoding="utf-8")

    # Paralel olcekleme iddiasi yalnizca raporlanir; esik iddiasi tasinmaz (Faz 6 Bolum 7.3).
    single = rows[0][1]
    for threads, gps, _, _ in rows[1:]:
        assert gps > 0.0
        print(f"threads={threads}: {gps / single:.2f}x (threads=1'e gore)")
