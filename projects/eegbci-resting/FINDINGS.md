# FINDINGS — eegbci-resting (server validation)

## 2026-06-19 — Resting recipes validated end-to-end on real public data (N=20)

PhysioNet **eegbci**, subjects 1–20, eyes-closed (R02) vs eyes-open (R01), 64 ch, resampled
160→250 Hz, ICA/ICLabel-cleaned. One run validates all three resting/complexity recipes and
provides an **N>1 second-level group test** (retires the "all results are N=1" limitation).
Runner: `python tools/validation/validate_resting_recipes.py --subjects 20`.

### C1 — Posterior alpha reactivity (resting-spectral-connectivity)
- **eyes-closed > eyes-open posterior alpha: CONFIRMED.**
- Posterior (8–13 Hz) power: EC = 6.73×10⁻¹¹ vs EO = 8.45×10⁻¹² V²/Hz (≈ 8×).
- Paired t (EC−EO), N=20: **t = 3.60, p = 0.0019, dz = 0.81**.
- **Second-level spatial cluster permutation** (5000 perms, seed 42): **1 significant cluster, p = 0.0002**, spanning 62/64 channels (posterior-maximal). ← the N>1 group result.

### C2 — Complexity drops with eyes closed (complexity-anesthesia)
- **eyes-open > eyes-closed complexity: CONFIRMED (LZC + permutation entropy).**
- Lempel–Ziv: EO = 0.520 vs EC = 0.473 — **t = 5.29, p = 4.2×10⁻⁵, dz = 1.18**.
- Permutation entropy: EO = 0.812 vs EC = 0.776 — **t = 7.92, p = 2.0×10⁻⁷, dz = 1.77**.
- **ICA was decisive:** before ICLabel eye/muscle removal the LZC contrast was direction-mixed (residual EOG/EMG inflates complexity); it became clean only after ICA — exactly the recipe's warning. Spectral entropy did not separate the states (1/f-dominated); not headlined.
- The anesthesia (awake→deep) contrast itself is **not tested** (no anesthesia data); literature-based.

### C3 — Canonical microstates (resting-microstate)
- **4 maps, ~70% GEV, durations 70–120 ms: CONFIRMED.**
- Total GEV (K=4) = **0.662 ± 0.120**; mean microstate duration median = **103 ms** (IQR 94–113).
- Caveat: at native 160 Hz the sample-based smoothing inflated durations to ~200 ms; resampling to 250 Hz brought them into the canonical band — the smoothing params are sfreq-dependent.

### Verdict
| Recipe | Sanity check | Verdict |
|--------|--------------|---------|
| resting-spectral-connectivity | EC > EO posterior alpha | ✅ validated (cluster p=0.0002) |
| complexity-anesthesia | EO > EC complexity (awake) | ✅ validated (LZC/PE); anesthesia untested |
| resting-microstate | 4 maps ~70% GEV, 70–120 ms | ✅ validated |

### Limitations (honest)
- eegbci native 160 Hz (< recipes' min_sfreq 250) → upsampled; ~61 s/run (< recommended 120 s).
- Single dataset, healthy young adults; per-subject (not group-template) microstate maps.
- `specparam` 1/f and wPLI connectivity were API-smoke-tested, not benchmarked here.

Figure: `figure-stage/resting_validation.png` · Methods: `report-stage/methods.md` ·
Audit: `audit-stage/AUDIT.md` · Receipt: `report-stage/REPRO_RECEIPT.md`.
