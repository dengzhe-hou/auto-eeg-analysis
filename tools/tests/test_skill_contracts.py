"""Observed coverage/handoff/report errors and the complete multiband example."""
from pathlib import Path
import json
import runpy
import sys
import mne
import numpy as np
import pytest
from scipy.integrate import trapezoid
from scipy.signal import hilbert

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_analysis_outputs import check_outputs, write_outputs
from load_skill import load_skill_packet
spectral = runpy.run_path(str(ROOT / 'skills/eeg-spectral/scripts/continuous.py'))
prep = runpy.run_path(str(ROOT / 'skills/eeg-preprocess/scripts/continuous.py'))
conn = runpy.run_path(str(ROOT / 'skills/eeg-connectivity/scripts/continuous.py'))


def test_partial_frequency_support_cannot_be_reported_as_a_complete_band():
    freqs = np.arange(26.)
    power = np.ones((2, len(freqs)))
    for band in ([20, 40], [-1, 5]):
        with pytest.raises(ValueError, match='fully covered'):
            spectral['integrated_power'](power, freqs, band=band, upper_closed=True)
        with pytest.raises(ValueError, match='fully covered'):
            spectral['maximum_bin_peak'](power, freqs, band=band)
    for closed in (True, False):
        mask = (freqs >= 8.2) & ((freqs <= 13.) if closed else (freqs < 13.))
        actual = spectral['integrated_power'](power, freqs, band=[8.2, 13.], upper_closed=closed)
        np.testing.assert_allclose(actual, trapezoid(power[:, mask], freqs[mask], axis=-1))


@pytest.mark.parametrize('remove_dc', [True, False])
@pytest.mark.parametrize('average', ['mean', 'median'])
def test_existing_and_canonical_welch_forms_are_numerically_identical(remove_dc, average):
    data = np.random.default_rng(901).normal(size=(2, 1200)) * 1e-6
    canonical = dict(segment_seconds=2., window='hamming', overlap_fraction=.25,
                     n_fft=None, remove_dc=remove_dc, average=average)
    retained = {k: v for k, v in canonical.items() if k != 'remove_dc'}
    retained.update(n_fft='n_per_seg', detrend='constant' if remove_dc else False)
    f1, p1 = spectral['welch_from_plan'](data, 200., plan=canonical)
    f2, p2 = spectral['welch_from_plan'](data, 200., plan=retained)
    np.testing.assert_array_equal(f1, f2)
    np.testing.assert_array_equal(p1, p2)
    with pytest.raises(ValueError, match='Conflicting'):
        spectral['resolved_welch_settings']({**canonical, 'detrend': False if remove_dc else 'constant'})
    with pytest.raises(KeyError, match='average'):
        spectral['resolved_welch_settings']({k: v for k, v in canonical.items() if k != 'average'})


def test_full_study_example_and_bounded_helper_share_the_same_settings():
    doc = (ROOT / 'skills/eeg-spectral/references/procedure.md').read_text(encoding="utf-8-sig")
    example = json.loads(doc.split('```json\n', 1)[1].split('```', 1)[0])
    settings = spectral['resolved_welch_settings'](example['welch'])
    data = np.random.default_rng(3).normal(size=(2, 1000)) * 1e-6
    raw = mne.io.RawArray(data, mne.create_info(['F3', 'F4'], 200., 'eeg'), verbose=False)
    kw = spectral['welch_parameters'](200., raw.n_times, **settings)
    full = raw.compute_psd(method='welch', fmin=0., fmax=100., **kw, verbose=False)
    freqs, bounded = spectral['welch_from_plan'](data, 200., plan=example['welch'])
    np.testing.assert_array_equal(full.freqs, freqs)
    np.testing.assert_allclose(full.get_data(), bounded, rtol=1e-12, atol=1e-28)


