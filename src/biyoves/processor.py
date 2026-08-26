from __future__ import annotations

import cv2
import logging
import os
from typing import Optional, Tuple, Union

import numpy as np

from .face_utils import SCRFD, Landmark106, Face
from .remove_bg import BackgroundRemover

logger = logging.getLogger(__name__)

# Minimum input image dimensions (pixels) to produce meaningful output
MIN_IMAGE_DIM = 100
# Maximum input dimension to prevent OOM (pixels)
MAX_IMAGE_DIM = 10000


class BiometricIDGenerator:
    """Detects, aligns, scales, crops, and cleans background for biometric photos."""

    def __init__(self, detector: Optional[SCRFD] = None,
                 bg_remover: Optional[BackgroundRemover] = None) -> None:
        """
        Args:
            detector: Optional shared SCRFD instance. If None, loads its own.
            bg_remover: Optional shared BackgroundRemover instance. If None, loads its own.
        """
        package_dir = os.path.dirname(os.path.abspath(__file__))
        det_path = os.path.join(package_dir, "models", "det_500m.onnx")
        lm_path = os.path.join(package_dir, "models", "2d106det.onnx")
        modnet_path = os.path.join(package_dir, "models", "modnet.onnx")

        try:
            # Use shared detector or load own
            if detector is not None:
                self.detector = detector
            else:
                if not os.path.exists(det_path):
                    raise FileNotFoundError(f"Model not found: {det_path}")
                self.detector = SCRFD(det_path)
                self.detector.prepare(0)

            # Landmark model (always loaded here — lightweight and only used by processor)
            if not os.path.exists(lm_path):
                raise FileNotFoundError(f"Model not found: {lm_path}")
            self.landmarker = Landmark106(lm_path)

            # Use shared bg_remover or load own
            if bg_remover is not None:
                self.bg_remover = bg_remover
            elif os.path.exists(modnet_path):
                self.bg_remover = BackgroundRemover(modnet_path)
            else:
                logger.warning(f"Background remover model not found at {modnet_path}. "
                               "Background removal will be skipped.")
                self.bg_remover = None

        except Exception as e:
            logger.error(f"Model initialization error: {e}")
            raise

        self.DPI = 300
        self.PIXELS_PER_MM = self.DPI / 25.4

        # Photo specifications for each type (dimensions in mm)
        # Sources:
        #   biyometrik: ICAO 9303 standard — face height 32-36mm, target 34mm
        #   vesikalik:  Turkish ID portrait format
        #   abd_vizesi: US Department of State visa photo requirements
        #   schengen:   EU Schengen visa photo requirements
        self.PHOTO_SPECS = {
            "biyometrik": {"w": 50, "h": 60, "face_h": 34, "top_margin": 2.5},
            "vesikalik":  {"w": 45, "h": 60, "face_h": 30, "top_margin": 2.5},
            "abd_vizesi": {"w": 50, "h": 50, "face_h": 30, "top_margin": 2.5},
            "schengen":   {"w": 35, "h": 45, "face_h": 28, "top_margin": 2.0},
        }

    def _get_landmarks(self, face: Face) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns key landmarks: (left_eye, right_eye, chin).

        Uses 106-point landmarks for chin if available, falls back to
        estimating chin from the 5-keypoint model.
        """
        if face.landmark_2d_106 is not None:
            lms = face.landmark_2d_106
            # InsightFace 2d106det: index 0 = bottom-center of the chin.
            # 5-keypoint (kps): index 0 = left eye, 1 = right eye, 2 = nose
            # Use kps for eyes (very stable), 106 for chin (more precise)
            return face.kps[0], face.kps[1], lms[0]

        # Fallback to 5-keypoint model with estimated chin
        # kps indices: 0=left_eye, 1=right_eye, 2=nose, 3=left_mouth, 4=right_mouth
        nose = face.kps[2]
        mouth_center = (face.kps[3] + face.kps[4]) / 2
        estimated_chin = mouth_center + (mouth_center - nose) * 0.8
        return face.kps[0], face.kps[1], estimated_chin

    def _estimate_hair_top(self, left_eye: np.ndarray, right_eye: np.ndarray,
                           chin: np.ndarray) -> float:
        """
        Estimates top of skull/hair based on eye and chin positions.

        Uses the eye-to-chin distance as a stable geometric fallback.
        The factor places the estimated crown slightly closer to the eyes
        than the chin, which matches typical frontal head proportions.
        """
        eye_center = (left_eye + right_eye) / 2
        chin_y = chin[1]
        eye_y = eye_center[1]
        face_bottom_half = chin_y - eye_y

        CROWN_FACTOR = 1.12
        return eye_y - (face_bottom_half * CROWN_FACTOR)

    @staticmethod
    def _first_stable_foreground_row(mask: np.ndarray,
                                     min_pixels: int) -> Optional[int]:
        """Return the first foreground row that continues into the next row."""
        if mask.size == 0:
            return None

        row_counts = np.count_nonzero(mask, axis=1)
        stable = row_counts >= max(1, min_pixels)
        for row in np.flatnonzero(stable):
            if row + 1 < len(stable) and stable[row + 1]:
                return int(row)
        return None

    def _detect_hair_top_from_matte(self, matte: Optional[np.ndarray],
                                    bbox: np.ndarray,
                                    left_eye: np.ndarray,
                                    right_eye: np.ndarray) -> Optional[float]:
        """Measure the real top of the hair inside a face-anchored matte ROI."""
        if matte is None or matte.ndim != 2:
            return None

        h, w = matte.shape
        face_w = max(1.0, float(bbox[2] - bbox[0]))
        face_h = max(1.0, float(bbox[3] - bbox[1]))
        pad_x = face_w * 0.35
        x1 = int(max(0, np.floor(float(bbox[0]) - pad_x)))
        x2 = int(min(w, np.ceil(float(bbox[2]) + pad_x)))
        y1 = int(max(0, np.floor(float(bbox[1]) - face_h * 0.6)))
        eye_y = int(min(h, np.ceil(min(float(left_eye[1]), float(right_eye[1])))))

        if x2 <= x1 or eye_y <= y1:
            return None

        foreground = matte[y1:eye_y, x1:x2] >= 0.2
        min_pixels = max(3, int(round(face_w * 0.015)))
        row = self._first_stable_foreground_row(foreground, min_pixels)
        if row is None:
            return None
        return float(y1 + row)

    def process_photo(self, image_input: Union[str, np.ndarray],
                      photo_type: str = "biyometrik",
                      bg_color: Tuple[int, int, int] = (255, 255, 255)
                      ) -> Optional[np.ndarray]:
        """
        Full biometric photo processing pipeline:
        detect → align → scale/crop → remove background.

        Args:
            image_input: BGR numpy array or file path string.
            photo_type: One of 'biyometrik', 'vesikalik', 'abd_vizesi', 'schengen'.
            bg_color: Background color as (B, G, R) tuple. Default is white.

        Returns:
            Processed BGR image at the correct dimensions, or None on failure.
        """
        if photo_type not in self.PHOTO_SPECS:
            logger.error(f"Invalid photo type: '{photo_type}'. "
                         f"Valid types: {list(self.PHOTO_SPECS.keys())}")
            return None

        if isinstance(image_input, str):
            original_image = cv2.imread(image_input)
        else:
            original_image = image_input

        if original_image is None:
            return None

        # Input size validation
        h, w = original_image.shape[:2]
        if h < MIN_IMAGE_DIM or w < MIN_IMAGE_DIM:
            logger.error(f"Image too small ({w}x{h}px). "
                         f"Minimum dimension is {MIN_IMAGE_DIM}px.")
            return None
        if h > MAX_IMAGE_DIM or w > MAX_IMAGE_DIM:
            logger.error(f"Image too large ({w}x{h}px). "
                         f"Maximum dimension is {MAX_IMAGE_DIM}px.")
            return None

        # 1. Detect faces
        dets, kpss = self.detector.detect(original_image, max_num=0)
        if kpss is None or len(kpss) == 0:
            logger.warning("No face detected in the image.")
            return None

        # Pick the largest face by bounding box area
        areas = (dets[:, 2] - dets[:, 0]) * (dets[:, 3] - dets[:, 1])
        largest_idx = np.argmax(areas)

        bbox = dets[largest_idx][:4]
        kps = kpss[largest_idx]

        # Get 106-point landmarks for precise chin location
        lms106 = self.landmarker.get(original_image, bbox)

        face = Face(bbox=bbox, kps=kps, lms106=lms106, det_score=dets[largest_idx][4])

        # 2. Alignment (rotation to make eyes horizontal)
        left_eye, right_eye, chin = self._get_landmarks(face)

        dy = right_eye[1] - left_eye[1]
        dx = right_eye[0] - left_eye[0]
        angle = np.degrees(np.arctan2(dy, dx))

        h, w = original_image.shape[:2]
        # Use float division for sub-pixel accuracy in rotation center
        center = ((left_eye[0] + right_eye[0]) / 2.0,
                  (left_eye[1] + right_eye[1]) / 2.0)
        M_rot = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated_img = cv2.warpAffine(original_image, M_rot, (w, h),
                                     flags=cv2.INTER_LANCZOS4,
                                     borderValue=(255, 255, 255))

        # 3. Re-detect on rotated image if rotation was significant (>5 degrees)
        if abs(angle) > 5:
            dets_rot, kpss_rot = self.detector.detect(rotated_img)
            if kpss_rot is not None and len(kpss_rot) > 0:
                areas = (dets_rot[:, 2] - dets_rot[:, 0]) * (dets_rot[:, 3] - dets_rot[:, 1])
                largest_idx = np.argmax(areas)
                bbox = dets_rot[largest_idx][:4]
                lms106 = self.landmarker.get(rotated_img, bbox)
                face = Face(bbox=bbox, kps=kpss_rot[largest_idx], lms106=lms106)
                left_eye, right_eye, chin = self._get_landmarks(face)

        # 4. Predict one portrait matte for both hair measurement and compositing
        spec = self.PHOTO_SPECS[photo_type]
        source_matte = None
        if self.bg_remover:
            source_matte = self.bg_remover.predict_matte(rotated_img)

        # 5. Scaling & cropping using the measured top of the hair
        detected_hair_top = None
        if source_matte is not None:
            detected_hair_top = self._detect_hair_top_from_matte(
                source_matte, bbox, left_eye, right_eye,
            )
        if detected_hair_top is not None:
            hair_top_y = detected_hair_top
        else:
            hair_top_y = self._estimate_hair_top(left_eye, right_eye, chin)

        face_height_px = abs(chin[1] - hair_top_y)

        target_face_h_px = spec['face_h'] * self.PIXELS_PER_MM
        scale = target_face_h_px / face_height_px

        # Target canvas size in pixels (at 300 DPI)
        target_w = int(spec['w'] * self.PIXELS_PER_MM)
        target_h = int(spec['h'] * self.PIXELS_PER_MM)
        target_top_margin_px = int(spec['top_margin'] * self.PIXELS_PER_MM)

        # Center face horizontally, position hair top at the margin
        face_center_x = (left_eye[0] + right_eye[0]) / 2

        new_face_center_x = face_center_x * scale
        new_hair_top_y = hair_top_y * scale

        shift_x = (target_w / 2) - new_face_center_x
        shift_y = target_top_margin_px - new_hair_top_y

        M_scale_trans = np.float32([
            [scale, 0, shift_x],
            [0, scale, shift_y]
        ])

        final_canvas = cv2.warpAffine(
            rotated_img, M_scale_trans, (target_w, target_h),
            flags=cv2.INTER_LANCZOS4, borderValue=(255, 255, 255),
        )

        # 6. Reuse the same matte for the final background composite
        if self.bg_remover and source_matte is not None:
            final_matte = cv2.warpAffine(
                source_matte, M_scale_trans, (target_w, target_h),
                flags=cv2.INTER_LANCZOS4, borderValue=0.0,
            )
            final_matte = self.bg_remover.smooth_matte(final_matte)
            final_canvas = self.bg_remover.composite(
                final_canvas, final_matte, bg_color=bg_color,
            )

        return final_canvas
