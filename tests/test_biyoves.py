"""
BiyoVes test suite.

Unit tests run without models (input validation, API surface).
Integration tests require ONNX models and are skipped if models are absent.
"""
import os
import re
import sys
from pathlib import Path

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

    def test_version_matches_project_metadata(self):
        pyproject = Path(__file__).parents[1] / "pyproject.toml"
        match = re.search(
            r'^version = "([^"]+)"$',
            pyproject.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        assert match is not None
        assert biyoves.__version__ == match.group(1)

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

        media_box = re.search(
            rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]",
            Path(pdf_path).read_bytes(),
        )
        assert media_box is not None
        width_pt, height_pt = map(float, media_box.groups())
        assert width_pt == pytest.approx(72.0, abs=0.01)
        assert height_pt == pytest.approx(96.0, abs=0.01)


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


# ---------------------------------------------------------------------------
# 8. Processor geometry (no models needed)
# ---------------------------------------------------------------------------

class TestProcessorGeometry:
    @staticmethod
    def generator_without_models():
        from biyoves.processor import BiometricIDGenerator
        return object.__new__(BiometricIDGenerator)

    def test_uses_bottom_center_landmark_as_chin(self):
        from biyoves.face_utils import Face

        gen = self.generator_without_models()
        landmarks = np.zeros((106, 2), dtype=np.float32)
        landmarks[0] = [50, 90]
        landmarks[16] = [10, 70]
        keypoints = np.array([
            [35, 40], [65, 40], [50, 55], [42, 67], [58, 67],
        ], dtype=np.float32)
        face = Face(
            bbox=np.array([20, 20, 80, 100], dtype=np.float32),
            kps=keypoints,
            lms106=landmarks,
        )

        _, _, chin = gen._get_landmarks(face)

        assert np.array_equal(chin, landmarks[0])

    def test_implausible_busy_background_scan_uses_estimate(self):
        gen = self.generator_without_models()
        left_eye = np.array([40, 200], dtype=np.float32)
        right_eye = np.array([60, 200], dtype=np.float32)
        chin = np.array([50, 300], dtype=np.float32)
        estimate = gen._estimate_hair_top(left_eye, right_eye, chin)

        selected = gen._select_hair_top(
            estimate,
            detected_hair_top=0.0,
            left_eye=left_eye,
            right_eye=right_eye,
            chin=chin,
        )

        assert estimate == pytest.approx(88.0)
        assert selected == pytest.approx(estimate)

    def test_plausible_scan_detection_is_used(self):
        gen = self.generator_without_models()
        left_eye = np.array([40, 50], dtype=np.float32)
        right_eye = np.array([60, 50], dtype=np.float32)
        chin = np.array([50, 100], dtype=np.float32)
        estimate = gen._estimate_hair_top(left_eye, right_eye, chin)

        selected = gen._select_hair_top(
            estimate,
            detected_hair_top=8.0,
            left_eye=left_eye,
            right_eye=right_eye,
            chin=chin,
        )

        assert selected == pytest.approx(8.0)

    def test_busy_background_portrait_keeps_hair_and_shoulders_in_frame(
            self, models_available):
        if not models_available:
            pytest.skip("Models not available")

        from biyoves.processor import BiometricIDGenerator

        source = (
            Path(__file__).parents[1]
            / "website" / "public" / "demo" / "synthetic-source.webp"
        )
        image = cv2.imread(str(source))
        result = BiometricIDGenerator().process_photo(image, photo_type="biyometrik")

        assert result is not None
        nonwhite = np.max(255 - result, axis=2) > 24
        visible_rows = np.where(nonwhite.sum(axis=1) >= 8)[0]
        target_margin = int(2.5 * (300 / 25.4))

        assert visible_rows[0] == pytest.approx(target_margin, abs=12)
        midpoint = result.shape[1] // 2
        assert nonwhite[-1, :midpoint].mean() > 0.9
        assert nonwhite[-1, midpoint:].mean() > 0.9


class TestOnnxRuntimeFallback:
    def test_retries_on_cpu_when_acceleration_fails(self, monkeypatch):
        from biyoves import runtime

        calls = []

        def fake_session(model_path, providers):
            calls.append(providers)
            if providers != ["CPUExecutionProvider"]:
                raise RuntimeError("synthetic accelerator failure")
            return object()

        monkeypatch.setattr(
            runtime.ort,
            "get_available_providers",
            lambda: ["CoreMLExecutionProvider", "CPUExecutionProvider"],
        )
        monkeypatch.setattr(runtime.ort, "InferenceSession", fake_session)

        session = runtime.create_inference_session("model.onnx")

        assert session is not None
        assert calls == [
            ["CoreMLExecutionProvider", "CPUExecutionProvider"],
            ["CPUExecutionProvider"],
        ]
