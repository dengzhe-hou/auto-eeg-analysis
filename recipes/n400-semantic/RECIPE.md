---
recipe: n400-semantic
version: "v0.1.0"
paradigm: N400 semantic priming — word pairs, unrelated − related centro-parietal negativity
status: validated
min_channels: 16
min_sfreq: 200
min_trials_per_condition: 30
required_markers: [stimulus/related, stimulus/unrelated]
references:
  - "Kutas, M., & Federmeier, K. D. (2011). Thirty years and counting: finding meaning in the N400 component of the event-related brain potential (ERP). Annual Review of Psychology, 62, 621–647."
  - "Kutas, M., & Hillyard, S. A. (1980). Reading senseless sentences: brain potentials reflect semantic incongruity. Science, 207(4427), 203–205."
  - "Kappenman, E. S., et al. (2021). ERP CORE: An open resource for human event-related potential research. NeuroImage, 225, 117465. doi:10.1016/j.neuroimage.2020.117465"
validation_dataset: "ERP CORE N400 (Kappenman 2021, 40 subjects)"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
---

# Recipe: N400 semantic priming (unrelated − related)

> The N400 is a centro-parietal negativity peaking ~300–500 ms that is **larger (more negative)
> for words that are semantically UNRELATED** to their context than for related/expected words
> (Kutas & Hillyard 1980). It indexes the ease of semantic access/integration and is a workhorse
> of language, memory, and clinical ERP research. The signature is the **unrelated − related
> difference wave**, maximal over centro-parietal midline sites (CPz/Cz/Pz).

This is a **group ERP** recipe: the headline is the across-subject grand-average N400 plus a
second-level cluster test — a population-level (N > 1) demonstration, not one subject.

## What this recipe needs

### Data shape
- **Channels:** ≥ 16 (CPz/Cz/Pz mandatory for the centro-parietal maximum).
- **Sampling rate (after resampling):** ≥ 200 Hz.
- **Conditions / markers (REQUIRED):**

  | Condition | Meaning |
  |---|---|
  | related | target word semantically related/expected given the prime |
  | unrelated | target word semantically unrelated/unexpected |

- **Trials:** ≥ 30 related and ≥ 30 unrelated target words per subject after artifact rejection.
- **Time-lock:** the **target** word (not the prime).

### Subjects
- **N recommended:** ≥ 15 for a group second-level cluster test.
- **Group structure:** within-subject (every subject sees both conditions).

## Pipeline

### 1. Preprocess
- Bandpass: 0.1–30 Hz zero-phase FIR (the N400 is a slow component; do not high-pass > 0.5 Hz).
- Average reference; drop EOG channels before referencing.

### 2. ICA (recommended)
- Reading tasks carry blinks/saccades; ICA (or careful rejection) improves single-subject SNR.
  The committed validation uses no ICA (reject=None) to keep the cross-tool benchmark exact.

### 3. Epoch
- −0.2 to 0.8 s relative to target-word onset; baseline −0.2 to 0 s.

### 4. Claims to test

| # | Claim | Contrast | ROI | Window | Test | Direction |
|---|-------|----------|-----|--------|------|-----------|
| C1 | Unrelated targets elicit a larger N400 | unrelated − related | CPz, Cz, Pz | 300–500 ms | second-level spatiotemporal cluster perm, 1-sample, tail=−1 | unrelated more negative |

### 5. Statistics
- Per subject: related and unrelated averages → unrelated − related difference wave.
- Group: second-level spatiotemporal cluster-permutation test (5000 perms, seed 42, one-sided).

### 6. Figures

| # | Figure | Content |
|---|--------|---------|
| F1 | Group N400 | (a) grand-average related/unrelated/difference at CPz/Cz/Pz; (b) N400 topomap at peak; (c) per-subject N400 amplitudes |

## Validated results (server, 2026-06-24)

**Dataset:** ERP CORE N400 (Kappenman 2021), **N = 20**, unrelated − related (target words),
CPz/Cz/Pz, 300–500 ms, 0.1–30 Hz, 256 Hz, average reference, reject=None.

**Sanity check — unrelated targets elicit a larger centro-parietal N400 than related, at the group level: CONFIRMED.**

| Quantity | Value (N = 20) |
|---|---|
| Grand-average N400 (unrelated − related, 300–500 ms) | **−2.957 µV** (SEM 0.466) |
| One-sample t (vs 0) | **t(19) = −6.34, p = 4.4 × 10⁻⁶**, Cohen's dz = −1.42 |
| Second-level spatiotemporal cluster | **1 significant cluster, p = 0.0002** |

Run: `python tools/validation/validate_n400_erpcore_group.py --subjects 20`.
Figure: [archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/n400_erpcore_group.png).
**Cross-tool benchmark:** reproduces MNE-BIDS-Pipeline's per-subject N400 to **≤ 6 nV (CCC = 1.000,
20/20 within ±0.1 µV)** — see [docs/BENCHMARK.md §4f](../../docs/BENCHMARK.md).

## Known limitations
- The N400 is sensitive to word frequency, cloze probability, and repetition — the recipe tests
  the canonical relatedness contrast; carefully matched stimuli are the experimenter's job.
- Centro-parietal ROI is standard but the N400 topography shifts with modality (auditory N400 is
  more anterior); adjust the ROI for spoken-word paradigms.

## Changelog
- v0.1.0 (2026-06-24): initial recipe; validated N=20 on ERP CORE N400 + cross-tool benchmark.
