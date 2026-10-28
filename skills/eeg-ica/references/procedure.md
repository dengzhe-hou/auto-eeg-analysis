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
   n_components = mne.compute_rank(raw_for_ica, rank=None, proj=False)['eeg']
   # Or fixed integer from ANALYSIS_PLAN
   ```
   Resolve the choice from the approved plan. For the rank-based path, estimate
   the actual fitting samples after the planned reference/interpolation steps.
   `proj=False` leaves pending projectors unapplied, matching the fitting samples
   in this example; apply a planned projector first if the fit requires it.
   `rank='info'` uses metadata and does not automatically detect interpolation or
   other sample-level dependencies. Do not subtract those losses again from an
   already measured rank.
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
   # ic_labels is a dict with keys: 'y_pred_proba' (shape (n_components,): the
   #   probability of each component's predicted class) and 'labels' (list of
   #   predicted class names).
   # Classes: brain, muscle artifact, eye blink, heart beat, line noise,
   #   channel noise, other
   # The full (n_components x 7) matrix, columns in the class order above, needed
   # for the top-2 review list (Phase D) and all_probabilities (Phase E), comes from
   #   from mne_icalabel.iclabel import iclabel_label_components
   #   full_proba = iclabel_label_components(raw_for_label, ica)
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
     "excluded_labels": ["eye blink", "muscle artifact", "eye blink"],
     "excluded_confidences": [0.95, 0.82, 0.91],
     "n_ambiguous": 1,
     "ambiguous_components": [7],
     "ambiguous_labels": ["muscle artifact"],
     "ambiguous_confidences": [0.55],
     "all_labels": ["eye blink", "brain", "brain", "brain", "muscle artifact", "..."],
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

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or has placeholders | Stop. Ask user to fill and freeze the plan. |
| `preprocess-stage/` missing or empty | Stop. Run `eeg-preprocess` first. |
| `mne_icalabel` not installed | Install via `pip install mne-icalabel`. If unavailable, fall back to manual inspection. Log in BACKEND_RESOLUTION.md. |
| ICA fails to converge | Try: (1) increase `max_iter` to 1000, (2) reduce n_components, (3) switch to PICARD. Document the change. |
| Rank deficiency error | Estimate the actual fitting data's rank using `mne.compute_rank(raw, rank=None, proj=False)` in the intended projection state. Record the cause and preserve the approved dimensionality rule; do not treat metadata rank as a sample estimate. |
| All components labeled `"other"` | ICLabel may be failing. Check: (1) data format matches ICLabel expectations, (2) channel locations are present, (3) data was properly preprocessed. |
| Too many components excluded (>30% of total) | Warning: likely over-rejection. Review threshold, check preprocessing quality, flag for manual review. |
| Brain component has low confidence (<0.5) | Do NOT reject. Flag for manual review. Low brain confidence often means the component mixes brain+artifact — inspect topography and spectrum. |
| No automated labeling available | Generate topomap PDFs and pause for human review. Do NOT auto-reject without ICLabel. |
| ICA fit on wrong data (not 1Hz HP copy) | Re-fit. This is a critical error per Winkler et al. 2015. |
| Peri-auricular / temporal EMG persists after ICA | Peri-auricular muscle is a known ICA-resistant case — it does not decompose into a single removable IC. Annotate and reject the affected segments instead of forcing more components out (EMG elsewhere on the scalp usually does correct via ICA). |
| EOG component has low raw correlation (r ~ 0.2) yet looks ocular | This is normal — true ocular ICs have low raw correlation; that is why `find_bads_eog` thresholds in z (3–4 SD), not on raw r. Trust the z-score / ICLabel label plus topography, not the raw r value. |
| Requested `n_components` exceeds effective rank after interpolation/average reference | Record measured rank and reference/projection state. Apply the approved rank-aware rule; a measured rank already includes sample dependencies, unlike `rank='info'`. |
| Borderline IC: unclear if neural or artifact | Do not auto-reject. Cross-check ICLabel against `find_bads_*`, inspect topography/spectrum/time-course against the visual-signature table, and run `ica.plot_overlay`. Keep unless removal clearly improves the data. |
| Slow drift or residual line noise still present after ICA | ICA cannot remove these. Go back to `eeg-preprocess`: ensure the high-pass (drift) and notch (line noise) were applied BEFORE ICA, then re-fit. Do not add components to chase drift/line noise. |
| Decomposition dominated by a few huge components / unstable | Non-stationary excursions or un-interpolated bad channels reached ICA. Do bad-segment deletion + bad-channel interpolation in the same pre-ICA pass (loose amplitude only), reduce `n_components` by `n_interpolated`, then re-fit. |
| Irregular / short ISI gives a poor continuous-fit decomposition | Epoch FIRST, then fit ICA on the concatenated epochs so the decomposition models task-locked structure instead of inter-trial junk. |
| Too many trials rejected before ICA | A tight (~±60 µV) amplitude pass was applied pre-ICA. Use only a loose pass before ICA; defer the tight pass (run ±100 µV → tighten ~±60 µV) to `eeg-epoch` AFTER IC removal. |
| Data was re-referenced before ICA | Re-reference belongs LAST (after IC removal). Re-fit ICA on the pre-reference montage; if average reference is needed for rank, add it as `projection=True` rather than a hard re-reference. |
