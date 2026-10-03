# FINDINGS — mne-sample-audvis

> Historical record. The corrected 2026-10-04 analysis is in [REANALYSIS.md](REANALYSIS.md). The values and earlier audit claims below are preserved verbatim; they contain the statistical, ROI and retention errors described there and must not be used as current results.

## 2026-05-22 — Case Study: Auditory vs Visual N100 (v2, post-audit fix)

### C1: Auditory > Visual N100
- Aud N100: -1.59 µV | Vis N100: -0.19 µV | Diff: -1.40 µV
- ROI: ['F3', 'F3', 'F3', 'FC1', 'FC1', 'FC2', 'F4', 'FC1', 'FC2', 'Cz', 'Cz', 'Cz'] (mapped from ['EEG 004', 'EEG 008', 'EEG 009', 'EEG 010', 'EEG 011', 'EEG 014', 'EEG 016', 'EEG 020', 'EEG 022', 'EEG 030', 'EEG 031', 'EEG 040'])
- Window: 80–150 ms (matches ANALYSIS_PLAN)
- Cluster perm: 1 significant cluster(s), 5000 perms, tail=-1 (one-sided)
- Cohen's d: -0.461
- Direction: CONSISTENT
- **Limitation**: Single subject, trial-level inference only.

### Audit fixes applied
1. ROI aligned to plan (Fz/Cz/FC1/FC2/F3/F4)
2. Time window aligned to plan (0.08–0.15s)
3. Permutations increased to 5000
4. One-sided test (tail=-1) for directional hypothesis
5. Baseline correction explicitly reported
6. Full filter specs reported
7. Adjacency construction documented
8. AutoReject vs threshold deviation documented
9. BACKEND_RESOLUTION.md created
