---
recipe: n170-face-inversion
version: 0.1.0
paradigm: N170 face-inversion effect
references:
  - "Rossion, B., Joyce, C. A., Cottrell, G. W., & Tarr, M. J. (2003). Early lateralization and orientation tuning for face, word, and object processing in the visual cortex. NeuroImage, 20(3), 1609–1624. doi:10.1016/j.neuroimage.2003.07.010"
  - "Bentin, S., Allison, T., Puce, A., Perez, E., & McCarthy, G. (1996). Electrophysiological studies of face perception in humans. J Cogn Neurosci, 8(6), 551–565. doi:10.1162/jocn.1996.8.6.551"
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
status: experimental
---

# Recipe: N170 face-inversion effect

The N170 is a negative-going ERP component peaking around 150–200 ms post-stimulus over right lateral occipito-temporal sites (P8/PO8/P10), preferentially elicited by faces compared to other object categories. Inverting the face delays and amplifies the N170 — the **face inversion effect** — taken as evidence for configural face processing. This recipe tests both effects: (a) face vs object N170, and (b) inverted vs upright N170 amplitude.

## What this recipe needs

### Data shape

- **Channels:** at minimum P7, P8, PO7, PO8, P9, P10 (10–20 system extended). 32+ channels recommended for topomaps.
- **Sampling rate (after resampling):** ≥ 250 Hz.
- **Conditions and marker codes (REQUIRED):**
  | Condition | Default marker | Plain meaning |
  |---|---|---|
  | face-upright | 11 | upright face stimulus onset |
  | face-inverted | 12 | inverted (180°) face stimulus onset |
  | object-upright | 21 | upright non-face object onset |
  | object-inverted | 22 | inverted non-face object onset |
- **Trial counts:** ≥ 60 per condition per subject after AutoReject.

### Subjects

- **N recommended:** ≥ 20 for paired-t cluster permutation.
- **Group structure:** within-subject (every subject sees all four conditions).

## Pipeline

### 1. Preprocess
- Bandpass: 0.1 – 30 Hz, zero-phase FIR.
- Notch: 50 Hz (or 60 Hz — infer from country).
- Reference: average of all scalp channels.
- Bad channels: RANSAC (pyprep) + manual review threshold > 4 stdev.

### 2. ICA
- Method: extended Infomax.
- N components: 0.99 variance.
- Auto-label via mne-icalabel; reject eye / muscle / heart / line / channel-noise.
- Pre-fit 1 Hz HP filter copy (best practice).

### 3. Epoch
- Window: −0.2 to 0.6 s.
- Baseline: −0.2 to 0 s.
- AutoReject: local mode.

### 4. Claims to test

| ID | Claim | Contrast | Channels / ROI | Time window | Test | Direction predicted |
|---|---|---|---|---|---|---|
| C1 | Faces elicit larger N170 than objects | face_avg − object_avg | P7, P8, PO7, PO8, P9, P10 | 130 – 200 ms | cluster permutation, paired t | face more negative |
| C2 | Inverted faces elicit larger and later N170 than upright | face_inverted − face_upright | P8, PO8, P10 (right hemisphere bias) | 150 – 250 ms | cluster permutation, paired t | inverted more negative |
| C3 | Inversion effect is face-specific (interaction) | (face_inv − face_up) − (object_inv − object_up) | same as C2 | same as C2 | cluster permutation on interaction | face inversion delta > object inversion delta |

### 5. Statistics
- N permutations: 5000.
- Cluster-forming threshold: derived from p < 0.05 t at the actual df.
- RNG seed: 42.
- Adjacency: channel triangulation from 10–20 standard montage.
- Multiple-comparisons across C1/C2/C3: Bonferroni N=3 → α = 0.0167.

### 6. Figures

