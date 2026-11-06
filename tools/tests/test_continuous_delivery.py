"""Regression checks for observed processing, unit, band and delivery failures."""
from pathlib import Path
import json
import runpy
import sys
import numpy as np
import pytest
import mne
from scipy.integrate import trapezoid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_analysis_outputs import check_outputs, write_outputs

prep = runpy.run_path(str(ROOT / "skills/eeg-preprocess/scripts/continuous.py"))
spectral = runpy.run_path(str(ROOT / "skills/eeg-spectral/scripts/continuous.py"))


@pytest.fixture
def raw():
    x = np.random.default_rng(17).normal(size=(3, 1600)) * 1e-6
    return mne.io.RawArray(x, mne.create_info(['F3', 'F4', 'Pz'], 200., 'eeg'), verbose=False)


def public_plan():
    return {'analysis_channels': ['F3', 'F4'], 'operations': [],
            'required_results': {'status': '', 'explanation': ''},
            'required_evidence': {'channels': '', 'freqs': '', 'psd': ''},
            'welch': {'segment_seconds': 3., 'window': 'hamming',
                      'overlap_fraction': .25, 'n_fft': 1024,
                      'detrend': 'constant', 'average': 'mean'},
            'numeric_tolerance': {'psd': {'rtol': 1e-10, 'atol': 1e-28},
                                  'signal': {'rtol': 1e-10, 'atol': 1e-18},
                                  'frequency_atol_hz': 1e-10}}


def test_explicit_empty_operations_preserve_input_and_do_not_authorize_fir(raw):
    original = raw.get_data().copy()
    selected = prep['prepare_continuous'](raw, analysis_channels=['F4', 'F3'], operations=[])
    np.testing.assert_array_equal(selected.get_data(), original[[1, 0]])
    np.testing.assert_array_equal(raw.get_data(), original)
    assert selected.ch_names == ['F4', 'F3']


def test_units_from_mne_and_external_arrays_are_converted_once(raw):
    np.testing.assert_array_equal(prep['data_in_volts'](raw), raw.get_data())
    np.testing.assert_allclose(prep['array_in_volts'](raw.get_data() * 1e6, input_unit='uV'), raw.get_data())
    with pytest.raises(ValueError, match='documented'):
        prep['array_in_volts'](raw.get_data(), input_unit='unknown')


def test_public_recompute_detects_unrequested_filter_and_double_scaling(raw, tmp_path):
    plan = public_plan()
    # An available configuration alone must not turn into a processing step.
    plan['fir'] = {'l_freq': 8., 'h_freq': 13.}
    selected = prep['prepare_continuous'](raw, analysis_channels=plan['analysis_channels'], operations=[])
    f, p = spectral['welch_from_plan'](prep['data_in_volts'](selected), 200., plan=plan['welch'])
    result = {'status': 'computed', 'explanation': 'Approved interval and channels.'}
    arrays = {'channels': selected.ch_names, 'freqs': f, 'psd': p}
    report = write_outputs(result, arrays, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw, final_result=report)['passed']
    converted = {**arrays, 'psd': p * 1e12, 'psd_unit': 'uV^2/Hz',
                 'processed': selected.get_data() * 1e6, 'signal_unit': 'uV',
                 'variance': selected.get_data().var(axis=-1) * 1e12, 'variance_unit': 'uV^2'}
    write_outputs(result, converted, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)['passed']
    write_outputs(result, {**arrays, 'psd': p * 1e-12}, tmp_path)
    wrong_units = check_outputs(plan, tmp_path, raw_input=raw)
    assert not wrong_units['passed']
    assert not next(c['passed'] for c in wrong_units['checks'] if c['name'] == 'approved_psd.values')
    filtered = mne.filter.filter_data(selected.get_data(), 200., 8., 13., verbose=False)
    f2, p2 = spectral['welch_from_plan'](filtered, 200., plan=plan['welch'])
    write_outputs(result, {**arrays, 'freqs': f2, 'psd': p2}, tmp_path)
    assert not check_outputs(plan, tmp_path, raw_input=raw)['passed']
    missing_operations = {k: v for k, v in plan.items() if k != 'operations'}
    with pytest.raises(ValueError, match='approved ordered operations'):
        check_outputs(missing_operations, tmp_path, raw_input=raw)


def test_frequency_branches_do_not_mutate_their_common_input(raw):
    original = raw.get_data().copy()
    common = {'method': 'fir', 'fir_design': 'firwin', 'fir_window': 'hamming',
              'phase': 'zero', 'filter_length': 'auto', 'l_trans_bandwidth': 'auto',
              'h_trans_bandwidth': 'auto', 'pad': 'reflect_limited'}
    for low, high in [(8., 13.), (13., 30.)]:
        branch = prep['prepare_continuous'](raw, analysis_channels=raw.ch_names,
            operations=[{'operation': 'filter', 'parameters': {**common, 'l_freq': low, 'h_freq': high}}])
        expected = mne.filter.filter_data(original, 200., low, high, **common, verbose=False)
        np.testing.assert_allclose(branch.get_data(), expected, rtol=1e-12, atol=1e-24)
        np.testing.assert_array_equal(raw.get_data(), original)


