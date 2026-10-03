"""Cluster mass inference with the Flankers example's blocked label exchange.

The observation is a retained trial. Labels are shuffled within acquisition
block x target-side strata; no cross-condition trial pairs are constructed.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse, stats
from scipy.sparse.csgraph import connected_components


def pooled_t(X: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Signed two-sample t, True condition minus False condition."""
    a, b = X[labels], X[~labels]
    na, nb = len(a), len(b)
    variance = ((na - 1) * a.var(axis=0, ddof=1)
                + (nb - 1) * b.var(axis=0, ddof=1)) / (na + nb - 2)
    if np.any(variance <= 0):
        raise ValueError("Pooled t is undefined with zero within-condition variance")
    return (a.mean(axis=0) - b.mean(axis=0)) / np.sqrt(variance * (1 / na + 1 / nb))


def cluster_components(t_obs, adjacency, threshold, tail):
    """Return positive cluster labels and nonnegative directional masses."""
    t_obs = np.asarray(t_obs)
    selected = np.flatnonzero(tail * t_obs > tail * threshold)
    labels = np.zeros(t_obs.size, dtype=np.int32)
    if not selected.size:
        return labels, np.empty(0, dtype=float)
    count, components = connected_components(
        adjacency[selected][:, selected], directed=False, return_labels=True)
    labels[selected] = components + 1
    masses = np.bincount(components, weights=tail * t_obs[selected], minlength=count)
    return labels, masses


def iter_block_permutations(labels, strata, n_permutations, seed):
    """Observed identity first, then independent shuffles within each stratum."""
    labels, strata = np.asarray(labels, dtype=bool), np.asarray(strata)
    groups = [np.flatnonzero(strata == value) for value in np.unique(strata)]
    rng = np.random.RandomState(seed)
    yield labels.copy()
    for _ in range(n_permutations - 1):
        shuffled = labels.copy()
        for indices in groups:
            shuffled[indices] = rng.permutation(labels[indices])
        yield shuffled


def blocked_cluster_test(X, labels, strata, adjacency, tail,
                         n_permutations=5000, seed=42, forming_alpha=.05):
    """One-sided max cluster mass test, preserving within-stratum class counts.

    X is observations x flattened features. Adjacency must use exactly that
    feature ordering. The 5000 default includes the observed configuration and
    4999 random configurations. Thus each p is (1 + exceedances) / 5000, with
    ties counted and the maximum taken across the complete tested domain.
    """
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels, dtype=bool)
    strata = np.asarray(strata)
    adjacency = sparse.csr_matrix(adjacency)
    if X.ndim != 2 or labels.shape != (len(X),) or strata.shape != labels.shape:
        raise ValueError("Expected X[trial, feature] and one label/stratum per trial")
    if adjacency.shape != (X.shape[1], X.shape[1]):
        raise ValueError("Adjacency does not match flattened feature order")
    if tail not in (-1, 1) or n_permutations < 2:
        raise ValueError("Use a one-sided tail and at least two configurations")
    if min(labels.sum(), (~labels).sum()) < 2 or not np.isfinite(X).all():
        raise ValueError("Each condition needs two finite observations")
    df = len(X) - 2
    threshold = tail * float(stats.t.ppf(1 - forming_alpha, df))
    t_obs = pooled_t(X, labels)
    cluster_labels, masses = cluster_components(t_obs, adjacency, threshold, tail)
    H0 = np.empty(n_permutations, dtype=float)
    H0[0] = masses.max(initial=0)
    permutations = iter_block_permutations(labels, strata, n_permutations, seed)
    next(permutations)
    for index, shuffled in enumerate(permutations, start=1):
        _, null_masses = cluster_components(
            pooled_t(X, shuffled), adjacency, threshold, tail)
        H0[index] = null_masses.max(initial=0)
    cluster_p = np.array([(H0 >= mass).sum() / n_permutations for mass in masses])
    return dict(t_obs=t_obs, cluster_labels=cluster_labels, cluster_p=cluster_p,
                H0=H0, threshold=threshold, df=df)
