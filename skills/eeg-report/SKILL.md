---
name: eeg-report
description: "Build an HTML report (mne.Report) and Markdown summary from executed EEG stages, including continuous/descriptive analyses and per-claim statistical results when planned. Use when the user requests an analysis report or the approved analysis stages have finished."
argument-hint: "[project-dir] [— format: html|md|both] [— cobidas: strict|normal]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-report: auto-generate HTML/Markdown report

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
python tools/load_skill.py eeg-report --section "Phase A — Collect stage outputs"
```

## Required Inputs

For a bounded structured delivery, use
[Final JSON and interpretation](references/procedure.md#final-json-and-interpretation):
save and print the same result object, including the requested interpretation.

Before building the report, these must exist:

1. `ANALYSIS_PLAN.md` — the approved version with stages and any planned claims. A descriptive workflow does not require inventing a contrast or significance test.
2. `DATASET_BRIEF.md` — acquisition parameters, participant info, task description.
3. Outputs of the planned stages, including continuous spectral, connectivity, complexity and microstate routes. Use [the shared input inventory](scripts/inputs.py) with actual source paths from the plan/execution ledger.
4. `FINDINGS.md` and statistical result files when claim verdicts are part of the approved workflow. Their absence must not be hidden if they were planned.
5. `ENVIRONMENT.json` — software versions and backend info.
6. `figure-stage/*.svg` and `figure-stage/*.png` when figures are planned. Record missing planned figures; do not treat an unplanned figure stage as a failed computation.

Optional:
- `channel_mapping.json` — for reporting channel name conventions.
- `stats-stage/BACKEND_RESOLUTION.md` — backend selection rationale.

## Critical Rules

- Inventory every supported output stage. Mark unplanned stages `not_applicable`, and planned-but-missing inputs `unavailable`; file presence alone does not prove a completed or validated analysis. Preserve partial/failed results in an explicitly incomplete report.
- **Never** fabricate data or statistics in the report. Every number must trace to a stage output file.
- **Never** omit exclusions or failed subjects — transparency is mandatory.
- **Never** modify ANALYSIS_PLAN.md during report generation.
- **Never** embed raw data files in the HTML report (size risk). Embed only figures and summary statistics.
- **Always** include the COBIDAS checklist — even if some items fail.
- **Always** generate REPRO_RECEIPT.md — it is not optional.
- **Always** record actual seeds used, not planned seeds, by reading from stage output logs.
- **Never** report microstate clinical effect directions (e.g., SCZ → increased C, AD → shortened durations) as a per-subject diagnosis or classifier — present them only as group-level literature context with citations, against published healthy-adult norm bands.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Collect stage outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Build HTML report via mne.Report

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Build Markdown report

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Generate REPRO_RECEIPT.md

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from reporting methodology literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `DATASET_BRIEF.md`, `FINDINGS.md`, `ENVIRONMENT.json`, all `*-stage/` directories, `figure-stage/*.svg`, `figure-stage/*.png`, `channel_mapping.json`
- Outputs: `report-stage/report.html`, `report-stage/REPORT.md`, `report-stage/REPRO_RECEIPT.md`, `report-stage/STAGE_INVENTORY.json`
- Previous: `eeg-stats` and `eeg-figure` must complete before report generation.
- Next: `eeg-audit` verifies report completeness. `eeg-methods-text` may draw from the report for manuscript methods section.
