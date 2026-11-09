---
name: eeg-preprocess
description: "Preprocess raw EEG according to the approved analysis plan: filtering, reference, bad channels and line noise. Also use for explicitly bounded channel/filter/export tasks and population-SD global field power (GFP) with peak times. Preserve the requested channels, operation order, units and outputs."
argument-hint: "[project-dir] [— subjects: sub-01,sub-02,...]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-preprocess: Raw → preprocessed EEG

Canonical sample skill for AEA. Mirrors ARIS skill structure: Constants → Inputs → Phases → Output → Errors.

## Context: $ARGUMENTS

## Use this skill

Read the task and approved plan, then select only the matching procedure.
For a bounded calculation, go directly to these sections:

- [Bounded preprocessing](references/bounded.md#bounded-preprocessing): translate
  approved steps, preserve their order and use a fresh input copy after errors.
- [Population global field power](references/bounded.md#population-global-field-power):
  preserve the approved buffer and compute absolute peak times.
- [Result status and inference limits](references/bounded.md#result-status-and-inference-limits):
  distinguish missing source data, supported calculations and unsupported inference.
- [Public artifact self-check](references/bounded.md#public-artifact-self-check):
  save actual outputs and check the processing, arrays and final JSON at the declared scope.

The full-study stages below apply when that workflow is requested. Their example
values add no processing step or scientific default to a bounded task. Preserve
fixed settings; record unresolved scientific choices and continue independent
approved work. A timeout or unattended run supplies no additional approval.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-preprocess --section "Bounded preprocessing"
```

For an approved bounded MNE GFP, Welch or Hilbert plan, the
[continuous-plan runner](../../docs/PRELOADED_SKILLS.md#execute-and-check-a-complete-continuous-plan)
executes its ordered operations and saves actual metadata and a checked final
JSON object. This route adds no scientific defaults.

## Required inputs

For a bounded channel/filter/export/GFP request, the supplied Raw or recording
and resolved task/plan provide the inputs. Preserve documented channel roles,
units, interval, operation order and output requirements; do not construct
unrequested full-study directories.

For a full study, the following must exist in the project directory:

1. `DATASET_BRIEF.md` — auto-generated via `tools/auto_brief.py` or manually filled. Resolve scientific choices against the approved plan. For an explicitly bounded request, its supplied public plan can provide these inputs; do not invent a new study brief or adopt example filter/reference values.
2. `ENVIRONMENT.json` — produced by `tools/env/check_env.{sh,ps1}`. Run the probe if missing.
3. `raw/` — directory with subject files (`.bdf`/`.set`/`.edf`/`.fif`/`.vhdr`).

## Critical Rules

- **Never** change the preprocessing order without justification. Filter → detect bads → interpolate → re-reference is the canonical order (Robbins et al. 2020).
- **Never** use a highpass >0.1 Hz for the final ERP data without documenting the rationale (risk of filter artifacts in baseline, Tanner et al. 2015).
- **Never** use causal (single-pass) filters for offline analysis — they introduce phase distortion and asymmetric temporal smearing.
- **Never** apply ICA in this stage — ICA belongs in `eeg-ica`. This stage only prepares data for ICA (1 Hz highpass copy if needed).
- When line-noise removal is approved, use its actual frequency and method; a lowpass does not establish that the specified operation was performed. Bounded tasks receive only their approved operations.
- **Never** use a lowpass below 20 Hz for ERP data — it distorts component morphology.
- **Never** include EOG/ECG/EMG/mastoid channels in an `average` reference — set their channel types (or drop them) first, or they leak into every scalp channel.
- **Never** silently change the planned sampling rate or downsampling stage. Raw resampling affects event-time precision; epoch resampling requires edge-effect precautions, and decimation requires prior anti-alias filtering.
- **Never** choose ICA dimensionality without accounting for the actual reference, interpolation and effective rank. Record `n_interpolated`, `avg_ref_applied` and projection state; a signal-derived rank already includes those dependencies and must not have them subtracted again.
- **Never** try to ICA out a transient all-channel excursion (head movement, swallow) — annotate it `'bad'` and reject the segment; ICA is for spatially-stationary sources (blinks, EOG, cardiac, EMG elsewhere).
- **Never** change the approved reference order or apply a decomposition to a different channel/reference configuration. Record whether average reference is applied or only a pending projector, and use the corresponding effective rank.
- A FIR parameter table or spectral integration band does not authorize a filter. Keep the approved processing order and do not add a notch or bandpass to an analysis that does not request it.
- **Never** decimate or slice samples without appropriate prior anti-alias filtering. Do not confuse this with MNE `resample`, which includes its own anti-alias filter.
- **Never** re-filter already-baselined epochs without re-running baseline correction — filtering reshapes the baseline window and invalidates the prior correction (prefer finalizing all filtering on continuous `Raw` before epoching).


## Procedure reference

Use the [bounded processing/export helpers](scripts/continuous.py) to select
the actual analysis subset, preserve SI units and reopen exported EDF files.

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

Before an average reference or an EEG-only channel ranking, read
[Channel identity and actual analysis picks](references/channel-identity.md).
Use the bundled [channel checker](scripts/check_channels.py) with the recording's
documented identities and the approved channel set. Reader-default EEG labels
alone are not evidence of scalp identity.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Plan

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-subject execution

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Aggregate summary

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Sanity checks before signaling success

Read this section in [the detailed procedure](references/procedure.md).

## Error handling

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG methodology literature)

Read this section in [the method background](references/background.md).

## Cross-references

- Inputs: `DATASET_BRIEF.md`, `ENVIRONMENT.json`, `ANALYSIS_PLAN.md` (for seed)
- Next stage: `eeg-ica` reads `preprocess-stage/<sub>/<sub>_preprocessed_raw.fif` and **uses `n_interpolated` + `avg_ref_applied` from `preprocess_summary.json` to set `ICA(n_components=...)`** (fit on a 1 Hz-highpass copy, apply to the 0.1 Hz data).
- `eeg-epoch` consumes the `'bad_*'` annotations written here via `reject_by_annotation=True`; amplitude-based peak-to-peak rejection (~100 µV, tightened for clean data) is applied there, AFTER ICA.
- `eeg-connectivity` may apply `compute_current_source_density()` (this skill's optional CSD transform) before sensor-space FC to reduce volume conduction.
- Audit: `eeg-audit` checks that the bandpass and reference recorded in `preprocess_summary.json` match what `DATASET_BRIEF.md` declared.
