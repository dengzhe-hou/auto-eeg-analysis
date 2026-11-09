---
name: eeg-behavior
description: "Behavioral data analysis and EEG-behavior relationships: RT/accuracy descriptive stats, condition effects, speed-accuracy tradeoffs, single-trial EEG-behavior regression, median-split analyses, brain-behavior correlations. Use when user says 'behavioral analysis', 'RT analysis', 'accuracy', 'EEG-behavior correlation', 'single-trial regression', 'does N2 predict RT', or needs to link EEG to performance."
argument-hint: "[project-dir] [— measures: rt,accuracy,dprime] [— eeg-behavior: regression|median-split|correlation]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-behavior: behavioral data analysis + EEG-behavior linking

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
python tools/load_skill.py eeg-behavior --section "Phase A — Extract behavioral data"
```

## Required Inputs

1. `epoch-stage/` — epoched data with event metadata (condition labels, response markers).
2. `DATASET_BRIEF.md` — to know trial structure, response markers, condition mapping.
3. `ANALYSIS_PLAN.md` — for behavioral claims or EEG-behavior claims.
4. Behavioral data source: either embedded in EEG events (response markers + timing) or separate behavioral log file.

## Critical Rules

- **Never** include incorrect trials in RT analysis (unless specifically analyzing error RTs).
- Preserve the approved RT eligibility, outlier and inclusion policy. Skew alone does not authorize removing observations or applying an accuracy cutoff.
- **Never** report median split as primary analysis — use regression. Median split is for visualization only.
- Distinguish within-subject trial associations from across-subject associations. Preserve the approved estimand; one does not establish the other.
- **Never** fit pooled `sm.OLS` (or `pearsonr`) on single trials from multiple subjects as if they were independent — use a mixed-effects model with a subject random effect (pseudoreplication otherwise inflates significance).
- **Never** use plain `KFold`/`train_test_split` when cross-validating an EEG->behavior model over pooled subjects — use `GroupKFold`/`LeaveOneGroupOut` with `groups=subject`. Report mean ± std across folds, never the best/max fold.
- **Never** forget to report the number of trials excluded by each filtering step.
- Assign responses only within the approved recording/block and response window. Record missed/unused responses and never reuse a response row across trials under the one-response assignment.
- Join retained EEG and behavior by the original trial keys. Equal lengths or similar row order do not establish alignment. Participant comparisons need participant identities; true trial-pair comparisons need their pair identities. Never truncate conditions to manufacture pairs.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

Use [the trial helpers](scripts/trials.py) for the explicitly selected first-unused
response assignment, one-to-one joins and paired arrays. The helpers retain
unmatched records, require the missing-data policy, and do not select a test or
aggregate trials into participants.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Extract behavioral data

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Behavioral descriptive statistics

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — EEG-behavior single-trial regression

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `epoch-stage/`, `DATASET_BRIEF.md` (for marker→condition mapping), behavioral log files
- Outputs: `behavior-stage/*.json`, `figure-stage/` (RT/accuracy plots, EEG-behavior scatter)
- Related: `eeg-erp` (ERP amplitudes as predictors), `eeg-stats` (group-level EEG-behavior correlation), `eeg-decoding` (can RT-sorted trials improve decoding?)
