# Replay a saved analysis

Save the program that produced the results, not just the prompt. AEA can capture
the approved code, configuration and installed package versions, then execute
that copy without an agent or a new model call.

## Prepare the analysis once

Ask the analysis agent to put all study-specific Python programs and configuration
in `projects/my-study/analysis/`. Include imported local helpers there. Programs
must read the supplied data path, write all outputs beneath the supplied output
path, and set the seeds and scientific parameters agreed in `ANALYSIS_PLAN.md`.
Keep raw data at its existing location.

Treat that output path as the study root for this run: write `preprocess-stage/`,
`stats-stage/` and the other stage folders inside it. Replay copies the captured
plan, dataset brief and available `ENVIRONMENT.json` there. Pass this same output
directory to methods-text, report and audit skills after computation, so they read
this run's results. For workflows with stage checkpoints, child skills first save and execute each
program once, recording its manifest command. Capture the completed program set
and compare its replay with that first run. When preparing all code before running,
use the two replay commands below for the first execution and its repeat. Do not
execute a second copy of the same computation through inline agent code.

Create `analysis/run.json` with the actual commands in execution order:

```json
{
  "commands": [
    ["{python}", "pipeline.py", "--config", "config.json", "--data", "{data}", "--out", "{out}"]
  ]
}
```

`pipeline.py` and `config.json` are the study's saved files, not built-in AEA
programs. Each command runs from the saved `analysis/` directory. `{python}` uses
the active interpreter; `{data}` and `{out}` supply absolute paths. Arguments are
passed directly, so paths containing spaces work without shell quoting. Include
any deliberate runtime overrides in the program/configuration. Copy required AEA
helpers into `analysis/` as well; imports must not depend on an unsaved checkout.
Keep scientific computation in this manifest. Model-based interpretation and audit
responses remain separate saved artifacts; replay does not regenerate them.

## Capture and execute

From the repository root in the analysis environment:

```bash
python tools/replay.py capture --project projects/my-study --data projects/my-study/raw --bundle projects/my-study/runs/run-001
python tools/replay.py run --bundle projects/my-study/runs/run-001 --out projects/my-study/results/run-001
python tools/replay.py run --bundle projects/my-study/runs/run-001 --out projects/my-study/results/run-001-repeat
```

Capture copies `analysis/`, the available plan, dataset brief and environment
probe, and writes:

- `capture.json`: Python/package versions, platform, AEA commit, modified tracked
  files and the original data location.
- `environment.yml`: a version-pinned Conda export, with its local prefix removed.
- `requirements.txt`: installed Python distribution versions.

Each execution writes `execution.json` and `stdout.log` beside the analysis
outputs. A failed command stops the run and returns a nonzero exit code. Existing
nonempty output directories and existing bundles are never overwritten. Keep the
bundle unchanged; revisions belong in a new bundle.

Compare the two runs' **scientific outputs** using the tolerances specified in the
plan. Record the compared fields, maximum differences, tolerances and pass/fail
result. Timestamps and output paths naturally differ. Successful execution alone
does not establish numerical agreement or scientific correctness.

## Restore on another machine

Transfer the bundle and arrange access to the same input data. From an AEA checkout:

```bash
conda env create -n study-replay -f /path/to/run-001/environment.yml
conda activate study-replay
python tools/replay.py run --bundle /path/to/run-001 --data /current/raw/location --out /new/results/location
```

Replay checks the captured Python and Python package versions before running.
Extra packages are allowed. Missing or changed versions produce an error identifying
the mismatch. Restore the recorded environment rather than silently changing it.
The export preserves package versions, not binary builds; platform-specific packages
may require the original OS/architecture. Platform differences are recorded and
numerical agreement still needs checking. Editable installs, external executables
and external model assets must be preserved separately when the analysis uses them.

For a new Linux x86_64 installation, the repository's `environment-pinned.yml`
provides a tested version snapshot. `environment.yml` remains the general setup
specification. A study's own captured environment is the reference for its replay.
