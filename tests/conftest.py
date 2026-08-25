import pytest
import numpy as np
import os


@pytest.fixture
def models_available():
    """Check if ONNX model files are present (needed for integration tests)."""
    package_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'biyoves', 'models')
    required = ['det_500m.onnx', '2d106det.onnx', 'modnet.onnx']
    return all(os.path.exists(os.path.join(package_dir, m)) for m in required)


@pytest.fixture
def sample_face_image():
    """Create a synthetic 300x400 BGR image with a simple 'face-like' pattern.

    This is NOT a realistic face — it won't pass face detection.
    Use only for input-validation and pipeline-error-path tests.
    """
    img = np.ones((400, 300, 3), dtype=np.uint8) * 200  # light gray
    return img


@pytest.fixture
def tiny_image():
    """Create an image smaller than the minimum dimension (50x50)."""
    return np.ones((50, 50, 3), dtype=np.uint8) * 128


@pytest.fixture
def tmp_output(tmp_path):
    """Return a temporary output path for saving results."""
    return str(tmp_path / "output.jpg")
