---
name: eeg-preprocess
description: "Filter, re-reference, detect bad channels, remove line noise on raw EEG. Reads DATASET_BRIEF.md to set defaults, ENVIRONMENT.json to verify MNE-Python. Writes per-subject preprocessed .fif under preprocess-stage/. Use when the user says \"预处理 EEG\", \"preprocess my EEG data\", \"clean the raw EEG\", or starts a new study from raw recordings."
argument-hint: "[project-dir] [— subjects: sub-01,sub-02,...]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-preprocess: Raw → preprocessed EEG

Canonical sample skill for AEA. Mirrors ARIS skill structure: Constants → Inputs → Phases → Output → Errors.

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **OUTPUT_DIR = `preprocess-stage/`** — relative to project root. Create if missing.
- **DEFAULT_BANDPASS = `[0.1, 40.0]` Hz** — overridden by `DATASET_BRIEF.md > Preprocessing decisions > Bandpass`.
- **DEFAULT_NOTCH = inferred from country** — Japan/EU = 50 Hz, US = 60 Hz. Always confirmed against `DATASET_BRIEF.md > Notch`.
- **DEFAULT_REFERENCE = `average`** — overridden by `DATASET_BRIEF.md > Re-reference scheme`.
- **DEFAULT_BAD_CHAN_RULE = `ransac`** (via pyprep). Falls back to manual list if pyprep missing.
- **RESAMPLE_TO = `null`** — no resampling unless DATASET_BRIEF requests it (recommend ≥250 Hz for ERP, ≥500 Hz for high-freq).
- **N_JOBS = `4`** — parallelism for filtering. Lower if memory-constrained.

## Required inputs

Before running, the following must exist in the project directory:

1. `DATASET_BRIEF.md` — auto-generated via `tools/auto_brief.py` or manually filled. Critical `[USER]` fields (paradigm, conditions) must be resolved. Non-critical fields with defaults (bandpass, reference) can proceed with defaults — note in the preprocess plan.
2. `ENVIRONMENT.json` — produced by `tools/env/check_env.{sh,ps1}`. Run the probe if missing.
3. `raw/` — directory with subject files (`.bdf`/`.set`/`.edf`/`.fif`/`.vhdr`).

## Phase A — Plan

Before touching data, write `preprocess-stage/PREPROCESS_PLAN.json` summarizing:

```json
{
  "backend": "mne",                     // MNE-Python
  "bandpass": [0.1, 40.0],
  "notch_freqs": [50],
  "reference": "average",
  "bad_channel_detection": "ransac",
  "resample_sfreq": null,
  "n_jobs": 4,
  "subjects": ["sub-01", "sub-02", ...],
  "raw_format": ".bdf",
  "seed": 42                            // copied from ANALYSIS_PLAN if it exists
}
```

If the user provided overrides via the skill argument (`— bandpass: 0.5,30`), apply them here. Print the plan and **wait for user confirmation** (or auto-proceed if `AUTO_PROCEED=true` was set in ARGUMENTS).

## Phase B — Backend resolution

Do **not** decide this by hand. Run the resolver — it reads `ENVIRONMENT.json` and
`tools/env/backends.json`, picks a backend, and writes the record the audit skill reads:

```bash
python tools/env/resolve_backend.py \
  --capability erp.preprocess_average \
  --env ENVIRONMENT.json \
  --out preprocess-stage/BACKEND_RESOLUTION.md
```

`mne` is the default and the reference backend — every committed certified value was produced by
it. `eeglab` and `fieldtrip` are selectable alternatives, validated on all five certified ERP CORE
components ([CROSS_TOOLBOX_EVAL.md](../../tools/benchmark/CROSS_TOOLBOX_EVAL.md): 10/10 runs
reproduce the group conclusion). Pass `--prefer eeglab` / `--prefer fieldtrip` when the user asks
for one, or when MNE is unavailable.

