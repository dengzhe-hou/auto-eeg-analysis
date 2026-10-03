"""Numerical references and known-input controls, beyond API smoke tests.

The QC sine control is a documented, unresolved failure of the released flat
threshold. It is xfailed explicitly, not converted into a passing QC claim.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
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


@pytest.mark.xfail(strict=True, reason="Released adjacent-difference flat threshold flags artifact-free 10 Hz sine control; owner decision pending")
def test_amplitude_qc_clean_sinusoid(amplitude_qc):
    assert amplitude_qc["sine_negative_control_passed"], {
        "bad_channels": amplitude_qc["sine_bad_channels"],
        "annotation_count": amplitude_qc["sine_annotation_count"],
    }
