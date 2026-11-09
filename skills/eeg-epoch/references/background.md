## Domain Knowledge (distilled from EEG methodology literature)

These notes explain method choices; they do not supply missing study settings.
The approved plan determines the epoch/baseline, ICA route, rejection and
inclusion rules. Numerical examples below are not automatic cutoffs.

### AutoReject (Jas et al. 2017, NeuroImage)

- AutoReject learns per-channel amplitude thresholds using cross-validation on the epoch data.
- **Local mode**: for each epoch, identifies bad channels and interpolates them. Only rejects the epoch if too many channels are bad. Results in higher trial retention than global rejection.
- **Global mode**: computes a single rejection threshold dictionary (e.g., `{'eeg': 120e-6}`). Equivalent to MNE's `reject` parameter but data-driven instead of arbitrary.
- Local and global modes change the processing method; choose them in the plan,
  rather than switching because a run is slow. Keep approved pre-ICA handling
  distinct from final artifact rejection and record both stages.
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

### Amplitude rejection definitions

- MNE's `reject={'eeg': value}` is a peak-to-peak threshold in volts. EEGLAB
  positive/negative amplitude limits describe signed voltage bounds. A ±100 µV
  limit is not interchangeable with a 100 µV peak-to-peak threshold; do not infer
  a shared default from examples using these different definitions.
- Record the actual criterion, value, units, channels and processing stage.
  Data-driven threshold estimation and fixed limits are different methods;
  a missing package does not authorize substitution or threshold tightening.
- See the [MNE Epochs rejection parameters](https://mne.tools/1.8/generated/mne.Epochs.html)
  and COBIDAS-MEEG (Pernet et al. 2020) for reporting the actual method.

### Epoch / segment duration sets spectral resolution

- For any analysis that goes to the frequency domain (PSD, Welch, TFR), the epoch or segment length **fixes** the frequency resolution: `resolution_Hz = sfreq / NFFT = 1 / duration_s`. Worked example: a resting recording at 256 Hz cut into 2 s segments (`L = 512` samples) yields `256/512 = 0.5 Hz` bins.
- Consequences for epoching choices: to resolve features 0.5 Hz apart (e.g. individual alpha sub-peaks) you need ≥2 s segments; for 0.25 Hz spacing you need ≥4 s. Longer segments buy finer resolution but yield fewer independent segments, so the PSD estimate is noisier (higher variance). This is the practical reason resting-state epoching often standardises on 2 s windows.
- Pick `duration` deliberately from the resolution the downstream analysis needs; pass the same length to `eeg-spectral` (Welch `n_per_seg = duration_s * sfreq`) so the epoching and PSD stages agree.
- Cite: Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra. *IEEE Trans. Audio Electroacoust.* 15(2), 70–73; standard FFT resolution relation Δf = fs/N.

### Trial counts and measurement quality

Report retained counts per participant and condition with score-specific
uncertainty where specified. A component name does not establish a universal
minimum trial count. Use the approved inclusion rule and preserve its scope;
quality concerns can be flagged without inventing participant exclusions.

### COBIDAS-MEEG reporting (Pernet et al. 2020, Nature Neuroscience)

For epoching, the methods section must report:
- Epoch time window (pre- and post-stimulus)
- Baseline correction window and method
- Artifact rejection method, criteria, and thresholds
- Number of trials per condition per subject (mean ± SD, range)
- Number of excluded subjects and reason
- Software and version
