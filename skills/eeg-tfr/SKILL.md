---
name: eeg-tfr
description: "Compute time-frequency representations (Morlet wavelets, multitaper, or Stockwell) and inter-trial coherence per subject per condition. Reads epoch-stage/ output. Backend: MNE-Python. Use when user says 'compute TFR', 'time-frequency', 'ERSP', 'wavelet', 'ITC', or after eeg-epoch completes."
argument-hint: "[project-dir] [— method: morlet|multitaper|stockwell] [— bands: theta,alpha,beta] [— baseline_mode: logratio|zscore|db|percent]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# eeg-tfr: epochs → time-frequency

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **METHOD = `morlet`** — Alternatives: `multitaper`, `stockwell`.
- **FREQS = `np.arange(2, 40, 1)`** unless DATASET_BRIEF specifies bands explicitly.
- **N_CYCLES = `freqs / 2`** — Standard adaptive cycle count (Cohen 2014). Override: `— n_cycles: 7` for fixed.
- **DECIM = `4`** — Temporal decimation to reduce file size. Override: `— decim: 2`.
- **BASELINE = `(-0.5, -0.1)`, mode = `logratio`** — Prefer `logratio` or `db` over `percent` (Grandchamp & Delorme 2011). Override: `— baseline_mode: zscore`.
- **OUTPUT_DIR = `tfr-stage/`** — Create if missing.
- **OUTPUT_FORMAT = `tfr-stage/<sub>/<sub>-<cond>-tfr.h5`** — HDF5 (fif does not handle 4-D TFR well).
- **ITC_OUTPUT = `tfr-stage/<sub>/<sub>-<cond>-itc.h5`** — Inter-trial coherence, saved separately.

> Override: `/eeg-tfr projects/my-study — method: multitaper — bands: theta,alpha — baseline_mode: db`

## Required Inputs

Before running, these must exist:

1. `epoch-stage/` — epoched data per subject (`*-epo.fif`). **Stop if missing.**
2. `DATASET_BRIEF.md` — for condition labels, frequency bands of interest, epoch window.
3. `ANALYSIS_PLAN.md` — if TFR claims exist, read frequency bands, time windows, and ROI from the claim table.
4. `ENVIRONMENT.json` — to resolve backend availability.

## Phase A — Parameter Resolution

1. Read `DATASET_BRIEF.md` for:
   - Epoch time window (needed to check edge artifact margin).
   - Frequency bands of interest (e.g., theta 4–8 Hz, alpha 8–13 Hz, beta 13–30 Hz).
   - Sampling rate after decimation during epoching.
2. Read `ANALYSIS_PLAN.md` claim table for TFR-specific claims:
   - Extract `freq_band`, `time_window`, `baseline` per claim.
   - Ensure requested frequencies fall within `FREQS`.
3. Resolve `n_cycles`:
   - **Adaptive** (default): `n_cycles = freqs / 2`. This gives ~3 cycles at 6 Hz (good temporal resolution) and ~20 cycles at 40 Hz (good frequency resolution).
   - **Fixed**: use when comparing across frequencies at matched temporal resolution. Typical: 5–7 cycles.
   - **Logarithmic**: `n_cycles = np.logspace(np.log10(3), np.log10(12), len(freqs))` for compromise.

### Report wavelets by FWHM, not just `n_cycles` (Cohen 2019)

`n_cycles` is the MNE knob, but it is **not** the most interpretable or reproducible way to *describe* a wavelet. Cohen (2019) recommends reporting the **full-width at half-maximum (FWHM)** of the wavelet's Gaussian in **time (ms)** and its dual in **frequency (Hz)** — these are directly readable as "what temporal/spectral smoothing did you apply" and don't depend on the reader re-deriving `sigma_t`. Convert and report both:

```
sigma_t  = n_cycles / (2 * np.pi * f)        # Gaussian std (s)
fwhm_t   = sigma_t * 2 * np.sqrt(2*np.log(2))  # = sigma_t * 2.355  → time FWHM (s)
fwhm_f   = (2 * np.sqrt(2*np.log(2))) / (2 * np.pi * sigma_t)  # frequency FWHM (Hz)
```

So an adaptive `n_cycles = f/2` gives a **constant** time-FWHM of `2.355 / (4*pi) ≈ 187 ms` at every frequency (a useful sanity check). When you build wavelets directly, Cohen's FWHM-Gaussian is `exp(-4*ln(2) * t**2 / fwhm_t**2)`. **COBIDAS:** report the FWHM-time at your lowest and highest frequency, not only `n_cycles`. Cite: Cohen, M. X. (2019). A better way to define and describe Morlet wavelets for time-frequency analysis. *NeuroImage*, 199, 81–86.

### Choosing `n_cycles` — the time/frequency tradeoff (worked numbers)

MNE has **no default** `n_cycles`; it is a first-class scientific choice, not a hidden knob. The Morlet wavelet is a Gaussian-tapered complex sine whose temporal Gaussian std is:

```
sigma_t = n_cycles / (2 * pi * f)        # seconds (Gaussian std)
sigma_f = f / (2 * pi * n_cycles)        # Hz   (spectral std; sigma_t*sigma_f = 1/(4*pi))
```

The **effective temporal support** (where the wavelet has non-negligible amplitude) is `~ n_cycles / f` seconds — it *shrinks with frequency* for a fixed `n_cycles`. Worked table for a fixed `n_cycles = 3`:

| f (Hz) | support `n_cycles/f` (s) | sigma_t (ms) | sigma_f (Hz) |
|---|---|---|---|
| 1  | 3.00 | 477 | 0.05 |
| 2  | 1.50 | 239 | 0.11 |
| 4  | 0.75 | 119 | 0.21 |
| 10 | 0.30 | 48  | 0.53 |
| 30 | 0.10 | 16  | 1.59 |

