---
name: eeg-report
description: "Build a self-contained HTML report (mne.Report) and a Markdown summary from all stage outputs: methods, sample, exclusions, per-claim results with figures, full statistical reporting. Use after eeg-stats and eeg-figure complete."
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

Before building the report, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `DATASET_BRIEF.md` — acquisition parameters, participant info, task description.
3. At least one stage output directory: `preprocess-stage/`, `ica-stage/`, `erp-stage/`, `tfr-stage/`, `stats-stage/`, `figure-stage/`.
4. `FINDINGS.md` — per-claim verdicts from eeg-stats.
5. `ENVIRONMENT.json` — software versions and backend info.
6. `figure-stage/*.svg` and `figure-stage/*.png` — rendered figures from eeg-figure.

Optional:
- `channel_mapping.json` — for reporting channel name conventions.
- `stats-stage/BACKEND_RESOLUTION.md` — backend selection rationale.

## Critical Rules

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
