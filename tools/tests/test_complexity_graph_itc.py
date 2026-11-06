"""Execute the public examples against finite LZ, native edges and ITC nulls."""
import itertools
import json
from pathlib import Path
import re
import runpy
import textwrap

import antropy
import mne
import mne_connectivity
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
lz = runpy.run_path(str(ROOT/'skills/eeg-complexity/scripts/lempel_ziv.py'))
graph = runpy.run_path(str(ROOT/'skills/eeg-connectivity/scripts/graph.py'))
itc = runpy.run_path(str(ROOT/'skills/eeg-tfr/scripts/itc.py'))
mne.set_log_level('ERROR')


def example(skill, label, **context):
    source = (ROOT/f'skills/{skill}/references/procedure.md').read_text()
    code, = [textwrap.dedent(block) for block in re.findall(r'```python\n(.*?)```', source, re.S)
             if f'# AEA example: {label}\n' in block]
    ns = {'np':np, 'AEA_ROOT':str(ROOT), **context}
    exec(compile(code, f'{skill}:{label}', 'exec'), ns)
    return ns


def ordinal_sequence(x, m):
    lookup = {perm:i for i,perm in enumerate(itertools.permutations(range(m)))}
    windows = np.lib.stride_tricks.sliding_window_view(x, m)
    return np.array([lookup[tuple(order)] for order in np.argsort(windows, axis=-1)])


def test_documented_five_second_binary_lzc_accepts_value_above_one():
    x = np.random.default_rng(10).normal(size=1250)  # 5 s at 250 Hz, as reviewed
    out = example('eeg-complexity', 'complexity-lzc', x=x,
                  approved_lzc_params={'symbolization':'median', 'alphabet_size':2})
    result = out['lzc_result']
    assert result['value'] == pytest.approx(1.0534617476658636)
    assert result['value'] > 1 and result['n_symbols'] == 1250
    assert result['raw_count'] == antropy.lziv_complexity(out['symbols'], normalize=False)
    assert result['normalization_base'] == 2
    assert result['backend_version'] == antropy.__version__


def test_finite_lzc_example_is_not_clipped_and_symbol_codes_do_not_change_parse():
    symbols = np.array(list('1001111011000010'), int)
    a = lz['symbolic_lzc'](symbols, alphabet_size=2)
    b = lz['symbolic_lzc'](symbols*17+9, alphabet_size=2)
    assert a['value'] == b['value'] == 1.5
    assert a['raw_count'] == b['raw_count'] == 6


def test_documented_ordinal_lzc_is_normalized_once_from_actual_motifs():
    symbols = ordinal_sequence(np.random.default_rng(10).normal(size=1250), 4)
    out = example('eeg-complexity', 'complexity-plzc-normalization', ordinal_symbols=symbols,
        approved_plzc_params={'alphabet_policy':'theoretical', 'embedding_dimension':4,
                             'delay':1, 'ordinal_tie_policy':'stable_rank'})
    result = out['plzc_result']
    assert result['raw_count'] == 307 and result['n_symbols'] == 1247
    assert result['observed_alphabet'] == result['normalization_base'] == 24
    assert result['value'] == pytest.approx(.5522154838224911)
    assert result['value'] == pytest.approx(antropy.lziv_complexity(symbols, normalize=True))
    assert result['value'] != pytest.approx(.12044056712255215)
    assert result['ordinal_tie_policy'] == 'stable_rank'


def test_missing_motifs_distinguish_observed_and_theoretical_alphabets():
    symbols = ordinal_sequence(np.arange(250.), 4)  # only one of 24 possible motifs
    observed = lz['symbolic_lzc'](symbols, alphabet_size='observed')
    theoretical = lz['symbolic_lzc'](symbols, alphabet_size=24)
    assert observed['observed_alphabet'] == 1
    assert observed['normalization_base'] == 2
    assert observed['value'] == pytest.approx(antropy.lziv_complexity(symbols, normalize=True))
    assert theoretical['value'] == pytest.approx(observed['value']*np.log(2)/np.log(24))


