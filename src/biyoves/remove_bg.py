import cv2
import numpy as np
import onnxruntime as ort
import os
import logging

logger = logging.getLogger(__name__)


class BackgroundRemover:
    """Removes image background using MODNet ONNX model with alpha matting."""

    def __init__(self, model_path="modnet.onnx"):
        """
        Args:
            model_path: Path to the MODNet ONNX model file.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.ref_size = 512

    def _get_dynamic_blur_radius(self, height, width):
        """Calculate Gaussian blur kernel size relative to image dimensions."""
        max_dim = max(height, width)
        k_size = int(max_dim / 300)
        if k_size % 2 == 0:
            k_size += 1
        return max(1, k_size)

    def process(self, image_input, bg_color=(255, 255, 255)):
        """
        Remove background from image and replace with solid color.

        Args:
            image_input: BGR numpy array or file path string.
            bg_color: Background replacement color as (B, G, R) tuple.

        Returns:
            BGR numpy array with background replaced, or None on failure.
        """
        if isinstance(image_input, str):
            image = cv2.imread(image_input)
            if image is None:
                logger.error(f"Could not read image: {image_input}")
                return None
        else:
            image = image_input

        if image is None:
            return None

        h, w = image.shape[:2]

        # Preprocessing: resize to model reference size while maintaining aspect ratio
        im_scale = self.ref_size / max(h, w)
        new_h, new_w = int(h * im_scale), int(w * im_scale)
        im_resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # Pad to square (ref_size × ref_size)
        im_padded = np.zeros((self.ref_size, self.ref_size, 3), dtype=np.uint8)
        im_padded[:new_h, :new_w, :] = im_resized

        # Normalize to [-1, 1] range
        im_normalized = (im_padded.astype(np.float32) - 127.5) / 127.5
        im_transposed = np.transpose(im_normalized, (2, 0, 1))
        input_tensor = im_transposed[np.newaxis, :, :, :]

        # Model inference
        result = self.session.run(None, {self.input_name: input_tensor})
        matte = result[0][0][0]

        # Postprocessing: crop padding, resize matte back to original dimensions
        matte_cropped = matte[:new_h, :new_w]
        matte_original = cv2.resize(matte_cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)

        # Smooth matte edges with adaptive Gaussian blur
        blur_k = self._get_dynamic_blur_radius(h, w)
        matte_blurred = cv2.GaussianBlur(matte_original, (blur_k, blur_k), 0)
        alpha = matte_blurred[:, :, np.newaxis]

        # Alpha-blend foreground with new background color
        foreground = image.astype(np.float32)
        background = np.full(image.shape, bg_color, dtype=np.float32)
        combined = (foreground * alpha) + (background * (1.0 - alpha))

        return combined.clip(0, 255).astype(np.uint8)