"""Descriptor types (kept free of heavy imports so the GUI can use them at start-up)."""

from __future__ import annotations

from enum import StrEnum


class Descriptor(StrEnum):
    GLOBAL = "global"
    """CLS token - invariant to position / crop / viewpoint."""
    SPATIAL = "spatial"
    """8x8 grid of patch tokens - fine detail and layout."""
    HYBRID = "hybrid"
    """Both; similarity = mean of global and spatial similarity."""


DEFAULT_DESCRIPTOR = Descriptor.HYBRID
