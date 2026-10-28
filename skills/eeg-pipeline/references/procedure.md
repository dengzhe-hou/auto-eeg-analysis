## Constants

- **AUTO_PROCEED** — read from `~/.claude/checkpoint.json`. If `auto_proceed: true` and the gate is `"auto"`, run gates auto-pass. If `auto_proceed: false` or gate is `"always_wait"`, pause for user OK between stages. If `~/.claude/checkpoint.json` does not exist, default to `true`.
- **FAIL_FAST = `false`** — when `true`, abort on first per-subject failure; otherwise log and continue.
- **STAGES_DEFAULT** — preparation stages plus only the analysis branches named in the approved plan, then `stats, figure, report, audit`. ERP, TFR, connectivity, microstate and source are selected explicitly; an example stage list does not request all of them.
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

- **Sampling and event alignment.** Keep the planned sampling rate and downsampling stage; do not add resampling as an optimization. MNE's `resample` includes anti-alias filtering, whereas `decimate` does not. Raw resampling reduces event-time precision: pass the corresponding events to `raw.resample(..., events=events)` and retain their original identities. Epoch resampling is supported but needs sufficient padding to keep filtering edge effects outside the analyzed interval. For planned integer decimation after epoching, filter the continuous data with an appropriate transition band first. Record the actual rate, method and event mapping; missing prerequisites block this step. See [MNE resampling guidance](https://mne.tools/stable/auto_tutorials/preprocessing/30_filtering_resampling.html#resampling).
- **Reference / ICA-rank consistency.** Pass the actual reference state, channel order, interpolation and effective rank from preprocessing to ICA. An applied average reference reduces rank; `set_eeg_reference(projection=True)` only adds a pending projector until it is applied. Do not claim that a pending projector has already re-referenced the samples or blindly subtract one twice. Compare the ICA fitting input and the data to which that decomposition is applied with the approved configuration.

## Phases

