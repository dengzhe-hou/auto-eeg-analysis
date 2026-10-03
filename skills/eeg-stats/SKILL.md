---
name: eeg-stats
description: "Run claim-driven group statistics: cluster permutation (channel/time/freq), paired/independent t, effect sizes. Reads ANALYSIS_PLAN.md claim rows and the matching erp/tfr/connectivity stage outputs. Backend: MNE-Python. Use when user says 'run stats', 'cluster permutation', 'test my claims', or after ERP/TFR stages complete."
argument-hint: "[project-dir] [— claim: C1,C2] [— perms: 5000] [— exploratory]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-stats: claim-driven group statistics

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **DEFAULT_PERMS = `5000`** — Must match `ANALYSIS_PLAN.md`. Override: `— perms: 1000` (for speed during development).
- **SEED = read from ANALYSIS_PLAN.md `RNG seeds > Cluster permutation`**, default `42`.
- **CLAIMS = read from ANALYSIS_PLAN.md claim table** — one stat run per claim row, never extra unless `— exploratory` is passed.
- **OUTPUT_DIR = `stats-stage/`** — Create if missing.
- **ALPHA = read from ANALYSIS_PLAN.md claim table `α` column**, default `0.05`.

> Override: `/eeg-stats projects/my-study — claim: C1 — perms: 1000 — backend: mne`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `erp-stage/` or `tfr-stage/` — averaged data per condition per subject (`.fif` or `.h5`).
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Phase A — Parse claims

For each row in ANALYSIS_PLAN's claim table:

1. Extract: `claim_id`, `contrast`, `channels/ROI`, `time_window`, `freq_band`, `test`, `direction`, `alpha`.
2. Resolve ROI channels:
   - If claim says `Fz, Cz, FC1` but data uses `EEG 001, EEG 002...`, read `channel_mapping.json` and map.
   - If no mapping exists, **stop and ask** — do not guess.
3. Determine test type:
   - `cluster perm, paired` → `mne.stats.spatio_temporal_cluster_1samp_test` on (subjects × time × channels) difference array.
   - `cluster perm, independent` → `mne.stats.spatio_temporal_cluster_test` on two group arrays.
   - If single-subject (N=1): use trial-level inference, document the limitation.
3b. **Determine the design (within vs between) — this switches BOTH the test and the pairing:**
   - **Within-subject** (same subjects measured under ≥2 conditions; the contrast is a condition difference): compute the per-subject difference `A − B` and feed it to `spatio_temporal_cluster_1samp_test` (one-sample test on the difference). This is the exact analog of FieldTrip `ft_statfun_depsamplesT`. Use `ttest_rel` / `f_mway_rm` for the per-point case. Requires **equal N and matched subject ordering** between conditions.
   - **Between-subject** (different groups, e.g. patients vs controls): feed the two group arrays to `spatio_temporal_cluster_test` (independent). Use `ttest_ind` for the per-point case. Tolerates **unequal N** (e.g. 20 controls vs 18 patients) — never pair.
   - The plan's `contrast` column plus the cohort description determines this. If ambiguous, **stop and ask** — pairing the wrong way silently invalidates the inference.
4. Determine tail from `direction`:
   - "A more negative" → `tail = -1`, threshold must be negative.
   - "A more positive" or "A > B" → `tail = 1`, threshold positive.
   - "any direction" or empty → `tail = 0`, two-sided.

