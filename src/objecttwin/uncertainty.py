"""Confidence estimation for a similarity ranking.

A single cosine score does not tell whether the best match is *clearly* the right one.
Three complementary signals are combined:

1. **Query test-time augmentation (TTA)** - the query is embedded in several slightly
   perturbed variants (crops, small rotations, brightness/contrast, blur) that mimic
   realistic capture differences. Each gallery image then has one score per variant:

   * ``mean`` / ``std`` of those scores - the score and how stable it is,
   * ``votes`` - fraction of variants for which the image ranks first. This is an
     empirical "how often would this be the answer" probability.

   Only the query is augmented, so the extra cost is a handful of forward passes.

2. **Margin** between best and second best mean score - small margin = ambiguous.

3. **Outlier strength** - robust z-score (median / MAD) of the best score relative to
   all scores. A best match that does not stand out from the crowd probably means the
   folder contains no real counterpart of the query.

Candidates whose mean score is statistically indistinguishable from the best one
(difference within ``sigma_k`` combined standard deviations, or below ``min_margin``)
are flagged as *plausible*.

The default thresholds are sensible starting points, not calibrated values; tune them
with labelled examples from the target data if available.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageStat

# Scale factor of the MAD to make it a consistent estimator of the standard deviation.
_MAD_TO_SIGMA = 1.4826


class Verdict(StrEnum):
    CONFIDENT = "confident"
    """One candidate clearly stands out and wins (almost) all query variants."""
    AMBIGUOUS = "ambiguous"
    """Several candidates are plausible - the user should compare them."""
    NO_MATCH = "no_match"
    """The best candidate does not stand out - likely no real counterpart in the folder."""
    EMPTY = "empty"
    """There was nothing to compare against."""


@dataclass(frozen=True, slots=True)
class Thresholds:
    confident_votes: float = 0.8
    """Minimum vote fraction of the best candidate for a CONFIDENT verdict."""
    min_margin: float = 0.02
    """Score differences below this are never considered significant."""
    sigma_k: float = 2.0
    """Candidates within ``sigma_k`` combined std of the best score are plausible."""
    no_match_z: float = 2.5
    """Robust z-score of the best candidate below which the verdict is NO_MATCH."""
    min_gallery_for_z: int = 8
    """The z-score is only meaningful (and computed) for at least this many images."""


@dataclass(frozen=True, slots=True)
class Assessment:
    verdict: Verdict
    margin: float | None
    """Mean score of best minus second best candidate (None if < 2 candidates)."""
    z_score: float | None
    """Robust z-score of the best candidate (None if too few candidates)."""
    n_plausible: int
    """Number of candidates indistinguishable from the best one (including it)."""
    n_variants: int
    """Number of query variants used (1 = no augmentation)."""


@dataclass(frozen=True, slots=True)
class Analysis:
    """Per-candidate statistics (arrays indexed like the input rows) plus the verdict."""

    mean: np.ndarray
    std: np.ndarray
    votes: np.ndarray
    plausible: np.ndarray
    order: np.ndarray
    """Candidate indices sorted by descending mean score."""
    assessment: Assessment


def query_variants(image: Image.Image) -> list[Image.Image]:
    """Return the original image followed by deterministic, mildly perturbed variants."""
    image = image.convert("RGB")
    w, h = image.size
    fill = tuple(int(c) for c in ImageStat.Stat(image).median)

    def crop(frac: float, fx: float, fy: float) -> Image.Image:
        cw, ch = max(1, round(w * frac)), max(1, round(h * frac))
        left, top = round((w - cw) * fx), round((h - ch) * fy)
        return image.crop((left, top, left + cw, top + ch))

    # Blur of roughly 1 px at the model's input resolution (shorter side 256 px).
    blur_radius = max(0.5, min(w, h) / 256)
    return [
        image,
        crop(0.9, 0.5, 0.5),  # zoom in
        crop(0.9, 0.0, 0.0),  # shift towards top-left
        crop(0.9, 1.0, 1.0),  # shift towards bottom-right
        image.rotate(4, resample=Image.Resampling.BICUBIC, fillcolor=fill),
        image.rotate(-4, resample=Image.Resampling.BICUBIC, fillcolor=fill),
        ImageEnhance.Brightness(image).enhance(0.85),
        ImageEnhance.Contrast(image).enhance(1.2),
        image.filter(ImageFilter.GaussianBlur(blur_radius)),
    ]


def analyse_scores(scores: np.ndarray, thresholds: Thresholds | None = None) -> Analysis:
    """Analyse a score matrix of shape ``(n_candidates, n_variants)``."""
    t = thresholds or Thresholds()
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 2:
        raise ValueError(f"scores must be 2-D (candidates x variants), got {scores.shape}")
    n, n_variants = scores.shape

    if n == 0:
        empty = np.empty(0)
        return Analysis(
            mean=empty,
            std=empty,
            votes=empty,
            plausible=np.empty(0, dtype=bool),
            order=np.empty(0, dtype=np.intp),
            assessment=Assessment(Verdict.EMPTY, None, None, 0, n_variants),
        )

    mean = scores.mean(axis=1)
    std = scores.std(axis=1)
    votes = np.bincount(scores.argmax(axis=0), minlength=n) / n_variants
    order = np.argsort(-mean, kind="stable")
    best = order[0]

    tolerance = np.maximum(t.sigma_k * np.sqrt(std[best] ** 2 + std**2), t.min_margin)
    plausible = (mean[best] - mean) <= tolerance
    n_plausible = int(plausible.sum())

    margin = float(mean[best] - mean[order[1]]) if n >= 2 else None
    z_score = _robust_z(mean, mean[best]) if n >= t.min_gallery_for_z else None

    if z_score is not None and z_score < t.no_match_z:
        verdict = Verdict.NO_MATCH
    elif votes[best] >= t.confident_votes and n_plausible == 1:
        verdict = Verdict.CONFIDENT
    else:
        verdict = Verdict.AMBIGUOUS

    return Analysis(
        mean=mean,
        std=std,
        votes=votes,
        plausible=plausible,
        order=order,
        assessment=Assessment(verdict, margin, z_score, n_plausible, n_variants),
    )


def _robust_z(values: np.ndarray, x: float) -> float:
    median = float(np.median(values))
    sigma = _MAD_TO_SIGMA * float(np.median(np.abs(values - median)))
    if sigma == 0.0:
        return float("inf") if x > median else 0.0
    return (x - median) / sigma
