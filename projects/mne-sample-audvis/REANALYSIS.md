# N100 reanalysis, 2026-10-04

This is the current corrected single-participant example on `main`, after the immutable v0.3.2 release. It revises the historical analysis plan with the owner's approval before execution. The original [plan](ANALYSIS_PLAN.md) and [findings](FINDINGS.md) remain available as historical records. This is a downstream rerun from saved epochs, not a new LLM evaluation or a raw-to-report timing measurement.

The machine-readable [result record](REANALYSIS.json) contains every tested claim, including nonsignificant outcomes, the input accounting, configuration and environment. Complete arrays, cluster labels, all cluster probabilities and permutation nulls are produced by the runner. The source raw data and cached derivatives remain in their existing storage locations; large arrays are not committed here.

## Corrected results


Auditory mean: -2.014844 µV; visual mean: -0.478059 µV; auditory minus visual: -1.536785 µV; cycle-level dz: -0.462439.

The analysis uses 61 complete cycles (122 auditory and 122 visual trials). The 45 target trials in incomplete cycles are retained in input-accounting records and excluded from this approved analysis.

1 significant clusters out of 1 total clusters.

- Cluster 0: p = 0.0004, t sum = -503.57, significant = True.

- This is a single-subject example; it does not support population inference.
- Conditions follow fixed within-cycle positions, not randomized assignment; condition effects cannot be separated from within-cycle position effects.
- The sign-flip null assumes independent cycle differences with a symmetric distribution about zero; the fixed presentation order does not guarantee this.
- The six ROI electrodes approximate template sites after coordinate-frame alignment; their original acquisition labels have not been recovered.
- Only complete four-condition cycles enter the approved analysis. The 45 target trials in smiley-interrupted cycles are explicitly excluded, not classified as artifact rejections.

## Reproduce

Run from the repository root in the documented environment, with the original project raw data and saved epochs available. `--out` must name a new output directory.

```bash
python tools/run_fix_audit.py --out projects/mne-sample-audvis/stats-stage/new-run
python tools/gen_case_study_figures.py --run-dir projects/mne-sample-audvis/stats-stage/new-run
```

## Methods and assumptions


Saved single-subject epochs were reused without rerunning preprocessing. The historical voltage rejection threshold was 150 µV peak-to-peak. All 289/289 target epochs were retained (100.0%). The 31 non-target events were not artifact rejections.

The raw stimulus sequence, retaining smileys and excluding button presses, comprises 76 fixed [auditory/right, visual/left, auditory/left, visual/right] cycles. The approved analysis uses 61 complete cycles, each contributing the mean of its two auditory epochs minus the mean of its two visual epochs. The 45 target trials in the 15 smiley-interrupted cycles are excluded from this analysis and are individually listed in summary.json. No additional target epoch is missing.

The standard_1020 montage was transformed to head coordinates before selecting the nearest measured electrode for each planned target: Fz represented by EEG 006 (27.04 mm); Cz represented by EEG 021 (19.14 mm); FC1 represented by EEG 011 (2.96 mm); FC2 represented by EEG 014 (3.90 mm); F3 represented by EEG 005 (9.91 mm); F4 represented by EEG 007 (7.94 mm). These are approximate template-site correspondences, not recovered acquisition labels.

One negative-tailed spatiotemporal cluster test covered all six electrodes and 80–150 ms, with 5000 sign-flip permutations, seed 42, and a cluster-forming t threshold of -1.67064886 (one-sided p = 0.05, df = 60). Channel adjacency was obtained by Delaunay triangulation of measured electrode positions. Cluster mass was the sum of t statistics; temporal adjacency connected successive time samples. All clusters and their probabilities are retained. Cycle-level Cohen dz is the mean ROI/window difference divided by its sample standard deviation (ddof = 1). Waveforms, mean amplitudes, and SEM use the same 61 cycles and 244 trials.

- This is a single-subject example; it does not support population inference.
- Conditions follow fixed within-cycle positions, not randomized assignment; condition effects cannot be separated from within-cycle position effects.
- The sign-flip null assumes independent cycle differences with a symmetric distribution about zero; the fixed presentation order does not guarantee this.
- The six ROI electrodes approximate template sites after coordinate-frame alignment; their original acquisition labels have not been recovered.
- Only complete four-condition cycles enter the approved analysis. The 45 target trials in smiley-interrupted cycles are explicitly excluded, not classified as artifact rejections.

## What changed

The historical nearest-electrode mapping compared mismatched coordinate frames and treated multiple electrodes as exact template labels. The corrected mapping first transforms the template to head coordinates, then uses the nearest measured electrode for each of the six planned targets. Distances are 2.96–27.04 mm, so the locations remain approximations.

Arbitrary pairing of condition arrays is replaced by the observed complete four-stimulus cycles. The 61 complete cycles contribute 244 target trials; 45 target trials in 15 incomplete cycles are excluded by the approved revision and listed individually in the JSON. All 289 original target epochs survived voltage rejection: the old 289/320 percentage incorrectly counted smiley and button events in that denominator.

## Figure files

Figure export requires Arial or Helvetica installed on the rendering machine; the plotter stops if neither is available. The published correction uses Arial.

[PDF](../../docs/assets/n100-case-study-corrected.pdf) · [SVG](../../docs/assets/n100-case-study-corrected.svg) · [PNG](../../docs/assets/n100-case-study-corrected.png) · [Caption](../../docs/assets/n100-case-study-corrected.caption.txt)