Three rules the resolver enforces, all of them earned from measurement rather than assumed:

1. **It fails loudly rather than degrading.** No backend available → non-zero exit with the install
   hint. Do not work around this; surface it.
2. **It refuses to switch silently away from a certified reference.** When you are reproducing a
   recipe's certified numbers, pass `--certified-reference mne`. Resolving to any other backend then
   fails unless the user explicitly accepts `--allow-uncertified`, and the report states that the
   result is no longer digit-comparable.
3. **It never claims unmeasured equivalence.** Where no benchmark exists (e.g. `ica.label` on
   EEGLAB), the report says "not measured" and you must not describe the outputs as interchangeable.

### If the resolved backend is not `mne`

**Emit the pinned template, never ad-hoc code.** Start from
`templates/backends/erp_preprocess_eeglab.m` or `erp_preprocess_fieldtrip.m` and fill only the
`SPEC` block.

This matters more than it looks. Cross-toolbox agreement is a property of how completely the
specification is pinned, **not** of the toolbox: at each toolbox's own defaults, per-subject
amplitudes differed from the reference by up to 43% of the group effect; with the specification
pinned, FieldTrip matched the reference within 0.1 µV on all 74 subject-component comparisons without trial rejection (per-component maxima 0.050–0.099 µV; MMN, which has trial rejection, 0.184 µV), while EEGLAB at its own defaults matched on 68 of 74 (N170 0.161 µV, ERN 0.210 µV; not pinned further).
The four conventions the templates force you to state — filter cutoff convention, transition width,
rejection criterion, resampling algorithm — are the ones that matter: the first three were measured to move the numbers (cutoff convention 0.80 → 0.05 µV on the FieldTrip P3b at fixed transition width; rejection criterion 0.089 → 0.040 µV mean |Δ| on MMN), while the contribution of the resampling algorithm was not isolated (the three arms use three different resamplers and agree within 0.1 µV once the filter is pinned).

Copy the `pin` section of `BACKEND_RESOLUTION.md` into `PREPROCESS_PLAN.json` so the choices reach
`eeg-methods-text` and `eeg-audit`.

## Phase C — Per-subject execution

For each `sub-XX` in `PREPROCESS_PLAN.json.subjects`:

Write and execute a preprocessing script following the canonical order (Robbins et al. 2020): **filter → bad channel detection → interpolation → re-reference → (optional resample)**. This order matters because filtering before bad channel detection prevents spectral artifacts from corrupting RANSAC correlation estimates, and interpolation must precede re-referencing so that bad channels do not contaminate the average reference.

### Canonical step order (full ERP pipeline checklist)

When the study epochs into ERPs and runs ICA, the **continuous-data steps in this skill are only the first half** of a longer canonical sequence that spans `eeg-preprocess` → `eeg-ica` → `eeg-epoch`. The full taught order (distilled from a teaching EEGLAB command history and the accompanying lab Q&A, see Domain Knowledge → "End-to-end canonical order") is:

