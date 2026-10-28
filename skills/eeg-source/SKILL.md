---
name: eeg-source
description: "Source localization: scalp EEG → cortical/dipole sources via boundary-element model (BEM), MNE/dSPM/sLORETA/eLORETA, or beamformer. Default head model fsaverage (template); individual MRI requires FreeSurfer. Brainstorm export-only path supported. Use when the user wants to identify intracranial generators of scalp signals."
argument-hint: "[project-dir] [— head-model: fsaverage|individual] [— inverse: dspm|sloreta|eloreta|mne|lcmv]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-source: scalp → cortical sources

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
python tools/load_skill.py eeg-source --section "Phase A — Pre-flight platform check"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen. **Stop if missing or unfrozen.**
2. `epochs-stage/` — cleaned, epoched `.fif` files per subject per condition (for evoked source estimation).
3. `ENVIRONMENT.json` — to resolve backend.
4. (If `individual`): FreeSurfer `subjects_dir` with completed `recon-all` output per subject.
5. (If `individual`): Digitized electrode positions or fiducials (`.elp`, `.hsp`, or embedded in `.fif` info).

## Critical Rules

- **Never** use a 1-layer BEM for EEG — EEG requires 3 layers (brain, skull, scalp). 1-layer is only acceptable for MEG.
- **Never** interpret source localization results with millimeter precision — EEG source localization has centimeter-scale accuracy at best, even with individual MRI.
- **Never** compare absolute source amplitudes across subjects without normalization (dSPM/sLORETA provide this; raw MNE does not).
- **Never** skip coregistration verification — misaligned electrodes produce systematically biased source estimates.
- **Never** use LCMV beamformer for correlated sources (e.g., bilateral auditory cortex activation) — beamformers suppress correlated sources by design.
- **Never** run a beamformer (LCMV/DICS) on non-average-referenced EEG — a forward-model error at the reference electrode contaminates all channels. Set `set_eeg_reference('average', projection=True)` first, and never drop channels afterward.
- **Never** estimate a separate spatial filter per condition when contrasting conditions — build ONE filter on pooled data and apply it to each condition; otherwise the filter itself encodes the condition difference and biases the contrast.
- **Never** compute the forward solution before verifying coregistration with `plot_alignment` — the BEM surfaces, source space, and montage must share one coordinate frame and one unit (mm) or the leadfield is silently wrong.
- **Never** claim voxel-precise peaks from a template BEM with template electrode positions — report coarse lobar/ROI/network-level localization only (see Domain Knowledge).
- **Never** change SNR/lambda2 to make results "look better" — use the pre-registered value.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Pre-flight platform check

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Forward model construction

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Noise covariance estimation

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Inverse operator and source estimation

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — ROI extraction

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from source localization methodology literature)

Read this section in [the method background](references/background.md).

## Platform-specific gotchas

Read this section in [the detailed procedure](references/procedure.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epochs-stage/`, `ENVIRONMENT.json`, FreeSurfer `subjects_dir` (optional)
- Outputs: `source-stage/*-stc.h5`, `source-stage/*-roi_ts.npz`, `source-stage/forward/*-fwd.fif`, `source-stage/covariance/*-cov.fif`, `source-stage/SOURCE_PARAMS.json`, `source-stage/PLATFORM_CHECK.md`, `FINDINGS.md`
- Next: `eeg-connectivity` can use ROI time courses for source-space connectivity. `eeg-stats` for statistical comparison of source estimates. `eeg-figure` for cortical surface plots. `eeg-methods-text` for the source localization paragraph.
- Source-space statistics: contrast source estimates with `mne.stats.spatio_temporal_cluster_1samp_test` (paired/within-subject) or `spatio_temporal_cluster_test`, using source-space adjacency `mne.spatial_src_adjacency(src)`, ≥1000 permutations, and a two-tailed threshold (the course convention is alpha = 0.025 per tail = 0.05 overall). When whole-brain cluster tests are underpowered, reduce to ROI time courses (`extract_label_time_course` over an atlas) and run ROI-wise paired t-tests with FDR/Bonferroni correction across ROIs. (Detailed protocol in `eeg-stats`.)
