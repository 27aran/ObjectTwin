# Architecture

## Goal

Given a reference image *q* and a root folder *R*: among all images in *R* (recursively),
find the one whose content is most similar to *q* – independent of file name,
resolution or bit depth.

## Approach

1. **Load & normalise** – every image (especially TIFF with 8/16/32 bit, grayscale,
   multiple channels or pages) is converted to a uniform 8-bit RGB image.
2. **Embed** – DINOv2 (Vision Transformer) produces one feature vector per image
   (global CLS token and/or a spatial grid of patch tokens). The vectors are L2-normalised.
3. **Compare** – similarity = cosine similarity = dot product of the normalised vectors.
   Highest score = most similar image.
4. **Assess confidence** – the query is embedded in several perturbed variants; the
   stability of the ranking, the margin to the runner-up and how far the best match
   stands out from the crowd yield a verdict and a set of *plausible* candidates.

DINOv2 is well suited because it was trained without labels and therefore captures
general visual features (shape, texture, structure) – ideal for image-to-image retrieval.

## Modules

| Module                    | Responsibility                                                   |
|---------------------------|------------------------------------------------------------------|
| `objecttwin.imageio`      | find & load images, TIFF special cases, normalisation to RGB     |
| `objecttwin.embedder`     | load DINOv2, pick GPU/CPU, pre-process, compute embeddings       |
| `objecttwin.search`       | scan folder, parallel loading, batching, ranking, cancel/progress |
| `objecttwin.uncertainty`  | query variants, per-candidate statistics, confidence verdict     |
| `objecttwin.descriptor`   | descriptor enum (import-light, usable by the GUI at start-up)     |
| `objecttwin.cli`          | command line front end (for testing / scripting)                 |
| `objecttwin.gui`          | PySide6 user interface (see below)                               |
| `objecttwin.appdirs`      | per-user data / log directories                                  |
| `objecttwin.__main__`     | entry point – starts the GUI                                     |

