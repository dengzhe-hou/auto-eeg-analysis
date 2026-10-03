---
name: eeg-spectral
description: "Power spectral analysis: PSD, aperiodic+periodic decomposition (specparam/FOOOF), individual alpha peak frequency (IAPF), band power extraction, 1/f slope. For resting-state, task-related power, and any analysis requiring frequency-domain characterization. Use when user says 'PSD', 'spectral analysis', 'alpha peak', 'FOOOF', 'specparam', '1/f', 'aperiodic', 'resting state power', or needs frequency-domain features."
argument-hint: "[project-dir] [— method: welch|multitaper] [— bands: theta,alpha,beta] [— fooof] [— iapf]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-spectral: frequency-domain analysis

## Context: $ARGUMENTS

## Constants

- **METHOD = `welch`** — PSD estimation method. Alternatives: `multitaper` (better frequency resolution, noisier), `periodogram` (no averaging).
- **FMIN = `1`** Hz — lower frequency bound.
- **FMAX = `40`** Hz — upper frequency bound. Increase to 100+ for high-gamma.
- **N_FFT = `null`** — auto from data. Set `n_per_seg = 2 * sfreq` for ~0.5 Hz resolution (2 s segments). Frequency resolution = `sfreq / n_per_seg = 1 / segment_seconds`; choose segment length from the resolution you need (see Phase B).
- **WINDOW = `hann`** — Welch taper. MNE's `psd_array_welch`/`compute_psd` default is `window='hamming'` with `n_overlap=0` (NOT Hann + 50% overlap). Always pass `window='hann'` and an explicit overlap — a bare/rectangular window leaks badly.
- **N_OVERLAP = `n_per_seg // 2`** — 50% segment overlap. The default `n_overlap=0` wastes variance reduction; set it explicitly.
- **REMOVE_DC = `true`** — MNE subtracts the per-segment mean (`remove_dc=True` by default). Keep on; for slow-drift data consider per-segment linear detrend (compute via `scipy.signal.welch(..., detrend='linear')` if needed).
- **BANDS** — canonical frequency bands:
  ```
  delta:  1–4 Hz
  theta:  4–8 Hz
  alpha:  8–13 Hz
  beta:   13–30 Hz
  gamma:  30–100 Hz (if FMAX allows)
  ```
  Override: `— bands: theta=4-7,alpha=8-12,low-beta=13-20,high-beta=20-30`
- **FOOOF = `false`** — run specparam (FOOOF) aperiodic+periodic decomposition. Override: `— fooof`. NOTE the in-script `freq_range=[1, 40]` and `max_n_peaks=6` defaults are NOT safe for the exponent — both fit borders bias the slope and many peaks hurt reliability; see Phase C "Fit-range borders are NOT free" and "Slope-only studies".
- **IAPF = `false`** — extract individual alpha peak frequency. Override: `— iapf`.
- **BASELINE_MODE = `null`** — for task-related spectral analysis, set to `percent` or `db` change from pre-stimulus.
- **OUTPUT_DIR = `spectral-stage/`**
- **SEED = read from ANALYSIS_PLAN**, default `42`.

> Override: `/eeg-spectral projects/my-study — fooof — iapf — method: multitaper — bands: theta=4-7,alpha=8-12`

## Required Inputs

1. `DATASET_BRIEF.md` — to know paradigm (resting-state vs task-related).
2. Preprocessed data: `preprocess-stage/` (for resting-state continuous PSD) or `epoch-stage/` (for task-related epoched PSD).
3. `ENVIRONMENT.json` — to check specparam/fooof availability.
4. `ANALYSIS_PLAN.md` — if spectral claims exist (e.g., "alpha power is higher in condition A").

## Phase A — Determine analysis type

1. Read `DATASET_BRIEF.md`:
   - **Resting-state** (eyes-open, eyes-closed): compute PSD on continuous preprocessed data (`preprocess-stage/` or `ica-stage/`).
   - **Task-related**: compute PSD on epoched data (`epoch-stage/`), optionally with baseline normalization.
2. Read `ANALYSIS_PLAN.md` for spectral claims (if any).
3. Check if `— fooof` or `— iapf` was requested.

Write `spectral-stage/SPECTRAL_PLAN.json`.

## Phase B — PSD computation

Write and execute a Python script. For each subject:

### MNE-Python path (default)

```python
import mne
import numpy as np

# Resting-state: continuous data
raw = mne.io.read_raw_fif(preprocessed_path, preload=True)
n_per_seg = int(2 * raw.info['sfreq'])       # 2 s segments → ~0.5 Hz resolution
psd = raw.compute_psd(method='welch', fmin=FMIN, fmax=FMAX,
                      n_fft=n_per_seg, n_per_seg=n_per_seg,
                      n_overlap=n_per_seg // 2, window='hann')
freq_res = raw.info['sfreq'] / n_per_seg      # report this
# psd.get_data() → (n_channels, n_freqs)
# psd.freqs → frequency vector

# Task-related: epoched data
epochs = mne.read_epochs(epochs_path, preload=True)
psd = epochs.compute_psd(method='welch', fmin=FMIN, fmax=FMAX, n_fft=N_FFT)
# psd.get_data() → (n_epochs, n_channels, n_freqs)
# Average across epochs per condition:
psd_cond = epochs[condition].compute_psd(method='welch', fmin=FMIN, fmax=FMAX)

# Band power extraction
bands = {'theta': (4, 8), 'alpha': (8, 13), 'beta': (13, 30)}
for band_name, (fmin_b, fmax_b) in bands.items():
    freq_mask = (psd.freqs >= fmin_b) & (psd.freqs <= fmax_b)
    band_power = psd.get_data()[:, freq_mask].mean(axis=-1)  # per channel
    # Convert to dB: 10 * np.log10(band_power)
```

