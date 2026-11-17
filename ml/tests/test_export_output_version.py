"""Faz 5 §8 Test 36 + Faz 6 §5.4: ONNX `output_version` metadata'si export ve handle tarafinda tutarli."""

from __future__ import annotations

import re
from pathlib import Path

import onnx
import pytest

REPO = Path(__file__).resolve().parent.parent.parent
EXPORT_PY = REPO / "ml" / "export_onnx.py"
HANDLE_CS = REPO / "Backgammon.Inference" / "OnnxModelHandle.cs"
MODEL_V1 = REPO / "ml" / "runs" / "stage_d" / "onnx" / "model_v5.onnx"
FIXTURE_V1 = REPO / "ml" / "artifacts" / "model_v2.onnx"
FIXTURE_V2 = REPO / "ml" / "artifacts" / "model_output_version_2.onnx"

PROB_ORDER = "W,GW,BW,L,GL,BL"


def _export_version() -> int:
    text = EXPORT_PY.read_text(encoding="utf-8")
    match = re.search(r"^OUTPUT_VERSION\s*=\s*(\d+)", text, re.MULTILINE)
    assert match is not None, "export_onnx.py icinde OUTPUT_VERSION bulunamadi"
    return int(match.group(1))


def _handle_supported_version() -> int:
    text = HANDLE_CS.read_text(encoding="utf-8")
    match = re.search(r"SupportedOutputVersion\s*=\s*(\d+)", text)
    assert match is not None, "OnnxModelHandle.cs icinde SupportedOutputVersion bulunamadi"
    return int(match.group(1))


def _metadata(path: Path) -> dict[str, str]:
    model = onnx.load(str(path))
    return {entry.key: entry.value for entry in model.metadata_props}


def test_export_output_version_constant() -> None:
    assert _export_version() == 2, "Faz 6 6 cikti li deger kafasi -> output_version = 2"


def test_handle_supported_output_version() -> None:
    assert _handle_supported_version() == 2


def test_export_and_handle_agree() -> None:
    assert _export_version() == _handle_supported_version(), (
        "export_onnx.py ve OnnxModelHandle.cs ayni output_version'i bildirmeli"
    )


@pytest.mark.parametrize("model_path", [MODEL_V1, FIXTURE_V1])
def test_legacy_models_declare_version_one(model_path: Path) -> None:
    """Faz 4/5 modelleri `output_version = 1` bildirir ve o sozlesmeyle kalir."""
    if not model_path.exists():
        pytest.skip(f"model yok: {model_path}")

    metadata = _metadata(model_path)
    assert metadata.get("output_version") == "1", (
        f"{model_path.name}: output_version = {metadata.get('output_version')!r}, beklenen '1'"
    )


def test_v2_fixture_declares_version_two() -> None:
    if not FIXTURE_V2.exists():
        pytest.skip(f"model yok: {FIXTURE_V2}")

    metadata = _metadata(FIXTURE_V2)
    assert metadata.get("output_version") == "2"
    assert metadata.get("prob_order") == PROB_ORDER
    assert metadata.get("prob_encoding") == "exclusive"


def test_v2_fixture_io_contract() -> None:
    """`probs` [B,6] + `policy_logit` [B,1]; `value` ciktisi yok (Faz 6 §5.4)."""
    if not FIXTURE_V2.exists():
        pytest.skip(f"model yok: {FIXTURE_V2}")

    model = onnx.load(str(FIXTURE_V2))
    outputs = {o.name: [d.dim_param or d.dim_value for d in o.type.tensor_type.shape.dim]
               for o in model.graph.output}
    assert set(outputs) == {"probs", "policy_logit"}, outputs
    assert outputs["probs"][1] == 6, outputs
    assert outputs["policy_logit"][1] == 1, outputs
    assert outputs["probs"][0] == "batch", "batch ekseni dinamik olmali"


def test_handle_rejects_newer_output_version() -> None:
    text = HANDLE_CS.read_text(encoding="utf-8")
    assert "NotSupportedException" in text, (
        "OnnxModelHandle desteklenmeyen output_version icin NotSupportedException atmalidir"
    )
    assert "output_version" in text