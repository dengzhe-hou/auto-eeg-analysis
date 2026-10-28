## Domain Knowledge (distilled from EEG methodology literature)

These guidelines are encoded from landmark EEG preprocessing papers. The LLM must follow them when generating code and choosing parameters.

### FIR filter design for ERP (Widmann et al. 2015, Journal of Neuroscience Methods)

- Use windowed sinc FIR filters (Hamming window) for offline EEG preprocessing. Both MNE (`raw.filter()`) and EEGLAB (`pop_eegfiltnew`) default to this and were written by the same author (Andreas Widmann).
- **Transition bandwidth** determines filter order: narrower transition = longer filter = sharper cutoff but more temporal smearing. MNE's `'auto'` mode sets transition bandwidth to min(max(l_freq * 0.25, 2), l_freq) for highpass; accept the default unless there is a specific reason to override.
- **Zero-phase filtering** (forward + backward pass, `phase='zero'` in MNE) is standard for offline analysis — no phase distortion. Never use causal (single-pass) filters for offline ERP unless replicating an online BCI pipeline.
- **Filter order** = 3.3 / transition_bandwidth * sfreq (Hamming window). MNE computes this automatically. If the auto-computed order exceeds the data length, MNE will error — reduce the order or use IIR as a last resort.
- **Passband ripple**: Hamming window yields -53 dB stopband attenuation and 0.0194 dB passband ripple — sufficient for EEG.
- Cite: Widmann, A., Schroger, E., & Maess, B. (2015). Digital filter design for electrophysiological data — a practical approach. Journal of Neuroscience Methods, 250, 34–46.

### Highpass cutoff selection (Tanner et al. 2015; Acunzo et al. 2012)

- **0.1 Hz HP** is the traditional standard for ERP research, but it can leak filter-induced artifacts into short baseline windows (<200 ms), artificially inflating pre-stimulus differences.
- **0.5 Hz HP** is recommended by some authors for P300/N400 work where slow drifts are not of interest and shorter baselines are used (Tanner et al. 2015, Psychophysiology).
- **0.01 Hz HP** (or DC-coupled) is needed for CNV, SPN, or other slow cortical potentials.
- **1.0 Hz HP** is specifically recommended for ICA decomposition (Winkler et al. 2015) — apply this for the ICA training data, then transfer the ICA weights to the 0.1 Hz-filtered data.
- Rule: match the highpass to the analysis goal. If DATASET_BRIEF specifies an ERP with a slow component (CNV, readiness potential), use 0.01–0.05 Hz. For standard ERP, use 0.1 Hz. For ICA-prep, use 1.0 Hz.
- Cite: Tanner, D., Morgan-Short, K., & Luck, S. J. (2015). How inappropriate high-pass filters can produce artifactual effects and incorrect conclusions in ERP studies of language and cognition. Psychophysiology, 52(8), 997–1009.

### Lowpass cutoff and analysis type

- **30 Hz LP** is standard for ERP analysis — removes residual EMG and preserves all ERP components (which are <30 Hz).
- **40 Hz LP** is appropriate when time-frequency analysis up to low gamma is planned.
- **100+ Hz LP** (or no lowpass) is needed for high-gamma analyses (60–150 Hz), somatosensory high-frequency oscillations, or brainstem auditory evoked potentials.
- **Never lowpass below 20 Hz** for ERP — this distorts component morphology and can shift apparent peak latencies (VanRullen 2011).

### Line noise removal: notch vs spectral methods

- **Notch frequency**: 50 Hz in Europe, Asia (except Japan east: 50 Hz, Japan west: 60 Hz), Africa, Oceania. 60 Hz in the Americas, Taiwan, South Korea, Philippines. Always include harmonics (100/120 Hz, 150/180 Hz).
- **Simple notch filter** (`raw.notch_filter()`, `pop_eegfiltnew` with `revfilt=1`) creates a spectral hole — removes signal at exactly the notch frequency plus transition band. Acceptable when no analysis targets that frequency range.
- **CleanLine** (EEGLAB plugin, Mullen 2012) uses multi-taper + Thompson F-statistic to identify and remove sinusoidal line noise without a spectral hole. Preferred for TFR analyses that include 50/60 Hz.
- **ZapLine** (`meegkit.dss.dss_line`, de Cheveigne 2020) uses DSS (denoising source separation) to isolate and remove line noise components. Most robust for data with non-stationary line noise amplitude. Preferred when available.
- **ZapLine-plus** (Klug & Kloosterman 2022) is the adaptive successor and the better default for long or non-stationary recordings: it chunks the recording into spatially-stable segments, **re-estimates the exact line frequency per chunk** (handling mains drift away from a nominal 50/60 Hz), **auto-selects the number of removed components** instead of a single global count, and re-checks the post-cleaning spectrum to confirm the peak is gone without over-removal. Prefer it over a single global frequency/component-count when the recording is long, mobile, or the line peak wanders. The fixed-frequency, fixed-component `dss_line` remains fine for short, stationary lab recordings.
- Rule: for ERP with 30 Hz lowpass, the choice is moot (line noise is already filtered). For TFR or high-gamma work, use CleanLine, ZapLine, or ZapLine-plus (the last when the line frequency is non-stationary).
- Cite: Klug, M., & Kloosterman, N. A. (2022). Zapline-plus: a Zapline extension for automatic and adaptive removal of frequency-specific noise artifacts in M/EEG. Human Brain Mapping, 43, 2743–2758.

