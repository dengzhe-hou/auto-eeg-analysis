## Domain Knowledge (distilled from EEG methodology literature)

These guidelines are encoded from landmark ICA methodology papers. The LLM must follow them when generating code and interpreting results.

### High-pass filtering for ICA fitting (Winkler et al. 2015, J Neurosci Methods)

- ICA decomposition quality degrades with slow drifts. A 1 Hz high-pass filter on the ICA training data dramatically improves decomposition.
- The recommended workflow: (1) apply 1 Hz HP to a COPY of the data, (2) fit ICA on the copy, (3) transfer the ICA weights to the original (lower HP) data, (4) apply artifact rejection on the original data.
- This is critical for ERP research where the analysis bandpass may be 0.1 Hz or lower — fitting ICA at 0.1 Hz produces poor decompositions.
- If the analysis bandpass is already >= 1 Hz, the separate filtered copy is unnecessary but harmless.
- Cite: Winkler, I., Debener, S., Muller, K. R., & Tangermann, M. (2015). On the influence of high-pass filtering on ICA-based artifact reduction in EEG-ERP. 37th Annual International Conference of the IEEE Engineering in Medicine and Biology Society (EMBC), 4101–4105.

### ICA placement, pre-cleaning, and two-stage amplitude rejection (Makeig et al. 1996; Luck 2014; SCCN Makoto pipeline)

- **ICA cannot remove what is not a stationary linear source.** Slow drift and line noise must be removed *before* ICA by filtering/notch — feeding them to ICA wastes components and corrupts the unmixing (drift is non-stationary; line noise is better killed by a notch/CleanLine/ZapLine). The role of ICA is to correct stereotyped, spatially-fixed artifacts: blinks, saccades, cardiac, and EMG that decomposes (not peri-auricular muscle, which is ICA-resistant). Pre-clean first so only ICA-correctable artifacts remain.
- **Bad-segment deletion and bad-channel interpolation belong in the same pre-ICA pass.** Big transient all-channel excursions (movement, swallows, pops) are non-stationary and will dominate the decomposition if left in; persistently-bad channels must be interpolated so the rank is known. Do both together before fitting, and reduce `n_components` by the number of interpolated channels (rank gate, Makeig/EEGLAB convention) — interpolating without segment deletion (or vice versa) leaves the decomposition either rank-inconsistent or hijacked by spikes.
- **Epoch FIRST, then ICA, for irregular or short/messy ISI.** With overlapping/jittered/rapid designs the continuous inter-trial record is mostly non-stereotyped junk; concatenating clean task epochs and fitting ICA on those gives a cleaner decomposition than fitting the raw continuous stream. For clean, well-spaced data, continuous fitting remains standard.
- **Two-stage amplitude rejection straddles ICA.** Stage 1 (pre-ICA): a *loose* peak-to-peak threshold that only removes the few extreme segments that would otherwise dominate components. Stage 2 (post-ICA, in `eeg-epoch`): a *tight* threshold — run at ±100 µV and tighten toward ~±60 µV for clean recordings — applied only after artifact-IC removal, so it does not discard trials ICA could have salvaged. Doing the tight pass before ICA throws away recoverable data; doing only a loose pass and never tightening leaves residual artifact in the average.
- **Re-reference is deferred until after IC removal** (handled in `eeg-preprocess`/`eeg-epoch`): the reference is a linear channel operation that changes the mixing matrix, so applying it before ICA degrades the decomposition. Fit ICA on the pre-reference montage. **Caveat for the ICLabel step:** deferring the reference applies to the *analysis* data and to the `ica.fit` input — it does NOT mean ICLabel should see pre-reference topographies. ICLabel was trained on common-average-referenced components, so classification degrades out-of-distribution on a non-average montage. Pass `label_components` a `set_eeg_reference('average')` COPY (re-referencing leaves the unmixing weights untouched and only rotates the component maps ICLabel reads), while the substantive re-reference still happens last. See the ICLabel note below.
- Cite: Makeig, S., Bell, A. J., Jung, T. P., & Sejnowski, T. J. (1996). Independent component analysis of electroencephalographic data. Advances in Neural Information Processing Systems, 8, 145–151. See also Luck, S. J. (2014), An Introduction to the Event-Related Potential Technique, 2nd ed. (recommended ICA placement and amplitude-rejection order), MIT Press, and the SCCN "Makoto's preprocessing pipeline" (Miyakoshi, UCSD SCCN wiki) for pre-ICA cleaning and rank conventions.

