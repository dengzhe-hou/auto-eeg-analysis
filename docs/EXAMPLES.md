# Worked examples

The N400 tutorial includes runnable scripts and compact result arrays. Raw EEG and
cached epochs are not distributed; `projects/` is your local workspace. Follow
[Getting started](GETTING_STARTED.md), run from the repository root in the analysis
environment, reuse data caches, and choose a new output directory each time.

## Replot the saved results

Start here to inspect a complete output without downloading source EEG or using an
LLM. In the analysis environment, install Arial or Helvetica, then run:

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

The OSF layout includes `ses-N400`; the runner expects
`sub-001/eeg/sub-001_task-N400_eeg.set` and the matching `_events.tsv`.
If your cache already has that layout, use it directly. For the OSF layout, run the
following in Python after changing the source path. It creates an input view next
to the dataset using symbolic links, without changing or copying source EEG.
On Windows, use WSL or enable symbolic-link creation in Developer Mode; see
[platform support](PLATFORM_SUPPORT.md).

```python
from pathlib import Path

source = Path("/path/to/ERP_CORE_BIDS_Raw_Files").resolve()
view = source.parent / "erpcore-N400-input"
for number in range(1, 21):
    subject = f"sub-{number:03d}"
    original = source / subject / "ses-N400" / "eeg"
    destination = view / subject / "eeg"
    destination.mkdir(parents=True, exist_ok=True)
    for suffix in ("eeg.set", "eeg.fdt", "events.tsv", "eeg.json",
                   "channels.tsv", "electrodes.tsv", "coordsystem.json"):
        file = original / f"{subject}_ses-N400_task-N400_{suffix}"
        if not file.is_file():
            raise FileNotFoundError(file)
        (destination / file.name.replace("_ses-N400", "")).symlink_to(file)
        if suffix == "eeg.fdt":
            (destination / file.name).symlink_to(file)  # preserve .set's data-file reference
print(view)
```

This view is for the fixed runner; it does not convert or replace the original BIDS
dataset. Keep it with your data cache, outside the repository. Use a fresh view path
if you repeat preparation.

## ERP CORE: complete N400 recipe case

This post-release example follows the [N400 recipe](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/recipes/n400-semantic/RECIPE.md)
from `v0.3.2` on the fixed 20-participant ERP CORE cohort. Its documented benchmark
branch omits ICA and amplitude rejection. The primary cluster test uses the recipe's
CPz/Cz/Pz ROI and 300–500 ms window. All participants retained 60 trials per condition;
the mean unrelated-minus-related amplitude was −2.957 µV (SEM 0.466), with one cluster
at p = 0.0002. This ROI test is separate from the historical all-channel certification.
See the [complete numerical record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/tools/examples/n400/recipe_case_results.json).

Pass the prepared input view (or your existing compatible cache) as `--data-root`,
and choose a fresh run directory. The runner downloads nothing. A Git clone with the
`v0.3.2` tag is required because it saves that recipe alongside the executed program.
These tutorial scripts are available on `main` and were added after v0.3.2.
Install Arial or Helvetica before the full run, which also renders figures.

```bash
python tools/examples/run_recipe_case.py --data-root /path/to/erpcore-N400-input --run-dir projects/n400-recipe-case/runs/run-001
python tools/examples/run_recipe_case.py --run-dir projects/n400-recipe-case/runs/run-001 --replay
```

The run saves the brief, frozen plan, program, preprocessed EEG, epochs, averages,
statistics, figures and methods. Start inspection at `stats-stage/summary.json`,
`figure-stage/F1_n400_recipe.png` and `report-stage/methods.md`; the run's `plan.json`
records the full configuration.

Replay checks group statistics from saved participant averages, without repeating
preprocessing. In the retained run, t maps, cluster masks, p values and permutation
null values were identical. This is an internal worked example, not an estimate of
LLM success rate or time savings.

## Adapt a recipe to your study

For your own recording, give the agent the [dataset brief](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/DATASET_BRIEF.md)
and ask it to draft an [analysis plan](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/templates/ANALYSIS_PLAN.md) before execution.
The following excerpt condenses the recorded N400 agent workflow. It illustrates
what the researcher supplies and approves; paths are examples.

```text
Study: N400 semantic priming; within participant; sub-001 through sub-020.
Raw data: /path/to/ERP_CORE_BIDS_Raw_Files (read only).
Time lock: target words, using events.tsv onset and value.
Related: values 211 and 212. Unrelated: values 221 and 222.
Prime values 111, 112, 121 and 122 and responses are not target onsets.
Question: are unrelated targets more negative than related targets?
Recipe: n400-semantic. Primary contrast: unrelated minus related.
ROI/window: CPz, Cz, Pz; 300–500 ms. Independent observation: participant.
```

For different recordings, replace the paths, participants and event mapping from
your acquisition log, then review the hypothesis, ROI and window for your design.
Request: “Read this brief and the N400 recipe. Draft the plan, list choices the recipe
does not fix, and stop for my approval before analyzing EEG.”

| Step | Concrete N400 example | What to inspect |
|---|---|---|
| Map events | Pool 211/212 as related and 221/222 as unrelated | Target timing and condition counts before cleaning |
| Approve the plan | Freeze contrast, ROI/window, cleaning, eligibility, adjacency, threshold, permutations and seeds | The researcher-approved `ANALYSIS_PLAN.md` |
| Execute the skills | Generate and save scripts for preprocessing → ICA → epochs → ERP → statistics → figures/report | Commands, stage parameters, per-participant counts and ICA proposals |
| Inspect and repeat | Retain code, condition averages, statistics, figures, methods and review records | Output arrays, report and saved-program replay comparison |

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
