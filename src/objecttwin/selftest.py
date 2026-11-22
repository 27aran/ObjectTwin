"""``ObjectTwin.exe --self-test`` - verifies an installation without user interaction.

Checks PyTorch / CUDA, loads the model, reads a 16-bit TIFF, embeds it, measures the
throughput and verifies that Qt can be imported. The report is written to
``%LOCALAPPDATA%\\ObjectTwin\\logs\\selftest.txt`` (and printed if a console exists).
Exit code 0 = all good.
"""

from __future__ import annotations

import logging
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np

from objecttwin import __version__
from objecttwin.appdirs import log_dir

log = logging.getLogger(__name__)

REPORT_NAME = "selftest.txt"


def report_path() -> Path:
    return log_dir() / REPORT_NAME


def _test_image() -> np.ndarray:
    """16-bit test pattern (gradient + rings) - exercises the high-bit-depth TIFF path."""
    y, x = np.mgrid[0:300, 0:400].astype(np.float32)
    rings = np.sin(np.hypot(x - 200, y - 150) / 9.0)
    return ((x / 400 + 0.5 * rings + 0.5) * 20000).astype(np.uint16)


def run_self_test() -> int:
    lines = [
        f"ObjectTwin {__version__} self-test",
        f"Python {platform.python_version()} on {platform.platform()}",
        f"Frozen executable: {bool(getattr(sys, 'frozen', False))}",
    ]
    ok = True

    def check(name: str, func) -> None:
        nonlocal ok
        started = time.perf_counter()
        try:
            detail = func()
            lines.append(f"[ OK ] {name}: {detail} ({time.perf_counter() - started:.1f} s)")
        except Exception:
            ok = False
            lines.append(f"[FAIL] {name}:\n{traceback.format_exc()}")

    state: dict[str, object] = {}

    def check_torch() -> str:
        import torch

        info = f"torch {torch.__version__}, CUDA build {torch.version.cuda or 'none'}"
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            major, minor = torch.cuda.get_device_capability(0)
            return f"{info}, GPU: {name} (sm_{major}{minor})"
        return f"{info}, no usable GPU - CPU will be used"

    def check_model() -> str:
        from objecttwin.embedder import Embedder
        from objecttwin.resources import resolve_model_source

        source = resolve_model_source()
        embedder = Embedder(source)
        state["embedder"] = embedder
        return f"{source} on {embedder.device_name}, descriptor {embedder.descriptor}"

    def check_tiff_and_embedding() -> str:
        import tifffile

        from objecttwin.imageio import load_image

        embedder = state["embedder"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selftest_16bit.tif"
            tifffile.imwrite(path, _test_image(), compression="zlib")
            image = load_image(path)
        vectors = embedder.embed([image, image.rotate(3), image.transpose(0)])
        norms = np.linalg.norm(vectors, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-3):
            raise AssertionError(f"embeddings not normalised: {norms}")
        same, flipped = float(vectors[0] @ vectors[1]), float(vectors[0] @ vectors[2])
        if not same > 0.8:
            raise AssertionError(f"rotated copy too dissimilar: {same:.3f}")
        return f"dim {vectors.shape[1]}, sim(rotated)={same:.3f}, sim(mirrored)={flipped:.3f}"

    def check_throughput() -> str:
        from objecttwin.embedder import CROP_SIZE

        embedder = state["embedder"]
        batch = np.random.default_rng(0).normal(size=(16, 3, CROP_SIZE, CROP_SIZE))
        embedder.embed_batch(batch.astype(np.float32))  # warm-up
        started = time.perf_counter()
        embedder.embed_batch(batch.astype(np.float32))
        return f"{16 / (time.perf_counter() - started):.1f} images/s"

    def check_qt() -> str:
        from PySide6 import __version__ as qt_version
        from PySide6.QtWidgets import QWidget  # noqa: F401

        return f"PySide6 {qt_version}"

    check("PyTorch / CUDA", check_torch)
    check("Load model", check_model)
    if "embedder" in state:
        check("16-bit TIFF -> embedding", check_tiff_and_embedding)
        check("Throughput", check_throughput)
    check("Qt", check_qt)
    lines.append("RESULT: " + ("PASSED" if ok else "FAILED"))

    text = "\n".join(lines)
    log.info("Self-test report:\n%s", text)
    try:
        path = report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    except OSError:
        log.exception("Could not write the self-test report")
    if sys.stdout is not None:
        print(text)
    return 0 if ok else 1
