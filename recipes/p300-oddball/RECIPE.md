---
recipe: p300-oddball
version: 0.1.0
paradigm: P300 auditory or visual oddball
references:
  - "Polich, J. (2007). Updating P300: An integrative theory of P3a and P3b. Clinical Neurophysiology, 118(10), 2128–2148. doi:10.1016/j.clinph.2007.04.019"
  - "Donchin, E., & Coles, M. G. H. (1988). Is the P300 component a manifestation of context updating? Behavioral and Brain Sciences, 11(3), 357–374."
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
status: experimental
---

# Recipe: P300 oddball (target vs standard)

The P300 is a positive-going ERP component peaking 300–500 ms post-stimulus over centro-parietal sites (Cz/Pz/CPz), elicited by **rare/target** stimuli embedded in a stream of frequent/standard stimuli. P300 amplitude scales with attention allocated to the target; latency reflects stimulus evaluation time. This recipe tests the canonical target − standard amplitude difference (P3b) and produces topography + latency tables.

## What this recipe needs

### Data shape

- **Channels:** at minimum Fz, Cz, Pz, CPz (10–20 system midline). 32+ channels recommended for full topomaps.
- **Sampling rate (after resampling):** ≥ 250 Hz.
- **Conditions and marker codes (REQUIRED):**
  | Condition | Default marker | Plain meaning |
  |---|---|---|
  | target | 1 | rare target stimulus (count or button press) |
  | standard | 2 | frequent standard stimulus (ignore) |
  | distractor | 3 | OPTIONAL — rare non-target distractor (P3a) |
- **Trial counts:** ≥ 30 target, ≥ 100 standard per subject after AutoReject.
- **Probability:** target 0.10–0.30; standard 0.70–0.90.

### Subjects

- **N recommended:** ≥ 16 for paired-t cluster permutation (P3b is large and robust).
- **Group structure:** typically within-subject; between-group comparison (e.g., patient vs control) supported via override.

## Pipeline

### 1. Preprocess
- Bandpass: 0.1 – 30 Hz, zero-phase FIR. (P3 has slow rise; do NOT use HP > 0.5 Hz.)
- Notch: 50 / 60 Hz inferred.
- Reference: average of all scalp channels.
- Bad channels: RANSAC + manual review.

### 2. ICA
- Method: extended Infomax.
- N components: 0.99 variance.
- Auto-label via mne-icalabel; reject eye / muscle / heart / line / channel-noise.