### A. Pre-flight (mandatory)
1. **Checkpoint config**: Read `~/.claude/checkpoint.json`. Set `AUTO_PROCEED` and `TIMEOUT_SECONDS` from the file. If file missing, default `AUTO_PROCEED=true`, `TIMEOUT_SECONDS=300`.
2. **Auto-brief**: If `DATASET_BRIEF.md` does not exist but `raw/` does, run `python tools/auto_brief.py --raw-dir <project-dir>/raw/ --out <project-dir>/DATASET_BRIEF.md --json <project-dir>/auto_brief_scan.json`. Then ask the user conversationally about remaining `[USER]` fields (paradigm, condition→marker mapping, epoch window, hypothesis). Do NOT dump the full template.
3. Read `DATASET_BRIEF.md`. Resolve scientific fields against the approved plan, including events, blocks, channel roles and coordinate units, filtering, reference, epoch/baseline, inclusion rules and statistics. A suggested bandpass, reference or test is not a non-critical execution default. Ask about unresolved fields in an interactive run; use the blocked-work record above in an unattended run.
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
  "run_dir": "/path/to/project/results/run-001",
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
  "unresolved_decisions": [],
  "skipped_stages": ["source"],
  "auto_proceed": true,
  "fail_fast": false
}
```

**Update rules**:
- Write `PIPELINE_STATE.json` at the start of the pipeline with `resolved_stages`.
- Record `run_dir` before executing any stage. Resume and `— from:` reuse that
  directory and its prerequisite artifacts; never assign them a new empty root.
- Before each stage: update `current_stage` and `current_stage_started_at`.
- After each stage: append to `completed_stages` with timing, update `updated_at`.
- On failure: append to `failed_stages` with error message.
- On crash recovery: read the file, skip `completed_stages`, resume from `current_stage`.

### C. Stage chain

For a new complete analysis, choose a new `<run-dir>` such as
`<project-dir>/results/run-001` and record it in `PIPELINE_STATE.json`. For resume
or `— from:`, reuse the recorded run directory. If an older state lacks that path,
identify the existing directory containing its prerequisite stage outputs before
continuing; do not infer that an empty new directory contains completed stages. Copy the
approved plan, dataset brief and environment probe there. All child skills use
this run directory as their study root, with stage folders beneath it; raw data
remain at their original location.

Before executing each scientific stage, save its program, local helpers and
configuration in `<project-dir>/analysis/`. Add its exact argument list to
`analysis/run.json` following `docs/REPLAY.md`: `{data}` is the raw-data location,
`{out}` is this run directory. Read the child skill to prepare the code, then run
that saved program once with these substitutions from the `analysis/` directory.
Do not execute a second copy through inline code. Preserve the normal stage
checkpoints below. Record seeds and all scientific settings in the saved files.
Model-based review and interpretation stay outside the computational manifest.

For each scientific stage in the resolved list, in order (methods/report/audit run in Phase D):

1. **Update state**: Write `current_stage` to `PIPELINE_STATE.json`.
2. **Record start time**: `stage_start = now()`.
3. **Invoke skill**: Use the client's skill mechanism or read the matching `skills/eeg-<stage>/SKILL.md` directly, passing `<run-dir>` + relevant overrides. The agent stays at the repository root; saved programs execute from `analysis/` as specified above.
4. **Record end time**: `stage_end = now()`. Compute `duration_s = stage_end - stage_start`.
5. **Progress report**: Print to user:
   ```
   ✓ [stage] completed in [duration_s]s  ([N]/[total] stages done)
   ```
6. **Update state**: Append to `completed_stages` only after the required artifacts exist and the stage's direct checks pass. Retain the artifact paths and check result with the stage record; an agent's completion message alone is insufficient.
7. Read the stage's report; if it reports any subject failure and `FAIL_FAST=true`, abort.
8. **Gate**: Follow the user's authorized execution mode. Interactive checkpoints can pause for review; an explicitly unattended run advances approved steps automatically and records unresolved decisions as blocked work. A checkpoint setting cannot approve new scientific choices.

### D. Audit + finalize

After all stages:
0. Capture the actually executed `analysis/` with `tools/replay.py capture`, then
   replay it into a second, new output directory. Compare that repeat against the
   first run's scientific outputs using the approved plan's tolerances. Retain the
   fieldwise comparison. Do not regenerate programs between these runs; record a
   failed or missing comparison without calling it reproducible.
1. Invoke methods-text/report and `eeg-audit` on the original `<run-dir>`, where the
   copied plan and first run's stage outputs live. Surface the audit verdict.
   Keep deterministic numeric and report checks alongside that review; a model
   verdict does not replace independent recomputation or artifact comparison.
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

- `— from: <stage>` skips earlier stages, reading their existing artifacts from the recorded `run_dir`. Overrides the resume point, not the result directory.
- `— skip: <stage1>,<stage2>` skips specific stages entirely. They appear in `skipped_stages` in the state file.
- If `PIPELINE_STATE.json` exists and no `— from:` override, auto-resume from the last incomplete stage.
- Re-runs preserve the approved inputs and parameters and retain their comparison results. Fixed seeds alone do not guarantee identical ICA fits or outputs across environments; preserve a failed comparison instead of assuming idempotence.

## Per-stage timing and progress

Every stage invocation is timed. The pipeline emits:
- **Per-stage**: `"[stage] completed in [X]s"` immediately after each stage.
- **Running total**: `"([N]/[total] stages done, elapsed [Y]s)"` after each stage.
- **Final summary**: Table of all stages with durations at pipeline end (see Phase D).

## Failure modes

| Symptom | Action |
|---|---|
| `PIPELINE_STATE.json` corrupt | Preserve the file and stop dependent work. Recover stage paths from retained artifacts before resuming; do not erase the execution record. |
| Stage times out (> TIMEOUT_SECONDS) | Preserve the failure and record incomplete work. Follow the approved retry rule; in an unattended run do not wait for a new decision or invent a larger budget. |
| `DATASET_BRIEF.md` missing + no `raw/` | Stop. Cannot auto-brief without raw data. |
| `ANALYSIS_PLAN.md` missing | Generate draft, require user confirmation before proceeding. |
| Checkpoint config missing | Default to `auto_proceed: true`, `timeout_seconds: 300`. |
| Sampling-rate change during resume | Keep the frozen rate unless the user approves a changed plan. Execute an approved change at its specified stage with the event-alignment and edge-effect precautions above, then rebuild affected downstream outputs. |
| Design ambiguous or `[USER]` in DATASET_BRIEF | Stop and ask. Do not default to paired — a within-subject test on mismatched subjects is a correctness error, not a default. |
| Within-subject claim but condition subject lists differ in count/order | Abort the stats branch for that claim. Paired tests require equal n and matched ordering; flag to user. |
| Reference scheme disagrees between `preprocess_summary.json` and ICA stage | Halt the dependent stage. Restore the planned fitting/application configuration and record its effective rank; an approved average reference can legitimately make the data rank deficient. |
