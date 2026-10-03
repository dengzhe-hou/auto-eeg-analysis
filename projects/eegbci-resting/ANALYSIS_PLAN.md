# ANALYSIS_PLAN — eegbci-resting

## Plan version
- **v1**, frozen 2026-06-19 (server validation of resting/complexity recipes)

## Claims (built-in recipe sanity checks)
| ID | Claim | Contrast | ROI / scope | Window / band | Test | Direction | alpha |
|----|-------|----------|-------------|---------------|------|-----------|-------|
| C1 | Posterior alpha reactivity | eyes-closed − eyes-open | posterior (O/PO/P) | 8–13 Hz | paired t + spatial cluster perm | EC > EO | 0.05 |
| C2 | Complexity drops with eyes closed | eyes-open − eyes-closed | whole-scalp mean | LZC, perm-entropy (0.5–45 Hz) | paired t, FDR over panel | EO > EC | 0.05 |
| C3 | Canonical microstates | descriptive (EC) | whole-scalp | 2–20 Hz, K=4 | GEV + duration ranges | ~70% GEV, 70–120 ms | n/a |

## Seeds
- ICA: 42, ModKMeans: 42, Cluster permutation: 42

## Multiple comparisons
- C1: spatial cluster permutation (intrinsic correction across channels)
- C2: FDR across the complexity measure panel

## Notes
- eegbci is natively 160 Hz (below the recipes' `min_sfreq=250`); resampled to 250 Hz so the
  sample-based microstate smoothing parameters behave as designed and the data gate is met.
- Runs are ~61 s/state (below the recipes' `min_duration_s=120`); adequate for the robust
  alpha-reactivity and complexity contrasts but short for stable microstate parameters
  (Khanna 2014) — reported as a limitation, not promoted as a stability claim.
