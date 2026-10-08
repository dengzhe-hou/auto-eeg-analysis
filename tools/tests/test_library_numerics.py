"""Numerical references and known-input controls, beyond API smoke tests."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))
import library_numerics as numerics


def test_morlet_power_itc_and_baseline_numerics():
    numerics.check_tfr()


def test_debiased_wpli_against_direct_dft():
    pytest.importorskip("mne_connectivity")
    numerics.check_connectivity()


def test_extended_infomax_known_source_recovery():
    numerics.check_ica()


def test_fixed_source_inverse_against_ridge_formula():
    numerics.check_source()


def test_grouped_decoding_signal_and_null():
    pytest.importorskip("sklearn")
    numerics.check_decoding()


def test_permutation_entropy_against_ordinal_counts():
    pytest.importorskip("antropy")
    numerics.check_complexity()


def test_microstate_transitions_against_known_sequence():
    pytest.importorskip("pycrostates")
    numerics.check_microstate()


def test_bids_roundtrip_units_channels_and_events():
    pytest.importorskip("mne_bids")
    pytest.importorskip("pybv")
    numerics.check_bids()


@pytest.fixture(scope="module")
def amplitude_qc():
    return numerics.check_qc()


def test_amplitude_qc_injected_faults(amplitude_qc):
    assert amplitude_qc["mechanism_checks_passed"]


def test_amplitude_qc_clean_sinusoid(amplitude_qc):
    assert amplitude_qc["sine_negative_control_passed"]
    assert len(amplitude_qc["normal_waveform_controls"]) == 27


def test_amplitude_qc_low_amplitude_remains_warning(amplitude_qc):
    result = amplitude_qc["low_amplitude_control"]
    assert len(result["low_amplitude_warnings"]) == 100
    assert not result["bad_channel_candidates"]
