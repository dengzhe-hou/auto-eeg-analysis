---
recipe: ern-flankers
version: "v0.1.0"
paradigm: Eriksen Flankers — Error-Related Negativity (ERN) + conflict N2 + frontal theta
status: validated
min_channels: 20
min_sfreq: 256
min_trials_per_condition: 40
required_markers: [stimulus/compatible, stimulus/incompatible, response]
references:
  - "Kappenman, E. S., et al. (2021). ERP CORE: An open resource for human event-related potential research. NeuroImage, 225, 117465. doi:10.1016/j.neuroimage.2020.117465"
  - "Gehring, W. J., et al. (1993). A neural system for error detection and compensation. Psychological Science, 4(6), 385–390."
  - "Cavanagh, J. F., & Frank, M. J. (2014). Frontal theta as a mechanism for cognitive control. Trends in Cognitive Sciences, 18(8), 414–421."
validation_dataset: "ERP CORE Subject-001, Task-Flankers (local converted FIF)"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
---

# Recipe: ERN + Conflict N2 + Frontal Theta (Flankers)

The error-related negativity (ERN) is a negative-going ERP component peaking within 100 ms after an erroneous response at frontocentral sites (FCz/Cz). In the Eriksen Flankers task, incompatible trials have flankers pointing in the opposite direction to the target. This recipe tests stimulus-locked N2, response-locked compatibility, and frontal theta contrasts. Its C2 groups responses by stimulus compatibility, not by response correctness. The separate group ERN validation below uses the canonical error-minus-correct contrast.

This recipe tests three effects:
- **(C1)** Stimulus-locked N2: incompatible > compatible at FCz/Fz/Cz (200–350 ms)
- **(C2)** Response-locked compatibility contrast: incompatible more negative than compatible at FCz/Fz/Cz (0–100 ms)
- **(C3)** Frontal theta power: incompatible > compatible at FCz/Fz/Cz (200–500 ms, 4–8 Hz)

## What this recipe needs

### Data shape

