---
name: eeg-connectivity
description: "Compute approved EEG connectivity: epoch-based wPLI, PLV, coherence, imaginary coherence, Granger causality or phase-amplitude coupling; also bounded continuous Pearson correlation, Hilbert PLV and ordinary temporal wPLI. Use when the task or study plan requests connectivity. Preserve the estimator and averaging axis."
argument-hint: "[project-dir] [— metric: wpli|plv|coh|imcoh|gc|pac] [— space: sensor|source]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-connectivity: functional connectivity

## Context: $ARGUMENTS

## Use this skill

Read the task and approved plan, then select the estimator and averaging axis.
For a bounded continuous request, load only the matching reference section:

- [Continuous Pearson correlation](references/continuous.md#continuous-pearson-correlation).
- [Continuous PLV](references/continuous.md#continuous-plv), averaged over time samples.
- [Continuous ordinary wPLI](references/continuous.md#continuous-ordinary-wpli),
  retaining analytic-signal amplitudes.
- [Complete multiband Hilbert calculation](references/continuous.md#complete-multiband-hilbert-calculation),
  connecting each approved branch to saved matrices, summaries and source-data checks.

For an epoch-based study, use the stages below with its approved estimator.
Preserve fixed settings; examples add no processing or scientific default to
the request. Record unresolved choices and continue independent approved work.
A timeout or unattended run supplies no additional approval.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-connectivity --section "Continuous ordinary wPLI"
```

## Required Inputs

For a bounded continuous request, use the approved task/plan, supplied Raw or
time series, resolved channel identities, and explicit estimator, bands,
interval and operation order. An already resolved request can supply the plan;
record it with the outputs. Continuous Hilbert methods do not require epochs.

For an epoch-based study, use the frozen `ANALYSIS_PLAN.md`, cleaned
per-condition epochs and `ENVIRONMENT.json` for the chosen backend. Resolve
`channel_mapping.json` when numbered labels need anatomical identities.
Source-space methods additionally require the approved source time courses.
Do not construct unrelated upstream directories for a bounded request.

## Critical Rules

- **Never** compute coherence or PLV in sensor space and interpret as "brain region A connects to region B" — volume conduction confounds this interpretation. Use wPLI, imaginary coherence, or source-space analysis.
- **Never** use Granger causality on non-stationary data without stationarity checks (ADF test or windowed approach).
- **Never** interpret graph metrics from a single threshold. Report sensitivity to threshold choice or use MST-based approaches.
- **Never** average connectivity across frequency bands without justification — each band may show different network topology.
- For epoch-based contrasts, preserve the approved handling of trial-count differences; do not silently subsample. This prerequisite does not apply to a continuous estimator averaged across time samples.
- Spectral coherence/PLV across epochs needs that averaging dimension. An approved Hilbert PLV across time samples is a different estimator; preserve its declared averaging axis.
- **Never** include the diagonal in connectivity statistics or in figure color scaling, and use the correct edge count for multiple-comparison correction (`E*(E-1)/2` undirected, `E*(E-1)` directed).
- For proportional graphs, select from the declared **available unique edges**,
  not a percentile of the whole matrix. Keep estimator storage/indices,
  direction, ranking/sign handling, density, rounding and boundary-tie policy.
  Uncomputed triangular entries are unavailable; measured zero edges remain
  eligible. Record the actual retained edge count and density.
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

For the continuous procedures linked above, use the matching
[callable primitives](scripts/continuous.py). These average over time samples,
not epochs; preserve the plan's estimator, bands and processing order.
For multiple bands, use independent input copies; MNE RawArray construction
can share an existing array's memory and filtering can otherwise contaminate
the next band.

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
The [proportional graph helper](scripts/graph.py) implements an explicitly
approved edge-selection policy and records its candidates/retained edges.
It does not choose a graph density, sign convention or thresholding method.

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
