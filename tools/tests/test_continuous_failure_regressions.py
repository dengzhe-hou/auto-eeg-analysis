"""Reproduce execution and self-check gaps observed in completed deliveries."""
from pathlib import Path
import runpy
import sys

import mne
import numpy as np
import pytest
from scipy.integrate import trapezoid
from scipy.signal import hilbert

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_analysis_outputs import check_outputs, write_outputs

spectral = runpy.run_path(str(ROOT / "skills/eeg-spectral/scripts/continuous.py"))


@pytest.fixture
def raw():
    data = np.random.default_rng(42).normal(size=(4, 1200)) * 1e-6
    # A transient outside the selected buffer makes the filtering order matter.
    data[0, 95:100] += 8e-6
    return mne.io.RawArray(data, mne.create_info(['F3', 'F4', 'C3', 'C4'], 100., 'eeg'),
                          verbose=False)


def fir():
    return dict(method='fir', fir_design='firwin', fir_window='hamming',
                phase='zero', filter_length='auto', l_trans_bandwidth='auto',
                h_trans_bandwidth='auto', pad='reflect_limited')


def test_swapped_mne_return_is_rejected_before_band_integration(raw):
    psd, freqs = mne.time_frequency.psd_array_welch(
        raw.get_data()[:1], sfreq=100., n_fft=200, n_per_seg=200,
        n_overlap=100, window='hamming', remove_dc=True, average='mean', verbose=False)
    with pytest.raises(ValueError, match='MNE.*returns'):
        spectral['integrated_power'](freqs, psd, band=(8., 13.), upper_closed=True)
    mask = (freqs >= 8.) & (freqs <= 13.)
    np.testing.assert_allclose(
        spectral['integrated_power'](psd, freqs, band=(8., 13.), upper_closed=True),
        trapezoid(psd[:, mask], freqs[mask], axis=-1))
    with pytest.raises(ValueError, match='last axis'):
        spectral['integrated_power'](psd[:, :-1], freqs, band=(8., 13.), upper_closed=True)


def test_sample_stop_and_inclusive_crop_are_distinguished(raw):
    # Transferring Raw.crop's final-sample time to get_data loses one sample.
    expected = raw.get_data(start=100, stop=500)
    cropped = raw.copy().crop(tmin=1., tmax=4.99).get_data()
    np.testing.assert_array_equal(cropped, expected)
    assert raw.get_data(tmin=1., tmax=4.99).shape[-1] == 399
    assert expected.shape[-1] == 400


def test_public_check_checks_required_frequency_coverage(tmp_path):
    plan = {'analysis_channels': ['F3'], 'required_results': {},
            'required_evidence': {'channels': '', 'freqs': '', 'psd': ''},
            'required_frequency_coverage_hz': [.5, 45.]}
    freqs = np.arange(26.)
    write_outputs({'status': 'limited_inference', 'explanation': 'Nyquist is 25 Hz.'},
                  {'channels': ['F3'], 'freqs': freqs, 'psd': np.ones((1, 26)) * 1e-12}, tmp_path)
    check = check_outputs(plan, tmp_path)
    assert not check['passed']
    assert not next(c['passed'] for c in check['checks'] if c['name'] == 'frequency_coverage')
    # A plan asking only for the observable band has no coverage error.
    assert check_outputs({**plan, 'required_frequency_coverage_hz': [.5, 25.]}, tmp_path)['passed']


def _manual_matrix(raw, low, high, metric, *, filter_before_crop=False):
    selected = raw.copy()
    if filter_before_crop:
        selected.filter(low, high, **fir(), verbose=False)
    selected.crop(tmin=1., tmax=4.99)
    if not filter_before_crop:
        selected.filter(low, high, **fir(), verbose=False)
    z = hilbert(selected.get_data(), axis=-1)
    matrix = np.full((4, 4), np.nan)
    for i in range(4):
        for j in range(i + 1, 4):
            if metric == 'plv':
                value = abs(np.mean(np.exp(1j * (np.angle(z[i]) - np.angle(z[j])))))
            else:
                imaginary = np.imag(z[i] * z[j].conj())
                value = abs(np.mean(imaginary)) / np.mean(abs(imaginary))
            matrix[i, j] = matrix[j, i] = value
    if metric == 'plv':
        np.fill_diagonal(matrix, 1.)
    return matrix


