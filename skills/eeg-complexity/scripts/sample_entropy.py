"""Count SampEn matches without allocating a dense pairwise distance matrix."""

import numpy as np
from scipy.spatial import cKDTree


def sample_entropy(x, m=2, r_fraction=0.2, *, closed=True):
    """Return SampEn, match counts and the numerical conventions used.

    Both embedding dimensions use N-m templates. Matches exclude self-pairs
    and use Chebyshev distance <= r (closed=True) or < r (closed=False).
    r is r_fraction times this segment's population standard deviation.
    Zero match counts produce an undefined (NaN) entropy, not a zero entropy.
    The tree counts pairs directly; no distance matrix or neighbor list is kept.
    """
    x = np.asarray(x, dtype=float)
    if not isinstance(m, (int, np.integer)) or m < 1:
        raise ValueError("m must be a positive integer")
    if x.ndim != 1 or x.size <= m:
        raise ValueError("x must be a one-dimensional segment with more than m samples")
    if not np.isfinite(x).all() or not np.isfinite(r_fraction) or r_fraction < 0:
        raise ValueError("Samples and r_fraction must be finite; r_fraction must be nonnegative")

    tolerance = float(r_fraction * np.std(x, ddof=0))
    radius = tolerance if closed else np.nextafter(tolerance, -np.inf)
    templates = np.lib.stride_tricks.sliding_window_view(x, m + 1)
    counts = []
    for width in (m, m + 1):
        if radius < 0:
            counts.append(0)
            continue
        tree = cKDTree(np.ascontiguousarray(templates[:, :width]))
        ordered_with_self = int(tree.count_neighbors(tree, radius, p=np.inf))
        counts.append((ordered_with_self - len(templates)) // 2)
    b, a = counts
    value = float(-np.log(a / b)) if a > 0 and b > 0 else float("nan")
    return {
        "sample_entropy": value,
        "matching_pairs_m": b,
        "matching_pairs_m_plus_1": a,
        "templates": len(templates),
        "m": int(m),
        "tolerance": tolerance,
        "sd_ddof": 0,
        "comparison": "<= r" if closed else "< r",
    }