| Fig | Type | Panels |
|---|---|---|
| F1 | C1 N170 face vs object | (a) butterfly per condition; (b) difference wave with cluster mask; (c) topomap at peak (~170 ms) |
| F2 | C2 inversion effect | (a) butterfly upright vs inverted face; (b) difference wave; (c) topomap at peak |
| F3 | C3 face-specific inversion | bar plot of inversion delta (face vs object) per subject + group mean ± 95% CI |

## Expected output (predicted — NOT yet validated)

> ⚠️ **Unvalidated predictions, not measured results.** This recipe has **not** been run
> end-to-end on real data on the AEA server: `mne.datasets` ships no upright/inverted-face
> EEG, so the paradigm could not be exercised. The earlier `mne.datasets.kiloword`
> reference was **incorrect** — kiloword is a single-word reading-ERP set and cannot run a
> face/inversion contrast. Correct public validation targets are **OpenNeuro ds000117**
> (Wakeman & Henson 2015; multi-subject famous/unfamiliar/scrambled faces — the canonical
> public face-N170 + repetition-suppression set) or **ds002893**; neither is pure inversion,
> but both exercise the N170 face-selectivity the recipe rests on. The values below are
> literature-derived predictions (Rossion et al. 2003), to be replaced with real numbers once
> run. See the separate [face-selectivity recipe](../n170-faces/RECIPE.md) and its
> [ds000117 validation results](../../tools/validation/n170_faces_results.json).

- C1 (predicted): cluster p < 0.001, peak channel PO8, peak time 158–170 ms, Cohen's dz > 1.0.
- C2 (predicted): cluster p < 0.05 in right hemisphere channels.
- F1 should visually match Rossion et al. (2003) Fig. 2 in shape and lateralization.

## Methods paragraph (for your paper)

```text
[AUTO-GENERATED. Sketch below for verification.]

Continuous EEG was preprocessed with a 0.1–30 Hz zero-phase FIR bandpass and a 50 Hz
notch, re-referenced to the average of all scalp channels. Bad channels were detected
via RANSAC (pyprep 0.4) and interpolated. Independent component analysis (extended
Infomax, n_components=0.99 variance) was fit on a 1-Hz high-pass copy and components
classified by ICLabel as eye, muscle, heart, line-noise, or channel-noise were rejected
(mne-icalabel 0.6). Data were epoched from −0.2 to 0.6 s relative to stimulus onset,
baseline-corrected against −0.2 to 0 s, and trial-level rejection was applied via
AutoReject (autoreject 0.4) with seed 42. Subjects with fewer than 60 retained trials
in any analyzed condition were excluded.

Group-level statistics were computed via cluster permutation (5000 permutations, RNG
seed 42, cluster-forming threshold derived from p<0.05 t at df=N−1, channel-time
adjacency from the 10–20 standard montage triangulation) in MNE-Python 1.7. Three
preregistered claims (face vs object N170, upright vs inverted face N170, and the
face-specific inversion interaction) were tested; multiple-comparisons across claims
used Bonferroni correction (α = 0.0167).
```

## Reproducibility notes

- Re-running on the same data with seed 42 must produce bitwise-identical numerical results.
- Marker code translation: if your data uses different codes, declare the mapping in `DATASET_BRIEF.md > Conditions table`. AEA will translate.

## Known limitations

- Recipe assumes within-subject design. For between-group (e.g., face-blind vs control), modify the test in C2/C3 to independent-sample t.
- Right-hemisphere channel bias is empirical to most adult Western samples; some neurodivergent or developmental populations show different lateralization. Document deviation if your sample is non-standard.
- Recipe does not address EEG–behavioral correlations. Use a separate recipe for that.

## Changelog

- **v0.1.0** (2026-05) — initial release. Three claims.
- **v0.1.1** (2026-06-19) — corrected a false validation claim: the recipe was never validated against `mne.datasets.kiloword` (a reading-ERP set that cannot run a face paradigm). Status remains `experimental`; "Expected output" relabeled as literature predictions pending a real face/inversion dataset.
