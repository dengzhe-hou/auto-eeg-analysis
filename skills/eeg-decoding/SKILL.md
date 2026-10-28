---
name: eeg-decoding
description: "Multivariate pattern analysis (MVPA) for EEG: temporal decoding, temporal generalization, searchlight, cross-condition decoding. Uses scikit-learn classifiers on MNE epochs. Use when user says 'decoding', 'MVPA', 'classification', 'temporal generalization', 'can we decode X from EEG', or wants to know when/where information is represented."
argument-hint: "[project-dir] [— classifier: svm|lda|logreg] [— method: sliding|generalization|searchlight] [— cv: 5]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-decoding: multivariate pattern analysis

## Context: $ARGUMENTS

## Use this skill

Read the task and the approved analysis plan before choosing a procedure. The
name and description select this skill; they do not specify the analysis.
Load only the relevant sections below, rather than every reference in advance.
For a bounded calculation, use the supplied inputs without inventing upstream
stages or approvals. Keep the actual method, parameters, outputs, and checks.

Template values in the detailed procedures describe their documented examples.
Resolve scientific choices against the task and approved plan before execution;
do not treat an example, a timeout, or an unattended run as researcher approval.
Preserve explicitly fixed configurations. Record unresolved choices and continue
independent approved work, as described in the project instructions.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-decoding --section "Phase A — Setup"
```

## Required Inputs

1. `epoch-stage/` — epoched data per subject (`.fif`).
2. `ANALYSIS_PLAN.md` — decoding claims (e.g., "face vs object decodable from 100–200 ms").
3. `ENVIRONMENT.json`

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


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Setup

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — Sliding estimator (default)

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Temporal generalization matrix (when `— method: generalization`)

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Searchlight (when `— method: searchlight`)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — CSP decoding (when `— method: csp`)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E6 — Riemannian / tangent-space decoding + Euclidean Alignment (oscillatory, cross-subject)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E7 — Confound control & disentangling correlated design factors

Read this section in [the detailed procedure](references/procedure.md).

## Phase E2 — Hyperparameter tuning without leakage (nested CV)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E3 — Representational similarity (RSA / cross-validated RDM)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E4 — Tabular feature decoding (non-time-resolved)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E5 — Diagnostic / state classifier reporting (sensitivity, specificity, confusion matrix per fold)

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `epoch-stage/`, `ANALYSIS_PLAN.md`
- Outputs: `decoding-stage/*.json`, `decoding-stage/*.npz`, `figure-stage/`
- Related: `eeg-erp` (univariate complement), `eeg-tfr` (time-frequency features for CSP), `eeg-stats` (cluster correction on decoding scores)
