## Integrated relative band power numerical quick start

When the approved task requests a ratio of integrated PSDs, use the same
frequency grid and supplied numerator/denominator bands. This returns one
ratio per channel (or epoch and channel); average channels afterwards only
as specified by the task. A ratio of mean PSD densities is a different
quantity when bandwidths differ.

```python
import numpy as np
from scipy.integrate import trapezoid

def integrated_band_power_ratio(psd_data, frequencies, band, total_band):
    band_mask = (frequencies >= band[0]) & (frequencies <= band[1])
    total_mask = (frequencies >= total_band[0]) & (frequencies <= total_band[1])
    band_power_int = trapezoid(psd_data[..., band_mask], frequencies[band_mask], axis=-1)
    total_power_int = trapezoid(psd_data[..., total_mask], frequencies[total_mask], axis=-1)
    if np.any(total_power_int <= 0):
        raise ValueError("Relative power needs a positive integrated denominator.")
    return band_power_int / total_power_int
```

Resolve channel identity, filtering, Welch parameters, DC removal and the
actual integration bins before calling this function. The sections below
explain these choices and distinguish average density from integrated power.

## Constants

Scientific settings must be resolved from the explicit task or approved plan;
this skill supplies no automatic 2 s window, alpha band or alpha estimator.
Keep fixed recipe/study settings when they have already been approved.

| Setting in `SPECTRAL_PLAN.json` | Required when |
| --- | --- |
| `method`, `frequency_range_hz` | Computing a PSD; choose the matching template, not another estimator as a silent fallback |
| `welch.segment_seconds`, `window`, `overlap_fraction`, `n_fft`, `remove_dc` | Welch; explicit `n_fft: null` means equal to the selected segment length |
| `bands`, `band_measure` (`mean_density` or `integrated_power`) | Extracting band values; relative power additionally needs its denominator and aggregation order |
| `alpha.method`, `band_hz`, channels/aggregation and method-specific parameters | Estimating alpha frequency; name peak versus center of gravity, smoothing and missing-peak rules |
| Aperiodic fit range and model parameters | Requesting specparam/FOOOF; see Phase C for fit-border considerations |
| Baseline and normalization rule | Requesting task-related baseline normalization |
| Seed | An approved stochastic operation requires one; read the plan rather than inserting 42 |

`OUTPUT_DIR = spectral-stage/` is a file-layout convention, not a scientific
parameter. Optional analyses run only when requested. A missing scientific
setting is a missing decision, not permission to copy an illustrative value.

For the Welch template below, this is an **example configuration**, not a fallback
or evidence of researcher approval:

```json
{
  "method": "welch",
  "frequency_range_hz": [1, 40],
  "welch": {
    "segment_seconds": 2.0, "window": "hann", "overlap_fraction": 0.5,
    "n_fft": null, "remove_dc": true
  },
  "bands": {"alpha": [8, 13]},
  "band_measure": "mean_density"
}
```

Do not request band or alpha settings for a task that only asks for a PSD.

## Phase A — Determine analysis type

1. Read `DATASET_BRIEF.md`:
   - **Resting-state** (eyes-open, eyes-closed): compute PSD on continuous preprocessed data (`preprocess-stage/` or `ica-stage/`).
   - **Task-related**: compute PSD on epoched data (`epoch-stage/`), optionally with baseline normalization.
2. Read `ANALYSIS_PLAN.md` for spectral claims (if any).
3. Check if `— fooof` or `— iapf` was requested. Resolve only the settings needed
   by the requested outputs. List missing choices explicitly and pause those
   computations; in unattended work, record them and continue independent approved work.

Write `spectral-stage/SPECTRAL_PLAN.json`.

## Phase B — PSD computation

Write and execute a Python script. For each subject:

### MNE-Python path (default)

