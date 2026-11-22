from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from objecttwin.embedder import CROP_SIZE, IMAGENET_MEAN, IMAGENET_STD, preprocess, select_device


@pytest.mark.parametrize("size", [(640, 480), (100, 900), (10, 10), (224, 224)])
def test_preprocess_shape(size: tuple[int, int]) -> None:
    out = preprocess(Image.new("RGB", size, (128, 64, 32)))
    assert out.shape == (3, CROP_SIZE, CROP_SIZE)
    assert out.dtype == np.float32


def test_preprocess_normalisation() -> None:
    out = preprocess(Image.new("RGB", (300, 300), (255, 0, 0)))
    expected = (np.array([1.0, 0.0, 0.0], dtype=np.float32) - IMAGENET_MEAN) / IMAGENET_STD
    np.testing.assert_allclose(out[:, 100, 100], expected, rtol=1e-5)


def test_preprocess_accepts_grayscale() -> None:
    assert preprocess(Image.new("L", (50, 60), 7)).shape == (3, CROP_SIZE, CROP_SIZE)


def test_select_device() -> None:
    assert select_device("cpu").type == "cpu"
    assert select_device().type in {"cpu", "cuda"}


# ---------------------------------------------------------------- real model (opt-in)


def _pattern(kind: str, size: int = 320) -> Image.Image:
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    if kind == "circles":
        for r in range(20, size // 2, 25):
            c = size // 2
            draw.ellipse((c - r, c - r, c + r, c + r), outline="black", width=6)
    else:  # stripes
        for x in range(0, size, 30):
            draw.rectangle((x, 0, x + 12, size), fill=(30, 90, 200))
    return img


@pytest.mark.model
def test_real_dinov2_ranks_same_motif_higher(tmp_path: Path) -> None:
    from objecttwin.embedder import Embedder

    embedder = Embedder("facebook/dinov2-small", device="cpu")
    query = _pattern("circles")
    same_motif = query.resize((200, 200)).rotate(5, fillcolor="white")
    other = _pattern("stripes")

    vecs = embedder.embed([query, same_motif, other])
    assert vecs.shape == (3, embedder.dim)
    np.testing.assert_allclose(np.linalg.norm(vecs, axis=1), 1.0, rtol=1e-4)
    assert vecs[0] @ vecs[1] > vecs[0] @ vecs[2]
