---
name: eeg-stats
description: "Run claim-driven group statistics: cluster permutation (channel/time/freq), paired/independent t, effect sizes. Reads ANALYSIS_PLAN.md claim rows and the matching erp/tfr/connectivity stage outputs. Backend: MNE-Python. Use when user says 'run stats', 'cluster permutation', 'test my claims', or after ERP/TFR stages complete."
argument-hint: "[project-dir] [— claim: C1,C2] [— perms: 5000] [— exploratory]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-stats: claim-driven group statistics

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
python tools/load_skill.py eeg-stats --section "Phase A — Parse claims"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `erp-stage/` or `tfr-stage/` — averaged data per condition per subject (`.fif` or `.h5`).
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Critical Rules

- **Never** run a stat not in ANALYSIS_PLAN. Exploratory analyses go in `stats-stage/exploratory/` and are labeled `[EXPLORATORY]` in FINDINGS.md.
- **Never** edit ANALYSIS_PLAN after running. If a reviewer asks for additional analyses, add them as exploratory or create a v2 plan with documented reason.
- **Never** change `n_permutations` to chase significance.
- **Never** use `tail=0` when the plan specifies a directional hypothesis (or vice versa).
- **Never** report cluster boundaries as precise onset/offset — cluster permutation only supports "a difference exists somewhere in the tested space."
- **Never** pair different participants or treat repeated measurements from the same participants as separate groups. At the trial level, establish pairing separately from participant identity (Phase A step 3b). Paired tests require matched observation identifiers, not just equal array lengths.
- **Never** copy FieldTrip's `cfg.alpha=0.025` as a second halving in MNE — MNE handles two-sidedness internally; judge `cluster_p < alpha` with `tail=0` (Phase C step 5).
- **Never** average across subjects before a group test, and never present an uncorrected p-map as 'significant' — uncorrected maps are visualization only.
- **Never** select the TF band/window or ERP channel+window from the grand average and then test it (double-dipping) — a-priori ROIs come from ANALYSIS_PLAN only.
- **Refuse to certify** group analyses with very small N (≲12) as adequately powered — flag them as underpowered in FINDINGS.md.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Parse claims

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-claim execution

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Multiple comparisons

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `erp-stage/`, `tfr-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `stats-stage/*.json`, `stats-stage/*.npz`, `stats-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-figure` reads stats results for cluster-masked plots. `eeg-methods-text` reads stats JSON for the paragraph. `eeg-audit` verifies stats match the plan.