1. ☐ **Import** raw recording (`mne.io.read_raw_*`, `preload=True`).
2. ☐ **Set montage / channel locations** (`raw.set_montage(...)`) — needed for interpolation, ICLabel, and average reference.
3. ☐ **Drop / re-type non-scalp refs** — set EOG/VEOG/HEOG/ECG/mastoid channel *types* (`raw.set_channel_types({...})`) or drop them; do an initial **manual bad-channel** pass from `DATASET_BRIEF.md` here.
4. ☐ **Filter** — high-pass (default 0.1 Hz), low-pass (default 40 Hz), **then notch** (always; see rule below). This stage.
5. ☐ **Resample** — only *after* filtering (`raw.resample(...)`). This stage.
6. ☐ **Epoch + baseline** — `mne.Epochs(...)`, `baseline=(None, 0)`. (`eeg-epoch` stage.)
7. ☐ **At the epoch stage**: interpolate remaining bad channels + reject bad epochs (loose amplitude pass, `reject_by_annotation=True`). (`eeg-epoch` stage.)
8. ☐ **ICA** — extended Infomax, fit on a 1 Hz HP copy. (`eeg-ica` stage.)
9. ☐ **Remove artifact ICs** — eye/muscle/heart/line/channel-noise. (`eeg-ica` stage.)
10. ☐ **POST-ICA amplitude sweep** — run a peak-to-peak reject at ±100 µV, then tighten to ~±60 µV for clean data. (`eeg-epoch` stage, AFTER ICA.)
11. ☐ **RE-REFERENCE LAST** — e.g. linked mastoids `raw.set_eeg_reference(['M1', 'M2'])` or average. **Never before ICA.**
    - **Reference choices**, roughly: *average* (default for ≥32 ch; needs whole-head coverage), *linked mastoids* (ERP convention, but can attenuate temporally-distributed effects), *CSD / surface Laplacian* (reference-free, sharpens local sources — see Domain Knowledge), and **REST** (Reference Electrode Standardization Technique): approximates a reference at infinity by projecting through a head model, reducing the reference's distortion of topography/connectivity (Yao 2001, *Physiol Meas* 22:693–711; available via `mne` lead-field projection or the `pyrest`/`eeglab` implementations). Report whichever you use — PSD, connectivity, and microstate results are all reference-dependent.

The continuous re-reference inside this skill's per-subject script (step 6 below) is for studies that do **not** run ICA, or where you deliberately apply an average reference as a `projection=True` projector to preserve rank for a later ICA. When the pipeline includes ICA, defer the final substantive re-reference (e.g. linked mastoids) to after artifact-IC removal — see Critical Rules and Domain Knowledge → "Re-reference last".

### MNE-Python path (default)

The script must:

1. **Load raw**: `mne.io.read_raw_*` — auto-detect format from extension (`.bdf`→`read_raw_bdf`, `.edf`→`read_raw_edf`, `.set`→`read_raw_eeglab`, `.fif`→`read_raw_fif`, `.vhdr`→`read_raw_brainvision`). Always load with `preload=True` for filtering.
2. **Bandpass filter**: `raw.filter(l_freq, h_freq, n_jobs=N_JOBS)`.
   - MNE defaults to FIR (zero-phase, windowed sinc) which is appropriate for most ERP/TFR work (Widmann et al. 2015).
   - For fine control: `raw.filter(l_freq, h_freq, method='fir', fir_design='firwin', phase='zero', fir_window='hamming')`.
   - Override `filter_length` only when MNE's auto-length exceeds the data duration (short recordings); prefer the default `'auto'` which sets length = 3.3x the reciprocal of the transition bandwidth.
   - For ICA-prerequisite runs, use `l_freq=1.0` for stable ICA decomposition, and apply the study's actual highpass later on the ICA-cleaned data.
3. **Notch filter / line noise removal**:
   - **Always apply the notch, even when the low-pass is below the line frequency.** The taught rule is to notch unconditionally: a 40 Hz LP does *not* guarantee 50/60 Hz is gone (FIR transition band leaks, and harmonics or filter ringing can re-introduce it), and skipping it is a frequent source of a residual line peak in the PSD. The notch is cheap insurance — run it after the band-pass.
   - Default: `raw.notch_filter(notch_freqs)` for simple spectral notch.
   - Preferred when available: `mne.preprocessing.EOGRegression` is not suitable; instead use spectral interpolation approaches. If `meegkit` is installed, use ZapLine (`meegkit.dss.dss_line`) which removes line noise without spectral notch artifacts. Log which method was used.
4. **Bad channel detection**: `pyprep.NoisyChannels(raw)` with `.find_all_bads()` which runs RANSAC (Bigdely-Shamlo et al. 2015). Mark via `raw.info['bads']`.
   - If pyprep is unavailable, fall back to manual list from `DATASET_BRIEF.md`.
   - If RANSAC marks >50% of channels, stop (likely wrong reference or montage).
