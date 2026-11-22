"""Application bootstrap: logging, QApplication, main window."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from objecttwin import __version__
from objecttwin.appdirs import APP_NAME, log_dir
from objecttwin.resources import asset_path, resolve_model_source

log = logging.getLogger(__name__)


def setup_logging() -> None:
    """Log to a rotating file in the user data dir (+ stderr when a console exists)."""
    handlers: list[logging.Handler] = []
    try:
        folder = log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                folder / "objecttwin.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
        )
    except OSError:
        pass
    if sys.stderr is not None:  # None in a windowed (no console) executable
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.captureWarnings(True)  # library warnings go to the log file, not to stderr


def _create_embedder():  # pragma: no cover - needs the real model
    # Imported lazily: torch/transformers take a few seconds to import, the window
    # should appear immediately.
    from objecttwin.embedder import Embedder

    return Embedder(resolve_model_source())


def run(argv: Sequence[str] | None = None) -> int:
    setup_logging()
    log.info("Starting %s %s", APP_NAME, __version__)
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setOrganizationName(APP_NAME)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    icon = asset_path("objecttwin.png")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))

    from objecttwin.gui.main_window import MainWindow

    window = MainWindow(_create_embedder, QSettings())
    window.show()
    return app.exec()