Reading the table: a small fixed `n_cycles` (e.g. 3) buys sharp **temporal** localization (good for transient ERD/ERS onsets) at the cost of poor **frequency** resolution; raising it (e.g. 7) reverses the trade. The AEA default `n_cycles = freqs / 2` is the adaptive compromise — it fixes `sigma_t` and `sigma_f` to *constant fractions of a cycle* at every frequency (constant relative resolution), so low frequencies automatically get fewer cycles (better timing) and high frequencies more (better frequency separation). Choose a small fixed value only when your hypothesis is about transient timing and you want identical temporal smoothing across the whole band.

4. **Check the cone-of-influence (COI) / edge-artifact margin** — quantitative guard:
   - Each epoch edge is contaminated inward by **one half-wavelet**: `half_support = n_cycles[f] / (2 * f)` seconds. This is *largest at the lowest frequency*, where the cone is widest.
   - **Required padding rule**: the epoch handed to the TFR must extend at least `n_cycles_min / (2 * f_min)` seconds beyond the *reporting* window on **both** sides. Worked number: 3 cycles at `f_min = 2 Hz` → `3/(2*2) = 0.75 s` buffer per side.
   - **Crop after computing, do not trust padded edges.** MNE implicitly zero-pads for the FFT (`use_fft=True`), and zero-padding *biases edge power downward*. So compute on the wide epoch, then `power.crop(tmin_report, tmax_report)` to discard the cone before plotting/stats.
   - **Validation warning**: emit a warning (and record it in `TFR_SUMMARY.md`) if the requested baseline window OR any effect time window falls within `n_cycles[f_min] / (2 * f_min)` of the epoch edge at the lowest frequency — those values are inside the COI and are not interpretable.
   - If padding is insufficient: raise `f_min`, lower the minimum `n_cycles`, or explicitly trim the reporting window.
5. Resolve baseline window and mode:
   - `logratio` (default): `10 * log10(power / baseline_mean)` — units are dB, symmetric around zero. **Preferred** (Grandchamp & Delorme 2011).
   - `db`: same as logratio in MNE (`10 * log10`).
   - `zscore`: `(power - baseline_mean) / baseline_std` — useful when absolute power differences matter.
   - `percent`: `(power - baseline_mean) / baseline_mean * 100` — **avoid**: asymmetric, inflates increases relative to decreases (Grandchamp & Delorme 2011).
   - `mean`: subtract baseline mean — removes absolute power but retains scale differences across frequencies.
   - Baseline window must fall entirely within the pre-stimulus period. Verify against epoch `tmin`.

   **Caveat — divisive (dB/logratio) baseline is NOT a neutral units choice (Gyurkovics et al. 2021).** The skill's default endorsement of logratio/dB is correct for the *asymmetry* problem but hides a modeling assumption: dividing by baseline power assumes a **multiplicative** relationship between the oscillation and the aperiodic (1/f) background. Empirically, within-participant 1/f power and narrowband (e.g. alpha) power are **not** positively correlated, which supports an **additive** signal+background model instead. Two consequences to encode: (1) a baseline-period shift in the aperiodic **exponent or offset** masquerades as a narrowband change after dB normalization; (2) a condition difference in 1/f produces a **spurious "oscillatory" TFR effect**. Mitigations: parameterize and remove the aperiodic component (specparam / IRASA, see `eeg-spectral`) before or alongside the TFR, or use an **additive (subtraction) baseline** and report the 1/f exponent/offset as a covariate. Cite: Gyurkovics, M., Clements, G. M., Low, K. A., Fabiani, M., & Gratton, G. (2021). The impact of 1/f activity and baseline correction on the results and interpretation of time-frequency analyses of EEG/MEG data. *NeuroImage*, 237, 118192.

Write `tfr-stage/TFR_PARAMS.json` summarizing all resolved parameters before computation.

## Phase B — Backend Resolution

```
1. Read ENVIRONMENT.json
2. Verify MNE-Python is available → generate MNE-Python code
3. Else → ERROR: MNE-Python required
```

Write `tfr-stage/BACKEND_RESOLUTION.md`.

### Method selection — the Heisenberg tradeoff (decision table)

All TFR methods sit on the time-frequency uncertainty curve; pick by whether the question is about *transient timing* or *precise frequency content*.

| Method | Freq resolution | Time resolution | Effective freq res | Best for | MNE call |
|---|---|---|---|---|---|
| **Morlet** (default) | constant *relative* (per-octave) | scales with f | `≈ f / n_cycles` (Hz) | general ERSP/ITC, broadband | `tfr_morlet` / `tfr_array_morlet` |
| **Multitaper** | constant *absolute*, tunable | fixed by window | set by `time_bandwidth`/window | narrowband, low-variance power | `tfr_multitaper(..., time_bandwidth=4.0)` |
| **Stockwell (S-transform)** | freq-dependent (auto) | freq-dependent (auto) | automatic | broadband, no n_cycles to tune | `tfr_stockwell(fmin, fmax)` |
| **STFT (fixed window)** | constant *absolute* | constant | `≈ Fs / n_window_points` (Hz) | when one freq res across band is desired | `scipy.signal.spectrogram` / `mne.time_frequency.stft` |
| **Hilbert on narrow bands** | low (set by filter band) | **highest** | filter passband width | transient band-power envelopes, single-trial timing | `Epochs.filter(...).apply_hilbert(envelope=True)` |
| **Superlets** | high *and* time-localized (adaptive order) | high | beats single-wavelet bound | single-trial transient HF bursts (gamma/beta) | no native MNE call — external array impl |

