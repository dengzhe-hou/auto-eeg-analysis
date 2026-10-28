---
name: eeg-pipeline
description: "Coordinate an approved EEG analysis across data preparation, selected analysis branches, statistics, figures, reporting and audit. Use for an end-to-end study or resuming a recorded pipeline. Read DATASET_BRIEF.md and ANALYSIS_PLAN.md before choosing stages."
argument-hint: "[project-dir] [— skip: ica,source] [— from: epoch] [— auto-proceed]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# eeg-pipeline: full orchestration

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
python tools/load_skill.py eeg-pipeline --section "Constants"
```

## Execution authority and unattended runs

The approved `ANALYSIS_PLAN.md` determines scientific choices. Recipe examples,
skill defaults and checkpoint settings do not approve a new filter, reference,
contrast, ROI, exclusion rule or statistical test. `AUTO_PROCEED` only advances
steps already covered by that approval.

When the user requests an unattended run, execute those approved steps without
intermediate confirmation. Record a missing scientific decision in
`PIPELINE_STATE.json.unresolved_decisions` with the stage, affected claim or
participant, missing field and reason. Mark the dependent work `blocked`,
preserve its artifacts, and continue independent approved work. Do not invent an
answer, request ad hoc help for one condition, silently drop that unit or report
the pipeline complete. Existing approved ICA decisions apply to their saved
decomposition, not to matching component numbers in a new fit.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Stage dependency graph

Read this section in [the detailed procedure](references/procedure.md).

## Phases

Read this section in [the detailed procedure](references/procedure.md).

## Resume semantics

Read this section in [the detailed procedure](references/procedure.md).

## Per-stage timing and progress

Read this section in [the detailed procedure](references/procedure.md).

## Failure modes

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge

Read this section in [the method background](references/background.md).

## Cross-references

- See each child skill's own SKILL.md for stage-specific behavior.
- Read `AGENT_GUIDE.md` for the project-layout convention.
- Checkpoint config: `~/.claude/checkpoint.json`.
