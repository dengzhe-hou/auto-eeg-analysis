## Constants

- **APPROVED SETTINGS** — resolve into `approved_behavior_params`: original
  recording/block and trial keys, event/condition/correctness mapping, response
  window and assignment, RT eligibility and outlier policy (including no outlier
  removal if approved), observation unit, condition test, contrast order,
  missing/unmatched policy, EEG estimator and regression model. Do not invent
  thresholds or select a new test/model from the results.
- **ACCURACY / TRIAL EXCLUSION** — use only an approved rule and its scope; no
  automatic 50% accuracy cutoff or universal RT bounds.
- **MEASURES / EEG_BEHAVIOR_METHOD** — use the requested scores and estimand;
  across-subject correlation and within-subject trial regression differ.
- **OUTPUT_DIR = `behavior-stage/`**
- **SEED** — read the approved seed if the selected operation needs randomness.

> Override: `/eeg-behavior projects/my-study — measures: rt,accuracy,dprime — eeg-behavior: regression`

## Phase A — Extract behavioral data

### From EEG event markers (most common)

```python
# AEA example: behavior-responses
import mne
import numpy as np
import pandas as pd
from pathlib import Path
import runpy
trial_helpers = runpy.run_path(str(
    Path(AEA_ROOT) / 'skills/eeg-behavior/scripts/trials.py'))
events, event_id = mne.events_from_annotations(raw,
    event_id=approved_behavior_params['event_id'], regexp=None,
    use_rounding=approved_behavior_params['use_rounding'])
stim_events = events[np.isin(events[:, 2], approved_behavior_params['stim_codes'])]
resp_events = events[np.isin(events[:, 2], approved_behavior_params['resp_codes'])]
stimuli = pd.DataFrame({'stim_sample': stim_events[:, 0],
                       'condition': stim_events[:, 2]})
responses = pd.DataFrame({'response_sample': resp_events[:, 0],
                         'response_code': resp_events[:, 2]})
# Actual recording/session/block identity, not a guessed row-number pairing.
for key, value in recording_identity.items():
    stimuli[key] = value
    responses[key] = value
df, response_audit = trial_helpers['match_responses'](
    stimuli, responses, sfreq=raw.info['sfreq'],
    **approved_behavior_params['response_policy'])
# Correctness comes from the approved task mapping, including no-response trials.
df['correct'] = [is_correct(row.condition,
    None if row.status == 'missed' else row.response_code) for row in df.itertuples()]
```

`raw` is the supplied recording on the approved event grid. This example uses
the original `stim_sample` plus recording/block fields as trial identity. For
logs with existing trial IDs, retain those IDs through their approved alignment
instead of assigning new IDs after EEG rejection.

The helper requires `group_keys`, `trial_keys`, `response_window_ms`,
`stop_at_next_stimulus` and `assignment='first_unused'`. Its window includes the
left bound and excludes the right bound; it visits stimuli chronologically per
recording/block and uses each response row once. Use it only when that rule is
approved. If the design permits another assignment or boundary convention,
implement that explicitly. Save `response_audit`, including missed, unused,
duplicate-source and multiple-candidate information; do not silently reuse or
deduplicate events. No-go omissions are not automatically coded incorrect.

### From behavioral log files

```python
# If user provides a separate behavioral file (CSV, TSV, PsychoPy log)
df = pd.read_csv(behavioral_log_path)
# Keep original recording/block/trial identity, condition, RT unit, response and correctness.
# Resolve timestamp-to-sample conversion and verify event identity before joining.
```

## Phase B — Behavioral descriptive statistics

### RT analysis

Apply the approved RT eligibility/outlier rule to form `df_clean`, retaining its
original keys. Record each filtering step and per-subject/condition counts.
There is no automatic IQR multiplier, absolute bound or participant exclusion.
Descriptive RT summaries must name their unit (trials or participant summaries).

For a participant-level paired test, first form the approved condition summary
per participant; for a genuinely paired-trial test, supply the original pair
keys. The following example is **only** for an approved paired t-test and does
not aggregate trials or choose a test:

