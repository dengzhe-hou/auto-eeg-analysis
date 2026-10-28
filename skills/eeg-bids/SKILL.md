---
name: eeg-bids
description: "Convert raw recordings to BIDS-EEG layout. Reads DATASET_BRIEF.md for paradigm/condition codes; produces dataset_description.json, participants.tsv, sub-*/eeg/ structure. Use when raw data is in lab-specific layout and needs BIDS-ifying before downstream skills run."
argument-hint: "[project-dir] [— powerline: 50|60] [— overwrite] [— validate-only]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-bids: raw → BIDS-EEG

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
python tools/load_skill.py eeg-bids --section "Constants"
```

## Required Inputs

Before running, these must exist:

1. `DATASET_BRIEF.md` — for paradigm, condition marker codes, demographics.
2. `raw/` directory — containing raw EEG files (`.set`, `.vhdr`, `.edf`, `.bdf`, `.fif`, `.cnt`, `.mff`).
3. `ENVIRONMENT.json` — to verify `mne_bids` is available.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phases

Read this section in [the detailed procedure](references/procedure.md).

## Failure modes

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge

Read this section in [the method background](references/background.md).

## Cross-references

- Inputs: `DATASET_BRIEF.md`, `raw/` directory, `ENVIRONMENT.json`.
- Outputs: `bids-stage/` (BIDS-formatted data), `bids-stage/BIDS_REPORT.md`, `bids-stage/BIDS_VALIDATION.md`, `bids-stage/BACKEND_RESOLUTION.md`.
- Next: `eeg-preprocess` reads from `bids-stage/` as input.
- MNE-BIDS documentation: [mne.tools/mne-bids](https://mne.tools/mne-bids).
