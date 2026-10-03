---
name: eeg-decoding
description: "Multivariate pattern analysis (MVPA) for EEG: temporal decoding, temporal generalization, searchlight, cross-condition decoding. Uses scikit-learn classifiers on MNE epochs. Use when user says 'decoding', 'MVPA', 'classification', 'temporal generalization', 'can we decode X from EEG', or wants to know when/where information is represented."
argument-hint: "[project-dir] [— classifier: svm|lda|logreg] [— method: sliding|generalization|searchlight] [— cv: 5]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-decoding: multivariate pattern analysis

## Context: $ARGUMENTS

## Constants

- **CLASSIFIER = `svm`** — Default: linear SVM (`sklearn.svm.SVC(kernel='linear')`). Alternatives: `lda` (LinearDiscriminantAnalysis, faster), `logreg` (LogisticRegression, probabilistic output).
- **METHOD = `sliding`** — Default: sliding time-point decoding. Alternatives: `generalization` (temporal generalization matrix), `searchlight` (spatial searchlight), `csp` (Common Spatial Patterns for oscillatory data).
- **CV = `5`** — Cross-validation folds. Use `stratified_kfold` to preserve class balance. Override: `— cv: 10`.
- **CV_SCHEME** — `StratifiedKFold(n_splits=5)` for single-subject (trials from one subject). **`GroupKFold` / `StratifiedGroupKFold` / `LeaveOneGroupOut` with `groups=subject_id` is MANDATORY when trials are pooled across subjects** (cross-subject decoding, patient-vs-control, resting-state classification). Plain `KFold`/`train_test_split` leaks subject identity and inflates accuracy.
- **N_REPEATS = `10`** — Use `RepeatedStratifiedKFold(n_splits=5, n_repeats=10)` for stable within-subject estimates (averages out fold-assignment variance).
- **NAVG** — Pseudo-trial averaging count (e.g. 5–13 trials averaged into one super-trial). Boosts SNR before classification; must be done inside each training fold, never across the train/test boundary.
- **SCORING = `roc_auc`** — Metric. Alternatives: `accuracy`, `balanced_accuracy`. AUC preferred for unbalanced classes.
- **N_PERMUTATIONS = `1000`** — For permutation-based significance testing.
- **SEED = read from ANALYSIS_PLAN**, default `42`.
- **OUTPUT_DIR = `decoding-stage/`**

> Override: `/eeg-decoding projects/my-study — method: generalization — classifier: lda — cv: 10`

## Required Inputs

1. `epoch-stage/` — epoched data per subject (`.fif`).
2. `ANALYSIS_PLAN.md` — decoding claims (e.g., "face vs object decodable from 100–200 ms").
3. `ENVIRONMENT.json`

## Phase A — Setup

1. Read `ANALYSIS_PLAN.md` for decoding claims.
2. Load epochs, identify conditions to decode.
3. Equalize trial counts across conditions (`epochs.equalize_event_counts()`).
4. Standardize features (z-score per time point across channels, within each CV fold).
5. If pooling trials across subjects, build a `groups` array of subject ids aligned to `X`/`y`, and pass it to every CV call (`cross_val_multiscore(..., groups=groups)`, `GridSearchCV(cv=GroupKFold(...))`). Decode **per subject first, then aggregate** when the design is within-subject (the standard MVPA convention: decode each subject independently, collect per-subject score time courses, test across subjects).

> **AVOID SUBJECT LEAKAGE.** When samples come from multiple subjects, use `GroupKFold` / `StratifiedGroupKFold` / `LeaveOneGroupOut(groups=subject_id)` — never `KFold`/`train_test_split`. Random splitting of trials from the same subject lets the classifier learn subject-specific (not condition-specific) structure, inflating accuracy. `LeaveOneGroupOut` is the standard leave-one-subject-out generalization estimate.

```python
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
# trials pooled across subjects -> groups = subject id per trial
scores = cross_val_multiscore(slider, X, y, cv=GroupKFold(n_splits=5), groups=groups)
# leave-one-subject-out generalization:
scores_loso = cross_val_multiscore(slider, X, y, cv=LeaveOneGroupOut(), groups=groups)
```

> **AVOID TEMPORAL / BLOCK LEAKAGE.** Subject identity is not the only confound. In a **block design** (all trials of one condition presented consecutively), slow EEG drift and block-level state make temporally adjacent trials correlated *regardless of stimulus*, so plain `KFold` lets the classifier exploit time/block identity instead of the condition — and the apparent accuracy collapses to chance if you re-test on a randomized-trial design. Mitigations: (1) prefer randomized/interleaved stimulus designs at acquisition; (2) when data are blocked, use **block-aware CV** where each contiguous block is an *atomic* train-xor-test unit (build a `groups` array of block ids and use `GroupKFold`/`LeaveOneGroupOut` — never split a block across train and test); (3) treat suspiciously high block-data accuracy as a red flag, not a result. Cite: Li, R., et al. (2021). The perils and pitfalls of block design for EEG classification experiments. IEEE TPAMI, 43(1), 316–333.

### No double-dipping: all data-driven preprocessing goes INSIDE the CV loop