### ICA best practices for ERP research (Chaumon et al. 2015, Front Neurosci)

- ICA requires sufficient data: a rule of thumb is 20x(n_channels^2) data points minimum (e.g., 64 channels -> ~82K points at 1 kHz -> ~82 seconds). If data is shorter, reduce n_components.
- Component inspection should check: (1) topography (focal vs distributed), (2) power spectrum (1/f for brain, peaks for artifacts), (3) time course (stereotyped patterns for blinks/saccades), (4) trial-to-trial image (locked to stimulus or not).
- Automated labeling (ICLabel) should be used as a first pass, but ambiguous components (confidence < threshold) should be flagged for manual review, especially in clinical or small-N studies.
- Removing too many components degrades signal. Track the percentage of variance removed and flag if > 20% of total variance is rejected.
- Cite: Chaumon, M., Bishop, D. V., & Busch, N. A. (2015). A practical guide to the selection of independent components of the electroencephalogram for artifact correction. Journal of Neuroscience Methods, 250, 47-63.

### Quantitative IC-selection measures and their MNE equivalents (Chaumon et al. 2015 SASICA; Nolan et al. 2010 FASTER; Mognon et al. 2011 ADJUST)

SASICA validated several quantitative measures against expert consensus, each with a default threshold. Map them onto MNE as follows:

| SASICA / FASTER / ADJUST measure | What it detects | Default threshold | MNE equivalent |
|---|---|---|---|
| Correlation with vertical/horizontal EOG | Blinks, saccades | conservative 4 SD (not 2 SD) | `ica.find_bads_eog(raw, measure='zscore')` (z-threshold, default 3.0) |
| Correlation with ECG channel | Heartbeat | adaptive z | `ica.find_bads_ecg(raw, method='correlation')` |
| Autocorrelation at short lag (low → muscle); high-frequency spectral slope (FASTER) | EMG / muscle | adaptive 2 SD | `ica.find_bads_muscle(raw)` |
| Single-dipole fit residual variance | Neural-component criterion | keep if RV < 15% | `mne.fit_dipole` on `ica.get_components()` map + a forward model |
| Focal topography (z-score of inverse weights across channels) | Bad-channel / focal IC | conservative 4 SD | ICLabel `ch_noise` class; or inspect `ica.plot_components` |
| Temporal kurtosis + spatial average/variance difference (ADJUST) | Blinks | dataset-adaptive | ICLabel `eye` class |
| Low SNR (pre- vs post-stimulus power) | Noise ICs | off by default | not built into MNE |

Key thresholds to encode: EOG/bad-channel correlation uses a more conservative **4 SD** (not the 2 SD used for other measures) because true ocular ICs have surprisingly low raw correlation (r ~ 0.2–0.25); and the **15% dipole residual-variance** cutoff is the EEGLAB/SASICA default distinguishing a clean neural IC from a mixed/artifact IC. ICLabel + `find_bads_*` together cover most of these; dipole RV requires a forward model and is optional.

- Cite: Chaumon, M., Bishop, D. V., & Busch, N. A. (2015). A practical guide to the selection of independent components of the electroencephalogram for artifact correction. Journal of Neuroscience Methods, 250, 47-63 (SASICA).
- Cite: Nolan, H., Whelan, R., & Reilly, R. B. (2010). FASTER: Fully Automated Statistical Thresholding for EEG artifact Rejection. Journal of Neuroscience Methods, 192(1), 152-162.
- Cite: Mognon, A., Jovicich, J., Bruzzone, L., & Buiatti, M. (2011). ADJUST: An automatic EEG artifact detector based on the joint use of spatial and temporal features. Psychophysiology, 48(2), 229-240.

### ICLabel: automated component classification (Pion-Tonachini et al. 2019, NeuroImage)

