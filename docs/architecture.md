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
| `objecttwin.embedder`     | load DINOv2, pick GPU/CPU, pre-process, compute embeddings       |
| `objecttwin.search`       | scan folder, parallel loading, batching, ranking, cancel/progress |
| `objecttwin.cli`          | command line front end (for testing / scripting)                 |
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

## Embeddings (`objecttwin.embedder`)

* **Model:** `facebook/dinov2-base` (ViT-B/14, 768-dim embedding). Any DINOv2 checkpoint
  name or local folder can be passed instead (e.g. `facebook/dinov2-small` – faster,
  slightly less accurate).
* **Pre-processing** (identical to the official DINOv2 processor, implemented with
  Pillow + numpy so `torchvision` is not needed): resize shorter side to 256 px
  (bicubic) → centre crop 224 × 224 → scale to 0–1 → ImageNet mean/std.
* **Feature:** `pooler_output` = layer-normalised CLS token, then L2-normalised.
* **Device:** CUDA if `torch.cuda.is_available()`, otherwise CPU. On CUDA the forward
  pass runs under float16 autocast for speed; the output is converted back to float32.

## Search (`objecttwin.search`)

`search_similar(query, root, embedder, top_k=10, ...)`:

1. Load and embed the query image.
2. Collect all images below `root` via `find_images` (the query file itself is excluded).
3. Process them in batches (default 16). A thread pool decodes and pre-processes the
   *next* batch while the current one runs through the model, so disk / TIFF decoding
   and inference overlap.
4. Score = dot product with the query vector; return the `top_k` best as `Match(path, score)`.

Unreadable files do not abort the search; they are listed in `SearchResult.skipped`.
`on_progress(Progress(done, total))` is called after every batch and `should_cancel()` is
polled before every batch (raises `SearchCancelled`) – this is what the GUI hooks into.

Score interpretation: 1.0 = identical embedding; near-duplicates typically score > 0.9;
unrelated images of the same domain can still score 0.6–0.8 because they share
low-level statistics. The ranking is what matters, not the absolute value.
