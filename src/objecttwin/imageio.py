"""Image loading and normalisation.

Every image - regardless of format, bit depth or channel layout - is converted to an
8-bit RGB :class:`PIL.Image.Image`, which is what the embedding model and the GUI
preview expect.

TIFF files get special treatment because they are frequently "scientific" images:
16/32-bit integers, floats, grayscale, planar channel layout, multiple pages or
pyramid levels. They are read with :mod:`tifffile` (with :mod:`imagecodecs` for all
compression schemes) and fall back to Pillow if that fails.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image, ImageOps

log = logging.getLogger(__name__)

# The user loads their own local files; very large microscopy / scan images are
# legitimate here, so disable Pillow's decompression-bomb guard.
Image.MAX_IMAGE_PIXELS = None

TIFF_EXTENSIONS: frozenset[str] = frozenset({".tif", ".tiff"})
SUPPORTED_EXTENSIONS: frozenset[str] = TIFF_EXTENSIONS | frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
)

# Percentiles used to stretch high-bit-depth data into 0..255. Clipping the extreme
# 0.5 % on each side keeps single hot/dead pixels from flattening the contrast.
_STRETCH_LOW_PCT = 0.5
_STRETCH_HIGH_PCT = 99.5

# Pillow modes that Image.convert("RGB") handles correctly.
_PIL_DIRECT_MODES = frozenset({"1", "L", "LA", "P", "PA", "RGB", "RGBA", "RGBX", "CMYK", "YCbCr"})


class ImageLoadError(Exception):
    """Raised when a file cannot be read as an image."""


def is_supported(path: str | os.PathLike[str]) -> bool:
    """Return True if the file extension is one ObjectTwin can load."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def find_images(root: str | os.PathLike[str]) -> Iterator[Path]:
    """Yield all supported image files below *root* (recursive, sorted, case-insensitive)."""
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort(key=str.lower)  # deterministic traversal order
        for name in sorted(filenames, key=str.lower):
            if is_supported(name):
                yield Path(dirpath) / name


def load_image(path: str | os.PathLike[str]) -> Image.Image:
    """Load *path* and return it as an 8-bit RGB image.

    For multi-page files only the first page (full resolution) is used.

    Raises:
        ImageLoadError: if the file is missing, unsupported or corrupt.
    """
    path = Path(path)
    if not path.is_file():
        raise ImageLoadError(f"File not found: {path}")

    errors: list[str] = []
    loaders = (
        (_load_tiff, _load_pillow) if path.suffix.lower() in TIFF_EXTENSIONS else (_load_pillow,)
    )
    for loader in loaders:
        try:
            return loader(path)
        except Exception as exc:
            log.debug("%s failed for %s: %s", loader.__name__, path, exc)
            errors.append(f"{loader.__name__}: {exc}")
    raise ImageLoadError(f"Cannot read image {path} ({'; '.join(errors)})")


def array_to_rgb(array: np.ndarray) -> np.ndarray:
    """Convert an arbitrary image array to ``uint8`` RGB with shape ``(H, W, 3)``.

    Handles grayscale, gray+alpha, RGB(A), channels-first layouts, image stacks
    (first plane is used) and any numeric dtype (high bit depths are contrast-stretched).
    """
    arr = np.asarray(array)
    if arr.dtype == bool:
        arr = arr.astype(np.uint8) * 255
    arr = np.squeeze(arr)

    # Reduce to (H, W) or (H, W, C).
    while arr.ndim > 3:
        arr = arr[0]
    if arr.ndim == 3:
        if arr.shape[-1] <= 4:
            pass  # channels-last
        elif arr.shape[0] <= 4:
            arr = np.moveaxis(arr, 0, -1)  # channels-first (planar TIFF)
        else:
            arr = arr[0]  # stack of planes (e.g. Z-stack) -> first plane
    if arr.ndim not in (2, 3):
        raise ValueError(f"Unsupported image shape {np.shape(array)}")

    arr = _to_uint8(arr)

    if arr.ndim == 2:
        return np.stack([arr] * 3, axis=-1)
    channels = arr.shape[-1]
    if channels in (1, 2):  # gray / gray + alpha
        return np.repeat(arr[..., :1], 3, axis=-1)
    return np.ascontiguousarray(arr[..., :3])  # RGB, drop alpha / extra channels


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.uint8:
        return arr
    data = arr.astype(np.float64)
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(data[finite], [_STRETCH_LOW_PCT, _STRETCH_HIGH_PCT])
    if hi <= lo:  # (nearly) constant image - fall back to the full range
        lo, hi = float(data[finite].min()), float(data[finite].max())
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    data = np.nan_to_num(data, nan=lo, posinf=hi, neginf=lo)
    scaled = (np.clip(data, lo, hi) - lo) * (255.0 / (hi - lo))
    return np.rint(scaled).astype(np.uint8)


def _load_tiff(path: Path) -> Image.Image:
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]  # first page = full resolution of first image
        arr = page.asarray()
        photometric = page.photometric
    if photometric == tifffile.PHOTOMETRIC.MINISWHITE:
        arr = np.iinfo(arr.dtype).max - arr if arr.dtype.kind in "ui" else arr.max() - arr
    return Image.fromarray(array_to_rgb(arr))


def _load_pillow(path: Path) -> Image.Image:
    with Image.open(path) as img:
        img.seek(0)
        img = ImageOps.exif_transpose(img)
        if img.mode in _PIL_DIRECT_MODES:
            if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
                # Composite onto white so transparent areas don't turn black.
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                return background
            return img.convert("RGB")
        # High bit depth modes (I;16, I, F, ...) -> normalise via numpy.
        return Image.fromarray(array_to_rgb(np.array(img)))
