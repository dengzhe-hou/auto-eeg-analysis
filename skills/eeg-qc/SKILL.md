---
name: eeg-qc
description: "Automated EEG data-quality dashboard: per-channel SNR/variance/Hurst, PSD-based bad-channel and line-noise detection, flatline/high-amplitude flags, channel & epoch rejection-rate reporting, before/after SNR per pipeline stage, head-motion/EMG indices, and an overall QC report (mne.Report + JSON) with pass/warn/fail gates. Runs BEFORE analysis to catch bad data early. Backend: MNE-Python. Use when user says 'QC', 'data quality', 'quality check', 'is this data usable', 'check my recordings', or before committing to an analysis."
argument-hint: "[project-dir] [— stage: raw|preprocess|ica|epoch|all] [— gates: strict|normal|lenient] [— subjects: sub-01,...]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-qc: automated data-quality dashboard

## Context: $ARGUMENTS

Compute a per-subject, per-channel, per-stage quality report so bad data is caught **before** it costs analysis time. This skill does not clean data — it *measures* the data that `eeg-preprocess` / `eeg-ica` / `eeg-epoch` produced, scores it against published gates, and emits a pass/warn/fail verdict plus an `mne.Report` HTML and machine-readable JSON. It is diagnostic, not corrective: a `fail` here routes the user back to a preprocessing decision, never to a silent fix.

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
python tools/load_skill.py eeg-qc --section "Phase A — Inventory and plan"
```

## Required Inputs

QC adapts to whatever stages exist; at least one must be present.

1. `DATASET_BRIEF.md` — for line frequency, montage, expected channel count, paradigm (resting vs task). **Stop if it has `<…>` placeholders for the line freq or montage.**
2. `ENVIRONMENT.json` — to resolve MNE and check optional QC deps (`pyprep`, `autoreject`, `antropy`/`nolds`).
3. One or more stage directories:
   - `raw/` — raw recordings (for the pre-preprocess `raw` stage sanity pass).
   - `preprocess-stage/<sub>/*_preprocessed_raw.fif` + `preprocess_summary.json`.
   - `ica-stage/<sub>/*-clean-raw.fif` + `ica_labels.json`.
   - `epoch-stage/<sub>/*-epo.fif` + `*-reject-log.json`, `TRIAL_COUNT_TABLE.csv`.
4. Optional: `channel_mapping.json` (to report bad channels in 10-20 names), `ANALYSIS_PLAN.md` (for the analyzed-conditions list and seed).

## Critical Rules

- **Never** modify, re-reject, or re-reference upstream stage data — QC measures, it does not clean. A `fail` routes the user back to `eeg-preprocess`/`eeg-ica`/`eeg-epoch`; it never edits their outputs.
- **Never** call `find_bad_channels_maxwell` on scalp EEG — it is MEG-only (Maxwell/SSS + fine-cal/crosstalk). Use `find_bad_channels_lof` (+ pyprep RANSAC) for EEG.
- **Never** gate on a threshold that is not written to `QC_GATES.json` — hidden thresholds violate COBIDAS reproducibility.
- **Never** promote a low-amplitude warning to a bad channel, bad-time annotation or automatic exclusion. Keep constant and rapid-change duration thresholds independent; save the exact amplitude helper beside the generated program for replay.
- **Never** silently skip a metric when its optional backend is missing — record `not_computed (<reason>)` and log the substitution (House rule: no silent fallbacks). The dashboard must still run without `pyprep`/`autoreject`/`antropy`.
- **Never** try to ICA out or "correct" head-movement / saturation segments — they are uncorrectable; report them as bad-time and reject the segment (Luck 2014).
- **Never** report a single SNR number without stating its definition (spectral vs across-trial evoked) and the trial count it depends on — ERP SNR scales as `sqrt(N)`.
- **Never** interpret PSD content above the low-pass cutoff as signal when scoring channels — bins exist to Nyquist but are filter roll-off (`eeg-spectral`).
- **Never** flag a channel bad on a single detector when geometry-aware corroboration is available — require ≥2 detectors (LOF + RANSAC, or variance-z + spectral-z) before marking, to avoid over-interpolation.
- **Never** present a green QC verdict as evidence the *analysis* is valid — QC certifies data quality (inputs), not the statistical claims (that is `eeg-stats` + `eeg-audit`).
- **Never** baseline-correct or assume task structure when QC'ing resting-state data — use the continuous/fixed-length path and spectral SNR.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Inventory and plan

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Per-channel quality metrics (per subject, per stage)

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Before/after SNR per pipeline stage

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Per-subject summary metrics

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Group QC

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Pass / warn / fail gates

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG data-quality literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- **Inputs**: `DATASET_BRIEF.md`, `ENVIRONMENT.json`, `raw/`, `preprocess-stage/*_preprocessed_raw.fif` + `preprocess_summary.json`, `ica-stage/*-clean-raw.fif` + `ica_labels.json`, `epoch-stage/*-epo.fif` + `*-reject-log.json` + `TRIAL_COUNT_TABLE.csv`, `channel_mapping.json`, `ANALYSIS_PLAN.md` (seed).
- **Outputs**: `qc-stage/<sub>/qc_summary.json`, `qc-stage/<sub>/<stage>_channel_metrics.csv`, `qc-stage/<sub>/stage_snr_delta.json`, `qc-stage/QC_REPORT.html`, `qc-stage/GROUP_QC.csv`, `qc-stage/QC_GATES.json`, `qc-stage/QC_PLAN.json`, `FINDINGS.md` entry, heat-map/bar-chart figures.
- **Runs before analysis**: `eeg-qc` consumes the cleaning stages and gates the data *before* `eeg-erp`/`eeg-tfr`/`eeg-spectral`/`eeg-stats` invest compute on it.
- **Upstream stages it measures**: `eeg-preprocess` (channel interpolation, line noise, reference), `eeg-ica` (variance/components removed, residual EMG), `eeg-epoch` (`drop_log`, rejection rates, AutoReject). A `fail` routes back to the offending one.
- **Related**: `eeg-spectral` (shares the PSD/line-noise/EMG-ratio and SNR conventions; QC must not interpret above the LP cutoff), `eeg-complexity` (Hurst/DFA and the `H ≈ (β−1)/2` link to the 1/f slope), `eeg-report` (the *results* HTML report — `eeg-qc` is the complementary *quality* report, same `mne.Report` builder), `eeg-audit` (consumes `QC_GATES.json` and `GROUP_QC.csv` to verify quality gates and exclusions were reported per COBIDAS).
