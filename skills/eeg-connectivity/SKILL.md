---
name: eeg-connectivity
description: "Compute functional connectivity per condition: wPLI, PLV, coherence, imaginary coherence, Granger causality, or phase-amplitude coupling on sensor-space epochs (or source-space if eeg-source ran). Optional skill — only invoked if DATASET_BRIEF.md ticks Connectivity."
argument-hint: "[project-dir] [— metric: wpli|plv|coh|imcoh|gc|pac] [— space: sensor|source]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-connectivity: functional connectivity

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
python tools/load_skill.py eeg-connectivity --section "Phase A — Metric selection and validation"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with connectivity claims (if any). **Stop if missing or unfrozen.**
2. `epoch-stage/` — cleaned, epoched `.fif` files per subject per condition.
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.
5. (Optional) `source-stage/` — source-space time courses if `— space: source`.

## Critical Rules

- **Never** compute coherence or PLV in sensor space and interpret as "brain region A connects to region B" — volume conduction confounds this interpretation. Use wPLI, imaginary coherence, or source-space analysis.
- **Never** use Granger causality on non-stationary data without stationarity checks (ADF test or windowed approach).
- **Never** interpret graph metrics from a single threshold. Report sensitivity to threshold choice or use MST-based approaches.
- **Never** average connectivity across frequency bands without justification — each band may show different network topology.
- **Never** compare connectivity matrices with different numbers of epochs across conditions — subsample to match trial counts.
- **Never** report coherence or PLV computed from a single segment/epoch — both are degenerate (=1) without averaging over multiple segments/trials.
- **Never** include the diagonal in connectivity statistics or in figure color scaling, and use the correct edge count for multiple-comparison correction (`E*(E-1)/2` undirected, `E*(E-1)` directed).
- **Never** threshold connectivity edges at p<0.05 independently — correct across the ~N² edges (FDR, cluster permutation, or NBS).
- **Never** estimate a separate source spatial filter per condition when contrasting conditions in source space — use one common filter on pooled data, then apply per condition.
- **Never** apply CSD/Laplacian before MVAR-based DTF/PDC — it distorts the MVAR model and yields misleading directed structure (CSD-before-FC is only for phase/coherence metrics).
- **Never** report PDC without stating the variant — standard column-normalized PDC is not scale-invariant and drops when a source drives multiple targets; prefer scale-invariant gPDC.
- **Never** claim mutual information, transfer entropy, or Synchronization Likelihood from `mne_connectivity` — they are not in MNE core and require external tools.
- **Never** report raw (un-normalized) PAC / Modulation Index — z-score it against a surrogate null (block-shift / trial-shuffle), since raw MI is always positively biased.
- **Never** rely on the FFT phase-scramble surrogate alone for PAC — it cannot control the sharp-edge/non-sinusoidal artifact that most often produces spurious coupling; prefer time-splice/block-shift or trial-shuffle.
- **Never** read significance off a raw comodulogram — correct the per-cell p-values across the full `n_phase × n_amp` grid (Holm/Bonferroni, FDR, or cluster permutation).
- **Never** crash the stage when `pactools`/`tensorpac` are absent — they are optional; fall back to the pure-NumPy Tort MI / Rayleigh implementations.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Ordinary wPLI numerical quick start

Read this section in [the detailed procedure](references/procedure.md).

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Metric selection and validation

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Backend resolution

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Per-subject connectivity computation

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Graph theory metrics

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Group-level aggregation

Read this section in [the detailed procedure](references/procedure.md).

## Phase E3 — Group connectivity statistics

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Phase-amplitude coupling (PAC)

Read this section in [the detailed procedure](references/procedure.md).

## Phase H — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from EEG connectivity methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epoch-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`, `source-stage/` (optional)
- Outputs: `connectivity-stage/*.npz`, `connectivity-stage/*-graph_metrics.json`, `connectivity-stage/BACKEND_RESOLUTION.md`, `connectivity-stage/METRIC_SELECTION.md`, `FINDINGS.md`
- Next: `eeg-stats` for statistical comparison of connectivity between conditions. `eeg-figure` for connectivity matrix plots and circle plots. `eeg-methods-text` for the connectivity paragraph.
