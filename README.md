# BiyoVes - Python Library

AI-powered biometric, passport, and visa photo generation for Python.

**Resources:** [Web Studio](https://mehmetaytugyuruk.github.io/biyoves-python-library/) · [PyPI](https://pypi.org/project/biyoves/) · [Source](https://github.com/mehmetaytugyuruk/biyoves-python-library) · [Issues](https://github.com/mehmetaytugyuruk/biyoves-python-library/issues) · [License](LICENSE)

## Overview

BiyoVes provides a compact API for background removal, face alignment,
standards-based cropping, and print-ready photo layouts.

Prefer a browser? The free [BiyoVes Web Studio](https://mehmetaytugyuruk.github.io/biyoves-python-library/)
uses the same processing pipeline without requiring an account.

## Installation

```bash
pip install biyoves
```

Or from source:

```bash
git clone https://github.com/mehmetaytugyuruk/biyoves-python-library.git
cd biyoves-python-library
pip install -e .
```

## Quick Start

### Method 1: Class-Based Usage (Recommended)

```python
from biyoves import BiyoVes

# Specify the photo path
img = BiyoVes("photo.jpg")

# Create a passport photo (2-up layout)
passport = img.create_image("vesikalik", "2li", "result_passport.jpg")

# Create a biometric photo (4-up layout)
biometric = img.create_image("biyometrik", "4lu", "result_biometric.jpg")

# US visa photo
us_visa = img.create_image("abd_vizesi", "2li", "result_us_visa.jpg")

# Schengen visa photo
schengen = img.create_image("schengen", "4lu", "result_schengen.jpg")
```

### Method 2: Function-Based Usage

```python
from biyoves import create_image

# Single-line processing
passport = create_image("photo.jpg", "vesikalik", "2li", "result.jpg")
```

### Batch Processing

```python
from biyoves import BiyoVes

results = BiyoVes.batch_process(
    input_dir="photos/",
    photo_type="biyometrik",
    layout_type="4lu",
    output_dir="results/",
)

for result in results:
    print(result)
```

Models are loaded once and shared across the batch. A failed photo is reported
with `status="error"` without stopping the remaining files. If `output_dir` is
omitted, results are written to `input_dir/results`.

### Photo Quality Preflight

```python
from biyoves import BiyoVes

img = BiyoVes("photo.jpg")
report = img.check_quality()

print(report["is_acceptable"])
print(report["warnings"])
```

The optional preflight checks face-region blur, eye openness, and estimated
frontal face angle. It reports warnings but never blocks image generation.

## Photo Types

- `"biyometrik"` - Standard biometric photo (50x60mm)
- `"vesikalik"` - Passport photo (45x60mm)
- `"abd_vizesi"` - US visa photo (50x50mm)
- `"schengen"` - Schengen visa photo (35x45mm)

## Layout Types

- `"2li"` - 2 photos stacked vertically (2x1)
- `"4lu"` - 4 photos in a grid (2x2)
- `"6li"` - 6 photos in a grid (3x2)
- `"8li"` - 8 photos in a grid (4x2)

## Features

- AI-powered automatic background removal
- Automatic face angle correction
- Automatic cropping to standard dimensions
- Batch directory processing with per-file results
- Optional preflight checks for blur, eye openness, and face angle
- Print templates (2-up / 4-up / 6-up / 8-up layouts)
- Print-ready PDF output at 300 DPI
- Cut lines for print-ready output

## Requirements

- Python >= 3.8
- OpenCV
- NumPy
- ONNX Runtime

## Models Used

This project uses the following ONNX models:

| Model | Purpose | Source |
|-------|---------|--------|
| **modnet.onnx** | Background Removal | [MODNet](https://github.com/ZHKKKe/MODNet) - Efficient background removal model |
| **det_500m.onnx** | Face Detection | [InsightFace SCRFD](https://github.com/deepinsight/insightface) - SCRFD (Stable Cascaded Refinement Face Detector) buffalo_s model |
| **2d106det.onnx** | Face Landmark Detection | [InsightFace 2D106](https://github.com/deepinsight/insightface) - 106-point facial landmark detection model |

**Model Directory:** All models are stored in the `src/biyoves/models/` directory.

### Model Citations

- **MODNet**: Zhanghan Ke et al., "MODNet: Real-Time Trimap-Free Portrait Matting via Objective Decomposition," AAAI 2022.
- **InsightFace**: Jiankang Deng et al., "InsightFace: 2D and 3D Face Analysis Project."

## Third-Party Models and Licensing

The BiyoVes source code is MIT-licensed. Bundled model weights retain their
original terms and are not relicensed by this repository:

- MODNet code and published models are provided under Apache-2.0 by the
  [MODNet project](https://github.com/ZHKKKe/MODNet).
- InsightFace model-zoo weights, including the SCRFD and 2D106 components used
  here, are provided for **non-commercial research purposes only** according to
  the [InsightFace model-zoo notice](https://github.com/deepinsight/insightface/tree/master/model_zoo).

Review the upstream terms before redistributing the weights or using them in a
commercial product.

## License

The BiyoVes source code is released under the [MIT License](LICENSE). Third-party
model weights are governed by the terms listed above.