5. **Interpolate**: `raw.interpolate_bads(reset_bads=True)` using spherical spline interpolation. **Record `n_interpolated = len(raw.info['bads'])` into `preprocess_summary.json` before the reset** — each interpolated channel costs one rank, which the downstream ICA must subtract from `n_components` (see Domain Knowledge → "Rank after interpolation and reference"). Interpolating bad channels before ICA without reducing the ICA rank produces ghost/duplicate components.
6. **Re-reference**: `raw.set_eeg_reference(reference)`.
   - **Before an `average` reference, exclude non-scalp channels** (EOG/ECG/EMG/mastoid). Set their types correctly first (`raw.set_channel_types({'HEOG': 'eog', ...})`) or drop them — otherwise they contaminate the average and leak ocular/cardiac signal into every scalp channel. `set_eeg_reference('average')` already ignores non-`eeg` channels, so the fix is to *type* them, not necessarily delete them.
   - **Average reference costs 1 rank.** Record `avg_ref_applied: true` in `preprocess_summary.json` so the downstream ICA subtracts this rank (see Domain Knowledge → "Rank after interpolation and reference"). To preserve full rank for a later ICA, apply it as a projector instead: `raw.set_eeg_reference('average', projection=True)`.
   - For robust average reference (Bigdely-Shamlo et al. 2015), run the full PREP pipeline: `pyprep.PrepPipeline(raw, prep_params, montage)` which iteratively detects bad channels and re-references.
   - For mastoid or linked-mastoid reference: `raw.set_eeg_reference(['M1', 'M2'])` — verify channel names exist.
   - For REST (reference electrode standardization technique): `raw.set_eeg_reference('REST')` (requires MNE >= 1.1 and a forward model).
7. **Resample** (if configured): `raw.resample(resample_sfreq)`. Anti-aliasing is handled automatically by MNE. Two hard rules: (a) **always filter the continuous data before resampling (downsample only AFTER filtering)** — resampling unfiltered data aliases line noise and high-frequency content into the passband; (b) **resample the continuous `Raw`, never `Epochs`** — `epochs.resample()` jitters event timing relative to the epoch t=0 and can shift apparent peak latencies. If you must downsample, do it here on `Raw` before epoching, and **after** all filtering (band-pass + notch) to avoid filter edge effects at lower sample rates. Recommend ≥250 Hz for ERP, ≥500 Hz for analyses needing >40 Hz content.
8. **Save**: `preprocess-stage/<sub>/<sub>_preprocessed_raw.fif`.
9. **Write summaries**:
   - `preprocess-stage/<sub>/preprocess_summary.json` — all parameters actually used (filter freqs, filter design, detected bads, reference, sfreq_out, backend versions, line noise method).
   - `preprocess-stage/<sub>/config.json` — the config that was used.

### Bad channels vs bad segments (the "sandwich" order)

A persistently dead/noisy *channel* and a transient all-channel *time segment* are handled by different mechanisms, and the ordering matters:

1. **Channels first**: identify and interpolate consistently-bad channels (`raw.info['bads']` → `raw.interpolate_bads`). Doing this first prevents a single globally-bad channel from falsely flagging many time segments.
2. **Segments second**: after channels are clean, mark transient artifacts that affect *all* channels and cannot be corrected by interpolation or ICA — head movement, large muscle bursts, electrode pops. Use `mne.preprocessing.annotate_amplitude(raw, peak=<V>, flat=...)` or hand-built `mne.Annotations` labelled `'bad_*'`; at epoching set `reject_by_annotation=True` to drop them.

Decision rule: persistently bad single channel → `interpolate_bads` (spherical). Transient all-channel excursion (movement, swallow) → annotate as `'bad'` and exclude the segment — do **not** try to ICA it out. This continuous-data screening is best done before ICA so the ICA decomposition is not dominated by a few huge non-stationary excursions.

