---
name: eeg-pipeline
description: "Top-level orchestrator: chains eeg-bids → eeg-preprocess → eeg-ica → eeg-epoch → (eeg-erp / eeg-tfr / eeg-connectivity / eeg-microstate / eeg-source) → eeg-stats → eeg-figure → eeg-report → eeg-audit. Reads DATASET_BRIEF.md and ANALYSIS_PLAN.md to decide which branches to run. Use when the user wants the full pipeline end-to-end."
argument-hint: "[project-dir] [— skip: ica,source] [— from: epoch] [— auto-proceed]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# eeg-pipeline: full orchestration

## Context: $ARGUMENTS

## Constants

- **AUTO_PROCEED** — read from `~/.claude/checkpoint.json`. If `auto_proceed: true` and the gate is `"auto"`, run gates auto-pass. If `auto_proceed: false` or gate is `"always_wait"`, pause for user OK between stages. If `~/.claude/checkpoint.json` does not exist, default to `true`.
- **FAIL_FAST = `false`** — when `true`, abort on first per-subject failure; otherwise log and continue.
- **STAGES_DEFAULT = `[bids, preprocess, ica, epoch, erp, tfr, stats, figure, report, audit]`** — `connectivity / microstate / source` only added if `DATASET_BRIEF.md > Analyses planned` ticks them.
- **STATE_FILE = `<project-dir>/PIPELINE_STATE.json`** — crash recovery persistence (see Phase B).
- **TIMEOUT_SECONDS** — read from `~/.claude/checkpoint.json`, default `300`.

## Stage dependency graph

Some stages have strict sequential dependencies; others can run in parallel when their inputs are ready:

```
bids ──→ preprocess ──→ ica ──→ epoch ──┬──→ erp ────────┐
                                         ├──→ tfr ────────┤
                                         ├──→ connectivity┤
                                         ├──→ microstate  ├──→ stats ──→ figure ──→ report ──→ audit
                                         └──→ source ─────┘
```

- **Parallel group**: After `epoch` completes, `erp`, `tfr`, `connectivity`, `microstate`, and `source` can all run independently.
- **Sync point**: `stats` waits for ALL analysis branches to finish before starting.
- In practice, invoke these branches sequentially through the client's skill mechanism, but log that they have no data dependency. If no child-skill invocation tool is available, read the corresponding `skills/eeg-<stage>/SKILL.md` directly and follow it from the repository root.

### Cross-stage ordering invariants (verify before chaining)

Individual child skills enforce their own internal order, but the orchestrator must guarantee these invariants hold *across* stage boundaries, because a re-run with `— from:` or `— skip:` can otherwise violate them:

- **Filter before downsample.** The continuous data must be band-pass / notch filtered *before* any `raw.resample(...)`. Resampling first aliases high-frequency content and shifts event sample indices. If `preprocess` is skipped but a later resample is requested, abort with a clear error.
- **Resample Raw, never Epochs.** Resampling belongs in `preprocess` (on `Raw`, before `epoch`). Never invoke a resample on the epoched data — `Epochs.resample` jitters event timing relative to t=0 and corrupts ERP latencies. If `ANALYSIS_PLAN.md` requests a sample rate change after `epoch`, route it back to the preprocess stage instead.
- **Reference / ICA-rank consistency.** If `preprocess` sets an average reference, it must be applied consistently and the data rank reduced by one before `ica` (e.g. via `set_eeg_reference(projection=True)`), so the ICA decomposition is not rank-deficient. The orchestrator should confirm `preprocess_summary.json` and the ICA stage agree on the reference scheme; a mismatch (e.g. average ref in preprocess but ICA run on un-referenced data) is a silent rank/quality bug.

## Phases

