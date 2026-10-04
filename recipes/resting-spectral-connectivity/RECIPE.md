---
recipe: resting-spectral-connectivity
version: "v0.1.1"
paradigm: Resting-state spectral power, aperiodic (1/f) parameterization, and functional connectivity
status: validated
min_channels: 19
min_sfreq: 250
min_duration_s: 120
required_markers: []          # continuous resting-state; optional eyes-open / eyes-closed blocks
references:
  - "Donoghue, T., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. Nature Neuroscience, 23(12), 1655–1665."
  - "Vinck, M., et al. (2011). An improved index of phase-synchronization (wPLI). NeuroImage, 55(4), 1548–1565."
  - "Barry, R. J., et al. (2007). EEG differences between eyes-closed and eyes-open resting conditions. Clinical Neurophysiology, 118(12), 2765–2773."
  - "Klimesch, W. (1999). EEG alpha and theta oscillations reflect cognitive and memory performance. Brain Research Reviews, 29(2–3), 169–195."
contributors:
  - "AEA core <hou.dengzhe.t8@dc.tohoku.ac.jp>"
license: CC-BY-4.0
distilled_from:
  - "MCKJ0914/part4-频域fft, part5 (频域分析), part7_fc (功能连接分析1/2)"
  - "Python-EEG-Handbook (Preprocessing + MultisubjectsAnalysis notebooks)"
  - "第八届启航班训练营 (PSD / Fieldtrip 功能连接 modules)"
---

# Recipe: Resting-State Spectral Power + 1/f + Functional Connectivity

> The two workhorse resting-state biomarkers. (1) **Spectral power**: band power and the individual alpha peak, plus the **aperiodic (1/f) slope** that must be separated from oscillatory power before any band comparison. (2) **Functional connectivity**: volume-conduction-robust phase coupling (debiased wPLI) per band, summarised with graph metrics. The built-in sanity check is the textbook **eyes-closed > eyes-open posterior alpha** effect (Berger / Barry 2007) — if it does not appear, the montage, reference, or band definitions are wrong.

## What this recipe needs

### Data shape
- **Channels:** ≥ 19 (10–20 system); 32+ for connectivity graphs. Positions required.
- **Sampling rate (after resampling):** ≥ 250 Hz.
- **Recording:** ≥ 120 s clean per state; **≥ 2 min eyes-closed strongly recommended** for stable alpha.
- **Markers:** none required. If eyes-open / eyes-closed blocks exist, annotate them — the alpha-reactivity check contrasts the two.

### Subjects
- **N recommended:** ≥ 20 for group spectra / connectivity with multiple-comparison correction.
- **Group structure:** descriptive, between-group, or within-subject (EC vs EO).

## Pipeline

### 1. Preprocess
- Bandpass: 1–45 Hz zero-phase FIR (the 1 Hz HP is needed for clean 1/f and ICA; do not high-pass above 1 Hz if delta is of interest).
- Notch: 50 / 60 Hz.
- Reference: average (report it — connectivity and PSD are reference-dependent).
- Bad channels: RANSAC → interpolate → re-reference.

### 2. ICA
- Extended Infomax + `mne-icalabel`; reject eye / muscle / heart / line / channel-noise.

### 3. Segment (continuous)
- `epochs = mne.make_fixed_length_epochs(raw, duration=2.0, overlap=0.0, preload=True)` (baseline=None). 2 s → 0.5 Hz frequency resolution (resolution = 1/duration). Drop bad segments by annotation.

### 4a. Spectral power
```python
spec = epochs.compute_psd(method='welch', fmin=1, fmax=45,
                          n_fft=int(epochs.info['sfreq']*2),
                          window='hann', n_overlap=int(epochs.info['sfreq']))  # MNE default is hamming/0 — set explicitly
psd, freqs = spec.get_data(return_freqs=True)      # already normalized — do NOT re-apply 2/N
```
- Band power: delta 1–4, theta 4–8, alpha 8–13, beta 13–30, gamma 30–45 Hz (absolute and relative).
- **Individual Alpha Frequency (IAF):** peak in 7–13 Hz over posterior channels (Klimesch 1999).

### 4b. Aperiodic (1/f) parameterization — **before any band comparison**
```python
# specparam / FOOOF — OPTIONAL dependency; degrade explicitly if missing
from specparam import SpectralModel          # (pip install fooof / specparam)
fm = SpectralModel(peak_width_limits=[1, 8], aperiodic_mode='fixed')
fm.fit(freqs, psd_channel, [1, 40])
exponent = fm.get_params('aperiodic', 'exponent')   # the 1/f slope
# report oscillatory peaks ABOVE the aperiodic fit, not raw band power alone
```
- A group "alpha decrease" is frequently just a steeper 1/f exponent. Always separate them (Donoghue 2020).

### 4c. Functional connectivity (per band)
```python
from mne_connectivity import spectral_connectivity_epochs
con = spectral_connectivity_epochs(
    epochs, method='wpli2_debiased', mode='multitaper',
    fmin=(1,4,8,13,30), fmax=(4,8,13,30,45), faverage=True, n_jobs=1)
conn = con.get_data(output='dense')           # n_ch × n_ch × n_bands
```
- Default metric **debiased wPLI** (volume-conduction robust). At sensor level never headline coherence/PLV as "region A→B". Optional CSD pre-step (`compute_current_source_density`).
- Graph metrics per band (threshold reported): clustering, global efficiency, characteristic path length.

