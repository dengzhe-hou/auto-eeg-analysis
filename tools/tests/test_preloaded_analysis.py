"""Numerical invariants and real request formatting for preloaded procedures."""
from pathlib import Path
import json
import runpy
import sys
import numpy as np
import pytest
from scipy import signal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_skill_packet import prepare_packet
from load_skill import check_packet_in_request
from check_analysis_outputs import check_outputs

spectral = runpy.run_path(str(ROOT / "skills/eeg-spectral/scripts/continuous.py"))
connectivity = runpy.run_path(str(ROOT / "skills/eeg-connectivity/scripts/continuous.py"))


def test_welch_matches_scipy_with_nondefault_explicit_settings():
    data = np.random.default_rng(61).normal(size=(2, 1600)) * 1e-6
    freq, power = spectral["welch_psd"](data, 200., segment_seconds=3.,
        window="hamming", overlap_fraction=.25, n_fft=1024, remove_dc=True, average="mean")
    expected_freq, expected = signal.welch(data, fs=200., window="hamming",
        nperseg=600, noverlap=150, nfft=1024, detrend="constant", axis=-1)
    np.testing.assert_array_equal(freq, expected_freq)
    np.testing.assert_allclose(power, expected, rtol=1e-12, atol=1e-28)
    f2, p2 = spectral["welch_psd"](data[:1] * 1e6, 200., segment_seconds=3.,
        window="hamming", overlap_fraction=.25, n_fft=1024, remove_dc=True, average="mean")
    assert p2.shape == (1, len(f2))
    np.testing.assert_allclose(p2, power[:1] * 1e12, rtol=1e-12)


def test_integrated_ratios_are_computed_per_channel():
    f = np.arange(6, dtype=float)
    power = np.array([[1, 1, 3, 3, 1, 1], [10, 10, 10, 10, 10, 10]], dtype=float)
    ratios = spectral["channel_relative_power"](power, f, band=[2, 3], total_band=[0, 5],
        upper_closed=True, total_upper_closed=True)
    np.testing.assert_allclose(ratios, [3/9, 10/50])
    assert not np.isclose(ratios.mean(), (3+10)/(9+50))


def test_peak_is_per_channel_and_uses_approved_search_band():
    f = np.arange(7, 15, dtype=float)
    power = np.zeros((2, len(f))); power[0, 3] = 3; power[1, 5] = 2
    np.testing.assert_array_equal(spectral["maximum_bin_peak"](power, f, band=[8, 13]), [10, 12])


def test_wpli_retains_amplitude_weights_and_unit_invariance():
    z = np.array([[1, 2, 1, 2], [1+1j, 1-1j, 1+1j, 1-1j]])
    w = connectivity["ordinary_wpli_from_analytic"](z)
    assert np.isnan(w.diagonal()).all()
    np.testing.assert_allclose(w[0, 1], 1/3, rtol=1e-14)
    np.testing.assert_allclose(w, connectivity["ordinary_wpli_from_analytic"](z * 1e-6), equal_nan=True)
    stripped = connectivity["ordinary_wpli_from_analytic"](np.exp(1j*np.angle(z)))
    assert not np.isclose(w[0, 1], stripped[0, 1])
    assert np.isnan(connectivity["ordinary_wpli_from_analytic"](np.ones((2, 5), dtype=complex))).all()


def test_plv_and_hemisphere_means_exclude_self_and_cross_side_edges():
    z = np.array([[1, 1, 1, 1], [1, -1, 1, -1]], dtype=complex)
    np.testing.assert_allclose(connectivity["plv_from_analytic"](z), np.eye(2), atol=1e-15)
    matrix = np.full((4, 4), 99.); matrix[0, 2] = matrix[2, 0] = .2; matrix[1, 3] = matrix[3, 1] = .8
    difference = connectivity["hemisphere_difference"](matrix, ['L1', 'R1', 'L2', 'R2'],
        homologous_pairs=[['L1', 'R1'], ['L2', 'R2']])
    assert np.isclose(difference, -.6)


def test_complete_packet_contains_selected_procedure_and_callable_source():
    packet, receipt = prepare_packet(ROOT, [{"skill": "eeg-spectral",
        "section": "Welch and band power", "scripts": ["scripts/continuous.py"]}])
    assert "def welch_psd" in packet and len(receipt['selections'][0]['sources']) == 2
    check_packet_in_request({'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': packet}]}]}, packet)
    with pytest.raises(ValueError, match='absent or truncated'):
        check_packet_in_request({'messages': [{'role': 'user', 'content': packet[:3000]}]}, packet)


def test_public_self_check_catches_wrong_channel_axis_and_variance(tmp_path):
    plan = {'analysis_channels': ['F3', 'F4'], 'required_results': {'status': '', 'explanation': ''},
            'required_evidence': {'channels': '', 'freqs': '', 'psd': '', 'processed': '', 'variance': ''}}
    (tmp_path/'result.json').write_text(json.dumps({'status': 'computed', 'explanation': 'Measured approved data.'}), encoding="utf-8")
    arrays = {'channels': np.array(['F3', 'F4']), 'freqs': np.arange(3.), 'psd': np.ones((2, 3)),
              'processed': np.array([[1., 2., 3.], [2., 4., 6.]]), 'variance': np.array([2/3, 8/3])}
    np.savez(tmp_path/'analysis_evidence.npz', **arrays)
    assert check_outputs(plan, tmp_path)['passed']
    np.savez(tmp_path/'analysis_evidence.npz', **{**arrays, 'psd': np.ones(3)})
    assert not check_outputs(plan, tmp_path)['passed']
    np.savez(tmp_path/'analysis_evidence.npz', **{**arrays, 'channels': np.array(['F4', 'F3'])})
    assert not check_outputs(plan, tmp_path)['passed']
    np.savez(tmp_path/'analysis_evidence.npz', **{**arrays, 'variance': arrays['variance']*2})
    assert not check_outputs(plan, tmp_path)['passed']
