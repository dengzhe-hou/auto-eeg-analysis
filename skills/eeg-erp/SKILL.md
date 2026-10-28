---
name: eeg-erp
description: "Compute ERPs (evoked responses) per condition per subject; export grand averages, GFP (global field power), difference waves, and per-condition .fif evoked files for the figure and stats stages. Measures component amplitudes and latencies per ANALYSIS_PLAN. Reads epoch-stage/ output. Use when user says 'compute ERPs', 'average epochs', 'ERP components', or after epoch-stage completes."
argument-hint: "[project-dir] [— conditions: valid,invalid] [— measure: mean_amp|peak|area_latency] [— components: N1,P3b,N400]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-erp: epochs → evoked

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
python tools/load_skill.py eeg-erp --section "Phase A — Parse conditions and components"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `epoch-stage/` — cleaned epochs per subject (`.fif` or `.set`).
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Critical Rules

- **Never** measure a component not specified in ANALYSIS_PLAN (unless `— exploratory` is passed).
- **Never** choose time windows or ROI channels based on the grand average — this is circular (Luck & Gaspelin 2017). Use pre-registered or literature-based windows.
- **Never** use peak amplitude as the sole measure for broad components (P3b, N400, LPP). Use mean amplitude.
- **Never** report peak latency from noisy data — use fractional area latency instead (Luck 2014).
- **Never** confuse the grand average difference wave (for display) with subject-level difference waves (for statistics).
- **Never** average across subjects before a cluster/ANOVA test — retain the per-subject array (FieldTrip `keepindividual='yes'`); collapsing first destroys the variance the test needs.
- **Never** select the time window or ROI from a data-driven test and then report a fixed-window test inside it as pre-registered — that is the circular window problem (Luck & Gaspelin 2017). Pre-register the window (Route A) or report the cluster-corrected result (Route B).
- **Never** average a contrast whose conditions have very unequal trial counts without equalizing (`equalize_event_counts`) or reporting the imbalance — the difference wave is biased toward the noisier condition.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Parse conditions and components

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-subject averaging

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Component measurement

Read this section in [the detailed procedure](references/procedure.md).

## Phase D.5 — Group statistics strategy (hypothesis-driven vs data-driven)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Grand averages and difference waves

Read this section in [the detailed procedure](references/procedure.md).

## Phase E.5 — Regression ERP (rERP) with overlap deconvolution (optional)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from ERP methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epoch-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `erp-stage/*-ave.fif`, `erp-stage/grand_average/`, `erp-stage/component_measures.csv`, `erp-stage/peak_table.csv`, `erp-stage/ERP_PLAN.json`, `erp-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-stats` reads evoked files and the per-subject metric arrays from this stage — hand it Route-A subject values (paired t-test / `mne.stats.f_mway_rm` for factorial designs) or the per-subject arrays for Route-B cluster permutation ('when'/'where'). `eeg-figure` reads grand averages and the mean±SEM band for plots. `eeg-audit` verifies measurements and trial counts match the plan. For topographic segmentation of evoked data (ERP microstates), see `eeg-microstate` (polarity-aware, all-timepoints mode — distinct from resting defaults).
