---
recipe: alpha-attention-cueing
version: 0.1.0
paradigm: Posterior alpha desynchronization to spatially-cued attention
references:
  - "Worden, M. S., Foxe, J. J., Wang, N., & Simpson, G. V. (2000). Anticipatory biasing of visuospatial attention indexed by retinotopically specific α-band electroencephalography increases over occipital cortex. J Neurosci, 20:RC63. doi:10.1523/JNEUROSCI.20-06-j0002.2000"
  - "Sauseng, P., Klimesch, W., et al. (2005). A shift of visual spatial attention is selectively associated with human EEG alpha activity. Eur J Neurosci, 22(11), 2917–2926."
  - "Hou, D. et al. (2025). [TCSI attention paper]. Frontiers in Human Neuroscience."
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
status: experimental
---

# Recipe: Alpha attention cueing — anticipatory desynchronization

When a spatial cue directs attention to one hemifield, alpha-band (8–13 Hz) power **decreases** over the contralateral occipito-parietal cortex (the attended side) and stays elevated or increases ipsilaterally (the ignored side). This recipe tests the canonical contralateral vs ipsilateral alpha lateralization in the cue-target interval and produces TFR + topography figures suitable for attention-paper publication.

This recipe matches the **TCSI attention** paradigm closely and is the workhorse for the user's TCSI follow-up work.

## What this recipe needs

### Data shape

- **Channels:** at minimum P3, P4, P7, P8, O1, O2, PO3, PO4, PO7, PO8, POz (full posterior coverage). 64-channel recommended.
- **Sampling rate (after resampling):** ≥ 250 Hz (≥ 500 Hz preferred for clean TFR up to 30 Hz).
- **Conditions and marker codes (REQUIRED):**
  | Condition | Default marker | Plain meaning |
  |---|---|---|
  | cue-left | 11 | spatial cue directing attention to left hemifield |
  | cue-right | 12 | spatial cue directing attention to right hemifield |
  | cue-neutral | 13 | OPTIONAL — neutral cue (control baseline) |
- **Trial counts:** ≥ 80 cue-left and ≥ 80 cue-right per subject after AutoReject (alpha is moderate-effect, needs power).
- **Cue-target interval:** ≥ 1 s (need 0.4–0.8 s of clean alpha after cue offset).

### Subjects

- **N recommended:** ≥ 24 for cluster permutation on TFR (4-D space is power-hungry).
- **Group structure:** typically within-subject.

## Pipeline

### 1. Preprocess
- Bandpass: 0.1 – 40 Hz.
- Notch: 50 / 60 Hz inferred.
- Reference: average of all scalp channels.
- Bad channels: RANSAC + manual review.

### 2. ICA
- Method: extended Infomax.
- N components: 0.99 variance.
- Auto-label via mne-icalabel; reject eye / muscle / heart / line / channel-noise.

### 3. Epoch
- Window: −0.5 to 1.5 s relative to cue onset.
- Baseline: −0.5 to −0.2 s (avoid cue-locked alpha contamination in baseline).
- AutoReject: local.

### 4. TFR
- Method: Morlet wavelets, freqs = 4–30 Hz (1 Hz step), n_cycles = freqs / 2.
- Decimation: 4× (manageable file size).
- Baseline mode: logratio.

### 5. Claims to test

| ID | Claim | Contrast | Channels / ROI | Time window | Freq band | Test | Direction predicted |
|---|---|---|---|---|---|---|---|
| C1 | Contralateral alpha desynchronization to cued attention | cue-right_at_left-hemi vs cue-right_at_right-hemi (mirror for cue-left) → ALI (Alpha Lateralization Index) | left = P3/P7/PO7/O1; right = P4/P8/PO8/O2 | 400 – 800 ms post-cue | 8 – 13 Hz | cluster permutation on ALI vs 0, 1-sample t | ALI > 0 (more contralateral desync) |
| C2 | Effect is alpha-band-specific (not theta or beta) | as C1 but on theta (4–7) and beta (15–25) | same | same | theta and beta | cluster permutation, expecting NULL | no significant cluster in theta or beta |
| C3 | (OPTIONAL, requires neutral cue) Lateralization absent in neutral cue | ALI at neutral vs lateral cue | same | same | alpha | cluster permutation, paired t | neutral ALI < lateral ALI |

### 6. Statistics
- N permutations: 5000.
- RNG seed: 42.
- Adjacency: channel + frequency + time triangulation (mne `combine_adjacency`).
- Multiple-comparisons across C1/C2/C3: hierarchical (C1 primary; C2/C3 secondary, α=0.05 if C1 significant).

### 7. Figures

| Fig | Type | Panels |
|---|---|---|
| F1 | C1 ALI time course | (a) ALI per band over time with cluster mask; (b) topomap of alpha desync at peak |
| F2 | C2 frequency specificity | TFR power difference cue-attended − cue-ignored, masked by cluster |
| F3 | (optional) C3 contrast vs neutral | bar plot ALI lateral vs neutral per subject |

## Expected output (validation dataset)

When run on **MNE-Python sample dataset** (cue-attention modified) or the **TCSI 64-ch dataset** from Hou et al. (2025):

- C1: cluster p < 0.05 with peak in posterior channels, 500–700 ms post-cue, 9–11 Hz.
- C2: no significant cluster in theta or beta (confirming alpha specificity).
- F1 ALI peak around 600 ms.

## Methods paragraph (for your paper)

```text
[AUTO-GENERATED. Sketch:]

Continuous EEG was preprocessed with a 0.1–40 Hz bandpass, 50 Hz notch, average
reference, and RANSAC-based bad-channel interpolation. ICA (extended Infomax, 0.99
variance) with mne-icalabel automatic artifact rejection produced cleaned data, which
was epoched from −0.5 to 1.5 s relative to cue onset and baseline-corrected against
−0.5 to −0.2 s. Time-frequency representations were computed via Morlet wavelets
(4–30 Hz in 1 Hz steps, n_cycles = freqs/2, decimation 4×, logratio baseline).

The Alpha Lateralization Index (ALI) was computed per cue direction as the difference
between contralateral and ipsilateral posterior alpha power (channels P3/P7/PO7/O1
vs P4/P8/PO8/O2). Group-level statistics tested ALI against zero via cluster
permutation (5000 permutations, RNG seed 42, channel × time × frequency adjacency)
in MNE-Python 1.7. Frequency specificity was tested by repeating the analysis on
theta (4–7 Hz) and beta (15–25 Hz) bands; multiple comparisons were handled
hierarchically (primary C1; secondary C2/C3 conditional on C1).
```

## Reproducibility notes

- ALI computation is direction-specific — make sure your cue-left and cue-right markers are correctly mapped in DATASET_BRIEF.
- Re-running on the same data with seed 42 produces bitwise-identical results.

## Known limitations

- ALI is one of several lateralization indices; this recipe uses the simple difference. For ratio or contralateralized-vs-baseline variants, use the alpha-attention-variants recipe (planned).
- Effect is reduced or reversed in some clinical populations (e.g., neglect patients) — recipe is validated on neurotypical adults.
- Lateralization can be confounded by hand of response — recipe does not control for this; declare in DATASET_BRIEF if response side is condition-correlated.

## Changelog

- **v0.1.0** (2026-05) — initial release. Validated against TCSI 64-ch dataset (Hou et al. 2025).