Any step that uses data statistics — scaling, variance filtering, univariate/L1/tree/wrapper feature selection, PCA — must be fit on the **training fold only**. Fitting it on the full `X` (or selecting features against all labels) before splitting leaks test information and is a classic cause of inflated EEG decoding accuracy. Wrap every such step in a `Pipeline` and pass the *pipeline* to `cross_val_multiscore`/`GridSearchCV` so it is re-fit per fold.

```python
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
from mne.decoding import Vectorizer, SlidingEstimator, cross_val_multiscore

# Per-time-point pipeline: scale -> select -> classify, ALL re-fit each fold
clf = make_pipeline(StandardScaler(), SelectKBest(f_classif, k=20), SVC(kernel='linear'))
slider = SlidingEstimator(clf, scoring='roc_auc')
scores = cross_val_multiscore(slider, X, y, cv=5)   # selector re-fit per fold
```

Method → sklearn map (all Pipeline-compatible):

| Method | sklearn / MNE |
|---|---|
| Variance filter | `VarianceThreshold` |
| Univariate | `SelectKBest` / `SelectPercentile(f_classif)` for continuous EEG (`chi2` only for non-negative features) |
| L1 (sparse) | `SelectFromModel(LogisticRegression(penalty='l1', solver='liblinear'))` |
| Tree-based | `SelectFromModel(RandomForestClassifier())` / GBDT |
| Wrapper | `RFE` / `RFECV` / `SequentialFeatureSelector(direction='forward'`/`'backward')` |
| Relief | `skrebate.ReliefF` (optional dep, not in sklearn) |
| Scaling for epochs | `mne.decoding.Scaler`, flatten with `mne.decoding.Vectorizer` |

Write `decoding-stage/DECODING_PLAN.json`.

## Phase B — Sliding estimator (default)

Decode at each time point independently. Each time point uses all channels as features.

### MNE-Python path

```python
import numpy as np
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from mne.decoding import SlidingEstimator, cross_val_multiscore

clf = make_pipeline(StandardScaler(), SVC(kernel='linear'))
slider = SlidingEstimator(clf, scoring='roc_auc', n_jobs=1)

X = epochs.get_data()          # (n_trials, n_channels, n_times)
y = epochs.events[:, 2]        # condition labels

# Cross-validated decoding at each time point
scores = cross_val_multiscore(slider, X, y, cv=5)
# scores: (n_folds, n_times)
mean_scores = scores.mean(axis=0)  # (n_times,)
```

### Significance via permutation

```python
from mne.decoding import cross_val_multiscore

# Null distribution: shuffle labels N times
null_scores = np.zeros((N_PERMUTATIONS, len(epochs.times)))
for i in range(N_PERMUTATIONS):
    y_perm = np.random.permutation(y)
    null = cross_val_multiscore(slider, X, y_perm, cv=5)
    null_scores[i] = null.mean(axis=0)

# P-value per time point (naive — see corrected estimator below)
p_values = np.mean(null_scores >= mean_scores, axis=0)
```

### Global accuracy significance — use the corrected estimator

For a single overall (non-time-resolved) accuracy, prefer `sklearn.model_selection.permutation_test_score`, which shuffles labels, refits, and returns the **corrected** p-value `(C+1)/(n_perm+1)` — not the naive `mean(null >= obs)` (which omits the +1 and can return p=0).

```python
from sklearn.model_selection import permutation_test_score, StratifiedKFold
score, perm_scores, pvalue = permutation_test_score(
    clf, X_mean_time, y, cv=StratifiedKFold(5),
    n_permutations=N_PERMUTATIONS, scoring='roc_auc', random_state=SEED)
```

When trials are grouped by subject, pass `groups=` and use a grouped CV so label shuffling respects the group structure (shuffling across subjects breaks the null).

### Time-resolved significance — cluster permutation against chance

```python
from mne.stats import permutation_cluster_1samp_test
# scores: (n_subjects, n_times) per-subject score time courses
# Restrict the analyzed window to the POST-STIMULUS epoch only — never test the baseline
t0 = np.searchsorted(epochs.times, 0.0)
scores_post = scores[:, t0:] - CHANCE          # CHANCE = 0.5 (AUC/binary) or 1/n_classes
t_obs, clusters, cluster_p, H0 = permutation_cluster_1samp_test(
    scores_post, n_permutations=N_PERMUTATIONS, tail=1, seed=SEED)  # tail=1 = above chance
```

State `CHANCE` explicitly in the output JSON (`0.5` for AUC/binary accuracy, `1/n_classes` for balanced multiclass; verify empirically with `DummyClassifier(strategy='stratified')` if classes are imbalanced).

## Phase C — Temporal generalization matrix (when `— method: generalization`)

Train at each time point, test at all time points. Reveals whether neural representations are stable over time.

```python
from mne.decoding import GeneralizingEstimator, cross_val_multiscore

gen = GeneralizingEstimator(clf, scoring='roc_auc', n_jobs=1)
scores_gen = cross_val_multiscore(gen, X, y, cv=5)
# scores_gen: (n_folds, n_train_times, n_test_times)
mean_gen = scores_gen.mean(axis=0)  # (n_train, n_test)
```

Interpretation:
- **Diagonal**: same as sliding estimator (transient representations).
- **Off-diagonal above chance**: representations generalize across time (sustained or reactivated).
- **Square blocks**: stable representation maintained for a period.

