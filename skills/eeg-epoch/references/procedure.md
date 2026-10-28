## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **WINDOW = read from DATASET_BRIEF** — default `[-0.2, 1.2]` s.
- **BASELINE = read from DATASET_BRIEF** — default `[-0.2, 0]` s. Set `null` to skip baseline correction.
- **AUTOREJECT_MODE = `local`** — `local` for per-channel per-epoch thresholds (Jas et al. 2017); `global` for fixed threshold; `none` to skip.
- **REJECT_THRESHOLD = `None`** — Only used when `AUTOREJECT_MODE = global` or as the no-`autoreject` fallback. Default: `dict(eeg=100e-6)` (100 µV peak-to-peak) — a conservative band that two independent reference workflows converge on (the MNE preprocessing tutorial recommends 50–100 µV; the MCKJ EEGLAB course uses ±100 µV then tightens to ±60 µV). Tighten to `dict(eeg=75e-6)` or `60e-6` for clean, low-impedance data. **Do not** use the older 150–200 µV default: 200 µV peak-to-peak lets through real artifacts (the MNE tutorial flags `2e-4` as "set too large"). Apply this threshold **after** ICA, never before — pre-ICA it discards good trials for blinks that ICA would have removed.
- **MIN_TRIALS_PER_CONDITION = 30** — Subjects below this for any analyzed condition are flagged. Luck (2014) recommends ≥30, preferably ≥60.
- **EXCLUSION_THRESHOLD = 10** — Subjects below this are excluded entirely and documented.
- **OUTPUT_DIR = `epoch-stage/`** — Create if missing.
- **OUTPUT_FORMAT = `epoch-stage/<sub>/<sub>-epo.fif`** — MNE Epochs FIF file.

> Override: `/eeg-epoch projects/my-study — window: -0.5,1.5 — baseline: -0.5,0 — reject_mode: autoreject`

## Phase A — Event Extraction

1. Read `DATASET_BRIEF.md` for:
   - Event coding scheme: numeric trigger codes (e.g., `{1: 'standard', 2: 'deviant'}`) or annotation strings.
   - Whether events are in the EEG data (trigger channel), a sidecar file (`*_events.tsv` for BIDS), or annotations.
   - Stimulus onset definition (trigger edge, photodiode, etc.).

2. Extract events per subject:

### MNE-Python event extraction

```python
import mne

raw = mne.io.read_raw_fif(raw_file, preload=True)

# Option 1: From trigger/stimulus channel (STI 014, Status, etc.)
events = mne.find_events(raw, stim_channel='STI 014',
                         min_duration=0.002,  # ignore spurious triggers < 2 ms
                         shortest_event=1)    # minimum event duration in samples

# Option 2: From annotations (common for BrainVision, EDF+, BIDS)
events, event_id = mne.events_from_annotations(raw,
                                                 event_id='auto')
# If annotation names need mapping:
# event_id = {'Stimulus/S  1': 1, 'Stimulus/S  2': 2}
# events, _ = mne.events_from_annotations(raw, event_id=event_id)

# Option 3: From BIDS events.tsv sidecar
# events = mne.read_events(events_tsv_path)
```

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

1. Create epochs from events:

### MNE-Python epoching

```python
event_id = {'standard': 1, 'deviant': 2}

epochs = mne.Epochs(
    raw, events, event_id,
    tmin=-0.2, tmax=1.2,
    baseline=(-0.2, 0),        # baseline correction window
    preload=True,
    reject=None,               # will use AutoReject instead
    reject_by_annotation=True, # skip annotated bad segments
    on_missing='warn',         # warn if event_id code missing from events
    detrend=None,              # set to 0 for DC detrend, 1 for linear
    proj=True                  # apply projections (SSP) if any
)

# Only if the plan specifies epoch-level resampling; keep enough padding for
# its filter edge effects outside the analyzed interval.
# epochs.resample(256)  # only if original srate > 256 and needed
```

### Resting-state / continuous data (no event markers)

