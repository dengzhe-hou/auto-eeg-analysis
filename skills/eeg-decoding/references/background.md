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
