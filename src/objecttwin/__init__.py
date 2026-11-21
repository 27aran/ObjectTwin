"""ObjectTwin - find the most similar image in a folder tree using DINOv2 embeddings."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("objecttwin")
except PackageNotFoundError:  # running from a source checkout / frozen exe
    __version__ = "0.1.0"

__all__ = ["__version__"]