```python
import mne
import numpy as np
from scipy.integrate import trapezoid

# SPECTRAL_PLAN is the resolved JSON from this task/approved study plan.
required = {'method', 'frequency_range_hz', 'welch'}
missing = required - SPECTRAL_PLAN.keys()
if missing:
    raise ValueError(f"Missing approved spectral settings: {sorted(missing)}")
if SPECTRAL_PLAN['method'] != 'welch':
    raise ValueError("This template is Welch; use the approved estimator's procedure.")
FMIN, FMAX = SPECTRAL_PLAN['frequency_range_hz']

def welch_parameters(sfreq, n_times):
    settings = SPECTRAL_PLAN['welch']
    missing = {'segment_seconds', 'window', 'overlap_fraction', 'n_fft', 'remove_dc'} - settings.keys()
    if missing:
        raise ValueError(f"Missing approved Welch settings: {sorted(missing)}")
    n_per_seg = round(settings['segment_seconds'] * sfreq)
    if not 1 <= n_per_seg <= n_times:
        raise ValueError("Approved segment duration does not fit the data; resolve it explicitly.")
    n_fft = n_per_seg if settings['n_fft'] is None else settings['n_fft']
    if n_fft < n_per_seg:
        raise ValueError("N_FFT must be >= n_per_seg; choose the segment duration explicitly.")
    overlap = settings['overlap_fraction']
    if not 0 <= overlap < 1:
        raise ValueError("Approved overlap_fraction must be in [0, 1).")
    return dict(n_fft=n_fft, n_per_seg=n_per_seg,
                n_overlap=int(overlap * n_per_seg), window=settings['window'],
                remove_dc=settings['remove_dc'])

# Resting-state: continuous data
raw = mne.io.read_raw_fif(preprocessed_path, preload=True)
welch_kw = welch_parameters(raw.info['sfreq'], raw.n_times)
psd = raw.compute_psd(method='welch', fmin=FMIN, fmax=FMAX, **welch_kw)
freq_res = raw.info['sfreq'] / welch_kw['n_per_seg']  # segment-limited resolution
freq_step = raw.info['sfreq'] / welch_kw['n_fft']     # frequency-grid spacing
# psd.get_data() → (n_channels, n_freqs)
# psd.freqs → frequency vector

# Task-related: epoched data
epochs = mne.read_epochs(epochs_path, preload=True)
welch_kw = welch_parameters(epochs.info['sfreq'], len(epochs.times))
psd = epochs.compute_psd(method='welch', fmin=FMIN, fmax=FMAX, **welch_kw)
# psd.get_data() → (n_epochs, n_channels, n_freqs)
# Per-condition spectra retain the epoch axis; average it separately if needed:
psd_cond = epochs[condition].compute_psd(method='welch', fmin=FMIN, fmax=FMAX, **welch_kw)

# Band power extraction
bands = SPECTRAL_PLAN.get('bands', {})  # omitted when no band summary is requested
if bands and SPECTRAL_PLAN.get('band_measure') not in {'mean_density', 'integrated_power'}:
    raise ValueError("Specify band_measure for the requested band values.")
for band_name, (fmin_b, fmax_b) in bands.items():
    freq_mask = (psd.freqs >= fmin_b) & (psd.freqs <= fmax_b)
    if SPECTRAL_PLAN['band_measure'] == 'mean_density':
        band_power = psd.get_data()[..., freq_mask].mean(axis=-1)
    else:
        band_power = trapezoid(psd.get_data()[..., freq_mask], psd.freqs[freq_mask], axis=-1)
    # Convert to dB: 10 * np.log10(band_power)
```

Resolve the approved JSON before executing. The same `welch_kw` is used for all
epochs and every condition, so their frequency grids agree. If an epoch is
shorter than the approved segment, the template raises instead of silently
shortening it. A shorter segment requires an explicit task/plan choice; record
its actual duration and resolution. An FFT below the segment length also raises.

### Frequency resolution, zero-padding, and the Nyquist/low-pass cap

- **Resolution rule:** achievable resolution = `sfreq / n_per_seg = 1 / segment_seconds`. 2 s segments → 0.5 Hz bins; 4 s → 0.25 Hz. Longer segments give finer resolution but fewer independent segments (noisier average). Choose deliberately from the science (e.g. resolving close alpha sub-peaks needs ≥2 s).
- **Zero-padding only interpolates:** `n_fft > n_per_seg` zero-pads each segment, producing a denser grid but no new ability to resolve two close frequencies. Explicit `n_fft: null` selects `n_fft == n_per_seg`; record the approved choice and both the grid spacing and segment duration.
- **Always assert** `fmax <= sfreq/2` (Nyquist). The spectrum has bins up to Nyquist regardless of filtering.
- **Low-pass cap pitfall:** if the data was low-pass filtered at `fc`, bins still exist up to Nyquist but content above `fc` is filter roll-off, not signal. Do NOT interpret spectral content above the low-pass cutoff even though bins are present. Cap reported/interpreted frequencies at `min(fmax, fc)`.

### Band-power aggregation: mean vs integral

Two conventions — report which one you used:

```python
freq_mask = (psd.freqs >= fmin_b) & (psd.freqs <= fmax_b)
psd_data = psd.get_data()  # power spectral density (units²/Hz)
from scipy.integrate import trapezoid
# (a) mean over bins — average power density (resolution-independent)
band_power_mean = psd_data[..., freq_mask].mean(axis=-1)
# (b) integral over bins — total band power (depends on resolution; the physical 'band power')
band_power_int = trapezoid(psd_data[..., freq_mask], psd.freqs[freq_mask], axis=-1)
```