Key contrasts to remember:
- **STFT / multitaper** use a window length *fixed across frequencies* → **constant absolute** Hz resolution (`Fs / window_points`), but capture more cycles at high f (poor low-f timing).
- **Morlet** window length `= n_cycles / f` is *adaptive* → **constant relative** resolution (good freq res at low f, good time res at high f), but is least friendly at the extremes of each axis.
- **Hilbert** trades almost all frequency resolution for time resolution; it requires band-pass filtering into a band *first* and yields an instantaneous amplitude/phase envelope (the high-time-resolution path to band power and the foundation of band-limited PLV/ITC).

## Phase C — Per-Subject TFR Computation

For each subject and condition, write and execute a script:

### MNE-Python path (default)

```python
import mne
import numpy as np

epochs = mne.read_epochs(epoch_file, preload=True)

# Morlet wavelet TFR
freqs = np.arange(2, 40, 1)
n_cycles = freqs / 2.0

# Average power (ERSP equivalent)
power = mne.time_frequency.tfr_morlet(
    epochs, freqs=freqs, n_cycles=n_cycles,
    return_itc=False, average=True, decim=4,
    n_jobs=-1, verbose=True
)

# Inter-trial coherence (requires single-trial)
power_st, itc = mne.time_frequency.tfr_morlet(
    epochs, freqs=freqs, n_cycles=n_cycles,
    return_itc=True, average=True, decim=4,
    n_jobs=-1
)

# Apply baseline correction
power.apply_baseline(baseline=(-0.5, -0.1), mode='logratio')

# Save
power.save(output_path, overwrite=True)  # .h5 format
itc.save(itc_output_path, overwrite=True)
```

**Alternative methods in MNE:**

- `mne.time_frequency.tfr_multitaper(epochs, freqs, n_cycles, time_bandwidth=4.0)` — Better frequency resolution, less spectral leakage. Use for narrow-band analyses (e.g., alpha sub-bands). `time_bandwidth` controls the frequency smoothing: higher = more tapers = smoother.
- `mne.time_frequency.tfr_stockwell(epochs, fmin=2, fmax=40)` — Automatic frequency-dependent resolution, no `n_cycles` parameter needed. Good for broadband analyses but computationally expensive.

### Superlets — single-trial transient high-frequency bursts (Moca et al. 2021)

The Morlet/multitaper/Stockwell trio serves **single-trial transient bursts** (gamma/beta) poorly: trial averaging blurs out bursts whose timing and frequency jitter, and any single wavelet is locked to one point on the time-frequency uncertainty curve. A **superlet** is the geometric mean of a *set* of Morlet wavelets with increasing cycle counts (an "order"); **adaptive superlets** raise the order with center frequency, beating the single-wavelet trade-off so you get sharp frequency resolution **and** good time localization at high frequencies simultaneously. There is **no native MNE call** — compute via an external array implementation (e.g. github.com/irhum/superlets) and wrap the result into an `AverageTFR` / `EpochsTFR` for downstream baseline/stats/figure handoff. Recommend specifically when the hypothesis concerns **transient bursts** rather than sustained rhythms (pairs naturally with the gamma myogenic guard above — confirm the burst is neural first). Cite: Moca, V. V., Bârzan, H., Nagy-Dăbâcan, A., & Mureșan, R. C. (2021). Time-frequency super-resolution with superlets. *Nat. Commun.*, 12, 337.

### Hilbert band-power path (highest time resolution)

When the question is the *timing* of band-limited activity (e.g. transient alpha suppression, single-trial envelopes) rather than its precise frequency, filter into the band and take the analytic-signal envelope — this is the high-time-resolution complement to Morlet/multitaper:

```python
# Per band of interest (filter FIRST, then Hilbert)
bands = {'theta': (4, 8), 'alpha': (8, 13), 'beta': (13, 30)}
for name, (lo, hi) in bands.items():
    ep_band = epochs.copy().filter(lo, hi, fir_design='firwin', verbose='error')
    analytic = ep_band.copy().apply_hilbert(envelope=False)    # complex analytic signal
    power_env = ep_band.copy().apply_hilbert(envelope=True)    # |Hilbert| = amplitude envelope
    # band power per trial = envelope.get_data()**2;
    # ITC per band = |mean(exp(1j*angle(analytic)))| over trials
```

Notes: `apply_hilbert` requires a **band-pass-filtered** signal (the analytic signal is only meaningful for a narrowband input); leave a filter transition margin inside the epoch (same COI logic as wavelets). Use this path, not Morlet, when you need per-sample band-power timing.

### Single-trial complex output (for ITC / single-trial analyses)

To compute ITC or per-trial power from arrays, request complex coefficients (`tfr_array_morlet` returns one coefficient per epoch — do **not** average first):

```python
# Complex per-trial coefficients via the array API
from mne.time_frequency import tfr_array_morlet
coefs = tfr_array_morlet(epochs.get_data(), sfreq=epochs.info['sfreq'],
                         freqs=freqs, n_cycles=n_cycles,
                         output='complex', n_jobs=-1)   # (n_epochs, n_ch, n_freqs, n_times)
itc = np.abs(np.mean(np.exp(1j * np.angle(coefs)), axis=0))   # (n_ch, n_freqs, n_times), in [0,1]
power_st = (np.abs(coefs) ** 2)                                # single-trial power
```

This is the same phasor average that defines PLV between channels (applied to a phase *difference*); see `eeg-connectivity`.

## Phase D — Baseline Correction

Apply baseline correction to all TFR outputs:

1. Verify baseline window `[t_start, t_end]` falls entirely within the epoch.
2. Apply chosen mode:
   - `logratio` / `db`: `10 * log10(power / mean(power_baseline))` — **recommended default**.
   - `zscore`: `(power - mean(power_baseline)) / std(power_baseline)`.
   - `percent`: `100 * (power - mean(power_baseline)) / mean(power_baseline)` — **avoid** unless reproducing legacy analysis.
