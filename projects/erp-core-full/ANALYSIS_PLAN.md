# ANALYSIS_PLAN — erp-core-flankers-full
## Plan version
- **v1**, frozen 2026-05-23 00:44

## Claims
| ID | Claim | Contrast | ROI | Window | Test | Direction | alpha |
|----|-------|----------|-----|--------|------|-----------|-------|
| C1 | Incompatible elicits larger N2 | incomp_stim − comp_stim | FCz, Fz, Cz | 200–350 ms post-stim | cluster perm, 1-sample, trial-level | incomp more negative | 0.05 |
| C2 | Incompatible responses elicit larger ERN | incomp_resp − comp_resp | FCz, Fz, Cz | 0–100 ms post-resp | cluster perm, 1-sample, trial-level | incomp more negative | 0.05 |
| C3 | Theta power greater for incompatible (TFR) | incomp_stim − comp_stim | FCz, Fz, Cz | 200–500 ms, 4–8 Hz | cluster perm on TFR, trial-level | incomp more positive | 0.05 |

## Seeds
- ICA: 42, Cluster: 42, AutoReject: N/A (threshold)

## Multiple comparisons
- Bonferroni N=3, adjusted alpha = 0.0167
