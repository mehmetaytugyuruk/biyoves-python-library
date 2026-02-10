# BiyoVes - Python Library

AI-powered Biometric, Passport, and Visa photo generation library.

## Installation

```bash
pip install biyoves
```

Or from source:

```bash
git clone https://github.com/aytugyuruk/biyoves.git
cd biyoves
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

## Photo Types

- `"biyometrik"` - Standard biometric photo (50x60mm)
- `"vesikalik"` - Passport photo (45x60mm)
- `"abd_vizesi"` - US visa photo (50x50mm)
- `"schengen"` - Schengen visa photo (35x45mm)

## Layout Types

- `"2li"` - 2 photos stacked vertically (2x1)
- `"4lu"` - 4 photos in a grid (2x2)

## Features

- AI-powered automatic background removal
- Automatic face angle correction
- Automatic cropping to standard dimensions
- Print templates (2-up / 4-up layouts)
- Cut lines for print-ready output

## Example Usage

```python
from biyoves import BiyoVes

# Load a photo
img = BiyoVes("person.jpg")

# Save in different formats
img.create_image("vesikalik", "2li", "passport_2up.jpg")
img.create_image("vesikalik", "4lu", "passport_4up.jpg")
img.create_image("biyometrik", "2li", "biometric_2up.jpg")
img.create_image("abd_vizesi", "4lu", "us_visa_4up.jpg")
```

## Requirements

- Python >= 3.7
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

- **MODNet**: Ze Liu, etc. "Is Depth Really Necessary for Shadow Detection?"
- **InsightFace**: Jiankang Deng, etc. "InsightFace: 2D and 3D Face Analysis Project"

## License

MIT License