**Artifact Subspace Reconstruction (ASR) — the missing middle option (optional).** Between "interpolate a dead channel" and "delete a contaminated segment" there is a third move this skill otherwise lacks: *reconstructing* high-variance transients while keeping the segment. ASR (Chang et al. 2018) learns a clean-data covariance on an artifact-free calibration window, then for each sliding window flags principal subspace directions whose variance exceeds a cutoff `k` (in SD units) and reconstructs them from the retained subspace. Implement via `meegkit.asr` (the same `meegkit` already used here for ZapLine), and place it **after the high-pass filter and before ICA**. Encodable rules: (a) high-pass *first* — an inadequate high-pass makes ASR over-correct, which in turn balloons the downstream `annotate_amplitude` window-rejection count; (b) calibrate on an explicitly clean baseline window, because ASR *cannot* remove an artifact that is also present in its own calibration data; (c) keep the cutoff in `k = 10–100` SD — below ~10 it starts deleting genuine high-amplitude neural activity. For mobile or low-channel montages prefer Riemannian ASR (rASR, Blum et al. 2019): better VEP specificity at roughly one-third the compute. ASR complements, and does not replace, the channel-interpolation / segment-rejection sandwich above.
- Cite: Chang, C.-Y., Hsu, S.-H., Pion-Tonachini, L., & Jung, T.-P. (2018). Evaluation of artifact subspace reconstruction for automatic EEG artifact removal. IEEE EMBC, 1242–1245; Blum, S., et al. (2019). A Riemannian modification of artifact subspace reconstruction for EEG artifact handling. Frontiers in Human Neuroscience, 13, 141; Jacobsen, N. S. J., et al. (2021). A walk in the park? EJN, 54, 8421 (calibration caveat).

### Re-filtering after baseline correction

If you re-filter data that has *already been epoched and baseline-corrected* (e.g. you decide to tighten the low-pass on existing epochs), the filter operation reshapes the whole epoch including the baseline window, so the previously-applied baseline no longer holds. **Re-run baseline correction after any re-filter of baselined epochs** (`epochs.apply_baseline((None, 0))`). The clean way to avoid this entirely is to finalize all filtering on the continuous `Raw` *before* epoching (canonical step order above) — only re-filter epochs when you genuinely cannot re-derive them from `Raw`, and re-baseline immediately when you do.

### Output per subject

Each subject produces:
- `preprocess-stage/<sub>/<sub>_preprocessed_raw.fif` (or `.set` for EEGLAB) — the preprocessed continuous EEG.
- `preprocess-stage/<sub>/preprocess_summary.json` — what was actually done (filter freqs, filter design, detected bads, reference, line noise method).
- `preprocess-stage/<sub>/config.json` — the config that was used.

If a subject fails (file unreadable, filter divergence, etc.), do **not** stop the batch. Record the failure in `preprocess-stage/<sub>/error.json` and continue. At the end, report the full success/failure list.

## Phase D — Aggregate summary

After all subjects processed, write `preprocess-stage/PREPROCESS_REPORT.md`:

```markdown
# Preprocess report

- Backend resolved: mne
- Subjects in: N=<X>, out: N=<Y>, failed: N=<Z>
- Mean bad channels per subject: <m> (range <a>–<b>)
- Bandpass applied: <l>–<h> Hz
- Notch: <freqs>
- Reference: <…>
- Resample: <…>
- Failed subjects:
  | Subject | Reason |
  |---|---|
  | sub-XX | <error> |
- Artifact path: preprocess-stage/
```

Also append a block to `FINDINGS.md` with the headline numbers.

## Phase E — Sanity checks before signaling success

The following must all be true. If any fails, the skill is **not** complete:

