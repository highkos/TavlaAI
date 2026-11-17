"""pytest yapilandirmasi: `ml/` paketini sys.path'e ekler."""

from __future__ import annotations

import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

ARTIFACTS = ML_DIR / "artifacts"
MODEL_PATH = ARTIFACTS / "model_v1.onnx"
PARITY_PATH = ARTIFACTS / "model_v1.onnx.parity.json"
GOLDEN_VECTOR_PATH = ML_DIR.parent / "Backgammon.Tests" / "ReferenceData" / "vector_golden.json"
GOLDEN_EQUITY_PATH = ML_DIR.parent / "Backgammon.Tests" / "ReferenceData" / "equity_golden.json"


def pytest_configure(config) -> None:
    """Faz 6 Asama D: ``slow`` isareti (gercek egitim kosusu yapan testler)."""
    config.addinivalue_line(
        "markers", "slow: gercek egitim kosusu yapar (dakikalar surer)"
    )