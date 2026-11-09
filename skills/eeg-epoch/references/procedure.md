## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **SCIENTIFIC SETTINGS** — resolve from the approved task/plan into
  `approved_epoch_params`, without fallback values: `event_source`, `event_id`,
  event detection settings; `tmin`, `tmax` for event-locked data or `duration_s`,
  `overlap_s` for fixed-length data; `baseline`, `baseline_stage`, `detrend`,
  `proj`, `reject_by_annotation`, `on_missing`, rejection method/settings, and
  flag/exclusion criteria. Explicit `None` or `none` differs from an absent choice.
- **ICA HANDOFF** — record `ica_fit_domain` and actual input/output paths:
  - `continuous`: preprocessing → ICA-cleaned Raw → epoching/final rejection.
  - `epochs`: preprocessing → initial epochs (`*-preica-epo.fif`) → ICA-cleaned
    epochs (`ica-stage/<sub>/<sub>-clean-epo.fif`) → epoch finalization. Preserve
    the original analysis-bandpass epochs separately from any ICA fitting copy.
  - `none`: supplied preprocessed Raw → epoching/final rejection.
  Do not select a route from ISI alone. For epoch-first finalization, use the
  existing cleaned Epochs and their events; do not re-cut or reapply a baseline.
- **TRIAL COUNTS** — there are no implicit 30-trial flag or 10-trial exclusion
  rules. Apply the approved scope (condition, contrast or participant). With no
  approved cutoff, record counts/quality and mark any needed inclusion decision
  unresolved rather than removing a participant.
- **OUTPUT_DIR = `epoch-stage/`** — Create if missing.
- **OUTPUT_FORMAT = `epoch-stage/<sub>/<sub>-epo.fif`** — MNE Epochs FIF file.

An explicit user instruction may amend the plan. An agent-generated override
does not authorize a new baseline, threshold or participant exclusion.

## Phase A — Event Extraction

1. Read `DATASET_BRIEF.md` for:
   - Event coding scheme: numeric trigger codes (e.g., `{1: 'standard', 2: 'deviant'}`) or annotation strings.
   - Whether events are in the EEG data (trigger channel), a sidecar file (`*_events.tsv` for BIDS), or annotations.
   - Stimulus onset definition (trigger edge, photodiode, etc.).

2. Extract events per subject:

### MNE-Python event extraction

```python
import mne

# AEA example: event-source
# raw and approved_epoch_params are the supplied input and resolved plan.
source = approved_epoch_params['event_source']
event_id = approved_epoch_params['event_id']
if source == 'stim':
    events = mne.find_events(raw, **approved_epoch_params['stim_detection'])
elif source in ('annotations', 'bids'):
    # For BIDS, raw must have been loaded through read_raw_bids below.
    # Explicit mapping preserves the intended labels/codes; do not infer them.
    events, event_id = mne.events_from_annotations(
        raw, event_id=event_id, regexp=None,
        use_rounding=approved_epoch_params['use_rounding'])
else:
    raise ValueError('Resolve the event source before extraction')
```

For BIDS input, load the dataset with MNE-BIDS so the sidecar events are attached
as annotations, then take the single `bids` branch above:

```python
# AEA example: bids-input
from mne_bids import read_raw_bids
raw = read_raw_bids(bids_path=bids_path, verbose=False)
raw.load_data()
```

Do not pass a BIDS `events.tsv` to `mne.read_events`: that reader expects MNE
event-file conventions, not BIDS onset seconds and condition columns. If the
input is an isolated sidecar, resolve its recording/time origin and condition
mapping before conversion; do not invent a sampling grid. Inspect event counts
and sample positions, including `raw.first_samp`, against the imported data.

3. Build `event_id` dictionary mapping condition labels to numeric codes.
4. Verify event counts per condition. Write `epoch-stage/EVENT_SUMMARY.json`:
```json
{
  "subject": "sub-01",
  "total_events": 480,
  "per_condition": {"standard": 400, "deviant": 80},
  "event_source": "annotations",
  "duplicate_events_removed": 0,
  "events_outside_recording": 0
}
```

## Phase B — Epoch Creation