### A. Pre-flight (mandatory)
1. **Checkpoint config**: Read `~/.claude/checkpoint.json`. Set `AUTO_PROCEED` and `TIMEOUT_SECONDS` from the file. If file missing, default `AUTO_PROCEED=true`, `TIMEOUT_SECONDS=300`.
2. **Auto-brief**: If `DATASET_BRIEF.md` does not exist but `raw/` does, run `python tools/auto_brief.py --raw-dir <project-dir>/raw/ --out <project-dir>/DATASET_BRIEF.md --json <project-dir>/auto_brief_scan.json`. Then ask the user conversationally about remaining `[USER]` fields (paradigm, condition→marker mapping, epoch window, hypothesis). Do NOT dump the full template.
3. Read `DATASET_BRIEF.md`. If any `[USER]` fields remain for critical parameters (paradigm, conditions, epoch window), ask the user. Non-critical fields with sensible defaults (bandpass, reference, stats) can proceed with defaults.
4. Read or generate `ENVIRONMENT.json` via `tools/env/check_env.{sh,ps1}`.
5. Read `ANALYSIS_PLAN.md`. If absent, generate a draft from `DATASET_BRIEF.md` claims and ask the user to confirm. **Do not run analyses without a frozen plan.**
6. Resolve which optional analyses (TFR / connectivity / microstate / source) are ticked in DATASET_BRIEF.
6b. **Resolve the group design before chaining stats.** Read `DATASET_BRIEF.md > Design` and the `ANALYSIS_PLAN.md` claim rows to classify each claim as **within-subject** (same subjects, ≥2 conditions) or **between-subject** (different groups). Record the resolution per claim and pass it through to `eeg-stats` so it selects the matching test:
   - **Within-subject** → per-subject condition difference fed to `spatio_temporal_cluster_1samp_test` (the analog of FieldTrip `depsamplesT`); point tests use `ttest_rel`. Requires **equal n and matched subject ordering** across conditions.
   - **Between-subject** → two independent group arrays to `spatio_temporal_cluster_test` (analog of `indepsamplesT`); point tests use `ttest_ind`. Tolerates **unequal n** (e.g. 20 controls vs 18 patients) and must **never pair**.
   If the design field is `[USER]` or ambiguous (e.g. a claim names two conditions but the subject lists differ), stop and ask the user — do not silently default to paired, because a within-test on mismatched subjects is a hard correctness error, not a tuning choice. Write the resolved design into `PIPELINE_STATE.json` under a `design` key so the stats branch and `eeg-audit` can verify it.
7. **Resume check**: If `PIPELINE_STATE.json` exists AND `— from:` was NOT explicitly passed, read it and offer to resume from the last incomplete stage (or auto-resume if `AUTO_PROCEED=true`).

### B. State persistence (crash recovery)

Maintain `PIPELINE_STATE.json` throughout the run for crash recovery:

```json
{
  "pipeline_version": "1.0",
  "project_dir": "/path/to/project",
  "started_at": "2026-05-22T10:00:00Z",
  "updated_at": "2026-05-22T10:15:00Z",
  "resolved_stages": ["bids", "preprocess", "ica", "epoch", "erp", "stats", "figure", "report", "audit"],
  "completed_stages": [
    {"stage": "bids", "status": "done", "duration_s": 12.3, "started_at": "...", "finished_at": "..."},
    {"stage": "preprocess", "status": "done", "duration_s": 45.1, "started_at": "...", "finished_at": "..."}
  ],
  "current_stage": "ica",
  "current_stage_started_at": "2026-05-22T10:01:00Z",
  "failed_stages": [],
  "skipped_stages": ["source"],
  "auto_proceed": true,
  "fail_fast": false
}
```

**Update rules**:
- Write `PIPELINE_STATE.json` at the start of the pipeline with `resolved_stages`.
- Before each stage: update `current_stage` and `current_stage_started_at`.
- After each stage: append to `completed_stages` with timing, update `updated_at`.
- On failure: append to `failed_stages` with error message.
- On crash recovery: read the file, skip `completed_stages`, resume from `current_stage`.

### C. Stage chain

For each stage in resolved list, in order:

1. **Update state**: Write `current_stage` to `PIPELINE_STATE.json`.
2. **Record start time**: `stage_start = now()`.
3. **Invoke skill**: Use the client's skill mechanism or read the matching `skills/eeg-<stage>/SKILL.md` directly, passing `[project-dir]` + relevant overrides. Keep the repository root as the working directory.
4. **Record end time**: `stage_end = now()`. Compute `duration_s = stage_end - stage_start`.
5. **Progress report**: Print to user:
   ```
   ✓ [stage] completed in [duration_s]s  ([N]/[total] stages done)
   ```
6. **Update state**: Append to `completed_stages` in `PIPELINE_STATE.json`.
7. Read the stage's report; if it reports any subject failure and `FAIL_FAST=true`, abort.
8. **Gate**: If `AUTO_PROCEED=false`, summarize the stage report to the user and wait for "go" before the next stage. If `AUTO_PROCEED=true`, proceed immediately.

### D. Audit + finalize

After all stages:
1. Invoke `eeg-audit`. Surface the audit verdict to the user.
2. Do not declare the pipeline complete unless the audit produces verdict `pass` or `pass-with-caveats`.
3. **Final timing report**: Print a summary table of all stage durations:
   ```
   Stage          Duration    Status
   ─────────────  ──────────  ──────
   bids           12.3s       done
   preprocess     45.1s       done
   ica            120.5s      done
   ...
   TOTAL          312.4s
   ```
4. Update `PIPELINE_STATE.json` with `"pipeline_status": "complete"` and total duration.

## Resume semantics

