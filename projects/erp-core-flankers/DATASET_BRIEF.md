# DATASET_BRIEF — erp-core-flankers
## 1. Study identity
- **Study short name:** erp-core-flankers
- **Paradigm:** Eriksen Flankers (compatible vs incompatible) — response-locked ERN
- **Hypothesis:** Incompatible trials elicit a larger ERN (more negative) than compatible at FCz
- **Source:** Kappenman et al. 2021, NeuroImage (ERP CORE)
## 2. Subjects
- **N:** 1 (validation demo)
## 3. Acquisition
- **System:** BioSemi ActiveTwo
- **Channels:** 30 EEG (10-20) + 3 EOG
- **Sampling rate:** 1024 Hz
- **Reference:** CMS/DRL (BioSemi), re-reference offline to average
## 4. Conditions
| Condition | Event | N trials |
|-----------|-------|----------|
| compatible/left | stimulus/compatible/target_left | 100 |
| compatible/right | stimulus/compatible/target_right | 100 |
| incompatible/left | stimulus/incompatible/target_left | 100 |
| incompatible/right | stimulus/incompatible/target_right | 100 |
| response/left | response/left | 202 |
| response/right | response/right | 200 |
## 5. Preprocessing
- Bandpass: 0.1–30 Hz (ERN-appropriate)
- Reference: average
- Epoch: -0.4 to 0.8 s response-locked
- Baseline: -0.4 to -0.2 s