Use the actual `epochs.times` integer-sample grid for measurement and checks.
Nominal epoch bounds need not be representable at the output sampling rate;
for example -0.2 s at 256 Hz rounds to -0.19921875 s. See
[approved ERP execution](approved-erp.md#approved-erp-execution). Do not invent
a second grid starting at nominal tmin or compare native sample indices directly
with indices after resampling. Preserve the plan's declared event source.

1. Create epochs from events:

### MNE-Python epoching

```python
# AEA example: event-epochs
epochs = mne.Epochs(
    raw, events, approved_epoch_params['event_id'],
    tmin=approved_epoch_params['tmin'], tmax=approved_epoch_params['tmax'],
    baseline=approved_epoch_params['baseline_at_creation'],
    preload=True,
    reject=None,               # apply only the selected Phase D method
    reject_by_annotation=approved_epoch_params['reject_by_annotation'],
    on_missing=approved_epoch_params['on_missing'],
    detrend=approved_epoch_params['detrend'],
    proj=approved_epoch_params['proj']
)

# Only if the plan specifies epoch-level resampling; keep enough padding for
# its filter edge effects outside the analyzed interval.
# epochs.resample(256)  # only if original srate > 256 and needed
```

### Resting-state / continuous data (no event markers)

For an approved fixed-length analysis, use its duration and overlap. The helper
does not baseline-correct. Any separately approved correction must be explicit
and recorded, rather than inferred from event-locked ERP examples.

```python
# AEA example: fixed-epochs
epochs = mne.make_fixed_length_epochs(
    raw, duration=approved_epoch_params['duration_s'],
    overlap=approved_epoch_params['overlap_s'],
    proj=approved_epoch_params['proj'], preload=True,
    reject_by_annotation=approved_epoch_params['reject_by_annotation']
)
```

If custom events require the two-step form, MNE includes `tmax`. Use the same
sample count as the helper, rather than adding the endpoint sample:

```python
# AEA example: fixed-epochs-two-step
events = mne.make_fixed_length_events(
    raw, duration=approved_epoch_params['duration_s'],
    overlap=approved_epoch_params['overlap_s'])
epochs = mne.Epochs(
    raw, events, event_id=None, tmin=0,
    tmax=approved_epoch_params['duration_s'] - 1 / raw.info['sfreq'],
    baseline=None, detrend=None, proj=approved_epoch_params['proj'],
    reject_by_annotation=approved_epoch_params['reject_by_annotation'],
    preload=True)
```

At 250 Hz a 2 s segment contains 500 points; the last point is 1.996 s. Verify
the actual count on the requested grid. For spectral work, distinguish FFT bin
spacing (`sfreq / n_fft`) from resolution governed by segment duration/window;
zero-padding does not supply additional independent spectral information.

2. Verify epoch count per condition matches expected count (within tolerance for edge-of-recording events).

## Phase C — Baseline Correction

Resolve the approved interval (or explicit `None`) and stage. Set
`baseline_at_creation` to that interval only when correction is approved at
creation; otherwise it is explicitly `None`. In epoch-first ICA, use the
approved fitting baseline policy and apply any final correction only after
cleaning if specified. Check `epochs.baseline` and the saved processing record
before applying it; do not apply it twice. An unavailable or out-of-range
baseline is an unresolved step, not permission to shorten the interval.

## Phase D — Artifact Rejection

### AutoReject (Jas et al. 2017) — only when selected

```python
# AEA example: epoch-rejection
method = approved_epoch_params['rejection_method']
if method == 'autoreject_local':
    from autoreject import AutoReject
    ar = AutoReject(**approved_epoch_params['autoreject_local'])
    epochs_clean, reject_log = ar.fit_transform(epochs, return_log=True)
elif method == 'autoreject_global':
    from autoreject import get_rejection_threshold
    reject = get_rejection_threshold(
        epochs, **approved_epoch_params['autoreject_global'])
    epochs_clean = epochs.copy().drop_bad(reject=reject)
    reject_log = None
elif method == 'threshold':
    epochs_clean = epochs.copy().drop_bad(
        reject=approved_epoch_params['reject_v'],
        flat=approved_epoch_params['flat_v'])
    reject_log = None
elif method == 'none':
    epochs_clean, reject_log = epochs.copy(), None
else:
    raise ValueError('Resolve the rejection method before executing')
```

These branches are alternatives. A missing selected package leaves this step
incomplete; do not silently change to a fixed threshold. MNE `reject` uses
peak-to-peak volts, whereas EEGLAB signed amplitude limits use a different
definition. Record the threshold definition, stage, channels and applied values.

### Recording rejection details

For every subject, record:
- Number of epochs before rejection per condition.
- Number rejected per condition (and reason if available).
- Number interpolated (AutoReject local mode).
- Percentage rejected.
- Channels most frequently interpolated.

Write per-subject: `epoch-stage/<sub>/<sub>-reject-log.json`.

## Phase E — Trial Counting and Exclusion

1. After rejection, count remaining trials per condition per subject.
2. Apply the approved flag/exclusion criteria and their scope. Keep condition
   counts distinct from participant inclusion; one sparse condition does not
   automatically exclude that participant from all contrasts. Record the exact
   rule and reason. If there is no cutoff policy, retain the counts and identify
   any unresolved inclusion decision without inventing a 10/30-trial rule.

3. Trial-count needs depend on the score, noise and design. Descriptive examples
   below illustrate reporting only; their numbers are not study cutoffs.

4. Write `epoch-stage/TRIAL_COUNT_TABLE.csv`:
```csv
subject,condition,n_before_reject,n_after_reject,n_rejected,pct_rejected,flag
sub-01,standard,400,385,15,3.8,ok
sub-01,deviant,80,72,8,10.0,ok
sub-02,standard,400,312,88,22.0,high_rejection
sub-02,deviant,80,18,62,77.5,below_minimum
```

5. Write `epoch-stage/EXCLUSION_REPORT.md`:
```markdown
# Exclusion Report
## Excluded subjects
- sub-05: deviant condition 8 trials (below threshold 10). Reason: excessive muscle artifacts.
## Flagged subjects (included with warning)
- sub-02: deviant condition 18 trials (below recommended 30).
## Summary
- Total subjects: 24
- Excluded: 1 (4.2%)
- Flagged: 1 (4.2%)
- Mean rejection rate: 12.3% (SD: 8.1%)
```

## Phase F — Save Outputs

For each subject, save:

### `epoch-stage/<sub>/<sub>-epo.fif`
MNE Epochs FIF file with metadata, event_id, and rejection info embedded.

### `epoch-stage/<sub>/<sub>-reject-log.json`
```json
{
  "subject": "sub-01",
  "autoreject_mode": "local",
  "n_epochs_before": 480,
  "n_epochs_after": 457,
  "n_rejected": 23,
  "n_interpolated_total": 89,
  "pct_rejected": 4.8,
  "per_condition": {
    "standard": {"before": 400, "after": 385, "rejected": 15},
    "deviant": {"before": 80, "after": 72, "rejected": 8}
  },
  "most_interpolated_channels": ["Fp1", "Fp2", "T7"],
  "autoreject_thresholds_uv": {"Fp1": 95.2, "Fz": 112.4}
}
```

### `epoch-stage/EPOCH_PARAMS.json`
Illustrative resolved record only. Write actual settings and installed versions,
including ICA domain, input path, baseline stage, rejection definition and the
approved scope of inclusion rules. Do not copy these values into a new study.
```json
{
  "window_s": [-0.2, 1.2],
  "baseline_s": [-0.2, 0],
  "autoreject_mode": "local",
  "min_trials_per_condition": 30,
  "exclusion_threshold": 10,
  "event_source": "annotations",
  "event_id": {"standard": 1, "deviant": 2},
  "n_subjects_processed": 24,
  "n_subjects_excluded": 1,
  "backend": "mne",
  "mne_version": "1.7.0",
  "autoreject_version": "0.4.3"
}
```

### `epoch-stage/TRIAL_COUNT_TABLE.csv`
Summary table (see Phase E above).

### `epoch-stage/EXCLUSION_REPORT.md`
Subject exclusion and flagging report (see Phase E above).

## Phase G — Sanity Checks

All must pass before declaring success:

- [ ] Every approved input subject has final epochs or a documented pending/excluded status, using the selected ICA/no-ICA route.
- [ ] `EPOCH_PARAMS.json` exists with all fields populated.
- [ ] Counts, retained event identities and drop reasons reconcile. Zero-trial conditions are explicitly unavailable; they are never averaged as zeros.
- [ ] Epoch time window matches `DATASET_BRIEF.md` specification.
- [ ] Baseline interval and actual stage match the approved settings and the saved record shows it was applied at most once.
- [ ] Event codes in epochs match `DATASET_BRIEF.md` condition table.
- [ ] Rejected epoch count is reasonable (< 50% per subject; if higher, investigate).
- [ ] `EXCLUSION_REPORT.md` exists (even if no subjects excluded).
- [ ] Epoch files load without error: `mne.read_epochs(fif_path)` succeeds.
- [ ] No channel has been interpolated in > 50% of epochs (flag as potentially bad channel — should have been removed upstream).

## Failure Modes

| Symptom | Action |
|---|---|
| Expected input missing | Identify the approved route and missing artifact. Do not require ICA for a no-ICA task or for initial epoch-first inputs. |
| No events found in data | Check `stim_channel` name. Try `mne.find_events` with different `stim_channel` or `mne.events_from_annotations`. |
| Event codes don't match DATASET_BRIEF | Stop. Ask user to verify event coding. Common issue: event codes are strings in annotations but integers in the brief. |
| > 50% epochs rejected for a subject | Investigate: was ICA cleaning sufficient? Are there remaining bad channels? Consider re-running upstream stages. |
| AutoReject is slow | Report runtime and continue within approved resources. A global-mode substitution or changed interpolation candidates requires approval. |
| Unequal trial counts across conditions | Expected for oddball/rare-event paradigms. Document. If comparing conditions, note that noise levels differ. |
| Baseline correction changes the ERP unexpectedly | Compare the actual interval/stage to the plan and check preceding activity. Report the issue; do not shorten or replace the approved baseline automatically. |
| Selected `autoreject` dependency missing | Leave this step incomplete and report the missing package; no threshold fallback. |
| Epochs have different numbers of time points | Check if resampling was applied inconsistently. All epochs for a subject must have identical shape. |