> ⚠️ **Numerical-specification note.** The **"Validated results" below were produced WITHOUT ICA and
> without peak-to-peak rejection** (`reject=None`), resampled to 256 Hz — the *harmonized minimal*
> configuration used for the cross-tool benchmark. Running the ICA step prescribed above is good
> practice for real analyses but will **not** reproduce the certified numbers. To reproduce them, use
> the pinned configuration. See [`tools/benchmark/SPEC_PRECISION_EVAL.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/SPEC_PRECISION_EVAL.md).

### 3. Epoch
- Window: −0.2 to 0.8 s.
- Baseline: −0.2 to 0 s.
- AutoReject: local. Subjects retaining < 30 target trials are excluded for P3 analyses.

### 4. Claims to test

| ID | Claim | Contrast | Channels / ROI | Time window | Test | Direction predicted |
|---|---|---|---|---|---|---|
| C1 | Targets elicit larger P300 than standards | target − standard | Fz, Cz, Pz, CPz | 300 – 500 ms | cluster permutation, paired t | target more positive |
| C2 | P3b is parietally maximal | target − standard, restricted to parietal | Pz, CPz, P3, P4 | 350 – 500 ms | cluster permutation, paired t | target more positive |
| C3 | (OPTIONAL, requires distractor condition) P3a frontal vs P3b parietal | distractor − standard at Fz vs target − standard at Pz | Fz vs Pz | 250 – 400 ms (P3a) vs 350 – 500 ms (P3b) | within-subject ANOVA (component × electrode) | P3a frontal max, P3b parietal max |

### 5. Statistics
- N permutations: 5000.
- Cluster-forming threshold: derived from p < 0.05 t at actual df.
- RNG seed: 42.
- Adjacency: channel triangulation from 10–20 montage.
- Multiple-comparisons across C1/C2 (and C3 if present): Bonferroni.

### 6. Figures

| Fig | Type | Panels |
|---|---|---|
| F1 | C1 target vs standard ERP | (a) butterfly per condition; (b) difference wave at Pz with cluster mask; (c) topomap at peak (~400 ms) |
| F2 | C2 P3b parietal topography | spline-interpolated topomap series 250→500 ms in 50 ms steps |
| F3 | (optional) P3a vs P3b dissociation | dual-line plot Fz vs Pz for distractor and target |

## Validated results (server, 2026-06-24)

**Dataset:** ERP CORE P3 (Kappenman 2021), active visual oddball, **N = 20** subjects,
target − standard (target = trials where the shown letter is the block target; ~20%),
30 EEG ch resampled to 256 Hz, average reference, no peak-to-peak rejection / no ICA
(harmonized minimal pipeline; see the benchmark note below).

**Sanity check — centro-parietal target−standard P3b, significant at the group level: CONFIRMED.**

| Quantity | Value (N = 20) |
|---|---|
| Grand-average P3b (Fz/Cz/Pz/CPz, 300–500 ms) | **+1.683 µV** (SEM 0.405) |
| One-sample t (vs 0) | **t(19) = +4.15, p = 5.4 × 10⁻⁴**, Cohen's dz = +0.93 |
| **Second-level spatiotemporal cluster** (5000 perms, seed 42, one-sided) | **1 significant cluster, p = 0.0002** |

Run: `python tools/validation/validate_p3_group.py --subjects 20`. Figure:
[archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/p3_group.png). (The earlier `mne.datasets.eegbci` reference was
**incorrect** — eegbci is a motor-imagery set with no oddball stream; this validation uses the
correct ERP CORE P3 oddball.)

**Cross-tool numeric benchmark:** the recipe's reference implementation reproduces MNE-BIDS-Pipeline's per-subject
P3b to **≤ 0.5 nV (CCC = 1.000, 20/20 within ±0.1 µV)** on the same data — see
[docs/BENCHMARK.md §4c](../../docs/BENCHMARK.md). With all epochs averaged (reject=None) both tools
average the identical trial set, so agreement is at the floating-point floor.

## Methods paragraph (for your paper)

```text
[AUTO-GENERATED. Sketch:]

Continuous EEG was bandpass filtered 0.1–30 Hz (zero-phase FIR), notch filtered at
50 Hz, re-referenced to the average of all scalp channels, and bad channels
(RANSAC, pyprep 0.4) interpolated. Independent component analysis (extended Infomax,
n_components=0.99 variance) on a 1-Hz HP copy was used with mne-icalabel for automatic
artifact-component rejection. Data were epoched from −0.2 to 0.8 s, baseline-corrected
against −0.2 to 0 s, and trial-level rejection applied via AutoReject (seed 42).
Subjects retaining fewer than 30 target trials were excluded.

P300 amplitude (target − standard contrast) was tested with cluster permutation (5000
permutations, RNG seed 42, cluster-forming threshold from p<0.05 t at df=N−1, 10–20
montage triangulation adjacency). Two preregistered claims (target vs standard P3 over
midline; parietal maximum) were Bonferroni-corrected.
```

## Reproducibility notes

- P300 is robust; recipe should reproduce across most acquisition systems.
- Marker convention: if your task has multiple target categories (color × shape oddball), declare them as targets in DATASET_BRIEF.

## Known limitations

- Recipe assumes a single-feature oddball (target vs standard). Multi-feature oddball needs custom handling.
- Eye-blink artifacts at Fz can bias frontal P3a measurement if ICA is too aggressive — review excluded components for this paradigm.
- Recipe does not implement single-trial classification; use the BCI-classification recipe (planned) for that.

## Changelog

- **v0.1.0** (2026-05) — initial release.