3. If no pre-stimulus period exists (e.g., resting-state): skip baseline, use raw power or log-transform. Document this in `TFR_PARAMS.json`.
4. For condition contrasts: apply baseline to each condition separately, then subtract. Do NOT compute contrast on raw power then baseline — this introduces bias (Cohen 2014, Section 18.5).

### Single-trial baseline for power–behavior regression (Hu et al. 2014)

The guidance above assumes trial-averaged ERSP. When power is correlated against behavior **trial-by-trial**, two extra issues bite: (1) pre-stimulus baseline power (especially alpha) **drifts as a hyperbolic function of trial ORDER** within a session, so a single grand baseline systematically biases early vs late trials — model trial-order drift (e.g. include trial index as a covariate). (2) Single-trial **percent/ratio** baseline overestimates ERS and underestimates ERD and is unstable on noisy trials, while single-trial **subtraction** baseline leaves the pre-stimulus fluctuation in the estimate; for single-trial power–behavior analyses, model the baseline as a **covariate** (or z-score power per trial) rather than dividing by it. Cite: Hu, L., Xiao, P., Zhang, Z. G., Mouraux, A., & Iannetti, G. D. (2014). Single-trial time–frequency analysis of electrocortical signals: baseline correction and beyond. *NeuroImage*, 84, 876–887.

## Phase E — Inter-Trial Coherence (ITC)

ITC (also called phase-locking factor, PLF) measures phase consistency across trials:

1. Compute single-trial complex spectral estimates (not averaged).
2. ITC at each time-frequency point: `ITC(t,f) = |mean(exp(i * phase(t,f,trial)))| across trials`.
3. ITC ranges from 0 (random phase) to 1 (perfect phase-locking).
4. ITC is **not** affected by power — it is a pure phase measure.
5. ITC significance can be tested via Rayleigh test or permutation (shuffle trial labels).
5b. **ERSP vs ITC — keep them distinct in code.** ERSP (event-related spectral perturbation) = baseline-normalized *trial-averaged power* (average power **then** baseline). ITC = phase-locking computed from *single-trial complex coefficients* (`return_itc=True` on `tfr_morlet`, or `output='complex'` on `tfr_array_morlet`). You cannot recover ITC from an averaged power TFR — keep the complex/per-trial data.
5c. **ITC positive bias.** ITC is biased upward at low trial counts (the phasor average of random phases is non-zero for finite N). Always report the trial count; when contrasting ITC across conditions with unequal N, equalize by subsampling, or compare against a permutation/shuffled-phase null rather than the raw magnitude.
6. Save ITC as separate file: `tfr-stage/<sub>/<sub>-<cond>-itc.h5`.

### ITPC / ITLC — phase-only vs amplitude-weighted phase-locking (single-channel, across-trial)

ITC as defined above is the **inter-trial phase coherence (ITPC)** — the across-trial average of *unit* phasors (amplitude discarded). Tallon-Baudry & Bertrand (1996) also define the **inter-trial linear coherence (ITLC)**, which *weights each trial's phasor by its amplitude*, so trials with stronger oscillations contribute more. Both are **single-channel, across-trial** measures of evoked phase-locking / phase resetting — they are **not** inter-channel connectivity and **not** power.

```python
import numpy as np
from mne.time_frequency import tfr_array_morlet

# ---- ITPC via the high-level API (recommended, returns AverageTFR) ----
power, itc = epochs.compute_tfr(
    method='morlet', freqs=freqs, n_cycles=n_cycles,
    return_itc=True, average=True, decim=4, n_jobs=-1,
)
# itc is an AverageTFR; itc.data is in [0, 1], shape (n_ch, n_freqs, n_times).
# This is unit-phasor ITPC = |mean_trials exp(i*phase)| — amplitude is discarded.

# ---- ITPC and ITLC from complex coefficients (pure numpy, single-channel) ----
F = tfr_array_morlet(epochs.get_data(), sfreq=epochs.info['sfreq'],
                     freqs=freqs, n_cycles=n_cycles,
                     output='complex', n_jobs=-1)        # (n_trials, n_ch, n_freqs, n_times)
N = F.shape[0]                                            # trial count

# ITPC (== itc.data above): average of unit phasors
itpc = np.abs(np.mean(np.exp(1j * np.angle(F)), axis=0)) # (n_ch, n_freqs, n_times), in [0, 1]

# ITLC (Tallon-Baudry & Bertrand 1996): amplitude-weighted, normalised to [0, 1]
itlc = np.abs(np.sum(F, axis=0)) / np.sqrt(N * np.sum(np.abs(F) ** 2, axis=0))
```

Use ITPC when you want a power-independent index of phase consistency; use ITLC when stronger-amplitude trials should dominate the phase estimate (it is closer to the magnitude of the trial-averaged complex signal normalised by total energy). Both collapse the trial axis of a **single channel** — never the channel axis.

**When ITC matters:**
- ERPs are visible only if ITC > 0 in the relevant frequency band.
- High power with low ITC = induced (non-phase-locked) activity.
- High power with high ITC = evoked (phase-locked) activity.
- ERDS maps typically show induced activity (ITC ≈ 0 after baseline).

### Make "induced" power actually induced (Kalcher & Pfurtscheller 1995)

The skill labels high-power/low-ITC activity "induced" conceptually, but **total** power (the default `tfr_morlet` output) still contains the **evoked** (phase-locked) contribution — an ERSP/ERDS map called "induced" without an isolation step is mislabeled. To isolate genuinely induced power, subtract the evoked response from every trial *before* the TFR:

