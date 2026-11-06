## Constants

Scientific values below describe available example configurations. Resolve
method, dimensionality, classes, threshold, fitting filter, reference and seed
from the approved plan; these examples do not fill missing study decisions.

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

1. Read `ANALYSIS_PLAN.md` for ICA-specific parameters (method, n_components, seed, reject classes, threshold, corroboration and ambiguous-component handling). Carry the approved rejection settings into `approved_ica_params['rejection_policy']`: `reject_classes`, `probability_threshold`, `require_corroboration`. Record `ambiguous_action` as approved (`await_review` or `keep_flagged`); do not fill a missing choice from an example.
2. Use the approved values. An explicitly authorized user override can amend the plan; an agent-generated CLI argument does not authorize a new scientific choice.
   Also resolve `fit_domain` (`continuous` or `epochs`) and `analysis_input`.
   Epoch-first input comes from `eeg-epoch`'s initial cut; the matching original
   analysis-bandpass epochs must survive separately from the fitting copy.
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
3. ☐ **Use the approved fitting domain.** For `continuous`, use preprocessed Raw. For `epochs`, use the saved pre-ICA epochs with the approved baseline and segment handling. Short/irregular ISI is not evidence that all inter-trial data are artifacts and does not automatically select epoch-first ICA.
4. ☐ **Approved bad-segment handling and interpolation completed.** Record interpolated channels and the actual reference/projection state before resolving dimensionality. A measured rank already includes sample dependencies; do not subtract interpolation losses again or subtract a channel count from a variance fraction. Preserve the approved handling rather than adding interpolation or rejection unasked.
5. ☐ **Approved pre-ICA handling only.** Verify its stage, channel scope and threshold definition. Preserve the approved post-ICA rejection settings for `eeg-epoch`; do not add or tighten a threshold from an example.

Only data that passes this gate is fed to `ica.fit(...)`.

### MNE-Python path (default)

The script must:

1. **Load the approved analysis input.** In the snippets below, `raw` denotes
   this original analysis instance and may be Raw or Epochs:
   ```python
   # AEA example: ica-analysis-input
   if approved_ica_params['fit_domain'] == 'continuous':
       raw = mne.io.read_raw_fif(approved_ica_params['analysis_input'], preload=True)
   elif approved_ica_params['fit_domain'] == 'epochs':
       raw = mne.read_epochs(approved_ica_params['analysis_input'], preload=True)
   else:
       raise ValueError('Resolve the ICA fitting domain before running')
   ```
2. **Create filtered copy for ICA fitting** (Winkler et al. 2015):
   ```python
   raw_for_ica = raw.copy().filter(l_freq=PRE_FILTER_HP, h_freq=None)
   ```
   This 1 Hz high-pass removes slow drifts that degrade ICA decomposition. The original `raw` object retains the analysis bandpass.
3. **Determine n_components**:
   ```python
   requested = approved_ica_params['n_components']
   if requested == 'rank':
       n_components = mne.compute_rank(raw_for_ica, rank=None, proj=False)['eeg']
   else:
       n_components = requested  # Approved integer or variance fraction.
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
   # Use the actual fitting instance, with the same channels and reference.
   # Do not change its reference only for labeling an existing decomposition.
   raw_for_label = raw_for_ica
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
   ICLabel's documented design uses extended infomax on common-average EEG
   filtered at 1–100 Hz. The supplied instance is the one used for fitting.
   Record actual reference, channels, filter and algorithm, and any deviation
   from those conditions. Do not claim a labeling-only reference change makes
   an existing decomposition match its training conditions. Preserve the
   approved analysis/labeling policy; changes to fitting, reference, filtering
   or automated exclusion require the researcher's choice when unresolved.
   See [ICLabel input requirements](https://mne.tools/mne-icalabel/stable/generated/api/mne_icalabel.iclabel.iclabel_label_components.html).
5b. **Collect the corroboration required by the approved policy.** Missing reference channels mean unavailable evidence, not a successful cross-check. Detector settings also come from the approved plan:
   ```python
   policy = approved_ica_params['rejection_policy']
   eog_idx = ecg_idx = muscle_idx = None
   if policy['require_corroboration']:
       types = raw_for_ica.get_channel_types()
       classes = policy['reject_classes']
       if 'eog' in types and any(label in classes for label in ('eye blink', 'eye movement')):
           eog_idx, eog_scores = ica.find_bads_eog(raw_for_ica, **approved_ica_params['eog_check'])
       if 'ecg' in types and 'heart beat' in classes:
           ecg_idx, ecg_scores = ica.find_bads_ecg(raw_for_ica, **approved_ica_params['ecg_check'])
       if 'muscle artifact' in classes:
           muscle_idx, muscle_scores = ica.find_bads_muscle(raw_for_ica, **approved_ica_params['muscle_check'])
   ```
   When corroboration is required, match it by class: EOG evidence for eye labels,
   ECG for heart, the approved muscle check for muscle. An ECG hit cannot
   corroborate an eye label. Other classes need an explicitly approved source;
   absent evidence remains unavailable. Record actual detector settings and
   results. The requirement itself is a researcher-approved policy, not a new
   default imposed by this example.
6. **Determine components to exclude**:
   ```python
   from pathlib import Path
   import runpy
   choose = runpy.run_path(str(Path(AEA_ROOT) / "skills/eeg-ica/scripts/selection.py"))["choose_components"]
   selection = choose(ic_labels['labels'], ic_labels['y_pred_proba'],
       **approved_ica_params['rejection_policy'],
       corroborating_components={'eye blink': eog_idx, 'eye movement': eog_idx,
                                 'heart beat': ecg_idx, 'muscle artifact': muscle_idx})
   exclude = selection['excluded']
   ambiguous = selection['ambiguous']
   ica.exclude = exclude
   ```
   This helper consumes saved labels/probabilities only. It never fits ICA or
   decides the scientific threshold. `brain` and `other` are not auto-rejected;
   `other` remains flagged for review. Every decision has a reason. An empty
   corroborating list means a performed check found no match; `None` means the
   check was unavailable. Handle ambiguous components under the approved policy.
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
       'threshold': approved_ica_params['rejection_policy']['probability_threshold'],
       'rejection_policy': approved_ica_params['rejection_policy'],
       'selection_decisions': selection['decisions'],
       'method': METHOD,
       'n_components_fitted': ica.n_components_,
   }
   with open(f'ica-stage/{sub}/ica_labels.json', 'w') as f:
       json.dump(label_info, f, indent=2)
   ```

