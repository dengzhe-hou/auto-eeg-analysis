"""Keep CV folds, participant observations and permutation units distinct."""
import numpy as np


def cv_splits(X, y, *, splitter, groups):
    """Materialize an approved splitter; preserve its indices in the output record.

    Pass groups=None only for an approved design without grouped splitting.
    A supplied group is an atomic train-or-test unit, such as a person or block.
    """
    y = np.asarray(y)
    if len(X) != len(y):
        raise ValueError('X and y must have the same trial identities/order')
    if groups is not None:
        groups = np.asarray(groups)
        if groups.shape != y.shape:
            raise ValueError('CV groups must have one identity per trial')
    splits, receipt = [], []
    for train, test in splitter.split(X, y, groups):
        train, test = np.asarray(train), np.asarray(test)
        if np.intersect1d(train, test).size:
            raise ValueError('A trial occurs in both training and test data')
        if groups is not None and np.intersect1d(groups[train], groups[test]).size:
            raise ValueError('A CV group occurs in both training and test data')
        splits.append((train, test))
        receipt.append({'train': train.tolist(), 'test': test.tolist()})
    if not splits:
        raise ValueError('The approved splitter produced no folds')
    return splits, receipt


def aggregate_folds(fold_scores, *, splits, method):
    """Collapse only the fold axis, with the approved rule, not an inferred one."""
    scores = np.asarray(fold_scores, float)
    if scores.ndim < 1 or scores.shape[0] != len(splits) or not len(splits):
        raise ValueError('Scores must have one row per actual CV split')
    if not np.all(np.isfinite(scores)):
        raise ValueError('Undefined scores; review the approved null/CV design')
    if method == 'mean':
        return scores.mean(axis=0)
    if method == 'test_size_weighted':
        return np.average(scores, axis=0, weights=[len(test) for _, test in splits])
    raise ValueError('Resolve fold_aggregation: mean or test_size_weighted')


def participant_record(participant_id, fold_scores, *, times, splits, fold_aggregation):
    """Summarize within-participant CV, using an explicitly approved fold rule.

    The caller must obtain participant_id from the actual input recording, not
    from fold numbers. Pooled-participant CV does not create these observations.
    """
    scores, times = np.asarray(fold_scores, float), np.asarray(times, float)
    if participant_id is None or not str(participant_id):
        raise ValueError('An actual participant identity is required')
    if times.ndim != 1 or scores.shape != (len(splits), len(times)):
        raise ValueError('Expected fold_scores with shape (n_folds, n_times)')
    if not np.all(np.isfinite(scores)) or not np.all(np.isfinite(times)):
        raise ValueError('Unavailable scores cannot enter participant inference')
    score = aggregate_folds(scores, splits=splits, method=fold_aggregation)
    return dict(observation_unit='participant', participant_id=str(participant_id),
                score=score, times=times.copy(), fold_scores=scores.copy(),
                fold_aggregation=fold_aggregation,
                splits=[dict(train=np.asarray(a).tolist(), test=np.asarray(b).tolist())
                        for a, b in splits])


def participant_matrix(records):
    """One row per real participant; never infer the sample size from CV folds."""
    if not isinstance(records, (list, tuple)) or any(not isinstance(r, dict) for r in records):
        raise ValueError('Provide participant records, not a fold-score array')
    if len(records) < 2:
        raise ValueError('Group inference requires at least two actual participants')
    ids, rows = [], []
    times = np.asarray(records[0]['times'])
    for record in records:
        if record['observation_unit'] != 'participant':
            raise ValueError('Group inference accepts participant observations, not folds')
        identity = str(record['participant_id'])
        if identity in ids:
            raise ValueError('A participant has multiple rows; resolve approved aggregation')
        if not np.array_equal(record['times'], times):
            raise ValueError('Participant time grids differ')
        score = np.asarray(record['score'], float)
        if score.shape != times.shape or not np.all(np.isfinite(score)):
            raise ValueError('Invalid or unavailable participant score time course')
        ids.append(identity)
        rows.append(score)
    return np.stack(rows), ids, times.copy()


def permuted_labels(y, *, policy, units, exchangeability_blocks, rng):
    """Draw from an approved exchangeability scheme, independently of CV groups.

    within_unit: shuffle trials within each (unit, block).
    between_units: exchange each unit's constant label within its block, then
    broadcast it back to all that unit's trials. Unequal trial counts are OK.
    Identity permutations are valid draws and are retained. A scheme which can
    never change any labels raises an error rather than producing a null test.
    """
    y, units, blocks = map(np.asarray, (y, units, exchangeability_blocks))
    if y.ndim != 1 or units.shape != y.shape or blocks.shape != y.shape:
        raise ValueError('Labels, permutation units and blocks need one entry per trial')
    result = y.copy()
    can_change = False
    if policy == 'within_unit':
        for unit in np.unique(units):
            for block in np.unique(blocks[units == unit]):
                idx = np.flatnonzero((units == unit) & (blocks == block))
                can_change |= np.unique(y[idx]).size > 1
                result[idx] = rng.permutation(y[idx])
    elif policy == 'between_units':
        unit_ids = np.unique(units)
        unit_labels, unit_blocks = [], []
        for unit in unit_ids:
            mask = units == unit
            if np.unique(y[mask]).size != 1 or np.unique(blocks[mask]).size != 1:
                raise ValueError('Between-unit exchange requires one label and block per unit')
            unit_labels.append(y[mask][0])
            unit_blocks.append(blocks[mask][0])
        unit_labels, unit_blocks = np.asarray(unit_labels), np.asarray(unit_blocks)
        for block in np.unique(unit_blocks):
            idx = np.flatnonzero(unit_blocks == block)
            can_change |= np.unique(unit_labels[idx]).size > 1
            shuffled = rng.permutation(unit_labels[idx])
            for unit, label in zip(unit_ids[idx], shuffled):
                result[units == unit] = label
    else:
        raise ValueError('Resolve permutation policy: within_unit or between_units')
    if not can_change:
        raise ValueError('The approved permutation scheme cannot change any labels')
    return result


def permutation_scores(estimator, X, y, splits, *, scoring, n_permutations,
                       policy, units, exchangeability_blocks, seed,
                       fold_aggregation):
    """Refit each shuffled dataset on the same explicitly approved CV indices.

    Returns uncorrected pointwise p values for time-resolved scores. No temporal
    multiplicity correction or participant inference is implied by this helper.
    """
    from mne.decoding import cross_val_multiscore

    if n_permutations < 1:
        raise ValueError('n_permutations must be positive')
    rng = np.random.default_rng(seed)
    # Validate the null scheme before fitting. The first draw is used, not discarded.
    first = permuted_labels(y, policy=policy, units=units,
                            exchangeability_blocks=exchangeability_blocks, rng=rng)

    def evaluate(labels):
        fold_scores = cross_val_multiscore(estimator, X, labels, cv=splits,
                                          scoring=scoring, n_jobs=1)
        return aggregate_folds(fold_scores, splits=splits, method=fold_aggregation)

    observed = evaluate(y)
    null = [evaluate(first)]
    for _ in range(1, n_permutations):
        shuffled = permuted_labels(y, policy=policy, units=units,
                                  exchangeability_blocks=exchangeability_blocks, rng=rng)
        null.append(evaluate(shuffled))
    null = np.asarray(null)
    p_values = (1 + np.sum(null >= observed, axis=0)) / (n_permutations + 1)
    return observed, null, p_values
