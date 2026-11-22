"""DINOv2 image embeddings.

Each image is mapped to one global feature vector (the layer-normalised CLS token,
``pooler_output``) which is L2-normalised, so cosine similarity is a plain dot product.

Pre-processing replicates the official DINOv2 image processor (resize shorter side to
256 px, bicubic -> centre crop 224 px -> ImageNet mean/std) with Pillow + numpy, which
avoids a dependency on torchvision.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Sequence

import numpy as np
import torch
from PIL import Image
from transformers import Dinov2Model
from transformers.utils import logging as hf_logging

log = logging.getLogger(__name__)

# tqdm progress bars write to stderr, which does not exist in a windowed (no console)
# executable - and they are noise for a GUI anyway.
hf_logging.disable_progress_bar()

DEFAULT_MODEL = "facebook/dinov2-base"

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
    ) -> None:
        self.device = select_device(device)
        log.info("Loading %s on %s", model_name_or_path, self.device_name)
        model = Dinov2Model.from_pretrained(str(model_name_or_path))
        self._model = model.eval().to(self.device)
        self.dim: int = self._model.config.hidden_size

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
            features = self._model(pixel_values=batch).pooler_output
        features = torch.nn.functional.normalize(features.float(), dim=-1)
        return features.cpu().numpy()

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        """Convenience wrapper: pre-process and embed a list of PIL images."""
        if not images:
            return np.empty((0, self.dim), dtype=np.float32)
        return self.embed_batch(np.stack([preprocess(img) for img in images]))
