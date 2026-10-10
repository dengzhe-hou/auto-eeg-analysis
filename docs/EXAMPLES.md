# Worked examples

Choose how you want to try N400:

| Goal | What you need | Start here |
|---|---|---|
| Replot saved results | Python environment and figure fonts; no raw EEG or LLM | [Replot](#replot-the-saved-results) |
| Run the fixed tutorial | Python environment, figure fonts, Git clone with v0.3.2 tag and ERP CORE data; no LLM | [Complete N400 example](#erp-core-complete-n400-recipe-case) |
| Use a coding agent | The analysis environment, data, signed-in client, installed skills and configured reviewer | [N400 dataset brief](#adapt-a-recipe-to-your-study) |

For the first two routes, complete only [Python environment setup](GETTING_STARTED.md#1-prepare-the-software)
and [the environment check](GETTING_STARTED.md#2-check-the-analysis-environment),
then return here. Client installation and model access are needed for the agent route.
Raw EEG and cached epochs are not distributed; `projects/` is your local workspace.
Run from the repository root, reuse data caches and choose a new output directory.

## Prepare the figure fonts

The figures use Arial or Helvetica. These fonts are not installed by the Conda
environment. Check availability from the repository root with `aeais` active:

```bash
python -c "import sys; sys.path.insert(0, 'tools/examples'); from plot_style import figure_style; print(figure_style()['font.sans-serif'][0])"
```

If it prints `Arial` or `Helvetica`, continue. Otherwise install an available copy
of either font on the machine running Python:

- **Windows:** open the font file and select Install, as in [Microsoft's guide](https://support.microsoft.com/en-us/windows/experience/personalization/manage-fonts-in-windows).
- **macOS:** install it in [Font Book](https://support.apple.com/guide/font-book/install-and-validate-fonts-fntbk1000/mac).
- **Linux or WSL:** put the font files in `~/.local/share/fonts/` and run `fc-cache -f`. For WSL, install inside Linux; installing in Windows alone does not supply the Linux font directory. [Fontconfig](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html) describes its font locations.

If a newly installed font is still missing, close Python and clear Matplotlib's
cached font list, then run the check again in a new Python process:

```bash
python -c "from pathlib import Path; import matplotlib; [p.unlink() for p in Path(matplotlib.get_cachedir()).glob('fontlist-v*.json')]"
```

The complete runner checks these fonts before reading EEG or creating its output
directory. Statistical `--replay` does not render figures and needs no fonts.

## Replot the saved results

Start here to inspect a complete output without downloading source EEG or using an
LLM. After [checking the figure fonts](#prepare-the-figure-fonts), run:

```bash
python tools/examples/gen_recipe_case_figures.py --run-dir projects/n400-recipe-figure --figure-data tools/examples/n400/recipe_case_figure_data.npz --summary tools/examples/n400/recipe_case_results.json
```

The three panels show condition/difference ERPs, a descriptive scalp map and all
participant amplitudes. Files appear in `projects/n400-recipe-figure/figure-stage/`
as `F1_n400_recipe.pdf`, `.svg` (editable text), `.png` (600 dpi) and a caption.
These are saved result arrays, not a new preprocessing or agent run.

## Prepare the N400 data

The [ERP CORE authors](https://erpinfo.org/erp-core) provide the dataset through
[OSF](https://osf.io/thsqg/). Choose
[BIDS-Compatible Raw Files](https://osf.io/9f5w7/), then `ERP_CORE_BIDS_Raw_Files`.
Reuse an existing local copy first. Otherwise download the root metadata and the
N400 files under `sub-001` through `sub-020` only, retaining their directory names:

```text
ERP_CORE_BIDS_Raw_Files/
  dataset_description.json, participants.tsv, participants.json
  task-N400_events.json, README, LICENSE
  sub-001/ses-N400/eeg/
    sub-001_ses-N400_task-N400_eeg.set
    sub-001_ses-N400_task-N400_eeg.fdt
    sub-001_ses-N400_task-N400_events.tsv
    sub-001_ses-N400_task-N400_eeg.json
    sub-001_ses-N400_task-N400_channels.tsv
    sub-001_ses-N400_task-N400_electrodes.tsv
    sub-001_ses-N400_task-N400_coordsystem.json
  ... through sub-020
```

Keep each `.set` with its external `.fdt`; the `.set` alone is insufficient. The
runner reads EEG from `.set`/`.fdt` and event `onset` (seconds) and numeric `value`
from `events.tsv`. Retain the sidecars to interpret channels, coordinates and
marker meanings. The separate non-BIDS raw/processed downloads have different
names and are not inputs to this runner.

Pass `ERP_CORE_BIDS_Raw_Files` directly to the runner. It reads the official
`sub-001/ses-N400/eeg/sub-001_ses-N400_task-N400_*` layout and existing caches with
`sub-001/eeg/sub-001_task-N400_*`. No renaming, copying or input-link view is needed.

## ERP CORE: complete N400 recipe case

This post-release example follows the [N400 recipe](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/recipes/n400-semantic/RECIPE.md)
from `v0.3.2` on the fixed 20-participant ERP CORE cohort. Its documented benchmark
branch omits ICA and amplitude rejection. The primary cluster test uses the recipe's
CPz/Cz/Pz ROI and 300–500 ms window. All participants retained 60 trials per condition;
the mean unrelated-minus-related amplitude was −2.957 µV (SEM 0.466), with one cluster
at p = 0.0002. This ROI test is separate from the historical all-channel certification.
See the [complete numerical record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/tools/examples/n400/recipe_case_results.json).

Pass the dataset root (or your existing compatible cache) as `--data-root`,
and choose a fresh run directory. The runner downloads nothing. A Git clone with the
`v0.3.2` tag is required because it saves that recipe alongside the executed program.
These tutorial scripts are available on `main` and were added after v0.3.2.
Complete the [font check](#prepare-the-figure-fonts) before the full run, which also
renders figures. Before reading EEG or creating outputs, the full runner checks
that all 20 participants have a `.set`, its companion `.fdt` and matching
`events.tsv`, in either supported layout above. This checks file presence only;
it does not establish data validity.

```bash
python tools/examples/run_recipe_case.py --data-root /path/to/ERP_CORE_BIDS_Raw_Files --run-dir projects/n400-recipe-case/runs/run-001
python tools/examples/run_recipe_case.py --run-dir projects/n400-recipe-case/runs/run-001 --replay
```

The full run prints stage messages like these, repeating the subject stage for all 20 participants:

```text
[inputs] Checking files for 20 participants...
[subject 1/20] sub-001: preprocessing, epochs and averages...
...
[statistics] Computing group clusters (5000 permutations)...
[replay] Checking saved group statistics (5000 permutations)...
[figures] Rendering figures...
[report] Saving methods and summary...
```

The run saves the brief, frozen plan, program, preprocessed EEG, epochs, averages,
statistics, figures and methods. Start inspection at `stats-stage/summary.json`,
`figure-stage/F1_n400_recipe.png` and `report-stage/methods.md`; the run's `plan.json`
records the full configuration. Completion means the terminal reports
`"status": "complete"`, `process.json` has `"exit_code": 0`, and the run directory's
`summary.json` has `"status": "complete"` and `"required_stages_complete": true`.
The replay check in `audit-stage/replay.json` must have `"passed": true`.

Replay checks group statistics from saved participant averages, without repeating
preprocessing. In the retained run, t maps, cluster masks, p values and permutation
null values were identical. This is an internal worked example, not an estimate of
LLM success rate or time savings.

### If the full run fails

Keep `run-001`, its `process.json` when created, and the terminal error. Fix the
reported problem, then use a fresh directory to rerun all 20 participants:

```bash
python tools/examples/run_recipe_case.py --data-root /path/to/ERP_CORE_BIDS_Raw_Files --run-dir projects/n400-recipe-case/runs/run-002
```

`--replay` only recomputes group statistics from a completed run's saved arrays;
it does not resume interrupted preprocessing or finish figures and reports.

## Adapt a recipe to your study

This route uses a coding agent, rather than the fixed Python runner. Complete
[agent setup](GETTING_STARTED.md#3-set-up-an-agent-optional), including its reviewer.
Create `projects/n400-agent/` and save the following as its `DATASET_BRIEF.md`.
Replace the raw-data path with the absolute path to your existing ERP CORE root;
keep the source files there, outside the study directory.

```markdown
# ERP CORE N400 dataset brief

- Study directory: projects/n400-agent
- Raw data root: /absolute/path/to/ERP_CORE_BIDS_Raw_Files (read only)
- Source: ERP CORE BIDS-Compatible Raw Files, https://osf.io/9f5w7/
- Recipe: n400-semantic
- Participants: sub-001 through sub-020, selected before analysis
- Design: within participant; participant is the independent observation
- Layout: sub-NNN/ses-N400/eeg/sub-NNN_ses-N400_task-N400_*
- Input: .set with companion .fdt; matching events.tsv and BIDS sidecars
- Expected recording: 30 scalp EEG channels plus 3 EOG channels at 1024 Hz;
  verify the headers and coordinate units against the source sidecars
- Event timing: events.tsv onset in seconds; codes in numeric value column
- Time lock: target words, not primes or responses
- Related targets: 211 and 212
- Unrelated targets: 221 and 222
- Exclude from target epochs: prime codes 111, 112, 121 and 122, and responses
- Question: do unrelated targets evoke a more negative N400 than related targets?
- Primary contrast: unrelated minus related
- ROI and window: CPz, Cz, Pz; 300–500 ms after the target
- Plan status: not approved; propose cleaning and statistical settings,
  list unresolved choices and wait for researcher approval before analysis
```

The generic `auto_brief` scanner reads only the top level of `raw/`; do not point it
at this nested BIDS root. The agent should read the saved brief, inspect the nested
EEG headers and matching events directly, and draft an
[analysis plan](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/ANALYSIS_PLAN.md).
From the repository root with `aeais` active, enter this inside Codex:

```text
$eeg-recipe n400-semantic --data projects/n400-agent
Read projects/n400-agent/DATASET_BRIEF.md and use its external raw-data root without moving the data.
Inspect the nested BIDS files directly. Draft the plan, list unresolved choices,
and stop for my approval before analyzing EEG.
```

In Claude Code, use `/eeg-recipe` instead of `$eeg-recipe`. For your own recordings,
adapt the [general dataset brief](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/DATASET_BRIEF.md),
participants, event mapping, hypothesis, ROI and window to your design.
The recorded N400 agent workflow illustrates the three steps below; the new brief
does not approve that run's cleaning choices for your analysis.

| Step | Researcher and agent actions | What to inspect |
|---|---|---|
| Research request | Supply the data paths, participants, event mapping and hypothesis in the brief above | Target timing and condition counts; 211/212 related, 221/222 unrelated |
| Researcher approval | Review the agent's plan and freeze contrast, ROI/window, cleaning, eligibility and statistical settings | `ANALYSIS_PLAN.md`; ambiguous ICA components need a further response |
| Generated code and results | The agent writes and runs scripts for preprocessing → ICA → epochs → ERP → statistics → figures/report, retaining the outputs | Scripts and commands, participant counts, condition averages, statistics, figures, methods, review records and saved-program replay comparison |

In the recorded agent run, the researcher approved ICA plus local AutoReject and
native 1024 Hz sampling. The plan fixed a 0.1–30 Hz filter, −200 to 800 ms epochs,
−200 to 0 ms baseline, at least 30 retained targets per condition, and a negative-tailed
group cluster test with 5,000 permutations and seed 42 in the stated ROI/window.
Ambiguous ICA components required a further researcher
response. These choices differ from the fixed no-ICA, 256 Hz tutorial above, so its
numerical results are not the agent run's results. A new study likewise needs its
own approved plan and checks; changing event labels alone does not validate it.

## Earlier examples

The examples below are historical records, rather than current tutorial commands.
Their original plans, scripts, positive and null results, corrections and audits are
retained in existing Git history.

### MNE sample: auditory versus visual N100

The corrected single-participant analysis uses 61 complete stimulus cycles (244 trials)
and six ROI electrodes with 3–27 mm location differences. Auditory minus visual
amplitude was −1.54 µV, paired-cycle Cohen's d_z = −0.462, with one cluster at
p = .0004 (5,000 permutations). Shading in the figure is ±1 SEM across cycles.
Original target-epoch retention was 289/289; the correction separately excluded
45 target trials in incomplete cycles, rather than rejecting them as artifacts.
Fixed stimulus order confounds condition with cycle position. The sign-flip test
assumes independent, symmetric cycle differences and does not establish a population effect.

[Corrected record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/mne-sample-audvis/REANALYSIS.md) ·
[result JSON](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/mne-sample-audvis/REANALYSIS.json) ·
[corrected figure](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/assets/n100-case-study-corrected.png) ·
[original figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/docs/assets/n100-case-study.png) ·
[historical instructions and commands](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/EXAMPLES.md#mne-sample-auditory-versus-visual-n100).

The [preparation](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/tools/prepare_sample_case.py),
[analysis](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/tools/run_fix_audit.py), and
[plotting](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/tools/gen_case_study_figures.py)
scripts remain in that snapshot. The published correction reused saved epochs;
preparation refits ICA and requires numerical comparison before treating a new run as the same result.

### ERP CORE: Flankers conflict processing

The corrected Subject-001 example retains all three planned contrasts. Minimum
cluster p values were N2 .0588 (d = −0.062), response-locked conflict .0006
(d = −0.316), and theta .0002 (d = 0.295): two pass p < .05/3. All retained trials
enter 5,000 permutations restricted by block × target side. Theta uses joint
frequency × time × electrode clusters. The response contrast is incompatible minus
compatible, separate from canonical error-minus-correct ERN. Restricted permutations
assume exchangeability within strata; this single-participant result does not
establish a population effect.

[Recipe](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/recipes/ern-flankers/RECIPE.md) ·
[corrected record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.md) ·
[result JSON](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.json) ·
[corrected figure](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/assets/flankers-case-study-corrected.png) ·
[original figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/docs/assets/flankers-case-study.png) ·
[historical instructions and commands](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/EXAMPLES.md#erp-core-flankers-conflict-processing).

The [analysis](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/tools/run_full_case_study.py) and
[plotting](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/tools/gen_case_study_figures.py)
scripts remain in the snapshot. The original pipeline reported 94.6 s; corrected
analysis took 12.60 s from saved epochs, excluding upstream stages and rendering.
These different stages do not establish complete-pipeline or LLM-related speedup.

## PhysioNet EEGBCI: resting-state recipes

These known-effect checks cover alpha power, complexity and microstates. Read the
[original findings](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/eegbci-resting/FINDINGS.md)
with the [audit follow-ups](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/eegbci-resting/audit-stage/AUDIT_FOLLOWUP.md):
alpha was spatially diffuse, LZC lost the contrast without ICA, microstate duration
depended on smoothing, and anesthesia was untested. [Original results](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/resting_results.json)
and [follow-up results](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/audit_followup_results.json) remain in the public snapshot;
[certification coverage](CERTIFICATION_LEVELS.md) is recorded separately.

The [recorded validation script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/validate_resting_recipes.py)
is available in the fixed public snapshot. Use the recipes above for a new analysis.

## Trial identities behind the reference comparison

The [post-release identity check](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/trial_identity_results.json) maps
[original event rows, retention and sample positions](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/trial_identity_event_ids.json)
for all 120 original subject-component records, including the eight excluded records.
Retained trial identities agree in 111 of the 112 certified common records; MMN
sub-030 has one additional deviant in the reference. Event timing can differ by one
resampled sample even when identity agrees. Original AEA counts and stored-precision
amplitudes are reproduced. The check compares AEA with retained MNE-BIDS-Pipeline
outputs; it does not add EEGLAB/FieldTrip trial identities.

The [recorded identity-check script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/validate_trial_identity.py)
requires the original ERP CORE caches and retained reference derivative
FIF files under `~/mne_data`. It regenerates original AEA subject processing and reads
the reference files; it does not run group permutations or overwrite the published
results. New records are written under `projects/trial-identity/`.

The script is available in the fixed public snapshot; it is not part of a new recipe run.
