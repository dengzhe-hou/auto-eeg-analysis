"""Explicit cluster-threshold conversion and TFCE point-output mapping."""
import numpy as np
from scipy.stats import t


def cluster_t_threshold(*, n_observations, cluster_forming_alpha, tail):
    """Convert an approved cluster-forming alpha to a t threshold, not FWER."""
    if n_observations < 2 or not 0 < cluster_forming_alpha < 1 or tail not in (-1, 0, 1):
        raise ValueError("Supply N>=2, a cluster-forming alpha in (0,1), and tail -1/0/1")
    df = n_observations - 1
    probability = (cluster_forming_alpha if tail == -1 else
                   1 - cluster_forming_alpha / 2 if tail == 0 else
                   1 - cluster_forming_alpha)
    return float(t.ppf(probability, df))


def tfce_p_map(statistic, clusters, p_values):
    """Map TFCE's singleton point masks to the actual statistic grid.

    Use MNE out_type='mask'. The p-values are a flat sequence associated with
    the returned masks, not necessarily ordered like an already shaped image.
    This function is specific to TFCE singleton clusters, not cluster-sum p's.
    """
    shape = np.shape(statistic)
    p_values = np.asarray(p_values, dtype=float)
    if len(clusters) != p_values.size:
        raise ValueError("Each returned TFCE point mask needs its corresponding p-value")
    result = np.full(shape, np.nan)
    occupied = np.zeros(shape, dtype=bool)
    for cluster, value in zip(clusters, p_values):
        mask = np.asarray(cluster)
        if mask.dtype != bool or mask.shape != shape or np.count_nonzero(mask) != 1:
            raise ValueError("Use TFCE singleton masks in the statistic grid, out_type='mask'")
        if np.any(occupied & mask):
            raise ValueError("A TFCE point was mapped more than once")
        result[mask] = value
        occupied |= mask
    if not occupied.all():
        raise ValueError("TFCE point masks do not cover the full statistic grid")
    return result