- `— from: <stage>` skips earlier stages, reading their existing artifacts. Overrides `PIPELINE_STATE.json` resume point.
- `— skip: <stage1>,<stage2>` skips specific stages entirely. They appear in `skipped_stages` in the state file.
- If `PIPELINE_STATE.json` exists and no `— from:` override, auto-resume from the last incomplete stage.
- The pipeline is **idempotent on re-run** for any stage as long as inputs haven't changed.

## Per-stage timing and progress

Every stage invocation is timed. The pipeline emits:
- **Per-stage**: `"[stage] completed in [X]s"` immediately after each stage.
- **Running total**: `"([N]/[total] stages done, elapsed [Y]s)"` after each stage.
- **Final summary**: Table of all stages with durations at pipeline end (see Phase D).

## Failure modes

| Symptom | Action |
|---|---|
| `PIPELINE_STATE.json` corrupt | Delete it, start fresh, warn user. |
| Stage times out (> TIMEOUT_SECONDS) | Log timeout in state file, surface to user, ask whether to continue. |
| `DATASET_BRIEF.md` missing + no `raw/` | Stop. Cannot auto-brief without raw data. |
| `ANALYSIS_PLAN.md` missing | Generate draft, require user confirmation before proceeding. |
| Checkpoint config missing | Default to `auto_proceed: true`, `timeout_seconds: 300`. |
| Resample requested after `epoch` / on `— from: stats` re-run | Refuse to resample Epochs (jitters event timing). Route the sample-rate change back to `preprocess` and re-run downstream stages, or reject the request. |
| Design ambiguous or `[USER]` in DATASET_BRIEF | Stop and ask. Do not default to paired — a within-subject test on mismatched subjects is a correctness error, not a default. |
| Within-subject claim but condition subject lists differ in count/order | Abort the stats branch for that claim. Paired tests require equal n and matched ordering; flag to user. |
| Reference scheme disagrees between `preprocess_summary.json` and ICA stage | Halt before `ica`. Re-run preprocess with the planned reference (and rank reduction) so ICA is not rank-deficient. |

## Domain Knowledge

- **Canonical cross-stage order is filter → resample → epoch, with re-reference deferable until after ICA.** A widely used EEGLAB preprocessing checklist orders steps as: format convert → channel locations → drop unused electrodes → filter → resample → epoch+baseline → bad-segment/channel handling → ICA → drop artifact ICs → extreme-value rejection → re-reference → manual browse. The key transferable facts: filter the *continuous* data before resampling, and re-referencing can be the second-to-last step so the reference does not mix removed artifacts back in. The MNE-Python preprocessing tutorials give the same spirit: notch → band-pass → mark bads → interpolate → ICA → re-reference → epoch. (EEGLAB 12-step preprocessing checklist; MNE-Python preprocessing tutorials, https://mne.tools/stable/auto_tutorials/preprocessing/index.html.)
- **Within- vs between-subject changes the test statistic AND the grouping.** FieldTrip encodes the design as a 2-row matrix (row 1 = subject id `cfg.uvar`, row 2 = condition `cfg.ivar`) and uses `ft_statfun_depsamplesT` for paired and `ft_statfun_indepsamplesT` for independent (Maris & Oostenveld, J. Neurosci. Methods 2007, 164(1):177-190). The MNE analog: within-subject = compute the per-subject condition difference and run `spatio_temporal_cluster_1samp_test` (one-sample on the difference; the subject pairing is implicit); between-subject = `spatio_temporal_cluster_test` on two independent arrays. Per-point tests mirror this with `scipy.stats.ttest_rel` (within) vs `ttest_ind` (between). Paired tests require equal n and matched ordering; independent tests allow unequal n.
- **Optional non-destructive ("lossless") mode separates annotation from rejection.** By default the pipeline bakes one irreversible cleaning decision into `preprocess`/`ica`. An alternative, drop-in for MNE-based runs, is to split artifact handling into two phases: a non-destructive **annotation** phase that only writes flags onto the *continuous* data (bad channels, bad time segments, the ICA decomposition with per-IC labels) and leaves the signal otherwise intact, and a destructive **rejection** phase applied separately by each downstream analysis according to its own policy. The shareable intermediate is then a single annotated continuous-data state, and different analyses (or different analysts) apply their own rejection on top of it. This is what makes the multiverse / analyst-specific reruns (see `eeg-report`) feasible from one curated intermediate rather than re-running preprocessing per fork. Implemented by PyLossless, which follows this annotate-then-reject design. To enable, run `preprocess`/`ica` in annotate-only mode and defer rejection to the analysis branches. (Huberty et al., 2024, bioRxiv 2024.01.12.575323, PyLossless; Desjardins et al., 2021, J. Neurosci. Methods 347:108961.)

## Cross-references

- See each child skill's own SKILL.md for stage-specific behavior.
- Read `AGENT_GUIDE.md` for the project-layout convention.
- Checkpoint config: `~/.claude/checkpoint.json`.
