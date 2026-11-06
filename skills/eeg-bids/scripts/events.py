"""Keep task event identity intact through MNE-BIDS export and TSV read-back."""
from pathlib import Path

import mne
import numpy as np
import pandas as pd


def prepare_event_export(raw, *, source, event_id, additional_annotation_event_id, events):
    """Normalize one task-event source to annotations on a copy of the Raw.

    source='annotations' uses the original annotations and requires events=None.
    'stim'/'external' require an actual MNE event array and explicitly declared
    auxiliary annotation mappings. Task labels/codes may not also be auxiliary
    annotations. The original recording, annotations and mappings are unchanged.
    Pass events=None to write_raw_bids for ALL paths; do not submit both copies.
    """
    mapping = dict(event_id)
    auxiliary = dict(additional_annotation_event_id)
    if source not in ('annotations', 'stim', 'external'):
        raise ValueError('Resolve event source: annotations, stim or external')
    if set(mapping) & set(auxiliary) or set(mapping.values()) & set(auxiliary.values()):
        raise ValueError('Task and auxiliary annotation identities must be distinct')
    combined = {**mapping, **auxiliary}
    if len(set(combined.values())) != len(combined):
        raise ValueError('Event codes must identify unique descriptions')
    out = raw.copy()
    if source == 'annotations':
        if events is not None or auxiliary:
            raise ValueError('Annotation source uses events=None and one complete event_id')
        missing = set(raw.annotations.description) - set(mapping)
        if missing:
            raise ValueError(f'Annotation descriptions lack approved codes: {sorted(missing)}')
    else:
        values = np.asarray(events)
        if (values.ndim != 2 or values.shape[1] != 3
                or not np.issubdtype(values.dtype, np.integer)):
            raise ValueError('Stim/external source requires an integer MNE events array')
        if set(values[:, 2]) - set(mapping.values()):
            raise ValueError('Actual event codes disagree with the approved event_id')
        if np.any(values[:, 0] < raw.first_samp) or np.any(values[:, 0] > raw.last_samp):
            raise ValueError('Task events lie outside this recording')
        if set(raw.annotations.description) - set(auxiliary):
            raise ValueError('Existing annotations need explicit auxiliary mapping; avoid duplicate task events')
        # Raw annotation onsets include first_time. set_annotations applies that
        # shift once to these relative onsets, for dated and undated recordings.
        onsets = np.r_[raw.annotations.onset - raw.first_time,
                       (values[:, 0] - raw.first_samp) / raw.info['sfreq']]
        durations = np.r_[raw.annotations.duration, np.zeros(len(values))]
        inverse = {code: name for name, code in mapping.items()}
        descriptions = list(raw.annotations.description) + [inverse[code] for code in values[:, 2]]
        out.set_annotations(mne.Annotations(onsets, durations, descriptions, orig_time=None))

    exported, _ = mne.events_from_annotations(out, event_id=combined, regexp=None,
                                             use_rounding=True)
    inverse = {code: name for name, code in combined.items()}
    expected = [dict(sample=int(row[0] - raw.first_samp),
                     onset=float((row[0] - raw.first_samp) / raw.info['sfreq']),
                     duration=float(duration), value=int(row[2]), trial_type=inverse[row[2]])
                for row, duration in zip(exported, out.annotations.duration)]
    receipt = dict(source=source, event_id=combined, first_samp=int(raw.first_samp),
                   sfreq=float(raw.info['sfreq']), expected_events=expected,
                   n_events=len(expected), task_events_from_single_source=True)
    return out, dict(events=None, event_id=combined), receipt


def check_exported_events(path, *, receipt, time_atol_s):
    """Compare actual exported rows, preserving duplicate counts and durations.

    A continuous record with no events may legitimately have no events.tsv.
    This checks the declared export contract, not the scientific marker meaning.
    """
    expected = receipt['expected_events']
    path = Path(path)
    if not path.exists():
        if expected:
            raise ValueError('Expected BIDS events.tsv was not written')
        return dict(status='passed', n_events=0, events_file_present=False)
    frame = pd.read_csv(path, sep='\t')
    if len(frame) != len(expected):
        raise ValueError('Exported event count differs from the declared source')
    if not expected:
        return dict(status='passed', n_events=0, events_file_present=True)
    columns = ['sample', 'trial_type', 'value', 'duration', 'onset']
    if not set(columns) <= set(frame):
        raise ValueError('Exported event identity/timing columns are missing')
    keys = ['sample', 'trial_type', 'value', 'duration']
    actual = frame[columns].sort_values(keys).reset_index(drop=True)
    wanted = pd.DataFrame(expected)[columns].sort_values(keys).reset_index(drop=True)
    for key in ('sample', 'trial_type', 'value'):
        if not np.array_equal(actual[key].to_numpy(), wanted[key].to_numpy()):
            raise ValueError(f'Exported event {key} differs from the declared source')
    for key in ('onset', 'duration'):
        if not np.allclose(actual[key], wanted[key], rtol=0, atol=time_atol_s):
            raise ValueError(f'Exported event {key} differs from the declared source')
    return dict(status='passed', n_events=len(expected), events_file_present=True)
