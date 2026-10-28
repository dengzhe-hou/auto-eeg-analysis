---
name: eeg-ica
description: "Fit ICA per subject and auto-label components (eye/muscle/heart/line/channel-noise) for rejection. Reads preprocess-stage/ output. Backend: MNE-Python + mne-icalabel. Use when user says 'run ICA', 'remove artifacts', 'artifact rejection', 'ICA decomposition', 'ICLabel', or after preprocessing completes."
argument-hint: "[project-dir] [— method: infomax|picard|fastica] [— n_components: 0.99|25|rank] [— threshold: 0.7] [— manual-review: sub-01,sub-03] [— hp-freq: 1.0]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-ica: ICA + automated component labeling

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
python tools/load_skill.py eeg-ica --section "Phase A — Resolve parameters"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with ICA parameters specified. **Stop if missing or unfrozen.**
2. `preprocess-stage/` — preprocessed continuous data per subject (`.fif`, `.set`, or `.mat`).
3. `ENVIRONMENT.json` — to resolve backend and available packages.
4. `channel_mapping.json` — if needed for consistent channel labeling.

## Critical Rules

- **Never** fit ICA on the analysis bandpass data directly. Always use a 1 Hz (or higher) high-pass filtered copy for fitting (Winkler et al. 2015).
- **Never** apply ICA to the filtered copy. Always apply the ICA solution to the original analysis-bandpass data.
- **Never** auto-reject components labeled `"brain"` or `"other"` by ICLabel. Brain components are signal; other components need manual inspection.
- **Never** lower the confidence threshold to reject more components post-hoc. If artifacts remain, re-examine preprocessing or add subjects to manual review.
- **Never** change the ICA seed after inspecting results. The seed must be set before any ICA is run.
- **Never** run ICA without setting a random seed. Reproducibility requires a fixed seed.
- **Never** fit ICA on epoched data unless explicitly justified (continuous data is standard for EEG ICA) — **except** when the ISI is irregular or short/messy, where you should epoch FIRST and fit ICA on the concatenated epochs so the decomposition models task structure rather than inter-trial junk.
- **Never** expect ICA to remove slow drift or line noise — those must be filtered/notched out in `eeg-preprocess` BEFORE ICA. ICA only separates stationary linear sources; feeding it drift or line noise corrupts the decomposition and wastes components.
- **Never** fit ICA before bad-segment deletion + bad-channel interpolation are done in the same pre-ICA pass — leftover transient excursions hijack the decomposition, and un-accounted interpolated channels break the rank (reduce `n_components` by `n_interpolated`).
- **Never** apply a tight peak-to-peak amplitude reject (~±60 µV) before ICA. Use a loose pass pre-ICA (extreme segments only) and reserve the tight pass for AFTER artifact-IC removal (`eeg-epoch`) — otherwise you discard trials ICA could have cleaned.
- **Never** skip reporting the number of excluded components per class. Reviewers need this information.
- **Never** reject a borderline component just to be thorough — when in doubt, KEEP it. Over-rejection wipes out neural signal: removing a single mislabeled frontal IC can destroy part of the ERP (Chaumon et al. 2015). Prefer correction of stereotyped artifacts over trial rejection, and reserve component removal for clear artifacts confirmed by both ICLabel and a `find_bads_*` cross-check or `ica.plot_overlay`.
- **Never** finalize a borderline exclusion without previewing its effect. Run `ica.plot_overlay(raw, exclude=[idx])` (or compare the evoked before/after) and only exclude if the overlay shows clear data improvement without flattening the ERP of interest.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Resolve parameters

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-subject ICA fitting

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Manual review handling

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Apply ICA and write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `preprocess-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `ica-stage/*_ica.fif`, `ica-stage/*/ica_labels.json`, `ica-stage/*_cleaned_raw.fif`, `ica-stage/ICA_REPORT.md`, `ica-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Previous: `eeg-preprocess` produces the input data. `eeg-ica` should run after preprocessing and before epoching.
- Next: `eeg-epoch` reads cleaned continuous data. `eeg-erp` and `eeg-tfr` stages use ICA-cleaned data. `eeg-audit` verifies ICA parameters match the plan. `eeg-methods-text` reads ICA_REPORT.md for the methods paragraph.