```python
# AEA example: behavior-paired-test
from pathlib import Path
import runpy
from scipy.stats import ttest_rel
trial_helpers = runpy.run_path(str(
    Path(AEA_ROOT) / 'skills/eeg-behavior/scripts/trials.py'))
test_spec = approved_behavior_params['condition_test']
if test_spec['method'] != 'paired_t':
    raise ValueError('This example requires an approved paired_t; use the planned test instead')
rt_a, rt_b, pairing_audit = trial_helpers['paired_values'](
    comparison_table, **test_spec['pairing'])
if len(rt_a) < 2:
    raise ValueError('Paired t-test needs at least two identified observation pairs')
t, p = ttest_rel(rt_a, rt_b, alternative=test_spec['alternative'])
```

`comparison_table` contains one value per approved unit and condition.
`pairing` requires `unit_keys`, `condition_column`, ordered `conditions`,
`value_column`, and `unmatched_policy` (`error` or explicitly approved
`intersection`). Duplicate unit/condition rows fail rather than being averaged
or truncated. Unpaired/independent designs require their approved test on the
appropriate units; equal row counts never establish related observations.

### Accuracy analysis

```python
accuracy = df.groupby('condition')['correct'].mean()

# Yes/no SDT with the approved target/nontarget coding, not a universal 2AFC conversion.
from scipy.stats import norm
hit_rate = np.clip(accuracy['target'], 0.01, 0.99)
fa_rate = np.clip(1 - accuracy['nontarget'], 0.01, 0.99)
dprime = norm.ppf(hit_rate) - norm.ppf(fa_rate)
criterion = -0.5 * (norm.ppf(hit_rate) + norm.ppf(fa_rate))

# Inverse Efficiency Score (IES = RT / accuracy)
ies = rt_mean / accuracy
```

## Phase C — EEG-behavior single-trial regression

Link trial-by-trial EEG amplitude to RT or accuracy.

### Single-trial regression (recommended)

```python
# AEA example: behavior-eeg-regression
import statsmodels.api as sm
from pathlib import Path
import runpy
trial_helpers = runpy.run_path(str(
    Path(AEA_ROOT) / 'skills/eeg-behavior/scripts/trials.py'))

# Extract single-trial EEG: mean amplitude in ROI+window per trial
epochs = mne.read_epochs(epochs_path, preload=True)
roi_idx = [epochs.ch_names.index(c) for c in roi]
t_mask = (epochs.times >= tmin) & (epochs.times <= tmax)

# Per-trial EEG feature
eeg_amplitudes = epochs.get_data()[:, roi_idx, :][:, :, t_mask].mean(axis=(1, 2)) * 1e6

# Preserve original identities through epoch rejection and RT filtering.
trial_keys = approved_behavior_params['trial_keys']
if epochs.metadata is None:
    raise ValueError('Original trial metadata is required; do not infer identity from row order')
feature_table = epochs.metadata[trial_keys].copy()
feature_table['eeg_amp'] = eeg_amplitudes
aligned, alignment_audit = trial_helpers['align_trials'](
    feature_table, df_clean, keys=trial_keys, right_columns=['rt'],
    unmatched_policy=approved_behavior_params['unmatched_policy'])
if approved_behavior_params['regression_method'] != 'single_subject_ols':
    raise ValueError('This example is only for the approved single-subject OLS model')
if aligned[approved_behavior_params['subject_column']].nunique() != 1:
    raise ValueError('Do not pool multiple subjects as independent OLS trials')
eeg_amplitudes = aligned['eeg_amp'].to_numpy()
rt_values = aligned['rt'].to_numpy()

# Regression
X = sm.add_constant(eeg_amplitudes)
model = sm.OLS(rt_values, X).fit()
beta = model.params[1]
r_squared = model.rsquared
p_value = model.pvalues[1]
```

