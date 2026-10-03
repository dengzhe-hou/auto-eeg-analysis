---
name: eeg-epoch
description: "Segment cleaned EEG into epochs around event markers, baseline-correct, run AutoReject for trial-level artifact rejection. Reads ica-stage/ output and DATASET_BRIEF condition codes. Backend: MNE-Python. Use when user says 'epoch', 'segment', 'create epochs', 'trial rejection', or after eeg-ica completes."
argument-hint: "[project-dir] [— window: -0.2,1.2] [— baseline: -0.2,0] [— reject_mode: autoreject|threshold|none]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# eeg-epoch: continuous → epoched

## Context: $ARGUMENTS

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

## Required Inputs

Before running, these must exist:

1. `ica-stage/` — cleaned continuous data per subject (`*-ica-raw.fif` or `*-clean-raw.fif`). **Stop if missing.**
2. `DATASET_BRIEF.md` — for condition codes/labels, event mapping, epoch window, baseline window.
3. `ANALYSIS_PLAN.md` — for exclusion criteria and minimum trial counts.
4. `ENVIRONMENT.json` — to resolve backend availability and `autoreject` installation.

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

# Optional: resample after epoching to avoid jitter artifacts
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

## Critical Rules

- **Never** epoch before ICA cleaning. ICA should be applied to continuous data (eeg-ica stage), and epochs are cut from the cleaned continuous data.
- **Never** use too-short epochs that cut off the component of interest. The epoch must extend beyond the latest expected component peak (e.g., P600 requires at least 800 ms post-stimulus).
- **Never** use a baseline window that overlaps with the stimulus or a preceding stimulus in rapid designs. For SOA < 500 ms, consider a pre-trial baseline or no baseline.
- **Never** apply AutoReject and then also apply threshold rejection — choose one method.
- **Never** exclude subjects without documenting the reason in `EXCLUSION_REPORT.md`.
- **Never** set `MIN_TRIALS_PER_CONDITION` below 10 — at that point, ERP averages are unreliable for any component.
- **Never** resample before epoching if the events are in sample indices — this shifts event timing. Resample after epoching, or re-extract events after resampling.
- **Never** drop epochs silently. Every rejection must be logged and counted.
- **Never** baseline-correct fixed-length / resting-state epochs. With no event onset there is nothing to baseline against — use `baseline=None` (MNE `make_fixed_length_epochs` does this by default; EEGLAB `eeg_regepochs(..., 'rmbase', NaN)`). Apply baseline only to event-locked epochs.
- **Never** apply a fixed amplitude threshold before ICA. Pre-ICA, blinks and saccades make most frontal epochs exceed any reasonable threshold, so you discard neural trials that ICA could have salvaged. Threshold (or AutoReject) goes after ICA.

## Domain Knowledge (distilled from EEG methodology literature)

### AutoReject (Jas et al. 2017, NeuroImage)

- AutoReject learns per-channel amplitude thresholds using cross-validation on the epoch data.
- **Local mode**: for each epoch, identifies bad channels and interpolates them. Only rejects the epoch if too many channels are bad. Results in higher trial retention than global rejection.
- **Global mode**: computes a single rejection threshold dictionary (e.g., `{'eeg': 120e-6}`). Equivalent to MNE's `reject` parameter but data-driven instead of arbitrary.
- When to use local: most analyses. When to use global: very large datasets where local is too slow, or when you need a simple threshold for reporting.
- AutoReject should be applied **after** ICA (bad ICA components add variance that biases the learned thresholds).
- Cite: Jas, M., Engemann, D. A., Bekhti, Y., Raimondo, F., & Gramfort, A. (2017). Autoreject: Automated artifact rejection for MEG and EEG data. NeuroImage, 159, 417–429.

### Epoch parameters (Luck 2014, An Introduction to the Event-Related Potential Technique, Ch. 4)

- **Baseline duration**: minimum 100 ms. The baseline period must be free of neural activity related to the current trial or preceding trial.
- **Epoch length**: must extend beyond the latest component of interest. For P300: at least 800 ms. For LPP/P600: at least 1000 ms.
- **Pre-stimulus buffer**: include 100–200 ms extra before the analysis window for baseline and for wavelet edge artifacts if TFR follows.
- **Post-stimulus buffer**: include 100–200 ms extra after the analysis window to avoid edge effects.
- **High-pass filter interaction**: if the continuous data was high-pass filtered above 0.1 Hz, filter ringing can distort the baseline. Use longer baselines (300–500 ms) to accommodate filter transients.
- **Trial count**: The SNR of an ERP average improves as sqrt(N). Doubling trials from 30 to 60 improves SNR by ~41%.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd Edition. MIT Press.

### EEGLAB rejection methods (Delorme et al. 2007, J. Neurosci. Methods)

