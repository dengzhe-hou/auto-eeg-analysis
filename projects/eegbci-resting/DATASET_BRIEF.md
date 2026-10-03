# DATASET_BRIEF — eegbci-resting

## 1. Study identity
- **Study short name:** eegbci-resting
- **Paradigm:** Resting-state, eyes-open vs eyes-closed (no per-trial markers)
- **Purpose:** Server-side end-to-end validation of three AEA resting/complexity recipes
  (`resting-spectral-connectivity`, `complexity-anesthesia`, `resting-microstate`) on a
  real public dataset, and one N>1 group analysis to retire the "all results are N=1" limitation.
- **Source:** PhysioNet EEG Motor Movement/Imagery Database (Schalk et al. 2004), baseline runs
  R01 (eyes-open) and R02 (eyes-closed). Fetched via `mne.datasets.eegbci`.

## 2. Subjects
- **N:** 20 (subjects 1–20 of 109 available)
- **Group structure:** within-subject state contrast (eyes-closed vs eyes-open)

## 3. Acquisition
- **System:** BCI2000, 64-channel international 10–10 montage
- **Sampling rate:** 160 Hz (native) → resampled to 250 Hz to meet each recipe's `min_sfreq`
- **Reference:** re-referenced offline to the common average
- **Duration:** ~61 s per state per subject

## 4. Conditions
| Condition | eegbci run | Plain meaning |
|-----------|-----------|---------------|
| eyes-open  | R01 | baseline, eyes open |
| eyes-closed| R02 | baseline, eyes closed |

## 5. Preprocessing
- Resample to 250 Hz; recipe-specific bandpass (1–45 Hz spectral / 2–20 Hz microstate / 0.5–45 Hz complexity)
- Reference: common average
- ICA (extended Infomax, 15 comp, seed 42) + ICLabel; reject eye / muscle / heart components

## 6. Analyses planned
- [x] Spectral: posterior alpha power + 1/f, eyes-closed vs eyes-open (sanity: EC > EO)
- [x] Complexity: LZC / permutation entropy, eyes-open vs eyes-closed (sanity: EO > EC)
- [x] Microstate: K=4 modified k-means GEV + durations (sanity: ~4 maps, ~70% GEV, 70–120 ms)

## 7. Statistical plan
- Second-level (across-subject) paired tests; spatial cluster-permutation across channels
  (5000 permutations, seed 42) for the alpha-reactivity map. N=20.