## Phase D — Manual review handling

If a subject is in the approved `MANUAL_REVIEW` list or has ambiguous components
(low probability, missing/negative corroboration, or an unclassified component),
record the reason and use `approved_ica_params['ambiguous_action']`:

- `await_review`: prepare the review materials below, leave the subject pending
  and continue independent approved subjects.
- `keep_flagged`: retain those components, apply only confirmed exclusions and
  record that the flagged components were not manually reviewed. This is allowed
  only when the approved plan specifies it, not because a user is absent.

If the handling is unresolved, record that decision and continue independent
authorized work. Neither a timeout nor missing evidence authorizes removal.

1. **Generate topomap report**:
   ```python
   fig = ica.plot_components(picks=ambiguous + exclude, show=False)
   fig.savefig(f'ica-stage/{sub}/{sub}_component_topos.pdf')
   # Also generate time-series view
   fig2 = ica.plot_sources(raw, picks=ambiguous, show=False)
   fig2.savefig(f'ica-stage/{sub}/{sub}_component_sources.pdf')
   ```
2. **Write review request** to `ica-stage/{sub}/MANUAL_REVIEW_NEEDED.md` listing ambiguous components with their top-2 ICLabel classes and probabilities.
3. For `await_review`, stop processing that subject and continue others. After review, apply the approved exclusion list to the saved decomposition. For approved `keep_flagged`, preserve the pending-review record while continuing without deleting the ambiguous components.

## Phase E — Apply ICA and write outputs

For each subject (after exclusion is finalized):

1. **Apply ICA rejection** to the ORIGINAL data (not the 1 Hz filtered copy):
   ```python
   ica = mne.preprocessing.read_ica(f'ica-stage/{sub}/{sub}_ica.fif')
   if approved_ica_params['fit_domain'] == 'continuous':
       raw = mne.io.read_raw_fif(approved_ica_params['analysis_input'], preload=True)
   elif approved_ica_params['fit_domain'] == 'epochs':
       raw = mne.read_epochs(approved_ica_params['analysis_input'], preload=True)
   else:
       raise ValueError('Resolve the ICA fitting domain before applying it')
   # Verify the approved channel/reference state matches the fitted solution;
   # only the planned analysis-vs-fitting filter difference is assumed here.
   ica.apply(raw)  # modifies raw in-place
   if approved_ica_params['fit_domain'] == 'continuous':
       raw.save(f'ica-stage/{sub}/{sub}_cleaned_raw.fif', overwrite=True)
   else:
       raw.save(f'ica-stage/{sub}/{sub}-clean-epo.fif', overwrite=True)
   ```
   Record the actual fit/apply inputs and output path. Epoch-first outputs
   retain their event identities and return to `eeg-epoch` for the approved
   final baseline/rejection/counting steps, not for another event extraction.
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

- [ ] Every subject selected for ICA has its approved Raw/Epochs input and a corresponding output or documented pending/failure state.
- [ ] Every subject has `ica_labels.json` and `*_ica.fif` (or `.set`).
- [ ] Every subject without review pending has the recorded cleaned Raw or Epochs output for the approved domain.
- [ ] No `"brain"` component was excluded (ICLabel brain class must never be auto-rejected).
- [ ] No `"other"` component was excluded (ambiguous class must go to manual review, not auto-reject).
- [ ] ICA was fit on the 1 Hz HP-filtered copy, not on the analysis bandpass data.
- [ ] ICLabel received the actual fitting instance with unchanged channels/reference; actual input conditions and any deviations from its documented design are reported under the approved labeling policy.
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
| Decomposition dominated by a few huge components / unstable | Inspect the actual fitting data, approved bad segments, channels and reference. Record measured rank and the approved dimensionality rule; do not subtract interpolation twice or change the fit/exclusions silently. |
| Irregular / short ISI and poor decomposition | Inspect the actual fitting data and approved domain. Propose a different fitting domain if supported; do not switch based on ISI alone. |
| Too many trials rejected before ICA | Compare the actual thresholds and stage with the plan, including peak-to-peak versus signed amplitude units. Correct implementation mismatches; any new rejection policy requires approval. |
| Fit, labeling or application reference differs from the approved configuration | Compare actual channel/reference/projection states with the plan. Average reference before fitting is not itself a failure; a pending projector is not an applied reference. Do not silently re-reference a labeling copy or refit a saved decomposition. Resolve any needed change with the researcher. |
