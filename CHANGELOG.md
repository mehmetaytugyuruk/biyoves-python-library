# Changelog

All notable changes to BiyoVes are documented here.

## Unreleased

## 1.4.0 - 2026-08-25

- Corrected biometric crop geometry by using the proper 106-point chin landmark.
- Rejected implausible hair-top detections on busy backgrounds and added a
  visual regression test for head margin and shoulder coverage.
- Added safe CPU fallback when an available ONNX acceleration provider fails.
- Reframed the website around the open-source Python library while preserving
  the full live processing studio.

## 1.3.2 - 2026-08-25

- Corrected the minimum supported Python version to 3.8 because the bundled
  ONNX models require a runtime newer than the final Python 3.7 build.
- Expanded CI coverage to every supported Python version from 3.8 through 3.13.
- Added verified, tokenless PyPI publishing and GitHub Release automation.

## 1.3.1 - 2026-08-25

- Removed the input-resolution quality gate.
- Kept print output at 300 DPI.
- Simplified the quality report to blur, eye openness, and face angle.

## 1.3.0 - 2026-08-25

- Added directory batch processing with per-file results.
- Added optional preflight checks for blur, eye openness, and face angle.
- Reused loaded models across batch and quality operations.

## 1.2.0 - 2025-08-25

- Added type hints to the public API.
- Added 6-photo and 8-photo layouts.
- Added print-ready PDF output.
- Added automated pytest execution in CI.

## 1.1.0 - 2025-08-25

- Added automatic CPU/GPU provider selection.
- Improved orientation-correction performance.
- Exposed custom background colors across the public API.
- Added the initial test suite.
