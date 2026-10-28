---
name: eeg-tfr
description: "Compute time-frequency representations (Morlet wavelets, multitaper, or Stockwell) and inter-trial coherence per subject per condition. Reads epoch-stage/ output. Backend: MNE-Python. Use when user says 'compute TFR', 'time-frequency', 'ERSP', 'wavelet', 'ITC', or after eeg-epoch completes."
argument-hint: "[project-dir] [— method: morlet|multitaper|stockwell] [— bands: theta,alpha,beta] [— baseline_mode: logratio|zscore|db|percent]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# eeg-tfr: epochs → time-frequency

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
python tools/load_skill.py eeg-tfr --section "Phase A — Parameter Resolution"
```

## Required Inputs

Before running, these must exist:

1. `epoch-stage/` — epoched data per subject (`*-epo.fif`). **Stop if missing.**
2. `DATASET_BRIEF.md` — for condition labels, frequency bands of interest, epoch window.
3. `ANALYSIS_PLAN.md` — if TFR claims exist, read frequency bands, time windows, and ROI from the claim table.
4. `ENVIRONMENT.json` — to resolve backend availability.

## Critical Rules

- **Never** use `percent` baseline mode without explicit user request and documented justification. `logratio`/`db` is the field standard (Grandchamp & Delorme 2011).
- **Never** baseline-correct a condition contrast — baseline each condition separately first, then subtract.
- **Never** ignore edge artifacts. Check the longest sampled wavelet against epoch length, and check the reporting/baseline margins against its half-support. Record insufficient input support before changing any resolved analysis parameter.
- **Never** compute ITC on averaged data — ITC requires single-trial complex estimates.
- **Never** interpret ITC magnitude without considering trial count — ITC is biased upward with fewer trials. Report trial count alongside ITC.
- **Never** describe ITPC/ITLC as connectivity or as power. ITPC/ITLC is **single-channel, across-trial** phase consistency (evoked phase-locking / phase resetting): it collapses the *trial* axis of *one* channel and discards (ITPC) or amplitude-weights (ITLC) magnitude. Inter-channel phase coupling (PLV/PLI/wPLI/coherence) is a different measure — see `eeg-connectivity` — and power is the squared magnitude, not a phase quantity.
- **Never** set `n_cycles` too high for low frequencies (e.g., 10 cycles at 2 Hz = 5 s wavelet — longer than most epochs).
- **Never** change `DECIM` after computation to match a claim's time resolution — recompute if needed.
- **Never** report or run statistics on TFR coefficients that require samples outside the input epoch. Crop the maximum sampled half-support, approximately `max(5*n_cycles/(2*pi*freqs))` seconds, from each edge for a common analysis window; use the exact sample count where available.
- **Never** apply `apply_hilbert` to broadband data — the analytic signal is only meaningful after band-pass filtering into a single band.
- **Never** present an uncorrected pixel-wise p-map as a result; it is a visualization aid only — correct via cluster permutation or FDR.
- **Never** report induced gamma/high-frequency (>30 Hz) power without an eye-tracker/radial-EOG microsaccade reject and a HF-topography QC — the saccadic spike potential and cranial EMG survive standard ICA and masquerade as induced gamma (Yuval-Greenberg et al. 2008; Hipp & Siegel 2013).
- **Never** label a total-power ERSP/ERDS map "induced" — total power still contains the evoked response. Subtract the average ERP per trial first (and verify low latency jitter), or report total power + ITC (Kalcher & Pfurtscheller 1995; Yeung et al. 2004).
- **Never** treat dB/logratio baseline as assumption-free: it assumes a multiplicative oscillation/aperiodic relationship, so a baseline or condition difference in 1/f can produce a spurious narrowband effect — remove/parameterize the aperiodic component or use additive baseline with 1/f as a covariate (Gyurkovics et al. 2021).


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Parameter Resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend Resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-Subject TFR Computation

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Baseline Correction

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Inter-Trial Coherence (ITC)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — ERDS Maps

Read this section in [the detailed procedure](references/procedure.md).

## Phase F2 — Standard TFR figure trio (preview/QC)

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Output Files

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Sanity Checks

Read this section in [the detailed procedure](references/procedure.md).

## Phase H2 — Time-frequency statistics hand-off

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- **Inputs**: `epoch-stage/*-epo.fif`, `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, `ENVIRONMENT.json`
- **Outputs**: `tfr-stage/*-tfr.h5`, `tfr-stage/*-itc.h5`, `tfr-stage/*-erds-bands.csv`, `tfr-stage/TFR_PARAMS.json`, `tfr-stage/TFR_SUMMARY.md`, `tfr-stage/BACKEND_RESOLUTION.md`
- **Next**: `eeg-stats` reads TFR outputs for cluster permutation on time-frequency data. `eeg-figure` reads TFR for ERSP/ITC plots and topographic ERDS maps. `eeg-methods-text` reads `TFR_PARAMS.json` for the methods paragraph.
- **Previous**: `eeg-epoch` produces the epoched data consumed here.
