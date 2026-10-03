"""Independent numeric and permutation-design checks for repaired case studies."""
from itertools import product
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse, stats

sys.path.insert(0, str(Path(__file__).parents[1]))
from case_study_stats import (blocked_cluster_test, cluster_components,
                             iter_block_permutations, pooled_t)


def test_pooled_t_matches_scipy_with_unequal_trial_counts_and_volt_units():
    rng = np.random.RandomState(19)
    X = rng.normal(size=(17, 12)) * 1e-6
    X[:7, :4] -= 2e-6
    labels = np.arange(17) < 7
    expected = stats.ttest_ind(X[labels], X[~labels], equal_var=True).statistic
    np.testing.assert_allclose(pooled_t(X, labels), expected, rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize('tail', [-1, 1])
def test_cluster_partition_and_mass_matches_mne_observed_map(tail):
    import mne
    rng = np.random.RandomState(12)
    X = rng.normal(size=(28, 6))
    labels = np.arange(28) < 13
    X[labels, 0:2] += tail * 3
    X[labels, 4:6] += tail * 3
    adjacency = sparse.diags([np.ones(5), np.ones(5)], [-1, 1], shape=(6, 6)).tocsr()
    threshold = tail * stats.t.ppf(.95, 26)
    actual = blocked_cluster_test(X, labels, np.zeros(28), adjacency, tail, 32)
    observed, clusters, _, _ = mne.stats.permutation_cluster_test(
        [X[labels], X[~labels]], stat_fun=mne.stats.ttest_ind_no_p,
        threshold=threshold, tail=tail, adjacency=adjacency,
        n_permutations=2, seed=42, out_type='mask', verbose=False)
    np.testing.assert_allclose(actual['t_obs'], observed, rtol=1e-13, atol=1e-13)
    expected_members = {tuple(np.flatnonzero(mask)) for mask in clusters}
    actual_members = {tuple(np.flatnonzero(actual['cluster_labels'] == i))
                      for i in range(1, actual['cluster_labels'].max() + 1)}
    assert actual_members == expected_members
    expected_max = max(tail * observed[mask].sum() for mask in clusters)
    assert actual['H0'][0] == pytest.approx(expected_max)


def test_block_permutations_keep_all_trials_and_each_stratum_count():
    labels = np.array([1, 1, 0, 0, 0, 1, 0, 1, 0], bool)
    strata = np.array([0, 0, 0, 0, 0, 1, 1, 2, 2])
    draws = list(iter_block_permutations(labels, strata, 100, 42))
    np.testing.assert_array_equal(draws[0], labels)
    assert any(not np.array_equal(draw, labels) for draw in draws[1:])
    for draw in draws:
        for group in range(3):
            assert draw[strata == group].sum() == labels[strata == group].sum()
    np.testing.assert_array_equal(draws, list(iter_block_permutations(labels, strata, 100, 42)))


def test_blocked_null_matches_exhaustive_small_design_and_plus_one_p():
    # Two matched acquisition strata, each with one A and one B trial. Enumerate
    # the four possible labelings independently of the sampler and t helper.
    X = np.array([[5., 4.], [0., .5], [6., 5.], [1., 0.]])
    labels = np.array([1, 0, 1, 0], bool)
    strata = np.array([0, 0, 1, 1])
    adjacency = sparse.csr_matrix(np.ones((2, 2)))
    result = blocked_cluster_test(X, labels, strata, adjacency, 1, 4000, 42)
    threshold = stats.t.ppf(.95, 2)
    exact_masses = []
    for a0, a1 in product([0, 1], repeat=2):
        selected = [a0, 2 + a1]
        remaining = sorted(set(range(4)) - set(selected))
        t = stats.ttest_ind(X[selected], X[remaining], equal_var=True).statistic
        exact_masses.append(t[t > threshold].sum())  # two adjacent features
    for mass in set(exact_masses):
        probability = sum(v == mass for v in exact_masses) / 4
        assert np.isclose(result['H0'][1:], mass).mean() == pytest.approx(probability, abs=.035)
    observed_mass = exact_masses[0]
    expected_p = (1 + np.count_nonzero(result['H0'][1:] >= observed_mass)) / 4000
    assert result['cluster_p'][0] == expected_p


def test_no_observed_cluster_keeps_the_complete_null_and_empty_results():
    X = np.array([[1., 2.], [3., 4.], [1.1, 2.1], [3.1, 4.1]])
    result = blocked_cluster_test(X, [1, 1, 0, 0], [0, 0, 0, 0], sparse.eye(2), 1, 20)
    assert result['cluster_p'].size == 0
    assert result['cluster_labels'].tolist() == [0, 0]
    assert len(result['H0']) == 20
