import cv2
import numpy as np
import logging
import os
from .face_utils import SCRFD, Face

logger = logging.getLogger(__name__)

class FaceOrientationCorrector:
    """Detects and corrects face orientation (0/90/180/270 degree rotations)."""

    def __init__(self, verbose=False, detector=None):
        """
        Args:
            verbose: If True, log orientation correction details.
            detector: Optional shared SCRFD instance. If None, loads its own.
        """
        self.verbose = verbose

        if detector is not None:
            self.detector = detector
        else:
            # Fallback: load own detector if none provided
            package_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(package_dir, "models", "det_500m.onnx")

            if not os.path.exists(model_path):
                raise FileNotFoundError(f"SCRFD model not found: {model_path}")

            self.detector = SCRFD(model_path)
            self.detector.prepare(0)

    def _rotate_image(self, image, angle):
        """Rotates image counter-clockwise by angle degrees (0, 90, 180, 270)."""
        if angle == 0: return image
        if angle == 90: return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if angle == 180: return cv2.rotate(image, cv2.ROTATE_180)
        if angle == 270: return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        return image

    def correct_image(self, image_input):
        """
        Tries all 4 cardinal orientations and returns the one with the
        highest-confidence upright face detection.

        Args:
            image_input: BGR numpy array or file path string.

        Returns:
            Corrected BGR image, or original if no face found.
        """
        if isinstance(image_input, str):
            original_image = cv2.imread(image_input)
            if original_image is None:
                logger.error(f"Could not read image: {image_input}")
                return None
        else:
            original_image = image_input

        if original_image is None:
            return None

        # Check all 4 orientations
        rotations = [0, 90, 180, 270]
        best_score = -1.0
        best_angle = 0
        best_img = original_image

        for angle in rotations:
            current_img = self._rotate_image(original_image, angle)

            # Detect face
            dets, kpss = self.detector.detect(current_img, max_num=1)

            if dets is not None and len(dets) > 0:
                score = dets[0][4]

                # Check if face is upright based on eye keypoints
                # InsightFace KPS: [left_eye, right_eye, nose, left_mouth, right_mouth]
                kps = kpss[0]
                left_eye = kps[0]
                right_eye = kps[1]
                dx = right_eye[0] - left_eye[0]
                dy = right_eye[1] - left_eye[1]
                internal_angle = np.degrees(np.arctan2(dy, dx))

                # Penalize non-upright faces (eyes should be roughly horizontal)
                # 30-degree tolerance for natural head tilt
                if abs(internal_angle) > 30:
                    score *= 0.5

                if score > best_score:
                    best_score = score
                    best_angle = angle
                    best_img = current_img

        if self.verbose:
            if best_score > 0:
                logger.info(f"Best orientation: {best_angle} degrees (score: {best_score:.4f})")
            else:
                logger.warning("No face detected at any orientation.")

        return best_img