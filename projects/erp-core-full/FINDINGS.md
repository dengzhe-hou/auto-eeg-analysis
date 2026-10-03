# FINDINGS — erp-core-flankers-full (AEA Full Case Study)

## 2026-05-23 — Flankers Conflict Processing

### C1: N2 (Incompatible > Compatible, stimulus-locked)
- Compatible N2: 1.53 µV | Incompatible N2: 1.34 µV | Diff: -0.19 µV
- ROI: ['FCz', 'Fz', 'Cz'] | Window: 200-350 ms
- Cluster perm: does_not_support, 0 sig, d=None
- Direction: CONSISTENT

### C2: ERN (Incompatible > Compatible, response-locked)
- Compatible ERN: -0.92 µV | Incompatible ERN: -2.07 µV | Diff: -1.15 µV
- ROI: ['FCz', 'Fz', 'Cz'] | Window: 0-100 ms post-response
- Cluster perm: supports, 1 sig, d=-0.23193049025667903
- Direction: CONSISTENT

### C3: Theta conflict effect (TFR)
- Compatible theta: -0.0600 dB | Incompatible theta: 0.0557 dB
- ROI: ['FCz', 'Fz', 'Cz'] | Window: 200-500 ms, 4-8 Hz
- supports, 41/77 sig timepoints, d=0.204

### Pipeline
- Data: ERP CORE Subject-001, Flankers, BioSemi 30ch, 1024Hz
- Preprocess: 0.1-30 Hz FIR, 60Hz notch, avg ref
- ICA: Infomax 15 comp, ICLabel excluded 6
- Stim epochs: 393 (±150µV) | Resp epochs: 390
- Bonferroni alpha = 0.0167
