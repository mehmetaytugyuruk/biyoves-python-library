"""
Photo quality assessment module for BiyoVes.

Checks whether a photo meets biometric standards BEFORE processing:
- Blur detection (Laplacian variance)
- Eye open/closed (Eye Aspect Ratio from 106-point landmarks)
- Face angle (yaw deviation from frontal)
- Resolution sufficiency (enough pixels for 300 DPI print)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from .face_utils import Landmark106, SCRFD

logger = logging.getLogger(__name__)

# Thresholds (tuned for biometric/passport photos)
BLUR_THRESHOLD = 80.0          # Laplacian variance; lower = blurrier
EAR_THRESHOLD = 0.18           # Eye Aspect Ratio; lower = more closed
MAX_FACE_ANGLE_DEG = 15.0      # Max estimated yaw deviation in degrees
MIN_FACE_PX_FOR_PRINT = 200    # Fallback when no photo standard is supplied

LEFT_EYE_INDICES = np.arange(33, 43)
RIGHT_EYE_INDICES = np.arange(87, 97)


@dataclass
class QualityReport:
    """Result of a photo quality assessment."""
    is_acceptable: bool = True
    blur_score: float = 0.0
    eyes_open: bool = True
    face_angle_degrees: float = 0.0
    resolution_sufficient: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "is_acceptable": bool(self.is_acceptable),
            "blur_score": round(float(self.blur_score), 1),
            "eyes_open": bool(self.eyes_open),
            "face_angle_degrees": round(float(self.face_angle_degrees), 1),
            "resolution_sufficient": bool(self.resolution_sufficient),
            "warnings": self.warnings,
        }


class PhotoQualityChecker:
    """Checks if a photo meets biometric quality standards."""

    def __init__(self, detector: Optional[SCRFD] = None,
                 landmark_model: Optional[Landmark106] = None,
                 blur_threshold: float = BLUR_THRESHOLD,
                 ear_threshold: float = EAR_THRESHOLD,
                 max_face_angle_deg: float = MAX_FACE_ANGLE_DEG,
                 min_face_px_for_print: int = MIN_FACE_PX_FOR_PRINT) -> None:
        model_dir = Path(__file__).parent / "models"

        if detector is None:
            detector = SCRFD(str(model_dir / "det_500m.onnx"))
            detector.prepare(0)
        if landmark_model is None:
            landmark_model = Landmark106(str(model_dir / "2d106det.onnx"))

        self.detector = detector
        self.landmark_model = landmark_model
        self.blur_threshold = float(blur_threshold)
        self.ear_threshold = float(ear_threshold)
        self.max_face_angle_deg = float(max_face_angle_deg)
        self.min_face_px_for_print = int(min_face_px_for_print)

    def check(self, image: np.ndarray) -> QualityReport:
        """
        Run all quality checks on an image.

        Args:
            image: BGR numpy array.

        Returns:
            QualityReport with detailed results and warnings.
        """
        report = QualityReport()

        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            report.is_acceptable = False
            report.warnings.append("Görüntü okunamadı.")
            return report

        # Detect face
        dets, kpss = self.detector.detect(image, max_num=1)
        if dets is None or len(dets) == 0:
            report.is_acceptable = False
            report.warnings.append("Yüz tespit edilemedi.")
            return report

        bbox = dets[0][:4].astype(int)

        # 1. Blur check (on face region)
        self._check_blur(image, bbox, report)

        # 2. Eye open/closed check
        try:
            lms106 = self.landmark_model.get(image, bbox)
            self._check_eyes(lms106, report)
        except Exception as exc:
            logger.warning("Eye landmark check failed: %s", exc)
            report.eyes_open = False
            report.warnings.append("Göz açıklığı kontrol edilemedi.")

        # 3. Face angle check
        if kpss is None or len(kpss) == 0:
            report.warnings.append("Yüz açısı kontrol edilemedi.")
        else:
            self._check_face_angle(kpss[0], report)

        # 4. Resolution check
        self._check_resolution(bbox, report)

        # Final verdict
        report.is_acceptable = not report.warnings

        return report

    def _check_blur(self, image: np.ndarray, bbox: np.ndarray,
                    report: QualityReport) -> None:
        """Check image sharpness using Laplacian variance on the face region."""
        x1, y1, x2, y2 = bbox
        # Clamp to image bounds
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        face_crop = image[y1:y2, x1:x2]
        if face_crop.size == 0:
            report.warnings.append("Yüz bölgesi görüntü sınırları dışında.")
            return

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        report.blur_score = float(score)

        if score < self.blur_threshold:
            report.warnings.append(
                f"Fotoğraf bulanık (skor: {score:.1f}, "
                f"minimum: {self.blur_threshold:.1f})"
            )

    def _check_eyes(self, lms106: np.ndarray,
                    report: QualityReport) -> None:
        """Check if eyes are open using a rotation-invariant aspect ratio."""
        if lms106 is None or len(lms106) < 97:
            raise ValueError("106-point landmarks are incomplete")

        left_ear = self._eye_aspect_ratio(lms106[LEFT_EYE_INDICES])
        right_ear = self._eye_aspect_ratio(lms106[RIGHT_EYE_INDICES])
        avg_ear = (left_ear + right_ear) / 2.0
        report.eyes_open = bool(avg_ear >= self.ear_threshold)

        if not report.eyes_open:
            report.warnings.append(
                f"Gözler kapalı görünüyor (EAR: {avg_ear:.2f}, "
                f"minimum: {self.ear_threshold:.2f})"
            )

    @staticmethod
    def _eye_aspect_ratio(eye_points: np.ndarray) -> float:
        """Return eye height/width after removing in-plane rotation."""
        points = np.asarray(eye_points, dtype=np.float32)
        if points.shape != (10, 2):
            raise ValueError("Each eye must contain exactly 10 landmarks")

        centered = points - points.mean(axis=0, keepdims=True)
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ axes.T
        spans = np.ptp(projected, axis=0)
        width = float(np.max(spans))
        height = float(np.min(spans))
        if width < 1e-6:
            raise ValueError("Eye landmarks have zero width")
        return height / width

    def _check_face_angle(self, kps: np.ndarray,
                          report: QualityReport) -> None:
        """Check face yaw angle — should be near-frontal for biometric photos."""
        if kps is None or len(kps) < 3:
            report.warnings.append("Yüz açısı kontrol edilemedi.")
            return

        # Use 5-keypoint eyes and nose for a lightweight yaw estimate.
        left_eye = kps[0]
        right_eye = kps[1]
        nose = kps[2]

        eye_center = (left_eye + right_eye) / 2
        eye_dist = np.linalg.norm(right_eye - left_eye)
        if eye_dist < 1e-6:
            report.warnings.append("Yüz açısı kontrol edilemedi.")
            return

        nose_deviation = (nose[0] - eye_center[0]) / eye_dist
        angle = float(abs(np.degrees(np.arctan(nose_deviation))))
        report.face_angle_degrees = angle

        if angle > self.max_face_angle_deg:
            report.warnings.append(
                f"Yüz açısı çok büyük ({angle:.1f}°, "
                f"maksimum: {self.max_face_angle_deg:.1f}°)"
            )

    def _check_resolution(self, bbox: np.ndarray,
                          report: QualityReport) -> None:
        """Check if face region has enough pixels for print quality."""
        x1, y1, x2, y2 = bbox[:4]
        face_height_px = abs(y2 - y1)
        report.resolution_sufficient = bool(
            face_height_px >= self.min_face_px_for_print
        )

        if not report.resolution_sufficient:
            report.warnings.append(
                f"Yüz çözünürlüğü yetersiz ({int(face_height_px)}px, "
                f"minimum: {self.min_face_px_for_print}px)"
            )
