---
recipe: mmn-oddball
version: "v0.1.0"
paradigm: Auditory Mismatch Negativity (MMN) — passive oddball, deviant − standard frontocentral negativity
status: validated
min_channels: 16
min_sfreq: 200
min_trials_per_condition: 50
required_markers: [stimulus/standard, stimulus/deviant]
references:
  - "Näätänen, R., Paavilainen, P., Rinne, T., & Alho, K. (2007). The mismatch negativity (MMN) in basic research of central auditory processing: a review. Clinical Neurophysiology, 118(12), 2544–2590."
  - "Garrido, M. I., Kilner, J. M., Stephan, K. E., & Friston, K. J. (2009). The mismatch negativity: a review of underlying mechanisms. Clinical Neurophysiology, 120(3), 453–463."
  - "Kappenman, E. S., et al. (2021). ERP CORE: An open resource for human event-related potential research. NeuroImage, 225, 117465. doi:10.1016/j.neuroimage.2020.117465"
validation_dataset: "mne.datasets.erp_core (Task-MMN, 40 subjects)"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
---

# Recipe: Auditory Mismatch Negativity (MMN)

> The MMN is a pre-attentive, frontocentral negativity peaking ~100–250 ms after a rare
> "deviant" sound embedded in a stream of repeated "standards" — it indexes the brain's
> automatic detection of a change against a sensory-memory regularity (Näätänen 2007). It is
> elicited passively (no task), is robust across subjects, and is a leading biomarker in
> schizophrenia, coma/consciousness, and developmental research. The signature is the
> **deviant − standard difference wave**, maximal at Fz/FCz, that inverts at the mastoids.

This is a **group ERP** recipe: the headline result is the across-subject grand-average MMN
plus a second-level cluster test — it is the canonical demonstration that a result holds at
the **population** level (N > 1), not just one subject.

## What this recipe needs

### Data shape
- **Channels:** ≥ 16 (Fz/FCz/Cz mandatory; mastoids M1/M2 or P9/P10 useful to show inversion).
- **Sampling rate (after resampling):** ≥ 200 Hz.
- **Conditions / markers (REQUIRED):**

  | Condition | Meaning |
  |---|---|
  | standard | the frequent repeated tone (~80–90% of trials) |
  | deviant | the rare tone differing in pitch, intensity, duration, or location |

- **Trials:** ≥ 50 deviants and ≥ 150 standards per subject after artifact rejection.

### Subjects
- **N recommended:** ≥ 15 for a group second-level cluster test; the MMN is reliable so even
  N ≈ 10 often suffices.
- **Group structure:** within-subject (every subject hears both streams).

## Pipeline

### 1. Preprocess
- Bandpass: 0.1–30 Hz zero-phase FIR (MMN is a slow frontocentral component).
- Reference: average of scalp channels (or linked mastoids — report which; mastoid reference
  makes the polarity inversion explicit but changes amplitudes).
- Drop dedicated EOG channels before referencing (do not average them into the reference).
- Bad channels: RANSAC → interpolate → re-reference. **OPTIONAL — and it moves the result.**

