---
name: eeg-methods-text
description: "Auto-generate a submission-ready EEG methods paragraph that satisfies the COBIDAS-MEEG checklist (Pernet et al. 2020). Reads DATASET_BRIEF.md, every stage's BACKEND_RESOLUTION.md and *_summary.json, ANALYSIS_PLAN.md, and stats-stage outputs to produce a paragraph users can paste into their paper. Reviewers love it. Authors love it more. Use when the user says \"write methods\", \"generate methods text\", \"COBIDAS paragraph\", or after the pipeline finishes."
argument-hint: "[project-dir] [— venue: NeurIPS|JNeurosci|NeuroImage|FrontiersHumanNeuro|CerebralCortex|generic] [— format: md|tex|both] [— bibtex]"
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# eeg-methods-text: COBIDAS-MEEG methods paragraph generator

A truly novel skill: no existing EEG pipeline emits a methods paragraph. Authors copy-paste from past papers and miss details that reviewers catch.

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
python tools/load_skill.py eeg-methods-text --section "Constants"
```

## Critical Rules

- **Never** write "significant" next to an uncorrected mass-univariate p < 0.05 map. Every cluster/point reported as significant must carry its multiple-comparison method (cluster permutation, FDR, or Bonferroni) in the same sentence.
- **Never** report a cluster's temporal/spatial extent as the effect's onset, offset, or peak location (Sassenhagen & Draschkow 2019); the methods text must phrase cluster bounds as "a cluster spanning ...", not "the effect began at ...".
- **Never** state a cluster-forming threshold as a bare number (e.g. "t = 2.0") without its derivation; report it as the critical t at the chosen alpha and design df (`scipy.stats.t.ppf(1 - alpha/2, df)`, two-tailed) or note `threshold=None` (MNE default) explicitly.
- **Never** invent demographics, filter cutoffs, or trial counts to fill a `missing` checklist item; emit "not recorded" and warn in the self-check.
- **Never** fabricate a citation. Only emit BibTeX for tools/methods actually present in a stage `BACKEND_RESOLUTION.md`.
- Always report **retained trial counts per condition** (mean and range across subjects), since ERP/TFR SNR scales with sqrt(n_trials); a paragraph that reports rejection percentage but not surviving counts is incomplete.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## What goes into the paragraph

Read this section in [the detailed procedure](references/procedure.md).

## Phases

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge

Read this section in [the method background](references/background.md).

## Failure modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Reads: `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, every stage's `*_summary.json` + `BACKEND_RESOLUTION.md`, `stats-stage/*_cluster_perm.json`.
- Writes: `report-stage/methods.md`, `report-stage/methods.tex`, `report-stage/methods_references.bib`, `report-stage/methods_artemis.json` (structured ARTEM-IS methods), `report-stage/preregistration_deviations.md` (executed-vs-planned diff), optionally `report-stage/methods_supplementary.md`.
- Auditor (`eeg-audit`) verifies that every claim in the methods paragraph traces back to a `stats-stage` artifact.
