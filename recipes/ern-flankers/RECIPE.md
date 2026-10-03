---
recipe: ern-flankers
version: "v0.1.0"
paradigm: Eriksen Flankers — Error-Related Negativity (ERN) + conflict N2 + frontal theta
status: validated
min_channels: 20
min_sfreq: 256
min_trials_per_condition: 40
required_markers: [stimulus/compatible, stimulus/incompatible, response]
references:
  - "Kappenman, E. S., et al. (2021). ERP CORE: An open resource for human event-related potential research. NeuroImage, 225, 117465. doi:10.1016/j.neuroimage.2020.117465"
  - "Gehring, W. J., et al. (1993). A neural system for error detection and compensation. Psychological Science, 4(6), 385–390."
  - "Cavanagh, J. F., & Frank, M. J. (2014). Frontal theta as a mechanism for cognitive control. Trends in Cognitive Sciences, 18(8), 414–421."
validation_dataset: "mne.datasets.erp_core (Subject-001, Task-Flankers)"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
---

# Recipe: ERN + Conflict N2 + Frontal Theta (Flankers)

The error-related negativity (ERN) is a negative-going ERP component peaking within 100 ms after an erroneous response at frontocentral sites (FCz/Cz). In the Eriksen Flankers task, incompatible trials (flankers point opposite direction to target) produce more errors and a larger ERN than compatible trials. Additionally, incompatible stimuli elicit a larger N2 (200–350 ms, stimulus-locked) and enhanced frontal theta power (4–8 Hz), both reflecting conflict monitoring.

This recipe tests three effects:
- **(C1)** Stimulus-locked N2: incompatible > compatible at FCz/Fz/Cz (200–350 ms)
- **(C2)** Response-locked ERN: incompatible > compatible at FCz/Fz/Cz (0–100 ms)
- **(C3)** Frontal theta power: incompatible > compatible at FCz/Fz/Cz (200–500 ms, 4–8 Hz)

## What this recipe needs

### Data shape

