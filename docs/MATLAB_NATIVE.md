# Use AEA with MATLAB and EEGLAB

This preview route keeps study preparation and the bounded ERP calculation
in MATLAB/EEGLAB. Python, MNE and MATLAB Engine for Python are not required.
Codex CLI or Claude Code reads the same AEA resource files and writes study-local
MATLAB code. The researcher still approves scientific choices.

This route is in the **[0.1.3 preview](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/eeglab-v0.1.3-preview)** and is not included in the
older 0.1.2 ZIP. The first native helper covers means from existing epochs, explicit
condition epoch lists, an ROI, a time window, figures and an HTML report. Other
skills have not all been translated or validated in MATLAB. Existing EEGLAB and
FieldTrip preprocessing templates remain available with their recorded scope.

## Set up the native route

1. Install MATLAB, EEGLAB and one coding client. Reuse existing installations.
   Sign in to [Codex CLI](https://learn.chatgpt.com/docs/cli) or
   [Claude Code](https://code.claude.com/docs/en/overview) in its own terminal first.
2. Download and extract the [matching AEA source ZIP](https://github.com/dengzhe-hou/auto-eeg-analysis/archive/refs/tags/eeglab-v0.1.3-preview.zip),
   or use an updated `main` checkout. The source folder supplies the skills and procedures.
   Extract the [plugin ZIP](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/download/eeglab-v0.1.3-preview/aea-eeglab-0.1.3.zip)
   into EEGLAB's `plugins` folder, yielding `plugins/aea0.1.3/`.
   Alternatively copy the checkout's `extensions/eeglab/aea` folder there.
   Keep one copy of the plugin, then restart EEGLAB.
3. Open **Tools > AEA > Settings**. Enter the checkout folder, `codex` or `claude`,
   and the working client executable path. Set **Analysis backend** to `matlab`.
   Leave **Python executable** blank for this route.
4. Load the current dataset and choose **Export current dataset and prepare study**.
   Choose a new folder. Native EEGLAB readback checks its shape and sampling rate,
   then records the runtime, paths, processing history and unresolved choices.
5. Choose **Start AEA for exported study**. The client reads `AEA_REQUEST.md` and
   the relevant skill/procedure source files directly. Native skill-directory
   registration is optional; this route does not need the Python skill installer.
6. Approve the study-local plan before dependent computation. The client creates
   and executes `.m` files, keeps its checks, and writes `report-stage/report.html`.
   Use **Open study report** when ready.

The client inherits its existing account, model, permissions and environment.
The plugin does not store credentials or choose a model. Calling a command
requests permission through the client's own policy when required. MATLAB
scripts can be run with [`matlab -batch`](https://www.mathworks.com/help/matlab/ref/matlabwindows.html).
The actual runtime and EEGLAB path are recorded in the exported study's
`ENVIRONMENT.json`; generated scripts should use those paths.

For a first native setup, the five Settings fields are:

| Field | Native MATLAB value |
| --- | --- |
| AEA checkout folder | The matching checkout containing `AGENT_GUIDE.md` |
| Python executable | Leave blank |
| Coding assistant | `codex` or `claude` |
| Assistant executable | The working local client's full executable path |
| Analysis backend | `matlab` |

On Windows, run `where.exe claude` or `where.exe codex` in a terminal to find
the client path. Complete the client's first sign-in in that terminal before
starting it from EEGLAB. No API key belongs in the AEA Settings dialog.

After choosing **Start AEA**, a first research request can be:

```text
Inspect this exported dataset and its processing history. Help me define an ERP
analysis using MATLAB/EEGLAB. Ask about missing event meanings, channels,
time windows and contrasts, and prepare a plan for my approval. Keep previously
approved choices. Generate .m scripts, retain direct checks, and save the report.
```

For an unsupported native step, the client must state the missing capability
and seek a decision. It must not silently use MNE or describe an untested
translation as equivalent. Recipe examples do not approve parameters.

## Run the fixed engineering example

After exporting the same four-epoch synthetic fixture used in the Windows
integration tests, this explicit specification reproduces its approved means:

```matlab
% Only for that fixed fixture: A/B/A/B, Cz/Pz, -0.2 to 0.8 s, 100 Hz.
spec = struct('roi', {{'Cz', 'Pz'}}, 'window_s', [0.1 0.3], ...
    'condition_names', {{'A', 'B'}}, ...
    'condition_epochs', {{[1 3], [2 4]}}, 'contrast', [2 1]);
analysis_output = fullfile(study, 'native-results'); % must not exist yet
results = aea_erp_mean(fullfile(study, 'input', 'imported.set'), analysis_output, spec);
```

For that call, use a **fresh analysis output directory**, not the existing
exported study folder. For example, set `analysis_output` to a new folder,
then call `aea_erp_mean(input_set, analysis_output, spec)`. The helper writes
`analysis_output/report-stage/report.html`. If you want the EEGLAB report menu
to open it, select `analysis_output` as the report folder.

The expected fixture values are A = 2.5 uV, B = 6.5 uV and B minus A = 4 uV.
The inclusive 0.1 to 0.3 s window has 21 samples. These values describe this
synthetic integration fixture, not a default EEG analysis plan.

The helper records the exact epoch indices and per-epoch means. It uses equal
ROI-channel weights and equal epoch weights within each condition. EEGLAB
samples remain in microvolts; there is no MNE volts-to-microvolts conversion.
It does not refilter, rereference, refit ICA, baseline-correct, reject trials or
perform statistical inference. A complete scientific workflow may require
additional approved steps.

Outputs include `results.json`, `analysis-spec.json`, `plot_data.json`,
`ENVIRONMENT.json`, SVG/PDF/600-dpi PNG figures, `report-stage/report.html` and
`run_analysis.m`. Add the output folder to the MATLAB path and call
`run_analysis(new_output_directory)` to replay the same inputs and parameters
without overwriting the first delivery. The generated entry point adds the
recorded helper, EEGLAB function tree and DIPFIT dependency paths, including
when invoked in a fresh MATLAB process.

## Choose the assistant and model

| Connection | AEA setting | What is configured separately |
| --- | --- | --- |
| Codex with its supported models | `codex` | Codex account, model and permissions |
| Claude through Claude Code | `claude` | Claude account/API, model and permissions |
| DeepSeek through Claude Code | `claude` | DeepSeek endpoint, API key and explicitly selected model |

DeepSeek's official
[Claude Code integration](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/)
uses its Anthropic-compatible endpoint. AEA does not need a third scientific
backend or a separate set of EEG skills. Keep a provider-specific launcher
separate from the normal Claude launcher so the existing Claude setup is retained.

On Windows, a local launcher such as `claude-deepseek.cmd` can contain:

```bat
@echo off
setlocal
if not defined DEEPSEEK_API_KEY exit /b 1
if not defined AEA_DEEPSEEK_MODEL exit /b 1
set "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic"
set "ANTHROPIC_AUTH_TOKEN=%DEEPSEEK_API_KEY%"
set "ANTHROPIC_API_KEY="
set "ANTHROPIC_MODEL=%AEA_DEEPSEEK_MODEL%"
set "ANTHROPIC_DEFAULT_OPUS_MODEL=%AEA_DEEPSEEK_MODEL%"
set "ANTHROPIC_DEFAULT_SONNET_MODEL=%AEA_DEEPSEEK_MODEL%"
set "ANTHROPIC_DEFAULT_HAIKU_MODEL=%AEA_DEEPSEEK_MODEL%"
set "CLAUDE_CODE_SUBAGENT_MODEL=%AEA_DEEPSEEK_MODEL%"
call "C:\path\to\claude.exe" %*
```

Replace the executable path with the working local Claude Code installation.
Provide `DEEPSEEK_API_KEY` through the local process environment and select
`AEA_DEEPSEEK_MODEL` from DeepSeek's current supported models. Do not paste keys
into the AEA study, plugin settings or Git. Start MATLAB from that configured
environment so the launcher can inherit the variables; an already-open MATLAB
process will not inherit variables set later in another terminal. Set the AEA
assistant to `claude` and its executable to this launcher. The launcher scopes
changes to its child process; it does not rewrite normal Claude settings.

This is a configuration route documented by DeepSeek. No DeepSeek API call or
end-to-end DeepSeek analysis has been tested for this native prototype. Provider
compatibility does not establish numerical accuracy, general reliability or cost.

For a complete study, also configure the
[separate reviewer](GETTING_STARTED.md#configure-the-reviewer) required by AEA's
full-workflow guidance. Selecting an analysis client does not configure that
review connection. Direct numerical and file checks remain separate from model
review; this engineering test does not invoke a reviewer model.

## Validation status

The development test `extensions/eeglab/aea/tests/test_aea_matlab.m` uses real
EEGLAB export/readback, explicit fixture arithmetic and a new-directory replay.
On 2026-10-29, the native route passed on Windows 11, MATLAB R2026a Update 2 and
EEGLAB 2026.0.0: batch arithmetic and replay, actual Settings with Python blank,
menu export, two labelled client launchers receiving the expected arguments and
working directory, and opening the actual generated report in Chrome. The
Codex/Claude launchers were test clients; no live model or provider API was used.
The original plugin, preferences and working EEG were preserved or restored.

Independent checks cover all 808 fixture samples, the 21-sample measurement
window, A = 2.5 uV, B = 6.5 uV, B minus A = 4 uV, full trace arrays and displayed
report numbers. A fresh-process replay initially failed because the generated
entry point omitted dependencies; its path initialization was repaired and
checked in fresh Octave and MATLAB processes. Numerical rules were unchanged.
The server's related test suite passes 11 tests, including a fresh-process replay.
These are engineering checks for this bounded route, separate from the older
Windows tests that actually invoked Codex and Claude on the MNE route.

A subsequent native test used the actual EEGLAB menus and real Claude Code
2.1.312 (`claude-opus-5-5`, existing `auto` permission mode). The client read AEA
skill/procedure files, wrote the study's `scripts/analysis.m` and ran MATLAB.
Independent checks of the first delivery passed. Replaying that same unchanged
entry point in a fresh MATLAB process and a new output directory also passed,
including the numerical results, full traces, SVG curves and visible report values.
EEGLAB's report menu opened that actual HTML in Chrome. Exported tick and legend
text measured about 6.75 pt rather than the plan's 7 pt; the discrepancy was
recorded without changing the analysis or drawing backend.

The client also read a test-script excerpt and documentation containing the
fixture's reference values, deviating from the requested reading restriction.
This records functional integration with a known-answer synthetic example; it
does not establish blind task performance, a benefit from skills, unattended
operation or reliability on real EEG. The original run and failures are retained.
The session includes two empty-input or `print()` Python command attempts;
EEG computation and numerical checking used MATLAB. A startup-check question
received one user reply, so the run is not described as fully unattended.

MacBook testing is left to external users. macOS desktop installation, terminal
launch and the full report route remain unverified until actual test evidence
is supplied. Report the OS/CPU, MATLAB/EEGLAB/client versions, commands, failures
and retained artifacts when contributing a platform test.