1. ☐ Every successful subject has `*_preprocessed_raw.fif` AND `preprocess_summary.json` on disk.
2. ☐ `BACKEND_RESOLUTION.md` exists.
3. ☐ `PREPROCESS_REPORT.md` exists and lists all subjects (even failed ones).
4. ☐ `FINDINGS.md` has a new dated entry referencing this stage.
5. ☐ For each subject, `preprocess_summary.json.sfreq_out` matches the planned `resample_sfreq` (if set) or the input sfreq (if not).

## Error handling

| Symptom | Action |
|---|---|
| `DATASET_BRIEF.md` has `<…>` placeholders | Stop. Ask the user to fill them. |
| `ENVIRONMENT.json` missing | Run `tools/env/check_env.sh` (or `.ps1` on Windows). |
| MNE-Python unavailable | Stop. Output an actionable install instruction in `BACKEND_RESOLUTION.md`. |
| Subject file not readable | Skip subject, log to `error.json`, continue batch. |
| RANSAC marks >50% of channels bad | Almost certainly a bad reference electrode or wrong montage — stop, ask user to verify. |
| Filter eats all data (NaN output) | Check the bandpass against the sfreq (Nyquist). Stop and report. |
| Residual 50/60 Hz peak in PSD despite a 40 Hz low-pass | The notch was skipped or under-specified. Always run `raw.notch_filter()` (even when LP < line freq) and include harmonics. Re-run the line-noise step. |
| Re-reference applied before ICA in the planned pipeline | Wrong order. Re-reference LAST (after artifact-IC removal). For rank-preservation before ICA, apply average reference as `projection=True` instead of a hard re-reference. Re-do from the pre-reference data. |
| Re-filtered epochs but baseline now looks shifted | Re-filtering reshaped the baseline window. Re-run `epochs.apply_baseline((None, 0))` after the re-filter, or re-derive epochs from the continuous `Raw`. |
| Downsampled, then a line/HF peak aliased into the band | Resample was done before filtering. Order is filter (band-pass + notch) → resample. Re-do from the unresampled `Raw`. |

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
- In MNE, compute the rank explicitly rather than guessing: `mne.compute_rank(raw, rank='info')` returns the effective rank from the data/info; pass that integer to `ICA(n_components=...)`. Over-specifying `n_components` on rank-deficient data produces ghost/duplicate components and an unstable decomposition.
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
- **Re-reference last, never before ICA.** The reference is a linear operation on the channels; applying it before ICA changes the mixing matrix the decomposition has to model and bakes the (possibly suboptimal) reference into every component. Run ICA on the pre-reference montage, remove artifact ICs, *then* set the substantive reference (linked mastoids or average). If you need an average reference for rank reasons before ICA, add it as a `projection=True` projector (preserves rank, deferrable) rather than a hard re-reference.
- **Two-stage amplitude rejection straddles ICA.** A *loose* peak-to-peak pass before ICA only removes the few extreme non-stationary segments that would otherwise dominate the decomposition; the *tight* pass (run at ±100 µV, then tighten toward ~±60 µV for clean recordings) is applied AFTER ICA has corrected the stereotyped artifacts, so it does not throw away trials that ICA could have salvaged.
- **Re-baseline after any re-filter of baselined epochs.** Filtering reshapes the baseline window, invalidating the prior baseline correction; re-run `apply_baseline` (or, preferably, finalize filtering on continuous `Raw` before epoching).
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd ed. (recommended processing order). MIT Press. See also Bigdely-Shamlo et al. (2015) and the SCCN "Makoto's preprocessing pipeline" (Miyakoshi, UCSD SCCN wiki) for the ICA-placement and rank conventions.

### Why preprocessing order matters (Robbins et al. 2020, Frontiers in Neuroinformatics)

