"""
BiyoVes test suite.

Unit tests run without models (input validation, API surface).
Integration tests require ONNX models and are skipped if models are absent.
"""
import os
import sys
import numpy as np
import cv2
import pytest

# Ensure local source is importable
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import biyoves
from biyoves import BiyoVes, create_image


# ---------------------------------------------------------------------------
# 1. Version & package metadata
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_is_string(self):
        assert isinstance(biyoves.__version__, str)

    def test_version_matches_semver(self):
        parts = biyoves.__version__.split('.')
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_all_exports(self):
        assert "BiyoVes" in biyoves.__all__
        assert "create_image" in biyoves.__all__


# ---------------------------------------------------------------------------
# 2. Input validation (no models needed)
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_no_image_path_raises(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        bv = BiyoVes(image_path=None)
        with pytest.raises(ValueError, match="No image path"):
            bv.create_image()

    def test_nonexistent_file_raises(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        bv = BiyoVes("nonexistent_photo_12345.jpg")
        with pytest.raises(FileNotFoundError):
            bv.create_image()

    def test_set_image_changes_path(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        bv = BiyoVes("initial.jpg")
        bv.set_image("updated.jpg")
        assert bv.image_path == "updated.jpg"


# ---------------------------------------------------------------------------
# 3. Photo type & layout validation
# ---------------------------------------------------------------------------

class TestPhotoSpecs:
    def test_invalid_photo_type_returns_none(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        dummy = np.ones((300, 300, 3), dtype=np.uint8) * 200
        result = gen.process_photo(dummy, photo_type="invalid_type")
        assert result is None

    def test_all_photo_types_have_specs(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        expected = {"biyometrik", "vesikalik", "abd_vizesi", "schengen"}
        assert set(gen.PHOTO_SPECS.keys()) == expected

    def test_photo_specs_have_required_keys(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        for name, spec in gen.PHOTO_SPECS.items():
            assert 'w' in spec, f"{name} missing 'w'"
            assert 'h' in spec, f"{name} missing 'h'"
            assert 'face_h' in spec, f"{name} missing 'face_h'"
            assert 'top_margin' in spec, f"{name} missing 'top_margin'"


# ---------------------------------------------------------------------------
# 4. Layout generator (no models needed)
# ---------------------------------------------------------------------------

class TestLayout:
    def test_invalid_layout_returns_none(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        result = lg.generate_layout(dummy, layout_type="invalid")
        assert result is None

    def test_2li_layout_shape(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        result = lg.generate_layout(dummy, layout_type="2li")
        assert result is not None
        # 2li = 2 rows × 1 col → height = 2 × img_h, width = 1 × img_w
        assert result.shape == (400, 150, 3)

    def test_4lu_layout_shape(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        result = lg.generate_layout(dummy, layout_type="4lu")
        assert result is not None
        # 4lu = 2 rows × 2 cols → height = 2 × img_h, width = 2 × img_w
        assert result.shape == (400, 300, 3)

    def test_layout_with_photo_spec(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        spec = {"w": 50, "h": 60}  # mm
        result = lg.generate_layout(dummy, layout_type="2li", photo_spec=spec)
        assert result is not None
        # Canvas dimensions should be based on spec, not input image
        expected_w = int(50 * lg.PIXELS_PER_MM)
        expected_h = int(60 * lg.PIXELS_PER_MM) * 2  # 2 rows
        assert result.shape[1] == expected_w
        assert result.shape[0] == expected_h

    def test_6li_layout_shape(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        result = lg.generate_layout(dummy, layout_type="6li")
        assert result is not None
        # 6li = 3 rows × 2 cols
        assert result.shape == (600, 300, 3)

    def test_8li_layout_shape(self):
        from biyoves.layout import PrintLayoutGenerator
        lg = PrintLayoutGenerator()
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 255
        result = lg.generate_layout(dummy, layout_type="8li")
        assert result is not None
        # 8li = 4 rows × 2 cols
        assert result.shape == (800, 300, 3)


# ---------------------------------------------------------------------------
# 4b. PDF output
# ---------------------------------------------------------------------------

class TestPDFOutput:
    def test_pdf_save(self, models_available, tmp_path):
        if not models_available:
            pytest.skip("Models not available")
        bv = BiyoVes(image_path=None)
        # Test the internal _save_as_pdf method directly
        dummy_layout = np.ones((400, 300, 3), dtype=np.uint8) * 255
        pdf_path = str(tmp_path / "test_output.pdf")
        bv._save_as_pdf(dummy_layout, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


# ---------------------------------------------------------------------------
# 5. Background remover (needs modnet.onnx)
# ---------------------------------------------------------------------------

class TestBackgroundRemover:
    def test_bg_remover_custom_color(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.remove_bg import BackgroundRemover
        model_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'biyoves', 'models', 'modnet.onnx'
        )
        remover = BackgroundRemover(model_path)
        dummy = np.ones((200, 150, 3), dtype=np.uint8) * 200
        # Use blue background
        result = remover.process(dummy, bg_color=(255, 0, 0))
        assert result is not None
        assert result.shape == dummy.shape

    def test_bg_remover_nonexistent_model_raises(self):
        from biyoves.remove_bg import BackgroundRemover
        with pytest.raises(FileNotFoundError):
            BackgroundRemover("nonexistent_model.onnx")


# ---------------------------------------------------------------------------
# 6. Corrector (needs det_500m.onnx)
# ---------------------------------------------------------------------------

class TestCorrector:
    def test_corrector_with_string_input(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.corrector import FaceOrientationCorrector
        corrector = FaceOrientationCorrector()
        result = corrector.correct_image("nonexistent_12345.jpg")
        assert result is None

    def test_corrector_with_numpy_input(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.corrector import FaceOrientationCorrector
        corrector = FaceOrientationCorrector()
        dummy = np.ones((300, 300, 3), dtype=np.uint8) * 200
        # No face → returns original
        result = corrector.correct_image(dummy)
        assert result is not None
        assert result.shape == dummy.shape


# ---------------------------------------------------------------------------
# 7. Processor input validation (needs models)
# ---------------------------------------------------------------------------

class TestProcessorValidation:
    def test_too_small_image_returns_none(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        tiny = np.ones((50, 50, 3), dtype=np.uint8) * 200
        result = gen.process_photo(tiny)
        assert result is None

    def test_too_large_image_returns_none(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        # Create a minimal "large" image by faking dimensions check
        huge = np.ones((10001, 100, 3), dtype=np.uint8) * 200
        result = gen.process_photo(huge)
        assert result is None

    def test_none_input_returns_none(self, models_available):
        if not models_available:
            pytest.skip("Models not available")
        from biyoves.processor import BiometricIDGenerator
        gen = BiometricIDGenerator()
        result = gen.process_photo(None)
        assert result is None