### Frequency resolution, zero-padding, and the Nyquist/low-pass cap

- **Resolution rule:** achievable resolution = `sfreq / n_per_seg = 1 / segment_seconds`. 2 s segments → 0.5 Hz bins; 4 s → 0.25 Hz. Longer segments give finer resolution but fewer independent segments (noisier average). Choose deliberately from the science (e.g. resolving close alpha sub-peaks needs ≥2 s).
- **Zero-padding only interpolates:** `n_fft > n_per_seg` zero-pads each segment, producing a denser-looking (sinc-interpolated) grid but NO new ability to resolve two close frequencies. Default `n_fft == n_per_seg`. Treat any larger n_fft as cosmetic. Power-of-two n_fft is not needed for speed in modern numpy/scipy (pocketfft).
- **Always assert** `fmax <= sfreq/2` (Nyquist). The spectrum has bins up to Nyquist regardless of filtering.
- **Low-pass cap pitfall:** if the data was low-pass filtered at `fc`, bins still exist up to Nyquist but content above `fc` is filter roll-off, not signal. Do NOT interpret spectral content above the low-pass cutoff even though bins are present. Cap reported/interpreted frequencies at `min(fmax, fc)`.

### Band-power aggregation: mean vs integral

Two conventions — report which one you used:

```python
freq_mask = (psd.freqs >= fmin_b) & (psd.freqs <= fmax_b)
psd_data = psd.get_data()  # power spectral density (units²/Hz)
# (a) mean over bins — average power density (resolution-independent)
band_power_mean = psd_data[..., freq_mask].mean(axis=-1)
# (b) integral over bins — total band power (depends on resolution; the physical 'band power')
band_power_int = np.trapezoid(psd_data[..., freq_mask], psd.freqs[freq_mask], axis=-1)  # np.trapz was removed in NumPy 2.4
```

Mean is robust to differing resolution; the trapezoidal integral is true band power (units²) and is preferred when comparing absolute power. Relative power = band integral / total (1–40 Hz) integral, which removes per-subject scaling and is often more reliable than absolute power.

### Parametric (AR) PSD — short-segment / high-resolution alternative to Welch

Welch needs many segments to average down variance, so on SHORT data (a few seconds, or a single short epoch) its resolution is coarse and the estimate is noisy. A parametric autoregressive (AR) model fits an order-`p` all-pole model to the (detrended) signal and derives a smooth, high-resolution PSD analytically — useful for short resting segments, transient windows, or when you need a compact spectral parameterization. The AR coefficients themselves are a small fixed-length feature vector that feeds the `eeg-decoding` tabular path.

**`statsmodels.regression.linear_model.yule_walker` is an OPTIONAL dependency** — guard the import and fall back to Welch if it (or the richer `spectrum` package) is missing. Detrend the segment BEFORE fitting (AR assumes zero-mean, drift-free input; a residual trend masquerades as spurious low-frequency power).

```python
import numpy as np
from scipy.signal import detrend

def ar_psd(x, fs, order=20, freqs=None):
    """Parametric AR (Yule-Walker) PSD. OPTIONAL: needs statsmodels.

    Returns (freqs, psd) in the same V**2/Hz convention as MNE Welch output,
    or (None, None) if statsmodels is unavailable so the caller can fall back.
    """
    try:
        from statsmodels.regression.linear_model import yule_walker
    except ImportError:
        # statsmodels not in the core env: caller should fall back to Welch.
        return None, None

    x = detrend(np.asarray(x, dtype=float), type='linear')  # detrend FIRST
    # rho = AR coefficients (a_1..a_p), sigma = innovation/residual std
    rho, sigma = yule_walker(x, order=order, method='mle')

    if freqs is None:
        freqs = np.linspace(0, fs / 2, 257)        # one-sided, DC..Nyquist
    # Denominator A(f) = 1 - sum_k rho_k * exp(-j 2*pi f k / fs)
    k = np.arange(1, order + 1)
    expo = np.exp(-1j * 2 * np.pi * np.outer(freqs / fs, k))   # (n_freqs, p)
    denom = 1.0 - expo @ rho
    psd = (sigma ** 2 / fs) / np.abs(denom) ** 2   # V**2/Hz
    return freqs, psd, rho   # rho is the compact AR feature vector

# Usage with graceful degradation
res = ar_psd(x_channel, fs=raw.info['sfreq'], order=20)
if res[0] is None:
    # fall back to Welch (Phase B default) — never crash on a missing optional dep
    psd_obj = raw.compute_psd(method='welch', fmin=FMIN, fmax=FMAX,
                              n_fft=n_per_seg, n_per_seg=n_per_seg,
                              n_overlap=n_per_seg // 2, window='hann')
else:
    freqs_ar, psd_ar, ar_coeffs = res
    # ar_coeffs (length = order) -> tabular feature for eeg-decoding
```

