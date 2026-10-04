# Worked examples

The complete N400 case below includes current scripts and compact result arrays.
Earlier examples link to full records in the [public evidence snapshot](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/projects),
including the October 2026 corrections, original plans, positive and null results,
historical errors and audits.
Raw EEG and cached epochs are not distributed. `projects/` is your local workspace.
Follow [Getting started](GETTING_STARTED.md), run from the repository root in the
analysis environment, reuse data caches and choose a new output directory each time.

## ERP CORE: complete N400 recipe case

This post-release example follows the [N400 recipe](../recipes/n400-semantic/RECIPE.md)
from `v0.3.2` on the fixed 20-participant ERP CORE cohort. Its documented benchmark
branch omits ICA and amplitude rejection. The primary cluster test uses the recipe's
CPz/Cz/Pz ROI and 300–500 ms window. All participants retained 60 trials per condition;
the mean unrelated-minus-related amplitude was −2.957 µV (SEM 0.466), with one cluster
at p = 0.0002. This ROI test is separate from the historical all-channel certification.
See the [complete numerical record](../tools/validation/recipe_case_results.json).

Use an existing ERP CORE N400 BIDS directory with sub-001 through sub-020 and a fresh
output directory. The runner saves the brief, frozen plan, program, preprocessed EEG,
epochs, averages, statistics, figures and methods. It downloads nothing.

```bash
python tools/validation/run_recipe_case.py --data-root /path/to/erpcore-N400 --run-dir projects/n400-recipe-case/runs/run-001
python tools/validation/run_recipe_case.py --run-dir projects/n400-recipe-case/runs/run-001 --replay
```

Replay checks group statistics from saved participant averages, without repeating
preprocessing. In the retained run, t maps, cluster masks, p values and permutation
null values were identical. This is an internal worked example, not an estimate of
LLM success rate or time savings. Its scripts and outputs were added after v0.3.2.

The complete three-panel figure can also be regenerated from the compact public
arrays, without the source EEG. Exports are PDF, editable SVG and 600 dpi PNG.

```bash
python tools/validation/gen_recipe_case_figures.py --run-dir projects/n400-recipe-figure --figure-data tools/validation/recipe_case_figure_data.npz --summary tools/validation/recipe_case_results.json
```

## MNE sample: auditory versus visual N100

The corrected example uses complete stimulus cycles from one participant; interrupted
cycles are excluded and accounted for. Fixed stimulus order confounds condition with
cycle position, and ROI electrode correspondences are approximate. See the
[corrected record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/mne-sample-audvis/REANALYSIS.md),
[result JSON](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/mne-sample-audvis/REANALYSIS.json) and [figure](assets/n100-case-study-corrected.png) for results and assumptions.

```bash
python tools/prepare_sample_case.py --project projects/mne-sample-audvis
python tools/run_fix_audit.py --project projects/mne-sample-audvis --out projects/mne-sample-audvis/runs/corrected-001
python tools/gen_case_study_figures.py --run-dir projects/mne-sample-audvis/runs/corrected-001
```

Skip preparation when the historical raw data and epochs are available. Preparation
reuses raw/preprocessed inputs, but refits ICA and writes new epochs; it fetches MNE
sample data if absent. The published correction reused historical epochs. A new
preparation run needs numerical comparison. Plotting requires Arial or Helvetica.

## ERP CORE: Flankers conflict processing

The single-participant example retains all three planned contrasts, including the
nonsignificant N2 result. Its response-locked compatibility contrast is separate from
canonical error-minus-correct ERN. Restricted permutations assume exchangeability
within block × target-side strata. See the [recipe](../recipes/ern-flankers/RECIPE.md),
[corrected record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.md),
[result JSON](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.json) and [figure](assets/flankers-case-study-corrected.png).

```bash
python tools/run_full_case_study.py --project projects/erp-core-full --reuse-epochs --out projects/erp-core-full/runs/corrected-001
python tools/gen_case_study_figures.py --run-dir projects/erp-core-full/runs/corrected-001
```

Supply converted Subject-001 Flankers data at `projects/erp-core-full/raw/sub-01.fif`
and saved stimulus/response epochs under that project's `epoch-stage/sub-01/`.
Omit `--reuse-epochs` to prepare those epochs from
raw FIF. The published correction reused epochs; its timing excludes upstream stages
and figure rendering. Neither single-participant example supports population inference.

## PhysioNet EEGBCI: resting-state recipes

These known-effect checks cover alpha power, complexity and microstates. Read the
[original findings](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/eegbci-resting/FINDINGS.md)
with the [audit follow-ups](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/eegbci-resting/audit-stage/AUDIT_FOLLOWUP.md):
alpha was spatially diffuse, LZC lost the contrast without ICA, microstate duration
depended on smoothing, and anesthesia was untested. [Original results](../tools/validation/resting_results.json)
and [follow-up results](../tools/validation/audit_followup_results.json) remain in the library;
[certification coverage](CERTIFICATION_LEVELS.md) is recorded separately.

```bash
python tools/validation/validate_resting_recipes.py --subjects 20 --out projects/eegbci-resting/runs/resting-001/resting_results.json
```

## Trial identities behind the reference comparison

The [post-release identity check](../tools/validation/trial_identity_results.json) maps
[original event rows, retention and sample positions](../tools/validation/trial_identity_event_ids.json)
for all 120 original subject-component records, including the eight excluded records.
Retained trial identities agree in 111 of the 112 certified common records; MMN
sub-030 has one additional deviant in the reference. Event timing can differ by one
resampled sample even when identity agrees. Original AEA counts and stored-precision
amplitudes are reproduced. The check compares AEA with retained MNE-BIDS-Pipeline
outputs; it does not add EEGLAB/FieldTrip trial identities.

The command requires the original ERP CORE caches and retained reference derivative
FIF files under `~/mne_data`. It regenerates original AEA subject processing and reads
the reference files; it does not run group permutations or overwrite the published
results. New records are written under `projects/trial-identity/`.

```bash
python tools/validation/validate_trial_identity.py --jobs 2
```
