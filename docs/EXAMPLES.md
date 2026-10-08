# Worked examples

The N400 tutorial includes runnable scripts and compact result arrays. Raw EEG and
cached epochs are not distributed; `projects/` is your local workspace. Follow
[Getting started](GETTING_STARTED.md), run from the repository root in the analysis
environment, reuse data caches, and choose a new output directory each time.

## ERP CORE: complete N400 recipe case

This post-release example follows the [N400 recipe](../recipes/n400-semantic/RECIPE.md)
from `v0.3.2` on the fixed 20-participant ERP CORE cohort. Its documented benchmark
branch omits ICA and amplitude rejection. The primary cluster test uses the recipe's
CPz/Cz/Pz ROI and 300–500 ms window. All participants retained 60 trials per condition;
the mean unrelated-minus-related amplitude was −2.957 µV (SEM 0.466), with one cluster
at p = 0.0002. This ROI test is separate from the historical all-channel certification.
See the [complete numerical record](../tools/examples/n400/recipe_case_results.json).

Install Arial or Helvetica on your system before running the analysis or
figure-rendering commands below.

Use an existing ERP CORE N400 BIDS directory with sub-001 through sub-020 and a fresh
output directory. The runner saves the brief, frozen plan, program, preprocessed EEG,
epochs, averages, statistics, figures and methods. It downloads nothing.

```bash
python tools/examples/run_recipe_case.py --data-root /path/to/erpcore-N400 --run-dir projects/n400-recipe-case/runs/run-001
python tools/examples/run_recipe_case.py --run-dir projects/n400-recipe-case/runs/run-001 --replay
```

Replay checks group statistics from saved participant averages, without repeating
preprocessing. In the retained run, t maps, cluster masks, p values and permutation
null values were identical. This is an internal worked example, not an estimate of
LLM success rate or time savings. Its scripts and outputs were added after v0.3.2.

The complete three-panel figure can also be regenerated from the compact public
arrays, without the source EEG. Exports are PDF, editable SVG and 600 dpi PNG.

```bash
python tools/examples/gen_recipe_case_figures.py --run-dir projects/n400-recipe-figure --figure-data tools/examples/n400/recipe_case_figure_data.npz --summary tools/examples/n400/recipe_case_results.json
```

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

[Recipe](../recipes/ern-flankers/RECIPE.md) ·
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
