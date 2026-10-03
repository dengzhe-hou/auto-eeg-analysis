# DATASET_BRIEF — `<study-name>`

> **Two ways to create this file:**
> 1. **Auto-brief (recommended):** run `python tools/auto_brief.py --raw-dir raw/ --out DATASET_BRIEF.md`. This reads EEG file headers and fills in everything it can (channels, sampling rate, events, format). The agent then asks you only about the remaining `[USER]` fields conversationally.
> 2. **Manual:** copy this template and fill in all fields yourself.
>
> AEA reads this to set defaults for every downstream stage. Fields the agent cannot infer from file headers are marked `[USER]` — the agent must ask about these, not invent them.

## 1. Study identity

- **Study short name:** `<e.g., TCSI-attn-2026>`
- **Paradigm:** `<e.g., Top-Cueing Sustained Inhibition; resting-state-EC; oddball-3stim>`
- **Hypothesis (one sentence):** `<e.g., parietal alpha desync is larger for valid-cue vs invalid-cue trials in 0.4–0.8 s post-cue>`
- **Linked publication / preprint (if any):** `<DOI or arXiv ID>`

## 2. Subjects

- **N enrolled / analyzed:** `<e.g., 32 / 28 (4 excluded — see exclusion criteria below)>`
- **Group structure:** `<single-group | between (control vs patient) | within-subject crossover | …>`
- **Demographics range:** `<age, handedness, sex/gender if relevant>`
- **Exclusion criteria (a priori):** `<list, e.g., >30% epochs rejected; ICA failed to converge; …>`

## 3. Acquisition

- **System:** `<BioSemi ActiveTwo | Brain Products actiCHamp | EGI HydroCel | …>`
- **Channels:** `<e.g., 64 Ag/AgCl, 10–20 montage; 2 EOG (HEOG, VEOG); 2 mastoid>`
- **Sampling rate (raw):** `<e.g., 2048 Hz>`
- **Online filter:** `<e.g., 0.1–100 Hz hardware bandpass; no notch>`
- **Online reference:** `<e.g., CMS/DRL (BioSemi) — re-reference offline>`
- **Channel locations:** `<standard-1020 | individual digitization (.elp/.elc); path>`
- **Marker / trigger source:** `<parallel port | LSL | photodiode>`

## 4. Conditions and trials

| Condition | Marker code | N trials / subject | Notes |
|---|---|---|---|
| `<valid-cue>` | `<11>` | `<120>` | … |
| `<invalid-cue>` | `<12>` | `<40>` | … |

- **Block structure:** `<e.g., 6 blocks × 30 trials, randomized within block>`
- **ITI:** `<e.g., 1.5–2.5 s jittered uniform>`
- **Trial timing:** `<cue onset → ISI 1 s → target → response window 1.5 s>`

## 5. Preprocessing decisions (a priori, NOT after seeing data)

- **Bandpass for analysis:** `<e.g., 0.1–40 Hz, 4th-order zero-phase Butterworth>`
- **Notch:** `<50 Hz | 60 Hz | none>`
- **Re-reference scheme:** `<average | linked-mastoid | REST | …>`
- **Bad channel detection rule:** `<e.g., RANSAC + manual review>`
- **Epoch window:** `<e.g., −0.2 to 1.2 s relative to cue>`
- **Baseline:** `<e.g., −0.2 to 0 s>`
- **Artifact rejection:** `<AutoReject (global / local) | ±100 µV threshold | …>`

## 6. Analyses planned

Tick the ones planned. The matching `eeg-*` skill will run only those.

- [ ] ERP — see `ANALYSIS_PLAN.md` for contrasts
- [ ] Time-frequency (TFR) — bands: `<theta 4–7, alpha 8–13, beta 14–30>`
- [ ] Connectivity — metric: `<wPLI | PLV | coh>` ROI: `<…>`
- [ ] Microstate — k = `<4 | 5 | 6>`
- [ ] Source localization — head model: `<template (fsaverage) | individual MRI>`

## 7. Statistical plan

- **Primary test:** `<cluster permutation, channel × time>`
- **Permutations:** `<5000>`
- **Cluster-forming threshold:** `<t-threshold corresponding to p<0.05>`
- **Multiple-comparisons strategy across analyses:** `<Bonferroni N=k | hierarchical | none — pre-registered>`
- **Effect-size reporting:** `<Cohen's d | partial eta² | …>`

## 8. Backends preferred

- Preprocessing: `<mne (default) | eeglab>`
- ICA: `<mne (mne-icalabel) | eeglab (ICLabel)>`
- Cluster permutation: `<mne | fieldtrip>`
- Microstate: `<pycrostates (default) | eeglab plugin>`
- Source: `<mne+FreeSurfer | export-only-from-Brainstorm>`

## 9. Data location and provenance

- **Raw path:** `<absolute path to read-only raw/>`
- **Format:** `<.bdf | .set | .edf | .fif | .vhdr>`
- **License / consent scope:** `<can it leave the lab machine? can it be uploaded to cloud GPU?>`
- **Backup location:** `<…>`

---

> **For the agent:** if any section above contains `<…>` placeholders when you start, stop and ask the user. Do not infer values from filenames or directory structure.
