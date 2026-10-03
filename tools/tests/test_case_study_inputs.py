"""Preserve original trial identities when repairing the historical examples."""

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from run_fix_audit import make_cycle_data, recover_cycles
from run_full_case_study import trial_metadata


def n100_events():
    # One smiley interrupts the second cycle; the button is not a cycle member.
    codes = np.array([2, 3, 1, 4, 2, 5, 32, 1, 4, 2, 3, 1, 4])
    events = np.column_stack([1000 + 10 * np.arange(len(codes)),
                              np.zeros(len(codes), dtype=int), codes])
    target_events = events[np.isin(codes, [1, 2, 3, 4])]
    return events, target_events


def test_n100_smiley_excludes_only_the_interrupted_cycle_and_accounts_for_trials():
    events, epoch_events = n100_events()
    actual = recover_cycles(events, epoch_events)
    assert actual["n_cycles"] == 3
    assert actual["n_complete_cycles"] == 2
    assert actual["n_incomplete_cycles"] == 1
    assert actual["n_included_target_trials"] == 8
    assert actual["n_excluded_target_trials"] == 3
    assert actual["n_target_events"] == actual["n_cached_target_epochs"] == 11
    assert actual["target_retention_percent"] == 100
    assert [row["cycle_index"] for row in actual["complete_cycles"]] == [0, 2]
    assert [row["raw_sample"] for row in actual["excluded_target_trials"]] == [1040, 1070, 1080]
    assert [row["event_code"] for row in actual["excluded_target_trials"]] == [2, 1, 4]
    assert actual["n_button_events"] == actual["n_smiley_events"] == 1


def test_n100_shuffled_cache_uses_sample_identity_for_balanced_cycle_differences():
    events, epoch_events = n100_events()
    epoch_events = epoch_events[[9, 0, 6, 4, 2, 10, 7, 1, 5, 8, 3]]
    # Values for the excluded cycle are deliberately large. Complete cycles have
    # auditory means -3/-7 and visual means 3/5, irrespective of cache row order.
    by_sample = {1000: -4, 1010: 2, 1020: -2, 1030: 4,
                 1040: 777, 1070: 888, 1080: 999,
                 1090: -8, 1100: 4, 1110: -6, 1120: 6}
    scalar = np.array([by_sample[sample] for sample in epoch_events[:, 0]])
    data = np.broadcast_to(scalar[:, None, None], (11, 3, 5)).copy()
    data += np.array([0, 10, 20])[None, :, None]
    actual = recover_cycles(events, epoch_events)
    auditory, visual = make_cycle_data(data, actual, [2, 0])
    assert auditory.shape == visual.shape == (2, 2, 5)
    np.testing.assert_array_equal(auditory[:, :, 0], [[17, -3], [13, -7]])
    np.testing.assert_array_equal(visual[:, :, 0], [[23, 3], [25, 5]])
    np.testing.assert_array_equal((auditory - visual).mean(axis=(1, 2)), [-6, -12])
    for cycle in actual["complete_cycles"]:
        for row in cycle["stimuli"]:
            assert epoch_events[row["epoch_index"], 0] == row["raw_sample"]


def test_n100_missing_target_epoch_fails_instead_of_silently_reducing_cycles():
    events, epoch_events = n100_events()
    with pytest.raises(ValueError, match=r"missing=\[1000\]"):
        recover_cycles(events, epoch_events[1:])


def flankers_events(response_locked):
    # Two acquisition blocks separated by 7 s at 100 Hz. Each block and side has
    # both compatibility conditions. Response codes are not compatibility codes.
    samples = np.array([1000, 1100, 1200, 1300, 2000, 2100, 2200, 2300])
    stimuli = np.column_stack([samples, np.zeros(8, dtype=int), [3, 4, 5, 6, 6, 5, 4, 3]])
    responses = np.column_stack([samples + 30, np.zeros(8, dtype=int), [2, 1, 1, 2, 1, 2, 2, 1]])
    epoch_samples = samples + 30 if response_locked else samples
    epoch_codes = np.array([201, 201, 202, 202, 202, 202, 201, 201]) if response_locked else np.array([101, 101, 102, 102, 102, 102, 101, 101])
    order = np.array([7, 2, 4, 1, 5, 0, 6, 3])
    epochs = SimpleNamespace(events=np.column_stack([epoch_samples, np.zeros(8, dtype=int), epoch_codes])[order])
    return epochs, stimuli, responses, order


@pytest.mark.parametrize("response_locked", [False, True], ids=["stimulus", "response"])
def test_flankers_shuffled_cache_recovers_original_trial_block_side_and_condition(response_locked):
    epochs, stimuli, responses, order = flankers_events(response_locked)
    actual = trial_metadata(epochs, stimuli, responses, 100.0, response_locked=response_locked)
    np.testing.assert_array_equal(actual["original_stimulus_index"], order)
    np.testing.assert_array_equal(actual["original_stimulus_sample"], stimuli[order, 0])
    np.testing.assert_array_equal(actual["original_stimulus_code"], stimuli[order, 2])
    np.testing.assert_array_equal(actual["block_zero_based"], np.array([0, 0, 0, 0, 1, 1, 1, 1])[order])
    np.testing.assert_array_equal(actual["target_side_right"], np.array([0, 1, 0, 1, 1, 0, 1, 0])[order])
    np.testing.assert_array_equal(actual["strata"], np.array([0, 1, 0, 1, 3, 2, 3, 2])[order])
    np.testing.assert_array_equal(actual["incompatible"], np.array([False, False, True, True, True, True, False, False])[order])
    assert len(actual["counts_per_stratum"]) == 4
    assert all(row["compatible"] == row["incompatible"] == 1
               for row in actual["counts_per_stratum"])


@pytest.mark.parametrize("response_locked", [False, True], ids=["stimulus", "response"])
def test_flankers_unknown_cached_sample_is_not_assigned_by_row_order(response_locked):
    epochs, stimuli, responses, _ = flankers_events(response_locked)
    epochs.events[0, 0] += 1
    with pytest.raises(ValueError, match="match original events|no original response event"):
        trial_metadata(epochs, stimuli, responses, 100.0, response_locked=response_locked)
