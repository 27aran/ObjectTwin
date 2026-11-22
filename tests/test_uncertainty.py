import numpy as np
import pytest
from PIL import Image

from objecttwin.uncertainty import Thresholds, Verdict, analyse_scores, query_variants

N_VARIANTS = 9


def _gallery(
    special: list[float], n_background: int = 30, seed: int = 0, jitter: float = 0.005
) -> np.ndarray:
    """Score matrix: the first rows have the given mean scores, the rest is background."""
    rng = np.random.default_rng(seed)
    background = rng.normal(0.60, 0.03, n_background)
    means = np.concatenate([special, background])
    return means[:, None] + rng.normal(0, jitter, (len(means), N_VARIANTS))


def test_clear_winner_is_confident() -> None:
    a = analyse_scores(_gallery([0.95]))
    assert a.order[0] == 0
    assert a.votes[0] == pytest.approx(1.0)
    assert a.plausible[0]
    assert a.assessment.n_plausible == 1
    assert a.assessment.verdict == Verdict.CONFIDENT
    assert a.assessment.margin is not None and a.assessment.margin > 0.2
    assert a.assessment.z_score is not None and a.assessment.z_score > 3


def test_near_tie_is_ambiguous_and_both_plausible() -> None:
    a = analyse_scores(_gallery([0.930, 0.928], jitter=0.01))
    assert set(a.order[:2]) == {0, 1}
    assert a.plausible[0] and a.plausible[1]
    assert a.assessment.n_plausible >= 2
    assert a.assessment.verdict == Verdict.AMBIGUOUS
    assert a.votes[0] + a.votes[1] == pytest.approx(1.0)


def test_nothing_stands_out_is_no_match() -> None:
    a = analyse_scores(_gallery([], n_background=40))
    assert a.assessment.verdict == Verdict.NO_MATCH


def test_empty() -> None:
    a = analyse_scores(np.empty((0, N_VARIANTS)))
    assert a.assessment.verdict == Verdict.EMPTY
    assert a.assessment.n_plausible == 0
    assert len(a.order) == 0


def test_small_gallery_skips_z_score() -> None:
    a = analyse_scores(np.array([[0.9] * 3, [0.5] * 3]))
    assert a.assessment.z_score is None
    assert a.assessment.margin == pytest.approx(0.4)
    assert a.assessment.verdict == Verdict.CONFIDENT


def test_single_variant_without_augmentation() -> None:
    a = analyse_scores(np.array([[0.80], [0.79], [0.40]]))
    assert np.all(a.std == 0)
    assert a.votes.tolist() == [1.0, 0.0, 0.0]
    assert a.plausible.tolist() == [True, True, False]  # within min_margin
    assert a.assessment.verdict == Verdict.AMBIGUOUS


def test_thresholds_are_configurable() -> None:
    scores = np.array([[0.80], [0.79], [0.40]])
    strict = analyse_scores(scores, Thresholds(min_margin=0.001))
    assert strict.assessment.n_plausible == 1
    assert strict.assessment.verdict == Verdict.CONFIDENT


def test_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        analyse_scores(np.zeros(5))


def test_query_variants() -> None:
    img = Image.new("L", (120, 80), 100)
    variants = query_variants(img)
    assert len(variants) == N_VARIANTS
    assert all(v.mode == "RGB" for v in variants)
    assert variants[0].size == (120, 80)
    # deterministic
    again = query_variants(img)
    assert all(a.tobytes() == b.tobytes() for a, b in zip(variants, again, strict=True))
