import cv2
import numpy as np
import logging
import os
from .face_utils import SCRFD, Landmark106, Face
from .remove_bg import BackgroundRemover

logger = logging.getLogger(__name__)

# Minimum input image dimensions (pixels) to produce meaningful output
MIN_IMAGE_DIM = 100
# Maximum input dimension to prevent OOM (pixels)
MAX_IMAGE_DIM = 10000


class BiometricIDGenerator:
    """Detects, aligns, scales, crops, and cleans background for biometric photos."""

    def __init__(self, detector=None, bg_remover=None):
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
        #   vesikalik:  Turkish passport photo standard
        #   abd_vizesi: US Department of State visa photo requirements
        #   schengen:   EU Schengen visa photo requirements
        self.PHOTO_SPECS = {
            "biyometrik": {"w": 50, "h": 60, "face_h": 34, "top_margin": 2.5},
            "vesikalik":  {"w": 45, "h": 60, "face_h": 30, "top_margin": 2.5},
            "abd_vizesi": {"w": 50, "h": 50, "face_h": 30, "top_margin": 2.5},
            "schengen":   {"w": 35, "h": 45, "face_h": 28, "top_margin": 2.0},
        }

    def _get_landmarks(self, face):
        """
        Returns key landmarks: (left_eye, right_eye, chin, nose_tip).

        Uses 106-point landmarks for chin if available, falls back to
        estimating chin from the 5-keypoint model.
        """
        if face.landmark_2d_106 is not None:
            lms = face.landmark_2d_106
            # 106-point model: index 16 = chin point
            # 5-keypoint (kps): index 0 = left eye, 1 = right eye, 2 = nose
            # Use kps for eyes (very stable), 106 for chin (more precise)
            return face.kps[0], face.kps[1], lms[16], face.kps[2]

        # Fallback to 5-keypoint model with estimated chin
        # kps indices: 0=left_eye, 1=right_eye, 2=nose, 3=left_mouth, 4=right_mouth
        nose = face.kps[2]
        mouth_center = (face.kps[3] + face.kps[4]) / 2
        nose_mouth_dist = np.linalg.norm(nose - mouth_center)
        estimated_chin = mouth_center + (mouth_center - nose) * 0.8
        return face.kps[0], face.kps[1], estimated_chin, face.kps[2]

    def _estimate_hair_top(self, left_eye, right_eye, chin):
        """
        Estimates top of skull/hair based on eye and chin positions.

        Uses the anthropometric heuristic that eyes sit at roughly
        the vertical midpoint of the head. A 1.5x multiplier accounts
        for hair volume above the skull.
        """
        eye_center = (left_eye + right_eye) / 2
        chin_y = chin[1]
        eye_y = eye_center[1]
        face_bottom_half = chin_y - eye_y

        # Factor: 1.0 = skull top, 1.3-1.5 = with hair volume
        HAIR_VOLUME_FACTOR = 1.5
        return eye_y - (face_bottom_half * HAIR_VOLUME_FACTOR)

    def _detect_hair_top_scan(self, img, left_eye, right_eye, chin):
        """
        Attempts to find the top pixel of the hair by flood-filling
        the background from the top edge of the image.

        Returns the Y-coordinate of the topmost foreground pixel
        above the eyes, or None if detection fails.
        """
        try:
            h, w = img.shape[:2]

            # ROI: X range covering the head (2x inter-eye distance on each side)
            face_w = np.linalg.norm(right_eye - left_eye) * 2.0
            center_x = (left_eye[0] + right_eye[0]) / 2
            x1 = int(max(0, center_x - face_w))
            x2 = int(min(w, center_x + face_w))

            if x2 <= x1:
                return None

            # Flood-fill from top edge to identify background pixels
            mask = np.zeros((h + 2, w + 2), np.uint8)
            flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE

            # Tolerance for background color uniformity (BGR channels)
            BG_TOLERANCE = (25, 25, 25)

            work_img = img.copy()

            # Seed points along the top edge
            seeds = [(0, 0), (w - 1, 0), (int(w / 2), 0)]
            for seed in seeds:
                if 0 <= seed[0] < w and 0 <= seed[1] < h:
                    cv2.floodFill(work_img, mask, seed, (0, 0, 0),
                                  BG_TOLERANCE, BG_TOLERANCE, flags)

            # In the mask, 255 = background. We look for foreground (0) above the eyes.
            eye_y = int(min(left_eye[1], right_eye[1]))
            if eye_y <= 0:
                return None

            # +1 offset because floodFill mask is padded by 1 on each side
            roi_mask = mask[1:eye_y + 1, x1 + 1:x2 + 1]

            # Find foreground pixels (value 0)
            fg_rows, _ = np.where(roi_mask == 0)

            if len(fg_rows) == 0:
                return None

            # Topmost foreground pixel
            min_y = np.min(fg_rows)
            return float(min_y)

        except Exception as e:
            logger.warning(f"Hair detection failed: {e}")
            return None

    def process_photo(self, image_input, photo_type="biyometrik"):
        """
        Full biometric photo processing pipeline:
        detect → align → scale/crop → remove background.

        Args:
            image_input: BGR numpy array or file path string.
            photo_type: One of 'biyometrik', 'vesikalik', 'abd_vizesi', 'schengen'.

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
        left_eye, right_eye, chin, nose = self._get_landmarks(face)

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
                left_eye, right_eye, chin, nose = self._get_landmarks(face)

        # 4. Scaling & Cropping
        spec = self.PHOTO_SPECS[photo_type]

        # Hair top detection: combine geometric estimate with scan-based detection
        estimated_hair_top = self._estimate_hair_top(left_eye, right_eye, chin)
        detected_hair_top = self._detect_hair_top_scan(rotated_img, left_eye, right_eye, chin)

        # Use the higher point (smaller Y) to be safe — handles voluminous hair
        if detected_hair_top is not None:
            hair_top_y = min(estimated_hair_top, detected_hair_top)
        else:
            hair_top_y = estimated_hair_top

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

        final_canvas = cv2.warpAffine(rotated_img, M_scale_trans, (target_w, target_h),
                                      flags=cv2.INTER_LANCZOS4,
                                      borderValue=(255, 255, 255))

        # 5. Background removal on the final cropped canvas (faster and cleaner)
        if self.bg_remover:
            final_canvas_clean = self.bg_remover.process(final_canvas)
            if final_canvas_clean is not None:
                final_canvas = final_canvas_clean

        return final_canvas