Store the original stimulus identity in `epochs.metadata` at epoch creation;
MNE carries the corresponding metadata through drops. Existing saved epochs
need their retained mapping (for example from the original event table and
`epochs.selection`); do not renumber remaining epochs. The helper preserves EEG
feature order, checks one-to-one identity and records both unmatched sets.
`intersection` means an explicitly approved common retained set; otherwise use
`error`. Keep the audit with the analysis output. Equal counts alone are not a
validation of alignment. Include condition in the identity/checks where needed
to verify labels, and keep recording/block keys to prevent cross-session joins.

> **Optional dependency:** `statsmodels` is NOT guaranteed in the `aeais` env. Guard the import (`try: import statsmodels.api as sm / import statsmodels.formula.api as smf except ImportError: ...`), log the absence to the stage JSON, surface it in AUDIT, and emit a `pip install statsmodels` hint instead of crashing. The same guard applies to the mixed-model recipe below.

### Multi-subject single-trial regression — use a mixed-effects model (NOT pooled OLS)

The `sm.OLS` recipe above is correct **only for a single subject**. When you pool single trials across subjects, trials from the same subject are correlated, so plain OLS treats N_trials as independent observations and grossly inflates degrees of freedom (pseudoreplication). Fit a linear mixed model with a per-subject random intercept (and, when justified, a random slope for the EEG predictor):

```python
# requires statsmodels (optional dep) — guard the import as noted above
import statsmodels.formula.api as smf

# long-format DataFrame: one row per trial, columns 'rt', 'eeg_amp', 'subject', 'condition'
# random intercept per subject (minimum), random slope when you have enough trials/subjects
md = smf.mixedlm("rt ~ eeg_amp", data=df_long,
                 groups=df_long["subject"],
                 re_formula="~eeg_amp")           # random slope+intercept; use "~1" for intercept-only
mf = md.fit(method="lbfgs", reml=True)
beta = mf.fe_params["eeg_amp"]                     # population-level (fixed) EEG->RT slope
p_value = mf.pvalues["eeg_amp"]
# report fixed-effect beta + p, the random-effect variance, and n_subjects AND n_trials
```

If the approved random-slope model fails to converge, retain the failure and
report it. A random-intercept-only fallback is allowed only if pre-authorized;
logging a change does not authorize it. Within-subject centering and condition
covariates also follow the approved estimand/model.

For a binary outcome (`correct`) use a logistic mixed model via `statsmodels.genmod.bayes_mixed_glm.BinomialBayesMixedGLM` (also gated behind the statsmodels import guard), or `glmer(correct ~ eeg_amp + (1|subject), family=binomial)` if R/lme4 is reachable through the optional `pymer4` package (neither statsmodels nor pymer4 is guaranteed in `aeais` — degrade gracefully).

### Median split (simpler alternative)

```python
# Split trials by EEG amplitude at ROI
median_amp = np.median(eeg_amplitudes)
fast_rt = rt_values[eeg_amplitudes < median_amp].mean()  # low amplitude = "fast"
slow_rt = rt_values[eeg_amplitudes >= median_amp].mean()  # high amplitude = "slow"
# Caution: median split has lower power than regression (MacCallum et al. 2002)
```

### Across-subject correlation (group data)

```python
# For each subject: compute mean EEG measure + mean behavioral measure
# Then correlate across subjects
from scipy.stats import pearsonr, spearmanr
r, p = pearsonr(subject_eeg_means, subject_rt_means)
# Use Spearman for non-normal distributions
rho, p = spearmanr(subject_eeg_means, subject_rt_means)
```

### AVOID SUBJECT LEAKAGE when validating an EEG-behavior link predictively

If you go beyond an explanatory model and ask "does single-trial EEG **predict** RT/accuracy out-of-sample" (cross-validated R²/AUC, or a learned EEG->behavior mapping pooled over subjects), **never** use plain `KFold`/`train_test_split` on pooled trials. Random splitting puts trials from the same subject in both train and test, so the model learns subject identity and the score is inflated. Group by subject:

```python
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut, cross_val_score

groups = df_long["subject"].values
# leave-one-subject-out generalization estimate (the honest number to report):
scores = cross_val_score(estimator, X, y, groups=groups, cv=LeaveOneGroupOut())
# or k folds of whole subjects:
scores = cross_val_score(estimator, X, y, groups=groups, cv=GroupKFold(n_splits=5))
```

`LeaveOneGroupOut` is the standard "leave-one-subject-out" estimate. Report mean ± std across folds, never the max fold.

## Phase D — Write outputs

### `behavior-stage/behavioral_summary.json`
```json
{
  "n_trials_total": 400,
  "n_trials_correct": 380,
  "n_trials_after_outlier": 365,
  "outlier_method": "iqr",
  "rt_by_condition": {
    "compatible": {"mean": 452.3, "median": 445.1, "std": 82.4, "n": 185},
    "incompatible": {"mean": 498.7, "median": 490.2, "std": 91.1, "n": 180}
  },
  "accuracy_by_condition": {
    "compatible": 0.96,
    "incompatible": 0.92
  },
  "rt_condition_test": {"t": -4.23, "p": 0.00003, "test": "paired_ttest"},
  "eeg_behavior": {
    "method": "regression",
    "predictor": "N2_amplitude_FCz_200-350ms",
    "outcome": "RT",
    "beta": -2.34,
    "r_squared": 0.08,
    "p": 0.012
  }
}
```

### Figures
1. **RT distribution**: violin/raincloud plot per condition with individual trials.
2. **Accuracy bars**: per condition with confidence intervals.
3. **EEG-behavior scatter**: single-trial amplitude vs RT with regression line.
4. **Conditional accuracy function (CAF)**: accuracy as function of RT quantile.
5. **Delta plot**: condition difference as function of RT quantile (reveals inhibition dynamics).

### Append to FINDINGS.md

## Phase E — Sanity checks

- [ ] RT units and the approved task-specific bounds/filter match the actual output; no generic 200–2000 ms cutoff is inferred.
- [ ] Accuracy/correctness mapping includes omissions as specified by the task; chance and exclusion rules are applied only when defined in the plan.
- [ ] Outlier removal didn't discard >20% of trials (if so, warn).
- [ ] Original recording/block/trial keys join one-to-one; matched identities and both unmatched sets are retained. Counts alone are insufficient.
- [ ] Response assignments satisfy the approved timing/ownership rule; no source response row is reused and duplicate source rows are identified.
- [ ] Condition-test pairs use actual participant/pair identities and the approved contrast order; no truncation or automatic trial pairing.
- [ ] EEG-behavior regression checked for outliers and influential points.
- [ ] If median split: caveat about loss of power documented.

## Failure Modes

| Symptom | Action |
|---|---|
| No response events in EEG | Check if responses are in a separate behavioral log file. |
| RT distribution bimodal | Likely two response strategies. Flag to user. Consider analyzing fast/slow separately. |
| Accuracy below chance | Wrong condition-response mapping. Check marker codes. |
| EEG-behavior r² very high (>0.5) | Almost certainly an artifact. Check for trial-ordering confound or data leakage. |
| Pooled single-trial regression p-value implausibly tiny (e.g. p<1e-10) with modest effect | Pseudoreplication from treating all subjects' trials as independent in OLS. Refit as a mixed model with a subject random intercept. |
| Cross-validated EEG->behavior accuracy/R² much higher than the explanatory effect | Subject leakage from plain KFold on pooled trials. Re-run with GroupKFold/LeaveOneGroupOut (groups=subject). |
| Random-slope mixed model fails to converge (singular fit) | Retain the failure and report it. Use a simpler model only under the approved fallback policy. |
| `import statsmodels` (or `pymer4`) fails | Record the missing selected dependency and leave the model incomplete; do not substitute single-subject OLS or a new estimand. |
| Too few trials after approved RT filtering | Report retained identities/counts and the applicable inclusion rule; do not loosen the threshold or change tests automatically. |