def connection_fixture():
    names = ['F3', 'F4', 'Pz']
    matrix = np.array([[1., .2, .7], [.2, 1., .4], [.7, .4, 1.]])
    summary = conn['summarize_undirected_connectivity'](matrix, names, top_k=3)
    plan = {'analysis_channels': names,
        'required_results': {'global_mean_plv': '', 'top3_plv_pairs': ''},
        'required_evidence': {'channels': '', 'plv': ''},
        'connectivity_summaries': [{'matrix_key': 'plv', 'pair_scope': 'undirected_distinct',
            'ranking': 'value_desc_label_asc', 'top_k': 3,
            'mean_result': 'global_mean_plv', 'pairs_result': 'top3_plv_pairs'}],
        'numeric_tolerance': {'result': {'rtol': 1e-10, 'atol': 1e-12}}}
    result = {'status': 'computed', 'explanation': 'Actual saved matrix summary.',
        'global_mean_plv': summary['global_mean'], 'top3_plv_pairs': summary['top_pairs']}
    return plan, result, {'channels': names, 'plv': matrix}


def test_public_check_rejects_wrong_mean_and_rank_but_accepts_equivalent_pairs(tmp_path):
    plan, result, evidence = connection_fixture()
    final = write_outputs(result, evidence, tmp_path)
    passed = check_outputs(plan, tmp_path, final_result=final)
    assert passed['passed'] and passed['coverage']['connectivity_summary_recomputed']
    equivalent = [{'channel_pair': list(reversed(pair)), 'plv': float(evidence['plv'][
        plan['analysis_channels'].index(pair[0]), plan['analysis_channels'].index(pair[1])])}
        for pair in result['top3_plv_pairs']]
    write_outputs({**result, 'top3_plv_pairs': equivalent}, evidence, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    for change, expected in [({'global_mean_plv': .99}, 'derived.global_mean_plv'),
            ({'top3_plv_pairs': list(reversed(result['top3_plv_pairs']))}, 'derived.top3_plv_pairs')]:
        final = write_outputs({**result, **change}, evidence, tmp_path)
        check = check_outputs(plan, tmp_path, final_result=final)
        assert not check['passed']
        assert expected in {row['name'] for row in check['checks'] if not row['passed']}


def test_public_gfp_check_detects_wrong_peak_and_absolute_time_coordinates(tmp_path):
    gfp = np.zeros(3000)
    gfp[[400, 401, 1400, 2400]] = 2e-6  # First-maximum tie in the first window.
    settings = dict(sfreq_hz=100., time_origin_s=30.,
                    windows_s=[[30., 40.], [40., 50.], [50., 60.]], tie_rule='first')
    computed = prep['gfp_peak_times'](gfp, **settings)
    fields = ['peak1', 'peak2', 'peak3']
    plan = {'analysis_channels': ['F3', 'F4'], 'required_results': dict.fromkeys(fields, ''),
        'required_evidence': {'channels': '', 'gfp': '', 'gfp_times': ''},
        'gfp_peaks': {**settings, 'result_fields': fields},
        'numeric_tolerance': {'time_atol_s': 1e-9}}
    result = {'status': 'computed', 'explanation': 'Absolute GFP peaks.',
              **dict(zip(fields, computed['peak_times_s']))}
    evidence = {'channels': ['F3', 'F4'], 'gfp': gfp, 'gfp_times': computed['times_s']}
    write_outputs(result, evidence, tmp_path)
    check = check_outputs(plan, tmp_path)
    assert check['passed'] and check['coverage']['gfp_peaks_recomputed']
    assert result['peak1'] == 34.
    write_outputs({**result, 'peak1': 34.01}, evidence, tmp_path)
    assert not check_outputs(plan, tmp_path)['passed']
    write_outputs(result, {**evidence, 'gfp_times': computed['times_s'] - 30.}, tmp_path)
    assert not check_outputs(plan, tmp_path)['passed']


@pytest.mark.parametrize('metric', ['plv', 'wpli'])
def test_complete_multiband_example_preserves_independent_inputs_and_checks_summaries(tmp_path, metric):
    sfreq = 100.
    names = ['F3', 'F4', 'P3', 'P4']
    data = np.random.default_rng(81).normal(size=(4, 2000)) * 1e-6
    original = mne.io.RawArray(data, mne.create_info(names, sfreq, 'eeg'), verbose=False)
    source = tmp_path / 'input_raw.fif'
    original.save(source, overwrite=True, verbose=False)
    # Match the recorded single-precision input used by the actual example.
    with mne.io.read_raw_fif(source, preload=False, verbose=False) as saved:
        source_data = saved.get_data()
    pairs = [['F3', 'F4'], ['P3', 'P4']]
    plan = {'input_path': str(source), 'analysis_channels': names,
        'required_results': {}, 'required_evidence': {'channels': ''},
        'hilbert_bands': {}, 'connectivity_summaries': [], 'hemisphere_contrasts': [],
        'numeric_tolerance': {'result': {'rtol': 1e-10, 'atol': 1e-12},
                              'connectivity': {'rtol': 1e-10, 'atol': 1e-12}}}
    filters = {}
    for label, band in [('alpha', [8., 13.]), ('beta', [13., 30.])]:
        matrix_key = f'{metric}_{label}'
        parameters = dict(l_freq=band[0], h_freq=band[1], method='fir',
                          fir_design='firwin', fir_window='hamming', phase='zero')
        filters[label] = parameters
        plan['hilbert_bands'][label] = {'metric': metric, 'matrix_key': matrix_key,
            'segment_key': f'segment_{label}', 'operations': [
                {'operation': 'filter', 'parameters': parameters},
                {'operation': 'crop', 'parameters': {'start_s': 2., 'stop_s': 8.}}]}
        plan['required_evidence'][matrix_key] = ''
        plan['connectivity_summaries'].append({'matrix_key': matrix_key,
            'pair_scope': 'undirected_distinct', 'ranking': 'value_desc_label_asc',
            'top_k': 3, 'mean_result': f'{label}_mean', 'pairs_result': f'{label}_pairs'})
        plan['hemisphere_contrasts'].append({'matrix_key': matrix_key,
            'homologous_pairs': pairs, 'result_field': f'{label}_difference'})
    packet, _ = load_skill_packet(ROOT, 'eeg-connectivity',
        section='Complete multiband Hilbert calculation')
    code = packet.split('```python\n', 1)[1].split('```', 1)[0]
    out = tmp_path / 'output'
    namespace = {'AEA_ROOT': ROOT, 'approved_public_plan': plan, 'output_directory': out}
    exec(compile(code, 'continuous.md multiband example', 'exec'), namespace)
    check = json.loads((out / 'SELF_CHECK.json').read_text(encoding="utf-8-sig"))
    assert check['passed'] and check['coverage']['connectivity_summary_recomputed']
    assert check['coverage']['hemisphere_contrast_recomputed']
    assert not check['coverage']['approved_processing_recomputed']
    assert check['coverage']['hilbert_matrices_recomputed'] == ['alpha', 'beta']
    result = json.loads((out / 'result.json').read_text(encoding="utf-8-sig"))
    with np.load(out / 'analysis_evidence.npz') as arrays:
        for label in ['alpha', 'beta']:
            expected_segment = mne.filter.filter_data(source_data.copy(), sfreq,
                **filters[label], verbose=False)[:, 200:800]
            np.testing.assert_allclose(arrays[f'segment_{label}'], expected_segment, rtol=1e-12, atol=1e-24)
            analytic = hilbert(expected_segment, axis=-1)
            # Direct pair formula, independently of the matrix helper.
            if metric == 'plv':
                expected = abs(np.mean(np.exp(1j * (np.angle(analytic[0]) - np.angle(analytic[1])))))
            else:
                imag = np.imag(analytic[0] * analytic[1].conj())
                expected = abs(imag.mean()) / np.abs(imag).mean()
            np.testing.assert_allclose(arrays[f'{metric}_{label}'][0, 1], expected, rtol=1e-12, atol=1e-14)
        evidence = {key: arrays[key] for key in arrays.files}
    write_outputs({**result, 'alpha_difference': -result['alpha_difference'] + 1.}, evidence, out)
    assert not check_outputs(plan, out)['passed']
    with mne.io.read_raw_fif(source, preload=False, verbose=False) as after:
        np.testing.assert_array_equal(after.get_data(), source_data)
        missing = {**plan, 'numeric_tolerance': {'result': plan['numeric_tolerance']['result']}}
        with pytest.raises(ValueError, match='numeric_tolerance.connectivity'):
            check_outputs(missing, out, raw_input=after)
