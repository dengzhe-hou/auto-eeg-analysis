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