- **Channels:** at minimum FCz, Fz, Cz (10–20 system). 20+ channels recommended for topomaps.
- **Sampling rate (after resampling):** ≥ 256 Hz.
- **Conditions and marker codes (REQUIRED):**

  | Condition | Default event | Plain meaning |
  |---|---|---|
  | compatible_stim | stimulus/compatible/* | compatible flanker stimulus onset |
  | incompatible_stim | stimulus/incompatible/* | incompatible flanker stimulus onset |
  | response | response/* | button press (any) |

  The recipe derives response-locked epochs by finding the most recent stimulus before each response and labeling the response as compatible or incompatible.

- **Trial counts:** ≥ 40 per condition per subject after artifact rejection.

### Subjects

- **N recommended:** ≥ 15 for group-level cluster permutation. Single-subject trial-level analysis is supported but limited.
- **Group structure:** within-subject (every subject sees both compatible and incompatible).

## Pipeline

### 1. Preprocess
- Bandpass: 0.1–30 Hz, zero-phase FIR (30 Hz LP appropriate for ERN and N2).
- Notch: 60 Hz (US) or 50 Hz (EU/Asia) — infer from data or ask user.
- Reference: average of all scalp channels.
- Bad channels: RANSAC (pyprep) if available; otherwise manual list.

### 2. ICA
- Method: extended Infomax.
- N components: 15 (or 0.99 variance if >30 channels).
- Auto-label via mne-icalabel; reject eye / muscle / heart.
- Pre-fit 1 Hz HP filter copy (best practice).

> ⚠️ **Numerical-specification note.** The **"Validated results" below were produced WITHOUT ICA and
> without peak-to-peak rejection** (`reject=None`), resampled to 256 Hz — the *harmonized minimal*
> configuration used for the cross-tool benchmark. Running the ICA step prescribed above is good
> practice for real analyses but will **not** reproduce the certified numbers. To reproduce them, use
> the pinned configuration. See [`tools/benchmark/SPEC_PRECISION_EVAL.md`](../../tools/benchmark/SPEC_PRECISION_EVAL.md).

### 3. Epoch
- **Stimulus-locked:** −0.2 to 0.8 s relative to stimulus onset. Baseline: −0.2 to 0 s.
- **Response-locked:** −0.4 to 0.6 s relative to response. Baseline: −0.4 to −0.2 s.
- Artifact rejection: ±150 µV threshold (or AutoReject if available).
- Derive response condition (compatible/incompatible) from the preceding stimulus marker.

### 4. Claims to test

| ID | Claim | Contrast | Channels / ROI | Time window | Freq band | Test | Direction predicted |
|---|---|---|---|---|---|---|---|
| C1 | Incompatible elicits larger N2 | incomp_stim − comp_stim | FCz, Fz, Cz | 200–350 ms | n/a | cluster perm, trial-level, tail=-1 | incomp more negative |
| C2 | Incompatible responses elicit larger ERN | incomp_resp − comp_resp | FCz, Fz, Cz | 0–100 ms post-resp | n/a | cluster perm, trial-level, tail=-1 | incomp more negative |
| C3 | Frontal theta greater for incompatible | incomp_stim − comp_stim (TFR) | FCz, Fz, Cz | 200–500 ms | 4–8 Hz | cluster perm on theta power, tail=1 | incomp more positive |

### 5. Statistics
- N permutations: 5000.
- Cluster-forming threshold: derived from p < 0.05 (one-sided) t at the actual df.
- RNG seed: 42.
- Adjacency: channel triangulation from 10–20 standard montage.
- Multiple-comparisons across C1/C2/C3: Bonferroni N=3 → α = 0.0167.

### 6. Figures

| Fig | Type | Panels |
|---|---|---|
| F1 | Full case study | (a) stimulus-locked ERP at ROI; (b) response-locked ERP (ERN); (c) N2 topomap; (d) TFR difference; (e) theta time course; (f) PSD |

### 7. Time-frequency
- Method: Morlet wavelets, 4–29 Hz, n_cycles = freqs/3.
- Baseline: −0.2 to 0 s, logratio mode.
- Extract theta (4–8 Hz) at ROI for C3.

## Expected output (validation dataset)

When run on **ERP CORE Subject-001 Flankers** (`mne.datasets.erp_core`), the recipe should produce:

- C1: N2 difference at FCz (incomp more negative). With Bonferroni (α=0.017), may not reach significance in single-subject N=1 data.
- C2: ERN difference at FCz, cluster p < 0.05, Cohen's d ≈ −0.2 to −0.3. Classic frontocentral negative deflection.
- C3: Frontal theta enhancement for incompatible, ~0.1 dB difference.
- F1: 6-panel figure matching the case study output.

## Validated results (2026-05-23)

| Claim | Verdict | Key values |
|-------|---------|-----------|
| C1 (N2) | not supported (Bonferroni) | diff = −0.19 µV, not significant at α=0.017 |
| C2 (ERN) | **supported** | diff = −1.15 µV, cluster p sig, d = −0.23 |
| C3 (Theta) | **supported** | diff = 0.12 dB, 41/77 sig timepoints, d = 0.20 |

Pipeline: 30 EEG ch, 1024 Hz, 0.1–30 Hz FIR, 60 Hz notch, avg ref, ICA 15 comp (6 excluded), stim epochs 393, resp epochs 390, full pipeline 94.6s.

### N>1 group ERN — canonical error−correct (server, 2026-06-24)

The C2 above uses incompatible−compatible responses (a conflict framing). The **standard** ERN is
**error − correct**, response-locked — validated here as a genuine group effect on ERP CORE ERN
(Kappenman 2021), **N = 14** (6 of 20 subjects excluded for <15 error trials), FCz/Fz/Cz, 0–100 ms
post-response, pre-response baseline (−0.4,−0.2), 0.1–30 Hz, 256 Hz, average ref, reject=None:

| Quantity | Value (N = 14) |
|---|---|
| Grand-average ERN (error − correct, 0–100 ms) | **−5.446 µV** (SEM 0.863) |
| One-sample t (vs 0) | **t(13) = −6.31, p = 2.7 × 10⁻⁵**, Cohen's dz = −1.69 |
| Second-level spatiotemporal cluster | **1 significant cluster, p = 0.0004** |

A large, robust ERN. Run: `python tools/validation/validate_ern_erpcore_group.py --subjects 20`.
**Cross-tool benchmark** (the first *response-locked* one): reproduces MNE-BIDS-Pipeline's per-subject
ERN to **≤ 32 nV (CCC = 1.000, 14/14 within ±0.1 µV)** — see [docs/BENCHMARK.md §4e](../../docs/BENCHMARK.md).

## Methods paragraph (for your paper)

```text
[AUTO-GENERATED SKETCH]

Continuous EEG was preprocessed with a 0.1–30 Hz zero-phase FIR bandpass and
60 Hz notch, re-referenced to the average of all scalp channels. ICA (extended
Infomax, 15 components, seed 42) was fit on a 1 Hz high-pass copy; ICLabel
classified 3 eye-blink and 3 muscle components for rejection. Stimulus-locked
epochs (-200 to 800 ms) and response-locked epochs (-400 to 600 ms) were
extracted, baseline-corrected, and artifacts exceeding ±150 µV rejected.

Three pre-registered claims were tested with Bonferroni correction (α = 0.017):
C1 (stimulus N2), C2 (response ERN), and C3 (frontal theta conflict effect),
each using cluster permutation (5000 permutations, seed 42) at FCz/Fz/Cz.
```

## Known limitations

- Single-subject demo: C1 (N2) may not reach significance with N=1 and Bonferroni. With N≥15, the N2 effect is robust in published literature.
- Response-locked epoching requires stimulus→response pairing logic (the recipe handles this automatically).
- Theta TFR requires epoch length > wavelet length at 4 Hz — n_cycles capped at freqs/3 for safety.

## Changelog

- **v0.1.0** (2026-05-23) — initial release. Three claims validated on ERP CORE Subject-001 Flankers.
