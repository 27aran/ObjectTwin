"""DINOv2 image embeddings.

Each image is mapped to one L2-normalised vector, so cosine similarity is a plain dot
product. Three descriptor types are available (see :class:`Descriptor`):

* ``global``  - the layer-normalised CLS token: invariant to position / crop / viewpoint,
  captures *what kind of* image it is.
* ``spatial`` - patch tokens average-pooled to an 8x8 grid and flattened: compares the
  image region by region, captures fine detail and layout of *this particular* image.
* ``hybrid``  - both, each normalised and scaled by 1/sqrt(2) before concatenation, so
  the dot product equals the mean of the global and the spatial cosine similarity.

Pre-processing replicates the official DINOv2 image processor (resize shorter side to
256 px, bicubic -> centre crop 224 px -> ImageNet mean/std) with Pillow + numpy, which
avoids a dependency on torchvision.
"""

from __future__ import annotations

import contextlib
import logging
import math
import os
from collections.abc import Sequence

import numpy as np
import torch
from PIL import Image
from transformers import Dinov2Model
from transformers.utils import logging as hf_logging

from objecttwin.descriptor import DEFAULT_DESCRIPTOR, Descriptor
from objecttwin.resources import MODEL_ID

log = logging.getLogger(__name__)

# tqdm progress bars write to stderr, which does not exist in a windowed (no console)
# executable - and they are noise for a GUI anyway.
hf_logging.disable_progress_bar()

DEFAULT_MODEL = MODEL_ID
SPATIAL_GRID = 8

RESIZE_SHORTER_SIDE = 256
CROP_SIZE = 224
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def select_device(preferred: str | None = None) -> torch.device:
    """Return *preferred* if given, otherwise CUDA when available, else CPU."""
    if preferred:
        return torch.device(preferred)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def preprocess(image: Image.Image) -> np.ndarray:
    """Convert an RGB image into a normalised ``float32`` array of shape ``(3, 224, 224)``.

    Pure Pillow/numpy and thread-safe, so it can run in loader threads.
    """
    image = image.convert("RGB")
    w, h = image.size
    scale = RESIZE_SHORTER_SIDE / min(w, h)
    new_w, new_h = max(CROP_SIZE, round(w * scale)), max(CROP_SIZE, round(h * scale))
    image = image.resize((new_w, new_h), Image.Resampling.BICUBIC)

    left, top = (new_w - CROP_SIZE) // 2, (new_h - CROP_SIZE) // 2
    image = image.crop((left, top, left + CROP_SIZE, top + CROP_SIZE))

    arr = np.asarray(image, dtype=np.float32) / 255.0
    arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(arr.transpose(2, 0, 1))


class Embedder:
    """Wraps a DINOv2 model and turns images into normalised embedding vectors."""

    def __init__(
        self,
        model_name_or_path: str | os.PathLike[str] = DEFAULT_MODEL,
        device: str | None = None,
        descriptor: Descriptor | str = DEFAULT_DESCRIPTOR,
    ) -> None:
        self.device = select_device(device)
        self.model_name = str(model_name_or_path)
        log.info("Loading %s on %s", self.model_name, self.device_name)
        model = Dinov2Model.from_pretrained(self.model_name)
        self._model = model.eval().to(self.device)
        self._hidden: int = self._model.config.hidden_size
        self.descriptor = descriptor  # also sets self.dim

    @property
    def descriptor(self) -> Descriptor:
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: Descriptor | str) -> None:
        """Switch the descriptor type; cheap, the model is not reloaded."""
        self._descriptor = Descriptor(value)
        spatial = self._hidden * SPATIAL_GRID * SPATIAL_GRID
        self.dim: int = {
            Descriptor.GLOBAL: self._hidden,
            Descriptor.SPATIAL: spatial,
            Descriptor.HYBRID: self._hidden + spatial,
        }[self._descriptor]

    @property
    def device_name(self) -> str:
        """Human readable device description, e.g. ``"NVIDIA GeForce RTX 4070 (CUDA)"``."""
        if self.device.type == "cuda":
            return f"{torch.cuda.get_device_name(self.device)} (CUDA)"
        return "CPU"

    # Exposed as a method so callers can treat it as part of the embedder interface.
    preprocess = staticmethod(preprocess)

    @torch.inference_mode()
    def embed_batch(self, pixels: np.ndarray) -> np.ndarray:
        """Embed pre-processed images of shape ``(N, 3, 224, 224)`` -> ``(N, dim)``."""
        if len(pixels) == 0:
            return np.empty((0, self.dim), dtype=np.float32)
        batch = torch.from_numpy(np.asarray(pixels, dtype=np.float32)).to(self.device)
        autocast = (
            torch.autocast("cuda", dtype=torch.float16)
            if self.device.type == "cuda"
            else contextlib.nullcontext()
        )
        with autocast:
            hidden = self._model(pixel_values=batch).last_hidden_state  # layer-normed
        hidden = hidden.float()

        parts: list[torch.Tensor] = []
        if self.descriptor in (Descriptor.GLOBAL, Descriptor.HYBRID):
            parts.append(_normalize(hidden[:, 0]))
        if self.descriptor in (Descriptor.SPATIAL, Descriptor.HYBRID):
            parts.append(_normalize(_patch_grid(hidden[:, 1:], SPATIAL_GRID)))
        if len(parts) > 1:  # dot product of the concatenation = mean of the similarities
            parts = [part / math.sqrt(len(parts)) for part in parts]
        return torch.cat(parts, dim=-1).cpu().numpy()

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        """Convenience wrapper: pre-process and embed a list of PIL images."""
        if not images:
            return np.empty((0, self.dim), dtype=np.float32)
        return self.embed_batch(np.stack([preprocess(img) for img in images]))


def _normalize(x: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(x, dim=-1)


def _patch_grid(patches: torch.Tensor, grid: int) -> torch.Tensor:
    """Average-pool patch tokens ``(N, P, D)`` to a ``grid x grid`` map, flatten to 2-D."""
    n, num_patches, dim = patches.shape
    side = math.isqrt(num_patches)
    if side * side != num_patches:
        raise ValueError(f"Expected a square patch grid, got {num_patches} patches")
    fmap = patches.transpose(1, 2).reshape(n, dim, side, side)
    return torch.nn.functional.adaptive_avg_pool2d(fmap, grid).flatten(1)