def test_crop_and_resample_use_approved_interval_and_actual_subset(raw):
    out = prep['prepare_continuous'](raw, analysis_channels=['F4'], operations=[
        {'operation': 'crop', 'parameters': {'start_s': 1., 'stop_s': 3.}},
        {'operation': 'resample', 'parameters': {'sfreq': 100., 'npad': 'auto'}}])
    assert out.ch_names == ['F4'] and out.n_times == 200 and out.info['sfreq'] == 100.
    assert raw.n_times == 1600


def test_personalized_power_distinguishes_shared_and_per_channel_centers(tmp_path):
    f = np.arange(0, 20.25, .25)
    p = np.array([1 + 8 * np.exp(-(f - 9.) ** 2), 2 + 5 * np.exp(-(f - 13.) ** 2)]) * 1e-12
    settings = {'search_band': [8., 13.], 'offsets': [-2., 2.], 'total_band': [.5, 19.],
                'center_mode': 'mean_peak', 'upper_closed': True, 'total_upper_closed': True}
    common = spectral['personalized_alpha_power'](p, f, **settings)
    separate = spectral['personalized_alpha_power'](p, f, **{**settings, 'center_mode': 'per_channel_peak'})
    np.testing.assert_array_equal(common['band_centers_hz'], [11., 11.])
    band = (f >= 9.) & (f <= 13.); total = (f >= .5) & (f <= 19.)
    expected = trapezoid(p[:, band], f[band], axis=-1) / trapezoid(p[:, total], f[total], axis=-1)
    np.testing.assert_allclose(common['relative_power_per_channel'], expected)
    assert not np.allclose(common['relative_power_per_channel'], separate['relative_power_per_channel'])
    plan = {'analysis_channels': ['F3', 'F4'], 'required_results': {'peak': '', 'percent': ''},
            'required_evidence': {'channels': '', 'freqs': '', 'psd': ''},
            'personalized_alpha': {**settings, 'mean_peak_result': 'peak', 'mean_percent_result': 'percent'},
            'numeric_tolerance': {'result': {'rtol': 1e-12, 'atol': 1e-15}}}
    result = {'status': 'computed', 'explanation': 'Common band centered on the mean peak.',
              'peak': common['mean_peak_hz'], 'percent': 100 * expected.mean()}
    evidence = {'channels': ['F3', 'F4'], 'freqs': f, 'psd': p}
    write_outputs(result, evidence, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    write_outputs({**result, 'percent': expected.mean(), 'percent_unit': 'fraction'}, evidence, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    write_outputs({**result, 'percent': 100 * separate['relative_power_per_channel'].mean()}, evidence, tmp_path)
    assert not check_outputs(plan, tmp_path)['passed']


def test_saved_and_final_values_use_one_computation_and_reject_mismatch(tmp_path):
    result = {'status': 'computed', 'explanation': 'Measured data.', 'amplitude': np.float64(1.234567891)}
    report = write_outputs(result, {'channels': np.array(['F3'], dtype=object)}, tmp_path)
    plan = {'analysis_channels': ['F3'], 'required_results': {'amplitude': ''},
            'required_evidence': {'channels': ''}}
    assert check_outputs(plan, tmp_path, final_result=report)['passed']
    assert not check_outputs(plan, tmp_path, final_result={**report, 'amplitude': 1.23})['passed']
    with np.load(tmp_path / 'analysis_evidence.npz', allow_pickle=False) as archive:
        assert archive['channels'].tolist() == ['F3']
    with pytest.raises(ValueError, match='not objects'):
        write_outputs(result, {'psd': np.array([{'invalid': 1}], dtype=object)}, tmp_path)


def test_edf_export_and_self_check_reopen_actual_subset(raw, tmp_path):
    pytest.importorskip('edfio')
    destination = tmp_path / 'file_check' / 'requested.edf'
    # The helper must select two channels even when given all three scalp channels.
    prep['export_checked_edf'](raw, destination, analysis_channels=['F3', 'F4'],
        sfreq=200., n_samples=1600)
    plan = {'analysis_channels': ['F3', 'F4'], 'required_results': {}, 'required_evidence': {},
            'output_filename': 'requested.edf', 'output_sfreq_hz': 200., 'output_n_samples': 1600}
    write_outputs({'status': 'computed', 'explanation': 'The selected pair was exported.'}, {}, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    raw.export(destination, fmt='edf', overwrite=True, verbose=False)
    assert not check_outputs(plan, tmp_path)['passed']
    with pytest.raises(ValueError, match='sample count'):
        prep['export_checked_edf'](raw, destination, analysis_channels=['F3'], sfreq=200., n_samples=1599)
