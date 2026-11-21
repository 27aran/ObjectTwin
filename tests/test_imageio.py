from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image

from objecttwin.imageio import (
    ImageLoadError,
    array_to_rgb,
    find_images,
    is_supported,
    load_image,
)

H, W = 16, 24


def _gradient(dtype: type, maximum: float) -> np.ndarray:
    return np.linspace(0, maximum, H * W).reshape(H, W).astype(dtype)


def _assert_rgb(img: Image.Image) -> np.ndarray:
    assert img.mode == "RGB"
    assert img.size == (W, H)
    arr = np.asarray(img)
    assert arr.dtype == np.uint8
    return arr


# ------------------------------------------------------------------ TIFF


def test_tiff_uint8_rgb_roundtrip(tmp_path: Path) -> None:
    rgb = np.random.default_rng(0).integers(0, 256, (H, W, 3), dtype=np.uint8)
    tifffile.imwrite(tmp_path / "a.tif", rgb, photometric="rgb")
    np.testing.assert_array_equal(_assert_rgb(load_image(tmp_path / "a.tif")), rgb)


def test_tiff_uint16_low_range_is_stretched(tmp_path: Path) -> None:
    # Typical 12-bit camera data stored in 16 bit: only 0..4095 is used.
    tifffile.imwrite(tmp_path / "a.tiff", _gradient(np.uint16, 4095))
    arr = _assert_rgb(load_image(tmp_path / "a.tiff"))
    assert arr.min() == 0
    assert arr.max() == 255
    assert np.all(arr[..., 0] == arr[..., 1])  # grayscale -> identical channels


def test_tiff_float32(tmp_path: Path) -> None:
    data = _gradient(np.float32, 1.0)
    data[0, 0] = np.nan
    tifffile.imwrite(tmp_path / "f.tif", data)
    arr = _assert_rgb(load_image(tmp_path / "f.tif"))
    assert arr.max() == 255


def test_tiff_uint16_rgb(tmp_path: Path) -> None:
    rgb = np.stack([_gradient(np.uint16, 65535)] * 3, axis=-1)
    tifffile.imwrite(tmp_path / "rgb16.tif", rgb, photometric="rgb")
    _assert_rgb(load_image(tmp_path / "rgb16.tif"))


def test_tiff_planar_rgb(tmp_path: Path) -> None:
    planar = np.zeros((3, H, W), dtype=np.uint8)
    planar[0] = 200  # red plane
    tifffile.imwrite(tmp_path / "p.tif", planar, photometric="rgb", planarconfig="separate")
    arr = _assert_rgb(load_image(tmp_path / "p.tif"))
    assert (arr[..., 0] == 200).all()
    assert (arr[..., 1:] == 0).all()


def test_tiff_multipage_uses_first_page(tmp_path: Path) -> None:
    path = tmp_path / "stack.tif"
    with tifffile.TiffWriter(path) as tw:
        tw.write(np.full((H, W), 10, dtype=np.uint8))
        tw.write(np.full((H, W), 250, dtype=np.uint8))
    assert (_assert_rgb(load_image(path)) == 10).all()


@pytest.mark.parametrize("compression", ["lzw", "zlib", "jpeg", "packbits"])
def test_tiff_compressions(tmp_path: Path, compression: str) -> None:
    rgb = np.full((H, W, 3), 128, dtype=np.uint8)
    tifffile.imwrite(tmp_path / "c.tif", rgb, photometric="rgb", compression=compression)
    _assert_rgb(load_image(tmp_path / "c.tif"))


def test_tiff_written_by_pillow(tmp_path: Path) -> None:
    Image.new("RGB", (W, H), (1, 2, 3)).save(tmp_path / "pil.tif", compression="tiff_lzw")
    assert tuple(_assert_rgb(load_image(tmp_path / "pil.tif"))[0, 0]) == (1, 2, 3)


# ------------------------------------------------------------------ other formats


@pytest.mark.parametrize("ext", [".png", ".jpg", ".bmp", ".webp"])
def test_common_formats(tmp_path: Path, ext: str) -> None:
    Image.new("RGB", (W, H), (10, 200, 30)).save(tmp_path / f"img{ext}")
    _assert_rgb(load_image(tmp_path / f"img{ext}"))


def test_png_16bit_grayscale(tmp_path: Path) -> None:
    Image.fromarray(_gradient(np.uint16, 1000)).save(tmp_path / "g16.png")
    arr = _assert_rgb(load_image(tmp_path / "g16.png"))
    assert arr.max() == 255


def test_transparent_png_composited_on_white(tmp_path: Path) -> None:
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(tmp_path / "t.png")
    assert (_assert_rgb(load_image(tmp_path / "t.png")) == 255).all()


# ------------------------------------------------------------------ errors


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ImageLoadError):
        load_image(tmp_path / "nope.tif")


def test_corrupt_file_raises(tmp_path: Path) -> None:
    (tmp_path / "bad.tif").write_bytes(b"this is not a tiff")
    with pytest.raises(ImageLoadError):
        load_image(tmp_path / "bad.tif")


# ------------------------------------------------------------------ array_to_rgb


@pytest.mark.parametrize(
    "shape",
    [(H, W), (H, W, 1), (H, W, 2), (H, W, 3), (H, W, 4), (3, H, W), (7, H, W), (2, 5, H, W)],
)
def test_array_to_rgb_shapes(shape: tuple[int, ...]) -> None:
    out = array_to_rgb(np.zeros(shape, dtype=np.uint8))
    assert out.shape == (H, W, 3)
    assert out.dtype == np.uint8


def test_array_to_rgb_constant_and_bool() -> None:
    assert (array_to_rgb(np.full((H, W), 42.0)) == 0).all()
    assert array_to_rgb(np.ones((H, W), dtype=bool)).max() == 255


# ------------------------------------------------------------------ discovery


def test_find_images_recursive_and_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "b" / "deep").mkdir(parents=True)
    (tmp_path / "a").mkdir()
    for rel in ["root.TIF", "a/x.tiff", "b/deep/y.png", "b/notes.txt", "a/z.Jpg"]:
        (tmp_path / rel).write_bytes(b"")
    found = [p.relative_to(tmp_path).as_posix() for p in find_images(tmp_path)]
    assert found == ["root.TIF", "a/x.tiff", "a/z.Jpg", "b/deep/y.png"]


def test_find_images_rejects_non_directory(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        list(find_images(tmp_path / "missing"))


def test_is_supported() -> None:
    assert is_supported("x.TIFF")
    assert not is_supported("x.txt")
