"""Deterministic tests for the batch and quality APIs."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from biyoves import BiyoVes
from biyoves.quality import PhotoQualityChecker, QualityReport


class FakeDetector:
    def __init__(self, bbox=None, keypoints=None):
        self.bbox = bbox
        self.keypoints = keypoints

    def detect(self, image, max_num=1):
        if self.bbox is None:
            return np.empty((0, 5), dtype=np.float32), None

        dets = np.array([list(self.bbox) + [0.99]], dtype=np.float32)
        kpss = np.array([self.keypoints], dtype=np.float32)
        return dets, kpss


class FakeLandmarker:
    def __init__(self, landmarks):
        self.landmarks = landmarks

    def get(self, image, bbox):
        return self.landmarks.copy()


def eye_contour(center_x, center_y, radius_x, radius_y):
    angles = np.linspace(0.0, 2.0 * np.pi, 10, endpoint=False)
    return np.column_stack((
        center_x + radius_x * np.cos(angles),
        center_y + radius_y * np.sin(angles),
    )).astype(np.float32)


def quality_checker(image_bbox=(20, 10, 200, 260), eye_height=7.0,
                    nose_x=110.0):
    landmarks = np.zeros((106, 2), dtype=np.float32)
    landmarks[33:43] = eye_contour(75, 90, 22, eye_height)
    landmarks[87:97] = eye_contour(145, 90, 22, eye_height)
    keypoints = np.array([
        [75, 90], [145, 90], [nose_x, 120], [90, 150], [130, 150]
    ], dtype=np.float32)
    return PhotoQualityChecker(
        detector=FakeDetector(image_bbox, keypoints),
        landmark_model=FakeLandmarker(landmarks),
    )


def sharp_image():
    checkerboard = np.indices((300, 220)).sum(axis=0) % 2
    gray = (checkerboard * 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class TestPhotoQualityChecker:
    def test_acceptable_photo_passes_all_three_checks(self):
        report = quality_checker().check(sharp_image())

        assert report.is_acceptable is True
        assert report.blur_score > 80
        assert report.eyes_open is True
        assert report.face_angle_degrees == pytest.approx(0.0)
        assert report.warnings == []

    def test_blurred_photo_is_rejected(self):
        image = np.full((300, 220, 3), 127, dtype=np.uint8)
        report = quality_checker().check(image)

        assert report.is_acceptable is False
        assert report.blur_score == pytest.approx(0.0)
        assert any("bulanık" in warning for warning in report.warnings)

    def test_closed_eyes_are_rejected(self):
        report = quality_checker(eye_height=1.0).check(sharp_image())

        assert report.eyes_open is False
        assert report.is_acceptable is False
        assert any("Gözler kapalı" in warning for warning in report.warnings)

    def test_large_face_angle_is_rejected(self):
        checker = quality_checker(nose_x=155.0)
        report = checker.check(sharp_image())

        assert report.face_angle_degrees > 15
        assert report.is_acceptable is False
        assert any("Yüz açısı" in warning for warning in report.warnings)

    def test_no_face_returns_an_unacceptable_report(self):
        checker = PhotoQualityChecker(
            detector=FakeDetector(),
            landmark_model=FakeLandmarker(np.zeros((106, 2), dtype=np.float32)),
        )
        report = checker.check(sharp_image())

        assert report.is_acceptable is False
        assert report.warnings == ["Yüz tespit edilemedi."]

    def test_report_dict_has_documented_shape(self):
        result = QualityReport().to_dict()
        assert set(result) == {
            "is_acceptable", "blur_score", "eyes_open",
            "face_angle_degrees", "warnings",
        }


class TestCheckQualityAPI:
    def test_uses_shared_models(self, tmp_path, monkeypatch):
        image_path = tmp_path / "photo.jpg"
        cv2.imwrite(str(image_path), np.full((100, 100, 3), 255, dtype=np.uint8))
        captured = {}

        class SpyChecker:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def check(self, image):
                return QualityReport()

        monkeypatch.setattr("biyoves.quality.PhotoQualityChecker", SpyChecker)

        instance = object.__new__(BiyoVes)
        instance.image_path = str(image_path)
        instance.processor = SimpleNamespace(
            detector=object(),
            landmarker=object(),
        )

        result = instance.check_quality()

        assert result["is_acceptable"] is True
        assert captured == {
            "detector": instance.processor.detector,
            "landmark_model": instance.processor.landmarker,
        }


class TestBatchProcess:
    @staticmethod
    def install_fake_pipeline(monkeypatch, failing_name=None):
        calls = []

        def fake_init(self, image_path=None, verbose=True):
            self.image_path = image_path
            self.verbose = verbose

        def fake_set_image(self, image_path):
            self.image_path = image_path

        def fake_create_image(self, photo_type, layout_type, output_path,
                              bg_color=(255, 255, 255)):
            if Path(self.image_path).name == failing_name:
                raise RuntimeError("synthetic processing error")
            calls.append((Path(self.image_path).name, photo_type, layout_type,
                          output_path, bg_color))
            Path(output_path).write_bytes(b"fake image")
            return np.zeros((1, 1, 3), dtype=np.uint8)

        monkeypatch.setattr(BiyoVes, "__init__", fake_init)
        monkeypatch.setattr(BiyoVes, "set_image", fake_set_image)
        monkeypatch.setattr(BiyoVes, "create_image", fake_create_image)
        return calls

    def test_processes_supported_files_and_ignores_others(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "photos"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        for name in ("a.JPG", "b.png", "notes.txt"):
            (input_dir / name).write_bytes(b"input")
        calls = self.install_fake_pipeline(monkeypatch)

        results = BiyoVes.batch_process(
            str(input_dir), photo_type="biyometrik", layout_type="4lu",
            output_dir=str(output_dir), verbose=False, bg_color=(1, 2, 3),
        )

        assert [result["file"] for result in results] == ["a.JPG", "b.png"]
        assert all(result["status"] == "success" for result in results)
        assert len(calls) == 2
        assert all(call[1:3] == ("biyometrik", "4lu") for call in calls)
        assert all(call[4] == (1, 2, 3) for call in calls)
        assert all(Path(result["output"]).exists() for result in results)

    def test_one_failure_does_not_stop_the_batch(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "photos"
        input_dir.mkdir()
        for name in ("broken.jpg", "good.jpg"):
            (input_dir / name).write_bytes(b"input")
        self.install_fake_pipeline(monkeypatch, failing_name="broken.jpg")

        results = BiyoVes.batch_process(str(input_dir), verbose=False)

        assert results[0]["status"] == "error"
        assert results[0]["error"] == "synthetic processing error"
        assert results[1]["status"] == "success"

    def test_default_output_directory_is_inside_input(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "photos"
        input_dir.mkdir()
        (input_dir / "person.jpg").write_bytes(b"input")
        self.install_fake_pipeline(monkeypatch)

        results = BiyoVes.batch_process(str(input_dir), verbose=False)

        assert Path(results[0]["output"]).parent == input_dir / "results"

    def test_empty_directory_returns_without_loading_models(self, tmp_path, monkeypatch):
        def fail_init(self, image_path=None, verbose=True):
            raise AssertionError("models should not load for an empty directory")

        monkeypatch.setattr(BiyoVes, "__init__", fail_init)
        assert BiyoVes.batch_process(str(tmp_path), verbose=False) == []

    def test_rejects_same_input_and_output_directory(self, tmp_path):
        with pytest.raises(ValueError, match="different"):
            BiyoVes.batch_process(
                str(tmp_path), output_dir=str(tmp_path), verbose=False,
            )