```python
erp = epochs.average()                        # phase-locked (evoked) response
induced = epochs.copy()
induced._data -= erp.data[None]               # remove the evoked part trial-by-trial
power_induced = mne.time_frequency.tfr_morlet(induced, freqs=freqs, n_cycles=n_cycles,
                                              return_itc=False, average=True, decim=DECIM)
# evoked power = TFR of the average ERP:
power_evoked = mne.time_frequency.tfr_morlet(
    mne.EpochsArray(erp.data[None], erp.info), freqs=freqs, n_cycles=n_cycles,
    return_itc=False, average=True, decim=DECIM)
```

Offer a `power_type: total|induced|evoked` option (default `total`). **Caveat to encode (Yeung et al. 2004):** ERP subtraction only removes phase-locked power if the evoked latency is *stable* across trials — with trial-to-trial latency jitter the average ERP is temporally smeared, subtraction is incomplete, and residual evoked energy leaks into "induced" power (and inflates ITC). Either latency-align trials first, or report **total power + ITC** rather than claiming a clean evoked/induced split. Cite: Kalcher, J., & Pfurtscheller, G. (1995). Discrimination between phase-locked and non-phase-locked event-related EEG activity. *Electroencephalogr. Clin. Neurophysiol.*, 94(5), 381–384; Yeung, N., Bogacz, R., Holroyd, C. B., & Cohen, J. D. (2004). Detection of synchronized oscillations in the electroencephalogram: an evaluation of methods. *Psychophysiology*, 41(6), 822–832.

## Phase F — ERDS Maps

Event-related desynchronization/synchronization (ERDS) maps (Pfurtscheller & Lopes da Silva 1999):

1. ERDS = baseline-corrected TFR expressed as percent change or dB.
2. ERD = power decrease (desynchronization) — negative values in logratio/dB.
3. ERS = power increase (synchronization) — positive values.
4. Standard ERDS bands:
   - Mu/alpha ERD (8–13 Hz): contralateral during motor planning/execution.
   - Beta ERD (13–30 Hz): during movement.
   - Beta ERS (13–30 Hz, "beta rebound"): post-movement, ~300–600 ms after movement offset.
5. For BCI/motor imagery studies: compute ERDS per channel, create topographic ERDS maps.
6. Save band-aggregated ERDS tables: `tfr-stage/<sub>/<sub>-erds-bands.csv` with columns `[subject, condition, band, channel, time_window, erds_value]`.

## Phase F2 — Standard TFR figure trio (preview/QC)

Produce a quick visual QC trio before handing off to `eeg-figure` (these are also the canonical deliverables). Always plot **baseline-corrected** TFR with a **symmetric** colour scale shared across conditions:

```python
# 1. Montage overview — TF image per channel laid out on the scalp
power.plot_topo(baseline=None, tmin=-0.2, tmax=1.0, fig_facecolor='w', font_color='k')

# 2. ROI channel(s) — single TF image (averages over picks)
power.plot(picks=['Cz', 'C1'], combine='mean', vlim=(-vmax, vmax), cmap='RdBu_r')

# 3. Band x time-window scalp topography (e.g. alpha 8-13 Hz, 80-420 ms)
power.plot_topomap(tmin=0.08, tmax=0.42, fmin=8, fmax=13, vlim=(-vmax, vmax))
```

- Canonical data axes order: **channels x freqs x times**.
- `plot(picks=...)` with `combine='mean'` **averages** the selected channels — state this when reporting an ROI figure.
- In MNE 1.12 `plot` / `plot_topomap` take `vlim=(min, max)` (not `vmin`/`vmax`); `plot_topo` still uses `vmin`/`vmax`. Fix `vmin = -vmax` for baseline-normalized (dB/logratio/percent) data and reuse the same `vmax` for every condition so panels are comparable.
- Group level: `grand = mne.grand_average([p1, p2, ...])` over per-subject `AverageTFR` objects, then re-run the same three plots.

Delegate publication figures to `eeg-figure`; this phase is for sanity-checking the TFR before stats.

### Gamma / high-frequency myogenic-artifact guard (Yuval-Greenberg et al. 2008; Hipp & Siegel 2013)

eeg-tfr treats >30 Hz like any other band, but **induced gamma-band power is frequently muscle, not brain**. The saccadic spike potential from miniature (micro)saccades plus cranial EMG produces a broadband transient that peaks ~200–350 ms post-stimulus over frontal and parieto-occipital sites, spans ~20–90 Hz with a peak near 65 Hz, and **survives standard ICA and amplitude rejection**. Bake these defaults in before trusting any >30 Hz result:

- Require **eye-tracker or radial-EOG (micro)saccade rejection** before reporting induced gamma — ordinary EOG channels miss microsaccades.
- Distrust **broadband / edge-rising** high-frequency power (a hallmark of EMG) and a stimulus-onset-locked transient burst rather than a sustained narrowband rhythm.
- Prefer **multitaper (DPSS)** over a single Morlet wavelet at high gamma (better variance control of the broadband estimate).
- **QC the HF TFR topography** (the `plot_topomap` panel above, fmin/fmax in the gamma band) for an edge- or temporalis-dominant (peripheral, non-cortical) spatial pattern before reporting any gamma effect.

Cite: Yuval-Greenberg, S., Tomer, O., Keren, A. S., Nelken, I., & Deouell, L. Y. (2008). Transient induced gamma-band response in EEG as a manifestation of miniature saccades. *Neuron*, 58(3), 429–441; Hipp, J. F., & Siegel, M. (2013). Dissociating neuronal gamma-band activity from cranial and ocular muscle activity in EEG. *Front. Hum. Neurosci.*, 7, 338.

## Phase G — Output Files

For each subject, produce:

### `tfr-stage/<sub>/<sub>-<cond>-tfr.h5`
HDF5 containing the averaged TFR (after baseline correction). Shape: `(n_channels, n_freqs, n_times)`.

