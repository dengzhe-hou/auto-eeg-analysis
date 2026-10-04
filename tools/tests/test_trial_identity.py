"""Focused checks of source-identity mapping, independent of equal trial counts."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("trial_identity", ROOT / "tools/validation/validate_trial_identity.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_equal_counts_do_not_establish_identity():
    result = audit.membership_summary([16, 17, 19], [16, 18, 19])
    assert result["aea_retained"] == result["reference_retained"] == 3
    assert not result["exact_membership"]
    assert result["aea_only_source_rows"] == [17]
    assert result["reference_only_source_rows"] == [18]
    assert result["intersection"] == 2


def test_selection_must_identify_actual_retained_events():
    events = np.array([[100, 0, 1], [200, 0, 2], [300, 0, 1]])
    audit.validate_selection(events[[0, 2]], [0, 2], ((), ("P9",), ()), events)
    with pytest.raises(ValueError, match="retained events"):
        audit.validate_selection(events[[0, 1]], [0, 2], ((), ("P9",), ()), events)
    with pytest.raises(ValueError, match="empty drop_log"):
        audit.validate_selection(events[[0, 2]], [0, 2], ((), (), ()), events)


def test_non_unique_source_identity_is_not_silently_accepted():
    with pytest.raises(ValueError, match="found 2"):
        audit.unique_match([16, 17], "same sample and condition")
    with pytest.raises(ValueError, match="duplicate retained source"):
        audit.membership_summary([16, 16], [16, 17])


def _saved_reference(tmp_path, boundary=False, multi_status=False):
    """Real FIF fixture: TSV has an ignored status row; clean selection does not index TSV."""
    mne = pytest.importorskip("mne")
    pd = pytest.importorskip("pandas")
    raw = mne.io.RawArray(np.zeros((1, 1500)), mne.create_info(["P9"], 256, ["eeg"]), verbose="ERROR")
    onsets = [0.5, 1.0, 2.0, 3.0]
    names = ["STATUS", "standard", "deviant", "standard"]
    codes = [1, 80, 70, 80]
    if boundary:
        onsets[-1] = 5.75
    descriptions = names.copy()
    if multi_status:
        onsets.insert(0, .25)
        names.insert(0, "STATUS")
        codes.insert(0, 4)
        descriptions = ["STATUS/4", "STATUS/1", *names[2:]]
    raw.set_annotations(mne.Annotations(onsets, [0.] * len(onsets), descriptions))
    subject = "sub-001"
    raw.save(tmp_path / f"{subject}_task-MMN_proc-filt_raw.fif", verbose="ERROR")
    events, event_id = mne.events_from_annotations(raw, verbose="ERROR")
    picked = events[np.isin(events[:, 2], [event_id["standard"], event_id["deviant"]])]
    metadata = pd.DataFrame({"event_name": ["standard", "deviant", "standard"]})
    epochs = mne.Epochs(raw, picked, event_id={k: event_id[k] for k in ("standard", "deviant")},
                        tmin=-.1, tmax=.2, baseline=None, metadata=metadata, preload=True, verbose="ERROR")
    epochs.save(tmp_path / f"{subject}_task-MMN_epo.fif", verbose="ERROR")
    epochs.drop([1], reason="P9", verbose="ERROR")
    epochs.save(tmp_path / f"{subject}_task-MMN_proc-clean_epo.fif", verbose="ERROR")
    source = pd.DataFrame({"onset": onsets, "sample": (np.array(onsets) * 1024).astype(int), "value": codes,
                           "trial_type": ["STATUS" if x == "STATUS" else "stimulus" for x in names]})
    bids = source.copy()
    bids["trial_type"] = names
    return source, bids


def test_reference_mapping_uses_tsv_identity_not_fif_selection(tmp_path):
    source, bids = _saved_reference(tmp_path)
    pre, clean, source_rows, checks, _ = audit.reference_mapping("MMN", "sub-001", source, bids, tmp_path)
    assert clean.selection.tolist() == [0, 2]
    assert source_rows == [1, 2, 3]
    assert [source_rows[i] for i in clean.selection] == [1, 3]
    assert checks["raw_annotation_source_bijection"]
    assert len(pre.drop_log) == 3 and len(source) == 4


def test_input_identity_survives_pre_epoch_boundary_drop(tmp_path):
    source, bids = _saved_reference(tmp_path, boundary=True)
    pre, clean, rows, checks, inputs = audit.reference_mapping("MMN", "sub-001", source, bids, tmp_path)
    assert len(inputs) == len(rows) == 3
    assert len(pre) == 2
    assert checks["pre_epoch_drops"] == [{"input_index": 2, "source_row_0based": 3, "reasons": ["TOO_SHORT"]}]
    assert clean.drop_log[2] == ("TOO_SHORT",)


def test_multivalue_status_description_maps_to_its_original_code(tmp_path):
    source, bids = _saved_reference(tmp_path, multi_status=True)
    _, clean, rows, checks, _ = audit.reference_mapping("MMN", "sub-001", source, bids, tmp_path)
    assert rows == [2, 3, 4]
    assert [rows[i] for i in clean.selection] == [2, 4]
    assert checks["source_events"] == 5


def test_changed_bids_original_code_breaks_provenance(tmp_path):
    source, bids = _saved_reference(tmp_path)
    bids.loc[2, "value"] = 80
    with pytest.raises(AssertionError):
        audit.reference_mapping("MMN", "sub-001", source, bids, tmp_path)


def test_original_condition_rules_keep_excluded_event_types_out():
    assert audit.condition_for("MMN", 180) is None
    assert audit.condition_for("P3", 22) == "target"
    assert audit.condition_for("P3", 23) == "standard"
    assert audit.condition_for("N170", 121) is None
    assert audit.condition_for("ERN", 211) == "error"
    assert audit.condition_for("ERN", 212) == "correct"
    assert audit.condition_for("N400", 112) is None
    assert audit.condition_for("N400", 212) == "related"


def test_missing_cohort_and_unknown_requested_subject_fail(tmp_path):
    with pytest.raises(ValueError, match="expected 20 source subjects; found 0"):
        audit.select_subjects(tmp_path, "P3")
    for number in range(1, 21):
        (tmp_path / f"sub-{number:03d}").mkdir()
    assert audit.select_subjects(tmp_path, "P3", ["sub-010"]) == ["sub-010"]
    with pytest.raises(ValueError, match="unknown requested subjects"):
        audit.select_subjects(tmp_path, "P3", ["sub-999"])


def test_diagnostic_cli_cannot_overwrite_retained_supplement(monkeypatch):
    monkeypatch.setattr(audit.sys, "argv", ["validate_trial_identity.py", "--out", str(audit.HERE / "trial_identity_results.json")])
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 2