**Model-order sensitivity (the load-bearing caveat).** The AR order `p` is a bias/variance knob with no free lunch — always sweep it and inspect, never trust a single order:

```python
for P in (10, 20, 50):
    f_ar, p_ar, _ = ar_psd(x_channel, fs=raw.info['sfreq'], order=P)
    # plot p_ar vs f_ar overlaid with the Welch PSD as ground truth
```

- **Too-low order (e.g. P=10)** over-smooths: real, closely-spaced peaks (e.g. an alpha sub-peak next to the main alpha) merge into one broad bump or vanish.
- **Too-high order (e.g. P=50)** injects SPURIOUS peaks: the model spends extra poles fitting noise, producing sharp narrowband features that look like oscillations but are artifacts of over-fitting.
- A common starting heuristic is `p ≈ fs/10` to `fs/3` of the segment, chosen by an order-selection criterion (AIC/FPE) and cross-checked against Welch. **Validate any AR peak against the Welch PSD before interpreting it.** If a peak appears in the AR spectrum but not in Welch, suspect over-fitting, not a real oscillation.

Richer parametric estimators live in the OPTIONAL `spectrum` package (`spectrum.pyule` for Yule-Walker, `spectrum.pyburg` for the Burg method, which is often more stable on short segments). Both are also NOT in the core env — guard their import the same way and fall back to the statsmodels/Welch path. `pip install statsmodels` (or `pip install spectrum`) to enable; otherwise the analysis silently uses Welch.

## Phase C — Specparam / FOOOF decomposition (when `— fooof`)

Decompose the PSD into aperiodic (1/f) and periodic (oscillatory peaks) components.

### Python (specparam, formerly FOOOF)

```python
from specparam import SpectralModel  # pip install specparam
# For group analysis: from specparam import SpectralGroupModel

# Per channel
sm = SpectralModel(peak_width_limits=[1, 8], max_n_peaks=6,
                   min_peak_height=0.1, peak_threshold=2.0,
                   aperiodic_mode='fixed')  # or 'knee' for longer recordings
sm.fit(freqs, power_spectrum, freq_range=[1, 40])

# Extract results via get_params (stable across specparam 2.x AND legacy fooof 1.x).
# NOTE: the `*_` attributes (sm.aperiodic_params_, sm.peak_params_, sm.r_squared_) exist ONLY
# in fooof 1.x and raise AttributeError on specparam 2.x — always prefer get_params().
exponent = sm.get_params('aperiodic', 'exponent')  # the 1/f slope (load-bearing)
offset   = sm.get_params('aperiodic', 'offset')
aperiodic_params = sm.get_params('aperiodic')       # [offset, exponent] (+ knee in 'knee' mode)
peak_params = sm.get_params('peak')                 # (n_peaks, 3): [center_freq, power, bandwidth]
# Fit quality: fooof 1.x exposes sm.r_squared_ / sm.error_; on specparam 2.x read sm.metrics.

# Group analysis (all channels)
fg = SpectralGroupModel(peak_width_limits=[1, 8], max_n_peaks=6,
                        min_peak_height=0.1, peak_threshold=2.0)
fg.fit(freqs, all_power_spectra, freq_range=[1, 40])
```

### Fit-range borders are NOT free — the `[1, 40]` default has two quantified failure modes

`freq_range=[1, 40]` is a starting default, not a safe one. Both borders bias the exponent, and the bias is large:

- **Upper border / noise plateau.** Including the high-frequency plateau (the flat noise floor where the spectrum stops falling) biases the exponent *downward* across the entire fit range, and in noisy data the plateau can begin as low as ~10 Hz. Set the upper border *below* the plateau onset rather than a fixed 40 Hz. Detect the onset as the lowest frequency at which the local log-log slope vanishes over a ~50 Hz interval, and use the *same* upper border across all conditions/groups so the bias does not differ between them.
- **Lower border / delta peak.** Starting the fit at 1 Hz lands the lower border on the delta peak; an oscillation straddling the border distorts the aperiodic fit and shifts the exponent by up to ~18% even when the true aperiodic activity is identical. Raise the lower border into the delta/theta trough (above the delta peak) instead of pinning it at 1 Hz.

```python
# Pick borders deliberately rather than reusing [1, 40]:
fit_lo = 2.0      # above the delta peak, in the delta/theta trough (not 1 Hz)
fit_hi = detect_plateau_onset(freqs, power_spectrum)  # below the noise floor, matched across conditions
sm.fit(freqs, power_spectrum, freq_range=[fit_lo, fit_hi])
```

Cite: Gerster, M., et al. (2022). Separating neural oscillations from aperiodic 1/f activity: challenges and recommendations. Neuroinformatics, 20, 991–1012.

### IRASA — a peak-robust second aperiodic estimator

IRASA (Irregular-Resampling Auto-Spectral Analysis) estimates the aperiodic component directly from the time series by resampling, so — unlike specparam — it does **not** break when a fit border falls on an oscillatory peak. It is a good cross-check on the specparam exponent. Encode its *evaluated* range explicitly: with resampling factors `hset` (default 1.1–1.9, step 0.05) and `hmax = max(hset)`, the trustworthy output spans `feval_min = ffit_min / hmax` to `feval_max = ffit_max * hmax`. Keep `hmax` small so `feval` stays clear of the hardware high-pass stopband at the bottom and the noise plateau at the top.