## Phase D — Searchlight (when `— method: searchlight`)

Decode using local channel neighborhoods. Reveals spatial distribution of information.

```python
from mne.decoding import SlidingEstimator, cross_val_multiscore
from mne.channels import find_ch_adjacency

adjacency, ch_names = find_ch_adjacency(epochs.info, ch_type='eeg')

# For each channel neighborhood:
searchlight_scores = np.zeros((len(epochs.ch_names), len(epochs.times)))
for i, ch in enumerate(epochs.ch_names):
    neighbors = adjacency[i].nonzero()[1]
    ch_idx = np.concatenate([[i], neighbors])
    X_local = X[:, ch_idx, :]
    scores = cross_val_multiscore(slider, X_local, y, cv=5)
    searchlight_scores[i] = scores.mean(axis=0)
```

## Phase E — CSP decoding (when `— method: csp`)

Common Spatial Patterns for oscillatory/band-power-based decoding.

```python
from mne.decoding import CSP
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score

csp = CSP(n_components=4, reg=None, log=True)
clf_csp = make_pipeline(csp, SVC(kernel='linear'))

# Filter epochs to frequency band of interest first
epochs_alpha = epochs.copy().filter(8, 13)
X_alpha = epochs_alpha.get_data()

scores = cross_val_score(clf_csp, X_alpha, y, cv=5, scoring='roc_auc')
```

## Phase E6 — Riemannian / tangent-space decoding + Euclidean Alignment (oscillatory, cross-subject)

CSP is not the only oscillatory tool. Covariance-based **Riemannian geometry** treats each trial's spatial covariance matrix as a point on the SPD manifold; tangent-space mapping then exposes it to any linear classifier. This was the top non-deep family in the MOABB benchmark and is the recommended default before reaching for a deep net. `pyriemann` is an OPTIONAL dependency (not in the base env) — check the import and graceful-degrade if absent (`pip install pyriemann`); record availability in the stage JSON and surface it in AUDIT.

```python
import pyriemann
from pyriemann.estimation import Covariances
from pyriemann.tangentspace import TangentSpace
from pyriemann.classification import MDM
from sklearn.linear_model import LogisticRegression
from mne.decoding import cross_val_multiscore

# tangent-space pipeline: SPD covariances -> Riemann tangent space -> linear clf
clf_ts = make_pipeline(Covariances('lwf'),       # Ledoit-Wolf shrinkage estimator
                       TangentSpace(metric='riemann'),
                       LogisticRegression())
# or Minimum-Distance-to-Riemannian-Mean directly on the manifold:
clf_mdm = make_pipeline(Covariances('lwf'), MDM(metric='riemann'))
scores = cross_val_multiscore(clf_ts, X, y, cv=GroupKFold(5), groups=groups)
```

**Euclidean Alignment (EA) for cross-subject / pooled decoding.** Before pooling trials across subjects, whiten every trial of each subject by that subject's reference covariance `R̄^(-1/2)` (the mean of the subject's trial covariances). EA is *unsupervised* (needs no test labels) and reduces inter-subject covariate shift, which is what makes cross-subject generalization work — it is orthogonal to the `GroupKFold` rule above (GroupKFold *prevents inflation*; EA *enables generalization*). Fit the alignment on the **training subjects only** inside the CV loop so the test subject's reference covariance never leaks.

```python
import scipy.linalg
def euclidean_align(X_subj):                 # X_subj: (n_trials, n_ch, n_times) of ONE subject
    covs = np.array([x @ x.T / x.shape[1] for x in X_subj])
    R_bar = covs.mean(0)
    P = scipy.linalg.fractional_matrix_power(R_bar, -0.5).real
    return np.array([P @ x for x in X_subj])  # whitened trials, pooled across train subjects
```

Cite: Barachant, A., et al. (2012). Multiclass brain–computer interface classification by Riemannian geometry. IEEE TBME, 59(4), 920–928. He, H., & Wu, D. (2020). Transfer learning for brain–computer interfaces: A Euclidean space data alignment approach. IEEE TBME, 67(2), 399–410.

### EEGNet (deep path) — escalate only at high trial counts

For raw-signal decoding (P300/ERN/MRCP/SMR) a compact CNN, **EEGNet**, is the reference deep architecture: a temporal convolution acts as a learned bandpass, a depthwise convolution learns spatial filters, and a separable convolution summarizes temporally — only a few thousand parameters. But the MOABB benchmark finds that on typical single-subject EEG sample sizes, Riemannian tangent-space pipelines match or beat deep nets, so **default to Riemannian / CSP+LDA and escalate to EEGNet only at high trial counts or with transfer/augmentation**. If used, report architecture, seeds, splits, and code for reproducibility. Cite: Lawhern, V. J., et al. (2018). EEGNet: a compact convolutional neural network for EEG-based brain–computer interfaces. J. Neural Eng., 15(5), 056013. Chevallier, S., et al. (2024). The largest EEG-based BCI reproducibility study for open science (MOABB). arXiv:2404.15319.

## Phase E7 — Confound control & disentangling correlated design factors

### Back-to-back (B2B) regression — separate correlated factors

