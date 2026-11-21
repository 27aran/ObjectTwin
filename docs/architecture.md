# Architecture

## Goal

Given a reference image *q* and a root folder *R*: among all images in *R* (recursively),
find the one whose content is most similar to *q* – independent of file name,
resolution or bit depth.

## Approach

1. **Load & normalise** – every image (especially TIFF with 8/16/32 bit, grayscale,
   multiple channels or pages) is converted to a uniform 8-bit RGB image.
2. **Embed** – DINOv2 (Vision Transformer) produces one global feature vector per
   image (CLS token). The vectors are L2-normalised.
3. **Compare** – similarity = cosine similarity = dot product of the normalised vectors.
   Highest score = most similar image.

DINOv2 is well suited because it was trained without labels and therefore captures
general visual features (shape, texture, structure) – ideal for image-to-image retrieval.

## Modules

| Module                    | Responsibility                                                   |
|---------------------------|------------------------------------------------------------------|
| `objecttwin.imageio`      | find & load images, TIFF special cases, normalisation to RGB     |
| `objecttwin.embedder`     | load DINOv2 (bundled or downloaded), compute embeddings          |
| `objecttwin.search`       | compute similarities, ranking                                    |
| `objecttwin.gui`          | PySide6 user interface, background worker for the search         |
| `objecttwin.__main__`     | entry point                                                      |

The core logic (`imageio`, `embedder`, `search`) is independent of the GUI and tested
separately.

## Technology

| Area             | Choice                    | Rationale                                          |
|------------------|---------------------------|----------------------------------------------------|
| Language         | Python 3.11               | PyTorch / DINOv2 ecosystem                         |
| Package manager  | uv                        | fast, reproducible (`uv.lock`)                     |
| Model            | DINOv2 via `transformers` | official weights, can be bundled for offline use   |
| TIFF             | Pillow + `tifffile`       | `tifffile` covers 16/32-bit & scientific TIFFs     |
| GUI              | PySide6 (Qt)              | native look, threading, good PyInstaller support   |
| Packaging        | PyInstaller               | produces a standalone `.exe`                       |

## Image loading (`objecttwin.imageio`)

`load_image(path)` always returns an 8-bit RGB image (`PIL.Image`).

| Case                                  | Handling                                                     |
|---------------------------------------|--------------------------------------------------------------|
| TIFF (all variants)                   | `tifffile` first (+ `imagecodecs` for LZW, JPEG, Deflate, …), Pillow as fallback |
| 16/32-bit integer, float              | contrast stretch to 0–255 (0.5th to 99.5th percentile, robust against outlier pixels) |
| NaN / ±Inf                            | set to the edge of the value range                           |
| Grayscale / gray + alpha              | expanded to 3 identical channels                             |
| Planar TIFF `(C, H, W)`               | reordered to `(H, W, C)`                                     |
| Multi-page / Z-stack / pyramid        | first page or first plane, full resolution                   |
| `MinIsWhite` TIFF                     | inverted                                                     |
| Transparency (PNG, GIF, …)            | composited onto a white background                           |
| JPEG with EXIF rotation               | rotation is applied                                          |

`find_images(root)` searches `root` recursively and yields all supported files
(`.tif .tiff .png .jpg .jpeg .bmp .gif .webp`, case-insensitive) in a fixed, sorted order.
