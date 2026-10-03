# AUDIT — eegbci-resting

> **Cross-model adversarial review (AEA `eeg-audit`, W3).**
> Reviewer: GPT (OpenAI) via Codex MCP, prompted as a hostile EEG methods reviewer.
> Date: 2026-06-19. Subject: the N=20 server validation of the three resting/complexity recipes.
> This memo is reproduced verbatim; the maintainer response follows at the end.

---

This validation is better described as a narrow smoke/sanity test on a convenient public dataset, not a validation of three resting-state EEG recipes. Several reported effects are plausible, but the inferential framing is too generous: the design tests a few expected state contrasts under short, upsampled, aggressively cleaned recordings, while leaving major recipe components unbenchmarked.

## Per-claim audit

### C1: Resting-spectral-connectivity recipe — **pass-with-caveats**
The eyes-closed > eyes-open posterior alpha result is biologically plausible and numerically convincing (posterior alpha EC = `6.73e-11` vs EO = `8.45e-12 V^2/Hz`, `t(19)=3.60`, `p=0.0019`, `dz=0.81`). But the claim is overstated if presented as validation of a "spectral-**connectivity**" recipe: the validated result is an alpha **power** contrast, and wPLI connectivity was only API-smoke-tested. The second-level cluster (one cluster `p=0.0002` spanning `62/64` channels) is suspiciously nonspecific — a posterior alpha effect should be posteriorly emphasized, not near-whole-scalp; the reference/adjacency/cluster-forming procedure may be producing spatially diffuse significance. Resampling `160→250 Hz` is unnecessary for 8–13 Hz PSD and cannot recover absent information.

### C2: Complexity-anesthesia recipe — **revise**
The eyes-open > eyes-closed complexity contrast is a strong within-dataset awake sanity check (LZC EO=`0.520` vs EC=`0.473`, `p=4.2e-5`, `dz=1.18`; permutation entropy `p=2.0e-7`). But the central biological contrast — awake→deep anesthesia — was not tested; calling the recipe "validated" on this basis is a category error. The dependence on ICA is a major red flag: a result that is direction-mixed without ICA and clean only after it needs controls, not a validation label. Median-binarized LZC is vulnerable to amplitude/spectral changes (eyes-closed alpha dominance can lower apparent complexity without indexing consciousness). Spectral entropy did not separate states — a failed subclaim, not a footnote.

### C3: Resting-microstate recipe — **revise**
GEV = `0.662 ± 0.120` and duration median = `103 ms` (IQR `94–113`) look conventional after resampling, but the analysis exposes a serious fragility: at native `160 Hz` durations were ~`200 ms`, and resampling "fixed" them because smoothing parameters are sample-based. Per-subject (not group-template) maps weaken comparability; `~61 s` recordings are short; no reliability/seed/split-half/K-sensitivity analysis is reported. Convention (K=4, seed 42) is not validation.

## Cross-cutting concerns
Upsampling `160→250 Hz` does not make the data equivalent to native 250 Hz and should not be used to satisfy a recipe `min_sfreq`. `~61 s` is below the recommended `≥120 s` and affects endpoints differently. The word "validated" is over-claimed across all three. The LZC result needs a preprocessing-sensitivity audit. Microstate stability is insufficiently established.

## Required revisions before publication
1. Replace "validated" with "sanity-checked"/"partially benchmarked" unless each recipe's core endpoint is tested.
2. C1: separate alpha-PSD validation from connectivity validation; do not imply wPLI was validated.
3. Report ROI, PSD params, cluster threshold/adjacency/correction, and effect topography; explain the 62/64 cluster.
4. C2: state plainly that anesthesia was not tested.
5. Add LZC/PE preprocessing-sensitivity analyses (with/without ICA, ICLabel thresholds, alternative binarization).
6. Treat spectral entropy as an unsupported subclaim if it belongs to the recipe.
7. C3: fix sfreq-dependent smoothing in physical units; rerun native 160 Hz vs 250 Hz to quantify bias.
8. Add microstate stability analyses (seeds, split-half, K sensitivity, group-template, canonical-map correlations).
9. Do not use upsampling to claim `min_sfreq=250` compliance; report native 160 Hz.
10. Add a limitation that all claims rest on one short, healthy-subject, motor-imagery baseline dataset.

---

## Maintainer response (2026-06-19)

The review is accepted as largely valid; dispositions:

| # | Disposition |
|---|---|
| 1 | **Accepted, scoped.** `status: validated` here means *the recipe's built-in sanity check is confirmed on real data* — each RECIPE's "Validated results" section now states explicitly what was and was **not** tested. The word remains per the hand-off's promotion rule, but is bounded by those caveats. |
| 2 | **Done.** `resting-spectral-connectivity` RECIPE now says only the alpha-power sanity check is validated; wPLI/`specparam` are marked API-smoke-tested only. |
| 3 | **Partially done / open.** ROI, PSD params, seeds, adjacency, 5000-perm correction are recorded in `report-stage/methods.md` + `ANALYSIS_PLAN.md`. The near-whole-scalp cluster (avg-reference alpha is genuinely widespread but posterior-max) warrants a topography panel — **deferred** (follow-up). |
| 4 | **Done.** The complexity RECIPE + FINDINGS state plainly the anesthesia contrast was not tested (no anesthesia data); only the awake EO>EC check is validated. |
| 5 | **Open (follow-up).** The ICA-dependence is reported as a finding; a full with/without-ICA + alternative-binarization sensitivity sweep is a good next experiment. |
| 6 | **Done.** Spectral entropy is reported as not separating states and is explicitly not headlined. |
| 7 | **Accepted (recipe fix).** The sample-based microstate smoothing should be physical-unit/sfreq-aware — logged as a recipe-improvement follow-up; current run documents the 160 Hz→200 ms vs 250 Hz→103 ms bias. |
| 8 | **Open (follow-up).** Seed/split-half/K-sensitivity/group-template stability analyses deferred. |
| 9 | **Accepted.** Native sampling rate (160 Hz) is reported throughout; upsampling is disclosed, not used to hide non-compliance. |
| 10 | **Done.** The single-dataset, healthy-young-adult, short-duration limitation is stated in FINDINGS and every RECIPE caveat. |

Net: the three sanity checks are real and strongly significant at N=20; the "validated" label is bounded to those checks; connectivity, anesthesia, 1/f benchmarking, and microstate stability remain explicitly untested and are the recommended next experiments.