Standard decoding cannot tell apart design factors that are themselves correlated (word length vs frequency, luminance vs category). **B2B** is a two-stage linear method that disentangles them: first *decode* each factor from the neural data, then *regress* the true factors onto those decoded estimates; the diagonal of the resulting matrix gives an unbiased per-factor influence, and running it per time point shows **when** each factor is encoded. Use it whenever the claim concerns one factor while a nuisance factor co-varies with it. Cite: King, J.-R., et al. (2020). Back-to-back regression: Disentangling the influence of correlated factors from multivariate observations. NeuroImage, 220, 117028.

### Confounds before a between-group accuracy comparison

The diagnostic / state path (Phase E5) invites comparing accuracy between groups — but a group accuracy gap can reflect SNR, trial count, age, or RT rather than the representation of interest. Critically, **classification accuracy cannot be "controlled for" a confound by adding it as a regressor** — accuracy is a single summary statistic, not a per-trial outcome. The valid options are: counterbalance the confound by design, regress the confound out of the features **inside each CV training fold** (post-hoc confound regression, fit on train only), or match trial counts / SNR across groups. Cite: Snoek, L., Miletić, S., & Scholte, H. S. (2019). How to control for confounds in decoding analyses of neuroimaging data. NeuroImage, 184, 741–760.

## Phase E2 — Hyperparameter tuning without leakage (nested CV)

When `C`/`gamma`/`kernel` (SVM) or `max_depth`/`n_estimators` (RF/GBDT) must be tuned, do it in an **inner** loop nested inside the **outer** evaluation loop. Tuning on the same data you report on is leakage; report the mean ± std of the outer scores, **never the max**.

```python
from sklearn.model_selection import GridSearchCV, cross_val_score, StratifiedKFold
from sklearn.svm import SVC

param_grid = {'C': [0.01, 0.1, 1, 10, 100], 'gamma': ['scale'], 'kernel': ['linear']}
inner = GridSearchCV(SVC(), param_grid, cv=StratifiedKFold(5), scoring='roc_auc')
outer_scores = cross_val_score(inner, X_mean_time, y, cv=StratifiedKFold(5), scoring='roc_auc')
print(f'{outer_scores.mean():.3f} ± {outer_scores.std():.3f}')
```

Use `RandomizedSearchCV` instead of `GridSearchCV` to cut search cost on large grids. For time-resolved decoding, the inner search runs inside `cross_val_multiscore` via the pipeline.

> **Do NOT report the maximum accuracy across repeats/folds** — that is cherry-picking. Report the mean with a dispersion estimate (std) and, ideally, a bootstrap confidence interval.

## Phase E3 — Representational similarity (RSA / cross-validated RDM)

RSA is a first-class decoding output alongside classification: build a time-resolved neural Representational Dissimilarity Matrix (RDM) of shape `(n_conditions, n_conditions, n_times)`, then relate it to model/behavioral RDMs by rank correlation.

**Prefer cross-validated distance (crossnobis / cross-validated Mahalanobis) over raw Euclidean.** Raw Euclidean/correlation RDMs are positively biased (a condition is never zero-distant from itself across noisy splits); cross-validation removes this bias and makes the dissimilarity an unbiased estimate that can legitimately go negative under the null.

`mne-rsa` is an OPTIONAL dependency (not in the base env). Check the import and graceful-degrade if absent (`pip install mne-rsa`); record availability in the stage JSON and surface it in AUDIT.

```python
import mne_rsa
# data RDM per time point, cross-validated Mahalanobis (crossnobis)
rdm = mne_rsa.rdm_epochs(
    epochs, y=epochs.events[:, 2],
    dist_metric='mahalanobis', cv=5,
    temporal_radius=0.05)        # sliding time window
# relate neural RDM to a model RDM via Spearman rank correlation
rsa_tc = mne_rsa.rsa_epochs(epochs, model_rdm, rsa_metric='spearman')
```

Group inference on the RSA/similarity time course uses the same one-sample cluster permutation as decoding (`permutation_cluster_1samp_test`, `tail=1`, post-stimulus window only; chance for a dissimilarity/correlation time course is 0). Visualize the group-mean RDM at a peak time point as a heatmap.

## Phase E4 — Tabular feature decoding (non-time-resolved)

Distinct from time-resolved MVPA: extract a fixed `(n_epochs, n_features)` matrix of engineered features per epoch (band power, spectral/sample entropy, Hjorth, line length, fractal dims, time-domain moments), then run a leakage-safe Pipeline. Standard for resting-state / patient-vs-control where there is no aligned stimulus time axis.

`mne-features` is an OPTIONAL dependency (not in the base env). Check the import and graceful-degrade if absent (`pip install mne-features`); record availability in the stage JSON and surface it in AUDIT.

```python
from mne_features.feature_extraction import extract_features
funcs = ['pow_freq_bands', 'spect_entropy', 'samp_entropy',
         'hjorth_mobility', 'hjorth_complexity', 'line_length',
         'higuchi_fd', 'mean', 'std', 'skewness', 'kurtosis']
X_feat = extract_features(epochs.get_data(), epochs.info['sfreq'], funcs)  # (n_epochs, n_features)

clf = make_pipeline(StandardScaler(), SelectKBest(f_classif, k=30),
                    SVC(kernel='rbf'))
scores = cross_val_score(clf, X_feat, y, cv=GroupKFold(5), groups=groups, scoring='roc_auc')
```

