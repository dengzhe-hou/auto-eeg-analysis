---
name: eeg-group-compare
description: "Second-level (across-subject) group statistics: group grand-averages with CIs, between/within-group spatio-temporal cluster permutation, repeated-measures/mixed ANOVA, TFCE, effect sizes (Cohen's d / partial eta-squared) with CIs, and forest plots. Handles unequal N and covariates. Use when user says 'compare groups', 'between-group stats', 'patients vs controls', 'mixed ANOVA', 'rmANOVA', 'second-level', 'forest plot', or 'effect size with CI'."
argument-hint: "[project-dir] [— design: between|within|mixed] [— groups: patient,control] [— test: cluster|anova|tfce] [— perms: 5000]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-group-compare: second-level group statistics

## Context: $ARGUMENTS

Population-level inference across subjects: tests whether condition or group effects generalize beyond the sampled participants. This is the **second level** of a hierarchical analysis — first-level (within-subject) summaries (per-subject ERPs/TFRs/band power) become the observations, and the test treats subject as the random effect. Trial-level (N=1) tests support claims about *that subject's data*, never about the population (Holmes & Friston 1998). Where `eeg-stats` runs the single per-claim cluster test, this skill is the broader toolkit for between/within/mixed designs, factorial models, effect sizes with CIs, and unequal-N / covariate handling.

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
python tools/load_skill.py eeg-group-compare --section "Phase A — Parse design and assemble the second-level array"
```

## Required Inputs

1. `ANALYSIS_PLAN.md` — frozen, with the claim table and group/design columns filled. **Stop if missing or unfrozen.**
2. First-level per-subject outputs: `erp-stage/<sub>/<sub>-ave.fif`, `tfr-stage/<sub>/<sub>-tfr.h5`, or `spectral-stage/<sub>/band_power.json` — one summary per subject per condition.
3. `group_membership.csv` (for between/mixed) — columns `subject, group[, covariate1, ...]`. **Stop if a between-group design has no membership file.**
4. `ENVIRONMENT.json` — to resolve `mne` and detect `statsmodels` / `pingouin`.
5. `channel_mapping.json` — if the plan's ROI uses 10-20 names but data uses numbered channels.

## Critical Rules

- **Never** treat trials as the observation unit for a group claim. The first array dimension must be subjects (Holmes & Friston 1998).
- **Never** report cluster boundaries as precise onset/offset or a single "significant electrode" (Sassenhagen & Draschkow 2019).
- **Never** run a between-group `_1samp` test or a within `spatio_temporal_cluster_test` — match the function to the design.
- **Never** use balanced-only `AnovaRM` on unequal-N or covariate data — switch to `MixedLM`.
- **Never** report a p-value without a standardized effect size and its CI.
- **Never** change `n_permutations`, seed, ROI, or window after seeing results, and never silently fall back from `pingouin`/`statsmodels` without logging it.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Parse design and assemble the second-level array

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Group grand-averages with confidence intervals

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Spatio-temporal cluster permutation (the nonparametric workhorse)

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Factorial / repeated-measures and mixed designs

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — TFCE (threshold-free cluster enhancement)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Effect sizes with confidence intervals

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Forest plot and outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from group-statistics literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `erp-stage/`, `tfr-stage/`, `spectral-stage/`, `group_membership.csv`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `group-stage/*.json`, `group-stage/*.npz`, `group-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Related: `eeg-stats` (single per-claim within-subject cluster test; this skill is the between/mixed/factorial superset), `eeg-behavior` (group-level EEG–behavior correlation and covariate sources), `eeg-figure` (renders grand-average CI plots, cluster-masked maps, and forest plots from the tables here)
- Next: `eeg-methods-text` reads `group-stage/*.json` for the COBIDAS paragraph; `eeg-audit` verifies the second-level tests match the frozen plan and that effect-size CIs are reported.
