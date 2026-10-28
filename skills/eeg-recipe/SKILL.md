---
name: eeg-recipe
description: "Apply an EEG recipe to user data: check the dataset brief, draft or reuse the approved analysis plan, pass its parameters through the declared stages, and save outputs and replay records. Use for run recipe X, reproduce paper Y, apply an EEG recipe to my data, or a named recipe slug."
argument-hint: "[recipe-slug] --data [project-dir] [--marker-map target=1,standard=2] [--skip-audit] [--version v0.2]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# eeg-recipe: run a published EEG analysis recipe

The flagship skill. Takes a recipe slug + a data directory, produces a paper-ready figure + COBIDAS-compliant methods text + reproducibility receipt.

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
python tools/load_skill.py eeg-recipe --section "Constants"
```


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phases

Read this section in [the detailed procedure](references/procedure.md).

## State-tracking recipe class (continuous, windowed)

Read this section in [the detailed procedure](references/procedure.md).

## Contributed-recipe quality gates

Read this section in [the detailed procedure](references/procedure.md).

## Failure modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Recipe library: `recipes/`, see `recipes/README.md`.
- Template for new recipes: `recipes/_template/RECIPE.md`.
- Contributing recipes: `CONTRIBUTING.md`.
- Auto-brief tool: `tools/auto_brief.py`.
- Figure comparison output: `FIGURE_COMPARISON.md`.
- Version tracking: `RECIPE_VERSION.json`.
- Complexity / entropy / RQA metrics for state-tracking recipes: `eeg-complexity` (the `complexity` stage skill).
- Windowing helper for continuous recipes: `mne.make_fixed_length_epochs` (default 5 s duration, 2 s overlap; ≥16 s for scale-free/Hurst).
