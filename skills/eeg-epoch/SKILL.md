---
name: eeg-epoch
description: "Create event-locked or fixed-length EEG epochs and apply the approved baseline, rejection and inclusion policy. Supports continuous ICA before epoching, approved epoch-first ICA, and analyses without ICA. Backend: MNE-Python. Use for 'epoch', 'segment', 'create epochs' or 'trial rejection'."
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

## Approved ERP execution

For a resolved ERP plan, read [approved ERP execution](references/approved-erp.md#approved-erp-execution).
This includes integer-sample epoch timing and saving computed artifacts before
additional checks. Load [ERP CORE response coding](references/approved-erp.md#erp-core-response-coding)
only for that dataset's error-minus-correct contrast, and
[approved ERP group statistics](references/approved-erp.md#approved-erp-group-statistics)
only for participant-level group tasks. Callable helpers are in `scripts/erp.py`.

## Required Inputs

Use the input selected by the approved task/plan, not a mandatory ICA directory:

1. Continuous ICA first: cleaned Raw from `ica-stage/`.
2. Epoch-first ICA: preprocessed Raw for the initial cut; cleaned Epochs from
   `ica-stage/` for finalization. Do not cut the cleaned epochs a second time.
3. No ICA: the supplied preprocessed Raw.

Resolve event mapping, window or duration, baseline and its stage, projection,
rejection and participant-inclusion rules from the approved task/plan. Record
them in `EPOCH_PARAMS.json`. For a bounded request, supplied data and explicit
settings suffice; do not invent a full-study prerequisite. Check environment
availability only for the selected method.

## Critical Rules

- Follow the approved ICA domain and ordering. Short/irregular ISI alone does not authorize changing between continuous and epoch-first ICA; see [the handoff](references/procedure.md#constants).
- **Never** use too-short epochs that cut off the component of interest. The epoch must extend beyond the latest expected component peak (e.g., P600 requires at least 800 ms post-stimulus).
- **Never** use a baseline window that overlaps with the stimulus or a preceding stimulus in rapid designs. For SOA < 500 ms, consider a pre-trial baseline or no baseline.
- Apply only the rejection steps approved for this stage. Do not append a second rejection method or substitute a missing dependency with a threshold.
- **Never** exclude subjects without documenting the reason in `EXCLUSION_REPORT.md`.
- Report actual retained trials and apply only the approved flag/exclusion rule. There is no universal trial-count cutoff for every component or score.
- **Never** silently change sampling rate or leave event samples on the old grid. Follow the approved stage: for Raw resampling, pass the existing events to `raw.resample(..., events=events)` and retain their identities; for epoch resampling, keep filtering edges outside the analyzed window. Integer epoch decimation requires prior continuous-data anti-alias filtering. See [MNE resampling guidance](https://mne.tools/stable/auto_tutorials/preprocessing/30_filtering_resampling.html#resampling).
- **Never** drop epochs silently. Every rejection must be logged and counted.
- Apply baseline correction only at its approved stage and record it once. Fixed-length helper output has no baseline correction; do not add one implicitly.
- Keep pre-ICA segment handling separate from post-ICA rejection. Both thresholds and their definitions (peak-to-peak versus signed amplitude) must be approved; neither a numerical example nor a slow run authorizes tightening them.


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

- **Inputs**: approved Raw/Epochs input, event mapping and analysis settings; full studies also use `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, `ENVIRONMENT.json`.
- **Outputs**: `epoch-stage/*-epo.fif`, `epoch-stage/*-reject-log.json`, `epoch-stage/EPOCH_PARAMS.json`, `epoch-stage/TRIAL_COUNT_TABLE.csv`, `epoch-stage/EXCLUSION_REPORT.md`
- **Next**: `eeg-erp` averages epochs into ERPs. `eeg-tfr` computes time-frequency from epochs. `eeg-spectral` runs PSD/Welch on epochs (especially the fixed-length resting-state epochs from Phase B — match Welch `n_per_seg` to the epoch duration; see the resolution = 1/duration rule). `eeg-stats` uses trial counts for power analysis.
- **Previous / handoff**: preprocessing or ICA according to the approved route. Save epoch-first fitting inputs as `*-preica-epo.fif`, retain ICA-cleaned epochs, and finalize `*-epo.fif` without overwriting the pre-ICA input.
