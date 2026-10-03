---
name: eeg-ica
description: "Fit ICA per subject and auto-label components (eye/muscle/heart/line/channel-noise) for rejection. Reads preprocess-stage/ output. Backend: MNE-Python + mne-icalabel. Use when user says 'run ICA', 'remove artifacts', 'artifact rejection', 'ICA decomposition', 'ICLabel', or after preprocessing completes."
argument-hint: "[project-dir] [— method: infomax|picard|fastica] [— n_components: 0.99|25|rank] [— threshold: 0.7] [— manual-review: sub-01,sub-03] [— hp-freq: 1.0]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-ica: ICA + automated component labeling

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** — Uses `mne-icalabel` for automated labeling.
- **METHOD = `infomax`** (extended). Override: `— method: picard` for faster convergence, `— method: fastica` for FastICA.
- **N_COMPONENTS = `0.99`** (variance explained). Override: `— n_components: 25` (fixed integer) or `— n_components: rank` (use data rank from preprocessing).
- **REJECT_CLASSES = `["eye blink", "eye movement", "muscle artifact", "heart beat", "line noise", "channel noise"]`** — ICLabel classes to exclude. `"brain"` and `"other"` are never auto-rejected.
- **CONFIDENCE_THRESHOLD = `0.7`** — Minimum ICLabel probability to auto-reject a component. Override: `— threshold: 0.8` (more conservative) or `— threshold: 0.5` (more aggressive).
- **PRE_FILTER_HP = `1.0` Hz** — Temporary 1 Hz high-pass for ICA fitting only (Winkler et al. 2015 best practice). Final data keeps the original bandpass. Override: `— hp-freq: 2.0`.
- **SEED = read from ANALYSIS_PLAN.md `RNG seeds > ICA`**, default `42`.
- **OUTPUT_DIR = `ica-stage/`** — Create if missing.

> Override: `/eeg-ica projects/my-study — backend: mne — method: picard — threshold: 0.8 — manual-review: sub-01`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with ICA parameters specified. **Stop if missing or unfrozen.**
2. `preprocess-stage/` — preprocessed continuous data per subject (`.fif`, `.set`, or `.mat`).
3. `ENVIRONMENT.json` — to resolve backend and available packages.
4. `channel_mapping.json` — if needed for consistent channel labeling.

## Phase A — Resolve parameters

1. Read `ANALYSIS_PLAN.md` for ICA-specific parameters (method, n_components, seed, reject classes, threshold).
2. If ANALYSIS_PLAN specifies values, use them. CLI overrides take priority over ANALYSIS_PLAN values.
3. Determine N_COMPONENTS strategy:
   - `0.99` (float) → variance-explained; MNE will auto-select count.
   - Integer (e.g., `25`) → fixed number of components.
   - `rank` → use the effective rank of the data after preprocessing (accounts for rank reduction from re-referencing, interpolation, or PCA).
