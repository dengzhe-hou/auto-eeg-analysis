# FINDINGS — erp-core-flankers (ERP CORE validation)

## 2026-05-22 — Flankers ERN: Incompatible vs Compatible

### C1: Incompatible > Compatible ERN
- Incompat ERN: -2.08 µV | Compat ERN: -0.93 µV | Diff: -1.15 µV
- ROI: ['FCz', 'Cz', 'Fz'] | Window: 0–100 ms post-response
- Cluster perm: 1 significant, 5000 perms
- Cohen's d: -0.162 if cohens_d else 'N/A'
- Direction: CONSISTENT (incompat more negative)
- **Real EEG data** (ERP CORE, Kappenman et al. 2021)
- Single subject, trial-level inference

### Pipeline
- Data: ERP CORE Subject-001, Flankers task, BioSemi 30 EEG, 1024 Hz
- Preprocess: 0.1–30 Hz FIR, average ref
- ICA: Infomax 15 comp, ICLabel excluded 6
- Epochs: 387 response-locked, ±150µV reject
- Compatible: 195 trials, Incompatible: 192 trials
