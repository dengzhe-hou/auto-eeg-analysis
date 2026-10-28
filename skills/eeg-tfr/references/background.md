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
- **Logratio** is `log10(power/baseline)`; **dB** is ten times that value. They are symmetric in log space: −3 dB and +3 dB represent reciprocal power ratios. **Preferred for statistical comparisons.**
- **Z-score** normalizes by baseline variability, useful when comparing across frequency bands with different power levels.
- **Subtraction** (mean removal) is acceptable but retains 1/f scaling across frequencies.
- When in doubt, use `logratio`/`db`.
- Cite: Grandchamp, R., & Delorme, A. (2011). Single-trial normalization for event-related spectral decomposition reduces sensitivity to noisy trials. Frontiers in Psychology, 2, 236.

### STFT vs wavelet: fixed vs adaptive windows and unit conventions (Cohen 2014, Ch. 11; Welch 1967)

- **STFT** uses a single window length for all frequencies → **constant absolute** frequency resolution `≈ Fs / n_window_points`, but the number of cycles captured grows with frequency (½ cycle at 1 Hz, 5 cycles at 10 Hz for a 0.5 s window) — poor timing at low f.
- **Morlet** widths scale as `n_cycles / f` in time and `f / n_cycles` in frequency. Fixed cycles give constant relative frequency resolution; the released `n_cycles=f/2` gives constant absolute widths.
- Use a **tapered** window (Hann/Hamming/DPSS), never a boxcar, to control spectral leakage; **detrend each segment** (`detrend='linear'` in `scipy.signal.spectrogram`) before the FFT so DC and slow drift do not leak into low-frequency bins; normalize by window energy so power is comparable across window lengths/types.
- Specify window length in **seconds** (convert to samples internally) and warn if `winsize * Fs < ~11` samples. MNE's `psd_array_welch` returns power spectral density (V²/Hz for EEG); Morlet `tfr_*` power uses wavelet normalization and is not a V²/Hz PSD. Do **not** apply a single-sided `2/N` amplitude factor to either output.
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