4. Write `ica-stage/ICA_PARAMS.json` summarizing resolved parameters before executing.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json
2. Verify MNE-Python + mne-icalabel available → generate MNE-Python code
3. Else → ERROR: MNE-Python and mne-icalabel required
```

Write `ica-stage/BACKEND_RESOLUTION.md`.

## Phase C — Per-subject ICA fitting

For each subject, write and execute a script. The script must handle ICA fitting and component labeling as a single pipeline.

### ICA-readiness gate (run BEFORE fitting)

ICA only separates **spatially-stationary, temporally-independent linear sources** — it cannot remove slow drift or line noise, and it must not be fed huge non-stationary excursions. Confirm all of the following before fitting; if any fails, fix it in `eeg-preprocess`/`eeg-epoch` first, do not proceed:

1. ☐ **Slow drift removed by filtering, not ICA.** The data (or the 1 Hz HP fitting copy) is high-pass filtered. ICA cannot "remove" drift — drift is non-stationary and smears across many components, corrupting the whole decomposition. Filter it out first so only ICA-correctable artifacts (blinks, saccades, cardiac, EMG-elsewhere) remain.
2. ☐ **Line noise removed by notch/CleanLine/ZapLine, not ICA.** While ICLabel has a `line_noise` class, relying on ICA to strip 50/60 Hz wastes components and is unreliable; the notch belongs in preprocessing. Only the residual should reach ICA.
3. ☐ **Epoch-first when the ISI is irregular or short/messy.** For irregular or short inter-stimulus intervals (overlapping responses, jittered/rapid designs), the continuous record between trials is dominated by non-stereotyped between-trial junk. **Epoch first, then fit ICA on the concatenated epochs** so the decomposition models the task-locked structure rather than the inter-trial mess. (For clean, well-spaced continuous data, fitting on continuous `Raw` remains the default — see Critical Rules.)
4. ☐ **Bad-segment deletion + bad-channel interpolation done in the SAME pre-ICA pass.** Interpolate persistently-bad channels and delete/annotate transient all-channel excursions *together, before* ICA — interpolating without removing segments (or vice versa) leaves either rank inconsistencies or huge non-stationary spikes that hijack components. Record `n_interpolated` so `n_components` is reduced accordingly (rank gate below).
5. ☐ **Loose amplitude pass only, pre-ICA.** Any peak-to-peak rejection applied *before* ICA must be **loose** (remove only extreme segments). The **tight** pass (~±60 µV) is reserved for AFTER IC removal (`eeg-epoch`) — see "Two-stage amplitude rejection" in Domain Knowledge. Tight rejection before ICA discards trials that ICA could have cleaned.

Only data that passes this gate is fed to `ica.fit(...)`.

### MNE-Python path (default)

The script must:

1. **Load data**: read preprocessed continuous data from `preprocess-stage/<sub>/<sub>_preprocessed_raw.fif`.
2. **Create filtered copy for ICA fitting** (Winkler et al. 2015):
   ```python
   raw_for_ica = raw.copy().filter(l_freq=PRE_FILTER_HP, h_freq=None)
   ```
   This 1 Hz high-pass removes slow drifts that degrade ICA decomposition. The original `raw` object retains the analysis bandpass.
3. **Determine n_components**:
   ```python
   # Variance-explained approach (default):
   n_components = 0.99
   # Or rank-based:
   n_components = mne.compute_rank(raw_for_ica, rank='info')['eeg']
   # Or fixed integer from ANALYSIS_PLAN
   ```
4. **Fit ICA**:
   ```python
   from mne.preprocessing import ICA
   ica = ICA(
       n_components=n_components,
       method='infomax',          # or 'picard', 'fastica'
       fit_params=dict(extended=True),  # only for infomax
       max_iter='auto',
       random_state=SEED,
   )
   ica.fit(raw_for_ica)
   ```
   - For `method='picard'`: omit `fit_params=dict(extended=True)`, use `fit_params=dict(ortho=False, extended=True)`.
   - For `method='fastica'`: omit `fit_params`.
5. **Auto-label components via ICLabel** (Pion-Tonachini et al. 2019):
   ```python
   from mne_icalabel import label_components
   # ICLabel was trained on COMMON-AVERAGE-REFERENCED components: feed it an
   # average-referenced COPY so its input matches the training distribution.
   # The unmixing weights are unchanged by referencing; only the topographies
   # ICLabel reads are. The analysis re-reference stays deferred (see below).
   raw_for_label = raw_for_ica.copy().set_eeg_reference('average')
   ic_labels = label_components(raw_for_label, ica, method='iclabel')
   # ic_labels is a dict with keys: 'y_pred_proba' (n_components x 7 matrix),
   #   'labels' (list of predicted class names)
   # Classes: brain, muscle, eye, heart, line_noise, ch_noise, other
   ```
5b. **Cross-check with EOG/ECG correlation** (complements ICLabel; SASICA-style). If EOG/ECG channels exist, correlation-based detection is a direct physiological cross-check on the ICLabel labels:
   ```python
   # Requires EOG channels (e.g. 'VEOG', 'HEOG') in the montage
   eog_idx, eog_scores = ica.find_bads_eog(raw_for_ica)          # vertical+horizontal
   # measure='zscore' (default); threshold is in z (default 3.0)
   if any(ch_type == 'ecg' for ch_type in raw_for_ica.get_channel_types()):
       ecg_idx, ecg_scores = ica.find_bads_ecg(raw_for_ica, method='correlation')
   # Muscle: spectral-slope heuristic, no EMG channel needed
   muscle_idx, muscle_scores = ica.find_bads_muscle(raw_for_ica)
   ```
   Use these as corroboration, not a replacement for ICLabel: a component flagged BOTH by ICLabel (eye/heart/muscle >= threshold) AND by the matching `find_bads_*` is a high-confidence reject; a component flagged by only one source is ambiguous and goes to manual review. Record both label sources in `ica_labels.json` (`iclabel_excluded`, `eog_corr_idx`, `ecg_idx`, `muscle_idx`). Note: EOG correlation values are genuinely low even for true ocular ICs (often r ~ 0.2–0.25), so keep the z-threshold conservative (3–4 SD) rather than thresholding on raw r — see Domain Knowledge.
6. **Determine components to exclude**:
   ```python
   exclude = []
   ambiguous = []
   for idx, (label, probs) in enumerate(zip(ic_labels['labels'], ic_labels['y_pred_proba'])):
       max_prob = probs.max()
       if label in REJECT_CLASSES and max_prob >= CONFIDENCE_THRESHOLD:
           exclude.append(idx)
       elif label in REJECT_CLASSES and max_prob < CONFIDENCE_THRESHOLD:
           ambiguous.append(idx)  # flag for manual review
       # 'brain' and 'other' components are never auto-rejected
   ica.exclude = exclude
   ```
7. **Save outputs**:
   ```python
   ica.save(f'ica-stage/{sub}/{sub}_ica.fif', overwrite=True)
   # Save labels JSON
   import json
   label_info = {
       'component_labels': ic_labels['labels'],
       'probabilities': ic_labels['y_pred_proba'].tolist(),
       'excluded': exclude,
       'ambiguous': ambiguous,
       'threshold': CONFIDENCE_THRESHOLD,
       'method': METHOD,
       'n_components_fitted': ica.n_components_,
   }
   with open(f'ica-stage/{sub}/ica_labels.json', 'w') as f:
       json.dump(label_info, f, indent=2)
   ```

## Phase D — Manual review handling

If a subject is in the `MANUAL_REVIEW` list (CLI override) OR has ambiguous components (max ICLabel prob < CONFIDENCE_THRESHOLD for non-brain classes):

1. **Generate topomap report**:
   ```python
   fig = ica.plot_components(picks=ambiguous + exclude, show=False)
   fig.savefig(f'ica-stage/{sub}/{sub}_component_topos.pdf')
   # Also generate time-series view
   fig2 = ica.plot_sources(raw, picks=ambiguous, show=False)
   fig2.savefig(f'ica-stage/{sub}/{sub}_component_sources.pdf')
   ```
2. **Write review request** to `ica-stage/{sub}/MANUAL_REVIEW_NEEDED.md` listing ambiguous components with their top-2 ICLabel classes and probabilities.
3. **Stop processing for that subject** and continue with others. After human review, re-run with updated exclusion list.

## Phase E — Apply ICA and write outputs

For each subject (after exclusion is finalized):

1. **Apply ICA rejection** to the ORIGINAL data (not the 1 Hz filtered copy):
   ```python
   ica = mne.preprocessing.read_ica(f'ica-stage/{sub}/{sub}_ica.fif')
   raw = mne.io.read_raw_fif(f'preprocess-stage/{sub}/{sub}_preprocessed_raw.fif', preload=True)
   ica.apply(raw)  # modifies raw in-place
   raw.save(f'ica-stage/{sub}/{sub}_cleaned_raw.fif', overwrite=True)
   ```
2. **Save per-subject summary** to `ica-stage/<sub>/ica_labels.json`:
   ```json
   {
     "subject": "sub-01",
     "n_components_fitted": 25,
     "method": "infomax_extended",
     "seed": 42,
     "hp_filter_for_fit": 1.0,
     "n_excluded": 3,
     "excluded_components": [0, 4, 12],
     "excluded_labels": ["eye", "muscle", "eye"],
     "excluded_confidences": [0.95, 0.82, 0.91],
     "n_ambiguous": 1,
     "ambiguous_components": [7],
     "ambiguous_labels": ["muscle"],
     "ambiguous_confidences": [0.55],
     "all_labels": ["eye", "brain", "brain", "brain", "muscle", "..."],
     "all_probabilities": [[0.95, 0.02, ...], "..."],
     "threshold": 0.7,
     "backend": "mne+mne_icalabel"
   }
   ```

3. **Append to `FINDINGS.md`**:
   ```markdown
   ## ICA artifact rejection — [date]
   - Method: extended Infomax, seed 42, 1 Hz HP copy for fit
   - Components fitted: [N] (0.99 variance), [M] excluded
   - Per-subject summary:
     | Subject | Fitted | Excluded | Eye | Muscle | Heart | Line | Ch.Noise | Ambiguous |
     |---------|--------|----------|-----|--------|-------|------|----------|-----------|
     | sub-01  | 25     | 3        | 2   | 1      | 0     | 0    | 0        | 1         |
   ```

4. **Write `ica-stage/ICA_REPORT.md`** with:
   - Global parameters (method, seed, n_components, threshold, hp_filter)
   - Per-subject table (components fitted, excluded, breakdown by class)
   - List of subjects requiring manual review
   - Total variance explained before/after rejection
   - Backend and software versions

## Phase F — Sanity checks

All must pass before declaring success:

- [ ] Every subject in `preprocess-stage/` has a corresponding `ica-stage/<sub>/` directory.
- [ ] Every subject has `ica_labels.json` and `*_ica.fif` (or `.set`).
- [ ] Every subject without manual review pending has `*_cleaned_raw.fif` (or `*_cleaned.set`).
- [ ] No `"brain"` component was excluded (ICLabel brain class must never be auto-rejected).
- [ ] No `"other"` component was excluded (ambiguous class must go to manual review, not auto-reject).
- [ ] ICA was fit on the 1 Hz HP-filtered copy, not on the analysis bandpass data.
- [ ] ICLabel was run on an average-referenced copy of the fitting data (matches ICLabel's training input), not on a non-average montage.
- [ ] ICA was applied to the ORIGINAL data (analysis bandpass), not to the 1 Hz filtered copy.
- [ ] `ICA_REPORT.md` exists with per-subject breakdown.
- [ ] `FINDINGS.md` has a new dated ICA entry.
- [ ] `BACKEND_RESOLUTION.md` exists.

## Critical Rules

- **Never** fit ICA on the analysis bandpass data directly. Always use a 1 Hz (or higher) high-pass filtered copy for fitting (Winkler et al. 2015).
- **Never** apply ICA to the filtered copy. Always apply the ICA solution to the original analysis-bandpass data.
- **Never** auto-reject components labeled `"brain"` or `"other"` by ICLabel. Brain components are signal; other components need manual inspection.
- **Never** lower the confidence threshold to reject more components post-hoc. If artifacts remain, re-examine preprocessing or add subjects to manual review.
- **Never** change the ICA seed after inspecting results. The seed must be set before any ICA is run.
- **Never** run ICA without setting a random seed. Reproducibility requires a fixed seed.
- **Never** fit ICA on epoched data unless explicitly justified (continuous data is standard for EEG ICA) — **except** when the ISI is irregular or short/messy, where you should epoch FIRST and fit ICA on the concatenated epochs so the decomposition models task structure rather than inter-trial junk.
- **Never** expect ICA to remove slow drift or line noise — those must be filtered/notched out in `eeg-preprocess` BEFORE ICA. ICA only separates stationary linear sources; feeding it drift or line noise corrupts the decomposition and wastes components.
- **Never** fit ICA before bad-segment deletion + bad-channel interpolation are done in the same pre-ICA pass — leftover transient excursions hijack the decomposition, and un-accounted interpolated channels break the rank (reduce `n_components` by `n_interpolated`).
- **Never** apply a tight peak-to-peak amplitude reject (~±60 µV) before ICA. Use a loose pass pre-ICA (extreme segments only) and reserve the tight pass for AFTER artifact-IC removal (`eeg-epoch`) — otherwise you discard trials ICA could have cleaned.
- **Never** skip reporting the number of excluded components per class. Reviewers need this information.
- **Never** reject a borderline component just to be thorough — when in doubt, KEEP it. Over-rejection wipes out neural signal: removing a single mislabeled frontal IC can destroy part of the ERP (Chaumon et al. 2015). Prefer correction of stereotyped artifacts over trial rejection, and reserve component removal for clear artifacts confirmed by both ICLabel and a `find_bads_*` cross-check or `ica.plot_overlay`.
- **Never** finalize a borderline exclusion without previewing its effect. Run `ica.plot_overlay(raw, exclude=[idx])` (or compare the evoked before/after) and only exclude if the overlay shows clear data improvement without flattening the ERP of interest.

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
- ICA is sensitive to rank deficiency. If the data rank is lower than the number of channels, reduce `n_components` to match the rank, or ICA produces ghost/duplicate components. Each of the following drops rank by a known amount: **average reference removes 1 rank**; **each interpolated bad channel removes 1 rank** (the interpolated channel is a linear combination of its neighbours, not new information). The EEGLAB-standard formula is `n_components = m - n` where `m` = current channel count and `n` = number of interpolated channels, minus 1 more if an average reference was applied before ICA. In MNE, prefer `n_components = mne.compute_rank(inst, rank='info')['eeg']`, which accounts for all of these automatically. Interpolating bad channels *before* ICA without reducing `n_components` is a common error that inflates apparent dimensionality.
- Cite: Makeig, S., Bell, A. J., Jung, T. P., & Sejnowski, T. J. (1996). Independent component analysis of electroencephalographic data. Advances in Neural Information Processing Systems, 8, 145-151.

### PICARD algorithm (Ablin et al. 2018, IEEE Trans. Signal Process.)

- PICARD (Preconditioned ICA for Real Data) is a faster alternative to Infomax that uses a preconditioned L-BFGS optimization.
- Typically converges 10x faster than Infomax with equivalent decomposition quality.
- Available in MNE-Python as `method='picard'` (requires `python-picard` package).
- Recommended for large datasets or when ICA runtime is a bottleneck.
- Can be used with `ortho=False, extended=True` for the extended version.
- Cite: Ablin, P., Cardoso, J. F., & Gramfort, A. (2018). Faster independent component analysis by preconditioning with Hessian approximations. IEEE Transactions on Signal Processing, 66(15), 4040–4049.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or has placeholders | Stop. Ask user to fill and freeze the plan. |
| `preprocess-stage/` missing or empty | Stop. Run `eeg-preprocess` first. |
| `mne_icalabel` not installed | Install via `pip install mne-icalabel`. If unavailable, fall back to manual inspection. Log in BACKEND_RESOLUTION.md. |
| ICA fails to converge | Try: (1) increase `max_iter` to 1000, (2) reduce n_components, (3) switch to PICARD. Document the change. |
| Rank deficiency error | Reduce n_components to data rank: `mne.compute_rank(raw, rank='info')`. Log the rank reduction cause (re-ref, interpolation, PCA). |
| All components labeled `"other"` | ICLabel may be failing. Check: (1) data format matches ICLabel expectations, (2) channel locations are present, (3) data was properly preprocessed. |
| Too many components excluded (>30% of total) | Warning: likely over-rejection. Review threshold, check preprocessing quality, flag for manual review. |
| Brain component has low confidence (<0.5) | Do NOT reject. Flag for manual review. Low brain confidence often means the component mixes brain+artifact — inspect topography and spectrum. |
| No automated labeling available | Generate topomap PDFs and pause for human review. Do NOT auto-reject without ICLabel. |
| ICA fit on wrong data (not 1Hz HP copy) | Re-fit. This is a critical error per Winkler et al. 2015. |
| Peri-auricular / temporal EMG persists after ICA | Peri-auricular muscle is a known ICA-resistant case — it does not decompose into a single removable IC. Annotate and reject the affected segments instead of forcing more components out (EMG elsewhere on the scalp usually does correct via ICA). |
| EOG component has low raw correlation (r ~ 0.2) yet looks ocular | This is normal — true ocular ICs have low raw correlation; that is why `find_bads_eog` thresholds in z (3–4 SD), not on raw r. Trust the z-score / ICLabel label plus topography, not the raw r value. |
| `n_components` >= channel count after interpolation/avg-ref | Rank deficiency. Set `n_components = mne.compute_rank(inst, rank='info')['eeg']`, equivalently `m − n_interpolated − (1 if avg-ref)`. Failing to reduce produces ghost/duplicate ICs. |
| Borderline IC: unclear if neural or artifact | Do not auto-reject. Cross-check ICLabel against `find_bads_*`, inspect topography/spectrum/time-course against the visual-signature table, and run `ica.plot_overlay`. Keep unless removal clearly improves the data. |
| Slow drift or residual line noise still present after ICA | ICA cannot remove these. Go back to `eeg-preprocess`: ensure the high-pass (drift) and notch (line noise) were applied BEFORE ICA, then re-fit. Do not add components to chase drift/line noise. |
| Decomposition dominated by a few huge components / unstable | Non-stationary excursions or un-interpolated bad channels reached ICA. Do bad-segment deletion + bad-channel interpolation in the same pre-ICA pass (loose amplitude only), reduce `n_components` by `n_interpolated`, then re-fit. |
| Irregular / short ISI gives a poor continuous-fit decomposition | Epoch FIRST, then fit ICA on the concatenated epochs so the decomposition models task-locked structure instead of inter-trial junk. |
| Too many trials rejected before ICA | A tight (~±60 µV) amplitude pass was applied pre-ICA. Use only a loose pass before ICA; defer the tight pass (run ±100 µV → tighten ~±60 µV) to `eeg-epoch` AFTER IC removal. |
| Data was re-referenced before ICA | Re-reference belongs LAST (after IC removal). Re-fit ICA on the pre-reference montage; if average reference is needed for rank, add it as `projection=True` rather than a hard re-reference. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `preprocess-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `ica-stage/*_ica.fif`, `ica-stage/*/ica_labels.json`, `ica-stage/*_cleaned_raw.fif`, `ica-stage/ICA_REPORT.md`, `ica-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Previous: `eeg-preprocess` produces the input data. `eeg-ica` should run after preprocessing and before epoching.
- Next: `eeg-epoch` reads cleaned continuous data. `eeg-erp` and `eeg-tfr` stages use ICA-cleaned data. `eeg-audit` verifies ICA parameters match the plan. `eeg-methods-text` reads ICA_REPORT.md for the methods paragraph.
