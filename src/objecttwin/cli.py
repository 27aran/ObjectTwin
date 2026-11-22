"""Command line interface - handy for testing and scripting without the GUI.

Usage::

    python -m objecttwin.cli QUERY_IMAGE SEARCH_FOLDER [--top 5] [--model NAME] [--device cpu]
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from objecttwin import __version__
from objecttwin.embedder import DEFAULT_MODEL, Embedder
from objecttwin.imageio import ImageLoadError
from objecttwin.search import DEFAULT_TOP_K, Progress, search_similar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="objecttwin-cli",
        description="Find the images in a folder tree most similar to a query image (DINOv2).",
    )
    parser.add_argument("query", help="reference image (TIFF, PNG, JPEG, ...)")
    parser.add_argument("folder", help="folder to search (recursively)")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K, help="number of results")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model name or local path")
    parser.add_argument("--device", default=None, help="'cuda' or 'cpu' (default: auto)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    embedder = Embedder(args.model, device=args.device)
    print(f"Model: {args.model} on {embedder.device_name}", file=sys.stderr)

    def show_progress(p: Progress) -> None:
        print(f"\r{p.done}/{p.total} images", end="", file=sys.stderr, flush=True)

    try:
        result = search_similar(
            args.query, args.folder, embedder, top_k=args.top, on_progress=show_progress
        )
    except (ImageLoadError, NotADirectoryError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 2
    print(file=sys.stderr)

    for rank, match in enumerate(result.matches, start=1):
        print(f"{rank:>3}. {match.score:.4f}  {match.path}")
    print(
        f"{result.scanned} images compared, {len(result.skipped)} skipped, "
        f"{result.elapsed_s:.1f} s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
