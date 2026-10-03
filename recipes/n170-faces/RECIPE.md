---
recipe: n170-faces
version: "v0.1.0"
paradigm: N170 face selectivity — faces vs non-face control images, occipito-temporal negativity
status: validated
min_channels: 32
min_sfreq: 200
min_trials_per_condition: 30
required_markers: [stimulus/face, stimulus/non_face]
references:
  - "Bentin, S., Allison, T., Puce, A., Perez, E., & McCarthy, G. (1996). Electrophysiological studies of face perception in humans. Journal of Cognitive Neuroscience, 8(6), 551–565."
  - "Rossion, B., et al. (2000). The N170 occipito-temporal component is delayed and enhanced to inverted faces but not to inverted objects. NeuroReport, 11(1), 69–74."
  - "Wakeman, D. G., & Henson, R. N. (2015). A multi-subject, multi-modal human neuroimaging dataset. Scientific Data, 2, 150001."
validation_dataset: "OpenNeuro ds000117 (Wakeman & Henson 2015, EEG from the MEG .fif)"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
---

# Recipe: N170 Face Selectivity

> The N170 is a negative ERP component peaking ~130–200 ms at lateral occipito-temporal
> electrodes that is **larger (more negative) for faces than for non-face images**
> (objects, cars, or scrambled faces). It is the canonical electrophysiological index of
> face-specific perceptual processing (Bentin 1996) and inverts/delays for inverted faces
> (Rossion 2000). This recipe contrasts **faces vs scrambled faces** and confirms the
> face-selective N170 at the group level.

Sibling recipe: `n170-face-inversion` tests the upright-vs-inverted contrast (needs an
inversion dataset); this recipe tests the face-vs-non-face *selectivity* contrast.

## What this recipe needs

### Data shape
- **Channels:** ≥ 32 with lateral occipito-temporal coverage (the N170 is maximal at
  PO7/PO8/P7/P8-equivalent sites); positions required.
- **Sampling rate (after resampling):** ≥ 200 Hz.
- **Conditions / markers:** `face` (any face image) and `non_face` (scrambled / object / car
  control). ≥ 30 trials per condition per subject after rejection.

### Subjects
- **N recommended:** ≥ 12 for a group second-level cluster test.

## Pipeline

### 1. Preprocess
- Bandpass: 0.1–40 Hz zero-phase FIR.
- **Drop non-scalp channels** (HEOG/VEOG/ECG) BEFORE referencing — some datasets (e.g.
  ds000117) carry them as `EEG0xx` with positions, so a position check misses them; drop by
  extreme variance (>> scalp) or by the dataset's channel table, else they corrupt the
  average reference and ±reject kills every blink-adjacent trial.
- Reference: average of scalp channels.
- Bad channels: RANSAC → interpolate → re-reference.

### 2. ICA (recommended)
- Faces evoke blinks; for clean N170 use ICA + `mne-icalabel` to remove ocular components.
  This recipe validated WITHOUT ICA (on ds000117 with ±150 µV reject; the ERP CORE cross-tool benchmark used `reject=None`) — adding ICA
  retains more trials and is preferred for low-trial-count subjects.

### 3. Epoch
- −0.2 to 0.5 s; baseline −0.2 to 0 s; reject ±150 µV (scalp channels only).

### 4. Claims to test

| ID | Claim | Contrast | ROI | Window | Test | Direction |
|----|-------|----------|-----|--------|------|-----------|
| C1 | Faces elicit a larger N170 | face − non_face | lateral occipito-temporal | 130–200 ms | second-level spatiotemporal cluster perm, 1-sample, tail=−1 | face more negative |

### 5. Statistics
- Per subject: face and non-face averages → face − non-face difference wave.
- Group: **second-level** `spatio_temporal_cluster_1samp_test` (5000 perms, seed 42, one-sided
  negative) over the occipito-temporal channels × N170 window.

### 6. Figures
| Fig | Type | Panels |
|---|---|---|
| F1 | Group N170 | (a) grand-average face/non-face/difference at occipito-temporal ROI; (b) N170 topomap; (c) per-subject N170 amplitudes |

