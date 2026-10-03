---
name: eeg-behavior
description: "Behavioral data analysis and EEG-behavior relationships: RT/accuracy descriptive stats, condition effects, speed-accuracy tradeoffs, single-trial EEG-behavior regression, median-split analyses, brain-behavior correlations. Use when user says 'behavioral analysis', 'RT analysis', 'accuracy', 'EEG-behavior correlation', 'single-trial regression', 'does N2 predict RT', or needs to link EEG to performance."
argument-hint: "[project-dir] [— measures: rt,accuracy,dprime] [— eeg-behavior: regression|median-split|correlation]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-behavior: behavioral data analysis + EEG-behavior linking

## Context: $ARGUMENTS

## Constants

- **RT_OUTLIER_METHOD = `iqr`** — Method for RT outlier removal. Alternatives: `sd` (±2.5 SD), `absolute` (200-2000ms), `mad` (median absolute deviation).
- **RT_OUTLIER_THRESHOLD = `1.5`** — IQR multiplier. For `sd` method: number of SDs.
- **ACCURACY_EXCLUSION = `0.5`** — Exclude subjects with accuracy below this threshold (chance for 2AFC).
- **MEASURES = `[rt, accuracy]`** — Behavioral measures to compute. Options: `rt`, `accuracy`, `dprime`, `criterion`, `ies` (inverse efficiency score).
- **EEG_BEHAVIOR_METHOD = `regression`** — How to link EEG to behavior. Options: `regression` (single-trial), `median_split`, `correlation` (across-subject), `robust_regression`.
- **OUTPUT_DIR = `behavior-stage/`**
- **SEED = read from ANALYSIS_PLAN**, default `42`.

> Override: `/eeg-behavior projects/my-study — measures: rt,accuracy,dprime — eeg-behavior: regression`

## Required Inputs

1. `epoch-stage/` — epoched data with event metadata (condition labels, response markers).
2. `DATASET_BRIEF.md` — to know trial structure, response markers, condition mapping.
3. `ANALYSIS_PLAN.md` — for behavioral claims or EEG-behavior claims.
4. Behavioral data source: either embedded in EEG events (response markers + timing) or separate behavioral log file.

## Phase A — Extract behavioral data

### From EEG event markers (most common)

```python
import mne
import numpy as np
import pandas as pd

# Load raw to get all events
raw = mne.io.read_raw_fif(raw_path, preload=False)
events, event_id = mne.events_from_annotations(raw)

# Build trial table: for each stimulus, find the next response
trials = []
stim_events = events[np.isin(events[:, 2], stim_codes)]
resp_events = events[np.isin(events[:, 2], resp_codes)]

for stim in stim_events:
    # Find first response after this stimulus
    next_resp = resp_events[resp_events[:, 0] > stim[0]]
    if len(next_resp) == 0:
        trials.append({'stim_sample': stim[0], 'condition': stim[2],
                       'rt': np.nan, 'response': np.nan, 'correct': False})
        continue
    resp = next_resp[0]
    rt_ms = (resp[0] - stim[0]) / raw.info['sfreq'] * 1000
    correct = is_correct(stim[2], resp[2])  # user-defined mapping
    trials.append({'stim_sample': stim[0], 'condition': stim[2],
                   'rt': rt_ms, 'response': resp[2], 'correct': correct})

df = pd.DataFrame(trials)
```

### From behavioral log files

```python
# If user provides a separate behavioral file (CSV, TSV, PsychoPy log)
df = pd.read_csv(behavioral_log_path)
# Must have columns: trial, condition, rt, response, correct
# Align with EEG events by trial number or timestamp
```

## Phase B — Behavioral descriptive statistics

### RT analysis