Mean is robust to differing resolution; the trapezoidal integral is true band power (units²) and is preferred when comparing absolute power. Relative power = band integral / total (1–40 Hz) integral, which removes per-subject scaling and is often more reliable than absolute power.

For a task-specific ratio, preserve the requested numerator and denominator
bands, channel-wise averaging and detrending rule. Record the selected channel
names and their identities: an EDF reader can type ECG as EEG when the file
does not encode channel types. Channel labels and dataset metadata therefore
need checking before `pick_types(eeg=True)` is treated as a physiological
selection. This also applies to ocular derivations such as LOC/ROC: retain
their EOG identity when the recording metadata defines them as eye channels,
even if the reader initially labels them EEG. State how reference derivations are handled; do not silently change
the channel set.

Save the Welch window, segment length, overlap, FFT length, DC removal and the
actual frequency bins used for each integral. A band narrower than the grid
can otherwise have too few bins or cover only part of the requested interval.
Do not choose these settings by closeness to a benchmark answer. Use
`scipy.integrate.trapezoid` in adapted templates; it also works in the observed
NumPy 1.x execution environment where `np.trapezoid` is unavailable.

### Parametric (AR) PSD — short-segment / high-resolution alternative to Welch

Welch needs many segments to average down variance, so on SHORT data (a few seconds, or a single short epoch) its resolution is coarse and the estimate is noisy. A parametric autoregressive (AR) model fits an order-`p` all-pole model to the (detrended) signal and derives a smooth, high-resolution PSD analytically — useful for short resting segments, transient windows, or when you need a compact spectral parameterization. The AR coefficients themselves are a small fixed-length feature vector that feeds the `eeg-decoding` tabular path.

**`statsmodels.regression.linear_model.yule_walker` is an OPTIONAL dependency.** If an approved AR analysis needs it and it is missing, report that requirement; do not silently replace AR with Welch. Detrend the segment BEFORE fitting (AR assumes zero-mean, drift-free input; a residual trend masquerades as spurious low-frequency power).

```python
import numpy as np
from scipy.signal import detrend

def ar_psd(x, fs, order, freqs):
    """Parametric AR (Yule-Walker) PSD. OPTIONAL: needs statsmodels.

    Returns (freqs, psd) in the same V**2/Hz convention as MNE Welch output,
    with the explicitly supplied order and frequency grid.
    """
    try:
        from statsmodels.regression.linear_model import yule_walker
    except ImportError as error:
        raise ImportError("Approved AR analysis requires statsmodels; install it or resolve the plan.") from error

    x = detrend(np.asarray(x, dtype=float), type='linear')  # detrend FIRST
    # rho = AR coefficients (a_1..a_p), sigma = innovation/residual std
    rho, sigma = yule_walker(x, order=order, method='mle')

    # Denominator A(f) = 1 - sum_k rho_k * exp(-j 2*pi f k / fs)
    k = np.arange(1, order + 1)
    expo = np.exp(-1j * 2 * np.pi * np.outer(freqs / fs, k))   # (n_freqs, p)
    denom = 1.0 - expo @ rho
    psd = (sigma ** 2 / fs) / np.abs(denom) ** 2   # V**2/Hz
    return freqs, psd, rho   # rho is the compact AR feature vector

# AR_PLAN and AR_FREQUENCIES are resolved for this study.
freqs_ar, psd_ar, ar_coeffs = ar_psd(
    x_channel, fs=raw.info['sfreq'], order=AR_PLAN['order'], freqs=AR_FREQUENCIES)
# ar_coeffs (length = order) -> tabular feature for eeg-decoding
```

**Model-order sensitivity (the load-bearing caveat).** The AR order `p` is a bias/variance knob with no free lunch — always sweep it and inspect, never trust a single order:

```python
for P in AR_PLAN['sensitivity_orders']:
    f_ar, p_ar, _ = ar_psd(x_channel, fs=raw.info['sfreq'], order=P, freqs=AR_FREQUENCIES)
    # plot p_ar vs f_ar overlaid with the Welch PSD as ground truth
```

- **Too-low order (e.g. P=10)** over-smooths: real, closely-spaced peaks (e.g. an alpha sub-peak next to the main alpha) merge into one broad bump or vanish.
- **Too-high order (e.g. P=50)** injects SPURIOUS peaks: the model spends extra poles fitting noise, producing sharp narrowband features that look like oscillations but are artifacts of over-fitting.
- A common starting heuristic is `p ≈ fs/10` to `fs/3` of the segment, chosen by an order-selection criterion (AIC/FPE) and cross-checked against Welch. **Validate any AR peak against the Welch PSD before interpreting it.** If a peak appears in the AR spectrum but not in Welch, suspect over-fitting, not a real oscillation.

