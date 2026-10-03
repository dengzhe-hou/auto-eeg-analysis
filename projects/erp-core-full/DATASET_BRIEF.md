# DATASET_BRIEF — erp-core-flankers-full

## 1. Study identity
- **Study short name:** erp-core-flankers-full
- **Paradigm:** Eriksen Flankers — compatible vs incompatible, stimulus-locked + response-locked
- **Hypothesis:** (C1) Incompatible stimuli elicit larger N2 at FCz 200-350ms; (C2) Incompatible responses elicit larger ERN at FCz 0-100ms; (C3) Theta power (4-8Hz) is greater for incompatible 200-500ms post-stimulus
- **Source:** Kappenman et al. 2021, NeuroImage (ERP CORE)

## 2. Subjects
- **N:** 1 (case study demo)
- **Group structure:** single-subject, within-subject conditions

## 3. Acquisition
- **System:** BioSemi ActiveTwo
- **Channels:** 30 EEG (10-20) + 3 EOG (HEOG_left, HEOG_right, VEOG_lower)
- **Sampling rate:** 1024 Hz
- **Online reference:** CMS/DRL
- **Online filter:** DC-coupled

## 4. Conditions
| Condition | Event | N trials |
|-----------|-------|----------|
| stimulus/compatible/target_left | 3 | 100 |
| stimulus/compatible/target_right | 4 | 100 |
| stimulus/incompatible/target_left | 5 | 100 |
| stimulus/incompatible/target_right | 6 | 100 |
| response/left | 1 | ~200 |
| response/right | 2 | ~200 |

## 5. Preprocessing
- Bandpass: 0.1–30 Hz zero-phase FIR
- Notch: 60 Hz (US data)
- Reference: average
- Bad channel detection: RANSAC (default)
- Epoch window (stimulus): -0.2 to 0.8 s
- Epoch window (response): -0.4 to 0.6 s
- Baseline: -0.2 to 0 s (stimulus), -0.4 to -0.2 s (response)
- Artifact rejection: ±150 µV threshold

## 6. Analyses planned
- [x] ERP — N2 (stimulus-locked) + ERN (response-locked)
- [x] Time-frequency (TFR) — theta band conflict effect
- [x] Spectral — PSD comparison

## 7. Statistical plan
- Cluster permutation, trial-level (single subject)
- 5000 permutations, seed 42
- One-sided tests per directional hypothesis
