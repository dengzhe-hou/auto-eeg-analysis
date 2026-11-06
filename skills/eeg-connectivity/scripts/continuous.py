"""Connectivity over time samples, distinct from spectral epoch estimators."""
import numpy as np


def plv_from_analytic(analytic):
    phase = np.exp(1j * np.angle(analytic))
    return np.abs(phase @ phase.conj().T / phase.shape[-1])


def ordinary_wpli_from_analytic(analytic):
    """Preserve analytic amplitude weights; self/zero-denominator entries NaN."""
    analytic = np.asarray(analytic)
    matrix = np.full((len(analytic), len(analytic)), np.nan)
    for i in range(len(analytic)):
        for j in range(i + 1, len(analytic)):
            imaginary = np.imag(analytic[i] * analytic[j].conj())
            denominator = np.mean(np.abs(imaginary))
            value = abs(np.mean(imaginary)) / denominator if denominator > 0 else np.nan
            matrix[i, j] = matrix[j, i] = value
    return matrix


def rank_distinct_pairs(matrix, channels):
    """Descending signed value; actual label pairs break exact ties."""
    pairs = [(float(matrix[i, j]), sorted([channels[i], channels[j]]))
             for i in range(len(channels)) for j in range(i + 1, len(channels))]
    return sorted(pairs, key=lambda item: (-item[0], item[1]))


def summarize_undirected_connectivity(matrix, channels, *, top_k):
    """Generate counts, mean and ranked labels from the actual matrix once."""
    matrix = np.asarray(matrix)
    names = list(channels)
    if matrix.shape != (len(names), len(names)) or len(names) < 2:
        raise ValueError("The actual connectivity matrix and channel labels must agree")
    ranked = rank_distinct_pairs(matrix, names)
    if not 0 <= top_k <= len(ranked):
        raise ValueError("Requested top_k exceeds the actual distinct-pair count")
    values = np.asarray([value for value, pair in ranked])
    if not np.isfinite(values).all():
        raise ValueError("Undefined distinct edges need the approved missing-value policy; do not omit them")
    return {"global_mean": float(values.mean()),
            "top_pairs": [pair for value, pair in ranked[:top_k]],
            "top_values": [value for value, pair in ranked[:top_k]],
            "metadata": {"channels": names, "n_channels": matrix.shape[0],
                         "n_undirected_pairs": len(ranked)}}


def hemisphere_difference(matrix, channels, *, homologous_pairs):
    positions = {channel: i for i, channel in enumerate(channels)}
    means = []
    for side in (0, 1):
        selected = [positions[pair[side]] for pair in homologous_pairs]
        if len(selected) < 2:
            raise ValueError("Within-hemisphere comparison needs two channels per side")
        means.append(float(np.mean([matrix[i, j] for k, i in enumerate(selected) for j in selected[k + 1:]])))
    return means[0] - means[1]