Richer parametric estimators live in the OPTIONAL `spectrum` package (`spectrum.pyule` for Yule-Walker, `spectrum.pyburg` for Burg). Report missing dependencies for the approved estimator. Switching estimator requires an explicit task/plan choice, not a dependency-driven fallback.

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

Extract the requested alpha-frequency measure per subject. `ALPHA_PLAN` comes
from the approved plan's `alpha` entry. Select exactly one estimator below;
the alternatives are not sequential fallback attempts. Resolve its search band,
channels, aggregation and method-specific settings first.

```python
import numpy as np
from scipy.signal import find_peaks
alpha_lo, alpha_hi = ALPHA_PLAN['band_hz']
method = ALPHA_PLAN['method']
alpha_mask = (freqs >= alpha_lo) & (freqs <= alpha_hi)
if method == 'specparam_peak':
    peaks = np.asarray(sm.get_params('peak')).reshape(-1, 3)
    alpha_peaks = [p for p in peaks if alpha_lo <= p[0] <= alpha_hi]
    iapf = max(alpha_peaks, key=lambda p: p[1])[0] if alpha_peaks else None
elif method == 'psd_peak':
    alpha_psd = psd[alpha_mask]
    peaks, properties = find_peaks(alpha_psd, height=ALPHA_PLAN['min_height'],
                                   prominence=ALPHA_PLAN['min_prominence'])
    iapf = (freqs[alpha_mask][peaks[np.argmax(properties['peak_heights'])]]
            if len(peaks) else None)
elif method == 'center_of_gravity':
    iapf = np.average(freqs[alpha_mask], weights=psd[alpha_mask])
else:
    raise ValueError("Select the procedure matching the approved alpha method.")
```

Report per subject: IAPF value, detection method, confidence (peak prominence), and whether individualized bands were derived.

### Estimate IAPF per channel, then average the estimates (restingIAF) — never peak-find a grand-averaged spectrum

The three snippets above operate on a single channel/PSD. **Do not detect the peak from a spectrum that has been averaged across channels (or across subjects):** spectra with slightly different individual peaks average into a smeared, flattened bump and bias the group peak. Instead derive per-channel estimates over parieto-occipital channels and average the *estimates*:

```python
# Use only when the plan explicitly selects this smoothed per-channel estimator.
from scipy.signal import savgol_filter, find_peaks
if ALPHA_PLAN['method'] != 'smoothed_channel_peak':
    raise ValueError("This procedure requires an explicit smoothed_channel_peak choice.")
po_chans = ALPHA_PLAN['channels']
alpha_lo, alpha_hi = ALPHA_PLAN['band_hz']
smoothing = ALPHA_PLAN['smoothing']
paf_per_chan, cog_per_chan = [], []
for ch in po_chans:
    p = savgol_filter(psd_ch[ch], window_length=smoothing['window_length'],
                     polyorder=smoothing['polyorder'])
    amask = (freqs >= alpha_lo) & (freqs <= alpha_hi)
    pk, props = find_peaks(p[amask], prominence=ALPHA_PLAN['min_prominence'])
    if len(pk):                                   # only count a resolvable peak
        paf_per_chan.append(freqs[amask][pk[np.argmax(p[amask][pk])]])
        cog_per_chan.append(np.average(freqs[amask], weights=p[amask]))  # center of gravity
# Require a peak in a MINIMUM number of channels before returning a subject value
MIN_CHANS = ALPHA_PLAN['min_channels']
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

- [ ] The requested estimator, segment, bands and alpha method are resolved in `SPECTRAL_PLAN.json`; no missing setting was filled by copying an example. Actual executed settings are saved with the output.
- [ ] PSD values are positive (power cannot be negative).
- [ ] Segment-limited resolution (`sfreq / n_per_seg`) and frequency-grid spacing (`sfreq / n_fft`) match the recorded settings.
- [ ] No NaN or Inf in output arrays.
- [ ] If FOOOF: r_squared > 0.90 for most channels (warn if not).
- [ ] If IAPF: detected in >80% of subjects (warn if not — population may lack alpha peak).
- [ ] Band power values are consistent across subjects (flag outliers > 3 SD).
- [ ] FINDINGS.md updated.

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
| statsmodels / spectrum not installed (AR PSD) | Report the missing approved dependency with installation instructions. Continue independent approved work; do not silently replace AR with Welch. |
| AR PSD shows sharp peaks Welch does not | Model order too high → spurious peaks from fitting noise. Lower the order, sweep P=10/20/50, and only interpret peaks confirmed by Welch. |
| AR PSD over-smooths / merges close peaks | Model order too low. Increase the order (guided by AIC/FPE), still cross-checking against Welch. |
| AR PSD has a large spurious low-frequency bump | Segment not detrended before `yule_walker`. Apply `scipy.signal.detrend(x, type='linear')` first. |
