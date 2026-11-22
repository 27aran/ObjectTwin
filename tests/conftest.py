from pathlib import Path

import numpy as np
import pytest
from PIL import Image


class FakeEmbedder:
    """Cheap, deterministic stand-in for DINOv2: embedding = normalised 4x4 thumbnail."""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def preprocess(self, image: Image.Image) -> np.ndarray:
        return np.asarray(image.convert("RGB").resize((4, 4)), dtype=np.float32).ravel() + 1.0

    def embed_batch(self, pixels: np.ndarray) -> np.ndarray:
        self.batch_sizes.append(len(pixels))
        return pixels / np.linalg.norm(pixels, axis=1, keepdims=True)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


def save_solid(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (32, 24)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path