When there are no stimulus events (resting state, free viewing, sleep), cut the continuous recording into back-to-back fixed-length windows instead of event-locked epochs. **Do not baseline-correct** — there is no event onset to baseline against (this matches EEGLAB's `eeg_regepochs(..., 'rmbase', NaN)`).

```python
# Fixed-length epochs, e.g. 2 s windows, no overlap, no baseline correction.
epochs = mne.make_fixed_length_epochs(
    raw, duration=2.0, overlap=0.0,
    preload=True, reject_by_annotation=True
)
# make_fixed_length_epochs does NOT apply baseline correction — do not call apply_baseline.

# Equivalent two-step form if you need to customise the events:
# events = mne.make_fixed_length_events(raw, duration=2.0, overlap=0.0)
# epochs = mne.Epochs(raw, events, tmin=0, tmax=2.0, baseline=None, preload=True)
```

**Choosing the window length:** the segment duration fixes the achievable spectral resolution downstream — `resolution_Hz = 1 / duration_s`. A 2 s window gives 0.5 Hz bins (adequate to separate individual alpha peaks); use 4 s for 0.25 Hz. Longer windows give finer resolution but fewer, noisier independent segments. Choose `duration` from the resolution your PSD/TFR analysis needs, not by default. Cross-link: `eeg-spectral` consumes these epochs and should set Welch `n_per_seg` to match the epoch duration.

2. Verify epoch count per condition matches expected count (within tolerance for edge-of-recording events).

## Phase C — Baseline Correction

1. Default: subtract mean of baseline window from each epoch.
   - MNE: `baseline=(-0.2, 0)` in `mne.Epochs()` constructor, or `epochs.apply_baseline((-0.2, 0))`.
   - Baseline must be entirely pre-stimulus.
2. When to skip baseline correction:
   - If the analysis is on absolute power (e.g., resting state).
   - If downstream TFR will apply its own baseline (to avoid double baseline correction).
   - Set `baseline=None` and document reason.
3. When to use `tmin` to `0` as baseline (entire pre-stimulus):
   - Standard for ERP analyses (Luck 2014).
   - Use the entire pre-stimulus window unless there is stimulus anticipation (CNV, readiness potential).
4. Baseline duration recommendations (Luck 2014):
   - Minimum 100 ms. Preferred 200 ms.
   - Longer baselines reduce noise but risk including slow drifts.
   - For very short epochs (e.g., auditory brainstem response): 50 ms may suffice.

## Phase D — Artifact Rejection

### AutoReject (Jas et al. 2017) — recommended

```python
from autoreject import AutoReject, get_rejection_threshold

# Local mode (default): per-channel, per-epoch adaptive thresholds
ar = AutoReject(
    n_interpolate=[1, 2, 4, 8, 12, 16],  # candidates for n channels to interpolate
    random_state=42,
    n_jobs=-1,
    verbose=True
)
epochs_clean, reject_log = ar.fit_transform(epochs, return_log=True)

# reject_log.bad_epochs: boolean array of rejected epochs
# reject_log.labels: (n_epochs, n_channels) — 0=good, 1=bad, 2=interpolated
n_rejected = reject_log.bad_epochs.sum()
n_interpolated = (reject_log.labels == 2).sum()
```

**Local vs Global AutoReject:**
- **Local** (default): learns per-channel thresholds and can interpolate bad channels within individual epochs rather than rejecting the entire epoch. Better trial retention. Use for most analyses.
- **Global**: computes a single threshold dictionary (like MNE's `reject` parameter). Faster but less sensitive.
  ```python
  reject = get_rejection_threshold(epochs, random_state=42)
  # Returns e.g. {'eeg': 120e-6}
  epochs.drop_bad(reject=reject)
  ```

### Threshold-based rejection (simple alternative)

```python
# Fixed threshold: reject epochs where any channel exceeds peak-to-peak amplitude.
# Conservative default 100 µV; tighten to 60–75 µV for clean, low-impedance data.
# Avoid 150–200 µV — too lax, lets real artifacts through (MNE tutorial). Apply after ICA.
reject = dict(eeg=100e-6)  # 100 µV peak-to-peak
epochs.drop_bad(reject=reject)

# Flat channel rejection: reject if any channel has < 1 µV range
flat = dict(eeg=1e-6)
epochs.drop_bad(reject=reject, flat=flat)
```

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
2. Apply minimum trial thresholds:
   - `< EXCLUSION_THRESHOLD` (default 10): **exclude subject entirely**. Document in `EXCLUSION_REPORT.md`.
   - `< MIN_TRIALS_PER_CONDITION` (default 30): **flag subject** with warning. Include in analysis but note reduced reliability.
   - `≥ MIN_TRIALS_PER_CONDITION`: no flag needed.

3. Trial count recommendations (from Luck 2014, Ch. 4):
   - **ERP components (N170, P300, N400, etc.)**: minimum 30 trials per condition, 60+ preferred.
   - **MMN (mismatch negativity)**: minimum 100 deviant trials (small amplitude component).
   - **P3a/P3b**: 30–40 trials sufficient (large amplitude).
   - **N2pc**: 100+ trials recommended (small lateralized difference).
   - **Error-related negativity (ERN)**: 6–8 trials may suffice (very large amplitude), but 20+ preferred.
   - General rule: smaller component amplitude → more trials needed.

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

- [ ] Every subject in `ica-stage/` has corresponding epochs in `epoch-stage/` (or is documented in `EXCLUSION_REPORT.md`).
- [ ] `EPOCH_PARAMS.json` exists with all fields populated.
- [ ] `TRIAL_COUNT_TABLE.csv` exists and no subject has 0 trials in any condition.
- [ ] Epoch time window matches `DATASET_BRIEF.md` specification.
- [ ] Baseline window is entirely pre-stimulus.
- [ ] Event codes in epochs match `DATASET_BRIEF.md` condition table.
- [ ] Rejected epoch count is reasonable (< 50% per subject; if higher, investigate).
- [ ] `EXCLUSION_REPORT.md` exists (even if no subjects excluded).
- [ ] Epoch files load without error: `mne.read_epochs(fif_path)` succeeds.
- [ ] No channel has been interpolated in > 50% of epochs (flag as potentially bad channel — should have been removed upstream).

## Failure Modes

| Symptom | Action |
|---|---|
| `ica-stage/` missing | Stop. Run `eeg-ica` first. |
| No events found in data | Check `stim_channel` name. Try `mne.find_events` with different `stim_channel` or `mne.events_from_annotations`. |
| Event codes don't match DATASET_BRIEF | Stop. Ask user to verify event coding. Common issue: event codes are strings in annotations but integers in the brief. |
| > 50% epochs rejected for a subject | Investigate: was ICA cleaning sufficient? Are there remaining bad channels? Consider re-running upstream stages. |
| AutoReject takes > 30 min per subject | Normal for high-density EEG (128+ channels). Consider `global` mode or reducing `n_interpolate` candidates. |
| Unequal trial counts across conditions | Expected for oddball/rare-event paradigms. Document. If comparing conditions, note that noise levels differ. |
| Baseline correction flattens the ERP | Check if baseline window includes neural activity (e.g., CNV, preceding response). Shorten baseline or use pre-trial baseline. |
| `autoreject` not installed | Fall back to `global` threshold rejection with `reject=dict(eeg=150e-6)`. Log substitution. |
| Epochs have different numbers of time points | Check if resampling was applied inconsistently. All epochs for a subject must have identical shape. |
