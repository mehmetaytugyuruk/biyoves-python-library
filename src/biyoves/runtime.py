from __future__ import annotations

import logging
from typing import Any

import onnxruntime as ort

logger = logging.getLogger(__name__)


def create_inference_session(model_path: str) -> Any:
    """Create an ONNX session and fall back to CPU if acceleration fails."""
    providers = ort.get_available_providers()
    try:
        return ort.InferenceSession(model_path, providers=providers)
    except Exception as exc:
        if providers == ["CPUExecutionProvider"] or "CPUExecutionProvider" not in providers:
            raise

        logger.warning(
            "Accelerated ONNX session failed; retrying on CPU: %s",
            exc,
        )
        return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