## Validated results (server, 2026-06-20)

**Dataset:** OpenNeuro **ds000117** (Wakeman & Henson 2015), EEG extracted from the Elekta
MEG `.fif`, **faces (Famous + Unfamiliar) − scrambled**, 70 scalp EEG → 250 Hz, average ref.

**Sanity check — faces elicit a larger (more negative) occipito-temporal N170 than scrambled, at the group level: CONFIRMED.**

| Quantity | Value (N = 16, run-01 only) |
|---|---|
| Grand-average N170 (face − scrambled, occipito-temporal, 130–200 ms) | **−0.641 µV** (SEM 0.251) |
| One-sample t (vs 0) | **t(15) = −2.56, p = 0.022**, Cohen's dz = −0.64 |
| **Second-level spatiotemporal cluster** (5000 perms, seed 42, one-sided) | **1 significant cluster, p = 0.029** |
| Direction | 11/16 subjects negative (faces more negative) |

A genuine population-level face-N170. The effect is **moderate** (dz ≈ 0.64), weaker than the
MMN/ERN — expected here because only **run-01 of 6** was used (~96 faces/subject), **no ICA**
(blink trials rejected, not corrected), an average reference, and a face-vs-*scrambled*
(not face-vs-object) contrast. Adding the other 5 runs and ICA would strengthen it; it already
passes the group sanity check on the canonical public face dataset.

The geometric posterior-lateral ROI is reported per run (transparent, not cherry-picked).
Figure: `tools/validation/figures/n170_faces.png`. Run: `python tools/validation/validate_n170_faces.py --subjects 16`.

### Second validation — ERP CORE N170 (server, 2026-06-24)

Re-validated on a **second public dataset** with the canonical face-vs-**car** control (a matched
non-face object, stronger than face-vs-scrambled): ERP CORE N170 (Kappenman 2021), **N = 20**,
face (value 1–40) − car (41–80), PO7/PO8/P7/P8, 130–200 ms, 0.1–40 Hz, 256 Hz, average ref, reject=None.

| Quantity | Value (N = 20) |
|---|---|
| Grand-average N170 (face − car, 130–200 ms) | **−1.181 µV** (SEM 0.265) |
| One-sample t (vs 0) | **t(19) = −4.45, p = 2.7 × 10⁻⁴**, Cohen's dz = −0.99 |
| Second-level spatiotemporal cluster | **1 significant cluster, p = 0.0002** |

Stronger than the ds000117 run-01 result (dz −0.99 vs −0.64) — the car control and full trial count
help. Run: `python tools/validation/validate_n170_erpcore_group.py --subjects 20`.
**Cross-tool benchmark:** reproduces MNE-BIDS-Pipeline's per-subject N170 to **≤ 11 nV (CCC = 1.000,
20/20 within ±0.1 µV)** — see [docs/BENCHMARK.md §4d](../../docs/BENCHMARK.md).

## Methods paragraph (for your paper)
```text
[AUTO-GENERATED SKETCH — verify after run]
EEG (0.1–40 Hz, average reference, non-scalp channels removed) was epoched −200 to 500 ms
around face and scrambled-face stimuli (baseline −200 to 0 ms, ±150 µV rejection). Per
subject, face and scrambled ERPs were averaged and a face-minus-scrambled difference wave
formed. The N170 face-selectivity effect was tested across subjects with a second-level
spatiotemporal cluster-permutation test (5000 permutations, seed 42, one-sided) at lateral
occipito-temporal channels, 130–200 ms.
```

## Known limitations
- The N170 scalp focus depends on the montage; the geometric ROI selects the most
  posterior-lateral electrodes, which approximates PO7/PO8 but is montage-dependent.
- Without ICA, blink-contaminated trials are rejected rather than corrected; low-trial-count
  subjects benefit from ICA.
- face vs scrambled is a face-selectivity contrast, not the face-inversion effect
  (see `n170-face-inversion`).

## Changelog
- **v0.1.0** (2026-06-20) — initial release; validated end-to-end on OpenNeuro ds000117 (group).
