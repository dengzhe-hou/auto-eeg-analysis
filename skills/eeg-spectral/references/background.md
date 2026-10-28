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
- Report: method, segment length (`n_per_seg`, or seconds), FFT length (`n_fft`), overlap percentage, segment-limited resolution and frequency-grid spacing.

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
epochs = mne.make_fixed_length_epochs(raw, duration=EPOCH_SECONDS,
                                      overlap=EPOCH_OVERLAP_SECONDS, preload=True)
# make_fixed_length_epochs applies NO baseline correction — correct for resting data
# EPOCH_SECONDS/EPOCH_OVERLAP_SECONDS are explicit plan values.
# Reuse welch_parameters from Phase B with the approved SPECTRAL_PLAN.
welch_kw = welch_parameters(epochs.info['sfreq'], len(epochs.times))
psd = epochs.compute_psd(method='welch', fmin=FMIN, fmax=FMAX, **welch_kw)
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