```python
# MNE ships IRASA: mne.time_frequency.psd_array_irasa (returns periodic + aperiodic)
from mne.time_frequency import psd_array_irasa
psd_ap, psd_osc = psd_array_irasa(x, sfreq=sfreq, fmin=fit_lo, fmax=fit_hi,
                                  hset=np.linspace(1.1, 1.9, 17))
# Fit a log-log line to psd_ap over [fit_lo/hmax, fit_hi*hmax] for the exponent.
```

### Slope-only studies: prefer alpha-censored regression over multi-peak FOOOF

When the science needs only the aperiodic exponent (not peak parameters), do **not** let specparam extract many peaks — every added peak lowers odd–even reliability (multi-peak FOOOF needs 60+ epochs to reach ICC ≈ 0.86). Instead mask the alpha band (~6–16 Hz) and fit a plain log-log linear regression to the remaining frequencies (censored regression reaches ICC > 0.90 at only ~30–40 epochs). **AEA's `max_n_peaks=6` default silently maximizes peaks and costs reliability** — drop it to 0–1 (or switch to censored regression / IRASA) for slope-only work.

```python
# Censored-regression exponent: mask alpha, fit log-log line to the rest
mask = ~((freqs >= 6) & (freqs <= 16)) & (freqs >= fit_lo) & (freqs <= fit_hi)
slope = np.polyfit(np.log10(freqs[mask]), np.log10(power_spectrum[mask]), 1)[0]
exponent_censored = -slope
```

Cite: Gerster et al. (2022), Neuroinformatics 20, 991 (IRASA); Kalamala, P., et al. (2025). Reliability of aperiodic-slope estimation. bioRxiv 2025.11.10.687541 (censored regression).

### Time-resolved aperiodic activity (SPRiNT) and knee interpretation

- **SPRiNT** runs specparam on a sliding short-time-Fourier spectrogram to track the exponent, offset, and peaks *over time*, then prunes peaks that fail to recur across adjacent windows. Use it when 1/f activity is non-stationary (arousal/state shifts) — AEA's static per-recording fit averages those dynamics away.
- **Convert the knee, don't just report it.** When fitting `aperiodic_mode='knee'` the knee parameter `k` is not directly interpretable; convert it to a frequency `knee_freq = k ** (1 / exponent)` and a timescale `tau = 1 / (2 * pi * knee_freq)`. The timescale makes the knee an interpretable E/I / neural-integration feature and bounds where the 1/f regime begins.

Cite: Wilson, L. E., da Silva Castanheira, J., & Baillet, S. (2022). Time-resolved parameterization of aperiodic and periodic brain activity (SPRiNT). eLife, 11, e77348; Donoghue et al. (2020), Nat. Neurosci. 23, 1655 (knee conversion).

## Phase D — Individual Alpha Peak Frequency (when `— iapf`)

Extract IAPF per subject — critical for individualized alpha band definitions.

```python
# Method 1: specparam peak detection (preferred)
# After fitting specparam, find the peak closest to 8-13 Hz
import numpy as np
peaks = np.atleast_2d(sm.get_params('peak'))   # (n_peaks, 3): [CF, power, BW]; stable on 2.x & 1.x
alpha_peaks = [p for p in peaks if p.size and 8 <= p[0] <= 13]
if alpha_peaks:
    iapf = max(alpha_peaks, key=lambda p: p[1])[0]  # highest power peak in alpha range
else:
    iapf = None  # no alpha peak detected

# Method 2: simple peak detection on PSD
from scipy.signal import find_peaks
alpha_mask = (freqs >= 7) & (freqs <= 14)
alpha_psd = psd[alpha_mask]
peaks, properties = find_peaks(alpha_psd, height=0, prominence=0.1)
if len(peaks) > 0:
    iapf = freqs[alpha_mask][peaks[np.argmax(properties['peak_heights'])]]
else:
    iapf = None  # no detectable alpha peak

# Method 3: center of gravity (Klimesch 1999)
alpha_mask = (freqs >= 7) & (freqs <= 14)
iapf_cog = np.average(freqs[alpha_mask], weights=psd[alpha_mask])
```

Report per subject: IAPF value, detection method, confidence (peak prominence), and whether individualized bands were derived.

### Estimate IAPF per channel, then average the estimates (restingIAF) — never peak-find a grand-averaged spectrum

The three snippets above operate on a single channel/PSD. **Do not detect the peak from a spectrum that has been averaged across channels (or across subjects):** spectra with slightly different individual peaks average into a smeared, flattened bump and bias the group peak. Instead derive per-channel estimates over parieto-occipital channels and average the *estimates*:

