---
name: eeg-audit
description: "Audit an EEG study using its approved reviewer connection: hand over the analysis plan, stats outputs, figures and FINDINGS in a fresh context. Check claim support, plan changes, reported probabilities and figure/text consistency alongside deterministic checks. Mandatory before declaring a complete-study pipeline finished. Use for a requested study audit or after its analysis stages."
argument-hint: "[project-dir] [— reviewer: codex-cli|codex|llm-chat] [— round: 1|2] [— focus: stats|figures|cobidas]"
allowed-tools: Bash(*), Read, Write, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply
---

# eeg-audit: independent claim verification

## Context: $ARGUMENTS

## Use this skill

Read the task and the approved analysis plan before choosing a procedure. The
name and description select this skill; they do not specify the analysis.
Load only the relevant sections below, rather than every reference in advance.
For a bounded calculation, use the supplied inputs without inventing upstream
stages or approvals. Keep the actual method, parameters, outputs, and checks.

For bounded continuous delivery checks, load
[Continuous delivery checks](references/procedure.md#continuous-delivery-checks).
These direct checks and offline review-context preparation do not launch an
external reviewer. A requested full-study audit uses the approved connection below.

Template values in the detailed procedures describe their documented examples.
Resolve scientific choices against the task and approved plan before execution;
do not treat an example, a timeout, or an unattended run as researcher approval.
Preserve explicitly fixed configurations. Record unresolved choices and continue
independent approved work, as described in the project instructions.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-audit --section "Phase A — Bundle"
```

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — the frozen analysis plan.
2. `stats-stage/*.json` — per-claim statistical results.
3. `FINDINGS.md` — narrative findings.
4. `report-stage/REPORT.md` — the manuscript/report draft.
5. `figure-stage/CAPTIONS.md` — figure captions (if figures were generated).
6. `*/BACKEND_RESOLUTION.md` — backend resolution logs from each stage.

Optional but checked if present:
- `DATASET_BRIEF.md`, `erp-stage/component_measures.csv`, `figure-stage/*.png`.

## Forbidden behaviors

- Do not let the analysis-producing session act as its own reviewer. Use the approved external reviewer connection and retain actual execution evidence.
- Do not edit any file in `stats-stage/`, `erp-stage/`, `epoch-stage/`, or `figure-stage/` based on the audit. The audit produces a verdict; the user (or a re-run of the analysis with corrected plan) produces the fix.
- Do not auto-trigger round 3 if round 2 still fails. Surface to user.
- Check the run plan against existing approval and execution records. Missing evidence remains unverified; a content/time discrepancy needs review. Do not invent an approval record.
- File modification times are diagnostic observations, not proof of approval or post-hoc editing. A copied plan can have a newer mtime without changed content. Do not turn this alone into a failed claim or a passing approval check.
- Never mark a source-localization claim `pass` if the EEG was not common-average referenced before the forward model, or if it ran with an unset montage / an *unintended* identity trans on a non-template setup. These are integrity-level failures, not caveats. (The bundled `trans='fsaverage'` transform with a standard montage is the documented template path — acceptable, but downgrade to ROI/lobar claims.)
- Never let a source-localization study built on a template BEM + template electrode positions (no individual MRI, no digitized electrodes) report voxel- or millimetre-precise peaks. Downgrade such claims to coarse ROI/lobar/network level.
- Never mark a microstate study `pass` if maps were fit per-recording (individual) rather than from a single global/group template — flag the reliability concern (Khanna et al. 2014, alpha ~0.52) regardless of the reported result.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Why this skill is non-optional

Read this section in [the detailed procedure](references/procedure.md).

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Bundle

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Plan provenance and consistency (direct check)

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Hand off to the configured reviewer

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Parse verdict and write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Re-audit protocol (Round 2)

Read this section in [the detailed procedure](references/procedure.md).

## Common EEG reviewer concerns (distilled from real peer reviews)

Read this section in [the method background](references/background.md).

## COBIDAS-MEEG checklist (Pernet et al. 2020, Nature Neuroscience)

Read this section in [the method background](references/background.md).

## Domain knowledge (audit-relevant, with citations)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `stats-stage/*.json`, `FINDINGS.md`, `report-stage/REPORT.md`, `figure-stage/CAPTIONS.md`, `*/BACKEND_RESOLUTION.md`, `DATASET_BRIEF.md`, `erp-stage/component_measures.csv`
- Outputs: `audit-stage/AUDIT.md`, `audit-stage/AUDIT.json`, `audit-stage/PLAN_PROVENANCE.json`, `audit-stage/AUDIT_ROUND1_BUNDLE.md`
- Next: If `pass` or `pass-with-caveats` → pipeline complete, proceed to submission. If `revise` → user fixes, then `/eeg-audit — round: 2`. If `fail` → pipeline halted.
