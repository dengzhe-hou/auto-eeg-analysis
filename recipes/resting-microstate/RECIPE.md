---
recipe: resting-microstate
version: "v0.1.1"
paradigm: Resting-state EEG microstate analysis (canonical maps A–D, temporal dynamics)
status: validated
min_channels: 20
min_sfreq: 250
min_duration_s: 120
required_markers: []          # continuous resting-state, NO per-trial markers
references:
  - "Michel, C. M., & Koenig, T. (2018). EEG microstates as a tool for studying the temporal dynamics of whole-brain neuronal networks: A review. NeuroImage, 180, 577–593. doi:10.1016/j.neuroimage.2017.11.062"
  - "Koenig, T., et al. (2002). Millisecond by millisecond, year by year: normative EEG microstates and developmental stages. NeuroImage, 16(1), 41–48."
  - "Pascual-Marqui, R. D., Michel, C. M., & Lehmann, D. (1995). Segmentation of brain electrical activity into microstates. IEEE Trans. Biomed. Eng., 42(7), 658–665."
  - "Khanna, A., Pascual-Leone, A., & Farzan, F. (2014). Reliability of resting-state microstate features in electroencephalography. PLoS ONE, 9(12), e114163."
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
distilled_from:
  - "MCKJ0914/part8_micro (EEGERP_microstates, microstate_notes + Theory/papers)"
  - "第八届启航班训练营/eight_qihangban/part8_micro; 16静息态EEG微状态分析直播间"
---

# Recipe: Resting-State EEG Microstates (A–D)

> Resting-state scalp EEG is not random: the topography of the instantaneous electric field stays quasi-stable for ~60–120 ms ("microstates"), then jumps to a new configuration. Four canonical maps (A, B, C, D) explain ~70% of the global variance across healthy adults. This recipe clusters the GFP-peak topographies into these maps, back-fits them to the continuous recording, and reports the four clinically used temporal parameters per map. It is the standard resting-state biomarker pipeline used in schizophrenia, dementia, and developmental studies.

This recipe produces **descriptive per-subject (and group) microstate parameters** — it is not a condition-contrast recipe. If you have two groups (e.g., patients vs controls) or two states (eyes-closed vs eyes-open), the parameter tables feed `eeg-stats` for a between-condition comparison.

## What this recipe needs

### Data shape

- **Channels:** ≥ 20 scalp channels (microstate maps need spatial coverage); 30–64 recommended. A montage with positions is required.
- **Sampling rate (after resampling):** ≥ 250 Hz.
- **Recording:** continuous resting-state, **≥ 120 s of clean data** per subject (Khanna 2014: reliability climbs steeply up to ~2 min; ≥ 5 min preferred). Eyes-closed and eyes-open should be analysed separately if both exist.
- **Markers:** none required. If the recording mixes eyes-open / eyes-closed blocks, provide the block boundaries (annotations) so they are not pooled.

### Subjects

- **N recommended:** ≥ 20 for stable **group-level global maps** and adequate between-group power.
- **Group structure:** single-group descriptive, **between-group**, or **within-subject state** (EC vs EO).

## Pipeline

### 1. Preprocess
- Bandpass: **2–20 Hz** (zero-phase FIR). *Microstate-specific* — broadband 1–40 Hz smears the GFP peaks; the 2–20 Hz band is the field convention (Michel & Koenig 2018).
- Notch: 50 / 60 Hz inferred from country.
- Reference: **average** of all scalp channels (mandatory — microstate topographies are reference-dependent).
- Bad channels: RANSAC (pyprep) → interpolate, then re-apply the average reference.

### 2. ICA
- Extended Infomax; auto-label via `mne-icalabel`; reject eye / muscle / heart / line / channel-noise components.

### 3. Segment (instead of epoch — continuous)
- No event epoching. Optionally `mne.make_fixed_length_epochs(raw, duration=2.0, overlap=0.0)` only for artifact screening; microstate fitting runs on the **GFP peaks of the continuous record**.
- Drop annotated bad segments.

### 4. Microstate fitting (`pycrostates`)

```python
from pycrostates.cluster import ModKMeans
from pycrostates.preprocessing import extract_gfp_peaks

gfp_peaks = extract_gfp_peaks(raw)            # cluster on GFP peaks only, not every sample
ModK = ModKMeans(n_clusters=4, random_state=42)
ModK.fit(gfp_peaks, n_jobs=1)                 # modified k-means; polarity-invariant
ModK.reorder_clusters(order=[...])            # align to canonical A,B,C,D after inspection
sf = raw.info['sfreq']
segmentation = ModK.predict(                  # back-fit to the CONTINUOUS raw
    raw, factor=10,
    half_window_size=round(0.030 * sf),       # 30 ms smoothing in PHYSICAL units (Poulsen 2018)
    min_segment_length=round(0.020 * sf),     # 20 ms — sfreq-INDEPENDENT (see note below)
    reject_by_annotation=True)
params = segmentation.compute_parameters()    # NOT pycrostates.metrics (does not exist)
```

