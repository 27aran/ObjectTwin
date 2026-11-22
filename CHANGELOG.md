# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased

### Added
- MIT license (`LICENSE`); the executable now also ships `LICENSE` and
  `third-party-licenses.md`.
- Developer credit in the GUI: status bar link, *Help → Developer on LinkedIn* and the
  *About* dialog.

### Planned
- Calibrate the confidence thresholds and the default comparison mode on real example
  images from the target domain.

## 0.1.0 – 2026-11-22

First release.

### Added
- **Image loading** for TIFF (8/16/32-bit integer, float, grayscale, planar, multi-page,
  LZW/Deflate/JPEG/PackBits compression) and PNG, JPEG, BMP, GIF, WebP; robust contrast
  stretching for high bit depths; recursive folder scan.
- **Similarity search** with DINOv2 (ViT-B/14) embeddings – *hybrid* (default),
  *global* and *spatial* descriptors; parallel image loading, batching, cancellation,
  progress reporting; unreadable files are skipped and reported.
- **Confidence estimation**: query test-time augmentation (9 variants) → per-candidate
  score ± std and *agreement* (vote share); margin and robust z-score → verdict
  *confident* / *ambiguous* / *no match*; *plausible* flag for candidates that are not
  significantly worse than the best one.
- **GUI** (PySide6): reference image with preview, folder selection, drag & drop,
  options, progress + cancel, colour-coded verdict banner, result table with thumbnails,
  side-by-side comparison, open / show in Explorer, English / German at runtime,
  persistent settings, log file.
- **Command line** interface `python -m objecttwin.cli`.
- **Windows executable** via PyInstaller (one-folder): CUDA 12.6 build with automatic
  CPU fallback and a CPU-only build; model bundled for offline use;
  `ObjectTwin.exe --self-test`.
- Documentation: README, architecture, build guide, user guide (EN/DE), third-party
  licenses.