### `tfr-stage/<sub>/<sub>-<cond>-itc.h5`
HDF5 containing inter-trial coherence. Same shape as TFR.

### `tfr-stage/<sub>/<sub>-erds-bands.csv`
Band-aggregated ERDS values for quick inspection and figure generation.

### `tfr-stage/TFR_PARAMS.json`
```json
{
  "method": "morlet",
  "freqs": [2, 3, "...", 39],
  "n_cycles": "freqs / 2 (adaptive)",
  "n_cycles_range": [1.0, 19.5],
  "decim": 4,
  "baseline_window": [-0.5, -0.1],
  "baseline_mode": "logratio",
  "edge_artifact_margin_s": 0.5,
  "srate_after_decim": 64,
  "n_subjects_processed": 24,
  "n_conditions": 2,
  "itc_computed": true,
  "erds_bands": {"theta": [4,8], "alpha": [8,13], "beta": [13,30], "gamma": [30,40]},
  "backend": "mne",
  "mne_version": "1.7.0"
}
```

### `tfr-stage/TFR_SUMMARY.md`
Per-subject summary: n_epochs used, edge artifact warnings, any subjects with excessive trial rejection.

## Phase H — Sanity Checks

All must pass before declaring success:

- [ ] Every subject in `epoch-stage/` has corresponding TFR output in `tfr-stage/`.
- [ ] `TFR_PARAMS.json` exists and all fields are populated.
- [ ] Baseline window falls within the pre-stimulus period (no overlap with stimulus).
- [ ] Edge artifact margin is documented; output time axis is trimmed if needed.
- [ ] If ANALYSIS_PLAN has TFR claims: requested frequency bands and time windows fall within computed ranges.
- [ ] ITC files exist if ITC was requested.
- [ ] No NaN or Inf values in output TFR arrays (check a random subset).
- [ ] File sizes are reasonable (H5 files should be < 500 MB per subject for typical EEG).

## Phase H2 — Time-frequency statistics hand-off

TFR data feed three multiple-comparison strategies (full details and code live in `eeg-stats`):

1. **Cluster-based permutation (preferred)** — respects TF/spatial contiguity, controls FWER. `mne.stats.permutation_cluster_1samp_test` / `spatio_temporal_cluster_test` on the `(n_subj, n_freq, n_time)` array.
2. **Mass-univariate pixel-wise + FDR** — a t-test at every (f, t) pixel, then `mne.stats.fdr_correction(p, alpha=0.05)`. Cheap, no contiguity assumption. The raw uncorrected p-map is **for visualization only** — never report it as significant.
3. **A-priori TF-ROI averaging** — if a band *and* window are hypothesized, average those axes per subject **first** (`tfr.crop(tmin, tmax)` then `.data[..., fband].mean(axis=(-1, -2))`) to one value per subject/channel, then run a single (optionally one-sided) test, FDR-correcting across channels only. Highest power, but the ROI must be pre-registered to avoid double-dipping.

Prepare the per-subject array for `eeg-stats` **after** baseline correction and **after** cropping the COI (Phase A step 4). State explicitly whether the test localizes "where" (collapse time+freq, cluster over channels), "when", or "what frequency".

## Critical Rules

- **Never** use `percent` baseline mode without explicit user request and documented justification. `logratio`/`db` is the field standard (Grandchamp & Delorme 2011).
- **Never** baseline-correct a condition contrast — baseline each condition separately first, then subtract.
- **Never** ignore edge artifacts. If the epoch is shorter than the lowest-frequency wavelet, either raise the minimum frequency, reduce `n_cycles`, or explicitly trim the output time axis.
- **Never** compute ITC on averaged data — ITC requires single-trial complex estimates.
- **Never** interpret ITC magnitude without considering trial count — ITC is biased upward with fewer trials. Report trial count alongside ITC.
- **Never** describe ITPC/ITLC as connectivity or as power. ITPC/ITLC is **single-channel, across-trial** phase consistency (evoked phase-locking / phase resetting): it collapses the *trial* axis of *one* channel and discards (ITPC) or amplitude-weights (ITLC) magnitude. Inter-channel phase coupling (PLV/PLI/wPLI/coherence) is a different measure — see `eeg-connectivity` — and power is the squared magnitude, not a phase quantity.
- **Never** set `n_cycles` too high for low frequencies (e.g., 10 cycles at 2 Hz = 5 s wavelet — longer than most epochs).
- **Never** change `DECIM` after computation to match a claim's time resolution — recompute if needed.
- **Never** report or run statistics on TFR values inside the cone-of-influence. Crop `n_cycles[f_min] / (2 * f_min)` seconds from each epoch edge after computation; padded/zero-padded edges bias power downward and are not data.
- **Never** apply `apply_hilbert` to broadband data — the analytic signal is only meaningful after band-pass filtering into a single band.
- **Never** present an uncorrected pixel-wise p-map as a result; it is a visualization aid only — correct via cluster permutation or FDR.
- **Never** report induced gamma/high-frequency (>30 Hz) power without an eye-tracker/radial-EOG microsaccade reject and a HF-topography QC — the saccadic spike potential and cranial EMG survive standard ICA and masquerade as induced gamma (Yuval-Greenberg et al. 2008; Hipp & Siegel 2013).
- **Never** label a total-power ERSP/ERDS map "induced" — total power still contains the evoked response. Subtract the average ERP per trial first (and verify low latency jitter), or report total power + ITC (Kalcher & Pfurtscheller 1995; Yeung et al. 2004).
- **Never** treat dB/logratio baseline as assumption-free: it assumes a multiplicative oscillation/aperiodic relationship, so a baseline or condition difference in 1/f can produce a spurious narrowband effect — remove/parameterize the aperiodic component or use additive baseline with 1/f as a covariate (Gyurkovics et al. 2021).