```python
# For each parieto-occipital channel: Savitzky-Golay smooth the PSD, find a peak.
from scipy.signal import savgol_filter, find_peaks
po_chans = ['P3','Pz','P4','PO3','POz','PO4','O1','Oz','O2']
paf_per_chan, cog_per_chan = [], []
for ch in po_chans:
    p = savgol_filter(psd_ch[ch], window_length=11, polyorder=5)   # smooth first
    amask = (freqs >= 7) & (freqs <= 14)
    pk, props = find_peaks(p[amask], prominence=0.1)
    if len(pk):                                   # only count a resolvable peak
        paf_per_chan.append(freqs[amask][pk[np.argmax(props['peak_heights'])]])
        cog_per_chan.append(np.average(freqs[amask], weights=p[amask]))  # center of gravity
# Require a peak in a MINIMUM number of channels before returning a subject value
MIN_CHANS = 3
iapf = np.nanmean(paf_per_chan) if len(paf_per_chan) >= MIN_CHANS else None  # flag, don't force
iapf_cog = np.nanmean(cog_per_chan) if len(cog_per_chan) >= MIN_CHANS else None
```

Follow restingIAF: Savitzky-Golay smoothing of each PSD before peak detection, both peak frequency (PAF) and center-of-gravity (CoG) per channel, a minimum-channel quorum before a participant value is returned, and an explicit "no unique peak" flag for participants who fail the quorum rather than forcing a number. Cite: Corcoran, A. W., et al. (2018). Toward a reliable, automated method of individual alpha frequency (IAF) quantification. Psychophysiology, 55, e13064.

## Phase E — Write outputs

### Per-subject files
- `spectral-stage/<sub>/psd.npz` — PSD array + freqs
- `spectral-stage/<sub>/band_power.json` — per-band, per-channel power
- `spectral-stage/<sub>/specparam_results.json` — if FOOOF requested
- `spectral-stage/<sub>/iapf.json` — if IAPF requested

### Group summary
- `spectral-stage/spectral_summary.json`:
```json
{
  "method": "welch",
  "fmin": 1, "fmax": 40,
  "n_subjects": 28,
  "band_power_mean": {"theta": 0.42, "alpha": 1.23, "beta": 0.31},
  "iapf_mean": 10.2, "iapf_std": 0.8, "iapf_range": [8.5, 12.1],
  "aperiodic_exponent_mean": 1.45, "aperiodic_exponent_std": 0.22,
  "fooof_r_squared_mean": 0.97
}
```

### Append to FINDINGS.md
```markdown
## Spectral analysis
- Method: Welch PSD, 1–40 Hz
- IAPF: mean 10.2 ± 0.8 Hz (range 8.5–12.1)
- Aperiodic exponent: 1.45 ± 0.22
- Alpha band power: [per condition if task-related]
```

## Phase F — Figures

Generate and save to `figure-stage/`:

1. **Grand-average PSD** — all channels overlaid or ROI-averaged, log-log scale, with shaded frequency bands.
2. **Specparam fit** (if FOOOF) — example channel showing raw PSD, aperiodic fit, and detected peaks.
3. **Topomap per band** — spatial distribution of theta/alpha/beta power.
4. **IAPF distribution** (if IAPF) — histogram or violin plot across subjects.
5. **Aperiodic exponent topomap** (if FOOOF) — spatial distribution of 1/f slope.

## Phase G — Sanity checks

- [ ] PSD values are positive (power cannot be negative).
- [ ] Frequency resolution matches expectation (n_fft / sfreq).
- [ ] No NaN or Inf in output arrays.
- [ ] If FOOOF: r_squared > 0.90 for most channels (warn if not).
- [ ] If IAPF: detected in >80% of subjects (warn if not — population may lack alpha peak).
- [ ] Band power values are consistent across subjects (flag outliers > 3 SD).
- [ ] FINDINGS.md updated.

## Domain Knowledge (distilled from spectral analysis literature)

### Aperiodic activity and specparam (Donoghue et al. 2020, Nature Neuroscience)

- Traditional band power conflates oscillatory (periodic) and aperiodic (1/f) components. A change in "alpha power" may actually reflect a change in the aperiodic slope.
- specparam (formerly FOOOF) separates these: aperiodic parameters (offset, exponent, optional knee) + periodic parameters (peak center, power, bandwidth).
- Always report both aperiodic and periodic components when using specparam. A steeper aperiodic slope (higher exponent) is associated with higher inhibition/excitation ratio.
- The aperiodic exponent `β` is the scale-free / 1/f slope (`PSD(f) ∝ f^(-β)`) and relates to the Hurst exponent via `H = (β - 1) / 2` (valid for `β` roughly in [1, 3]). A longer-epoch DFA estimate (`antropy.detrended_fluctuation`, `nolds.dfa`/`nolds.hurst_rs` — both OPTIONAL deps, check the import and graceful-degrade) is an alternative route to the same scaling and can be converted to/from the specparam exponent. Scaling/criticality estimates need LONGER epochs than band power (e.g. ~16 s with high overlap for power-law fits vs 2 s for PSD) and benefit from z-scoring the segment first.
- Use `aperiodic_mode='fixed'` for short recordings (<2 min); `'knee'` for longer recordings or lower frequency ranges.
- Cite: Donoghue, T., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. Nature Neuroscience, 23, 1655–1665.

### Individual alpha frequency (Klimesch 1999, Brain Research Reviews)