Optional functional-connectivity features: flatten `mne_connectivity.spectral_connectivity_epochs` output into the feature vector. See `eeg-complexity` for entropy/fractal feature parameters (e.g. SampEn `m=2`, `r=0.2*SD`).

## Phase E5 — Diagnostic / state classifier reporting (sensitivity, specificity, confusion matrix per fold)

For a **clinical or state classifier** — patient-vs-control, sleep/wake or eyes-open/eyes-closed state, seizure/normal, responder/non-responder — accuracy alone is insufficient and clinically misleading (a 90%-specific test still misses 1 in 10 patients). The reporting convention is **sensitivity (recall of the positive/patient class) + specificity (recall of the negative/control class) + the confusion matrix**, alongside balanced accuracy and ROC-AUC. Compute these **per CV fold** from that fold's confusion matrix, then average across folds (and report the same set on a held-out test set when one exists).

Fix the **positive class** explicitly (patient/abnormal/eyes-closed = positive) and pass it as `labels=[neg, pos]` to `confusion_matrix` so the `tn, fp, fn, tp` unpacking is deterministic regardless of label encoding or class order.

```python
import numpy as np
from sklearn.metrics import confusion_matrix, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold   # or GroupKFold(groups=subject_id)

NEG, POS = 0, 1   # set POS = patient/abnormal/eyes-closed; state it in the JSON
cv = StratifiedKFold(n_splits=CV, shuffle=True, random_state=SEED)

per_fold = []
cms = np.zeros((2, 2), dtype=int)   # pooled confusion matrix across folds
for train, test in cv.split(X_feat, y):           # add groups= for grouped CV
    clf.fit(X_feat[train], y[train])
    y_pred = clf.predict(X_feat[test])
    cm = confusion_matrix(y[test], y_pred, labels=[NEG, POS])
    cms += cm
    tn, fp, fn, tp = cm.ravel()
    sens = tp / (tp + fn) if (tp + fn) else np.nan   # recall of POS (patients found)
    spec = tn / (tn + fp) if (tn + fp) else np.nan   # recall of NEG (controls cleared)
    bal_acc = balanced_accuracy_score(y[test], y_pred)
    # AUC needs scores, not labels; use decision_function (preferred) or predict_proba
    y_score = (clf.decision_function(X_feat[test])
               if hasattr(clf, 'decision_function')
               else clf.predict_proba(X_feat[test])[:, 1])
    auc = roc_auc_score(y[test], y_score)
    per_fold.append(dict(sensitivity=sens, specificity=spec,
                         balanced_accuracy=bal_acc, roc_auc=auc))

def mean_std(key):
    v = np.array([f[key] for f in per_fold], float)
    return float(np.nanmean(v)), float(np.nanstd(v))

report = {k: dict(zip(('mean', 'std'), mean_std(k)))
          for k in ('sensitivity', 'specificity', 'balanced_accuracy', 'roc_auc')}
report['confusion_matrix_pooled'] = cms.tolist()   # rows=true [neg,pos], cols=pred
report['positive_class'] = POS
print(f"sens {report['sensitivity']['mean']:.3f} | "
      f"spec {report['specificity']['mean']:.3f} | "
      f"bal_acc {report['balanced_accuracy']['mean']:.3f} | "
      f"AUC {report['roc_auc']['mean']:.3f}")
```

Notes:
- **Sensitivity = `tp/(tp+fn)`** (true-positive rate, recall of the positive class); **specificity = `tn/(tn+fp)`** (true-negative rate). These are the standard 2×2 contingency definitions.
- Guard the `(tp+fn)` / `(tn+fp)` denominators: a fold with zero true positives or true negatives yields a NaN that `np.nanmean` skips — better than a silent divide-by-zero. With very few patients per fold, prefer `StratifiedKFold`/`StratifiedGroupKFold` so each fold contains both classes.
- **Average over folds**, and additionally **pool the confusion matrices** (sum the 2×2 counts) for a single interpretable contingency table; the pooled table is more stable than any single fold's.
- **Held-out set:** when a locked test set exists, fit on the full training data and emit the *same* four metrics + confusion matrix on the held-out predictions — keep it strictly out of all CV/tuning.
- For the worked book example (Oz alpha-power eyes-open vs eyes-closed, LDA), `POS = eyes-closed` (the higher-alpha state); sensitivity is then the rate of correctly detected eyes-closed epochs.

This per-fold confusion-matrix path is the clinical complement to the metric-shortcut panel below: for routine MVPA prefer the built-in `scoring=`/`cross_validate` metrics; for a **diagnostic claim** emit the explicit sensitivity/specificity + confusion matrix here.

## Phase F — Write outputs

### `decoding-stage/<claim_id>_decoding.json`
```json
{
  "claim_id": "C1",
  "method": "sliding",
  "classifier": "svm_linear",
  "cv": 5,
  "scoring": "roc_auc",
  "n_trials_per_class": [72, 71],
  "peak_score": 0.73,
  "peak_time_ms": 165,
  "chance_level": 0.5,
  "significant_window_ms": [120, 250],
  "cluster_p": 0.002,
  "n_permutations": 1000,
  "seed": 42
}
```