- EEGLAB provides multiple rejection criteria: amplitude threshold, joint probability, kurtosis, spectral threshold, and trend.
- **Amplitude threshold** (`pop_eegthresh`): simplest; rejects epochs exceeding ±X µV. Good for catching large artifacts but misses subtle ones.
- **Joint probability** (`pop_jointprob`): rejects statistically improbable epochs based on the distribution of all epochs. Good for detecting outliers.
- **Kurtosis** (`pop_rejkurt`): detects epochs with peaky or flat distributions. Good for catching brief muscle artifacts or flat-line segments.
- Best practice: combine multiple criteria or use automated methods (FASTER, AutoReject).
- Cite: Delorme, A., Sejnowski, T., & Makeig, S. (2007). Enhanced detection of artifacts in EEG data using higher-order statistics and independent component analysis. NeuroImage, 34(4), 1443–1449.

### Amplitude rejection thresholds — converging practice (~100 µV)

- Two independent reference workflows converge on a peak-to-peak rejection band of ~100 µV for typical scalp EEG, applied **after** ICA. The MNE-Python preprocessing tutorial's worked example uses `reject=dict(eeg=2e-4)` (200 µV) but its own annotation flags this as "set too large" and recommends 5e-5–1e-4 V (50–100 µV) for good-quality data. The MCKJ ERP course rejects at ±100 µV via EEGLAB `pop_eegthresh`, then tightens to ±60 µV once ICA has removed blinks.
- Practical default: `dict(eeg=100e-6)` conservative; tighten to 60–75 µV for clean, low-impedance recordings; loosen only with explicit justification. 150–200 µV passes real artifacts.
- Threshold rejection is amplitude-only and misses subtle artifacts; AutoReject (`get_rejection_threshold` for a data-driven global threshold, or local mode for per-channel interpolation) is the preferred replacement for a hand-set number when `autoreject` is available.
- Cite: MNE-Python preprocessing tutorial, "Rejecting Epochs based on channel amplitude" (mne.tools documentation); and COBIDAS-MEEG (Pernet et al. 2020, *Nature Neuroscience* 23, 1473–1483) for the requirement to report the exact threshold used.

### Epoch / segment duration sets spectral resolution

- For any analysis that goes to the frequency domain (PSD, Welch, TFR), the epoch or segment length **fixes** the frequency resolution: `resolution_Hz = sfreq / NFFT = 1 / duration_s`. Worked example: a resting recording at 256 Hz cut into 2 s segments (`L = 512` samples) yields `256/512 = 0.5 Hz` bins.
- Consequences for epoching choices: to resolve features 0.5 Hz apart (e.g. individual alpha sub-peaks) you need ≥2 s segments; for 0.25 Hz spacing you need ≥4 s. Longer segments buy finer resolution but yield fewer independent segments, so the PSD estimate is noisier (higher variance). This is the practical reason resting-state epoching often standardises on 2 s windows.
- Pick `duration` deliberately from the resolution the downstream analysis needs; pass the same length to `eeg-spectral` (Welch `n_per_seg = duration_s * sfreq`) so the epoching and PSD stages agree.
- Cite: Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra. *IEEE Trans. Audio Electroacoust.* 15(2), 70–73; standard FFT resolution relation Δf = fs/N.

### Trial count requirements across paradigms

| Paradigm / Component | Minimum trials | Recommended | Source |
|---|---|---|---|
| P300 (oddball) | 30 | 60+ | Luck 2014 |
| N170 (face/object) | 30 | 40+ | Luck 2014 |
| N400 (language) | 30 | 50+ | Luck 2014 |
| MMN (auditory) | 100 | 200+ | Näätänen et al. 2007 |
| N2pc (attention) | 100 | 200+ | Luck 2012 |
| ERN (error) | 6 | 20+ | Olvet & Hajcak 2009 |
| LPP (emotion) | 30 | 60+ | Luck 2014 |
| SSVEP | 10 | 20+ | Norcia et al. 2015 |

### COBIDAS-MEEG reporting (Pernet et al. 2020, Nature Neuroscience)

For epoching, the methods section must report:
- Epoch time window (pre- and post-stimulus)
- Baseline correction window and method
- Artifact rejection method, criteria, and thresholds
- Number of trials per condition per subject (mean ± SD, range)
- Number of excluded subjects and reason
- Software and version

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

## Cross-references

- **Inputs**: `ica-stage/*-clean-raw.fif`, `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, `ENVIRONMENT.json`
- **Outputs**: `epoch-stage/*-epo.fif`, `epoch-stage/*-reject-log.json`, `epoch-stage/EPOCH_PARAMS.json`, `epoch-stage/TRIAL_COUNT_TABLE.csv`, `epoch-stage/EXCLUSION_REPORT.md`
- **Next**: `eeg-erp` averages epochs into ERPs. `eeg-tfr` computes time-frequency from epochs. `eeg-spectral` runs PSD/Welch on epochs (especially the fixed-length resting-state epochs from Phase B — match Welch `n_per_seg` to the epoch duration; see the resolution = 1/duration rule). `eeg-stats` uses trial counts for power analysis.
- **Previous**: `eeg-ica` produces the cleaned continuous data consumed here.
