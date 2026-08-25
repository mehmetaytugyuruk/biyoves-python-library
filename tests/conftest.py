import pytest
import os


@pytest.fixture
def models_available():
    """Check if ONNX model files are present (needed for integration tests)."""
    package_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'biyoves', 'models')
    required = ['det_500m.onnx', '2d106det.onnx', 'modnet.onnx']
    return all(os.path.exists(os.path.join(package_dir, m)) for m in required)