## Domain Knowledge (distilled from EEG methodology literature)

### Wavelet parameters and n_cycles (Cohen 2014, Analyzing Neural Time Series Data, Ch. 12–13)

- The Morlet wavelet is a complex sine wave tapered by a Gaussian. The key parameter is the number of cycles, which controls the time-frequency trade-off.
- Fewer cycles → better temporal resolution, worse frequency resolution. More cycles → vice versa.
- `n_cycles = freqs / 2` is a common adaptive choice: gives ~3 cycles at 6 Hz and ~15 cycles at 30 Hz.
- Fixed `n_cycles` (e.g., 7) gives matched temporal resolution across frequencies but poor frequency resolution at low frequencies.
- Edge artifacts extend `n_cycles / (2 * freq)` seconds from each epoch boundary. Always verify that the analysis window excludes this margin.
- Report: wavelet family, n_cycles formula, frequency range, decimation factor.
- Cite: Cohen, M. X. (2014). Analyzing Neural Time Series Data: Theory and Practice. MIT Press.

### Single-trial time-frequency analysis (Grandchamp & Delorme 2011, Front. Psychol.)

- Single-trial TFR preserves trial-to-trial variability lost in averaging.
- Useful for: correlating power with behavior, classifying trials, computing ITC.
- In MNE: `tfr_morlet(epochs, average=False)` returns `(n_epochs, n_channels, n_freqs, n_times)`.
- Memory-intensive: consider processing one channel at a time for large datasets.
- Cite: Grandchamp, R., & Delorme, A. (2011). Single-trial normalization for event-related spectral decomposition reduces sensitivity to noisy trials. Front. Psychol., 2, 236.

### Better baselines for TFR (Grandchamp & Delorme 2011, Front. Psychol.)

- **Percent change** (`percent`) is asymmetric: a 50% decrease and 200% increase are not symmetric around zero. This distorts visualization and statistics.
- **dB / logratio** (`10 * log10(power/baseline)`) is symmetric in log space: −3 dB and +3 dB represent the same ratio. **Preferred for statistical comparisons.**
- **Z-score** normalizes by baseline variability, useful when comparing across frequency bands with different power levels.
- **Subtraction** (mean removal) is acceptable but retains 1/f scaling across frequencies.
- When in doubt, use `logratio`/`db`.
- Cite: Grandchamp, R., & Delorme, A. (2011). Single-trial normalization for event-related spectral decomposition reduces sensitivity to noisy trials. Frontiers in Psychology, 2, 236.

### STFT vs wavelet: fixed vs adaptive windows and unit conventions (Cohen 2014, Ch. 11; Welch 1967)

- **STFT** uses a single window length for all frequencies → **constant absolute** frequency resolution `≈ Fs / n_window_points`, but the number of cycles captured grows with frequency (½ cycle at 1 Hz, 5 cycles at 10 Hz for a 0.5 s window) — poor timing at low f.
- **Morlet** window length `= n_cycles / f` is adaptive → **constant relative** resolution `≈ f / n_cycles` (Hz).
- Use a **tapered** window (Hann/Hamming/DPSS), never a boxcar, to control spectral leakage; **detrend each segment** (`detrend='linear'` in `scipy.signal.spectrogram`) before the FFT so DC and slow drift do not leak into low-frequency bins; normalize by window energy so power is comparable across window lengths/types.
- Specify window length in **seconds** (convert to samples internally) and warn if `winsize * Fs < ~11` samples. MNE's `psd_array_welch` / `tfr_*` already return PSD with the Fs and window normalization applied — do **not** re-apply the single-sided `2/N` amplitude factor on top of MNE PSD output.
- Cite: Cohen, M. X. (2014). *Analyzing Neural Time Series Data*, MIT Press, Ch. 11; Welch, P. (1967). The use of fast Fourier transform for the estimation of power spectra. IEEE Trans. Audio Electroacoust., 15(2), 70–73.

### Inter-trial phase-locking: ITPC and ITLC (Tallon-Baudry & Bertrand 1996, J. Neurosci.)

- Originally introduced to separate **phase-locked (evoked)** from **non-phase-locked (induced)** gamma activity: phase-locked oscillations survive trial averaging, induced ones do not.
- **Inter-trial phase coherence (ITPC)**, a.k.a. phase-locking factor / phase-locking value across trials: `ITPC(t,f) = |(1/N) Σ_trials exp(i·φ)|`. Each trial contributes a *unit* phasor — amplitude is discarded, so ITPC is a pure phase measure in [0, 1].
- **Inter-trial linear coherence (ITLC)**: `ITLC(t,f) = |Σ_trials F| / sqrt(N · Σ_trials |F|²)` from the complex coefficients `F`. Each trial is weighted by its amplitude, so high-amplitude trials dominate; also normalised to [0, 1]. ITLC is the magnitude of the trial-summed complex signal divided by the square root of total energy.
- Both are **single-channel** quantities computed **across trials** (collapse the trial axis); they index evoked phase-locking / stimulus-driven phase resetting at one sensor. They are **not** inter-channel connectivity (that is PLV/PLI/coherence; see `eeg-connectivity`) and **not** power.
- Both are biased upward at small N (the resultant of random phasors is non-zero for finite trials). Report trial count; equalise N or compare against a shuffled-phase null when contrasting conditions.
- In MNE: `epochs.compute_tfr(method='morlet', ..., return_itc=True, average=True)` returns the unit-phasor ITPC as an `AverageTFR` (`itc.data` in [0, 1]); ITLC needs the complex coefficients from `tfr_array_morlet(..., output='complex')`.
- Cite: Tallon-Baudry, C., Bertrand, O., Delpuech, C., & Pernier, J. (1996). Stimulus specificity of phase-locked and non-phase-locked 40 Hz visual responses in human. Journal of Neuroscience, 16(13), 4240–4249.

