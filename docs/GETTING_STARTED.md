# Getting started

AEA is a library of EEG analysis skills and recipes with MNE-Python as its main
execution backend. An agent reads the skills, writes analysis code, runs it in your
Python environment, and records the results in a study directory. The skills are
instructions for the agent; they are not shell commands or a standalone EEG application.

## 1. Prepare the software

You need Git, Conda or Miniconda, and a local agent client that can read files and
run commands. Install and sign in to Codex CLI or Claude Code using its own setup
instructions. AEA does not install a client, supply model access, or configure
credentials. The analysis environment below is separate from the agent's model
subscription or API access.

This guide describes `main`. See [versions and changes](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/CHANGELOG.md#choose-a-version)
to choose the fixed v0.3.2 snapshot or update an existing checkout.

Run these commands in a terminal:

```bash
git clone https://github.com/dengzhe-hou/auto-eeg-analysis.git
cd auto-eeg-analysis
conda env create -f environment.yml
conda activate aeais
```

On Linux x86_64, replace the environment creation command with
`conda env create -f tools/env/environment-pinned.yml` to use the tested package versions.
This snapshot has been rebuilt in a separate Linux environment; it is not a
cross-platform lock. Other platforms can use `environment.yml`, then capture the
installed environment with their [saved analysis](REPLAY.md).

Keep the agent's working directory at the **AEA repository root**. Skills refer to
`tools/`, `templates/`, and `recipes/` there. Put each study in its own directory,
such as `projects/my-study/`, and pass that path to the skill.

## 2. Make the skills visible to your client

Choose the command for your client:

```bash
python tools/install_skills.py --agent codex
```

```bash
python tools/install_skills.py --agent claude
```

Use `--agent both` if you use both clients. The installer creates repository-local
links from `.agents/skills/` for Codex or `.claude/skills/` for Claude Code to the
original `skills/` directories. These are the clients' documented discovery
locations; both support linked skill directories. See the official
[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) and
[Claude Code skill documentation](https://code.claude.com/docs/en/skills).

The installer leaves an existing link to the same skill unchanged. If a destination
already contains a different directory or link, it reports the conflict and leaves
that item intact. Move the conflicting item before retrying. Links track edits and
updates to existing skills automatically; rerun the installer after pulling a
version that adds new skills.

On Windows, creating directory links requires symlink permission, for example with
Developer Mode enabled or an appropriately privileged terminal. Alternatively, run
the checkout, environment, installer, and client together inside WSL. A failed link
installation reports an error and does not silently copy the skills.

## 3. Check the analysis environment

On macOS or Linux, from the activated `aeais` environment:

```bash
bash tools/env/check_env.sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools/env/check_env.ps1
```

The probe writes `ENVIRONMENT.json` in the repository root. Check that MNE is
available. Missing optional packages are listed separately; install the packages
needed by your chosen analysis, then rerun the probe. The default environment
includes MNE, mne-icalabel with ONNX Runtime, AutoReject, Pycrostates,
mne-connectivity, and pyprep. MATLAB, EEGLAB, FieldTrip, and FreeSurfer are optional.
See [platform setup](PLATFORM_SUPPORT.md) for details.

This small check exercises the documented library calls on synthetic data:

```bash
conda run -n aeais python -m pytest tools/tests/test_skill_apis.py -q
```

It needs no EEG download or model call. Checks requiring absent optional packages
are skipped. This verifies the installed library interfaces, not your study's
scientific results. For the full repository checks, run:

```bash
conda run -n aeais python -m pytest tools/tests/ recipes/
```

Data-dependent tests can skip when their datasets are absent. The MNE sample
regression tests download data only when `AEA_FETCH_DATA=1` is explicitly set;
reuse an existing dataset cache before opting into that download.

## 4. Prepare a study directory

Create a directory with this layout:

```text
projects/my-study/
  raw/
    subject-01.edf
    subject-02.edf
```

The header scanner reads `.bdf`, `.edf`, `.set`, `.fif`, and `.vhdr` files directly
inside `raw/`. Keep companion files together, such as BrainVision `.eeg` and
`.vmrk` files or an EEGLAB `.fdt` file. For nested or BIDS data, tell the agent the
existing layout so it can use the appropriate reader and create the dataset brief.
Existing raw data can be linked into the study rather than duplicated.

You can inspect headers before opening an agent:

```bash
python tools/auto_brief.py --raw-dir projects/my-study/raw/ --out projects/my-study/DATASET_BRIEF.md --json projects/my-study/auto_brief_scan.json
```

Review the resulting `DATASET_BRIEF.md`. You must supply the experiment's meaning:
condition and event-code mapping, subject/group design, hypotheses, and any
parameters the headers cannot establish. The agent uses this brief and an agreed
`ANALYSIS_PLAN.md` to run the study.

## 5. Start one of the three workflows

Start `codex` or `claude` from the repository root in the activated environment.
In Codex CLI, use `/skills` or type `$` to select an AEA skill. In Claude Code,
type `/` followed by the skill name. Enter the following examples **inside the
client**, not in your terminal shell. If newly installed skills do not appear,
restart the client from the repository root. These invocation forms are documented
by [OpenAI](https://learn.chatgpt.com/docs/build-skills) and
[Anthropic](https://code.claude.com/docs/en/skills).

### W1 Run a recipe

For compatible Flankers data, in Codex CLI:

```text
$eeg-recipe ern-flankers --data projects/my-study
```

In Claude Code:

```text
/eeg-recipe ern-flankers --data projects/my-study
```

Choose a recipe matching your paradigm from the [recipe library](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/recipes/README.md).
The skill checks the required channels, sampling rate, events, and trial counts,
asks about missing information, and waits for confirmation before running the
pipeline. A recipe's certified reference configuration may differ from its full
analysis workflow; read its numerical-specification note when reproducing benchmark
values.

### W2 Design a custom analysis

```text
Use eeg-pipeline for projects/my-study. Read the raw data headers, help me fill
DATASET_BRIEF.md, and draft ANALYSIS_PLAN.md for my attention experiment.
Use MNE-Python and wait for me to approve the plan before running the analysis.
```

Describe your paradigm, event meanings, hypotheses, and group design. The plan
determines which analysis branches and statistics run.

### W3 Audit an existing analysis

```text
Use eeg-audit on projects/my-study in adversarial reviewer mode.
```

This workflow reads the existing plan, statistical JSON, findings, report, captions,
and backend logs. Its independent model review requires a separately configured
reviewer connection. The default is a fresh, read-only Codex CLI process. Complete
the setup below before W1's default audit or W3. Existing configured MCP and
`llm-chat` connections remain alternatives.

### Configure the reviewer

Install [Codex CLI](https://learn.chatgpt.com/docs/cli) on the machine running the
analysis agent, even if that agent is Claude Code. In your terminal, check the
installation and sign in:

```bash
codex --version
codex login
codex login status
```

Use an account with access to the selected reviewer model, currently `gpt-6-astra`.
The audit uses a model call and consumes that account's usage. This setup needs no
MCP registration. Keep Codex on the command path available to your analysis agent.
Do not put credentials into a study directory or commit them to the repository.

Then ask your analysis agent:

```text
Use eeg-audit on projects/my-study with reviewer: codex-cli.
Build the audit bundle, then use a fresh codex exec process with gpt-6-astra,
max effort, and a read-only sandbox. Save the prompt, response, event log,
and exit status in audit-stage, and write the audit report from that response.
```

The [skill's invocation instructions](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-audit/SKILL.md#invocation-pattern)
give the exact command and output files. It closes stdin, waits for completion,
and checks the exit code and JSON before reporting a verdict. On native Windows,
the agent can launch the same command through Python with `stdin=subprocess.DEVNULL`;
Bash/WSL uses `< /dev/null`. If authentication, model access, or execution fails,
the audit remains incomplete and the error log explains the next setup step.
See OpenAI's [non-interactive mode documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
for authentication and output handling.

### Use another file-aware agent

You can give an agent the source file directly when it does not have a compatible
skill selector:

```text
Read skills/eeg-recipe/SKILL.md and follow it for ern-flankers with
--data projects/my-study. Keep the AEA repository as the working directory.
Read the referenced child SKILL.md files when a stage calls for them.
Use the aeais environment for Python commands.
```

The client still needs local file access, command execution, and a configured
reviewer for the audit stage. This entry point does not establish that the client
has been evaluated end-to-end.

## Choose skills for a task

Use the tasks in your approved plan. This table is a starting point; each linked
skill specifies its required inputs, full parameters and output files. Record the
resolved choices in the [dataset brief](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/DATASET_BRIEF.md) and
[analysis plan](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/ANALYSIS_PLAN.md) before execution.

| Task | Skills | Choices to supply or approve | Main outputs |
|---|---|---|---|
| Clean recordings and inspect quality | [Preprocessing](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-preprocess/SKILL.md), [ICA](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-ica/SKILL.md), [QC](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-qc/SKILL.md) | Filters, reference, bad-channel/artifact policy, ICA exclusions and QC gates | Cleaned EEG, processing summaries and `qc-stage/` reports |
| Measure event-related potentials | [Epoching](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-epoch/SKILL.md), [ERP](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-erp/SKILL.md) | Event-to-condition mapping, epoch/baseline windows, rejection, ROI, component window and measurement | Epochs, participant averages and `erp-stage/component_measures.csv` |
| Examine power over time | [Time-frequency](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-tfr/SKILL.md) | Conditions, frequencies, method/cycles, baseline window and normalization | `tfr-stage/` power and inter-trial coherence HDF5 files |
| Measure spectral power | [Spectral](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-spectral/SKILL.md) | Frequency bands, estimator, segment length, taper, overlap and any aperiodic-fit range | `spectral-stage/` arrays and parameter/summary JSON |
| Estimate connectivity | [Connectivity](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-connectivity/SKILL.md) | Metric, sensor/source space, channel/ROI pairs, bands, time range and trial matching | `connectivity-stage/` matrices and requested graph summaries |
| Test a planned contrast | [Statistics](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-stats/SKILL.md) | Observation unit and pairing, contrast, ROI/window, test/tail, correction, permutations and seed | `stats-stage/` statistical JSON, arrays and findings |
| Prepare figures and a report | [Figures](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-figure/SKILL.md), [Report](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/skills/eeg-report/SKILL.md) | Figure plan, data sources, units, uncertainty bands and output layout | SVG/PNG figures, captions and `report-stage/` HTML/Markdown |

ERP and time-frequency tasks read cleaned epochs; statistics and figures read the
matching participant-level outputs. The pipeline arranges these dependencies.
See [worked examples](EXAMPLES.md#adapt-a-recipe-to-your-study) for a complete case and how to adapt its brief
and plan to another study. The [coverage page](CERTIFICATION_LEVELS.md) records
which outputs have numerical evidence.

## Find the outputs and validation evidence

Analysis outputs belong to the study directory: stage-specific folders such as
`preprocess-stage/`, `erp-stage/`, `stats-stage/`, `figure-stage/`, `report-stage/`,
and `audit-stage/`. The plan and run logs record what was requested and completed.

For a repeatable run, retain the generated program and configuration using the
[saved-analysis replay workflow](REPLAY.md). It captures installed versions and
runs the saved code without another model call. The [archived external-use protocol](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/docs/FIRST_EXTERNAL_TEST.md)
explains how to record an independent run on your own data.

MNE is the main execution and certification reference backend. EEGLAB and FieldTrip
provide cross-toolbox comparisons and selectable paths for the capabilities listed
in [the backend registry](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/tools/env/backends.json). Availability, API tests, and
numerical certification describe different evidence. See
[certification coverage](CERTIFICATION_LEVELS.md) and the
[benchmark record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/docs/BENCHMARK.md) for the measured configurations and tolerances.

## Troubleshooting

| Symptom | Next step |
|---|---|
| Skills do not appear in the client | [Install the links](#2-make-the-skills-visible-to-your-client), then restart the client from the AEA repository root. |
| Windows cannot create skill links | Enable symlink permission or run the full setup inside WSL; see [skill installation](#2-make-the-skills-visible-to-your-client). |
| A requested package or backend is missing | Check the active environment, install the selected analysis's dependencies and rerun the [environment probe](#3-check-the-analysis-environment). See [optional packages](PLATFORM_SUPPORT.md#known-gotchas). |
| Windows crashes during LAPACK/SVD | Activate the environment or use `conda run`; see [Windows environment activation](PLATFORM_SUPPORT.md#windows-environment-activation). |
| Raw files are not found or cannot be read | The header scanner expects files directly in `raw/`; retain companion files and describe nested/BIDS layouts as in [study preparation](#4-prepare-a-study-directory). |
| The audit fails at login or model access | Check `codex login status`, model access and the command path in [reviewer setup](#configure-the-reviewer). Keep the failed audit's error log. |
| Replay refuses an existing output directory | Choose a new empty output directory and keep the captured bundle unchanged; see [capture and execute](REPLAY.md#capture-and-execute). |
| The N400 figure exporter requests a font | Install Arial or Helvetica as described in the [N400 example](EXAMPLES.md#erp-core-complete-n400-recipe-case). |

If the problem persists, [open an issue](https://github.com/dengzhe-hou/auto-eeg-analysis/issues/new)
with the command, error, environment and minimal shareable example listed in
[Contributing](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/CONTRIBUTING.md#contribute-a-tool-document-or-fix).
