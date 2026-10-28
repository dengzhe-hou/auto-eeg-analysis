# Method choices and numerical contract

Use this reference when adapting the spectral templates. Scientific settings
must be supplied by the explicit task or approved plan before computation. Keep
already fixed study configurations; do not infer missing values from an example.

| Choice | Record with the output | Why different choices can change the number |
| --- | --- | --- |
| Data selection | Participants, events/condition, time segment, actual channel names and identities | Auxiliary channels and different segments change the signal being summarized |
| Reference | Applied reference and contributor channels; pending projector state | Referencing changes channel signals before PSD estimation |
| PSD estimator | Welch/multitaper/other; taper, segment samples and seconds, overlap, FFT length, DC removal | Segment duration affects spectral resolution; zero padding changes the grid, not the resolving ability |
| Band definition | Exact numerator/denominator limits, boundary convention, actual bins and integration/mean rule | 8–12 and 8–13 Hz or mean density and integrated power are different quantities |
| Units and aggregation | V²/Hz or µV²/Hz; integrated units; linear/dB scale; channel/epoch/participant aggregation order | Unit conversions and averaging after a nonlinear transform do not commute |
| Alpha frequency | Search interval, peak/CoG method, smoothing, channel aggregation and missing-peak rule | These estimators need not produce the same alpha-frequency value |

The detailed procedure includes a labelled example JSON with 2 s Welch segments,
Hann taper and 50% overlap. It is not an automatic default. Executable templates
read the supplied configuration, reject missing Welch choices, and require an
explicit alpha estimator and search interval. They no longer silently shorten
a segment to fit an epoch. A resolved recipe may provide the parameters when
approved for this study. PSD-only tasks do not require unrequested band/alpha choices.

If the task fixes a choice, implement it and record the override. If it leaves
a consequential choice open, follow the project's researcher-decision policy:
propose it with a reason, or record it as unresolved during an unattended run.
Do not resolve it by searching for the setting closest to a benchmark answer.
For a plan that already approves these template values, retain them.

Checks should compare the same estimand and conventions. Independently recompute
the result with those settings and compare units and aggregation explicitly.
A result using another defensible definition can miss a fixed reference without
establishing that the method is scientifically wrong. Changing the benchmark's
acceptance policy is a separate evaluation decision; this skill does not do so.

Sources checked on 2026-10-28:

- [MNE Welch API](https://mne.tools/stable/generated/mne.time_frequency.psd_array_welch.html):
  segment length, FFT length, overlap, taper and DC removal.
- [SciPy Welch API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html):
  density/spectrum units and explicit estimator parameters.
- [MNE EEG reference tutorial](https://mne.tools/stable/auto_tutorials/preprocessing/55_setting_eeg_reference.html):
  reference application versus a pending projector.
