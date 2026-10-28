---
name: eeg-microstate
description: "Fit modified k-means microstate templates on EEG (or apply published templates), segment data per condition, compute coverage / GEV / mean duration / occurrence / transition matrix. Backend: pycrostates (Python)."
argument-hint: "[project-dir] [— k: 4|5|6] [— template: published|fit-here]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-microstate: scalp microstate analysis

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
python tools/load_skill.py eeg-microstate --section "Phase A — Data preparation"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen. **Stop if missing or unfrozen.**
2. `epochs-stage/` or `clean-stage/` — cleaned continuous or epoched EEG (`.fif`). Continuous preferred for microstate analysis.
3. `ENVIRONMENT.json` — to resolve backend.

**Preconditions (check before fitting; warn/abort if unmet):**
- **>= 20 EEG channels with montage positions** for full-head coverage. Lower-density arrays (19 or even 8 ch) still recover duration/frequency/coverage reliably (Khanna 2014, α 0.87–0.91), but **flag that maps C and D are less consistent** at low density.
- **>= 180 s of clean, average-referenced, artifact-free data** per recording (warn below ~120 s; Khanna used ~128 s, range 80–204 s). Bad channels must be interpolated or removed first.
- **Prefer group / global templates over per-recording fitting.** Per-recording (individual) template fitting is the *least* reliable strategy (Khanna 2014, Cronbach α ≈ 0.52 vs ≈ 0.81 for global maps).
- **Ocular ICA removal is mandatory before clustering, not optional.** Residual eye-movement/blink activity destabilizes the cluster-validity criteria (so K selection becomes unreliable) and distorts the resulting topographies. Removing the ocular ICs is the step that matters; aggressive "keep brain-ICs-only" cleaning beyond that adds little. Treat upstream EOG-component rejection as a hard precondition and abort/warn if `clean-stage` was produced without it. Cite: Artoni & Michel (2025), Brain Topogr. 38:28.

## Critical Rules

- **Resting microstate defaults (GFP-peak selection, polarity-invariant modified k-means, no smoothing during clustering) do NOT apply to ERP / event-locked data.** Topographic ERP microstate segmentation is a distinct, well-established method — do not blanket-forbid it. For evoked data: cluster on **all time points** of the grand-average Evoked (not GFP peaks), use **polarity-aware standard k-means** (Euclidean), and **smooth at the segmentation step** (timepoints are time-ordered). ERP microstate classes map to ERP component latency windows, not the canonical A–D. See `eeg-erp` and Murray et al. 2008 (TANOVA, GFP, topographic segmentation).
- **Never** compare microstate parameters across studies with different K values.
- **Never** skip GFP-peak extraction and fit on all time points — this inflates GEV and produces unstable maps.
- **Never** interpret microstate labels (A, B, C, D) as fixed neural generators without verifying topographic similarity to published canonical maps.
- **Never** use transition probabilities without testing against a Markov null model (random transitions given observed coverage) — but note that resting sequences empirically *fail* the first-order Markov property (von Wegner & Laufs 2018), so treat this null as an approximation and prefer entropy-rate / autoinformation summaries for the full dynamics.
- **Never** report transition probabilities as a standalone longitudinal biomarker — they are the least reliable parameter (ICC often < 0.50); base biomarker claims on duration / occurrence / coverage (Kleinert et al. 2023).


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Data preparation

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Clustering (Fit phase)

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Template alignment

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Segmentation (Back-fitting)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Compute microstate parameters

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG microstate methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `clean-stage/` or `epochs-stage/`, `ENVIRONMENT.json`
- Outputs: `microstate-stage/*-microstate_params.json`, `microstate-stage/group/group_template_maps.npz`, `microstate-stage/group/group_params_summary.csv`, `microstate-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-stats` for statistical comparison of microstate parameters between conditions (paired t / cluster perm on transition matrices). `eeg-figure` for topographic map plots and temporal segmentation visualization. For source-level microstates (rare), invoke after `eeg-source`.
