"""Proportional graphs from declared available edges, not full-array quantiles."""
import numpy as np


def proportional_adjacency(matrix, *, node_names, available_edges, storage, directed,
                           density, ranking, rounding, ties):
    """Select an approved fraction of available unique off-diagonal edges.

    storage: lower, upper, symmetric (undirected), or directed (ordered edges).
    availability is an explicit mask from estimator indices, never matrix!=0.
    ranking: weight or magnitude; no implicit abs, clipping or sign exclusion.
    rounding: floor, ceil, nearest (ties-to-even); ties: error, include_all,
    or channel_order (the declared node order breaks equal-score ties).
    """
    if np.iscomplexobj(matrix):
        raise ValueError('Resolve the approved real edge statistic before graph ranking')
    matrix = np.asarray(matrix, float)
    available = np.asarray(available_edges, bool)
    names = list(node_names)
    n = len(names)
    if n < 2 or len(set(names)) != n or matrix.shape != (n, n) or available.shape != (n, n):
        raise ValueError('Select one real-valued band with matching distinct node names and edge mask')
    if np.any(np.diag(available)):
        raise ValueError('Available edges must exclude the diagonal')
    if not 0 <= density <= 1:
        raise ValueError('Approve a density between 0 and 1')
    if ranking not in ('weight', 'magnitude') or rounding not in ('floor', 'ceil', 'nearest'):
        raise ValueError('Resolve approved ranking and edge-count rounding')
    if ties not in ('error', 'include_all', 'channel_order'):
        raise ValueError('Resolve approved boundary-tie policy')
    if directed:
        if storage != 'directed':
            raise ValueError('Directed edges require directed storage; do not mirror them')
        candidate = available
    else:
        if storage == 'lower':
            if np.any(np.triu(available)):
                raise ValueError('Lower storage requires a lower-triangle availability mask')
            candidate = available
        elif storage == 'upper':
            if np.any(np.tril(available)):
                raise ValueError('Upper storage requires an upper-triangle availability mask')
            candidate = available
        elif storage == 'symmetric':
            if (not np.array_equal(available, available.T)
                    or not np.array_equal(matrix[available], matrix.T[available])):
                raise ValueError('Declared symmetric values/availability disagree; resolve representation')
            candidate = np.triu(available, 1)
        else:
            raise ValueError('Declare lower, upper or symmetric storage for an undirected graph')
    rows, cols = np.nonzero(candidate)
    if not directed:
        # Use one canonical node-pair order, so channel-order tie handling
        # agrees for equivalent lower, upper and symmetric representations.
        canonical = np.lexsort((np.maximum(rows, cols), np.minimum(rows, cols)))
        rows, cols = rows[canonical], cols[canonical]
    weights = matrix[rows, cols]
    m = len(weights)
    if m == 0 or not np.all(np.isfinite(weights)):
        raise ValueError('No usable available edges, or an available edge is nonfinite')
    scores = np.abs(weights) if ranking == 'magnitude' else weights
    target = {'floor':np.floor, 'ceil':np.ceil, 'nearest':np.rint}[rounding](density * m)
    target = int(target)
    order = np.argsort(-scores, kind='stable')
    selected = order[:target]
    cutoff = float(scores[order[target-1]]) if target else None
    if 0 < target < m and scores[order[target-1]] == scores[order[target]]:
        if ties == 'error':
            raise ValueError('Boundary scores tie; resolve the approved graph tie policy')
        if ties == 'include_all':
            selected = np.flatnonzero(scores >= cutoff)
    adjacency = np.zeros((n, n), bool)
    adjacency[rows[selected], cols[selected]] = True
    if not directed:
        adjacency |= adjacency.T
    possible = n * (n-1) if directed else n * (n-1)//2
    edges = [dict(source=names[rows[i]], target=names[cols[i]],
                  weight=float(weights[i]), ranking_score=float(scores[i])) for i in selected]
    audit = dict(method='proportional_of_available_edges', node_names=names, directed=directed,
                 storage=storage, ranking=ranking, rounding=rounding, ties=ties,
                 requested_density=density, n_available_edges=m, n_possible_edges=possible,
                 target_edge_count=target, retained_edge_count=len(selected),
                 actual_density_available=len(selected)/m,
                 actual_density_all_possible=len(selected)/possible,
                 cutoff_score=cutoff, selected_edges=edges)
    return adjacency, audit