### `decoding-stage/<claim_id>_diagnostic.json` (clinical / state classifier — Phase E5)
```json
{
  "claim_id": "C2",
  "task": "eyes_open_vs_eyes_closed",
  "positive_class": "eyes_closed",
  "classifier": "lda",
  "cv": 5,
  "sensitivity": {"mean": 0.91, "std": 0.06},
  "specificity": {"mean": 0.88, "std": 0.05},
  "balanced_accuracy": {"mean": 0.90, "std": 0.04},
  "roc_auc": {"mean": 0.95, "std": 0.03},
  "confusion_matrix_pooled": [[88, 12], [9, 91]],
  "confusion_matrix_rows": "true [neg, pos]",
  "confusion_matrix_cols": "pred [neg, pos]",
  "held_out": {"sensitivity": 0.89, "specificity": 0.86, "balanced_accuracy": 0.875, "roc_auc": 0.94},
  "seed": 42
}
```

### `decoding-stage/<claim_id>_scores.npz`
Save `mean_scores`, `all_scores`, `times`, `p_values`, `null_distribution`.

### Figures
- **Sliding decoding**: score vs time, with chance line + significance shading.
- **Temporal generalization**: matrix heatmap (train time × test time), with diagonal highlighted.
- **Searchlight**: topomap of decoding accuracy at peak time.
- **CSP**: spatial patterns of top CSP components.
- **Linear weight maps (SVM/LDA/LogReg)**: never topomap the raw coefficients — convert to a forward pattern first (see below).

### Never interpret raw decoder weights as brain activity — apply the Haufe transform

A backward (discriminative) model's weights `W` are *extraction filters*: they can load heavily on noise-suppressing channels that carry no signal of interest, so plotting raw SVM/LDA/LogReg coefficients as a topomap is physiologically misleading. Before any neurophysiological or topographic interpretation, convert the filter to a forward **activation pattern** `A = Cov(X) · W · Cov(s)^(-1)` (for a 1-D decision score `s`, the trailing factor is a scalar). CSP spatial *patterns* are already forward patterns and need no conversion; only learned weight vectors do. Cite: Haufe, S., et al. (2014). On the interpretation of weight vectors of linear models in multivariate neuroimaging. NeuroImage, 87, 96–110.

```python
# w: (n_channels,) linear weights; X_t: (n_trials, n_channels) features at one time point
s = X_t @ w                                   # decision scores
A = np.cov(X_t.T) @ w / np.var(s)             # forward activation pattern -> topomap THIS
```

### Reporting panel (don't report bare accuracy)

- **Binary:** ROC-AUC as primary (or balanced accuracy under class imbalance), plus confusion matrix, precision/recall/F1.
- **Multiclass:** balanced accuracy + per-class confusion matrix; chance = `1/n_classes`.
- Use `scoring='roc_auc'` / `'balanced_accuracy'` (or `cross_validate(scoring=['roc_auc','balanced_accuracy'])`) for routine MVPA — do not hand-compute metrics from `confusion_matrix.ravel()` for the general case. `sklearn.metrics` provides `roc_auc_score`, `balanced_accuracy_score`, `precision_recall_fscore_support`, `RocCurveDisplay`, `ConfusionMatrixDisplay`.
- **Clinical / state classifier (patient-vs-control, eyes-open/closed, seizure/normal):** the diagnostic convention is per-fold **sensitivity + specificity + confusion matrix** alongside balanced accuracy and ROC-AUC — see **Phase E5**, which derives them from each fold's `confusion_matrix(...).ravel()` and averages (+ pools) across folds. Here the explicit `tn,fp,fn,tp` decomposition is the *intended* report, not a shortcut to avoid.
- Report mean ± std across outer folds; **never report the max** across repeats.
- For AUC prefer the classifier's `decision_function`; avoid `SVC(probability=True)` (slow internal CV) unless calibrated probabilities are genuinely needed.

### Append to FINDINGS.md

## Phase G — Sanity checks

- [ ] Chance-level accuracy is correct (0.5 for AUC with balanced classes; 1/n_classes for accuracy).
- [ ] Trial counts are equalized across conditions.
- [ ] Features are standardized within CV folds (not across entire dataset — data leakage).
- [ ] Significance is assessed via permutation, not just comparison to chance.
- [ ] If temporal generalization: matrix is square (same time points for train and test).

## Domain Knowledge

### Temporal decoding fundamentals (King & Dehaene 2014, Trends in Cognitive Sciences)

- Temporal generalization reveals the dynamics of neural representations: transient (diagonal-only), sustained (square blocks), or sequential (off-diagonal chains).
- Always plot the full generalization matrix, not just the diagonal.
- A representation that generalizes across time suggests a stable neural code; one that doesn't suggests dynamic recoding.
- Cite: King, J.-R., & Dehaene, S. (2014). Characterizing the dynamics of mental representations. Trends in Cognitive Sciences, 18(4), 203–210.

### Decoding best practices (Grootswagers et al. 2017, NeuroImage)

- Always use cross-validation. Never decode on training data.
- Standardize features (z-score channels) within each CV fold to prevent data leakage.
- LDA is fastest and often performs comparably to SVM for EEG decoding.
- Report: classifier, CV scheme, scoring metric, chance level, significance method.
- Cite: Grootswagers, T., Wardle, S. G., & Carlson, T. A. (2017). Decoding dynamic brain patterns from evoked responses: A tutorial on multivariate pattern analysis applied to time series neuroimaging data. Journal of Cognitive Neuroscience, 29(4), 677–697.

