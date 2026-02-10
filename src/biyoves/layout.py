import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class PrintLayoutGenerator:
    """Arranges processed biometric photos in a printable grid layout with cut lines."""

    def __init__(self):
        self.DPI = 300
        self.PIXELS_PER_MM = self.DPI / 25.4

        # Predefined grid configurations
        # rows × cols determines how many copies appear on the sheet
        self.GRID_CONFIGS = {
            "2li": {"rows": 2, "cols": 1},
            "4lu": {"rows": 2, "cols": 2},
        }

    def generate_layout(self, image_input, layout_type="2li", photo_spec=None):
        """
        Places the processed photo into a printable grid layout.

        Args:
            image_input: BGR numpy array or file path string.
            layout_type: Grid type — '2li' (2×1) or '4lu' (2×2).
            photo_spec: Optional dict with 'w' and 'h' in mm. If provided,
                        canvas dimensions are calculated from photo size × grid.
                        If None, canvas is calculated from the input image size.

        Returns:
            BGR canvas image with photos arranged in a grid, or None on failure.
        """
        if layout_type not in self.GRID_CONFIGS:
            logger.error(f"Invalid layout type: '{layout_type}'. "
                         f"Valid types: {list(self.GRID_CONFIGS.keys())}")
            return None

        # Read input
        if isinstance(image_input, str):
            input_img = cv2.imread(image_input)
        else:
            input_img = image_input

        if input_img is None:
            return None

        grid = self.GRID_CONFIGS[layout_type]
        rows, cols = grid["rows"], grid["cols"]
        img_h, img_w = input_img.shape[:2]

        # Calculate canvas dimensions dynamically based on photo spec or image size
        if photo_spec is not None:
            # Use the photo specification to calculate exact cell and canvas sizes
            cell_w = int(photo_spec['w'] * self.PIXELS_PER_MM)
            cell_h = int(photo_spec['h'] * self.PIXELS_PER_MM)
        else:
            # Fallback: each cell is the same size as the input image
            cell_w = img_w
            cell_h = img_h

        canvas_w = cell_w * cols
        canvas_h = cell_h * rows

        # White background canvas
        canvas = np.ones((canvas_h, canvas_w, 3), dtype=np.uint8) * 255

        # Light gray contour color for cut guides
        CONTOUR_COLOR = (180, 180, 180)
        CONTOUR_THICKNESS = 2

        for r in range(rows):
            for c in range(cols):
                # Center of the current cell
                cx = (c * cell_w) + (cell_w // 2)
                cy = (r * cell_h) + (cell_h // 2)

                # Top-left corner where the image should start
                start_x = cx - (img_w // 2)
                start_y = cy - (img_h // 2)
                end_x = start_x + img_w
                end_y = start_y + img_h

                # Clip to canvas boundaries
                y1 = max(0, start_y)
                y2 = min(canvas_h, end_y)
                x1 = max(0, start_x)
                x2 = min(canvas_w, end_x)

                # Compensate source image offsets when image exceeds cell/canvas
                img_y1 = y1 - start_y
                img_x1 = x1 - start_x
                img_y2 = img_y1 + (y2 - y1)
                img_x2 = img_x1 + (x2 - x1)

                if y2 > y1 and x2 > x1:
                    # Paste the photo
                    canvas[y1:y2, x1:x2] = input_img[img_y1:img_y2, img_x1:img_x2]

                    # Draw contour (border) around the photo
                    cv2.rectangle(canvas, (x1, y1), (x2 - 1, y2 - 1),
                                  CONTOUR_COLOR, CONTOUR_THICKNESS)

        # Draw cut guide lines between cells
        LINE_COLOR = (0, 0, 0)
        LINE_THICKNESS = 2

        # Vertical dividers
        for c in range(1, cols):
            x = c * cell_w
            cv2.line(canvas, (x, 0), (x, canvas_h), LINE_COLOR, LINE_THICKNESS)

        # Horizontal dividers
        for r in range(1, rows):
            y = r * cell_h
            cv2.line(canvas, (0, y), (canvas_w, y), LINE_COLOR, LINE_THICKNESS)

        return canvas