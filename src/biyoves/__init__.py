from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple

from .corrector import FaceOrientationCorrector
from .processor import BiometricIDGenerator
from .layout import PrintLayoutGenerator
from .face_utils import SCRFD
from .remove_bg import BackgroundRemover

logger = logging.getLogger(__name__)

# Minimum input image dimensions (pixels)
MIN_IMAGE_DIM = 100
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


class BiyoVes:
    """
    AI-powered biometric, passport, and visa photo generator.

    Pipeline: orientation correction → face detection & alignment →
    scale/crop → background removal → print layout.
    """

    def __init__(self, image_path: Optional[str] = None, verbose: bool = True) -> None:
        """
        Args:
            image_path: Path to the input photo file.
            verbose: If True, log processing details.
        """
        self.verbose = verbose
        self.image_path = image_path

        # Load shared models once and inject into sub-components
        package_dir = Path(__file__).parent
        det_path = package_dir / "models" / "det_500m.onnx"
        modnet_path = package_dir / "models" / "modnet.onnx"

        if not det_path.exists():
            raise FileNotFoundError(f"SCRFD model not found: {det_path}")

        # Shared face detector (used by both corrector and processor)
        shared_detector = SCRFD(str(det_path))
        shared_detector.prepare(0)

        # Shared background remover (used by processor)
        shared_bg_remover = None
        if modnet_path.exists():
            shared_bg_remover = BackgroundRemover(str(modnet_path))

        self.corrector = FaceOrientationCorrector(verbose=self.verbose,
                                                  detector=shared_detector)
        self.processor = BiometricIDGenerator(detector=shared_detector,
                                             bg_remover=shared_bg_remover)
        self.layout_gen = PrintLayoutGenerator()

    def create_image(self, photo_type: str = "biyometrik", layout_type: str = "2li",
                     output_path: Optional[str] = None,
                     bg_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
        """
        Full pipeline: correct orientation → process biometric photo → generate print layout.

        Args:
            photo_type: One of 'biyometrik', 'vesikalik', 'abd_vizesi', 'schengen'.
            layout_type: Grid layout — '2li' (2×1), '4lu' (2×2),
                '6li' (3×2), or '8li' (4×2).
            output_path: Optional file path to save the result (JPEG/PNG/PDF supported).
            bg_color: Background color as (B, G, R) tuple. Default is white (255, 255, 255).

        Returns:
            BGR numpy array of the final print layout.

        Raises:
            ValueError: If no image path was set.
            FileNotFoundError: If input image file doesn't exist.
            RuntimeError: If face detection or layout generation fails.
        """
        if self.image_path is None:
            raise ValueError("No image path set. Use BiyoVes('photo.jpg') or set_image().")

        # 1. Read input image
        original_img = cv2.imread(self.image_path)
        if original_img is None:
            raise FileNotFoundError(f"Input image not found: {self.image_path}")

        # Input size validation
        h, w = original_img.shape[:2]
        if h < MIN_IMAGE_DIM or w < MIN_IMAGE_DIM:
            raise ValueError(f"Image too small ({w}x{h}px). "
                             f"Minimum dimension: {MIN_IMAGE_DIM}px.")

        # 2. Face orientation correction (fix 90/180/270 degree rotations)
        corrected_img = self.corrector.correct_image(original_img)
        if corrected_img is None:
            logger.warning("Orientation correction found no face, using original image.")
            corrected_img = original_img

        # 3. Biometric processing (detect, align, crop, scale, remove background)
        processed_img = self.processor.process_photo(corrected_img, photo_type=photo_type,
                                                     bg_color=bg_color)
        if processed_img is None:
            raise RuntimeError("Face detection or processing failed.")

        # 4. Print layout (arrange photos in grid with cut lines)
        # Pass photo spec so layout dimensions match the photo type
        photo_spec = self.processor.PHOTO_SPECS.get(photo_type)
        final_layout = self.layout_gen.generate_layout(processed_img,
                                                       layout_type=layout_type,
                                                       photo_spec=photo_spec)
        if final_layout is None:
            raise RuntimeError("Layout generation failed.")

        # 5. Save (if output path specified)
        if output_path:
            output_lower = output_path.lower()
            if output_lower.endswith('.pdf'):
                # PDF output with correct physical dimensions at 300 DPI
                self._save_as_pdf(final_layout, output_path)
            elif output_lower.endswith('.jpg') or output_lower.endswith('.jpeg'):
                # JPEG quality 100 = minimum compression (still lossy, but negligible)
                cv2.imwrite(output_path, final_layout, [cv2.IMWRITE_JPEG_QUALITY, 100])
            elif output_lower.endswith('.png'):
                # PNG compression 0 = fastest write, lossless format
                cv2.imwrite(output_path, final_layout, [cv2.IMWRITE_PNG_COMPRESSION, 0])
            else:
                cv2.imwrite(output_path, final_layout)

            if self.verbose:
                logger.info(f"Saved result: {output_path}")

        return final_layout

    def _save_as_pdf(self, image: np.ndarray, output_path: str) -> None:
        """Save layout image as a print-ready PDF at 300 DPI."""
        from fpdf import FPDF

        h_px, w_px = image.shape[:2]
        dpi = 300
        w_mm = w_px / (dpi / 25.4)
        h_mm = h_px / (dpi / 25.4)

        pdf = FPDF(unit="mm", format=(w_mm, h_mm))
        pdf.set_margin(0)
        pdf.add_page()

        # Write image to a temp file, embed in PDF, then clean up
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
        try:
            os.close(tmp_fd)
            cv2.imwrite(tmp_path, image, [cv2.IMWRITE_JPEG_QUALITY, 100])
            pdf.image(tmp_path, x=0, y=0, w=w_mm, h=h_mm)
            pdf.output(output_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def set_image(self, image_path: str) -> None:
        """Change the input image path."""
        self.image_path = image_path

    def check_quality(self) -> Dict[str, object]:
        """
        Check if the current image meets biometric quality standards.

        Runs 3 checks:
        - Blur detection (Laplacian variance on face region)
        - Eye open/closed (Eye Aspect Ratio from landmarks)
        - Face angle (yaw deviation from frontal)

        Returns:
            Dict with keys: is_acceptable, blur_score, eyes_open,
            face_angle_degrees, warnings.

        Notes:
            This is an automated preflight check, not a guarantee that an
            issuing authority will accept the photo.

        Raises:
            ValueError: If no image path is set.
            FileNotFoundError: If the image file doesn't exist.
        """
        from .quality import PhotoQualityChecker

        if self.image_path is None:
            raise ValueError("No image path set. Use BiyoVes('photo.jpg') or set_image().")

        image = cv2.imread(self.image_path)
        if image is None:
            raise FileNotFoundError(f"Input image not found: {self.image_path}")

        checker = PhotoQualityChecker(
            detector=self.processor.detector,
            landmark_model=self.processor.landmarker,
        )
        report = checker.check(image)
        return report.to_dict()

    @classmethod
    def batch_process(cls, input_dir: str, photo_type: str = "biyometrik",
                      layout_type: str = "2li", output_dir: Optional[str] = None,
                      verbose: bool = True,
                      bg_color: Tuple[int, int, int] = (255, 255, 255)) -> List[Dict[str, object]]:
        """
        Process all photos in a directory.

        Creates a single BiyoVes instance (shared models) and processes
        each image file found in input_dir.

        Args:
            input_dir: Path to directory containing input photos.
            photo_type: One of 'biyometrik', 'vesikalik', 'abd_vizesi', 'schengen'.
            layout_type: Grid layout — '2li', '4lu', '6li', or '8li'.
            output_dir: Directory to save results. Defaults to ``input_dir/results``
                and is created if it doesn't exist.
            verbose: If True, log processing details.
            bg_color: Background color as (B, G, R) tuple.

        Returns:
            List of dicts, one per image:
            [{"file": "photo.jpg", "status": "success", "output": "out/photo_biyoves.jpg"},
             {"file": "bad.jpg",   "status": "error",   "error": "No face detected"}]
        """
        input_path = Path(input_dir)
        if not input_path.is_dir():
            raise NotADirectoryError(f"Input directory not found: {input_dir}")

        output_path = Path(output_dir) if output_dir else input_path / "results"
        if output_path.resolve() == input_path.resolve():
            raise ValueError("Output directory must be different from input directory.")

        image_files = sorted(
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )

        if not image_files:
            if verbose:
                logger.warning(f"No image files found in {input_dir}")
            return []

        output_path.mkdir(parents=True, exist_ok=True)

        # Single instance → shared models across all images
        bv = cls(image_path=None, verbose=verbose)
        results: List[Dict[str, object]] = []

        for img_file in image_files:
            bv.set_image(str(img_file))
            try:
                out_name = f"{img_file.stem}_biyoves{img_file.suffix}"
                out_file = str(output_path / out_name)

                bv.create_image(photo_type, layout_type, out_file, bg_color=bg_color)
                results.append({
                    "file": img_file.name,
                    "status": "success",
                    "output": out_file,
                })
                if verbose:
                    logger.info(f"✓ {img_file.name}")
            except Exception as e:
                results.append({
                    "file": img_file.name,
                    "status": "error",
                    "error": str(e),
                })
                if verbose:
                    logger.warning(f"✗ {img_file.name}: {e}")

        # Summary
        success = sum(1 for r in results if r["status"] == "success")
        if verbose:
            logger.info(f"Batch complete: {success}/{len(results)} successful")

        return results


# Convenience function API
def create_image(image_path: str, photo_type: str = "biyometrik",
                 layout_type: str = "2li", output_path: Optional[str] = None,
                 verbose: bool = True,
                 bg_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """
    One-line API to create a biometric photo layout.

    Args:
        image_path: Path to the input photo file.
        photo_type: One of 'biyometrik', 'vesikalik', 'abd_vizesi', 'schengen'.
        layout_type: Grid layout — '2li' (2×1), '4lu' (2×2), '6li' (3×2), or '8li' (4×2).
        output_path: Optional file path to save the result (JPEG/PNG/PDF supported).
        verbose: If True, log processing details.
        bg_color: Background color as (B, G, R) tuple. Default is white (255, 255, 255).

    Returns:
        BGR numpy array of the final print layout.
    """
    biyoves = BiyoVes(image_path, verbose=verbose)
    return biyoves.create_image(photo_type, layout_type, output_path, bg_color=bg_color)


__version__ = "1.4.1"
__all__ = ["BiyoVes", "create_image"]