```python
# 1. Filter: correct trials only, within RT bounds
df_correct = df[df['correct'] == True].copy()

# 2. Outlier removal
if RT_OUTLIER_METHOD == 'iqr':
    q1 = df_correct['rt'].quantile(0.25)
    q3 = df_correct['rt'].quantile(0.75)
    iqr = q3 - q1
    df_clean = df_correct[(df_correct['rt'] >= q1 - 1.5*iqr) &
                           (df_correct['rt'] <= q3 + 1.5*iqr)]
elif RT_OUTLIER_METHOD == 'sd':
    mean, std = df_correct['rt'].mean(), df_correct['rt'].std()
    df_clean = df_correct[np.abs(df_correct['rt'] - mean) <= 2.5 * std]
elif RT_OUTLIER_METHOD == 'absolute':
    df_clean = df_correct[(df_correct['rt'] >= 200) & (df_correct['rt'] <= 2000)]

# 3. Per-condition summary
summary = df_clean.groupby('condition')['rt'].agg(['mean', 'median', 'std', 'count'])

# 4. Condition comparison (paired t-test or Wilcoxon for single subject)
from scipy.stats import ttest_rel, wilcoxon
rt_a = df_clean[df_clean['condition'] == cond_a]['rt']
rt_b = df_clean[df_clean['condition'] == cond_b]['rt']
t, p = ttest_rel(rt_a[:min(len(rt_a), len(rt_b))],
                 rt_b[:min(len(rt_a), len(rt_b))])
```

### Accuracy analysis

```python
accuracy = df.groupby('condition')['correct'].mean()

# d-prime (signal detection theory) for 2AFC
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
from sklearn.linear_model import LinearRegression
import statsmodels.api as sm

# Extract single-trial EEG: mean amplitude in ROI+window per trial
epochs = mne.read_epochs(epochs_path, preload=True)
roi_idx = [epochs.ch_names.index(c) for c in roi]
t_mask = (epochs.times >= tmin) & (epochs.times <= tmax)

# Per-trial EEG feature
eeg_amplitudes = epochs.get_data()[:, roi_idx, :][:, :, t_mask].mean(axis=(1, 2)) * 1e6

# Match to behavioral data (same trial order)
rt_values = df_clean['rt'].values[:len(eeg_amplitudes)]

# Regression
X = sm.add_constant(eeg_amplitudes)
model = sm.OLS(rt_values, X).fit()
beta = model.params[1]
r_squared = model.rsquared
p_value = model.pvalues[1]
```

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

If the random-slope model fails to converge, fall back to a random-intercept-only model (`re_formula="~1"`) and say so. Center `eeg_amp` within subject if you want the slope to reflect within-subject (trial-level) coupling rather than a mix of within- and between-subject effects.

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

- [ ] RT values are plausible (200–2000 ms for typical EEG tasks).
- [ ] Accuracy is above chance for all conditions.
- [ ] Outlier removal didn't discard >20% of trials (if so, warn).
- [ ] Trial counts match between behavioral data and epoch counts.
- [ ] EEG-behavior regression checked for outliers and influential points.
- [ ] If median split: caveat about loss of power documented.

## Domain Knowledge

### Single-trial EEG-behavior analysis (Pernet et al. 2011, Frontiers in Psychology)

- Single-trial regression is preferred over averaged ERP × averaged RT correlation: it preserves trial-level variability and avoids ecological fallacy.
- Use robust regression (e.g., Huber or IRLS) if single trials have outliers.
- Always report: predictor (which EEG measure, which ROI, which window), outcome, beta, r², p, and number of trials.
- Cite: Pernet, C. R., et al. (2011). Single-trial analyses: why bother? Frontiers in Psychology, 2, 322.

### Mixed-effects models for trial-level EEG-behavior (Volpert-Esmond et al. 2021, Int. J. Psychophysiology)

- When single trials are pooled across subjects, the trials are not independent: each subject contributes many correlated trials. Multilevel / linear mixed-effects models (random intercept per subject, random slopes where supported) partition within- vs between-subject variance and give correct standard errors; pooled OLS does not and inflates Type I error.
- The fixed-effect slope is the population EEG->behavior coupling; the random-effect variance quantifies how much that coupling varies across subjects. Always report both n_subjects and n_trials.
- Prefer mixed models over the two-step "per-subject slope then t-test against zero" especially when per-subject trial counts are uneven — the mixed model weights subjects appropriately.
- Cite: Volpert-Esmond, H. I., Page-Gould, E., & Bartholow, B. D. (2021). Using multilevel models for the analysis of event-related potentials. International Journal of Psychophysiology, 162, 145–156.

### Median split problems (MacCallum et al. 2002, Psychological Methods)