- **Channels:** at minimum FCz, Fz, Cz (10–20 system). 20+ channels recommended for topomaps.
- **Sampling rate (after resampling):** ≥ 256 Hz.
- **Conditions and marker codes (REQUIRED):**

  | Condition | Default event | Plain meaning |
  |---|---|---|
  | compatible_stim | stimulus/compatible/* | compatible flanker stimulus onset |
  | incompatible_stim | stimulus/incompatible/* | incompatible flanker stimulus onset |
  | response | response/* | button press (any) |

  The recipe derives response-locked epochs by finding the most recent stimulus before each response and labeling the response as compatible or incompatible.

- **Trial counts:** ≥ 40 per condition per subject after artifact rejection.

### Subjects

- **N recommended:** ≥ 15 for group-level cluster permutation. Single-subject trial-level analysis is supported but limited.
- **Group structure:** within-subject (every subject sees both compatible and incompatible).

## Pipeline

### 1. Preprocess
- Bandpass: 0.1–30 Hz, zero-phase FIR (30 Hz LP appropriate for ERN and N2).
- Notch: 60 Hz (US) or 50 Hz (EU/Asia) — infer from data or ask user.
- Reference: average of all scalp channels.
- Bad channels: RANSAC (pyprep) if available; otherwise manual list.

### 2. ICA
- Method: extended Infomax.
- N components: 15 (or 0.99 variance if >30 channels).
- Auto-label via mne-icalabel; reject eye / muscle / heart.
- Pre-fit 1 Hz HP filter copy (best practice).

The single-participant case uses ICA, 150 µV peak-to-peak rejection, and the native 1024 Hz data.
The separate N=14 canonical ERN group validation and cross-tool benchmark use the harmonized
minimal configuration: no ICA, `reject=None`, and 256 Hz. These are different analyses.
Use the pinned configuration to reproduce the cross-tool results; see
[`tools/benchmark/SPEC_PRECISION_EVAL.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/SPEC_PRECISION_EVAL.md).

### 3. Epoch
- **Stimulus-locked:** −0.2 to 0.8 s relative to stimulus onset. Baseline: −0.2 to 0 s.
- **Response-locked:** −0.4 to 0.6 s relative to response. Baseline: −0.4 to −0.2 s.
- Artifact rejection: 150 µV peak-to-peak EEG threshold in the reference case.
- Derive response condition (compatible/incompatible) from the preceding stimulus marker.

### 4. Claims to test

| ID | Claim | Contrast | Channels / ROI | Time window | Freq band | Test | Direction predicted |
|---|---|---|---|---|---|---|---|
| C1 | Incompatible elicits larger N2 | incomp_stim − comp_stim | FCz, Fz, Cz | 200–350 ms | n/a | cluster perm, trial-level, tail=-1 | incomp more negative |
| C2 | Incompatible responses are more negative | incomp_resp − comp_resp | FCz, Fz, Cz | 0–100 ms post-resp | n/a | cluster perm, trial-level, tail=-1 | incomp more negative |
| C3 | Frontal theta greater for incompatible | incomp_stim − comp_stim (TFR) | FCz, Fz, Cz | 200–500 ms | 4–8 Hz | cluster perm on theta power, tail=1 | incomp more positive |

### 5. Statistics
- Use every retained trial, without truncating conditions to equal counts or pairing trials by their order.
- Statistic: pooled independent-samples t, incompatible minus compatible; df = n_incompatible + n_compatible − 2.
- Permute compatibility labels within original acquisition block × target-side strata, preserving each stratum's retained condition counts. In Subject-001, the original ten blocks have 40 trials each, ten per compatibility × target-side cell. Original event samples link cached epochs to this structure.
- This assumes conditional exchangeability within the strata. It is not a reconstruction of the original task randomization algorithm, and it is not a population-level test.
- N permutations: 5000, including the observed configuration and 4999 random configurations.
- Cluster-forming threshold: derived from p < 0.05 (one-sided) t at the actual df. This is distinct from the final Bonferroni threshold.
- RNG seed: 42.
- Adjacency: ROI channel triangulation combined with adjacent time samples for C1/C2; adjacent time samples × adjacent frequency bins × ROI channel triangulation for C3. C3 retains all five 4–8 Hz bins and all three ROI channels, without averaging these dimensions before inference.
- Correct for the complete tested domain using maximum cluster mass. Across C1/C2/C3, use Bonferroni N=3: cluster p < 0.05/3 = 0.0166667.
- Report all cluster p-values and all three claims. Report descriptive Cohen's d for every claim using trial-level planned-domain means and pooled within-condition sample variance (ddof=1), regardless of significance.

The saved local analysis plan and its dated repair specification are analysis records, not a formal preregistration.

### 6. Figures

| Fig | Type | Panels |
|---|---|---|
| F1 | Full case study | (a) stimulus-locked ERP at ROI; (b) response-locked compatibility ERP; (c) mean N2-window topomap; (d) TFR difference; (e) theta time course; (f) PSD |

### 7. Time-frequency
- Method: Morlet wavelets, 4–29 Hz, n_cycles = freqs/3, decim=4, zero_mean=True, use_fft=False.
- Baseline: −0.2 to 0 s. Normalize each trial's power separately, then convert to dB with `10 * log10(power / mean_baseline_power)` before averaging trials.
- Use that same per-trial dB quantity in statistics, condition summaries and figures. Log-normalizing condition-averaged power is a different estimand.
- C3 tests the complete 4–8 Hz × 200–500 ms × FCz/Fz/Cz domain.

## Corrected single-participant results (2026-10-04)

The repair reused the historical ICA-cleaned epochs of **ERP CORE Subject-001 Flankers**.
Preprocessing and ICA were not rerun. C1/C3 use 196 compatible and 197 incompatible trials;
C2 uses 196 compatible and 194 incompatible trials. All three original claims were tested.

| Claim | Incompatible − compatible | Pooled Cohen's d | Minimum cluster p | Significant clusters at p < 0.05/3 |
|---|---:|---:|---:|---:|
| C1, stimulus-locked N2 | −0.192431 µV | −0.062090 | 0.0588 | 0 |
| C2, response-locked compatibility | −1.151246 µV | −0.316387 | 0.0006 | 1 |
| C3, frontal theta | +1.278953 dB | +0.295295 | 0.0002 | 1 |

These are trial-level results for one participant. The reported p-values already correct
over each claim's full cluster domain; compare them with 0.05/3 for the additional correction
across claims. The tested arrays contain 154 times × 3 channels for C1, 103 × 3 for C2,
and 77 times × 5 frequencies × 3 channels for C3. Full result and reproduction details are in
[`projects/erp-core-full/REANALYSIS.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.md) and
[`REANALYSIS.json`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/projects/erp-core-full/REANALYSIS.json).

### Run the corrected example

The source project must contain the local converted FIF at `raw/sub-01.fif`. For the
cached-epoch command below, it must also contain the saved stimulus and response FIFs under
`epoch-stage/sub-01/`. Raw EEG and these cached FIFs are not distributed in the Git repository.

```bash
python tools/run_full_case_study.py --project projects/erp-core-full \
  --reuse-epochs --out /tmp/aea-flankers-corrected
python tools/gen_case_study_figures.py --run-dir /tmp/aea-flankers-corrected
```

Choose a new or empty output directory for each run. Omit `--reuse-epochs` to run the
original raw-FIF preprocessing, ICA and epoching configuration as well. The runner preserves
the source project's historical plan and results. Its output contains the summary, all trial
inputs and strata, adjacency, observed cluster maps, every cluster p-value, permutation null,
plotting arrays, methods and findings. The plotting command exports the six-panel figure as
PDF, editable SVG and 600 dpi PNG.

The corrected downstream run took 12.596 s on the recorded environment, excluding preprocessing,
ICA and separate figure rendering. This is not a full-pipeline runtime or a speedup comparison.
The correction is on current development history; the immutable **v0.3.2** release does not
contain this later reanalysis.

### Historical single-participant output (2026-05-23)

The following table preserves the original reported values and verdicts. It is a record of
the previous implementation, not the current corrected evidence. C1/C2 paired equal-length
condition prefixes by order. C3 used uncorrected per-time-point t-tests within its window,
despite the plan specifying a cluster test. Its reported dB values were actually unscaled
log10 power ratios. The historical C2 label “ERN” meant the compatibility contrast.

| Claim | Verdict | Key values |
|-------|---------|-----------|
| C1 (N2) | not supported (Bonferroni) | diff = −0.19 µV, not significant at α=0.017 |
| C2 (historically labeled ERN) | reported supported | diff = −1.15 µV, cluster p reported significant, d = −0.23 |
| C3 (Theta) | reported supported | diff reported as 0.12 dB (unit incorrect), 41/77 significant timepoints, d = 0.20 |

Historical pipeline: 30 EEG channels, 1024 Hz, 0.1–30 Hz FIR, 60 Hz notch, average reference,
ICA 15 components (6 excluded), 393 stimulus epochs and 390 response epochs. The old
documentation reported 94.6 s; no corresponding retained execution-time trace was identified.
That number is preserved as a historical report, not substituted with the downstream repair time.

The old TFR figure normalized power after averaging trials, whereas the old statistical
input normalized each trial first. Their summaries therefore estimated different quantities.
The old trial-based difference, after the ×10 unit correction, was 1.2643586534 dB for the
first 196 trials of each condition. Applying that same selection to the new saved inputs
reproduces it to 3 × 10⁻¹² dB. The corrected 1.2789527859 dB uses all 197 incompatible
trials and all 196 compatible trials. Morlet settings were unchanged.

### N>1 group ERN — canonical error−correct (server, 2026-06-24)

The C2 above uses incompatible−compatible responses (a conflict framing). The **standard** ERN is
**error − correct**, response-locked — validated here as a genuine group effect on ERP CORE ERN
(Kappenman 2021), **N = 14** (6 of 20 subjects excluded for <15 error trials), FCz/Fz/Cz, 0–100 ms
post-response, pre-response baseline (−0.4,−0.2), 0.1–30 Hz, 256 Hz, average ref, reject=None:

| Quantity | Value (N = 14) |
|---|---|
| Grand-average ERN (error − correct, 0–100 ms) | **−5.446 µV** (SEM 0.863) |
| One-sample t (vs 0) | **t(13) = −6.31, p = 2.7 × 10⁻⁵**, Cohen's dz = −1.69 |
| Second-level spatiotemporal cluster | **1 significant cluster, p = 0.0004** |

A large, robust ERN. Run: `python tools/validation/validate_ern_erpcore_group.py --subjects 20`.
**Cross-tool benchmark** (the first *response-locked* one): reproduces MNE-BIDS-Pipeline's per-subject
ERN to **≤ 32 nV (CCC = 1.000, 14/14 within ±0.1 µV)** — see [docs/BENCHMARK.md §4e](../../docs/BENCHMARK.md).

## Methods paragraph (for your paper)

```text
[REFERENCE-CASE METHODS; use the run's generated methods for its exact results]

Continuous EEG was preprocessed with a 0.1–30 Hz zero-phase FIR bandpass and
60 Hz notch, re-referenced to the average of all scalp channels. ICA (extended
Infomax, 15 components, seed 42) was fit on a 1 Hz high-pass copy; ICLabel
classified 3 eye-blink and 3 muscle components for rejection. Stimulus-locked
epochs (-200 to 800 ms) and response-locked epochs (-400 to 600 ms) were
extracted, baseline-corrected, and epochs exceeding 150 µV peak-to-peak EEG
amplitude were rejected. The corrected downstream run reused these epochs.

Three contrasts fixed in a local analysis plan were tested at FCz/Fz/Cz:
stimulus N2, response-locked compatibility, and frontal theta. All retained
trials entered pooled independent-samples t statistics. Compatibility labels
were permuted within block-by-target-side strata, retaining each stratum's
condition counts (5000 permutations, seed 42). Cluster-forming p was 0.05
one-sided; final cluster p was compared with 0.05/3 across the three claims.
C3 retained its full time-by-frequency-by-electrode domain. Power was converted
to dB after per-trial baseline normalization and before averaging. This is
conditional trial-level inference for one participant, not population inference.
```

## Known limitations

- Single-subject demo: C1 (N2) may not reach significance with N=1 and Bonferroni. With N≥15, the N2 effect is robust in published literature.
- Response-locked epoching requires stimulus→response pairing logic (the recipe handles this automatically).
- Theta TFR requires epoch length > wavelet length at 4 Hz — n_cycles capped at freqs/3 for safety.

## Changelog

- **2026-10-04 correction**: all-trial block-by-target-side permutation, full-domain C3 cluster correction, consistent per-trial dB, pooled descriptive effect sizes, and retained historical records. This update is after the immutable AEA v0.3.2 release.
- **v0.1.0** (2026-05-23): initial release and the historical three-claim case-study results preserved above.