### Statistical testing of decoding results (Allefeld et al. 2016, NeuroImage)

- Prevalence-based inference: tests whether an effect is present in the population, not just the sample.
- For group-level decoding: compute accuracy per subject, then test across subjects (second-level analysis).
- Permutation testing at the group level: shuffle condition labels within each subject, compute group mean, repeat.
- Cluster correction on the decoding time course is appropriate (same as for ERPs).
- Cite: Allefeld, C., Görgen, K., & Haynes, J.-D. (2016). Valid population inference for information-based imaging: From the second-level t-test to prevalence inference. NeuroImage, 141, 378–392.

### Common Spatial Patterns (Blankertz et al. 2008, NeuroImage)

- CSP finds spatial filters that maximize variance difference between two conditions — ideal for oscillatory (band-power) decoding.
- Filter epochs to the frequency band of interest before CSP.
- Regularized CSP (`reg='ledoit_wolf'`) is more robust with few trials.
- Cite: Blankertz, B., et al. (2008). Optimizing spatial filters for robust EEG single-trial analysis. IEEE Signal Processing Magazine, 25(1), 41–56.

### COBIDAS-MEEG reporting for decoding (Pernet et al. 2020)

Report: classifier type, regularization, CV scheme, n_folds, scoring metric, trial equalization method, feature normalization, significance testing method, chance level formula, number of permutations.

### Diagnostic / biomarker reporting: sensitivity, specificity, confusion matrix

- For a diagnostic or state classifier (patient-vs-control, normal-vs-abnormal, eyes-open-vs-eyes-closed), the established reporting convention is the 2×2 confusion matrix decomposed into **sensitivity** and **specificity**, not overall accuracy. With the positive class = patient/abnormal: **sensitivity = TP/(TP+FN)** (true-positive rate, the fraction of patients correctly detected) and **specificity = TN/(TN+FP)** (true-negative rate, the fraction of controls correctly cleared). These are the standard contingency-table definitions used throughout clinical diagnostics; accuracy `(TP+TN)/N` collapses them and is uninformative under class imbalance.
- Report both, per fold, and average across folds — a classifier with 95% specificity but 40% sensitivity is a poor screening test even at high accuracy, and accuracy alone would hide it. Balanced accuracy `= (sensitivity + specificity)/2` and ROC-AUC are threshold-summary complements; the confusion matrix gives the threshold-specific operating point.
- The standard worked example in 脑电信号处理与特征提取 (第十四章) classifies eyes-open vs eyes-closed from occipital (Oz) alpha power with LDA: eyes-closed produces the well-known posterior alpha enhancement (Berger effect), so band-power features separate the two states with high sensitivity/specificity — and the chapter reports the confusion matrix / classification rate per class, not bare accuracy.
- Cite: 脑电信号处理与特征提取 第十四章 (EEG signal processing and feature extraction, Ch. 14; Oz alpha-power eyes-open/eyes-closed LDA worked example). Sensitivity/specificity follow the standard 2×2 contingency-table definitions (true-positive rate / true-negative rate); see also Pernet et al. 2020 (COBIDAS-MEEG) for required decoding-report fields.

### Subject-wise cross-validation prevents identity leakage (Varoquaux et al. 2017, NeuroImage)

- When samples are pooled across participants, random trial-level splitting lets the classifier exploit within-subject correlations rather than the condition of interest, inflating accuracy.
- Use `GroupKFold` / `StratifiedGroupKFold` / `LeaveOneGroupOut` with `groups=subject_id`; leave-one-subject-out is the standard population-generalization estimate.
- Cite: Varoquaux, G., et al. (2017). Assessing and tuning brain decoders: cross-validation, caveats, and guidelines. NeuroImage, 145, 166–179.

### Cross-validated (crossnobis) distance for RSA (Walther et al. 2016, NeuroImage)

- Non-cross-validated dissimilarities (Euclidean, correlation) are positively biased: noise alone produces apparent dissimilarity, so even identical conditions look different.
- Cross-validated Mahalanobis distance (crossnobis) is an unbiased estimator of the squared pattern distance; it is zero in expectation under the null and may be negative in a sample.
- Multivariate noise normalization (whitening by the residual covariance) further improves RDM reliability.
- Cite: Walther, A., et al. (2016). Reliability of dissimilarity measures for multi-voxel pattern analysis. NeuroImage, 137, 188–200.

### Pseudo-trial averaging and repeated CV stabilize EEG decoding (Guggenmos et al. 2018, NeuroImage)

- Averaging small groups of same-condition trials into pseudo-trials raises SNR and reliably improves single-subject decoding and RDM reliability; the averaging must occur inside each training fold to avoid leakage.
- Repeated stratified CV (`RepeatedStratifiedKFold`, e.g. 10 repeats) averages out the variance from a single fold assignment, giving a more stable per-subject estimate before the group test.
- Balance classes per fold (subsample the majority class each iteration) to avoid majority-class bias in accuracy.
- Cite: Guggenmos, M., Sterzer, P., & Cichy, R. M. (2018). Multivariate pattern analysis for MEG: A comparison of dissimilarity measures. NeuroImage, 173, 434–447.

