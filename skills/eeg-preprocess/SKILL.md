---
name: eeg-preprocess
description: "Filter, re-reference, detect bad channels, remove line noise on raw EEG. Reads DATASET_BRIEF.md to set defaults, ENVIRONMENT.json to verify MNE-Python. Writes per-subject preprocessed .fif under preprocess-stage/. Use when the user says \"预处理 EEG\", \"preprocess my EEG data\", \"clean the raw EEG\", or starts a new study from raw recordings."
argument-hint: "[project-dir] [— subjects: sub-01,sub-02,...]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-preprocess: Raw → preprocessed EEG

Canonical sample skill for AEA. Mirrors ARIS skill structure: Constants → Inputs → Phases → Output → Errors.

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
python tools/load_skill.py eeg-preprocess --section "Phase A — Plan"
```

## Required inputs

Before running, the following must exist in the project directory:

1. `DATASET_BRIEF.md` — auto-generated via `tools/auto_brief.py` or manually filled. Critical `[USER]` fields (paradigm, conditions) must be resolved. Non-critical fields with defaults (bandpass, reference) can proceed with defaults — note in the preprocess plan.
2. `ENVIRONMENT.json` — produced by `tools/env/check_env.{sh,ps1}`. Run the probe if missing.
3. `raw/` — directory with subject files (`.bdf`/`.set`/`.edf`/`.fif`/`.vhdr`).

## Critical Rules

- **Never** change the preprocessing order without justification. Filter → detect bads → interpolate → re-reference is the canonical order (Robbins et al. 2020).
- **Never** use a highpass >0.1 Hz for the final ERP data without documenting the rationale (risk of filter artifacts in baseline, Tanner et al. 2015).
- **Never** use causal (single-pass) filters for offline analysis — they introduce phase distortion and asymmetric temporal smearing.
- **Never** apply ICA in this stage — ICA belongs in `eeg-ica`. This stage only prepares data for ICA (1 Hz highpass copy if needed).
- **Never** skip line noise removal and assume the lowpass will handle it — harmonics and spectral leakage can persist.
- **Never** use a lowpass below 20 Hz for ERP data — it distorts component morphology.
- **Never** include EOG/ECG/EMG/mastoid channels in an `average` reference — set their channel types (or drop them) first, or they leak into every scalp channel.
- **Never** silently change the planned sampling rate or downsampling stage. Raw resampling affects event-time precision; epoch resampling requires edge-effect precautions, and decimation requires prior anti-alias filtering.
- **Never** choose ICA dimensionality without accounting for the actual reference, interpolation and effective rank. Record `n_interpolated`, `avg_ref_applied` and projection state; a signal-derived rank already includes those dependencies and must not have them subtracted again.
- **Never** try to ICA out a transient all-channel excursion (head movement, swallow) — annotate it `'bad'` and reject the segment; ICA is for spatially-stationary sources (blinks, EOG, cardiac, EMG elsewhere).
- **Never** change the approved reference order or apply a decomposition to a different channel/reference configuration. Record whether average reference is applied or only a pending projector, and use the corresponding effective rank.
- **Never** skip the notch even when the low-pass is below the line frequency — the LP transition band/ringing and harmonics can leave a residual 50/60 Hz peak; always run `notch_filter()` after the band-pass.
- **Never** decimate or slice samples without appropriate prior anti-alias filtering. Do not confuse this with MNE `resample`, which includes its own anti-alias filter.
- **Never** re-filter already-baselined epochs without re-running baseline correction — filtering reshapes the baseline window and invalidates the prior correction (prefer finalizing all filtering on continuous `Raw` before epoching).


## Procedure reference

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
