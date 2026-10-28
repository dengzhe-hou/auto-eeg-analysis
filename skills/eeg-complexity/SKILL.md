---
name: eeg-complexity
description: "Compute EEG sample, approximate, permutation and multiscale entropy; Lempel-Ziv and spatial complexity; recurrence, scale-free dynamics and perturbation-gated PCI. Use when the approved task requests complexity or entropy, including a bounded SampEn calculation. Load the section for the requested metric. Produces per-channel values, windowed time courses or condition contrasts; metric-specific prerequisites remain in the procedure."
argument-hint: "[project-dir] [— metric: lzc|plzc|lzc_st|ace|sce|sampen|apen|pe|dispen|mse|rcmse|shannon|wavelet_en|hhse|rqa|dfa|lrtc|avalanche|pcist|spatial] [— window: 5] [— overlap: 3]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-complexity: nonlinear / entropy / complexity analysis

## Context: $ARGUMENTS

> **OPTIONAL skill.** Only run if `DATASET_BRIEF.md` (or `ANALYSIS_PLAN.md`) ticks Complexity / entropy / nonlinear dynamics / criticality / consciousness-depth tracking. If no complexity claim exists, **do not run** — return control to the dispatcher.
>
> **Every external library in this skill is an OPTIONAL dependency.** None of `antropy`, `neurokit2`, `EntropyHub`, `nolds`, `mne-features`, `pywt`, `PyEMD`/`emd`, `specparam`/`fooof` are guaranteed to be installed. **Every** code path MUST guard its import, log availability to the stage JSON, surface missing libs in `BACKEND_RESOLUTION.md`, and degrade gracefully (skip the metric with a clear message + `pip install` hint — never crash the stage). Only `numpy`/`scipy`/`scikit-learn`/`mne` are assumed present.

For a bounded SampEn request, the explicit task supplies the analysis plan.
Read [the segment procedure](references/sample-entropy.md) and the SampEn section in [the detailed procedure](references/procedure.md); do not invent an upstream stage or replace the requested segment with
this skill's sliding-window defaults.

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
python tools/load_skill.py eeg-complexity --section "Phase A — Metric selection and validation"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with the complexity/entropy claim(s). **Stop if missing or unfrozen.**
2. `DATASET_BRIEF.md` — must tick Complexity (otherwise this skill should not have been invoked); also gives the paradigm and condition labels (e.g. awake vs deep anesthesia, eyes-open vs eyes-closed).
3. Preprocessed data: `preprocess-stage/` or `ica-stage/` (continuous, for windowed time courses) or `epoch-stage/` (already-epoched).
4. `ENVIRONMENT.json` — to resolve which complexity backend is available.
5. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Critical Rules

- **Never** crash the stage on a missing optional library — guard every external import with `check_backend(...)`, log the skip, surface it in AUDIT, and continue with the available metrics.
- Record SampEn's tolerance, embedding positions, SD convention and radius
  boundary. A shared metric name alone does not establish numerical equivalence
  between implementations.
- **Never** compute `r` for SampEn/ApEn from a global SD — recompute it from each window's own SD, inside the window loop.
- **Never** normalize PLZC (or any >2-symbol LZC) with base 2 — the normalization base must be `m!`. Mismatched base silently produces uninterpretable values.
- **Never** compute LZC/PLZC/SampEn across channels — these are per-channel 1-D time-series metrics. Only spatial complexity (Omega/NSC) operates across channels.
- **Never** compare a complexity value across windows/conditions of different length — `c(n)`, RR, and entropy estimates all depend on `n`. Hold window length fixed.
- **Never** compute spatial complexity without an average reference first.
- **Never** report Shannon-amplitude or wavelet entropy without stating the (fixed) bin count / decomposition level — both are bin/level dependent.
- **Never** run DFA/Hurst/aperiodic-slope on short (≤5 s) entropy-sized windows — use ≥16 s windows; scaling exponents are unstable otherwise.
- **Never** call broadband DFA an LRTC/criticality measure — LRTC is DFA on the **narrow-band amplitude envelope** (band-pass → Hilbert → DFA); broadband DFA conflates the aperiodic 1/f slope with LRTC.
- **Never** recompute the SampEn tolerance `r` per scale in MSE — compute it once on the scale-1 SD and hold it fixed; on AEA's 5 s windows default to **RCMSE** (plain MSE is undefined at coarse scales).
- **Never** fit avalanche size/duration distributions by log-log least-squares — use maximum likelihood with a Clauset KS test, and bin at the mean inter-event interval (not an arbitrary bin width).
- **Never** run PCI/PCIst on spontaneous EEG — it is gated on a TMS/perturbation tick and operates on the evoked response.
- **Never** compare multichannel LZc/ACE/SCE across montages without per-subject phase-shuffled-surrogate normalization — raw values scale with channel count and spectral content.
- **Never** trust correlation dimension or Lyapunov exponents on short or noisy EEG without surrogate-data testing.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Metric selection and validation

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Windowing (shared helper for temporal metrics)

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Temporal entropy & Lempel-Ziv

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Recurrence Quantification Analysis (RQA)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Scale-free dynamics / criticality

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Spatial complexity (Omega / NSC / LCD)

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Outputs and sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG complexity / nonlinear-dynamics literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `DATASET_BRIEF.md`, `preprocess-stage/` / `ica-stage/` / `epoch-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `complexity-stage/<sub>/*-timecourse.npz`, `complexity-stage/<sub>/*-summary.json`, `complexity-stage/group/complexity_summary.csv`, `complexity-stage/BACKEND_RESOLUTION.md`, `complexity-stage/METRIC_SELECTION.md`, `FINDINGS.md`
- Related: `eeg-spectral` (aperiodic 1/f slope via specparam — shared scale-free path), `eeg-connectivity` (spatial complexity is a global-state complement to pairwise connectivity; multivariate nonlinear coupling / Synchronization Likelihood documented here), `eeg-tfr` (wavelet/HHT time-frequency), `eeg-decoding` (entropy/fractal/Hjorth features via `mne-features` feed the tabular feature matrix)
- Next: `eeg-stats` for group comparison of complexity values/time courses, `eeg-figure` for complexity time-course plots and topomaps, `eeg-methods-text` for the complexity paragraph, `eeg-recipe` for a ready "complexity-tracking" recipe (preprocess → average reference for spatial SC → windowed metrics → condition contrast)
