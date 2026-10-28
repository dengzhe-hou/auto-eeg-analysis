---
name: eeg-epoch
description: "Segment cleaned EEG into epochs around event markers, baseline-correct, run AutoReject for trial-level artifact rejection. Reads ica-stage/ output and DATASET_BRIEF condition codes. Backend: MNE-Python. Use when user says 'epoch', 'segment', 'create epochs', 'trial rejection', or after eeg-ica completes."
argument-hint: "[project-dir] [— window: -0.2,1.2] [— baseline: -0.2,0] [— reject_mode: autoreject|threshold|none]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# eeg-epoch: continuous → epoched

## Context: $ARGUMENTS

## Use this skill

Read the task and the approved analysis plan before choosing a procedure. The
name and description select this skill; they do not specify the analysis.
Load only the relevant sections below, rather than every reference in advance.
For a bounded calculation, use the supplied inputs without inventing upstream
stages or approvals. Keep the actual method, parameters, outputs, and checks.

Template values in the detailed procedures describe their documented examples.
Resolve scientific choices against the task and approved plan before execution;
do not treat an example, a timeout, or an unattended run as researcher approval.
Preserve explicitly fixed configurations. Record unresolved choices and continue
independent approved work, as described in the project instructions.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-epoch --section "Phase A — Event Extraction"
```

## Required Inputs

Before running, these must exist:

1. `ica-stage/` — cleaned continuous data per subject (`*-ica-raw.fif` or `*-clean-raw.fif`). **Stop if missing.**
2. `DATASET_BRIEF.md` — for condition codes/labels, event mapping, epoch window, baseline window.
3. `ANALYSIS_PLAN.md` — for exclusion criteria and minimum trial counts.
4. `ENVIRONMENT.json` — to resolve backend availability and `autoreject` installation.

## Critical Rules

- **Never** epoch before ICA cleaning. ICA should be applied to continuous data (eeg-ica stage), and epochs are cut from the cleaned continuous data.
- **Never** use too-short epochs that cut off the component of interest. The epoch must extend beyond the latest expected component peak (e.g., P600 requires at least 800 ms post-stimulus).
- **Never** use a baseline window that overlaps with the stimulus or a preceding stimulus in rapid designs. For SOA < 500 ms, consider a pre-trial baseline or no baseline.
- **Never** apply AutoReject and then also apply threshold rejection — choose one method.
- **Never** exclude subjects without documenting the reason in `EXCLUSION_REPORT.md`.
- **Never** set `MIN_TRIALS_PER_CONDITION` below 10 — at that point, ERP averages are unreliable for any component.
- **Never** silently change sampling rate or leave event samples on the old grid. Follow the approved stage: for Raw resampling, pass the existing events to `raw.resample(..., events=events)` and retain their identities; for epoch resampling, keep filtering edges outside the analyzed window. Integer epoch decimation requires prior continuous-data anti-alias filtering. See [MNE resampling guidance](https://mne.tools/stable/auto_tutorials/preprocessing/30_filtering_resampling.html#resampling).
- **Never** drop epochs silently. Every rejection must be logged and counted.
- **Never** baseline-correct fixed-length / resting-state epochs. With no event onset there is nothing to baseline against — use `baseline=None` (MNE `make_fixed_length_epochs` does this by default; EEGLAB `eeg_regepochs(..., 'rmbase', NaN)`). Apply baseline only to event-locked epochs.
- **Never** apply a fixed amplitude threshold before ICA. Pre-ICA, blinks and saccades make most frontal epochs exceed any reasonable threshold, so you discard neural trials that ICA could have salvaged. Threshold (or AutoReject) goes after ICA.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Event Extraction

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Epoch Creation

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Baseline Correction

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Artifact Rejection

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Trial Counting and Exclusion

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Save Outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Sanity Checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- **Inputs**: `ica-stage/*-clean-raw.fif`, `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, `ENVIRONMENT.json`
- **Outputs**: `epoch-stage/*-epo.fif`, `epoch-stage/*-reject-log.json`, `epoch-stage/EPOCH_PARAMS.json`, `epoch-stage/TRIAL_COUNT_TABLE.csv`, `epoch-stage/EXCLUSION_REPORT.md`
- **Next**: `eeg-erp` averages epochs into ERPs. `eeg-tfr` computes time-frequency from epochs. `eeg-spectral` runs PSD/Welch on epochs (especially the fixed-length resting-state epochs from Phase B — match Welch `n_per_seg` to the epoch duration; see the resolution = 1/duration rule). `eeg-stats` uses trial counts for power analysis.
- **Previous**: `eeg-ica` produces the cleaned continuous data consumed here.
