# AGENT_GUIDE.md — How LLM agents should drive AEA

This file is the LLM-facing entry point. Read this *before* running any skill.

## What AEA is

AEA is an open library of EEG analysis skills for MNE-Python, with executable specifications and a numerically certified core. The agent reads each `SKILL.md` and generates analysis code in the user's environment. The repository also includes utility tools, EEGLAB / FieldTrip backend templates, reference analysis scripts, validation results, and tests. You orchestrate; MNE-Python is the primary computation backend. Every step writes artifacts to disk so the pipeline survives compaction, crashes, and sleep.

## Project layout you will encounter

```
projects/<study-name>/
├── DATASET_BRIEF.md          # filled by user — paradigm, subjects, channels, conditions
├── ANALYSIS_PLAN.md          # claim-driven plan (you may help draft, user must approve)
├── ENVIRONMENT.json          # produced by tools/env/check_env.{sh,ps1}
├── raw/                      # original .bdf/.set/.edf/.fif (read-only)
├── bids/                     # BIDS-converted (eeg-bids output)
├── preprocess-stage/         # filtered, re-referenced, bad-chan-marked .fif
├── ica-stage/                # .ica, ICLabel decisions, before/after PSD
├── epoch-stage/              # epoched .fif + AutoReject decisions
├── erp-stage/                # evoked .fif per condition + GFP
├── tfr-stage/                # tfr_morlet.h5
├── stats-stage/              # cluster_perm.json, results.csv
├── figure-stage/             # *.svg / *.png (paper-ready)
├── report-stage/             # REPORT.md + report.html (mne.Report)
├── audit-stage/              # AUDIT.md (cross-model verdict)
└── FINDINGS.md               # accumulated key results across stages
```

## The 6 rules

### 1. Auto-brief first, ask second

When the user points you at a `raw/` directory without a `DATASET_BRIEF.md`, run `python tools/auto_brief.py` to extract what the file headers tell you (channels, sampling rate, events, format, system). Then ask the user **only** about what you couldn't infer — paradigm, condition→marker mapping, epoch window, hypothesis. Do NOT dump a 9-section template and say "please fill this in". Conversational, targeted questions only.

### 2. Read environment before claiming a backend works

Always read `ENVIRONMENT.json` before invoking a FreeSurfer-dependent path. If a required package is missing:
- **Degrade explicitly**: log the issue to the stage's `*.json`, and surface it in the eventual `AUDIT.md`.
- **Never silently skip**: the user must see what is missing and how it affects the analysis.

### 3. Refuse to run analyses without a frozen `ANALYSIS_PLAN.md`

The plan declares: *condition contrast → channels/ROI → time window → frequency band → statistical test → expected effect direction*. If a stage finishes and the result contradicts the planned direction, that goes in `FINDINGS.md` as a negative result — **you do not retroactively edit the plan to make the result fit**. This is enforced by `eeg-audit`.

### 4. Artifact-first, in-memory-second

Every stage writes to disk before returning. If the agent crashes mid-pipeline, the next invocation re-reads the most recent stage output and continues. Skills are designed to be idempotent on re-run.

### 5. The audit step is non-optional

`eeg-audit` invokes a fresh Codex CLI process (gpt-6-astra, max effort, read-only sandbox) with the plan, the stats output, and the figures. It produces an independent verdict on whether claims are evidence-supported. See [reviewer setup](docs/GETTING_STARTED.md#configure-the-reviewer) for configuration and the supported alternative connections. Do not skip even if everything "looks fine" — the same model that ran the analysis cannot grade it without bias.

### 6. GUI tools are not driven, only consumed

If the user mentions Brainstorm / BrainVision Analyzer / Curry / Neuroscan, ask them to export to `.set` (EEGLAB), `.fif` (MNE), or `.bdf/.edf` (raw). Do not attempt to script GUI applications.

## Skill invocation order (typical)

```
/eeg-bids        →  raw/ → bids/
/eeg-preprocess  →  bids/ → preprocess-stage/
/eeg-ica         →  preprocess-stage/ → ica-stage/
/eeg-epoch       →  ica-stage/ → epoch-stage/
/eeg-erp /eeg-tfr /eeg-connectivity /eeg-microstate /eeg-source  → epoch-stage/ → <stage>-stage/
/eeg-stats       →  <stage>-stage/ → stats-stage/
/eeg-figure      →  stats-stage/ + erp-stage/ + … → figure-stage/
/eeg-report      →  all stages → report-stage/
/eeg-audit       →  all stages → audit-stage/
```

`/eeg-pipeline` chains these and handles gates between stages.

## Backend defaults

| Skill | Default | When to override |
|---|---|---|
| eeg-preprocess | `mne` | `--prefer eeglab` / `--prefer fieldtrip` — both validated on all 5 certified components |
| eeg-ica | `mne` (mne-icalabel) | EEGLAB ICLabel exists but agreement with mne-icalabel is **unmeasured** |
| eeg-stats | `mne` | FieldTrip cluster partitions and observed t-maps have been compared for N400, P3b, N170, and ERN at the tested configurations; see [certification coverage](docs/CERTIFICATION_LEVELS.md) |
| eeg-microstate | `pycrostates` | — |
| eeg-source | `mne` + FreeSurfer | Brainstorm exports can be consumed via `scipy.io.loadmat` |

**MNE-Python is the default and the reference backend.** EEGLAB and FieldTrip provide independent
validation and are *selectable alternatives* for ERP preprocessing, validated
against the reference on all five certified ERP CORE components
([CROSS_TOOLBOX_EVAL.md](tools/benchmark/CROSS_TOOLBOX_EVAL.md): 10/10 runs reproduce the group
conclusion).

Never pick one by hand. Run `tools/env/resolve_backend.py`, which writes `BACKEND_RESOLUTION.md`,
fails loudly when nothing is available, refuses to switch silently away from a certified reference,
and refuses to claim equivalence that was never measured. When it resolves to a non-MNE backend,
emit `templates/backends/erp_preprocess_{eeglab,fieldtrip}.m` rather than ad-hoc code: cross-toolbox
agreement is a property of how completely the specification is pinned, not of the toolbox.

## Things to never do

- Run analyses on data without `ENVIRONMENT.json` checked first.
- Edit `ANALYSIS_PLAN.md` after a stage has run (creates retro-fit bias).
- Skip `eeg-audit` because results "look reasonable".
- Drive GUI applications via accessibility / AppleScript / keyboard automation.
- Use a backend that the env probe didn't confirm — degrade explicitly instead.
- Switch backends without re-running `resolve_backend.py` and updating `BACKEND_RESOLUTION.md`.
- Write EEGLAB/FieldTrip code that leaves the filter cutoff convention, transition width, or
  rejection criterion to the toolbox default. Unstated is not neutral — it is silent, and it moved
  per-subject amplitudes by up to 43% of the group effect in AEA's own measurements.
- Describe two backends' outputs as equivalent when `backends.json` records the agreement as
  unmeasured.
- Use a different random seed across stages without recording it (cluster perm is RNG-sensitive).
- Report a p-value without recording the number of permutations and the cluster-forming threshold.

## When in doubt

Read the relevant `skills/eeg-*/SKILL.md`. If still unclear, ask the user — do not improvise on EEG-specific decisions (filter cutoff, reference scheme, ICA component count, etc.). These are paradigm-dependent and the user knows their data.
