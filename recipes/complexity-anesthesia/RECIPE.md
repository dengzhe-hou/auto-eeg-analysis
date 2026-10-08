---
recipe: complexity-anesthesia
version: "v0.1.1"
paradigm: EEG signal-complexity tracking of arousal / anesthetic depth (state tracking, no trials)
status: validated   # sanity check (eyes-open > eyes-closed complexity) validated; anesthesia contrast literature-based, untested here
min_channels: 8
min_sfreq: 250
min_duration_s: 60
required_markers: []          # continuous; state labels (awake / sedated / deep) via annotations
references:
  - "Schartner, M., et al. (2015). Complexity of multi-dimensional spontaneous EEG decreases during propofol induced general anaesthesia. PLoS ONE, 10(8), e0133532."
  - "Zhang, X.-S., Roy, R. J., & Jensen, E. W. (2001). EEG complexity as a measure of depth of anesthesia for patients. IEEE Trans. Biomed. Eng., 48(12), 1424–1433."
  - "Bandt, C., & Pompe, B. (2002). Permutation entropy: a natural complexity measure for time series. Physical Review Letters, 88(17), 174102."
  - "Richman, J. S., & Moorman, J. R. (2000). Physiological time-series analysis using approximate and sample entropy. Am. J. Physiol. Heart Circ. Physiol., 278(6), H2039–H2049."
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
distilled_from:
  - "第八届启航班训练营/eight_qihangban/advance_class/complexity_part7 (EEGcomplexity, spatialcomplexity, nonlinear_EEG_analysis code)"
  - "脑电信号处理与特征提取/第十章 (entropy & complexity codes: main_entropy_anesthesia, ComplexityCompute, ...)"
---

# Recipe: EEG Complexity for Arousal / Anesthetic-Depth Tracking

> Signal complexity falls as the brain becomes less responsive: Lempel–Ziv complexity, sample/permutation entropy, and the aperiodic slope all **decrease** from wakefulness → sedation → deep anesthesia, and **increase** again on emergence. This recipe computes a panel of complexity measures over sliding windows of a continuous recording and tracks them against state labels — the canonical use case for the new `eeg-complexity` skill. The built-in validity check is **eyes-open > eyes-closed** complexity in awake subjects; if that ordering is absent, fix the pipeline before trusting any anesthesia contrast.

This is a **state-tracking** recipe: continuous data, no per-trial markers. "Conditions" are time segments (state labels) rather than stimulus events.

## What this recipe needs

### Data shape
- **Channels:** ≥ 8 (complexity is often computed per channel then averaged; frontal coverage matters for anesthesia). Whole-scalp preferred for spatial complexity.
- **Sampling rate (after resampling):** ≥ 250 Hz (entropy parameters assume adequate temporal sampling).
- **Recording:** continuous, **≥ 60 s per state**. Scale-free measures (DFA, 1/f) need **≥ 16 s contiguous** windows.
- **State labels:** provide annotations marking each state (e.g., `awake`, `sedated`, `deep`, `recovery`) or eyes-open / eyes-closed blocks. Without labels the recipe still produces a complexity time-course but cannot test a state contrast.

### Subjects
- **N recommended:** ≥ 10 for a group state-tracking contrast; single-subject within-state tracking is supported and useful for monitoring demos.
- **Group structure:** within-subject **state** contrast (the norm), or between-group.

## Pipeline

### 1. Preprocess
- Bandpass: 0.5–45 Hz zero-phase FIR (broadband — complexity needs the full signal; do NOT narrow-band first). Some measures (e.g., spectral entropy) report per-band as well.
- Notch: 50 / 60 Hz.
- Reference: average (spatial complexity **requires** average reference).
- Bad channels: RANSAC → interpolate → re-reference. Aggressive movement/EMG cleaning matters — EMG inflates complexity.

### 2. ICA
- Extended Infomax + `mne-icalabel`; reject eye / muscle / heart. (Muscle rejection is critical — residual EMG masquerades as high complexity.)

### 3. Windowing (instead of epoching)
- Sliding windows over the continuous record: **5 s window, 3 s overlap** for entropy/LZC; **≥ 16 s** for DFA / aperiodic slope. Use `mne.make_fixed_length_epochs(raw, duration=5.0, overlap=3.0)` per state, baseline=None.
- One complexity vector per window → a time-course; aggregate (median) within each state.

### 4. Complexity measures (via the `eeg-complexity` skill)
Per channel per window, then average across channels (and report spatial complexity across channels):

| Measure | What it captures | Key params | Expected change: deeper anesthesia |
|---|---|---|---|
| Lempel–Ziv complexity (LZC) | signal "randomness"/diversity | median binarization, length-normalized | ↓ |
| Sample entropy (SampEn) | regularity/predictability | m=2, r=0.15–0.2·SD | ↓ |
| Permutation entropy (PE) | ordinal pattern diversity | order=3, normalized | ↓ |
| Spectral / wavelet entropy | flatness of the spectrum | per-band | ↓ |
| Aperiodic exponent (1/f) | excitation/inhibition balance | specparam, ≥16 s | ↑ (steeper) |
| Spatial complexity (Omega / NSC) | # independent spatial patterns | average reference | ↓ |