## Critical Rules

- **Never** train and test on the same data (no CV = no result).
- **Never** standardize features across the entire dataset before CV split (data leakage).
- **Never** report accuracy without chance level and significance test.
- **Never** interpret temporal generalization diagonal as "the only information" — always plot the full matrix.
- **Never** use accuracy as metric with unbalanced classes — use AUC or balanced accuracy.
- **Never** use plain `KFold`/`train_test_split` when trials are pooled across subjects — use `GroupKFold`/`LeaveOneGroupOut(groups=subject_id)` or accuracy is inflated by subject identity.
- **Never** split a block across train and test in a block design — temporal autocorrelation lets the classifier decode block/time identity instead of the condition; use block-aware CV with whole blocks as atomic units.
- **Never** topomap raw linear decoder weights (SVM/LDA/LogReg) as if they were brain activity — convert them to a forward activation pattern via the Haufe transform first.
- **Never** "control for" a confound by adding it as a regressor to a classification-accuracy comparison — counterbalance, regress the confound out of features inside the CV training folds, or match trial counts/SNR across groups instead.
- **Never** fit a scaler, feature selector, or PCA on the full dataset before the CV split — wrap them in a `Pipeline` so they re-fit on each training fold (double-dipping otherwise).
- **Never** tune hyperparameters and report performance on the same fold — use nested CV (inner `GridSearchCV`, outer `cross_val_score`).
- **Never** report the maximum accuracy across repeats/folds as the result — report mean ± std (cherry-picking otherwise).
- **Never** run the group cluster test across the whole epoch including the baseline — restrict the stats window to the post-stimulus period and state chance explicitly.
- **Never** treat a raw-Euclidean RDM as unbiased — use cross-validated distance (crossnobis) for RSA.
- **Never** report only accuracy for a clinical/state classifier — emit **sensitivity and specificity** (+ the confusion matrix), plus balanced accuracy and ROC-AUC, computed per fold and averaged. Accuracy hides which class is being missed (e.g. high accuracy on a control-heavy sample while patient sensitivity is near chance).

## Failure Modes

| Symptom | Action |
|---|---|
| Decoding at chance everywhere | Check: (1) conditions really differ, (2) enough trials, (3) correct labels, (4) data not too noisy. Report as negative finding. |
| Perfect accuracy (1.0) | Almost certainly data leakage. Check CV pipeline and feature scaling. |
| Very few trials per class (<30) | Warn: decoding unreliable. Use LDA (fewer parameters) and fewer CV folds. |
| scikit-learn not installed | `pip install scikit-learn`. It's in environment.yml. |
| Memory error with generalization matrix | Reduce n_times by decimating epochs (`epochs.decimate(4)`). |
| Suspiciously high cross-subject accuracy (>0.9) | Check CV uses `GroupKFold`/`LeaveOneGroupOut(groups=subject_id)`. Plain KFold leaks subject identity. |
| Accuracy drops a lot when selector/scaler moved into Pipeline | The original was double-dipping (fit on full X). The lower Pipeline number is the honest estimate. |
| Permutation p-value reported as exactly 0 | Naive `mean(null>=obs)` omits the +1 correction. Use `permutation_test_score` → p = (C+1)/(n+1). |
| Significant cluster sits entirely in the baseline | Stats window wasn't restricted to post-stimulus; re-run on `times >= 0` only. |
| RDM dissimilarities never near zero on the diagonal / all positive | Raw Euclidean is positively biased; switch to cross-validated (crossnobis) distance. |
| `mne_features` / `mne_rsa` / `pyriemann` not installed | `pip install mne-features mne-rsa pyriemann`. Optional deps, not in base MNE. |
| High block-design accuracy that vanishes on randomized re-test | Classifier decoded block/time identity, not the condition. Use block-aware CV (whole blocks atomic) or an interleaved design. |
| Decoder weight topomap looks like noise channels / makes no anatomical sense | You plotted raw filter weights. Convert to a forward activation pattern (Haufe transform) before interpreting. |
| Imbalanced classes (e.g. 80% controls, 20% patients) | Do **not** report raw accuracy — a constant "control" prediction scores 0.80. Report **balanced accuracy + per-class recall (sensitivity & specificity)** and ROC-AUC; use `StratifiedKFold`/`StratifiedGroupKFold` and verify chance with `DummyClassifier(strategy='stratified')`. |
| High accuracy but one class always wrong | Inspect the confusion matrix (Phase E5): the off-diagonal reveals the minority class is being missed. Report sensitivity & specificity separately, not the blended accuracy. |
| Sensitivity or specificity is NaN for a fold | That fold had zero true positives or zero true negatives. Use stratified CV so each fold has both classes; `np.nanmean` skips the NaN, but a NaN signals too-few patients per fold. |

## Cross-references

- Inputs: `epoch-stage/`, `ANALYSIS_PLAN.md`
- Outputs: `decoding-stage/*.json`, `decoding-stage/*.npz`, `figure-stage/`
- Related: `eeg-erp` (univariate complement), `eeg-tfr` (time-frequency features for CSP), `eeg-stats` (cluster correction on decoding scores)
