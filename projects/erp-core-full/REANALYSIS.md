# Flankers reanalysis, 2026-10-04

This is the current corrected single-participant example on `main`, after the immutable v0.3.2 release. It revises the historical analysis plan with the owner's approval before execution. The original [plan](ANALYSIS_PLAN.md) and [findings](FINDINGS.md) remain available as historical records. This is a downstream rerun from saved epochs, not a new LLM evaluation or a raw-to-report timing measurement.

The machine-readable [result record](REANALYSIS.json) contains every tested claim, including nonsignificant outcomes, the input accounting, configuration and environment. Complete arrays, cluster labels, all cluster probabilities and permutation nulls are produced by the runner. The source raw data and cached derivatives remain in their existing storage locations; large arrays are not committed here.

## Corrected results


Only downstream analysis was executed from saved ICA-cleaned epochs; preprocessing and ICA were not rerun.

All three originally planned claims and all retained trials are reported.

## C1: Stimulus-locked N2 compatibility contrast

- Incompatible: 1.34151 uV; compatible: 1.53394 uV.
- Difference: -0.192431 uV; pooled Cohen's d: -0.0620903.
- Retained trials: {'incompatible': 197, 'compatible': 196}.
- Cluster p-values: [0.0588].
- Result at cluster alpha 0.05/3: does_not_support (0 significant clusters).

## C2: Response-locked compatibility contrast

- Incompatible: -2.06728 uV; compatible: -0.916038 uV.
- Difference: -1.15125 uV; pooled Cohen's d: -0.316387.
- Retained trials: {'incompatible': 194, 'compatible': 196}.
- Cluster p-values: [0.0006].
- Result at cluster alpha 0.05/3: supports (1 significant clusters).

## C3: Frontal theta compatibility contrast

- Incompatible: -0.0472073 dB; compatible: -1.32616 dB.
- Difference: 1.27895 dB; pooled Cohen's d: 0.295295.
- Retained trials: {'incompatible': 197, 'compatible': 196}.
- Cluster p-values: [0.0002].
- Result at cluster alpha 0.05/3: supports (1 significant clusters).

## Scope

Single participant; trial-level conditional inference only.
Historical results remain in the original project; this output does not change the v0.3.2 release.
Run elapsed time: 12.596 s for the scope stated above.

## Reproduce

Run from the repository root in the documented environment, with the original project raw data and saved epochs available. `--out` must name a new output directory. To rerun Flankers preprocessing and ICA as well, omit `--reuse-epochs`; the published correction used the saved epochs.

```bash
python tools/run_full_case_study.py --reuse-epochs --out projects/erp-core-full/stats-stage/new-run
python tools/gen_case_study_figures.py --run-dir projects/erp-core-full/stats-stage/new-run
```

## Methods and assumptions


This is an internally produced single-participant demonstration using ERP CORE Subject-001. Only downstream analysis was executed from saved ICA-cleaned epochs; preprocessing and ICA were not rerun.
The source epoch configuration is 0.1–30 Hz zero-phase FIR filtering, 60 Hz notch filtering,
average reference, extended Infomax ICA with 15 components and seed 42, and ICLabel exclusion
of eye-blink, muscle-artifact and heart-beat components. Actual component labels/exclusions are
recorded in the ICA summary identified in summary.json.
Stimulus epochs span −0.2 to 0.8 s with a −0.2 to 0 s baseline. Response epochs span −0.4 to
0.6 s with a −0.4 to −0.2 s baseline. Rejection uses a 150 µV peak-to-peak EEG threshold.
All 393 retained stimulus trials and
390 retained response trials were included without equal-count truncation.

C1 compares incompatible minus compatible stimulus-locked activity at FCz/Fz/Cz in 200–350 ms.
C2 makes the same compatibility contrast on response-locked activity at FCz/Fz/Cz in 0–100 ms.
C2 is not the canonical error-minus-correct ERN contrast. C3 tests the complete 4–8 Hz,
200–500 ms, FCz/Fz/Cz domain. Morlet power uses 4–29 Hz, n_cycles=freqs/3, zero_mean=True,
use_fft=False, and decim=4. Baseline normalization is applied separately to every trial and
channel/frequency before averaging: 10 log10(power / mean baseline power), in dB. This same
quantity is used in statistics, figures and descriptive summaries.

Each claim uses a pooled independent-samples t statistic with compatibility-label permutations
restricted to original block × target-side strata, retaining each stratum's condition counts.
This assumes conditional exchangeability within the strata; the original task randomization
algorithm was not reconstructed. Original samples link each retained epoch to its stimulus,
block and target side. Block gaps greater than 2 s separate the recorded 40-trial blocks.
The cluster adjacency combines the original three-channel triangulation with neighboring time
samples and, for C3, neighboring frequency bins. All tests use 5,000 permutations, seed 42,
one-sided cluster-forming p=0.05, tails −1/−1/+1, and cluster p<0.05/3 after Bonferroni across
the three claims. Cluster masses sum signed t values; negative-tail null maxima use positive
absolute masses. Full observed maps, cluster labels, every cluster p-value and permutation
null are saved. Cluster extents are not onset/offset confidence intervals.

Cohen's d is reported for every claim regardless of significance, using each trial's full
planned-domain mean and pooled within-condition sample variance (ddof=1). It is a descriptive
effect size without block or side adjustment. Inference is conditional on this participant's
retained trials and does not support population conclusions. Methods are produced by the saved
Python program from its configuration and result records, not a new LLM generation.

Execution time for this run scope: 12.596 s.
Environment: Python 3.11.15, MNE 1.12.1,
NumPy 2.4.6, SciPy 1.17.1.

## What changed

The old analysis truncated conditions to equal counts and paired unrelated trials. The corrected tests retain all 393 stimulus and 390 response epochs and shuffle compatibility labels within each recorded block × target-side stratum. The cluster-forming level is p=0.05; the final threshold remains 0.05/3 across the three planned claims. C3 now clusters jointly over time, frequency and the three electrodes rather than testing a reduced time course.

MNE `logratio` is log10 power ratio, so the old values labelled dB lacked a factor of ten. The corrected C3 normalizes power separately in each trial, then averages this same quantity for statistics and figures. The previous display normalized averaged power, which is a different estimand. Keeping the previously truncated 196 trials per condition reproduces the old statistical contrast after the factor-of-ten correction (1.2643586534 dB); restoring the 197th incompatible trial gives 1.2789527859 dB. Morlet settings are unchanged.

C2 is a response-locked incompatible-minus-compatible comparison, not an error-minus-correct ERN test. The separate multi-participant canonical ERN validation remains unchanged.

## Figure files

Figure export requires Arial or Helvetica installed on the rendering machine; the plotter stops if neither is available. The published correction uses Arial.

[PDF](../../docs/assets/flankers-case-study-corrected.pdf) · [SVG](../../docs/assets/flankers-case-study-corrected.svg) · [PNG](../../docs/assets/flankers-case-study-corrected.png) · [Caption](../../docs/assets/flankers-case-study-corrected.caption.txt)
