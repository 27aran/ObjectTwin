"""Locating bundled resources (model weights, icons) - from source and in the frozen exe.

Model lookup order (:func:`resolve_model_source`):

1. environment variable ``OBJECTTWIN_MODEL`` (Hugging Face id or local folder),
2. ``models/dinov2-base`` bundled next to the code (the PyInstaller build always ships
   it there; in a source checkout it exists after ``scripts/download_model.py``),
3. the Hugging Face id ``facebook/dinov2-base`` (downloaded and cached on first use).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

MODEL_ID = "facebook/dinov2-base"
MODEL_DIR_NAME = "dinov2-base"
MODEL_ENV_VAR = "OBJECTTWIN_MODEL"


def is_frozen() -> bool:
    """True when running from the PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Folder containing ``models/``: the exe's ``_internal`` folder or the project root."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]  # src/objecttwin/resources.py -> project root


def bundled_model_dir() -> Path:
    return bundle_root() / "models" / MODEL_DIR_NAME


def asset_path(name: str) -> Path:
    """Path of a file in ``objecttwin/assets`` (icons)."""
    return Path(__file__).resolve().parent / "assets" / name


def resolve_model_source() -> str:
    """Return the model to load (local folder or Hugging Face id), see module docstring.

    When a local folder is used, Hugging Face network access is disabled so the
    application works fully offline.
    """
    source = os.environ.get(MODEL_ENV_VAR, "").strip()
    if not source:
        local = bundled_model_dir()
        source = str(local) if (local / "config.json").is_file() else MODEL_ID
    if Path(source).is_dir():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    log.info("Model source: %s", source)
    return source
