"""Known-input checks for diagnostic segments, thresholds and non-mutation."""
import json
from pathlib import Path
import sys

import mne
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qc_amplitude import amplitude_qc


def make_raw(values, sfreq, names=None):
    values = np.atleast_2d(values)
    names = names or [f"EEG{i}" for i in range(len(values))]
    return mne.io.RawArray(values, mne.create_info(names, sfreq, "eeg"),
                          first_samp=123, verbose=False)


@pytest.mark.parametrize("equal_intervals", [4, 5, 6])
def test_constant_duration_boundary(equal_intervals):
    values = np.arange(750) * 1e-6
    start = 100
    values[start:start + equal_intervals + 1] = 5e-6
    result = amplitude_qc(make_raw(values, 250.))
    expected = [] if equal_intervals < 5 else [
        {"channel": "EEG0", "onset": start / 250., "duration": equal_intervals / 250.}]
    assert result["constant_segments"] == expected
    assert not result["bad_channel_candidates"]


@pytest.mark.parametrize("jump_intervals", [4, 5, 6])
def test_rapid_change_duration_independent_of_constant_duration(jump_intervals):
    sfreq = 1000.
    values = 20e-6 * np.sin(2 * np.pi * 10 * np.arange(1000) / sfreq + .3)
    start = 100
    length = jump_intervals - 1
    values[start:start + length] = np.where(np.arange(length) % 2, -300e-6, 300e-6)
    result = amplitude_qc(make_raw(values, sfreq), constant_min_duration=.2)
    expected = [] if jump_intervals < 5 else [
        {"channel": "EEG0", "onset": (start - 1) / sfreq, "duration": jump_intervals / sfreq}]
    assert result["jump_segments"] == expected
    assert not result["constant_segments"]
    assert not result["bad_channel_candidates"]


def test_persistent_faults_have_distinct_reasons():
    values = np.array([np.zeros(1001), np.tile([-300e-6, 300e-6], 501)[:1001]])
    result = amplitude_qc(make_raw(values, 250., ["constant", "jumping"]))
    # The skill writes the complete helper result with json.dumps; MNE n_times
    # and NumPy run indices otherwise leak non-serializable scalar types.
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert result["bad_channel_candidates"] == ["constant", "jumping"]
    assert result["per_channel"]["constant"] == {
        "constant_fraction": 1., "jump_fraction": 0., "candidate_reasons": ["constant"]}
    assert result["per_channel"]["jumping"] == {
        "constant_fraction": 0., "jump_fraction": 1., "candidate_reasons": ["rapid_change"]}


def test_low_amplitude_windows_and_tail_do_not_make_bad_candidates():
    # Two complete 25-sample windows have known ranges of .4 and 2 microvolts;
    # the final seven samples do not form a complete diagnostic window.
    low = np.linspace(0., .4e-6, 25)
    normal = np.linspace(-1e-6, 1e-6, 25)
    values = np.r_[low, normal, np.linspace(0., .1e-6, 7)]
    result = amplitude_qc(make_raw(values, 250.))
    assert result["low_amplitude_warnings"] == [
        {"channel": "EEG0", "onset": 0., "duration": .1, "peak_to_peak": .4e-6}]
    assert result["ignored_tail_samples"] == 7
    assert not result["bad_channel_candidates"]
    assert not result["constant_segments"] and not result["jump_segments"]


def test_diagnostics_preserve_samples_annotations_and_existing_bads():
    values = np.array([np.zeros(500), 20e-6 * np.sin(2 * np.pi * 10 * np.arange(500) / 250.)])
    raw = make_raw(values, 250., ["flat", "normal"])
    raw.info["bads"] = ["normal"]
    raw.set_annotations(mne.Annotations([.2], [.1], ["existing_marker"]))
    annotations = raw.annotations.copy()
    original_first_samp = raw.first_samp
    result = amplitude_qc(raw)
    np.testing.assert_array_equal(raw.get_data(), values)
    np.testing.assert_array_equal(raw.annotations.onset, annotations.onset)
    np.testing.assert_array_equal(raw.annotations.duration, annotations.duration)
    np.testing.assert_array_equal(raw.annotations.description, annotations.description)
    assert raw.annotations.orig_time == annotations.orig_time
    assert raw.info["bads"] == ["normal"]
    assert raw.first_samp == original_first_samp
    assert set(result["per_channel"]) == {"flat", "normal"}
    assert result["bad_channel_candidates"] == ["flat"]
    assert result["constant_segments"][0]["onset"] == 0.