Write `stats-stage/STATS_PLAN.json` summarizing all resolved claims before executing.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json
2. Verify MNE-Python is available → generate MNE-Python code
3. Else → ERROR: MNE-Python required
```

Write `stats-stage/BACKEND_RESOLUTION.md`.

## Phase C — Per-claim execution

For each claim in `STATS_PLAN.json`, write and execute a Python script:

### MNE-Python path (default)

The script must:

1. **Load data**: read `-ave.fif` (ERP) or `-tfr.h5` (TFR) per subject per condition from `erp-stage/` or `tfr-stage/`.
2. **Build arrays**: shape `(n_subjects_or_trials, n_times, n_channels)` for the difference (condition_A - condition_B).
3. **Constrain to ROI + time window**: only include planned channels and time range.
4. **Compute adjacency**: `mne.channels.find_ch_adjacency(info, ch_type="eeg")` on the ROI subset.
5. **Compute the cluster-forming threshold from the design df — do NOT hard-code 1.96 / 2.0.** This is the cluster-FORMING threshold (which data points enter a cluster), a *different* knob from the cluster-LEVEL alpha (whether a formed cluster is significant). `df = n_subjects − 1` for the within/paired one-sample-on-difference design; `df = nA + nB − 2` for independent. For an F-based cluster test, use `scipy.stats.f.ppf(1 - alpha, dfn, dfd)`.
   - `tail=-1`: `threshold = scipy.stats.t.ppf(alpha, df)`  (negative)
   - `tail=1`:  `threshold = scipy.stats.t.ppf(1 - alpha, df)`
   - `tail=0`:  `threshold = scipy.stats.t.ppf(1 - alpha/2, df)`  (halve alpha ONCE, here, for the two-sided forming threshold)
   - **Do not halve alpha a second time at the cluster level.** With `tail=0`, MNE already accounts for two-sidedness internally; judge the returned `cluster_p` against the full `alpha` (e.g. 0.05). FieldTrip users halve `cfg.alpha` to 0.025 because FieldTrip does not — that 0.025 is NOT a second correction to copy into MNE.
   - **Forming-threshold sensitivity is not just "report it" — sanity-check it.** A *low* forming threshold merges genuine and spurious effects and over-spreads cluster extent; a *high* one fragments a single true effect into several small clusters. Before interpreting cluster extent, re-run with two or three forming thresholds and confirm the cluster is stable; when no principled threshold exists, default to **TFCE** (`threshold=dict(start=…, step=…)`) which integrates over thresholds. Use a **permutation** null for the cluster, not a bootstrap (bootstrap cluster nulls can be liberal). Cite: Pernet et al. (2015). Cluster-based computational methods for mass univariate analyses of event-related brain potentials/fields. *J. Neurosci. Methods*, 250, 85–93.
6. **Run**: `mne.stats.spatio_temporal_cluster_1samp_test(X, n_permutations=N, threshold=threshold, tail=tail, seed=SEED, adjacency=adj, out_type="mask")`.
7. **Extract significant clusters**: `cluster_p < alpha`.
8. **Compute effect size**: Cohen's d (or dz for paired) = mean(differences) / std(differences) across the cluster or the planned ROI+window.

> **Robust location for amplitude/latency inference.** ERP amplitude and latency scores are outlier-prone and non-normal, and a single bad subject or trial can shift the mean enough to manufacture or erase an effect — a failure mode that permutation testing does *not* address (permutation handles the null distribution, not a corrupted central tendency). Following the LIMO-EEG convention, default subject-level amplitude/latency summaries to a **20% trimmed mean with a percentile-bootstrap CI** rather than the raw mean and parametric CI. Report the estimator alongside the test. Cite: Pernet et al. (2011). LIMO EEG: a toolbox for hierarchical linear modeling of electroencephalographic data. *Comput. Intell. Neurosci.*, 2011, 831409.

### Brain–behavior correlation (when the claim links an EEG measure to a behavioral score)

For claims like "ERN amplitude predicts post-error slowing" or "frontal-theta power correlates with accuracy", the unit of analysis is a per-subject (or per-trial) **(EEG metric, behavior)** pair, not a condition contrast:

- **Pick the coefficient by the data:** Pearson for linear + roughly bivariate-normal; **Spearman** (rank) when either variable is skewed, ordinal, or has outliers. Always eyeball the scatter first — Anscombe's quartet is the cautionary tale that identical r's hide wildly different shapes (a single leverage point can manufacture or destroy an r).
- **Combine / compare correlations across subjects or ROIs with the Fisher-z transform** (r is not additive; z is): `z = np.arctanh(r)` with `SE = 1/np.sqrt(n-3)`; average/compare in z-space, then back-transform `r = np.tanh(z)`. To test whether two independent correlations differ: `Z = (z1 - z2) / np.sqrt(1/(n1-3) + 1/(n2-3))`.
- **Significance / robustness:** for small N or non-normal data prefer a permutation test (shuffle the behavior labels, recompute r, 5000×) over the parametric p; report the CI from the Fisher-z SE, and FDR across multiple electrodes/ROIs/time-windows just as for the contrast tests above.
- **Single-trial** EEG–behavior coupling (amplitude → RT within subject) is a mixed-effects regression — route to `eeg-behavior` (statsmodels MixedLM), not a subject-level correlation.

Cite: Cohen, M. X. (2014). *Analyzing Neural Time Series Data*, Ch. 27–28 (correlation, Fisher-z, robustness).

### Mass-univariate LMM with crossed subject AND item random effects (lmeEEG)

When stimuli are **sampled** (faces, words, scenes — the classic N400/face/word case) and single-trial data exist, treating the stimulus set as fixed silently inflates Type I error: the inference does not generalize to new stimuli. AEA's existing mixed-effects support (`eeg-behavior`, `eeg-group-compare` MixedLM) carries only a subject random effect (`1|subject`) and either collapses to one scalar per subject or models single-trial *behavior* — it cannot cross subjects with items. (The plain single-trial-LMM idea — Volpert-Esmond et al. 2021 — is already covered by `eeg-behavior`; the genuinely new piece here is the *mass-univariate crossed* design.)

The lmeEEG recipe avoids refitting REML at millions of (channel × time) points: fit the full LMM with crossed subject and item random effects **once** per channel/time point, extract the **marginal EEG** (observed signal minus the estimated random-effect contributions), then run ordinary mass-univariate regression on those marginals followed by cluster/TFCE permutation. Use whenever stimuli are sampled and you want to generalize beyond the specific stimulus set. Cite: Visalli et al. (2024). lmeEEG: Mass linear mixed-effects modeling of EEG data with crossed random effects. *J. Neurosci. Methods*, 401, 110008.

### Time-frequency claims — three routes (pick by hypothesis specificity)

When the claim is on a TFR (`tfr-stage/*-tfr.h5`), build the per-subject array as `(n_subjects, n_freqs, n_times)` for the chosen channel/ROI and choose ONE route:

1. **A-priori TF-ROI averaging (highest power; requires a pre-registered band+window).** Crop to the planned `(fmin:fmax, tmin:tmax)` and average those axes per subject to one value, then run a single (optionally one-sided) test across subjects: `X.mean(axis=(-2,-1))` → `ttest_rel` / `ttest_1samp`. If multiple ROIs/channels, FDR across them. This is the TF analog of `cfg.avgovertime='yes'; cfg.avgoverfreq='yes'`. Double-dipping risk: the band/window MUST come from the plan, never from the grand-average TFR.
2. **Spatial-only cluster after collapsing time+freq.** When only the band and window are hypothesized but the topography is the question, average the freq+time axes per subject first, leaving `(n_subjects, n_channels)`, then cluster over channels with `adjacency=find_ch_adjacency(info,'eeg')`. This is the 'where' test at high power.
3. **Full pixel-wise mass-univariate + FDR (no cluster assumption).** Run `scipy.stats.ttest_rel`/`ttest_ind` over every `(freq,time)` pixel, then mask with `mne.stats.fdr_correction(p, alpha=0.05)`. Cheap and assumption-light, but lower power than cluster permutation; report the FDR-significant region, not the raw p-map.

Prefer cluster-based permutation over the freq×time plane (`permutation_cluster_1samp_test` with TF adjacency) when the effect is contiguous and no a-priori ROI exists — it controls FWER while respecting TF contiguity. **Baseline-correct before any of these** (see Domain Knowledge: baseline modes).

### Factorial within-subject designs (mne.stats.f_mway_rm)

For a 2×2 (or higher) repeated-measures design, do NOT chain pairwise t-tests. Stack per-subject condition data into `(n_subjects, n_conditions, n_signals)` with the condition axis ordered so factor levels nest in a FIXED order (e.g. A1B1, A1B2, A2B1, A2B2 — B varies fastest within A), then:

```python
from mne.stats import f_mway_rm
factor_levels = [2, 2]            # levels per factor, same order as the stacking
F_A,  p_A  = f_mway_rm(X, factor_levels, effects='A')
F_B,  p_B  = f_mway_rm(X, factor_levels, effects='B')
F_AB, p_AB = f_mway_rm(X, factor_levels, effects='A:B')
```

For a corrected map, wrap `f_mway_rm` as the `stat_fun` inside `permutation_cluster_test(..., stat_fun=lambda *a: f_mway_rm(np.stack(a,1), factor_levels, effects='A', return_pvals=False)[0])` rather than FDR-ing per point. Heed Luck & Gaspelin 2017: each extra factor adds interaction terms that inflate Type I error — only run the effects the plan names, and record df for the methods text.

### Source-space and decoding claims (cross-reference)

- **Source space**: use `mne.stats.spatio_temporal_cluster_1samp_test` (within) / `spatio_temporal_cluster_test` (between) with source adjacency `mne.spatial_src_adjacency(src)`, `n_permutations ≥ 1000`, two-tailed. The FieldTrip course convention is `alpha=0.025` per tail = 0.05 overall — in MNE judge `cluster_p < 0.05` with `tail=0` (do not also halve, per Phase C step 5). When whole-brain is underpowered, parcellate first: `mne.extract_label_time_course` over an atlas → one value per label per subject → paired test per label with FDR/Bonferroni across labels. See `eeg-source`.
- **Decoding / RSA vs chance**: test per-subject `(accuracy − chance)` curves with `permutation_cluster_1samp_test(tail=1)` over the post-stimulus window ONLY; state chance explicitly (`1/n_classes`, or 0.5 for binary). For a single global-accuracy p-value use `sklearn.model_selection.permutation_test_score` (n_permutations≥1000; it applies the corrected p=(C+1)/(n+1)). See `eeg-decoding` for the upstream CV/balancing defaults.

## Phase D — Multiple comparisons

**Two distinct levels apply — keep them separate:**

**D1. Within a single mass-univariate test** (many time / freq / channel points in one claim). Pick the method by the *structure* of the expected effect:

| Method | Controls | Use when | MNE call |
|---|---|---|---|
| **Cluster-based permutation** (default) | FWER | Effect is contiguous in time / space / frequency (the EEG norm) | `*_cluster_*_test` (already in Phase C) |
| **FDR (Benjamini–Hochberg)** | FDR | Effect is sparse / non-contiguous, or you want a cheap per-point map without a cluster assumption | `mne.stats.fdr_correction(p_vals, alpha=alpha, method='indep')` → `(reject_bool, p_corrected)` |
| **tmax (max-statistic permutation)** | strong FWER | Sparse / narrow / punctate effect where you DO want per-point "significant here" licence (cluster tests cannot give that) | `mne.stats.permutation_t_test(X)` (single-step max-stat) |
| **Bonferroni** | FWER | A small, pre-specified set of channels×windows only (last resort) | `p_corrected = np.minimum(p_vals * n_tests, 1.0)` |

Bonferroni is over-conservative for autocorrelated EEG points — reserve it for a handful of a-priori comparisons. **Never report an uncorrected p<0.05 map as 'significant'** (uncorrected maps are for visualization only).

> **FIX — the `method='indep'` default is the wrong FDR variant when EEG points are dependent.** The table above (and the Phase E default) hard-code `fdr_correction(..., method='indep')`, which is plain Benjamini–Hochberg and is only proven valid under independence or *positive* dependence with a known structure. Neighbouring EEG time/freq/channel points are positively autocorrelated with a structure you have not characterized, so for an unknown-dependence map use the Benjamini–Yekutieli variant `method='negcorr'` — it controls FDR under arbitrary dependence (at some power cost). Default to `'negcorr'` whenever you cannot justify the independence assumption.
>
> **tmax vs cluster — pick by effect shape.** Single-step max-statistic permutation controls strong FWER at *every individual point*, so — unlike cluster permutation — it legitimately licenses per-electrode / per-timepoint "the effect is significant here" statements, and it is *more* powerful than cluster tests when the effect is narrow or punctate. Rule of thumb: broad/contiguous effect → cluster; sparse/narrow → tmax (`mne.stats.permutation_t_test`). Cite: Groppe, Urbach & Kutas (2011). Mass univariate analysis of event-related brain potentials/fields I. *Psychophysiology*, 48(12), 1711–1725 (tmax and the BY/`negcorr` FDR choice).

**D2. Across claims** (the cross-claim family). If ANALYSIS_PLAN specifies a strategy:
- `Bonferroni N=K` → adjusted alpha = alpha / K for each claim.
- `hierarchical` → primary claim at alpha, secondary at alpha only if primary significant.
- `none` → no correction (single claim or pre-registered).

Apply the correction to the per-claim verdicts.

## Phase E — Write outputs

For each claim, write:

### `stats-stage/<claim_id>_cluster_perm.json`
```json
{
  "claim_id": "C1",
  "claim": "...",
  "test": "spatio_temporal_cluster_1samp_test",
  "n_permutations": 5000,
  "threshold": -1.656,
  "tail": -1,
  "tail_justification": "Directional: auditory more negative",
  "seed": 42,
  "window": [0.08, 0.15],
  "window_matches_plan": true,
  "roi_channels_numbered": ["EEG 004", "..."],
  "roi_channels_1020": ["F3", "Cz", "..."],
  "roi_matches_plan": true,
  "n_observations": 144,
  "n_clusters": 2,
  "significant": [
    {"id": 0, "p": 0.001, "t_sum": -1139.2, "time_ms": [82, 150], "channels_1020": ["Fz","Cz"]}
  ],
  "cohens_d": -0.461,
  "cohens_d_formula": "mean(diff) / std(diff) across observations in ROI+window",
  "adjacency": "Delaunay triangulation from digitized positions, ROI subset",
  "alpha": 0.05,
  "mc_correction": "none (single claim)",
  "verdict": "supports"
}
```

### `stats-stage/<claim_id>_arrays.npz`
Save `t_obs`, `cluster_p`, `H0` for reproducibility.

### Append to `FINDINGS.md`
```markdown
## C1: [claim text]
- Result: [supports / does_not_support / partial]
- Cluster p = [value], [N] permutations, seed [S]
- Cohen's d = [value]
- ROI: [channels], window: [time]
```

### Group grand-average + uncertainty band (for the figure stage)

For any per-subject result handed to `eeg-figure`, **keep the subject axis** — never average across subjects before the test (the analog of FieldTrip `keepindividual='yes'`; collapsing first destroys the data the cluster/ANOVA needs). For the descriptive plot, the published convention is grand-average ± 1 SEM:

```python
avg = X.mean(axis=0)                       # mean over subjects
sem = X.std(axis=0, ddof=0) / np.sqrt(X.shape[0])   # SEM, ddof=0
```

Use `mne.grand_average(evokeds)` or `mne.viz.plot_compare_evokeds(evokeds_dict)` (which draws mean ± SEM, or a bootstrap CI, automatically). State the band definition ("shaded = ±1 SEM, N=…") in the figure caption.

## Phase F — Sanity checks

All must pass before declaring success:

- [ ] Every claim in ANALYSIS_PLAN has a corresponding `stats-stage/<claim_id>_cluster_perm.json`.
- [ ] Every JSON has `window_matches_plan: true` and `roi_matches_plan: true`.
- [ ] No claim was run that isn't in the plan (unless `— exploratory` was passed).
- [ ] FINDINGS.md has a new dated entry for each claim.
- [ ] BACKEND_RESOLUTION.md exists.

## Critical Rules

- **Never** run a stat not in ANALYSIS_PLAN. Exploratory analyses go in `stats-stage/exploratory/` and are labeled `[EXPLORATORY]` in FINDINGS.md.
- **Never** edit ANALYSIS_PLAN after running. If a reviewer asks for additional analyses, add them as exploratory or create a v2 plan with documented reason.
- **Never** change `n_permutations` to chase significance.
- **Never** use `tail=0` when the plan specifies a directional hypothesis (or vice versa).
- **Never** report cluster boundaries as precise onset/offset — cluster permutation only supports "a difference exists somewhere in the tested space."
- **Never** pair a between-subjects contrast or run an independent test on within-subjects conditions — match the test to the design (Phase A step 3b). Paired tests require equal N and matched ordering.
- **Never** copy FieldTrip's `cfg.alpha=0.025` as a second halving in MNE — MNE handles two-sidedness internally; judge `cluster_p < alpha` with `tail=0` (Phase C step 5).
- **Never** average across subjects before a group test, and never present an uncorrected p-map as 'significant' — uncorrected maps are visualization only.
- **Never** select the TF band/window or ERP channel+window from the grand average and then test it (double-dipping) — a-priori ROIs come from ANALYSIS_PLAN only.
- **Refuse to certify** group analyses with very small N (≲12) as adequately powered — flag them as underpowered in FINDINGS.md.

## Domain Knowledge (distilled from EEG methodology literature)

These guidelines are encoded from landmark EEG methodology papers. The LLM must follow them when generating code and interpreting results.

### Cluster permutation interpretation (Sassenhagen & Draschkow 2019, Psychophysiology)

- Cluster-based permutation tests control the family-wise error rate across the tested space, but **do not establish the significance of any individual time point, channel, or frequency**.
- It is incorrect to say "the effect was significant from 80 to 150 ms" based on cluster boundaries. The correct interpretation is: "a significant cluster was identified in the tested space (80–150 ms, channels X, Y, Z)."
- Cluster onset/offset is determined by the arbitrary cluster-forming threshold, not by the true effect onset.
- When reporting: state the cluster p-value, the search space (ROI + window), and the cluster-forming threshold. Do NOT over-interpret temporal or spatial precision.
- Cite: Sassenhagen, J., & Draschkow, D. (2019). Cluster-based permutation tests of MEG/EEG data do not establish significance of effect latency or location. Psychophysiology, 56(6), e13335.

### Avoiding false positives in ERP research (Luck & Gaspelin 2017, Psychophysiology)

- Selecting time windows and electrode sites from the grand average introduces circularity (double-dipping). Use pre-registered or literature-based windows.
- Multi-factor ANOVAs on ERP data inflate Type I error rates because each factor adds interaction terms.
- The ANALYSIS_PLAN must specify channels and time windows BEFORE analysis. `eeg-audit` enforces this via mtime check.
- Cite: Luck, S. J., & Gaspelin, N. (2017). How to get statistically significant effects in any ERP experiment (and why you shouldn't). Psychophysiology, 54(1), 146–157.

### Time-frequency analysis (Cohen 2014, Analyzing Neural Time Series Data)

- For TFR cluster permutation: use `logratio` or `zscore` baseline before statistical comparison across conditions.
- n_cycles should be adaptive (e.g., freqs/2): fewer cycles = better temporal resolution at low frequencies, more cycles = better frequency resolution at high frequencies.
- Beware wavelet edge artifacts: the epoch must be longer than the longest wavelet. If not, either trim the epoch or reduce n_cycles for low frequencies.
- Report: wavelet family (Morlet), frequency range, n_cycles formula, baseline window and mode, decimation factor.
- Cite: Cohen, M. X. (2014). Analyzing Neural Time Series Data: Theory and Practice. MIT Press.

### TFR baseline modes before statistics (Cohen 2014; Grandchamp & Delorme 2011, Front Psychol)

- Baseline correction must happen **before** pixel-wise or ROI TF statistics, and the baseline window must lie inside the cone of influence (specify it in seconds).
- Power is multiplicative and 1/f-dominated, so **plain subtraction (`mode='mean'`) is suboptimal for power** — it leaves units in µV² and lets high-power low frequencies dominate. Some teaching code (e.g. MATLAB TF-FC scripts) uses pure subtraction; treat that as a simplification to avoid for evoked power.
- Mode menu (`mne.baseline.rescale` / `AverageTFR.apply_baseline`):
  - **dB** = `10·log10(power/baseline)` → MNE `mode='logratio'` then ×10 (or report logratio directly).
  - **percent** = `(power − baseline)/baseline·100` → `mode='percent'`.
  - **z-score** = `(power − mean_bl)/std_bl` → `mode='zscore'` (and `'zlogratio'`).
  - **subtract** = `power − mean_bl` → `mode='mean'` (reserve for already-normalized measures).
- **Default: `logratio`(dB) or `percent` for evoked/condition-averaged power; `zscore` for single-trial / decoding inputs.** Report the baseline window and mode in methods (COBIDAS).
- Cite: Cohen, M. X. (2014). Analyzing Neural Time Series Data. MIT Press; Grandchamp, R., & Delorme, A. (2011). Single-trial normalization for event-related spectral decomposition. Frontiers in Psychology, 2, 236.

### COBIDAS-MEEG reporting requirements (Pernet et al. 2020, Nature Neuroscience)

For every statistical test, the methods section must report:
- The statistical test used and its implementation (software + version)
- Number of permutations and RNG seed
- Cluster-forming threshold and how it was derived
- Channel adjacency definition (triangulation, distance, template)
- Alpha level and multiple-comparisons correction
- Effect size metric and formula
- Tail (one-sided vs two-sided) and justification
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.

### Hypothesis-driven vs data-driven ERP statistics (Luck 2014, An Introduction to the ERP Technique, 2nd ed.)

There are three group-level strategies; choosing one controls the multiple-comparison burden:
- **Hypothesis-driven** — fixed ROI + fixed time window from the plan; reduce to **mean amplitude** over the window (`Evoked.get_data(...).mean`) and run ONE across-subject test. Minimal correction needed. Mean amplitude is more robust than peak amplitude for noisy / low-trial data.
- **Data-driven 'when'** — fix the channel/ROI, test point-by-point along time with cluster correction over the time axis (localizes the component window).
- **Data-driven 'where'** — fix the latency, test point-by-point across channels with spatial cluster/adjacency correction (localizes the ROI).
- Peak amplitude and peak latency come from `Evoked.get_peak(mode='abs'/'pos'/'neg', tmin, tmax)`; prefer mean amplitude over a window for inference. The data-driven routes are exploratory unless the resulting window/ROI is then validated on independent data — otherwise it is double-dipping.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press, Ch. 9–10.

### Nonparametric permutation as the small-N / non-normal default (Maris & Oostenveld 2007, J Neurosci Methods)

- For small N or questionable normality (typical of ERP amplitudes, decoding accuracies, connectivity values), prefer a permutation test over parametric t/F. Cluster-based permutation **is** a nonparametric test — for contiguous effects it delivers distribution-free inference *and* FWER control in one step.
- Per-point nonparametric analogs: `scipy.stats.permutation_test` or `mne.stats.permutation_t_test`, still followed by FDR for multiple comparisons.
- Label-permutation nulls (decoding, connectivity) must shuffle **within** the CV / subject grouping to keep the null valid, and report the corrected p = (C+1)/(n_perms+1).
- Cite: Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. Journal of Neuroscience Methods, 164(1), 177–190.

### Bayes factors with mandatory prior-sensitivity reporting (Teichmann et al. 2022, Aperture Neuro)

When a claim needs graded evidence — and especially evidence *for* the null (a null NHST result is mute on whether H0 holds) — offer a Bayes factor alongside the permutation verdict. BFs grade evidence continuously and stay valid under optional stopping, which suits exploratory M/EEG. The M/EEG-specific catch to encode: the BF depends **strongly on the prior width** and on the window/data size, so a single BF is uninterpretable. Always report a **prior-sensitivity robustness curve** — sweep a range of JZS Cauchy prior scales (e.g. 0.3–1.5) and show how the BF moves — rather than one number. Cite: Teichmann et al. (2022). An empirically driven guide on using Bayes factors for M/EEG decoding. *Aperture Neuro*, 2, 1–10.

### Cluster permutation onset estimation (Rousselet et al. 2025, European J Neuroscience)

- Recent work shows cluster-sum methods lead to positively biased and high-variance onset estimates.
- Do not use cluster boundaries to claim precise effect onset times.
- If onset estimation is needed, use dedicated methods (e.g., jackknife, fractional area latency) rather than cluster boundaries.

### Cluster Depth Test — the actual remedy for the localization caveat (Frossard & Renaud 2022, NeuroImage)

The Sassenhagen & Draschkow and Rousselet sections above tell you what you *cannot* say from a cluster test, but offer no escape hatch. The Cluster Depth Test (CDT) is that escape hatch: it provides **point-wise strong FWER control**, so unlike cluster-mass or TFCE it genuinely licenses honest *per-timepoint* and *per-channel* statements about effect onset and extent — while retaining most of the cluster-level sensitivity that makes contiguous-effect detection powerful.

- When a claim needs latency or spatial-extent precision (e.g. "the effect begins at ~120 ms" or "is confined to occipital channels"), run CDT and report it as **point-wise FWER-controlled**, instead of falling back on the "cluster tests cannot localize" disclaimer.
- Reference implementation: R `permuco::clusterlm(..., multcomp='clusterdepth')`. There is no native MNE call yet — generate from raw permutation arrays or shell out to permuco.
- Cite: Frossard, J., & Renaud, O. (2022). The cluster depth tests: Toward point-wise strong control of the family-wise error rate in massively univariate tests with application to M/EEG. *NeuroImage*, 247, 118824.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or has placeholders | Stop. Ask user to fill and freeze the plan. |
| ROI channels not found in data | Stop. Check channel_mapping.json or ask user. |
| No significant clusters | Report as ❌ does_not_support. Do NOT rerun with different params. |
| Cluster spans entire tested window | Report but warn: "cluster hits analysis boundary — consider wider window or note temporal non-specificity." |
| Only 1 subject | Use trial-level test. Document: "single-subject, trial-level inference, does not support population claims." |
| MNE-Python unavailable | Stop. MNE-Python is required for statistics. |
| Within-subject conditions but unequal/mismatched N | Stop. Paired design requires equal N and matched ordering — check the contrast and cohort, do not silently fall back to independent. |
| Plan specifies two-sided but code halves alpha twice (0.025 at cluster level) | Fix: derive forming threshold with `alpha/2`, judge `cluster_p < alpha` with `tail=0`. MNE handles two-sidedness once. |
| TFR claim with no baseline applied before stats | Stop. Apply `logratio`/`percent` (evoked power) or `zscore` (single-trial) baseline inside the COI first. |
| Mass-univariate p-map reported without correction | Reject as 'significant'. Apply cluster permutation (contiguous) or `fdr_correction` (sparse); uncorrected maps are visualization only. |
| Multi-factor design tested with chained pairwise t-tests | Use `mne.stats.f_mway_rm` with `factor_levels`; run only the plan's effects (interactions inflate Type I). |
| Group N ≲ 12 | Run, but label FINDINGS.md entry 'underpowered'; do not certify the claim as adequately powered. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `erp-stage/`, `tfr-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `stats-stage/*.json`, `stats-stage/*.npz`, `stats-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-figure` reads stats results for cluster-masked plots. `eeg-methods-text` reads stats JSON for the paragraph. `eeg-audit` verifies stats match the plan.
