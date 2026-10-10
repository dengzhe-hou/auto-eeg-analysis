"""Check real recipe failure modes: prime leakage and ROI inference-domain drift."""
from pathlib import Path
import sys

import mne
import numpy as np
import pytest

pd = pytest.importorskip("pandas")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from run_recipe_case import (RELATED, ROI, UNRELATED, roi_adjacency, target_events,
                             validate_channels, validate_trial_counts, display_path,
                             prepare_run_directory, write_json, find_subject_inputs)


@pytest.mark.parametrize("session", [None, "ses-N400"])
def test_n400_inputs_accept_official_and_existing_cache_layouts(tmp_path, session):
    subject = "sub-001"
    directory = tmp_path / subject
    prefix = subject
    if session:
        directory /= session
        prefix += f"_{session}"
    directory /= "eeg"
    directory.mkdir(parents=True)
    input_set = directory / f"{prefix}_task-N400_eeg.set"
    input_events = directory / f"{prefix}_task-N400_events.tsv"
    input_set.touch()
    input_events.touch()
    assert find_subject_inputs(tmp_path, subject) == (input_set, input_events)


def test_n400_inputs_do_not_mix_eeg_and_events_from_different_layouts(tmp_path):
    session = tmp_path / "sub-001" / "ses-N400" / "eeg"
    session.mkdir(parents=True)
    (session / "sub-001_ses-N400_task-N400_eeg.set").touch()
    cache = tmp_path / "sub-001" / "eeg"
    cache.mkdir()
    (cache / "sub-001_task-N400_events.tsv").touch()
    with pytest.raises(FileNotFoundError, match="sub-001_ses-N400_task-N400_events.tsv"):
        find_subject_inputs(tmp_path, "sub-001")


def test_target_mapping_excludes_prime_events():
    frame = pd.DataFrame({"onset": [0., 1., 2., 3., 4., 5.],
                          "value": [111, 211, 121, 222, 212, 221]})
    assert target_events(frame, 256).tolist() == [
        [256, 0, RELATED], [768, 0, UNRELATED], [1024, 0, RELATED], [1280, 0, UNRELATED],
    ]


def test_adjacency_is_subset_of_full_montage_in_declared_order():
    names = ["Fp1", "F3", "F7", "FC3", "C3", "C5", "P3", "P7", "P9", "PO7",
             "PO3", "O1", "Oz", "Pz", "CPz", "Fp2", "Fz", "F4", "F8", "FC4",
             "FCz", "Cz", "C4", "C6", "P4", "P8", "P10", "PO8", "PO4", "O2"]
    info = mne.create_info(names, 256, "eeg")
    info.set_montage("standard_1020")
    full, ordered = mne.channels.find_ch_adjacency(info, ch_type="eeg")
    idx = [ordered.index(name) for name in ROI]
    actual = roi_adjacency(info).toarray()
    assert actual.shape == (3, 3)
    assert np.array_equal(actual, full.toarray()[np.ix_(idx, idx)])
    assert actual[0, 1] and actual[0, 2]


def test_missing_required_channel_fails_instead_of_shrinking_roi():
    channels = ["Cz", "Pz", *[f"other{i}" for i in range(28)]]
    with pytest.raises(ValueError, match="CPz"):
        validate_channels(channels)


@pytest.mark.parametrize("counts", [{"related": 29, "unrelated": 60},
                                    {"related": 60, "unrelated": 29},
                                    {"related": 60}])
def test_insufficient_condition_trials_fail_instead_of_dropping_subject(counts):
    with pytest.raises(ValueError, match=">=30"):
        validate_trial_counts(counts)


def test_custom_external_paths_and_new_output_parent(tmp_path):
    run_dir = tmp_path / "study"
    prepare_run_directory(run_dir)
    out = tmp_path / "new_parent" / "summary.json"
    write_json(out, {"private_outputs": display_path(run_dir)})
    assert out.exists()
    assert display_path(run_dir) == str(run_dir.resolve())
    (run_dir / "process.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="fresh empty"):
        prepare_run_directory(run_dir)
