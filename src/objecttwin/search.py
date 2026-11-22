"""Similarity search: rank all images below a folder by similarity to a query image."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from objecttwin.imageio import find_images, load_image

log = logging.getLogger(__name__)

DEFAULT_TOP_K = 10
DEFAULT_BATCH_SIZE = 16
DEFAULT_LOADER_THREADS = min(8, os.cpu_count() or 4)


class SupportsEmbedding(Protocol):
    """Interface the search needs from an embedder (see :class:`objecttwin.embedder.Embedder`)."""

    def preprocess(self, image: Image.Image) -> np.ndarray: ...

    def embed_batch(self, pixels: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class Match:
    path: Path
    score: float
    """Cosine similarity in ``[-1, 1]``; 1.0 means identical embedding."""


@dataclass(frozen=True, slots=True)
class Progress:
    done: int
    total: int


@dataclass
class SearchResult:
    matches: list[Match]
    """Best matches, most similar first."""
    scanned: int
    """Number of images that were successfully compared."""
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    """Files that could not be read, with the error message."""
    elapsed_s: float = 0.0


class SearchCancelled(Exception):
    """Raised when ``should_cancel`` returned True during a search."""


@dataclass(frozen=True, slots=True)
class _Loaded:
    path: Path
    pixels: np.ndarray | None
    error: str | None


def search_similar(
    query_path: str | os.PathLike[str],
    root: str | os.PathLike[str],
    embedder: SupportsEmbedding,
    *,
    top_k: int = DEFAULT_TOP_K,
    batch_size: int = DEFAULT_BATCH_SIZE,
    loader_threads: int = DEFAULT_LOADER_THREADS,
    on_progress: Callable[[Progress], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> SearchResult:
    """Find the images below *root* that are most similar to *query_path*.

    Images are decoded and pre-processed in a thread pool while the previous batch is
    being embedded. The query file itself is excluded from the results if it lives
    inside *root*. Unreadable files are skipped and reported in ``SearchResult.skipped``.

    Raises:
        ImageLoadError: if the query image cannot be read.
        NotADirectoryError: if *root* is not a directory.
        SearchCancelled: if *should_cancel* returns True.
    """
    started = time.perf_counter()
    query_vec = embedder.embed_batch(embedder.preprocess(load_image(query_path))[None])[0]

    query_resolved = Path(query_path).resolve()
    files = [p for p in find_images(root) if p.resolve() != query_resolved]
    total = len(files)
    log.info("Searching %d images below %s", total, root)
    if on_progress:
        on_progress(Progress(0, total))

    def load(path: Path) -> _Loaded:
        try:
            return _Loaded(path, embedder.preprocess(load_image(path)), None)
        except Exception as exc:
            log.warning("Skipping %s: %s", path, exc)
            return _Loaded(path, None, str(exc))

    batches = [files[i : i + batch_size] for i in range(0, total, batch_size)]
    paths: list[Path] = []
    vectors: list[np.ndarray] = []
    skipped: list[tuple[Path, str]] = []
    done = 0

    with ThreadPoolExecutor(max_workers=max(1, loader_threads)) as pool:

        def submit(batch: Sequence[Path]) -> list[Future[_Loaded]]:
            return [pool.submit(load, p) for p in batch]

        pending = submit(batches[0]) if batches else []
        for index in range(len(batches)):
            if should_cancel and should_cancel():
                for fut in pending:
                    fut.cancel()
                raise SearchCancelled
            loaded = [fut.result() for fut in pending]
            # Prefetch the next batch while this one is being embedded.
            pending = submit(batches[index + 1]) if index + 1 < len(batches) else []

            ok = [item for item in loaded if item.pixels is not None]
            skipped.extend((item.path, item.error or "") for item in loaded if item.error)
            if ok:
                vectors.append(embedder.embed_batch(np.stack([item.pixels for item in ok])))
                paths.extend(item.path for item in ok)

            done += len(loaded)
            if on_progress:
                on_progress(Progress(done, total))

    matches: list[Match] = []
    if vectors:
        scores = np.concatenate(vectors) @ query_vec
        order = np.argsort(-scores, kind="stable")[: max(0, top_k)]
        matches = [Match(paths[i], float(scores[i])) for i in order]

    return SearchResult(
        matches=matches,
        scanned=len(paths),
        skipped=skipped,
        elapsed_s=time.perf_counter() - started,
    )
