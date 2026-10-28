## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **OUTPUT_DIR = `preprocess-stage/`** — relative to project root. Create if missing.
- **DEFAULT_BANDPASS = `[0.1, 40.0]` Hz** — overridden by `DATASET_BRIEF.md > Preprocessing decisions > Bandpass`.
- **DEFAULT_NOTCH = inferred from country** — Japan/EU = 50 Hz, US = 60 Hz. Always confirmed against `DATASET_BRIEF.md > Notch`.
- **DEFAULT_REFERENCE = `average`** — overridden by `DATASET_BRIEF.md > Re-reference scheme`.
- **DEFAULT_BAD_CHAN_RULE = `ransac`** (via pyprep). Falls back to manual list if pyprep missing.
- **RESAMPLE_TO = `null`** — no resampling unless DATASET_BRIEF requests it (recommend ≥250 Hz for ERP, ≥500 Hz for high-freq).
- **N_JOBS = `4`** — parallelism for filtering. Lower if memory-constrained.

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
components ([CROSS_TOOLBOX_EVAL.md](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md): 10/10 runs
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
   - Check the actual contributor set against documented channel identities and the approved set immediately before applying the reference. Use the bundled helper in [Channel identity and actual analysis picks](channel-identity.md); include its record in `preprocess_summary.json`. It fails if an ocular/auxiliary signal is still typed EEG instead of merely warning in prose. Do not infer identities from the reader's default channel types.
   - **Applied average reference reduces rank.** Record whether it was actually applied in `preprocess_summary.json`, together with the effective rank used for ICA. `raw.set_eeg_reference('average', projection=True)` adds a pending projector and leaves sample values unchanged until applied; do not record `avg_ref_applied: true` for that operation alone or subtract the same rank loss twice.
   - For robust average reference (Bigdely-Shamlo et al. 2015), run the full PREP pipeline: `pyprep.PrepPipeline(raw, prep_params, montage)` which iteratively detects bad channels and re-references.
   - For mastoid or linked-mastoid reference: `raw.set_eeg_reference(['M1', 'M2'])` — verify channel names exist.
   - For REST (reference electrode standardization technique): `raw.set_eeg_reference('REST')` (requires MNE >= 1.1 and a forward model).
7. **Resample only if planned at this stage.** MNE's `raw.resample` applies anti-alias filtering itself. Pass existing event samples with `raw, events = raw.resample(resample_sfreq, events=events)` and preserve trial identities and the original sampling rate; raw resampling reduces event-time precision. Follow the approved filtering order and record the actual output rate. A plan may instead use epoch-level resampling with sufficient padding, or continuous low-pass filtering followed by integer epoch decimation; `decimate` does not anti-alias. Do not move a planned downsampling step, choose a new rate or forbid epoch resampling categorically. See [MNE resampling guidance](https://mne.tools/stable/auto_tutorials/preprocessing/30_filtering_resampling.html#resampling).
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
6. ☐ For an average reference, the summary records the checked contributor names and the channel-identity source. The actual contributors match the approved set after the planned bad-channel handling, and no documented non-scalp signal remains in that set. A pending projector is recorded as pending; recheck its contributor set if picks/bads change before application.

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
| Reference state differs from the approved ICA fitting/application configuration | Preserve the mismatch and rebuild the affected step with the planned reference and effective rank. An approved average reference before ICA is supported; do not move it solely because another example references after ICA. |
| Re-filtered epochs but baseline now looks shifted | Re-filtering reshaped the baseline window. Re-run `epochs.apply_baseline((None, 0))` after the re-filter, or re-derive epochs from the continuous `Raw`. |
| Downsampled, then a line/HF peak aliased into the band | Inspect the actual method and filter transition band. MNE `resample` anti-aliases; unfiltered `decimate`/sample slicing does not. Preserve the failure and rebuild from the original signal with the approved anti-aliasing configuration. |