- The alpha peak frequency varies across individuals (typically 8–12 Hz in adults). Using a fixed 8–13 Hz band for everyone introduces error.
- IAPF can be used to define individualized bands: e.g., lower alpha = IAPF-2 to IAPF, upper alpha = IAPF to IAPF+2.
- IAPF decreases with age and cognitive load. Not all individuals show a clear alpha peak (especially children, elderly, some clinical populations).
- When reporting: state the detection method, the search range, and how many subjects had a detectable peak.
- Cite: Klimesch, W. (1999). EEG alpha and theta oscillations reflect cognitive and memory performance. Brain Research Reviews, 29, 169–195.

### PSD estimation methods (Welch vs multitaper)

- **Welch** (default): segments data into overlapping windows, computes FFT on each, averages. Good balance of frequency resolution and variance reduction. Standard for most EEG work.
- **Multitaper**: uses multiple orthogonal tapers (DPSS/Slepian) on a single window. Better frequency resolution and lower variance than Welch for short data segments. Preferred for resting-state with limited data.
- **Periodogram**: single FFT on entire signal. Maximum frequency resolution but high variance. Rarely appropriate for EEG.
- Report: method, window length (n_fft), overlap percentage, frequency resolution.

### Parametric (AR / Yule-Walker) spectral estimation (Kay & Marple 1981)

- **Nonparametric** estimators (Welch, periodogram, multitaper) make no model assumption but pay for it with the resolution/variance trade-off — fine resolution needs long data. **Parametric** AR estimators assume the signal is the output of an all-pole filter driven by white noise, then derive a smooth, high-resolution PSD from the fitted coefficients. On SHORT segments (where Welch can only average a handful of windows) AR gives sharper, less noisy spectra — this is its main advantage.
- The Yule-Walker equations relate the AR coefficients to the signal autocorrelation; `statsmodels`' `yule_walker(x, order=p, method='mle')` returns the coefficients `rho` and the innovation std `sigma`, and the PSD is `(sigma**2 / fs) / |1 - Σ_k rho_k e^{-j 2π f k / fs}|**2` (computable in pure numpy).
- **Model order is the central pitfall.** Too low → over-smoothed, merged peaks; too high → spurious narrowband peaks from fitting noise (the AR analog of over-fitting). Kay & Marple stress order selection (AIC, FPE) and validation against a nonparametric estimate. AEA always sweeps several orders (e.g. P=10/20/50) and cross-checks AR peaks against the Welch PSD before interpreting them.
- Always detrend/demean before fitting: AR assumes a zero-mean, stationary, drift-free process, and a residual trend appears as spurious low-frequency power.
- The fitted AR coefficients form a compact, fixed-length descriptor of the spectrum — a natural tabular feature for downstream classification (see `eeg-decoding`).
- Cite: Kay, S. M., & Marple, S. L. (1981). Spectrum analysis—A modern perspective. Proceedings of the IEEE, 69(11), 1380–1419.

### Units and scaling: amplitude vs power vs PSD

At each frequency bin the FFT yields a complex number `a + bi`:
- **amplitude** = `|X(f)| = sqrt(a^2 + b^2)`, units V (or µV)
- **power** = `|X(f)|^2`, units V²
- **PSD** = power per Hz, units V²/Hz (what `compute_psd`/`psd_array_welch` returns by default)
- **phase** = `np.angle(X(f)) = arctan(b/a)`

**MNE PSD functions already return correctly normalized PSD (V²/Hz)** — they handle the one-sided folding and `1/N`, `1/Fs` normalization internally. Do NOT hand-roll `2*abs(fft)/N` on MNE output and do NOT re-apply any 2/N factor.

If you DO compute a raw amplitude spectrum yourself (e.g. `np.fft.rfft` for an SSVEP peak amplitude): single-sided amplitude = `2/N * abs(rfft(x))` where `N` is the TRUE number of time samples (not a larger zero-padded n_fft), and the DC bin (0 Hz) and Nyquist bin must NOT be doubled. `sqrt(psd)` is amplitude-spectral-density (V/√Hz), which is not the same as a peak amplitude — keep the unit convention straight before any statistics, because squaring changes the distribution.

**Labeling pitfall:** always state explicitly whether an array is amplitude, power, or PSD; never call an amplitude 'power'. MATLAB FFT pipelines that store `2*abs(fft)/L` (an amplitude) in a variable named `*_power` and label the y-axis 'Amplitude' are a common source of this mismatch.

Why a taper matters: a rectangular-window FFT (a plain `fft(y)`) suffers strong spectral leakage. Welch with a Hann taper and 50% overlap suppresses leakage; averaging `|FFT|` across epochs without a per-epoch window is the taper-free 'poor man's Welch' and is acceptable only with a per-epoch window.
Cite: Welch, P. (1967). The use of FFT for the estimation of power spectra. IEEE Trans. Audio Electroacoust. 15, 70–73; Harris, F. J. (1978). On the use of windows for harmonic analysis with the DFT. Proc. IEEE 66, 51–83.

### Resting-state EEG guidelines (Barry et al. 2007; Bazanova & Vernon 2014)

- Eyes-open vs eyes-closed: alpha power is reliably higher in eyes-closed. Always report condition.
- Minimum duration: 2 minutes per condition recommended; 5 minutes preferred for reliable specparam fits.
- Stationarity: resting-state EEG shows drift over time. Consider segmenting into shorter epochs and averaging PSD across segments.
- Artifact rejection: exclude segments with muscle, eye, or drowsiness artifacts before PSD computation.

