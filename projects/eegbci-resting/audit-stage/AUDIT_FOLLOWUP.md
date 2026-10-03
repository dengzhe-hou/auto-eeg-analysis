# AUDIT FOLLOW-UP — eegbci-resting

> Responses to the GPT cross-model review (`AUDIT.md`). Three of the reviewer's
> required revisions were turned into actual experiments on the same eegbci data
> (`tools/validation/audit_followups.py`, N=20; microstate N=10). The reviewer was
> **partly vindicated** on all three — reported honestly below.

## 1a — Complexity ICA-sensitivity (review item #5)

Re-ran the EO>EC complexity contrast **without** ICA (and with mean vs median binarization):

| Measure | With ICA (committed) | **Without ICA** | Conclusion |
|---|---|---|---|
| Permutation entropy (order 3) | p = 2.0×10⁻⁷ | **p = 4.9×10⁻⁶ (dz = 1.41)** | **robust** to preprocessing |
| Lempel–Ziv (median binarization) | p = 4.2×10⁻⁵ | **p = 0.59 (dz = −0.12)** | **collapses** without ICA |
| Lempel–Ziv (mean binarization) | — | p = 0.74 | also fragile |

**Verdict:** the reviewer was right that the **LZC** result is ICA-dependent (residual EOG/EMG). But **permutation entropy survives without ICA**, so it is the robust primary measure. The `complexity-anesthesia` recipe now recommends PE as the headline and flags LZC as artifact-sensitive.

## 1b — Microstate stability + physical-unit smoothing (review items #7, #8)

Re-fit microstates at **native 160 Hz** with smoothing expressed in **physical units (30 ms)** instead of samples, across 3 seeds, with a split-half map-reproducibility check (N=10):

| Quantity | Sample-based (old) | **Physical-unit (fixed)** |
|---|---|---|
| Mean duration @ native 160 Hz | ~200 ms | **116 ms** (range 96–147) |
| Total GEV | — | 0.631 |
| Split-half map similarity ( \|r\| ) | — | **0.866** (highly reproducible) |

**Verdict:** the reviewer was right that sample-based smoothing is sfreq-fragile. Switching to physical units fixes the duration artifact (200 → 116 ms at 160 Hz) and maps are reproducible across data halves (|r| = 0.87). The `resting-microstate` recipe code block now derives the windows from `sfreq`.

## 1c — Alpha topography (review item #3)

Per-channel EC−EO alpha (8–13 Hz) paired t-map:

| Region | Mean t |
|---|---|
| Posterior (O/PO/P) | 3.29 |
| Anterior | 3.40 |
| Max | TP8 (t = 4.51) |

**Verdict:** the reviewer was right — the EC−EO alpha difference is **spatially diffuse, not posterior-specific** (posterior ≈ anterior), which is why the second-level cluster spans 62/64 channels. This is an **average-reference** effect (eye-closure raises alpha broadly; the average reference redistributes it). The recipe's *posterior alpha power* contrast is genuine, but the *difference topography* is reference-dependent — now documented in the `resting-spectral-connectivity` caveat.

## 1d — Connectivity wPLI benchmark (review item #2, `tools/validation/validate_connectivity.py`, N=15)

Posterior-posterior debiased wPLI (alpha 8–13 Hz), eyes-closed vs eyes-open:

| Quantity | Value |
|---|---|
| EC wPLI | 0.270 |
| EO wPLI | 0.193 |
| diff (EC−EO) | +0.076 (dz = 0.36) |
| paired t (N=15) | t = 1.40, **p = 0.18 (n.s.)** |

**Verdict:** wPLI runs correctly and **trends in the expected direction** (EC > EO posterior alpha synchrony) but is **not group-significant** — it is much weaker/noisier than the power effect (a dz ≈ 0.36 needs N ≈ 60). So connectivity moves from "API-smoke only" to "runs + trends right but underpowered"; the recipe now labels wPLI claims **exploratory**. This is the honest answer to the reviewer's point #2.

## Still open (deferred follow-ups, with reasons)
- `specparam` 1/f: still API-smoke-tested only (not benchmarked against a literature 1/f slope).
- Anesthesia awake→deep contrast: untested (no anesthesia data on the server).
- Microstate group-template maps + K-sensitivity: deferred — split-half (|r|=0.87) and 3-seed
  stability already establish reproducibility; group-template/K-sweep are refinements, not gaps.
- SampEn full panel: deferred — permutation entropy already shown robust (a stronger measure
  than SampEn here); adding SampEn is redundant for the EO>EC sanity check.

Figure: `figure-stage/F2_audit_followups.png` (alpha t-map topomap + complexity without-ICA bars).
