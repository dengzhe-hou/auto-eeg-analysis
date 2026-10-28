---
name: eeg-figure
description: "Render paper-ready figures from stage outputs: ERP butterfly + topomap + cluster-masked difference, TFR maps with cluster outlines, microstate template + transitions, source dipole renderings. Reads FIGURE_PLAN.md and writes both SVG (editable) and PNG (preview)."
argument-hint: "[project-dir] [— figures: F1,F2,F3] [— journal: nature|jneurosci|neuroimage] [— width: single|double]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-figure: paper-ready figure rendering

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
python tools/load_skill.py eeg-figure --section "Phase A — Parse figure plan"
```

## Required Inputs

Before rendering, these must exist:

1. `FIGURE_PLAN.md` — specifies each figure's panels, data sources, and layout. **Stop if missing.**
2. Stage outputs referenced in the plan: `erp-stage/`, `tfr-stage/`, `stats-stage/`, `connectivity-stage/`, `source-stage/`, etc.
3. `ANALYSIS_PLAN.md` — to verify figure content matches planned analyses.
4. `channel_mapping.json` — if topomaps need 10-20 labels but data uses numbered channels.

## Forbidden styles (audit will flag)

- `jet` colormap — always rejected.
- Auto-scaled symmetric difference plots (`vmin`/`vmax` must be explicit).
- 3-D rotated topomaps without explicit user request.
- Bar plots with SEM only (must show distribution + 95% CI or individual data).
- "p = 0.000" — must be `p < 0.001`.
- Red-green only color coding without secondary encoding (linestyle/marker).
- Missing colorbars on heatmaps or topomaps.
- Missing units on any axis.

## Critical Rules

- **Never** render a figure not in FIGURE_PLAN. Ad hoc figures go in `figure-stage/exploratory/` and are labeled `[EXPLORATORY]`.
- **Never** auto-scale vmin/vmax for difference or t-value maps — always set symmetric explicit limits.
- **Never** use `plt.show()` in scripts — only `savefig()`. Rendering is headless.
- **Never** use `jet`. Not even "just for a quick look." The audit flags it. Use `viridis` or `RdBu_r`.
- **Never** produce bar plots that hide the underlying distribution. Use violin, raincloud, or dot plots.
- **Always** include scale bars, units, and colorbars.
- **Always** set `bbox_inches='tight'` to avoid clipping labels.
- **Never** include the connectivity-matrix diagonal in the color scale — it is trivial (coh≈1, PLI/wPLI≈0) and saturates the map. Mask it (`np.fill_diagonal(M, np.nan)`) and scale from off-diagonal values; count edges as E·(E−1)/2 (undirected) or E·(E−1) (directed).
- **Never** average across subjects before producing the array fed to cluster/permutation stats — keep the per-subject axis (the analog of FieldTrip `keepindividual='yes'`); collapse only for the visual mean.
- **Always** morph individual source estimates to `fsaverage` before group display or MNI reporting, and state the display threshold used to mask the map.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Parse figure plan

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Figure type catalog and rendering

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Style enforcement

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Render and save

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Generate captions

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from visualization methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `FIGURE_PLAN.md`, `erp-stage/`, `tfr-stage/`, `stats-stage/`, `decoding-stage/`, `connectivity-stage/`, `source-stage/`, `ANALYSIS_PLAN.md`, `channel_mapping.json`
- Outputs: `figure-stage/F<n>_<name>.svg`, `figure-stage/F<n>_<name>.png`, `figure-stage/CAPTIONS.md`, `figure-stage/FIGURE_RENDER_PLAN.json`
- Next: `eeg-report` embeds figures into HTML report. `eeg-methods-text` references figure numbers. `eeg-audit` checks figures match the plan.