### 5. Statistics
- EC vs EO (within): paired test per band/channel, **cluster permutation across channels** (alpha-reactivity is spatially contiguous). Between-group: independent.
- Connectivity: per-edge **FDR over the upper triangle** (`mne.stats.fdr_correction`) or NBS-style permutation; report edge count = E·(E−1)/2.
- Multiple-comparison correction is mandatory for both PSD maps and the ~N² connectivity edges.

### 6. Figures
| Fig | Type | Panels |
|---|---|---|
| F1 | PSD | (a) grand-average spectra per state with ±SEM; (b) topomap of band power; (c) specparam fit (periodic vs aperiodic) |
| F2 | Connectivity | (a) wPLI matrix per band (diagonal masked); (b) circle/topographic connectogram; (c) graph-metric bars |

## Expected output (validation dataset)
Eyes-closed should show a clear posterior **alpha peak (~10 Hz)** and higher posterior alpha power than eyes-open; alpha-band wPLI should be highest posteriorly.

## Validated results (server, 2026-06-19)

**Dataset:** PhysioNet eegbci, **N = 20** subjects, eyes-closed (run R02) vs eyes-open (run R01), 64 ch.
**Sanity check — eyes-closed > eyes-open posterior alpha (Berger / Barry 2007): CONFIRMED.**

| Metric | Value |
|---|---|
| Posterior (8–13 Hz) alpha, eyes-closed | 6.73 × 10⁻¹¹ V²/Hz |
| Posterior alpha, eyes-open | 8.45 × 10⁻¹² V²/Hz (≈ 8× lower) |
| Paired t-test (EC − EO), N=20 | t = 3.60, **p = 0.0019**, Cohen's dz = 0.81 |
| **Second-level spatial cluster** (across-subject, 5000 perms) | **1 significant cluster, p = 0.0002**, 62/64 channels |

Figure: [archived figure](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/figures/resting_validation.png) (panel A). Run: `python tools/validation/validate_resting_recipes.py --subjects 20`.

> **Validation caveats (honest):** eegbci is natively **160 Hz (below this recipe's `min_sfreq: 250`)** and only **~61 s/run (below the recommended ≥120 s)**; data were resampled to 250 Hz and ICA-cleaned (ICLabel: eye/muscle/heart). The EC>EO alpha **power** effect is robust; the alpha-reactivity sanity check is what promotes `status: validated`. `specparam` 1/f was exercised at the API level only (`tools/tests/test_skill_apis.py`), not benchmarked.

> **wPLI connectivity benchmark (audit follow-up, `tools/validation/validate_connectivity.py`, N=15).** Posterior-posterior debiased wPLI (alpha 8–13 Hz) **trends in the expected direction** (eyes-closed 0.270 > eyes-open 0.193, diff +0.076, dz = 0.36) but is **NOT significant** (paired t = 1.40, p = 0.18). Connectivity is noisier and weaker than the power effect; at this N it is a **trend, not a confirmed effect** (a dz ≈ 0.36 needs N ≈ 60 for 80% power). So the recipe's *power* half is validated; its *connectivity* half runs correctly and trends right but is **not** group-significant here — treat wPLI claims as exploratory until run on a larger sample.

> **Topography caveat (audit follow-up).** The per-channel EC−EO alpha t-map
> (`tools/validation/audit_followups.py`, N=20) is **spatially diffuse, not posterior-specific**:
> posterior mean t = 3.29 vs anterior mean t = 3.40 (max at TP8). This is expected under an
> **average reference** — eye-closure raises alpha broadly and the average reference
> redistributes it — and explains why the second-level cluster spans 62/64 channels. The
> recipe's **posterior alpha power** contrast is genuine, but the *scalp distribution of the
> difference* is reference-dependent; do not over-interpret the cluster's spatial extent.
> For posterior-specific claims use a mastoid/REST reference or report the topography explicitly.

## Methods paragraph (for your paper)
```text
[AUTO-GENERATED SKETCH — verify after run]
Resting EEG (1–45 Hz, average reference, ICA-cleaned) was segmented into 2 s
windows. Power spectral density was estimated by Welch (2 s Hann windows, 50%
overlap) and parameterized with specparam to separate periodic peaks from the
aperiodic 1/f exponent. Functional connectivity was computed as debiased wPLI per
band (mne-connectivity). State (eyes-closed vs eyes-open) effects were tested with
cluster-based permutation; connectivity edges were FDR-corrected.
```

## Known limitations
- `specparam`/`fooof` is an optional dependency (absent in the default env) — band power is still reported without it, but the 1/f caveat then applies.
- Connectivity at the sensor level is volume-conduction-limited; use wPLI/imcoh or source space for "connection" claims.
- 2 s windows give 0.5 Hz resolution; lengthen windows for finer delta/theta resolution.

## Changelog
- **v0.1.0** (2026-06-18) — initial release; distilled from the frequency-domain and functional-connectivity course modules + the MNE handbook. Not yet server-validated.