- ICLabel is a deep-learning classifier trained on ~6000 expert-labeled components from the EEGLAB community.
- Seven output classes: **Brain**, **Muscle**, **Eye**, **Heart**, **Line Noise**, **Channel Noise**, **Other**.
- The classifier outputs a probability distribution over all 7 classes. The predicted class is the argmax, but the probability should be used for thresholding.
- Recommended workflow: auto-reject components where the artifact class probability >= 0.7. Components with lower confidence should be flagged for manual review.
- ICLabel was trained on data processed with specific parameters; using very different preprocessing may degrade classification accuracy. Concretely, the training set was common-average-referenced and band-passed ~1–100 Hz before extended-Infomax decomposition, so the labeling step expects an average-referenced decomposition. **Feed `label_components` a `set_eeg_reference('average')` copy of the fitting data** (Phase C step 5); the 1 Hz HP fitting copy already matches the training filter, and average-referencing only rotates the topographies ICLabel inspects without changing the unmixing weights. Skipping this leaves ICLabel scoring out-of-distribution component maps. This is distinct from the deferred *analysis* re-reference, which still happens after IC removal.
- The `mne_icalabel` Python package ports ICLabel to MNE-Python. The reference implementation is the EEGLAB ICLabel plugin.
- Cite: Pion-Tonachini, L., Kreutz-Delgado, K., & Makeig, S. (2019). ICLabel: An automated electroencephalographic independent component classifier, dataset, and website. NeuroImage, 198, 181-197.

### Visual IC signatures for human review (Chaumon et al. 2015)

When `plot_components` / `plot_properties` / `plot_sources` output is reviewed (Phase D), match each component against these signatures. ICLabel automates this, but human review of ambiguous ICs should use the same cues:

| Type | Topography | Time course | Spectrum |
|---|---|---|---|
| **Neural** | smooth / dipolar | strong evoked response, high autocorrelation | 1/f with physiological peak (delta 1–4, theta ~5, alpha 8–12, beta 15–30 Hz) |
| **Blink (vertical eye)** | frontal, flat elsewhere, polarity flips below the eyes | very large, recurs ~1 Hz, ranks in first dozen ICs | no physiological peak; high VEOG correlation |
| **Horizontal saccade** | bilateral frontal, opposite sign left/right | step-like | high HEOG correlation |
| **Muscle** | focal at cap edge (neck / jaw / temporal) | steady noisy, low autocorrelation | power rising > 20–30 Hz |
| **Bad channel** | single focal electrode | noisy | high correlation with that one channel |
| **ECG / heartbeat** | broad, gradient-like | regular RR-spaced deflections ('rain-drop' scatter) | — |
| **Line noise** | near ground electrode, very regular per trial | regular | sharp 50/60 Hz peak |

Heuristic from the SASICA material: a large fraction of neural ICs fall among the high-variance early components, so do not assume high-variance early components are all artifacts.

- Cite: Chaumon, M., Bishop, D. V., & Busch, N. A. (2015). A practical guide to the selection of independent components of the electroencephalogram for artifact correction. Journal of Neuroscience Methods, 250, 47-63 (Figs 2–6, Sections 2.1).

### Original Infomax ICA (Makeig et al. 1996, TINS; Bell & Sejnowski 1995)

- ICA for EEG assumes that cortical sources, ocular artifacts, and other signal generators are spatially fixed and temporally independent.
- Extended Infomax (Lee et al. 1999) handles both super-Gaussian (e.g., eye blinks — sparse, peaked) and sub-Gaussian (e.g., line noise — smooth, uniform) source distributions. Always use extended mode.
- The mixing matrix (A) and unmixing matrix (W) define the linear transformation: sources = W * data, data = A * sources.
- ICA is sensitive to rank deficiency. An applied average reference and interpolated channels create linear dependencies; the usual channel-count-minus-losses formula is a useful cross-check. For a rank-based approved fit, estimate the actual fitting samples with `mne.compute_rank(inst, rank=None, proj=False)['eeg']` in the projection state used for fitting. `rank='info'` does not measure these sample dependencies. A pending average-reference projector leaves the samples unchanged; account for whether it was applied, and do not subtract the same loss twice. See [MNE ICA rank guidance](https://mne.tools/stable/generated/mne.preprocessing.ICA.html#notes).
- Cite: Makeig, S., Bell, A. J., Jung, T. P., & Sejnowski, T. J. (1996). Independent component analysis of electroencephalographic data. Advances in Neural Information Processing Systems, 8, 145-151.

### PICARD algorithm (Ablin et al. 2018, IEEE Trans. Signal Process.)

- PICARD (Preconditioned ICA for Real Data) is a faster alternative to Infomax that uses a preconditioned L-BFGS optimization.
- Typically converges 10x faster than Infomax with equivalent decomposition quality.
- Available in MNE-Python as `method='picard'` (requires `python-picard` package).
- Recommended for large datasets or when ICA runtime is a bottleneck.
- Can be used with `ortho=False, extended=True` for the extended version.
- Cite: Ablin, P., Cardoso, J. F., & Gramfort, A. (2018). Faster independent component analysis by preconditioning with Hessian approximations. IEEE Transactions on Signal Processing, 66(15), 4040–4049.
