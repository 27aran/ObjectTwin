"""Per-user application directories."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ObjectTwin"


def user_data_dir() -> Path:
    """``%LOCALAPPDATA%\\ObjectTwin`` on Windows, ``~/.local/share/ObjectTwin`` elsewhere."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_NAME


def log_dir() -> Path:
    return user_data_dir() / "logs"