- Dichotomizing a continuous variable (median split) loses statistical power and can create spurious effects.
- Use continuous regression whenever possible. Only use median split for visualization.
- Cite: MacCallum, R. C., et al. (2002). On the practice of dichotomization of quantitative variables. Psychological Methods, 7(1), 19–40.

### Speed-accuracy tradeoff and delta plots (Ridderinkhof 2002, Psychophysiology)

- The Flanker effect typically increases with RT (delta plot slopes upward) because fast responses are too fast for the conflict to influence them.
- Delta plots (condition difference × RT quantile) reveal the time course of inhibition.
- Conditional accuracy functions (accuracy × RT quantile) reveal whether fast errors are the result of impulsive responding.
- Cite: Ridderinkhof, K. R. (2002). Activation and suppression in conflict tasks. In W. Prinz & B. Hommel (Eds.), Common Mechanisms in Perception and Action: Attention and Performance XIX (pp. 494–519). Oxford University Press.

### Inverse Efficiency Score (Townsend & Ashby 1978)

- IES = RT / proportion correct. Combines speed and accuracy into a single metric.
- Useful when there is a speed-accuracy tradeoff. Not meaningful when accuracy is at ceiling.
- Cite: Townsend, J. T., & Ashby, F. G. (1978). Methods of modeling capacity in simple processing systems. In J. Castellan & F. Restle (Eds.), Cognitive Theory (Vol. 3). Erlbaum.

### COBIDAS reporting for behavioral data

Report: number of trials per condition (before and after exclusion), outlier removal method and threshold, RT filter criteria, accuracy exclusion criteria, statistical test used, effect size.

## Critical Rules

- **Never** include incorrect trials in RT analysis (unless specifically analyzing error RTs).
- **Never** use raw RT without outlier removal — RT distributions are positively skewed.
- **Never** report median split as primary analysis — use regression. Median split is for visualization only.
- **Never** correlate subject-averaged EEG with subject-averaged RT when you have single-trial data (ecological fallacy).
- **Never** fit pooled `sm.OLS` (or `pearsonr`) on single trials from multiple subjects as if they were independent — use a mixed-effects model with a subject random effect (pseudoreplication otherwise inflates significance).
- **Never** use plain `KFold`/`train_test_split` when cross-validating an EEG->behavior model over pooled subjects — use `GroupKFold`/`LeaveOneGroupOut` with `groups=subject`. Report mean ± std across folds, never the best/max fold.
- **Never** forget to report the number of trials excluded by each filtering step.

## Failure Modes

| Symptom | Action |
|---|---|
| No response events in EEG | Check if responses are in a separate behavioral log file. |
| RT distribution bimodal | Likely two response strategies. Flag to user. Consider analyzing fast/slow separately. |
| Accuracy below chance | Wrong condition-response mapping. Check marker codes. |
| EEG-behavior r² very high (>0.5) | Almost certainly an artifact. Check for trial-ordering confound or data leakage. |
| Pooled single-trial regression p-value implausibly tiny (e.g. p<1e-10) with modest effect | Pseudoreplication from treating all subjects' trials as independent in OLS. Refit as a mixed model with a subject random intercept. |
| Cross-validated EEG->behavior accuracy/R² much higher than the explanatory effect | Subject leakage from plain KFold on pooled trials. Re-run with GroupKFold/LeaveOneGroupOut (groups=subject). |
| Random-slope mixed model fails to converge (singular fit) | Too few trials/subjects for the slope variance. Drop to random-intercept-only (`re_formula="~1"`) and document the simplification. |
| `import statsmodels` (or `pymer4`) fails | Optional dep absent in `aeais`. Log to stage JSON + AUDIT, emit `pip install statsmodels`, and fall back to the per-subject-slope two-step or single-subject OLS. |
| Too few trials after RT filtering (<20 per condition) | Loosen outlier threshold or use non-parametric tests. |

## Cross-references

- Inputs: `epoch-stage/`, `DATASET_BRIEF.md` (for marker→condition mapping), behavioral log files
- Outputs: `behavior-stage/*.json`, `figure-stage/` (RT/accuracy plots, EEG-behavior scatter)
- Related: `eeg-erp` (ERP amplitudes as predictors), `eeg-stats` (group-level EEG-behavior correlation), `eeg-decoding` (can RT-sorted trials improve decoding?)