@pytest.mark.parametrize('metric', ['pe', 'nsc'])
def test_bounded_entropy_retains_its_upper_bound(metric):
    lz['check_normalized_complexity']([0., .5, 1.], metric=metric)
    with pytest.raises(ValueError, match=r'\[0,1\]'):
        lz['check_normalized_complexity']([1.05], metric=metric)


@pytest.mark.parametrize('metric', ['lzc', 'plzc'])
def test_lz_range_is_finite_nonnegative_without_a_unit_upper_bound(metric):
    lz['check_normalized_complexity']([0., 1.05, 1.5], metric=metric)
    for value in (np.nan, np.inf, -.1):
        with pytest.raises(ValueError, match='finite and nonnegative'):
            lz['check_normalized_complexity']([value], metric=metric)


def test_raw_eeg_is_not_mistaken_for_symbol_ids_and_missing_policy_is_unresolved():
    with pytest.raises(ValueError, match='integer symbols'):
        lz['symbolic_lzc']([.1, .2, .3], alphabet_size=2)
    with pytest.raises(ValueError, match='Declare alphabet_size'):
        lz['symbolic_lzc']([0, 1, 2], alphabet_size=2)
    with pytest.raises(ValueError, match='approved symbolization'):
        example('eeg-complexity', 'complexity-lzc', x=np.arange(50.),
                approved_lzc_params={'symbolization':'mean', 'alphabet_size':2})


def graph_policy(n=5, **overrides):
    return dict(node_names=[f'N{i}' for i in range(n)], available_edges=np.tril(np.ones((n,n), bool), -1),
                storage='lower', directed=False, density=.2, ranking='weight',
                rounding='floor', ties='error', **overrides)