> **Smoothing must be in physical units, not samples.** Earlier drafts used
> `half_window_size=8, min_segment_length=5` (sample counts), which are sampling-rate
> dependent: at 250 Hz they give ~32/20 ms, but on a 160 Hz recording the same counts mean
> 50/31 ms and inflate mean microstate durations to ~200 ms (validated: 160 Hz native →
> 200 ms vs the canonical ~100 ms). Deriving the windows from `sfreq` (30/20 ms) fixes this
> — on the eegbci validation at native 160 Hz the duration came to **116 ms** and split-half
> map reproducibility was **|r| = 0.87** ([recorded audit script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/audit_followups.py)).

- **Selecting K:** default K = 4 (canonical). If exploring, justify K by Global Explained Variance (GEV) elbow + cross-validation criterion across K = 3–7; report GEV.
- **Polarity invariance:** microstate clustering ignores map polarity — never interpret the sign of a map.
- **Group global maps (recommended, Khanna 2014):** two-stage — fit per subject, then cluster the per-subject maps into group maps, then back-fit group maps to every subject. Far more reliable (Cronbach α ≈ 0.81 vs 0.52 for per-recording maps).

### 5. Parameters reported (per map, per subject)

| Parameter | Meaning | Typical healthy-adult range (K=4, EC) |
|---|---|---|
| GEV | global variance the map explains | total ≈ 65–80% |
| Duration | mean dwell time (ms) | ~70–120 ms |
| Occurrence | appearances per second | ~3–6 /s |
| Coverage | fraction of total time | ~20–30% each |
| Transition probability | map→map, **base-rate corrected** | matrix (4×4) |

```python
from pycrostates.segmentation import compute_transition_matrix, compute_expected_transition_matrix
T_obs = compute_transition_matrix(segmentation)
T_exp = compute_expected_transition_matrix(segmentation)   # base-rate (Markov) expectation
# report T_obs and the (observed − expected) excess to remove coverage confounds
```

### 6. Statistics (only if a contrast exists)
- Feed per-subject parameter tables to `eeg-stats`. Between-group: independent test per parameter with **FDR across the 4 maps × 4 parameters**. EC vs EO: paired.
- Never run 16 uncorrected t-tests on the parameter grid.

### 7. Figures
- F1: the 4 topographic maps (A–D), polarity-free colormap.
- F2: per-map parameter bars (duration / occurrence / coverage) with ±1 SEM across subjects.
- F3: transition-probability matrix (observed − expected excess).

## Expected output (validation dataset)

On a clean ≥2-min eyes-closed adult recording the recipe should yield 4 maps explaining ~70% GEV, durations ~70–120 ms, and a roughly symmetric transition matrix with the well-known C↔D and A↔B preferences.

## Validated results (server, 2026-06-19)

**Dataset:** PhysioNet eegbci, **N = 20** subjects, eyes-closed (R02), 64 ch, K = 4, seed 42.
**Sanity check — 4 maps, ~70% GEV, durations in the 70–120 ms band: CONFIRMED.**

| Parameter | Value (N=20) | Field-expected |
|---|---|---|
| Total GEV (4 maps) | **0.662 ± 0.120** | ~65–80% |
| Mean microstate duration (median over maps/subjects) | **103 ms** (IQR 94–113) | ~70–120 ms |
| Maps | 4 (canonical K) | A–D |

Figure: [archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/resting_validation.png) (panel C). [Recorded validation script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/validate_resting_recipes.py) (20 subjects).

> **Validation caveats (honest):** eegbci is natively **160 Hz** and only **~61 s/run** — both **below** this recipe's `min_sfreq: 250` and the ≥120 s (ideally ≥2 min) Khanna-2014 reliability floor. Data were **resampled to 250 Hz** before fitting; at the native 160 Hz the sample-based smoothing params (`half_window_size=8`, `min_segment_length=5`) inflated durations to ~200 ms — a reminder that those params are sfreq-dependent and the recipe assumes ≥250 Hz. GEV (66%) sits at the low end of the 70% expectation, consistent with the short, upsampled segments. Per-subject (not group-template) maps were used.

## Methods paragraph (for your paper)

```text
[AUTO-GENERATED SKETCH — verify after run]
Resting EEG was band-pass filtered 2–20 Hz, average-referenced, and cleaned with
ICA (mne-icalabel). Microstate maps were derived by modified k-means (pycrostates,
K=4, seed 42) on GFP-peak topographies and back-fitted to the continuous recording
with temporal smoothing. For each subject and map we computed GEV, mean duration,
occurrence, coverage, and base-rate-corrected transition probabilities. Group maps
were obtained by a second-level clustering of per-subject maps.
```

## Known limitations
- K=4 is the convention but not a law; report GEV and justify any other K.
- Microstate parameters are sensitive to the reference (must be average) and to the GFP-peak vs all-sample fitting choice — record both.
- Short (<2 min) or <20-channel recordings give unreliable parameters (Khanna 2014).
- `pycrostates` must be installed; degrade explicitly if absent.

## Changelog
- **v0.1.0** (2026-06-18) — initial release; distilled from the 茗创科技 microstate course modules. Not yet server-validated.