### PREP pipeline and robust average reference (Bigdely-Shamlo et al. 2015, Frontiers in Neuroinformatics)

- The PREP pipeline provides a standardized, fully automated preprocessing sequence: line noise removal → robust average reference → bad channel detection (RANSAC + other criteria) → interpolation → final re-reference.
- **RANSAC** (Random Sample Consensus) for bad channel detection: predicts each channel from a random subset of neighboring channels; channels poorly predicted across multiple random subsets are marked bad. More robust than simple correlation or variance thresholds.
- **Robust average reference**: iteratively removes bad channels, computes average reference on the remaining channels, re-detects bad channels on the re-referenced data, and repeats until stable. This avoids the chicken-and-egg problem where bad channels corrupt the average reference.
- In Python: `pyprep.PrepPipeline(raw, prep_params, montage)` runs the full pipeline. For just bad channel detection: `pyprep.NoisyChannels(raw)` followed by `.find_all_bads()`.
- Cite: Bigdely-Shamlo, N., et al. (2015). The PREP pipeline: standardized preprocessing for large-scale EEG analysis. Frontiers in Neuroinformatics, 9, 16.

### Rank after interpolation and reference — set ICA n_components to the true rank (Winkler et al. 2015; Makoto Miyakoshi pipeline)

- Each operation that creates a linear dependency among channels reduces the data rank: **every interpolated bad channel costs 1 rank**, and an **average reference costs 1 rank** (the channels now sum to ~0).
- The downstream ICA must therefore use `n_components = n_eeg_channels − n_interpolated − (1 if average reference was applied)`. EEGLAB spells this out as `pop_runica(EEG, 'extended', 1, 'pca', m−n)` where m = current channel count and n = interpolated channels; plain `'extended', 1` (full rank) is only correct when nothing was interpolated and no average reference was applied.
- Estimate the rank from the actual EEG samples supplied to ICA, for example `mne.compute_rank(raw, rank=None, proj=False)['eeg']` when fitting the current samples without applying pending projectors. `rank='info'` derives rank from metadata rather than estimating it from the signal, so it can miss interpolation-induced dependencies. Record the projection state and measured rank; do not subtract interpolation/reference losses again from that measured result. Over-specifying `n_components` on rank-deficient data makes the decomposition unstable. See [MNE ICA rank guidance](https://mne.tools/stable/generated/mne.preprocessing.ICA.html#notes).
- This is why `preprocess_summary.json` records `n_interpolated` and `avg_ref_applied` — they are the inputs the `eeg-ica` stage needs to set `n_components` correctly.
- Cite: Winkler, I., Debener, S., Müller, K.-R., & Tangermann, M. (2015). On the influence of high-pass filtering on ICA-based artifact reduction in EEG-ERP. EMBC 2015, 4101–4105. (rank/HP guidance also encoded in the Makoto Miyakoshi preprocessing pipeline, SCCN.)

### Artifact morphology in `raw.plot()` and how to treat each (Luck 2014, ch. 6)

When pre-screening continuous data (`raw.plot()`, default display scale ~50–70 µV/channel), the following morphologies recur. Recognising them tells you whether the fix is a filter, an interpolation, an ICA component, or a deleted segment:

| Pattern (raw view) | Morphology | Handling |
|---|---|---|
| Eye blink | Sharp high-amplitude frontal deflections recurring ~1 Hz | ICA (frontal, removable) |
| Eye drift | Slow large rolling undulations across many channels | ICA; aggravated by too-low highpass |
| Temporal/peri-auricular EMG | High-frequency "fuzz" concentrated on ear-adjacent channels | EMG elsewhere → ICA; **peri-auricular muscle is ICA-resistant** — may need segment rejection |
| Swallowing | Burst of dense high-amplitude spiky activity in a short window | Annotate + reject segment (not ICA) |
| Sweating / overheating | Very slow large baseline ramp at frontal channels | Higher highpass (≥0.1 Hz) handles it |
| Head movement | Huge crossing low-frequency swings, all channels | **Uncorrectable** — annotate `'bad'` and delete the segment |
| Bad electrode | One channel persistently flat or noisy | `interpolate_bads` (spherical) |

These same patterns corroborate ICA component labels in the next stage: a component whose time course matches the blink/eye-drift morphology and has a frontal topography is a confident ocular reject.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd ed., ch. 6 (artifact identification). MIT Press.

### Surface Laplacian / Current Source Density as a reference-free spatial transform (Perrin et al. 1989; Kayser & Tenke 2006)

- **CSD (surface Laplacian)** estimates the second spatial derivative of the scalp potential, which is **reference-independent** and sharpens topographies by attenuating volume-conducted, spatially-broad activity. It is an optional alternative/complement to choosing a reference.
- In MNE: `mne.preprocessing.compute_current_source_density(raw_or_epochs)` (Perrin spherical-spline CSD). It requires a montage with 3D positions and outputs units of V/m² (`csd` channel type). Apply it *instead of* a conventional reference, not on top of one.
- Trade-off: CSD removes broad/reference-dependent components and reduces volume conduction (useful before sensor-space connectivity), but lowers SNR and discards far-field/deep contributions — so it is not appropriate for analyses that need absolute potentials. For functional-connectivity work, CSD-before-FC plus a volume-conduction-insensitive metric is the most defensible "double-insurance" combination (see `eeg-connectivity`).
- Cite: Kayser, J., & Tenke, C. E. (2006). Principal components analysis of Laplacian waveforms as a generic method for identifying ERP generator patterns. Clinical Neurophysiology, 117(2), 348–368; Perrin, F., et al. (1989). Spherical splines for scalp potential and current density mapping. EEG & Clin. Neurophysiol., 72(2), 184–187.

### End-to-end canonical order, ICA placement, and re-reference-last (Luck 2014; Makoto Miyakoshi pipeline; teaching EEGLAB history)

- The full ERP pipeline order taught in practice is: **import → set montage → drop/re-type non-scalp refs + manual bad-channel pass → filter (HP ~0.1, LP ~40, then notch) → resample → epoch + baseline → (epoch stage) interpolate bad channels + reject bad epochs → ICA (extended Infomax) → remove artifact ICs → POST-ICA amplitude sweep (run at ±100 µV, tighten to ~±60 µV for clean data) → re-reference LAST (e.g. linked mastoids)**. This is the sequence in Steve Luck's ERPLAB-style teaching pipeline and the SCCN/Makoto Miyakoshi "Makoto's preprocessing pipeline", and is exactly what a teaching EEGLAB command history walks through.
- **Always notch**, even when the low-pass cutoff is below the line frequency. The low-pass FIR has a finite transition band and ringing, and line harmonics/leakage can survive it; the unconditional notch is cheap and removes a common residual 50/60 Hz peak.
- **Downsample only after filtering.** Resampling first aliases line noise and high-frequency content into the passband; the anti-alias filter at the lower rate also interacts badly with subsequent band-pass edges.
- **Reference order follows the approved pipeline.** Some workflows apply the final reference after ICA; others fit ICA after an applied average reference with the corresponding rank reduction. Preserve the selected sequence and match the decomposition's fitting/application configuration. A pending `projection=True` projector leaves the samples unchanged and does not implement an applied average reference.
- **Two-stage amplitude rejection straddles ICA.** A *loose* peak-to-peak pass before ICA only removes the few extreme non-stationary segments that would otherwise dominate the decomposition; the *tight* pass (run at ±100 µV, then tighten toward ~±60 µV for clean recordings) is applied AFTER ICA has corrected the stereotyped artifacts, so it does not throw away trials that ICA could have salvaged.
- **Re-baseline after any re-filter of baselined epochs.** Filtering reshapes the baseline window, invalidating the prior baseline correction; re-run `apply_baseline` (or, preferably, finalize filtering on continuous `Raw` before epoching).
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd ed. (recommended processing order). MIT Press. See also Bigdely-Shamlo et al. (2015) and the SCCN "Makoto's preprocessing pipeline" (Miyakoshi, UCSD SCCN wiki) for the ICA-placement and rank conventions.

### Why preprocessing order matters (Robbins et al. 2020, Frontiers in Neuroinformatics)

- The canonical order is: **filter → bad channel detection → interpolation → re-reference → (optional: ICA → epoch)**.
- **Filter before bad channel detection**: unfiltered data contains slow drifts and line noise that inflate variance-based and correlation-based bad channel metrics, causing false positives.
- **Interpolate before re-referencing**: if bad channels are included in the average reference, they bias the reference and distort all channels. Interpolate first (or use robust average reference which handles this iteratively).
- **Reference state and rank**: an applied average reference makes the EEG rank deficient by one in an otherwise full-rank montage. A pending `projection=True` projector does not change the samples. The fitting and application data must follow the approved reference scheme and measured rank, without double-counting rank losses.
- **Downsampling**: preserve the planned stage and rate, account for anti-alias filtering and event-time precision, and distinguish MNE resampling from unfiltered decimation as described in Phase C.
- Cite: Robbins, K. A., et al. (2020). How sensitive are EEG results to preprocessing methods: a benchmarking study. IEEE Transactions on Neural Systems and Rehabilitation Engineering, 28(5), 1081–1090.

### FASTER automated artifact rejection (Nolan et al. 2010, Journal of Neuroscience Methods)

- FASTER (Fully Automated Statistical Thresholding for EEG artifact Rejection) uses z-score thresholds on multiple statistical properties at each processing level: channel-level, epoch-level, and component-level.
- Channel-level metrics: variance, mean correlation with other channels, Hurst exponent. Channels with any metric |z| > 3 are marked bad.
- While FASTER was designed for the full pipeline (including epoching and ICA), its channel-level metrics can be used as a complement to RANSAC for bad channel detection in the preprocessing stage.
- In MNE: no built-in FASTER, but the metrics can be computed manually. In EEGLAB: available as the FASTER plugin.
- Cite: Nolan, H., Whelan, R., & Reilly, R. B. (2010). FASTER: Fully Automated Statistical Thresholding for EEG artifact Rejection. Journal of Neuroscience Methods, 192(1), 152–162.

### Population-aware policy: a developmental retention mode (MADE, Debnath et al. 2020)

- The default channel/segment policy above is tuned for adult lab data, where dropping a few contaminated channels or trials costs little. For **infant, child, or clinical** sessions — which are short and heavily contaminated, so aggressive rejection can leave too little data to analyse — switch to a `--population: developmental` policy that **prioritises data retention over purity** (MADE, the Maryland Analysis of Developmental EEG pipeline). Concretely: correct/interpolate *within* epochs (interpolate the bad channels for that epoch only) rather than dropping whole channels or whole trials, and loosen the bad-channel and segment thresholds so a normally contaminated developmental recording does not collapse to zero usable epochs. Report the looser thresholds explicitly so the retention trade-off is auditable.
- Cite: Debnath, R., et al. (2020). The Maryland Analysis of Developmental EEG (MADE) pipeline. Psychophysiology, 57, e13580.

### File-level quality rating for big-data inclusion (Automagic, Pedroni et al. 2019)

- `eeg-qc` gates on per-metric thresholds, but large datasets also need a single citable file-level sort key for inclusion/exclusion. Automagic assigns each recording a **Good / OK / Bad** rating from three quantities: the **Overall-High-Amplitude** fraction, the **Timepoints-of-High-Variance** fraction, and the **Ratio-of-Bad-Channels**. Compute these per subject after cleaning and record the rating in `preprocess_summary.json` (and surface it in `PREPROCESS_REPORT.md`) so downstream group stages can drop "Bad" files with a documented, reproducible criterion rather than ad-hoc eyeballing. This complements, not replaces, the per-metric gates in `eeg-qc`.
- Cite: Pedroni, A., Bahreini, A., & Langer, N. (2019). Automagic: standardized preprocessing of big EEG data. NeuroImage, 200, 460–473.

### COBIDAS-MEEG preprocessing reporting requirements (Pernet et al. 2020, Nature Neuroscience)

For every preprocessing step, the methods section must report:
- **Filter**: type (FIR/IIR), design (windowed sinc, Butterworth), window (Hamming, Kaiser), order or transition bandwidth, cutoff frequencies (-6 dB or -3 dB point — MNE uses -6 dB), phase (zero-phase/causal), software and version.
- **Line noise**: method used (notch, CleanLine, ZapLine), frequency, bandwidth.
- **Bad channels**: detection method (RANSAC, manual, FASTER), criteria and thresholds, number detected per subject (mean, range).
- **Interpolation**: method (spherical spline, nearest neighbor), number interpolated per subject.
- **Re-reference**: scheme (average, mastoid, REST), whether robust (PREP) or simple.
- **Resampling**: original and target sample rate, anti-aliasing filter details.
- **Order of operations**: the exact sequence of preprocessing steps.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.