### Fixed-length epoching of continuous resting data

For resting-state data with no event markers, either feed the continuous recording straight to `raw.compute_psd` (which Welch-segments internally) or segment it into back-to-back fixed-length windows first. Do NOT baseline-correct resting data — there is no event to baseline against.

```python
# Fixed-length epochs from continuous resting data
epochs = mne.make_fixed_length_epochs(raw, duration=2.0, overlap=0.0, preload=True)
# make_fixed_length_epochs applies NO baseline correction — correct for resting data
psd = epochs.compute_psd(method='welch', fmin=FMIN, fmax=FMAX, window='hann')
```

Epoch/segment duration directly sets spectral resolution (= 1/duration): 2 s → 0.5 Hz, 4 s → 0.25 Hz. Pick the duration from the resolution you need. See `eeg-epoch` for fixed-length epoching of continuous data.

### COBIDAS-MEEG reporting for spectral analysis (Pernet et al. 2020)

Report:
- PSD estimation method, window length, overlap, taper
- Frequency range and resolution
- Band definitions (and whether fixed or individualized)
- Whether aperiodic component was modeled
- Normalization (absolute vs relative power vs dB)
- For task-related: baseline window and normalization mode
- Cite: Pernet, C. R., et al. (2020). Nature Neuroscience, 23(12), 1473–1483.

### Multi-site biomarker work: harmonization, age-normative referencing, and reliability-ranked features

When spectral features (exponent, offset, IAF, band power) are pooled across sites or used as clinical biomarkers, three steps protect the analysis — all absent from the default pipeline:

- **ComBat harmonization before pooling.** Run ComBat (`neuroHarmonize` / `pycombat`, OPTIONAL deps — guard the import and graceful-degrade) to remove site batch effects on exponent/offset/IAF/beta while *protecting* biological covariates (age, sex, diagnosis). Done correctly, harmonization can even *increase* the true age effect size rather than wash it out.
- **Age-regress before group comparison — but not the offset.** Alpha peak frequency declines ~0.015 Hz/yr and the aperiodic exponent ~0.003–0.004/yr, so regress age out of those before comparing groups. The aperiodic *offset* shows no reliable age effect — do **not** age-correct the offset.
- **Rank features by test–retest reliability.** Most reliable: offset (ICC 0.81–0.85) and parameterized alpha (0.79–0.93). Exponent is good (0.64–0.73, up to ~0.93 when the upper fit bound is restricted — consistent with the plateau caveat in Phase C). Bandwidth is weakest (0.55–0.77). The absolute alpha/beta power *ratio* is more reliable (ICC > 0.75) than any single-band power — treat it as a first-class biomarker, not an afterthought.

Cite: Li, J., et al. (2024). ComBat harmonization of resting-state spectral features. Clin. Neurophysiol., 168, 1; Leroy, A., et al. (2025). Age norms for aperiodic and periodic EEG. Front. Aging Neurosci., 17, 1540040; McKeown, D. J., et al. (2024). Test–retest reliability of aperiodic parameters. Cereb. Cortex, 34, bhad482; Chang, M. (2025). Reliability of EEG band-power ratios. Brain Behav., 15, e71035.

### Group spectral statistics: pipeline and multiple-comparison control

Standard group-PSD pipeline: `compute_psd` per epoch → average across epochs within subject → stack subjects into `subjects × channels × frequencies` → group contrast.

A mass-univariate t-test per frequency (at one ROI channel) and per channel (band-averaged for a topomap) with NO multiple-comparison correction inflates false positives. AEA must add multiple-comparison control:

```python
from mne.stats import permutation_cluster_test
# frequency- and/or sensor-resolved cluster permutation over the freq × channel map
T_obs, clusters, cluster_pv, H0 = permutation_cluster_test(
    [group1_psd, group2_psd], n_permutations=5000, seed=SEED)
# fallback when no spatial/spectral adjacency structure is assumed:
from mne.stats import fdr_correction
reject, p_fdr = fdr_correction(p_raw, alpha=0.05)
```

Use cluster-based permutation (over frequency and/or the sensor adjacency) as the default for spectral maps; FDR as a fallback. See `eeg-stats`.
Cite: Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. J. Neurosci. Methods, 164, 177–190.

## Critical Rules