> ⚠️ **Numerical-specification note (added 2026-07 after the §6f generation eval).** The
> **"Validated results" below were produced WITHOUT RANSAC**, resampled to **256 Hz**, no ICA — the
> *harmonized minimal* configuration. Running RANSAC as written rescues two otherwise-excluded
> subjects (**n = 40 instead of 38**) and shifts the grand mean to **−0.822 µV**. Both are defensible
> analyses; they are **not the same number**. To reproduce the certified values, use the pinned
> configuration: no RANSAC, no ICA, resample 256 Hz, peak-to-peak 100 µV, window edges inclusive
> (`0.100 ≤ t ≤ 0.250`). See [`tools/benchmark/RECIPE_GENERATION_EVAL.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/RECIPE_GENERATION_EVAL.md).

### 2. ICA (optional for clean passive data)
- For high-EOG datasets, extended Infomax + `mne-icalabel` (reject eye/muscle). ERP CORE MMN
  is clean enough that a simple ±100 µV epoch reject suffices; document whichever you use.

### 3. Epoch
- −0.2 to 0.5 s relative to stimulus onset; baseline −0.2 to 0 s.
- Artifact rejection: ±100 µV (MMN is small; keep the threshold tight).

### 4. Claims to test

| ID | Claim | Contrast | ROI | Window | Test | Direction |
|----|-------|----------|-----|--------|------|-----------|
| C1 | Deviants elicit an MMN | deviant − standard | Fz, FCz, Cz | 100–250 ms | second-level (across-subject) spatiotemporal cluster perm, 1-sample, tail=−1 | deviant more negative |

### 5. Statistics
- Per subject: average standard and deviant, form the deviant − standard difference wave.
- Group: **second-level** `spatio_temporal_cluster_1samp_test` on the per-subject difference
  (subjects × times × channels), 5000 permutations, seed 42, one-sided (negative).
- This is the level that licenses a population claim; a single-subject difference wave does not.

### 6. Figures
| Fig | Type | Panels |
|---|---|---|
| F1 | Group MMN | (a) grand-average deviant/standard/difference at FCz with ±SEM; (b) MMN topomap at peak; (c) per-subject MMN amplitudes |

## Validated results (server, 2026-06-19; re-run 2026-06-24 with the recipe's ≥50/≥150 trial guard)

**Dataset:** ERP CORE MMN (`mne.datasets.erp_core`, Task-MMN), **N = 40** subjects,
deviant (70 dB) − standard (80 dB), 33→30 EEG ch resampled to 256 Hz, average reference.

**Sanity check — frontocentral deviant−standard MMN, significant at the group level: CONFIRMED.**

| Quantity | Value (N = 38; sub-007 and sub-012 dropped for < 50 deviants) |
|---|---|
| Grand-average MMN (Fz/FCz/Cz, 100–250 ms) | **−0.840 µV** (SEM 0.107) |
| One-sample t (vs 0) | **t(37) = −7.87, p = 2.0 × 10⁻⁹**, Cohen's dz = −1.28 |
| **Second-level spatiotemporal cluster** (5000 perms, seed 42, one-sided) | **1 significant cluster, p = 0.0002** |

This is a population-level (N > 1) result: the MMN is significant across subjects, not just
in one recording. ICA was not used (passive ERP CORE data is clean; ±100 µV reject sufficed).
The trial-count guard (≥ 50 deviants, ≥ 150 standards) matches the `## What this recipe needs`
spec above; it drops the two subjects whose retained-deviant counts fall short (11 and 47).
An independent cross-tool benchmark reproduces this −0.840 µV to ~3 nV — see the [benchmark record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/docs/BENCHMARK.md).

Figure: [archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/mmn_group.png). [Recorded validation script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/validate_mmn_group.py) (40 subjects).

## Methods paragraph (for your paper)
```text
[AUTO-GENERATED SKETCH — verify after run]
Passive auditory oddball EEG (0.1–30 Hz, average reference) was epoched −200 to 500 ms
around standard and deviant tones (baseline −200 to 0 ms, ±100 µV rejection). Per subject,
standard and deviant ERPs were averaged and a deviant-minus-standard difference wave formed.
The mismatch negativity was tested across subjects with a second-level spatiotemporal
cluster-permutation test (5000 permutations, seed 42, one-sided) at Fz/FCz/Cz, 100–250 ms.
```

## Known limitations
- The deviant/standard mapping is paradigm-specific (intensity, pitch, duration, location
  deviants all elicit MMN but with different scalp foci); set `required_markers` to your stream.
- Average reference spreads the frontocentral negativity; mastoid reference shows the classic
  inversion but is sensitive to mastoid placement.
- Refractoriness confounds: a "genuine" MMN controls for the standard/deviant physical
  difference with a reverse-control or roving paradigm; the simple deviant−standard wave
  includes an adaptation component.

## Changelog
- **v0.1.0** (2026-06-19) — initial release; validated end-to-end on ERP CORE MMN (N=40).