> Library note: the underlying packages (`antropy`, `neurokit2`, `EntropyHub`, `nolds`) are **optional and not in the default env** — `eeg-complexity` degrades explicitly and tells you which `pip install` is needed. `antropy` cannot set the SampEn tolerance `r`; use `neurokit2`/`EntropyHub` when a specific `r` is required.

### 5. Statistics
- State contrast (within-subject): paired test on per-state median complexity, or a repeated-measures trend across ordered states (`mne.stats.f_mway_rm` / Spearman trend). FDR across the measure panel.
- Report effect direction against the predicted column above; an effect in the wrong direction is a finding, not an error to hide.

### 6. Figures
| Fig | Type | Panels |
|---|---|---|
| F1 | Complexity time-course | each measure vs time, state bands shaded |
| F2 | State summary | per-state median ± SEM bars per measure |
| F3 | Topography | per-channel LZC / SampEn scalp map per state |

## Expected output (validation dataset)
In an awake recording, **eyes-open complexity > eyes-closed** (sanity check). In an anesthesia recording, LZC/SampEn/PE decrease and the aperiodic exponent steepens from awake → deep.

## Validated results (server, 2026-06-19)

**Dataset:** PhysioNet eegbci, **N = 20** subjects, eyes-open (R01) vs eyes-closed (R02), 64 ch, channel-averaged.
**Sanity check — eyes-open > eyes-closed complexity (awake): CONFIRMED for LZC and permutation entropy.**

| Measure | Eyes-open | Eyes-closed | Paired test (N=20) |
|---|---|---|---|
| Lempel–Ziv complexity | **0.520** | 0.473 | t = 5.29, **p = 4.2 × 10⁻⁵**, dz = 1.18 |
| Permutation entropy (order 3) | **0.812** | 0.776 | t = 7.92, **p = 2.0 × 10⁻⁷**, dz = 1.77 |

Figure: [archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/resting_validation.png) (panel B). [Recorded validation script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/validate_resting_recipes.py) (20 subjects).

> **What this validates — and what it does NOT.** The **awake eyes-open > eyes-closed** ordering (eyes-closed alpha makes the signal more regular → lower entropy) is confirmed, which is the recipe's stated gate for promotion. **Crucially, ICA matters:** without ICLabel eye/muscle removal the LZC contrast was noisy and direction-mixed (residual EOG/EMG inflates complexity, exactly as the recipe warns) — it became clean and significant only after ICA. The headline **anesthesia (awake→sedated→deep) contrast is NOT tested here** (no anesthesia data on the server); it remains literature-based (Schartner 2015, Zhang 2001). Spectral entropy did **not** separate the states cleanly (1/f-dominated) and is not headlined. eegbci is 160 Hz / ~61 s/run, resampled to 250 Hz.

### ICA-sensitivity follow-up (audit response, N=20)

[Recorded audit script](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation/audit_followups.py).

Re-running the contrast **without** ICA quantifies the preprocessing dependence the GPT audit flagged:

| Measure | With ICA (p) | **Without** ICA (p) | Verdict |
|---|---|---|---|
| Permutation entropy (order 3) | 2.0×10⁻⁷ | **4.9×10⁻⁶ (still significant)** | **robust → primary measure** |
| Lempel–Ziv (median binarization) | 4.2×10⁻⁵ | **0.59 (collapses)** | ICA-dependent → secondary |

**Take-away:** prefer **permutation entropy** as the headline complexity measure (robust to artifact); **LZC with median binarization is fragile** — its EO>EC effect vanishes without ICA (residual EOG/EMG), so always pair LZC with aggressive ICA/EMG cleaning and report the with/without-ICA sensitivity (Schartner 2015).

## Methods paragraph (for your paper)
```text
[AUTO-GENERATED SKETCH — verify after run]
Continuous EEG (0.5–45 Hz, average reference, ICA-cleaned) was divided into 5 s
sliding windows (3 s overlap). For each window and channel we computed Lempel–Ziv
complexity, sample entropy (m=2, r=0.2·SD), permutation entropy (order 3), spectral
entropy, and the aperiodic 1/f exponent, averaged across channels. State (awake vs
sedated vs deep) effects were tested with repeated-measures statistics and FDR
correction across measures.
```

## Known limitations
- **Optional dependencies** (`antropy`/`neurokit2`/`EntropyHub`/`nolds`/`specparam`) are not installed in the default env; the recipe lists exactly what to `pip install` and degrades per measure.
- Complexity is highly sensitive to residual EMG and to window length / sampling rate — keep these fixed across states and report them.
- The anesthesia directional predictions are well-supported in the literature (Schartner 2015; Zhang 2001) but are population/anesthetic-agent dependent; this recipe ships `experimental` and must be validated on the target montage and agent.

## Changelog
- **v0.1.0** (2026-06-18) — initial release; distilled from the nonlinear-EEG / complexity course module and the 《脑电信号处理与特征提取》 entropy chapter. Not yet server-validated.