@pytest.mark.parametrize('metric', ['plv', 'wpli'])
def test_multiband_source_check_catches_plausible_matrices_with_wrong_order(raw, tmp_path, metric):
    branches = {}
    evidence = {'channels': raw.ch_names}
    result = {'status': 'computed', 'explanation': 'Approved bounded bands.'}
    original_data = raw.get_data().copy()
    for label, bounds in [('alpha', (8., 13.)), ('beta', (13., 30.))]:
        key = metric + '_' + label
        branches[label] = {'metric': metric, 'matrix_key': key, 'operations': [
            {'operation': 'crop', 'parameters': {'start_s': 1., 'stop_s': 5.}},
            {'operation': 'filter', 'parameters': {**fir(), 'l_freq': bounds[0], 'h_freq': bounds[1]}}]}
        evidence[key] = _manual_matrix(raw, *bounds, metric)
    plan = {'analysis_channels': raw.ch_names, 'required_results': {},
            'required_evidence': {key: '' for key in evidence},
            'hilbert_bands': branches,
            'numeric_tolerance': {'connectivity': {'rtol': 1e-10, 'atol': 1e-12}}}
    report = write_outputs(result, evidence, tmp_path)
    correct = check_outputs(plan, tmp_path, raw_input=raw, final_result=report)
    assert correct['passed'], correct
    assert correct['coverage']['hilbert_matrices_recomputed'] == ['alpha', 'beta']
    assert correct['coverage']['report_values_compared']
    evidence[metric + '_alpha'] = _manual_matrix(raw, 8., 13., metric, filter_before_crop=True)
    write_outputs(result, evidence, tmp_path)
    structure_only = check_outputs(plan, tmp_path)
    assert structure_only['passed']
    assert structure_only['coverage']['hilbert_matrices_recomputed'] == []
    wrong = check_outputs(plan, tmp_path, raw_input=raw)
    assert not wrong['passed']
    assert not next(c['passed'] for c in wrong['checks'] if c['name'] == 'approved_hilbert.alpha')
    np.testing.assert_array_equal(raw.get_data(), original_data)


def test_gfp_source_check_catches_swapped_resampling_and_filtering(raw, tmp_path):
    selected = raw.copy().set_eeg_reference('average', projection=False, verbose=False)
    selected.resample(50., verbose=False).filter(1., 20., **fir(), verbose=False)
    selected.crop(tmin=2., tmax=5.98)
    result = {'status': 'computed', 'explanation': 'GFP of the approved buffer.'}
    evidence = {'channels': raw.ch_names, 'gfp': selected.get_data().std(axis=0, ddof=0)}
    plan = {'analysis_channels': raw.ch_names, 'required_results': {},
            'required_evidence': {'channels': '', 'gfp': ''},
            'numeric_tolerance': {'signal': {'rtol': 1e-9, 'atol': 1e-15}},
            'operations': [
                {'operation': 'average_reference', 'parameters': {'projection': False}},
                {'operation': 'resample', 'parameters': {'sfreq': 50.}},
                {'operation': 'filter', 'parameters': {**fir(), 'l_freq': 1., 'h_freq': 20.}},
                {'operation': 'crop', 'parameters': {'start_s': 2., 'stop_s': 6.}}]}
    write_outputs(result, evidence, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)['passed']
    wrong = raw.copy().set_eeg_reference('average', projection=False, verbose=False)
    wrong.filter(1., 20., **fir(), verbose=False).resample(50., verbose=False)
    wrong.crop(tmin=2., tmax=5.98)
    write_outputs(result, {**evidence, 'gfp': wrong.get_data().std(axis=0, ddof=0)}, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    assert not check_outputs(plan, tmp_path, raw_input=raw)['passed']


def test_retry_does_not_hide_an_extra_filter_in_spectral_evidence(raw, tmp_path):
    operation = {'operation': 'filter', 'parameters': {**fir(), 'l_freq': 1., 'h_freq': 30.}}
    plan = {'analysis_channels': raw.ch_names, 'operations': [operation],
            'required_results': {}, 'required_evidence': {'channels': '', 'freqs': '', 'psd': ''},
            'welch': {'segment_seconds': 2., 'window': 'hamming', 'overlap_fraction': .5,
                      'n_fft': None, 'remove_dc': True, 'average': 'mean'},
            'numeric_tolerance': {'psd': {'rtol': 1e-10, 'atol': 1e-28}, 'frequency_atol_hz': 1e-10}}
    delivery = {'status': 'computed', 'explanation': 'A single approved filter.'}
    selected = raw.copy().filter(1., 30., **fir(), verbose=False)
    f, p = spectral['welch_from_plan'](selected.get_data(), 100., plan=plan['welch'])
    write_outputs(delivery, {'channels': raw.ch_names, 'freqs': f, 'psd': p}, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)['passed']
    # A later exception in the same cell would not undo this in-place mutation.
    selected.filter(1., 30., **fir(), verbose=False)
    f, p = spectral['welch_from_plan'](selected.get_data(), 100., plan=plan['welch'])
    write_outputs(delivery, {'channels': raw.ch_names, 'freqs': f, 'psd': p}, tmp_path)
    assert not check_outputs(plan, tmp_path, raw_input=raw)['passed']
