## Domain Knowledge (distilled from group-statistics literature)

### Cluster-based permutation for MEEG (Maris & Oostenveld 2007, J Neurosci Methods)

- Solves the multiple-comparisons problem across the full channel × time (× freq) space by clustering adjacent suprathreshold samples and comparing the largest observed cluster statistic to a permutation null of largest clusters. Controls family-wise error rate without parametric assumptions.
- For between-group designs, the exchangeability unit is the **subject**: permute group labels across subjects. For within designs, flip the sign of each subject's difference (`_1samp` test).
- The cluster-forming threshold and the cluster statistic (sum vs TFCE) are choices, not ground truth — report them.
- Cite: Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. Journal of Neuroscience Methods, 164(1), 177–190.

### TFCE (Smith & Nichols 2009, NeuroImage)

- Threshold-Free Cluster Enhancement integrates the cluster-support profile over all thresholds (`h_power`, `e_power` defaults 2.0 / 0.5), yielding point-wise corrected p-values without a hard cluster-forming threshold.
- More robust to the threshold-choice arbitrariness of cluster-sum and often more sensitive to broad, low-magnitude effects; in MNE it is enabled by passing `threshold=dict(start=, step=)`.
- Cite: Smith, S. M., & Nichols, T. E. (2009). Threshold-free cluster enhancement. NeuroImage, 44(1), 83–98.

### Cluster tests do not localize (Sassenhagen & Draschkow 2019, Psychophysiology)

- A significant cluster establishes that a condition/group difference exists in the tested space — NOT the significance of any individual latency, channel, or frequency. Cluster onset/offset is governed by the arbitrary forming threshold, not the true effect boundary.
- Report clusters as "an effect was present in window W over channels C", never "the effect began at t and was significant at electrode X".
- Cite: Sassenhagen, J., & Draschkow, D. (2019). Cluster-based permutation tests of MEG/EEG data do not establish significance of effect latency or location. Psychophysiology, 56(6), e13335.

### First vs second level — the random-effects requirement (Holmes & Friston 1998; Luck 2014)

- Fixed-effects (trial-level) inference supports claims only about the analyzed dataset. Population claims require a **random-effects** model where between-subject variance is the error term — i.e., the second level, with subject as the random factor.
- The grand-average standard error / CI must therefore be computed across subjects, and N for power is the number of subjects, not trials. A single-subject (N=1) test never supports a population claim.
- Cite: Holmes, A. P., & Friston, K. J. (1998). Generalisability, random effects and population inference. NeuroImage, 7(4 Pt 2), S754. Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press.

### Don't inflate Type I error with factorial t-tests (Luck & Gaspelin 2017, Psychophysiology)

- Running many pairwise t-tests across electrodes/windows, or multi-factor ANOVAs with many interactions, inflates false positives; each added factor multiplies the comparisons.
- Pre-register ROI + window; use an omnibus rmANOVA/mixed model for factorial designs, then planned contrasts — not a t-test per cell.
- Cite: Luck, S. J., & Gaspelin, N. (2017). How to get statistically significant effects in any ERP experiment (and why you shouldn't). Psychophysiology, 54(1), 146–157.

### MNE-Python as the implementation (Gramfort et al. 2013, Frontiers in Neuroscience)

- The spatio-temporal cluster tests, `f_mway_rm`, `f_threshold_mway_rm`, TFCE, and `fdr_correction` used here are part of MNE-Python's `mne.stats`; report the MNE version (`mne.__version__`) and the exact function names for reproducibility.
- Cite: Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.

### Effect sizes and their CIs (Lakens 2013, Frontiers in Psychology)

- Report standardized effect sizes (Cohen's d/dz, Hedges' g, partial eta-squared) with confidence intervals, not just p-values. Use Hedges' g for small samples (bias correction) and bootstrap or noncentral-t CIs.
- A significant cluster with a small, CI-crossing-zero effect is weak evidence — present both.
- Cite: Lakens, D. (2013). Calculating and reporting effect sizes to facilitate cumulative science. Frontiers in Psychology, 4, 863.

### Unequal N and covariates

- Cluster permutation handles unequal N because it permutes labels (the null is exchangeable regardless of group size); parametric ANOVA does not — prefer `MixedLM` or Type-III SS for unbalanced cells.
- Covariates (age, IQ, head size) belong in the model: include them as fixed effects in `MixedLM`, or residualize the per-subject summary against the covariate before the cluster test (document which). Never compare groups that differ systematically on a nuisance variable without adjusting.

### A-priori power and sample size (Boudewyn et al. 2018, Psychophysiology)

To plan a target N (or trial count) rather than only analyze a fixed sample, estimate power by **Monte-Carlo subsampling** an existing large dataset (a pilot or a reference corpus such as ERP CORE): repeatedly draw subsamples over a grid of (`n_subjects` × `k_trials`), rerun the planned second-level test on each draw, and record the proportion that reach significance — yielding a power *surface* over both axes.

```python
rng = np.random.default_rng(SEED)
power = {}
for n in n_grid:
    for k in trial_grid:
        hits = sum(run_planned_test(subsample(pool, n, k, rng)) < alpha
                   for _ in range(n_iter))      # n_iter ≈ 1000
        power[(n, k)] = hits / n_iter            # estimated power at that (n, k)
```

Non-obvious facts to encode when reporting a power analysis: power depends **jointly and non-linearly** on N, trials, and SNR (not on N alone); within-subject **difference-wave** designs reach a given power with far fewer trials than between-condition/between-group designs (the subject-level difference cancels shared variance); and trial count shows a **component-specific diminishing-returns knee** — past it, adding trials buys little, so allocate effort to subjects. Report the assumed effect size/SNR, the grid, `n_iter`, and the seed, and prefer this empirical surface over a single closed-form G*Power number for cluster/mass-univariate tests. Cite: Boudewyn, M. A., Luck, S. J., Farrens, J. L., & Kappenman, E. S. (2018). How many trials does it take to get a significant ERP effect? *Psychophysiology*, 55(6), e13049.

### COBIDAS-MEEG reporting for group statistics (Pernet et al. 2020, Nature Neuroscience)

For every second-level test report: design (between/within/mixed) and the random/fixed factors; N per group/cell; the test, software, and version; permutation count, RNG seed, cluster-forming threshold (or TFCE params) and how derived; channel adjacency definition; alpha and multiple-comparison control (cluster-FWER, TFCE, FDR via `mne.stats.fdr_correction`); effect-size metric, formula, and CI; covariate handling; and tail/justification.
Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee. Nature Neuroscience, 23, 1548–1554.