- The canonical order is: **filter → bad channel detection → interpolation → re-reference → (optional: ICA → epoch)**.
- **Filter before bad channel detection**: unfiltered data contains slow drifts and line noise that inflate variance-based and correlation-based bad channel metrics, causing false positives.
- **Interpolate before re-referencing**: if bad channels are included in the average reference, they bias the reference and distort all channels. Interpolate first (or use robust average reference which handles this iteratively).
- **Re-reference before ICA** (in the next stage): ICA decomposition is sensitive to the reference; average reference provides a full-rank data matrix after removing one channel from the rank (use `raw.set_eeg_reference(projection=True)` to maintain rank for ICA).
- **Resample last**: avoids aliasing artifacts from interacting with filter edge effects.
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

## Critical Rules

- **Never** change the preprocessing order without justification. Filter → detect bads → interpolate → re-reference is the canonical order (Robbins et al. 2020).
- **Never** use a highpass >0.1 Hz for the final ERP data without documenting the rationale (risk of filter artifacts in baseline, Tanner et al. 2015).
- **Never** use causal (single-pass) filters for offline analysis — they introduce phase distortion and asymmetric temporal smearing.
- **Never** apply ICA in this stage — ICA belongs in `eeg-ica`. This stage only prepares data for ICA (1 Hz highpass copy if needed).
- **Never** skip line noise removal and assume the lowpass will handle it — harmonics and spectral leakage can persist.
- **Never** use a lowpass below 20 Hz for ERP data — it distorts component morphology.
- **Never** include EOG/ECG/EMG/mastoid channels in an `average` reference — set their channel types (or drop them) first, or they leak into every scalp channel.
- **Never** resample `Epochs` to fix sample rate — resample the continuous `Raw` before epoching; epoch-level resampling jitters event timing and shifts peak latencies. And never resample before filtering (aliasing).
- **Never** hand `n_components` to the downstream ICA without subtracting interpolated channels and (if applied) the average-reference rank — record `n_interpolated` and `avg_ref_applied` so `eeg-ica` can use `mne.compute_rank()`.
- **Never** try to ICA out a transient all-channel excursion (head movement, swallow) — annotate it `'bad'` and reject the segment; ICA is for spatially-stationary sources (blinks, EOG, cardiac, EMG elsewhere).
- **Never** apply the substantive re-reference before ICA — **re-reference LAST**, after artifact-IC removal (e.g. linked mastoids). The reference is a linear channel operation that changes the ICA mixing matrix; baking it in before ICA degrades the decomposition. If you need an average reference before ICA for rank reasons, add it as a `projection=True` projector, not a hard re-reference.
- **Never** skip the notch even when the low-pass is below the line frequency — the LP transition band/ringing and harmonics can leave a residual 50/60 Hz peak; always run `notch_filter()` after the band-pass.
- **Never** resample before filtering — downsample only AFTER the band-pass + notch, or line noise and high-frequency content alias into the passband.
- **Never** re-filter already-baselined epochs without re-running baseline correction — filtering reshapes the baseline window and invalidates the prior correction (prefer finalizing all filtering on continuous `Raw` before epoching).

## Cross-references

- Inputs: `DATASET_BRIEF.md`, `ENVIRONMENT.json`, `ANALYSIS_PLAN.md` (for seed)
- Next stage: `eeg-ica` reads `preprocess-stage/<sub>/<sub>_preprocessed_raw.fif` and **uses `n_interpolated` + `avg_ref_applied` from `preprocess_summary.json` to set `ICA(n_components=...)`** (fit on a 1 Hz-highpass copy, apply to the 0.1 Hz data).
- `eeg-epoch` consumes the `'bad_*'` annotations written here via `reject_by_annotation=True`; amplitude-based peak-to-peak rejection (~100 µV, tightened for clean data) is applied there, AFTER ICA.
- `eeg-connectivity` may apply `compute_current_source_density()` (this skill's optional CSD transform) before sensor-space FC to reduce volume conduction.
- Audit: `eeg-audit` checks that the bandpass and reference recorded in `preprocess_summary.json` match what `DATASET_BRIEF.md` declared.