def lower_matrix(n=5):
    matrix = np.zeros((n,n))
    matrix[np.tril_indices(n,-1)] = np.arange(1, n*(n-1)//2+1)/10
    return matrix


def test_documented_graph_on_actual_mne_native_matrix_keeps_two_of_ten_edges():
    data = np.random.default_rng(7).normal(0, 1e-6, (12,5,500))
    con = mne_connectivity.spectral_connectivity_epochs(
        data, method='coh', mode='fourier', sfreq=250., fmin=8., fmax=12.,
        faverage=True, n_jobs=1, verbose=False)
    matrix = con.get_data(output='dense')[:,:,0]
    assert con.indices is None and np.all(matrix[np.triu_indices(5,1)] == 0)
    old = matrix > np.percentile(matrix, 80)
    assert np.count_nonzero(np.tril(old,-1)) == 5  # original failure
    policy = graph_policy()
    out = example('eeg-connectivity', 'connectivity-proportional-graph', conn_matrix=matrix,
        node_names=policy.pop('node_names'), available_edges=policy.pop('available_edges'),
        approved_graph_params=policy)
    audit = out['edge_audit']
    assert audit['n_available_edges'] == 10 and audit['retained_edge_count'] == 2
    assert audit['actual_density_available'] == audit['actual_density_all_possible'] == .2
    assert np.array_equal(out['adj'], out['adj'].T) and not np.diag(out['adj']).any()


@pytest.mark.parametrize('storage', ['lower', 'upper', 'symmetric'])
@pytest.mark.parametrize('tied', [False, True])
def test_equivalent_storage_has_same_unique_edges_and_channel_order_tie_result(storage, tied):
    matrix = lower_matrix()
    if tied: matrix[np.tril_indices(5,-1)] = 1.
    reference_policy = graph_policy();reference_policy['ties'] = 'channel_order'
    expected, _ = graph['proportional_adjacency'](matrix, **reference_policy)
    policy = graph_policy();policy.update(storage=storage, ties='channel_order')
    if storage == 'upper':
        matrix = matrix.T;policy['available_edges'] = policy['available_edges'].T
    elif storage == 'symmetric':
        matrix = matrix + matrix.T
        policy['available_edges'] |= policy['available_edges'].T
    actual, audit = graph['proportional_adjacency'](matrix, **policy)
    np.testing.assert_array_equal(actual, expected)
    assert audit['n_available_edges'] == 10 and audit['retained_edge_count'] == 2


@pytest.mark.parametrize('rounding,k', [('floor',1), ('ceil',2), ('nearest',2)])
def test_requested_fraction_has_explicit_integer_rounding(rounding, k):
    policy = graph_policy();policy.update(density=.15, rounding=rounding)
    _, audit = graph['proportional_adjacency'](lower_matrix(), **policy)
    assert audit['target_edge_count'] == audit['retained_edge_count'] == k


def test_boundary_ties_require_policy_and_include_all_reports_changed_density():
    matrix = lower_matrix();matrix[4,1:] = 0.  # diagonal remains unavailable
    matrix[3,0] = matrix[3,1] = matrix[3,2] = 1.
    policy = graph_policy()
    with pytest.raises(ValueError, match='Boundary scores tie'):
        graph['proportional_adjacency'](matrix, **policy)
    policy['ties'] = 'include_all'
    _, audit = graph['proportional_adjacency'](matrix, **policy)
    assert audit['target_edge_count'] == 2 and audit['retained_edge_count'] == 3
    assert audit['actual_density_available'] == .3


def test_real_zero_edge_remains_available_and_missing_edges_do_not_become_zeros():
    matrix = np.full((4,4), np.nan)
    available = np.zeros((4,4), bool)
    available[1,0] = available[2,0] = True
    matrix[1,0] = 0.;matrix[2,0] = .5
    policy = graph_policy(4);policy.update(available_edges=available, density=1.)
    adj, audit = graph['proportional_adjacency'](matrix, **policy)
    assert adj[1,0] and adj[2,0] and audit['retained_edge_count'] == 2
    assert audit['n_available_edges'] == 2 and audit['n_possible_edges'] == 6
    assert audit['actual_density_available'] == 1.
    assert audit['actual_density_all_possible'] == pytest.approx(1/3)


def test_directed_edges_are_ordered_and_not_mirrored():
    matrix = np.array([[0.,9.,8.], [7.,0.,6.], [5.,4.,0.]])
    policy = graph_policy(3);policy.update(available_edges=~np.eye(3,dtype=bool),
        directed=True, storage='directed', density=1/3)
    adj, audit = graph['proportional_adjacency'](matrix, **policy)
    assert adj[0,1] and adj[0,2] and not adj[1,0]
    assert audit['n_available_edges'] == 6 and audit['retained_edge_count'] == 2


def test_signed_ranking_does_not_silently_take_absolute_weights():
    matrix = np.array([[0.,0.,0.], [-.9,0.,0.], [.5,.4,0.]])
    policy = graph_policy(3);policy['density'] = 1/3
    signed, _ = graph['proportional_adjacency'](matrix, **policy)
    policy['ranking'] = 'magnitude'
    magnitude, _ = graph['proportional_adjacency'](matrix, **policy)
    assert signed[2,0] and not signed[1,0]
    assert magnitude[1,0] and not magnitude[2,0]


@pytest.mark.parametrize('density,k', [(0.,0), (1.,10)])
def test_zero_and_full_density_have_literal_counts(density, k):
    policy = graph_policy();policy['density'] = density
    _, audit = graph['proportional_adjacency'](lower_matrix(), **policy)
    assert audit['retained_edge_count'] == k


def test_graph_rejects_diagonal_unknown_storage_and_complex_edges():
    policy = graph_policy();policy['available_edges'][0,0] = True
    with pytest.raises(ValueError, match='diagonal'):
        graph['proportional_adjacency'](lower_matrix(), **policy)
    policy = graph_policy();policy['storage'] = 'unknown'
    with pytest.raises(ValueError, match='Declare lower'):
        graph['proportional_adjacency'](lower_matrix(), **policy)
    with pytest.raises(ValueError, match='real edge statistic'):
        graph['proportional_adjacency'](lower_matrix().astype(complex), **graph_policy())


def test_documented_binary_graph_metrics_match_known_cycle_values():
    pytest.importorskip('networkx')
    adj = np.zeros((4,4), bool)
    for i,j in [(0,1),(1,2),(2,3),(3,0)]: adj[i,j] = adj[j,i] = True
    out = example('eeg-connectivity','connectivity-binary-graph-metrics',adj=adj,
                  approved_graph_params={'directed':False})
    metrics = out['metrics']
    assert metrics['clustering_coefficient'] == metrics['local_efficiency'] == 0.
    assert metrics['characteristic_path_length'] == pytest.approx(4/3)
    assert metrics['global_efficiency'] == pytest.approx(5/6)
    assert out['metric_status']['characteristic_path_length'] == 'computed'
    json.dumps(dict(metrics=metrics,status=out['metric_status']),allow_nan=False)


def test_documented_sparse_graph_is_saved_without_infinity_or_adding_edges():
    pytest.importorskip('networkx')
    adj, audit = graph['proportional_adjacency'](lower_matrix(), **graph_policy())
    before = adj.copy()
    out = example('eeg-connectivity','connectivity-binary-graph-metrics',adj=adj,
                  approved_graph_params={'directed':False})
    assert out['metrics']['characteristic_path_length'] is None
    assert out['metric_status']['characteristic_path_length'] == 'unavailable_disconnected'
    assert audit['retained_edge_count'] == 2
    np.testing.assert_array_equal(adj,before)
    saved = json.dumps(dict(metrics=out['metrics'],status=out['metric_status']),allow_nan=False)
    assert json.loads(saved)['metrics']['characteristic_path_length'] is None


def phase_data():
    return np.exp(1j*np.random.default_rng(8).normal(size=(12,2,3)))


def label_policy(**overrides):
    return dict(trial_axis=0, participant_ids=['S1']*12, conditions=['A','B'],
                exchangeability_blocks=[0]*6+[1]*6, n_permutations=31,
                seed=18, alternative='two_sided', **overrides)


def labels():
    return np.array(['A','A','A','B','B','B']*2)


def test_itc_discards_positive_amplitude_scale_and_preserves_nontrial_axes():
    coefficients = phase_data()
    amplitudes = np.random.default_rng(12).uniform(.1,20,coefficients.shape)
    expected = np.abs(coefficients.mean(axis=0))
    actual = itc['itc_from_complex'](np.moveaxis(coefficients*amplitudes,0,-1), trial_axis=-1)
    np.testing.assert_allclose(actual, expected)
    assert actual.shape == (2,3)


def test_reordering_trials_cannot_supply_an_absolute_locking_null():
    coefficients = np.exp(1j*np.linspace(-.4,.4,40))
    observed = itc['itc_from_complex'](coefficients, trial_axis=0)
    assert observed == pytest.approx(.972200450374989)
    rng = np.random.default_rng(3)
    for _ in range(25):
        assert itc['itc_from_complex'](rng.permutation(coefficients),trial_axis=0) == pytest.approx(observed)
    with pytest.raises(ValueError, match='leaves ITC unchanged'):
        itc['inference_route'](target='single_condition_locking',null_operation='trial_order')
    with pytest.raises(ValueError, match='not absolute locking'):
        itc['inference_route'](target='single_condition_locking',null_operation='condition_label_exchange')


def test_itc_routes_preserve_unresolved_and_separate_approved_nulls():
    assert itc['inference_route'](target='descriptive', null_operation=None) == 'descriptive'
    assert itc['inference_route'](target='single_condition_locking',null_operation='rayleigh') == 'separate_approved_test'
    with pytest.raises(ValueError, match='explicitly approved null'):
        itc['inference_route'](target='condition_difference',null_operation=None)
    assert itc['inference_route'](target='condition_difference',null_operation='condition_label_exchange') == 'condition_label_exchange'


@pytest.mark.parametrize('alternative', ['two_sided','greater','less'])
def test_streamed_label_test_matches_an_independent_retained_null_reference(alternative):
    coefficients = phase_data()
    policy = label_policy();policy['alternative'] = alternative
    result = itc['condition_label_test'](coefficients, labels(), **policy)
    phases = np.angle(coefficients)
    y = labels();rng = np.random.default_rng(policy['seed'])
    def statistic(current):
        return abs(np.exp(1j*phases[current=='A']).mean(axis=0)) - abs(np.exp(1j*phases[current=='B']).mean(axis=0))
    observed = statistic(y)
    null = []
    for _ in range(policy['n_permutations']):
        shuffled = y.copy()
        for idx in (np.arange(6),np.arange(6,12)):
            shuffled[idx] = rng.permutation(y[idx])
            assert sum(shuffled[idx]=='A') == sum(shuffled[idx]=='B') == 3
        null.append(statistic(shuffled))
    null = np.array(null)
    compare = {'two_sided':lambda:abs(null)>=abs(observed),
               'greater':lambda:null>=observed, 'less':lambda:null<=observed}[alternative]()
    np.testing.assert_allclose(result['observed_difference'],observed)
    np.testing.assert_allclose(result['p_uncorrected'],(compare.sum(axis=0)+1)/32)
    assert result['trial_counts'] == [6,6] and result['participant_id'] == 'S1'
    assert result['multiplicity'] == 'uncorrected'
    assert result['exchangeability_blocks'] == policy['exchangeability_blocks']


def test_documented_itc_example_can_be_descriptive_or_an_explicit_condition_test():
    coefficients = phase_data()
    out = example('eeg-tfr', 'tfr-itc-target', coefficients=coefficients,
        approved_itc_params={'trial_axis':0, 'target':'descriptive', 'null_operation':None})
    assert out['itc_test'] is None
    policy = label_policy();policy.pop('participant_ids');policy.pop('exchangeability_blocks')
    policy.update(target='condition_difference',null_operation='condition_label_exchange')
    out = example('eeg-tfr','tfr-itc-target',coefficients=coefficients,
        trial_conditions=labels(), participant_ids=['S1']*12,
        exchangeability_blocks=[0]*6+[1]*6, approved_itc_params=policy)
    assert out['itc_test']['trial_counts'] == [6,6]
    with pytest.raises(NotImplementedError,match='separate approved test'):
        example('eeg-tfr','tfr-itc-target',coefficients=coefficients,
            approved_itc_params={'trial_axis':0,'target':'single_condition_locking','null_operation':'rayleigh'})


def test_multiple_participants_cannot_be_pooled_by_single_participant_trial_test():
    policy = label_policy();policy['participant_ids'] = ['S1']*6+['S2']*6
    with pytest.raises(ValueError, match='one actual participant'):
        itc['condition_label_test'](phase_data(), labels(), **policy)


def test_no_exchangeable_labels_is_rejected_but_equal_null_statistics_are_valid():
    policy = label_policy();policy['exchangeability_blocks'] = labels()
    with pytest.raises(ValueError, match='cannot change condition membership'):
        itc['condition_label_test'](phase_data(), labels(), **policy)
    result = itc['condition_label_test'](np.ones((12,2),complex), labels(), **label_policy())
    np.testing.assert_array_equal(result['p_uncorrected'], 1.)
    np.testing.assert_array_equal(result['observed_difference'], 0.)


def test_unequal_counts_are_preserved_without_silent_subsampling():
    y = np.array(['A']*4+['B']*8)
    policy = label_policy();policy['exchangeability_blocks'] = [0]*12
    result = itc['condition_label_test'](phase_data(), y, **policy)
    assert result['trial_counts'] == [4,8]


def test_power_and_undefined_zero_phase_are_not_silently_accepted():
    with pytest.raises(ValueError, match='complex coefficients'):
        itc['itc_from_complex'](np.ones((12,2)), trial_axis=0)
    coefficients = phase_data();coefficients[0,0,0] = 0.
    with pytest.raises(ValueError, match='zero-amplitude'):
        itc['itc_from_complex'](coefficients, trial_axis=0)
