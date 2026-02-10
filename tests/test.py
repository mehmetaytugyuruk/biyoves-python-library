
import os
import sys
import cv2

# Add src to path to prioritize local source over installed packages
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import biyoves


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "insan.jpg")
    output_path = os.path.join(base_dir, "test_result_4lu_biyometrik.jpg")

    if not os.path.exists(input_path):
        print(f"Error: Sample file not found: {input_path}")
        return

    print("Testing BiyoVes Library...")
    print(f"Version: {biyoves.__version__}")

    try:
        # High-level API: includes orientation correction, processing, and layout
        result = biyoves.create_image(
            image_path=input_path,
            photo_type="biyometrik",  # 50x60mm
            layout_type="4lu",        # 2x2 grid on 10x15cm paper
            output_path=output_path,
            verbose=True
        )

        if result is not None:
            print(f"Success! Result saved: {output_path}")
            print(f"Output dimensions: {result.shape[1]}x{result.shape[0]}px")
        else:
            print("Processing failed.")

    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