### ERDS maps (Pfurtscheller & Lopes da Silva 1999, Clin. Neurophysiol.)

- ERD (event-related desynchronization): power decrease relative to baseline, reflecting cortical activation.
- ERS (event-related synchronization): power increase, reflecting cortical idling or active inhibition.
- Mu (8–13 Hz) and beta (13–30 Hz) ERD are robust markers of motor cortex engagement.
- Beta rebound (post-movement ERS) occurs ~300–600 ms after movement offset and is sensitive to fatigue, learning, and pharmacological interventions.
- ERDS maps plot time-frequency power changes per channel, typically for motor paradigms.
- Cite: Pfurtscheller, G., & Lopes da Silva, F. H. (1999). Event-related EEG/MEG synchronization and desynchronization: basic principles. Clin. Neurophysiol., 110(11), 1842–1857.

### Hilbert band power and band-limited phase (Le Van Quyen et al. 2001, J. Neurosci. Methods)

- For band-resolved *timing*, band-pass filter into a narrow band then take the analytic signal `z(t) = x(t) + i·H{x(t)}`; `|z(t)|` is the instantaneous amplitude (band power = `|z|²`) and `angle(z(t))` is the instantaneous phase.
- The analytic signal is only meaningful for a **narrowband** input — broadband Hilbert mixes frequencies and yields uninterpretable phase. Filter first.
- This is the high-time-resolution / low-frequency-resolution corner of the tradeoff: amplitude/phase are defined per sample, but all within-band frequency detail is discarded.
- Band-limited Hilbert phase is the substrate for band PLV/ITC (the same unit-phasor average used by Morlet ITC), making the Hilbert and wavelet phase metrics closely equivalent for a matched band.
- Cite: Le Van Quyen, M., Foucher, J., Lachaux, J.-P., Rodriguez, E., Lutz, A., Martinerie, J., & Varela, F. J. (2001). Comparison of Hilbert transform and wavelet methods for the analysis of neuronal synchrony. J. Neurosci. Methods, 111(2), 83–98.

### COBIDAS-MEEG TFR reporting (Pernet et al. 2020, Nature Neuroscience)

For TFR analyses, the methods section must report:
- Time-frequency decomposition method (Morlet, multitaper, Stockwell)
- Frequency range and resolution
- Number of cycles (or equivalent parameter) and whether adaptive
- Baseline window and correction mode
- Decimation factor and resulting temporal resolution
- Whether power, ITC, or both were computed
- Software and version

## Failure Modes

| Symptom | Action |
|---|---|
| `epoch-stage/` missing | Stop. Run `eeg-epoch` first. |
| Edge artifact exceeds analysis window | Warn user. Trim output time axis or adjust `n_cycles`/frequency range. |
| NaN in TFR output | Check for flat channels or epochs with zero variance. Likely upstream issue — re-run `eeg-epoch` with stricter artifact rejection. |
| Memory error on single-trial TFR | Reduce `n_jobs`, process channels sequentially, or increase `decim`. |
| Baseline window overlaps stimulus | Stop. Adjust baseline window to be entirely pre-stimulus. |
| ITC values all near zero | Expected for induced (non-phase-locked) responses. Verify phase-locked responses (ERPs) exist before interpreting. |
| Extremely large H5 files (> 2 GB) | Increase `decim`, reduce frequency resolution, or save only frequency bands of interest. |
| Different trial counts across conditions | Warn. ITC is biased by trial count — equalize by subsampling if comparing ITC across conditions. |
| Effect/baseline window inside the COI at f_min | Stop or warn. Widen the epoch by `n_cycles[f_min]/(2*f_min)` s per side and recompute, or raise `f_min`. Values in the cone are not interpretable. |
| `apply_hilbert` gives noisy/meaningless envelope | The input was not band-pass filtered. Filter into a single band first (`epochs.filter(lo, hi)`), then `apply_hilbert`. |
| Stockwell TFR very slow / memory-heavy | Expected for broadband `tfr_stockwell`. Narrow `fmin/fmax`, increase `decim`, or switch to Morlet. |
| ITC looks high but trial count is small | Positive bias at low N. Report N; compare against a shuffled-phase permutation null instead of the raw magnitude. |
| ITPC/ITLC inflated, or one condition higher purely because it has more rejected trials | Phase-resultant of finite N is non-zero even for random phase, so smaller N inflates the metric. Use an adequate trial count and **match N across conditions** (subsample to the smaller N, or average several random subsamples); never compare raw ITPC/ITLC across unequal trial counts. |
| ITPC/ITLC reported as "connectivity" or compared to power | Category error. ITPC/ITLC is single-channel, across-trial phase-locking — not inter-channel coupling (`eeg-connectivity`) and not power. Relabel; recompute the intended quantity if connectivity/power was actually wanted. |

## Cross-references

- **Inputs**: `epoch-stage/*-epo.fif`, `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, `ENVIRONMENT.json`
- **Outputs**: `tfr-stage/*-tfr.h5`, `tfr-stage/*-itc.h5`, `tfr-stage/*-erds-bands.csv`, `tfr-stage/TFR_PARAMS.json`, `tfr-stage/TFR_SUMMARY.md`, `tfr-stage/BACKEND_RESOLUTION.md`
- **Next**: `eeg-stats` reads TFR outputs for cluster permutation on time-frequency data. `eeg-figure` reads TFR for ERSP/ITC plots and topographic ERDS maps. `eeg-methods-text` reads `TFR_PARAMS.json` for the methods paragraph.
- **Previous**: `eeg-epoch` produces the epoched data consumed here.