- **Never** report band power without specifying whether it's absolute, relative, or dB.
- **Never** compare alpha power across subjects without considering IAPF differences (use individualized bands or specparam peaks).
- **Never** interpret a change in band power as oscillatory without ruling out aperiodic slope changes (use specparam).
- **Never** use a periodogram on short data segments — use Welch or multitaper.
- **Never** forget to report eyes-open vs eyes-closed for resting-state data.
- **Never** re-apply a `2/N` or factor-2 single-sided correction to MNE PSD output — it is already normalized (V²/Hz). The 2/N rule applies only to a hand-rolled `np.fft.rfft` amplitude, with DC and Nyquist left undoubled.
- **Never** use a bare/rectangular-window FFT for PSD — always taper (Hann/Hamming/DPSS). MNE's Welch default is Hamming with `n_overlap=0`; set `window='hann'` and 50% overlap explicitly.
- **Never** claim that increasing `n_fft` (zero-padding) improves true frequency resolution — it only interpolates. Resolution = `sfreq / n_per_seg = 1 / segment_seconds`.
- **Never** interpret spectral content above the low-pass cutoff, even though bins exist up to Nyquist.
- **Never** report uncorrected per-frequency or per-channel p-maps for a group spectral contrast — use cluster-based permutation or FDR.
- **Never** call an amplitude spectrum 'power' (or vice versa); state amplitude vs power vs PSD explicitly before any statistics.
- **Never** trust a single AR model order — sweep it (e.g. P=10/20/50) and cross-check AR peaks against the Welch PSD. A peak present in the AR spectrum but absent in Welch is over-fitting (spurious), not an oscillation.
- **Never** fit an AR model to a non-detrended segment — drift appears as spurious low-frequency power. Detrend/demean first.
- **Never** trust the specparam exponent from `freq_range=[1, 40]`: a fit border on the delta peak (lower) or the noise plateau (upper) biases the exponent by up to ~18% / drives it downward. Raise the lower border into the delta/theta trough and set the upper border below the plateau onset, matched across conditions. Cross-check with IRASA.
- **Never** maximize peaks (`max_n_peaks=6`) for a slope-only study — every extra peak lowers exponent reliability. Use 0–1 peaks, alpha-censored regression, or IRASA.
- **Never** detect IAPF from a channel- or subject-averaged spectrum — differing individual peaks average into a smeared bump. Estimate per parieto-occipital channel and average the per-channel PAF/CoG estimates; flag participants with no resolvable peak instead of forcing one.
- **Never** age-correct the aperiodic offset (no reliable age effect), and never pool spectral biomarkers across sites without ComBat harmonization that protects age/sex/diagnosis covariates.

## Failure Modes

| Symptom | Action |
|---|---|
| specparam not installed | `pip install specparam`. Fall back to simple band power if user declines. |
| No alpha peak detected | Report as finding. Some populations lack a clear alpha peak. Do not force detection. |
| FOOOF r² < 0.85 | Warn: poor fit. Check frequency range, try `aperiodic_mode='knee'`, or increase `peak_width_limits`. |
| Exponent differs between conditions but slope looks similar by eye | Likely a fit-border artifact (delta peak at lower border or noise plateau at upper border). Re-fit with borders raised/lowered and matched across conditions; cross-check with IRASA (`psd_array_irasa`). |
| Exponent reliability poor across split-halves | Too many peaks. Drop `max_n_peaks` to 0–1 or use alpha-censored regression for slope-only work. |
| Group/grand-average alpha peak looks broad or absent but individuals have clear peaks | IAPF detected on an averaged spectrum. Estimate per channel and average the estimates (restingIAF); never peak-find a grand-averaged PSD. |
| PSD has line noise spike | Preprocessing should have removed it. If still present, re-run preprocess with notch/CleanLine. |
| Very short data (<30s) | Warn: PSD estimates unreliable. Minimum 60s for Welch, 30s for multitaper. |
| Frequency resolution too low | Use LONGER segments (`n_per_seg`); resolution = sfreq/n_per_seg. Increasing only `n_fft` (zero-padding) interpolates but does NOT add real resolution. |
| PSD looks ~2× too large / 'power' is really amplitude | Likely a hand-applied `2/N` factor on MNE PSD, or amplitude mislabeled as power. MNE PSD is already V²/Hz — remove the manual correction. |
| Spurious 'signal' just below the line-noise notch or above the LP cutoff | Filter roll-off, not neural signal. Cap interpretation at the low-pass cutoff; do not read bins above it. |
| Group p-map looks significant everywhere | Uncorrected mass-univariate testing. Switch to `permutation_cluster_test` / `fdr_correction`. |
| Coherence/PLV = 1 with one segment | Connectivity metrics are degenerate on a single segment; need many epochs — see `eeg-connectivity`. |
| statsmodels / spectrum not installed (AR PSD) | `pip install statsmodels` (or `pip install spectrum`). If unavailable, fall back to Welch (Phase B default) — never crash on the missing optional dep. |
| AR PSD shows sharp peaks Welch does not | Model order too high → spurious peaks from fitting noise. Lower the order, sweep P=10/20/50, and only interpret peaks confirmed by Welch. |
| AR PSD over-smooths / merges close peaks | Model order too low. Increase the order (guided by AIC/FPE), still cross-checking against Welch. |
| AR PSD has a large spurious low-frequency bump | Segment not detrended before `yule_walker`. Apply `scipy.signal.detrend(x, type='linear')` first. |

## Cross-references

- Inputs: `preprocess-stage/` (resting-state), `epoch-stage/` (task-related), `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`
- Outputs: `spectral-stage/*.npz`, `spectral-stage/*.json`, `figure-stage/` (PSD plots, topomaps)
- Related: `eeg-tfr` (time-resolved spectral, complementary; share the same amplitude/power/PSD unit convention), `eeg-stats` (cluster permutation / FDR for group spectral contrasts), `eeg-epoch` (`make_fixed_length_epochs` for continuous resting data), `eeg-connectivity` (coherence/PLV from the cross-spectrum), `eeg-complexity` (DFA/Hurst and 1/f-slope criticality), `eeg-decoding` (AR coefficients from the parametric PSD as a compact tabular feature)
- Next: `eeg-stats` for group comparison of spectral features, `eeg-figure` for publication-ready spectral plots
