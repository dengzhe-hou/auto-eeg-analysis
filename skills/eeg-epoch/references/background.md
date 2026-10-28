## Domain Knowledge (distilled from EEG methodology literature)

### AutoReject (Jas et al. 2017, NeuroImage)

- AutoReject learns per-channel amplitude thresholds using cross-validation on the epoch data.
- **Local mode**: for each epoch, identifies bad channels and interpolates them. Only rejects the epoch if too many channels are bad. Results in higher trial retention than global rejection.
- **Global mode**: computes a single rejection threshold dictionary (e.g., `{'eeg': 120e-6}`). Equivalent to MNE's `reject` parameter but data-driven instead of arbitrary.
- When to use local: most analyses. When to use global: very large datasets where local is too slow, or when you need a simple threshold for reporting.
- AutoReject should be applied **after** ICA (bad ICA components add variance that biases the learned thresholds).
- Cite: Jas, M., Engemann, D. A., Bekhti, Y., Raimondo, F., & Gramfort, A. (2017). Autoreject: Automated artifact rejection for MEG and EEG data. NeuroImage, 159, 417–429.

### Epoch parameters (Luck 2014, An Introduction to the Event-Related Potential Technique, Ch. 4)

- **Baseline duration**: minimum 100 ms. The baseline period must be free of neural activity related to the current trial or preceding trial.
- **Epoch length**: must extend beyond the latest component of interest. For P300: at least 800 ms. For LPP/P600: at least 1000 ms.
- **Pre-stimulus buffer**: include 100–200 ms extra before the analysis window for baseline and for wavelet edge artifacts if TFR follows.
- **Post-stimulus buffer**: include 100–200 ms extra after the analysis window to avoid edge effects.
- **High-pass filter interaction**: if the continuous data was high-pass filtered above 0.1 Hz, filter ringing can distort the baseline. Use longer baselines (300–500 ms) to accommodate filter transients.
- **Trial count**: The SNR of an ERP average improves as sqrt(N). Doubling trials from 30 to 60 improves SNR by ~41%.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd Edition. MIT Press.

### EEGLAB rejection methods (Delorme et al. 2007, J. Neurosci. Methods)

- EEGLAB provides multiple rejection criteria: amplitude threshold, joint probability, kurtosis, spectral threshold, and trend.
- **Amplitude threshold** (`pop_eegthresh`): simplest; rejects epochs exceeding ±X µV. Good for catching large artifacts but misses subtle ones.
- **Joint probability** (`pop_jointprob`): rejects statistically improbable epochs based on the distribution of all epochs. Good for detecting outliers.
- **Kurtosis** (`pop_rejkurt`): detects epochs with peaky or flat distributions. Good for catching brief muscle artifacts or flat-line segments.
- Best practice: combine multiple criteria or use automated methods (FASTER, AutoReject).
- Cite: Delorme, A., Sejnowski, T., & Makeig, S. (2007). Enhanced detection of artifacts in EEG data using higher-order statistics and independent component analysis. NeuroImage, 34(4), 1443–1449.

### Amplitude rejection thresholds — converging practice (~100 µV)

- Two independent reference workflows converge on a peak-to-peak rejection band of ~100 µV for typical scalp EEG, applied **after** ICA. The MNE-Python preprocessing tutorial's worked example uses `reject=dict(eeg=2e-4)` (200 µV) but its own annotation flags this as "set too large" and recommends 5e-5–1e-4 V (50–100 µV) for good-quality data. The MCKJ ERP course rejects at ±100 µV via EEGLAB `pop_eegthresh`, then tightens to ±60 µV once ICA has removed blinks.
- Practical default: `dict(eeg=100e-6)` conservative; tighten to 60–75 µV for clean, low-impedance recordings; loosen only with explicit justification. 150–200 µV passes real artifacts.
- Threshold rejection is amplitude-only and misses subtle artifacts; AutoReject (`get_rejection_threshold` for a data-driven global threshold, or local mode for per-channel interpolation) is the preferred replacement for a hand-set number when `autoreject` is available.
- Cite: MNE-Python preprocessing tutorial, "Rejecting Epochs based on channel amplitude" (mne.tools documentation); and COBIDAS-MEEG (Pernet et al. 2020, *Nature Neuroscience* 23, 1473–1483) for the requirement to report the exact threshold used.

### Epoch / segment duration sets spectral resolution

- For any analysis that goes to the frequency domain (PSD, Welch, TFR), the epoch or segment length **fixes** the frequency resolution: `resolution_Hz = sfreq / NFFT = 1 / duration_s`. Worked example: a resting recording at 256 Hz cut into 2 s segments (`L = 512` samples) yields `256/512 = 0.5 Hz` bins.
- Consequences for epoching choices: to resolve features 0.5 Hz apart (e.g. individual alpha sub-peaks) you need ≥2 s segments; for 0.25 Hz spacing you need ≥4 s. Longer segments buy finer resolution but yield fewer independent segments, so the PSD estimate is noisier (higher variance). This is the practical reason resting-state epoching often standardises on 2 s windows.
- Pick `duration` deliberately from the resolution the downstream analysis needs; pass the same length to `eeg-spectral` (Welch `n_per_seg = duration_s * sfreq`) so the epoching and PSD stages agree.
- Cite: Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra. *IEEE Trans. Audio Electroacoust.* 15(2), 70–73; standard FFT resolution relation Δf = fs/N.

### Trial count requirements across paradigms

| Paradigm / Component | Minimum trials | Recommended | Source |
|---|---|---|---|
| P300 (oddball) | 30 | 60+ | Luck 2014 |
| N170 (face/object) | 30 | 40+ | Luck 2014 |
| N400 (language) | 30 | 50+ | Luck 2014 |
| MMN (auditory) | 100 | 200+ | Näätänen et al. 2007 |
| N2pc (attention) | 100 | 200+ | Luck 2012 |
| ERN (error) | 6 | 20+ | Olvet & Hajcak 2009 |
| LPP (emotion) | 30 | 60+ | Luck 2014 |
| SSVEP | 10 | 20+ | Norcia et al. 2015 |

### COBIDAS-MEEG reporting (Pernet et al. 2020, Nature Neuroscience)

For epoching, the methods section must report:
- Epoch time window (pre- and post-stimulus)
- Baseline correction window and method
- Artifact rejection method, criteria, and thresholds
- Number of trials per condition per subject (mean ± SD, range)
- Number of excluded subjects and reason
- Software and version
