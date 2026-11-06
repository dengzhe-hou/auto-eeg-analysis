"""Descriptive ITC and a bounded, explicitly approved condition-label test."""
import numpy as np


def unit_phasors(coefficients, *, trial_axis):
    """Preserve all other axes; zero-amplitude coefficients have undefined phase."""
    coefficients = np.asarray(coefficients)
    if not np.iscomplexobj(coefficients):
        raise ValueError('ITC requires single-trial complex coefficients, not averaged power')
    ordered = np.moveaxis(coefficients, trial_axis, 0)
    amplitude = np.abs(ordered)
    if not len(ordered) or not np.all(np.isfinite(amplitude)) or np.any(amplitude == 0):
        raise ValueError('Resolve unavailable/zero-amplitude phase observations before ITC')
    return ordered / amplitude


def itc_from_complex(coefficients, *, trial_axis):
    phasors = unit_phasors(coefficients, trial_axis=trial_axis)
    return np.abs(phasors.mean(axis=0))


def inference_route(*, target, null_operation):
    """Route the declared target; a route is not approval or null validation."""
    if target == 'descriptive':
        if null_operation is not None:
            raise ValueError('Descriptive ITC does not declare a significance null')
        return 'descriptive'
    if target not in ('single_condition_locking', 'condition_difference'):
        raise ValueError('Resolve ITC target: descriptive, single_condition_locking or condition_difference')
    if null_operation is None:
        raise ValueError('An inferential target needs an explicitly approved null operation')
    if null_operation == 'trial_order':
        raise ValueError('Pure trial reordering leaves ITC unchanged and is not this inferential null')
    if target == 'single_condition_locking' and null_operation == 'condition_label_exchange':
        raise ValueError('Condition-label exchange tests a condition difference, not absolute locking')
    if target == 'condition_difference' and null_operation == 'condition_label_exchange':
        return 'condition_label_exchange'
    return 'separate_approved_test'


def condition_label_test(coefficients, labels, *, trial_axis, participant_ids,
                         conditions, exchangeability_blocks, n_permutations,
                         seed, alternative):
    """Single participant, two conditions, approved within-block label exchange.

    Computes ITC(first condition)-ITC(second condition). Trial counts are kept;
    identity permutations are allowed. Streams exceedance counts, without a
    permutations x channel x frequency x time null array. P values are pointwise
    and uncorrected. This is not an absolute-locking or a population-level test.
    """
    phasors = unit_phasors(coefficients, trial_axis=trial_axis)
    labels, people, blocks = map(np.asarray, (labels, participant_ids, exchangeability_blocks))
    if labels.ndim != 1 or any(x.shape != labels.shape for x in (people, blocks)) or len(labels) != len(phasors):
        raise ValueError('Labels, participant IDs and blocks must align with the actual trial axis')
    if len(np.unique(people)) != 1:
        raise ValueError('This bounded test accepts one actual participant, not pooled participant trials')
    if (len(conditions) != 2 or conditions[0] == conditions[1]
            or set(np.unique(labels)) != set(conditions)):
        raise ValueError('Supply exactly the two approved conditions and their selected trials')
    if n_permutations < 1 or alternative not in ('greater', 'less', 'two_sided'):
        raise ValueError('Resolve permutation count and alternative explicitly')
    block_indices = [np.flatnonzero(blocks == block) for block in np.unique(blocks)]
    if not any(len(np.unique(labels[idx])) > 1 for idx in block_indices):
        raise ValueError('Approved within-block label exchange cannot change condition membership')

    def statistic(current):
        return (np.abs(phasors[current == conditions[0]].mean(axis=0))
                - np.abs(phasors[current == conditions[1]].mean(axis=0)))

    observed = statistic(labels)
    exceedances = np.zeros(observed.shape, dtype=np.int64)
    rng = np.random.default_rng(seed)
    for _ in range(n_permutations):
        shuffled = labels.copy()
        for idx in block_indices:
            shuffled[idx] = rng.permutation(shuffled[idx])
        null = statistic(shuffled)
        if alternative == 'greater':
            exceedances += null >= observed
        elif alternative == 'less':
            exceedances += null <= observed
        else:
            exceedances += np.abs(null) >= np.abs(observed)
    p_values = (exceedances + 1) / (n_permutations + 1)
    return dict(target='condition_difference', null_operation='condition_label_exchange',
                participant_id=str(people[0]), conditions=list(conditions),
                trial_counts=[int(np.sum(labels == cond)) for cond in conditions],
                observed_difference=observed, p_uncorrected=p_values, exceedances=exceedances,
                n_permutations=n_permutations, seed=seed, alternative=alternative,
                exchangeability_blocks=blocks.tolist(), multiplicity='uncorrected')
