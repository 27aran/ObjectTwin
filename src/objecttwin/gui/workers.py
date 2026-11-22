"""Background workers - model loading and searching must never block the UI thread.

Workers are QObjects living in the GUI thread; their ``run`` method executes in a Python
daemon thread (``start()``). Signals emitted from that thread are delivered to the GUI
thread via queued connections. Daemon threads also guarantee that closing the window is
never blocked by e.g. a model download that is still running.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from objecttwin.imageio import load_image
from objecttwin.search import Progress, SearchCancelled, SupportsEmbedding, search_similar

log = logging.getLogger(__name__)


class _ThreadedWorker(QObject):
    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, name=type(self).__name__, daemon=True)
        thread.start()
        return thread

    def run(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


THUMBNAIL_SIZE = 512


def pil_to_qimage(image: Image.Image) -> QImage:
    """Convert a PIL image to a QImage that owns its pixel data (safe across threads)."""
    image = image.convert("RGB")
    w, h = image.size
    qimage = QImage(image.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
    return qimage.copy()  # detach from the Python bytes buffer


def load_thumbnail(path: str | Path, size: int = THUMBNAIL_SIZE) -> QImage:
    """Load any supported image as a QImage no larger than *size* x *size*."""
    image = load_image(path)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return pil_to_qimage(image)


class ModelLoader(_ThreadedWorker):
    """Creates the embedder (slow: imports weights, maybe downloads them)."""

    loaded = Signal(object)  # the embedder
    failed = Signal(str)

    def __init__(self, factory: Callable[[], SupportsEmbedding]) -> None:
        super().__init__()
        self._factory = factory

    def run(self) -> None:
        try:
            self.loaded.emit(self._factory())
        except Exception as exc:
            log.exception("Loading the model failed")
            self.failed.emit(str(exc))


class SearchWorker(_ThreadedWorker):
    """Runs :func:`search_similar` and prepares thumbnails of the matches."""

    progress = Signal(int, int)  # done, total
    finished = Signal(object, dict)  # SearchResult, {path str: QImage}
    cancelled = Signal()
    failed = Signal(str)

    def __init__(
        self,
        embedder: SupportsEmbedding,
        query: Path,
        folder: Path,
        top_k: int,
    ) -> None:
        super().__init__()
        self._embedder = embedder
        self._query = query
        self._folder = folder
        self._top_k = top_k
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Thread-safe: request cancellation; takes effect before the next batch."""
        self._cancel.set()

    def run(self) -> None:
        try:
            result = search_similar(
                self._query,
                self._folder,
                self._embedder,
                top_k=self._top_k,
                on_progress=self._report,
                should_cancel=self._cancel.is_set,
            )
            thumbnails: dict[str, QImage] = {}
            for match in result.matches:
                if self._cancel.is_set():
                    raise SearchCancelled
                try:
                    thumbnails[str(match.path)] = load_thumbnail(match.path)
                except Exception as exc:  # thumbnail is cosmetic - never fail the search
                    log.warning("No thumbnail for %s: %s", match.path, exc)
        except SearchCancelled:
            self.cancelled.emit()
        except Exception as exc:
            log.exception("Search failed")
            self.failed.emit(str(exc))
        else:
            self.finished.emit(result, thumbnails)

    def _report(self, p: Progress) -> None:
        self.progress.emit(p.done, p.total)