The core logic (`imageio`, `embedder`, `search`, `uncertainty`) is independent of the GUI and tested
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
* **Feature:** see [Descriptors](#descriptors).
* **Device:** CUDA if `torch.cuda.is_available()`, otherwise CPU. On CUDA the forward
  pass runs under float16 autocast for speed; the output is converted back to float32.

## Search (`objecttwin.search`)

`search_similar(query, root, embedder, top_k=10, ...)`:

1. Load and embed the query image.
2. Collect all images below `root` via `find_images` (the query file itself is excluded).
3. Process them in batches (default 16). A thread pool decodes and pre-processes the
   *next* batch while the current one runs through the model, so disk / TIFF decoding
   and inference overlap.
4. Score every image against every query variant (only the scores are kept, not the
   embeddings – spatial descriptors are ~200 KB per image), analyse the score matrix
   (see [Confidence estimation](#confidence-estimation-objecttwinuncertainty)) and return
   the `top_k` best as `Match(path, score, score_std, votes, plausible)` plus an
   `Assessment`.

Unreadable files do not abort the search; they are listed in `SearchResult.skipped`.
`on_progress(Progress(done, total))` is called after every batch and `should_cancel()` is
polled before every batch (raises `SearchCancelled`) – this is what the GUI hooks into.

Score interpretation: 1.0 = identical embedding. Images of the same domain (e.g. all
microscopy, all photos of similar parts) can score 0.7–0.9 even when unrelated, so the
absolute value says little – the ranking and the confidence signals below matter.

## Descriptors

| Descriptor          | Vector                                                   | Size (base) | Good at                                    | Weak at                                    |
|---------------------|----------------------------------------------------------|-------------|--------------------------------------------|--------------------------------------------|
| `global`            | CLS token                                                | 768         | invariance to position, crop, viewpoint    | telling apart many images of the same kind |
| `spatial`           | patch tokens, average-pooled to 8 × 8, flattened         | 49 152      | fine detail and layout of *this* image     | strong shifts / rotations                  |
| `hybrid` (default)  | both, each normalised and scaled by 1/√2, concatenated   | 49 920      | compromise: dot product = mean of both similarities | –                                 |

Why `hybrid` is the default – measured on a synthetic, deliberately homogeneous set
(40 TIFFs of random shapes, 8 and 16 bit) with `dinov2-base`; *z* = robust z-score of the
best match (higher = stands out more), *rank* = position of the true counterpart:

| Query                                   | `global` z / rank | `spatial` (8×8) z / rank | `hybrid` z / rank |
|-----------------------------------------|-------------------|--------------------------|-------------------|
| noisy, downscaled copy                  | 2.2 / 1           | 7.2 / 1                  | 4.9 / 1           |
| shifted, rotated 12°, cropped, noisy    | 1.2 / **10**      | 2.5 / 1                  | 2.7 / 1           |
| image not in the folder                 | 1.2 / –           | 2.1 / –                  | 2.2 / –           |

The global CLS token alone cannot separate images that are all "of the same kind"; the
spatial grid can, and the combination keeps some invariance. Real data may favour a
different descriptor – it is a single parameter (`--descriptor`).

## Confidence estimation (`objecttwin.uncertainty`)

A single best score does not tell whether the model might be wrong. Three signals:

1. **Query test-time augmentation.** The query is embedded as 9 variants: original,
   zoom-in, two shifted crops, ±4° rotation, brightness −15 %, contrast +20 %, slight
   blur – mimicking realistic capture differences. For every candidate this gives
   * `score` = mean similarity, `score_std` = its standard deviation,
   * `votes` = fraction of variants for which the candidate ranks first
     (an empirical "how often would this be the answer").

   Only the query is augmented, so the cost is 8 extra forward passes per search.
2. **Margin** – best minus second-best mean score.
3. **Outlier strength** – robust z-score `(best − median) / (1.4826 · MAD)` over all
   candidates (computed for ≥ 8 candidates). A low value means the best match does not
   stand out – likely there is no real counterpart in the folder.

A candidate is **plausible** if its mean score is within
`max(sigma_k · sqrt(std_best² + std_i²), min_margin)` of the best one.

| Verdict      | Rule (checked in this order)                                     | Meaning for the user                                 |
|--------------|------------------------------------------------------------------|------------------------------------------------------|
| `empty`      | no images found                                                  | –                                                    |
| `no_match`   | z < `no_match_z`                                                 | best candidate does not stand out – verify carefully |
| `confident`  | best has votes ≥ `confident_votes` and is the only plausible one | clear match                                          |
| `ambiguous`  | otherwise                                                        | several plausible candidates – compare them          |

Default thresholds (`Thresholds`): `confident_votes = 0.8`, `min_margin = 0.02`,
`sigma_k = 2.0`, `no_match_z = 2.5`, `min_gallery_for_z = 8`.

Observed on the synthetic set with `hybrid`:

| Scenario                                                  | Verdict                                                   | Correct?        |
|-----------------------------------------------------------|-----------------------------------------------------------|-----------------|
| noisy copy of a folder image                              | `confident` (100 % votes)                                 | ✅              |
| folder contains the image *and* a near-identical variant  | `ambiguous`, both plausible                               | ✅              |
| image not in the folder                                   | `no_match` (although one wrong image got 89 % of votes)   | ✅              |
| shifted + rotated + noisy copy                            | `no_match`, but true image ranked 1st with 89 % votes     | ⚠️ too cautious |

Votes alone can be misleading (row 3); the combination of signals is what makes the
verdict useful. **The thresholds are not calibrated on real data.** With a handful of
labelled query/answer pairs from the target domain they can be tuned.

## GUI (`objecttwin.gui`)

| Module          | Content                                                                    |
|-----------------|----------------------------------------------------------------------------|
| `app`           | logging set-up (rotating file in `%LOCALAPPDATA%\ObjectTwin\logs`), `QApplication`, start |
| `main_window`   | the window: reference / candidate previews, folder & options, verdict banner, results table |
| `workers`       | `ModelLoader` and `SearchWorker` (background threads), PIL → `QImage` conversion |
| `widgets`       | `ImagePreview` – aspect-ratio preserving image label with placeholder text |
| `i18n`          | English / German strings, runtime switch, `tr(key, **kwargs)`               |

**Threading.** Nothing slow runs in the GUI thread. Workers are `QObject`s whose `run()`
executes in a Python *daemon* thread; their signals are delivered to the GUI thread via
queued connections. Daemon threads mean closing the window is never blocked (e.g. by a
model download). The search is cancelled cooperatively (`threading.Event`, checked
before every batch).

**Start-up time.** `torch` / `transformers` take seconds to import, so the GUI modules do
not import them; the window appears immediately and the model is created in the
`ModelLoader` thread. The embedder is created once and reused; switching the comparison
mode only changes `Embedder.descriptor` (no reload).

**Translations.** A plain dictionary instead of Qt's `.ts`/`.qm` tool chain – two
languages, ~80 strings, switchable without restart. A unit test enforces that every key
exists in every language with the same `{placeholders}`. Numbers use a decimal comma in
German.

**Settings** (`QSettings`, i.e. the registry under `HKCU\Software\ObjectTwin`): language,
last reference image, folder, number of candidates, comparison mode, window geometry.

**Tests.** `tests/test_gui.py` drives the real window headless (`QT_QPA_PLATFORM=offscreen`,
`pytest-qt`) with a fake embedder: full search, language switch, persistence, cancel,
error handling.
